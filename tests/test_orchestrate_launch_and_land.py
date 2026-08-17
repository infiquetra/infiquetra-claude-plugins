"""Two decisions a unit carries that nothing else can recover: how it launches, and whether it lands.

Both exist because the live run for issue 48 lost them. The launcher needed an argument the unit had
no field for, so a whole review phase was started by hand and never entered the run record; and
``land`` merges every finished unit, which is the one thing the command's own documentation forbids
for competing plans, so every merge in that run was done by hand instead.

The landing tests drive ``cmd_land`` against a real git repository rather than a stand-in for one.
Merging is the behaviour under test, so a fake that reports a merge proves nothing about whether one
happened.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
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
    spec = importlib.util.spec_from_file_location("_orchestrate_launch_land", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def launcher_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Put a launcher where ``agent_argv`` will find one.

    ``agent_argv`` resolves the wrapper for real rather than trusting a name, so on a machine
    without it every one of these fails on the lookup instead of on the thing under test. Giving it
    a real file keeps that resolution in the test rather than stubbing it out -- the check is the
    reason a renamed wrapper stopped launching Cursor by mistake.
    """
    (tmp_path / "agents").write_text("#!/bin/sh\n")
    (tmp_path / "agents").chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)


@pytest.mark.usefixtures("launcher_on_path")
class TestLauncherArgumentsArePassedThrough:
    """The plugin carries what the operator asked for; the launcher decides whether it is valid."""

    def test_extra_arguments_reach_the_command_line(self, orchestrate: ModuleType) -> None:
        unit = orchestrate.Unit(
            name="reviewer",
            vendor="claude",
            task="/saga:code-review the build",
            model="opus",
            launch_args=["--company-account"],
        )
        argv = orchestrate.agent_argv(unit)
        assert "--company-account" in argv

    def test_they_follow_the_vendor_token(self, orchestrate: ModuleType) -> None:
        """The wrapper reads its own flags out of the arguments after the vendor name."""
        unit = orchestrate.Unit(
            name="reviewer", vendor="claude", task="x", launch_args=["--company-account"]
        )
        argv = orchestrate.agent_argv(unit)
        assert argv.index("--company-account") > argv.index("claude")

    def test_nothing_is_added_when_none_are_asked_for(self, orchestrate: ModuleType) -> None:
        unit = orchestrate.Unit(name="reviewer", vendor="claude", task="x")
        plain = orchestrate.agent_argv(unit)
        unit.launch_args = ["--company-account"]
        assert orchestrate.agent_argv(unit) == plain + ["--company-account"]

    def test_an_unknown_argument_is_not_rejected_here(self, orchestrate: ModuleType) -> None:
        """No allow-list: a stale one in this file is the same closed vocabulary one level up."""
        unit = orchestrate.Unit(
            name="reviewer", vendor="qwen", task="x", launch_args=["--not-a-real-flag"]
        )
        assert "--not-a-real-flag" in orchestrate.agent_argv(unit)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _commit(cwd: Path, name: str) -> None:
    (cwd / name).write_text(name + "\n")
    _git(cwd, "add", name)
    _git(cwd, "commit", "-m", f"add {name}")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A run branch plus two unit branches, each with one commit of its own."""
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
        _git(r, "checkout", "main")
    return r


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


def _unit(name: str, **over: Any) -> dict[str, Any]:
    return {
        "name": name,
        "vendor": "claude",
        "task": "x",
        "branch": f"orch/r1-{name}",
        "status": "done",
        **over,
    }


def _on(repo: Path, branch: str, path: str) -> bool:
    got = subprocess.run(
        ["git", "cat-file", "-e", f"{branch}:{path}"], cwd=repo, capture_output=True
    )
    return got.returncode == 0


class TestLandHonoursMergeIntent:
    def test_a_unit_that_says_no_is_not_merged(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(repo, [_unit("alpha"), _unit("beta", merge=False)])
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 0

        assert _on(repo, "orch/r1", "alpha.txt"), "a plain unit should have landed"
        assert not _on(repo, "orch/r1", "beta.txt"), "merge=false should have been honoured"

    def test_the_skipped_unit_is_named(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Silence would read as 'everything landed', which is how a branch gets left behind."""
        _write_run(repo, [_unit("alpha"), _unit("beta", merge=False)])
        monkeypatch.chdir(repo)
        orchestrate.cmd_land(argparse.Namespace())

        out = capsys.readouterr().out
        assert "NOT MERGED BY REQUEST" in out
        assert "beta" in out

    def test_merging_is_the_default(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A plan written before this field existed must behave exactly as it did."""
        _write_run(repo, [_unit("alpha"), _unit("beta")])
        monkeypatch.chdir(repo)
        orchestrate.cmd_land(argparse.Namespace())

        assert _on(repo, "orch/r1", "alpha.txt")
        assert _on(repo, "orch/r1", "beta.txt")
        assert "NOT MERGED BY REQUEST" not in capsys.readouterr().out

    def test_an_unfinished_unit_is_not_reported_as_skipped(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The report is about finished work held back, not about work still running."""
        _write_run(repo, [_unit("alpha"), _unit("beta", merge=False, status="running")])
        monkeypatch.chdir(repo)
        orchestrate.cmd_land(argparse.Namespace())

        assert "NOT MERGED BY REQUEST" not in capsys.readouterr().out

    def test_the_working_branch_is_restored(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(repo, [_unit("alpha", merge=False)])
        monkeypatch.chdir(repo)
        orchestrate.cmd_land(argparse.Namespace())

        on = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert on == "main"


class TestCleanCanReapDuringARun:
    """`clean --merged` measured against the operator's tree, which sees nothing until `collect`.

    So the only mode safe to run unattended closed nothing for the whole run — exactly when sessions
    pile up — and the only way to reap mid-run was bare `clean`, which also discards the worktree of
    a unit that failed.
    """

    def test_a_landed_unit_is_reapable_before_collect(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _git(repo, "checkout", "orch/r1")
        _git(repo, "merge", "--no-ff", "--no-edit", "orch/r1-alpha")
        _git(repo, "checkout", "main")
        _write_run(repo, [_unit("alpha")])
        monkeypatch.chdir(repo)
        r = orchestrate.Run.load()

        assert orchestrate.landed("orch/r1-alpha", r) is True

    def test_an_unlanded_unit_is_kept(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Its worktree is the evidence you look at when it went wrong."""
        _write_run(repo, [_unit("beta")])
        monkeypatch.chdir(repo)
        r = orchestrate.Run.load()

        assert orchestrate.landed("orch/r1-beta", r) is False

    def test_a_unit_that_never_merges_is_never_reaped(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A competing-plan branch holds the only copy of its plan, so it keeps its worktree."""
        _write_run(repo, [_unit("alpha", merge=False)])
        monkeypatch.chdir(repo)
        r = orchestrate.Run.load()

        assert orchestrate.landed("orch/r1-alpha", r) is False

    def test_a_run_with_no_run_branch_falls_back_to_the_operator_tree(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Old run files predate `land`; there is nothing else to measure against."""
        _write_run(repo, [_unit("alpha")])
        path = repo / ".orchestrate" / "run.json"
        payload = json.loads(path.read_text())
        payload["branch"] = ""
        path.write_text(json.dumps(payload))
        monkeypatch.chdir(repo)
        r = orchestrate.Run.load()

        assert orchestrate.landed("orch/r1-alpha", r) is False
