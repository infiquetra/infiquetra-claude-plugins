#!/usr/bin/env python3
"""Write-ahead child launch, interaction readiness, scope checks, and recorded reaping.

The register is the lifecycle authority.  This module deliberately keeps the three external
boundaries visible: :class:`AgentWrapper` runs the local ``agent`` launcher,
:class:`HerdrControl` reads and controls Herdr, and :class:`GitLanding` provisions worktrees and
enumerates changed paths.  The coordinating functions accept those adapters so ordering and
failure recovery can be tested without launching a real coding agent.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess  # nosec B404 -- fixed argv, no shell
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fleet_commons_shim
import herdr_events
import register as register_store
import subscriber

tier_resolver = fleet_commons_shim.load("tier_resolver")

TRUST_PROMPT_PATTERNS = (
    re.compile(r"do you trust", re.IGNORECASE),
    re.compile(r"trust (?:this|the) (?:folder|workspace|directory|project)", re.IGNORECASE),
    re.compile(r"workspace trust", re.IGNORECASE),
)
DEFAULT_HERDR_SESSION = "default"
IGNORED_PATHS_LIMITATION = (
    "Git-ignored paths are outside U4 scope observation; repository control-plane protection "
    "requires a separate filesystem boundary."
)


class SessionLifecycleError(RuntimeError):
    """Base error for lifecycle operations."""


class LaunchPreviewError(SessionLifecycleError):
    """The launcher's dry-run does not target the requested cwd or workspace."""


class LaunchProtocolError(SessionLifecycleError):
    """The launcher or Herdr returned an incomplete response."""


class NotReadyError(SessionLifecycleError):
    """A launched child did not prove readiness within the bounded window."""


class EffortNotAppliedError(NotReadyError):
    """A runtime acknowledged effort without applying it."""


class TrustPromptError(NotReadyError):
    """A child is parked on a trust prompt and must not receive work."""


class LandingError(SessionLifecycleError):
    """A mutating child's worktree or environment could not be provisioned."""


class ScopeViolationError(SessionLifecycleError):
    """A child changed a repository path outside its declared scope."""


class VanishedChildError(SessionLifecycleError):
    """A child disappeared before a recorded reap transition."""


@dataclass(frozen=True)
class ChildSpec:
    """One child launch request.

    ``scope`` contains repository-relative files or directory prefixes.  Mutating children receive
    a dedicated branch worktree.  ``environment_command`` is run in a newly created worktree; the
    default makes a uv-managed Python worktree independently runnable.

    The default carries ``--locked --extra dev`` because that is what this repository's CI
    provisions with (``.github/workflows/ci.yml``), and the whole reason the field exists is that
    a fresh worktree does not inherit the repository's ``.venv``, so a child in one cannot run its
    predicate at all.  A bare ``uv sync`` installs the runtime dependency set only: the resulting
    environment has no pytest, no ruff and no mypy, which is exactly the set of programs a
    predicate is most likely to be.
    """

    run_id: str
    row_id: str
    runtime: str
    work_shape: str
    instruction: str
    scope: tuple[str, ...]
    mutating: bool
    workspace: str
    readiness_timeout: float = 30.0
    environment_command: tuple[str, ...] = ("uv", "sync", "--locked", "--extra", "dev")


@dataclass(frozen=True)
class Landing:
    cwd: Path
    integration_mode: str
    destination: str
    base_commit: str | None = None
    ambient_root: Path | None = None


@dataclass(frozen=True)
class LaunchIdentity:
    agent_name: str
    workspace_id: str
    tab_id: str
    pane_id: str
    reused: bool


@dataclass(frozen=True)
class ReadyChild:
    identity: LaunchIdentity
    changed_paths_baseline: ChangedPathsBaseline
    readiness_sentinel: str


@dataclass(frozen=True)
class ChangedPathsBaseline:
    paths: frozenset[str]
    fingerprints: tuple[tuple[str, str], ...]
    ambient_paths: frozenset[str] = frozenset()
    ambient_fingerprints: tuple[tuple[str, str], ...] = ()
    ambient_base_commit: str | None = None


@dataclass(frozen=True)
class ScopeCheck:
    predicate_passed: bool
    changed_paths: frozenset[str]
    new_changed_paths: frozenset[str]
    outside_scope: frozenset[str]


Runner = Callable[..., Any]


def task_label(run_id: str, row_id: str) -> str:
    """Return the deterministic run-bound label used for launch recovery."""
    if not run_id or not row_id:
        raise ValueError("run_id and row_id must be non-empty")
    return f"orchestrate-{run_id}-{row_id}"


