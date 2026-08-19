"""`clean --merged` once destroyed live work; these tests stand on that grave.

`landed` used to answer with two values, and "zero commits ahead of the run branch" meant landed
-- which is also exactly what a unit that has not committed yet looks like. `clean --merged` never
asked the unit's status, so it closed the tabs and removed the worktrees of two builds and two
reviews that were still working, and took about thirty-five minutes of work with them.

The corrected rule: a unit is reapable only when it is DONE and its commits are on the run
branch. `land --clean` reaps exactly that rule's units after a successful land, and nothing short
of an explicit `clean --branches` ever deletes a branch.

Same class, second verse: ``produced_anything`` measured from the run's ORIGINAL base, so a unit
created after the first land counted as productive the moment it existed -- the branch it was cut
from already carried the landed work. After a land, ``check`` could never say NO COMMITS again,
its LOOKS DONE fired on any post-land unit merely idle between turns, and ``go``'s dependency gate
could never catch an empty dependency. It now measures the unit's OWN commits: from the merge
base of the run branch and the unit's branch, plus the --no-ff merge that landed them.

Same class, third verse: a run predating the run branch landed its units straight onto the
operator's tree, and ``landed_by_merge`` refused to read that shape without a run branch -- so
a legacy unit whose work WAS merged read as produced nothing: ``check`` shouted NO COMMITS at
landed work, and ``clean --merged`` would not reap it. The second-parent shape is just as
readable on HEAD; but the fix is the shape, not a blanket yes -- a legacy branch that never
committed is still nothing to land.

Same class, fourth verse: ``land --clean`` reaped every unit the rule allowed, not only the
units its own invocation merged -- so a land that merged nothing still swept away work an
earlier invocation deliberately kept. Reaping is now a consequence of what THIS land did; the
operator's own ``clean --merged`` remains the deliberate whole-run sweep.

Same class, fifth verse: recording where a unit branch began did not prove it authored a later
tip. An empty unit could merge an advanced run branch and inherit the same ancestry as real work.
Only a no-fast-forward merge onto the run branch records enough shape to call the unit landed.

Everything here runs against a real temporary git repository. Merging and reaping are the
behaviour under test, so a fake that reports them proves nothing.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "orchestrate"
    / "skills"
    / "orchestrate"
    / "scripts"
    / "orchestrate.py"
)


@pytest.fixture(scope="module")
def orchestrate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_orchestrate_land_clean", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _git_out(cwd: Path, *args: str) -> str:
    got = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return got.stdout.strip()


def _commit(cwd: Path, name: str) -> None:
    (cwd / name).write_text(name + "\n")
    _git(cwd, "add", name)
    _git(cwd, "commit", "-m", f"add {name}")


def _branch_exists(repo: Path, branch: str) -> bool:
    got = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", branch], cwd=repo, capture_output=True
    )
    return got.returncode == 0


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A main branch, one base commit, and a run branch sitting at that base."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "test@example.com")
    _git(r, "config", "user.name", "Test")
    _commit(r, "base.txt")
    _git(r, "branch", "orch/r1")
    return r


def _worktree(repo: Path, name: str) -> Path:
    """Cut a unit branch at the run branch's tip and give it a worktree, as `go` would."""
    path = repo.parent / f"orch-{name}"
    _git(repo, "worktree", "add", str(path), "-b", f"orch/r1-{name}", "orch/r1")
    return path


