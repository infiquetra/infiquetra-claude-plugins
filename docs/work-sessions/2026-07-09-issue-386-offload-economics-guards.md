---
date: 2026-07-09
kind: work-session
issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/386
plan: docs/plans/2026-07-09-issue-386-offload-economics-guards-plan.md
review: docs/reviews/2026-07-09-issue-386-offload-economics-guards-plan-review.md
status: complete
---

# Work Session - Offload Economics Guards

## Summary

Implemented dispatch-time economics guards for Saga external-engine `offload` routes. Metered dispatch
now halts before runner invocation when token break-even, provider budget, or required estimate checks fail;
successful runs carry typed net-savings evidence into manifests and run-ledger engine facts. Advisory offer
previews expose the same economics context to operators without becoming an authority surface.

## Built

- U1: Added registry cost-policy metadata: `cost_class` and provider `budget_ceiling_usd` with validation
  for metered/free rows and provider-namespace consistency across variants.
- U2: Added pure chaperone economics policy helpers for `proceed`, `free-class-proceed`,
  `break-even-halt`, `budget-ceiling-halt`, and `economics-missing-halt` decisions.
- U3: Wired dispatch-time economics enforcement before `_build_invocation()` and before runner execution,
  while preserving resolver halt precedence and advisory-only gate semantics.
- U4: Persisted net-savings evidence through `saga.manifest.v1` manifests and run-ledger `engine` facts,
  with the manifest producer/consumer matrix updated for the new `economics` field.
- U5: Added operator-facing `engine_offer.py` cost-delta previews for complete offload estimates, CLI
  estimate flags, and docs clarifying preview-vs-dispatch authority.
- Release: Bumped Saga release surfaces to `0.75.13`, synced marketplace metadata, and updated changelog
  plus metadata parity tests.

## Commits

- `35411d9` docs(saga): plan offload economics guards
- `ba3ea87` feat(saga): add engine cost policy metadata
- `641453f` feat(saga): add offload economics policy helper
- `3103fdb` feat(saga): enforce offload economics before dispatch
- `dc5d9c8` feat(saga): record offload net savings
- `bc493d6` feat(saga): preview offload economics offers
- `abe9b34` test(saga): sync economics manifest matrix

## Modified Files

- `.claude-plugin/marketplace.json`
- `docs/engineering-journal/DECISIONS.md`
- `docs/plans/2026-07-09-issue-386-offload-economics-guards-plan.md`
- `docs/reviews/2026-07-09-issue-386-offload-economics-guards-plan-review.md`
- `docs/work-sessions/2026-07-09-issue-386-offload-economics-guards.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/saga/references/engine-dispatch.md`
- `plugins/saga/references/engine-registry.yaml`
- `plugins/saga/references/run-fact-ledger.md`
- `plugins/saga/references/saga-spec.md`
- `plugins/saga/scripts/chaperone_economics.py`
- `plugins/saga/scripts/engine_dispatch.py`
- `plugins/saga/scripts/engine_offer.py`
- `plugins/saga/scripts/engine_registry.py`
- `plugins/saga/scripts/engine_registry_cli.py`
- `plugins/saga/scripts/engine_resolver.py`
- `plugins/saga/scripts/provenance_manifest.py`
- `tests/test_chaperone_economics.py`
- `tests/test_engine_offer.py`
- `tests/test_engine_registry_cli.py`
- `tests/test_engine_registry_lint.py`
- `tests/test_manifest_consumer_matrix.py`
- `tests/test_provenance_manifest.py`
- `tests/test_run_ledger.py`
- `tests/test_saga_engine_dispatch.py`
- `tests/test_saga_engine_registry.py`
- `tests/test_saga_engine_resolver.py`
- `tests/test_saga_plugin.py`

## Checks Run

- `uv run pytest tests/test_saga_engine_registry.py tests/test_engine_registry_lint.py tests/test_engine_registry_cli.py tests/test_chaperone_economics.py tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_provenance_manifest.py tests/test_run_ledger.py tests/test_engine_offer.py tests/test_saga_plugin.py -v` - passed, 260 tests.
- `uv run --with pytest --with pytest-cov python -m pytest tests/test_manifest_consumer_matrix.py -v` - passed, 3 tests.
- `uv run --with pytest --with pytest-cov python -m pytest tests/test_chaperone_economics.py tests/test_engine_offer.py -v` - passed, 44 tests.
- `uv run --with pytest --with pytest-cov --with fakeredis python -m pytest` - passed, 2768 tests, 1 skipped.
- `uv run ruff check .` - passed.
- `uv run ruff format --check .` - passed.
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` - passed.
- `uv run python scripts/sync_marketplace.py --check` - passed.
- `uv run python scripts/check_release_surface_parity.py` - passed.
- `git diff --check` - passed.

## Residual Risk

No known implementation blockers. The economics preview is advisory and only appears when supplied estimates
are complete; dispatch remains the hard spending stop for unattended and attended paths.

## Next Step

Run pre-PR `/code-review`, open the PR for issue #386, monitor CI, merge, close the issue, and harvest the
outcome leaf.
