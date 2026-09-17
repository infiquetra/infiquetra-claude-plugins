---
title: Finite test plan — Code Review result and repair-lifecycle integrity from issue 908
type: test
status: active
date: 2026-09-16
origin: GitHub issue 908 and nested children 898, 902, 892, 893, 895, 894, 899, 884, 956, 959, 974, 976
backend: inline
---

# Finite test plan — Code Review result and repair-lifecycle integrity from issue 908

This plan exists before any implementation commit that changes review-result or repair-lifecycle behavior. Every scenario drives a shipped function in `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py` or `plugins/saga/scripts/review_consensus.py`. Tests live in the modules named in each row.

No scenario re-implements the unit under test, mocks `review_slot` / `route_review_result` / `cmd_review_result` / `cmd_status` / `cmd_land` / `record_cycle` / `consolidate_fix_requests`, or starts past the defect.

## Key Technical Decisions

KTD1. Each child's load-bearing case calls the shipped entry point on a representative fixture. Removing the new guard must fail the negative test named in that row.

## Implementation Units

### U1. Finite scenario table

The table below is the executable unit. Implementation of the behaviors it names is the companion plan `docs/plans/2026-09-16-issue-908-review-integrity-plan.md`.

## How to run

```bash
uv run pytest tests/test_orchestrate_scoped_review_controllers.py tests/test_orchestrate_review_loop.py tests/test_orchestrate_status_and_notes.py tests/test_orchestrate_review_transport.py tests/test_orchestrate_land_clean.py tests/test_review_consensus.py tests/test_review_consensus_cycles.py tests/test_review_loop_end_to_end.py -q
```

A scenario is done when the named test calls the shipped function and the assertion matches the expected outcome column. Run the suite twice. Both runs must exit 0 and the new tests must execute, not collect-and-skip.

## Child scenario table

