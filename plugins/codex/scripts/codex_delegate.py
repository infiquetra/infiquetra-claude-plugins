#!/usr/bin/env python3
"""Codex delegation wrapper.

First-party, guarded, synchronous codex delegation bridge mirroring the agy wrapper's shape
(``plugins/agy/scripts/agy_delegate.py``). This module currently ships the ``codex.delegation.v1``
schema, the ``Envelope`` contract with fail-loud validation, and the ``bridge_receipt.v1`` emitter
seam (U1). The supervised ``codex exec`` runner, evidence-bundle writer, and diff-scan machinery
land in follow-on units (U2/U3) — see
``docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md``.

Schema shape mirrors ``agy.delegation.v1`` minus members that do not apply to codex's v1 scope
(KTD1): codex has no ``verification`` policy and no ``apply_policy`` beyond ``preserve-patch``,
since write-capable dispatch importing a patch into the live tree is deferred (KTD5) — a ``task``
mode run always produces a patch in a disposable clone and never applies to the live tree.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_commons_shim  # noqa: E402

_bridge_receipt = fleet_commons_shim.load("bridge_receipt")

SCHEMA = "codex.delegation.v1"

ROLES = frozenset({"coder", "reviewer"})
# "read-only" mirrors agy's no-write posture (`codex -s read-only`); "task" is the write-capable
# mode, scoped to a disposable clone only (KTD5) — it never applies to the live tree in v1.
MODES = frozenset({"read-only", "task"})
REVIEW_LENSES = frozenset({"adversarial", "quality", "scope-gap", "security-ops"})
EVIDENCE_LEVELS = frozenset({"minimal", "summary", "full"})
# v1 has exactly one apply policy: a "task" run always preserves its patch in the evidence bundle
# and never applies to the live tree (KTD5). The field is kept for forward compatibility with a
# future write-capable dispatch mode rather than hardcoding the behavior inline.
APPLY_POLICIES = frozenset({"preserve-patch"})
STATUSES = frozenset(
    {
        "success",
        "patch_ready",
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
    """Raised when a delegation envelope violates the codex.delegation.v1 contract."""


def _default_mode(role: str) -> str:
    return "task" if role == "coder" else "read-only"


def _enum_error(field: str, value: Any, allowed: frozenset[str]) -> str:
    return f"{field} must be one of {sorted(allowed)}, got {value!r}"


def _enum_field(
    value: dict[str, Any], field: str, allowed: frozenset[str], *, default: str | None = None
) -> str:
    raw = value.get(field, default)
    if raw is None:
        raise EnvelopeError(f"{field} is required")
    if not isinstance(raw, str) or raw not in allowed:
        raise EnvelopeError(_enum_error(field, raw, allowed))
    return raw


def _string_field(value: dict[str, Any], field: str, *, default: str | None = None) -> str:
    raw = value.get(field, default)
    if raw is None:
        raise EnvelopeError(f"{field} is required")
    if not isinstance(raw, str) or not raw.strip():
        raise EnvelopeError(f"{field} must be a non-empty string")
    return raw


def _positive_int(value: dict[str, Any], field: str, *, default: int) -> int:
    raw = value.get(field, default)
    if not isinstance(raw, int) or isinstance(raw, bool) or raw <= 0:
        raise EnvelopeError(f"{field} must be a positive integer")
    return raw


def _write_set(raw: Any) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(
        isinstance(entry, str) and entry.strip() for entry in raw
    ):
        raise EnvelopeError("write_set must be a list of non-empty strings")
    return list(raw)


@dataclass(frozen=True)
class Envelope:
    schema: str
    role: str
    mode: str
    task: str
    model: str | None
    effort: str | None
    review_lens: str | None
    write_set: list[str]
    apply_policy: str
    evidence: str
    timeout_seconds: int
    no_output_seconds: int
    provenance_required: bool

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> Envelope:
        if not isinstance(value, dict):
            raise EnvelopeError("envelope must be a JSON object")

        schema = value.get("schema", SCHEMA)
        if schema != SCHEMA:
            raise EnvelopeError(f"schema must be {SCHEMA}")

        role = _enum_field(value, "role", ROLES)
        mode = _enum_field(value, "mode", MODES, default=_default_mode(role))
        task = _string_field(value, "task")

        model = value.get("model")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise EnvelopeError("model must be a non-empty string or null")

        effort = value.get("effort")
        if effort is not None and (not isinstance(effort, str) or not effort.strip()):
            raise EnvelopeError("effort must be a non-empty string or null")

        review_lens = value.get("review_lens")
        if review_lens is not None and (
            not isinstance(review_lens, str) or review_lens not in REVIEW_LENSES
        ):
            raise EnvelopeError(_enum_error("review_lens", review_lens, REVIEW_LENSES))
        if role == "reviewer" and review_lens is None:
            review_lens = "adversarial"

        write_set = _write_set(value.get("write_set", []))
        if mode == "task" and not write_set:
            raise EnvelopeError("task mode requires a non-empty write_set")
        if role == "reviewer" and write_set:
            raise EnvelopeError("reviewer role must not carry a write_set")

        apply_policy = _enum_field(value, "apply_policy", APPLY_POLICIES, default="preserve-patch")
        evidence = _enum_field(value, "evidence", EVIDENCE_LEVELS, default="summary")
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
            effort=effort,
            review_lens=review_lens,
            write_set=write_set,
            apply_policy=apply_policy,
            evidence=evidence,
            timeout_seconds=timeout_seconds,
            no_output_seconds=no_output_seconds,
            provenance_required=provenance_required,
        )

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
        "task": task,
        "model": args.model,
        "effort": args.effort,
        "review_lens": args.review_lens,
        "write_set": args.write_set,
        "apply_policy": args.apply_policy,
        "evidence": args.evidence,
        "timeout_seconds": args.timeout_seconds,
        "no_output_seconds": args.no_output_seconds,
        "provenance_required": args.provenance_required,
    }
    if args.mode is not None:
        payload["mode"] = args.mode
    return Envelope.from_mapping(payload)


@dataclass(frozen=True)
class SupervisedRunResult:
    """Terminal outcome of one supervised ``codex exec`` invocation.

    The full supervising loop (process launch, timeout/no-output watchdog, SIGTERM/SIGINT
    die-clean handling) lands in U2; this shape exists now so the receipt seam (U1/R8) has a
    stable, testable contract to build against.
    """

    status: str
    codex_launched: bool
    resolved_codex: str | None
    argv: list[str]
    process_id: int | None
    return_code: int | None
    started_at: datetime
    ended_at: datetime
    stdout_bytes: int
    stderr_bytes: int
    error: str | None = None


def _supervised_receipt(
    run_result: SupervisedRunResult, *, envelope: Envelope
) -> dict[str, Any] | None:
    """Build a ``bridge_receipt.v1`` for a run that actually launched ``codex``.

    Launch-failure paths (``codex`` missing, ``OSError`` on process start) set
    ``codex_launched=False`` and never reach here — there is nothing to prove was run, so no
    receipt is emitted (parity with agy's ``_supervised_receipt``,
    ``plugins/agy/scripts/agy_delegate.py:1390-1412``).
    """
    if not run_result.codex_launched:
        return None
    wall_time_s = (run_result.ended_at - run_result.started_at).total_seconds()
    return _bridge_receipt.emit_receipt(
        engine_id="codex",
        variant=envelope.model or "default",
        transport="cli",
        wall_time_s=wall_time_s,
        bytes_produced=run_result.stdout_bytes + run_result.stderr_bytes,
        runner={
            "pid": run_result.process_id,
            "argv": run_result.argv,
            "exit_code": run_result.return_code,
        },
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded codex delegation wrapper")
    parser.add_argument("--envelope", type=Path, default=None, help="Path to a JSON envelope")
    parser.add_argument("--role", choices=sorted(ROLES))
    parser.add_argument("--mode", choices=sorted(MODES), default=None)
    parser.add_argument("--task", default=None)
    parser.add_argument("--task-file", type=Path, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--effort", default=None)
    parser.add_argument("--review-lens", dest="review_lens", choices=sorted(REVIEW_LENSES))
    parser.add_argument("--write-set", dest="write_set", action="append", default=[])
    parser.add_argument(
        "--apply-policy", dest="apply_policy", choices=sorted(APPLY_POLICIES), default="preserve-patch"
    )
    parser.add_argument("--evidence", choices=sorted(EVIDENCE_LEVELS), default="summary")
    parser.add_argument("--timeout-seconds", dest="timeout_seconds", type=int, default=900)
    parser.add_argument("--no-output-seconds", dest="no_output_seconds", type=int, default=180)
    parser.add_argument(
        "--no-provenance-required",
        dest="provenance_required",
        action="store_false",
        default=True,
    )
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    try:
        if args.envelope is not None:
            envelope = load_envelope(args.envelope)
        else:
            if not args.role:
                raise EnvelopeError("--role is required when --envelope is not supplied")
            envelope = build_envelope_from_args(args)
    except EnvelopeError as exc:
        print(f"codex-delegate: envelope error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(envelope.to_jsonable(), indent=2))
    if args.validate_only:
        return 0

    print(
        "codex-delegate: supervised codex exec runner is not yet implemented "
        "(lands in U2/U3 of the codex first-party bridge plan)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
