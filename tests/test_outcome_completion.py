"""Tests for the completion barrier + GitHub read + harvest + cascade (U5).

Pins R9 (parent-owned barrier predicate over evidence, HALT on unmet contract), R10/R11 (per-subplot
completion contract — code=PR-merged, non-code=tick+canonical-marker, child=terminal-success),
R22 (only the downstream subtree of a block pauses), R27/R28 (GitHub-canonical, cache-less reconstruct),
and R34 (a GitHub read failure degrades to ``unknown``, never a false completion).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

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


GH = _load("outcome_github")
SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
ORCH = _load("outcome_orchestrator")
OUTCOME = _load("outcome")


def _store(tmp_path: Path):
    return STORE.Store(root=tmp_path / "store").ensure()


def _gh(
    pr: dict[str, str] | None = None, issue: dict[str, str] | None = None, *, fail: bool = False
):
    """A fake ``gh`` runner: maps a pr/issue ref to a GitHub state (UPPERCASE), or fails (offline)."""
    pr = pr or {}
    issue = issue or {}

    def runner(args: list[str], **_kw: Any) -> SimpleNamespace:
        if fail:
            return SimpleNamespace(returncode=1, stdout="", stderr="gh down")
        kind, ref = args[1], args[3]
        if kind == "pr":
            st = pr.get(ref, "OPEN")
            body = {"state": st, "mergedAt": "2026-06-26T00:00:00Z" if st == "MERGED" else None}
        else:
            body = {"state": issue.get(ref, "OPEN")}
        return SimpleNamespace(returncode=0, stdout=json.dumps(body), stderr="")

    return runner


def _node(sid: str, **kw: Any):
    data = {"subplot_id": sid, "title": sid, **kw}
    return SPEC.Node.from_dict(data)


# --------------------------------------------------------------------------- outcome_github (R10/R34)


def test_pr_state_merged_closed_open() -> None:
    assert GH.pr_state("1", runner=_gh(pr={"1": "MERGED"})) == "merged"
    assert GH.pr_state("2", runner=_gh(pr={"2": "CLOSED"})) == "closed"  # closed-unmerged != merged
    assert GH.pr_state("3", runner=_gh(pr={"3": "OPEN"})) == "open"


def test_pr_state_offline_is_unknown_never_false_merged() -> None:
    # R34: a read failure must degrade to unknown — never fabricate a merged/closed completion.
    assert GH.pr_state("1", runner=_gh(fail=True)) == "unknown"


def test_issue_state() -> None:
    assert GH.issue_state("7", runner=_gh(issue={"7": "CLOSED"})) == "closed"
    assert GH.issue_state("8", runner=_gh(issue={"8": "OPEN"})) == "open"
    assert GH.issue_state("9", runner=_gh(fail=True)) == "unknown"


# --------------------------------------------------------------------------- code-leaf barrier (R11)


def test_code_leaf_done_only_when_pr_merged(tmp_path: Path) -> None:
    store = _store(tmp_path)
    node = _node("build", kind="code", github={"pr": "42"})
    merged = ORCH.barrier_satisfied(node, store=store, github_runner=_gh(pr={"42": "MERGED"}))
    assert merged.satisfied and merged.contract == ORCH.CONTRACT_CODE and merged.state == "merged"
    # PR still open -> the parent HALTs on the unmet contract (R9), not a child self-report
    openv = ORCH.barrier_satisfied(node, store=store, github_runner=_gh(pr={"42": "OPEN"}))
    assert not openv.satisfied and openv.state == "open"


def test_code_leaf_no_pr_ref_is_not_satisfied(tmp_path: Path) -> None:
    node = _node("build", kind="code")  # no github.pr yet
    v = ORCH.barrier_satisfied(node, store=_store(tmp_path), github_runner=_gh())
    assert not v.satisfied and "no PR ref" in v.reason


# --------------------------------------------------------------------------- non-code barrier (R11)


def test_noncode_leaf_done_when_tracking_issue_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    node = _node("design", kind="non-code", github={"issue": "7"})
    closed = ORCH.barrier_satisfied(node, store=store, github_runner=_gh(issue={"7": "CLOSED"}))
    assert closed.satisfied and closed.contract == ORCH.CONTRACT_NONCODE
    openv = ORCH.barrier_satisfied(node, store=store, github_runner=_gh(issue={"7": "OPEN"}))
    assert not openv.satisfied


def test_noncode_leaf_canonical_event_without_issue(tmp_path: Path) -> None:
    # Untracked local non-code work: the durable marker is a completion event flagged canonical.
    store = _store(tmp_path)
    node = _node("notes", kind="non-code")
    assert not ORCH.barrier_satisfied(node, store=store, github_runner=_gh()).satisfied
    STORE.write_completion_event(
        store,
        STORE.CompletionEvent(
            subplot_id="notes", state="done", idempotency_key="k", payload={"canonical": True}
        ),
    )
    assert ORCH.barrier_satisfied(node, store=store, github_runner=_gh()).satisfied


# --------------------------------------------------------------------------- child-outcome barrier (KTD10)


def test_child_outcome_done_only_when_child_terminal_successful(tmp_path: Path) -> None:
    store = _store(tmp_path)
    node = _node("subgraph", child_spec_ref="child-x")
    assert node.is_outcome
    done = ORCH.barrier_satisfied(node, store=store, child_state_reader=lambda c: "done")
    assert done.satisfied and done.contract == ORCH.CONTRACT_CHILD
    running = ORCH.barrier_satisfied(node, store=store, child_state_reader=lambda c: "running")
    assert not running.satisfied
    # a NEGATIVE child terminal is also not "satisfied" (it is a failure, not completion)
    failed = ORCH.barrier_satisfied(node, store=store, child_state_reader=lambda c: "failed")
    assert not failed.satisfied


# --------------------------------------------------------------------------- harvest (R10 unlock)


def _spec(nodes: list[dict[str, Any]]):
    return SPEC.OutcomeSpec.from_dict({"outcome_id": "o", "objective": "x", "nodes": nodes})


def test_harvest_materializes_merged_pr_and_unlocks_dependents(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec(
        [
            {"subplot_id": "design", "title": "d", "kind": "code", "github": {"pr": "1"}},
            {
                "subplot_id": "build",
                "title": "b",
                "kind": "code",
                "github": {"pr": "2"},
                "depends_on": ["design"],
            },
        ]
    )
    # design merged, build still open
    runner = _gh(pr={"1": "MERGED", "2": "OPEN"})
    harvested = ORCH.harvest(spec, store=store, github_runner=runner)
    assert harvested == ["design"]  # only the merged leaf is harvested
    assert STORE.completed_subplots(store) == {"design"}
    # design's merge unlocks build as the new frontier (R10)
    assert SPEC.ready_frontier(spec, STORE.completed_subplots(store)) == ["build"]


def test_harvest_is_idempotent(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec([{"subplot_id": "design", "title": "d", "kind": "code", "github": {"pr": "1"}}])
    runner = _gh(pr={"1": "MERGED"})
    assert ORCH.harvest(spec, store=store, github_runner=runner) == ["design"]
    assert ORCH.harvest(spec, store=store, github_runner=runner) == []  # already harvested
    assert len(STORE.read_completion_events(store, "design")) == 1


def test_cacheless_machine_reharvests_from_github(tmp_path: Path) -> None:
    # R27/R11: a non-code completion survives a cache wipe because its canonical marker (closed issue)
    # is on GitHub — harvest re-materializes the completion from GitHub, no canonical state lost.
    store = _store(tmp_path)
    spec = _spec(
        [{"subplot_id": "design", "title": "d", "kind": "non-code", "github": {"issue": "7"}}]
    )
    runner = _gh(issue={"7": "CLOSED"})
    assert ORCH.harvest(spec, store=store, github_runner=runner) == ["design"]
    shutil.rmtree(store.root)  # wipe the cache
    fresh = STORE.Store(root=store.root)
    assert STORE.completed_subplots(fresh) == set()  # cache lost
    assert ORCH.harvest(spec, store=fresh, github_runner=runner) == [
        "design"
    ]  # re-derived from GitHub


# --------------------------------------------------------------------------- cascade (R22)


def test_blocked_subtree_pauses_downstream_only_not_siblings() -> None:
    # A->B->C is one chain; D->E is an independent chain. Blocking B pauses only C (B's downstream).
    spec = _spec(
        [
            {"subplot_id": "A", "title": "A"},
            {"subplot_id": "B", "title": "B", "depends_on": ["A"]},
            {"subplot_id": "C", "title": "C", "depends_on": ["B"]},
            {"subplot_id": "D", "title": "D"},
            {"subplot_id": "E", "title": "E", "depends_on": ["D"]},
        ]
    )
    paused = ORCH.blocked_subtree(spec, {"B"})
    assert paused == {"C"}  # only B's downstream; A (upstream) + D/E (independent) keep running


# --------------------------------------------------------------------------- P1: attempt collision


def test_harvest_writes_fresh_attempt_over_a_prior_failed_terminal(tmp_path: Path) -> None:
    # A subplot holding a NON-success terminal at attempt 1 is not in completed_subplots, so harvest
    # must write a FRESH attempt slot — a hardcoded attempt-1 write would collide + raise + wedge the
    # whole reconcile loop.
    store = _store(tmp_path)
    STORE.write_completion_event(
        store,
        STORE.CompletionEvent(
            subplot_id="build", state="failed", idempotency_key="fail-1", attempt=1
        ),
    )
    spec = _spec([{"subplot_id": "build", "title": "b", "kind": "code", "github": {"pr": "9"}}])
    # PR now merged -> harvest must materialize success without colliding with the failed a1 slot
    harvested = ORCH.harvest(spec, store=store, github_runner=_gh(pr={"9": "MERGED"}))
    assert harvested == ["build"]
    assert "build" in STORE.completed_subplots(store)  # success now recorded (sticky)
    assert {e.attempt for e in STORE.read_completion_events(store, "build")} == {1, 2}


# --------------------------------------------------------------------------- P2: advance integration


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    common = tmp_path / ".git"
    common.mkdir()
    monkeypatch.setattr(
        OUTCOME.outcome_store.subprocess,
        "run",
        lambda args, **kw: SimpleNamespace(returncode=0, stdout=str(common) + "\n", stderr=""),
    )
    return tmp_path


def test_advance_harvester_unlocks_dependents_in_one_tick(repo: Path) -> None:
    # End-to-end: advance(harvester=production_harvester) harvests a merged PR BEFORE the frontier read,
    # so design's completion unlocks build and build dispatches in the SAME advance.
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[
            {"subplot_id": "design", "title": "d", "kind": "code", "github": {"pr": "1"}},
            {
                "subplot_id": "build",
                "title": "b",
                "kind": "code",
                "github": {"pr": "2"},
                "depends_on": ["design"],
            },
        ],
    )
    gh = _gh(pr={"1": "MERGED", "2": "OPEN"})
    result = OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=OUTCOME.outcome_dispatcher.make_dispatcher(),
        harvester=OUTCOME.production_harvester(repo, github_runner=gh),
    )
    assert result.harvested == ["design"]  # merged PR materialized
    assert result.dispatched == ["build"]  # unlocked + dispatched the same tick


def test_production_harvester_child_outcome_recurses(repo: Path) -> None:
    # KTD10: a parent child_spec_ref node unlocks only when the child outcome's terminal state reads
    # done — the production harvester recurses into the child outcome to determine that.
    OUTCOME.start(
        repo,
        "child-x",
        "Child outcome",
        nodes=[{"subplot_id": "leaf", "title": "l", "kind": "non-code", "github": {"issue": "5"}}],
    )
    OUTCOME.start(
        repo,
        "parent",
        "Parent outcome",
        nodes=[{"subplot_id": "sub", "title": "s", "child_spec_ref": "child-x"}],
    )
    gh = _gh(issue={"5": "CLOSED"})  # the child's only leaf is done
    result = OUTCOME.advance(
        repo,
        "parent",
        dispatcher=OUTCOME.outcome_dispatcher.make_dispatcher(),
        harvester=OUTCOME.production_harvester(repo, github_runner=gh),
    )
    # the child outcome's leaf reads done -> child terminal-successful -> parent's child node unlocks
    assert result.harvested == ["sub"]
