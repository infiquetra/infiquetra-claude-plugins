---
name: outcome
description: Coordinate a whole outcome as a durable DAG of leaf sagas — start, advance the ready frontier, attend a leaf, resume, graph, export/import. The coordinator routes and dispatches to executors; it never runs leaf work itself, and status is derived on read.
argument-hint: "[start <id> <objective> | advance <id> [--loop] | attend <id> <subplot> | resume <id> | status <id> | graph <id> | export <id> | import <bundle>]"
---

Load `saga/skills/outcome/SKILL.md` and run the requested coordinator verb.

`/outcome` is the **OutcomeOrchestrator** surface — the layer ABOVE a single work-thread saga that owns a
whole outcome as a concurrent DAG of leaf sagas (subplots). It is a **level-triggered reconcile loop**
(R29): each `advance` tick reconstructs live state from the durable store, dispatches the ready frontier
to executors, harvests completion, and pages the operator only at gates and exceptions — it holds no
authoritative in-memory DAG, so it is crash-tolerant and host-agnostic.

Two invariants the surface enforces:
- **The coordinator routes, it never executes** (R2/R3). `/outcome` only dispatches leaves to their
  backends and harvests their completion; it never runs a leaf's work in-context. Leaf work stays the
  native `/resume <leaf-saga-id>` / `/work` / `/code-review` / `/qa` — there is no `/outcome work`.
  `attend` just prints the native re-entry handoff for a leaf you want hands-on (R16 altitude seam).
- **Status is derived on read** (R17). There is no operator-writable status field; the cockpit is
  recomputed every read from the committed spec + completion events, so it cannot drift.

It does **not** author the graph from scratch (that is `/plan` + the decompose flow), run leaf
implementations, file SDLC issues (`mission-control`), or deploy (`deploy`).

Arguments provided to the command:

`$ARGUMENTS`
