#!/usr/bin/env python3
"""Managed-session Runner for /code-review and /doc-review external reviewers.

``dispatch_second_opinion`` launches through this Runner. A started session
with no result file yet is ``pending``, not died. ``collect`` reads the later
result. A hanging wait is the caller's process to own.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

import engine_dispatch
import external_only
import reconcile

REVIEW_STAGES = frozenset({"code-review", "doc-review"})
SessionOutcome = Literal["not-started", "pending", "died", "ran-empty", "ran"]
_KNOWN_TOOLS = frozenset({"codex", "agy", "claude", "grok", "muse", "opencode", "qwen", "mimir"})


class SessionRunnerError(ValueError):
    """The managed-session runner or its selection is invalid."""


class SessionLaunchError(Exception):
    """The managed session never started."""


class SessionPending(Exception):  # noqa: N818 - pending is not an error
    """The session started; no terminal result exists yet."""


class SessionCollectError(Exception):
    """The session started but produced no usable result."""


@dataclass(frozen=True)
class SessionHandle:
    """Identity of a session that ``start`` claims to have launched."""

    label: str
    request_digest: str
    result_path: Path
    tool: str
    tab_id: str | None = None
    argv: tuple[str, ...] = ()
    pid: int | None = None
    exit_code: int | None = None
    model: str | None = None
    effort: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "label": self.label,
            "request_digest": self.request_digest,
            "result_path": str(self.result_path),
            "tool": self.tool,
            "argv": list(self.argv),
        }
        if self.tab_id is not None:
            data["tab_id"] = self.tab_id
        if self.pid is not None:
            data["pid"] = self.pid
        if self.exit_code is not None:
            data["exit_code"] = self.exit_code
        if self.model is not None:
            data["model"] = self.model
        if self.effort is not None:
            data["effort"] = self.effort
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SessionHandle:
        path = data.get("result_path")
        digest = data.get("request_digest")
        label = data.get("label")
        tool = data.get("tool")
        if not isinstance(path, str) or not path:
            raise SessionCollectError("session handle is missing result_path")
        if not isinstance(digest, str) or not digest:
            raise SessionCollectError("session handle is missing request_digest")
        if not isinstance(label, str) or not label:
            raise SessionCollectError("session handle is missing label")
        if not isinstance(tool, str) or not tool:
            raise SessionCollectError("session handle is missing tool")
        raw_argv = data.get("argv") or []
        argv = tuple(str(item) for item in raw_argv) if isinstance(raw_argv, list) else ()
        return cls(
            label=label,
            request_digest=digest,
            result_path=Path(path),
            tool=tool,
            tab_id=_optional_str(data.get("tab_id")),
            argv=argv,
            pid=data.get("pid") if isinstance(data.get("pid"), int) else None,
            exit_code=data.get("exit_code") if isinstance(data.get("exit_code"), int) else None,
            model=_optional_str(data.get("model")),
            effort=_optional_str(data.get("effort")),
        )


@dataclass(frozen=True)
class CollectedSession:
    """A completed session's typed findings. Absence of this type is not emptiness."""

    findings: tuple[dict[str, Any], ...]
    output: str


@dataclass(frozen=True)
class CommandResult:
    """One launcher process completion."""

    returncode: int
    stdout: str = ""
    stderr: str = ""
    pid: int | None = None


CommandRun = Callable[[list[str]], CommandResult]


class SessionLauncher(Protocol):
    """Start a managed session and later collect its result."""

    def start(self, invocation: Mapping[str, Any]) -> SessionHandle:
        """Launch the session. Raise ``SessionLaunchError`` if it never started."""

    def collect(self, handle: SessionHandle) -> CollectedSession:
        """Read the session's result. Raise ``SessionPending`` if none exists yet."""


def classify_session_result(result: Mapping[str, Any]) -> SessionOutcome:
    """Name what the runner learned. Missing the field is an error, not a guess."""
    outcome = result.get("session_outcome")
    if outcome == "not-started":
        return "not-started"
    if outcome == "pending":
        return "pending"
    if outcome == "died":
        return "died"
    if outcome == "ran-empty":
        return "ran-empty"
    if outcome == "ran":
        return "ran"
    raise SessionRunnerError("runner result is missing a session_outcome")


def reviewer_tool(invocation: Mapping[str, Any]) -> str:
    """Return the agent tool named by a real dispatch invocation."""
    schema = invocation.get("schema")
    if schema == "agy.delegation.v1":
        return "agy"
    via = invocation.get("via")
    if isinstance(via, str) and via.strip():
        prefix = via.split(":", 1)[0].strip().casefold()
        if prefix == "engine-bridge-http" or invocation.get("transport") == "http":
            raise SessionLaunchError("http transport is not a managed session")
        if prefix in _KNOWN_TOOLS:
            return prefix
    engine_id = invocation.get("engine_id")
    if isinstance(engine_id, str) and engine_id.strip():
        return external_only.vendor_of(engine_id)
    raise SessionLaunchError("invocation names no reviewer tool")


