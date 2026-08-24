#!/usr/bin/env python3
"""Mid-run posture renegotiation for ``/outcome`` — the ``repost``/``set_intent`` verb (#433).

An outcome campaign captures posture once at ``start`` (#380: the committed intent envelope;
per-node ``degrade_policy``/``sandbox``) and, until this module, had no supported way to change
it mid-run — ``outcome.set_intent`` explicitly refuses to overwrite a committed envelope. This
module is that renegotiation path: ONE verb, reusing the existing atomic mutation shape
(snapshot -> validate -> ``bump_revision`` -> ``decision_trail``, mirroring
``OutcomeSpec.redirect_dependency``), never a family of ad hoc posture setters and never a
second posture vocabulary — campaign posture IS the #380 envelope (``run_mode`` +
``ceremony_gates``), node posture IS the existing ``degrade_policy``/``sandbox`` fields.

The four contract facets (issue #433):

* **Atomic repost (R1/R2)** — :func:`repost` applies the change set to a deep-copied snapshot,
  validates it, and only then mutates the real spec + bumps ``spec_revision`` + appends one
  structured ``decision_trail`` entry. A rejected repost raises :class:`RepostError` and leaves
  ``spec_revision``, ``decision_trail``, and every posture field byte-identical (no partial
  mutation — the R26 invariant).
* **Overlap-safe amendment (R4/R5/R6)** — every repost tags the spec with ``intent_revision``
  (the revision it introduced); each leaf's dispatch record captures the ``intent_revision`` +
  posture (including the campaign envelope) active at its dispatch (written by
  ``outcome._reconcile_once``). An in-flight leaf finishes under its dispatch-time posture —
  dispatch AND completion: the harvest/closure-gate seam evaluates an in-flight leaf's
  intent-implied checks against its dispatch-era envelope, never against a later loosening; a
  pending leaf picks the new posture up at its next dispatch. A repost that would *strand* an
  in-flight leaf's irreversible-op authorization (a ``destructive`` leaf whose node-scoped
  sandbox would tighten mid-flight — where "in flight" fail-closed includes a bare
  intent-phase dispatch record, the mid-dispatch window) HALTs the campaign instead: the
  amendment is rejected (spec untouched), ONE ``coordinator`` ``andon_halt`` lands in the
  #372 adjustment envelope append-once (the next advance tick stops dispatching), and ONE
  durable ledger record (append-once on ``(phase, key)``) names the stranded leaf — no silent
  resolution in either direction, no directive pile-up on repeats.
* **Monotonic merge/deploy gating (R7)** — ``ceremony_gates.merge`` / ``deploy_nonprod`` (the
  campaign's merge/deploy gate posture) may only move toward MORE gating (``auto`` ->
  ``gate``). Any repost moving either from gated toward autonomous is rejected outright — and
  the sibling ``set-intent`` verb enforces the SAME rule on a live campaign
  (:func:`validate_live_attach`): once any dispatch record exists, a first envelope attach
  carrying ``merge``/``deploy_nonprod: "auto"`` is rejected against the effective
  default-gated posture, so the rule has no second-verb side door (AC5). One-directional by
  design: reverting a mistaken tightening takes a new campaign.
* **Loosening re-closes the frontier (R3)** — every repost bumps ``spec_revision``, and the R20
  approval gate is revision-keyed, so the frontier approval is consumed automatically. A repost
  that ONLY tightens carries the prior revision's approval forward (a new approval record with
  carried-forward provenance); a repost with any loosening delta does not — affected leaves stay
  gated until the operator re-approves.

Direction vocabulary (what counts as tighten vs. loosen) is CLOSED and total per axis, except
one documented conservative case: the two isolated ``workspace_isolation`` values
(``disposable-worktree`` / ``owned-worktree``) are mutually incomparable, so a move between
them is classified **loosen** — the conservative reading costs at most one extra re-approval
and can never skip one.

Threat model / self-attestation: ``reason`` and the carried-forward approval provenance are
self-attested operator input — this module validates the *shape and direction* of a posture
change, not the *authority* of whoever invoked the CLI (the same stance as the #372 envelope
and the #380 provenance fields).

House pattern (mirrors ``outcome_spec`` / ``adjustment_envelope``): pure functions over
explicit values, no I/O at import, injectable store/paths so the whole contract is
unit-testable offline.
"""

from __future__ import annotations