def permission_argv(runtime: str) -> list[str]:
    """Apply the vendor's workspace-write posture where the CLI exposes one.

    Every child gets the same posture, mutating or not, and the ``mutating`` distinction is
    deliberately **not** expressed as a flag any more.  A read-only child must still write exactly
    one thing -- its own deliverable -- and none of the supported CLIs accepts a repository-relative
    path allowlist, so there is no flag that permits that write and forbids every other one.  A
    read-only posture flag therefore never contained a read-only child; it only stopped it
    producing the artifact it was dispatched to produce, which is a launch that cannot succeed
    rather than a launch that is safe.

    What this posture **does** contain: writes outside the workspace the child was launched in.
    That is the only *containment* in the word's real sense -- a boundary the runtime refuses to
    let the child cross.  Inside the workspace nothing is contained.
    :func:`check_completion_scope` is **post-hoc, partial, repository-visible change detection**:
    it runs after the child has stopped, it reports rather than prevents, it observes only tracked
    and non-ignored paths, and in a shared checkout it cannot establish which actor made a change.
    A read-only child's empty repository write allowlist means any repository-visible write fails
    that child's completion -- which is a refusal to verify, not a write that did not happen.
    Git-ignored paths are outside even that -- see ``IGNORED_PATHS_LIMITATION`` -- which is why the
    durable dispatch receipt is authenticated rather than merely stored (``completion.py``).

    Claude and Muse expose no positive flag: Claude has no cwd-write boundary flag at all, and
    Muse's sandbox is already on by default.  Qwen's boolean ``--sandbox`` is its
    write-within-project profile on this host.
    """
    return {
        "claude": [],
        "codex": ["--sandbox", "workspace-write"],
        "grok": ["--sandbox", "workspace"],
        "muse": [],
        "qwen": ["--sandbox"],
        "agy": ["--sandbox"],
    }.get(runtime, [])


