"""Release-surface contract for the agent-launcher plugin (#777, #841)."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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


def _set_plugin_version(root: Path, version: str) -> None:
    manifest = root / ".claude-plugin" / "plugin.json"
    payload = json.loads(_read(manifest))
    payload["version"] = version
    manifest.write_text(json.dumps(payload), encoding="utf-8")


def _declared_version(plugin: str) -> str:
    """ARCH-20: installed-layout cache directories follow the plugin's own manifest."""
    payload = json.loads(_read(ROOT / "plugins" / plugin / ".claude-plugin" / "plugin.json"))
    return str(payload["version"])


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _git_out(cwd: Path, *args: str) -> str:
    got = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return got.stdout.strip()


def _install_fake_agents(tmp_path: Path) -> Path:
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir(exist_ok=True)
    wrapper = binary_dir / "agents"
    wrapper.write_text("#!/bin/sh\nprintf 'Tools:\\n  claude  Claude\\n\\n'\n", encoding="utf-8")
    wrapper.chmod(0o755)
    return binary_dir


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
    assert plugin_json["version"] == "1.3.0"
    assert "Herdr" in plugin_json["description"]
    assert {"agent-launcher", "agents", "herdr", "launch", "sessions"} <= set(
        plugin_json["keywords"]
    )
    assert marketplace_entry["source"] == "./plugins/agent-launcher"
    assert marketplace_entry["version"] == plugin_json["version"]
    assert marketplace_entry["keywords"] == plugin_json["keywords"]


def test_installed_layout_names_cache_dirs_from_the_manifest() -> None:
    """ARCH-20: cache directories follow plugin.json, not leftover 3.x literals."""
    source = Path(__file__).read_text(encoding="utf-8")
    assert f'"{3}.0.1"' not in source
    assert f'"{3}.2.1"' not in source
    assert "_declared_version(" in source


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
    launcher_version = json.loads(_read(PLUGIN_ROOT / ".claude-plugin" / "plugin.json"))["version"]
    assert floors.get("agent-launcher") == f">={launcher_version}", declared

    orch_entry = next(
        plugin for plugin in marketplace["plugins"] if plugin["name"] == "orchestrate"
    )
    launcher_entry = next(
        plugin for plugin in marketplace["plugins"] if plugin["name"] == "agent-launcher"
    )
    assert orch_entry["version"] == orch_json["version"]
    assert launcher_entry["version"] == launcher_version


def test_orchestrate_skill_matches_the_deferred_floor_failure_contract() -> None:
    skill = _read(ORCHESTRATE_ROOT / "skills" / "orchestrate" / "SKILL.md")
    section = skill[skill.index("**Single launch seam") : skill.index("Unsupported post-launch")]
    assert "plugin manifest" in section
    assert "read-only recovery commands" in section
    assert all(
        command in section
        for command in (
            "`roster`",
            "`saga`",
            "`start`",
            "`expand`",
            "`go`",
            "`review-result`",
            "`land`",
            "`clean`",
        )
    )
    assert EXPECTED_REMEDIATION in section
    assert "claude plugin update agent-launcher@infiquetra-plugins" in section


def test_orchestrate_readme_and_command_agree_the_launcher_floor_is_enforced() -> None:
    """DOCC-04: origin/main's two docs must not keep the pre-U8 'nothing checks' sentences."""
    readme = _read(ORCHESTRATE_ROOT / "README.md")
    command = _read(ORCHESTRATE_ROOT / "commands" / "orchestrate.md")
    assert "nothing verifies them" not in readme
    assert "no code checks" not in command
    for text in (readme, command):
        assert "agent-launcher" in text
        assert "status" in text and "check" in text


def test_orchestrate_skill_states_the_staged_input_recovery_runbook() -> None:
    """REL-12: the operator-facing runbook for a staged-input stop. Prose is compared with
    whitespace flattened so line wrapping cannot mask a claim."""
    skill = _read(ORCHESTRATE_ROOT / "skills" / "orchestrate" / "SKILL.md")
    start = skill.index("**A staged-input stop is retryable")
    end = skill.index("Unsupported post-launch")
    assert start < end, "the runbook must sit in the launch-contract section"
    section = " ".join(skill[start:end].split())
    assert "PENDING" in section
    assert "same pane" in section
    assert "creates no session" in section
    assert "left open" in section
    assert "`already has tab`" in section


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
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
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
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
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
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
    )
    _install_plugin(
        cache,
        "agent-launcher",
        _declared_version("agent-launcher"),
        parts=(".claude-plugin", "skills"),
    )
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"

    result = _run_installed_orchestrate(script, ["roster"], cwd=tmp_path)
    # Preflight resolves agent-launcher; output may exit 0 with roster table or exit 1 if wrapper binary 'agents' is absent,
    # but must NOT fail with missing agent-launcher error.
    err_and_out = result.stderr + result.stdout
    assert "agent-launcher plugin not found" not in err_and_out
    assert EXPECTED_REMEDIATION not in err_and_out


