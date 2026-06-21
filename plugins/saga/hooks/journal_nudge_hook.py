#!/usr/bin/env python3
"""
PostToolUse hook: nudge when a feat/fix commit omits a journal entry.

Fires after a Bash tool call that issues a `git commit`.  When the commit
message starts with `feat` or `fix` and the committed diff touches code files
but includes NO `docs/engineering-journal/` path, prints a one-line nudge to
stderr.

Properties (all by design):
  - NON-blocking: always exits 0.
  - NON-writing: never creates or edits journal files.
  - Cross-repo-safe: degrades quietly when the journal dir is absent or git
    is unavailable.

Exit codes:
  0 — always (nudge or not, pass or error).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Commit message prefixes that warrant a journal nudge.
_FEAT_FIX_RE = re.compile(r"^(feat|fix)\b", re.IGNORECASE)

# Extensions considered "code" (not pure docs/config/chore).
_CODE_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".sh",
        ".bash",
        ".go",
        ".rs",
        ".rb",
        ".java",
        ".kt",
        ".swift",
        ".c",
        ".cpp",
        ".h",
        ".cs",
        ".php",
        ".r",
        ".sql",
    }
)

# Prefix that marks a journal entry in the committed diff.
_JOURNAL_PREFIX = "docs/engineering-journal/"


def _is_git_commit_command(command: str) -> bool:
    """Return True if the shell command performs a `git commit`."""
    # Match plain `git commit` and `git -C <dir> commit` variants.
    return bool(re.search(r"\bgit\b.*\bcommit\b", command))


def _extract_commit_message(command: str) -> str:
    """
    Extract the commit message from a git commit command string.

    Handles `-m "msg"`, `-m 'msg'`, and heredoc-via-$() forms.
    Returns '' if not found.
    """
    # -m "..." or -m '...' (greedy across newlines)
    m = re.search(r"-m\s+(['\"])(.*?)\1", command, re.DOTALL)
    if m:
        return m.group(2)
    # -m msg (no quotes, single token)
    m2 = re.search(r"-m\s+(\S+)", command)
    if m2:
        return m2.group(1)
    return ""


def _parse_git_dash_c(command: str) -> str | None:
    """Return the path from `git -C <path>` if present, else None."""
    m = re.search(r"\bgit\s+-C\s+(['\"]?)([^'\" ]+)\1", command)
    if m:
        return m.group(2)
    return None


def _git_show_files(cwd: str | None) -> list[str]:
    """
    Return the list of file paths touched by HEAD (the just-committed commit).

    Returns [] on any error (git unavailable, not a repo, etc.).
    """
    try:
        result = subprocess.run(
            ["git", "show", "--name-only", "--format=", "HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        # --format= suppresses the commit header; output is one filename per line.
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def _journal_dir_exists(cwd: str | None) -> bool:
    """Return True if docs/engineering-journal/ exists in the repo root."""
    base = Path(cwd) if cwd else Path.cwd()
    # Try to find the repo root via git rev-parse for cross-repo accuracy.
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=5,
        )
        if result.returncode == 0:
            base = Path(result.stdout.strip())
    except Exception:
        pass

    return (base / "docs" / "engineering-journal").is_dir()


def _has_code_files(files: list[str]) -> bool:
    """Return True if at least one committed file has a code extension."""
    return any(Path(f).suffix.lower() in _CODE_EXTENSIONS for f in files)


def _has_journal_entry(files: list[str]) -> bool:
    """Return True if at least one committed file is under docs/engineering-journal/."""
    return any(f.startswith(_JOURNAL_PREFIX) for f in files)


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except Exception:
        # Malformed envelope — pass through silently.
        sys.exit(0)

    tool_name: str = payload.get("tool_name", "")
    tool_input: dict = payload.get("tool_input", {})

    if tool_name != "Bash":
        sys.exit(0)

    command: str = tool_input.get("command", "")

    if not _is_git_commit_command(command):
        sys.exit(0)

    # Extract the commit message type.
    msg = _extract_commit_message(command)
    if not _FEAT_FIX_RE.match(msg):
        # docs-only, chore, refactor, etc. — stay silent.
        sys.exit(0)

    # Determine the working directory from `git -C <path>` if present.
    cwd: str | None = _parse_git_dash_c(command)

    # Cross-repo safety: if the journal dir doesn't exist, degrade silently.
    if not _journal_dir_exists(cwd):
        sys.exit(0)

    # Inspect the committed files.
    files = _git_show_files(cwd)
    if not files:
        # Cannot determine committed files — be conservative, stay silent.
        sys.exit(0)

    if not _has_code_files(files):
        # Docs-only or non-code commit — no nudge.
        sys.exit(0)

    if _has_journal_entry(files):
        # Journal entry present — all good, no nudge.
        sys.exit(0)

    # Nudge: non-blocking, stderr only.
    print(
        "[saga/journal-nudge] Heads up: this feat/fix commit touches code but "
        "includes no docs/engineering-journal/ entry. "
        "Add a LEARNINGS.md or DECISIONS.md entry if the change earned one "
        "(non-obvious fix, pattern decision, tooling choice).",
        file=sys.stderr,
    )

    # Always exit 0 — never block.
    sys.exit(0)


if __name__ == "__main__":
    main()
