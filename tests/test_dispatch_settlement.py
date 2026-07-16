"""Dispatch-settlement schema, transitions, casualty reports, DLQ, and leak reads (#351)."""

from __future__ import annotations

import importlib.util
import json
import os
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


DS = _load("dispatch_settlement")
RL = sys.modules["run_ledger"]
AT = "2026-07-16T00:00:00Z"
DIGEST = "a" * 64


def _ledger(tmp_path: Path) -> Any:
    return RL.RunLedger(tmp_path / "run-facts.jsonl")


def _units(count: int = 3) -> list[Any]:
    return [
        DS.UnitSpec(f"unit-{index}", f"stable-{index}", (f"result-{index}",))
        for index in range(count)
    ]


def _manifest(
    ledger: Any,
    *,
    count: int = 3,
    threshold: int = 0,
    max_attempts: int = 3,
    dispatch_id: str = "dispatch-1",
) -> None:
    DS.append_manifest(
        ledger,
        DS.manifest_fact(
            subplot_id="sub-351",
            at=AT,
            dispatch_id=dispatch_id,
            site="outcome",
            units=_units(count),
            casualty_threshold_percent=threshold,
            max_attempts=max_attempts,
        ),
    )


def _spawn(ledger: Any, unit: int, attempt: int = 1, dispatch_id: str = "dispatch-1") -> None:
    DS.append_spawn(
        ledger,
        DS.spawn_fact(
            subplot_id="sub-351",
            at=AT,
            dispatch_id=dispatch_id,
            unit_id=f"unit-{unit}",
            attempt=attempt,
            idempotency_key=f"stable-{unit}",
        ),
    )


def _settle(
    ledger: Any,
    unit: int,
    classification: str = DS.DELIVERED,
    *,
    attempt: int = 1,
    dispatch_id: str = "dispatch-1",
) -> None:
    kwargs = (
        {}
        if classification == DS.SILENT_NOOP
        else {"evidence_ref": f"receipt-{unit}-{attempt}", "evidence_sha256": DIGEST}
    )
    DS.append_settlement(
        ledger,
        DS.settle_fact(
            subplot_id="sub-351",
            at=AT,
            dispatch_id=dispatch_id,
            unit_id=f"unit-{unit}",
            attempt=attempt,
            classification=classification,
            reason=f"classified {classification}",
            **kwargs,
        ),
    )


def test_manifest_is_first_and_file_mode_is_private(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger)
    records = RL.read_facts(ledger)
    assert records[0]["kind"] == "dispatch-settlement"
    assert records[0]["event"] == "manifest"
    assert records[0]["units"][0]["unit_id"] == "unit-0"
    assert os.stat(ledger.path).st_mode & 0o777 == 0o600
    assert os.stat(RL._lock_path(ledger)).st_mode & 0o777 == 0o600


def test_schema_rejects_duplicate_manifest_and_invalid_bounds(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger)
    with pytest.raises(DS.DispatchSettlementError, match="already has a manifest"):
        _manifest(ledger)
    with pytest.raises(DS.DispatchSettlementError, match="0..100"):
        DS.manifest_fact(
            subplot_id="s",
            at=AT,
            dispatch_id="d",
            site="outcome",
            units=_units(1),
            casualty_threshold_percent=101,
        )
    with pytest.raises(DS.DispatchSettlementError, match="1..3"):
        DS.manifest_fact(
            subplot_id="s",
            at=AT,
            dispatch_id="d",
            site="outcome",
            units=_units(1),
            max_attempts=4,
        )


