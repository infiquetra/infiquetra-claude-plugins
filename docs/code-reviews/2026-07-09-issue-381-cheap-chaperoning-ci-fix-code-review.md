# Issue #381 Cheap Chaperoning CI Fix Code Review

## Review Result

- Target: CI-fix working-tree diff on PR #538 after commit `6e90753fb7c3c99b04edc5d82a625bc14778f876`
- Base: `origin/main` merge base `109a4269e371119134d0be4b17f108a6458544a2`
- Plan: `docs/plans/2026-07-09-issue-381-cheap-chaperoning-plan.md`
- Work session: `docs/work-sessions/2026-07-09-issue-381-cheap-chaperoning.md`
- Blocked: no
- P0 findings: 0
- P1 findings: 0
- P2 findings: 0
- P3 findings: 0

## Built Vs Planned

- U6 release surfaces: DONE. Saga description now validates under the manifest limit, marketplace is synced from plugin manifests, and fleet-core is patch-bumped because #381 changed non-doc fleet-core tier-policy/rendering files.
- CI remediation: DONE. Ruff formatting, CI-scope mypy, plugin validation, release parity, and broad tests now pass locally for the patched surface.

Scope check: CLEAN. The follow-up diff is limited to CI remediation for the already-reviewed #381 implementation.

## Review Lenses

- Correctness: checked typed test changes preserve the dynamic module behavior while satisfying mypy.
- Security: no new trust boundary, credential, network, or input-handling surface introduced.
- Testing: CI-scope mypy now covers the previously missed test errors; focused and broad pytest passes were rerun.
- Maintainability/conventions: plugin manifest, marketplace, changelog, and formatting surfaces are aligned with repo release rules.

No conditional deploy, reliability, API-contract, or performance lens was selected; this diff does not touch those domains.

## Findings

No findings.

## Evidence

- `uv run ruff check .` passed.
- `uv run ruff format --check .` passed.
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` passed.
- `uv run pytest -q tests/test_chaperone_economics.py tests/test_saga_engine_resolver.py tests/test_team_execution_plugin.py` passed: 47 tests.
- `uv run pytest -q --ignore=tests/test_redis_channel_channel.py --ignore=tests/test_redis_channel_notifier.py` passed: 2591 passed, 1 skipped.
- `uv run python scripts/validate_plugins.py` passed.
- `uv run python marketplace/validator/validate.py` passed.
- `uv run python scripts/sync_marketplace.py --check` passed.
- `uv run python scripts/check_release_surface_parity.py` passed.
- `git diff --check` passed.

## Residual Risk

- `python3 tools/release_surface_diff_guard.py --base-ref origin/main` must be rerun after the CI-fix commit because the guard intentionally reads committed diff only.
