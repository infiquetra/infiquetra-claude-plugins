"""Read-only orphan projection contract tests (#355)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "plugins" / "saga" / "scripts" / "reap_orphans.py"
FLEET = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "orphan_evidence.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R = _load("reap_orphans", SCRIPT)
OE = _load("orphan_evidence_test", FLEET)

TOKEN: dict[str, Any] = {
    "broker_epoch": "11111111-1111-4111-8111-111111111111",
    "fencing_sequence": 7,
}
RESOURCE = {"logical_unit_id": "issue-355"}
LEASE_ID = "22222222-2222-4222-8222-222222222222"


def _head(*, token: dict[str, object] = TOKEN, close: dict[str, object] | None = None) -> dict:
    return {
        "resource_ref": RESOURCE,
        "broker_epoch": token["broker_epoch"],
        "fencing_sequence": token["fencing_sequence"],
        "lease_id": LEASE_ID,
        "close_receipt": close,
    }


def _lease(state: str = "expired", *, token: dict[str, object] = TOKEN) -> dict:
    return {
        "lease_id": LEASE_ID,
        "resource_ref": RESOURCE,
        "broker_epoch": token["broker_epoch"],
        "fencing_sequence": token["fencing_sequence"],
        "derived_state": state,
    }


def _snapshot(
    *sources: dict,
    head: dict | None = None,
    archived: dict[str, dict] | None = None,
    leases: list[dict] | None = None,
) -> dict:
    selected = head or _head()
    return {
        "schema": "orphan-projection-snapshot.v1",
        "broker_heads": {OE.resource_sha256(RESOURCE): selected},
        "archived_broker_heads": archived or {},
        "broker_leases": [_lease()] if leases is None else leases,
        "sources": list(sources),
    }


def _close() -> dict[str, Any]:
    close = {
        "schema": "settlement_close.v1",
        "resource_ref": RESOURCE,
        "token": TOKEN,
        "lease_id": LEASE_ID,
        "settlement_id": "44444444-4444-4444-8444-444444444444",
        "session_id": "close-session",
        "policy_sha256": "d" * 64,
        "generation": OE.generation(TOKEN),
        "phase": "closed",
        "producer": "team-execution",
        "run_id": "run-closed",
        "terminal": True,
        "evidence_refs": ["accepted-target"],
        "expected_output_sha256": "a" * 64,
        "protected_write_intent_sha256": "b" * 64,
        "settlement_sha256": "e" * 64,
    }
    close["receipt_sha256"] = OE._digest(close, "receipt_sha256", "sha256")
    return cast(dict[str, Any], OE._finalize(close))


def _event(
    classification: str = "superseded-write-blocked",
    *,
    token: dict[str, object] = TOKEN,
    receipt_sha256: str | None = None,
) -> dict[str, Any]:
    lease = SimpleNamespace(resource_ref=RESOURCE, token=token, lease_id=LEASE_ID)
    return cast(
        dict[str, Any],
        OE.build_event(
            lease=lease,
            producer="agy",
            run_id="caller-event-run",
            classification=classification,
            expected_output_sha256="c" * 64,
            evidence_refs=["event:evidence"],
            payload_refs=[],
            observed_at="2026-07-17T12:00:00Z",
            receipt_sha256=receipt_sha256,
        ),
    )


def test_projection_derives_expiry_from_broker_lease_not_event_classification() -> None:
    [candidate] = R.scan(_snapshot(_event("superseded-write-blocked")))

    assert candidate["classification"] == "expired-write-quarantined"
    assert candidate["owner"] == "agy-supervisor"
    assert "receipt_sha256" not in candidate


def test_projection_derives_close_identity_and_classification_from_canonical_receipt() -> None:
    close = _close()
    [candidate] = R.scan(
        _snapshot(_event("superseded-write-blocked"), head=_head(close=close), leases=[])
    )

    assert candidate["classification"] == "late-write-after-close"
    assert candidate["owner"] == "team-execution"
    assert candidate["run_id"] == close["run_id"]
    assert candidate["expected_output_sha256"] == close["expected_output_sha256"]
    assert candidate["receipt_sha256"] == close["receipt_sha256"]


def test_generic_terminal_assertion_is_not_a_projection_source() -> None:
    fabricated = {
        "expected_output": {},
        "terminal": {"state": "stalled", "authoritative": True},
        "classification": "stalled",
    }

    with pytest.raises(R.ReapOrphansError, match="schema is unsupported"):
        R.scan(_snapshot(fabricated))


def test_receiptless_closed_head_is_integrity_error_not_claimed_disposition() -> None:
    [candidate] = R.scan(_snapshot(_event("superseded-write-blocked"), leases=[]))

    assert candidate["classification"] == "evidence-integrity-error"


def test_bounded_archived_close_head_remains_authoritative() -> None:
    close = _close()
    digest = OE.resource_sha256(RESOURCE)
    snapshot = _snapshot(
        _event("superseded-write-blocked"),
        head={
            "resource_ref": {"logical_unit_id": "other"},
            "broker_epoch": TOKEN["broker_epoch"],
            "fencing_sequence": 20,
            "lease_id": "33333333-3333-4333-8333-333333333333",
            "close_receipt": None,
        },
        archived={digest: _head(close=close)},
        leases=[],
    )
    snapshot["broker_heads"] = {
        OE.resource_sha256(snapshot["broker_heads"][digest]["resource_ref"]): next(
            iter(snapshot["broker_heads"].values())
        )
    }

    [candidate] = R.scan(snapshot)

    assert candidate["classification"] == "late-write-after-close"
    assert candidate["receipt_sha256"] == close["receipt_sha256"]


def test_successor_generation_derives_superseded_refusal() -> None:
    successor = {
        "broker_epoch": TOKEN["broker_epoch"],
        "fencing_sequence": TOKEN["fencing_sequence"] + 1,
    }
    [candidate] = R.scan(
        _snapshot(_event("expired-write-quarantined"), head=_head(token=successor), leases=[])
    )

    assert candidate["classification"] == "superseded-write-blocked"


def test_scan_is_byte_deterministic_and_does_not_mutate_input() -> None:
    first_source = _event("superseded-write-blocked")
    second_source = _event("expired-write-quarantined")
    second_source["run_id"] = "second-run"
    second_source = OE._finalize(
        {key: value for key, value in second_source.items() if key != "sha256"}
    )
    snapshot = _snapshot(first_source, second_source)
    before = json.dumps(snapshot, sort_keys=True)
    first = json.dumps(R.scan(snapshot), sort_keys=True, separators=(",", ":"))
    snapshot["sources"].reverse()
    second = json.dumps(R.scan(snapshot), sort_keys=True, separators=(",", ":"))

    assert first == second
    snapshot["sources"].reverse()
    assert json.dumps(snapshot, sort_keys=True) == before


def test_production_adapter_reads_broker_events_and_archived_inspection(
    tmp_path: Path,
) -> None:
    lease_broker = R._load_lease_broker()
    broker = lease_broker.LeaseBroker(tmp_path / "authority")
    lease = broker.acquire_agent(
        owner_id="projector-owner",
        session_id="projector-session",
        policy_sha256="a" * 64,
        session_limit=3,
        aggregate_limit=7,
        mutation="read-write",
        resource_ref={"logical_unit_id": "projector-resource"},
        agent_type="worker",
    )
    settlement = broker.prepare_agent_settlement(
        lease.lease_id,
        token=lease.token,
        owner_id=lease.owner_id,
        producer="saga",
        run_id="projector-run",
        expected_output_sha256="b" * 64,
        protected_write_intent_sha256="c" * 64,
    )
    close = broker.commit_agent_settlement(
        settlement.settlement_id,
        owner_id=lease.owner_id,
        token=lease.token,
        write=lambda _lease: ["accepted"],
    )
    event = OE.build_event(
        lease=lease,
        producer="agy",
        run_id="caller-event-run",
        classification="late-write-after-close",
        expected_output_sha256="d" * 64,
        evidence_refs=["event:evidence"],
        payload_refs=[],
        observed_at="2026-07-17T12:00:00Z",
        receipt_sha256=close["receipt_sha256"],
    )
    event_path = (
        tmp_path / "audit" / OE.EVENTS / OE.resource_sha256(lease.resource_ref) / "event.json"
    )
    OE._atomic_write(event_path, OE.canonical_json(event) + b"\n")

    snapshot = R.snapshot_from_stores(
        broker_root=tmp_path / "authority", evidence_root=tmp_path / "audit"
    )
    [candidate] = R.scan(snapshot)

    assert "archived_broker_heads" in snapshot
    assert candidate["classification"] == "late-write-after-close"
    assert candidate["run_id"] == "projector-run"


def test_stalled_or_empty_flagged_from_canonical_outcome_and_manifest_stores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lease_broker = R._load_lease_broker()
    broker = lease_broker.LeaseBroker(tmp_path / "authority")

    def close_run(
        run_id: str, *, expected_output_sha256: str = "b" * 64
    ) -> tuple[Any, dict[str, Any]]:
        lease = broker.acquire_agent(
            owner_id=f"owner-{run_id}",
            session_id=f"session-{run_id}",
            policy_sha256="a" * 64,
            session_limit=3,
            aggregate_limit=7,
            mutation="read-write",
            resource_ref={"logical_unit_id": run_id},
            agent_type="worker",
        )
        settlement = broker.prepare_agent_settlement(
            lease.lease_id,
            token=lease.token,
            owner_id=lease.owner_id,
            producer="saga",
            run_id=run_id,
            expected_output_sha256=expected_output_sha256,
            protected_write_intent_sha256="c" * 64,
        )
        close = broker.commit_agent_settlement(
            settlement.settlement_id,
            owner_id=lease.owner_id,
            token=lease.token,
            write=lambda _lease: [f"accepted:{run_id}"],
        )
        return lease, close

    close_run("stalled-run")
    template = OE.build_expected_output_template(
        "empty-run", required=True, artifact_keys=["artifact"], target_count=1
    )
    provisional_lease = broker.acquire_agent(
        owner_id="owner-empty-run",
        session_id="session-empty-run",
        policy_sha256="a" * 64,
        session_limit=3,
        aggregate_limit=7,
        mutation="read-write",
        resource_ref={"logical_unit_id": "empty-run"},
        agent_type="worker",
    )
    expected_output = OE.bind_expected_output(
        template,
        resource=provisional_lease.resource_ref,
        token=provisional_lease.token,
        lease_id=provisional_lease.lease_id,
        producer="saga",
        run_id="empty-run",
    )
    settlement = broker.prepare_agent_settlement(
        provisional_lease.lease_id,
        token=provisional_lease.token,
        owner_id=provisional_lease.owner_id,
        producer="saga",
        run_id="empty-run",
        expected_output_sha256=expected_output["expected_output_sha256"],
        protected_write_intent_sha256="c" * 64,
    )
    broker.commit_agent_settlement(
        settlement.settlement_id,
        owner_id=provisional_lease.owner_id,
        token=provisional_lease.token,
        write=lambda _lease: ["accepted:empty-run"],
    )
    common = tmp_path / "common"
    common.mkdir()
    monkeypatch.setattr(R.outcome_store, "resolve_common_dir", lambda *_args, **_kwargs: common)
    # A full-suite import may load manifest_store's outcome_store under its canonical module name
    # before this test's isolated reap_orphans module is loaded. Patch both references so the test
    # proves the store join rather than depending on import order.
    monkeypatch.setattr(
        R.manifest_store.outcome_store,
        "resolve_common_dir",
        lambda *_args, **_kwargs: common,
    )
    outcome = R.outcome_store.Store.for_outcome("outcome-355", tmp_path)
    R.outcome_store.write_completion_event(
        outcome,
        R.outcome_store.CompletionEvent(
            subplot_id="stalled-run",
            state="stalled",
            idempotency_key="stalled-run:a1",
            attempt=1,
            at="2026-07-17T12:00:00Z",
        ),
    )
    manifests = R.manifest_store.Store.for_saga("saga-355", tmp_path).ensure()
    R.manifest_store.write_manifest(
        manifests,
        "empty-run",
        {
            "execution_id": "empty-run",
            "output_completeness": {
                "declared_keys": ["artifact"],
                "target_count": 1,
                "produced_keys": [],
                "produced_count": 0,
                "missing_keys": ["artifact"],
            },
        },
    )
    before = {
        path.relative_to(common).as_posix(): path.read_bytes()
        for path in common.rglob("*")
        if path.is_file()
    }

    snapshot = R.snapshot_from_stores(
        broker_root=tmp_path / "authority",
        evidence_root=tmp_path / "audit",
        repo_root=tmp_path,
        outcome_id="outcome-355",
        saga_id="saga-355",
        expected_outputs=[expected_output],
        expected_output_templates=[template],
    )
    candidates = R.scan(snapshot)

    assert {candidate["classification"] for candidate in candidates} == {
        "stalled",
        "empty-artifacts",
    }
    assert {candidate["owner"] for candidate in candidates} == {"outcome"}
    after = {
        path.relative_to(common).as_posix(): path.read_bytes()
        for path in common.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_empty_artifact_contract_optional_and_integrity_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lease_broker = R._load_lease_broker()
    broker = lease_broker.LeaseBroker(tmp_path / "authority")
    lease = broker.acquire_agent(
        owner_id="contract-owner",
        session_id="contract-session",
        policy_sha256="a" * 64,
        session_limit=3,
        aggregate_limit=7,
        mutation="read-write",
        resource_ref={"logical_unit_id": "contract-run"},
        agent_type="worker",
    )
    optional = OE.build_expected_output_template(
        "contract-run", required=False, artifact_keys=["artifact"], target_count=1
    )
    expected = OE.bind_expected_output(
        optional,
        resource=lease.resource_ref,
        token=lease.token,
        lease_id=lease.lease_id,
        producer="saga",
        run_id="contract-run",
    )
    settlement = broker.prepare_agent_settlement(
        lease.lease_id,
        token=lease.token,
        owner_id=lease.owner_id,
        producer="saga",
        run_id="contract-run",
        expected_output_sha256=expected["expected_output_sha256"],
        protected_write_intent_sha256="c" * 64,
    )
    broker.commit_agent_settlement(
        settlement.settlement_id,
        owner_id=lease.owner_id,
        token=lease.token,
        write=lambda _lease: ["accepted"],
    )
    common = tmp_path / "common-contract"
    common.mkdir()
    monkeypatch.setattr(
        R.manifest_store.outcome_store, "resolve_common_dir", lambda *_a, **_k: common
    )
    manifests = R.manifest_store.Store.for_saga("saga-contract", tmp_path).ensure()
    R.manifest_store.write_manifest(
        manifests,
        "contract-run",
        {
            "execution_id": "contract-run",
            "output_completeness": {
                "declared_keys": ["artifact"],
                "target_count": 1,
                "produced_keys": [],
                "produced_count": 0,
                "missing_keys": ["artifact"],
            },
        },
    )

    no_contract_snapshot = R.snapshot_from_stores(
        broker_root=tmp_path / "authority",
        repo_root=tmp_path,
        saga_id="saga-contract",
    )
    assert R.scan(no_contract_snapshot) == []

    optional_snapshot = R.snapshot_from_stores(
        broker_root=tmp_path / "authority",
        repo_root=tmp_path,
        saga_id="saga-contract",
        expected_outputs=[expected],
        expected_output_templates=[optional],
    )
    assert R.scan(optional_snapshot) == []

    integrity_snapshot = R.snapshot_from_stores(
        broker_root=tmp_path / "authority",
        repo_root=tmp_path,
        saga_id="saga-contract",
        expected_outputs=[expected],
    )
    [candidate] = R.scan(integrity_snapshot)
    assert candidate["classification"] == "evidence-integrity-error"


def test_cli_has_no_caller_terminal_source_or_snapshot_path() -> None:
    help_text = R.build_parser().format_help()

    assert "--terminal-sources" not in help_text
    assert "--snapshot" not in help_text
    assert "--evidence-root" not in help_text


def test_quarantine_recovery_uses_broker_process_identity_providers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sentinel = object()
    captured: dict[str, object] = {}

    def for_root(root: Path, *, providers: object) -> object:
        captured["root"] = root
        captured["providers"] = providers
        return "store"

    def recover(store: object) -> dict[str, int]:
        captured["store"] = store
        return {"finalized": 0, "removed": 0, "retained": 0, "alerts": 0}

    monkeypatch.setattr(R, "_canonical_evidence_root", lambda: tmp_path / "evidence")
    monkeypatch.setattr(
        R,
        "_load_lease_broker",
        lambda: SimpleNamespace(Providers=lambda: sentinel),
    )
    monkeypatch.setattr(
        R,
        "_load_orphan_evidence",
        lambda: SimpleNamespace(
            QuarantineStore=SimpleNamespace(for_root=for_root),
            recover_quarantine=recover,
        ),
    )

    assert R.main(["quarantine-recover", "--json"]) == 0
    assert captured == {
        "root": tmp_path / "evidence",
        "providers": sentinel,
        "store": "store",
    }
    assert json.loads(capsys.readouterr().out) == {
        "alerts": 0,
        "finalized": 0,
        "removed": 0,
        "retained": 0,
    }
