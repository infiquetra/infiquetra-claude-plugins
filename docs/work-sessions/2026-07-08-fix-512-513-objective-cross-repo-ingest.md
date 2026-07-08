# Work session — Cross-repo Objective ingestion (#512/#513)

- **Date:** 2026-07-08
- **Issues:** #512 — duplicate subplot IDs for cross-repo same-number sub-issues; #513 — parent repo stamped onto child issues
- **Plan:** `docs/plans/2026-07-08-fix-512-513-objective-cross-repo-ingest-plan.md`
- **Doc-review:** `docs/reviews/2026-07-08-fix-512-513-objective-cross-repo-ingest-plan-doc-review.md`
- **Code-review:** `docs/code-reviews/2026-07-08-fix-512-513-objective-cross-repo-ingest-code-review.md`
- **Backend:** inline autonomous defect loop.

## What Shipped

`/outcome start --from-objective` now ingests cross-repo Objective sub-issues with correct child
provenance and collision-safe subplot IDs.

- `discover_subissues.py` fetches `repository.nameWithOwner` for sub-issues and tracked issues.
- Normalized sub-issues carry `repo`, and tracked issues carry typed repo/number refs when repo data
  is available.
- `outcome_edges.py` owns the shared subplot ID map, preserving `sub-<number>` for unique numbers and
  repo-qualifying same-number collisions.
- Edge inference resolves typed cross-repo dependencies and drops ambiguous legacy number-only refs
  instead of guessing.
- `nodes_from_objective` stamps each node with the child issue repo and uses the shared ID map.
- Saga release surfaces were updated to `0.75.2`.

## Gates

- `uv run pytest tests/test_outcome_from_objective.py tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -v`
- `uv run pytest tests/test_outcome_from_objective.py tests/test_outcome_command.py tests/test_outcome_board_sync.py tests/test_outcome_reconcile.py -v`
- `uv run python -m ruff check plugins/saga/scripts/discover_subissues.py plugins/saga/scripts/outcome_edges.py plugins/saga/scripts/outcome.py tests/test_outcome_from_objective.py tests/test_saga_plugin.py`
- `uv run python -m ruff format --check plugins/saga/scripts/discover_subissues.py plugins/saga/scripts/outcome_edges.py plugins/saga/scripts/outcome.py tests/test_outcome_from_objective.py tests/test_saga_plugin.py`
- `uv run python -m mypy plugins/saga/scripts/discover_subissues.py plugins/saga/scripts/outcome_edges.py plugins/saga/scripts/outcome.py tests/test_outcome_from_objective.py --ignore-missing-imports`
- `python3 scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `python3 plugins/saga/scripts/outcome.py --repo-root /tmp/outcome-repro-512-513.rWj5PH start collision-check --from-objective infiquetra/campps-context-library#69`
- `python3 plugins/saga/scripts/outcome.py --repo-root /tmp/outcome-repro-512-513.rWj5PH graph collision-check`
- Generated spec readback showed 13 nodes, child repo stamps, and repo-qualified duplicate `#95`
  subplot IDs.
- `git diff --check`

## Residual Risk

Already-started outcome specs keep their existing IDs and GitHub stamps. This fix only changes new
Objective ingestion.
