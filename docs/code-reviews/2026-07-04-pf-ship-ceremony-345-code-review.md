---
title: Code review — ship_ceremony.py primitive (#345)
type: code-review
status: complete
date: 2026-07-04
---

# Code review — ship_ceremony.py primitive (#345)

**Target:** branch `feat/pf-ship-ceremony-345` vs `main`
**Reviewed SHA:** `e462101` (pre-fix commit); fixes applied in-session post-review, re-verified against the full gate before PR
**Blocked status:** was blocked (2 P1s); both fixed — clean to proceed
**Issue / plan:** infiquetra/infiquetra-claude-plugins#345 / `docs/plans/2026-07-04-ship-ceremony-primitive-plan.md`
**Work session:** `docs/work-sessions/2026-07-04-ship-ceremony-primitive.md`

## Scope check

**CLEAN.** All 17 changed files map to the plan's U1-U6 file lists plus the plan/review/
work-session/journal artifacts themselves. No scope drift, no unaddressed requirement.

## Plan-completion audit

R1-R7 and AC1-AC7 (from the issue and plan): all **DONE**, verified by direct code
reading plus the test suite (28 tests, all passing, 99% coverage on `ship_ceremony.py`).
AC6 (`work/SKILL.md` free of raw ceremony `git`/`gh` commands) verified directly via
`grep -nE "git (checkout|pull|branch -d)|gh pr (create|merge)" plugins/saga/skills/work/SKILL.md`
returning no matches.

## Lenses run

Correctness, security, testing, maintainability (4 always-on; no conditional lens
warranted — no deploy/infra/migration surface in this diff). `saga:readonly-verifier` +
disposable worktree per spawn, backend inline (matches session).

## Findings

| # | File | Issue | Reviewer | Confidence | Route | Status |
|---|---|---|---|---|---|---|
| 1 | `plugins/saga/scripts/ship_ceremony.py:389` | `start()` had no guard against an already-progressed ceremony — would open a second PR and regress `ceremony_transition` back to `commit` | correctness | 90 (P1) | manual | **fixed** |
| 2 | `tests/test_ship_ceremony.py` | Zero failure-path tests; `TransitionFailedError`'s "state must not advance" contract unverified | testing | 90 (P1) | manual | **fixed** |
| 3 | `plugins/saga/scripts/ship_ceremony.py:207` | `NoSagaError` path untested | testing | 90 (P2) | manual | **fixed** |
| 4 | `plugins/saga/scripts/ship_ceremony.py:337` | `_current_pr_number`'s pr_refs guard untested | testing | 85 (P2) | manual | **fixed** |
| 5 | `plugins/saga/scripts/ship_ceremony.py:309` | `_do_branch_delete`'s branch-safety guard untested | testing | 85 (P2) | manual | **fixed** |
| 6 | `plugins/saga/scripts/ship_ceremony.py` (CLI) | `main()`/`_build_parser()` dispatch and error-exit path untested | testing | 80 (P2) | manual | **fixed** |
| 7 | `tests/test_ship_ceremony.py` | Docstring/docs claimed 23 tests; actually 21 (now 28) | testing | 60 (P3, suppressed) | advisory | **fixed** (free, while in the file) |
| 8 | `plugins/saga/scripts/ship_ceremony.py:308` | `_do_branch_delete` guard special-cases only `"main"`, not other possible default-branch names | security | 60 (P3, suppressed) | advisory | not fixed — residual, noted below |
| 9 | `plugins/saga/scripts/ship_ceremony.py:313` | Remote branch-delete uses `check=False`, silently discarding a genuine remote-delete failure | correctness | 50 (P3, suppressed) | advisory | not fixed — residual, noted below |

Maintainability: **clean** (0 findings) — runner-injection pattern consistently applied,
`CeremonyTier` naming distinct from `reversibility_certificate.Tier`, KTD1-KTD4 docstring
claims verified accurate against the code, release surfaces internally consistent.

## Coverage / residual risk

`ship_ceremony.py`: 99% line coverage after fixes (2 lines uncovered: a minor `install`
error-branch variant already exercised via a different path, and `main`'s `start`
dispatch line — both P3-tier, not blocking). Findings #8 and #9 above are recorded as
known residual risk, not fixed in this PR: neither is reachable under this repo's actual
usage (default branch is `main`; GitHub's merge-time auto-delete makes the remote
branch-delete usually redundant) — revisit if `ship_ceremony.py` is ever pointed at a
repo with a different default branch name.

## Saga

Appended to `issue-345`'s work-thread saga tick (`--review-paths` this artifact,
`--orchestration-mode inline`); `lifecycle_phase` left at `work` (code-review never
advances it).

## Route

Clean — proceeding to PR-ready per `/work`'s continuation loop (destination `merge`,
confirmed).
