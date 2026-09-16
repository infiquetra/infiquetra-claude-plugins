---
title: Issue 1002 Agent Launcher findings — plan document review
type: review
status: complete
date: 2026-09-16
assignment: issue-1002-plan-doc-review
verdict: accepted
blocked: false
candidate: working tree after plan repairs
reviewed:
  - docs/plans/2026-09-16-issue-1002-agent-launcher-findings-plan.md
  - docs/plans/2026-09-16-issue-1002-agent-launcher-findings-finite-test-plan.md
---

# Issue 1002 Agent Launcher findings — plan document review

The plan can drive `/work`. Remaining P0 and P1 findings were repaired in the plan before implementation.

## Applied fixes

D1. U1 now names the two test inversions (`test_a_weak_marker_under_a_decorated_box_is_content`, `test_adjacent_staged_and_empty_marker_rows_are_ambiguous`) and the two tests that must stay green (`test_an_empty_live_box_below_an_echo_reads_empty`, `test_a_quoted_row_below_staged_text_is_not_the_composer`). Without those names an implementer would leave F110's adjacent-decoy case as `UNCLASSIFIABLE`, which still authorizes a write.

D2. U1 now stops other-glyph absorption once the open block has visible text, so OpenCode menu rows under a filled Claude box are not concatenated into the draft.

D3. U2 now specifies `SystemExit` (not `StagedInputError`) for `READ_FAILED`/`READ_TIMEOUT`, with the message tokens `input box {state}` and `refusing to prompt`.

D4. U2's mutation test covers every `PANE_WRITE_SITES` row, including `orchestrate.py`.

D5. U3 now treats a missing `unit_name` as a miss, forbids the `agent_name` fallback, and states that `owned` must be present but need not be `True`.

## Readiness summary

Issue-phase cores: acceptance criteria map to named pytest functions in the finite test plan; devil's advocate finds one classification cluster (#954/#969/#970) rather than three designs; spec fidelity traces each R-ID to a child of #1002. No remaining P0 or P1.

## Remaining findings

| ID | Priority | Status | Finding |
|---|---|---|---|
| D6 | P2 | open | Residual `getattr`/`sys.modules` door constructions stay undocumented in the class docstring until U2 lands; KTD9 already accepts this. |
| D7 | P3 | open | Orchestrate `cmd_redrive` copies the `session_has_started` gate in prose; U3 says read it and edit only if it duplicates the old `done` set. |

## Rubric notes

| Rubric | Score | Note |
|---|---|---|
| acceptance_criteria_clarity | 9 | Each R-ID names a shipped function and a TP-* test. |
| devils_advocate_issue | 9 | Twenty-one findings, one plugin, one release. Cluster of three issues is the smallest slice that keeps one vocabulary. |
| spec_fidelity | 9 | Origin is issue 1002 plus the finite test plan. Non-goals match the parent. |

## Review-result contract

- target path: `docs/plans/2026-09-16-issue-1002-agent-launcher-findings-plan.md`
- reviewed revision: working tree after D1–D5
- blocked: false
- linked issue: #1002
