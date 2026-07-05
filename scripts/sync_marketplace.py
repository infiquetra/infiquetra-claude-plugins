#!/usr/bin/env python3
"""
Generate `.claude-plugin/marketplace.json` plugin entries from each plugin's own
`plugin.json` (#429). Single source of truth: `plugin.json`. `marketplace.json` is a
generated mirror, never hand-edited.

`license` and `category` are marketplace-owned pass-through fields (KTD2, #429): no
plugin's `plugin.json` carries either field, so the generator preserves an existing
entry's values verbatim and never derives them from `plugin.json`. A plugin with no
prior marketplace entry has no value to preserve — `license` defaults to `MIT`
(every existing entry's current value) and `category` must be supplied via
`--category` or the run fails loudly rather than guessing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PLUGINS_DIR = REPO_ROOT / "plugins"

DEFAULT_LICENSE = "MIT"


class SyncMarketplaceError(Exception):
    pass


def discover_plugin_jsons(plugins_dir: Path = PLUGINS_DIR) -> list[Path]:
    return sorted(plugins_dir.glob("*/.claude-plugin/plugin.json"))


def load_json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def build_entry(
    plugin_json: dict[str, Any],
    plugin_dir_name: str,
    existing_entry: dict[str, Any] | None,
    category_override: str | None = None,
) -> dict[str, Any]:
    """Build a marketplace entry for one plugin (KTD2: license/category pass through)."""
    entry: dict[str, Any] = {
        "name": plugin_json["name"],
        "source": f"./plugins/{plugin_dir_name}",
        "version": plugin_json["version"],
        "description": plugin_json["description"],
        "author": plugin_json["author"],
        "repository": plugin_json["repository"],
        "license": DEFAULT_LICENSE,
        "keywords": plugin_json.get("keywords", []),
    }
    if existing_entry is not None:
        entry["license"] = existing_entry.get("license", DEFAULT_LICENSE)
        if "category" in existing_entry:
            entry["category"] = existing_entry["category"]
    if category_override is not None:
        entry["category"] = category_override
    if existing_entry is None and "category" not in entry:
        raise SyncMarketplaceError(
            f"plugin '{plugin_json['name']}' has no existing marketplace entry and no "
            "--category was supplied; category cannot be derived from plugin.json "
            "(KTD2) — pass --category explicitly for a new plugin"
        )
    return entry


def build_target_plugins(
    marketplace: dict[str, Any],
    plugins_dir: Path = PLUGINS_DIR,
    category_override: str | None = None,
) -> list[dict[str, Any]]:
    """Regenerate the plugins array, preserving existing entry order (KTD3)."""
    existing_by_name = {p["name"]: p for p in marketplace.get("plugins", [])}
    order = [p["name"] for p in marketplace.get("plugins", [])]

    plugin_json_paths = discover_plugin_jsons(plugins_dir)
    by_name: dict[str, tuple[dict[str, Any], str]] = {}
    for path in plugin_json_paths:
        pj = load_json(path)
        plugin_dir_name = path.parent.parent.name
        by_name[pj["name"]] = (pj, plugin_dir_name)

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in order:
        if name not in by_name:
            continue  # a plugin removed from plugins/ stays out of the regenerated array
        pj, plugin_dir_name = by_name[name]
        result.append(
            build_entry(pj, plugin_dir_name, existing_by_name.get(name), category_override)
        )
        seen.add(name)

    # New plugins (present in plugins/*/ but absent from marketplace.json) append in scan order.
    for path in plugin_json_paths:
        pj = load_json(path)
        if pj["name"] in seen:
            continue
        plugin_dir_name = path.parent.parent.name
        result.append(build_entry(pj, plugin_dir_name, None, category_override))
        seen.add(pj["name"])

    return result


def diff_entries(current: list[dict[str, Any]], target: list[dict[str, Any]]) -> list[str]:
    """Return plugin names whose generated entry differs from the committed one."""
    current_by_name = {p["name"]: p for p in current}
    target_by_name = {p["name"]: p for p in target}
    drifted = []
    for name, target_entry in target_by_name.items():
        if current_by_name.get(name) != target_entry:
            drifted.append(name)
    for name in current_by_name:
        if name not in target_by_name:
            drifted.append(name)
    return sorted(drifted)


def run(
    check: bool,
    category_override: str | None,
    marketplace_path: Path = MARKETPLACE_PATH,
    plugins_dir: Path = PLUGINS_DIR,
) -> int:
    marketplace = load_json(marketplace_path)
    try:
        target_plugins = build_target_plugins(marketplace, plugins_dir, category_override)
    except SyncMarketplaceError as exc:
        print(f"sync_marketplace: {exc}", file=sys.stderr)
        return 1

    if check:
        drifted = diff_entries(marketplace.get("plugins", []), target_plugins)
        if drifted:
            print(
                "sync_marketplace --check: marketplace.json is stale for: " + ", ".join(drifted),
                file=sys.stderr,
            )
            return 1
        print("sync_marketplace --check: marketplace.json matches plugin.json fleet")
        return 0

    marketplace["plugins"] = target_plugins
    marketplace_path.write_text(json.dumps(marketplace, indent=2) + "\n")
    print(f"sync_marketplace: wrote {len(target_plugins)} plugin entries")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if marketplace.json disagrees with generated output, without writing",
    )
    parser.add_argument(
        "--category",
        default=None,
        help="category for a plugin with no existing marketplace entry (required for new plugins)",
    )
    args = parser.parse_args(argv)
    return run(check=args.check, category_override=args.category)


if __name__ == "__main__":
    sys.exit(main())
