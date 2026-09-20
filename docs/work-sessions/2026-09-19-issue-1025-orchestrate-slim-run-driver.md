# Work session — issue 1025, orchestrate slims to the run driver

**Status: done. The driver is rewritten, the whole test suite is green, and the integration branch
is merged in.** An earlier revision of this document reported an honest red mid-flight; that half
is replaced by the ledgers below rather than deleted, because what it recorded is now finished.

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

## The test ledgers

A test was removed **only** when the behaviour it tested belongs to a subsystem this card removes,
and the subsystem is named. A test whose behaviour survives was migrated, however tedious, because
the tests are this card's proof and the parent review's.

### Modules deleted whole

| Module | Tests | Where every test name went |
|---|---|---|
| `test_orchestrate_task_spill.py` | 12 | All test the task spill, which goes with the fixed-path run file. No assertion survives, because there is no spill |
| `test_orchestrate_task_file_safety.py` | 15 | Eleven test the spill pointer and go with it. The four that test unsafe unit names and an unsafe run identifier are carried into `test_orchestrate_plan_check.py`, proved against a path that creates nothing |
| `test_orchestrate_land_worktree.py` | 29 | All test the landing-worktree recovery machinery. Its cleanup-failure assertion is re-authored with an injected failure in `test_orchestrate_clean.py` (issue 991) |
| `test_orchestrate_land_announce.py` | 12 | Nine test the writeback records. The three announce-per-unit assertions are carried into `test_orchestrate_merge.py`, where the announcement now happens |

### `test_orchestrate_land_clean.py` → `test_orchestrate_reap_and_remote.py`

**All 50 tests migrated; none removed.** Everything it covers survives the card: `landed`'s three
answers, the hand-finished landing shapes, `reap`'s rule, the keep reasons, the post-land
`produced_anything` reading, `check` after a merge, the legacy-run readings, the scoped `--clean`
reap, and the thirteen remote-branch proofs. Four assertions moved with contracts that moved, each
with the reason in the test:

| Test | What moved |
|---|---|
| `test_every_keep_cause_prints_its_own_reason` | exits 3, not 0: an owned tab could not be closed |
| `test_a_worktree_that_cannot_be_removed_keeps_the_unit_and_the_run_record` | exits 3; its `--all` run-state assertion went with `--all` |
| `test_a_kept_unit_names_the_tab_this_pass_already_closed` | exits 3 |
| `test_clean_reports_an_unowned_tab_as_left_open_and_never_closes_it` | its `--all` retention assertion went with `--all`; the rest stands |
| `test_land_clean_says_every_merged_unit_was_kept_rather_than_merged_nothing` | the sentence says "this invocation" |
| the two `TestLandCleanReapsOnlyWhatThisLandMerged` tests | the retained unit now carries a tab, which is what defers the merge-turn release; the scoping question they ask is unchanged |

### `test_orchestrate_launch_and_land.py` → `test_orchestrate_launch_argv.py`

**54 migrated, 6 removed.**

| Removed test | Subsystem that took it |
|---|---|
| `test_staged_input_stop_on_an_owned_pane_retries_through_the_same_pane` | the staged-input redelivery route (`_staged_input_stop`) |
| `test_a_staged_receipt_without_a_pane_is_not_a_retry` | the staged-input redelivery route |
| `test_the_staged_marker_is_the_composer_enum_value` | the staged-input redelivery route (`STAGED_INPUT_BOX`) |
| `test_redrive_reprompts_an_undelivered_unit_whose_session_is_idle` | the `redrive` command and the `prompt_undelivered` door |
| `test_redrive_refuses_a_session_that_has_started_and_a_unit_that_is_not_undelivered` | the `redrive` command |
| `test_a_load_and_save_round_trip_writes_no_version_key` | the run file's `contract` key |

Migrated with a changed premise, not deleted: `test_staged_input_stop_returns_the_unit_to_retryable_pending`
and `test_repeated_staged_stop_keeps_identifiers_and_dedupes_the_note` keep the half that survives —
the stop returns the unit to `PENDING`, keeps its identifiers, and says why — and lose the retry
cycle. The two OpenCode tests keep their argv assertions and drop the receipt-after-reload ones,
which tested a persistence this card removes.

### Removed elsewhere, same rule

