"""Tests for leaf liveness enforcement — heartbeats + the ``stalled`` terminal (U9 — R31).

Pins R31 (a dispatched leaf breaching ``heartbeat_seconds`` or ``timeout_seconds`` is reclaimed as the
defined ``stalled`` terminal — pages once, idempotent — and cascades to its downstream subtree, R22; a
leaf with no budget is never killed; a heartbeat pushes back the deadline).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

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


SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
ORCH = _load("outcome_orchestrator")
_load("outcome_dispatcher")
_load("outcome_merge")
_load("outcome_worktrees")
_load("outcome_decompose")
ENG = _load("outcome")
LV = _load("outcome_liveness")


def _store(tmp_path: Path) -> Any:
    return STORE.Store(root=tmp_path / "store").ensure()


def _spec(nodes: list[dict[str, Any]]) -> Any:
    return SPEC.OutcomeSpec.from_dict({"outcome_id": "o", "objective": "x", "nodes": nodes})


def _dispatch(store: Any, sid: str, at: float) -> None:
    STORE.append_ledger(
        store,
        {
            "phase": "commit",
            "kind": "dispatch",
            "key": f"d:{sid}",
            "subplot_id": sid,
            "leaf_saga_id": f"l-{sid}",
            "at": at,
        },
    )


def test_timeout_breach_stalls_the_leaf(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code", "timeout_seconds": 100}])
    store = _store(tmp_path)
    _dispatch(store, "a", at=1000.0)
    assert LV.harvest_liveness(spec, store, now=1050.0)["stalled"] == []  # 50s < 100s — alive
    res = LV.harvest_liveness(spec, store, now=1200.0)  # 200s > 100s — stalled
    assert res["stalled"] == ["a"]
    assert ENG.derive_states(spec, store)["a"] == "stalled"


def test_heartbeat_gap_stalls_and_a_recent_heartbeat_resets_the_deadline(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": "b", "title": "b", "kind": "code", "heartbeat_seconds": 30}])
    store = _store(tmp_path)
    _dispatch(store, "b", at=1000.0)
    # a fresh heartbeat at 1040 pushes the deadline; at now=1060 the gap is 20s (< 30) -> alive
    LV.record_heartbeat(store, "b", at=1040.0)
    assert LV.harvest_liveness(spec, store, now=1060.0)["stalled"] == []
    # at now=1100 the gap since the last heartbeat is 60s (> 30) -> stalled
    assert LV.harvest_liveness(spec, store, now=1100.0)["stalled"] == ["b"]


def test_pre_dispatch_heartbeat_does_not_false_stall(tmp_path: Path) -> None:
    # P2 regression (CASE A): a heartbeat with at < dispatch_at (coordinator/leaf clock skew) must NOT
    # make a freshly-launched leaf look idle — last_activity is floored at the dispatch time.
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code", "heartbeat_seconds": 30}])
    store = _store(tmp_path)
    LV.record_heartbeat(store, "a", at=900.0)  # a skewed/early heartbeat
    _dispatch(store, "a", at=1000.0)
    assert LV.harvest_liveness(spec, store, now=1010.0)["stalled"] == []  # 10s since dispatch < 30


def test_out_of_order_heartbeats_use_the_max_timestamp(tmp_path: Path) -> None:
    # P2 regression (CASE B): heartbeats can arrive out of write-order (buffered/replayed) — the latest
    # BY TIMESTAMP wins, not the write-order-last.
    spec = _spec([{"subplot_id": "b", "title": "b", "kind": "code", "heartbeat_seconds": 30}])
    store = _store(tmp_path)
    _dispatch(store, "b", at=1000.0)
    LV.record_heartbeat(store, "b", at=2000.0)
    LV.record_heartbeat(store, "b", at=1500.0)  # written later but an older timestamp
    assert (
        LV.harvest_liveness(spec, store, now=2020.0)["stalled"] == []
    )  # max beat 2000, gap 20 < 30


def test_no_budget_means_never_stalled(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code"}])  # no timeout/heartbeat
    store = _store(tmp_path)
    _dispatch(store, "a", at=1000.0)
    assert LV.harvest_liveness(spec, store, now=10_000_000.0)["stalled"] == []  # runs forever, fine


def test_stalled_is_idempotent_pages_once(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code", "timeout_seconds": 10}])
    store = _store(tmp_path)
    _dispatch(store, "a", at=1000.0)
    LV.harvest_liveness(spec, store, now=2000.0)
    LV.harvest_liveness(spec, store, now=3000.0)  # re-run
    assert sum(e.state == "stalled" for e in STORE.read_completion_events(store, "a")) == 1


def test_stalled_cascades_to_downstream(tmp_path: Path) -> None:
    spec = _spec(
        [
            {"subplot_id": "a", "title": "a", "kind": "code", "timeout_seconds": 10},
            {"subplot_id": "dep", "title": "dep", "kind": "code", "depends_on": ["a"]},
            {"subplot_id": "indep", "title": "indep", "kind": "code"},
        ]
    )
    store = _store(tmp_path)
    _dispatch(store, "a", at=1000.0)
    res = LV.harvest_liveness(spec, store, now=2000.0)
    assert res["stalled"] == ["a"]
    assert res["cascade_paused"] == [
        "dep"
    ]  # only a's downstream pauses; indep is independent (R22)


def test_only_dispatched_leaves_are_liveness_checked(tmp_path: Path) -> None:
    # a ready (undispatched) leaf with a budget is not "running", so it cannot stall.
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code", "timeout_seconds": 1}])
    store = _store(tmp_path)
    # no dispatch record -> a is 'ready', not 'dispatched'
    assert LV.harvest_liveness(spec, store, now=10_000.0)["stalled"] == []


def test_legacy_dispatch_without_timestamp_is_skipped(tmp_path: Path) -> None:
    # a dispatch commit record with no `at` (pre-U9) cannot be judged for liveness -> skipped, not crashed.
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code", "timeout_seconds": 10}])
    store = _store(tmp_path)
    STORE.append_ledger(
        store,
        {
            "phase": "commit",
            "kind": "dispatch",
            "key": "d:a",
            "subplot_id": "a",
            "leaf_saga_id": "l-a",
        },
    )
    assert LV.harvest_liveness(spec, store, now=10_000.0)["stalled"] == []


def test_cli_describes_policy(capsys: Any) -> None:
    import json

    assert LV.main([]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["stalled_state"] == "stalled"
