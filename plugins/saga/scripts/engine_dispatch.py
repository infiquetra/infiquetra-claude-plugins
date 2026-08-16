#!/usr/bin/env python3
"""Dispatch Saga external-engine resolutions as advisory evidence."""

from __future__ import annotations

import contextlib
import hashlib
import json
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Literal, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bridge_signatures  # noqa: E402
import chaperone_economics as ce  # noqa: E402
import engine_resolver  # noqa: E402
import fleet_commons_shim  # noqa: E402
import manifest_store  # noqa: E402
import provenance_manifest as pm  # noqa: E402
import reconcile  # noqa: E402
import run_ledger  # noqa: E402
from engine_resolver import Resolution, RunMemo  # noqa: E402
from execution_spec import AdvisoryPanelRequest  # noqa: E402

_bridge_receipt = fleet_commons_shim.load("bridge_receipt")

# The delegation/audit fleet-core modules are loaded LAZILY (#520 F5): they were added in
# fleet-core 0.8.0, so an eager module-level `shim.load()` made every `engine_dispatch` import
# crash under version skew (saga >= 0.74.0 against an older installed fleet-core) — where the
# hooks guard the identical loads and fail open. Callers go through `_load_fleet_module`, which
# degrades NAMED (`delegation-audit-unavailable`, the tripwire_unarmed pattern) instead of
# raising at import time. `bridge_receipt` stays eager: it long predates the skew window, and
# this module's hard imports (bridge_signatures -> output_attestation) already require that era.
_LAZY_FLEET_MODULES = frozenset({"delegation_audit", "delegation_state", "audit_store"})

_DELEGATION_AUDIT_UNAVAILABLE = "delegation-audit-unavailable"

# The broker-free close-receipt chain (#677/U3): dispatch mints one self-authenticating receipt per
# registered dispatch; the claim and adjudication manifest transitions chain from it. Each receipt
# binds its output + write-intent digests and its predecessor's receipt digest — the chain proves
# itself by hash; no broker fence backs it (the fencing loss is accepted, Scope Decision row 1).
CLOSE_RECEIPT_SCHEMA = "saga.close-receipt.v1"


def _load_fleet_module(name: str) -> tuple[ModuleType | None, str]:
    """Load a fleet-core module lazily; ``(None, named-degradation-reason)`` when unavailable.

    Never caches failures: the shim itself caches successes keyed by resolved root, and a
    re-pointed ``FLEET_COMMONS_ROOT`` (as tests do) must be able to recover.
    """
    try:
        return fleet_commons_shim.load(name), ""
    except Exception as exc:  # noqa: BLE001 - version skew degrades named, never crashes
        return None, f"{_DELEGATION_AUDIT_UNAVAILABLE}: {name}: {exc}"


def _require_close_receipt_digest(fields: Mapping[str, Any]) -> str:
    """Re-derive a close receipt's self-authenticating digest over every field but itself."""
    content = {key: value for key, value in fields.items() if key != "receipt_sha256"}
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def __getattr__(name: str) -> ModuleType:
    """Back-compat module attributes (``_delegation_audit`` etc.) resolve lazily (PEP 562)."""
    if name.startswith("_") and name[1:] in _LAZY_FLEET_MODULES:
        return fleet_commons_shim.load(name[1:])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


FAILURE_STATUSES = frozenset({"timeout", "no-output", "error", "malformed", "clone-failed"})
PENDING_STATUS = "pending"
PENDING_NOTE = "external launch has not resolved; no result yet"
NON_GATING_ROLE_KINDS = frozenset({"advisory-reviewer", "panel"})

# Untrusted panel output is fail-closed at the dispatch boundary. Limits are UTF-8 bytes, not
# characters, and are checked without truncation before output can reach gather/foreman logic.
PANEL_MEMBER_OUTPUT_BYTES_CAP = 64 * 1024
PANEL_TOTAL_OUTPUT_BYTES_CAP = 256 * 1024

# A runner result carrying any of these keys is attempting to set/override a gate verdict --
# structurally rejected, not policy-rejected (R6, plan U6, binding decision
# `{#external-engines-never-gatekeepers}` #283). An external engine's output is advisory by
# construction; no runner may hand back a key that looks like a gate authority surface.
_GATEKEEPER_KEYS = frozenset({"verdict", "gate_status", "adjudicated"})

Runner = Callable[[dict[str, Any]], dict[str, Any]]
PanelForeman = Callable[[tuple[reconcile.PanelMemberEvidence, ...]], reconcile.ReconciliationResult]


class DispatchError(ValueError):
    """A dispatch adapter result violates the external-engine contract."""


def _mint_close_receipt(
    *,
    resource_ref: Mapping[str, str],
    producer: str,
    run_id: str,
    expected_output_sha256: str,
    protected_write_intent_sha256: str,
    predecessor_receipt_sha256: str = "",
) -> dict[str, Any]:
    """Mint one self-authenticating close receipt for the broker-free chain (#677/U3).

    The receipt binds the exact output + write-intent digests and its predecessor's receipt digest;
    ``receipt_sha256`` closes over every other field, so any tampering or staleness is detectable by
    re-derivation alone — no broker resource head to consult.
    """
    receipt: dict[str, Any] = {
        "schema": CLOSE_RECEIPT_SCHEMA,
        "resource_ref": dict(resource_ref),
        "producer": producer,
        "run_id": run_id,
        "phase": "closed",
        "terminal": True,
        "expected_output_sha256": expected_output_sha256,
        "protected_write_intent_sha256": protected_write_intent_sha256,
        "predecessor_receipt_sha256": predecessor_receipt_sha256,
    }
    receipt["receipt_sha256"] = _require_close_receipt_digest(receipt)
    return receipt


def _validate_predecessor_close(
    close: Mapping[str, Any] | None,
    *,
    resource_ref: Mapping[str, str],
    expected_producer: str,
    run_id: str,
    binding: str,
) -> str:
    """Structurally validate one predecessor close receipt; return its receipt digest.

    Every check is content-only (the broker's fence-head consultation is retired with it, #677/U3):
    schema, resource binding, producer/run-id identity, terminal phase, 64-hex digest fields, and the
    self-authenticating receipt digest. Returns ``receipt_sha256`` for the successor to chain from.
    """
    if not isinstance(close, Mapping):
        raise DispatchError(f"{binding} must be a close-receipt mapping")
    if close.get("schema") != CLOSE_RECEIPT_SCHEMA:
        raise DispatchError(f"{binding} is not a {CLOSE_RECEIPT_SCHEMA} receipt")
    if close.get("resource_ref") != dict(resource_ref):
        raise DispatchError(f"{binding} does not bind this execution resource")
    if close.get("producer") != expected_producer:
        raise DispatchError(f"{binding} requires an exact {expected_producer} predecessor close")
    if close.get("run_id") != run_id:
        raise DispatchError(f"{binding} does not bind this execution run")
    if close.get("phase") != "closed" or close.get("terminal") is not True:
        raise DispatchError(f"{binding} must be a closed terminal receipt")
    for field in (
        "expected_output_sha256",
        "protected_write_intent_sha256",
        "receipt_sha256",
    ):
        value = close.get(field)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise DispatchError(f"{binding} carries an invalid {field}")
    predecessor = close.get("predecessor_receipt_sha256")
    if not isinstance(predecessor, str) or (
        predecessor
        and (len(predecessor) != 64 or any(char not in "0123456789abcdef" for char in predecessor))
    ):
        raise DispatchError(f"{binding} carries an invalid predecessor_receipt_sha256")
    if _require_close_receipt_digest(close) != close["receipt_sha256"]:
        raise DispatchError(
            f"{binding} digest does not match its content — tampered or stale receipt"
        )
    return str(close["receipt_sha256"])


