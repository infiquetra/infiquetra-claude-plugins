# Work session — repo argument normalization (#505)

- **Date:** 2026-07-08
- **Issue:** #505 — `defect(sdlc-manager): org double-prepended when --repo is passed as org/repo`
- **Plan:** `docs/plans/2026-07-08-fix-505-repo-normalization-plan.md`
- **Doc-review:** `docs/reviews/2026-07-08-fix-505-repo-normalization-plan-doc-review.md`
- **Code-review:** `docs/code-reviews/2026-07-08-fix-505-repo-normalization-code-review.md`
- **Backend:** inline autonomous defect loop.

## What Shipped

Mission-control repository CLI arguments now accept either bare repo names or
`infiquetra/<repo>` owner-qualified names without double-prepending the org in downstream REST and
GraphQL calls.

- Added a shared argparse boundary helper, `_normalize_repo_arg`, that preserves bare repo names,
  strips the matching Infiquetra owner, rejects malformed owner-qualified values, and rejects
  foreign owners before any network call can run.
- Wired the helper into all repository-valued mission-control CLI flags: `--repo`, `--parent-repo`,
  and `--child-repo`.
- Added tests for direct helper behavior, parser-level label audit dispatch, and cross-repo
  `flow link-sub-issue` dispatch.
- Updated the mission-control metadata drift guard to expect the new `2.6.1` release version after
  CI caught the stale hardcoded value.
- Updated mission-control release surfaces: plugin metadata `2.6.1`, changelog, and marketplace
  registry.

## Gates

- `uv run pytest plugins/mission-control/tests/test_flow_subcommands.py -k "repo_arg or link_sub_issue_normalizes" -v`
- `uv run pytest plugins/mission-control/tests/test_flow_subcommands.py -k "repo_arg or link_sub_issue_normalizes or field_options or set_field" -v`
- `uv run python -m ruff check plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_flow_subcommands.py`
- `uv run python -m ruff format --check plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_flow_subcommands.py`
- `uv run python -m mypy plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_flow_subcommands.py --ignore-missing-imports`
- `python3 scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `python3 plugins/mission-control/scripts/sdlc_manager.py labels audit --repo infiquetra/infiquetra-claude-plugins`
- `python3 plugins/mission-control/scripts/sdlc_manager.py labels audit --repo infiquetra-claude-plugins`
- `git diff --check`
- CI follow-up: `uv run pytest plugins/mission-control/tests/test_prompt_alignment.py::test_sdlc_manager_metadata_and_marketplace_entry_match -v`

## Residual Risk

The live acceptance check covered the labels audit path with both repo input forms. Other command
families share the same argparse normalization boundary and have parser-level regression coverage
for the sub-issue cross-repo path.
