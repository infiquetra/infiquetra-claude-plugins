# Issue #452 Engine Registry Schema Currency Code Review

Date: 2026-07-09
Target: branch `work/452-engine-registry-schema-currency`
Base: `origin/main` at `bd78b62b6b66e81fa2d7d994a12dd68f3fa7172f`
Reviewed revision: `85849edd89fc2e96aa62f893e1b273062a52fea5`
Issue: `infiquetra/infiquetra-claude-plugins#452`
Plan: `docs/plans/2026-07-09-issue-452-engine-registry-schema-currency-plan.md`
Work session: `docs/work-sessions/2026-07-09-issue-452-engine-registry-schema-currency.md`
Reviewer backend: `inline`
Verdict: PASS

## Scope Check

Scope Check: CLEAN
Intent: make Saga engine-registry schema currency data-first with capability, family, cost, staleness,
and surface-intent defaults.
Delivered: branch adds plan/review artifacts, registry schema/data changes, resolver/dispatch metadata
surfacing, named CI lint, data-driven offer defaults, release-surface bump, tests, and work-session
evidence.

## Review Team

- correctness: always-on; checked capability vocabulary propagation, family-default materialization,
  stale-row behavior, resolver output, and dispatch warning threading.
- security: always-on; checked new YAML loaders avoid secret materialization and dispatch warnings remain
  advisory provenance rather than gate authority.
- testing: always-on; checked registry, resolver, dispatch, lint, offer-default, release-surface, and
  broad local gate evidence.
- maintainability/conventions: always-on; checked data ownership, release surfaces, work-session, and
  existing preference override behavior.
- deploy/migration-verification: selected because the diff adds a named CI validation step.

## Plan Completion

COMPLETION: 6/6 DONE, 0 PARTIAL, 0 NOT-DONE, 0 CHANGED, 0 UNVERIFIABLE

- DONE U1: `engine_registry.py` widens `CAPABILITIES` and the shipped registry resolves
  `bulk-classification`, `structured-extraction`, and `embedding` via
  `tests/test_saga_engine_registry.py:419`.
- DONE U2: `engine_registry.py:171` parses `model_families`, `engine_registry.py:190` materializes
  family defaults, and `tests/test_saga_engine_registry.py:424` covers shipped Codex defaults.
- DONE U3: `engine_registry.py:153` validates `cost_per_token`, `engine_registry.py:164` validates
  `latency_class`, and `engine_resolver.py:606` exposes cost, latency, and input-cost estimates.
- DONE U4: `check_engine_registry.py:39` loads the registry, `check_engine_registry.py:40` loads release
  data, and `.github/workflows/ci.yml:78` adds the named `Engine Registry` step.
- DONE U5: `engine_resolver.py:642` emits stale warnings and `engine_dispatch.py:362` copies them into
  advisory provenance; `tests/test_saga_engine_dispatch.py:1089` proves warning-only evidence does not
  satisfy gates.
- DONE U6: `surface_intent_defaults.yaml` owns stage/shape defaults, `engine_offer.py:205` loads them,
  and `tests/test_engine_offer.py:203` proves a stage default changes from data.

## Findings

No P0/P1/P2/P3 findings.

## Coverage

Suppressed count: 0

Residual risks:

- `cost_per_token` remains authored metadata, not telemetry; future price-aware routing still needs a
  separate measured-data design.
- staleness depends on humans updating `plugins/saga/references/model-releases.yaml` when model revision
  dates advance.

Testing gaps:

- No remaining blocker. Broad local pytest passed with the two known Redis-channel live-service tests
  ignored, matching prior leaf practice.

## Checks Reviewed

- `python3 -m py_compile plugins/saga/scripts/engine_offer.py plugins/saga/scripts/check_engine_registry.py plugins/saga/scripts/engine_registry.py plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_dispatch.py`
- `uv run pytest tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_engine_registry_lint.py tests/test_engine_offer.py tests/test_saga_plugin.py -q`
- `uv run ruff check plugins/saga/scripts/engine_offer.py plugins/saga/scripts/check_engine_registry.py plugins/saga/scripts/engine_registry.py plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_dispatch.py tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_engine_registry_lint.py tests/test_engine_offer.py tests/test_saga_plugin.py`
- `uv run python plugins/saga/scripts/check_engine_registry.py`
- `uv run pytest tests/test_saga_engine_registry.py -q`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python scripts/check_release_surface_parity.py`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
- `git diff --check`
- `COVERAGE_FILE=/tmp/cov-452-full uv run pytest -q --ignore=tests/test_redis_channel_channel.py --ignore=tests/test_redis_channel_notifier.py`
- `uv run pytest tests/test_saga_engine_registry.py tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_engine_registry_lint.py tests/test_engine_offer.py tests/test_saga_plugin.py -q`

## Route

PR-ready. Commit artifact, open PR, monitor CI, merge when checks stay green.
