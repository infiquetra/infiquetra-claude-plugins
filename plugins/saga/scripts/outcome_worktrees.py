#!/usr/bin/env python3
"""Durable per-sub-outcome worktree lifecycle + the worktree-removed terminal (U7).

A **sub-outcome** (a ``child_spec_ref`` node, ``Node.is_outcome``) runs autonomously and concurrently
with its siblings, so each gets **one durable, named, owner-tagged git worktree** — shared across all of
that child's leaves, **not one-per-leaf** (R15). Plain code leaves run in the ambient outcome worktree
(the branch the operator/coordinator is already in) and are not managed here; only the autonomous
sub-outcomes need an isolated worktree so two concurrent children cannot collide on the working tree.

Three invariants this module enforces structurally:

* **Bounded proliferation (R15).** A hard cap on concurrent live worktrees: an N-sub-outcome outcome can
  never exhaust a solo machine's disk/inodes — past the cap, provisioning **defers** (the sub-outcome
  waits for a slot) rather than spawning an (N+1)th worktree. Heavy dependency installs are **shared**
  across an outcome's sibling worktrees via one ``shared_install_ref`` recorded on every entry.
* **git is the liveness source of truth (the U6 lesson).** Whether a worktree still exists is read from
  the injected :class:`WorktreeOps` (``git worktree list`` / path existence), never inferred from our
  own registry — so a worktree removed **out-of-band** is detected. Only a *definite* absence reaps or
  terminates; a transient ``git`` failure degrades safe (treat as present, never falsely terminate, R34).
* **The worktree-removed negative terminal (R32, the one U6 deferred).** A sub-outcome whose worktree
  vanished out-of-band reaches a **defined** terminal state — ``rejected`` (sticky, cascades like a block
  via R22 ``blocked_subtree``) — so its dependents do not hang on a dead worktree, exactly as U6 models a
  closed-unmerged PR / deleted branch.

The registry (``<store>/worktrees.json``) records the owner tag + shared-install ref + branch/path that
``git worktree list`` cannot carry; it is written read-modify-write by the single writer the caller
discipline provides (``advance`` holds one tick per outcome, R13). The lease fence that once backed
that single-writer guarantee was retired with the fleet broker (#677/U3) — the registry entry is now
the reap authority itself, and abandoned worktrees are reclaimed by the operator through the manual
path in ``plugins/saga/references/worktree-reclamation.md``.

House pattern (mirrors ``outcome_merge`` / ``outcome_github``): pure functions over an injected
:class:`WorktreeOps` adapter so the whole lifecycle is unit-testable with no real ``git worktree``; the
real adapter wires ``git`` with an injectable runner; no I/O at import.
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 — git CLI only, fixed argv, no shell
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome_orchestrator  # noqa: E402  (after the sys.path shim, by design)
import outcome_spec  # noqa: E402
import outcome_store  # noqa: E402

# How many autonomous sub-outcome worktrees may be live at once (R15 bound). Past this, provisioning
# defers — a deterministic page-and-wait, never an unbounded fan-out that exhausts a solo machine.
WORKTREE_CAP = 4

# The negative terminal a vanished worktree reaches (R32). ``rejected`` (sticky, cascades) mirrors U6's
# branch-deleted/closed-PR model — the working state is gone, so the node does not silently retry.
WORKTREE_REMOVED_STATE = "rejected"


class WorktreeError(ValueError):
    """A worktree lifecycle operation violated an invariant (bad id, ops failure surfaced loudly)."""


@dataclass
class WorktreeOps:
    """The git-worktree operations the lifecycle needs — injected so it is testable with no real git.

    Every method is duck-simple so a fake can stand in. ``exists`` is the **liveness oracle** (git owns
    the truth, the U6 lesson): it returns a definite present/absent, and the real adapter degrades an
    ambiguous ``git`` failure to **present** (never falsely terminate a live sub-outcome, R34).
    """

    add: Callable[[str, str], bool]  # (path, branch) -> created?
    remove: Callable[[str], bool]  # (path) -> removed?  (idempotent: already-gone is success)
    exists: Callable[[str], bool]  # (path) -> definitely present? (ambiguity degrades to True)
    list_paths: Callable[[], list[str]]  # the live worktree paths git knows about


# ---------------------------------------------------------------------------
# Deterministic names + paths (R13 namespacing — the path doubles as a return address)
# ---------------------------------------------------------------------------


def worktree_name(outcome_id: str, subplot_id: str) -> str:
    """A stable, collision-free worktree/branch name for a sub-outcome (namespaced by both ids)."""
    o = outcome_store._safe_name(outcome_id, what="outcome_id")
    s = outcome_store._safe_name(subplot_id, what="subplot_id")
    return f"saga-outcome-{o}-{s}"


def worktrees_root(repo_root: Path) -> Path:
    """Where managed worktrees live: ``<repo>/.saga-worktrees`` (git-ignored, never committed)."""
    return Path(repo_root) / ".saga-worktrees"


def worktree_path(repo_root: Path, outcome_id: str, subplot_id: str) -> Path:
    """The deterministic on-disk path for a sub-outcome's durable worktree (R13 return address)."""
    o = outcome_store._safe_name(outcome_id, what="outcome_id")
    s = outcome_store._safe_name(subplot_id, what="subplot_id")
    return worktrees_root(repo_root) / o / s


