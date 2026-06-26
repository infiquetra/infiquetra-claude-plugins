#!/usr/bin/env python3
"""OutcomeOrchestrator reconcile engine + thin ``/outcome`` CLI (U3).

This is the coordinator runtime that sits on top of the spec (U1, structure) and the store (U2,
cache + completion + locks). It is a **level-triggered reconcile loop** (R29), not a long-lived
imperative process: every ``advance`` tick reconstructs live state from the durable store, advances
the ready frontier, **dispatches** non-gated leaves to their executors, and pages on exceptions —
holding no authoritative in-memory DAG, so it is crash-tolerant and host-agnostic (a local ``/loop``
session or a scheduled routine drives the repeats).

Two invariants this module enforces structurally:

* **The coordinator routes, it never executes** (R2/R3). ``advance`` only *dispatches* (hands a leaf
  off to a backend via an injected ``dispatcher`` and records it) and *harvests* (reads completion
  events). It never runs a leaf's work in the advance process — so a coordinator failure can never
  collapse the whole DAG into one inline context. The default dispatcher is record-only; real
  backends (team-execution, workflows, ``/goal``, …) arrive in U4/U9 as dispatcher implementations.
* **Status is derived on read** (R17/R29). There is no operator-writable status field. A node's live
  state is *computed* every call from the committed spec + completion events + dispatch records —
  never read from a stored scalar — so the cockpit physically cannot drift.

The ``/outcome`` surface is deliberately thin (KTD11, R16): ``start``, ``graph``, ``advance``,
``attend``, ``resume``, ``export``, ``import``, ``status``. Leaf work stays the native ``/resume
<leaf-saga-id>`` / ``/work`` / ``/code-review`` / ``/qa`` — there is no ``/outcome work``; ``attend``
just prints the native re-entry handoff (R16 altitude seam).

House pattern (mirrors ``outcome_spec`` / ``outcome_store`` / ``saga``): pure-ish functions over
explicit values, dependency-injected ``dispatcher`` / ``now`` / ``runner`` so the loop is unit-testable
offline with no real git repo, no backend, and no wall clock; no I/O at import.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Make sibling scripts importable when loaded by path (tests, CLI).
sys.path.insert(0, str(Path(__file__).resolve().parent))

# The backend dispatcher module owns the HALT contract (it is never run as ``__main__``, so there is
# exactly one ``BackendHaltError`` class regardless of how the engine is launched). The reconcile loop
# catches ``outcome_dispatcher.BackendHaltError`` per leaf. outcome_dispatcher does NOT import this
# module (it duck-types the request), so there is no import cycle.
import outcome_dispatcher  # noqa: E402
import outcome_spec  # noqa: E402  (after the sys.path shim, by design)
import outcome_store  # noqa: E402

# Where the canonical spec lives on the outcome's own branch (KTD1/R26). The committed spec is the
# structural source of truth; the store under the git-common-dir is its performance cache.
OUTCOMES_DIR = "docs/outcomes"

# Default coordinator-lease TTL (seconds): a tick that dies without releasing is reclaimable after
# this. The host drives ticks far more often than this, so a healthy loop always refreshes in time.
DEFAULT_LEASE_TTL = 900.0


class OutcomeError(ValueError):
    """An ``/outcome`` operation violated an invariant (bad id, missing spec, etc.)."""


# A dispatcher hands a ready leaf off to a backend and returns its leaf saga id. It MUST NOT run the
# leaf's work in-process (R3) — it records/launches and returns. The record-only default is the
# skeleton; U4/U9 supply real backend dispatchers with the same signature.
Dispatcher = Callable[["DispatchRequest"], str]


@dataclass(frozen=True)
class DispatchRequest:
    """Everything a backend needs to launch a leaf — passed to the injected dispatcher."""

    outcome_id: str
    subplot_id: str
    title: str
    backend: str
    repo_root: Path


def _default_dispatcher(req: DispatchRequest) -> str:
    """Record-only dispatch: mint a stable leaf saga id, run NOTHING (R3).

    Real execution backends (team-execution, cc-workflows-ultracode, ``/goal``, fork, subagent,
    manual) are dispatcher implementations that arrive in U4/U9. The skeleton just allocates the
    handoff address; the leaf is executed by its own native saga, never here.
    """
    return f"leaf-{req.outcome_id}-{req.subplot_id}"


def _append_ledger_once(store: Any, record: dict[str, Any]) -> bool:
    """Append a ledger record only if no record with the same ``(phase, key)`` already exists.

    The ``commit`` dispatch record is the dedup marker for SUCCESSFUL dispatch, but a HALTed or
    degrade-then-crashed leaf never writes a commit, so it is re-evaluated every tick. Without this, an
    attended leaf polling ``advance`` against a persistently-unavailable backend re-appends a ``halt``
    record on every tick (unbounded ledger growth), and a crash in the degrade->commit window
    double-lists the degradation. Deduping on ``(phase, key)`` (the ``import_bundle`` pattern) bounds
    both. Returns True if the record was appended, False if it was already present.
    """
    phase, key = record.get("phase"), record.get("key")
    for rec in outcome_store.read_ledger(store):
        if rec.get("phase") == phase and rec.get("key") == key:
            return False
    outcome_store.append_ledger(store, record)
    return True


def _default_holder() -> str:
    """A holder id UNIQUE to this advance invocation (pid + a monotonic nonce).

    The coordinator lease only excludes a *different* holder (same-holder acquire is a refresh). A
    constant holder would therefore let two concurrent / re-entrant advances both "acquire" and
    both dispatch the same leaf (R13 violated). A per-invocation unique id makes a concurrent
    advance a genuinely different holder, so it no-ops on the held lease as intended.
    """
    return f"coordinator-{os.getpid()}-{time.monotonic_ns()}"


# ---------------------------------------------------------------------------
# Spec placement + load/save on the outcome's branch
# ---------------------------------------------------------------------------


def spec_path(repo_root: Path, outcome_id: str) -> Path:
    return Path(repo_root) / OUTCOMES_DIR / _safe(outcome_id) / "outcome-spec.json"


def _safe(outcome_id: str) -> str:
    # Reuse the store's path-traversal guard so ids are validated identically everywhere.
    return outcome_store._safe_name(outcome_id, what="outcome_id")


def load_spec(repo_root: Path, outcome_id: str) -> outcome_spec.OutcomeSpec:
    path = spec_path(repo_root, outcome_id)
    try:
        spec = outcome_spec.OutcomeSpec.from_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OutcomeError(f"no outcome spec at {path} — run `outcome start` first") from exc
    spec.validate()
    return spec


def save_spec(repo_root: Path, spec: outcome_spec.OutcomeSpec) -> Path:
    """Persist the canonical spec (structure + decision-trail + cost) to the branch path.

    Writes the working-tree file only; the **git commit + push** to the outcome's own branch (the R26/R27
    cross-machine-durability step) is :func:`commit_spec`, run explicitly via ``/outcome commit`` or
    ``/outcome advance --persist`` — never silently per tick. node live-state stays derived-on-read (R17),
    so the branch history is not polluted with state churn.
    """
    spec.validate()
    path = spec_path(repo_root, spec.outcome_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(spec.to_json(), encoding="utf-8")
    return path


# The branches the spec must NEVER be committed to mid-run (R26: "the outcome's own branch, not main").
_PROTECTED_BRANCHES = frozenset({"main", "master"})


def _git(
    args: list[str], repo_root: Path, runner: Callable[..., Any] | None = None
) -> tuple[int, str, str]:
    """Run a ``git`` subcommand in ``repo_root``; ``(rc, stdout, stderr)``. ``runner`` injectable (tests)."""
    import subprocess  # nosec B404 — git CLI only, fixed argv, no shell

    run = runner if runner is not None else subprocess.run
    try:
        result = run(  # nosec B603 — fixed argv, no shell
            ["git", *args], cwd=str(repo_root), capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "", str(exc)
    return (
        getattr(result, "returncode", 1),
        (getattr(result, "stdout", "") or "").strip(),
        (getattr(result, "stderr", "") or "").strip(),
    )


def commit_spec(
    repo_root: Path,
    outcome_id: str,
    *,
    message: str = "",
    push: bool = False,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Commit the canonical outcome spec to the **outcome's own branch** (R26/R27 cross-machine durability).

    The spec artifact is canonical for structure + decision-trail + cost (R26); committing + pushing it to
    the outcome's branch is what lets a **different machine reconstruct the whole outcome by pulling the
    repo** (R27/F5) — load the committed spec, then re-harvest completion from GitHub (canonical), no
    dependence on the local cache. This is the **mechanism**; the *cadence* (how often it runs) is the
    operator's / `/loop`'s call (the deferred half of R26).

    **Refuses to commit to ``main``/``master``** (R26: "not main mid-run") so an outcome's structural churn
    never pollutes the default branch. A path-limited commit (only the spec file) leaves the operator's
    other working-tree changes untouched. Idempotent: a no-op when the spec is already committed.
    """
    branch = ""
    rc, out, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root, runner)
    if rc == 0:
        branch = out
    if branch in _PROTECTED_BRANCHES:
        raise OutcomeError(
            f"refusing to commit the {outcome_id!r} spec to {branch!r} — R26: the outcome spec lives on "
            f"its own branch (outcome/<slug>), never main mid-run. Switch to the outcome branch first."
        )
    path = spec_path(repo_root, outcome_id)
    rel = str(path)
    _git(["add", "--", rel], repo_root, runner)
    staged_rc, _o, _e = _git(["diff", "--cached", "--quiet", "--", rel], repo_root, runner)
    if staged_rc == 0:  # nothing staged -> the spec is already committed (idempotent no-op)
        return {"committed": False, "branch": branch, "pushed": False, "reason": "spec unchanged"}
    msg = message or f"chore(outcome): persist {outcome_id} spec"
    crc, _o, cerr = _git(["commit", "-m", msg, "--", rel], repo_root, runner)
    if crc != 0:
        raise OutcomeError(f"could not commit the {outcome_id!r} spec: {cerr}")
    pushed = False
    if push:
        prc, _po, _pe = _git(["push"], repo_root, runner)
        pushed = prc == 0
    return {"committed": True, "branch": branch, "pushed": pushed}


