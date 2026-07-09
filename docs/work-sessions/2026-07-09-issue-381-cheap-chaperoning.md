# Issue #381 Cheap Chaperoning Work Session

## Built

- U1: added `plugins/saga/scripts/chaperone_economics.py` with homogeneous batching,
  verifiability-to-review-mode mapping, evidence-size escalation, deterministic sampling, and
  sampled-defect full-review escalation.
- U2: added optional `Unit.verifiability` to `execution_spec.py`, emitted it in external-engine call
  metadata only when authored, and refreshed the generated `/plan` tier table with a test-gated
  ratify-only offload row.
- U3: documented batch-aware team-execution chaperone context packages and distinct per-unit
  manifest invariants.
- U4: threaded optional chaperone provenance through `engine_dispatch.dispatch()` without changing
  `saga.manifest.v1` or gate semantics.
- U5: added run-scoped payload memoization in `engine_resolver.RunMemo`, keyed by `unit_id`,
  protocol hash, and context hash.
- U6: bumped Saga and Team Execution plugin release surfaces.
- Persistence: added `docs/engineering-journal/narratives/2026-07-09-objective-execution-loop.md`
  as the durable objective/outcome loop reference.

## Checks Run

- `uv run pytest tests/test_chaperone_economics.py -q`
- `uv run ruff check plugins/saga/scripts/chaperone_economics.py tests/test_chaperone_economics.py`
- `uv run pytest tests/test_saga_execution_spec.py tests/test_tier_resolver.py tests/test_tier_vocab_single_source.py -q`
- `uv run pytest tests/test_team_execution_plugin.py -q`
- `uv run pytest tests/test_saga_engine_dispatch.py -q`
- `uv run pytest tests/test_saga_engine_resolver.py -q`
- `uv run pytest tests/test_chaperone_economics.py tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_saga_execution_spec.py tests/test_team_execution_plugin.py tests/test_saga_plugin.py tests/test_tier_resolver.py tests/test_tier_vocab_single_source.py -q`
- `uv run ruff check plugins/saga/scripts/chaperone_economics.py plugins/saga/scripts/execution_spec.py plugins/saga/scripts/engine_dispatch.py plugins/saga/scripts/engine_resolver.py tests/test_chaperone_economics.py tests/test_saga_execution_spec.py tests/test_saga_engine_dispatch.py tests/test_saga_engine_resolver.py tests/test_team_execution_plugin.py tests/test_saga_plugin.py tests/test_tier_resolver.py`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python scripts/check_release_surface_parity.py`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `uv run ruff check .`
- `uv run mypy plugins/`
- `git diff --check`
- `uv run pytest -q --ignore=tests/test_redis_channel_channel.py --ignore=tests/test_redis_channel_notifier.py`
- `uv run bandit -q -r plugins/saga/scripts/chaperone_economics.py plugins/saga/scripts/execution_spec.py plugins/saga/scripts/engine_dispatch.py plugins/saga/scripts/engine_resolver.py -s B101,B105`

## Checks With Caveats

- `uv run pytest -q` failed during collection because local `mcp` is unavailable for
  `tests/test_redis_channel_channel.py` and `tests/test_redis_channel_notifier.py`. The same suite
  passed after excluding only those two collection-failing redis-channel files:
  `2591 passed, 1 skipped`.
- `uv run bandit -q -r plugins/saga/scripts/chaperone_economics.py plugins/saga/scripts/execution_spec.py plugins/saga/scripts/engine_dispatch.py plugins/saga/scripts/engine_resolver.py`
  reported existing low-severity `execution_spec.py` B101/B105 findings; the rerun skipped those
  known advisory rules and passed.

## Next Step

Run code-review, then open the PR and monitor CI.