def shared_install_ref(repo_root: Path, outcome_id: str) -> str:
    """One shared heavy-install location reused by every sibling worktree of an outcome (R15).

    A single path per outcome (``<repo>/.saga-worktrees/<outcome>/_shared-install``) recorded on every
    worktree entry so the real provisioner can symlink/point a heavy ``node_modules`` / venv at it
    instead of re-installing per worktree. This module records + propagates the *policy* (one ref, reused
    by all siblings); the physical link is the adapter's job.
    """
    o = outcome_store._safe_name(outcome_id, what="outcome_id")
    return str(worktrees_root(repo_root) / o / "_shared-install")


# ---------------------------------------------------------------------------
# Registry (<store>/worktrees.json) — the owner/branch/shared-install facts git can't carry
# ---------------------------------------------------------------------------


def _registry_path(store: Any) -> Path:
    return Path(store.root) / "worktrees.json"


def read_registry(store: Any) -> dict[str, dict[str, Any]]:
    """The {subplot_id -> entry} map; an absent/malformed registry reads as empty (never fatal, KTD15)."""
    data = outcome_store._read_json_or_quarantine(
        _registry_path(store), quarantine_dir=store.quarantine_dir
    )
    if not data:
        return {}
    entries = data.get("worktrees", {})
    return {str(k): dict(v) for k, v in entries.items() if isinstance(v, dict)}


def read_registry_strict(store: Any) -> dict[str, dict[str, Any]]:
    """Read the registry without invoking the normal quarantine/repair path.

    Settlement reconciliation is observational: even malformed input must not move, rewrite, or
    create files. A malformed registry therefore fails visibly and leaves recovery to the worktree
    lifecycle's mutation owner.
    """
    path = _registry_path(store)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise WorktreeError(f"cannot read worktree registry without repair: {exc}") from exc
    if not isinstance(data, dict):
        raise WorktreeError("worktree registry must be a JSON object")
    if set(data) != {"worktrees"}:
        raise WorktreeError("worktree registry requires exactly the 'worktrees' field")
    entries = data["worktrees"]
    if not isinstance(entries, dict):
        raise WorktreeError("worktree registry 'worktrees' must be an object")
    invalid = [str(key) for key, value in entries.items() if not isinstance(value, dict)]
    if invalid:
        raise WorktreeError(
            "worktree registry entries must be objects: " + ", ".join(sorted(invalid))
        )
    return {str(k): dict(v) for k, v in entries.items()}


def _write_registry(store: Any, entries: dict[str, dict[str, Any]]) -> None:
    outcome_store._atomic_write(
        _registry_path(store), json.dumps({"worktrees": entries}, indent=2, sort_keys=True) + "\n"
    )


def register(store: Any, subplot_id: str, entry: dict[str, Any]) -> None:
    """Record/overwrite a sub-outcome's worktree entry (read-modify-write under the coordinator lease)."""
    outcome_store._safe_name(subplot_id, what="subplot_id")
    entries = read_registry(store)
    entries[subplot_id] = dict(entry)
    _write_registry(store, entries)


