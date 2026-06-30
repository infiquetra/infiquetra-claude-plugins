#!/usr/bin/env python3
"""Antigravity delegation wrapper.

U2 owns envelope validation and evidence bundle creation. U3 adds the
supervised `agy` subprocess path and transcript provenance classifier. Later
units add the repository clone boundary and patch import gate.
"""

from __future__ import annotations

import argparse
import json
import os
import selectors
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "agy.delegation.v1"

ROLES = frozenset({"coder", "reviewer"})
MODES = frozenset({"no-write", "patch-only", "auto-if-clean"})
REVIEW_LENSES = frozenset({"adversarial", "quality", "scope-gap", "security-ops"})
EVIDENCE_LEVELS = frozenset({"minimal", "summary", "full"})
APPLY_POLICIES = frozenset({"preserve-patch", "apply-if-clean"})
RUN_SCOPES = frozenset({"clone", "live", "none"})
STATUSES = frozenset(
    {
        "success",
        "patch_ready",
        "applied",
        "plan_gap",
        "test_conflict",
        "path_missing",
        "timeout",
        "no_output",
        "fallback_suspected",
        "out_of_scope_mutation",
        "checks_failed",
        "shutdown_incomplete",
        "bundle_failed",
        "error",
    }
)


class EnvelopeError(ValueError):
    """Raised when a delegation envelope violates the v1 contract."""


@dataclass(frozen=True)
class VerificationPolicy:
    commands: list[str]
    required: bool
    run_scope: str

    @classmethod
    def from_mapping(cls, value: Any) -> VerificationPolicy:
        if value is None:
            return cls(commands=[], required=False, run_scope="clone")
        if not isinstance(value, dict):
            raise EnvelopeError("verification must be an object")

        commands = value.get("commands", [])
        if not isinstance(commands, list) or not all(
            isinstance(command, str) and command.strip() for command in commands
        ):
            raise EnvelopeError("verification.commands must be a list of non-empty strings")

        required = value.get("required", False)
        if not isinstance(required, bool):
            raise EnvelopeError("verification.required must be a boolean")
        if required and not commands:
            raise EnvelopeError("verification.commands is required when verification.required is true")

        run_scope = value.get("run_scope", "clone")
        if run_scope not in RUN_SCOPES:
            raise EnvelopeError(_enum_error("verification.run_scope", run_scope, RUN_SCOPES))

        return cls(commands=commands, required=required, run_scope=run_scope)


