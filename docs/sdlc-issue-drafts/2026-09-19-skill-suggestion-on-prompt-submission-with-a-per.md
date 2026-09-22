---
title: Skill suggestion on prompt submission with a persistent local client (exploration)
repo: infiquetra-claude-plugins
type: exploration
team: asgard
project: operations
status: Ready for Planning
stage: Shaping
labels: exploration, research
risk: UNKNOWN
mode: execute
handoff_maturity: requirements-ready
---

# Skill suggestion on prompt submission with a persistent local client (exploration)

### Research Question

Can a `UserPromptSubmit` hook suggest the right saga command from the operator's text within a latency the operator does not notice, given that a cold-process hook costs 1.07 to 1.94 seconds while the API answers in about 0.3 seconds, and what persistent local client shape (a socket-served process, a warm interpreter, a cache) makes that true?

### Context

TR R26 and section 7; the vendor's skill-suggestion cookbook; the codex-context-diet measurement of cold hook cost. A12 adds the hook registration; this exploration decides whether the hook can be fast enough to keep.

### Success Criteria

- A measured per-prompt latency under 400 milliseconds at the 95th percentile for the hook, or a documented reason it cannot be reached.
- A recommendation to keep, defer, or drop the suggestion.

### Timebox

One working session.

### Deliverables

- `docs/analysis/<date>-prompt-suggestion-latency.md` with the measurements and the recommendation.
- If kept, a capability card under parent B for the implementation.

### Key Questions to Answer

- Does a persistent process survive Claude Code's hook lifecycle and the two plugin trees?
- What state does the suggestion need (the run record's `next_step`, the command list) and how is it kept fresh?
- How is a wrong suggestion surfaced and overridden without noise?

### Related Issues

- Parent B; B1; A12.

### Intent

TR R26 and section 7; the vendor's skill-suggestion cookbook; the codex-context-diet measurement of cold hook cost. A12 adds the hook registration; this exploration decides whether the hook can be fast enough to keep.

### Target repo / surface

`infiquetra-claude-plugins` — the `UserPromptSubmit` hook A12 registers, and fleet-core's TypeSafe client (B1).

### Mode

explore — one working session measuring latency, not an implementation.

### Constraints

One working session.

### Transfer notes

Produces `docs/analysis/<date>-prompt-suggestion-latency.md` with the measurements and the recommendation; if kept, a capability card under parent B for the implementation.

### Risk

UNKNOWN

Not applicable — this is a non-actionable exploration card; risk belongs to the follow-up implementing capability card this exploration produces, not to this research step.

### Handoff maturity
requirements-ready

### Recommended Tier Band
sonnet/low

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1038
- Number: 1038
- Created at: 2026-09-19T14:51:30.644385+00:00

