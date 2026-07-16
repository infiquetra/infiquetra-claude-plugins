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

Implementation, release surfaces, the corrected Verified Workflow review/validator panel, and the
full integration gate are complete in the issue worktree. `/code-review`, PR, merge, board
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
- Corrected the validator evidence declaration from two protected records to the verifier's supported
  one-command-record contract. The operator approved replacement workflow digest
  `2f4da7745094b5f6427206b6246df6d00dd5c46cae4aef453279ca8e99dd9ea5`.

## Checkpoints

- `59cce98 feat(saga): add dispatch settlement ledger`
- Focused settlement/outcome/worktree tests: 88 passed.
- Prior focused execution-spec, outcome, Saga, and team-execution suites: 398 passed, 1 skipped;
  54 passed; all scoped Ruff checks passed.
- Review attempt 1 produced six validated findings across architecture, security, and failure-mode
  lenses: cohort boundary, closed fact validation, attempt binding, crash-gap reconciliation, retry
  exhaustion, and the public evidence path. Protected receipts record the blocking verdicts.
- Repair now groups outcome frontiers, preserves original retry binding, reconciles every canonical
  completion, returns visible retry exhaustion, derives public settlement from closed structured
  evidence, and validates stored facts semantically in addition to the hash chain.
- Post-repair settlement and outcome-dispatch tests: 80 passed, including concurrent duplicate and
  distinct-unit spawn races that preserve exactly-once transition checks and the ledger hash chain.
- Inline review caught and repaired four final boundaries: rolling-upgrade in-flight dispatches are
  excluded from new cohorts, terminal retries stop adding intents, non-string fact fields fail closed,
  and emitted workflow settlement identity remains stable across session tier ceilings. The expanded
  settlement, outcome-dispatch, and execution-spec suites pass 444 tests.
- Workflow run 4 was superseded after both tester rows proved structurally ungateable: their approved
  two-ID evidence declaration conflicted with the verifier's mandatory single command-output record.
  The corrected run changes no role, model, effort, permission, dependency, implementation, or test.
- Corrected workflow run 5 passed all four reviews and both required validators. Concurrency selected
  9 tests; event flow passed 87 tests. Both validator commands produced clean no-mutation audits.
- Full repository test gate passed 4,492 tests with 1 skip and 83 percent aggregate coverage. After
  formatter and one test-helper typing cleanup, the 444 focused settlement/outcome/workflow tests,
  repository-wide Ruff format/check, and mypy over 244 source files all pass.
- Release parity, marketplace sync, and release-surface diff guards all pass against refreshed
  `origin/main`. Bandit reports no new changed-line finding and no medium/high finding in the changed
  Python modules; its nonzero status is the repository's pre-existing low-severity assert/subprocess
  baseline.
- Captured gate-output SHA-256 values: full pytest
  `cb4b6e1e2e97f88d7ed4a3da9bef55b3f0336ad74048e489cf3bbd2118d08328`, focused pytest
  `a9f02b3abf8b252fc71c61cc173a8c20bec689d4272a4b151b702ebc9e601ae2`, mypy
  `ed90d8a91f19eaa093edf47cd47b55644af5ba8d9e7e3e089150683c5b0b2e0b`, release parity
  `4eb13e5e15735d1ade8b9d3e4715cfcbbc666cd31d2133a7c80ea4ae4ca9a57c`, marketplace sync
  `c2a39a1f311285b8d0b53d138052a2cfc188215fd4d6bf6e3f6ed714b25b2786`, and release diff
  `cc5ae8f353da4c76bc8672d5cc61b93c0456a30abd0befff0348b5bda40115d9`.

## Next Steps

1. Write and close `/code-review`, then commit and publish the issue PR.
2. Prove CI, merge, close issue #351, reconcile Operations, capture QA/closure evidence, and harvest
   outcome node `sub-351`.

## Blockers and Residual Risk

No implementation blocker is known. Workflow agents cannot write the ledger, so driver materialized
host/result evidence remains the explicit trust boundary and fails closed when missing or
contradictory.
