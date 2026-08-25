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
from typing import Any

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
    """set-field-status key carries the field name in retry identity (#812)."""
    k = RC.idempotency_key("set-field-status", "infiquetra/x", 279, "In-Progress")
    assert k == "set-field-status:infiquetra/x#279:Status:In-Progress"


def test_idempotency_key_includes_explicit_field() -> None:
    """Passing field=Stage distinguishes retry identity from Status (#812)."""
    status = RC.idempotency_key(
        "set-field-status", "infiquetra/x", 279, "In-Progress", field="Status"
    )
    stage = RC.idempotency_key(
        "set-field-status", "infiquetra/x", 279, "In-Progress", field="Stage"
    )
    assert status != stage
    assert ":Status:" in status
    assert ":Stage:" in stage


def test_idempotency_key_non_set_field_omits_field() -> None:
    """Unrelated op-kinds keep the original four-part recipe (F4: no clamp)."""
    k = RC.idempotency_key("sub-issue-close", "infiquetra/x", 279, "")
    assert k == "sub-issue-close:infiquetra/x#279:"


def test_authorize_correction_field_allows_status_and_stage_by_name() -> None:
    """Status and Stage (by name) are AUTHORIZED; no set-field-stage op-kind exists."""
    assert RC.authorize_correction_field("Status") == RC.AUTHORIZED
    assert RC.authorize_correction_field("Stage") == RC.AUTHORIZED
    assert "set-field-stage" not in {ok.value for ok in RC.all_op_kinds()}


def test_authorize_correction_field_rejects_other_project_fields() -> None:
    """Initiative / Objective / unknown fields GATE — field name is authorization."""
    assert RC.authorize_correction_field("Initiative") == RC.GATE
    assert RC.authorize_correction_field("Objective") == RC.GATE
    assert RC.authorize_correction_field("Priority") == RC.GATE


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


# ---------------------------------------------------------------------------
# #449 — AUTONOMOUS_UNDER_ENVELOPE: inert without a token (AC1), sibling-only
# ---------------------------------------------------------------------------

ET = _load("envelope_token")

_ENVELOPE_AUTO_MERGE = {
    "schema_version": 1,
    "run_mode": "attended",
    "ceremony_gates": {"reviews_required": "gate", "merge": "auto", "deploy_nonprod": "gate"},
}


class _Check:
    """A minimal token_check stand-in for the PURE sibling's unit tests (the real
    TokenCheck path is exercised in the envelope_token chain test below)."""

    def __init__(self, valid: bool, reason: str = "", envelope_id: str = "", token_id: str = ""):
        self.valid = valid
        self.reason = reason
        self.envelope_id = envelope_id
        self.token_id = token_id


def test_merge_under_envelope_authorize_write_gates_with_no_token() -> None:
    """AC1: the merge-authorization op kind through plain authorize_write is GATE — the
    class is inert without a token, and authorize_write has no token parameter (R2)."""
    assert RC.authorize_write("merge-under-envelope") == RC.GATE
    assert RC.authorize_write(RC.OpKind.MERGE_UNDER_ENVELOPE) == RC.GATE


def test_merge_under_envelope_registry_facts() -> None:
    """#449 R1: the write class is enumerated with its own tier — irreversible (no
    inverse), not ALWAYS_OPERATOR (the sibling CAN authorize it), never 'reversible'."""
    f = RC.facts(RC.OpKind.MERGE_UNDER_ENVELOPE)
    assert f.tier == RC.Tier.AUTONOMOUS_UNDER_ENVELOPE
    assert f.inverse is None, "a squash-merge has no registered inverse — it is irreversible"
    assert f.always_operator is False
    assert RC.OpKind.MERGE_UNDER_ENVELOPE not in RC.reversible_op_kinds()
    assert RC.OpKind.MERGE_UNDER_ENVELOPE in RC.all_op_kinds()


def test_bare_merge_and_deploy_strings_still_gate() -> None:
    """#449 R6/R7: adding the envelope class does not enumerate bare merge/deploy —
    R20's default-GATE for every tokenless caller is byte-identical."""
    assert RC.authorize_write("merge") == RC.GATE
    assert RC.authorize_write("deploy") == RC.GATE
    assert RC.authorize_write("pr-merge") == RC.GATE


def test_envelope_sibling_gates_without_token() -> None:
    """No token presented -> GATE, with the R20 default named in the reason."""
    auth = RC.authorize_write_under_envelope(
        RC.OpKind.MERGE_UNDER_ENVELOPE, None, other_gates_green=True
    )
    assert auth.verdict == RC.GATE
    assert "R20" in auth.reason
    assert auth.authorizing_envelope_id == "" and auth.token_id == ""


def test_envelope_sibling_never_widens_base_ops() -> None:
    """#449 R7: presenting a (valid-looking) token alongside a base-allowlist op or an
    unknown op grants NOTHING — the sibling only ever speaks for the envelope class."""
    check = _Check(True, "active", envelope_id="sha256:" + "a" * 64, token_id="t1")
    for op in ("set-field-status", "parent-issue-close", "some-invented-operation", ""):
        auth = RC.authorize_write_under_envelope(op, check, other_gates_green=True)
        assert auth.verdict == RC.GATE, f"{op!r} must GATE through the envelope sibling"
        assert auth.authorizing_envelope_id == ""


