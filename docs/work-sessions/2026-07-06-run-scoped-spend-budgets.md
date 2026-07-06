---
title: Work session — run-scoped spend budgets (#366)
issue: infiquetra/infiquetra-claude-plugins#366
plan: docs/plans/2026-07-06-run-scoped-spend-budgets-plan.md
branch: feat/366-run-scoped-spend-budgets
date: 2026-07-06
---

# Work session — run-scoped spend budgets (#366)

**Built the full DoD (all four facets in one PR, per the operator's full-DoD decision).** saga +
fleet_commons; full repo gate green. Six units, backend inline, destination merge.

## What was built (by U-ID)

- **U1 — cost-weight table** (`plugins/fleet-core/scripts/fleet_commons/cost_weights.json` +
  `cost_weights.py`): a 16-cell ordinal weight grid and `to_spend(model, effort)`, co-located with
  `models.json` and validated against the live `tier_palette` ordering at import — completeness,
  per-axis strict monotonicity, and off-palette rejection all raise `CostWeightsError` (drift fails
  loud, closing the `{#tier-vocab-ordering}` gap). Weights hand-authored non-linear (KTD1/KTD2).
- **U2 — `cost_budget` emit-time HALT** (`execution_spec.py`): optional `ExecutionSpec.cost_budget`;
  `validate()`/`emit` raise a `SpecError` naming total vs ceiling when `spec_spend()` exceeds it
  (mirrors `VERIFY_N_CAP`, soft warn band). The multiplicity-aware `unit_spend()` counts fan-out
  target count and verify-panel `n` × iterations — a `pilot` is a separate declared unit, never
  re-added (double-count guard, KTD8). This is the correctness-critical facet.
- **U3 — `spend_envelope` + accumulator + `spend` CLI** (`execution_spec.py`): optional
  `ExecutionSpec.spend_envelope`; the pure `SpendEnvelope.consider(delta)` prompts only on the
  crossing choice ("ask once, at the crossing"); `execution_spec.py spend <spec>` reports per-unit
  spend, total, budget headroom, and the envelope — the real read-consumer `/plan` invokes.
- **U4 — effort-escrow ledger** (`effort_ledger.py` + `references/effort-policy.yaml`): `EffortLedger`
  records per-unit actual-vs-planned spend, refunds an under-spending unit's unused allocation to a run
  pool, and surfaces an escalation-request **before** a unit executes when it would exceed allocation.
  CLI verbs `allocate`/`record`/`escalate`/`report`; PyYAML policy; absent file → safe default.
- **U5 — skill wiring**: `plan/SKILL.md` §5.2a Step 1b (price the plan, set the guards);
  `work/references/execution-strategy.md` effort-escrow accounting (named CLI calls at the dispatch +
  completion seams); `pr-continuation-loop.md` envelope-consult note on the #364 between-rounds gate.
- **U6 — release surface**: saga `0.68.0 → 0.69.0` (plugin.json, marketplace sync via
  `sync_marketplace.py`, `test_saga_plugin.py` pin); CHANGELOG `[0.69.0]`; `references/execution-spec.md`
  documents the fields, HALT, and `spend` verb; DECISIONS `{#run-scoped-spend-budgets-366}` (KTD1-KTD8).

## Key decisions resolved against the issue's indicative guidance

- `cost_weights.json` moved to `fleet_commons/` (beside `models.json`, the ordering it prices) rather
  than the issue's indicative `saga/references/` — drift-guarded co-location (KTD1).
- Budget fields on `ExecutionSpec` (per-run), not `OutcomeSpec` — the coordinator keeps its derived
  `cost_rollup`; a run-scoped budget there would fight the HALT-not-degrade cost-ledger law (KTD4).
- KTD8 (multiplicity summation) was surfaced by doc-review as a P1: a one-weight-per-unit sum would
  false-negative the HALT on exactly the expensive fan-out/panel plans. Built correctly from the start.

## Gates

- `uv run pytest` — 2304 passed, 1 skipped (33 new tests: cost_weights 7, spend_envelope 6,
  effort_ledger 10, execution_spec +10). Every issue-AC `-k` selector resolves: `monotonicity`,
  `sub_threshold_silent`, `crossing_prompts_once`, `over_budget`, `refund`, `escalation_before_execution`.
- ruff format/check clean; mypy (CI scope) Success 147 files; bandit `-ll` 0 medium/high severity.

## Next step

Adversarial `/code-review` gate (U2 correctness-critical), then PR + merge on green, then harvest into
the `tier-effort-first-class` outcome. #367 follows.
