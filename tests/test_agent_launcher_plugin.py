"""Release-surface contract for the agent-launcher plugin (#777, #841)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "agent-launcher"
ORCHESTRATE_ROOT = ROOT / "plugins" / "orchestrate"
MARKETPLACE = "infiquetra-plugins"
EXPECTED_REMEDIATION = "claude plugin install agent-launcher@infiquetra-plugins"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter(path: Path) -> dict[str, str]:
    lines = _read(path).splitlines()
    assert lines[0] == "---"
    data: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return data
        if ": " in line:
            key, value = line.split(": ", 1)
            data[key] = value.strip()
    raise AssertionError(f"{path} has no closing frontmatter marker")


def _install_plugin(cache: Path, plugin: str, version: str, *, parts: tuple[str, ...]) -> Path:
    """Copy the named subtrees of a repo plugin into a simulated cache."""
    destination = cache / plugin / version
    for part in parts:
        source = ROOT / "plugins" / plugin / part
        shutil.copytree(source, destination / part)
    return destination


def _run_installed_orchestrate(
    script_path: Path,
    args: list[str],
    *,
    cwd: Path,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute installed orchestrate.py in a clean subprocess."""
    clean_env = {
        "HOME": str(cwd),
        "PATH": os.environ.get("PATH", ""),
    }
    # Explicitly exclude any repo/machine override variables
    for key in ("AGENT_LAUNCHER_ROOT", "CLAUDE_PLUGIN_ROOT", "PYTHONPATH"):
        clean_env.pop(key, None)
    if env_overrides:
        clean_env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=clean_env,
        timeout=30,
    )


def test_agent_launcher_metadata_is_marketplace_registered() -> None:
    plugin_json = json.loads(_read(PLUGIN_ROOT / ".claude-plugin" / "plugin.json"))
    marketplace = json.loads(_read(ROOT / ".claude-plugin" / "marketplace.json"))
    marketplace_entry = next(
        plugin for plugin in marketplace["plugins"] if plugin["name"] == "agent-launcher"
    )

    assert plugin_json["name"] == "agent-launcher"
    assert plugin_json["version"] == "1.2.0"
    assert "Herdr" in plugin_json["description"]
    assert {"agent-launcher", "agents", "herdr", "launch", "sessions"} <= set(
        plugin_json["keywords"]
    )
    assert marketplace_entry["source"] == "./plugins/agent-launcher"
    assert marketplace_entry["version"] == plugin_json["version"]
    assert marketplace_entry["keywords"] == plugin_json["keywords"]


def test_orchestrate_declares_agent_launcher_dependency_in_metadata() -> None:
    """Distribution metadata keeps Orchestrate and Agent Launcher consistently registered (#841)."""
    orch_json = json.loads(_read(ORCHESTRATE_ROOT / ".claude-plugin" / "plugin.json"))
    marketplace = json.loads(_read(ROOT / ".claude-plugin" / "marketplace.json"))

    assert "dependencies" in orch_json
    # The Claude plugin loader requires an array here and rejects the whole manifest for
    # any other type, which made Orchestrate unloadable from 2.0.0 through 3.0.6 (#871).
    declared = orch_json["dependencies"]
    assert isinstance(declared, list), (
        f"dependencies must be an array, got {type(declared).__name__}"
    )
    floors = {entry["name"]: entry.get("version") for entry in declared if isinstance(entry, dict)}
    assert floors.get("agent-launcher") == ">=1.2.0", declared

    orch_entry = next(
        plugin for plugin in marketplace["plugins"] if plugin["name"] == "orchestrate"
    )
    launcher_entry = next(
        plugin for plugin in marketplace["plugins"] if plugin["name"] == "agent-launcher"
    )
    assert orch_entry["version"] == orch_json["version"]
    assert launcher_entry["version"] == "1.2.0"


def test_agent_launcher_packaged_files() -> None:
    expected = (
        ".claude-plugin/plugin.json",
        "README.md",
        "CHANGELOG.md",
        "skills/agent-launcher/SKILL.md",
        "skills/agent-launcher/scripts/composer.py",
        "skills/agent-launcher/scripts/launcher.py",
        "tests/test_launcher_contract.py",
    )
    for relative_path in expected:
        assert (PLUGIN_ROOT / relative_path).exists(), f"missing {relative_path}"
    assert _frontmatter(PLUGIN_ROOT / "skills" / "agent-launcher" / "SKILL.md")["name"] == (
        "agent-launcher"
    )
    assert not (PLUGIN_ROOT / "skills" / "herdr").exists()


