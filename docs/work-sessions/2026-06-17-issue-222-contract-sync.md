# Issue #222 Contract Sync Work Session

Date: 2026-06-17

Branch: `work/issue-222-contract-sync`

Plan: `docs/plans/2026-06-17-mission-control-issue-contract-sync-plan.md`

Issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/222

## Summary

Implemented U1-U5 of the issue #222 plan.

- U1: Vendored the current `infiquetra-sdlc origin/main` schema snapshot into mission-control and added a schema-level `issue_fields` drift guard.
- U2/U3: Added context-aware prepared issue validation using the generated required matrix, compiled fallback actionable bodies from generated contract data, and kept `validate_card_body(body)` body-only for compatibility.
- U4/U5: Regenerated issue template guidance from vendored contract data, removed stale `Context library links` optionality, and added a Saga handoff no-template-copy guard.
- Gate repair: Replaced an existing `set.add()` list-comprehension idiom in `board_add` so mission-control mypy passes.

## Commits

- `22557f0` `fix(mission-control): vendor issue fields schema`
- `24a9057` `fix(mission-control): validate prepared issue context`
- `b664ed1` `docs(mission-control): sync issue contract guidance`
- `5ad705f` `fix(mission-control): satisfy board add type check`

## Checks Run

- `uv run pytest plugins/mission-control/tests/test_issue_contract_parity.py -q`
- `uv run pytest plugins/mission-control/tests/test_card_validator.py plugins/mission-control/tests/test_issue_prepare.py plugins/mission-control/tests/test_issue_prepare_compile_approve.py plugins/mission-control/tests/test_issue_create_prepared.py -q`
- `uv run pytest plugins/mission-control/tests/test_template_sync.py plugins/mission-control/tests/test_prompt_alignment.py -q`
- `INFIQUETRA_SDLC_PATH=<clean origin/main export> uv run python plugins/mission-control/scripts/sync_template_docs.py --check`
- `uv run pytest plugins/mission-control/tests/test_issue_contract_parity.py plugins/mission-control/tests/test_card_validator.py plugins/mission-control/tests/test_issue_prepare.py plugins/mission-control/tests/test_issue_prepare_compile_approve.py plugins/mission-control/tests/test_issue_create_prepared.py plugins/mission-control/tests/test_template_sync.py plugins/mission-control/tests/test_prompt_alignment.py -q` — 67 passed.
- `uv run ruff check .`
- `uv run mypy plugins/mission-control`
- `uv run pytest -q -k 'not test_suite_does_not_create_claude_dir_under_repo_root'` — 752 passed, 1 local-state guard deselected.
- `git diff --check origin/main..HEAD`
- `uv run bandit -q -r plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/scripts/sync_template_docs.py` — reported pre-existing low-severity subprocess/exception findings in `sdlc_manager.py`; no new high/medium findings.

## Residual Risk

Full `uv run pytest -q` fails locally only on `tests/test_saga_saga.py::test_suite_does_not_create_claude_dir_under_repo_root` because this lifecycle run intentionally writes real Saga state under `.claude/saga/`. The same suite passes when that local-state guard is deselected, and CI should run in a clean checkout without this local Saga state.

## Next Step

Run the code-review gate, then open the PR if no P0/P1 findings remain.
