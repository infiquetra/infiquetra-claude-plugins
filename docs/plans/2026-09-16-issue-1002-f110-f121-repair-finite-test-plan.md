---
title: Finite test plan — Agent Launcher F110/F121 repair after 1.5.0
type: test
status: active
date: 2026-09-16
origin: docs/plans/2026-09-16-issue-1002-agent-launcher-findings-finite-test-plan.md
backend: inline
---

# Finite test plan — Agent Launcher F110/F121 repair after 1.5.0

1.5.0 landed the twenty-one issue 1002 children, then a post-merge skeptic showed two of those contracts still fail. This table exists before the repair commit. Every scenario calls a shipped function. No scenario re-implements the unit under test, mocks it, or special-cases a snippet so the assertion can pass without the detector reporting a stray door.

## Key Technical Decisions

KTD1. F110 tests call `inspect_composer`. F121 tests call `_raw_door_calls` on every snippet, including an f-string element-0 case.

## Implementation Units

### U1. Finite scenario table

The table below is the executable unit. Implementation is the companion plan `docs/plans/2026-09-16-issue-1002-f110-f121-repair-plan.md`.

## How to run

```bash
python3 -m pytest plugins/agent-launcher/tests/test_launcher_contract.py::test_blank_separated_empty_marker_below_staged_is_a_decoy plugins/agent-launcher/tests/test_launcher_contract.py::test_two_trailing_empty_markers_below_staged_are_decoys plugins/agent-launcher/tests/test_launcher_contract.py::test_an_empty_live_box_below_an_echo_reads_empty plugins/agent-launcher/tests/test_launcher_contract.py::test_structural_detector_kills_enumerated_evasion_shapes plugins/agent-launcher/tests/test_launcher_contract.py::test_every_pane_write_goes_through_the_one_writer -q
```

| ID | Issue | Finding | Shipped function | Input | Action | Expected outcome | Test |
|---|---|---|---|---|---|---|---|
| TP-F110c | #961 | Blank-separated empty marker classifies EMPTY | `inspect_composer` | `❯ staged draft\n\n❯ ` vendor `claude` | classify | `STAGED` text `staged draft`, not `EMPTY` | `test_blank_separated_empty_marker_below_staged_is_a_decoy` |
| TP-F110d | #961 | Two trailing empty markers classify UNCLASSIFIABLE | `inspect_composer` | `❯ staged draft\n❯ \n❯ ` vendor `claude` | classify | `STAGED` text `staged draft`, not `UNCLASSIFIABLE` | `test_two_trailing_empty_markers_below_staged_are_decoys` |
| TP-F110b | #961 | Content row between echo and empty box | `inspect_composer` / `composer_staged_text` | `❯ earlier submitted prompt\npane output line\n❯ ` | classify | empty string (CORR-05 last-block-wins) | `test_an_empty_live_box_below_an_echo_reads_empty` |
| TP-F121 | #972 | Enumerated evasions miss `_raw_door_calls` | `_raw_door_calls` | each snippet in `test_structural_detector_kills_enumerated_evasion_shapes` | parse and walk | helper returns a non-empty list; no special-case `return` in that test | `test_structural_detector_kills_enumerated_evasion_shapes` |
| TP-F121b | #972 | Production files still walk the same helper | `_raw_door_calls` | AST of `launcher.py` and `orchestrate.py` | walk | two doors inside `PaneWriter`; zero strays outside it; orchestrate empty | `test_every_pane_write_goes_through_the_one_writer` |

## Evasion snippets TP-F121 must report

| Snippet | Detector must report |
|---|---|
| `subprocess.run(['herdr','pane','run','p','t'])` | stray door |
| `argv=['herdr','pane','run','p','t']; run(argv)` | stray door |
| `run(('herdr','pane','run','p','t'))` | stray door |
| `run(['herdr']+['pane','run','p','t'])` | stray door |
| `HERDR='herdr'\nrun([HERDR,'pane','run','p','t'])` | stray door |
| `run([f'herdr','pane','run','p','t'])` | stray door |
| `run(args=['herdr','pane','run','p','t'])` | stray door |
| `_run=run\n_run(['herdr','pane','run','p','t'])` | stray door |
| `writer._raw('t', door='pane')` | stray door |
| `if not session_owned(unit):\n    guard_pane_before_write(unit, pane)` | inline predicate |
| `guard_pane_before_write(unit, pane) if not session_owned(unit) else None` | inline predicate |
| `w.write('t')` | write site |
