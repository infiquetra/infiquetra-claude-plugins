# SDLC Manager Alignment Pass Ideation

**Date:** 2026-05-30

**Focus:** Determine whether `sdlc-manager` matches the current `infiquetra-sdlc`
operating model, and whether to continue with a docs/prompt alignment pass.

**Status:** Implemented in the working tree after pulling `origin/main` to `f5ffbaa`.

## Executive Summary

Yes, continue the docs/prompt alignment pass. This recommendation was implemented in the working
tree after the initial ideation pass.

The core operational update is partially present: the vendored
`config/sdlc-schema.json` matches the current `infiquetra-sdlc` schema, the
generated issue-template reference is in sync, and the `sdlc-manager` test suite
passes locally. The remaining risk is guidance drift. Several operator-facing
prompts, command docs, and reference docs still teach old label behavior or
contradict the current Hermes-actionability model.

There is also release metadata drift. The plugin manifest still says `1.4.0`,
the marketplace entry still says `1.0.0`, and the recent schema/template work is
recorded only under `Unreleased`. If the alignment pass ships, it should include
a plugin version bump, marketplace update, and changelog release section.

Implementation outcome: `sdlc-manager` is now bumped to `1.5.0` in the working tree, prompt and
reference drift has been corrected, and a prompt/reference drift guard has been added.

## Grounding

Local checks performed before this write-up:

- Fetched `infiquetra-claude-plugins` and sibling `infiquetra-sdlc`.
- Confirmed sibling `infiquetra-sdlc` is at `74da244` on `main`.
- Confirmed plugin schema matches canonical schema:
  - `plugins/sdlc-manager/config/sdlc-schema.json`
  - `../infiquetra-sdlc/config/sdlc-schema.json`
- Ran template drift guard:
  - `uv run python plugins/sdlc-manager/scripts/sync_template_docs.py --check`
- Ran plugin tests:
  - `uv run pytest plugins/sdlc-manager/tests -q`
  - Result: 93 passed.
- Checked release metadata:
  - `plugins/sdlc-manager/.claude-plugin/plugin.json` still has `version: 1.4.0`.
  - `.claude-plugin/marketplace.json` still lists `sdlc-manager` as `version: 1.0.0`.
  - `plugins/sdlc-manager/CHANGELOG.md` has current work under `Unreleased`.

## Alignment Status

| Area | Status | Evidence | Action |
|---|---|---|---|
| Vendored board schema | Aligned | Plugin schema matches `infiquetra-sdlc/config/sdlc-schema.json`. | Keep. |
| Template reference generation | Aligned | `sync_template_docs.py --check` passes. | Keep generator and guard test. |
| Board, metrics, rollout references | Mostly aligned | The references are condensed, not verbatim copies. They use current Jeff Intent, Asgard, and Mount Olympus concepts. | Do not regenerate wholesale. Spot-check during prompt pass. |
| Issue type reference | Drifted | `issue-types.md` still says capability/enhancement use `needs-analysis`, defect uses `needs-triage`, and objectives use `objective:*` / `initiative:*` labels. | Rewrite label sections to point at generated template reference and project fields. |
| `sdlc-operator` prompt | Drifted | Early identity section says only capability/enhancement/defect are Hermes-actionable, but later section says exploration/context-update also get `hermes-task`. Output example uses `needs-analysis`. | Fix contradiction and examples. |
| `/sdlc-triage` command | Drifted | Manual label example applies `capability,needs-analysis`; command also says it recommends initiative/objective labels. | Replace with template/current labels and project-field wording. |
| Label auto-label docs | Needs decision | `labels.json` in `infiquetra-sdlc` still contains auto-label fallback rules for `needs-analysis` and `needs-triage`; issue templates now use `needs-plan`. | Distinguish "template defaults" from "legacy/fallback auto-label rules" before changing. |
| Release metadata | Drifted | Manifest stayed `1.4.0`; marketplace entry stayed `1.0.0`; changelog is `Unreleased`. | Include version, marketplace, and changelog release cleanup in the pass. |

## Strongest Ideas

### 1. Make Generated Template Reference the Canonical Label Source

Update handwritten issue-type guidance so it stops duplicating exact template
labels. It should summarize when to use each issue type and link to
`templates-reference.md` for current auto-applied labels and body requirements.

Why this survives: duplication already drifted. The generated reference has a
checkable sync path; handwritten references should not compete with it.

### 2. Fix the `sdlc-operator` Hermes-Actionability Contract

Make the prompt use one contract everywhere:

- `hermes-task`: capability, enhancement, defect.
- `hermes-not-actionable`: objective, exploration, context-update.
- Initiative and Objective are project fields, not labels.

Why this survives: this is the highest-risk prompt drift. It affects how agents
classify work and whether Hermes should pick up a card.

