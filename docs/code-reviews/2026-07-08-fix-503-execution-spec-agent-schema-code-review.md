---
date: 2026-07-08
kind: code-review
target: working-tree diff against origin/main
reviewed_revision: working tree at 075b26709468768cb973d0435b7f556b826de936
blocked: false
linked_issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/503
plan: docs/plans/2026-07-08-fix-503-execution-spec-agent-schema-plan.md
work_session: docs/work-sessions/2026-07-08-fix-503-execution-spec-agent-schema.md
---

# Code Review - Execution Spec Agent Schema

## Verdict

Clean. No P0/P1 findings.

## Scope Check

Intent: force structured output at generation time for `execution_spec` unit calls with
declared `returns`, while preserving `__gate` and cheap-tier pull-cord behavior.

Delivered: `_agent_opts()` now appends a return-key-derived schema for every returned unit call,
including external-engine dispatches and retry re-emits; tests cover the representative emission
sites; saga release surfaces are bumped to `0.75.3`.

Scope Check: CLEAN.

## Plan Completion

| Unit | Status | Evidence |
|---|---|---|
| U1 Schema helper | DONE | `_return_schema()` builds the normal required-key object schema and cheap-tier `oneOf` pull-cord alternative. |
| U2 Agent options | DONE | `_agent_opts()` appends `schema:` after normal or external-engine options whenever `unit.returns` is non-empty. |
| U3 Tests | DONE | `tests/test_saga_execution_spec.py` covers normal, external-engine, parallel, iterate-to-consensus, unattended retry, and cheap pull-cord cases. |
| U4 Release surfaces | DONE | `plugins/saga/.claude-plugin/plugin.json`, marketplace metadata, changelog, and plugin parity test all move to `0.75.3`. |

## Findings

| # | Priority | File | Issue | Status |
|---|---|---|---|---|
| - | - | - | No findings. | Clean |

## Review Notes

- Correctness: schema emission is single-sourced through `_agent_opts()`, the shared helper used
  by singleton, thunk, consensus, external-engine, and retry paths. The external-engine early
  return was removed, so selector-based units no longer bypass schema emission.
- Compatibility: `__gate` remains intact and the prompt return contract is unchanged. Cheap-tier
  pull-cord output remains schema-valid through the explicit `oneOf` branch.
- Testing: string-level emitter tests are appropriate here because the bug is emitted workflow
  shape, not runtime JSON Schema validation.
- Residual risk: verifier panel structured output remains intentionally out of scope for #519.

## Checks Reviewed

- `uv run pytest tests/test_saga_execution_spec.py tests/test_workflow_emitter.py tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -v`
- `uv run pytest`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy plugins/`
- `uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports`
- `uv run python scripts/validate_plugins.py`
- `uv run python marketplace/validator/validate.py`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python scripts/check_release_surface_parity.py`
- `uv run python -m pytest tests/test_changelog_heading_lint.py -k fleet_baseline -v`
- `uv run python tools/release_surface_diff_guard.py --base-ref origin/main`
- `uv run python -m bandit plugins/saga/scripts/execution_spec.py -ll -f json -o /tmp/bandit-503-execution-spec.json`
- `git diff --check`

## Gate

PR-ready. No unresolved P0/P1 findings and no stale code change after this review pass.
