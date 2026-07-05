#!/usr/bin/env python3
"""Dispatch Saga external-engine resolutions as advisory evidence."""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import manifest_store  # noqa: E402
import provenance_manifest as pm  # noqa: E402
import run_ledger  # noqa: E402
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


def build_codex_invocation(resolution: Resolution, *, sandbox: Any = None) -> dict[str, Any]:
    """Build a read-only codex-rescue invocation with a verbatim task payload.

    codex has no write adapter (#287 KTD4): ``sandbox: "read-only"`` is its only supported posture.
    A sandboxed-mutate unit routed to codex HALTS visibly here rather than silently running
    read-only and dropping the requested write -- halt-not-downgrade (R4/R6).
    """
    if _sandbox_requests_writes(sandbox):
        raise DispatchError(
            "codex has no write adapter: a sandboxed-mutate unit cannot run on codex "
            "(#287 R6/KTD4 halt-not-downgrade) -- route write-mode work to agy, or drop the "
            "sandbox to run codex read-only"
        )
    invocation = {
        "via": "codex:codex-rescue",
        "task": resolution.payload,
        "sandbox": "read-only",
    }
    _assert_payload_preserved(invocation["task"], resolution.payload)
    return invocation


def build_agy_envelope(
    resolution: Resolution,
    *,
    model: Any,
    sandbox: Any = None,
    write_set: list[str] | None = None,
) -> dict[str, Any]:
    """Build an agy delegation envelope with a verbatim task payload.

    Default / read-only sandbox keeps the evidence-only ceiling (``mode: "no-write"``,
    ``write_set: []``) -- byte-identical to before. A sandboxed-mutate sandbox (read-write into an
    owned/isolated workspace) lifts the ceiling by WIRING agy's existing clone + gated patch import
    (#287 U5/R6): ``mode: "patch-only"``, ``write_set`` = the unit's declared files,
    ``apply_policy: "preserve-patch"``. No new isolation is built -- the remotes-stripped disposable
    clone agy already sets up is the workspace, and preserve-patch was already the apply policy.
    """
    if _sandbox_requests_writes(sandbox):
        mode = "patch-only"
        allowed_writes = list(write_set or [])
    else:
        mode = "no-write"
        allowed_writes = []
    envelope = {
        "schema": "agy.delegation.v1",
        "role": "coder",
        "mode": mode,
        "task": resolution.payload,
        "model": model,
        "write_set": allowed_writes,
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
    sandbox: Any = None,
    write_set: list[str] | None = None,
    ledger: run_ledger.RunLedger | None = None,
    subplot_id: str = "",
    at: str = "",
) -> AdvisoryEvidence:
    """Run an external engine adapter and return advisory evidence only.

    ``sandbox`` (a Unit's declared containment) + ``write_set`` (its declared files) thread through
    to the envelope builders (#287 U5): a sandboxed-mutate agy unit lifts to patch-only; a
    sandboxed-mutate codex unit raises ``DispatchError`` (no write adapter). Default/read-only is
    byte-identical to before.

    ``ledger``/``subplot_id``/``at`` (#401) are **telemetry only** — when all are supplied a real
    advisory call records an ``engine`` run-fact (and a ``delegation`` fact for an ``agy.delegation.v1``
    call). This never gates and never changes the returned evidence (KTD5); omitting them is a no-op, so
    every existing caller is byte-identical.
    """
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

    invocation = _build_invocation(resolution, model=model, sandbox=sandbox, write_set=write_set)
    result = runner(invocation)
    status = _string_result(result.get("status"), default="malformed")
    output = _string_result(result.get("output"), default="")
    provenance = {
        "engine": resolution.engine_id,
        "variant": resolution.variant,
        "status": status,
    }

    if status == "ok":
        evidence = AdvisoryEvidence(
            engine_id=resolution.engine_id,
            variant=resolution.variant,
            evidence=output,
            provenance=provenance,
        )
    elif status not in FAILURE_STATUSES:
        raise DispatchError(f"runner returned unsupported status {status!r}")
    else:
        note = downgrade_note(resolution.engine_id, _failure_reason(status, output))
        provenance["note"] = note
        evidence = AdvisoryEvidence(
            engine_id=resolution.engine_id,
            variant=resolution.variant,
            evidence="",
            provenance=provenance,
            halt=note,
        )

    _record_advisory_facts(ledger, invocation, evidence, result, subplot_id=subplot_id, at=at)
    return evidence