def test_read_only_help_and_roster_survive_a_stale_launcher_while_go_enforces_the_floor(
    tmp_path: Path,
) -> None:
    """Below the floor, ``--help`` and ``roster`` run -- roster writes nothing -- and the
    first command that would write a pane, ``go``, refuses with the update remedy
    (terminal review F24; DECISIONS ``{#907-agent-launcher-floor-owner}``)."""
    cache = tmp_path / "cache" / MARKETPLACE
    orch_install = _install_plugin(
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
    )
    stale = _install_plugin(cache, "agent-launcher", "1.2.0", parts=(".claude-plugin", "skills"))
    _set_plugin_version(stale, "1.2.0")
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"
    path = f"{_install_fake_agents(tmp_path)}:{os.environ.get('PATH', '')}"

    help_result = _run_installed_orchestrate(
        script, ["--help"], cwd=tmp_path, env_overrides={"PATH": path}
    )
    assert help_result.returncode == 0, help_result.stderr
    assert "Traceback" not in help_result.stderr

    roster_result = _run_installed_orchestrate(
        script, ["roster"], cwd=tmp_path, env_overrides={"PATH": path}
    )
    assert roster_result.returncode == 0, roster_result.stderr
    roster_output = roster_result.stderr + roster_result.stdout
    assert "claude plugin update agent-launcher" not in roster_output
    assert "Traceback" not in roster_output
    assert "claude" in roster_result.stdout

    go_result = _run_installed_orchestrate(
        script, ["go"], cwd=tmp_path, env_overrides={"PATH": path}
    )
    assert go_result.returncode != 0
    output = go_result.stderr + go_result.stdout
    assert (
        f"agent-launcher 1.2.0 is installed; Orchestrate requires >={_declared_floor()}" in output
    )
    # Issue 907 U8 (ARCH-02): a stale install prescribes the update, never the install.
    assert "claude plugin update agent-launcher@infiquetra-plugins" in output
    assert "Traceback" not in output


def test_missing_composer_is_deferred_and_reported_without_a_traceback(tmp_path: Path) -> None:
    cache = tmp_path / "cache" / MARKETPLACE
    orch_install = _install_plugin(
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
    )
    launcher_install = _install_plugin(
        cache,
        "agent-launcher",
        _declared_version("agent-launcher"),
        parts=(".claude-plugin", "skills"),
    )
    (launcher_install / "skills" / "agent-launcher" / "scripts" / "composer.py").unlink()
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"

    help_result = _run_installed_orchestrate(script, ["--help"], cwd=tmp_path)
    assert help_result.returncode == 0, help_result.stderr
    assert "Traceback" not in help_result.stderr

    roster_result = _run_installed_orchestrate(script, ["roster"], cwd=tmp_path)
    assert roster_result.returncode != 0
    output = roster_result.stderr + roster_result.stdout
    assert "cannot load agent-launcher composer parser" in output
    assert "file is missing" in output
    assert EXPECTED_REMEDIATION in output
    assert "Traceback" not in output


def test_standalone_launcher_missing_composer_is_a_named_stop(tmp_path: Path) -> None:
    launcher_install = _install_plugin(
        tmp_path,
        "agent-launcher",
        _declared_version("agent-launcher"),
        parts=(".claude-plugin", "skills"),
    )
    composer = launcher_install / "skills" / "agent-launcher" / "scripts" / "composer.py"
    composer.unlink()
    script = launcher_install / "skills" / "agent-launcher" / "scripts" / "launcher.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=30,
    )
    assert result.returncode != 0
    output = result.stderr + result.stdout
    assert "cannot load agent-launcher composer parser" in output
    assert "file is missing" in output
    assert "Traceback" not in output


BROKEN_COMPOSERS = [
    ("raise RuntimeError('composer exploded')\n", "RuntimeError: composer exploded"),
    ("raise ValueError('composer bad value')\n", "ValueError: composer bad value"),
    (
        'assert False, "composer contract violated"\n',
        "AssertionError: composer contract violated",
    ),
]


@pytest.mark.parametrize(
    ("broken", "expected_detail"),
    BROKEN_COMPOSERS,
    ids=["runtime-error", "value-error", "assertion-error"],
)
def test_standalone_launcher_broken_composer_is_a_named_stop(
    tmp_path: Path, broken: str, expected_detail: str
) -> None:
    """ARCH-05: any exception while loading composer.py becomes the named stop carrying the
    exception type and message, with no traceback, in the standalone entry mode. At the
    frozen revision the RuntimeError case dies with a traceback."""
    launcher_install = _install_plugin(
        tmp_path,
        "agent-launcher",
        _declared_version("agent-launcher"),
        parts=(".claude-plugin", "skills"),
    )
    composer = launcher_install / "skills" / "agent-launcher" / "scripts" / "composer.py"
    composer.write_text(broken, encoding="utf-8")
    script = launcher_install / "skills" / "agent-launcher" / "scripts" / "launcher.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=30,
    )
    assert result.returncode != 0
    output = result.stderr + result.stdout
    assert "cannot load agent-launcher composer parser" in output
    assert expected_detail in output
    assert "Traceback" not in output


