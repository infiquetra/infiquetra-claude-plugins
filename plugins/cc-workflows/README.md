# cc-workflows

Claude Code Workflow execution capability for Infiquetra plans, extracted from Saga (#925,
issue #918 wave 1, unit U4).

## What it is

The reusable capability behind the `cc-workflows-ultracode` execution backend:

- `skills/cc-workflows/scripts/emitter.py` — the workflow-script emission path
  (`emit_workflow_script`: execution spec → runnable `.workflow.js`), the driver-owned
  settlement/lease metadata builders, and the #708 agent-opts guards.
- `skills/cc-workflows/scripts/workflow_emitter.py` — the frozen
  `workflow_lease_reservation.v1` contract CLI (`reserve` / `attest` / `release` / `renew`).
- `skills/cc-workflows/SKILL.md` — the explicit-invocation contract and the spec → script
  authoring protocol (thin prompts, verify panels, validate, emit, approve).
- `skills/cc-workflows/references/protocol.md` — invocation identity, lease-contract
  retirement semantics, release/renew, settlement.

## The boundary

The seam is the **typed execution spec**, not a clean separation: this plugin reads Saga's
spec shape (`plugins/saga/scripts/execution_spec.py`) and never copies it. Saga keeps the
spec schema, validation, tier resolution, and `team_emitter.py`, plus the typed integration
contract that recognises the backend, records the explicit selection, validates availability,
invokes this emitter, and consumes its structured result.

## Explicit invocation only

`cc-workflows-ultracode` is never a default or automatic backend and never a generic
interchangeable execution backend (issue #808 NARROW, #840 C5). The recommender never
returns it; it is entered only by explicit invocation.
