"""Run-state and documentation hygiene for the Orchestrate plugin."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "orchestrate"
SCRIPT = PLUGIN_ROOT / "skills" / "orchestrate" / "scripts" / "orchestrate.py"
README = PLUGIN_ROOT / "README.md"
SKILL = PLUGIN_ROOT / "skills" / "orchestrate" / "SKILL.md"


@pytest.fixture(scope="module")
def orchestrate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_orchestrate_hygiene", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=check, capture_output=True, text=True)


@pytest.fixture
def driven_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "driven"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "tracked.txt").write_text("base\n")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "base")
    return repo


@pytest.fixture
def launcher_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep start's real launcher discovery deterministic without replacing it."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    launcher = bin_dir / "agents"
    launcher.write_text("#!/bin/sh\nexit 0\n")
    launcher.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir), prepend=os.pathsep)


def _exclude_path(repo: Path) -> Path:
    raw = _git(repo, "rev-parse", "--git-path", "info/exclude").stdout.strip()
    path = Path(raw)
    return path if path.is_absolute() else repo / path


def _write_plan(repo: Path, *, run_id: str = "hygiene") -> Path:
    path = repo / ".orchestrate" / "tasks" / "start-plan.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"run_id": run_id, "source": "test", "units": []}))
    return path


@pytest.mark.usefixtures("launcher_on_path")
class TestLocalRunStateExclude:
    def test_start_preserves_existing_rules_and_excludes_fresh_run_state(
        self,
        orchestrate: ModuleType,
        driven_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        exclude_path = _exclude_path(driven_repo)
        before = "# operator rule\nlocal-cache/\n"
        exclude_path.write_text(before)
        plan = _write_plan(driven_repo)
        monkeypatch.chdir(driven_repo)

        assert orchestrate.cmd_start(argparse.Namespace(plan=str(plan), base=None)) == 0

        after = exclude_path.read_text()
        assert after.startswith(before)
        assert after.splitlines().count(".orchestrate/") == 1
        assert (
            _git(driven_repo, "check-ignore", "-q", ".orchestrate/run.json", check=False).returncode
            == 0
        )
        assert _git(driven_repo, "status", "--porcelain", "--untracked-files=all").stdout == ""

    def test_start_twice_does_not_duplicate_the_exclude_rule(
        self,
        orchestrate: ModuleType,
        driven_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        plan = _write_plan(driven_repo)
        monkeypatch.chdir(driven_repo)

        assert orchestrate.cmd_start(argparse.Namespace(plan=str(plan), base=None)) == 0
        assert orchestrate.cmd_start(argparse.Namespace(plan=str(plan), base=None)) == 0

        rules = _exclude_path(driven_repo).read_text().splitlines()
        assert rules.count(".orchestrate/") == 1

    def test_start_from_a_subdirectory_updates_only_the_driven_repository_exclude(
        self,
        orchestrate: ModuleType,
        driven_repo: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        plan = _write_plan(driven_repo)
        subdirectory = driven_repo / "docs" / "deep"
        subdirectory.mkdir(parents=True)
        stray_exclude = tmp_path / ".git" / "info" / "exclude"
        monkeypatch.chdir(subdirectory)

        assert orchestrate.cmd_start(argparse.Namespace(plan=str(plan), base=None)) == 0

        assert ".orchestrate/" in _exclude_path(driven_repo).read_text().splitlines()
        assert not stray_exclude.exists()
        assert (
            _git(driven_repo, "check-ignore", "-q", ".orchestrate/run.json", check=False).returncode
            == 0
        )

    def test_start_terminates_an_existing_final_rule_before_appending_the_exclude(
        self,
        orchestrate: ModuleType,
        driven_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        exclude_path = _exclude_path(driven_repo)
        exclude_path.write_text("local-cache/")
        plan = _write_plan(driven_repo)
        monkeypatch.chdir(driven_repo)

        assert orchestrate.cmd_start(argparse.Namespace(plan=str(plan), base=None)) == 0

        assert exclude_path.read_text() == "local-cache/\n.orchestrate/\n"

    @pytest.mark.parametrize("run_id", ["", "/tmp/escape", "nested/run", "nested\\run", ".", ".."])
    def test_start_refuses_a_run_id_that_is_not_one_path_component(
        self,
        orchestrate: ModuleType,
        driven_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        run_id: str,
    ) -> None:
        plan = _write_plan(driven_repo, run_id=run_id)
        monkeypatch.chdir(driven_repo)

        with pytest.raises(SystemExit, match="run id"):
            orchestrate.cmd_start(argparse.Namespace(plan=str(plan), base=None))

        assert not (driven_repo / ".orchestrate" / "run.json").exists()


def test_readme_references_only_python_modules_the_plugin_ships() -> None:
    references = set(
        re.findall(
            r"(?<![A-Za-z0-9_.-])((?:skills/orchestrate/)?scripts/[A-Za-z0-9_.-]+\.py)",
            README.read_text(),
        )
    )
    assert references == {
        "skills/orchestrate/scripts/herdr_events.py",
        "skills/orchestrate/scripts/orchestrate.py",
    }
    assert all((PLUGIN_ROOT / reference).is_file() for reference in references)


def test_skill_keeps_hand_authored_briefs_with_the_run() -> None:
    skill = " ".join(SKILL.read_text().split())
    assert "Hand-authored briefs belong in `.orchestrate/tasks/`" in skill
    assert "give the unit the brief's absolute path" in skill