import copy
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import adjustment_envelope  # noqa: E402  (after the sys.path shim, by design)
import intent_envelope  # noqa: E402
import outcome_spec  # noqa: E402
import outcome_store  # noqa: E402

# Directions (closed). Every accepted delta is classified as exactly one of these.
TIGHTEN = "tighten"
LOOSEN = "loosen"

# The renegotiable posture fields (closed vocabularies — an unknown field is an error, never a
# pass). Campaign fields live on the #380 intent envelope; node fields on the Node itself.
CAMPAIGN_FIELDS = ("run_mode", "reviews_required", "merge", "deploy_nonprod")
NODE_FIELDS = ("degrade_policy", "sandbox")
# R7: these gates are monotonic-toward-more-gating — a loosening repost is rejected outright.
MONOTONIC_FIELDS = frozenset({"merge", "deploy_nonprod"})

# Per-axis "more gated" orderings. Higher = more gated/tighter.
_GATE_ORDER = {intent_envelope.AUTO: 0, intent_envelope.GATE: 1}
_RUN_MODE_ORDER = {intent_envelope.UNATTENDED: 0, intent_envelope.ATTENDED: 1}
_DEGRADE_ORDER = {"none": 0, "operator_away_one_rung": 1, "halt": 2}
_MUTATION_ORDER = {"read-write": 0, "read-only": 1}
# workspace_isolation: ambient is strictly the loosest; the two isolated values are mutually
# incomparable (see module docstring) — a move between them classifies LOOSEN conservatively.
_ISOLATION_ORDER = {"ambient": 0, "disposable-worktree": 1, "owned-worktree": 1}

# The effective posture of a campaign with NO committed envelope: every ceremony gate defaults
# to GATE (CeremonyGates defaults) and run_mode reads attended — the same baseline
# ``intent_envelope.seeded_tier`` assumes for an intent-less spec.
_NO_ENVELOPE_RUN_MODE = intent_envelope.ATTENDED

# The default (widest) sandbox a node with no declared sandbox runs under — mirrored from
# outcome_spec's documented "absent => ambient x read-write" contract.
_DEFAULT_SANDBOX = ("read-write", "ambient")


class RepostError(ValueError):
    """A rejected repost — the spec is left byte-identical to its pre-repost state (R2)."""


class RepostStrandedError(RepostError):
    """The repost would strand an in-flight leaf's irreversible-op authorization (R6).

    The campaign HALTs: the amendment is NOT applied (spec untouched), a ``coordinator``
    ``andon_halt`` is written to the adjustment envelope (the next advance tick stops
    dispatching), and a durable ledger record names the stranded leaf. Carries the receipt.
    """

    def __init__(self, receipt: dict[str, Any]) -> None:
        super().__init__(str(receipt.get("reason", "stranded irreversible-op authorization")))
        self.receipt = receipt


@dataclass(frozen=True)
class PostureDelta:
    """One accepted posture change on one axis, with its tighten/loosen classification."""

    field: str  # "run_mode" | "reviews_required" | "merge" | "deploy_nonprod" |
    # "degrade_policy" | "sandbox.mutation_policy" | "sandbox.workspace_isolation"
    scope: str  # "" = campaign-wide; else the subplot_id the change is scoped to
    old: str
    new: str
    direction: str  # TIGHTEN | LOOSEN

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "scope": self.scope,
            "old": self.old,
            "new": self.new,
            "direction": self.direction,
        }


@dataclass(frozen=True)
class RepostResult:
    """The committed outcome of one accepted repost."""

    outcome_id: str
    spec_revision: int  # the NEW revision the repost introduced
    intent_revision: int  # == spec_revision (R4: the posture tag names its own revision)
    deltas: tuple[PostureDelta, ...]
    loosened: bool  # any delta loosened a gate -> the frontier approval was re-closed (R3)
    prior_frontier_approved: bool  # was the pre-repost revision's frontier approved?
    approval_carried_forward: bool  # pure-tightening repost re-approved the new revision
    reapproval_required: bool  # the operator must re-approve before gated leaves dispatch

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "spec_revision": self.spec_revision,
            "intent_revision": self.intent_revision,
            "deltas": [d.to_dict() for d in self.deltas],
            "loosened": self.loosened,
            "prior_frontier_approved": self.prior_frontier_approved,
            "approval_carried_forward": self.approval_carried_forward,
            "reapproval_required": self.reapproval_required,
        }


