# Issue 907 terminal Code Review repair — units U19 through U27 executed

**Date:** 2026-09-02
**Branch:** `work/cp907-launcher-session-contract`
**Input:** the typed Code Review outcome
`docs/code-reviews/2026-09-02-issue-907-terminal-code-review-result.v1.json` — outcome
`repairs_requested`, next action `dispatch_repairs`, bound to revision `7b0d653c`, 37 findings
across seven lenses (7 P1, 23 P2, 7 P3; five marked pre-existing). The operator ruled: repair all
37, deduplicate by root cause, drop nothing.
**Prior units:** U1–U18 as recorded in the two earlier work-sessions under this date.
**Backend:** inline.
**change_kinds:** behavior, security, api, docs, config

## What was built, by unit

| Unit | Commit | One line |
|---|---|---|
| — | d6c7d722 | Review artifacts committed alone, contents untouched |
| U19 | dbbb4c42 | Track every pane write for the guard; close the redelivery retry door on a busy session; pane-write timeouts; receipt shape single owner |
| U20 | a3f85b04 | Run-file contract `2026-09-02.permission-declared`, bound to the Unit field set by a test; State section documents the reader floor |
| U21 | c3de966a | Orchestrate senders inspect owned panes through `should_guard_pane_write`; one staged controller no longer blocks the rest |
| U22 | 1c3fa73e | `redeliver` CLI subcommand with a real-subprocess test; SKILL/README state the shipped guard rule and the retry |
| U23 | 25da63f3 | `roster` and `saga` run below floor; six write commands gate; matrix test pins both buckets; four documents agree |
| U24 | 5797a3d0 | Observing tests for two row-rule clauses and the second strip; staged counter-case carries a pane; staged literal and four shared constants bound; `_plugin_root` everywhere |
| U25 | cd543fb2 | `clean --merged` keep reasons split (branchless, git failure); `reap` checks `git worktree remove` |
| U26 | 694de6d0 | OSC regex linear; parser handed at most `PANE_INSPECT_MAX_CHARS` from the tail |
| U27 | b8e39dc7 | agent-launcher 1.3.0, orchestrate 4.2.0, floor `>=1.3.0`, both changelogs, floor constant test, fixture provenance |

## Root causes behind the seven P1s

| Root cause | Findings | Unit |
|---|---|---|
| The write flag was derived from which door `say()` used, and a plain assignment discarded the redelivery seed | F02, F03, F04, F30, F16 | U19 |
| A new Unit field shipped under an unchanged run-file contract string | F05, F21 | U20 |
| Orchestrate's later senders exempted owned panes | F06, F22 | U21 |
| `redeliver` appeared in no release surface and had no standalone door | F01, F07 | U22, U27 |

## Traceability ledger — all 37 findings

Every row has a disposition. None was dropped and none was disproven; where the reviewer offered
two fixes, the row names which was taken.

