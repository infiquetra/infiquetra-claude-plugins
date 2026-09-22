---
title: The tier suggestion inside the staffing component
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

# The tier suggestion inside the staffing component

### Objective

The staffing component (A3) consults `jev tier` for each role or unit at admission, batched per run, with a confidence floor below which the policy default stands, and logs the suggestion, the chosen value, and any override to the verdict log. The suggestion never changes a value on its own.

### Intent

The tier-selection probe scored 10 of 10 on saga's work-shape policy, batched at 388 milliseconds for ten units (TR R5). With `/tier` and the emitters removed, the staffing component is the one place tiers are resolved (SR R29).

### Out-of-scope / non-goals

- No automatic promotion above a band until the harness shows it.
- No change to the policy defaults themselves.

### Files expected to change

- `plugins/fleet-core/scripts/fleet_commons/staffing.py` (calls the client; logs)
- `plugins/saga/scripts/admission.py` (shows the suggestion beside the default)
- release surfaces

### Tests to add or update

- With a fake client: a suggestion above the floor is shown and logged; below the floor the default stands and the log says why; a client failure falls open to the default with a logged reason.

### Context library links

- coding_standards: _none_

General references:
- TR R5, section 2 (the tier probe); SR R29

### Acceptance criteria

- [ ] `uv run python plugins/fleet-core/scripts/fleet_commons/staffing.py resolve --shape judgment --suggest` prints the default, the suggestion, its confidence, and which one applies.
- [ ] `uv run pytest tests/test_staffing_suggest.py -q` passes.
- [ ] The verdict log records one entry per suggested role after a real admission.

### Verification

```bash
uv run python plugins/fleet-core/scripts/fleet_commons/staffing.py resolve --shape judgment --suggest
uv run pytest tests/test_staffing_suggest.py -q
```

### Risk

low

advisory and logged; the default always stands when in doubt.

### Handoff maturity
requirements-ready

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1033
- Number: 1033
- Created at: 2026-09-19T14:49:04.431394+00:00

