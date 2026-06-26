"""Tests for realized economics — per-subplot cost + the per-outcome rollup (U10 — R24/R7).

Pins R24 (every cost field has a producer `record_cost` AND a consumer `rollup`; tokens / operator
touches / retries aggregate per outcome; the rollup answers "did the DAG beat one long thread?" with the
critical-path-vs-serial comparison; missing telemetry is "no data yet" not a fabricated zero; pruned-node
cost is reconciled into `sunk`, R33) and the producer -> spec.cost_rollup -> U8-report consumer edge.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
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


_load("lifecycle_state")
SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
ORCH = _load("outcome_orchestrator")
_load("outcome_dispatcher")
_load("outcome_merge")
_load("outcome_worktrees")
DEC = _load("outcome_decompose")
ENG = _load("outcome")
REP = _load("outcome_report")
_load("outcome_liveness")
C = _load("outcome_costs")


def _store(tmp_path: Path) -> Any:
    return STORE.Store(root=tmp_path / "store").ensure()


def _spec(nodes: list[dict[str, Any]]) -> Any:
    return SPEC.OutcomeSpec.from_dict({"outcome_id": "o", "objective": "x", "nodes": nodes})


# --------------------------------------------------------------------------- producer <-> consumer (R24)


def test_every_cost_field_has_a_producer_and_a_consumer(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code"}])
    store = _store(tmp_path)
    C.record_cost(
        store,
        "a",
        executor="team-execution",
        tokens=100,
        wall_seconds=10,
        operator_touches=2,
        retries=1,
        evidence="PR 5",
    )
    # producer round-trips through subplot_cost
    sc = C.subplot_cost(store, "a")
    assert sc["executor"] == "team-execution" and sc["tokens"] == 100 and sc["evidence"] == "PR 5"
    # consumer (rollup) surfaces each numeric field
    r = C.rollup(spec, store)
    assert r["tokens"] == 100 and r["operator_touches"] == 2 and r["retries"] == 1
    assert r["by_executor"] == {"team-execution": 1}


def test_tokens_touches_retries_aggregate_per_outcome(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": s, "title": s, "kind": "code"} for s in ("a", "b")])
    store = _store(tmp_path)
    C.record_cost(store, "a", tokens=100, operator_touches=1, retries=0)
    C.record_cost(store, "b", tokens=250, operator_touches=3, retries=2)
    r = C.rollup(spec, store)
    assert r["tokens"] == 350 and r["operator_touches"] == 4 and r["retries"] == 2


def test_latest_cost_record_wins(tmp_path: Path) -> None:
    store = _store(tmp_path)
    C.record_cost(store, "a", tokens=10, at=1.0)
    C.record_cost(store, "a", tokens=99, at=2.0)  # a later (final) report
    assert C.subplot_cost(store, "a")["tokens"] == 99
    # out-of-order append: an older `at` written later does not win (max-by-timestamp)
    C.record_cost(store, "a", tokens=50, at=1.5)
    assert C.subplot_cost(store, "a")["tokens"] == 99


# --------------------------------------------------------------------------- DAG vs one thread (R24)


def test_rollup_answers_did_the_dag_beat_one_thread(tmp_path: Path) -> None:
    # a -> {b, c}; serial = 10+20+5 = 35; critical path = a(10)+b(20) = 30 -> the DAG beat one thread.
    spec = _spec(
        [
            {"subplot_id": "a", "title": "a", "kind": "code"},
            {"subplot_id": "b", "title": "b", "kind": "code", "depends_on": ["a"]},
            {"subplot_id": "c", "title": "c", "kind": "code", "depends_on": ["a"]},
        ]
    )
    store = _store(tmp_path)
    C.record_cost(store, "a", wall_seconds=10)
    C.record_cost(store, "b", wall_seconds=20)
    C.record_cost(store, "c", wall_seconds=5)
    r = C.rollup(spec, store)
    assert r["wall_seconds_serial"] == 35
    assert r["wall_seconds_parallel"] == 30  # the critical path a->b
    assert r["beat_one_thread"] is True


def test_a_pure_chain_does_not_beat_one_thread(tmp_path: Path) -> None:
    # a -> b -> c (no parallelism): critical path == serial -> beat_one_thread False (honest).
    spec = _spec(
        [
            {"subplot_id": "a", "title": "a", "kind": "code"},
            {"subplot_id": "b", "title": "b", "kind": "code", "depends_on": ["a"]},
            {"subplot_id": "c", "title": "c", "kind": "code", "depends_on": ["b"]},
        ]
    )
    store = _store(tmp_path)
    for s in ("a", "b", "c"):
        C.record_cost(store, s, wall_seconds=10)
    r = C.rollup(spec, store)
    assert r["wall_seconds_serial"] == 30 and r["wall_seconds_parallel"] == 30
    assert r["beat_one_thread"] is False


def test_pure_chain_in_reverse_topo_order_with_fractional_walls_does_not_fake_a_win(
    tmp_path: Path,
) -> None:
    # P1 regression: nodes declared reverse-topo + fractional walls -> declaration-order float sum drifts
    # 1 ULP from the topo-order critical path; a bare `<` would fabricate beat_one_thread=True on a pure
    # serial chain. The tolerance comparison + fsum keep it honest.
    spec = _spec(
        [
            {"subplot_id": "c", "title": "c", "kind": "code", "depends_on": ["b"]},
            {"subplot_id": "b", "title": "b", "kind": "code", "depends_on": ["a"]},
            {"subplot_id": "a", "title": "a", "kind": "code"},
        ]
    )
    store = _store(tmp_path)
    C.record_cost(store, "a", wall_seconds=0.3)
    C.record_cost(store, "b", wall_seconds=0.2)
    C.record_cost(store, "c", wall_seconds=0.1)
    r = C.rollup(spec, store)
    assert r["beat_one_thread"] is False  # a pure chain never "beats one thread"


# --------------------------------------------------------------------------- honesty (R24 / the U8 stance)


def test_no_telemetry_is_no_data_yet_not_a_zero(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code"}])
    store = _store(tmp_path)
    assert C.rollup(spec, store) == {}  # empty -> U8 renders "no data yet", never a fabricated zero


def test_missing_telemetry_is_counted_not_summed_as_zero(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": s, "title": s, "kind": "code"} for s in ("a", "b")])
    store = _store(tmp_path)
    C.record_cost(store, "a", tokens=10)  # b records nothing
    r = C.rollup(spec, store)
    assert r["leaves_with_cost"] == 1 and r["leaves_total"] == 2  # b is missing, not a 0


def test_an_executor_only_record_omits_numeric_fields_not_fabricates_zeros(tmp_path: Path) -> None:
    # P2 regression: a leaf that records only its executor (no numeric telemetry) must NOT surface
    # tokens:0.0 / retries:0.0 / wall_seconds_serial:0.0 as hard facts — those fields are OMITTED.
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code"}])
    store = _store(tmp_path)
    C.record_cost(store, "a", executor="team-execution")  # no numeric fields
    r = C.rollup(spec, store)
    assert r["by_executor"] == {"team-execution": 1} and r["leaves_with_cost"] == 1
    for f in ("tokens", "operator_touches", "retries", "wall_seconds_serial", "beat_one_thread"):
        assert f not in r  # omitted, never a fabricated 0


def test_a_later_untimestamped_record_supersedes_an_earlier_timestamped_one(tmp_path: Path) -> None:
    # P2 regression: a physically-later untimestamped report must win (write-order causal), not be locked
    # out by an earlier timestamped record.
    store = _store(tmp_path)
    C.record_cost(store, "a", tokens=10, at=1.0)
    C.record_cost(store, "a", tokens=99)  # later, no timestamp
    assert C.subplot_cost(store, "a")["tokens"] == 99


def test_record_cost_rejects_a_non_timestamp_at(tmp_path: Path) -> None:
    # P3: at=True / at="now" are caller errors, not a 1.0 epoch or an uncaught float() crash.
    store = _store(tmp_path)
    for bad in (True, "now"):
        try:
            C.record_cost(store, "a", tokens=1, at=bad)  # type: ignore[arg-type]
            raise AssertionError(f"expected a rejection for at={bad!r}")
        except ValueError:
            pass


# --------------------------------------------------------------------------- sunk cost (R33 — U7 deferred)


def test_pruned_node_cost_is_reconciled_into_sunk(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": s, "title": s, "kind": "code"} for s in ("keep", "a")])
    store = _store(tmp_path)
    C.record_cost(store, "a", tokens=99, wall_seconds=9)
    C.record_cost(store, "keep", tokens=1)
    DEC.prune(spec, store, "a")  # a leaves the spec
    r = C.rollup(spec, store)
    assert r["tokens"] == 1  # active total excludes the pruned node
    assert r["sunk"]["subplots"] == ["a"] and r["sunk"]["tokens"] == 99  # accounted, not dropped


# --------------------------------------------------------------------------- materialize + report (U8 edge)


def test_materialize_writes_rollup_only_when_changed(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code"}])
    store = _store(tmp_path)
    C.record_cost(store, "a", tokens=10)
    assert C.materialize(spec, store) is True and spec.cost_rollup["tokens"] == 10
    assert C.materialize(spec, store) is False  # unchanged -> no re-write


def test_report_renders_the_materialized_rollup(tmp_path: Path) -> None:
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
        ["git", "commit", "-q", "--allow-empty", "-m", "i"], cwd=repo, check=True, env=env
    )
    ENG.start(repo, "o", "ship", nodes=[{"subplot_id": "a", "title": "a", "kind": "code"}])
    store = ENG._store(repo, "o")
    # before any cost: the report says "no data yet"
    assert "no data yet" in REP.report_markdown(repo, "o", store=store)
    # record cost + materialize into the spec (the cost_processor's job), then the report renders it
    C.record_cost(store, "a", tokens=42, wall_seconds=3)
    spec = ENG.load_spec(repo, "o")
    assert C.materialize(spec, store) is True
    ENG.save_spec(repo, spec)
    text = REP.report_markdown(repo, "o", store=store)
    assert "no data yet" not in text.split("## Cost rollup")[1].split("##")[0]
    assert "tokens" in text and "42" in text


def test_cli_describes_fields(capsys: Any) -> None:
    import json

    assert C.main([]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "tokens" in out["per_subplot"] and "executor" in out["per_subplot"]
