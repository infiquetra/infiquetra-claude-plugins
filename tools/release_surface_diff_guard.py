#!/usr/bin/env python3
"""
PR-scoped diff-aware release-surface bump guard (#429, R3/KTD4; extended #842).

Any plugin whose non-doc files changed in a diff (versus a base ref) must touch that plugin's
own `plugin.json` and `CHANGELOG.md` in the same diff, and its manifest `version` must strictly
advance compared to the merge-base version. Equal, lower, malformed, and incomparable versions
fail naming the plugin and both values. Doc-only (`README.md`, `docs/**`) or test-only
(`tests/**`) changes are exempt — they don't require a bump.

The base ref is taken explicitly via `--base-ref` (CI supplies the PR's
`github.event.pull_request.base.sha`); this keeps the guard testable against fixture git repos
without faking GitHub Actions' event context.
"""

from __future__ import annotations

import argparse
import functools
import json
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable
from typing import Any

DEFAULT_BASE_REF = "origin/main"

PLUGIN_PATH_RE = re.compile(r"^plugins/([^/]+)/(.*)$")
DOC_EXEMPT_BASENAME = "README.md"
DOC_EXEMPT_PREFIX = "docs/"

SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


class DiffGuardError(Exception):
    pass


@functools.total_ordering
class SemVer:
    """Semantic version parser supporting SemVer 2.0 precedence comparison."""

    def __init__(
        self,
        major: int,
        minor: int,
        patch: int,
        prerelease: tuple[int | str, ...] = (),
        raw: str = "",
    ) -> None:
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = prerelease
        self.raw = raw

    def _cmp_key(self) -> tuple[Any, ...]:
        if not self.prerelease:
            pre_key: tuple[int, Any] = (1, ())
        else:
            parts: list[tuple[int, int | str]] = []
            for p in self.prerelease:
                if isinstance(p, int):
                    parts.append((0, p))
                else:
                    parts.append((1, p))
            pre_key = (0, tuple(parts))
        return (self.major, self.minor, self.patch, pre_key)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._cmp_key() == other._cmp_key()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._cmp_key() < other._cmp_key()

    def __repr__(self) -> str:
        return f"SemVer({self.raw!r})"

    def __str__(self) -> str:
        return self.raw


def parse_semver(version: str | None) -> SemVer | None:
    if not isinstance(version, str):
        return None
    match = SEMVER_RE.match(version.strip())
    if not match:
        return None
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))
    prerelease_raw = match.group("prerelease")
    prerelease_parts: list[int | str] = []
    if prerelease_raw:
        for part in prerelease_raw.split("."):
            if not part:
                return None
            if part.isdigit():
                if len(part) > 1 and part.startswith("0"):
                    return None
                prerelease_parts.append(int(part))
            else:
                prerelease_parts.append(part)
    return SemVer(major, minor, patch, tuple(prerelease_parts), raw=version)


