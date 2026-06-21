#!/usr/bin/env python3
"""
SessionStart hook: surface the stale-main guard as session-start context.

After a squash-merge lands on ``origin/main``, local ``main`` is silently
behind until explicitly fast-forwarded — a failure mode that has cost builds
here (#shipped-on-origin-not-in-stale-local-tree). This hook runs the repo's
own ``tools/stale_main_guard.py`` at session start and injects its output as
SessionStart ``additionalContext`` so the operator (and any build agent) sees
the stale-state warning before reading the tree.

Repo-presence guard (the safety mechanism)
------------------------------------------
The saga plugin is DISTRIBUTED — it may be installed in any repo. This hook
must be INERT everywhere except this repo (or a fork of it). The signal is the
PRESENCE of ``tools/stale_main_guard.py`` at the CWD repo root, NOT a hardcoded
repo name. Resolution:
  1. Resolve the repo root via ``git rev-parse --show-toplevel``.
  2. If that fails (not a git repo) → exit 0 silently.
  3. If ``<root>/tools/stale_main_guard.py`` does NOT exist → exit 0 silently
     (no git fetch, no subprocess — fully inert).
  4. Only when the guard tool exists do we invoke it (the repo's OWN copy, not
     ``${CLAUDE_PLUGIN_ROOT}``'s — the guard is repo-local tooling).

Output
------
When the guard prints output, emit the official SessionStart JSON shape:
  {"hookSpecificOutput": {"hookEventName": "SessionStart",
                          "additionalContext": "<guard output>"}}
When the guard is silent, print nothing.

Properties (all by design):
  - NON-blocking: always exits 0 (SessionStart cannot block anyway).
  - INERT outside this repo: the repo-presence guard short-circuits.
  - QUIET on error: any subprocess error/timeout degrades to no output.

Exit codes:
  0 — always.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# The repo-local guard tool, relative to the repo root. Its presence is the
# signal that this hook should run (this repo or a fork of it).
_GUARD_REL = Path("tools") / "stale_main_guard.py"


def _read_cwd_from_stdin() -> str | None:
    """
    Read the SessionStart hook JSON from stdin and return its ``cwd`` field.

    Tolerates empty/malformed stdin by returning None (caller falls back to the
    process CWD).
    """
    try:
        raw = sys.stdin.read()
    except Exception:
        return None
    if not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    cwd = payload.get("cwd")
    return cwd if isinstance(cwd, str) and cwd else None


def _repo_root(cwd: str | None) -> Path | None:
    """Return the git repository root for ``cwd``, or None if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    root = result.stdout.strip()
    return Path(root) if root else None


def _run_guard(guard_path: Path, cwd: str | None) -> str:
    """
    Run the repo-local stale-main guard and return its combined output.

    The guard prints its warning/confirmation to stderr (and exits 0 always),
    so we capture both streams. Returns '' on any error/timeout.
    """
    try:
        result = subprocess.run(
            [sys.executable, str(guard_path)],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30,
        )
    except Exception:
        return ""
    parts = [part for part in (result.stdout.strip(), result.stderr.strip()) if part]
    return "\n".join(parts)


def main() -> None:
    cwd = _read_cwd_from_stdin()

    root = _repo_root(cwd)
    if root is None:
        # Not a git repo — stay inert.
        sys.exit(0)

    guard_path = root / _GUARD_REL
    if not guard_path.is_file():
        # The saga plugin is installed somewhere that isn't this repo (or its
        # fork). Do NOT run git fetch or anything — stay fully inert.
        sys.exit(0)

    output = _run_guard(guard_path, cwd)
    if not output:
        # Guard was silent (up to date, or it degraded quietly) — print nothing.
        sys.exit(0)

    # Surface the guard's output as SessionStart context.
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": output,
                }
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
