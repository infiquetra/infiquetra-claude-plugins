---
title: Widen-only unions: `parse_issue` flags and the journal nudge
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

# Widen-only unions: `parse_issue` flags and the journal nudge

### Objective

Two regex-floored judgments where the model can only add, never remove: `parse_issue.py`'s flags (destructive, credentials, production, and the other approval-boundary categories) gain a noul per category over the issue body, unioned with the regex result; the journal-nudge hook gains a noul "does this commit deserve a learning or decision entry" unioned with the feat/fix rule, still advisory on stderr. The orchestrate review-detection and delegation-audit targets from the original list are dropped with the machinery they targeted.

### Intent

TR R7 and R8; the widen-only rule is the community's and the vendor's own guidance for pattern floors.

### Out-of-scope / non-goals

- No narrowing of any regex result.
- No blocking behavior in the hook.

### Files expected to change

- `plugins/saga/scripts/parse_issue.py`, `plugins/saga/hooks/journal_nudge_hook.py`
- release surfaces

### Tests to add or update

- With a fake client: a flag set by regex stays set whatever the model says; a flag the model raises is added and logged; the hook exits 0 in every case.

### Context library links

- coding_standards: _none_

General references:
- TR R7, R8; SDLC/docs/process/operator-escalations.md (the seven categories)

### Acceptance criteria

- [ ] `uv run python plugins/saga/scripts/parse_issue.py --issue <N> --flags` prints each category with its regex result, the model's probability, and the union.
- [ ] `uv run pytest tests/test_parse_issue_flags.py tests/test_journal_nudge.py -q` passes.

### Verification

```bash
uv run python plugins/saga/scripts/parse_issue.py --issue <N> --flags
uv run pytest tests/test_parse_issue_flags.py tests/test_journal_nudge.py -q
```

### Risk

low

widen-only by construction.

### Handoff maturity
requirements-ready

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1036
- Number: 1036
- Created at: 2026-09-19T14:50:31.687580+00:00