@dataclass(frozen=True)
class Envelope:
    schema: str
    role: str
    mode: str
    task: str
    model: str
    review_lens: str | None
    write_set: list[str]
    apply_policy: str
    evidence: str
    verification: VerificationPolicy
    timeout_seconds: int
    no_output_seconds: int
    provenance_required: bool

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> Envelope:
        schema = _string_field(value, "schema", default=SCHEMA)
        if schema != SCHEMA:
            raise EnvelopeError(f"schema must be {SCHEMA}")

        role = _enum_field(value, "role", ROLES)
        mode = _enum_field(value, "mode", MODES, default=_default_mode(role))
        task = _string_field(value, "task")
        model = _string_field(value, "model", default="flash")

        review_lens = value.get("review_lens")
        if review_lens is not None:
            if not isinstance(review_lens, str):
                raise EnvelopeError("review_lens must be a string or null")
            if review_lens not in REVIEW_LENSES:
                raise EnvelopeError(_enum_error("review_lens", review_lens, REVIEW_LENSES))

        write_set = _write_set(value.get("write_set", []))
        if mode == "auto-if-clean" and not write_set:
            raise EnvelopeError("auto-if-clean requires a non-empty write_set")

        apply_policy = _enum_field(
            value,
            "apply_policy",
            APPLY_POLICIES,
            default="apply-if-clean" if mode == "auto-if-clean" else "preserve-patch",
        )
        evidence = _enum_field(value, "evidence", EVIDENCE_LEVELS, default="summary")
        verification = VerificationPolicy.from_mapping(value.get("verification"))
        timeout_seconds = _positive_int(value, "timeout_seconds", default=900)
        no_output_seconds = _positive_int(value, "no_output_seconds", default=180)
        if no_output_seconds > timeout_seconds:
            raise EnvelopeError("no_output_seconds must be less than or equal to timeout_seconds")

        provenance_required = value.get("provenance_required", True)
        if not isinstance(provenance_required, bool):
            raise EnvelopeError("provenance_required must be a boolean")

        return cls(
            schema=schema,
            role=role,
            mode=mode,
            task=task,
            model=model,
            review_lens=review_lens,
            write_set=write_set,
            apply_policy=apply_policy,
            evidence=evidence,
            verification=verification,
            timeout_seconds=timeout_seconds,
            no_output_seconds=no_output_seconds,
            provenance_required=provenance_required,
        )

    def to_jsonable(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["verification"] = asdict(self.verification)
        return payload


@dataclass(frozen=True)
class BundleResult:
    status: str
    run_id: str
    bundle_path: Path
    projection: str


@dataclass(frozen=True)
class SupervisedRunResult:
    status: str
    agy_launched: bool
    resolved_agy: str | None
    argv: list[str]
    process_id: int | None
    return_code: int | None
    started_at: datetime
    ended_at: datetime
    shutdown: str
    stdout_path: Path
    stderr_path: Path
    timeout_class: str | None
    stdout_bytes: int
    stderr_bytes: int
    error: str | None = None


@dataclass(frozen=True)
class TranscriptClassification:
    classification: str
    agy_command_seen: bool
    claude_file_tool_seen: bool
    evidence: list[str]

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self)


def parse_status(name: str) -> str:
    if name not in STATUSES:
        raise EnvelopeError(_enum_error("status", name, STATUSES))
    return name


def load_envelope(path: Path) -> Envelope:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EnvelopeError(f"envelope JSON is invalid: {exc}") from exc
    except OSError as exc:
        raise EnvelopeError(f"could not read envelope: {exc}") from exc
    if not isinstance(payload, dict):
        raise EnvelopeError("envelope must be a JSON object")
    return Envelope.from_mapping(payload)


def build_envelope_from_args(args: argparse.Namespace) -> Envelope:
    task = args.task
    if args.task_file is not None:
        try:
            task = args.task_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise EnvelopeError(f"could not read task file: {exc}") from exc

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "role": args.role,
        "mode": args.mode,
        "task": task,
        "model": args.model,
        "review_lens": args.review_lens,
        "write_set": args.write_set,
        "apply_policy": args.apply_policy,
        "evidence": args.evidence,
        "verification": {
            "commands": args.verification_command,
            "required": args.verification_required,
            "run_scope": args.verification_run_scope,
        },
        "timeout_seconds": args.timeout_seconds,
        "no_output_seconds": args.no_output_seconds,
        "provenance_required": args.provenance_required,
    }
    return Envelope.from_mapping(payload)