def _write_run(repo: Path, units: list[dict[str, Any]]) -> None:
    base = subprocess.run(
        ["git", "rev-parse", "main"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    payload = {
        "run_id": "r1",
        "source": "a test",
        "base": base,
        "branch": "orch/r1",
        "units": units,
    }
    path = repo / ".orchestrate" / "run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _unit_row(name: str, worktree: Path | None, status: str, **over: Any) -> dict[str, Any]:
    return {
        "name": name,
        "vendor": "claude",
        "task": "x",
        "branch": f"orch/r1-{name}",
        "worktree": str(worktree) if worktree else None,
        "status": status,
        **over,
    }


def _clean_args(**over: bool) -> argparse.Namespace:
    kwargs = {"merged": False, "branches": False, "all": False}
    kwargs.update(over)
    return argparse.Namespace(**kwargs)


def _land_sibling(repo: Path) -> None:
    """Land one unit's commit on the run branch, so branches cut afterwards are post-land.

    That is the shape the old measurement got wrong: everything cut from the run branch after
    this point inherits alpha's landed work.
    """
    _git(repo, "checkout", "-b", "orch/r1-alpha", "orch/r1")
    _commit(repo, "alpha.txt")
    _git(repo, "checkout", "orch/r1")
    _git(repo, "merge", "--no-ff", "--no-edit", "orch/r1-alpha")
    _git(repo, "checkout", "main")


def _legacy_worktree(repo: Path, name: str) -> Path:
    """Cut a unit branch from the operator's tree, as a run predating the run branch did."""
    path = repo.parent / f"orch-{name}"
    _git(repo, "worktree", "add", str(path), "-b", f"orch/r1-{name}", "main")
    return path


def _write_legacy_run(repo: Path, units: list[dict[str, Any]], *, base: str | None = None) -> None:
    """A run record from before the run branch existed: no ``branch`` key at all.

    ``base`` defaults to main's tip at call time -- record it before the merge, as a real run
    records it at start. Pass ``""`` for a record that has no base either.
    """
    if base is None:
        base = subprocess.run(
            ["git", "rev-parse", "main"], cwd=repo, check=True, capture_output=True, text=True
        ).stdout.strip()
    payload = {
        "run_id": "r1",
        "source": "a legacy test",
        "base": base,
        "units": units,
    }
    path = repo / ".orchestrate" / "run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _fake_agents(
    orchestrate: ModuleType, monkeypatch: pytest.MonkeyPatch, states: dict[str, str]
) -> None:
    """Stand in for herdr's session list, as the drift tests do: one agent per name, at the
    given ``agent_status``. The machine running these tests may or may not have a herdr, and its
    sessions are never these units', so ``check`` is answered from a list built here instead.
    """
    agents = [{"name": name, "agent_status": status} for name, status in states.items()]
    monkeypatch.setattr(orchestrate, "live_agents", lambda: agents)


class TestLandedHasThreeAnswers:
    """True = landed, False = unlanded commits, None = nothing to land. None is not True."""

    def test_a_branch_whose_commits_are_all_on_the_run_branch_is_landed(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wt = _worktree(repo, "alpha")
        _commit(wt, "alpha.txt")
        _git(repo, "checkout", "orch/r1")
        _git(repo, "merge", "--no-ff", "--no-edit", "orch/r1-alpha")
        _git(repo, "checkout", "main")
        _write_run(repo, [_unit_row("alpha", wt, "done")])
        monkeypatch.chdir(repo)

        assert orchestrate.landed("orch/r1-alpha", orchestrate.Run.load()) is True

    def test_a_branch_with_commits_not_on_the_run_branch_is_not_landed(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wt = _worktree(repo, "beta")
        _commit(wt, "beta.txt")
        _write_run(repo, [_unit_row("beta", wt, "done")])
        monkeypatch.chdir(repo)

        assert orchestrate.landed("orch/r1-beta", orchestrate.Run.load()) is False

    def test_a_branch_with_no_commits_of_its_own_is_not_landed(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The whole defect: this used to answer exactly like a merged branch."""
        wt = _worktree(repo, "silent")
        _write_run(repo, [_unit_row("silent", wt, "running")])
        monkeypatch.chdir(repo)
        got = orchestrate.landed("orch/r1-silent", orchestrate.Run.load())

        assert got is None
        assert got is not True


class TestHandFinishedLandingShapes:
    def test_a_fast_forward_land_is_not_inferred_without_merge_evidence(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A fast-forward loses authorship evidence, so the safe reading is committed nothing."""
        base = _git_out(repo, "rev-parse", "orch/r1")
        unit = orchestrate.Unit(name="fast", vendor="claude", task="x", status="done")
        run_record = orchestrate.Run(
            run_id="r1",
            source="a test",
            base=base,
            branch="orch/r1",
            units=[unit],
        )
        monkeypatch.chdir(repo)
        orchestrate.make_worktree(unit, run_record, repo)
        assert unit.branched_from == base
        assert unit.worktree is not None
        worktree = Path(unit.worktree)
        _commit(worktree, "fast.txt")
        run_record.save()

        _git(repo, "checkout", "orch/r1")
        _git(repo, "merge", "--no-edit", "orch/r1-fast")
        _git(repo, "checkout", "main")
        assert _git_out(repo, "rev-parse", "orch/r1") == _git_out(repo, "rev-parse", "orch/r1-fast")
        assert len(_git_out(repo, "rev-list", "--parents", "-n", "1", "orch/r1").split()) == 2

        loaded = orchestrate.Run.load()
        got = orchestrate.landed("orch/r1-fast", loaded)
        assert got is None
        assert got is not True

        capsys.readouterr()
        assert orchestrate.cmd_diff(argparse.Namespace(unit="fast", stat=False)) == 0
        diff_out = capsys.readouterr().out
        assert "no commits of its own" in diff_out

        _fake_agents(orchestrate, monkeypatch, {})
        assert orchestrate.cmd_check(argparse.Namespace()) == 1
        check_out = capsys.readouterr().out
        assert "NO COMMITS fast" in check_out

        assert orchestrate.cmd_clean(_clean_args(merged=True)) == 0
        clean_out = capsys.readouterr().out
        assert worktree.exists()
        assert "closed: nothing" in clean_out
        assert "fast" in clean_out.split("kept", 1)[1]

    def test_an_empty_unit_at_an_old_run_tip_stays_empty_and_is_not_reaped(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        base = _git_out(repo, "rev-parse", "orch/r1")
        worktree = _worktree(repo, "silent")

        _git(repo, "checkout", "-b", "advance", "orch/r1")
        _commit(repo, "advance.txt")
        _git(repo, "checkout", "orch/r1")
        _git(repo, "merge", "--no-edit", "advance")
        _git(repo, "branch", "-d", "advance")
        _git(repo, "checkout", "main")
        assert _git_out(repo, "merge-base", "orch/r1", "orch/r1-silent") == base
        assert _git_out(repo, "rev-parse", "orch/r1-silent") == base

        _write_run(
            repo,
            [_unit_row("silent", worktree, "done", branched_from=base)],
        )
        _fake_agents(orchestrate, monkeypatch, {})
        monkeypatch.chdir(repo)
        loaded = orchestrate.Run.load()

        got = orchestrate.landed("orch/r1-silent", loaded)
        assert got is None
        assert got is not True

        assert orchestrate.cmd_diff(argparse.Namespace(unit="silent", stat=False)) == 0
        diff_out = capsys.readouterr().out
        assert "no commits of its own" in diff_out

        assert orchestrate.cmd_check(argparse.Namespace()) == 1
        assert "NO COMMITS silent" in capsys.readouterr().out

        assert orchestrate.cmd_clean(_clean_args(merged=True)) == 0
        clean_out = capsys.readouterr().out
        assert worktree.exists()
        assert "closed: nothing" in clean_out
        assert "silent" in clean_out.split("kept", 1)[1]

    def test_an_empty_unit_that_merges_the_advanced_run_stays_empty(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Moving an empty unit to the run tip must not attribute a sibling's commit to it."""
        base = _git_out(repo, "rev-parse", "orch/r1")
        worktree = _worktree(repo, "updater")

        _git(repo, "checkout", "-b", "sibling", "orch/r1")
        _commit(repo, "sibling.txt")
        _git(repo, "checkout", "orch/r1")
        _git(repo, "merge", "--no-ff", "--no-edit", "sibling")
        _git(repo, "checkout", "main")

        # The unit authored nothing. This plain merge fast-forwards its branch from the recorded
        # creation tip to the advanced run tip, creating the ambiguous shape from the review.
        _git(worktree, "merge", "--no-edit", "orch/r1")
        assert _git_out(worktree, "rev-parse", "HEAD") != base
        assert _git_out(worktree, "rev-parse", "HEAD") == _git_out(repo, "rev-parse", "orch/r1")

        _write_run(
            repo,
            [
                _unit_row("updater", worktree, "done", branched_from=base),
                _unit_row("follower", None, "pending", branch=None, after=["updater"]),
            ],
        )
        _fake_agents(orchestrate, monkeypatch, {})
        monkeypatch.chdir(repo)
        loaded = orchestrate.Run.load()
        updater = loaded.unit("updater")

        got = orchestrate.landed("orch/r1-updater", loaded)
        assert got is None
        assert got is not True
        assert orchestrate.reapable(updater, loaded) is False
        assert orchestrate.produced_anything(updater, loaded) is False

        assert orchestrate.cmd_check(argparse.Namespace()) == 1
        assert "NO COMMITS updater" in capsys.readouterr().out

        assert orchestrate.cmd_diff(argparse.Namespace(unit="updater", stat=False)) == 0
        diff_out = capsys.readouterr().out
        assert "no commits of its own" in diff_out
        assert "sibling.txt" not in diff_out

        launched: list[str] = []
        monkeypatch.setattr(
            orchestrate,
            "launch",
            lambda unit, *_args, **_kwargs: launched.append(unit.name),
        )
        assert orchestrate.cmd_go(argparse.Namespace(limit=0)) == 0
        go_out = capsys.readouterr().out
        assert launched == []
        assert "follower: skipped" in go_out
        assert "updater committed nothing" in go_out

        assert orchestrate.cmd_clean(_clean_args(merged=True)) == 0
        clean_out = capsys.readouterr().out
        assert worktree.exists()
        assert "closed: nothing" in clean_out
        assert "updater" in clean_out.split("kept", 1)[1]

    def test_a_recorded_normal_merge_keeps_the_existing_landing_shape(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        base = _git_out(repo, "rev-parse", "orch/r1")
        worktree = _worktree(repo, "normal")
        _commit(worktree, "normal.txt")
        _write_run(
            repo,
            [_unit_row("normal", worktree, "done", branched_from=base)],
        )
        _git(repo, "checkout", "orch/r1")
        _git(repo, "merge", "--no-ff", "--no-edit", "orch/r1-normal")
        _git(repo, "checkout", "main")
        monkeypatch.chdir(repo)

        assert orchestrate.landed("orch/r1-normal", orchestrate.Run.load()) is True
        assert orchestrate.cmd_diff(argparse.Namespace(unit="normal", stat=False)) == 0
        out = capsys.readouterr().out
        assert "landed on orch/r1 in merge" in out
        assert "normal.txt" in out

    def test_recorded_commits_not_on_the_run_branch_are_not_landed(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = _git_out(repo, "rev-parse", "orch/r1")
        worktree = _worktree(repo, "waiting")
        _commit(worktree, "waiting.txt")
        _write_run(
            repo,
            [_unit_row("waiting", worktree, "done", branched_from=base)],
        )
        monkeypatch.chdir(repo)

        assert orchestrate.landed("orch/r1-waiting", orchestrate.Run.load()) is False


class TestCleanMergedOnlyReapsWhatSurvived:
    def test_a_running_unit_with_zero_commits_keeps_its_worktree(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """THE defect. A unit mid-work has committed nothing yet, which reads as zero commits
        ahead of the run branch -- the exact shape of a merged branch. It must survive."""
        wt = _worktree(repo, "builder")
        _write_run(repo, [_unit_row("builder", wt, "running")])
        monkeypatch.chdir(repo)

        rc = orchestrate.cmd_clean(_clean_args(merged=True))
        out = capsys.readouterr().out

        assert rc == 0
        assert wt.exists(), "a running unit's worktree must survive clean --merged"
        assert "closed: nothing" in out
        assert "builder" in out.split("kept", 1)[1]

    def test_a_done_unit_whose_commits_are_on_the_run_branch_is_reaped(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        wt = _worktree(repo, "alpha")
        _commit(wt, "alpha.txt")
        _write_run(repo, [_unit_row("alpha", wt, "done")])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_land(argparse.Namespace(clean=False)) == 0
        assert orchestrate.cmd_clean(_clean_args(merged=True)) == 0
        out = capsys.readouterr().out

        assert not wt.exists(), "a done unit whose work landed is pure overhead"
        assert "closed: alpha" in out
        assert _branch_exists(repo, "orch/r1-alpha"), "reaping never deletes branches"

    def test_a_done_unit_that_committed_nothing_keeps_its_worktree(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """That worktree is the evidence the session saved nothing -- the failure it shows."""
        wt = _worktree(repo, "silent")
        _write_run(repo, [_unit_row("silent", wt, "done")])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_clean(_clean_args(merged=True)) == 0

        assert wt.exists()

    def test_a_pending_unit_is_never_reaped(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Whatever the commit count: its branch here is fully landed, and it is still kept."""
        wt = _worktree(repo, "later")
        _commit(wt, "later.txt")
        _git(repo, "checkout", "orch/r1")
        _git(repo, "merge", "--no-ff", "--no-edit", "orch/r1-later")
        _git(repo, "checkout", "main")
        _write_run(repo, [_unit_row("later", wt, "pending")])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_clean(_clean_args(merged=True)) == 0

        assert wt.exists()


class TestLandCleanReapsWhatTheRuleAllows:
    def test_it_reaps_exactly_the_done_landed_units(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        wt_alpha = _worktree(repo, "alpha")
        _commit(wt_alpha, "alpha.txt")
        wt_silent = _worktree(repo, "silent")  # done, committed nothing
        wt_builder = _worktree(repo, "builder")  # still running, committed nothing
        _write_run(
            repo,
            [
                _unit_row("alpha", wt_alpha, "done"),
                _unit_row("silent", wt_silent, "done"),
                _unit_row("builder", wt_builder, "running"),
            ],
        )
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_land(argparse.Namespace(clean=True)) == 0
        out = capsys.readouterr().out

        assert not wt_alpha.exists()
        assert wt_silent.exists()
        assert wt_builder.exists()
        reaped = [line for line in out.splitlines() if line.startswith("reaped:")]
        assert reaped == ["reaped: alpha"]

    def test_it_never_deletes_branches(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A branch is cheap and is the last copy of a failed unit's work."""
        wt_alpha = _worktree(repo, "alpha")
        _commit(wt_alpha, "alpha.txt")
        wt_silent = _worktree(repo, "silent")
        _write_run(
            repo,
            [_unit_row("alpha", wt_alpha, "done"), _unit_row("silent", wt_silent, "done")],
        )
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_land(argparse.Namespace(clean=True)) == 0
        capsys.readouterr()

        assert _branch_exists(repo, "orch/r1-alpha"), "the reaped unit keeps its branch"
        assert _branch_exists(repo, "orch/r1-silent"), "the kept unit keeps its branch"

    def test_branch_deletion_stays_an_explicit_clean_flag(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wt_alpha = _worktree(repo, "alpha")
        _commit(wt_alpha, "alpha.txt")
        _write_run(repo, [_unit_row("alpha", wt_alpha, "done")])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_land(argparse.Namespace(clean=True)) == 0
        assert _branch_exists(repo, "orch/r1-alpha")

        assert orchestrate.cmd_clean(_clean_args(merged=True, branches=True)) == 0
        assert not _branch_exists(repo, "orch/r1-alpha")

    def test_with_nothing_landed_it_is_a_clean_no_op(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        wt = _worktree(repo, "builder")
        _write_run(repo, [_unit_row("builder", wt, "running")])
        monkeypatch.chdir(repo)

        rc = orchestrate.cmd_land(argparse.Namespace(clean=True))
        out = capsys.readouterr().out

        assert rc == 0
        assert wt.exists()
        assert "nothing new" in out
        assert "nothing to reap" in out


class TestProducedAnythingMeansThisUnit:
    """Measured from r.base, a post-land branch inherited the landed work and counted as
    productive the moment it existed. The merge base counts only what the unit itself did."""

    def test_a_post_land_branch_with_no_commits_produced_nothing(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _land_sibling(repo)
        wt = _worktree(repo, "late")  # cut from orch/r1 AFTER alpha landed
        _write_run(repo, [_unit_row("late", wt, "running")])
        monkeypatch.chdir(repo)
        r = orchestrate.Run.load()

        assert orchestrate.produced_anything(r.unit("late"), r) is False

    def test_a_post_land_branch_with_one_commit_produced_something(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _land_sibling(repo)
        wt = _worktree(repo, "late")
        _commit(wt, "late.txt")
        _write_run(repo, [_unit_row("late", wt, "running")])
        monkeypatch.chdir(repo)
        r = orchestrate.Run.load()

        assert orchestrate.produced_anything(r.unit("late"), r) is True

    def test_a_landed_unit_still_counts_as_produced(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """land merges with --no-ff: the unit's tip is the merge's second parent, and its
        commits are no less real for being on the run branch now."""
        _land_sibling(repo)
        _write_run(repo, [_unit_row("alpha", None, "done")])
        monkeypatch.chdir(repo)
        r = orchestrate.Run.load()

        assert orchestrate.produced_anything(r.unit("alpha"), r) is True


class TestCheckAfterALand:
    """The findings that died after the first land, on the post-land shapes that killed them."""

    def test_no_looks_done_for_an_idle_post_land_unit_that_committed_nothing(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Idle between turns with nothing saved is not drift -- that code's own comment says
        so, and after a land the old measurement made it fire anyway."""
        _land_sibling(repo)
        wt = _worktree(repo, "late")
        _write_run(repo, [_unit_row("alpha", None, "done"), _unit_row("late", wt, "running")])
        _fake_agents(orchestrate, monkeypatch, {"late": "idle"})
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_check(argparse.Namespace()) == 0
        out = capsys.readouterr().out
        assert "LOOKS DONE" not in out
        assert "the record agrees with the repository" in out

    def test_looks_done_still_fires_for_an_idle_post_land_unit_with_commits(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The positive control: the finding is alive post-land, so the test above proves a
        real silence, not a dead code path."""
        _land_sibling(repo)
        wt = _worktree(repo, "late")
        _commit(wt, "late.txt")
        _write_run(repo, [_unit_row("alpha", None, "done"), _unit_row("late", wt, "running")])
        _fake_agents(orchestrate, monkeypatch, {"late": "idle"})
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_check(argparse.Namespace()) == 1
        assert "LOOKS DONE late" in capsys.readouterr().out

    def test_no_commits_fires_for_a_done_post_land_unit_that_saved_nothing(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The finding `land` exists to shout about. After the first land it could never fire."""
        _land_sibling(repo)
        wt = _worktree(repo, "late")
        _write_run(repo, [_unit_row("alpha", None, "done"), _unit_row("late", wt, "done")])
        _fake_agents(orchestrate, monkeypatch, {})
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_check(argparse.Namespace()) == 1
        out = capsys.readouterr().out
        assert "NO COMMITS late" in out
        assert "LOOKS DONE" not in out


class TestALegacyRunStillRecognisesItsMergedWork:
    """A run predating the run branch landed its units straight onto the operator's tree.

    HEAD is the measure then, and the second-parent shape is just as readable there -- refusing
    it read a legacy unit whose work WAS merged as having produced nothing: ``check`` shouted
    NO COMMITS at landed work, and ``clean --merged`` would not reap it. The fix is the shape,
    not a blanket yes: a legacy branch that never committed is still nothing to land."""

    def test_a_merged_legacy_unit_is_landed(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wt = _legacy_worktree(repo, "alpha")
        _commit(wt, "alpha.txt")
        _write_legacy_run(repo, [_unit_row("alpha", wt, "done")])
        _git(repo, "merge", "--no-ff", "--no-edit", "orch/r1-alpha")
        monkeypatch.chdir(repo)

        assert orchestrate.landed("orch/r1-alpha", orchestrate.Run.load()) is True

    def test_check_is_quiet_for_a_merged_legacy_unit(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """It committed and landed: NO COMMITS would be a finding about nothing."""
        wt = _legacy_worktree(repo, "alpha")
        _commit(wt, "alpha.txt")
        _write_legacy_run(repo, [_unit_row("alpha", wt, "done")])
        _git(repo, "merge", "--no-ff", "--no-edit", "orch/r1-alpha")
        _fake_agents(orchestrate, monkeypatch, {})
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_check(argparse.Namespace()) == 0
        out = capsys.readouterr().out
        assert "NO COMMITS" not in out
        assert "the record agrees with the repository" in out

    def test_clean_merged_reaps_a_merged_legacy_unit(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        wt = _legacy_worktree(repo, "alpha")
        _commit(wt, "alpha.txt")
        _write_legacy_run(repo, [_unit_row("alpha", wt, "done")])
        _git(repo, "merge", "--no-ff", "--no-edit", "orch/r1-alpha")
        monkeypatch.chdir(repo)

        rc = orchestrate.cmd_clean(_clean_args(merged=True))
        out = capsys.readouterr().out

        assert rc == 0
        assert not wt.exists(), "its work is on the operator's tree; the worktree is overhead"
        assert "closed: alpha" in out
        assert _branch_exists(repo, "orch/r1-alpha"), "reaping never deletes branches"

    def test_a_legacy_run_without_a_base_still_recognises_its_merged_unit(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No run branch AND no base: there is no earlier bound to name, so the merge reading
        walks the ref's whole history rather than refusing."""
        wt = _legacy_worktree(repo, "alpha")
        _commit(wt, "alpha.txt")
        _git(repo, "merge", "--no-ff", "--no-edit", "orch/r1-alpha")
        _write_legacy_run(repo, [_unit_row("alpha", wt, "done")], base="")
        monkeypatch.chdir(repo)

        assert orchestrate.landed("orch/r1-alpha", orchestrate.Run.load()) is True

    def test_a_legacy_unit_that_never_committed_is_not_landed(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The legacy fix is the second-parent shape, not a blanket yes."""
        wt = _legacy_worktree(repo, "silent")
        _write_legacy_run(repo, [_unit_row("silent", wt, "done")])
        monkeypatch.chdir(repo)
        got = orchestrate.landed("orch/r1-silent", orchestrate.Run.load())

        assert got is None
        assert got is not True

    def test_clean_merged_keeps_a_legacy_unit_that_never_committed(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """That worktree is still the evidence the session saved nothing."""
        wt = _legacy_worktree(repo, "silent")
        _write_legacy_run(repo, [_unit_row("silent", wt, "done")])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_clean(_clean_args(merged=True)) == 0

        assert wt.exists()


class TestLandCleanReapsOnlyWhatThisLandMerged:
    """Reaping must be a consequence of what THIS land merged, not a sweep of the whole run.

    ``land --clean`` once reaped every unit the rule allowed, so an invocation that merged
    nothing still closed the tabs and removed the worktrees of units an earlier invocation
    deliberately kept. The operator's own ``clean --merged`` remains the deliberate sweep."""

    def test_merging_nothing_reaps_nothing_and_keeps_a_retained_worktree(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        wt_alpha = _worktree(repo, "alpha")
        _commit(wt_alpha, "alpha.txt")
        _write_run(repo, [_unit_row("alpha", wt_alpha, "done")])
        monkeypatch.chdir(repo)

        # The first land merges alpha and deliberately keeps its worktree.
        assert orchestrate.cmd_land(argparse.Namespace(clean=False)) == 0
        capsys.readouterr()
        assert wt_alpha.exists()

        # The second merges nothing -- and must not sweep what the first one kept.
        assert orchestrate.cmd_land(argparse.Namespace(clean=True)) == 0
        out = capsys.readouterr().out

        assert wt_alpha.exists(), "a land that merged nothing is not a licence to reap"
        assert "nothing new" in out
        assert "nothing to reap" in out

    def test_merging_one_unit_reaps_it_and_leaves_a_retained_unit_alone(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        wt_alpha = _worktree(repo, "alpha")
        _commit(wt_alpha, "alpha.txt")
        wt_beta = _worktree(repo, "beta")
        _commit(wt_beta, "beta.txt")
        _write_run(
            repo,
            [_unit_row("alpha", wt_alpha, "done"), _unit_row("beta", wt_beta, "running")],
        )
        monkeypatch.chdir(repo)

        # The first land merges alpha and deliberately keeps its worktree.
        assert orchestrate.cmd_land(argparse.Namespace(clean=False)) == 0
        capsys.readouterr()
        assert wt_alpha.exists()

        # Beta finishes; the second land merges it -- and reaps only it.
        _write_run(
            repo,
            [_unit_row("alpha", wt_alpha, "done"), _unit_row("beta", wt_beta, "done")],
        )
        assert orchestrate.cmd_land(argparse.Namespace(clean=True)) == 0
        out = capsys.readouterr().out

        assert not wt_beta.exists()
        assert wt_alpha.exists(), "an earlier invocation kept alpha; this land did not merge it"
        reaped = [line for line in out.splitlines() if line.startswith("reaped:")]
        assert reaped == ["reaped: beta"]
