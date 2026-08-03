---
title: Work skill overwrites the orchestration_ref it later reads to locate the spec
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: medium
mode: actionable
handoff_maturity: requirements-ready
---

# Work skill overwrites the orchestration_ref it later reads to locate the spec

### Objective
Stop the `/work` skill from overwriting the saga field it later reads, by giving the workflow run
handle its own field instead of overloading `orchestration_ref`.

### Intent
`plugins/saga/skills/work/SKILL.md` uses `orchestration_ref` for two incompatible purposes.

At line 290 it **reads** the field to locate the canonical spec JSON, then passes that value as a
path to three scripts (lines 301, 302, 304: `spec_table.py`, `execution_spec.py emit`,
`execution_spec.py lease`). After launch, line 395 **writes** the field again with
`--orchestration-ref <workflow-id>`.

The two values are not interchangeable. One is a path to a file on disk; the other is a workflow run
identifier. Whichever was written last wins, and the launch step always runs after the read step, so
a saga that has launched has lost its spec path.

The failure is quiet rather than loud. The resume halt at lines 402 and 410 tests only that the
field is **present** and non-empty. A resumed saga carrying a run id therefore clears the halt — the
guard that exists precisely to catch a missing ref reports it as satisfied — and then hands a
workflow id to a script expecting a filename.

Measured on this machine's `.claude/saga/state.json` at the time of filing: 93 sagas, 15 holding a
run-id-shaped ref, 7 holding a spec path, 71 empty. So the field is already predominantly the wrong
kind of value for the read at line 290.

Worked around once by hand: the #686 session left the spec path in place and recorded the workflow
handle in `--notes` instead, a stated divergence from the skill's literal instruction.

### Out-of-scope / non-goals
- Do not migrate or rewrite the 15 sagas already holding run-id refs. Backfill is a separate call.
- Do not change how the workflow backend is selected or launched.
- Do not remove the resume halt; make it discriminate rather than delete it.

### Files expected to change
- `plugins/saga/skills/work/SKILL.md`
- `plugins/saga/scripts/saga.py` (new field plus argument)
- `plugins/saga/references/` schema documentation for the saga envelope
- `tests/` coverage for the saga envelope schema
- `plugins/saga/CHANGELOG.md`, `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`

### Tests to add or update
- A schema test that a saga can hold a spec path and a run handle simultaneously without either
  clobbering the other.
- A test that the resume guard halts when the spec path is absent **even if** a run handle is
  present — this is the case that currently passes and should not.
- A test that a run-id-shaped value in the spec-path field is rejected or flagged rather than
  silently accepted.

### Context library links
- `plugins/saga/skills/work/SKILL.md` lines 290, 301-304, 390-395, 402, 410
- `docs/work-sessions/2026-08-03-verify-panel-severity-axis.md`

### Acceptance criteria
- [ ] A saga tick can record a spec path and a workflow run handle at the same time, and reading either
   back returns what was written.
- [ ] `grep -c 'orchestration-ref <workflow-id>' plugins/saga/skills/work/SKILL.md` returns 0.
- [ ] A test proves the resume guard halts on a missing spec path when a run handle is present.
- [ ] Reverting the guard change in a scratch copy makes that test fail (mutation proof).
- [ ] `uv run python -m pytest -q` exits 0.

### Verification
```bash
uv run python -m pytest tests/ -q -k saga
uv run python -m pytest -q
grep -n 'orchestration_ref' plugins/saga/skills/work/SKILL.md
uv run python scripts/check_release_surface_parity.py
```

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/69f09efc-465e-4e84-9258-fcca4901722b/scratchpad/cards/03-orchestration-ref-overloaded.md
- Source type: local-file
- Source title: 03-orchestration-ref-overloaded

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/693
- Number: 693
- Created at: 2026-08-03T19:54:42.241412+00:00

