# Issue 912 — repair round 9 record

**Status: repairs complete and evidenced; NOT accepted.** Issues #912–#916 and their board cards
stay open. Nothing here re-closes anything. Acceptance requires a typed `review_result.v1` bound to
the exact repaired revision, and no such result exists yet.

## What this round was

Cycle 8 closed six of the ten P1 findings by operator-scoped decision and stopped, leaving 45
findings open across 19 fix requests. This round worked all 45.

The work was decomposed by the run's planner into three file-disjoint worker lanes, reviewed by the
plan reviewer, revised, and executed concurrently in three separate worktrees of `77c01c99`.

## Custody and constraints held throughout

- `docs/plans/2026-08-30-agent-launcher-907-run-plan.md` was never modified, staged, removed or
  restored. Its SHA-256 is `f695be329f00597156b7c085d17885403a3b52b6b5afa1244f91524a694aac84` at the
  end of the round, unchanged, and it remains untracked. Every commit staged explicit paths; no
  `git add -A` was used at any point.
- No file under `plugins/mission-control/` or `plugins/orchestrate/` was touched.
- No plugin was installed and the marketplace was not refreshed — issue 907 has a live worker pinned
  to installed Saga 0.148.0.
- No worker ran any git command. Every mutation proof restored by `cp` backup plus a `cmp -s`
  byte-identity check; `git checkout` was never used to restore a working file.
- Issue 918 and its worktree were not touched. `origin/main` was not merged.
- Every commit references issues with `re #N`. No closing keyword, no attribution trailer.

## The commits

| Commit | Contents |
|---|---|
| `b878854a` | the approved three-lane repair plan |
| `8a250b1a` | lane A — the handoff envelope core, 22 findings |
| `f8f661bf` | lane B — contract prose, release note, journal, dialogue guard, 11 findings |
| `c21f7de8` | lane C — routing prose, its guards, the docs model and renderer, 14 findings |
| `5483b9e6` | the journal fold — three learnings and three decisions from lanes A and C |
| `f8f9515a` | lane C's per-finding disposition table |

## Gates

The full 25-step gate ran in a clean detached worktree at each integration commit, because
`tests/test_plan_artifact_conformance.py` scans `docs/plans/` from disk including untracked files
and the issue-907 plan would fail it in the working checkout.

| Commit | Result | Tests | Coverage |
|---|---|---|---|
| `8a250b1a` | GREEN — 25 steps, 0 blocking, 0 uncovered | 7297 passed, 7 skipped | 85% |
| `f8f661bf` | GREEN — 25 steps, 0 blocking, 0 uncovered | 7300 passed, 7 skipped | 85% |
| `c21f7de8` | GREEN — 25 steps, 0 blocking, 0 uncovered | 7309 passed, 7 skipped | 85% |
| `5483b9e6` | GREEN — 25 steps, 0 blocking, 0 uncovered | 7309 passed, 7 skipped | 85% |

Each was verified three ways: wrapper exit code 0, the `result.txt` marker, and a step-header count
of 25. The two advisory notes in every run are the board schema census (live-gated, cannot run
locally) and bandit; CI does not block on either.

The coverage total is byte-identical across all four runs. That was checked rather than assumed:
the coverage scope is `--cov=plugins`, so tests are excluded; lane B changed no `plugins/` Python at
all, and lane C's only one was a `globals()` removal that is statement-count neutral.

## The reconciliation, and what it caught

Every one of the 45 findings was cross-checked by identifier against the three lanes' evidence
notes. Lane C's commit claimed fourteen findings while its note named eight. The evidence existed —
its predicate probes covered AM-8, AU-4, AU-6, AU-7 and AU-10 — but nothing recorded which probe
closed which finding, so the claim was not checkable without rereading the diff. Lane C added a
fourteen-row disposition table; no code changed, verified byte-identical against `c21f7de8` for all
twelve source files.

**Four green gates did not surface this.** A green gate proves the code works; it says nothing about
whether a claimed repair has a proof behind it. The identifier-level reconciliation is what found it.

## Corrections to the record this round made

1. **DOC-1 was recorded as closed in the cycle-8 disposition and was not.** Cycle 8 rewrote only the
   fourth bullet of the 0.156.0 release note; the second bullet still said an out-of-root source with
   no readable declaration "still resolves by the path rule and can route live". Repaired in lane B.
2. **The SEC-1 acceptance test named in the first draft of the plan would have proved nothing.** Its
   fixture declared `pending-confirmation`, which emits no runnable command before or after the fix,
   so its "no `/issue --prepare`" assertion was green either way. The plan reviewer caught it; the
   security proof now asserts on `suggested_command` with a `plan-ready` fixture, and its red run
   shows the live command in the failure output.
3. **Every line number in the typed review is stale** for `handoff_envelope.py` by about 37 lines,
   because cycle 8 inserted the strict YAML loader and the alias-tracking walk. The plan carries a
   review-anchor-to-HEAD line map; findings were identified by content, never by the review's
   numbers.
4. **The AM-3 acceptance grep cannot return what the plan asked for.** The literal grep counts the
   function definition as well as the call, so it returns 2, not 1. Lane A supplied an AST proof —
   exactly one re-anchor call and two containment calls, all inside `resolve_source` — and declined
   to rename or disguise the definition to make a text count come out green. The controller accepted
   the mechanical correction.

## Residuals carried forward, unrepaired

- **API-23**, from cycle 7: the fail-closed guarantee is scoped to saga's reader; mission-control's
  own reader is unaffected. Tracked as issue 950. Reproduction table in `residuals-cycle-7.md`.
- **A defect on `origin/main`, not on this branch:** `tests/test_plan_artifact_conformance.py` scans
  `docs/plans/` from disk including untracked files, so any worktree holding an in-flight plan fails
  two tests unrelated to its own changes. Still unfiled, awaiting the operator's call. Every gate in
  this round worked around it by running in a clean detached worktree.
- **A version collision is possible and is not yet resolved.** This branch carries saga `0.156.0`;
  `origin/main` is at `0.155.0`. Issue 918 is a concurrent run in a separate worktree. If it lands
  carrying `0.156.0`, all eight version surfaces on this branch must re-bump before the candidate is
  frozen.

## Why this is not an acceptance

The last serialized typed result remains evidence-ledger sequence 17, bound to revision `1bcee0a9`,
`outcome: repairs_requested`. This round repaired what that result asked for and proved each repair,
but a repair round is not a verdict. The branch is not accepted until a seven-lens Saga Code Review
returns a `review_result.v1` that accepts the exact final repaired revision, and that review has not
run. It is deliberately held: the operator serialized it behind issue 918 landing, so that the two
concurrent runs cannot overwrite or invalidate each other.
