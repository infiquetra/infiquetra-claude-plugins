---
date: 2026-06-25
topic: outcome-orchestration-saga
focus: should saga gain an outcome-level orchestration layer above its single-work-thread lifecycle — outcome → sub-outcomes → tasks as a DAG, interchangeable execution backends, human on gates
scope: broad
repo: infiquetra-claude-plugins
maturity: idea-ready
---

# Ideation: Outcome-Level Orchestration for Saga

Seeded by a ChatGPT conversation that converged on a "plugin-managed DAG runner as a control plane
outside the chat" (`docs/analysis/2026-06-25-claude-cache-and-orchestration-chatgpt-source.md`).
The seeds entered the pool as peers and were reshaped hard by grounded critique (see Co-ideation
log). Sibling to the within-work-thread backend docs
[`2026-06-20-execution-backend-representation-ideation.md`](./2026-06-20-execution-backend-representation-ideation.md)
and [`2026-06-21-plan-work-backend-handoff-ideation.md`](./2026-06-21-plan-work-backend-handoff-ideation.md);
this run sits one altitude above them.

## Grounding Context

**Repo:** `saga` is a lifecycle engine in `infiquetra-claude-plugins`. A saga is the durable,
resumable work-state envelope for **one thread** of lifecycle work (`saga-spec.md:20`); lifecycle
ideation→brainstorm→plan→review→work→qa→retro. There is **no multi-thread / dependency / outcome
modeling** anywhere — no `parent_saga`/`child_sagas`/`depends_on`; `state.json` is a flat
`{saga_id → summary}` map. Execution backends are "offered, not vendored" (`operator-choice.md:37`):
`inline` | `team-execution` (gated/governance) | `cc-workflows-ultracode` (advisory/throwaway)
(`ORCHESTRATION_MODES`, `saga.py:71`). **`execution_spec.py` already carries per-unit DAG
machinery** — `dependency_layers()` Kahn parallelism (`:361`), the refute-N verifier panel, per-unit
`{model,effort}`, and `emit_workflow_script()` (`:541`, present + tested but **no skill calls it** —
the open contract hole). Binding decisions: the **dead-wiring guard** (a field needs a real producer
AND consumer), **HALT-not-degrade** (`operator-choice.md §6`), and the **self-modifying-engine
gate**. **campps #38** (objective → 9 capabilities → 56 components, plan only *described* the
workflow, no `.workflow.js` emitted, silent off-contract substitution) is direct evidence of the
failure an outcome layer must not reproduce one altitude up.

