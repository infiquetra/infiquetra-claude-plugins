#!/usr/bin/env python3
"""Read-only GitHub PR/issue state — the canonical completion-truth primitive (U5).

The OutcomeOrchestrator's completion is **canonical on GitHub** (R10/R11/R27), not in the cache: a
code leaf is done when its **PR reads merged**, a non-code leaf when its **tracking sub-issue reads
closed**. This module is that read side — the merge/close *actions* are U6; here we only **read**
completion truth so the parent-owned barrier (``outcome_orchestrator``) can decide "done" in a way a
cache-less machine reproduces by reading GitHub.

Every read degrades safely: if ``gh`` is unavailable / rate-limited / the ref is unknown, the state is
``"unknown"`` — never a false ``"merged"``/``"closed"`` (R34). The barrier treats ``unknown`` as
not-yet-complete, so a GitHub outage can only DELAY an unlock, never fabricate one.

House pattern: pure functions over an injectable ``runner`` (so tests run offline with no real ``gh``),
no I/O at import.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404 — gh CLI only, fixed argv, no shell
import sys
from collections.abc import Callable
from typing import Any

# Canonical PR completion states. ``unknown`` is the safe degraded value (gh down / ref missing).
PR_STATES = ("merged", "closed", "open", "unknown")
ISSUE_STATES = ("closed", "open", "unknown")


def _run_gh(args: list[str], *, runner: Callable[..., Any] | None = None) -> tuple[int, str]:
    """Run a ``gh`` subcommand, returning ``(returncode, stdout)``; (1, "") on any failure.

    ``runner`` defaults to ``subprocess.run`` resolved at CALL time (not a bound default) so a test
    can monkeypatch ``outcome_github.subprocess.run``.
    """
    run = runner if runner is not None else subprocess.run
    try:
        result = run(  # nosec B603 — fixed argv, no shell
            ["gh", *args], capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    if getattr(result, "returncode", 1) != 0:
        return 1, ""
    return 0, (result.stdout or "").strip()


def pr_state(pr_ref: str, *, runner: Callable[..., Any] | None = None) -> str:
    """Canonical state of a PR: ``merged`` / ``closed`` / ``open`` / ``unknown``.

    ``merged`` requires a real merge (``mergedAt`` set), so a PR that is CLOSED-unmerged reads
    ``closed`` (a NEGATIVE terminal, R32), never ``merged``. Any read failure -> ``unknown``.
    """
    rc, out = _run_gh(["pr", "view", str(pr_ref), "--json", "state,mergedAt"], runner=runner)
    if rc != 0 or not out:
        return "unknown"
    try:
        data = json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return "unknown"
    if not isinstance(data, dict):
        return "unknown"
    if data.get("mergedAt"):
        return "merged"
    state = str(data.get("state", "")).upper()
    if state == "MERGED":  # defensive — gh may set state=MERGED with mergedAt
        return "merged"
    if state == "CLOSED":
        return "closed"
    if state == "OPEN":
        return "open"
    return "unknown"


def issue_state(issue_ref: str, *, runner: Callable[..., Any] | None = None) -> str:
    """Canonical state of an issue: ``closed`` / ``open`` / ``unknown`` (any read failure -> unknown)."""
    rc, out = _run_gh(["issue", "view", str(issue_ref), "--json", "state"], runner=runner)
    if rc != 0 or not out:
        return "unknown"
    try:
        data = json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return "unknown"
    if not isinstance(data, dict):
        return "unknown"
    state = str(data.get("state", "")).upper()
    return {"CLOSED": "closed", "OPEN": "open"}.get(state, "unknown")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Read canonical GitHub PR/issue completion state.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_pr = sub.add_parser("pr-state", help="print a PR's canonical state")
    p_pr.add_argument("ref")
    p_issue = sub.add_parser("issue-state", help="print an issue's canonical state")
    p_issue.add_argument("ref")

    args = parser.parse_args(argv)
    if args.command == "pr-state":
        print(json.dumps({"ref": args.ref, "state": pr_state(args.ref)}))
    elif args.command == "issue-state":
        print(json.dumps({"ref": args.ref, "state": issue_state(args.ref)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
