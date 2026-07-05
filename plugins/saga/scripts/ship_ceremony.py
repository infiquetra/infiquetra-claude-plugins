#!/usr/bin/env python3
"""ship_ceremony.py — one composable, resumable, guarded ship primitive (issue #345).

Replaces the raw, hand-typed ``commit -> PR -> merge -> checkout-main -> pull ->
branch-delete`` sequence ``/work`` used to drive inline with an explicit, ordered
transition table. The primitive is a stateless CLI (re-reads state each invocation,
mirroring ``saga.py`` / ``outcome_store.py``): every invocation resolves the current
saga, looks up the next unrun transition, executes it, and records the result — so
killing the process mid-ceremony and re-invoking simply continues rather than
restarting or duplicating a completed transition.

Two entry points share this one implementation (R4): ``/work``'s PR-ready flow calls
``run``/``start`` directly; a terminal operator installs a local git alias
(``install``) and then runs ``git ship``. Merge, PR-open, and review-request are never
auto-fired by this script on its own initiative — every mutating transition is invoked
only when the caller (``/work`` or the operator at the terminal) explicitly asks for
the next step; the primitive automates *sequencing and bookkeeping*, not
*authorization* (R5).

Reversibility tiers (KTD1) are declared locally as ``CeremonyTier`` rather than reusing
``reversibility_certificate.py`` — that module's own docstring scopes its ``OpKind``
allowlist to mission-control board/issue verbs and intentionally excludes merge,
deploy, and repo-level mutations (its R20). Ceremony state (KTD2) rides the governing
issue's existing work-thread saga tick via ``saga.py save --ceremony-transition
--ceremony-tier`` rather than a second store; no index is persisted; the transition's
position is always recomputed from ``TRANSITIONS`` so there is nothing to drift out of
sync with the name.

House testability pattern (mirrors ``outcome_store.py``): every function that shells
out takes a ``runner`` callable, defaulted to ``subprocess.run`` resolved at call time
(never bound as a default argument), so tests can monkeypatch ``ship_ceremony.subprocess.run``
or pass a fake runner directly.
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SAGA_PY = SCRIPT_DIR / "saga.py"


class ShipCeremonyError(Exception):
    """Base error for ship_ceremony.py — always caught at the CLI boundary and
    reported as a message, never an uncaught traceback."""


class AmbiguousSagaError(ShipCeremonyError):
    """More than one saga candidate matches the current branch; refuses to guess."""


class NoSagaError(ShipCeremonyError):
    """No saga candidate matches the current branch or the given issue-ref."""


class TransitionFailedError(ShipCeremonyError):
    """The underlying git/gh call for a transition failed; state was not advanced."""


# --------------------------------------------------------------------------- #
# Reversibility tiers (KTD1) — named distinctly from reversibility_certificate.Tier
# to avoid a symbol collision anywhere both modules are imported (e.g. tests).
# --------------------------------------------------------------------------- #


class CeremonyTier:
    """Ceremony-local reversibility tiers, mirroring reversibility_certificate.py's
    vocabulary shape (not its symbol names, and not its allowlist — see module
    docstring KTD1)."""

    REVERSIBLE = "reversible"
    ADDITIVE = "additive"
    ALWAYS_OPERATOR = "always_operator"


# Ordered transition table (R1). Position in this tuple IS the canonical index;
# ship_ceremony.py never persists an index, only the transition name, and always
# recomputes the index from this tuple on read (KTD2).
TRANSITIONS: tuple[str, ...] = (
    "commit",
    "open_pr",
    "request_review",
    "merge",
    "checkout_main",
    "pull",
    "branch_delete",
)

TRANSITION_TIERS: Mapping[str, str] = {
    "commit": CeremonyTier.REVERSIBLE,
    "open_pr": CeremonyTier.REVERSIBLE,
    "request_review": CeremonyTier.REVERSIBLE,
    "merge": CeremonyTier.ALWAYS_OPERATOR,
    "checkout_main": CeremonyTier.REVERSIBLE,
    "pull": CeremonyTier.REVERSIBLE,
    "branch_delete": CeremonyTier.ALWAYS_OPERATOR,
}


def next_transition(last_transition: str) -> str | None:
    """The transition that should run next, given the last one recorded.

    ``last_transition == ""`` (never started) means the next transition is
    ``TRANSITIONS[0]``. Returns ``None`` once every transition has run (the
    ceremony is complete) — callers must not re-run ``branch_delete``.
    """
    if last_transition == "":
        return TRANSITIONS[0]
    if last_transition not in TRANSITIONS:
        raise ShipCeremonyError(
            f"unrecognized ceremony_transition {last_transition!r} in saga state; "
            f"expected one of {TRANSITIONS} or empty"
        )
    index = TRANSITIONS.index(last_transition)
    if index + 1 >= len(TRANSITIONS):
        return None
    return TRANSITIONS[index + 1]


# --------------------------------------------------------------------------- #
# Subprocess helpers — runner injectable at every call site (never bound as a
# default argument, so a test monkeypatching ``ship_ceremony.subprocess.run``
# takes effect even when a caller didn't thread a runner through explicitly).
# --------------------------------------------------------------------------- #


def _run(
    cmd: Sequence[str],
    *,
    cwd: Path,
    runner: Callable[..., Any] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    run = runner if runner is not None else subprocess.run
    result = run(  # nosec B603 — fixed argv, no shell
        list(cmd),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if check and getattr(result, "returncode", 1) != 0:
        raise TransitionFailedError(
            f"{' '.join(cmd)} failed (exit {result.returncode}): "
            f"{(getattr(result, 'stderr', '') or '').strip()}"
        )
    return result


def _saga_cli(
    args: Sequence[str],
    *,
    repo_root: Path,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Invoke ``saga.py`` as a subprocess (the CLI is the contract, not the module —
    mirrors how other saga consumers shell out to it) and parse its JSON stdout."""
    result = _run(
        [sys.executable, str(SAGA_PY), *args],
        cwd=repo_root,
        runner=runner,
    )
    return json.loads(result.stdout)


