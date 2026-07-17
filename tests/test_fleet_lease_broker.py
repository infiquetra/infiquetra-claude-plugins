"""Contract tests for fleet-core's lease-backed admission authority (#356)."""

from __future__ import annotations

import importlib.util
import json
import multiprocessing
import os
import stat
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
BROKER_PATH = (
    ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "lease_broker.py"
)
POLICY_PATH = (
    ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "concurrency_policy.py"
)


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


B = _load(BROKER_PATH, "fleet_lease_broker_under_test")
P = _load(POLICY_PATH, "fleet_concurrency_policy_under_test")


@dataclass
class FakeRuntime:
    wall: datetime = datetime(2026, 7, 16, 12, tzinfo=UTC)
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

    def advance(self, seconds: int, *, wall_seconds: int | None = None) -> None:
        self.monotonic += seconds * 1_000_000_000
        self.wall += timedelta(seconds=seconds if wall_seconds is None else wall_seconds)


@pytest.fixture
def runtime() -> FakeRuntime:
    return FakeRuntime()


@pytest.fixture
def broker(tmp_path: Path, runtime: FakeRuntime) -> Any:
    return B.LeaseBroker(tmp_path / "authority", providers=runtime.providers())


def _limits(**overrides: int) -> Any:
    return P.AdmissionLimits(**overrides)


def _agent(
    broker: Any,
    *,
    owner: str = "owner",
    session: str = "session",
    limits: Any | None = None,
    resource: str | None = None,
    ttl: int = 300,
    tool: str | None = None,
    agent_type: str = "worker",
) -> Any:
    effective = _limits() if limits is None else limits
    return broker.acquire_agent(
        owner_id=owner,
        session_id=session,
        policy_sha256=effective.policy_sha256(),
        session_limit=effective.max_concurrent,
        aggregate_limit=effective.aggregate_max_concurrent,
        mutation="read-write",
        ttl_seconds=ttl,
        resource_ref=None if resource is None else {"logical_unit_id": resource},
        tool_use_id=tool,
        agent_type=agent_type,
    )


def _worktree_resource(root: Path, index: int = 1) -> dict[str, str]:
    return {
        "repo_root": str(root),
        "outcome_id": "356",
        "subplot_id": f"sub-{index}",
    }


def _raw_registry(broker: Any) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(broker.registry_path.read_text(encoding="utf-8")))


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys.update(_all_keys(child))
        return keys
    if isinstance(value, list):
        nested_keys: set[str] = set()
        for child in value:
            nested_keys.update(_all_keys(child))
        return nested_keys
    return set()


