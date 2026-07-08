# Work session — label taxonomy cap and required labels (#506)

- **Date:** 2026-07-08
- **Issue:** #506 — `defect(labels): 6 taxonomy label descriptions exceed GitHub 100-char cap; objective/research labels missing`
- **Plan:** `docs/plans/2026-07-08-fix-506-label-taxonomy-cap-plan.md`
- **Doc-review:** `docs/reviews/2026-07-08-fix-506-label-taxonomy-cap-plan-doc-review.md`
- **Code-review:** `docs/code-reviews/2026-07-08-fix-506-label-taxonomy-cap-code-review.md`
- **Backend:** inline autonomous defect loop.

## What Shipped

This was a cross-repo fix.

`infiquetra-sdlc` PR #52 merged first:

- Shortened six canonical label descriptions to GitHub's 100-character cap.
- Added missing `objective` and `research` labels.
- Added `objective` to `label_categories.issue_type`.
- Added `tools/docs/tests/test_labels_config.py` to guard unique label names, description length,
  required issue-taxonomy labels, and category references.

Mission-control now protects the deploy path:

- Added `_validate_label_taxonomy` before `labels_deploy` calls `gh label create`.
- Validation reports all overlong descriptions, duplicate/missing names, missing colors, empty
  taxonomy, and missing labels required by mission-control issue types.
- Added tests proving valid taxonomy passes, overlong descriptions are reported, `objective` and
  `research` absence is reported, and `labels_deploy` does not call GitHub when taxonomy preflight
  fails.
- Updated mission-control release surfaces to `2.6.3`.

## Gates

`infiquetra-sdlc`:

- `python3 -m pytest tools/docs/tests/test_labels_config.py -v`
- `python3 -c "import json; d=json.load(open('config/labels.json')); bad=[l for l in d['labels'] if len(l.get('description',''))>100]; print(bad or 'OK')"`
- PR #52 CI: passed and merged.

`infiquetra-claude-plugins`:

- `uv run pytest tests/test_mission_control.py -k "label_taxonomy or labels_deploy_validates" -v`
- `uv run pytest plugins/mission-control/tests/test_prompt_alignment.py::test_sdlc_manager_metadata_and_marketplace_entry_match -v`
- `uv run python -m ruff check plugins/mission-control/scripts/sdlc_manager.py tests/test_mission_control.py plugins/mission-control/tests/test_prompt_alignment.py`
- `uv run python -m ruff format --check plugins/mission-control/scripts/sdlc_manager.py tests/test_mission_control.py plugins/mission-control/tests/test_prompt_alignment.py`
- `uv run python -m mypy plugins/mission-control/scripts/sdlc_manager.py tests/test_mission_control.py plugins/mission-control/tests/test_prompt_alignment.py --ignore-missing-imports`
- `python3 scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `python3 plugins/mission-control/scripts/sdlc_manager.py labels audit --repo infiquetra-claude-plugins`
- `git diff --check`

## Residual Risk

Live `labels deploy` against a fresh repository was not run locally because it mutates real GitHub
labels. The known failure mechanism is covered by the merged canonical config test, mission-control
preflight tests, and a live non-mutating audit that now reports 56 required labels with no missing
labels in this repo.
