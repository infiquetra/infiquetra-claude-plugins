---
title: "enhancement: run-scoped spend budgets — threshold envelope, emit-time cost HALT, cost-weight table, effort escrow"
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
objective: "Make tier+effort a first-class priced resolvable lever"
---

# enhancement: run-scoped spend budgets — threshold envelope, emit-time cost HALT, cost-weight table, effort escrow

### Objective
Make tier+effort a first-class priced resolvable lever

## Summary

The fleet has exactly one operator-facing model/effort lever — saga `/plan`'s unit tier
table (`plugins/saga/skills/plan/SKILL.md:296-352`), backed by the ordered vocabularies
`MODELS = ("fable", "opus", "sonnet", "haiku")` and `EFFORTS = ("low", "medium", "high",
"xhigh")` (`plugins/saga/scripts/execution_spec.py:52-53`) — but that lever has no notion
of cost. Tiers are ordered, not priced: nothing sums what a plan actually costs, nothing
lets an operator cap it, and nothing collapses "ask me before every expensive choice"
into "ask me once." This issue merges four independently-surviving ideation facets into
one priced-budget primitive: a shared ordinal cost-weight table, a run-scoped spend
envelope that only interrupts on a threshold crossing, an emit-time HALT when an authored
plan's total exceeds a declared ceiling, and a per-unit effort-escrow ledger for
refund/escalation semantics.

## Problem / Motivation

- **The tier ladder has an ordering but no magnitude.** `MODELS`/`EFFORTS` in
  `plugins/saga/scripts/execution_spec.py:52-53` establish that `fable`/`xhigh` costs more
  than `haiku`/`low`, but nothing turns that ordering into a comparable number. Every
  plugin that wants to say "this is expensive" has to hand-roll its own sense of
  expensive — reproducing the ad hoc tier reasoning the grounding brief's session-mining
  synthesis flagged as a recurring pattern (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  §7, pattern reference to ad hoc cost reasoning; §1 "Model/effort reality").
- **Approval today is a per-decision interrupt, not a budget.** The intake's spend-approval
  rule treats every spend-increasing choice (parallel fan-out, cache churn, tier
  escalation) as requiring its own explicit operator yes, "asked once per run start" in
  aspiration only — the moment a run has several spend-increasing choices, "asked once"
  stops being literally true. A run-scoped envelope that is set once and only interrupts
  on a threshold crossing is the only shape that keeps the "asked once" promise honest
  while preserving the cheap-silent/expensive-asks asymmetry
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2, `{#operator-choice-framework}`
  row: operator-choice is doc-only, CLI-driven — the envelope must be a CLI-set field, not
  a new autonomous gate).
- **The fleet already has an emit-time HALT precedent for structural bounds, but not for
  spend.** `VERIFY_N_CAP = 7` (`plugins/saga/scripts/execution_spec.py:114`) fails
  `validate`/`emit` loudly rather than silently emitting an over-large verify panel — born
  from a real 22-judge panel rate-limit incident
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §1, "Concurrency governance").
  Spend has no equivalent: an authored plan can be arbitrarily expensive and nothing stops
  it before a token is spent. The binding `/outcome` campaign decision is HALT-not-degrade,
  never a silent trim (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2, `/outcome
  campaign (U1–U11)` row).
- **Effort is a label with no lifecycle accounting.** The pre-existing seed
  `{#team-execution-per-teammate-effort}` (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  §5) is the direct "why can't I pick effort?" ask; today no agent frontmatter across any
  of the 8 plugins carries an `effort:` field (0 of 24 in team-execution per the fleet map,
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §1), and nothing records
  actual-vs-planned spend per unit, so cheap units can't refund unused budget and risky
  units can't request escalation before they run.

## Definition of Done

Ship one merged PR (plus follow-on facet for effort escrow, see Scope) that lands:

1. `plugins/saga/references/cost_weights.json` — a 16-cell ordinal weight table (4 models ×
   4 efforts) consistent with the `MODELS`/`EFFORTS` ordering in
   `plugins/saga/scripts/execution_spec.py:52-53`, plus a `to_spend()` helper that turns a
   list of (model, effort) tiers into one comparable spend figure. Weights are ordinal
   (relative units), never asserted dollar prices.
