---
title: Mission-control: retire the Mount Olympus status vocabulary and the stale --status help string
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
labels: defect, needs-plan
risk: low
stage: Shaping
handoff_maturity: requirements-ready
---

# Mission-control: retire the Mount Olympus status vocabulary and the stale --status help string

### Objective
Remove the retired Mount Olympus board vocabulary (`Assigned`, `In Review`, `Needs Question`)
from mission-control's agent-facing prose, and correct the `--status` CLI help string in
`sdlc_manager.py` so an agent whose Status write was just rejected is not handed three more
rejected values.

### Intent
Carried from the issue 1020 code review
(`docs/code-reviews/2026-09-19-issue-1020-board-vocabulary-code-review.md`, round three, "The two
P2 findings, recorded and not repaired", findings P2-A and P2-B) as a P2 residual outside that
card's scope. Neither is a defect issue 1020 introduced, and both concern a different retired
vocabulary from the board-stage migration names issue 1020's prose guard covers.

Three mission-control prose files still present the retired Mount Olympus board vocabulary as
current: `plugins/mission-control/skills/milestones/SKILL.md:122` names `Assigned` and
`In Review` as states to watch; `:123`, `plugins/mission-control/skills/metrics/SKILL.md:145`,
and `plugins/mission-control/skills/metrics/references/metrics-targets.md:96` present
`Needs Question` as a live state; and `metrics-targets.md:111` instructs an agent to write it.
Separately, `plugins/mission-control/scripts/sdlc_manager.py:7313` reads
`help="Target status (e.g. 'Assigned', 'In Review', 'Active')"`, which argparse prints on a
parse error — so an agent whose Status was just rejected is handed three more rejected ones.

None of these six names is a Status on any live board, and `LIVE_LEGACY_STATUS_ALIASES`
(`plugins/mission-control/scripts/sdlc_manager.py:297`) has no key for any of them, so no
migration hint fires. The prose guard issue 1020 added cannot see them: it sweeps `*.md`
instruction surfaces for the six names the board-stage migration renamed plus `Done`, not the
older Mount Olympus set, and it does not sweep argparse help strings in the Python sources at all.

### Out-of-scope / non-goals
- No change to the board-stage migration prose guard issue 1020 added
  (`tests/test_board_schema_drift.py`), beyond widening its file/name coverage as described below.
- No change to the `board wip` help text (`plugins/mission-control/scripts/sdlc_manager.py:7320`),
  which is a distinct, pre-existing "Show WIP counts and limits" claim flagged in the same review
  paragraph (P2-B) but not part of this card's scope.
- No change to `plugins/mission-control/config/board-schema.json` itself; the committed census is
  the source of truth this card conforms the help string to, not a target of the fix.

### Files expected to change
- `plugins/mission-control/skills/milestones/SKILL.md`
- `plugins/mission-control/skills/metrics/SKILL.md`
- `plugins/mission-control/skills/metrics/references/metrics-targets.md`
- `plugins/mission-control/scripts/sdlc_manager.py`

### Tests to add or update
Extend `tests/test_board_schema_drift.py`'s retired-name coverage (the set the prose guard scans
for) to include the Mount Olympus names `Assigned`, `In Review`, and `Needs Question`, and add a
case that fails when the `--status` help string in `sdlc_manager.py` names an example status
absent from the committed board census (`plugins/mission-control/config/board-schema.json`).

### Context library links
_none_

### Acceptance criteria
- [ ] `grep -nE "Assigned|In Review|Needs Question" plugins/mission-control/skills/milestones/SKILL.md plugins/mission-control/skills/metrics/SKILL.md plugins/mission-control/skills/metrics/references/metrics-targets.md` returns zero matches (empty output).
- [ ] `grep -n 'help="Target status' plugins/mission-control/scripts/sdlc_manager.py` shows an example list containing only status names present in `jq -r '.boards.operations.fields[] | select(.name=="Status") | .options[].name' plugins/mission-control/config/board-schema.json`.
- [ ] `uv run pytest tests/test_board_schema_drift.py -q` passes.

### Verification
```bash
grep -nE "Assigned|In Review|Needs Question" \
  plugins/mission-control/skills/milestones/SKILL.md \
  plugins/mission-control/skills/metrics/SKILL.md \
  plugins/mission-control/skills/metrics/references/metrics-targets.md
grep -n 'help="Target status' plugins/mission-control/scripts/sdlc_manager.py
jq -r '.boards.operations.fields[] | select(.name=="Status") | .options[].name' plugins/mission-control/config/board-schema.json
uv run pytest tests/test_board_schema_drift.py -q
```

### Risk
low

Prose and one argparse help string only; no schema, API, or automatic-board-move behavior
changes. The fix only narrows text that already fails at runtime — every option it removes is
already rejected by every live board — so it cannot turn a previously accepted write into a
rejected one.

### Handoff maturity
requirements-ready

### Suggested next action
/plan docs/analysis/_filing-seeds/card1-status-vocab.md

### Source context
- Source: docs/analysis/_filing-seeds/card1-status-vocab.md
- Source type: local-file
- Source title: Mission-control: retire the Mount Olympus status vocabulary and the stale --status help string

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1042
- Number: 1042
- Created at: 2026-09-19T19:22:43.591785+00:00

