"""Contract tests for the codex plugin release surface."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "codex"


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


def test_codex_plugin_json_has_required_fields() -> None:
    plugin_json = json.loads(_read(PLUGIN_ROOT / ".claude-plugin" / "plugin.json"))
    assert plugin_json["name"] == "codex"
    assert plugin_json["version"] == "0.1.0"
    assert plugin_json["description"]
    assert plugin_json["author"] == {"name": "Infiquetra", "email": "hello@infiquetra.com"}
    assert plugin_json["repository"] == "https://github.com/infiquetra/infiquetra-claude-plugins"
    assert {"codex", "delegation"} <= set(plugin_json["keywords"])


def test_codex_plugin_surfaces_exist() -> None:
    for relative in (
        ".claude-plugin/plugin.json",
        "README.md",
        "CHANGELOG.md",
        "commands/delegate.md",
        "scripts/codex_delegate.py",
        "scripts/fleet_commons_shim.py",
        "skills/codex-delegate/SKILL.md",
        "agents/codex-coder.md",
        "agents/codex-reviewer.md",
    ):
        path = PLUGIN_ROOT / relative
        assert path.is_file(), f"missing packaged surface: {path}"


def test_codex_command_frontmatter_name() -> None:
    assert _frontmatter(PLUGIN_ROOT / "commands" / "delegate.md")["name"] == "delegate"


def test_codex_skill_frontmatter_name() -> None:
    skill_path = PLUGIN_ROOT / "skills" / "codex-delegate" / "SKILL.md"
    assert _frontmatter(skill_path)["name"] == "codex-delegate"


def test_codex_agent_frontmatter_names() -> None:
    for agent_name in ("codex-coder", "codex-reviewer"):
        agent_path = PLUGIN_ROOT / "agents" / f"{agent_name}.md"
        frontmatter = _frontmatter(agent_path)
        assert frontmatter["name"] == agent_name
        assert frontmatter["tools"] == "Bash"
