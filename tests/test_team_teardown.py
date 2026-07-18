"""Tests for the non-skippable team teardown contract (#358): events, projection, driver."""

from __future__ import annotations

import importlib.util
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
BROKER_PATH = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "lease_broker.py"
POLICY_PATH = (
    ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "concurrency_policy.py"
)


def _load_saga(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_path(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RL = _load_saga("run_ledger")
TT = _load_saga("team_teardown")
B = _load_path(BROKER_PATH, "fleet_lease_broker_for_teardown_tests")
P = _load_path(POLICY_PATH, "fleet_concurrency_policy_for_teardown_tests")

AT = "2026-07-18T12:00:00Z"
SUB = "leaf-lease-safe-runtime-continuity-sub-358"


@dataclass
class FakeRuntime:
    wall: datetime = datetime(2026, 7, 18, 12, tzinfo=UTC)
    monotonic: int = 1_000_000_000
    boot: str = "boot-a"
    next_uuid: int = 1
    processes: dict[int, tuple[bool, str | None]] = field(default_factory=dict)

    def uuid4(self) -> uuid.UUID:
        value = uuid.UUID(int=self.next_uuid)
        self.next_uuid += 1
        return value

    def providers(self) -> Any:
        return B.Providers(
            wall_now=lambda: self.wall,
            monotonic_ns=lambda: self.monotonic,
            boot_id=lambda: self.boot,
            uuid4=self.uuid4,
            process_identity=lambda pid: self.processes.get(pid, (False, None))[1],
            process_exists=lambda pid: self.processes.get(pid, (False, None))[0],
        )

    def advance(self, seconds: int) -> None:
        self.monotonic += seconds * 1_000_000_000
        self.wall += timedelta(seconds=seconds)


@pytest.fixture
def runtime() -> FakeRuntime:
    return FakeRuntime()


@pytest.fixture
def broker(tmp_path: Path, runtime: FakeRuntime) -> Any:
    return B.LeaseBroker(tmp_path / "authority", providers=runtime.providers())


@pytest.fixture
def ledger(tmp_path: Path) -> Any:
    return RL.RunLedger(path=tmp_path / "run-facts.jsonl")


def _limits() -> Any:
    return P.AdmissionLimits()


def _acquire(broker: Any, *, owner: str, session: str = "session-1", resource: str = "u1") -> Any:
    limits = _limits()
    return broker.acquire_agent(
        owner_id=owner,
        session_id=session,
        policy_sha256=limits.policy_sha256(),
        session_limit=limits.max_concurrent,
        aggregate_limit=limits.aggregate_max_concurrent,
        mutation="read-write",
        resource_ref={"logical_unit_id": resource},
        agent_type="worker",
    )


def _open(ledger: Any, broker: Any, run_id: str = "team-run-1") -> dict[str, Any]:
    return TT.open_run(
        ledger, broker, subplot_id=SUB, session_id="session-1", at=AT, team_run_id=run_id
    )


def _intend(ledger: Any, run_id: str = "team-run-1", reason: str = "success") -> dict[str, Any]:
    fact = TT.build_teardown_intent(
        subplot_id=SUB, at=AT, team_run_id=run_id, terminal_reason=reason, close_generation=7
    )
    return TT.append_teardown_event(ledger, fact)


def _attempt(
    ledger: Any,
    run_id: str = "team-run-1",
    *,
    reason: str = "success",
    resource_id: str = "lease-1",
    generation: str = "3",
    action: str = "lease-release",
    kind: str = "provisional-lease",
) -> dict[str, Any]:
    fact = TT.build_resource_attempt(
        subplot_id=SUB,
        at=AT,
        team_run_id=run_id,
        intent_id=TT.intent_id_for(run_id, reason),
        resource_id=resource_id,
        resource_kind=kind,
        generation=generation,
        action=action,
    )
    return TT.append_teardown_event(ledger, fact)


def _result(
    ledger: Any,
    run_id: str = "team-run-1",
    *,
    key: str,
    disposition: str = "released",
    refs: tuple[str, ...] = ("sha:receipt",),
    at: str = AT,
) -> dict[str, Any]:
    fact = TT.build_resource_result(
        subplot_id=SUB,
        at=at,
        team_run_id=run_id,
        action_key_value=key,
        disposition=disposition,
        evidence_refs=list(refs),
    )
    return TT.append_teardown_event(ledger, fact)


# --------------------------------------------------------------------- owner-admission fence


class TestOwnerAdmissionFence:
    def test_acquire_before_close_succeeds_and_after_close_refuses(self, broker: Any) -> None:
        _acquire(broker, owner="team-run-1", resource="u-before")
        record = broker.close_owner_admission(owner_id="team-run-1")
        assert record["owner_id"] == "team-run-1"
        assert record["close_generation"] >= 1
        with pytest.raises(B.OwnerAdmissionClosedError):
            _acquire(broker, owner="team-run-1", resource="u-after")

    def test_close_is_idempotent_and_has_no_reopen(self, broker: Any) -> None:
        first = broker.close_owner_admission(owner_id="team-run-1")
        second = broker.close_owner_admission(owner_id="team-run-1")
        assert first == second
        assert broker.inspect_owner_admission("team-run-1") == first
        assert not hasattr(broker, "reopen_owner_admission")

    def test_close_generations_are_monotonic(self, broker: Any) -> None:
        first = broker.close_owner_admission(owner_id="team-run-1")
        second = broker.close_owner_admission(owner_id="team-run-2")
        assert second["close_generation"] > first["close_generation"]

    def test_reserve_and_batch_paths_refuse_after_close(self, broker: Any) -> None:
        limits = _limits()
        broker.close_owner_admission(owner_id="team-run-1")
        with pytest.raises(B.OwnerAdmissionClosedError):
            broker.reserve_batch(
                count=1,
                owner_id="team-run-1",
                session_id="session-1",
                batch_id="batch-1",
                agent_type="*",
                policy_sha256=limits.policy_sha256(),
                session_limit=limits.max_concurrent,
                aggregate_limit=limits.aggregate_max_concurrent,
                mutation="read-write",
            )

    def test_claim_of_closed_owner_reservation_refuses(self, broker: Any) -> None:
        lease = _acquire(broker, owner="team-run-1", resource="u-claim")
        assert lease.agent_id is None
        broker.close_owner_admission(owner_id="team-run-1")
        with pytest.raises(B.OwnerAdmissionClosedError):
            broker.claim(
                session_id="session-1",
                agent_type="worker",
                agent_id="agent-1",
                resource_ref={"logical_unit_id": "u-claim"},
            )

    def test_worktree_acquire_and_transfer_refuse_for_closed_owner(
        self, broker: Any, tmp_path: Path
    ) -> None:
        resource = {
            "repo_root": str(tmp_path),
            "outcome_id": "outcome-1",
            "subplot_id": "sub-1",
        }
        lease = broker.acquire_worktree(
            owner_id="live-owner", session_id="session-1", resource_ref=resource
        )
        broker.close_owner_admission(owner_id="team-run-1")
        with pytest.raises(B.OwnerAdmissionClosedError):
            broker.acquire_worktree(
                owner_id="team-run-1",
                session_id="session-1",
                resource_ref={
                    "repo_root": str(tmp_path),
                    "outcome_id": "outcome-1",
                    "subplot_id": "sub-2",
                },
            )
        with pytest.raises(B.OwnerAdmissionClosedError):
            broker.transfer_worktree(lease.lease_id, token=lease.token, owner_id="team-run-1")

    def test_closed_owner_leases_remain_inspectable_and_releasable(self, broker: Any) -> None:
        lease = _acquire(broker, owner="team-run-1", resource="u-open")
        broker.close_owner_admission(owner_id="team-run-1")
        listed = [item["lease_id"] for item in broker.inspect()["leases"]]
        assert lease.lease_id in listed
        assert broker.release(lease.lease_id, token=lease.token, owner_id="team-run-1")

    def test_close_serializes_against_concurrent_acquire(
        self, tmp_path: Path, runtime: FakeRuntime
    ) -> None:
        authority = tmp_path / "authority"
        outcomes: list[str] = []
        lock = threading.Lock()

        def _acquirer() -> None:
            handle = B.LeaseBroker(authority, providers=runtime.providers())
            try:
                _acquire(handle, owner="team-run-1", resource="u-race")
                with lock:
                    outcomes.append("acquired")
            except B.OwnerAdmissionClosedError:
                with lock:
                    outcomes.append("refused")

        def _closer() -> None:
            handle = B.LeaseBroker(authority, providers=runtime.providers())
            handle.close_owner_admission(owner_id="team-run-1")
            with lock:
                outcomes.append("closed")

        threads = [threading.Thread(target=_acquirer), threading.Thread(target=_closer)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        verifier = B.LeaseBroker(authority, providers=runtime.providers())
        owned = [item for item in verifier.inspect()["leases"] if item["owner_id"] == "team-run-1"]
        # Serialization invariant: either the acquire won the lock and its lease exists,
        # or the close won and the acquire was refused with no lease. Never a half state.
        if "acquired" in outcomes:
            assert len(owned) == 1
        else:
            assert outcomes.count("refused") == 1
            assert owned == []

    def test_from_dict_migrates_pre_358_shape(self, runtime: FakeRuntime) -> None:
        registry = B.Registry.fresh(runtime.providers())
        raw = registry.to_dict()
        raw.pop("closed_owner_admissions")
        migrated = B.Registry.from_dict(raw)
        assert migrated.closed_owner_admissions == {}

    def test_overflow_evicts_lowest_generation_close(self, broker: Any) -> None:
        for index in range(128):
            broker.close_owner_admission(owner_id=f"team-run-{index}")
        oldest = broker.inspect_owner_admission("team-run-0")
        assert oldest is not None
        broker.close_owner_admission(owner_id="team-run-overflow")
        assert broker.inspect_owner_admission("team-run-0") is None
        assert broker.inspect_owner_admission("team-run-overflow") is not None


# --------------------------------------------------------------------- event family


class TestTeardownEventFamily:
    def test_valid_open_intent_attempt_result_complete_chain(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker)
        _intend(ledger)
        attempt = _attempt(ledger)
        key = attempt["action_key"]
        _result(ledger, key=key)
        complete = TT.append_teardown_event(
            ledger,
            TT.build_teardown_complete(
                subplot_id=SUB,
                at=AT,
                team_run_id="team-run-1",
                intent_id=TT.intent_id_for("team-run-1", "success"),
                close_generation=7,
                released_count=1,
                already_absent_count=0,
            ),
        )
        assert complete["event"] == "teardown-complete"
        report = RL.verify_chain(ledger)
        assert report.ok

    def test_duplicate_identical_event_is_idempotent(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        first = _intend(ledger)
        second = _intend(ledger)
        assert first["this_hash"] == second["this_hash"]
        assert len([r for r in RL.read_facts(ledger) if r["event"] == "teardown-intent"]) == 1

    def test_conflicting_duplicate_is_refused(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        _intend(ledger)
        conflicting = TT.build_teardown_intent(
            subplot_id=SUB,
            at=AT,
            team_run_id="team-run-1",
            terminal_reason="success",
            close_generation=9,
        )
        with pytest.raises(TT.TeardownConflictError):
            TT.append_teardown_event(ledger, conflicting)

    def test_attempt_without_intent_is_refused(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        with pytest.raises(TT.TeardownError, match="requires a recorded teardown-intent"):
            _attempt(ledger)

    def test_result_without_attempt_is_refused(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        _intend(ledger)
        with pytest.raises(TT.TeardownError, match="requires a prior resource-attempt"):
            _result(ledger, key="a" * 64)

    def test_complete_with_retained_resource_is_refused(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        _intend(ledger)
        attempt = _attempt(ledger)
        _result(ledger, key=attempt["action_key"], disposition="retained")
        with pytest.raises(TT.TeardownError, match="retained/failed"):
            TT.append_teardown_event(
                ledger,
                TT.build_teardown_complete(
                    subplot_id=SUB,
                    at=AT,
                    team_run_id="team-run-1",
                    intent_id=TT.intent_id_for("team-run-1", "success"),
                    close_generation=7,
                    released_count=0,
                    already_absent_count=0,
                ),
            )

    def test_complete_with_dangling_attempt_is_refused(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        _intend(ledger)
        _attempt(ledger)
        with pytest.raises(TT.TeardownError, match="have no result"):
            TT.append_teardown_event(
                ledger,
                TT.build_teardown_complete(
                    subplot_id=SUB,
                    at=AT,
                    team_run_id="team-run-1",
                    intent_id=TT.intent_id_for("team-run-1", "success"),
                    close_generation=7,
                    released_count=0,
                    already_absent_count=0,
                ),
            )

    def test_partial_result_then_retry_converges_on_stable_action_key(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker)
        _intend(ledger)
        attempt = _attempt(ledger)
        key = attempt["action_key"]
        _result(ledger, key=key, disposition="failed")
        retry = _attempt(ledger)
        assert retry["action_key"] == key
        _result(ledger, key=key, disposition="released", at="2026-07-18T12:05:00Z")
        with pytest.raises(TT.TeardownError, match="final disposition"):
            _attempt(ledger)

    def test_events_after_complete_are_refused_except_recovery_observation(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker)
        _intend(ledger)
        TT.append_teardown_event(
            ledger,
            TT.build_teardown_complete(
                subplot_id=SUB,
                at=AT,
                team_run_id="team-run-1",
                intent_id=TT.intent_id_for("team-run-1", "success"),
                close_generation=7,
                released_count=0,
                already_absent_count=0,
            ),
        )
        with pytest.raises(TT.TeardownError, match="already recorded teardown-complete"):
            _intend(ledger, reason="hard-fail")
        observation = TT.append_teardown_event(
            ledger,
            TT.build_recovery_observation(
                subplot_id=SUB,
                at=AT,
                team_run_id="team-run-1",
                observed_open=0,
                actions_taken=0,
                reason_code="post-complete-audit",
            ),
        )
        assert observation["event"] == "recovery-observation"

    def test_unknown_kind_and_unknown_event_are_refused(self, ledger: Any) -> None:
        with pytest.raises(RL.RunLedgerError):
            RL.build_fact("reclaim", subplot_id=SUB, at=AT)
        alien = RL.build_fact("teardown", subplot_id=SUB, at=AT, event="resource-vanish")
        with pytest.raises(TT.TeardownError, match="unknown teardown event"):
            TT.append_teardown_event(ledger, alien)
        spend = RL.build_fact("spend", subplot_id=SUB, at=AT, tokens=1)
        with pytest.raises(TT.TeardownError, match="only accepts kind=teardown"):
            TT.append_teardown_event(ledger, spend)

    def test_bounded_ids_and_refs_are_enforced(self) -> None:
        with pytest.raises(TT.TeardownError):
            TT.build_run_opened(
                subplot_id=SUB,
                at=AT,
                team_run_id="x" * 300,
                owner_id="o",
                session_id="s",
                root_sha256="a" * 64,
            )
        with pytest.raises(TT.TeardownError):
            TT.build_resource_result(
                subplot_id=SUB,
                at=AT,
                team_run_id="team-run-1",
                action_key_value="a" * 64,
                disposition="released",
                evidence_refs=[f"ref-{i}" for i in range(17)],
            )
        with pytest.raises(TT.TeardownError):
            TT.build_teardown_intent(
                subplot_id=SUB,
                at=AT,
                team_run_id="team-run-1",
                terminal_reason="shrugged",
                close_generation=1,
            )

    def test_two_concurrent_reclaim_callers_allocate_one_logical_action(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker)
        _intend(ledger)
        results: list[str] = []
        lock = threading.Lock()

        def _caller() -> None:
            record = _attempt(ledger)
            with lock:
                results.append(record["this_hash"])

        threads = [threading.Thread(target=_caller) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(set(results)) == 1
        attempts = [r for r in RL.read_facts(ledger) if r["event"] == "resource-attempt"]
        assert len(attempts) == 1


# --------------------------------------------------------------------- decision input


class TestDecisionInputAndProjection:
    def test_broken_chain_refuses_decisions(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        lines = ledger.path.read_text().splitlines()
        ledger.path.write_text(lines[0].replace("run-opened", "run-doctored") + "\n")
        with pytest.raises(TT.TeardownError, match="broken run-fact chain"):
            TT.read_decision_input(ledger, broker)

    def test_corrupt_broker_is_a_typed_refusal(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)

        class ExplodingBroker:
            def inspect(self) -> dict[str, Any]:
                raise B.RegistryCorruptError("registry bytes are wrong")

        with pytest.raises(TT.TeardownError, match="broker snapshot unavailable"):
            TT.read_decision_input(ledger, ExplodingBroker())

    def test_projection_reports_open_and_disposed_resources(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        lease = _acquire(broker, owner="team-run-1", resource="u-open")
        _intend(ledger)
        attempt = _attempt(ledger, resource_id="lease-gone", generation="2")
        _result(ledger, key=attempt["action_key"], disposition="released")
        decision = TT.read_decision_input(ledger, broker)
        projection = TT.project(decision, "team-run-1")
        assert projection["schema"] == "team_teardown.v1"
        assert projection["open_count"] == 1
        assert projection["released_count"] == 1
        assert projection["completion_fact_ref"] is None
        open_rows = [r for r in projection["resources"] if r["disposition"] == "open"]
        assert open_rows and open_rows[0]["resource_id"] == lease.lease_id

    def test_projection_is_deterministic_for_one_snapshot(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        _acquire(broker, owner="team-run-1", resource="u-a")
        _intend(ledger)
        decision = TT.read_decision_input(ledger, broker)
        assert TT.project(decision, "team-run-1") == TT.project(decision, "team-run-1")

    def test_open_runs_scopes_by_repository_root(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker, run_id="team-run-here")
        foreign = TT.build_run_opened(
            subplot_id=SUB,
            at=AT,
            team_run_id="team-run-elsewhere",
            owner_id="team-run-elsewhere",
            session_id="session-9",
            root_sha256="b" * 64,
        )
        TT.append_teardown_event(ledger, foreign)
        scoped = TT.open_runs(
            TT.read_decision_input(ledger, broker), root_sha256=str(broker.root_sha256)
        )
        assert scoped == ["team-run-here"]
        unscoped = TT.open_runs(TT.read_decision_input(ledger, broker))
        assert set(unscoped) == {"team-run-here", "team-run-elsewhere"}

    def test_no_mutable_summary_exists_anywhere(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        _intend(ledger)
        facts = RL.read_facts(ledger)
        for fact in facts:
            assert "open" not in fact.get("status", "")
            assert "status" not in fact
        files = sorted(p.name for p in ledger.path.parent.iterdir())
        assert files == [ledger.path.name] or set(files) <= {
            ledger.path.name,
            ledger.path.name + ".lock",
        }


# --------------------------------------------------------------------- terminal driver


def _ats() -> Any:
    counter = {"n": 0}

    def _next() -> str:
        counter["n"] += 1
        return f"2026-07-18T13:{counter['n']:02d}:00Z"

    return _next


class TestTerminalDriver:
    @pytest.mark.parametrize(
        "reason", ["success", "hard-fail", "operator-abort", "andon", "recovered-crash"]
    )
    def test_every_terminal_reason_reaches_b8_and_completes_at_zero_open(
        self, ledger: Any, broker: Any, reason: str
    ) -> None:
        run_id = f"team-run-{reason}"
        _open(ledger, broker, run_id=run_id)
        projection = TT.reclaim_all(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            team_run_id=run_id,
            terminal_reason=reason,
            at_provider=_ats(),
        )
        assert projection["open_count"] == 0
        assert projection["completion_fact_ref"] is not None
        assert projection["terminal_reason"] == reason

    def test_provisional_leases_release_and_complete(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        _acquire(broker, owner="team-run-1", resource="u-a")
        _acquire(broker, owner="team-run-1", resource="u-b")
        projection = TT.reclaim_all(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="success",
            at_provider=_ats(),
        )
        assert projection["released_count"] == 2
        assert projection["open_count"] == 0
        assert projection["completion_fact_ref"] is not None
        remaining = [
            item for item in broker.inspect()["leases"] if item["owner_id"] == "team-run-1"
        ]
        assert remaining == []

    def test_repeated_b8_is_idempotent(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        _acquire(broker, owner="team-run-1", resource="u-a")
        adapters = TT.production_adapters(broker)
        first = TT.reclaim_all(
            ledger,
            broker,
            adapters,
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="success",
            at_provider=_ats(),
        )
        facts_after_first = len(RL.read_facts(ledger))
        second = TT.reclaim_all(
            ledger,
            broker,
            adapters,
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="success",
            at_provider=_ats(),
        )
        assert first["completion_fact_ref"] == second["completion_fact_ref"]
        assert len(RL.read_facts(ledger)) == facts_after_first

    def test_action_exception_is_failed_and_blocks_completion(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker)
        _acquire(broker, owner="team-run-1", resource="u-a")

        def _explode(_lease: Any) -> Any:
            raise RuntimeError("adapter blew up")

        projection = TT.reclaim_all(
            ledger,
            broker,
            TT.ReclaimAdapters(lease_release=_explode),
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="hard-fail",
            at_provider=_ats(),
        )
        assert projection["failed_count"] == 1
        assert projection["completion_fact_ref"] is None
        results = [r for r in RL.read_facts(ledger) if r.get("event") == "resource-result"]
        assert results[-1]["reason_code"] == "action-exception:RuntimeError"

    def test_retained_resource_is_a_blocked_terminal_not_a_completion(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker)
        lease = _acquire(broker, owner="team-run-1", resource="u-a")
        projection = TT.reclaim_all(
            ledger,
            broker,
            TT.ReclaimAdapters(),  # every slot defaults to conservative retain
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="operator-abort",
            at_provider=_ats(),
        )
        assert projection["retained_count"] == 1
        assert projection["completion_fact_ref"] is None
        assert projection["open_count"] == 1
        listed = [item["lease_id"] for item in broker.inspect()["leases"]]
        assert lease.lease_id in listed

    def test_close_fence_prevents_spawn_racing_completion(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        TT.reclaim_all(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="success",
            at_provider=_ats(),
        )
        with pytest.raises(B.OwnerAdmissionClosedError):
            _acquire(broker, owner="team-run-1", resource="u-late")

    def test_request_records_intent_without_acting(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        lease = _acquire(broker, owner="team-run-1", resource="u-a")
        outcome = TT.request(
            ledger,
            broker,
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="operator-abort",
            at="2026-07-18T13:00:00Z",
        )
        assert outcome["complete"] is False
        listed = [item["lease_id"] for item in broker.inspect()["leases"]]
        assert lease.lease_id in listed
        events = {r["event"] for r in RL.read_facts(ledger)}
        assert events == {"run-opened", "teardown-intent"}

    def test_dry_run_census_changes_nothing(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        _acquire(broker, owner="team-run-1", resource="u-a")
        before = len(RL.read_facts(ledger))
        projection = TT.reclaim_all(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="success",
            at_provider=_ats(),
            dry_run=True,
        )
        assert projection["open_count"] == 1
        assert len(RL.read_facts(ledger)) == before
        assert broker.inspect_owner_admission("team-run-1") is None

    def test_crash_orphaned_attempt_reconciles_as_already_absent(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker)
        lease = _acquire(broker, owner="team-run-1", resource="u-a")
        close = broker.close_owner_admission(owner_id="team-run-1")
        TT.append_teardown_event(
            ledger,
            TT.build_teardown_intent(
                subplot_id=SUB,
                at=AT,
                team_run_id="team-run-1",
                terminal_reason="success",
                close_generation=int(close["close_generation"]),
            ),
        )
        key = TT.action_key(
            "team-run-1", lease.lease_id, str(lease.fencing_sequence), "lease-release"
        )
        TT.append_teardown_event(
            ledger,
            TT.build_resource_attempt(
                subplot_id=SUB,
                at=AT,
                team_run_id="team-run-1",
                intent_id=TT.intent_id_for("team-run-1", "success"),
                resource_id=lease.lease_id,
                resource_kind="provisional-lease",
                generation=str(lease.fencing_sequence),
                action="lease-release",
            ),
        )
        # The crash happened after the release landed but before its result fact.
        assert broker.release(lease.lease_id, token=lease.token, owner_id="team-run-1")
        projection = TT.reclaim_all(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="success",
            at_provider=_ats(),
        )
        assert projection["already_absent_count"] == 1
        assert projection["completion_fact_ref"] is not None
        results = [
            r
            for r in RL.read_facts(ledger)
            if r.get("event") == "resource-result" and r.get("action_key") == key
        ]
        assert len(results) == 1
        assert results[0]["reason_code"] == "recovered-after-crash"


class TestRecovery:
    def test_recover_skips_runs_with_live_owner_when_expired_only(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker)
        _acquire(broker, owner="team-run-1", resource="u-live")
        outcome = TT.recover(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            expired_only=True,
            max_actions=4,
            at_provider=_ats(),
        )
        assert outcome["recovered_runs"] == [
            {"team_run_id": "team-run-1", "actions_taken": 0, "skipped": "live-owner"}
        ]
        observations = [
            r for r in RL.read_facts(ledger) if r.get("event") == "recovery-observation"
        ]
        assert observations and observations[-1]["reason_code"] == "expired-only-live-owner"

    def test_recover_reclaims_expired_run_within_budget(
        self, ledger: Any, broker: Any, runtime: FakeRuntime
    ) -> None:
        _open(ledger, broker)
        _acquire(broker, owner="team-run-1", resource="u-a")
        runtime.advance(4000)  # beyond the default lease TTL: ownership derives expired
        outcome = TT.recover(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            expired_only=True,
            max_actions=4,
            at_provider=_ats(),
        )
        run_pass = outcome["recovered_runs"][0]
        assert run_pass["actions_taken"] >= 1
        assert run_pass["complete"] is True

    def test_recover_respects_action_budget(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        for index in range(3):
            _acquire(broker, owner="team-run-1", resource=f"u-{index}")
        outcome = TT.recover(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            expired_only=False,
            max_actions=2,
            at_provider=_ats(),
        )
        assert outcome["recovered_runs"][0]["actions_taken"] == 2
        projection = TT.project(TT.read_decision_input(ledger, broker), "team-run-1")
        assert projection["completion_fact_ref"] is None
        assert projection["open_count"] == 1

    def test_recover_observes_even_with_nothing_to_do(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        outcome = TT.recover(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            expired_only=True,
            max_actions=4,
            at_provider=_ats(),
        )
        assert outcome["recovered_runs"][0]["complete"] is True
        observations = [
            r for r in RL.read_facts(ledger) if r.get("event") == "recovery-observation"
        ]
        assert len(observations) == 1
