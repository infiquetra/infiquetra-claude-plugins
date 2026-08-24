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
from typing import Any, cast

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


@pytest.mark.usefixtures("launcher_on_path")
class TestWorkspaceIsALauncherField:
    """``--workspace`` only works before the vendor token, so it is a field, not a passthrough."""

    def test_a_unit_workspace_is_emitted_before_the_vendor_token(
        self, orchestrate: ModuleType
    ) -> None:
        unit = orchestrate.Unit(name="reviewer", vendor="claude", task="x", workspace="issue-48")
        argv = orchestrate.agent_argv(unit)
        assert argv[argv.index("--workspace") + 1] == "issue-48"
        assert argv.index("--workspace") < argv.index("claude")

    def test_launch_args_still_follow_the_vendor_token(self, orchestrate: ModuleType) -> None:
        unit = orchestrate.Unit(
            name="reviewer",
            vendor="claude",
            task="x",
            workspace="issue-48",
            launch_args=["--company-account"],
        )
        argv = orchestrate.agent_argv(unit)
        assert argv.index("--workspace") < argv.index("claude")
        assert argv.index("--company-account") > argv.index("claude")

    def test_a_unit_with_no_workspace_produces_today_s_argv(self, orchestrate: ModuleType) -> None:
        unit = orchestrate.Unit(name="reviewer", vendor="claude", task="x")
        argv = orchestrate.agent_argv(unit)
        assert "--workspace" not in argv
        with_args = orchestrate.Unit(
            name="reviewer", vendor="claude", task="x", launch_args=["--company-account"]
        )
        assert orchestrate.agent_argv(with_args) == argv + ["--company-account"]

    def test_a_run_default_is_inherited_when_the_unit_has_none(
        self, orchestrate: ModuleType
    ) -> None:
        unit = orchestrate.Unit(name="reviewer", vendor="claude", task="x")
        argv = orchestrate.agent_argv(unit, default_workspace="issue-48")
        assert argv[argv.index("--workspace") + 1] == "issue-48"
        assert argv.index("--workspace") < argv.index("claude")

    def test_a_unit_workspace_wins_over_the_run_default(self, orchestrate: ModuleType) -> None:
        unit = orchestrate.Unit(name="reviewer", vendor="claude", task="x", workspace="child-9")
        argv = orchestrate.agent_argv(unit, default_workspace="issue-48")
        assert argv[argv.index("--workspace") + 1] == "child-9"

    def test_absent_both_does_not_emit_the_flag(self, orchestrate: ModuleType) -> None:
        unit = orchestrate.Unit(name="reviewer", vendor="claude", task="x")
        assert "--workspace" not in orchestrate.agent_argv(unit, default_workspace=None)


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


