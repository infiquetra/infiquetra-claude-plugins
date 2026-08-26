# Work session — delete self-referential compatibility alias clause in Mission Control issue docs (#819)

**Saga:** `issue-819` · **Plan:** `docs/plans/2026-08-26-improve-claude-plugins-847-run-plan.md` (Unit U16) ·
**Branch:** `orch/orch-2026-08-26-847-847-m5-819` · **Destination:** PR ·
**Backend:** `inline` (operator-approved in run directive)

## Summary of Changes

Deleted self-referential compatibility alias clauses in `plugins/mission-control/commands/issue.md` and historical entries in `plugins/mission-control/CHANGELOG.md`. Added focused test assertions ensuring that no sentence names a command as its own compatibility alias, confirming neither repaired sentence carries an alias clause, and asserting that the plugin ships exactly four commands (`board`, `issue`, `metrics`, `triage`). Bumped Mission Control release surfaces to `2.12.7`.

### 1. Documentation Repairs
- `plugins/mission-control/commands/issue.md`:
  - Removed `; `/issue` remains a compatibility alias.` from line 7, leaving `"Create or prepare an SDLC issue in any Infiquetra repository. This is the primary user-facing issue command."`.
- `plugins/mission-control/CHANGELOG.md`:
  - Removed `, with `/issue` retained as a compatibility alias.` from historical `## [Unreleased]` section.
  - Added new release section `## [2.12.7] - 2026-08-26` describing the fix.

### 2. Release Surfaces Bump (2.12.7)
- `plugins/mission-control/.claude-plugin/plugin.json`: Bumped version to `2.12.7`.
- `.claude-plugin/marketplace.json`: Bumped Mission Control plugin version to `2.12.7`.
- `plugins/mission-control/tests/test_prompt_alignment.py`: Updated version assertion to `2.12.7` and added compatibility alias absence check on `commands/issue.md`.

### 3. Tests & Drift Guards (`tests/test_mission_control.py`)
- Added `TestMissionControlSelfReferentialAliasDriftGuard`:
  - `test_no_sentence_names_command_as_own_compatibility_alias`: Verifies across `commands/issue.md` and `CHANGELOG.md` that no sentence names a command as its own compatibility alias.
  - `test_plugin_ships_exactly_four_commands`: Verifies `plugins/mission-control/commands/` contains exactly `board.md`, `issue.md`, `metrics.md`, and `triage.md`, with no legacy `/create-issue` or alias commands.
  - `test_repaired_sentences_contain_no_alias_clauses`: Verifies neither repaired document carries an alias clause.
  - `test_mutation_proof_self_referential_alias_fails_guard`: Mutation proves that inserting a self-referential alias sentence fails the drift guard.

### 4. Engineering Journal & Verification
- Added learning entry `{#819-delete-self-referential-command-alias-clause}` in `docs/engineering-journal/LEARNINGS.md`.
- Verified changelog heading grammar: `uv run python scripts/changelog_heading_lint.py` (exits 0).
- Verified test suite: `uv run pytest tests/test_mission_control.py -q` (42/42 green).
- Verified prompt alignment: `uv run pytest plugins/mission-control/tests/test_prompt_alignment.py -q` (13/13 green).
- Verified release surface parity: `uv run python scripts/check_release_surface_parity.py` (clean).
- Verified journal order: `uv run python scripts/lint_journal_order.py` (0 violations).
- Verified git diff hygiene: `git diff --check` (clean).
