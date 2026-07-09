# Issue #391 Task Provider Recommendation Work Session

Date: 2026-07-09
Issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/391
Plan: docs/plans/2026-07-09-issue-391-task-provider-recommend-plan.md
Review: docs/reviews/2026-07-09-issue-391-task-provider-recommend-plan-review.md

## Built

- U1: Added required registry `egress_policy` with closed values `local-only` and `networked`.
- U1: Marked all current seed registry rows `networked`, including in-repo agy rows.
- U2/U3: Added `plugins/saga/scripts/engine_recommend.py` read-only recommendation API over
  `Registry.ranked_candidates()`.
- U2/U3: Implemented `cheapest-viable`, `free-first`, MODERATE default fit floor, context-window
  filtering, sensitive local-only filtering, and explicit halted result when no local-only candidate
  exists.
- U4: Bumped Saga release metadata to `0.75.15` and added changelog coverage.

## Key Decisions

- Kept recommendation separate from `engine_resolver.resolve()` so dispatch/preflight behavior remains
  unchanged.
- `cheapest-viable` sorts viable candidates by `input_usd + output_usd`, then `cost_speed_rank`, then
  `registry_order`.
- Sensitive recommendations never include networked alternatives; no local-only viable row returns a
  halted, empty recommendation.

## Files Modified

- `.claude-plugin/marketplace.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/saga/references/engine-registry.yaml`
- `plugins/saga/scripts/engine_recommend.py`
- `plugins/saga/scripts/engine_registry.py`
- `tests/test_engine_recommend.py`
- `tests/test_engine_registry_cli.py`
- `tests/test_engine_registry_lint.py`
- `tests/test_saga_engine_dispatch.py`
- `tests/test_saga_engine_registry.py`
- `tests/test_saga_engine_resolver.py`
- `tests/test_saga_plugin.py`

## Checks Run

- `uv run pytest tests/test_engine_recommend.py tests/test_saga_engine_registry.py tests/test_engine_registry_lint.py tests/test_saga_engine_resolver.py tests/test_engine_registry_cli.py tests/test_saga_engine_dispatch.py -q`
- `uv run pytest tests/test_engine_recommend.py tests/test_saga_engine_registry.py tests/test_engine_registry_lint.py tests/test_saga_engine_resolver.py tests/test_engine_registry_cli.py tests/test_saga_engine_dispatch.py tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -q`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python scripts/check_release_surface_parity.py`
- `uv run python tools/release_surface_diff_guard.py --base-ref origin/main`
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
- `git diff --check`
- `uv run pytest --ignore=tests/test_redis_channel_channel.py --ignore=tests/test_redis_channel_notifier.py`

## Checks Not Run

- Full unfiltered `uv run pytest` is blocked locally by missing `mcp` during redis-channel test
  collection in `tests/test_redis_channel_channel.py` and `tests/test_redis_channel_notifier.py`.

## Next Step

Run `/code-review`, address any findings, then open the PR.
