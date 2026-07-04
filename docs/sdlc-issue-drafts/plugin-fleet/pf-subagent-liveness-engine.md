---
title: "enhancement: fleet-shared subagent liveness engine — phi-accrual staleness, artifact-pointer progress, acknowledged idle notifications"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: "Govern fleet concurrency and reclaim leaked resources"
---

# enhancement: fleet-shared subagent liveness engine — phi-accrual staleness, artifact-pointer progress, acknowledged idle notifications

### Objective
Govern fleet concurrency and reclaim leaked resources

### Intent
Extract saga's `outcome_liveness` heartbeat/timeout reaper into a fleet-shared liveness module
that any coordinator can poll — not just `/outcome` — and upgrade its detection from a binary
threshold check to three complementary signals: a phi-accrual suspicion score computed from a
worker's heartbeat inter-arrival distribution (replacing the current fixed
`heartbeat_seconds`/`timeout_seconds` cutoff), progress derived from artifact-pointer appearance
rather than agent chattiness (so a talkative-but-artifactless agent is flagged, not trusted), and
an acknowledged-delivery handshake for idle notifications so an unacknowledged re-ping is treated
as undelivered and retried rather than assumed seen.

Today `outcome_liveness.harvest_liveness()` (`plugins/saga/scripts/outcome_liveness.py:112`) is
the only liveness reaper in the fleet, and it is wired to exactly one consumer:
`production_liveness_processor()` in `plugins/saga/scripts/outcome.py:1050-1058`, which lazily
imports `outcome_liveness` and calls `harvest_liveness(spec, store, now=now())`. It works by a
binary threshold: each node's optional `heartbeat_seconds` / `timeout_seconds` budget is compared
against `now - max(dispatched_at, last_heartbeat)`
(`plugins/saga/scripts/outcome_liveness.py` — the pre-dispatch/freshly-launched and
threshold-breach branches around the `_last_heartbeat` / stalled-terminal logic), and a breach
writes a sticky `stalled` terminal (`STALLED_STATE = "stalled"`) that cascades to the dependent
subtree (R22) and pages exactly once (idempotent write, not re-recorded every tick).

`team-execution` — the fleet's other fan-out coordinator (2.9.0, consensus review,
`plugins/team-execution/skills/team-execution/SKILL.md`) — has no equivalent module. A repo-wide
search of `plugins/team-execution/` for `heartbeat`, `idle`, `stalled`, `notification`,
`re-ping`, and `check-in` returns zero matches: team-execution has no liveness reaper, no idle
detection, and no re-ping mechanism at all. This is not a design choice recorded anywhere in the
plugin's references — it is a gap. The grounding brief documents the same failure mode recurring
live: "Subagents idle without delivering; stale idle notifications — coordinator must detect and
re-ping (2 repos; also reproduced live in this very session)"
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3 recurring-pattern 9), rolled into
"Agent-team & gate lifecycle: teardown, pause points, liveness (teardown gap, stale worktrees,
idle-without-delivering)" as dispatch theme 6 (`grounding-brief.md` §8, theme 6). The same brief's
hygiene pass found 15 stale abandoned saga worktrees in `.worktrees/` inflating one repo 10x+ —
direct evidence of the reclaim-on-idle gap this engine closes (`grounding-brief.md` §3).

The existing detector is also purely time-based: `outcome_liveness.py` has no phi-accrual (or any
statistical) staleness scoring — a fixed timeout is either breached or not, with no signal for "this
worker's cadence just changed materially." And progress today is inferred only from ledger
`heartbeat` records (self-reported liveness pings), not from what the worker has actually produced:
`team-execution`'s typed artifact-pointer passing
(`plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py`, `ArtifactPointer`
class at `:112`, `snapshot()` at `:221`) gives every fan-out worker a concrete, verifiable
progress signal — pointer appearance in the CAS store — that the current liveness engine never
consumes. A worker that keeps heartbeating without ever producing an artifact pointer is
indistinguishable, today, from one that is making real progress.

## Definition of Done
- `outcome_liveness` is generalized into a shared module that any coordinator (both `/outcome` and
  team-execution) polls — no second liveness implementation remains.
- Suspicion scoring comes from heartbeat inter-arrival distribution (phi-accrual), progress is
  derived from artifact-pointer appearance rather than heartbeat chattiness, and idle notifications
  require acknowledgment before being trusted as delivered.
- Existing `/outcome` stalled-terminal behavior (idempotent single page, R22 cascade) is unchanged
  for the pure-timeout case.

### Out-of-scope / non-goals
- Epoch fencing on evidence writes, lease quarantine for expired/superseded writers, and the
  cross-bridge orphan reaper for delegated runners (agy delegation, external teammate bridges) —
  that is a separate, already-drafted capability
  (`docs/sdlc-issue-drafts/plugin-fleet/pf-orphan-fencing-liveness.md`, T15-F1-8/F2-7/F4-4). This
  issue is about the *detection and scoring* engine one layer up (is this worker stalled, and
  should this notification be trusted); the orphan-fencing issue is about *write-safety* once a
  runner is confirmed gone. The two land on the same underlying substrate
  (`outcome_liveness.py`) but touch different code paths and should not be merged into one PR.
