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

Requirement traceability: R1–R9, R20; KTD1–KTD4, KTD8.
"""

from __future__ import annotations

from enum import StrEnum

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


# ---------------------------------------------------------------------------
# Tier constants
# ---------------------------------------------------------------------------


class Tier(StrEnum):
    """Reversibility tier for an operation."""

    REVERSIBLE = "reversible"  # Registered inverse exists; can be undone.
    ADDITIVE = "additive"  # Append-only; abort-cost bounded; no inverse.
    ALWAYS_OPERATOR = "always_operator"  # Gates even if otherwise reversible.


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
        key_recipe="{op_kind}:{repo}#{issue_number}:{target_state}",
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


def side_effected(had_side_effect: bool) -> bool:
    """Instance-fact accessor — a pure function of the explicit value passed in.

    Returns the ``had_side_effect`` fact unchanged; U2 will wire this to ``node.destructive``
    at the call site in ``outcome_dispatcher.degrade_decision``.  The identity is intentional:
    the certificate declares the fact without re-deriving it, which is the seam U2's
    pass-through identity test must prove is load-bearing (KTD5 / R10).
    """
    return had_side_effect


def idempotency_key(op_kind: str | OpKind, repo: str, issue_number: int, target_state: str) -> str:
    """Return a deterministic idempotency key for an autonomous board write (KTD4 / R9).

    Key form:
      reversible/always-op: ``"{op_kind}:{repo}#{issue_number}:{target_state}"``
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
    "InverseDescriptor",
    "OpFacts",
    "facts",
    "authorize_write",
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