def create_validation_bundle(
    envelope: Envelope,
    *,
    repo_root: Path,
    run_id: str | None = None,
    source_envelope: Path | None = None,
    argv: list[str] | None = None,
    now: datetime | None = None,
) -> BundleResult:
    timestamp = now or datetime.now(UTC)
    resolved_run_id = run_id or _new_run_id(timestamp)
    _validate_run_id(resolved_run_id)
    bundle_path = repo_root / ".claude" / "agy" / "runs" / resolved_run_id

    try:
        bundle_path.mkdir(parents=True, exist_ok=False)
        envelope_payload = envelope.to_jsonable()
        prompt = render_prompt(envelope)
        command_payload = {
            "validation_only": True,
            "agy_launch_planned": False,
            "argv": _sanitize_argv(argv or []),
            "source_envelope": str(source_envelope) if source_envelope else None,
            "repo_root": str(repo_root),
        }
        lease_payload = {
            "run_id": resolved_run_id,
            "launch_state": "validation_only",
            "process_id": None,
            "started_at": timestamp.isoformat(),
            "ended_at": timestamp.isoformat(),
            "timeout_seconds": envelope.timeout_seconds,
            "no_output_seconds": envelope.no_output_seconds,
            "shutdown": "not_started",
        }
        result_payload = {
            "schema": "agy.result.v1",
            "status": parse_status("success"),
            "run_id": resolved_run_id,
            "bundle_path": str(bundle_path),
            "role": envelope.role,
            "mode": envelope.mode,
            "evidence": envelope.evidence,
            "validation_only": True,
            "agy_launched": False,
            "summary": "Envelope validated and evidence bundle skeleton created. agy was not launched.",
        }
        projection = render_projection(result_payload)

        _write_json(bundle_path / "envelope.json", envelope_payload)
        (bundle_path / "prompt.txt").write_text(prompt, encoding="utf-8")
        _write_json(bundle_path / "command.json", command_payload)
        _write_json(bundle_path / "run-lease.json", lease_payload)
        _write_json(bundle_path / "result.json", result_payload)
        (bundle_path / "projection.md").write_text(projection, encoding="utf-8")
    except OSError:
        projection = render_bundle_failed_projection(bundle_path)
        return BundleResult(
            status=parse_status("bundle_failed"),
            run_id=resolved_run_id,
            bundle_path=bundle_path,
            projection=projection,
        )

    return BundleResult(
        status=parse_status("success"),
        run_id=resolved_run_id,
        bundle_path=bundle_path,
        projection=projection,
    )


def create_supervised_bundle(
    envelope: Envelope,
    *,
    repo_root: Path,
    run_id: str | None = None,
    source_envelope: Path | None = None,
    wrapper_argv: list[str] | None = None,
    agy_bin: str | None = None,
    now: datetime | None = None,
) -> BundleResult:
    timestamp = now or datetime.now(UTC)
    resolved_run_id = run_id or _new_run_id(timestamp)
    _validate_run_id(resolved_run_id)
    bundle_path = repo_root / ".claude" / "agy" / "runs" / resolved_run_id

    try:
        bundle_path.mkdir(parents=True, exist_ok=False)
        envelope_payload = envelope.to_jsonable()
        prompt = render_prompt(envelope)
        prompt_path = bundle_path / "prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        _write_json(bundle_path / "envelope.json", envelope_payload)

        stdout_path = bundle_path / "stdout.log"
        stderr_path = bundle_path / "stderr.log"
        stdout_path.touch()
        stderr_path.touch()

        command_payload: dict[str, Any] = {
            "validation_only": False,
            "agy_launch_planned": True,
            "wrapper_argv": _sanitize_argv(wrapper_argv or []),
            "source_envelope": str(source_envelope) if source_envelope else None,
            "repo_root": str(repo_root),
            "working_directory": str(repo_root),
        }
        _write_json(bundle_path / "command.json", command_payload)

        run_result = run_agy_supervised(
            envelope,
            prompt=prompt,
            repo_root=repo_root,
            bundle_path=bundle_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            agy_bin=agy_bin,
        )

        command_payload.update(
            {
                "agy_argv": _sanitize_argv(run_result.argv, prompt_replacement="<prompt:prompt.txt>"),
                "resolved_agy": run_result.resolved_agy,
            }
        )
        _write_json(bundle_path / "command.json", command_payload)

        lease_payload = _run_lease_payload(
            run_id=resolved_run_id,
            envelope=envelope,
            run_result=run_result,
            repo_root=repo_root,
        )
        _write_json(bundle_path / "run-lease.json", lease_payload)

        result_payload = {
            "schema": "agy.result.v1",
            "status": parse_status(run_result.status),
            "run_id": resolved_run_id,
            "bundle_path": str(bundle_path),
            "role": envelope.role,
            "mode": envelope.mode,
            "evidence": envelope.evidence,
            "validation_only": False,
            "agy_launched": run_result.agy_launched,
            "resolved_agy": run_result.resolved_agy,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "summary": _supervised_summary(run_result),
        }
        if run_result.error is not None:
            result_payload["error"] = run_result.error

        projection = render_projection(result_payload)
        _write_json(bundle_path / "result.json", result_payload)
        (bundle_path / "projection.md").write_text(projection, encoding="utf-8")
    except OSError:
        projection = render_bundle_failed_projection(bundle_path)
        return BundleResult(
            status=parse_status("bundle_failed"),
            run_id=resolved_run_id,
            bundle_path=bundle_path,
            projection=projection,
        )

    return BundleResult(
        status=parse_status(run_result.status),
        run_id=resolved_run_id,
        bundle_path=bundle_path,
        projection=projection,
    )


