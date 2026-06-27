---
date: 2026-06-27
topic: worker-model-cache-scheduling
maturity: requirements-ready
source: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md — S-1 "Schedule the (worker×model) Cache, Not the Worker"
---

# Worker×Model Cache Scheduling — Requirements

## Summary

Port VECU's cost-first worker derivation + named-teammate residency into infiquetra's
`team-execution` (2.2.0) and thread it through `saga`'s (0.38.0) existing
`execution_spec`/`team_emitter` seam, so the engine pays context-creation cost once per
reuse-relevant boundary instead of re-spawning fresh per phase and per review round. The unit
scheduled and billed is the **(worker×model) context cache**, not the task or the model tier.

## Problem Frame

The expensive event in a multi-agent run is context **(re)creation**, not token throughput. Today
infiquetra re-pays that cost on two hot paths that VECU has already closed on its side:

- `team-execution` spawns workers fresh per phase and re-spawns **fresh reviewers every consensus
  round** (`plugins/team-execution/skills/team-execution/references/consensus-protocol.md`) — each
  re-reads the full plan + diff + criteria from a cold cache.
- `saga`'s `team_emitter.py` **flattens** `depends_on` edges and per-unit tiers on the way to the
  team backend, so team-execution can't even see where a reuse boundary or a dependency wave is.

The cost is real and observed — it shows up as cache-creation spend on the operator's heavy
real-codebase runs (VECU-laptop headroom telemetry + the after-action reports at
`jeff.cox@10.220.1.148:workspace/coxaut/vecu-custody-service`). The engine does its hard work
downstream of where it is edited, so the signal is strongest where the engine *runs*, not where it
*lives*. This is the motivation; it is not gated on re-measurement.

## Key Decisions

- **D1 — Residency mechanism = named-teammate, segment-scoped.** Not a warm pool, not crew-pairing.
  Workers are spawned as named persistent teammates (`Agent` with `name` + `run_in_background`) and
  re-engaged via `SendMessage`. This resolves the ideation doc's one open fork and matches VECU's
  shipped design (`vecu-team-execution` 3.15.0, `SKILL.md:598/667`).
- **D2 — A segment is a run of contiguous phases sharing a reuse boundary.** One resident worker per
  segment; cross-segment dependency → summary handoff; independent cross-segment → fresh worker.
  **The boundary signal is infiquetra-specific** — VECU shards on *repo* change, which never fires in
  a single monorepo; infiquetra must shard on a plugin-directory / file-cluster boundary instead
  (see R3, OQ3).
- **D3 — Cache-reuse is first-order; model tier is chosen per segment as one unit.** "Group first,
  then tier the whole group." Worker tiering maps the segment's file paths → archetype → tier,
  upgrade-only (never downgrade within a segment).
- **D4 — Residency is bounded by cache-TTL realism.** Cache ≈ 5-min TTL → reuse captures a hit only
  when it is temporally tight (back-to-back review rounds, sequential segment phases). A worker
  expected to block past that horizon is shed and respawned rather than kept warm — keeping it warm
  pays carry cost (long-lived workers are cache-read-dominated) for an evicted cache.
- **D5 — Dynamic role-tiering (RMPA) stays out.** infiquetra already has static per-role model
  frontmatter (reviewers→opus, testers→sonnet, scanners→haiku). VECU measured the full dynamic
  reviewer/scanner tiering machinery across ~25 runs and killed it (`DECISIONS.md:134`); only the
  *worker-lane* tiering (D3) is in scope.
- **D6 — R15a context-GC is out, by harness limit.** Claude Code exposes no lever for live
  `tool_result` pruning (`context editing` is Messages-API-only — VECU `DECISIONS.md:203`). The only
  available eviction is structural: a fresh worker at a segment boundary.

## Requirements

### Worker derivation & residency

- R1. The engine SHALL derive workers by grouping contiguous plan phases that share a reuse boundary
  (D2) into segments, producing exactly one resident worker per segment.
- R2. A resident worker SHALL be reused across its segment's sequential phases — re-engaged via
  `SendMessage`, never re-spawned per phase.
- R3. The segment boundary signal SHALL be a monorepo-appropriate proxy (plugin directory / file
  cluster), not VECU's repo-change proxy, so segmentation is meaningful inside one repository.
- R4. At a segment boundary the engine SHALL select one of: **reuse** (same segment),
  **summary-handoff** (cross-segment dependency — fresh worker seeded with the prior worker's
  `SendMessage` summary, not its full context), or **fresh** (independent cross-segment).
- R5. Every worker SHALL be spawned as a named persistent teammate (`Agent` name +
  `run_in_background`), never an anonymous one-shot subagent.

### Review-loop residency

- R6. Reviewers SHALL be spawned as named persistent teammates on iteration 1.
- R7. On iteration N≥2, only the reviewers that scored below the consensus threshold on N−1 SHALL be
  re-engaged via `SendMessage` (no re-spawn), preserving each reviewer's history so it reviews the
  **delta** ("was what I flagged fixed?") rather than re-deriving its full critique.

### Model tiering

- R8. Each segment's worker SHALL be assigned a model + effort tier as a single unit, mapped from the
  segment's file paths via an archetype→tier table, honoring per-unit upgrades and rejecting
  downgrades.
