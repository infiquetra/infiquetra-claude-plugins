# Work session — board vocabulary drift, issue 1020

**What shipped.** The mission-control plugin's cached snapshot of the three GitHub project boards
was two board migrations stale. It is regenerated from the live boards, the prose that described
the old vocabulary is rewritten, a credential-free drift guard is added so the gap cannot reopen
silently, and a stale workflow label in the shipped project mappings is removed.

## Units executed

| Unit | What it did | Verified by |
|---|---|---|
| U1 | `board_census.py` now writes `fields` as a mapping keyed by field name, raising on a duplicate name | `plugins/mission-control/tests/test_board_census.py`, 12 passed, including a new duplicate-name test |
| U2 | Regenerated `config/board-schema.json` from the live boards | The card's two `jq` acceptance checks; the diff matched the plan's predicted field membership exactly |
| U3 | Added `tests/test_board_schema_drift.py` | 14 passed, 1 skipped (the opt-in live leg); proven red first — 12 failures against the pre-regeneration census |
| U4 | Rewrote the board reference and board skill onto `stage_flow`, deleted the withdrawn work-in-progress limits, corrected the terminal-status tables in the metrics skill and its reference | The card's `grep -n "retired"` check returns nothing; both completeness sweeps clean; `test_prompt_alignment.py` still passes |
| U5 | Removed the three stale `workflow` labels from `config/project-mappings.json` | New `TestVendoredMappingsDoNotOverrideTheBoardWorkflow` class, 3 tests; the vendored file now resolves `stage_flow` for all three boards |
| U6 | Release surfaces to 2.17.0 and the journal entries | `sync_marketplace.py`; the repository gate |

## How the drift guard was proven

The plan required observing the new guard fail before trusting it, because a guard only ever seen
green is not known to guard anything. Restoring the census as it stood at the branch base and
re-running gave 12 failures, 1 pass and 1 skip. The single pass was the board-presence assertion,
which the plan predicted would pass beforehand. Restoring the regenerated census returned it to 13
passed, 1 skipped.

## What code review changed

Two rounds of repair landed after the first implementation commit, and both are worth naming
because each closes a hole the implementation had left.

**The plan's blast-radius analysis was wrong, and the way it was wrong is reusable.** Planning
searched the repository for the strings `board-schema` and `board_schema` and concluded that only
the census script and its own test consumed the shape. That search finds files that name the
artifact. It cannot find `plugins/mission-control/config/generated/check_issue_contract_parity.py`,
which imports `board_census.fetch_project_fields_census` and consumed the result positionally.
Under the mapping, that raises `TypeError`. It would not have been caught by the repository gate or
by continuous integration either, because the broken path is live-gated and skips without a
`project`-scoped token, and because the parity tests inject their own fixture in place of the real
producer — so the suite agreed with itself while production would have disagreed. Fixed in commit
`b02b3597`, verified by running the live leg against the real boards.

**The new drift guard could have silently covered nothing.** Every assertion in it is parametrized
over the list of active boards, and nothing asserted that list was populated. Had
`sdlc-schema.json`'s board `status` key been renamed — the very drift class the guard exists to
catch — the parametrized cases would have collected zero tests and the module would have reported
passed. Confirmed against pytest rather than assumed: with an empty list the loop test passes, the
parametrized test is skipped, and only an explicit guard fails. Fixed in commit `f9d3a50f`, together
with three smaller findings about error handling around the new duplicate-name exception.

## The fresh review round, and the decision it reached

**Decision: the round did not accept, and the driver stopped rather than opening a third.**

Round one ended at 7.6 with an open P1. The coordinator directed a repair and a fresh round rather
than an override, on the reasoning that the finding was concrete and the fix known — which it was.
Round two ran the same seven lenses on the repaired tree with a fresh repair allowance, and finished
at 8.5 with every dimension above the 7.0 floor. Two P2 findings remained. Both are now repaired in
`b7b859bf`; no lens has reviewed that commit, because a third round is the operator's call.

One repair inside round two was not an improvement but a correction of harm the driver had just
done: the `flow set-field` line added to `agents/sdlc-operator.md` to fix the Stage-and-Status
pairing omitted a required `--project` argument and exited 2. Shipping a documented command that
cannot run is worse than the omission it was meant to fix, so it was corrected even though the
round's re-review budget had been used. That is the one case where completing a botched repair was
judged not to be the same thing as opening a new cycle.

**What the two rounds actually bought.** Fourteen findings were raised and closed across four review
passes. Six of them were defects a previous repair had introduced. The counter-measure that worked
was mechanical, not attentional: prove a guard red before trusting it green, and mutation-test a
test by reverting the fix it covers. Every guard in `tests/test_board_schema_drift.py` has now been
watched to fail against a tree that should trip it, and the newest two were confirmed to die when
their fix is reverted. The test count rose from 526 to 541, and thirteen of the additions exercise
the guard's own logic with synthetic input rather than against prose that happens to be clean.

## Answers applied, and where each came from

Every choice below was supplied by the run coordinator before work began, in the message opening
this stage. None was invented, and none was taken from chat memory.

| Choice | Answer applied | Source |
|---|---|---|
| Saga identity | Resumed `issue-1020`; no second saga minted | Coordinator |
| Branch | Stayed on `issue/1020`; no new branch | Coordinator |
| Execution backend | `inline`, matching the plan's `backend:` frontmatter; no other backend offered or entered | Coordinator, and the plan document |
| Doc-review gate | Passed, zero P0 and zero P1, per `docs/reviews/doc-review-issue-1020-2026-09-19.md`; no override sought | Coordinator |
| Complexity triage | Small-to-medium: build a task list from the plan's unit identifiers rather than implementing directly | Skill default, recorded here |
| Round-N detection | Fresh build — the restored saga carries no pull-request references, so this is not a re-entry into the round-N loop | Skill default, confirmed from the saga scan |
| Board write | Submitted the `Stage` = `Active`, `Status` = `Implementing` pair through the reconcile controller; the record came back `written` with `field` reading `Stage+Status`, so both halves landed | Coordinator permitted this write |
| Pull request | None opened | Coordinator |
| Merge | None; the card merges onto the integration branch `parent/1018` by merge turn, performed by the coordinator | Coordinator |
| Ship ceremony | Not run | Coordinator |
| Push | Never | Coordinator |
| Continuation routing | Return to the coordinator | Coordinator |

## Deviation from the skill, recorded

The `/work` skill reaches a pull-request-ready boundary and then offers to open a pull request and
to merge. Both were declined by standing instruction, because this card is a child of the saga
simplification parent (issue 1018) and lands on the integration branch by merge turn rather than
through its own pull request. No ship ceremony ran and nothing was pushed.

## Residual risk

The census regeneration reached the live GitHub Projects API using this session's `project`-scoped
token. A session without that scope cannot run unit 2 and must stop rather than hand-edit the
census — a hand-written census is the failure this card exists to repair.
