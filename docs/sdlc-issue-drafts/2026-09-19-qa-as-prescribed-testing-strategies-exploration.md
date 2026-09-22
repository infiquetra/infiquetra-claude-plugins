---
title: `/qa` as prescribed testing strategies (exploration)
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

# `/qa` as prescribed testing strategies (exploration)

### Research Question

What set of prescribed testing strategies should `/qa` offer, chosen by situation, so that the functional-test step can verify working software end to end with more tools than a browser (browser automation, device emulators such as an iPhone simulator for Auralis, API contract runs, command-line smoke, data checks), and how should a typed-judgment model help decide which strategy and which tool apply to a given change and environment?

### Context

`/qa` today is a gate-only verdict command that reads the evidence ledgers; those ledgers are removed (A11) and `/qa` reads the run record instead until this redesign lands. The sdlc's functional-test step runs after the non-production deployment against the real environment. The operator wants the strategies prescribed, not improvised, and sees typed judgments (TypeSafe's Jev) as useful for choosing among them (SR R30).

### Success Criteria

- A catalogue of testing strategies, each with its situation triggers, its tools, its evidence shape, and its thresholds, owned by code.
- A decision procedure (which strategy, which tool) that a typed judgment can answer from the change shape and the environment, with a logged suggestion and override.
- A spec that `/plan` can consume for the implementing card.

### Timebox

Two working sessions: one `/brainstorm` run producing the requirements document, one `/spec` run producing the specification.

### Deliverables

- `docs/brainstorms/<date>-qa-testing-strategies.md`
- `docs/specs/<date>-qa-testing-strategies.md`
- A follow-up capability card under parent A with the implementing work.

### Key Questions to Answer

- Which situations recur across the repositories (web app, Flutter and native macOS app, Python plugins, infrastructure) and which tool serves each?
- What evidence does each strategy leave in the run record, and what threshold turns evidence into a pass?
- Where does the typed judgment add value beyond a lookup table (ambiguous change shapes, mixed changes), and where would it mislead?
- How does the Functional Tester role invoke a strategy in its own herdr session?

### Related Issues

- Parent A; A11; B1 (the judgment client); TR section 5 for the judgment patterns.

### Intent

`/qa` today is a gate-only verdict command that reads the evidence ledgers; those ledgers are removed (A11) and `/qa` reads the run record instead until this redesign lands. The sdlc's functional-test step runs after the non-production deployment against the real environment. The operator wants the strategies prescribed, not improvised, and sees typed judgments (TypeSafe's Jev) as useful for choosing among them (SR R30).

### Target repo / surface

`infiquetra-claude-plugins` — `plugins/saga/skills/qa/` and the `/qa` command; the deliverables land under `docs/brainstorms/` and `docs/specs/`.

### Mode

explore — a bounded `/brainstorm` then `/spec` research pass, not an implementation.

### Constraints

Two working sessions: one `/brainstorm` run producing the requirements document, one `/spec` run producing the specification.

### Transfer notes

Produces `docs/brainstorms/<date>-qa-testing-strategies.md`, `docs/specs/<date>-qa-testing-strategies.md`, and a follow-up capability card under parent A for the implementing work; related to A11 and B1.

### Risk

UNKNOWN

Not applicable — this is a non-actionable exploration card; risk belongs to the follow-up implementing capability card this exploration produces, not to this research step.

### Handoff maturity
requirements-ready

### Recommended Tier Band
sonnet/low

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1031
- Number: 1031
- Created at: 2026-09-19T14:48:02.141910+00:00

