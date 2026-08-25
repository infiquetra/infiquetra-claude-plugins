"""Release-surface contract for the agent-launcher plugin (#777)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "agent-launcher"


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


def test_agent_launcher_metadata_is_marketplace_registered() -> None:
    plugin_json = json.loads(_read(PLUGIN_ROOT / ".claude-plugin" / "plugin.json"))
    marketplace = json.loads(_read(ROOT / ".claude-plugin" / "marketplace.json"))
    marketplace_entry = next(
        plugin for plugin in marketplace["plugins"] if plugin["name"] == "agent-launcher"
    )

    assert plugin_json["name"] == "agent-launcher"
    assert plugin_json["version"] == "1.0.0"
    assert "Herdr" in plugin_json["description"]
    assert {"agent-launcher", "agents", "herdr", "launch", "sessions"} <= set(
        plugin_json["keywords"]
    )
    assert marketplace_entry["source"] == "./plugins/agent-launcher"
    assert marketplace_entry["version"] == plugin_json["version"]
    assert marketplace_entry["keywords"] == plugin_json["keywords"]


def test_agent_launcher_packaged_files() -> None:
    expected = (
        ".claude-plugin/plugin.json",
        "README.md",
        "CHANGELOG.md",
        "skills/agent-launcher/SKILL.md",
        "skills/agent-launcher/scripts/launcher.py",
        "tests/test_launcher_contract.py",
    )
    for relative_path in expected:
        assert (PLUGIN_ROOT / relative_path).exists(), f"missing {relative_path}"
    assert _frontmatter(PLUGIN_ROOT / "skills" / "agent-launcher" / "SKILL.md")["name"] == (
        "agent-launcher"
    )
    assert not (PLUGIN_ROOT / "skills" / "herdr").exists()
