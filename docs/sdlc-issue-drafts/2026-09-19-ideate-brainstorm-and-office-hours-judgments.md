---
title: Ideate, brainstorm, and office-hours judgments
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

# Ideate, brainstorm, and office-hours judgments

### Objective

In `/ideate`: pairwise dedupe of generated ideas, axis-coverage choice, a grounding-fit gate, a tactical-scope noul, rubric scores, and a revival check, with the rule that a judgment drops nothing and the critique stays generative. In `/brainstorm`: a scope-tier choice, consequence-factor nouls, question-ordering scores, and a readiness noul batch, with the dialogue untouched. In `/office-hours`: the routing choice among the shaping commands and `/plan`, shown with its distribution. The `/loop` and `/handoff` choices from the original list are dropped with those commands; the verify-panel vote is dropped with the panels.

### Intent

TR R12, R13, and the surviving part of R9; the operator's recorded rule for brainstorm is "add no rigidity without demonstrated value," which is why every judgment here is advisory and none becomes a gate.

### Out-of-scope / non-goals

- No preset number of critique rounds; no assurance levels.
- No saga tick written by these commands (they become stateless in A13's release).

### Files expected to change

- `plugins/saga/skills/ideate/SKILL.md`, `plugins/saga/skills/brainstorm/SKILL.md`, `plugins/saga/skills/office-hours/SKILL.md` and their references
- `plugins/saga/scripts/shaping_judgments.py` (new; batches the questions per state)
- release surfaces

### Tests to add or update

- With a fake client: dedupe groups without dropping; the readiness batch returns one probability per criterion; the office-hours choice shows a distribution and never auto-routes.

### Context library links

- coding_standards: _none_

General references:
- TR R9, R12, R13 and its section 6; `saga-brainstorm-change-candidates.md` in agent-operations

### Acceptance criteria

- [ ] `uv run python plugins/saga/scripts/shaping_judgments.py readiness --doc <brainstorm.md>` prints one probability per readiness criterion.
- [ ] `uv run pytest tests/test_shaping_judgments.py -q` passes.

### Verification

```bash
uv run python plugins/saga/scripts/shaping_judgments.py readiness --doc <brainstorm.md>
uv run pytest tests/test_shaping_judgments.py -q
```

### Risk

low

advisory inside conversational commands.

### Handoff maturity
requirements-ready

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1037
- Number: 1037
- Created at: 2026-09-19T14:51:01.277103+00:00

