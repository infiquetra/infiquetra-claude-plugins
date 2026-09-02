# Issue 907 terminal Code Review cycle 2 repair — units U28 through U33 executed

**Date:** 2026-09-02
**Branch:** `work/cp907-launcher-session-contract`
**Input:** the typed Code Review outcome
`docs/code-reviews/2026-09-02-issue-907-terminal-code-review-cycle2-result.v1.json` — outcome
`repairs_requested`, 0 of 7 lenses accepted, 39 findings (5 P1, 13 P2, 21 P3) bound to
revision `7aa0e3b7`. The operator ruled on method: fix the pane-write class structurally, with
one guarded write choke point, not a fifth flag-setting call.
**Prior units:** U1–U27 as recorded in the three earlier work-sessions under this date.
**Backend:** inline.
**change_kinds:** behavior, security, api, docs, config

## What was built, by unit

| Unit | Commit | One line |
|---|---|---|
| — | cf5cc12f | Cycle-2 review artifacts committed alone, contents untouched |
| U28 | 46454e57 | `PaneWriter`: both raw Herdr doors live only inside it, `write` owns the inspection; picker, `send()`, resends, `redeliver()` and Orchestrate's senders all go through it; `say()` removed; structural test pins the site enumeration |
| U29 | 5969e864 | `land` exits 4 when a resubmission is withheld; exit-code table pinned against the return statements; kept-merge wording; keep reason names the closed tab |
| U30 | f633fcbe, e5ff6406 | Parser cap by rows; size-ratio timing check; picker refusal reports a count; variant confirmation records its source |
| U31 | 991556b7 | One never-started vocabulary for the retry gate; `redrive --unit`; receipt shape reads the unit; retry exit codes 0/1/2; empty prompt refused; alias dropped; receipt keys documented |
| U32 | fa803209 | Post-ingest verification of every bound launcher name; old-source matrix state; `permission_declared` defaults false; paneless staged predicate; downgrade scope; reader docstring; contract-gate test |
| U33 | 5d74974d | agent-launcher 1.4.0, orchestrate 4.3.0, floor `>=1.4.0`, both changelogs, launcher-suite floor assertion, ledger sentence |

## The write-site enumeration and the per-site mutation run

Every place in either plugin that puts a line into a session, pinned as `PANE_WRITE_SITES` in
`plugins/agent-launcher/tests/test_launcher_contract.py` and checked by
`test_every_pane_write_goes_through_the_one_writer` (raw doors only inside `PaneWriter`, none in
Orchestrate, no inline copy of the predicate, the observed `writer.write` sites equal to this list):

| Site | File | Function | Write |
|---|---|---|---|
| S1 | launcher.py | `drive_opencode_variant_selection` | picker open (`/variants`) |
| S2 | launcher.py | `drive_opencode_variant_selection` | variant select |
| S3 | launcher.py | `send` | each setup slash command |
| S4 | launcher.py | `send` | the task (first send and every resend) |
| S5 | orchestrate.py | `_send_with_pane_guard` | review dispatch and land resubmission |

Each site's guard was forced off independently by swapping `writer.write(...)` for the private
raw door `writer._raw(...)`, plus two structural mutants. Every mutant was killed by tests that
observe the missing inspection, not only by the structural test:

| Mutant | Result | Observed by |
|---|---|---|
| S1 picker open, guard off | 5 failed | four OpenCode launch/redelivery tests + structural |
| S2 variant select, guard off | 5 failed | same four + structural |
| S3 setup line, guard off | 2 failed | `test_each_setup_line_and_the_task_are_separately_inspected` + structural |
| S4 task, guard off | 39 failed | every guard-launch, resend and redelivery test |
| S5 Orchestrate sender, guard off | 9 failed | eight review-dispatch and land-resubmit tests + structural |
| S6 a new raw `herdr pane run` added outside the class | 5 failed | structural + four OpenCode tests |
| S7 writer never records its write | 6 failed | resend and setup tests |

## Traceability ledger — all 39 findings

Every row has a disposition. None was dropped and none was disproven.

