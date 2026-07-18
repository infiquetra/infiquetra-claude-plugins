# Doc review - fleet-shared liveness engine plan (#357)

Verdict: **READY AT PRE-IMPLEMENTATION GATES**. The merged-#355 baseline refresh has zero
unresolved P0-P3 findings and does not change the approved implementation workflow.

## Review contract

- Target: `docs/plans/2026-07-15-issue-357-fleet-shared-liveness-engine-plan.md`
- Reviewed revision: working tree based on merge commit
  `df70b4ac7359f2eb5aa0e649cff83949656802d6`
- Merged baseline: `a1dc0c2a247fd72e2c5fec723ac1334c511fe7a4` (PR #614)
- Reviewed input digest: `5270503970c4afcf4287bce82af5306d0641e1740fc37bbe764b532362adab89`
- Linked issue: `infiquetra/infiquetra-claude-plugins#357`; outcome node `sub-357`
- Blocked: no
- Override rationale: none

## Applied fixes

- Corrected the baseline to merged #355 and recorded the true merge-parent relationship.
- Corrected release sequencing to fleet-core 0.13.0 -> 0.14.0, Saga 0.100.0 -> 0.101.0,
  and team-execution 2.19.0 -> 2.20.0.
- Reclassified #355 as a merged release-surface sibling and ownership boundary, not an API
  prerequisite.
- Corrected the `{#fleet-shared-liveness-357}` journal anchor so digest activity cannot imply
  resident progress without trusted exclusive provenance.
- Removed the stale pre-PR rebase instruction. The gate now verifies merged ancestry and release
  metadata directly.

These are baseline and evidence corrections. They do not alter requirements R1-R14, user outcomes
U1-U6, implementation ownership, acceptance tests, or the approved Verified Workflow graph.

## Readiness summary

| Rubric | Score | Result |
|---|---:|---|
| Acceptance criteria clarity | 10/10 | R1-R14 and U1-U6 define pass/fail thresholds, negative paths, and named executable evidence. |
| Devil's advocate | 9/10 | The PR is broad but remains one tightly coupled engine, two adapters, and one atomic release; splitting it would create dead wiring or duplicate authority. |
| Spec fidelity | 10/10 | The plan traces the parent outcome and `sub-357`, preserves exact R31 authority, and excludes #355/#356/#358 ownership. |
| Context completeness | 10/10 | Production files, precedents, contracts, polling boundaries, tests, and release surfaces are named. |
| Issue sizing | 8/10 | Large but independently reviewable as one shared engine and its production consumers; no unrelated capability is included. |
| Prerequisite mapping | 10/10 | #351/#356/#355 are merged, #358 and #353 remain downstream, and no external credential or deployment prerequisite exists. |

Overall: **9.5/10, accept**. Remaining findings: P0 0, P1 0, P2 0, P3 0.

## Finding closure

| ID | Status | Closure |
|---|---|---|
| `D357-1` | CLOSED | One fleet-core engine; Saga owns adapters; Team invokes the canonical Saga CLI. |
| `D357-2` | CLOSED | Scoped Git changes remain unattributed without an exclusive-provenance receipt. |
| `D357-3` | CLOSED | Phi creates suspicion only; only three proven-send windows can confirm a Team stall; #357 owns no teardown. |
| `D357-4` | CLOSED | Outcome keeps its heartbeat-first legacy fixed-gap and absolute-timeout authority. |
| `D357-5` | CLOSED | Clock skew, rollback, nonfinite, and negative values have explicit clamp/error behavior. |
| `D357-6` | CLOSED | Notice identity uses trusted host identity or a lock-allocated subject-local sequence. |
| `D357-7` | CLOSED | Source-aware conformance covers fleet-core and both production consumers. |
| `D357-8` | CLOSED | Every cooperative polling boundary, adapter, hook, and production-path test is named. |
| `issue-357.r31-terminal-authority` | CLOSED | Adapter-specific authority preserves exact R31 reasons, idempotency, and cascade. |
| `issue-357.reping-send-proof` | CLOSED | Intent, accepted send, definitive non-send, unresolved send, and acknowledgment are separate facts. |
| `issue-357.suspicion-generations` | CLOSED | Cause/anchor-stable generations cannot be rotated by unrelated signals. |
| `issue-357.subject-identity-schema` | CLOSED | Closed canonical identity and append-lock validation reject drift and cross-subject evidence. |
| `issue-357.progress-attribution` | CLOSED | Digest activity cannot update progress; only trusted exclusive provenance can. |
| `issue-357.reping-definitive-failure-retry-contract` | CLOSED | Exactly one predecessor-bound definitive-not-sent retry is permitted; unresolved or exhausted delivery never counts or confirms. |
| `issue-357.progress-reachability-closure` | CLOSED | Only explicitly named generations close, and only when the complete trusted provenance interval is after the generation/send anchor. |

## Evidence and gates

- Merge commit `df70b4ac7359f2eb5aa0e649cff83949656802d6` has both the prior #357 head and
  merged PR #614 head `a1dc0c2a247fd72e2c5fec723ac1334c511fe7a4` as parents.
- Live manifests report fleet-core 0.13.0, Saga 0.100.0, and team-execution 2.19.0.
- The phi equation, five-interval cold start, exact threshold, event identity, recovery paths,
  attributed-progress boundary, and Outcome compatibility all have named executable tests.
- `git diff --check` passes after the baseline and journal corrections.
- Verified Workflow recompilation produced the approved workflow digest
  `4e993a3e3e4a9ce6b953995fdc5d58e74d7be26da2304e95d342d373a7d230b3` and selection-policy
  digest `cf0f2f5016a17d934f0c40f36d2410597ac1ebb8c8cf00df280c09d3b0caa67c`. Both are
  digest-identical to the operator-approved candidate, so approval carries without a graph change.

## Residual risk

Phi thresholds remain policy choices over local cadence and may need later telemetry-based tuning.
Polling is cooperative because the host exposes no always-on plugin daemon. #356 prevents a stale
worker's next mutation, while #358 owns later destructive reclamation.