**Named repos:** `infiquetra-sdlc` — defines the canonical 5-tier hierarchy Initiative (field) →
Objective (field + Outcome Scorecard doc, **not an issue**, type retired 2026-06-14) → [Outcome card,
initiative boards only] → Capability (issue) → Component (child-card role). Crucially, **sub-issues
are decomposition, not a DAG**: no `depends_on`/`blocks` edge, no inter-capability ordering; and
**board-state vs saga-state are deliberately distinct coordinate systems** (`board-topology.md`: "the
board is the portfolio projection… the canonical lifecycle is the saga spine"). An outcome layer must
honor: Objective is a field+doc (DAG nodes must be Outcome cards/Capabilities), the operator closes
parents, native sub-issue API (not prose links), Initiative/Objective are fields not labels, and the
GitHub sub-issue depth cap (~3 levels).

**Context-libraries:** `infiquetra-context-library` consulted — holds company anatomy / platform /
Norns material; nothing canonical on lifecycle orchestration, outcomes, or DAG/dependency concepts.
None contributed.

## Topic Axes

- **A1 — State home & coordinate-system fit:** where outcome/DAG state lives given the deliberate
  saga-spine vs board-projection split; third coordinate system, or fold into one?
- **A2 — Dependency-edge semantics & DAG source-of-truth:** sub-issues have no `depends_on`; where do
  edges live and what is authoritative for "B blocks A"?
- **A3 — Outcome-level executor selection:** lifting per-unit `{model,effort}` + backend
  recommendation to per-node/per-layer; coordinated choice across a portfolio.
- **A4 — Autonomy & operator gating:** `/goal`-style autonomous loop vs explicit stepping; honoring
  "operator closes parents," workflow pause limits, the gated-vs-advisory split.
- **A5 — Outcome↔execution round-trip:** how a node emits a machine-runnable handoff INTO execution
  and reads completion/evidence BACK (anti-dead-wiring), plus cost/evidence attribution per outcome.

## Ranked Survivors

### 1. Emission-as-precondition — wire the unwired `emit_workflow_script()` as the decomposition→execution gate

A node cannot become "ready/executing" until it has emitted a machine-runnable handoff — which also closes the known open contract hole.

`emit_workflow_script()` (`execution_spec.py:541`) and the team emitter are present and tested but no skill calls them. Make emission a structural state-transition precondition at the outcome altitude, so no node is ever "described but not emitted" and the campps #38 pathology becomes an unrepresentable state.

Rationale: one wiring closes the within-thread contract hole AND the outcome-altitude dead-wiring at once — a real producer (the emitter) with a real consumer (the backend that runs it) — and HALT-not-degrade finally gets teeth at the portfolio level. Engages plan-work survivors #1/#2.

Downsides: emission-before-ready feels heavy for a trivial inline node — needs an "inline nodes self-emit" carve-out. Couples the layer to the spec/emitter format's stability.

| field | value |
|-------|-------|
| basis | `direct:` `execution_spec.py:541` (tested, uncalled); campps #38; `operator-choice.md §6` |
| confidence | 85 |
| complexity | Low–Med |
| axis | A5 |
| status | Unexplored |

### 2. Recursive `ExecutionSpec` — one DAG schema at two altitudes (saga-of-sagas)

Make the outcome DAG a higher-altitude instance of the `ExecutionSpec` saga already ships and tests, not a new node schema.

An outcome "node" is a saga thread whose own plan is another `ExecutionSpec`; a unit can expand into a sub-spec (recursion). `dependency_layers()` Kahn ordering, the refute-N verifier panel, and per-unit `{model,effort}` then run unchanged at both the plan-unit and outcome-node altitudes.

Rationale: every future altitude (initiative→outcome→capability) inherits parallelism, verification, and tiering for free — one schema to test and evolve — and it is the most direct realization of "lift the per-unit DAG to the inter-saga level" (`execution_spec.py:361`). Largely answers seed US6.

Downsides: recursion at the outcome altitude is unproven; `ExecutionSpec`'s unit fields may not all map cleanly to a saga-thread node, and an outcome-wide spec could grow large (needs segmentation discipline).

| field | value |
|-------|-------|
| basis | `direct:` `execution_spec.py:361 dependency_layers()`, per-unit `depends_on`/`{model,effort}`; survivor S4 |
| confidence | 82 |
| complexity | Med |
| axis | A2 |
| status | Unexplored |

### 3. Outcome state as a derived projection, not a third coordinate system

Compute the outcome DAG/status on read from sources that already exist; do not stand up a rival store.

Project from `issue_ref` (saga→issue), the native sub-issue tree, each plan's `orchestration_ref` spec, and child tick-chains; `/outcome report|next` are queries, not a new `state.json` grouping. One open sub-decision: pure-projection (zero new state) vs a single child `parent_ref` pointer to make traversal cheap.

Rationale: `board-topology.md` says board-state and saga-state are deliberately distinct coordinate systems — a projection is a lens over both, not a third — and the dead-wiring guard is satisfied trivially (no write to orphan). CQRS/Temporal precedent: state as a fold over existing events; it would also have *caught* campps #38 by reading `orchestration_ref` and surfacing "no `.workflow.js` emitted."

Downsides: recompute-on-read cost + join complexity across GitHub + saga + specs; a pure projection can't cheaply answer "what's my parent" without scanning (the `parent_ref` tension); correctness leans on `gh` availability.

| field | value |
|-------|-------|
| basis | `direct:` dead-wiring guard, flat `state.json` (`saga-spec §5.4`), third-coordinate warning; `external:` CQRS/Temporal |
| confidence | 80 |
| complexity | Low–Med |
| axis | A1 |
| status | Unexplored |

### 4. Evidence + cost rollup — the `/retro` + `/optimize` consumer that justifies the layer

"Done" requires durable acceptance evidence (task-token style); realized `{model,effort}` cost rolls up per outcome, feeding the two meta-commands that today have nothing portfolio-shaped to act on.

Pair the outbound handoff with a mandatory evidence stamp — a node isn't done until acceptance evidence is written (Step-Functions `waitForTaskToken`: no callback, no advance) — and sum realized cost up the DAG. `/optimize` (off-chain today) and `/retro` (single-thread today) gain a real cross-thread consumer.

Rationale: this is the direct answer to "would this even save money?" from the source chat — the per-outcome cost denominator + evidence is the worth-it signal, and it is what makes the new outcome state pass the dead-wiring guard (a behavior-changing reader). Turns "done" from the self-asserted flag campps #38 lied with into evidence-backed truth.

Downsides: realized-cost capture depends on per-node usage attribution (R12 telemetry is young); the evidence schema must stay light or it becomes bureaucracy; risks scope-creep into a full reporting system.

| field | value |
|-------|-------|
| basis | `direct:` dead-wiring guard, saga consumer map (`/optimize`,`/retro`), survivor S5; `external:` Step Functions task-token |
| confidence | 78 |
| complexity | Med |
| axis | A5 |
| status | Unexplored |

### 5. Backend selection at the Kahn layer, budgeted by human attention

Lift `recommend_execution_backend()` from per-node to the ready-layer, and cap concurrent gated backends because the human is the scarce resource.

Feed each `dependency_layers()` layer's aggregate shape to the recommender (independent fan-out → one workflow; gated change → team-execution; singleton → inline/fork), and add a portfolio budget (≤1 concurrent team-execution, N advisory workflows, unbounded inline). Never fold a gated node into an advisory fan-out — the governance split is preserved per layer.

Rationale: the real parallelism/cost leverage lives at the frontier, not the node, and per-layer keeps a layer uniformly gated OR advisory (clean governance). The Airflow-pools insight: lifting selection to a portfolio reveals that human-gate throughput, not compute, is the true constraint.

Downsides: a frontier-level batcher is exactly where the gated/advisory split could be silently flattened — needs a hard invariant + test; budget caps are empirical (wrong caps starve parallelism or melt the operator).

| field | value |
|-------|-------|
| basis | `direct:` `lifecycle_state.py:99`, `execution_spec.py:361`, survivors S2/S5; `external:` Airflow pools |
| confidence | 75 |
| complexity | Med |
| axis | A3 |
| status | Unexplored |

### 6. Gate-typed autonomy as level-triggered reconciliation

Auto-advance through advisory layers, hard-halt at gated nodes and parent-close; reconcile from actual world state instead of imperative stepping.

Autonomy isn't a global mode — it's the per-edge gate-class saga already owns (advisory/workflow auto-advances; team-execution/gated and parent-close HALT). Implement `/outcome next|reconcile` as a level-triggered loop (read actual issue/PR/CI/qa state, drive unsatisfied nodes) so a crash/resume just runs another reconcile — idempotent, can't double-execute a satisfied node.

Rationale: makes `/goal`-grade autonomy safe-by-construction out of existing machinery (HALT-not-degrade, "operator closes parents," "only permission prompts pause"), directly answering the campps #38 fear; K8s level-triggered control gives the resume-safety the flat `state.json` lacks. The human is the admission controller on gated dispatches.

Downsides: the reconcile loop is the most novel runtime here (highest burden/risk) and leans on `gh`/evidence reliability each tick; the minimalist pole — no loop, `/outcome next` runs one node then halts — may be the safer v1.

| field | value |
|-------|-------|
| basis | `direct:` `operator-choice.md §6`, gated-vs-advisory split, "operator closes parents"; `external:` K8s reconciliation |
| confidence | 72 |
| complexity | Med–High |
| axis | A4 |
| status | Unexplored |

### 7. Board as a generated projection — "one spec, three emitters"

Add a third emitter that renders the outcome `ExecutionSpec` into a native mission-control sub-issue tree, so the board is generated from the DAG, not a rival of it.

Alongside `team_emitter.py` and `emit_workflow_script()`, emit the spec → native sub-issue ownership tree; the spec stays the single source of truth for `depends_on`, the board becomes a decomposition projection that can't drift. The one-way `/handoff` bridge becomes this emitter — inverting seed US3 (issues *project* the DAG, they don't store it).