def get_merge_base(
    base_ref: str,
    head_ref: str = "HEAD",
    *,
    runner: Callable[..., Any] | None = None,
) -> str:
    run = runner if runner is not None else subprocess.run
    result = run(
        ["git", "merge-base", base_ref, head_ref],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise DiffGuardError(
            f"git merge-base failed for {base_ref!r} and {head_ref!r}: {result.stderr}"
        )
    return result.stdout.strip()


def read_committed_file(
    ref: str,
    path: str,
    *,
    runner: Callable[..., Any] | None = None,
) -> str | None:
    run = runner if runner is not None else subprocess.run
    result = run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def changed_files(base_ref: str, *, runner: Callable[..., Any] | None = None) -> list[str]:
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
    if plugin_relative_path == DOC_EXEMPT_BASENAME or plugin_relative_path.endswith(
        f"/{DOC_EXEMPT_BASENAME}"
    ):
        return False
    if plugin_relative_path == "CHANGELOG.md":
        return False
    if plugin_relative_path.startswith(DOC_EXEMPT_PREFIX) or f"/{DOC_EXEMPT_PREFIX}" in (
        plugin_relative_path
    ):
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


def find_violations(
    paths: list[str],
    base_ref: str = DEFAULT_BASE_REF,
    *,
    runner: Callable[..., Any] | None = None,
    manifest_reader: Callable[[str, str], str | None] | None = None,
) -> list[str]:
    """Return violations for plugins whose non-doc files changed without an advancing version."""
    by_plugin = classify_by_plugin(paths)
    violations: list[str] = []

    reader = manifest_reader
    merge_base: str | None = None

    for plugin_name, relative_paths in sorted(by_plugin.items()):
        bump_required = any(is_bump_required_path(p) for p in relative_paths)
        if not bump_required:
            continue
        bumped_plugin_json = ".claude-plugin/plugin.json" in relative_paths
        bumped_changelog = "CHANGELOG.md" in relative_paths
        if not (bumped_plugin_json and bumped_changelog):
            violations.append(
                f"{plugin_name}: non-doc files changed without a matching "
                "plugin.json + CHANGELOG.md bump"
            )
            continue

        if reader is None:
            if merge_base is None:
                merge_base = get_merge_base(base_ref, "HEAD", runner=runner)
            base_content = read_committed_file(
                merge_base, f"plugins/{plugin_name}/.claude-plugin/plugin.json", runner=runner
            )
            head_content = read_committed_file(
                "HEAD", f"plugins/{plugin_name}/.claude-plugin/plugin.json", runner=runner
            )
        else:
            base_content = reader("base", f"plugins/{plugin_name}/.claude-plugin/plugin.json")
            head_content = reader("HEAD", f"plugins/{plugin_name}/.claude-plugin/plugin.json")

        if head_content is None:
            violations.append(
                f"{plugin_name}: missing head manifest plugins/{plugin_name}/.claude-plugin/plugin.json"
            )
            continue

        try:
            head_data = json.loads(head_content)
            head_version = head_data.get("version") if isinstance(head_data, dict) else None
        except Exception:
            head_version = None

        head_version_str = head_version if isinstance(head_version, str) else str(head_version)
        head_parsed = parse_semver(head_version) if isinstance(head_version, str) else None

        if base_content is None:
            # New plugin — no base version exists
            if head_parsed is None:
                violations.append(
                    f"{plugin_name}: proposed manifest version {head_version_str!r} is malformed "
                    f"(merge-base version: <absent>)"
                )
            continue

        try:
            base_data = json.loads(base_content)
            base_version = base_data.get("version") if isinstance(base_data, dict) else None
        except Exception:
            base_version = None

        base_version_str = base_version if isinstance(base_version, str) else str(base_version)
        base_parsed = parse_semver(base_version) if isinstance(base_version, str) else None

        if head_parsed is None:
            violations.append(
                f"{plugin_name}: proposed manifest version {head_version_str!r} is malformed "
                f"(merge-base version: {base_version_str!r})"
            )
        elif base_parsed is None:
            violations.append(
                f"{plugin_name}: merge-base manifest version {base_version_str!r} is malformed "
                f"(proposed version: {head_version_str!r})"
            )
        else:
            try:
                is_equal = head_parsed == base_parsed
                is_lower = head_parsed < base_parsed
            except TypeError:
                violations.append(
                    f"{plugin_name}: proposed manifest version {head_version_str!r} is "
                    f"incomparable to merge-base version {base_version_str!r}"
                )
                continue

            if is_equal:
                violations.append(
                    f"{plugin_name}: proposed manifest version {head_version_str!r} is equal to "
                    f"merge-base version {base_version_str!r} (must be strictly greater)"
                )
            elif is_lower:
                violations.append(
                    f"{plugin_name}: proposed manifest version {head_version_str!r} is lower than "
                    f"merge-base version {base_version_str!r} (must be strictly greater)"
                )

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
        violations = find_violations(paths, base_ref=args.base_ref)
    except DiffGuardError as exc:
        print(f"release_surface_diff_guard: {exc}", file=sys.stderr)
        return 1

    if violations:
        print(
            "release_surface_diff_guard: violations found:\n"
            + "\n".join(f"  - {v}" for v in violations),
            file=sys.stderr,
        )
        return 1
    print("release_surface_diff_guard: all changed plugins bumped their release surfaces")
    return 0


if __name__ == "__main__":
    sys.exit(main())
