---
title: Doc-review — runtime ladder climbing plan
target: docs/plans/2026-07-06-runtime-ladder-climbing-plan.md
reviewed_revision: working tree
blocked: false
date: 2026-07-06
linked_issue: infiquetra/infiquetra-claude-plugins#364
---

# Doc-review — runtime ladder climbing (#364)

**Readiness: READY, not blocked.** Three findings, all fixed in place. The load-bearing ones were
two composition gaps between the new escalation retry and *existing* retry-shaped machinery — both
unbounded-spend vectors, the exact failure class the issue forbids.

## Applied fixes

| # | Priority | Finding | Fix |
|---|----------|---------|-----|
| 1 | P1 | U2 was silent on `escalate_on_signal` × `iterate_to_consensus` (`execution_spec.py:471`) — nesting the consensus loop (`max_iterations=3`) inside a climb retry compounds retry loops into unbounded spend. | v1 composition exclusion enforced at `validate` (`SpecError`), test scenario added; lifting it is Follow-Up Work. |
| 2 | P1 | U2 was silent on `escalate_on_signal` × fan-out units (`fanout=True`, `execution_spec.py:669`) — a climb re-runs across ALL targets, silently multiplying higher-tier spend. | Same v1 exclusion at `validate`, test scenario added. |
| 3 | P2 | KTD1's "effort stays runnable on a stronger model" was asserted without palette evidence; U3 cited a stale gate-helper line range. | KTD1 now cites `models.json` (haiku ceiling `high`, others `xhigh`) with the `supports_effort` invariant named; U3 citation corrected to `_JS_GATE_HELPER` at `execution_spec.py:162`. |

## Verification performed

- Line citations spot-checked against working tree: `is_escalation` (1355), `patch_spec_tiers`
  (1373), refute throw (1200-1216), `iterate_to_consensus` (471), `fanout` (669),
  `_JS_GATE_HELPER` (162), `tier_palette.escalate` (158 — single-axis, **no-op at top**, which is
  why KTD2's None-at-top consumer semantics are needed).
- `models.json` effort ceilings confirm KTD1's model-climb-keeps-effort invariant holds in the
  current palette and is guarded by `supports_effort` regardless.
- `tests/test_execution_spec.py` does not exist; the plan's correction to
  `tests/test_saga_execution_spec.py` is right, and every planned test name contains its issue-AC
  `-k` selector verbatim (checked all 7 selectors).
- No price-per-tier data exists (`models.json` = rank/rung/ceiling only) — KTD6's ordinal-delta
  deferral to #367 matches the identical deferral already recorded at `commands/tier.md:41-42`.
- Attendance precedent verified: no attended/unattended concept exists in `execution_spec.py` /
  `team_emitter.py`; `outcome.py --autonomous` (1129-1133) is the only precedent, matching KTD3's
  emit-time-flag choice.

## Residual risk

Moderate — the emit-template surgery (`_emit_panel_reconciliation`, the gate helper) is
string-templated JS, the repo's fiddliest surface; the plan mitigates with emitted-JS assertion
tests (the established `_emit_units` pattern) and the operator's standing instruction to escalate
to an adversarial-verify workflow if `/code-review` surfaces P0/P1 in the escalation logic.
