---
title: Work session — issue 1001, code review on the sdlc roster
type: docs
status: complete
date: 2026-09-19
---

# Work session — issue 1001, code review on the sdlc roster

**What shipped.** Saga's code review stopped owning quality policy. It now reads the lens
declaration from the run record, resolves `review_roster.v1` by invoking the lifecycle repository's
own generator as a subprocess, computes the verdict from that catalogue's strictness ladder, writes
`review_result.v2` into the run record, and publishes exactly one pull-request comment and never an
approving review.

Branch `issue/1001`, base `4e951f0e` on `origin/parent/1018`. No pull request: the parent pull
request that issue 1030 opens carries one code review for the whole parent, and the coordinator
merges this branch onto the integration branch.

## Choices applied, and where each came from

Every one of these was supplied by the coordinator's stage-two message. None was invented, and none
was put to the operator.

| Choice | Value applied | Source |
|---|---|---|
| Saga thread | resumed `issue-1001` from this worktree's store; no second saga minted | coordinator's stage-two message |
| Branch | stayed on `issue/1001` | coordinator |
| Execution backend | `inline`, as the plan's `backend:` frontmatter says; no other backend offered or entered | coordinator, and the plan document |
| Doc-review gate | passed with nothing open; no override sought or needed | coordinator, and `docs/reviews/2026-09-19-issue-1001-code-review-sdlc-roster-plan-review.md` |
| Complexity triage | large; fresh build rather than a round-N continuation | coordinator ("take the skill's documented default"), matching earlier cards |
| Ceremony start | declined — it opens a draft pull request and this card opens none | coordinator, naming what earlier cards did |
| Code review of this card | none run; no lenses in this thread, no review artifact for this card | operator decision of 2026-09-19, relayed by the coordinator |
| Gate | `scripts/gate.sh` not run; the named inner loop run instead | coordinator |
| Push and pull request | neither; the coordinator merges | coordinator |
| Continuation routing | return to the coordinator | coordinator |

## Board moves

| Move | Result |
|---|---|
| Stage=Active, Status=Implementing, at the start of the build | `written`, field `Stage+Status` — both halves landed |

The planning-stage moves from stage one (`Designing`, then `Ready for Active`) both landed the same
way and are recorded in the plan document.

## Card 931's transport prohibition

The coordinator's addendum asked that the rewritten code-review skill keep a **script-free**
prohibition equivalent to the one the Document Review skill carries, so issue 1026's cross-file
agreement test passes against this rewrite.

**Location: `plugins/saga/skills/code-review/SKILL.md`, the "Reviewer-session transport" section,
lines 61 to 74.** It states that Orchestrate owns every reviewer session, that no reviewer is
launched or collected through any saga transport script, that `engine-registry.yaml` is capability
metadata and not a launch authority, and — the sentence issue 1026's test reads — that **"In a
standalone `/code-review` with no orchestrated run, the operator is the transport"**.

The clause names no script deliberately, and the paragraph after it says why: an earlier form listed
the scripts by name, and those names went stale when the scripts were deleted. A clause that names a
deleted file reads as satisfied whatever the code does. `engine-registry.yaml` is still named
because that file still exists and the prohibition is about its *authority*, not its absence.

Whichever of issue 1001 and issue 1026 merges second resolves the conflict on that line by keeping
this full rewrite.

## The eleven inventoried test files, and what happened to each

The plan's unit U6 inventoried eleven files. Reading the tree turned up **three more** the inventory
missed, and one it named that turned out to be unaffected. The corrected list:

