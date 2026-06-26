"""Tests for the derived-on-read report + the attention consolidator (U8).

Pins R18/AE5/F3 (one ranked prompt: type-tier first — gate -> ambiguity -> failure — then unblock-
leverage within a tier), R19/F6 (the report is regenerated from state, carries the Mermaid topology +
evidence + decision trail, renders cost "when present"/"no data yet" when absent, and is deterministic
so it cannot drift), and R17 (derived-on-read — no operator-writable status, no U10 dependency).
"""

from __future__ import annotations

import importlib.util
import json
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


SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
ORCH = _load("outcome_orchestrator")
_load("outcome_dispatcher")
_load("outcome_merge")
_load("outcome_worktrees")
DEC = _load("outcome_decompose")
ENG = _load("outcome")
REP = _load("outcome_report")


def _store(tmp_path: Path) -> Any:
    return STORE.Store(root=tmp_path / "store").ensure()


def _spec(nodes: list[dict[str, Any]]) -> Any:
    return SPEC.OutcomeSpec.from_dict({"outcome_id": "o", "objective": "Ship it", "nodes": nodes})


def _done(store: Any, sid: str, state: str = "done") -> None:
    STORE.write_completion_event(
        store,
        STORE.CompletionEvent(subplot_id=sid, state=state, idempotency_key=f"k:{sid}:{state}"),
    )


def _dispatched(store: Any, sid: str) -> None:
    STORE.append_ledger(
        store,
        {
            "phase": "commit",
            "kind": "dispatch",
            "key": f"d:{sid}",
            "subplot_id": sid,
            "leaf_saga_id": f"l-{sid}",
        },
    )


def _halt(store: Any, sid: str) -> None:
    STORE.append_ledger(
        store,
        {
            "phase": "halt",
            "kind": "dispatch",
            "key": f"d:{sid}",
            "subplot_id": sid,
            "reason": "backend down",
        },
    )


# --------------------------------------------------------------------------- consolidator (R18/AE5)


def test_consolidator_orders_gate_then_ambiguity_then_failure(tmp_path: Path) -> None:
    # AE5: a gate, an ambiguity, and a failure simultaneously -> gate first, ambiguity second, failure third.
    spec = _spec(
        [
            {"subplot_id": "gate", "title": "g", "kind": "code", "gated": True},
            {"subplot_id": "amb", "title": "a", "kind": "code"},
            {"subplot_id": "fail", "title": "f", "kind": "code"},
        ]
    )
    store = _store(tmp_path)
    DEC.approve_frontier(store, spec)  # isolate per-node tiers from the R20 approval gate
    _dispatched(store, "gate")  # gated + dispatched -> a gate
    _halt(store, "amb")  # HALT receipt -> an ambiguity
    _done(store, "fail", "failed")  # negative terminal -> a failure
    items = REP.consolidate(spec, store)
    assert [it.kind for it in items] == ["gate", "ambiguity", "failure"]
    assert [it.tier for it in items] == [1, 2, 3]


def test_consolidator_ranks_by_unblock_leverage_within_a_tier(tmp_path: Path) -> None:
    # two failures; the one holding up more downstream work sorts first (R18 leverage).
    spec = _spec(
        [
            {"subplot_id": "big", "title": "b", "kind": "code"},
            {"subplot_id": "d1", "title": "d1", "kind": "code", "depends_on": ["big"]},
            {"subplot_id": "d2", "title": "d2", "kind": "code", "depends_on": ["big"]},
            {"subplot_id": "small", "title": "s", "kind": "code"},
        ]
    )
    store = _store(tmp_path)
    _done(store, "big", "failed")
    _done(store, "small", "failed")
    items = [it for it in REP.consolidate(spec, store) if it.kind == "failure"]
    assert [it.subplot_id for it in items] == [
        "big",
        "small",
    ]  # big holds up 2 downstream, sorts first
    assert items[0].leverage == 2 and items[1].leverage == 0


