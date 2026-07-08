# Work session — bulk flow set-field (#507)

- **Date:** 2026-07-08
- **Issue:** #507 — `defect(flow): set-field lacks bulk mode, batch field syncs blow timeouts`
- **Plan:** `docs/plans/2026-07-08-fix-507-flow-set-field-bulk-plan.md`
- **Doc-review:** `docs/reviews/2026-07-08-fix-507-flow-set-field-bulk-plan-doc-review.md`
- **Code-review:** `docs/code-reviews/2026-07-08-fix-507-flow-set-field-bulk-code-review.md`
- **Backend:** inline autonomous defect loop.

## What Shipped

`flow set-field` now supports bulk project-field updates in one CLI invocation.

- Added `--numbers <n1,n2,...>` as a mutually exclusive alternative to `--number`.
- Allowed repeated `--field/--option` pairs so operators can set multiple fields across the same
  issue set in one invocation.
- Added a shared multi-field resolver that performs one project-field discovery query for the
  invocation.
- Added a project-item index that performs one project-item fetch for the invocation.
- Added bulk result reporting with `updated` and `failed` entries. Missing items and mutation
  failures are reported per issue/field, remaining updates continue, and the command exits non-zero
  after output if anything failed.
- Preserved the existing single-card `--number --field --option` helper path.
- Updated the flow skill documentation and mission-control release surfaces to `2.6.2`.

## Finding Resolved Mid-Build

The first plan draft only added `--numbers`, which would reduce two fields on 19 issues to two CLI
invocations. The issue acceptance criteria requires a single invocation for two fields across many
issues, so the plan and implementation were expanded to support repeated `--field/--option` pairs.

## Gates

- `uv run pytest plugins/mission-control/tests/test_flow_subcommands.py -k "set_field or set_fields or numbers or mismatched" -v`
- `uv run pytest plugins/mission-control/tests/test_prompt_alignment.py::test_sdlc_manager_metadata_and_marketplace_entry_match -v`
- `uv run python -m ruff check plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_flow_subcommands.py plugins/mission-control/tests/test_prompt_alignment.py`
- `uv run python -m ruff format --check plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_flow_subcommands.py plugins/mission-control/tests/test_prompt_alignment.py`
- `uv run python -m mypy plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_flow_subcommands.py plugins/mission-control/tests/test_prompt_alignment.py --ignore-missing-imports`
- `python3 scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `git diff --check`

## Residual Risk

Live GitHub mutation was not run locally because the command updates real project fields. Unit tests
prove the call counts, parser route, partial-failure continuation, and result shape without mutating
the board.
