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
``{transition, tier, branch, base, head_sha, pr_number, merge_sha, pre_merge_main_sha,
remote_created, undone}``. ``pre_merge_main_sha`` is audit-only forensic context —
``undo()`` reverts from ``merge_sha`` alone and never consumes it programmatically.
``base`` is the opposite: it is the ceremony's merge target, recorded by
``ship_ceremony._do_merge`` and consumed programmatically by ``_undo_merge`` (issue
#635, R12) so the revert lands on the branch the merge actually landed on.

``undo()`` is forward-only (KTD4): a landed merge is undone with ``git revert
<recorded squash SHA>`` on the ceremony's recorded base branch (a new commit, never a
rewrite), and a deleted branch is resurrected from its recorded head SHA. It never
runs ``push --force`` or ``reset`` on a shared ref. A recorded SHA that is
unreachable (squash-discarded
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
import os
import re
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

# Undo target for a ``merge`` entry that predates base recording (issue #635, R12).
# Reached exactly when the entry carries no ``base`` — nothing else is consulted, and
# in particular the repo's current default branch is deliberately NOT resolved. Not a
# guess: every such entry was written by a ``_do_merge`` that probed ``refs/heads/main``
# literally, so ``main`` is the branch its recorded sha was actually read from —
# reverting there is exactly the pre-#635 behavior, which is the compatibility contract
# for old manifests. Entries written from now on always carry their own base, so this
# floor never applies to them.
LEGACY_MERGE_BASE = "main"

# saga_id becomes a path component under .claude/saga/sagas/ — a traversal value
# ("../..", absolute path) would read/write outside the sidecar directory. Single
# path segment, alphanumeric first char (also excludes "." / ".." / leading "-").
_SAGA_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_PR_NUMBER_RE = re.compile(r"[0-9]+")


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
    untouched. Carries a ``remedy`` (same contract as
    ``merge_watcher.MergeExpectationMissingError``) so the operator's next step is
    in the message."""

    def __init__(self, sha: str, *, entry_transition: str) -> None:
        self.sha = sha
        self.entry_transition = entry_transition
        self.kind = SHA_UNREACHABLE
        self.remedy = (
            "the sha was not found even after 'git fetch origin' — recover it "
            "(mirror clone, origin reflog) or resolve this entry by hand; it stays "
            "unmarked, so a later undo resumes exactly here"
        )
        super().__init__(
            f"{SHA_UNREACHABLE}: sha {sha!r} recorded on transition {entry_transition!r} "
            f"is not reachable in this repository; {self.remedy}"
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


def _merge_entry_base(entry: Mapping[str, Any]) -> str:
    """The branch a ``merge`` entry's revert belongs on (issue #635, R12).

    The recorded ``base`` — written by ``ship_ceremony._do_merge`` from
    ``resolve_ceremony_refs`` (the PR's own ``baseRefName`` when that rung answers,
    the ceremony base sidecar otherwise) — is authoritative: it is the branch the
    squash actually landed on, and therefore the only branch where
    ``git revert <merge_sha>`` reverts *this ceremony's* work.

    An entry without one predates base recording, and its fallback is the *literal*
    ``LEGACY_MERGE_BASE``, deliberately NOT the repository's current default branch. Such
    an entry's ``merge_sha`` was read by a pre-#635 ``_do_merge`` that probed
    ``refs/heads/main`` verbatim, so ``main`` is provably where that sha came from.
    Resolving the default branch instead would send the revert wherever
    ``refs/remotes/origin/HEAD`` happens to point today — on a repo whose default is not
    ``main`` that is a branch the recorded sha was never read from, which is neither the
    pre-#635 behavior nor a safe place to revert. Provenance beats currency here: the
    compatibility contract is "revert where the sha actually came from"."""
    recorded = str(entry.get("base") or "").strip()
    if recorded:
        return _require_option_safe(recorded, field="base", transition="merge")
    return LEGACY_MERGE_BASE


def _sha_reachable(sha: str, *, repo_root: Path, runner: Callable[..., Any] | None) -> bool:
    """Best-effort reachability check — ``git cat-file -e <sha>^{commit}``, and on a
    local miss one ``git fetch origin`` before re-probing: the squash SHA a merge
    records exists only on origin until this clone pulls, and declaring it
    unreachable in that window would falsely block the undo. The fetch itself is
    best-effort (``check=False``) so offline undo of local-only entries still works.
    Never raises: a non-zero/erroring probe means "not reachable", not "unknown"."""

    def _probe() -> bool:
        result = _run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            cwd=repo_root,
            runner=runner,
            check=False,
        )
        return getattr(result, "returncode", 1) == 0

    if _probe():
        return True
    _run(["git", "fetch", "origin"], cwd=repo_root, runner=runner, check=False)
    return _probe()


# --------------------------------------------------------------------------- #
# Manifest sidecar — append/read helpers (KTD1)
# --------------------------------------------------------------------------- #


def _validate_saga_id(saga_id: str) -> str:
    if not _SAGA_ID_RE.fullmatch(saga_id):
        raise ShipUndoError(
            f"invalid saga_id {saga_id!r}: must be a single path-safe segment "
            "matching [A-Za-z0-9][A-Za-z0-9._-]* (e.g. issue-345)"
        )
    return saga_id


def _require_option_safe(value: str, *, field: str, transition: str) -> str:
    """Manifest-sourced strings become git/gh argv — a value opening with ``-``
    would parse as an option, not a ref. Refused loud, never sanitized."""
    if value.startswith("-"):
        raise ShipUndoError(
            f"{field} {value!r} recorded on transition {transition!r} begins with '-' "
            "and cannot be passed to git/gh safely; fix the rollback manifest by hand"
        )
    return value


def manifest_path(repo_root: Path, saga_id: str) -> Path:
    return repo_root / SAGAS_DIR / _validate_saga_id(saga_id) / MANIFEST_NAME


def read_manifest(repo_root: Path, saga_id: str) -> list[dict[str, Any]]:
    """Read every recorded entry, oldest-first (append order). Returns ``[]`` when
    no manifest has been written yet — never an error (a saga with no ceremony
    progress simply has nothing to undo)."""
    path = manifest_path(repo_root, saga_id)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ShipUndoError(f"rollback manifest at {path} is not valid JSON: {exc}") from exc
    return list(data)


def _write_manifest(repo_root: Path, saga_id: str, entries: Sequence[Mapping[str, Any]]) -> Path:
    path = manifest_path(repo_root, saga_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace (same idiom as saga.py's _atomic_write) — a crash mid-write
    # must never leave a truncated manifest that a resuming undo() would misread.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(list(entries), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def append_entry(
    *,
    repo_root: Path,
    saga_id: str,
    transition: str,
    tier: str,
    branch: str | None = None,
    base: str | None = None,
    head_sha: str | None = None,
    pr_number: int | str | None = None,
    merge_sha: str | None = None,
    pre_merge_main_sha: str | None = None,
    remote_created: bool = False,
) -> dict[str, Any]:
    """Append one entry for a just-completed ceremony transition (R6). Read-append-
    rewrite, mirroring ``tier_session.py``'s sidecar pattern — small files, no
    concurrent writers (single-operator assumption, same as the rest of ``.claude/saga/``).

    ``base`` is the ceremony's merge target (issue #635, R12). The ``merge`` transition
    passes the value ``ship_ceremony._do_merge`` already resolved via
    ``resolve_ceremony_refs``, so ``_undo_merge`` can target the right branch from the
    manifest alone — no ``gh`` round trip at undo time, on a path that has to work when
    the network does not.
    ``None`` on every other transition, and on any entry written before #635."""
    entries = read_manifest(repo_root, saga_id)
    entry: dict[str, Any] = {
        "transition": transition,
        "tier": tier,
        "branch": branch,
        "base": base,
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
    _require_option_safe(str(branch), field="branch", transition="commit")
    _run(
        ["git", "push", "origin", "--delete", "--", branch],
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
    if not _PR_NUMBER_RE.fullmatch(str(pr_number)):
        raise ShipUndoError(
            f"pr_number {pr_number!r} recorded on transition 'open_pr' is not a "
            "plain PR number; fix the rollback manifest by hand"
        )
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
    """Reverse of ``merge`` (KTD4): ``git revert <recorded squash SHA>`` on the
    **ceremony's recorded base** — a new commit, never a rewrite — then push. Refuses
    with a named ``SHA_UNREACHABLE`` failure rather than fabricating a revert target.

    The checkout and the push both name one resolved branch, and the revert runs on
    the branch that checkout left HEAD on (issue #635, R12) — the revert's own argv
    names only the sha. All three steps used to target the literal ``main``, which
    made the undo of a
    leaf-into-outcome ceremony destructive rather than merely wrong: once the outcome
    branch itself has landed on the default branch, the leaf's squash sha *is* an
    ancestor of ``main``, so ``git revert`` applies cleanly there and strips that leaf's
    work off the default branch — no conflict, no refusal, nothing to notice. Recording
    the right sha (``_do_merge``) and applying it to the right branch (here) are two
    halves of one property; neither alone is enough.

    Resumable across the revert-lands-locally-but-push-rejected failure mode: if a
    prior (failed) attempt already created the revert commit locally,
    ``_revert_already_applied`` detects it and this skips straight to the push
    instead of re-reverting an already-reverted commit."""
    merge_sha = entry.get("merge_sha")
    if not merge_sha:
        raise UndoTransitionFailedError(
            "merge entry is missing merge_sha; cannot revert a merge that was never recorded"
        )
    _require_option_safe(str(merge_sha), field="merge_sha", transition="merge")
    # Resolved before the reachability probe so an option-like recorded base refuses
    # before this handler shells out at all (same contract as the branch/pr_number
    # guards): the base becomes git argv below, and it selects the branch the revert
    # in between lands on.
    base = _merge_entry_base(entry)
    if not _sha_reachable(merge_sha, repo_root=repo_root, runner=runner):
        raise SHAUnreachableError(merge_sha, entry_transition="merge")
    current = _current_branch(repo_root, runner=runner)
    if current != base:
        _run(["git", "checkout", base], cwd=repo_root, runner=runner)
    if not _revert_already_applied(merge_sha, repo_root=repo_root, runner=runner):
        _run(["git", "revert", "--no-edit", merge_sha], cwd=repo_root, runner=runner)
    _run(["git", "push", "origin", base], cwd=repo_root, runner=runner)


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
    _require_option_safe(str(branch), field="branch", transition=str(entry.get("transition")))
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
    # Trailing "--" pins <branch> as a revision, never a pathspec.
    _run(["git", "checkout", branch, "--"], cwd=repo_root, runner=runner)


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
    _require_option_safe(str(branch), field="branch", transition="branch_delete")
    _require_option_safe(str(head_sha), field="head_sha", transition="branch_delete")
    if not _sha_reachable(head_sha, repo_root=repo_root, runner=runner):
        raise SHAUnreachableError(head_sha, entry_transition="branch_delete")
    exists = _run(
        ["git", "rev-parse", "--verify", branch],
        cwd=repo_root,
        runner=runner,
        check=False,
    )
    if getattr(exists, "returncode", 1) != 0:
        _run(["git", "branch", "--", branch, head_sha], cwd=repo_root, runner=runner)
    _run(["git", "push", "origin", "--", branch], cwd=repo_root, runner=runner)


def _undo_teardown(
    entry: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> None:
    """``teardown``'s forward transition (issue #347) mints an immutable, write-once
    ship receipt and reclaims idle merged worktrees — both forward-only truths. There
    is nothing to reverse: the receipt is tamper-evident by design (0444, exclusive
    create), and a reclaimed merged worktree is trivially re-created via
    ``git worktree add`` from the surviving merged branch, not something undo owns. This
    handler exists so a rollback manifest carrying a ``teardown`` entry never crashes
    undo on an unregistered transition name — it is a deliberate no-op."""


_REVERSE_RUNNERS: Mapping[str, Callable[..., None]] = {
    "commit": _undo_commit,
    "open_pr": _undo_open_pr,
    "request_review": _undo_request_review,
    "merge": _undo_merge,
    "checkout_main": _undo_checkout_main,
    "pull": _undo_pull,
    "branch_delete": _undo_branch_delete,
    "teardown": _undo_teardown,
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
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ShipUndoError(
            f"saga.py {' '.join(args)} returned unparseable JSON: {result.stdout!r}"
        ) from exc


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
