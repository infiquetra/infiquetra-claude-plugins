#!/usr/bin/env python3
"""
Tri-lock release-surface parity gate (#429, R2): for each plugin, assert
`plugin.json` version == generated `marketplace.json` entry version == the plugin's own
`CHANGELOG.md` top dated version-heading. Fails naming exactly the plugin(s) out of parity.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from changelog_heading_lint import VERSION_HEADING_RE  # noqa: E402
from sync_marketplace import build_target_plugins, load_json  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PLUGINS_DIR = REPO_ROOT / "plugins"


class ParityError(Exception):
    pass


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
    """Return the names of plugins whose plugin.json/marketplace/CHANGELOG versions disagree."""
    marketplace = load_json(marketplace_path)
    marketplace_entries = build_target_plugins(marketplace, plugins_dir)
    marketplace_versions = {p["name"]: p["version"] for p in marketplace_entries}

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