def _num(value: Any) -> float:
    """A numeric metric from a runner result, or ``0.0`` when absent/non-numeric (bool excluded)."""
    if isinstance(value, bool):
        return 0.0
    return float(value) if isinstance(value, (int, float)) else 0.0


def _evidence_pointer(evidence: AdvisoryEvidence) -> str:
    """A content-addressed **reference** to a delegation's evidence — a pointer, never inlined bytes."""
    body = evidence.evidence or ""
    if not body:
        return f"engine:{evidence.engine_id}:{evidence.provenance.get('status', '')}"
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def _record_advisory_facts(
    ledger: run_ledger.RunLedger | None,
    invocation: Any,
    evidence: AdvisoryEvidence,
    result: dict[str, Any],
    *,
    subplot_id: str,
    at: str,
) -> None:
    """Write run-fact telemetry for an advisory call. **Telemetry only (KTD5)** — never gates, and a
    no-op unless ``ledger`` + ``subplot_id`` + ``at`` are all supplied (so dispatch is byte-identical
    for every existing caller). U3 writes an ``engine`` fact on any real call; U4 adds a ``delegation``
    fact only when the invocation is an ``agy.delegation.v1`` envelope.
    """
    if ledger is None or not subplot_id or not at:
        return
    run_ledger.append_fact(
        ledger,
        run_ledger.build_fact(
            "engine",
            subplot_id=subplot_id,
            at=at,
            engine=evidence.engine_id,
            variant=evidence.variant,
            status=str(evidence.provenance.get("status", "")),
            cost=_num(result.get("cost")),
            latency_seconds=_num(result.get("latency_seconds")),
            tokens=_num(result.get("tokens")),
        ),
    )
    if isinstance(invocation, dict) and invocation.get("schema") == "agy.delegation.v1":
        run_ledger.append_fact(
            ledger,
            run_ledger.build_fact(
                "delegation",
                subplot_id=subplot_id,
                at=at,
                evidence=_evidence_pointer(evidence),
                engine=evidence.engine_id,
            ),
        )


def build_dispatch_manifest(
    evidence: AdvisoryEvidence,
    *,
    execution_id: str,
    saga_ref: str,
    created_at: str,
    effort: str = "",
    protocol: str = "",
    sandbox: str = "",
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
            sandbox=sandbox,
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
    sandbox: str = "",
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
        sandbox=sandbox,
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


def _build_invocation(
    resolution: Resolution,
    *,
    model: Any | None,
    sandbox: Any = None,
    write_set: list[str] | None = None,
) -> dict[str, Any]:
    if resolution.engine_id == "codex":
        return build_codex_invocation(resolution, sandbox=sandbox)
    if resolution.engine_id == "agy":
        return build_agy_envelope(resolution, model=model, sandbox=sandbox, write_set=write_set)
    raise DispatchError(f"unsupported external engine {resolution.engine_id!r}")


def _sandbox_requests_writes(sandbox: Any) -> bool:
    """True iff ``sandbox`` explicitly permits writes into an isolated workspace (sandboxed-mutate).

    The default (None) and read-only sandboxes keep the evidence-only ceiling; only an explicit
    restrictive read-write sandbox lifts it (#287 U5). Duck-typed so either spec house's Sandbox
    object works.
    """
    return (
        sandbox is not None
        and getattr(sandbox, "is_restrictive", False)
        and getattr(sandbox, "mutation_policy", None) == "read-write"
    )


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
