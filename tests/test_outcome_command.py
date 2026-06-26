"""Tests for the /outcome reconcile engine (U3).

Pins the U3 plan scenarios and the two load-bearing invariants:

* R3 — the coordinator DISPATCHES but never runs a leaf's work in the advance process;
* R17/R29 — status is derived on read (never a stored field) and reconstructs from the canonical
  spec even with the cache deleted; the reconcile loop is level-triggered + idempotent.

The store resolves under a (monkeypatched) git common dir so the whole engine is exercised offline
with no real git repo; repo_root is a tmp dir that holds the branch-local spec.
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


M = _load("outcome")
SPEC = _load("outcome_spec")
STORE = _load("outcome_store")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp repo_root whose git common dir resolves to tmp_path/.git (monkeypatched, no real git)."""
    common = tmp_path / ".git"
    common.mkdir()

    def fake_run(args: list[str], **_kw: Any) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout=str(common) + "\n", stderr="")

    monkeypatch.setattr(M.outcome_store.subprocess, "run", fake_run)
    return tmp_path


def _recorder():
    calls: list[str] = []

    def dispatcher(req: Any) -> str:
        calls.append(req.subplot_id)
        return f"leaf-{req.subplot_id}"

    return dispatcher, calls


# --------------------------------------------------------------------------- start / status


def test_start_creates_branch_local_spec_and_two_node_dag(repo: Path) -> None:
    spec = M.start(repo, "ship-x", "Ship feature X")
    path = M.spec_path(repo, "ship-x")
    assert path.exists()
    assert [n.subplot_id for n in spec.nodes] == ["design", "build"]
    # the branch-local spec round-trips and is canonical structure
    on_disk = SPEC.OutcomeSpec.from_json(path.read_text())
    assert on_disk.outcome_id == "ship-x"


def test_start_twice_is_rejected(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    with pytest.raises(M.OutcomeError, match="already started"):
        M.start(repo, "ship-x", "Ship feature X")


def test_status_is_derived_not_stored(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    # nothing done yet -> design is the frontier, build is blocked
    st = M.status(repo, "ship-x")
    assert st["states"] == {"design": "ready", "build": "blocked"}
    assert st["frontier"] == ["design"]
    # the canonical spec has NO stored status field — status is computed from spec + store
    assert (
        "status"
        not in SPEC.OutcomeSpec.from_dict(
            {"outcome_id": "o", "objective": "x", "nodes": [{"subplot_id": "a", "title": "a"}]}
        ).to_dict()
    )
    # writing a completion event (no advance, no status write) flips the derived state
    store = STORE.Store.for_outcome("ship-x", repo)
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="design", state="done", idempotency_key="kd")
    )
    st2 = M.status(repo, "ship-x")
    assert st2["states"]["design"] == "done" and st2["states"]["build"] == "ready"


# --------------------------------------------------------------------------- advance (R3 + idempotency)


