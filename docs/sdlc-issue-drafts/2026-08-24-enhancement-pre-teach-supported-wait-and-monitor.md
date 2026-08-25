---
title: [ENHANCEMENT] Pre-teach supported wait and monitor patterns in orchestration guidance
repo: infiquetra-claude-plugins
type: enhancement
team: asgard
project: operations
status: Shaping
labels: enhancement, needs-plan
risk: low
handoff_maturity: requirements-ready
---

# [ENHANCEMENT] Pre-teach supported wait and monitor patterns in orchestration guidance

### Objective

Stop sessions from rediscovering the polling rules the hard way: the orchestration guidance should
pre-teach the supported wait mechanism for each recurring wait shape, so the execution guard's
sleep-chain block stops costing a turn per occurrence.

## Observed behavior

Across the two large agent-plugins orchestration sessions in the audit window, agents reached for
chained `sleep N && <check>` shell polling seven times — polling PR checks (`gh pr checks`),
background task output, and sibling agent panes (`herdr agent read …`) — and the execution guard
rejected every attempt with the same fixed text ("To wait for a condition, use Monitor with an
until-loop… use run_in_background… Do not chain shorter sleeps"). Each block cost a full agent turn
before the supported mechanism was used. The Orchestrate plugin already ships a supported
settlement wait (`orchestrate.py wait`, event-socket based —
`plugins/orchestrate/skills/orchestrate/SKILL.md:176-181`) and Herdr ships `agent wait` /
`pane wait-output`; none of the governing guidance pre-teaches them for these wait shapes.

Occurrences: session 754b6091-9bb0-46dc-88b2-e00814b02fd8 at 2026-08-22T03:54:22Z and
2026-08-23T00:00:54Z; session 939e7ee5-181f-4f11-a2fd-7ec978d73517 at 2026-08-23T16:44:30Z,
17:05:34Z, 17:59:38Z, and 22:27:54Z (seven total).

## Operator impact

Seven wasted turns in one workflow family, recurring per session because nothing in the workflow's
own guidance teaches the sanctioned alternatives up front.

## Evidence and provenance

- `~/.claude/projects/-Users-jefcox-workspace-infiquetra-infiquetra-agent-plugins/754b6091….jsonl`
  line 695 (2026-08-22T03:54:22Z) — "Blocked: sleep 25 followed by: gh pr checks 2 …".
- `~/.claude/projects/…-infiquetra-agent-plugins/939e7ee5….jsonl` line 2055
  (2026-08-23T17:59:38Z) — "Blocked: sleep 45 followed by: herdr agent read codereview-codex …".
- Five further anchors: `/private/tmp/plugin-transcript-audit-20260823/lane2-agent-plugins/findings.json` (lane2-03).
- Transcript-audit report: FINAL-REPORT.md finding E5.

### Intent

Add a "waiting" section to the Orchestrate skill guidance naming the three recurring wait shapes
and the supported mechanism for each, with one copy-pasteable example per shape: (a) sibling herdr
agent/pane output → `herdr agent wait` / `pane wait-output` / `orchestrate.py wait`; (b) PR checks
and other external state → a Monitor-style until-loop; (c) a command the session itself started →
background run with completion notification.

### Out-of-scope / non-goals

- Changing the execution guard itself (it behaves correctly).
- New tooling or wrappers; this is guidance placement.
- Herdr's own documentation (dependency context).

### Files expected to change

- `plugins/orchestrate/skills/orchestrate/SKILL.md`
- `plugins/orchestrate/.claude-plugin/plugin.json`, `plugins/orchestrate/CHANGELOG.md`,
  `.claude-plugin/marketplace.json` (release-surface parity)

### Tests to add or update

- None required beyond the grep-verifiable documentation checks below; if a docs-lint exists for
  the skill, it runs unchanged.

### Context library links

- source_context: `/private/tmp/plugin-transcript-audit-20260823/issue-sources/5-supported-monitoring.md`
  (audit task dir — ephemeral; durable anchors are the transcript paths above)

### Acceptance criteria

- [ ] `grep -n -i "waiting" plugins/orchestrate/skills/orchestrate/SKILL.md` shows a section
      naming all three wait shapes with one copy-pasteable example each.
- [ ] `grep -n -i "sleep" plugins/orchestrate/skills/orchestrate/SKILL.md` shows an explicit
      "never chained sleep" instruction beside the supported patterns.
- [ ] The section cross-references `orchestrate.py wait` for settlement waits — verifiable via
      `grep -n "wait" plugins/orchestrate/skills/orchestrate/SKILL.md`.
- [ ] Implementation-time check: one subsequent run of this workflow shows zero guard-blocked
      sleep-chain attempts in its transcript.

### Verification

```bash
grep -n -i "waiting" plugins/orchestrate/skills/orchestrate/SKILL.md
grep -n -i "sleep" plugins/orchestrate/skills/orchestrate/SKILL.md
scripts/gate.sh
```

Validation belongs in implementation — no fresh reproduction was required to file (operator
instruction, 2026-08-24).

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Recommended Tier Band

sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/783
- Number: 783
- Created at: 2026-08-24T03:58:53.180092+00:00

