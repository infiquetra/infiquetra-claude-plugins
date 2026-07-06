---
title: Code review — run-scoped spend budgets (#366)
target: feat/366-run-scoped-spend-budgets (main..HEAD)
reviewed_sha: 7d92388b0bf057655bc6c10d29252e91d72ff707
diff_base: 0eec314d9f890a5545f824ddcbf8d0e7335b6866
issue: infiquetra/infiquetra-claude-plugins#366
blocked: false
date: 2026-07-06
---

# Code review — run-scoped spend budgets (#366)

**Verdict: CLEAN — safe to merge. 0 P0/P1/P2 findings.** The correctness-critical emit-time HALT was
verified by adversarial *execution* (a three-verifier refute-panel), not just read. Scope check: CLEAN.

## Scope check

- **Intent:** price the tier lever — cost-weight table, `cost_budget` HALT, `spend_envelope`, effort
  escrow (issue #366, full DoD).
- **Delivered:** exactly that, across 6 U-IDs. The one addition beyond the issue's indicative file list —
  the `execution_spec.py spend` CLI verb — is the planned R6 anti-dead-wiring read-consumer, not creep.
- **Result:** CLEAN. No unrelated files, no "while I was in there" changes, no missing requirements.

## Plan-completion audit (DIFF-verified)

| U-ID | State | Evidence |
|---|---|---|
| U1 cost_weights + to_spend | DONE | `cost_weights.json` + `cost_weights.py`; 7 tests incl. drift guard |
| U2 cost_budget HALT | DONE | `ExecutionSpec.validate`/`spec_spend`/`unit_spend`; 10 tests incl. multiplicity |
| U3 spend_envelope + accumulator + spend CLI | DONE | `SpendEnvelope` + `spend` verb; 8 tests |
| U4 effort_ledger + policy | DONE | `effort_ledger.py` + `effort-policy.yaml`; 10 tests |
| U5 skill wiring | DONE | `plan/SKILL.md` Step 1b, `execution-strategy.md`, `pr-continuation-loop.md` |
| U6 release surface | DONE | saga 0.69.0, marketplace, CHANGELOG, pin, execution-spec.md, DECISIONS |

## Adversarial verification (refute-panel, executed at SHA 7d92388)

Three read-only verifiers (disposable worktrees) each tried to REFUTE a distinct claim by executing
crafted adversarial inputs. **All 15 claims survived; 0 refuted.**

| Panel | Claims probed | Result |
|---|---|---|
| U2 HALT (correctness-critical) | fan-out false-negative, verify + iterate_to_consensus multiplicity, budget boundary (`==` passes, `+1` HALTs), pilot double-count, int/bool/`<1` hardening, mixed-spec hand-recompute | all SAFE |
| cost_weights drift guard | wrong-direction monotonicity (both axes), completeness, off-palette rejection, non-int/bool cells, cross-axis residual | all SAFE (residual honestly documented) |
| escrow + envelope | ask-once crossing (7 sequences), refund conservation, escalation-before-execution, policy safe-default, save/load round-trip | all SAFE |

The verifiers independently recomputed `spec_spend()` by hand for mixed fan-out/verify/pilot specs and
the code matched every time. Both U2 verifiers also correctly identified and ignored an injected
MCP-instruction block as noise (a prompt-injection vector) rather than acting on it.

## Findings

**None.** No P0/P1/P2/P3 findings survived the gate.

## Why clean (not a weak gate)

The multiplicity false-negative that this gate exists to catch was already caught by `/doc-review` at
plan time (the P1 → KTD8), so U2 was built multiplicity-aware from the first commit. Catching it earlier
means the adversarial gate confirms rather than catches — the intended outcome of the front-loaded
readiness pass.

## Residual risk

Cross-axis weight ordering (`opus/low` vs `sonnet/xhigh`) is the authored ordinal judgment, not
machine-checkable beyond the corner invariant — documented as such in `cost_weights.py`. This does not
affect `spec_spend()` correctness (the HALT sums exact per-cell weights). No action needed.

## Links

- Diff: `main..7d92388` (base `0eec314`)
- Plan: `docs/plans/2026-07-06-run-scoped-spend-budgets-plan.md`
- Doc-review: `docs/reviews/2026-07-06-run-scoped-spend-budgets-doc-review.md`
- Work session: `docs/work-sessions/2026-07-06-run-scoped-spend-budgets.md`
- Issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/366
