---
title: TypeSafe Jev integration: typed judgments in the lifecycle
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

# TypeSafe Jev integration: typed judgments in the lifecycle

### Objective

Put TypeSafe's System One model Jev (`jev-1.13.0`, alias `jev-latest`) to work as typed judgments inside the lifecycle: a stdlib client and command-line tool in fleet-core with an evaluation harness and verdict log; then the judgment points that survive the saga simplification: the tier suggestion in the staffing component, the conditional-lens proposal, finding dedupe, and severity flag in code review, triage and labels in mission-control, the widen-only flag and journal-nudge unions, the ideate, brainstorm, and office-hours judgments, the agent-operations runbook judgments with a provenance convention, the prompt-submission skill suggestion, and the global instruction section with skill propagation. Every judgment ships in suggest mode with verdicts and overrides logged; after about 30 real uses per decision the harness reports agreement per confidence band and the decision is kept advisory, promoted, or removed.

### Intent

Live calls return in 330 to 430 milliseconds at 0.042 dollars per million input tokens; a tier-selection probe scored 10 of 10 and an issue-type probe 19 of 30 with repository policy in the state. Code owns control flow; Jev returns probabilities (TR sections 1 to 5). The simplification removed five of the original targets (`/loop`, `/handoff`, verify panels, orchestrate review detection, delegation audit) and moved two (tier selection into the staffing component, the lens pre-screen into the roster-based code review); see the filing plan's section 2.

### Out-of-scope / non-goals

- No automatic action from a judgment until the harness shows agreement above a band for that decision.
- No vendor SDK; the client is stdlib `urllib`.
- No secrets in any log or prompt; state is redacted by pattern before sending.

### Files expected to change

- `plugins/fleet-core/scripts/fleet_commons/typesafe_client.py` and the `jev` tool, the staffing component, saga's code-review, ideate, brainstorm, office-hours, and parse-issue paths, mission-control's issue and labels paths, agent-operations runbooks, and the global instruction files — owned by the children.

### Tests to add or update

Per child; the parent's own check is the verdict log: every shipped judgment writes a verdict with the pinned model version, and `jev eval` runs against the cached answers.

### Context library links

- coding_standards: _none_

General references:
- TR sections 5, 8, 11; https://docs.typesafe.ai/llms.txt

### Acceptance criteria

- [ ] Every child under this parent is closed with its pull request merged: `gh api graphql -f query='{repository(owner:"infiquetra",name:"infiquetra-claude-plugins"){issue(number:<B>){subIssues(first:50){nodes{number state}}}}}'` shows every node `CLOSED`.
- [ ] `jev eval --summary` reports at least one decision with 30 or more logged verdicts and its agreement per confidence band.
- [ ] `grep -rn "TYPESAFE_API_KEY" plugins/ | grep -v getenv | wc -l` prints 0 (the key is read from the environment only).

### Verification

```bash
gh api graphql -f query='{repository(owner:"infiquetra",name:"infiquetra-claude-plugins"){issue(number:<B>){subIssues(first:50){totalCount nodes{number state}}}}}'
jev eval --summary
```

### Risk

medium

advisory everywhere by construction; the risk is a suggestion trusted before its band is measured, which the suggest-mode rule prevents.

### Handoff maturity
requirements-ready

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1019
- Number: 1019
- Created at: 2026-09-19T14:39:54.334932+00:00

