# Work session — ship_ceremony.py open_pr push fix (#478)

- **Date:** 2026-07-05
- **Issue:** [#478](https://github.com/infiquetra/infiquetra-claude-plugins/issues/478) (defect, sub-issue of #340)
- **Plan:** `docs/plans/2026-07-05-ship-ceremony-open-pr-push-478-plan.md`
- **Doc-review:** `docs/reviews/2026-07-05-ship-ceremony-open-pr-push-478-doc-review.md` (clean)
- **Branch:** `fix/pf-ship-ceremony-open-pr-478`
- **Backend:** inline · **Destination:** merge

## Built (by U-ID)

- **U1 — open_pr push (front-loaded path).** Extracted `_push_branch(repo_root, *, runner)`
  emitting `git push -u origin <branch>`; `_do_commit` now delegates to it (behavior-preserving),
  and `_do_open_pr`'s existing-PR branch calls it **before** `gh pr ready`. Added
  `test_open_pr_pushes_pending_commits_on_existing_pr_path`: `start()` → local commit after →
  assert `origin/<branch>` behind HEAD → run `open_pr` → assert `origin/<branch>` == HEAD and PR
  flipped ready.
- **U2 — release surfaces.** saga `0.54.2` → `0.54.3` across `plugin.json`, `CHANGELOG.md`,
  regenerated `marketplace.json`, and the `test_saga_plugin.py` version literal.

## Key decisions

- **Push at `open_pr`, not `merge`** (KTD2, journal `{#ship-ceremony-open-pr-push-478}`). The only
  unpushed window is `start()`→`open_pr`; `/work`'s round-N loop already re-pushes post-`open_pr`
  commits (`pr-continuation-loop.md:33,35`), and a merge-time push would reset green CI right
  before `gh pr merge --squash` (no `--auto`).
- **Shared `_push_branch` helper** (KTD1) rather than an inline second push, keeping `_do_commit`'s
  argv identical so the existing `fail_prefix` transition-failure test still matches.

## Files modified

- `plugins/saga/scripts/ship_ceremony.py` — `_push_branch` helper + push in `_do_open_pr`.
- `tests/test_ship_ceremony.py` — 1 regression test.
- `plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`,
  `.claude-plugin/marketplace.json`, `tests/test_saga_plugin.py` — release surfaces.
- `docs/plans/…-478-plan.md`, `docs/reviews/…-478-doc-review.md`,
  `docs/engineering-journal/DECISIONS.md` — durable artifacts.

## Checks run

- `uv run pytest` — **1989 passed** (1988 prior + 1 new).
- `uv run ruff check .` — clean · `ruff format --check .` — 210 files formatted.
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — no issues (132 files).
- `sync_marketplace.py` (9 entries) · `check_release_surface_parity.py` — in parity ·
  `release_surface_diff_guard.py --base-ref origin/main` — all changed plugins bumped.
- Programmatic `/code-review` — CLEAN, no P0/P1, scope CLEAN.

## Known interaction

`saga.py`'s `branch` field is stuck at `main` for this saga (**defect #480** — first-save-only
auto-derive). `branch_delete` will refuse on the stale field; handled manually at ceremony end
(verify `MERGED` via `gh`, delete branch by hand), same as #477.

## Next step

Ship ceremony to merge (open draft PR → flip ready → merge → cleanup), then tick #478's row in the
plugin-fleet execution-order doc.