Rationale: resolves the third-coordinate-system tension by making the DAG generate the board rather than rival it, while honoring "operator closes parents," native sub-issue API, Initiative/Objective-are-fields, Component-stays-a-role, and the GitHub depth cap. Kills board↔saga drift at the source.

Downsides: generating/reconciling GitHub issues is side-effectful and hard to make idempotent (creation, depth-cap 422s); "operator closes parents" means the emitter syncs but cannot close; human edits to generated issues need a drift-back story.

| field | value |
|-------|-------|
| basis | `direct:` survivor S4 "one spec, two emitters", `board-topology.md`, `sub-issues.md`; challenges US3 |
| confidence | 70 |
| complexity | Med |
| axis | A1 |
| status | Unexplored |

## Did not survive (revivable)

| id | title | summary | reason | status |
|----|-------|---------|--------|--------|
| R1 | Compensating transactions / `/outcome abort` | Each sub-outcome records a compensation pointer; `/outcome abort` runs them reverse-topologically (saga's namesake pattern). | Valuable exception/rollback path (the "human on exceptions" half) but orthogonal to the core layer — a later increment. | rejected |
| R2 | Content-addressed idempotent resume | Fingerprint nodes from spec+acceptance+world-state; skip still-satisfied nodes, invalidate downstream (`nx affected`). | Strong resume optimization; folded as a mechanism into survivor #6 (reconcile) rather than a standalone build. | rejected |
| R3 | External plugin-managed DAG-runner control plane (seed US1) | A new always-on plugin/daemon outside the chat as the control plane. | Convergent finding is an in-engine projection + extended `/loop`, not a new daemon; kept as the maximal-build alternative if the lightweight approach proves insufficient. | rejected |
| R4 | Net-new DAG-node YAML schema (seed US6) | Author a fresh node schema (executor/model/effort/worktree/scope/acceptance/validation/evidence). | Reshaped into survivor #2 (recursive `ExecutionSpec`); a net-new schema duplicates tested machinery — revive if recursion mis-fits at the outcome altitude. | rejected |
| R5 | Reject-the-DAG: goal + regenerable frontier (HTN) | Store only a goal (acceptance predicate) + regenerate the frontier each tick; no stored graph at all. | Provocative "durability is the goal, not the decomposition" reframe; partially absorbed by survivor #6 (reconcile re-derives the frontier). Kept as the no-stored-graph pole. | rejected |
| R6 | Dependency-free acceptance-predicate readiness (TDD-outcomes) | Store `ready_when` predicates over evidence, derive the frontier live; write the acceptance proof first. | Strong A2 alternative to edge-derivation; overlaps survivors #4 (evidence-gated done) + #6 (derive frontier). Kept as the "predicates not edges" pole. | rejected |

Rejection summary: convergence was unusually high — ~30 of 37 frame candidates folded into the 7
survivors as cluster members; 6 distinct *alternatives* are kept revivable (R1–R6); the rest were
variants subsumed by a stronger sibling. Axis coverage (survivors): A1 (#3, #7), A2 (#2), A3 (#5),
A4 (#6), A5 (#1, #4) — all five covered, no deliberate gaps.

## Co-ideation log

| source | entered | idea / seed | outcome |
|--------|---------|-------------|---------|
| user-seed | Phase 0 | US1 — plugin-managed DAG runner / external control plane | cut → R3 (challenged by frames 2/4 — reshaped to in-engine projection + extended `/loop`) |
| user-seed | Phase 0 | US2 — per-node executor-recommendation engine | survived as #5 (reframed per-node → per-Kahn-layer by frames 3/4/5) |
| user-seed | Phase 0 | US3 — lean on GitHub sub-issues AS the DAG | survived as #7 (inverted by frame 4 — issues *project* the DAG, don't store it) |
| user-seed | Phase 0 | US4 — `/goal`-style autonomous outcome loop | survived as #6 (reshaped to gate-typed level-triggered reconcile by frames 1/3/5) |
| user-seed | Phase 0 | US5 — `/outcome plan\|next\|report` surface | survives as the thin command skin over #3/#6 |
| user-seed | Phase 0 | US6 — net-new DAG-node YAML schema | cut → R4 (challenged by frames 3/4 — reuse recursive `ExecutionSpec`, #2) |
| frame-agent | Phase 2 | Emission-as-precondition / wire `emit_workflow_script()` (frames 2+4) | survived as #1 |
| frame-agent | Phase 2 | Recursive `ExecutionSpec` saga-of-sagas (frames 3+4) | survived as #2 |
| frame-agent | Phase 2 | Derived projection / read-model (frames 1/2/3/5) | survived as #3 |
| frame-agent | Phase 2 | Evidence + cost rollup; task-token done (frames 1/4/5) | survived as #4 |
| frame-agent | Phase 2 | Kahn-layer selection + human-attention budget (frames 3/4/5) | survived as #5 |
| frame-agent | Phase 2 | Gate-typed / reconcile autonomy (frames 1/3/4/5) | survived as #6 |
| frame-agent | Phase 2 | Board as generated projection / third emitter (frame 4) | survived as #7 |
