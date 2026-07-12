"""Tests for the reversibility certificate authority (U1 — R1–R9, R20).

Mirrors test_outcome_backends.py per-case style and _load import mechanism.

These are UNIT tests proving the authority in isolation — they do NOT prove the
authority is wired to any consumer (KTD8: dead-wired until U4).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RC = _load("reversibility_certificate")


# ---------------------------------------------------------------------------
# R5 — Enumerated reversible op → AUTHORIZED; declared inverse present
# ---------------------------------------------------------------------------


def test_set_field_status_is_authorized() -> None:
    """set-field-status is an enumerated reversible op → authorize_write returns AUTHORIZED (R5)."""
    verdict = RC.authorize_write(RC.OpKind.SET_FIELD_STATUS)
    assert verdict == RC.AUTHORIZED


def test_set_field_status_has_declared_inverse() -> None:
    """set-field-status declares an inverse to set-field-status with a prior-value recipe (R5, KTD3)."""
    f = RC.facts(RC.OpKind.SET_FIELD_STATUS)
    assert f.tier == RC.Tier.REVERSIBLE
    assert f.inverse is not None, "reversible op must have a declared inverse"
    assert f.inverse.op_kind == RC.OpKind.SET_FIELD_STATUS
    assert "prior" in f.inverse.arg_derivation.lower(), (
        "inverse arg_derivation must reference reverting to the prior value"
    )


def test_set_field_status_string_form_is_authorized() -> None:
    """String form 'set-field-status' resolves to AUTHORIZED (coerce path, R5)."""
    assert RC.authorize_write("set-field-status") == RC.AUTHORIZED


def test_sub_issue_close_inverse_is_reopen_not_self() -> None:
    """sub-issue-close's inverse is sub-issue-reopen — NOT itself (R5, KTD3).

    Mutation-proof against the self-inverse footgun: a rollback of an autonomous close
    must REOPEN the sub-issue, never re-close it.
    """
    f = RC.facts(RC.OpKind.SUB_ISSUE_CLOSE)
    assert f.inverse is not None
    assert f.inverse.op_kind == RC.OpKind.SUB_ISSUE_REOPEN
    assert f.inverse.op_kind != RC.OpKind.SUB_ISSUE_CLOSE, (
        "closing is not its own inverse — the inverse of a close is a reopen"
    )


def test_close_reopen_inverses_are_symmetric() -> None:
    """close⇄reopen and add⇄remove form symmetric reversible pairs (R5, KTD3)."""
    close = RC.facts(RC.OpKind.SUB_ISSUE_CLOSE)
    reopen = RC.facts(RC.OpKind.SUB_ISSUE_REOPEN)
    assert close.inverse is not None and reopen.inverse is not None
    assert close.inverse.op_kind == RC.OpKind.SUB_ISSUE_REOPEN
    assert reopen.inverse.op_kind == RC.OpKind.SUB_ISSUE_CLOSE

    add = RC.facts(RC.OpKind.ISSUE_LABEL_ADD)
    remove = RC.facts(RC.OpKind.ISSUE_LABEL_REMOVE)
    assert add.inverse is not None and remove.inverse is not None
    assert add.inverse.op_kind == RC.OpKind.ISSUE_LABEL_REMOVE
    assert remove.inverse.op_kind == RC.OpKind.ISSUE_LABEL_ADD


# ---------------------------------------------------------------------------
# issue #347 U3 (KTD7) — worktree-reclaim-merged reversible op + its inverse
# ---------------------------------------------------------------------------


def test_worktree_reclaim_merged_is_authorized_reversible() -> None:
    """worktree-reclaim-merged is an enumerated reversible op → AUTHORIZED (KTD7)."""
    verdict = RC.authorize_write(RC.OpKind.WORKTREE_RECLAIM_MERGED)
    assert verdict == RC.AUTHORIZED
    f = RC.facts(RC.OpKind.WORKTREE_RECLAIM_MERGED)
    assert f.tier == RC.Tier.REVERSIBLE
    assert f.always_operator is False


def test_worktree_reclaim_merged_declares_git_worktree_add_inverse() -> None:
    """Its inverse re-creates the worktree via `git worktree add` (KTD7, R5 golden)."""
    f = RC.facts(RC.OpKind.WORKTREE_RECLAIM_MERGED)
    assert f.inverse is not None
    assert "worktree add" in f.inverse.arg_derivation
    assert RC.OpKind.WORKTREE_RECLAIM_MERGED in RC.reversible_op_kinds()


def test_worktree_reclaim_merged_string_form_authorized() -> None:
    """String form resolves to AUTHORIZED via the coerce path (KTD7)."""
    assert RC.authorize_write("worktree-reclaim-merged") == RC.AUTHORIZED


# ---------------------------------------------------------------------------
# R6 — Enumerated additive op → AUTHORIZED; no inverse; abort_cost bound present
# ---------------------------------------------------------------------------


def test_issue_progress_comment_is_authorized() -> None:
    """issue-progress-comment is an enumerated additive op → AUTHORIZED (R6)."""
    verdict = RC.authorize_write(RC.OpKind.ISSUE_PROGRESS_COMMENT)
    assert verdict == RC.AUTHORIZED


def test_issue_progress_comment_has_no_inverse() -> None:
    """issue-progress-comment is append-only → no inverse declared (R6)."""
    f = RC.facts(RC.OpKind.ISSUE_PROGRESS_COMMENT)
    assert f.tier == RC.Tier.ADDITIVE
    assert f.inverse is None, "additive op must have no declared inverse"


def test_issue_progress_comment_carries_abort_cost_bound() -> None:
    """issue-progress-comment carries an abort_cost bound (R6)."""
    f = RC.facts(RC.OpKind.ISSUE_PROGRESS_COMMENT)
    assert f.abort_cost is not None and len(f.abort_cost) > 0, (
        "additive op must carry a non-empty abort_cost bound"
    )


# ---------------------------------------------------------------------------
# R7, AE3 — ALWAYS_OPERATOR → GATE even though closeable
# ---------------------------------------------------------------------------


def test_parent_issue_close_is_always_gated() -> None:
    """parent-issue-close is ALWAYS_OPERATOR → authorize_write returns GATE (R7, AE3)."""
    verdict = RC.authorize_write(RC.OpKind.PARENT_ISSUE_CLOSE)
    assert verdict == RC.GATE


def test_parent_issue_close_always_operator_flag() -> None:
    """parent-issue-close facts carry always_operator=True (R7)."""
    f = RC.facts(RC.OpKind.PARENT_ISSUE_CLOSE)
    assert f.always_operator is True


def test_parent_issue_close_string_form_is_gated() -> None:
    """String form 'parent-issue-close' also resolves to GATE (R7)."""
    assert RC.authorize_write("parent-issue-close") == RC.GATE


# ---------------------------------------------------------------------------
# R3, R8, AE5 — Unenumerated op → GATE (default-deny)
# ---------------------------------------------------------------------------


def test_repo_label_definition_delete_is_gated() -> None:
    """Unenumerated op 'repo-label-definition-delete' → GATE (R3, R8, AE5)."""
    verdict = RC.authorize_write("repo-label-definition-delete")
    assert verdict == RC.GATE


def test_arbitrary_string_op_is_gated() -> None:
    """Arbitrary unknown string → GATE (default-deny, R3, R8)."""
    assert RC.authorize_write("some-invented-operation") == RC.GATE


def test_empty_string_is_gated() -> None:
    """Empty string (not an OpKind member) → GATE (R8)."""
    assert RC.authorize_write("") == RC.GATE


# ---------------------------------------------------------------------------
# R20, AE7 — merge / deploy absent from registry → GATE
# ---------------------------------------------------------------------------


def test_merge_is_gated() -> None:
    """'merge' is absent from the registry → GATE (R20, AE7)."""
    assert RC.authorize_write("merge") == RC.GATE


def test_deploy_is_gated() -> None:
    """'deploy' is absent from the registry → GATE (R20, AE7)."""
    assert RC.authorize_write("deploy") == RC.GATE


def test_pr_merge_is_gated() -> None:
    """'pr-merge' variant also absent → GATE (R20)."""
    assert RC.authorize_write("pr-merge") == RC.GATE


# ---------------------------------------------------------------------------
# R9 — idempotency_key is deterministic and distinct across target/issue
# ---------------------------------------------------------------------------


def test_idempotency_key_is_deterministic() -> None:
    """Same inputs produce the same key every time (R9)."""
    k1 = RC.idempotency_key("set-field-status", "infiquetra/x", 279, "In-Progress")
    k2 = RC.idempotency_key("set-field-status", "infiquetra/x", 279, "In-Progress")
    assert k1 == k2


def test_idempotency_key_distinct_target_state() -> None:
    """Different target_state → distinct key (R9)."""
    k1 = RC.idempotency_key("set-field-status", "infiquetra/x", 279, "In-Progress")
    k2 = RC.idempotency_key("set-field-status", "infiquetra/x", 279, "Done")
    assert k1 != k2


def test_idempotency_key_distinct_issue_number() -> None:
    """Different issue_number → distinct key (R9)."""
    k1 = RC.idempotency_key("set-field-status", "infiquetra/x", 279, "In-Progress")
    k2 = RC.idempotency_key("set-field-status", "infiquetra/x", 280, "In-Progress")
    assert k1 != k2


def test_idempotency_key_distinct_repo_same_number() -> None:
    """Different repo, SAME issue number → distinct key (R9).

    Regression guard for the cross-repo collision the U4 adversarial-verify found: saga#5 and
    mission-control#5 must not share a ledger entry, or one silently skips the other's board write.
    """
    k1 = RC.idempotency_key("sub-issue-close", "infiquetra/saga", 5, "")
    k2 = RC.idempotency_key("sub-issue-close", "infiquetra/mission-control", 5, "")
    assert k1 != k2


def test_idempotency_key_distinct_op_kind() -> None:
    """Different op_kind → distinct key (R9)."""
    k1 = RC.idempotency_key("set-field-status", "infiquetra/x", 279, "In-Progress")
    k2 = RC.idempotency_key("issue-label-add", "infiquetra/x", 279, "In-Progress")
    assert k1 != k2


def test_idempotency_key_opkind_enum_and_string_equivalent() -> None:
    """OpKind enum and its string value produce the same key (R9)."""
    k_enum = RC.idempotency_key(RC.OpKind.SET_FIELD_STATUS, "infiquetra/x", 279, "In-Progress")
    k_str = RC.idempotency_key("set-field-status", "infiquetra/x", 279, "In-Progress")
    assert k_enum == k_str


def test_idempotency_key_format() -> None:
    """Key follows the '{op_kind}:{repo}#{issue_number}:{target_state}' recipe (KTD4)."""
    k = RC.idempotency_key("set-field-status", "infiquetra/x", 279, "In-Progress")
    assert k == "set-field-status:infiquetra/x#279:In-Progress"


# ---------------------------------------------------------------------------
# R5 — Every reversible OpKind has a registered inverse (golden invariant)
# ---------------------------------------------------------------------------


def test_every_reversible_op_kind_has_registered_inverse() -> None:
    """Every reversible OpKind has a non-None inverse declared (R5, KTD3)."""
    reversible = RC.reversible_op_kinds()
    assert len(reversible) > 0, "registry must contain at least one reversible op"
    for ok in reversible:
        f = RC.facts(ok)
        assert f.inverse is not None, (
            f"reversible OpKind {ok!r} is missing its declared inverse — "
            "every reversible op must have one (R5)"
        )
        assert isinstance(f.inverse, RC.InverseDescriptor)
        assert f.inverse.op_kind is not None
        assert f.inverse.arg_derivation, "inverse arg_derivation must be non-empty"


def test_reversible_ops_are_authorized() -> None:
    """All reversible ops that are not ALWAYS_OPERATOR resolve to AUTHORIZED."""
    for ok in RC.reversible_op_kinds():
        f = RC.facts(ok)
        assert not f.always_operator, (
            f"{ok!r} is REVERSIBLE tier but also marked always_operator=True — "
            "if it should be ALWAYS_OPERATOR use that tier instead"
        )
        assert RC.authorize_write(ok) == RC.AUTHORIZED, (
            f"reversible non-always-op {ok!r} must be AUTHORIZED"
        )


# ---------------------------------------------------------------------------
# side_effected — pure pass-through identity (R10, KTD5 seam)
# ---------------------------------------------------------------------------


def test_side_effected_true_passthrough() -> None:
    """side_effected(True) returns True — pass-through identity (R10, KTD5)."""
    assert RC.side_effected(True) is True


def test_side_effected_false_passthrough() -> None:
    """side_effected(False) returns False — pass-through identity (R10, KTD5)."""
    assert RC.side_effected(False) is False


# ---------------------------------------------------------------------------
# Closed-allowlist sanity — only enumerated ops can be AUTHORIZED
# ---------------------------------------------------------------------------


def test_all_op_kinds_covered_in_registry() -> None:
    """Every OpKind member appears in the registry (allowlist completeness)."""
    registered = set(RC.all_op_kinds())
    for ok in RC.OpKind:
        assert ok in registered, f"OpKind {ok!r} is not registered in the allowlist"


def test_only_non_always_operator_ops_are_authorized() -> None:
    """Only reversible/additive ops that are NOT always_operator resolve to AUTHORIZED."""
    for ok in RC.OpKind:
        verdict = RC.authorize_write(ok)
        f = RC.facts(ok)
        if f.always_operator:
            assert verdict == RC.GATE, f"{ok!r} is ALWAYS_OPERATOR but got AUTHORIZED"
        elif f.tier in (RC.Tier.REVERSIBLE, RC.Tier.ADDITIVE):
            assert verdict == RC.AUTHORIZED, f"{ok!r} is {f.tier} but got GATE"