| Finding | Sev | Lens | Disposition | Unit / commit | Observed by |
|---|---|---|---|---|---|
| F01 | P1 | api-contract | Repaired: 1.3.0 changelog names `redeliver`, its refusals and precondition; SKILL.md carries the retry door beside the stop conditions | U22 1c3fa73e, U27 b8e39dc7 | `test_documents_state_the_count_definition_and_the_shipped_guard_rule`; changelog assertion in the contract suite |
| F02 | P1 | correctness | Repaired: `_deliver` sets `wrote_before = True` the moment the first send returns; the plain assignment is gone | U19 dbbb4c42 | `test_redeliver_with_the_real_send_inspects_before_every_write` (1 guard call for 3 writes at 7b0d653c) |
| F03 | P1 | security | Repaired: `say()` and `send()` return nothing; the flag records that a write happened, not the door | U19 dbbb4c42 | `test_agent_prompt_resend_into_an_owned_pane_is_inspected_before_each_resend` (replaces the test that pinned the gap), `..._stops_on_a_draft_staged_since` |
| F04 | P1 | reliability | Repaired: `redeliver()` reads the Herdr row and refuses anything but `idle`, closing the retry route as `prompt_undelivered` | U19 dbbb4c42 | `test_redeliver_refuses_when_the_session_has_left_idle`, `..._is_gone`; counter-case `test_redeliver_into_an_idle_session_still_sends` |
| F05 | P1 | api-contract | Repaired: `RUN_FILE_CONTRACT = "2026-09-02.permission-declared"`, previous string kept readable | U20 a3f85b04 | `test_a_reader_that_knows_only_the_previous_contract_refuses_this_run_file` |
| F06 | P1 | security | Repaired (pre-existing): `_send_with_pane_guard` calls `should_guard_pane_write(unit, wrote_before=True)` | U21 c3de966a | `test_owned_review_dispatch_inspects_once_before_its_send`, `..._with_draft_refuses`, `test_owned_land_resubmit_inspects_once_before_its_send` |
| F07 | P1 | documentation-clarity | Repaired: `redeliver` CLI subcommand exposed (the first of the two offered fixes) and documented under the stop conditions | U22 1c3fa73e | `test_redeliver_cli_as_a_real_subprocess_reprompts_the_recorded_pane` and four in-process CLI tests |
| F08 | P2 | documentation-clarity | Repaired the other way: the code was brought back to the record (F24, option one), and the record carries an amendment saying so; both buckets are now named | U23 25da63f3 | the matrix test's two bucket constants |
| F09 | P2 | documentation-clarity | Repaired: citation names `wrapper_reused` at line 94 of revision dbbb4c42 and says what 54–65 is | U22 1c3fa73e | prose; no test |
| F10 | P2 | documentation-clarity | Repaired: two 1.2.2 bullets added — the named broken-parser stop (3a60c6ca) and the close-note dedup (e35c802c) | U27 b8e39dc7 | prose; changelog assertion checks the section exists |
| F11 | P2 | correctness | Repaired: both documents state the shipped predicate and when an owned receipt carries `input_box` | U22 1c3fa73e | `test_documents_state_the_count_definition_and_the_shipped_guard_rule` (asserts the superseded sentence is gone) |
| F12 | P2 | security | Repaired: OSC body excludes ESC; `PANE_INSPECT_MAX_CHARS` cap from the tail. Measured 9.06 s → under 0.2 s at 16000 starts | U26 694de6d0 | `test_unterminated_osc_sequences_parse_in_linear_time`, `test_the_bytes_handed_to_the_parser_are_capped_from_the_tail` |
| F13 | P2 | testing | Repaired: two row-rule cases added | U24 5797a3d0 | `test_an_indented_row_led_by_another_vendors_glyph_ends_the_block`, `test_a_bordered_row_of_spaced_rule_segments_is_a_rule_row` |
| F14 | P2 | testing | Repaired: styled-border case binds the second strip | U24 5797a3d0 | `test_a_styled_border_around_a_border_glyph_draft_still_reads_staged` |
| F15 | P2 | architecture-maintainability | Repaired: the hand-typed literal in `record_wrapper_identity` is deleted | U19 dbbb4c42 | `test_wrapper_identity_receipt_is_the_shape_function_output` |
| F16 | P2 | architecture-maintainability | Repaired: `should_guard_pane_write` is the one owner; three launcher sites and Orchestrate's sender call it | U19 dbbb4c42, U21 c3de966a | `test_pane_write_guard_predicate_has_one_owner` (AST: no inline copy) |
| F17 | P2 | testing | Repaired: a redelivery test leaves the preflight real and admits an hour-old transcript | U19 dbbb4c42 | `test_redeliver_admits_a_transcript_older_than_the_retry` (mutant `since=time.time()` killed) |
| F18 | P2 | reliability | Repaired (pre-existing): `PANE_WRITE_SECONDS` on both doors; a timed-out prompt is a named stop that never falls through to the pane | U19 dbbb4c42 | `test_pane_writes_carry_a_timeout_and_a_timed_out_prompt_never_falls_through` |
| F19 | P2 | documentation-clarity | Repaired: README and command document name the six write commands and the two informational ones by bucket | U23 25da63f3 | prose; matrix test pins the behaviour |
| F20 | P2 | api-contract | Repaired: State section names `permission`, `permission_declared`, and the 4.2.0 reader floor | U20 a3f85b04 | prose |
| F21 | P2 | correctness | Repaired with F05; `UNIT_FIELDS_BY_CONTRACT` binds the string to the field tuple | U20 a3f85b04 | `test_the_contract_string_moves_with_the_unit_field_set` (mutant: added field without bump, killed) |
| F22 | P2 | security | Repaired: the sender's docstring states the actual rule and why it differs from `launch` | U21 c3de966a | prose; behaviour under F06's tests |
| F23 | P2 | reliability | Repaired: `_resubmit_one` records, prints with the controller's name, leaves pending, returns False | U21 c3de966a | `test_a_staged_stop_on_one_controller_does_not_block_the_other_controllers_resubmit` |
| F24 | P2 | security | Repaired (option one): `assert_agent_launcher_ingested` gates `roster` and `saga`; only six commands gate on the floor | U23 25da63f3 | matrix test `below-floor/roster`, `below-floor/saga`, the renamed help-and-roster test |
| F25 | P2 | api-contract | Repaired (option two): named `STAGED_INPUT_BOX` bound to `ComposerState.STAGED.value` by a test | U24 5797a3d0 | `test_the_staged_marker_is_the_composer_enum_value` |
| F26 | P2 | reliability | Repaired: the gate has two arms; the branchless-done arm prints its own reason | U25 cd543fb2 | `test_every_keep_cause_prints_its_own_reason` (`settled` row) |
| F27 | P2 | reliability | Repaired (pre-existing): removal result captured; a failure that leaves the directory keeps the unit and the run record | U25 cd543fb2 | `test_a_worktree_that_cannot_be_removed_keeps_the_unit_and_the_run_record`; counter-case `..._already_gone_..._is_still_closed` |
| F28 | P2 | testing | Repaired: the counter-case carries a pane; a second counter-case covers a pane with an empty receipt | U24 5797a3d0 | `test_already_has_tab_still_skips_a_pending_unit_without_the_staged_marker`, `test_a_pending_unit_with_a_pane_and_an_empty_receipt_is_skipped_not_redelivered` (widened-clause mutant killed) |
| F29 | P2 | api-contract | Repaired: `AGENT_LAUNCHER_FLOOR_RELEASE = "1.3.0"` names the release; a second test asserts the floor is not above the shipped launcher | U27 b8e39dc7 | `test_orchestrate_keeps_its_agent_launcher_floor`, `test_the_declared_floor_is_not_above_the_launcher_this_repository_ships` |
| F30 | P2 | api-contract | Repaired with F04 (same defect, api-contract lens) | U19 dbbb4c42 | as F04 |
| F31 | P3 | api-contract | Repaired (pre-existing): AST parity test over the four shared constants, reading each module's own definition | U24 5797a3d0 | `test_the_four_shared_constants_agree_between_orchestrate_and_the_launcher` |
| F32 | P3 | api-contract | Repaired: `pane_input_text` deleted (no caller) | U19 dbbb4c42 | grep; no test |
| F33 | P3 | correctness | Repaired (pre-existing): `launch()` docstring names the three OpenCode writes, two inspections, and the picker-selection gap as a residual | U19 dbbb4c42 | prose |
| F34 | P3 | testing | Repaired (option two): `_provenance` block in the fixture for all four captures; the two 2026-08-30 rows state that pane id and Herdr version were not recorded | U27 b8e39dc7 | fixture; test-module comment |
| F35 | P3 | architecture-maintainability | Accepted as stated: docstring note that the roster test checks completeness, not minimality | U24 5797a3d0 | prose |
| F36 | P3 | api-contract | Repaired: schema resolver and `PLUGIN_MANIFEST` go through `_plugin_root` | U24 5797a3d0 | `test_every_sibling_plugin_path_goes_through_the_layout_helper` (AST: no raw `parents[]`) |
| F37 | P3 | correctness | Repaired: `_reap_keep_reason` re-runs the rev-list and names a git failure | U25 cd543fb2 | `test_every_keep_cause_prints_its_own_reason` (`ghost` row) |

