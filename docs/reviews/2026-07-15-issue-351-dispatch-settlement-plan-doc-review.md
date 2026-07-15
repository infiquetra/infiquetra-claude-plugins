# Doc review - dispatch settlement plan (#351)

Verdict: **READY AT OPERATOR GATE** - all issue-rubric and readiness findings were fixed in place;
zero P0-P3 findings remain. Implementation is intentionally blocked until the outcome and exact
Verified Workflow candidate are approved.

## Review-Result Contract

- **Target:** `docs/plans/2026-07-15-issue-351-dispatch-settlement-plan.md`
- **Reviewed revision:** working tree on `outcome/lease-safe-runtime-continuity`, base
  `a20cc3ce6d74`
- **Blocked status:** document is not blocked; execution is blocked at the explicit operator gates
- **Linked issue:** infiquetra/infiquetra-claude-plugins#351, outcome node `sub-351`
- **Linked outcome:** `docs/outcomes/lease-safe-runtime-continuity/proposal.md` (local review draft)
- **Review artifact:** `docs/reviews/2026-07-15-issue-351-dispatch-settlement-plan-doc-review.md`
- **Override rationale:** none
- **External panel:** not invoked; the panel is opt-in and the operator did not request external egress

## Applied Fixes

The review replaced the stale artifact-pointer assumption with the existing worker-manifest contract,
made pre-call spawn and late-delivery semantics explicit, defined the closed ledger shape, mapped every
requirement to units/tests, pinned real workflow/test/release files, serialized the Saga release
collision with #350, repaired the machine-checked workflow section, and replaced an inaccurate
read-only-sandbox claim with the actual mutation contract and root diff audit.

## Issue-Rubric Results

All three core issue rubrics and all applicable extras ran inline. Scores reflect the remediated plan.

| Rubric | Score | Finding | Status |
|---|---:|---|---|
| acceptance criteria clarity | 9 | Spawn timing, retry cohort denominator, late delivery, and the published no-ACK selector lacked one implementable interpretation | FIXED - event shapes, per-attempt cohorts, late-delivery facts, and worker-manifest ACK semantics are explicit |
| devil's advocate | 8 | Three runtime adapters make the slice broad, but shipping only one leaves the issue's falsely-green fan-out path intact | ACCEPTED - one shared core with thin adapters and no throttling/refactor scope |
| spec fidelity | 9 | The issue assumes `artifact_pointer.py` acknowledges worker delivery, but live code defines it as a post-work reviewer snapshot | FIXED - `saga.manifest.v1` output completeness is the delivery evidence; the published selector remains stable |
| context completeness | 10 | The workflow driver integration and one test filename were initially unresolved | FIXED - `/work` Phase 1.5 and `tests/test_saga_execution_spec.py` are named exactly |
| issue sizing | 8 | Core, three adapters, CLI, and two release surfaces are a large but cohesive contract | ACCEPTED - six dependency-ordered units and atomic checkpoints bound review without landing a knowingly partial contract |
| prerequisite mapping | 9 | #401 was implicit and #350 shared release files were not treated as an execution collision | FIXED - #401 is confirmed merged; #351 refreshes from `main` after #350 and names all downstream leaves |

## Readiness Findings

Every readiness finding was a safe, evidence-backed fix.

| ID | Priority | Finding | Status |
|---|---|---|---|
| D351-1 | P1 | The Workflow Structure parser treated the following `###` subsection as table rows, so the proposed workflow was not executable | FIXED - operating contract moved to its own H2; installed parser and selection policy pass |
| D351-2 | P1 | Recording spawn only after a successful host handle made a crash/tool failure before the return invisible, defeating settlement | FIXED - spawn is append-before-submit and explicitly means committed attempt, not proof of process start |
| D351-3 | P1 | Terminal casualty plus a late first-attempt delivery had no append-only representation, so idempotent at-least-once evidence could be lost or rewritten | FIXED - digest-bound `late-delivery` facts and before/after retry semantics added |
| D351-4 | P2 | `tests/test_execution_spec.py` and an unspecified workflow reference were not live paths | FIXED - replaced with `tests/test_saga_execution_spec.py` and `/work` Phase 1.5 |
| D351-5 | P2 | Release versions and hardcoded version fixtures were vague, and parallel #350 work could collide | FIXED - post-#350 Saga 0.98.0, team-execution 2.17.0, both pinning tests, and serialized merge order are explicit |
| D351-6 | P2 | The workflow claimed named profiles guaranteed read-only workspace access although current V2 may reapply the parent permission profile | FIXED - `mutation=none` is the authorization boundary; root baseline/diff audit fails any child mutation |
| D351-7 | P2 | Frontmatter used `status: proposed`, which is outside the plan artifact's active/completed lifecycle contract | FIXED - plan status is `active`; operator approval remains a separate execution gate |

## Evidence Verified

- `run_ledger.py` explicitly names #351 as a future writer, stores one hash-chained repo ledger, and
  exposes lock-consistent `append_fact_atomic`; existing `kind=reconciliation` has another meaning.
- Team-execution's `worker-manifest.md` defines missing contract-bearing `saga.manifest.v1` as
  missing-output; `artifact_pointer.py` runs after worker completion for diff transfer.
- `/work` Phase 1.5 already makes the driving session the record producer for filesystem-less Workflow
  leaves and persists per-unit completeness after collection.
- Outcome dispatch, orchestrator, worktree registry/reaper, and all named existing test files were
  verified in the live tree.
- Saga is currently 0.96.0 and team-execution 2.16.0; their plugin tests pin both literals. #350's
  required first merge establishes the planned 0.97.0 Saga baseline for #351.
- Workflow digest `4c7114ab6317aad550977f37a0c3992dd9667ee4e57e23d58e750b9b39057848`
  passes the installed role/profile binding and requires both `validate-concurrency` and
  `validate-event-flow`.

## Remaining Findings by Priority

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Residual Risk

The generated-workflow adapter necessarily trusts the driving host's dispatch/result boundary because
workflow leaves cannot write the ledger themselves. The plan fails closed on missing or contradictory
host evidence and preserves the no-filesystem boundary. This review ran inline in the authoring
session; independent concurrency/event-flow validation and later `/code-review` remain mandatory.
