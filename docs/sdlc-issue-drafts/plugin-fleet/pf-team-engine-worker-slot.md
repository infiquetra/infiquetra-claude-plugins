---
title: "capability: team-execution external-engine worker — fail-loud invocation-proof discriminator"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
objective: "Stand up the external-engine offload lane"
tier: structural
wave: wave-1
---

# capability: team-execution external-engine worker — fail-loud invocation-proof discriminator

### Objective
Stand up the external-engine offload lane

---
date: 2026-07-03
topic: pf-team-engine-worker-slot
maturity: requirements-ready
source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/ — T1-F2-5 (primary), S-2, S-18 (dedup-merged), T15-F3-4 (facet)
tier: structural
wave: wave-1
---

# Activate the team-execution external-engine worker slot's missing invocation-proof discriminator

## Summary

The team-execution external-engine (chaperone-dispatch) worker slot that this issue's ideation
set out to "activate" was **already shipped** by `880b94c` — "team-execution external-engine
workers — chaperone dispatch (#318) (#319)", merged 2026-07-02, one day before this ideation
ran. `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`
(176 lines) fully specs the resolve → dispatch → verify → apply → test → manifest protocol;
`SKILL.md` Step B1 (`plugins/team-execution/skills/team-execution/SKILL.md:303-324`) wires it;
`worker-manifest.md` already carries the `kind="external-engine"` attribution and the
`fell-back-to-claude` / `substituted-engine` dispositions. So three of the four absorbed ideas
(T1-F2-5 "activate the deferred slot", S-2 "delegate-agents plugin", S-18 "use codex/agy in
teams dynamic workflows") describe work that is functionally done and should **not** be
re-executed.

What remains open, and is this issue's actual deliverable, is the fourth absorbed facet,
**T15-F3-4**: give the external-engine worker the same fail-loud invocation-proof discriminator
that `agy` already has (`plugins/agy/scripts/agy_delegate.py` writes a `git-proof.json` bundle
per run — see `_write_git_proof` at `plugins/agy/scripts/agy_delegate.py:1422` and
`agy.git-proof.v1` schema at `:1437` — and `agy_delegate.py`'s run-lease path, `_run_lease_payload`
at `:1559`, refuses to credit a run that never produced proof of invocation). team-execution's
chaperone worker has no equivalent: nothing in `worker-manifest.md`, `validator-registry.md`, or
`consensus-protocol.md` requires an invocation-proof field on the chaperone's exit manifest, and
nothing downgrades an external-engine worker's evidence to not-counted in consensus when that
proof is missing. `validator-registry.md:89`'s `external-second-opinion` validator entry treats
a chaperone-dispatched verdict as usable evidence unconditionally — there is no discriminator
for "the engine call itself may never have actually run."

## Problem Frame

- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md` (the
  "Never gatekeeper" section) already hard-requires `evidence.verified_by_claude == True`
  (`plugins/saga/scripts/engine_dispatch.py:238-258`) before any chaperone-sourced advisory
  evidence counts toward a verdict — but that check verifies Claude adjudicated the *content*,
  not that the underlying engine invocation actually happened and produced the diff/output it
  claims to.
- `agy` solved the adjacent problem for its own delegation surface: `agy_delegate.py` writes a
  `git-proof.json` bundle (schema `agy.git-proof.v1`, `_write_git_proof` at
  `plugins/agy/scripts/agy_delegate.py:1422`) and a run-lease payload
  (`_run_lease_payload`, `plugins/agy/scripts/agy_delegate.py:1559`) so a caller can tell a real
  invocation from a silent no-op. team-execution's chaperone worker (`worker-manifest.md`) has
  no analogous field — `worker-manifest.md`'s Disposition section (R18) only distinguishes
  `ran-as-requested`, `fell-back-to-claude`, and `substituted-engine`; none of those states
  encode "the chaperone reported a disposition but never actually produced invocation evidence
  for it."
- `validator-registry.md:89` (`external-second-opinion` row) and `consensus-protocol.md`
  (reviewer-consensus tally logic) both consume chaperone-dispatched verdicts as ordinary
  evidence with no invocation-proof gate — a worker that fabricates or omits proof of having
  run currently weighs the same as one that produced it, in direct tension with the
  `{#external-engines-never-gatekeepers}` decision's spirit (Claude must remain
  verifier-of-record, and unverifiable "evidence" should not silently pass as evidence).
- Binding decisions this must respect without re-architecting: `{#external-engines-never-gatekeepers}`
  (docs/plans/2026-07-03-plugin-fleet-grounding-brief.md §2, anchor #283) — codex/agy remain
  generator/advisory-reviewer/non-gated worker only, Claude stays verifier-of-record; and
  `{#external-engine-chaperone-dispatch}` (grounding brief §2, anchor #318) — external engines in
  teams are chaperone-dispatched only, never a second executor kind, never git-participant.
  This issue's revisit-when trigger under `{#external-engines-never-gatekeepers}` is explicitly
  engaged: "team-execution gains external-engine worker slot" has now happened (#319), so the
  decision must be re-engaged rather than silently assumed still-satisfied.

## Key Decisions

- **Do not re-build the already-shipped chaperone-dispatch slot.** T1-F2-5, S-2, and S-18 are
  absorbed as provenance/history, not as remaining scope — `external-engine-workers.md`,
  `SKILL.md` Step B1, and `worker-manifest.md`'s attribution/disposition fields already satisfy
  their intent. Re-implementing them would be wasted, overlapping work.
- **Invocation-proof is a required field, not opportunistic.** Every chaperone-worker exit
  manifest must carry an invocation-proof field (or reference to one, e.g. an `agy`-style
  `git-proof.json`-shaped record, or team-execution's own equivalent artifact-pointer) so a
  missing/unproven chaperone run is structurally distinguishable from a proven one.
- **Unproven → not-counted, not merely flagged.** When invocation proof is absent for a
  chaperone-dispatched worker, `consensus-protocol.md`'s tally and `validator-registry.md`'s
  `external-second-opinion` row must treat that worker's evidence as **not counted** toward
  consensus — not downweighted, not warned-and-passed. This is the fail-loud discriminator
  T15-F3-4 asks for, mirrored from agy's git-proof/run-lease pattern.
- **Flags only, no re-architecture.** This ships as a manifest-field addition plus a
  consensus/registry check, honoring `{#external-engine-chaperone-dispatch}`'s "flags, no
  re-architecture" constraint (per T15-F3-4's dod_sketch) — it does not change chaperone
  dispatch shape, add a second executor kind, or touch `external-engine-workers.md`'s resolve →
  dispatch → verify → apply → test → manifest protocol beyond the manifest's exit contract.

## Requirements

R1. The chaperone-worker exit manifest (`worker-manifest.md`'s manifest shape) gains a required
`invocation_proof` field for `kind="external-engine"` workers, populated from the engine
dispatch's own evidence (analogous to `agy`'s `git-proof.json` / run-lease payload) — absent for
Claude-agent workers (`protocol=""`), required whenever `kind="external-engine"`.

R2. When a chaperone worker's manifest is missing `invocation_proof` (or it fails a minimal
shape check — non-empty, references a real dispatch), that worker's evidence is excluded from
`consensus-protocol.md`'s consensus tally: it does not count toward "reviewers agree" or
"reviewers disagree," and does not satisfy the `external-second-opinion` validator's pass
criterion in `validator-registry.md:89`.

R3. The exclusion is fail-loud: a run with a missing-proof chaperone worker must surface a
named, typed condition (e.g. `unproven-invocation`) in team-execution's output — not a silent
drop from the tally.

R4. `{#external-engines-never-gatekeepers}` and `{#external-engine-chaperone-dispatch}` are
explicitly re-engaged (cited by anchor) in this PR's description/DECISIONS entry, since the
prerequisite condition in each decision's revisit-when clause has now occurred.

R5. No change to chaperone dispatch resolve → dispatch → verify → apply → test → manifest
protocol shape, wave scheduling, or residency — this is additive to the manifest/consensus
layer only.

### Out-of-scope / non-goals
- Does not re-implement or modify the chaperone-dispatch protocol shipped in #319
  (`external-engine-workers.md`, `SKILL.md` Step B1, existing `worker-manifest.md` attribution
  fields) beyond adding the `invocation_proof` field to the manifest schema.
- Does not add a second executor kind, change residency/wave scheduling, or let an external
  engine become a git participant — `{#external-engine-chaperone-dispatch}` stays intact.
- Does not change what counts as Claude-adjudicated evidence under
  `evidence.verified_by_claude` (`plugins/saga/scripts/engine_dispatch.py:238-258`) — that gate
  is orthogonal and untouched; this issue adds a second, independent discriminator
  (invocation happened at all) on top of it.
- Does not build a new delegate-agents plugin (S-2's original ask) — that surface already
  exists via `agy` and via team-execution's chaperone protocol; this issue only closes the
  fail-loud gap between them.
- Does not touch `plugins/agy`'s own git-proof/run-lease implementation — it is read as
  reference precedent only, not modified.

## Grounding References

- **T1-F2-5** (primary, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json`) —
  "Activate deferred team-execution engine-worker slot — remove 'dispatch deferred' gap." Basis:
  direct read of the then-current team-execution reference set. Status: superseded by shipped
  work (`880b94c`, PR #318/#319, merged 2026-07-02) — absorbed for history, not re-executed.
- **S-2** (facet, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`) —
  "Delegate-agents plugin (codex/agy as first-class delegation surface)." Basis: direct, QUEUED
  anchor `{#delegate-agents-plugin}` (`docs/engineering-journal/QUEUED.md:230`, brief §5). Status:
  intent satisfied by the shipped chaperone protocol + existing `agy` plugin; no new plugin
  needed.
- **S-18** (dedup-merged into S-2, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`) —
  "Use codex/agy in teams dynamic workflows." Basis: direct, operator statement. Status: same as
  S-2 — satisfied by shipped chaperone dispatch (offload→sonnet/medium, second-opinion→opus/high
  per `{#external-engine-chaperone-dispatch}`).
- **T15-F3-4** (facet, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json`) — "Give
  team-execution's external-engine workers the same fail-loud discriminator agy has." Basis:
  silent-fallback-elimination theme scan. This is the facet that remains open and is this
  issue's actual deliverable: an invocation-proof field on the chaperone worker contract, with an
  unproven→not-counted rule wired into `consensus-protocol.md` and `validator-registry.md`.
- **Binding decisions engaged**: `{#external-engines-never-gatekeepers}` (#283,
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2) — revisit-when clause ("team-execution
  gains external-engine worker slot") is now triggered by #319's merge; `{#external-engine-chaperone-dispatch}`
  (#318, same brief §2) — this issue must stay within "flags, no re-architecture."
- **Shipped precedent read as reference**: `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`,
  `plugins/team-execution/skills/team-execution/references/worker-manifest.md`,
  `plugins/team-execution/skills/team-execution/SKILL.md:303-324` (Step B1),
  `plugins/team-execution/skills/team-execution/references/validator-registry.md:89`,
  `plugins/team-execution/skills/team-execution/references/consensus-protocol.md`,
  `plugins/agy/scripts/agy_delegate.py:1422` (`_write_git_proof`), `:1437` (`agy.git-proof.v1`
  schema), `:1559` (`_run_lease_payload`).

## Recommended Executor Profile

- **Model**: sonnet. **Effort**: high *(target posture — inert until `pf-effort-first-class` lands; teammates inherit session tier)*. **Backend**: team-execution. **External-LLM posture**:
  offload (advisory only; never gatekeeping — consistent with what this issue itself enforces).
- **Justification**: this is a scoped, mechanical schema-plus-gating-check addition on top of an
  already-shipped protocol (no new architecture, no cross-cutting design decision) — sonnet/high
  matches the "mechanical or deterministic work" tier per this repo's model-tiering guidance. It
  does not require opus-level judgment because the shape (manifest field + consensus exclusion
  rule) is fully specified by T15-F3-4's dod_sketch and the agy precedent; it is not being
  escalated above sonnet.

## Definition of Done

Merged PR that:
1. Adds a required `invocation_proof` field to the chaperone-worker exit manifest schema
   (`plugins/saga/scripts/provenance_manifest.py` / `worker-manifest.md`'s documented shape),
   populated from the engine dispatch's own evidence for every `kind="external-engine"` worker.
2. Wires an unproven→not-counted rule into `consensus-protocol.md`'s tally logic and
   `validator-registry.md`'s `external-second-opinion` row, so a chaperone worker with missing
   or invalid `invocation_proof` is excluded from consensus rather than silently counted.
3. Surfaces a typed `unproven-invocation` condition when this exclusion fires (fail-loud, not a
   silent drop).
4. Explicitly re-engages `{#external-engines-never-gatekeepers}` and
   `{#external-engine-chaperone-dispatch}` by anchor in the PR description and/or a
   `DECISIONS.md` entry, since the former's revisit-when condition has now fired.
5. Ships with a scripted end-to-end test: a chaperone worker run whose manifest lacks
   `invocation_proof` has its evidence downgraded to not-counted in the consensus tally, and the
   run reports `unproven-invocation`; a chaperone worker run with valid `invocation_proof`
   participates in consensus normally.
6. Updates release surfaces for `team-execution` (see checklist below) since this changes
   worker-contract behavior.

### Acceptance criteria
- [ ] A chaperone-dispatched external-engine worker whose exit manifest carries a valid
  `invocation_proof` has its evidence counted normally in `consensus-protocol.md`'s tally and in
  the `external-second-opinion` validator's pass criterion (T1-F2-5, S-2/S-18 — confirms the
  already-shipped chaperone-dispatch lane still functions as advisory/non-gated evidence).
  Check: `uv run pytest tests/test_team_execution_consensus.py -k chaperone_proven_counts` →
  passes.
- [ ] A chaperone-dispatched worker whose exit manifest is missing `invocation_proof` (or has an
  unresolvable/empty one) is excluded from the consensus tally — `not-counted`, not merely
  flagged (T15-F3-4). Check:
  `uv run pytest tests/test_team_execution_consensus.py -k chaperone_unproven_not_counted` →
  passes.
- [ ] The unproven-invocation condition is surfaced as a named, typed result (`unproven-invocation`)
  in team-execution's run output — never a silent drop. Check:
  `uv run pytest tests/test_team_execution_consensus.py -k unproven_invocation_typed` → passes.
- [ ] Claude remains verifier-of-record: no code path lets a chaperone-dispatched (proven or
  unproven) worker satisfy a gate on its own — `engine_dispatch.satisfy_gate()`'s existing
  `evidence.verified_by_claude` requirement (`plugins/saga/scripts/engine_dispatch.py:238-258`)
  is untouched and still enforced. Check:
  `uv run pytest tests/test_team_execution_consensus.py -k external_engine_never_gates` →
  passes.
- [ ] `{#external-engines-never-gatekeepers}` and `{#external-engine-chaperone-dispatch}` are
  cited by anchor in the PR body and/or a new `DECISIONS.md` entry, noting the revisit-when
  trigger fired. Check: `grep -n "external-engines-never-gatekeepers\|external-engine-chaperone-dispatch" docs/engineering-journal/DECISIONS.md`
  finds a dated entry referencing this PR.
- [ ] Full suite, format, lint, types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

## Release-Surface Checklist

Because this changes chaperone-worker contract/schema behavior in `team-execution`, update in
the same PR:
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump (current: `2.9.0`).
- [ ] `.claude-plugin/marketplace.json` — matching `team-execution` entry version bump
  (currently `2.9.0` at line 111).
- [ ] `plugins/team-execution/CHANGELOG.md` — new dated entry describing the invocation-proof
  field and the not-counted consensus rule.
- [ ] Any version/metadata drift-guard tests (e.g. `tests/test_team_execution_plugin.py`) —
  confirm they assert the bumped version and pass.

## Files Expected to Change

- `plugins/saga/scripts/provenance_manifest.py` — add `invocation_proof` field to manifest
  schema for `kind="external-engine"` workers.
- `plugins/team-execution/skills/team-execution/references/worker-manifest.md` — document the
  new required field and its shape.
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md` — wire the
  unproven→not-counted exclusion into the tally logic.
- `plugins/team-execution/skills/team-execution/references/validator-registry.md` — update the
  `external-second-opinion` row (line 89) to require valid `invocation_proof` before counting.
- `tests/test_team_execution_consensus.py` — new tests for proven/unproven chaperone-evidence
  counting and the typed `unproven-invocation` condition.
- `plugins/team-execution/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/team-execution/CHANGELOG.md` — release-surface updates (see checklist above).

## Tests to Add or Update

- `tests/test_team_execution_consensus.py -k chaperone_proven_counts` — valid
  `invocation_proof` → evidence counted normally.
- `tests/test_team_execution_consensus.py -k chaperone_unproven_not_counted` — missing/invalid
  `invocation_proof` → evidence excluded from tally.
- `tests/test_team_execution_consensus.py -k unproven_invocation_typed` — exclusion surfaces the
  named `unproven-invocation` condition, never a silent drop.
- `tests/test_team_execution_consensus.py -k external_engine_never_gates` — regression: no
  chaperone worker (proven or unproven) can satisfy a gate on its own.

### Verification
```bash
# New consensus/manifest tests
uv run pytest tests/test_team_execution_consensus.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the new tests demonstrate proven chaperone evidence counts, unproven
evidence does not, and the exclusion is always surfaced as a typed `unproven-invocation`
condition rather than a silent drop.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json,
  docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json,
  docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json
- Source type: ideation (issue-map)
- Source title: Activate the team-execution external-engine worker slot as the fleet's
  delegation surface for codex/agy

### Intent

The team-execution external-engine (chaperone-dispatch) worker slot that this issue's ideation set out to "activate" was **already shipped** by `880b94c` — "team-execution external-engine workers — chaperone dispatch (#318) (#319)", merged 2026-07-02, one day before this ideation ran. `plugins/team-execution/skills/team-execution/references/external-engine-workers.md` (176 lines) fully specs the resolve → dispatch → verify → apply → test → manifest protocol; `SKILL.md` Step B1 (`plugins/team-execution/skills/team-execution/SKILL.md:303-324`) wires it; `worker-manifest.md` already carries the `kind="external-engine"` attribution and the `fell-back-to-claude` / `substituted-engine` dispositions. So three of the four absorbed ideas (T1-F2-5 "activate the deferred slot", S-2 "delegate-agents plugin", S-18 "use codex/agy in teams dynamic workflows") describe work that is functionally done and should **not** be re-executed.

### Context library links

_none_

### Files expected to change

- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`
- `plugins/agy/scripts/agy_delegate.py`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/team-execution/skills/team-execution/references/worker-manifest.md`
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md`

### Tests to add or update

- `tests/test_team_execution_consensus.py`
- `tests/test_team_execution_plugin.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/392
- Number: 392
- Created at: 2026-07-04T07:59:02.036829+00:00