@dataclass(frozen=True)
class AdvisoryEvidence:
    """Evidence returned by an external engine before Claude verification."""

    engine_id: str
    variant: str
    evidence: str
    provenance: dict[str, Any]
    execution_id: str = ""
    intent: str = "offload"
    evidence_digest: str = ""
    runner_output_digest: str = ""
    runner_output_bytes: int | None = None
    source_finding_ids: tuple[str, ...] = ()
    source_findings: tuple[reconcile.SourceFinding, ...] = ()
    verified_by_claude: bool = False
    role_kind: str = "worker"
    halt: str | None = None
    # The runner's ``bridge_receipt.v1`` proof-of-execution, threaded from ``result["receipt"]``
    # by :func:`dispatch` (plan U5, KTD8). Additive and defaulted (R11) -- receipt-less runners
    # (every CLI adapter today, and any failed dispatch) leave it ``None``. U6 consumes it to gate
    # ``RAN_AS_REQUESTED`` vs ``UNPROVEN``; this unit only lands and populates the field.
    runner_receipt: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.role_kind not in engine_resolver.ROLE_KINDS:
            raise DispatchError(
                f"advisory evidence role_kind {self.role_kind!r} not in "
                f"{engine_resolver.ROLE_KINDS}"
            )
        try:
            reconcile.recipe_for_intent(self.intent)
        except reconcile.ReconciliationError as exc:
            raise DispatchError(f"advisory evidence has invalid intent: {exc}") from exc
        raw_output_digest = self.runner_output_digest or reconcile.evidence_digest(self.evidence)
        if self.runner_output_digest:
            try:
                reconcile._require_digest(self.runner_output_digest, "runner_output_digest")
            except reconcile.ReconciliationError as exc:
                raise DispatchError(str(exc)) from exc
        if self.runner_output_bytes is not None and (
            not isinstance(self.runner_output_bytes, int)
            or isinstance(self.runner_output_bytes, bool)
            or self.runner_output_bytes < 0
        ):
            raise DispatchError("runner_output_bytes must be a non-negative integer")
        raw_output_bytes = (
            self.runner_output_bytes
            if self.runner_output_bytes is not None
            else len(self.evidence.encode("utf-8"))
        )
        if not isinstance(self.source_findings, tuple) or not all(
            isinstance(finding, reconcile.SourceFinding) for finding in self.source_findings
        ):
            raise DispatchError("advisory source findings must be an immutable typed collection")
        findings = self.source_findings
        if not findings and self.evidence and self.intent == "offload":
            findings = (reconcile.SourceFinding.from_content(self.evidence, 0, opaque=True),)
        if findings:
            ordinals = tuple(finding.ordinal for finding in findings)
            if ordinals != tuple(range(len(findings))):
                raise DispatchError("advisory source findings require contiguous ordered ordinals")
        if self.intent != "offload" and any(finding.opaque for finding in findings):
            raise DispatchError("opaque-artifact findings are allowed only for explicit offload")
        if self.intent in {"second-opinion", "divergence"} and self.halt is None:
            canonical_evidence = reconcile.render_source_findings(findings)
            if self.evidence != canonical_evidence:
                raise DispatchError(
                    f"{self.intent} evidence must exactly match the canonical ordered findings "
                    "envelope"
                )
        else:
            canonical_evidence = self.evidence
        digest = reconcile.evidence_digest(canonical_evidence)
        if self.evidence_digest and self.evidence_digest != digest:
            raise DispatchError("advisory evidence digest disagrees with canonical finding content")
        expected_ids = tuple(finding.source_finding_id for finding in findings)
        if self.source_finding_ids and self.source_finding_ids != expected_ids:
            raise DispatchError("advisory source-finding identities disagree with its content")
        object.__setattr__(self, "evidence", canonical_evidence)
        object.__setattr__(self, "evidence_digest", digest)
        object.__setattr__(self, "runner_output_digest", raw_output_digest)
        object.__setattr__(self, "runner_output_bytes", raw_output_bytes)
        object.__setattr__(self, "source_finding_ids", expected_ids)
        object.__setattr__(self, "source_findings", findings)


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


@dataclass(frozen=True)
class PanelDispatchResult:
    """Advisory-only result of a fully reconciled external-engine panel."""

    role_name: str
    member_evidence: tuple[AdvisoryEvidence, ...]
    gathered_evidence: tuple[reconcile.PanelMemberEvidence, ...]
    reconciliation: reconcile.ReconciliationResult
    reconcile_fact: dict[str, Any]
    apply_fact: dict[str, Any]
    advisory: bool = True


@dataclass(frozen=True)
class ManifestTransitionResult:
    """A canonical Team Execution manifest transition and its close receipt (#677/U3)."""

    manifest: pm.Manifest
    close_receipt: dict[str, Any]


# In-process FALLBACK for the consecutive gated-divergence attempt counter (KTD7
# re-queue-once-then-HALT), keyed session + engine. The durable counter lives in the
# delegation-state marker family (`delegation_state.record_integrity_divergence`,
# `.claude/delegation/integrity.json`) so it survives one-process-per-attempt consumers
# (#520 F1); this dict is used only when that store is unavailable (version-skewed
# fleet-core, unwritable filesystem). Reset on any corroborated acceptance; a surviving
# count of 1 means the NEXT divergence for the same key is the second consecutive one
# and must HALT.
_INTEGRITY_ATTEMPTS: dict[str, int] = {}
_SATISFIED_RECONCILIATIONS: set[tuple[str, str, str, str]] = set()

_TRIPWIRE_UNARMED = "tripwire_unarmed"
_INTEGRITY_REASON = (
    "delegation-integrity: engine self-report 'ok' but observer corroboration failed "
    "(bundle launch flag + schema-valid receipt required)"
)


def _integrity_key(session_id: str, engine_id: str) -> str:
    return f"{session_id or 'anon'}:{engine_id}"


def _record_integrity_divergence(
    session_id: str, engine_id: str, workspace_root: Path | str | None
) -> int:
    """Record one gated divergence durably; returns the consecutive attempt count (#520 F1).

    Prefers the delegation-state marker family (cross-process, KTD7's real guarantee); falls
    back to the in-process dict when that store is unavailable (skewed fleet-core lacking the
    counter API, unwritable filesystem) so the same-process behavior is never worse than
    pre-#520.
    """
    key = _integrity_key(session_id, engine_id)
    delegation_state, _ = _load_fleet_module("delegation_state")
    if delegation_state is not None and hasattr(delegation_state, "record_integrity_divergence"):
        try:
            attempt = int(
                delegation_state.record_integrity_divergence(
                    session_id or "anon", engine_id, root=workspace_root
                )
            )
        except Exception:  # noqa: BLE001 - durable-store trouble degrades to in-process
            pass
        else:
            _INTEGRITY_ATTEMPTS[key] = attempt
            return attempt
    attempt = _INTEGRITY_ATTEMPTS.get(key, 0) + 1
    _INTEGRITY_ATTEMPTS[key] = attempt
    return attempt


def _clear_integrity_attempts(
    session_id: str, engine_id: str, workspace_root: Path | str | None
) -> None:
    """Reset the divergence counter (corroborated acceptance, or immediately after a HALT)."""
    _INTEGRITY_ATTEMPTS.pop(_integrity_key(session_id, engine_id), None)
    delegation_state, _ = _load_fleet_module("delegation_state")
    if delegation_state is not None and hasattr(delegation_state, "clear_integrity_attempts"):
        with contextlib.suppress(Exception):
            delegation_state.clear_integrity_attempts(
                session_id or "anon", engine_id, root=workspace_root
            )


def build_codex_invocation(
    resolution: Resolution,
    *,
    sandbox: Any = None,
    role_kind: str = "worker",
) -> dict[str, Any]:
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
    _validate_role_kind(role_kind)
    invocation: dict[str, Any] = {
        "via": "codex:delegate",
        "task": resolution.payload,
        "sandbox": "read-only",
    }
    if resolution.invocation is not None:
        model = resolution.invocation.get("model")
        effort = resolution.invocation.get("effort")
        if not isinstance(model, str) or not model.strip():
            raise DispatchError(
                "registry-backed Codex resolution is missing a non-empty invocation.model"
            )
        if not isinstance(effort, str) or not effort.strip():
            raise DispatchError(
                "registry-backed Codex resolution is missing a non-empty invocation.effort"
            )
        invocation["model"] = model
        invocation["effort"] = effort
    if role_kind in {"advisory-reviewer", "panel"}:
        invocation["role"] = "reviewer"
    _assert_payload_preserved(invocation["task"], resolution.payload)
    return invocation


