---
title: Issue 351 dispatch settlement work session
issue: 351
status: active
date: 2026-07-16
plan: ../plans/2026-07-15-issue-351-dispatch-settlement-plan.md
---

# Issue 351 dispatch settlement work session

## Goal

Ship one evidence-derived settlement contract across outcome, team-execution, and generated-workflow
fan-outs. The parent records manifests and pre-call spawns in the canonical run-fact ledger, settles
from trusted evidence, derives casualty and dead-letter views, and never grants agents ledger writes.

## Current Phase

Implementation and release surfaces are complete in the issue worktree. Full repository quality
gates, the approved Verified Workflow review/validator panel, `/code-review`, PR, merge, board
reconciliation, QA evidence, and outcome harvest remain.

## Completed

- Implemented the closed `dispatch-settlement` fact vocabulary, atomic state transitions, casualty
  reporting, open positions, late delivery, dead-letter derivation, and stable-key retry claims.
- Wired outcome manifest/spawn/settle boundaries and canonical GitHub completion evidence.
- Added deterministic generated-workflow expected-unit metadata and documented driver-owned
  settlement for filesystem-less agents.
- Added team-execution reviewer/validator settlement protocol, evidence boundaries, casualty gate,
  dead-letter view, and retry rules.
- Added an observational worktree leak projection that neither quarantines malformed input nor
  mutates the registry, ledger, or filesystem.
- Updated Saga to 0.98.0 and team-execution to 2.17.0 across plugin metadata, marketplace entries,
  changelogs, README guidance, and version guards.
- Preserved the approved workflow digest
  `4c7114ab6317aad550977f37a0c3992dd9667ee4e57e23d58e750b9b39057848`.

## Checkpoints

- `59cce98 feat(saga): add dispatch settlement ledger`
- Focused settlement/outcome/worktree tests: 88 passed.
- Prior focused execution-spec, outcome, Saga, and team-execution suites: 398 passed, 1 skipped;
  54 passed; all scoped Ruff checks passed.

## Next Steps

1. Run formatter, lint, type, security, release-parity, and full test gates.
2. Run the approved review and validator roles; repair every validated finding within the bounded
   remediation policy.
3. Write and close `/code-review`, then commit and publish the issue PR.
4. Prove CI, merge, close issue #351, reconcile Operations, capture QA/closure evidence, and harvest
   outcome node `sub-351`.

## Blockers and Residual Risk

No implementation blocker is known. Workflow agents cannot write the ledger, so driver materialized
host/result evidence remains the explicit trust boundary and fails closed when missing or
contradictory.
