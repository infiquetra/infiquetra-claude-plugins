# Document review — WK1 board-submission path plan, round 3 (issue #927)

N1, N2, and N3 are repaired against the round-2 asks. The plan is still not ready to drive `cp919-worker-1`, because the one-invocation pair has no owned path through the writer that U4 and the new #927 acceptance criterion both name.

| field | value |
| --- | --- |
| target path | `docs/plans/2026-08-30-cp919-wk1-board-submission-path-plan.md` |
| reviewed revision | working tree on `work/cp919-saga-work-improvement` at base `1c1c04a9`; plan is uncommitted (931 lines, `deepened: 2026-08-30`, round-3 repair record present) |
| prior reviews | r1 `docs/reviews/2026-08-30-cp919-wk1-board-submission-path-plan-doc-review.md`; r2 `docs/reviews/2026-08-31-cp919-wk1-board-submission-path-plan-doc-review-r2.md` |
| blocked status | **yes** — one new P1 remains. `/work` blocks until it is repaired or explicitly overridden. |
| applied fixes | none. The review brief forbids editing the plan. |
| review artifact path | `docs/reviews/2026-08-31-cp919-wk1-board-submission-path-plan-doc-review-r3.md` |
| linked issue | [infiquetra/infiquetra-claude-plugins#927](https://github.com/infiquetra/infiquetra-claude-plugins/issues/927) |
| linked parent | [infiquetra/infiquetra-claude-plugins#919](https://github.com/infiquetra/infiquetra-claude-plugins/issues/919) |
| pass | round 3 of the WK1 plan |
| override rationale | n/a |

## Applied fixes

None. Safe in-place edits were disabled by the review brief.

## Readiness summary

The three round-2 findings are repaired in the document. N2's blast radius is now named. N3's six Orchestrate rungs are explicit, live on both the schema and the Operations board, stage-monotonic 2 / 2 / 3 / 3 / 3 / 4, and `landed` is `Verify` rather than `Retro`. Remapping `codereview` to `Active` / `Code review` is the right sub-decision.

N1's requested prose is present: U4 asserts both `(field, option)` assignments and the half-applied case fails; Decision A documents that `flow_set_fields_bulk` does not roll back; U5 must read both identity records. The leftover hole is the call stack those assertions sit on. One `flow set-field` invocation can carry both assignments. `default_board_writer` and `reconcile_controller` still cannot. No unit lists those files. Issue #927's new half-applied criterion names the writer and a per-field runner outcome that a single argv cannot produce.

## N1–N3 dispositions

| id | round-2 priority | disposition | note |
| --- | --- | --- | --- |
| N1 | P1 | **repaired** | Pair shape, non-atomicity, U4 both-fields assertion, U4 half-applied-fails, and U5 read-back are all in the plan. Remaining implementability is N4, not an unrepaired N1. |
| N2 | P2 | **repaired** | U5 names `Run.status_map` at `:420` and its docstring, both override tests (`"Ready"` at `:230-233`, `"Done"` / `"Verify"` at `:235-237`), four `status_writes` sites (`:309-310`, `:362`, `:410`, `:429`), and the `FakeReconcileController` capture at `:94` / `:116`. The new override shape is a `stage_statuses`-validated pair. |
| N3 | P2 | **repaired** | All six keys are named. See the rung table below. |

Nothing from the round-2 list is unrepaired. Nothing was only partially repaired.

## New findings the repair introduced

| id | priority | status | claim |
| --- | --- | --- | --- |
| N4 | P1 | open | The one-invocation pair has no owned path through `default_board_writer`, and the #927 half-applied runner criterion cannot observe per-assignment success and failure on a single argv |

## N1 — what the repair actually did

The section "How a pair is actually submitted" is the load-bearing addition. Three claims in it were re-checked against the tree at `1c1c04a9`:

| claim | holds |
| --- | --- |
| `--field` / `--option` are `action="append"` | yes, `sdlc_manager.py:7045-7056` |
| equal-length check, then `flow_set_fields_bulk` when `len(args.field) > 1` | yes, `:7292-7305` |
| one assignment per `_set_lifecycle_field_cross_board`; `RuntimeError` appends `failed` and does not roll back; only `LifecycleMutationHaltError` propagates | yes, `:3298-3323` |
| a non-empty `failed` list still prints, then raises | yes, `:3405-3409` — so one process that half-applies exits non-zero |
| `_reconcile_call` takes one `target_state`; `default_board_writer` emits one `--field` / `--option` | yes, `orchestrate.py:1949-1958`; `board_progression.py:442-461` |
| `reconcile_controller` still reads one `payload["field"]` and defaults to `Status` | yes, `:232-233` |

U2 now requires both `--field` / `--option` assignments in every fenced block. U4 asserts both `(field, option)` pairs in the captured argv and asserts the half-applied case fails. U5 item 5 requires reading both identity records before converging. The risk table names the same hole. Against the round-2 ask, that is a repair.

Choosing one invocation over two reconcile calls is sound **at the Mission Control boundary**. Two calls would double discovery and widen the half-applied window. The defect is that the plan then declines to touch `board_progression.py` (revision record, line 906) while U5's file table widens only `_reconcile_call`. That is N4.

## N2 — blast radius

Verified in `orchestrate.py` and `tests/test_orchestrate_board_writeback.py` at `1c1c04a9`. Every site the round-2 finding named is now on U5's two tables, plus the extras the planner found (`announce_comment_body` `:1932`, discriminator `:2071`, four `status_writes` assertions rather than two). The override contract is stated as a pair validated against resolved `stage_statuses`. No new hole here.

## N3 — the six rungs

Re-read from the plan, then checked against live issue #919's board transition contract, `workflows.stage_flow` in the worktree schema, and a read-only `flow field-options` against Operations just now.

| Orchestrate key | Plan pair | #919 contract row | Stage index | Live on schema | Live on Operations |
| --- | --- | --- | --- | --- | --- |
| `plan` | `Planning` / `Designing` | "A plan document exists" | 2 | yes | yes |
| `docreview` | `Planning` / `Ready for Active` | no parent row; schema `entry_option_rule` terminal exception | 2 | yes | yes |
| `work` | `Active` / `Implementing` | "Dispatched, with a session or worktree" | 3 | yes | yes |
| `fix` | `Active` / `Implementing` | same Active row; repair is still pre-merge | 3 | yes | yes |
| `codereview` | `Active` / `Code review` | "Pull request open carrying a typed Saga Code Review outcome" | 3 | yes | yes |
| `landed` | `Verify` / `Awaiting verification` | "Merged and either deployed or artifact-verified (W-D2)" | 4 | yes | yes |

Stage order on the live board and in the schema is Intake, Shaping, Planning, Active, Verify, Retro. Indices 2, 2, 3, 3, 3, 4 are monotonic. No rung moves a card backwards.

**`landed` is `Verify`, not `Retro`.** `Retro` / `Ready to close` is the parent's close-out row (child closed, gate green). Mapping `landed` there would skip Verify and violate W-D2, which this child is also enforcing. That pair stays on Work's delivered-terminal skill boundary (R1 row 5) and on the coordinator. Correct.

**Remap `codereview`, do not delete the key.** The argument holds. W-D2 and #927 require that `codereview` no longer map to `Verify`. They do not require the key to vanish. Deleting it would make `mapped_status("codereview-…")` return `None` and skip the announce (`orchestrate.py:2031-2033`), which is a behaviour regression against R6 and against today's announce at that prefix. `Active` / `Code review` is the parent table's own row and keeps pre-merge work in Active. Rejecting `fix` → `Active` / `Repairing` is also right: that split is phase semantics, and `Repairing` is live (schema and board) but out of mandate.

U3 still says "remove the entry" and the sequencing sentence still says U3 removes a key. That is an intermediate step, not the final map: U3 writes no option string, U5 puts `codereview` back with the live pair. Serialized U3 → U5, the mutation proof "restore `codereview`: `Verify`" still works. Not a new finding.

Live Operations re-query this session: Stage has 6 options (Intake / Shaping / Planning / Active / Verify / Retro); Status has 26 options; bare `Ready` is on neither. Agrees with the schema at `222fcdd3` and with the plan's 2026-08-31 claim.

## Issue changes since round 2

Both live issues were re-fetched this session.

**#927 half-applied acceptance criterion.** Present. It names `tests/test_saga_board_first_move.py -k half_applied`, `board_progression.default_board_writer`, an injected `runner` that succeeds on `--field Stage` and fails on `--field Status`, and a failure record rather than `written` or `skipped`. U4 names the same file and the same assertion. The plan's verification block does not quote the `-k half_applied` node; the issue does. That is only a problem because the runner contract and the one-invocation shape cannot both be true — see N4.

**Negative B false green.** Fixed in live #919, live #927, and the plan (line 793). All three now use the literal arrow, not a backslash-u escape. Re-run at `1c1c04a9`:

| check | result |
| --- | --- |
| Literal `Status *(->|→) *(Idea\|Ready\|Active\|Verify\|Done)` | four hits: `plan/SKILL.md:312`, `work/SKILL.md:253`, `:780`, `:787` |
| Escaped `\\u2192` form | zero hits — the false green the operator reported |
| Positive resolution check | names all six dead rungs |
| Negative A | `STATUS_LADDER` and `"landed": "Done"` |

The plan's claimed RED output still matches.

## Issue-phase rubric review

Classification unchanged: issue-derived plan, all three cores and all three extras. Rubric findings are not reclassified as readiness findings. N4 independently meets the acceptance-criteria REVISE criterion (the new half-applied AC and Decision A's one-invocation writer are not the same test).

| rubric | score | note |
| --- | --- | --- |
| `acceptance_criteria_clarity` | 7/10 | Live pairs, the three RED checks, and the new half-applied AC are reviewer-testable. The AC's per-field runner and the plan's one argv describe two different machines. |
| `devils_advocate_issue` | 8/10 | Remap-vs-delete is justified. The writer-custody gap is the remaining structural smell. |
| `spec_fidelity` | 8/10 | Descent is live #919 / #927. Rung table now matches the parent contract. The new AC is in the issue and only half-mirrored in U4. |
| `context_completeness` | 8/10 | Type-layer and rung-layer pins are exact. The writer / controller / identity-record transport is still implied. |
| `issue_sizing` | 8/10 | Seven units plus a justified U5 remains large and coherent. Decision B is unchanged. |
| `prerequisite_mapping` | 9/10 | `U1 → U2 → U3 → U5 → U4 → U7` with U6 concurrent is still the right graph. |

## Triggered lenses

Security/ops scrutiny still applies: every unit except U6 and U7 submits or guards GitHub project-field writes. This pass issued two read-only `flow field-options` queries against Operations (Stage, Status) and no writes. Founder-review not triggered. Deployment readiness not triggered.

## Decisions taken without asking

1. Do not edit the plan.
2. Do not re-open D1–D10 or N1–N3 as questions. Judge the recorded repairs.
3. Do not write the board, commit, or push. Field-options reads are not writes.
4. No external-reviewer panel.
5. Report-only second-opinion: N4 assigned; no `external_opinion` recommended.
6. Write a new round-3 artifact. Leave the round-1 and round-2 files as the historical record.

---

### N4 — The one-invocation pair has no owned path through the writer, and the half-applied runner test cannot see per-assignment outcomes

**Priority:** P1

**Where:** Decision A "How a pair is actually submitted" (lines 95–132); U5 Files (lines 478–504) and item 5 (lines 573–580); U4 half-applied assertion (lines 443–446); revision record (lines 905–910); live #927 half-applied acceptance criterion; `board_progression.py:432-511`; `reconcile_controller.py:231-261`; `orchestrate.py:1949-1994`.

**What is wrong.** Mission Control already accepts both assignments in one `flow set-field` process. The Saga writer does not emit them. `default_board_writer` builds one `--field` / `--option` pair from `payload.get("field")` and `payload.get("target_state")`, then calls the runner once and treats any non-zero as total failure. It never parses stdout, so it never sees MC's two identity records. `reconcile_controller` still lifts one `field` from the payload and defaults to `Status`. `_reconcile_call` still takes one `target_state` and returns one controller record.

U5's file table lists `_reconcile_call` as the widen site and does not list `plugins/saga/scripts/board_progression.py` or `plugins/saga/scripts/reconcile_controller.py`. The revision record celebrates not touching `board_progression.py`. Widening `_reconcile_call` cannot make a one-field writer emit two flags.

The new #927 criterion and U4's "runner returning success for one assignment and failure for the other" assume per-assignment runner outcomes. One argv with both `--field Stage` and `--field Status` is one `subprocess.run` and one returncode. A runner cannot succeed on Stage and fail on Status inside that single call. If the worker instead loops two runner calls, they have reintroduced the two-invocation path Decision A rejected. If they keep one call, the #927 `-k half_applied` check is unimplementable as written, and U5's "read both identity records" has no transport: `_reconcile_call` parses the controller JSON, not MC's `identity` / `failed` arrays.

A Status-only payload still compiles, still authorizes, and still looks like a completed write. That is the same false-green family N1 named, now sitting one layer below the prose repair.

**Why it matters.** Issue #927 now requires a pytest that a worker following U5's file list cannot write without inventing a `board_progression.py` change the plan told them not to make. `/work` would either skip the AC or widen a file with no custody.

**Suggested repair.** Give U5 (or a named sibling) custody of `default_board_writer` and the controller payload so one invocation can carry two assignments **and** surface both MC records to the caller. Rewrite the half-applied proof to match that seam: one runner call, stdout containing one `updated` identity and one `failed` row (or a non-zero exit after `_out`), and the caller treating that as a failed move. Do not keep the per-field "succeeds on Stage, fails on Status" runner language unless the writer is specified to call the runner once per assignment — which is the path Decision A already rejected.

## Residual risk from limited evidence

Live Operations Stage and Status options were re-queried this session and agree with the schema. Option *ids* were not used for any write. Identity-record JSON shape was read from `flow_set_fields_bulk` in the worktree, not from a fresh live pair-write.

This review did not read the uncommitted evidence package in `infiquetra-agent-operations`. Live #919 and #927, fetched this session, were treated as authoritative.

Plan untouched. No commit, push, or board write.