def invocation_vendor(invocation: Mapping[str, Any]) -> str:
    return external_only.vendor_of(reviewer_tool(invocation))


def request_digest_for(invocation: Mapping[str, Any]) -> str:
    supplied = invocation.get("request_digest")
    if isinstance(supplied, str) and supplied.strip():
        return supplied.strip()
    payload = {
        "via": invocation.get("via"),
        "schema": invocation.get("schema"),
        "task": invocation.get("task"),
        "model": invocation.get("model"),
        "effort": invocation.get("effort"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def result_path_for(cwd: Path, digest: str) -> Path:
    return Path(cwd) / ".saga" / "second-opinion-results" / f"{digest}.json"


def read_result_file(handle: SessionHandle) -> CollectedSession:
    """Load a terminal envelope bound to this handle.

    A missing file is not an empty review. A file that never names findings is
    not an empty review. A file bound to another request is not this review.
    """
    if not handle.result_path.is_file():
        raise SessionPending("managed session has not written a result file yet")
    try:
        payload = json.loads(handle.result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionCollectError(f"managed session result file is unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise SessionCollectError("managed session result file must be an object")
    if "findings" not in payload:
        raise SessionCollectError("result file does not claim findings")
    raw_findings = payload["findings"]
    if not isinstance(raw_findings, list) or not all(
        isinstance(item, dict) for item in raw_findings
    ):
        raise SessionCollectError("managed session result findings must be an object array")
    digest = payload.get("request_digest")
    if digest != handle.request_digest:
        raise SessionCollectError("result file is not bound to this request")
    try:
        typed = reconcile.parse_source_findings(raw_findings)
    except reconcile.ReconciliationError as exc:
        raise SessionCollectError(f"result findings are not a typed envelope: {exc}") from exc
    return CollectedSession(
        findings=tuple({"content": item.content} for item in typed),
        output=reconcile.render_source_findings(typed),
    )


def runner(*, launcher: SessionLauncher) -> engine_dispatch.Runner:
    """Return a Runner that launches or collects a managed session."""

    def invoke(invocation: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(invocation, dict):
            raise SessionRunnerError("invocation must be an object")
        if invocation.get("operation") == "collect":
            raw_handle = invocation.get("handle")
            if not isinstance(raw_handle, dict):
                raise SessionRunnerError("collect invocation requires a handle")
            return _collect_result(launcher, SessionHandle.from_dict(raw_handle))
        try:
            handle = launcher.start(invocation)
        except SessionLaunchError as exc:
            return {
                "status": "error",
                "output": "",
                "session_outcome": "not-started",
                "reason": str(exc) or "managed session could not be started",
            }
        return _collect_result(launcher, handle)

    return invoke


def _collect_result(launcher: SessionLauncher, handle: SessionHandle) -> dict[str, Any]:
    try:
        collected = launcher.collect(handle)
    except SessionPending as exc:
        return {
            "status": "pending",
            "output": "",
            "session_outcome": "pending",
            "handle": handle.to_dict(),
            "reason": str(exc) or "managed session has not resolved",
        }
    except SessionCollectError as exc:
        return {
            "status": "no-output",
            "output": "",
            "session_outcome": "died",
            "handle": handle.to_dict(),
            "reason": str(exc) or "managed session produced no usable result",
        }
    findings = list(collected.findings)
    if not findings:
        return {
            "status": "ok",
            "output": collected.output if collected.output else "[]",
            "findings": [],
            "session_outcome": "ran-empty",
            "handle": handle.to_dict(),
        }
    return {
        "status": "ok",
        "output": collected.output,
        "findings": findings,
        "session_outcome": "ran",
        "handle": handle.to_dict(),
    }


def bound_runner(
    *,
    launcher: SessionLauncher,
    allowed_vendor: str,
    home_vendor: str,
    mode: str,
) -> engine_dispatch.Runner:
    """A runner that cannot start the excluded vendor under external-only."""
    inner = runner(launcher=launcher)

    def invoke(invocation: dict[str, Any]) -> dict[str, Any]:
        if invocation.get("operation") == "collect":
            return inner(invocation)
        if mode == external_only.EXTERNAL_ONLY_MODE:
            try:
                vendor = invocation_vendor(invocation)
                excluded = external_only.vendor_of(home_vendor)
                allowed = external_only.vendor_of(allowed_vendor)
            except (SessionLaunchError, external_only.ExternalOnlyError) as exc:
                return {
                    "status": "error",
                    "output": "",
                    "session_outcome": "not-started",
                    "reason": str(exc) or "invocation names no reviewer tool",
                }
            if vendor == excluded:
                return {
                    "status": "error",
                    "output": "",
                    "session_outcome": "not-started",
                    "reason": "excluded vendor cannot start an external-only session",
                }
            if vendor != allowed:
                return {
                    "status": "error",
                    "output": "",
                    "session_outcome": "not-started",
                    "reason": "invocation vendor is not the admitted external-only vendor",
                }
        return inner(invocation)

    return invoke


def select_review_runner(
    *,
    stage: str,
    mode: str,
    home_vendor: str,
    engine_id: str,
    launcher: SessionLauncher,
) -> engine_dispatch.Runner | external_only.ExternalOnlyHalt:
    """The only runner /code-review and /doc-review may inject for an external reviewer.

    There is no alternate runner argument. Under external-only, an excluded-vendor
    ``engine_id`` is a halt, not a session. The returned runner stays bound to the
    admitted vendor.
    """
    if stage not in REVIEW_STAGES:
        raise SessionRunnerError(
            f"managed-session runner is only for {sorted(REVIEW_STAGES)}, not {stage!r}"
        )
    if mode not in {external_only.ADDITIVE_MODE, external_only.EXTERNAL_ONLY_MODE}:
        raise SessionRunnerError(f"unsupported review mode {mode!r}")
    if mode == external_only.EXTERNAL_ONLY_MODE:
        admitted = external_only.admit_external_only(
            home_vendor=home_vendor,
            candidates=(engine_id,),
            quorum=1,
        )
        if isinstance(admitted, external_only.ExternalOnlyHalt):
            return admitted
        allowed = admitted.members[0] if admitted.members else engine_id
        return bound_runner(
            launcher=launcher,
            allowed_vendor=external_only.vendor_of(allowed),
            home_vendor=home_vendor,
            mode=mode,
        )
    return bound_runner(
        launcher=launcher,
        allowed_vendor=external_only.vendor_of(engine_id),
        home_vendor=home_vendor,
        mode=mode,
    )


def subprocess_run(argv: list[str]) -> CommandResult:
    completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        pid=completed.pid,
    )


@dataclass(frozen=True)
class CommandSessionLauncher:
    """Launch via an injected command runner. Production may omit ``run``.

    Tests pass a scripted ``run``. This type never waits on a live session.
    """

    cwd: Path
    run: CommandRun = subprocess_run
    binary: str = "agent"
    collect_result: Callable[[SessionHandle], CollectedSession] | None = None

    def start(self, invocation: Mapping[str, Any]) -> SessionHandle:
        tool = reviewer_tool(invocation)
        digest = request_digest_for(invocation)
        model = _optional_str(invocation.get("model"))
        effort = _optional_str(invocation.get("effort"))
        task = invocation.get("task")
        if not isinstance(task, str) or not task.strip():
            raise SessionLaunchError("invocation carries no review task")
        result_path = result_path_for(self.cwd, digest)
        if result_path.exists():
            raise SessionLaunchError("result path already exists; not this session")
        result_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path = result_path.with_suffix(".prompt.md")
        prompt_path.write_text(
            _prompt_for(task, result_path=result_path, request_digest=digest),
            encoding="utf-8",
        )
        label = f"so-{digest[:12]}"
        argv = [
            self.binary,
            "--no-focus",
            "--current",
            "--herdr",
            "--herdr-control-only",
            "--task",
            label,
            "--cwd",
            str(self.cwd.resolve()),
            tool,
        ]
        if model:
            argv.extend(["--model", model])
        if effort:
            if tool == "codex":
                argv.extend(["-c", f"model_reasoning_effort={effort}"])
            else:
                argv.extend(["--effort", effort])
        argv.append(str(prompt_path))
        try:
            completed = self.run(argv)
        except OSError as exc:
            raise SessionLaunchError(f"managed session launcher failed: {exc}") from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip() or f"exit {completed.returncode}"
            raise SessionLaunchError(f"managed session could not be started: {detail}")
        tab_id = _optional_tab_id(completed.stdout)
        return SessionHandle(
            label=label,
            request_digest=digest,
            result_path=result_path,
            tool=tool,
            tab_id=tab_id,
            argv=tuple(argv),
            pid=completed.pid,
            exit_code=completed.returncode,
            model=model,
            effort=effort,
        )

    def collect(self, handle: SessionHandle) -> CollectedSession:
        if self.collect_result is not None:
            return self.collect_result(handle)
        return read_result_file(handle)


def _prompt_for(task: str, *, result_path: Path, request_digest: str) -> str:
    return (
        f"{task.rstrip()}\n\n"
        "Write one JSON object to the result path when finished. The object must "
        f"include request_digest {request_digest!r} and a findings array of objects "
        "that each contain only a content string. Other keys, including output, "
        f"are ignored. Result path: {result_path}\n"
    )


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _optional_tab_id(stdout: str) -> str | None:
    text = stdout.strip()
    if not text:
        return None
    try:
        payload = json.loads(text.splitlines()[-1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    tab_id = payload.get("tab_id")
    if isinstance(tab_id, str) and tab_id:
        return tab_id
    return None


DEFAULT_CLAIM_STORE = Path(".saga") / "second-opinion-claims.json"


def handle_from_payload(data: Mapping[str, Any]) -> SessionHandle:
    """Accept a bare handle or the launch command's full JSON object."""
    if not isinstance(data, Mapping):
        raise SessionCollectError("session handle file must contain an object")
    nested = data.get("handle")
    if isinstance(nested, dict) and "result_path" not in data:
        return SessionHandle.from_dict(nested)
    return SessionHandle.from_dict(data)


def flatten_launch_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """Put handle fields at the top level so collect can read launch stdout as-is."""
    payload = dict(result)
    handle = result.get("handle")
    if isinstance(handle, dict):
        for key, value in handle.items():
            payload.setdefault(key, value)
    return payload


def _claim_store_from_args(args: argparse.Namespace) -> Any:
    import second_opinion as so

    root = Path(getattr(args, "repo_root", "."))
    store_path = Path(args.claim_store)
    if not store_path.is_absolute():
        store_path = root / store_path
    return so.SecondOpinionClaimStore(store_path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    launch = sub.add_parser("launch", help="start a managed-session reviewer")
    launch.add_argument("--invocation-file", required=True)
    launch.add_argument("--repo-root", default=".")
    launch.add_argument("--stage", choices=sorted(REVIEW_STAGES), default="code-review")
    launch.add_argument("--mode", default=external_only.ADDITIVE_MODE)
    launch.add_argument("--home-vendor", default="")
    launch.add_argument("--engine-id", default="")
    launch.add_argument("--claim-store", default=str(DEFAULT_CLAIM_STORE))
    collect = sub.add_parser("collect", help="read a launched session's result file")
    collect.add_argument("--handle-file", required=True)
    collect.add_argument("--repo-root", default=".")
    collect.add_argument("--claim-store", default=str(DEFAULT_CLAIM_STORE))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "launch":
        invocation = json.loads(Path(args.invocation_file).read_text(encoding="utf-8"))
        if not isinstance(invocation, dict):
            parser.error("invocation file must contain an object")
        digest = invocation.get("request_digest")
        if not isinstance(digest, str) or not digest.strip():
            parser.error("invocation must include request_digest so the claim can be reserved")
        import second_opinion as so

        store = _claim_store_from_args(args)
        try:
            store.reserve_pending_for_digest(digest)
        except so.PendingBoundError as exc:
            print(json.dumps({"halt": str(exc), "session_outcome": "not-started"}))
            return 2
        except so.SecondOpinionError as exc:
            parser.error(str(exc))
        engine_id = args.engine_id or invocation.get("engine_id") or reviewer_tool(invocation)
        launcher = CommandSessionLauncher(cwd=Path(args.repo_root))
        selected = select_review_runner(
            stage=args.stage,
            mode=args.mode,
            home_vendor=args.home_vendor or engine_id,
            engine_id=str(engine_id),
            launcher=launcher,
        )
        if isinstance(selected, external_only.ExternalOnlyHalt):
            print(json.dumps({"halt": selected.reason, "excluded": selected.excluded_vendor}))
            return 2
        result = selected(invocation)
        handle = result.get("handle")
        if isinstance(handle, dict) and result.get("session_outcome") == "pending":
            store.record_handle_for_digest(digest, handle=handle)
        print(json.dumps(flatten_launch_result(result), sort_keys=True, default=str))
        return 0 if result.get("session_outcome") in {"pending", "ran", "ran-empty"} else 1
    raw_handle = json.loads(Path(args.handle_file).read_text(encoding="utf-8"))
    if not isinstance(raw_handle, dict):
        parser.error("handle file must contain an object")
    handle = handle_from_payload(raw_handle)
    launcher = CommandSessionLauncher(cwd=handle.result_path.parent)
    result = _collect_result(launcher, handle)
    print(json.dumps(flatten_launch_result(result), sort_keys=True, default=str))
    return 0 if result.get("session_outcome") in {"pending", "ran", "ran-empty"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
