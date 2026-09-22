---
title: Instructions and runbooks after the release
repo: infiquetra-agent-operations
type: context-update
team: asgard
project: operations
status: Ready for Planning
stage: Shaping
labels: context-update, documentation
risk: UNKNOWN
mode: execute
handoff_maturity: requirements-ready
---

# Instructions and runbooks after the release

### Context Summary

After saga 1.0.0 ships, the instruction files and runbooks that describe the old mechanics are corrected: the global Claude instructions' delegation and tiering sections name roster roles and the staffing component instead of team-execution and "team teammate" units, with the Gemini and Codex mirrors following; the agent-operations coordinator prompt in `docs/operations/single-issue-delivery.md` shrinks to "run `/plan issue N` in the coordinator pane and answer the admission questions," with the roster section pointing at the roster helper; `lead-handoff-role-boundaries.md` references the roles library for role definitions. The global files live outside any repository and are edited by the operator; this card records the exact edits and their date.

### What Changed

Saga's chain became automatic (parent card A), roles became roster sessions (A4, A6), and eleven commands were removed (A13).

### Affected Surfaces

- `~/.claude-company/CLAUDE.md` and `~/.claude/CLAUDE.md` ("Delegation & Context Economy", "Model & effort tiering"), `~/.gemini/GEMINI.md`, `~/.codex/AGENTS.md`
- `docs/operations/single-issue-delivery.md`, `docs/operations/lead-handoff-role-boundaries.md`, `docs/operations/tooling.md`

### Acceptance criteria

- [ ] `grep -c "team-execution" ~/.claude-company/CLAUDE.md` prints 0.
- [ ] `grep -c "/plan issue" docs/operations/single-issue-delivery.md` prints at least 1 and `wc -l docs/operations/single-issue-delivery.md` is under 80.
- [ ] The engineering journal in agent-operations carries a decision entry for the change with the date.

### Verification

```bash
grep -c "team-execution" ~/.claude-company/CLAUDE.md
wc -l docs/operations/single-issue-delivery.md
```

### Risk

low

documentation; nothing executes it.

### Intent

Saga's chain became automatic (parent card A), roles became roster sessions (A4, A6), and eleven commands were removed (A13); this card corrects the instruction files and runbooks that describe the old mechanics to match.

### Target repo / surface

`infiquetra-agent-operations` — `docs/operations/single-issue-delivery.md`, `docs/operations/lead-handoff-role-boundaries.md`, `docs/operations/tooling.md`; plus the global instruction files listed in Affected Surfaces (operator-owned, outside any repository).

### Mode

execute — a direct text edit to runbooks and global instruction files; no application code change.

### Constraints

The global instruction files are operator-owned; this card records the exact edits and their date rather than making the edit itself unreviewed. Sequenced after saga 1.0.0 ships (parent card A13).

### Transfer notes

The operator applies the recorded edits to the global instruction files (operator-owned, outside any repository); the in-repository files (`docs/operations/*`) are edited directly by whoever implements this card.

### Handoff maturity
requirements-ready

### Recommended Tier Band
sonnet/medium
