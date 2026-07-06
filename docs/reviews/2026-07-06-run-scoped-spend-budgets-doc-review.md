---
title: Doc-review — run-scoped spend budgets plan (#366)
target: docs/plans/2026-07-06-run-scoped-spend-budgets-plan.md
reviewed_revision: working tree
issue: infiquetra/infiquetra-claude-plugins#366
blocked: false
date: 2026-07-06
---

# Doc-review — run-scoped spend budgets plan (#366)

**Verdict: ready to drive implementation.** Four findings surfaced (one P1, one P2, two P3); all four
were fixed in place. No findings remain. The plan is well-grounded — every cited `path:line` anchor
verified against the working tree.

## Applied fixes

All four findings were evidence-backed safe fixes to the plan and were applied in place (per the
"fix ALL findings" mandate, not just P0/P1).

| # | Priority | Finding | Fix |
|---|---|---|---|
| 1 | P1 | `cost_budget` summation counted one weight per unit, ignoring call multiplicity — a fan-out unit runs its op `len(targets)` times (`execution_spec.py:1061,1518`) and a verify panel adds `n` calls. The naive sum undercounts exactly the expensive fan-out/panel plans and false-negatives the correctness-critical HALT (a HALT-not-degrade violation). | Added **KTD8** pinning multiplicity-aware summation (`to_spend(tier) × max(len(targets),1) + pilot + verify.n × iterations`); refined R3; added U2 test `test_over_budget_counts_fanout_and_verify_multiplicity` + a `spec_spend()` helper. |
| 2 | P2 | Escrow (U4/U5) wiring named seams ("record actuals at the completion seam") but no concrete call mechanism — risking a tested-but-unwired ledger (dead-wiring). | Gave `effort_ledger.py` a **CLI surface** (`allocate`/`record`/`report`) symmetric with the `spend` verb; U5 now names concrete CLI calls at each `/work` seam instead of intent. |
| 3 | P3 | Weight-ordering guarantee was ambiguous: the monotonicity guard is per-axis, but cross-axis magnitude (`opus/low` vs `sonnet/xhigh`) is authored judgment the guard cannot check. | U1 scope now states per-axis monotonicity is guarded, cross-axis is authored (only the `fable/xhigh > haiku/low` corner is an invariant), so `/work` does not expect the guard to police cross-axis. |
| 4 | P3 | Load timing of `cost_weights.json` was unstated (import-time vs lazy), which changes the blast radius of a malformed table. | U1 scope now states the table loads at import time (like `tier_palette`/`models.json`), failing fast and loud. |

## Readiness summary

The plan can safely drive implementation without `/work` inventing missing decisions. The load-bearing
choices — cost_weights in `fleet_commons` (drift-guarded), budget fields on `ExecutionSpec` not
`OutcomeSpec`, the `cost_budget` HALT mirroring `VERIFY_N_CAP`, and the full-DoD escrow ledger — are all
resolved with rationale and grounded in verified `path:line` anchors. The P1 was the highest-value
catch: the emit-time HALT is the facet the issue itself flags as opus-level correctness-critical, and a
multiplicity-blind sum would have defeated it precisely on the expensive plans it exists to stop.

## Remaining findings

None. All four findings fixed in place.

## Residual risk

The effort-escrow ledger remains the thinnest-specified facet (the issue was terse there); its data
model (run-level pool, per-unit allocation arithmetic) is now pinned to a CLI surface and unit tests,
but the exact `effort-policy.yaml` schema is left to U4 implementation. U2's adversarial gate at merge
is the backstop for the P1 multiplicity arithmetic — the one place a subtle summation bug could still
slip a green suite.

## Links

- Plan: `docs/plans/2026-07-06-run-scoped-spend-budgets-plan.md`
- Issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/366
- Decision: `docs/engineering-journal/DECISIONS.md` `{#run-scoped-spend-budgets-366}`
- Saga: `issue-366` (plan tick `20260706-171454.md`)
