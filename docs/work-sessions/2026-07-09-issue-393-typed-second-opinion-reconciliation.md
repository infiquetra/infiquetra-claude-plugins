# Issue #393 Typed Second-Opinion Reconciliation Work Session

## Scope

Execute U1-U6 from the approved typed second-opinion reconciliation plan on the
operator-confirmed `team-execution` backend. This work session records local implementation,
review, and validation evidence only; PR, issue, board, deploy, and outcome receipts remain out of
scope.

## Team Execution Evidence

- Backend: `team-execution`
- Run: `issue-393-typed-second-opinion-reconciliation`
- State: `.claude/team-execution/validators/` (git-ignored)
- Worker schedule: dependency-serial resident workers because the approved units overlap shared Saga
  files; later segments remain blocked until their dependencies commit.
- U1 worker: `worker-reconcile-core`, resolved effort `high`, Agent-path effort rider reconciled with
  no tiering drift.
- U1 manifest: `worker-reconcile-core-U1` in the `issue-393` manifest store, disposition
  `ran-as-requested`.
- U2 worker: `worker-intent-contract`, resolved effort `high`, Agent-path effort rider reconciled with
  no tiering drift.
- U2 manifest: `worker-intent-contract-U2` in the `issue-393` manifest store, disposition
  `ran-as-requested`.
- U3 worker: `worker-manifest-signal`, resolved effort `high`, Agent-path effort rider reconciled
  with no tiering drift.
- U3 manifest: `worker-manifest-signal-U3` in the `issue-393` manifest store, disposition
  `ran-as-requested`.
- U4 worker: `worker-panel-foreman`, resolved effort `high`, Agent-path effort rider reconciled with
  no tiering drift.
- U4 manifest: `worker-panel-foreman-U4` in the `issue-393` manifest store, disposition
  `ran-as-requested`.
- U5 worker: `worker-retro-reader`, resolved effort `high`, Agent-path effort rider reconciled with no
  tiering drift.
- U5 manifest: `worker-retro-reader-U5` in the `issue-393` manifest store, disposition
  `ran-as-requested`.
- U6 worker: `worker-release-closure`, resolved effort `medium`, Agent-path effort rider reconciled
  with no tiering drift.
- U6 manifest: `worker-release-closure-U6` in the `issue-393` manifest store, disposition
  `ran-as-requested`.

## Completed Work

### U1: Typed reconciliation registry and ledger writer

- Added immutable reconciliation recipes, typed results/items, source-finding accounting, canonical
  result hashing, and strict reconciliation-fact read/write validation.
- Extended `run_fact.v1` with the closed `reconciliation` fact kind.
- Added reconciliation completeness as a prerequisite at `engine_dispatch.satisfy_gate()` without
  relaxing the existing Claude verification, observer, disposition, claim, or advisory-role refusals.
- Added happy-path, edge, failure, chain-integrity, and gate-integration tests.

Checks:

- `uv run pytest tests/test_reconcile.py tests/test_run_ledger.py tests/test_saga_engine_dispatch.py -q`
  - 89 passed
- Narrow Ruff over U1 implementation and tests
  - passed
- `uv run mypy plugins/saga/scripts/reconcile.py --follow-imports=skip`
  - passed
- `git diff --check`
  - passed

### U6: Documentation, decision record, and release closure

- Documented typed reconciliation facts, rejected-offload evidence, three-intent recipes,
  `PANEL_N_CAP`, and read-only retro proposals across the run-fact and Team Execution contracts.
- Recorded the binding intent-to-recipe decision, external-engine authority boundary, approval-only
  learning rule, and fourth-intent revisit condition in the engineering journal.
- Bumped fleet-core to `0.8.4`, Saga to `0.75.17`, and Team Execution to `2.14.3`, with synchronized
  changelogs and marketplace metadata.
- Updated version drift guard tests for the released contracts.

Checks:

- Full focused reconciliation matrix
  - 485 passed
- Release/package matrix
  - 71 passed
- Marketplace sync check
  - passed
- Release-surface parity
  - passed
- `git diff --check`
  - passed

### U5: Read-only retro proposal view