def _store(repo_root: Path, outcome_id: str, *, runner: Callable[..., Any] | None = None) -> Any:
    return outcome_store.Store.for_outcome(outcome_id, Path(repo_root), runner=runner).ensure()


# ---------------------------------------------------------------------------
# start / resume
# ---------------------------------------------------------------------------


def start(
    repo_root: Path,
    outcome_id: str,
    objective: str,
    nodes: list[dict[str, Any]] | None = None,
    *,
    runner: Callable[..., Any] | None = None,
) -> outcome_spec.OutcomeSpec:
    """Create the branch-local spec + its store. Idempotent only if no spec exists yet.

    ``nodes`` defaults to a minimal 2-node design->build DAG so the skeleton is usable immediately;
    the real graph is authored/decomposed via U7. Fails if a spec already exists (use ``resume``).
    """
    path = spec_path(repo_root, outcome_id)
    if path.exists():
        raise OutcomeError(f"outcome {outcome_id!r} already started ({path}); use `resume`")
    node_dicts = nodes if nodes is not None else _starter_nodes()
    spec = outcome_spec.OutcomeSpec.from_dict(
        {"outcome_id": outcome_id, "objective": objective, "nodes": node_dicts}
    )
    spec.validate()
    save_spec(repo_root, spec)
    _store(repo_root, outcome_id, runner=runner)  # materialize the cache tree
    return spec


def _starter_nodes() -> list[dict[str, Any]]:
    return [
        {"subplot_id": "design", "title": "Design", "kind": "non-code"},
        {"subplot_id": "build", "title": "Build", "kind": "code", "depends_on": ["design"]},
    ]


