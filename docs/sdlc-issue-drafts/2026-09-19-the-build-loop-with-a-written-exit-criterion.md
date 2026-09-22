---
title: The build loop with a written exit criterion
repo: infiquetra-claude-plugins
type: capability
team: asgard
project: operations
status: Ready for Planning
stage: Shaping
labels: capability, needs-plan
risk: medium
mode: execute
handoff_maturity: requirements-ready
---

# The build loop with a written exit criterion

### Objective

`/work` becomes the build loop: one worktree and branch per unit (through A7's driver); implement; run the mechanical baseline from the staffing profile and the sdlc catalogue's check map (for Python: ruff, strict mypy, bandit, pytest with coverage; plus the security and dependency scanners as baseline entries: bandit, pip-audit, gitleaks or detect-secrets, semgrep where configured); run the plan's child-scoped functional checks; deploy to the branch preview where the repository declares one; run the plan's scenario smoke; repeat until green; then hand to code review. The exit criterion is written in the plan at admission. The confirmed-only merge, the ship ceremony, and the risk-gated test prose are removed; the repository's own pre-push gate stays.

### Intent

The narrow reading decided 2026-09-19 (question 1): working software is a fact the worker checks before review, and review stays before merge. Team-execution's scanners become checks, not roles (SR R4).

### Out-of-scope / non-goals

- No deployment to the non-production destination (A11).
- No new gate: a failing check is a loop iteration, not a refusal.

### Files expected to change

- `plugins/saga/skills/work/SKILL.md` (1,121 lines today; the loop replaces the round-N pull-request ceremony)
- `plugins/saga/scripts/build_loop.py` (new: runs the baseline and the plan's checks, records results in the run record)
- `plugins/saga/scripts/ship_ceremony.py`, `ceremony_hazards.py`, `ship_receipt.py`, `ship_teardown.py`, `ship_undo.py` (removed)
- `plugins/saga/references/mechanical-baseline.md` (new)
- release surfaces

### Tests to add or update

- The baseline for a Python repository runs the four tools and records each result in the run record.
- A declared preview deployment is invoked and its result recorded; an undeclared one is skipped with a record entry, never an error.
- The loop exits only when every check and the scenario smoke are green, and hands to code review with the exact revision.

### Context library links

- coding_standards: _none_

General references:
- SDLC/docs/lifecycle/run-model.md (step 5); SDLC/config/lens-catalogue.json (`mechanical_checks`); SR R4, section 5

### Acceptance criteria

- [ ] `uv run python plugins/saga/scripts/build_loop.py --record <path> --dry-run` prints the checks it would run for this repository and whether a preview deployment is declared.
- [ ] `test ! -f plugins/saga/scripts/ship_ceremony.py`
- [ ] `uv run pytest tests/test_build_loop.py -q` passes.
- [ ] A real unit reached code review with a green baseline, its functional checks, and a preview record in the run record.

### Verification

```bash
uv run python plugins/saga/scripts/build_loop.py --record <path> --dry-run
uv run pytest tests/test_build_loop.py -q
```

### Risk

medium

it rewrites the heaviest skill; the repository gate and the code review still stand behind it.

### Handoff maturity
requirements-ready

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1027
- Number: 1027
- Created at: 2026-09-19T14:45:49.959610+00:00

