"""Tests for the durable per-sub-outcome worktree lifecycle + the worktree-removed terminal (U7).

Pins R15 (one durable named+owned worktree per sub-outcome, reused across leaves not one-per-leaf;
cap-bounded; reaped on terminal; shared install ref), R32-worktree (a worktree removed out-of-band ->
a defined ``rejected`` terminal), R22 (the removed terminal cascades to its downstream subtree), and
R34 (a transient git failure degrades to present — never falsely terminates a live sub-outcome).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

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


# Load in dependency order so every lazy `import outcome` / sibling import reuses these instances.
SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
ORCH = _load("outcome_orchestrator")
_load("outcome_dispatcher")
_load("outcome_merge")
ENG = _load("outcome")
WT = _load("outcome_worktrees")


def _store(tmp_path: Path) -> Any:
    return STORE.Store(root=tmp_path / "store").ensure()


def _spec(nodes: list[dict[str, Any]]) -> Any:
    return SPEC.OutcomeSpec.from_dict({"outcome_id": "o", "objective": "x", "nodes": nodes})


def _sub(sid: str, **kw: Any) -> dict[str, Any]:
    """A sub-outcome node dict (child_spec_ref set so Node.is_outcome is True)."""
    return {"subplot_id": sid, "title": sid, "kind": "code", "child_spec_ref": f"child-{sid}", **kw}


def _dispatched(store: Any, sid: str) -> None:
    STORE.append_ledger(
        store,
        {
            "phase": "commit",
            "kind": "dispatch",
            "key": f"dispatch:{sid}",
            "subplot_id": sid,
            "leaf_saga_id": f"leaf-{sid}",
        },
    )


class FakeWT:
    """A fake WorktreeOps backed by an in-memory set of live paths (git is simulated)."""

    def __init__(self, *, exists_override: Any = None) -> None:
        self.paths: set[str] = set()
        self.removed: list[str] = []
        self._exists_override = exists_override

    def _add(self, path: str, _branch: str) -> bool:
        self.paths.add(path)
        return True

    def _remove(self, path: str) -> bool:
        self.paths.discard(path)
        self.removed.append(path)
        return True

    def _exists(self, path: str) -> bool:
        if self._exists_override is not None:
            return bool(self._exists_override(path))
        return path in self.paths

    def ops(self) -> Any:
        return WT.WorktreeOps(
            add=self._add,
            remove=self._remove,
            exists=self._exists,
            list_paths=lambda: sorted(self.paths),
        )


@dataclass
class FakeLeaseRuntime:
    wall: datetime = datetime(2026, 7, 16, 12, tzinfo=UTC)
    monotonic: int = 1_000_000_000
    boot: str = "boot-a"
    processes: dict[int, tuple[bool, str | None]] = field(default_factory=dict)

    def providers(self) -> Any:
        authority = WT.fleet_leases.authority
        return authority.Providers(
            wall_now=lambda: self.wall,
            monotonic_ns=lambda: self.monotonic,
            boot_id=lambda: self.boot,
            process_identity=lambda pid: self.processes.get(pid, (False, None))[1],
            process_exists=lambda pid: self.processes.get(pid, (False, None))[0],
        )

    def advance(self, seconds: int) -> None:
        self.monotonic += seconds * 1_000_000_000
        self.wall += timedelta(seconds=seconds)


def _lease_broker(tmp_path: Path, runtime: FakeLeaseRuntime, *, worktree_limit: int = 4) -> Any:
    return WT.fleet_leases.authority.LeaseBroker(
        tmp_path / "authority",
        providers=runtime.providers(),
        worktree_limit=worktree_limit,
    )


# --------------------------------------------------------------------------- names / paths


def test_names_and_paths_are_deterministic_and_namespaced() -> None:
    assert WT.worktree_name("o", "s1") == "saga-outcome-o-s1"
    p = WT.worktree_path(Path("/repo"), "o", "s1")
    assert p == Path("/repo/.saga-worktrees/o/s1")
    # the shared install ref is one path per OUTCOME (reused by every sibling worktree, R15)
    assert WT.shared_install_ref(Path("/repo"), "o") == "/repo/.saga-worktrees/o/_shared-install"


# --------------------------------------------------------------------------- ensure (R15)


def test_plain_leaf_is_not_managed(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": "p", "title": "p", "kind": "code"}])  # no child_spec_ref
    out = WT.ensure_worktree(
        tmp_path, spec, _store(tmp_path), spec.nodes[0], FakeWT().ops(), owner="me"
    )
    assert out.state == "skipped-not-suboutcome"


def test_suboutcome_creates_once_then_reuses(tmp_path: Path) -> None:
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    first = WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    assert first.state == "created"
    second = WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    assert second.state == "reused"  # one durable worktree, reused across the child's leaves (R15)
    assert second.path == first.path


def test_cap_defers_never_overshoots(tmp_path: Path) -> None:
    spec = _spec([_sub("s1"), _sub("s2")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    assert (
        WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me", cap=1).state
        == "created"
    )
    capped = WT.ensure_worktree(tmp_path, spec, store, spec.nodes[1], ops, owner="me", cap=1)
    assert capped.state == "capped"  # past the cap -> defer + page, never an (N+1)th worktree
    assert (
        WT.ensure_worktree(tmp_path, spec, store, spec.nodes[1], ops, owner="me", cap=2).state
        == "created"
    )


def test_siblings_share_one_install_ref_and_are_owner_tagged(tmp_path: Path) -> None:
    spec = _spec([_sub("s1"), _sub("s2")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="alice", cap=4)
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[1], ops, owner="alice", cap=4)
    reg = WT.read_registry(store)
    assert (
        reg["s1"]["shared_install_ref"] == reg["s2"]["shared_install_ref"]
    )  # shared installs (R15)
    assert reg["s1"]["owner"] == reg["s2"]["owner"] == "alice"  # named + owner-tagged
    assert reg["s1"]["branch"] == "saga-outcome-o-s1"


def test_stale_registry_entry_is_dropped_then_recreated(tmp_path: Path) -> None:
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    # simulate the worktree vanishing out-of-band, then a re-ensure: stale entry dropped, recreated
    fw.paths.clear()
    again = WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    assert again.state == "created"  # not wedged on the stale record


def test_stale_worktree_debits_are_read_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    WT.register(
        store,
        "s1",
        {"path": str(WT.worktree_path(tmp_path, "o", "s1")), "branch": "branch-s1"},
    )
    registry_before = WT._registry_path(store).read_bytes()
    debits = WT.stale_worktree_debits(store, FakeWT().ops(), outcome_id="o")
    assert debits == [
        {
            "dispatch_id": "outcome:o:worktrees",
            "unit_id": "s1",
            "attempt": 1,
            "worktree": str(WT.worktree_path(tmp_path, "o", "s1")),
        }
    ]
    assert WT._registry_path(store).read_bytes() == registry_before


def test_stale_worktree_debits_leave_malformed_registry_untouched(tmp_path: Path) -> None:
    store = _store(tmp_path)
    registry = WT._registry_path(store)
    registry.write_text("{broken\n", encoding="utf-8")

    with pytest.raises(WT.WorktreeError, match="without repair"):
        WT.stale_worktree_debits(store, FakeWT().ops(), outcome_id="o")

    assert registry.read_text(encoding="utf-8") == "{broken\n"
    assert list(store.quarantine_dir.iterdir()) == []


def test_provisioning_persists_recovery_authority_before_physical_add(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = FakeLeaseRuntime()
    broker = _lease_broker(tmp_path, runtime)
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()

    def fail_register(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("registry unavailable")

    monkeypatch.setattr(WT, "register", fail_register)
    with pytest.raises(OSError, match="registry unavailable"):
        WT.ensure_worktree(
            tmp_path,
            spec,
            store,
            spec.nodes[0],
            fw.ops(),
            owner="coordinator",
            lease_authority=broker,
        )
    assert fw.paths == set()
    assert broker.inspect()["leases"] == []


def test_uncertain_add_failure_retains_registry_and_lease_for_retry(tmp_path: Path) -> None:
    runtime = FakeLeaseRuntime()
    broker = _lease_broker(tmp_path, runtime)
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    uncertain = WT.WorktreeOps(
        add=lambda _path, _branch: False,
        remove=lambda _path: False,
        exists=lambda _path: True,
        list_paths=list,
    )

    with pytest.raises(WT.WorktreeError, match="registry and lease retained"):
        WT.ensure_worktree(
            tmp_path,
            spec,
            store,
            spec.nodes[0],
            uncertain,
            owner="coordinator",
            lease_authority=broker,
        )
    assert "s1" in WT.read_registry(store)
    assert len(broker.inspect()["leases"]) == 1
    assert WT.reap_worktree(store, "s1", FakeWT().ops(), lease_authority=broker) is True
    assert WT.read_registry(store) == {}
    assert broker.inspect()["leases"] == []


# --------------------------------------------------------------------------- fleet lease ownership (#356)


def _reconcile_leases(
    tmp_path: Path,
    spec: Any,
    store: Any,
    ops: Any,
    broker: Any,
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        WT.reconcile_worktree_leases(
            tmp_path,
            spec,
            store,
            ops,
            broker,
            owner="coordinator",
            store_resolver=lambda _outcome_id, _repo_root: store,
        ),
    )


def test_worktree_lease_is_recorded_and_renewed_at_active_tick(tmp_path: Path) -> None:
    runtime = FakeLeaseRuntime()
    runtime.processes[os.getpid()] = (True, "coordinator-start")
    broker = _lease_broker(tmp_path, runtime)
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    WT.ensure_worktree(
        tmp_path,
        spec,
        store,
        spec.nodes[0],
        ops,
        owner="coordinator",
        lease_authority=broker,
        lease_ttl_seconds=5,
    )
    entry = WT.read_registry(store)["s1"]
    lease_id, token = WT._lease_binding(entry, broker)
    assert entry["repo_root"] == str(tmp_path.resolve())
    assert "root" not in entry["lease"]

    runtime.advance(4)
    result = _reconcile_leases(tmp_path, spec, store, ops, broker)
    assert result["lease_renewed"] == ["s1"]
    runtime.advance(4)
    assert (
        broker.classify_token(
            WT.fleet_leases.worktree_resource(tmp_path, "o", "s1"), token, pool="worktree"
        )
        == "current"
    )
    assert broker.inspect()["leases"][0]["lease_id"] == lease_id


def test_expired_live_owner_is_reported_not_reaped(tmp_path: Path) -> None:
    runtime = FakeLeaseRuntime()
    runtime.processes[os.getpid()] = (True, "coordinator-start")
    broker = _lease_broker(tmp_path, runtime)
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    WT.ensure_worktree(
        tmp_path,
        spec,
        store,
        spec.nodes[0],
        fw.ops(),
        owner="coordinator",
        lease_authority=broker,
        lease_ttl_seconds=1,
    )
    lease_id = WT.read_registry(store)["s1"]["lease"]["lease_id"]
    runtime.advance(1)

    result = _reconcile_leases(tmp_path, spec, store, fw.ops(), broker)
    assert result["lease_retained"][lease_id] == "expired-live-owner"
    assert fw.removed == []
    assert "s1" in WT.read_registry(store)


def test_expired_active_child_transfers_to_the_next_one_shot_coordinator(tmp_path: Path) -> None:
    runtime = FakeLeaseRuntime()
    broker = _lease_broker(tmp_path, runtime)
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    WT.ensure_worktree(
        tmp_path,
        spec,
        store,
        spec.nodes[0],
        fw.ops(),
        owner="coordinator-old",
        lease_authority=broker,
        lease_ttl_seconds=1,
    )
    _dispatched(store, "s1")
    lease_id = WT.read_registry(store)["s1"]["lease"]["lease_id"]
    runtime.advance(1)

    result = WT.reconcile_worktree_leases(
        tmp_path,
        spec,
        store,
        fw.ops(),
        broker,
        owner="coordinator-new",
        store_resolver=lambda _outcome_id, _repo_root: store,
    )
    assert result["lease_transferred"] == ["s1"]
    assert result["lease_reaped"] == []
    assert fw.removed == []
    assert broker.inspect()["leases"][0]["lease_id"] == lease_id
    assert broker.inspect()["leases"][0]["owner_id"] == "coordinator-new"
    assert "s1" in WT.read_registry(store)


@pytest.mark.parametrize("reboot", [False, True])
def test_expired_dead_or_reboot_invalidated_owner_is_reaped(tmp_path: Path, reboot: bool) -> None:
    runtime = FakeLeaseRuntime()
    runtime.processes[os.getpid()] = (True, "coordinator-start")
    broker = _lease_broker(tmp_path, runtime)
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    WT.ensure_worktree(
        tmp_path,
        spec,
        store,
        spec.nodes[0],
        fw.ops(),
        owner="coordinator",
        lease_authority=broker,
        lease_ttl_seconds=1,
    )
    lease_id = WT.read_registry(store)["s1"]["lease"]["lease_id"]
    if reboot:
        runtime.boot = "boot-b"
    else:
        runtime.processes[os.getpid()] = (False, None)
        runtime.advance(1)

    result = _reconcile_leases(tmp_path, spec, store, fw.ops(), broker)
    assert result["lease_reaped"] == [lease_id]
    assert "s1" not in WT.read_registry(store)
    assert broker.inspect()["leases"] == []


def test_fifteen_dead_worktree_leases_are_validated_and_reaped(tmp_path: Path) -> None:
    runtime = FakeLeaseRuntime()
    broker = _lease_broker(tmp_path, runtime, worktree_limit=15)
    spec = _spec([_sub(f"s{index}") for index in range(15)])
    store = _store(tmp_path)
    fw = FakeWT()
    for node in spec.nodes:
        WT.ensure_worktree(
            tmp_path,
            spec,
            store,
            node,
            fw.ops(),
            owner="coordinator",
            cap=15,
            lease_authority=broker,
            lease_ttl_seconds=1,
        )
    runtime.advance(1)

    result = _reconcile_leases(tmp_path, spec, store, fw.ops(), broker)
    assert len(result["lease_reaped"]) == 15
    assert len(fw.removed) == 15
    assert WT.read_registry(store) == {}
    assert broker.inspect()["leases"] == []


@pytest.mark.parametrize("corruption", ["escape", "lease-id"])
def test_sweep_refuses_escaping_path_or_mismatched_registry_binding(
    tmp_path: Path, corruption: str
) -> None:
    runtime = FakeLeaseRuntime()
    broker = _lease_broker(tmp_path, runtime)
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    WT.ensure_worktree(
        tmp_path,
        spec,
        store,
        spec.nodes[0],
        fw.ops(),
        owner="coordinator",
        lease_authority=broker,
        lease_ttl_seconds=1,
    )
    entry = WT.read_registry(store)["s1"]
    lease_id = entry["lease"]["lease_id"]
    if corruption == "escape":
        entry["path"] = str(tmp_path.parent / "escaped")
    else:
        entry["lease"]["lease_id"] = "different-lease"
    WT.register(store, "s1", entry)
    runtime.advance(1)

    result = _reconcile_leases(tmp_path, spec, store, fw.ops(), broker)
    assert result["lease_retained"][lease_id] == "reap-failed"
    assert broker.inspect()["leases"][0]["lease_id"] == lease_id
    assert "s1" in WT.read_registry(store)


def test_reap_failure_retains_authority_then_retries(tmp_path: Path) -> None:
    runtime = FakeLeaseRuntime()
    broker = _lease_broker(tmp_path, runtime)
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    path = str(WT.worktree_path(tmp_path, "o", "s1"))
    paths = {path}
    fail = True

    def remove(target: str) -> bool:
        if fail:
            return False
        paths.discard(target)
        return True

    def add(target: str, _branch: str) -> bool:
        paths.add(target)
        return True

    ops = WT.WorktreeOps(
        add=add,
        remove=remove,
        exists=lambda target: target in paths,
        list_paths=lambda: sorted(paths),
    )
    WT.ensure_worktree(
        tmp_path,
        spec,
        store,
        spec.nodes[0],
        ops,
        owner="coordinator",
        lease_authority=broker,
        lease_ttl_seconds=1,
    )
    lease_id = WT.read_registry(store)["s1"]["lease"]["lease_id"]
    runtime.advance(1)
    first = _reconcile_leases(tmp_path, spec, store, ops, broker)
    assert first["lease_retained"][lease_id] == "reap-failed"
    fail = False
    second = _reconcile_leases(tmp_path, spec, store, ops, broker)
    assert second["lease_reaped"] == [lease_id]
    assert WT.read_registry(store) == {}


def test_registry_reap_exception_keeps_broker_authority_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = FakeLeaseRuntime()
    broker = _lease_broker(tmp_path, runtime)
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    WT.ensure_worktree(
        tmp_path,
        spec,
        store,
        spec.nodes[0],
        fw.ops(),
        owner="coordinator",
        lease_authority=broker,
        lease_ttl_seconds=1,
    )
    lease_id = WT.read_registry(store)["s1"]["lease"]["lease_id"]
    runtime.advance(1)
    original = WT.deregister

    def fail_deregister(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("registry unavailable")

    monkeypatch.setattr(WT, "deregister", fail_deregister)

    first = _reconcile_leases(tmp_path, spec, store, fw.ops(), broker)
    assert first["lease_retained"][lease_id] == "reap-failed"
    assert broker.inspect()["leases"][0]["lease_id"] == lease_id
    assert "s1" in WT.read_registry(store)

    monkeypatch.setattr(WT, "deregister", original)
    second = _reconcile_leases(tmp_path, spec, store, fw.ops(), broker)
    assert second["lease_reaped"] == [lease_id]
    assert broker.inspect()["leases"] == []


def test_broker_preserves_existing_cap_four(tmp_path: Path) -> None:
    runtime = FakeLeaseRuntime()
    broker = _lease_broker(tmp_path, runtime)
    spec = _spec([_sub(f"s{index}") for index in range(5)])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    for node in spec.nodes[:4]:
        WT.ensure_worktree(
            tmp_path,
            spec,
            store,
            node,
            ops,
            owner="coordinator",
            cap=10,
            lease_authority=broker,
        )
    with pytest.raises(WT.WorktreeError, match="worktree lease admission refused"):
        WT.ensure_worktree(
            tmp_path,
            spec,
            store,
            spec.nodes[4],
            ops,
            owner="coordinator",
            cap=10,
            lease_authority=broker,
        )
    assert len(WT.read_registry(store)) == 4


def test_legacy_live_registry_entry_is_adopted_under_a_lease(tmp_path: Path) -> None:
    runtime = FakeLeaseRuntime()
    runtime.processes[os.getpid()] = (True, "coordinator-start")
    broker = _lease_broker(tmp_path, runtime)
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="legacy")

    result = _reconcile_leases(tmp_path, spec, store, ops, broker)
    assert result["lease_adopted"] == ["s1"]
    assert "lease" in WT.read_registry(store)["s1"]
    assert len(broker.inspect()["leases"]) == 1


def test_terminal_reap_releases_exact_worktree_lease(tmp_path: Path) -> None:
    runtime = FakeLeaseRuntime()
    broker = _lease_broker(tmp_path, runtime)
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    WT.ensure_worktree(
        tmp_path,
        spec,
        store,
        spec.nodes[0],
        fw.ops(),
        owner="coordinator",
        lease_authority=broker,
    )
    _completed(store, "s1", "done")

    result = WT.harvest_worktrees(spec, store, fw.ops(), lease_authority=broker)
    assert result["reaped"] == ["s1"]
    assert broker.inspect()["leases"] == []
    assert WT.read_registry(store) == {}


def test_sweep_refuses_store_resolution_mismatch(tmp_path: Path) -> None:
    runtime = FakeLeaseRuntime()
    broker = _lease_broker(tmp_path, runtime)
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    WT.ensure_worktree(
        tmp_path,
        spec,
        store,
        spec.nodes[0],
        fw.ops(),
        owner="coordinator",
        lease_authority=broker,
        lease_ttl_seconds=1,
    )
    lease_id = WT.read_registry(store)["s1"]["lease"]["lease_id"]
    runtime.advance(1)
    wrong_store = STORE.Store(root=tmp_path / "wrong-store").ensure()

    result = WT.reconcile_worktree_leases(
        tmp_path,
        spec,
        store,
        fw.ops(),
        broker,
        owner="coordinator",
        store_resolver=lambda _outcome_id, _repo_root: wrong_store,
    )
    assert result["lease_retained"][lease_id] == "reap-failed"
    assert "s1" in WT.read_registry(store)


# --------------------------------------------------------------------------- reap (R15)


def test_reap_removes_and_deregisters_idempotently(tmp_path: Path) -> None:
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    assert WT.reap_worktree(store, "s1", ops) is True
    assert "s1" not in WT.read_registry(store)
    assert WT.reap_worktree(store, "s1", ops) is False  # idempotent — nothing left to reap


def _ops_remove_fails() -> Any:
    """An ops whose remove always fails (a stuck/locked worktree that survives --force)."""
    return WT.WorktreeOps(
        add=lambda _p, _b: True,
        remove=lambda _p: False,
        exists=lambda _p: True,
        list_paths=list,
    )


def test_reap_keeps_the_entry_when_removal_fails(tmp_path: Path) -> None:
    # P2 regression: a failed ops.remove() must NOT deregister — that would silently leak the worktree
    # (drop it from the registry/cap accounting while it survives on disk).
    store = _store(tmp_path)
    WT.register(store, "s1", {"path": str(WT.worktree_path(tmp_path, "o", "s1")), "branch": "x"})
    assert WT.reap_worktree(store, "s1", _ops_remove_fails()) is False
    assert "s1" in WT.read_registry(
        store
    )  # entry retained so a later pass retries (no silent leak)


# --------------------------------------------------------------------------- harvest (R15 reap + R32 + R22)


def _completed(store: Any, sid: str, state: str = "done") -> None:
    STORE.write_completion_event(
        store,
        STORE.CompletionEvent(subplot_id=sid, state=state, idempotency_key=f"k:{sid}:{state}"),
    )


def test_harvest_reaps_terminal_suboutcome_worktrees(tmp_path: Path) -> None:
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    _completed(store, "s1", "done")  # s1 reaches a terminal -> its worktree is reaped
    res = WT.harvest_worktrees(spec, store, ops)
    assert res["reaped"] == ["s1"] and "s1" not in WT.read_registry(store)


def test_removed_worktree_becomes_rejected_terminal_and_cascades(tmp_path: Path) -> None:
    # R32 (the terminal U6 deferred) + R22: a vanished worktree -> rejected; its downstream cascades.
    spec = _spec(
        [
            _sub("s1"),
            {"subplot_id": "dep", "title": "dep", "kind": "code", "depends_on": ["s1"]},
            {"subplot_id": "indep", "title": "indep", "kind": "code"},  # not downstream of s1
        ]
    )
    store = _store(tmp_path)
    fw = FakeWT()
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    fw.paths.clear()  # worktree removed out-of-band (git no longer lists it)
    res = WT.harvest_worktrees(spec, store, ops)
    assert res["removed"] == ["s1"]
    assert res["cascade_paused"] == [
        "dep"
    ]  # only s1's downstream pauses; indep keeps running (R22)
    assert ENG.derive_states(spec, store)["s1"] == "rejected"  # the defined terminal (R32)


def test_transient_git_failure_does_not_terminate_a_live_suboutcome(tmp_path: Path) -> None:
    # R34: ops.exists degraded to True (a flake) must NOT fire the removed terminal.
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT(exists_override=lambda _p: True)  # git "always present" (flake degrades to present)
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    res = WT.harvest_worktrees(spec, store, ops)
    assert res["removed"] == []  # never falsely terminated
    assert "rejected" not in {e.state for e in STORE.read_completion_events(store, "s1")}


def test_removed_terminal_is_idempotent(tmp_path: Path) -> None:
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    fw.paths.clear()
    WT.harvest_worktrees(spec, store, ops)
    WT.harvest_worktrees(spec, store, ops)  # re-run
    assert sum(e.state == "rejected" for e in STORE.read_completion_events(store, "s1")) == 1


def test_harvest_reaps_a_node_gone_orphan(tmp_path: Path) -> None:
    # P2 regression: a registry entry whose node left the spec (pruned away another path) must be
    # reaped + deregistered, not skipped forever holding a cap slot.
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    # s1 is gone from the spec, but its worktree is still registered
    gone_spec = _spec([{"subplot_id": "other", "title": "other", "kind": "code"}])
    res = WT.harvest_worktrees(gone_spec, store, ops)
    assert res["orphaned"] == ["s1"] and "s1" not in WT.read_registry(store)


# --------------------------------------------------------------------------- provision_pending (R15)


def test_provision_only_dispatched_suboutcomes(tmp_path: Path) -> None:
    spec = _spec([_sub("s1"), _sub("s2")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    # mark s1 dispatched via a commit ledger record; s2 stays ready (undispatched)
    STORE.append_ledger(
        store,
        {
            "phase": "commit",
            "kind": "dispatch",
            "key": "dispatch:s1",
            "subplot_id": "s1",
            "leaf_saga_id": "leaf-s1",
        },
    )
    res = WT.provision_pending(tmp_path, spec, store, ops, owner="me", cap=4)
    assert res["provisioned"] == ["s1"] and res["deferred"] == []  # only the dispatched one
    assert "s2" not in WT.read_registry(store)


def test_provision_defers_past_cap(tmp_path: Path) -> None:
    spec = _spec([_sub("s1"), _sub("s2")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    for sid in ("s1", "s2"):
        STORE.append_ledger(
            store,
            {
                "phase": "commit",
                "kind": "dispatch",
                "key": f"dispatch:{sid}",
                "subplot_id": sid,
                "leaf_saga_id": f"leaf-{sid}",
            },
        )
    res = WT.provision_pending(tmp_path, spec, store, ops, owner="me", cap=1)
    assert res["provisioned"] == ["s1"] and res["deferred"] == [
        "s2"
    ]  # cap bounds it, the rest defers


# --------------------------------------------------------------------------- real git adapter (degrade-safe)


def _git_runner(out: str = "", *, rc: int = 0, err: str = "") -> Any:
    return lambda args, **kw: SimpleNamespace(returncode=rc, stdout=out, stderr=err)


def test_real_exists_degrades_to_present_on_git_failure(tmp_path: Path) -> None:
    # git unreadable -> exists() degrades to True (never falsely terminate a live sub-outcome, R34).
    ops = WT.git_worktree_ops(tmp_path, runner=_git_runner(rc=1, err="fatal: not a git repo"))
    assert ops.exists("/anything") is True


def test_real_exists_true_only_when_git_lists_the_path(tmp_path: Path) -> None:
    listing = "worktree /repo/.saga-worktrees/o/s1\nbranch refs/heads/saga-outcome-o-s1\n"
    ops = WT.git_worktree_ops(tmp_path, runner=_git_runner(listing))
    assert ops.exists("/repo/.saga-worktrees/o/s1") is True
    assert ops.exists("/repo/.saga-worktrees/o/missing") is False  # definite absence


def test_real_remove_is_idempotent_when_path_already_gone(tmp_path: Path) -> None:
    # a non-zero `git worktree remove` on an already-absent path is still success (idempotent reaping).
    ops = WT.git_worktree_ops(tmp_path, runner=_git_runner(rc=1, err="is not a working tree"))
    assert ops.remove(str(tmp_path / "definitely-absent")) is True


def test_real_git_adapter_sees_a_live_worktree_under_a_symlinked_root(tmp_path: Path) -> None:
    # P0 regression: with the REAL `git worktree` against a symlinked/relative repo_root, a LIVE
    # on-disk worktree must read as PRESENT — a verbatim string compare read it ABSENT, silently
    # breaking the R15 cap (unbounded fan-out) AND R34 (live sub-outcomes falsely terminated).
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        "PATH": __import__("os").environ["PATH"],
    }
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo, check=True, env=env
    )
    # a symlink to the repo forces the path divergence the P0 was about (link != realpath)
    link = tmp_path / "link"
    link.symlink_to(repo)
    ops = WT.git_worktree_ops(link)
    store = _store(tmp_path)

    spec = _spec([_sub("s1")])
    created = WT.ensure_worktree(link, spec, store, spec.nodes[0], ops, owner="me")
    assert created.state == "created"
    reg = WT.read_registry(store)
    # the live worktree reads PRESENT despite the symlinked/relative registry path (the P0 fix)
    assert ops.exists(reg["s1"]["path"]) is True
    assert WT.live_worktrees(store, ops) == {"s1"}
    # harvest does NOT falsely terminate the live sub-outcome (R34) and does not reap it (non-terminal)
    res = WT.harvest_worktrees(spec, store, ops)
    assert res["removed"] == [] and res["reaped"] == []
    assert ENG.derive_states(spec, store)["s1"] != "rejected"
    # and the cap is now actually enforceable (it counts the live worktree)
    spec2 = _spec([_sub("s1"), _sub("s2")])
    capped = WT.ensure_worktree(link, spec2, store, spec2.nodes[1], ops, owner="me", cap=1)
    assert capped.state == "capped"  # not an unbounded (N+1)th worktree


def test_real_git_dead_worktree_reclamation_retries_without_losing_authority(
    tmp_path: Path,
) -> None:
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        "PATH": os.environ["PATH"],
    }
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo, check=True, env=env
    )
    runtime = FakeLeaseRuntime()
    broker = _lease_broker(tmp_path, runtime, worktree_limit=2)
    spec = _spec([_sub("s1"), _sub("s2")])
    store = _store(tmp_path)
    real_ops = WT.git_worktree_ops(repo)
    for node in spec.nodes:
        WT.ensure_worktree(
            repo,
            spec,
            store,
            node,
            real_ops,
            owner="dead-coordinator",
            cap=2,
            lease_authority=broker,
            lease_ttl_seconds=1,
        )
    paths = {sid: WT.read_registry(store)[sid]["path"] for sid in ("s1", "s2")}
    runtime.advance(1)
    first_failure = True

    def flaky_remove(path: str) -> bool:
        nonlocal first_failure
        if path == paths["s1"] and first_failure:
            first_failure = False
            return False
        return cast(bool, real_ops.remove(path))

    flaky_ops = WT.WorktreeOps(
        add=real_ops.add,
        remove=flaky_remove,
        exists=real_ops.exists,
        list_paths=real_ops.list_paths,
    )
    first = WT.reconcile_worktree_leases(
        repo,
        spec,
        store,
        flaky_ops,
        broker,
        owner="next-coordinator",
        store_resolver=lambda _outcome_id, _repo_root: store,
    )
    assert len(first["lease_reaped"]) == 1
    assert len(first["lease_retained"]) == 1
    assert real_ops.exists(paths["s1"]) is True
    assert real_ops.exists(paths["s2"]) is False

    second = WT.reconcile_worktree_leases(
        repo,
        spec,
        store,
        real_ops,
        broker,
        owner="next-coordinator",
        store_resolver=lambda _outcome_id, _repo_root: store,
    )
    assert len(second["lease_reaped"]) == 1
    assert WT.read_registry(store) == {}
    assert broker.inspect()["leases"] == []
    assert not any(path in real_ops.list_paths() for path in paths.values())


def test_cli_describes_policy(capsys: Any) -> None:
    assert WT.main(["--cap", "7"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["worktree_cap"] == 7 and out["removed_terminal"] == "rejected"