def test_consolidator_classifies_each_node_once_terminal_wins(tmp_path: Path) -> None:
    # a node that is BOTH gated and failed is a FAILURE (terminal), never double-counted as a gate.
    spec = _spec([{"subplot_id": "x", "title": "x", "kind": "code", "gated": True}])
    store = _store(tmp_path)
    _dispatched(store, "x")
    _done(store, "x", "failed")
    items = REP.consolidate(spec, store)
    assert len(items) == 1 and items[0].kind == "failure"


def test_consolidator_is_empty_when_healthy(tmp_path: Path) -> None:
    # "healthy" = the frontier is APPROVED and auto-advancing; an unapproved frontier is NOT healthy.
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code"}])
    store = _store(tmp_path)
    DEC.approve_frontier(store, spec)
    assert REP.consolidate(spec, store) == []
    assert "no operator attention" in REP.consolidated_prompt([])


def test_unapproved_frontier_is_the_top_attention_item(tmp_path: Path) -> None:
    # P2 regression: a started-but-unapproved outcome is NOT a healthy empty surface — the R20 approval
    # gate is the #1 ranked item, and the report must not claim "auto-advancing".
    spec = _spec(
        [
            {"subplot_id": "a", "title": "a", "kind": "code"},
            {"subplot_id": "b", "title": "b", "kind": "code"},
        ]
    )
    store = _store(tmp_path)
    items = REP.consolidate(spec, store)
    assert items and items[0].kind == "approval" and items[0].tier == 1
    assert items[0].leverage == 2  # both ready leaves are held by the unapproved frontier
    # once approved, the gate clears -> healthy empty surface
    DEC.approve_frontier(store, spec)
    assert REP.consolidate(spec, store) == []


def test_halt_then_recovered_is_not_a_sticky_ambiguity(tmp_path: Path) -> None:
    # P1 regression: a halt superseded by a commit (re-dispatch) or by completion must NOT stay an
    # ambiguity forever (that broke the healthy->empty surface).
    spec = _spec([{"subplot_id": "x", "title": "x", "kind": "code"}])
    store = _store(tmp_path)
    DEC.approve_frontier(store, spec)
    _halt(store, "x")
    _done(store, "x", "done")  # halt then recovered-to-done
    assert REP.consolidate(spec, store) == []  # not a sticky ambiguity

    # a halt later superseded by a commit on a gated node -> a gate, not an ambiguity
    spec2 = _spec([{"subplot_id": "y", "title": "y", "kind": "code", "gated": True}])
    store2 = _store(tmp_path / "s2")
    DEC.approve_frontier(store2, spec2)
    _halt(store2, "y")
    _dispatched(store2, "y")  # commit supersedes the halt
    items = REP.consolidate(spec2, store2)
    assert len(items) == 1 and items[0].kind == "gate"


def test_consolidated_prompt_is_one_ranked_block(tmp_path: Path) -> None:
    spec = _spec(
        [
            {"subplot_id": "gate", "title": "g", "kind": "code", "gated": True},
            {"subplot_id": "fail", "title": "f", "kind": "code"},
        ]
    )
    store = _store(tmp_path)
    _dispatched(store, "gate")
    _done(store, "fail", "failed")
    prompt = REP.consolidated_prompt(REP.consolidate(spec, store))
    assert (
        prompt.count("\n") == 2
    )  # one header line + two ranked items = a single page, not N pages
    assert prompt.index("[gate]") < prompt.index("[failure]")


# --------------------------------------------------------------------------- report (R19/F6) — needs a real repo


def _repo(tmp_path: Path) -> Path:
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
    return repo


