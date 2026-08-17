"""Where the run record and the repository disagree, and how adopt puts the pieces back.

A run's whole state is one JSON file, while the truth lives in git and herdr; the two drift when a
session is started by hand or a run file is lost around live work. ``check`` names the drift and
changes nothing; ``adopt`` rebuilds a unit row from what is still true -- the branch, its worktree,
and the session herdr reports there -- and only writes when told to.

Both are driven against a real git repository. The discovery under test is reading actual branches
and worktrees, so a fake that reports them proves nothing about whether they exist.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
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
    spec = importlib.util.spec_from_file_location("_orchestrate_drift_adopt", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _commit(cwd: Path, name: str) -> None:
    (cwd / name).write_text(name + "\n")
    _git(cwd, "add", name)
    _git(cwd, "commit", "-m", f"add {name}")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A run branch and two unit branches, each with one commit, both already landed.

    Landed rather than raw so the fixture is a run whose record agrees with the repository -- the
    clean baseline ``check`` reports nothing on. Tests that need drift add branches on top of it.
    """
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "test@example.com")
    _git(r, "config", "user.name", "Test")
    _commit(r, "base.txt")
    _git(r, "branch", "orch/r1")
    for unit in ("alpha", "beta"):
        _git(r, "checkout", "-b", f"orch/r1-{unit}", "orch/r1")
        _commit(r, f"{unit}.txt")
        _git(r, "checkout", "orch/r1")
        _git(r, "merge", "--no-ff", "--no-edit", f"orch/r1-{unit}")
    _git(r, "checkout", "main")
    return r


