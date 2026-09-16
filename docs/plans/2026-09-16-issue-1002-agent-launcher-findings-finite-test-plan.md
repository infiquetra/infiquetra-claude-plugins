---
title: Finite test plan — Agent Launcher pane-write findings from issue 1002
type: test
status: active
date: 2026-09-16
origin: GitHub issue 1002 and children 953, 954, 955, 961, 963-972, 981-987
backend: inline
---

# Finite test plan — Agent Launcher pane-write findings from issue 1002

This plan exists before any implementation commit. Every scenario drives a shipped function in `plugins/agent-launcher/skills/agent-launcher/scripts/composer.py` or `launcher.py`. Tests live in `plugins/agent-launcher/tests/test_launcher_contract.py` unless a scenario names `tests/test_agent_launcher_plugin.py`.

No scenario re-implements the unit under test, mocks the function under test, or hard-codes an expected value that bypasses the shipped entry point.

## Key Technical Decisions

KTD1. Each scenario calls a shipped composer or launcher function with a representative pane dump or receipt. Re-implementing the unit under test inside the test is not coverage.

## Implementation Units

### U1. Finite scenario table

The table below is the executable unit. Implementation of the behaviors it names is the companion plan `docs/plans/2026-09-16-issue-1002-agent-launcher-findings-plan.md`.

## How to run

```bash
python3 -m pytest plugins/agent-launcher/tests/test_launcher_contract.py tests/test_agent_launcher_plugin.py -q
```

A scenario is done when the named test calls the shipped function and the assertion matches the expected outcome column.

## Finding classes

Plan #954, #969, and #970 together: one classification rule. A Herdr row reporting `done` has started and finished. It is not a never-started session.

