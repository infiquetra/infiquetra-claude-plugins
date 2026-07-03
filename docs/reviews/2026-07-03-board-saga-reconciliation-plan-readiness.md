# Doc-review: board-saga reconciliation plan — readiness

**Verdict: READY.** All findings were evidence-backed and fixed in place; no P0/P1 remains. The plan can drive `/work 295` without the implementer inventing missing decisions.

| field | value |
|-------|-------|
| target | docs/plans/2026-07-03-board-saga-reconciliation-plan.md |
| reviewed revision | working tree (plan uncommitted at review time) |
| blocked | no |
| review type | readiness-skeptic pass (plan artifact; no idea/issue/spec rubric phase applies) |
| linked issue | infiquetra/infiquetra-claude-plugins#295 |
| origin | docs/brainstorms/2026-06-28-board-saga-reconciliation-requirements.md |
| saga | issue-295 (plan tick 20260703-163310) |

## Method

The plan was authored in-session, so the review adversarially re-verified every claim asserted from memory rather than direct evidence — via live `gh` probes against this repo and code reads. Origin mapping re-checked: issue R1.1–R1.9 → plan R1–R10 complete; AE1–AE4 → U3/U4 scenarios complete; KD1–KD7 carried or explicitly corrected in the plan's verification table.

## Findings

| # | P | status | finding |
|---|---|--------|---------|
| F1 | P1 | fixed | U2 named a nonexistent `gh issue view` JSON field (`closedByActorLogin`; `closedBy` also rejected — probed live). Implementer would have hit an unknown-field error mid-unit and invented a substitute. Fixed with the verified two-call shape: `--json state,stateReason` + REST `issues/<n>/events --paginate` last closed event's `actor.login`. |
| F2 | P1 | fixed | KTD7/U1's premise was false: a new mission-control GraphQL `flow get-field` verb is unnecessary because `gh issue view --json projectItems` returns per-project `{status:{name},title}` in one call (probed live). U1 rewritten as `outcome_github.board_status` (saga-side, degrade-safe, title↔slug match); mission-control dropped from the diff entirely (R9/R10/U5/U6 adjusted; saga-only version bump). Old approach preserved as KTD7's rejected alternative with a revisit condition. |
| F3 | P2 | fixed (moot) | U1 claimed "the `flow set-field` handler and its tests in `tests/test_mission_control.py`" — grep shows zero flow-verb tests exist. Moot after the U1 rewrite; recorded because the pattern claim was unverified. |
| F4 | P2 | fixed | Plan test path (`tests/test_outcome_reconcile.py`, repo `test_outcome_*` convention) silently diverged from issue #295's acceptance-criteria commands (`tests/test_saga_reconcile.py` + `-k` selectors). Fixed: U3 now pins the exact test function names matching the issue's selectors and states the supersession, keeping the acceptance criteria executable modulo path. |
| F5 | P2 | fixed | U5 called lease-free detection "read-only," but U3's recover-record branch writes ledger files. Fixed with the precise claim: read-only on GitHub; local writes go through `outcome_store._write_once` (verified atomic temp + `os.link`), so a concurrent `advance` writing the same key is a benign no-op race. |
| F6 | P3 | fixed | Risks section carried an assumed-risk about gh field support (now verified) and omitted events-API pagination (issues with >30 events would miss the close event without `--paginate`). Both corrected; U3 scenario 11 also extended to cover accepted-external-close override silence. |

## Applied fixes

All six findings fixed in place in the plan (verification table row, R9/R10, KTD7, U1 full rewrite, U2 approach, U3 test-name preamble + scenario 11, U5 approach, U6 files/verification, Risks, Sources probe log). No product decisions were resolved without operator input — F2 corrects a falsified factual premise; the operator-confirmed design decisions (close semantics, trigger, field class) are untouched.

## Residual risk / limited evidence

- Title↔slug matching for `projectItems` was probed against the Operations board only; asgard/campps titles are assumed to match their slugs case-insensitively. Degrade path (no match → unreadable note, never a wrong diff) bounds the damage; U1 scenario 2 covers multi-board selection.
- `gh api --paginate` with a `--jq` filter concatenates per-page results; "last closed event" selection must be applied after pagination, not per page — U3/U2 tests will force this, flagged here so the implementer doesn't trip on it.
- The plan-phase saga tick (20260703-163310) records the pre-revision KTD7 wording; the review tick supersedes it. Saga ticks are append-only local state — no correction needed.

## Note for the saga tick consumer

`/work` may consume this artifact as the same-session doc-review output: not blocked, no unresolved P0/P1.
