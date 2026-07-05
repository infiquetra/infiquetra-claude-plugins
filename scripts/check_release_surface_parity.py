#!/usr/bin/env python3
"""
Tri-lock release-surface parity gate (#429, R2): for each plugin, assert
`plugin.json` version == the plugin's own `marketplace.json` entry version (as actually
committed, not regenerated) == the plugin's own `CHANGELOG.md` top dated version-heading.
Fails naming exactly the plugin(s) out of parity.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PLUGINS_DIR = REPO_ROOT / "plugins"

_CHL_SPEC = importlib.util.spec_from_file_location(
    "changelog_heading_lint", Path(__file__).resolve().parent / "changelog_heading_lint.py"
)
assert _CHL_SPEC is not None and _CHL_SPEC.loader is not None
_CHL = importlib.util.module_from_spec(_CHL_SPEC)
sys.modules["changelog_heading_lint"] = _CHL
_CHL_SPEC.loader.exec_module(_CHL)
VERSION_HEADING_RE = _CHL.VERSION_HEADING_RE


class ParityError(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def top_changelog_version(changelog_path: Path) -> str:
    """First dated `## [X.Y.Z] - YYYY-MM-DD` heading's version, skipping `[Unreleased]`."""
    for line in changelog_path.read_text().splitlines():
        if not line.startswith("## "):
            continue
        if VERSION_HEADING_RE.match(line):
            return line.split("[", 1)[1].split("]", 1)[0]
    raise ParityError(f"{changelog_path}: no dated version heading found")


def check_parity(
    marketplace_path: Path = MARKETPLACE_PATH, plugins_dir: Path = PLUGINS_DIR
) -> list[str]:
    """Return the names of plugins whose plugin.json/marketplace/CHANGELOG versions disagree.

    The marketplace version is read from the ACTUALLY COMMITTED marketplace.json entry —
    not regenerated from plugin.json (that would make this leg of the tri-lock a tautology,
    since a regenerated entry's version always equals plugin.json's by construction).
    """
    marketplace = load_json(marketplace_path)
    marketplace_versions = {p["name"]: p.get("version") for p in marketplace.get("plugins", [])}

    drifted = []
    for plugin_json_path in sorted(plugins_dir.glob("*/.claude-plugin/plugin.json")):
        plugin_json = load_json(plugin_json_path)
        name = plugin_json["name"]
        plugin_json_version = plugin_json["version"]
        changelog_path = plugin_json_path.parent.parent / "CHANGELOG.md"
        try:
            changelog_version = top_changelog_version(changelog_path)
        except ParityError:
            drifted.append(name)
            continue
        marketplace_version = marketplace_versions.get(name)
        if not (plugin_json_version == marketplace_version == changelog_version):
            drifted.append(name)
    return sorted(drifted)


def main(argv: list[str] | None = None) -> int:
    del argv
    drifted = check_parity()
    if drifted:
        print(
            "check_release_surface_parity: out of parity: " + ", ".join(drifted),
            file=sys.stderr,
        )
        return 1
    print("check_release_surface_parity: all plugins in parity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
