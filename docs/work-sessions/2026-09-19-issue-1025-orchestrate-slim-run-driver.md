# Work session — issue 1025, orchestrate slims to the run driver

**Status: the driver is done and proved; the legacy test migration is not finished.** This document
says exactly what is true, what is not, and what the next session picks up. It is written that way
on purpose: a work-session note that reports a green suite when the suite is red is worse than no
note at all.

| Field | Value |
|---|---|
| Issue | infiquetra/infiquetra-claude-plugins#1025, under parent #1018 |
| Plan | `docs/plans/2026-09-19-issue-1025-orchestrate-slim-run-driver-plan.md` |
| Document review | `docs/reviews/2026-09-19-doc-review-issue-1025-orchestrate-slim-run-driver.md`, no P0 or P1 open |
| Branch | `issue/1025`, from `parent/1018` at `4e951f0e` |
| Backend | `inline` |
| Destination | `pr` — the parent pull request (issue 1030) carries the review for the whole parent |
| Code review | none for this card, by operator decision on 2026-09-19 |

## What is finished, and how it is proved

The driver rewrite is complete. `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`
passes `ruff check`, `ruff format --check` and `mypy`, its `--help` lists the subcommand set the
card's first acceptance criterion names, and seven new test modules cover every behaviour the plan's
units describe. **All 77 of those tests pass.**

| New module | Tests | What it proves |
|---|---|---|
| `tests/test_orchestrate_record.py` | 9 | Two issues coexist in one repository, each with its own record; the version refusal, unknown-field preservation, the added unit keys, and that `start` requires the record and names the admission command |
| `tests/test_orchestrate_worktree.py` | 10 | A fresh worktree on every launch, the stale one released rather than reused or left, a refusal when it is dirty, and the virtual-environment step in all four of its shapes |
| `tests/test_orchestrate_launch_persist.py` | 10 | A repeated `go` launches once, a keyboard interrupt leaves the identity on disk, and the width number bounds launches across calls — counting open roster rows too |
| `tests/test_orchestrate_plan_check.py` | 11 | Every assertion is reachable without mutation, with a mutation proof that fails on any write |
| `tests/test_orchestrate_merge.py` | 13 | The merge turn, the stale-turn release derived from git, the `main` regression guard including the fetch-first refusal, and the worktree release with both its refusals |
| `tests/test_orchestrate_clean.py` | 12 | The sweep is total, the report survives an unwinding exception, workspaces are retired by ownership, and the fleet-doctor check reports by path |
| `tests/test_orchestrate_guards.py` | 22 | All four escaping spellings of `main`, the close-failure record, and the recorded settlements |

Add `tests/test_orchestrate_surface.py` for the card's own runnable criteria and the release-surface
parity, and `tests/test_orchestrate_hygiene.py` (rewritten) for the documentation contract.

### Fail-then-pass evidence

Three of these tests failed against the implementation before they passed, and the failure was the
point rather than an accident of fixture order:

1. **`test_two_launches_get_two_different_paths`** failed with git's own
   `fatal: 'orch/3-u1' is already used by worktree at …`. The first attempt at a fresh worktree
   created a second directory on the same branch, which git refuses. That is a real design defect
   the test found: the repair is to release the stale worktree first, refusing on uncommitted or
   unpushed work. The test then failed a second time, asserting the old directory still existed —
   which it correctly no longer did.
2. **`test_a_managed_worktree_with_no_live_session_is_reported_by_path`** failed because a
   non-`--merged` sweep closes a running unit before the check runs. The behaviour was right and
   the test was asking the wrong question; it now asks it under `--merged`, where a running unit is
   kept.
3. **`test_start_leaves_the_admission_half_of_the_record_byte_identical`** failed on
   `approval_scope`, because the record module normalises an absent block into seven null
   categories on read. The fixture now writes them out, which is what a real admission writes.

The protected-reference test carries its mutation proof inside itself: it runs the superseded
peel-before-strip implementation directly and asserts that it misses all four spellings, so the
parametrised set is shown to discriminate rather than merely to pass.

## What is NOT finished

**The legacy Orchestrate test suite is not green.** The rewrite invalidated most of the 17,953 lines
of tests that drove the old fixed-path run file, and the migration is substantially advanced but
incomplete.

At the last measurement, across the orchestrate modules: **524 passing, 175 failing** — down from 276
failing when the driver rewrite landed. Of the 175:

