# Document review — WK1 board-submission path plan, round 4 (issue #927)

N4 is repaired. The plan is ready to drive `cp919-worker-1`. One new P2 remains; it does not block.

| field | value |
| --- | --- |
| target path | `docs/plans/2026-08-30-cp919-wk1-board-submission-path-plan.md` |
| reviewed revision | working tree on `work/cp919-saga-work-improvement` at base `1c1c04a9`; plan is uncommitted (1057 lines) |
| prior reviews | r1 `docs/reviews/2026-08-30-cp919-wk1-board-submission-path-plan-doc-review.md`; r2 `…-r2.md`; r3 `…-r3.md` |
| blocked status | **no** |
| applied fixes | none. The review brief forbids editing the plan. |
| review artifact path | `docs/reviews/2026-08-31-cp919-wk1-board-submission-path-plan-doc-review-r4.md` |
| linked issue | [infiquetra/infiquetra-claude-plugins#927](https://github.com/infiquetra/infiquetra-claude-plugins/issues/927) |
| linked parent | [infiquetra/infiquetra-claude-plugins#919](https://github.com/infiquetra/infiquetra-claude-plugins/issues/919) |
| pass | round 4 of the WK1 plan, N4 confirm |
| override rationale | n/a |

## Applied fixes

None. Safe in-place edits were disabled by the review brief.

## Readiness summary

Round 3's N4 had two faces: no owned path through the writer, and a half-applied criterion that assumed per-assignment runner outcomes. Both are closed. U5 now owns `board_progression.py` and `reconcile_controller.py`. Live #927's Files list grew by exactly those two paths. The half-applied proof is one `CompletedProcess` with `returncode=1` and the split on stdout. The stale "do not touch `board_progression.py`" sentence is marked superseded. The four rejected alternatives are recorded.

The detection claim is true in the code. `flow_set_fields_bulk` prints, then raises. The writer already fails loud on a non-zero exit. The missing piece on the failure path is that the error currently quotes `stderr` and drops stdout. The plan implements exactly that: emit N assignments, parse stdout on failure, do not invent a second success detector.

## N4

**Repaired.**

| r3 claim | now |
| --- | --- |
| U5 file table omitted `board_progression.py` and `reconcile_controller.py` | both are U5 files, with site and minimal scope |
| revision record celebrated not touching `board_progression.py` | blockquoted **Superseded in round 4** at the old N1 paragraph; the one-invocation decision itself stands |
| #927 Files list omitted the writer and the controller | live issue now lists exactly those two added paths |
| #927 AC assumed a runner that succeeds on Stage and fails on Status | replaced: one runner call, one `CompletedProcess`, `returncode=1`, Stage in `updated`, Status in `failed`, error names both halves |
| plan U4 still used the per-field runner language | rewritten to the same one-argv shape; two runner calls are a named rejected alternative |

## Is "parse stdout on failure" sufficient?

Yes, for the half-applied *detection and evidence* half of N4. Re-read at `1c1c04a9`:

| claim | holds |
| --- | --- |
| `_out(result, fmt)` prints `updated` / `failed` / `identity` to stdout | yes. `_out` at `sdlc_manager.py:857-862` is `print(...)` with no `file=`. Default `--format` is `text`, and a dict still goes through `json.dumps`, so the keys are on stdout either way. |
| raise happens only after `_out` | yes, `:3404` then `:3405-3409` |
| `identity` is built from `updated` only | yes, `:3391-3403`. A failed assignment gets no identity record. |
| `main()` turns that raise into exit 1 without eating stdout | yes, `:7353-7355` — `_error(str(e))` to stderr, `sys.exit(1)` |
| writer already fails loud on non-zero | yes, `board_progression.py:508-511` |
| writer currently reports only stderr | yes: `raise RuntimeError(f"... failed: {result.stderr!r}")` |

A half-applied pair is already a failed move at the process boundary. The writer does not need new success logic. It needs to stop discarding the report that is already on stdout, so the surfaced error names which half landed. That is what U5's writer scope and U4's assertion require.

Emit-N-assignments is the other half of N4 (owned path). The plan does not treat parse-stdout as a substitute for that. U5's writer row names both: emit one `--field`/`--option` per assignment, and parse stdout on failure. Absent `assignments` keeps today's single-field behaviour, which is what `tests/test_board_progression.py` already pins.

## Plan and issue agree

Live #927 fetched this session (`updatedAt` 2026-08-31T04:39:41Z).

**Files.** The issue's "Files expected to change" grew by exactly two paths, matching the plan's fenced block:

- `plugins/saga/scripts/board_progression.py` — emit N assignments, parse stdout on failure
- `plugins/saga/scripts/reconcile_controller.py` — authorize every field; key the pair

**Half-applied AC.** The issue now pins one injected runner call returning a single `CompletedProcess` with `returncode=1` and stdout carrying Stage in `updated` and Status in `failed`, asserting the raised error names both halves. U4's "observable proof" paragraph is the same machine. That phrasing forbids looping two runner calls.

## Four rejected alternatives

All four are recorded in U5 and restated in the round-4 revision record, each with a reason:

1. Widen `_reconcile_call` alone — argv is built in `board_progression.py` (N4 itself).
2. Two `default_board_writer` calls — restores two-invocation; splits the ledger so a re-drive can re-land one half.
3. Call `sdlc_manager.py` directly from Orchestrate — violates W-D1; drops certificate, ledger, replay key.
4. New `set-field-pair` op-kind — dead API surface; same reasoning that rejected `set-field-stage`.

## New findings

| id | priority | status | claim |
| --- | --- | --- | --- |
| N5 | P2 | open | U5 pins `default_board_writer` `:440-511` and says payload rides through `authorize_and_write` untouched, but `authorize_and_write` `:216-225` still lifts one `field`, defaults to `Status`, and mints the ledger key |

Not a P1. A Status-only write still cannot satisfy U4 or the #927 AC. A worker who follows the stated line range will emit the pair and parse stdout, and the first-move and half-applied proofs still hold. The leftover is idempotency: the controller is told to key the pair, while `authorize_and_write` will still write `set-field-status:…:Status:…` unless that site is widened too. Re-announce would then miss the pair-key and re-drive a write that already landed. Board-side that write is idempotent; R6's skip is weaker than the plan claims. Name `:216-225` in U5's `board_progression.py` row, or say the controller's pair-key is the only ledger identity and `authorize_and_write` must use it.

## Issue-phase rubric review

Classification unchanged. Rubric findings are not reclassified as readiness findings. N5 does not meet a REVISE/BLOCK criterion on its own.

| rubric | score | note |
| --- | --- | --- |
| `acceptance_criteria_clarity` | 9/10 | The replaced half-applied AC is reviewer-testable against one argv. |
| `devils_advocate_issue` | 8/10 | The three-layer cut is the right smallest slice. `authorize_and_write`'s key is the leftover smell. |
| `spec_fidelity` | 9/10 | Plan and live #927 now name the same files and the same proof. |
| `context_completeness` | 8/10 | Writer and controller pins are exact. The authorize-and-write key site is implied away. |
| `issue_sizing` | 8/10 | Unchanged: seven units, U5 justified. |
| `prerequisite_mapping` | 9/10 | `U1 → U2 → U3 → U5 → U4 → U7` still holds; U5 now owns the writer U4 proves. |

## Triggered lenses

Security/ops scrutiny still applies. No board writes this pass. Founder-review not triggered. Deployment readiness not triggered.

## Decisions taken without asking

1. Do not edit the plan.
2. Do not re-open N1–N3. Judge N4 and anything the repair introduced.
3. Do not write the board, commit, or push.
4. No external-reviewer panel.
5. Report-only: N5 assigned; no `external_opinion` recommended.
6. Write a new round-4 artifact. Leave r1–r3 as the historical record.

Plan untouched. No commit, push, or board write.