2. An optional `spend_envelope` field on the run/outcome spec plus gate logic: spend-increasing
   choices below the remaining envelope proceed silently; a choice that would cross the
   remaining envelope is the only one that prompts.
3. An optional `cost_budget` field on `ExecutionSpec` plus an emit-time check — mirroring the
   `VERIFY_N_CAP` block at `plugins/saga/scripts/execution_spec.py:355-363` — that sums
   declared unit tiers via `to_spend()` and raises a `SpecError` naming the total versus the
   ceiling when the authored plan exceeds it, before any unit executes.
4. As a follow-on facet (may land in a subsequent PR against the same issue): an effort-escrow
   ledger (`effort_ledger.py` + `effort-policy.yaml`) recording actual-versus-planned effort per
   unit, with refund semantics for unused budget and an escalation-request surface for units
   that need more than their declared allocation, wired into `/plan` and `/work`.

Verification: `uv run pytest` covers weight monotonicity, envelope gate behavior, emit-time
HALT behavior, and (for the escrow facet) refund/escalation semantics; `uv run ruff check .`
and `uv run mypy plugins/` stay green.

### Acceptance criteria
- [ ] **Weight monotonicity** — `to_spend()` of any (model, effort) cell where either axis is
  strictly higher on the `MODELS`/`EFFORTS` ordering (`plugins/saga/scripts/execution_spec.py:52-53`)
  produces a strictly higher weight; a `fable`/`xhigh` unit's weight exceeds any `haiku`/`low`
  unit's weight. Check: `uv run pytest tests/test_cost_weights.py -k monotonicity` → passes.
- [ ] **Sub-threshold sequence yields zero prompts** — a simulated sequence of spend-increasing
  choices that each stay under the remaining `spend_envelope` produces zero operator prompts.
  Check: `uv run pytest tests/test_spend_envelope.py -k sub_threshold_silent` → passes.
- [ ] **Crossing choice yields exactly one prompt** — a simulated sequence where one choice
  would cross the remaining envelope produces exactly one prompt, at the crossing choice only.
  Check: `uv run pytest tests/test_spend_envelope.py -k crossing_prompts_once` → passes.
- [ ] **Over-budget spec fails emit naming total vs ceiling** — a fixture `ExecutionSpec` whose
  summed unit tiers (via `to_spend()`) exceed a declared `cost_budget` fails `validate`/`emit`
  with a `SpecError` message naming both the computed total and the ceiling. Check:
  `uv run pytest tests/test_execution_spec.py -k cost_budget_halt` → passes.
- [ ] **Under-budget spec passes emit unchanged** — a fixture `ExecutionSpec` whose summed unit
  tiers are within `cost_budget` (or with no `cost_budget` declared) passes `validate`/`emit`
  exactly as before this change. Check: `uv run pytest tests/test_execution_spec.py -k
  cost_budget_pass` → passes.
- [ ] **No `cost_budget`/`spend_envelope` declared degrades safely** — a run with neither field
  set behaves identically to pre-change behavior (no prompts introduced, no emit failures
  introduced). Check: `uv run pytest tests/test_execution_spec.py -k cost_budget_absent_noop`
  → passes.
- [ ] **(Follow-on facet) Escrow refund** — a unit that under-spends its declared effort
  allocation refunds the unused budget to the run-level ledger. Check: `uv run pytest
  tests/test_effort_ledger.py -k refund` → passes.
- [ ] **(Follow-on facet) Escrow escalation surfaces before execution** — a unit flagged as
  risky that would exceed its declared allocation raises an escalation request that surfaces
  to the operator before that unit executes, not after. Check: `uv run pytest
  tests/test_effort_ledger.py -k escalation_before_execution` → passes.
