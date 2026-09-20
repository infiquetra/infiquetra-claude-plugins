# Work session — issue 1027, the build loop with a written exit criterion

Date: 2026-09-20. Branch: `issue/1027`, from `origin/parent/1018`. Plan:
`docs/plans/2026-09-20-issue-1027-build-loop-exit-criterion-plan.md`. Document review:
`docs/reviews/doc-review-issue-1027-2026-09-20.md`, ready with no `P0` and no `P1` open.

## What was built, by unit

| Unit | What landed |
|---|---|
| U1 | `plugins/saga/scripts/build_loop.py` — reads the criterion from the run record and the profile, runs it once per invocation, records every result under the unit row's `build_loop` key, and prints the criterion under `--dry-run` |
| U2 | `plugins/saga/references/mechanical-baseline.md`, plus one row each in `references/run-record.md` (the `build_loop` key) and `references/repository-profile.md` (the optional `branch_preview_command`) |
| U3 | `/work` Phase 3 is the build loop; core principle 3, section 4.1's gate-input clause, sections 5.1 and 5.4, the hard boundary, `references/test-and-gates.md`, `references/pr-continuation-loop.md` and `commands/work.md` all rewritten within the span the plan declared |
| U4 | The five ship-ceremony modules and four test files removed, the `SessionStart` hook entry deleted, and every importer repaired |
| U5 | `tests/test_build_loop.py` (39 tests) plus repairs to seven existing test files |
| U6 | The fourth acceptance criterion proved against a copy of the record with a fake preview step |
| U7 | saga 0.170.0 across `plugin.json`, `marketplace.json`, `CHANGELOG.md` and the version literal in `tests/test_saga_plugin.py`; three `LEARNINGS.md` entries and four `DECISIONS.md` entries under `## 2026-09-20` |

## The build loop's own result for this card

Recorded in the unit's `build_loop` block, read verbatim rather than re-derived — the block is the
authority and this section is a rendering of it.

- **Baseline**: `ruff check` `pass`, `ruff format --check` `pass`, `mypy` `pass`,
  `pytest tests/ plugins/*/tests/` **`fail`** — "5 failed, 8583 passed, 34 skipped, 1 xfailed in
  889.59s".
- **Functional checks**: two, both `pass` — the dry run printing the criterion, and the absence of
  `ship_ceremony.py`.
- **Preview**: `pass` against a fake preview step, on a copy of the record with `branch_preview`
  set true. This repository declares no preview, so the live path here records
  `no-preview-declared`; the live proof for a genuinely declared preview belongs to a repository
  that has one.
- **Scenario smoke**: one, `pass` — `tests/test_build_loop.py`, 39 tests.
- **Iteration verdict**: `green: false`, no `handed_to_code_review` written. Exactly as designed:
  the loop recorded a non-green iteration rather than refusing, and wrote no hand-off.

**That iteration is not a verdict on this card, and the record says why.** Its `revision` is
`572b4db5` — the plan commit, which predates both of this card's commits — while the preview step
at the end of the same iteration printed `1bc5bd82`, the merge commit. The fifteen-minute baseline
therefore spanned the merge-conflict resolution: it read `work/SKILL.md`, `CHANGELOG.md`,
`plugin.json`, `marketplace.json` and `tests/test_saga_plugin.py` while those five files were being
edited, and five tests failed. Those are the same five files the merge conflicted on.

A clean re-run on the stable merged tree is the authority, and it was still in flight when this
card returned: 13 percent complete with zero failures, under a load average of 8 with four sibling
drivers' suites competing for the machine. Every test file the card touches was run separately on
the stable tree and is green — 358 tests across the ten affected files, plus the release-surface
parity, marketplace sync, validator, gate-absence and journal-order checks.

This is worth keeping as evidence of the loop working rather than as an embarrassment: an iteration
that ran against a moving tree produced a wrong verdict, and the record's own `revision` field is
what makes that detectable afterwards. A loop that recorded only "fail" would have left no way to
tell.

## Two defects the loop found on its first real run

Both were in the interaction between the loop and this repository, and neither would have been
visible from reading the code.

1. **A glob in a baseline command reached the program verbatim.** The profile carries
   `uv run pytest tests/ plugins/*/tests/ -q`; the loop runs with `shell=False` on purpose, so
   pytest received a literal path and the loop recorded a `fail` indistinguishable from a real test
   failure. Globs are now expanded against the repository root, with `shell=False` intact.
2. **`--repo-root` was doing double duty**, meaning both "where the profile is" and "whose `HEAD`
   is recorded". Pointing it at a profile directory moved the revision lookup to somewhere that was
   not a checkout. `--profile` is now a separate flag and every check runs from the repository root.

## Decisions taken from the coordinator's message, with that message as the source

| Choice | Answer taken |
|---|---|
| Saga | Resume `issue-1027` from this worktree's store; no second saga minted |
| Branch | Stay on `issue/1027` |
| Execution backend | `inline`, matching the plan's `backend:` frontmatter; no other backend offered or entered |
| Doc-review gate | Passed with nothing above `P2` open; no override needed or taken |
| Code review | None in this stage, by the operator's decision of 2026-09-19; the parent pull request carries one review for the whole parent |
| Complexity triage | Fresh build, not a round-N re-entry: there is no pull request for this card |
| Ceremony start | Not applicable — this card removes the ceremony. In its place `/work` opens no pull request during the loop, because there is nothing to review until the criterion is green |
| Bandit | Stays advisory exactly as continuous integration runs it, reported by the dry run as an uncovered catalogue check; the recorded default, not a new decision |
| The mypy and coverage divergence | Named in `references/mechanical-baseline.md` and left as the repository has it |
| Version | 0.170.0, taken above 0.169.0 which issue 1029 landed on the integration branch at `23959a80` |

Both questions stay declared in the plan for the operator to overrule later.

## Board moves

| Move | Result |
|---|---|
| `Stage=Planning`, `Status=Designing` | `written`, `field` = `Stage+Status`, 1 attempt |
| `Stage=Planning`, `Status=Ready for Active` | `written`, `field` = `Stage+Status`, 1 attempt |
| `Stage=Active`, `Status=Implementing` | `written`, `field` = `Stage+Status`, 1 attempt |

Each reported `Stage+Status`, so both halves landed in every case — the half-write that reports
`written` after setting `Status` alone did not occur.

## Deferred to issue 1030, recorded rather than silently left

`merge_watcher.py` with `tests/test_merge_watcher.py`; `lifecycle_state.py`'s
`requires_hard_test_gate` with `/loop`'s two references to it; and `saga.py`'s
`ceremony_transition` and `ceremony_tier` fields. Each is orphaned by this card's removals, none is
named by the card, and issue 1030 owns the commands that still read them.

## Next step

Return to the coordinator, which merges `issue/1027` onto `parent/1018`. No pull request and no
push from this worktree.

**One item is open**: the clean full-suite run on the merged tree had not finished when this card
returned. Its log is at `<scratchpad>/issue-1027/fullsuite.log`. If it names any failure, that
failure is this card's to repair.
