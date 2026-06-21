#!/usr/bin/env python3
"""
Stale-main-after-squash guard (this-repo-local, R18).

After a squash-merge lands on ``origin/main``, local ``main`` is silently
behind until explicitly fast-forwarded.  This guard detects that state and
emits a loud warning before any build agent reads the stale tree — a failure
mode that cost two builds here (#shipped-on-origin-not-in-stale-local-tree).

Behaviour
---------
1. ``git fetch origin`` (with a short timeout — network errors degrade quietly).
2. Count how many commits local ``main`` is behind ``origin/main``.
3. If ``count == 0``: silent (exits 0).
4. If ``count > 0`` AND the working tree is clean (no uncommitted changes):
   auto-fast-forward ``main`` and print one confirmation line.
5. If ``count > 0`` AND there are uncommitted changes or we are on a non-main
   branch: print a loud one-line warning and exit 0 (non-blocking — the guard
   informs, it does not halt).

Worktree safety
---------------
In a bg-worktree session ``git rev-parse --abbrev-ref HEAD`` returns the
worktree branch, not ``main``.  The guard detects this and omits the
auto-fast-forward (it would be wrong to mutate ``main`` from inside a
worktree).  The stale-behind warning is still emitted so the operator knows
the repo state.

This-repo-local
---------------
The guard is scoped to this repo.  It does not assume any cross-repo idiom.
Do not run it unconditionally in CI or other repos; install it as a
``SessionStart`` hook (or call it manually after a squash-merge) via
``hooks/hooks.json`` under a repo-path guard.

Exit codes
----------
0   Always (guard is non-blocking).
"""

from __future__ import annotations

import subprocess
import sys

_MAIN_BRANCH = "main"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _run(args: list[str], *, timeout: int = 15) -> tuple[int, str, str]:
    """Run a subprocess; return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "timed out"
    except FileNotFoundError:
        return 1, "", f"{args[0]!r} not found"
    except Exception as exc:
        return 1, "", str(exc)


def _fetch_origin() -> bool:
    """
    Run ``git fetch origin``.

    Returns True on success, False on any error (network, not-a-repo, etc.).
    Failures are swallowed so the guard degrades quietly.
    """
    rc, _, _ = _run(["git", "fetch", "origin"], timeout=20)
    return rc == 0


def _commits_behind() -> int | None:
    """
    Return how many commits local ``main`` is behind ``origin/main``.

    Returns None if the comparison cannot be made (no remote tracking branch,
    not a git repo, etc.).
    """
    rc, stdout, _ = _run(["git", "rev-list", "--count", f"{_MAIN_BRANCH}..origin/{_MAIN_BRANCH}"])
    if rc != 0:
        return None
    try:
        return int(stdout)
    except ValueError:
        return None


def _current_branch() -> str | None:
    """Return the currently checked-out branch, or None on detached HEAD / error."""
    rc, stdout, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if rc != 0:
        return None
    return stdout if stdout != "HEAD" else None  # 'HEAD' = detached


def _is_worktree() -> bool:
    """
    Return True if we are running inside a git worktree (not the main tree).

    Compares the common git dir with the git dir — in a worktree they differ.
    """
    rc_gitdir, gitdir, _ = _run(["git", "rev-parse", "--git-dir"])
    rc_common, common, _ = _run(["git", "rev-parse", "--git-common-dir"])
    if rc_gitdir != 0 or rc_common != 0:
        return False
    # In the main worktree, both paths resolve to the same directory.
    # In a linked worktree, --git-dir returns the per-worktree dir
    # (e.g. .git/worktrees/<name>) while --git-common-dir returns .git.
    return gitdir != common


def _working_tree_is_clean() -> bool:
    """Return True if there are no uncommitted changes (staged or unstaged)."""
    rc, stdout, _ = _run(["git", "status", "--porcelain"])
    if rc != 0:
        return False  # Treat unknown state as dirty (conservative)
    return stdout == ""


def _fast_forward_main() -> bool:
    """
    Fast-forward local ``main`` to ``origin/main``.

    Returns True on success.
    """
    rc, _, _ = _run(["git", "fetch", "origin", f"{_MAIN_BRANCH}:{_MAIN_BRANCH}"])
    return rc == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_guard(*, _fetch: bool = True) -> int:
    """
    Execute the stale-main guard.  Returns 0 always.

    Extracted from ``main()`` for testability (``_fetch=False`` skips the
    network call in unit tests).
    """
    if _fetch:
        # Degrade quietly on network failure — the count check below will use
        # whatever FETCH_HEAD git already has.
        _fetch_origin()

    behind = _commits_behind()

    if behind is None:
        # Cannot compare (no remote branch, not a repo, etc.) — stay silent.
        return 0

    if behind == 0:
        # Up to date — silent.
        return 0

    # Local main is stale.
    in_worktree = _is_worktree()
    current = _current_branch()
    on_main = current == _MAIN_BRANCH

    if in_worktree:
        # Cannot safely fast-forward main from inside a worktree.
        print(
            f"[stale-main-guard] WARNING: local '{_MAIN_BRANCH}' is {behind} commit(s) "
            f"behind origin/{_MAIN_BRANCH}. "
            f"You are in a worktree (branch: {current!r}). "
            f"Fast-forward manually: git fetch origin {_MAIN_BRANCH}:{_MAIN_BRANCH}",
            file=sys.stderr,
        )
        return 0

    if not on_main:
        # Not on main — warn but do not attempt a fast-forward.
        print(
            f"[stale-main-guard] WARNING: local '{_MAIN_BRANCH}' is {behind} commit(s) "
            f"behind origin/{_MAIN_BRANCH}. "
            f"You are on branch {current!r}. "
            f"Fast-forward when ready: git fetch origin {_MAIN_BRANCH}:{_MAIN_BRANCH}",
            file=sys.stderr,
        )
        return 0

    # On main — try auto-fast-forward if the tree is clean.
    if _working_tree_is_clean():
        if _fast_forward_main():
            print(
                f"[stale-main-guard] Auto-fast-forwarded '{_MAIN_BRANCH}' by {behind} "
                f"commit(s) to match origin/{_MAIN_BRANCH}.",
                file=sys.stderr,
            )
        else:
            print(
                f"[stale-main-guard] WARNING: local '{_MAIN_BRANCH}' is {behind} "
                f"commit(s) behind origin/{_MAIN_BRANCH} and auto-fast-forward failed. "
                f"Run: git fetch origin {_MAIN_BRANCH}:{_MAIN_BRANCH}",
                file=sys.stderr,
            )
    else:
        print(
            f"[stale-main-guard] WARNING: local '{_MAIN_BRANCH}' is {behind} commit(s) "
            f"behind origin/{_MAIN_BRANCH}. Working tree has uncommitted changes — "
            f"skipping auto-fast-forward. Run when ready: "
            f"git fetch origin {_MAIN_BRANCH}:{_MAIN_BRANCH}",
            file=sys.stderr,
        )

    return 0


def main() -> int:
    return run_guard()


if __name__ == "__main__":
    sys.exit(main())
