# Code Review — Issue #347 (ship ends in teardown)

One-line verdict: **PASS** — 4 actionable findings (1 P1, 2 P2, 1 P3) from a 4-lens adversarial
review, all fixed in-branch and upheld 4/4 by an independent falsification re-review with a clean
regression sweep.

## Review-result contract

- **Target**: branch `work/347-ship-teardown-reconciliation`, diff `ec85a0c..54b9a43`
- **Reviewed SHA**: original 4-lens pass at `215a8ae`; falsification re-review at `54b9a43`
  (fix commits `e6e400d`, `54b9a43`). Artifact commits after `54b9a43` are docs-only and
  non-staling for the code verdict.
- **Mode**: programmatic / report-only — `/work` owns persistence (this artifact)
- **Lenses**: correctness, security, testing, maintainability/conventions — each spawned as
  `saga:readonly-verifier`, worktree isolation, opus tier, mandated `examined_sha` reporting
- **Linked**: issue #347; PR #563; plan
  `docs/plans/2026-07-11-issue-347-ship-teardown-reconciliation-plan.md`; saga `issue-347`

## Findings (Stage A merged, deduped by path:line:category)

| # | Sev | Conf | Lens(es) | Finding | Status |
|---|---|---|---|---|---|
| 1 | P1 | 100 | security + correctness (both reproduced independently) | `reclaim` crashes with uncaught `FileNotFoundError` on a prunable worktree (working dir deleted out-of-band) — fires in the SessionStart hook's primary scenario and in `_do_teardown` | **fixed** `e6e400d`: `isdir` guard → `ACTION_SKIP_PRUNABLE` report line; `_worktree_is_dirty` degrades to dirty on `OSError` (TOCTOU backstop); 2 regression tests |
| 2 | P2 | 75 | security | ceremony scratch teardown `shutil.rmtree(entry.ref)` with zero containment — `register()` stores refs verbatim, so absolute/`..` refs would be honored | **fixed** `e6e400d`: `_scratch_ref_contained` (realpath + strict containment under system tempdir / repo root, roots themselves refused); uncontained entry stays open so the re-reconcile HALTs naming it; truth-table + end-to-end test |
| 3 | P2 | 100 | testing | issue AC6 check command names `tests/test_ship_teardown_reconciliation.py` but the only AC6 test lived in `tests/test_ship_ceremony.py` — the selector collects zero tests (exit 5) | **fixed** `e6e400d`: thin structural AC6 test co-located in the named file (behavioral half stays with the FakeGh rig per rigs-stay-home convention); selector verified collecting 1 passed |
| 4 | P3 | 75 | maintainability | `ship_receipt.py:51` rationale comment claims "dependency-free" while the module hard-imports `ship_teardown` — falsehood copied from `merge_watcher.py` where it was true | **fixed** `54b9a43`: reworded to the real constraint (private-name copy, not decoupling) |

## Falsification re-review (at `54b9a43`)

Independent adversarial verifier attempted to refute all four fixes: **0 refuted, 9 upheld**
(real-repo prunable reproduction incl. the `--if-idle --quiet` hook form exiting 0; symlinked
worktrees not over-skipped; containment resists prefix-collision `/root-evil`, symlink-out,
traversal, root-itself, empty-ref vectors; the P2 fix confirmed wired into the production
`_do_teardown` path, not dead code; AC6 assertions non-vacuous by runtime introspection).
Regression sweep: 174 tests across the four ceremony suites + ruff check + format + mypy, all
green in the verifier's own worktree.

## Suppressed (below the confidence-75 gate; residual notes, not defects)

- `_do_teardown` → `reclaim(repo_root)` sweeps all merged+clean worktrees, not only the
  ceremony's own entry (conf 50, correctness) — only reachable when open worktree entries exist,
  which the shipped KTD9 wiring never creates; breadth note for a future revisit.
- `WORKTREE_RECLAIM_MERGED` string literal duplicated between `ship_teardown.py` and the
  `OpKind` enum with no equality drift-guard (conf 50, maintainability) — drift fails SAFE
  (unknown string → GATE → reclaim disabled, never mis-authorized).
- Atomic-write oracle only covers the clean-write path (conf 50, testing) — byte-identical to the
  house reference in `test_merge_watcher.py`.
- `test_AC_2` swaps the module-global `subprocess.run` with manual restore (hygiene; would race
  under pytest-xdist, which the repo does not use).
- `ship_receipt.mint` chmods 0444 in `finally` even on a mid-write failure (disk-full edge) —
  an empty read-only receipt would need manual removal before re-mint.
- `git rev-parse --verify` lacks `--end-of-options` (defense-in-depth only; refs originate from
  controlled ceremony values).
- Empty-ref `register()` acceptance (pre-existing; the containment gate strictly narrowed its
  blast radius — realpath('') at repo-root cwd resolves to the root itself, which is refused).

## Validation method

Every lens ran in a disposable worktree pinned to the reviewed SHA with `examined_sha` reported
back; findings required file:line evidence, and both P1 reporters reproduced the crash on real
git repos before it was accepted. Fixes were verified by an independent falsification pass that
rebuilt the scenarios from scratch rather than re-running the authors' tests.