# --------------------------------------------------------------------------- #
# Saga resolution — resolves by --issue-ref when given; otherwise filters
# ``saga.py scan``'s candidate list by the current branch. ``scan`` itself has no
# branch filter (verified against its CLI); the filtering is ship_ceremony.py's
# own responsibility.
# --------------------------------------------------------------------------- #


# Statuses a saga can never be a live ceremony target in — excluded from the by-branch
# candidate filter so terminal sagas left on a branch (esp. the pile frozen on ``main``) don't
# force a false ambiguous match. Mirrors saga.py's STATUSES terminal members.
_TERMINAL_STATUSES = frozenset({"done", "abandoned"})


def current_branch(repo_root: Path, *, runner: Callable[..., Any] | None = None) -> str:
    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, runner=runner)
    return result.stdout.strip()


def resolve_saga(
    *,
    repo_root: Path,
    issue_ref: str | None = None,
    saga_id: str | None = None,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Resolve the saga this ceremony run should act on.

    Precedence: an explicit ``saga_id`` wins, then ``issue_ref``, then a by-branch match.
    An explicit key is the ONLY thing that works across the whole ceremony for a task-kind
    saga: ``checkout_main`` moves you onto ``main`` for the ``pull``/``branch_delete``
    transitions, but the saga being shipped still records its feature branch, so a by-branch
    match on ``main`` can never find it — and instead collides with every other saga left on
    ``main``. ``/work``'s issue path passes ``issue_ref``; a task-kind ceremony must pass
    ``saga_id`` (e.g. ``task-<slug>``).

    The by-branch fallback (the terminal ``git ship`` path on the feature branch) ignores
    terminal (``done``/``abandoned``) sagas — they are never a live ceremony target and would
    otherwise pile up on a reused branch name and force an ambiguous match.
    """
    if saga_id is not None:
        return _saga_cli(["restore", "--saga-id", saga_id], repo_root=repo_root, runner=runner)
    if issue_ref is not None:
        derived = f"issue-{issue_ref.rsplit('#', 1)[-1]}"
        return _saga_cli(["restore", "--saga-id", derived], repo_root=repo_root, runner=runner)

    branch = current_branch(repo_root, runner=runner)
    scanned = _saga_cli(["scan"], repo_root=repo_root, runner=runner)
    candidates = [
        c
        for c in scanned.get("candidates", [])
        if c.get("branch") == branch and c.get("status") not in _TERMINAL_STATUSES
    ]
    if not candidates:
        raise NoSagaError(
            f"no live saga found for branch {branch!r}; pass --issue-ref or --saga-id explicitly "
            "(a task-kind ceremony must pass --saga-id once checkout_main moves off the work branch)"
        )
    if len(candidates) > 1:
        ids = ", ".join(c["saga_id"] for c in candidates)
        raise AmbiguousSagaError(
            f"multiple live sagas match branch {branch!r} ({ids}); pass --issue-ref or --saga-id "
            "explicitly rather than guessing"
        )
    return _saga_cli(
        ["restore", "--saga-id", candidates[0]["saga_id"]], repo_root=repo_root, runner=runner
    )


def _saga_short_id(saga: Mapping[str, Any]) -> str:
    """The bare id (``--id``) for ``saga.py save``, derived from the saga's own kind/id."""
    return str(saga["id"])


# --------------------------------------------------------------------------- #
# Transition runners — one function per TRANSITIONS entry. Each returns nothing on
# success and raises TransitionFailedError on failure; the caller (``run``) is
# responsible for not advancing recorded state past a failed transition.
# --------------------------------------------------------------------------- #


def _push_branch(repo_root: Path, *, runner: Callable[..., Any] | None) -> None:
    """Push the current branch to its ``origin`` tracking ref. Idempotent — a no-op
    ("Everything up-to-date") when the remote already matches local HEAD. Shared by
    ``_do_commit`` and ``_do_open_pr``'s existing-PR path so both emit the same push
    argv (issue #478)."""
    branch = current_branch(repo_root, runner=runner)
    _run(["git", "push", "-u", "origin", branch], cwd=repo_root, runner=runner)


def _do_commit(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    """Push the current branch. The scaffold commit itself already exists — from
    ``/work``'s Phase 1.4 mint (KTD4) or from the operator's own commits — this
    transition's job is making sure it is on the remote."""
    _push_branch(repo_root, runner=runner)


def _do_open_pr(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    """Open a PR, or — if the front-loaded ``start`` mode already opened a draft PR
    (R7) — flip that existing draft ready instead of opening a second one."""
    existing = saga.get("pr_refs") or []
    if existing:
        # Front-loaded path: ``start`` opened the draft and pre-recorded
        # ``ceremony_transition="commit"``, so ``_do_commit`` (the only other push
        # site) never runs. Push the commits accumulated since ``start`` BEFORE
        # flipping ready, so CI validates the current HEAD, not the ``start``-time
        # HEAD (issue #478).
        _push_branch(repo_root, runner=runner)
        pr_number = _pr_number(existing[-1])
        _run(["gh", "pr", "ready", pr_number], cwd=repo_root, runner=runner)
        return
    branch = current_branch(repo_root, runner=runner)
    body_lines: list[str] = []
    # Auto-close the tracked issue on merge via a ``Fixes #N`` line, so shipping never leaves a
    # fixed issue open — the manual close step is easy to forget (it was, on #477). Only added
    # when the saga names a real numeric issue (``owner/repo#N``); task-kind sagas have none.
    issue_ref = saga.get("issue_ref") or ""
    issue_num = issue_ref.rsplit("#", 1)[-1] if "#" in issue_ref else ""
    if issue_num.isdigit():
        body_lines.append(f"Fixes #{issue_num}")
    plan_path = saga.get("plan_path") or ""
    if plan_path:
        body_lines.append(f"Plan: {plan_path}")
    body = "\n\n".join(body_lines)
    result = _run(
        ["gh", "pr", "create", "--head", branch, "--fill", "--body", body],
        cwd=repo_root,
        runner=runner,
    )
    pr_number = result.stdout.strip().rsplit("/", 1)[-1]
    _saga_cli(
        [
            "save",
            "--kind",
            saga["kind"],
            "--id",
            _saga_short_id(saga),
            "--pr-refs",
            f"#{pr_number}",
        ],
        repo_root=repo_root,
        runner=runner,
    )


def _do_request_review(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    """Deliberate no-op (issue #477, dated 2026-07-04): this repository has exactly one
    human maintainer, who is also the sole author of every ceremony PR — there is no one
    else to request review from. The previous body shelled out to
    ``gh pr edit --add-reviewer @me``, which always failed (``@me`` is not a valid login
    for the ``requestReviewsByLogin`` mutation); resolving the real login instead would
    still be a self-review request. Revisit only if a second human maintainer joins."""


def _do_merge(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    pr_number = _current_pr_number(saga, repo_root=repo_root, runner=runner)
    _run(["gh", "pr", "merge", pr_number, "--squash"], cwd=repo_root, runner=runner)


def _do_checkout_main(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    _run(["git", "checkout", "main"], cwd=repo_root, runner=runner)


def _do_pull(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    _run(["git", "pull"], cwd=repo_root, runner=runner)


def _do_branch_delete(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    branch = saga.get("branch") or ""
    if not branch or branch == "main":
        raise TransitionFailedError(
            f"refusing to delete branch {branch!r}; saga's recorded branch looks wrong"
        )
    _run(["git", "branch", "-d", branch], cwd=repo_root, runner=runner)
    _run(["git", "push", "origin", "--delete", branch], cwd=repo_root, runner=runner, check=False)


_RUNNERS: Mapping[str, Callable[..., None]] = {
    "commit": _do_commit,
    "open_pr": _do_open_pr,
    "request_review": _do_request_review,
    "merge": _do_merge,
    "checkout_main": _do_checkout_main,
    "pull": _do_pull,
    "branch_delete": _do_branch_delete,
}


def _pr_number(pr_ref: str) -> str:
    """``pr_refs`` entries are stored as ``#123`` or a full URL; extract the number."""
    return pr_ref.rsplit("/", 1)[-1].lstrip("#")


def _current_pr_number(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> str:
    refs = saga.get("pr_refs") or []
    if not refs:
        raise TransitionFailedError("no pr_refs recorded on saga; open_pr must run first")
    return _pr_number(refs[-1])


# --------------------------------------------------------------------------- #
# CLI subcommands
# --------------------------------------------------------------------------- #


def run(
    *,
    repo_root: Path,
    issue_ref: str | None = None,
    saga_id: str | None = None,
    runner: Callable[..., Any] | None = None,
) -> str:
    """Execute exactly the next unrun transition and record it. Returns a
    human-readable status line; raises on ambiguity or transition failure."""
    saga = resolve_saga(repo_root=repo_root, issue_ref=issue_ref, saga_id=saga_id, runner=runner)
    upcoming = next_transition(saga.get("ceremony_transition", ""))
    if upcoming is None:
        return "already shipped — all ceremony transitions complete"

    _RUNNERS[upcoming](saga, repo_root=repo_root, runner=runner)

    _saga_cli(
        [
            "save",
            "--kind",
            saga["kind"],
            "--id",
            _saga_short_id(saga),
            "--ceremony-transition",
            upcoming,
            "--ceremony-tier",
            TRANSITION_TIERS[upcoming],
        ],
        repo_root=repo_root,
        runner=runner,
    )
    return f"ran transition {upcoming!r} (tier={TRANSITION_TIERS[upcoming]})"


def start(
    *,
    repo_root: Path,
    issue_ref: str,
    runner: Callable[..., Any] | None = None,
) -> str:
    """Front-loaded mode (R7/KTD4): push the branch and open a draft PR carrying the
    plan link, immediately after ``/work``'s Phase 1.4 saga mint. Records the draft
    PR on ``pr_refs`` right away; the later ``open_pr`` transition detects it and
    flips it ready instead of creating a second PR.

    Refuses to run if the ceremony has already progressed (``ceremony_transition``
    set) or a PR already exists (``pr_refs`` populated) — code-review correctness
    finding: an unconditional ``start()`` call on an already-progressed saga would
    open a second PR AND regress ``ceremony_transition`` back to ``'commit'``,
    causing the next ``run`` to re-execute already-completed transitions.
    """
    saga = resolve_saga(repo_root=repo_root, issue_ref=issue_ref, runner=runner)
    if saga.get("ceremony_transition") or saga.get("pr_refs"):
        raise ShipCeremonyError(
            "ceremony already in progress for this saga "
            f"(ceremony_transition={saga.get('ceremony_transition')!r}, "
            f"pr_refs={saga.get('pr_refs')!r}); 'start' is front-loaded-mode-only and "
            "must not run against a saga that already has state — use 'run' to continue"
        )
    branch = current_branch(repo_root, runner=runner)
    _run(["git", "push", "-u", "origin", branch], cwd=repo_root, runner=runner)

    plan_path = saga.get("plan_path") or ""
    body = f"Plan: {plan_path}" if plan_path else ""
    _run(
        ["gh", "pr", "create", "--draft", "--head", branch, "--fill", "--body", body],
        cwd=repo_root,
        runner=runner,
    )
    pr_view = _run(["gh", "pr", "view", branch, "--json", "number"], cwd=repo_root, runner=runner)
    pr_number = json.loads(pr_view.stdout)["number"]

    _saga_cli(
        [
            "save",
            "--kind",
            saga["kind"],
            "--id",
            _saga_short_id(saga),
            "--pr-refs",
            f"#{pr_number}",
            "--ceremony-transition",
            "commit",
            "--ceremony-tier",
            TRANSITION_TIERS["commit"],
        ],
        repo_root=repo_root,
        runner=runner,
    )
    return f"opened draft PR #{pr_number}, ceremony at 'commit' complete"


def install(
    *, repo_root: Path, force: bool = False, runner: Callable[..., Any] | None = None
) -> str:
    """Install the local (repo-scoped) ``git ship`` alias (R4b/KTD3). Never touches
    global git config. Refuses to overwrite an unrelated pre-existing alias unless
    ``force`` is set; a re-install pointing at this same script is a no-op success."""
    script_path = Path(__file__).resolve()
    target_command = f"!python3 {script_path} run"

    existing = _run(
        ["git", "config", "--local", "--get", "alias.ship"],
        cwd=repo_root,
        runner=runner,
        check=False,
    )
    if getattr(existing, "returncode", 1) == 0:
        current = existing.stdout.strip()
        if current == target_command:
            return "alias.ship already installed and up to date (no-op)"
        if not force:
            raise ShipCeremonyError(
                f"alias.ship already set to {current!r}; pass --force to overwrite"
            )

    _run(
        ["git", "config", "--local", "alias.ship", target_command],
        cwd=repo_root,
        runner=runner,
    )
    return "installed 'git ship' as a local (repo-scoped) alias"


def uninstall(*, repo_root: Path, runner: Callable[..., Any] | None = None) -> str:
    """Remove the local ``git ship`` alias. Idempotent — no alias installed is success."""
    result = _run(
        ["git", "config", "--local", "--unset", "alias.ship"],
        cwd=repo_root,
        runner=runner,
        check=False,
    )
    if getattr(result, "returncode", 1) not in (0, 5):
        raise ShipCeremonyError(
            f"git config --unset alias.ship failed unexpectedly: "
            f"{(getattr(result, 'stderr', '') or '').strip()}"
        )
    return "alias.ship removed (or was already absent)"


# --------------------------------------------------------------------------- #
# argparse wiring
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root", type=Path, default=Path.cwd(), help="repo root (default: cwd)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="execute the next unrun ceremony transition")
    p_run.add_argument("--issue-ref", default=None, help="owner/repo#N; omit to resolve by branch")
    p_run.add_argument(
        "--saga-id",
        default=None,
        help="explicit saga id (e.g. task-<slug>); survives checkout_main, unlike by-branch resolution",
    )

    p_start = sub.add_parser("start", help="front-loaded mode: push branch, open draft PR")
    p_start.add_argument("--issue-ref", required=True, help="owner/repo#N")

    p_install = sub.add_parser("install", help="install the local 'git ship' alias")
    p_install.add_argument(
        "--force", action="store_true", help="overwrite a pre-existing, unrelated alias.ship"
    )

    sub.add_parser("uninstall", help="remove the local 'git ship' alias")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root

    try:
        if args.command == "run":
            print(run(repo_root=repo_root, issue_ref=args.issue_ref, saga_id=args.saga_id))
        elif args.command == "start":
            print(start(repo_root=repo_root, issue_ref=args.issue_ref))
        elif args.command == "install":
            print(install(repo_root=repo_root, force=getattr(args, "force", False)))
        elif args.command == "uninstall":
            print(uninstall(repo_root=repo_root))
        else:  # pragma: no cover - argparse enforces valid choices
            parser.error(f"unknown command {args.command!r}")
            return 2
    except ShipCeremonyError as exc:
        print(f"ship_ceremony: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
