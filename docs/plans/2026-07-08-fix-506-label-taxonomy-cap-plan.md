---
title: Fix label taxonomy caps and missing issue-type labels — issue #506
type: fix
status: active
date: 2026-07-08
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/506
---

# Fix Label Taxonomy Caps And Missing Issue-Type Labels — Issue #506

## Summary

`labels deploy` reads the canonical taxonomy from `infiquetra-sdlc/config/labels.json`. That file
contains six descriptions longer than GitHub's 100-character label-description cap and omits the
`objective` and `research` labels required by mission-control's issue taxonomy.

This is a cross-repo fix:

- `infiquetra-sdlc`: fix the canonical taxonomy and add a CI guard for label description length and
  required issue-taxonomy labels.
- `infiquetra-claude-plugins`: add a mission-control deploy-time taxonomy validator so future bad
  config fails clearly before any GitHub label mutation, plus lifecycle artifacts and release
  surfaces.

## Requirements

R1. The six overlong descriptions in `infiquetra-sdlc/config/labels.json` must be shortened to
100 characters or fewer without changing label names or broad semantics.

R2. The taxonomy must include `objective` and `research` labels.

R3. The taxonomy's issue-type category must include `objective`.

R4. CI in `infiquetra-sdlc` must fail if any label description exceeds 100 characters or if labels
referenced by mission-control issue types are missing.

R5. `mission-control labels deploy` must validate the loaded taxonomy before calling GitHub and
return a clear per-label error when the taxonomy is invalid.

R6. Mission-control release surfaces must be updated because `labels deploy` behavior changes.

R7. The Operations board card must not be closed until both the canonical taxonomy PR and the
mission-control validator PR are merged.

## Key Technical Decisions

**KTD1: Fix the source of truth in `infiquetra-sdlc`.** The plugin reads that config live; patching
only mission-control would leave every consumer of the canonical taxonomy broken.

**KTD2: Add a local fail-fast guard in mission-control.** The canonical config should be correct,
but `labels deploy` should not discover cap violations by attempting GitHub mutations one by one.

**KTD3: Keep semantics stable.** Shorten descriptions and add the two missing labels only. Do not
rewrite taxonomy categories beyond adding `objective` to the issue-type category.

## Implementation Units

### S1. Canonical taxonomy fix (`infiquetra-sdlc`)

Edit `config/labels.json` to:

- shorten `hermes-task`, `hermes-not-actionable`, `needs-plan`, `needs-author-action`,
  `hermes/approve`, and `hermes/close`,
- add `objective`,
- add `research`,
- include `objective` in `label_categories.issue_type`.

### S2. Canonical taxonomy guard (`infiquetra-sdlc`)

Add a lightweight pytest under `tools/docs/tests/` that asserts:

- every label has a unique name,
- every label description is at most 100 characters,
- required issue-taxonomy labels exist: `capability`, `enhancement`, `defect`, `objective`,
  `exploration`, `context-update`, `hermes-task`, `hermes-not-actionable`, `needs-plan`, and
  `research`,
- category entries resolve to real labels.

### M1. Deploy-time validation (`infiquetra-claude-plugins`)

Add mission-control helper validation for loaded label definitions and call it at the start of
`labels_deploy`. Invalid config reports every violation before exiting non-zero and before any
`gh label create` call.

### M2. Mission-control tests and release surfaces

Add tests for valid taxonomy and overlong-description preflight. Bump mission-control metadata,
changelog, marketplace registry, and metadata drift guard.

## Scope Boundaries

Out of scope: changing taxonomy names beyond adding `objective` and `research`, deploying to a live
fresh test repo from local development, or rewriting legacy `auto_label_rules`.

## Verification

`infiquetra-sdlc`:

- `python3 -m pytest tools/docs/tests/test_labels_config.py -v`
- `python3 -c "import json; d=json.load(open('config/labels.json')); bad=[l for l in d['labels'] if len(l.get('description',''))>100]; print(bad or 'OK')"`

`infiquetra-claude-plugins`:

- `uv run pytest plugins/mission-control/tests/test_prompt_alignment.py::test_sdlc_manager_metadata_and_marketplace_entry_match -v`
- `uv run pytest plugins/mission-control/tests/test_mission_control.py -k "label" -v`
- `uv run python -m ruff check plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_mission_control.py plugins/mission-control/tests/test_prompt_alignment.py`
- `uv run python -m ruff format --check plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_mission_control.py plugins/mission-control/tests/test_prompt_alignment.py`
- `uv run python -m mypy plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_mission_control.py plugins/mission-control/tests/test_prompt_alignment.py --ignore-missing-imports`
- `python3 scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
