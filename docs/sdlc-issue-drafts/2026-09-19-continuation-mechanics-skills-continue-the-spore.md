---
title: Continuation mechanics: skills continue, the spore injects the next step, the prompt suggestion names the command
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

# Continuation mechanics: skills continue, the spore injects the next step, the prompt suggestion names the command

### Objective

Every lifecycle skill ends by doing the next step in the same turn; the run record's `next_step` is injected at session start by the existing spore hook (and suppressed when the record says the step is done, so stale state cannot leak); the prompt-submission suggestion names the command when the operator's text is about a step. `/loop`, `/resume`, and `/handoff` and the handoff and intent envelope machinery are removed in A13; the run record does their job.

### Intent

The chain is operator-invoked today except `/work` → `/code-review`; `/loop`'s Drive mode is the only chaining and must be chosen. This session itself started with a stale `next_step` from an old saga tick, which is why suppression is part of the change (SR R8).

### Out-of-scope / non-goals

- No hook that blocks or refuses on the chain.
- No new state: `next_step` lives in the run record only.

### Files expected to change

- `plugins/saga/hooks/compact_spore_session_hook.py`, `precompact_spore_hook.py` (read `next_step` from the run record; suppress when done)
- `plugins/saga/skills/{plan,doc-review,work,code-review,qa}/SKILL.md` (each ends by invoking the next step)
- `plugins/saga/hooks/hooks.json` (a `UserPromptSubmit` entry for the suggestion, shared with B8)
- release surfaces

### Tests to add or update

- The session-start hook injects `next_step` for an active run and injects nothing for a closed run or when no record exists.
- Each lifecycle skill's instructions end with the invocation of the next step, not a recommendation (a structural test over the skill files).

### Context library links

- coding_standards: _none_

General references:
- SR R8, section 5 ("How automatic works mechanically"); TR R26

### Acceptance criteria

- [ ] `grep -n -i "recommended next" plugins/saga/skills/*/SKILL.md` prints nothing.
- [ ] `uv run pytest tests/test_spore_hooks.py -q` passes with the suppression case present.
- [ ] Starting a new session in a repository with an active run prints the run's `next_step` in the session-start context, and none for a closed run.

### Verification

```bash
grep -n -i "recommended next" plugins/saga/skills/*/SKILL.md
uv run pytest tests/test_spore_hooks.py -q
```

### Risk

low

hook text and skill endings; nothing here can block a turn.

### Handoff maturity
requirements-ready

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1029
- Number: 1029
- Created at: 2026-09-19T14:46:53.555086+00:00