- [ ] Full suite, format, lint, types stay green. Check: `uv run pytest && uv run ruff format
  --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/
  --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
- **In scope:** `cost_weights.json` + `to_spend()`; `spend_envelope` field + threshold-crossing
  gate on the run/outcome spec; `cost_budget` field + emit-time `SpecError` HALT on
  `ExecutionSpec`, mirroring the existing `VERIFY_N_CAP` pattern exactly (same fail-loud shape,
  not a new failure taxonomy).
- **Deferred to a follow-on PR against this same issue, not blocking it:** the effort-escrow
  ledger (`effort_ledger.py`, `effort-policy.yaml`) and its `/plan`/`/work` integration. The
  cost-weight table and the two HALT/envelope mechanisms are usable and independently
  verifiable without escrow; escrow is additive on top of them.
- **Not asserting real dollar prices.** Weights stay ordinal/relative so the primitive is
  stable across provider price changes — this issue does not add a pricing API integration or
  live-cost telemetry.
- **Not a new autonomous gate.** The envelope is a CLI-set field on the spec, consistent with
  `{#operator-choice-framework}` — this issue does not add background/unattended spend
  decisions; an unattended run with no envelope set falls back to the existing silent-cache-tight
  default, unchanged.
- **Not changing `VERIFY_N_CAP` or the existing structural-bound machinery** — this issue reuses
  its pattern for spend, it does not modify or generalize the verify-panel cap itself.
- **Not changing team-execution's reviewer fan-out or its own concurrency posture** — spend
  budgeting here is scoped to the saga `/plan`/`ExecutionSpec`/`/outcome` surface named above;
  team-execution consumption of the shared `cost_weights.json` (if any) is a future integration,
  not part of this issue's DoD.
- **Not full implementations of a fleet-wide provider-router** — `X-codex-15`'s framing
  ("external providers, local models, and Claude tiers all drawing from the same abstract
  budget") is captured here only as the escrow ledger's data model, not as a routing engine.

## Grounding References

- `T12-F3-3` (primary, direct basis) — run-scoped spend-envelope reframe of the per-decision
  approval rule; basis: intake §1 "any spend-increasing choice ... always requires explicit
  operator yes ... asked once per run start," and `{#operator-choice-framework}` (doc-only,
  CLI-driven).
- `T12-F6-6` (facet, direct basis) — spec-level `cost_budget` HALT reusing the emit-time
  fail-loud pattern; basis: `plugins/saga/scripts/execution_spec.py:111-114` (`VERIFY_N_CAP`
  block) and the `/outcome` campaign's binding HALT-not-degrade decision
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2).
- `T12-F4-8` (facet, reasoned basis) — the shared ordinal `cost_weights.json` +
  `to_spend()` helper; basis: first-principles argument that comparable before/after cost
  display requires one shared unit, tied to the `MODELS`/`EFFORTS` ordering at
  `plugins/saga/scripts/execution_spec.py:52-53`.
- `T3-F5-7` (facet, reasoned basis) — Kubernetes ResourceQuota/QoS-class framing for a
  run-level cost ceiling that HALTs rather than silently downgrades; basis: `execution_spec.py:53`
  ordering plus the `/outcome` binding's HALT-not-degrade rule.
- `X-codex-15` (facet, external basis — codex/GPT proposal) — effort escrow: per-unit
  spendable budget with refund/escalation semantics and a pre-execution ledger; consensus
  participation here is advisory-only per `{#external-engines-never-gatekeepers}`
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2) — this facet informs the data
  model, Claude remains verifier-of-record for any gated escalation decision.
- Binding decisions this issue must not contradict: `{#operator-choice-framework}` (envelope is
  CLI-set, not autonomous), `/outcome` campaign HALT-not-degrade (U1–U11), `{#tier-vocab-ordering}`
  (tiers are an ordered escalation ladder, which `cost_weights.json` must respect),
  `{#external-engines-never-gatekeepers}` (escrow escalation decisions stay Claude-gated).

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** mechanical, well-scoped data-modeling and gate-logic work against an
  existing, well-precedented pattern (`VERIFY_N_CAP`) — no architectural ambiguity requiring
  opus-level judgment, but high effort is warranted given four facets to reconcile into one
  coherent schema and the emit-time HALT's correctness-criticality (a false-negative here
  silently lets an over-budget run proceed, violating HALT-not-degrade).

