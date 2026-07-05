#!/usr/bin/env python3
"""
Lint each plugin's `CHANGELOG.md` against the fleet's canonical heading grammar (#429, KTD1,
`docs/engineering-journal/DECISIONS.md#release-surface-single-source-429`):

- The file title is exactly `# Changelog` (no plugin-name suffix).
- Each version heading is `## [X.Y.Z] - YYYY-MM-DD` (bracketed version, hyphen-minus date).
- An optional `## [Unreleased]` heading (no date) may precede the first dated entry.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"

TITLE_RE = re.compile(r"^# Changelog$")
VERSION_HEADING_RE = re.compile(r"^## \[\d+\.\d+\.\d+\] - \d{4}-\d{2}-\d{2}$")
UNRELEASED_HEADING_RE = re.compile(r"^## \[Unreleased\]$")


@dataclass
class LintFailure:
    path: Path
    line_number: int
    line: str
    reason: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line_number}: {self.reason} — {self.line!r}"


def lint_changelog(path: Path) -> list[LintFailure]:
    lines = path.read_text().splitlines()
    failures: list[LintFailure] = []

    title_lines = [(i, line) for i, line in enumerate(lines, start=1) if line.startswith("# ")]
    if not title_lines or not TITLE_RE.match(title_lines[0][1]):
        line_number, line = title_lines[0] if title_lines else (1, "")
        failures.append(LintFailure(path, line_number, line, "title must be exactly '# Changelog'"))

    for i, line in enumerate(lines, start=1):
        if not line.startswith("## "):
            continue
        if VERSION_HEADING_RE.match(line) or UNRELEASED_HEADING_RE.match(line):
            continue
        failures.append(
            LintFailure(
                path,
                i,
                line,
                "version heading must match '## [X.Y.Z] - YYYY-MM-DD' or '## [Unreleased]'",
            )
        )

    return failures


def lint_fleet(plugins_dir: Path = PLUGINS_DIR) -> dict[Path, list[LintFailure]]:
    results: dict[Path, list[LintFailure]] = {}
    for changelog in sorted(plugins_dir.glob("*/CHANGELOG.md")):
        failures = lint_changelog(changelog)
        if failures:
            results[changelog] = failures
    return results


def main(argv: list[str] | None = None) -> int:
    del argv
    results = lint_fleet()
    if not results:
        print("changelog_heading_lint: all plugin CHANGELOGs match the canonical grammar")
        return 0
    for _path, failures in results.items():
        for failure in failures:
            print(failure, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
