#!/usr/bin/env python3
"""Pagination-completeness lint for mission-control's GitHub list calls (#424, T9-F4-5).

Scans mission-control's own Python scripts and skill/agent/command reference
docs for `gh` list invocations that fetch a bounded page of results with no
cursor loop and no explicit `--limit` guard -- the call-site shape named in
the grounding brief's session-mining synthesis as a recurring fleet defect:
"mission-control board/field drift ... item-list pagination silently
truncating at 200 of 375 items"
(docs/plans/2026-07-03-plugin-fleet-grounding-brief.md §7, pattern 3).

Three guarded patterns, one violation kind each:

  1. Raw CLI list calls (``gh project item-list ...``) with no ``--limit``
     on the same line -- ``gh``'s own default page size silently caps
     output at 30 items with no visible truncation signal.
  2. Bare REST list fetches (``_rest_get(...per_page=...)``) instead of the
     shared ``_rest_list_paginated()`` helper (``sdlc_manager.py``, #424)
     that loops pages until a short page proves the list is exhausted.
  3. A GraphQL query literal that sets a page-size arg (``first:``) in a
     file that never checks ``hasNextPage`` anywhere -- such a query has
     no way to detect that it stopped short of the full list.

Exit 0 = no unguarded call sites found; exit 1 = at least one violation.

Usage::

    python3 check_pagination.py             # scans mission-control's own tree
    python3 check_pagination.py <path> ...   # scans explicit paths instead
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_MISSION_CONTROL_DIR = _SCRIPTS_DIR.parent

DEFAULT_ROOTS = (
    _MISSION_CONTROL_DIR / "scripts",
    _MISSION_CONTROL_DIR / "skills",
    _MISSION_CONTROL_DIR / "commands",
    _MISSION_CONTROL_DIR / "agents",
)

# This lint script's own docstring/body legitimately mentions the guarded
# patterns by name; exclude it from its own scan.
_SELF_PATH = Path(__file__).resolve()

RAW_ITEM_LIST_RE = re.compile(r"gh\s+project\s+item-list\b")
BARE_REST_PAGE_RE = re.compile(r"_rest_get\([^)]*per_page=")
GRAPHQL_FIRST_RE = re.compile(r"\bfirst\s*:\s*\d+")
COMMENT_LINE_RE = re.compile(r"^\s*#")
SUPPRESS_MARKER = "# pagination-lint: allow"

SCAN_SUFFIXES = (".py", ".md")

# How many lines (including the match line) to search for a `--limit` guard,
# so a `--limit` on a wrapped/continuation line still counts as a guard.
_INVOCATION_WINDOW = 3


def iter_files(roots: list[Path]) -> list[Path]:
    """Collect scannable files under `roots`, de-duplicated, order-preserving."""
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            files.append(root)
            continue
        for suffix in SCAN_SUFFIXES:
            files.extend(sorted(root.rglob(f"*{suffix}")))

    seen: set[Path] = set()
    ordered: list[Path] = []
    for f in files:
        resolved = f.resolve()
        if resolved == _SELF_PATH or resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(f)
    return ordered


def check_file(path: Path) -> list[str]:
    """Return human-readable violations for one file; empty list = clean."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    violations: list[str] = []

    for lineno, line in enumerate(lines, start=1):
        if SUPPRESS_MARKER in line:
            continue
        if RAW_ITEM_LIST_RE.search(line):
            # A comment line mentioning the command by name (e.g. explaining its
            # flattening behavior) is documentation, not an invocation to guard.
            if COMMENT_LINE_RE.match(line):
                continue
            window = "\n".join(lines[lineno - 1 : lineno - 1 + _INVOCATION_WINDOW])
            if "--limit" not in window:
                violations.append(
                    f"{path}:{lineno}: unguarded `gh project item-list` (no cursor "
                    f"loop, no --limit) -- add --limit N or route through a "
                    f"documented pagination loop"
                )
        if BARE_REST_PAGE_RE.search(line):
            violations.append(
                f"{path}:{lineno}: bare per_page REST fetch via `_rest_get` -- use "
                f"`_rest_list_paginated()` (sdlc_manager.py, #424) instead"
            )

    if GRAPHQL_FIRST_RE.search(text) and "hasNextPage" not in text:
        violations.append(
            f"{path}: GraphQL query sets a page-size arg (`first:`) but this file "
            f"never checks `hasNextPage` -- the query cannot detect truncation"
        )

    return violations


def run_lint(roots: list[Path] | None = None) -> list[str]:
    """Return all violations across `roots` (defaults to mission-control's own tree)."""
    all_violations: list[str] = []
    for path in iter_files(roots if roots is not None else list(DEFAULT_ROOTS)):
        all_violations.extend(check_file(path))
    return all_violations


def main(argv: list[str]) -> int:
    roots = [Path(p) for p in argv] if argv else None
    violations = run_lint(roots)

    if violations:
        for v in violations:
            print(f"FAIL {v}")
        print(f"\npagination lint FAILED: {len(violations)} unguarded call site(s)")
        return 1

    print("pagination lint passed: no unguarded list call sites found")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
