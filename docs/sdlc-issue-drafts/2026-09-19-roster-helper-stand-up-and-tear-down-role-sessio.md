---
title: Roster helper: stand up and tear down role sessions in herdr
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

# Roster helper: stand up and tear down role sessions in herdr

### Objective

`saga roster up` reads the run record's staffing plan and creates one named herdr pane per role through agent-launcher's `go` (or `agent-herdr crew` for a whole workspace), prompts each role from the roles library, waits with `herdr agent wait` or an `events.subscribe` stream, and reads results with `herdr agent read`; `saga roster down` closes only what it created. The coordinator must run inside a herdr pane.

### Intent

The hand-written coordinator prompt in agent-operations does this by instruction today; the live roster shows 26 agent panes across seven kinds with role-shaped titles. Herdr's socket API exposes pane creation, agent start, prompt, wait, read, and event subscriptions, and agent-launcher already knows eight agent kinds with model, provider, permissions, working directory, and machine (SR R13; card 891's bounded wait lands here).

### Out-of-scope / non-goals

- No worktree creation (A7's driver does that per unit).
- No closing of panes the helper did not create.
- No control of a herdr session from outside a herdr pane.

### Files expected to change

- `plugins/agent-launcher/skills/agent-launcher/scripts/roster.py` (new)
- `plugins/agent-launcher/skills/agent-launcher/SKILL.md`
- `plugins/saga/skills/work/SKILL.md`, `plugins/saga/skills/code-review/SKILL.md` (call the helper)
- release surfaces

### Tests to add or update

- `tests/test_roster.py` with a fake herdr command runner: one pane per role with the staffing plan's kind and model; prompts come from the roles library; a blocked agent is reported, not answered; `down` removes only recorded panes; a wait uses the settled-state defaults and a caller timeout.

### Context library links

- coding_standards: _none_

General references:
- `herdr-live-evidence.md` in the inputs folder; the herdr socket API and plugin docs (v0.9.1); SR R13; agent-operations `docs/operations/single-issue-delivery.md`

### Acceptance criteria

- [ ] `uv run python plugins/agent-launcher/skills/agent-launcher/scripts/roster.py up --record <path> --dry-run` prints the panes, kinds, models, and prompts it would create.
- [ ] Inside a herdr pane, `roster.py up` for a two-role plan creates two named panes visible in `herdr agent list`, and `roster.py down` removes exactly those two.
- [ ] `uv run pytest tests/test_roster.py -q` passes.

### Verification

```bash
test "${HERDR_ENV:-}" = 1 && uv run python plugins/agent-launcher/skills/agent-launcher/scripts/roster.py up --record <path> --dry-run
herdr agent list | jq '.result.agents | length'
uv run pytest tests/test_roster.py -q
```

### Risk

medium

it creates and closes terminal panes on the operator's server; the guards are the record of what it created and the rule never to close anything else.

### Handoff maturity
requirements-ready

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1024
- Number: 1024
- Created at: 2026-09-19T14:44:18.467486+00:00