## Release-Surface Checklist

This issue changes plugin behavior (new spec fields, new emit-time failure mode) — the
following must be updated in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump; changelog entry pointer.
- [ ] `.claude-plugin/marketplace.json` — saga plugin metadata/version kept in sync.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting `spend_envelope`, `cost_budget`,
  `cost_weights.json`, and (if landed in this PR) the effort-escrow ledger.
- [ ] Any version/metadata drift-guard tests (e.g. plugin.json/marketplace.json parity tests)
  updated to reflect the new version and pass.
- [ ] `plugins/saga/skills/plan/SKILL.md` unit-tier table (`:296-352`) updated to document the
  new `spend_envelope`/`cost_budget` fields and how they interact with tier selection.

## Files Expected to Change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/references/cost_weights.json` — new 16-cell ordinal weight table.
- `plugins/saga/scripts/execution_spec.py` — `to_spend()` helper, `spend_envelope` field +
  gate logic, `cost_budget` field + emit-time `SpecError` HALT (mirroring `:111-114`).
- `plugins/saga/scripts/effort_ledger.py` — new (follow-on facet): per-unit escrow ledger.
- `plugins/saga/references/effort-policy.yaml` — new (follow-on facet): refund/escalation
  policy config.
- `plugins/saga/skills/plan/SKILL.md` — unit-tier table documentation update.
- `tests/test_cost_weights.py`, `tests/test_spend_envelope.py`, `tests/test_execution_spec.py`,
  `tests/test_effort_ledger.py` — new/updated tests.
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface updates (see checklist above).

### Verification
```bash
# Cost-weight monotonicity + envelope + emit-time HALT
uv run pytest tests/test_cost_weights.py tests/test_spend_envelope.py tests/test_execution_spec.py -v
# Effort-escrow ledger (if landed in this PR)
uv run pytest tests/test_effort_ledger.py -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the over-budget fixture fails emit naming both the computed total and
the declared ceiling; the sub-threshold/crossing envelope test shows zero prompts then
exactly one.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T12.json (T12-F3-3,
  T12-F6-6, T12-F4-8), docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T3.json
  (T3-F5-7), docs/plans/plugin-fleet-ideation-2026-07-03/survivors/OTHER.json (X-codex-15)
- Source type: ideation-survivor-merge
- Source title: Run-scoped spend budgets: threshold envelope, emit-time cost HALT,
  cost-weight table, and effort escrow

### Intent

The fleet has exactly one operator-facing model/effort lever — saga `/plan`'s unit tier table (`plugins/saga/skills/plan/SKILL.md:296-352`), backed by the ordered vocabularies `MODELS = ("fable", "opus", "sonnet", "haiku")` and `EFFORTS = ("low", "medium", "high", "xhigh")` (`plugins/saga/scripts/execution_spec.py:52-53`) — but that lever has no notion of cost. Tiers are ordered, not priced: nothing sums what a plan actually costs, nothing lets an operator cap it, and nothing collapses "ask me before every expensive choice" into "ask me once." This issue merges four independently-surviving ideation facets into one priced-budget primitive: a shared ordinal cost-weight table, a run-scoped spend envelope that only interrupts on a threshold crossing, an emit-time HALT when an authored plan's total exceeds a declared ceiling, and a per-unit effort-escrow ledger for refund/escalation semantics.

### Context library links

_none_

### Files expected to change

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/saga/references/cost_weights.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/saga/skills/plan/SKILL.md`
- `plugins/saga/scripts/execution_spec.py`
- `plugins/saga/scripts/effort_ledger.py`

### Tests to add or update

- `tests/test_cost_weights.py`
- `tests/test_effort_ledger.py`
- `tests/test_execution_spec.py`
- `tests/test_spend_envelope.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/366
- Number: 366
- Created at: 2026-07-04T07:51:16.246707+00:00

