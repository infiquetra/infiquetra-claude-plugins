---
date: 2026-06-25
topic: operator-outcome-orchestration
maturity: requirements-ready
source: docs/ideation/2026-06-25-operator-outcome-orchestration-ideation.md (consolidated brief — 16 components, architecture reframe, storage model) + docs/ideation/2026-06-25-operator-outcome-orchestration-ux-walkthrough.md
---

# Operator Outcome-Orchestration — Requirements

## Summary

Build an `OutcomeOrchestrator` into the saga plugin: a coordinator that owns a DAG of leaf sagas and
lets the operator drive a whole **outcome** — across sessions, worktrees, and machines — from a thin
`/outcome` surface, with team-execution / mission-control / deploy / cc-workflows-ultracode acting as
per-subplot executors. It is built whole (all components co-equal), not phased.

## Problem Frame

The operator already runs multi-subplot outcomes by hand — a multi-PR campaign, an engine-merge across
many commands — holding the dependency graph in his head, hand-writing prompts to other sessions, and
tracking which thread is where across worktrees that get cleaned up. That manual coordination is the
cost: attention spent *routing* instead of *deciding*, state lost when a worktree or session dies, and
no measured answer to whether a DAG of right-sized executions actually beats one long thread.

The source conversation converged on a control plane *outside* the chat that holds the DAG so the
operator doesn't have to. The pain is concrete and recurring (the bg-worktree ↔ saga state-loss
problem is this same pain one altitude down), and saga already has most of the machinery — a durable
tick model, a per-run DAG with Kahn layering, a backend recommender — just never lifted above a single
linear work thread.

## Actors

The outcome model has five meaningfully-distinct parties.

- A1. **Operator** — starts outcomes, prunes the draft DAG, answers gates and ambiguities, owns
  parent-close. Interrupt-handler, not babysitter.
- A2. **OutcomeOrchestrator** — the coordinator; owns the DAG, locks, frontier, attention routing.
  Never executes inside an execution context.
- A3. **Leaf saga** — a strictly linear executor (plan→work→qa) that does one subplot's work and
  publishes a completion event up.
- A4. **Executor backend** — where a leaf actually runs: inline / fork / subagent / team-execution /
  cc-workflows-ultracode / `/goal`.
- A5. **GitHub / mission-control** — the canonical system of record (issue/PR tree = completion truth;
  board = generated portfolio projection).

## Key Decisions

These framing choices are settled; Requirements and Flows below inherit them.

- **Coordinator ≠ a bigger saga.** The outcome is a distinct `OutcomeOrchestrator`, not the linear
  `Saga` dataclass — `lifecycle_phase` cannot represent a concurrent DAG (an outcome whose subplot A is
  in `work`, B in `qa`, C blocked in `plan` has no single phase). The orchestrator *reuses* saga
  machinery; the leaves *are* sagas. Self-similar **operator experience**, not self-similar **data
  structure**.
- **All components co-equal.** No secondary tier and no phasing — the build is complete only when every
  component ships. "All or nothing," confirmed.
- **Independent branches survive a block.** When a subplot hard-blocks, only its downstream subtree
  pauses; independent branches keep running; blocks bubble into one consolidated page; the operator can
  manually halt-all for a plan-level block.
- **Degrade is conditional on presence.** Halt + page when the operator is attending the leaf;
  auto-degrade one rung (`cc-workflows → team-execution → inline`) when the leaf is autonomous and the
  operator is away, recording a visible receipt; a leaf tagged guarantee-bearing halts regardless. In
  practice this only bites cc-workflows — team-execution always runs (see below).
- **team-execution is a native-agent-teams wrapper.** Its tmux is entirely vestigial display
  scaffolding (verified: zero load-bearing references); strip all of it and delete the `team-setup`
  command. Validators run as native agent-team subagents already.
