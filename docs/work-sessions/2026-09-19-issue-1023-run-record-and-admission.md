# Work session — issue 1023, the run record and the admission questionnaire

**Branch** `issue/1023`, branched from `origin/parent/1018` at `550ae6ce`.
**Plan** `docs/plans/2026-09-19-issue-1023-run-record-and-admission-plan.md`.
**Backend** `inline`, from the plan's `backend:` frontmatter — honoured, not re-offered.
**Destination** `pr`. **Saga** `issue-1023`, resumed from this worktree's store, not re-minted.

Saga keeps run state in six separate stores and none of them can answer "what is the next step for
issue 1023?". This session adds the one file that can, and the step that fills its front section.

## What shipped

| Unit | What it is |
|---|---|
| U1 | `plugins/saga/scripts/run_record.py` — the schema, the store resolution, the read and write seam, the unknown-version refusal, the unknown-field round trip, and a `show` / `path` command line |
| U2 | `plugins/saga/references/run-record.md` and `repository-profile.md` — the schema as a document, with six tests pinning it to the code |
| U3 | `plugins/saga/scripts/admission.py` and a tracked `.saga-profile.json` |
| U4 | `saga.authoritative_next_step()` and `mirror_next_step_to_record()`; the spore freezes and re-injects the record |
| U5 | `plugins/saga/skills/plan/SKILL.md` §0.1b — admission is the first thing `/plan issue` does |
| U6 | saga 0.163.0 across `plugin.json`, `marketplace.json`, the changelog and the version literal in `tests/test_saga_plugin.py`; four journal decisions and four learnings |

Nothing was removed. The six stores the record replaces stay exactly where they are; the removals
card (issue 1030) deletes them once every reader has moved, and the replacement map is written into
`references/run-record.md` so that card has something to work from.

## The decisions that were made for me, and by whom

Every choice the `/work` skill would have asked about was answered in advance by the run
coordinator's stage-two message. Recorded here because a decision with no recorded source is a
decision nobody can check.

| Choice | Taken | Source |
|---|---|---|
| Saga | resumed `issue-1023`; no second saga minted | coordinator message |
| Branch | stayed on `issue/1023` | coordinator message |
| Execution backend | `inline`; no other backend offered or entered | coordinator message, and the plan's `backend:` field |
| Document-review gate | passed, nothing above P3 open; no override needed or permitted | coordinator message; `docs/reviews/2026-09-19-issue-1023-run-record-and-admission-doc-review.md` |
| Code review | none this stage; no lenses, no review artifact | operator decision of 2026-09-19, relayed by the coordinator |
| Pull request | none; the coordinator merges onto `parent/1018` | coordinator message |
| Version | 0.163.0 | coordinator message: the next free minor above both `parent/1018`'s 0.161.0 and the fold's 0.162.0 |
| Complexity triage | large — six units, twelve decisions, a task list built from the U-IDs | the skill's own documented rubric |
| Round-N detection | fresh build, not a re-entry: the resumed saga carries no `pr_refs` | the skill's documented rule |
| Front-loaded ceremony start | declined — the ceremony opens a draft pull request, and this card opens none | the skill's own "or when the operator declines" |
| Board moves | `Active` / `Implementing` submitted at §1.3b and landed | coordinator message; the skill's §1.3b |

## Board moves

Three, all through the reconcile controller, all landing with `field: Stage+Status` — the half-write
this repository has been caught by before would have reported a bare `Status`.

| When | Move | Result |
|---|---|---|
| Planning started | `Planning` / `Designing` | `written` |
| Plan cleared review | `Planning` / `Ready for Active` | `written` |
| Work started | `Active` / `Implementing` | `written` |

No further move was invented. In particular no "In Review" was submitted: the Operations board does
not define that status.

## Tests, and the evidence they are worth anything

Fifty-two new tests across `tests/test_run_record.py` and `tests/test_admission.py`. Two forms of
evidence, because a green test proves nothing on its own.

**Watched failing before passing.** The six guards that pin `references/run-record.md` to
`run_record.py` were written first and run against a missing document: six failures, then green once
the document existed.

**Reverted, and watched die.** Eight mutations, each restoring the tree afterwards:

| Mutation | Tests killed |
|---|---|
| Swap a run-setup-contract field name into the thirteen parameters | 15 |
| Drop a top-level key from the write order | 1 |
| Stop refusing an unknown record version | 3 |
| Drop unknown top-level fields instead of preserving them | 1 |
| Let a stale envelope win over the record for `next_step` | 1 |
| Replace the atomic move with a plain write | 1 |
| Reword the refusal line so the document no longer quotes it | 2 |
| Resolve the store from the worktree instead of the git common directory | 1 |

Two real bugs were caught this way rather than by inspection. The round-trip test failed because
`updated_at` moves on every write, which is correct behaviour and a wrong test — the clock is now
injected. And `resolve_plugin_root` returns `(root, rung)`, not a path, so `admission.py` raised a
`TypeError` on the one test that exercises the real resolution instead of an injected fake.

Every test that touches a store passes an explicit `tmp_path` root. Nothing in the suite writes into
the primary checkout's `.claude/saga/` store.

## The acceptance criteria

All four, run against a temporary store under the scratchpad.

1. `admission.py --issue 1023 --dry-run` filled 10 of the 13 parameters — one from the staffing
   component, four from the profile, five from the lifecycle defaults — printed the 8 questions that
   remained, and created no file.
2. `run_record.py show 1023` printed the record with `next_step`.
3. A record whose `schema` reads `run_record.v2` exits 3 with one line and no traceback.
4. A linked worktree created with `git worktree add` resolved the identical absolute path as the
   primary checkout and read the record through it — proved in a throwaway repository, with the
   negative alongside it: the worktree has no `.claude` directory of its own, so the old
   repository-relative shape would have found nothing.

## A correction to the plan

The plan's KTD4a said the record has eleven top-level keys. It has twelve: the table put
`created_at` and `updated_at` on one row. The code writes twelve, the guard pins twelve, and the
plan now says twelve with a note explaining the arithmetic. Caught by writing the guard.

## Residual

The store resolution refuses when the git common directory is not named `.git` — a repository
created with a separate git directory. That is deliberate and tested, but it means a checkout of
that shape cannot use the run record without passing `--store-root`. No such checkout is known here.
