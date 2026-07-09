#!/usr/bin/env python3
"""Antigravity delegation wrapper."""

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

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_commons_shim  # noqa: E402

_bridge_receipt = fleet_commons_shim.load("bridge_receipt")
_output_attestation = fleet_commons_shim.load("output_attestation")

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
            raise EnvelopeError(
                "verification.commands is required when verification.required is true"
            )

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
class CloneSetupResult:
    success: bool
    base_sha: str | None
    clone_path: Path
    removed_remotes: list[str]
    error: str | None = None


@dataclass(frozen=True)
class DiffEvidence:
    changed_paths: list[str]
    diff_patch_path: Path
    changed_paths_path: Path
    git_proof_path: Path


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
    repo_root = repo_root.resolve()
    timestamp = now or datetime.now(UTC)
    resolved_run_id = run_id or _new_run_id(timestamp)
    _validate_run_id(resolved_run_id)
    bundle_path = repo_root / ".claude" / "agy" / "runs" / resolved_run_id

    try:
        bundle_path.mkdir(parents=True, exist_ok=False)
        envelope_payload = envelope.to_jsonable()
        prompt = render_prompt(envelope, repo_root=repo_root)
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
    repo_root = repo_root.resolve()
    timestamp = now or datetime.now(UTC)
    resolved_run_id = run_id or _new_run_id(timestamp)
    _validate_run_id(resolved_run_id)
    bundle_path = repo_root / ".claude" / "agy" / "runs" / resolved_run_id

    try:
        bundle_path.mkdir(parents=True, exist_ok=False)
        clone_path = bundle_path / "worktree"
        envelope_payload = envelope.to_jsonable()
        prompt = render_prompt(envelope, repo_root=clone_path)
        prompt_path = bundle_path / "prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        _write_json(bundle_path / "envelope.json", envelope_payload)

        stdout_path = bundle_path / "stdout.log"
        stderr_path = bundle_path / "stderr.log"
        stdout_path.touch()
        stderr_path.touch()
        checks_path = bundle_path / "checks.json"
        git_proof_path = bundle_path / "git-proof.json"
        diff_patch_path = bundle_path / "diff.patch"
        live_preflight = _live_git_status(repo_root)

        command_payload: dict[str, Any] = {
            "validation_only": False,
            "agy_launch_planned": True,
            "wrapper_argv": _sanitize_argv(wrapper_argv or []),
            "source_envelope": str(source_envelope) if source_envelope else None,
            "repo_root": str(repo_root),
            "working_directory": str(clone_path),
        }
        _write_json(bundle_path / "command.json", command_payload)

        if envelope.mode == "auto-if-clean" and not live_preflight["clean"]:
            run_result = _not_started_run_result(
                status=parse_status("checks_failed"),
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                error="live repo is dirty before auto-if-clean launch",
            )
            _write_json(
                checks_path,
                {
                    "required": envelope.verification.required,
                    "commands": [],
                    "passed": False,
                    "skipped_reason": "live repo dirty before launch",
                },
            )
            _write_git_proof(
                git_proof_path,
                repo_root=repo_root,
                clone_result=None,
                live_preflight=live_preflight,
                changed_paths=[],
                diff_patch_path=diff_patch_path,
                checks_path=checks_path,
                post_apply=None,
            )
            result_payload = _result_payload(
                envelope=envelope,
                run_id=resolved_run_id,
                bundle_path=bundle_path,
                run_result=run_result,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                summary="auto-if-clean refused to launch because the live repository was dirty.",
                changed_paths=[],
                diff_patch_path=diff_patch_path,
                checks_path=checks_path,
                clone_path=clone_path,
            )
            projection = render_projection(result_payload)
            _write_json(
                bundle_path / "run-lease.json",
                _run_lease_payload(
                    run_id=resolved_run_id,
                    envelope=envelope,
                    run_result=run_result,
                    repo_root=clone_path,
                ),
            )
            _write_json(bundle_path / "result.json", result_payload)
            (bundle_path / "projection.md").write_text(projection, encoding="utf-8")
            return BundleResult(
                status=parse_status("checks_failed"),
                run_id=resolved_run_id,
                bundle_path=bundle_path,
                projection=projection,
            )

        clone_result = setup_disposable_clone(repo_root=repo_root, clone_path=clone_path)
        if not clone_result.success:
            run_result = _not_started_run_result(
                status=parse_status("error"),
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                error=clone_result.error or "disposable clone setup failed",
            )
            _write_json(
                checks_path,
                {
                    "required": envelope.verification.required,
                    "commands": [],
                    "passed": False,
                    "skipped_reason": "clone setup failed",
                },
            )
            _write_git_proof(
                git_proof_path,
                repo_root=repo_root,
                clone_result=clone_result,
                live_preflight=live_preflight,
                changed_paths=[],
                diff_patch_path=diff_patch_path,
                checks_path=checks_path,
                post_apply=None,
            )
            result_payload = _result_payload(
                envelope=envelope,
                run_id=resolved_run_id,
                bundle_path=bundle_path,
                run_result=run_result,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                summary=f"disposable clone setup failed: {run_result.error}",
                changed_paths=[],
                diff_patch_path=diff_patch_path,
                checks_path=checks_path,
                clone_path=clone_path,
            )
            projection = render_projection(result_payload)
            _write_json(
                bundle_path / "run-lease.json",
                _run_lease_payload(
                    run_id=resolved_run_id,
                    envelope=envelope,
                    run_result=run_result,
                    repo_root=clone_path,
                ),
            )
            _write_json(bundle_path / "result.json", result_payload)
            (bundle_path / "projection.md").write_text(projection, encoding="utf-8")
            return BundleResult(
                status=parse_status("error"),
                run_id=resolved_run_id,
                bundle_path=bundle_path,
                projection=projection,
            )

        run_result = run_agy_supervised(
            envelope,
            prompt=prompt,
            repo_root=clone_path,
            bundle_path=bundle_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            agy_bin=agy_bin,
        )
        blocked_status = _blocked_status_from_logs(stdout_path, stderr_path)
        if run_result.status == "success" and blocked_status is not None:
            run_result = _override_run_status(run_result, status=blocked_status)

        diff_evidence = derive_diff_evidence(
            clone_path=clone_path,
            base_sha=clone_result.base_sha or "HEAD",
            bundle_path=bundle_path,
        )
        checks_payload = {
            "required": envelope.verification.required,
            "commands": [],
            "passed": None,
        }
        post_apply: dict[str, Any] | None = None
        final_status = parse_status(run_result.status) if run_result.status != "success" else None

        if final_status is None:
            rogue_commits = _rogue_commits(
                clone_path=clone_path,
                base_sha=clone_result.base_sha or "HEAD",
            )
            out_of_scope = _policy_out_of_scope_paths(
                envelope=envelope,
                changed_paths=diff_evidence.changed_paths,
            )
            if rogue_commits:
                final_status = parse_status("checks_failed")
                checks_payload["skipped_reason"] = "delegate created commits"
                checks_payload["rogue_commits"] = rogue_commits
            elif out_of_scope:
                final_status = parse_status("out_of_scope_mutation")
                checks_payload["skipped_reason"] = "changed paths outside write_set"
                checks_payload["out_of_scope_paths"] = out_of_scope
            else:
                final_status = decide_non_apply_status(
                    envelope=envelope,
                    run_result=run_result,
                    changed_paths=diff_evidence.changed_paths,
                )

        if final_status is None:
            if envelope.apply_policy != "apply-if-clean":
                final_status = parse_status("patch_ready")
                checks_payload["skipped_reason"] = "apply_policy is preserve-patch"
            else:
                checks_payload = run_verification_commands(envelope, clone_path=clone_path)
                if not checks_payload["passed"]:
                    final_status = parse_status("checks_failed")
                else:
                    apply_payload = apply_patch_to_live_repo(
                        repo_root=repo_root,
                        patch_path=diff_evidence.diff_patch_path,
                        expected_write_set=envelope.write_set,
                    )
                    post_apply = apply_payload
                    final_status = (
                        parse_status("applied")
                        if apply_payload["applied"] and apply_payload["only_expected_changes"]
                        else parse_status("checks_failed")
                    )

        _write_json(checks_path, checks_payload)
        _write_git_proof(
            git_proof_path,
            repo_root=repo_root,
            clone_result=clone_result,
            live_preflight=live_preflight,
            changed_paths=diff_evidence.changed_paths,
            diff_patch_path=diff_evidence.diff_patch_path,
            checks_path=checks_path,
            post_apply=post_apply,
        )

        if final_status != run_result.status:
            run_result = _override_run_status(run_result, status=final_status)

        command_payload.update(
            {
                "agy_argv": _sanitize_argv(
                    run_result.argv, prompt_replacement="<prompt:prompt.txt>"
                ),
                "resolved_agy": run_result.resolved_agy,
                "base_sha": clone_result.base_sha,
                "clone_path": str(clone_path),
            }
        )
        _write_json(bundle_path / "command.json", command_payload)

        result_payload = _result_payload(
            envelope=envelope,
            run_id=resolved_run_id,
            bundle_path=bundle_path,
            run_result=run_result,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            summary=_supervised_summary(run_result),
            changed_paths=diff_evidence.changed_paths,
            diff_patch_path=diff_evidence.diff_patch_path,
            checks_path=checks_path,
            clone_path=clone_path,
        )

        lease_payload = _run_lease_payload(
            run_id=resolved_run_id,
            envelope=envelope,
            run_result=run_result,
            repo_root=clone_path,
        )
        # One status per bundle: the provenance_required coercion (R1/KTD1) lives in
        # result_payload, and the lease must not report the pre-coercion status beside it.
        lease_payload["status"] = result_payload["status"]
        _write_json(bundle_path / "run-lease.json", lease_payload)

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
        # Source status from result_payload, not run_result.status directly: the
        # provenance_required coercion in _result_payload (R1/KTD1) may have escalated
        # a passing run_result.status to "fallback_suspected", and the exit code (main()
        # at :1167) must reflect that escalation, not the pre-coercion status.
        status=parse_status(result_payload["status"]),
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
        workspace_dir=repo_root,
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


