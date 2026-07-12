"""Tests for the evidence-gated closure gate (#397).

Pins R1-R6 (the five issue-named acceptance behaviors plus the plain unresolved-fail case), R8
(no `required_checks` -> trivially satisfied), R9 (pure read-time derivation, HALT-not-degrade),
KTD2 (close-SHA resolution: override wins, else PR head SHA for a `code` node), KTD3 (supersession
is a `payload["supersession_reason"]` convention), KTD4 (`evidence_ledger.history()` distinguishes
missing- from stale-evidence), and KTD5 (a tampered chain HALTs rather than trusting a stale read).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
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


LEDGER = _load("evidence_ledger")
SPEC = _load("outcome_spec")
GATE = _load("closure_gate")


def _gh(head_ref_oid: dict[str, str] | None = None):
    """A fake ``gh`` runner supporting ``pr view --json headRefOid``."""
    head_ref_oid = head_ref_oid or {}

    def runner(args: list[str], **_kw: Any) -> SimpleNamespace:
        ref = args[3]
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"headRefOid": head_ref_oid.get(ref, "")}),
            stderr="",
        )

    return runner


def _node(sid: str, **kw: Any) -> Any:
    defaults: dict[str, Any] = {
        "subplot_id": sid,
        "title": sid,
        "kind": "code",
        "leaf_saga_id": f"leaf-outcome-{sid}",
        "github": {"pr": "42"},
        "evidence": {},
    }
    defaults.update(kw)
    return SPEC.Node(**defaults)


SHA = "a" * 40


def _store(tmp_path: Path, saga_id: str):
    return LEDGER.Store.for_saga(saga_id, tmp_path)


def test_closure_gate_matching_sha_pass_closes(tmp_path: Path) -> None:
    node = _node("sub1", evidence={"required_checks": ["qa"]})
    store = _store(tmp_path, node.leaf_saga_id)
    LEDGER.write(
        store, check_id="qa", reviewed_sha=SHA, producer="qa-gate", verdict="PASS", content="ok"
    )

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert verdict.satisfied
    assert verdict.halt_reason is None
    assert verdict.checks[0].verdict == "PASS"


def test_closure_gate_golden_fixture_fail_overwritten_by_unexplained_pass(tmp_path: Path) -> None:
    """The grounding-brief incident, reproduced verbatim: a FAIL silently overwritten by a PASS."""
    node = _node("sub2", evidence={"required_checks": ["qa"]})
    store = _store(tmp_path, node.leaf_saga_id)
    LEDGER.write(
        store, check_id="qa", reviewed_sha=SHA, producer="qa-gate", verdict="FAIL", content="bad"
    )
    LEDGER.write(
        store, check_id="qa", reviewed_sha=SHA, producer="qa-gate", verdict="PASS", content="ok"
    )

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert not verdict.satisfied
    assert verdict.halt_reason == "unsuperseded-fail:qa"


def test_closure_gate_fail_superseded_with_justification(tmp_path: Path) -> None:
    node = _node("sub3", evidence={"required_checks": ["qa"]})
    store = _store(tmp_path, node.leaf_saga_id)
    LEDGER.write(
        store, check_id="qa", reviewed_sha=SHA, producer="qa-gate", verdict="FAIL", content="bad"
    )
    LEDGER.write(
        store,
        check_id="qa",
        reviewed_sha=SHA,
        producer="qa-gate",
        verdict="PASS",
        content="ok",
        payload={"supersession_reason": "flaky network mock, re-ran clean"},
    )

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert verdict.satisfied
    assert verdict.checks[0].superseded_fail is True


def test_closure_gate_stale_sha_halts(tmp_path: Path) -> None:
    node = _node("sub4", evidence={"required_checks": ["qa"]})
    store = _store(tmp_path, node.leaf_saga_id)
    other_sha = "b" * 40
    LEDGER.write(
        store,
        check_id="qa",
        reviewed_sha=other_sha,
        producer="qa-gate",
        verdict="PASS",
        content="ok",
    )

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert not verdict.satisfied
    assert verdict.halt_reason == "stale-sha:qa"


def test_closure_gate_missing_evidence_halts(tmp_path: Path) -> None:
    node = _node("sub5", evidence={"required_checks": ["qa"]})

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert not verdict.satisfied
    assert verdict.halt_reason == "missing-evidence:qa"


def test_closure_gate_unresolved_fail_halts(tmp_path: Path) -> None:
    node = _node("sub6", evidence={"required_checks": ["qa"]})
    store = _store(tmp_path, node.leaf_saga_id)
    LEDGER.write(
        store, check_id="qa", reviewed_sha=SHA, producer="qa-gate", verdict="FAIL", content="bad"
    )

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert not verdict.satisfied
    assert verdict.halt_reason == "unresolved-fail:qa"


def test_closure_gate_real_qa_verdict_vocab_no_ship_halts(tmp_path: Path) -> None:
    """The real `/qa` verdict vocabulary (`ship`/`ship-with-deferred`/`no-ship`), not just FAIL/PASS."""
    node = _node("sub6b", evidence={"required_checks": ["qa"]})
    store = _store(tmp_path, node.leaf_saga_id)
    LEDGER.write(
        store, check_id="qa", reviewed_sha=SHA, producer="qa-gate", verdict="no-ship", content="bad"
    )

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert not verdict.satisfied
    assert verdict.halt_reason == "unresolved-fail:qa"


def test_closure_gate_real_qa_verdict_vocab_ship_with_deferred_satisfies(tmp_path: Path) -> None:
    node = _node("sub6c", evidence={"required_checks": ["qa"]})
    store = _store(tmp_path, node.leaf_saga_id)
    LEDGER.write(
        store,
        check_id="qa",
        reviewed_sha=SHA,
        producer="qa-gate",
        verdict="ship-with-deferred",
        content="ok",
    )

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert verdict.satisfied


def test_closure_gate_real_code_review_verdict_vocab_blocked_halts(tmp_path: Path) -> None:
    """The real `/code-review` verdict vocabulary (`clean`/`blocked`)."""
    node = _node("sub6d", evidence={"required_checks": ["code-review"]})
    store = _store(tmp_path, node.leaf_saga_id)
    LEDGER.write(
        store,
        check_id="code-review",
        reviewed_sha=SHA,
        producer="code-review-gate",
        verdict="blocked",
        content="bad",
    )

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert not verdict.satisfied
    assert verdict.halt_reason == "unresolved-fail:code-review"


def test_closure_gate_real_code_review_verdict_vocab_clean_satisfies(tmp_path: Path) -> None:
    node = _node("sub6e", evidence={"required_checks": ["code-review"]})
    store = _store(tmp_path, node.leaf_saga_id)
    LEDGER.write(
        store,
        check_id="code-review",
        reviewed_sha=SHA,
        producer="code-review-gate",
        verdict="clean",
        content="ok",
    )

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert verdict.satisfied


def test_closure_gate_no_ship_superseded_with_justification(tmp_path: Path) -> None:
    """The real-vocab equivalent of the golden fixture: no-ship -> justified ship-with-deferred."""
    node = _node("sub6f", evidence={"required_checks": ["qa"]})
    store = _store(tmp_path, node.leaf_saga_id)
    LEDGER.write(
        store, check_id="qa", reviewed_sha=SHA, producer="qa-gate", verdict="no-ship", content="bad"
    )
    LEDGER.write(
        store,
        check_id="qa",
        reviewed_sha=SHA,
        producer="qa-gate",
        verdict="ship",
        content="ok",
        payload={"supersession_reason": "false positive, re-ran clean"},
    )

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert verdict.satisfied


def test_closure_gate_unrecognized_verdict_halts(tmp_path: Path) -> None:
    """An unrecognized verdict string HALTs rather than being silently treated as a pass."""
    node = _node("sub6g", evidence={"required_checks": ["qa"]})
    store = _store(tmp_path, node.leaf_saga_id)
    LEDGER.write(
        store,
        check_id="qa",
        reviewed_sha=SHA,
        producer="qa-gate",
        verdict="pending-review",
        content="?",
    )

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert not verdict.satisfied
    assert verdict.halt_reason == "unrecognized-verdict:qa"


def test_closure_gate_repeat_fail_pass_cycle(tmp_path: Path) -> None:
    """A second FAIL->justified-PASS cycle after an earlier cycle already resolved.

    Proves the justification check keys off the LATEST entry's own payload, not a once-ever flag.
    """
    node = _node("sub7", evidence={"required_checks": ["qa"]})
    store = _store(tmp_path, node.leaf_saga_id)
    LEDGER.write(
        store, check_id="qa", reviewed_sha=SHA, producer="qa-gate", verdict="FAIL", content="bad-1"
    )
    LEDGER.write(
        store,
        check_id="qa",
        reviewed_sha=SHA,
        producer="qa-gate",
        verdict="PASS",
        content="ok-1",
        payload={"supersession_reason": "fixed the first regression"},
    )
    LEDGER.write(
        store, check_id="qa", reviewed_sha=SHA, producer="qa-gate", verdict="FAIL", content="bad-2"
    )
    LEDGER.write(
        store,
        check_id="qa",
        reviewed_sha=SHA,
        producer="qa-gate",
        verdict="PASS",
        content="ok-2",
        payload={"supersession_reason": "fixed the second regression"},
    )

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert verdict.satisfied


def test_closure_gate_no_required_checks_trivially_satisfied(tmp_path: Path) -> None:
    node = _node("sub8", evidence={})

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh())

    assert verdict.satisfied
    assert verdict.checks == []


def test_closure_gate_reviewed_sha_override_for_non_code_node(tmp_path: Path) -> None:
    node = _node(
        "sub9",
        kind="non-code",
        github={},
        evidence={"required_checks": ["qa"], "reviewed_sha": SHA},
    )
    store = _store(tmp_path, node.leaf_saga_id)
    LEDGER.write(
        store, check_id="qa", reviewed_sha=SHA, producer="qa-gate", verdict="PASS", content="ok"
    )

    verdict = GATE.evaluate(node, repo_root=tmp_path)

    assert verdict.satisfied


def test_closure_gate_unresolvable_close_sha_halts(tmp_path: Path) -> None:
    node = _node("sub10", kind="non-code", github={}, evidence={"required_checks": ["qa"]})

    verdict = GATE.evaluate(node, repo_root=tmp_path)

    assert not verdict.satisfied
    assert verdict.halt_reason == "unresolvable-close-sha"


def test_closure_gate_empty_leaf_saga_id_halts(tmp_path: Path) -> None:
    node = _node("sub11", leaf_saga_id="", evidence={"required_checks": ["qa"]})

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert not verdict.satisfied
    assert verdict.halt_reason == "unresolvable-close-sha"


def test_closure_gate_tamper_detected_halts(tmp_path: Path) -> None:
    node = _node("sub12", evidence={"required_checks": ["qa"]})
    store = _store(tmp_path, node.leaf_saga_id)
    result = LEDGER.write(
        store, check_id="qa", reviewed_sha=SHA, producer="qa-gate", verdict="PASS", content="ok"
    )
    result.artifact_path.write_text("TAMPERED", encoding="utf-8")

    verdict = GATE.evaluate(node, repo_root=tmp_path, github_runner=_gh({"42": SHA}))

    assert not verdict.satisfied
    assert verdict.halt_reason == "chain-tamper:sub12"


def test_closure_gate_cli_evaluate_prints_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    node = _node("sub13", evidence={"required_checks": ["qa"], "reviewed_sha": SHA})
    store = _store(tmp_path, node.leaf_saga_id)
    LEDGER.write(
        store, check_id="qa", reviewed_sha=SHA, producer="qa-gate", verdict="PASS", content="ok"
    )
    spec_obj = SPEC.OutcomeSpec(outcome_id="oc", objective="test", nodes=[node])
    spec_path = tmp_path / "outcome-spec.json"
    spec_path.write_text(spec_obj.to_json(), encoding="utf-8")

    exit_code = GATE.main(
        [
            "--repo-root",
            str(tmp_path),
            "evaluate",
            "--spec",
            str(spec_path),
            "--subplot-id",
            "sub13",
        ]
    )

    assert exit_code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["satisfied"] is True


def test_closure_gate_cli_evaluate_unknown_subplot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    node = _node("sub14")
    spec_obj = SPEC.OutcomeSpec(outcome_id="oc", objective="test", nodes=[node])
    spec_path = tmp_path / "outcome-spec.json"
    spec_path.write_text(spec_obj.to_json(), encoding="utf-8")

    exit_code = GATE.main(
        [
            "--repo-root",
            str(tmp_path),
            "evaluate",
            "--spec",
            str(spec_path),
            "--subplot-id",
            "does-not-exist",
        ]
    )

    assert exit_code == 1
