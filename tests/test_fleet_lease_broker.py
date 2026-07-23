"""Contract tests for fleet-core's lease-backed admission authority (#356)."""

from __future__ import annotations

import importlib.util
import json
import multiprocessing
import os
import stat
import subprocess
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
BROKER_PATH = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "lease_broker.py"
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
    isolation: str | None = None,
    agent_id: str | None = None,
    on_conflict: str = "supersede",
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
        isolation=isolation,
        agent_id=agent_id,
        on_conflict=on_conflict,
    )


def _worktree_resource(root: Path, index: int = 1) -> dict[str, str]:
    return {
        "repo_root": str(root),
        "outcome_id": "356",
        "subplot_id": f"sub-{index}",
    }


def _raw_registry(broker: Any) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(broker.registry_path.read_text(encoding="utf-8")))


def test_boot_id_fallback_ignores_wall_jump_and_expires_on_reboot(
    tmp_path: Path,
    runtime: FakeRuntime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read_text = B.Path.read_text
    original_run = B.subprocess.run
    boot = {"value": "darwin-utmpx:1781257565:89752"}

    def deny_linux_boot_id(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == Path("/proc/sys/kernel/random/boot_id"):
            raise OSError("proc boot identity unavailable")
        return cast(str, original_read_text(path, *args, **kwargs))

    def deny_darwin_boot_time(command: list[str], *args: Any, **kwargs: Any) -> Any:
        if command == ["sysctl", "-n", "kern.boottime"]:
            raise OSError("sysctl boot identity unavailable")
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(B.Path, "read_text", deny_linux_boot_id)
    monkeypatch.setattr(B.subprocess, "run", deny_darwin_boot_time)
    monkeypatch.setattr(B.sys, "platform", "darwin")
    monkeypatch.setattr(B, "_darwin_utmpx_boot_id", lambda: boot["value"])
    providers = B.Providers(
        wall_now=lambda: runtime.wall,
        monotonic_ns=lambda: runtime.monotonic,
        boot_id=B._default_boot_id,
        uuid4=runtime.uuid4,
        process_identity=lambda _pid: "stable-process",
        process_exists=lambda _pid: True,
    )
    selected = B.LeaseBroker(tmp_path / "fallback-authority", providers=providers)

    lease = _agent(selected, resource="fallback-boot-id")
    runtime.advance(1, wall_seconds=3_600)
    renewed = selected.renew(lease.lease_id, owner_id=lease.owner_id, token=lease.token)

    assert renewed.boot_id == lease.boot_id
    assert selected.verify(lease.resource_ref, lease.token).lease_id == lease.lease_id

    boot["value"] = "darwin-utmpx:1784265600:1"
    runtime.advance(1)
    with pytest.raises(B.LeaseExpiredError, match="expired"):
        selected.renew(lease.lease_id, owner_id=lease.owner_id, token=lease.token)


@pytest.mark.skipif(sys.platform != "darwin", reason="Darwin utmpx contract")
def test_darwin_utmpx_boot_identity_is_stable_across_processes() -> None:
    program = (
        "import runpy; "
        f"module = runpy.run_path({str(BROKER_PATH)!r}); "
        "print(module['_darwin_utmpx_boot_id']())"
    )
    identities = [
        subprocess.run(
            [sys.executable, "-c", program],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        for _ in range(2)
    ]

    assert identities[0].startswith("darwin-utmpx:")
    assert identities[0] == identities[1]


def test_boot_id_fails_closed_when_every_os_identity_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        B.Path, "read_text", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError())
    )
    monkeypatch.setattr(
        B.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError())
    )
    monkeypatch.setattr(B.sys, "platform", "darwin")
    monkeypatch.setattr(B, "_darwin_utmpx_boot_id", lambda: None)

    with pytest.raises(B.UnsafeAuthorityError, match="boot identity is unavailable"):
        B._default_boot_id()


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
        "archived_resource_fences": {},
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


def test_exact_legacy_v1_registry_shape_migrates_to_empty_session_admissions(
    broker: Any,
) -> None:
    lease = _agent(broker, resource="legacy")
    raw = _raw_registry(broker)
    del raw["session_admissions"]
    broker.registry_path.write_text(json.dumps(raw), encoding="utf-8")
    os.chmod(broker.registry_path, 0o600)

    assert broker.inspect()["leases"][0]["lease_id"] == lease.lease_id
    assert broker.release(lease.lease_id, token=lease.token) is True
    assert _raw_registry(broker)["session_admissions"] == {}


def test_exact_legacy_settlement_close_remains_readable_but_not_current_proof(
    broker: Any,
) -> None:
    lease = _agent(broker, resource="legacy-close")
    settlement = broker.prepare_agent_settlement(
        lease.lease_id,
        owner_id=lease.owner_id,
        token=lease.token,
        producer="saga",
        run_id="legacy-run",
        expected_output_sha256="b" * 64,
        protected_write_intent_sha256="c" * 64,
    )
    current_close = broker.commit_agent_settlement(
        settlement.settlement_id,
        owner_id=lease.owner_id,
        token=lease.token,
        write=lambda _lease: ["legacy-evidence"],
    )
    legacy_close = {
        key: value
        for key, value in current_close.items()
        if key
        not in {
            "settlement_id",
            "session_id",
            "policy_sha256",
            "protected_write_intent_sha256",
            "settlement_sha256",
            "receipt_sha256",
            "sha256",
        }
    }
    legacy_close["receipt_sha256"] = B._record_sha256(legacy_close)
    legacy_close["sha256"] = B._record_sha256(legacy_close)

    with pytest.raises(B.RegistryCorruptError, match="missing field"):
        B.validate_settlement_close(legacy_close)

    raw = _raw_registry(broker)
    digest = B.resource_sha256(lease.resource_ref)
    raw["resource_fences"][digest]["close_receipt"] = legacy_close
    broker.registry_path.write_text(json.dumps(raw), encoding="utf-8")
    os.chmod(broker.registry_path, 0o600)

    assert broker.classify_token(lease.resource_ref, lease.token) == "closed"
    assert broker.inspect()["resource_fences"][digest]["close_receipt"] == legacy_close
    with pytest.raises(B.LeaseClosedError, match="released"):
        broker.verify(lease.resource_ref, lease.token)


def test_session_and_minimum_live_aggregate_limits(broker: Any) -> None:
    session_two = _limits(max_concurrent=2, readonly_max_concurrent=4, aggregate_max_concurrent=5)
    first = _agent(broker, session="same", limits=session_two)
    second = _agent(broker, session="same", limits=session_two)
    with pytest.raises(B.CapacityExhaustedError) as captured:
        _agent(broker, session="same", limits=session_two)
    assert captured.value.earliest_expiry is not None

    aggregate_three = _limits(
        max_concurrent=3, readonly_max_concurrent=3, aggregate_max_concurrent=3
    )
    other = B.LeaseBroker(broker.root, providers=broker.providers)
    with pytest.raises(B.PolicyMismatchError):
        _agent(other, session="same", limits=aggregate_three)

    assert broker.release(first.lease_id, token=first.token)
    assert broker.release(second.lease_id, token=second.token)
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
    assert broker.release(original.lease_id, token=original.token)
    assert _agent(broker, limits=changed).policy_sha256 == changed.policy_sha256()


def test_session_admission_is_exact_live_snapshot_and_compact(broker: Any) -> None:
    limits = _limits(max_concurrent=2, readonly_max_concurrent=2, aggregate_max_concurrent=3)
    configured = broker.configure_session_admission(
        "session",
        policy_sha256=limits.policy_sha256(),
        session_limit=2,
        aggregate_limit=3,
        mutation="read-write",
    )
    assert broker.get_session_admission("session") == configured
    _agent(broker, limits=limits)
    for kwargs in (
        {
            "policy_sha256": "0" * 64,
            "session_limit": 2,
            "aggregate_limit": 3,
            "mutation": "read-write",
        },
        {
            "policy_sha256": limits.policy_sha256(),
            "session_limit": 1,
            "aggregate_limit": 3,
            "mutation": "read-write",
        },
        {
            "policy_sha256": limits.policy_sha256(),
            "session_limit": 2,
            "aggregate_limit": 2,
            "mutation": "read-write",
        },
        {
            "policy_sha256": limits.policy_sha256(),
            "session_limit": 2,
            "aggregate_limit": 3,
            "mutation": "none",
        },
    ):
        with pytest.raises(B.PolicyMismatchError):
            broker.configure_session_admission("session", **kwargs)
    with pytest.raises(B.PolicyMismatchError):
        _agent(
            broker,
            limits=_limits(max_concurrent=1, readonly_max_concurrent=1, aggregate_max_concurrent=3),
        )
    with pytest.raises(B.LeaseOwnershipError):
        broker.clear_session_admission("session")
    broker.release_session("session")
    assert broker.get_session_admission("session") is None


