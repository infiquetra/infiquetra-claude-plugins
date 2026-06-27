---
title: "capability: worker×model cache scheduling — cost-first worker residency"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: plan-ready
objective: tooling_enhancements
---

# capability: worker×model cache scheduling — cost-first worker residency

### Objective

Under the **tooling_enhancements** objective. Port VECU's cost-first worker derivation + named-teammate
residency into the infiquetra execution engine so it pays context-creation cost **once per reuse
boundary** instead of re-spawning fresh per phase and per review round. The scheduling unit is the
(worker×model) context cache, not the task.

### Intent

infiquetra re-pays context creation on two hot paths VECU has already closed: `team_emitter.py:107`
flattens every unit to a positional `worker-{i}`, discarding the `depends_on` + `{model,effort}` tier
already on `Unit`; and `consensus-protocol.md:51` re-spawns *fresh* reviewers every consensus round.

The fix is split along the seam infiquetra already has: **saga derives** (segment units by plugin
directory, assign one resident agent-id + tier per segment, derive segment-level deps) and
**team-execution resides** (spawn one named teammate per segment, reuse it via `SendMessage`, shed at
the boundary). The payoff shows up as reduced cache-creation cost on heavy real-codebase runs; it is
validated by operator runs + `/retro`, not a measurement gate (the operator is the measurement loop).

**The authoritative implementation spec is the linked plan**
(`docs/plans/2026-06-27-worker-model-cache-scheduling-plan.md`). Implement per its Implementation Units
(U1–U6), Key Technical Decisions, and per-unit test scenarios — this issue is the tracked pointer and
acceptance summary, not a re-specification. If the issue and the plan ever disagree, the plan wins.

### Out-of-scope / non-goals

- Warm-pool / crew-pairing residency alternatives — named-teammate residency first; revisit only if it
  proves insufficient.
- A formal within-run Kahn-wave *queue* — reactive unblocking on the derived segment graph first.
- R15a live context-GC — **excluded**, no harness lever (Claude Code exposes no live `tool_result`
  pruning; Messages-API-only).
- Dynamic RMPA reviewer/scanner tiering — measured-and-killed in VECU; only worker-lane tiering is in
  scope.

### Files expected to change

- `plugins/saga/scripts/execution_spec.py` — `Unit.files` field + saga-side segmentation / dep-derivation
  / tiering on a side mapping (U1).
- `plugins/saga/scripts/team_emitter.py` — segment-row emit (one row per resident worker); schema-breaking
  (U2).
- `plugins/team-execution/skills/team-execution/SKILL.md` — worker residency runtime + reactive
  segment-graph waves (U3, U5).
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md` — review-loop residency
  + delta re-engagement context (U4).
- `plugins/saga/.claude-plugin/plugin.json` + CHANGELOG, `plugins/team-execution/.claude-plugin/plugin.json`
  (2.2.0 → 2.3.0) + CHANGELOG, `.claude-plugin/marketplace.json` — release surfaces (U6).

### Tests to add or update

- `tests/test_workflow_emitter.py` — `Unit.files` round-trip; same-plugin-dir units group to one segment;
  plugin boundary opens a new segment; upgrade-only segment tier; segment-dep collapse (intra drop / cross
  aggregate); input spec unchanged after derivation (U1).
- `tests/test_team_emitter.py` — one resident-worker row per segment (not `worker-N`); tier + segment-deps
  columns; **update** the existing `worker-1/2/3` assertions (`:146-151,:274-275,:306`) (U2).
- `tests/test_release_triad.py` — version + marketplace drift green (U6).
- U3/U4/U5 are skills-prose (no pytest by design; validated by `/doc-review` + operator runs).

### Context library links

- Plan: `docs/plans/2026-06-27-worker-model-cache-scheduling-plan.md`
- Requirements: `docs/brainstorms/2026-06-27-worker-model-cache-scheduling-requirements.md`
- Ideation (S-1 build-first): `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md`
- Doc-review: `docs/reviews/2026-06-27-worker-model-cache-scheduling-review.md`
- Decisions: `docs/engineering-journal/DECISIONS.md#worker-cache-scheduling`
- Reference impl: `../coxauto/vecu-claude-plugins` (`vecu-team-execution` 3.15.0)

### Acceptance criteria

- [ ] `Unit` carries a `files` field (round-tripped); segments derived by plugin-dir; one resident-id +
  upgrade-only tier per segment (R1, R2, R6).
- [ ] `team_emitter` emits **one row per segment** (resident-id, covered units, tier, segment-deps), not
  per unit; `worker-{i}` oracles updated (R7).
- [ ] Segment-level deps derived (intra-segment dropped, cross-segment aggregated); reactive unblock on
  the segment graph, subordinate to the coordinator `ready_frontier` (R8, R10).
- [ ] team-execution spawns one named teammate per segment, reuses via `SendMessage`, summary-handoff at
  a cross-segment dependency, sheds at boundary / TTL horizon (R3, R4, R11).
- [ ] Review loop re-engages sub-threshold reviewers via `SendMessage` with **delta** context (R5).
- [ ] Segmentation never mutates the shared `ExecutionSpec` (R9).
- [ ] Release surfaces bumped; drift guards green.

### Verification

```bash
uv run pytest tests/test_workflow_emitter.py tests/test_team_emitter.py tests/test_release_triad.py
uv run ruff check . && uv run ruff format --check .
```

- `pytest` green: `tests/test_workflow_emitter.py`, `tests/test_team_emitter.py`,
  `tests/test_release_triad.py` + the two plugin validators.
- Plan was doc-reviewed (codex `gpt-5.5` xhigh + agy Gemini 3.1 Pro High + readiness pass): 1 P0 + 4 P1
  found and all fixed — see the review artifact.
- Behavioral units (U3/U4/U5) validated by `/doc-review` + the first real `/work` run observing reduced
  cache-creation cost in headroom telemetry.
- Execute via `/work` (inline → PR).

### Handoff maturity

plan-ready

### Suggested next action

Use `/work <issue>` to execute from the plan-grade context.

### Source context

- Source: `docs/plans/2026-06-27-worker-model-cache-scheduling-plan.md`
- Source type: plan
- Source title: Worker×Model Cache Scheduling — Implementation Plan