def setup_disposable_clone(*, repo_root: Path, clone_path: Path) -> CloneSetupResult:
    base_sha_result = _run_git(["rev-parse", "HEAD"], cwd=repo_root)
    if base_sha_result.returncode != 0:
        return CloneSetupResult(
            success=False,
            base_sha=None,
            clone_path=clone_path,
            removed_remotes=[],
            error=base_sha_result.stderr.strip() or "could not resolve live repo HEAD",
        )

    base_sha = base_sha_result.stdout.strip()
    clone_result = subprocess.run(
        ["git", "clone", "--no-hardlinks", str(repo_root), str(clone_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if clone_result.returncode != 0:
        return CloneSetupResult(
            success=False,
            base_sha=base_sha,
            clone_path=clone_path,
            removed_remotes=[],
            error=clone_result.stderr.strip() or clone_result.stdout.strip() or "git clone failed",
        )

    remotes_result = _run_git(["remote"], cwd=clone_path)
    removed_remotes = [line.strip() for line in remotes_result.stdout.splitlines() if line.strip()]
    for remote in removed_remotes:
        remove_result = _run_git(["remote", "remove", remote], cwd=clone_path)
        if remove_result.returncode != 0:
            return CloneSetupResult(
                success=False,
                base_sha=base_sha,
                clone_path=clone_path,
                removed_remotes=removed_remotes,
                error=remove_result.stderr.strip() or f"could not remove remote {remote}",
            )

    return CloneSetupResult(
        success=True,
        base_sha=base_sha,
        clone_path=clone_path,
        removed_remotes=removed_remotes,
    )


def derive_diff_evidence(*, clone_path: Path, base_sha: str, bundle_path: Path) -> DiffEvidence:
    untracked = _git_nul_lines(["ls-files", "--others", "--exclude-standard", "-z"], cwd=clone_path)
    if untracked:
        _run_git(["add", "--intent-to-add", "--", *untracked], cwd=clone_path)

    diff_patch_path = bundle_path / "diff.patch"
    diff_result = _run_git(["diff", "--binary", base_sha], cwd=clone_path)
    diff_patch_path.write_text(diff_result.stdout, encoding="utf-8")

    changed_paths = sorted(
        set(_git_nul_lines(["diff", "--name-only", "-z", base_sha], cwd=clone_path))
    )
    changed_paths_path = bundle_path / "changed-paths.json"
    _write_json(
        changed_paths_path,
        {
            "base_sha": base_sha,
            "changed_paths": changed_paths,
        },
    )
    return DiffEvidence(
        changed_paths=changed_paths,
        diff_patch_path=diff_patch_path,
        changed_paths_path=changed_paths_path,
        git_proof_path=bundle_path / "git-proof.json",
    )


def decide_non_apply_status(
    *,
    envelope: Envelope,
    run_result: SupervisedRunResult,
    changed_paths: list[str],
) -> str | None:
    if run_result.status != "success":
        return parse_status(run_result.status)
    if envelope.mode == "no-write":
        return parse_status("patch_ready") if changed_paths else parse_status("success")
    if envelope.mode == "patch-only":
        return parse_status("patch_ready") if changed_paths else parse_status("success")
    if not changed_paths:
        return parse_status("success")
    return None


def run_verification_commands(envelope: Envelope, *, clone_path: Path) -> dict[str, Any]:
    if not envelope.verification.required or not envelope.verification.commands:
        return {
            "required": envelope.verification.required,
            "commands": [],
            "passed": False,
            "skipped_reason": "auto-if-clean requires explicit required verification commands",
        }
    if envelope.verification.run_scope != "clone":
        return {
            "required": envelope.verification.required,
            "run_scope": envelope.verification.run_scope,
            "commands": [],
            "passed": False,
            "skipped_reason": "auto-if-clean verification must run in clone scope",
        }

    command_results: list[dict[str, Any]] = []
    passed = True
    for command in envelope.verification.commands:
        started_at = datetime.now(UTC)
        timed_out = False
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=clone_path,
                check=False,
                capture_output=True,
                text=True,
                timeout=envelope.timeout_seconds,
            )
            return_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            return_code = None
            stdout = _decode_timeout_output(exc.stdout)
            stderr = _decode_timeout_output(exc.stderr)
        ended_at = datetime.now(UTC)
        command_passed = return_code == 0 and not timed_out
        passed = passed and command_passed
        command_results.append(
            {
                "command": command,
                "cwd": str(clone_path),
                "shell": True,
                "timeout_seconds": envelope.timeout_seconds,
                "timed_out": timed_out,
                "return_code": return_code,
                "passed": command_passed,
                "started_at": started_at.isoformat(),
                "ended_at": ended_at.isoformat(),
                "stdout": stdout,
                "stderr": stderr,
            }
        )

    return {
        "required": envelope.verification.required,
        "run_scope": envelope.verification.run_scope,
        "passed": passed,
        "commands": command_results,
    }


def apply_patch_to_live_repo(
    *,
    repo_root: Path,
    patch_path: Path,
    expected_write_set: list[str],
) -> dict[str, Any]:
    apply_result = _run_git(["apply", str(patch_path)], cwd=repo_root)
    live_changed_paths = _live_changed_paths(repo_root)
    out_of_scope = _paths_outside_write_set(live_changed_paths, expected_write_set)
    return {
        "applied": apply_result.returncode == 0,
        "return_code": apply_result.returncode,
        "stdout": apply_result.stdout,
        "stderr": apply_result.stderr,
        "live_changed_paths": live_changed_paths,
        "out_of_scope_paths": out_of_scope,
        "only_expected_changes": apply_result.returncode == 0 and not out_of_scope,
    }


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

    classification = (
        "real" if agy_command_seen and not claude_file_tool_seen else "fallback_suspected"
    )
    return TranscriptClassification(
        classification=classification,
        agy_command_seen=agy_command_seen,
        claude_file_tool_seen=claude_file_tool_seen,
        evidence=evidence,
    )


def render_prompt(envelope: Envelope, *, repo_root: Path | None = None) -> str:
    lens = envelope.review_lens or "none"
    boundary = str(repo_root) if repo_root is not None else "the current repository root"
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
            "## Repository Boundary",
            f"Repository root: {boundary}",
            "Work in this repository root only. Do not use Antigravity's default scratch directory "
            "for repository files.",
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
    parser.add_argument(
        "--validation-only", action="store_true", help="Validate without running agy"
    )
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
    parser.add_argument(
        "--verification-required", action=argparse.BooleanOptionalAction, default=False
    )
    parser.add_argument("--verification-run-scope", choices=sorted(RUN_SCOPES), default="clone")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--no-output-seconds", type=int, default=180)
    parser.add_argument(
        "--provenance-required", action=argparse.BooleanOptionalAction, default=True
    )
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
    return _exit_code_for_status(result.status)


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


def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def _git_nul_lines(args: list[str], *, cwd: Path) -> list[str]:
    completed = _run_git(args, cwd=cwd)
    if completed.returncode != 0 or not completed.stdout:
        return []
    return [item for item in completed.stdout.split("\0") if item]


def _live_git_status(repo_root: Path) -> dict[str, Any]:
    status = _run_git(
        ["status", "--porcelain=v1", "-z", "--", ".", ":(exclude).claude"],
        cwd=repo_root,
    )
    entries = _parse_status_z(status.stdout) if status.returncode == 0 else []
    return {
        "clean": status.returncode == 0 and not entries,
        "return_code": status.returncode,
        "stdout": status.stdout,
        "stderr": status.stderr,
        "changed_paths": sorted({path for entry in entries for path in entry["paths"]}),
    }


def _live_changed_paths(repo_root: Path) -> list[str]:
    status = _run_git(
        ["status", "--porcelain=v1", "-z", "--", ".", ":(exclude).claude"],
        cwd=repo_root,
    )
    if status.returncode != 0:
        return []
    return sorted({path for entry in _parse_status_z(status.stdout) for path in entry["paths"]})


def _rogue_commits(*, clone_path: Path, base_sha: str) -> list[str]:
    completed = _run_git(["rev-list", f"{base_sha}..HEAD"], cwd=clone_path)
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _parse_status_z(output: str) -> list[dict[str, Any]]:
    if not output:
        return []

    entries: list[dict[str, Any]] = []
    parts = output.split("\0")
    index = 0
    while index < len(parts):
        item = parts[index]
        index += 1
        if not item:
            continue
        status = item[:2]
        path = item[3:]
        paths = [path]
        if status.startswith("R") or status.startswith("C"):
            if index < len(parts) and parts[index]:
                paths.append(parts[index])
            index += 1
        entries.append({"status": status, "paths": paths})
    return entries


def _paths_outside_write_set(changed_paths: list[str], write_set: list[str]) -> list[str]:
    return [path for path in changed_paths if not _path_in_write_set(path, write_set)]


def _policy_out_of_scope_paths(*, envelope: Envelope, changed_paths: list[str]) -> list[str]:
    if not changed_paths:
        return []
    if envelope.mode == "no-write":
        return changed_paths
    if not envelope.write_set:
        return []
    return _paths_outside_write_set(changed_paths, envelope.write_set)


def _path_in_write_set(path: str, write_set: list[str]) -> bool:
    normalized_path = Path(path).as_posix()
    for allowed in write_set:
        normalized_allowed = Path(allowed).as_posix().rstrip("/")
        if normalized_path == normalized_allowed:
            return True
        if normalized_path.startswith(f"{normalized_allowed}/"):
            return True
    return False


def _not_started_run_result(
    *,
    status: str,
    stdout_path: Path,
    stderr_path: Path,
    error: str,
) -> SupervisedRunResult:
    timestamp = datetime.now(UTC)
    return SupervisedRunResult(
        status=parse_status(status),
        agy_launched=False,
        resolved_agy=None,
        argv=[],
        process_id=None,
        return_code=None,
        started_at=timestamp,
        ended_at=timestamp,
        shutdown="not_started",
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_class=None,
        stdout_bytes=0,
        stderr_bytes=0,
        error=error,
    )


def _override_run_status(run_result: SupervisedRunResult, *, status: str) -> SupervisedRunResult:
    return SupervisedRunResult(
        status=parse_status(status),
        agy_launched=run_result.agy_launched,
        resolved_agy=run_result.resolved_agy,
        argv=run_result.argv,
        process_id=run_result.process_id,
        return_code=run_result.return_code,
        started_at=run_result.started_at,
        ended_at=run_result.ended_at,
        shutdown=run_result.shutdown,
        stdout_path=run_result.stdout_path,
        stderr_path=run_result.stderr_path,
        timeout_class=run_result.timeout_class,
        stdout_bytes=run_result.stdout_bytes,
        stderr_bytes=run_result.stderr_bytes,
        error=run_result.error,
    )


def _blocked_status_from_logs(stdout_path: Path, stderr_path: Path) -> str | None:
    text = stdout_path.read_text(encoding="utf-8") + "\n" + stderr_path.read_text(encoding="utf-8")
    markers = {
        "PLAN_GAP:": "plan_gap",
        "TEST_CONFLICT:": "test_conflict",
        "PATH_MISSING:": "path_missing",
        "FALLBACK_SUSPECTED:": "fallback_suspected",
    }
    for marker, status in markers.items():
        if marker in text:
            return parse_status(status)
    return None


def _decode_timeout_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def _supervised_receipt(
    run_result: SupervisedRunResult,
    *,
    envelope: Envelope,
    run_id: str,
    external_tokens: int,
    output_attestation: dict[str, Any],
) -> dict[str, Any] | None:
    """Build a ``bridge_receipt.v1`` for a run that actually launched ``agy``.

    Launch-failure paths (``agy`` missing, ``OSError`` on ``Popen``) set
    ``agy_launched=False`` and never reach here — there is nothing to prove was run, so no
    receipt is emitted and the result envelope validates without one (KTD6/KTD7).
    """
    if not run_result.agy_launched:
        return None
    wall_time_s = (run_result.ended_at - run_result.started_at).total_seconds()
    return _bridge_receipt.emit_receipt(
        engine_id="agy",
        variant=envelope.model,
        transport="cli",
        wall_time_s=wall_time_s,
        bytes_produced=run_result.stdout_bytes + run_result.stderr_bytes,
        runner={
            "pid": run_result.process_id,
            "argv": run_result.argv,
            "exit_code": run_result.return_code,
        },
        receipt_emitter="agy-delegate",
        run_id=run_id,
        external_tokens=external_tokens,
        output_attestation=output_attestation,
    )


def _agy_external_tokens(run_result: SupervisedRunResult) -> int:
    return max(run_result.stdout_bytes + run_result.stderr_bytes, 0)


_PASSING_STATUSES = frozenset({"success", "patch_ready", "applied"})


def _exit_code_for_status(status: str) -> int:
    """The one status-to-process-exit mapping (single source: ``_PASSING_STATUSES``)."""
    return 0 if status in _PASSING_STATUSES else 1


def _result_payload(
    *,
    envelope: Envelope,
    run_id: str,
    bundle_path: Path,
    run_result: SupervisedRunResult,
    stdout_path: Path,
    stderr_path: Path,
    summary: str,
    changed_paths: list[str],
    diff_patch_path: Path,
    checks_path: Path,
    clone_path: Path,
) -> dict[str, Any]:
    status = parse_status(run_result.status)
    coerced_by: str | None = None
    if (
        envelope.provenance_required
        and status in _PASSING_STATUSES
        and _real_agy_verdict(run_result) == "unproven"
    ):
        # R1/KTD1: a caller that demanded provenance must not get exit 0 on a run the
        # wrapper itself cannot prove actually launched agy. classify_transcript is
        # deliberately not consulted here — transcript auditing is the Stop-hook's job
        # (#384); _real_agy_verdict is the wrapper's only in-run provenance signal.
        status = parse_status("fallback_suspected")
        coerced_by = "provenance_required"
    payload: dict[str, Any] = {
        "schema": "agy.result.v1",
        "status": status,
        "run_id": run_id,
        "bundle_path": str(bundle_path),
        "role": envelope.role,
        "mode": envelope.mode,
        "evidence": envelope.evidence,
        "validation_only": False,
        "agy_launched": run_result.agy_launched,
        "resolved_agy": run_result.resolved_agy,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "clone_path": str(clone_path),
        "changed_paths": changed_paths,
        "diff_patch": str(diff_patch_path),
        "checks_path": str(checks_path),
        "summary": summary,
    }
    receipt = _supervised_receipt(
        run_result,
        envelope=envelope,
        run_id=run_id,
        external_tokens=_agy_external_tokens(run_result),
        output_attestation=_output_attestation.emit_attestation(
            artifact="summary",
            content=summary,
        ),
    )
    if receipt is not None:
        payload["receipt"] = receipt
    if run_result.error is not None:
        payload["error"] = run_result.error
    if coerced_by is not None:
        payload["coerced_by"] = coerced_by
    return payload


def _write_git_proof(
    path: Path,
    *,
    repo_root: Path,
    clone_result: CloneSetupResult | None,
    live_preflight: dict[str, Any],
    changed_paths: list[str],
    diff_patch_path: Path,
    checks_path: Path,
    post_apply: dict[str, Any] | None,
) -> None:
    clone_state = _clone_git_state(clone_result)
    _write_json(
        path,
        {
            "schema": "agy.git-proof.v1",
            "repo_root": str(repo_root),
            "base_sha": clone_result.base_sha if clone_result else None,
            "clone_path": str(clone_result.clone_path) if clone_result else None,
            "clone_created": bool(clone_result and clone_result.success),
            "removed_remotes": clone_result.removed_remotes if clone_result else [],
            "clone_error": clone_result.error if clone_result else None,
            "live_preflight": live_preflight,
            "clone_head": clone_state["head"],
            "clone_post_status": clone_state["status"],
            "clone_remotes_after": clone_state["remotes_after"],
            "rogue_commits": clone_state["rogue_commits"],
            "changed_paths": changed_paths,
            "diff_patch": str(diff_patch_path),
            "checks_path": str(checks_path),
            "post_apply": post_apply,
        },
    )


def _clone_git_state(clone_result: CloneSetupResult | None) -> dict[str, Any]:
    empty = {
        "head": None,
        "status": {"return_code": None, "entries": []},
        "remotes_after": [],
        "rogue_commits": [],
    }
    if clone_result is None or not clone_result.success:
        return empty

    head = _run_git(["rev-parse", "HEAD"], cwd=clone_result.clone_path)
    status = _run_git(["status", "--porcelain=v1", "-z"], cwd=clone_result.clone_path)
    remotes = _run_git(["remote", "-v"], cwd=clone_result.clone_path)
    return {
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "status": {
            "return_code": status.returncode,
            "entries": _parse_status_z(status.stdout) if status.returncode == 0 else [],
            "stderr": status.stderr,
        },
        "remotes_after": [line.strip() for line in remotes.stdout.splitlines() if line.strip()]
        if remotes.returncode == 0
        else [],
        "rogue_commits": _rogue_commits(
            clone_path=clone_result.clone_path,
            base_sha=clone_result.base_sha or "HEAD",
        ),
    }


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
    workspace_dir: Path,
    prompt: str,
    log_path: Path,
) -> list[str]:
    argv = [
        resolved_agy,
        "--model",
        envelope.model,
        "--print-timeout",
        f"{envelope.timeout_seconds}s",
        "--log-file",
        str(log_path),
        "--add-dir",
        str(workspace_dir),
    ]
    if envelope.mode == "no-write":
        argv.append("--sandbox")
    else:
        argv.append("--dangerously-skip-permissions")
    return [*argv, "--print", prompt]


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
        "real_agy_verdict": _real_agy_verdict(run_result),
        "error": run_result.error,
    }


def _real_agy_verdict(run_result: SupervisedRunResult) -> str:
    if (
        run_result.agy_launched
        and run_result.return_code == 0
        and run_result.timeout_class is None
        and run_result.shutdown == "exited"
    ):
        return "real"
    return "unproven"


def _supervised_summary(run_result: SupervisedRunResult) -> str:
    if run_result.status == "success":
        return "agy completed successfully under supervised foreground execution."
    if run_result.status == "patch_ready":
        return "agy completed successfully and the patch was preserved without live-tree apply."
    if run_result.status == "applied":
        return "agy completed successfully and the verified patch was applied to the live tree."
    if run_result.status == "out_of_scope_mutation":
        return "agy completed, but changed paths outside the allowed write set."
    if run_result.status == "checks_failed":
        return "agy completed, but the apply-policy checks failed."
    if run_result.status in {"plan_gap", "test_conflict", "path_missing", "fallback_suspected"}:
        return f"agy reported {run_result.status}; no patch was applied."
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