def test_orphan_session_admissions_expire_remain_visible_and_recover_capacity(
    broker: Any, runtime: FakeRuntime
) -> None:
    for index in range(B._MAX_SESSION_ADMISSIONS):
        broker.configure_session_admission(
            f"session-{index}",
            policy_sha256="a" * 64,
            session_limit=1,
            aggregate_limit=1,
            mutation="none",
        )

    inspected = broker.inspect()["session_admissions"]
    assert len(inspected) == B._MAX_SESSION_ADMISSIONS
    assert {item["derived_state"] for item in inspected.values()} == {"armed"}
    with pytest.raises(B.CapacityExhaustedError, match="registry is full"):
        broker.configure_session_admission(
            "overflow",
            policy_sha256="a" * 64,
            session_limit=1,
            aggregate_limit=1,
            mutation="none",
        )

    runtime.advance(B.DEFAULT_TTL_SECONDS)
    broker.configure_session_admission(
        "recovered",
        policy_sha256="a" * 64,
        session_limit=1,
        aggregate_limit=1,
        mutation="none",
    )
    assert set(broker.inspect()["session_admissions"]) == {"recovered"}

    runtime.advance(B.DEFAULT_TTL_SECONDS)
    broker.sweep()
    assert broker.inspect()["session_admissions"] == {}


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
    assert broker.record_parent_completed("session", "tool-1") == ()
    assert broker.verify_agent("child-1").lease_id == claimed.lease_id
    assert broker.record_child_terminal("child-1") is True
    assert broker.classify_token(claimed.resource_ref, claimed.token) == "expired"
    assert broker.record_child_terminal("child-1") is False


def _arm_admission(broker: Any, session: str = "session", limits: Any | None = None) -> Any:
    effective = _limits() if limits is None else limits
    broker.configure_session_admission(
        session,
        policy_sha256=effective.policy_sha256(),
        session_limit=effective.max_concurrent,
        aggregate_limit=effective.aggregate_max_concurrent,
        mutation="read-write",
    )
    return effective


def test_unclaimed_failed_parent_releases_reservation(broker: Any) -> None:
    # R3: a genuine spawn failure (adapter maps PostToolUseFailure -> spawn_failed=True) keeps
    # today's eager removal of the unclaimed reservation and pops the now-empty session admission.
    limits = _arm_admission(broker)
    provisional = _agent(broker, limits=limits, tool="tool-failed")
    assert "session" in broker.inspect()["session_admissions"]
    assert broker.record_parent_completed("session", "tool-failed", spawn_failed=True) == (
        provisional.lease_id,
    )
    assert broker.inspect()["leases"] == []
    assert "session" not in broker.inspect()["session_admissions"]


def test_parent_completion_is_scoped_to_its_session(broker: Any) -> None:
    # Scoping still holds under the new semantics: a spawn-failure signal removes only the
    # matching session's reservation and leaves the other session's slot untouched.
    first = _agent(broker, owner="one", session="one", tool="shared")
    second = _agent(broker, owner="two", session="two", tool="shared")
    assert broker.record_parent_completed("one", "shared", spawn_failed=True) == (first.lease_id,)
    assert [item["lease_id"] for item in broker.inspect()["leases"]] == [second.lease_id]


def test_unclaimed_parent_completed_stamps_and_survives(broker: Any) -> None:
    """R1/KTD1: an async parent-completed signal that arrives before SubagentStart claims the
    reservation stamps parent_completed_at and keeps the slot claimable; the session admission
    survives and no lease id is returned."""
    limits = _arm_admission(broker)
    provisional = _agent(broker, limits=limits, tool="tool-async")
    assert "session" in broker.inspect()["session_admissions"]
    assert broker.record_parent_completed("session", "tool-async") == ()
    leases = broker.inspect()["leases"]
    assert [item["lease_id"] for item in leases] == [provisional.lease_id]
    assert leases[0]["agent_id"] is None
    assert leases[0]["parent_completed_at"] is not None
    assert broker.inspect()["session_admissions"]["session"]["derived_state"] == "live"


def test_async_ordering_stamped_reservation_claims_then_releases(broker: Any) -> None:
    """R2: reserve -> parent-completed (stamped, survives) -> claim (stamp preserved by replace's
    untouched parent_completed_at) -> child-terminal releases the foreground lease via the
    dual signal already recorded."""
    provisional = _agent(broker, tool="tool-async2")
    assert broker.record_parent_completed("session", "tool-async2") == ()
    claimed = broker.claim(
        session_id="session",
        agent_type="worker",
        agent_id="async-child",
        resource_ref={"logical_unit_id": "async-unit"},
    )
    assert claimed.lease_id == provisional.lease_id
    assert claimed.parent_completed_at is not None
    assert broker.record_child_terminal("async-child") is True
    assert broker.inspect()["leases"] == []


def test_stamped_batch_slot_survives_parent_completed_then_claim_recycles(broker: Any) -> None:
    """R2/KTD4: a stamped workflow batch slot receiving parent-completed before its child claims
    survives (stamped, unclaimed); the child then claims it, and child-terminal recycles the slot
    through the dual-signal contract."""
    _workflow_batch(broker, count=1)
    stamped = broker.prepare_batch_call(
        session_id="workflow", batch_id="wf-batch", agent_type="worker", tool_use_id="tool-b"
    )
    assert broker.record_parent_completed("workflow", "tool-b") == ()
    surviving = broker.inspect()["leases"]
    assert [item["lease_id"] for item in surviving] == [stamped.lease_id]
    assert surviving[0]["agent_id"] is None
    assert surviving[0]["parent_completed_at"] is not None
    claimed = broker.claim(
        session_id="workflow", agent_type="worker", agent_id="batch-child", batch_id="wf-batch"
    )
    assert claimed.lease_id == stamped.lease_id
    assert claimed.parent_completed_at is not None
    assert broker.record_child_terminal("batch-child") is True
    recycled = broker.inspect()["leases"][0]
    assert recycled["agent_id"] is None
    assert recycled["tool_use_id"] is None
    assert recycled["parent_completed_at"] is None


def test_expired_stamped_unclaimed_reservation_is_not_live(
    broker: Any, runtime: FakeRuntime
) -> None:
    """R6: an abandoned reservation (parent-completed stamped, child never claims) stops counting as
    a live agent once its claim TTL lapses, and a fresh acquire_agent is not blocked by the stale
    slot."""
    limits = _arm_admission(broker)
    _agent(broker, limits=limits, tool="tool-linger", ttl=B.DEFAULT_CLAIM_TTL_SECONDS)
    assert broker.record_parent_completed("session", "tool-linger") == ()
    runtime.advance(B.DEFAULT_CLAIM_TTL_SECONDS + 1)
    stale = broker.inspect()["leases"][0]
    assert stale["parent_completed_at"] is not None
    assert stale["derived_state"] == "expired"
    assert broker.inspect()["session_admissions"]["session"]["derived_state"] != "live"
    fresh = _agent(broker, tool="tool-fresh", ttl=B.DEFAULT_CLAIM_TTL_SECONDS)
    fresh_state = {item["lease_id"]: item["derived_state"] for item in broker.inspect()["leases"]}
    assert fresh_state[fresh.lease_id] == "live"


def test_settle_batch_releases_abandoned_stamped_slot(broker: Any) -> None:
    """R6/KTD4: settle_batch releases an unclaimed slot whose parent call already returned
    (stamped, no child) so the registry drains to zero leases at batch teardown."""
    _workflow_batch(broker, count=1)
    broker.prepare_batch_call(
        session_id="workflow", batch_id="wf-batch", agent_type="worker", tool_use_id="abandon-tool"
    )
    assert broker.record_parent_completed("workflow", "abandon-tool") == ()
    assert len(broker.settle_batch("wf-batch", owner_id="driver", session_id="workflow")) == 1
    assert broker.inspect()["leases"] == []


def test_settle_batch_keeps_mid_run_stamped_slot_without_parent_signal(broker: Any) -> None:
    """R6/KTD4: a mid-run stamped slot still awaiting its child (no parent-completed signal) is not
    released at settlement -- wave semantics unchanged."""
    _workflow_batch(broker, count=1)
    stamped = broker.prepare_batch_call(
        session_id="workflow", batch_id="wf-batch", agent_type="worker", tool_use_id="live-tool"
    )
    assert broker.settle_batch("wf-batch", owner_id="driver", session_id="workflow") == ()
    assert [item["lease_id"] for item in broker.inspect()["leases"]] == [stamped.lease_id]