| ID | Issue | Shipped function | Input | Expected outcome | Test |
|---|---|---|---|---|---|
| TP-898 | #898 | `Run.review_slot` | One controller reviewed unscoped so run-level fields hold a typed result; the same controller is then assigned `lifecycle="c2"`; `review_slot` is read. A second case: the named slot already holds a different result. | The four fields (`review_result`, `review_outcome`, `review_resubmit_pending`, `operator_fix_requests`) appear in the named slot as copies, not aliases. A conflicting named-slot result is a `SystemExit` naming the conflict, and neither slot is overwritten. Removing the migrate/conflict guard fails this test. | `test_late_lifecycle_assignment_migrates_run_global_review_state`, `test_late_lifecycle_assignment_refuses_a_conflicting_named_slot` in `tests/test_orchestrate_scoped_review_controllers.py` |
| TP-902 | #902 | `_replacement_name`, `_replacement_worker` | Scoped controller lifecycle `providers`; template is an unscoped worker named `work-shell-slice-shell` with workspace `shell-ws`; the template name already contains `-fix-` (a repair-of-a-repair). | Replacement `name` and `workspace` identify the `providers` lifecycle, not the shell template. The name does not contain a second `-fix-` segment. A note or `serialize` entry still names the template so lineage is recoverable. A single-lifecycle unscoped mint keeps today's stem. Removing the identity rewrite fails this test. | `test_replacement_name_and_workspace_identify_the_controller_lifecycle` in `tests/test_orchestrate_review_loop.py` |
| TP-892 | #892 | `route_review_result` then `dispatch_review_routing` | Role-and-path match is `status=failed` (and a sibling case `orphaned`) with a live pane; no other live match. A second case: a `running` match exists beside a failed one. | The terminal unit is not in `routing.dispatches` and its status is unchanged. A replacement is minted for the request whose only path match is terminal. A live non-terminal match is still reused. `dispatch_review_routing` never sets a terminal unit to `running`. Removing the status predicate fails this test. | `test_route_review_result_skips_terminal_units_and_mints_instead` in `tests/test_orchestrate_review_loop.py` |
| TP-893 | #893 | `cmd_review_result` | Slot already holds `cycle_cap_best_available` with `cycle_history` length 3. Incoming artifact is `accepted` with `cycle_history` length 1 (different bytes). A second case: the same bytes as already stored. A third: a non-terminal slot receiving a shorter `cycle_history` than stored. | Named refusal, slot bytes and outcome unchanged, exit non-zero. Byte-identical replay still returns 0 and dispatches nothing. Cycle-regressed ingest into a non-terminal slot is also a named refusal. Removing the continuity check fails this test. | `test_review_result_refuses_cycle_regressed_overwrite_of_a_terminal_slot` in `tests/test_orchestrate_review_loop.py` |
| TP-895 | #895 | `cmd_status` | Slot has a non-empty `review_result` and `review_outcome is None`. A second case: typed outcome `cycle_cap_best_available` while the controller's `note` contains `ACCEPTED`. | Stdout contains `recorded-but-unrouted` (or the same words with hyphens/spaces as the implementation prints) for the stored result. The typed outcome still prints; the note does not replace it. A contradiction line names that the note disagrees with the typed outcome. Removing the unrouted branch fails the first case. | `test_status_shows_recorded_but_unrouted_result`, `test_status_typed_outcome_outranks_a_contradictory_note` in `tests/test_orchestrate_status_and_notes.py` |
| TP-894 | #894 | `ReviewCycleState.record_cycle` then `ReviewResult.to_json` / `from_json` | Passing lens scores (overall 9.4, every dimension at or above 7.0) plus a P2 `status=active` finding that is not a fix-request candidate (`pre_existing=True` or `autofix_class="advisory"`), so failing lenses and unresolved fix ids are empty. A second case: `repairs_requested` with an active candidate finding. | The accepted result cannot serialize or round-trip with any finding still `active`. `repairs_requested` and `cycle_cap_best_available` may still carry `active` findings. Constructing `ReviewResult` directly in the accepted+empty+active shape raises `ReviewConsensusError`. Removing the result-level check fails this test. | `test_accepted_result_cannot_carry_active_findings`, `test_repairs_requested_may_carry_active_findings` in `tests/test_review_consensus_cycles.py` |
| TP-899 | #899 | `consolidate_fix_requests` via `ReviewCycleState.record_cycle` | Two `ReviewCycleState` values constructed with different lifecycle identifiers, same owner, same autofix class, same finding labels. A second case: the same lifecycle re-derives the same grouped findings on a later cycle. A third: `to_json` / `from_json` of a state that has a lifecycle, then `record_cycle` again on the restored state. | The two lifecycles mint different `fix_id` values. The same lifecycle mints the same `fix_id` across cycles. The restored state mints the same `fix_id` as before the round trip. The function remains a pure hash of its inputs (no clock, counter, or randomness). Unscoped state (no lifecycle argument) keeps today's identity string so existing assertions on grouping still hold. `review_result.v1` gains no new field. Removing the lifecycle component of the identity, or dropping it from cycle-state restore, fails the cross-lifecycle or resume case. | `test_fix_identifiers_differ_across_lifecycles_and_are_stable_within_one` in `tests/test_review_consensus_cycles.py` |
| TP-884 | #884 | `resubmit_review_if_ready` via `cmd_land` | Two scoped controllers. Land a unit that belongs only to lifecycle A. Controller B is `running` on its own frozen target with `review_resubmit_pending` true. Controller A has pending clear repairs. | Controller B is not prompted. Controller A is prompted with the revision that contains A's landed repairs, not merely the run-branch head if those differ. A single-lifecycle run still resubmits after its own repairs land. A lifecycle with no landed repairs in this invocation is not resubmitted. Removing the landed-lifecycle filter fails this test. | `test_land_in_lifecycle_a_does_not_resubmit_a_running_controller_in_lifecycle_b` in `tests/test_orchestrate_review_loop.py` |
| TP-956 | #956 | `resubmit_review_if_ready` | Two scoped controllers both pending and clear. The sender raises `SystemExit("pane run failed")` for the first and succeeds for the second. | The second controller is still prompted. The first is named as skipped. The call surfaces a failure so `cmd_land` can exit 4. A `StagedInputError` on one still withholds only that one (existing test stays green). Catching only `StagedInputError` (today) fails this test. | `test_a_non_staged_resubmit_write_failure_does_not_abort_later_controllers` in `tests/test_orchestrate_review_loop.py` |
| TP-959 | #959 | `cmd_land` | Leftover landing path that is not a proven live linked worktree (the path that currently returns 3) AND a review resubmission that was owed and not made (staged withhold or write failure). | Exit 4, not 3. Cleanup is still reported in stdout. Removing the precedence (return 3 before checking owed resubmit) fails this test. | `test_land_exit_4_outranks_leftover_landing_path_exit_3` in `tests/test_orchestrate_review_loop.py` |
| TP-974 | #974 | `cmd_land` | Scoped or unscoped controller with `review_resubmit_pending` true and non-empty `operator_fix_requests`, no staged-input withhold, no leftover landing path. | Exit 4, not 0. Stdout still names `REVIEW RESUBMISSION HELD`. `test_land_names_the_operator_request_holding_review_resubmission` must be updated so it no longer asserts exit 0. The documented exit-code table in `plugins/orchestrate/commands/orchestrate.md` names operator-hold as a way exit 4 is reached; `test_the_documented_land_exit_codes_are_the_ones_the_command_returns` stays green. | `test_land_exits_4_when_resubmission_is_held_by_operator_fix_requests` in `tests/test_orchestrate_review_loop.py` |
| TP-976 | #976 | `cmd_review_result` | Two live workers. First dispatch succeeds; second raises `StagedInputError`. Retry the same result file against the same run so `route_review_result` rebuilds request dicts and `_park_fix_request` replaces the parked bag. | First worker is not prompted a second time. Second worker is attempted again. `review_outcome` stays unset until every Work request has dispatched or been replaced. The skip is `review_slot()["dispatched_fix_ids"]` (per fix_id, on the controller slot) so it survives re-parking and a different holder. A flag on the request dict or on the worker unit is not coverage. Removing the slot list fails this test. | `test_retrying_review_result_does_not_reprompt_a_worker_that_already_took_its_repair` in `tests/test_orchestrate_review_loop.py` |

