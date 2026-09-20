---
title: Doc review — issue 1001 code review on the sdlc roster plan
type: docs
status: complete
date: 2026-09-19
---

# Doc review — issue 1001 code review on the sdlc roster plan

**Readiness verdict: ready.** After two rounds of repair the plan can drive implementation without an
agent inventing a missing decision, and no `P0` or `P1` finding remains.

## Review-result contract

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-19-issue-1001-code-review-sdlc-roster-plan.md` |
| Reviewed revision | working tree, on branch `issue/1001` at base `4e951f0e` |
| Classification | plan (path tie-breaker `docs/plans/`; content signals `origin:`, `Implementation Units`, `Key Technical Decisions`, `U1`) |
| Rubric engine | not run — the rubric phases are idea, issue and spec; a plan document maps to none of them, and the readiness-skeptic pass ran in full |
| Blocked | no |
| Findings | 8 raised, 8 fixed in place, 0 remaining |
| Applied fixes | 8, listed below |
| Linked issue | infiquetra/infiquetra-claude-plugins#1001 |
| Linked run record | `<primary checkout>/.claude/saga/runs/issue-1001.json` |

## Findings and their disposition

| # | Priority | Finding | Status |
|---|---|---|---|
| D1 | P1 | The plan deleted machinery in `review_consensus.py` without settling the eleven existing test files that exercise it. `tests/test_lens_selection.py` imports symbols on the removal list, and eight more files name the same module. Following the plan literally would red the suite on functions removed on purpose. | Fixed — new unit U6 inventories all eleven with a decided fate each, and lands before U2's deletions |
| D2 | P1 | Two environment variables name the lifecycle checkout on this branch: `INFIQUETRA_SDLC_PATH` in the staffing component and mission-control, `INFIQUETRA_SDLC_ROOT` in sixteen role prompts. A review whose controller resolved one way would dispatch lens sessions resolving the other way or not at all. | Fixed — KTD9 adopts `INFIQUETRA_SDLC_PATH`, reads the second as a fallback, names which was read, and files the one-name repair as a follow-up under issue 1022 |
| D3 | P1 | Requirement R12 depends on a cycle counter the plan never located, and the lifecycle repository's rule is one counter per loop rather than one per run. An implementer would have invented it. | Fixed — KTD11 puts the counter in the run record's `review_cycles`, filtered by a new `loop` field valued `code_review` or `post_merge` |
| D4 | P2 | Existing run records may hold `review_result.v1` entries, and the plan said nothing about reading one after v2 lands. | Fixed — KTD12 reports a v1 entry by name, preserves it unchanged, counts it toward no allowance, and records why |
| D5 | P2 | The plan named `plugins/agent-launcher/roles/lens-reviewer.md` as consumed but never said what a lens brief carries, leaving the catalogue's no-shared-context-contamination and no-hidden-model-inheritance invariants unenforced. | Fixed — R5a states the five things a dispatch carries and the three it must not; R5b adds the durable per-lens write that failure isolation needs |
| D6 | P2 | The roster is resolved from the lifecycle checkout's working tree while the role prompts read that repository at the pin `5efc869f`, and the plan did not reconcile the two. | Fixed — KTD10 records both and explains why the generator cannot read a pin |
| D7 | P2 | `load_scoring_policy` was on the removal list with nothing named to replace it. | Fixed — U2 now states that thresholds come from the resolved roster the scorer is handed, loading nothing from disk |
| D8 | P3 | Child 935 names `tests/test_review_publish.py` while `tests/test_review_publication_lane.py` already exists for the same subject — the same one-word collision child 939 reports elsewhere. | Fixed — U6 renames the existing file, satisfying the child's criterion literally and leaving one file per subject |

## Claims verified against a current source

Every quantitative claim in the plan was checked, not accepted. The line counts of
`review_consensus.py` (2,787), `lens-roster.json` (1,375), `second_opinion.py` (2,076) and the
code-review skill and its references; `ROSTER_PATH` at line 94; the named symbols and their line
numbers in `review_consensus.py`; the ten `lens-roster.json` references across eight team-execution
files; and the lifecycle repository's catalogue, profile, ledger, strictness ladder, finding schema,
verdict table and repair allowances at revision `5efc869f`.

Two facts are load-bearing enough to name separately. The roster generator was **run**, not assumed to
run: from a temporary export of revision `5efc869f`, with a hand-built declaration, it produced a
`review_roster.v1` hashed `sha256:3a2863068c891cf12f51eb38b216f296a2e988107ed1fb9002cd7817b0700e7a`
and a refused validation report, using only the standard library. That settles the card's stop
condition in the negative — no vendoring is required. And the executor-verification ledger is empty
both at the pin and on the lifecycle repository's `origin/main`, which is the same commit; that was
read today with `git show` after a fetch, not recalled.

## Residual risk from limited evidence

Two things this review could not establish.

The dry run described in U7 has not been executed, because the scripts it exercises do not exist yet.
Its feasibility rests on the generator probe above, which is direct evidence for the roster half and
inference for the rest.

Whether the eleven existing test files can all be rewritten rather than deleted was judged from their
names and their imports, not from reading each one in full. U6 names a fate per file; the work stage
may find that a file's fate is different once opened, which is a plan revision rather than a surprise.