- R9. Reviewer / scanner / tester role tiering SHALL remain static per-agent frontmatter; no dynamic
  RMPA tiering machinery is introduced (D5).

### Dependency-wave scheduling

- R10. A worker whose dependencies are unmet SHALL NOT be spawned (paying creation) until its upstream
  tasks complete — reactive unblocking, not spawn-then-block-and-idle-poll. Workers with no unmet
  dependencies start together.
- R11. The saga→team-execution handoff SHALL carry `depends_on` edges and per-unit tier hints through
  `team_emitter.py` (both flattened today), so team-execution can see reuse boundaries and waves.

### Integration with saga

- R12. Worker derivation SHALL reuse saga's existing `execution_spec` / OutcomeOrchestrator frontier
  rather than duplicating it: the coordinator-level `ready_frontier` remains the source of truth for
  leaf ordering, and any within-run wave logic is subordinate to it.
- R13. team-execution SHALL gain both the residency protocol and a worker-derivation step; it has
  neither at 2.2.0 (no `scripts/`, no residency machinery).

## Key Flows

- **F1 — Derivation.** Plan phases → segment by boundary proxy → one resident worker per segment with
  its unit tier → spawn named teammates at wave readiness (R1, R3, R5, R8, R10).
- **F2 — Segment reuse.** Phase *k* completes → same-segment phase *k+1* → `SendMessage` to the
  resident worker (cache warm) → no re-spawn (R2).
- **F3 — Review consensus loop.** Iter-1: spawn all named reviewers → score → iter-2: `SendMessage`
  only the sub-threshold reviewers → they review the delta → repeat to consensus or max iterations
  (R6, R7).
- **F4 — Cross-segment handoff.** Segment A's worker finishes → segment B (depends on A) gets a fresh
  worker seeded with A's *summary*, not A's full context → B starts on a lean cache (R4).

## Scope Boundaries

**In scope:** named-teammate residency, monorepo-aware segment derivation, review-loop residency,
worker-lane tiering, reactive-unblock waves, handoff un-flattening.

**Deferred for later:** warm-pool and crew-pairing residency alternatives (VECU did not build them;
revisit only if named-teammate residency proves insufficient); a formal within-run Kahn-wave queue
(reactive unblocking first — saga's coordinator frontier already does the heavy sequencing).

**Out — forced:** R15a live context-GC (no harness lever; D6).
**Out — decided:** dynamic RMPA reviewer/scanner tiering (measured-and-killed in VECU; D5).

## Dependencies / Assumptions

- **Harness.** Named agents + `SendMessage` preserve a teammate's context across turns; whether a
  reuse is a *cache hit* depends on the ~5-min TTL (assumption: the in-scope reuse loops — review
  rounds, sequential segment phases — are tight enough to land inside it). Confirmed absent: any
  PreCompact lever and any live context-editing lever.
- **VECU blueprint.** `../coxauto/vecu-claude-plugins` (`vecu-team-execution` 3.15.0) is the reference
  implementation for the residency protocol, `worker_derivation.py`, and the review-loop pattern.
  infiquetra `saga` (0.38.0) is *ahead* of VECU `saga` (0.22.0), so the saga-side integration is
  infiquetra-specific, not a port.
- **Cost motivation.** Creation-dominated worker spend is the operator's observed telemetry plus the
  B8 creation-tax/carry-cost model; it is the rationale for the build, not a gate on it.

## Outstanding Questions (deferred to planning)

- **OQ1.** Does `worker_derivation` live in `team-execution` (as in VECU) or in saga's
  `execution_spec` (where infiquetra's dependency + tier data already sits)? Architecture call for
  `/plan`.
- **OQ2.** Are within-run reactive waves worth building for infiquetra at all, given saga's
  coordinator-level `ready_frontier` already sequences leaves? `/plan` reconciles the overlap.
- **OQ3.** Exact monorepo boundary proxy for D2/R3 — plugin directory, top-level path cluster, or
  declared file-set divergence? Needs a concrete rule before derivation is implemented.

## Sources / Research

- Ideation survivor: `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` — S-1 (build-first),
  Reconciliation §2026-06-27.
- VECU reference: `../coxauto/vecu-claude-plugins` —
  `plugins/vecu-team-execution/scripts/worker_derivation.py` (segment/tier),
  `.../skills/team-execution/SKILL.md:598,667,730` (named-teammate residency + review loop),
  `docs/engineering-journal/DECISIONS.md:134` (RMPA HALT), `:203` (context-GC unbuildable),
  `docs/plans/issue-92-team-execution-worker-derivation.md` (cost frame).
- infiquetra current state: `plugins/team-execution/.../consensus-protocol.md` (fresh re-spawn gap),
  `plugins/saga/scripts/team_emitter.py` (flattens depends_on + tiers),
  `plugins/saga/scripts/execution_spec.py` (`ready_frontier`, `dependency_layers`),
  `plugins/saga/scripts/outcome_spec.py` (coordinator frontier).
- Operator telemetry: VECU-laptop headroom cache-creation cost; AARs at
  `jeff.cox@10.220.1.148:workspace/coxaut/vecu-custody-service`.
