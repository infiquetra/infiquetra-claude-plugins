# Doc-review — saga.py branch refresh (#480) plan

**Verdict: READY to drive implementation. Not blocked.** Four citation-accuracy safe fixes
applied in place; zero findings remain. The plan's decisions (live-git-wins for `branch`;
`head_sha`/`last_commit_sha` deferred) are grounded and its requirement mapping is complete.

## Review-result contract

| Field | Value |
|---|---|
| Target | `docs/plans/2026-07-05-saga-branch-refresh-480-plan.md` |
| Reviewed revision | working tree (uncommitted plan) |
| Blocked | No |
| Findings remaining | 0 (P0: 0 · P1: 0 · P2: 0 · P3: 0) |
| Safe fixes applied | 4 (citation corrections) |
| Linked issue | [#480](https://github.com/infiquetra/infiquetra-claude-plugins/issues/480) |
| Linked plan | `docs/plans/2026-07-05-saga-branch-refresh-480-plan.md` |
| Review artifact | `docs/reviews/2026-07-05-saga-branch-refresh-480-doc-review.md` |

## Applied fixes (citation accuracy — source is the evidence)

| # | Location | Was | Now | Why |
|---|---|---|---|---|
| 1 | Problem Frame, "Observed" bullet | `_do_branch_delete` (`ship_ceremony.py:308-317`) | `:322-331`, guard `:325-328` | `:308-317` is `_do_checkout_main`'s neighborhood; `_do_branch_delete` starts at `:322`. The wrong number was copied verbatim from the issue body. |
| 2 | Problem Frame, refresh-block cite | `saga.py:748-752` | `saga.py:746-752` | Block starts at the `git = current_git_state` line (`:746`) and the `branch` clause (`:747-748`), not mid-clause. |
| 3 | Problem Frame, `_merge` carry-forward cite | `saga.py:614-618` | `saga.py:613-617` | Scalar carry-forward comment is `:613`, the `if/else` runs `:614-617`. |
| 4 | U1 edit-site cite | `save()` (`~:748`) | `save()` (refresh block `:746-752`) | Same block-start correction as #2. |

## Verified-correct (adversarially checked, no change needed)

- **Ceremony order** — `commit → open_pr → request_review → merge → checkout_main → pull →
  branch_delete` matches `ship_ceremony.py:86-92` exactly.
- **KTD2 sibling cite** — `head_sha`/`last_commit_sha` at `saga.py:749-752` is correct
  (head_sha `:749-750`, last_commit_sha `:751-752`).
- **Consumer audit** — `head_sha` → `status_card.py:307` (display-only CI ref);
  `last_commit_sha` set only in `scaffold_checkpoint.py:81`, no behavior-gating consumer;
  `work/SKILL.md:151` is the re-save-on-work-branch instruction the fix makes true.
- **Regression risk** — the only `.branch ==` assertion in the suite is the single-save
  first-capture case (`tests/test_saga_saga.py:375`), preserved by the change. No test depends
  on `branch` carrying forward across a git-branch change.

## Residual risk

Low. The fix is a one-guard change plus two tests, and every load-bearing claim is now cited to
verified source. The only judgment call is the KTD2 scope boundary (branch-only), which is
documented with the safety audit that would justify a follow-up — so a reviewer will read the
`head_sha`/`last_commit_sha` asymmetry as deliberate, not an oversight.

## Addendum (post-review, during `/work`) — KTD1 was reversed

This review passed the plan when KTD1 was *pure* live-git-wins (drop the first-save-only guard
outright). During `/work`, the test gate found that direction broke two `test_ship_ceremony.py`
tests: the ceremony records progress via `saga.py save` after every transition, so the save after
`checkout_main` reset `branch` to `main` right before `branch_delete`. KTD1 was corrected to a
**protected refresh** (auto-refresh, but never downgrade a stored work branch to `main`/`master`),
a new R5 + regression test were added, and the plan/DECISIONS were updated to match.

**Why doc-review didn't catch it:** the flaw was a *runtime interaction* between `save()` and the
ceremony's progress-save sequence, not a citation error, a readiness gap, or an unstated
assumption in the document. The plan's own claim "the ceremony never re-saves the saga" was the
wrong premise — and verifying that claim required running the ceremony (the test gate), not
reading the doc. This is the honest boundary of a doc-review pass: it checks whether the document
can *drive* implementation, not whether the design *survives execution*. The two gates are
complementary, and here the second one earned its keep.
