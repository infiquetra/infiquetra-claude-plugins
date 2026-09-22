---
title: Mission-control: triage suggestions, risk pre-fill, objective and status suggestions, override logging, and auto-labels
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

# Mission-control: triage suggestions, risk pre-fill, objective and status suggestions, override logging, and auto-labels

### Objective

`issue prepare` shows a suggested issue type with its full distribution (using the repository's issue-type policy as state, which lifted the probe from 17 to 19 of 30), a suggested Risk tier, and suggested Objective and board Status, each accepted or overridden by the operator with the override logged; `labels` suggests content labels as a widen-only union over the existing rules. Nothing auto-applies.

### Intent

TR R14 and R15; the issue-type probe's ceiling is label noise in the training set, which is why the distribution is shown rather than a single answer.

### Out-of-scope / non-goals

- No auto-apply of any suggestion.
- No change to the card validator.

### Files expected to change

- `plugins/mission-control/scripts/sdlc_manager.py` (prepare path), `plugins/mission-control/skills/labels/` (union)
- release surfaces

### Tests to add or update

- With a fake client: the prepare draft carries the suggestions and the operator's choice; the labels union never removes a rule-derived label; a client failure leaves the draft unchanged with a note.

### Context library links

- coding_standards: _none_

General references:
- TR R14, R15, section 2 (the triage probe); `plugins/mission-control/skills/issues/references/issue-types.md`

### Acceptance criteria

- [ ] `python3 plugins/mission-control/scripts/sdlc_manager.py issue prepare --repo infiquetra-claude-plugins --type defect --title t --from <file> --suggest` writes a draft whose sidecar carries `type_suggestion` with a distribution and `risk_suggestion`.
- [ ] `uv run pytest tests/test_mission_control_suggest.py -q` passes.

### Verification

```bash
uv run pytest tests/test_mission_control_suggest.py -q
```

### Risk

low

suggestions in a draft the operator already reviews before creation.

### Handoff maturity
requirements-ready

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1035
- Number: 1035
- Created at: 2026-09-19T14:50:03.301607+00:00

