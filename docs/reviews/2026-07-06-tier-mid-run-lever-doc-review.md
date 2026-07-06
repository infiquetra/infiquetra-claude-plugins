---
title: Doc-review — /tier mid-run lever plan
target: docs/plans/2026-07-06-tier-mid-run-lever-plan.md
reviewed_revision: working tree
blocked: false
date: 2026-07-06
linked_issue: infiquetra/infiquetra-claude-plugins#365
---

# Doc-review — /tier mid-run lever

**Readiness: READY, not blocked.** Four findings, all safe/evidence-backed and fixed in place (per
operator instruction to fix every finding). The most important was a shared-contract risk that also
removed redundant work.

## Applied fixes

| # | Priority | Finding | Fix |
|---|----------|---------|-----|
| 1 | P1 | KTD2/U2 extended `tier_resolver.resolve()`'s `envelope_ceiling` (shared `fleet_commons`, additive-only 0.x contract, **no live caller** — verified) to the effort axis — redundant with the emit-time clamp and a contract risk. | Dropped the resolver extension; **emit is the sole enforcement point** (both emitters clamp the final tier, covering both axes after the resolve cascade). Inline is advisory. KTD3 reference to the extension also removed. |
| 2 | P2 | KTD4 named `already_run_ids` source vaguely and gave no behavior when run-state is unavailable. | Named the source (saga completed-units / workflow manifest) and specified a **conservative fallback** — refuse rather than silently patch a possibly-run unit. |
| 3 | P2 | The R7 `test_segment_boundary_tier_override` scenario conflated emit-ceiling with segment-boundary isolation. | Clarified: the isolation is the U4 not-yet-run filter applied at the boundary; team_emitter honors the current override at emit and does not re-consult per live spawn (which team-execution's skill-driven flow does not do). |
| 4 | P3 | The session-override file's single-file / per-session semantics were unstated. | Noted: machine-local single file; per-session isolation out of scope v1 (single-operator). |

## Verification performed

- `envelope_ceiling` has **no live caller** in `plugins/`/`tests/` (only CHANGELOG + reference doc
  mentions) — confirming it is #366-reserved forward-compat, and confirming the emit-time clamp is the
  correct single enforcement point.
- `emit_workflow_script` bakes per-unit tier (`execution_spec.py:1047-1048, 1085-1086`) — so an
  emit-time clamp on `unit.tier` before rendering is a valid enforcement point.
- The `fleet_commons` additive-only 0.x contract is real (`tier_palette.py:10`, `retry_backoff.py:18`).

## Residual risk

Moderate — this is a Deep, cross-plugin capability (5 units, saga + team-execution). The core clamp and
patch are pure, tested functions riding proven primitives (`tier_palette.clamp`, the existing
`validate`/`emit` CLI). The softest requirement is R7 (team-execution is skill-only; the emit-time seam
is the operator-chosen build). The escalation gate is a minimal ask-rule by design (KTD5); the
spend-delta classifier is #367's.
