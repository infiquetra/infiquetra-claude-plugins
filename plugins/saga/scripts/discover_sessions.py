#!/usr/bin/env python3
"""Discover recent Claude Code session JSONL files for a repo (Tier-2 fallback).

This is the discovery half of the ``/resume`` heavy-forensic Tier-2 path: a
slim, Claude-only port of CE ``ce-sessions``' ``discover-sessions.sh``. It is
used ONLY when there is no saga and no resolvable issue to anchor a deep
reconstruction on, so the engine falls back to mining prior local sessions.

Usage:
  python3 discover_sessions.py --repo <repo-folder> --days <N> \\
      [--projects-root <path>] [--exclude <session-id>]

It globs ``~/.claude/projects/*<repo>*/*.jsonl`` within an mtime window, drops
``--exclude``\\d session ids, RECENCY-ranks newest-first, and CAPS at 5.

Output is ``json.dumps`` of ``{"candidates": [{"path", "session_id", "mtime"}],
"count": N}`` — PATHS plus small metadata ONLY. It NEVER reads or emits file
bodies (session files can be multiple MB; bodies stay out of orchestrator
context). The extractor (``extract_session_skeleton.py``) is the only thing that
reads a body, and it does so file-mediated.

MVP = recency ranking only. Keyword / branch relevance ranking (CE's
``extract-metadata.py``) is deliberately deferred — see QUEUED.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import TypedDict

MAX_CANDIDATES = 5


class Candidate(TypedDict):
    """A discovered session: PATH plus small metadata only, never a file body."""

    path: str
    session_id: str
    mtime: float


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Repo folder name to match (substring)")
    parser.add_argument("--days", type=int, required=True, help="mtime window in days")
    parser.add_argument(
        "--projects-root",
        default=str(Path.home() / ".claude" / "projects"),
        help="Override the Claude projects root (default ~/.claude/projects); for testing",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Session id or basename to drop (repeatable or comma-separated); e.g. the current session",
    )
    return parser.parse_args(argv)


def _excluded_ids(raw: list[str]) -> set[str]:
    """Normalize ``--exclude`` values (repeatable + comma-separated) to bare session ids."""
    ids: set[str] = set()
    for item in raw:
        for part in item.split(","):
            part = part.strip()
            if part:
                # Accept either a bare id or a *.jsonl basename/path.
                ids.add(Path(part).name.removesuffix(".jsonl"))
    return ids


def discover(projects_root: Path, repo: str, days: int, exclude: set[str]) -> list[Candidate]:
    """Return recency-ranked session candidates (newest first), capped at 5."""
    if not projects_root.is_dir():
        return []

    cutoff = time.time() - days * 86400
    candidates: list[Candidate] = []
    for project_dir in projects_root.glob(f"*{repo}*"):
        if not project_dir.is_dir():
            continue
        for jsonl in project_dir.glob("*.jsonl"):
            try:
                mtime = jsonl.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                continue
            session_id = jsonl.stem
            if session_id in exclude:
                continue
            candidates.append({"path": str(jsonl), "session_id": session_id, "mtime": mtime})

    # RECENCY rank only (MVP): newest mtime first, then cap.
    candidates.sort(key=lambda c: c["mtime"], reverse=True)
    return candidates[:MAX_CANDIDATES]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidates = discover(
        Path(args.projects_root).expanduser(),
        args.repo,
        args.days,
        _excluded_ids(args.exclude),
    )
    print(json.dumps({"candidates": candidates, "count": len(candidates)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
