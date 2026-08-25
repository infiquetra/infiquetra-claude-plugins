"""Honest delivery notes and readable per-unit status reporting.

The delivery check is deliberately only a warning: its short observation window has produced
false positives on sessions that later committed useful work.  The warning must therefore stay
visible without changing settlement, preserve any earlier handover note, and disappear once git
shows that the unit produced work.  These tests use a real temporary repository for every git
claim; only Herdr's session readings are supplied by the test.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
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
    spec = importlib.util.spec_from_file_location("_orchestrate_status_and_notes", SCRIPT)
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
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    _commit(path, "base.txt")
    _git(path, "branch", "orch/r1")
    return path


def _make_unit_branch(repo: Path, name: str, *, commit: bool = False, land: bool = False) -> None:
    branch = f"orch/r1-{name}"
    _git(repo, "checkout", "-b", branch, "orch/r1")
    if commit:
        _commit(repo, f"{name}.txt")
    if land:
        _git(repo, "checkout", "orch/r1")
        _git(repo, "merge", "--no-ff", "--no-edit", branch)
    _git(repo, "checkout", "main")


def _unit(name: str, **overrides: Any) -> dict[str, Any]:
    unit: dict[str, Any] = {
        "name": name,
        "vendor": "claude",
        "task": "do the work",
        "branch": f"orch/r1-{name}",
        "status": "running",
    }
    unit.update(overrides)
    return unit


def _write_run(repo: Path, units: list[dict[str, Any]]) -> None:
    base = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    path = repo / ".orchestrate" / "run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_id": "r1",
                "source": "a test",
                "base": base,
                "branch": "orch/r1",
                "units": units,
            }
        )
    )


def _read_unit(repo: Path, name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((repo / ".orchestrate" / "run.json").read_text())
    return next(unit for unit in payload["units"] if unit["name"] == name)


def _agents(*states: tuple[str, str]) -> list[dict[str, str]]:
    return [{"name": name, "agent_status": status} for name, status in states]


def test_delivery_warning_appends_to_the_file_handover_note(
    orchestrate: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The warning must not erase where the session's full task was handed over."""
    monkeypatch.chdir(tmp_path)
    launcher = tmp_path / "test-agent-launcher"
    launcher.write_text("#!/bin/sh\nexit 0\n")
    launcher.chmod(0o755)
    monkeypatch.setenv("ORCHESTRATE_AGENT_LAUNCHER", str(launcher))
    unit = orchestrate.Unit(name="review", vendor="qwen", task="x" * 900)
    orchestrate.pane_text(unit, unit.task)
    handover_note = unit.note

    completed = subprocess.CompletedProcess(
        ["agents"],
        returncode=0,
        stdout='{"tab_id":"tab-1","agent_name":"review","pane_id":"pane-1"}\n',
        stderr="",
    )
    monkeypatch.setattr(orchestrate, "run", lambda *_args, **_kwargs: completed)
    monkeypatch.setattr(orchestrate, "await_ready", lambda _unit: True)
    monkeypatch.setattr(orchestrate, "send", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestrate, "took_the_task", lambda _unit: False)
    monkeypatch.setattr(
        orchestrate,
        "agent_row",
        lambda _unit, _agents=None: {
            "pane_id": "pane-1",
            "agent": "qwen",
            "interactive_ready": True,
        },
    )

    orchestrate.launch(unit)

    assert handover_note in unit.note
    assert orchestrate.DELIVERY_WARNING in unit.note
    assert unit.note == f"{handover_note}; {orchestrate.DELIVERY_WARNING}"


