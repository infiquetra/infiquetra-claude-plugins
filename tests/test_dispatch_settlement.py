"""Dispatch-settlement schema, transitions, casualty reports, DLQ, and leak reads (#351)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
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
PM = _load("provenance_manifest")
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


def _descriptor(
    path: Path, *, unit_id: str = "unit-0", receipt_type: str = "artifact"
) -> dict[str, str]:
    return {
        "receipt_type": receipt_type,
        "unit_id": unit_id,
        "evidence_path": path.name,
    }


def _reviewer_artifact(
    path: Path, *, unit_id: str = "unit-0", payload: dict[str, Any] | None = None
) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema": DS.ARTIFACT_RECEIPT_SCHEMA,
                "kind": "reviewer-result",
                "unit_id": unit_id,
                "payload": payload
                or {
                    "reviewer": unit_id,
                    "score": 9.5,
                    "dimension_scores": {"correctness": 9.5},
                    "findings": [],
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _worker_manifest(path: Path, *, produced: list[str], missing: list[str] | None = None) -> Path:
    manifest = PM.Manifest(
        execution_id="unit-0",
        saga_ref="issue-351",
        attribution=PM.Attribution(PM.ProducerKind.TEAM_EXECUTION, "unit-0"),
        disposition=PM.Disposition.RAN_AS_REQUESTED,
        created_at=AT,
        output_completeness=PM.OutputCompleteness(
            declared_keys=("result-0",),
            produced_keys=tuple(produced),
            missing_keys=tuple(missing or []),
        ),
    )
    path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    return path


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


def test_appenders_reject_noncanonical_raw_fact_shapes(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    manifest = DS.manifest_fact(
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        site="outcome",
        units=_units(1),
    )
    with pytest.raises(DS.DispatchSettlementError, match="extra"):
        DS.append_manifest(ledger, {**manifest, "unexpected": True})
    DS.append_manifest(ledger, manifest)

    spawn = DS.spawn_fact(
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        unit_id="unit-0",
        attempt=1,
        idempotency_key="stable-0",
    )
    with pytest.raises(DS.DispatchSettlementError, match="integer >= 1"):
        DS.append_spawn(ledger, {**spawn, "attempt": True})
    DS.append_spawn(ledger, spawn)

    settlement = DS.settle_fact(
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        unit_id="unit-0",
        attempt=1,
        classification=DS.DELIVERED,
        reason="complete",
        evidence_ref="receipt",
        evidence_sha256=DIGEST,
    )
    settlement.pop("evidence_ref")
    with pytest.raises(DS.DispatchSettlementError, match="evidence_ref"):
        DS.append_settlement(ledger, settlement)

    late = DS.late_delivery_fact(
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        unit_id="unit-0",
        attempt=1,
        evidence_ref="late",
        evidence_sha256=DIGEST,
    )
    with pytest.raises(DS.DispatchSettlementError, match="extra"):
        DS.append_late_delivery(ledger, {**late, "classification": DS.DELIVERED})


def test_semantically_invalid_hash_valid_fact_breaks_settlement_reads(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1)
    malformed = DS.spawn_fact(
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        unit_id="unit-0",
        attempt=1,
        idempotency_key="stable-0",
    )
    RL.append_fact(ledger, {**malformed, "unexpected": "hash-valid"})
    assert RL.verify_chain(ledger).ok
    with pytest.raises(DS.DispatchSettlementError, match="malformed dispatch-settlement fact"):
        DS.settlement_report(ledger, "dispatch-1")


def test_fact_timestamp_must_be_iso_utc() -> None:
    with pytest.raises(DS.DispatchSettlementError, match="ISO-8601 UTC"):
        DS.spawn_fact(
            subplot_id="sub-351",
            at="tomorrow",
            dispatch_id="dispatch-1",
            unit_id="unit-0",
            attempt=1,
            idempotency_key="stable-0",
        )


@pytest.mark.parametrize(
    "bad", [None, True, 1, [], {}], ids=["null", "bool", "int", "list", "object"]
)
def test_closed_string_fields_reject_non_strings(bad: object) -> None:
    with pytest.raises(DS.DispatchSettlementError, match="safe identifier characters"):
        DS.manifest_fact(
            subplot_id="sub-351",
            at=AT,
            dispatch_id=bad,
            site="outcome",
            units=_units(1),
        )
    with pytest.raises(DS.DispatchSettlementError, match="printable text"):
        DS.settle_fact(
            subplot_id="sub-351",
            at=AT,
            dispatch_id="dispatch-1",
            unit_id="unit-0",
            attempt=1,
            classification=DS.SILENT_NOOP,
            reason=bad,
        )
    with pytest.raises(DS.DispatchSettlementError, match="lowercase SHA-256"):
        DS.settle_fact(
            subplot_id="sub-351",
            at=AT,
            dispatch_id="dispatch-1",
            unit_id="unit-0",
            attempt=1,
            classification=DS.DELIVERED,
            reason="complete",
            evidence_ref="receipt",
            evidence_sha256=bad,
        )


def test_hash_valid_non_string_identifier_breaks_settlement_reads(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    malformed = DS.manifest_fact(
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        site="outcome",
        units=_units(1),
    )
    malformed["units"][0]["unit_id"] = None
    RL.append_fact(ledger, malformed)
    assert RL.verify_chain(ledger).ok
    with pytest.raises(DS.DispatchSettlementError, match="safe identifier characters"):
        DS.settlement_report(ledger, "dispatch-1")


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


def test_concurrent_duplicate_spawn_has_one_winner_and_valid_chain(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1)
    barrier = threading.Barrier(2)

    def write() -> str:
        barrier.wait(timeout=10)
        try:
            _spawn(ledger, 0)
        except DS.DispatchSettlementError as exc:
            return str(exc)
        return "written"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result() for future in (pool.submit(write), pool.submit(write))]

    assert sorted(results) == ["duplicate spawn attempt", "written"]
    records = RL.read_facts(ledger)
    spawns = [record for record in records if record.get("event") == DS.EVENT_SPAWN]
    assert len(spawns) == 1
    assert RL.verify_chain(ledger).ok


def test_concurrent_distinct_spawns_are_not_lost(tmp_path: Path) -> None:
    count = 8
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=count)
    barrier = threading.Barrier(count)

    def write(unit: int) -> None:
        barrier.wait(timeout=10)
        _spawn(ledger, unit)

    with ThreadPoolExecutor(max_workers=count) as pool:
        list(pool.map(write, range(count)))

    records = RL.read_facts(ledger)
    spawns = [record for record in records if record.get("event") == DS.EVENT_SPAWN]
    assert {record["unit_id"] for record in spawns} == {f"unit-{unit}" for unit in range(count)}
    assert RL.verify_chain(ledger).ok


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


def test_late_delivery_requires_complete_persisted_evidence(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1)
    _spawn(ledger, 0)
    _settle(ledger, 0, DS.SILENT_NOOP)
    artifact = _worker_manifest(tmp_path / "late.json", produced=["result-0"])

    result = DS.append_late_delivery_from_evidence(
        ledger,
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        unit_id="unit-0",
        attempt=1,
        evidence=_descriptor(artifact, receipt_type="worker-manifest"),
        evidence_root=tmp_path,
    )

    assert result["event"] == DS.EVENT_LATE_DELIVERY
    assert DS.dead_letters(ledger, "dispatch-1") == []


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


def test_retry_casualty_uses_retry_cohort_denominator(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=10, threshold=10)
    for unit in range(10):
        _spawn(ledger, unit)
        _settle(ledger, unit, DS.SILENT_NOOP if unit == 0 else DS.DELIVERED)
    assert not DS.settlement_report(ledger, "dispatch-1").halt_required

    DS.claim_retry(
        ledger,
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        unit_id="unit-0",
    )
    _settle(ledger, 0, DS.SILENT_NOOP, attempt=2)

    report = DS.settlement_report(ledger, "dispatch-1")
    assert report.cohorts[1].casualty_rate_percent == 100.0
    assert report.halt_required


def test_incomplete_cohort_never_claims_threshold_verdict(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=2, threshold=0)
    _spawn(ledger, 0)
    _settle(ledger, 0, DS.SILENT_NOOP)
    report = DS.settlement_report(ledger, "dispatch-1")
    assert not report.cohorts[0].complete
    assert not report.cohorts[0].halt_required
    assert report.halt_required
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
    path = _worker_manifest(tmp_path / "manifest.json", produced=["result-0"])
    evidence = _descriptor(path, receipt_type="worker-manifest")
    result = DS.classify_evidence(
        ["result-0"], evidence, expected_unit_id="unit-0", evidence_root=tmp_path
    )
    assert result.classification == DS.DELIVERED
    assert result.evidence_ref.startswith("worker-manifest:sha256:")
    assert result.evidence_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_incomplete_manifest_is_not_delivered(tmp_path: Path) -> None:
    path = _worker_manifest(tmp_path / "manifest.json", produced=[], missing=["result-0"])
    result = DS.classify_evidence(
        ["result-0"],
        _descriptor(path, receipt_type="worker-manifest"),
        expected_unit_id="unit-0",
        evidence_root=tmp_path,
    )
    assert result.classification == DS.SILENT_NOOP
    assert "missing required outputs" in result.reason


def test_unknown_or_untrusted_evidence_halts(tmp_path: Path) -> None:
    with pytest.raises(DS.DispatchSettlementError, match="exactly"):
        DS.classify_evidence(
            ["result"],
            {
                "receipt_type": "artifact",
                "trusted": True,
                "unit_id": "unit-0",
                "outputs": ["result"],
                "evidence_ref": "fake",
                "evidence_sha256": DIGEST,
            },
        )
    with pytest.raises(DS.DispatchSettlementError, match="under evidence_root"):
        DS.classify_evidence(
            ["result"],
            _descriptor(tmp_path / "missing.json"),
            evidence_root=tmp_path,
        )


def test_artifact_derives_review_output_only_from_validated_payload(tmp_path: Path) -> None:
    path = _reviewer_artifact(tmp_path / "reviewer.json")
    result = DS.classify_evidence(
        ["scored-review"],
        _descriptor(path),
        expected_unit_id="unit-0",
        evidence_root=tmp_path,
    )
    assert result.classification == DS.DELIVERED

    forged = _reviewer_artifact(
        tmp_path / "forged.json",
        payload={"prose": "Everything passed.", "outputs": ["scored-review"]},
    )
    with pytest.raises(DS.DispatchSettlementError, match="reviewer artifact identity"):
        DS.classify_evidence(
            ["scored-review"],
            _descriptor(forged),
            expected_unit_id="unit-0",
            evidence_root=tmp_path,
        )


def test_evidence_schema_rejects_wrong_unit_and_extra_fields(tmp_path: Path) -> None:
    path = _worker_manifest(tmp_path / "artifact.json", produced=["result-0"])
    evidence = _descriptor(path, unit_id="other-unit", receipt_type="worker-manifest")
    with pytest.raises(DS.DispatchSettlementError, match="does not match"):
        DS.classify_evidence(
            ["result-0"], evidence, expected_unit_id="unit-0", evidence_root=tmp_path
        )
    with pytest.raises(DS.DispatchSettlementError, match="exactly"):
        DS.classify_evidence(
            ["result-0"],
            {**evidence, "unit_id": "unit-0", "classification": DS.DELIVERED},
            expected_unit_id="unit-0",
            evidence_root=tmp_path,
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


def test_concurrent_retry_claim_has_one_winner_and_valid_chain(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1)
    _spawn(ledger, 0)
    _settle(ledger, 0, DS.RATE_KILLED)
    barrier = threading.Barrier(2)

    def claim() -> str:
        barrier.wait(timeout=10)
        try:
            result = DS.claim_retry(
                ledger,
                subplot_id="sub-351",
                at=AT,
                dispatch_id="dispatch-1",
                unit_id="unit-0",
            )
        except DS.DispatchSettlementError as exc:
            return str(exc)
        assert result["idempotency_key"] == "stable-0"
        return "written"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result() for future in (pool.submit(claim), pool.submit(claim))]

    assert results.count("written") == 1
    assert len([result for result in results if result != "written"]) == 1
    spawns = [
        record
        for record in RL.read_facts(ledger)
        if record.get("event") == DS.EVENT_SPAWN and record.get("attempt") == 2
    ]
    assert len(spawns) == 1
    assert spawns[0]["idempotency_key"] == "stable-0"
    assert RL.verify_chain(ledger).ok


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


def test_attempt_bound_delivery_never_settles_a_newer_retry(tmp_path: Path) -> None:
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

    result = DS.settle_attempt(
        ledger,
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        unit_id="unit-0",
        attempt=1,
        classification=DS.DELIVERED,
        reason="attempt one arrived late",
        evidence_ref="attempt-one-result",
        evidence_sha256=DIGEST,
    )

    assert result["event"] == DS.EVENT_LATE_DELIVERY
    assert [(item["unit_id"], item["attempt"]) for item in DS.open_positions(ledger)] == [
        ("unit-0", 2)
    ]


def test_settle_attempt_rejects_contradictory_replay_evidence(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1)
    _spawn(ledger, 0)
    _settle(ledger, 0, DS.DELIVERED)

    with pytest.raises(DS.DispatchSettlementError, match="contradictory settlement evidence"):
        DS.settle_attempt(
            ledger,
            subplot_id="sub-351",
            at=AT,
            dispatch_id="dispatch-1",
            unit_id="unit-0",
            attempt=1,
            classification=DS.DELIVERED,
            reason="different delivery claim",
            evidence_ref="different-receipt",
            evidence_sha256="b" * 64,
        )


def test_prepare_attempt_returns_retry_exhausted_without_raising(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1, max_attempts=1)
    _spawn(ledger, 0)
    _settle(ledger, 0, DS.SILENT_NOOP)

    result = DS.prepare_attempt(
        ledger,
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        site="outcome",
        unit=_units(1)[0],
        max_attempts=1,
    )

    assert result["status"] == "retry-exhausted"
    assert result["attempt"] == 1


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

    with pytest.raises(DS.DispatchSettlementError, match="integer >= 1"):
        DS.reconcile_leaks(
            ledger,
            stale_worktrees=[
                {
                    "dispatch_id": "outcome-1",
                    "unit_id": "sub-stale",
                    "attempt": True,
                    "worktree": ".claude/worktrees/stale",
                }
            ],
        )


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


def test_outcome_dispatch_identity_is_unambiguous_for_colon_ids(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    first_id, first_units = DS.outcome_frontier_identity("parent", ["unit-0"])
    second_id, second_units = DS.outcome_frontier_identity("parent:child", ["unit-0"])
    assert first_id != second_id
    for outcome_id, dispatch_id, units in (
        ("parent", first_id, first_units),
        ("parent:child", second_id, second_units),
    ):
        DS.append_manifest(
            ledger,
            DS.manifest_fact(
                subplot_id=outcome_id,
                at=AT,
                dispatch_id=dispatch_id,
                site="outcome",
                units=units,
            ),
        )
    bindings = DS.outcome_dispatch_bindings(ledger, "parent", ["unit-0"])
    assert bindings["unit-0"][0] == first_id


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
                "--evidence-json",
                "null",
                "--at",
                AT,
            ]
        )
        == 0
    )
    assert DS.main([*common, "report", "--dispatch-id", "cli-dispatch"]) == 0
    output = capsys.readouterr().out
    assert '"classification": "silent-no-op"' in output


def test_cli_manifest_exact_replay_is_idempotent(tmp_path: Path, capsys: Any) -> None:
    ledger_path = tmp_path / "facts.jsonl"
    command = [
        "--ledger-path",
        str(ledger_path),
        "--subplot-id",
        "sub-351",
        "manifest",
        "--dispatch-id",
        "cli-dispatch",
        "--site",
        "workflow",
        "--units-json",
        json.dumps([_units(1)[0].to_dict()]),
        "--at",
        AT,
    ]

    assert DS.main(command) == 0
    assert DS.main(command) == 0

    records = RL.read_facts(RL.RunLedger(ledger_path))
    assert len([record for record in records if record.get("event") == DS.EVENT_MANIFEST]) == 1
    capsys.readouterr()


def test_cli_read_views_have_deterministic_text_format(tmp_path: Path, capsys: Any) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1)
    _spawn(ledger, 0)
    _settle(ledger, 0, DS.SILENT_NOOP)
    common = ["--ledger-path", str(ledger.path), "--subplot-id", "sub-351"]

    assert DS.main([*common, "report", "--dispatch-id", "dispatch-1", "--format", "text"]) == 0
    report = capsys.readouterr().out
    assert "dispatch dispatch-1 site=outcome halt_required=true" in report
    assert "unit-0 attempt=1 classification=silent-no-op" in report

    assert DS.main([*common, "dlq", "--dispatch-id", "dispatch-1", "--format", "text"]) == 0
    assert "dispatch-1/unit-0 attempt=1->2" in capsys.readouterr().out

    assert DS.main([*common, "reconcile", "--leaks", "--format", "text"]) == 0
    assert capsys.readouterr().out == "open_positions=0\n"


# ------------------------------------------------------------------ operator waivers (#618)


def _waive(
    ledger: Any,
    *,
    dispatch_id: str = "dispatch-1",
    reason: str = "operator waiver",
    waived_by: str = "jeff",
    transport: str = "",
) -> dict[str, Any]:
    result: dict[str, Any] = DS.record_waiver(
        ledger,
        subplot_id="sub-351",
        at=AT,
        dispatch_id=dispatch_id,
        waived_by=waived_by,
        reason=reason,
        transport=transport,
    )
    return result


def _waiver_facts(ledger: Any) -> list[dict[str, Any]]:
    return [rec for rec in RL.read_facts(ledger) if rec.get("kind") == DS.WAIVER_KIND]


def test_waiver_happy_path_covers_open_units(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=2)
    _spawn(ledger, 0)
    _spawn(ledger, 1)
    result = _waive(ledger, transport="terminal")
    assert result["appended"] is True
    record = result["record"]
    assert record["kind"] == DS.WAIVER_KIND
    assert record["waived_by"] == "jeff"
    assert record["transport"] == "terminal"
    assert record["reason"] == "operator waiver"
    assert record["waived_roster"] == [["unit-0", 1, "open"], ["unit-1", 1, "open"]]
    assert record["roster_digest"] == DS.evidence_digest(record["waived_roster"])
    report = DS.settlement_report(ledger, "dispatch-1")
    assert report.halt_required is True
    assert DS.active_waiver_covers(ledger, report) is True


def test_waiver_survives_delivery_shrinking_roster(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=2)
    _spawn(ledger, 0)
    _spawn(ledger, 1)
    _waive(ledger)
    _settle(ledger, 0)  # delivered: the roster shrinks, the waiver keeps covering (KTD3)
    report = DS.settlement_report(ledger, "dispatch-1")
    assert report.halt_required is True
    assert DS.blocking_roster(ledger, "dispatch-1") == frozenset({("unit-1", 1, "open")})
    assert DS.active_waiver_covers(ledger, report) is True


def test_waiver_stale_after_new_casualty(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=2)
    _spawn(ledger, 0)
    _spawn(ledger, 1)
    _waive(ledger)
    _settle(ledger, 0, DS.RATE_KILLED)  # a NEW blocking pair falls outside the snapshot
    report = DS.settlement_report(ledger, "dispatch-1")
    assert report.halt_required is True
    assert DS.active_waiver_covers(ledger, report) is False


def test_waiver_stale_after_new_attempt_cohort(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=2)
    _spawn(ledger, 0)
    _spawn(ledger, 1)
    _settle(ledger, 0, DS.RATE_KILLED)
    _waive(ledger)
    report = DS.settlement_report(ledger, "dispatch-1")
    assert DS.active_waiver_covers(ledger, report) is True
    _spawn(ledger, 0, attempt=2)  # retry cohort: a new open pair re-halts unwaived
    report = DS.settlement_report(ledger, "dispatch-1")
    assert report.halt_required is True
    assert DS.active_waiver_covers(ledger, report) is False


def test_waiver_requires_manifest(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(DS.DispatchSettlementError, match="no manifest"):
        _waive(ledger)


def test_waiver_refuses_healthy_cohort(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1)
    _spawn(ledger, 0)
    _settle(ledger, 0)
    with pytest.raises(DS.DispatchSettlementError, match="not halt-required"):
        _waive(ledger)


def test_waiver_duplicate_grant_is_reported_noop(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=2)
    _spawn(ledger, 0)
    _spawn(ledger, 1)
    first = _waive(ledger)
    second = _waive(ledger, reason="same roster, different wording")
    assert second["appended"] is False
    assert second["record"]["this_hash"] == first["record"]["this_hash"]
    assert len(_waiver_facts(ledger)) == 1


def test_rewaive_after_roster_change_appends_a_second_fact(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=2)
    _spawn(ledger, 0)
    _spawn(ledger, 1)
    first = _waive(ledger)
    _settle(ledger, 0, DS.RATE_KILLED)
    second = _waive(ledger, reason="casualty acknowledged")
    assert second["appended"] is True
    assert second["record"]["roster_digest"] != first["record"]["roster_digest"]
    report = DS.settlement_report(ledger, "dispatch-1")
    assert DS.active_waiver_covers(ledger, report) is True
    assert len(_waiver_facts(ledger)) == 2


def test_old_readers_ignore_waiver_facts(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=2)
    _spawn(ledger, 0)
    _spawn(ledger, 1)
    _waive(ledger)
    # The settlement stream never sees the new kind: reports, open positions, and later appends
    # all succeed, and the hash chain still verifies (R5 fail-closed isolation).
    report = DS.settlement_report(ledger, "dispatch-1")
    assert [entry.classification for entry in report.entries] == ["open", "open"]
    assert RL.verify_chain(ledger).ok is True
    _settle(ledger, 0)
    assert DS.settlement_report(ledger, "dispatch-1").halt_required is True
    assert {pos["unit_id"] for pos in DS.open_positions(ledger)} == {"unit-1"}


def test_waiver_field_bounds(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1)
    _spawn(ledger, 0)
    with pytest.raises(DS.DispatchSettlementError, match="reason"):
        _waive(ledger, reason="")
    with pytest.raises(DS.DispatchSettlementError, match="waived_by"):
        _waive(ledger, waived_by="")
    with pytest.raises(DS.DispatchSettlementError, match="reason"):
        _waive(ledger, reason="x" * 501)
    with pytest.raises(DS.DispatchSettlementError, match="waived_roster state"):
        DS.waiver_fact(
            subplot_id="sub-351",
            at=AT,
            dispatch_id="dispatch-1",
            waived_by="jeff",
            reason="bad state",
            waived_roster=[("unit-0", 1, DS.DELIVERED)],
        )
    with pytest.raises(DS.DispatchSettlementError, match="at least one blocking pair"):
        DS.waiver_fact(
            subplot_id="sub-351",
            at=AT,
            dispatch_id="dispatch-1",
            waived_by="jeff",
            reason="empty roster",
            waived_roster=[],
        )


def test_stored_waiver_fact_with_extra_field_breaks_waiver_reads(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=1)
    _spawn(ledger, 0)
    fact = DS.waiver_fact(
        subplot_id="sub-351",
        at=AT,
        dispatch_id="dispatch-1",
        waived_by="jeff",
        reason="tampered",
        waived_roster=[("unit-0", 1, "open")],
    )
    fact["surprise"] = True
    RL.append_fact(ledger, fact)
    report = DS.settlement_report(ledger, "dispatch-1")  # settlement readers stay unaffected
    with pytest.raises(DS.DispatchSettlementError, match="extra=\\['surprise'\\]"):
        DS.active_waiver_covers(ledger, report)


def test_blocking_roster_empty_iff_halt_false(tmp_path: Path) -> None:
    """Property pin: roster-empty <=> halt-false at every step, incl. the late-delivery resolve."""
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=2)

    def check() -> None:
        report = DS.settlement_report(ledger, "dispatch-1")
        roster = DS.blocking_roster(ledger, "dispatch-1")
        assert (roster == frozenset()) == (report.halt_required is False)

    check()  # both unspawned
    _spawn(ledger, 0)
    check()  # open + unspawned
    _spawn(ledger, 1)
    check()  # both open
    _settle(ledger, 0, DS.RATE_KILLED)
    check()  # casualty + open
    _settle(ledger, 1)
    check()  # complete, unresolved breach at threshold 0
    assert DS.blocking_roster(ledger, "dispatch-1") == frozenset({("unit-0", 1, DS.RATE_KILLED)})
    DS.append_late_delivery(
        ledger,
        DS.late_delivery_fact(
            subplot_id="sub-351",
            at=AT,
            dispatch_id="dispatch-1",
            unit_id="unit-0",
            attempt=1,
            evidence_ref="receipt-late-0",
            evidence_sha256=DIGEST,
        ),
    )
    # entries still say rate-killed, but latest_states says delivered — the roster must follow
    # the halt derivation, not the entries.
    report = DS.settlement_report(ledger, "dispatch-1")
    assert report.halt_required is False
    assert DS.blocking_roster(ledger, "dispatch-1") == frozenset()


def test_cli_waive_verb_roundtrip_and_error_paths(tmp_path: Path, capsys: Any) -> None:
    ledger = _ledger(tmp_path)
    _manifest(ledger, count=2)
    _spawn(ledger, 0)
    _spawn(ledger, 1)
    common = ["--ledger-path", str(ledger.path), "--subplot-id", "sub-351"]
    assert (
        DS.main(
            [
                *common,
                "waive",
                "--dispatch-id",
                "dispatch-1",
                "--at",
                AT,
                "--waived-by",
                "jeff",
                "--reason",
                "unblock new frontier dispatch",
                "--transport",
                "terminal",
            ]
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["appended"] is True
    assert out["record"]["transport"] == "terminal"
    assert (
        DS.main(
            [
                *common,
                "waive",
                "--dispatch-id",
                "missing-dispatch",
                "--at",
                AT,
                "--waived-by",
                "jeff",
                "--reason",
                "no such cohort",
            ]
        )
        == 1
    )
    assert "no manifest" in capsys.readouterr().err