def run_agy_supervised(
    envelope: Envelope,
    *,
    prompt: str,
    repo_root: Path,
    bundle_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    agy_bin: str | None = None,
) -> SupervisedRunResult:
    started_at = datetime.now(UTC)
    resolved_agy = agy_bin or shutil.which("agy")
    if resolved_agy is None:
        ended_at = datetime.now(UTC)
        return SupervisedRunResult(
            status=parse_status("error"),
            agy_launched=False,
            resolved_agy=None,
            argv=[],
            process_id=None,
            return_code=None,
            started_at=started_at,
            ended_at=ended_at,
            shutdown="not_started",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout_class=None,
            stdout_bytes=0,
            stderr_bytes=0,
            error="agy executable not found",
        )

    argv = _build_agy_argv(
        resolved_agy=resolved_agy,
        envelope=envelope,
        prompt=prompt,
        log_path=bundle_path / "agy.log",
    )
    stdout_bytes = 0
    stderr_bytes = 0
    timeout_class: str | None = None
    shutdown = "exited"
    process_id: int | None = None
    return_code: int | None = None

    with (
        stdout_path.open("ab") as stdout_log,
        stderr_path.open("ab") as stderr_log,
    ):
        try:
            process = subprocess.Popen(
                argv,
                cwd=repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
            )
        except OSError as exc:
            ended_at = datetime.now(UTC)
            stderr_log.write(f"failed to launch agy: {exc}\n".encode())
            return SupervisedRunResult(
                status=parse_status("error"),
                agy_launched=False,
                resolved_agy=resolved_agy,
                argv=argv,
                process_id=None,
                return_code=None,
                started_at=started_at,
                ended_at=ended_at,
                shutdown="not_started",
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                timeout_class=None,
                stdout_bytes=0,
                stderr_bytes=stderr_log.tell(),
                error=str(exc),
            )

        process_id = process.pid
        selector = selectors.DefaultSelector()
        if process.stdout is not None:
            selector.register(process.stdout, selectors.EVENT_READ, stdout_log)
        if process.stderr is not None:
            selector.register(process.stderr, selectors.EVENT_READ, stderr_log)

        start_monotonic = time.monotonic()
        last_output_monotonic = start_monotonic

        while process.poll() is None:
            events = selector.select(timeout=0.05)
            for key, _mask in events:
                data = os.read(key.fileobj.fileno(), 8192)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                key.data.write(data)
                key.data.flush()
                if key.data is stdout_log:
                    stdout_bytes += len(data)
                else:
                    stderr_bytes += len(data)
                last_output_monotonic = time.monotonic()

            now_monotonic = time.monotonic()
            if now_monotonic - start_monotonic >= envelope.timeout_seconds:
                timeout_class = "timeout"
                shutdown = _terminate_process(process)
                break
            if now_monotonic - last_output_monotonic >= envelope.no_output_seconds:
                timeout_class = "no_output"
                shutdown = _terminate_process(process)
                break

        while selector.get_map():
            events = selector.select(timeout=0.05)
            if not events:
                break
            for key, _mask in events:
                data = os.read(key.fileobj.fileno(), 8192)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                key.data.write(data)
                key.data.flush()
                if key.data is stdout_log:
                    stdout_bytes += len(data)
                else:
                    stderr_bytes += len(data)

        selector.close()
        return_code = process.poll()
        if return_code is None:
            try:
                return_code = process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                return_code = None

    ended_at = datetime.now(UTC)
    if shutdown == "shutdown_incomplete":
        status = parse_status("shutdown_incomplete")
    elif timeout_class == "timeout":
        status = parse_status("timeout")
    elif timeout_class == "no_output":
        status = parse_status("no_output")
    elif return_code == 0:
        status = parse_status("success")
    else:
        status = parse_status("error")

    return SupervisedRunResult(
        status=status,
        agy_launched=True,
        resolved_agy=resolved_agy,
        argv=argv,
        process_id=process_id,
        return_code=return_code,
        started_at=started_at,
        ended_at=ended_at,
        shutdown=shutdown,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_class=timeout_class,
        stdout_bytes=stdout_bytes,
        stderr_bytes=stderr_bytes,
    )


