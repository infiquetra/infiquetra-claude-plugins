---
title: Plan continues into plan review
repo: infiquetra-claude-plugins
type: enhancement
team: asgard
project: operations
status: Ready for Planning
stage: Shaping
labels: enhancement, needs-plan
risk: medium
mode: execute
handoff_maturity: requirements-ready
---

# Plan continues into plan review

### Objective

`/plan` ends by dispatching `/doc-review` to the Plan Reviewer (a roster pane when one exists, else the same session in review-only mode), repairing, and looping until no P0 or P1 finding remains or the operator overrides with a word; the loop is the repair protocol. The Workflow-backend and team-execution-emission prose leave `/plan` and `/work` (relocated to a reference file per card 808), with `execution_spec.py`, `team_emitter.py`, and the spec table removed.

### Intent

Today `/plan` recommends `/doc-review` and stops; `/work` asks whether to run it and blocks on P0 or P1 unless overridden. The document-review floor gate stays blocking (decided 2026-09-19, question 4) but runs by itself. The Workflow backend occupies 44.9 percent of `/plan`'s instructions for a path used in 0 of 137 saved plans (SR R3). Cards 931, 932, 934 re-parent here unchanged; 933 is rewritten as a child; 920 closes as superseded.

### Out-of-scope / non-goals

- No change to the review rubric's content or severities.
- No automatic override: the operator's word is the only way past an unresolved P0 or P1.

### Files expected to change

- `plugins/saga/skills/plan/SKILL.md`, `plugins/saga/skills/doc-review/SKILL.md`, `plugins/saga/skills/work/SKILL.md`
- `plugins/saga/references/workflow-backend.md` (new home of the relocated prose)
- `plugins/saga/scripts/execution_spec.py`, `team_emitter.py`, `spec_table.py` (removed)
- release surfaces

### Tests to add or update

- The plan skill's instructions contain no Workflow or team-execution backend section and reference the relocated file.
- The rubric command resolves from any working directory and fails loud when a rubric is missing (card 932).
- A plan with an unresolved P0 finding stops with the finding named and a one-word override path (card 933).

### Context library links

- coding_standards: _none_

General references:
- SR R3, section 8 cluster C; SDLC/docs/reviewers/plan-review.md; `saga-plan-evidence-package.md` and `saga-document-review-evidence-package.md` in agent-operations

### Acceptance criteria

- [ ] `grep -c -i "workflow backend" plugins/saga/skills/plan/SKILL.md` prints 0 and `test -f plugins/saga/references/workflow-backend.md`.
- [ ] `test ! -f plugins/saga/scripts/execution_spec.py`
- [ ] `uv run pytest tests/test_doc_review*.py tests/test_plan*.py -q` passes.
- [ ] A real `/plan issue <N>` run ends in a plan-review pass or a named P0/P1 without the operator typing `/doc-review`.

### Verification

```bash
grep -c -i "workflow backend" plugins/saga/skills/plan/SKILL.md
uv run pytest tests/test_doc_review*.py tests/test_plan*.py -q
```

### Risk

medium

it changes the entry of every run; the floor gate's blocking behavior is preserved and tested.

### Handoff maturity
requirements-ready

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1026
- Number: 1026
- Created at: 2026-09-19T14:45:17.402446+00:00

