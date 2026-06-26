"""Tests for the auto-merge queue + GitHub negative terminal states (U6).

Pins R12 (serialized squash-merge, base-freshness rebase-then-reverify, expected-base-SHA guard,
base-churn cap, conflict->work+page), R32 (PR closed-unmerged / deleted branch -> rejected terminal,
out-of-band merge not duplicated), R22 (rejected cascades to its downstream subtree), and R34 (a gh
read failure degrades to a safe value — defers a merge, never performs a wrong one).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
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


GH = _load("outcome_github")
SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
M = _load("outcome_merge")


def _store(tmp_path: Path):
    return STORE.Store(root=tmp_path / "store").ensure()


def _node(sid: str, **kw: Any):
    return SPEC.Node.from_dict({"subplot_id": sid, "title": sid, "kind": "code", **kw})


def _seq(val: Any, default: Any) -> Any:
    """A scriptable adapter field: a list is consumed on successive calls, else a constant."""
    if isinstance(val, list):
        box = {"i": 0}

        def f(*_a: Any) -> Any:
            i = min(box["i"], len(val) - 1)
            box["i"] += 1
            return val[i]

        return f
    fixed = val if val is not None else default
    return lambda *_a: fixed


def _ops(
    *,
    pr_state: Any = "open",
    merge_state: Any = "clean",
    squash: Any = "merged",
    branch: bool = True,
    base_oids: Any = None,
    on_update: list[str] | None = None,
) -> Any:
    base = _seq(base_oids, "A") if base_oids is not None else _seq(None, "A")

    def update(r: str) -> bool:
        if on_update is not None:
            on_update.append(r)
        return True

    return M.MergeOps(
        pr_state=_seq(pr_state, "open"),
        base_oid=base,
        merge_state=_seq(merge_state, "clean"),
        update_branch=update,
        squash_merge=_seq(squash, "merged"),
        branch_exists=lambda _b: branch,
    )


# --------------------------------------------------------------------------- outcome_github write side


def _gh_runner(out: str = "", *, rc: int = 0, err: str = ""):
    return lambda args, **kw: SimpleNamespace(returncode=rc, stdout=out, stderr=err)


def test_base_ref_oid_and_merge_state_degrade_safe() -> None:
    assert GH.base_ref_oid("1", runner=_gh_runner(json.dumps({"baseRefOid": "abc"}))) == "abc"
    assert GH.base_ref_oid("1", runner=_gh_runner(rc=1)) == ""  # gh down -> empty (safe)
    assert (
        GH.merge_state("1", runner=_gh_runner(json.dumps({"mergeStateStatus": "BEHIND"})))
        == "behind"
    )
    assert GH.merge_state("1", runner=_gh_runner(rc=1)) == "unknown"  # safe degrade (R34)


def test_squash_merge_returns_error_not_conflict_on_failure() -> None:
    assert GH.squash_merge("1", runner=_gh_runner()) == "merged"
    # a non-zero exit is NOT necessarily a conflict (could be transient) -> "error" (caller defers)
    assert GH.squash_merge("1", runner=_gh_runner(rc=1)) == "error"


def test_branch_exists_only_a_definite_404_is_gone() -> None:
    assert GH.branch_exists("feat", runner=_gh_runner("refs/heads/feat")) is True
    assert GH.branch_exists("feat", runner=_gh_runner(rc=1, err="HTTP 404: Not Found")) is False
    # a transient gh error (NOT a 404) must NOT falsely declare a live branch gone (degrades present)
    assert GH.branch_exists("feat", runner=_gh_runner(rc=1, err="connection timed out")) is True


# --------------------------------------------------------------------------- auto_merge_one (R12)


def test_clean_squash_merges(tmp_path: Path) -> None:
    out = M.auto_merge_one(_node("build", github={"pr": "1"}), _ops())
    assert out.state == "merged" and out.cycles == 0


def test_behind_base_rebases_then_squashes() -> None:
    updates: list[str] = []
    out = M.auto_merge_one(
        _node("build", github={"pr": "1"}),
        _ops(merge_state=["behind", "clean"], on_update=updates),
    )
    assert out.state == "merged" and out.cycles == 1
    assert updates == ["1"]  # rebased (update-branch) before the squash (R12 base-freshness)


def test_conflict_fails_leaf_back_to_work() -> None:
    out = M.auto_merge_one(_node("build", github={"pr": "1"}), _ops(merge_state="dirty"))
    assert out.state == "conflict" and "work" in out.reason


def test_github_rejected_squash_reloops_then_merges() -> None:
    # GitHub is the atomic guard: a stale-tree/head-moved squash is rejected ("error") -> reloop;
    # the next attempt (base now stable) succeeds. (--match-head-commit makes this GitHub-side.)
    out = M.auto_merge_one(_node("build", github={"pr": "1"}), _ops(squash=["error", "merged"]))
    assert (
        out.state == "merged" and out.cycles == 1
    )  # relooped once on a rejected squash, then merged


def test_base_churn_caps_at_three_then_halts() -> None:
    # GitHub rejects the squash on every attempt (head/base keeps moving) -> reloop -> capped, no spin.
    out = M.auto_merge_one(_node("build", github={"pr": "1"}), _ops(squash="error"))
    assert out.state == "capped" and out.cycles == M.MERGE_CAP  # halt + page, no starvation spin


def test_unreadable_base_defers_never_merges() -> None:
    # base_oid unreadable (gh degraded) -> defer, never squash on an unguardable base (R34).
    out = M.auto_merge_one(_node("build", github={"pr": "1"}), _ops(base_oids=[""]))
    assert out.state == "not-ready"


# --------------------------------------------------------------------------- negative states (R32)


def test_closed_unmerged_pr_is_rejected() -> None:
    out = M.auto_merge_one(_node("build", github={"pr": "1"}), _ops(pr_state="closed"))
    assert out.state == "rejected" and "closed" in out.reason


def test_out_of_band_merge_is_not_duplicated() -> None:
    out = M.auto_merge_one(_node("build", github={"pr": "1"}), _ops(pr_state="merged"))
    assert out.state == "already-merged"  # detected, never a second merge


def test_deleted_branch_is_rejected() -> None:
    out = M.auto_merge_one(_node("build", github={"pr": "1", "branch": "feat"}), _ops(branch=False))
    assert out.state == "rejected" and "branch deleted" in out.reason


def test_gated_risky_destructive_wait_for_operator() -> None:
    for flag in ("gated", "risky", "destructive"):
        out = M.auto_merge_one(_node("build", github={"pr": "1"}, **{flag: True}), _ops())
        assert out.state == "waits-operator"


def test_unknown_merge_state_defers_never_squashes() -> None:
    # merge readiness unknown (gh degraded) -> defer, never squash on an unknown readiness (R34).
    out = M.auto_merge_one(
        _node("build", github={"pr": "1"}), _ops(pr_state="unknown", merge_state="unknown")
    )
    assert out.state == "not-ready"


def test_gh_outage_via_real_adapter_defers_never_fails_leaf(tmp_path: Path) -> None:
    # P1 regression: a TOTAL gh outage through the REAL github_merge_ops must DEFER (not-ready), never
    # record a permanent `failed`/`rejected` terminal (the bug the fake squash='error' had masked).
    def gh_down(args: Any, **kw: Any) -> SimpleNamespace:
        raise OSError("gh unreachable")

    ops = M.github_merge_ops(runner=gh_down)
    out = M.auto_merge_one(_node("build", github={"pr": "1", "branch": "feat"}), ops)
    assert out.state == "not-ready"  # deferred, R34 — never a wrong action on an outage
    store = _store(tmp_path)
    spec = _spec([{"subplot_id": "build", "title": "b", "kind": "code", "github": {"pr": "1"}}])
    M.process_merge_queue(spec, store, ops)
    assert STORE.completed_subplots(store, successful_only=False) == set()  # NO terminal recorded


def test_conflict_then_fixed_leaf_is_retried_not_permanently_skipped(tmp_path: Path) -> None:
    # P2 regression: a conflict records a `failed` terminal, but once /work fixes it the leaf must
    # RE-ENTER the queue — `failed` is retryable, only `rejected`/`stalled` permanently skip.
    store = _store(tmp_path)
    spec = _spec([{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}])
    M.process_merge_queue(spec, store, _ops(merge_state="dirty"))  # conflict -> failed
    assert any(e.state == "failed" for e in STORE.read_completion_events(store, "A"))
    # the conflict is fixed -> a fresh queue run must retry (not skip) and merge it
    result = M.process_merge_queue(spec, store, _ops(merge_state="clean", squash="merged"))
    assert any(o["state"] == "merged" for o in result["outcomes"])  # retried, not stranded


def test_no_pr_ref_not_ready() -> None:
    assert M.auto_merge_one(_node("build"), _ops()).state == "not-ready"


# --------------------------------------------------------------------------- queue + cascade (R22/R32)


def _spec(nodes: list[dict[str, Any]]):
    return SPEC.OutcomeSpec.from_dict({"outcome_id": "o", "objective": "x", "nodes": nodes})


def test_process_queue_rejects_and_cascades_downstream(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec(
        [
            {"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}},
            {
                "subplot_id": "B",
                "title": "B",
                "kind": "code",
                "github": {"pr": "2"},
                "depends_on": ["A"],
            },
            {"subplot_id": "C", "title": "C", "kind": "code", "github": {"pr": "3"}},  # independent
        ]
    )

    # A's PR is closed-unmerged -> rejected; C is clean -> merged. B (downstream of A) cascades.
    def ops_for(_spec: Any) -> Any:
        return None

    # A closed, B/C handled per their own pr — use a per-pr scripted adapter
    pr_states = {"1": "closed", "2": "open", "3": "open"}
    ops = M.MergeOps(
        pr_state=lambda r: pr_states.get(r, "open"),
        base_oid=lambda r: "A",
        merge_state=lambda r: "clean",
        update_branch=lambda r: True,
        squash_merge=lambda r: "merged",
        branch_exists=lambda b: True,
    )
    result = M.process_merge_queue(spec, store, ops)
    assert "A" in result["rejected"]
    assert result["cascade_paused"] == [
        "B"
    ]  # only A's downstream pauses; C is independent + merged
    # A's rejected terminal is recorded (negative terminal, R32)
    assert any(e.state == "rejected" for e in STORE.read_completion_events(store, "A"))
    # re-processing is idempotent (no duplicate rejected event)
    M.process_merge_queue(spec, store, ops)
    assert sum(e.state == "rejected" for e in STORE.read_completion_events(store, "A")) == 1


def test_process_queue_records_conflict_as_failed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec([{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}])
    ops = _ops(merge_state="dirty")
    M.process_merge_queue(spec, store, ops)
    # a conflict fails the leaf back to work — a NON-success terminal (does not unlock dependents)
    events = STORE.read_completion_events(store, "A")
    assert any(e.state == "failed" for e in events)
    assert STORE.completed_subplots(store, successful_only=True) == set()  # not a success


def test_a_code_leaf_with_an_incomplete_upstream_is_not_merged(tmp_path: Path) -> None:
    # U11 regression: a coincidentally-clean PR must NOT squash while its declared upstream is incomplete
    # (GitHub does not model the DAG — especially a non-code upstream produces no base-blocking merge).
    store = _store(tmp_path)
    spec = _spec(
        [
            {
                "subplot_id": "design",
                "title": "design",
                "kind": "non-code",
                "github": {"issue": "9"},
            },
            {
                "subplot_id": "build",
                "title": "build",
                "kind": "code",
                "github": {"pr": "1"},
                "depends_on": ["design"],
            },
        ]
    )
    # build's PR is perfectly clean, but design (its upstream) is not done -> build must NOT merge.
    result = M.process_merge_queue(spec, store, _ops(merge_state="clean", squash="merged"))
    assert all(o["state"] != "merged" for o in result["outcomes"])  # nothing merged out of order
    # once design completes, build is eligible and merges.
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="design", state="done", idempotency_key="k:design")
    )
    result2 = M.process_merge_queue(spec, store, _ops(merge_state="clean", squash="merged"))
    assert any(o["subplot_id"] == "build" and o["state"] == "merged" for o in result2["outcomes"])


def test_cli_describes_policy(capsys: Any) -> None:
    assert M.main(["--cap", "5"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["merge_cap"] == 5 and "squash" in out["policy"]
