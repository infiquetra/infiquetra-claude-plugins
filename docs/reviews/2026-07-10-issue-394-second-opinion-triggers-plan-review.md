# Issue #394 Second-Opinion Triggers Plan Review

All P0-P3 readiness findings were fixed in place. Work-start source grounding then corrected one additional
P1 durability gap. The operator had already settled the remaining execution choice:
the plan is ready to run as a root-owned native Codex DAG with Saga `inline`, not as a Claude-style Agent
Team.

## Review Result

| Field | Value |
| --- | --- |
| Target path | `docs/plans/2026-07-10-issue-394-second-opinion-triggers-plan.md` |
| Reviewed revision | `46fefb6` baseline plus review fixes, native-DAG amendment, and work-start durability correction |
| Linked issue | `infiquetra/infiquetra-claude-plugins#394` |
| Linked saga | `issue-394` (`.claude/saga/sagas/issue-394/`) |
| Blocked status | no |
| Finding priorities and statuses | 6 P1, 5 P2, and 2 P3; all fixed; no unresolved P0-P3 |
| Override rationale | No finding override; the operator's native-DAG backend choice replaces the shape recommendation. |
| Work-session path | none; implementation has not started |
| Review artifact path | `docs/reviews/2026-07-10-issue-394-second-opinion-triggers-plan-review.md` |

## Applied Fixes

The revised plan closes every rubric and readiness finding without expanding #394 beyond its three trigger
paths.

| ID | Priority | Status | Applied fix |
| --- | --- | --- | --- |
| F1 | P1 | fixed | Replaced contradictory whole-failure-set reset language with target-specific three-fix streaks: passes reset all targets, absence resets one target, reruns cannot advance, incidental failures do not hide a persistent file, and the lexical first target wins. |
| F2 | P1 | fixed | Defined the live ownership boundary: `second_opinion.py` coordinates typed state; the Markdown stage remains the chaperone and invokes the existing `codex:delegate`, `agy:delegate`, or generic HTTP wrapper through the host surface. Cross-plugin imports, raw CLIs, and a new transport are forbidden. |
| F3 | P1 | fixed | Replaced prose-only programmatic handoff with a closed `external_opinion` state/field contract on the selected finding, plus a closed Claude adjudication/final-status contract that `/work` consumes before the existing `Review complete` terminator. |
| F4 | P1 | fixed | Added a bounded single-finding context package, explicit sensitivity criteria, provider/egress disclosure, and `engine_recommend` local-only filtering. The current all-networked registry now yields a visible unavailable result for sensitive input instead of silent egress. |
| F5 | P1 | fixed | Corrected the hostile-output expectation: gate-shaped top-level runner fields reject, but the same words inside typed opinion prose remain escaped opaque data and cannot execute, choose paths, or set verdicts. |
| F6 | P2 | fixed | Removed unsupported late-result semantics. Version 1 remains synchronous within existing wrapper timeouts; timeout/halt/unavailable proceeds, and callbacks, polling, and late-result ingestion are explicitly out of scope. |
| F7 | P2 | fixed | Defined `saga.work-second-opinion.v1`, its file name, fields, disposition vocabulary, atomic writes, exact 64-attempt/256-target caps, stable epoch-based offer key, and fresh-process resume behavior. |
| F8 | P2 | fixed | Pinned idempotent durability ordering: stable request ID, ready reconciliation, `reconcile` fact, atomic enriched-artifact/sidecar write, matching `available` claim, then `apply`; programmatic review delegates the durable write/apply transition to `/work`. |
| F9 | P2 | fixed | Added source-acceptance-to-R/U/test traceability and justified the 18-file one-PR shape as one indivisible Saga behavior plus tests, release triad, trust-boundary record, and journal entry. |
| F10 | P2 | fixed | Preserved the 18-file/5-unit shape recommendation as `team-execution` evidence, then recorded the operator's explicit override: Saga remains `inline` while the root Codex thread executes U1 -> {U2, U3, U4} -> U5 with bounded native children, one shared-worktree writer, and root-owned acceptance. No Team Structure or Team Execution receipt is required. |
| F11 | P3 | fixed | Named immutable verification via `dataclasses.replace`, exact offer text, exact field/enumeration names, deterministic doc-review finding order, and quantitative input/output caps. |
| F12 | P3 | fixed | Aligned implementation verification with repository CI: added plugin/marketplace/registry validation and focused hostile-output/egress/receipt tests, made scoped Bandit blocking, and documented repository-wide Bandit as informational rather than an impossible hard gate. |
| F13 | P1 | fixed | Work-start grounding proved that stable IDs alone cannot prevent a duplicate external wrapper call after a crash between runner return and durable artifact persistence. Added an atomic pre-dispatch `requested` claim, matching-digest conflict rule, unavailable-on-uncertain-retry behavior, idempotent reconcile/artifact/available/apply recovery, conservative sensitive-content classification, canonical full-context and field caps, validated reviewer wrapper role propagation, and the trust-boundary update. |

