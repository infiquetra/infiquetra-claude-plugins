#!/usr/bin/env python3
"""
SHA-stamp stager (this-repo-local, R18).

After a squash-merge, reads the real squash SHA from ``gh pr view --json
mergeCommit``, finds every placeholder line in the repo's journal that matches
a configurable marker, and **stages** the substitution as a reviewable diff.
It never blind-applies: the operator sees the diff and confirms before commit.

Usage
-----
::

    python3 tools/sha_stamp_stager.py --pr 123
    python3 tools/sha_stamp_stager.py --pr 123 --placeholder SHA-TODO
    python3 tools/sha_stamp_stager.py --pr 123 --dry-run

Options
-------
--pr            GitHub PR number whose squash SHA to look up. Required.
--placeholder   String that marks SHA placeholders in journal files.
                Defaults to ``PENDING_SHA``.
--search-root   Directory tree to search for placeholder lines.
                Defaults to ``docs/engineering-journal``.
--dry-run       Print the substitution diff but do NOT stage any files.

Exit codes
----------
0   Substitution staged (or nothing to do).
1   Error (gh unavailable, PR not merged, etc.).
2   Conflicts or unexpected state.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Git / gh helpers
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    """Return the root of the current git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _die("Not inside a git repository.")
    return Path(result.stdout.strip())


def _squash_sha_from_pr(pr_number: int) -> str:
    """
    Return the squash commit SHA for a merged PR via ``gh pr view``.

    Exits 1 if the PR is not yet merged or gh is unavailable.
    """
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", "mergeCommit,state"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _die(
            f"gh pr view failed for PR #{pr_number}:\n{result.stderr.strip()}\n"
            "Make sure gh is installed and authenticated."
        )

    data = json.loads(result.stdout)
    state: str = data.get("state", "")
    merge_commit: dict | None = data.get("mergeCommit")

    if state != "MERGED":
        _die(
            f"PR #{pr_number} is not merged (state={state!r}). "
            "The SHA-stamp stager only applies to squash-merged PRs."
        )

    if not merge_commit or not merge_commit.get("oid"):
        _die(
            f"PR #{pr_number} is merged but has no mergeCommit.oid in the API response. "
            "This can happen for very old PRs or PRs merged without a squash."
        )

    return merge_commit["oid"]


# ---------------------------------------------------------------------------
# Placeholder scanning
# ---------------------------------------------------------------------------


def _find_placeholder_files(search_root: Path, placeholder: str) -> list[Path]:
    """
    Return every file under *search_root* that contains *placeholder*.

    Searches recursively, follows symlinks, skips binary files.
    """
    matches: list[Path] = []
    for path in sorted(search_root.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            # Binary or unreadable — skip.
            continue
        if placeholder in text:
            matches.append(path)
    return matches


def _build_diff(path: Path, placeholder: str, sha: str) -> str:
    """Return a human-readable unified-diff string showing the substitution."""
    original = path.read_text(encoding="utf-8")
    updated = original.replace(placeholder, sha)

    # Build a minimal --- / +++ diff.
    orig_lines = original.splitlines(keepends=True)
    upd_lines = updated.splitlines(keepends=True)

    import difflib

    diff = list(
        difflib.unified_diff(
            orig_lines,
            upd_lines,
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
    )
    return "".join(diff)


def _apply_substitution(path: Path, placeholder: str, sha: str) -> None:
    """Replace all occurrences of *placeholder* with *sha* in *path*."""
    original = path.read_text(encoding="utf-8")
    updated = original.replace(placeholder, sha)
    path.write_text(updated, encoding="utf-8")


def _stage_file(path: Path) -> None:
    """Stage *path* via ``git add``."""
    result = subprocess.run(
        ["git", "add", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _die(f"git add failed for {path}:\n{result.stderr.strip()}")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _die(msg: str, code: int = 1) -> None:
    print(f"[sha-stamp-stager] ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage SHA-stamp substitutions for squash-merged PRs (this-repo-local)."
    )
    parser.add_argument("--pr", type=int, required=True, help="Merged PR number.")
    parser.add_argument(
        "--placeholder",
        default="PENDING_SHA",
        help="Placeholder string to replace (default: PENDING_SHA).",
    )
    parser.add_argument(
        "--search-root",
        default="docs/engineering-journal",
        help="Directory to search for placeholder lines (default: docs/engineering-journal).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the diff but do not stage any files.",
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    search_root = repo_root / args.search_root

    if not search_root.exists():
        _die(
            f"Search root '{search_root}' does not exist. "
            "Run from inside the repo or pass --search-root."
        )

    # Look up the squash SHA first — fail fast if the PR isn't merged.
    sha = _squash_sha_from_pr(args.pr)
    short_sha = sha[:7]
    print(f"[sha-stamp-stager] PR #{args.pr} squash SHA: {sha} (short: {short_sha})")

    # Find files with the placeholder.
    placeholder_files = _find_placeholder_files(search_root, args.placeholder)
    if not placeholder_files:
        print(
            f"[sha-stamp-stager] No placeholder '{args.placeholder}' found under "
            f"'{search_root}'. Nothing to stage."
        )
        return 0

    print(
        f"[sha-stamp-stager] Found {len(placeholder_files)} file(s) with "
        f"placeholder '{args.placeholder}':"
    )
    for p in placeholder_files:
        print(f"  {p.relative_to(repo_root)}")

    print()

    # Show the diff for each file.
    for path in placeholder_files:
        diff = _build_diff(path, args.placeholder, sha)
        print(f"--- diff: {path.relative_to(repo_root)} ---")
        print(diff)

    if args.dry_run:
        print("[sha-stamp-stager] --dry-run: no files staged.")
        return 0

    # Apply + stage each file.
    staged: list[Path] = []
    for path in placeholder_files:
        _apply_substitution(path, args.placeholder, sha)
        _stage_file(path)
        staged.append(path)
        print(f"[sha-stamp-stager] Staged: {path.relative_to(repo_root)}")

    print()
    print(
        f"[sha-stamp-stager] {len(staged)} file(s) staged. "
        "Review the diff above, then commit with:\n"
        f"  git commit -m 'chore(journal): fill squash SHA for PR #{args.pr} ({short_sha})'"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