@pytest.mark.parametrize(
    ("broken", "expected_detail"),
    BROKEN_COMPOSERS,
    ids=["runtime-error", "value-error", "assertion-error"],
)
def test_ingested_launcher_broken_composer_uses_the_same_named_contract(
    tmp_path: Path, broken: str, expected_detail: str
) -> None:
    """ARCH-05 through Orchestrate's ingest door: the loader's named stop, with the
    exception type, is carried into the deferred unusable message."""
    cache = tmp_path / "cache" / MARKETPLACE
    orch_install = _install_plugin(
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
    )
    launcher_install = _install_plugin(
        cache,
        "agent-launcher",
        _declared_version("agent-launcher"),
        parts=(".claude-plugin", "skills"),
    )
    composer = launcher_install / "skills" / "agent-launcher" / "scripts" / "composer.py"
    composer.write_text(broken, encoding="utf-8")
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"

    help_result = _run_installed_orchestrate(script, ["--help"], cwd=tmp_path)
    assert help_result.returncode == 0, help_result.stderr
    assert "Traceback" not in help_result.stderr

    roster_result = _run_installed_orchestrate(script, ["roster"], cwd=tmp_path)
    assert roster_result.returncode != 0
    output = roster_result.stderr + roster_result.stdout
    assert "cannot load agent-launcher composer parser" in output
    assert expected_detail in output
    assert EXPECTED_REMEDIATION in output
    assert "Traceback" not in output


def test_internal_launcher_failure_uses_the_same_deferred_named_contract(tmp_path: Path) -> None:
    cache = tmp_path / "cache" / MARKETPLACE
    orch_install = _install_plugin(
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
    )
    launcher_install = _install_plugin(
        cache,
        "agent-launcher",
        _declared_version("agent-launcher"),
        parts=(".claude-plugin", "skills"),
    )
    composer = launcher_install / "skills" / "agent-launcher" / "scripts" / "composer.py"
    composer.write_text("raise RuntimeError('simulated roster drift')\n", encoding="utf-8")
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"

    help_result = _run_installed_orchestrate(script, ["--help"], cwd=tmp_path)
    assert help_result.returncode == 0, help_result.stderr
    assert "Traceback" not in help_result.stderr

    roster_result = _run_installed_orchestrate(script, ["roster"], cwd=tmp_path)
    assert roster_result.returncode != 0
    output = roster_result.stderr + roster_result.stdout
    assert "simulated roster drift" in output
    assert EXPECTED_REMEDIATION in output
    assert "Traceback" not in output


