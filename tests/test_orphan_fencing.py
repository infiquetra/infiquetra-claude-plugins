"""Failure-atomic broker settlement and refused-write containment (#355)."""

from __future__ import annotations

import hashlib
import importlib.util
import multiprocessing
import os
import sys
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
COMMONS = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons"
FIXTURES = ROOT / "tests" / "fixtures" / "orphan_evidence"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


B = _load(COMMONS / "lease_broker.py", "issue355_lease_broker")
OE = _load(COMMONS / "orphan_evidence.py", "issue355_orphan_evidence")


def _successor_close_worker(
    authority_root: str, target_path: str, start: Any, finished: Any
) -> None:
    broker = B.LeaseBroker(Path(authority_root))
    start.wait(timeout=10)
    lease = broker.acquire_agent(
        owner_id="successor",
        session_id="successor-session",
        policy_sha256="a" * 64,
        session_limit=3,
        aggregate_limit=7,
        mutation="read-write",
        ttl_seconds=300,
        resource_ref={"logical_unit_id": "two-process-race"},
        agent_type="worker",
    )
    settlement = broker.prepare_agent_settlement(
        lease.lease_id,
        token=lease.token,
        owner_id=lease.owner_id,
        producer="agy",
        run_id="successor-run",
        expected_output_sha256="b" * 64,
        protected_write_intent_sha256="c" * 64,
    )

    def write(_lease: Any) -> list[str]:
        Path(target_path).write_bytes(b"successor-bytes")
        return ["accepted.txt"]

    receipt = broker.commit_agent_settlement(
        settlement.settlement_id,
        owner_id=lease.owner_id,
        token=lease.token,
        write=write,
    )
    finished.put((lease.lease_id, receipt))


@dataclass
class Runtime:
    wall: datetime = datetime(2026, 7, 17, 9, tzinfo=UTC)
    monotonic: int = 1_000_000_000
    boot: str = "boot-a"
    next_uuid: int = 1
    processes: dict[int, tuple[bool, str | None]] = field(default_factory=dict)

    def uuid4(self) -> uuid.UUID:
        result = uuid.UUID(int=self.next_uuid)
        self.next_uuid += 1
        return result

    def broker_providers(self) -> Any:
        return B.Providers(
            wall_now=lambda: self.wall,
            monotonic_ns=lambda: self.monotonic,
            boot_id=lambda: self.boot,
            uuid4=self.uuid4,
            process_identity=lambda pid: self.processes.get(pid, (False, None))[1],
            process_exists=lambda pid: self.processes.get(pid, (False, None))[0],
        )

    def evidence_providers(self) -> Any:
        return OE.Providers(
            wall_now=lambda: self.wall,
            monotonic_ns=lambda: self.monotonic,
            boot_id=lambda: self.boot,
            process_identity=lambda pid: self.processes.get(pid, (False, None))[1],
            process_exists=lambda pid: self.processes.get(pid, (False, None))[0],
        )

    def advance(self, seconds: int) -> None:
        self.wall += timedelta(seconds=seconds)
        self.monotonic += seconds * 1_000_000_000


@pytest.fixture
def runtime() -> Runtime:
    return Runtime()


def _broker(tmp_path: Path, runtime: Runtime) -> Any:
    return B.LeaseBroker(
        tmp_path / "authority",
        providers=runtime.broker_providers(),
    )


def _agent(
    broker: Any,
    *,
    resource: str,
    owner: str = "owner",
    session: str = "session",
    ttl: int = 300,
    owner_pid: int | None = None,
) -> Any:
    return broker.acquire_agent(
        owner_id=owner,
        owner_pid=owner_pid,
        session_id=session,
        policy_sha256="a" * 64,
        session_limit=3,
        aggregate_limit=7,
        mutation="read-write",
        ttl_seconds=ttl,
        resource_ref={"logical_unit_id": resource},
        agent_type="worker",
    )


def _prepare(broker: Any, lease: Any, *, run_id: str = "run-1") -> Any:
    return broker.prepare_agent_settlement(
        lease.lease_id,
        token=lease.token,
        owner_id=lease.owner_id,
        producer="agy",
        run_id=run_id,
        expected_output_sha256="b" * 64,
        protected_write_intent_sha256="c" * 64,
    )


def _store(tmp_path: Path, runtime: Runtime) -> Any:
    runtime.processes[os.getpid()] = (True, "root-process")
    return OE.QuarantineStore.for_root(tmp_path / "audit", providers=runtime.evidence_providers())


