---
title: Code review — issue 908 review-result and repair-lifecycle integrity
type: code-review
status: accepted
date: 2026-09-16
reviewed_revision: 8dbfc416147f09118cea0c4ee727039bc016f2bb
cycle: 1
outcome: accepted
plan: docs/plans/2026-09-16-issue-908-review-integrity-plan.md
---

# Code review — issue 908 review-result and repair-lifecycle integrity

Cycle 1 accepted. Every selected always-on lens `accepted`, applicable-dimension floor met, `derived_overall >= 9.0`. No remaining P0 or P1. `cycle_history` length is 1.

## Scope check

CLEAN. Orchestrate review-slot, replacement identity, terminal routing, ingest continuity, status, resubmit, land-exit, dispatch-once; Saga accepted-result consistency and fix-id namespacing; tests in the named modules; SKILL.md / orchestrate.md; Orchestrate 4.5.0 and Saga 0.159.0 release triad; journal. `review_result.v1` field set unchanged. `review_cycle_state.v1` gains optional `lifecycle`.

## Plan completion

| ID | State | Evidence |
|---|---|---|
| U1 | DONE | `ReviewResult` refuses accepted+empty+active; `record_cycle` reconciles; `test_accepted_result_cannot_carry_active_findings` |
| U2 | DONE | `lifecycle=` on `ReviewCycleState`, round-trip, SKILL.md construction sentence; `test_fix_identifiers_differ_across_lifecycles_and_are_stable_within_one` |
| U3 | DONE | `_migrate_run_global_review_state`; conflict stop; `test_late_lifecycle_assignment_*` |
| U4 | DONE | `_replacement_name` lifecycle-first `-repair-`; workspace `{lifecycle}-repair`; `test_replacement_name_and_workspace_identify_the_controller_lifecycle` |
| U5 | DONE | `_unit_is_terminal`; reusable/assigned/dispatch skip; `test_route_review_result_skips_terminal_units_and_mints_instead` |
| U6 | DONE | `_review_ingest_refusal`; `test_review_result_refuses_cycle_regressed_overwrite_of_a_terminal_slot` |
| U7 | DONE | `recorded-but-unrouted`; note contradiction line; status tests |
| U8 | DONE | landed_names filter, skip `running`, `SystemExit` per controller; tests 884 and 956 |
| U9 | DONE | exit 4 before 3; operator-hold is 4; documented table; tests 959 and 974 |
| U10 | DONE | `dispatched_fix_ids` on the slot; `test_retrying_review_result_does_not_reprompt_a_worker_that_already_took_its_repair` |
| U11 | DONE | Orchestrate 4.5.0, Saga 0.159.0, marketplace and CHANGELOG parity |

## Lenses

Always-on four. Conditionals not launched (always-on-only for this bounded defect repair).

| Lens | cycle | derived_overall | accepted |
|---|---:|---:|:---:|
| architecture-maintainability | 1 | 9.5 | yes |
| correctness | 1 | 9.5 | yes |
| security | 1 | 9.5 | yes |
| testing | 1 | 9.5 | yes |

## Findings

None at P0–P3 after cycle 1.

Residual, not scored: `run_global_linked` is extra slot state, not a `review_result.v1` field. An existing scoped run whose named slot and leftover run-level bytes differ and which has never been linked will `SystemExit` on first `review_slot` read; that is the conflict stop #898 asked for, and it is the rare mixed leftover, not the late-assignment empty-slot path.

## Independent gates

- Named pytest modules twice: 256 passed then 256 passed. Fourteen load-bearing new tests all executed and passed.
- `review_result.v1` field set unchanged versus `origin/main`.
- Built-vs-planned: all eleven units DONE.

Typed result: `docs/code-reviews/2026-09-16-issue-908-review-integrity-cycle1-result.v1.json`
