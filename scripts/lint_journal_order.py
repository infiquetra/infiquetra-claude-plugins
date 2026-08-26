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

Three modes:

* structural (always) -- date headings strictly descending and unique, entries at `###`, no
  entry stranded above the first date heading.
* anchors (always) -- heading-attached ``{#slug}`` definitions are unique across the joint
  file set, and ``](#slug)`` / non-heading ``{#slug}`` mentions resolve to that set (#407).
  Cross-file Markdown fragment links (``](FILE.md#anchor)``) among the covered journal set
  resolve against the destination file's explicit ``{#slug}`` and GitHub-generated heading
  anchors (#838).
* diff-scoped (``--base-ref``) -- an entry ADDED by this branch must land in the newest date
  section. This is the check that actually prevents recurrence, and it mirrors the existing
  PR-scoped guard in ``tools/release_surface_diff_guard.py``.

Deliberately NOT a schema validator: prose fields (Context/Evidence/Mechanism/Revisit when)
and commit-hash presence are out of scope (operator ruling on #407).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_JOURNALS = (
    "docs/engineering-journal/LEARNINGS.md",
    "docs/engineering-journal/DECISIONS.md",
)
#: ARCHIVE/QUEUED carry heading anchors but not newest-first date sections, so they join
#: the definition set without joining the ordering check. A LEARNINGS citation of a QUEUED
#: slug is a real edge in the graph, not a dangle.
ANCHOR_EXTRA = (
    "docs/engineering-journal/ARCHIVE.md",
    "docs/engineering-journal/QUEUED.md",
)

DATE_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")
ENTRY = re.compile(r"^### ")
#: An entry mistakenly written at `##`: an H2 that is not a date and carries an entry anchor.
MISLEVELLED = re.compile(r"^## (?!\d{4}-\d{2}-\d{2}\s*$).*\{#[^}]+\}\s*$")
HEADING_LINE = re.compile(r"^#{1,6}\s+")
BRACE_ANCHOR = re.compile(r"\{#([^}]+)\}")
MARKDOWN_LINK = re.compile(r"\]\(([^)\s\"]+)\)")
FENCE_MARK = re.compile(r"^(?:> ?)* {0,3}(`{3,}|~{3,})")
#: The format-template placeholder in the journal headers, not a citation.
PLACEHOLDER_SLUGS = frozenset({"slug"})


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

    def identity(heading: str) -> tuple[str, str | None]:
        """An entry's (title, slug). Slug is None for an unanchored entry."""
        title = re.sub(r"\{#[^}]+\}", "", heading)
        title = re.sub(r"^#+\s*", "", title).strip()
        m = re.search(r"\{#([^}]+)\}", heading)
        return title, (m.group(1) if m else None)

    def pairs(src: str) -> set[tuple[str, str | None]]:
        return {identity(ln) for ln in src.splitlines() if ENTRY.match(ln) or MISLEVELLED.match(ln)}

    base_pairs = pairs(base_text)
    base_slugs = {slug for _, slug in base_pairs if slug}
    new_pairs = pairs(text)

    def is_new(heading: str) -> bool:
        """Whether this entry is a NEW filing rather than an existing one moved or renamed.

        Three exemptions, each carved for a real edit that must not read as a new entry:

        * the exact (title, slug) pair was already in the base -- a pure move or re-level;
        * the slug was already in the base -- the title was re-worded in place;
        * the title was in the base under a slug that no longer sits on that title -- the
          slug was renamed, which is how a duplicate `{#slug}` gets disambiguated (#407).

        The third exemption is deliberately keyed to the base entry's OWN (title, slug) pair
        disappearing. Keying it to the title alone would let a genuinely new entry that reuses
        an existing title be filed at the bottom of the file unchecked, which is exactly the
        drift this function exists to catch.
        """
        title, slug = identity(heading)
        if (title, slug) in base_pairs:
            return False
        if slug and slug in base_slugs:
            return False
        return not any(bt == title and (bt, bs) not in new_pairs for bt, bs in base_pairs)

    added = {
        ln.rstrip()
        for ln in text.splitlines()
        if (ENTRY.match(ln) or MISLEVELLED.match(ln)) and is_new(ln)
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


def _scan(text: str) -> tuple[list[tuple[int, str]], int | None]:
    """Active (non-fenced) lines as (1-based line, text), plus any unclosed fence's line.

    Blockquoted fences count, so a ``> ```markdown`` template block is skipped like any
    other. The second return value is the line that opened a fence never closed by the end
    of the file: everything after it was skipped, so the caller must report it rather than
    silently checking a truncated file (a fence typo would otherwise switch both anchor
    checks off for the remainder of the file and still print VIOLATIONS: 0).
    """
    fence: tuple[str, int, int] | None = None
    out: list[tuple[int, str]] = []
    for i, line in enumerate(text.splitlines(), 1):
        m = FENCE_MARK.match(line)
        if m:
            marker = m.group(1)
            ch, n = marker[0], len(marker)
            if fence is None:
                fence = (ch, n, i)
            elif ch == fence[0] and n >= fence[1]:
                fence = None
            continue
        if fence is None:
            out.append((i, line))
    return out, (fence[2] if fence else None)


def _heading_definitions(active: list[tuple[int, str]]) -> list[tuple[str, int]]:
    """Heading-attached ``{#slug}`` definitions as (slug, line)."""
    found: list[tuple[str, int]] = []
    for n, line in active:
        if not HEADING_LINE.match(line):
            continue
        for m in BRACE_ANCHOR.finditer(line):
            slug = m.group(1).strip()
            if slug:
                found.append((slug, n))
    return found


def _github_slug(heading_line: str) -> str:
    """GitHub-generated heading slug from a Markdown heading line."""
    text = re.sub(r"^#{1,6}\s+", "", heading_line)
    text = re.sub(r"\{#[^}]+\}", "", text).strip()
    text = re.sub(r"[`*_~]", "", text)
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-")


def _heading_slugs(active: list[tuple[int, str]]) -> set[str]:
    """GitHub-generated heading anchor slugs from active heading lines."""
    slugs: set[str] = set()
    counts: dict[str, int] = {}
    for _, line in active:
        if not HEADING_LINE.match(line):
            continue
        base_slug = _github_slug(line)
        if not base_slug:
            continue
        count = counts.get(base_slug, 0)
        counts[base_slug] = count + 1
        if count == 0:
            slugs.add(base_slug)
        else:
            slugs.add(f"{base_slug}-{count}")
    return slugs


def _references(active: list[tuple[int, str]]) -> list[tuple[str | None, str, int]]:
    """Same-file mentions/fragments and cross-file Markdown fragment links.

    Returns tuples of (target_file_or_None, anchor, line). target_file is None
    for same-file fragment targets (](#anchor)) and non-heading {#slug} mentions.
    """
    found: list[tuple[str | None, str, int]] = []
    seen: set[tuple[str | None, str, int]] = set()
    for n, line in active:
        is_heading = bool(HEADING_LINE.match(line))
        if not is_heading:
            for m in BRACE_ANCHOR.finditer(line):
                slug = m.group(1).strip()
                if not slug or slug in PLACEHOLDER_SLUGS:
                    continue
                mention_key: tuple[str | None, str, int] = (None, slug, n)
                if mention_key not in seen:
                    seen.add(mention_key)
                    found.append(mention_key)
        for m in MARKDOWN_LINK.finditer(line):
            target = m.group(1).strip()
            if "#" not in target:
                continue
            dest_file, anchor = target.split("#", 1)
            dest_file = dest_file.strip()
            anchor = anchor.strip()
            if not anchor or anchor in PLACEHOLDER_SLUGS:
                continue
            if dest_file.startswith(("http://", "https://", "mailto:")):
                continue
            file_part = dest_file if dest_file else None
            link_key: tuple[str | None, str, int] = (file_part, anchor, n)
            if link_key not in seen:
                seen.add(link_key)
                found.append(link_key)
    return found


def check_anchors(files: list[tuple[str, str]]) -> list[str]:
    """Duplicate heading ``{#slug}`` definitions and dangling references, jointly.

    Definitions are heading-attached ``{#slug}`` across *files* together — a slug
    defined in LEARNINGS.md and again in DECISIONS.md is a duplicate. References
    include same-file mentions/fragments as well as cross-file ``](FILE.md#anchor)``
    links resolved against destination files' explicit ``{#slug}`` and GitHub-generated
    heading slugs. Duplicate reports name every definition site; dangling reports
    name the referencing line and destination; an unclosed code fence is reported
    on its own line.
    """
    defs: dict[str, list[tuple[str, int]]] = {}
    file_defs: dict[str, set[str]] = {}
    file_heading_slugs: dict[str, set[str]] = {}
    file_refs: list[tuple[str, list[tuple[str | None, str, int]]]] = []
    problems: list[str] = []

    covered_by_basename: dict[str, str] = {}
    for rel, text in files:
        covered_by_basename[Path(rel).name] = rel
        active, unclosed = _scan(text)
        if unclosed is not None:
            problems.append(
                f"{rel}:{unclosed}: code fence opened here is never closed — "
                f"the rest of the file is not anchor-checked"
            )
        f_defs: set[str] = set()
        for slug, n in _heading_definitions(active):
            defs.setdefault(slug, []).append((rel, n))
            f_defs.add(slug)
        file_defs[rel] = f_defs
        file_heading_slugs[rel] = _heading_slugs(active)
        file_refs.append((rel, _references(active)))

    for slug in sorted(defs):
        sites = defs[slug]
        if len(sites) < 2:
            continue
        named = " and ".join(f"{rel}:{n}" for rel, n in sites)
        problems.append(f"duplicate {{#{slug}}}: {named}")

    joint_explicit = set(defs)
    for rel, refs in file_refs:
        src_parent = Path(rel).parent
        for file_part, anchor, n in refs:
            if file_part is None:
                if anchor in joint_explicit or anchor in file_heading_slugs.get(rel, set()):
                    continue
                problems.append(f"{rel}:{n}: dangling {{#{anchor}}} — no heading definition")
            else:
                target_rel = None
                cand1 = os.path.normpath(src_parent / file_part).replace("\\", "/")
                cand2 = os.path.normpath(file_part).replace("\\", "/")
                cand3 = covered_by_basename.get(Path(file_part).name)
                if cand1 in file_defs:
                    target_rel = cand1
                elif cand2 in file_defs:
                    target_rel = cand2
                elif cand3 and cand3 in file_defs:
                    target_rel = cand3

                if target_rel is None:
                    problems.append(
                        f"{rel}:{n}: destination `{file_part}` is outside the covered journal set or does not exist"
                    )
                else:
                    valid_anchors = file_defs.get(target_rel, set()) | file_heading_slugs.get(
                        target_rel, set()
                    )
                    if anchor not in valid_anchors:
                        problems.append(
                            f"{rel}:{n}: dangling reference to `{file_part}#{anchor}` — "
                            f"no heading definition in {target_rel}"
                        )
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="lint_journal_order.py",
        description=(
            "Check the engineering journal's newest-first ordering (#659) "
            "and joint {#slug} uniqueness / dangling refs (#407)."
        ),
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
    loaded: list[tuple[str, str]] = []
    journal_args = args.journals or list(DEFAULT_JOURNALS)
    for rel in journal_args:
        path = args.root / rel
        if not path.is_file():
            # A repo without this journal is not a violation — the fleet has many plugins
            # and only some carry one.
            continue
        checked += 1
        text = path.read_text(encoding="utf-8")
        loaded.append((rel, text))
        problems.extend(check_structure(rel, text))
        if args.base_ref:
            problems.extend(check_new_entries(rel, text, args.base_ref, args.root))

    # The anchor check is inherently joint, so its file set is fixed rather than derived
    # from the CLI arguments: linting one journal on its own must not turn every honest
    # citation of a slug defined in another journal into a dangling reference.
    anchor_files = list(loaded)
    loaded_rels = {rel for rel, _ in anchor_files}
    for rel in (*DEFAULT_JOURNALS, *ANCHOR_EXTRA):
        if rel in loaded_rels:
            continue
        path = args.root / rel
        if not path.is_file():
            continue
        checked += 1
        anchor_files.append((rel, path.read_text(encoding="utf-8")))
    problems.extend(check_anchors(anchor_files))

    for p in problems:
        print(p, file=sys.stderr)
    print(f"journal-order lint: {checked} file(s) checked, VIOLATIONS: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
