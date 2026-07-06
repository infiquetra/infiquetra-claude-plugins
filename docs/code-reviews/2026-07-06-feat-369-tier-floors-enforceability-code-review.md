---
title: Code-review — tier floors & backend enforceability (#369)
target: feat/369-tier-floors-enforceability (main..HEAD)
reviewed_revision: a1beafc
blocked: false
date: 2026-07-06
mode: programmatic (in-loop /work gate)
linked_issue: infiquetra/infiquetra-claude-plugins#369
linked_plan: docs/plans/2026-07-06-tier-floors-enforceability-plan.md
linked_work_session: docs/work-sessions/2026-07-06-tier-floors-enforceability.md
---

# Code-review — tier floors & backend enforceability (#369)

**Verdict: NOT BLOCKED (clean after fix).** One P0 was found by an independent adversarial verifier,
fixed, and the fix independently re-verified. Scope CLEAN; plan-completion DONE for the in-scope
mechanisms (1 & 2); mechanism 3 correctly deferred.

## Scope check

**CLEAN.** Intent: ship #369 mechanisms 1 (backend-enforceability halt) & 2 (`Unit.min_tier` floor);
defer mechanism 3. Delivered: exactly that plus release surface + journal. No scope creep; every
changed file maps to a plan U-ID.

## Plan-completion audit

| Req | Status | Evidence |
|-----|--------|----------|
| R1 halt on unenforceable model | DONE | `team_emitter.py` post-merge halt + `test_fable_xhigh_unit_halts_on_non_enforcing_backend` |
| R2 passes on enforcing backend | DONE | `test_unenforceable_tier_passes_reachable_model` |
| R3 unknown never permissive | DONE | `unenforceable_tier` `.get(backend, frozenset())` + `test_unenforceable_tier_unknown_backend_never_permissive` |
| R4 min_tier pulls segment up | DONE | `segment_units()` clamp + `test_min_tier_pulls_cheap_segment_up` |
| R5 off-palette min_tier fails | DONE | `Unit.validate` → `Tier.validate` + `test_off_palette_min_tier_fails_emit` |
| R6 byte-identical round-trip | DONE | conditional `to_dict` + `test_absent_min_tier_round_trips_byte_identical` |
| R7 no regression | DONE | full suite 2222 passed, 1 skipped |
| R8 release surfaces | DONE | plugin.json 0.65.0, CHANGELOG, marketplace sync, DECISIONS, drift-guard |
| Mechanism 3 | DEFERRED | KTD5 (operator-approved) — correctly not built |

## Findings

| # | Sev | File | Issue | Route | Status |
|---|-----|------|-------|-------|--------|
| 1 | P0 | `plugins/saga/scripts/team_emitter.py` | The tier-enforceability halt checked pre-merge `unit.tier`, but the `min_tier` floor clamp raises the merged `Segment.tier` *after* it — so a `min_tier: fable/xhigh` floor bypassed the halt and landed a `fable/xhigh` segment on team-execution with no `SpecError` (the exact silent-under-tier failure #369 prevents). | fixed in-loop | RESOLVED `a1beafc` |

**Fix:** moved the halt to run on the post-merge `Segment.tier` (`for seg in segments:
unenforceable_tier("team-execution", seg.tier)`), which subsumes the per-unit case. Added regression
test `test_min_tier_floor_cannot_bypass_the_team_execution_tier_halt`.

## Adversarial verification

Two independent read-only, worktree-isolated verifier passes (`saga:readonly-verifier`):

1. **Initial pass** — REFUTED claim 1 (found the bypass, reproduced by execution); claims 2 (clamp
   direction / no unrunnable pair) and 3 (round-trip / validation) HELD.
2. **Re-verify of the fix** — CLAIM 1 NOW-CLOSED (ran the exact repro against committed code, halt
   fires); OVER-BLOCK none (chaperone tiers ∈ {opus, sonnet}, existing chaperone tests pass);
   OTHER-BYPASS none (`team_emitter` is the sole team-execution entry point, halt runs unconditionally
   before any row renders). **VERDICT: SAFE-TO-MERGE.**

## Coverage

Suppressed: 0. Residual risk: low — the change is 2 code files with proven in-repo pattern siblings,
full gate green, and the one compositional edge is now regression-tested. Testing gaps: none
identified for the in-scope mechanisms.
