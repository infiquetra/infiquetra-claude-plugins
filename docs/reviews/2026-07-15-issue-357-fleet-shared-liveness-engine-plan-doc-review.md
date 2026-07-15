# Doc review - fleet-shared liveness engine plan (#357)

Verdict: **READY AT OPERATOR GATE** - all issue-rubric, lifecycle, safety, and executable-readiness
findings were fixed in place; zero P0-P3 findings remain. Implementation is intentionally blocked
until #351/#356 are merged and the outcome plus exact Verified Workflow candidate are approved.

## Review-Result Contract

- **Target:** `docs/plans/2026-07-15-issue-357-fleet-shared-liveness-engine-plan.md`
- **Reviewed revision:** working tree on `outcome/lease-safe-runtime-continuity`, base
  `a20cc3ce6d74`
- **Blocked status:** document is not blocked; execution is blocked at explicit operator gates and
  hard #351/#356 dependencies
- **Linked issue:** infiquetra/infiquetra-claude-plugins#357, outcome node `sub-357`
- **Linked outcome:** `docs/outcomes/lease-safe-runtime-continuity/proposal.md` (local review draft)
- **Review artifact:**
  `docs/reviews/2026-07-15-issue-357-fleet-shared-liveness-engine-plan-doc-review.md`
- **Override rationale:** none
- **External panel:** not invoked; the panel is opt-in and the operator did not request external egress

## Applied Fixes

The review moved the shared algorithm to fleet-core, reused #351's run-fact ledger and #356's trusted
resident/clock identity, converted phi from a statistical kill switch into capability-gated suspicion
plus bounded confirmation, preserved unsupported Outcome backends' fixed-gap behavior, replaced
whole-worktree pointer appearance with baseline-relative declared-path digests, separated idle ack
from output delivery, added locked notice sequencing and re-ping transitions, bounded clock skew and
sample history, and made every team poll boundary executable and source-inventoried.

## Issue-Rubric Results

All three core issue rubrics and all applicable extras ran inline. Scores reflect the remediated plan.

| Rubric | Score | Finding | Status |
|---|---:|---|---|
| acceptance criteria clarity | 9 | Phi thresholds/confirmation, “artifactless,” and idle acknowledgment lacked exact pass/fail transition and trust semantics | FIXED - committed policy constants, closed decisions/events, scoped progress, ack meaning, selectors, and scenario evidence added |
| devil's advocate | 8 | Statistical scoring, artifact progress, notifications, two consumers, and release work are broad, and each could become a separate subsystem | ACCEPTED - one pure engine, existing ledgers, thin adapters, no daemon/queue/teardown, and six dependency-ordered units bind one detection contract |
| spec fidelity | 9 | The issue predates #351/#356 and proposed a Saga-local shared module plus pointer presence as progress | FIXED - fleet-core is canonical; #351 owns facts/delivery, #356 identity/TTL, #355 fencing, and #358 actions |
| context completeness | 10 | Current team protocol, artifact-pointer timing, lack of generic Outcome re-ping transport, and installed module bus were load-bearing | FIXED - exact files/functions/call boundaries, compatibility paths, tests, and release baselines are named |
| issue sizing | 7 | Three plugins, a statistical core, event transitions, pointer inspection, and release surfaces exceed a typical small PR | ACCEPTED - splitting would permit duplicate algorithms or dead consumers; action/teardown and delivery/retry remain separate issues |
| prerequisite mapping | 10 | #351/#356 were implicit in the stale issue and #355 shares the Wave 3 release base | FIXED - hard/transitive dependencies, serialized expected versions, downstream #358/#353/runtime children, and no external prerequisites are explicit |
| security and destructive operations | 9 | Untrusted clocks/IDs/paths or a raw phi score could falsely grant health or destructive authority | FIXED - trusted host/resource identity, bounded skew, safe path digests, evidence-error state, root-only probes, and no destructive action |

## Readiness Findings

Every P0-P3 readiness finding was fixed in the plan.

