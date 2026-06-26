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
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Make sibling scripts importable when loaded by path (tests, CLI).
sys.path.insert(0, str(Path(__file__).resolve().parent))

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

    Note: this writes **structure**, not per-tick operational state — node live-state is derived on
    read (R17), never re-committed each tick, so the branch history is not polluted with state churn.
    """
    spec.validate()
    path = spec_path(repo_root, spec.outcome_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(spec.to_json(), encoding="utf-8")
    return path


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
        "frontier": outcome_spec.ready_frontier(spec, done),
        "complete": len(done) == len(spec.nodes),
    }


# ---------------------------------------------------------------------------
# advance — the level-triggered reconcile tick (R29)
# ---------------------------------------------------------------------------


@dataclass
class AdvanceResult:
    dispatched: list[str] = field(default_factory=list)  # subplots handed to a backend this tick
    skipped_busy: bool = False  # coordinator lease held by another tick -> no-op (R13)
    ticks: int = 1
    status: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatched": self.dispatched,
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
    holder: str | None = None,
    lease_ttl: float = DEFAULT_LEASE_TTL,
    now: Callable[[], float] = time.time,
    runner: Callable[..., Any] | None = None,
) -> AdvanceResult:
    """Run one (``loop=False``) or repeated (``loop=True``) reconcile ticks.

    A tick: acquire the coordinator lease under a per-invocation unique ``holder`` (a second
    concurrent / re-entrant ``advance`` is a different holder, so it no-ops on the held lease, R13);
    recompute the ready frontier from the durable store; for each ready, not-yet-dispatched,
    not-completed leaf, take its per-subplot dispatch lock and **dispatch** it (record an intent,
    call the injected backend dispatcher, record a commit) — never running the leaf's work here (R3);
    then return the derived status. Idempotent: a leaf with a settled (``commit``) dispatch record is
    skipped, so repeated ticks never double-dispatch. ``loop`` repeats until the frontier is empty or
    ``max_ticks``, which the host (`/loop`/cron) would otherwise drive.
    """
    holder = holder if holder is not None else _default_holder()
    dispatch = dispatcher if dispatcher is not None else _default_dispatcher
    spec = load_spec(repo_root, outcome_id)
    store = _store(repo_root, outcome_id, runner=runner)

    if not outcome_store.acquire_coordinator(store, holder, lease_ttl, now=now):
        return AdvanceResult(
            skipped_busy=True, ticks=0, status=status(repo_root, outcome_id, spec=spec, store=store)
        )

    all_dispatched: list[str] = []
    ticks = 0
    try:
        while True:
            ticks += 1
            tick_dispatched = _reconcile_once(
                repo_root, spec, store, dispatch, holder, lease_ttl, now
            )
            all_dispatched.extend(tick_dispatched)
            if not loop:
                break
            if not tick_dispatched:
                break  # quiescent: nothing new to dispatch this tick
            if ticks >= max_ticks:
                break
    finally:
        outcome_store.release_lease(store, outcome_store.COORDINATOR_LOCK, holder)

    return AdvanceResult(
        dispatched=all_dispatched,
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
) -> list[str]:
    """One level-triggered pass: dispatch every ready, not-yet-settled leaf exactly once.

    Each dispatch is recorded **intent -> effect -> commit** (the store's replay protocol): the
    intent is written BEFORE the backend is invoked, so a crash/append-failure after the effect
    leaves a durable dangling intent that ``replay_pending`` surfaces and the next reconcile re-drives
    (the dispatcher must be idempotent on its leaf id) rather than the leaf being silently lost. The
    ``commit`` is the durable dedup marker — a settled dispatch is skipped on every later tick.
    """
    success = outcome_store.completed_subplots(store)  # success-only -> the frontier input
    settled = set(_dispatch_records(store))  # subplots with a COMMIT dispatch record
    dispatched: list[str] = []
    for sid in outcome_spec.ready_frontier(spec, success):
        if sid in settled:
            continue  # settled dispatch record exists -> idempotent skip (no double-dispatch)
        node = spec.node_by_id(sid)
        if node is None:
            continue
        # Per-subplot lock guards the concurrent-tick race within the TTL window; the commit record
        # is the durable dedup. If another tick holds the lock right now, skip — it owns this leaf.
        if not outcome_store.acquire_dispatch(store, sid, holder, lease_ttl, now=now):
            continue
        key = f"dispatch:{sid}"
        outcome_store.append_ledger(
            store, {"phase": "intent", "kind": "dispatch", "key": key, "subplot_id": sid}
        )
        leaf_saga_id = dispatch(
            DispatchRequest(
                outcome_id=spec.outcome_id,
                subplot_id=sid,
                title=node.title,
                backend=node.backend,
                repo_root=Path(repo_root),
            )
        )
        outcome_store.append_ledger(
            store,
            {
                "phase": "commit",
                "kind": "dispatch",
                "key": key,
                "subplot_id": sid,
                "leaf_saga_id": leaf_saga_id,
                "backend": node.backend,
            },
        )
        dispatched.append(sid)
    return dispatched


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

    for verb in ("resume", "status", "graph"):
        p = sub.add_parser(verb, help=f"{verb} an outcome")
        p.add_argument("outcome_id")

    p_attend = sub.add_parser("attend", help="print the native /resume handoff for a leaf")
    p_attend.add_argument("outcome_id")
    p_attend.add_argument("subplot_id")

    p_export = sub.add_parser("export", help="print a portable bundle (spec + completion)")
    p_export.add_argument("outcome_id")

    p_import = sub.add_parser("import", help="reconstruct an outcome from a bundle file")
    p_import.add_argument("path")

    args = parser.parse_args(argv)
    root = Path(args.repo_root)
    try:
        if args.command == "start":
            spec = start(root, args.outcome_id, args.objective)
            print(json.dumps({"started": spec.outcome_id, "nodes": len(spec.nodes)}))
        elif args.command == "advance":
            print(json.dumps(advance(root, args.outcome_id, loop=args.loop).to_dict()))
        elif args.command == "resume":
            print(json.dumps(resume(root, args.outcome_id)))
        elif args.command == "status":
            print(json.dumps(status(root, args.outcome_id)))
        elif args.command == "graph":
            print(graph_mermaid(root, args.outcome_id))
        elif args.command == "attend":
            print(attend(root, args.outcome_id, args.subplot_id))
        elif args.command == "export":
            print(json.dumps(export_bundle(root, args.outcome_id)))
        elif args.command == "import":
            bundle = json.loads(Path(args.path).read_text(encoding="utf-8"))
            spec = import_bundle(root, bundle)
            print(json.dumps({"imported": spec.outcome_id, "nodes": len(spec.nodes)}))
    except (OutcomeError, outcome_spec.OutcomeSpecError, outcome_store.OutcomeStoreError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