def registered_entry_strict(
    store: Any,
    subplot_id: str,
    *,
    expected_outcome_id: str | None = None,
) -> dict[str, Any] | None:
    """Read one registry entry without repair, proving it binds the expected outcome.

    The broker-free reap preflight (#677/U3): an absent entry returns ``None``; a present entry is
    returned verbatim after the outcome binding check. Registry corruption is surfaced, never
    repaired/quarantined — the ``lease`` field a pre-retirement entry may still carry is inert data,
    never read and never a reap blocker.
    """
    outcome_store._safe_name(subplot_id, what="subplot_id")
    entry = read_registry_strict(store).get(subplot_id)
    if entry is None:
        return None
    if expected_outcome_id is not None:
        outcome_id = entry.get("outcome_id")
        if not isinstance(outcome_id, str):
            raise WorktreeError("worktree registry entry lacks outcome_id")
        if outcome_id != expected_outcome_id:
            raise WorktreeError(
                f"worktree registry outcome {outcome_id!r} does not match "
                f"expected outcome {expected_outcome_id!r}"
            )
    return entry


def deregister(store: Any, subplot_id: str) -> None:
    """Drop a sub-outcome's worktree entry (idempotent — absent is fine)."""
    entries = read_registry(store)
    if subplot_id in entries:
        del entries[subplot_id]
        _write_registry(store, entries)


# ---------------------------------------------------------------------------
# Live-worktree accounting (git is the source of truth, cross-checked with the registry)
# ---------------------------------------------------------------------------


def live_worktrees(store: Any, ops: WorktreeOps) -> set[str]:
    """Subplot ids whose registered worktree path **still exists** per git (the liveness oracle).

    Reads existence from ``ops`` (git), NOT from the registry alone — a worktree removed out-of-band is
    therefore not counted as live (it frees a cap slot and is eligible for the removed-terminal).
    """
    live: set[str] = set()
    for sid, entry in read_registry(store).items():
        path = str(entry.get("path", ""))
        if path and ops.exists(path):
            live.add(sid)
    return live


def stale_worktree_debits(
    store: Any,
    ops: WorktreeOps,
    *,
    outcome_id: str,
) -> list[dict[str, Any]]:
    """Project registered-but-absent worktrees as read-only settlement debits (#351).

    This deliberately does not deregister, reap, append facts, or create files. The normal outcome
    worktree harvester remains the only mutation owner; ``reconcile --leaks`` consumes this view.
    """
    outcome_store._safe_name(outcome_id, what="outcome_id")
    debits: list[dict[str, Any]] = []
    for sid, entry in sorted(read_registry_strict(store).items()):
        path = str(entry.get("path", ""))
        if path and not ops.exists(path):
            debits.append(
                {
                    "dispatch_id": f"outcome:{outcome_id}:worktrees",
                    "unit_id": sid,
                    "attempt": 1,
                    "worktree": path,
                }
            )
    return debits


@dataclass
class WorktreeResult:
    """The outcome of an ``ensure_worktree`` call."""

    subplot_id: str
    state: str  # created / reused / capped / skipped-not-suboutcome
    path: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "subplot_id": self.subplot_id,
            "state": self.state,
            "path": self.path,
            "reason": self.reason,
        }