| ID | Issue | Finding | Shipped function | Input | Action | Expected outcome | Test |
|---|---|---|---|---|---|---|---|
| TP-F102 | #953 | Second `>` row classified EMPTY | `inspect_composer` / `_classify_row` | Claude pane `❯ \n> quoted draft line` | classify | `STAGED`, withheld text includes the quoted line; `guard_pane_before_write` raises `StagedInputError` | `test_claude_quoted_second_row_is_staged_not_empty` |
| TP-F103 | #954 | Redeliver into a finished session | `redeliver` / `session_has_started` | owned unit, Herdr `agent_status=done`, empty composer | `redeliver(unit)` | no prompt or pane write; status `prompt_undelivered`; note names `done` | `test_redeliver_refuses_a_done_session` |
| TP-F104 | #955 | `PaneWriter._raw` / `_type` callable outside `write` | `PaneWriter` | class body of `PaneWriter` | AST inspect | no method named `_raw` or `_type`; doors exist only as nested functions inside `write` | `test_pane_writer_has_no_raw_or_type_methods` |
| TP-F110 | #961 | Last-block-wins painted marker | `inspect_composer` | `❯ staged draft\n❯ ` (adjacent empty marker below) | classify | `STAGED` of the earlier draft, not `EMPTY` | `test_empty_marker_below_staged_draft_is_a_decoy` |
| TP-F110b | #961 | Echo above empty live box still empty | `inspect_composer` | `❯ earlier submitted prompt\npane output line\n❯ ` | classify | `EMPTY` (content row between blocks keeps last-block live) | `test_an_empty_live_box_below_an_echo_reads_empty` (existing, must stay green) |
| TP-F110c | #961 | Blank-separated empty marker | `inspect_composer` | `❯ staged draft\n\n❯ ` | classify | `STAGED` of the earlier draft, not `EMPTY` | `test_blank_separated_empty_marker_below_staged_is_a_decoy` |
| TP-F110d | #961 | Two trailing empty markers | `inspect_composer` | `❯ staged draft\n❯ \n❯ ` | classify | `STAGED` of the earlier draft, not `UNCLASSIFIABLE` | `test_two_trailing_empty_markers_below_staged_are_decoys` |
| TP-F112 | #963 | Receipt keys documented vs enforced | `_adopt_retry_receipt` | receipt missing `unit_name` and/or `agent_name` | adopt | `RetryReceiptRefused` (exit 2); missing `unit_name` never accepted | `test_redeliver_refuses_receipt_missing_required_keys` |
| TP-F113 | #964 | Markdown bullets as picker options | `parse_opencode_variants` | pane of agent prose `- shipped\n* broken\n> high` | parse | only ladder tokens (`high` etc.); `shipped`/`broken` are not options | `test_parse_opencode_variants_ignores_prose_bullets` |
| TP-F114 | #965 | Failed/timed-out read authorizes write | `guard_pane_before_write` | `pane_input_inspection` returns `READ_FAILED` or `READ_TIMEOUT` | guard then `PaneWriter.write` | `SystemExit`; no Herdr pane/prompt write | `test_failed_or_timed_out_composer_read_refuses_the_write` |
| TP-F115 | #966 | Launcher echo confirms variant | `confirm_opencode_variant_selected` | pane is exactly the typed token `high` plus menu rows | confirm | not `"session"`; `"picker_menu_only"` or stop | `test_opencode_echo_of_typed_token_is_not_session_confirmation` |
| TP-F116 | #967 | `herdr workspace list` unbounded | `workspace_id_for_name` | stub `run` that records kwargs | call with a workspace name | `run` is invoked with a finite `timeout=` | `test_workspace_id_for_name_bounds_the_herdr_list` |
| TP-F117 | #968 | Account label scraped anywhere | `pane_account_label` | pane body contains `user [personal]:` and statusline tail is `user [company]:` | scrape | `"company"` (tail/statusline wins; body cannot override) | `test_account_label_is_read_from_the_statusline_tail` |
| TP-F118 | #969 | `prompt_undelivered` fixed point on `done` | `took_the_task` / `session_has_started` | row `agent_status=done` | `session_has_started(row)` | `True`; `NEVER_STARTED_STATUSES` does not contain `"done"` | `test_done_is_a_started_status` |
| TP-F119 | #970 | Delivered-plus-staged receipt accepted | `_adopt_retry_receipt` | `prompt_delivered=True` and `input_box=staged` | adopt | `RetryReceiptRefused`; delivered prompt is not sent twice | `test_redeliver_refuses_delivered_plus_staged_receipt` |
| TP-F120 | #971 | Named mutation test does not exist | `test_forcing_the_guard_off_at_each_write_site_is_observed` | each `PANE_WRITE_SITES` row | mutate AST so that site skips `write` and calls a raw door | the structural detector fails that mutated tree | `test_forcing_the_guard_off_at_each_write_site_is_observed` |
| TP-F121 | #972 | Sixteen evasion shapes pass | `_raw_door_calls` (the helper `test_every_pane_write_goes_through_the_one_writer` uses) | the enumerated evasion snippets, including f-string element 0 | parse each snippet and assert `_raw_door_calls` is non-empty | detector reports a stray door for each catchable shape; the test has no special-case return | `test_structural_detector_kills_enumerated_evasion_shapes` |
| TP-F130 | #981 | Row cap removed byte bound | `pane_input_inspection` / `tail_inspect_window` | 4201 short rows (under old 65536 bytes) whose tail is a staged Claude box, and a 100-row viewport of 80k-char rows | inspect | staged box survives the row cap; byte cap still trims from the head on a row boundary | `test_inspect_window_has_both_row_and_byte_bounds` |
| TP-F131 | #982 | Stale `input_box_text_chars` | `guard_pane_before_write` | first inspect staged (sets chars), then inspect empty | empty branch | receipt `input_box=="empty"` and `input_box_text_chars` absent or 0 | `test_empty_input_box_clears_stale_text_chars` |
| TP-F132 | #983 | Picker token in note / stop | `drive_opencode_variant_selection` / `confirm_opencode_variant_selected` | selected token `high`; `picker_menu_only` confirmation | drive / confirm | note has no token; `picker_menu_only` does not write a verified note; refusal stop interpolates no option token | `test_picker_token_is_redacted_from_notes_and_stops` |
| TP-F133 | #984 | Symlink escape on task file | `pane_text` | unit name safe; `.orchestrate/tasks/<name>.md` is a symlink to `/tmp/outside` | `pane_text` with text over `PANE_TYPING_LIMIT` | `SystemExit` naming containment; target file not written | `test_pane_text_refuses_symlink_escape` |
| TP-F134 | #985 | Five untested write-door stops | `PaneWriter.write` | (1) pane typing nonzero (2) prompt refused, no pane (3) `door=pane` and no pane (4) unknown door (5) launch with no `pane_id` | call shipped door | each raises the named `SystemExit` | `test_pane_writer_nonzero_typing_is_a_named_stop`, `test_pane_writer_prompt_refused_without_pane`, `test_pane_writer_pane_door_requires_a_pane`, `test_pane_writer_unknown_door_is_a_named_stop`, `test_launch_without_pane_id_is_a_named_stop` |
| TP-F135 | #986 | Wall-clock parser complexity | `inspect_composer` / `ANSI_RE` | 16000 unterminated OSC starts plus a staged box | classify | `STAGED` `"draft"`; `ANSI_RE.pattern` excludes ESC in the OSC body; no `elapsed <` or `+ 0.05` slack in this test | `test_unterminated_osc_sequences_parse_in_linear_time` (rewritten) |
| TP-F136 | #987 | Observer compares task write to itself | `send` via `launch` | unowned unit, setup two slash commands, known `unit.task` | launch | third write text equals the normalized task, not `sends[2][4]` compared to itself | `test_each_setup_line_and_the_task_are_separately_inspected` (assertion repaired) |

