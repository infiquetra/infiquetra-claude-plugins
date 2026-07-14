"""Tests for envelope_token — the #449 revocable merge-authorization credential.

Pins R3 (token shape: envelope id, outcome id, merge-only scope, expiry,
revocation-checkable status; validity re-derived at authorization time, never cached)
and R4 (revocation effective on the very next check), plus the fail-closed matrix:
exact-keys schema, strict types, timezone-aware timestamps, whole-lane poisoning on a
malformed document, and ambiguity-GATEs on multiple active tokens.

Everything drives the production module loaded from ``plugins/saga/scripts`` — no
fabricated shapes; the CLI tests go through ``main()`` (the surface skills shell to).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

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


ET = _load("envelope_token")
RC = _load("reversibility_certificate")
SPEC = _load("outcome_spec")

T0 = "2026-07-14T00:00:00+00:00"
T1 = "2026-07-14T01:00:00+00:00"
T2 = "2026-07-14T02:00:00+00:00"


def _envelope(merge: str = "auto", **extra: Any) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_mode": "attended",
        "ceremony_gates": {"reviews_required": "gate", "merge": merge, "deploy_nonprod": "gate"},
        **extra,
    }


def _lane(tmp_path: Path) -> Path:
    return tmp_path / "envelope-tokens"


def _mint(lane: Path, **kw: Any) -> Any:
    defaults: dict[str, Any] = {
        "outcome_id": "o",
        "envelope": _envelope(),
        "intent_revision": 0,
        "ttl_hours": 24,
        "issued_by": "operator",
        "now": T0,
    }
    defaults.update(kw)
    return ET.mint_token(lane, **defaults)


def _check(lane: Path, token_id: str, **kw: Any) -> Any:
    defaults: dict[str, Any] = {
        "expected_outcome_id": "o",
        "expected_envelope": _envelope(),
        "expected_intent_revision": 0,
        "now": T1,
    }
    defaults.update(kw)
    return ET.check_token(lane, token_id, **defaults)


# ---------------------------------------------------------------------------
# Fingerprint — content-addressed envelope identity
# ---------------------------------------------------------------------------


def test_fingerprint_is_key_order_independent_and_content_sensitive() -> None:
    env = _envelope()
    reordered = {
        "run_mode": "attended",
        "ceremony_gates": {"deploy_nonprod": "gate", "merge": "auto", "reviews_required": "gate"},
        "schema_version": 1,
    }
    assert ET.envelope_fingerprint(env) == ET.envelope_fingerprint(reordered)
    tightened = _envelope(merge="gate")
    assert ET.envelope_fingerprint(env) != ET.envelope_fingerprint(tightened)


def test_fingerprint_rejects_an_invalid_envelope() -> None:
    with pytest.raises(Exception, match="unknown field"):
        ET.envelope_fingerprint({"run_mode": "attended", "bogus": 1})


# ---------------------------------------------------------------------------
# Mint — the write seam refuses what the read seam would refuse (lesson 10)
# ---------------------------------------------------------------------------


def test_mint_and_check_round_trip(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    token = _mint(lane)
    assert token["scope"] == "merge"
    assert token["envelope_id"] == ET.envelope_fingerprint(_envelope())
    check = _check(lane, token["token_id"])
    assert check.valid is True and check.malformed is False
    assert check.envelope_id == token["envelope_id"]


def test_mint_refuses_envelope_less_and_gate_posture(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    with pytest.raises(ET.EnvelopeTokenError, match="no committed intent envelope"):
        _mint(lane, envelope=None)
    with pytest.raises(ET.EnvelopeTokenError, match="merge token may only be minted"):
        _mint(lane, envelope=_envelope(merge="gate"))


def test_mint_expiry_authoring_rules(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    with pytest.raises(ET.EnvelopeTokenError, match="exactly one of"):
        _mint(lane, ttl_hours=None, expires_at=None)
    with pytest.raises(ET.EnvelopeTokenError, match="exactly one of"):
        _mint(lane, ttl_hours=1, expires_at=T1)
    with pytest.raises(ET.EnvelopeTokenError, match="not in the future"):
        _mint(lane, ttl_hours=None, expires_at="2026-07-13T00:00:00+00:00")
    with pytest.raises(ET.EnvelopeTokenError, match="ttl_hours"):
        _mint(lane, ttl_hours=-1)
    with pytest.raises(ET.EnvelopeTokenError, match="timezone-aware"):
        _mint(lane, ttl_hours=None, expires_at="2026-07-15T00:00:00")  # naive -> error


def test_mint_is_write_once_per_token_id(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    _mint(lane, token_id="emt-fixed")
    with pytest.raises(ET.EnvelopeTokenError, match="already exists"):
        _mint(lane, token_id="emt-fixed")


def test_mint_rejects_unsafe_token_id(tmp_path: Path) -> None:
    with pytest.raises(ET.EnvelopeTokenError, match="token_id"):
        _mint(_lane(tmp_path), token_id="../escape")


# ---------------------------------------------------------------------------
# Schema validation — exact keys, exact types, closed vocabularies (lesson 1)
# ---------------------------------------------------------------------------


def _valid_token_doc() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "token_id": "emt-1",
        "envelope_id": ET.envelope_fingerprint(_envelope()),
        "outcome_id": "o",
        "intent_revision": 0,
        "scope": "merge",
        "issued_at": T0,
        "expires_at": T2,
        "issued_by": "operator",
    }


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ({"extra_key": 1}, "unknown keys"),
        ({"schema_version": None}, "missing keys|schema_version"),
        ({"schema_version": 2}, "not the supported"),
        ({"schema_version": True}, "must be an integer"),
        ({"intent_revision": True}, "must be an integer"),
        ({"intent_revision": "0"}, "must be an integer"),
        ({"intent_revision": -1}, ">= 0"),
        ({"scope": "deploy"}, "merge-only"),
        ({"scope": "merge,deploy"}, "merge-only"),
        ({"envelope_id": "sha1:abc"}, "sha256"),
        ({"token_id": "bad/../id"}, "filename-safe"),
        ({"issued_at": "2026-07-14T00:00:00"}, "timezone-aware"),
        ({"expires_at": T0}, "strictly after"),
        ({"issued_by": 7}, "must be a non-empty string"),
    ],
)
def test_validate_token_fails_closed(mutation: dict[str, Any], match: str) -> None:
    doc = _valid_token_doc()
    for key, value in mutation.items():
        if value is None:
            doc.pop(key, None)
        else:
            doc[key] = value
    with pytest.raises(ET.EnvelopeTokenError, match=match):
        ET.validate_token(doc)


def test_validate_token_accepts_the_valid_document() -> None:
    """Baseline control: the matrix above can go green — a valid doc validates."""
    assert ET.validate_token(_valid_token_doc())["token_id"] == "emt-1"


# ---------------------------------------------------------------------------
# Check — derived on every read; every failure a precise reason (R3)
# ---------------------------------------------------------------------------


def test_check_missing_token(tmp_path: Path) -> None:
    check = _check(_lane(tmp_path), "emt-none")
    assert check.valid is False and "no token" in check.reason
    assert check.malformed is False  # absent is not malformed


def test_check_expired_at_boundary(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    token = _mint(lane, ttl_hours=1)  # expires T0+1h
    at_expiry = _check(lane, token["token_id"], now="2026-07-14T01:00:00+00:00")
    assert at_expiry.valid is False and "expired" in at_expiry.reason
    before = _check(lane, token["token_id"], now="2026-07-14T00:59:59+00:00")
    assert before.valid is True  # control: strictly-before still authorizes


def test_check_outcome_mismatch(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    token = _mint(lane)
    check = _check(lane, token["token_id"], expected_outcome_id="other")
    assert check.valid is False and "issued for outcome" in check.reason


def test_check_envelope_less_spec(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    token = _mint(lane)
    check = _check(lane, token["token_id"], expected_envelope=None)
    assert check.valid is False and "no committed intent envelope" in check.reason


def test_check_gate_posture_never_authorizes(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    token = _mint(lane)
    check = _check(lane, token["token_id"], expected_envelope=_envelope(merge="gate"))
    assert check.valid is False and "does not permit autonomous merge" in check.reason


def test_check_fingerprint_mismatch_after_renegotiation(tmp_path: Path) -> None:
    """A repost that changes ANY envelope content invalidates the token (era binding)."""
    lane = _lane(tmp_path)
    token = _mint(lane)
    renegotiated = _envelope(merge="auto", source="repost")  # content changed, merge still auto
    check = _check(lane, token["token_id"], expected_envelope=renegotiated)
    assert check.valid is False and "fingerprint mismatch" in check.reason


def test_check_intent_revision_mismatch(tmp_path: Path) -> None:
    """Same content at a NEW revision (an A->B->A round trip) is a new era -> invalid."""
    lane = _lane(tmp_path)
    token = _mint(lane, intent_revision=0)
    check = _check(lane, token["token_id"], expected_intent_revision=2)
    assert check.valid is False and "intent_revision" in check.reason


def test_check_malformed_token_file(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    lane.mkdir(parents=True)
    (lane / "emt-bad.json").write_text("{not json", encoding="utf-8")
    check = _check(lane, "emt-bad")
    assert check.valid is False and check.malformed is True


def test_check_token_file_identity_mismatch(tmp_path: Path) -> None:
    """A token document whose token_id disagrees with its filename is a forgery signal."""
    lane = _lane(tmp_path)
    token = _mint(lane, token_id="emt-real")
    forged = {**token, "token_id": "emt-other"}
    (lane / "emt-copy.json").write_text(json.dumps(forged), encoding="utf-8")
    check = _check(lane, "emt-copy")
    assert check.valid is False and check.malformed is True and "identity" in check.reason


# ---------------------------------------------------------------------------
# Revocation — immediate, write-once, monotonic (R4)
# ---------------------------------------------------------------------------


def test_revocation_flips_the_very_next_check(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    token = _mint(lane)
    assert _check(lane, token["token_id"]).valid is True
    ET.revoke_token(lane, token["token_id"], reason="operator stop", now=T1)
    after = _check(lane, token["token_id"], now="2026-07-14T01:00:01+00:00")
    assert after.valid is False and after.revoked is True
    assert "operator stop" in after.reason


def test_revoking_unknown_token_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ET.EnvelopeTokenError, match="unknown token"):
        ET.revoke_token(_lane(tmp_path), "emt-ghost", reason="typo", now=T1)


def test_double_revocation_is_idempotent_and_never_rewrites_history(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    token = _mint(lane)
    first = ET.revoke_token(lane, token["token_id"], reason="first", now=T1)
    assert first["already_revoked"] is False
    second = ET.revoke_token(lane, token["token_id"], reason="second", now=T2)
    assert second["already_revoked"] is True
    assert second["reason"] == "first" and second["revoked_at"] == T1  # original preserved


def test_unreadable_revocation_marker_fails_closed_as_revoked(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    token = _mint(lane)
    (lane / f"{token['token_id']}.revoked.json").write_text("{torn", encoding="utf-8")
    check = _check(lane, token["token_id"])
    assert check.valid is False and check.revoked is True and check.malformed is True


# ---------------------------------------------------------------------------
# Resolve — exactly-one-active or GATE (ambiguity + lane poisoning)
# ---------------------------------------------------------------------------


def _resolve(lane: Path, **kw: Any) -> Any:
    defaults: dict[str, Any] = {
        "outcome_id": "o",
        "envelope": _envelope(),
        "intent_revision": 0,
        "now": T1,
    }
    defaults.update(kw)
    return ET.resolve_merge_token(lane, **defaults)


def test_resolve_no_lane_and_no_tokens(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    assert _resolve(lane).valid is False  # no lane at all
    lane.mkdir(parents=True)
    check = _resolve(lane)
    assert check.valid is False and "no tokens minted" in check.reason


def test_resolve_exactly_one_active_token(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    token = _mint(lane)
    resolved = _resolve(lane)
    assert resolved.valid is True and resolved.token_id == token["token_id"]


def test_resolve_ambiguous_multiple_active_tokens_gates(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    _mint(lane, token_id="emt-a")
    _mint(lane, token_id="emt-b")
    resolved = _resolve(lane)
    assert resolved.valid is False and "ambiguous" in resolved.reason


def test_resolve_expired_plus_active_resolves_the_active_one(tmp_path: Path) -> None:
    """A well-formed but no-longer-valid token does NOT poison the lane (control)."""
    lane = _lane(tmp_path)
    _mint(lane, token_id="emt-old", ttl_hours=0.5)  # expired by T1
    _mint(lane, token_id="emt-live", ttl_hours=24)
    resolved = _resolve(lane)
    assert resolved.valid is True and resolved.token_id == "emt-live"


def test_resolve_malformed_document_poisons_the_whole_lane(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    _mint(lane, token_id="emt-live")
    (lane / "junk.json").write_text("not json at all", encoding="utf-8")
    resolved = _resolve(lane)
    assert resolved.valid is False and "whole lane closed" in resolved.reason


def test_resolve_all_invalid_reports_each_reason(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    _mint(lane, token_id="emt-old", ttl_hours=0.5)
    ET.revoke_token(lane, "emt-old", reason="done", now=T0)
    resolved = _resolve(lane)
    assert resolved.valid is False
    assert "emt-old" in resolved.reason and "revoked" in resolved.reason


# ---------------------------------------------------------------------------
# list_tokens — operator audit with derived statuses
# ---------------------------------------------------------------------------


def test_list_tokens_derives_statuses(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    _mint(lane, token_id="emt-active", ttl_hours=24)
    _mint(lane, token_id="emt-expired", ttl_hours=0.5)
    _mint(lane, token_id="emt-revoked", ttl_hours=24)
    ET.revoke_token(lane, "emt-revoked", reason="done", now=T0)
    (lane / "emt-junk.json").write_text("{", encoding="utf-8")
    rows = {r["token_id"]: r["status"] for r in ET.list_tokens(lane, now=T1)}
    assert rows == {
        "emt-active": "active",
        "emt-expired": "expired",
        "emt-revoked": "revoked",
        "emt-junk": "malformed",
    }


# ---------------------------------------------------------------------------
# CLI — the operator surface (mint -> check -> revoke -> check), production spec file
# ---------------------------------------------------------------------------


def _write_spec(tmp_path: Path, *, intent: dict[str, Any] | None) -> Path:
    payload: dict[str, Any] = {
        "outcome_id": "o",
        "objective": "ship",
        "nodes": [{"subplot_id": "a", "title": "A", "kind": "code"}],
    }
    if intent is not None:
        payload["intent"] = intent
    spec = SPEC.OutcomeSpec.from_dict(payload)
    spec.validate()
    path = tmp_path / "outcome-spec.json"
    path.write_text(spec.to_json(), encoding="utf-8")
    return path


def test_cli_mint_check_revoke_check(tmp_path: Path, capsys: Any) -> None:
    spec_file = _write_spec(tmp_path, intent=_envelope())
    store_root = tmp_path / "store"
    base = ["--store-root", str(store_root), "--now", T0]

    rc = ET.main(
        [
            "mint",
            *base,
            "--outcome-spec",
            str(spec_file),
            "--ttl-hours",
            "24",
            "--token-id",
            "emt-cli",
            "--issued-by",
            "operator",
        ]
    )
    assert rc == 0
    minted = json.loads(capsys.readouterr().out)
    assert minted["token_id"] == "emt-cli" and minted["scope"] == "merge"

    rc = ET.main(["check", *base[:2], "--now", T1, "--outcome-spec", str(spec_file)])
    assert rc == 0  # resolves the single active token without an explicit id
    assert json.loads(capsys.readouterr().out)["valid"] is True

    rc = ET.main(["revoke", *base[:2], "--now", T1, "emt-cli", "--reason", "stop"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["already_revoked"] is False

    rc = ET.main(["check", *base[:2], "--now", T2, "--outcome-spec", str(spec_file)])
    assert rc == 1  # invalid -> exit 1 (scripts can branch on it)
    out = json.loads(capsys.readouterr().out)
    assert out["valid"] is False and "revoked" in out["reason"]


def test_cli_mint_refuses_gate_postured_spec(tmp_path: Path, capsys: Any) -> None:
    spec_file = _write_spec(tmp_path, intent=_envelope(merge="gate"))
    rc = ET.main(
        [
            "mint",
            "--store-root",
            str(tmp_path / "store"),
            "--outcome-spec",
            str(spec_file),
            "--ttl-hours",
            "24",
        ]
    )
    assert rc == 1
    capsys.readouterr()


def test_cli_requires_a_lane_argument(tmp_path: Path, capsys: Any) -> None:
    spec_file = _write_spec(tmp_path, intent=_envelope())
    rc = ET.main(["check", "--outcome-spec", str(spec_file)])
    assert rc == 2
    capsys.readouterr()


# ---------------------------------------------------------------------------
# Composed authorization with an explicit token id (the check_token path)
# ---------------------------------------------------------------------------


def test_authorize_with_explicit_token_id(tmp_path: Path) -> None:
    lane = _lane(tmp_path)
    token = _mint(lane)
    auth = ET.authorize_merge_under_envelope(
        lane,
        outcome_id="o",
        envelope=_envelope(),
        intent_revision=0,
        other_gates_green=True,
        token_id=token["token_id"],
        now=T1,
    )
    assert auth.verdict == RC.AUTHORIZED
    wrong = ET.authorize_merge_under_envelope(
        lane,
        outcome_id="o",
        envelope=_envelope(),
        intent_revision=0,
        other_gates_green=True,
        token_id="emt-ghost",
        now=T1,
    )
    assert wrong.verdict == RC.GATE


def test_reserved_revoked_suffix_token_id_refused_at_every_verb(tmp_path: Path) -> None:
    """#449 panel hand-finish (P3): a token id ending '.revoked' would make its file
    collide with token '<id>''s revocation-marker path — invisible to list/resolve yet
    checkable by explicit id, and able to shadow the sibling's revocation state. The
    shared path seam refuses the reserved suffix, so mint, check, and revoke ALL fail
    closed on it and the collision is unmintable."""
    lane = _lane(tmp_path)
    lane.mkdir(parents=True)
    with pytest.raises(ET.EnvelopeTokenError, match="reserved"):
        _mint(lane, token_id="x.revoked")
    # The read seam's contract is a fail-closed VERDICT, never an exception (its whole
    # surface returns TokenCheck) — the reserved id checks invalid+malformed, not valid.
    checked = _check(lane, "x.revoked")
    assert not checked.valid and checked.malformed and "reserved" in checked.reason
    with pytest.raises(ET.EnvelopeTokenError, match="reserved"):
        ET.revoke_token(lane, "x.revoked", reason="r", now=T1)
    # Control: the seam refuses ONLY the reserved suffix — a dotted id still mints.
    assert _mint(lane, token_id="x.v2")["token_id"] == "x.v2"