def test_long_task_handover_appends_after_the_setup_prompt_fallback_note(
    orchestrate: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the production ordering: setup fallback first, then the long task handover."""
    monkeypatch.chdir(tmp_path)
    unit = orchestrate.Unit(
        name="review",
        vendor="qwen",
        task="x" * 900,
        setup=["/effort high"],
    )

    def pane_fallback(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            cmd,
            returncode=1 if cmd[:3] == ["herdr", "agent", "prompt"] else 0,
            stdout="",
            stderr="prompt unavailable",
        )

    monkeypatch.setattr(orchestrate, "run", pane_fallback)

    orchestrate.send(unit, "pane-1")

    assert unit.note.startswith("prompted through its pane")
    assert "; task handed over as a file, too long to type:" in unit.note


def test_long_task_without_setup_keeps_both_pane_fallback_diagnostics(
    orchestrate: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The task-file writer runs before the pane-fallback writer on the default setup path."""
    monkeypatch.chdir(tmp_path)
    unit = orchestrate.Unit(name="review", vendor="qwen", task="x" * 900)

    def pane_fallback(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            cmd,
            returncode=1 if cmd[:3] == ["herdr", "agent", "prompt"] else 0,
            stdout="",
            stderr="prompt unavailable",
        )

    monkeypatch.setattr(orchestrate, "run", pane_fallback)

    orchestrate.send(unit, "pane-1")

    assert unit.note.startswith("task handed over as a file, too long to type:")
    assert (
        "; prompted through its pane; this agent does not report interactive readiness" in unit.note
    )


def test_status_uses_only_the_batched_commit_status_helper(orchestrate: ModuleType) -> None:
    assert hasattr(orchestrate, "unit_commit_statuses")
    assert not hasattr(orchestrate, "unit_commit_status")


def test_settle_clears_only_the_delivery_warning_after_the_first_commit(
    orchestrate: ModuleType,
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _make_unit_branch(repo, "alpha", commit=True)
    _write_run(
        repo,
        [_unit("alpha", note=f"task handed over as a file; {orchestrate.DELIVERY_WARNING}")],
    )
    monkeypatch.chdir(repo)
    monkeypatch.setattr(orchestrate, "live_agents", lambda: _agents(("alpha", "working")))

    assert orchestrate.cmd_settle(argparse.Namespace(interval=20, once=True)) == 0

    saved = _read_unit(repo, "alpha")
    assert saved["status"] == "running"
    assert saved["note"] == "task handed over as a file"


def test_check_reports_a_delivery_warning_with_no_commits(
    orchestrate: ModuleType,
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _make_unit_branch(repo, "alpha")
    _write_run(repo, [_unit("alpha", note=orchestrate.DELIVERY_WARNING)])
    monkeypatch.chdir(repo)
    monkeypatch.setattr(orchestrate, "live_agents", lambda: _agents(("alpha", "working")))

    assert orchestrate.cmd_check(argparse.Namespace()) == 1
    output = capsys.readouterr().out
    assert "DELIVERY WARNING alpha" in output
    assert "branch has no commits" in output


def test_status_sizes_columns_collapses_tasks_and_shows_git_and_notes(
    orchestrate: ModuleType,
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    model = "model-123456789012345"
    assert len(model) == 21
    _make_unit_branch(repo, "alpha", commit=True)
    _make_unit_branch(repo, "beta", commit=True, land=True)
    _write_run(
        repo,
        [
            _unit(
                "alpha",
                model=model,
                effort="high",
                status="done",
                task="first line\nsecond line\tthird line",
                note=orchestrate.DELIVERY_WARNING,
            ),
            _unit("beta", model="short", effort="low", status="done", task="landed task"),
        ],
    )
    monkeypatch.chdir(repo)
    original_run = orchestrate.run
    history_walks: list[list[str]] = []

    def count_history_walks(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:4] == ["git", "log", "--first-parent", "--merges"]:
            history_walks.append(cmd)
        return cast(subprocess.CompletedProcess[str], original_run(cmd, **kwargs))

    monkeypatch.setattr(orchestrate, "run", count_history_walks)

    assert orchestrate.cmd_status(argparse.Namespace()) == 0
    lines = capsys.readouterr().out.splitlines()
    header = next(line for line in lines if line.startswith("unit "))
    rule = lines[lines.index(header) + 1]
    alpha = next(line for line in lines if line.startswith("alpha "))
    beta = next(line for line in lines if line.startswith("beta "))

    assert len([line for line in lines if line.startswith(("alpha ", "beta "))]) == 2
    assert "first line second line third line" in alpha
    assert not any(line.startswith(("second line", "third line")) for line in lines)
    assert "SENT BUT NEVER STARTED" in alpha
    assert orchestrate.DELIVERY_WARNING not in alpha
    assert len(alpha) <= len(rule)
    assert len(history_walks) == 1

    model_start = header.index("model")
    effort_start = header.index("effort")
    commits_start = header.index("commits")
    landed_start = header.index("landed")
    task_start = header.index("task")
    note_start = header.index("note")
    assert alpha[model_start:effort_start].strip() == model
    assert alpha[commits_start:landed_start].strip() == "1"
    assert beta[commits_start:landed_start].strip() == "1"
    assert alpha[landed_start:task_start].strip() == "no"
    assert beta[landed_start:task_start].strip() == "yes"
    assert alpha[note_start:] == orchestrate.status_cell(orchestrate.DELIVERY_WARNING)


def test_settle_leaves_a_warned_zero_commit_unit_running_after_two_idle_readings(
    orchestrate: ModuleType,
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _make_unit_branch(repo, "alpha")
    _write_run(repo, [_unit("alpha", note=orchestrate.DELIVERY_WARNING)])
    readings = iter([_agents(("alpha", "idle")), _agents(("alpha", "idle"))])
    monkeypatch.chdir(repo)
    monkeypatch.setattr(orchestrate, "live_agents", lambda: next(readings))
    monkeypatch.setattr(orchestrate.time, "sleep", lambda _seconds: None)

    assert orchestrate.cmd_settle(argparse.Namespace(interval=20, once=False)) == 0

    saved = _read_unit(repo, "alpha")
    assert saved["status"] == "running"
    assert saved["note"] == orchestrate.DELIVERY_WARNING


def test_settle_finishes_a_warned_unit_with_commits_and_clears_warning(
    orchestrate: ModuleType,
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _make_unit_branch(repo, "alpha", commit=True)
    _write_run(repo, [_unit("alpha", note=orchestrate.DELIVERY_WARNING)])
    readings = iter([_agents(("alpha", "idle")), _agents(("alpha", "idle"))])
    monkeypatch.chdir(repo)
    monkeypatch.setattr(orchestrate, "live_agents", lambda: next(readings))
    monkeypatch.setattr(orchestrate.time, "sleep", lambda _seconds: None)

    assert orchestrate.cmd_settle(argparse.Namespace(interval=20, once=False)) == 0

    saved = _read_unit(repo, "alpha")
    assert saved["status"] == "done"
    assert saved["note"] == ""
