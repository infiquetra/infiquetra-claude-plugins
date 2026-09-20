# Document review — issue 1023 plan, the saga run record and the admission questionnaire

**Verdict: ready to drive implementation. No P0 or P1 finding remains open.**

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-19-issue-1023-run-record-and-admission-plan.md` |
| Reviewed revision | working tree, branch `issue/1023`, base `550ae6ce` (`origin/parent/1018`) |
| Classification | plan (path `docs/plans/`, carries `origin:`, `Implementation Units`, `Key Technical Decisions`, `U1`) |
| Rubric engine | not run — the rubric phases are `idea` and `issue`; a plan takes the readiness-skeptic pass only |
| Blocked | no |
| Rounds | two review rounds, eight safe fixes applied in place |
| Linked issue | infiquetra/infiquetra-claude-plugins#1023, child of #1018 |

## Applied fixes

Eight, all supported by the document itself or by code read in this worktree.

| Key | Priority | What was wrong | Fix |
|---|---|---|---|
| D1 | P1 | The record's top-level key set was never stated, so an implementer and every later child would each invent one — on the card whose whole point is a fixed schema. | Added KTD4a naming eleven top-level keys, what each holds, and the missing-key rule. |
| D2 | P1 | Both the run record and the saga envelope carry `next_step` and the plan did not say which wins on a disagreement. | Added KTD8a: the record is authoritative, the envelope mirrors it, nothing reconciles backwards. |
| D3 | P1 | Nothing said how two writers are handled, and the parent's stop conditions say to stop if a child needs a lock — so silence invited an implementer to add one. | Added KTD4b: atomic write then replace, no lock, no lease, `updated_at` is what a reader compares. |
| D4 | P1 | Two different things are called "destination" — saga's four-value routing intent and the lifecycle repository's lower-environment parameter — and the schema held both without distinguishing them. | Added the "Two things called destination" paragraph under KTD4a, citing `saga.py:78`. |
| D5 | P2 | No requirement-to-unit mapping, so a unit could be finished without anything to check it against. | Added the "Requirements to units" table covering R1 through R15. |
| D6 | P2 | The plan did not say whether admission runs all six of the lifecycle repository's issue-review checks or only the card validator. | Added a scope boundary: check one only; checks two through six are the Issue Reviewer's judgment and are recorded as `not_performed` until issue 1024 staffs the role. |
| D7 | P2 | `admission.py`'s arguments were undefined beyond `--issue`. | Named `--repo` (defaulting to the `origin` remote), `--dry-run`, `--answers`, and `--store-root`. |
| D8 | P3 | Three citations were wrong: a `--path-format=absolute` flag `resolve_common_dir` does not pass, `saga.py:264` for the `extra` field (it is 261), and "nine technical decisions" (there are twelve). | All three corrected against the files in this worktree. |

Two further corrections went with them: the ledger-replacement table said `approval_scope` sits under
`run_configuration` when it is a top-level block, and four new test scenarios were added to U1, U2 and
U4 so each of D1, D2, D3 is proved rather than merely asserted.

## Remaining findings

| Key | Priority | Status | Finding |
|---|---|---|---|
| D9 | P3 | open | U6 does not name the version number to bump the saga plugin to. Deliberate: the run coordinator renumbers versions when it folds `main` into the integration branch, so a number fixed now would be wrong by merge time. |
| D10 | P3 | open | The `.saga-profile.json` file this card adds to this repository has no schema-validation test of its own; the reference document describes it and the admission tests exercise a fixture profile. Worth revisiting if a second repository gets a profile. |

## Residual risk from limited evidence

The lifecycle repository was read at its pinned revision `5efc869f` through
`git show`, never at its working tree, so the thirteen run-configuration parameters and the seven
approval boundaries are quoted from the pin this whole parent is built against. If that pin moves
under issue 170's amendment, KTD4's table is the thing to re-check first.

The staffing component (issue 1021) and the roles library (issue 1022) were read on this card's base
commit, not at whatever they become after the coordinator folds `main` forward. The plan depends on
`staffing.resolve_role` and the vendored `lifecycle-snapshot.json` keeping their current shapes.