- Replacing the existing `stalled` terminal semantics, its idempotent single-page behavior, or the
  R22 cascade-to-dependent-subtree behavior in `/outcome` — the phi-accrual score is a new *input*
  to the existing stalled decision, not a rewrite of what happens once a leaf is declared stalled.
- A generic cross-plugin pub/sub notification bus — the acknowledged-delivery handshake covers
  idle/re-ping notifications specifically, not a general notification framework.
- Changing team-execution's validator/consensus dispatch order or its existing proceed-with-best-
  available cap — this issue adds liveness detection alongside those, it does not touch them.
- Backfilling artifact-pointer progress signals onto coordinators or worker shapes that do not
  already emit pointers — the progress signal is opportunistic: workers with no pointer emit fall
  back to heartbeat-only scoring, same as today.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/scripts/outcome_liveness.py` — refactor `harvest_liveness()` and its heartbeat/
  threshold helpers into a shared, coordinator-agnostic module (proposed:
  `plugins/saga/scripts/liveness_engine.py`, imported by both `outcome.py` and team-execution);
  add phi-accrual suspicion scoring over heartbeat inter-arrival intervals.
- `plugins/saga/scripts/outcome.py` — `production_liveness_processor()` (`:1050`) updated to call
  the extracted shared engine instead of the module-local `outcome_liveness` import.
- `plugins/team-execution/skills/team-execution/scripts/` — new consumer wiring so team-execution
  polls the shared liveness engine (proposed: a thin adapter module, or direct import from the
  shared `liveness_engine.py`, keyed on team-execution's existing run/worker identifiers).
- `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py` — expose a
  pointer-appearance query the liveness engine can poll as a progress signal (no change to
  `ArtifactPointer`'s on-disk shape).
- `plugins/saga/skills/*/references/` or `plugins/team-execution/skills/team-execution/references/`
  — document the acknowledged-idle-notification handshake contract (re-ping-on-unacknowledged).
- `tests/test_outcome_liveness.py` (or new `tests/test_liveness_engine.py`) — shared-engine,
  phi-accrual, artifact-pointer-progress, and idle-acknowledgment tests.
- `tests/test_team_execution*.py` — team-execution-side consumption test against the shared engine
  (no second liveness implementation).

### Tests to add or update
- Shared consumption: both `/outcome` (via `outcome.py`) and team-execution poll the same engine
  module — no second liveness implementation exists in team-execution after the change.
- Phi-accrual: a stalled-interval fixture (heartbeats that go silent past the worker's own steady
  cadence) crosses the suspicion threshold and is flagged; a steady-interval fixture does not.
- Artifact-pointer progress: a worker that heartbeats steadily but never emits an artifact pointer
  is flagged as chatty-but-artifactless, distinct from a genuinely stalled (no heartbeat) worker.
- Idle notification acknowledgment: an idle notification with no acknowledgment within its window
  is treated as undelivered and triggers a re-ping; an acknowledged notification does not re-ping.
- Regression: existing `outcome.py` R31 stalled-terminal behavior (idempotent single page, R22
  cascade to dependent subtree) is unchanged for the pure-timeout case.

### Context library links
- source_context: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json (T6-F4-3,
  T6-F5-3, T6-F6-6, H-F1-3)

### Acceptance criteria
- [ ] `team-execution` and `/outcome` both consume the shared liveness engine module — grep proof
  no second copy exists. Check: `grep -rn "def harvest_liveness\|class.*Liveness" plugins/team-execution/ plugins/saga/scripts/` → exactly one production implementation, imported (not duplicated) by both callers.
- [ ] A stalled-interval heartbeat fixture crosses the phi-accrual suspicion threshold and surfaces
  a flag; a steady-interval fixture does not. Check: `uv run pytest tests/test_liveness_engine.py -k phi_accrual` → passes.
- [ ] A chatty-but-artifactless worker (steady heartbeats, no artifact-pointer emission) is flagged
  distinctly from a silent (no-heartbeat) stalled worker. Check: `uv run pytest tests/test_liveness_engine.py -k artifactless` → passes.
- [ ] An idle notification without acknowledgment inside its window is treated as undelivered and
  triggers a re-ping; an acknowledged one does not. Check: `uv run pytest tests/test_liveness_engine.py -k idle_ack` → passes.
- [ ] Existing `/outcome` R31 stalled-terminal tests (idempotent single page, R22 cascade) stay
  green with no behavior change for the pure-timeout case. Check: `uv run pytest tests/test_outcome_liveness.py -k stalled` → passes.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Verification
```bash
# Shared-engine, phi-accrual, artifact-pointer-progress, idle-ack tests
uv run pytest tests/test_liveness_engine.py -v
# Regression: existing R31 stalled-terminal behavior unchanged
uv run pytest tests/test_outcome_liveness.py -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the phi-accrual, artifact-pointer-progress, and idle-acknowledgment fixtures
each demonstrate their named failure mode being caught, and both coordinators are proven to share
one liveness implementation rather than two.

## Grounding References
- **T6-F4-3** (primary) — "Extract `outcome_liveness` into a fleet-shared heartbeat/stalled
  engine." Basis: `outcome_liveness.harvest_liveness()` (`plugins/saga/scripts/outcome_liveness.py:112`)
  is wired to exactly one consumer today (`plugins/saga/scripts/outcome.py:1050-1058`); team-execution
  has zero liveness/idle-detection code (verified: no `heartbeat`/`idle`/`stalled` matches under
  `plugins/team-execution/`).
- **T6-F5-3** (facet) — "Phi-accrual failure detector for subagent liveness." Basis: the current
  detector is a fixed `heartbeat_seconds`/`timeout_seconds` threshold with no statistical staleness
  scoring (`plugins/saga/scripts/outcome_liveness.py`, threshold-breach branch); a phi-accrual score
  over heartbeat inter-arrival intervals is new machinery, not a rewrite of an existing signal.
- **T6-F6-6** (facet) — "Every idle notification is a lie until acknowledged: a delivery-receipt
  handshake." Basis: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3 recurring-pattern 9
  ("subagents idle without delivering; stale idle notifications — coordinator must detect and
  re-ping (2 repos; also reproduced live in this very session)"); no acknowledgment/receipt
  mechanism exists on any idle notification path today.
- **H-F1-3** (facet) — "Liveness derived from artifact-pointer appearance, not agent chattiness."
  Basis: `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py`
  (`ArtifactPointer` class `:112`, `snapshot()` `:221`) gives every fan-out worker a concrete,
  verifiable progress signal that today's heartbeat-only liveness engine never consumes.
- **Theme grounding**: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §8 theme 6
  ("Agent-team & gate lifecycle: teardown, pause points, liveness (teardown gap, stale worktrees,
  idle-without-delivering)"); §3 hygiene find of 15 stale abandoned saga worktrees as direct
  evidence of the reclaim-on-idle gap.
- **Binding decisions this builds on**: `/outcome` campaign decisions (U1-U11, especially
  derived-on-read status and HALT-not-degrade) — the phi-accrual/artifact-pointer/ack signals feed
  the existing derived-on-read `stalled` terminal, they do not introduce a new committed-status
  field. `{#readonly-verifier-fallback-ladder-325}` — any verify-class spawn this issue's testing
  adds must follow the existing readonly-verifier + worktree-isolation pattern, not a new
  unsandboxed spawn site.
- **Related but distinct**: `docs/sdlc-issue-drafts/plugin-fleet/pf-orphan-fencing-liveness.md`
  (T15-F1-8/F2-7/F4-4) — epoch fencing and write-safety for delegated/bridged runners, built on the
  same `outcome_liveness.py` substrate but a separate failure axis (write-safety vs. detection);
  keep as two PRs.

## Recommended Executor Profile
- **Model**: sonnet
- **Effort**: high
- **Backend**: inline
- **External-LLM posture**: none
- **Justification**: mechanical extraction (one existing module into a shared one, wired to a
  second consumer) plus a well-bounded statistical addition (phi-accrual over an existing
  heartbeat ledger) and two already-verified concrete integration points (`outcome.py:1050-1058`,
  `artifact_pointer.py:112/:221`). No architectural ambiguity remains open for `/plan` to resolve
  beyond module boundaries; sonnet at high effort is sufficient, no case for opus-tier judgment or
  an external engine.

### Release-surface checklist
This changes runtime behavior shared by two plugins — update all of the following in the same PR:
- `plugins/saga/.claude-plugin/plugin.json` — version bump for the extracted shared liveness module
  and phi-accrual/artifact-pointer-progress/idle-ack behavior.
- `plugins/team-execution/.claude-plugin/plugin.json` — version bump for team-execution's new
  liveness-engine consumption (previously absent).
- `.claude-plugin/marketplace.json` — version/metadata sync for both `saga` and `team-execution`
  entries.
- `plugins/saga/CHANGELOG.md` — entry for the extracted shared engine, phi-accrual scoring, and
  acknowledged-idle-notification handshake.
- `plugins/team-execution/CHANGELOG.md` — entry for team-execution gaining liveness/idle detection
  for the first time.
- Any version/metadata drift-guard tests in `tests/` that assert plugin.json/marketplace.json/
  CHANGELOG parity — run and confirm they still pass after both bumps.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json (T6-F4-3, T6-F5-3,
  T6-F6-6, H-F1-3)
- Source type: ideation-map
- Source title: Fleet-shared liveness engine: extract outcome_liveness, phi-accrual staleness
  scoring, artifact-pointer-derived progress, and acknowledged idle notifications

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/357
- Number: 357
- Created at: 2026-07-04T07:48:34.386367+00:00

