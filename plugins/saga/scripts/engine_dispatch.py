#!/usr/bin/env python3
"""Dispatch Saga external-engine resolutions as advisory evidence."""

from __future__ import annotations

import contextlib
import hashlib
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chaperone_economics as ce  # noqa: E402
import fleet_commons_shim  # noqa: E402
import manifest_store  # noqa: E402
import provenance_manifest as pm  # noqa: E402
import run_ledger  # noqa: E402
from engine_resolver import Resolution  # noqa: E402

_bridge_receipt = fleet_commons_shim.load("bridge_receipt")
_delegation_audit = fleet_commons_shim.load("delegation_audit")
_delegation_state = fleet_commons_shim.load("delegation_state")

FAILURE_STATUSES = frozenset({"timeout", "no-output", "error", "malformed", "clone-failed"})
NON_GATING_ROLE_KINDS = frozenset({"advisory-reviewer", "panel"})

# A runner result carrying any of these keys is attempting to set/override a gate verdict --
# structurally rejected, not policy-rejected (R6, plan U6, binding decision
# `{#external-engines-never-gatekeepers}` #283). An external engine's output is advisory by
# construction; no runner may hand back a key that looks like a gate authority surface.
_GATEKEEPER_KEYS = frozenset({"verdict", "gate_status", "adjudicated"})

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
    role_kind: str = "worker"
    halt: str | None = None
    # The runner's ``bridge_receipt.v1`` proof-of-execution, threaded from ``result["receipt"]``
    # by :func:`dispatch` (plan U5, KTD8). Additive and defaulted (R11) -- receipt-less runners
    # (every CLI adapter today, and any failed dispatch) leave it ``None``. U6 consumes it to gate
    # ``RAN_AS_REQUESTED`` vs ``UNPROVEN``; this unit only lands and populates the field.
    runner_receipt: dict[str, Any] | None = None


@dataclass(frozen=True)
class RequeueDisposition:
    """The typed re-queue disposition a GATED two-signal divergence returns (#384 U5, KTD7).

    Returned by :func:`dispatch` exactly ONCE per consecutive-divergence streak: the first
    time the engine's self-report ("ok") and the observer signal (bundle launch flag +
    schema-valid receipt) disagree. Consumers re-dispatch at most once; a second consecutive
    divergence raises :class:`DispatchError` (HALT) instead of returning this. ``attempt``
    is the divergence counter carried into the manifest record; ``evidence`` is the disputed
    advisory evidence whose manifest names ``Disposition.DELEGATION_INTEGRITY``.
    """

    reason: str
    attempt: int
    evidence: AdvisoryEvidence
    disposition: str = "requeue"


# Consecutive gated-divergence attempt counter (KTD7 re-queue-once-then-HALT), keyed by
# session + engine. Reset on any corroborated acceptance; a surviving count of 1 means the
# NEXT divergence for the same key is the second consecutive one and must HALT.
_INTEGRITY_ATTEMPTS: dict[str, int] = {}

_TRIPWIRE_UNARMED = "tripwire_unarmed"
_INTEGRITY_REASON = (
    "delegation-integrity: engine self-report 'ok' but observer corroboration failed "
    "(bundle launch flag + schema-valid receipt required)"
)


