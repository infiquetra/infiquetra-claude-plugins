# Issue #389 Provider Auth Preflight Code Review

## Verdict

Review clean: no unresolved P0/P1 findings block PR preparation.

| Field | Value |
| --- | --- |
| Target | Working tree diff for `work/389-provider-auth-preflight` |
| Reviewed revision | Working tree over `59add5e` |
| Linked issue | `https://github.com/infiquetra/infiquetra-claude-plugins/issues/389` |
| Plan | `docs/plans/2026-07-09-issue-389-provider-auth-preflight-plan.md` |
| Work session | `docs/work-sessions/2026-07-09-issue-389-provider-auth-preflight.md` |
| Blocked status | Not blocked |
| Finding priorities and statuses | No unresolved P0/P1/P2/P3 findings |
| Next route | PR prep, then CI/merge loop |

## Scope Check

CLEAN.

Intent: implement registry-authored provider credential preflight for issue #389.

Delivered: normalized row auth schema, registry-driven CLI preflight, row-aware memoization, migrated
codex/agy registry rows, focused tests, and saga release surfaces.

## Plan Completion

COMPLETION: 5/5 DONE, 0 PARTIAL, 0 NOT-DONE, 0 CHANGED, 0 UNVERIFIABLE.

| Unit | State | Evidence |
| --- | --- | --- |
| U1 Registry Auth Schema | DONE | `EngineEntry.auth` and auth mode validation are in `plugins/saga/scripts/engine_registry.py:174`; shipped-row auth assertions are in `tests/test_saga_engine_registry.py:424`. |
| U2 Registry-Driven Preflight | DONE | `preflight()` now accepts row auth probes and row-aware cache keys in `plugins/saga/scripts/engine_resolver.py:91`; same-engine row cache regression is covered in `tests/test_saga_engine_resolver.py:645`. |
| U3 Redaction And Halt/Fallback Behavior | DONE | Env and secret-ref redaction assertions are in `tests/test_saga_engine_resolver.py:541` and `tests/test_saga_engine_resolver.py:565`; fallback/halt behavior is covered in `tests/test_saga_engine_resolver.py:600`. |
| U4 Registry Migration | DONE | Codex and agy rows now declare `invocation.cli` plus file-backed auth in `plugins/saga/references/engine-registry.yaml:30`, `:67`, `:101`, and `:138`. |
| U5 Release Surfaces And Traceability | DONE | Saga metadata is bumped in `plugins/saga/.claude-plugin/plugin.json:3`, marketplace mirrors it in `.claude-plugin/marketplace.json:86`, and changelog notes #389 in `plugins/saga/CHANGELOG.md:3`. |

## Findings

No findings remain after review.

| Priority | Status | Finding | Route |
| --- | --- | --- | --- |
| P0 | None | No P0 findings. | None |
| P1 | None | No unresolved P1 findings. | None |
| P2 | None | No P2 findings. | None |
| P3 | None | No P3 findings. | None |

## Review Notes

The review used correctness, security, testing, maintainability/conventions, and adversarial lenses.

One issue was caught and fixed before this final verdict: HTTP transport rows are now constrained to
`auth.mode: bearer` because `engine_bridge_http.py` only consumes bearer auth today. Non-bearer auth
modes remain available to CLI rows, where preflight is the only consumer.

## Coverage

Suppressed findings: 0.

Checks passed:

- `uv run pytest tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -q`
- `uv run ruff check plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py tests/test_saga_plugin.py`
- `uv run ruff format --check plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py tests/test_saga_plugin.py`
- `uv run mypy plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py --ignore-missing-imports`
- `uv run bandit -r plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python scripts/check_release_surface_parity.py`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `git diff --check`

Residual risk: `uv run pytest -q` is blocked during collection by pre-existing redis-channel tests that
import missing package `mcp` (`tests/test_redis_channel_channel.py` and
`tests/test_redis_channel_notifier.py`). Targeted saga tests and release-surface gates pass.
