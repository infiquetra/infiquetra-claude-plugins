---
title: Conditional-lens proposal, finding dedupe, and severity flag in the code review
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

# Conditional-lens proposal, finding dedupe, and severity flag in the code review

### Objective

Three advisory judgments inside the roster-based code review (A8): at admission, propose which of the eleven conditional lenses apply from the change shape (one noul per lens; the four always-on lenses are never proposed away, and a proposal can only add lenses to the Planner's declaration, never remove them); across lens results, dedupe findings that describe the same defect (pairwise noul over candidate pairs found by code); flag a finding whose stated severity looks out of line with its text (a score against the catalogue's severity anchors), for a second look. All three log their suggestion and the outcome; none scores a lens.

### Intent

TR R6 (the lens pre-screen) and R11 (the finding cross-check) survive the simplification in this form; the private roster they targeted is gone (filing plan section 2).

### Out-of-scope / non-goals

- No lens scoring, verdict, or threshold by the judgment model.
- No removal of a finding by the dedupe; duplicates are grouped and shown.

### Files expected to change

- `plugins/saga/scripts/review_roster.py` (proposal at declaration time), `plugins/saga/scripts/review_result.py` (dedupe and flag over results)
- `plugins/saga/skills/code-review/SKILL.md`
- release surfaces

### Tests to add or update

- With a fake client: a proposal adds a lens and never removes one; dedupe groups two findings with the same fingerprint and keeps both; a severity flag is attached, not applied.

### Context library links

- coding_standards: _none_

General references:
- TR R6, R11; SDLC/config/lens-catalogue.json (`finding_schema`, `scoring`)

### Acceptance criteria

- [ ] `uv run python plugins/saga/scripts/review_roster.py --declaration <decl.json> --propose` prints the proposed additions with probabilities and leaves the declaration's lenses intact.
- [ ] `uv run pytest tests/test_review_judgments.py -q` passes.

### Verification

```bash
uv run python plugins/saga/scripts/review_roster.py --declaration <decl.json> --propose
uv run pytest tests/test_review_judgments.py -q
```

### Risk

low

additive and advisory inside a review whose verdict is computed by code.

### Handoff maturity
requirements-ready

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1034
- Number: 1034
- Created at: 2026-09-19T14:49:35.670145+00:00

