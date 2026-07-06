---
title: Run-scoped spend budgets — cost-weight table, spend envelope, emit-time cost HALT, effort escrow
type: feat
status: active
date: 2026-07-06
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/366
---

# Run-scoped spend budgets — cost-weight table, spend envelope, emit-time cost HALT, effort escrow

## Summary

Give the fleet's one model/effort lever a notion of *magnitude*: a shared ordinal cost-weight table
(`to_spend()`), a run-scoped `spend_envelope` that collapses "ask before every expensive choice" into
"ask once per run at the crossing," an emit-time `cost_budget` HALT on `ExecutionSpec` mirroring the
proven `VERIFY_N_CAP` fail-loud pattern, and an effort-escrow ledger recording actual-vs-planned effort
with refund and pre-execution escalation-request semantics. Operator decision: **full DoD — all four
facets in one PR** (the escrow ledger is not deferred). This is outcome leaf `sub-366` of
`tier-effort-first-class`; issue #367 (the spend-*delta* classifier) follows.

## Problem Frame

Tiers today are **ordered but not priced** (`MODELS`/`EFFORTS` in `tier_palette.py`, re-exported at
`plugins/saga/scripts/execution_spec.py:62-63`): `fable/xhigh` outranks `haiku/low`, but nothing turns
that ordering into a comparable number, nothing sums what a plan costs, nothing lets the operator cap a
run, and every lever that wants to say "this is expensive" hand-rolls its own sense of expensive — the
exact drift `{#tier-vocab-ordering}` warns about (a tuple used for membership *and* ordering has two
contracts, and only one shows up in the validator). Approval is per-decision interrupt, not a run
budget. The fleet already HALTs on a *structural* bound (`VERIFY_N_CAP = 7`, born from a real 22-judge
rate-limit incident) but has no *spend* equivalent, so an authored plan can be arbitrarily expensive
with nothing stopping the tokens. And the effort label carries no lifecycle accounting: no unit records
actual-vs-planned spend, cheap units cannot refund, risky units cannot request escalation before they
run.

## Requirements

- **R1.** `to_spend(model, effort) -> int` returns an ordinal weight for any `{model, effort}` cell,
  strictly higher when either axis moves up the `tier_palette` ordering (strongest-first models,
  weakest-first efforts). `fable/xhigh` exceeds every `haiku/low` weight.
- **R2.** The weight table is validated at load: **completeness** (all `MODELS × EFFORTS` cells
  present), **strict monotonicity** along both `tier_palette` axes, and a **drift guard** against the
  live palette ordering. Any gap, non-monotonic cell, or off-palette key fails loud
  (`CostWeightsError`) — never a silent default.
- **R3.** An optional `cost_budget` field on `ExecutionSpec`: when set, `validate()`/`emit` HALT with a
  `SpecError` naming **total vs ceiling** if the summed spend exceeds it. The sum accounts for call
  **multiplicity** (fan-out target count, pilot, verify-panel `n` × iterations — KTD8), not one weight
  per unit. The failure shape mirrors `VERIFY_N_CAP` exactly (fail-loud `SpecError`, both sides named),
  with an optional soft warn band below the ceiling.
- **R4.** An under-budget spec (summed spend ≤ `cost_budget`) validates and emits unchanged; an absent
  `cost_budget` performs no check.
- **R5.** An optional `spend_envelope` field on `ExecutionSpec` plus a pure `SpendEnvelope` accumulator:
  a simulated sequence of spend-increasing choices that stays under the remaining envelope yields
  **zero** prompts; a sequence where exactly one choice crosses the envelope yields **exactly one**
  prompt, on the crossing choice only.