def resume(
    repo_root: Path, outcome_id: str, *, runner: Callable[..., Any] | None = None
) -> dict[str, Any]:
    """Reconstruct live status from the canonical spec + store — the spec always survives a cache wipe.

    The committed spec (on the branch) is canonical structure, so it always reloads after any cache
    loss. **Completion is a different facet**: in U3 completion events live ONLY in the cache, so a
    cache wipe currently *does* drop completion (a done leaf reverts to the frontier). The full R27
    "rebuild completion from GitHub" leg is U5 (`outcome_github`); until it lands, ``export`` is the
    durable completion checkpoint. ``resume`` recomputes the frontier from whatever completion truth
    survives (R27/R29) — lossless for structure today, lossless for completion once U5 reads GitHub.
    """
    spec = load_spec(repo_root, outcome_id)
    store = _store(repo_root, outcome_id, runner=runner)
    return status(repo_root, outcome_id, spec=spec, store=store)


# ---------------------------------------------------------------------------
# Derived live state (R17 — computed every read, never a stored status field)
# ---------------------------------------------------------------------------

# Live node states the coordinator derives (computed from completion events + dispatch records,
# never persisted). NOTE: ``Node.state`` on the committed spec is the AUTHORING-time declared state
# only — derive_states never reads it; live state comes solely from the store (R17). The negative
# terminals are surfaced (not masked as "dispatched") so the cockpit never shows a dead leaf as
# in-flight; the cascade/handling of those terminals is U6.
LIVE_READY = "ready"
LIVE_DISPATCHED = "dispatched"
LIVE_DONE = "done"
LIVE_BLOCKED = "blocked"


def _dispatch_records(store: Any) -> dict[str, str]:
    """subplot_id -> leaf_saga_id for every SETTLED dispatch (a ``commit`` record in the ledger).

    Keyed on the ``commit`` phase, not ``intent``: a dispatch is recorded intent -> effect -> commit,
    so a leaf whose intent was written but whose dispatch then failed (no commit) is NOT counted as
    dispatched here — it falls back to the frontier and is re-driven, and ``replay_pending`` flags its
    dangling intent. This makes the dedup durable AND a failed dispatch recoverable rather than stuck.
    """
    out: dict[str, str] = {}
    for rec in outcome_store.read_ledger(store):
        if rec.get("kind") == "dispatch" and rec.get("phase") == "commit":
            sid = str(rec.get("subplot_id", ""))
            if sid:
                out[sid] = str(rec.get("leaf_saga_id", ""))
    return out


def _terminal_state_map(store: Any) -> dict[str, str]:
    """subplot_id -> its terminal completion state (done/failed/rejected/stalled), latest attempt wins."""
    out: dict[str, str] = {}
    for node_id in outcome_store.completed_subplots(store, successful_only=False):
        events = outcome_store.read_completion_events(store, node_id)
        if events:
            out[node_id] = events[-1].state  # events sorted by attempt; latest is authoritative
    return out


def derive_states(spec: outcome_spec.OutcomeSpec, store: Any) -> dict[str, str]:
    """Compute each node's LIVE state from the spec + store — the load-bearing derived-on-read map.

    Precedence per node: a SUCCESS completion -> ``done``; any other terminal completion ->
    its actual negative terminal (``failed`` / ``rejected`` / ``stalled``) so a dead leaf is never
    mislabeled as in-flight; else a settled dispatch -> ``dispatched``; else in the ready frontier ->
    ``ready``; else ``blocked`` (an upstream is not yet done). No node's state is ever read from a
    stored scalar (R17) — ``Node.state`` on the spec is authoring-time-only and ignored here.
    """
    success = outcome_store.completed_subplots(store, successful_only=True)
    terminals = _terminal_state_map(store)
    dispatched = _dispatch_records(store)
    frontier = set(outcome_spec.ready_frontier(spec, success))
    states: dict[str, str] = {}
    for node in spec.nodes:
        sid = node.subplot_id
        if sid in success:
            states[sid] = LIVE_DONE
        elif sid in terminals:
            states[sid] = terminals[sid]  # negative terminal — surfaced, not masked
        elif sid in dispatched:
            states[sid] = LIVE_DISPATCHED
        elif sid in frontier:
            states[sid] = LIVE_READY
        else:
            states[sid] = LIVE_BLOCKED
    return states


def status(
    repo_root: Path,
    outcome_id: str,
    *,
    spec: outcome_spec.OutcomeSpec | None = None,
    store: Any | None = None,
) -> dict[str, Any]:
    """A computed cockpit snapshot — derived on read, never from a stored status field (R17)."""
    spec = spec if spec is not None else load_spec(repo_root, outcome_id)
    store = store if store is not None else _store(repo_root, outcome_id)
    states = derive_states(spec, store)
    counts: dict[str, int] = {}
    for st in states.values():
        counts[st] = counts.get(st, 0) + 1
    done = {sid for sid, st in states.items() if st == LIVE_DONE}
    return {
        "outcome_id": spec.outcome_id,
        "objective": spec.objective,
        "spec_revision": spec.spec_revision,
        "nodes": len(spec.nodes),
        "states": states,
        "counts": counts,
        # Derive the frontier from the SAME states map, not a separate success-only ready_frontier:
        # otherwise a negative-terminal (failed/rejected/stalled) node whose deps are satisfied would be
        # re-listed as dispatchable, contradicting its own `states` entry (the U8 cross-surface fix).
        "frontier": sorted(sid for sid, st in states.items() if st == LIVE_READY),
        "complete": len(done) == len(spec.nodes),
    }


# ---------------------------------------------------------------------------
# advance — the level-triggered reconcile tick (R29)
# ---------------------------------------------------------------------------