# ---------------------------------------------------------------------------
# Effective posture + direction classification
# ---------------------------------------------------------------------------


def effective_envelope(spec: Any) -> intent_envelope.IntentEnvelope:
    """The campaign posture in force: the committed envelope, else the documented defaults.

    A campaign with no committed intent runs attended with every ceremony gate at GATE — the
    fail-safe baseline. This means a repost against an envelope-less campaign compares against
    GATED defaults, so e.g. ``merge=auto`` is a loosening from gated and is rejected (R7).
    """
    if getattr(spec, "intent", None):
        return intent_envelope.IntentEnvelope.from_dict(spec.intent)
    return intent_envelope.IntentEnvelope(
        run_mode=_NO_ENVELOPE_RUN_MODE,
        ceremony_gates=intent_envelope.CeremonyGates(),
        source="defaults:no-committed-envelope",
    )


def effective_sandbox(node: Any) -> tuple[str, str]:
    """A node's ``(mutation_policy, workspace_isolation)`` in force (absent => the wide default)."""
    sandbox = getattr(node, "sandbox", None)
    if sandbox is None:
        return _DEFAULT_SANDBOX
    return (sandbox.mutation_policy, sandbox.workspace_isolation)


def _classify(order: Mapping[str, int], field: str, old: str, new: str) -> str:
    """TIGHTEN/LOOSEN by the axis ordering. Equal rank but different value => LOOSEN (conservative)."""
    old_rank, new_rank = order[old], order[new]
    if new_rank > old_rank:
        return TIGHTEN
    if new_rank < old_rank:
        return LOOSEN
    # Same rank, different value: the incomparable isolation pair. Conservative: LOOSEN — the
    # misclassification cost is one extra re-approval, never a skipped one.
    return LOOSEN


def _require_vocab(field: str, value: str, vocab: tuple[str, ...]) -> None:
    if value not in vocab:
        raise RepostError(f"repost: {field}={value!r} is not in the closed vocabulary {vocab}")


def _parse_sandbox_value(value: str) -> outcome_spec.Sandbox:
    """Parse a repost sandbox value: a known profile, or ``<mutation_policy>:<isolation>``."""
    if value in outcome_spec.SANDBOX_PROFILES:
        mutation_policy, workspace_isolation = outcome_spec.SANDBOX_PROFILES[value]
        return outcome_spec.Sandbox(mutation_policy, workspace_isolation)
    if ":" in value:
        mutation_policy, _, workspace_isolation = value.partition(":")
        sandbox = outcome_spec.Sandbox(mutation_policy, workspace_isolation)
        try:
            sandbox.validate("repost sandbox")
        except outcome_spec.OutcomeSpecError as exc:
            raise RepostError(f"repost: {exc}") from exc
        return sandbox
    raise RepostError(
        f"repost: sandbox={value!r} is neither a known profile "
        f"{tuple(outcome_spec.SANDBOX_PROFILES)} nor '<mutation_policy>:<workspace_isolation>'"
    )


def _validate_changes(changes: Mapping[str, Any], scope: str, spec: Any) -> dict[str, str]:
    """Strictly validate the change set's SHAPE (fail closed, R2). Returns str->str changes."""
    if not isinstance(changes, Mapping) or not changes:
        raise RepostError("repost: needs a non-empty {field: value} change set")
    allowed = NODE_FIELDS if scope else CAMPAIGN_FIELDS
    where = f"scope {scope!r}" if scope else "campaign scope"
    out: dict[str, str] = {}
    for field, value in changes.items():
        if field not in allowed:
            raise RepostError(
                f"repost: unknown field {field!r} for {where} — the vocabulary is closed "
                f"({list(allowed)}); a field this module cannot model is an error, not a pass"
            )
        if not isinstance(value, str) or not value:
            # Value-type strictness: a bool/int/None here is an authoring error, never coerced.
            raise RepostError(
                f"repost: {field} must be a non-empty string, got {type(value).__name__} {value!r}"
            )
        out[field] = value
    if scope and spec.node_by_id(scope) is None:
        raise RepostError(f"repost: scope {scope!r} names no declared subplot")
    return out