def test_runtime_neutral_default_and_explicit_root_resolution(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    default = B.resolve_state_root(
        {"CLAUDE_PLUGIN_ROOT": "/claude", "PLUGIN_DATA": "/plugin-data"}, home=home
    )
    assert default == home / ".local/state/infiquetra/fleet-leases"
    assert ".claude" not in str(default)
    assert ".codex" not in str(default)

    explicit = tmp_path / "explicit"
    assert B.resolve_state_root({B.STATE_ENV: str(explicit)}, home=home) == explicit
    xdg = tmp_path / "xdg"
    assert B.resolve_state_root({B.XDG_STATE_ENV: str(xdg)}, home=home) == (
        xdg / "infiquetra/fleet-leases"
    )


@pytest.mark.parametrize("name", [B.STATE_ENV, B.XDG_STATE_ENV])
def test_relative_or_unsafe_configured_root_is_rejected(name: str) -> None:
    with pytest.raises(B.UnsafeAuthorityError, match="normalized absolute"):
        B.resolve_state_root({name: "relative/state"})
    with pytest.raises(B.UnsafeAuthorityError, match="normalized absolute"):
        B.resolve_state_root({name: "/tmp/../escaped"})


def test_inspect_is_read_only_and_root_identity_is_stable(tmp_path: Path) -> None:
    root = tmp_path / "authority"
    first = B.LeaseBroker(root)
    second = B.LeaseBroker(Path(str(root)))
    assert first.root_sha256 == second.root_sha256
    assert first.inspect() == {
        "exists": False,
        "root_sha256": first.root_sha256,
        "leases": [],
    }
    assert not root.exists()


def test_first_write_modes_and_no_committed_expiry_field(broker: Any) -> None:
    lease = _agent(broker, resource="unit-1")
    assert lease.token.fencing_sequence == 1
    assert stat.S_IMODE(broker.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(broker.lock_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(broker.registry_path.stat().st_mode) == 0o600
    raw = _raw_registry(broker)
    assert raw["schema"] == B.SCHEMA
    assert not ({"status", "expired", "expires_at", "stale"} & _all_keys(raw))


def test_session_and_minimum_live_aggregate_limits(broker: Any) -> None:
    session_two = _limits(max_concurrent=2, readonly_max_concurrent=4, aggregate_max_concurrent=5)
    _agent(broker, session="same", limits=session_two)
    _agent(broker, session="same", limits=session_two)
    with pytest.raises(B.CapacityExhaustedError) as captured:
        _agent(broker, session="same", limits=session_two)
    assert captured.value.earliest_expiry is not None

    aggregate_three = _limits(
        max_concurrent=3, readonly_max_concurrent=3, aggregate_max_concurrent=3
    )
    other = B.LeaseBroker(broker.root, providers=broker.providers)
    with pytest.raises(B.PolicyMismatchError):
        _agent(other, session="same", limits=aggregate_three)

    broker.release_owner("owner", session_id="same")
    _agent(broker, owner="a", session="a", limits=aggregate_three)
    _agent(broker, owner="b", session="b", limits=aggregate_three)
    _agent(broker, owner="c", session="c", limits=aggregate_three)
    wider = _limits(max_concurrent=4, readonly_max_concurrent=4, aggregate_max_concurrent=7)
    with pytest.raises(B.CapacityExhaustedError, match="aggregate_limit=3"):
        _agent(broker, owner="d", session="d", limits=wider)


def test_session_can_rearm_with_new_policy_after_drain(broker: Any) -> None:
    original = _agent(broker)
    changed = _limits(max_concurrent=2, readonly_max_concurrent=4, aggregate_max_concurrent=6)
    with pytest.raises(B.PolicyMismatchError):
        _agent(broker, limits=changed)
    assert broker.release(original.lease_id)
    assert _agent(broker, limits=changed).policy_sha256 == changed.policy_sha256()


def test_batch_reservation_is_atomic_and_claim_is_single_use(broker: Any) -> None:
    limits = _limits(max_concurrent=3, readonly_max_concurrent=3, aggregate_max_concurrent=3)
    batch = broker.reserve_batch(
        count=3,
        owner_id="driver",
        session_id="workflow",
        batch_id="batch-1",
        agent_type="*",
        policy_sha256=limits.policy_sha256(),
        session_limit=3,
        aggregate_limit=3,
        mutation="none",
    )
    assert len(batch) == 3
    with pytest.raises(B.CapacityExhaustedError):
        broker.reserve_batch(
            count=2,
            owner_id="other",
            session_id="other",
            batch_id="batch-2",
            agent_type="reviewer",
            policy_sha256=limits.policy_sha256(),
            session_limit=3,
            aggregate_limit=3,
            mutation="none",
        )
    assert len(broker.inspect()["leases"]) == 3

    broker.prepare_batch_call(
        session_id="workflow",
        batch_id="batch-1",
        agent_type="reviewer",
        tool_use_id="workflow-tool-1",
    )
    claimed = broker.claim(
        session_id="workflow",
        agent_type="reviewer",
        agent_id="agent-1",
        resource_ref={"logical_unit_id": "review-1"},
        batch_id="batch-1",
    )
    assert claimed.lease_id == batch[0].lease_id
    assert claimed.fencing_sequence > batch[-1].fencing_sequence
    assert broker.verify_agent("agent-1").lease_id == claimed.lease_id


def test_normal_reservation_requires_two_release_signals(broker: Any) -> None:
    provisional = _agent(broker, tool="tool-1", agent_type="worker")
    claimed = broker.claim(
        session_id="session",
        agent_type="worker",
        agent_id="child-1",
        resource_ref={"logical_unit_id": "unit-1"},
    )
    assert claimed.lease_id == provisional.lease_id
    assert broker.record_parent_completed("tool-1") == ()
    assert broker.verify_agent("child-1").lease_id == claimed.lease_id
    assert broker.record_child_terminal("child-1") is True
    assert broker.classify_token(claimed.resource_ref, claimed.token) == "closed"
    assert broker.record_child_terminal("child-1") is False


def test_unclaimed_failed_parent_releases_reservation(broker: Any) -> None:
    provisional = _agent(broker, tool="tool-failed")
    assert broker.record_parent_completed("tool-failed") == (provisional.lease_id,)
    assert broker.inspect()["leases"] == []


def test_session_renewal_is_atomic_and_release_is_agent_pool_scoped(
    broker: Any, runtime: FakeRuntime, tmp_path: Path
) -> None:
    first = _agent(broker, owner="parent-a", session="team-session", resource="unit-a")
    second = _agent(broker, owner="parent-b", session="team-session", resource="unit-b")
    worktree = broker.acquire_worktree(
        owner_id="outcome-owner",
        session_id="team-session",
        resource_ref=_worktree_resource(tmp_path),
    )

    runtime.advance(30)
    renewed = broker.renew_session("team-session")
    assert {lease.lease_id for lease in renewed} == {first.lease_id, second.lease_id}
    assert all(lease.renewed_monotonic_ns == runtime.monotonic for lease in renewed)

    released = broker.release_session("team-session")
    assert set(released) == {first.lease_id, second.lease_id}
    assert [lease["lease_id"] for lease in broker.inspect()["leases"]] == [worktree.lease_id]
    assert broker.release_session("team-session") == ()


def test_session_renewal_refuses_expired_member_without_partial_write(
    broker: Any, runtime: FakeRuntime
) -> None:
    short = _agent(broker, session="team-session", resource="short", ttl=5)
    long = _agent(broker, session="team-session", resource="long", ttl=60)
    before = broker.registry_path.read_bytes()

    runtime.advance(6)
    with pytest.raises(B.LeaseExpiredError, match=short.lease_id):
        broker.renew_session("team-session")

    assert broker.registry_path.read_bytes() == before
    assert broker.verify(long.resource_ref, long.token).lease_id == long.lease_id


def test_monotonic_expiry_ignores_wall_jump_and_renew_prevents_expiry(
    broker: Any, runtime: FakeRuntime
) -> None:
    lease = _agent(broker, resource="unit", ttl=10)
    runtime.wall += timedelta(days=365)
    assert broker.classify_token(lease.resource_ref, lease.token) == "current"
    runtime.advance(9, wall_seconds=-365 * 24 * 60 * 60)
    renewed = broker.renew(lease.lease_id, token=lease.token)
    runtime.advance(9)
    assert broker.classify_token(renewed.resource_ref, renewed.token) == "current"
    runtime.advance(1)
    assert broker.classify_token(renewed.resource_ref, renewed.token) == "expired"
    with pytest.raises(B.LeaseExpiredError):
        broker.renew(lease.lease_id)


def test_boot_change_invalidates_process_authority(broker: Any, runtime: FakeRuntime) -> None:
    lease = _agent(broker, resource="unit", ttl=999)
    runtime.boot = "boot-b"
    assert broker.classify_token(lease.resource_ref, lease.token) == "expired"


def test_resource_head_persists_and_token_states_are_distinct(
    broker: Any, runtime: FakeRuntime
) -> None:
    first = _agent(broker, resource="unit", ttl=5)
    assert broker.classify_token(first.resource_ref, first.token) == "current"
    runtime.advance(5)
    assert broker.classify_token(first.resource_ref, first.token) == "expired"

    retry = _agent(broker, resource="unit", ttl=30)
    assert retry.fencing_sequence > first.fencing_sequence
    assert broker.classify_token(first.resource_ref, first.token) == "superseded"
    assert broker.classify_token(retry.resource_ref, retry.token) == "current"
    assert broker.release(retry.lease_id, token=retry.token)
    assert broker.classify_token(retry.resource_ref, retry.token) == "closed"
    raw = _raw_registry(broker)
    assert next(iter(raw["resource_fences"].values()))["lease_id"] == retry.lease_id


def test_retry_supersedes_at_full_capacity(broker: Any) -> None:
    limits = _limits(max_concurrent=1, readonly_max_concurrent=1, aggregate_max_concurrent=1)
    first = _agent(broker, limits=limits, resource="same")
    retry = _agent(broker, limits=limits, resource="same")
    assert broker.classify_token(first.resource_ref, first.token) == "superseded"
    assert broker.verify(retry.resource_ref, retry.token).lease_id == retry.lease_id
    assert len(broker.inspect()["leases"]) == 1


def test_recreated_store_has_new_epoch_and_old_token_is_not_current(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    root = tmp_path / "authority"
    first_broker = B.LeaseBroker(root, providers=runtime.providers())
    first = _agent(first_broker, resource="unit")
    first_epoch = first.token.broker_epoch
    first_broker.registry_path.unlink()
    second_broker = B.LeaseBroker(root, providers=runtime.providers())
    second = _agent(second_broker, resource="unit")
    assert second.token.broker_epoch != first_epoch
    assert second_broker.classify_token(first.resource_ref, first.token) == "superseded"


def test_write_fencing_and_missing_worktree_fail_loud(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    root = tmp_path / "authority"
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    broker = B.LeaseBroker(root, providers=runtime.providers())
    limits = _limits()
    provisional = broker.acquire_agent(
        owner_id="owner",
        session_id="session",
        policy_sha256=limits.policy_sha256(),
        session_limit=limits.max_concurrent,
        aggregate_limit=limits.aggregate_max_concurrent,
        mutation="read-write",
        agent_type="worker",
    )
    claimed = broker.claim(
        session_id="session",
        agent_type="worker",
        agent_id="child",
        resource_ref={"logical_unit_id": "unit", "worktree_root": str(worktree)},
    )
    assert claimed.lease_id == provisional.lease_id
    assert broker.assert_write_target("child", worktree / "file.txt") == claimed
    with pytest.raises(B.MissingResourceError, match="outside leased worktree"):
        broker.assert_write_target("child", tmp_path / "elsewhere.txt")
    worktree.rmdir()
    with pytest.raises(B.MissingResourceError, match="worktree is missing"):
        broker.assert_write_target("child", "file.txt")


def test_worktree_sweep_requires_dead_owner_and_preserves_failed_reap(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    broker = B.LeaseBroker(tmp_path / "authority", providers=runtime.providers(), worktree_limit=4)
    runtime.processes[100] = (True, "start-a")
    live_owner = broker.acquire_worktree(
        owner_id="owner-live",
        session_id="session",
        resource_ref=_worktree_resource(tmp_path, 1),
        ttl_seconds=1,
        owner_pid=100,
        owner_process_start="start-a",
    )
    runtime.processes[200] = (False, None)
    dead_owner = broker.acquire_worktree(
        owner_id="owner-dead",
        session_id="session",
        resource_ref=_worktree_resource(tmp_path, 2),
        ttl_seconds=1,
        owner_pid=200,
        owner_process_start="start-b",
    )
    runtime.advance(1)
    failed = broker.sweep(worktree_reaper=lambda _resource: False)
    assert failed.retained[live_owner.lease_id] == "expired-live-owner"
    assert failed.retained[dead_owner.lease_id] == "reap-failed"
    assert len(broker.inspect()["leases"]) == 2

    reaped_resources: list[dict[str, str]] = []

    def _reap(resource: dict[str, str]) -> bool:
        reaped_resources.append(resource)
        return True

    passed = broker.sweep(
        worktree_reaper=_reap,
        terminal_lease_ids=[live_owner.lease_id],
    )
    assert set(passed.reaped_worktree_leases) == {live_owner.lease_id, dead_owner.lease_id}
    assert len(reaped_resources) == 2
    assert broker.inspect()["leases"] == []


def test_expired_agents_release_capacity_on_sweep(broker: Any, runtime: FakeRuntime) -> None:
    lease = _agent(broker, ttl=1)
    runtime.advance(1)
    swept = broker.sweep()
    assert swept.released_agent_leases == (lease.lease_id,)
    assert broker.inspect()["leases"] == []


@pytest.mark.parametrize("target", ["root", "lock", "registry"])
def test_symlinked_authority_nodes_are_rejected(
    tmp_path: Path, runtime: FakeRuntime, target: str
) -> None:
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    root = tmp_path / "authority"
    if target == "root":
        root.symlink_to(real, target_is_directory=True)
    else:
        root.mkdir(mode=0o700)
        destination = tmp_path / f"real-{target}"
        destination.write_text("{}", encoding="utf-8")
        os.chmod(destination, 0o600)
        name = B.LOCK_NAME if target == "lock" else B.REGISTRY_NAME
        (root / name).symlink_to(destination)
    broker = B.LeaseBroker(root, providers=runtime.providers())
    with pytest.raises(B.UnsafeAuthorityError, match="symlink"):
        _agent(broker)


def test_unsafe_modes_and_unknown_schema_fail_closed(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    root = tmp_path / "authority"
    root.mkdir(mode=0o700)
    broker = B.LeaseBroker(root, providers=runtime.providers())
    _agent(broker)
    os.chmod(broker.registry_path, 0o644)
    with pytest.raises(B.UnsafeAuthorityError, match="mode must be 0600"):
        broker.inspect()
    os.chmod(broker.registry_path, 0o600)
    raw = _raw_registry(broker)
    raw["unexpected"] = True
    broker.registry_path.write_text(json.dumps(raw), encoding="utf-8")
    os.chmod(broker.registry_path, 0o600)
    with pytest.raises(B.RegistryCorruptError, match="unknown field"):
        broker.inspect()


def _contention_worker(root: str, start: Any, output: Any, index: int) -> None:
    module = _load(BROKER_PATH, f"fleet_lease_broker_worker_{index}")
    policy = _load(POLICY_PATH, f"fleet_concurrency_policy_worker_{index}")
    broker = module.LeaseBroker(Path(root))
    limits = policy.AdmissionLimits(
        max_concurrent=3, readonly_max_concurrent=3, aggregate_max_concurrent=3
    )
    start.wait(10)
    try:
        lease = broker.acquire_agent(
            owner_id=f"owner-{index}",
            session_id=f"session-{index}",
            policy_sha256=limits.policy_sha256(),
            session_limit=3,
            aggregate_limit=3,
            mutation="read-write",
            ttl_seconds=60,
        )
        output.put(("granted", lease.lease_id))
    except module.CapacityExhaustedError:
        output.put(("refused", None))


def test_fleet_cap_contention_across_processes(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    authority.mkdir(mode=0o700)
    context = multiprocessing.get_context("fork")
    start = context.Event()
    output = context.Queue()
    processes = [
        context.Process(target=_contention_worker, args=(str(authority), start, output, index))
        for index in range(8)
    ]
    for process in processes:
        process.start()
    start.set()
    results = [output.get(timeout=20) for _ in processes]
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0
    assert sum(result[0] == "granted" for result in results) == 3
    assert sum(result[0] == "refused" for result in results) == 5
    broker = B.LeaseBroker(authority)
    assert len(broker.inspect()["leases"]) == 3