def classify_transcript(path: Path) -> TranscriptClassification:
    evidence: list[str] = []
    agy_command_seen = False
    claude_file_tool_seen = False

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            evidence.append(f"line {line_number}: invalid json")
            continue
        if not isinstance(event, dict):
            continue

        tool_name = _event_tool_name(event)
        command = _event_command(event)
        if command and _looks_like_agy_command(command):
            agy_command_seen = True
            evidence.append(f"line {line_number}: agy command via {tool_name or 'unknown'}")
        if tool_name in {"Edit", "MultiEdit", "NotebookEdit", "Write"}:
            claude_file_tool_seen = True
            evidence.append(f"line {line_number}: Claude file tool {tool_name}")

    classification = "real" if agy_command_seen and not claude_file_tool_seen else "fallback_suspected"
    return TranscriptClassification(
        classification=classification,
        agy_command_seen=agy_command_seen,
        claude_file_tool_seen=claude_file_tool_seen,
        evidence=evidence,
    )


def render_prompt(envelope: Envelope) -> str:
    lens = envelope.review_lens or "none"
    write_set = "\n".join(f"- {path}" for path in envelope.write_set) or "- none"
    commands = "\n".join(f"- {command}" for command in envelope.verification.commands) or "- none"
    return "\n".join(
        [
            "# agy delegation packet",
            "",
            f"Schema: {envelope.schema}",
            f"Role: {envelope.role}",
            f"Mode: {envelope.mode}",
            f"Model: {envelope.model}",
            f"Review lens: {lens}",
            "",
            "## Task",
            envelope.task,
            "",
            "## Write Set",
            write_set,
            "",
            "## Verification",
            f"Required: {str(envelope.verification.required).lower()}",
            f"Run scope: {envelope.verification.run_scope}",
            commands,
            "",
            "## Guardrails",
            "- Do not commit, push, rewrite history, or mutate paths outside the write set.",
            "- Use PLAN_GAP:, TEST_CONFLICT:, and PATH_MISSING: markers when blocked.",
        ]
    )


def render_projection(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# agy delegation projection",
            "",
            f"Status: {result['status']}",
            f"Run ID: {result['run_id']}",
            f"Bundle: {result['bundle_path']}",
            f"Role: {result['role']}",
            f"Mode: {result['mode']}",
            "",
            result["summary"],
            "",
        ]
    )


