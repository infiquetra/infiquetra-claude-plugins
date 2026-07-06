---
title: Work session — spend-delta machinery (#367)
issue: infiquetra/infiquetra-claude-plugins#367
plan: docs/plans/2026-07-06-spend-delta-machinery-plan.md
branch: feat/367-spend-delta-machinery
date: 2026-07-06
---

# Work session — spend-delta machinery (#367)

**Built the full DoD (all 4 facets + wiring + release).** saga-only; full repo gate green. The **final
leaf** of `tier-effort-first-class` — merging completes the outcome (9/9). Two design decisions emerged
during implementation (baseline = `sonnet/high`; hard-block `require_receipts`-gated), both recorded.

## What was built (by U-ID)

- **U1 — `spend_delta` + `is_escalation` refactor** (`execution_spec.py`): the three-way
  `cheapen`/`escalate`/`lateral` classifier over a shared `_axis_deltas` helper (palette `stronger`,
  never raw `.index()`). `is_escalation` shares the helper but keeps its exact two-way semantics
  (`lateral` deliberately distinct from `escalate`). Built on ordering, not `to_spend` — the cost table
  is injective, so magnitude could never yield `lateral` (KTD1).
- **U2 — `adjacent_tier`**: the relative one-notch lever. `cheaper` reuses `tier_resolver.cheaper_fallback`
  (#362); `dearer` is the symmetric one-rung-up. Boundary calls raise (never clamp/wrap).
- **U3 — worth-it hard-block**: optional `Unit.worth_it_because` + `Unit.cheaper_fallback` (byte-identical
  round-trip absent). `validate(require_receipts=True)` fails a premium tier (above `sonnet/high`) lacking
  a justification or a strictly-cheaper named fallback. `require_receipts`-gated (KTD8) so emit/existing
  specs are untouched; engine-owned units exempt. CLI `validate --require-receipts`.
- **U4 — `spend_authority.py`** + `.saga/spend-authority.json`: a `silent_ceiling` matrix resolving each
  unit `silent`/`ask`; absent → safe default `sonnet/high`; malformed → loud `SpendAuthorityError`. Same
  `is_escalation` predicate as U3, pinned by an exhaustive grid guard test (KTD5).
- **U5 — `/plan` §5.2a Step 1c**: relative override, worth-it receipts (`validate --require-receipts`),
  spend-authority stamp.
- **U6 — release surface**: saga `0.69.0 → 0.70.0` (plugin.json, marketplace, CHANGELOG, pin);
  `execution-spec.md` doc; DECISIONS `{#spend-delta-machinery-367}` (KTD1-KTD9).

## Decisions that emerged during implementation

- **KTD9 — baseline is `sonnet/high`, not `sonnet/medium`.** The issue's premium set "(opus, fable, xhigh
  in either axis)" omits `high`; `is_escalation(sonnet/high, tier)` yields exactly that set and avoids
  retroactively flagging common `sonnet/high` units. Surfaced by 25 test failures on the `sonnet/medium`
  reading.
- **KTD8 — the hard-block is `require_receipts`-gated.** An unconditional `validate()` check (75 emitter
  tests failed) contradicts the issue's own "no retroactive backfill" non-goal. The check is enforced at
  the `/plan` authoring boundary via `validate(require_receipts=True)`; `emit()` and existing specs use
  the default. Interaction: `/tier`-patching (#365) up to a premium tier is subject to the same gate.

## Gates

- `uv run pytest` — 2326 passed, 1 skipped (22 new #367 tests). Every issue-AC `-k` selector resolves:
  `spend_delta`, `worth_it_fallback`, `adjacent_tier_boundary`, `spend_authority_matrix`,
  `spend_authority_absent_default`.
- ruff format/check clean; mypy (CI scope) Success 149 files; bandit `-ll` 0 medium/high severity.
- Saga-only diff — no fleet-core change (`cheaper_fallback` reused, not modified); the diff-aware
  release-surface guard will confirm only saga's surface moved.

## Next step

Adversarial `/code-review` gate, then PR + merge on green, then harvest sub-367 → outcome **9/9 COMPLETE**.
