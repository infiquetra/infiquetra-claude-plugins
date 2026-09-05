---
kind: doc-review
target: docs/plans/2026-09-01-issue-907-terminal-validation-repair-plan.md
classification: plan, issue-derived
reviewed_revision: d5179179f04564a3e43519dad0ff1606dcfa1229
reviewed_revision_plan_sha256: b74dbe5fe603b7d2e4c6e4c824c59ca77e68c3f4ddc58748f95ca61b783a3d8f
prior_review: docs/reviews/2026-09-01-issue-907-terminal-validation-repair-plan-document-review.md
prior_review_commit: 7c7347b4
authoritative_artifact: docs/code-reviews/2026-08-31-issue-907-terminal-validation-result.v1.json
linked_issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/907
blocked: true
outcome: not-ready
applied_fixes: none
pass: findings-closure
---

# Document review r2 — issue 907 terminal-validation repair plan

Round-1 findings D1–D8 are closed. The repair introduced one new P1: a named mirror mutant that would not die.

| field | value |
|-------|-------|
| target path | `docs/plans/2026-09-01-issue-907-terminal-validation-repair-plan.md` |
| reviewed revision | `d5179179f04564a3e43519dad0ff1606dcfa1229` (clean tree) |
| plan SHA-256 | `b74dbe5fe603b7d2e4c6e4c824c59ca77e68c3f4ddc58748f95ca61b783a3d8f` |
| prior review | `docs/reviews/2026-09-01-issue-907-terminal-validation-repair-plan-document-review.md` at `7c7347b4` |
| classification | Plan, under `docs/plans/`, issue-derived. Not reclassified. |
| review type | Findings-closure of D1–D8, plus an independent check of the planner's one-sided-proof sweep. No external-reviewer panel. Report-only; no dispatch. |
| linked issue | [infiquetra/infiquetra-claude-plugins#907](https://github.com/infiquetra/infiquetra-claude-plugins/issues/907) |
| blocked status | **yes** — one new P1 remains |
| applied fixes | none. Operator contract forbade editing the plan. Round-1 artifact left byte-identical. |
| review artifact path | `docs/reviews/2026-09-01-issue-907-terminal-validation-repair-plan-document-review-r2.md` |
| readiness verdict | `not-ready` |
| override rationale | n/a |

## Applied fixes

None in this session. The planner repaired the plan at `d5179179`. That commit touches only the plan file.

## Readiness summary

Not ready. D1–D8 close on evidence in the repaired plan. The planner's sweep of U7, U8 and U10 added mutants that do die under the tests they name. U1, U2, U5 and U9 already bound both sides. U11–U14 keep the omissions round 1 accepted.

The U4 mutant added with the D2 repair does not. Dropping the ownership half of `not session_owned(unit) or used_pane` leaves `used_pane`. A fresh launch starts with `used_pane=False`, so an owned first send is still uninspected and `test_freshly_created_pane_takes_no_inspection_path` stays green. The plan's own U4 approach text already states that fact. A kill list that cannot kill is the one-sided-proof class again.

Round 1's acceptance-criteria-clarity BLOCK (U4's two-read versus one-read contradiction) is lifted by the D2 repair.

## Closure of D1–D8

| id | priority | status | closing evidence |
|---|---|---|---|
| D1 | P1 | closed | Plan:262, :277, :282. Owned-plus-agent-prompt expects zero guard calls in total. `if True:` makes the loop record one call. |
| D2 | P1 | closed | Plan:294–312. Claude evidence is `["preflight", "guard"]` against frozen `["guard", "preflight"]`. Empty-then-staged is OpenCode-only and adds the second read. `test_empty_reused_box_is_prompted_exactly_as_today` stays one Claude read. Grounding row at plan:49 confirms those are the only read-count pins. |
| D3 | P1 | closed | Plan:99, :363–403. `redeliver` never runs the wrapper; `cmd_go` sends a marked unit through it; both happy paths assert one create and a stable `tab_id`. The owned path is a named scenario, not only the unowned evidence test. |
| D4 | P2 | closed | Plan:156. Clean transition now names owned-closed versus unowned-left-open. |
| D5 | P2 | closed | Plan:506, :520. Notice uses the reading Orchestrate version from its own manifest. Load-and-save writes no version key. |
| D6 | P3 | closed | Ledger rows 60 and 61: split, remaining slices named, row closes only when every slice has landed. |
| D7 | P3 | closed | Plan:670. Only U1 and U3 may swap. The dependency table is normative. U6 now depends on U3 and U4. |
| D8 | P3 | closed | Plan:103. KTD10 states the merge-first re-verification cost and points at Decision 4's table. |

