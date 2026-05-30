# SDLC Manager Alignment Checkpoint

## Goal

Document whether `plugins/sdlc-manager` matches the current `infiquetra-sdlc`
operating model and decide whether to continue with a docs/prompt alignment pass.

## Current Phase

Implementation complete in the working tree. Awaiting user decision on commit/PR handling.

## Completed

- Compared the vendored plugin schema with `../infiquetra-sdlc/config/sdlc-schema.json`.
- Ran `uv run python plugins/sdlc-manager/scripts/sync_template_docs.py --check`.
- Ran `uv run pytest plugins/sdlc-manager/tests -q` with 93 passing tests.
- Identified prompt/reference drift in:
  - `plugins/sdlc-manager/skills/sdlc-issues/references/issue-types.md`
  - `plugins/sdlc-manager/agents/sdlc-operator.md`
  - `plugins/sdlc-manager/commands/sdlc-triage.md`
  - `plugins/sdlc-manager/skills/sdlc-labels/SKILL.md`
- Identified release metadata drift:
  - `plugins/sdlc-manager/.claude-plugin/plugin.json` remains `1.4.0`.
  - `.claude-plugin/marketplace.json` lists `sdlc-manager` as `1.0.0`.
  - current schema/template work remains under `Unreleased`.
- Wrote `docs/ideation/2026-05-30-sdlc-manager-alignment-pass.md`.
- Updated prompt/reference docs to use current Hermes-actionability and label contracts.
- Marked `needs-analysis` / `needs-triage` as legacy auto-label fallback labels, not current
  template defaults.
- Bumped `sdlc-manager` plugin and marketplace metadata to `1.5.0`.
- Added `plugins/sdlc-manager/tests/test_prompt_alignment.py`.
- Moved the SDLC-manager alignment queue item to `ARCHIVE.md` as shipped.

## Next Steps

1. Review the diff.
2. Decide whether to commit these changes from `main` or move them to a branch/worktree first.
3. Separately decide whether `infiquetra-sdlc/config/labels.json` should migrate legacy
   title-pattern auto-label rules from `needs-analysis` / `needs-triage` to `needs-plan`.

## Blockers

None for this repo. Cross-repo label-config migration remains a separate `infiquetra-sdlc`
decision.

## Checks Run

- `uv run python plugins/sdlc-manager/scripts/sync_template_docs.py --check`
- `uv run ruff check plugins/sdlc-manager/tests/test_prompt_alignment.py`
- `uv run pytest plugins/sdlc-manager/tests tests/test_sdlc_manager.py -q`
- `git diff --check`
