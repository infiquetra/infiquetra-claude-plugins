# Issue #451 Engine Offer Helper Work Session

Date: 2026-07-09
Branch: `work/451-engine-offer-helper`
Plan: `docs/plans/2026-07-09-issue-451-engine-offer-helper-plan.md`
Review: `docs/reviews/2026-07-09-issue-451-engine-offer-helper-plan-review.md`

## Summary

Implemented the shared Saga `engine_offer` helper as an advisory-only policy primitive for
`ideate`, `brainstorm`, `work`, `doc-review`, and `code-review`. The helper resolves stage and unit
shape into `none`, `offload`, or `second-opinion`, persists repo-local stage preferences in
`.saga/engine-prefs.json`, and uses the canonical fleet-core model/effort vocabulary through
`fleet_commons_shim`.

## Implementation Units

- U1: Added `plugins/saga/scripts/engine_offer.py` with closed stage/intent/shape validation,
  structured `EngineOffer` output, advisory-only defaults, and CLI `offer`/`remember` commands.
- U2: Added schema-versioned preference load/save with atomic replace, malformed JSON errors,
  stored `none` suppression, and idempotent repeated-save coverage.
- U3: Added conservative unit-shape classification: explicit shape wins, judgment terms override
  mechanical text, and unknown work defaults to no offer.
- U4: Added shared helper call-site guidance to the five Saga stage skills and drift-guard tests.
- U5: Bumped Saga release surface to `0.75.8`, updated the changelog, marketplace metadata, version
  assertion, `.gitignore`, and engineering-journal decision.

## Notable Fix

The first broad pytest run failed `tests/test_tier_vocab_single_source.py::test_no_bare_model_literals_outside_module`
because `engine_offer.py` initially re-declared the model/effort tuples. The helper now imports the
canonical vocabulary via `fleet_commons_shim.load("tier_palette")`, and the focused vocabulary guard
passes.

## Files Modified

- `.claude-plugin/marketplace.json`
- `.gitignore`
- `docs/engineering-journal/DECISIONS.md`
- `docs/plans/2026-07-09-issue-451-engine-offer-helper-plan.md`
- `docs/reviews/2026-07-09-issue-451-engine-offer-helper-plan-review.md`
- `docs/work-sessions/2026-07-09-issue-451-engine-offer-helper.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/saga/scripts/engine_offer.py`
- `plugins/saga/skills/brainstorm/SKILL.md`
- `plugins/saga/skills/code-review/SKILL.md`
- `plugins/saga/skills/doc-review/SKILL.md`
- `plugins/saga/skills/ideate/SKILL.md`
- `plugins/saga/skills/work/SKILL.md`
- `tests/test_engine_offer.py`
- `tests/test_saga_plugin.py`

## Checks

- `uv run pytest tests/test_engine_offer.py tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -q`
- `uv run pytest tests/test_engine_offer.py tests/test_saga_plugin.py tests/test_tier_resolver.py tests/test_saga_engine_resolver.py tests/test_chaperone_economics.py -q`
- `uv run pytest tests/test_engine_offer.py tests/test_tier_vocab_single_source.py::test_no_bare_model_literals_outside_module tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -q`
- `COVERAGE_FILE=/tmp/cov-451-full uv run pytest -q --ignore=tests/test_redis_channel_channel.py --ignore=tests/test_redis_channel_notifier.py` (2614 passed, 1 skipped)
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
- `uv run bandit plugins/saga/scripts/engine_offer.py`
- `uv run python scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python marketplace/validator/validate.py` (passed with existing recommended-field warnings)
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `git diff --check`

## Residual Risk

No known functional blockers. The helper is advisory-only and does not dispatch engines or satisfy gates.
The main remaining risk is prompt ergonomics in the five markdown-driven stage skills, which is bounded
by drift guards and can be refined in later stage-specific work.

## Next Step

Run the pre-PR code-review gate and open the PR if clean.