## Operator-Directed Execution Amendment

The post-review execution change resolves F10's deferred choice without changing issue #394's product scope,
implementation units, files, or acceptance criteria. It adopts the Codex-native pattern approved in
`infiquetra-codex-plugins@3f63910`: Saga records `inline`; the root owns lifecycle, barriers, integration,
Git, and final gates; ordinary Codex child threads receive bounded U-ID exploration, write, review, or
validation tasks.

The focused re-review found no new P0-P3 issue. The graph records only hard dependencies, keeps U2/U3/U4 on
one ready frontier after U1, treats shared-file serialization as a scheduler constraint, and opens U5 only
after all three consumers pass. The plan also defines dirty-worktree snapshots, one-writer ownership,
fresh-context review, child evidence limits, serial fallback, and root-only release handoff. These controls
replace the stale backend-confirmation gate; they do not create a Team Structure or let the second-opinion
feature under construction accept itself.

## Work-Start Durability Correction

The initial KTD9 ordering began at wrapper dispatch, but current `engine_dispatch` telemetry does not record
execution IDs or opinion bytes and #393 reconciliation facts begin only after the wrapper returns. A crash in
that interval could not distinguish a safe retry from a duplicate call. The amended plan instead claims the
stable request in the review artifact or work sidecar before dispatch; a resumed unresolved claim becomes
visible unavailable and never replays the wrapper. Once a ready result exists, `reconcile` precedes the
atomic raw-opinion artifact, which precedes the `available` claim and `apply`; only the latter two transitions
can resume without the raw result. This preserves the issue's synchronous, no-polling scope without adding a
transport, executor, or raw-output ledger.

## Formal Issue-Phase Rubrics

All core rubrics and all three applicable extras pass after remediation.

| Rubric | Result | Evidence |
| --- | --- | --- |
| `acceptance_criteria_clarity` | pass | Nine requirements, the source traceability table, exact one-line offer, closed states/statuses, quantitative caps, and per-unit positive/negative/integration scenarios give each source AC an observable pass/fail artifact. |
| `devils_advocate_issue` | pass | The plan reuses #451/#393/#385/#391/#476 and adds one trigger contract; it explicitly rejects a new transport, schema unification, async delivery, telemetry, and adjacent lifecycle stages. |
| `spec_fidelity` | pass | `T1-F3-8`, `T1-F6-7`, `T1-F5-1`, advisory-only constraints, and release obligations map directly to requirements, units, and tests; the issue's non-goals remain intact. |
| `context_completeness` | pass | Each unit names concrete source/test files, current call sites, wrapper ownership, context/data contracts, failure behavior, persistence ordering, verification commands, and its root-owned DAG execution rule. |
| `issue_sizing` | pass | Eighteen files exceed the usual caution threshold but remain one plugin/one behavior: nine runtime/contracts, five tests, three required release surfaces, and one journal record. Splitting would ship dead wiring or an incomplete source AC. |
| `prerequisite_mapping` | pass | Live/current source confirms #451, #393, #385, #391, and #476 are available; #283/#318 remain binding; no external/infra/team prerequisite remains; #394 is the only open leaf under #336. |

## Readiness Summary

The plan can safely guide an unfamiliar implementer without inventing trigger state, reset rules, envelope
fields, egress policy, wrapper ownership, verdict authority, crash ordering, or execution topology. The
review gate is clear: no unresolved P0, P1, P2, or P3 findings remain.

## Remaining Findings

No unresolved findings remain.

| Priority | Status | Finding |
| --- | --- | --- |
| P0 | none | No destructive or unsafe plan instruction remains. |
| P1 | none | No implementation-blocking assumption, mapping, state contract, or gate ambiguity remains. |
| P2 | none | No meaningful rework-risk ambiguity remains. |
| P3 | none | No actionable clarity or verification polish remains. |

## Residual Risk

This is a plan-only review: the helper, role propagation, sidecar, enriched finding records, and fixtures do
not exist yet. Sensitive second-opinion requests intentionally remain unavailable while the registry has no
eligible `local-only` row, and actual wrapper behavior still requires implementation/QA evidence through the
focused and full gates listed in the plan. Native child role, isolation, and read-only labels are execution
requests rather than acceptance proof, so the root must verify the worktree and evidence after each wave.

The optional cross-family external-reviewer panel was not invoked; every adopted finding was instead
verified against current repository source, live GitHub prerequisite state, and the formal rubric set.

## Work Handoff

Document readiness no longer blocks issue #394. `/work issue-394` should execute the plan's root-owned
U1 -> {U2, U3, U4} -> U5 Codex DAG with the API hard-test gate; the operator has already settled the backend
choice as Saga `inline`, so no Team Execution confirmation remains.
