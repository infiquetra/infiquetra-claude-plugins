#!/usr/bin/env python3
"""
PR-scoped diff-aware release-surface bump guard (#429, R3/KTD4; extended #842).

Any plugin whose non-doc files changed in a diff (versus an authoritative base ref) must touch
that plugin's own `plugin.json` and `CHANGELOG.md` in the same diff, and its manifest `version`
must strictly advance compared to the version on the base-ref tip. Equal, lower, and malformed
or invalid versions fail naming the plugin and both values. Doc-only (`README.md`, `docs/**`)
or test-only (`tests/**`) changes are exempt — they don't require a bump.

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
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ManifestParseResult:
    error: str | None = None
    raw_version: str | None = None
    parsed_version: SemVer | None = None


def extract_manifest_version(content: str | None, manifest_label: str) -> ManifestParseResult:
    """Parse JSON manifest and semver. Return ManifestParseResult with error or parsed SemVer."""
    if content is None:
        return ManifestParseResult(error=f"{manifest_label} is missing")

    try:
        data = json.loads(content)
    except Exception:
        return ManifestParseResult(error=f"{manifest_label} has invalid JSON")

    if not isinstance(data, dict):
        return ManifestParseResult(
            error=f"{manifest_label} has invalid JSON (top-level is not an object)"
        )

    if "version" not in data:
        return ManifestParseResult(error=f"{manifest_label} is missing 'version' key")

    raw_version = data["version"]
    if not isinstance(raw_version, str):
        return ManifestParseResult(
            error=f"{manifest_label} 'version' is not a string ({raw_version!r})",
            raw_version=str(raw_version),
        )

    parsed = parse_semver(raw_version)
    if parsed is None:
        return ManifestParseResult(
            error=f"{manifest_label} version {raw_version!r} is malformed",
            raw_version=raw_version,
        )

    return ManifestParseResult(raw_version=raw_version, parsed_version=parsed)


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

        manifest_path = f"plugins/{plugin_name}/.claude-plugin/plugin.json"
        if manifest_reader is None:
            base_content = read_committed_file(base_ref, manifest_path, runner=runner)
            head_content = read_committed_file("HEAD", manifest_path, runner=runner)
        else:
            base_content = manifest_reader("base", manifest_path)
            head_content = manifest_reader("HEAD", manifest_path)

        head_res = extract_manifest_version(head_content, f"proposed manifest {manifest_path}")
        if head_res.error:
            if base_content is not None:
                base_res = extract_manifest_version(
                    base_content, f"base-ref manifest {manifest_path}"
                )
                if base_res.raw_version is not None:
                    violations.append(
                        f"{plugin_name}: {head_res.error} (base-ref version: {base_res.raw_version!r})"
                    )
                else:
                    violations.append(f"{plugin_name}: {head_res.error}")
            else:
                violations.append(f"{plugin_name}: {head_res.error} (base-ref version: <absent>)")
            continue

        assert head_res.parsed_version is not None
        assert head_res.raw_version is not None

        if base_content is None:
            # New plugin on base_ref — head version is valid semver
            continue

        base_res = extract_manifest_version(base_content, f"base-ref manifest {manifest_path}")
        if base_res.error:
            violations.append(
                f"{plugin_name}: {base_res.error} (proposed version: {head_res.raw_version!r})"
            )
            continue

        assert base_res.parsed_version is not None
        assert base_res.raw_version is not None

        if head_res.parsed_version == base_res.parsed_version:
            violations.append(
                f"{plugin_name}: proposed manifest version {head_res.raw_version!r} is equal to "
                f"base-ref version {base_res.raw_version!r} (must be strictly greater)"
            )
        elif head_res.parsed_version < base_res.parsed_version:
            violations.append(
                f"{plugin_name}: proposed manifest version {head_res.raw_version!r} is lower than "
                f"base-ref version {base_res.raw_version!r} (must be strictly greater)"
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