def test_transition_rejects_spawn_without_manifest_and_settle_before_spawn(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(DS.DispatchSettlementError, match="no manifest"):
        _spawn(ledger, 0)
    _manifest(ledger)
    with pytest.raises(DS.DispatchSettlementError, match="matching spawn"):
        _settle(ledger, 0)


def test_transition_rejects_duplicate_spawn_settle_and_attempt_gap(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger)
    _spawn(ledger, 0)
    with pytest.raises(DS.DispatchSettlementError, match="duplicate spawn"):
        _spawn(ledger, 0)
    _settle(ledger, 0, DS.SILENT_NOOP)
    with pytest.raises(DS.DispatchSettlementError, match="duplicate settlement"):
        _settle(ledger, 0, DS.SILENT_NOOP)
    with pytest.raises(DS.DispatchSettlementError, match="attempt gap"):
        _spawn(ledger, 0, 3)


def test_transition_rejects_idempotency_key_drift(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger)
    fact = DS.spawn_fact(
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        unit_id="unit-0",
        attempt=1,
        idempotency_key="changed-key",
    )
    with pytest.raises(DS.DispatchSettlementError, match="idempotency-key drift"):
        DS.append_spawn(ledger, fact)


def test_late_delivery_requires_non_delivered_settle_and_is_write_once(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger)
    _spawn(ledger, 0)
    _settle(ledger, 0, DS.SILENT_NOOP)
    fact = DS.late_delivery_fact(
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        unit_id="unit-0",
        attempt=1,
        evidence_ref="late-artifact",
        evidence_sha256=DIGEST,
    )
    DS.append_late_delivery(ledger, fact)
    with pytest.raises(DS.DispatchSettlementError, match="duplicate late delivery"):
        DS.append_late_delivery(ledger, fact)


def test_casualty_report_names_both(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=5, threshold=50)
    for unit in range(5):
        _spawn(ledger, unit)
        _settle(ledger, unit, DS.RATE_KILLED if unit in {1, 4} else DS.DELIVERED)

    report = DS.settlement_report(ledger, "dispatch-1")

    casualties = [entry for entry in report.entries if entry.classification == DS.RATE_KILLED]
    assert [(entry.unit_id, entry.classification) for entry in casualties] == [
        ("unit-1", "rate-killed"),
        ("unit-4", "rate-killed"),
    ]
    assert report.cohorts[0].casualty_rate_percent == 40.0
    assert not report.halt_required


def test_casualty_rate_halts_only_when_strictly_above_threshold(tmp_path: Path) -> None:
    equal = _ledger(tmp_path / "equal")
    _manifest(equal, count=2, threshold=50)
    for unit in range(2):
        _spawn(equal, unit)
        _settle(equal, unit, DS.SILENT_NOOP if unit == 0 else DS.DELIVERED)
    assert not DS.settlement_report(equal, "dispatch-1").halt_required

    above = _ledger(tmp_path / "above")
    _manifest(above, count=3, threshold=50)
    for unit in range(3):
        _spawn(above, unit)
        _settle(above, unit, DS.SILENT_NOOP if unit < 2 else DS.DELIVERED)
    assert DS.settlement_report(above, "dispatch-1").halt_required


def test_incomplete_cohort_never_claims_threshold_verdict(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=2, threshold=0)
    _spawn(ledger, 0)
    _settle(ledger, 0, DS.SILENT_NOOP)
    report = DS.settlement_report(ledger, "dispatch-1")
    assert not report.cohorts[0].complete
    assert not report.cohorts[0].halt_required
    assert {entry.classification for entry in report.entries} == {"silent-no-op", "unspawned"}


def test_settlement_ignores_self_report(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1)
    _spawn(ledger, 0)
    DS.settle_from_evidence(
        ledger,
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        unit_id="unit-0",
        attempt=1,
        evidence={"self_report": "success", "prose": "I finished everything"},
    )
    entry = DS.settlement_report(ledger, "dispatch-1").entries[0]
    assert entry.classification == DS.SILENT_NOOP
    assert "self-report" in entry.reason


def test_complete_trusted_manifest_is_delivery_evidence(tmp_path: Path) -> None:
    evidence = {
        "receipt_type": "worker-manifest",
        "trusted": True,
        "outputs": ["result-0"],
        "evidence_ref": "manifest-0",
        "evidence_sha256": DIGEST,
    }
    result = DS.classify_evidence(["result-0"], evidence)
    assert result.classification == DS.DELIVERED
    assert result.evidence_ref == "manifest-0"


def test_incomplete_manifest_is_not_delivered(tmp_path: Path) -> None:
    evidence = {
        "receipt_type": "worker-manifest",
        "trusted": True,
        "outputs": [],
        "evidence_ref": "manifest-0",
        "evidence_sha256": DIGEST,
    }
    result = DS.classify_evidence(["result-0"], evidence)
    assert result.classification == DS.SILENT_NOOP
    assert "missing required outputs" in result.reason


def test_unknown_or_untrusted_evidence_halts(tmp_path: Path) -> None:
    with pytest.raises(DS.DispatchSettlementError, match="unknown evidence"):
        DS.classify_evidence(["result"], {"receipt_type": "agent-prose", "trusted": True})
    with pytest.raises(DS.DispatchSettlementError, match="host-trusted"):
        DS.classify_evidence(
            ["result"],
            {
                "receipt_type": "artifact",
                "trusted": False,
                "outputs": ["result"],
                "evidence_ref": "result",
                "evidence_sha256": DIGEST,
            },
        )


def test_three_spawn_two_reap_one_open(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger)
    for unit in range(3):
        _spawn(ledger, unit)
    _settle(ledger, 0)
    _settle(ledger, 1)
    positions = DS.open_positions(ledger)
    assert len(positions) == 1
    assert positions[0]["unit_id"] == "unit-2"


def test_no_ack_lands_in_dlq_after_bounded_retries(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1, max_attempts=2)
    _spawn(ledger, 0)
    _settle(ledger, 0, DS.SILENT_NOOP)
    first = DS.dead_letters(ledger, "dispatch-1")
    assert [(item.unit_id, item.next_attempt) for item in first] == [("unit-0", 2)]
    DS.claim_retry(
        ledger,
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        unit_id="unit-0",
    )
    _settle(ledger, 0, DS.SILENT_NOOP, attempt=2)
    assert DS.dead_letters(ledger, "dispatch-1") == []
    assert DS.settlement_report(ledger, "dispatch-1").entries[-1].classification == DS.SILENT_NOOP


def test_dlq_redispatch_is_idempotent(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1)
    _spawn(ledger, 0)
    _settle(ledger, 0, DS.RATE_KILLED)
    retry = DS.claim_retry(
        ledger,
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        unit_id="unit-0",
    )
    assert retry["attempt"] == 2
    assert retry["idempotency_key"] == "stable-0"
    with pytest.raises(DS.DispatchSettlementError, match="not currently retry-eligible"):
        DS.claim_retry(
            ledger,
            subplot_id="sub-351",
            at=AT,
            dispatch_id="dispatch-1",
            unit_id="unit-0",
        )


def test_late_delivery_before_retry_removes_dlq_entry(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1)
    _spawn(ledger, 0)
    _settle(ledger, 0, DS.SILENT_NOOP)
    DS.append_late_delivery(
        ledger,
        DS.late_delivery_fact(
            subplot_id="sub-351",
            at=AT,
            dispatch_id="dispatch-1",
            unit_id="unit-0",
            attempt=1,
            evidence_ref="late-result",
            evidence_sha256=DIGEST,
        ),
    )
    assert DS.dead_letters(ledger, "dispatch-1") == []
    with pytest.raises(DS.DispatchSettlementError, match="not currently retry-eligible"):
        DS.claim_retry(
            ledger,
            subplot_id="sub-351",
            at=AT,
            dispatch_id="dispatch-1",
            unit_id="unit-0",
        )


def test_late_delivery_after_retry_does_not_cancel_inflight_retry(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1)
    _spawn(ledger, 0)
    _settle(ledger, 0, DS.SILENT_NOOP)
    DS.claim_retry(
        ledger,
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        unit_id="unit-0",
    )
    DS.append_late_delivery(
        ledger,
        DS.late_delivery_fact(
            subplot_id="sub-351",
            at=AT,
            dispatch_id="dispatch-1",
            unit_id="unit-0",
            attempt=1,
            evidence_ref="late-result",
            evidence_sha256=DIGEST,
        ),
    )
    positions = DS.open_positions(ledger)
    assert [(item["unit_id"], item["attempt"]) for item in positions] == [("unit-0", 2)]


def test_stale_worktrees_flagged_as_debit_without_mutation(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    before = set(tmp_path.rglob("*"))
    result = DS.reconcile_leaks(
        ledger,
        stale_worktrees=[
            {
                "dispatch_id": "outcome-1",
                "unit_id": "sub-stale",
                "attempt": 1,
                "worktree": ".claude/worktrees/stale",
            }
        ],
    )
    assert result["open_count"] == 1
    assert result["stale_worktrees"][0]["classification"] == "leaked-worktree"
    assert set(tmp_path.rglob("*")) == before


def test_broken_chain_refuses_reports_and_writes(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger)
    record = json.loads(ledger.path.read_text())
    record["site"] = "workflow"
    ledger.path.write_text(json.dumps(record) + "\n")
    with pytest.raises(DS.DispatchSettlementError, match="broken run-fact chain"):
        DS.settlement_report(ledger, "dispatch-1")
    with pytest.raises(RL.RunLedgerError, match="broken run-fact chain"):
        _spawn(ledger, 0)


def test_read_views_on_absent_ledger_create_no_files(tmp_path: Path) -> None:
    ledger = RL.RunLedger(tmp_path / "absent" / "run-facts.jsonl")
    assert DS.open_positions(ledger) == []
    assert DS.dead_letters(ledger) == []
    assert DS.reconcile_leaks(ledger)["open_count"] == 0
    assert not ledger.path.parent.exists()


def test_workflow_settlement_metadata_is_deterministic_and_filesystem_free() -> None:
    first = DS.settlement_metadata(
        dispatch_id="workflow-1", site="workflow", units=_units(2), casualty_threshold_percent=20
    )
    second = DS.settlement_metadata(
        dispatch_id="workflow-1", site="workflow", units=_units(2), casualty_threshold_percent=20
    )
    assert first == second
    assert DS.evidence_digest(first) == DS.evidence_digest(second)
    assert set(first) == {
        "schema",
        "dispatch_id",
        "site",
        "units",
        "casualty_threshold_percent",
        "max_attempts",
    }


def test_cli_manifest_spawn_settle_report_round_trip(tmp_path: Path, capsys: Any) -> None:
    ledger_path = tmp_path / "facts.jsonl"
    common = ["--ledger-path", str(ledger_path), "--subplot-id", "sub-351"]
    assert (
        DS.main(
            [
                *common,
                "manifest",
                "--dispatch-id",
                "cli-dispatch",
                "--site",
                "team-execution",
                "--units-json",
                json.dumps([_units(1)[0].to_dict()]),
                "--at",
                AT,
            ]
        )
        == 0
    )
    assert (
        DS.main(
            [
                *common,
                "spawn",
                "--dispatch-id",
                "cli-dispatch",
                "--unit-id",
                "unit-0",
                "--attempt",
                "1",
                "--idempotency-key",
                "stable-0",
                "--at",
                AT,
            ]
        )
        == 0
    )
    assert (
        DS.main(
            [
                *common,
                "settle",
                "--dispatch-id",
                "cli-dispatch",
                "--unit-id",
                "unit-0",
                "--attempt",
                "1",
                "--classification",
                "silent-no-op",
                "--reason",
                "no trusted manifest",
                "--at",
                AT,
            ]
        )
        == 0
    )
    assert DS.main([*common, "report", "--dispatch-id", "cli-dispatch"]) == 0
    output = capsys.readouterr().out
    assert '"classification": "silent-no-op"' in output
