---
title: "capability: runtime ladder climbing — gated one-rung escalation on failure signals"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: "Make tier+effort a first-class priced resolvable lever"
---

# capability: runtime ladder climbing — gated one-rung escalation on failure signals

## Objective
Make tier+effort a first-class priced resolvable lever: when a unit fails or a worker
self-reports over its depth, the engine (or the worker itself) can climb exactly one rung
of the existing tier ladder — never guess the whole ladder up front, and never loop or
silently overspend.

## Tier / Type / Wave
- Tier: structural
- Type: capability
- Wave: wave-1

## Problem / Motivation

The tier vocabulary is already an explicit, ordered ladder, not a closed set:
`MODELS = ("fable", "opus", "sonnet", "haiku")` and `EFFORTS = ("low", "medium", "high",
"xhigh")` in `plugins/saga/scripts/execution_spec.py:52-53`, with the ordering called out as
load-bearing in the comment at `plugins/saga/scripts/execution_spec.py:47-51` ("ORDERING IS
LOAD-BEARING: `segment_units()` merges tiers upgrade-only via `min(MODELS.index)` /
`max(EFFORTS.index)`"). `segment_units()` already performs that upgrade-only merge at
`plugins/saga/scripts/execution_spec.py:1474-1476`.

What is missing is a *runtime* climb primitive that reuses this ladder after a unit has
already failed or a cheap worker has already flagged itself as out of depth, instead of only
merging tiers at segment-planning time:

- There is no `escalate_tier()` / `bump_tier()` helper anywhere in the codebase (confirmed:
  `grep -n "def escalate\|def bump_tier" plugins/saga/scripts/execution_spec.py` returns
  nothing) — only a read-only override-rate *reporting* concept
  (`plugins/saga/scripts/override_rate_reader.py:88-108`) that counts past over-tier /
  under-tier decisions after the fact; it does not compute or apply a next rung.
- `/work`'s existing tier lever is plan-time and operator-facing only: it recommends a
  backend once via `recommend_execution_backend()` and surfaces alternatives so "escalation
  is one keystroke" (`plugins/saga/skills/work/SKILL.md:51`), but there is no
  round-N-to-round-N+1 recovery step that proposes climbing one rung *because a prior round
  failed*, with a cost delta attached.
- Nothing on the `execution_spec.py` segment/verify path watches a difficulty signal (a
  verifier refute, a failed risk-gated test, a unit's own low-confidence return) and
  re-emits the unit one rung up; today a refuted unit is simply re-run at the same tier or
  escalation is guessed by a human re-reading the transcript.
- There is no worker-initiated "I am out of my depth" return disposition distinct from
  success or crash — a cheap-tier unit that is substantively wrong but shape-valid passes
  through silently. This is the same failure class as `{#silent-omission-completeness-gate}`
  (`docs/sdlc-issue-drafts/2026-06-27-capability-infiquetra-claude-plugins-campps-work-2.md`)
  but for *quality-out-of-depth*, not *absent output*: the unit did emit, but at a tier that
  cannot do the work.

This capability is spend-increasing (it causes more expensive re-runs), so it engages the
existing intake asymmetric-approval rule already binding on this ideation cycle: **silent
climb is permitted only in unattended/cache-tight runs; attended runs must surface the
escalation as an explicit ask before the re-run** (grounding brief §2,
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`, binding decision
`{#tier-vocab-ordering}`, and the operator-choice framework
`{#operator-choice-framework}` — "operator-choice = doc-only, CLI-driven `/work`").

## Definition of Done

A single merged mechanism, reusing the existing ordered `MODELS`/`EFFORTS` ladder, that lets
a failed or self-reporting unit climb exactly one rung, gated by attendance mode:

1. `escalate_tier()` (and its inverse `de_escalate_tier` semantics where applicable) added to
   `plugins/saga/scripts/execution_spec.py`, computing the next rung strictly via
   `MODELS.index` / `EFFORTS.index` arithmetic on the existing ordered tuples (no new
   vocabulary, no skipping a rung).
2. A gated `/work` between-rounds recovery step (in `plugins/saga/skills/work/`) that, on a
   round's failure, proposes the next rung up with an explicit cost delta, and end-clamps
   (never proposes past the top or bottom of the ladder).
3. An `escalate_on_signal` rung wired into the `execution_spec.py` segment/verify path so a
   refuted unit or a failed risk-gated test re-emits at exactly one index higher on `MODELS`
   or `EFFORTS` — and halts (rather than looping) if it is already at the top rung.
4. A `pull_cord` return disposition on the cheap-tier unit return contract (alongside
   `BUDGET_RIDER`, `plugins/saga/scripts/execution_spec.py:122`), distinct from success/crash,
   that a worker can emit when it judges itself out of depth; the coordinator batches any
   pulled cords into a single operator escalation ask rather than acting on each individually.
5. Attended-mode escalation (any of the above three paths) always emits an explicit ask gate
   before re-running at the higher tier; unattended/cache-tight mode may climb silently.
   `pull_cord` units are never marked complete.
6. Tests proving: one-rung-only climbing, end-clamping at the top rung (halt, not loop), the
   attended-mode ask gate, and that a `pull_cord` unit is excluded from completion.

### Acceptance criteria
One or more per absorbed facet (T3-F6-4, T3-F1-5, T12-F5-1, T12-F5-6):

- [ ] `escalate_tier()`/`bump_tier()` exists in `execution_spec.py` and computes the next
      rung by index arithmetic on `MODELS`/`EFFORTS`, never inventing a tier outside the
      closed ordered sets. Check: `uv run pytest tests/test_execution_spec.py -k escalate_tier`
      → passes.
- [ ] A refuted unit is re-emitted at exactly one index up the ladder (`MODELS` or
      `EFFORTS`), never more than one rung. Check:
      `uv run pytest tests/test_execution_spec.py -k escalate_on_signal_one_rung` → passes.
- [ ] A unit already at the top of the ladder that fails again surfaces `HALT` rather than
      re-emitting or looping. Check:
      `uv run pytest tests/test_execution_spec.py -k escalate_on_signal_top_of_ladder_halts`
      → passes.
- [ ] `/work`'s between-rounds recovery step proposes the next-rung escalation with a cost
      delta after a round fails, and end-clamps at the ladder boundary (documented affordance,
      not silently applied). Check: `plugins/saga/skills/work/references/*.md` names the
      round-N escalation/de-escalation step and its end-clamping behavior; reviewed in
      `/doc-review`.
- [ ] Attended-mode escalation (any of the three escalation paths) always emits an explicit
      ask gate before the higher-tier re-run; it is never applied silently in attended mode.
      Check: `uv run pytest tests/test_execution_spec.py -k escalate_attended_asks` → passes.
- [ ] Unattended/cache-tight mode is permitted to climb silently (asymmetric-approval rule
      applied correctly in both directions, not just the attended side). Check:
      `uv run pytest tests/test_execution_spec.py -k escalate_unattended_silent` → passes.
- [ ] A `pull_cord` return disposition is added to the cheap-tier unit return contract,
      distinct from success and crash. Check:
      `uv run pytest tests/test_execution_spec.py -k pull_cord_disposition` → passes.
- [ ] A unit returning `pull_cord` is never marked complete, and produces exactly one batched
      escalation entry for the coordinator (not one ask per cord). Check:
      `uv run pytest tests/test_execution_spec.py -k pull_cord_not_complete_batched` → passes.
- [ ] Full suite, format, lint, and types stay green. Check:
      `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
- One rung per escalation event — no multi-rung jumps, no "escalate straight to opus/xhigh."
- No change to the *plan-time* tier-merge logic in `segment_units()`
  (`execution_spec.py:1474-1476`); this issue only adds *runtime* escalation after
  plan-time tiers are already assigned.
- No change to `team-execution`'s existing proceed-best-available cap or consensus-protocol
  iteration semantics — those are separately owned (`plugins/team-execution/skills/
  team-execution/references/consensus-protocol.md`, `validator-execution-order.md`) and out
  of scope here.
- Does not touch the silent-omission completeness gate (missing/malformed output detection)
  — that is a distinct, separately tracked capability
  (`docs/sdlc-issue-drafts/2026-06-27-capability-infiquetra-claude-plugins-campps-work-2.md`);
  `pull_cord` is a *worker-initiated depth* signal, not an absence detector, and the two must
  not be merged into one mechanism.
- No new plugin — this extends `plugins/saga/scripts/execution_spec.py` and
  `plugins/saga/skills/work/`, consistent with the active plugin-sprawl concern
  (`{#plugin-portfolio-groom-17-to-7}`, grounding brief §2).
- No new external-engine executor kind or residency change — escalation stays within the
  existing tier vocabulary and existing chaperone-dispatch model
  (`{#external-engine-chaperone-dispatch}`, #318).

## Grounding References

- **T3-F6-4** (primary) — "Gated auto-escalation one rung up the tier ladder on unit
  failure." Basis: `execution_spec.py`'s ordered `MODELS`/`EFFORTS` tuples and the
  upgrade-only merge in `segment_units()` (`execution_spec.py:1474-1476`); no existing
  runtime escalate primitive. `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T3.json`.
- **T3-F1-5** (facet) — "An escalate-one-rung primitive for the operator's mid-run 'bump the
  model' ask." Basis: same file, direct extension of tier-vocab ordering into a `/work`
  between-rounds affordance. `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T3.json`.
- **T12-F5-1** (facet) — "Titrate-to-effect tier escalation: start cheap, climb only on a
  difficulty signal." Basis (external): anesthesiology titration-to-effect (dose to minimum
  effective level, escalate only on a monitored signal — Bispectral Index / depth-of-anesthesia
  monitors per Miller's Anesthesia), mapped onto `{#tier-vocab-ordering}`
  (`execution_spec.py:49-53`) and the intake asymmetric-approval rule (silent only when
  unattended). `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T12.json`.
- **T12-F5-6** (facet) — "Andon cord: a running cheap worker can stop and request escalation
  instead of failing silently." Basis (external): Toyota Production System andon cord + jidoka
  (Ohno, *Toyota Production System*, 1988) — a worker stops the line on an abnormality and
  surfaces it to a human. Maps onto a `pull_cord` return disposition on the cheap-tier return
  contract next to `BUDGET_RIDER` (`execution_spec.py:122`); honors the same
  asymmetric-approval rule; stays advisory-only.
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T12.json`.
- **Binding decisions engaged**: `{#tier-vocab-ordering}` (tier tuples are ordered escalation
  ladders, not just closed sets — this capability is the runtime consumer of that ordering);
  `{#operator-choice-framework}` (operator-choice stays doc-only, CLI-driven `/work` — the
  round-N recovery step is a documented affordance, not a new automated backend);
  `{#external-engine-chaperone-dispatch}` (#318, escalation never introduces a second
  executor kind); `{#plugin-portfolio-groom-17-to-7}` (no new plugin — extend `saga` and
  `work` in place). All from `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2.

## Recommended Executor Profile

- Model: sonnet
- Effort: high
- Backend: inline
- External LLM: none
- Justification: mechanical extension of an already-ordered, already-validated tier
  vocabulary (index arithmetic + one new return-disposition enum value + a documented
  between-rounds affordance) — no architectural ambiguity requiring opus-level judgment,
  but the gating logic (attended-vs-unattended asks, end-clamping, batched pull-cord asks)
  has enough edge-case surface to warrant high effort over medium.

## Release-Surface Checklist

This changes `saga` plugin runtime behavior (new escalation primitive, new return
disposition) and `/work` skill-documented behavior (round-N recovery affordance), so update
in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump + changelog-worthy behavior
      note (new escalation primitive + `pull_cord` disposition).
- [ ] `.claude-plugin/marketplace.json` — synced version for `saga` (and `team-execution` if
      any consensus/validator-order doc cross-reference is touched, though no `saga`
      behavior change is intended there).
- [ ] `plugins/saga/CHANGELOG.md` — entry describing `escalate_tier()`/`bump_tier()`, the
      `escalate_on_signal` segment/verify rung, the `/work` round-N recovery affordance, and
      the `pull_cord` disposition.
- [ ] Version/metadata drift-guard tests (repo's plugin-metadata consistency tests) updated
      to reflect the new `saga` version and confirm plugin.json/marketplace.json/CHANGELOG
      tell the same story as the diff.
- [ ] `docs/engineering-journal/DECISIONS.md` — entry on the one-rung-only + asymmetric-ask
      gating pattern (rationale, rejected alternative of multi-rung jumps, revisit-when: a
      second failure-signal source beyond refute/failed-test/self-report is proposed).

### Verification
```bash
uv run pytest tests/test_execution_spec.py -k "escalate or pull_cord" -v
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; escalation tests confirm one-rung-only, top-of-ladder halt, attended-mode
ask gate, unattended silent climb, and `pull_cord` non-completion + batching.

## Handoff maturity
requirements-ready

## Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Intent

The tier vocabulary is already an explicit, ordered ladder, not a closed set: `MODELS = ("fable", "opus", "sonnet", "haiku")` and `EFFORTS = ("low", "medium", "high", "xhigh")` in `plugins/saga/scripts/execution_spec.py:52-53`, with the ordering called out as load-bearing in the comment at `plugins/saga/scripts/execution_spec.py:47-51` ("ORDERING IS LOAD-BEARING: `segment_units()` merges tiers upgrade-only via `min(MODELS.index)` / `max(EFFORTS.index)`"). `segment_units()` already performs that upgrade-only merge at `plugins/saga/scripts/execution_spec.py:1474-1476`.

### Context library links

_none_

### Files expected to change

- `docs/sdlc-issue-drafts/2026-06-27-capability-infiquetra-claude-plugins-campps-work-2.md`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/saga/scripts/execution_spec.py`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T3.json`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T12.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`

### Tests to add or update

- `tests/test_execution_spec.py`

### Objective

"Make tier+effort a first-class priced resolvable lever"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/364
- Number: 364
- Created at: 2026-07-04T07:50:40.914636+00:00