def ensure_worktree(
    repo_root: Path,
    spec: Any,
    store: Any,
    node: Any,
    ops: WorktreeOps,
    *,
    owner: str,
    cap: int = WORKTREE_CAP,
    at: str = "",
) -> WorktreeResult:
    """Ensure exactly one durable worktree for a sub-outcome node (R15). Idempotent + cap-bounded.

    Only ``is_outcome`` nodes (``child_spec_ref`` set) are managed — a plain leaf returns
    ``skipped-not-suboutcome`` (it runs in the ambient outcome worktree). If the sub-outcome already has
    a **live** registered worktree, it is **reused** (the "not one-per-leaf, reused across its leaves"
    guarantee). Otherwise, if the live count is already at ``cap``, provisioning **defers**
    (``capped``) — never an (N+1)th worktree. Else a worktree is created (named + owner-tagged + sharing
    the outcome's one ``shared_install_ref``) and registered.
    """
    sid = node.subplot_id
    if not node.is_outcome:
        return WorktreeResult(
            sid, "skipped-not-suboutcome", "", "plain leaf — uses ambient worktree"
        )

    path = str(worktree_path(repo_root, spec.outcome_id, sid))
    live = live_worktrees(store, ops)
    if sid in live:
        return WorktreeResult(
            sid, "reused", path, "durable worktree already live — reused across leaves"
        )

    # A registered-but-vanished entry must NOT block reuse: drop the stale record before re-creating.
    registry = read_registry(store)
    if sid in registry and not ops.exists(str(registry[sid].get("path", ""))):
        deregister(store, sid)

    if len(live) >= cap:
        return WorktreeResult(
            sid, "capped", path, f"worktree cap {cap} reached ({sorted(live)}) — defer + page (R15)"
        )

    branch = worktree_name(spec.outcome_id, sid)
    entry = {
        "path": path,
        "branch": branch,
        "owner": owner,
        "shared_install_ref": shared_install_ref(repo_root, spec.outcome_id),
        "at": at,
        "repo_root": str(Path(repo_root).resolve()),
        "outcome_id": spec.outcome_id,
    }
    # Persist the registry record BEFORE creating the physical worktree. If the process dies after
    # ``ops.add`` returns, a later harvest pass — or the operator's manual reclamation path
    # (#677/U3) — can still tell from the registry which paths we own. The reverse order can strand
    # an unregistered worktree.
    register(store, sid, entry)
    try:
        added = ops.add(path, branch)
    except Exception as add_exc:
        cleaned = reap_worktree(store, sid, ops)
        if not cleaned:
            raise WorktreeError(
                f"git worktree add raised for {sid!r}; registry entry retained for retry"
            ) from add_exc
        raise
    if not added:
        cleaned = reap_worktree(store, sid, ops)
        if not cleaned:
            raise WorktreeError(
                f"git worktree add failed for {sid!r} at {path}; registry entry retained for retry"
            )
        raise WorktreeError(f"git worktree add failed for {sid!r} at {path}")
    return WorktreeResult(sid, "created", path, "durable named+owned worktree provisioned (R15)")


def reap_worktree(store: Any, subplot_id: str, ops: WorktreeOps) -> bool:
    """Remove + deregister a sub-outcome's worktree on terminal/abandon (R15 reaping). Idempotent.

    Returns True if a worktree was reaped, False if there was nothing registered **or the removal
    failed** (a stuck/locked worktree that survives ``git worktree remove --force``). A failed removal
    KEEPS the registry entry so a later harvest pass retries it — deregistering a worktree that is still
    on disk would drop it from the cap accounting and leak it silently (the registry is the only record
    of which worktrees we own). ``ops.remove`` is idempotent for an already-gone path (that returns
    True), so reaping a vanished worktree still cleans the registry.

    Broker-free (#677/U3): the registry entry IS the reap authority. Single-writer safety comes from
    the caller (one ``advance`` tick per outcome), not from a lease fence — the accepted loss of
    runtime fencing applies here as everywhere else in the retirement. A ``lease`` receipt written by
    a pre-retirement run is inert data: never read, never a reap blocker.
    """
    entry = registered_entry_strict(store, subplot_id)
    if entry is None:
        return False
    if not ops.remove(str(entry.get("path", ""))):
        return False  # removal failed -> keep the entry so a later pass retries (no silent leak)
    deregister(store, subplot_id)
    return True


# ---------------------------------------------------------------------------
# The advance processor: reap terminals + detect removed worktrees (the U7 live consumer)
# ---------------------------------------------------------------------------


def _record_terminal(store: Any, sid: str, state: str, reason: str) -> None:
    """Record a NEGATIVE terminal completion event at a fresh attempt, idempotently (U6 pattern)."""
    existing = outcome_store.read_completion_events(store, sid)
    if any(e.state == state for e in existing):
        return
    attempt = max((e.attempt for e in existing), default=0) + 1
    outcome_store.write_completion_event(
        store,
        outcome_store.CompletionEvent(
            subplot_id=sid,
            state=state,
            idempotency_key=f"worktree-removed:{sid}:{state}",
            attempt=attempt,
            payload={"reason": reason},
        ),
    )