def test_broker_commit_linearizes_close_and_successor_cas(tmp_path: Path, runtime: Runtime) -> None:
    broker = _broker(tmp_path, runtime)
    lease = _agent(broker, resource="logical-unit")
    settlement = _prepare(broker, lease)
    target = tmp_path / "accepted.txt"

    receipt = broker.commit_agent_settlement(
        settlement.settlement_id,
        owner_id=lease.owner_id,
        token=lease.token,
        write=lambda _current: target.write_text("accepted", encoding="utf-8") and ["target"],
    )

    assert target.read_text(encoding="utf-8") == "accepted"
    assert broker.classify_token(lease.resource_ref, lease.token) == "closed"
    state = broker.inspect()
    digest = B.resource_sha256(lease.resource_ref)
    assert state["settlements"] == {}
    assert state["resource_fences"][digest]["close_receipt"] == receipt

    with pytest.raises(B.LeaseOwnershipError, match="requires acquire_successor"):
        _agent(broker, resource="logical-unit", owner="ordinary", session="ordinary")

    with pytest.raises(B.LeaseOwnershipError, match="token or receipt CAS"):
        broker.acquire_successor(
            owner_id="successor",
            session_id="successor-session",
            policy_sha256="a" * 64,
            session_limit=3,
            aggregate_limit=7,
            mutation="read-write",
            resource_ref=lease.resource_ref,
            predecessor_token=lease.token,
            predecessor_receipt_sha256="d" * 64,
        )
    successor = broker.acquire_successor(
        owner_id="successor",
        session_id="successor-session",
        policy_sha256="a" * 64,
        session_limit=3,
        aggregate_limit=7,
        mutation="read-write",
        resource_ref=lease.resource_ref,
        predecessor_token=lease.token,
        predecessor_receipt_sha256=receipt["receipt_sha256"],
    )
    assert successor.fencing_sequence > lease.fencing_sequence