| Finding | Sev | Lens | Disposition | Unit / commit | Observed by |
|---|---|---|---|---|---|
| F38 | P1 | documentation-clarity | Dissolved by the structural change and the skill rewritten: the one exempt write is now true, including on OpenCode where it is the picker opening | U28 46454e57 | `test_documents_state_the_count_definition_and_the_shipped_guard_rule`; `test_an_owned_opencode_launch_inspects_before_the_select_and_the_task` |
| F39 | P1 | testing | Dissolved: the picker writes go through the writer; an owned OpenCode redelivery is observed with three guard calls; S1/S2 mutants killed | U28 46454e57 | `test_an_owned_opencode_redelivery_inspects_before_every_write` |
| F40 | P1 | correctness | Dissolved: an owned OpenCode launch inspects before the select and the task | U28 46454e57 | `test_an_owned_opencode_launch_inspects_before_the_select_and_the_task` |
| F41 | P1 | reliability | Dissolved: each setup line and the task are separate inspected writes | U28 46454e57 | `test_each_setup_line_and_the_task_are_separately_inspected` |
| F42 | P1 | correctness | Repaired: the stop is raised again; the multi-controller loop catches per controller and raises the withheld set; `land` exits 4 | U29 5969e864 | `test_land_exits_4_when_the_resubmission_is_withheld_on_staged_input` |
| F43 | P2 | documentation-clarity | Repaired: the 1.3.0 bullet says which writes it left outside the rule; the 1.4.0 entry states the rule as built | U33 5d74974d | changelog assertion in the contract suite |
| F44 | P2 | correctness | Dissolved: the code gap is closed, so the documents' one-write exemption is true; both documents name OpenCode's case | U28 46454e57 | as F38 |
| F45 | P2 | security | Repaired: cap by rows from the tail; a 450-row bordered draft past the old byte limit reads staged | U30 f633fcbe | `test_a_long_bordered_draft_past_the_old_byte_cap_still_reads_staged`, `test_the_rows_handed_to_the_parser_are_capped_from_the_tail_without_cutting_a_row` |
| F46 | P2 | architecture-maintainability | Dissolved: the write record is state on the writer, scoped to one delivery; nothing is threaded by hand | U28 46454e57 | structural test; S7 mutant |
| F47 | P2 | security | Dissolved with F40 | U28 46454e57 | as F40 |
| F48 | P2 | correctness | Repaired: the retry gate reads `session_has_started`, the same set `took_the_task` uses | U31 991556b7 | `test_redeliver_treats_done_and_unknown_as_never_started`, `test_redeliver_refuses_every_started_status` |
| F49 | P2 | reliability | Repaired with F48; a gone row is the preflight's named stop, not a closed route; `redrive` reopens the undelivered bucket | U31 991556b7 | `test_redeliver_of_a_gone_session_is_the_preflights_named_stop` |
| F50 | P2 | testing | Repaired: the structural test walks both trees for inline predicate copies and raw doors | U28 46454e57 | `test_every_pane_write_goes_through_the_one_writer` |
| F51 | P2 | api-contract | Repaired: the launcher suite asserts only that the packaged launcher satisfies the floor | U33 5d74974d | `test_orchestrate_declares_agent_launcher_dependency_and_breaking_version` (mutant: floor above shipped, killed) |
| F52 | P2 | api-contract | Repaired: the skill scopes the refusal to 4.0.0–4.1.x and says older opens blind | U32 fa803209 | prose |
| F53 | P2 | testing | Repaired: paneless live worker is prompted with zero reads | U28 46454e57 | `test_a_live_worker_with_no_pane_is_prompted_without_a_read` |
| F54 | P2 | api-contract | Repaired: after ingest every required name is verified; a missing one binds the stub and records the update remedy | U32 fa803209 | `test_a_launcher_root_that_lacks_the_bound_names_is_the_named_companion_fault`; matrix `old-source` |
| F55 | P2 | testing | Repaired: predicate false for a paneless staged receipt, and `go` prints already-has-tab | U32 fa803209 | `test_a_staged_receipt_without_a_pane_is_not_a_retry` |
| F56 | P3 | testing | Repaired both ways: the matrix asserts no pane write for every command in the below-floor, old-source and unusable states, and the earlier ledger sentence names its scope | U32 fa803209, U33 5d74974d | matrix test |
| F57 | P3 | api-contract | Repaired: the skill lists the surface Orchestrate binds; DECISIONS names the launcher as owner of the pane-write rule | U28 46454e57 | prose; `{#907-pane-writer-owns-the-write-rule}` |
| F58 | P3 | correctness | Repaired: the shape reads `unit.owned`, never the receipt it replaces | U31 991556b7 | `test_the_receipt_shape_reads_ownership_from_the_unit_not_the_receipt_it_replaces` |
| F59 | P3 | architecture-maintainability | Repaired: the rebound local is `existing_receipt` | U31 991556b7 | per-file mypy clean on launcher.py |
| F60 | P3 | reliability | Repaired inside the writer: the typing door's timeout names the ambiguity | U28 46454e57 | `test_a_pane_typing_timeout_names_the_ambiguity_like_the_prompt_door` |
| F61 | P3 | api-contract | Repaired: README key-set table; the `pane_id` alias is refused | U31 991556b7 | refusal case `pane_id` in `test_redeliver_cli_refuses_a_receipt_it_will_not_retry_with_exit_2` |
| F62 | P3 | testing | Repaired: a receipt without `owned` adopts unowned and identity is verified | U31 991556b7 | `test_a_retry_receipt_without_an_ownership_key_verifies_identity` |
| F63 | P3 | api-contract | Repaired: an empty `--prompt` is refused before any Herdr call | U31 991556b7 | refusal case `--prompt is empty` |
| F64 | P3 | api-contract | Repaired: refusals exit 2, undelivered exits 1, delivered 0; documented in the skill | U31 991556b7 | the refusal test and `test_redeliver_cli_exits_nonzero_when_the_prompt_was_not_taken` |
| F65 | P3 | testing | Repaired: a ratio at 4000 and 16000 starts complements the wall clock | U30 f633fcbe | `test_unterminated_osc_sequences_parse_in_linear_time` |
| F66 | P3 | api-contract | Repaired: `land` exit-code table in the command document, pinned to the return statements | U29 5969e864 | `test_the_documented_land_exit_codes_are_the_ones_the_command_returns` |
| F67 | P3 | api-contract | Repaired: default false; only the plan parser sets it true | U32 fa803209 | `test_a_legacy_row_without_the_permission_key_reads_as_not_declared` |
| F68 | P3 | api-contract | Repaired: `read_unit` docstring says the tolerance is a same-contract safety net | U32 fa803209 | prose |
| F69 | P3 | reliability | Repaired: missing names are bound after any ingest, and the `old-source` matrix state has a launcher whose source predates the floor | U32 fa803209 | matrix `old-source` rows |
| F70 | P3 | reliability | Repaired: `land --clean` branches on the landed names | U29 5969e864 | `test_land_clean_says_every_merged_unit_was_kept_rather_than_merged_nothing` |
| F71 | P3 | correctness | Repaired: the keep reason names the tab this pass closed | U29 5969e864 | `test_a_kept_unit_names_the_tab_this_pass_already_closed` |
| F72 | P3 | api-contract | Repaired: a launcher root pointed at a tree missing the predicate yields the named fault, and `status` survives | U32 fa803209 | `test_a_launcher_root_that_lacks_the_bound_names_is_the_named_companion_fault` |
| F73 | P3 | testing | Repaired: the test monkeypatches the known set to the previous one and asserts the gate raises with the remedy | U32 fa803209 | `test_a_reader_that_knows_only_the_previous_contract_refuses_this_run_file` |
| F74 | P3 | security | Repaired: the refusal reports the count of options | U30 f633fcbe, e5ff6406 | `test_the_picker_refusal_reports_a_count_not_the_scraped_options` |
| F75 | P3 | security | Repaired: `variant_confirmed_from` is `session` or `picker_menu_only`; the preflight confirms only the first | U30 f633fcbe | `test_variant_confirmation_records_whether_the_token_was_seen_outside_the_menu` |
| F76 | P3 | reliability | Repaired: `redrive --unit` in Orchestrate; `redeliver` accepts an undelivered receipt; the warning names both | U31 991556b7 | `test_redrive_reprompts_an_undelivered_unit_whose_session_is_idle`, `test_redeliver_cli_accepts_an_undelivered_receipt` |

