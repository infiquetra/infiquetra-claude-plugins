---
title: Issue #453 Engines Route Explain Work Session
type: work-session
status: complete
date: 2026-07-09
issue: infiquetra/infiquetra-claude-plugins#453
plan: docs/plans/2026-07-09-issue-453-engines-route-explain-plan.md
---

# Issue #453 Engines Route Explain Work Session

## Built

- U1: Added validated repo-local `.saga/engine-overlay.json` state with atomic writes, mutation helpers,
  and gitignore coverage.
- U2: Added shared registry candidate ranking and `explain_capability()` while keeping no-overlay
  `Registry.by_capability()` behavior unchanged.
- U3: Added `engine_registry_cli.py` and `/engines` command documentation for list, pin, deprecate,
  clear, and read-only `route explain`.
- U4: Threaded optional overlay/repo-root support through `engine_resolver.resolve()` with
  overlay-safe capability memo keys.
- U5: Bumped Saga to `0.75.11`, updated marketplace/changelog/package tests, and updated Saga docs
  command coverage for `/engines`.

## Key Decisions

- Overlay state remains explicit and opt-in; no registry or resolver caller reads current working
  directory implicitly.
- Pins validate against the registry before they can affect routing.
- Deprecated rows are filtered before ranking; if all candidates are filtered, resolver worker/generator
  calls fall back through the existing no-fit path.
- `route explain` is read-only and deterministic over registry plus local overlay state.

## Files Modified

- `.gitignore`
- `.claude-plugin/marketplace.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/saga/commands/engines.md`
- `plugins/saga/docs/commands.md`
- `plugins/saga/docs/model/saga-docs-model.yaml`
- `plugins/saga/scripts/engine_overlay.py`
- `plugins/saga/scripts/engine_registry.py`
- `plugins/saga/scripts/engine_registry_cli.py`
- `plugins/saga/scripts/engine_resolver.py`
- `tests/test_engine_overlay.py`
- `tests/test_engine_registry_cli.py`
- `tests/test_saga_docs_coverage.py`
- `tests/test_saga_engine_registry.py`
- `tests/test_saga_engine_resolver.py`
- `tests/test_saga_plugin.py`

## Checks Run

- `uv run pytest tests/test_engine_overlay.py tests/test_engine_registry_cli.py -v`
- `uv run pytest tests/test_saga_engine_registry.py tests/test_saga_engine_resolver.py -k "overlay or explain or deprecate or pin" -v`
- `uv run pytest tests/test_saga_engine_registry.py tests/test_saga_engine_resolver.py -v`
- `uv run pytest tests/test_saga_plugin.py -v`
- `uv run pytest tests/test_saga_docs_coverage.py -q`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python scripts/check_release_surface_parity.py`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
- `git diff --check`
- `COVERAGE_FILE=/tmp/cov-453-full uv run pytest -q --ignore=tests/test_redis_channel_channel.py --ignore=tests/test_redis_channel_notifier.py`

## Result

Implementation complete and locally validated. Next step: run the code-review gate for issue #453.
