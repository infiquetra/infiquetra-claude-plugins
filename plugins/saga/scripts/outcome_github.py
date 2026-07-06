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
import re
import subprocess  # nosec B404 — gh CLI only, fixed argv, no shell
import sys
from collections.abc import Callable
from typing import Any

# Canonical PR completion states. ``unknown`` is the safe degraded value (gh down / ref missing).
PR_STATES = ("merged", "closed", "open", "unknown")
ISSUE_STATES = ("closed", "open", "unknown")


def _run_gh(args: list[str], *, runner: Callable[..., Any] | None = None) -> tuple[int, str, str]:
    """Run a ``gh`` subcommand, returning ``(returncode, stdout, stderr)``; (1, "", "<err>") on failure.

    ``runner`` defaults to ``subprocess.run`` resolved at CALL time (not a bound default) so a test
    can monkeypatch ``outcome_github.subprocess.run``. ``stderr`` is returned so a definite HTTP 404
    (a deleted ref) can be told apart from a transient error (which must degrade safe, R34).
    """
    run = runner if runner is not None else subprocess.run
    try:
        result = run(  # nosec B603 — fixed argv, no shell
            ["gh", *args], capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "", str(exc)
    rc = getattr(result, "returncode", 1)
    stderr = (getattr(result, "stderr", "") or "").strip()
    if rc != 0:
        return 1, "", stderr
    return 0, (result.stdout or "").strip(), stderr


# Ref normalization (#495 U1) — make every stored ref format gh-consumable.
# Decompose/ingestion stores refs as ``owner/repo#N``, but ``gh issue view "owner/repo#N"`` errors
# (invalid issue format) and ``gh pr view "owner/repo#N"`` misreads it as a branch. A full URL and a
# bare number both work, so normalize ``owner/repo#N`` -> a full URL and pass the other two through.
_OWNER_REPO_NUM = re.compile(r"^(?P<owner>[^/\s#]+)/(?P<repo>[^/\s#]+)#(?P<number>\d+)$")
_GITHUB_URL = re.compile(
    r"^https?://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)/(?:pull|issues)/(?P<number>\d+)"
    r"(?:[/?#].*)?$"
)


def _parse_ref(ref: str) -> tuple[str, str, str] | None:
    """``(owner, repo, number)`` from an ``owner/repo#N`` ref or a full github ``pull``/``issues`` URL.

    Returns ``None`` for a bare number or anything unparseable, so a caller that needs owner/repo (the
    REST events path in ``_closed_by``) degrades safely rather than fabricating one.
    """
    s = str(ref).strip()
    for rx in (_OWNER_REPO_NUM, _GITHUB_URL):
        m = rx.match(s)
        if m:
            return m["owner"], m["repo"], m["number"]
    return None


def _gh_ref(ref: str, kind: str) -> str:
    """A gh-consumable token for ``ref``. ``owner/repo#N`` -> a full URL (cwd-independent); a full URL or
    a bare number passes through unchanged. ``kind`` is the URL path segment: ``pull`` (PRs), ``issues``.
    """
    s = str(ref).strip()
    if s.lower().startswith(("http://", "https://")):
        return s  # already a full URL — pass through byte-for-byte
    parsed = _parse_ref(s)
    if parsed is None:
        return s  # bare number or unparseable — hand to gh as-is (resolved in the repo cwd)
    owner, repo, number = parsed
    return f"https://github.com/{owner}/{repo}/{kind}/{number}"


def pr_state(pr_ref: str, *, runner: Callable[..., Any] | None = None) -> str:
    """Canonical state of a PR: ``merged`` / ``closed`` / ``open`` / ``unknown``.

    ``merged`` requires a real merge (``mergedAt`` set), so a PR that is CLOSED-unmerged reads
    ``closed`` (a NEGATIVE terminal, R32), never ``merged``. Any read failure -> ``unknown``.
    """
    rc, out, _err = _run_gh(
        ["pr", "view", _gh_ref(pr_ref, "pull"), "--json", "state,mergedAt"], runner=runner
    )
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
    rc, out, _err = _run_gh(
        ["issue", "view", _gh_ref(issue_ref, "issues"), "--json", "state"], runner=runner
    )
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


def board_status(issue_ref: str, *, project: str, runner: Callable[..., Any] | None = None) -> str:
    """Live board Status option name for ``issue_ref`` on the ``project`` board; "" on any failure.

    Reads ``gh issue view <ref> --json projectItems`` (probed live 2026-07-03: each item carries
    ``{"status": {"name": ...}, "title": <project title>}``) and returns the Status name of the
    project whose ``title`` matches ``project`` case-insensitively ("Operations" ↔ "operations").
    Every failure — gh down, malformed JSON, no matching project item, a null/absent status —
    degrades to "" (the reconcile caller treats "" as unreadable, never as drift), mirroring
    ``issue_state``'s never-raise contract. This is the board-Status half of the saga-owned field
    class (#295 U1); it adds no GraphQL and no mission-control surface.
    """
    rc, out, _err = _run_gh(
        ["issue", "view", _gh_ref(issue_ref, "issues"), "--json", "projectItems"], runner=runner
    )
    if rc != 0 or not out:
        return ""
    try:
        data = json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    items = data.get("projectItems")
    if not isinstance(items, list):
        return ""
    want = project.strip().lower()
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("title", "")).strip().lower() != want:
            continue
        status = item.get("status")
        if isinstance(status, dict):
            name = status.get("name")
            if isinstance(name, str) and name:
                return name
        return ""  # matched the project but its Status is unset/null → unreadable
    return ""


