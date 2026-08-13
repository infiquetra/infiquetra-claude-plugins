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
from pathlib import Path, PurePosixPath
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
    a dedicated branch worktree.  ``environment_command`` is run in a newly created worktree;
    the default makes a uv-managed Python worktree independently runnable.
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
    environment_command: tuple[str, ...] = ("uv", "sync")


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


def permission_argv(runtime: str, *, mutating: bool) -> list[str]:
    """Apply real vendor read/write posture flags where the CLI exposes one.

    These flags are defence in depth.  They do not replace the final Git boundary check, because
    none of the supported CLIs accepts a repository-relative path allowlist. For mutating work,
    Codex, Grok, Qwen, and Agy expose sandbox flags. Claude exposes no cwd-write boundary flag.
    Muse's sandbox is on by default and its existing-worktree binding is applied separately.
    """
    if mutating:
        return {
            # Claude has no CLI flag that constrains writes to the launch cwd.
            "claude": [],
            "codex": ["--sandbox", "workspace-write"],
            "grok": ["--sandbox", "workspace"],
            # Muse enables its sandbox by default; _runtime_resolution also binds its existing
            # worktree. There is no positive CLI flag to enable a narrower write posture.
            "muse": [],
            # Qwen's boolean sandbox uses its write-within-project profile on this host.
            "qwen": ["--sandbox"],
            "agy": ["--sandbox"],
        }.get(runtime, [])
    return {
        "claude": ["--permission-mode", "plan"],
        "codex": ["--sandbox", "read-only"],
        "grok": ["--permission-mode", "plan"],
        "muse": ["--disable-write"],
        "agy": ["--mode", "plan"],
        # Qwen's --sandbox is not a read-only mode, so it would overstate the control.
        "qwen": [],
    }.get(runtime, [])


