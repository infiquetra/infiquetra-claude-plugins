---
date: 2026-07-08
kind: work-session
issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/503
plan: docs/plans/2026-07-08-fix-503-execution-spec-agent-schema-plan.md
status: complete
---

# Work Session - Execution Spec Agent Schema

## Built

- U1/U2: Added `_return_schema()` and wired `_agent_opts()` to emit `schema:` for every
  unit with declared `returns`, including external-engine dispatch units.
- U3: Added regression coverage for ordinary unit calls, external-engine calls, parallel
  thunks, iterate-to-consensus loops, unattended climb retries, and cheap-tier pull-cord
  schemas.
- U4: Bumped saga release metadata to `0.75.3`, regenerated marketplace metadata, and
  added the changelog entry.
- Extra type hygiene: made the dynamic `to_spend()` return type explicit with `cast(int, ...)`
  so the focused mypy gate for the touched module is clean.

## Decisions

- Kept `__gate` unchanged as the backstop for legacy malformed output, missing return keys,
  target reconciliation, and pull-cord collection.
- Preserved cheap-tier pull-cord behavior with a `oneOf` schema alternative instead of making
  cheap agents always satisfy the normal return-key object.
- Did not add schema to verifier panel calls; that is the separate #519 defect.

## Modified Files

- `.claude-plugin/marketplace.json`
- `docs/engineering-journal/LEARNINGS.md`
- `docs/plans/2026-07-08-fix-503-execution-spec-agent-schema-plan.md`
- `docs/reviews/2026-07-08-fix-503-execution-spec-agent-schema-plan-doc-review.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/saga/scripts/execution_spec.py`
- `tests/test_saga_execution_spec.py`
- `tests/test_saga_plugin.py`

## Checks Run

- `uv run pytest tests/test_saga_execution_spec.py tests/test_workflow_emitter.py tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -v`
  - 169 passed.
- `uv run pytest`
  - 2625 passed, 1 skipped.
- `uv run ruff check .`
  - passed.
- `uv run ruff format --check .`
  - 263 files already formatted.
- `uv run mypy plugins/`
  - passed, 39 source files.
- `uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  - passed, 162 source files.
- `uv run python scripts/validate_plugins.py`
  - passed with no errors.
- `uv run python marketplace/validator/validate.py`
  - passed, 10 plugins valid, 49 existing recommended-field warnings.
- `uv run python scripts/sync_marketplace.py --check`
  - marketplace matches plugin metadata.
- `uv run python scripts/check_release_surface_parity.py`
  - all plugins in parity.
- `uv run python -m pytest tests/test_changelog_heading_lint.py -k fleet_baseline -v`
  - 1 passed, 2 deselected; coverage emitted the expected no-data warning for this docs-only test.
- `uv run python tools/release_surface_diff_guard.py --base-ref origin/main`
  - all changed plugins bumped their release surfaces.
- `uv run python -m bandit plugins/saga/scripts/execution_spec.py -ll -f json -o /tmp/bandit-503-execution-spec.json`
  - passed.
- `uv run python -m bandit -r plugins/ scripts/ tests/ -ll -f json -o /tmp/bandit-503.json`
  - exited 1 on pre-existing medium/high findings outside this diff; CI treats this job as
    advisory with `|| true`.
- `git diff --check`
  - clean.

## Next Step

Run the pre-PR code-review gate, commit, open the PR for #503, and monitor CI.