# stateReason values gh reports (upper-cased on the wire), normalized to lowercase snake_case.
_STATE_REASONS = {"COMPLETED": "completed", "NOT_PLANNED": "not_planned", "REOPENED": "reopened"}


def _closed_by(issue_ref: str, *, runner: Callable[..., Any] | None = None) -> str:
    """Best-effort login of whoever last closed ``issue_ref``; "" when undiscoverable.

    ``gh issue view`` exposes no close-actor field, so this rides the REST events endpoint, which
    needs an ``owner/repo`` — only an ``owner/repo#N`` ref yields one, so a bare or unqualified ref
    degrades to "". ``--paginate`` concatenates every event page into one array (an issue with >30
    events would otherwise drop the close), and the LAST ``closed`` event is selected AFTER the
    concatenation (never per-page). Any failure → "".
    """
    parsed = _parse_ref(issue_ref)
    if parsed is None:
        return ""  # a bare/unqualified ref yields no owner/repo — the REST events path needs one
    owner, repo, number = parsed
    path = f"repos/{owner}/{repo}/issues/{number}/events"
    rc, out, _err = _run_gh(["api", path, "--paginate"], runner=runner)
    if rc != 0 or not out:
        return ""
    try:
        events = json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(events, list):
        return ""
    login = ""
    for ev in events:
        if isinstance(ev, dict) and ev.get("event") == "closed":
            actor = ev.get("actor")
            if isinstance(actor, dict) and isinstance(actor.get("login"), str):
                login = actor["login"]
    return login


def issue_close_info(issue_ref: str, *, runner: Callable[..., Any] | None = None) -> dict[str, str]:
    """How an issue was closed: ``{"state", "state_reason", "closed_by"}`` — every field degrade-safe.

    ``state`` ∈ {open, closed, unknown}; ``state_reason`` ∈ {completed, not_planned, reopened,
    unknown}; ``closed_by`` is a best-effort login or "". Powers the reconcile close semantics
    (#295 KTD4): a contract-satisfying ``completed`` close is the harvester's sanctioned silent
    path, while a ``not_planned`` close — or an unreadable reason on a contract a close does not
    satisfy — is drift. ``issue_state`` is left untouched so the harvester barrier keeps its exact
    open/closed semantics.
    """
    rc, out, _err = _run_gh(
        ["issue", "view", _gh_ref(issue_ref, "issues"), "--json", "state,stateReason"],
        runner=runner,
    )
    state = "unknown"
    reason = "unknown"
    if rc == 0 and out:
        try:
            data = json.loads(out)
        except (json.JSONDecodeError, ValueError):
            data = None
        if isinstance(data, dict):
            state = {"CLOSED": "closed", "OPEN": "open"}.get(
                str(data.get("state", "")).upper(), "unknown"
            )
            reason = _STATE_REASONS.get(str(data.get("stateReason", "") or "").upper(), "unknown")
    closed_by = _closed_by(issue_ref, runner=runner) if state == "closed" else ""
    return {"state": state, "state_reason": reason, "closed_by": closed_by}


# ---------------------------------------------------------------------------
# Write side (U6) — base-SHA reads + the squash-merge action + branch existence.
# Every read still degrades to a SAFE value (empty SHA / "unknown" merge-state / branch-absent), so a
# gh outage can only DELAY or DEFER a merge, never perform a wrong one.
# ---------------------------------------------------------------------------

