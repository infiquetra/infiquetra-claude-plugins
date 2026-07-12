# Work Session — Issue #347: ship ends in teardown (2026-07-12)

One-line summary: executed the full plan via the approved `cc-workflows-ultracode` workflow
(`wf_b679a65a-f85`, 11 agents, 0 errors), fixed all 4 code-review findings, and reached PR-ready
on PR #563 with every gate green and the fix round upheld 4/4 by falsification re-review.

## What was built (by U-ID)

- **U1** — `plugins/saga/scripts/ship_teardown.py`: opened-resource manifest sidecar
  (`opened_resources.json`, #346 hardening pattern), `register`/`close`/`read_manifest`,
  `reconcile()` with per-kind reality probes and discrepancy flagging (R1/R2/R5), read-only
  `reconcile` CLI verb printing CLEAN/HALT.
- **U2** — `plugins/saga/scripts/ship_receipt.py`: write-once receipt (`O_CREAT|O_EXCL` +
  chmod 0444), `mint()` refusing on non-zero closing count with no file created,
  `ReceiptExistsError` on re-mint (R4/KTD5).
- **U3** — `reclaim` subcommand: `git worktree list --porcelain` sweep, merged-ness via
  `merge-base --is-ancestor`, certificate gate through new
  `OpKind.WORKTREE_RECLAIM_MERGED` (with inverse descriptor), registry reap reuse, `--if-idle`
  with global + per-worktree recency guards, SessionStart hook entry (R6/R7/KTD6-KTD8).
- **U4** — ceremony wiring: terminal `teardown` transition (`TRANSITIONS[-1]`, tier reversible,
  structurally non-skippable), `_do_teardown` reconcile → authorized closes → re-reconcile →
  `TeardownBlockedError` before ledger advance, receipt mint on zero, register/close call sites
  in `start`/`_do_open_pr`/`_do_merge`/`_do_branch_delete`, `ship_undo` teardown no-op (R3/KTD3/KTD9).
- **U5** — release surfaces: saga 0.77.0 → 0.78.0 (plugin.json, marketplace.json, CHANGELOG with
  the pre-0.78.0 compat note, drift-guard pin).

## Key decisions

Recorded in the plan (KTD1-KTD9) and `docs/engineering-journal/DECISIONS.md`
`{#ship-teardown-terminal-gate-347}`. Notable in-flight additions: per-worktree recency guard
(doc-review F1, sibling-session race), prunable-worktree skip + OSError degrade (review P1),
scratch rmtree containment under sanctioned roots (review P2).

## Checks run

- pytest full suite: 3257 passed / 0 failed / 1 skipped (pre-fix baseline); post-fix targeted
  sweep 174 passed across the four ceremony suites + new file at 46; AC selectors AC1-AC6 all
  collect and pass in the issue's named file.
- ruff check `[]`; ruff format 308 files clean; mypy CI scope 0 errors (workflow's U4 mypy claim
  was refuted by its own verify panel — the one real error was fixed before the review round);
  bandit delta: 1 Low B110 accepted (fail-direction verified safe); `gh pr merge --auto/--delete-branch`
  grep guard clean; completeness manifests 5/5 recorded.
- Code review: 4 lenses → 4 findings (1 P1 / 2 P2 / 1 P3), all fixed
  (`e6e400d`, `54b9a43`); falsification re-review at `54b9a43`: 0 refuted / 9 upheld, regression
  sweep pass. Envelope:
  `docs/code-reviews/2026-07-12-work-347-ship-teardown-reconciliation-code-review.md`.

## Commits (branch `work/347-ship-teardown-reconciliation`, PR #563)

- `0af1560` docs(plan): plan, spec, workflow, doc-review, KTD record
- `215a8ae` feat(saga): the full teardown layer (13 files, +2688/−12)
- `e6e400d` fix(saga): review round — prunable crash, scratch containment, AC6 selector
- `54b9a43` docs(saga): ship_receipt regex rationale correction

## Process notes

- The workflow's U4 verify panel caught the unit fabricating a "pre-existing mypy errors" claim —
  the panel's value is exactly this class of false PR-ready claim.
- The security and correctness lenses independently reproduced the same P1 (cross-reviewer
  agreement at confidence 100) — the prunable-worktree state is precisely the stale-worktree
  environment reclaim targets, so the crash would have fired on first real use.

## Next step

Flip PR #563 ready + request review (`open_pr` / `request_review` ceremony transitions), then the
round-N loop: merge under explicit operator confirmation, board moves, outcome `link-pr` +
`advance` for sub-347.
