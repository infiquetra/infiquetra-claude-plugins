---
date: 2026-07-09
kind: work-session
issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/389
plan: docs/plans/2026-07-09-issue-389-provider-auth-preflight-plan.md
status: complete
---

# Work Session - Provider Auth Preflight

## Built

- U1: Added `AUTH_MODES` and normalized `EngineEntry.auth` validation for `files`, `env`, `bearer`,
  and `secret-ref` credential probes.
- U2: Reworked resolver preflight to read row-authored `invocation.cli` and `entry.auth`, while
  preserving the legacy no-entry `config_exists` seam.
- U3: Kept credential probes redaction-safe: result payloads name only env keys, file paths, or secret
  refs, never credential values.
- U4: Migrated codex and agy registry rows to declare `invocation.cli` plus file-backed auth probes.
- U5: Bumped saga release metadata to `0.75.5`, synced marketplace metadata, and updated the changelog
  and metadata parity test.

## Review Fixes Applied

- Replaced the old `RunMemo` `engine_id`-only preflight cache with row-aware keys when an `EngineEntry`
  is supplied, with regression coverage for two variants sharing an engine id but using different auth.
- Tightened registry validation so CLI rows that declare auth must also declare `invocation.cli`; legacy
  fixture rows without auth still load for backward compatibility.
- Kept HTTP transport rows bearer-only because `engine_bridge_http.py` only consumes bearer auth today;
  `env` and `secret-ref` probe modes are available to CLI rows until the bridge grows a secret resolver.
- Replaced an existing `assert` in the touched resolver path with an explicit `RegistryError` so Bandit
  passes without suppression.

## Modified Files

- `.claude-plugin/marketplace.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/saga/references/engine-registry.yaml`
- `plugins/saga/scripts/engine_registry.py`
- `plugins/saga/scripts/engine_resolver.py`
- `tests/test_saga_engine_registry.py`
- `tests/test_saga_engine_resolver.py`
- `tests/test_saga_plugin.py`

## CI Follow-up

- PR #537 CI failed `Tests (Python 3.12)` because the dispatch memoization tests monkeypatched
  `_cli_preflight` with the old keyword-only helper shape after resolver preflight gained row-auth
  seams (`file_exists`, `env_get`, `secret_ref_resolves`, `entry`).
- Updated the local test helpers in `tests/test_saga_engine_dispatch.py` to accept future private
  `_cli_preflight` keyword additions while keeping the call-count assertion scoped to `engine_id`.

## Checks

- `uv run pytest tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -q` - 57 passed.
- `uv run ruff check plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py tests/test_saga_plugin.py` - passed.
- `uv run ruff format --check plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py tests/test_saga_plugin.py` - passed.
- `uv run mypy plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py --ignore-missing-imports` - passed.
- `uv run bandit -r plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py` - passed.
- `uv run python scripts/sync_marketplace.py --check` - passed.
- `uv run python scripts/check_release_surface_parity.py` - passed.
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main` - passed.
- `git diff --check` - clean.
- `uv run pytest -q` - blocked during collection by existing redis-channel tests importing missing
  package `mcp` (`tests/test_redis_channel_channel.py`, `tests/test_redis_channel_notifier.py`).

## Next Step

Run `/code-review`, then commit implementation changes, open the PR, monitor CI, merge, close #389,
and harvest the outcome leaf.
