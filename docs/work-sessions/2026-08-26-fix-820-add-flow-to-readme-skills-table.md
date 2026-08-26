# Work session — add flow row to Mission Control README skills table (#820)

**Saga:** `issue-820` · **Plan:** `docs/plans/2026-08-26-improve-claude-plugins-847-run-plan.md` (Unit U17) ·
**Branch:** `orch/orch-2026-08-26-847-847-m6-820` · **Destination:** PR ·
**Backend:** `inline` (operator-approved in run directive)

## Summary of Changes

Added the `flow` row to the "Skill | Activates When..." table in `plugins/mission-control/README.md` with activation text consistent with `plugins/mission-control/skills/flow/SKILL.md`. Added a bijection guard in `tests/test_mission_control.py` asserting exact 1-to-1 correspondence between directory names under `plugins/mission-control/skills/` and README table rows, verifying specific skill names in failure messages and mutation-proving that removing the `flow` row, adding phantom rows, or altering skill directories fails the guard. Bumped Mission Control release surfaces to `2.12.8`.

### 1. Documentation Repairs
- `plugins/mission-control/README.md`:
  - Added `| `flow` | Project field assignment, sub-issue linking, label verification, card validation |` to the `## Skills` table.
- `plugins/mission-control/CHANGELOG.md`:
  - Added new release section `## [2.12.8] - 2026-08-26` describing the fix.

### 2. Release Surfaces Bump (2.12.8)
- `plugins/mission-control/.claude-plugin/plugin.json`: Bumped version to `2.12.8`.
- `.claude-plugin/marketplace.json`: Bumped Mission Control plugin version to `2.12.8`.
- `plugins/mission-control/tests/test_prompt_alignment.py`: Updated version assertion to `2.12.8`.

### 3. Tests & Drift Guards (`tests/test_mission_control.py`)
- Added `TestMissionControlSkillsTableBijectionGuard`:
  - `test_shipped_skills_match_readme_table_bijection`: Verifies exact bijection between `plugins/mission-control/skills/` subdirectories and README table rows.
  - `test_flow_skill_row_present_with_accurate_activation_text`: Verifies `flow` row exists and describes field assignment, sub-issues, labels, and card validation.
  - `test_mutation_proof_removing_flow_row_fails_naming_flow`: Mutation-proves that removing `flow` row fails the guard naming `flow`.
  - `test_mutation_proof_extra_skill_row_fails_naming_extra_skill`: Mutation-proves that adding a phantom skill row fails the guard naming the extra skill.
  - `test_mutation_proof_missing_skill_dir_fails_naming_missing_dir`: Mutation-proves that a missing skill directory fails the guard naming the missing skill.

### 4. Engineering Journal & Verification
- Added learning entry `{#820-skills-table-bijection-guard}` in `docs/engineering-journal/LEARNINGS.md`.
- Verified changelog heading grammar: `uv run python scripts/changelog_heading_lint.py` (exits 0).
- Verified test suite: `uv run pytest tests/test_mission_control.py -q` (47/47 green).
- Verified mission-control test suite: `uv run pytest plugins/mission-control/tests/ -q` (328 passed, 1 xfailed).
- Verified prompt alignment: `uv run pytest plugins/mission-control/tests/test_prompt_alignment.py -q` (13/13 green).
- Verified release surface parity: `uv run python scripts/check_release_surface_parity.py` (clean).
- Verified journal order: `uv run python scripts/lint_journal_order.py` (0 violations).
- Verified git diff hygiene: `git diff --check` (clean).