@dataclass
class AdvanceResult:
    dispatched: list[str] = field(default_factory=list)  # subplots handed to a backend this tick
    harvested: list[str] = field(
        default_factory=list
    )  # completions materialized from GitHub (U5/R10)
    halted: list[dict[str, Any]] = field(
        default_factory=list
    )  # HALT receipts (R5/R23 — backend down)
    merges: list[Any] = field(default_factory=list)  # per-tick auto-merge queue results (U6/R12)
    worktrees: list[Any] = field(
        default_factory=list
    )  # per-tick worktree reap/removed/provision (U7/R15/R32)
    liveness: list[Any] = field(default_factory=list)  # per-tick stalled-leaf reclaim (U9/R31)
    costs: list[Any] = field(
        default_factory=list
    )  # per-tick realized-cost rollup materialization (U10/R24)
    gated: list[str] = field(
        default_factory=list
    )  # ready leaves held back by the approval gate (U7/R20)
    degraded: list[dict[str, Any]] = field(
        default_factory=list
    )  # leaves degraded one rung autonomous+away (U9/R23)
    skipped_busy: bool = False  # coordinator lease held by another tick -> no-op (R13)
    ticks: int = 1
    status: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatched": self.dispatched,
            "harvested": self.harvested,
            "halted": self.halted,
            "merges": self.merges,
            "worktrees": self.worktrees,
            "liveness": self.liveness,
            "costs": self.costs,
            "gated": self.gated,
            "degraded": self.degraded,
            "skipped_busy": self.skipped_busy,
            "ticks": self.ticks,
            "status": self.status,
        }


def advance(
    repo_root: Path,
    outcome_id: str,
    *,
    loop: bool = False,
    max_ticks: int = 100,
    dispatcher: Dispatcher | None = None,
    harvester: Callable[[Any, Any], list[str]] | None = None,
    merge_processor: Callable[[Any, Any], Any] | None = None,
    worktree_processor: Callable[[Any, Any], Any] | None = None,
    liveness_processor: Callable[[Any, Any], Any] | None = None,
    cost_processor: Callable[[Any, Any], Any] | None = None,
    gate_factory: Callable[[Any, Any], Callable[[str], bool]] | None = None,
    available: Sequence[str] | None = None,
    attending: bool = True,
    holder: str | None = None,
    lease_ttl: float = DEFAULT_LEASE_TTL,
    now: Callable[[], float] = time.time,
    runner: Callable[..., Any] | None = None,
) -> AdvanceResult:
    """Run one (``loop=False``) or repeated (``loop=True``) reconcile ticks.

    A tick: acquire the coordinator lease under a per-invocation unique ``holder`` (a second
    concurrent / re-entrant ``advance`` is a different holder, so it no-ops on the held lease, R13);
    **harvest** GitHub-canonical completions into the cache (the optional ``harvester``, U5 — a
    code leaf's merged PR / a non-code leaf's closed issue becomes a completion event that unlocks the
    next Kahn layer, R10/R11); recompute the ready frontier; for each ready, not-yet-dispatched,
    not-completed leaf, take its per-subplot dispatch lock and **dispatch** it — never running the
    leaf's work here (R3); then return the derived status. Idempotent: a leaf with a settled
    (``commit``) dispatch record is skipped, so repeated ticks never double-dispatch. ``loop`` repeats
    until the frontier is empty or ``max_ticks``, which the host (`/loop`/cron) would otherwise drive.
    """
    holder = holder if holder is not None else _default_holder()
    dispatch = dispatcher if dispatcher is not None else _default_dispatcher
    spec = load_spec(repo_root, outcome_id)
    store = _store(repo_root, outcome_id, runner=runner)
    # The R20 approval gate is built from the loaded spec/store so it sees the CURRENT spec_revision —
    # a graph edit (which bumps the revision + re-closes the gate) is reflected on the next advance.
    dispatch_gate = gate_factory(spec, store) if gate_factory is not None else None

    if not outcome_store.acquire_coordinator(store, holder, lease_ttl, now=now):
        return AdvanceResult(
            skipped_busy=True, ticks=0, status=status(repo_root, outcome_id, spec=spec, store=store)
        )

    all_dispatched: list[str] = []
    all_halted: list[dict[str, Any]] = []
    all_harvested: list[str] = []
    all_gated: list[str] = []
    all_degraded: list[dict[str, Any]] = []
    merge_runs: list[Any] = []
    worktree_runs: list[Any] = []
    liveness_runs: list[Any] = []
    cost_runs: list[Any] = []
    ticks = 0
    try:
        while True:
            ticks += 1
            if merge_processor is not None:
                # Auto-merge clean PRs FIRST (under the held coordinator lease, so serialized
                # cross-process, R12/R13), then harvest reads the now-merged PRs as completions.
                merge_runs.append(merge_processor(spec, store))
            if harvester is not None:
                # Materialize GitHub-canonical completions BEFORE the frontier read so a leaf whose
                # PR just merged unlocks its dependents this same tick (R10/R11).
                all_harvested.extend(harvester(spec, store))
            if worktree_processor is not None:
                # Reap terminal sub-outcomes' worktrees + record the worktree-removed terminal (R32)
                # BEFORE the frontier read so a vanished worktree cascades this tick (R22/R15).
                worktree_runs.append(worktree_processor(spec, store))
            if liveness_processor is not None:
                # Reclaim any hung dispatched leaf as `stalled` (R31) BEFORE the frontier read so its
                # downstream cascade is reflected this tick (R22).
                liveness_runs.append(liveness_processor(spec, store))
            tick_dispatched, tick_halted, tick_gated, tick_degraded = _reconcile_once(
                repo_root,
                spec,
                store,
                dispatch,
                holder,
                lease_ttl,
                now,
                dispatch_gate=dispatch_gate,
                available=available,
                attending=attending,
            )
            all_dispatched.extend(tick_dispatched)
            all_halted.extend(tick_halted)
            all_gated.extend(tick_gated)
            all_degraded.extend(tick_degraded)
            if cost_processor is not None:
                # Materialize the realized-cost rollup into spec.cost_rollup AFTER dispatch/harvest so it
                # reflects this tick's completions (U10/R24). The U8 report renders spec.cost_rollup.
                cost_runs.append(cost_processor(spec, store))
            if not loop:
                break
            if not tick_dispatched:
                break  # quiescent: nothing new to dispatch this tick (HALTed/gated leaves wait)
            if ticks >= max_ticks:
                break
    finally:
        outcome_store.release_lease(store, outcome_store.COORDINATOR_LOCK, holder)

    return AdvanceResult(
        dispatched=all_dispatched,
        harvested=all_harvested,
        halted=all_halted,
        merges=merge_runs,
        worktrees=worktree_runs,
        liveness=liveness_runs,
        costs=cost_runs,
        gated=sorted(set(all_gated)),
        degraded=all_degraded,
        ticks=ticks,
        status=status(repo_root, outcome_id, spec=spec, store=store),
    )


