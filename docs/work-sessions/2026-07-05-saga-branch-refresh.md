# Work session — saga.py branch refresh (#480)

- **Date:** 2026-07-05
- **Issue:** [#480](https://github.com/infiquetra/infiquetra-claude-plugins/issues/480) (defect, sub-issue of #340)
- **Plan:** `docs/plans/2026-07-05-saga-branch-refresh-480-plan.md`
- **Doc-review:** `docs/reviews/2026-07-05-saga-branch-refresh-480-doc-review.md` (clean; see its post-review addendum)
- **Branch:** `fix/pf-saga-branch-refresh-480`
- **Backend:** inline · **Destination:** merge

## Built (by U-ID)

- **U1 — protected branch refresh.** `saga.py` `save()` now refreshes `branch` from live git on
  every save, guarded so (a) an empty read (detached HEAD / no git) never clobbers a stored value
  and (b) a save on a default branch (`main`/`master`) never overwrites an already-recorded real
  work branch. New module constant `_DEFAULT_BRANCHES`. Three regression tests in
  `tests/test_saga_saga.py`: refresh-on-later-save, empty-read-preserves, and
  default-branch-preserves-work-branch.
- **U2 — release surfaces.** saga `0.54.3` → `0.54.4` across `plugin.json`, `CHANGELOG.md`,
  regenerated `marketplace.json`, and the `test_saga_plugin.py` version literal.

## Key decision — KTD1 was reversed mid-build

The plan (and its clean doc-review) chose **pure live-git-wins** (drop the first-save-only guard
outright). `/work`'s test gate caught that this **breaks two `test_ship_ceremony.py` tests**:
`ship_ceremony.run` records progress via `saga.py save` after *every* transition, so the save
after `checkout_main` reset `branch` to `main` right before `branch_delete`. Pure live-git-wins
would not even have fixed #480 — the ceremony's own progress-save re-wrongs the branch regardless
of what `/work` stored.

Corrected to a **protected refresh**: track live git, but never downgrade a stored work branch to
`main`/`master`. Because `_do_checkout_main` hard-codes `git checkout main`, the `{main, master}`
guard mirrors the ceremony's own constant. Verified the two ceremony tests were green on
`origin/main` (stashed the change → 2 passed), red under the draft fix, green under the corrected
fix. Plan, DECISIONS, and the doc-review addendum were all updated to match.

Lesson (journal `{#saga-branch-refresh-on-every-save-480}`): a doc-review verifies whether a plan
can *drive* implementation; it does not prove the design *survives execution*. A runtime
interaction between `save()` and the ceremony's save-after-every-transition loop was only
catchable by running the tests.

## Live dogfood

#480's own saga was minted on `main` by `/plan` (so it carried `branch="main"` — the very bug).
After U1 landed, re-saving on the work branch refreshes `branch` to
`fix/pf-saga-branch-refresh-480`. If the fix is correct end-to-end, this ceremony's `branch_delete`
should delete the branch cleanly — the first of the three recent ship ceremonies (#477, #478, #480)
that will *not* need the manual branch cleanup those two required.

## Files modified

- `plugins/saga/scripts/saga.py` — `_DEFAULT_BRANCHES` constant + protected refresh in `save()`.
- `tests/test_saga_saga.py` — 3 regression tests.
- `plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`,
  `.claude-plugin/marketplace.json`, `tests/test_saga_plugin.py` — release surfaces.
- `docs/plans/…-480-plan.md`, `docs/reviews/…-480-doc-review.md`,
  `docs/engineering-journal/DECISIONS.md` — durable artifacts (updated for the reversal).

## Checks run

- `uv run pytest` — **1992 passed** (1989 prior + 3 new).
- `uv run ruff check .` clean · `ruff format --check .` — 210 files formatted.
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — no issues (132 files).
- `sync_marketplace.py` (9 entries) · `check_release_surface_parity.py` — in parity ·
  `release_surface_diff_guard.py --base-ref origin/main` — all changed plugins bumped.
- `test_ship_ceremony.py` — 30 passed (the end-to-end ceremony-safety proof).

## Next step

Programmatic `/code-review` gate, then ship ceremony to merge; verify the `branch_delete` dogfood
works (no manual cleanup); tick #480's row in the plugin-fleet execution-order doc; close #480.
