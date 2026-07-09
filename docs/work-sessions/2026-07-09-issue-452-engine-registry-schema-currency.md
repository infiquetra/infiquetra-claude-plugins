# Issue #452 Engine Registry Schema Currency Work Session

Date: 2026-07-09
Branch: `work/452-engine-registry-schema-currency`
Plan: `docs/plans/2026-07-09-issue-452-engine-registry-schema-currency-plan.md`
Review: `docs/reviews/2026-07-09-issue-452-engine-registry-schema-currency-plan-review.md`

## Summary

Implemented Saga engine-registry schema currency: widened the closed capability vocabulary, added
model-family capability inheritance, exposed authored cost and latency metadata through resolver output,
threaded staleness warnings into dispatch provenance, added a named registry CI lint, moved
surface-intent defaults into data, and bumped Saga release surfaces to `0.75.10`.

## Implementation Units

- U1: Added `bulk-classification`, `structured-extraction`, and `embedding` to the closed capability
  vocabulary, with Ollama Cloud rows for bulk/structured work and embeddings-only
  `ollama-cloud/nomic-embed-text`.
- U2: Added top-level `model_families` support so `model_identity` defaults materialize before strict
  row validation, preserving current registry lookup winners.
- U3: Added required row-level `cost_per_token` and `latency_class` metadata, exposed it through
  `engine_resolver.Resolution`, and added input-cost estimates when `token_estimate` is supplied.
- U4: Added `plugins/saga/references/model-releases.yaml`,
  `plugins/saga/scripts/check_engine_registry.py`, CI's named `Engine Registry` step, and lint tests for
  valid, malformed, and stale registry rows.
- U5: Reused one `Registry.stale()` mechanism with two severities: CI hard-fails stale rows while
  dispatch records non-blocking warnings in advisory provenance.
- U6: Added `plugins/saga/references/surface_intent_defaults.yaml` and updated `engine_offer.py` to
  load default stage/shape intent policy from data while preserving `.saga/engine-prefs.json` overrides.

## Modified Files

- `.claude-plugin/marketplace.json`
- `.github/workflows/ci.yml`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/saga/references/engine-registry.yaml`
- `plugins/saga/references/model-releases.yaml`
- `plugins/saga/references/surface_intent_defaults.yaml`
- `plugins/saga/scripts/check_engine_registry.py`
- `plugins/saga/scripts/engine_dispatch.py`
- `plugins/saga/scripts/engine_offer.py`
- `plugins/saga/scripts/engine_registry.py`
- `plugins/saga/scripts/engine_resolver.py`
- `tests/test_engine_offer.py`
- `tests/test_engine_registry_lint.py`
- `tests/test_saga_engine_dispatch.py`
- `tests/test_saga_engine_registry.py`
- `tests/test_saga_engine_resolver.py`
- `tests/test_saga_plugin.py`

## Checks

- `python3 -m py_compile plugins/saga/scripts/engine_offer.py plugins/saga/scripts/check_engine_registry.py plugins/saga/scripts/engine_registry.py plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_dispatch.py`
- `uv run pytest tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_engine_registry_lint.py tests/test_engine_offer.py tests/test_saga_plugin.py -q`
- `uv run ruff check plugins/saga/scripts/engine_offer.py plugins/saga/scripts/check_engine_registry.py plugins/saga/scripts/engine_registry.py plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_dispatch.py tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_engine_registry_lint.py tests/test_engine_offer.py tests/test_saga_plugin.py`
- `uv run python plugins/saga/scripts/check_engine_registry.py`
- `uv run pytest tests/test_saga_engine_registry.py -q`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python scripts/check_release_surface_parity.py`
- `uv run ruff check .`
- `uv run ruff format plugins/saga/scripts/check_engine_registry.py plugins/saga/scripts/engine_offer.py plugins/saga/scripts/engine_resolver.py tests/test_saga_engine_registry.py`
- `uv run ruff format --check .`
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
- `git diff --check`
- `COVERAGE_FILE=/tmp/cov-452-full uv run pytest -q --ignore=tests/test_redis_channel_channel.py --ignore=tests/test_redis_channel_notifier.py`
- `uv run pytest tests/test_saga_engine_registry.py tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_engine_registry_lint.py tests/test_engine_offer.py tests/test_saga_plugin.py -q`

## Residual Risk

`cost_per_token` remains authored metadata, not measured telemetry, and registry staleness depends on
humans updating `model-releases.yaml` when a model revision advances.

## Next Step

Run broader quality gates, perform the pre-PR code-review gate, then open the PR.
