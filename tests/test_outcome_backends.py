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
CERT = _load("reversibility_certificate")


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
    # #657 (U9): workflow_available without host_capable resolves to floor and carries coupling explanation
    workflow_only = D.resolve_available(host_capable=False, workflow_available=True)
    assert workflow_only == ("inline", "team-execution", "manual")
    assert "cc-workflows-ultracode" not in workflow_only
    assert (
        workflow_only.unavailable_reasons.get("cc-workflows-ultracode")
        == "cc-workflows-ultracode unavailable: --workflow-available requires --host-capable"
    )
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


def test_advance_workflow_available_degrade_policy_halt_regression(tmp_path: Path) -> None:
    # #657: an operator passing --workflow-available without --host-capable on a leaf with
    # degrade_policy: "halt" receives a loud HALT naming --host-capable, not a silent downgrade.
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
                "degrade_policy": "halt",
            }
        ],
    )
    _approve(repo, "o")
    avail = D.resolve_available(host_capable=False, workflow_available=True)
    result = ENG.advance(
        repo,
        "o",
        dispatcher=D.make_dispatcher(available=SPEC.NODE_BACKENDS),
        available=avail,
        attending=False,  # away, but degrade_policy: "halt" prevents degrade
    )
    assert result.dispatched == []
    assert len(result.halted) == 1
    assert result.degraded == []
    halt = result.halted[0]
    assert (
        "cc-workflows-ultracode unavailable: --workflow-available requires --host-capable"
        in halt["reason"]
    )


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


# --------------------------------------------------------------------------- U2 subsumption equivalence (R10, R11, R12, R14, R21)


def test_u2_available_backend_dispatches_via_certificate() -> None:
    # golden tuple: certificate-routed path returns identical result (R10, R11)
    assert D.degrade_decision(
        "team-execution",
        available=_FLOOR,
        attending=True,
        guarantee_bearing=False,
        had_side_effect=False,
    ) == ("dispatch", "team-execution", "")


def test_u2_attending_halts_not_degrades_via_certificate() -> None:
    # attending branch fires BEFORE certificate — halt, not degrade (R11, R13)
    action, backend, _ = D.degrade_decision(
        "cc-workflows-ultracode",
        available=_FLOOR,
        attending=True,
        guarantee_bearing=False,
        had_side_effect=False,
    )
    assert action == "halt" and backend == "cc-workflows-ultracode"


def test_u2_autonomous_away_degrades_one_rung_via_certificate() -> None:
    # degrade path: certificate side_effected(False) -> False, does not block degrade (R10, R11)
    action, backend, reason = D.degrade_decision(
        "cc-workflows-ultracode",
        available=_FLOOR,
        attending=False,
        guarantee_bearing=False,
        had_side_effect=False,
    )
    assert action == "degrade" and backend == "team-execution" and "R23" in reason


def test_u2_guarantee_bearing_halts_even_when_away_via_certificate() -> None:
    # guarantee branch fires BEFORE certificate — halt (R11, R13)
    action, _, reason = D.degrade_decision(
        "cc-workflows-ultracode",
        available=_FLOOR,
        attending=False,
        guarantee_bearing=True,
        had_side_effect=False,
    )
    assert action == "halt" and "guarantee" in reason


def test_u2_side_effected_leaf_never_degrades_via_certificate() -> None:
    # certificate-routed: side_effected(True) -> True -> halt (R10, R11)
    action, _, reason = D.degrade_decision(
        "cc-workflows-ultracode",
        available=_FLOOR,
        attending=False,
        guarantee_bearing=False,
        had_side_effect=True,
    )
    assert action == "halt" and "side effect" in reason


def test_u2_backend_not_on_the_ladder_halts_via_certificate() -> None:
    # certificate routes side_effected(False) -> False; no-lower-rung branch fires -> halt (R11)
    action, _, _ = D.degrade_decision(
        "fork", available=_FLOOR, attending=False, guarantee_bearing=False, had_side_effect=False
    )
    assert action == "halt"


def test_u2_degrade_skips_an_unavailable_intermediate_rung_via_certificate() -> None:
    # certificate routes side_effected(False) -> False; degrades to inline floor (R10, R11)
    action, backend, _ = D.degrade_decision(
        "cc-workflows-ultracode",
        available=("inline",),
        attending=False,
        guarantee_bearing=False,
        had_side_effect=False,
    )
    assert action == "degrade" and backend == "inline"


def test_u2_certificate_side_effected_is_identity_passthrough() -> None:
    # pin the pass-through: certificate does not re-derive the fact, just routes it (KTD5, R10, R14)
    assert CERT.side_effected(True) is True
    assert CERT.side_effected(False) is False


def test_u2_side_effected_routes_through_certificate_not_raw_bool(monkeypatch: Any) -> None:
    """Load-bearing substitution test: monkeypatch side_effected to return the negation.

    A scenario that HALTs today purely because had_side_effect=True (backend unavailable, not attending,
    not guarantee_bearing) must now return 'degrade' instead of 'halt' — proving degrade_decision routes
    through the certificate's side_effected fact, not the raw bool (KTD5, R10, R14).
    """
    import reversibility_certificate as _cert_module  # the live module in sys.modules

    monkeypatch.setattr(_cert_module, "side_effected", lambda v: not v)
    action, backend, _ = D.degrade_decision(
        "cc-workflows-ultracode",
        available=_FLOOR,
        attending=False,
        guarantee_bearing=False,
        had_side_effect=True,  # raw True, but certificate now returns False -> should degrade
    )
    assert action == "degrade" and backend == "team-execution"


def test_u2_parent_close_is_always_operator_via_certificate() -> None:
    # R12/AE3: PARENT_ISSUE_CLOSE is ALWAYS_OPERATOR -> GATE -> parent_close stays operator-only
    assert CERT.authorize_write(CERT.OpKind.PARENT_ISSUE_CLOSE) is CERT.GATE


def test_u2_recommend_outcome_backend_output_unaffected_by_certificate(monkeypatch: Any) -> None:
    # R21/AE9: backend recommender is NOT modified by U2; certificate is NOT consulted by the recommender.
    # Confirm that recommend_outcome_backend returns byte-identical results regardless of certificate state.
    import reversibility_certificate as _cert_module

    # Record the result before any monkeypatching
    before = D.recommend_outcome_backend(frontier_width=1, broad_independent_fanout=True)

    # Monkeypatch certificate's authorize_write to return the opposite verdict — recommender must not change
    original_authorize = _cert_module.authorize_write
    monkeypatch.setattr(
        _cert_module,
        "authorize_write",
        lambda op: (
            _cert_module.AUTHORIZED
            if original_authorize(op) is _cert_module.GATE
            else _cert_module.GATE
        ),
    )
    after = D.recommend_outcome_backend(frontier_width=1, broad_independent_fanout=True)
    assert before == after  # byte-identical: certificate not consulted by recommender (R21)
