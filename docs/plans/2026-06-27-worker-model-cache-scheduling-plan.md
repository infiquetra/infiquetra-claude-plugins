---
title: Worker×Model Cache Scheduling — Implementation Plan
type: feat
status: active
date: 2026-06-27
revised: 2026-06-27
origin: docs/brainstorms/2026-06-27-worker-model-cache-scheduling-requirements.md
---

# Worker×Model Cache Scheduling — Implementation Plan

## Summary

Port VECU's cost-first worker derivation + named-teammate residency into infiquetra by splitting it
along the seam infiquetra already has: **saga derives** (segments units, assigns one stable resident
agent-id per segment, groups tiers, derives segment-level deps) and **team-execution resides** (spawns
one named teammate per segment, reuses it via `SendMessage`, sheds at boundaries). The unit scheduled
is the (worker×model) context cache, so the engine pays context-creation once per reuse-relevant
boundary instead of re-spawning fresh per phase and per review round.

## Problem Frame

infiquetra re-pays context creation on two hot paths VECU has already closed. `team_emitter.py:107`
flattens every unit to a positional `worker-{i}`, discarding the `depends_on` and `{model,effort}`
tier that already live on `Unit` (`execution_spec.py:176,:182`) — so team-execution can't see a reuse
boundary even though saga computed one. And `consensus-protocol.md:51` re-spawns *fresh* reviewers
every consensus round (re-running B3a from `:26`), each re-reading the whole plan + diff + criteria from
a cold cache.

