---
title: Code review — spend-delta machinery (#367)
target: feat/367-spend-delta-machinery (main..HEAD)
reviewed_sha: 4b16289f79328c38f533a1eb5c47df398ecd0ad1
issue: infiquetra/infiquetra-claude-plugins#367
blocked: false
date: 2026-07-06
---

# Code review — spend-delta machinery (#367)

**Verdict: CLEAN after one P3 fix — safe to merge.** A two-verifier adversarial refute-panel *executed*
the classifier, the `require_receipts` gating, the worth-it hard-block, and the spend-authority resolver.
One finding (P3) was surfaced and fixed; everything else survived. Scope check: CLEAN.

## Scope check

- **Intent:** a shared spend-direction classifier + the relative lever, worth-it receipts, and spend
  authority (#367, full DoD).
- **Delivered:** exactly that, saga-only (no fleet-core change — `cheaper_fallback` reused, not modified).
- **Result:** CLEAN.

## Plan-completion audit (DIFF-verified)

| U-ID | State | Evidence |
|---|---|---|
| U1 spend_delta + is_escalation refactor | DONE | `_axis_deltas`/`spend_delta`; grid guard proves is_escalation unchanged |
| U2 adjacent_tier | DONE | reuses `cheaper_fallback`; boundary raises; asymmetry documented |
| U3 worth-it hard-block | DONE | `require_receipts`-gated; engine-owned exempt; 6 tests |
| U4 spend_authority | DONE | `.saga/spend-authority.json`; 256-pair `is_escalation` equivalence guard |
| U5 skill wiring | DONE | `/plan` §5.2a Step 1c |
| U6 release surface | DONE | saga 0.70.0, marketplace, CHANGELOG, pin, execution-spec.md, DECISIONS |

## Adversarial verification (refute-panel, executed at 64d1462)

Two read-only verifiers (disposable worktrees) executed adversarial cases.

| Panel | Claims | Result |
|---|---|---|
| spend_delta / is_escalation / adjacent_tier | is_escalation grid-preserved (mixed move stays True while spend_delta is lateral); spend_delta 3-way correctness; ordering-not-magnitude (54 mixed pairs stayed lateral despite a to_spend delta); adjacent_tier boundaries + `cheaper_fallback` agreement + never-unrunnable | 3 SAFE, **1 P3 refuted** |
| require_receipts / worth-it / spend_authority | receipts NEVER leak into emit/plain validate; baseline=sonnet/high premium set exact; cheaper_fallback strictly-cheaper enforcement; engine-owned exemption; spend_authority default/matrix/malformed + 256-pair grid | all 5 SAFE |

The single most important non-regression was **CONFIRMED**: `require_receipts` does not leak into `emit()`
or plain `validate()`, so premium specs authored before #367 are not retroactively broken.

## Findings

| # | Priority | Finding | Status |
|---|---|---|---|
| 1 | P3 | `adjacent_tier` "dearer-then-cheaper" does not round-trip for `fable/{low,medium,high}` — both directions prefer the model axis, so at the fable ceiling `dearer` moves effort while `cheaper` undoes via the model axis. Not a contract violation (each op is a valid one-rung move, boundaries raise), but an intended asymmetry that was undocumented, and the test over-claimed a universal inverse. | **Fixed** in `4b16289`: documented the asymmetry on `adjacent_tier`; the test now asserts mid-ladder inverts while the model boundary intentionally does not. |

## Residual risk

None material. The `adjacent_tier` asymmetry is now documented and tested as intended. The
`spend_delta`/`is_escalation`/`spend_authority` predicates are pinned to each other by exhaustive grid
guard tests (16×16 and 256-pair), so they cannot silently drift.

## Links

- Diff: `main..4b16289`
- Plan: `docs/plans/2026-07-06-spend-delta-machinery-plan.md`
- Doc-review: `docs/reviews/2026-07-06-spend-delta-machinery-doc-review.md`
- Work session: `docs/work-sessions/2026-07-06-spend-delta-machinery.md`
- Issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/367
