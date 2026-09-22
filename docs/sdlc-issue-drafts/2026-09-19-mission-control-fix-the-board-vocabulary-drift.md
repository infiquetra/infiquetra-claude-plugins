---
title: Mission-control: fix the board vocabulary drift
repo: infiquetra-claude-plugins
type: enhancement
team: asgard
project: operations
status: Ready for Planning
stage: Shaping
labels: enhancement, needs-plan
risk: low
mode: execute
handoff_maturity: requirements-ready
---

# Mission-control: fix the board vocabulary drift

### Objective

Regenerate `plugins/mission-control/config/board-schema.json` from the live boards and correct the Operations and Asgard section of the board reference, so that every consumer sees the sdlc stage-flow vocabulary (Capturing, Discovering, Ready for Planning, Implementing, Ready to merge, Closeout, Ready to close, and the rest) and the CAMPPS Stage field.

### Intent

The cached schema was last touched 2026-07-14, before two migrations; it carries the retired six-value status set for Operations and Asgard and no Stage field for CAMPPS. The board reference admits its own staleness for two of three boards. The automatic board moves in A11 read this schema (SR section 2.4, R18).

### Out-of-scope / non-goals

- No change to `sdlc-schema.json`, which is current.
- No change to which moves saga may submit.

### Files expected to change

- `plugins/mission-control/config/board-schema.json`
- `plugins/mission-control/skills/board/references/kanban-workflow.md`
- `plugins/mission-control/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/mission-control/CHANGELOG.md`

### Tests to add or update

A drift-guard test that fails when `board-schema.json` disagrees with the live project field options for the three boards (run under a recorded fixture in CI, live under an opt-in flag).

### Context library links

- coding_standards: _none_

General references:
- SR section 2.4; `research-plugin-census.md` section 11 in the inputs folder

### Acceptance criteria

- [ ] `jq -r '.boards.operations.fields.Status.options[].name' plugins/mission-control/config/board-schema.json` lists the stage-flow statuses and none of `Idea, Ready, Active, Done`.
- [ ] `jq -r '.boards.campps.fields | keys[]' plugins/mission-control/config/board-schema.json` includes `Stage`.
- [ ] `grep -n "retired" plugins/mission-control/skills/board/references/kanban-workflow.md` returns nothing.
- [ ] `uv run pytest tests/test_board_schema_drift.py -q` passes.

### Verification

```bash
jq -r '.boards.operations.fields.Status.options[].name' plugins/mission-control/config/board-schema.json
uv run pytest tests/test_board_schema_drift.py -q
```

### Risk

low

a cached file and a reference document; the live board is the source and is unchanged.

### Handoff maturity
requirements-ready

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1020
- Number: 1020
- Created at: 2026-09-19T14:41:02.590446+00:00

