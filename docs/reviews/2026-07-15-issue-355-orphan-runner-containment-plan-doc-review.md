# Doc review - orphan runner containment plan (#355)

Verdict: **READY AT OPERATOR GATE** - all issue-rubric, lifecycle, safety, and executable-readiness
findings were fixed in place; zero P0-P3 findings remain. Implementation is intentionally blocked
until #356 is merged and the outcome plus exact Verified Workflow candidate are approved.

## Review-Result Contract

- **Target:** `docs/plans/2026-07-15-issue-355-orphan-runner-containment-plan.md`
- **Reviewed revision:** working tree on `outcome/lease-safe-runtime-continuity`, base
  `a20cc3ce6d74`
- **Blocked status:** document is not blocked; execution is blocked at the explicit operator gates
  and its hard #356 dependency
- **Linked issue:** infiquetra/infiquetra-claude-plugins#355, outcome node `sub-355`
- **Linked outcome:** `docs/outcomes/lease-safe-runtime-continuity/proposal.md` (local review draft)
- **Review artifact:**
  `docs/reviews/2026-07-15-issue-355-orphan-runner-containment-plan-doc-review.md`
- **Override rationale:** none
- **External panel:** not invoked; the panel is opt-in and the operator did not request external egress

## Applied Fixes

The review replaced the issue's terminal `run-lease.json` assumption with #356's single live
authority, assigned stable resource identity to a trusted outer coordinator parameter, closed the
grant-versus-write race with one resource-lock order, aligned quarantine size semantics with agy's
real supervisor boundary, defined claim-to-adjudication renewal and successor takeover, restricted
close seals to terminal generations, prevented valid successor generations from triggering false
late-write alarms, and added explicit issue/spec/dependency/acceptance traceability.

## Issue-Rubric Results

All three core issue rubrics and all applicable extras ran inline. Scores reflect the remediated plan.

| Rubric | Score | Finding | Status |
|---|---:|---|---|
| acceptance criteria clarity | 9 | “stalled or empty,” quarantine limits, and late-after-close lacked exact evidence/lifecycle boundaries | FIXED - explicit output contracts, selector mapping, size boundary, terminal seals, and mixed-run fixtures added |
| devil's advocate | 8 | Three plugin surfaces and six units are broad, but a partial bridge rollout would leave an accepted stale-write bypass while claiming containment | ACCEPTED - one shared disposition core, two thin bridge adopters, read-only projection, and hard sibling exclusions keep the slice cohesive |
| spec fidelity | 9 | The issue's local lease snapshot assumption conflicted with the outcome dependency that gives #356 sole authority | FIXED - #356 owns lease/token/worktree sweep; #355 only consumes dispositions at bridge-evidence seams |
| context completeness | 10 | Trusted caller, live writers, close state, and downstream owners were initially implicit | FIXED - exact functions, files, trust inputs, test paths, authority, and owner mappings are named |
| issue sizing | 7 | The issue spans fleet-core, agy, Saga, conformance, and three release surfaces | ACCEPTED - the cross-plugin contract must land atomically to avoid a falsely safe partial state; #357 liveness and #358 reclamation remain separate |
| prerequisite mapping | 10 | #356 was named, but delivery serialization and downstream unlocks were incomplete | FIXED - hard/transitive dependencies, release-surface serialization, downstream children, and lack of external prerequisites are explicit |
| security and destructive operations | 9 | Untrusted resource keys, unsafe quarantine paths, and a mutating “reaper” could grant or destroy authority | FIXED - outer trusted key, digest/no-follow store, bounded 0600 evidence, and a strictly read-only projector/scan command |

## Readiness Findings

Every P0-P3 readiness finding was fixed in the plan.

| ID | Priority | Finding | Status |
|---|---|---|---|
| D355-1 | P1 | `lease_resource_key` was “caller supplied” without defining whether the untrusted envelope, prompt, environment, or engine could replace it | FIXED - trusted outer CLI/coordinator parameter validated before envelope construction; all untrusted replacement paths are forbidden and tested |
| D355-2 | P2 | The plan said exactly 128 MiB succeeds, while agy's existing supervisor rejects output when the count reaches that boundary | FIXED - quarantine accepts only payloads strictly below 128 MiB and rejects at/above the shared constant |
| D355-3 | P1 | Saga could publish a claim and later adjudicate without a defined lease renewal, release, or legitimate successor-generation path | FIXED - resource stays renewed until terminal adjudication; a later trusted adjudicator intentionally acquires the current successor generation |
| D355-4 | P1 | Sealing the claimed manifest would make the expected adjudication itself look like a post-close mutation | FIXED - claims are intermediate and unsealed; only final adjudication or explicit terminal non-adjudication writes a seal |
| D355-5 | P1 | Comparing every historical close seal would falsely flag a valid retry/successor that changed the same logical artifact | FIXED - only the newest sealed generation without a later head is compared; prior generations become historical |
| D355-6 | P2 | Parent spec, issue-AC mapping, delivery collision, and downstream consumers were distributed across the outcome proposal rather than executable from this plan | FIXED - a local traceability/dependency table now maps every published acceptance to requirements, units, and evidence |

## Evidence Verified

- `agy_delegate.py` currently applies live patches and mirrors result/receipt evidence without a
  renewable lease check; its `run-lease.json` payload is built as terminal bundle material.
- `audit_store.py` already provides the effective machine-local delegation-audit root, atomic 0600
  writes, safe-name checks, and write-once publication patterns that quarantine can extend.
- Saga's `record_dispatch_manifest` and `adjudicate_manifest` are distinct intermediate/final
  read-write seams over `manifest_store.write_manifest`; the plan guards both without treating an
  intermediate claim as closed.
- `outcome_liveness.py` already derives fixed-budget heartbeat stalls; #357 retains advanced shared
  liveness and #358 retains destructive/resource teardown.
- The Workflow Structure has eight steps and digest
  `62d5bff8e79f0330744f250358cbbc6910dcb82a7e31bf1a44f216747932430d`.
  Installed role/profile binding passes, full-review selection passes, and both
  `validate-concurrency` and `validate-event-flow` are required.
- The local outcome spec makes #356 the direct dependency of `sub-355`; the Claude child and #353 are
  downstream consumers.

## Remaining Findings by Priority

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Residual Risk

The resource lock protects Python-owned acceptance seams; it is not a distributed lock or a general
filesystem monitor. A current live patch can succeed before an additive audit mirror fails, so that
run remains an explicit evidence error with no terminal seal rather than pretending the live change
was rolled back. The broad issue remains review-heavy by necessity. Independent concurrency and
event-flow validation, the full Verified Workflow review panel, and later `/code-review` remain
mandatory before merge.
