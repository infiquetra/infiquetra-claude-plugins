---
title: Roles library in the sdlc's role vocabulary
repo: infiquetra-claude-plugins
type: capability
team: asgard
project: operations
status: Ready for Planning
stage: Shaping
labels: capability, needs-plan
risk: low
mode: execute
handoff_maturity: requirements-ready
---

# Roles library in the sdlc's role vocabulary

### Objective

A `roles/` directory (in agent-launcher, which already creates sessions) with one prompt per sdlc role: Planner, Plan Reviewer, Review Controller, Lens Reviewer parameterized by lens, Standard and Expert Repair Implementer, Release Worker, Functional Tester, Investigator, Issue Reviewer, Architect, Product, Delivery Manager. Each prompt states the role, its inputs from the run record, its output contract (the sdlc handoff comment shape), and its stop rule. The 25 team-execution agent prompts and two checklists (2,570 lines) are the source material.

### Intent

Roles already run as named herdr panes across seven agent kinds; what is missing is a reusable prompt per role in the vocabulary the sdlc uses, so a roster can be stood up from a plan instead of a hand-written handoff (SR R12; team-execution's structure is archived in A13).

### Out-of-scope / non-goals

- No spawning, ordering, gating, or aggregation logic; that is the roster helper (A6) and the chain.
- No scanner, validator, or monitor roles: scanners become baseline checks in A10, monitors become wait steps in A11.
- No new role the sdlc does not name.

### Files expected to change

- `plugins/agent-launcher/roles/*.md` (new, one per role; lens reviewers as one template plus per-lens sections keyed to the catalogue ids)
- `plugins/agent-launcher/roles/README.md` (the contract each prompt follows)
- `plugins/team-execution/agents/*.md`, `review-criteria.md`, `validator-criteria.md` (content migrated, files removed in A13)
- `plugins/agent-launcher/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/agent-launcher/CHANGELOG.md`

### Tests to add or update

- `tests/test_roles_library.py`: every sdlc role has a prompt; every prompt names its inputs, output contract, and stop rule; every catalogue lens id has a lens-reviewer section; no prompt references team-execution.

### Context library links

- coding_standards: _none_

General references:
- SDLC/docs/roles/run-roles.md; SDLC/docs/process/run-contracts.md; SDLC/config/lens-catalogue.json; SR R12

### Acceptance criteria

- [ ] `ls plugins/agent-launcher/roles/*.md | wc -l` is at least 14 (thirteen roles plus the README).
- [ ] `grep -L "### Stop rule" plugins/agent-launcher/roles/*.md` prints nothing except the README.
- [ ] `uv run pytest tests/test_roles_library.py -q` passes.

### Verification

```bash
ls plugins/agent-launcher/roles/
uv run pytest tests/test_roles_library.py -q
```

### Risk

low

prompt files with a structural test; no runtime behavior changes until A6 consumes them.

### Handoff maturity
requirements-ready

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1022
- Number: 1022
- Created at: 2026-09-19T14:43:20.162452+00:00