def compute_deltas(spec: Any, changes: Mapping[str, str], scope: str) -> tuple[PostureDelta, ...]:
    """Classify every proposed change against the posture currently in force.

    Fails closed on an off-vocabulary value and on a no-op (a value equal to the one already in
    force changes nothing — a silent bump would fabricate a decision-trail entry, R2).
    """
    deltas: list[PostureDelta] = []
    if not scope:
        envelope = effective_envelope(spec)
        current = {
            "run_mode": envelope.run_mode,
            "reviews_required": envelope.ceremony_gates.reviews_required,
            "merge": envelope.ceremony_gates.merge,
            "deploy_nonprod": envelope.ceremony_gates.deploy_nonprod,
        }
        orders: dict[str, Mapping[str, int]] = {
            "run_mode": _RUN_MODE_ORDER,
            "reviews_required": _GATE_ORDER,
            "merge": _GATE_ORDER,
            "deploy_nonprod": _GATE_ORDER,
        }
        vocabs: dict[str, tuple[str, ...]] = {
            "run_mode": tuple(intent_envelope.RUN_MODES),
            "reviews_required": tuple(intent_envelope.GATE_SETTINGS),
            "merge": tuple(intent_envelope.GATE_SETTINGS),
            "deploy_nonprod": tuple(intent_envelope.GATE_SETTINGS),
        }
        for field, new in changes.items():
            _require_vocab(field, new, vocabs[field])
            old = current[field]
            if new == old:
                raise RepostError(
                    f"repost: {field}={new!r} is already the posture in force — a no-op repost "
                    f"would bump the revision and fabricate a trail entry; nothing to change"
                )
            deltas.append(
                PostureDelta(
                    field=field,
                    scope="",
                    old=old,
                    new=new,
                    direction=_classify(orders[field], field, old, new),
                )
            )
        return tuple(deltas)

    node = spec.node_by_id(scope)
    if "degrade_policy" in changes:
        new = changes["degrade_policy"]
        _require_vocab("degrade_policy", new, outcome_spec.DEGRADE_POLICIES)
        old = node.degrade_policy
        if new == old:
            raise RepostError(
                f"repost: degrade_policy={new!r} is already in force on {scope!r} — nothing to change"
            )
        deltas.append(
            PostureDelta(
                field="degrade_policy",
                scope=scope,
                old=old,
                new=new,
                direction=_classify(_DEGRADE_ORDER, "degrade_policy", old, new),
            )
        )
    if "sandbox" in changes:
        new_sandbox = _parse_sandbox_value(changes["sandbox"])
        old_mutation, old_isolation = effective_sandbox(node)
        axis_deltas: list[PostureDelta] = []
        if new_sandbox.mutation_policy != old_mutation:
            axis_deltas.append(
                PostureDelta(
                    field="sandbox.mutation_policy",
                    scope=scope,
                    old=old_mutation,
                    new=new_sandbox.mutation_policy,
                    direction=_classify(
                        _MUTATION_ORDER,
                        "sandbox.mutation_policy",
                        old_mutation,
                        new_sandbox.mutation_policy,
                    ),
                )
            )
        if new_sandbox.workspace_isolation != old_isolation:
            axis_deltas.append(
                PostureDelta(
                    field="sandbox.workspace_isolation",
                    scope=scope,
                    old=old_isolation,
                    new=new_sandbox.workspace_isolation,
                    direction=_classify(
                        _ISOLATION_ORDER,
                        "sandbox.workspace_isolation",
                        old_isolation,
                        new_sandbox.workspace_isolation,
                    ),
                )
            )
        if not axis_deltas:
            raise RepostError(
                f"repost: sandbox={changes['sandbox']!r} equals the sandbox already in force on "
                f"{scope!r} — nothing to change"
            )
        deltas.extend(axis_deltas)
    return tuple(deltas)


# ---------------------------------------------------------------------------
# R6 — the strand check (overlap-safe amendment's HALT case)
# ---------------------------------------------------------------------------


