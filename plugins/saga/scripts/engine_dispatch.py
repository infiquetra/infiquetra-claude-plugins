#!/usr/bin/env python3
"""Dispatch Saga external-engine resolutions as advisory evidence."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine_resolver import Resolution  # noqa: E402

FAILURE_STATUSES = frozenset({"timeout", "no-output", "error", "malformed", "clone-failed"})

Runner = Callable[[dict[str, Any]], dict[str, Any]]


class DispatchError(ValueError):
    """A dispatch adapter result violates the external-engine contract."""


@dataclass(frozen=True)
class AdvisoryEvidence:
    """Evidence returned by an external engine before Claude verification."""

    engine_id: str
    variant: str
    evidence: str
    provenance: dict[str, Any]
    verified_by_claude: bool = False
    halt: str | None = None


def build_codex_invocation(resolution: Resolution) -> dict[str, Any]:
    """Build a read-only codex-rescue invocation with a verbatim task payload."""
    invocation = {
        "via": "codex:codex-rescue",
        "task": resolution.payload,
        "sandbox": "read-only",
    }
    _assert_payload_preserved(invocation["task"], resolution.payload)
    return invocation


def build_agy_envelope(resolution: Resolution, *, model: Any) -> dict[str, Any]:
    """Build a no-write agy delegation envelope with a verbatim task payload."""
    envelope = {
        "schema": "agy.delegation.v1",
        "role": "coder",
        "mode": "no-write",
        "task": resolution.payload,
        "model": model,
        "write_set": [],
        "apply_policy": "preserve-patch",
        "evidence": "summary",
        "verification": {
            "commands": [],
            "required": False,
            "run_scope": "none",
        },
        "provenance_required": True,
    }
    _assert_payload_preserved(envelope["task"], resolution.payload)
    return envelope


def dispatch(
    resolution: Resolution,
    *,
    runner: Runner,
    model: Any | None = None,
) -> AdvisoryEvidence:
    """Run an external engine adapter and return advisory evidence only."""
    if resolution.halt is not None:
        return AdvisoryEvidence(
            engine_id=resolution.engine_id,
            variant=resolution.variant,
            evidence="",
            provenance={
                "engine": resolution.engine_id,
                "variant": resolution.variant,
                "status": "halted",
            },
            halt=resolution.halt,
        )

    invocation = _build_invocation(resolution, model=model)
    result = runner(invocation)
    status = _string_result(result.get("status"), default="malformed")
    output = _string_result(result.get("output"), default="")
    provenance = {
        "engine": resolution.engine_id,
        "variant": resolution.variant,
        "status": status,
    }

    if status == "ok":
        return AdvisoryEvidence(
            engine_id=resolution.engine_id,
            variant=resolution.variant,
            evidence=output,
            provenance=provenance,
        )

    if status not in FAILURE_STATUSES:
        raise DispatchError(f"runner returned unsupported status {status!r}")

    note = downgrade_note(resolution.engine_id, _failure_reason(status, output))
    provenance["note"] = note
    return AdvisoryEvidence(
        engine_id=resolution.engine_id,
        variant=resolution.variant,
        evidence="",
        provenance=provenance,
        halt=note,
    )


def satisfy_gate(evidence: AdvisoryEvidence) -> None:
    """Require Claude verification before advisory evidence can satisfy a gate."""
    if evidence.verified_by_claude is not True:
        raise DispatchError(
            "external advisory evidence must be verified by Claude before satisfying a gate"
        )


def downgrade_note(engine: str, reason: str) -> str:
    """Return the one-line provenance downgrade note used for wrapper failures."""
    safe_reason = " ".join(reason.split()) or "unspecified dispatch failure"
    return f"Downgraded external engine {engine}: {safe_reason}"


def _build_invocation(resolution: Resolution, *, model: Any | None) -> dict[str, Any]:
    if resolution.engine_id == "codex":
        return build_codex_invocation(resolution)
    if resolution.engine_id == "agy":
        return build_agy_envelope(resolution, model=model)
    raise DispatchError(f"unsupported external engine {resolution.engine_id!r}")


def _assert_payload_preserved(task: Any, payload: str) -> None:
    assert isinstance(task, str)
    assert task.encode("utf-8") == payload.encode("utf-8")


def _failure_reason(status: str, output: str) -> str:
    details = " ".join(output.split())
    if details:
        return f"{status}: {details}"
    return status


def _string_result(value: Any, *, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)
