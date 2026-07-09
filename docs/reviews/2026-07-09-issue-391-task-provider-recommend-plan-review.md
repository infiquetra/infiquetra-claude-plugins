# Doc Review: Task Provider Recommendation Primitive - Issue #391

The plan is ready for implementation after two safe in-place fixes that pinned ambiguous recommendation defaults.

## Applied Fixes

| ID | Priority | Status | Fix |
| --- | --- | --- | --- |
| DR-001 | P1 | Applied | Added the default sufficient capability floor: `MODERATE` or stronger, preserving the existing resolver's WEAK-as-no-fit behavior. |
| DR-002 | P1 | Applied | Added the v1 `cheapest-viable` price key: `input_usd + output_usd`, with `cost_speed_rank` and `registry_order` tie-breaks. |

## Readiness Summary

The issue is `requirements-ready` and the plan now carries the load-bearing HOW decisions needed for implementation: a separate advisory `engine_recommend.py`, explicit `egress_policy`, registry-backed candidate sourcing, viability-before-policy ordering, sensitive-task empty/halt behavior, and release-surface synchronization.

The plan maps the issue's key acceptance facets into requirements and units, names concrete files, names focused tests, and keeps dispatch/gate behavior out of scope.

## Findings

| Priority | Status | Finding |
| --- | --- | --- |
| P0 | None | No P0 findings. |
| P1 | None | No unresolved P1 findings after DR-001 and DR-002. |
| P2 | None | No P2 findings requiring remediation before `/work`. |
| P3 | None | No P3 polish findings worth delaying the loop. |

## Rubric Notes

Issue-phase rubrics consulted: `acceptance_criteria_clarity`, `spec_fidelity`, and `devils_advocate_issue`.

The plan addresses the acceptance-criteria clarity risk by naming test files and specific ranking, egress, protocol, and side-effect scenarios. It addresses spec fidelity by carrying forward the issue's source context and by explicitly deferring lifecycle skill integration instead of smuggling it into this PR.

## Review Contract

| Field | Value |
| --- | --- |
| Target path | `docs/plans/2026-07-09-issue-391-task-provider-recommend-plan.md` |
| Reviewed revision | Working tree on `work/391-recommend-routing` |
| Linked issue | `https://github.com/infiquetra/infiquetra-claude-plugins/issues/391` |
| Blocked status | Not blocked |
| Finding priorities and statuses | DR-001 P1 applied; DR-002 P1 applied; no unresolved P0/P1 |
| Applied fixes | Capability floor and cheapest-viable price key added to plan and decision record |
| Review artifact path | `docs/reviews/2026-07-09-issue-391-task-provider-recommend-plan-review.md` |
| Override rationale | None |
| Next route | `/work docs/plans/2026-07-09-issue-391-task-provider-recommend-plan.md` |

## Residual Risk

The plan intentionally does not wire `recommend()` into lifecycle command UX. Implementation review should verify that no caller starts depending on the helper before its result contract is tested.