## Remaining findings

| id | priority | status | title | plan anchor |
|---|---|---|---|---|
| D9 | P1 | open | U4 ownership-half mutant does not die | plan:321 |

### D9 — U4 ownership-half mutant does not die

The named mirror mutant for the owned-zero-inspection direction cannot fail the test it cites.

U4's proof list says: drop the ownership half of the predicate so an owned fresh session is inspected, and confirm `test_freshly_created_pane_takes_no_inspection_path` fails (plan:321). KTD4 is `not session_owned(unit) or used_pane` (plan:97). Dropping the ownership half leaves `used_pane`. `launch()` calls `_deliver` with `used_pane=False` (plan:306, :383). An owned fresh send therefore still skips the guard. The named test asserts zero ANSI reads on an owned create (`test_launcher_contract.py:636-649`) and stays green.

The same unit already writes the remaining predicate correctly: "used_pane is false before the first send of a fresh launch, so this reads `not session_owned(unit)` there" (plan:306). The mutant as written contradicts that sentence.

U3's `if True:` mutant is the one that actually forces an owned inspection. That is the kill U4 needs on the first-send site.

**Suggested fix:** Replace the U4 ownership-half mutant with `if True:` (or any predicate that is true on an owned fresh send) and keep `test_freshly_created_pane_takes_no_inspection_path` as the named kill.

## Sweep of the one-sided-proof class

Tested, not accepted from the planner's report.

| Unit | Planner claim | Ruling |
|---|---|---|
| U7 | Added: remove `session_owned` at the top of `close_run_session`; unowned no-Herdr-call assertion fails | Holds. An unowned `tab_id` then reaches `herdr tab close`. The edge scenario at plan:439 requires that assertion. Treating `None` as closed remains the other side. |
| U8 | Added: put `status` or `check` in the gated set; direction-not-fixed test fails | Holds. That test requires exit 0 in all three companion states (plan:477). Gating either command makes below-floor and unusable refuse. |
| U10 | Added: inspect regardless of ownership; owned-sends-without-a-read test fails | Holds. Plan:550 names that test. An owned worker would then record a pane read. |
| U1, U2, U5, U9 | Already bound both sides | Holds. U1's idle-versus-staged counter-cases and named clause kills; U2's visible-versus-unstyled pair; U5's broken-versus-healthy loader; U9's failed-ingest restore plus the monkeypatch success counter-cases. |
| U11–U14 | Keep the omitted sections | Holds. Same reasons as round 1. |
| U4 | Ownership-half mutant binds the owned-zero-read direction | Fails. That is D9. |
| U3, U6 | Both-sides lists after the D1 and D3 repairs | Holds. U3 `if True:` dies on the zero-call test. U6 `used_pane=False` on `redeliver` dies on the owned still-staged launcher test; `cmd_go` calling `launch` dies on the one-create assertion. |

## Residual risk

CORR-01's styled wrap is still constructed. Grok, Agy and Qwen still have no capture. Decision 1 still gates R5 on `review-result` and `land`. Redelivery's `since=None` account floor and the repeated OpenCode picker are stated trades, not silent gaps.

Identifiers `D1`–`D9` are this document-review's keys. Terminal-validation identifiers cited above are from `docs/code-reviews/2026-08-31-issue-907-terminal-validation-result.v1.json` unless the prior-validation artifact is named in the same sentence.

The round-1 artifact, every other review JSON, cycle state, and the append-only evidence ledger were not modified.
