---
title: Worker×Model Cache Scheduling — Implementation Plan
type: feat
status: active
date: 2026-06-27
origin: docs/brainstorms/2026-06-27-worker-model-cache-scheduling-requirements.md
---

# Worker×Model Cache Scheduling — Implementation Plan

## Summary

Port VECU's cost-first worker derivation + named-teammate residency into infiquetra by splitting it
along the seam infiquetra already has: **saga derives** (segments units, assigns stable resident
agent-ids, groups tiers) and **team-execution resides** (spawns named teammates, reuses them via
`SendMessage`, sheds at boundaries). The unit scheduled is the (worker×model) context cache, so the
engine pays context-creation once per reuse-relevant boundary instead of re-spawning fresh per phase
and per review round.

## Problem Frame

infiquetra re-pays context creation on two hot paths VECU has already closed. `team_emitter.py:107`
flattens every unit to a positional `worker-{i}`, discarding the `depends_on` and `{model,effort}`
tier that already live on `Unit` (`execution_spec.py:176,:182`) — so team-execution can't see a reuse
boundary even though saga computed one. And `consensus-protocol.md:51` re-spawns *fresh* reviewers
every consensus round, each re-reading the whole plan + diff + criteria from a cold cache.

The win is real where the engine runs hard (operator's VECU-laptop headroom cache-creation cost); it is
not gated on re-measurement — the operator + `/retro` is the measurement loop.

## Requirements

Carried from `docs/brainstorms/2026-06-27-worker-model-cache-scheduling-requirements.md` as the
reviewer's and `/work`'s checklist.

**Worker derivation & residency**

- R1. Workers SHALL be derived by grouping contiguous units sharing a plugin-directory boundary into
  segments — one resident worker per segment (replaces VECU's repo-change proxy; KTD2).
- R2. A resident worker SHALL be reused across its segment's units via `SendMessage`, never re-spawned
  per unit; spawned as a named persistent teammate, never an anonymous one-shot.
- R3. At a segment boundary the engine SHALL select **reuse** (same segment), **summary-handoff**
  (cross-segment dependency — fresh worker seeded with the prior worker's summary), or **fresh**
  (independent cross-segment).

**Review-loop residency**

- R4. Reviewers SHALL be spawned as named teammates on iteration 1; on iteration N≥2 only the
  sub-threshold reviewers SHALL be re-engaged via `SendMessage` (no re-spawn), preserving history so
  each reviews the delta.

**Model tiering**

- R5. Each segment's worker SHALL be assigned one `{model,effort}` tier as a unit via the existing
  per-unit tier, upgrade-only (downgrades rejected). No dynamic RMPA role-tiering is introduced.

**Dependency-wave scheduling**

- R6. The saga→team handoff SHALL carry `depends_on` + tier through `team_emitter.py` (both flattened
  today) so team-execution sees reuse boundaries and waves.
- R7. A worker with unmet `depends_on` SHALL NOT be spawned until its upstream units complete; no-dep
  workers start together (reactive unblocking, not spawn-then-idle-poll).

**Integration & durability**

- R8. Derivation SHALL reuse saga's `ExecutionSpec`; the coordinator-level `ready_frontier`
  (`outcome_spec.py:531`) remains source of truth for leaf ordering, with within-run waves subordinate.
- R9. A resident worker SHALL be shed rather than kept warm across a block expected to exceed the cache
  TTL horizon (~5 min); reuse is for temporally-tight loops.
- R10. R15a live context-GC is excluded — no harness lever exists (KTD5).

## Key Technical Decisions

- **KTD1 — Derivation is saga-side; residency runtime is team-execution-side.** The structured data
  (`Unit.depends_on` `execution_spec.py:182`, `Unit.tier` `:176`) already lives in saga's
  `ExecutionSpec` and is discarded by `team_emitter.py:107`. So segmentation, agent-id assignment, and
  tier-grouping go saga-side at the `recompile_for_tier`→`_emit_team_structure` seam
  (`execution_spec.py:742`); team-execution consumes the emitted ids and implements the named-teammate
  reuse. No new `worker_derivation.py` in team-execution. *Rejected:* VECU's team-execution-side
  derivation — correct for VECU's primitive saga, wrong here where the data is already saga-side.
- **KTD2 — Segment boundary = plugin directory.** `plugins/<name>/` is the monorepo's natural context
  boundary; top-level clusters (`tests/`, `docs/`, `tools/`) are their own segments. VECU's repo-change
  proxy never fires in a single repo.
- **KTD3 — Stable agent identity = segment/unit id, replacing positional `worker-{i}`.** Residency
  needs a durable handle to `SendMessage`; a positional name breaks on any reorder
  (`team_emitter.py:107`).
- **KTD4 — Behavioral residency is markdown protocol; the testable surface is the saga-side data
  plumbing.** The reuse/wave/review-loop behaviors live in skills-based-plugin prose (no Python) and
  are validated by `/doc-review` + operator runs + headroom telemetry. The Python units (un-flatten,
  segmentation) carry real pytest coverage. This is honest, not a gap: the cache-saving is observed in
  use, consistent with the solo-operator measurement loop.
- **KTD5 — R15a context-GC excluded.** Claude Code exposes no live `tool_result` pruning lever
  (Messages-API-only); structural shed (fresh worker at a boundary) is the only available eviction.

## High-Level Technical Design

```
   saga (derives)                              team-execution (resides)
   ─────────────────────────────              ──────────────────────────────
   ExecutionSpec.units[]                       Step A7 worker table
     unit_id, depends_on, tier   ──U1 emit──▶   | agent-id | role | deps | tier |
            │                                            │
        U2 segment                              U3 spawn named teammate
   group by plugin-dir, one                     (name + run_in_background),
   resident agent-id + tier                     reuse across segment via
   per segment                                  SendMessage, shed at boundary
            │                                            │
   team_emitter.emit_team_structure ───────▶    U5 reactive wave: hold a
   (un-flattened: ids+deps+tier)                worker until depends_on done

   consensus-protocol.md ── U4 ──▶ named reviewers; re-engage <9.0 via SendMessage (independent)
```

## Implementation Units

### U1. Un-flatten the saga→team handoff

**What:** In `team_emitter.py` `emit_team_structure` (`:70-143`), replace the positional
`agent = f"worker-{i}"` (`:107`) with the unit's stable id, and add `Depends-on` + `Tier` columns to
the worker table sourced from `Unit.depends_on` and `Unit.tier`. Foundation — everything downstream
needs these emitted.

**Files:** `plugins/saga/scripts/team_emitter.py`

**Test scenario:** `tests/test_team_emitter.py` — a multi-unit spec with `depends_on` + distinct tiers
emits stable unit-ids as agent names (not `worker-1`), and the table carries the deps + tier columns;
a unit with no deps renders an empty deps cell, not a crash.

**Depends on:** none.

### U2. Saga-side segmentation + resident agent-id derivation

**What:** In `execution_spec.py`, before the team arm of `recompile_for_tier` (`:742`), add a
derivation pass that groups contiguous units sharing a plugin-directory boundary (KTD2) into segments,
assigns one stable resident agent-id per segment, and computes a monolithic per-segment tier as the
upgrade-only max of member tiers (R5). Annotate units so U1's emitter renders the segment id as the
agent name.

**Files:** `plugins/saga/scripts/execution_spec.py` (consumed by `team_emitter.py`)

**Test scenario:** `tests/test_workflow_emitter.py` — consecutive same-plugin-dir units collapse to one
agent-id; a plugin-boundary crossing opens a new segment; the segment tier is the upgrade-only max
(a `haiku` + `opus` segment tiers `opus`, never down to `haiku`); independent segments get distinct ids.

**Depends on:** U1.

### U3. Worker residency runtime protocol (team-execution)

**What:** In `SKILL.md`, augment Step A7's worker table (`:218-260`) to carry the stable agent-id
column, and Step B1 (`:294-297`) to spawn each worker as a **named persistent teammate** (`Agent` with
`name` + `run_in_background`), reuse it across its segment's units via `SendMessage` (no per-unit
re-spawn), and shed it at a segment boundary or when a block is expected to exceed the cache-TTL horizon
(R2, R3, R9).

**Files:** `plugins/team-execution/skills/team-execution/SKILL.md`

**Test expectation:** none — markdown protocol in a skills-based plugin (KTD4); validated by
`/doc-review` + operator runs.

**Depends on:** U1, U2.

### U4. Review-loop reviewer residency (team-execution) — independent quick win

**What:** In `consensus-protocol.md`, change B3a (`:26`) to spawn reviewers as named teammates and
record their handles, and B3e (`:51`) to re-engage the same named reviewer via `SendMessage` for the
`<9.0` re-review (no fresh re-spawn), preserving each reviewer's history so it reviews the delta (R4).

**Files:** `plugins/team-execution/skills/team-execution/references/consensus-protocol.md`

**Test expectation:** none — markdown protocol (KTD4); validated by `/doc-review` + operator runs.

**Depends on:** none — independent of worker derivation; can land first / in parallel.

### U5. Reactive-unblock waves (team-execution)

**What:** In `SKILL.md` Step B1, add the rule that a worker with unmet `depends_on` is not spawned
(paying creation) until its upstream units complete; no-dep workers start together (R7). Rides on U1's
emitted `depends_on`.

**Files:** `plugins/team-execution/skills/team-execution/SKILL.md`

**Test expectation:** none — markdown protocol (KTD4).

**Depends on:** U1, U3.

### U6. Release surfaces + drift guards

**What:** Bump `plugins/team-execution/.claude-plugin/plugin.json` (2.2.0 → 2.3.0) + its CHANGELOG;
bump `plugins/saga/.claude-plugin/plugin.json` + its CHANGELOG for the `execution_spec`/`team_emitter`
changes; update `.claude-plugin/marketplace.json`; keep any version-drift guard green. Per the CLAUDE.md
release-surface rule.

**Files:** the two `plugin.json` + two `CHANGELOG.md` + `.claude-plugin/marketplace.json`,
`tests/test_release_triad.py` as needed.

**Test scenario:** `tests/test_release_triad.py` + the two plugin validators pass; marketplace entries
match plugin versions.

**Depends on:** U1–U5.

## Scope Boundaries

**In scope:** un-flatten handoff, saga-side segmentation + tier-grouping, worker residency runtime,
review-loop residency, reactive waves, release surfaces.

**Deferred to follow-up work:** warm-pool / crew-pairing residency alternatives (revisit only if
named-teammate residency proves insufficient); a formal within-run Kahn-wave queue (reactive unblocking
first — saga's coordinator frontier does the heavy sequencing).

**Out — forced:** R15a live context-GC (no harness lever; KTD5). **Out — decided:** dynamic RMPA
reviewer/scanner tiering (measured-and-killed in VECU; R5).

## Risk Analysis & Mitigation

- **Load-bearing seam.** `execution_spec.py` / `team_emitter.py` are on the `/work` execution path; a
  regression there breaks all backends. *Mitigation:* U1/U2 carry real pytest coverage; the emitter
  change is additive (new columns + id source), not a control-flow rewrite; gate via `/doc-review`
  before merge.
- **Behavioral parts are prose-validated.** The actual cache-saving lives in U3/U4/U5 markdown and has
  no pytest. *Mitigation:* this is inherent to skills-based plugins; correctness is `/doc-review` + the
  operator observing headroom cost on the next real run (the accepted measurement loop, not a gap).
- **TTL realism.** A worker kept resident past ~5 min evicts and re-pays creation anyway. *Mitigation:*
  R9 sheds at the TTL horizon; reuse is scoped to tight loops (review rounds, sequential segment units).

## Sources / Research

- Requirements: `docs/brainstorms/2026-06-27-worker-model-cache-scheduling-requirements.md`.
- Ideation: `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` — S-1 (build-first).
- infiquetra seams: `plugins/saga/scripts/team_emitter.py:107` (flatten),
  `plugins/saga/scripts/execution_spec.py:176,:182,:742` (Unit fields + team seam),
  `plugins/saga/scripts/outcome_spec.py:531` (coordinator frontier),
  `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:26,:51` (review loop),
  `plugins/team-execution/skills/team-execution/SKILL.md:218,:294` (worker derive/spawn).
- Tests: `tests/test_team_emitter.py`, `tests/test_workflow_emitter.py`, `tests/test_release_triad.py`.
- VECU reference: `../coxauto/vecu-claude-plugins` (`vecu-team-execution` 3.15.0) — `worker_derivation.py`,
  `SKILL.md:598,667,730`, `DECISIONS.md:134,:203`.
