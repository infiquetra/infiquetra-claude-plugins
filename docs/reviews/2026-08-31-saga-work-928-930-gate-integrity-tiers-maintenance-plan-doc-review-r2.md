# Document review — WK2–WK4 gate-integrity plan, round 2 (issues #928, #929, #930)

All eleven round-1 findings are repaired. The plan is ready to drive `cp919-worker-2`. One new P2 remains and does not block.

| field | value |
| --- | --- |
| target path | `docs/plans/2026-08-30-saga-work-928-930-gate-integrity-tiers-maintenance-plan.md` |
| reviewed revision | working tree on `work/cp919-saga-work-improvement` at base `1c1c04a9`; plan is uncommitted (793 lines) |
| prior review | `docs/reviews/2026-08-30-saga-work-928-930-gate-integrity-tiers-maintenance-plan-doc-review.md` |
| blocked status | **no** — zero P0/P1 findings remain |
| applied fixes | none. The review brief forbids editing the plan. |
| review artifact path | `docs/reviews/2026-08-31-saga-work-928-930-gate-integrity-tiers-maintenance-plan-doc-review-r2.md` |
| linked issues | [infiquetra/infiquetra-claude-plugins#928](https://github.com/infiquetra/infiquetra-claude-plugins/issues/928), [#929](https://github.com/infiquetra/infiquetra-claude-plugins/issues/929), [#930](https://github.com/infiquetra/infiquetra-claude-plugins/issues/930) |
| linked parent | [infiquetra/infiquetra-claude-plugins#919](https://github.com/infiquetra/infiquetra-claude-plugins/issues/919) |
| pass | round 2 of the WK2–WK4 plan |
| override rationale | n/a |

## Applied fixes

None. Safe in-place edits were disabled by the review brief.

## Readiness summary

Both P1s are gone. The mutation protocol is commit-first, pinned to a named tag, restored with `--source="$BASE"`, and checked with `git diff --exit-code "$BASE"`. U2 now names `resolve_build_unit_tier` in `lifecycle_state.py` as a delegating seam with an ignored `host_tier`; it does not describe a host-session experiment pytest cannot run, and it does not rebuild the #369/#373 chain.

OQ1 and OQ4 stay open with their stated defaults. That is not a defect. OQ3 now has a close condition. The worker can execute this plan without inventing a restore path or a spawn function.

## D1–D11 dispositions

| id | round-1 priority | disposition | note |
| --- | --- | --- | --- |
| D1 | P1 | **repaired** | Commit-first only. See the D1 verdict below. |
| D2 | P1 | **repaired** | Named seam in `lifecycle_state.py`. Two-part proof. Mutation is `return host_tier`. Not a new resolver. |
| D3 | P2 | **repaired** | OQ3 close condition: name-and-repair all six, or file a residue list and leave the child open. §1.5 is off limits during the stub hunt. |
| D4 | P2 | **repaired** | R10 is a negative: do not touch `execution_spec.py` or `plan/SKILL.md`. No Work-side premium check. |
| D5 | P2 | **repaired** | Pin the writeup field and the skill's single-source wording. No second derivation. |
| D6 | P2 | **repaired** | `resume/SKILL.md` is on the U3 file list for `:185`, `:186`, `:199`. `:190` is left alone. R14 is bounded to `plugins/saga/`. |
| D7 | P2 | **repaired** | Expected set is `TRANSITIONS[TRANSITIONS.index("request_review") + 1 :]`. Index form preferred over `[-5:]`. |
| D8 | P2 | **repaired** | First-time-move is protocol mutation 5 and uses the same commit-first restore. |
| D9 | P2 | **repaired** | Catch parser `ValueError`, re-raise `SagaSaveError` with the text unchanged. Tests assert exit 2 and `error: `. |
| D10 | P3 | **repaired** | `performance` withdrawn from U2. |
| D11 | P3 | **repaired** | Preflight follows the amended #919/#930 `artifact_pointer.py` rows. |

Nothing from the round-1 list is unrepaired. Nothing was only partially repaired.

## D1 verdict — commit-first only

The single path is sound for this executor. A named-stash alternative would have been a second restore shape, and a Build Auto reader is where two shapes go wrong. Declining it was the right call.

The hazard is stated in the plan, not implied. `git restore` / `git checkout --` with no `--source` targets `HEAD`, which on an uncommitted unit is the pre-unit base, and the following `git diff` is clean for the wrong reason. That is the original defect.

The written sequence does the four things the brief asked for:

| check | holds |
| --- | --- |
| Cannot destroy uncommitted unit work | Yes. Step 0 commits the implementation before any mutation. |
| Restore targets the implementation ref, not pre-unit HEAD | Yes. `git restore --source="$BASE" --worktree -- <paths>` with `BASE=cp919-<unit>-premutation`. |
| Verifying diff is against that same ref | Yes. `git diff --exit-code "$BASE" -- <paths>`, then empty `git status --porcelain`. |
| Exact commands, not implied | Yes. Steps 0–4 are a copyable bash block. Bare `git restore` or bare `git diff` is named as the defect. |

Two mutations on one unit share one pin. Restore returns the worktree to that pin each time. The tag is deleted only after every row for the unit is proven. The `return host_tier` mutation and the two U3 prose mutations all fit this sequence.

The leftover is `git add -A` in Step 0 (N1). That does not re-open the data-loss hole.

## D2 verdict — named seam, not a new resolver

The plan now says the thing the tree actually is: there is no `Agent(`, `Task(`, `model:`, or `subagent_type` in `work/SKILL.md`, and no Python Work spawn. Phase 2 is prose at `:644-648`. A pytest cannot set a host session model.

The seam is `resolve_build_unit_tier(*, plan_tier, work_shape, host_tier=None)` in `plugins/saga/scripts/lifecycle_state.py`, beside `requires_hard_test_gate` at `:111` and `recommend_execution_backend` at `:183`. Both pins are live. It is on the U2 file list.

It is not a new resolver. KTD11 and the U2 Approach require it to call `tier_defaults` / `tier_resolver` and to compute no `{model, effort}` pair of its own. `host_tier` is accepted and never read, so the test can hand in `fable` / `xhigh` and still see the plan or policy result. The mutation that must go red is `return host_tier` — that is inheritance, written as a one-line swap.

Part (b) is a skill-text pin in the same style as `tests/test_work_review_contract.py`. Naming `recommend_execution_backend()` in the Work skill is already the house pattern (`work/SKILL.md:321`). The issue's "dispatch at that tier" AC is as close as a prose spawn site can get without rebuilding the #369/#373 machinery.

## Specific repair claims

**D6.** Live tree: bare `artifact_pointer.py` at `work/SKILL.md:730` and at `resume/SKILL.md:185`, `:186`, `:199`. `:190` is already the full team-execution path. U3 Files name those three resume lines and say do not touch `:190`. R14 and the U3 negative grep are scoped to `plugins/saga/`, matching amended #930. `CLAUDE.md` and `canary_registry.json` are out of scope.

**D9.** `main()` at `saga.py:1683-1690` still catches `SagaSaveError` and `SagaTickIndexWriteError` only. R1 and the U1 Approach now require the wrap. The refusal tests require exit 2 and an `error: ` prefix, so a traceback at exit 1 cannot pass.

**D7.** `TRANSITIONS` is eight items. `TRANSITIONS[TRANSITIONS.index("request_review") + 1 :]` is `merge`, `checkout_main`, `pull`, `branch_delete`, `teardown`. Preferring the index form over `[-5:]` is correct: an append after `teardown` would drop `merge` from a negative slice.

## Residual-risk additions

**cc-workflows seam.** Real. §1.5 starts at `work/SKILL.md:317` and runs to the Phase 2 heading at `:629`. It is full of bash blocks. U3 Files now mark that range off limits and say to record and stop if the unlocated command stub appears to live there.

**`P0`/`P1` pin.** Real, and correctly bounded. `tests/test_work_review_contract.py:102-106` searches the **entire** `work/SKILL.md` (`_read_skill()`), case-insensitively, for `\bP0\b`, `\bP1\b`, `Priority 0`, `Priority 1`, and `P-level`. It does not forbid `P2` or `P3`. All three units edit that file. Carrying this review's "P1" language into skill text would fail the existing pin. The plan's mitigation — describe findings by name, never by priority token, in that file — matches the test.

## New findings the repair introduced

| id | priority | status | claim |
| --- | --- | --- | --- |
| N1 | P2 | open | Step 0's `git add -A` stages the whole worktree, not the unit's file list |

OQ1 and OQ4 remaining open is not a finding.

## Issue-phase rubric review

Classification unchanged: issue-derived plan, all three cores and all three extras. No rubric finding is reclassified as a readiness finding.

| rubric | score | note |
| --- | --- | --- |
| `acceptance_criteria_clarity` | 8/10 | Named seams, exit-2 assertions, and the five protocol mutations are reviewer-testable. |
| `devils_advocate_issue` | 8/10 | No hidden refactor. The wrapper is the smallest callable that makes R8 testable. |
| `spec_fidelity` | 8/10 | Descent is #928/#929/#930 plus W-D3/W-D5/W-D6/W-D7. The seam delegates rather than rebuilding. |
| `context_completeness` | 9/10 | Pins, resume lines, the §1.5 bound, and the protocol commands are exact. |
| `issue_sizing` | 8/10 | Three serialized units, no false parallel worktree. |
| `prerequisite_mapping` | 8/10 | WK1 → U1 → U2 → U3 is unchanged and still right. |

## Decisions taken without asking

1. Do not edit the plan.
2. Do not answer OQ1 or OQ4. Do not treat their remaining open as a defect.
3. Treat commit-first-only as a deliberate ruling, not an omission.
4. Do not write the board, commit, or push.
5. No external-reviewer panel.
6. Report-only second-opinion: N1 assigned; no `external_opinion` recommended.
7. Write a new round-2 artifact. Leave the round-1 file as the historical record.

---

### N1 — Step 0's `git add -A` stages the whole worktree

**Priority:** P2

**Where:** Mutation-proof protocol Step 0 (lines 628–631).

**What is wrong.** The pin is the right idea. The add is not scoped. `git add -A` stages every dirty and untracked path in `orch-claude-plugins-919`, which today includes both plans and every review artifact in `docs/reviews/`. A literal Build Auto worker will fold those into the U1 ship commit.

**Why it matters.** It does not restore the data-loss hole. It does make the first implementation commit carry files this unit does not own, and it can hide an unrelated dirty path inside the pin that later `git restore -- <paths>` will not touch.

**Suggested repair.** Replace `git add -A` with `git add -- <paths>` using the unit's file list. Keep the commit, the tag, `--source="$BASE"`, and the `$BASE` diff. Do not add a stash path.

## Residual risk from limited evidence

`lifecycle_state.py` already has a CLI (`recommend-backend`, `normalize`, `recheck-capability`). The plan adds a function and has the Phase 2 prose name it, which matches how `recommend_execution_backend()` is already named in the skill. It does not add a CLI verb. That is consistent, not a gap.

This review did not re-fetch #928/#929/#930; the repaired plan's quoted grep and files rows were checked against the live tree and against the amended texts used in the previous pass. The design record in `infiquetra-agent-operations` was not re-read.

Line numbers are from `1c1c04a9` and will move after #927 merges. The plan already requires U3 to re-resolve.