# Merge readiness as GitHub computes it. ``BEHIND`` = the PR base moved ahead (needs an update before
# merge, R12 base-freshness); ``DIRTY`` = a merge conflict; ``CLEAN``/``UNSTABLE`` = mergeable.
MERGE_STATES = ("clean", "behind", "blocked", "dirty", "unstable", "unknown")


def base_ref_oid(pr_ref: str, *, runner: Callable[..., Any] | None = None) -> str:
    """The SHA of the PR's base branch tip as GitHub sees it (``baseRefOid``); "" on any failure.

    Used as a **readability pre-check** by the merge queue (an empty value = gh degraded -> defer, R34)
    and as reference/telemetry. The authoritative stale-tree guard is GitHub itself, via the
    ``--match-head-commit`` CAS on ``gh pr merge`` — not a local compare of this value.
    """
    rc, out, _err = _run_gh(["pr", "view", str(pr_ref), "--json", "baseRefOid"], runner=runner)
    if rc != 0 or not out:
        return ""
    try:
        data = json.loads(out)
        return str(data.get("baseRefOid", "")) if isinstance(data, dict) else ""
    except (json.JSONDecodeError, ValueError):
        return ""


def head_ref_oid(pr_ref: str, *, runner: Callable[..., Any] | None = None) -> str:
    """The PR head commit SHA (``headRefOid``); "" on any failure. Used for the ``--match-head-commit``
    CAS so GitHub rejects a squash if the head moved since (a stale tree cannot be merged)."""
    rc, out, _err = _run_gh(["pr", "view", str(pr_ref), "--json", "headRefOid"], runner=runner)
    if rc != 0 or not out:
        return ""
    try:
        data = json.loads(out)
        return str(data.get("headRefOid", "")) if isinstance(data, dict) else ""
    except (json.JSONDecodeError, ValueError):
        return ""


def merge_state(pr_ref: str, *, runner: Callable[..., Any] | None = None) -> str:
    """GitHub's mergeStateStatus, lowercased to MERGE_STATES; "unknown" on any failure (R34)."""
    rc, out, _err = _run_gh(
        ["pr", "view", str(pr_ref), "--json", "mergeStateStatus"], runner=runner
    )
    if rc != 0 or not out:
        return "unknown"
    try:
        data = json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return "unknown"
    if not isinstance(data, dict):
        return "unknown"
    state = str(data.get("mergeStateStatus", "")).lower()
    return state if state in MERGE_STATES else "unknown"


def branch_exists(branch: str, *, runner: Callable[..., Any] | None = None) -> bool:
    """Whether a branch ref still exists on the remote (a deleted branch -> a negative terminal, R32).

    Only a **definite 404** reports the branch GONE (``False``); a transient gh failure degrades to
    **True** (present) so a flake never falsely rejects a live subplot (R34) — the deleted-branch
    terminal fires only when GitHub explicitly says the ref is absent.
    """
    rc, out, err = _run_gh(
        ["api", f"repos/{{owner}}/{{repo}}/git/refs/heads/{branch}", "--jq", ".ref"], runner=runner
    )
    if rc == 0:
        return bool(out)
    # Only a definite 404 reports the ref GONE (R32); a transient error degrades to present (R34).
    is_404 = "404" in err or "not found" in err.lower()
    return not is_404


def update_branch(pr_ref: str, *, runner: Callable[..., Any] | None = None) -> bool:
    """Update the PR branch with its base (the R12 rebase-then-reverify step). True iff it succeeded."""
    rc, _out, _err = _run_gh(["pr", "update-branch", str(pr_ref)], runner=runner)
    return rc == 0


def squash_merge(
    pr_ref: str, *, expected_head: str = "", runner: Callable[..., Any] | None = None
) -> str:
    """Server-side squash-merge the PR. Returns ``merged`` on success, else ``error``.

    **GitHub is the authoritative atomic guard** (not a local check): ``gh pr merge`` rejects a PR that
    is not mergeable — base moved (behind), a conflict, or required checks unmet — so a non-zero exit
    is NOT necessarily a conflict and is reported as ``error``. The caller re-classifies via
    ``merge_state`` (``dirty`` = a real conflict; ``behind`` = base moved; ``unknown`` = transient ->
    defer) and never fails a leaf permanently on a transient ``error`` (R34). When ``expected_head`` is
    given, ``--match-head-commit`` makes GitHub reject the merge if the PR head moved since (a CAS on
    the head), so a stale tree cannot be squashed.
    """
    args = ["pr", "merge", str(pr_ref), "--squash"]
    if expected_head:
        args += ["--match-head-commit", expected_head]
    rc, _out, _err = _run_gh(args, runner=runner)
    return "merged" if rc == 0 else "error"


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
