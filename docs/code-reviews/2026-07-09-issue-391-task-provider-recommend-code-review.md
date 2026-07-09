# Code Review - Issue #391 Task Provider Recommendation

| Field | Value |
| --- | --- |
| Target | Branch diff `work/391-recommend-routing` against `origin/main` |
| Reviewed revision | `0fd0ab279f2a1250fe07940763b666e140d8d80d` |
| Linked issue | `https://github.com/infiquetra/infiquetra-claude-plugins/issues/391` |
| Plan | `docs/plans/2026-07-09-issue-391-task-provider-recommend-plan.md` |
| Doc review | `docs/reviews/2026-07-09-issue-391-task-provider-recommend-plan-review.md` |
| Work session | `docs/work-sessions/2026-07-09-issue-391-task-provider-recommend.md` |
| Blocked status | Not blocked |
| Finding priorities and statuses | No unresolved P0/P1/P2/P3 findings |
| Next route | PR prep, then CI/merge loop |

## Scope Check

Scope Check: CLEAN

Intent: add a read-only task-to-provider recommendation primitive for Saga external engines.

Delivered: added `engine_recommend.py`, explicit registry `egress_policy`, focused tests,
release metadata, changelog, and work-session evidence. The existing resolver/dispatch path remains
unchanged.

## Review Lenses

- correctness: enum/value completeness for `egress_policy`, policy ordering, token-window filtering,
  and malformed task input.
- security: no provider preflight/dispatch side effects; sensitive tasks never receive networked
  alternatives.
- testing: recommendation policies, schema validation, resolver regression, release-surface parity, and
  side-effect sentinel coverage.
- maintainability/conventions: separate recommendation from resolver, release surfaces synchronized,
  repo formatting/type/lint gates.
- adversarial: public task-shape boundary and sensitive/no-egress failure mode.
- agent-native: `recommend()` is an importable agent/lifecycle API and returns the metadata an agent
  needs to explain or choose the next rung.

## Built Vs Planned

| Unit | State | Evidence |
| --- | --- | --- |
| U1 Registry Egress Policy Field | DONE | `plugins/saga/scripts/engine_registry.py` requires `egress_policy`; `plugins/saga/references/engine-registry.yaml` marks all seed rows; `tests/test_saga_engine_registry.py` validates missing, unknown, networked, and local-only values. |
| U2 Advisory Recommendation Module | DONE | `plugins/saga/scripts/engine_recommend.py` returns a ranked `RecommendationResult`; `tests/test_engine_recommend.py` covers cheapest-viable, free-first, metadata, overlay deprecations, malformed input, and resolver side-effect sentinel. |
| U3 Sensitivity Empty-Result Semantics | DONE | `engine_recommend.py` filters `sensitive=True` to `local-only`; `tests/test_engine_recommend.py` proves no-network fallback and halted empty result when no local-only candidate exists. |
| U4 Documentation, Release Surfaces, Saga Trace | DONE | Saga plugin version bumped to `0.75.15` in plugin and marketplace metadata; `plugins/saga/CHANGELOG.md` updated; work-session artifact created. |

COMPLETION: 4/4 DONE, 0 PARTIAL, 0 NOT-DONE, 0 CHANGED, 0 UNVERIFIABLE

## Findings

| Priority | Status |
| --- | --- |
| P0 | None |
| P1 | None |
| P2 | None |
| P3 | None |

## Coverage

Suppressed count: 0.

Checks run:

- `uv run pytest tests/test_engine_recommend.py tests/test_saga_engine_registry.py tests/test_engine_registry_lint.py tests/test_saga_engine_resolver.py tests/test_engine_registry_cli.py tests/test_saga_engine_dispatch.py tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -q`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python scripts/check_release_surface_parity.py`
- `uv run python tools/release_surface_diff_guard.py --base-ref origin/main`
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
- `git diff --check`
- `uv run pytest --ignore=tests/test_redis_channel_channel.py --ignore=tests/test_redis_channel_notifier.py`

Residual risk:

- Full unfiltered `uv run pytest` is locally blocked before collection completes because
  `tests/test_redis_channel_channel.py` and `tests/test_redis_channel_notifier.py` import `mcp`, which is
  not installed in this local environment.