def test_advance_dispatches_frontier_but_never_runs_leaf_work(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    dispatcher, calls = _recorder()
    result = M.advance(repo, "ship-x", dispatcher=dispatcher)
    # the coordinator DISPATCHED design (the frontier)...
    assert result.dispatched == ["design"]
    assert calls == ["design"]  # dispatcher called exactly once, for the frontier leaf
    # ...but did NOT run/complete it: design is 'dispatched', not 'done', and there is NO
    # completion event (the coordinator never fabricates a leaf's completion — R3).
    st = M.status(repo, "ship-x")
    assert st["states"]["design"] == "dispatched"
    assert st["states"]["build"] == "blocked"
    store = STORE.Store.for_outcome("ship-x", repo)
    assert STORE.completed_subplots(store) == set()  # no leaf body ran -> nothing completed


def test_advance_is_idempotent_no_duplicate_dispatch(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    dispatcher, calls = _recorder()
    first = M.advance(repo, "ship-x", dispatcher=dispatcher)
    second = M.advance(repo, "ship-x", dispatcher=dispatcher)
    assert first.dispatched == ["design"]
    assert second.dispatched == []  # already dispatched -> no re-dispatch
    assert calls == ["design"]  # dispatcher NOT called again
    store = STORE.Store.for_outcome("ship-x", repo)
    # one settled dispatch (commit) for design, never two
    commits = [
        r
        for r in STORE.read_ledger(store)
        if r.get("kind") == "dispatch" and r.get("phase") == "commit"
    ]
    assert len(commits) == 1


def test_concurrent_reentrant_advance_does_not_double_dispatch(repo: Path) -> None:
    # Model a second concurrent tick by re-entering advance() from inside the dispatcher. With a
    # per-invocation unique holder, the nested advance is a DIFFERENT holder -> it no-ops on the
    # held coordinator lease, so design is dispatched exactly ONCE (not twice).
    M.start(repo, "ship-x", "Ship feature X")
    calls: list[str] = []

    def reentrant(req: Any) -> str:
        calls.append(req.subplot_id)
        if len(calls) == 1:  # re-enter once, mid-dispatch, as a "concurrent" tick
            M.advance(repo, "ship-x", dispatcher=reentrant)
        return f"leaf-{req.subplot_id}"

    M.advance(repo, "ship-x", dispatcher=reentrant)
    assert calls == ["design"]  # the nested advance no-op'd on the held lease -> single dispatch
    store = STORE.Store.for_outcome("ship-x", repo)
    commits = [
        r
        for r in STORE.read_ledger(store)
        if r.get("kind") == "dispatch" and r.get("phase") == "commit"
    ]
    assert len(commits) == 1


def test_negative_terminal_leaf_shows_failed_not_dispatched(repo: Path) -> None:
    # A dispatched leaf that reaches a NEGATIVE terminal must render as its actual terminal state,
    # not stay masked as "dispatched" (a dead leaf must not look in-flight).
    M.start(repo, "ship-x", "Ship feature X")
    M.advance(repo, "ship-x")  # dispatch design
    store = STORE.Store.for_outcome("ship-x", repo)
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="design", state="failed", idempotency_key="kf")
    )
    st = M.status(repo, "ship-x")
    assert st["states"]["design"] == "failed"  # surfaced, not "dispatched"


def test_advance_unlocks_next_layer_after_completion(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    M.advance(repo, "ship-x")  # dispatch design
    store = STORE.Store.for_outcome("ship-x", repo)
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="design", state="done", idempotency_key="kd")
    )
    result = M.advance(repo, "ship-x")  # now build is ready
    assert result.dispatched == ["build"]


def test_advance_loop_runs_until_quiescent(repo: Path) -> None:
    # With a dispatcher that immediately records completion, --loop should dispatch the whole chain.
    M.start(repo, "ship-x", "Ship feature X")
    store = STORE.Store.for_outcome("ship-x", repo).ensure()

    def auto_complete(req: Any) -> str:
        leaf = f"leaf-{req.subplot_id}"
        STORE.write_completion_event(
            store,
            STORE.CompletionEvent(subplot_id=req.subplot_id, state="done", idempotency_key=leaf),
        )
        return leaf

    result = M.advance(repo, "ship-x", loop=True, dispatcher=auto_complete)
    assert sorted(result.dispatched) == ["build", "design"]
    assert result.status["complete"] is True