def test_installed_cache_discovery_selects_and_validates_the_highest_numeric_version(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "cache" / MARKETPLACE
    orch_install = _install_plugin(
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
    )
    older = _install_plugin(cache, "agent-launcher", "1.9.0", parts=(".claude-plugin", "skills"))
    newer = _install_plugin(cache, "agent-launcher", "1.10.0", parts=(".claude-plugin", "skills"))
    _set_plugin_version(older, _declared_version("agent-launcher"))
    _set_plugin_version(newer, _declared_version("agent-launcher"))
    old_script = older / "skills" / "agent-launcher" / "scripts" / "launcher.py"
    old_script.write_text("raise RuntimeError('lower cache entry selected')\n", encoding="utf-8")
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"
    path = f"{_install_fake_agents(tmp_path)}:{os.environ.get('PATH', '')}"

    result = _run_installed_orchestrate(
        script, ["roster"], cwd=tmp_path, env_overrides={"PATH": path}
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "claude" in result.stdout


# --- Issue 907 U8: the companion floor is a command-by-state matrix (KTD7) ---------------------


FAKE_HERDR = """#!/usr/bin/env python3
import json
import os
import sys
with open(os.environ["HERDR_LOG"], "a") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\\n")
argv = sys.argv[1:]
if argv[:2] == ["agent", "list"]:
    print(json.dumps({"result": {"agents": [{"name": "alpha", "agent_status": "working"}]}}))
elif argv[:2] == ["tab", "list"]:
    print(json.dumps({"result": {"tabs": []}}))
elif argv[:2] == ["pane", "current"]:
    print(json.dumps({"result": {"pane": {"workspace_id": "w1"}}}))
sys.exit(0)
"""

MATRIX_INVOCATIONS = {
    "--help": ["--help"],
    "start": ["start", "--plan", "plan.md"],
    "roster": ["roster"],
    "saga": ["saga", "plan"],
    "expand": ["expand", "--plan", "plan.md"],
    "review-result": ["review-result", "--file", "result.json"],
    "go": ["go"],
    "status": ["status"],
    "settle": ["settle", "--interval", "0"],
    "wait": ["wait", "--timeout", "1"],
    "land": ["land"],
    "announce": ["announce", "alpha"],
    "collect": ["collect"],
    "clean": ["clean"],
    "check": ["check"],
    "adopt": ["adopt"],
    "diff": ["diff"],
    "park": ["park", "--unit", "alpha", "--evidence", "blocked"],
    "resume": ["resume", "--unit", "alpha"],
}

# The six commands the floor gates: each writes a pane, creates a session or worktree, or
# closes a tab. A companion below the floor refuses them with the update remedy; a missing or
# unusable one refuses them with the install remedy.
GATED_SUBCOMMANDS = (
    "start",
    "expand",
    "go",
    "review-result",
    "land",
    "clean",
)
# The two informational commands: they read the wrapper's tool list and the saga install on
# disk and write nothing, so a companion below the floor still serves them (terminal review
# F24, matching the decision record's read-only bucket); only a companion that was never
# ingested -- missing or unusable -- refuses them, with the install remedy.
INGEST_ONLY_SUBCOMMANDS = ("roster", "saga")

PANE_WRITES = (("pane", "run"), ("agent", "prompt"), ("tab", "close"))


def _declared_floor() -> str:
    manifest = json.loads(_read(ORCHESTRATE_ROOT / ".claude-plugin" / "plugin.json"))
    requirement = next(
        entry["version"]
        for entry in manifest["dependencies"]
        if isinstance(entry, dict) and entry.get("name") == "agent-launcher"
    )
    assert isinstance(requirement, str) and requirement.startswith(">=")
    return requirement.removeprefix(">=")


def _matrix_layout(tmp_path: Path, state: str) -> tuple[Path, Path, bytes, Path]:
    """One installed layout per companion state: orchestrate plus a companion at the floor,
    below it, or broken at import; a git repo holding one RUNNING unit; a recording fake
    herdr on PATH. Returns the orchestrate script, the repo, the run-file snapshot, and
    the PATH directory that holds the fake herdr and agents binaries."""
    cache = tmp_path / f"cache-{state}" / MARKETPLACE
    orch_install = _install_plugin(
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
    )
    launcher_install = _install_plugin(
        cache, "agent-launcher", _declared_floor(), parts=(".claude-plugin", "skills")
    )
    if state == "below-floor":
        _set_plugin_version(launcher_install, "1.0.0")
    if state == "unusable":
        composer = launcher_install / "skills" / "agent-launcher" / "scripts" / "composer.py"
        composer.write_text("raise RuntimeError('simulated roster drift')\n", encoding="utf-8")

    repo = tmp_path / f"repo-{state}"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-m", "base")
    _git(repo, "branch", "orch/r1")
    _git(repo, "branch", "orch/r1-alpha")
    _git(repo, "remote", "add", "origin", str(repo))
    (repo / "plan.md").write_text("- plan\n")
    (repo / "result.json").write_text("{}\n")
    run_file = repo / ".orchestrate" / "run.json"
    run_file.parent.mkdir()
    snapshot = json.dumps(
        {
            "run_id": "r1",
            "source": "matrix",
            "base": _git_out(repo, "rev-parse", "main"),
            "branch": "orch/r1",
            "units": [
                {
                    "name": "alpha",
                    "vendor": "claude",
                    "task": "x",
                    "branch": "orch/r1-alpha",
                    "status": "running",
                    "tab_id": "w1:t1",
                    "pane_id": "w1:p1",
                    "launch_receipt": {"tab_id": "w1:t1", "owned": True, "input_box": "empty"},
                }
            ],
        }
    ).encode()
    run_file.write_bytes(snapshot)

    bin_dir = tmp_path / f"bin-{state}"
    bin_dir.mkdir()
    herdr = bin_dir / "herdr"
    herdr.write_text(FAKE_HERDR, encoding="utf-8")
    herdr.chmod(0o755)
    agents = bin_dir / "agents"
    agents.write_text("#!/bin/sh\nprintf 'Tools:\\n  claude  Claude\\n\\n'\n", encoding="utf-8")
    agents.chmod(0o755)
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"
    return script, repo, snapshot, bin_dir


def _run_matrix_command(
    tmp_path: Path, script: Path, repo: Path, snapshot: bytes, bin_dir: Path, command: str
) -> tuple[int, str, list[list[str]]]:
    """Run one matrix invocation: fresh run record, fresh herdr log, combined output."""
    (repo / ".orchestrate" / "run.json").write_bytes(snapshot)
    if command == "adopt":
        # adopt only reaches its liveness read when a run branch is unrecorded; give it
        # one for this invocation and take it away again so `check` sees a clean repo.
        _git(repo, "branch", "orch/r1-orphan", "main")
    log = tmp_path / f"herdr-{command}-{repo.name}.log"
    if log.exists():
        log.unlink()
    env = {
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "HERDR_LOG": str(log),
    }
    proc = _run_installed_orchestrate(
        script, MATRIX_INVOCATIONS[command], cwd=repo, env_overrides=env
    )
    if command == "adopt":
        _git(repo, "branch", "-D", "orch/r1-orphan")
    calls = (
        [line.split() for line in log.read_text(encoding="utf-8").splitlines()]
        if log.exists()
        else []
    )
    return proc.returncode, proc.stderr + proc.stdout, calls


def _assert_no_pane_write(calls: list[list[str]], command: str, state: str) -> None:
    for call in calls:
        assert tuple(call[:2]) not in PANE_WRITES, (
            f"{state}/{command}: a gated command reached a pane write: {' '.join(call)}"
        )


@pytest.mark.parametrize("state", ["at-floor", "below-floor", "unusable"])
@pytest.mark.parametrize("command", list(MATRIX_INVOCATIONS))
def test_the_companion_floor_matrix(tmp_path: Path, state: str, command: str) -> None:
    """SEC-03/API-02: the companion floor as a command-by-state matrix. A below-floor or
    missing companion never reaches a pane write, a creation, or a tab close through the
    gated commands; --help, status and check survive every companion state."""
    script, repo, snapshot, bin_dir = _matrix_layout(tmp_path, state)
    code, output, calls = _run_matrix_command(tmp_path, script, repo, snapshot, bin_dir, command)

    if command == "--help":
        assert code == 0, f"{state}/--help: {output}"
        return
    if state == "at-floor":
        assert "claude plugin update agent-launcher" not in output, (
            f"{state}/{command}: the gate fired at floor: {output}"
        )
        assert EXPECTED_REMEDIATION not in output, f"{state}/{command}: {output}"
        if command in ("status", "check"):
            assert code == 0, f"{state}/{command}: {output}"
            assert any(c[:2] == ["agent", "list"] for c in calls), (
                f"{state}/{command}: liveness was not asked of herdr"
            )
        return
    if state == "below-floor":
        if command in GATED_SUBCOMMANDS:
            assert code != 0, f"{state}/{command}: ran against a below-floor companion"
            assert "claude plugin update agent-launcher@infiquetra-plugins" in output, (
                f"{state}/{command}: no update remedy: {output}"
            )
            assert EXPECTED_REMEDIATION not in output, (
                f"{state}/{command}: the install remedy serves a stale install: {output}"
            )
            _assert_no_pane_write(calls, command, state)
        elif command in INGEST_ONLY_SUBCOMMANDS:
            assert code == 0, f"{state}/{command}: a read-only command refused: {output}"
            assert "claude plugin update agent-launcher" not in output, (
                f"{state}/{command}: the floor gated a command that writes nothing: {output}"
            )
            assert EXPECTED_REMEDIATION not in output, f"{state}/{command}: {output}"
            _assert_no_pane_write(calls, command, state)
        elif command in ("status", "check"):
            assert code == 0, f"{state}/{command}: {output}"
            assert EXPECTED_REMEDIATION not in output and "unusable" not in output, (
                f"{state}/{command}: a stale companion printed a fault: {output}"
            )
            assert any(c[:2] == ["agent", "list"] for c in calls), (
                f"{state}/{command}: the ingested companion did not read liveness"
            )
        else:
            assert "claude plugin update agent-launcher" not in output, (
                f"{state}/{command}: refused: {output}"
            )
        return
    # unusable: nothing was ingested
    if command in GATED_SUBCOMMANDS or command in INGEST_ONLY_SUBCOMMANDS:
        assert code != 0, f"{state}/{command}: ran against an unusable companion"
        assert "simulated roster drift" in output or "not found" in output, (
            f"{state}/{command}: no cause named: {output}"
        )
        assert EXPECTED_REMEDIATION in output, f"{state}/{command}: {output}"
        _assert_no_pane_write(calls, command, state)
    elif command in ("status", "check"):
        assert code == 0, f"{state}/{command}: a read-only command died: {output}"
        assert output.count("simulated roster drift") == 1, (
            f"{state}/{command}: the fault was not printed exactly once: {output}"
        )
        assert not any(c[:2] == ["agent", "list"] for c in calls), (
            f"{state}/{command}: liveness was asked without a companion"
        )
        if command == "status":
            assert "unknown" in output, f"{state}/{command}: liveness not unknown: {output}"
    elif command in ("wait", "settle", "adopt"):
        assert code != 0, f"{state}/{command}: ran without the companion's Herdr reads"
        assert "simulated roster drift" in output, f"{state}/{command}: {output}"
    else:
        # The ungated commands run to their own semantics; the matrix only promises they
        # are never refused by the companion.
        assert "simulated roster drift" not in output, f"{state}/{command}: {output}"


@pytest.mark.parametrize("plugin_root", ["sibling", "grandparent"])
def test_plugin_root_discovery_selects_the_highest_numeric_version(
    tmp_path: Path, plugin_root: str
) -> None:
    """TEST-03 / O16 / O17 / O18: with the parent walk unable to resolve a launcher, the
    CLAUDE_PLUGIN_ROOT branch is the only route, and it picks the highest numeric version
    -- never the 1.9.0 entry whose script raises."""
    cache_a = tmp_path / "cache-a" / MARKETPLACE
    orch_install = _install_plugin(
        cache_a, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
    )
    cache_b = tmp_path / "cache-b" / MARKETPLACE
    older = _install_plugin(cache_b, "agent-launcher", "1.9.0", parts=(".claude-plugin", "skills"))
    newer = _install_plugin(cache_b, "agent-launcher", "1.10.0", parts=(".claude-plugin", "skills"))
    _set_plugin_version(older, _declared_version("agent-launcher"))
    _set_plugin_version(newer, _declared_version("agent-launcher"))
    old_script = older / "skills" / "agent-launcher" / "scripts" / "launcher.py"
    old_script.write_text("raise RuntimeError('lower cache entry selected')\n", encoding="utf-8")
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"

    if plugin_root == "sibling":
        root = cache_b / "orchestrate"
    else:
        root = cache_b / "orchestrate" / _declared_version("orchestrate")
    path = f"{_install_fake_agents(tmp_path)}:{os.environ.get('PATH', '')}"
    result = _run_installed_orchestrate(
        script,
        ["roster"],
        cwd=tmp_path,
        env_overrides={"PATH": path, "CLAUDE_PLUGIN_ROOT": str(root)},
    )
    output = result.stderr + result.stdout
    assert result.returncode == 0, output
    assert "claude" in result.stdout
    assert "lower cache entry selected" not in output


def test_bad_agent_launcher_root_override_exits_with_the_named_message(tmp_path: Path) -> None:
    """O21: a bad AGENT_LAUNCHER_ROOT names the missing file, not a manifest failure."""
    cache = tmp_path / "cache" / MARKETPLACE
    orch_install = _install_plugin(
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
    )
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"
    empty_root = tmp_path / "not-a-plugin"
    empty_root.mkdir()

    result = _run_installed_orchestrate(
        script, ["roster"], cwd=tmp_path, env_overrides={"AGENT_LAUNCHER_ROOT": str(empty_root)}
    )
    output = result.stderr + result.stdout
    assert result.returncode != 0
    assert "does not contain skills/agent-launcher/scripts/launcher.py" in output
    assert "cannot verify agent-launcher manifest" not in output


@pytest.mark.parametrize(
    "requirement",
    ["^1.2.1", "1.2.1", ">=1.2.1,<2.0.0"],
    ids=["caret-range", "bare-version", "compound-range"],
)
def test_malformed_floor_requirements_exit_with_the_named_message(
    tmp_path: Path, requirement: str
) -> None:
    """TEST-11's floor-regex half / O3: a requirement that is not a numeric >= floor is
    refused by name, in every malformed shape."""
    cache = tmp_path / "cache" / MARKETPLACE
    orch_install = _install_plugin(
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
    )
    # The malformed floor is only reached once a launcher exists to check; discovery
    # happens before the floor.
    _install_plugin(
        cache,
        "agent-launcher",
        _declared_version("agent-launcher"),
        parts=(".claude-plugin", "skills"),
    )
    manifest = orch_install / ".claude-plugin" / "plugin.json"
    payload = json.loads(_read(manifest))
    next(
        entry
        for entry in payload["dependencies"]
        if isinstance(entry, dict) and entry.get("name") == "agent-launcher"
    )["version"] = requirement
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"

    # The malformed floor gates the write side: `go` refuses before it reads a run file.
    # `roster` writes nothing and runs against an ingested companion whatever the floor says.
    result = _run_installed_orchestrate(script, ["go"], cwd=tmp_path)
    output = result.stderr + result.stdout
    assert result.returncode != 0
    assert "must be a numeric >= floor" in output
    roster = _run_installed_orchestrate(
        script,
        ["roster"],
        cwd=tmp_path,
        env_overrides={"PATH": f"{_install_fake_agents(tmp_path)}:{os.environ['PATH']}"},
    )
    assert "must be a numeric >= floor" not in roster.stderr + roster.stdout


def test_each_companion_fault_names_its_own_cause_and_remedy(tmp_path: Path) -> None:
    """ARCH-02 / REL-02: below floor prescribes the update, missing prescribes the
    install, unusable names the exception type."""
    # missing: no companion installed at all
    cache = tmp_path / "cache-missing" / MARKETPLACE
    orch_install = _install_plugin(
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
    )
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"
    result = _run_installed_orchestrate(script, ["roster"], cwd=tmp_path)
    missing_output = result.stderr + result.stdout
    assert result.returncode != 0
    assert "not found" in missing_output
    assert EXPECTED_REMEDIATION in missing_output

    # below floor: update, never install -- on the write side (`go`); `roster` writes nothing
    # and is served by the stale companion (terminal review F24).
    script, repo, snapshot, bin_dir = _matrix_layout(tmp_path, "below-floor")
    result = _run_installed_orchestrate(
        script, ["go"], cwd=repo, env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"}
    )
    below_output = result.stderr + result.stdout
    assert result.returncode != 0
    assert "is installed; Orchestrate requires >=" in below_output
    assert "claude plugin update agent-launcher@infiquetra-plugins" in below_output
    assert "not found" not in below_output
    roster = _run_installed_orchestrate(
        script, ["roster"], cwd=repo, env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"}
    )
    assert roster.returncode == 0, roster.stderr
    assert "Orchestrate requires" not in roster.stderr + roster.stdout

    # unusable: the exception type is named
    script, repo, snapshot, bin_dir = _matrix_layout(tmp_path, "unusable")
    result = _run_installed_orchestrate(
        script, ["roster"], cwd=repo, env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}"}
    )
    unusable_output = result.stderr + result.stdout
    assert result.returncode != 0
    assert "RuntimeError: simulated roster drift" in unusable_output
    assert EXPECTED_REMEDIATION in unusable_output


LAUNCHER_ONLY_NAMES = (
    "ComposerState",
    "ComposerInspection",
    "inspect_composer",
    "pane_input_inspection",
    "record_wrapper_identity",
    "await_ready",
    "send",
)


def test_a_launcher_that_fails_mid_file_binds_nothing(tmp_path: Path) -> None:
    """CORR-11 / REL-11: a launcher that dies partway through its own import leaves the
    namespace exactly as it was -- run is still the fallback and no launcher-only name is
    live. At the frozen revision the partial exec left every name it had bound."""
    cache = tmp_path / "cache" / MARKETPLACE
    orch_install = _install_plugin(
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
    )
    launcher_install = _install_plugin(
        cache,
        "agent-launcher",
        _declared_version("agent-launcher"),
        parts=(".claude-plugin", "skills"),
    )
    launcher_script = launcher_install / "skills" / "agent-launcher" / "scripts" / "launcher.py"
    launcher_script.write_text(
        launcher_script.read_text(encoding="utf-8") + "\n1 / 0\n", encoding="utf-8"
    )
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"
    spec = importlib.util.spec_from_file_location("_orchestrate_midfile_probe", script)
    assert spec is not None and spec.loader is not None
    orch = importlib.util.module_from_spec(spec)
    sys.modules["_orchestrate_midfile_probe"] = orch
    try:
        spec.loader.exec_module(orch)
        assert orch.run is orch._subprocess_run, "a failed ingest left the launcher's run bound"
        for name in LAUNCHER_ONLY_NAMES:
            assert not hasattr(orch, name), f"{name} survived a failed ingest"
    finally:
        sys.modules.pop("_orchestrate_midfile_probe", None)


def test_installed_orchestrate_help_describes_orchestrate(tmp_path: Path) -> None:
    """ARCH-08 / API-09 / DOCC-12: --help describes Orchestrate, never the ingested
    launcher's docstring."""
    cache = tmp_path / "cache" / MARKETPLACE
    orch_install = _install_plugin(
        cache, "orchestrate", _declared_version("orchestrate"), parts=(".claude-plugin", "skills")
    )
    _install_plugin(
        cache,
        "agent-launcher",
        _declared_version("agent-launcher"),
        parts=(".claude-plugin", "skills"),
    )
    script = orch_install / "skills" / "orchestrate" / "scripts" / "orchestrate.py"

    result = _run_installed_orchestrate(script, ["--help"], cwd=tmp_path)
    output = result.stderr + result.stdout
    assert result.returncode == 0, output
    assert "Run a plan of units across herdr agent sessions" in output
    assert "Shared single-session launch contract" not in output


def _top_level_bindings(tree: ast.Module) -> set[str]:
    """The names a module binds at its own top level, outside any conditional block."""

    def assign_names(target: ast.expr) -> set[str]:
        if isinstance(target, ast.Name):
            return {target.id}
        if isinstance(target, ast.Tuple):
            return {name for elt in target.elts for name in assign_names(elt)}
        return set()

    bound: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            bound.update(name for t in node.targets for name in assign_names(t))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
        elif isinstance(node, ast.Import):
            bound.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            bound.update(alias.asname or alias.name for alias in node.names)
    return bound


def test_the_degraded_stub_roster_covers_every_referenced_launcher_name() -> None:
    """ARCH-18 / TEST-10 / O13: the roster is test-bound by the reviewer's AST method.
    This checks completeness -- every launcher name Orchestrate references has a degraded
    binding -- not minimality: a stub bound for a name Orchestrate never references is
    harmless and is not reported here (terminal review F35).
    Every launcher-provided name Orchestrate's own code references must have a binding in
    the degraded fallback, or a failed ingest leaves that reference unbound."""
    orch_tree = ast.parse(
        _read(ORCHESTRATE_ROOT / "skills" / "orchestrate" / "scripts" / "orchestrate.py")
    )
    launcher_tree = ast.parse(
        _read(PLUGIN_ROOT / "skills" / "agent-launcher" / "scripts" / "launcher.py")
    )
    provided = _top_level_bindings(launcher_tree)
    own = _top_level_bindings(orch_tree)
    referenced = {node.id for node in ast.walk(orch_tree) if isinstance(node, ast.Name)}
    degraded: set[str] = set()
    for node in ast.walk(orch_tree):
        if isinstance(node, ast.If) and "not _ingest_agent_launcher()" in ast.unparse(node.test):
            for sub in node.body:
                if isinstance(sub, ast.Assign):
                    degraded.update(t.id for t in sub.targets if isinstance(t, ast.Name))
                elif isinstance(sub, ast.ClassDef):
                    degraded.add(sub.name)
    missing = (provided & referenced) - degraded - own
    assert not missing, f"launcher names referenced with no degraded binding: {sorted(missing)}"


SHARED_STATUS_CONSTANTS = ("RUNNING", "PROMPT_UNDELIVERED", "ACCOUNT_MISMATCH")


def _top_level_assignment(tree: ast.Module, name: str) -> ast.expr:
    """The value expression bound to ``name`` at module top level, through a plain assignment
    or one position of a tuple unpacking such as ``PENDING, RUNNING, ... = ...``."""
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                return node.value
            if isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple):
                for position, element in enumerate(target.elts):
                    if isinstance(element, ast.Name) and element.id == name:
                        return node.value.elts[position]
    raise AssertionError(f"{name} is not assigned at the top level")


