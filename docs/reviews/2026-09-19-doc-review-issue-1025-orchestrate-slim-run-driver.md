# Document review — issue 1025 orchestrate slim-driver plan

**Verdict: ready to drive implementation. Not blocked — no `P0` and no `P1` remains open.**

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-19-issue-1025-orchestrate-slim-run-driver-plan.md` |
| Reviewed revision | working tree, on branch `issue/1025` at base commit `4e951f0e` |
| Classification | plan (path `docs/plans/`, carries `origin:`, `Implementation Units`, `Key Technical Decisions`, and a `U1` prefix) |
| Rubric phase | none — the formal software-development-lifecycle rubrics cover the idea, issue, and spec phases; a plan document runs the readiness-skeptic pass only |
| Blocked | no |
| Rounds | two repair rounds, both applied in place |
| Linked issue | infiquetra/infiquetra-claude-plugins#1025 |
| Saga | `issue-1025`, plan tick `20260920-025711` |

## Applied fixes

Nine findings were repaired in the document itself. Each was backed by the document, the card, or
source in this repository at base commit `4e951f0e`; none invented a decision.

| # | Priority | What was wrong | What was done |
|---|---|---|---|
| D1 | P1 | The plan repeated issue 879's claim that `assert_review_transport` is not among the assertions `start` runs. That claim is stale: the call is at `orchestrate.py:1103` inside `plan_units`, and `cmd_start` calls `plan_units` at `orchestrate.py:3441` | KTD9 now states the contradiction with both line numbers and says the implementer follows the code, not the sentence |
| D2 | P1 | A unit left at `merge_state = merging` by a turn whose process died had nothing to clear it, and with no expiry it would block every later turn forever — card 992's failure shape in a new place | KTD6 now derives the refusal on read: git is asked whether a merge is in flight, and a row git does not confirm is reset to `ready` with a line saying the previous turn did not finish |
| D3 | P1 | The `main` regression guard compared against `origin/main` without refreshing it, so a stale remote-tracking ref would make the guard pass silently — the same quiet failure card 875 reported | KTD6 now fetches `origin main` first and refuses the turn when the fetch fails |
| D4 | P1 | U5 removed the landing worktree but never said where a merge then happens, leaving the implementer to invent it | U5 now names it: one detached worktree per turn, created and removed inside the turn, with the bookkeeping around it (the conflict pointer, the numbered fallback, the retained-merge recovery) being what "landing reservations" removes |
| D5 | P1 | The width bound counted only orchestrate's own units, so a run with six role panes and ten units would put sixteen sessions on one account against a number that exists for the account's rate limit | KTD10 now counts open `roster` rows as well as `running` units, with two test scenarios |
| D6 | P1 | The plan never said whether `start` creates the record or requires one | U1 now states that admission writes the record and `start` refuses with exit 2 and names the admission command when there is none, with two test scenarios |
| D7 | P1 | `shared_blockers` had no named producer, so an implementer would have to invent one | KTD11 now states that orchestrate is only the reader, and names the guess it rejects |
| D8 | P2 | Two different things are called "roster" — the record's role-session rows and orchestrate's vendor-listing subcommand | U1 now separates them in one paragraph |
| D9 | P2 | Two counts were wrong: 24 test modules and 19,595 lines, against a measured 26 modules and 17,953 lines. `merge --clean` was never said to exist, though card 960 is about that flag. U6 and U8 disagreed about which unit deletes a test module | Counts corrected; `merge --clean` stated with its card-960 meaning; U8 given an explicit four-module deletion table with the rule that governs it |

## Remaining findings

| # | Priority | Finding | Status |
|---|---|---|---|
| D10 | P2 | The plan does not say what happens to a `.orchestrate/` directory that already exists on an operator's machine when 5.0.0 lands. The version is a major bump and the changelog names the record move as breaking, so no data is silently misread — but no migration or cleanup step is named either | open, accepted |
| D11 | P3 | The plan carries an open operator question about whether the board-writeback path leaves orchestrate in this release or with issue 1028. It is declared with a gate marker and the plan states the keep-it reading so work can proceed, so it does not block implementation | open by design |

Neither remaining finding blocks `/work`.

## Residual risk from limited evidence

Two claims in this plan rest on documents rather than on execution, and are named so a later reader
does not mistake them for measurements. First, the five recorded collisions are taken from the
simplification review and the child cards; no collision was reproduced during this review. Second, the
merge-turn design follows the software-development-lifecycle repository's parent-branch chapter at
revision `5efc869f`, which marks itself forward-looking — "none of it is implemented yet" — so this
card is the first implementation of that chapter and nothing exists to compare it against.

## Review artifact

This file: `docs/reviews/2026-09-19-doc-review-issue-1025-orchestrate-slim-run-driver.md`.
