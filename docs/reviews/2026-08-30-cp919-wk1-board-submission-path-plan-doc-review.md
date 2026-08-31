# Document review — WK1 board-submission path plan (issue #927)

The plan is not ready to drive `cp919-worker-1`. Q1's three options do not cover the write shape the rest of the plan already assumes, and three authorized units will submit dead option names that Mission Control refuses.

| field | value |
| --- | --- |
| target path | `docs/plans/2026-08-30-cp919-wk1-board-submission-path-plan.md` |
| reviewed revision | working tree on `work/cp919-saga-work-improvement` at base `1c1c04a9`; plan is uncommitted (476 lines) |
| blocked status | **yes** — three P1 findings remain. `/work` blocks until they are repaired or explicitly overridden. |
| applied fixes | none. The review brief forbids editing the plan. |
| review artifact path | `docs/reviews/2026-08-30-cp919-wk1-board-submission-path-plan-doc-review.md` |
| linked issue | [infiquetra/infiquetra-claude-plugins#927](https://github.com/infiquetra/infiquetra-claude-plugins/issues/927) |
| linked parent | [infiquetra/infiquetra-claude-plugins#919](https://github.com/infiquetra/infiquetra-claude-plugins/issues/919) |
| pass | 1 of 2 (this document only) |
| override rationale | n/a |

## Applied fixes

None. Safe in-place edits were disabled by the review brief.

## Readiness summary

A worker can invert the guard, keep Orchestrate's writer, bind every unit to `opus / high` on `cp919-worker-1`, and name the three mutation proofs. That is not enough.

Q1 is the load-bearing gap. Its three options are a scope choice (this unit vs a child) plus a one-field Stage guess. They omit the pair-write the parent board contract and U5's own scope already describe, and option 3 cannot deliver the mandated `Ready` first move because `Ready` is valid on neither field. Meanwhile R1, U2, and U3 are authorized to proceed and will submit the dead `STATUS_LADDER` names against `Status`. Those writes halt at option resolution. U5 is gated, so the authorized path ships a caller that still cannot land.

This review does not answer Q1. It asks whether the question as written can be answered without inventing a fourth reading.

## Remaining findings by priority

| id | priority | status | claim |
| --- | --- | --- | --- |
| D1 | P1 | open | Q1's three options are incomplete and option 3 is mis-scoped |
| D2 | P1 | open | U2 and U3 are authorized to submit dead option names |
| D3 | P1 | open | KTD2/U3 pre-decide a live pair while Q1 is still open |
| D4 | P2 | open | Q2 is load-bearing and marked non-blocking |
| D5 | P2 | open | Silent dead vocabulary remains in R1, greps, and leftover map entries |
| D6 | P2 | open | U6 misses the fired W13 Stage revisit trigger and the process doc's "Stage is not live" sentence |
| D7 | P2 | open | U4's first-move test is underspecified against `FakeReconcileController` |
| D8 | P2 | open | U3 and U5 share `DEFAULT_STATUS_MAP`; U3's file list omits `STATUS_LADDER` |
| D9 | P3 | open | U6 `previous-comments` lens does not match that lens's trigger |
| D10 | P3 | open | Two pin nits: authorize line `:440` vs `:443`; "six moves" vs five named rungs |

## Issue-phase rubric review

Classification: issue-derived plan under `docs/plans/`, origin #927, parent #919. Issue-phase rubrics apply. All three core rubrics applied. All three extras applied: this is a multi-unit, two-repository change with a named serial graph.

Rubric findings are not reclassified as readiness findings. D1 independently meets the acceptance-criteria REVISE criterion (Q1 option 2 vs the "first board move happens" AC). Readiness treats the same contradiction as P1.

| rubric | score | note |
| --- | --- | --- |
| `acceptance_criteria_clarity` | 7/10 | Named greps and the three mutation proofs are reviewer-testable. Q1 option 2 accepts a `Ready` rung that cannot land, which collides with issue #927's first-move AC. U4's "real path" test has no named artifact. |
| `devils_advocate_issue` | 8/10 | KTD3 correctly keeps Orchestrate's writer. U5 is extra scope the issue did not name, but it is gated. Option 3 is under-challenged against `Ready` being valid on neither field. |
| `spec_fidelity` | 8/10 | Descent is #919 W-D1/W-D2/W-D6 and #927, not a spec.md. Submit-versus-execute is inherited, not reopened. KTD2's `Planning` / `Ready for Active` is schema-grounded for a committed plan, but it is a different pair than the parent's `Planning` / `Designing` row. |
| `context_completeness` | 8/10 | Pins, paths, and line numbers are strong. U4's new test files are unnamed. U3's file list is too narrow for the Ready rung it describes. |
| `issue_sizing` | 7/10 | Seven units plus a gated eighth concern is large for one child. Custody splits are real. U5 is the piece that should have been a named open question only, not a half-specified unit. |
| `prerequisite_mapping` | 7/10 | U1 → U2 → U3 → U4 → U7 is explicit. U6 concurrency is correct. The U3 → U5 / Q2 dependency is understated. |

## Q1 assessment — framing only, not an answer

The live Operations board and `workflows.stage_flow` at `222fcdd3` agree. Recomputed from `plugins/mission-control/config/sdlc-schema.json` in this worktree:

| check | result |
| --- | --- |
| `STATUS_LADDER` ∩ live Status | empty |
| `STATUS_LADDER` ∩ live Stage | `Shaping`, `Active`, `Verify` |
| `Ready` on Status | no |
| `Ready` on Stage | no |
| `Ready for Active` on Status | yes |
| live Status count | 26 |

`announce_units` submits `--field Status` because `payload=None` (`orchestrate.py:2063-2064`, `reconcile_controller.py:233`). `_set_lifecycle_field_cross_board` preflights option ids and raises before the first write (`sdlc_manager.py:3016-3017`, `:3097`). The plan's halt claim is correct.

The three options are not a complete decision set.

Option 1 and option 2 are the same design (re-point through the schema) with different scheduling. That split is correctly scoped as operator territory.

Option 3 is not a peer of 1 and 2. Passing `field: "Stage"` makes three of six rungs resolvable and leaves `Idea`, `Ready`, and `Done` still unresolvable. `Ready` is the rung W-D1 and R2 require. The plan already says the Shaping/Active/Verify overlap is "coincidence, not design" (U5), then offers that coincidence as the cheapest reading. A Stage-only write also cannot express the parent #919 table, which is pairs, and it fights KTD4 (do not hard-code a second ladder).

A fourth reading is already in the document and not in Q1: submit the `(Stage, Status)` pair the parent board contract names. U5's scope paragraph assumes that reading. KTD2 assumes it for one rung. Q2 names it and then marks it non-blocking. A worker answering Q1 from the three bullets cannot choose the pair-write without inventing an option.

Q1 is therefore not correctly scoped. It asks a scheduling question as if it were the vocabulary question, and it offers a one-field Stage guess that cannot satisfy the first-move requirement it is supposed to unblock.

## Dead-vocabulary dependencies

These units and checks still treat `STATUS_LADDER` names as writable values. They are not gated on Q1.

- R1's five submissions: `Shaping`, `Ready`, `Active`, `Verify`, `Done`.
- U2's replacement prose at Plan §0.6 / §5.0 and Work §1.3b / §4.4. Today's skill text already says `Status → Ready`, `Status → Active`, `Status → Verify`, `Status → Done`. Replacing the prohibition without renaming the option still submits a value Mission Control cannot resolve.
- U3's `DEFAULT_STATUS_MAP`. After the `codereview` deletion, `plan`/`docreview` stay `Shaping`, `work`/`fix` stay `Active`, `landed` stays `Done`. `Shaping` and `Active` are Stage options. `Done` is neither.
- `announce_units` (`orchestrate.py:2034`) skips any mapped value not in `STATUS_LADDER`. `tests/test_orchestrate_board_writeback.py:239-240` requires every map value to be a ladder member. A live name such as `Ready for Active` cannot enter the map without editing `STATUS_LADDER` (U5's file).
- Verification `grep -rnE '"Ready"'` matches the dead literal in `STATUS_LADDER` and would go green if U3 added `"Ready"`. It does not prove `Ready for Active`.
- Work §4.4 still describes Verify as a Status move. Verify is a Stage option. The live Status at that boundary is `Awaiting verification`. W-D2's post-merge rule is kept; the field name is not.

## Unit boundaries, custody, proofs, lenses, tiers, U6

**Boundaries.** U1 before U2 is required: the current guard asserts `"set-field-status" not in plan_skill` (`tests/test_saga_no_direct_write.py:165`). U6 is genuinely disjoint. U5 is the only claimed parallel-except-gate unit, and that gate is the problem above.

**Custody.** U1's file list is exact. U2's skill paths and the §1.5 / second-opinion exclusions match the live files (`work/SKILL.md:90-126`, `:317`). U4 says "new tests under `tests/`" with no names. U3 lists only `DEFAULT_STATUS_MAP` but the Ready rung it describes cannot pass the existing ladder-membership test without `STATUS_LADDER`. U3 and U5 both edit the map.

**Mutation proofs.** Issue #927 names three. The plan places them correctly: U1 narrows the scan root, U2 deletes the Plan §5.0 submission, U3 restores `"codereview": "Verify"`. U4 restates all three as a surviving suite. That mapping is complete.

**Lenses.** Every named id exists in `lens-roster.json`. `correctness` and `testing` are always-on. `adversarial`, `agent-usability`, `documentation-clarity`, `api-contract`, and `reliability` are valid conditionals for those units. U6's `previous-comments` is the wrong lens: it fires only when a pull request already has review threads, not when a journal entry must be superseded.

**Tiers.** Every unit is bound `opus / high` on `cp919-worker-1`, with cheaper fallbacks recorded and no fabricated spend column. That matches the #919 roster (Claude Opus 5, High, company account for issue #927). The binding is an operator override, not a work-shape derivation. No substitution path is left open.

**U6.** The rejected alternative *"Giving `/plan` and `/work` a submitting path"* is at `infiquetra-sdlc` `DECISIONS.md:635`. The authority-versus-mechanism sentence is at `:606-607`. The W6/#87 revisit trigger is at `:651` and has fired. The same paragraph also says to revisit "if W13 creates the `Stage` field"; that trigger has also fired (schema changelog 2026-08-29). The process doc's W7 section still says Stage is "not live on any board" (`saga-board-write-authority.md:58-59`) and still lists the dead `Status → Shaping/Ready/Active/Verify/Done` moves (`:30-31`). U6's scope statement covers submit-versus-execute only. The config/ empty-diff acceptance check is the right bound.

## Triggered lenses

Security/ops scrutiny applies: every unit except U6 and U7 submits or guards GitHub project-field writes. No secrets or new credentials are in scope. Founder-review was not triggered. Deployment readiness was not triggered; Verify remains post-merge plus deploy-or-artifact per W-D2.

## Spot-checks against the pinned tree

Verified in `/Users/jefcox/workspace/infiquetra/orch-claude-plugins-919` at `1c1c04a9`, and in `infiquetra-sdlc` at `222fcdd3`.

- `STATUS_LADDER` is at `orchestrate.py:1854`. `DEFAULT_STATUS_MAP` is at `:1861-1868` with `"codereview": "Verify"` at `:1866` and `"docreview": "Shaping"` at `:1863`.
- `announce_units` calls `_reconcile_call(..., payload=None)` at `:2064`. `mapped_status` is a single string (`:1919`). Values off the ladder are skipped, not failed loud (`:2034-2041`).
- `default_board_writer` is at `board_progression.py:381`. Field default is `payload.get("field") or "Status"` at `:442`. The authorize check is at `:443`, not `:440`. `CORRECTION_FIELDS` is at `reversibility_certificate.py:59`.
- Plan §0.6 (`plan/SKILL.md:123-132`) and §5.0 (`:308-316`) carry the superseded prohibition. Work §1.3b (`work/SKILL.md:247-256`) matches. Work §4.4 (`:776-799`) forbids the Status move, drives `sub-issue-close` only, and says Verify "never fires."
- Guard tests still assert `"set-field-status" not in` the Plan and Work skills (`test_saga_no_direct_write.py:165-178`). Scan root is `SAGA_ROOT`. `AUTO_CORRECT_OP_KINDS` is empty (`reconcile_controller.py:90`).
- `TestStatusMapping` and `TestALandedUnitAnnounces` exist and use `FakeReconcileController`.
- Worktree `plugins/saga/.claude-plugin/plugin.json` is `0.150.0`. Marketplace saga is `0.150.0`, orchestrate `3.0.8`. Plan skill md5 in this worktree is `9b28d1ff5c75452ca5df8864daacfcff` as claimed.
- `intent_flow.statuses` is the six-name ladder (`sdlc-schema.json:123`). `stage_flow` is the live vocabulary (`:129-144`).

## Decisions taken without asking

1. Do not edit the plan. The brief forbids it.
2. Do not answer Q1. Assess whether its three options are complete and correctly scoped.
3. Do not write the board, commit, or push.
4. No external-reviewer panel. The brief asked for one installed document review, not a cross-engine pass.
5. Report-only second-opinion: D1–D10 are assigned; no `external_opinion` is recommended.
6. Write this artifact because a formal rubric review ran and P1 findings remain.

---

### D1 — Q1's three options are incomplete and option 3 is mis-scoped

**Priority:** P1

**Where:** plan Open questions Q1 (lines 451–466); U5 coincidence sentence (line 295); U5 scope (lines 297–301).

**What is wrong.** Options 1 and 2 are one design with two schedules. Option 3 (pass `field: "Stage"`) cannot deliver `Ready`, which is valid on neither live field, so it cannot satisfy R2. The pair-write already assumed by U5's scope and by issue #919's board table is not a listed option. The plan itself calls the Stage-name overlap coincidence, then offers that overlap as the cheapest reading.

**Why it matters.** An operator answering Q1 from the three bullets cannot choose the write shape the rest of the plan implements. A "3" answer still leaves the first-move rung dead.

**Suggested repair.** Keep Q1 unanswered. Add the pair-write as an explicit option, and state that option 3 is a partial field retarget that still requires a `Ready` remapping. Do not pick a winner in the plan until the operator answers.

### D2 — U2 and U3 are authorized to submit dead option names

**Priority:** P1

**Where:** plan R1 (lines 57–59); U2 (lines 187–196); U3 (lines 216–232); Sequencing (lines 398–399).

**What is wrong.** The plan says U5 is gated and that U1–U4, U6, and U7 are complete without it. U2's five submissions and U3's remaining map values (`Shaping`, `Active`, `Done`, and a new `Ready` rung) are the dead `STATUS_LADDER` names. Submitted as `Status`, every one of them fails option resolution. `announce_units` will accept `"Ready"` because it is on the local ladder, then Mission Control will halt.

**Why it matters.** The authorized worker path builds the caller the issue asked for and still cannot move a card. Issue #927's first-move AC and "writes through Mission Control" AC can be claimed from tests while live writes stay dark.

**Suggested repair.** Either gate U2's option strings and U3's map values on Q1, or require those units to submit only names that already exist on the live field the operator chooses — without choosing that field in this review.

### D3 — KTD2/U3 pre-decide a live pair while Q1 is still open

**Priority:** P1

**Where:** plan KTD2 (lines 111–116); U3 (lines 226–232).

**What is wrong.** KTD2 states that `Ready` resolves to `Stage=Planning`, `Status=Ready for Active`, and that this is "the one place Q1's answer changes a value." U3 then installs that pair at the `docreview` boundary. `DEFAULT_STATUS_MAP` is `dict[str, str]` and `mapped_status` returns one string. The existing test requires that string to be a `STATUS_LADDER` member. The pair cannot be stored or announced without U5's API change, which is not authorized.

**Why it matters.** A worker who follows KTD2 invents a pair-write. A worker who follows the map type ships `"Ready"` and stays halted. Both are plan-following. The parent table's `Planning` / `Designing` row is a third live pair nobody chose.

**Suggested repair.** Move the live-pair sentence out of KTD2/U3 and into Q1 as an option. Leave U3's structural change (`codereview` off `Verify`; `docreview` as the Ready *boundary*) independent of the option string.

### D4 — Q2 is load-bearing and marked non-blocking

**Priority:** P2

**Where:** plan Q2 (lines 468–471).

**What is wrong.** `board_progression` submits one `--field`. The parent contract and KTD2 describe pairs. Q2 says Q1 "probably settles this." Q1's three bullets are all single-field.

**Why it matters.** Every U2 fenced invocation and every U3 announce call needs a field list before it can be written. Leaving that as a footnote guarantees invention at implementation time.

**Suggested repair.** Promote Q2 to blocking for U2, U3, and U5, or fold the pair-vs-single choice into Q1's option list.

### D5 — Silent dead vocabulary remains in R1, greps, and leftover map entries

**Priority:** P2

**Where:** plan R1 (lines 57–59); Verification (lines 436–438); U3 leftover keys (lines 1861–1868 in source); Work §4.4 (source lines 780–799).

**What is wrong.** After a correct remapping, `grep -rnE '"Ready"'` still matches `STATUS_LADDER` and would match a dead `"Ready"` map entry. `landed: "Done"` is not on either live field. Work's Verify sentence still names a Status move.

**Why it matters.** The parent's own verification block uses the same `Ready` grep. A dead-literal add satisfies the check.

**Suggested repair.** Pin the live names the operator chooses, or grep for the submission seam and a resolved option from the schema, not the retired token.

### D6 — U6 misses the fired W13 Stage trigger and the process doc's stale Stage sentence

**Priority:** P2

**Where:** plan U6 (lines 315–326); KTD5 (lines 132–141); `infiquetra-sdlc` `DECISIONS.md:651-654`; `saga-board-write-authority.md:30-31, 58-59`.

**What is wrong.** KTD5 cites the W6/#87 revisit trigger and the rejected alternative correctly. The same Revisit-when clause also fires when W13 creates Stage. The process doc still says Stage is not live and still lists `Status →` the six dead names. U6's scope does not name those sentences.

**Why it matters.** A docs PR that supersedes the rejected alternative and leaves "Stage is not live" in the same file re-teaches the stale model.

**Suggested repair.** Keep U6 documentation-only. Require the W7 section and the journal entry to drop the "Stage is not live" claim and to cite both fired revisit triggers. Do not touch `config/`.

### D7 — U4's first-move test is underspecified against `FakeReconcileController`

**Priority:** P2

**Where:** plan U4 (lines 250–267); `tests/test_orchestrate_board_writeback.py` (`FakeReconcileController`, line 83).

**What is wrong.** The three named mutation proofs are present and correctly assigned. The "most important" U4 test says a fixture may not stand in for the real submission path. The only announce tests today use `FakeReconcileController`. The plan does not name the seam that counts as "real" (argv to `sdlc_manager.py`, recorded `flow set-field --correction`, or a live board write).

**Why it matters.** A worker will either reuse the fake and claim the path, or invent a live GitHub write from a unit test.

**Suggested repair.** Name the recorded Mission Control argv, or an in-process `default_board_writer` with an injected runner, as the proof. Forbid a live project-field write from pytest.

### D8 — U3 and U5 share `DEFAULT_STATUS_MAP`; U3's file list omits `STATUS_LADDER`

**Priority:** P2

**Where:** plan U3 Files (lines 218–219); U5 Files (lines 279–280).

**What is wrong.** U3 adds a Ready rung to the map. U5 re-points the same map and the ladder. The ladder-membership test makes a live option string a U5 edit.

**Why it matters.** If Q1 authorizes U5 after U3 merges, the map is rewritten twice. If Q1 never authorizes U5, U3's rung is a dead name that the local ladder accepts.

**Suggested repair.** Give U3 custody of the `codereview` deletion and the `docreview` *boundary* only. Leave every option string to the Q1-gated unit.

### D9 — U6 `previous-comments` lens does not match that lens's trigger

**Priority:** P3

**Where:** plan U6 Lenses (lines 336–338); `lens-roster.json` `previous-comments` trigger.

**What is wrong.** `previous-comments` applies when a pull request already has review threads. U6 needs a journal supersession, which `documentation-clarity` already covers.

**Why it matters.** An integrated Code Review that launches `previous-comments` on a new sdlc PR will mark the lens non-applicable and look like a miss.

**Suggested repair.** Drop `previous-comments` from U6. Keep `documentation-clarity`. The always-on four still run.

### D10 — Authorize line and "six moves" pin nits

**Priority:** P3

**Where:** plan Problem Frame (lines 28–33); High-Level Technical Design (implied `:440`).

**What is wrong.** The authorize check is `board_progression.py:443`. The issue and plan say "six" moves; R1 names five (`Shaping`, `Ready`, `Active`, `Verify`, `Done`). The sixth is never identified.

**Why it matters.** The plan already says to re-resolve line numbers. The count mismatch is inherited from #919/#927.

**Suggested repair.** Re-pin `:443` at preflight. Say "five named Saga rungs" unless the sixth is named.

## Residual risk from limited evidence

The live Operations board was not re-queried in this session. Vocabulary checks used the schema at `222fcdd3` and the worktree vendored copy, which agree with each other and with the plan's table. If GitHub's project option names have drifted from that schema since the pin, Q1's facts would need a fresh board read before any write lands.

This review did not read the uncommitted evidence package in `infiquetra-agent-operations`. Issues #919 and #927, as amended 2026-08-30, were treated as authoritative.