## Reproducer discipline, stated plainly

The structural unit U28 was verified the way the operator specified: the sites were enumerated
first, then the guard was forced off at each independently, and every mutant was observed. Its
new behavioural tests were written together with the restructure; the 38 tests the restructure
broke were harnesses that had stubbed `send` or `say`, and they were rebuilt on the real door
rather than re-stubbed. For U29–U33 the test and the fix were written together and the fail-first
evidence is the named mutant that reverts the fix; every such mutant was killed. The mutants that
survived nothing: none. One commit (U30) went in with an Orchestrate-side assertion still pinning
the old picker wording; the follow-up `e5ff6406` repointed three tests to the redacted message.

## Mutants named and killed, by unit

| Unit | Killed |
|---|---|
| U28 | 7 (S1–S7 above) |
| U29 | 5 |
| U30 | 5 |
| U31 | 7 |
| U32 | 4 |
| U33 | 1 |

## Checks run

- Affected suites per unit: U28 687, U29 208, U30 258 launcher + 113 Orchestrate after the
  follow-up, U31 515, U32 553, U33 467 — all passed.
- `ruff check` and `ruff format --check` clean at every unit.
- Gate-style `mypy plugins/ scripts/ tests/`: clean after U28 and after U31.
- Journal ordering lint: 0 violations.
- Full gate: `GATE_LOG_DIR=/tmp/gate-cp907-r3` — result recorded in the saga tick that follows.

## Journal entries filed

- DECISIONS `{#907-pane-writer-owns-the-write-rule}` (U28); amendment to
  `{#907-agent-launcher-floor-owner}` naming `redrive` (U31).
- LEARNINGS `{#907-flag-per-call-site-fails-at-the-next-site}` (U28).

## Not done, by instruction

- No push, no pull request, no merge, no Code Review launched.
- `docs/runs/2026-08-30-agent-launcher-907-run-plan.md` untouched.
- Nothing under `docs/code-reviews/` or `docs/evidence/` edited after the artifact commit.