- Added a chain-verified, reconciliation-schema-validated derive-on-read proposal view.
- Deduplicated reconcile/apply facts by stable reconciliation identity while retaining action and
  ledger-hash evidence.
- Emitted explicit `no-proposal` output for an empty ledger and `approval_required: true` for every
  recipe-review proposal.
- Preserved the torn-tail tolerance and made non-trailing corruption, chain failure, and invalid
  reconciliation records visible failures.
- Documented `/retro`'s terminal, advisory, propose-diff-and-wait boundary.

Checks:

- Focused U5 pytest matrix
  - 25 passed
- Targeted Ruff format and lint
  - passed
- Focused mypy with skipped imports
  - passed
- `git diff --check`
  - passed

### U4: Bounded advisory-jury panel and foreman reconciliation

- Added a separate `AdvisoryPanelRequest` contract and `PANEL_N_CAP = 7`.
- Validated normalized role names, advisory/Claude-foreman role posture, zero membership, cap
  overflow, and all-member availability before the first dispatch.
- Reused `resolve_role()` and `panel_halt()` while preserving the existing single-resolution panel
  role policy.
- Deduplicated identical non-empty member evidence, retained explicit per-member empty evidence, and
  required an exact typed Claude-foreman reconciliation before ledger append.
- Persisted only typed reconcile/apply facts; raw member output remains transient and panel evidence
  remains structurally non-gating.

Checks:

- Focused U4 pytest matrix
  - 249 passed
- Repository Ruff and targeted Ruff rerun
  - passed
- `git diff --check`
  - passed

### U3: Rejected-offload disposition and manifest evidence wiring

- Added the `rejected-offload` disposition with a mandatory normalized non-empty note.
- Extended the single manifest-builder precedence while preserving fallback, substitution,
  delegation-integrity, unproven, proof-integrity, and requested-result ordering.
- Projected rejection notes into typed dropped reconciliation items and explicit advisory
  reviewer/validator evidence.
- Preserved the structural rule that rejected, panel, or other advisory evidence cannot satisfy a
  gate.
- Updated the worker-manifest and external-engine chaperone contracts.

Checks:

- Focused U3 pytest matrix
  - 108 passed
- Targeted Ruff format and lint
  - passed
- `git diff --check`
  - passed

### U2: Canonical divergence intent and plan-time tier contract

- Added `divergence` to the fleet-core-owned canonical intent vocabulary.
- Added the `opus / high` divergence policy and regenerated the plan skill's tier table from the
  renderer.
- Preserved omitted-intent `offload` behavior, selector XOR validation, plain-Claude serialization,
  and upgrade-only segment intent ordering.
- Added execution-spec, renderer, resolver, team/workflow emitter, and chaperone-economics coverage.

Checks:

- Focused U2 pytest matrix
  - 338 passed
- Narrow Ruff over U2 implementation and tests
  - passed
- `git diff --check`
  - passed

## Team Execution Review Cycle 1

The required panel reviewed the same verified epoch-1 full-diff pointer in two capacity-bounded
waves (three reviewers, then two). Consensus was not reached:

| Reviewer | Score | Verdict |
| --- | ---: | --- |
| Devil's Advocate | 7.1 | needs revision |
| Security | 7.0 | needs revision |
| Architecture | 8.0 | needs revision |
| Testing | 7.1 | needs revision |
| Clarity | 7.1 | needs revision |

### Core remediation

- Bound reconciliation to immutable dispatch execution identity, canonical intent, evidence digest,
  and source-finding identities; rejected replay, mismatch, and empty-result bypasses before existing
  authority checks.
- Preserved rejected results under their canonical intent and closed surplus recipe definitions.
- Replaced raw-result ledger persistence with a bounded structural projection; rationales and engine
  prose remain outside the JSONL record, and ledger/lock files are mode `0600`.
- Added one-lock verified snapshot append semantics and enforced `reconcile` then at most one `apply`.
- Restored all legacy gate suites to their original assertion paths.

Checks:

- Focused core and legacy gate matrix
  - 218 passed
- Direct `reconcile.py` branch coverage
  - 94%
- Targeted Ruff and scoped mypy
  - passed
- `git diff --check`
  - passed

## Next Step

Complete panel-policy and documentation remediation, then re-engage only the five failed reviewers.