def test_batch_settlement_and_terminal_session_release_are_atomic(broker: Any) -> None:
    limits = _limits(max_concurrent=3, readonly_max_concurrent=3, aggregate_max_concurrent=3)
    batch = broker.reserve_batch(
        count=2,
        owner_id="driver",
        session_id="workflow",
        batch_id="batch",
        agent_type="*",
        policy_sha256=limits.policy_sha256(),
        session_limit=3,
        aggregate_limit=3,
        mutation="none",
    )
    broker.prepare_batch_call(
        session_id="workflow", batch_id="batch", agent_type="worker", tool_use_id="tool"
    )
    claimed = broker.claim(
        session_id="workflow",
        batch_id="batch",
        agent_type="worker",
        agent_id="child",
        resource_ref={"logical_unit_id": "unit"},
    )
    assert broker.settle_batch("batch", owner_id="driver", session_id="workflow") == (
        batch[1].lease_id,
    )
    assert broker.inspect()["leases"]
    assert broker.record_parent_completed("workflow", "tool") == ()
    assert broker.record_child_terminal("child")
    assert broker.settle_batch("batch", owner_id="driver", session_id="workflow") == (
        claimed.lease_id,
    )

    _agent(broker, owner="root", session="terminal", tool="terminal-tool")
    active = broker.claim(
        session_id="terminal",
        agent_type="worker",
        agent_id="terminal-child",
        resource_ref={"logical_unit_id": "terminal-unit"},
    )
    with pytest.raises(B.LeaseOwnershipError):
        broker.release_session_if_terminal("terminal", terminal_agent_ids=[])
    assert broker.release_session_if_terminal(
        "terminal", terminal_agent_ids=["terminal-child"]
    ) == (active.lease_id,)

    _agent(broker, owner="root", session="persisted", tool="persisted-tool")
    persisted = broker.claim(
        session_id="persisted",
        agent_type="worker",
        agent_id="persisted-child",
        resource_ref={"logical_unit_id": "persisted-unit"},
    )
    assert broker.record_child_terminal("persisted-child")
    assert broker.release_session_if_terminal("persisted", terminal_agent_ids=[]) == (
        persisted.lease_id,
    )

    _agent(broker, owner="owner-release", session="owner-release", tool="owner-tool")
    owner_bound = broker.claim(
        session_id="owner-release",
        agent_type="worker",
        agent_id="owner-child",
        resource_ref={"logical_unit_id": "owner-unit"},
    )
    with pytest.raises(B.LeaseOwnershipError, match="non-terminal"):
        broker.release_owner("owner-release", session_id="owner-release")
    assert broker.record_child_terminal("owner-child")
    assert broker.release_owner("owner-release", session_id="owner-release") == (
        owner_bound.lease_id,
    )

    unbound = _agent(broker, owner="direct-owner", session="direct-session", resource="direct")
    with pytest.raises(B.LeaseOwnershipError, match="non-terminal"):
        broker.release_owner("direct-owner", session_id="direct-session")
    assert broker.release(unbound.lease_id, token=unbound.token)


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
        broker.renew(lease.lease_id, token=lease.token)


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
    assert broker.classify_token(retry.resource_ref, retry.token) == "expired"
    raw = _raw_registry(broker)
    assert next(iter(raw["resource_fences"].values()))["lease_id"] == retry.lease_id