| Test | Module | Subsystem |
|---|---|---|
| `test_a_second_land_still_reports_an_outstanding_failure` | board writeback | the outstanding-writeback ledger |
| `test_a_converged_announce_clears_the_outstanding_entry` | board writeback | the outstanding-writeback ledger |
| `test_the_contract_string_moves_with_the_unit_field_set` | board writeback | the run file's `contract` key |
| `test_a_reader_that_knows_only_the_previous_contract_refuses_this_run_file` | board writeback | the run file's `contract` key |
| `test_a_run_file_from_a_newer_orchestrate_is_refused_not_read` | board writeback | the `contract` key; the record's `schema` refusal replaces it, proved in `test_orchestrate_record.py` |
| `test_a_run_file_this_version_wrote_round_trips` | board writeback | the run file; the record round trip is proved in `test_orchestrate_record.py` |
| `test_an_unrecorded_numbered_landing_worktree_is_reported` | drift and adopt | the landing-worktree discovery, with the landing bookkeeping |
| four `info/exclude` tests, `clean --all`, the hand-authored-brief test | hygiene | the run state they protected; its run-identifier safety test is carried into `test_orchestrate_plan_check.py` |

`test_orchestrate_hygiene.py` was rewritten rather than deleted: its two documentation checks
survive, one of them rewritten to assert the skill names the record rather than a run file.

## Defects the migration found

Every one surfaced in a legacy test rather than in this card's new ones, and every one was fixed in
the driver rather than in the test that caught it.

| Defect | Fix |
|---|---|
| `clean` exited 3 whenever the `--merged` rule kept anything | the exit code reads a separate failure set, so it means "something this run owns was left behind"; a borrowed tab is reported and does not raise it |
| The merge-turn worktree release pulled the floor from under a live session | the release refuses while the unit records a tab; `clean` keeps the close-then-remove order |
| A release deferred for that reason counted as a cleanup failure | it is the correct order, so it does not |
| Dropping the persisted receipt took the launcher's tab-ownership proof with it | `Unit.owned` keeps that one fact beside `tab_id`, which `session_owned` already falls back to |
| The saga resolver could not see a saga installed beside orchestrate in a versioned cache | a sibling-cache rung, newest version first |
| A plan that is not JSON died in a decode error six frames deep | a named refusal, reachable because the floor now warns |
| The unattended-worktree check read only a session's working directory | it matches on the agent name too |
| A relaunch could not check out a branch its stale worktree still held | the stale worktree is released first, refusing on uncommitted or unpushed work |

## The merge

`origin/parent/1018` at **`b98e94ea`** merged in, carrying issue 1001 (the code-review rewrite,
orchestrate 4.6.0, saga 0.165.0) and issue 1026 (plan continues into plan review, saga 0.166.0).
Six files conflicted and all six were resolved keeping both sides:

- Both changelogs keep both sections. Orchestrate's 5.0.0 stands above 1001's 4.6.0, whose section
  is folded under it rather than renumbered; saga's 0.167.0 stands above 1026's 0.166.0.
- Saga took **0.167.0**, bumped from 0.166.0 at `b98e94ea`, because 1001 and 1026 took 0.165.0 and
  0.166.0 while this card's suite ran.
- The driver carries `review_result.v2` as issue 1001 left it.

## The operator question, answered

Whether the board-writeback path leaves orchestrate in this release: **it stays**, by the run's
rules rather than by a new decision. The card does not name it, nothing unnamed is deleted, and
issue 1028 — which implements the simplification review's recommendation R19 and depends on this
card — moves board writes into saga and removes the path then. Unit U8's inventory is unchanged.

## Choices taken, and where each came from

| Choice | Taken | Source |
|---|---|---|
| Saga | resumed `issue-1025`; no second saga minted | coordinator |
| Branch | stayed on `issue/1025` | coordinator |
| Execution backend | `inline`; no other offered or entered | coordinator, and the plan's `backend:` field |
| Document-review gate | passed with nothing above P2 open; no override | coordinator, and the review artifact |
| Complexity triage | fresh build, not a round-N continuation | the skill's documented default; no pull request exists for this card |
| Ceremony start | declined | it opens a draft pull request, and this card opens none |
| Code review | none; no lenses, no review artifact | operator decision, 2026-09-19 |
| Live record | read, never written by code; every test writes a temporary record under `tmp_path` | coordinator |

## Board moves

| Move | Result |
|---|---|
| `Active` / `Implementing`, at the start of the work | `written`, `field: Stage+Status`, 1 attempt |
| `Active` / `Code review`, at the end | recorded in the return; the suite was green first |
