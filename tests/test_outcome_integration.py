"""End-to-end integration gate for the OutcomeOrchestrator (U11).

The per-unit suites pin each unit in isolation; this proves the **whole vertical slice composes** — that
U1–U10 run together through the production `advance` wiring on a real DAG and reach a coherent terminal
state. It drives a 2-layer outcome (a non-code design leaf gated on a closed tracking issue → a code
build leaf gated on a merged PR) through start → approve → dispatch → GitHub-canonical harvest →
auto-merge → cost rollup → report → projection, with a stateful fake `gh` (no network) and a real git
repo for the store + branch spec.

This is the saga-feature-level proof that the OutcomeOrchestrator ships whole (R1–R34 composed), not the
unit-level requirement pins (those live in the per-unit `test_outcome_*` suites).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
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
PROJ = _load("outcome_projection")
_load("outcome_liveness")
C = _load("outcome_costs")


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    # Configure a repo-local identity so EVERY commit — including the ones `commit_spec` makes via the
    # ambient git (not an injected env) — has a committer, even on a CI runner with no global git config.
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo, check=True)
    return repo


class _FakeGitHub:
    """A stateful fake `gh` runner that gates completion on **dispatch** — a leaf's tracking issue/PR
    only resolves once that leaf has a settled dispatch record, so the dispatch seam is load-bearing
    (a leaf can't complete without first being dispatched -> worked). `gh` is never really invoked.
    """

    _REF_SID = {"1": "design", "2": "build"}  # issue 1 -> design; pr 2 -> build

    def __init__(self, store: Any) -> None:
        self.store = store
        self.merged: set[str] = set()

    def _dispatched(self, sid: str) -> bool:
        return sid in ENG._dispatch_records(self.store)

    def __call__(self, args: list[str], **_kw: Any) -> SimpleNamespace:
        a = list(args)
        if a and a[0] == "gh":  # _run_gh invokes the runner with ["gh", *subcommand]
            a = a[1:]
        text = " ".join(a)
        # design's tracking issue closes only AFTER design's leaf is dispatched (R11 non-code contract)
        if a[:2] == ["issue", "view"] and "1" in a:
            closed = self._dispatched("design")
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"state": "CLOSED" if closed else "OPEN"}),
                stderr="",
            )
        # build's PR is mergeable only AFTER build's leaf is dispatched; merged after the squash lands
        if a[:2] == ["pr", "view"] and "2" in a:
            disp = self._dispatched("build")
            if "mergedAt" in text:
                merged = "2" in self.merged
                return SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "state": "MERGED" if merged else "OPEN",
                            "mergedAt": "x" if merged else None,
                        }
                    ),
                    stderr="",
                )
            if "mergeStateStatus" in text:
                return SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps({"mergeStateStatus": "CLEAN" if disp else "BLOCKED"}),
                    stderr="",
                )
            if "baseRefOid" in text:
                return SimpleNamespace(
                    returncode=0, stdout=json.dumps({"baseRefOid": "base-sha"}), stderr=""
                )
            if "headRefOid" in text:
                return SimpleNamespace(
                    returncode=0, stdout=json.dumps({"headRefOid": "head-sha"}), stderr=""
                )
        if a[:2] == ["pr", "merge"] and "2" in a:
            self.merged.add("2")  # the squash lands -> pr 2 now reads merged
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if a[:1] == ["api"]:  # branch_exists probe -> present
            return SimpleNamespace(returncode=0, stdout="refs/heads/x", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="unhandled")


def test_full_outcome_composes_end_to_end(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    ENG.start(
        repo,
        "ship-auth",
        "Ship passwordless auth",
        nodes=[
            {
                "subplot_id": "design",
                "title": "Design",
                "kind": "non-code",
                "github": {"issue": "1"},
            },
            {
                "subplot_id": "build",
                "title": "Build",
                "kind": "code",
                "depends_on": ["design"],
                "github": {"pr": "2", "branch": "feat-build"},
            },
        ],
    )
    store = ENG._store(repo, "ship-auth")

    # U7 approval gate: nothing dispatches until the operator approves the frontier (R20).
    pre = ENG.advance(repo, "ship-auth", gate_factory=lambda s, st: DEC.make_dispatch_gate(st, s))
    assert pre.dispatched == [] and pre.gated == ["design"]
    DEC.approve_frontier(store, ENG.load_spec(repo, "ship-auth"))

    # The leaves report their realized cost (R24) — the coordinator never runs them (R3).
    C.record_cost(
        store, "design", executor="inline", tokens=500, wall_seconds=20, operator_touches=1
    )
    C.record_cost(
        store, "build", executor="team-execution", tokens=1500, wall_seconds=40, retries=1
    )

    gh = _FakeGitHub(store)
    # The full production wiring: dispatch seam + harvest (U5) + auto-merge (U6) + worktree (U7) +
    # liveness (U9) + cost (U10) + the approval gate (U7). Re-approve each revision the cost_processor
    # may bump by materializing the rollup, so the gate stays open across ticks.
    result = None
    all_dispatched: set[str] = set()
    for _ in range(6):
        spec_now = ENG.load_spec(repo, "ship-auth")
        DEC.approve_frontier(
            store, spec_now
        )  # keep the current revision approved (rollup bumps it)
        result = ENG.advance(
            repo,
            "ship-auth",
            dispatcher=D.make_dispatcher(available=SPEC.NODE_BACKENDS),
            harvester=ENG.production_harvester(repo, github_runner=gh),
            merge_processor=ENG.production_merge_processor(github_runner=gh),
            worktree_processor=ENG.production_worktree_processor(repo),
            liveness_processor=ENG.production_liveness_processor(),
            cost_processor=ENG.production_cost_processor(repo),
            gate_factory=lambda s, st: DEC.make_dispatch_gate(st, s),
            available=D.resolve_available(),
            attending=True,
        )
        all_dispatched.update(result.dispatched)
        if result.status.get("complete"):
            break

    assert result is not None and result.status["complete"] is True  # the whole DAG reached done
    # the DISPATCH seam is load-bearing: completion only flowed AFTER each leaf was dispatched (R5).
    assert all_dispatched == {"design", "build"}
    states = result.status["states"]
    assert states == {
        "design": "done",
        "build": "done",
    }  # non-code (closed issue) + code (merged PR)

    # U8 report: derived-on-read, carries the topology + the now-materialized cost rollup (U10).
    report = REP.report_markdown(repo, "ship-auth")
    assert "```mermaid" in report and "Ship passwordless auth" in report
    assert (
        "no data yet" not in report.split("## Cost rollup")[1].split("##")[0]
    )  # cost is populated

    # U10 rollup: the DAG-vs-one-thread proof — critical path 60 (20+40) vs serial 60 -> a pure chain,
    # so beat_one_thread is honestly False (design -> build has no parallelism).
    spec_final = ENG.load_spec(repo, "ship-auth")
    rollup = spec_final.cost_rollup
    assert rollup["tokens"] == 2000 and rollup["operator_touches"] == 1 and rollup["retries"] == 1
    assert rollup["wall_seconds_serial"] == 60 and rollup["wall_seconds_parallel"] == 60
    assert rollup["beat_one_thread"] is False

    # U8 projection: generated, complete, never auto-closes the parent (R25).
    proj = PROJ.project(spec_final, store)
    assert proj["complete"] is True and proj["parent_close"] == "operator-keystroke-only"
    assert proj["progress"] == {"done": 2, "total": 2, "percent": 100}


def test_a_pure_parallel_fan_out_beats_one_thread(tmp_path: Path) -> None:
    # The thesis in the affirmative: two independent code leaves -> critical path < serial -> the DAG wins.
    repo = _repo(tmp_path)
    ENG.start(
        repo,
        "fan",
        "Two independent workstreams",
        nodes=[
            {"subplot_id": "a", "title": "A", "kind": "code"},
            {"subplot_id": "b", "title": "B", "kind": "code"},
        ],
    )
    store = ENG._store(repo, "fan")
    C.record_cost(store, "a", wall_seconds=30)
    C.record_cost(store, "b", wall_seconds=50)
    spec = ENG.load_spec(repo, "fan")
    C.materialize(spec, store)
    assert spec.cost_rollup["wall_seconds_serial"] == 80  # one thread runs both
    assert (
        spec.cost_rollup["wall_seconds_parallel"] == 50
    )  # the longer of the two, run concurrently
    assert spec.cost_rollup["beat_one_thread"] is True


def _checkout(repo: Path, branch: str) -> None:
    subprocess.run(["git", "checkout", "-q", "-b", branch], cwd=repo, check=True)


def test_commit_spec_persists_the_spec_to_the_outcome_branch_for_cross_machine_reentry(
    tmp_path: Path,
) -> None:
    # R26/R27/F5: the spec must be COMMITTED + pushed to the outcome's own branch (not main) so a
    # different machine reconstructs the whole outcome by pulling the repo — no dependence on the cache.
    repo = _repo(tmp_path)
    ENG.start(repo, "ship", "obj", nodes=[{"subplot_id": "a", "title": "A", "kind": "code"}])

    # R26 "not main mid-run": refuse to commit the spec to main/master.
    try:
        ENG.commit_spec(repo, "ship")
        raise AssertionError("expected a refusal to commit on main")
    except ENG.OutcomeError as exc:
        assert "main" in str(exc) and "R26" in str(exc)

    _checkout(repo, "outcome/ship")
    res = ENG.commit_spec(repo, "ship")
    assert res["committed"] is True and res["branch"] == "outcome/ship"
    # idempotent: a second commit with no spec change is a no-op.
    assert ENG.commit_spec(repo, "ship")["committed"] is False

    # the spec is genuinely committed on the branch -> a different machine that pulls reconstructs it.
    log = subprocess.run(
        ["git", "log", "--oneline", "-1", "--", "docs/outcomes/ship/outcome-spec.json"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert log.stdout.strip(), "the outcome spec must be a committed object on the outcome branch"
    # cross-machine: any checkout of the branch reconstructs the outcome from the COMMITTED spec blob
    # alone (no dependence on the local cache, R27) — read the committed blob + reconstruct.
    blob = subprocess.run(
        ["git", "show", "outcome/ship:docs/outcomes/ship/outcome-spec.json"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    reconstructed = SPEC.OutcomeSpec.from_json(blob.stdout)
    assert reconstructed.outcome_id == "ship"
    assert [n.subplot_id for n in reconstructed.nodes] == ["a"]


def test_advance_persist_commits_the_spec_on_the_outcome_branch(tmp_path: Path) -> None:
    # The autonomous-run durability path: `/outcome advance --persist` commits the spec each run, so an
    # unattended loop keeps the outcome branch current (R26/R27).
    repo = _repo(tmp_path)
    ENG.start(repo, "o", "obj", nodes=[{"subplot_id": "a", "title": "A", "kind": "code"}])
    _checkout(repo, "outcome/o")
    store = ENG._store(repo, "o")
    DEC.approve_frontier(store, ENG.load_spec(repo, "o"))
    C.record_cost(store, "a", tokens=10)  # a cost record so the cost_processor mutates the spec
    rc = ENG.main(["--repo-root", str(repo), "advance", "o", "--persist"])
    assert rc == 0
    # the cost-rollup-mutated spec was committed on the outcome branch.
    log = subprocess.run(
        ["git", "log", "--oneline", "-1", "--", "docs/outcomes/o/outcome-spec.json"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert log.stdout.strip()