- **R6.** `spend_envelope` and `cost_budget` have a **real consumer** (anti-dead-wiring): a
  `execution_spec.py spend <spec.json>` CLI verb prints per-unit spend, total, budget headroom, and the
  envelope, which `/plan` §5.2a invokes to surface the numbers for operator confirmation. The
  accumulator's crossing semantics are consumed by `/work`'s #364 between-rounds escalation proposal
  (consult the envelope before proposing a spend-increasing climb). The autonomous runtime-gate wiring
  is explicitly **out of scope** (#366: "not a new autonomous gate; the envelope is a CLI-set field").
- **R7.** An effort-escrow ledger (`effort_ledger.py`): records per-unit actual-vs-planned effort;
  **refunds** an under-spending unit's unused allocation to a run-level pool; **surfaces an
  escalation-request BEFORE a unit executes** (not after) when a unit flagged risky would exceed its
  declared allocation.
- **R8.** `effort-policy.yaml` configures refund/escalation policy (loaded via PyYAML like
  `engine_registry.py`); an absent policy file resolves to a documented safe default (no auto-refund
  beyond allocation, escalation-request surfaced not auto-approved).
- **R9.** `/plan` authors `cost_budget`/`spend_envelope`/per-unit effort allocations at §5.2a
  (after tiers are locked — tiers are the input to `to_spend()`); `/work` records actuals, applies
  refunds, and surfaces escalation-requests at the `execution-strategy.md` dispatch/complete seams.
- **R10.** Every new optional field on `ExecutionSpec`/`Unit` round-trips **byte-identical** when
  absent — existing specs and `team_emitter` gain no new key (the `min_tier`/`escalate_on_signal`
  precedent).
- **R11.** Release surface synced in the same PR: saga `plugin.json` → `0.69.0`, marketplace entry,
  `CHANGELOG.md`, version-pin test `tests/test_saga_plugin.py:49`, `references/execution-spec.md` doc,
  `plan/SKILL.md` authoring step, and a `DECISIONS.md` entry.
- **R12.** Full gate green: `uv run pytest && uv run ruff format --check . && uv run ruff check . &&
  uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`; bandit `-ll` clean on changed
  scripts.

## Key Technical Decisions

**KTD1 — `cost_weights.json` + a `cost_weights.py` loader live in `fleet_commons/`, beside
`models.json`, NOT in `saga/references/`.** This deviates from the issue's *indicative*
`plugins/saga/references/cost_weights.json` (the issue delegates the exact path to `/plan`). Rationale:
the weight table must not drift from the `tier_palette` ordering it prices; co-locating it with the
ordering source and validating monotonicity at load closes the `{#tier-vocab-ordering}` two-contracts
gap. `execution_spec.py` loads it via `fleet_commons_shim.load("cost_weights")`, symmetric with how it
already loads `tier_palette`. saga/references carries zero `.json` files today; fleet_commons is the
home for shared tier data.

**KTD2 — weights are hand-authored ordinal values (non-linear allowed), not pure `rank + rung`
arithmetic.** A hand-authored table lets `xhigh`/`opus`/`fable` be *disproportionately* expensive (a
real cost signal) rather than linearly spaced, while the load-time monotonicity guard keeps it honest.
Weights stay ordinal/relative — no dollar prices, no pricing-API integration (#366 out-of-scope: stable
across provider price changes).

**KTD3 — the `cost_budget` HALT mirrors `VERIFY_N_CAP` exactly** (`execution_spec.py:489-500`): same
fail-loud `SpecError`, message naming both sides ("total spend N exceeds cost_budget M"), optional soft
warn band. Rationale: this is the correctness-critical facet — a false-negative silently lets an
over-budget run proceed, violating the `/outcome` campaign's binding **HALT-not-degrade** rule. Reuse
the proven pattern, not a new failure taxonomy. **This unit (U2) carries the adversarial verify gate at
merge.**

**KTD4 — `spend_envelope` and `cost_budget` live on `ExecutionSpec` (per-run), not `OutcomeSpec`.**
`OutcomeSpec` keeps its derived `cost_rollup` (R24 leaf-produced fact); a run-scoped *budget* on the
coordinator would fight the grounding-brief `/outcome` law ("cost ledger = leaf-produced fact /
HALT-not-degrade"). This resolves the DoD's "run/outcome spec" ambiguity toward the per-run spec; any
outcome-level rollup view is out of scope.

**KTD5 — `SpendEnvelope` is a pure accumulator primitive**, tested in isolation. Crossing semantics:
a choice crosses iff `cumulative + delta > envelope` while `cumulative <= envelope` (the single
boundary point), so a sequence with one crossing prompts exactly once. Its consumers are the `spend`
CLI verb (R6, real Python read) and `/work`'s #364 between-rounds escalation (doc). The autonomous
runtime gate is deliberately not built (#366: "not a new autonomous gate").

**KTD6 — the effort-escrow ledger is a self-contained module with pure operations**
(`allocate` / `record_actual` / `refund` / `request_escalation`); `effort-policy.yaml` is real config
the ledger loads. Producer = `/work` records actuals; consumers = the refund/escalation computation and
`/plan` reading the policy. The escalation-request surfaces **pre-execution**, mirroring #364's
between-rounds gate pattern (`pr-continuation-loop.md:49`). Allocations are expressed in the shared
ordinal spend unit (`to_spend()`), so escrow and budget speak one currency.

**KTD7 — new test files are `tests/test_cost_weights.py`, `tests/test_spend_envelope.py`,
`tests/test_effort_ledger.py`; the `cost_budget` over/under-budget tests land in the EXISTING
`tests/test_saga_execution_spec.py`.** The issue names `tests/test_execution_spec.py`, which does not
exist in this repo (same reconciliation #364 made). The AC `-k` selectors (`monotonicity`,
`sub_threshold_silent`, `crossing_prompts_once`, `over_budget`, `refund`,
`escalation_before_execution`) become test-function-name fragments so every AC's `-k` check resolves.

**KTD8 — `cost_budget` spend summation accounts for call MULTIPLICITY, not one weight per unit
(readiness P1).** A unit is not always one agent call: a fan-out unit runs its op `len(targets)` times
(`execution_spec.py:1061,1518`), and a `verify` panel adds `n` verifier calls at the unit's tier (×
`max_iterations` when `iterate_to_consensus`). The summed spend is therefore `Σ over units of
unit_spend`, where `unit_spend = to_spend(tier) × max(len(targets), 1) + (verify ? verify.n ×
to_spend(tier) × (iterate_to_consensus ? max_iterations : 1) : 0)`. A `pilot` is deliberately **not**
an addend here: it is a separate declared unit already counted on its own row, so re-adding it would
double-count. A naive one-weight-per-unit sum would undercount exactly the expensive fan-out/panel plans
and silently false-negative the HALT — the HALT-not-degrade violation this facet exists to prevent. The
multiplicity arithmetic is U2's; U2's adversarial gate verifies it.

## Implementation Units

### U1. Cost-weight table + `to_spend()` in fleet_commons

The shared ordinal magnitude primitive every other facet consumes.

**Scope:** Add `plugins/fleet-core/scripts/fleet_commons/cost_weights.json` (16 cells, 4 models × 4
efforts, hand-authored ordinal, non-linear) and `cost_weights.py` exposing `load_cost_weights()` and
`to_spend(model, effort) -> int`. Validate at load: completeness against `tier_palette.MODELS ×
EFFORTS`, strict monotonicity along both axes, off-palette-key rejection — all raising `CostWeightsError`.
The load runs at **import time** (like `tier_palette` loading `models.json`), so a malformed table
fails fast and loud rather than surfacing lazily mid-run. **Scope note on the guard:** the monotonicity
check is **per-axis** (each single step up either axis strictly increases weight); the *cross-axis*
magnitude (is `opus/low` dearer than `sonnet/xhigh`?) is the author's ordinal judgment encoded in the
values and is NOT machine-checkable beyond the corner invariant `fable/xhigh` > `haiku/low` (R1). `/work`
must not expect the guard to police cross-axis ordering.

**Files:** `plugins/fleet-core/scripts/fleet_commons/cost_weights.json` (new),
`plugins/fleet-core/scripts/fleet_commons/cost_weights.py` (new).

**Test scenarios (`tests/test_cost_weights.py`, new):**
`test_to_spend_monotonicity` — every cell strictly exceeds any cell weaker on either axis;
`fable/xhigh` > every `haiku/low`. `test_cost_weights_completeness_all_cells` — all 16 `MODELS×EFFORTS`
cells present. `test_cost_weights_drift_guard_fails_loud` — a table with a non-monotonic or missing
cell raises `CostWeightsError`. `test_off_palette_key_rejected` — a cell for a model/effort not in the
palette fails load.

### U2. `cost_budget` field + emit-time HALT on ExecutionSpec

The correctness-critical facet — mirrors `VERIFY_N_CAP`; carries the adversarial gate.

**Scope:** Add optional `cost_budget: int | None` to `ExecutionSpec` (from_dict/to_dict/validate,
byte-identical round-trip when absent, R10). Add a `spec_spend()` helper computing the multiplicity-aware
total (KTD8: base tier weight × fan-out target count + pilot + verify-panel `n` × iterations). In
`validate()`, if `cost_budget` is set and `spec_spend()` > budget, raise `SpecError` naming total vs
ceiling (KTD3 shape). Optional soft warn band below the ceiling (stderr, mirroring `VERIFY_N_WARN`).

**Files:** `plugins/saga/scripts/execution_spec.py` (ExecutionSpec dataclass + `spec_spend()` + validate).

**Test scenarios (`tests/test_saga_execution_spec.py`, existing):**
`test_over_budget_spec_fails_emit_naming_total_vs_ceiling` — a spec whose summed spend exceeds
`cost_budget` raises `SpecError` with both numbers in the message. `test_under_budget_spec_passes` —
summed ≤ budget validates/emits clean. `test_over_budget_counts_fanout_and_verify_multiplicity` — a spec
that is under budget on naive per-unit sum but OVER budget once a fan-out unit's target count and a
verify panel's `n` are counted HALTs (KTD8 — guards the false-negative). `test_cost_budget_absent_roundtrips`
— no `cost_budget` key → byte-identical to_dict/from_dict, no spend check. `test_cost_budget_soft_warn_band`
— a spec in the warn band validates but emits a stderr warning.

### U3. `spend_envelope` field + `SpendEnvelope` accumulator + `spend` CLI verb

The "ask once per run" collapse — accumulator primitive + the real read-consumer.

**Scope:** Add optional `spend_envelope: int | None` to `ExecutionSpec` (round-trip, R10). Add a pure
`SpendEnvelope` accumulator (KTD5 crossing semantics). Add a `execution_spec.py spend <spec.json>` CLI
subcommand printing per-unit spend, total, `cost_budget` headroom, and `spend_envelope` (R6
anti-dead-wiring read).

**Files:** `plugins/saga/scripts/execution_spec.py` (field + accumulator + CLI verb).

**Test scenarios (`tests/test_spend_envelope.py`, new):**
`test_sub_threshold_silent` — a sequence of choices all under the remaining envelope yields zero
prompts. `test_crossing_prompts_once` — a sequence where one choice crosses yields exactly one prompt,
on the crossing choice. `test_spend_envelope_absent_roundtrips` — no key → byte-identical. Plus a
`spend`-verb smoke test in `tests/test_saga_execution_spec.py`
(`test_spend_cli_reports_total_and_headroom`).

### U4. Effort-escrow ledger + policy config

Per-unit effort accounting: refund + pre-execution escalation-request.

**Scope:** Add `plugins/saga/scripts/effort_ledger.py` with `EffortLedger`
(`allocate`/`record_actual`/`refund`/`request_escalation`, allocations in `to_spend()` units) and
`plugins/saga/references/effort-policy.yaml` (refund/escalation policy). Ledger loads the policy via
PyYAML; an absent file resolves to the documented safe default (R8). Expose the ledger operations as
`effort_ledger.py` **CLI subcommands** (`allocate` / `record` / `report`), symmetric with the `spend`
verb and with how `saga.py`/`outcome.py`/`execution_spec.py` surface their operations — so `/work`'s
wiring (U5) is a named CLI call, not intent-only prose (readiness P2). The ledger state persists under
git-ignored `.claude/saga/` (machine-local run accounting, never committed).

**Files:** `plugins/saga/scripts/effort_ledger.py` (new),
`plugins/saga/references/effort-policy.yaml` (new).

**Test scenarios (`tests/test_effort_ledger.py`, new):**
`test_refund_unused_allocation` — a unit that under-spends its declared allocation refunds the unused
amount to the run pool. `test_escalation_before_execution` — a risky unit that would exceed its
allocation raises an escalation-request *before* it is marked executed, not after.
`test_absent_policy_default` — with no `effort-policy.yaml`, the ledger resolves the documented safe
default (escalation surfaced, not auto-approved). `test_ledger_actual_vs_planned_roundtrip` —
record→refund→pool arithmetic is conserved.

### U5. `/plan` + `/work` skill wiring

Producer and consumer seams so the fields are not dead-wired.

**Scope:** `plan/SKILL.md` §5.2a — a new authoring step between Step 1 (tier derivation) and Step 2
(thin prompts): surface `cost_budget`/`spend_envelope` via `execution_spec.py spend` and author per-unit
effort allocations via `effort_ledger.py allocate`, operator-confirm before locking.
`work/references/execution-strategy.md` — call `effort_ledger.py record` at the per-unit completion seam
(`## Incremental-commit heuristic`, line 108) to record actual effort and apply refunds, and consult
`effort_ledger.py report` at the pre-dispatch seam (`## Subagent dispatch`, line 70) to surface a
unit's escalation-request BEFORE it runs, mirroring the #364 between-rounds gate in
`pr-continuation-loop.md:49`. Each seam names a concrete CLI call (readiness P2 fix), not just intent.

**Files:** `plugins/saga/skills/plan/SKILL.md`,
`plugins/saga/skills/work/references/execution-strategy.md`,
`plugins/saga/skills/work/references/pr-continuation-loop.md` (envelope-consult note).

**Test expectation:** doc wiring — update `tests/test_saga_docs_coverage.py` if it guards the changed
sections; otherwise `Test expectation: none -- skill-doc wiring, covered by the U1-U4 primitive tests
its prose points at`.

### U6. Release surface + journal

Installed metadata tells the same story as the diff (CLAUDE.md step 6).

**Scope:** saga `plugin.json` `0.68.0 → 0.69.0`; `.claude-plugin/marketplace.json` sync via
`scripts/sync_marketplace.py` + `python3 -m json.tool` check; `plugins/saga/CHANGELOG.md` new
`## [0.69.0]` entry (cost_weights.json, spend_envelope, cost_budget HALT, effort-escrow ledger);
`tests/test_saga_plugin.py:49` pin → `0.69.0`; `plugins/saga/references/execution-spec.md` documents the
new fields, HALT, and CLI verb; `docs/engineering-journal/DECISIONS.md` `{#run-scoped-spend-budgets-366}`
(KTD1-KTD7).

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`,
`plugins/saga/references/execution-spec.md`, `docs/engineering-journal/DECISIONS.md`.

**Test scenarios:** `tests/test_saga_plugin.py` version-pin + marketplace-parity pass at `0.69.0`.

## Dependency Order

`U1` (weights) → `U2` (cost_budget), `U3` (spend_envelope), `U4` (escrow — allocations in `to_spend()`
units). `U2`/`U3`/`U4` → `U5` (wiring needs the fields). `U5` → `U6` (release surface + docs last).
U2/U3/U4 are independently landable once U1 exists.

## Scope Boundaries

**Out of scope (true non-goals):**

- No autonomous runtime spend-gate — `spend_envelope` is a CLI-set field + accumulator primitive
  surfaced to the operator, not a mechanism that silently blocks execution (#366).
- No real dollar prices, no pricing-API integration, no live-cost telemetry — weights stay
  ordinal/relative.
- No `OutcomeSpec` budget field — the coordinator keeps its derived `cost_rollup`; no run-scoped
  budget at the outcome level (KTD4).
- No `team-execution` consumption of `cost_weights.json` — cross-emitter integration is future work.
- No fleet-wide provider-router — the "external providers / local models / Claude tiers draw one
  abstract budget" framing (X-codex-15) is captured only in the ledger's data model, not a routing
  engine.

**Deferred to Follow-Up Work (distinct from non-goals):**

- The spend-*delta* classifier (`spend_delta`, `adjacent_tier`, `worth_it_because`/`cheaper_fallback`,
  `.saga/spend-authority.json`) is **issue #367** — the next outcome leaf, planned separately.
- `team-execution` markdown-emitter consumption of the shared cost unit — revisit when a second
  emitter needs budget parity.

## Risk Analysis & Mitigation

**Highest risk — escrow dead-wiring (U4/U5).** The escrow ledger is the facet the issue specified most
thinly, and the classic failure is a module only its own tests exercise. Mitigation: the plan pins a
**real producer** (`/work` records actuals at the `execution-strategy.md` completion seam) and a **real
consumer** (`/plan` reads `effort-policy.yaml` and sets allocations; the refund/escalation compute reads
the ledger). For inline runs these are skill-prose call sites, not autonomous code — the same posture as
`spend_envelope` — so `/doc-review` should pressure-test whether the U5 wiring names concrete call sites
and not just intent. If U5's wiring reads as intent-only, tighten it to a named CLI verb the skill
invokes (as `spend` is for the budget fields) before `/work`.

**Cost-weight drift (U1).** A hand-authored 16-cell table can silently fall out of step with the
`tier_palette` ordering — exactly the `{#tier-vocab-ordering}` hazard. Mitigation: the load-time
monotonicity + completeness + off-palette guard (`CostWeightsError`) makes drift a loud load failure,
and co-location in `fleet_commons/` keeps the table beside the ordering it prices. A guard test asserts
the table stays monotonic against the *live* palette, so adding a model/effort fails loudly.

**Emit-time HALT false-negative (U2).** A summation bug that under-counts spend would let an over-budget
run proceed silently — a HALT-not-degrade violation. Mitigation: U2 carries the adversarial verify gate
at merge (refute-N over the composed emit-time HALT), per the issue's own opus-level flag.

## Verification

```bash
# Facet tests
uv run pytest tests/test_cost_weights.py tests/test_spend_envelope.py tests/test_effort_ledger.py \
  tests/test_saga_execution_spec.py -k "monotonicity or sub_threshold or crossing or over_budget or \
  under_budget or refund or escalation_before_execution or cost_budget or spend_envelope" -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && \
  uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; each facet test demonstrates the behavior named in its acceptance criterion, and
every issue-AC `-k` selector resolves to a real test.