def test_report_is_deterministic_and_overwrites_from_state(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    ENG.start(
        repo,
        "demo",
        "Ship the thing",
        nodes=[
            {"subplot_id": "a", "title": "A", "kind": "non-code"},
            {"subplot_id": "b", "title": "B", "kind": "code", "depends_on": ["a"]},
        ],
    )
    path1 = REP.write_report(repo, "demo")
    first = path1.read_text(encoding="utf-8")
    # re-render on unchanged state == byte-identical (no wall-clock in the body -> cannot drift, R19)
    assert REP.report_markdown(repo, "demo") == first
    path2 = REP.write_report(repo, "demo")
    assert path2 == path1 and path2.read_text(encoding="utf-8") == first


def test_report_carries_topology_evidence_and_decision_trail(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    ENG.start(
        repo,
        "demo",
        "Ship the thing",
        nodes=[{"subplot_id": "build", "title": "Build", "kind": "code", "github": {"pr": "42"}}],
    )
    text = REP.write_report(repo, "demo").read_text(encoding="utf-8")
    assert "```mermaid" in text  # the topology (KTD12)
    assert "PR 42" in text  # per-subplot evidence
    assert (
        "no data yet" in text
    )  # cost rollup absent -> "no data yet", never a fabricated zero (R24)
    assert "## Decision trail" in text  # the "why" for cold re-entry (F5)


def test_report_renders_a_present_cost_rollup(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    spec = ENG.start(
        repo, "demo", "Ship", nodes=[{"subplot_id": "a", "title": "A", "kind": "code"}]
    )
    spec.cost_rollup = {"tokens": 1234, "operator_touches": 2}
    ENG.save_spec(repo, spec)
    text = REP.report_markdown(repo, "demo")
    assert (
        "tokens:** 1234" in text
        and "no data yet" not in text.split("## Cost rollup")[1].split("##")[0]
    )


def test_report_state_cells_match_derived_state(tmp_path: Path) -> None:
    # R17: every state cell is DERIVED, never a stored/operator-set scalar.
    repo = _repo(tmp_path)
    ENG.start(repo, "demo", "Ship", nodes=[{"subplot_id": "a", "title": "A", "kind": "code"}])
    store = ENG._store(repo, "demo")
    _done(store, "a", "done")
    spec = ENG.load_spec(repo, "demo")
    states = ENG.derive_states(spec, store)
    text = REP.report_markdown(repo, "demo", store=store)
    assert f"| `a` | {states['a']} |" in text


def test_cost_cell_renders_present_keys_not_no_data_yet() -> None:
    # P3 regression: a non-empty cost dict (incl. unmodelled keys / a real 0) renders, never "no data yet".
    node = SPEC.Node.from_dict({"subplot_id": "a", "title": "a", "kind": "code"})
    assert REP._cost_cell(node) == "no data yet"  # truly empty
    node.cost = {"operator_touches": 3}
    assert REP._cost_cell(node) == "operator_touches:3"  # unmodelled key rendered, not dropped
    node.cost = {"tokens": 0}
    assert REP._cost_cell(node) == "tokens:0"  # a real 0 renders (not treated as absent)
    node.cost = {"tokens": 1200, "wall_seconds": 45}
    assert REP._cost_cell(node) == "tokens:1200, wall_s:45"  # sorted, deterministic, renamed


def test_display_percent_never_100_below_completion() -> None:
    # P2 regression: banker's rounding made 199/200 read 100% (incomplete) — display caps at 99.
    assert REP.display_percent(199, 200) == 99
    assert REP.display_percent(200, 200) == 100  # actually complete
    assert REP.display_percent(1, 201) == 1  # real progress never floors to 0
    assert REP.display_percent(0, 5) == 0
    assert REP.display_percent(0, 0) == 0


def test_cli_report_and_attend(tmp_path: Path, capsys: Any) -> None:
    repo = _repo(tmp_path)
    ENG.start(repo, "demo", "Ship", nodes=[{"subplot_id": "a", "title": "A", "kind": "code"}])
    # approve so the frontier is auto-advancing -> the healthy "no operator attention" surface
    store = ENG._store(repo, "demo")
    DEC.approve_frontier(store, ENG.load_spec(repo, "demo"))
    assert REP.main(["--repo-root", str(repo), "report", "demo"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["report"].endswith("docs/outcomes/demo/report.md")
    assert REP.main(["--repo-root", str(repo), "attend", "demo"]) == 0
    assert "no operator attention" in capsys.readouterr().out
