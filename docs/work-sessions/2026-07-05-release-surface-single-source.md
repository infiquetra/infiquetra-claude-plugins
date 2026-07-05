# Work session: release-surface single source (#429)

**Plan:** `docs/plans/2026-07-05-release-surface-single-source-plan.md`
**Doc-review:** `docs/reviews/2026-07-05-release-surface-single-source-429-doc-review.md` (not blocked)
**Branch:** `feat/pf-release-surface-429`. **PR:** #475 (draft, opened front-loaded via `ship_ceremony.py start`).

## What was built

- **U1** — `scripts/sync_marketplace.py`: generator + `--check` mode deriving each plugin's
  marketplace entry from `plugin.json` (R1); `license`/`category` are marketplace-owned
  pass-through fields per KTD2 (no `plugin.json` carries either); entry order preserved per KTD3.
  6 tests, all passing.
- **U2** — `scripts/changelog_heading_lint.py`: enforces KTD1's canonical grammar (`# Changelog`
  title, `## [X.Y.Z] - YYYY-MM-DD` version headings, optional `## [Unreleased]`). 3 tests.
- **U3** — reformatted `deploy`, `saga`, `team-execution`, `mission-control` CHANGELOGs to the
  canonical grammar, each with a matching patch version bump (`0.1.2→0.1.3`, `0.54.0→0.54.1`,
  `2.9.0→2.9.1`, `2.5.0→2.5.1`) and a new heading documenting the reformat; regenerated
  `marketplace.json` from the now-current `plugin.json` set.
- **U4** — `scripts/check_release_surface_parity.py`: tri-lock gate (`plugin.json` ==
  marketplace entry == CHANGELOG top heading), naming exactly the plugin(s) out of parity. 2 tests.
- **U5** — `tools/release_surface_diff_guard.py`: PR-scoped diff-aware bump guard per KTD4
  (`--base-ref`, doc/test path exemptions). 8 tests (incl. runner-injection coverage for
  `changed_files`).
- **U6** — CI wiring: new `release-surfaces` job in `.github/workflows/ci.yml` running the
  generator `--check`, the tri-lock gate, and the heading-lint fleet baseline on every push/PR,
  plus the diff-aware guard as a PR-only step (needs `github.event.pull_request.base.sha`).
  `docs/engineering-journal/LEARNINGS.md` dated entry cross-referencing `{#marketplace-drift}`.

## Real findings during implementation (not anticipated by the plan)

1. **Doc-review self-consistency catch (pre-implementation):** U3 originally added CHANGELOG
   entries to the 4 touched plugins without a matching version bump — which would have broken
   U4's own tri-lock gate on landing. Fixed during `/doc-review` before any code was written.
2. **Live pre-existing drift, not a script bug:** running the generator's `--check` against the
   untouched fleet turned up real independent drift — 6 of 9 plugins' `marketplace.json` keyword
   order had diverged from `plugin.json`'s (e.g. `agy`). This is exactly the drift class the issue
   targets; U3's regeneration resolved it, and `tests/test_agy_plugin.py`'s hardcoded keyword-order
   assertion was updated to assert equality with `plugin.json` directly instead of a second
   hardcoded literal.
3. **A 5th non-canonical CHANGELOG spot, missed on first pass:** `mission-control/CHANGELOG.md`
   had two more non-conforming headings below the ones the issue itself named (`## 1.6.1 -
   2026-05-31` missing brackets at line 78, `## Unreleased` missing brackets at line 85) —
   invisible without running the lint against the whole file, not just the top.
4. **Five pre-existing drift-guard tests needed their hardcoded version literals updated** to
   match U3's bumps: `test_deploy_plugin.py`, `test_saga_plugin.py`, `test_team_execution_plugin.py`,
   `test_agy_plugin.py` (top-level `tests/`), and `plugins/mission-control/tests/
  test_prompt_alignment.py` (a fifth one living under the plugin's own `tests/` dir, missed on
  the first sweep and caught by running the full `uv run pytest -q` gate before considering the
  work done).

## Checks run

```
uv run pytest -q                                          # 1977 passed
uv run ruff format --check .                               # all formatted
uv run ruff check .                                        # all checks passed
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports  # no issues, 132 files
uv run bandit -r plugins/ scripts/ tests/ -ll -f json       # 0 new medium/high findings
python3 scripts/sync_marketplace.py --check                 # matches
python3 scripts/check_release_surface_parity.py             # all plugins in parity
python3 scripts/changelog_heading_lint.py                    # all conform
python3 tools/release_surface_diff_guard.py --base-ref main  # self-test: all bumped
```

All 10 acceptance criteria from #429 verified individually via their named `pytest -k` filters
plus the combined AC10 baseline command.

## Files modified

`scripts/sync_marketplace.py`, `scripts/changelog_heading_lint.py`,
`scripts/check_release_surface_parity.py`, `tools/release_surface_diff_guard.py`,
`tests/test_sync_marketplace.py`, `tests/test_changelog_heading_lint.py`,
`tests/test_release_surface_parity.py`, `tests/test_release_surface_diff_guard.py`,
`.github/workflows/ci.yml`, `.claude-plugin/marketplace.json`,
`plugins/{deploy,saga,team-execution,mission-control}/CHANGELOG.md`,
`plugins/{deploy,saga,team-execution,mission-control}/.claude-plugin/plugin.json`,
`tests/test_agy_plugin.py`, `tests/test_deploy_plugin.py`, `tests/test_saga_plugin.py`,
`tests/test_team_execution_plugin.py`, `plugins/mission-control/tests/test_prompt_alignment.py`,
`docs/engineering-journal/DECISIONS.md`, `docs/engineering-journal/LEARNINGS.md`,
`docs/plans/2026-07-05-release-surface-single-source-plan.md`,
`docs/reviews/2026-07-05-release-surface-single-source-429-doc-review.md`.

## Next step

Run `/code-review` (programmatic gate) before PR-ready.
