# Work session — #818 U15 Replace six version-pinned installed paths in Mission Control

**Date:** 2026-08-26
**Issue:** infiquetra/infiquetra-claude-plugins#818
**Plan:** `docs/plans/2026-08-26-improve-claude-plugins-847-run-plan.md` unit U15
**Branch:** `orch/orch-2026-08-26-847-847-m4-818`
**Backend:** inline (plan frontmatter)
**Role:** review-fixer

## What was built (U15)

1. **Replaced Six Version-Pinned Installed Script Paths:**
   - Rewrote all six sites hardcoding `~/.claude/plugins/cache/infiquetra-plugins/mission-control/2.1.0/scripts/sdlc_manager.py` to the settled repository convention `"$CLAUDE_PLUGIN_ROOT/scripts/sdlc_manager.py"` (no `skills/` segment since Mission Control stores scripts directly under `scripts/`):
     - `plugins/mission-control/README.md:28`
     - `plugins/mission-control/commands/board.md:42`
     - `plugins/mission-control/commands/issue.md:50`
     - `plugins/mission-control/commands/issue.md:59`
     - `plugins/mission-control/commands/metrics.md:40`
     - `plugins/mission-control/commands/triage.md:40`
   - Verified that `plugins/mission-control/agents/sdlc-operator.md` remains unaffected and clean.

2. **Added Installed-Path Drift Guard Test Suite:**
   - Added `TestMissionControlInstalledPathDriftGuard` in `tests/test_mission_control.py` with:
     - `test_no_version_pinned_installed_paths_in_tracked_documents`: fails on any version-pinned `infiquetra-plugins/mission-control/[0-9]` path in tracked Mission Control markdown files.
     - `test_replacement_invocation_form_present_at_all_six_repaired_sites`: confirms that all six sites carry the replacement invocation form and no `skills/` segment.
     - `test_mutation_proof_restored_pinned_path_fails_guard`: mutation-proves that restoring a pinned path fails the guard.
     - `test_sdlc_operator_agent_unaffected`: asserts `plugins/mission-control/agents/sdlc-operator.md` has no version digits and retains its `<version>` placeholder.

3. **Bumped Mission Control Release Surfaces:**
   - Bumped version `2.12.5` -> `2.12.6` in `plugins/mission-control/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
   - Added `[2.12.6] - 2026-08-26` release notes to `plugins/mission-control/CHANGELOG.md`.
   - Updated version metadata test in `plugins/mission-control/tests/test_prompt_alignment.py`.

4. **Engineering Journal Entry:**
   - Appended a dated entry (`## 2026-08-26`) to `docs/engineering-journal/LEARNINGS.md` (`{#818-claude-plugin-root-installed-path-convention}`).

## Key decisions

- Execution backend recorded as `inline` per plan frontmatter.
- Path convention: used `"$CLAUDE_PLUGIN_ROOT/scripts/sdlc_manager.py"` matching settled convention across plugins, avoiding runtime resolver frameworks or doc generators.
- Clean agent surface: `agents/sdlc-operator.md` was left untouched.

## Files modified

- `plugins/mission-control/README.md`
- `plugins/mission-control/commands/board.md`
- `plugins/mission-control/commands/issue.md`
- `plugins/mission-control/commands/metrics.md`
- `plugins/mission-control/commands/triage.md`
- `plugins/mission-control/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/mission-control/CHANGELOG.md`
- `plugins/mission-control/tests/test_prompt_alignment.py`
- `tests/test_mission_control.py`
- `docs/engineering-journal/LEARNINGS.md`
- `docs/work-sessions/2026-08-26-818-stale-installed-paths.md`

## Checks run

- `grep -rn "infiquetra-plugins/mission-control/[0-9]" plugins/mission-control/` — exit 1 (clean, 0 matches)
- `uv run pytest tests/test_mission_control.py -q` — 38 passed
- `uv run pytest plugins/mission-control/tests/ -q` — 328 passed, 1 xfailed
- `uv run python scripts/changelog_heading_lint.py` — passed
- `uv run python tools/release_surface_diff_guard.py` — passed
- `uv run python scripts/lint_journal_order.py` — passed (VIOLATIONS: 0)
- `bash scripts/gate.sh` — passed (GATE GREEN, 25/25 steps ran, 0 blocking failures)
- `git diff --check` — clean

## Next step

Commit, push, and open pull request linked to #818.