def test_closed_resource_heads_are_archived_without_losing_exact_state(
    broker: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(B, "_MAX_CLOSED_FENCES", 4)
    issued = []
    for index in range(B._MAX_CLOSED_FENCES + 2):
        lease = _agent(broker, resource=f"unit-{index}")
        issued.append(lease)
        assert broker.release(lease.lease_id, token=lease.token)
    raw = _raw_registry(broker)
    assert len(raw["resource_fences"]) == B._MAX_CLOSED_FENCES
    assert len(list(broker.closed_fences_dir.glob("*.json"))) == 2
    assert broker.classify_token(issued[0].resource_ref, issued[0].token) == "expired"
    assert broker.classify_token(issued[-1].resource_ref, issued[-1].token) == "expired"
    archived_projection = broker.inspect()["archived_resource_fences"]
    assert len(archived_projection) == 2
    assert archived_projection[B.resource_sha256(issued[0].resource_ref)]["close_receipt"] is None

    worktrees = []
    for index in range(B._MAX_CLOSED_FENCES + 2):
        lease = broker.acquire_worktree(
            owner_id="worktree",
            session_id="worktree",
            resource_ref=_worktree_resource(tmp_path, index),
        )
        worktrees.append(lease)
        assert broker.release(lease.lease_id, token=lease.token)
    raw = _raw_registry(broker)
    assert len(raw["resource_fences"]) == B._MAX_CLOSED_FENCES
    assert (
        broker.classify_token(worktrees[0].resource_ref, worktrees[0].token, pool="worktree")
        == "expired"
    )
    assert (
        broker.classify_token(worktrees[-1].resource_ref, worktrees[-1].token, pool="worktree")
        == "expired"
    )
    archived = broker.closed_fences_dir / f"{B.resource_sha256(issued[0].resource_ref)}.json"
    assert archived.is_file()
    archived.chmod(0o644)
    with pytest.raises(B.UnsafeAuthorityError, match="closed fence"):
        broker.classify_token(issued[0].resource_ref, issued[0].token)


def test_retry_supersedes_at_full_capacity(broker: Any) -> None:
    limits = _limits(max_concurrent=1, readonly_max_concurrent=1, aggregate_max_concurrent=1)
    first = _agent(broker, limits=limits, resource="same")
    retry = _agent(broker, limits=limits, resource="same")
    assert broker.classify_token(first.resource_ref, first.token) == "superseded"
    assert broker.verify(retry.resource_ref, retry.token).lease_id == retry.lease_id
    assert len(broker.inspect()["leases"]) == 1


def _refuse_acquire(
    broker: Any,
    *,
    owner: str,
    resource: str,
    limits: Any | None = None,
    ttl: int = 300,
    owner_pid: int | None = None,
    owner_process_start: str | None = None,
) -> Any:
    effective = _limits() if limits is None else limits
    return broker.acquire_agent(
        owner_id=owner,
        session_id="session",
        policy_sha256=effective.policy_sha256(),
        session_limit=effective.max_concurrent,
        aggregate_limit=effective.aggregate_max_concurrent,
        mutation="none",
        ttl_seconds=ttl,
        resource_ref={"logical_unit_id": resource},
        agent_type="worker",
        owner_pid=owner_pid,
        owner_process_start=owner_process_start,
        on_conflict="refuse",
    )


def test_refuse_mode_rejects_live_prior_and_leaves_registry_untouched(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    # Two brokers over one state dir model the cross-runtime dispatch seam (#627 R1/R2). A holds a
    # live lease on the shared digest; B's refuse-mode acquire must fail closed without mutating
    # A's authority — no supersede, no registry byte change.
    root = tmp_path / "authority"
    broker_a = B.LeaseBroker(root, providers=runtime.providers())
    broker_b = B.LeaseBroker(root, providers=runtime.providers())
    held = broker_a.acquire_agent(
        owner_id="runtime-a",
        session_id="session",
        policy_sha256=_limits().policy_sha256(),
        session_limit=_limits().max_concurrent,
        aggregate_limit=_limits().aggregate_max_concurrent,
        mutation="none",
        resource_ref={"logical_unit_id": "shared-leaf"},
        agent_type="worker",
        on_conflict="refuse",
    )
    before = broker_a.registry_path.read_bytes()

    with pytest.raises(B.LeaseConflictError, match="runtime-a") as exc:
        _refuse_acquire(broker_b, owner="runtime-b", resource="shared-leaf")

    assert isinstance(exc.value, B.LeaseOwnershipError)  # broad handlers still catch it
    assert exc.value.holder_owner_id == "runtime-a"
    assert broker_a.registry_path.read_bytes() == before  # zero-mutation on refusal
    assert broker_a.verify(held.resource_ref, held.token).lease_id == held.lease_id


def test_refuse_mode_reclaims_expired_prior(tmp_path: Path, runtime: FakeRuntime) -> None:
    # An expired prior is not a live conflict — refuse mode reclaims exactly as supersede does (R1).
    root = tmp_path / "authority"
    broker_a = B.LeaseBroker(root, providers=runtime.providers())
    broker_b = B.LeaseBroker(root, providers=runtime.providers())
    _refuse_acquire(broker_a, owner="runtime-a", resource="shared-leaf", ttl=60)
    runtime.advance(120)  # past the prior lease TTL -> _expired is True

    reclaimed = _refuse_acquire(broker_b, owner="runtime-b", resource="shared-leaf")

    assert broker_b.verify(reclaimed.resource_ref, reclaimed.token).lease_id == reclaimed.lease_id
    assert len(broker_b.inspect()["leases"]) == 1


def test_refuse_mode_admits_crash_orphan_without_ttl_wait(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    # A SIGKILL skips the finally-release, so the orphaned lease is still unexpired (no TTL elapsed).
    # #637: refuse mode now probes owner liveness — a provably dead pid admits re-dispatch of the
    # same leaf immediately, matching supersede-mode byte-behavior, instead of self-refusing for the
    # full 300 s TTL.
    root = tmp_path / "authority"
    broker_a = B.LeaseBroker(root, providers=runtime.providers())
    broker_b = B.LeaseBroker(root, providers=runtime.providers())
    runtime.processes[4242] = (True, "start-4242")
    held = _refuse_acquire(broker_a, owner="runtime-a", resource="shared-leaf", owner_pid=4242)
    runtime.processes[4242] = (
        False,
        None,
    )  # holder crashed; pid no longer exists, no time advanced

    reclaimed = _refuse_acquire(broker_b, owner="runtime-b", resource="shared-leaf")

    assert broker_b.verify(reclaimed.resource_ref, reclaimed.token).lease_id == reclaimed.lease_id
    assert len(broker_b.inspect()["leases"]) == 1  # dead prior superseded, not accumulated
    assert broker_b.classify_token(held.resource_ref, held.token) == "superseded"


def test_refuse_mode_refuses_live_owner_with_zero_mutation(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    # A live pid on the prior lease still refuses with zero registry mutation (#627 R1/R2 pin held).
    root = tmp_path / "authority"
    broker_a = B.LeaseBroker(root, providers=runtime.providers())
    broker_b = B.LeaseBroker(root, providers=runtime.providers())
    runtime.processes[4242] = (True, "start-4242")
    held = _refuse_acquire(broker_a, owner="runtime-a", resource="shared-leaf", owner_pid=4242)
    before = broker_a.registry_path.read_bytes()

    with pytest.raises(B.LeaseConflictError, match="runtime-a") as exc:
        _refuse_acquire(broker_b, owner="runtime-b", resource="shared-leaf")

    assert exc.value.holder_owner_id == "runtime-a"
    assert broker_a.registry_path.read_bytes() == before  # zero-mutation on refusal
    assert broker_a.verify(held.resource_ref, held.token).lease_id == held.lease_id


def test_refuse_mode_refuses_unknown_owner_pid_none(tmp_path: Path, runtime: FakeRuntime) -> None:
    # No owner_pid recorded -> _owner_state is "unknown" -> fail-closed refuse (R2). Only proof of
    # death admits; the absence of liveness evidence is never treated as death.
    root = tmp_path / "authority"
    broker_a = B.LeaseBroker(root, providers=runtime.providers())
    broker_b = B.LeaseBroker(root, providers=runtime.providers())
    _refuse_acquire(broker_a, owner="runtime-a", resource="shared-leaf")  # owner_pid=None default
    before = broker_a.registry_path.read_bytes()

    with pytest.raises(B.LeaseConflictError, match="runtime-a"):
        _refuse_acquire(broker_b, owner="runtime-b", resource="shared-leaf")

    assert broker_a.registry_path.read_bytes() == before


def test_refuse_mode_refuses_unreadable_owner_identity(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    # pid still alive but its process-start identity is now unreadable -> "unknown" -> refuse (R2).
    root = tmp_path / "authority"
    broker_a = B.LeaseBroker(root, providers=runtime.providers())
    broker_b = B.LeaseBroker(root, providers=runtime.providers())
    runtime.processes[4242] = (True, "start-4242")
    _refuse_acquire(broker_a, owner="runtime-a", resource="shared-leaf", owner_pid=4242)
    runtime.processes[4242] = (True, None)  # alive, but identity unreadable
    before = broker_a.registry_path.read_bytes()

    with pytest.raises(B.LeaseConflictError, match="runtime-a"):
        _refuse_acquire(broker_b, owner="runtime-b", resource="shared-leaf")

    assert broker_a.registry_path.read_bytes() == before


def test_refuse_mode_refuses_same_owner_when_live(tmp_path: Path, runtime: FakeRuntime) -> None:
    # R3 / #627 KTD1: cross-runtime exclusion is the point — a live holder refuses even when the
    # requester's owner_id matches (owner_id is deterministic per leaf, so this is the common case).
    root = tmp_path / "authority"
    broker_a = B.LeaseBroker(root, providers=runtime.providers())
    broker_b = B.LeaseBroker(root, providers=runtime.providers())
    runtime.processes[4242] = (True, "start-4242")
    _refuse_acquire(broker_a, owner="runtime-a", resource="shared-leaf", owner_pid=4242)

    with pytest.raises(B.LeaseConflictError, match="runtime-a"):
        _refuse_acquire(broker_b, owner="runtime-a", resource="shared-leaf")


def test_refuse_mode_admits_after_reboot_without_ttl_wait(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    # Stale boot-id counts as dead: after a reboot the prior lease's owner cannot be alive, so refuse
    # mode reclaims immediately — no TTL wait — even though the recorded pid still appears to exist.
    root = tmp_path / "authority"
    broker_a = B.LeaseBroker(root, providers=runtime.providers())
    broker_b = B.LeaseBroker(root, providers=runtime.providers())
    runtime.processes[4242] = (True, "start-4242")
    _refuse_acquire(broker_a, owner="runtime-a", resource="shared-leaf", owner_pid=4242)
    runtime.boot = "boot-b"  # reboot; prior lease boot_id is now stale

    reclaimed = _refuse_acquire(broker_b, owner="runtime-b", resource="shared-leaf")

    assert broker_b.verify(reclaimed.resource_ref, reclaimed.token).lease_id == reclaimed.lease_id
    assert len(broker_b.inspect()["leases"]) == 1


def test_acquire_agent_rejects_unknown_on_conflict(broker: Any) -> None:
    with pytest.raises(B.LeaseBrokerError, match="on_conflict"):
        broker.acquire_agent(
            owner_id="owner",
            session_id="session",
            policy_sha256=_limits().policy_sha256(),
            session_limit=_limits().max_concurrent,
            aggregate_limit=_limits().aggregate_max_concurrent,
            mutation="none",
            resource_ref={"logical_unit_id": "x"},
            agent_type="worker",
            on_conflict="explode",  # type: ignore[arg-type]
        )


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


def test_write_fencing_and_missing_worktree_fail_loud(tmp_path: Path, runtime: FakeRuntime) -> None:
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


def test_worktree_acquire_never_steals_and_exact_token_transfer_renews(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    broker = B.LeaseBroker(tmp_path / "authority", providers=runtime.providers())
    resource = _worktree_resource(tmp_path)
    original = broker.acquire_worktree(
        owner_id="first",
        session_id="session",
        resource_ref=resource,
        ttl_seconds=1,
        owner_pid=10,
        owner_process_start="first-start",
    )
    assert (
        broker.acquire_worktree(
            owner_id="first",
            session_id="session",
            resource_ref=resource,
            ttl_seconds=1,
            owner_pid=10,
            owner_process_start="first-start",
        )
        == original
    )
    before = broker.registry_path.read_bytes()
    with pytest.raises(B.LeaseOwnershipError):
        broker.acquire_worktree(
            owner_id="second", session_id="session", resource_ref=resource, owner_pid=20
        )
    assert broker.registry_path.read_bytes() == before
    runtime.advance(1)
    with pytest.raises(B.LeaseExpiredError):
        broker.acquire_worktree(
            owner_id="second", session_id="session", resource_ref=resource, owner_pid=20
        )
    transferred = broker.transfer_worktree(
        original.lease_id,
        token=original.token,
        owner_id="second",
        owner_pid=20,
        owner_process_start="second-start",
    )
    assert transferred.token == original.token
    assert transferred.owner_id == "second"
    assert broker.verify(resource, original.token, pool="worktree").owner_id == "second"


def test_worktree_transfer_cannot_race_a_destructive_sweep(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    broker = B.LeaseBroker(tmp_path / "authority", providers=runtime.providers())
    lease = broker.acquire_worktree(
        owner_id="first",
        session_id="session",
        resource_ref=_worktree_resource(tmp_path),
        ttl_seconds=1,
        owner_pid=10,
        owner_process_start="first-start",
    )
    runtime.advance(1)
    reaper_entered = threading.Event()
    allow_reaper_to_finish = threading.Event()
    transfer_finished = threading.Event()
    sweep_results: list[Any] = []
    transfer_results: list[Any] = []

    def reaper(_resource: dict[str, str]) -> bool:
        reaper_entered.set()
        assert allow_reaper_to_finish.wait(timeout=5)
        return False

    def run_sweep() -> None:
        sweep_results.append(broker.sweep(worktree_reaper=reaper))

    def run_transfer() -> None:
        try:
            transfer_results.append(
                broker.transfer_worktree(
                    lease.lease_id,
                    token=lease.token,
                    owner_id="second",
                    owner_pid=20,
                    owner_process_start="second-start",
                )
            )
        finally:
            transfer_finished.set()

    sweep_thread = threading.Thread(target=run_sweep)
    sweep_thread.start()
    assert reaper_entered.wait(timeout=5)
    transfer_thread = threading.Thread(target=run_transfer)
    transfer_thread.start()
    assert not transfer_finished.wait(timeout=0.1)
    allow_reaper_to_finish.set()
    sweep_thread.join(timeout=5)
    transfer_thread.join(timeout=5)
    assert not sweep_thread.is_alive()
    assert not transfer_thread.is_alive()
    assert sweep_results[0].retained[lease.lease_id] == "reap-failed"
    assert transfer_results[0].owner_id == "second"
    assert broker.inspect()["leases"][0]["owner_id"] == "second"


def test_wrong_owner_token_and_stale_token_refusals_leave_authority_unchanged(
    broker: Any, runtime: FakeRuntime, tmp_path: Path
) -> None:
    first = _agent(broker, owner="first", resource="unit")
    before = broker.registry_path.read_bytes()
    with pytest.raises(B.LeaseOwnershipError):
        broker.release(first.lease_id, owner_id="second", token=first.token)
    with pytest.raises(B.LeaseOwnershipError):
        broker.renew(first.lease_id, token=B.FencingToken(first.token.broker_epoch, 999))
    assert broker.registry_path.read_bytes() == before

    runtime.advance(1)
    replacement = _agent(broker, owner="replacement", resource="unit")
    before = broker.registry_path.read_bytes()
    with pytest.raises(B.LeaseOwnershipError):
        broker.release(replacement.lease_id, token=first.token)
    with pytest.raises(B.LeaseOwnershipError):
        broker.renew(replacement.lease_id, token=first.token)
    assert broker.registry_path.read_bytes() == before

    worktree = broker.acquire_worktree(
        owner_id="worktree", session_id="worktree", resource_ref=_worktree_resource(tmp_path)
    )
    before = broker.registry_path.read_bytes()
    with pytest.raises(B.LeaseSupersededError):
        broker.transfer_worktree(
            worktree.lease_id,
            token=B.FencingToken(worktree.token.broker_epoch, worktree.token.fencing_sequence + 1),
            owner_id="other",
        )
    assert broker.registry_path.read_bytes() == before


def test_parent_validation_and_child_grant_share_one_authority_transaction(broker: Any) -> None:
    limits = _limits(max_concurrent=3, readonly_max_concurrent=3, aggregate_max_concurrent=3)
    parent = broker.acquire_agent(
        owner_id="parent-owner",
        session_id="session",
        policy_sha256=limits.policy_sha256(),
        session_limit=limits.max_concurrent,
        aggregate_limit=limits.aggregate_max_concurrent,
        mutation="read-write",
        resource_ref={"logical_unit_id": "parent"},
        agent_id="parent-agent",
    )
    child = broker.acquire_agent(
        owner_id="child-owner",
        session_id="session",
        policy_sha256=limits.policy_sha256(),
        session_limit=limits.max_concurrent,
        aggregate_limit=limits.aggregate_max_concurrent,
        mutation="read-write",
        resource_ref={"logical_unit_id": "child"},
        parent_agent_id="parent-agent",
    )
    assert child.session_id == parent.session_id

    with pytest.raises(B.LeaseOwnershipError, match="different session"):
        broker.acquire_agent(
            owner_id="other-child",
            session_id="other-session",
            policy_sha256=limits.policy_sha256(),
            session_limit=limits.max_concurrent,
            aggregate_limit=limits.aggregate_max_concurrent,
            mutation="read-write",
            resource_ref={"logical_unit_id": "other-child"},
            parent_agent_id="parent-agent",
        )

    assert broker.release(parent.lease_id, token=parent.token)
    with pytest.raises(B.LeaseNotFoundError, match="current parent lease"):
        broker.acquire_agent(
            owner_id="stale-child",
            session_id="session",
            policy_sha256=limits.policy_sha256(),
            session_limit=limits.max_concurrent,
            aggregate_limit=limits.aggregate_max_concurrent,
            mutation="read-write",
            resource_ref={"logical_unit_id": "stale-child"},
            parent_agent_id="parent-agent",
        )
    assert broker.release(child.lease_id, token=child.token)


def test_legacy_agent_settlement_cannot_bypass_receipt_protocol(broker: Any) -> None:
    lease = _agent(broker, resource="settlement")
    with (
        pytest.raises(B.LeaseBrokerError, match="legacy agent_settlement is disabled"),
        broker.agent_settlement(lease.lease_id, owner_id=lease.owner_id, token=lease.token),
    ):
        raise AssertionError("legacy context body must never execute")
    assert broker.classify_token(lease.resource_ref, lease.token) == "current"


def _recovery_intent(
    settlement: Any,
    *,
    runtime: FakeRuntime,
    expected_phase: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "settlement_recovery_intent.v1",
        "resource_ref": settlement.resource_ref,
        "token": settlement.token.to_dict(),
        "lease_id": settlement.lease_id,
        "generation": B.token_generation(settlement.token),
        "settlement_id": settlement.settlement_id,
        "session_id": settlement.session_id,
        "policy_sha256": settlement.policy_sha256,
        "expected_phase": expected_phase,
        "protected_write_intent_sha256": settlement.protected_write_intent_sha256,
        "recovery_owner_id": "root-adapter",
        "recovery_owner_pid": os.getpid(),
        "recovery_owner_process_start": "root-process",
        "recovery_owner_boot_id": runtime.boot,
        "recovery_owner_effective_uid": os.geteuid(),
    }
    payload["sha256"] = B._record_sha256(payload)
    return payload


def test_recovery_is_unavailable_from_ordinary_broker_instances(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    ordinary = B.LeaseBroker(tmp_path / "authority", providers=runtime.providers())

    assert not hasattr(ordinary, "recover_agent_settlement")
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        B.LeaseBroker(
            tmp_path / "other-authority",
            providers=runtime.providers(),
            recovery_owner_id="child-selected-owner",
        )
    with pytest.raises(B.LeaseOwnershipError, match="root-adapter-owned"):
        B.SettlementRecoveryCoordinator(
            object(),
            ordinary,
            recovery_owner_id="child-selected-owner",
            recovery_handlers={},
            recovery_capability=b"x" * 32,
        )


def test_root_recovery_replay_binds_full_settlement_and_lost_response_converges(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    runtime.processes[os.getpid()] = (True, "root-process")
    runtime.processes[42] = (False, None)
    broker = B.LeaseBroker(tmp_path / "authority", providers=runtime.providers())
    coordinator = B._open_settlement_recovery_coordinator(
        broker,
        recovery_owner_id="root-adapter",
    )
    with pytest.raises(B.LeaseOwnershipError, match="different root recovery capability"):
        B._open_settlement_recovery_coordinator(
            B.LeaseBroker(tmp_path / "authority", providers=runtime.providers()),
            recovery_owner_id="forged-child-adapter",
        )
    lease = _agent(broker, resource="recovery", owner="child", ttl=30)
    raw = _raw_registry(broker)
    raw["leases"][lease.lease_id]["owner_pid"] = 42
    raw["leases"][lease.lease_id]["owner_process_start"] = "dead-child"
    broker.registry_path.write_text(json.dumps(raw), encoding="utf-8")
    os.chmod(broker.registry_path, 0o600)
    settlement = broker.prepare_agent_settlement(
        lease.lease_id,
        token=lease.token,
        owner_id=lease.owner_id,
        producer="agy",
        run_id="run-recovery",
        expected_output_sha256="b" * 64,
        protected_write_intent_sha256="c" * 64,
    )

    def fail_after_write(_lease: Any) -> list[str]:
        raise RuntimeError("lost protected-write response")

    with pytest.raises(RuntimeError, match="lost protected-write response"):
        broker.commit_agent_settlement(
            settlement.settlement_id,
            owner_id=lease.owner_id,
            token=lease.token,
            write=fail_after_write,
        )

    replay_count = 0

    def replay(_lease: Any, retained: Any) -> Any:
        nonlocal replay_count
        replay_count += 1
        assert retained.settlement_sha256 == settlement.settlement_sha256
        return B.SettlementReplayResult(["recovered-output"], "c" * 64, "b" * 64)

    coordinator.register_recovery_handler(B.SettlementRecoveryHandler(settlement, replay))
    intent = _recovery_intent(settlement, runtime=runtime, expected_phase="ambiguous")
    first = coordinator.recover_agent_settlement(intent, action="commit")
    retry = coordinator.recover_agent_settlement(intent, action="commit")

    assert first == retry
    assert replay_count == 1
    assert first is not None
    assert first["settlement_sha256"] == settlement.settlement_sha256
    assert first["protected_write_intent_sha256"] == "c" * 64
    assert first["expected_output_sha256"] == "b" * 64


def test_recovery_rejects_replay_result_with_wrong_output_semantics(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    runtime.processes[os.getpid()] = (True, "root-process")
    runtime.processes[42] = (False, None)
    broker = B.LeaseBroker(tmp_path / "authority", providers=runtime.providers())
    coordinator = B._open_settlement_recovery_coordinator(
        broker,
        recovery_owner_id="root-adapter",
    )
    lease = _agent(broker, resource="wrong-replay", owner="child")
    raw = _raw_registry(broker)
    raw["leases"][lease.lease_id]["owner_pid"] = 42
    raw["leases"][lease.lease_id]["owner_process_start"] = "dead-child"
    broker.registry_path.write_text(json.dumps(raw), encoding="utf-8")
    os.chmod(broker.registry_path, 0o600)
    settlement = broker.prepare_agent_settlement(
        lease.lease_id,
        token=lease.token,
        owner_id=lease.owner_id,
        producer="agy",
        run_id="wrong-replay",
        expected_output_sha256="b" * 64,
        protected_write_intent_sha256="c" * 64,
    )
    coordinator.register_recovery_handler(
        B.SettlementRecoveryHandler(
            settlement,
            lambda _lease, _settlement: B.SettlementReplayResult(["wrong"], "c" * 64, "d" * 64),
        )
    )
    intent = _recovery_intent(settlement, runtime=runtime, expected_phase="prepared")

    with pytest.raises(B.LeaseOwnershipError, match="write/output semantics"):
        coordinator.recover_agent_settlement(intent, action="commit")
    assert next(iter(broker.inspect()["settlements"].values()))["phase"] == "ambiguous"


def test_write_fence_rejects_existing_and_nonexistent_symlink_escape(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    worktree = tmp_path / "worktree"
    outside = tmp_path / "outside"
    worktree.mkdir()
    outside.mkdir()
    broker = B.LeaseBroker(tmp_path / "authority", providers=runtime.providers())
    _agent(broker, tool="tool")
    broker.claim(
        session_id="session",
        agent_type="worker",
        agent_id="child",
        resource_ref={"logical_unit_id": "unit", "worktree_root": str(worktree)},
    )
    (worktree / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(B.MissingResourceError, match="outside leased worktree"):
        broker.assert_write_target("child", worktree / "escape" / "new.txt")


def test_expired_agents_release_capacity_on_sweep(broker: Any, runtime: FakeRuntime) -> None:
    lease = _agent(broker, ttl=1)
    limits = _limits()
    broker.configure_session_admission(
        "session",
        policy_sha256=limits.policy_sha256(),
        session_limit=limits.max_concurrent,
        aggregate_limit=limits.aggregate_max_concurrent,
        mutation="read-write",
    )
    runtime.advance(1)
    swept = broker.sweep()
    assert swept.released_agent_leases == (lease.lease_id,)
    assert broker.inspect()["leases"] == []
    assert broker.get_session_admission("session") is None


def test_swept_receiptless_head_remains_expired_not_closed(
    broker: Any, runtime: FakeRuntime
) -> None:
    lease = _agent(broker, resource="swept-head", ttl=1)
    runtime.advance(1)

    assert broker.sweep().released_agent_leases == (lease.lease_id,)
    assert broker.classify_token(lease.resource_ref, lease.token) == "expired"
    with pytest.raises(B.LeaseExpiredError, match="expired"):
        broker.verify(lease.resource_ref, lease.token)


def test_mismatched_live_head_is_corrupt_not_closed(broker: Any) -> None:
    first = _agent(broker, resource="first-head")
    second = _agent(broker, resource="second-head")
    registry_path = broker.root / B.REGISTRY_NAME
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    digest = B.resource_sha256(first.resource_ref)
    registry["resource_fences"][digest]["lease_id"] = second.lease_id
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    registry_path.chmod(0o600)

    with pytest.raises(B.RegistryCorruptError, match="does not bind"):
        broker.classify_token(first.resource_ref, first.token)


def test_cached_authority_rejects_root_identity_change(
    tmp_path: Path, runtime: FakeRuntime
) -> None:
    root = tmp_path / "authority"
    broker = B.LeaseBroker(root, providers=runtime.providers())
    first = _agent(broker, resource="before-swap")
    retained_root = tmp_path / "retained-authority"
    root.rename(retained_root)
    root.mkdir(mode=0o700)

    with pytest.raises(B.UnsafeAuthorityError, match="root changed identity"):
        _agent(broker, resource="after-swap")

    retained = B.LeaseBroker(retained_root, providers=runtime.providers()).inspect()
    assert {item["lease_id"] for item in retained["leases"]} == {first.lease_id}
    assert not (root / B.REGISTRY_NAME).exists()


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


def test_unsafe_modes_and_unknown_schema_fail_closed(tmp_path: Path, runtime: FakeRuntime) -> None:
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


def _same_session_worker(root: str, start: Any, output: Any, index: int) -> None:
    module = _load(BROKER_PATH, f"fleet_lease_broker_session_worker_{index}")
    policy = _load(POLICY_PATH, f"fleet_concurrency_policy_session_worker_{index}")
    broker = module.LeaseBroker(Path(root))
    limits = policy.AdmissionLimits(
        max_concurrent=2, readonly_max_concurrent=2, aggregate_max_concurrent=7
    )
    start.wait(10)
    try:
        lease = broker.acquire_agent(
            owner_id=f"owner-{index}",
            session_id="shared-session",
            policy_sha256=limits.policy_sha256(),
            session_limit=2,
            aggregate_limit=7,
            mutation="read-write",
            ttl_seconds=60,
        )
        output.put(("granted", lease.lease_id))
    except module.CapacityExhaustedError:
        output.put(("refused", None))


def _batch_contention_worker(root: str, start: Any, output: Any, index: int) -> None:
    module = _load(BROKER_PATH, f"fleet_lease_broker_batch_worker_{index}")
    policy = _load(POLICY_PATH, f"fleet_concurrency_policy_batch_worker_{index}")
    broker = module.LeaseBroker(Path(root))
    limits = policy.AdmissionLimits(
        max_concurrent=3, readonly_max_concurrent=3, aggregate_max_concurrent=3
    )
    start.wait(10)
    try:
        leases = broker.reserve_batch(
            count=2,
            owner_id=f"driver-{index}",
            session_id=f"workflow-{index}",
            batch_id=f"batch-{index}",
            agent_type="*",
            policy_sha256=limits.policy_sha256(),
            session_limit=3,
            aggregate_limit=3,
            mutation="none",
        )
        output.put(("granted", len(leases)))
    except module.CapacityExhaustedError:
        output.put(("refused", 0))


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


def test_same_session_ceiling_is_enforced_across_processes(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    authority.mkdir(mode=0o700)
    context = multiprocessing.get_context("fork")
    start = context.Event()
    output = context.Queue()
    processes = [
        context.Process(target=_same_session_worker, args=(str(authority), start, output, index))
        for index in range(6)
    ]
    for process in processes:
        process.start()
    start.set()
    results = [output.get(timeout=20) for _ in processes]
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0
    assert sum(result[0] == "granted" for result in results) == 2
    assert sum(result[0] == "refused" for result in results) == 4


def test_batch_reservation_contention_is_all_or_nothing_across_processes(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    authority.mkdir(mode=0o700)
    context = multiprocessing.get_context("fork")
    start = context.Event()
    output = context.Queue()
    processes = [
        context.Process(
            target=_batch_contention_worker, args=(str(authority), start, output, index)
        )
        for index in range(2)
    ]
    for process in processes:
        process.start()
    start.set()
    results = [output.get(timeout=20) for _ in processes]
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0
    assert sorted(results) == [("granted", 2), ("refused", 0)]
    assert len(B.LeaseBroker(authority).inspect()["leases"]) == 2


def _workflow_batch(
    broker: Any, *, count: int = 2, batch_id: str = "wf-batch", ttl: int = 30
) -> Any:
    limits = _limits(max_concurrent=4, readonly_max_concurrent=4, aggregate_max_concurrent=4)
    return broker.reserve_batch(
        count=count,
        owner_id="driver",
        session_id="workflow",
        batch_id=batch_id,
        agent_type="*",
        policy_sha256=limits.policy_sha256(),
        session_limit=4,
        aggregate_limit=4,
        mutation="read-write",
        ttl_seconds=ttl,
    )


def test_unstamped_batch_claim_binds_oldest_slot_and_derives_logical_unit(broker: Any) -> None:
    batch = _workflow_batch(broker)
    claimed = broker.claim(
        session_id="workflow",
        agent_type="reviewer",
        agent_id="wf-child-1",
        batch_id="wf-batch",
    )
    assert claimed.lease_id == batch[0].lease_id
    assert claimed.resource_ref["logical_unit_id"] == "workflow:reviewer:wf-child-1"
    replay = broker.claim(
        session_id="workflow",
        agent_type="reviewer",
        agent_id="wf-child-1",
        batch_id="wf-batch",
    )
    assert replay.lease_id == claimed.lease_id


def test_stamped_slot_is_preferred_and_unstamped_claims_activate_the_remainder(
    broker: Any,
) -> None:
    batch = _workflow_batch(broker)
    stamped = broker.prepare_batch_call(
        session_id="workflow",
        batch_id="wf-batch",
        agent_type="reviewer",
        tool_use_id="tool-1",
    )
    first = broker.claim(
        session_id="workflow", agent_type="reviewer", agent_id="child-a", batch_id="wf-batch"
    )
    assert first.lease_id == stamped.lease_id
    assert first.resource_ref["logical_unit_id"] == "tool-1"
    second = broker.claim(
        session_id="workflow", agent_type="reviewer", agent_id="child-b", batch_id="wf-batch"
    )
    assert second.lease_id == batch[1].lease_id
    assert second.resource_ref["logical_unit_id"] == "workflow:reviewer:child-b"
    with pytest.raises(B.LeaseNotFoundError):
        broker.claim(
            session_id="workflow", agent_type="reviewer", agent_id="child-c", batch_id="wf-batch"
        )


def test_non_batch_claim_ordering_ignores_stamp_state(broker: Any) -> None:
    unstamped = _agent(broker, tool=None, agent_type="worker")
    _agent(broker, tool="tool-late", agent_type="worker")
    claimed = broker.claim(
        session_id="session",
        agent_type="worker",
        agent_id="plain-child",
        resource_ref={"logical_unit_id": "unit"},
    )
    assert claimed.lease_id == unstamped.lease_id


def test_unstamped_slot_recycles_on_child_terminal_alone(broker: Any, runtime: FakeRuntime) -> None:
    _workflow_batch(broker, count=1)
    first = broker.claim(
        session_id="workflow", agent_type="worker", agent_id="wave-1", batch_id="wf-batch"
    )
    assert broker.record_child_terminal("wave-1") is True
    snapshot = broker.inspect()["leases"]
    assert len(snapshot) == 1
    assert snapshot[0]["agent_id"] is None
    assert snapshot[0]["tool_use_id"] is None
    second = broker.claim(
        session_id="workflow", agent_type="worker", agent_id="wave-2", batch_id="wf-batch"
    )
    assert second.lease_id == first.lease_id
    assert second.agent_id == "wave-2"
    assert broker.record_child_terminal("wave-2") is True
    runtime.advance(B.DEFAULT_CLAIM_TTL_SECONDS + 1)
    with pytest.raises(B.LeaseNotFoundError):
        broker.claim(
            session_id="workflow", agent_type="worker", agent_id="wave-3", batch_id="wf-batch"
        )


def test_stamped_batch_slot_keeps_dual_signal_release(broker: Any) -> None:
    _workflow_batch(broker, count=1)
    broker.prepare_batch_call(
        session_id="workflow", batch_id="wf-batch", agent_type="worker", tool_use_id="tool-9"
    )
    claimed = broker.claim(
        session_id="workflow", agent_type="worker", agent_id="stamped-child", batch_id="wf-batch"
    )
    assert broker.record_child_terminal("stamped-child") is True
    still = {lease["lease_id"]: lease for lease in broker.inspect()["leases"]}
    assert still[claimed.lease_id]["agent_id"] == "stamped-child"
    broker.record_parent_completed("workflow", "tool-9")
    after = {lease["lease_id"]: lease for lease in broker.inspect()["leases"]}
    assert after[claimed.lease_id]["agent_id"] is None
    assert after[claimed.lease_id]["tool_use_id"] is None


def test_batch_keep_alive_renews_live_siblings_but_never_resurrects(
    broker: Any, runtime: FakeRuntime
) -> None:
    _workflow_batch(broker, count=3, ttl=30)
    runtime.advance(20)
    first = broker.claim(
        session_id="workflow", agent_type="worker", agent_id="child-1", batch_id="wf-batch"
    )
    runtime.advance(20)
    second = broker.claim(
        session_id="workflow", agent_type="worker", agent_id="child-2", batch_id="wf-batch"
    )
    assert second.lease_id != first.lease_id
    runtime.advance(31)
    with pytest.raises(B.LeaseNotFoundError):
        broker.claim(
            session_id="workflow", agent_type="worker", agent_id="child-3", batch_id="wf-batch"
        )
    assert broker.record_child_terminal("child-1") is True
    third = broker.claim(
        session_id="workflow", agent_type="worker", agent_id="child-4", batch_id="wf-batch"
    )
    assert third.lease_id == first.lease_id
    with pytest.raises(B.LeaseNotFoundError):
        broker.claim(
            session_id="workflow", agent_type="worker", agent_id="child-5", batch_id="wf-batch"
        )


def test_mutation_verification_renews_batch_member_and_live_siblings(
    broker: Any, runtime: FakeRuntime
) -> None:
    batch = _workflow_batch(broker, count=2, ttl=30)
    child = broker.claim(
        session_id="workflow", agent_type="worker", agent_id="long-child", batch_id="wf-batch"
    )
    for _ in range(20):
        runtime.advance(25)
        renewed = broker.assert_write_target("long-child")
        assert renewed.lease_id == child.lease_id
    second = broker.claim(
        session_id="workflow", agent_type="worker", agent_id="second-child", batch_id="wf-batch"
    )
    assert second.lease_id in {lease.lease_id for lease in batch}
    assert second.lease_id != child.lease_id


def test_mutation_verification_does_not_renew_non_batch_leases(
    broker: Any, runtime: FakeRuntime
) -> None:
    _agent(broker, tool="tool-nb")
    broker.claim(
        session_id="session",
        agent_type="worker",
        agent_id="nb-child",
        resource_ref={"logical_unit_id": "nb-unit"},
    )
    runtime.advance(200)
    broker.assert_write_target("nb-child")
    runtime.advance(150)
    with pytest.raises(B.LeaseExpiredError):
        broker.assert_write_target("nb-child")


def test_expired_batch_member_is_not_resurrected_by_mutation_path(
    broker: Any, runtime: FakeRuntime
) -> None:
    _workflow_batch(broker, count=1)
    broker.claim(
        session_id="workflow", agent_type="worker", agent_id="stalled", batch_id="wf-batch"
    )
    runtime.advance(B.DEFAULT_TTL_SECONDS + 1)
    with pytest.raises(B.LeaseExpiredError):
        broker.assert_write_target("stalled")


# --- #616 worktree write-fence scoping: fence by declared isolation, not spawn cwd ---


def test_stamped_non_isolated_claim_leaves_write_unfenced(broker: Any, tmp_path: Path) -> None:
    """R1: a PreToolUse-stamped, non-worktree reservation claims with no worktree_root, so a
    verified mutation outside the spawn cwd passes assert_write_target (the fence is removed)."""
    cwd = tmp_path / "spawn-cwd"
    cwd.mkdir()
    reservation = _agent(broker, tool="tool-r1", isolation=None)
    claimed = broker.claim(
        session_id="session",
        agent_type="worker",
        agent_id="child-r1",
        worktree_root=str(cwd),
    )
    assert claimed.lease_id == reservation.lease_id
    assert claimed.isolation is None
    assert claimed.resource_ref == {"logical_unit_id": "tool-r1"}
    outside = tmp_path / "elsewhere" / "file.txt"
    assert broker.assert_write_target("child-r1", outside).lease_id == claimed.lease_id


def test_worktree_isolated_claim_stays_write_fenced(broker: Any, tmp_path: Path) -> None:
    """R2: a reservation declaring isolation='worktree' claims with worktree_root stamped from the
    child cwd; a write outside that root is still refused by the containment check."""
    worktree = tmp_path / "isolated-wt"
    worktree.mkdir()
    reservation = _agent(broker, tool="tool-r2", isolation="worktree")
    claimed = broker.claim(
        session_id="session",
        agent_type="worker",
        agent_id="child-r2",
        worktree_root=str(worktree),
    )
    assert claimed.lease_id == reservation.lease_id
    assert claimed.isolation == "worktree"
    assert claimed.resource_ref == {
        "logical_unit_id": "tool-r2",
        "worktree_root": str(worktree),
    }
    assert (
        broker.assert_write_target("child-r2", worktree / "file.txt").lease_id == claimed.lease_id
    )
    with pytest.raises(B.MissingResourceError, match="outside leased worktree"):
        broker.assert_write_target("child-r2", tmp_path / "elsewhere.txt")


def test_unstamped_batch_slot_claim_stamps_worktree_root_byte_parity(
    broker: Any, tmp_path: Path
) -> None:
    """R3: an attested-but-unstamped batch slot (tool_use_id is None) keeps today's conservative
    cwd fence byte-for-byte — worktree_root stamped from the child cwd."""
    cwd = tmp_path / "wf-cwd"
    cwd.mkdir()
    _workflow_batch(broker, count=1)
    claimed = broker.claim(
        session_id="workflow",
        agent_type="worker",
        agent_id="wf-child",
        batch_id="wf-batch",
        worktree_root=str(cwd),
    )
    assert claimed.isolation is None
    assert claimed.resource_ref == {
        "logical_unit_id": "workflow:worker:wf-child",
        "worktree_root": str(cwd),
    }


def test_prepare_batch_call_records_isolation_and_claim_honors_it(
    broker: Any, tmp_path: Path
) -> None:
    """R4: a direct Agent spawn during a live batch records the declared isolation on the slot and
    claim honors it identically to the non-batch path."""
    worktree = tmp_path / "batch-wt"
    worktree.mkdir()
    _workflow_batch(broker, count=2)

    fenced_slot = broker.prepare_batch_call(
        session_id="workflow",
        batch_id="wf-batch",
        agent_type="worker",
        tool_use_id="tool-fenced",
        isolation="worktree",
    )
    assert fenced_slot.isolation == "worktree"
    fenced = broker.claim(
        session_id="workflow",
        agent_type="worker",
        agent_id="child-fenced",
        batch_id="wf-batch",
        worktree_root=str(worktree),
    )
    assert fenced.resource_ref == {"logical_unit_id": "tool-fenced", "worktree_root": str(worktree)}

    open_slot = broker.prepare_batch_call(
        session_id="workflow",
        batch_id="wf-batch",
        agent_type="worker",
        tool_use_id="tool-open",
        isolation=None,
    )
    assert open_slot.isolation is None
    unfenced = broker.claim(
        session_id="workflow",
        agent_type="worker",
        agent_id="child-open",
        batch_id="wf-batch",
        worktree_root=str(tmp_path / "other-cwd"),
    )
    assert unfenced.resource_ref == {"logical_unit_id": "tool-open"}


def test_registry_without_isolation_key_backfills_to_none(
    broker: Any, tmp_path: Path, runtime: FakeRuntime
) -> None:
    """R5: a 0.19.0-shaped lease dict (no isolation key) loads with isolation=None; a written
    0.20.0 registry serializes the field and re-loads cleanly."""
    lease = _agent(broker, resource="reg-unit", tool="reg-tool")
    raw = _raw_registry(broker)
    record = raw["leases"][lease.lease_id]
    assert "isolation" in record  # a 0.20.0 broker always serializes the field (fresh round-trip)
    del record["isolation"]
    broker.registry_path.write_text(json.dumps(raw), encoding="utf-8")
    os.chmod(broker.registry_path, 0o600)

    loaded = broker.inspect()["leases"][0]
    assert loaded["lease_id"] == lease.lease_id
    assert loaded["isolation"] is None
    # A second broker over the same on-disk state re-reads the pre-#616 shape without error.
    reopened = B.LeaseBroker(tmp_path / "authority", providers=runtime.providers())
    reloaded = reopened.inspect()["leases"][0]
    assert reloaded["lease_id"] == lease.lease_id
    assert reloaded["isolation"] is None


def test_batch_slot_recycle_resets_isolation(broker: Any, tmp_path: Path) -> None:
    """R6: after a stamped, isolated batch child goes terminal the recycled slot resets isolation to
    None, so a workflow child that re-claims it gets row-3 (unstamped) behavior, not the prior
    spawn's declaration."""
    worktree = tmp_path / "recycle-wt"
    worktree.mkdir()
    _workflow_batch(broker, count=1)
    broker.prepare_batch_call(
        session_id="workflow",
        batch_id="wf-batch",
        agent_type="worker",
        tool_use_id="tool-recycle",
        isolation="worktree",
    )
    broker.claim(
        session_id="workflow",
        agent_type="worker",
        agent_id="child-first",
        batch_id="wf-batch",
        worktree_root=str(worktree),
    )
    assert broker.record_parent_completed("workflow", "tool-recycle") == ()
    assert broker.record_child_terminal("child-first") is True

    recycled = broker.inspect()["leases"][0]
    assert recycled["agent_id"] is None
    assert recycled["tool_use_id"] is None
    assert recycled["isolation"] is None

    second_cwd = tmp_path / "second-cwd"
    second_cwd.mkdir()
    reclaimed = broker.claim(
        session_id="workflow",
        agent_type="worker",
        agent_id="child-second",
        batch_id="wf-batch",
        worktree_root=str(second_cwd),
    )
    assert reclaimed.isolation is None
    assert reclaimed.resource_ref == {
        "logical_unit_id": "workflow:worker:child-second",
        "worktree_root": str(second_cwd),
    }


def test_supersede_replaces_isolation_declaration(broker: Any) -> None:
    """A superseding reservation on the same resource digest wins its isolation declaration."""
    generous = _limits(max_concurrent=4, readonly_max_concurrent=4, aggregate_max_concurrent=4)
    first = _agent(broker, limits=generous, resource="shared", agent_id="a1", isolation="worktree")
    assert first.isolation == "worktree"
    second = _agent(
        broker,
        limits=generous,
        resource="shared",
        agent_id="a2",
        isolation=None,
        on_conflict="supersede",
    )
    assert second.isolation is None
    lease_ids = {item["lease_id"] for item in broker.inspect()["leases"]}
    assert first.lease_id not in lease_ids
    assert second.lease_id in lease_ids


def test_invalid_isolation_value_rejected_at_boundary(broker: Any) -> None:
    """Only 'worktree'/None are storable; any other declared value is rejected at the broker
    boundary so no speculative isolation ever reaches the registry."""
    with pytest.raises(B.LeaseBrokerError, match="isolation must be"):
        _agent(broker, tool="tool-bad", isolation="remote")
    _workflow_batch(broker, count=1)
    with pytest.raises(B.LeaseBrokerError, match="isolation must be"):
        broker.prepare_batch_call(
            session_id="workflow",
            batch_id="wf-batch",
            agent_type="worker",
            tool_use_id="tool-bad-batch",
            isolation="remote",
        )


def test_registry_with_invalid_isolation_value_raises_registry_corrupt(broker: Any) -> None:
    """An on-disk isolation value outside 'worktree'/None is registry corruption, not an API
    error: the from_dict read path (corrupt=True) raises RegistryCorruptError."""
    lease = _agent(broker, resource="corrupt-unit", tool="corrupt-tool")
    raw = _raw_registry(broker)
    raw["leases"][lease.lease_id]["isolation"] = "remote"
    broker.registry_path.write_text(json.dumps(raw), encoding="utf-8")
    os.chmod(broker.registry_path, 0o600)
    with pytest.raises(B.RegistryCorruptError, match="isolation must be"):
        broker.inspect()


def test_recycled_slot_re_stamp_honors_new_isolation(broker: Any, tmp_path: Path) -> None:
    """A recycled batch slot re-stamped by a second prepare_batch_call honors the NEW declared
    isolation: an unfenced first wave (isolation None) followed by a worktree-declared second
    wave claims fenced, proving the reuse path re-applies the fresh declaration."""
    first_cwd = tmp_path / "wave1-cwd"
    first_cwd.mkdir()
    _workflow_batch(broker, count=1)
    broker.prepare_batch_call(
        session_id="workflow",
        batch_id="wf-batch",
        agent_type="worker",
        tool_use_id="tool-wave1",
        isolation=None,
    )
    first = broker.claim(
        session_id="workflow",
        agent_type="worker",
        agent_id="child-wave1",
        batch_id="wf-batch",
        worktree_root=str(first_cwd),
    )
    assert first.isolation is None
    assert first.resource_ref == {"logical_unit_id": "tool-wave1"}
    assert broker.record_parent_completed("workflow", "tool-wave1") == ()
    assert broker.record_child_terminal("child-wave1") is True

    second_cwd = tmp_path / "wave2-wt"
    second_cwd.mkdir()
    broker.prepare_batch_call(
        session_id="workflow",
        batch_id="wf-batch",
        agent_type="worker",
        tool_use_id="tool-wave2",
        isolation="worktree",
    )
    second = broker.claim(
        session_id="workflow",
        agent_type="worker",
        agent_id="child-wave2",
        batch_id="wf-batch",
        worktree_root=str(second_cwd),
    )
    assert second.isolation == "worktree"
    assert second.resource_ref == {
        "logical_unit_id": "tool-wave2",
        "worktree_root": str(second_cwd),
    }
