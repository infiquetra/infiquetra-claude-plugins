# Document review — issue 1028 plan

**Target:** `docs/plans/2026-09-20-issue-1028-integrate-release-functional-test-close-plan.md`

**Reviewed revision:** working tree on branch `issue/1028`, base commit `87a5329e`
(`origin/parent/1018`)

**Classification:** plan (path `docs/plans/`, carries `origin:`, `Implementation Units`,
`Key Technical Decisions`, and a `U1` unit). No formal idea-phase or issue-phase rubric applies, so
the readiness-skeptic pass ran alone, with the deployment-readiness and security/operations lenses
triggered by the release, merge and external-board content.

**Blocked status:** not blocked. No `P0` or `P1` finding remains open.

## Verdict

The plan can drive implementation. Three rounds ran; every finding above `P2` was repaired in place
and the repairs are evidence-backed, not preference.

## Findings

| Key | Priority | Finding | Status |
|---|---|---|---|
| D1 | P1 | The card's first acceptance criterion asks the dry run at the review-acceptance boundary to print "the single move it would submit", but that boundary has no row in the lifecycle repository's allowed submissions, so no honest single move exists | fixed — KTD2a states how the criterion is judged and names the concrete repair it does not take |
| D2 | P1 | Three requirements (the release, the recorded absence of a destination, the closeout comment) lived only in skill prose and had no executable guard | fixed — KTD6a adds `release_step.py` and unit U8 with its test scenarios |
| D3 | P1 | "`main` is re-integrated into surviving branches" was one sentence covering two different merges, so an implementer would do one of them | fixed — R5 now names both, and U2's scenarios test both |
| D4 | P1 | `fetch_default_branch` was cited at `orchestrate.py:4912`, which is `release_unit_worktree`; the function is at `:4870` | fixed — verified with `grep -n` and corrected |
| D5 | P2 | The repository allows merge, squash and rebase merges, so the commit that lands is not always the head the checks ran against | fixed — KTD6b records both, with the merge method that connects them |
| D6 | P2 | Waiting for required checks had no stated mechanism, and this repository's journal records a squash merged on a watch command's word while the merge state was `UNSTABLE` | fixed — KTD6aa binds the merge to the checked head and classifies from `mergeStateStatus`, citing `DECISIONS.md:9485` and `LEARNINGS.md:11001` |
| D7 | P2 | An importer repair in U4 could quietly become a module deletion belonging to issue 1030 | fixed — one stated rule governs every repair, with the deferral as its fallback |
| D8 | P2 | `next_step` is written here and continued by issue 1029, with no statement of where the boundary sits | fixed — stated in the run-record fields section |
| D9 | P2 | The route from the new boundary command into Mission Control was unnamed | fixed — the design now names the reconcile controller and the submission primitive behind it |
| D10 | P3 | The plan is long for a reader who only needs the boundary table | open — accepted; the table is a section of its own and the summary points at it |

## Applied fixes

All nine repairs above were applied in place to the plan document. Each is supported by the document
itself, by the lifecycle repository at its pinned revision, by this repository's code and journal, or
by a live `gh` read — none invents a requirement or resolves a product decision.

## Residual risk from limited evidence

One thing this review could not settle and deliberately did not paper over: the card's fourth
acceptance criterion names two board statuses — `Ready to merge` and `Closeout` — that the live
Operations board carries and the lifecycle repository does not allow saga to submit. The plan
reports that to the operator under KTD2 rather than choosing a side. Until it is answered, the
criterion is proved against the allowed vocabulary, and a reader comparing the card's wording with
the shipped behaviour will see a difference that is intentional.

## Links

- Plan: `docs/plans/2026-09-20-issue-1028-integrate-release-functional-test-close-plan.md`
- Card: `infiquetra/infiquetra-claude-plugins#1028`
- Run record: `<primary checkout>/.claude/saga/runs/issue-1028.json`