## Assertions that must change with the behavior

These currently pin the defects. Leaving them green is not coverage.

| Current assertion | After this issue |
|---|---|
| `test_land_names_the_operator_request_holding_review_resubmission` expects `cmd_land` == 0 | expect 4; the held prose stays |
| `test_the_documented_land_exit_codes_are_the_ones_the_command_returns` reads row 4 as prompt-failed or staged-withheld only | row 4 also names operator-hold; leftover-path row 3 is outranked when 4 applies |
| `cmd_status` skips a slot when `review_outcome` is falsy | a stored result with unset outcome prints recorded-but-unrouted |
| `_replacement_name` always uses `{template.name}-fix-{slug}` | a scoped mint names the lifecycle it serves and does not compound `-fix-` |
| `resubmit_review_if_ready` walks every pending scoped controller with the run-branch head | only controllers whose own lifecycle landed repairs in this invocation, and never a controller already `running` on its frozen target |

## Version-parity scenarios (release unit)

| Test | File | Expected |
|---|---|---|
| Orchestrate metadata | marketplace / plugin contract tests already in this repo | `plugins/orchestrate/.claude-plugin/plugin.json` version equals marketplace `orchestrate` version and is strictly above the 4.4.0 currently on `origin/main`; CHANGELOG has a heading for that version |
| Saga metadata | the same contract tests | `plugins/saga/.claude-plugin/plugin.json` version equals marketplace `saga` version and is strictly above the 0.158.0 currently on `origin/main`; CHANGELOG has a heading for that version |

Re-read both versions from `origin/main` at bump time; go strictly above whatever that read shows.

## Schema non-coverage (must stay identical)

Diff `origin/main` against this branch for the review artifact schema and the `review_result.v1` field set (`plugins/saga/skills/code-review/references/findings-schema.md` and the `ReviewResult` fields in `plugins/saga/scripts/review_consensus.py`). The field set is unchanged. Lens scoring, lens selection, and the consensus protocol (which lenses rerun, cycle cap 3, outcome vocabulary) are unchanged. Fix-identifier *values* may change when a lifecycle is supplied; the `fix_id` field itself stays.

## Explicit non-coverage

- Issue 885 (post-cap closure path) and any child not nested under 908.
- Issues 909 and 910.
- Migrating or rewriting existing run records on disk as a batch.
- Reopening the scoped-controller design settled by issue 877.
- Validation that a finding's cited evidence file exists.
- Removing run-level review mirror fields.
- Changing unscoped backfill, execution-config inheritance from a replacement template, or lifecycle-fallback precedence beyond what #902 requires for name and workspace.
- A fourth `/code-review` scoring cycle.
- Direct push to protected `main`.
- Installing the new versions inside a live Claude Code session.
