---
title: Code review — issue 1002 F110/F121 repair
type: code-review
status: accepted
date: 2026-09-16
reviewed_revision: 5be9e76125232b288945e2b1b0e3b4b51b07e1e8
cycle: 2
outcome: accepted
derived_overall: 9.33
plan: docs/plans/2026-09-16-issue-1002-f110-f121-repair-plan.md
---

# Code review — issue 1002 F110/F121 repair

Cycle 2 accepted. Mean derived overall 9.33. Applicable-dimension floor met. No remaining P0 or P1. One repair iteration (ANSI-stripped blank predicate).

## Scope check

CLEAN. Composer decoy walk, production `_raw_door_calls` expansion, 1.5.1 triad, journal, and the repair plan/test-plan.

## Plan completion

| ID | State | Evidence |
|---|---|---|
| U1 | DONE | `_row_without_sgr` shared; blank/ANSI/two-trailing dumps `STAGED`; CORR-05 `EMPTY` |
| U2 | DONE | `_raw_door_calls` reports every enumerated snippet; snippet test has no special-case return |
| U3 | DONE | 1.5.1 triad; Orchestrate floor `>=1.4.0` |

## Lenses (always-on)

| Lens | cycle | derived_overall | accepted |
|---|---:|---:|:---:|
| architecture-maintainability | 2 | 9.43 | yes |
| correctness | 2 | 9.40 | yes |
| security | 2 | 9.00 | yes |
| testing | 1 (delta-checked on 5be9e761) | 9.50 | yes |

## Cycle 1 (8b396a98) — repairs_requested

`_only_blanks_between` used raw `str.strip`, so `inspect_composer("❯ staged draft\n\x1b[0m\n❯ ", vendor="claude")` was `EMPTY` and authorized a write. Architecture 8.86, correctness 8.6, security 8.8. Testing 9.5.

## Cycle 2 repairs

Share `_row_without_sgr` with `_classify_row`. `test_ansi_only_separator_below_staged_is_a_decoy` drives the SGR-only and background-spacer dumps. CORR-05 test renamed to `test_content_row_between_echo_and_empty_marker_is_live_empty`.

Verified on 5be9e761: ANSI-reset and background-SGR spacers are `STAGED`; `guard_pane_before_write` raises `StagedInputError`; CORR-05 stays `EMPTY`.

## Findings

None at P0 or P1 after cycle 2.

Residual, not scored: `ANSI_RE` strips CSI and OSC. A non-CSI leftover (`ESC(B`, C0) is not in the in-tree `herdr --format ansi` captures. No 75+ finding.

## Independent gates

Tests: `plugins/agent-launcher/tests/test_launcher_contract.py` and `tests/test_agent_launcher_plugin.py` — 418 passed on 5be9e761.

Typed result: `docs/code-reviews/2026-09-16-issue-1002-f110-f121-repair-cycle2-result.v1.json`