def _run_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    runner: Runner | None = None,
    timeout: float = 60.0,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run = runner or subprocess.run
    extra: dict[str, Any] = {}
    if env is not None:
        extra["env"] = dict(env)
    try:
        result = run(  # nosec B603 -- argv is a sequence and shell is never enabled
            list(argv),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            **extra,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SessionLifecycleError(f"command failed to run: {argv[0]}: {exc}") from exc
    if not isinstance(result, subprocess.CompletedProcess):
        # Test runners commonly return a duck-typed object; normalize it for callers.
        return subprocess.CompletedProcess(
            list(argv),
            int(getattr(result, "returncode", 1)),
            str(getattr(result, "stdout", "") or ""),
            str(getattr(result, "stderr", "") or ""),
        )
    return result


class AgentWrapper:
    """The control-only ``agent`` subprocess boundary."""

    def __init__(self, binary: str = "agent", *, runner: Runner | None = None) -> None:
        self.binary = binary
        self.runner = runner

    @staticmethod
    def _argv(
        spec: ChildSpec,
        landing: Landing,
        label: str,
        runtime_argv: Sequence[str],
        *,
        dry_run: bool,
    ) -> list[str]:
        argv = [spec.runtime]
        argv.extend(runtime_argv)
        launcher = [
            "--no-focus",
            "--current",
            "--herdr",
            "--herdr-control-only",
            "--herdr-session",
            DEFAULT_HERDR_SESSION,
            "--workspace",
            spec.workspace,
            "--task",
            label,
            "--cwd",
            str(landing.cwd.resolve()),
        ]
        if dry_run:
            launcher.insert(0, "--dry-run")
        return launcher + argv

    def preview(
        self,
        spec: ChildSpec,
        landing: Landing,
        label: str,
        runtime_argv: Sequence[str],
    ) -> None:
        result = _run_command(
            [self.binary, *self._argv(spec, landing, label, runtime_argv, dry_run=True)],
            cwd=landing.cwd,
            runner=self.runner,
        )
        if result.returncode != 0:
            raise LaunchPreviewError(result.stderr.strip() or "agent dry-run failed")
        lines = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        expected_cwd = str(landing.cwd.resolve())
        if lines.get("cwd") != expected_cwd:
            raise LaunchPreviewError(
                f"agent dry-run cwd {lines.get('cwd')!r} does not equal {expected_cwd!r}"
            )
        workspace = lines.get("herdr_workspace", "")
        if spec.workspace not in workspace:
            raise LaunchPreviewError(
                f"agent dry-run workspace {workspace!r} does not contain {spec.workspace!r}"
            )

    def launch(
        self,
        spec: ChildSpec,
        landing: Landing,
        label: str,
        runtime_argv: Sequence[str],
    ) -> LaunchIdentity:
        result = _run_command(
            [self.binary, *self._argv(spec, landing, label, runtime_argv, dry_run=False)],
            cwd=landing.cwd,
            runner=self.runner,
        )
        if result.returncode != 0:
            raise SessionLifecycleError(result.stderr.strip() or "agent launch failed")
        try:
            payload = json.loads(result.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise LaunchProtocolError("agent launch did not return one JSON object") from exc
        if not isinstance(payload, Mapping):
            raise LaunchProtocolError("agent launch JSON must be an object")
        values = {
            key: payload.get(key) for key in ("agent_name", "workspace_id", "tab_id", "pane_id")
        }
        if any(not isinstance(value, str) or not value for value in values.values()):
            raise LaunchProtocolError(f"agent launch JSON lacks identifiers: {values}")
        reused = payload.get("reused")
        if not isinstance(reused, bool):
            raise LaunchProtocolError("agent launch JSON field 'reused' must be boolean")
        return LaunchIdentity(reused=reused, **values)  # type: ignore[arg-type]


class HerdrControl:
    """Herdr command adapter for snapshot discovery and pane/tab control."""

    def __init__(self, binary: str = "herdr", *, runner: Runner | None = None) -> None:
        self.binary = binary
        self.runner = runner

    def _json(self, args: Sequence[str], *, cwd: Path) -> dict[str, Any]:
        result = _run_command(
            [self.binary, "--session", DEFAULT_HERDR_SESSION, *args],
            cwd=cwd,
            runner=self.runner,
        )
        if result.returncode != 0:
            raise LaunchProtocolError(result.stderr.strip() or f"herdr {' '.join(args)} failed")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise LaunchProtocolError(f"herdr {' '.join(args)} returned malformed JSON") from exc
        if not isinstance(payload, dict):
            raise LaunchProtocolError("herdr response must be an object")
        result_value = payload.get("result")
        if not isinstance(result_value, dict):
            raise LaunchProtocolError("herdr response lacks an object result")
        return result_value

    def snapshot(self, *, cwd: Path) -> dict[str, Any]:
        result = self._json(["api", "snapshot"], cwd=cwd)
        snapshot = result.get("snapshot")
        if not isinstance(snapshot, dict):
            raise LaunchProtocolError("herdr snapshot response lacks result.snapshot")
        return snapshot

    def discover_by_label(self, label: str, *, cwd: Path) -> LaunchIdentity | None:
        snapshot = self.snapshot(cwd=cwd)
        tabs = snapshot.get("tabs")
        panes = snapshot.get("panes")
        if not isinstance(tabs, list) or not isinstance(panes, list):
            raise LaunchProtocolError("herdr snapshot requires tabs and panes arrays")
        matches = [tab for tab in tabs if isinstance(tab, Mapping) and tab.get("label") == label]
        if not matches:
            return None
        if len(matches) != 1:
            raise LaunchProtocolError(f"run label {label!r} matches more than one Herdr tab")
        tab = matches[0]
        tab_id = tab.get("tab_id")
        workspace_id = tab.get("workspace_id")
        tab_panes = [
            pane for pane in panes if isinstance(pane, Mapping) and pane.get("tab_id") == tab_id
        ]
        if (
            not isinstance(tab_id, str)
            or not isinstance(workspace_id, str)
            or len(tab_panes) != 1
            or not isinstance(tab_panes[0].get("pane_id"), str)
        ):
            raise LaunchProtocolError(f"run label {label!r} does not resolve to one complete pane")
        pane_id = str(tab_panes[0]["pane_id"])
        agents = snapshot.get("agents", [])
        agent_name = label
        if isinstance(agents, list):
            matching_agent = next(
                (
                    agent
                    for agent in agents
                    if isinstance(agent, Mapping) and agent.get("pane_id") == pane_id
                ),
                None,
            )
            if isinstance(matching_agent, Mapping) and isinstance(matching_agent.get("name"), str):
                agent_name = str(matching_agent["name"])
        return LaunchIdentity(agent_name, workspace_id, tab_id, pane_id, reused=True)

    def pane_text(self, pane_id: str, *, cwd: Path) -> str:
        result = _run_command(
            [
                self.binary,
                "--session",
                DEFAULT_HERDR_SESSION,
                "pane",
                "read",
                pane_id,
                "--source",
                "recent-unwrapped",
            ],
            cwd=cwd,
            runner=self.runner,
        )
        if result.returncode != 0:
            raise LaunchProtocolError(result.stderr.strip() or "herdr pane read failed")
        return result.stdout

    def send_line(self, pane_id: str, text: str, *, cwd: Path) -> None:
        result = _run_command(
            [self.binary, "--session", DEFAULT_HERDR_SESSION, "pane", "run", pane_id, text],
            cwd=cwd,
            runner=self.runner,
        )
        if result.returncode != 0:
            raise LaunchProtocolError(result.stderr.strip() or "herdr pane run failed")

    def tab_present(self, tab_id: str, *, cwd: Path) -> bool:
        tabs = self.snapshot(cwd=cwd).get("tabs")
        if not isinstance(tabs, list):
            raise LaunchProtocolError("herdr snapshot lacks tabs")
        return any(isinstance(tab, Mapping) and tab.get("tab_id") == tab_id for tab in tabs)

    def close_tab(self, tab_id: str, *, cwd: Path) -> None:
        result = _run_command(
            [self.binary, "--session", DEFAULT_HERDR_SESSION, "tab", "close", tab_id],
            cwd=cwd,
            runner=self.runner,
        )
        if result.returncode != 0:
            raise LaunchProtocolError(result.stderr.strip() or "herdr tab close failed")


class HerdrInteraction:
    """One bounded ``pane.output_matched`` interaction over Herdr's Unix socket."""

    def __init__(self, socket_path: Path = herdr_events.DEFAULT_SOCKET_PATH) -> None:
        self.socket_path = socket_path

    @staticmethod
    def _read_json(stream: Any) -> dict[str, Any]:
        line = stream.readline()
        if not line:
            raise LaunchProtocolError("Herdr closed the socket during an interaction")
        try:
            payload = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LaunchProtocolError("Herdr returned malformed interaction JSON") from exc
        if not isinstance(payload, dict):
            raise LaunchProtocolError("Herdr interaction response must be an object")
        return payload

    def observe(
        self,
        *,
        pane_id: str,
        match: str,
        timeout: float,
        dispatch: Callable[[], Any],
        accept: Callable[[herdr_events.HerdrEvent, Any], bool] | None = None,
    ) -> tuple[herdr_events.HerdrEvent, Any]:
        """Subscribe first, then dispatch, and return the first accepted matching event."""
        subscription = {
            "type": "pane.output_matched",
            "pane_id": pane_id,
            "source": "recent_unwrapped",
            "match": {"type": "substring", "value": match},
        }
        request = herdr_events.build_subscribe_request("orchestrate-interaction", [subscription])
        deadline = time.monotonic() + timeout
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            try:
                sock.connect(str(self.socket_path))
                with sock.makefile("rwb") as stream:
                    stream.write(json.dumps(request, separators=(",", ":")).encode() + b"\n")
                    stream.flush()
                    started = self._read_json(stream)
                    if started.get("result") != {"type": "subscription_started"}:
                        raise LaunchProtocolError("Herdr did not confirm the output subscription")
                    dispatch_state = dispatch()
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise NotReadyError(
                                f"pane {pane_id} did not emit {match!r} within {timeout:g}s"
                            )
                        sock.settimeout(remaining)
                        try:
                            event = herdr_events.decode_event(self._read_json(stream))
                        except TimeoutError as exc:
                            raise NotReadyError(
                                f"pane {pane_id} did not emit {match!r} within {timeout:g}s"
                            ) from exc
                        if (
                            event.name == "pane.output_matched"
                            and event.pane_id == pane_id
                            and event.matched_line is not None
                            and match in event.matched_line
                            and (accept is None or accept(event, dispatch_state))
                        ):
                            return event, dispatch_state
            except OSError as exc:
                raise LaunchProtocolError(
                    f"cannot complete Herdr interaction at {self.socket_path}: {exc}"
                ) from exc
        raise NotReadyError(f"pane {pane_id} did not emit {match!r}")


class GitLanding:
    """Real Git worktree and repository-visible changed-path boundary.

    The boundary observes committed branch and ambient-checkout changes plus uncommitted tracked
    and non-ignored files in both working trees.
    Git-ignored paths are deliberately outside this control; see ``IGNORED_PATHS_LIMITATION``.
    """

    def __init__(self, *, runner: Runner | None = None) -> None:
        self.runner = runner

    def _git(
        self,
        root: Path,
        args: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        result = _run_command(["git", *args], cwd=root, runner=self.runner, env=env)
        if result.returncode != 0:
            raise LandingError(result.stderr.strip() or f"git {' '.join(args)} failed")
        return result

    def base_commit(self, root: Path) -> str:
        """Return the committed reference used as a child's launch baseline."""
        value = self._git(root, ["rev-parse", "HEAD"]).stdout.strip()
        if not value:
            raise LandingError("git rev-parse HEAD returned no commit")
        return value

    def rev_parse(self, root: Path, rev: str) -> str | None:
        """Resolve one revision to a commit, or ``None`` when it does not exist.

        ``base_commit`` cannot express "this branch may not exist yet", which is exactly the
        question the completion integration gate asks about a child's destination branch.
        """
        result = _run_command(
            ["git", "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"],
            cwd=root,
            runner=self.runner,
        )
        return result.stdout.strip() or None

    def common_dir(self, root: Path) -> Path:
        """The shared object store of the git repository that contains ``root``.

        Linked worktrees share the main checkout's common directory. An independent repository
        nested inside another checkout has its own. The path is absolute: the relative form is
        ``.git`` for every repository, which would make two different repositories compare equal.
        """
        # Membership probes fail permissively under GIT_DIR / GIT_COMMON_DIR: every
        # repository reports the inherited store, so two different checkouts compare
        # equal. Other git calls in this adapter fail loudly on a bad environment;
        # only this one would accept. Strip the inherited git identity, not the rest
        # of the process environment.
        env = {
            key: value
            for key, value in os.environ.items()
            if key
            not in {
                "GIT_DIR",
                "GIT_COMMON_DIR",
                "GIT_WORK_TREE",
                "GIT_OBJECT_DIRECTORY",
                "GIT_CEILING_DIRECTORIES",
            }
        }
        value = self._git(
            root,
            ["rev-parse", "--path-format=absolute", "--git-common-dir"],
            env=env,
        ).stdout.strip()
        if not value:
            raise LandingError(f"git rev-parse --git-common-dir returned no path at {root}")
        return Path(value).resolve()

    def is_invisible_to_boundary(self, root: Path, relative: str) -> bool:
        """Whether ``relative`` is genuinely outside what this boundary observes.

        Two independent conditions, because an ignore rule on its own answers a different
        question than the one the caller is asking.  ``git check-ignore`` reports whether the
        *rules* cover a path; a path that is already **tracked** stays visible to ``git status``
        and to the committed-diff comparison no matter what ``.gitignore`` says.  An operator who
        force-adds an artifact directory would otherwise get a check that still answers "ignored"
        while every write under that directory is reported as a change -- which is how a control
        ends up firing on the orchestrator's own correct work rather than on a child's.

        Answering "no" here is a refusal to dispatch, not a failure of the child, and the caller
        says how to clear it.
        """
        tracked = self._git(root, ["ls-files", "-z", "--", relative]).stdout
        if tracked.replace("\0", "").strip():
            return False
        result = _run_command(
            ["git", "check-ignore", "--quiet", "--no-index", "--", relative],
            cwd=root,
            runner=self.runner,
        )
        if result.returncode not in (0, 1):
            raise LandingError(result.stderr.strip() or "git check-ignore failed")
        return result.returncode == 0

    def provision(self, root: Path, spec: ChildSpec, *, base_commit: str | None = None) -> Landing:
        root = root.resolve()
        resolved_base = base_commit or self.base_commit(root)
        if not spec.mutating:
            return Landing(root, "none", "none", resolved_base, root)
        branch = task_label(spec.run_id, spec.row_id)
        path = root / ".orchestrate" / "worktrees" / spec.run_id / spec.row_id
        listed = self._git(root, ["worktree", "list", "--porcelain"]).stdout
        live_paths = {
            Path(line.removeprefix("worktree ")).resolve()
            for line in listed.splitlines()
            if line.startswith("worktree ")
        }
        created = path.resolve() not in live_paths
        if created:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._git(root, ["worktree", "add", "-b", branch, str(path), resolved_base])
        if spec.environment_command and (created or not (path / ".venv").exists()):
            result = _run_command(
                spec.environment_command, cwd=path, runner=self.runner, timeout=600
            )
            if result.returncode != 0:
                raise LandingError(
                    f"environment setup failed in {path}: "
                    f"{result.stderr.strip() or result.stdout.strip()}"
                )
        return Landing(path.resolve(), "branch", branch, resolved_base, root)

    def changed_paths(self, cwd: Path) -> frozenset[str]:
        """Return uncommitted tracked and non-ignored paths reported by Git status."""
        result = self._git(cwd, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
        raw = result.stdout.encode("utf-8", errors="surrogateescape")
        entries = raw.split(b"\0")
        paths: set[str] = set()
        index = 0
        while index < len(entries) and entries[index]:
            entry = entries[index]
            if len(entry) < 4:
                raise LandingError("git status returned a malformed porcelain entry")
            status = entry[:2]
            paths.add(entry[3:].decode("utf-8", errors="surrogateescape"))
            if b"R" in status or b"C" in status:
                index += 1
                if index >= len(entries) or not entries[index]:
                    raise LandingError("git status rename/copy entry lacks its source path")
                paths.add(entries[index].decode("utf-8", errors="surrogateescape"))
            index += 1
        return frozenset(paths)

    def committed_paths(
        self,
        cwd: Path,
        base_commit: str | None,
        *,
        upstream_commit: str | None = None,
    ) -> frozenset[str]:
        """Return both sides of committed changes relative to the applicable branch base.

        An isolated child worktree is compared with the merge base of its current tip and the
        ambient checkout's current tip. This excludes upstream commits after either a merge or a
        rebase while retaining the child's resulting tree changes. A child in the ambient checkout
        has no separate upstream and remains relative to its launch commit.
        """
        if base_commit is None:
            return frozenset()
        comparison_base = base_commit
        if upstream_commit is not None:
            comparison_base = self._git(cwd, ["merge-base", upstream_commit, "HEAD"]).stdout.strip()
            if not comparison_base:
                raise LandingError("git merge-base returned no commit")
        result = self._git(cwd, ["diff", "--name-status", "-z", comparison_base, "HEAD"])
        entries = result.stdout.encode("utf-8", errors="surrogateescape").split(b"\0")
        paths: set[str] = set()
        index = 0
        while index < len(entries) and entries[index]:
            status = entries[index]
            index += 1
            if index >= len(entries) or not entries[index]:
                raise LandingError("git diff name-status entry lacks its path")
            paths.add(entries[index].decode("utf-8", errors="surrogateescape"))
            index += 1
            if status.startswith((b"R", b"C")):
                if index >= len(entries) or not entries[index]:
                    raise LandingError("git diff rename/copy entry lacks its destination path")
                paths.add(entries[index].decode("utf-8", errors="surrogateescape"))
                index += 1
        return frozenset(paths)

    def observed_paths(
        self,
        cwd: Path,
        *,
        base_commit: str | None,
        upstream_commit: str | None = None,
    ) -> frozenset[str]:
        """Union committed branch changes with uncommitted repository-visible changes."""
        return self.committed_paths(
            cwd, base_commit, upstream_commit=upstream_commit
        ) | self.changed_paths(cwd)

    @staticmethod
    def fingerprint(cwd: Path, relative: str) -> str:
        path = cwd / relative
        if path.is_symlink():
            return "symlink:" + os.readlink(path)
        if not path.exists():
            return "missing"
        if path.is_dir():
            return "directory"
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return "file:" + digest.hexdigest()

    def changed_paths_baseline(
        self,
        cwd: Path,
        *,
        base_commit: str | None = None,
        ambient_root: Path | None = None,
    ) -> ChangedPathsBaseline:
        paths = self.observed_paths(cwd, base_commit=base_commit)
        observe_ambient = ambient_root is not None and ambient_root.resolve() != cwd.resolve()
        ambient_cwd = ambient_root if observe_ambient else None
        ambient_base_commit = self.base_commit(ambient_cwd) if ambient_cwd is not None else None
        ambient = (
            self.observed_paths(ambient_cwd, base_commit=ambient_base_commit)
            if ambient_cwd is not None
            else frozenset()
        )
        return ChangedPathsBaseline(
            paths,
            tuple((path, self.fingerprint(cwd, path)) for path in sorted(paths)),
            ambient,
            tuple(
                (path, self.fingerprint(ambient_cwd, path))
                for path in sorted(ambient)
                if ambient_cwd is not None
            ),
            ambient_base_commit,
        )


def _runtime_resolution(spec: ChildSpec, landing: Landing) -> tuple[Any, list[str]]:
    resolution = tier_resolver.resolve_for_runtime(spec.work_shape, spec.runtime)
    argv = tier_resolver.adapt_runtime_argv(spec.runtime, resolution.model, resolution.effort)
    argv.extend(permission_argv(spec.runtime))
    if spec.runtime == "muse" and spec.mutating:
        argv.extend(["--worktree", "existing", "--worktree-existing", str(landing.cwd)])
    return resolution, argv


def _row_identity(identity: LaunchIdentity) -> dict[str, Any]:
    return {
        "agent": identity.agent_name,
        "workspace_id": identity.workspace_id,
        "tab_id": identity.tab_id,
        "pane_id": identity.pane_id,
    }


def launch_child(
    root: Path,
    spec: ChildSpec,
    *,
    wrapper: AgentWrapper,
    herdr: HerdrControl,
    git: GitLanding,
) -> tuple[LaunchIdentity, Landing, Any]:
    """Write the launch intent, recover an existing label, or launch one child.

    Identifier fields are written immediately after the launcher returns, while the phase remains
    ``launching``. Dispatch later moves the row to ``launched`` before sending the task.
    """
    root = register_store.canonical_work_location(root)
    # The run's work location is the repository that contains this argument, not
    # a package subdirectory and not a value derived from the landing. Issuance
    # compares the claimed store against the record this writes.
    # Imported lazily: completion already imports this module.
    import completion as completion_mod

    completion_mod.record_run_root(root, spec.run_id)
    label = task_label(spec.run_id, spec.row_id)
    existing = register_store.read_rows(root, run_id=spec.run_id).get(spec.row_id)
    if existing and existing.get("phase") == "launching" and not existing.get("pane_id"):
        recovery_cwd = Path(str(existing.get("cwd", root)))
        recovered = herdr.discover_by_label(label, cwd=recovery_cwd)
        if recovered is not None:
            register_store.upsert_row(
                root, spec.row_id, _row_identity(recovered), run_id=spec.run_id
            )
            landing = Landing(
                recovery_cwd,
                str(existing.get("integration_mode", "none")),
                str(existing.get("destination", "none")),
                str(existing["base_commit"])
                if isinstance(existing.get("base_commit"), str)
                else None,
                root,
            )
            resolution, _ = _runtime_resolution(spec, landing)
            return recovered, landing, resolution

    base_commit_value = existing.get("base_commit") if existing else None
    base_commit = (
        str(base_commit_value) if isinstance(base_commit_value, str) else git.base_commit(root)
    )
    register_store.upsert_row(
        root,
        spec.row_id,
        {
            "run_id": spec.run_id,
            "agent": spec.runtime,
            "vendor": spec.runtime,
            "herdr_session": DEFAULT_HERDR_SESSION,
            "task": label,
            "work_shape": spec.work_shape,
            "scope": list(spec.scope),
            **({"base_commit": base_commit} if base_commit is not None else {}),
            "expected_state": "ready",
        },
        run_id=spec.run_id,
    )
    register_store.write_phase(root, spec.row_id, "planned", run_id=spec.run_id)
    landing = git.provision(root, spec, base_commit=base_commit)
    resolution, runtime_argv = _runtime_resolution(spec, landing)
    register_store.upsert_row(
        root,
        spec.row_id,
        {
            "model": resolution.model,
            "effort": resolution.effort,
            "cwd": str(landing.cwd),
            "integration_mode": landing.integration_mode,
            "destination": landing.destination,
        },
        run_id=spec.run_id,
    )
    wrapper.preview(spec, landing, label, runtime_argv)
    register_store.write_phase(root, spec.row_id, "launching", run_id=spec.run_id)
    identity = wrapper.launch(spec, landing, label, runtime_argv)
    register_store.upsert_row(root, spec.row_id, _row_identity(identity), run_id=spec.run_id)
    return identity, landing, resolution


def _is_trust_prompt(text: str) -> bool:
    return any(pattern.search(text) for pattern in TRUST_PROMPT_PATTERNS)


def confirm_ready(
    root: Path,
    spec: ChildSpec,
    identity: LaunchIdentity,
    landing: Landing,
    resolution: Any,
    *,
    herdr: HerdrControl,
    interaction: HerdrInteraction,
    git: GitLanding,
    sentinel_nonce: str | None = None,
) -> ReadyChild:
    """Establish effort when required, then dispatch and observe a readiness sentinel."""
    pane_text = herdr.pane_text(identity.pane_id, cwd=landing.cwd)
    if _is_trust_prompt(pane_text):
        register_store.record_observed_state(
            root,
            spec.row_id,
            "trust_prompt",
            source="observed:pane_content",
            run_id=spec.run_id,
        )
        raise TrustPromptError(f"child {spec.row_id} is blocked on a workspace trust prompt")

    effort_application = resolution.effort_application
    if effort_application.get("mode") == "in_session":
        command = effort_application.get("command")
        if not isinstance(command, str) or not command:
            raise LaunchProtocolError("in-session effort application lacks a command")
        acknowledgement = (
            f"Reasoning effort: {resolution.effort} "
            "(requested; the effective tier depends on the active provider/model)."
        )
        disabled_acknowledgement = (
            f"Reasoning effort set to {resolution.effort}, but thinking is currently disabled"
        )
        try:
            interaction.observe(
                pane_id=identity.pane_id,
                match="Reasoning effort",
                timeout=spec.readiness_timeout,
                dispatch=lambda: _count_and_send(
                    herdr,
                    identity.pane_id,
                    landing.cwd,
                    command,
                    (acknowledgement, disabled_acknowledgement),
                ),
                accept=lambda _event, previous_counts: _accept_effort_acknowledgement(
                    herdr,
                    identity.pane_id,
                    landing.cwd,
                    acknowledgement,
                    disabled_acknowledgement,
                    previous_counts,
                ),
            )
        except EffortNotAppliedError:
            register_store.record_observed_state(
                root,
                spec.row_id,
                "not_ready",
                source="inferred:effort_not_applied",
                run_id=spec.run_id,
            )
            raise
        except NotReadyError:
            register_store.record_observed_state(
                root,
                spec.row_id,
                "not_ready",
                source="inferred:effort_timeout",
                run_id=spec.run_id,
            )
            raise
    elif effort_application.get("mode") != "argv":
        raise LaunchProtocolError(f"unsupported effort application {effort_application!r}")

    sentinel = subscriber.make_sentinel(spec.run_id, spec.row_id, "readiness", nonce=sentinel_nonce)
    baseline_paths = ChangedPathsBaseline(frozenset(), ())

    def _dispatch() -> int:
        nonlocal baseline_paths
        baseline_paths = git.changed_paths_baseline(
            landing.cwd,
            base_commit=landing.base_commit,
            ambient_root=landing.ambient_root,
        )
        register_store.upsert_row(
            root,
            spec.row_id,
            {
                "phase": "launched",
                "dispatched_at": time.time(),
                "expected_state": "working",
            },
            run_id=spec.run_id,
            writer=register_store.PHASE_WRITER,
        )
        prompt = (
            subscriber.sentinel_assembly_instructions(sentinel, when="you are ready to begin")
            + "\n\n"
            + spec.instruction
        )
        herdr.send_line(identity.pane_id, prompt, cwd=landing.cwd)
        return 0

    try:
        interaction.observe(
            pane_id=identity.pane_id,
            match=sentinel,
            timeout=spec.readiness_timeout,
            dispatch=_dispatch,
        )
    except NotReadyError:
        register_store.record_observed_state(
            root,
            spec.row_id,
            "not_ready",
            source="inferred:readiness_timeout",
            run_id=spec.run_id,
        )
        raise
    register_store.write_phase(root, spec.row_id, "ready", run_id=spec.run_id)
    register_store.record_observed_state(
        root,
        spec.row_id,
        "ready",
        source="observed:pane.output_matched",
        run_id=spec.run_id,
    )
    return ReadyChild(identity, baseline_paths, sentinel)


def _count_and_send(
    herdr: HerdrControl,
    pane_id: str,
    cwd: Path,
    text: str,
    acknowledgements: tuple[str, str],
) -> tuple[int, int]:
    text_before = herdr.pane_text(pane_id, cwd=cwd)
    previous_counts = (
        text_before.count(acknowledgements[0]),
        text_before.count(acknowledgements[1]),
    )
    herdr.send_line(pane_id, text, cwd=cwd)
    return previous_counts


def _accept_effort_acknowledgement(
    herdr: HerdrControl,
    pane_id: str,
    cwd: Path,
    acknowledgement: str,
    disabled_acknowledgement: str,
    previous_counts: tuple[int, int],
) -> bool:
    text = herdr.pane_text(pane_id, cwd=cwd)
    if text.count(disabled_acknowledgement) > previous_counts[1]:
        raise EffortNotAppliedError(
            "Qwen acknowledged the effort request but thinking is disabled; "
            "re-enable thinking before dispatch"
        )
    return text.count(acknowledgement) > previous_counts[0]


def normalize_scope(scope: Sequence[str]) -> tuple[str, ...]:
    if not scope:
        return ()
    try:
        return register_store.normalize_repo_relative_paths(scope, what="scope entry")
    except register_store.RegisterError as exc:
        raise ValueError(str(exc)) from exc


def path_in_scope(path: str, scope: Sequence[str]) -> bool:
    return any(path == allowed or path.startswith(f"{allowed}/") for allowed in scope)


def _paths_changed_since_baseline(
    cwd: Path,
    final: frozenset[str],
    baseline_paths: frozenset[str],
    baseline_fingerprints: tuple[tuple[str, str], ...],
    git: GitLanding,
) -> set[str]:
    previous_fingerprints = dict(baseline_fingerprints)
    return {
        path
        for path in final | baseline_paths
        if path not in baseline_paths
        or path not in final
        or git.fingerprint(cwd, path) != previous_fingerprints[path]
    }


def check_completion_scope(
    spec: ChildSpec,
    landing: Landing,
    changed_paths_baseline: ChangedPathsBaseline,
    *,
    predicate_passed: bool,
    git: GitLanding,
) -> ScopeCheck:
    """Evaluate predicate and all repository-visible landing/ambient changes independently."""
    has_distinct_ambient = (
        landing.ambient_root is not None and landing.ambient_root.resolve() != landing.cwd.resolve()
    )
    upstream_commit = None
    if has_distinct_ambient and landing.ambient_root is not None:
        upstream_commit = git.base_commit(landing.ambient_root)
    final = git.observed_paths(
        landing.cwd,
        base_commit=landing.base_commit,
        upstream_commit=upstream_commit,
    )
    landing_changed = _paths_changed_since_baseline(
        landing.cwd,
        final,
        changed_paths_baseline.paths,
        changed_paths_baseline.fingerprints,
        git,
    )
    ambient_final: frozenset[str] = frozenset()
    ambient_changed: set[str] = set()
    if has_distinct_ambient and landing.ambient_root is not None:
        ambient_final = git.observed_paths(
            landing.ambient_root,
            base_commit=changed_paths_baseline.ambient_base_commit,
        )
        ambient_changed = _paths_changed_since_baseline(
            landing.ambient_root,
            ambient_final,
            changed_paths_baseline.ambient_paths,
            changed_paths_baseline.ambient_fingerprints,
            git,
        )
    scope = normalize_scope(spec.scope)
    landing_outside = {path for path in landing_changed if not path_in_scope(path, scope)}
    outside = frozenset(landing_outside | ambient_changed)
    new_changed = landing_changed | ambient_changed
    result = ScopeCheck(predicate_passed, final | ambient_final, frozenset(new_changed), outside)
    if outside:
        details: list[str] = []
        if landing_outside:
            if has_distinct_ambient:
                details.append(
                    "isolated landing outside declared scope: " + ", ".join(sorted(landing_outside))
                )
            else:
                details.append(
                    "shared-checkout landing outside declared scope; attribution to this child "
                    "is not established: " + ", ".join(sorted(landing_outside))
                )
        if ambient_changed:
            details.append("ambient checkout: " + ", ".join(sorted(ambient_changed)))
        raise ScopeViolationError("child boundary violation: " + "; ".join(details))
    return result


def reap_verified(
    root: Path,
    row_id: str,
    *,
    run_id: str,
    herdr: HerdrControl,
) -> None:
    """Record ``reaped`` before closing a verified child's tab.

    ``root`` must be the coordinator-recorded work location. A first-writer stamp
    is not enough. A disagreeing or unrecorded directory is refused and the tab is
    not closed.
    """
    register_store.assert_root_belongs_to_run(root, run_id, require_recorded=True)
    row = register_store.read_rows(root, run_id=run_id).get(row_id)
    if row is None or row.get("phase") not in {"verified", "reaped"}:
        raise SessionLifecycleError(f"child {row_id!r} must be verified before reap")
    tab_id = row.get("tab_id")
    if not isinstance(tab_id, str) or not tab_id:
        raise LaunchProtocolError(f"child {row_id!r} has no tab_id")
    cwd = Path(str(row.get("cwd", root)))
    if row.get("phase") != "reaped":
        register_store.write_phase(root, row_id, "reaped", run_id=run_id)
        register_store.upsert_row(root, row_id, {"expected_state": "exited"}, run_id=run_id)
    if herdr.tab_present(tab_id, cwd=cwd):
        herdr.close_tab(tab_id, cwd=cwd)


def assert_child_not_vanished(
    root: Path,
    row_id: str,
    *,
    run_id: str,
    herdr: HerdrControl,
) -> None:
    """Raise when a registered child disappears without a recorded reap.

    ``root`` must be the coordinator-recorded work location. A first-writer stamp
    is not enough. A disagreeing directory is refused rather than treated as a
    missing child.
    """
    register_store.assert_root_belongs_to_run(root, run_id, require_recorded=True)
    row = register_store.read_rows(root, run_id=run_id).get(row_id)
    if row is None:
        raise SessionLifecycleError(f"unknown child row {row_id!r}")
    if row.get("phase") == "reaped":
        return
    tab_id = row.get("tab_id")
    if not isinstance(tab_id, str) or not tab_id:
        raise LaunchProtocolError(f"child {row_id!r} has no tab_id")
    if not herdr.tab_present(tab_id, cwd=Path(str(row.get("cwd", root)))):
        raise VanishedChildError(f"child {row_id!r} vanished before the register recorded a reap")