def _in_flight_dispatch_record(store: Any, subplot_id: str) -> dict[str, Any] | None:
    """The leaf's latest dispatch record iff it is in flight (not yet terminal).

    BOTH dispatch phases count as in flight (fail closed against the R6 TOCTOU): a settled
    ``commit`` record is a live flight, and a bare ``intent`` record — the mid-dispatch
    window where a concurrent tick has declared the dispatch but not yet committed it, or a
    crashed/rate-limited dispatch ``replay_pending`` will re-drive — is treated as in flight
    too. Resolving "mid-dispatch" as "not in flight" would let a tightening repost apply
    cleanly while the leaf launches under the old, wider posture: the exact stranded state R6
    exists to HALT on. The conservative read costs at most one deferred repost (retry after
    the flight settles or is re-driven), never a silently-stranded authorization. A ``commit``
    record wins over its ``intent`` (it carries the dispatch-time posture snapshot).
    """
    record: dict[str, Any] | None = None
    for rec in outcome_store.read_ledger(store):
        if (
            rec.get("kind") == "dispatch"
            and rec.get("phase") in ("intent", "commit")
            and str(rec.get("subplot_id", "")) == subplot_id
        ):
            if (
                record is not None
                and record.get("phase") == "commit"
                and rec.get("phase") == "intent"
            ):
                continue  # keep the settled record: it carries the posture snapshot
            record = rec
    if record is None:
        return None
    # Any terminal completion (done/failed/rejected/stalled) means the flight is over — there
    # is no live authorization left to strand.
    if subplot_id in outcome_store.completed_subplots(store, successful_only=False):
        return None
    return record


def _stranded_receipt(
    spec: Any, store: Any, deltas: tuple[PostureDelta, ...], scope: str
) -> dict[str, Any] | None:
    """The R6 strand receipt, or ``None`` when the repost strands nothing.

    Strand predicate: the repost is scoped to a ``destructive`` leaf (authorized for an
    irreversible operation) that is IN FLIGHT (a dispatch record in either phase — ``commit``,
    or the fail-closed mid-dispatch ``intent`` window — with no terminal completion), and
    at least one delta TIGHTENS that leaf's sandbox — revoking authorization the leaf already
    carried into its own process and cannot be re-issued mid-op. Campaign-scoped fields and
    ``degrade_policy`` govern *future* dispatch AND completion decisions through the
    dispatch-era posture capture (each leaf's commit record pins the envelope in force at its
    dispatch, which the harvest seam reads back), not authorization already in the leaf's
    hands, so they never strand (R5 covers them: dispatch-time posture finishes the flight —
    dispatch and completion gates both; the change lands at the next dispatch). Loosening
    deltas grant authorization and never strand either — the tighter dispatch-time posture
    simply finishes the flight.
    """
    if not scope:
        return None
    node = spec.node_by_id(scope)
    if not getattr(node, "destructive", False):
        return None
    revoking = [d for d in deltas if d.field.startswith("sandbox.") and d.direction == TIGHTEN]
    if not revoking:
        return None
    record = _in_flight_dispatch_record(store, scope)
    if record is None:
        return None
    dispatch_posture = record.get("posture") or {
        "intent_revision": record.get("intent_revision", 1),
        "degrade_policy": node.degrade_policy,
        "mutation_policy": effective_sandbox(node)[0],
        "workspace_isolation": effective_sandbox(node)[1],
    }
    return {
        "kind": "strand-halt",
        "outcome_id": spec.outcome_id,
        "subplot_id": scope,
        "leaf_saga_id": str(record.get("leaf_saga_id", "")),
        "dispatch_posture": dispatch_posture,
        "revoking": [d.to_dict() for d in revoking],
        "reason": (
            f"repost would strand {scope!r}: the leaf is mid-flight with irreversible-op "
            f"authorization (destructive) and the amendment tightens its sandbox — it cannot "
            f"be un-authorized mid-op. The campaign HALTs: the amendment is NOT applied and "
            f"the op is neither silently allowed to proceed under a rejected posture nor "
            f"silently revoked (R6). Resolve: let the leaf finish (or terminate it via its own "
            f"saga), clear the halt, then repost."
        ),
    }


# ---------------------------------------------------------------------------
# The verb — atomic snapshot -> validate -> bump_revision -> decision_trail
# ---------------------------------------------------------------------------


def _apply_changes(target: Any, changes: Mapping[str, str], scope: str, at: str) -> None:
    """Apply an already-validated change set to ``target`` (a spec). Same function drives the
    snapshot validation AND the committed mutation, so the two can never diverge."""
    if scope:
        node = target.node_by_id(scope)
        if "degrade_policy" in changes:
            node.degrade_policy = changes["degrade_policy"]
        if "sandbox" in changes:
            node.sandbox = _parse_sandbox_value(changes["sandbox"])
        return
    envelope = effective_envelope(target)
    gates = envelope.ceremony_gates
    new_envelope = intent_envelope.IntentEnvelope(
        run_mode=changes.get("run_mode", envelope.run_mode),
        ceremony_gates=intent_envelope.CeremonyGates(
            reviews_required=changes.get("reviews_required", gates.reviews_required),
            merge=changes.get("merge", gates.merge),
            deploy_nonprod=changes.get("deploy_nonprod", gates.deploy_nonprod),
        ),
        schema_version=envelope.schema_version,
        source=envelope.source,
        authored_at=envelope.authored_at or at,
        authored_by=envelope.authored_by,
    )
    new_envelope.validate()
    target.intent = new_envelope.to_dict()


