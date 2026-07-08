# Work session — Board-sync comment idempotency (#502)

- **Date:** 2026-07-08
- **Issue:** #502 — `saga: crash between comment POST and ledger write double-posts board-sync comments; reconcile cannot heal`
- **Plan:** `docs/plans/2026-07-08-fix-502-board-sync-comment-idempotency-plan.md`
- **Doc-review:** `docs/reviews/2026-07-08-fix-502-board-sync-comment-idempotency-plan-doc-review.md`
- **Code-review:** `docs/code-reviews/2026-07-08-fix-502-board-sync-comment-idempotency-code-review.md`
- **Backend:** inline autonomous defect loop.

## What Shipped

Saga board-sync progress comments are now replay-safe across the post-before-ledger crash window.

- Added a deterministic hidden `saga-board-sync-idempotency` marker derived from the same key as the
  board-sync ledger.
- `authorize_and_write` appends that marker to `issue-progress-comment` payloads without mutating
  caller-owned payload dictionaries.
- The production board writer now checks existing issue comments for the marker before posting a
  marked progress comment.
- A replay after a remote comment landed but the local ledger key was lost now skips the duplicate
  POST and records the missing ledger key.
- Updated saga release surfaces to `0.75.1`.

## Gates

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

Existing duplicate comments, if any, are left in place. The fix prevents future duplicates on
crash replay and does not add comment-history reconciliation to `outcome_reconcile`.
