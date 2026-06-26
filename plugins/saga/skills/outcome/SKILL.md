---
name: outcome
description: Coordinate a whole outcome as a durable DAG of leaf sagas. A level-triggered reconcile loop that dispatches the ready frontier to executors, harvests completion, and pages the operator only at gates and exceptions. The coordinator routes and never runs leaf work; status is derived on read. Thin coordinator verbs only — start, graph, advance, attend, resume, export, import — leaf work stays the native /resume, /work, /code-review, /qa.
---

# Outcome

`/outcome` is the **OutcomeOrchestrator**: the layer above a single work-thread saga that drives a whole
*outcome* — outcome → subplots (leaf sagas) — as a concurrent, durable DAG across sessions, worktrees,
and machines. The human is an interrupt-handler on gates and exceptions; the runner advances everything
else.

This skill is the thin operator surface over the reconcile engine
(`plugins/saga/scripts/outcome.py`), the spec (`outcome_spec.py`, U1 — structure) and the store
(`outcome_store.py`, U2 — the git-common-dir cache, completion events, locks, replay ledger).

## Position in the lifecycle

`/outcome` sits **above** the saga lifecycle, not inside it. A leaf subplot is a normal linear saga that
runs the usual `/plan → /work → /code-review → /qa` on its own branch/worktree. `/outcome` coordinates
*which* leaves are ready, dispatches them, and harvests their completion — it never replaces the leaf
verbs. The altitude seam is explicit: `attend` hands you the native `/resume <leaf-saga-id>` to drop into
a leaf hands-on, then you come back up to `/outcome`.

## Core principles

1. **The coordinator routes, it never executes (R2/R3).** `advance` dispatches ready leaves to their
   backends and reads their completion events. It must never run a leaf's work in the advance process —
   doing so would collapse the whole DAG into one inline context and lose the plot. There is no
   `/outcome work`.
2. **Level-triggered, not imperative (R29).** Every tick reconstructs from the durable store, advances
   the ready frontier, and sleeps. It holds no authoritative in-memory DAG, so a crash mid-run is
   recoverable — the next tick re-derives. `/goal` and compiled workflows are *executors it dispatches
   to*, never the host.
3. **Status is derived on read (R17).** No operator-writable status field. A node's live state is
   computed each call from the committed spec + completion events + dispatch records. A healthy steady
   state is an empty surface — you are paged only at gates, unsatisfiable barriers, ambiguity, and
   parent-close.
4. **The committed spec is canonical for structure; GitHub for completion; the cache holds nothing
   canonical (R26/R27).** Deleting the git-common-dir cache loses nothing — `resume` rebuilds it.

## The thin surface (KTD11)

Coordinator-only verbs — run via `python3 plugins/saga/scripts/outcome.py <verb> ...`:

| verb | does |
|---|---|
| `start <id> <objective>` | create the branch-local spec (`docs/outcomes/<id>/outcome-spec.json`) + its store |
| `graph <id>` | print a Mermaid DAG annotated with each node's derived live state (one-glance topology) |
| `advance <id> [--loop]` | one (or repeated) reconcile ticks — dispatch the ready frontier, idempotently |
| `attend <id> <subplot>` | print the native `/resume <leaf-saga-id>` handoff for a leaf you want hands-on |
| `resume <id>` | reconstruct live status from spec + store (works even if the cache was wiped) |
| `status <id>` | the derived-on-read cockpit snapshot (states, counts, frontier) |
| `commit <id> [--push]` | **commit (+ push) the spec to the outcome's own branch** — the R26/R27 cross-machine durability step (refuses on `main`/`master`) |
| `report <id>` / `project <id>` | regenerate the derived-on-read report (R19) / the mission-control projection (R25) |
| `approve <id>` / `prune <id> <subplot>` / `promote <id> <subplot> <child>` | the R20 frontier approval + the R33 graph edits |
| `export <id>` / `import <bundle>` | a portable spec + completion bundle to move an outcome across machines |

**Persist the spec to the branch (R26/R27).** The committed `docs/outcomes/<id>/outcome-spec.json` on the
outcome's own branch (`outcome/<slug>`, never `main` mid-run) is what lets a **different machine
reconstruct the whole outcome by pulling the repo** — load the committed spec, then re-harvest completion
from GitHub (canonical), with no dependence on the local cache. `start` and the graph edits write the
working-tree file; **commit + push is explicit**: run `/outcome commit <id> --push` after structural
changes, or `/outcome advance <id> --persist` to commit the (cost-rollup-updated) spec each tick on an
unattended `/loop` run. The *cadence* is yours; the *mechanism* is `commit`/`--persist`. (`export`/`import`
remain the cache-derived bundle for an ad-hoc move; the committed-branch path is the canonical durability.)

Leaf work is **always** the native verbs on the leaf's own saga: `/resume <leaf-saga-id>`, `/work`,
`/code-review`, `/qa`. Never shadow them.

## How a reconcile tick works (`advance`)

1. Load the canonical spec (branch) and open the store (git-common-dir cache).
2. Acquire the **coordinator lease** — a second concurrent `advance` no-ops on a held lease and reclaims
   a stale one (R13), so two ticks (a cron tick overlapping a manual one) never both mutate.
3. Recompute `completed` from the store's completion events and the **ready frontier** from the spec
   (`ready_frontier`, the level-triggered read).
4. For each ready, not-yet-dispatched, not-completed leaf: take its per-subplot dispatch lock and
   **dispatch** it to its backend (record the handoff in the ledger). Already-dispatched leaves are
   skipped — repeated ticks never double-dispatch (idempotent).
5. Return the derived status. Pages only on exceptions.

The execution backends a leaf can be dispatched to — inline / fork / subagent / team-execution /
cc-workflows-ultracode / `/goal` / manual — are wired in later units; the dispatch *seam* and the
reconcile loop are the contract.

## Interaction method

Drive `/outcome` for coordination; drop to native leaf verbs for hands-on work. When several leaves block
at once, the attention consolidator (later unit) bubbles them into one ranked prompt rather than N pages.
Use `AskUserQuestion` only for genuine coordinator-level decisions (a gate, an unsatisfiable barrier, a
parent-close); in a channel session, inline the choices instead.

## What `/outcome` does NOT own

- Authoring the graph from scratch — that is `/plan` + the decompose flow (a later unit).
- Running any leaf's implementation — that is the leaf's native saga.
- Filing SDLC issues (`mission-control`) or deploying (`deploy`).
- A stored status field — status is always derived.

Arguments provided to the command:

`$ARGUMENTS`
