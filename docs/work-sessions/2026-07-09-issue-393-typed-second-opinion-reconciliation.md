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

## Next Step

Execute U3 to preserve rejected offloads as typed advisory manifest and reconciliation evidence.