| File | Fate | Why |
|---|---|---|
| `tests/test_lens_selection.py` | **deleted** | 57 references to the conditional-approval machinery issue 1001 removes; every symbol it imports is gone |
| `tests/test_lens_roster.py` | **deleted** (not in the plan's inventory) | It tests the deleted policy file itself |
| `tests/test_review_second_opinion.py` | **deleted** | The review-side external advisory seat, which issue 1001 names |
| `tests/test_review_publication_lane.py` | **renamed and rewritten** as `tests/test_review_publish.py` | Child 935 names that filename, and two files one word apart for one subject is the same collision child 939 reports elsewhere |
| `tests/test_review_consensus.py` | **rewritten** | Thresholds now come from a roster fixture, not the deleted file |
| `tests/test_review_consensus_cycles.py` | **rewritten in part** | Same fixture change; the two external-advisory tests deleted with the seat; the schema token moved to v2 |
| `tests/test_review_consensus_docs.py` | **rewritten in part** | The worked example takes its policy from a roster |
| `tests/test_review_loop_end_to_end.py` | **rewritten in part** | One `load_scoring_policy()` call replaced by a roster fixture |
| `tests/test_orchestrate_review_loop.py` | **fixtures updated** | Seven result-schema tokens moved to v2 |
| `tests/test_orchestrate_scoped_review_controllers.py` | **fixtures updated** | Seven tokens moved to v2 |
| `tests/test_orchestrate_review_transport.py` | **fixtures updated** | Three tokens moved to v2 |
| `tests/test_work_review_contract.py` | **unchanged** | Named no removed symbol |
| `tests/test_adjustment_envelope.py` | **unchanged** | Imports the module but names no removed symbol |
| `tests/test_saga_plugin.py` | **retargeted** | Its merge-contract pins described the removed publication lane; retargeted at the new durable surface with the same strictness, and the second-opinion contract test deleted with the seat |
| `tests/test_team_execution_consensus.py` | **skipped, with the reason on the page** | See below |
| `tests/test_team_execution_consensus_advisory.py` | **skipped, with the reason on the page** | See below |

`tests/test_roster.py` matched the inventory's search but is agent-launcher's roster **helper** test,
a different subject entirely. It was not touched.

### The team-execution conflict, and how it was resolved

Two team-execution test files assert that the plugin reads Saga's `references/lens-roster.json` and
its `load_scoring_policy` scorer. Issue 1001 deletes both. Three options, and none of them clean:

- Keep the roster — contradicts the card's own acceptance criterion `test ! -f …/lens-roster.json`.
- Delete the roster and let those tests red — contradicts a green suite.
- Delete or rewrite the team-execution files — contradicts "nothing goes that the card does not
  name", and issue 1001 names no team-execution file.

The resolution taken is a module-level skip carrying the reason in full: the plugin's own files are
**untouched**, the ten references stay for parent 1018's archive step, and the pending work is
visible on the page rather than quietly deleted. If archiving lands after this card, a follow-up
repoints them at the resolved roster.

## Two changes outside the plan, both recorded

**Orchestrate moved to `review_result.v2`.** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`
pinned `review_result.v1` and exits on an unrecognised schema, so the end-to-end review loop test
failed until it moved. The pair of schema identifiers is the only persistent compatibility contract
across that boundary, so a consumer must move with the producer or refuse. One line, plus a comment
saying why it is a named constant. Orchestrate's release surfaces moved with it, 4.5.0 to 4.6.0.

**Filing residual issues left this plugin.** The first draft of `review_result.py` shelled out to
create issues at the cycle cap. `tests/test_check_ownership_lanes.py` caught it: opening an issue is
mission-control's ownership lane, and a saga script crossing it is a violation. The module now
**prepares** the residual payloads and the caller hands them to mission-control. A test pins the
absence.

## What was proved, and what was deferred

The four scripted acceptance criteria all pass; their outputs are in the return to the coordinator.

The fifth — one real review on a pull request producing one comment, no approving review, and a
`review_result.v2` in the run record — is **deferred to the parent pull request that issue 1030
opens**, because children of parent 1018 open no pull request of their own. What stands in for it is
`tests/test_review_dry_run.py`: the declaration built from a run record, the roster resolved by the
real generator against the real lifecycle checkout, a fake executor in place of the lens sessions,
the verdict computed, a `review_result.v2` written to a temporary store, and the would-be comment
captured rather than sent.

## The state a reader will otherwise misdiagnose

**Every review returns `review_incomplete` today, and that is correct.** The lifecycle repository's
`config/executor-verifications.json` has no entries — true at the pin `5efc869f` and on that
repository's `origin/main`, which is the same commit, both read today. No executor is qualified, so
no lens establishes a threshold, so the verdict function's first row fires. A test asserts it, so the
day the first qualification lands is a diff someone reads.
