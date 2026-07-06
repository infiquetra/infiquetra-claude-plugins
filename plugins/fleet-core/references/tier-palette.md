# Tier palette — adding a model or effort

The fleet's model/effort vocabulary is **single-source**: it lives in
[`scripts/fleet_commons/models.json`](../scripts/fleet_commons/models.json) and is derived into the
ordered `MODELS` / `EFFORTS` tuples by [`tier_palette.py`](../scripts/fleet_commons/tier_palette.py) at
import. Every other surface — `execution_spec.py`, the `/plan` tier table, the team-execution worker
table, the ladder ops — reads from there. Grow the vocabulary **here**, never with a second bare literal
elsewhere (a repo-wide guard, `tests/test_tier_vocab_single_source.py::test_no_bare_model_literals_outside_module`,
fails the build if a second vocabulary source appears in production Python).

## The load-bearing rule (`{#tier-vocab-ordering}`)

> A tuple used for **membership** *and* **ordering** has two contracts. Before extending a closed
> vocabulary, `grep` for `.index(` on it — a wrong insertion point silently mis-tiers every
> upgrade-only merge.

`MODELS` is **strongest-first** (rank 0 = strongest) and `EFFORTS` is **weakest-first** (rung 0 =
weakest) — the two run in *opposite* directions. That is exactly why callers must use `model_rank()` /
`effort_rank()` or the `escalate` / `downgrade` / `clamp` / `stronger` ladder ops, which reason in
**strength**, and must never hand-roll `MODELS.index(...)` / `EFFORTS.index(...)` arithmetic.

## To add a model

1. Add a row to `models.json` under `"models"` with an explicit integer `rank` and an `effort_ceiling`
   (the strongest effort the model actually runs). **Ranks must stay contiguous `0..n-1`** — inserting a
   new strongest model means renumbering the existing ranks, not squeezing in a duplicate or a gap.
   Import-time validation (`_derive_ordered`) rejects a duplicate/gapped/non-int rank loudly.
2. Run `uv run pytest tests/test_tier_vocab_single_source.py` — the registry-order, ladder-monotonicity,
   and effort-ceiling guards confirm the new row slots in without mis-tiering.
3. If the model needs the budget-discipline rider (a cheap model), add it to `CHEAP_MODELS` in
   `tier_palette.py`.

## To add an effort

1. Add a row to `models.json` under `"efforts"` with an explicit integer `rung` (0 = weakest), keeping
   the rungs contiguous.
2. Review every model's `effort_ceiling`: a new top effort is **not** automatically reachable by a
   weaker model — set each `effort_ceiling` deliberately so an unsupported `{model, effort}` combination
   halts at `Tier.validate()` rather than running an un-runnable tier.
3. Run the guard suite.

## What you do NOT touch

- The `/plan` tier table and the team-execution worker table are **rendered/validated against the
  registry** — a hand-edit that drifts from the vocabulary fails
  `tests/test_tier_resolver.py::test_skill_registry_sync` and the tier-token guards in
  `tests/test_tier_vocab_single_source.py`. Change the registry, not the tables.
- `effort_ceiling` for engine-owned chaperone-dispatch workers — those stay pinned to their chaperone
  tiers (`{#external-engine-chaperone-dispatch}`, #318) and are excluded from the per-teammate ceiling
  HALT.
