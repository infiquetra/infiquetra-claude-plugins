"""Tests for decomposition, in-flight graph editing, and orphan reconciliation (U7).

Pins R20 (draft-then-review: no layer dispatches before the operator approves the current frontier;
a graph edit re-closes the gate), R21 (the four growth mechanisms: add/prune, lazy-grow,
elaborate-in-place, promote), and R33 (in-flight edit rules: a dispatched node needs a terminal
transition before prune/elaborate; pruning reconciles orphans — closes the sub-issue, reaps the
worktree, drops edges; every edit is atomic — a rejected edit leaves the spec untouched).
"""

from __future__ import annotations

import importlib.util
import json
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
ENG = _load("outcome")
WT = _load("outcome_worktrees")
DEC = _load("outcome_decompose")


def _store(tmp_path: Path) -> Any:
    return STORE.Store(root=tmp_path / "store").ensure()


def _spec(nodes: list[dict[str, Any]] | None = None) -> Any:
    nodes = (
        nodes
        if nodes is not None
        else [
            {"subplot_id": "a", "title": "a", "kind": "non-code"},
            {"subplot_id": "b", "title": "b", "kind": "code", "depends_on": ["a"]},
        ]
    )
    return SPEC.OutcomeSpec.from_dict({"outcome_id": "o", "objective": "x", "nodes": nodes})


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


def _closer(sink: list[str]) -> Any:
    """A recording ``issue_close`` adapter: records the closed ref and reports success."""

    def close(ref: str) -> bool:
        sink.append(ref)
        return True

    return close


class _PathOps:
    """A fake WorktreeOps over an in-memory path set (mypy-clean methods, no side-effect lambdas)."""

    def __init__(self, paths: set[str]) -> None:
        self.paths = paths

    def add(self, path: str, _branch: str) -> bool:
        self.paths.add(path)
        return True

    def remove(self, path: str) -> bool:
        self.paths.discard(path)
        return True

    def exists(self, path: str) -> bool:
        return path in self.paths

    def ops(self) -> Any:
        return WT.WorktreeOps(
            add=self.add,
            remove=self.remove,
            exists=self.exists,
            list_paths=lambda: sorted(self.paths),
        )


# --------------------------------------------------------------------------- node + edge edits


def test_add_node_bumps_revision_and_validates() -> None:
    spec = _spec()
    rev = spec.spec_revision
    new = DEC.add_node(spec, {"subplot_id": "c", "title": "c", "kind": "code", "depends_on": ["a"]})
    assert new == rev + 1 and spec.node_by_id("c") is not None


def test_add_node_rejecting_a_dangling_edge_is_atomic() -> None:
    spec = _spec()
    rev = spec.spec_revision
    try:
        DEC.add_node(spec, {"subplot_id": "c", "title": "c", "depends_on": ["nope"]})
        raise AssertionError("expected a rejection")
    except SPEC.OutcomeSpecError:
        pass
    assert spec.node_by_id("c") is None and spec.spec_revision == rev  # untouched


def test_add_and_remove_dependency() -> None:
    spec = _spec(
        [
            {"subplot_id": "a", "title": "a", "kind": "code"},
            {"subplot_id": "b", "title": "b", "kind": "code"},
        ]
    )
    DEC.add_dependency(spec, "b", "a")
    assert "a" in spec.node_by_id("b").depends_on
    DEC.remove_dependency(spec, "b", "a")
    assert "a" not in spec.node_by_id("b").depends_on


def test_add_dependency_that_would_cycle_is_rejected_atomically() -> None:
    spec = _spec()  # b depends on a
    rev = spec.spec_revision
    try:
        DEC.add_dependency(spec, "a", "b")  # a->b plus b->a = cycle
        raise AssertionError("expected a cycle rejection")
    except SPEC.OutcomeSpecError:
        pass
    assert spec.node_by_id("a").depends_on == [] and spec.spec_revision == rev


# --------------------------------------------------------------------------- lazy-grow (R21)


def test_lazy_grow_appends_a_later_layer() -> None:
    spec = _spec()
    DEC.lazy_grow(
        spec,
        [
            {"subplot_id": "c", "title": "c", "kind": "code", "depends_on": ["b"]},
            {"subplot_id": "d", "title": "d", "kind": "code", "depends_on": ["c"]},
        ],
    )
    assert [n.subplot_id for n in spec.nodes] == ["a", "b", "c", "d"]


def test_lazy_grow_is_all_or_nothing() -> None:
    spec = _spec()
    rev = spec.spec_revision
    try:
        DEC.lazy_grow(
            spec,
            [
                {"subplot_id": "c", "title": "c", "depends_on": ["b"]},
                {
                    "subplot_id": "d",
                    "title": "d",
                    "depends_on": ["nope"],
                },  # dangling -> whole batch rolls back
            ],
        )
        raise AssertionError("expected a rejection")
    except SPEC.OutcomeSpecError:
        pass
    assert (
        spec.node_by_id("c") is None and spec.node_by_id("d") is None and spec.spec_revision == rev
    )


# --------------------------------------------------------------------------- elaborate-in-place (R21/R33)