| ID | Priority | Finding | Status |
|---|---|---|---|
| D357-1 | P1 | A Saga-local “shared” module would force team-execution to import a sibling plugin implementation or copy it, contradicting the fleet-commons distribution decision | FIXED - pure engine lives in fleet-core; Saga owns its existing ledger adapters and team invokes the one canonical adapter CLI |
| D357-2 | P1 | Existing artifact pointers appear only after all workers and cover the whole worktree, so pointer presence/epoch could credit a chatty worker for another worker's changes | FIXED - trusted baseline-relative digest over disjoint declared paths; overlap/no contract falls back to heartbeat-only |
| D357-3 | P1 | Phi threshold alone could terminalize a noisy but live local worker and cascade/delete downstream work | FIXED - phi is suspicion; armed transport requires bounded host-correlated confirmation, and #357 has no teardown authority |
| D357-4 | P1 | Not every Outcome backend exposes a trusted re-ping/ack transport; replacing fixed heartbeat logic would make rich-history leaves either unsafe or immortal | FIXED - current unarmed Outcome path surfaces phi advisory evidence while retaining the exact fixed-gap/timeout terminal; adaptive confirmation is capability-gated |
| D357-5 | P2 | Future/nonfinite timestamps were described as discarded while the safety contract said invalid clocks are evidence errors | FIXED - five-second trusted skew clamp is explicit; beyond-tolerance, rollback, nonfinite, and negative time produce non-terminal `evidence-error` |
| D357-6 | P1 | Idle notice identity was unspecified when the host supplies no event ID, allowing message text or racing writers to invent identities/attempt counts | FIXED - subject-local sequence is allocated under the run-ledger lock from normalized host metadata; message text is excluded |
| D357-7 | P2 | The published grep searches only Saga/team-execution, so moving the canonical engine to fleet-core could produce zero/one misleading matches and falsely pass | FIXED - plan requires issue amendment and source-aware fleet-core plus both-consumer conformance before work |
| D357-8 | P1 | Team-execution is skill-driven and has no daemon, so a library plus prose could ship with no production poll | FIXED - exact pre-wave, assignment, lease-renewal, host-event, dependency-unblock, and pre-review CLI boundaries are inventoried and production-tested |

## Evidence Verified

- `outcome_liveness.py` derives dispatch/heartbeat facts, floors activity at dispatch, uses the
  timestamp maximum, writes one sticky `stalled` event, and cascades R22 through the production
  processor in `outcome.py`.
- Team-execution B1 currently has resident workers and one post-worker review snapshot but no
  heartbeat/idle/stalled/re-ping implementation or background poller.
- `artifact_pointer.py snapshot` is a whole-tree temp-index snapshot; its existing pointer is a
  review transfer artifact, and #351's reviewed contract explicitly forbids treating it as delivery.
- `run_ledger.py` is the canonical hash-chained repo-level fact stream; #351 adds dispatch settlement,
  while #356's reviewed contract supplies 300-second leased residents and boot-aware monotonic time.
- The original phi-accrual report defines a continuous late-arrival suspicion score rather than a
  direct resource action: https://dspace.jaist.ac.jp/dspace/handle/10119/4784
- The Workflow Structure has eight steps and digest
  `4e993a3e3e4a9ce6b953995fdc5d58e74d7be26da2304e95d342d373a7d230b3`.
  Installed role/profile binding passes, full-review selection passes, and both
  `validate-event-flow` and `validate-scenarios` are required.

## Remaining Findings by Priority

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Residual Risk

Phi defaults are policy choices over local agent cadence, not universal truths; the plan makes them
explicit, bounded, and testable but real-run telemetry may justify later tuning through `/optimize`.
Team polling remains cooperative at protocol boundaries because the host exposes no always-on plugin
daemon. A single in-flight tool can outlive both poll and lease periods; #356 blocks its next mutation,
and #358 later owns teardown. Independent event-flow/scenario validation, the full review panel, and
later `/code-review` remain mandatory before merge.