- **GitHub-anchored store, split by facet.** The committed outcome-spec artifact is canonical for
  structure + decision trail + cost; GitHub issues/PRs are canonical for completion; the local store is
  a performance-only cache. Cold-reentry on any machine reconstructs the whole outcome — including the
  "why" — from the repo + GitHub, losslessly.
- **Thin `/outcome`, native leaf verbs.** The operator drives coordinator-only actions from an explicit
  `/outcome` surface that hands into the native `/work` / `/code-review` / `/resume` on a leaf when
  hands-on — explicit altitude seam, reuse-maximal.
- **Per-subplot completion contract.** Code subplots unlock dependents on PR-merged; non-code on the
  local completion tick. Non-gated clean subplots auto-merge so an autonomous DAG flows.
- **Bespoke coordinator, not composed from existing tools.** A CI/Actions DAG + sub-issues + a board
  could sequence work, but cannot pick and recommend a per-subplot *executor* (inline/fork/team/
  workflow/`/goal`) under an attention+cost budget, give each leaf saga's full plan→work→qa→review
  lifecycle, route the operator's *attention* (the consolidator, gates, cold-reentry-with-why), or
  instrument realized cost to prove the thesis. The orchestrator earns its existence on those four; it
  reuses GitHub / Actions / the board as projections and gates, not as the engine.

## Requirements

What must be true of the built capability. Grouped by concern; IDs continuous.

**Coordinator architecture**

- R1. The outcome is a distinct `OutcomeOrchestrator` built into the saga plugin, reusing its machinery
  (the `execution_spec` DAG / Kahn layering / emitters, `recommend_execution_backend`, the
  `save` / `read_ticks` / `restore` tick model) — not the linear `Saga` dataclass. It owns the
  dependency graph, concurrency locks, and operator-attention routing.
- R2. Leaf subplots are strictly linear sagas — the executors. The coordinator never runs inside an
  execution context; it routes, it does not execute.
- R3. The coordinator degrades only *leaves*, never itself — it must never collapse the orchestration
  to a single inline context (which would serialize the whole DAG into one agent and lose the plot).
- R4. All components in this document are co-equal core. The build is not "done" until every one ships;
  none is marked secondary or deferred-within-build.

**Dispatch and executors**

- R5. Each subplot routes to its backend through a single dispatcher seam, built by promoting the
  by-mode fork off `recompile_for_tier`'s downgrade-only path and wiring the existing `team_emitter`.
  When a chosen backend cannot actually run, the seam emits a visible HALT-not-degrade receipt rather
  than silently substituting.
- R6. The per-subplot executor menu is the full set: inline / fork / subagent / team-execution /
  cc-workflows-ultracode / `/goal`. Forks (share the parent prompt cache) and `/goal` (bounded
  autonomous loops) are first-class, not just the current three backends.
- R7. The backend is recommended by `recommend_execution_backend`, auto-bound for non-gated subplots,
  and operator-overridden only — decided at the ready-frontier under a remaining attention/token
  budget, not per-node in isolation. Overrides feed the R12 override telemetry consumed by `/optimize`.
- R8. team-execution is reshaped to a native-agent-teams wrapper: remove every tmux reference, delete
  the entire `team-setup` command, and run reviewers/validators as native agent-team subagents that
  return a consensus verdict + evidence to the coordinator. The `.claude/`-git-ignored validator-state
  safety check is re-homed into the execution skill's pre-execution phase so it survives the deletion.

**Completion, flow, and merge**

- R9. Dispatch and completion ride one bidirectional envelope: a `/resume <subplot-saga-id>` re-entry
  token out (not a drift-prone pasted prompt) carrying a return channel, and a completion tick back via
  `save()`. "Done" is a **parent-owned barrier predicate over the returned evidence**, not a child's
  self-report, and HALTs on an unmet contract.
