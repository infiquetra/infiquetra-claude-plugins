---
title: Doc-review — spend-delta machinery plan (#367)
target: docs/plans/2026-07-06-spend-delta-machinery-plan.md
reviewed_revision: working tree
issue: infiquetra/infiquetra-claude-plugins#367
blocked: false
date: 2026-07-06
---

# Doc-review — spend-delta machinery plan (#367)

**Verdict: ready to drive implementation.** Two findings (one P1, one P3); both fixed in place. No
findings remain. Every cited `path:line` anchor verified against the working tree.

## Applied fixes

| # | Priority | Finding | Fix |
|---|---|---|---|
| 1 | P1 | R2/KTD2 claimed `is_escalation` could be redefined as `spend_delta(...) == "escalate"` and stay behavior-preserving. It cannot: `is_escalation` (current, `execution_spec.py:1703`) is True whenever `new` is stronger on *either* axis, so a mixed/sideways move is `is_escalation == True` but `spend_delta == "lateral"`. The redefinition would flip `is_escalation` False on every sideways trade and silently regress #365's `/tier` confirmation gate (a partly-more-expensive change would stop asking). | R2/KTD2/U1 rewritten: `spend_delta` and `is_escalation` **share** an `_axis_deltas` helper (the real DRY win) but `is_escalation` keeps its exact predicate `dm>0 or de>0`; the guard test asserts it is unchanged, and that the two predicates deliberately differ on mixed/identical inputs. |
| 2 | P3 | The new `Unit.cheaper_fallback` field shares a name with `tier_resolver.cheaper_fallback` the function — implementer could conflate the declared value with the computed default. | U3 scope now names the overlap and instructs a code comment distinguishing the field (author-declared Tier) from the function (computes the one-rung-down suggestion). |

## Readiness summary

The plan is well-grounded and correctly leverages the two shipped primitives it builds on
(`is_escalation` #365, `cheaper_fallback` #362) and the #370 named-ops mandate (raw `.index()` is
forbidden — `execution_spec.py:1684,2157`). The P1 was the high-value catch: the plan's own DRY
consolidation, taken literally, would have regressed a live gate on mixed tier moves. The corrected
design shares the axis-delta *computation* without changing `is_escalation`'s *semantics* — DRY without
regression.

The design's most elegant property survives review: a single `sonnet/medium` baseline drives BOTH the
worth-it hard-block and the spend-authority default (both via `is_escalation(baseline, tier)`), so the
two levers cannot disagree about what "expensive" means. And #367 is correctly scoped saga-only — no
fleet-core bump — because `cheaper_fallback` is reused, not modified (the lesson from #366's parity
failure applied preemptively).

## Remaining findings

None.

## Residual risk

`spend_delta`'s `lateral` bucket depends on the per-axis (partial-order) reading of "same-cost
transposition" rather than a literal equal-cost reading — correct, because the cost-weight table is
injective so a magnitude reading could never yield `lateral` (recorded as KTD1). The implementer must not
"simplify" `spend_delta` onto `to_spend`. U1's `test_spend_delta_lateral_transposition` guards this.

## Links

- Plan: `docs/plans/2026-07-06-spend-delta-machinery-plan.md`
- Issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/367
- Decision: `docs/engineering-journal/DECISIONS.md` `{#spend-delta-machinery-367}`
- Saga: `issue-367` (plan tick)
