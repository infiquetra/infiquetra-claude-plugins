#!/usr/bin/env python3
"""Reversibility certificate authority — the one authority for reversibility-gated autonomous writes.

A pure-data allowlist registry that declares an operation's reversibility facts and answers a
single ``authorize_write`` verdict (``AUTHORIZED`` / ``GATE``, **default GATE**).  The verdict is
closed by construction — no "probably fine" branch, no solver.

House pattern (mirrors the other ``outcome_*`` modules): pure functions over explicit values,
lazy imports only if needed, no I/O at import.

Design points:
* ``OpKind`` is a frozen string-constant enum mirroring mission-control verbs (KTD2).
* Inverses are declared *declaratively* as data — not as callables — keeping the authority
  pure and golden-testable (KTD3).
* ``authorize_write`` gates any op that is not explicitly enumerated, or is ``ALWAYS_OPERATOR``,
  or is merge/deploy (absent from the registry) — default GATE (R3/R7/R8/R20).
* This module is dead-wired until U4 makes it a live producer+consumer (KTD8).
* #449: the ``AUTONOMOUS_UNDER_ENVELOPE`` tier (sole member: ``MERGE_UNDER_ENVELOPE``) is
  **inert through** ``authorize_write`` — it can only be AUTHORIZED via the sibling
  :func:`authorize_write_under_envelope`, and only when a fresh envelope-token check
  (``envelope_token.check_token`` / ``resolve_merge_token`` — re-read from disk at
  authorization time, never cached) is valid AND the caller attests every other required
  gate is green. Bare ``merge`` / ``deploy`` strings stay absent from the registry: R20's
  default-GATE for every caller that presents no token is unchanged (#449 R2/R6/R7).

Requirement traceability: R1–R9, R20; KTD1–KTD4, KTD8; #449 R1–R2.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Verdict constants
# ---------------------------------------------------------------------------


class Verdict(StrEnum):
    """The two possible authorize_write outcomes."""

    AUTHORIZED = "AUTHORIZED"
    GATE = "GATE"


AUTHORIZED = Verdict.AUTHORIZED
GATE = Verdict.GATE


# ---------------------------------------------------------------------------
# Op kind — enumerated allowlist (KTD2)
# ---------------------------------------------------------------------------


# Project fields saga may submit as a correction through mission-control ``flow set-field``.
# Status is the live field on Operations / Asgard / CAMPPS. Stage is allowed *by name* so a
# future Stage field can reuse this seam; no Stage field exists today and no ``set-field-stage``
# op-kind is created (#812, S3-repaired: Status-only against the live board schema).
CORRECTION_FIELDS = frozenset({"Status", "Stage"})


class OpKind(StrEnum):
    """Canonical names for mission-control operations, mirroring mission-control verbs.

    The registry is a *closed* allowlist: anything not named here returns GATE by default-deny.
    Merge, deploy, and repo-level mutations are intentionally absent (R20).
    """

    SET_FIELD_STATUS = "set-field-status"
    ISSUE_LABEL_ADD = "issue-label-add"
    ISSUE_LABEL_REMOVE = "issue-label-remove"
    SUB_ISSUE_CLOSE = "sub-issue-close"
    SUB_ISSUE_REOPEN = "sub-issue-reopen"
    ISSUE_PROGRESS_COMMENT = "issue-progress-comment"
    PARENT_ISSUE_CLOSE = "parent-issue-close"
    # issue #347 U3 (KTD7): the certificate authority for ship_teardown.reclaim's
    # merged-worktree removal. Reversible — a merged-only reclaim leaves the branch/
    # commit on origin/main, so the worktree can be re-created via ``git worktree add``.
    WORKTREE_RECLAIM_MERGED = "worktree-reclaim-merged"
    # #449: the envelope-authorized merge write class. NOT part of the base allowlist a
    # caller gets for free — ``authorize_write`` always GATEs it (its tier is neither
    # reversible nor additive); only ``authorize_write_under_envelope`` with a valid,
    # unexpired, unrevoked merge-scope envelope token can AUTHORIZE it. Bare "merge" /
    # "deploy" remain absent (R20 unchanged for every tokenless caller).
    MERGE_UNDER_ENVELOPE = "merge-under-envelope"


# ---------------------------------------------------------------------------
# Tier constants
# ---------------------------------------------------------------------------


class Tier(StrEnum):
    """Reversibility tier for an operation."""

    REVERSIBLE = "reversible"  # Registered inverse exists; can be undone.
    ADDITIVE = "additive"  # Append-only; abort-cost bounded; no inverse.
    ALWAYS_OPERATOR = "always_operator"  # Gates even if otherwise reversible.
    # #449: authorized ONLY through authorize_write_under_envelope with a live token
    # check — authorize_write itself always GATEs this tier (inert without a token).
    AUTONOMOUS_UNDER_ENVELOPE = "autonomous_under_envelope"


# ---------------------------------------------------------------------------
# Inverse descriptor (KTD3)
# ---------------------------------------------------------------------------


class InverseDescriptor:
    """Declarative inverse: the inverse OpKind and how to derive its args.

    This is a *data* declaration, not a callable.  The authority asserts the inverse exists;
    executing a rollback is the consumer's responsibility.
    """

    __slots__ = ("op_kind", "arg_derivation")

    def __init__(self, op_kind: OpKind, arg_derivation: str) -> None:
        self.op_kind = op_kind
        self.arg_derivation = arg_derivation  # human-readable recipe for deriving args

    def __repr__(self) -> str:
        return (
            f"InverseDescriptor(op_kind={self.op_kind!r}, arg_derivation={self.arg_derivation!r})"
        )


# ---------------------------------------------------------------------------
# Op facts descriptor
# ---------------------------------------------------------------------------


class OpFacts:
    """Declared facts for a single OpKind entry in the registry.

    Attributes:
        op_kind:         The canonical operation name.
        tier:            Reversibility tier.
        inverse:         ``InverseDescriptor`` for reversible ops; ``None`` for additive/always-op.
        abort_cost:      Human-readable bound on the cost of aborting mid-flight (additive ops).
        always_operator: True when GATE is forced regardless of tier (R7).
        key_recipe:      Human-readable idempotency-key recipe (informational; ``idempotency_key``
                         is the canonical computation).
    """

    __slots__ = ("op_kind", "tier", "inverse", "abort_cost", "always_operator", "key_recipe")

    def __init__(
        self,
        op_kind: OpKind,
        tier: Tier,
        inverse: InverseDescriptor | None,
        abort_cost: str | None,
        always_operator: bool,
        key_recipe: str,
    ) -> None:
        self.op_kind = op_kind
        self.tier = tier
        self.inverse = inverse
        self.abort_cost = abort_cost
        self.always_operator = always_operator
        self.key_recipe = key_recipe

    def __repr__(self) -> str:
        return (
            f"OpFacts(op_kind={self.op_kind!r}, tier={self.tier!r}, "
            f"always_operator={self.always_operator!r})"
        )


# ---------------------------------------------------------------------------
# Registry — the closed allowlist (KTD2, KTD3)
# ---------------------------------------------------------------------------

_REGISTRY: dict[OpKind, OpFacts] = {
    # --- Reversible tier (R5) ---
    OpKind.SET_FIELD_STATUS: OpFacts(
        op_kind=OpKind.SET_FIELD_STATUS,
        tier=Tier.REVERSIBLE,
        inverse=InverseDescriptor(
            op_kind=OpKind.SET_FIELD_STATUS,
            arg_derivation="set-field-status to the prior value recorded before this write",
        ),
        abort_cost=None,
        always_operator=False,
        key_recipe="{op_kind}:{repo}#{issue_number}:{field}:{target_state}",
    ),
    OpKind.ISSUE_LABEL_ADD: OpFacts(
        op_kind=OpKind.ISSUE_LABEL_ADD,
        tier=Tier.REVERSIBLE,
        inverse=InverseDescriptor(
            op_kind=OpKind.ISSUE_LABEL_REMOVE,
            arg_derivation="remove the same label that was added",
        ),
        abort_cost=None,
        always_operator=False,
        key_recipe="{op_kind}:{repo}#{issue_number}:{label}",
    ),
    OpKind.ISSUE_LABEL_REMOVE: OpFacts(
        op_kind=OpKind.ISSUE_LABEL_REMOVE,
        tier=Tier.REVERSIBLE,
        inverse=InverseDescriptor(
            op_kind=OpKind.ISSUE_LABEL_ADD,
            arg_derivation="add back the same label that was removed",
        ),
        abort_cost=None,
        always_operator=False,
        key_recipe="{op_kind}:{repo}#{issue_number}:{label}",
    ),
    OpKind.SUB_ISSUE_CLOSE: OpFacts(
        op_kind=OpKind.SUB_ISSUE_CLOSE,
        tier=Tier.REVERSIBLE,
        inverse=InverseDescriptor(
            op_kind=OpKind.SUB_ISSUE_REOPEN,
            arg_derivation="reopen the same sub-issue that was closed (inverse of sub-issue-close)",
        ),
        abort_cost=None,
        always_operator=False,
        key_recipe="{op_kind}:{repo}#{issue_number}:",
    ),
    OpKind.SUB_ISSUE_REOPEN: OpFacts(
        op_kind=OpKind.SUB_ISSUE_REOPEN,
        tier=Tier.REVERSIBLE,
        inverse=InverseDescriptor(
            op_kind=OpKind.SUB_ISSUE_CLOSE,
            arg_derivation="close the same sub-issue again (inverse of sub-issue-reopen)",
        ),
        abort_cost=None,
        always_operator=False,
        key_recipe="{op_kind}:{repo}#{issue_number}:",
    ),
    # issue #347 U3 (KTD7): merged-worktree reclamation. REVERSIBLE — the inverse is
    # re-creating the worktree via ``git worktree add`` from the surviving merged
    # branch/main (a merged-only reclaim never removes the branch or its commits from
    # origin/main). Everything not enumerated here keeps the default-GATE verdict.
    OpKind.WORKTREE_RECLAIM_MERGED: OpFacts(
        op_kind=OpKind.WORKTREE_RECLAIM_MERGED,
        tier=Tier.REVERSIBLE,
        inverse=InverseDescriptor(
            op_kind=OpKind.WORKTREE_RECLAIM_MERGED,
            arg_derivation=(
                "re-create the removed worktree via `git worktree add <path> <branch>` from "
                "the surviving merged branch or main — a merged-only reclaim leaves the branch "
                "and its commits on origin/main, so nothing is lost by the removal"
            ),
        ),
        abort_cost=None,
        always_operator=False,
        key_recipe="{op_kind}:{worktree_path}",
    ),
    # --- Additive tier (R6) ---
    OpKind.ISSUE_PROGRESS_COMMENT: OpFacts(
        op_kind=OpKind.ISSUE_PROGRESS_COMMENT,
        tier=Tier.ADDITIVE,
        inverse=None,  # append-only; no inverse
        abort_cost="one comment posted per coalescing key; cost is bounded and visible",
        always_operator=False,
        key_recipe="issue-progress-comment:{repo}#{issue_number}:{leaf_transition_id}",
    ),
    # --- ALWAYS_OPERATOR tier (R7) ---
    OpKind.PARENT_ISSUE_CLOSE: OpFacts(
        op_kind=OpKind.PARENT_ISSUE_CLOSE,
        tier=Tier.ALWAYS_OPERATOR,
        inverse=None,
        abort_cost=None,
        always_operator=True,
        key_recipe="N/A — never autonomous",
    ),
    # --- AUTONOMOUS_UNDER_ENVELOPE tier (#449 R1) ---
    # A squash-merge has NO registered inverse — it is irreversible, which is exactly why
    # it may only be authorized under an explicit, expiring, revocable envelope token
    # (authorize_write_under_envelope), never through the base allowlist. authorize_write
    # GATEs this entry unconditionally (the tier is neither reversible nor additive).
    OpKind.MERGE_UNDER_ENVELOPE: OpFacts(
        op_kind=OpKind.MERGE_UNDER_ENVELOPE,
        tier=Tier.AUTONOMOUS_UNDER_ENVELOPE,
        inverse=None,
        abort_cost=None,
        always_operator=False,
        key_recipe="merge-under-envelope:{outcome_id}:{subplot_id}:{pr}:{phase}:{token_id}",
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def facts(op_kind: OpKind) -> OpFacts:
    """Return the declared facts for an enumerated op_kind.

    Raises ``KeyError`` for any op_kind not in the registry — callers that need a safe lookup
    should call ``authorize_write`` first (which returns GATE for unenumerated ops).
    """
    return _REGISTRY[op_kind]


def authorize_write(op_kind: str | OpKind) -> Verdict:
    """Return AUTHORIZED or GATE (default GATE) for the given op kind.

    Decision logic — closed allowlist (R3/R7/R8/R20):
      * Anything not enumerated → GATE (default-deny).
      * Any ALWAYS_OPERATOR entry → GATE even if its tier is otherwise reversible.
      * Only enumerated reversible/additive ops that are NOT ALWAYS_OPERATOR → AUTHORIZED.
      * The ``AUTONOMOUS_UNDER_ENVELOPE`` tier (#449) → GATE here, always — no token
        parameter exists on this function by design (#449 R2: zero regression for every
        existing caller); the envelope class flows only through
        :func:`authorize_write_under_envelope`.

    ``op_kind`` may be a string or an ``OpKind`` instance; strings that match no ``OpKind``
    member return GATE without raising.
    """
    # Coerce string → OpKind; non-members return GATE immediately (R8/R20).
    if not isinstance(op_kind, OpKind):
        try:
            op_kind = OpKind(op_kind)
        except ValueError:
            return GATE

    entry = _REGISTRY.get(op_kind)
    if entry is None:
        return GATE  # should not happen after the coerce above, but be defensive

    if entry.always_operator:
        return GATE  # R7: ALWAYS_OPERATOR forces GATE

    if entry.tier in (Tier.REVERSIBLE, Tier.ADDITIVE):
        return AUTHORIZED

    return GATE  # belt-and-suspenders default


def authorize_correction_field(field_name: str) -> Verdict:
    """AUTHORIZE Status and Stage by name; GATE every other project field (#812).

    The field name is part of authorization: a ``set-field-status`` op that names
    Initiative / Objective / anything else is GATE, never a silent write. Stage is
    allowed as a name only — no Stage field exists on the live boards (receipt
    2026-08-25) and no ``set-field-stage`` op-kind is created.
    """
    if field_name in CORRECTION_FIELDS:
        return AUTHORIZED
    return GATE


class EnvelopeAuthorization:
    """One #449 envelope-class authorization verdict — pure data, echoed facts.

    ``authorizing_envelope_id`` / ``token_id`` are populated only on AUTHORIZED, so a
    ledger writer can never attribute a merge to an envelope that did not authorize it.
    """

    __slots__ = ("verdict", "reason", "authorizing_envelope_id", "token_id")

    def __init__(
        self,
        verdict: Verdict,
        reason: str,
        authorizing_envelope_id: str = "",
        token_id: str = "",
    ) -> None:
        self.verdict = verdict
        self.reason = reason
        self.authorizing_envelope_id = authorizing_envelope_id
        self.token_id = token_id

    def to_dict(self) -> dict[str, str]:
        return {
            "verdict": str(self.verdict.value),
            "reason": self.reason,
            "authorizing_envelope_id": self.authorizing_envelope_id,
            "token_id": self.token_id,
        }

    def __repr__(self) -> str:
        return (
            f"EnvelopeAuthorization(verdict={self.verdict!r}, reason={self.reason!r}, "
            f"authorizing_envelope_id={self.authorizing_envelope_id!r}, "
            f"token_id={self.token_id!r})"
        )


def authorize_write_under_envelope(
    op_kind: str | OpKind,
    token_check: Any,
    *,
    other_gates_green: bool,
) -> EnvelopeAuthorization:
    """The #449 envelope-class verdict: AUTHORIZED only under a live token AND green gates.

    This sibling deliberately leaves :func:`authorize_write` untouched (#449 R2/R7) and
    can never WIDEN anything: an op kind whose tier is not ``AUTONOMOUS_UNDER_ENVELOPE``
    GATEs here with a pointer back to ``authorize_write`` — presenting a token alongside
    ``set-field-status`` (or anything else) grants nothing it did not already have.

    Purity contract: this function performs **no I/O**. ``token_check`` must be the
    result of a FRESH ``envelope_token.check_token`` / ``resolve_merge_token`` read made
    by the caller at authorization time (the composed one-call surface is
    ``envelope_token.authorize_merge_under_envelope``) — the token module's re-read is
    what makes revocation effective on the very next call (#449 R3/R4). A stale or
    cached check object defeats that contract; nothing here can detect one, so the
    composed surface is the one consumers should call.

    ``token_check`` may be ``None`` (no token presented → GATE) or an object with
    ``valid``/``reason``/``envelope_id``/``token_id`` attributes. A wrong-TYPED
    ``token_check.valid`` or ``other_gates_green`` is a caller bug and raises —
    never a coerced comparison (fail closed, never enumerate).
    """
    if not isinstance(other_gates_green, bool):
        raise TypeError(
            f"other_gates_green must be a bool, got {type(other_gates_green).__name__} "
            f"{other_gates_green!r} — a truthy stand-in is not an attestation"
        )
    if not isinstance(op_kind, OpKind):
        try:
            op_kind = OpKind(op_kind)
        except ValueError:
            return EnvelopeAuthorization(
                GATE, f"op kind {op_kind!r} is not enumerated — default GATE (R8/R20)"
            )
    entry = _REGISTRY.get(op_kind)
    if entry is None or entry.tier != Tier.AUTONOMOUS_UNDER_ENVELOPE:
        return EnvelopeAuthorization(
            GATE,
            f"op kind {op_kind.value!r} is not an envelope-authorized class — its verdict "
            "belongs to authorize_write; presenting a token widens nothing (#449 R7)",
        )
    if token_check is None:
        return EnvelopeAuthorization(
            GATE,
            "no envelope token presented — merge-class writes GATE by default (R20; "
            "#449 R1: the class is inert without a token)",
        )
    valid = getattr(token_check, "valid", None)
    if not isinstance(valid, bool):
        raise TypeError(
            f"token_check.valid must be a bool, got {type(valid).__name__} {valid!r} — "
            "pass a fresh envelope_token.TokenCheck, nothing looser"
        )
    reason = getattr(token_check, "reason", "")
    if not isinstance(reason, str):
        raise TypeError(f"token_check.reason must be a string, got {reason!r}")
    if not valid:
        return EnvelopeAuthorization(
            GATE, f"envelope token check failed: {reason or 'no reason given'}"
        )
    envelope_id = getattr(token_check, "envelope_id", "")
    token_id = getattr(token_check, "token_id", "")
    if not isinstance(envelope_id, str) or not envelope_id:
        raise TypeError(
            f"a valid token_check must carry a non-empty envelope_id, got {envelope_id!r}"
        )
    if not isinstance(token_id, str) or not token_id:
        raise TypeError(f"a valid token_check must carry a non-empty token_id, got {token_id!r}")
    if not other_gates_green:
        return EnvelopeAuthorization(
            GATE,
            "envelope authorization is necessary but not sufficient — other required "
            "gates are not green (#449 AC2)",
        )
    return EnvelopeAuthorization(
        AUTHORIZED,
        "valid envelope token + all other gates attested green",
        authorizing_envelope_id=envelope_id,
        token_id=token_id,
    )


def side_effected(had_side_effect: bool) -> bool:
    """Instance-fact accessor — a pure function of the explicit value passed in.

    Returns the ``had_side_effect`` fact unchanged; U2 will wire this to ``node.destructive``
    at the call site in ``outcome_dispatcher.degrade_decision``.  The identity is intentional:
    the certificate declares the fact without re-deriving it, which is the seam U2's
    pass-through identity test must prove is load-bearing (KTD5 / R10).
    """
    return had_side_effect


def idempotency_key(
    op_kind: str | OpKind,
    repo: str,
    issue_number: int,
    target_state: str,
    *,
    field: str | None = None,
) -> str:
    """Return a deterministic idempotency key for an autonomous board write (KTD4 / R9).

    Key form:
      set-field-status:     ``"{op_kind}:{repo}#{issue_number}:{field}:{target_state}"``
                            (``field`` defaults to ``Status``; #812 retry identity)
      other reversible/op:  ``"{op_kind}:{repo}#{issue_number}:{target_state}"``
      additive comment:     ``"issue-progress-comment:{repo}#{issue_number}:{target_state}"``
                            where ``target_state`` carries the leaf_transition_id as the coalescing
                            discriminator (so one comment is posted per meaningful leaf transition).

    The ``repo`` qualifier is load-bearing: two leaves whose issues share a number in **different**
    repos (e.g. ``saga#5`` and ``mission-control#5`` — the common case in v1's two-plugin scope) must
    get distinct keys, or one silently skips the other's board write off a colliding ledger entry.

    This function is a pure string recipe — it does **not** write any ledger.  Recording executed
    keys in the board-sync idempotency ledger is U4's responsibility (KTD4).
    """
    op_str = op_kind.value if isinstance(op_kind, OpKind) else str(op_kind)
    if op_str == OpKind.SET_FIELD_STATUS.value:
        field_name = field if field else "Status"
        return f"{op_str}:{repo}#{issue_number}:{field_name}:{target_state}"
    return f"{op_str}:{repo}#{issue_number}:{target_state}"


def reversible_op_kinds() -> list[OpKind]:
    """Return all enumerated OpKinds with tier REVERSIBLE (convenience for golden tests)."""
    return [ok for ok, f in _REGISTRY.items() if f.tier == Tier.REVERSIBLE]


def all_op_kinds() -> list[OpKind]:
    """Return all enumerated OpKinds in the registry."""
    return list(_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Re-exports for callers that want a single import
# ---------------------------------------------------------------------------

__all__ = [
    "OpKind",
    "Tier",
    "Verdict",
    "AUTHORIZED",
    "GATE",
    "CORRECTION_FIELDS",
    "InverseDescriptor",
    "OpFacts",
    "EnvelopeAuthorization",
    "facts",
    "authorize_write",
    "authorize_correction_field",
    "authorize_write_under_envelope",
    "side_effected",
    "idempotency_key",
    "reversible_op_kinds",
    "all_op_kinds",
]


def _self_check() -> None:  # pragma: no cover
    """Quick smoke-test when run as a script."""
    for ok in OpKind:
        v = authorize_write(ok)
        f = _REGISTRY[ok]
        print(f"{ok.value:35s}  tier={f.tier.value:14s}  verdict={v.value}")
    print()
    k1 = idempotency_key("set-field-status", "infiquetra/saga", 279, "In-Progress")
    k2 = idempotency_key("set-field-status", "infiquetra/saga", 279, "Done")
    k3 = idempotency_key("set-field-status", "infiquetra/saga", 280, "In-Progress")
    print(f"key 279/In-Progress : {k1}")
    print(f"key 279/Done        : {k2}")
    print(f"key 280/In-Progress : {k3}")
    assert k1 != k2, "different target_state must differ"
    assert k1 != k3, "different issue_number must differ"
    print("\nself-check PASSED")


if __name__ == "__main__":
    _self_check()