def _write_run(repo: Path, units: list[dict[str, Any]], branch: str = "orch/r1") -> None:
    base = subprocess.run(
        ["git", "rev-parse", "main"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    payload = {
        "run_id": "r1",
        "source": "a test",
        "base": base,
        "branch": branch,
        "units": units,
    }
    path = repo / ".orchestrate" / "run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _read_run(repo: Path) -> dict[str, Any]:
    raw: dict[str, Any] = json.loads((repo / ".orchestrate" / "run.json").read_text())
    return raw


def _unit(name: str, **over: Any) -> dict[str, Any]:
    return {
        "name": name,
        "vendor": "claude",
        "task": "x",
        "branch": f"orch/r1-{name}",
        "status": "done",
        **over,
    }


class TestCheck:
    def test_a_clean_run_reports_nothing(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(repo, [_unit("alpha"), _unit("beta")])
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_check(argparse.Namespace()) == 0
        assert "the record agrees with the repository" in capsys.readouterr().out

    def test_a_branch_with_no_unit_is_unrecorded(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _git(repo, "branch", "orch/r1-stray", "orch/r1")
        _write_run(repo, [_unit("alpha"), _unit("beta")])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_check(argparse.Namespace()) == 1
        out = capsys.readouterr().out
        assert "UNRECORDED stray -- branch orch/r1-stray is not a unit in this run" in out

    def test_the_run_branch_itself_is_never_unrecorded(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``orch/r1`` exists like any other run branch, but it is no unit and must never appear."""
        _write_run(repo, [_unit("alpha"), _unit("beta")])
        monkeypatch.chdir(repo)
        orchestrate.cmd_check(argparse.Namespace())

        out = capsys.readouterr().out
        assert "branch orch/r1 is not a unit" not in out

    def test_a_done_unit_with_no_commits_is_reported(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # at base with nothing of its own: the session finished and saved nothing
        _git(repo, "branch", "orch/r1-empty", "main")
        _write_run(repo, [_unit("alpha"), _unit("beta"), _unit("empty")])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_check(argparse.Namespace()) == 1
        assert "NO COMMITS empty" in capsys.readouterr().out

    def test_a_done_unit_with_unlanded_commits_is_reported(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(repo, [_unit("alpha"), _unit("beta")])
        _git(repo, "checkout", "orch/r1-alpha")
        _commit(repo, "late.txt")
        _git(repo, "checkout", "main")
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_check(argparse.Namespace()) == 1
        out = capsys.readouterr().out
        assert "NOT LANDED alpha" in out
        assert "1 commit not on orch/r1" in out

    def test_a_done_unit_with_merge_false_is_not_not_landed(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """merge=false is a hold by request, not drift -- ``land`` names it, ``check`` must not."""
        _write_run(repo, [_unit("alpha"), _unit("beta", merge=False)])
        _git(repo, "checkout", "orch/r1-beta")
        _commit(repo, "late.txt")
        _git(repo, "checkout", "main")
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_check(argparse.Namespace()) == 0
        out = capsys.readouterr().out
        assert "NOT LANDED" not in out
        assert "the record agrees with the repository" in out


def _hide_herdr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A PATH with git on it and no herdr -- what a build runner actually looks like.

    Emptying PATH outright would also hide git, which these commands genuinely need; that tests a
    different machine than the one that broke.
    """
    only_git = tmp_path / "path-without-herdr"
    only_git.mkdir(exist_ok=True)
    (only_git / "git").symlink_to(shutil.which("git") or "/usr/bin/git")
    monkeypatch.setenv("PATH", str(only_git))
    assert shutil.which("herdr") is None


class TestHerdrIsOptional:
    """Both commands decided herdr is optional; the code only half meant it.

    ``check=False`` covers a command that fails, not a command that is not installed --
    ``subprocess.run`` raises there rather than returning. CI has no herdr, and every one of these
    tests died on a traceback out of a read-only command. This machine has herdr, which is exactly
    why the local run was green.
    """

    def test_check_survives_a_machine_without_herdr(
        self,
        orchestrate: ModuleType,
        repo: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(repo, [_unit("alpha")])
        _hide_herdr(tmp_path, monkeypatch)
        monkeypatch.chdir(repo)
        orchestrate.cmd_check(argparse.Namespace())

    def test_adopt_survives_a_machine_without_herdr(
        self,
        orchestrate: ModuleType,
        repo: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(repo, [])
        _hide_herdr(tmp_path, monkeypatch)
        monkeypatch.chdir(repo)
        orchestrate.cmd_adopt(argparse.Namespace(yes=False))


class TestAdopt:
    """No live session exists in a temporary repository: these all exercise the no-matched-agent
    path, which is the one where a branch is all the evidence there is."""

    def test_without_yes_nothing_is_written(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _git(repo, "checkout", "-b", "orch/r1-stray", "orch/r1")
        _commit(repo, "stray.txt")
        _git(repo, "checkout", "main")
        _write_run(repo, [_unit("alpha"), _unit("beta")])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_adopt(argparse.Namespace(yes=False)) == 0
        out = capsys.readouterr().out
        assert "would adopt: stray" in out
        assert "nothing written -- rerun with --yes" in out
        assert [u["name"] for u in _read_run(repo)["units"]] == ["alpha", "beta"]

    def test_with_yes_the_unit_lands_in_the_record(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _git(repo, "checkout", "-b", "orch/r1-stray", "orch/r1")
        _commit(repo, "stray.txt")
        _git(repo, "checkout", "main")
        _write_run(repo, [_unit("alpha"), _unit("beta")])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_adopt(argparse.Namespace(yes=True)) == 0
        out = capsys.readouterr().out
        assert "adopted: stray" in out
        assert "1 unit(s) written to the run file" in out

        units = {u["name"]: u for u in _read_run(repo)["units"]}
        assert "stray" in units
        assert units["stray"]["branch"] == "orch/r1-stray"
        assert units["stray"]["note"] == "adopted: created outside the run record"

    def test_a_branch_with_commits_and_no_session_is_done(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Commits are the evidence the session finished its work, so the row says done."""
        _git(repo, "checkout", "-b", "orch/r1-stray", "orch/r1")
        _commit(repo, "stray.txt")
        _git(repo, "checkout", "main")
        _write_run(repo, [_unit("alpha"), _unit("beta")])
        monkeypatch.chdir(repo)

        orchestrate.cmd_adopt(argparse.Namespace(yes=True))
        units = {u["name"]: u for u in _read_run(repo)["units"]}
        assert units["stray"]["status"] == "done"
        assert units["stray"]["vendor"] == "unknown"

    def test_a_branch_with_no_commits_and_no_session_is_failed(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No session and nothing committed: there is no reading of that in which it succeeded."""
        # at base with nothing of its own -- a branch cut from orch/r1 would carry the landed
        # commits of the other units and read as done
        _git(repo, "branch", "orch/r1-hollow", "main")
        _write_run(repo, [_unit("alpha"), _unit("beta")])
        monkeypatch.chdir(repo)

        orchestrate.cmd_adopt(argparse.Namespace(yes=True))
        units = {u["name"]: u for u in _read_run(repo)["units"]}
        assert units["hollow"]["status"] == "failed"

    def test_adopting_twice_does_not_duplicate(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The second pass must see the unit the first pass wrote, not the branch alone."""
        _git(repo, "checkout", "-b", "orch/r1-stray", "orch/r1")
        _commit(repo, "stray.txt")
        _git(repo, "checkout", "main")
        _write_run(repo, [_unit("alpha"), _unit("beta")])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_adopt(argparse.Namespace(yes=True)) == 0
        assert orchestrate.cmd_adopt(argparse.Namespace(yes=True)) == 0
        names = [u["name"] for u in _read_run(repo)["units"]]
        assert names.count("stray") == 1