def test_envelope_sibling_gates_on_failed_check() -> None:
    """An invalid token check -> GATE, echoing the check's precise reason."""
    auth = RC.authorize_write_under_envelope(
        RC.OpKind.MERGE_UNDER_ENVELOPE,
        _Check(False, "token expired at 2026-01-01T00:00:00+00:00"),
        other_gates_green=True,
    )
    assert auth.verdict == RC.GATE and "expired" in auth.reason


def test_envelope_sibling_gates_when_other_gates_not_green() -> None:
    """AC2 (negative): a VALID token is necessary but not sufficient — other gates
    not green -> GATE."""
    check = _Check(True, "active", envelope_id="sha256:" + "b" * 64, token_id="t2")
    auth = RC.authorize_write_under_envelope(
        RC.OpKind.MERGE_UNDER_ENVELOPE, check, other_gates_green=False
    )
    assert auth.verdict == RC.GATE
    assert "necessary but not sufficient" in auth.reason


def test_envelope_sibling_authorizes_valid_token_and_green_gates() -> None:
    """AC2 (positive, cert level): valid check + green gates -> AUTHORIZED, echoing the
    authorizing envelope id so the ledger can attribute the write."""
    check = _Check(True, "active", envelope_id="sha256:" + "c" * 64, token_id="t3")
    auth = RC.authorize_write_under_envelope(
        RC.OpKind.MERGE_UNDER_ENVELOPE, check, other_gates_green=True
    )
    assert auth.verdict == RC.AUTHORIZED
    assert auth.authorizing_envelope_id == "sha256:" + "c" * 64
    assert auth.token_id == "t3"


def test_envelope_sibling_is_type_strict() -> None:
    """Wrong-TYPED attestations are caller bugs and raise — never coerced (lesson 1)."""
    check = _Check(True, "active", envelope_id="sha256:" + "d" * 64, token_id="t4")
    try:
        RC.authorize_write_under_envelope(
            RC.OpKind.MERGE_UNDER_ENVELOPE,
            check,
            other_gates_green=1,  # type: ignore[arg-type]
        )
        raise AssertionError("non-bool other_gates_green must raise")
    except TypeError:
        pass
    bad_valid = _Check(True, "active", envelope_id="sha256:" + "e" * 64, token_id="t5")
    bad_valid.valid = "yes"  # type: ignore[assignment]
    try:
        RC.authorize_write_under_envelope(
            RC.OpKind.MERGE_UNDER_ENVELOPE, bad_valid, other_gates_green=True
        )
        raise AssertionError("non-bool token_check.valid must raise")
    except TypeError:
        pass
    empty_id = _Check(True, "active", envelope_id="", token_id="t6")
    try:
        RC.authorize_write_under_envelope(
            RC.OpKind.MERGE_UNDER_ENVELOPE, empty_id, other_gates_green=True
        )
        raise AssertionError("a valid check with no envelope_id must raise")
    except TypeError:
        pass


def test_envelope_token_check_denied_authorized_revoked_chain(tmp_path: Path) -> None:
    """DoD chain (`-k envelope_token`): DENIED with no token -> AUTHORIZED with a valid
    token + green gates -> re-DENIED after revocation — one assertion chain through the
    REAL envelope_token store and the composed authorization surface (AC1/AC2/AC3)."""
    lane = tmp_path / "envelope-tokens"

    def authorize(now: str) -> Any:
        return ET.authorize_merge_under_envelope(
            lane,
            outcome_id="o",
            envelope=_ENVELOPE_AUTO_MERGE,
            intent_revision=0,
            other_gates_green=True,
            now=now,
        )

    # 1) DENIED: no token has ever been minted.
    pre = authorize("2026-07-14T00:00:00+00:00")
    assert pre.verdict == RC.GATE

    # 2) AUTHORIZED: one active token, all gates attested green.
    token = ET.mint_token(
        lane,
        outcome_id="o",
        envelope=_ENVELOPE_AUTO_MERGE,
        intent_revision=0,
        ttl_hours=24,
        issued_by="operator",
        now="2026-07-14T00:00:00+00:00",
    )
    mid = authorize("2026-07-14T01:00:00+00:00")
    assert mid.verdict == RC.AUTHORIZED
    assert mid.authorizing_envelope_id == token["envelope_id"]
    assert mid.token_id == token["token_id"]

    # 2b) envelope authorization is necessary but NOT sufficient (AC2).
    not_green = ET.authorize_merge_under_envelope(
        lane,
        outcome_id="o",
        envelope=_ENVELOPE_AUTO_MERGE,
        intent_revision=0,
        other_gates_green=False,
        now="2026-07-14T01:00:00+00:00",
    )
    assert not_green.verdict == RC.GATE

    # 3) re-DENIED: revocation flips the VERY NEXT call, nothing cached (AC3/R4).
    ET.revoke_token(
        lane, token["token_id"], reason="operator stop", now="2026-07-14T01:30:00+00:00"
    )
    post = authorize("2026-07-14T01:31:00+00:00")
    assert post.verdict == RC.GATE
    assert "revoked" in post.reason