def test_elaborate_splices_subnodes_inheriting_upstream_and_rewiring_dependents(
    tmp_path: Path,
) -> None:
    # a -> b -> c ; elaborate b into b1->b2. b1 inherits b's upstream [a]; c rewires onto sink b2.
    spec = _spec(
        [
            {"subplot_id": "a", "title": "a", "kind": "code"},
            {"subplot_id": "b", "title": "b", "kind": "code", "depends_on": ["a"]},
            {"subplot_id": "c", "title": "c", "kind": "code", "depends_on": ["b"]},
        ]
    )
    store = _store(tmp_path)
    DEC.elaborate(
        spec,
        store,
        "b",
        [
            {"subplot_id": "b1", "title": "b1", "kind": "code"},
            {"subplot_id": "b2", "title": "b2", "kind": "code", "depends_on": ["b1"]},
        ],
    )
    assert spec.node_by_id("b") is None
    assert spec.node_by_id("b1").depends_on == ["a"]  # entry inherited b's upstream
    assert spec.node_by_id("c").depends_on == ["b2"]  # dependent rewired onto the sink
    spec.validate()  # still a valid DAG


def test_elaborate_dedups_an_inherited_upstream_edge(tmp_path: Path) -> None:
    # P3 regression: an entry sub-node that re-declares the elaborated node's own upstream must NOT get
    # a doubled edge.
    spec = _spec(
        [
            {"subplot_id": "a", "title": "a", "kind": "code"},
            {"subplot_id": "b", "title": "b", "kind": "code", "depends_on": ["a"]},
        ]
    )
    store = _store(tmp_path)
    DEC.elaborate(
        spec, store, "b", [{"subplot_id": "b1", "title": "b1", "kind": "code", "depends_on": ["a"]}]
    )
    assert spec.node_by_id("b1").depends_on == ["a"]  # not ["a", "a"]


def test_elaborate_a_terminal_node_gives_a_distinct_message(tmp_path: Path) -> None:
    # P3 regression: the rejection message for an already-terminal node must not nonsensically say
    # "transition it to terminal first".
    spec = _spec()
    store = _store(tmp_path)
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="b", state="done", idempotency_key="k:b")
    )
    try:
        DEC.elaborate(spec, store, "b", [{"subplot_id": "b1", "title": "b1", "kind": "code"}])
        raise AssertionError("expected a terminal rejection")
    except DEC.DecomposeError as exc:
        assert "already" in str(exc) and "lazy_grow" in str(exc)


def test_elaborate_a_dispatched_node_is_rejected(tmp_path: Path) -> None:
    # R33: an in-flight node cannot be elaborated (would discard its work) -> terminal first.
    spec = _spec()
    store = _store(tmp_path)
    _dispatched(store, "b")
    rev = spec.spec_revision
    try:
        DEC.elaborate(spec, store, "b", [{"subplot_id": "b1", "title": "b1", "kind": "code"}])
        raise AssertionError("expected an in-flight rejection")
    except DEC.DecomposeError:
        pass
    assert spec.node_by_id("b") is not None and spec.spec_revision == rev  # untouched


# --------------------------------------------------------------------------- promote (R21)


def test_promote_sets_child_spec_ref() -> None:
    spec = _spec()
    DEC.promote(spec, "b", "child-b")
    assert spec.node_by_id("b").is_outcome and spec.node_by_id("b").child_spec_ref == "child-b"


def test_promote_to_an_ancestor_is_a_cross_spec_cycle_rejected() -> None:
    spec = _spec()  # outcome_id == "o"
    rev = spec.spec_revision
    for bad in ("o", "grandparent"):
        try:
            DEC.promote(spec, "b", bad, ancestors=("grandparent", "parent"))
            raise AssertionError(f"expected rejection for {bad}")
        except DEC.DecomposeError:
            pass
    assert spec.node_by_id("b").child_spec_ref == "" and spec.spec_revision == rev


# --------------------------------------------------------------------------- prune + orphan reconcile (R33)


def test_prune_undispatched_drops_node_and_edges(tmp_path: Path) -> None:
    spec = _spec(
        [
            {"subplot_id": "a", "title": "a", "kind": "code"},
            {"subplot_id": "b", "title": "b", "kind": "code", "depends_on": ["a"]},
        ]
    )
    store = _store(tmp_path)
    summary = DEC.prune(spec, store, "a")
    assert spec.node_by_id("a") is None
    assert spec.node_by_id("b").depends_on == []  # the edge to the pruned node was dropped
    assert summary["dependents_orphaned"] == ["b"]


def test_prune_a_dispatched_node_is_rejected(tmp_path: Path) -> None:
    # R33: a dispatched (in-flight) node needs a terminal transition before it can be pruned.
    spec = _spec()
    store = _store(tmp_path)
    _dispatched(store, "b")
    rev = spec.spec_revision
    try:
        DEC.prune(spec, store, "b")
        raise AssertionError("expected an in-flight rejection")
    except DEC.DecomposeError:
        pass
    assert spec.node_by_id("b") is not None and spec.spec_revision == rev


