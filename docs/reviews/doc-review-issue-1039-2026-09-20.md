# Doc review — issue 1039, the `/qa` strategy catalogue plan

## Review result

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-20-issue-1039-qa-strategy-catalogue-plan.md` |
| Reviewed revision | working tree, on branch `issue/1039` at base commit `61da4b1c` |
| Classification | plan (path tie-breaker `docs/plans/` plus the content signals `origin:`, `Implementation Units`, `Key Technical Decisions`, `U1`) |
| Formal rubric phase | none — the rubric engine covers the idea, issue and spec phases; a plan gets the readiness-skeptic pass |
| Triggered lenses | security and operations (secrets, credentials, deployment, an external service call) and deployment readiness (a non-production destination, a release surface, a version bump) |
| Blocked | no |
| Rounds | one review round, nine findings, all nine fixed in place |
| Linked issue | infiquetra/infiquetra-claude-plugins#1039, a child of #1018 |
| Run record | `.claude/saga/runs/issue-1039.json` (git-ignored, not durable review output) |

## Readiness summary

The plan is ready to drive implementation. Every finding below was fixed in the document itself
rather than deferred, and each fix is backed by a file read in this repository at the base commit
rather than by the specification's earlier reading of the same files.

The one finding that would have stopped the work is F1: an existing test pins the deleted script's
name into the skill corpus, so an implementer who followed the plan literally would have deleted
the script, rewritten the skill, and met a red gate with nothing in the plan to tell them why.

## Applied fixes

| # | Priority | Finding | Fix applied | Evidence |
|---|---|---|---|---|
| F1 | P0 | The plan deletes `qa_health_score.py` and rewrites the qa skill, but an existing test asserts that the skill document and the report reference each contain the literal string `qa_health_score.py`. The repository gate (requirement R16) could never pass. | Unit U7 now names `tests/test_saga_plugin.py` among its files and says which assertions are rewritten and into what. | `tests/test_saga_plugin.py:1281-1290` |
| F2 | P1 | The plan repeated the specification's citation of the evidence-ledger calls at `SKILL.md:172-181` and `310-313`. At the base commit those two passages already read the run record; the surviving ledger references are three lines in the report reference. | The Problem Frame now states the specification's reading was verified at a different commit, cites the three lines that actually survive, and records that the module still exists. | `grep -rn "evidence_ledger" plugins/saga/skills/qa/`; `plugins/saga/scripts/evidence_ledger.py` present |
| F3 | P1 | The plan defined only the `branch-preview` case of the boundary filter. The general containment rule was missing, and the end-to-end run at `non-production` (R15) depends on it — without the rule a `non-production` run selects only the widest rung. | R9 now declares the ladder `hermetic` ⊂ `branch-preview` ⊂ `non-production` and the "B or narrower" selection rule. | the specification's proof-boundary column |
| F4 | P1 | R15 softened the specification's "one published comment" into "one report", dropping the observable the operator's original complaint is about. | R15 now requires a comment published to the issue, and says which tool publishes it and why that is not a board write. | specification criterion 15 and its Functional Tester procedure, step 5 |
| F5 | P2 | Unit U7 created two new reference documents and left the two they replace implicitly deleted, although the card lists both only as "replaced". | U7 now renames both with `git mv` and then rewrites them, which keeps their history and avoids a deletion the card does not name. | the card's "Files expected to change" |
| F6 | P2 | The plan asserted "distinct exit codes" in a test scenario without declaring what they are. | U6 now declares the six-code table, following the build loop's existing pattern. | `plugins/saga/scripts/build_loop.py:120-125` |
| F7 | P2 | The `installed-surface` driver reads two installed plugin trees; the plan did not say how it resolves them, and a hard-coded home path would make the check read the wrong tree on another machine. | U4 now routes the resolution through fleet-core's plugin-resolution component, loaded the way admission already loads it. | `plugins/saga/scripts/admission.py:153-156` |
| F8 | P2 | The status card parses `health_score:` out of the qa artifact's frontmatter, which this change stops emitting. The plan named no consequence. | U7 records the consequence, confirms the existing guard degrades safely, confirms the literal string sweep is unaffected, and adds the follow-up to the deferred list. | `plugins/saga/scripts/status_card.py:546-600` |
| F9 | P3 | R3 described the widening judgment as adding "an eleventh candidate" although the catalogue holds ten strategies in total. | R3 now describes it as a catalogue strategy the profile's patterns did not select. | the plan's own R1 |

Two smaller edits went in alongside: every unit's test scenarios now name their repository-relative
test file, which the plan skill's hard floor requires, and the risk table now records that the run
record is git-ignored, so redaction is defence in depth rather than the only barrier.

## Remaining findings

None at P0, P1, P2 or P3. Every finding above was fixed in place.

## Residual risk from limited evidence

Three things this review could not verify from this repository and the plan therefore treats as
assumptions, each named in the document rather than hidden:

The CAMPPS scenario registry and the `campps-e2e-canary` executor were not read here — they live in
other repositories that are not checked out on this branch. The plan's delegation design comes from
the specification's reading of them, and the card's acceptance criterion for it is satisfied by a
recorded invocation rather than a live call, so a drift in that executor's command line would
surface at first real use rather than at the gate.

The `app-ui` and `hosted-surface` strategies ship declared but without drivers, which is a narrowing
beyond the specification's stated scope boundary. The plan declares the narrowing openly with its
reason and a revisit condition rather than quietly shipping two untested drivers.

The end-to-end run (R15) is the criterion that makes the other fifteen mean something, and it cannot
be rehearsed at plan time. If this repository's own profile turns out to produce fewer than two
`passed` strategies, the profile — not the criterion — is what should change, and that will be
visible in the work session rather than inferable from the plan.
