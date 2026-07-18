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
from typing import Any, cast

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
    return cast(
        dict[str, Any],
        TT.open_run(
            ledger, broker, subplot_id=SUB, session_id="session-1", at=AT, team_run_id=run_id
        ),
    )


def _intend(ledger: Any, run_id: str = "team-run-1", reason: str = "success") -> dict[str, Any]:
    fact = TT.build_teardown_intent(
        subplot_id=SUB, at=AT, team_run_id=run_id, terminal_reason=reason, close_generation=7
    )
    return cast(dict[str, Any], TT.append_teardown_event(ledger, fact))


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
    return cast(dict[str, Any], TT.append_teardown_event(ledger, fact))


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
    return cast(dict[str, Any], TT.append_teardown_event(ledger, fact))


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

    def test_reissued_close_generation_replays_the_one_intent(
        self, ledger: Any, broker: Any
    ) -> None:
        # close_generation is not intent identity: an evicted-then-re-closed owner mints a
        # fresh generation, and that re-append must converge to the recorded intent, never
        # poison the run with a permanent conflict.
        _open(ledger, broker)
        first = _intend(ledger)
        reissued = TT.build_teardown_intent(
            subplot_id=SUB,
            at=AT,
            team_run_id="team-run-1",
            terminal_reason="success",
            close_generation=9,
        )
        replay = TT.append_teardown_event(ledger, reissued)
        assert replay["this_hash"] == first["this_hash"]
        assert len([r for r in RL.read_facts(ledger) if r["event"] == "teardown-intent"]) == 1

    def test_conflicting_duplicate_is_refused(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        _intend(ledger)
        conflicting = TT.build_teardown_intent(
            subplot_id="another-subplot",
            at=AT,
            team_run_id="team-run-1",
            terminal_reason="success",
            close_generation=1,
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


# --------------------------------------------------------------------- action adapters (U3)


def _register_proc(
    broker: Any,
    runtime: FakeRuntime,
    *,
    pid: int,
    alive: bool = True,
    identity: str | None = "proc-start-1",
    escalation: str = "term-only",
    run_id: str = "team-run-1",
) -> Any:
    runtime.processes[pid] = (alive, identity)
    limits = _limits()
    return TT.register_subprocess(
        broker,
        team_run_id=run_id,
        session_id="session-1",
        pid=pid,
        argv_digest="d" * 64,
        policy_sha256=limits.policy_sha256(),
        session_limit=limits.max_concurrent,
        aggregate_limit=limits.aggregate_max_concurrent,
        escalation=escalation,
    )


def _lease_row(broker: Any, lease_id: str) -> dict[str, Any]:
    return next(item for item in broker.inspect()["leases"] if item["lease_id"] == lease_id)


class TestProcessStopAdapter:
    def _adapter(self, broker: Any, kills: list[tuple[int, int]], runtime: FakeRuntime) -> Any:
        def _kill(pid: int, sig: int) -> None:
            kills.append((pid, sig))
            # SIGTERM/SIGKILL on the fake runtime: the process disappears immediately.
            runtime.processes[pid] = (False, None)

        return TT.make_process_stop_adapter(broker, kill=_kill, sleep=lambda _s: None)

    def test_term_success_releases_with_signal_receipt(
        self, broker: Any, runtime: FakeRuntime
    ) -> None:
        lease = _register_proc(broker, runtime, pid=4242)
        kills: list[tuple[int, int]] = []
        outcome = self._adapter(broker, kills, runtime)(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "released"
        assert kills == [(4242, 15)]
        assert "process:signal-receipt:sigterm" in outcome.evidence_refs
        assert _lease_row_absent(broker, lease.lease_id)

    def test_pid_reuse_is_absence_proof_and_never_signals(
        self, broker: Any, runtime: FakeRuntime
    ) -> None:
        lease = _register_proc(broker, runtime, pid=4242)
        runtime.processes[4242] = (True, "different-process-start")
        kills: list[tuple[int, int]] = []
        outcome = self._adapter(broker, kills, runtime)(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "already-absent"
        assert outcome.reason_code == "pid-identity-mismatch"
        assert kills == []

    def test_boot_change_is_absence_proof_and_never_signals(
        self, broker: Any, runtime: FakeRuntime
    ) -> None:
        lease = _register_proc(broker, runtime, pid=4242)
        runtime.boot = "boot-b"
        kills: list[tuple[int, int]] = []
        outcome = self._adapter(broker, kills, runtime)(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "already-absent"
        assert outcome.reason_code == "boot-identity-changed"
        assert kills == []

    def test_exited_process_is_already_absent(self, broker: Any, runtime: FakeRuntime) -> None:
        lease = _register_proc(broker, runtime, pid=4242)
        runtime.processes[4242] = (False, None)
        kills: list[tuple[int, int]] = []
        outcome = self._adapter(broker, kills, runtime)(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "already-absent"
        assert outcome.reason_code == "process-not-running"
        assert kills == []

    def test_survivor_without_escalation_is_retained(
        self, broker: Any, runtime: FakeRuntime
    ) -> None:
        lease = _register_proc(broker, runtime, pid=4242)
        kills: list[tuple[int, int]] = []

        def _kill_noop(pid: int, sig: int) -> None:
            kills.append((pid, sig))  # the process ignores the signal

        adapter = TT.make_process_stop_adapter(
            broker, kill=_kill_noop, sleep=lambda _s: None, term_wait_seconds=0.3
        )
        outcome = adapter(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "retained"
        assert outcome.reason_code == "alive-after-term-no-escalation"
        assert kills == [(4242, 15)]
        assert not _lease_row_absent(broker, lease.lease_id)

    def test_explicit_term_then_kill_escalates_and_releases(
        self, broker: Any, runtime: FakeRuntime
    ) -> None:
        lease = _register_proc(broker, runtime, pid=4242, escalation="term-then-kill")
        kills: list[tuple[int, int]] = []

        def _kill(pid: int, sig: int) -> None:
            kills.append((pid, sig))
            if sig == 9:
                runtime.processes[pid] = (False, None)

        adapter = TT.make_process_stop_adapter(
            broker, kill=_kill, sleep=lambda _s: None, term_wait_seconds=0.3
        )
        outcome = adapter(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "released"
        assert kills == [(4242, 15), (4242, 9)]
        assert "process:signal-receipt:term-then-kill" in outcome.evidence_refs

    def test_permission_error_fails_safe(self, broker: Any, runtime: FakeRuntime) -> None:
        lease = _register_proc(broker, runtime, pid=4242)

        def _kill(_pid: int, _sig: int) -> None:
            raise PermissionError("not ours")

        adapter = TT.make_process_stop_adapter(broker, kill=_kill, sleep=lambda _s: None)
        outcome = adapter(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "retained"
        assert outcome.reason_code == "signal-permission-denied"

    def test_real_owned_subprocess_is_terminated(self, broker: Any, runtime: FakeRuntime) -> None:
        """R8 end to end against a real owned child: TERM lands, identity releases."""
        import subprocess
        import sys as _sys
        import time as _time

        child = subprocess.Popen(  # noqa: S603
            [_sys.executable, "-c", "import time; time.sleep(60)"]
        )
        try:
            identity = B._default_process_identity(child.pid)
            assert identity is not None
            runtime.processes[child.pid] = (True, identity)
            lease = _register_proc(broker, runtime, pid=child.pid, alive=True, identity=identity)

            def _real_kill(pid: int, sig: int) -> None:
                __import__("os").kill(pid, sig)
                child.wait(timeout=10)
                runtime.processes[pid] = (False, None)

            adapter = TT.make_process_stop_adapter(
                broker, kill=_real_kill, sleep=_time.sleep, term_wait_seconds=5.0
            )
            outcome = adapter(_lease_row(broker, lease.lease_id))
            assert outcome.disposition == "released"
            assert child.poll() is not None
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)


def _lease_row_absent(broker: Any, lease_id: str) -> bool:
    return all(item["lease_id"] != lease_id for item in broker.inspect()["leases"])


class TestResidentStopAdapter:
    def _bound_resident(self, broker: Any) -> Any:
        _acquire(broker, owner="team-run-1", resource="u-resident")
        return broker.claim(
            session_id="session-1",
            agent_type="worker",
            agent_id="resident-1",
            resource_ref={"logical_unit_id": "u-resident"},
        )

    def test_resident_without_terminal_receipt_is_retained(self, broker: Any) -> None:
        lease = self._bound_resident(broker)
        adapter = TT.make_resident_stop_adapter(broker)
        outcome = adapter(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "retained"
        assert outcome.reason_code == "no-terminal-receipt"
        assert not _lease_row_absent(broker, lease.lease_id)

    def test_resident_with_terminal_receipt_releases(self, broker: Any) -> None:
        lease = self._bound_resident(broker)
        assert broker.record_child_terminal("resident-1")
        adapter = TT.make_resident_stop_adapter(broker)
        outcome = adapter(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "released"
        assert any("terminal-at" in ref for ref in outcome.evidence_refs)
        assert _lease_row_absent(broker, lease.lease_id)

    def test_superseded_token_is_retained(self, broker: Any) -> None:
        lease = self._bound_resident(broker)
        row = dict(_lease_row(broker, lease.lease_id))
        row["fencing_sequence"] = row["fencing_sequence"] - 1
        adapter = TT.make_resident_stop_adapter(broker)
        outcome = adapter(row)
        assert outcome.disposition == "retained"
        assert outcome.reason_code == "lease-generation-superseded"


class TestWorktreeSweepAdapter:
    def _worktree(self, broker: Any, tmp_path: Path, *, owner: str = "team-run-1") -> Any:
        return broker.acquire_worktree(
            owner_id=owner,
            session_id="session-1",
            resource_ref={
                "repo_root": str(tmp_path),
                "outcome_id": "outcome-1",
                "subplot_id": "sub-1",
            },
            owner_pid=987654,
        )

    def test_live_owner_worktree_is_retained(
        self, broker: Any, tmp_path: Path, runtime: FakeRuntime
    ) -> None:
        runtime.processes[987654] = (True, None)
        lease = self._worktree(broker, tmp_path)
        adapter = TT.make_worktree_sweep_adapter(broker)
        outcome = adapter(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "retained"
        assert not _lease_row_absent(broker, lease.lease_id)

    def test_dead_owner_worktree_is_swept_through_the_reaper(
        self, broker: Any, tmp_path: Path, runtime: FakeRuntime
    ) -> None:
        runtime.processes[987654] = (False, None)
        lease = self._worktree(broker, tmp_path)
        runtime.advance(4000)  # expire the lease so the sweep may consider it
        reaped: list[Any] = []

        def _reaper(resource: Any) -> bool:
            reaped.append(resource)
            return True

        adapter = TT.make_worktree_sweep_adapter(broker, worktree_reaper=_reaper)
        outcome = adapter(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "released"
        assert reaped and reaped[0]["subplot_id"] == "sub-1"
        assert _lease_row_absent(broker, lease.lease_id)

    def test_reap_failure_is_retained_for_retry(
        self, broker: Any, tmp_path: Path, runtime: FakeRuntime
    ) -> None:
        runtime.processes[987654] = (False, None)
        lease = self._worktree(broker, tmp_path)
        runtime.advance(4000)
        adapter = TT.make_worktree_sweep_adapter(broker, worktree_reaper=lambda _r: False)
        outcome = adapter(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "retained"
        assert outcome.reason_code == "sweep:reap-failed"
        assert not _lease_row_absent(broker, lease.lease_id)

    def test_without_reaper_the_worktree_stays_visible(
        self, broker: Any, tmp_path: Path, runtime: FakeRuntime
    ) -> None:
        runtime.processes[987654] = (False, None)
        lease = self._worktree(broker, tmp_path)
        runtime.advance(4000)
        adapter = TT.make_worktree_sweep_adapter(broker)
        outcome = adapter(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "retained"
        assert outcome.reason_code == "sweep:expired-no-reaper"


class TestEndToEndReclaim:
    def test_mixed_resources_reclaim_to_zero_open(
        self, ledger: Any, broker: Any, runtime: FakeRuntime, tmp_path: Path
    ) -> None:
        _open(ledger, broker)
        _acquire(broker, owner="team-run-1", resource="u-provisional")
        proc_lease = _register_proc(broker, runtime, pid=5150)
        kills: list[tuple[int, int]] = []

        def _kill(pid: int, sig: int) -> None:
            kills.append((pid, sig))
            runtime.processes[pid] = (False, None)

        adapters = TT.production_adapters(broker, kill=_kill, sleep=lambda _s: None)
        projection = TT.reclaim_all(
            ledger,
            broker,
            adapters,
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="success",
            at_provider=_ats(),
        )
        assert projection["open_count"] == 0
        assert projection["completion_fact_ref"] is not None
        assert projection["released_count"] == 2
        assert kills == [(5150, 15)]
        assert _lease_row_absent(broker, proc_lease.lease_id)


# --------------------------------------------------------------------- idle eviction (U4)


class TestIdleEvictionGate:
    def _resident(self, broker: Any, unit: str = "u-resident") -> Any:
        _acquire(broker, owner="team-run-1", resource=unit)
        return broker.claim(
            session_id="session-1",
            agent_type="worker",
            agent_id=f"resident-{unit}",
            resource_ref={"logical_unit_id": unit},
        )

    def _decision(self, classification: str, authority: str = "none") -> dict[str, Any]:
        return {
            "schema": "liveness_decision.v1",
            "subject_id": "subject-1",
            "classification": classification,
            "terminal_authority": authority,
            "generation": "gen-1",
        }

    @pytest.mark.parametrize(
        "classification",
        [
            "healthy",
            "heartbeat-suspect",
            "chatty-artifactless",
            "reping-required",
            "reping-send-unresolved",
            "reping-delivery-blocked",
            "evidence-error",
        ],
    )
    def test_unconfirmed_classifications_never_authorize(
        self, broker: Any, classification: str
    ) -> None:
        lease = self._resident(broker)
        verdict = TT.authorize_resident_stop(
            broker,
            self._decision(classification),
            team_run_id="team-run-1",
            lease_id=lease.lease_id,
        )
        assert verdict["authorized"] is False
        assert classification in verdict["reason_code"]

    def test_confirmed_stalled_with_authority_authorizes_exact_resident(self, broker: Any) -> None:
        lease = self._resident(broker)
        verdict = TT.authorize_resident_stop(
            broker,
            self._decision("confirmed-stalled", authority="team-reping-confirmed"),
            team_run_id="team-run-1",
            lease_id=lease.lease_id,
        )
        assert verdict["authorized"] is True
        assert verdict["reason_code"] == "confirmed-stalled"
        assert verdict["lease_id"] == lease.lease_id
        assert verdict["agent_id"] == "resident-u-resident"

    def test_confirmed_without_terminal_authority_is_refused(self, broker: Any) -> None:
        lease = self._resident(broker)
        verdict = TT.authorize_resident_stop(
            broker,
            self._decision("confirmed-stalled"),
            team_run_id="team-run-1",
            lease_id=lease.lease_id,
        )
        assert verdict["authorized"] is False
        assert verdict["reason_code"] == "confirmed-without-terminal-authority"

    def test_missing_decision_and_foreign_owner_are_refused(self, broker: Any) -> None:
        lease = self._resident(broker)
        no_decision = TT.authorize_resident_stop(
            broker, None, team_run_id="team-run-1", lease_id=lease.lease_id
        )
        assert no_decision["authorized"] is False
        assert no_decision["reason_code"] == "no-liveness-decision"
        foreign = TT.authorize_resident_stop(
            broker,
            self._decision("confirmed-stalled", authority="team-reping-confirmed"),
            team_run_id="team-run-9",
            lease_id=lease.lease_id,
        )
        assert foreign["authorized"] is False
        assert foreign["reason_code"] == "not-owned-by-run"

    def test_explicit_segment_shed_authorizes_without_liveness(self, broker: Any) -> None:
        lease = self._resident(broker)
        verdict = TT.authorize_resident_stop(
            broker,
            None,
            team_run_id="team-run-1",
            lease_id=lease.lease_id,
            explicit_shed=True,
        )
        assert verdict["authorized"] is True
        assert verdict["reason_code"] == "segment-boundary-shed"

    def test_evicting_one_resident_retains_the_warm_peer(self, broker: Any) -> None:
        stalled = self._resident(broker, "u-stalled")
        warm = self._resident(broker, "u-warm")
        verdict = TT.authorize_resident_stop(
            broker,
            self._decision("confirmed-stalled", authority="team-reping-confirmed"),
            team_run_id="team-run-1",
            lease_id=stalled.lease_id,
        )
        assert verdict["authorized"] is True
        assert broker.record_child_terminal("resident-u-stalled")
        outcome = TT.make_resident_stop_adapter(broker)(_lease_row(broker, stalled.lease_id))
        assert outcome.disposition == "released"
        assert _lease_row_absent(broker, stalled.lease_id)
        assert not _lease_row_absent(broker, warm.lease_id)


class TestCrashRecoveryAcceptance:
    def test_sigkilled_subprocess_is_recovered_after_ttl(
        self, ledger: Any, broker: Any, runtime: FakeRuntime
    ) -> None:
        """The kill-mid-run acceptance (R5/KTD3): a SIGKILLed owned child cannot run B8;
        a later bounded recovery pass after TTL expiry proves absence and completes."""
        import signal as _signal
        import subprocess
        import sys as _sys

        child = subprocess.Popen(  # noqa: S603
            [_sys.executable, "-c", "import time; time.sleep(60)"]
        )
        identity = B._default_process_identity(child.pid)
        assert identity is not None
        runtime.processes[child.pid] = (True, identity)
        _open(ledger, broker)
        _register_proc(broker, runtime, pid=child.pid, alive=True, identity=identity)

        # SIGKILL: no finalizer runs, no teardown fact lands — the honest crash shape.
        child.send_signal(_signal.SIGKILL)
        child.wait(timeout=10)
        runtime.processes[child.pid] = (False, None)
        runtime.advance(4000)  # injected TTL boundary: ownership derives expired

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
        assert run_pass["complete"] is True
        projection = TT.project(TT.read_decision_input(ledger, broker), "team-run-1")
        assert projection["open_count"] == 0
        assert projection["already_absent_count"] == 1
        assert projection["completion_fact_ref"] is not None


# --------------------------------------------------------- ceremony round-1 regressions


class TestAdmissionEvictionResilience:
    """The bounded closed-owner map may evict and re-close an owner under a fresh
    generation; teardown must converge across that seam, never poison (round-1 F1)."""

    def _evict(self, broker: Any, count: int = 128) -> None:
        for index in range(count):
            broker.close_owner_admission(owner_id=f"churn-owner-{index}")

    def test_evicted_close_record_re_close_converges_instead_of_poisoning(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker)
        _acquire(broker, owner="team-run-1", resource="u-a")
        blocked = TT.reclaim_all(
            ledger,
            broker,
            TT.ReclaimAdapters(),  # conservative retain: the run stays incomplete
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="hard-fail",
            at_provider=_ats(),
        )
        assert blocked["completion_fact_ref"] is None
        self._evict(broker)
        assert broker.inspect_owner_admission("team-run-1") is None
        converged = TT.reclaim_all(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="hard-fail",
            at_provider=_ats(),
        )
        assert converged["completion_fact_ref"] is not None
        intents = [r for r in RL.read_facts(ledger) if r.get("event") == "teardown-intent"]
        assert len(intents) == 1

    def test_session_end_request_survives_generation_reissue(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker)
        TT.request(
            ledger,
            broker,
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="success",
            at=AT,
        )
        self._evict(broker)
        repeated = TT.request(
            ledger,
            broker,
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="success",
            at=AT,
        )
        assert repeated["recorded"] == "teardown-intent"
        intents = [r for r in RL.read_facts(ledger) if r.get("event") == "teardown-intent"]
        assert len(intents) == 1

    def test_unfenced_window_lease_is_captured_by_next_pass(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        TT.request(
            ledger,
            broker,
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="success",
            at=AT,
        )
        self._evict(broker)
        # The evicted window is real: admission for the torn-down owner lapses open.
        late = _acquire(broker, owner="team-run-1", resource="u-late")
        assert late is not None
        # The driver re-closes at pass start and snapshots AFTER the close, so the
        # window lease is captured and reclaimed — eviction never leaks past a pass.
        projection = TT.reclaim_all(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="success",
            at_provider=_ats(),
        )
        assert projection["open_count"] == 0
        assert projection["completion_fact_ref"] is not None

    @pytest.mark.parametrize("mode", ["evicted", "superseded"])
    def test_completion_refused_when_close_generation_is_lost(
        self, ledger: Any, broker: Any, mode: str
    ) -> None:
        class _LossyBroker:
            def __init__(self, inner: Any) -> None:
                self._inner = inner

            def __getattr__(self, name: str) -> Any:
                return getattr(self._inner, name)

            def inspect_owner_admission(self, owner_id: str) -> Any:
                real = self._inner.inspect_owner_admission(owner_id)
                if mode == "evicted" or real is None:
                    return None
                return {**real, "close_generation": int(real["close_generation"]) + 999}

        _open(ledger, broker)
        lossy = _LossyBroker(broker)
        with pytest.raises(TT.TeardownError, match="no longer the closed generation"):
            TT.reclaim_all(
                ledger,
                lossy,
                TT.production_adapters(lossy),
                subplot_id=SUB,
                team_run_id="team-run-1",
                terminal_reason="success",
                at_provider=_ats(),
            )
        completes = [r for r in RL.read_facts(ledger) if r.get("event") == "teardown-complete"]
        assert completes == []


class TestConcurrentReclaim:
    def test_concurrent_reclaim_invokes_adapter_once_per_action(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker)
        _acquire(broker, owner="team-run-1", resource="u-a")
        production = TT.production_adapters(broker)
        invocations: list[str] = []
        count_lock = threading.Lock()

        def _counting_release(lease: Any) -> Any:
            with count_lock:
                invocations.append(str(lease.get("lease_id")))
            return production.lease_release(lease)

        adapters = TT.ReclaimAdapters(lease_release=_counting_release)
        barrier = threading.Barrier(2)
        projections: list[dict[str, Any]] = []
        errors: list[BaseException] = []

        def _pass() -> None:
            barrier.wait()
            try:
                projections.append(
                    TT.reclaim_all(
                        ledger,
                        broker,
                        adapters,
                        subplot_id=SUB,
                        team_run_id="team-run-1",
                        terminal_reason="success",
                        at_provider=_ats(),
                    )
                )
            except BaseException as exc:  # noqa: BLE001 - collected for assertion
                errors.append(exc)

        threads = [threading.Thread(target=_pass) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        assert errors == []
        assert len(invocations) == 1
        assert all(p["completion_fact_ref"] is not None for p in projections)
        attempts = [r for r in RL.read_facts(ledger) if r.get("event") == "resource-attempt"]
        results = [r for r in RL.read_facts(ledger) if r.get("event") == "resource-result"]
        assert len(attempts) == 1
        assert len(results) == 1


class TestRecoveryIsolation:
    def test_poisoned_run_does_not_block_newer_runs_recovery(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker, run_id="team-run-poisoned")
        _acquire(broker, owner="team-run-poisoned", session="session-p", resource="u-p")
        _open(ledger, broker, run_id="team-run-healthy")
        _acquire(broker, owner="team-run-healthy", session="session-h", resource="u-h")
        production = TT.production_adapters(broker)

        def _selective_release(lease: Any) -> Any:
            if str(lease.get("owner_id")) == "team-run-poisoned":
                raise TT.TeardownError("poisoned-run adapter refusal")
            return production.lease_release(lease)

        outcome = TT.recover(
            ledger,
            broker,
            TT.ReclaimAdapters(lease_release=_selective_release),
            subplot_id=SUB,
            expired_only=False,
            max_actions=8,
            at_provider=_ats(),
        )
        by_run = {entry["team_run_id"]: entry for entry in outcome["recovered_runs"]}
        assert by_run["team-run-poisoned"]["error"] == "TeardownError"
        assert by_run["team-run-healthy"]["complete"] is True
        observations = [
            r for r in RL.read_facts(ledger) if r.get("event") == "recovery-observation"
        ]
        codes = {r["team_run_id"]: r["reason_code"] for r in observations}
        assert codes["team-run-poisoned"] == "recovery-run-error:TeardownError"
        assert codes["team-run-healthy"] == "recovery-pass"


class TestProcessStopBranches:
    """Round-1 TST-2/TST-5: every reachable retain/absent/failed branch pins its
    disposition and reason so a fail-safe can never silently become a release."""

    def test_survivor_of_kill_is_failed_and_blocks_completion(
        self, ledger: Any, broker: Any, runtime: FakeRuntime
    ) -> None:
        _open(ledger, broker)
        lease = _register_proc(broker, runtime, pid=4242, escalation="term-then-kill")
        kills: list[tuple[int, int]] = []

        def _immortal_kill(pid: int, sig: int) -> None:
            kills.append((pid, sig))  # the process never exits

        adapter = TT.make_process_stop_adapter(broker, kill=_immortal_kill, sleep=lambda _s: None)
        outcome = adapter(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "failed"
        assert outcome.reason_code == "alive-after-kill"
        assert [sig for _pid, sig in kills] == [15, 9]
        assert _lease_row(broker, lease.lease_id) is not None
        projection = TT.reclaim_all(
            ledger,
            broker,
            TT.ReclaimAdapters(
                process_stop=TT.make_process_stop_adapter(
                    broker, kill=_immortal_kill, sleep=lambda _s: None
                )
            ),
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="hard-fail",
            at_provider=_ats(),
        )
        assert projection["completion_fact_ref"] is None

    def test_unrecorded_process_identity_is_retained(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        plain = _acquire(broker, owner="team-run-1", resource="u-plain")
        kills: list[tuple[int, int]] = []
        adapter = TT.make_process_stop_adapter(
            broker, kill=lambda p, s: kills.append((p, s)), sleep=lambda _s: None
        )
        outcome = adapter(_lease_row(broker, plain.lease_id))
        assert outcome.disposition == "retained"
        assert outcome.reason_code == "process-identity-unrecorded"
        assert kills == []

    def test_unreadable_process_identity_is_retained(
        self, broker: Any, runtime: FakeRuntime, ledger: Any
    ) -> None:
        _open(ledger, broker)
        lease = _register_proc(broker, runtime, pid=4242, alive=True, identity="proc-start-1")
        runtime.processes[4242] = (True, None)
        kills: list[tuple[int, int]] = []
        adapter = TT.make_process_stop_adapter(
            broker, kill=lambda p, s: kills.append((p, s)), sleep=lambda _s: None
        )
        outcome = adapter(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "retained"
        assert outcome.reason_code == "process-identity-unavailable"
        assert kills == []

    def test_exit_during_term_send_is_absence_proof(
        self, broker: Any, runtime: FakeRuntime, ledger: Any
    ) -> None:
        _open(ledger, broker)
        lease = _register_proc(broker, runtime, pid=4242)

        def _gone_on_term(_pid: int, _sig: int) -> None:
            raise ProcessLookupError

        adapter = TT.make_process_stop_adapter(broker, kill=_gone_on_term, sleep=lambda _s: None)
        outcome = adapter(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "already-absent"
        assert outcome.reason_code == "exited-during-signal"
        assert _lease_row_absent(broker, lease.lease_id)

    def test_exit_before_kill_escalation_is_released(
        self, broker: Any, runtime: FakeRuntime, ledger: Any
    ) -> None:
        _open(ledger, broker)
        lease = _register_proc(broker, runtime, pid=4242, escalation="term-then-kill")
        sent: list[int] = []

        def _exits_between_signals(_pid: int, sig: int) -> None:
            sent.append(sig)
            if sig == 9:
                raise ProcessLookupError

        adapter = TT.make_process_stop_adapter(
            broker, kill=_exits_between_signals, sleep=lambda _s: None
        )
        outcome = adapter(_lease_row(broker, lease.lease_id))
        assert outcome.disposition == "released"
        assert "process:signal-receipt:exited-before-kill" in outcome.evidence_refs
        assert sent == [15, 9]
        assert _lease_row_absent(broker, lease.lease_id)


class TestDefensiveRefusals:
    """Round-1 TST-3/TST-6/TST-7: reachable typed refusals stay typed."""

    def test_eviction_gate_refuses_absent_lease(self, broker: Any) -> None:
        verdict = TT.authorize_resident_stop(
            broker,
            {"classification": "confirmed-stalled", "terminal_authority": "team"},
            team_run_id="team-run-1",
            lease_id="lease-that-never-existed",
        )
        assert verdict["authorized"] is False
        assert verdict["reason_code"] == "lease-absent"

    def test_non_object_broker_snapshot_is_refused(self, ledger: Any) -> None:
        class _BadBroker:
            def inspect(self) -> Any:
                return ["not", "a", "mapping"]

        with pytest.raises(TT.TeardownError, match="non-object snapshot"):
            TT.read_decision_input(ledger, _BadBroker())

    def test_snapshot_without_lease_list_is_refused(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)

        class _NoLeasesBroker:
            def inspect(self) -> Any:
                return {"leases": None}

        decision = TT.read_decision_input(ledger, _NoLeasesBroker())
        with pytest.raises(TT.TeardownError, match="no lease list"):
            TT.project(decision, "team-run-1")

    @pytest.mark.parametrize(
        "factory",
        [
            lambda broker: TT.make_resident_stop_adapter(broker),
            lambda broker: TT.production_adapters(broker).lease_release,
            lambda broker: TT.make_worktree_sweep_adapter(broker),
        ],
        ids=["resident-stop", "lease-release", "worktree-sweep"],
    )
    def test_adapter_head_none_is_already_absent(self, broker: Any, factory: Any) -> None:
        adapter = factory(broker)
        outcome = adapter({"lease_id": "vanished-lease", "owner_id": "team-run-1"})
        assert outcome.disposition == "already-absent"
        assert "broker:lease-absent:vanished-lease" in outcome.evidence_refs

    def test_recover_refuses_negative_budget(self, ledger: Any, broker: Any) -> None:
        with pytest.raises(TT.TeardownError, match="must be non-negative"):
            TT.recover(
                ledger,
                broker,
                TT.ReclaimAdapters(),
                subplot_id=SUB,
                expired_only=True,
                max_actions=-1,
                at_provider=_ats(),
            )

    def test_complete_without_matching_intent_is_refused(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker)
        _intend(ledger, reason="success")
        orphan = TT.build_teardown_complete(
            subplot_id=SUB,
            at=AT,
            team_run_id="team-run-1",
            intent_id=TT.intent_id_for("team-run-1", "hard-fail"),
            close_generation=7,
            released_count=0,
            already_absent_count=0,
        )
        with pytest.raises(TT.TeardownError, match="requires its teardown-intent"):
            TT.append_teardown_event(ledger, orphan)

    def test_project_refuses_unknown_run(self, ledger: Any, broker: Any) -> None:
        with pytest.raises(TT.TeardownError, match="unknown team run"):
            TT.project(TT.read_decision_input(ledger, broker), "team-run-never-opened")

    def test_register_subprocess_refuses_unknown_escalation(
        self, broker: Any, runtime: FakeRuntime
    ) -> None:
        runtime.processes[4242] = (True, "proc-start-1")
        limits = _limits()
        with pytest.raises(TT.TeardownError, match="escalation must be"):
            TT.register_subprocess(
                broker,
                team_run_id="team-run-1",
                session_id="session-1",
                pid=4242,
                argv_digest="d" * 64,
                policy_sha256=limits.policy_sha256(),
                session_limit=limits.max_concurrent,
                aggregate_limit=limits.aggregate_max_concurrent,
                escalation="maim",
            )


# --------------------------------------------------------- ceremony round-2 regressions


class TestFenceSuccessorAndBatchCall:
    """Round-2 TST-FENCE-GAP-1: the two remaining guarded admission paths refuse a
    closed owner, so no admission-shaped operation can slip the #358 fence."""

    def test_acquire_successor_refuses_closed_owner(self, broker: Any) -> None:
        limits = _limits()
        broker.close_owner_admission(owner_id="team-run-1")
        with pytest.raises(B.OwnerAdmissionClosedError):
            broker.acquire_successor(
                owner_id="team-run-1",
                session_id="session-1",
                policy_sha256=limits.policy_sha256(),
                session_limit=limits.max_concurrent,
                aggregate_limit=limits.aggregate_max_concurrent,
                mutation="read-write",
                resource_ref={"logical_unit_id": "u-succ"},
                predecessor_token=B.FencingToken(broker_epoch="epoch-x", fencing_sequence=1),
                predecessor_receipt_sha256="a" * 64,
            )

    def test_prepare_batch_call_refuses_closed_owner_slot(self, broker: Any) -> None:
        limits = _limits()
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
        broker.close_owner_admission(owner_id="team-run-1")
        with pytest.raises(B.OwnerAdmissionClosedError):
            broker.prepare_batch_call(
                session_id="session-1",
                batch_id="batch-1",
                agent_type="worker",
                tool_use_id="tool-1",
            )


class TestRecoveryBudget:
    """Round-2 TST-BUDGET-GAP-2 / DA-R2-1: the cross-run action budget bounds real
    adapter invocations only, and skipped runs still get an honest observation."""

    def test_budget_exhausted_skips_later_runs_with_observation(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker, run_id="team-run-a")
        _acquire(broker, owner="team-run-a", session="session-a", resource="u-a")
        _open(ledger, broker, run_id="team-run-b")
        _acquire(broker, owner="team-run-b", session="session-b", resource="u-b")
        outcome = TT.recover(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            expired_only=False,
            max_actions=1,
            at_provider=_ats(),
        )
        by_run = {entry["team_run_id"]: entry for entry in outcome["recovered_runs"]}
        assert by_run["team-run-a"]["actions_taken"] == 1
        assert by_run["team-run-a"]["complete"] is True
        assert by_run["team-run-b"]["skipped"] == "budget"
        assert sum(e.get("actions_taken", 0) for e in outcome["recovered_runs"]) == 1
        codes = {
            r["team_run_id"]: r["reason_code"]
            for r in RL.read_facts(ledger)
            if r.get("event") == "recovery-observation"
        }
        assert codes["team-run-b"] == "recovery-action-budget-exhausted"

    def test_crash_reconcile_results_do_not_drain_budget(self, ledger: Any, broker: Any) -> None:
        # team-run-a holds only a crash-orphaned attempt over a gone resource: its
        # reconcile is bookkeeping, not an action, and must not starve team-run-b.
        _open(ledger, broker, run_id="team-run-a")
        TT.request(
            ledger,
            broker,
            subplot_id=SUB,
            team_run_id="team-run-a",
            terminal_reason="success",
            at=AT,
        )
        _attempt(ledger, "team-run-a", resource_id="ghost-lease")
        _open(ledger, broker, run_id="team-run-b")
        _acquire(broker, owner="team-run-b", session="session-b", resource="u-b")
        outcome = TT.recover(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            expired_only=False,
            max_actions=1,
            at_provider=_ats(),
        )
        by_run = {entry["team_run_id"]: entry for entry in outcome["recovered_runs"]}
        assert by_run["team-run-a"]["complete"] is True
        assert by_run["team-run-a"]["actions_taken"] == 0
        assert by_run["team-run-b"]["complete"] is True
        assert by_run["team-run-b"]["actions_taken"] == 1

    def test_error_path_does_not_charge_unspent_budget(self, ledger: Any, broker: Any) -> None:
        _open(ledger, broker, run_id="team-run-a")
        _acquire(broker, owner="team-run-a", session="session-a", resource="u-a")
        _open(ledger, broker, run_id="team-run-b")
        _acquire(broker, owner="team-run-b", session="session-b", resource="u-b")
        production = TT.production_adapters(broker)

        def _poisoned_release(lease: Any) -> Any:
            if str(lease.get("owner_id")) == "team-run-a":
                raise TT.TeardownError("poisoned before any result")
            return production.lease_release(lease)

        outcome = TT.recover(
            ledger,
            broker,
            TT.ReclaimAdapters(lease_release=_poisoned_release),
            subplot_id=SUB,
            expired_only=False,
            max_actions=1,
            at_provider=_ats(),
        )
        by_run = {entry["team_run_id"]: entry for entry in outcome["recovered_runs"]}
        assert by_run["team-run-a"]["error"] == "TeardownError"
        assert by_run["team-run-a"]["actions_taken"] == 0
        assert by_run["team-run-b"]["complete"] is True


class TestRecoveryIsolationBrokerErrors:
    """Round-2 CONC-1: isolation covers the broker's own error family, not only
    TeardownError — one corrupt owner record cannot wedge the whole recovery pass."""

    def test_broker_error_for_one_run_does_not_block_newer_runs(
        self, ledger: Any, broker: Any, monkeypatch: Any
    ) -> None:
        _open(ledger, broker, run_id="team-run-a")
        _acquire(broker, owner="team-run-a", session="session-a", resource="u-a")
        _open(ledger, broker, run_id="team-run-b")
        _acquire(broker, owner="team-run-b", session="session-b", resource="u-b")

        # Patch the bound method so type(broker) — and with it the dual-load token
        # module resolution in _current_head — stays the real broker class.
        real_close = broker.close_owner_admission

        def _corrupt_for_a(*, owner_id: str) -> Any:
            if owner_id == "team-run-a":
                raise B.RegistryCorruptError("malformed owner record")
            return real_close(owner_id=owner_id)

        monkeypatch.setattr(broker, "close_owner_admission", _corrupt_for_a)
        outcome = TT.recover(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            expired_only=False,
            max_actions=8,
            at_provider=_ats(),
        )
        by_run = {entry["team_run_id"]: entry for entry in outcome["recovered_runs"]}
        assert by_run["team-run-a"]["error"] == "RegistryCorruptError"
        assert by_run["team-run-b"]["complete"] is True
        codes = {
            r["team_run_id"]: r["reason_code"]
            for r in RL.read_facts(ledger)
            if r.get("event") == "recovery-observation"
        }
        assert codes["team-run-a"] == "recovery-run-error:RegistryCorruptError"


class TestRecoveryEvidenceBestEffort:
    """Round-3 CONC-1-R3-1: per-run isolation is total — a SECOND ledger/broker failure
    while counting or recording one run's evidence degrades to that run's pass entry
    and never aborts the batch."""

    def test_secondary_count_failure_does_not_abort_batch(
        self, ledger: Any, broker: Any, monkeypatch: Any
    ) -> None:
        _open(ledger, broker, run_id="team-run-a")
        _acquire(broker, owner="team-run-a", session="session-a", resource="u-a")
        _open(ledger, broker, run_id="team-run-b")
        _acquire(broker, owner="team-run-b", session="session-b", resource="u-b")
        real_count = TT._count_budgeted_results

        def _corrupt_for_a(ledger_arg: Any, broker_arg: Any, team_run_id: str) -> int:
            if team_run_id == "team-run-a":
                raise RL.RunLedgerError("malformed ledger line")
            return int(real_count(ledger_arg, broker_arg, team_run_id))

        monkeypatch.setattr(TT, "_count_budgeted_results", _corrupt_for_a)
        outcome = TT.recover(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            expired_only=False,
            max_actions=4,
            at_provider=_ats(),
        )
        by_run = {entry["team_run_id"]: entry for entry in outcome["recovered_runs"]}
        assert by_run["team-run-a"]["error"] == "RunLedgerError"
        assert by_run["team-run-a"]["evidence_error"] == "RunLedgerError"
        assert by_run["team-run-a"]["actions_taken"] == 0
        assert by_run["team-run-b"]["complete"] is True
        codes = {
            r["team_run_id"]: r["reason_code"]
            for r in RL.read_facts(ledger)
            if r.get("event") == "recovery-observation"
        }
        assert codes["team-run-a"] == "recovery-run-error:RunLedgerError"
        assert codes["team-run-b"] == "recovery-pass"

    def test_observation_append_failure_does_not_abort_batch(
        self, ledger: Any, broker: Any, monkeypatch: Any
    ) -> None:
        _open(ledger, broker, run_id="team-run-a")
        _acquire(broker, owner="team-run-a", session="session-a", resource="u-a")
        _open(ledger, broker, run_id="team-run-b")
        _acquire(broker, owner="team-run-b", session="session-b", resource="u-b")
        real_append = TT.append_teardown_event

        def _refuse_a_observation(ledger_arg: Any, fact: Any) -> Any:
            if (
                fact.get("event") == "recovery-observation"
                and fact.get("team_run_id") == "team-run-a"
            ):
                raise RL.RunLedgerError("observation refused")
            return real_append(ledger_arg, fact)

        monkeypatch.setattr(TT, "append_teardown_event", _refuse_a_observation)
        outcome = TT.recover(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            expired_only=False,
            max_actions=4,
            at_provider=_ats(),
        )
        by_run = {entry["team_run_id"]: entry for entry in outcome["recovered_runs"]}
        assert by_run["team-run-a"]["complete"] is True
        assert by_run["team-run-a"]["evidence_error"] == "RunLedgerError"
        assert by_run["team-run-b"]["complete"] is True
        codes = {
            r["team_run_id"]: r["reason_code"]
            for r in RL.read_facts(ledger)
            if r.get("event") == "recovery-observation"
        }
        assert "team-run-a" not in codes
        assert codes["team-run-b"] == "recovery-pass"


class TestReclaimGuardLifecycle:
    """Round-2 ARCH-R2-1 / ARCH-R2-2 / CONC-2: the per-run lock sidecar is provisioned
    with a typed failure surface and reclaimed once the run's receipt is final."""

    def test_fresh_repo_reclaim_provisions_store_and_fails_typed(
        self, tmp_path: Path, broker: Any
    ) -> None:
        # On a writable fresh repository the guard's mkdir SUCCEEDS (this path does not
        # enter the OSError wrap — see the next test); the surfaced failure is the
        # unknown-run refusal from the driver, never a raw filesystem traceback.
        fresh = RL.RunLedger(path=tmp_path / "never" / "provisioned" / "run-facts.jsonl")
        with pytest.raises(TT.TeardownError, match="unknown team run"):
            TT.reclaim_all(
                fresh,
                broker,
                TT.ReclaimAdapters(),
                subplot_id=SUB,
                team_run_id="team-run-x",
                terminal_reason="success",
                at_provider=_ats(),
            )
        assert fresh.path.parent.is_dir()

    def test_guard_provisioning_failure_surfaces_typed_refusal(
        self, tmp_path: Path, broker: Any
    ) -> None:
        # Round-3 ARCH-R3-1 / TST-R3-1: a regular file where the store directory belongs
        # makes the guard's mkdir raise — the OSError must surface as the module's typed
        # refusal, never a raw FileExistsError traceback to an operator reclaim.
        blocker = tmp_path / "store"
        blocker.write_text("not a directory\n")
        fresh = RL.RunLedger(path=blocker / "run-facts.jsonl")
        with pytest.raises(TT.TeardownError, match="cannot provision the reclaim guard"):
            TT.reclaim_all(
                fresh,
                broker,
                TT.ReclaimAdapters(),
                subplot_id=SUB,
                team_run_id="team-run-x",
                terminal_reason="success",
                at_provider=_ats(),
            )

    def test_lock_sidecar_persists_while_blocked_and_clears_on_completion(
        self, ledger: Any, broker: Any
    ) -> None:
        _open(ledger, broker)
        _acquire(broker, owner="team-run-1", resource="u-a")
        lock_path = TT._reclaim_lock_path(ledger, "team-run-1")
        blocked = TT.reclaim_all(
            ledger,
            broker,
            TT.ReclaimAdapters(),  # conservative retain: blocked terminal
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="hard-fail",
            at_provider=_ats(),
        )
        assert blocked["completion_fact_ref"] is None
        assert lock_path.exists()
        converged = TT.reclaim_all(
            ledger,
            broker,
            TT.production_adapters(broker),
            subplot_id=SUB,
            team_run_id="team-run-1",
            terminal_reason="hard-fail",
            at_provider=_ats(),
        )
        assert converged["completion_fact_ref"] is not None
        assert not lock_path.exists()


class TestBoundaryGuards:
    """Round-2 TST-BOUNDARY-3 / DA-R2-2: typed boundary refusals stay typed, and a
    driver-bypassing completion append stays visibly inconsistent."""

    def test_bogus_adapter_disposition_is_refused(self) -> None:
        with pytest.raises(TT.TeardownError, match="adapter disposition must be one of"):
            TT.ActionOutcome(disposition="bogus").validated()

    def test_adapter_cannot_emit_driver_reserved_reason_code(
        self, ledger: Any, broker: Any
    ) -> None:
        # Round-3 DA-R2-1-R3-1: the budget exemption is keyed on driver-only bookkeeping
        # literals; an adapter outcome carrying one would impersonate the crash-reconcile
        # seam and dodge the recovery budget, so the contract refuses it loudly at
        # validation time (same precedent as the bogus disposition above).
        with pytest.raises(TT.TeardownError, match="driver-reserved"):
            TT.ActionOutcome(
                disposition="released", reason_code="recovered-after-crash"
            ).validated()
        _open(ledger, broker)
        _acquire(broker, owner="team-run-1", resource="u-a")
        spoof = TT.ReclaimAdapters(
            lease_release=lambda _lease: TT.ActionOutcome(
                disposition="released", reason_code="recovered-after-crash"
            )
        )
        with pytest.raises(TT.TeardownError, match="driver-reserved"):
            TT.reclaim_all(
                ledger,
                broker,
                spoof,
                subplot_id=SUB,
                team_run_id="team-run-1",
                terminal_reason="success",
                at_provider=_ats(),
            )

    def test_default_broker_names_missing_capability(self, monkeypatch: Any) -> None:
        class _NoFenceBroker:
            pass

        class _Authority:
            LeaseBroker = _NoFenceBroker

        monkeypatch.setattr(TT.fleet_commons_shim, "load", lambda _name: _Authority)
        with pytest.raises(TT.TeardownError, match="lacks close_owner_admission"):
            TT.default_broker()

    def test_direct_completion_bypass_stays_visibly_inconsistent(
        self, ledger: Any, broker: Any
    ) -> None:
        # append_teardown_event validates ledger-internal transitions only; the broker
        # zero-open gate is the driver's. A bypass cannot hide the open resource: the
        # projection derives open_count live from the broker beside the recorded receipt.
        _open(ledger, broker)
        _acquire(broker, owner="team-run-1", resource="u-open")
        _intend(ledger)
        bypass = TT.build_teardown_complete(
            subplot_id=SUB,
            at=AT,
            team_run_id="team-run-1",
            intent_id=TT.intent_id_for("team-run-1", "success"),
            close_generation=7,
            released_count=0,
            already_absent_count=0,
        )
        TT.append_teardown_event(ledger, bypass)
        projection = TT.project(TT.read_decision_input(ledger, broker), "team-run-1")
        assert projection["completion_fact_ref"] is not None
        assert projection["open_count"] == 1