def _call_string_arg(node: ast.expr) -> str:
    assert isinstance(node, ast.Call), ast.unparse(node)
    value = ast.literal_eval(node.args[0])
    assert isinstance(value, str)
    return value


def test_the_four_shared_constants_agree_between_orchestrate_and_the_launcher() -> None:
    """Terminal review F31: the launcher's exec into Orchestrate's globals redefines four names
    Orchestrate binds above its ingest point -- three status strings and TASK_DIR -- so the
    launcher's copies win after a successful ingest and Orchestrate's win in the degraded path.
    The launcher comment asserts the literals are identical; this binds them, reading each
    module's own definition rather than the post-ingest namespace."""
    orch_tree = ast.parse(
        _read(ORCHESTRATE_ROOT / "skills" / "orchestrate" / "scripts" / "orchestrate.py")
    )
    launcher_tree = ast.parse(
        _read(PLUGIN_ROOT / "skills" / "agent-launcher" / "scripts" / "launcher.py")
    )
    for name in SHARED_STATUS_CONSTANTS:
        orch_value = ast.literal_eval(_top_level_assignment(orch_tree, name))
        launcher_value = ast.literal_eval(_top_level_assignment(launcher_tree, name))
        assert orch_value == launcher_value, name
    run_file = _call_string_arg(_top_level_assignment(orch_tree, "RUN_FILE"))
    task_dir_expr = ast.unparse(_top_level_assignment(orch_tree, "TASK_DIR"))
    assert task_dir_expr == "RUN_FILE.parent / 'tasks'", task_dir_expr
    launcher_task_dir = _call_string_arg(_top_level_assignment(launcher_tree, "TASK_DIR"))
    assert str(Path(run_file).parent / "tasks") == str(Path(launcher_task_dir))


def test_every_sibling_plugin_path_goes_through_the_layout_helper() -> None:
    """Terminal review F36: ``_plugin_root`` claims every place that needs a sibling plugin or
    a plugin manifest goes through it so the layout is named once. A raw ``parents[...]``
    index anywhere else is that claim being false."""
    source = _read(ORCHESTRATE_ROOT / "skills" / "orchestrate" / "scripts" / "orchestrate.py")
    tree = ast.parse(source)
    helper = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_plugin_root"
    )
    strays = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "parents"
        and not (helper.lineno <= node.lineno <= (helper.end_lineno or helper.lineno))
    ]
    assert strays == [], f"raw parents[] index outside _plugin_root at lines {strays}"