@pytest.mark.usefixtures("launcher_on_path")
class TestRunWorkspaceIsInheritedAtLaunch:
    """A run default is stored on the run, copied onto a unit only when that unit has none."""

    def test_start_records_the_run_workspace(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(repo)
        plan = repo / "plan.json"
        plan.write_text(
            json.dumps(
                {
                    "run_id": "r2",
                    "source": "a test",
                    "workspace": "issue-48",
                    "units": [{"name": "alpha", "vendor": "claude", "task": "x"}],
                }
            )
        )
        assert orchestrate.cmd_start(argparse.Namespace(plan=str(plan), base=None)) == 0
        raw = json.loads((repo / ".orchestrate" / "run.json").read_text())
        assert raw["workspace"] == "issue-48"
        assert raw["units"][0].get("workspace") in (None, "")

    def test_go_copies_the_run_default_onto_a_unit_that_has_none(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("alpha", status="pending", branch=None)])
        path = repo / ".orchestrate" / "run.json"
        raw = json.loads(path.read_text())
        raw["workspace"] = "issue-48"
        raw["units"][0]["workspace"] = None
        path.write_text(json.dumps(raw))
        monkeypatch.chdir(repo)
        seen: list[str | None] = []

        def fake_launch(
            unit: Any, backend: str = "inline", *, review_elsewhere: bool = False
        ) -> None:
            seen.append(unit.workspace)
            unit.status = "running"

        monkeypatch.setattr(orchestrate, "make_worktree", lambda *_a, **_k: None)
        monkeypatch.setattr(orchestrate, "launch", fake_launch)
        assert orchestrate.cmd_go(argparse.Namespace(limit=0)) == 0
        assert seen == ["issue-48"]

    def test_go_does_not_overwrite_a_unit_workspace(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("alpha", status="pending", branch=None, workspace="child-9")])
        path = repo / ".orchestrate" / "run.json"
        raw = json.loads(path.read_text())
        raw["workspace"] = "issue-48"
        path.write_text(json.dumps(raw))
        monkeypatch.chdir(repo)
        seen: list[str | None] = []

        def fake_launch(
            unit: Any, backend: str = "inline", *, review_elsewhere: bool = False
        ) -> None:
            seen.append(unit.workspace)
            unit.status = "running"

        monkeypatch.setattr(orchestrate, "make_worktree", lambda *_a, **_k: None)
        monkeypatch.setattr(orchestrate, "launch", fake_launch)
        assert orchestrate.cmd_go(argparse.Namespace(limit=0)) == 0
        assert seen == ["child-9"]


def _git_branch_exists(repo: Path, branch: str) -> bool:
    res = subprocess.run(["git", "rev-parse", "--verify", branch], cwd=repo, capture_output=True)
    return res.returncode == 0


@pytest.mark.usefixtures("launcher_on_path")
class TestBackgroundNoFocusLaunchFlags:
    """The central agent_argv path must always lock the background no-focus invariant."""

    EXPECTED_FLAGS = ("--no-focus", "--current", "--herdr", "--herdr-control-only")

    @pytest.mark.parametrize(
        "vendor",
        ["claude", "codex", "grok", "muse", "agy", "qwen", "opencode"],
    )
    def test_complete_background_flags_emitted_before_vendor_token(
        self, orchestrate: ModuleType, vendor: str
    ) -> None:
        unit = orchestrate.Unit(name="worker", vendor=vendor, task="do work")
        argv = orchestrate.agent_argv(unit)
        vendor_idx = argv.index(vendor)
        for flag in self.EXPECTED_FLAGS:
            assert flag in argv, f"flag {flag!r} missing from agent_argv for vendor {vendor!r}"
            assert argv.index(flag) < vendor_idx, (
                f"flag {flag!r} emitted after vendor token {vendor!r}"
            )

    def test_background_flag_ordering_and_completeness(self, orchestrate: ModuleType) -> None:
        unit = orchestrate.Unit(
            name="worker",
            vendor="claude",
            task="do work",
            worktree="/tmp/wt-worker",
            workspace="ws-1",
            model="opus",
            effort="high",
            launch_args=["--company-account"],
        )
        argv = orchestrate.agent_argv(unit)
        launcher_bin = orchestrate.launcher()
        expected_prefix = [
            launcher_bin,
            "--no-focus",
            "--current",
            "--herdr",
            "--herdr-control-only",
            "--task",
            "worker",
            "--cwd",
            "/tmp/wt-worker",
            "--workspace",
            "ws-1",
            "claude",
        ]
        assert argv[: len(expected_prefix)] == expected_prefix
        assert "--company-account" in argv
        assert argv.index("--company-account") > argv.index("claude")