def test_archived_close_outside_bounded_projection_still_requires_exact_successor(
    tmp_path: Path, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(B, "_MAX_CLOSED_FENCES", 1)
    broker = _broker(tmp_path, runtime)
    closed: list[tuple[Any, dict[str, Any]]] = []
    for index in range(3):
        lease = _agent(broker, resource=f"archived-{index}", owner=f"owner-{index}")
        settlement = _prepare(broker, lease, run_id=f"archived-run-{index}")
        receipt = broker.commit_agent_settlement(
            settlement.settlement_id,
            owner_id=lease.owner_id,
            token=lease.token,
            write=lambda _lease, index=index: [f"accepted-{index}"],
        )
        closed.append((lease, receipt))

    predecessor, receipt = closed[0]
    digest = B.resource_sha256(predecessor.resource_ref)
    inspected = broker.inspect()
    assert digest not in inspected["resource_fences"]
    assert digest not in inspected["archived_resource_fences"]
    assert broker.inspect_resource_head(predecessor.resource_ref)["close_receipt"] == receipt

    disposition, event, quarantine = OE.contain_refused_write(
        broker,
        _store(tmp_path, runtime),
        predecessor,
        b"late archived output",
        producer="agy",
        run_id="archived-run-0",
        expected_output_sha256="b" * 64,
    )
    assert disposition == "LATE_WRITE_AFTER_CLOSE"
    assert event["receipt_sha256"] == receipt["receipt_sha256"]
    assert quarantine is not None

    with pytest.raises(B.LeaseOwnershipError, match="requires acquire_successor"):
        _agent(broker, resource="archived-0", owner="ordinary", session="ordinary")

    successor = broker.acquire_successor(
        owner_id="successor",
        session_id="successor-session",
        policy_sha256="a" * 64,
        session_limit=3,
        aggregate_limit=7,
        mutation="read-write",
        resource_ref=predecessor.resource_ref,
        predecessor_token=predecessor.token,
        predecessor_receipt_sha256=receipt["receipt_sha256"],
    )
    assert successor.fencing_sequence > predecessor.fencing_sequence


def test_two_process_successor_close_fences_stale_writer_and_preserves_bytes(
    tmp_path: Path,
) -> None:
    authority_root = tmp_path / "authority"
    broker = B.LeaseBroker(authority_root)
    stale = _agent(broker, resource="two-process-race")
    target = tmp_path / "accepted.txt"
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    finished = context.Queue()
    process = context.Process(
        target=_successor_close_worker,
        args=(str(authority_root), str(target), start, finished),
    )
    process.start()
    start.set()
    successor_lease_id, receipt = finished.get(timeout=20)
    process.join(timeout=20)

    assert process.exitcode == 0
    assert target.read_bytes() == b"successor-bytes"
    with pytest.raises((B.LeaseSupersededError, B.LeaseNotFoundError)):
        _prepare(broker, stale, run_id="stale-run")
    state = broker.inspect()
    head = state["resource_fences"][B.resource_sha256(stale.resource_ref)]
    assert head["lease_id"] == successor_lease_id
    assert head["close_receipt"] == receipt
    assert target.read_bytes() == b"successor-bytes"


def test_callback_failure_retains_ambiguous_authority(tmp_path: Path, runtime: Runtime) -> None:
    broker = _broker(tmp_path, runtime)
    lease = _agent(broker, resource="retained")
    settlement = _prepare(broker, lease)

    def fail_after_write(_lease: Any) -> list[str]:
        (tmp_path / "unaccepted.txt").write_text(
            "bytes exist but are not accepted", encoding="utf-8"
        )
        raise RuntimeError("mirror failed")

    with pytest.raises(RuntimeError, match="mirror failed"):
        broker.commit_agent_settlement(
            settlement.settlement_id,
            owner_id=lease.owner_id,
            token=lease.token,
            write=fail_after_write,
        )

    inspected = broker.inspect()
    assert next(iter(inspected["settlements"].values()))["phase"] == "ambiguous"
    assert broker.sweep().retained[lease.lease_id] == "settlement-ambiguous"
    with pytest.raises(B.LeaseOwnershipError, match="retained settlement"):
        _agent(broker, resource="retained", owner="retry", session="retry")
    with pytest.raises(B.LeaseOwnershipError, match="retained settlement authority"):
        broker.release_session(lease.session_id)


def test_final_close_persistence_failure_retains_committing_authority(
    tmp_path: Path, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = _broker(tmp_path, runtime)
    lease = _agent(broker, resource="close-persistence-failure")
    settlement = _prepare(broker, lease)
    target = tmp_path / "written-before-close.txt"
    original_write_registry = broker._write_registry
    writes = 0

    def fail_final_registry_write(registry: Any) -> None:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("simulated final authority replacement failure")
        original_write_registry(registry)

    monkeypatch.setattr(broker, "_write_registry", fail_final_registry_write)

    with pytest.raises(OSError, match="final authority replacement"):
        broker.commit_agent_settlement(
            settlement.settlement_id,
            owner_id=lease.owner_id,
            token=lease.token,
            write=lambda _current: (
                target.write_text("written", encoding="utf-8") and ["written-before-close.txt"]
            ),
        )

    assert target.read_text(encoding="utf-8") == "written"
    durable = _broker(tmp_path, runtime).inspect()
    digest = B.resource_sha256(lease.resource_ref)
    assert durable["settlements"][digest]["phase"] == "committing"
    assert durable["resource_fences"][digest]["close_receipt"] is None
    assert durable["leases"][0]["lease_id"] == lease.lease_id


def test_committing_persistence_failure_before_callback_aborts_exact_authority(
    tmp_path: Path, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = _broker(tmp_path, runtime)
    lease = _agent(broker, resource="pre-callback-persistence-failure")
    settlement = _prepare(broker, lease)
    original_write_registry = broker._write_registry
    writes = 0
    callback_count = 0

    def fail_initial_committing_write(registry: Any) -> None:
        nonlocal writes
        writes += 1
        if writes == 1:
            original_write_registry(registry)
            raise OSError("simulated initial committing authority replacement failure")
        original_write_registry(registry)

    monkeypatch.setattr(broker, "_write_registry", fail_initial_committing_write)

    def callback(_lease: Any) -> list[str]:
        nonlocal callback_count
        callback_count += 1
        return ["must-not-run"]

    with pytest.raises(OSError, match="initial committing authority replacement failure"):
        broker.commit_agent_settlement(
            settlement.settlement_id,
            owner_id=lease.owner_id,
            token=lease.token,
            write=callback,
        )

    assert callback_count == 0
    reopened = _broker(tmp_path, runtime)
    assert reopened.inspect()["leases"] == []
    assert reopened.inspect()["settlements"] == {}
    assert reopened.get_session_admission(lease.session_id) is None

    retry = _agent(
        reopened,
        resource="pre-callback-persistence-failure",
        owner="retry",
        session="retry-session",
    )
    assert reopened.classify_token(retry.resource_ref, retry.token) == "current"


def test_committing_persistence_failure_preserves_original_and_notes_cleanup_failure(
    tmp_path: Path, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = _broker(tmp_path, runtime)
    lease = _agent(broker, resource="pre-callback-cleanup-failure")
    settlement = _prepare(broker, lease)
    original_write_registry = broker._write_registry
    writes = 0
    callback_count = 0

    def fail_initial_and_cleanup_writes(registry: Any) -> None:
        nonlocal writes
        writes += 1
        if writes == 1:
            raise OSError("initial persistence failure")
        if writes == 2:
            raise OSError("rollback persistence failure")
        original_write_registry(registry)

    monkeypatch.setattr(broker, "_write_registry", fail_initial_and_cleanup_writes)

    def callback(_lease: Any) -> list[str]:
        nonlocal callback_count
        callback_count += 1
        return ["must-not-run"]

    with pytest.raises(OSError, match="initial persistence failure") as exc_info:
        broker.commit_agent_settlement(
            settlement.settlement_id,
            owner_id=lease.owner_id,
            token=lease.token,
            write=callback,
        )

    assert callback_count == 0
    assert "rollback persistence failure" in "\n".join(exc_info.value.__notes__)


def test_prepared_dead_owner_recovery_can_abort_exact_authority(
    tmp_path: Path, runtime: Runtime
) -> None:
    runtime.processes[os.getpid()] = (True, "root-process")
    broker = _broker(tmp_path, runtime)
    coordinator = B._open_settlement_recovery_coordinator(
        broker,
        recovery_owner_id="root-coordinator",
    )
    lease = _agent(broker, resource="recover", owner_pid=42)
    settlement = _prepare(broker, lease)
    intent = OE.build_recovery_intent(
        settlement,
        recovery_owner_id="root-coordinator",
        recovery_owner_pid=os.getpid(),
        recovery_owner_process_start="root-process",
        recovery_owner_boot_id=runtime.boot,
        recovery_owner_effective_uid=os.geteuid(),
    )

    assert coordinator.recover_agent_settlement(intent, action="abort") is None
    assert broker.inspect()["leases"] == []
    assert broker.inspect()["settlements"] == {}


def test_recovery_commit_requires_configured_owner_and_digest_bound_handler(
    tmp_path: Path, runtime: Runtime
) -> None:
    runtime.processes[os.getpid()] = (True, "root-process")
    broker = _broker(tmp_path, runtime)
    coordinator = B._open_settlement_recovery_coordinator(
        broker,
        recovery_owner_id="root-coordinator",
    )
    lease = _agent(broker, resource="recover-commit", owner_pid=42)
    settlement = _prepare(broker, lease)

    def fail_after_write(_lease: Any) -> list[str]:
        (tmp_path / "partial.txt").write_text("partial", encoding="utf-8")
        raise RuntimeError("crash after protected write")

    with pytest.raises(RuntimeError, match="crash after protected write"):
        broker.commit_agent_settlement(
            settlement.settlement_id,
            owner_id=lease.owner_id,
            token=lease.token,
            write=fail_after_write,
        )
    intent = OE.build_recovery_intent(
        settlement,
        recovery_owner_id="wrong-root",
        recovery_owner_pid=os.getpid(),
        recovery_owner_process_start="root-process",
        recovery_owner_boot_id=runtime.boot,
        recovery_owner_effective_uid=os.geteuid(),
    )
    intent["expected_phase"] = "ambiguous"
    intent = OE._finalize({key: value for key, value in intent.items() if key != "sha256"})
    with pytest.raises(B.LeaseOwnershipError, match="retained root adapter"):
        coordinator.recover_agent_settlement(intent, action="commit")

    valid_intent = dict(intent)
    valid_intent["recovery_owner_id"] = "root-coordinator"
    valid_intent = OE._finalize(
        {key: value for key, value in valid_intent.items() if key != "sha256"}
    )
    recovered_target = tmp_path / "recovered.txt"
    replay_attempts = 0

    def replay(_lease: Any, _settlement: Any) -> Any:
        nonlocal replay_attempts
        replay_attempts += 1
        if replay_attempts == 1:
            return B.SettlementReplayResult(["bad"], "c" * 64, "d" * 64)
        recovered_target.write_text("recovered", encoding="utf-8")
        return B.SettlementReplayResult(["recovered.txt"], "c" * 64, "b" * 64)

    coordinator.register_recovery_handler(B.SettlementRecoveryHandler(settlement, replay))
    with pytest.raises(B.LeaseOwnershipError, match="write/output semantics"):
        coordinator.recover_agent_settlement(valid_intent, action="commit")

    receipt = coordinator.recover_agent_settlement(valid_intent, action="commit")

    assert receipt is not None
    assert recovered_target.read_text(encoding="utf-8") == "recovered"
    assert broker.inspect()["settlements"] == {}


def test_closed_schema_fixtures_round_trip_and_reject_duplicate_keys() -> None:
    golden = (FIXTURES / "golden" / "agy-expected-output-template.json").read_bytes()
    duplicate = (FIXTURES / "malformed" / "duplicate-schema.json").read_bytes()

    record = OE.loads_record(golden)

    assert OE.loads_record(OE.canonical_json(record)) == record
    with pytest.raises(OE.OrphanEvidenceError, match="duplicate JSON key"):
        OE.loads_record(duplicate)


def test_every_orphan_evidence_schema_rejects_unknown_fields_and_bad_self_digests(
    tmp_path: Path, runtime: Runtime
) -> None:
    broker = _broker(tmp_path, runtime)
    lease = _agent(broker, resource="schema-matrix")
    settlement = _prepare(broker, lease)
    template = OE.build_expected_output_template(
        "schema-matrix-template", required=True, artifact_keys=["result"], target_count=1
    )
    expected = OE.bind_expected_output(
        template,
        resource=lease.resource_ref,
        token=lease.token,
        lease_id=lease.lease_id,
        producer="agy",
        run_id="schema-matrix-run",
    )
    store = _store(tmp_path, runtime)
    quarantine = OE.quarantine_late_write(
        store,
        b"schema-matrix-payload",
        resource=lease.resource_ref,
        token=lease.token,
        lease_id=lease.lease_id,
        producer="agy",
        run_id="schema-matrix-run",
        reason="expired-lease",
        expected_output_sha256=expected["expected_output_sha256"],
    )
    _, manifest = OE.read_quarantine(quarantine)
    event = OE.build_event(
        lease=lease,
        producer="agy",
        run_id="schema-matrix-run",
        classification="superseded-write-blocked",
        expected_output_sha256=expected["expected_output_sha256"],
        evidence_refs=["event-evidence"],
        payload_refs=[],
        observed_at=OE.utc_text(runtime.wall),
    )
    candidate = OE._candidate(
        classification="superseded-write-blocked",
        producer="agy",
        run_id="schema-matrix-run",
        resource=lease.resource_ref,
        token=lease.token,
        lease_id=lease.lease_id,
        expected_output_sha256=expected["expected_output_sha256"],
        evidence_refs=["event-evidence"],
    )
    close = B.build_settlement_close(
        resource_ref=lease.resource_ref,
        token=lease.token,
        lease_id=lease.lease_id,
        producer="agy",
        run_id="schema-matrix-run",
        evidence_refs=["close-evidence"],
        expected_output_sha256=expected["expected_output_sha256"],
        settlement_id=settlement.settlement_id,
        session_id=settlement.session_id,
        policy_sha256=settlement.policy_sha256,
        protected_write_intent_sha256=settlement.protected_write_intent_sha256,
        settlement_sha256=settlement.settlement_sha256,
    )
    recovery = OE.build_recovery_intent(
        settlement,
        recovery_owner_id="root-coordinator",
        recovery_owner_pid=os.getpid(),
        recovery_owner_process_start="root-process",
        recovery_owner_boot_id=runtime.boot,
        recovery_owner_effective_uid=os.geteuid(),
    )
    records = {
        item["schema"]: item
        for item in (
            template,
            expected,
            close,
            recovery,
            manifest,
            event,
            candidate,
            {
                "schema": "reservation.v1",
                "reservation_id": str(uuid.UUID(int=999)),
                "payload_sha256": "d" * 64,
                "payload_bytes": 1,
                "owner_pid": os.getpid(),
                "owner_process_start": "root-process",
                "boot_id": runtime.boot,
                "created_at": OE.utc_text(runtime.wall),
                "created_monotonic_ns": runtime.monotonic,
                "state": "reserved",
            },
            {
                "schema": "agy.lease-admission.v1",
                "session_id": "schema-matrix-session",
                "owner_id": "schema-matrix-owner",
                "owner_pid": os.getpid(),
                "owner_process_start": "root-process",
                "policy_sha256": "a" * 64,
                "session_limit": 3,
                "aggregate_limit": 7,
                "mutation": "read-write",
                "ttl_seconds": 300,
                "resource_ref": lease.resource_ref,
                "repository_identity_sha256": "e" * 64,
                "expected_output_template_sha256": template["expected_output_template_sha256"],
            },
        )
    }

    assert set(records) == set(OE.SCHEMA_FIELDS)
    for record in records.values():
        assert OE.loads_record(OE.canonical_json(record)) == record
        with pytest.raises(OE.OrphanEvidenceError, match="missing or unknown fields"):
            OE.validate_record({**record, "caller_authored_field": True})
        if "sha256" in record:
            with pytest.raises(OE.OrphanEvidenceError, match="self digest does not match"):
                OE.validate_record({**record, "sha256": "0" * 64})


def test_quarantine_rejects_item_at_strict_cap_without_publication(
    tmp_path: Path, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(OE, "MAX_PAYLOAD_BYTES", 4)
    store = _store(tmp_path, runtime)

    with pytest.raises(OE.OrphanEvidenceError, match="smaller than 128 MiB"):
        OE.quarantine_late_write(
            store,
            b"1234",
            resource={"logical_unit_id": "cap"},
            token={"broker_epoch": str(uuid.UUID(int=100)), "fencing_sequence": 1},
            lease_id=str(uuid.UUID(int=101)),
            producer="agy",
            run_id="cap-run",
            reason="expired-lease",
            expected_output_sha256="b" * 64,
        )
    assert not (store.root / OE.QUARANTINE).exists()


def test_superseded_lease_rejected(tmp_path: Path, runtime: Runtime) -> None:
    broker = _broker(tmp_path, runtime)
    stale = _agent(broker, resource="shared")
    current = _agent(broker, resource="shared", owner="retry", session="retry")
    target = tmp_path / "current.txt"
    target.write_bytes(b"current-successor")

    disposition, event, quarantine = OE.contain_refused_write(
        broker,
        _store(tmp_path, runtime),
        stale,
        b"stale-output",
        producer="agy",
        run_id="stale-run",
        expected_output_sha256="b" * 64,
    )

    assert broker.classify_token(current.resource_ref, current.token) == "current"
    assert disposition == "ORPHAN_WRITE_BLOCKED"
    assert event["classification"] == "superseded-write-blocked"
    assert quarantine is None
    assert target.read_bytes() == b"current-successor"


def test_expired_lease_quarantined(tmp_path: Path, runtime: Runtime) -> None:
    broker = _broker(tmp_path, runtime)
    lease = _agent(broker, resource="expired", ttl=1)
    runtime.advance(2)

    disposition, event, quarantine = OE.contain_refused_write(
        broker,
        _store(tmp_path, runtime),
        lease,
        b"late-expired-output",
        producer="agy",
        run_id="expired-run",
        expected_output_sha256="b" * 64,
    )

    assert disposition == "EXPIRED_LEASE_QUARANTINED"
    assert event["classification"] == "expired-write-quarantined"
    assert quarantine is not None
    payload, manifest = OE.read_quarantine(quarantine)
    assert payload == b"late-expired-output"
    assert manifest["reason"] == "expired-lease"
    assert "receipt_sha256" not in manifest


def test_successor_between_expiry_classification_and_publication_blocks_payload(
    tmp_path: Path, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = _broker(tmp_path, runtime)
    lease = _agent(broker, resource="expired-publication-race", ttl=1)
    runtime.advance(2)
    store = _store(tmp_path, runtime)
    original_publish = broker.publish_if_token_state
    successor: list[Any] = []

    def publish_after_successor(*args: Any, **kwargs: Any) -> bool:
        successor.append(
            _agent(
                broker,
                resource="expired-publication-race",
                owner="retry",
                session="retry",
            )
        )
        return cast(bool, original_publish(*args, **kwargs))

    monkeypatch.setattr(broker, "publish_if_token_state", publish_after_successor)

    disposition, event, quarantine = OE.contain_refused_write(
        broker,
        store,
        lease,
        b"stale-after-successor",
        producer="agy",
        run_id="expired-publication-race",
        expected_output_sha256="b" * 64,
    )

    assert successor
    assert broker.classify_token(successor[0].resource_ref, successor[0].token) == "current"
    assert disposition == "ORPHAN_WRITE_BLOCKED"
    assert event["classification"] == "superseded-write-blocked"
    assert quarantine is None
    assert not list((store.root / OE.QUARANTINE).rglob("payload.bin"))
    assert not list((store.root / OE.STAGING).glob("*"))


def test_successor_between_closed_classification_and_inspection_blocks_payload(
    tmp_path: Path, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = _broker(tmp_path, runtime)
    lease = _agent(broker, resource="closed-inspection-race")
    settlement = _prepare(broker, lease, run_id="closed-inspection-race")
    receipt = broker.commit_agent_settlement(
        settlement.settlement_id,
        owner_id=lease.owner_id,
        token=lease.token,
        write=lambda _lease: ["accepted-target"],
    )
    store = _store(tmp_path, runtime)
    original_inspect_resource_head = broker.inspect_resource_head
    successor: list[Any] = []

    def inspect_after_successor(resource_ref: Mapping[str, Any]) -> dict[str, Any] | None:
        successor.append(
            broker.acquire_successor(
                owner_id="successor",
                session_id="successor-session",
                policy_sha256="a" * 64,
                session_limit=3,
                aggregate_limit=7,
                mutation="read-write",
                resource_ref=lease.resource_ref,
                predecessor_token=lease.token,
                predecessor_receipt_sha256=receipt["receipt_sha256"],
            )
        )
        return cast(dict[str, Any] | None, original_inspect_resource_head(resource_ref))

    monkeypatch.setattr(broker, "inspect_resource_head", inspect_after_successor)

    disposition, event, quarantine = OE.contain_refused_write(
        broker,
        store,
        lease,
        b"stale-after-closed-successor",
        producer="agy",
        run_id="closed-inspection-race",
        expected_output_sha256="b" * 64,
    )

    assert successor
    assert disposition == "ORPHAN_WRITE_BLOCKED"
    assert event["classification"] == "superseded-write-blocked"
    assert quarantine is None
    assert not list((store.root / OE.QUARANTINE).rglob("payload.bin"))
    assert not list((store.root / OE.STAGING).glob("*"))


def test_identical_quarantine_and_event_retry_converges_after_time_advances(
    tmp_path: Path, runtime: Runtime
) -> None:
    broker = _broker(tmp_path, runtime)
    lease = _agent(broker, resource="retry-expired", ttl=1)
    runtime.advance(2)
    store = _store(tmp_path, runtime)

    first = OE.contain_refused_write(
        broker,
        store,
        lease,
        b"same-expired-output",
        producer="agy",
        run_id="retry-run",
        expected_output_sha256="b" * 64,
    )
    runtime.advance(60)
    second = OE.contain_refused_write(
        broker,
        store,
        lease,
        b"same-expired-output",
        producer="agy",
        run_id="retry-run",
        expected_output_sha256="b" * 64,
    )

    assert first[2] == second[2]
    assert first[1]["event_id"] == second[1]["event_id"]
    assert len(list((store.root / OE.EVENTS).rglob("*.json"))) == 1


def test_quarantine_total_cap_never_evicts_committed_evidence(
    tmp_path: Path, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(OE, "MAX_QUARANTINE_BYTES", 5)
    store = _store(tmp_path, runtime)
    token = {"broker_epoch": str(uuid.UUID(int=200)), "fencing_sequence": 1}
    first = OE.quarantine_late_write(
        store,
        b"123",
        resource={"logical_unit_id": "total-cap-a"},
        token=token,
        lease_id=str(uuid.UUID(int=201)),
        producer="agy",
        run_id="total-cap-a",
        reason="expired-lease",
        expected_output_sha256="b" * 64,
    )

    with pytest.raises(OE.OrphanEvidenceError, match="capacity is exhausted"):
        OE.quarantine_late_write(
            store,
            b"456",
            resource={"logical_unit_id": "total-cap-b"},
            token={"broker_epoch": str(uuid.UUID(int=202)), "fencing_sequence": 2},
            lease_id=str(uuid.UUID(int=203)),
            producer="agy",
            run_id="total-cap-b",
            reason="expired-lease",
            expected_output_sha256="b" * 64,
        )

    assert OE.read_quarantine(first)[0] == b"123"


def test_quarantine_recovery_validates_reservation_identity_and_retains_live_owner(
    tmp_path: Path, runtime: Runtime
) -> None:
    store = _store(tmp_path, runtime).ensure()
    invalid = store.root / OE.STAGING / str(uuid.UUID(int=301))
    OE._ensure_dir(invalid)
    reservation = {
        "schema": "reservation.v1",
        "reservation_id": str(uuid.UUID(int=302)),
        "payload_sha256": "a" * 64,
        "payload_bytes": 1,
        "owner_pid": os.getpid(),
        "owner_process_start": "root-process",
        "boot_id": runtime.boot,
        "created_at": OE.utc_text(runtime.wall),
        "created_monotonic_ns": runtime.monotonic,
        "state": "reserved",
    }
    OE._atomic_write(invalid / "reservation.json", OE.canonical_json(reservation) + b"\n")

    live_id = str(uuid.UUID(int=303))
    live = store.root / OE.STAGING / live_id
    OE._ensure_dir(live)
    live_reservation = {**reservation, "reservation_id": live_id}
    OE._atomic_write(live / "reservation.json", OE.canonical_json(live_reservation) + b"\n")
    runtime.advance(OE.LIVE_RESERVATION_ALERT_SECONDS + 1)

    recovered = OE.recover_quarantine(store)

    assert invalid.name in recovered["discarded"]
    assert live.name in recovered["retained"]
    assert live.name in recovered["alerts"]
    assert live.is_dir()


def test_real_lease_broker_providers_retain_live_quarantine_reservation_bytes(
    tmp_path: Path,
) -> None:
    providers = B.Providers()
    process_identity = providers.process_identity(os.getpid())

    assert process_identity
    assert providers.process_identity(os.getpid()) == process_identity

    store = OE.QuarantineStore.for_root(tmp_path / "audit", providers=providers).ensure()
    reservation_id = str(uuid.uuid4())
    staging = store.root / OE.STAGING / reservation_id
    payload = b"live-owner-real-provider-payload"
    reservation = {
        "schema": "reservation.v1",
        "reservation_id": reservation_id,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "payload_bytes": len(payload),
        "owner_pid": os.getpid(),
        "owner_process_start": process_identity,
        "boot_id": providers.boot_id(),
        "created_at": OE.utc_text(providers.wall_now()),
        "created_monotonic_ns": providers.monotonic_ns(),
        "state": "payload-written",
    }
    OE._ensure_dir(staging)
    OE._atomic_write(staging / "reservation.json", OE.canonical_json(reservation) + b"\n")
    OE._atomic_write(staging / "payload.bin", payload)
    before = {
        path.relative_to(staging).as_posix(): path.read_bytes()
        for path in staging.rglob("*")
        if path.is_file()
    }

    recovered = OE.recover_quarantine(store)

    after = {
        path.relative_to(staging).as_posix(): path.read_bytes()
        for path in staging.rglob("*")
        if path.is_file()
    }
    assert recovered["retained"] == [reservation_id]
    assert after == before


def test_quarantine_publication_recovers_dead_incomplete_reservation_before_capacity(
    tmp_path: Path, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(OE, "MAX_QUARANTINE_ITEMS", 1)
    store = _store(tmp_path, runtime).ensure()
    reservation_id = str(uuid.UUID(int=304))
    staging = store.root / OE.STAGING / reservation_id
    OE._ensure_dir(staging)
    reservation = {
        "schema": "reservation.v1",
        "reservation_id": reservation_id,
        "payload_sha256": hashlib.sha256(b"abandoned").hexdigest(),
        "payload_bytes": len(b"abandoned"),
        "owner_pid": 42,
        "owner_process_start": "dead-process",
        "boot_id": runtime.boot,
        "created_at": OE.utc_text(runtime.wall),
        "created_monotonic_ns": runtime.monotonic,
        "state": "reserved",
    }
    OE._atomic_write(staging / "reservation.json", OE.canonical_json(reservation) + b"\n")

    published = OE.quarantine_late_write(
        store,
        b"replacement",
        resource={"logical_unit_id": "capacity-recovery"},
        token={"broker_epoch": str(uuid.UUID(int=305)), "fencing_sequence": 1},
        lease_id=str(uuid.UUID(int=306)),
        producer="agy",
        run_id="capacity-recovery-run",
        reason="expired-lease",
        expected_output_sha256="b" * 64,
    )

    assert not staging.exists()
    assert OE.read_quarantine(published)[0] == b"replacement"


def test_quarantine_recovery_retains_live_owner_after_final_rename(
    tmp_path: Path, runtime: Runtime
) -> None:
    store = _store(tmp_path, runtime).ensure()
    payload = b"live-owner-payload"
    token = {"broker_epoch": str(uuid.UUID(int=320)), "fencing_sequence": 1}
    manifest = OE._manifest(
        resource={"logical_unit_id": "live-moved"},
        token=token,
        lease_id=str(uuid.UUID(int=321)),
        producer="agy",
        run_id="live-moved-run",
        reason="expired-lease",
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        payload_bytes=len(payload),
        observed_at=OE.utc_text(runtime.wall),
        expected_output_sha256="b" * 64,
        evidence_refs=[],
        receipt_sha256=None,
    )
    manifest_bytes = OE.canonical_json(manifest) + b"\n"
    reservation_id = str(uuid.UUID(int=322))
    destination = store.final_dir(manifest["resource_ref"], token, manifest["payload_sha256"])
    OE._ensure_dir(destination)
    reservation = {
        "schema": "reservation.v1",
        "reservation_id": reservation_id,
        "payload_sha256": manifest["payload_sha256"],
        "payload_bytes": len(payload),
        "owner_pid": os.getpid(),
        "owner_process_start": "root-process",
        "boot_id": runtime.boot,
        "created_at": OE.utc_text(runtime.wall),
        "created_monotonic_ns": runtime.monotonic,
        "state": "manifest-written",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    }
    OE._atomic_write(destination / "payload.bin", payload)
    OE._atomic_write(destination / "manifest.json", manifest_bytes)
    OE._atomic_write(destination / "reservation.json", OE.canonical_json(reservation) + b"\n")

    recovered = OE.recover_quarantine(store)

    assert destination.as_posix() in recovered["retained"]
    assert not (destination / "committed").exists()


def test_event_publication_refuses_tampered_payload_evidence(
    tmp_path: Path, runtime: Runtime
) -> None:
    store = _store(tmp_path, runtime)
    token = {"broker_epoch": str(uuid.UUID(int=307)), "fencing_sequence": 1}
    lease = SimpleNamespace(
        resource_ref={"logical_unit_id": "tampered-event"},
        token=token,
        lease_id=str(uuid.UUID(int=308)),
    )
    quarantine = OE.quarantine_late_write(
        store,
        b"original",
        resource=lease.resource_ref,
        token=lease.token,
        lease_id=lease.lease_id,
        producer="agy",
        run_id="tampered-event-run",
        reason="expired-lease",
        expected_output_sha256="b" * 64,
    )
    (quarantine / "payload.bin").write_bytes(b"tampered")
    event = OE.build_event(
        lease=lease,
        producer="agy",
        run_id="tampered-event-run",
        classification="expired-write-quarantined",
        expected_output_sha256="b" * 64,
        evidence_refs=[],
        payload_refs=[quarantine.relative_to(store.root).as_posix()],
        observed_at=OE.utc_text(runtime.wall),
    )

    with pytest.raises(OE.OrphanEvidenceError, match="payload digest does not match"):
        OE.write_event(store, event)

    assert not (store.root / OE.EVENTS).exists()


def test_recovery_rejects_complete_staging_with_wrong_manifest_digest(
    tmp_path: Path, runtime: Runtime
) -> None:
    store = _store(tmp_path, runtime).ensure()
    runtime.processes[42] = (False, None)
    reservation_id = str(uuid.UUID(int=309))
    staging = store.root / OE.STAGING / reservation_id
    OE._ensure_dir(staging)
    token = {"broker_epoch": str(uuid.UUID(int=310)), "fencing_sequence": 1}
    payload = b"complete-but-malformed"
    manifest = OE._manifest(
        resource={"logical_unit_id": "malformed-recovery"},
        token=token,
        lease_id=str(uuid.UUID(int=311)),
        producer="agy",
        run_id="malformed-recovery-run",
        reason="expired-lease",
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        payload_bytes=len(payload),
        observed_at=OE.utc_text(runtime.wall),
        expected_output_sha256="b" * 64,
        evidence_refs=[],
        receipt_sha256=None,
    )
    manifest_bytes = OE.canonical_json(manifest) + b"\n"
    reservation = {
        "schema": "reservation.v1",
        "reservation_id": reservation_id,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "payload_bytes": len(payload),
        "owner_pid": 42,
        "owner_process_start": "dead-process",
        "boot_id": runtime.boot,
        "created_at": OE.utc_text(runtime.wall),
        "created_monotonic_ns": runtime.monotonic,
        "state": "manifest-written",
        "manifest_sha256": "0" * 64,
    }
    OE._atomic_write(staging / "payload.bin", payload)
    OE._atomic_write(staging / "manifest.json", manifest_bytes)
    OE._atomic_write(staging / "reservation.json", OE.canonical_json(reservation) + b"\n")

    recovered = OE.recover_quarantine(store)

    assert reservation_id in recovered["discarded"]
    assert not staging.exists()
    assert not (store.root / OE.QUARANTINE).exists()


def test_late_writer_after_close_is_quarantined_with_receipt(
    tmp_path: Path, runtime: Runtime
) -> None:
    broker = _broker(tmp_path, runtime)
    lease = _agent(broker, resource="closed")
    settlement = _prepare(broker, lease, run_id="closed-run")
    receipt = broker.commit_agent_settlement(
        settlement.settlement_id,
        owner_id=lease.owner_id,
        token=lease.token,
        write=lambda _lease: ["accepted-target"],
    )

    disposition, event, quarantine = OE.contain_refused_write(
        broker,
        _store(tmp_path, runtime),
        lease,
        b"late-closed-output",
        producer="agy",
        run_id="closed-run",
        expected_output_sha256="b" * 64,
    )

    assert disposition == "LATE_WRITE_AFTER_CLOSE"
    assert event["classification"] == "late-write-after-close"
    assert event["receipt_sha256"] == receipt["receipt_sha256"]
    assert quarantine is not None
    payload, manifest = OE.read_quarantine(quarantine)
    assert payload == b"late-closed-output"
    assert manifest["reason"] == "late-after-close"
    assert manifest["receipt_sha256"] == receipt["receipt_sha256"]