def harvest_worktrees(
    spec: Any,
    store: Any,
    ops: WorktreeOps,
) -> dict[str, Any]:
    """One worktree-reconcile pass for ``advance`` (R15 reap + R32 worktree-removed terminal + R22).

    Three derived-on-read sweeps over the registry, each cross-checked against git (the liveness oracle):

    1. **Orphan** — a registry entry whose node is **no longer in the spec** (pruned/elaborated away by
       another path) is reaped + deregistered, so a stranded worktree never holds a cap slot forever.
    2. **Reap** the worktree of any sub-outcome that has reached a **terminal** state (its work is done
       or dead — free the disk). A *failed* removal keeps the entry (retried next pass), never a silent
       leak.
    3. **Detect removed**: a still-registered worktree whose path git says is **definitely absent**,
       whose node is **non-terminal**, reaches the ``rejected`` terminal (R32) and its downstream subtree
       cascades (R22 ``blocked_subtree``). A transient ``ops.exists`` failure degrades to *present*
       (handled in the real adapter), so a flake never falsely terminates a live sub-outcome (R34).

    Runs single-writer per outcome (one ``advance`` tick at a time, R13); the registry
    read-modify-writes and the terminal records rely on that caller discipline now that the lease
    fence is retired (#677/U3). Returns ``{reaped, removed, orphaned, reap_failed, cascade_paused}``.
    """
    # Lazy import to avoid a cycle (outcome imports this module).
    import outcome as outcome_engine

    states = outcome_engine.derive_states(spec, store)
    registry = read_registry(store)
    reaped: list[str] = []
    removed: list[str] = []
    orphaned: list[str] = []
    reap_failed: list[str] = []

    for sid, entry in sorted(registry.items()):
        node = spec.node_by_id(sid)
        if node is None:
            # The node left the spec (pruned/elaborated away) but its worktree is still registered ->
            # reap the orphan so it does not hold a cap slot / leak disk forever.
            if reap_worktree(store, sid, ops):
                orphaned.append(sid)
            else:
                reap_failed.append(sid)
            continue
        live_state = states.get(sid, "")
        path = str(entry.get("path", ""))
        present = ops.exists(path) if path else False

        if live_state in outcome_spec.TERMINAL_STATES:
            # Terminal sub-outcome -> reap its worktree, success or negative alike. A failed removal
            # keeps the entry (retried next pass) rather than silently leaking it.
            if reap_worktree(store, sid, ops):
                reaped.append(sid)
            else:
                reap_failed.append(sid)
            continue
        if not present:
            # Non-terminal but the worktree vanished out-of-band -> the R32 removed terminal + cascade.
            if not reap_worktree(store, sid, ops):
                reap_failed.append(sid)
                continue
            _record_terminal(
                store, sid, WORKTREE_REMOVED_STATE, "worktree removed out-of-band (R32)"
            )
            removed.append(sid)

    cascade = sorted(outcome_orchestrator.blocked_subtree(spec, set(removed)))
    return {
        "reaped": reaped,
        "removed": removed,
        "orphaned": orphaned,
        "reap_failed": reap_failed,
        "cascade_paused": cascade,
    }


def provision_pending(
    repo_root: Path,
    spec: Any,
    store: Any,
    ops: WorktreeOps,
    *,
    owner: str,
    cap: int = WORKTREE_CAP,
    at: str = "",
) -> dict[str, Any]:
    """Ensure a worktree for every **dispatched** sub-outcome that lacks one (cap-bounded, R15).

    Only acts on sub-outcomes whose live derived state is ``dispatched`` (handed to a backend, still
    running) — a not-yet-dispatched sub-outcome has no work to isolate, and a terminal one is reaped by
    :func:`harvest_worktrees`, not provisioned. Cap enforcement is inside :func:`ensure_worktree` and is
    re-read after each create, so a single pass never overshoots the cap. Returns ``{provisioned,
    deferred}`` (``deferred`` = sub-outcomes waiting for a cap slot — a page, not a silent drop).
    """
    import outcome as outcome_engine

    states = outcome_engine.derive_states(spec, store)
    provisioned: list[str] = []
    deferred: list[str] = []
    for node in spec.nodes:
        if not node.is_outcome or states.get(node.subplot_id) != "dispatched":
            continue
        result = ensure_worktree(
            repo_root,
            spec,
            store,
            node,
            ops,
            owner=owner,
            cap=cap,
            at=at,
        )
        if result.state == "created":
            provisioned.append(node.subplot_id)
        elif result.state == "capped":
            deferred.append(node.subplot_id)
    return {"provisioned": provisioned, "deferred": deferred}