## Evasion shapes the structural detector must kill (TP-F121)

Catchable in an AST walk of `launcher.py` / `orchestrate.py`. Residual Python dynamism (`getattr` on `sys.modules`) is documented in the plan as residual, not claimed impossible.

| Shape | Detector must report |
|---|---|
| `subprocess.run([... herdr pane run ...])` outside `PaneWriter.write` | stray door |
| `argv = ["herdr","pane","run",...]; run(argv)` | stray door |
| tuple literal `("herdr","pane","run",...)` passed to `run` | stray door |
| list concatenation building a raw door | stray door |
| module constant as argv element 0 equal to `"herdr"` with pane/prompt tail | stray door |
| f-string element 0 that equals a raw door | stray door |
| alias `_run = run` then `_run([herdr pane run])` | stray door |
| `run(args=[...])` keyword form | stray door |
| `writer._raw(...)` or `writer._type(...)` attribute call | stray door (and the methods must not exist) |
| write local not named `writer` (`w.write(...)` on a `PaneWriter`) | still a write site, counted |
| inline `if not session_owned(unit)` or ternary re-deriving the guard | inline predicate |

Not a defect: `PaneWriter(...).write(text)` chained. That is the door.

## Cluster #954 / #969 / #970 — one rule, three tests

`NEVER_STARTED_STATUSES` becomes `(None, "idle", "unknown")`. `"done"` is started.

| Test | Proves |
|---|---|
| `test_done_is_a_started_status` | `session_has_started` is true for `done` |
| `test_redeliver_refuses_a_done_session` | retry door does not send |
| `test_redeliver_refuses_delivered_plus_staged_receipt` | a receipt that already delivered is refused even when `input_box` is `staged` |

Existing `test_redeliver_treats_done_and_unknown_as_never_started` is inverted or split: `unknown` and `None` remain retryable; `done` is not.

## Version-parity scenarios (release unit)

| Test | File | Expected |
|---|---|---|
| `test_agent_launcher_metadata_is_marketplace_registered` | `tests/test_agent_launcher_plugin.py` | `plugin.json` version equals marketplace `agent-launcher` version and is greater than `1.4.0` |
| changelog heading | `test_release_and_journal_record_the_composer_contract` | historical `## [1.4.0]` remains; a newer heading exists |
| Orchestrate floor | `tests/test_plugin_manifest_loader_contract.py` | `AGENT_LAUNCHER_FLOOR_RELEASE` stays `1.4.0` unless a new public API is added |

## Explicit non-coverage

- Live Herdr daemon, live vendor CLIs, and production Claude Code install.
- Cross-plugin companion-contract findings under #908, #909, #910 (including #886).
- A wall-clock performance SLO for the parser; complexity is the regex contract plus classification of the hostile input.
