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


def test_harvest_attaches_manifest_ref_when_dispatch_manifest_exists(tmp_path: Path) -> None:
    """A harvested leaf whose dispatch recorded a provenance manifest gets the advisory pointer."""
    store = STORE.Store(root=tmp_path / "saga-outcomes" / "o").ensure()
    manifest_dir = tmp_path / "saga-manifests" / "o"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "design.json").write_text("{}", encoding="utf-8")
    spec = _spec(
        [
            {"subplot_id": "design", "title": "d", "kind": "code", "github": {"pr": "1"}},
            {"subplot_id": "bare", "title": "b", "kind": "code", "github": {"pr": "2"}},
        ]
    )
    runner = _gh(pr={"1": "MERGED", "2": "MERGED"})
    harvested = ORCH.harvest(spec, store=store, github_runner=runner)
    assert sorted(harvested) == ["bare", "design"]
    with_manifest = STORE.read_completion_events(store, "design")[0]
    assert with_manifest.payload.get("manifest_ref") == "saga-manifests/o/design.json"
    bare = STORE.read_completion_events(store, "bare")[0]
    assert "manifest_ref" not in bare.payload


# ---------------------------------------------------------------------------
# board_status + issue_close_info — the saga-owned field-class reads (#295 U1/U2)
# ---------------------------------------------------------------------------


def _gh_reads(
    *,
    view: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
    fail: bool = False,
    bad_json: bool = False,
):
    """Fake gh: ``issue view`` returns ``view`` JSON; ``api .../events`` returns ``events`` JSON."""

    def runner(args: list[str], **_kw: Any) -> SimpleNamespace:
        if fail:
            return SimpleNamespace(returncode=1, stdout="", stderr="gh down")
        if bad_json:
            return SimpleNamespace(returncode=0, stdout="{not json", stderr="")
        sub = args[1]  # args = ["gh", <sub>, ...]
        if sub == "api":
            return SimpleNamespace(returncode=0, stdout=json.dumps(events or []), stderr="")
        return SimpleNamespace(returncode=0, stdout=json.dumps(view or {}), stderr="")

    return runner


def test_board_status_happy_path() -> None:
    """The Operations item's Status name is returned for project=operations."""
    view = {
        "projectItems": [
            {"status": {"optionId": "x", "name": "In Progress"}, "title": "Operations"}
        ]
    }
    assert (
        GH.board_status("o/r#5", project="operations", runner=_gh_reads(view=view)) == "In Progress"
    )


def test_board_status_multi_board_reads_only_slug_match() -> None:
    """With two project memberships, only the title-matched project's Status is read."""
    view = {
        "projectItems": [
            {"status": {"name": "Todo"}, "title": "Operations"},
            {"status": {"name": "Active"}, "title": "Asgard"},
        ]
    }
    assert GH.board_status("o/r#5", project="asgard", runner=_gh_reads(view=view)) == "Active"
    assert GH.board_status("o/r#5", project="operations", runner=_gh_reads(view=view)) == "Todo"


def test_board_status_no_matching_project_is_empty() -> None:
    """An issue on no matching project degrades to ""."""
    view = {"projectItems": [{"status": {"name": "Todo"}, "title": "Asgard"}]}
    assert GH.board_status("o/r#5", project="operations", runner=_gh_reads(view=view)) == ""


def test_board_status_degrades_on_failure_bad_json_and_null_status() -> None:
    """gh non-zero, malformed JSON, and a null/absent status all degrade to "" without raising."""
    assert GH.board_status("o/r#5", project="operations", runner=_gh_reads(fail=True)) == ""
    assert GH.board_status("o/r#5", project="operations", runner=_gh_reads(bad_json=True)) == ""
    null_status = {"projectItems": [{"status": None, "title": "Operations"}]}
    assert GH.board_status("o/r#5", project="operations", runner=_gh_reads(view=null_status)) == ""
    no_items: dict[str, Any] = {"projectItems": []}
    assert GH.board_status("o/r#5", project="operations", runner=_gh_reads(view=no_items)) == ""


def test_issue_close_info_completed_with_actor() -> None:
    """A completed close with a discoverable actor returns the full dict."""
    view = {"state": "CLOSED", "stateReason": "COMPLETED"}
    events: list[dict[str, Any]] = [
        {"event": "labeled"},
        {"event": "closed", "actor": {"login": "namredips"}},
    ]
    info = GH.issue_close_info("o/r#5", runner=_gh_reads(view=view, events=events))
    assert info == {"state": "closed", "state_reason": "completed", "closed_by": "namredips"}


def test_issue_close_info_not_planned() -> None:
    """A not_planned close surfaces state_reason=not_planned (the drift signal)."""
    view = {"state": "CLOSED", "stateReason": "NOT_PLANNED"}
    info = GH.issue_close_info("o/r#5", runner=_gh_reads(view=view, events=[]))
    assert info["state"] == "closed"
    assert info["state_reason"] == "not_planned"
    assert info["closed_by"] == ""


def test_issue_close_info_open_skips_events() -> None:
    """An open issue reports open, no reason, empty author — and never reads the events endpoint."""
    view = {"state": "OPEN", "stateReason": None}

    calls: list[str] = []

    def runner(args: list[str], **_kw: Any) -> SimpleNamespace:
        calls.append(args[1])
        return SimpleNamespace(returncode=0, stdout=json.dumps(view), stderr="")

    info = GH.issue_close_info("o/r#5", runner=runner)
    assert info == {"state": "open", "state_reason": "unknown", "closed_by": ""}
    assert "api" not in calls  # events endpoint not consulted for an open issue


def test_issue_close_info_degrades_on_failure() -> None:
    """gh failure / malformed JSON degrade to an all-unknown dict without raising."""
    assert GH.issue_close_info("o/r#5", runner=_gh_reads(fail=True)) == {
        "state": "unknown",
        "state_reason": "unknown",
        "closed_by": "",
    }
    assert GH.issue_close_info("o/r#5", runner=_gh_reads(bad_json=True))["state"] == "unknown"


def test_issue_close_info_last_closed_event_wins_after_pagination() -> None:
    """The LAST closed event (post-concatenation) is the author — reopen/close churn resolves right."""
    view = {"state": "CLOSED", "stateReason": "COMPLETED"}
    events = [
        {"event": "closed", "actor": {"login": "first"}},
        {"event": "reopened", "actor": {"login": "mid"}},
        {"event": "closed", "actor": {"login": "final"}},
    ]
    info = GH.issue_close_info("o/r#5", runner=_gh_reads(view=view, events=events))
    assert info["closed_by"] == "final"


def test_issue_close_info_bare_ref_has_no_author() -> None:
    """A ref without owner/repo can't build the events path → closed_by degrades to "" (still closed)."""
    view = {"state": "CLOSED", "stateReason": "COMPLETED"}
    info = GH.issue_close_info(
        "5", runner=_gh_reads(view=view, events=[{"event": "closed", "actor": {"login": "x"}}])
    )
    assert info["state"] == "closed"
    assert info["closed_by"] == ""
