#!/usr/bin/env python3
"""
PR-scoped diff-aware release-surface bump guard (#429, R3/KTD4).

Any plugin whose non-doc files changed in a diff (versus a base ref) must also touch that
plugin's own `plugin.json` and `CHANGELOG.md` in the same diff. Doc-only (`README.md`,
`docs/**`) or test-only (`tests/**`) changes are exempt — they don't require a bump.

The base ref is taken explicitly via `--base-ref` (CI supplies the PR's
`github.event.pull_request.base.sha`); this keeps the guard testable against fixture git repos
without faking GitHub Actions' event context.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict

DEFAULT_BASE_REF = "origin/main"

PLUGIN_PATH_RE = re.compile(r"^plugins/([^/]+)/(.*)$")
DOC_EXEMPT_SUFFIXES = ("README.md",)


class DiffGuardError(Exception):
    pass


def changed_files(base_ref: str, runner=None) -> list[str]:
    run = runner if runner is not None else subprocess.run
    result = run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise DiffGuardError(f"git diff failed against base ref {base_ref!r}: {result.stderr}")
    return [line for line in result.stdout.splitlines() if line]


def is_bump_required_path(plugin_relative_path: str) -> bool:
    """Non-doc, non-test path within a plugin's directory requires a bump."""
    if plugin_relative_path in DOC_EXEMPT_SUFFIXES:
        return False
    if plugin_relative_path == "CHANGELOG.md":
        return False
    return not (plugin_relative_path.startswith("tests/") or "/tests/" in plugin_relative_path)


def classify_by_plugin(paths: list[str]) -> dict[str, list[str]]:
    by_plugin: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        match = PLUGIN_PATH_RE.match(path)
        if match is None:
            continue
        plugin_name, relative_path = match.groups()
        by_plugin[plugin_name].append(relative_path)
    return by_plugin


def find_violations(paths: list[str]) -> list[str]:
    """Return the names of plugins that changed non-doc files without a matching bump."""
    by_plugin = classify_by_plugin(paths)
    violations = []
    for plugin_name, relative_paths in sorted(by_plugin.items()):
        bump_required = any(is_bump_required_path(p) for p in relative_paths)
        if not bump_required:
            continue
        bumped_plugin_json = ".claude-plugin/plugin.json" in relative_paths
        bumped_changelog = "CHANGELOG.md" in relative_paths
        if not (bumped_plugin_json and bumped_changelog):
            violations.append(plugin_name)
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-ref",
        default=DEFAULT_BASE_REF,
        help=f"base ref to diff against (default: {DEFAULT_BASE_REF})",
    )
    args = parser.parse_args(argv)

    try:
        paths = changed_files(args.base_ref)
    except DiffGuardError as exc:
        print(f"release_surface_diff_guard: {exc}", file=sys.stderr)
        return 1

    violations = find_violations(paths)
    if violations:
        print(
            "release_surface_diff_guard: non-doc files changed without a matching "
            "plugin.json + CHANGELOG.md bump for: " + ", ".join(violations),
            file=sys.stderr,
        )
        return 1
    print("release_surface_diff_guard: all changed plugins bumped their release surfaces")
    return 0


if __name__ == "__main__":
    sys.exit(main())
