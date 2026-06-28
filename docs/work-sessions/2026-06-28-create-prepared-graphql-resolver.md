# Issue #280 Create-Prepared GraphQL Resolver Work Session

Date: 2026-06-28
Branch: `fix/create-prepared-graphql-resolver`
Plan: `docs/plans/2026-06-28-create-prepared-partial-graphql-error-plan.md`
Doc review: `docs/reviews/2026-06-28-create-prepared-partial-graphql-error-plan-doc-review.md`
Issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/280

## Summary

Implemented U1-U4 from the issue #280 plan.

- U1/U2: Replaced speculative `issue(number:)` plus `pullRequest(number:)` GraphQL lookups with `issueOrPullRequest(number:)` union resolution in mission-control code and board-query docs.
- U3: Added post-create pending/resume handling for `issue create-prepared` so a failure after GitHub issue creation can retry board-add and Status without creating a duplicate issue.
- U3: Added strict board-add mode for the create-prepared post-create path while preserving normal text-returning CLI behavior.
- U4: Bumped mission-control release surfaces to `2.3.1` across plugin metadata, marketplace metadata, changelog, and drift guard tests.
- Review-found fix: normalized `repository: null` GraphQL read payloads to the existing missing-node path and added the remaining R9 negative tests for null data, empty stdout, and malformed stdout.
- Journal: Added a durable decision noting that GraphQL partial-error tolerance belongs at query-shape boundaries, not in shared `_graphql` strictness.

## Commits

- `5dad734` `docs: add create-prepared defect plan`
- `386f323` `fix(mission-control): resume prepared issue post-create`
- `12a976f` `chore(mission-control): release 2.3.1`
- `022677a` `style(mission-control): format prepared issue flow`
- `5a7bc7e` `docs: record create-prepared work session`
- `134aaf7` `fix(mission-control): handle null GraphQL repository nodes`

## Checks Run

- `uv run pytest plugins/mission-control/tests/test_graphql_issue_resolution.py plugins/mission-control/tests/test_issue_create_prepared.py plugins/mission-control/tests/test_board_add_multi_project.py plugins/mission-control/tests/test_typed_exceptions.py plugins/mission-control/tests/test_prompt_alignment.py tests/test_release_triad.py -q` - passed, 88 tests.
- `uv run pytest` - passed, 1260 tests, after temporarily moving local `.claude/saga/sagas` state out of the repo and restoring it afterward so the suite guard ran against a clean saga path.
- `uv run ruff format --check .` - passed.
- `uv run ruff check .` - passed.
- `uv run mypy plugins/` - passed.
- `python3 -m py_compile plugins/mission-control/scripts/sdlc_manager.py` - passed.
- `git diff --check` - passed.
- `uv run bandit -q -r plugins/mission-control/scripts plugins/mission-control/config plugins/mission-control/skills --severity-level medium -x '*/tests/*'` - passed.

## Residual Risk

- `uv run bandit -q -r plugins/mission-control/scripts plugins/mission-control/config plugins/mission-control/skills -x '*/tests/*'` still reports existing low-severity subprocess / broad-exception patterns in mission-control. The new issue #280 path did not add a new Bandit finding.
- Full-repo `uv run bandit -r plugins/` remains noisy because of pre-existing plugin findings, including vendored `.venv` content under plugin trees.
- Manual dogfood of `issue create-prepared` against a throwaway prepared draft was not run because it would create or mutate GitHub issue/project state. That acceptance check needs explicit confirmation before execution.

## Next Step

Run the code-review gate against `134aaf7`, then open a PR after explicit confirmation if no P0/P1 findings remain.