### 3. Separate Template Labels from Auto-Label Fallback Labels

Do not blindly delete every `needs-analysis` or `needs-triage` reference. The
canonical templates moved to `needs-plan`, but `infiquetra-sdlc/config/labels.json`
still includes title/body auto-label rules that apply older labels. The pass
should either preserve those as legacy fallback behavior or update the canonical
label config in `infiquetra-sdlc` first.

Why this survives: it avoids papering over a real source-of-truth conflict.

### 4. Treat Release Metadata as Part of the Alignment Pass

The schema/template update changed plugin behavior enough to need a release
record. The pass should:

- Move the `Unreleased` changelog entry into a dated release, likely `1.5.0`.
- Bump `plugins/sdlc-manager/.claude-plugin/plugin.json`.
- Update the `sdlc-manager` marketplace entry version and stale description.
- Check installed command examples that hard-code `1.0.0` cache paths.

Why this survives: without this, users can install or reason about the wrong
plugin version even if the docs are corrected.

### 5. Add a Narrow Prompt Drift Guard

Add a small test or script that checks the most expensive stale vocabulary in
operator-facing docs:

- No `objective:*` or `initiative:*` as recommended current labels.
- No claim that exploration/context-update are `hermes-task`.
- No default example applying `needs-analysis` to capability/enhancement.
- No default example applying `needs-triage` to defects unless clearly marked as
  legacy or fallback.

Why this survives: the template docs already have a guard. The remaining drift is
in prompts and human-written references, so a narrow guard is the cheapest way to
stop the same problem recurring.

## Rejected or Deferred Ideas

### Regenerate all SDLC manager references verbatim from `infiquetra-sdlc`

Reject for now. The plugin docs are operationally condensed and agent-oriented;
making them verbatim copies would add noise. The right move is to remove exact
duplicated facts that drift, not remove all local summarization.

### Remove every `needs-analysis` and `needs-triage` mention immediately

Defer until label config intent is clarified. Current issue templates use
`needs-plan`, but auto-label rules in `infiquetra-sdlc` still mention the older
labels. The alignment pass should make that distinction explicit or update the
source config first.

### Treat schema sync as the main remaining problem

Reject. The schema is already aligned. The problem is that prompts and reference
docs still teach stale behavior around labels, project fields, and
Hermes-actionability.

## Recommended Pass

Proceed with a focused docs/prompt alignment pass:

1. Update `sdlc-issues` issue-type guidance to stop duplicating auto-applied
   labels and to point at generated template reference for exact current labels.
2. Fix `sdlc-operator` Hermes-actionability wording and output examples.
3. Fix `/sdlc-triage` command wording and examples around labels and project
   fields.
4. Clarify `sdlc-labels` docs around template labels versus auto-label fallback
   labels.
5. Bump release metadata and marketplace entry if behavior/docs are shipped.
6. Add a narrow stale-vocabulary guard for operator prompts and references.
7. Re-run:
   - `uv run python plugins/sdlc-manager/scripts/sync_template_docs.py --check`
   - `uv run pytest plugins/sdlc-manager/tests -q`
   - `git diff --check`

## Implementation Outcome

Implemented in the current working tree:

- Pulled latest `origin/main` first. The pulled commit already restored the legacy rollout
  WIP-limit fallback in `plugins/sdlc-manager/scripts/sdlc_manager.py`, so this pass did not
  duplicate that runtime fix.
- Updated `sdlc-operator`, `/sdlc-triage`, issue-type docs, label docs, command examples, and
  README cache paths.
- Bumped `plugins/sdlc-manager/.claude-plugin/plugin.json` and the marketplace entry to `1.5.0`.
- Cut the `CHANGELOG.md` `Unreleased` content as `1.5.0`.
- Added `plugins/sdlc-manager/tests/test_prompt_alignment.py`.
- Added journal coverage:
  - `docs/engineering-journal/LEARNINGS.md`
  - `docs/engineering-journal/ARCHIVE.md`
  - `docs/engineering-journal/QUEUED.md`

Validation after implementation:

- `uv run python plugins/sdlc-manager/scripts/sync_template_docs.py --check`
- `uv run ruff check plugins/sdlc-manager/tests/test_prompt_alignment.py`
- `uv run pytest plugins/sdlc-manager/tests tests/test_sdlc_manager.py -q` -> 108 passed
- `git diff --check`

## Follow-Up Questions and Decisions

- Decided for this repo: document `needs-analysis` / `needs-triage` as legacy/fallback labels
  rather than silently changing `infiquetra-sdlc/config/labels.json` from this repository.
- Decided for this repo: release the plugin as `sdlc-manager` `1.5.0`.
- Still open cross-repo follow-up: decide in `infiquetra-sdlc` whether title-pattern auto-label
  rules should migrate from `needs-analysis` / `needs-triage` to `needs-plan`.