def repost(
    spec: Any,
    store: Any,
    *,
    changes: Mapping[str, Any],
    scope: str = "",
    reason: str,
    envelope_path: Path,
    at: str = "",
) -> RepostResult:
    """Renegotiate a live campaign's posture — the single atomic ``repost``/``set_intent`` verb.

    Sequence (R1): validate the change set's shape; classify every delta against the posture in
    force; reject any merge/deploy loosening outright (R7); HALT the campaign on a strand (R6);
    apply the changes to a deep-copied snapshot and ``validate()`` it; only then mutate the real
    spec, ``bump_revision`` (one revision counter), append ONE structured ``decision_trail``
    entry (one trail), and tag ``intent_revision`` (R4). Approval (R3): the revision bump
    re-closes the R20 frontier gate; a pure-tightening repost carries an existing approval
    forward with carried-forward provenance, a loosening one leaves the gate closed.

    On ANY rejection the spec is byte-identical to its pre-repost state (R2). The caller owns
    persistence (``save_spec``) — this function mutates the in-memory spec only.
    """
    if not isinstance(reason, str) or not reason.strip():
        raise RepostError("repost: needs a non-empty --reason recording why posture changed (R1)")
    validated = _validate_changes(changes, scope, spec)
    deltas = compute_deltas(spec, validated, scope)

    # R7 — monotonic merge/deploy gating: reject outright, never silently accept.
    for delta in deltas:
        if delta.field in MONOTONIC_FIELDS and delta.direction == LOOSEN:
            raise RepostError(
                f"repost: {delta.field} may only move toward MORE gating — "
                f"{delta.old!r} -> {delta.new!r} would relax a merge/deploy gate from gated "
                f"toward autonomous, which set_intent rejects outright (R7). Loosening "
                f"merge/deploy posture requires a new campaign, by design."
            )

    # R6 — the strand check: HALT the campaign rather than silently resolve either direction.
    # Both writes are APPEND-ONCE (the same (phase, key) / (writer, scope) parity as the
    # reconcile halt path): a repeated stranded repost re-raises the error every time, but
    # never duplicates the coordinator andon directive or the halt ledger record.
    receipt = _stranded_receipt(spec, store, deltas, scope)
    if receipt is not None:
        adjustment_envelope.raise_strand_halt(
            envelope_path, scope=scope, reason=str(receipt["reason"]), at=at
        )
        outcome_store.append_ledger_once(
            store,
            # receipt first: the ledger identity keys (phase/kind/key) must win the merge so
            # the record is queryable as a repost halt (the receipt's own kind is nested-only).
            # Scoped with a generation component (spec_revision) so repeat attempts at the same
            # revision dedup, but a distinct strand event at a future revision appends a new record (#598).
            {
                **receipt,
                "phase": "halt",
                "kind": "repost",
                "key": f"repost:{scope}:r{spec.spec_revision}",
                "at": at,
            },
        )
        raise RepostStrandedError(receipt)

    # Atomic apply: snapshot first (R2). A change set that breaks any spec invariant is
    # rejected here with the real spec untouched.
    candidate = copy.deepcopy(spec)
    _apply_changes(candidate, validated, scope, at)
    try:
        candidate.validate()
    except outcome_spec.OutcomeSpecError as exc:
        raise RepostError(f"repost rejected: {exc}") from exc

    # Commit: same apply function against the real spec, then ONE revision bump + ONE
    # structured trail entry (mirroring bump_revision's contract — one counter, one trail).
    import outcome_decompose  # noqa: PLC0415  (sibling; deferred, mirrors outcome.py idiom)

    old_revision = spec.spec_revision
    prior_approved = outcome_decompose.frontier_approved(store, old_revision)
    _apply_changes(spec, validated, scope, at)
    scope_label = f" scope={scope}" if scope else ""
    new_revision = spec.bump_revision(reason=f"repost{scope_label}: {reason}", at=at)
    spec.decision_trail[-1].update(
        {
            "kind": "repost",
            "scope": scope,
            "deltas": [d.to_dict() for d in deltas],
            "intent_revision": new_revision,
        }
    )
    spec.intent_revision = new_revision

    loosened = any(d.direction == LOOSEN for d in deltas)
    carried = False
    if not loosened and prior_approved:
        # R3: a pure-tightening repost never reopens a closed gate NOR re-asks a settled
        # approval — carry the operator's r<old> approval to the new revision with explicit
        # carried-forward provenance (frontier_approved is existence-only; the provenance is
        # for the audit trail).
        outcome_decompose.approve_frontier(
            store, spec, at=at, answerer=f"carried-forward:tightening-repost:r{old_revision}"
        )
        carried = True

    return RepostResult(
        outcome_id=spec.outcome_id,
        spec_revision=new_revision,
        intent_revision=new_revision,
        deltas=deltas,
        loosened=loosened,
        prior_frontier_approved=prior_approved,
        approval_carried_forward=carried,
        reapproval_required=not outcome_decompose.frontier_approved(store, new_revision),
    )