def build_agy_envelope(
    resolution: Resolution,
    *,
    model: Any,
    sandbox: Any = None,
    write_set: list[str] | None = None,
    role_kind: str = "worker",
) -> dict[str, Any]:
    """Build an agy delegation envelope with a verbatim task payload.

    Default / read-only sandbox keeps the evidence-only ceiling (``mode: "no-write"``,
    ``write_set: []``) -- byte-identical to before. A sandboxed-mutate sandbox (read-write into an
    owned/isolated workspace) lifts the ceiling by WIRING agy's existing clone + gated patch import
    (#287 U5/R6): ``mode: "patch-only"``, ``write_set`` = the unit's declared files,
    ``apply_policy: "preserve-patch"``. No new isolation is built -- the remotes-stripped disposable
    clone agy already sets up is the workspace, and preserve-patch was already the apply policy.
    """
    _validate_role_kind(role_kind)
    if _sandbox_requests_writes(sandbox):
        mode = "patch-only"
        allowed_writes = list(write_set or [])
    else:
        mode = "no-write"
        allowed_writes = []
    envelope = {
        "schema": "agy.delegation.v1",
        "role": "reviewer" if role_kind in {"advisory-reviewer", "panel"} else "coder",
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


def _dispatch_once(
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
    execution_id: str = "",
    intent: str = "offload",
    role_kind: str = "worker",
    deferred_fact_writes: list[tuple[dict[str, Any], AdvisoryEvidence, dict[str, Any]]]
    | None = None,
) -> AdvisoryEvidence | RequeueDisposition:
    """Run an external engine adapter and return advisory evidence only.

    ``sandbox`` (a Unit's declared containment) + ``write_set`` (its declared files) thread through
    to the envelope builders (#287 U5): a sandboxed-mutate agy unit lifts to patch-only; a
    sandboxed-mutate codex unit raises ``DispatchError`` (no write adapter). Default/read-only is
    byte-identical to before.

    ``ledger``/``subplot_id``/``at`` (#401) are **telemetry only** — when all are supplied a real
    advisory call records an ``engine`` run-fact (and a ``delegation`` fact for an ``agy.delegation.v1``
    call), including a launch that returns ``pending`` and is never collected. This never gates and
    never changes the returned evidence (KTD5); omitting them is a no-op, so every existing caller
    is byte-identical.

    Two-signal acceptance (#384 U5, R4/R6, KTD6/KTD7) is opt-in through three new kwargs:

    - ``session_id`` — when supplied, the dispatch layer ARMS the delegation-liveness marker
      (``delegation_state.arm``) before running the adapter and disarms it in a ``finally``.
      An arming failure never blocks dispatch: it is recorded fail-open as a named
      ``tripwire_unarmed`` note on the evidence provenance (and the manifest).
    - ``workspace_root`` — the repo root under which the engine's bundle artifacts live;
      supplying it (or ``gated=True``) enables observer corroboration after the run:
      observer-yes = bundle ``launch_key`` true (``delegation_audit.corroborate``) AND a
      ``_receipt_problems()``-clean receipt. A missing launch flag is observer-NO
      (conservative). HTTP-transport lanes (#524) have no bundle directory, so their
      observer signal is receipt-only (:func:`_http_receipt_corroborates`): full receipt
      schema + emitter signature policy + output attestation bound to the returned output.
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
    try:
        reconcile.recipe_for_intent(intent)
    except reconcile.ReconciliationError as exc:
        raise DispatchError(f"dispatch intent is invalid: {exc}") from exc
    _validate_role_kind(role_kind)

    def record_facts(evidence: AdvisoryEvidence, result: dict[str, Any]) -> None:
        if deferred_fact_writes is not None:
            deferred_fact_writes.append((invocation, evidence, result))
            return
        _record_advisory_facts(
            ledger,
            invocation,
            evidence,
            result,
            subplot_id=subplot_id,
            at=at,
            resolution=resolution,
        )

    if resolution.halt is not None:
        halted_provenance: dict[str, Any] = {
            "engine": resolution.engine_id,
            "variant": resolution.variant,
            "status": "halted",
        }
        _copy_resolution_warnings(halted_provenance, resolution)
        if chaperone is not None:
            halted_provenance["chaperone"] = dict(chaperone)
        return AdvisoryEvidence(
            engine_id=resolution.engine_id,
            variant=resolution.variant,
            evidence="",
            provenance=halted_provenance,
            execution_id=execution_id,
            intent=intent,
            role_kind=role_kind,
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
            economics_provenance = {
                "engine": resolution.engine_id,
                "variant": resolution.variant,
                "status": "halted",
                "economics": economics_decision.to_provenance(),
            }
            _copy_resolution_warnings(economics_provenance, resolution)
            if chaperone is not None:
                economics_provenance["chaperone"] = dict(chaperone)
            return AdvisoryEvidence(
                engine_id=resolution.engine_id,
                variant=resolution.variant,
                evidence="",
                provenance=economics_provenance,
                execution_id=execution_id,
                intent=intent,
                role_kind=role_kind,
                halt=economics_decision.status,
            )

    invocation = _build_invocation(
        resolution,
        model=model,
        sandbox=sandbox,
        write_set=write_set,
        role_kind=role_kind,
    )

    # Arm the delegation-liveness marker BEFORE the adapter runs (KTD4: arming authority is
    # the dispatch layer) and disarm in a finally. Arming failure is fail-open but NAMED:
    # dispatch still runs, and the evidence/manifest carry a `tripwire_unarmed` note. A
    # fleet-core too old to carry delegation_state at all degrades the same way, under its
    # own name (`delegation-audit-unavailable`, #520 F5) — never an import-time crash.
    armed_at: float | None = None
    tripwire_note = ""
    delegation_state: ModuleType | None = None
    if session_id:
        delegation_state, state_degradation = _load_fleet_module("delegation_state")
        if delegation_state is None:
            tripwire_note = state_degradation
        else:
            try:
                entry = delegation_state.arm(
                    resolution.engine_id, session_id, "engine_dispatch", root=workspace_root
                )
                armed_at = float(entry.armed_at)
            except Exception as exc:  # noqa: BLE001 - fail-open, named (plan U5 error scenario)
                tripwire_note = f"{_TRIPWIRE_UNARMED}: {exc}"
    try:
        result = runner(invocation)
    except BaseException:
        if armed_at is not None and delegation_state is not None:
            with contextlib.suppress(Exception):
                delegation_state.disarm(session_id, root=workspace_root)
        raise

    try:
        return _finish_adapter_result(
            result,
            resolution=resolution,
            invocation=invocation,
            record_facts=record_facts,
            armed_at=armed_at,
            tripwire_note=tripwire_note,
            gated=gated,
            session_id=session_id,
            workspace_root=workspace_root,
            expected_identity=expected_identity,
            chaperone=chaperone,
            economics_decision=economics_decision,
            execution_id=execution_id,
            intent=intent,
            role_kind=role_kind,
            downgrade_note=downgrade_note,
        )
    finally:
        if armed_at is not None and delegation_state is not None:
            # Disarm after the pending fact is written, not before.
            with contextlib.suppress(Exception):
                delegation_state.disarm(session_id, root=workspace_root)


def _finish_adapter_result(
    result: dict[str, Any],
    *,
    resolution: Resolution,
    invocation: dict[str, Any],
    record_facts: Callable[..., None],
    armed_at: float | None,
    tripwire_note: str,
    gated: bool,
    session_id: str,
    workspace_root: Path | str | None,
    expected_identity: str | None,
    chaperone: dict[str, Any] | None,
    economics_decision: Any,
    execution_id: str,
    intent: str,
    role_kind: str,
    downgrade_note: Callable[..., str],
) -> AdvisoryEvidence | RequeueDisposition:
    _reject_gatekeeper_keys(result)
    status = _string_result(result.get("status"), default="malformed")
    output = _string_result(result.get("output"), default="")
    try:
        source_findings = (
            reconcile.parse_source_findings(result["findings"]) if "findings" in result else ()
        )
    except reconcile.ReconciliationError as exc:
        raise DispatchError(f"runner findings envelope is malformed: {exc}") from exc
    if status == "ok" and intent in {"second-opinion", "divergence"} and "findings" not in result:
        raise DispatchError(f"{intent} evidence requires a typed runner findings envelope")
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
    if runner_receipt is not None:
        provenance["bridge_run_key"] = bridge_signatures.bridge_run_key(runner_receipt)

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
        # HTTP-transport lanes have no runs/ bundle directory and no ENGINE_CONFIGS row —
        # the bridge's receipt IS the observer artifact (#524) — so they corroborate
        # receipt-only and never consult delegation_audit. Keyed off the registry-built
        # invocation (authoritative), never off the runner-controlled receipt's own claim.
        http_lane = invocation.get("transport") == "http"
        if two_signal and not http_lane:
            # Version-skew guard (#520 F5): a fleet-core lacking delegation_audit degrades
            # NAMED on the provenance; the observer predicate below then reads conservative
            # observer-NO, never a silent accept and never an import/dispatch crash.
            _, audit_degradation = _load_fleet_module("delegation_audit")
            if audit_degradation:
                provenance["degradation"] = audit_degradation
        observer_yes = two_signal and _observer_corroborates(
            resolution.engine_id,
            runner_receipt,
            workspace_root=workspace_root,
            since_ts=armed_at,
            transport="http" if http_lane else "",
            variant=resolution.variant,
            evidence_text=output,
        )
        integrity_key = _integrity_key(session_id, resolution.engine_id)
        if two_signal and not observer_yes:
            provenance["integrity"] = pm.Disposition.DELEGATION_INTEGRITY.value
            if gated:
                # KTD7 re-queue-once-then-HALT: first divergence returns the typed re-queue
                # disposition; a second CONSECUTIVE divergence for the same key HALTs. The
                # count is durable (delegation-state marker family, #520 F1) so the guarantee
                # holds across one-process-per-attempt consumers, not just this process.
                attempt = _record_integrity_divergence(
                    session_id, resolution.engine_id, workspace_root
                )
                if attempt >= 2:
                    _clear_integrity_attempts(session_id, resolution.engine_id, workspace_root)
                    raise DispatchError(
                        "HALT: second consecutive delegation-integrity divergence for "
                        f"{integrity_key!r} -- {_INTEGRITY_REASON} "
                        "(KTD7: re-queue once, then HALT -- never silent accept)"
                    )
                reason = f"{_INTEGRITY_REASON} (divergence attempt {attempt}; one re-queue allowed)"
                provenance["note"] = reason
                disputed = AdvisoryEvidence(
                    engine_id=resolution.engine_id,
                    variant=resolution.variant,
                    evidence="",
                    provenance=provenance,
                    execution_id=execution_id,
                    intent=intent,
                    role_kind=role_kind,
                    halt=reason,
                    runner_receipt=runner_receipt,
                )
                record_facts(disputed, result)
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
                execution_id=execution_id,
                intent=intent,
                role_kind=role_kind,
                halt=note,
                runner_receipt=runner_receipt,
            )
            record_facts(evidence, result)
            return evidence
        if gated:
            _clear_integrity_attempts(session_id, resolution.engine_id, workspace_root)
        if two_signal and observer_yes:
            provenance["observer_corroborated"] = True
        evidence = AdvisoryEvidence(
            engine_id=resolution.engine_id,
            variant=resolution.variant,
            evidence=output,
            provenance=provenance,
            execution_id=execution_id,
            intent=intent,
            role_kind=role_kind,
            source_findings=source_findings,
            runner_output_digest=reconcile.evidence_digest(output),
            runner_output_bytes=len(output.encode("utf-8")),
            runner_receipt=runner_receipt,
        )
    elif status == PENDING_STATUS:
        provenance["note"] = PENDING_NOTE
        evidence = AdvisoryEvidence(
            engine_id=resolution.engine_id,
            variant=resolution.variant,
            evidence="",
            provenance=provenance,
            execution_id=execution_id,
            intent=intent,
            role_kind=role_kind,
            halt=PENDING_NOTE,
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
            execution_id=execution_id,
            intent=intent,
            role_kind=role_kind,
            halt=note,
            runner_receipt=runner_receipt,
        )

    record_facts(evidence, result)
    return evidence


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
    execution_id: str = "",
    intent: str = "offload",
    role_kind: str = "worker",
    attempt_id: str = "",
    predecessor_close: Mapping[str, Any] | None = None,
) -> AdvisoryEvidence | RequeueDisposition:
    """Dispatch one external-engine adapter call; mint the close receipt for a trusted session.

    Omitting ``session_id`` preserves the compatibility path for pure builders and tests (no close
    receipt). Registered runtime consumers provide their trusted session id and bounded
    execution/attempt identity — caller-asserted since the broker's retirement (#677/U3) — and the
    dispatch mints a ``saga.close-receipt.v1`` receipt onto the evidence provenance
    (``provenance["dispatch_close"]``). A retry chains from the prior attempt's receipt via
    ``predecessor_close``; the binding is by digest, so a stale or tampered predecessor refuses.
    Dispatch is NOT admitted against any runtime lease: concurrent dispatches of the same attempt
    both proceed (accepted loss, plan #677 Scope Decision row 1).
    """

    if not session_id:
        return _dispatch_once(
            resolution,
            runner=runner,
            model=model,
            sandbox=sandbox,
            write_set=write_set,
            ledger=ledger,
            subplot_id=subplot_id,
            at=at,
            gated=gated,
            session_id=session_id,
            workspace_root=workspace_root,
            expected_identity=expected_identity,
            chaperone=chaperone,
            economics=economics,
            execution_id=execution_id,
            intent=intent,
            role_kind=role_kind,
        )

    # Broker-free registered dispatch (#677/U3). Identity is CALLER-ASSERTED — a decision, not an
    # oversight (plan #677 Scope Decision row 2, accepted on judgment): the bounded session /
    # execution / attempt identities below are validated for shape, never broker-verified. Dispatch
    # is no longer admitted against a runtime lease, so two concurrent dispatches of the same
    # attempt BOTH PROCEED — the accepted idempotency loss (row 1), pinned by test. What survives is
    # the close-receipt chain: this dispatch mints a self-authenticating receipt that the manifest
    # claim/adjudication transitions chain from by digest.
    _bounded_identity(session_id, "session_id")
    execution_identity = _bounded_identity(execution_id, "execution_id")
    attempt_identity = _bounded_identity(attempt_id, "attempt_id")
    resource_ref = _engine_resource_ref(execution_identity, attempt_identity)
    predecessor_receipt_sha256 = ""
    if predecessor_close is not None:
        predecessor_receipt_sha256 = _validate_predecessor_close(
            predecessor_close,
            resource_ref=resource_ref,
            expected_producer="saga",
            run_id=execution_identity,
            binding="engine retry predecessor",
        )

    evidence = _dispatch_once(
        resolution,
        runner=runner,
        model=model,
        sandbox=sandbox,
        write_set=write_set,
        ledger=ledger,
        subplot_id=subplot_id,
        at=at,
        gated=gated,
        session_id=session_id,
        workspace_root=workspace_root,
        expected_identity=expected_identity,
        chaperone=chaperone,
        economics=economics,
        execution_id=execution_id,
        intent=intent,
        role_kind=role_kind,
    )
    bound_evidence = evidence.evidence if isinstance(evidence, RequeueDisposition) else evidence
    expected_output_sha256 = hashlib.sha256(
        json.dumps(
            {
                "schema": "saga.expected-output.v1",
                "execution_id": execution_identity,
                "attempt_id": attempt_identity,
                "intent": intent,
                "role_kind": role_kind,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    protected_write_intent_sha256 = hashlib.sha256(
        json.dumps(
            {
                "schema": "saga.dispatch-write-intent.v1",
                "execution_id": execution_identity,
                "attempt_id": attempt_identity,
                "engine_id": bound_evidence.engine_id,
                "variant": bound_evidence.variant,
                "evidence_digest": bound_evidence.evidence_digest,
                "runner_output_digest": bound_evidence.runner_output_digest,
                "halt": bound_evidence.halt,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()
    bound_evidence.provenance["dispatch_close"] = _mint_close_receipt(
        resource_ref=resource_ref,
        producer="saga",
        run_id=execution_identity,
        expected_output_sha256=expected_output_sha256,
        protected_write_intent_sha256=protected_write_intent_sha256,
        predecessor_receipt_sha256=predecessor_receipt_sha256,
    )
    return evidence


def _bounded_identity(value: str, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise DispatchError(f"engine dispatch {field} must be a non-empty string <= 256 characters")
    if any(ord(character) < 32 for character in value):
        raise DispatchError(f"engine dispatch {field} must not contain control characters")
    return value


def _engine_resource_ref(execution_id: str, attempt_id: str) -> dict[str, str]:
    """Return execution-stable identity; attempt is evidence metadata, never a resource."""

    _bounded_identity(attempt_id, "attempt_id")
    digest = hashlib.sha256(f"{len(execution_id)}:{execution_id}".encode()).hexdigest()
    return {"logical_unit_id": f"engine-dispatch:{digest}"}


def dispatch_advisory_panel(
    request: AdvisoryPanelRequest,
    *,
    registry: Any,
    runner: Runner,
    foreman: PanelForeman,
    execution_id: str,
    session_id: str,
    intent: str,
    ledger: run_ledger.RunLedger,
    subplot_id: str,
    at: str,
    task_context: dict[str, Any] | None = None,
    memo: RunMemo | None = None,
) -> PanelDispatchResult:
    """Resolve, dispatch, and Claude-reconcile one bounded advisory jury.

    ``resolve_role`` validates the normalized role and member count before it performs any
    member preflight. All resolutions are then checked with ``panel_halt`` before the first
    dispatch, so an unavailable member cannot create partial work. Member dispatches receive no
    ledger: raw panel output is in-memory foreman input only. The validated typed foreman result
    is the sole panel content appended to the run-fact ledger.

    Broker-free (#677/U3): the panel no longer acquires a lease or renews it between members, and
    the reconcile/apply facts are appended directly rather than under a settlement fence — the
    accepted fencing loss applies (plan #677 Scope Decision row 1). ``session_id`` stays required:
    it keys the delegation-integrity tripwire inside each member dispatch.
    """
    if not isinstance(request, AdvisoryPanelRequest):
        raise DispatchError("advisory panel dispatch requires an AdvisoryPanelRequest")
    try:
        reconcile.validate_panel_execution_metadata(
            execution_id=execution_id,
            intent=intent,
            subplot_id=subplot_id,
            at=at,
        )
    except reconcile.ReconciliationError as exc:
        raise DispatchError(f"advisory panel execution metadata is invalid: {exc}") from exc
    _bounded_identity(session_id, "session_id")
    role_name = request.role
    try:
        resolutions = engine_resolver.resolve_role(
            role_name,
            registry=registry,
            task_context=task_context,
            memo=memo,
        )
    except engine_resolver.RegistryError as exc:
        raise DispatchError(f"advisory panel request rejected: {exc}") from exc

    halt = engine_resolver.panel_halt(resolutions)
    if halt is not None:
        raise DispatchError(f"advisory panel halted before dispatch: {halt}")

    member_evidence: list[AdvisoryEvidence] = []
    total_output_bytes = 0
    for resolution in resolutions:
        panel_evidence = _dispatch_once(
            resolution,
            runner=runner,
            execution_id=execution_id,
            session_id=session_id,
            intent=intent,
            role_kind="panel",
        )
        if isinstance(panel_evidence, RequeueDisposition):
            raise DispatchError("advisory panel dispatch unexpectedly requested a gated requeue")
        if panel_evidence.halt is not None:
            raise DispatchError(
                "advisory panel member failed; no reconciliation fact was written: "
                f"{panel_evidence.engine_id}/{panel_evidence.variant}: {panel_evidence.halt}"
            )
        output_bytes = len(panel_evidence.evidence.encode("utf-8"))
        if output_bytes > PANEL_MEMBER_OUTPUT_BYTES_CAP:
            raise DispatchError(
                "advisory panel member output exceeds "
                f"PANEL_MEMBER_OUTPUT_BYTES_CAP={PANEL_MEMBER_OUTPUT_BYTES_CAP} bytes: "
                f"{panel_evidence.engine_id}/{panel_evidence.variant} produced {output_bytes}"
            )
        total_output_bytes += output_bytes
        if total_output_bytes > PANEL_TOTAL_OUTPUT_BYTES_CAP:
            raise DispatchError(
                "advisory panel cumulative output exceeds "
                f"PANEL_TOTAL_OUTPUT_BYTES_CAP={PANEL_TOTAL_OUTPUT_BYTES_CAP} bytes: "
                f"observed {total_output_bytes}"
            )
        member_evidence.append(panel_evidence)

    try:
        gathered = reconcile.gather_panel_evidence(
            (f"{evidence.engine_id}/{evidence.variant}", evidence.source_findings)
            for evidence in member_evidence
        )
        foreman_result = foreman(gathered)
    except Exception as exc:  # noqa: BLE001 - foreman failure is a named no-append boundary
        raise DispatchError(f"Claude panel foreman failed before ledger append: {exc}") from exc
    try:
        result = reconcile.validate_panel_reconciliation(
            foreman_result,
            execution_id=execution_id,
            intent=intent,
            evidence=gathered,
        )
    except reconcile.ReconciliationError as exc:
        raise DispatchError(f"Claude panel foreman reconciliation failed: {exc}") from exc

    # Panel-member attribution (#459 R4): which members produced each gathered finding, so the
    # capability_elo reducer can derive head-to-head matches from this reconciliation. Metadata
    # only — it never enters the canonical result hash and grants no authority.
    member_attribution = {item.source_finding_id: list(item.member_ids) for item in gathered}
    reconcile_fact = reconcile.append_reconciliation_fact(
        ledger,
        result,
        action=reconcile.ReconciliationAction.RECONCILE,
        subplot_id=subplot_id,
        at=at,
        member_index=member_attribution,
    )
    apply_fact = reconcile.append_reconciliation_fact(
        ledger,
        result,
        action=reconcile.ReconciliationAction.APPLY,
        subplot_id=subplot_id,
        at=at,
        member_index=member_attribution,
    )
    return PanelDispatchResult(
        role_name=role_name,
        member_evidence=tuple(member_evidence),
        gathered_evidence=gathered,
        reconciliation=result,
        reconcile_fact=reconcile_fact,
        apply_fact=apply_fact,
    )


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
                cost_class=cast(Literal["metered", "free"], cost_class),
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


def _is_proof_extension_problem(problem: str) -> bool:
    return problem.startswith(
        (
            "receipt_emitter ",
            "run_id ",
            "external_tokens ",
            "output_attestation ",
        )
    )


def _base_receipt_problems(runner_receipt: dict[str, Any] | None) -> list[str]:
    return [
        problem
        for problem in _receipt_problems(runner_receipt)
        if not _is_proof_extension_problem(problem)
    ]


def _receipt_identity_problems(evidence: AdvisoryEvidence) -> list[str]:
    if evidence.runner_receipt is None or _base_receipt_problems(evidence.runner_receipt):
        return []
    receipt_engine = evidence.runner_receipt.get("engine_id")
    receipt_variant = evidence.runner_receipt.get("variant")
    errors: list[str] = []
    if receipt_engine != evidence.engine_id:
        errors.append(
            "proof-integrity: receipt-engine-mismatch "
            f"expected={evidence.engine_id!r} observed={receipt_engine!r}"
        )
    if receipt_variant != evidence.variant:
        errors.append(
            "proof-integrity: receipt-variant-mismatch "
            f"expected={evidence.variant!r} observed={receipt_variant!r}"
        )
    return errors


def _proof_integrity_problems(evidence: AdvisoryEvidence) -> list[str]:
    """Stronger #388 proof checks, after the base receipt schema has passed."""
    receipt_problems = _receipt_problems(evidence.runner_receipt)
    if any(not _is_proof_extension_problem(problem) for problem in receipt_problems):
        return []
    assert evidence.runner_receipt is not None  # narrowed by _receipt_problems above
    proof_errors = [
        f"proof-integrity: {problem}"
        for problem in receipt_problems
        if _is_proof_extension_problem(problem)
    ]
    proof_errors.extend(
        bridge_signatures.validate_receipt_signature(
            evidence.runner_receipt,
            evidence_text=evidence.evidence,
            evidence_digest=evidence.runner_output_digest,
            evidence_bytes=evidence.runner_output_bytes,
        )
    )
    proof_errors.extend(_receipt_identity_problems(evidence))
    return proof_errors


def _bridge_key_set(
    keys: set[str] | list[str] | tuple[str, ...] | None,
) -> set[str] | None:
    if keys is None:
        return None
    return {str(key) for key in keys if str(key)}


def _gate_bridge_keys(evidence: AdvisoryEvidence, manifest: pm.Manifest | None) -> set[str]:
    keys: set[str] = set()
    evidence_key = _bridge_run_key(evidence)
    if evidence_key:
        keys.add(evidence_key)
    if manifest is not None and manifest.bridge_run_key:
        keys.add(manifest.bridge_run_key)
    return keys


def _filtered_liveness_errors(
    launched_keys: set[str],
    consumed_keys: set[str],
    expected_keys: set[str] | None,
) -> list[str]:
    if expected_keys is not None:
        launched_keys = launched_keys & expected_keys
        consumed_keys = consumed_keys & expected_keys
    return bridge_signatures.liveness_errors(launched_keys, consumed_keys)


def bridge_liveness_errors(
    ledger: run_ledger.RunLedger,
    store: manifest_store.Store,
    *,
    expected_keys: set[str] | list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """Compare launched bridge runs in the ledger to consumed runs in manifests (#388)."""
    launched: set[str] = set()
    for fact in run_ledger.read_facts(ledger):
        if fact.get("kind") != "engine":
            continue
        key = fact.get("bridge_run_key")
        if isinstance(key, str) and key.strip():
            launched.add(key)

    consumed: set[str] = set()
    for execution_id in manifest_store.list_manifests(store):
        manifest = manifest_store.read_manifest(store, execution_id)
        if not isinstance(manifest, dict):
            continue
        key = manifest.get("bridge_run_key")
        if isinstance(key, str) and key.strip():
            consumed.add(key)

    return _filtered_liveness_errors(
        launched,
        consumed,
        _bridge_key_set(expected_keys),
    )


def _bridge_run_key(evidence: AdvisoryEvidence) -> str:
    if evidence.runner_receipt is None:
        return ""
    return bridge_signatures.bridge_run_key(evidence.runner_receipt)


def _external_tokens(evidence: AdvisoryEvidence) -> float | None:
    if evidence.runner_receipt is None:
        return None
    value = evidence.runner_receipt.get("external_tokens")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _observer_corroborates(
    engine_id: str,
    runner_receipt: dict[str, Any] | None,
    *,
    workspace_root: Path | str | None,
    since_ts: float | None,
    transport: str = "",
    variant: str = "",
    evidence_text: str = "",
) -> bool:
    """The independent observer signal (#384 U5): launch flag true + schema-valid receipt.

    Conservative by construction: a receipt-valid bundle whose ``launch_key`` is missing or
    false is observer-NO, an unknown/uncorroboratable engine is observer-NO, and any error
    reading the bundles is observer-NO. A fleet-core too old to carry ``delegation_audit``
    is observer-NO too (#520 F5) — ``dispatch`` records the named
    ``delegation-audit-unavailable`` degradation on the provenance. The observer never
    raises -- divergence handling (not this predicate) decides what a "no" costs.

    HTTP-transport lanes (#524) have no runs/ bundle directory and no ``ENGINE_CONFIGS``
    row — the HTTP bridge's own receipt IS the observer artifact — so ``transport="http"``
    routes to :func:`_http_receipt_corroborates` (receipt-only, proof extensions and output
    attestation included) instead of the bundle scan. The subprocess-bundle path below is
    byte-identical for every non-HTTP engine (issue #524 non-goal: agy/codex unchanged).
    """
    if _base_receipt_problems(runner_receipt):
        return False
    if transport == "http":
        return _http_receipt_corroborates(engine_id, variant, runner_receipt, evidence_text)
    delegation_audit, _ = _load_fleet_module("delegation_audit")
    if delegation_audit is None:
        return False
    try:
        corroboration = delegation_audit.corroborate(engine_id, since_ts, root=workspace_root)
    except Exception:  # noqa: BLE001 - observer-no beats crashing the dispatch path
        return False
    return bool(corroboration.launched)


def _http_receipt_corroborates(
    engine_id: str,
    variant: str,
    runner_receipt: dict[str, Any] | None,
    evidence_text: str,
) -> bool:
    """Receipt-only observer signal for HTTP-bridge lanes (#524, fix direction 1).

    Observer-yes requires ALL of: a fully schema-valid ``bridge_receipt.v1`` (proof
    extensions INCLUDED, unlike the base check every lane already passed), the receipt's
    own ``transport`` being ``http`` and its engine/variant identity matching the
    resolution, and the emitter's ``bridge_signatures`` policy passing with the output
    attestation bound to the ACTUAL returned output — so a receipt attesting different
    bytes than the evidence the engine handed back is a genuine divergence and still
    trips the tripwire. Anything short of all of that is observer-NO; never raises.
    """
    if runner_receipt is None or _receipt_problems(runner_receipt):
        return False
    if runner_receipt.get("transport") != "http":
        return False
    if runner_receipt.get("engine_id") != engine_id or runner_receipt.get("variant") != variant:
        return False
    try:
        problems = bridge_signatures.validate_receipt_signature(
            runner_receipt, evidence_text=evidence_text
        )
    except Exception:  # noqa: BLE001 - observer-no beats crashing the dispatch path
        return False
    return not problems


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
    resolution: Any | None = None,
) -> None:
    """Write run-fact telemetry for an advisory call. **Telemetry only (KTD5)** — never gates, and a
    no-op unless ``ledger`` + ``subplot_id`` + ``at`` are all supplied (so dispatch is byte-identical
    for every existing caller). U3 writes an ``engine`` fact on any real call; U4 adds a ``delegation``
    fact only when the invocation is an ``agy.delegation.v1`` envelope.

    ``resolution`` (#459 R1) contributes the registry-cell join fields — ``capability`` and the
    resolution-time ``rating_claimed`` — so earned-ratings reducers can join a dispatch fact to a
    ``(engine_key, capability)`` cell; ``execution_id`` joins it to a reconciliation. All three are
    strings (empty when unknown), never gates, and never change the returned evidence.
    """
    if ledger is None or not subplot_id or not at:
        return
    bridge_run_key = _bridge_run_key(evidence)
    if bridge_run_key:
        for fact in run_ledger.read_facts(ledger):
            if fact.get("kind") == "engine" and fact.get("bridge_run_key") == bridge_run_key:
                return
    proof_errors = _proof_integrity_problems(evidence)
    proof_status = "failed" if proof_errors else "ok" if bridge_run_key else "unproven"
    external_tokens = _external_tokens(evidence)
    proof_fields: dict[str, Any] = {"proof_integrity_status": proof_status}
    if bridge_run_key:
        proof_fields["bridge_run_key"] = bridge_run_key
    if external_tokens is not None:
        proof_fields["external_tokens"] = external_tokens
    if proof_errors:
        proof_fields["proof_integrity_errors"] = list(proof_errors)
    run_ledger.append_fact(
        ledger,
        run_ledger.build_fact(
            "engine",
            subplot_id=subplot_id,
            at=at,
            **{
                "engine": evidence.engine_id,
                "variant": evidence.variant,
                "status": str(evidence.provenance.get("status", "")),
                "capability": str(getattr(resolution, "capability", None) or ""),
                "rating_claimed": str(getattr(resolution, "rating_claimed", None) or ""),
                "execution_id": evidence.execution_id or "",
                "cost": _num(result.get("cost")),
                "latency_seconds": _num(result.get("latency_seconds")),
                "tokens": _num(result.get("tokens")),
                **proof_fields,
                **_economics_fact_fields(evidence),
            },
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


def _economics_fact_fields(evidence: AdvisoryEvidence) -> dict[str, Any]:
    economics = evidence.provenance.get("economics")
    if not isinstance(economics, dict):
        return {}
    net_savings = economics.get("net_savings")
    if not isinstance(net_savings, dict):
        return {}
    fields: dict[str, Any] = {}
    for name in (
        "engine_tokens_avoided",
        "chaperone_tokens_spent",
        "net_savings_tokens",
        "net_savings_status",
        "external_cost_usd",
    ):
        if name in net_savings:
            fields[name] = net_savings[name]
    return fields


def _manifest_economics_record(evidence: AdvisoryEvidence) -> pm.EconomicsRecord | None:
    fields = _economics_fact_fields(evidence)
    if not fields:
        return None
    return pm.EconomicsRecord.from_dict(fields)


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
    A chaperone rejection is stamped on ``evidence.provenance['rejected_offload_note']`` after
    review. It enters this same precedence chain below dispatch/substitution/integrity proof
    failures and above the normal requested disposition; no second manifest path exists.
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
        receipt_problems = _base_receipt_problems(evidence.runner_receipt)
        if receipt_problems:
            disposition = pm.Disposition.UNPROVEN
            note = "no schema-valid bridge_receipt.v1: " + "; ".join(receipt_problems)
        else:
            proof_errors = _proof_integrity_problems(evidence)
            if proof_errors:
                disposition = pm.Disposition.PROOF_INTEGRITY
                note = "; ".join(proof_errors)
            elif "rejected_offload_note" in evidence.provenance:
                disposition = pm.Disposition.REJECTED_OFFLOAD
                try:
                    note = reconcile.normalize_rejection_note(
                        evidence.provenance["rejected_offload_note"]
                    )
                except reconcile.ReconciliationError as exc:
                    raise DispatchError(str(exc)) from exc
            else:
                disposition = pm.Disposition.RAN_AS_REQUESTED
                note = ""
    # A failed arming attempt (fail-open, #384 U5) stays a separately bounded operational note.
    # It must not be appended to a rejected-offload summary because that summary is evidence-bound.
    tripwire = evidence.provenance.get("tripwire", "")
    if not isinstance(tripwire, str):
        raise DispatchError("manifest tripwire note must be a string")
    tripwire_note = " ".join(tripwire.split())
    # R3 invariant (#390 U2): every non-RAN_AS_REQUESTED manifest carries a non-empty,
    # human-readable disposition_note -- a forced fallback must be traceable prose, not a bare
    # enum. A degenerate empty reason (empty halt string, whitespace-only note) gets a fixed
    # fallback naming the disposition rather than an empty note.
    if disposition is not pm.Disposition.RAN_AS_REQUESTED and not str(note).strip():
        note = f"{disposition.value}: reason unspecified"
    economics = _manifest_economics_record(evidence)
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
        economics=economics,
        bridge_run_key=_bridge_run_key(evidence),
        tripwire_note=tripwire_note,
    )


def reject_offload(evidence: AdvisoryEvidence, rejection_note: str) -> AdvisoryEvidence:
    """Mark reviewed engine output as rejected without mutating the source evidence."""
    if evidence.halt is not None:
        raise DispatchError("cannot reject an offload that did not produce reviewable output")
    try:
        note = reconcile.normalize_rejection_note(rejection_note)
    except reconcile.ReconciliationError as exc:
        raise DispatchError(str(exc)) from exc
    return AdvisoryEvidence(
        engine_id=evidence.engine_id,
        variant=evidence.variant,
        evidence=evidence.evidence,
        provenance={**evidence.provenance, "rejected_offload_note": note},
        execution_id=evidence.execution_id,
        intent=evidence.intent,
        evidence_digest=evidence.evidence_digest,
        runner_output_digest=evidence.runner_output_digest,
        runner_output_bytes=evidence.runner_output_bytes,
        source_finding_ids=evidence.source_finding_ids,
        source_findings=evidence.source_findings,
        verified_by_claude=evidence.verified_by_claude,
        role_kind=evidence.role_kind,
        halt=evidence.halt,
        runner_receipt=evidence.runner_receipt,
    )


def rejected_offload_reconciliation(
    manifest: pm.Manifest,
    *,
    reconciliation_id: str,
    adjudicator_id: str,
    evidence: AdvisoryEvidence | None = None,
) -> reconcile.ReconciliationResult:
    """Turn evidence-bound rejected-offload state into typed reviewer/validator evidence."""
    if manifest.disposition is not pm.Disposition.REJECTED_OFFLOAD:
        raise DispatchError("rejected-offload reconciliation requires a rejected-offload manifest")
    if not isinstance(evidence, AdvisoryEvidence):
        raise DispatchError("rejected-offload reconciliation requires dispatched AdvisoryEvidence")
    if manifest.execution_id != evidence.execution_id:
        raise DispatchError(
            "rejected-offload manifest execution_id does not match dispatched evidence"
        )
    try:
        evidence_note = reconcile.normalize_rejection_note(
            evidence.provenance.get("rejected_offload_note")
        )
    except reconcile.ReconciliationError as exc:
        raise DispatchError(
            f"rejected-offload reconciliation requires evidence marked by reject_offload: {exc}"
        ) from exc
    if manifest.disposition_note != evidence_note:
        raise DispatchError("rejected-offload manifest note does not match dispatched evidence")
    try:
        return reconcile.build_rejected_offload_signal(
            reconciliation_id=reconciliation_id,
            execution_id=evidence.execution_id,
            intent=evidence.intent,
            adjudicator_id=adjudicator_id,
            rejection_note=manifest.disposition_note,
            bound_evidence_digest=evidence.evidence_digest,
            bound_source_finding_ids=evidence.source_finding_ids,
        )
    except reconcile.ReconciliationError as exc:
        raise DispatchError(str(exc)) from exc


def _mirror_manifest_to_audit_store(
    audit_store_root: Path | None,
    execution_id: str,
    manifest: pm.Manifest,
    evidence: AdvisoryEvidence | None,
) -> None:
    """Mirror the manifest — and the raw receipt, when the evidence carries one — to the durable
    audit store (#396, R2/KTD9). A no-op when ``audit_store_root`` is ``None`` (KTD5 — this module
    has no CLI layer, so the resolved default lives at the documented chaperone call site rather
    than a hidden default here). Never raises: a failed durable-mirror write must not fail the
    dispatch/adjudication it mirrors — the mirror is additive evidence, not a gate. A fleet-core
    too old to carry ``audit_store`` skips the mirror the same way (#520 F5, lazy guarded load).
    """
    if audit_store_root is None:
        return
    audit_store, _ = _load_fleet_module("audit_store")
    if audit_store is None:
        return
    try:
        store = audit_store.Store.for_root(audit_store_root).ensure()
        audit_store.mirror_noncanonical_manifest(store, execution_id, manifest.to_dict())
        if evidence is not None and evidence.runner_receipt is not None:
            audit_store.mirror_receipt(store, execution_id, evidence.runner_receipt)
    except OSError:
        pass


def _mirror_manifest_to_audit_store_strict(
    audit_store_root: Path,
    execution_id: str,
    manifest: pm.Manifest,
    evidence: AdvisoryEvidence | None,
) -> list[str]:
    audit_store, degradation = _load_fleet_module("audit_store")
    if audit_store is None:
        raise DispatchError(
            f"canonical manifest mirror requires fleet-core audit_store: {degradation}"
        )
    store = audit_store.Store.for_root(audit_store_root).ensure()
    manifest_path = audit_store.mirror_manifest(store, execution_id, manifest.to_dict())
    refs = [f"manifest:{execution_id}", f"audit:{manifest_path}"]
    if evidence is not None and evidence.runner_receipt is not None:
        receipt_path = audit_store.mirror_receipt(store, execution_id, evidence.runner_receipt)
        refs.append(f"audit:{receipt_path}")
    return refs


def _serialized_manifest_bytes(manifest: pm.Manifest) -> bytes:
    """Return the exact bytes ``manifest_store.write_manifest`` publishes."""

    return (json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n").encode()


def _manifest_write_intent_sha256(
    *,
    manifest_sha256: str,
    store: manifest_store.Store,
    audit_store_root: Path,
    execution_id: str,
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "audit_store_root": str(audit_store_root),
                "execution_id": execution_id,
                "manifest_store_root": str(store.root),
                "manifest_sha256": manifest_sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _canonical_manifest_transition(
    *,
    manifest: pm.Manifest,
    store: manifest_store.Store,
    execution_id: str,
    evidence: AdvisoryEvidence | None,
    audit_store_root: Path,
    predecessor_close: Mapping[str, Any],
    session_id: str,
    transition_kind: Literal["claim", "adjudication"],
    expected_current_bytes: bytes | None = None,
) -> ManifestTransitionResult:
    """CAS one Team Execution manifest transition from an exact predecessor close receipt.

    Broker-free re-key (#677/U3): the transition chains from its predecessor by the receipt's
    self-authenticating digest instead of a broker fencing token, and the write is protected by the
    byte-level CAS below instead of a settlement fence. A concurrent double-claim of the same
    execution is no longer refused at admission — the accepted fencing loss (Scope Decision row 1);
    the adjudication's ``expected_current_bytes`` CAS still catches a stale source.
    """
    _bounded_identity(session_id, "session_id")
    resource_ref = _engine_resource_ref(execution_id, "team-execution")
    expected_predecessor = "saga" if transition_kind == "claim" else "team-execution"
    predecessor_receipt_sha256 = _validate_predecessor_close(
        predecessor_close,
        resource_ref=resource_ref,
        expected_producer=expected_predecessor,
        run_id=execution_id,
        binding=f"canonical manifest {transition_kind} predecessor",
    )

    manifest_bytes = _serialized_manifest_bytes(manifest)
    expected_output_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    write_intent_sha256 = _manifest_write_intent_sha256(
        manifest_sha256=expected_output_sha256,
        store=store,
        audit_store_root=audit_store_root,
        execution_id=execution_id,
    )
    if expected_current_bytes is not None:
        try:
            current_bytes = store.manifest_path(execution_id).read_bytes()
        except OSError as exc:
            raise DispatchError(
                "manifest became unreadable before canonical adjudication commit"
            ) from exc
        if current_bytes != expected_current_bytes:
            raise DispatchError("manifest changed before canonical adjudication commit")
    manifest_path = manifest_store.write_manifest(store, execution_id, manifest.to_dict())
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != expected_output_sha256:
        raise DispatchError("canonical manifest write does not match expected output bytes")
    _mirror_manifest_to_audit_store_strict(audit_store_root, execution_id, manifest, evidence)
    close_receipt = _mint_close_receipt(
        resource_ref=resource_ref,
        producer="team-execution",
        run_id=execution_id,
        expected_output_sha256=expected_output_sha256,
        protected_write_intent_sha256=write_intent_sha256,
        predecessor_receipt_sha256=predecessor_receipt_sha256,
    )
    return ManifestTransitionResult(manifest=manifest, close_receipt=close_receipt)


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
    audit_store_root: Path | None = None,
    predecessor_close: Mapping[str, Any] | None = None,
    session_id: str | None = None,
) -> pm.Manifest | ManifestTransitionResult:
    """Persist evidence-only output or CAS a canonical Team Execution claim transition."""
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
    canonical = (predecessor_close, session_id)
    if any(value is not None for value in canonical):
        if predecessor_close is None or session_id is None or audit_store_root is None:
            raise DispatchError(
                "canonical manifest claim requires predecessor_close, session_id, and "
                "audit_store_root"
            )
        result = _canonical_manifest_transition(
            manifest=manifest,
            store=store,
            execution_id=execution_id,
            evidence=evidence,
            audit_store_root=audit_store_root,
            predecessor_close=predecessor_close,
            session_id=session_id,
            transition_kind="claim",
        )
        evidence.provenance["manifest_gate_eligibility"] = "canonical"
        evidence.provenance["manifest_close_receipt"] = result.close_receipt
        return result
    evidence.provenance["manifest_gate_eligibility"] = "noncanonical"
    evidence.provenance["manifest_gate_reason"] = "legacy manifest write has no close-receipt chain"
    manifest_store.write_noncanonical_manifest(store, execution_id, manifest.to_dict())
    _mirror_manifest_to_audit_store(audit_store_root, execution_id, manifest, evidence)
    return manifest


def adjudicate_manifest(
    store: manifest_store.Store,
    execution_id: str,
    adjudications: dict[tuple[str, str], tuple[pm.AdjudicatedStatus, pm.Adjudication]],
    *,
    audit_store_root: Path | None = None,
    predecessor_close: Mapping[str, Any] | None = None,
    session_id: str | None = None,
) -> pm.Manifest | ManifestTransitionResult:
    """Write Claude's adjudication layer onto a persisted claimed-only manifest (D5/R6).

    ``adjudications`` maps ``(claim text, source_ref)`` → (adjudicated status, attested
    adjudication record). The key includes ``source_ref`` so two claims sharing text but
    grounded in different sources can be adjudicated independently — text alone is not
    unique within a manifest. Called by the driving session only — never by an engine
    adapter. Claims not named keep their claimed-only state (mismatch_reason
    ``not-adjudicated`` when read by the gate).
    """

    def build_adjudicated(manifest: pm.Manifest) -> pm.Manifest:
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
        return pm.Manifest(
            execution_id=manifest.execution_id,
            saga_ref=manifest.saga_ref,
            attribution=manifest.attribution,
            disposition=manifest.disposition,
            disposition_note=manifest.disposition_note,
            created_at=manifest.created_at,
            output_completeness=manifest.output_completeness,
            claim_provenance=pm.ClaimProvenance(claims=tuple(updated_claims)),
            economics=manifest.economics,
            bridge_run_key=manifest.bridge_run_key,
            tripwire_note=manifest.tripwire_note,
        )

    def read_canonical_source() -> tuple[pm.Manifest, bytes]:
        """Capture and validate the exact source bytes for the adjudication CAS."""
        try:
            source_bytes = store.manifest_path(execution_id).read_bytes()
        except FileNotFoundError as exc:
            raise DispatchError(
                f"no manifest to adjudicate for execution_id={execution_id!r}"
            ) from exc
        except OSError as exc:
            raise DispatchError(
                f"manifest is unreadable for execution_id={execution_id!r}"
            ) from exc
        try:
            raw = json.loads(source_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise DispatchError(f"manifest is malformed for execution_id={execution_id!r}") from exc
        if not isinstance(raw, dict):
            raise DispatchError(f"manifest is malformed for execution_id={execution_id!r}")
        return pm.Manifest.from_dict(raw), source_bytes

    canonical = (predecessor_close, session_id)
    if any(value is not None for value in canonical):
        if predecessor_close is None or session_id is None or audit_store_root is None:
            raise DispatchError(
                "canonical manifest adjudication requires predecessor_close, session_id, and "
                "audit_store_root"
            )
        # One source snapshot supplies both the derived output and the byte-level CAS.
        source_manifest, expected_current_bytes = read_canonical_source()
        adjudicated = build_adjudicated(source_manifest)

        return _canonical_manifest_transition(
            manifest=adjudicated,
            store=store,
            execution_id=execution_id,
            evidence=None,
            audit_store_root=audit_store_root,
            predecessor_close=predecessor_close,
            session_id=session_id,
            transition_kind="adjudication",
            expected_current_bytes=expected_current_bytes,
        )
    raw = manifest_store.read_noncanonical_manifest(store, execution_id)
    if raw is None:
        raise DispatchError(f"no manifest to adjudicate for execution_id={execution_id!r}")
    adjudicated = build_adjudicated(pm.Manifest.from_dict(raw))
    manifest_store.write_noncanonical_manifest(store, execution_id, adjudicated.to_dict())
    _mirror_manifest_to_audit_store(audit_store_root, execution_id, adjudicated, evidence=None)
    return adjudicated


def satisfy_gate(
    evidence: AdvisoryEvidence,
    manifest: pm.Manifest | None = None,
    *,
    reconciliation: reconcile.ReconciliationResult | None = None,
    ledger: run_ledger.RunLedger | None = None,
    store: manifest_store.Store | None = None,
    audit_store_root: Path | None = None,
    manifest_close_receipt: Mapping[str, Any] | None = None,
) -> None:
    """Require complete reconciliation and Claude verification before evidence satisfies a gate.

    Issue #393 adds a first prerequisite: every source finding must appear in a typed
    reconciliation result. This check deliberately runs before the existing authority checks; it
    only closes an evidence-completeness gap and does not replace or relax any prior refusal.

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

    Bridge liveness (#388 U5): when the gate caller has both the run ledger and manifest store,
    the producer/consumer bridge-run join must be contradiction-free. A launched run that was never
    consumed, or a consumed manifest whose run was never launched, blocks the gate.

    Advisory-reviewer refusal (#382): reviewer-role external evidence is report-only. Even when
    Claude verifies the evidence and the observer corroborates the run, it cannot satisfy a gate or
    move Team Execution consensus threshold math.
    """
    if reconciliation is None:
        raise DispatchError("a typed reconciliation result is required before satisfying a gate")
    try:
        reconciliation.require_ready()
    except reconcile.ReconciliationError as exc:
        raise DispatchError(f"reconciliation is not ready: {exc}") from exc
    replay_key = (
        evidence.execution_id,
        reconciliation.reconciliation_id,
        evidence.evidence_digest,
        reconcile.canonical_result_hash(reconciliation),
    )
    if replay_key in _SATISFIED_RECONCILIATIONS:
        raise DispatchError(
            "reconciliation replay: this evidence/result pair already satisfied a gate"
        )
    if not evidence.execution_id:
        raise DispatchError("gate evidence is missing its authoritative dispatch execution_id")
    if reconciliation.execution_id != evidence.execution_id:
        raise DispatchError("reconciliation execution_id does not match dispatched evidence")
    if reconciliation.intent != evidence.intent:
        raise DispatchError("reconciliation intent does not match dispatched evidence")
    if reconciliation.recipe_id != reconcile.recipe_for_intent(evidence.intent).recipe_id:
        raise DispatchError("reconciliation recipe does not match the canonical dispatch intent")
    if reconciliation.evidence_digest != evidence.evidence_digest:
        raise DispatchError("reconciliation evidence digest does not match dispatched evidence")
    if evidence.evidence and not reconciliation.items:
        raise DispatchError("non-empty dispatched evidence cannot use an empty reconciliation")
    if reconciliation.source_finding_ids != evidence.source_finding_ids:
        raise DispatchError("reconciliation source findings do not match dispatched evidence")
    if manifest is not None and manifest.execution_id != evidence.execution_id:
        raise DispatchError("manifest execution_id does not match dispatched evidence")
    if evidence.role_kind in NON_GATING_ROLE_KINDS:
        raise DispatchError(
            f"{evidence.role_kind} evidence is advisory-only and can never satisfy a gate"
        )
    if "rejected_offload_note" in evidence.provenance:
        raise DispatchError(
            "rejected-offload evidence is advisory reviewer/validator signal and can never "
            f"satisfy a gate: {evidence.provenance['rejected_offload_note']}"
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
    if manifest is not None and manifest.disposition is pm.Disposition.REJECTED_OFFLOAD:
        raise DispatchError(
            "rejected-offload evidence is advisory reviewer/validator signal and can never "
            f"satisfy a gate: {manifest.disposition_note}"
        )
    proof_errors = _proof_integrity_problems(evidence)
    if proof_errors:
        raise DispatchError(
            "proof-integrity failure can never satisfy a gate (#388): " + "; ".join(proof_errors)
        )
    if manifest is not None and manifest.disposition is pm.Disposition.PROOF_INTEGRITY:
        raise DispatchError(
            "proof-integrity failure can never satisfy a gate (#388): the "
            f"manifest disposition is {manifest.disposition.value!r} -- "
            f"{manifest.disposition_note}"
        )
    if ledger is not None and store is None:
        raise DispatchError(
            "bridge liveness gate requires a manifest store beside the run ledger (#388)"
        )
    if ledger is not None and store is not None:
        liveness_errors = bridge_liveness_errors(
            ledger,
            store,
            expected_keys=_gate_bridge_keys(evidence, manifest),
        )
        if liveness_errors:
            raise DispatchError("bridge liveness failure (#388): " + "; ".join(liveness_errors))
    if manifest is None:
        if "manifest_gate_eligibility" in evidence.provenance:
            raise DispatchError(
                "recorded manifest evidence must be supplied to the gate with its canonical proof"
            )
        _SATISFIED_RECONCILIATIONS.add(replay_key)
        return
    if evidence.provenance.get("manifest_gate_eligibility") != "canonical":
        raise DispatchError("noncanonical manifest evidence is explicitly unable to satisfy a gate")
    if manifest.claim_provenance is not None:
        for claim in manifest.claim_provenance.claims:
            if claim.adjudicated is None or claim.adjudication is None:
                raise DispatchError(
                    "gated verdict requires Claude-adjudicated claims (R11): "
                    f"claim {claim.text!r} is producer-claimed only"
                )
    if manifest_close_receipt is None or store is None or audit_store_root is None:
        raise DispatchError(
            "canonical manifest gating requires its store, audit root, and terminal close receipt"
        )
    close = dict(manifest_close_receipt)
    resource_ref = _engine_resource_ref(manifest.execution_id, "manifest-gate")
    # Structural + self-authenticating receipt proof (#677/U3): the broker resource-head
    # consultation is retired with the broker; the receipt's own digest re-derivation is the proof.
    _validate_predecessor_close(
        close,
        resource_ref=resource_ref,
        expected_producer="team-execution",
        run_id=manifest.execution_id,
        binding="manifest gate close receipt",
    )
    manifest_bytes = _serialized_manifest_bytes(manifest)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    persisted_path = store.manifest_path(manifest.execution_id)
    try:
        persisted_bytes = persisted_path.read_bytes()
    except OSError as exc:
        raise DispatchError(f"canonical manifest output is unreadable: {exc}") from exc
    if persisted_bytes != manifest_bytes:
        raise DispatchError("canonical manifest store bytes do not match the gated manifest")
    write_intent_sha256 = _manifest_write_intent_sha256(
        manifest_sha256=manifest_sha256,
        store=store,
        audit_store_root=audit_store_root,
        execution_id=manifest.execution_id,
    )
    if (
        close.get("expected_output_sha256") != manifest_sha256
        or close.get("protected_write_intent_sha256") != write_intent_sha256
    ):
        raise DispatchError(
            "manifest close receipt does not bind the exact output and write intent"
        )
    audit_store, audit_degradation = _load_fleet_module("audit_store")
    if audit_store is None:
        raise DispatchError(
            f"canonical manifest gate requires fleet-core audit_store: {audit_degradation}"
        )
    audit_manifest = audit_store.resolve_manifest(
        audit_store.Store.for_root(audit_store_root), manifest.execution_id
    )
    if audit_manifest != manifest.to_dict():
        raise DispatchError("canonical manifest audit mirror does not match the gated manifest")
    _SATISFIED_RECONCILIATIONS.add(replay_key)


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
    role_kind: str = "worker",
) -> dict[str, Any]:
    # Transport-keyed branch (KTD1): a row carrying http-transport invocation data dispatches
    # through the generic bridge; the cli arm keeps the existing codex/agy builders unchanged.
    row = resolution.invocation or {}
    if row.get("via") == "engine-bridge-http":
        return build_http_invocation(resolution)
    if resolution.engine_id == "codex":
        return build_codex_invocation(resolution, sandbox=sandbox, role_kind=role_kind)
    if resolution.engine_id == "agy":
        return build_agy_envelope(
            resolution,
            model=model,
            sandbox=sandbox,
            write_set=write_set,
            role_kind=role_kind,
        )
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


def _validate_role_kind(role_kind: str) -> None:
    if role_kind not in engine_resolver.ROLE_KINDS:
        raise DispatchError(f"role_kind {role_kind!r} not in {engine_resolver.ROLE_KINDS}")


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