def _run_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    runner: Runner | None = None,
    timeout: float = 60.0,
) -> subprocess.CompletedProcess[str]:
    run = runner or subprocess.run
    try:
        result = run(  # nosec B603 -- argv is a sequence and shell is never enabled
            list(argv),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
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

    def _git(self, root: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        result = _run_command(["git", *args], cwd=root, runner=self.runner)
        if result.returncode != 0:
            raise LandingError(result.stderr.strip() or f"git {' '.join(args)} failed")
        return result

    def base_commit(self, root: Path) -> str:
        """Return the committed reference used to create a mutating child's branch."""
        value = self._git(root, ["rev-parse", "HEAD"]).stdout.strip()
        if not value:
            raise LandingError("git rev-parse HEAD returned no commit")
        return value

    def provision(self, root: Path, spec: ChildSpec, *, base_commit: str | None = None) -> Landing:
        root = root.resolve()
        if not spec.mutating:
            return Landing(root, "none", "none", ambient_root=root)
        resolved_base = base_commit or self.base_commit(root)
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

    def committed_paths(self, cwd: Path, base_commit: str | None) -> frozenset[str]:
        """Return both sides of every committed path change since ``base_commit``."""
        if base_commit is None:
            return frozenset()
        result = self._git(cwd, ["diff", "--name-status", "-z", base_commit, "HEAD"])
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

    def observed_paths(self, cwd: Path, *, base_commit: str | None) -> frozenset[str]:
        """Union committed branch changes with uncommitted repository-visible changes."""
        return self.committed_paths(cwd, base_commit) | self.changed_paths(cwd)

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
    argv.extend(permission_argv(spec.runtime, mutating=spec.mutating))
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
    root = root.resolve()
    label = task_label(spec.run_id, spec.row_id)
    existing = register_store.read_rows(root).get(spec.row_id)
    if existing and existing.get("phase") == "launching" and not existing.get("pane_id"):
        recovery_cwd = Path(str(existing.get("cwd", root)))
        recovered = herdr.discover_by_label(label, cwd=recovery_cwd)
        if recovered is not None:
            register_store.upsert_row(root, spec.row_id, _row_identity(recovered))
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
        str(base_commit_value)
        if isinstance(base_commit_value, str)
        else git.base_commit(root)
        if spec.mutating
        else None
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
            "phase": "planned",
            "expected_state": "ready",
        },
    )
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
    )
    wrapper.preview(spec, landing, label, runtime_argv)
    register_store.upsert_row(root, spec.row_id, {"phase": "launching"})
    identity = wrapper.launch(spec, landing, label, runtime_argv)
    register_store.upsert_row(root, spec.row_id, _row_identity(identity))
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
        register_store.upsert_row(
            root,
            spec.row_id,
            {
                "observed_state": "trust_prompt",
                "observed_state_source": "observed:pane_content",
            },
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
        register_store.upsert_row(
            root,
            spec.row_id,
            {
                "observed_state": "not_ready",
                "observed_state_source": "inferred:readiness_timeout",
            },
        )
        raise
    register_store.upsert_row(
        root,
        spec.row_id,
        {
            "phase": "ready",
            "observed_state": "ready",
            "observed_state_source": "observed:pane.output_matched",
        },
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
        raise NotReadyError(
            "Qwen acknowledged the effort request but thinking is disabled; "
            "re-enable thinking before dispatch"
        )
    return text.count(acknowledgement) > previous_counts[0]


def _normalize_scope(scope: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for item in scope:
        path = PurePosixPath(item)
        if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
            raise ValueError(f"scope entry {item!r} must be a bounded repository-relative path")
        normalized.append(path.as_posix().rstrip("/"))
    return tuple(normalized)


def _in_scope(path: str, scope: Sequence[str]) -> bool:
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
    final = git.observed_paths(landing.cwd, base_commit=landing.base_commit)
    new_changed = _paths_changed_since_baseline(
        landing.cwd,
        final,
        changed_paths_baseline.paths,
        changed_paths_baseline.fingerprints,
        git,
    )
    ambient_final: frozenset[str] = frozenset()
    if landing.ambient_root is not None and landing.ambient_root.resolve() != landing.cwd.resolve():
        ambient_final = git.observed_paths(
            landing.ambient_root,
            base_commit=changed_paths_baseline.ambient_base_commit,
        )
        new_changed.update(
            _paths_changed_since_baseline(
                landing.ambient_root,
                ambient_final,
                changed_paths_baseline.ambient_paths,
                changed_paths_baseline.ambient_fingerprints,
                git,
            )
        )
    scope = _normalize_scope(spec.scope)
    outside = frozenset(path for path in new_changed if not _in_scope(path, scope))
    result = ScopeCheck(predicate_passed, final | ambient_final, frozenset(new_changed), outside)
    if outside:
        raise ScopeViolationError(
            "child changed paths outside its declared scope: " + ", ".join(sorted(outside))
        )
    return result


def reap_verified(
    root: Path,
    row_id: str,
    *,
    herdr: HerdrControl,
) -> None:
    """Record ``reaped`` before closing a verified child's tab."""
    row = register_store.read_rows(root).get(row_id)
    if row is None or row.get("phase") not in {"verified", "reaped"}:
        raise SessionLifecycleError(f"child {row_id!r} must be verified before reap")
    tab_id = row.get("tab_id")
    if not isinstance(tab_id, str) or not tab_id:
        raise LaunchProtocolError(f"child {row_id!r} has no tab_id")
    cwd = Path(str(row.get("cwd", root)))
    if row.get("phase") != "reaped":
        register_store.upsert_row(root, row_id, {"phase": "reaped", "expected_state": "exited"})
    if herdr.tab_present(tab_id, cwd=cwd):
        herdr.close_tab(tab_id, cwd=cwd)


def assert_child_not_vanished(
    root: Path,
    row_id: str,
    *,
    herdr: HerdrControl,
) -> None:
    """Raise when a registered child disappears without a recorded reap."""
    row = register_store.read_rows(root).get(row_id)
    if row is None:
        raise SessionLifecycleError(f"unknown child row {row_id!r}")
    if row.get("phase") == "reaped":
        return
    tab_id = row.get("tab_id")
    if not isinstance(tab_id, str) or not tab_id:
        raise LaunchProtocolError(f"child {row_id!r} has no tab_id")
    if not herdr.tab_present(tab_id, cwd=Path(str(row.get("cwd", root)))):
        raise VanishedChildError(f"child {row_id!r} vanished before the register recorded a reap")
