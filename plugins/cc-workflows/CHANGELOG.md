# Changelog

## [1.0.0] - 2026-08-30

- Initial extraction from Saga (#925, issue #918 wave 1, unit U4): the workflow-script
  emission path (`emit_workflow_script` + the #708 agent-opts guards + the driver-owned
  settlement/lease metadata builders) moved from `plugins/saga/scripts/execution_spec.py`
  into `skills/cc-workflows/scripts/emitter.py`; `workflow_emitter.py` (the frozen
  `workflow_lease_reservation.v1` contract CLI) moved from `plugins/saga/scripts/`.
- The boundary is the typed execution spec: the emitter reads Saga's spec shape (never a
  copy); Saga keeps the spec schema, validation, tier resolution, `team_emitter.py`, and
  the integration contract that delegates `emit` / `settlement` / `lease` here.
- Workflow protocol prose (authoring Steps 2–5, invocation identity, lease-contract
  retirement semantics, release/renew) carried with the plugin; Saga's `/plan` and `/work`
  keep the driver-side seam.