The win is real where the engine runs hard (operator's VECU-laptop headroom cache-creation cost); it is
not gated on re-measurement — the operator + `/retro` is the measurement loop.

## Requirements

Carried from `docs/brainstorms/2026-06-27-worker-model-cache-scheduling-requirements.md` as the
reviewer's and `/work`'s checklist.

**Worker derivation & residency**

- R1. Workers SHALL be derived by grouping contiguous units that share a plugin-directory boundary
  into segments — one resident worker per segment.
- R2. The plugin-directory boundary SHALL be computed from a per-unit declared file list (a new
  `Unit.files` field), since `Unit` carries no path data today (KTD2).
- R3. A resident worker SHALL be reused across its segment's units via `SendMessage`, never re-spawned
  per unit; spawned as a named persistent teammate, never an anonymous one-shot.
- R4. At a segment boundary the engine SHALL select **reuse** (same segment), **summary-handoff**
  (cross-segment dependency — fresh worker seeded with the prior worker's summary, not its full
  context), or **fresh** (independent cross-segment).

**Review-loop residency**

- R5. Reviewers SHALL be spawned as named teammates on iteration 1; on iteration N≥2 only the
  sub-threshold reviewers SHALL be re-engaged via `SendMessage` (no re-spawn), and the re-engagement
  context SHALL carry the **delta** since their last review, not the full diff.

**Model tiering**

- R6. Each segment's resident worker SHALL be assigned one `{model,effort}` tier as a unit — the
  upgrade-only max of its members' tiers (downgrades rejected). No dynamic RMPA role-tiering.

**Dependency-wave scheduling**

- R7. The saga→team handoff SHALL emit one worker row per **resident worker (segment)** — carrying the
  resident agent-id, the covered unit ids, the segment tier, and the segment-level `Depends-on` — not
  one row per unit (`team_emitter.py` emits per-unit today).
- R8. Segment-level dependencies SHALL be derived by collapsing the unit-level `depends_on` graph (drop
  intra-segment edges, aggregate cross-segment edges); a resident worker with unmet segment-deps SHALL
  NOT be spawned until its upstream segments complete (reactive unblocking).

**Integration & durability**

- R9. Derivation SHALL annotate via a copy or side mapping; it SHALL NOT mutate the shared
  `ExecutionSpec` (`recompile_for_tier` runs per-tier on one shared object).
- R10. The within-run segment frontier SHALL be subordinate to saga's coordinator-level
  `ready_frontier` (`outcome_spec.py:531`), which remains source of truth for leaf ordering.
- R11. A resident worker SHALL be shed rather than kept warm across a block expected to exceed the
  cache TTL horizon (~5 min); reuse is for temporally-tight loops.
- R12. R15a live context-GC is excluded — no harness lever exists (KTD7).

## Key Technical Decisions

- **KTD1 — Derivation is saga-side; residency runtime is team-execution-side.** The structured data
  (`Unit.depends_on` `execution_spec.py:182`, `Unit.tier` `:176`) already lives in saga's
  `ExecutionSpec` and is discarded by `team_emitter.py:107`. So segmentation, agent-id assignment,
  tier-grouping, and segment-dep derivation go saga-side at the `recompile_for_tier`→
  `_emit_team_structure` seam (`:742`); team-execution consumes the emitted rows and implements the
  reuse. No new `worker_derivation.py` in team-execution. *Rejected:* VECU's team-execution-side
  derivation — correct for VECU's primitive saga, wrong here.
- **KTD2 — Segment boundary = plugin directory, computed from a new `Unit.files` field.** `Unit`
  carries no path data today (`execution_spec.py:163-192`), so plugin-dir segmentation is unbuildable
  until `Unit` gains a `files: list[str]` (threaded through `from_dict`/`to_dict`), populated from the
  plan's per-unit file lists. The boundary is the common `plugins/<name>/` prefix; top-level clusters
  (`tests/`, `docs/`, `tools/`) are their own segments. VECU's repo-change proxy never fires in a
  single repo.
- **KTD3 — Emitted row cardinality = one row per resident worker (segment), not per unit.** A segment
  of N units yields ONE worker row whose agent name is the stable resident agent-id, listing the
  covered unit ids, the segment tier, and the segment `Depends-on`. This replaces `team_emitter.py:107`'s
  positional `worker-{i}` (one row per `spec.units`), which would otherwise emit N rows for one resident
  worker.
- **KTD4 — Segment-level dependency derivation.** `Unit.depends_on` (`:182`) and `dependency_layers`
  (`:361`) are unit-level; once units collapse into segments the wave scheduler needs a *segment* graph
  — derived by dropping intra-segment edges and aggregating cross-segment edges. `Unit.depends_on` stays
  unit-ids; the segment graph is derived alongside segmentation.
- **KTD5 — Annotate via copy / side mapping, never mutate the shared spec.** `recompile_for_tier(spec,
  mode)` (`:725`) is called per-tier on one shared `ExecutionSpec`; segmentation must produce a side
  mapping (or operate on a deep copy) so a later emit for a different tier is unaffected.
- **KTD6 — Behavioral residency is markdown protocol; the testable surface is the saga-side plumbing.**
  The `Unit.files` schema, segmentation, segment-dep derivation, and segment-row emit carry real pytest
  (`test_workflow_emitter.py` for the spec round-trip, `test_team_emitter.py` for the emitted rows). The
  reuse/wave/review-loop behaviors live in skills-based-plugin prose validated by `/doc-review` +
  operator runs + headroom telemetry. Consistent with the solo-operator measurement loop.
- **KTD7 — R15a context-GC excluded.** Claude Code exposes no live `tool_result` pruning lever
  (Messages-API-only); structural shed (fresh worker at a boundary) is the only available eviction.

## High-Level Technical Design

```
   saga (derives, sage-side)                    team-execution (resides)
   ─────────────────────────────────           ──────────────────────────────
   ExecutionSpec.units[]                        Step A7 worker table
     unit_id, files(NEW), depends_on, tier        one row PER RESIDENT WORKER:
            │                                      | resident-id | units | tier | seg-deps |
   U1 segment (side map, no mutate):                       │
     group by plugin-dir(files);               U3 spawn ONE named teammate per
     1 resident-id + tier per segment;         resident worker; SendMessage reuse
     derive SEGMENT-level deps                 across its units; summary-handoff at
            │                                  a cross-segment dep; shed at boundary
   U2 team_emitter.emit_team_structure ──────▶ U5 reactive wave: hold a resident
     one row per segment (not per unit)        worker until its segment-deps done

   consensus-protocol.md ── U4 ──▶ named reviewers; re-engage <thr via SendMessage with DELTA context
```

## Implementation Units

### U1. `Unit.files` + saga-side segmentation, dep-derivation, tiering

**What:** In `execution_spec.py`, add a `files: list[str]` field to `Unit` (threaded through
`from_dict`/`to_dict`; empty list default so existing specs round-trip unchanged). Add a segmentation
pass (invoked before the team arm of `recompile_for_tier`, `:742`) that, **on a copy or side mapping —
never mutating the shared spec** (KTD5): groups contiguous units by common `plugins/<name>/` prefix of
their `files` (KTD2) into segments; assigns one stable resident agent-id + a monolithic upgrade-only
tier per segment (R6); and derives the segment-level dependency graph by collapsing `Unit.depends_on`
(drop intra-segment, aggregate cross-segment; KTD4).

**Files:** `plugins/saga/scripts/execution_spec.py`

**Test scenario:** `tests/test_workflow_emitter.py` — a `Unit` with `files` round-trips through
`from_dict`/`to_dict`; segmentation groups consecutive same-plugin-dir units into one segment with one
resident-id; a plugin-boundary opens a new segment; the segment tier is the upgrade-only max (a
`haiku`+`opus` segment → `opus`); cross-segment `depends_on` aggregates to a segment edge while
intra-segment deps drop; the input spec object is unchanged after derivation (no mutation).

**Depends on:** none (foundation).

### U2. Segment-row emit (un-flatten `team_emitter.py`)

**What:** In `team_emitter.py` `emit_team_structure` (`:70-143`), replace the per-unit
`agent = f"worker-{i}"` loop (`:106-110`) with **one row per resident worker (segment)** from U1's side
mapping — columns: resident agent-id, covered unit ids, segment tier, segment `Depends-on` (KTD3). This
is **schema-breaking**: the emitted contract changes from per-unit `worker-{i}` to per-segment
resident-ids with new columns; the existing `worker-{i}` oracle assertions must be updated, not
extended.

**Files:** `plugins/saga/scripts/team_emitter.py`

**Test scenario:** `tests/test_team_emitter.py` — drive segmentation through `recompile_for_tier(spec,
"team-execution")` / `emit_team_structure`: a 3-unit single-plugin spec emits ONE resident-worker row
(not three `worker-N`); a 2-plugin spec emits two rows; rows carry the tier + segment `Depends-on`
columns. **Update** the existing `worker-1/2/3` assertions (`:146-151,:274-275,:306`) to the
resident-id format.

**Depends on:** U1.

### U3. Worker residency runtime protocol (team-execution)

**What:** In `SKILL.md`, update Step A7's worker-table template (`:218-260`) to the new column shape
(resident agent-id, covered units, tier, segment-deps) so the documented template matches U2's emitted
output. Update Step B1 (`:294-297`) to spawn **one named persistent teammate per resident worker**
(`Agent` `name` + `run_in_background`), reuse it across its segment's units via `SendMessage` (no
per-unit re-spawn), perform the **cross-segment summary-handoff** (R4 — a dependent segment's fresh
worker is seeded with the prior segment's `SendMessage` summary, not its full context), and shed at a
segment boundary or when a block exceeds the cache-TTL horizon (R11).

**Files:** `plugins/team-execution/skills/team-execution/SKILL.md`

**Test expectation:** none — markdown protocol in a skills-based plugin (KTD6); validated by
`/doc-review` + operator runs.

**Depends on:** U1, U2.

### U4. Review-loop reviewer residency (team-execution) — independent quick win

**What:** In `consensus-protocol.md`, change B3a (`:26`) to spawn reviewers as named teammates and
record their handles; change B3e (`:51`) to re-engage the same named reviewer via `SendMessage` for the
`<9.0` re-review (no fresh re-spawn); and update the reviewer context template (`~:136-157`) so a
re-engagement carries only the **delta** since that reviewer's last pass (R5), preserving its history
so it reviews what changed rather than re-deriving its whole critique.

**Files:** `plugins/team-execution/skills/team-execution/references/consensus-protocol.md`

**Test expectation:** none — markdown protocol (KTD6); validated by `/doc-review` + operator runs.

**Depends on:** none — independent of worker derivation; can land first / in parallel.

### U5. Reactive-unblock waves on the segment graph (team-execution)

**What:** In `SKILL.md` Step B1, add the rule that a resident worker with unmet **segment-level**
`Depends-on` (from U1/U2) is not spawned (paying creation) until its upstream segments complete; no-dep
segments start together (R8). This within-run frontier is subordinate to saga's coordinator
`ready_frontier` (R10).

**Files:** `plugins/team-execution/skills/team-execution/SKILL.md`

**Test expectation:** none — markdown protocol (KTD6).

**Depends on:** U1, U2, U3.

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

**In scope:** `Unit.files` + saga-side segmentation/dep-derivation/tiering, segment-row emit, worker
residency runtime, review-loop residency, segment-graph reactive waves, release surfaces.

**Deferred to follow-up work:** warm-pool / crew-pairing residency alternatives (revisit only if
named-teammate residency proves insufficient); a formal within-run Kahn-wave *queue* (reactive
unblocking on the derived segment graph first — saga's coordinator frontier does the heavy sequencing).

**Out — forced:** R15a live context-GC (no harness lever; KTD7). **Out — decided:** dynamic RMPA
reviewer/scanner tiering (measured-and-killed in VECU; R6).

## Risk Analysis & Mitigation

- **U2 is schema-breaking, not additive.** It changes the emitted team-structure contract (per-unit
  `worker-{i}` → per-segment resident-ids + new columns) and breaks the `test_team_emitter.py`
  `worker-{i}` oracles. *Mitigation:* U2 updates the SKILL A7 template (U3) and the oracle assertions in
  the same change; the emitter stays a pure function (no I/O); gate via `/doc-review` before merge.
- **Load-bearing seam.** `execution_spec.py` / `team_emitter.py` are on the `/work` execution path; a
  regression breaks all backends. *Mitigation:* segmentation operates on a side mapping (KTD5), so a
  non-team emit is byte-for-byte unchanged; U1/U2 carry real pytest; the `files` field defaults empty so
  existing specs round-trip.
- **Segment-dep derivation correctness.** Collapsing the unit dep graph to segments (KTD4) can mis-order
  if intra/cross edges are mis-classified. *Mitigation:* U1's test asserts intra-segment deps drop and
  cross-segment deps aggregate; the within-run frontier stays subordinate to the coordinator frontier
  (R10).
- **Behavioral parts are prose-validated.** The cache-saving lives in U3/U4/U5 markdown with no pytest.
  *Mitigation:* inherent to skills-based plugins; correctness is `/doc-review` + the operator observing
  headroom cost on the next real run (the accepted measurement loop, not a gap).
- **TTL realism.** A worker kept resident past ~5 min evicts and re-pays creation anyway. *Mitigation:*
  R11 sheds at the TTL horizon; reuse is scoped to tight loops.

## Sources / Research

- Requirements: `docs/brainstorms/2026-06-27-worker-model-cache-scheduling-requirements.md`.
- Ideation: `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` — S-1 (build-first).
- infiquetra seams: `plugins/saga/scripts/team_emitter.py:106-110` (per-unit flatten),
  `plugins/saga/scripts/execution_spec.py:163-192` (`Unit` fields — no path data), `:219-244`
  (round-trip), `:361-368` (`dependency_layers`), `:742` (team seam),
  `plugins/saga/scripts/outcome_spec.py:531-544` (coordinator frontier),
  `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:26,:51,:136-157`
  (review loop + context template),
  `plugins/team-execution/skills/team-execution/SKILL.md:218-260,:294-297` (worker derive/spawn).
- Tests: `tests/test_team_emitter.py:146-151,:306` (worker-`{i}` oracles), `tests/test_workflow_emitter.py`,
  `tests/test_release_triad.py`.
- VECU reference: `../coxauto/vecu-claude-plugins` (`vecu-team-execution` 3.15.0) — `worker_derivation.py`,
  `SKILL.md:598,667,730`, `DECISIONS.md:134,:203`.
- Review: `docs/reviews/2026-06-27-worker-model-cache-scheduling-review.md` (codex + agy + readiness pass).
