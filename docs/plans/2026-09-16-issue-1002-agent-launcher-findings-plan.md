---
title: Agent Launcher pane-write findings from issue 1002
type: fix
status: active
date: 2026-09-16
origin: docs/plans/2026-09-16-issue-1002-agent-launcher-findings-finite-test-plan.md
backend: inline
---

# Agent Launcher pane-write findings from issue 1002

Repair the twenty-one Agent Launcher findings grouped under GitHub issue 1002 so the pane-write door, composer parser, receipts, and retry path match the contracts those issues describe, then ship a version above 1.4.0.

## Problem Frame

Issue 907 shipped agent-launcher 1.4.0 under a terminal review that accepted no lens. The operator took that outcome at its word and filed the findings. These twenty-one are the ones whose cited file is inside `plugins/agent-launcher/` and whose fix is the launcher's alone. The current tree still classifies a quoted Claude continuation as empty, treats a finished (`done`) session as never-started, leaves `PaneWriter._raw` / `_type` callable outside `write`, and authorizes a write when the composer was never observed.

## Requirements

R1. A Claude composer whose first content row begins with `>` is `STAGED`, not `EMPTY`. `guard_pane_before_write` refuses that pane. (#953 F102)

R2. `session_has_started` is true for Herdr `agent_status=done`. `NEVER_STARTED_STATUSES` is `(None, "idle", "unknown")`. `redeliver` does not send into a `done` session. (#954 F103, #969 F118)

R3. `_adopt_retry_receipt` refuses a receipt with `prompt_delivered is True`, including delivered-plus-staged. (#970 F119)

R4. `PaneWriter` has no `_raw` or `_type` methods. The two Herdr doors exist only inside `write`. (#955 F104)

R5. `inspect_composer` does not let a later empty marker row with only blank separators from an earlier `STAGED` block classify as `EMPTY`. An empty live box below an echo with a content row between them stays `EMPTY`. (#961 F110)

R6. `_adopt_retry_receipt` requires `unit_name`, `pane`, `tab_id`, `owned`, `agent_name`, and one retryable marker. Missing `unit_name` is a refusal, not a skip. (#963 F112)

R7. `parse_opencode_variants` returns only tokens in `OPENCODE_VARIANT_RANKS`. Markdown bullets from agent prose are not options. (#964 F113)

R8. `READ_FAILED` and `READ_TIMEOUT` refuse the write. They do not record a note and return. `UNCLASSIFIABLE`, `NOT_FOUND`, and `UNSUPPORTED_VENDOR` keep the documented styled-composer trade. (#965 F114)

R9. `confirm_opencode_variant_selected` does not treat a row that is only the typed token as `"session"`. (#966 F115)

R10. `workspace_id_for_name` passes a finite timeout to `run`. (#967 F116)

R11. `pane_account_label` reads the account from the visible tail (statusline region), not from arbitrary body text. (#968 F117)

R12. A committed test named `test_forcing_the_guard_off_at_each_write_site_is_observed` mutates each `PANE_WRITE_SITES` row and expects the structural detector to fail that tree. The comment above `PANE_WRITE_SITES` names a function that exists. (#971 F120)

R13. The structural detector reports the catchable evasion shapes in the finite test plan. It does not claim every Python dynamism is impossible. (#972 F121)

R14. Composer inspection is bounded by both `PANE_INSPECT_MAX_LINES` and `PANE_INSPECT_MAX_CHARS`, trimming from the head on a row boundary so the live box survives. (#981 F130)

R15. The empty-box branch clears `input_box_text_chars` (delete or zero). (#982 F131)

R16. Picker notes and refusal stops do not interpolate scraped option tokens. A `picker_menu_only` confirmation does not write a verified note. (#983 F132)

R17. `pane_text` refuses a task-file path whose resolved target is outside `TASK_DIR`, matching Orchestrate's `resolve_task_file`. (#984 F133)

R18. The five named write-door stops (nonzero typing, prompt refused with no pane, pane door with no pane, unknown door, launch without `pane_id`) each have a test that calls the shipped door. (#985 F134)

R19. The OSC complexity test classifies the hostile input and asserts `ANSI_RE`'s OSC body excludes ESC. It does not assert wall-clock elapsed time or a 50 ms slack. (#986 F135)

R20. `test_each_setup_line_and_the_task_are_separately_inspected` asserts the third write text equals the normalized task. (#987 F136)

R21. Agent Launcher version is greater than 1.4.0 with `plugin.json` / marketplace `agent-launcher` entry / `CHANGELOG.md` parity. Every assertion that pins `1.4.0` as the current version is updated in the same unit. Orchestrate's companion floor stays `>=1.4.0` unless a new public API is added.

R22. Every child of issue 1002 is `CLOSED` or carries a recorded parking ruling.

## Key Technical Decisions

KTD1. `done` is started, not never-started: Herdr reports `done` after a session took its task and finished. Counting it with `idle` made `took_the_task` return false, recorded `PROMPT_UNDELIVERED`, and opened every retry door onto a finished session. `unknown` and a missing row stay never-started because they are not evidence of work. Rejected: keep `done` in the never-started set and add a separate redeliver gate. Two gates on one vocabulary already drifted once.

KTD2. Nested doors, not private methods: `PaneWriter.write` owns `herdr agent prompt` and `herdr pane run` as nested functions. Python's `_raw` prefix is convention; the review's mutant called `writer._raw` and the structural test still passed. Nested functions are not attributes. Rejected: `inspect.stack()` caller checks (fragile) and name mangling (still callable).

KTD3. Empty marker below a staged block is a decoy only when no content row sits between them: last-block-wins stays for `❯ submitted\npane output\n❯ ` so a working launch is not a refusal. An adjacent or blank-separated empty marker under a staged block is painted chrome, and the earlier staged inspection wins so the write stops. Rejected: always prefer any earlier staged block (breaks the echo-above-empty-box case). Rejected: keep last-block-wins with no exception (F110).

KTD4. Failed observation refuses the write: `READ_FAILED` and `READ_TIMEOUT` are the absence of a pane, not styled-composer ambiguity. `{#907-styled-composer-trade}` still covers `UNCLASSIFIABLE`, `NOT_FOUND`, and `UNSUPPORTED_VENDOR`. Rejected: refuse all five inconclusive states (would stop every OpenCode picker inspect and every uncharacterised vendor).

KTD5. OpenCode options are the ladder, not any bullet: `parse_opencode_variants` keeps a token only when `token.lower()` is in `OPENCODE_VARIANT_RANKS`. Agent markdown is full of `-` / `*` / `>` rows. Rejected: require a picker header heuristic (fragile across OpenCode versions).

KTD6. Typed-token echo is not session confirmation: a row whose stripped text equals the selected token, or that matches the menu-row regex, is not `"session"`. Confirmation needs the token on a non-menu row with additional context (for example `variant: high`). Rejected: wait-and-re-read until the echo leaves (unbounded).

KTD7. Account label from the visible tail: `pane_account_label` searches only the last three visible rows. The wrapper writes the statusline there; agent body text that names `user [personal]:` cannot certify the tenant. Rejected: first-match (statusline can sit below chrome). Rejected: whole-pane last-match (F117).

KTD8. Both inspect caps, tail-preserving: restore `PANE_INSPECT_MAX_CHARS = 65536` beside `PANE_INSPECT_MAX_LINES = 4000`. Trim rows from the head of the window until both bounds hold, never splitting a row. Rejected: rows only (F130). Rejected: bytes only (F45 mid-row cut).

KTD9. Structural test is a net, not a proof of impossibility: catch the enumerated AST shapes; document `getattr` / `sys.modules` as residual. The class docstring must not say an unguarded write is impossible by construction. Rejected: claim completeness the review already refuted.

KTD10. Release 1.5.0, floor stays 1.4.0: this repair changes behaviour of functions Orchestrate already imports (`session_has_started`, `redeliver`, `PaneWriter.write`). It does not add a new public name. `{#907-agent-launcher-floor-owner}` and `{#993-release-bump-owns-drift-guards}` apply: bump current version and the hardcoded current-version pin; do not lockstep the companion floor.

## Implementation Units

### U1. Composer classification

Fix F102 and F110 in `composer.py` so a quoted continuation is staged and a painted empty marker cannot authorize a write.

**Goal:** `_classify_row` / `_composer_blocks` absorb a `>` continuation of an empty Claude marker into the open block; `inspect_composer` returns the earlier staged block when the last block is an empty decoy with no content row between them.

**Requirements:** R1, R5

**Dependencies:** none

**Files:** `plugins/agent-launcher/skills/agent-launcher/scripts/composer.py`, `plugins/agent-launcher/tests/test_launcher_contract.py`

**Approach:** In `_composer_blocks`, when the open block has no visible text after the marker and the next row would be a terminator whose first printable character is in `COMPOSER_MARKERS` but is not this vendor's glyph, append it as continuation. In `inspect_composer`, walk blocks from the tail: if the last classified block is `EMPTY` and every row between it and a previous `STAGED` block is blank, return that staged inspection. Keep `test_an_empty_live_box_below_an_echo_reads_empty` green. Invert `test_a_weak_marker_under_a_decorated_box_is_content` to match R1.

**Patterns to follow:** `_classify_row` at `composer.py:198`, `inspect_composer` at `composer.py:345`, `{#907-composer-structural-continuations}`.

**Test scenarios:** TP-F102, TP-F110, TP-F110b.

**Verification:** `inspect_composer("❯ \n> quoted", vendor="claude").state` is `STAGED`. `inspect_composer("❯ draft\n❯ ", vendor="claude").state` is `STAGED`. Echo-below-content-row stays `EMPTY`.

---

### U2. Write-door observation and encapsulation

Failed composer reads refuse the write. `PaneWriter` doors live only inside `write`. Structural tests catch the enumerated evasions and the named mutation run exists.

**Goal:** `guard_pane_before_write` raises on `READ_FAILED` and `READ_TIMEOUT`. Nested Herdr calls replace `_raw`/`_type`. Detector and per-site mutation tests land.

**Requirements:** R4, R8, R12, R13, R18

**Dependencies:** none

**Files:** `plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py`, `plugins/agent-launcher/tests/test_launcher_contract.py`

**Approach:** In `guard_pane_before_write`, the `READ_FAILED`/`READ_TIMEOUT` branch records the note, sets `receipt["input_box"]`, and raises `SystemExit` naming the missing observation. Collapse `_raw` and `_type` into nested functions in `write`. Broaden `_raw_door_calls` to tuples, keyword `args=`, aliases, `subprocess.run`, and attribute calls named `_raw`/`_type`. Add `test_forcing_the_guard_off_at_each_write_site_is_observed` that, for each `PANE_WRITE_SITES` launcher function, copies the AST, replaces that function's `writer.write(...)` with a raw `run(["herdr","pane","run",...])`, and asserts the detector reports it. Add the five named-stop tests against `PaneWriter.write` and `launch`.

**Patterns to follow:** `guard_pane_before_write` at `launcher.py:832`, `PaneWriter` at `launcher.py:1638`, `test_every_pane_write_goes_through_the_one_writer`.

**Test scenarios:** TP-F104, TP-F114, TP-F120, TP-F121, TP-F134.

**Verification:** constructing `PaneWriter` and looking up `_raw` raises `AttributeError`. A timed-out inspect during a guarded write raises and records zero pane/prompt commands.

---

### U3. Session classification, receipts, and redeliver

One classification rule for #954, #969, and #970, plus the documented receipt key set and stale empty-box chars.

**Goal:** `done` is started. Redeliver and `_adopt_retry_receipt` refuse a finished or already-delivered session. Required receipt keys are enforced. Empty-box receipts drop the stale count.

**Requirements:** R2, R3, R6, R15

**Dependencies:** none

**Files:** `plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py`, `plugins/agent-launcher/README.md`, `plugins/agent-launcher/skills/agent-launcher/SKILL.md`, `plugins/agent-launcher/tests/test_launcher_contract.py`

**Approach:** Remove `"done"` from `NEVER_STARTED_STATUSES`. Update `redeliver`'s docstring to match the gate. In `_adopt_retry_receipt`, require `unit_name == unit.name` (missing is a miss), require `tab_id`, `owned` key present, `agent_name` present (no fallback to `unit.name` for the Herdr handle), and refuse when `prompt_delivered is True`. On the empty-box branch, `receipt.pop("input_box_text_chars", None)`. Split `test_redeliver_treats_done_and_unknown_as_never_started` so `unknown`/`None` still retry and `done` refuses.

**Patterns to follow:** `session_has_started` at `launcher.py:679`, `_adopt_retry_receipt` at `launcher.py:1879`, Orchestrate `cmd_redrive` at `orchestrate.py:5908` (reads the same function; no Orchestrate edit unless a call site still special-cases `done`).

**Test scenarios:** TP-F103, TP-F112, TP-F118, TP-F119, TP-F131.

**Verification:** `session_has_started({"agent_status":"done"}) is True`. `_adopt_retry_receipt` on delivered-plus-staged raises `RetryReceiptRefused`.

---

### U4. OpenCode picker parse, confirm, and redaction

Ladder-only options, echo is not confirmation, tokens stay out of notes and stops.

**Goal:** `parse_opencode_variants` ignores prose bullets. Confirmation requires non-echo session context. Notes and stops report counts, not tokens. `picker_menu_only` does not claim verified.

**Requirements:** R7, R9, R16

**Dependencies:** U2 (writer still the only door)

**Files:** `plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py`, `plugins/agent-launcher/tests/test_launcher_contract.py`

**Approach:** Filter parsed tokens through `OPENCODE_VARIANT_RANKS`. In `confirm_opencode_variant_selected`, ignore menu rows and rows whose stripped text equals the selected token. The existing `"variant: high"` fixture remains `"session"`. `append_unit_note` becomes `variant verified` without interpolating the token, and only when `seen_in == "session"`. Refusal `SystemExit` interpolates no option token.

**Patterns to follow:** `parse_opencode_variants` at `launcher.py:717`, `confirm_opencode_variant_selected` at `launcher.py:884`, `test_the_picker_refusal_reports_a_count_not_the_scraped_options`.

**Test scenarios:** TP-F113, TP-F115, TP-F132.

**Verification:** prose pane `- shipped\n> high` parses as `["high"]`. Pane `high\n> high` confirms `picker_menu_only`.

---

### U5. Bounds, containment, and account scrape

Timeout the workspace list, tail-limit the account scrape, restore the byte inspect cap, contain task-file writes.

**Goal:** Every remaining reliability/security finding in this inventory has a shipped-function test.

**Requirements:** R10, R11, R14, R17

**Dependencies:** none

**Files:** `plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py`, `plugins/agent-launcher/tests/test_launcher_contract.py`

**Approach:** Pass `timeout=20` (same as `list_tab_ids` / `live_agents`) from `workspace_id_for_name`. Search `pane_account_label` on `text.splitlines()[-3:]`. Add `tail_inspect_window` used by `pane_input_inspection`. After `assert_safe_path_component`, resolve `TASK_DIR / f"{unit.name}.md"` and refuse unless `TASK_DIR.resolve()` is in `resolved.parents` or equal, matching `resolve_task_file` at `orchestrate.py:843`.

**Patterns to follow:** `list_tab_ids` timeout at `launcher.py:111`, `resolve_task_file` at `orchestrate.py:843`, `pane_account_label` at `launcher.py:1100`.

**Test scenarios:** TP-F116, TP-F117, TP-F130, TP-F133.

**Verification:** a recording stub sees `timeout` on workspace list. A symlink under `.orchestrate/tasks/` to a path outside that directory raises before `write_text`.

---

### U6. Remaining test-only repairs

Wall-clock-free parser assertion and the F41 observer that compared the task write to itself.

**Goal:** TP-F135 and TP-F136 pass against the shipped functions without timing flakes or tautological compares.

**Requirements:** R19, R20

**Dependencies:** U1 (parser still classifies the hostile OSC input)

**Files:** `plugins/agent-launcher/tests/test_launcher_contract.py`

**Approach:** Rewrite `test_unterminated_osc_sequences_parse_in_linear_time` to call `inspect_composer` on the 16000-repeat hostile input, assert `STAGED`/`draft`, and assert `"\\x1b"` (ESC) is excluded in the OSC branch of `ANSI_RE.pattern`. Delete `elapsed < 2.0` and the `8 * small_time + 0.05` ratio. In `test_each_setup_line_and_the_task_are_separately_inspected`, assert `sends[2][4]` equals `launcher.normalize_task(...)` for that unit.

**Patterns to follow:** existing tests at `test_launcher_contract.py:2387` and `:2836`.

**Test scenarios:** TP-F135, TP-F136.

**Verification:** the complexity test source contains no `perf_counter` and no `elapsed`. The F41 test source contains `unit.task` or `normalize_task` in the third-write assertion.

---

### U7. Release surface 1.5.0

Bump Agent Launcher above 1.4.0 with triad parity and the current-version pin.

**Goal:** `plugin.json`, marketplace `agent-launcher` entry, and changelog name `1.5.0`. The hardcoded `== "1.4.0"` pin in `tests/test_agent_launcher_plugin.py` moves. Historical changelog assertions for 1.4.0 remain. Orchestrate floor stays `1.4.0`.

**Requirements:** R21

**Dependencies:** U1, U2, U3, U4, U5, U6

**Files:** `plugins/agent-launcher/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/agent-launcher/CHANGELOG.md`, `tests/test_agent_launcher_plugin.py`, `plugins/agent-launcher/tests/test_launcher_contract.py` (only if a current-version heading is asserted)

**Approach:** Grep the repo for `1.4.0` before the bump. Update every assertion that means "the version shipping today". Leave `AGENT_LAUNCHER_FLOOR_RELEASE` and historical changelog headings. Changelog records the classification, write-door, receipt, picker, and bound repairs and cites #1002.

**Patterns to follow:** `{#993-release-bump-owns-drift-guards}`, `{#907-agent-launcher-floor-owner}`.

**Test scenarios:** version-parity scenarios in the finite test plan.

**Verification:** the three surfaces print the same version, and that version is not `1.4.0`.

## Scope Boundaries

Out of scope: #908, #909, #910 and #886. Re-prioritizing P-levels. Nesting another parent under #1002. A fourth code-review cycle. Direct push to protected `main`. Production deploy beyond plugin/marketplace parity for a Claude Code pull.

Deferred: `getattr(sys.modules[__name__], "run")` and other dynamic door constructions the AST net does not catch (KTD9).

## Risks

| Risk | Mitigation |
|---|---|
| Inverting `test_redeliver_treats_done_and_unknown_as_never_started` hides a still-retryable `unknown` row | Split the parametrize; keep `unknown`/`None` green on the retry path |
| F102 absorption concatenates OpenCode menu rows into a Claude draft | Only absorb other-glyph terminators while the open block is still empty |
| F110 decoy rule refuses a real empty box under scrollback | Require no content row between the staged block and the empty marker |
| Orchestrate `cmd_redrive` still special-cases `done` | Read `orchestrate.py` around `session_has_started`; change only if it duplicates the old set |
| Stale `1.4.0` pin outside the triad | Grep before U7; the known pin is `tests/test_agent_launcher_plugin.py:134` |

## Success Metrics

Every TP-* scenario in the finite test plan is a passing pytest. `derived_overall` on the code-review `review_result.v1` is at least 9.0 within three cycles. GitHub `issue(number:1002).subIssues` are all `CLOSED`.