@pytest.mark.usefixtures("launcher_on_path")
class TestExpansionAndCentralLauncher:
    """Expansion units must be persisted before creation and launched via central launcher."""

    def test_post_plan_expansion_persists_before_launch_and_uses_central_launcher(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(repo)
        plan_file = repo / "initial-plan.json"
        plan_file.write_text(
            json.dumps(
                {
                    "run_id": "r1",
                    "source": "expansion test",
                    "workspace": "issue-773",
                    "units": [{"name": "planner", "vendor": "claude", "task": "plan"}],
                }
            )
        )
        assert orchestrate.cmd_start(argparse.Namespace(plan=str(plan_file), base=None)) == 0

        # Expand with new units at later phase boundary
        expand_file = repo / "expand-plan.json"
        expand_file.write_text(
            json.dumps(
                {
                    "units": [
                        {
                            "name": "builder-1",
                            "vendor": "claude",
                            "task": "build 1",
                            "after": ["planner"],
                        },
                        {
                            "name": "builder-2",
                            "vendor": "grok",
                            "task": "build 2",
                            "after": ["planner"],
                        },
                    ]
                }
            )
        )
        assert orchestrate.cmd_expand(argparse.Namespace(plan=str(expand_file))) == 0

        # Assert persisted before any worktree or session is created
        run_data = json.loads((repo / ".orchestrate" / "run.json").read_text())
        unit_names = [u["name"] for u in run_data["units"]]
        assert unit_names == ["planner", "builder-1", "builder-2"]
        for u in run_data["units"]:
            if u["name"] in ("builder-1", "builder-2"):
                assert u["status"] == "pending"
                assert u.get("worktree") in (None, "")
                assert u.get("tab_id") in (None, "")

        # Create branch and commit for planner so 'after' dependency is satisfied
        _commit_file = repo / "planner.txt"
        _commit_file.write_text("plan doc\n")
        subprocess.run(
            ["git", "checkout", "-b", "orch/r1-planner", "orch/r1"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "add", "planner.txt"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "plan commit"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)

        # Mark planner done in run.json
        r = orchestrate.Run.load()
        r.units[0].status = "done"
        r.units[0].branch = "orch/r1-planner"
        r.save()

        # Track launches via cmd_go
        launched_argvs: list[list[str]] = []
        original_run = orchestrate.run

        def intercept_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            if cmd and cmd[0] == orchestrate.launcher():
                launched_argvs.append(cmd)
                unit_name = cmd[cmd.index("--task") + 1]
                return subprocess.CompletedProcess(
                    cmd,
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "tab_id": f"tab-{unit_name}",
                            "pane_id": f"pane-{unit_name}",
                            "agent_name": unit_name,
                        }
                    )
                    + "\n",
                    stderr="",
                )
            return cast(subprocess.CompletedProcess[str], original_run(cmd, **kwargs))

        monkeypatch.setattr(orchestrate, "run", intercept_run)
        monkeypatch.setattr(orchestrate, "await_ready", lambda _unit: True)
        monkeypatch.setattr(orchestrate, "send", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(orchestrate, "took_the_task", lambda _unit: True)

        assert orchestrate.cmd_go(argparse.Namespace(limit=0)) == 0

        # Verify that both expanded units launched through central launcher with no-focus flags
        assert len(launched_argvs) == 2
        for argv in launched_argvs:
            assert "--no-focus" in argv
            assert "--current" in argv
            assert "--herdr" in argv
            assert "--herdr-control-only" in argv

        # Verify run record completeness
        updated_run = orchestrate.Run.load()
        for u in updated_run.units[1:]:
            assert u.status == "running"
            assert u.tab_id == f"tab-{u.name}"
            assert u.pane_id == f"pane-{u.name}"
            assert u.agent_name == u.name
            assert u.branch == f"orch/r1-{u.name}"
            assert u.worktree is not None and Path(u.worktree).exists()
            assert u.workspace == "issue-773"


@pytest.mark.usefixtures("launcher_on_path")
class TestNoFocusInvariantIntegration:
    """Integration test: operator focused pane is preserved before and after run-owned launches."""

    def test_operator_focused_pane_preserved_across_multiple_launches(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(repo)
        # Create run with 3 pending units
        _write_run(
            repo,
            [
                _unit("unit1", status="pending", branch=None),
                _unit("unit2", status="pending", branch=None),
                _unit("unit3", status="pending", branch=None),
            ],
        )

        focused_pane = "pane-operator-main"
        original_run = orchestrate.run

        # Mock herdr / launcher interaction:
        # A launcher with --no-focus preserves the operator's active focused pane.
        # Without --no-focus it would switch focus to the new pane.
        def mocked_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            nonlocal focused_pane
            if cmd and cmd[0] == orchestrate.launcher():
                unit_name = cmd[cmd.index("--task") + 1]
                new_pane = f"pane-{unit_name}"
                if "--no-focus" not in cmd:
                    focused_pane = new_pane
                return subprocess.CompletedProcess(
                    cmd,
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "tab_id": f"tab-{unit_name}",
                            "pane_id": new_pane,
                            "agent_name": unit_name,
                        }
                    )
                    + "\n",
                    stderr="",
                )
            return cast(subprocess.CompletedProcess[str], original_run(cmd, **kwargs))

        monkeypatch.setattr(orchestrate, "run", mocked_run)
        monkeypatch.setattr(orchestrate, "await_ready", lambda _unit: True)
        monkeypatch.setattr(orchestrate, "send", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(orchestrate, "took_the_task", lambda _unit: True)

        pane_before = focused_pane
        assert orchestrate.cmd_go(argparse.Namespace(limit=0)) == 0
        pane_after = focused_pane

        assert pane_before == "pane-operator-main"
        assert pane_after == "pane-operator-main"

        # Verify run record contains every created worktree, branch, workspace, tab, pane, agent
        r = orchestrate.Run.load()
        for u in r.units:
            assert u.status == "running"
            assert u.worktree is not None and Path(u.worktree).exists()
            assert u.branch == f"orch/r1-{u.name}"
            assert u.tab_id == f"tab-{u.name}"
            assert u.pane_id == f"pane-{u.name}"
            assert u.agent_name == u.name


class TestScopedCleanup:
    """Cleanup remains limited to run-owned resources and never removes foreign resources."""

    def test_cleanup_only_touches_run_owned_resources(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(repo)
        # Land run-owned alpha unit
        _git(repo, "checkout", "orch/r1")
        _git(repo, "merge", "--no-ff", "--no-edit", "orch/r1-alpha")
        _git(repo, "checkout", "main")

        wt_alpha = repo / ".orchestrate" / "wt-alpha"
        wt_alpha.mkdir(parents=True, exist_ok=True)
        _git(repo, "worktree", "add", "--detach", str(wt_alpha), "orch/r1-alpha")

        # Create foreign/unrelated worktree, branch, and tab
        foreign_wt = repo / "foreign-worktree"
        foreign_wt.mkdir(parents=True, exist_ok=True)
        _git(repo, "branch", "foreign-feature", "main")
        _git(repo, "worktree", "add", "--detach", str(foreign_wt), "foreign-feature")

        _write_run(
            repo,
            [
                _unit(
                    "alpha",
                    status="done",
                    branch="orch/r1-alpha",
                    worktree=str(wt_alpha),
                    tab_id="tab-run-alpha",
                ),
            ],
        )

        closed_tabs: list[str] = []
        original_run = orchestrate.run

        def track_tab_close(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            if cmd[:3] == ["herdr", "tab", "close"]:
                closed_tabs.append(cmd[3])
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
            return cast(subprocess.CompletedProcess[str], original_run(cmd, **kwargs))

        monkeypatch.setattr(orchestrate, "run", track_tab_close)

        assert orchestrate.cmd_clean(argparse.Namespace(merged=True, branches=True, all=False)) == 0

        # Verify run-owned alpha tab and worktree were closed
        assert "tab-run-alpha" in closed_tabs
        assert not wt_alpha.exists()
        assert not _git_branch_exists(repo, "orch/r1-alpha")

        # Verify foreign resources were NOT touched
        assert foreign_wt.exists()
        assert _git_branch_exists(repo, "foreign-feature")


class TestStatusSurfacesUnrecordedDrift:
    """Status reports unrecorded unit branches matching the run prefix."""

    def test_status_reports_unrecorded_unit_branches(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(repo, [_unit("alpha")])
        _git(repo, "branch", "orch/r1-untracked", "orch/r1")
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_status(argparse.Namespace()) == 0
        output = capsys.readouterr().out
        assert (
            "UNRECORDED untracked -- branch orch/r1-untracked is not a unit in this run" in output
        )


@pytest.mark.usefixtures("launcher_on_path")
class TestOpenCodeLaunchAndVariantRecipe:
    """OpenCode launch recipe, interactive /variants picker driving, and preflight verification."""

    def test_opencode_launches_through_agents_and_drives_variants_recipe(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Complete OpenCode recipe: agents launch, /variants driven, xhigh selected for max, verified receipt."""
        monkeypatch.chdir(repo)
        _write_run(
            repo,
            [
                _unit(
                    "mimir-builder",
                    vendor="opencode",
                    model="opencode/muse-spark-1.2-contributor-free",
                    effort="max",
                    task="/work build feature",
                    status="pending",
                    branch=None,
                )
            ],
        )

        executed_cmds: list[list[str]] = []
        sent_prompts: list[str] = []
        original_run = orchestrate.run

        def mocked_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            executed_cmds.append(cmd)
            if cmd and cmd[0] == orchestrate.launcher():
                return subprocess.CompletedProcess(
                    cmd,
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "tab_id": "tab-mimir",
                            "pane_id": "pane-mimir",
                            "agent_name": "mimir-builder",
                        }
                    )
                    + "\n",
                    stderr="",
                )
            if cmd[:4] == ["herdr", "pane", "read", "pane-mimir"]:
                # Live picker output offering up to xhigh (Team Mimir scenario)
                picker_output = (
                    "Select a variant:\n> Default\n  minimal\n  low\n  medium\n  high\n  xhigh\n"
                )
                return subprocess.CompletedProcess(
                    cmd, returncode=0, stdout=picker_output, stderr=""
                )
            if cmd[:3] == ["herdr", "pane", "run"]:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
            if cmd[:3] == ["herdr", "agent", "prompt"]:
                sent_prompts.append(cmd[4] if len(cmd) > 4 else "")
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
            return cast(subprocess.CompletedProcess[str], original_run(cmd, **kwargs))

        monkeypatch.setattr(orchestrate, "run", mocked_run)
        monkeypatch.setattr(orchestrate, "await_ready", lambda _unit: True)
        monkeypatch.setattr(orchestrate, "took_the_task", lambda _unit: True)

        assert orchestrate.cmd_go(argparse.Namespace(limit=0)) == 0

        # Verify launch command passed through central launcher with model
        launcher_calls = [c for c in executed_cmds if c and c[0] == orchestrate.launcher()]
        assert len(launcher_calls) == 1
        launcher_argv = launcher_calls[0]
        assert "--no-focus" in launcher_argv
        assert "opencode" in launcher_argv
        assert "-m" in launcher_argv
        assert "opencode/muse-spark-1.2-contributor-free" in launcher_argv

        # Verify /variants was opened
        variant_open_calls = [
            c
            for c in executed_cmds
            if c[:4] == ["herdr", "pane", "run", "pane-mimir"] and c[4] == "/variants"
        ]
        assert len(variant_open_calls) == 1

        # Verify xhigh was selected (Team Mimir resolution for 'max' request)
        variant_select_calls = [
            c
            for c in executed_cmds
            if c[:4] == ["herdr", "pane", "run", "pane-mimir"] and c[4] == "xhigh"
        ]
        assert len(variant_select_calls) == 1

        # Verify task was submitted
        assert any("build feature" in p for p in sent_prompts)

        # Verify unit state and receipt
        r = orchestrate.Run.load()
        unit = r.units[0]
        assert unit.status == "running"
        assert unit.variant == "xhigh"
        assert unit.launch_receipt["vendor"] == "opencode"
        assert unit.launch_receipt["provider"] == "opencode"
        assert unit.launch_receipt["model"] == "opencode/muse-spark-1.2-contributor-free"
        assert unit.launch_receipt["variant"] == "xhigh"
        assert unit.launch_receipt["pane"] == "pane-mimir"
        assert unit.launch_receipt["verified"] is True
        assert "variant xhigh verified" in unit.note

    def test_non_opencode_vendor_does_not_send_variants(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Non-OpenCode vendors retain native controls and never receive /variants."""
        monkeypatch.chdir(repo)
        _write_run(
            repo,
            [
                _unit(
                    "claude-worker",
                    vendor="claude",
                    model="opus",
                    effort="high",
                    task="do work",
                    status="pending",
                    branch=None,
                )
            ],
        )

        executed_cmds: list[list[str]] = []
        original_run = orchestrate.run

        def mocked_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            executed_cmds.append(cmd)
            if cmd and cmd[0] == orchestrate.launcher():
                return subprocess.CompletedProcess(
                    cmd,
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "tab_id": "tab-claude",
                            "pane_id": "pane-claude",
                            "agent_name": "claude-worker",
                        }
                    )
                    + "\n",
                    stderr="",
                )
            if cmd[:3] == ["herdr", "agent", "prompt"]:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
            return cast(subprocess.CompletedProcess[str], original_run(cmd, **kwargs))

        monkeypatch.setattr(orchestrate, "run", mocked_run)
        monkeypatch.setattr(orchestrate, "await_ready", lambda _unit: True)
        monkeypatch.setattr(orchestrate, "took_the_task", lambda _unit: True)

        assert orchestrate.cmd_go(argparse.Namespace(limit=0)) == 0

        # Verify no /variants commands were sent
        for cmd in executed_cmds:
            assert "/variants" not in cmd

        # Verify launch receipt recorded
        r = orchestrate.Run.load()
        unit = r.units[0]
        assert unit.status == "running"
        assert unit.launch_receipt["vendor"] == "claude"
        assert unit.launch_receipt["model"] == "opus"
        assert unit.launch_receipt["variant"] == "high"

    def test_opencode_picker_failure_fails_loudly_before_task_submission(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Picker read failure marks unit failed and never submits the task."""
        monkeypatch.chdir(repo)
        _write_run(
            repo,
            [
                _unit(
                    "mimir-builder",
                    vendor="opencode",
                    model="opencode/muse-spark-1.2-contributor-free",
                    effort="max",
                    task="do work",
                    status="pending",
                    branch=None,
                )
            ],
        )

        sent_prompts: list[str] = []
        original_run = orchestrate.run

        def mocked_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            if cmd and cmd[0] == orchestrate.launcher():
                return subprocess.CompletedProcess(
                    cmd,
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "tab_id": "tab-mimir",
                            "pane_id": "pane-mimir",
                            "agent_name": "mimir-builder",
                        }
                    )
                    + "\n",
                    stderr="",
                )
            if cmd[:4] == ["herdr", "pane", "read", "pane-mimir"]:
                # Empty output simulates picker failure
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
            if cmd[:3] == ["herdr", "pane", "run"]:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
            if cmd[:3] == ["herdr", "agent", "prompt"]:
                sent_prompts.append(cmd[4] if len(cmd) > 4 else "")
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
            return cast(subprocess.CompletedProcess[str], original_run(cmd, **kwargs))

        monkeypatch.setattr(orchestrate, "run", mocked_run)
        monkeypatch.setattr(orchestrate, "await_ready", lambda _unit: True)

        assert orchestrate.cmd_go(argparse.Namespace(limit=0)) == 0

        # Verify task was NOT sent
        assert sent_prompts == []

        # Verify unit marked failed with clear note
        r = orchestrate.Run.load()
        unit = r.units[0]
        assert unit.status == "failed"
        assert "unable to read live picker options" in unit.note

    def test_opencode_unavailable_variant_fails_loudly_before_task_submission(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Requesting an unavailable exact variant stops before task submission."""
        monkeypatch.chdir(repo)
        _write_run(
            repo,
            [
                _unit(
                    "mimir-builder",
                    vendor="opencode",
                    model="opencode/muse-spark-1.2-contributor-free",
                    effort="ultra",
                    task="do work",
                    status="pending",
                    branch=None,
                )
            ],
        )

        sent_prompts: list[str] = []
        original_run = orchestrate.run

        def mocked_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            if cmd and cmd[0] == orchestrate.launcher():
                return subprocess.CompletedProcess(
                    cmd,
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "tab_id": "tab-mimir",
                            "pane_id": "pane-mimir",
                            "agent_name": "mimir-builder",
                        }
                    )
                    + "\n",
                    stderr="",
                )
            if cmd[:4] == ["herdr", "pane", "read", "pane-mimir"]:
                picker_output = "> Default\n  minimal\n  low\n  medium\n  high\n  xhigh\n"
                return subprocess.CompletedProcess(
                    cmd, returncode=0, stdout=picker_output, stderr=""
                )
            if cmd[:3] == ["herdr", "pane", "run"]:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
            if cmd[:3] == ["herdr", "agent", "prompt"]:
                sent_prompts.append(cmd[4] if len(cmd) > 4 else "")
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
            return cast(subprocess.CompletedProcess[str], original_run(cmd, **kwargs))

        monkeypatch.setattr(orchestrate, "run", mocked_run)
        monkeypatch.setattr(orchestrate, "await_ready", lambda _unit: True)

        assert orchestrate.cmd_go(argparse.Namespace(limit=0)) == 0

        # Verify task was NOT sent
        assert sent_prompts == []

        # Verify unit marked failed
        r = orchestrate.Run.load()
        unit = r.units[0]
        assert unit.status == "failed"
        assert "ultra" in unit.note
        assert "not available in live picker options" in unit.note

    def test_mismatched_working_directory_stops_before_task_submission(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Working directory mismatch closes run session and fails loudly before task submission."""
        monkeypatch.chdir(repo)
        _write_run(
            repo,
            [
                _unit(
                    "worker",
                    vendor="claude",
                    task="do work",
                    status="pending",
                    branch=None,
                )
            ],
        )

        closed_tabs: list[str] = []
        sent_prompts: list[str] = []
        original_run = orchestrate.run

        def mocked_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            if cmd and cmd[0] == orchestrate.launcher():
                return subprocess.CompletedProcess(
                    cmd,
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "tab_id": "tab-bad-cwd",
                            "pane_id": "pane-bad-cwd",
                            "agent_name": "worker",
                        }
                    )
                    + "\n",
                    stderr="",
                )
            if cmd[:3] == ["herdr", "tab", "close"]:
                closed_tabs.append(cmd[3])
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
            if cmd[:3] == ["herdr", "agent", "prompt"]:
                sent_prompts.append(cmd[4] if len(cmd) > 4 else "")
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
            return cast(subprocess.CompletedProcess[str], original_run(cmd, **kwargs))

        monkeypatch.setattr(orchestrate, "run", mocked_run)
        monkeypatch.setattr(orchestrate, "await_ready", lambda _unit: True)
        monkeypatch.setattr(
            orchestrate,
            "live_agents",
            lambda: [{"pane_id": "pane-bad-cwd", "cwd": "/wrong/worktree/dir"}],
        )

        assert orchestrate.cmd_go(argparse.Namespace(limit=0)) == 0

        # Session closed and task never sent
        assert "tab-bad-cwd" in closed_tabs
        assert sent_prompts == []

        r = orchestrate.Run.load()
        unit = r.units[0]
        assert unit.status == "failed"
        assert "differs from unit worktree" in unit.note
