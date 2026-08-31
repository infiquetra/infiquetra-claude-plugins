# Document review — WK1 board-submission path plan, round 2 (issue #927)

The ten round-1 findings are repaired. The plan is still not ready to drive `cp919-worker-1`, because the pair decision was not carried into the one-field submission seam or the first-move proof.

| field | value |
| --- | --- |
| target path | `docs/plans/2026-08-30-cp919-wk1-board-submission-path-plan.md` |
| reviewed revision | working tree on `work/cp919-saga-work-improvement` at base `1c1c04a9`; plan is uncommitted (758 lines, `deepened: 2026-08-30`) |
| prior review | `docs/reviews/2026-08-30-cp919-wk1-board-submission-path-plan-doc-review.md` |
| blocked status | **yes** — one new P1 remains. `/work` blocks until it is repaired or explicitly overridden. |
| applied fixes | none. The review brief forbids editing the plan. |
| review artifact path | `docs/reviews/2026-08-31-cp919-wk1-board-submission-path-plan-doc-review-r2.md` |
| linked issue | [infiquetra/infiquetra-claude-plugins#927](https://github.com/infiquetra/infiquetra-claude-plugins/issues/927) |
| linked parent | [infiquetra/infiquetra-claude-plugins#919](https://github.com/infiquetra/infiquetra-claude-plugins/issues/919) |
| pass | round 2 of the WK1 plan |
| override rationale | n/a |

## Applied fixes

None. Safe in-place edits were disabled by the review brief.

## Readiness summary

Decisions A and B are sound. U5 is correctly in scope. The dict-of-str map, `mapped_status`, the ladder-membership test, and the announce skip must move together, and the plan now gives that bundle to one unit. Execution order is `U1 → U2 → U3 → U5 → U4 → U7` with U6 concurrent, and no U-ID was renumbered. The false-green `Ready` grep is gone from the plan and from both live issues.

The leftover hole is the call. `default_board_writer` and `_reconcile_call` still write one field per invocation. U5 says "name both fields" on that one call. U4's first-move assertion is a single `flow set-field --field <Stage|Status>` argv. A Status-only write of `Ready for Active` is a live option, so that proof can go green while Stage stays wherever it was.

## D1–D10 dispositions

| id | round-1 priority | disposition | note |
| --- | --- | --- | --- |
| D1 | P1 | **repaired** | Q1 is gone. Decisions A and B replace the three options. Field-retarget-alone is foreclosed, with a stated reversal. |
| D2 | P1 | **repaired** | R1 is a five-row live-pair table. U2 must rename the four `Status →` sentences. U3 writes no option string. Remaining call-shape risk is N1, not an unrepaired D2. |
| D3 | P1 | **repaired** | The live pair left KTD2. KTD2 is actor and trigger only. KTD6 makes the retype one unit with the ladder and the test. |
| D4 | P2 | **repaired** | Q2 is answered by Decision A: pairs. It is no longer a non-blocking footnote. |
| D5 | P2 | **repaired** | Dead tokens are banned in R1. The three replacement commands are in the plan and in live #919 and #927. All three are RED at `1c1c04a9` and name all six dead rungs. |
| D6 | P2 | **repaired** | U6 is three corrections: supersede the bullet, cite W6 and W13, delete the two false sentences at `:29-31` and `:58-59`. `config/` stays untouched. |
| D7 | P2 | **repaired** | Both test files are named. The seam is `default_board_writer` with the injected `runner` at `:385` / `:402`. Live board writes from pytest are forbidden. The new pair-shaped hole in that argv is N1. |
| D8 | P2 | **repaired** | U3 owns the `codereview` deletion and the `docreview` boundary. U5 owns `STATUS_LADDER`, the map retype, `mapped_status`, the announce skip, and `test_the_defaults_never_leave_the_ladder`. |
| D9 | P3 | **repaired** | `previous-comments` is withdrawn from U6 with the roster trigger quoted. |
| D10 | P3 | **repaired** | Authorize check is pinned at `:443`. The missing sixth rung is named as unidentified. The plan builds the five that exist. |

Nothing from the round-1 list is unrepaired. Nothing was only partially repaired.

## New findings the repair introduced

| id | priority | status | claim |
| --- | --- | --- | --- |
| N1 | P1 | open | The pair is decided; the one-field submission seam and the first-move argv still allow a Status-only write |
| N2 | P2 | open | U5's file list names one test; the retype breaks `Run.status_map`, the override tests, and the single-`status_writes` announce fixtures |
| N3 | P2 | open | U5 "fill every rung from R1's table" does not name `work` / `fix` / `landed`, and `landed → Retro` would skip Verify |

## Decisions A and B

The derivation is sound. It is not a silent product pick.

**A.** W-D1 requires a real first-move path to `Ready`. Live Operations and `workflows.stage_flow` at `222fcdd3` still agree: six Stages, 26 Statuses, bare `Ready` on neither. A single-field retarget cannot express that rung. The parent #919 table is already pairs and matches `stage_statuses`. All five R1 pairs are live in the schema. Overturning A requires a board-option change, which is outside the run. That is the right reversal.

**B.** Issue #919 fixes membership at four native children and admits a fifth only by an amendment on that issue. No such amendment exists. Putting the re-point inside WK1 expands #927; it does not add a child. #919 already gives WK1 `orchestrate.py`'s announce path and `DEFAULT_STATUS_MAP`. The stop condition fires on a fifth child, not on another unit inside an existing one. Overturning B requires a membership amendment. That is the right reversal.

**U5 in scope is correctly worked through at the type layer.** `DEFAULT_STATUS_MAP` is `dict[str, str]`. `mapped_status` returns one string (`orchestrate.py:1919`). `announce_units` skips any value not in `STATUS_LADDER` (`:2034-2041`). `test_the_defaults_never_leave_the_ladder` asserts `set(values) <= set(STATUS_LADDER)` (`test_orchestrate_board_writeback.py:239-240`). A live pair cannot enter that map while those four facts stand. KTD6 is right to move them together and to reject a delimited string. U3-before-U5 is right: do not retype a key you are about to delete. U5-before-U4 is right: do not pin the stale shape.

**U5 is not fully worked through at the call layer.** That is N1, not a failure of A or B.

## Outside-the-plan changes

**Q1.** Resolved by derivation, recorded as two reversible assumptions. See above. Not re-litigated as an open question.

**False-green `Ready` grep.** Live #919 and #927 now carry Planner A's three commands, marked `REPLACED 2026-08-31`. The plan's block matches them. Re-run in this worktree at `1c1c04a9`:

| check | result |
| --- | --- |
| Positive | exits 1; names all six: `plan/docreview=Shaping`, `work/fix=Active`, `codereview=Verify`, `landed=Done` |
| Negative A | `STATUS_LADDER` at `:1854` and `"landed": "Done"` at `:1867` |
| Negative B | `plan/SKILL.md:312`, `work/SKILL.md:253`, `:780`, `:787` |
| Old `grep -rnE '"Ready"'` | still passes on `STATUS_LADDER` — the false green the replacement exists to kill |

The plan's claimed RED output is correct. Negative B's honest limit on Plan §0.6 (prose, no arrow) is stated and is real.

**`artifact_pointer.py`.** Live #919 now lists `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py` for WK4 and records the old saga path as a correction. This WK1 plan does not mention the old path and does not contradict the amendment.

## Execution order and identifiers

The claim holds. Identifiers are still U1–U7. U5 moved ahead of U4; it was not renamed. The mermaid graph matches the prose. The three load-bearing orderings (U1 before U2, U3 before U5, U5 before U4) are the right ones. U6 remains the only concurrent, disjoint worktree.

## Issue-phase rubric review

Classification unchanged: issue-derived plan, all three cores and all three extras. Rubric findings are not reclassified as readiness findings. N1 independently meets the acceptance-criteria REVISE criterion (the first-move AC can pass on a one-field write).

| rubric | score | note |
| --- | --- | --- |
| `acceptance_criteria_clarity` | 8/10 | Live pairs and the three RED checks are reviewer-testable. U4's argv still describes one field. |
| `devils_advocate_issue` | 8/10 | U5 inside WK1 is justified. The pair call and the leftover Orchestrate keys are the remaining structural smell. |
| `spec_fidelity` | 9/10 | Descent is live #919 / #927. Verification commands now match. R1's fifth pair is the one stretch against the parent close-out row. |
| `context_completeness` | 8/10 | Type-layer pins are exact. Call shape, `Run.status_map`, and `work`/`fix`/`landed` are thin. |
| `issue_sizing` | 8/10 | Seven units plus a justified U5 is large and now coherent. Decision B is the reason it stays one child. |
| `prerequisite_mapping` | 9/10 | WK1 → rest of the run is unchanged. Inside WK1 the serial graph is explicit and correct. |

## Triggered lenses

Security/ops scrutiny still applies: every unit except U6 and U7 submits or guards GitHub project-field writes. No secrets. Founder-review not triggered. Deployment readiness not triggered.

## Spot-checks

Verified in `/Users/jefcox/workspace/infiquetra/orch-claude-plugins-919` at `1c1c04a9`.

- Authorize check is `board_progression.py:443`. Field default is `:442`. Injected `runner` is `:385`, consumed at `:402`.
- `_reconcile_call` (`orchestrate.py:1949`) drives one `--target-state` and an optional one-field payload. `announce_units` still calls it once with `payload=None` at `:2063-2065`.
- `default_board_writer` emits one `flow set-field --field … --option … --correction`.
- `Run.status_map` is `dict[str, str]` at `:420`. Override tests use `{"work": "Ready"}`. `FakeReconcileController` tests assert `len(status_writes) == 1`.
- `_resolve_sdlc_schema` exists. The stage-flow helper is `_stage_flow_rules`, not `_stage_flow`. Orchestrate currently imports neither.
- `LIVE_READABLE_CORRECTION_FIELD` is `"Status"`. A Stage write already skips the controller's live drift check. That is existing behaviour, not a plan defect.
- Schema `entry_option_rule` names `Ready for Active` (Planning) and `Ready to close` (Verify/Retro) as the terminal exceptions. KTD2's derived rung is schema-grounded.
- Status option count is 26. The plan's correction from 25 is right.

## Decisions taken without asking

1. Do not edit the plan.
2. Do not re-open Q1 as a question. Judge the recorded derivation.
3. Do not write the board, commit, or push.
4. No external-reviewer panel.
5. Report-only second-opinion: N1–N3 assigned; no `external_opinion` recommended.
6. Write a new round-2 artifact. Leave the round-1 file as the historical record.

---

### N1 — The pair is decided; the one-field seam and the first-move argv still allow a Status-only write

**Priority:** P1

**Where:** Decision A (lines 76–93); U5 item 5 (lines 454–456); U2 Scope (lines 291–305); U4 proof (lines 380–387); `orchestrate.py:1949-2065`; `board_progression.py:440-461`.

**What is wrong.** A pair cannot travel through one `_reconcile_call` or one `default_board_writer` invocation. Each takes one `target_state` and one `field`. U5 says the call "must name both fields explicitly" as if one payload could carry them. U2 says "the runnable submission" in the singular. U4's proof is one captured argv: `--field <Stage|Status> --option <live option>`. `Ready for Active` is a live Status. A worker who submits only that half satisfies the written test, lands a legal Status, and leaves Stage wherever it was — including `Shaping`, where `Ready for Active` is not a valid pair.

**Why it matters.** Decision A exists so the first-move path is a real pair. The most important test in the plan can go green without Stage moving. That is a new false green, in the same family as the `Ready` grep this repair just killed.

**Suggested repair.** Say the submission is two reconcile calls, Stage then Status, each with `payload={"field": …}`. Name that in U2's fenced invocations and in U5's announce loop. Change U4's assertion to two captured argv records whose `(field, option)` pairs match R1. Keep the injected runner. Do not edit `board_progression.py` or `reconcile_controller.py` unless a later finding requires it — two calls already fit the current API. Extend the existing all-or-none comment at `:2067-2069` so a half-done pair is not left on the board.

### N2 — U5's file list names one test; the retype breaks the override and announce fixtures

**Priority:** P2

**Where:** U5 Files (lines 419–423); Risk table last row (line 603); `orchestrate.py:420-425`; `test_orchestrate_board_writeback.py:230-240, 309, 362`.

**What is wrong.** The file list cites `test_the_defaults_never_leave_the_ladder` only. `Run.status_map` is still `dict[str, str]`. `TestStatusMapping` overrides with `"Ready"` and `"Done"`. `TestALandedUnitAnnounces` asserts one `status_writes` entry. After the retype those tests fail before the new vocabulary test can speak.

**Why it matters.** A worker who follows the file list will change the map and leave the fixtures asserting the old string shape. The risk table already knows the override contract is the regression and then does not put those tests on the file list.

**Suggested repair.** Give U5 custody of `Run.status_map`, `mapped_status`'s return type, `announce_comment_body`, the discriminator at `:2071`, and the whole `TestStatusMapping` / announce `status_writes` cluster. State the new override shape: a pair, validated against `stage_statuses`, not a leftover string.

### N3 — U5 does not name `work` / `fix` / `landed`, and `landed → Retro` would skip Verify

**Priority:** P2

**Where:** R1 table (lines 126–132); U5 item 3 (lines 448–449); issue #919 board table; W-D2.

**What is wrong.** R1 has five Plan/Work skill boundaries. After U3 the Orchestrate map still has `plan`, `docreview`, `work`, `fix`, and `landed`. U5 says fill every remaining rung from R1's table. That table has no `fix` row and two different Work §4.4 rows. `landed → Retro / Ready to close` is one available reading. The parent writes that pair only when the child is closed and the gate is green. Orchestrate `landed` is a unit-landed announce, which is the post-merge side of W-D2, not close-out.

**Why it matters.** Mapping `landed` to Retro moves Stage past Verify. That skips the merge-plus-deploy-or-artifact rule this child is also implementing. `fix` is equally unspecified.

**Suggested repair.** Write the five remaining keys down. A grounded reading: `plan` = Planning/Designing, `docreview` = Planning/Ready for Active, `work` and `fix` = Active/Implementing, `landed` = Verify/Awaiting verification. Leave Retro / Ready to close on Work's delivered-terminal skill boundary and on the coordinator, not on `landed`.

## Residual risk from limited evidence

The live Operations board was not re-queried in this session. Vocabulary checks used the worktree schema, which still has 6 Stages, 26 Statuses, and no bare `Ready`. The plan claims a 2026-08-31 board re-query that agreed. If GitHub's option names have drifted since that query, U5's fill-in step needs a fresh read before any write lands.

`_stage_flow()` as named in KTD4 is `_stage_flow_rules()` in `sdlc_manager.py:376`. Re-pin at preflight. Not a readiness finding.

This review did not read the uncommitted evidence package in `infiquetra-agent-operations`. Live #919 and #927, fetched this session, were treated as authoritative.
