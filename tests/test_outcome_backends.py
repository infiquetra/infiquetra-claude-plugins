"""Tests for the full backend menu + the presence-conditional degrade policy (U9).

Pins R6 (the runnable menu is host-conditional: always-available floor + host-dependent backends), R23/AE1
(an unavailable backend HALTs when attended / guarantee-bearing / already side-effected, else degrades one
rung down the ladder when autonomous + away, recording a visible receipt surfaced in the report), and R7
(the recommender is frontier-budget aware; the fork cost lever is claimed only when it is actually cheap).
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


_load("lifecycle_state")
SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
ORCH = _load("outcome_orchestrator")
D = _load("outcome_dispatcher")
_load("outcome_merge")
_load("outcome_worktrees")
DEC = _load("outcome_decompose")
ENG = _load("outcome")
REP = _load("outcome_report")
_load("outcome_liveness")


def _node(sid: str, **kw: Any) -> Any:
    return SPEC.Node.from_dict({"subplot_id": sid, "title": sid, "kind": "code", **kw})


# --------------------------------------------------------------------------- resolve_available (R6)


def test_resolve_available_is_host_conditional() -> None:
    assert D.resolve_available() == ("inline", "team-execution", "manual")
    host = D.resolve_available(host_capable=True)
    assert (
        "fork" in host
        and "subagent" in host
        and "goal" in host
        and "cc-workflows-ultracode" not in host
    )
    full = D.resolve_available(host_capable=True, workflow_available=True)
    assert "cc-workflows-ultracode" in full
    # ordered by the spec's NODE_BACKENDS vocabulary (deterministic)
    assert list(full) == [b for b in SPEC.NODE_BACKENDS if b in set(full)]


# --------------------------------------------------------------------------- degrade_decision (R23/AE1)

_FLOOR = ("inline", "team-execution", "manual")  # cc-workflows-ultracode unavailable


def test_available_backend_dispatches() -> None:
    assert D.degrade_decision(
        "team-execution",
        available=_FLOOR,
        attending=True,
        guarantee_bearing=False,
        had_side_effect=False,
    ) == ("dispatch", "team-execution", "")


def test_attending_halts_not_degrades() -> None:
    action, backend, _ = D.degrade_decision(
        "cc-workflows-ultracode",
        available=_FLOOR,
        attending=True,
        guarantee_bearing=False,
        had_side_effect=False,
    )
    assert action == "halt" and backend == "cc-workflows-ultracode"


def test_autonomous_away_degrades_one_rung() -> None:
    action, backend, reason = D.degrade_decision(
        "cc-workflows-ultracode",
        available=_FLOOR,
        attending=False,
        guarantee_bearing=False,
        had_side_effect=False,
    )
    assert action == "degrade" and backend == "team-execution" and "R23" in reason


def test_guarantee_bearing_halts_even_when_away() -> None:
    action, _, reason = D.degrade_decision(
        "cc-workflows-ultracode",
        available=_FLOOR,
        attending=False,
        guarantee_bearing=True,
        had_side_effect=False,
    )
    assert action == "halt" and "guarantee" in reason


def test_side_effected_leaf_never_degrades() -> None:
    action, _, reason = D.degrade_decision(
        "cc-workflows-ultracode",
        available=_FLOOR,
        attending=False,
        guarantee_bearing=False,
        had_side_effect=True,
    )
    assert action == "halt" and "side effect" in reason


def test_backend_not_on_the_ladder_halts() -> None:
    # fork is not on the cc-workflows->team-execution->inline degrade ladder -> no rung -> HALT.
    action, _, _ = D.degrade_decision(
        "fork", available=_FLOOR, attending=False, guarantee_bearing=False, had_side_effect=False
    )
    assert action == "halt"


def test_degrade_skips_an_unavailable_intermediate_rung() -> None:
    # cc-workflows + team-execution both unavailable -> degrade to the inline floor (first available rung).
    action, backend, _ = D.degrade_decision(
        "cc-workflows-ultracode",
        available=("inline",),
        attending=False,
        guarantee_bearing=False,
        had_side_effect=False,
    )
    assert action == "degrade" and backend == "inline"


def test_is_guarantee_bearing() -> None:
    assert D.is_guarantee_bearing(_node("a", guarantee_tags=["security"])) is True
    assert D.is_guarantee_bearing(_node("a", degrade_policy="halt")) is True
    assert D.is_guarantee_bearing(_node("a")) is False


# --------------------------------------------------------------------------- recommender (R7)


def test_fork_is_cheap_only_when_everything_matches_within_ttl() -> None:
    assert D.fork_is_cheap(
        model_matches=True, system_matches=True, tools_match=True, within_ttl=True
    )
    assert not D.fork_is_cheap(
        model_matches=True, system_matches=True, tools_match=True, within_ttl=False
    )
    assert not D.fork_is_cheap(
        model_matches=False, system_matches=True, tools_match=True, within_ttl=True
    )


def test_recommender_is_frontier_budget_aware() -> None:
    narrow = D.recommend_outcome_backend(frontier_width=1, broad_independent_fanout=True)
    assert (
        narrow["recommended"] == "cc-workflows-ultracode"
    )  # a narrow frontier affords the workflow
    wide = D.recommend_outcome_backend(frontier_width=20, broad_independent_fanout=True)
    assert (
        wide["recommended"] == "team-execution" and "budget_note" in wide
    )  # wide -> budget downgrade
    assert "cc-workflows-ultracode" in wide["alternatives"]  # escalation stays one keystroke


def test_recommender_takes_fork_only_when_cheap() -> None:
    cheap = D.recommend_outcome_backend(
        fork_candidate=True,
        fork_signals={
            "model_matches": True,
            "system_matches": True,
            "tools_match": True,
            "within_ttl": True,
        },
    )
    assert cheap["recommended"] == "fork"
    not_cheap = D.recommend_outcome_backend(
        fork_candidate=True,
        fork_signals={
            "model_matches": True,
            "system_matches": True,
            "tools_match": False,
            "within_ttl": True,
        },
        broad_independent_fanout=True,
    )
    assert not_cheap["recommended"] != "fork"  # a cache-missing fork is not claimed as cheap


# --------------------------------------------------------------------------- advance integration (R23)


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


def _approve(repo: Path, oid: str) -> None:
    DEC.approve_frontier(ENG._store(repo, oid), ENG.load_spec(repo, oid))


def test_advance_degrades_an_autonomous_cc_workflows_leaf_and_records_a_receipt(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    ENG.start(
        repo,
        "o",
        "ship",
        nodes=[
            {
                "subplot_id": "build",
                "title": "B",
                "kind": "code",
                "backend": "cc-workflows-ultracode",
            }
        ],
    )
    _approve(repo, "o")
    floor = D.resolve_available()  # cc-workflows-ultracode NOT available
    result = ENG.advance(
        repo,
        "o",
        dispatcher=D.make_dispatcher(available=SPEC.NODE_BACKENDS),
        available=floor,
        attending=False,  # autonomous + away
    )
    assert result.dispatched == ["build"] and result.halted == []
    assert len(result.degraded) == 1 and result.degraded[0]["to_backend"] == "team-execution"
    # the degrade is surfaced in the report (R23)
    text = REP.report_markdown(repo, "o", store=ENG._store(repo, "o"))
    assert "## Degradations" in text and "cc-workflows-ultracode → team-execution" in text


def test_advance_halts_an_attended_unavailable_leaf(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    ENG.start(
        repo,
        "o",
        "ship",
        nodes=[
            {
                "subplot_id": "build",
                "title": "B",
                "kind": "code",
                "backend": "cc-workflows-ultracode",
            }
        ],
    )
    _approve(repo, "o")
    result = ENG.advance(
        repo,
        "o",
        dispatcher=D.make_dispatcher(available=SPEC.NODE_BACKENDS),
        available=D.resolve_available(),
        attending=True,  # operator attending -> HALT, never degrade
    )
    assert result.dispatched == [] and len(result.halted) == 1 and result.degraded == []


def test_repeated_halt_appends_one_ledger_record_not_n(tmp_path: Path) -> None:
    # P2 regression: an attended leaf polling advance against a persistently-unavailable backend must
    # NOT grow the ledger by one halt record per tick (append-once on (halt, key)).
    repo = _repo(tmp_path)
    ENG.start(
        repo,
        "o",
        "ship",
        nodes=[
            {
                "subplot_id": "build",
                "title": "B",
                "kind": "code",
                "backend": "cc-workflows-ultracode",
            }
        ],
    )
    _approve(repo, "o")
    for _ in range(5):
        ENG.advance(
            repo,
            "o",
            dispatcher=D.make_dispatcher(available=SPEC.NODE_BACKENDS),
            available=D.resolve_available(),
            attending=True,
        )
    store = ENG._store(repo, "o")
    halts = [
        r
        for r in STORE.read_ledger(store)
        if r.get("phase") == "halt" and r.get("key") == "dispatch:build"
    ]
    assert len(halts) == 1  # one halt record across 5 advances, not 5


def test_degrade_record_is_not_double_listed_after_a_crash(tmp_path: Path) -> None:
    # P2 regression: a crash in the degrade->commit window (recovery re-runs the intent) must not
    # double-list the degradation (append-once on (degrade, key)).
    repo = _repo(tmp_path)
    ENG.start(
        repo,
        "o",
        "ship",
        nodes=[
            {
                "subplot_id": "build",
                "title": "B",
                "kind": "code",
                "backend": "cc-workflows-ultracode",
            }
        ],
    )
    _approve(repo, "o")
    store = ENG._store(repo, "o")
    # simulate a pre-crash degrade record + intent with NO commit
    STORE.append_ledger(
        store,
        {"phase": "intent", "kind": "dispatch", "key": "dispatch:build", "subplot_id": "build"},
    )
    STORE.append_ledger(
        store,
        {
            "phase": "degrade",
            "key": "dispatch:build",
            "kind": "degrade",
            "outcome_id": "o",
            "subplot_id": "build",
            "from_backend": "cc-workflows-ultracode",
            "to_backend": "team-execution",
            "reason": "x",
        },
    )
    ENG.advance(
        repo,
        "o",
        dispatcher=D.make_dispatcher(available=SPEC.NODE_BACKENDS),
        available=D.resolve_available(),
        attending=False,
    )
    degrades = [r for r in STORE.read_ledger(store) if r.get("phase") == "degrade"]
    commits = [
        r
        for r in STORE.read_ledger(store)
        if r.get("phase") == "commit" and r.get("kind") == "dispatch"
    ]
    assert len(degrades) == 1 and len(commits) == 1  # one degrade, one dispatch — no double-list


def test_cli_dispatch_dry_run_still_works(capsys: Any) -> None:
    # the U4 dry-run CLI is unchanged by the U9 menu expansion
    assert D.main(["o", "build", "team-execution"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "dispatched"
