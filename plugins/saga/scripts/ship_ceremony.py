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
*authorization* (R5). Sequencing and bookkeeping are not the whole of authorization,
though: ``run()`` also enforces it directly for ``always_operator``-tier transitions
(``merge``, ``branch_delete``) — a bare ``run`` reaching one of them refuses
(``OperatorConfirmationError``) before the transition runner or ``saga.py save`` is
ever reached, and only ``--operator-confirmed <transition>`` naming that exact
transition unlocks it (issue #526). The gate is a tier lookup against
``TRANSITION_TIERS``, never a hardcoded transition-name list, so any future
transition declared ``always_operator`` inherits enforcement automatically.

Reversibility tiers (KTD1) are declared locally as ``CeremonyTier`` rather than reusing
``reversibility_certificate.py`` — that module's own docstring scopes its ``OpKind``
allowlist to mission-control board/issue verbs and intentionally excludes merge,
deploy, and repo-level mutations (its R20). Ceremony state (KTD2) rides the governing
issue's existing work-thread saga tick via ``saga.py save --ceremony-transition
--ceremony-tier`` rather than a second store; no index is persisted; the transition's
position is always recomputed from ``TRANSITIONS`` so there is nothing to drift out of
sync with the name.

Ceremony refs (issue #635) are resolved, never guessed: ``resolve_ceremony_refs``
answers "what are this ceremony's head and base branches?" from the PR itself first,
then from ceremony-scoped local evidence (the opened-resource manifest's
``ceremony-branch:`` entry plus the per-saga base sidecar), then refuses. The saga's
``branch`` tick field is not a rung at any point — ``saga.py`` re-stamps it from
``git branch --show-current`` on every save, so it records "wherever the last tick
happened", and a destructive path trusting it deletes the PR base on a
leaf-into-outcome ceremony. ``resolve_default_branch`` likewise resolves the repo
default rather than hardcoding ``"main"``.

House testability pattern (mirrors ``outcome_store.py``): every function that shells
out takes a ``runner`` callable, defaulted to ``subprocess.run`` resolved at call time
(never bound as a default argument), so tests can monkeypatch ``ship_ceremony.subprocess.run``
or pass a fake runner directly.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess  # nosec B404
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SAGA_PY = SCRIPT_DIR / "saga.py"

# Sibling-module imports (issue #346, U4): the hazard registry, the merge-watcher,
# and the undo engine are imported directly (not shelled out to) so run() can call
# them as a library — mirrors the sys.path.insert + import pattern already used by
# engine_dispatch.py and friends in this directory. Each of those three modules
# documents "Depends on: nothing" (U1-U3) specifically so this import graph stays
# one-directional: they never import ship_ceremony.py back.
sys.path.insert(0, str(SCRIPT_DIR))

import ceremony_hazards  # noqa: E402
import merge_watcher  # noqa: E402
import ship_receipt  # noqa: E402
import ship_teardown  # noqa: E402
import ship_undo  # noqa: E402


class ShipCeremonyError(Exception):
    """Base error for ship_ceremony.py — always caught at the CLI boundary and
    reported as a message, never an uncaught traceback."""


class AmbiguousSagaError(ShipCeremonyError):
    """More than one saga candidate matches the current branch; refuses to guess."""


class NoSagaError(ShipCeremonyError):
    """No saga candidate matches the current branch or the given issue-ref."""


class TransitionFailedError(ShipCeremonyError):
    """The underlying git/gh call for a transition failed; state was not advanced."""


class OperatorConfirmationError(ShipCeremonyError):
    """The upcoming transition is ``always_operator``-tier and was not (or was
    mismatched-ly) confirmed via ``--operator-confirmed <transition>``; refused
    before dispatch and before the save (R1/R3/KTD3)."""


class HazardRefusedError(ShipCeremonyError):
    """One or more ``ceremony_hazards.detect()`` findings on the upcoming transition
    were not acknowledged via ``--acknowledge-hazard <hazard-id>`` (or are not
    acknowledgeable at all, e.g. ``merge_not_landed``); refused before dispatch and
    before ``saga.py save`` (R1/R2/KTD2/KTD3)."""


class CeremonyRefsError(ShipCeremonyError):
    """The ceremony's head/base refs could not be resolved from ceremony-scoped
    evidence (issue #635, KTD2/R7). Raised only after every rung of the ladder is
    exhausted, and always names each source that was tried and what it lacked.
    ``saga["branch"]`` is deliberately not a rung: it is re-stamped from
    ``git branch --show-current`` on every ``saga.py save``, so it means "wherever the
    last tick happened", never "the branch this ceremony opened". Degrading to it is
    exactly the data-loss defect this resolver exists to remove, so exhausting the
    ladder refuses instead of guessing."""


class MergePreflightError(ShipCeremonyError):
    """``merge_watcher.validate()`` refused the ``merge`` transition — either no
    ``merge_expectation.json`` sidecar exists (KTD8) or live PR state diverged from
    the recorded baseline (R4); refused before dispatch and before ``saga.py save``
    (KTD2)."""


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
    "teardown",
)

TRANSITION_TIERS: Mapping[str, str] = {
    "commit": CeremonyTier.REVERSIBLE,
    "open_pr": CeremonyTier.REVERSIBLE,
    "request_review": CeremonyTier.REVERSIBLE,
    "merge": CeremonyTier.ALWAYS_OPERATOR,
    "checkout_main": CeremonyTier.REVERSIBLE,
    "pull": CeremonyTier.REVERSIBLE,
    "branch_delete": CeremonyTier.ALWAYS_OPERATOR,
    # teardown (issue #347, KTD3): the terminal gate. Appended after branch_delete so
    # next_transition() structurally refuses to report the ceremony complete until it
    # has run (AC6 — no configuration bypass). tier=REVERSIBLE is honest: teardown only
    # closes resources whose removal is reversible (merged worktrees, scratch,
    # already-merged draft PRs) and HALTs on anything else.
    "teardown": CeremonyTier.REVERSIBLE,
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
# Opened-resource manifest wiring (issue #347, KTD9) — register-on-open at the
# ceremony's own resource-opening sites (branch push, PR create) and close-on-close
# at the sites that close them (merge lands the PR, branch_delete removes the branch).
# The manifest is ship_teardown.py's per-saga sidecar; the terminal ``teardown``
# transition reconciles it. Resource ids are deterministic per (kind, ref) so the
# close site can address exactly what the open site registered.
# --------------------------------------------------------------------------- #


def _branch_resource_id(branch: str) -> str:
    return f"ceremony-branch:{branch}"


def _pr_resource_id(pr_number: str) -> str:
    return f"ceremony-pr:{pr_number}"


def _register_branch(
    saga: Mapping[str, Any], branch: str, *, repo_root: Path, opened_by: str
) -> None:
    """Register the pushed feature branch on the opened-resource manifest (R1). Shared
    by both push sites — ``_do_commit`` (plain ``run`` flow) and ``start()``
    (front-loaded) — since the branch is 'opened' the moment either pushes it. Idempotent
    per resource id (a re-push refreshes the still-open entry)."""
    ship_teardown.register(
        repo_root,
        str(saga["saga_id"]),
        _branch_resource_id(branch),
        kind="branch",
        ref=branch,
        opened_by=opened_by,
    )


def _register_pr(
    saga: Mapping[str, Any], pr_number: str, *, repo_root: Path, opened_by: str
) -> None:
    """Register a PR this ceremony opens on the opened-resource manifest (R1)."""
    ship_teardown.register(
        repo_root,
        str(saga["saga_id"]),
        _pr_resource_id(str(pr_number)),
        kind="draft_pr",
        ref=str(pr_number),
        opened_by=opened_by,
    )


def _close_if_registered(
    saga: Mapping[str, Any], resource_id: str, *, repo_root: Path, evidence: str
) -> None:
    """Close a manifest entry the ceremony owns, but only if it was registered —
    ``ship_teardown.close`` is fail-loud on an unknown id by design, yet a ceremony
    that predates this wiring (or a forced-state test jump) may legitimately have no
    entry to close. Absence here is not an accounting gap: reconcile still sees a truly
    unclosed entry as open. So this closes when present and no-ops when absent, never
    inventing an entry and never crashing the mutating transition it rides on."""
    saga_id = str(saga["saga_id"])
    if resource_id in ship_teardown.read_manifest(repo_root, saga_id):
        ship_teardown.close(repo_root, saga_id, resource_id, evidence=evidence)


# --------------------------------------------------------------------------- #
# Ceremony ref resolution (issue #635, U1) — the single answer to "what are this
# ceremony's head and base refs?", consumed by every site that used to guess from
# ``saga["branch"]`` or the literal string ``"main"`` (KTD1).
#
# The ladder (KTD2), in order:
#   1. ``gh pr view <n> --json headRefName,baseRefName`` when the saga carries a PR
#      ref — the ceremony's own externally durable record, immune to local drift and
#      the same thing the operator sees.
#   2. the ``ceremony-branch:`` entry on ``opened_resources.json`` (written once at
#      push time by ``_register_branch`` and never re-stamped) for the head, plus the
#      per-saga base sidecar for the base — a local answer that needs no network at
#      exactly the moment an operator is finishing a ship.
#   3. raise ``CeremonyRefsError`` naming every exhausted source.
#
# ``saga["branch"]`` is not a rung at any point (R7). Manifest-first was rejected:
# preferring local state over the shared record is how the ceremony got here.
#
# The base sidecar is a per-saga JSON file beside ``merge_expectation.json`` and
# ``rollback_manifest.json`` ({#ceremony-sidecars-forward-only-undo-346}, KTD4) — NOT
# a saga tick field. A tick field rolls with the checkout, which IS the defect; a
# sidecar is ceremony-scoped and stays put.
# --------------------------------------------------------------------------- #


SAGAS_DIR = ship_teardown.SAGAS_DIR
CEREMONY_BASE_SIDECAR_NAME = "ceremony_base.json"

# Same single-path-safe-segment shape ship_teardown / merge_watcher / ship_undo each
# enforce on the saga id before it becomes a directory name (traversal guard).
_SAGA_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

# ``CeremonyRefs.source`` values — the rung that actually answered, recorded so a
# consumer (and any future receipt/evidence surface) can say where a destructive
# target came from rather than asserting it was "resolved".
CEREMONY_REFS_SOURCE_PR = "pr_view"
CEREMONY_REFS_SOURCE_MANIFEST = "manifest_sidecar"


@dataclass(frozen=True)
class CeremonyRefs:
    """This ceremony's resolved refs. ``head`` is the PR head (the branch the
    ceremony opened and may delete); ``base`` is the PR base (the branch the merge
    lands on, checked out by ``checkout_main``, probed by ``_do_merge``); ``source``
    is the ladder rung that answered."""

    head: str
    base: str
    source: str


def _validate_saga_id(saga_id: str) -> str:
    if not _SAGA_ID_RE.fullmatch(saga_id):
        raise CeremonyRefsError(
            f"invalid saga_id {saga_id!r}: must be a single path-safe segment "
            "matching [A-Za-z0-9][A-Za-z0-9._-]* (e.g. issue-635)"
        )
    return saga_id


def ceremony_base_path(repo_root: Path, saga_id: str) -> Path:
    """Path to the per-saga ceremony-base sidecar (KTD4) — same directory as
    ``merge_expectation.json`` / ``rollback_manifest.json`` / ``opened_resources.json``."""
    return repo_root / SAGAS_DIR / _validate_saga_id(saga_id) / CEREMONY_BASE_SIDECAR_NAME


def read_ceremony_base(repo_root: Path, saga_id: str) -> str:
    """The recorded ceremony base branch, or ``""`` when no sidecar exists.

    An absent sidecar is not an error here (a ceremony that predates this wiring
    legitimately has none) — it simply means this rung cannot answer, and
    ``resolve_ceremony_refs`` names it among the exhausted sources rather than
    substituting a guess."""
    path = ceremony_base_path(repo_root, saga_id)
    if not path.exists():
        return ""
    with open(path, encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise CeremonyRefsError(
                f"{CEREMONY_BASE_SIDECAR_NAME} at {path} is not valid JSON: {exc}"
            ) from exc
    if not isinstance(data, dict):
        raise CeremonyRefsError(
            f"{CEREMONY_BASE_SIDECAR_NAME} at {path} is not a JSON object: {data!r}"
        )
    return str(data.get("base") or "")


def write_ceremony_base(
    repo_root: Path,
    saga_id: str,
    base: str,
    *,
    recorded_by: str,
    now: str | None = None,
) -> Path:
    """Record this ceremony's base branch to the per-saga sidecar (KTD4).

    Rewritable rather than write-once: the base is re-recorded by whichever site
    learns it authoritatively, and a later write with the same value must be a no-op
    in effect. Atomic replace (the ``merge_watcher._write_sidecar`` idiom) so a crash
    mid-write can never leave a torn base for a destructive path to read."""
    if not base:
        raise CeremonyRefsError(
            f"refusing to record an empty ceremony base for saga {saga_id!r}; "
            "an empty base would make the ladder's rung 2 answer with nothing"
        )
    path = ceremony_base_path(repo_root, saga_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "base": base,
        "recorded_at": now or datetime.now(UTC).isoformat(),
        "recorded_by": recorded_by,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def resolve_default_branch(repo_root: Path, runner: Callable[..., Any] | None = None) -> str:
    """The repository's default branch, resolved — never the hardcoded literal
    ``"main"`` (KTD5).

    ``git symbolic-ref refs/remotes/origin/HEAD`` first (local, no network, and the
    ref git itself maintains), then ``gh repo view --json defaultBranchRef``. Both
    failing raises: replacing one hardcoded ``main`` with another hardcoded ``main``
    moves the bug rather than fixing it, and this repo family already contains repos
    whose default branch is not the ceremony's base."""
    tried: list[str] = []

    symbolic = _run(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        cwd=repo_root,
        runner=runner,
        check=False,
    )
    if getattr(symbolic, "returncode", 1) == 0:
        value = (getattr(symbolic, "stdout", "") or "").strip()
        prefix = "refs/remotes/origin/"
        name = value[len(prefix) :] if value.startswith(prefix) else ""
        if name:
            return name
        tried.append(f"git symbolic-ref refs/remotes/origin/HEAD (unparseable output {value!r})")
    else:
        tried.append(
            "git symbolic-ref refs/remotes/origin/HEAD "
            f"(exit {getattr(symbolic, 'returncode', 'unknown')}: "
            f"{(getattr(symbolic, 'stderr', '') or '').strip()})"
        )

    repo_view = _run(
        ["gh", "repo", "view", "--json", "defaultBranchRef"],
        cwd=repo_root,
        runner=runner,
        check=False,
    )
    if getattr(repo_view, "returncode", 1) == 0:
        raw = (getattr(repo_view, "stdout", "") or "").strip()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            tried.append(f"gh repo view --json defaultBranchRef (invalid JSON: {exc})")
        else:
            ref = payload.get("defaultBranchRef") if isinstance(payload, dict) else None
            name = str((ref or {}).get("name") or "") if isinstance(ref, dict) else ""
            if name:
                return name
            tried.append(
                f"gh repo view --json defaultBranchRef (no defaultBranchRef.name in {raw!r})"
            )
    else:
        tried.append(
            "gh repo view --json defaultBranchRef "
            f"(exit {getattr(repo_view, 'returncode', 'unknown')}: "
            f"{(getattr(repo_view, 'stderr', '') or '').strip()})"
        )

    raise CeremonyRefsError(
        "cannot resolve the repository default branch; refusing to assume 'main' "
        "(KTD5 — a hardcoded default is the same class of guess this resolver removes). "
        "Sources tried: " + "; ".join(tried)
    )


def _manifest_head_branch(repo_root: Path, saga_id: str) -> str:
    """The head branch from the opened-resource manifest's ``ceremony-branch:`` entry
    (rung 2's head source), or ``""`` when the manifest carries none.

    ``_register_branch`` writes exactly one such entry per pushed branch at push time
    and never re-stamps it. When more than one exists (a ceremony that pushed under
    two names), still-open entries win over closed ones and the most recently opened
    wins within that pool, with the resource id as a stable tie-break — so the answer
    is deterministic rather than dict-order dependent."""
    entries = ship_teardown.read_manifest(repo_root, saga_id)
    candidates = [
        (resource_id, entry)
        for resource_id, entry in entries.items()
        if entry.get("kind") == "branch" and entry.get("ref")
    ]
    if not candidates:
        return ""
    still_open = [item for item in candidates if not item[1].get("closed_at")]
    pool = still_open or candidates
    pool.sort(key=lambda item: (str(item[1].get("opened_at") or ""), item[0]))
    return str(pool[-1][1]["ref"])


def resolve_ceremony_refs(
    saga: Mapping[str, Any],
    *,
    repo_root: Path,
    runner: Callable[..., Any] | None = None,
) -> CeremonyRefs:
    """Resolve this ceremony's head and base refs from ceremony-scoped evidence,
    walking KTD2's ladder and refusing rather than guessing when it is exhausted.

    Never reads ``saga["branch"]`` — not as a rung, not as a fallback, not as a
    tie-break. That field is the defect (issue #635): it is re-stamped from
    ``git branch --show-current`` on every save, so on a leaf-into-outcome ceremony
    whose last tick happened after ``checkout_main`` it holds the PR **base**, and a
    destructive path consuming it deletes the base branch."""
    tried: list[str] = []

    # Rung 1 — the PR itself.
    pr_refs = saga.get("pr_refs") or []
    if pr_refs:
        pr_number = _pr_number(str(pr_refs[-1]))
        view = _run(
            ["gh", "pr", "view", pr_number, "--json", "headRefName,baseRefName"],
            cwd=repo_root,
            runner=runner,
            check=False,
        )
        if getattr(view, "returncode", 1) == 0:
            raw = (getattr(view, "stdout", "") or "").strip()
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError as exc:
                tried.append(
                    f"gh pr view {pr_number} --json headRefName,baseRefName (invalid JSON: {exc})"
                )
            else:
                pr_head = str(payload.get("headRefName") or "") if isinstance(payload, dict) else ""
                pr_base = str(payload.get("baseRefName") or "") if isinstance(payload, dict) else ""
                if pr_head and pr_base:
                    return CeremonyRefs(head=pr_head, base=pr_base, source=CEREMONY_REFS_SOURCE_PR)
                tried.append(
                    f"gh pr view {pr_number} --json headRefName,baseRefName "
                    f"(incomplete payload {raw!r})"
                )
        else:
            tried.append(
                f"gh pr view {pr_number} --json headRefName,baseRefName "
                f"(exit {getattr(view, 'returncode', 'unknown')}: "
                f"{(getattr(view, 'stderr', '') or '').strip()})"
            )
    else:
        tried.append("saga pr_refs (empty — no PR to ask; open_pr has not run)")

    # Rung 2 — the local, never-re-stamped ceremony evidence.
    saga_id = str(saga.get("saga_id") or "")
    if not saga_id:
        tried.append("opened_resources.json + ceremony_base.json (saga carries no saga_id)")
        raise CeremonyRefsError(_refs_refusal(tried))

    try:
        head = _manifest_head_branch(repo_root, saga_id)
    except ship_teardown.ShipTeardownError as exc:
        head = ""
        tried.append(f"opened_resources.json ceremony-branch: entry (unreadable: {exc})")
    else:
        if not head:
            tried.append(
                "opened_resources.json ceremony-branch: entry "
                f"(no kind='branch' resource registered for saga {saga_id!r})"
            )
    base = read_ceremony_base(repo_root, saga_id)
    if not base:
        tried.append(
            f"{CEREMONY_BASE_SIDECAR_NAME} sidecar "
            f"(absent or empty at {ceremony_base_path(repo_root, saga_id)})"
        )
    if head and base:
        return CeremonyRefs(head=head, base=base, source=CEREMONY_REFS_SOURCE_MANIFEST)

    # Rung 3 — refuse. saga["branch"] is deliberately not consulted here (R7).
    raise CeremonyRefsError(_refs_refusal(tried))


def _refs_refusal(tried: Sequence[str]) -> str:
    return (
        "cannot resolve this ceremony's head/base refs from ceremony-scoped evidence; "
        "refusing to fall back to the saga's rolling 'branch' field (issue #635, R7). "
        "Sources tried: " + "; ".join(tried)
    )


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


def _remote_branch_exists(
    repo_root: Path, branch: str, *, runner: Callable[..., Any] | None
) -> bool:
    """Best-effort check of whether ``branch`` already exists on ``origin`` BEFORE
    this ceremony pushes it — feeds the rollback manifest's ``remote_created`` flag
    (R6) so ``ship_undo.py``'s ``_undo_commit`` never deletes a remote branch that
    predates the ceremony."""
    result = _run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
        cwd=repo_root,
        runner=runner,
        check=False,
    )
    return getattr(result, "returncode", 1) == 0


def _push_and_record_commit_fields(
    repo_root: Path, *, runner: Callable[..., Any] | None
) -> dict[str, Any]:
    """Push the current branch and return the rollback-manifest fields (R6) the
    ``commit`` transition contributes — ``branch``, ``head_sha``, and
    ``remote_created``. Shared by ``_do_commit`` and the front-loaded ``start()``
    path, which both complete the ``commit`` transition."""
    branch = current_branch(repo_root, runner=runner)
    existed_before = _remote_branch_exists(repo_root, branch, runner=runner)
    _run(["git", "push", "-u", "origin", branch], cwd=repo_root, runner=runner)
    head_sha = _run(["git", "rev-parse", "HEAD"], cwd=repo_root, runner=runner).stdout.strip()
    return {"branch": branch, "head_sha": head_sha, "remote_created": not existed_before}


def _do_commit(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> dict[str, Any]:
    """Push the current branch. The scaffold commit itself already exists — from
    ``/work``'s Phase 1.4 mint (KTD4) or from the operator's own commits — this
    transition's job is making sure it is on the remote. Returns the rollback-
    manifest fields (R6) for this transition.

    Register-on-open (R1/KTD9): the plain ``run`` flow's push site — the branch is
    'opened' here, so it lands on the opened-resource manifest for teardown to account
    (``start()`` is the front-loaded counterpart)."""
    fields = _push_and_record_commit_fields(repo_root, runner=runner)
    _register_branch(saga, fields["branch"], repo_root=repo_root, opened_by="commit")
    return fields


def _do_open_pr(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> dict[str, Any]:
    """Open a PR, or — if the front-loaded ``start`` mode already opened a draft PR
    (R7) — flip that existing draft ready instead of opening a second one. Either
    path records the merge-watcher expectation baseline (R3) right after the PR
    carries the HEAD that will actually be merged, and returns the rollback-
    manifest fields (R6) for this transition."""
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
        # force=True: this may be re-baselining over the sidecar `start()` already
        # wrote (KTD7's re-baseline path is exactly this — commits pushed after
        # start() moved HEAD past what was recorded then) or the very first record
        # if the ceremony never front-loaded via start().
        merge_watcher.record(
            saga_id=saga["saga_id"],
            pr_number=pr_number,
            repo_root=repo_root,
            force=True,
            runner=runner,
        )
        return {"pr_number": pr_number, "branch": current_branch(repo_root, runner=runner)}
    branch = current_branch(repo_root, runner=runner)
    # No PR exists yet — this ceremony has no recorded base (issue #635, R5). The
    # explicit base is the dynamically resolved repo default branch, never the
    # literal "main" (KTD5).
    base = resolve_default_branch(repo_root, runner=runner)
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
        ["gh", "pr", "create", "--head", branch, "--base", base, "--fill", "--body", body],
        cwd=repo_root,
        runner=runner,
    )
    pr_number = result.stdout.strip().rsplit("/", 1)[-1]
    # Register-on-open (R1/KTD9): the PR this transition just created lands on the
    # opened-resource manifest; _do_merge closes it once the merge lands.
    _register_pr(saga, pr_number, repo_root=repo_root, opened_by="open_pr")
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
    merge_watcher.record(
        saga_id=saga["saga_id"],
        pr_number=pr_number,
        repo_root=repo_root,
        force=True,
        runner=runner,
    )
    return {"pr_number": pr_number, "branch": branch}


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
) -> dict[str, Any]:
    """Squash-merge the ceremony PR and record the rollback-manifest fields (R6) for
    this transition.

    Both SHA probes read the PR's **resolved base** ref, never the literal
    ``refs/heads/main`` (issue #635, R6/KTD1). On a leaf-into-outcome PR the old
    hardcoded probe recorded the *default branch's* tip as ``merge_sha`` — and that
    sha is perfectly reachable, so ``ship_undo._undo_merge``'s ``SHA_UNREACHABLE``
    guard never fires: ``git revert --no-edit <sha>`` succeeds against an unrelated
    healthy commit on the default branch and gets pushed.

    A safe undo needs BOTH halves, and this function is only the first: recording the
    right sha (here, R6) and applying it to the right branch
    (``ship_undo._undo_merge``, R12, which used to revert on the literal ``main``
    whatever the ceremony's base was). The ``SHA_UNREACHABLE`` guard is an existence
    probe and catches neither — a wrong-but-reachable sha and a right sha reverted on
    the wrong branch both sail past it. That is why the resolved base is also returned
    below: ``ship_undo.append_entry`` records it on the merge entry so the undo path
    can target the same branch this merge landed on without a ``gh`` round trip.

    The returned key stays ``pre_merge_main_sha`` deliberately (R6): it is a keyword
    argument of ``ship_undo.append_entry``, it is referenced by name across the ceremony
    and undo test suites, and ``ship_undo.py``'s module docstring records it as
    audit-only forensic context that ``undo()`` never consumes programmatically —
    renaming it changes a cross-module signature on the undo path for zero behavioral
    gain. (No reference count is quoted here on purpose: any such number is stale the
    moment a test is added, and R13 exists because counts previously quoted in this
    docstring were wrong.)"""
    pr_number = _current_pr_number(saga, repo_root=repo_root, runner=runner)
    base = resolve_ceremony_refs(saga, repo_root=repo_root, runner=runner).base
    base_ref = "refs/heads/" + base
    pre_merge_main_sha = _run(
        ["git", "ls-remote", "origin", base_ref], cwd=repo_root, runner=runner
    ).stdout.split()[0]
    _run(["gh", "pr", "merge", pr_number, "--squash"], cwd=repo_root, runner=runner)
    merge_sha = _run(
        ["git", "ls-remote", "origin", base_ref], cwd=repo_root, runner=runner
    ).stdout.split()[0]
    # Close-on-close (KTD9): the merge landed the PR, so the draft_pr manifest entry
    # this ceremony opened is now closed, evidenced by the squash-merge sha.
    _close_if_registered(
        saga,
        _pr_resource_id(pr_number),
        repo_root=repo_root,
        evidence=f"merged: {merge_sha}",
    )
    return {
        "pr_number": pr_number,
        "branch": saga.get("branch"),
        "base": base,
        "pre_merge_main_sha": pre_merge_main_sha,
        "merge_sha": merge_sha,
    }


def _do_checkout_main(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> dict[str, Any]:
    """Check out this ceremony's resolved BASE branch (issue #635, R4) — never the
    literal ``"main"``.

    The returned ``branch`` deliberately stays ``saga.get("branch")``, NOT the
    resolved base — do not "fix" this. That value becomes the ``checkout_main``
    rollback-manifest entry's ``branch``, consumed by
    ``ship_undo._restore_pre_ceremony_checkout`` (``ship_undo.py``), whose contract is
    restoring the operator's PRE-CEREMONY checkout (the saga's own branch), not the
    branch this transition just checked out. Returning the resolved base instead would
    make ``current == branch`` true immediately after this transition runs and turn
    that undo step into a permanent silent no-op."""
    base = resolve_ceremony_refs(saga, repo_root=repo_root, runner=runner).base
    _run(["git", "checkout", base], cwd=repo_root, runner=runner)
    return {"branch": saga.get("branch")}


def _do_pull(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> dict[str, Any]:
    _run(["git", "pull"], cwd=repo_root, runner=runner)
    return {"branch": saga.get("branch")}


def _do_branch_delete(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> dict[str, Any]:
    """Delete the ceremony's **head** branch, local and origin, and close its manifest
    entry.

    The target is resolved ONCE from ceremony-scoped evidence (issue #635, R1/R3/KTD1)
    and that single value drives the ``git rev-parse``, the ``git branch -d``, the
    ``git push origin --delete``, **and** ``_branch_resource_id()`` for the manifest
    close. ``saga["branch"]`` is never consulted: it is re-stamped from
    ``git branch --show-current`` on every ``saga.py save``, so on a leaf-into-outcome
    ceremony whose last tick landed after ``checkout_main`` it holds the PR *base* —
    which is how the live incident deleted ``outcome/norns-next-horizon`` local and
    origin. Deriving the delete target and the manifest key independently from that
    same wrong field is also why the teardown ledger silently diverged: the close
    addressed ``ceremony-branch:<base>``, an id that was never registered, and
    ``_close_if_registered`` no-ops on unknown ids by design. One resolved value makes
    that divergence unrepresentable.

    The empty/``main`` guard below stays as defense in depth — the resolver already
    refuses to answer with an empty ref, but a destructive path keeps its own floor."""
    refs = resolve_ceremony_refs(saga, repo_root=repo_root, runner=runner)
    branch = refs.head
    if not branch or branch == "main":
        raise TransitionFailedError(
            f"refusing to delete branch {branch!r}; resolved ceremony head looks wrong "
            f"(resolution source: {refs.source})"
        )
    head_sha = _run(["git", "rev-parse", branch], cwd=repo_root, runner=runner).stdout.strip()
    _run(["git", "branch", "-d", branch], cwd=repo_root, runner=runner)
    _run(["git", "push", "origin", "--delete", branch], cwd=repo_root, runner=runner, check=False)
    # Close-on-close (KTD9): the branch this ceremony opened is now deleted, evidenced
    # by the head sha it carried at deletion (also the resurrection target for undo).
    _close_if_registered(
        saga,
        _branch_resource_id(branch),
        repo_root=repo_root,
        evidence=f"deleted head: {head_sha}",
    )
    return {"branch": branch, "head_sha": head_sha}


def _teardown_ceremony_summary(saga: Mapping[str, Any], *, repo_root: Path) -> dict[str, Any]:
    """Build the ``ceremony`` block the receipt records (KTD5): what shipped — the PR
    ref, the branch, the final transition, and (best-effort) the squash-merge sha pulled
    from the rollback manifest's ``merge`` entry. A missing merge sha is not fatal (a
    task-kind ceremony that never merged still tears down and mints a receipt)."""
    pr_refs = saga.get("pr_refs") or []
    summary: dict[str, Any] = {
        "pr": pr_refs[-1] if pr_refs else "",
        "branch": saga.get("branch") or "",
        "final_transition": "teardown",
    }
    try:
        for entry in ship_undo.read_manifest(repo_root, str(saga["saga_id"])):
            if entry.get("transition") == "merge" and entry.get("merge_sha"):
                summary["merge_sha"] = entry["merge_sha"]
                break
    except ship_undo.ShipUndoError:
        pass
    return summary


def _scratch_ref_contained(ref: str, repo_root: Path) -> bool:
    """True only when a scratch ref resolves strictly INSIDE a sanctioned root (the
    system tempdir or the repo itself). ``register`` stores refs verbatim, so an
    absolute or ``..``-bearing ref would otherwise be honored by ``rmtree`` — the
    security-review F2 deletion-safety gap. A root itself is never removable."""
    target = os.path.realpath(ref)
    for root in (os.path.realpath(tempfile.gettempdir()), os.path.realpath(str(repo_root))):
        if root and target.startswith(root + os.sep):
            return True
    return False


def _teardown_attempt_closes(
    saga: Mapping[str, Any],
    report: ship_teardown.ReconcileReport,
    *,
    repo_root: Path,
    runner: Callable[..., Any] | None,
) -> None:
    """Best-effort authorized close of the ceremony's own still-open resources (KTD9),
    so a ceremony that legitimately opened a merged worktree or a scratch dir can reach
    a clean teardown without operator intervention.

    * scratch — remove the directory, then close the manifest entry with evidence.
    * worktree — route through ``ship_teardown.reclaim`` (the certificate-gated,
      merged+clean-only single sanctioned removal primitive, U3); close each manifest
      entry whose worktree ``reclaim`` actually removed. An unmerged/dirty/gated worktree
      is left in place by ``reclaim`` and stays open — the re-reconcile then HALTs on it,
      which is the point (teardown never force-closes what it cannot safely remove).

    Only ``open`` entries are touched; a ``discrepancy`` (marked closed but still alive)
    is a different failure the operator must resolve, never silently re-closed here."""
    saga_id = str(saga["saga_id"])
    open_worktrees = [
        e for e in report.entries if e.status == ship_teardown.STATUS_OPEN and e.kind == "worktree"
    ]
    open_scratch = [
        e for e in report.entries if e.status == ship_teardown.STATUS_OPEN and e.kind == "scratch"
    ]

    for entry in open_scratch:
        if not _scratch_ref_contained(entry.ref, repo_root):
            # Refuse to rmtree a ref outside the sanctioned scratch roots (security
            # review F2): the entry stays open, so the re-reconcile HALTs naming it —
            # teardown never deletes an uncontained path on the manifest's say-so.
            continue
        path = Path(entry.ref)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            ship_teardown.close(
                repo_root, saga_id, entry.resource_id, evidence=f"scratch removed: {entry.ref}"
            )

    if open_worktrees:
        reclaim_report = ship_teardown.reclaim(repo_root, runner=runner)
        removed = {os.path.realpath(e.path) for e in reclaim_report.removed}
        for entry in open_worktrees:
            if os.path.realpath(entry.ref) in removed:
                ship_teardown.close(
                    repo_root,
                    saga_id,
                    entry.resource_id,
                    evidence="reclaimed via ship_teardown.reclaim",
                )


def _do_teardown(
    saga: Mapping[str, Any], *, repo_root: Path, runner: Callable[..., Any] | None
) -> dict[str, Any]:
    """The terminal gate (issue #347, R3/R4/KTD3). Reconcile the opened-resource
    manifest against reality; if anything is still open, attempt an authorized close of
    the ceremony's own resources and reconcile again. A non-zero closing count raises
    ``ship_receipt.TeardownBlockedError`` naming every blocker — and because this raises
    from inside ``_RUNNERS[upcoming]``, it lands BEFORE ``run()``'s ``ship_undo.append_entry``
    and ``saga.py save``, so the ledger is provably unadvanced (the #526/#346 refusal
    shape). A zero count mints the immutable receipt (``ship_receipt.mint``, write-once)
    and returns its path in ``extra``."""
    saga_id = str(saga["saga_id"])
    report = ship_teardown.reconcile(repo_root, saga_id, runner=runner)
    if not report.clean:
        _teardown_attempt_closes(saga, report, repo_root=repo_root, runner=runner)
        report = ship_teardown.reconcile(repo_root, saga_id, runner=runner)
    if not report.clean:
        # Raised before append_entry + save (see run()): ledger provably unadvanced.
        raise ship_receipt.TeardownBlockedError(saga_id, report)
    receipt_path = ship_receipt.mint(
        repo_root, saga_id, report, _teardown_ceremony_summary(saga, repo_root=repo_root)
    )
    return {"branch": saga.get("branch"), "receipt_path": str(receipt_path)}


_RUNNERS: Mapping[str, Callable[..., Mapping[str, Any] | None]] = {
    "commit": _do_commit,
    "open_pr": _do_open_pr,
    "request_review": _do_request_review,
    "merge": _do_merge,
    "checkout_main": _do_checkout_main,
    "pull": _do_pull,
    "branch_delete": _do_branch_delete,
    "teardown": _do_teardown,
}


def _pr_number(pr_ref: str) -> str:
    """``pr_refs`` entries are stored as ``#123`` or a full URL; extract the number."""
    return pr_ref.rsplit("/", 1)[-1].lstrip("#")


# Transitions whose operator confirmation must name a target as well as the transition
# (issue #635, KTD6/R8). ``{#ship-ceremony-operator-gate-526}``'s own "Revisit when"
# clause anticipated exactly this: "A transition is added whose confirmation needs an
# argument of its own … then the flag grows into a typed confirmation payload rather
# than a name match." ``branch_delete`` is that transition — the operator is authorizing
# the deletion of a specific branch, so the confirmation carries the branch. Every other
# transition keeps the bare grammar unchanged.
CONFIRMATION_TARGET_TRANSITIONS: frozenset[str] = frozenset({"branch_delete"})


def _parse_operator_confirmation(value: str) -> tuple[str, str | None]:
    """Split ``--operator-confirmed`` into (transition, target).

    ``"merge"`` -> ``("merge", None)``; ``"branch_delete:outcome/demo"`` ->
    ``("branch_delete", "outcome/demo")``. Only the FIRST colon separates, so a branch
    name containing a colon survives intact. A trailing colon with nothing after it
    carries no target and reads as bare — it must refuse with the resolved target named,
    not squeak through as a target of ``""``."""
    name, _, target = value.partition(":")
    return name, (target or None)


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
    operator_confirmed: str | None = None,
    acknowledge_hazard: Sequence[str] | None = None,
    undo: bool = False,
    runner: Callable[..., Any] | None = None,
) -> str:
    """Execute exactly the next unrun transition and record it. Returns a
    human-readable status line; raises on ambiguity or transition failure.

    R1/R3/KTD2-KTD4: when the upcoming transition is ``always_operator``-tier
    (looked up via ``TRANSITION_TIERS``, never a hardcoded name list), the caller
    must pass ``operator_confirmed`` naming that exact transition — a bare call, or
    one naming a different transition, refuses before ``_RUNNERS[upcoming]`` is
    invoked and before any ``saga.py save``, so the ledger is provably unadvanced.

    Issue #635 KTD6/R8: for the transitions in ``CONFIRMATION_TARGET_TRANSITIONS``
    (``branch_delete``) the confirmation must also name the target —
    ``branch_delete:<branch>`` — and that branch must equal the head
    ``resolve_ceremony_refs()`` resolves. A bare ``branch_delete`` refuses with the
    resolved target printed, so the operator's next invocation carries a value they
    have actually seen. Every other transition keeps the bare grammar, and passing a
    target to one of them refuses rather than being ignored.

    ``undo=True`` (KTD6) forks to ``ship_undo.undo()`` immediately after saga
    resolution — BEFORE the mismatch check and the always_operator gate above, so
    ``--operator-confirmed undo`` (KTD5) can never trip the forward-transition
    mismatch rule against whatever the upcoming *forward* transition happens to be.

    KTD2: after the operator-confirmation gate and before ``_RUNNERS[upcoming]``
    dispatch and the ``saga.py save``, this consults two more preflights: a hazard
    scan (``ceremony_hazards.detect()``, refusing on any unacknowledged finding —
    R1/R2/KTD3) and, for ``merge`` specifically, the merge-watcher's point-in-time
    ``validate()`` (R4, refusing on a missing expectation per KTD8 or a named
    divergence). Both refuse before dispatch and before save, the same
    ledger-unadvanced proof shape as the always_operator gate above.
    """
    saga = resolve_saga(repo_root=repo_root, issue_ref=issue_ref, saga_id=saga_id, runner=runner)

    if undo:
        return ship_undo.undo(
            saga, repo_root=repo_root, operator_confirmed=operator_confirmed, runner=runner
        )

    upcoming = next_transition(saga.get("ceremony_transition", ""))
    if upcoming is None:
        return "already shipped — all ceremony transitions complete"

    confirmed_transition: str | None = None
    confirmed_target: str | None = None
    if operator_confirmed is not None:
        confirmed_transition, confirmed_target = _parse_operator_confirmation(operator_confirmed)

    if confirmed_transition is not None and confirmed_transition != upcoming:
        # KTD4: the mismatch rule is uniform across tiers — refuse even when the
        # upcoming transition is itself reversible, so a mispredicted ledger
        # position always surfaces instead of confirmation silently "spilling"
        # onto a step the caller did not name. #635/KTD6 changed the operand, not the
        # rule: this compares the parsed transition NAME rather than the raw string, so
        # a qualified confirmation naming the wrong transition still refuses here with
        # the identical message. One narrow output change follows from that and is
        # deliberate: ``merge:x`` with ``merge`` upcoming used to hit this mismatch
        # branch (whole-string compare) and now falls through to the "does not take a
        # confirmation target" refusal below, which is the accurate diagnosis. Both
        # refuse; only the wording moved. Unreachable from the CLI before this change
        # (``choices=`` rejected the colon form outright), reachable via the Python API.
        raise OperatorConfirmationError(
            f"--operator-confirmed {operator_confirmed!r} does not match the upcoming "
            f"transition {upcoming!r}; confirmation must name the exact transition being run"
        )

    # KTD6/R8 (issue #635): ``branch_delete`` confirms a TARGET, not just a transition.
    # Resolving here — before the hazard scan, before ``_RUNNERS[upcoming]`` dispatch and
    # before the ``saga.py save`` — keeps every refusal below on the ledger-unadvanced
    # side of the ceremony, and hands ``detect()`` the branch that would actually be
    # deleted. That injection only makes the R2 hazard a genuine two-source comparison
    # when the resolver answered on rung 2; on rung 1 head and base share one PR record
    # and the hazard is inert by construction. ``_probe_branch_delete_targets_base``
    # documents the rung split in full.
    resolved_head: str | None = None
    if upcoming in CONFIRMATION_TARGET_TRANSITIONS:
        refs = resolve_ceremony_refs(saga, repo_root=repo_root, runner=runner)
        resolved_head = refs.head
        qualified = f"--operator-confirmed {upcoming}:{refs.head}"
        provenance = f"head resolved from {refs.source}"
        if confirmed_transition is None:
            raise OperatorConfirmationError(
                f"transition {upcoming!r} is tier={CeremonyTier.ALWAYS_OPERATOR!r} and requires "
                f"operator confirmation naming the branch it will delete; re-run with "
                f"{qualified} ({provenance})"
            )
        if confirmed_target is None:
            raise OperatorConfirmationError(
                f"--operator-confirmed {upcoming} must name the branch this transition will "
                f"delete (issue #635, KTD6) — confirming a bare transition name authorizes a "
                f"deletion target the operator never saw; re-run with {qualified} ({provenance})"
            )
        if confirmed_target != refs.head:
            raise OperatorConfirmationError(
                f"--operator-confirmed {upcoming}:{confirmed_target} names a branch that is not "
                f"this ceremony's resolved head {refs.head!r} ({provenance}); re-run with "
                f"{qualified}"
            )
    else:
        if confirmed_target is not None:
            raise OperatorConfirmationError(
                f"transition {upcoming!r} does not take a confirmation target; pass a bare "
                f"--operator-confirmed {upcoming}. Only "
                f"{', '.join(sorted(CONFIRMATION_TARGET_TRANSITIONS))} confirms a named target "
                "(issue #635, KTD6)"
            )
        if (
            TRANSITION_TIERS[upcoming] == CeremonyTier.ALWAYS_OPERATOR
            and confirmed_transition is None
        ):
            raise OperatorConfirmationError(
                f"transition {upcoming!r} is tier={CeremonyTier.ALWAYS_OPERATOR!r} and requires "
                f"operator confirmation; re-run with --operator-confirmed {upcoming}"
            )

    hazards = ceremony_hazards.detect(
        saga, upcoming, repo_root, runner, resolved_head=resolved_head
    )
    acknowledged_ids = set(acknowledge_hazard or ())
    unacknowledged = [
        h for h in hazards if not (h.acknowledgeable and h.hazard_id in acknowledged_ids)
    ]
    if unacknowledged:
        lines = [
            f"- {h.hazard_id} ({h.transition}): {h.message}\n  remedy: {h.remedy}"
            for h in unacknowledged
        ]
        raise HazardRefusedError(
            f"transition {upcoming!r} refused — {len(unacknowledged)} unacknowledged "
            "hazard(s):\n" + "\n".join(lines)
        )

    if upcoming == "merge":
        try:
            merge_watcher.validate(saga_id=saga["saga_id"], repo_root=repo_root, runner=runner)
        except merge_watcher.MergeWatcherError as exc:
            raise MergePreflightError(str(exc)) from exc

    extra = _RUNNERS[upcoming](saga, repo_root=repo_root, runner=runner) or {}

    ship_undo.append_entry(
        repo_root=repo_root,
        saga_id=saga["saga_id"],
        transition=upcoming,
        tier=TRANSITION_TIERS[upcoming],
        branch=extra.get("branch"),
        # Only ``_do_merge`` returns a base; recorded so ``ship_undo._undo_merge``
        # reverts on the branch this ceremony merged into (issue #635, R12).
        base=extra.get("base"),
        head_sha=extra.get("head_sha"),
        pr_number=extra.get("pr_number"),
        merge_sha=extra.get("merge_sha"),
        pre_merge_main_sha=extra.get("pre_merge_main_sha"),
        remote_created=extra.get("remote_created", False),
    )

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
    confirmation_note = ", operator-confirmed" if confirmed_transition == upcoming else ""
    receipt_note = ""
    if extra.get("receipt_path"):
        receipt_note = f"; ship receipt minted at {extra['receipt_path']}"
    return (
        f"ran transition {upcoming!r} (tier={TRANSITION_TIERS[upcoming]}"
        f"{confirmation_note}){receipt_note}"
    )


def start(
    *,
    repo_root: Path,
    issue_ref: str,
    base: str | None = None,
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

    ``base`` (issue #635, R5/KTD5): the draft PR's base branch, explicit or resolved
    via ``resolve_default_branch`` when omitted — never the literal ``"main"``. The
    resolved value is recorded to the per-saga ceremony-base sidecar (KTD4) so later
    transitions (``checkout_main``, ``merge``, ``branch_delete``) can resolve this
    ceremony's base from local evidence, without a ``gh pr view`` round trip, via
    ``resolve_ceremony_refs``'s rung 2.
    """
    saga = resolve_saga(repo_root=repo_root, issue_ref=issue_ref, runner=runner)
    if saga.get("ceremony_transition") or saga.get("pr_refs"):
        raise ShipCeremonyError(
            "ceremony already in progress for this saga "
            f"(ceremony_transition={saga.get('ceremony_transition')!r}, "
            f"pr_refs={saga.get('pr_refs')!r}); 'start' is front-loaded-mode-only and "
            "must not run against a saga that already has state — use 'run' to continue"
        )
    commit_fields = _push_and_record_commit_fields(repo_root, runner=runner)
    branch = commit_fields["branch"]
    # Register-on-open (R1/KTD9): the front-loaded push site — the branch is 'opened'
    # here, the counterpart to _do_commit's registration on the plain run flow.
    _register_branch(saga, branch, repo_root=repo_root, opened_by="start")

    resolved_base = base or resolve_default_branch(repo_root, runner=runner)
    write_ceremony_base(repo_root, str(saga["saga_id"]), resolved_base, recorded_by="start")

    plan_path = saga.get("plan_path") or ""
    body = f"Plan: {plan_path}" if plan_path else ""
    _run(
        [
            "gh",
            "pr",
            "create",
            "--draft",
            "--head",
            branch,
            "--base",
            resolved_base,
            "--fill",
            "--body",
            body,
        ],
        cwd=repo_root,
        runner=runner,
    )
    pr_view = _run(["gh", "pr", "view", branch, "--json", "number"], cwd=repo_root, runner=runner)
    pr_number = json.loads(pr_view.stdout)["number"]
    # Register-on-open (R1/KTD9): the draft PR start() just opened; _do_open_pr's
    # existing-draft path later flips it ready without re-registering, and _do_merge
    # closes it once the merge lands.
    _register_pr(saga, pr_number, repo_root=repo_root, opened_by="start")

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
    # R3: record the merge-watcher baseline right away, before any poll loop
    # exists — this front-loaded path is one of the two record sites (the other
    # is _do_open_pr's existing-draft branch, which re-baselines with force=True
    # after any commits pushed since this call).
    merge_watcher.record(
        saga_id=saga["saga_id"],
        pr_number=pr_number,
        repo_root=repo_root,
        runner=runner,
    )
    # R6: start() completes the "commit" transition (ceremony_transition is set to
    # "commit" above) even though _do_commit itself never runs on this path — the
    # rollback manifest needs an entry here too, or a ceremony killed right after
    # start() would leave ship_undo with no record of the branch this call pushed.
    ship_undo.append_entry(
        repo_root=repo_root,
        saga_id=saga["saga_id"],
        transition="commit",
        tier=TRANSITION_TIERS["commit"],
        branch=commit_fields["branch"],
        head_sha=commit_fields["head_sha"],
        remote_created=commit_fields["remote_created"],
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


_OPERATOR_CONFIRMED_NAMES: tuple[str, ...] = (*TRANSITIONS, "undo")


def _operator_confirmed_arg(value: str) -> str:
    """argparse ``type`` for ``--operator-confirmed``.

    Replaces the flag's former ``choices=`` (issue #635/KTD6): the value may now carry a
    ``:<target>`` suffix, which ``choices`` cannot express. The palette check itself is
    unchanged in strength and in shape — an off-palette transition name is still
    argparse's error (usage + exit 2, "invalid choice"), never the gate's, and the
    target's own validation stays in ``run()`` where the resolved head is known."""
    name, _target = _parse_operator_confirmation(value)
    if name not in _OPERATOR_CONFIRMED_NAMES:
        raise argparse.ArgumentTypeError(
            f"invalid choice: {name!r} (choose from "
            + ", ".join(repr(choice) for choice in _OPERATOR_CONFIRMED_NAMES)
            + "; branch_delete also requires a ':<branch>' target)"
        )
    return value


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
    p_run.add_argument(
        "--operator-confirmed",
        default=None,
        type=_operator_confirmed_arg,
        metavar="TRANSITION[:TARGET]",
        help=(
            "name the always_operator-tier transition (merge, branch_delete) you are "
            "authorizing; required when the upcoming transition is always_operator-tier. "
            "branch_delete additionally requires the branch it will delete "
            "(--operator-confirmed branch_delete:<branch>, issue #635/KTD6); a bare "
            "'branch_delete' refuses and prints the resolved target. "
            "Pass 'undo' (KTD5) when --undo's in-scope plan reverses merge/branch_delete."
        ),
    )
    p_run.add_argument(
        "--acknowledge-hazard",
        action="append",
        default=None,
        choices=ceremony_hazards.HAZARD_REGISTRY,
        help=(
            "repeatable; acknowledge a detected hazard by id to unblock its transition "
            "(KTD3). Non-acknowledgeable hazards (merge_not_landed, "
            "branch_delete_targets_base) ignore this."
        ),
    )
    p_run.add_argument(
        "--undo",
        action="store_true",
        help=(
            "revert this ceremony from its rollback manifest instead of running the next "
            "forward transition (KTD6); forks before the forward gate and mismatch checks"
        ),
    )

    p_start = sub.add_parser("start", help="front-loaded mode: push branch, open draft PR")
    p_start.add_argument("--issue-ref", required=True, help="owner/repo#N")
    p_start.add_argument(
        "--base",
        default=None,
        help=(
            "explicit base branch for the draft PR; default: resolve_default_branch() "
            "(issue #635, KTD5) — never the literal 'main'"
        ),
    )

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
            print(
                run(
                    repo_root=repo_root,
                    issue_ref=args.issue_ref,
                    saga_id=args.saga_id,
                    operator_confirmed=args.operator_confirmed,
                    acknowledge_hazard=args.acknowledge_hazard,
                    undo=args.undo,
                )
            )
        elif args.command == "start":
            print(start(repo_root=repo_root, issue_ref=args.issue_ref, base=args.base))
        elif args.command == "install":
            print(install(repo_root=repo_root, force=getattr(args, "force", False)))
        elif args.command == "uninstall":
            print(uninstall(repo_root=repo_root))
        else:  # pragma: no cover - argparse enforces valid choices
            parser.error(f"unknown command {args.command!r}")
            return 2
    except (
        ShipCeremonyError,
        ceremony_hazards.HazardError,
        merge_watcher.MergeWatcherError,
        ship_undo.ShipUndoError,
        ship_teardown.ShipTeardownError,
        ship_receipt.ShipReceiptError,
    ) as exc:
        print(f"ship_ceremony: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
