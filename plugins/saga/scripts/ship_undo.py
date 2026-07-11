#!/usr/bin/env python3
"""ship_undo.py — rollback manifest + undo engine for ship_ceremony.py (issue #346, U3).

A ceremony that dies after merge used to leave the operator reconstructing state by
hand — there was no undo. This module is the two-part answer: append/read helpers
over a rollback manifest sidecar (KTD1), and an ``undo()`` engine that executes the
reverse of a recorded ceremony newest-to-oldest (KTD4), gated per KTD5.

Storage (KTD1): the manifest is a JSON sidecar at
``.claude/saga/sagas/<saga_id>/rollback_manifest.json`` — git-ignored, machine-local,
written directly by this module (never through ``saga.py save``), one entry per
successful ceremony transition:
``{transition, tier, branch, head_sha, pr_number, merge_sha, pre_merge_main_sha,
remote_created, undone}``.

``undo()`` is forward-only (KTD4): a landed merge is undone with ``git revert
<recorded squash SHA>`` on ``main`` (a new commit, never a rewrite), and a deleted
branch is resurrected from its recorded head SHA. It never runs ``push --force`` or
``reset`` on a shared ref. A recorded SHA that is unreachable (squash-discarded
commits GC'd on origin, absent locally) surfaces a named ``SHA_UNREACHABLE`` failure
for that entry rather than fabricating state — the remaining (older) entries stay
untouched so a fixed re-invoke can resume.

Gating (KTD5) mirrors the forward ceremony's operator-confirmation palette: an undo
plan whose in-scope entries include an ``always_operator``-tier transition (``merge``,
``branch_delete`` — mirrored locally as ``ALWAYS_OPERATOR_TRANSITIONS`` rather than
imported from ``ship_ceremony.py``, the same "duplicated, not imported" pattern
``ceremony_hazards.py`` uses, so U4 can import THIS module from ``ship_ceremony.py``
without a circular import) requires ``operator_confirmed == "undo"``; a plan touching
only reversible entries runs on the bare call alone. Gating is computed from the
in-scope entries *before anything executes* — refuse-before-dispatch, ledger-unadvanced
contract, same shape as the #526 forward gate.

Resumability: each entry is marked ``undone: true`` only *after* its reverse mutation
confirms (the manifest is rewritten to disk immediately after each successful step,
not batched at the end) — a process killed mid-undo, or a step that raises, leaves
already-reverted entries marked and everything else untouched, so a later ``undo()``
call against the same saga picks up exactly where it left off. An empty or
fully-undone manifest is a no-op success, not an error.

House testability pattern (mirrors ``ship_ceremony.py`` / ``ceremony_hazards.py`` /
``merge_watcher.py``): every function that shells out takes a ``runner`` callable,
defaulted to ``subprocess.run`` resolved at call time (never bound as a default
argument), so tests can pass a fake runner directly.
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

# Machine-local, git-ignored — sibling of the saga cache (SAGAS_DIR in saga.py) and the
# merge-expectation sidecar (merge_watcher.py:53). No import of saga.py's constants
# (U3 "Depends on: nothing"); the path shape is duplicated here deliberately.
STATE_DIR = Path(".claude/saga")
SAGAS_DIR = STATE_DIR / "sagas"
MANIFEST_NAME = "rollback_manifest.json"

# Mirrors ship_ceremony.CeremonyTier.ALWAYS_OPERATOR members (merge, branch_delete) —
# duplicated rather than imported so ship_ceremony.py can import THIS module (U4)
# without a circular import (the same pattern ceremony_hazards.py documents at its
# top for the same reason).
ALWAYS_OPERATOR_TRANSITIONS: frozenset[str] = frozenset({"merge", "branch_delete"})

SHA_UNREACHABLE = "SHA_UNREACHABLE"


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class ShipUndoError(Exception):
    """Base error for ship_undo.py — always caught at the CLI boundary and reported
    as a message, never an uncaught traceback."""


class UndoTransitionFailedError(ShipUndoError):
    """The underlying git/gh call for a reverse step failed; the entry was NOT
    marked undone (resumability contract)."""


class SHAUnreachableError(ShipUndoError):
    """A recorded SHA (merge_sha or head_sha) is unreachable — squash-discarded
    commits GC'd on origin, or simply absent locally (KTD4). Named, not fabricated;
    the entry stays unmarked and later (older) entries in this run are left
    untouched."""

    def __init__(self, sha: str, *, entry_transition: str) -> None:
        self.sha = sha
        self.entry_transition = entry_transition
        self.kind = SHA_UNREACHABLE
        super().__init__(
            f"{SHA_UNREACHABLE}: sha {sha!r} recorded on transition {entry_transition!r} "
            "is not reachable in this repository; undo cannot proceed for this entry"
        )


class UndoOperatorConfirmationError(ShipUndoError):
    """The in-scope undo plan reverses an ``always_operator``-tier transition and was
    not confirmed via ``operator_confirmed == 'undo'`` (KTD5); refused before any
    mutation and before the manifest is touched."""


# --------------------------------------------------------------------------- #
# Subprocess helper — runner injectable, never bound as a default argument.
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
        raise UndoTransitionFailedError(
            f"{' '.join(cmd)} failed (exit {result.returncode}): "
            f"{(getattr(result, 'stderr', '') or '').strip()}"
        )
    return result


def _current_branch(repo_root: Path, *, runner: Callable[..., Any] | None) -> str:
    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, runner=runner)
    return result.stdout.strip()


def _sha_reachable(sha: str, *, repo_root: Path, runner: Callable[..., Any] | None) -> bool:
    """Best-effort local reachability check — ``git cat-file -e <sha>^{commit}``.
    Never raises: a non-zero/erroring probe means "not reachable", not "unknown"."""
    result = _run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=repo_root,
        runner=runner,
        check=False,
    )
    return getattr(result, "returncode", 1) == 0


# --------------------------------------------------------------------------- #
# Manifest sidecar — append/read helpers (KTD1)
# --------------------------------------------------------------------------- #


def manifest_path(repo_root: Path, saga_id: str) -> Path:
    return repo_root / SAGAS_DIR / saga_id / MANIFEST_NAME


def read_manifest(repo_root: Path, saga_id: str) -> list[dict[str, Any]]:
    """Read every recorded entry, oldest-first (append order). Returns ``[]`` when
    no manifest has been written yet — never an error (a saga with no ceremony
    progress simply has nothing to undo)."""
    path = manifest_path(repo_root, saga_id)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return list(data)


def _write_manifest(repo_root: Path, saga_id: str, entries: Sequence[Mapping[str, Any]]) -> Path:
    path = manifest_path(repo_root, saga_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(entries), indent=2, sort_keys=True) + "\n")
    return path


def append_entry(
    *,
    repo_root: Path,
    saga_id: str,
    transition: str,
    tier: str,
    branch: str | None = None,
    head_sha: str | None = None,
    pr_number: int | str | None = None,
    merge_sha: str | None = None,
    pre_merge_main_sha: str | None = None,
    remote_created: bool = False,
) -> dict[str, Any]:
    """Append one entry for a just-completed ceremony transition (R6). Read-append-
    rewrite, mirroring ``tier_session.py``'s sidecar pattern — small files, no
    concurrent writers (single-operator assumption, same as the rest of ``.claude/saga/``).
    """
    entries = read_manifest(repo_root, saga_id)
    entry: dict[str, Any] = {
        "transition": transition,
        "tier": tier,
        "branch": branch,
        "head_sha": head_sha,
        "pr_number": pr_number,
        "merge_sha": merge_sha,
        "pre_merge_main_sha": pre_merge_main_sha,
        "remote_created": remote_created,
        "undone": False,
    }
    entries.append(entry)
    _write_manifest(repo_root, saga_id, entries)
    return entry


# --------------------------------------------------------------------------- #
# Reverse step handlers — one per TRANSITIONS entry (U3 Behavior). Each raises on
# failure; the caller (``undo``) is responsible for only marking ``undone: true``
# after the handler returns without raising.
# --------------------------------------------------------------------------- #


def _undo_commit(
    entry: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    """Reverse of ``commit`` (a branch push): delete the remote ref, but only if
    this ceremony was the one that created it (``remote_created``) — never delete a
    remote branch that predates the ceremony. ``check=False``: the ref may already
    be gone (idempotent, resumable)."""
    if not entry.get("remote_created"):
        return
    branch = entry.get("branch")
    if not branch:
        return
    _run(
        ["git", "push", "origin", "--delete", branch],
        cwd=repo_root,
        runner=runner,
        check=False,
    )


def _undo_open_pr(
    entry: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    """Reverse of ``open_pr``: close the PR — the reversible-plan path (R7) for a
    ceremony killed right after PR-open."""
    pr_number = entry.get("pr_number")
    if not pr_number:
        return
    _run(["gh", "pr", "close", str(pr_number)], cwd=repo_root, runner=runner)


def _undo_request_review(
    entry: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    """``request_review``'s forward transition is a deliberate no-op
    (ship_ceremony.py's ``_do_request_review``); its reverse is a no-op too."""


def _revert_already_applied(
    sha: str, *, repo_root: Path, runner: Callable[..., Any] | None
) -> bool:
    """True iff a revert commit for ``sha`` (``git revert``'s auto-generated ``This
    reverts commit <sha>`` trailer) already exists in history. Guards the
    revert-lands-locally-but-push-rejected resume case named in the plan's Risk
    Analysis: a naive retry would try to ``git revert`` an already-reverted commit
    a second time and fail loud on "nothing to commit" — this lets a resumed undo()
    skip straight to the (still-pending) push instead."""
    result = _run(
        ["git", "log", "--all", "--fixed-strings", "--grep", f"This reverts commit {sha}"],
        cwd=repo_root,
        runner=runner,
        check=False,
    )
    return bool((getattr(result, "stdout", "") or "").strip())


def _undo_merge(
    entry: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    """Reverse of ``merge`` (KTD4): ``git revert <recorded squash SHA>`` on
    ``main`` — a new commit, never a rewrite — then push. Refuses with a named
    ``SHA_UNREACHABLE`` failure rather than fabricating a revert target.

    Resumable across the revert-lands-locally-but-push-rejected failure mode: if a
    prior (failed) attempt already created the revert commit locally,
    ``_revert_already_applied`` detects it and this skips straight to the push
    instead of re-reverting an already-reverted commit."""
    merge_sha = entry.get("merge_sha")
    if not merge_sha:
        raise UndoTransitionFailedError(
            "merge entry is missing merge_sha; cannot revert a merge that was never recorded"
        )
    if not _sha_reachable(merge_sha, repo_root=repo_root, runner=runner):
        raise SHAUnreachableError(merge_sha, entry_transition="merge")
    current = _current_branch(repo_root, runner=runner)
    if current != "main":
        _run(["git", "checkout", "main"], cwd=repo_root, runner=runner)
    if not _revert_already_applied(merge_sha, repo_root=repo_root, runner=runner):
        _run(["git", "revert", "--no-edit", merge_sha], cwd=repo_root, runner=runner)
    _run(["git", "push", "origin", "main"], cwd=repo_root, runner=runner)


def _restore_pre_ceremony_checkout(
    entry: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    """Shared reverse behavior for ``checkout_main``/``pull``: restore the recorded
    pre-ceremony checkout (the saga's own branch) — a no-op if HEAD is already
    there, or if that branch no longer exists locally (a not-yet-resurrected
    ``branch_delete`` entry elsewhere in the same undo run; mutation order across
    entries is newest-to-oldest, not a same-tick dependency graph, so this must
    tolerate either ordering relative to the branch-delete reverse)."""
    branch = entry.get("branch")
    if not branch:
        return
    current = _current_branch(repo_root, runner=runner)
    if current == branch:
        return
    exists = _run(
        ["git", "rev-parse", "--verify", branch],
        cwd=repo_root,
        runner=runner,
        check=False,
    )
    if getattr(exists, "returncode", 1) != 0:
        return
    _run(["git", "checkout", branch], cwd=repo_root, runner=runner)


def _undo_checkout_main(
    entry: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    _restore_pre_ceremony_checkout(entry, repo_root=repo_root, runner=runner)


def _undo_pull(
    entry: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    _restore_pre_ceremony_checkout(entry, repo_root=repo_root, runner=runner)


def _undo_branch_delete(
    entry: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    """Reverse of ``branch_delete``: resurrect the branch from its recorded head
    SHA (KTD4 — never a force-push, never a reset), then push it back to origin."""
    branch = entry.get("branch")
    head_sha = entry.get("head_sha")
    if not branch or not head_sha:
        raise UndoTransitionFailedError(
            "branch_delete entry is missing branch/head_sha; cannot resurrect"
        )
    if not _sha_reachable(head_sha, repo_root=repo_root, runner=runner):
        raise SHAUnreachableError(head_sha, entry_transition="branch_delete")
    exists = _run(
        ["git", "rev-parse", "--verify", branch],
        cwd=repo_root,
        runner=runner,
        check=False,
    )
    if getattr(exists, "returncode", 1) != 0:
        _run(["git", "branch", branch, head_sha], cwd=repo_root, runner=runner)
    _run(["git", "push", "origin", branch], cwd=repo_root, runner=runner)


_REVERSE_RUNNERS: Mapping[str, Callable[..., None]] = {
    "commit": _undo_commit,
    "open_pr": _undo_open_pr,
    "request_review": _undo_request_review,
    "merge": _undo_merge,
    "checkout_main": _undo_checkout_main,
    "pull": _undo_pull,
    "branch_delete": _undo_branch_delete,
}


# --------------------------------------------------------------------------- #
# undo() — the engine (R7/R8/KTD4/KTD5)
# --------------------------------------------------------------------------- #


def undo(
    saga: Mapping[str, Any],
    *,
    repo_root: Path,
    operator_confirmed: str | None = None,
    runner: Callable[..., Any] | None = None,
) -> str:
    """Revert a ceremony from its rollback manifest alone, newest-to-oldest (KTD4).

    Stateless re-read like the forward ceremony (module docstring): every call
    re-reads the manifest from disk, computes the in-scope (not-yet-undone) entries,
    and gates on those alone. An empty or fully-undone manifest is a no-op success.

    Gating (KTD5, computed from in-scope entries before anything executes): if any
    in-scope entry reverses an ``always_operator``-tier transition (``merge``,
    ``branch_delete``), ``operator_confirmed`` must equal exactly ``"undo"`` or this
    raises ``UndoOperatorConfirmationError`` before any mutation and before the
    manifest is rewritten — the same refuse-before-dispatch, ledger-unadvanced
    contract as the forward ceremony's #526 gate.

    Each entry's reverse mutation is executed and, only once it confirms, the entry
    is marked ``undone: true`` and the manifest is rewritten immediately — so a
    process killed mid-undo, or a step that raises (including a named
    ``SHAUnreachableError``), leaves already-reverted entries marked and all
    remaining (older) entries untouched, ready for a later, resuming call.
    """
    saga_id = str(saga["saga_id"])
    entries = read_manifest(repo_root, saga_id)
    pending_indices = [i for i, e in enumerate(entries) if not e.get("undone")]

    if not pending_indices:
        return "no-op — rollback manifest is empty or already fully undone"

    in_scope_transitions = {entries[i]["transition"] for i in pending_indices}
    gated = in_scope_transitions & ALWAYS_OPERATOR_TRANSITIONS
    if gated and operator_confirmed != "undo":
        raise UndoOperatorConfirmationError(
            f"undo plan reverses always_operator-tier transition(s) {sorted(gated)}; "
            "re-run with operator_confirmed='undo' (--operator-confirmed undo)"
        )

    reverted = 0
    for index in reversed(pending_indices):
        entry = entries[index]
        transition = str(entry["transition"])
        handler = _REVERSE_RUNNERS.get(transition)
        if handler is None:
            raise ShipUndoError(
                f"no reverse handler registered for transition {transition!r}; "
                f"expected one of {sorted(_REVERSE_RUNNERS)}"
            )
        handler(entry, repo_root=repo_root, runner=runner)
        entries[index]["undone"] = True
        _write_manifest(repo_root, saga_id, entries)
        reverted += 1

    return f"undo complete — reverted {reverted} transition(s) for saga {saga_id!r}"


# --------------------------------------------------------------------------- #
# CLI subcommands — a thin operator-facing wrapper; ``ship_ceremony.py`` (U4) calls
# ``undo()`` directly as a library function, this is for standalone/manual use.
# --------------------------------------------------------------------------- #


def _saga_cli(
    args: Sequence[str],
    *,
    repo_root: Path,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    result = _run(
        [sys.executable, str(SAGA_PY), *args],
        cwd=repo_root,
        runner=runner,
    )
    return json.loads(result.stdout)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root", type=Path, default=Path.cwd(), help="repo root (default: cwd)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_undo = sub.add_parser("undo", help="revert a ceremony from its rollback manifest")
    p_undo.add_argument("--saga-id", required=True, help="e.g. issue-345 or task-<slug>")
    p_undo.add_argument(
        "--operator-confirmed",
        default=None,
        choices=("undo",),
        help="pass 'undo' when the in-scope plan reverses merge/branch_delete (KTD5)",
    )

    p_show = sub.add_parser("show", help="print the current rollback manifest as JSON")
    p_show.add_argument("--saga-id", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root

    try:
        if args.command == "undo":
            saga = _saga_cli(["restore", "--saga-id", args.saga_id], repo_root=repo_root)
            print(
                undo(
                    saga,
                    repo_root=repo_root,
                    operator_confirmed=args.operator_confirmed,
                )
            )
        elif args.command == "show":
            print(json.dumps(read_manifest(repo_root, args.saga_id), indent=2, sort_keys=True))
        else:  # pragma: no cover - argparse enforces valid choices
            parser.error(f"unknown command {args.command!r}")
            return 2
    except ShipUndoError as exc:
        print(f"ship_undo: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