# ---------------------------------------------------------------------------
# Real git adapter (degraded-to-safe — git is the liveness oracle, the U6 lesson)
# ---------------------------------------------------------------------------


def _run_git(
    args: list[str], *, cwd: Path, runner: Callable[..., Any] | None = None
) -> tuple[int, str, str]:
    run = runner if runner is not None else subprocess.run
    try:
        result = run(  # nosec B603 — fixed argv, no shell
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "", str(exc)
    rc = getattr(result, "returncode", 1)
    return (
        rc,
        (getattr(result, "stdout", "") or "").strip(),
        (getattr(result, "stderr", "") or "").strip(),
    )


def git_worktree_ops(repo_root: Path, *, runner: Callable[..., Any] | None = None) -> WorktreeOps:
    """The real adapter wiring ``git worktree`` (degraded-to-safe so git is the liveness oracle).

    **Path canonicalization is load-bearing.** ``git worktree list --porcelain`` emits **absolute,
    symlink-resolved (realpath)** paths, while the registry stores the path built from ``repo_root`` —
    which the ``/outcome`` CLI defaults to ``.`` (relative) and which may sit under a symlink (e.g. macOS
    ``/tmp`` -> ``/private/tmp``). A naive string compare would read **every live worktree as ABSENT**,
    which silently breaks BOTH the R15 cap (a never-tripping cap -> unbounded fan-out) AND R34 (a live
    sub-outcome falsely driven to the ``rejected`` terminal). So both sides are reduced to the same
    canonical form: ``realpath(join(resolve(repo_root), path))`` — a relative registry path is resolved
    against the resolved repo root, an absolute one is realpath'd, and git's paths are realpath'd too.

    ``exists`` still degrades an ambiguous git failure to **present** (True) so a transient ``git`` blip
    never falsely fires the worktree-removed terminal (R34) — only a *definite* absence (the canonical
    path is not in ``git worktree list``) reads as gone.
    """
    root = Path(repo_root).resolve()

    def _canon(path: str) -> str:
        # os.path.join ignores ``root`` when ``path`` is already absolute, so this handles both a
        # relative registry path (resolved against the repo root) and an absolute one — then realpath
        # collapses symlinks to match git's porcelain form exactly.
        return os.path.realpath(os.path.join(str(root), path)) if path else ""

    def _listed_canon(out: str) -> set[str]:
        return {
            _canon(line[len("worktree ") :])
            for line in out.splitlines()
            if line.startswith("worktree ")
        }

    def _add(path: str, branch: str) -> bool:
        Path(_canon(path)).parent.mkdir(parents=True, exist_ok=True)
        rc, _out, _err = _run_git(
            ["worktree", "add", "-b", branch, _canon(path)], cwd=root, runner=runner
        )
        return rc == 0

    def _remove(path: str) -> bool:
        rc, _out, _err = _run_git(
            ["worktree", "remove", "--force", _canon(path)], cwd=root, runner=runner
        )
        # An already-removed worktree is success (idempotent reaping), not a failure.
        return True if rc == 0 else not Path(_canon(path)).exists()

    def _list() -> list[str]:
        rc, out, _err = _run_git(["worktree", "list", "--porcelain"], cwd=root, runner=runner)
        return sorted(_listed_canon(out)) if rc == 0 else []

    def _exists(path: str) -> bool:
        rc, out, _err = _run_git(["worktree", "list", "--porcelain"], cwd=root, runner=runner)
        if rc != 0:
            # git unreadable -> degrade to PRESENT (never falsely terminate a live sub-outcome, R34).
            return True
        return _canon(path) in _listed_canon(out)

    return WorktreeOps(add=_add, remove=_remove, exists=_exists, list_paths=_list)


def _git_common_dir(repo_root: Path, *, runner: Callable[..., Any] | None = None) -> Path | None:
    rc, out, _err = _run_git(["rev-parse", "--git-common-dir"], cwd=Path(repo_root), runner=runner)
    if rc != 0 or not out:
        return None
    common = Path(out)
    return common if common.is_absolute() else (Path(repo_root) / common).resolve()


def reclaim_candidates(
    repo_root: Path, *, runner: Callable[..., Any] | None = None
) -> list[dict[str, str]]:
    """Report-only inventory of outcome worktrees an operator may want to reclaim (#677/U3).

    Enumerates every outcome store's worktree registry under the repo's git-common-dir (the same
    census shape team teardown uses), cross-checks each registered path against ``git worktree
    list``, and additionally reports on-disk paths under ``.saga-worktrees/`` that no registry
    claims. **Automatic** reclamation of abandoned outcome worktrees was retired with the lease
    broker — this inventory only REPORTS; removal stays an explicit operator act (procedure in
    ``plugins/saga/references/worktree-reclamation.md``).

    States: ``live`` (git still lists the path — reclaiming abandons that sub-outcome's work and
    its next harvest pass reaches the ``rejected`` worktree-removed terminal), ``path-absent``
    (registered but git no longer lists it — the next harvest pass settles the entry on its own),
    ``unregistered`` (on disk under ``.saga-worktrees/`` but claimed by no registry — a stranded
    leftover, safe to remove after confirming no run needs it).
    """
    root = Path(repo_root).resolve()
    ops = git_worktree_ops(root, runner=runner)

    def _canon(path: str) -> str:
        return os.path.realpath(os.path.join(str(root), path)) if path else ""

    candidates: list[dict[str, str]] = []
    claimed: set[str] = set()
    common = _git_common_dir(root, runner=runner)
    if common is not None:
        for registry_path in sorted(common.glob("saga-outcomes/*/worktrees.json")):
            try:
                data = json.loads(registry_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            entries = data.get("worktrees", {}) if isinstance(data, dict) else {}
            if not isinstance(entries, dict):
                continue
            for sid, entry in sorted(entries.items()):
                if not isinstance(entry, dict):
                    continue
                path = str(entry.get("path", ""))
                if not path:
                    continue
                candidates.append(
                    {
                        "outcome_id": str(entry.get("outcome_id", "")),
                        "subplot_id": str(sid),
                        "path": path,
                        "registry": str(registry_path),
                        "state": "live" if ops.exists(path) else "path-absent",
                    }
                )
                claimed.add(_canon(path))

    managed_root = worktrees_root(root)
    if managed_root.is_dir():
        for outcome_dir in sorted(p for p in managed_root.iterdir() if p.is_dir()):
            for candidate in sorted(p for p in outcome_dir.iterdir() if p.is_dir()):
                if candidate.name == "_shared-install":
                    continue  # the shared heavy-install ref, not a worktree
                if os.path.realpath(str(candidate)) in claimed:
                    continue
                candidates.append(
                    {
                        "outcome_id": outcome_dir.name,
                        "subplot_id": candidate.name,
                        "path": str(candidate),
                        "registry": "",
                        "state": "unregistered",
                    }
                )
    candidates.sort(key=lambda item: (item["state"], item["outcome_id"], item["subplot_id"]))
    return candidates


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Outcome worktree lifecycle (U7) + the operator reclamation inventory (#677/U3)."
    )
    parser.add_argument("--cap", type=int, default=WORKTREE_CAP)
    parser.add_argument(
        "--reclaim-list",
        action="store_true",
        help="report-only inventory of reclaimable outcome worktrees (never removes anything)",
    )
    parser.add_argument(
        "--repo-root", default=".", help="repository root for --reclaim-list (default: cwd)"
    )
    args = parser.parse_args(argv)
    if args.reclaim_list:
        print(
            json.dumps(
                {"candidates": reclaim_candidates(Path(args.repo_root))},
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    print(
        json.dumps(
            {
                "worktree_cap": args.cap,
                "removed_terminal": WORKTREE_REMOVED_STATE,
                "policy": "one durable named+owned worktree per sub-outcome, reused across its leaves; "
                "cap-bounded (defer past cap); reap on terminal; worktree-removed -> rejected+cascade; "
                "shared install ref across an outcome's worktrees; abandoned worktrees reclaimed "
                "by the operator (references/worktree-reclamation.md)",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