def test_second_concurrent_advance_noops_on_held_lease(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    store = STORE.Store.for_outcome("ship-x", repo).ensure()
    # an external holder grabs the coordinator lease with a long TTL
    assert STORE.acquire_coordinator(store, "other", ttl_seconds=10_000) is True
    result = M.advance(repo, "ship-x")
    assert result.skipped_busy is True and result.dispatched == []


# --------------------------------------------------------------------------- attend (R16 handoff)


def test_attend_prints_native_resume_handoff(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    M.advance(repo, "ship-x", dispatcher=lambda req: f"leaf-saga-{req.subplot_id}")
    assert M.attend(repo, "ship-x", "design") == "/resume leaf-saga-design"


def test_attend_undispatched_leaf_errors(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    with pytest.raises(M.OutcomeError, match="not dispatched"):
        M.attend(repo, "ship-x", "design")


# --------------------------------------------------------------------------- resume / cache loss


def test_resume_reconstructs_with_cache_deleted(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    M.advance(repo, "ship-x")  # dispatch design (record lives in the cache)
    store = STORE.Store.for_outcome("ship-x", repo)
    shutil.rmtree(store.root)  # wipe the cache (e.g. `git worktree remove`)
    # the canonical spec on the branch survives -> resume reconstructs structure with no crash;
    # the cache-resident dispatch record is gone, so design is back on the frontier (recomputed).
    st = M.resume(repo, "ship-x")
    assert st["outcome_id"] == "ship-x"
    assert st["states"] == {"design": "ready", "build": "blocked"}
    assert st["frontier"] == ["design"]


# --------------------------------------------------------------------------- export / import (R14)


def test_export_import_roundtrips_across_repos(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    M.advance(repo, "ship-x")  # dispatch design (creates dispatch ledger records)
    store = STORE.Store.for_outcome("ship-x", repo)
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="design", state="done", idempotency_key="kd")
    )
    M.advance(repo, "ship-x")  # design done -> dispatch build
    bundle = M.export_bundle(repo, "ship-x")
    assert bundle["schema"] == "outcome-bundle/1"
    assert any(e["subplot_id"] == "design" for e in bundle["completion_events"])
    assert any(r.get("subplot_id") == "build" for r in bundle["dispatch_ledger"])

    # import into a DIFFERENT repo (fresh common dir)
    dest = tmp_path / "dest"
    dest.mkdir()
    common2 = dest / ".git"
    common2.mkdir()
    monkeypatch.setattr(
        M.outcome_store.subprocess,
        "run",
        lambda args, **kw: SimpleNamespace(returncode=0, stdout=str(common2) + "\n", stderr=""),
    )
    spec = M.import_bundle(dest, bundle)
    assert spec.outcome_id == "ship-x"
    # completion + dispatch replayed -> design done, build dispatched (same derived status)
    st = M.status(dest, "ship-x")
    assert st["states"]["design"] == "done" and st["states"]["build"] == "dispatched"

    # re-import is idempotent: the dispatch ledger does not grow on a second import
    dest_store = STORE.Store.for_outcome("ship-x", dest)
    ledger_before = len(STORE.read_ledger(dest_store))
    M.import_bundle(dest, bundle)
    assert len(STORE.read_ledger(dest_store)) == ledger_before


# --------------------------------------------------------------------------- graph + CLI


def test_graph_mermaid_renders_nodes_edges_states(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    g = M.graph_mermaid(repo, "ship-x")
    assert g.startswith("flowchart TD")
    assert "design --> build" in g
    assert "design: ready" in g


def test_cli_start_advance_status(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert M.main(["--repo-root", str(repo), "start", "ship-x", "Ship feature X"]) == 0
    capsys.readouterr()
    # R20: nothing dispatches before the operator approves the current frontier.
    assert M.main(["--repo-root", str(repo), "advance", "ship-x"]) == 0
    gated = json.loads(capsys.readouterr().out)
    assert gated["dispatched"] == [] and gated["gated"] == ["design"]
    # approve, then advance -> the frontier dispatches.
    assert M.main(["--repo-root", str(repo), "approve", "ship-x"]) == 0
    capsys.readouterr()
    assert M.main(["--repo-root", str(repo), "advance", "ship-x"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dispatched"] == ["design"]
    assert M.main(["--repo-root", str(repo), "status", "ship-x"]) == 0
    st = json.loads(capsys.readouterr().out)
    assert st["states"]["design"] == "dispatched"


def test_cli_missing_outcome_errors(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = M.main(["--repo-root", str(repo), "status", "nope"])
    assert rc == 1
    err = json.loads(capsys.readouterr().err)
    assert err["ok"] is False