def render_bundle_failed_projection(bundle_path: Path) -> str:
    return "\n".join(
        [
            "# agy delegation projection",
            "",
            "Status: bundle_failed",
            f"Bundle: {bundle_path}",
            "",
            "The wrapper could not create or write the evidence bundle.",
            "",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate or run an agy delegation envelope.")
    parser.add_argument("--envelope", type=Path, help="Path to an agy.delegation.v1 JSON envelope")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", help="Run id to use for deterministic tests")
    parser.add_argument("--launch-agy", action="store_true", help="Run agy after validation")
    parser.add_argument("--validation-only", action="store_true", help="Validate without running agy")
    parser.add_argument("--dry-run", action="store_true", help="Alias for --validation-only")
    parser.add_argument("--agy-bin", help="agy executable path for tests or host-specific installs")
    parser.add_argument("--role", choices=sorted(ROLES), default="coder")
    parser.add_argument("--mode", choices=sorted(MODES))
    parser.add_argument("--task", help="Delegated task text")
    parser.add_argument("--task-file", type=Path, help="Path containing delegated task text")
    parser.add_argument("--model", default="flash")
    parser.add_argument("--review-lens", choices=sorted(REVIEW_LENSES))
    parser.add_argument("--write-set", action="append", default=[])
    parser.add_argument("--apply-policy", choices=sorted(APPLY_POLICIES))
    parser.add_argument("--evidence", choices=sorted(EVIDENCE_LEVELS), default="summary")
    parser.add_argument("--verification-command", action="append", default=[])
    parser.add_argument("--verification-required", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--verification-run-scope", choices=sorted(RUN_SCOPES), default="clone")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--no-output-seconds", type=int, default=180)
    parser.add_argument("--provenance-required", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.envelope is not None:
            envelope = load_envelope(args.envelope)
            source_envelope = args.envelope
        else:
            envelope = build_envelope_from_args(args)
            source_envelope = None

        wrapper_argv = list(sys.argv[1:] if argv is None else argv)
        validation_only = args.validation_only or args.dry_run or not args.launch_agy
        if validation_only:
            result = create_validation_bundle(
                envelope,
                repo_root=args.repo_root,
                run_id=args.run_id,
                source_envelope=source_envelope,
                argv=wrapper_argv,
            )
        else:
            result = create_supervised_bundle(
                envelope,
                repo_root=args.repo_root,
                run_id=args.run_id,
                source_envelope=source_envelope,
                wrapper_argv=wrapper_argv,
                agy_bin=args.agy_bin,
            )
    except EnvelopeError as exc:
        print(f"agy delegation envelope error: {exc}", file=sys.stderr)
        return 2

    print(result.projection, end="")
    return 0 if result.status == "success" else 1


def _default_mode(role: str) -> str:
    return "no-write" if role == "reviewer" else "patch-only"


def _enum_field(
    payload: dict[str, Any], name: str, allowed: frozenset[str], *, default: str | None = None
) -> str:
    value = payload.get(name)
    if value is None:
        value = default
    if not isinstance(value, str) or not value:
        raise EnvelopeError(f"{name} must be a non-empty string")
    if value not in allowed:
        raise EnvelopeError(_enum_error(name, value, allowed))
    return value


def _string_field(payload: dict[str, Any], name: str, *, default: str | None = None) -> str:
    value = payload.get(name, default)
    if not isinstance(value, str) or not value.strip():
        raise EnvelopeError(f"{name} must be a non-empty string")
    return value


def _positive_int(payload: dict[str, Any], name: str, *, default: int) -> int:
    value = payload.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise EnvelopeError(f"{name} must be a positive integer")
    return value


def _write_set(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise EnvelopeError("write_set must be a list of relative paths")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise EnvelopeError("write_set entries must be non-empty strings")
        path = Path(item)
        if path.is_absolute() or ".." in path.parts:
            raise EnvelopeError("write_set entries must be repo-relative paths without '..'")
        normalized.append(path.as_posix())
    return normalized


def _enum_error(name: str, value: object, allowed: frozenset[str]) -> str:
    return f"{name} has invalid value {value!r}; expected one of: {', '.join(sorted(allowed))}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sanitize_argv(argv: list[str], *, prompt_replacement: str | None = None) -> list[str]:
    sanitized: list[str] = []
    redact_next = False
    for token in argv:
        if prompt_replacement is not None and "\n" in token:
            sanitized.append(prompt_replacement)
            continue
        if redact_next:
            sanitized.append("<redacted>")
            redact_next = False
            continue
        lowered = token.lower()
        if lowered in {"--token", "--api-key", "--password"}:
            sanitized.append(token)
            redact_next = True
            continue
        if any(secret in lowered for secret in ("token=", "api_key=", "password=")):
            sanitized.append("<redacted>")
            continue
        sanitized.append(token)
    return sanitized


def _new_run_id(now: datetime) -> str:
    return f"{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:12]}"


def _validate_run_id(run_id: str) -> None:
    if not run_id or any(char in run_id for char in "/\\"):
        raise EnvelopeError("run_id must be a non-empty path segment")


def _build_agy_argv(
    *,
    resolved_agy: str,
    envelope: Envelope,
    prompt: str,
    log_path: Path,
) -> list[str]:
    return [
        resolved_agy,
        "--model",
        envelope.model,
        "--print-timeout",
        f"{envelope.timeout_seconds}s",
        "--log-file",
        str(log_path),
        "--print",
        prompt,
    ]


def _terminate_process(process: subprocess.Popen[bytes]) -> str:
    process.terminate()
    try:
        process.wait(timeout=1)
        return "terminated"
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=1)
            return "killed"
        except subprocess.TimeoutExpired:
            return "shutdown_incomplete"


def _run_lease_payload(
    *,
    run_id: str,
    envelope: Envelope,
    run_result: SupervisedRunResult,
    repo_root: Path,
) -> dict[str, Any]:
    elapsed_seconds = (run_result.ended_at - run_result.started_at).total_seconds()
    return {
        "run_id": run_id,
        "launch_state": "launched" if run_result.agy_launched else "not_started",
        "agy_launched": run_result.agy_launched,
        "resolved_agy": run_result.resolved_agy,
        "process_id": run_result.process_id,
        "return_code": run_result.return_code,
        "status": run_result.status,
        "started_at": run_result.started_at.isoformat(),
        "ended_at": run_result.ended_at.isoformat(),
        "elapsed_seconds": elapsed_seconds,
        "timeout_seconds": envelope.timeout_seconds,
        "no_output_seconds": envelope.no_output_seconds,
        "timeout_class": run_result.timeout_class,
        "shutdown": run_result.shutdown,
        "working_directory": str(repo_root),
        "stdout_path": str(run_result.stdout_path),
        "stderr_path": str(run_result.stderr_path),
        "stdout_bytes": run_result.stdout_bytes,
        "stderr_bytes": run_result.stderr_bytes,
        "real_agy_verdict": "real" if run_result.agy_launched and run_result.status == "success" else "unproven",
        "error": run_result.error,
    }


def _supervised_summary(run_result: SupervisedRunResult) -> str:
    if run_result.status == "success":
        return "agy completed successfully under supervised foreground execution."
    if run_result.status == "timeout":
        return "agy exceeded the total timeout and was shut down."
    if run_result.status == "no_output":
        return "agy produced no output before the no-output timeout and was shut down."
    if run_result.status == "shutdown_incomplete":
        return "agy did not shut down cleanly after timeout handling."
    if run_result.error:
        return f"agy launch failed: {run_result.error}"
    return "agy exited with a non-zero status."


def _event_tool_name(event: dict[str, Any]) -> str | None:
    for key in ("tool_name", "name"):
        value = event.get(key)
        if isinstance(value, str):
            return value

    message = event.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    name = item.get("name")
                    if isinstance(name, str):
                        return name
    return None


def _event_command(event: dict[str, Any]) -> str | None:
    for key in ("command", "cmd"):
        value = event.get(key)
        if isinstance(value, str):
            return value

    arguments = event.get("arguments") or event.get("input")
    if isinstance(arguments, dict):
        value = arguments.get("command")
        if isinstance(value, str):
            return value

    message = event.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "tool_use":
                    continue
                tool_input = item.get("input")
                if isinstance(tool_input, dict):
                    value = tool_input.get("command")
                    if isinstance(value, str):
                        return value
    return None


def _looks_like_agy_command(command: str) -> bool:
    command_lower = command.lower()
    return (
        "plugins/agy/scripts/agy_delegate.py" in command_lower
        or " --launch-agy" in command_lower
        or command_lower.startswith("agy ")
        or " agy " in command_lower
        or command_lower.endswith("/agy")
        or "/agy " in command_lower
    )


if __name__ == "__main__":
    raise SystemExit(main())
