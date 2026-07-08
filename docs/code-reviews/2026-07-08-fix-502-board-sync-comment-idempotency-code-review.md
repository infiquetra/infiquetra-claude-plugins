# Code-review — Board-sync comment idempotency (#502)

- **Scope:** `fix/502-board-sync-comment-idempotency` vs `origin/main`.
- **Mode:** inline code-review gate after `/work`.
- **Verdict:** PASS — no remaining P0/P1/P2 findings. PR-ready.

## Remaining Findings

| Priority | Finding | Status |
|---|---|---|
| P0 | None. | Clean. |
| P1 | None. | Clean. |
| P2 | None. | Clean. |

## Fixed During Review

| Priority | Finding | Fix |
|---|---|---|
| P1 | The initial `gh api` preflight used `-F per_page=100` without `--method GET`, which makes GitHub CLI issue a POST and fail with a 422 missing `body`. | Added explicit `--method GET` and verified the live command returns JSON type `array`. |

## Lenses Applied

| Lens | Result |
|---|---|
| Built-vs-planned audit | PASS — comment payloads get a ledger-key-derived marker, the production writer checks for it before posting, and non-comment ops keep existing behavior. |
| Crash-window replay | PASS — unit coverage simulates remote marker present with missing local ledger and confirms no duplicate POST plus ledger restoration. |
| GitHub command correctness | PASS — live `gh api --method GET ... comments --paginate -F per_page=100 --jq type` returns `array`. |
| Release surface parity | PASS — saga metadata, changelog, marketplace registry, and metadata test are updated to `0.75.1`. |
| Type and style | PASS — ruff, format-check, and mypy are clean. |

## Gates Reviewed

- `uv run pytest tests/test_board_progression.py tests/test_outcome_board_sync.py tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -v`
- `uv run python -m ruff check plugins/saga/scripts/board_progression.py plugins/saga/scripts/outcome_board_sync.py tests/test_board_progression.py tests/test_outcome_board_sync.py tests/test_saga_plugin.py`
- `uv run python -m ruff format --check plugins/saga/scripts/board_progression.py plugins/saga/scripts/outcome_board_sync.py tests/test_board_progression.py tests/test_outcome_board_sync.py tests/test_saga_plugin.py`
- `uv run python -m mypy plugins/saga/scripts/board_progression.py plugins/saga/scripts/outcome_board_sync.py tests/test_board_progression.py tests/test_outcome_board_sync.py --ignore-missing-imports`
- `python3 scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `gh api --method GET repos/infiquetra/infiquetra-claude-plugins/issues/502/comments --paginate -F per_page=100 --jq type`
- `git diff --check`

## Residual Risk

No blocking residual risk. This fix does not remove historical duplicate comments and does not
expand `outcome_reconcile` to scan comment history.