def campaign_live(store: Any) -> bool:
    """Whether the campaign is LIVE: ANY dispatch has been declared or settled (#433 AC5).

    Both dispatch phases count — a bare ``intent`` record means a dispatch is mid-flight or
    will be re-driven (``replay_pending``), so posture changes must already clear the
    mid-run rules. Before the first dispatch record the campaign is still at run-start:
    the #380 interview-fallback ``set-intent`` attach may carry any posture.
    """
    return any(
        rec.get("kind") == "dispatch" and rec.get("phase") in ("intent", "commit")
        for rec in outcome_store.read_ledger(store)
    )


def validate_live_attach(spec: Any, envelope_dict: Any) -> tuple[PostureDelta, ...]:
    """AC5 (#433 R7) for the sibling ``set-intent`` verb: a first envelope attach on a LIVE
    campaign is the same semantic transition as a repost against the effective
    (default-gated) posture, so it passes the SAME monotonic validation — one rule, both
    verbs, no side door.

    Computes the envelope's deltas against the no-envelope effective posture (attended,
    every ceremony gate at GATE) and rejects outright any delta that would move a monotonic
    gate (``merge`` / ``deploy_nonprod``) from gated toward autonomous. Returns the
    classified deltas so the caller records them on the decision trail — one verb, one
    revision counter, one trail. Raises :class:`RepostError` on violation; the caller's
    spec is untouched (nothing here mutates).
    """
    envelope = intent_envelope.IntentEnvelope.from_dict(envelope_dict)
    current = effective_envelope(spec)
    changes: dict[str, str] = {}
    for field_name, new, old in (
        ("run_mode", envelope.run_mode, current.run_mode),
        (
            "reviews_required",
            envelope.ceremony_gates.reviews_required,
            current.ceremony_gates.reviews_required,
        ),
        ("merge", envelope.ceremony_gates.merge, current.ceremony_gates.merge),
        (
            "deploy_nonprod",
            envelope.ceremony_gates.deploy_nonprod,
            current.ceremony_gates.deploy_nonprod,
        ),
    ):
        if new != old:
            changes[field_name] = new
    if not changes:
        return ()
    deltas = compute_deltas(spec, changes, "")
    for delta in deltas:
        if delta.field in MONOTONIC_FIELDS and delta.direction == LOOSEN:
            raise RepostError(
                f"set-intent: attaching this envelope to a LIVE campaign would move "
                f"{delta.field} from the effective gated default toward autonomous "
                f"({delta.old!r} -> {delta.new!r}) — rejected outright, the same monotonic "
                f"rule repost enforces (#433 R7/AC5). Attach a gated envelope, or start a "
                f"new campaign for an autonomous merge/deploy posture."
            )
    return deltas


def parse_set_args(sets: list[str]) -> dict[str, str]:
    """Parse repeatable CLI ``--set FIELD=VALUE`` args into a change set (fail closed).

    A token without ``=``, an empty field, or a duplicated field is an error — a change set
    this parser cannot fully model must never silently shrink (R2).
    """
    out: dict[str, str] = {}
    for token in sets:
        field, sep, value = token.partition("=")
        if not sep or not field:
            raise RepostError(f"repost: --set {token!r} is not FIELD=VALUE")
        if field in out:
            raise RepostError(
                f"repost: --set {field!r} given twice ({out[field]!r} and {value!r}) — "
                f"ambiguous; give each field once"
            )
        out[field] = value
    return out