## Invariants written before each edit (both directions)

- **U19.** Must not happen: any write after the first goes out uninspected; a redelivery prompts a
  session that already took the task. Must still happen: the first write into a freshly created
  owned pane takes no inspection (`test_freshly_created_pane_takes_no_inspection_path`, kept);
  an idle session with a cleared composer is still redelivered.
- **U20.** Must not happen: an older reader opens a file it cannot read. Must still happen: this
  reader opens every older file (`test_a_run_file_this_version_wrote_round_trips`, kept).
- **U21.** Must not happen: an owned pane is prompted hours later with no read. Must still
  happen: an owned pane with an empty box is still dispatched; an unowned draft still stops.
- **U22.** Must not happen: the retry door delivers a prompt that was already delivered. Must
  still happen: a receipt that records a staged stop is retried without a wrapper create.
- **U23.** Must not happen: a below-floor companion reaches a pane write (matrix asserts no pane
  write for every command in the below-floor and unusable states, extended to every command in those
  states and the old-source state by the cycle-2 repair, U32). Must still happen: `roster` and `saga` refuse when
  nothing was ingested.
- **U25.** Must not happen: a failed removal is reported closed. Must still happen: a nonzero
  removal whose directory is gone is a removal, not a keep.
- **U26.** Must not happen: the parse is quadratic. Must still happen: the box at the tail of an
  oversized viewport still classifies.