def test_prune_the_last_node_is_rejected_atomically(tmp_path: Path) -> None:
    # pruning the only node would empty the spec (invalid) -> the atomic prune rejects + rolls back.
    spec = _spec([{"subplot_id": "only", "title": "only", "kind": "code"}])
    store = _store(tmp_path)
    rev = spec.spec_revision
    try:
        DEC.prune(spec, store, "only")
        raise AssertionError("expected a rejection")
    except SPEC.OutcomeSpecError:
        pass
    assert spec.node_by_id("only") is not None and spec.spec_revision == rev


def test_prune_a_terminal_node_is_allowed(tmp_path: Path) -> None:
    spec = _spec()
    store = _store(tmp_path)
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="b", state="done", idempotency_key="k:b")
    )
    DEC.prune(spec, store, "b")  # terminal -> prunable
    assert spec.node_by_id("b") is None


def test_prune_reconciles_orphans_closes_issue_and_reaps_worktree(tmp_path: Path) -> None:
    spec = _spec(
        [
            {"subplot_id": "keep", "title": "keep", "kind": "code"},
            {
                "subplot_id": "s",
                "title": "s",
                "kind": "code",
                "child_spec_ref": "child-s",
                "github": {"issue": "42"},
            },
        ]
    )
    store = _store(tmp_path)
    # give s a registered worktree so prune reaps it
    ops = _PathOps({str(WT.worktree_path(tmp_path, "o", "s"))}).ops()
    WT.register(
        store,
        "s",
        {"path": str(WT.worktree_path(tmp_path, "o", "s")), "branch": "x", "owner": "me"},
    )
    closed: list[str] = []
    summary = DEC.prune(spec, store, "s", issue_close=_closer(closed), worktree_ops=ops)
    assert closed == ["42"] and summary["closed_issue"] == "42"  # generated sub-issue closed (R33)
    assert summary["reaped_worktree"] is True and "s" not in WT.read_registry(
        store
    )  # worktree reaped


def test_prune_rejected_does_not_close_issue() -> None:
    # the side-effecting reconcile must run only AFTER the canonical prune commits — a rejected prune
    # (in-flight) must never close a live issue.
    import tempfile

    spec = _spec([{"subplot_id": "s", "title": "s", "kind": "code", "github": {"issue": "42"}}])
    store = STORE.Store(root=Path(tempfile.mkdtemp()) / "s").ensure()
    _dispatched(store, "s")
    closed: list[str] = []
    try:
        DEC.prune(spec, store, "s", issue_close=_closer(closed))
        raise AssertionError("expected rejection")
    except DEC.DecomposeError:
        pass
    assert (
        closed == [] and spec.node_by_id("s") is not None
    )  # no orphan side effect on a rejected edit


# --------------------------------------------------------------------------- approval gate (R20)


def test_frontier_not_approved_by_default(tmp_path: Path) -> None:
    spec = _spec()
    store = _store(tmp_path)
    assert DEC.frontier_approved(store, spec.spec_revision) is False
    gate = DEC.make_dispatch_gate(store, spec)
    assert gate("a") is False  # nothing dispatches before approval (R20)


def test_approval_is_per_revision_and_reclosed_by_an_edit(tmp_path: Path) -> None:
    spec = _spec()
    store = _store(tmp_path)
    DEC.approve_frontier(store, spec)
    assert DEC.make_dispatch_gate(store, spec)("a") is True
    # a structural edit bumps the revision -> the gate re-closes until re-approved (R20 <-> R33)
    DEC.add_node(spec, {"subplot_id": "c", "title": "c", "kind": "code"})
    assert DEC.make_dispatch_gate(store, spec)("a") is False
    DEC.approve_frontier(store, spec)
    assert DEC.make_dispatch_gate(store, spec)("a") is True


def test_approve_is_idempotent(tmp_path: Path) -> None:
    spec = _spec()
    store = _store(tmp_path)
    assert (
        DEC.approve_frontier(store, spec) == DEC.approve_frontier(store, spec) == spec.spec_revision
    )


# --------------------------------------------------------------------------- advance integration (R20)


def test_advance_holds_back_the_frontier_until_approved(tmp_path: Path) -> None:
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
    ENG.start(
        repo,
        "demo",
        "ship",
        nodes=[{"subplot_id": "design", "title": "Design", "kind": "non-code"}],
    )

    gate_factory = lambda spec, store: DEC.make_dispatch_gate(store, spec)  # noqa: E731
    r1 = ENG.advance(repo, "demo", gate_factory=gate_factory)
    assert r1.dispatched == [] and r1.gated == ["design"]  # held back (R20)

    spec = ENG.load_spec(repo, "demo")
    store = ENG._store(repo, "demo")
    DEC.approve_frontier(store, spec)
    r2 = ENG.advance(repo, "demo", gate_factory=gate_factory)
    assert r2.dispatched == ["design"] and r2.gated == []  # approved -> dispatches


def test_cli_describes_policy(capsys: Any) -> None:
    assert DEC.main([]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "elaborate-in-place" in out["mechanisms"] and "approval" in out
