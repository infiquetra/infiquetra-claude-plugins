---
title: Saga simplification: one automatic run per issue, roles as herdr sessions, simple worktree and merge
repo: infiquetra-claude-plugins
type: capability
team: asgard
project: operations
status: Ready for Planning
stage: Shaping
labels: capability, needs-plan
risk: high
mode: execute
handoff_maturity: requirements-ready
---

# Saga simplification: one automatic run per issue, roles as herdr sessions, simple worktree and merge

### Objective

Replace saga's operator-invoked, gate-and-refusal lifecycle with one automatic run per issue in the shape the sdlc defines: admission questions once, then plan, plan review, a build-until-it-works loop, an up-front-lensed mechanical code review, merge turn, release, functional test, close, and retro capture. Roles run as herdr sessions from a roles library; worktree, branch, and merge handling is the simple model orchestrate already implements; eleven commands and the machinery behind them are removed in the same release.

### Intent

The sdlc (the source of truth for the lifecycle) is lighter than the plugins on every axis checked: five gates plus a floor of five, merge turns with no lock service, no global concurrency cap, no machine-validated handoffs, and a run model it marks "not implemented anywhere yet." The operating record shows four saga commands in live use and a hand-written coordinator prompt doing the chaining. Saga is 91,064 lines, 68 percent scripts, and three unused subsystems are 54 percent of that script code. Decisions taken 2026-09-19 (SR section 0): the narrow reading of "working software before review"; orchestrate slimmed, not retired; eleven commands removed in the same release; floor gates stay blocking but automatic; one staffing component in fleet-core; `/qa` kept and redesigned.

### Inputs inventory

- The simplification review (SR), sections 5, 6, 7, and 11 — the decision record this parent and its children implement.
- SDLC/docs/lifecycle/run-model.md, SDLC/docs/process/gates.md, SDLC/docs/process/parent-branch-integration.md — the source-of-truth lifecycle every child must match.
- No dependency on another card in this tree (section 1's table: Depends on = none).

### Out-of-scope / non-goals

- No change to the sdlc's stage and status vocabulary, gate floor, or board-write authority (mission-control stays the only writer).
- No removal of `/qa`, `/retro`, `/strategy`, `/founder-review`, or the five shaping commands.
- No phased rollout: the children ship together as saga 1.0.0 and are judged in use.
- No new lease, reservation, receipt, or ledger mechanism, whatever a child finds.

### Files expected to change

- `plugins/saga/`, `plugins/orchestrate/`, `plugins/agent-launcher/`, `plugins/fleet-core/`, `plugins/team-execution/` (archived), `plugins/mission-control/config/`, `.claude-plugin/marketplace.json`, `tests/`, and the sdlc documents named in A1 — owned by the children; this parent changes no file directly.

### Tests to add or update

Per child. The parent's own check is the release: the gate green at the release commit, both plugin trees at the same version, and one real issue run through the chain end to end.

### Context library links

- architecture_decisions: https://github.com/infiquetra/infiquetra-sdlc/blob/main/docs/adrs/adr-001-code-review-executor-boundary.md
- coding_standards: _none_

General references:
- SR sections 5, 6, 7, and 11
- SDLC/docs/lifecycle/run-model.md, SDLC/docs/process/gates.md, SDLC/docs/process/parent-branch-integration.md

### Acceptance criteria

- [ ] Every child listed in SR section 11 (as filed under this parent) is closed with its pull request merged: `gh api graphql -f query='{repository(owner:"infiquetra",name:"infiquetra-claude-plugins"){issue(number:<A>){subIssues(first:50){nodes{number state}}}}}'` shows every node `CLOSED`.
- [ ] One real issue has been run through `/plan issue <N>` and reached a merged pull request with a non-production deployment and a functional-test record in its run record, without the operator typing any lifecycle command after admission.
- [ ] `ls plugins/saga/commands | wc -l` prints 14 and none of the eleven removed commands exists.
- [ ] `GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh` exits 0 at the release commit, and `jq -r .version plugins/saga/.claude-plugin/plugin.json` prints `1.0.0`.

### Verification

```bash
gh api graphql -f query='{repository(owner:"infiquetra",name:"infiquetra-claude-plugins"){issue(number:<A>){subIssues(first:50){totalCount nodes{number state}}}}}'
ls plugins/saga/commands | wc -l
jq -r .version plugins/saga/.claude-plugin/plugin.json ~/.claude/plugins/marketplaces/infiquetra-plugins/plugins/saga/.claude-plugin/plugin.json ~/.claude-company/plugins/marketplaces/infiquetra-plugins/plugins/saga/.claude-plugin/plugin.json
```

### Failure modes / pre-mortem

Subtraction removes something a recorded collision needed (each of the five recorded collisions is mapped to a line in A7); automatic chaining runs away (bounded by the sdlc's 3 plus 2 cycle allowances and the floor gates); the two plugin trees diverge on install (hand-repair step in the release note); the plugin gets ahead of the sdlc (A1 lands first).

### Stop conditions

Stop and report if a child would need a lock, lease, reservation, or receipt to pass its own tests; if the sdlc amendment in A1 is refused; or if the first real run cannot reach a merged pull request without an operator lifecycle command.

### Risk

high

it removes about 50,000 lines and changes how every issue is delivered; the mitigation is that the removed machinery has no caller in the September record and the chain is used on one real issue before the release is called done.

### Handoff maturity
requirements-ready

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1018
- Number: 1018
- Created at: 2026-09-19T14:39:06.537444+00:00

