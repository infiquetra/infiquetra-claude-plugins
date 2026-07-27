#!/usr/bin/env python3
"""Structural lint for the engineering journal's newest-first convention (#659).

`LEARNINGS.md` and `DECISIONS.md` both declare "append new entries to the top, most-recent
first" and both had drifted away from it: 16 and 20 entries respectively had accumulated below
the oldest date heading, filed under `## 2026-05-01` while dating from July -- roughly 10% of
each file, invisible to anyone who trusted the header and read from the top. Four date headings
were duplicated, and five DECISIONS entries had been written at `##` instead of `###`, so they
read as section headings rather than entries.

Nothing mechanical caused that drift; it was authored by hand, one entry at a time, each one
locally reasonable. That is exactly the class of decay a lint exists to stop, so this checks the
structure every run rather than trusting the prose instruction.

Two modes:

* structural (always) -- date headings strictly descending and unique, entries at `###`, no
  entry stranded above the first date heading.
* diff-scoped (``--base-ref``) -- an entry ADDED by this branch must land in the newest date
  section. This is the check that actually prevents recurrence, and it mirrors the existing
  PR-scoped guard in ``tools/release_surface_diff_guard.py``.

Deliberately NOT a schema validator: #407 tracks validating each entry's internal shape
(Context/Evidence/Mechanism/...). This one only cares about ordering and heading levels.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_JOURNALS = (
    "docs/engineering-journal/LEARNINGS.md",
    "docs/engineering-journal/DECISIONS.md",
)

DATE_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")
ENTRY = re.compile(r"^### ")
#: An entry mistakenly written at `##`: an H2 that is not a date and carries an entry anchor.
MISLEVELLED = re.compile(r"^## (?!\d{4}-\d{2}-\d{2}\s*$).*\{#[^}]+\}\s*$")


def _run(args: list[str], cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True).stdout


def check_structure(rel: str, text: str) -> list[str]:
    """Ordering and heading-level violations, as human-readable lines."""
    problems: list[str] = []
    lines = text.splitlines()

    headings = [
        (i + 1, m.group(1)) for i, line in enumerate(lines) if (m := DATE_HEADING.match(line))
    ]
    if not headings:
        return [f"{rel}: no `## YYYY-MM-DD` headings found"]

    for (n1, d1), (n2, d2) in zip(headings, headings[1:], strict=False):
        if d1 < d2:
            problems.append(
                f"{rel}:{n2}: `## {d2}` comes after `## {d1}` (line {n1}) — "
                f"headings must run newest-first"
            )

    seen: dict[str, int] = {}
    for n, d in headings:
        if d in seen:
            problems.append(
                f"{rel}:{n}: duplicate `## {d}` (already opened at line {seen[d]}) — "
                f"merge the two sections"
            )
        else:
            seen[d] = n

    for i, line in enumerate(lines):
        if MISLEVELLED.match(line):
            problems.append(
                f"{rel}:{i + 1}: entry written at `##`; entries are `###` — {line[3:63].strip()}"
            )

    first_heading = headings[0][0]
    for i, line in enumerate(lines[: first_heading - 1]):
        if ENTRY.match(line):
            problems.append(
                f"{rel}:{i + 1}: entry appears above the first date heading — {line[4:64].strip()}"
            )
    return problems


def check_new_entries(rel: str, text: str, base_ref: str, root: Path) -> list[str]:
    """Entries ADDED relative to base_ref must live in the newest date section.

    "Added" is decided by comparing the two versions' sets of entry headings, NOT by reading
    `+` lines out of a diff. A diff cannot tell a new entry from a relocated one -- every moved
    entry shows up as a deletion plus an addition -- so a re-filing pass (exactly what #659's own
    migration was) would be flagged as hundreds of misfilings. Set comparison makes a move a
    no-op, which is the correct semantics: moving an existing entry is how you FIX this file.
    """
    try:
        base_text = _run(["git", "show", f"{base_ref}:{rel}"], root)
    except subprocess.CalledProcessError:
        # New journal in this branch: every entry is new, so require them all to be up top.
        base_text = ""

    def key(heading: str) -> str:
        """Identity of an entry, independent of heading level and surrounding whitespace.

        Keyed on the `{#slug}` anchor when there is one, so re-levelling an entry (`##` -> `###`,
        which the #659 migration did to five of them) and re-wording nothing else reads as the
        same entry rather than a new one. Falls back to the stripped title for unanchored entries.
        """
        if m := re.search(r"\{#([^}]+)\}", heading):
            return f"#{m.group(1)}"
        return re.sub(r"^#+\s*", "", heading).strip()

    def entry_keys(src: str) -> set[str]:
        return {key(ln) for ln in src.splitlines() if ENTRY.match(ln) or MISLEVELLED.match(ln)}

    base_keys = entry_keys(base_text)
    added = {
        ln.rstrip()
        for ln in text.splitlines()
        if (ENTRY.match(ln) or MISLEVELLED.match(ln)) and key(ln) not in base_keys
    }
    if not added:
        return []

    lines = text.splitlines()
    headings = [i for i, line in enumerate(lines) if DATE_HEADING.match(line)]
    if not headings:
        return [f"{rel}: entries added but the file has no date heading"]
    newest_start = headings[0]
    newest_end = headings[1] if len(headings) > 1 else len(lines)
    newest = {ln.rstrip() for ln in lines[newest_start:newest_end] if ENTRY.match(ln)}
    newest_date = DATE_HEADING.match(lines[newest_start]).group(1)  # type: ignore[union-attr]

    problems = []
    for entry in sorted(added - newest):
        problems.append(
            f"{rel}: new entry filed outside the newest section (`## {newest_date}`) — "
            f"{entry[4:64].strip()}"
        )
    if problems:
        problems.append(
            f"{rel}: add a `## <today>` heading at the top and put new entries under it; "
            f"do not append at the end of the file"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="lint_journal_order.py",
        description="Check the engineering journal's newest-first ordering (#659).",
    )
    ap.add_argument("journals", nargs="*", default=list(DEFAULT_JOURNALS))
    ap.add_argument(
        "--base-ref",
        help="also require entries added since this ref to sit in the newest date section",
    )
    ap.add_argument("--root", type=Path, default=Path.cwd())
    args = ap.parse_args(argv)

    problems: list[str] = []
    checked = 0
    for rel in args.journals or list(DEFAULT_JOURNALS):
        path = args.root / rel
        if not path.is_file():
            # A repo without this journal is not a violation — the fleet has many plugins
            # and only some carry one.
            continue
        checked += 1
        text = path.read_text(encoding="utf-8")
        problems.extend(check_structure(rel, text))
        if args.base_ref:
            problems.extend(check_new_entries(rel, text, args.base_ref, args.root))

    for p in problems:
        print(p, file=sys.stderr)
    print(f"journal-order lint: {checked} file(s) checked, VIOLATIONS: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
