"""Evidence-based settlement: settle records done only with branch evidence, never from pane state alone.

Three observed incidents across Team Mimir sessions drove this contract:
1. Stale `done`: Herdr reported `done` predating a supplemental prompt, but the branch had no
   commits. Settle must leave the unit running instead of falsely calling it done.
2. Idle-but-stuck: A unit with a SIGTTIN-suspended background child reported `done` repeatedly while
   stuck. Settle must never mark an idle unit done without commits on its branch.
3. Closed-session-after-commit vs gone-without-commits: When operator cleanup closed a worker session
   after its commits were authored, settle previously called it failed. Settle must mark a closed
   session with commits `done`, while a closed session with no commits produces the distinct
   `orphaned` state.
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
    spec = importlib.util.spec_from_file_location("_orchestrate_settlement", SCRIPT)
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
    """A git repo with a base commit, run branch, and multiple unit branches."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "test@example.com")
    _git(r, "config", "user.name", "Test")
    _commit(r, "base.txt")
    _git(r, "branch", "orch/r1")

    # Committed units (have branch completion evidence)
    for unit in ("committed-alpha", "committed-beta"):
        _git(r, "checkout", "-b", f"orch/r1-{unit}", "orch/r1")
        _commit(r, f"{unit}.txt")
        _git(r, "checkout", "main")

    # Uncommitted units (sitting at base, zero commits)
    for unit in ("empty-stale", "empty-stuck", "empty-gone"):
        _git(r, "branch", f"orch/r1-{unit}", "orch/r1")

    return r


