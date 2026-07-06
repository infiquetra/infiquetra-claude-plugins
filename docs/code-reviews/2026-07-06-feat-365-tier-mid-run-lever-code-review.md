---
title: Code-review — /tier mid-run lever (#365)
target: feat/365-tier-mid-run-lever (main..HEAD)
reviewed_revision: 94a3d8c
blocked: false
date: 2026-07-06
mode: programmatic (in-loop /work gate)
linked_issue: infiquetra/infiquetra-claude-plugins#365
linked_plan: docs/plans/2026-07-06-tier-mid-run-lever-plan.md
linked_work_session: docs/work-sessions/2026-07-06-tier-mid-run-lever.md
---

# Code-review — /tier mid-run lever (#365)

**Verdict: NOT BLOCKED (clean after fix).** One P0 found (flagged on review, confirmed by an
independent adversarial verifier via execution), fixed in two layers, and the fix independently
re-verified. Scope CLEAN; all 7 requirements + 5 units delivered.

## Scope check

**CLEAN.** Intent: ship the `/tier` mid-run lever (session ceiling + mid-run patch + escalation gate +
R7 team-execution segment-boundary read). Delivered: exactly that across saga + team-execution, plus
docs + release surface. Every changed file maps to a plan U-ID.

## Plan-completion audit

| Req | Status | Evidence |
|-----|--------|----------|
| R1 session ceiling file | DONE | `tier_session.py` + `test_tier_ceiling_write` |
| R2 emit clamps to ceiling | DONE | `clamp_tier_to_ceiling` + emit clamp + `test_workflow/team_emit_honors_session_ceiling` |
| R3 clamp logged, no re-prompt | DONE | emit comment/HTML-comment logs |
| R4 patch not-yet-run only | DONE | `patch_spec_tiers` + `test_tier_patch_unrun_only` |
| R5 patch validate-gate + re-emit | DONE | `patch` CLI `validate()` + `test_tier_patch_validate_gate`/`reemit` |
| R6 escalation gate | DONE | `is_escalation` + patch CLI NOTE + `test_tier_patch_spend_delta_gate` |
| R7 segment-boundary override | DONE | `team_emitter` ceiling read + `test_segment_boundary_tier_override` |
| R8 release surfaces | DONE | saga 0.66.0, team-execution 2.12.0, marketplace, CHANGELOGs, DECISIONS, drift guards, docs model |

## Findings

| # | Sev | File | Issue | Route | Status |
|---|-----|------|-------|-------|--------|
| 1 | P0 | `tier_session.py` + `execution_spec.py` (emit clamp) | `tier_session` accepted an on-palette-but-unrunnable tier (`haiku/xhigh`); the emit-time ceiling clamp then rendered an unrunnable `{model, effort}` into the emitted workflow/team artifact with **no halt** — silently defeating the #369/#370 halt-not-clamp discipline. The mid-run patch path was already safe (`validate()` gates it). | fixed in-loop | RESOLVED `94a3d8c` |

**Fix (two layers, defense in depth):**
1. `tier_session._validate_tier` rejects an unrunnable tier (`tier_palette.supports_effort`) at both
   write and read — the operator gets a loud error, and a hand-edited file fails on read.
2. `clamp_tier_to_ceiling` pulls the clamped effort down to the clamped model's `effort_ceiling`,
   making it a **total function** that returns a runnable tier even for a direct caller (an emitter)
   passed an unrunnable ceiling Tier. Provably sufficient: a runnable ceiling can never yield an
   unrunnable result. Two regression tests added.

## Adversarial verification

Two independent read-only, worktree-isolated verifier passes (`saga:readonly-verifier`):

1. **Initial pass** — REFUTED claim 1 (found + reproduced the unrunnable-tier leak by execution,
   localized to the emit-clamp path, distinguished from the safe patch path); claims 2 (clamp
   direction / floor precedence), 3 (not-yet-run filter), 4 (`dataclasses.replace` field preservation)
   HELD.
2. **Re-verify of the fix** — LEAK CLOSED on both paths (reproduced by execution); NEW-PROBLEM none
   (exhaustive palette sweep: validation matches `supports_effort` exactly, normal-path clamp
   byte-identical); OTHER none. **VERDICT: SAFE-TO-MERGE.**

## Coverage

Suppressed: 0. Residual risk: low — the change rides proven primitives (`tier_palette.clamp`, the
`validate`/`emit` CLI seam), full gate green, and the one real correctness hole is now closed at two
layers and regression-tested. The ceiling-vs-floor precedence (operator-wins) and R6-minimal-gate are
documented operator/plan decisions (KTD3/KTD5), not defects.