| Module | Failing | Why |
|---|---|---|
| `tests/test_orchestrate_land_clean.py` | 49 | Not started. Mixed: its remote-branch half survives and needs migrating; its landing half tests removed machinery |
| `tests/test_orchestrate_launch_and_land.py` | 40 | Not started. Mixed: launch argv, workspace and OpenCode tests survive; the land, staged-input and redrive tests are of removed machinery |
| `tests/test_orchestrate_board_writeback.py` | ~22 | Hand-built `Run` objects saved to a path, plus tests of the removed contract key |
| `tests/test_orchestrate_scoped_review_controllers.py` | ~14 | Hand-built `Run` objects saved to a path |
| `tests/test_orchestrate_review_loop.py` | ~16 | The same, plus land-path assertions |
| Five smaller modules | ~34 | A long tail of per-test work |

The migration so far was six mechanical passes over the surviving modules: the command Namespace now
carries `--issue` and `--store-root`; the run-file writers and readers point at the record;
`Run.load()` and `cmd_land` call sites moved; hand-built runs attach to a record through
`tests/orchestrate_support.save_run`; and every test repository gets a bare local remote, because the
merge turn now fetches before it compares.

### Modules deleted, with the ledger the plan requires

Four modules were deleted. The plan named four; the count matched but the membership did not, because
two more modules turned out to be wholly about removed subsystems and one of the planned four is
mixed. That is a deviation from the plan and it is recorded here rather than glossed:

| Module | Tests | Where every test name went |
|---|---|---|
| `tests/test_orchestrate_task_spill.py` | 12 | All of them test the task spill, which goes with the fixed-path run file. No assertion survives, because there is no spill |
| `tests/test_orchestrate_task_file_safety.py` | 15 | Eleven test the spill pointer and go with it. The four that test unsafe unit names and an unsafe run identifier are carried into `tests/test_orchestrate_plan_check.py`, where they are proved against a path that creates nothing |
| `tests/test_orchestrate_land_worktree.py` | 29 | All of them test the landing-worktree recovery machinery the card removes. Its one cleanup-failure assertion is re-authored with an injected failure in `tests/test_orchestrate_clean.py` (issue 991) |
| `tests/test_orchestrate_land_announce.py` | 12 | Nine test the writeback records the card removes. The three announce-per-unit assertions are carried into `tests/test_orchestrate_merge.py`, where the announcement now happens |

`tests/test_orchestrate_hygiene.py` was rewritten rather than deleted: its four `info/exclude` tests
and its `clean --all` test go with the removed run state, its run-identifier safety test is carried
into `tests/test_orchestrate_plan_check.py`, and its two documentation checks survive.

**The two mixed modules, `test_orchestrate_land_clean.py` and `test_orchestrate_launch_and_land.py`,
have NOT been split.** Their ledgers are the work the next session starts with.

## The operator question, answered

The plan carried one open question: whether the board-writeback path leaves orchestrate in this
release. **Answered by the run's rules rather than by a new decision: it stays.** The card does not
name it, nothing unnamed is deleted, and issue 1028 — which implements the simplification review's
recommendation R19 and depends on this card — moves board writes into saga and removes the path
then. Unit U8's removal inventory is unchanged.

## Choices taken, and where each came from

Every choice the work skill would have asked about was answered up front by the coordinator, and each
is recorded here with that message as its source.

| Choice | Taken | Source |
|---|---|---|
| Saga | resumed `issue-1025` from this worktree's store; no second saga minted | coordinator |
| Branch | stayed on `issue/1025` | coordinator |
| Execution backend | `inline`, as the plan's frontmatter says; no other backend offered or entered | coordinator, and the plan's `backend:` field |
| Document-review gate | passed with nothing above P2 open; no override sought or needed | coordinator, and the review artifact |
| Complexity triage | fresh build, not a round-N continuation | the skill's documented default; no pull request exists for this card |
| Ceremony start | declined | earlier cards in this run declined it because it opens a draft pull request, and this card opens none |
| Code review | none run; no lenses, no review artifact | operator decision, 2026-09-19 |
| Live record | the live record at `.claude/saga/runs/issue-1025.json` was read, never written by code; every test writes a temporary record under `tmp_path` | coordinator |

## Board moves

| Move | Result |
|---|---|
| `Active` / `Implementing` at the start of the work | `written`, `field: Stage+Status`, 1 attempt — both halves executed |

No end-of-work move was submitted, because the work is not finished and moving the card would be a
claim this session cannot make.

## Where the next session starts

1. Split `tests/test_orchestrate_land_clean.py`: migrate its remote-branch tests, drop its landing
   tests, and write the name ledger for both halves.
2. Split `tests/test_orchestrate_launch_and_land.py` the same way.
3. Work the remaining tail — hand-built `Run` saves, and the handful of tests that assert on removed
   subsystems (the run-file contract key, the outstanding-writeback ledger).
4. Run the inner loop and then the full suite across both pytest roots.
5. Merge `origin/parent/1018` into `issue/1025`, re-run at the merged head, and hand back.