def _write_run(repo: Path, units: list[dict[str, Any]], **over: Any) -> None:
    base = subprocess.run(
        ["git", "rev-parse", "main"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    payload = {
        "run_id": "r1",
        "source": "settlement-test",
        "base": base,
        "branch": "orch/r1",
        "units": units,
        **over,
    }
    path = repo / ".orchestrate" / "run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _read_units(repo: Path) -> dict[str, dict[str, Any]]:
    raw = json.loads((repo / ".orchestrate" / "run.json").read_text())
    units: list[dict[str, Any]] = raw["units"]
    return {u["name"]: u for u in units}


def _unit(name: str, **over: Any) -> dict[str, Any]:
    return {
        "name": name,
        "vendor": "claude",
        "task": "do work",
        "branch": f"orch/r1-{name}",
        "status": "running",
        **over,
    }


def _agent(name: str, status: str) -> dict[str, str]:
    return {"name": name, "agent_status": status}


class FakeHerdr:
    def __init__(self, readings: list[list[dict[str, str]]]) -> None:
        self.readings = list(readings)
        self.calls = 0

    def __call__(self) -> list[dict[str, str]]:
        self.calls += 1
        assert self.readings, f"herdr polled {self.calls} times but no more readings configured"
        return self.readings.pop(0)


def _patch_settle(
    orchestrate: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    readings: list[list[dict[str, str]]],
) -> tuple[FakeHerdr, list[float]]:
    fake = FakeHerdr(readings)
    monkeypatch.setattr(orchestrate, "live_agents", fake)
    slept: list[float] = []
    monkeypatch.setattr(orchestrate.time, "sleep", slept.append)
    return fake, slept


class TestIncidentShape1StaleDoneWithoutCommits:
    """Incident 1: A stale done reading predating a prompt must not settle done without commits."""

    def test_stale_done_with_no_commits_stays_running(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(repo, [_unit("empty-stale")])
        _patch_settle(
            orchestrate,
            monkeypatch,
            [[_agent("empty-stale", "done")], [_agent("empty-stale", "done")]],
        )
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_settle(argparse.Namespace(interval=20, once=False)) == 0
        saved = _read_units(repo)["empty-stale"]
        assert saved["status"] == "running"
        out = capsys.readouterr().out
        assert "empty-stale" in out
        assert "still moving (no commits)" in out

    def test_idle_pane_with_no_commits_stays_running(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(repo, [_unit("empty-stale")])
        _patch_settle(
            orchestrate,
            monkeypatch,
            [[_agent("empty-stale", "idle")], [_agent("empty-stale", "idle")]],
        )
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_settle(argparse.Namespace(interval=20, once=False)) == 0
        saved = _read_units(repo)["empty-stale"]
        assert saved["status"] == "running"
        out = capsys.readouterr().out
        assert "still moving (no commits)" in out


class TestIncidentShape2IdleStuckWithoutCommits:
    """Incident 2: A stuck session reporting idle/done (e.g. SIGTTIN suspended child) stays running."""

    def test_stuck_unit_reporting_done_six_times_never_settles_without_evidence(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("empty-stuck")])
        monkeypatch.chdir(repo)

        # 3 consecutive settle passes (each with 2 confirming readings = 6 readings total)
        for _ in range(3):
            _patch_settle(
                orchestrate,
                monkeypatch,
                [[_agent("empty-stuck", "done")], [_agent("empty-stuck", "done")]],
            )
            assert orchestrate.cmd_settle(argparse.Namespace(interval=20, once=False)) == 0
            saved = _read_units(repo)["empty-stuck"]
            assert saved["status"] == "running"


class TestIncidentShape3SessionGoneOutcomes:
    """Incident 3: Session gone with commits settles done; session gone without commits is orphaned."""

    def test_session_closed_after_commit_settles_done_never_failed(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Committed work whose Herdr session was closed settles done, not failed."""
        _write_run(repo, [_unit("committed-alpha")])
        _patch_settle(orchestrate, monkeypatch, [[], []])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_settle(argparse.Namespace(interval=20, once=False)) == 0
        saved = _read_units(repo)["committed-alpha"]
        assert saved["status"] == "done"
        out = capsys.readouterr().out
        assert "committed-alpha: session gone with commits -> done" in out

    def test_session_gone_without_commits_yields_distinct_orphaned_state(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A session that disappeared without commits is marked orphaned with a distinct note."""
        _write_run(repo, [_unit("empty-gone")])
        _patch_settle(orchestrate, monkeypatch, [[], []])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_settle(argparse.Namespace(interval=20, once=False)) == 0
        saved = _read_units(repo)["empty-gone"]
        assert saved["status"] == "orphaned"
        assert saved["status"] == orchestrate.ORPHANED
        assert saved["status"] != orchestrate.FAILED
        assert saved["status"] != orchestrate.DONE
        assert "session disappeared without commits" in saved["note"]
        out = capsys.readouterr().out
        assert "empty-gone: session gone -> orphaned" in out


class TestSettlementUnderOnceFlag:
    """Settlement under --once still requires branch evidence."""

    def test_once_settles_committed_idle_unit_done(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("committed-alpha")])
        _patch_settle(orchestrate, monkeypatch, [[_agent("committed-alpha", "idle")]])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_settle(argparse.Namespace(interval=20, once=True)) == 0
        saved = _read_units(repo)["committed-alpha"]
        assert saved["status"] == "done"

    def test_once_leaves_uncommitted_idle_unit_running(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("empty-stale")])
        _patch_settle(orchestrate, monkeypatch, [[_agent("empty-stale", "idle")]])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_settle(argparse.Namespace(interval=20, once=True)) == 0
        saved = _read_units(repo)["empty-stale"]
        assert saved["status"] == "running"

    def test_once_settles_committed_gone_unit_done(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("committed-alpha")])
        _patch_settle(orchestrate, monkeypatch, [[]])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_settle(argparse.Namespace(interval=20, once=True)) == 0
        saved = _read_units(repo)["committed-alpha"]
        assert saved["status"] == "done"

    def test_once_settles_uncommitted_gone_unit_orphaned(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("empty-gone")])
        _patch_settle(orchestrate, monkeypatch, [[]])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_settle(argparse.Namespace(interval=20, once=True)) == 0
        saved = _read_units(repo)["empty-gone"]
        assert saved["status"] == "orphaned"


class TestLandedWorkSettlement:
    """A unit whose commits were already merged onto the run branch counts as produced work."""

    def test_session_gone_for_already_landed_unit_settles_done(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Merge committed-beta into the run branch
        _git(repo, "checkout", "orch/r1")
        _git(repo, "merge", "--no-ff", "-m", "merge beta", "orch/r1-committed-beta")
        _git(repo, "checkout", "main")

        _write_run(repo, [_unit("committed-beta")])
        _patch_settle(orchestrate, monkeypatch, [[], []])
        monkeypatch.chdir(repo)

        assert orchestrate.cmd_settle(argparse.Namespace(interval=20, once=False)) == 0
        saved = _read_units(repo)["committed-beta"]
        assert saved["status"] == "done"