def build_codex_invocation(resolution: Resolution, *, sandbox: Any = None) -> dict[str, Any]:
    """Build a read-only codex:delegate invocation with a verbatim task payload.

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
        "via": "codex:delegate",
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
    gated: bool = False,
    session_id: str = "",
    workspace_root: Path | str | None = None,
    expected_identity: str | None = None,
    chaperone: dict[str, Any] | None = None,
    economics: dict[str, Any] | None = None,
) -> AdvisoryEvidence | RequeueDisposition:
    """Run an external engine adapter and return advisory evidence only.

    ``sandbox`` (a Unit's declared containment) + ``write_set`` (its declared files) thread through
    to the envelope builders (#287 U5): a sandboxed-mutate agy unit lifts to patch-only; a
    sandboxed-mutate codex unit raises ``DispatchError`` (no write adapter). Default/read-only is
    byte-identical to before.

    ``ledger``/``subplot_id``/``at`` (#401) are **telemetry only** — when all are supplied a real
    advisory call records an ``engine`` run-fact (and a ``delegation`` fact for an ``agy.delegation.v1``
    call). This never gates and never changes the returned evidence (KTD5); omitting them is a no-op, so
    every existing caller is byte-identical.

    Two-signal acceptance (#384 U5, R4/R6, KTD6/KTD7) is opt-in through three new kwargs:

    - ``session_id`` — when supplied, the dispatch layer ARMS the delegation-liveness marker
      (``delegation_state.arm``) before running the adapter and disarms it in a ``finally``.
      An arming failure never blocks dispatch: it is recorded fail-open as a named
      ``tripwire_unarmed`` note on the evidence provenance (and the manifest).
    - ``workspace_root`` — the repo root under which the engine's bundle artifacts live;
      supplying it (or ``gated=True``) enables observer corroboration after the run:
      observer-yes = bundle ``launch_key`` true (``delegation_audit.corroborate``) AND a
      ``_receipt_problems()``-clean receipt. A missing launch flag is observer-NO
      (conservative).
    - ``gated`` — a self-report "ok" with observer-no becomes ``DELEGATION_INTEGRITY``:
      dispatch returns a typed :class:`RequeueDisposition` ONCE, and a second consecutive
      divergence for the same session+engine raises :class:`DispatchError` (HALT, KTD7).
      Advisory (``gated=False``) divergence keeps the existing ``downgrade_note`` mechanism
      with the integrity reason attached — no re-queue loop.

    Omitting all three keeps every existing caller byte-identical.

    ``expected_identity`` (#390 U2, KTD3) is the plan-time preview baseline in ``engine/variant``
    form. When supplied it is stamped verbatim onto the evidence provenance so
    :func:`build_dispatch_manifest` can derive ``Disposition.SUBSTITUTED_ENGINE`` when the engine
    that actually resolved/ran differs from the one the plan previewed. ``None`` (the default)
    stamps nothing and keeps every existing path byte-for-byte -- the resolver/registry seam
    (#388) is never touched.

    ``chaperone`` (#381) is advisory chaperone-economics provenance. When supplied, it is copied
    under ``provenance["chaperone"]`` for downstream review/work-session evidence. It does not
    change gate satisfaction or ``saga.manifest.v1``.
    """
    if resolution.halt is not None:
        provenance: dict[str, Any] = {
            "engine": resolution.engine_id,
            "variant": resolution.variant,
            "status": "halted",
        }
        _copy_resolution_warnings(provenance, resolution)
        if chaperone is not None:
            provenance["chaperone"] = dict(chaperone)
        return AdvisoryEvidence(
            engine_id=resolution.engine_id,
            variant=resolution.variant,
            evidence="",
            provenance=provenance,
            halt=resolution.halt,
        )

    economics_metadata = _offload_economics_metadata(chaperone, economics)
    economics_decision: ce.OffloadEconomicsDecision | None = None
    if economics_metadata is not None:
        economics_decision = _decide_offload_economics(
            resolution,
            economics_metadata,
            ledger=ledger,
        )
        if not economics_decision.proceed:
            provenance = {
                "engine": resolution.engine_id,
                "variant": resolution.variant,
                "status": "halted",
                "economics": economics_decision.to_provenance(),
            }
            _copy_resolution_warnings(provenance, resolution)
            if chaperone is not None:
                provenance["chaperone"] = dict(chaperone)
            return AdvisoryEvidence(
                engine_id=resolution.engine_id,
                variant=resolution.variant,
                evidence="",
                provenance=provenance,
                halt=economics_decision.status,
            )

    invocation = _build_invocation(resolution, model=model, sandbox=sandbox, write_set=write_set)

    # Arm the delegation-liveness marker BEFORE the adapter runs (KTD4: arming authority is
    # the dispatch layer) and disarm in a finally. Arming failure is fail-open but NAMED:
    # dispatch still runs, and the evidence/manifest carry a `tripwire_unarmed` note.
    armed_at: float | None = None
    tripwire_note = ""
    if session_id:
        try:
            entry = _delegation_state.arm(
                resolution.engine_id, session_id, "engine_dispatch", root=workspace_root
            )
            armed_at = float(entry.armed_at)
        except Exception as exc:  # noqa: BLE001 - fail-open, named (plan U5 error scenario)
            tripwire_note = f"{_TRIPWIRE_UNARMED}: {exc}"
    try:
        result = runner(invocation)
    finally:
        if armed_at is not None:
            # Disarm failure must never mask the adapter's result.
            with contextlib.suppress(Exception):
                _delegation_state.disarm(session_id, root=workspace_root)

    _reject_gatekeeper_keys(result)
    status = _string_result(result.get("status"), default="malformed")
    output = _string_result(result.get("output"), default="")
    provenance: dict[str, Any] = {
        "engine": resolution.engine_id,
        "variant": resolution.variant,
        "status": status,
    }
    _copy_resolution_warnings(provenance, resolution)
    # A runner may hand back a ``bridge_receipt.v1`` proving what actually ran (HTTP bridge does;
    # CLI adapters don't yet). Thread it through verbatim -- never fabricated here, and a secret
    # can never ride it because the bridge never puts one in (KTD8; see engine_bridge_http).
    receipt = result.get("receipt")
    runner_receipt = receipt if isinstance(receipt, dict) else None

    if tripwire_note:
        provenance["tripwire"] = tripwire_note

    # Stamp the plan-time preview baseline (#390 U2, KTD3) so the manifest builder can derive
    # SUBSTITUTED_ENGINE. Additive-defaulted: None stamps nothing (byte-for-byte preserved).
    if expected_identity is not None:
        provenance["expected_identity"] = expected_identity
    if chaperone is not None:
        provenance["chaperone"] = dict(chaperone)
    if economics_decision is not None:
        provenance["economics"] = economics_decision.to_provenance()

    if status == "ok":
        # Two-signal reconciliation (R4/R6): the engine SAYS ok; the observer signal is the
        # bundle launch flag plus a schema-valid receipt. Opt-in (gated or workspace_root) so
        # every existing single-signal advisory caller stays byte-identical.
        two_signal = gated or workspace_root is not None
        observer_yes = two_signal and _observer_corroborates(
            resolution.engine_id,
            runner_receipt,
            workspace_root=workspace_root,
            since_ts=armed_at,
        )
        integrity_key = f"{session_id or 'anon'}:{resolution.engine_id}"
        if two_signal and not observer_yes:
            provenance["integrity"] = pm.Disposition.DELEGATION_INTEGRITY.value
            if gated:
                # KTD7 re-queue-once-then-HALT: first divergence returns the typed re-queue
                # disposition; a second CONSECUTIVE divergence for the same key HALTs.
                attempt = _INTEGRITY_ATTEMPTS.get(integrity_key, 0) + 1
                if attempt >= 2:
                    _INTEGRITY_ATTEMPTS.pop(integrity_key, None)
                    raise DispatchError(
                        "HALT: second consecutive delegation-integrity divergence for "
                        f"{integrity_key!r} -- {_INTEGRITY_REASON} "
                        "(KTD7: re-queue once, then HALT -- never silent accept)"
                    )
                _INTEGRITY_ATTEMPTS[integrity_key] = attempt
                reason = f"{_INTEGRITY_REASON} (divergence attempt {attempt}; one re-queue allowed)"
                provenance["note"] = reason
                disputed = AdvisoryEvidence(
                    engine_id=resolution.engine_id,
                    variant=resolution.variant,
                    evidence="",
                    provenance=provenance,
                    halt=reason,
                    runner_receipt=runner_receipt,
                )
                _record_advisory_facts(
                    ledger, invocation, disputed, result, subplot_id=subplot_id, at=at
                )
                return RequeueDisposition(reason=reason, attempt=attempt, evidence=disputed)
            # Advisory (non-gated) divergence: the existing downgrade_note mechanism with the
            # integrity reason attached -- NO re-queue loop (plan U5 edge scenario).
            note = downgrade_note(resolution.engine_id, _INTEGRITY_REASON)
            provenance["note"] = note
            evidence = AdvisoryEvidence(
                engine_id=resolution.engine_id,
                variant=resolution.variant,
                evidence="",
                provenance=provenance,
                halt=note,
                runner_receipt=runner_receipt,
            )
            _record_advisory_facts(
                ledger, invocation, evidence, result, subplot_id=subplot_id, at=at
            )
            return evidence
        if gated:
            _INTEGRITY_ATTEMPTS.pop(integrity_key, None)
        if two_signal and observer_yes:
            provenance["observer_corroborated"] = True
        evidence = AdvisoryEvidence(
            engine_id=resolution.engine_id,
            variant=resolution.variant,
            evidence=output,
            provenance=provenance,
            runner_receipt=runner_receipt,
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
            runner_receipt=runner_receipt,
        )

    _record_advisory_facts(ledger, invocation, evidence, result, subplot_id=subplot_id, at=at)
    return evidence


def _offload_economics_metadata(
    chaperone: dict[str, Any] | None,
    economics: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if economics is not None:
        return dict(economics)
    if chaperone is None:
        return None
    raw = chaperone.get("economics")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise DispatchError("chaperone economics metadata must be a mapping")
    return dict(raw)


def _decide_offload_economics(
    resolution: Resolution,
    metadata: dict[str, Any],
    *,
    ledger: run_ledger.RunLedger | None,
) -> ce.OffloadEconomicsDecision:
    prior_spend = metadata.get("prior_provider_spend_usd")
    if prior_spend is None:
        prior_spend = _provider_spend_usd(ledger, resolution.engine_id)
    estimated_cost = metadata.get("estimated_external_cost_usd")
    if estimated_cost is None:
        estimated_cost = resolution.estimated_input_cost_usd
    cost_class = metadata.get("cost_class") or resolution.cost_class
    if cost_class is None:
        cost_class = "metered"
    try:
        return ce.decide_offload_economics(
            ce.OffloadEconomicsInput(
                engine_id=resolution.engine_id,
                cost_class=cost_class,
                estimated_external_cost_usd=estimated_cost,
                provider_budget_ceiling_usd=metadata.get(
                    "provider_budget_ceiling_usd", resolution.budget_ceiling_usd
                ),
                prior_provider_spend_usd=prior_spend,
                claude_inline_tokens_estimate=metadata.get("claude_inline_tokens_estimate"),
                chaperone_tokens_estimate=metadata.get("chaperone_tokens_estimate"),
                inline_fallback=str(metadata.get("inline_fallback", "inline")),
            )
        )
    except ce.ChaperonePolicyError as exc:
        raise DispatchError(f"invalid offload economics input: {exc}") from exc


def _provider_spend_usd(ledger: run_ledger.RunLedger | None, engine_id: str) -> float:
    if ledger is None:
        return 0.0
    total = 0.0
    for fact in run_ledger.read_facts(ledger):
        if fact.get("kind") != "engine" or fact.get("engine") != engine_id:
            continue
        cost = fact.get("cost")
        if isinstance(cost, bool) or not isinstance(cost, int | float):
            continue
        total += float(cost)
    return total


def _copy_resolution_warnings(provenance: dict[str, Any], resolution: Resolution) -> None:
    if resolution.warnings:
        provenance["warnings"] = list(resolution.warnings)


def _receipt_problems(runner_receipt: dict[str, Any] | None) -> list[str]:
    """Validate ``runner_receipt`` against ``bridge_receipt.v1``; a list of problems (empty =
    valid). Absent receipt is its own problem -- named explicitly rather than folded into a
    generic validation error, so the disposition note is legible (R8)."""
    if runner_receipt is None:
        return ["no receipt present on evidence"]
    if not isinstance(runner_receipt, dict):
        return [f"receipt must be a dict, got {type(runner_receipt).__name__}"]
    return list(_bridge_receipt.validate_receipt(runner_receipt))


def _observer_corroborates(
    engine_id: str,
    runner_receipt: dict[str, Any] | None,
    *,
    workspace_root: Path | str | None,
    since_ts: float | None,
) -> bool:
    """The independent observer signal (#384 U5): launch flag true + schema-valid receipt.

    Conservative by construction: a receipt-valid bundle whose ``launch_key`` is missing or
    false is observer-NO, an unknown/uncorroboratable engine is observer-NO, and any error
    reading the bundles is observer-NO. The observer never raises -- divergence handling
    (not this predicate) decides what a "no" costs.
    """
    if _receipt_problems(runner_receipt):
        return False
    try:
        corroboration = _delegation_audit.corroborate(engine_id, since_ts, root=workspace_root)
    except Exception:  # noqa: BLE001 - observer-no beats crashing the dispatch path
        return False
    return bool(corroboration.launched)


def _reject_gatekeeper_keys(result: dict[str, Any]) -> None:
    """Structurally refuse a runner result that attempts to carry gate/verdict authority (R6).

    Policy-level advisory-only behavior is not enough -- a runner shaped to slip a
    ``verdict``/``gate_status``/``adjudicated`` key past the dispatch boundary must be
    rejected by the contract itself, never merely ignored.
    """
    found = _GATEKEEPER_KEYS.intersection(result)
    if found:
        raise DispatchError(
            "external engines never gatekeepers "
            "(#283 {#external-engines-never-gatekeepers}): runner result carries "
            f"disallowed key(s) {sorted(found)!r}"
        )


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


def _substitution_note(evidence: AdvisoryEvidence) -> str | None:
    """The SUBSTITUTED_ENGINE note when the plan-time preview baseline
    (``provenance['expected_identity']``, #390 U2/KTD3) differs from the engine that actually
    resolved/ran; ``None`` when no baseline was stamped or it matches. The note names BOTH
    identities so a forced substitution is traceable prose, not a bare enum (R2/R3)."""
    expected = evidence.provenance.get("expected_identity")
    if not expected:
        return None
    resolved = f"{evidence.engine_id}/{evidence.variant}"
    if expected == resolved:
        return None
    return (
        f"substituted engine: plan previewed {expected!r} but {resolved!r} resolved/ran "
        "-- substituted evidence can never satisfy a gate as-approved (#390 KTD4/KTD5)"
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

    Disposition mapping (AE6/F4, U6/KTD8/R8): a halted or failed dispatch fell back to Claude,
    carrying the existing ``downgrade_note`` flow as ``disposition_note``; an ``ok`` dispatch
    is ``RAN_AS_REQUESTED`` only when ``evidence.runner_receipt`` is a schema-valid
    ``bridge_receipt.v1`` (validated via the fleet-commons ``bridge_receipt`` module) --
    receipt-less or invalid-receipt "ok" evidence resolves to ``UNPROVEN`` with a note naming
    what was missing, never a silent ``RAN_AS_REQUESTED`` and never the lie of
    ``FELL_BACK_TO_CLAUDE`` (nothing fell back). Engine output claims enter the claimed layer
    only — adjudication is written later by the driving session (Claude) via
    :func:`adjudicate_manifest`, never by the engine (D5, #external-engines-never-gatekeepers).
    """
    if evidence.provenance.get("integrity") == pm.Disposition.DELEGATION_INTEGRITY.value:
        # Two-signal divergence (#384 U5/KTD6): the engine said "ok" but the observer signal
        # disagreed. Named, never folded into FELL_BACK_TO_CLAUDE (nothing admitted failure)
        # or UNPROVEN (this is a contradiction, not merely missing proof).
        disposition = pm.Disposition.DELEGATION_INTEGRITY
        note = (
            evidence.provenance.get("note")
            or evidence.halt
            or "engine self-report diverged from observer corroboration"
        )
    elif evidence.halt is not None:
        disposition = pm.Disposition.FELL_BACK_TO_CLAUDE
        note = evidence.provenance.get("note") or evidence.halt or ""
    elif _substitution_note(evidence) is not None:
        # SUBSTITUTED_ENGINE (#390 U2, KTD4): the plan previewed one engine but a different one
        # resolved/ran. Ranks BELOW the halt branch (nothing-ran / admitted-failure outranks
        # wrong-thing-ran) but ABOVE the receipt check -- a valid receipt for the WRONG engine
        # must never yield RAN_AS_REQUESTED. The note names BOTH identities.
        disposition = pm.Disposition.SUBSTITUTED_ENGINE
        note = _substitution_note(evidence) or ""
    else:
        receipt_problems = _receipt_problems(evidence.runner_receipt)
        if receipt_problems:
            disposition = pm.Disposition.UNPROVEN
            note = "no schema-valid bridge_receipt.v1: " + "; ".join(receipt_problems)
        else:
            disposition = pm.Disposition.RAN_AS_REQUESTED
            note = ""
    # A failed arming attempt (fail-open, #384 U5) is NAMED on the manifest record so a
    # tripwire-unprotected run is distinguishable from a protected one.
    tripwire = evidence.provenance.get("tripwire")
    if tripwire:
        note = f"{note}; {tripwire}" if note else str(tripwire)
    # R3 invariant (#390 U2): every non-RAN_AS_REQUESTED manifest carries a non-empty,
    # human-readable disposition_note -- a forced fallback must be traceable prose, not a bare
    # enum. A degenerate empty reason (empty halt string, whitespace-only note) gets a fixed
    # fallback naming the disposition rather than an empty note.
    if disposition is not pm.Disposition.RAN_AS_REQUESTED and not str(note).strip():
        note = f"{disposition.value}: reason unspecified"
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

    Two-signal acceptance (#384 U5/R6): beside ``verified_by_claude``, a gated verdict
    additionally requires OBSERVER corroboration — the ``observer_corroborated`` provenance
    mark :func:`dispatch` stamps only when the bundle launch flag was true AND the receipt
    was ``_receipt_problems()``-clean. Claude's own say-so is one signal; the gate needs
    both. Divergent or uncorroborated "ok" evidence can therefore never satisfy a gate.

    Substitution refusal (#390 U2/KTD5): a manifest whose disposition is
    ``SUBSTITUTED_ENGINE`` is refused outright -- a run that executed a different engine than the
    plan approved can never satisfy a gate as-approved, regardless of how well-corroborated its
    (wrong-engine) evidence is.

    Advisory-reviewer refusal (#382): reviewer-role external evidence is report-only. Even when
    Claude verifies the evidence and the observer corroborates the run, it cannot satisfy a gate or
    move Team Execution consensus threshold math.
    """
    if evidence.role_kind in NON_GATING_ROLE_KINDS:
        raise DispatchError(
            f"{evidence.role_kind} evidence is advisory-only and can never satisfy a gate"
        )
    if evidence.verified_by_claude is not True:
        raise DispatchError(
            "external advisory evidence must be verified by Claude before satisfying a gate"
        )
    if evidence.provenance.get("observer_corroborated") is not True:
        raise DispatchError(
            "two-signal acceptance (#384 R6): a gated verdict requires observer corroboration "
            "(bundle launch flag true + schema-valid receipt) beside Claude verification -- "
            "this evidence carries no observer_corroborated mark"
        )
    if manifest is not None and manifest.disposition is pm.Disposition.SUBSTITUTED_ENGINE:
        raise DispatchError(
            "substituted evidence can never satisfy a gate as-approved (#390 U2/KTD5): the "
            f"manifest disposition is {manifest.disposition.value!r} -- "
            f"{manifest.disposition_note}"
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


def build_http_invocation(resolution: Resolution) -> dict[str, Any]:
    """Build a generic OpenAI-compatible HTTP invocation, driven purely by the registry row.

    Every provider difference (base URL, model id, bearer auth env var) is copied straight from the
    resolution's row ``invocation`` -- there is no per-provider branching. The task payload is carried
    byte-for-byte (same ``_assert_payload_preserved`` guarantee the CLI builders give, R11).

    SECRET LIFECYCLE: the ``auth`` mapping carries the env var *name* (``key_env``) only, never a
    resolved token -- this invocation dict flows into run-ledger telemetry
    (``_record_advisory_facts``), so a value here would leak. The bridge resolves the token from
    ``key_env`` at request-build time; see ``engine_bridge_http`` (KTD10, plan risk "secret leakage").
    """
    row = resolution.invocation or {}
    base_url = row.get("base_url")
    model = row.get("model")
    if not isinstance(base_url, str) or not base_url:
        raise DispatchError("http invocation missing base_url in registry row data")
    if not isinstance(model, str) or not model:
        raise DispatchError("http invocation missing model in registry row data")
    row_auth = row.get("auth") or {}
    # Name only -- never the key value (SECRET LIFECYCLE).
    auth = {"mode": row_auth.get("mode"), "key_env": row_auth.get("key_env")}
    invocation = {
        "via": "engine-bridge-http",
        "transport": "http",
        "engine_id": resolution.engine_id,
        "variant": resolution.variant,
        "base_url": base_url,
        "model": model,
        "effort": row.get("effort", resolution.effort),
        "auth": auth,
        "task": resolution.payload,
    }
    _assert_payload_preserved(invocation["task"], resolution.payload)
    return invocation


def _build_invocation(
    resolution: Resolution,
    *,
    model: Any | None,
    sandbox: Any = None,
    write_set: list[str] | None = None,
) -> dict[str, Any]:
    # Transport-keyed branch (KTD1): a row carrying http-transport invocation data dispatches
    # through the generic bridge; the cli arm keeps the existing codex/agy builders unchanged.
    row = resolution.invocation or {}
    if row.get("via") == "engine-bridge-http":
        return build_http_invocation(resolution)
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
