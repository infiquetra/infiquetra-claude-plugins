# Doc Review - Issue #358 non-skippable teardown and reclamation plan

One-line verdict: **READY** - all P0-P3 findings were fixed in place; the dependency-correct plan can
drive implementation after the operator approves its exact outcome/workflow candidate.

## Review-result contract

- **Target:** `docs/plans/2026-07-15-issue-358-non-skippable-teardown-reclamation-plan.md`
- **Reviewed revision:** uncommitted outcome worktree based on `a20cc3ce6d740a4891bddba71f7e8f2856620655`
- **Blocked:** no document-readiness blocker; workflow execution remains operator-gated
- **Classification:** issue-derived deep implementation plan
- **Rubrics:** all issue cores plus applicable context, sizing, and prerequisite extras
- **Linked:** `infiquetra/infiquetra-claude-plugins#358`, parent outcome
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`
- **Review artifact:** this file

## Applied fixes

The review found eight actionable defects and fixed all eight in the plan or its parent outcome.

| ID | Priority | Status | Applied fix |
|---|---|---|---|
| D358-1 | P1 | fixed | Added a broker-locked, monotonic owner-admission closing fence so a concurrent acquire/reserve/claim/retry cannot create a resource after the B8 zero-open snapshot; updated fleet-core scope and version to 0.15.0. |
| D358-2 | P1 | fixed | Made #357 a hard DAG prerequisite of #358 because idle eviction consumes #357's confirmed liveness classification; removed the accidental parallel-delivery claim and revalidated all ten nodes. |
| D358-3 | P1 | fixed | Removed the false cross-store atomic-snapshot implication; specified separate chain-verified/lock-consistent snapshots, action-time authority rechecks, and crash-after-action `already-absent` reconciliation. |
| D358-4 | P1 | fixed | Separated hermetic CI proof from live developer cleanup. CI plants and closes an isolated worktree leak; current worktrees require attended dry-run, separate authority, and #356 safety proof. |
| D358-5 | P2 | fixed | Bound hook scope and work: SessionEnd targets the trusted session/repo with a five-second timeout; SessionStart targets the canonical repo with a 15-second, four-action expired-only recovery batch. |
| D358-6 | P2 | fixed | Preserved `run_fact.v1` leaf production by requiring every teardown fact to carry #351's authoritative `subplot_id`, even when root records the fact for that leaf. |
| D358-7 | P1 | fixed | Replaced the stale concurrency-tester lens digest with the installed role digest; the full Workflow Structure now compiles and passes selection policy. |
| D358-8 | P3 | fixed | Corrected the source acceptance count from five to seven and made every acceptance outcome map to a plan contract and executable evidence row. |

## Readiness summary

The plan is implementation-ready and rejects the issue's stale optional-broker/second-ledger design.
Its single coherent slice is closing admission, reconciling owned resources, executing typed actions,
recovering interrupted runs, and proving the lifecycle; splitting those parts would reintroduce the
spawn/completion or action/result gaps the issue exists to close.

| rubric | score | result |
|---|---:|---|
| acceptance criteria clarity | 10/10 | seven distinct outcomes have named production tests, negative bounds, and proof artifacts |
| devil's advocate | 9/10 | broad three-plugin scope is justified by one atomic lifecycle; current-worktree deletion was removed from implicit scope |
| spec fidelity | 10/10 | requirements trace to the local outcome DAG and source issue; stale mechanics are explicitly superseded, not silently dropped |
| context completeness | 10/10 | canonical owners, production seams, precedents, files, tests, hook contract, and forbidden paths are named |
| issue sizing | 8/10 | six units and three release surfaces are large, but one PR preserves the closing-fence and terminal-receipt invariant |
| prerequisite mapping | 10/10 | #351/#356/#357 are hard upstream, #355 is a serialized sibling, and #353/cross-runtime proof are downstream |

## Evidence verified

- The current team-execution skill ends at Step B7 and has no B8.
- #356's reviewed plan owns broker admission, resource fencing, register-before-spawn, the validated
  outcome worktree sweep, and only a minimum stop-confirm-release-sweep adoption.
- #351's current `run_ledger.py` is hash-chained and leaf-produced; the plan preserves that
  attribution rather than creating a coordinator-only fact stream.
- #347's `ship_teardown.py` and ceremony provide reconcile/fail-loud/receipt precedent but use a
  different per-saga sidecar and broad merged-worktree janitor, so they are patterns rather than team
  ownership authority.
- The live 2026-07-15 census has nine worktrees, not the issue's historical fifteen; none was removed.
- Official Claude hooks document SessionEnd and SessionStart behavior:
  https://code.claude.com/docs/en/hooks
- Outcome validation passes with ten nodes and no warnings. Topological layers now place #358 after
  #357 and before #353.
- The Workflow Structure has eight steps, digest
  `4d670236995dc6a600a8214c4bd4238197af6783f976ca1749e066d6873a6fcd`, all four required reviewers,
  and required concurrency/event-flow validators. Installed role/profile and selection validation
  pass; no agent or validator was launched.
- `tests/test_outcome_spec.py`: 73 passed. `git diff --check`: clean.

## Remaining findings by priority

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Residual risk

Recovery after `SIGKILL` or host death remains eventual: it needs TTL expiry and a later SessionStart
or explicit recovery invocation because no process can run its own finalizer after death. Exact PID
signaling and worktree removal are intentionally root-only, identity-gated actions; the later code
review and required concurrency/event-flow validators must treat any weakened guard as blocking.

The plan deliberately does not authorize cleanup of the nine current worktrees. That is a separate
operator choice because names and age do not prove abandonment, and the source issue's historical
"cleanup in this PR" language is unsafe against live state.