def test_installed_orchestrate_roster_fails_fast_without_launcher(tmp_path: Path) -> None:
    """Simulate installed layout with no discoverable launcher: roster fails fast (#841)."""
    cache = tmp_path / "cache" / MARKETPLACE
    cache.mkdir(parents=True)
    orch_install = _install_plugin(
        cache, "orchestrate", "3.0.1", parts=(".claude-plugin", "skills")
    )
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"

    result = _run_installed_orchestrate(script, ["roster"], cwd=tmp_path)
    assert result.returncode != 0
    err = result.stderr + result.stdout
    assert "agent-launcher plugin not found" in err
    assert EXPECTED_REMEDIATION in err
    assert "/Users/" not in err
    assert "AGENT_LAUNCHER_ROOT" not in err


def test_installed_orchestrate_expand_and_go_fail_before_worktree_creation(tmp_path: Path) -> None:
    """expand and go fail preflight before creating sessions or worktrees (#841)."""
    cache = tmp_path / "cache" / MARKETPLACE
    cache.mkdir(parents=True)
    orch_install = _install_plugin(
        cache, "orchestrate", "3.0.1", parts=(".claude-plugin", "skills")
    )
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"

    # 1. Initialize a real git repo for orchestrate run commands
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo_dir), check=True)
    (repo_dir / "README.md").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=str(repo_dir), check=True, capture_output=True
    )

    # 2. Start command fails fast on missing launcher
    plan_file = repo_dir / "plan.json"
    plan_data = {
        "run_id": "test-run",
        "units": [
            {
                "name": "worker-1",
                "vendor": "claude",
                "task": "do something",
            }
        ],
    }
    plan_file.write_text(json.dumps(plan_data))

    start_res = _run_installed_orchestrate(
        script, ["start", "--plan", str(plan_file)], cwd=repo_dir
    )
    assert start_res.returncode != 0
    start_err = start_res.stderr + start_res.stdout
    assert "agent-launcher plugin not found" in start_err
    assert EXPECTED_REMEDIATION in start_err

    # 3. Expand command fails fast on missing launcher
    expand_res = _run_installed_orchestrate(
        script, ["expand", "--plan", str(plan_file)], cwd=repo_dir
    )
    assert expand_res.returncode != 0
    expand_err = expand_res.stderr + expand_res.stdout
    assert "agent-launcher plugin not found" in expand_err
    assert EXPECTED_REMEDIATION in expand_err

    # 4. Create a dummy run.json to test `go`
    orch_state_dir = repo_dir / ".orchestrate"
    orch_state_dir.mkdir(parents=True, exist_ok=True)
    run_json = orch_state_dir / "run.json"
    run_json.write_text(
        json.dumps(
            {
                "run_id": "test-run",
                "base": "HEAD",
                "backend": "inline",
                "branch": "orch/test-run",
                "units": [
                    {
                        "name": "worker-1",
                        "vendor": "claude",
                        "task": "do something",
                        "status": "pending",
                        "after": [],
                        "serialize": [],
                    }
                ],
            }
        )
    )

    go_res = _run_installed_orchestrate(script, ["go"], cwd=repo_dir)
    assert go_res.returncode != 0
    go_err = go_res.stderr + go_res.stdout
    assert "agent-launcher plugin not found" in go_err
    assert EXPECTED_REMEDIATION in go_err

    # Crucial assertion: no worktree was created
    worktree_dir = repo_dir / ".orchestrate" / "worktrees" / "worker-1"
    assert not worktree_dir.exists()
    assert not (repo_dir / "worker-1").exists()


def test_installed_orchestrate_with_discoverable_launcher_passes_preflight(tmp_path: Path) -> None:
    """When agent-launcher sibling is installed, installed orchestrate passes preflight (#841)."""
    cache = tmp_path / "cache" / MARKETPLACE
    cache.mkdir(parents=True)
    orch_install = _install_plugin(
        cache, "orchestrate", "3.0.1", parts=(".claude-plugin", "skills")
    )
    _install_plugin(cache, "agent-launcher", "1.0.0", parts=(".claude-plugin", "skills"))
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"

    result = _run_installed_orchestrate(script, ["roster"], cwd=tmp_path)
    # Preflight resolves agent-launcher; output may exit 0 with roster table or exit 1 if wrapper binary 'agents' is absent,
    # but must NOT fail with missing agent-launcher error.
    err_and_out = result.stderr + result.stdout
    assert "agent-launcher plugin not found" not in err_and_out
    assert EXPECTED_REMEDIATION not in err_and_out
