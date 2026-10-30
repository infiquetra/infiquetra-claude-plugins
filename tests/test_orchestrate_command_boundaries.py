"""Read-only discovery, confirmation and atomic state publication use real Orchestrate code."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from orchestrate_support import load_orchestrate

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py"


@pytest.fixture
def orch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    def deny_process(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("uncontrolled host process in discovery test")

    monkeypatch.setattr(subprocess, "run", deny_process)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("AGENT_LAUNCHER_ROOT", raising=False)
    return load_orchestrate("_orchestrate_command_boundaries", SCRIPT)


def plant_capabilities(root: Path) -> Path:
    (root / "commands").mkdir(parents=True)
    (root / "commands/plan.md").write_text("plan")
    (root / "commands/README.md").write_text("ignore documentation")
    (root / "commands/qa").mkdir()
    (root / "commands/qa/SKILL.md").write_text("qa")
    (root / "commands/not-a-skill").mkdir()
    return root / "commands"


def test_installed_capability_discovery_uses_only_real_command_and_skill_files(
    orch: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    commands = plant_capabilities(tmp_path)
    monkeypatch.setattr(
        orch, "SAGA_INSTALL", {"codex": [str(commands)], "claude": [str(commands)], "grok": []}
    )
    assert orch.saga_capabilities("codex") == ["plan", "qa"]
    assert orch.saga_capabilities("unknown") == []
    monkeypatch.setattr(
        orch, "roster", lambda: [("codex", "flags"), ("grok", "none"), ("claude", "flags")]
    )
    assert orch.cmd_saga(argparse.Namespace(cap="plan")) == 0
    output = capsys.readouterr().out
    assert "$saga:plan" in output and "/saga:plan" in output
    assert "grok" in output and "NO SAGA INSTALLED" in output and "without saga: grok" in output
    assert orch.cmd_saga(argparse.Namespace(cap="code-review")) == 0
    assert "no `code-review` among its 2 capabilities" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("models_requested", "probe_requested"), [(False, False), (True, False), (False, True)]
)
def test_roster_explains_installed_capabilities_models_and_flag_drift_without_host_calls(
    orch: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    models_requested: bool,
    probe_requested: bool,
) -> None:
    commands = plant_capabilities(tmp_path)
    monkeypatch.setattr(orch, "SAGA_INSTALL", {"codex": [str(commands)], "claude": [], "grok": []})
    monkeypatch.setattr(
        orch,
        "roster",
        lambda: [("codex", "model+effort"), ("claude", "model+effort"), ("grok", "model+effort")],
    )
    monkeypatch.setattr(orch, "launchable", lambda: ["codex", "claude", "grok", "future-vendor"])
    monkeypatch.setattr(
        orch, "favourites", lambda name: ["preferred-route"] if name == "codex" else []
    )
    monkeypatch.setattr(
        orch, "models", lambda name: ["route-a", "route-b", "route-c"] if name != "grok" else []
    )

    def probe(name: str) -> tuple[str, dict]:
        if name == "grok":
            raise SystemExit("fixture wrapper has no help")
        if name == "codex":
            return "help has no supported flags", {"model": False, "effort": False}
        return "--model --effort", {"model": True, "effort": True}

    monkeypatch.setattr(orch, "probe", probe)
    assert (
        orch.cmd_roster(argparse.Namespace(models=models_requested, probe=probe_requested, limit=1))
        == 0
    )
    output = capsys.readouterr().out
    assert "3 usable here" in output and "future-vendor" in output
    assert "not installed" in output and "2 capabilities" in output and "permission" in output
    assert "known but not available" in output and "note" in output
    if models_requested:
        assert "preferred-route" in output and "your favourites" in output
        assert "and 2 more" in output and "ask for the name" in output
    if probe_requested:
        assert (
            "DRIFT" in output
            and "mismatch(es)" in output
            and "could not run --help; skipped" in output
        )
    if not models_requested and not probe_requested:
        assert "roster --models" in output


def test_empty_roster_has_a_named_failure(
    orch: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(orch, "roster", lambda: [])
    assert orch.cmd_roster(argparse.Namespace(models=False, probe=False, limit=1)) == 1
    assert "could not read the wrapper" in capsys.readouterr().out


def test_roster_detects_newly_advertised_flags_and_reports_clean_help(
    orch: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(orch, "roster", lambda: [("qwen", "none")])
    monkeypatch.setattr(orch, "saga_capabilities", lambda name: [])
    monkeypatch.setattr(orch, "launchable", lambda: ["qwen"])
    monkeypatch.setattr(
        orch, "probe", lambda name: ("--model --effort", {"model": True, "effort": True})
    )
    monkeypatch.setattr(orch, "VENDOR_FLAGS", {"qwen": {}})
    assert orch.cmd_roster(argparse.Namespace(models=False, probe=True, limit=1)) == 0
    assert "advertises a model flag" in capsys.readouterr().out
    monkeypatch.setattr(orch, "probe", lambda name: ("", {"model": False, "effort": False}))
    assert orch.cmd_roster(argparse.Namespace(models=False, probe=True, limit=1)) == 0
    assert "no drift" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("value", "reason"), [("one", "integer"), ("1", "at least 2"), ("0", "at least 2")]
)
def test_wait_requires_multiple_numeric_confirmations(
    orch: ModuleType, value: str, reason: str
) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match=reason):
        orch.confirmation_count(value)
    assert orch.confirmation_count("3") == 3


@pytest.mark.parametrize(
    ("first", "observations", "expected", "sleeps"),
    [
        ("blocked", [], "blocked", []),
        ("working", [], None, []),
        ("idle", ["working"], None, [2]),
        ("done", ["blocked"], "blocked", [2]),
        ("idle", ["done", "idle"], "idle", [2, 2]),
    ],
)
def test_confirmed_stop_observes_consecutive_states_without_real_sleep(
    orch: ModuleType, first: str, observations: list[str], expected: str | None, sleeps: list[int]
) -> None:
    remaining = iter(observations)
    waited: list[int] = []
    result = orch.confirmed_stop(
        first, lambda: next(remaining), interval=2, needed=3, sleep=waited.append
    )
    assert result == expected and waited == sleeps


def test_confirmation_deadline_does_not_overrun_or_poll_again(orch: ModuleType) -> None:
    observed = []
    waited: list[float] = []

    def poll() -> str:
        observed.append(True)
        return "idle"

    assert (
        orch.confirmed_stop(
            "idle",
            poll,
            interval=2,
            needed=2,
            sleep=waited.append,
            deadline=10,
            monotonic=lambda: 9.5,
        )
        is None
    )
    assert waited == [0.5] and observed == []
    assert (
        orch.confirmed_stop(
            "done",
            poll,
            interval=2,
            needed=2,
            sleep=waited.append,
            deadline=10,
            monotonic=lambda: 11,
        )
        is None
    )
    assert waited == [0.5] and observed == []
    with pytest.raises(ValueError, match="at least two"):
        orch.confirmed_stop("idle", poll, interval=2, needed=1)


@pytest.mark.parametrize("fail_publish", [False, True])
def test_atomic_state_publication_retains_previous_data_and_cleans_scratch(
    orch: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_publish: bool
) -> None:
    target = tmp_path / "state/run.json"
    target.parent.mkdir()
    target.write_text('{"old": true}')
    if fail_publish:

        def denied(self: Path, destination: Path) -> Path:
            raise PermissionError("controlled publish refusal")

        monkeypatch.setattr(Path, "replace", denied)
        with pytest.raises(PermissionError, match="publish refusal"):
            orch._atomic_write_text(target, '{"new": true}')
        assert json.loads(target.read_text()) == {"old": True}
    else:
        orch._atomic_write_text(target, '{"new": true}')
        assert json.loads(target.read_text()) == {"new": True}
    assert list(target.parent.iterdir()) == [target]
