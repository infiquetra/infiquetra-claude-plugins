#!/usr/bin/env python3
"""Dispatch Saga external-engine resolutions as advisory evidence."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import manifest_store  # noqa: E402
import provenance_manifest as pm  # noqa: E402
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


def build_dispatch_manifest(
    evidence: AdvisoryEvidence,
    *,
    execution_id: str,
    saga_ref: str,
    created_at: str,
    effort: str = "",
    protocol: str = "",
    claim_provenance: pm.ClaimProvenance | None = None,
) -> pm.Manifest:
    """Type today's ad-hoc ``provenance`` dict into a saga.manifest.v1 envelope (U3/R2/R18).

    Disposition mapping (AE6/F4): a halted or failed dispatch fell back to Claude, carrying
    the existing ``downgrade_note`` flow as ``disposition_note``; an ``ok`` dispatch ran as
    requested. Engine output claims enter the claimed layer only — adjudication is written
    later by the driving session (Claude) via :func:`adjudicate_manifest`, never by the
    engine (D5, #external-engines-never-gatekeepers).
    """
    if evidence.halt is not None:
        disposition = pm.Disposition.FELL_BACK_TO_CLAUDE
        note = evidence.provenance.get("note") or evidence.halt or ""
    else:
        disposition = pm.Disposition.RAN_AS_REQUESTED
        note = ""
    return pm.Manifest(
        execution_id=execution_id,
        saga_ref=saga_ref,
        attribution=pm.Attribution(
            kind=pm.ProducerKind.EXTERNAL_ENGINE,
            identity=f"{evidence.engine_id}/{evidence.variant}",
            effort=effort,
            protocol=protocol,
        ),
        disposition=disposition,
        disposition_note=str(note),
        created_at=created_at,
        claim_provenance=claim_provenance,
    )


def record_dispatch_manifest(
    store: manifest_store.Store,
    evidence: AdvisoryEvidence,
    *,
    execution_id: str,
    saga_ref: str,
    created_at: str,
    effort: str = "",
    protocol: str = "",
    claim_provenance: pm.ClaimProvenance | None = None,
) -> pm.Manifest:
    """Build and persist the typed manifest for one dispatch via ``manifest_store`` (KTD1)."""
    manifest = build_dispatch_manifest(
        evidence,
        execution_id=execution_id,
        saga_ref=saga_ref,
        created_at=created_at,
        effort=effort,
        protocol=protocol,
        claim_provenance=claim_provenance,
    )
    manifest_store.write_manifest(store, execution_id, manifest.to_dict())
    return manifest


def adjudicate_manifest(
    store: manifest_store.Store,
    execution_id: str,
    adjudications: dict[tuple[str, str], tuple[pm.AdjudicatedStatus, pm.Adjudication]],
) -> pm.Manifest:
    """Write Claude's adjudication layer onto a persisted claimed-only manifest (D5/R6).

    ``adjudications`` maps ``(claim text, source_ref)`` → (adjudicated status, attested
    adjudication record). The key includes ``source_ref`` so two claims sharing text but
    grounded in different sources can be adjudicated independently — text alone is not
    unique within a manifest. Called by the driving session only — never by an engine
    adapter. Claims not named keep their claimed-only state (mismatch_reason
    ``not-adjudicated`` when read by the gate).
    """
    raw = manifest_store.read_manifest(store, execution_id)
    if raw is None:
        raise DispatchError(f"no manifest to adjudicate for execution_id={execution_id!r}")
    manifest = pm.Manifest.from_dict(raw)
    if manifest.claim_provenance is None:
        raise DispatchError("manifest carries no claim_provenance to adjudicate")
    updated_claims = []
    for claim in manifest.claim_provenance.claims:
        key = (claim.text, claim.source_ref)
        if key in adjudications:
            status, record = adjudications[key]
            claim = pm.Claim(
                text=claim.text,
                claimed=claim.claimed,
                source_ref=claim.source_ref,
                source_revision=claim.source_revision,
                adjudicated=status,
                mismatch_reason=pm.mismatch_reason_for(claim.claimed, status),
                adjudication=record,
            )
        updated_claims.append(claim)
    adjudicated = pm.Manifest(
        execution_id=manifest.execution_id,
        saga_ref=manifest.saga_ref,
        attribution=manifest.attribution,
        disposition=manifest.disposition,
        disposition_note=manifest.disposition_note,
        created_at=manifest.created_at,
        output_completeness=manifest.output_completeness,
        claim_provenance=pm.ClaimProvenance(claims=tuple(updated_claims)),
    )
    manifest_store.write_manifest(store, execution_id, adjudicated.to_dict())
    return adjudicated


def satisfy_gate(evidence: AdvisoryEvidence, manifest: pm.Manifest | None = None) -> None:
    """Require Claude verification before advisory evidence can satisfy a gate.

    R11 extension (U3): when a typed manifest accompanies the evidence, a gated verdict
    additionally requires every gate-relevant claim to be Claude-adjudicated — a
    claimed-only manifest (any claim with no adjudicated status or no attested
    adjudication record) is refused. The manifest itself stays advisory evidence (R8/R20);
    only this existing gate consumes it.

    `manifest` is opt-in by signature, not by safety: this function cannot detect that a
    manifest with unresolved claim_provenance exists and simply wasn't threaded through.
    Any caller that has a manifest for this evidence MUST pass it here for the R11
    per-claim check to run at all -- silently omitting it degrades the guarantee to the
    evidence-level `verified_by_claude` bit alone.
    """
    if evidence.verified_by_claude is not True:
        raise DispatchError(
            "external advisory evidence must be verified by Claude before satisfying a gate"
        )
    if manifest is None or manifest.claim_provenance is None:
        return
    for claim in manifest.claim_provenance.claims:
        if claim.adjudicated is None or claim.adjudication is None:
            raise DispatchError(
                "gated verdict requires Claude-adjudicated claims (R11): "
                f"claim {claim.text!r} is producer-claimed only"
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
    # Explicit checks, not `assert` -- this is the R11 byte-preservation guarantee the
    # dispatch contract advertises to callers; it must still hold under `python -O`,
    # which strips `assert` statements.
    if not isinstance(task, str):
        raise DispatchError("dispatch task must be a str")
    if task.encode("utf-8") != payload.encode("utf-8"):
        raise DispatchError("dispatch task does not match the resolved payload byte-for-byte")


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
