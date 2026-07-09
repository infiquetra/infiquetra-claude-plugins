# Issue #382 Consensus Advisory Seat Work Session

## Built

Implemented U1-U4 from `docs/plans/2026-07-09-issue-382-consensus-advisory-seat-plan.md`.

- U1: Added `plugins/team-execution/skills/team-execution/scripts/consensus_advisory.py` with gated-vs-advisory consensus math, advisory absence handling, and key-based convergence rendering.
- U2: Added `AdvisoryEvidence.role_kind` and `satisfy_gate()` refusal for `advisory-reviewer` and `panel` evidence.
- U3: Updated Team Execution consensus, reviewer registry, and external-engine chaperone references to document the non-scoring advisory seat and convergence report.
- U4: Bumped Team Execution to `2.14.0`, synced marketplace metadata, updated changelog, and recorded the decision in the engineering journal.

## Key Decisions

The implementation keeps the advisory seat executable but local: a helper models the consensus math without adding a Team Execution runtime service.

Gate enforcement lives at the Saga evidence boundary. `advisory-reviewer` evidence is rejected before verification/corroboration checks can make it look gate-capable.

## Checks Run

- `COVERAGE_FILE=/tmp/cov-382-focused-postformat uv run pytest tests/test_team_execution_consensus_advisory.py tests/test_team_execution_consensus.py tests/test_team_execution_plugin.py tests/test_saga_engine_dispatch.py -q` — passed, 73 tests.
- `COVERAGE_FILE=/tmp/cov-382-advisory-status uv run pytest tests/test_team_execution_consensus_advisory.py -q` — passed, 5 tests after code-review robustness fix.
- `COVERAGE_FILE=/tmp/cov-382-full-final uv run pytest -q --ignore=tests/test_redis_channel_channel.py --ignore=tests/test_redis_channel_notifier.py` — passed, 2601 passed, 1 skipped.
- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed.
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — passed.
- `uv run python scripts/validate_plugins.py` — exited 0; printed existing "No plugin files found" warning.
- `uv run python marketplace/validator/validate.py` — passed with existing recommended-field warnings.
- `uv run python scripts/sync_marketplace.py --check` — passed.
- `uv run python scripts/check_release_surface_parity.py` — passed.
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main` — passed.
- `git diff --check` — passed.
- `uv run bandit plugins/team-execution/skills/team-execution/scripts/consensus_advisory.py plugins/saga/scripts/engine_dispatch.py` — passed.

## Residual Risk

Full `uv run bandit -r plugins/` is not clean in this repo because of existing findings outside the changed files. Scoped Bandit over the changed Python files found no issues.

The broad pytest run used the established Redis-channel ignores because those local tests are known to be environment-sensitive in this repo.

## Next Step

Run the pre-PR code-review gate, then commit, push, open PR, monitor CI, merge, and advance #382 through board/outcome closeout.