- R10. The DAG unlocks the next Kahn layer from completion events written as **per-leaf immutable
  files** in the shared store's completion directory — each leaf drops its own
  `<subplot-id>-<timestamp>` event, saga's one-file-per-tick model lifted to the shared store, so
  concurrent leaves never contend on one file — never a racy last-writer-wins merged index. The
  coordinator's own DAG / lock / frontier state stays out of any merged summary; those mutations are
  single-writer (the orchestrator), so R13's locks cover only them, not the completion log.
- R11. Completion is a per-subplot contract: a code subplot unlocks its dependents on **PR-merged**; a
  non-code subplot (docs, research) on the **local completion tick**. The contract is the concrete form
  of R9's barrier predicate.
- R12. A non-gated subplot **auto-merges** (squash) to unlock its dependents — where "clean" means all
  required CI checks green AND the reviewer-consensus threshold met (team-execution backend) or
  `/code-review` clean of P0/P1 (other backends) AND not flagged risky/destructive. The merge is a
  server-side PR squash-merge (the leaf's own work already passed the local pre-push gate), so an
  autonomous DAG advances through code layers unattended; gated, risky, or non-clean subplots wait for
  the operator.

**Concurrency and state**

- R13. Concurrent subplot execution is safe by construction: locks / idempotency / duplicate-dispatch
  prevention, with execution state namespaced by subplot id (e.g. `.../<repo>/<subplot_id>/`, which
  doubles as the dispatcher's return address). R7's frontier dispatch and R17's auto-advance depend on
  this safety existing first.
- R14. Outcome state is portable across machines / worktrees / sessions via an explicit export/import
  story, so the DAG survives worktree cleanup and the operator's real multi-machine pattern.
- R15. The runner maintains one durable persistent session + worktree **per sub-outcome** (not per
  subtask), naming and owning it, coupled to the re-entry token (R9) and portable state (R14).

**Operator surface**

- R16. The operator drives from a thin explicit `/outcome` surface (coordinator-only actions: start,
  advance the frontier, report, resume) that hands into the native `/work` / `/code-review` / `/resume`
  on a leaf when hands-on. Explicit altitude seam; the leaf verbs are reused, not shadowed.
- R17. The operator is an interrupt-handler over a pull-derived cockpit: the runner auto-advances
  non-gated subplots, status is **derived on read** (no operator-writable status field), and it pages
  the operator only at gates, unsatisfiable barriers, ambiguity, and parent-close. A healthy steady
  state is an empty surface.
- R18. When several leaves block at once, the attention consolidator bubbles them into **one** ranked
  prompt — ordered **type-tier first** (ready-to-ship gates → decisions/ambiguities → failures), then
  unblock-leverage within each tier — never N separate pages.
- R19. `/outcome report` is a derived-on-read digest regenerated to a markdown artifact under
  `docs/outcomes/` (overwritten from state on demand and on completion, never hand-edited so it
  physically cannot drift). It carries, per subplot, the evidence (PR / CI / review / qa), plus the
  realized cost rollup (R24), the decision trail (the "why" for cold-reentry), and current state.

**Decomposition**

- R20. Decomposition is draft-then-review: the runner drafts the subplot DAG (recursion via a
  subplot's `orchestration_ref` pointing at a child spec — net-new dispatch semantics, not a state
  store) and the operator reviews it — **pruning nodes and adding / removing / redirecting the
  `depends_on` edges**, not only deleting nodes. No layer dispatches until the operator has approved the
  ready frontier's edges; operator-review-before-first-dispatch is the mandatory safety net for a
  mis-drafted graph. The operator never hand-authors the whole graph from scratch.
- R21. The DAG grows lazily (later layers elaborate as evidence arrives), elaborates an over-sized
  subplot in place, and promotes a subplot from a cheap row to its own child saga only when it earns
  it. These are four distinct mechanisms (draft/prune, lazy-grow, elaborate-in-place, promote), each
  built deliberately with its own edge cases.

**Failure and degradation policy**

- R22. When a subplot hard-blocks, only its downstream subtree pauses; subplots with no dependency path
  to the block keep running. The operator can manually halt-all when a block is plan-level (it reveals
  the approach is wrong), but the default optimizes the node-local case.
- R23. Leaf degradation is conditional on operator presence: halt + page when the operator is attending
  the leaf; auto-degrade one rung (`cc-workflows → team-execution → inline`) when the leaf is autonomous
  and the operator is away, recording a visible downgrade receipt surfaced in the report; a leaf tagged
  guarantee-bearing halts even when away.

**Economics and portfolio**

- R24. The runner records per subplot — executor used, rough token/cost, wall-clock, operator touches,
  retries, accepted evidence — and rolls it up per outcome. This is the falsifiable proof of the
  cost-vs-operator-time thesis and gives `/optimize` and `/retro` a portfolio-shaped consumer.
- R25. The subplot-DAG progress auto-projects into mission-control as a generated **secondary**
  portfolio view (no manual `/handoff`); closing a parent stays the operator's deliberate keystroke.

**Storage**

- R26. The durable record splits by **facet**: the version-controlled outcome-spec artifact (and its
  companion decision/cost log), committed + pushed, is canonical for **structure** — subplot nodes,
  their `depends_on` edges, the decision trail (R19), and the cost rollup (R24) — while **GitHub**
  issues/PRs are canonical for **completion state** (PR-merged / issue-closed). The artifact is the
  single source for the node set; GitHub sub-issues are a generated projection of it, so structure and
  completion cannot drift against each other.
- R27. The git-common-dir store is a **pure performance cache** (verified to resolve identically from
  every worktree and survive worktree cleanup). Because structure + trail + cost live in the committed
  artifact and completion lives in GitHub, any machine reconstructs the **whole** outcome — including
  the "why" — by pulling the repo and reading GitHub issue/PR state, with no dependence on the cache.
  Reconstruction is non-lossy.
- R28. Leaf saga ticks stay per-worktree (volatile, git-ignored, discarded on cleanup); a leaf's
  durable output is its merged PR plus a completion event published up to the shared store as its own
  immutable file (no shared-file append — multi-writer-safe by construction, mirroring saga's
  one-file-per-tick model).

## Key Flows

The operator-visible behavior at outcome altitude.

- F1. **Start.** Operator runs `/outcome` on an objective; the runner drafts the subplot DAG with a
  recommended backend per node; the operator prunes/edits; the runner dispatches the ready frontier.
- F2. **Autonomous advance.** The runner walks its ready-frontier, auto-binds backends, auto-advances
  non-gated subplots, and auto-merges clean ones to unlock the next layer. Surface stays empty while
  healthy.
- F3. **Block and consolidate.** One or more leaves block; independent branches keep running; the
  consolidator pages the operator **once**, type-tiered then leverage-ranked, each item with its
  context and why.
- F4. **Leaf completion and unlock.** A leaf finishes, writes a completion event up; per its contract
  (code → on merge, non-code → on tick) the dependent layer unlocks; evidence and cost land in the
  rollup.
- F5. **Cold re-entry.** Days later, on any machine, `/outcome resume` reconstructs from the committed
  spec artifact + GitHub: where (layer/percent), what's done, what's left, why it paused, and the
  decision trail — a long gap costs nothing.
- F6. **Report.** `/outcome report` regenerates the digest from state: delivered subplots + evidence,
  realized cost rollup, decisions taken, current state — a readable artifact that cannot drift.

## Acceptance Examples

The conditional requirements, pinned so planning cannot invent the edge behavior.

- AE1. **Covers R23 (degrade).** **When** the operator is actively attending a leaf whose chosen
  cc-workflows backend is unavailable, the runner HALTs that leaf and pages the operator. **When** the
  same leaf is autonomous and the operator is away, the runner degrades it one rung to team-execution,
  records a visible receipt, and continues — **unless** the leaf is tagged guarantee-bearing, in which
  case it halts and waits regardless.
- AE2. **Covers R11 (unlock).** **When** subplot B depends on a **code** subplot A, B unlocks only after
  A's PR is merged. **When** B depends on a **non-code** subplot A (a research or docs subplot with no
  PR), B unlocks on A's completion tick.
- AE3. **Covers R12 (auto-merge).** **When** a non-gated subplot's CI is green and its review passed,
  the runner squash-merges it and unlocks dependents without the operator. **When** the subplot is
  gated, flagged risky/destructive, or non-green, it stops at the merge and waits.
- AE4. **Covers R22 (failure cascade).** **When** subplot C hard-blocks, its downstream subtree pauses
  but sibling subplots with no dependency on C keep running to completion; the operator returns to "C
  blocked, D and E done," not a stalled DAG.
- AE5. **Covers R18 (consolidator).** **When** a gate (subplot ready to ship), an ambiguity (needs a
  decision), and a failure (needs a fix) block simultaneously, the single prompt lists the gate first,
  the ambiguity second, the failure third — and within a tier, the item holding up the most downstream
  work first.

## Scope Boundaries

What this build includes, defers to planning, and deliberately excludes.

**In scope (built whole):**

- Every requirement R1–R28 — the coordinator, dispatch seam, envelope, concurrency/state, operator
  surface, decomposition, failure/degrade policy, economics, and storage.
- The team-execution friend-plugin change (R8): strip tmux, delete `team-setup`, re-home the
  validator-state check.

**Deferred to `/plan`** (mechanism, not product — answered during planning):

- Exact paths, file formats, and schemas (the outcome-spec DAG format, the shared-store layout, the
  `/outcome report` markdown layout).
- The exact `/outcome` subcommand vocabulary.
- The "guarantee-bearing" leaf-tagging mechanism (how a leaf is marked halt-not-degrade).
- The validator-state-check re-home mechanic (where in the execution skill's pre-phase it lands).

**Outside the core build** (add only on demonstrated need):

- A networked cross-host completion stream (e.g. Redis) for sub-second completion when subplots
  genuinely fan across machines — GitHub + the git-common-dir cache cover the single-machine,
  many-worktree common case. Build it only when cross-host realtime is actually required.

## Dependencies / Assumptions

What this rides on, and the load-bearing assumptions to keep visible.

- Reuses saga machinery as the substrate: `execution_spec` (`dependency_layers` Kahn layering ~`:361`,
  per-unit `{model, effort}`, the emitters), `recommend_execution_backend`
  (`lifecycle_state.py:99`), and the `save` / `read_ticks` / `restore` tick model.
- **Reused vs net-new (verified against the code).** *Reused as primitives:* the Kahn layering
  *algorithm* (`dependency_layers`), the tick model (`save` / `read_ticks` / `restore`), the
  recommender, and `team_emitter`. *Net-new — no existing machinery (saga scripts carry zero
  `outcome` / `subplot` / publish-up tokens today):* the living cross-session DAG + frontier + locks,
  the parent-owned completion barrier (R9), the publish-up completion events (R28), the shared outcome
  store (R27), and `orchestration_ref`→child-spec recursion (R20) — `orchestration_ref` is presently a
  single-saga backend pointer (a spec path or workflow id), not a parent→child link, and the
  `execution_spec` DAG is computed at emit time within one run. Planning must scope the orchestration
  layer as net build, not adaptation.
- `team_emitter.py` (`emit_team_structure` ~`:71`) already emits a pure-markdown agent-team role spec
  with zero tmux; saga's dispatch consumes no tmux. **Verified** this session, correcting the brief's
  earlier "missing file" framing — the file exists and is tested.
- **Verified-absence assumption:** team-execution's 59 tmux references are *all* vestigial
  display/setup; none are load-bearing for Phase B execution (workers/reviewers/validators spawn as
  native subagents). Removal carries no execution risk. If planning finds a load-bearing reference this
  scan missed, R8's "zero risk" claim must be revisited.
- Binding journal decisions: KTD6 (halt-not-degrade vs the operator-absent recompile-down carve-out)
  underpins R23; KTD7 (the `save()` provenance guard) governs how R5/R23 record backend choices and
  downgrades; R9-of-the-tiering-campaign (one spec → two emitters, saga stores only the
  `orchestration_ref` pointer) underpins R5.
- mission-control / GitHub is assumed reachable for the canonical loop (R26); offline operation runs on
  the cache (R27) until reconcile. No root `STRATEGY.md` exists, so this doc and the ideation brief are
  the scope anchors.

## Success Criteria

What "built right" looks like for this all-or-nothing build.

- All R1–R28 ship together; no component is left as a stub.
- The cost thesis is **measurable**, not asserted — R24's rollup can answer "did the DAG of right-sized
  executions beat one long thread?" with real per-outcome numbers.
- Cold re-entry on a *different machine* after a multi-day gap reconstructs where / what / why with
  nothing lost (F5).
- An overnight autonomous run **progresses through code layers** (auto-merge unlocks dependents) rather
  than stalling at the first merge boundary.
- Concurrent blocks reach the operator as **one** ranked page, not N (R18).
- team-execution runs with **zero** tmux and no setup step, validators intact.

## Outstanding Questions

- **Resolve before planning:** none. The two store-architecture decisions raised in doc-review are
  resolved in the requirements above — structure + decision trail + cost live in the committed spec
  artifact, completion in GitHub, the cache is performance-only (R26/R27); completion events are
  per-leaf immutable files, multi-writer-safe by construction (R10/R28); node/edge drift is closed by
  making the spec the single source and sub-issues a projection (R26); and edge-review with
  review-before-dispatch is a named requirement (R20).
- **Deferred to planning:** exact paths/formats/schemas (the outcome-spec artifact format and its
  embedded decision/cost log, the completion-event file shape, the `/outcome report` layout); the
  `/outcome` subcommand vocabulary; the leaf "guarantee-bearing" tagging mechanism; the validator-state
  re-home mechanic; the artifact commit cadence (how often structure/trail/cost is committed); the
  operator's edge-review CLI affordance; and the trigger for introducing the networked completion
  stream.

## Sources / Research

Breadcrumbs for a planner reading cold.

- Ideation brief: `docs/ideation/2026-06-25-operator-outcome-orchestration-ideation.md` (16 components,
  the coordinator/executor reframe, the storage model, Codex + Antigravity second opinions).
- UX walkthrough: `docs/ideation/2026-06-25-operator-outcome-orchestration-ux-walkthrough.md`
  (illustrative operator experience at small and epic scale).
- Source problem: `docs/analysis/2026-06-25-claude-cache-and-orchestration-chatgpt-source.md`.
- Code substrate: `plugins/saga/scripts/execution_spec.py` (`dependency_layers`,
  `recompile_for_tier` ~`:708`, the emitters), `plugins/saga/scripts/team_emitter.py`
  (`emit_team_structure` ~`:71`), `plugins/saga/scripts/lifecycle_state.py:99`
  (`recommend_execution_backend`), `plugins/saga/scripts/saga.py:71` (the backend enum).
- team-execution current state: native-agent-teams execution in `plugins/team-execution/` Phase B; the
  vestigial tmux lives in `commands/team-setup.md`, `docs/agent-overflow.sh`, `docs/example_tmux.conf`,
  and `skills/team-execution/references/validator-pane-behavior.md`.
- Binding decisions: `docs/engineering-journal/DECISIONS.md` —
  `#parallel-refuteN-emitter-plan-work-wiring` (KTD6, KTD7),
  `#saga-tiering-execution-campaign-shipped` (the two-emitter / `orchestration_ref` model).
