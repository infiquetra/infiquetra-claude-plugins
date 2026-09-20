#!/usr/bin/env python3
"""The closed allowlist of mission-control operations saga may submit without an operator.

This is the surviving half of `reversibility_certificate.py`, which issue 1030 removed with the
ship-ceremony family. That module carried two things: a **reversibility tiering** -- which
operations were reversible, what their inverse was, what aborting one cost -- and, underneath it, a
**default-deny allowlist** of the operations saga is allowed to submit at all.

The tiering went with the ceremony that consumed it: nothing computes an inverse or an abort cost
any more. The allowlist stays, because it answers a question the lifecycle still asks on every
board write -- *may saga do this one without a human?* -- and because its failure direction is the
one worth keeping: an operation nobody enumerated is refused, not attempted.

Two ops are enumerated and still refused, which is the point of naming them rather than omitting
them. Closing a **parent** issue is always the operator's, because it declares a whole tree of work
finished. Merging was reachable only through the envelope machinery this release removes, so it has
no autonomous path left at all.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["AUTHORIZED", "GATE", "OpKind", "Verdict", "authorize_write"]


class Verdict(StrEnum):
    """What the allowlist says about one operation."""

    AUTHORIZED = "AUTHORIZED"
    GATE = "GATE"


AUTHORIZED = Verdict.AUTHORIZED
GATE = Verdict.GATE


class OpKind(StrEnum):
    """Canonical names for mission-control operations, mirroring mission-control's verbs.

    A closed allowlist: anything not named here is refused by default-deny. Repository-level
    mutations are deliberately absent -- saga never submits one.
    """

    SET_FIELD_STATUS = "set-field-status"
    ISSUE_LABEL_ADD = "issue-label-add"
    ISSUE_LABEL_REMOVE = "issue-label-remove"
    SUB_ISSUE_CLOSE = "sub-issue-close"
    SUB_ISSUE_REOPEN = "sub-issue-reopen"
    ISSUE_PROGRESS_COMMENT = "issue-progress-comment"
    WORKTREE_RECLAIM_MERGED = "worktree-reclaim-merged"
    PARENT_ISSUE_CLOSE = "parent-issue-close"


#: The operations saga may submit on its own. Every one is undoable by a later submission of a
#: member of this same set, which is why it needs no operator and no recorded inverse.
_AUTONOMOUS: frozenset[OpKind] = frozenset(
    {
        OpKind.SET_FIELD_STATUS,
        OpKind.ISSUE_LABEL_ADD,
        OpKind.ISSUE_LABEL_REMOVE,
        OpKind.SUB_ISSUE_CLOSE,
        OpKind.SUB_ISSUE_REOPEN,
        OpKind.ISSUE_PROGRESS_COMMENT,
        OpKind.WORKTREE_RECLAIM_MERGED,
    }
)

#: Enumerated and still the operator's. Named rather than omitted so the refusal reads as a
#: decision: an omitted op is refused by accident, a listed one is refused on purpose.
_OPERATOR_ONLY: frozenset[OpKind] = frozenset({OpKind.PARENT_ISSUE_CLOSE})


def authorize_write(op_kind: str | OpKind) -> Verdict:
    """Return ``AUTHORIZED`` or ``GATE`` for *op_kind*, defaulting to ``GATE``.

    A string that matches no member returns ``GATE`` without raising, so a caller passing a typo or
    a verb from a newer mission-control never writes by accident.
    """
    if not isinstance(op_kind, OpKind):
        try:
            op_kind = OpKind(op_kind)
        except ValueError:
            return GATE
    if op_kind in _OPERATOR_ONLY:
        return GATE
    return AUTHORIZED if op_kind in _AUTONOMOUS else GATE
