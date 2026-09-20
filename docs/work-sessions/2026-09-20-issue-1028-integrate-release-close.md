# Issue 1028 — integrate, release, functional test, close, and the six board moves

**Branch:** `issue/1028`, from `origin/parent/1018` at `87a5329e`, merged with `origin/parent/1018`
at `23959a80` (issue 1029's continuation mechanics).

**Plan:** `docs/plans/2026-09-20-issue-1028-integrate-release-functional-test-close-plan.md`
**Document review:** `docs/reviews/2026-09-20-issue-1028-plan-doc-review.md` — three rounds, no P0
or P1 open.

**Code review:** none for this card, by operator decision on 2026-09-19. The parent pull request
carries one review for the whole parent; this card proves itself with tests, the full suite and the
merge onto the integration branch.

## What shipped

| Unit | What it is |
|---|---|
| U1 | `plugins/fleet-core/scripts/fleet_commons/merge_guard.py` — the shared never-revert-a-newer-branch guard |
| U2 | `plugins/saga/scripts/merge_turn.py` — one worker merges at a time, over the run record |
| U3 | `board_progression.py` — the lifecycle-boundary interface plus allowed-list enforcement |
| U4 | the effort ledger removed; three ledgers deferred to issue 1030 and recorded |
| U5 | the orchestrate board-writeback path removed (about 850 lines) |
| U6 | the work, QA and retro skills |
| U7 | release surfaces: saga 0.170.0, orchestrate 5.1.0, fleet-core 0.29.0 |
| U8 | `plugins/saga/scripts/release_step.py` — the release, the functional test, the close |

## Choices, and where each answer came from

Every choice the work skill would put to an operator was answered in advance by the run driver's
continuation message of 2026-09-20; none was invented here, and none fell in the production,
destructive, credential, permission, billing, external-commitment or process-authority categories.

| Choice | Answer | Source |
|---|---|---|
| Saga resume versus mint | resume `issue-1028` from this worktree's store | the driver's message |
| Branch | stay on `issue/1028` | the driver's message |
| Execution backend | `inline` | the plan's `backend:` frontmatter, per the driver |
| Doc-review gate | passed, nothing above P3, no override needed | `docs/reviews/2026-09-20-issue-1028-plan-doc-review.md` |
| Complexity triage | fresh build, not a round-N re-entry | the skill's documented default; there is no pull request for this card |
| Ship ceremony start | declined | the driver's message: the ceremony opens a draft pull request and this card opens none |
| Board moves | the build-start boundary, once, through the new module | the driver's message |
| Code review | none | operator decision, 2026-09-19 |
| Versions | next minor above `origin/parent/1018` at 23959a80 | the driver's message |

## The board move, and the boundary dry runs

One real move, through the new module, at the build-start boundary:

```
{"status": "written", "boundary": "build-start", "stage": "Active",
 "op_kind": "set-field-status", "repo": "infiquetra/infiquetra-claude-plugins", "number": 1028,
 "target_state": "Implementing", "field": "Stage+Status",
 "key": "set-field-status:infiquetra/infiquetra-claude-plugins#1028:Stage+Status:Active+Implementing",
 "attempts": 1}
```

`field` reads `Stage+Status`, so both halves landed. The plan stage submitted the other two real
moves, `Planning`/`Designing` and `Planning`/`Ready for Active`, each `written` with the same paired
field and one attempt.

The remaining boundaries were exercised as dry runs only; all six outputs are quoted in the driver's
return.

## The deleted writeback test modules, by name

`tests/test_orchestrate_board_writeback.py` carried **56** tests and
`tests/test_orchestrate_status_map_contract.py` carried **10**. Both pinned behaviour that no longer
exists: the schema-vocabulary resolution, the rung mapping, the announcement bodies, the writeback
failure reporting and the `announce` subcommand. Recorded here so a later reader can tell a deleted
guard from a lost one.

The 56 from the writeback module: `test_store`, `test_the_default_prefixes`,
`test_the_bare_prefix_is_a_unit_name_too`, `test_matching_stops_at_a_word_boundary`,
`test_the_status_map_overrides_key_by_key`, `test_a_specific_name_beats_a_shorter_prefix`,
`test_a_pre_pair_string_override_fails_loud`, `test_the_defaults_never_leave_the_live_vocabulary`,
`test_the_rungs_never_move_a_card_backwards`, `test_no_rung_reaches_verify_or_retro`,
`test_no_retired_token_survives_in_the_module`, `test_issue_refs_split_into_repo_and_number`,
`test_land_merges_but_writes_nothing`, `test_announce_is_a_noop`,
`test_a_run_file_from_before_the_field_still_loads`, `test_one_status_set_and_one_comment`,
`test_the_arguments_carry_the_issue_and_both_halves_of_the_rung`,
`test_the_status_map_overrides_what_lands`, `test_a_rung_the_board_does_not_carry_fails_loud`,
`test_a_pre_pair_override_fails_loud_rather_than_half_writing`,
`test_an_unresolvable_schema_fails_loud_on_stderr`,
`test_a_saga_too_old_to_execute_the_pair_is_caught`,
`test_a_pair_aware_saga_records_the_identity_orchestrate_expects`,
`test_an_unmapped_prefix_announces_nothing`,
`test_a_malformed_issue_ref_is_loud_and_never_fatal_to_the_merge`,
`test_announcing_the_same_boundary_twice_posts_one_comment`,
`test_a_second_land_writes_nothing_new`, `test_land_succeeds_and_says_so_on_stderr`,
`test_announce_succeeds_too`, `test_the_env_override_points_at_the_script`,
`test_a_missing_env_override_is_not_importable`, `test_the_repo_layout_resolves_without_any_env`,
`test_a_corrupt_schema_falls_through_rather_than_raising`,
`test_a_schema_with_the_wrong_shape_resolves_to_nothing`,
`test_installs_are_ordered_by_version_not_by_string`,
`test_a_newer_install_in_a_later_root_outranks_a_stale_one_in_an_earlier_root`,
`test_the_company_plugin_root_is_searched`, `test_a_failure_reason_is_printed_not_just_its_status`,
`test_the_retry_door_is_named_only_when_a_retry_can_clear_it`,
`test_a_run_file_override_cannot_submit_an_unobservable_stage`,
`test_the_override_is_a_live_rung_so_liveness_alone_would_have_passed_it`,
`test_a_retired_prefix_fails_loudly_rather_than_going_quiet`,
`test_an_explicit_override_of_a_retired_key_is_still_judged_on_its_merits`,
`test_announce_exits_two_when_a_writeback_fails`,
`test_announce_exits_zero_when_the_writeback_converges`,
`test_converged_statuses_is_exactly_the_three_that_mean_the_board_moved`,
`test_a_halt_or_a_gate_never_names_the_retry_door`,
`test_an_ordinary_failure_still_names_the_retry_door`,
`test_the_outer_timeout_exceeds_sagas_own_worst_case`, `test_the_declared_saga_floor` and the
remainder recorded in the deletion commit's diff.

The 10 from the status-map pin: `test_codereview_does_not_map_to_verify`,
`test_no_rung_reaches_the_verify_stage_by_any_door`, `test_the_landed_rung_is_retired`,
`test_the_map_carries_exactly_the_announcing_prefixes`,
`test_every_rung_is_a_live_stage_status_pair`, `test_the_rungs_are_stage_monotonic`,
`test_no_rung_reaches_the_retro_stage_either`, `test_the_hard_coded_ladder_is_gone`, and two
fixtures beside them.

## Two things the operator should see

1. **The card's second acceptance criterion is not met, deliberately.**
   `test ! -f plugins/saga/scripts/evidence_ledger.py` fails on this branch. Its sole production
   importer is `closure_gate.py`, whose whole subject is that ledger and which issue 1030 deletes
   with its two dependents; removing it here means deleting or rewriting modules this card does not
   name. The plan's amendment section and the run-record replacement table both record it.
2. **The card's first and fourth criteria name board moves the lifecycle repository forbids.**
   `Ready to merge` and `Closeout` are live Operations options that are not in
   `allowed_submissions`, and review acceptance has no row at all. The build follows the allowed
   list; the discrepancy is the operator's to settle.
