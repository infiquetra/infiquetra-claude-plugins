"""Tests for the evidence ledger: content-addressed, append-only custody log (#398).

Oracles pinned here:

* no_clobber — a second write under the same ``(check_id, reviewed_sha, attempt)`` identity with
  different content is rejected; an identical resubmission is an idempotent no-op; omitting
  ``attempt`` auto-assigns the next one (a retry, not a clobber); a traversal-shaped id is
  rejected (parity with ``outcome_store._safe_name``).
* custody_chain_validates — N writes verify end to end; a hand-edited entry, a deleted artifact,
  and a torn trailing line each HALT with a typed error.
* fail_then_pass_supersession — a PASS after a FAIL for the same ``(check_id, reviewed_sha)``
  preserves the FAIL record unchanged; ``latest()`` flags the transition; the reverse order is
  not flagged.
* criteria_frozen_across_attempts — freeze once; attempt-1 FAIL then attempt-2 PASS both persist;
  the criteria bytes never change; a second freeze is rejected.
* closure_halts_on_tamper — mutating an artifact's bytes after write makes ``close_verify`` HALT;
  a clean chain closes successfully.
* producer_cannot_self_certify — a verifier matching the check's producer role is rejected; a
  distinct verifier closes successfully.
* qa_and_code_review_write_through — the CLI drives write/latest/verify-chain/close end to end;
  the no-saga adhoc fallback lands under ``docs/evidence/adhoc-*/``; both skill files reference
  the ledger instead of a bare file write.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
SCRIPT = SCRIPTS / "evidence_ledger.py"


def _load() -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("evidence_ledger", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["evidence_ledger"] = module
    spec.loader.exec_module(module)
    return module


E = _load()

SHA_A = "a" * 40
SHA_B = "b" * 40


@pytest.fixture
def store(tmp_path: Path):
    return E.Store.for_saga("issue-398", tmp_path).ensure()


# ---------------------------------------------------------------------------
# no_clobber
# ---------------------------------------------------------------------------


def test_evidence_ledger_no_clobber_rejects_same_identity_different_content(store):
    E.write(
        store,
        check_id="qa",
        reviewed_sha=SHA_A,
        producer="qa-gate",
        verdict="PASS",
        content="report v1",
        attempt=1,
    )
    with pytest.raises(E.EvidenceLedgerError):
        E.write(
            store,
            check_id="qa",
            reviewed_sha=SHA_A,
            producer="qa-gate",
            verdict="FAIL",
            content="report v2 -- different bytes",
            attempt=1,
        )
    result = E.latest(store, check_id="qa", reviewed_sha=SHA_A)
    assert result.verdict == "PASS"
    assert len(result.history) == 1


def test_evidence_ledger_no_clobber_allows_idempotent_replay(store):
    r1 = E.write(
        store,
        check_id="qa",
        reviewed_sha=SHA_A,
        producer="qa-gate",
        verdict="PASS",
        content="same bytes",
        attempt=1,
    )
    r2 = E.write(
        store,
        check_id="qa",
        reviewed_sha=SHA_A,
        producer="qa-gate",
        verdict="PASS",
        content="same bytes",
        attempt=1,
    )
    assert r1.content_hash == r2.content_hash
    assert len(E._read_lines_or_halt(store.ledger_path)) == 1


def test_evidence_ledger_no_clobber_auto_attempt_is_a_new_attempt_not_a_clobber(store):
    E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="FAIL", content="v1"
    )
    r2 = E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="PASS", content="v2"
    )
    assert r2.attempt == 2
    assert len(E._read_lines_or_halt(store.ledger_path)) == 2


def test_evidence_ledger_no_clobber_rejects_path_traversal_id(tmp_path):
    with pytest.raises(E.EvidenceLedgerError):
        E.Store.for_saga("../escape", tmp_path)
    good_store = E.Store.for_saga("issue-398", tmp_path).ensure()
    with pytest.raises(E.EvidenceLedgerError):
        E.write(
            good_store,
            check_id="../escape",
            reviewed_sha=SHA_A,
            producer="p",
            verdict="PASS",
            content="x",
        )


# ---------------------------------------------------------------------------
# custody_chain_validates
# ---------------------------------------------------------------------------


def test_evidence_ledger_custody_chain_validates_end_to_end(store):
    E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="FAIL", content="v1"
    )
    E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="PASS", content="v2"
    )
    E.write(
        store,
        check_id="code-review",
        reviewed_sha=SHA_B,
        producer="code-review-gate",
        verdict="PASS",
        content="cr",
    )
    report = E.verify_chain(store)
    assert report.entry_count == 3
    assert report.verified_artifacts == 3


def test_evidence_ledger_custody_chain_validates_rejects_hand_edited_entry(store):
    E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="PASS", content="v1"
    )
    entry = json.loads(store.ledger_path.read_text(encoding="utf-8").splitlines()[0])
    entry["verdict"] = "FAIL"  # tamper the recorded entry itself, not just the artifact
    store.ledger_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    with pytest.raises(E.EvidenceLedgerError):
        E.verify_chain(store)


def test_evidence_ledger_custody_chain_validates_rejects_deleted_artifact(store):
    result = E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="PASS", content="v1"
    )
    result.artifact_path.unlink()
    with pytest.raises(E.EvidenceLedgerError):
        E.verify_chain(store)


def test_evidence_ledger_custody_chain_validates_rejects_torn_trailing_line(store):
    E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="PASS", content="v1"
    )
    with open(store.ledger_path, "a", encoding="utf-8") as fh:
        fh.write('{"seq": 2, "kind": "evidence"')  # truncated, no trailing newline
    with pytest.raises(E.EvidenceLedgerError):
        E.verify_chain(store)


# ---------------------------------------------------------------------------
# fail_then_pass_supersession
# ---------------------------------------------------------------------------


def test_evidence_ledger_fail_then_pass_supersession_preserves_fail_and_flags_transition(store):
    E.write(
        store,
        check_id="qa",
        reviewed_sha=SHA_A,
        producer="qa-gate",
        verdict="FAIL",
        content="fail body",
    )
    E.write(
        store,
        check_id="qa",
        reviewed_sha=SHA_A,
        producer="qa-gate",
        verdict="PASS",
        content="pass body",
    )
    result = E.latest(store, check_id="qa", reviewed_sha=SHA_A)
    assert result.verdict == "PASS"
    assert result.superseded_fail is True
    assert len(result.history) == 2
    assert result.history[0]["verdict"] == "FAIL"
    assert result.history[0]["hash"] == E._sha256_hex(b"fail body")


def test_evidence_ledger_fail_then_pass_supersession_pass_then_fail_is_not_flagged(store):
    E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="PASS", content="v1"
    )
    E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="FAIL", content="v2"
    )
    result = E.latest(store, check_id="qa", reviewed_sha=SHA_A)
    assert result.superseded_fail is False


# ---------------------------------------------------------------------------
# history (#397) — every entry for a check across every reviewed_sha
# ---------------------------------------------------------------------------


def test_evidence_ledger_history_returns_entries_across_every_sha(store):
    E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="FAIL", content="v1"
    )
    E.write(
        store, check_id="qa", reviewed_sha=SHA_B, producer="qa-gate", verdict="PASS", content="v2"
    )
    E.write(
        store,
        check_id="code-review",
        reviewed_sha=SHA_A,
        producer="code-review-gate",
        verdict="PASS",
        content="v3",
    )

    qa_history = E.history(store, check_id="qa")

    assert [e["reviewed_sha"] for e in qa_history] == [SHA_A, SHA_B]
    assert all(e["check_id"] == "qa" for e in qa_history)


def test_evidence_ledger_history_empty_for_unknown_check(store):
    E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="PASS", content="v1"
    )

    assert E.history(store, check_id="code-review") == []
    assert E.history(store, check_id="qa") != []


# ---------------------------------------------------------------------------
# criteria_frozen_across_attempts
# ---------------------------------------------------------------------------


def test_evidence_ledger_criteria_frozen_across_attempts(store):
    criteria = {"pass_if": "no P0/P1", "check": "code-review"}
    frozen = E.freeze_criteria(store, check_id="code-review", reviewed_sha=SHA_A, criteria=criteria)
    before_bytes = frozen.criteria_path.read_bytes()

    E.write(
        store,
        check_id="code-review",
        reviewed_sha=SHA_A,
        producer="code-review-gate",
        verdict="FAIL",
        content="attempt1",
    )
    E.write(
        store,
        check_id="code-review",
        reviewed_sha=SHA_A,
        producer="code-review-gate",
        verdict="PASS",
        content="attempt2",
    )

    result = E.latest(store, check_id="code-review", reviewed_sha=SHA_A)
    assert len(result.history) == 2
    assert frozen.criteria_path.read_bytes() == before_bytes

    with pytest.raises(E.EvidenceLedgerError):
        E.freeze_criteria(store, check_id="code-review", reviewed_sha=SHA_A, criteria=criteria)


# ---------------------------------------------------------------------------
# closure_halts_on_tamper
# ---------------------------------------------------------------------------


def test_evidence_ledger_closure_halts_on_tamper(store):
    result = E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="PASS", content="v1"
    )
    result.artifact_path.write_text("tampered bytes", encoding="utf-8")
    with pytest.raises(E.EvidenceLedgerError):
        E.close_verify(store, check_id="qa", reviewed_sha=SHA_A, verifier="operator")


def test_evidence_ledger_closure_halts_on_tamper_clean_chain_closes(store):
    E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="PASS", content="v1"
    )
    report = E.close_verify(store, check_id="qa", reviewed_sha=SHA_A, verifier="operator")
    assert report.verifier == "operator"
    assert report.certified_through_seq == 1


# ---------------------------------------------------------------------------
# producer_cannot_self_certify
# ---------------------------------------------------------------------------


def test_evidence_ledger_producer_cannot_self_certify(store):
    E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="PASS", content="v1"
    )
    with pytest.raises(E.EvidenceLedgerError):
        E.close_verify(store, check_id="qa", reviewed_sha=SHA_A, verifier="qa-gate")


def test_evidence_ledger_producer_cannot_self_certify_distinct_verifier_passes(store):
    E.write(
        store, check_id="qa", reviewed_sha=SHA_A, producer="qa-gate", verdict="PASS", content="v1"
    )
    report = E.close_verify(
        store, check_id="qa", reviewed_sha=SHA_A, verifier="outcome-coordinator"
    )
    assert report.certified_through_seq == 1


# ---------------------------------------------------------------------------
# qa_and_code_review_write_through
# ---------------------------------------------------------------------------


def test_evidence_ledger_qa_and_code_review_write_through_cli_write_and_latest(tmp_path):
    artifact = tmp_path / "qa-report.md"
    artifact.write_text("# QA Report\n\nverdict: ship\n", encoding="utf-8")
    rc = E.main(
        [
            "--repo-root",
            str(tmp_path),
            "--saga-id",
            "issue-398",
            "write",
            "--check-id",
            "qa",
            "--reviewed-sha",
            SHA_A,
            "--producer",
            "qa-gate",
            "--verdict",
            "ship",
            "--artifact-file",
            str(artifact),
        ]
    )
    assert rc == 0
    cli_store = E.Store.for_saga("issue-398", tmp_path)
    result = E.latest(cli_store, check_id="qa", reviewed_sha=SHA_A)
    assert result.verdict == "ship"


def test_evidence_ledger_qa_and_code_review_write_through_no_saga_adhoc_fallback(tmp_path):
    artifact = tmp_path / "code-review.md"
    artifact.write_text("# Code Review\n\nverdict: clean\n", encoding="utf-8")
    saga_id = "adhoc-work-398-evidence-ledger"
    rc = E.main(
        [
            "--repo-root",
            str(tmp_path),
            "--saga-id",
            saga_id,
            "write",
            "--check-id",
            "code-review",
            "--reviewed-sha",
            SHA_B,
            "--producer",
            "code-review-gate",
            "--verdict",
            "clean",
            "--artifact-file",
            str(artifact),
        ]
    )
    assert rc == 0
    assert (tmp_path / "docs" / "evidence" / saga_id / "ledger.jsonl").exists()


def test_evidence_ledger_qa_and_code_review_write_through_cli_full_lifecycle(tmp_path, capsys):
    saga_id = "issue-398"
    criteria_file = tmp_path / "criteria.json"
    criteria_file.write_text(json.dumps({"pass_if": "ok"}), encoding="utf-8")
    assert (
        E.main(
            [
                "--repo-root",
                str(tmp_path),
                "--saga-id",
                saga_id,
                "freeze-criteria",
                "--check-id",
                "qa",
                "--reviewed-sha",
                SHA_A,
                "--criteria-file",
                str(criteria_file),
            ]
        )
        == 0
    )

    artifact = tmp_path / "art.md"
    artifact.write_text("body", encoding="utf-8")
    assert (
        E.main(
            [
                "--repo-root",
                str(tmp_path),
                "--saga-id",
                saga_id,
                "write",
                "--check-id",
                "qa",
                "--reviewed-sha",
                SHA_A,
                "--producer",
                "qa-gate",
                "--verdict",
                "PASS",
                "--artifact-file",
                str(artifact),
            ]
        )
        == 0
    )

    capsys.readouterr()
    assert (
        E.main(
            [
                "--repo-root",
                str(tmp_path),
                "--saga-id",
                saga_id,
                "latest",
                "--check-id",
                "qa",
                "--reviewed-sha",
                SHA_A,
            ]
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "PASS"

    assert E.main(["--repo-root", str(tmp_path), "--saga-id", saga_id, "verify-chain"]) == 0

    assert (
        E.main(
            [
                "--repo-root",
                str(tmp_path),
                "--saga-id",
                saga_id,
                "close",
                "--check-id",
                "qa",
                "--reviewed-sha",
                SHA_A,
                "--verifier",
                "operator",
            ]
        )
        == 0
    )

    # a second close attributed to the producer itself is rejected (non-zero exit, no traceback)
    assert (
        E.main(
            [
                "--repo-root",
                str(tmp_path),
                "--saga-id",
                saga_id,
                "close",
                "--check-id",
                "qa",
                "--reviewed-sha",
                SHA_A,
                "--verifier",
                "qa-gate",
            ]
        )
        == 1
    )


def test_evidence_ledger_qa_and_code_review_write_through_skill_sections_call_the_ledger():
    qa_skill = (ROOT / "plugins" / "saga" / "skills" / "qa" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    cr_skill = (ROOT / "plugins" / "saga" / "skills" / "code-review" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "evidence_ledger.py" in qa_skill
    assert "evidence_ledger.py" in cr_skill