## Reproducer discipline, stated plainly

For U19, U20, U21 and U26 the reproducers were written and confirmed failing at the prior
revision before any edit (8, 2, 4 and 2 failures respectively). For U22, U23, U24, U25 and U27
the test and the fix were written together and the fail-first evidence is the named mutant that
reverts the fix; every such mutant was killed. That is a deviation from the "fail first, then
edit" ordering the brief asked for on those five units, and it is recorded here rather than
smoothed over.

## Mutants named and killed, by unit

| Unit | Killed | Notes |
|---|---|---|
| U19 | 11 | includes the mirror image (predicate always true), caught by the kept fresh-pane test |
| U20 | 3 | string reverted; old string dropped from the known set; field added without bump |
| U21 | 5 | ownership-only; never inspects; write half false; re-raise; claims success after a stop |
| U22 | 5 | staged check removed; launch instead of redeliver; exit code inverted; task-name check removed; subcommand absent |
| U23 | 2 + 1 equivalent | "ingested check never refuses" survives because the degraded stub for `roster` refuses on its own; two mechanisms guarantee the same refusal |
| U24 | 7 | one per finding: F13 twice, F14, F25, F28, F31, F36 |
| U25 | 4 | gate recombined; git failure as unlanded; removal ignored; keeps when the directory is gone |
| U26 | 3 | OSC body admits ESC; cap removed; cap from the head |
| U27 | 2 | floor back to 1.2.2; floor above the shipped launcher |

## Checks run

- Plugin subsets after each unit: U19 372, U20 285, U21 287, U22 434, U23 88 (plugin module),
  U24 503, U25 47 (land/clean), U26 305, U27 423 — all passed.
- `ruff check` and `ruff format --check` clean on every touched file at every unit.
- Gate-style `mypy plugins/ scripts/ tests/`: clean (346 files) after U21, after U24, and after
  U26. Two concurrent mypy runs corrupted `.mypy_cache` once and reported seven phantom
  redis-channel errors; clearing the cache and running alone restored the clean result.
- Journal ordering lint: 0 violations after every journal edit.
- Full gate: `GATE_LOG_DIR=/tmp/gate-cp907-r2` — result recorded in the saga tick that follows
  this writeup.

## Journal entries filed (same commit as the change)

- LEARNINGS `{#907-write-flag-tracked-the-door}` (U19), `{#907-osc-regex-quadratic}` (U26).
- DECISIONS `{#907-run-file-contract-bound-to-unit-fields}` (U20); amendment to
  `{#907-agent-launcher-floor-owner}` (U23).

## Not done, by instruction

- No push, no pull request, no merge, no Code Review launched.
- `docs/runs/2026-08-30-agent-launcher-907-run-plan.md` untouched.
- Nothing under `docs/code-reviews/` or `docs/evidence/` edited after the artifact commit.

## Next step

Run the full gate in `/tmp/gate-cp907-r2`, read `result.txt`, record it on the saga, stop and
report to the coordinator.