def _reconcile_once(
    repo_root: Path,
    spec: outcome_spec.OutcomeSpec,
    store: Any,
    dispatch: Dispatcher,
    holder: str,
    lease_ttl: float,
    now: Callable[[], float],
    *,
    dispatch_gate: Callable[[str], bool] | None = None,
    available: Sequence[str] | None = None,
    attending: bool = True,
) -> tuple[list[str], list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    """One level-triggered pass: dispatch every ready, not-yet-settled leaf exactly once.

    Returns ``(dispatched, halted, gated, degraded)``. Each dispatch is recorded **intent -> effect ->
    commit** (the store's replay protocol): the intent is written BEFORE the backend is invoked, so a
    crash/append-failure after the effect leaves a durable dangling intent that ``replay_pending``
    surfaces and the next reconcile re-drives. The ``commit`` is the durable dedup marker (and carries an
    ``at`` timestamp for the U9 liveness check) — a settled dispatch is skipped on every later tick.

    The optional ``dispatch_gate`` is the R20 approval gate: a ready leaf the gate rejects is **held
    back** (added to ``gated``, NOT dispatched) until the operator approves the current frontier.

    The presence-conditional **degrade decision** (R23/AE1, ``outcome_dispatcher.degrade_decision``) runs
    per leaf before dispatch when ``available`` is given: a leaf whose chosen backend is unavailable
    **HALTs** if the operator is attending / it is guarantee-bearing / it already side-effected
    (destructive), else **degrades one rung** down the ladder (recording a visible :class:`DegradeReceipt`
    in the ledger) and dispatches on the lower backend. ``available=None`` keeps the legacy behavior (the
    chosen backend is dispatched as-is, and a dispatcher that raises ``BackendHaltError`` still HALTs).

    A backend HALT is recorded in the ledger (durable + visible) and reconcile CONTINUES to other
    runnable leaves — one unavailable backend never starves the frontier, and a HALT/degrade is never a
    silent substitution.
    """
    success = outcome_store.completed_subplots(store)  # success-only -> the frontier input
    settled = set(_dispatch_records(store))  # subplots with a COMMIT dispatch record
    dispatched: list[str] = []
    halted: list[dict[str, Any]] = []
    gated: list[str] = []
    degraded: list[dict[str, Any]] = []
    for sid in outcome_spec.ready_frontier(spec, success):
        if sid in settled:
            continue  # settled dispatch record exists -> idempotent skip (no double-dispatch)
        if dispatch_gate is not None and not dispatch_gate(sid):
            gated.append(sid)  # R20: frontier not approved at the current revision -> hold back
            continue
        node = spec.node_by_id(sid)
        if node is None:
            continue
        # Per-subplot lock guards the concurrent-tick race within the TTL window; the commit record
        # is the durable dedup. If another tick holds the lock right now, skip — it owns this leaf.
        if not outcome_store.acquire_dispatch(store, sid, holder, lease_ttl, now=now):
            continue

        # The presence-conditional degrade decision (R23). Resolves the backend to dispatch on, or HALTs.
        resolved_backend = node.backend
        degrade_receipt: dict[str, Any] | None = None
        if available is not None:
            action, resolved_backend, reason = outcome_dispatcher.degrade_decision(
                node.backend,
                available=available,
                attending=attending,
                guarantee_bearing=outcome_dispatcher.is_guarantee_bearing(node),
                had_side_effect=node.destructive,
            )
            if action == "halt":
                outcome_store.release_lease(store, f"dispatch-{sid}", holder)
                receipt = outcome_dispatcher.HaltReceipt(
                    outcome_id=spec.outcome_id,
                    subplot_id=sid,
                    backend=node.backend,
                    reason=reason,
                    available=tuple(available),
                ).to_dict()
                # Append-once on (halt, key): an attended leaf polling against a persistently-unavailable
                # backend must not re-append a halt record every tick (unbounded ledger growth).
                _append_ledger_once(
                    store,
                    {"phase": "halt", "kind": "dispatch", "key": f"dispatch:{sid}", **receipt},
                )
                halted.append(receipt)
                continue
            if action == "degrade":
                degrade_receipt = outcome_dispatcher.DegradeReceipt(
                    outcome_id=spec.outcome_id,
                    subplot_id=sid,
                    from_backend=node.backend,
                    to_backend=resolved_backend,
                    reason=reason,
                ).to_dict()

        key = f"dispatch:{sid}"
        outcome_store.append_ledger(
            store, {"phase": "intent", "kind": "dispatch", "key": key, "subplot_id": sid}
        )
        try:
            leaf_saga_id = dispatch(
                DispatchRequest(
                    outcome_id=spec.outcome_id,
                    subplot_id=sid,
                    title=node.title,
                    backend=resolved_backend,
                    repo_root=Path(repo_root),
                )
            )
        except outcome_dispatcher.BackendHaltError as halt:
            # A dispatcher-raised HALT (legacy / a restricted injected dispatcher). Release the lock so a
            # later tick re-attempts + re-surfaces it; record the receipt durably; never abort the tick.
            outcome_store.release_lease(store, f"dispatch-{sid}", holder)
            receipt = (
                halt.receipt.to_dict() if hasattr(halt.receipt, "to_dict") else dict(halt.receipt)
            )
            _append_ledger_once(store, {"phase": "halt", "kind": "dispatch", "key": key, **receipt})
            halted.append(receipt)
            continue
        if degrade_receipt is not None:
            # A visible downgrade receipt (R23) — surfaced in the report's Degradations section.
            # Append-once on (degrade, key) so a crash in the degrade->commit window (recovery re-runs the
            # intent) cannot double-list the degradation.
            _append_ledger_once(store, {"phase": "degrade", "key": key, **degrade_receipt})
            degraded.append(degrade_receipt)
        outcome_store.append_ledger(
            store,
            {
                "phase": "commit",
                "kind": "dispatch",
                "key": key,
                "subplot_id": sid,
                "leaf_saga_id": leaf_saga_id,
                "backend": resolved_backend,
                "at": now(),  # dispatch timestamp for the U9 liveness check (R31)
            },
        )
        dispatched.append(sid)
    return dispatched, halted, gated, degraded


# ---------------------------------------------------------------------------
# attend — print the native leaf re-entry handoff (R16 altitude seam)
# ---------------------------------------------------------------------------


def attend(repo_root: Path, outcome_id: str, subplot_id: str) -> str:
    """Return the native ``/resume <leaf-saga-id>`` handoff for a dispatched leaf.

    The coordinator does not run the leaf — it hands the operator the exact native command to drop
    into that leaf's own saga (R16). Leaf verbs (`/work`, `/code-review`, `/qa`) are reused, never
    shadowed by an `/outcome work`.
    """
    store = _store(repo_root, outcome_id)
    records = _dispatch_records(store)
    leaf = records.get(subplot_id)
    if not leaf:
        raise OutcomeError(
            f"subplot {subplot_id!r} is not dispatched yet — nothing to attend "
            f"(dispatched: {sorted(records)})"
        )
    return f"/resume {leaf}"


# ---------------------------------------------------------------------------
# export / import — portable bundle across machines/worktrees (R14)
# ---------------------------------------------------------------------------


def export_bundle(
    repo_root: Path, outcome_id: str, *, runner: Callable[..., Any] | None = None
) -> dict[str, Any]:
    """A self-contained, portable snapshot: canonical spec + completion events + dispatch records.

    This is the R14 cross-machine/worktree story — the structural truth plus the completion/dispatch
    facts needed to resume elsewhere. The cache itself is never exported (it is rebuildable).
    """
    spec = load_spec(repo_root, outcome_id)
    store = _store(repo_root, outcome_id, runner=runner)
    events: list[dict[str, Any]] = []
    for node in spec.nodes:
        for ev in outcome_store.read_completion_events(store, node.subplot_id):
            events.append(ev.to_dict())
    return {
        "schema": "outcome-bundle/1",
        "spec": spec.to_dict(),
        "completion_events": events,
        "dispatch_ledger": [
            r for r in outcome_store.read_ledger(store) if r.get("kind") == "dispatch"
        ],
    }


def import_bundle(
    repo_root: Path, bundle: dict[str, Any], *, runner: Callable[..., Any] | None = None
) -> outcome_spec.OutcomeSpec:
    """Reconstruct an outcome from a bundle: write the spec to the branch + replay events/records.

    Fully **idempotent** — re-importing the same bundle does not duplicate state: completion events
    replay through the write-once, idempotency-keyed store; dispatch ledger records are deduped
    against the existing ledger by their ``(phase, key)`` so the ledger does not grow on re-import.
    """
    if bundle.get("schema") != "outcome-bundle/1":
        raise OutcomeError(f"unrecognized bundle schema {bundle.get('schema')!r}")
    spec = outcome_spec.OutcomeSpec.from_dict(bundle["spec"])
    spec.validate()
    save_spec(repo_root, spec)
    store = _store(repo_root, spec.outcome_id, runner=runner)
    for ev_dict in bundle.get("completion_events", []):
        outcome_store.write_completion_event(
            store, outcome_store.CompletionEvent.from_dict(ev_dict)
        )
    existing = {(str(r.get("phase")), str(r.get("key"))) for r in outcome_store.read_ledger(store)}
    for rec in bundle.get("dispatch_ledger", []):
        ident = (str(rec.get("phase")), str(rec.get("key")))
        if ident in existing:
            continue  # already present -> skip so re-import does not grow the ledger
        outcome_store.append_ledger(store, rec)
        existing.add(ident)
    return spec


# ---------------------------------------------------------------------------
# graph — Mermaid topology (KTD12 one-glance frontier; full report is U8)
# ---------------------------------------------------------------------------


def graph_mermaid(repo_root: Path, outcome_id: str, *, store: Any | None = None) -> str:
    """A Mermaid flowchart of the DAG annotated with derived live state (KTD12 one-glance topology)."""
    spec = load_spec(repo_root, outcome_id)
    store = store if store is not None else _store(repo_root, outcome_id)
    states = derive_states(spec, store)
    lines = ["flowchart TD"]
    for node in spec.nodes:
        st = states[node.subplot_id]
        lines.append(f'    {node.subplot_id}["{node.subplot_id}: {st}"]')
    for node in spec.nodes:
        for dep in node.depends_on:
            lines.append(f"    {dep} --> {node.subplot_id}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Production harvester — the completion-barrier injector for the live advance loop (U5)
# ---------------------------------------------------------------------------


def production_harvester(
    repo_root: Path, *, github_runner: Callable[..., Any] | None = None
) -> Callable[[Any, Any], list[str]]:
    """Build the harvester ``advance`` runs each tick: it materializes GitHub-canonical completions
    (a merged PR / closed issue) into the store so the frontier unlocks the next Kahn layer (U5).

    Child-outcome nodes (``child_spec_ref``, KTD10) resolve their terminal state by **recursing**
    into the child outcome — load its branch spec, harvest it, and report ``done`` iff every child
    node is success-complete. A ``seen`` set guards against a ``child_spec_ref`` ancestor cycle (the
    deep static cycle check lands with the decompose flow, U7); a missing/unstarted child reads
    ``unknown`` (so the parent waits, never falsely unlocks).
    """
    import outcome_orchestrator

    def child_state_reader(child_id: str, seen: frozenset[str] = frozenset()) -> str:
        if child_id in seen:
            return "unknown"  # ancestor cycle — do not recurse forever
        try:
            child_spec = load_spec(repo_root, child_id)
        except OutcomeError:
            return "unknown"  # child not started yet -> parent keeps waiting
        # NOTE: the store's runner resolves the git-common-dir (NOT GitHub) — it must stay the
        # default git resolver, never the ``github_runner`` (that is only for ``gh`` reads in harvest).
        child_store = _store(repo_root, child_id)
        nxt = seen | {child_id}
        outcome_orchestrator.harvest(
            child_spec,
            store=child_store,
            github_runner=github_runner,
            child_state_reader=lambda cid: child_state_reader(cid, nxt),
        )
        done_set = outcome_store.completed_subplots(child_store)
        all_done = all(n.subplot_id in done_set for n in child_spec.nodes)
        return "done" if all_done else "running"

    def harvester(spec: Any, store: Any) -> list[str]:
        return outcome_orchestrator.harvest(
            spec, store=store, github_runner=github_runner, child_state_reader=child_state_reader
        )

    return harvester


def production_merge_processor(
    *, github_runner: Callable[..., Any] | None = None
) -> Callable[[Any, Any], Any]:
    """Build the merge processor ``advance`` runs each tick under the held coordinator lease (U6): it
    auto-merges every clean, non-gated code leaf (serialized) and records GitHub negative terminals."""
    import outcome_merge

    ops = outcome_merge.github_merge_ops(github_runner)

    def processor(spec: Any, store: Any) -> Any:
        return outcome_merge.process_merge_queue(spec, store, ops)

    return processor


def production_worktree_processor(
    repo_root: Path,
    *,
    runner: Callable[..., Any] | None = None,
    owner: str = "",
    cap: int | None = None,
) -> Callable[[Any, Any], Any]:
    """Build the worktree processor ``advance`` runs each tick under the held coordinator lease (U7):
    it reaps terminal sub-outcomes' worktrees, records the worktree-removed terminal (R32) + cascade,
    and provisions a durable worktree for each dispatched sub-outcome (cap-bounded, R15)."""
    import outcome_worktrees

    ops = outcome_worktrees.git_worktree_ops(repo_root, runner=runner)
    owner = owner or _default_holder()
    wt_cap = cap if cap is not None else outcome_worktrees.WORKTREE_CAP

    def processor(spec: Any, store: Any) -> Any:
        harvested = outcome_worktrees.harvest_worktrees(spec, store, ops)
        provisioned = outcome_worktrees.provision_pending(
            repo_root, spec, store, ops, owner=owner, cap=wt_cap
        )
        return {**harvested, **provisioned}

    return processor


def production_liveness_processor(
    *, now: Callable[[], float] = time.time
) -> Callable[[Any, Any], Any]:
    """Build the liveness processor ``advance`` runs each tick under the held coordinator lease (U9): it
    reclaims every hung dispatched leaf (breaching its heartbeat/timeout budget) as ``stalled`` (R31)."""
    import outcome_liveness

    def processor(spec: Any, store: Any) -> Any:
        return outcome_liveness.harvest_liveness(spec, store, now=now())

    return processor


def production_cost_processor(repo_root: Path) -> Callable[[Any, Any], Any]:
    """Build the cost processor ``advance`` runs each tick (U10): it materializes the realized-cost
    rollup (R24) into ``spec.cost_rollup`` and persists the spec WHEN the rollup changed, so the U8
    report renders it (the producer -> spec -> consumer edge, no U8->U10 code dependency)."""
    import outcome_costs

    def processor(spec: Any, store: Any) -> Any:
        changed = outcome_costs.materialize(spec, store)
        if changed:
            save_spec(repo_root, spec)
        return {"rollup": spec.cost_rollup, "changed": changed}

    return processor


# ---------------------------------------------------------------------------
# CLI — the thin /outcome verbs (KTD11). No I/O at import.
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="OutcomeOrchestrator — thin coordinator verbs.")
    parser.add_argument("--repo-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="create the branch-local spec + store")
    p_start.add_argument("outcome_id")
    p_start.add_argument("objective")

    p_advance = sub.add_parser("advance", help="run a reconcile tick (dispatch the ready frontier)")
    p_advance.add_argument("outcome_id")
    p_advance.add_argument("--loop", action="store_true")
    p_advance.add_argument(
        "--autonomous",
        action="store_true",
        help="operator is away — an unavailable backend degrades one rung instead of HALTing (R23)",
    )
    p_advance.add_argument(
        "--host-capable",
        action="store_true",
        help="this host can run the forked-context backends (fork/subagent/goal)",
    )
    p_advance.add_argument(
        "--workflow-available",
        action="store_true",
        help="this host can run cc-workflows-ultracode (the Workflow tool is present)",
    )
    p_advance.add_argument(
        "--persist",
        action="store_true",
        help="commit + push the spec to the outcome branch after advancing (R26/R27 durability)",
    )

    for verb in ("resume", "status", "graph"):
        p = sub.add_parser(verb, help=f"{verb} an outcome")
        p.add_argument("outcome_id")

    p_attend = sub.add_parser(
        "attend",
        help="the consolidated attention prompt (R18); with a subplot, the /resume handoff",
    )
    p_attend.add_argument("outcome_id")
    p_attend.add_argument("subplot_id", nargs="?", default=None)

    p_report = sub.add_parser(
        "report", help="regenerate docs/outcomes/<id>/report.md from state (R19)"
    )
    p_report.add_argument("outcome_id")

    p_project = sub.add_parser(
        "project", help="the generated mission-control secondary projection (R25)"
    )
    p_project.add_argument("outcome_id")
    p_project.add_argument("--markdown", action="store_true")

    p_commit = sub.add_parser(
        "commit", help="commit (+ --push) the spec to the outcome's branch (R26/R27 durability)"
    )
    p_commit.add_argument("outcome_id")
    p_commit.add_argument("--push", action="store_true")

    p_export = sub.add_parser("export", help="print a portable bundle (spec + completion)")
    p_export.add_argument("outcome_id")

    p_import = sub.add_parser("import", help="reconstruct an outcome from a bundle file")
    p_import.add_argument("path")

    p_approve = sub.add_parser(
        "approve", help="approve the current frontier so it may dispatch (R20)"
    )
    p_approve.add_argument("outcome_id")

    p_prune = sub.add_parser("prune", help="prune a node + reconcile its orphans (R33)")
    p_prune.add_argument("outcome_id")
    p_prune.add_argument("subplot_id")

    p_promote = sub.add_parser("promote", help="promote a subplot to its own child saga (R21)")
    p_promote.add_argument("outcome_id")
    p_promote.add_argument("subplot_id")
    p_promote.add_argument("child_spec_ref")

    args = parser.parse_args(argv)
    # Resolve the repo root to an absolute, symlink-collapsed path. The default is ``.`` (relative),
    # and a relative/symlinked root would make the worktree registry paths diverge from git's absolute
    # realpath porcelain — reading every live worktree as ABSENT (R15 cap unenforced + R34 false
    # worktree-removed terminals). Canonicalizing here keeps the registry paths == git's view.
    root = Path(args.repo_root).resolve()
    try:
        if args.command == "start":
            spec = start(root, args.outcome_id, args.objective)
            print(json.dumps({"started": spec.outcome_id, "nodes": len(spec.nodes)}))
        elif args.command == "advance":
            # The production /outcome advance routes through the REAL backend seam (R5/R6), the REAL
            # completion barrier (U5, harvester), the REAL auto-merge queue (U6, merge_processor), the
            # REAL worktree lifecycle (U7, worktree_processor), the REAL approval gate (U7, gate_factory),
            # the REAL liveness reclaim (U9, liveness_processor: hung leaf -> stalled), and the REAL
            # presence-conditional degrade decision (U9, available + attending): an unavailable backend
            # HALTs when attended/guaranteed/side-effected, else degrades one rung when --autonomous.
            import outcome_decompose

            avail = outcome_dispatcher.resolve_available(
                host_capable=args.host_capable, workflow_available=args.workflow_available
            )
            # The dispatcher mints any backend the degrade decision resolves to (it never halts here —
            # _reconcile_once owns the HALT/degrade decision via degrade_decision with `avail`).
            result = advance(
                root,
                args.outcome_id,
                loop=args.loop,
                dispatcher=outcome_dispatcher.make_dispatcher(available=outcome_spec.NODE_BACKENDS),
                harvester=production_harvester(root),
                merge_processor=production_merge_processor(),
                worktree_processor=production_worktree_processor(root),
                liveness_processor=production_liveness_processor(),
                cost_processor=production_cost_processor(root),
                gate_factory=lambda spec, store: outcome_decompose.make_dispatch_gate(store, spec),
                available=avail,
                attending=not args.autonomous,
            )
            out = result.to_dict()
            if args.persist:
                # R26/R27: commit + push the (possibly cost-rollup-mutated) spec to the outcome branch so
                # a different machine can pull-and-reconstruct (refuses on main; no-op if unchanged).
                out["persisted"] = commit_spec(root, args.outcome_id, push=True)
            print(json.dumps(out))
        elif args.command == "commit":
            print(json.dumps(commit_spec(root, args.outcome_id, push=args.push)))
        elif args.command == "approve":
            import outcome_decompose

            spec = load_spec(root, args.outcome_id)
            store = _store(root, args.outcome_id)
            rev = outcome_decompose.approve_frontier(store, spec)
            print(json.dumps({"approved_revision": rev, "outcome_id": spec.outcome_id}))
        elif args.command == "prune":
            import outcome_decompose
            import outcome_worktrees

            spec = load_spec(root, args.outcome_id)
            store = _store(root, args.outcome_id)
            # The worktree reap is wired to the real git adapter. U8's projection is artifact-only (it
            # generates the secondary view, it does NOT create GitHub sub-issues), so there is no
            # generated sub-issue to close yet; the sub-issue close adapter is deferred to a later
            # operator-initiated mission-control consumer, so issue_close stays None until then.
            summary = outcome_decompose.prune(
                spec,
                store,
                args.subplot_id,
                worktree_ops=outcome_worktrees.git_worktree_ops(root),
            )
            save_spec(root, spec)
            print(json.dumps(summary))
        elif args.command == "promote":
            import outcome_decompose

            spec = load_spec(root, args.outcome_id)
            rev = outcome_decompose.promote(spec, args.subplot_id, args.child_spec_ref)
            save_spec(root, spec)
            print(json.dumps({"promoted": args.subplot_id, "spec_revision": rev}))
        elif args.command == "resume":
            print(json.dumps(resume(root, args.outcome_id)))
        elif args.command == "status":
            print(json.dumps(status(root, args.outcome_id)))
        elif args.command == "graph":
            print(graph_mermaid(root, args.outcome_id))
        elif args.command == "attend":
            if args.subplot_id:
                print(attend(root, args.outcome_id, args.subplot_id))
            else:
                # No subplot -> the single consolidated attention prompt (R18), one ranked page.
                import outcome_report

                spec = load_spec(root, args.outcome_id)
                store = _store(root, args.outcome_id)
                print(outcome_report.consolidated_prompt(outcome_report.consolidate(spec, store)))
        elif args.command == "report":
            import outcome_report

            path = outcome_report.write_report(root, args.outcome_id)
            print(json.dumps({"report": str(path)}))
        elif args.command == "project":
            import outcome_projection

            spec = load_spec(root, args.outcome_id)
            store = _store(root, args.outcome_id)
            if args.markdown:
                print(outcome_projection.projection_markdown(spec, store), end="")
            else:
                print(json.dumps(outcome_projection.project(spec, store)))
        elif args.command == "export":
            print(json.dumps(export_bundle(root, args.outcome_id)))
        elif args.command == "import":
            bundle = json.loads(Path(args.path).read_text(encoding="utf-8"))
            spec = import_bundle(root, bundle)
            print(json.dumps({"imported": spec.outcome_id, "nodes": len(spec.nodes)}))
    except (OutcomeError, outcome_spec.OutcomeSpecError, outcome_store.OutcomeStoreError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    except ValueError as exc:
        # DecomposeError / WorktreeError (both ValueError subclasses) — a rejected edit / worktree op.
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
