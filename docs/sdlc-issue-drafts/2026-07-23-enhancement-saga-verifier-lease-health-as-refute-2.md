---
title: enhancement(saga): verifier lease health as refute-panel validity precondition (under-strength instead of false refute)
repo: infiquetra-claude-plugins
type: enhancement
team: asgard
project: operations
status: Shaping
labels: enhancement, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
approval_state: needs_operator_approval
---

# enhancement(saga): verifier lease health as refute-panel validity precondition (under-strength instead of false refute)

## Problem

A refute-mandate verify panel whose verifiers lose their fleet lease (Bash fenced) can only
refute quantitative claims — it cannot execute tests — so machinery casualties read as
"refuted 3/3" and kill the unit even when the work is correct. During #616 this happened on
four consecutive passes for U1 (four distinct lease-machinery faults), forcing an operator
adjudication; during the #643 code review 3 of 8 sandboxed subagents hit the same fence
mid-run.

## Proposal

Make verifier lease health a precondition of panel validity in the emitter/panel contract:

- Each verifier reports whether its execution tooling (Bash) was live for the claims it judged.
- A refute verdict produced without working tooling for a quantitative claim counts as
  "unverifiable", not "refuted"; the panel goes under-strength instead of failing the unit.
- Under-strength handling: re-spawn the casualty (bounded retries) or surface an explicit
  operator gate, never a silent gate failure.

## Evidence

- `docs/work-sessions/2026-07-22-issue-616-worktree-write-fence-scoping.md` (durable machinery
  finding 2; operator decision A record)

### Files expected to change

- `plugins/saga/scripts/execution_spec.py` — verify-panel emission (verifier tooling-health
  report + under-strength handling)
- `plugins/saga/agents/readonly-verifier.md` — report contract addition
- Release surfaces: saga plugin.json, marketplace.json, CHANGELOG, drift pins

### Tests to add or update

- `tests/test_saga_workflow_emitter.py`: emitted verifier prompts/schema carry the
  tooling-health field; panel aggregation treats tooling-dead refutes of quantitative claims
  as unverifiable.

### Verification

```
uv run pytest -q tests/test_saga_workflow_emitter.py
# rehearsal: a panel with one fenced verifier goes under-strength instead of failing the unit
```

### Objective

Not yet assigned to an Objective — durable finding 2 from the #616 governed execution (operator adjudication A was the manual workaround); grouping is the operator's call.

### Intent

Verify panels distinguish 'refuted' from 'unverifiable': machinery casualties degrade the panel to under-strength with explicit handling instead of manufacturing false refutes.

### Out-of-scope / non-goals

Fixing the underlying lease machinery faults (separate defects); changing refute-mandate semantics for healthy panels.

### Context library links

- docs/work-sessions/2026-07-22-issue-616-worktree-write-fence-scoping.md (durable machinery finding 2; operator decision A)

### Acceptance criteria

- [ ] `uv run pytest -q tests/test_saga_workflow_emitter.py -k panel` green, including: emitted verifier schema carries an execution-tooling-health field.
- [ ] Aggregation test: a quantitative-claim refute from a tooling-dead verifier counts as `unverifiable`, not `refuted`; panel result is `under-strength`, unit not killed.
- [ ] Rehearsal script: a width-3 panel with one fenced verifier triggers bounded re-spawn or an explicit operator gate — assert no silent unit failure in the journal.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/a2c17e16-6a69-4ff8-a9f6-dc347823861a/scratchpad/issue-bodies/panel-validity.md
- Source type: local-file
- Source title: rehearsal: a panel with one fenced verifier goes under-strength instead of failing the unit

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/648
- Number: 648
- Created at: 2026-07-23T12:07:23.990523+00:00

