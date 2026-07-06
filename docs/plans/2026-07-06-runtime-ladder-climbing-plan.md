---
title: Runtime ladder climbing — gated one-rung escalation on failure signals
type: feat
status: active
date: 2026-07-06
origin: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
---

# Runtime ladder climbing — gated one-rung escalation on failure signals

## Summary

Add the *runtime* climb primitive the tier system is missing: when a unit is refuted, fails, or
self-reports out of depth, climb exactly **one rung** of the existing `MODELS`/`EFFORTS` ladder —
attended runs get an explicit ask gate before any higher-tier re-run; unattended runs may climb
silently but strictly bounded (one climb per unit per run, ceiling-aware, halt at the top). One
merged mechanism, three trigger paths: `escalate_on_signal` (refuted unit), the `/work`
between-rounds recovery proposal, and the worker-initiated `pull_cord` disposition.

## Problem Frame

Plan-time tiers already merge upgrade-only (`segment_units()`,
`plugins/saga/scripts/execution_spec.py:1751-1770` via `tier_palette.strongest`), and #365 gave the
operator a *mid-run manual* lever (`/tier` patch, gated on `is_escalation`,
`execution_spec.py:1355-1370`). But nothing reacts to a **failure signal at runtime**: a refuted
unit today simply **throws** (`verifier-disagreement`, `execution_spec.py:1200-1216`) and a human
re-reads the transcript to guess the next tier; a cheap unit that is substantively wrong but
shape-valid passes silently. The vocabulary ladder ops exist (`tier_palette.escalate`,
`plugins/fleet-core/scripts/fleet_commons/tier_palette.py:158` — single-axis, ceiling-aware,
**no-op at top**), but there is no pair-level `{model, effort}` climb, no runtime consumer, and no
worker-initiated depth signal.

## Requirements (acceptance criteria)

R1. `escalate_tier()` exists in `execution_spec.py`, computes the next rung by index arithmetic on
    the closed ordered `MODELS`/`EFFORTS` sets (via the named `tier_palette` ops — raw `.index()`
    arithmetic is forbidden by `execution_spec.py:1749-1750`), never inventing a tier and never
    skipping a rung. Test: `-k escalate_tier`.

R2. A refuted `escalate_on_signal` unit is re-emitted at exactly one rung up (one axis, one index),
    never more. Test: `-k escalate_on_signal_one_rung`.

R3. A unit already at the top of the ladder that fails again surfaces HALT rather than re-emitting
    or looping. Test: `-k escalate_on_signal_top_of_ladder_halts`.

R4. `/work`'s between-rounds recovery step proposes the next-rung escalation with a cost delta
    after a round fails, and end-clamps at the ladder boundary (documented affordance, not silently
    applied). Check: `plugins/saga/skills/work/references/pr-continuation-loop.md` names the step;
    reviewed in `/doc-review`.

R5. Attended-mode escalation (all three paths) always emits an explicit ask gate before the
    higher-tier re-run — never applied silently. Test: `-k escalate_attended_asks`.

R6. Unattended/cache-tight mode is permitted to climb silently (asymmetric-approval applied in both
    directions). Test: `-k escalate_unattended_silent`.

R7. A `pull_cord` return disposition exists on the unit return contract, distinct from success and
    crash. Test: `-k pull_cord_disposition`.

R8. A `pull_cord` unit is never marked complete and produces exactly one batched escalation entry
    for the coordinator (not one ask per cord). Test: `-k pull_cord_not_complete_batched`.

R9. Full suite, format, lint, types stay green.

**Correction to the issue's checks:** the AC file `tests/test_execution_spec.py` does not exist —
the real suite is `tests/test_saga_execution_spec.py` (verified); all `-k` selectors above run
against it.

## Key Technical Decisions

KTD1 — **Pair-level climb order is effort-first, then model, one rung per event.**
`escalate_tier(tier, *, ceiling=None) -> Tier | None` climbs the EFFORT axis while the current
model supports a stronger effort (`supports_effort` invariant — an unrunnable pair is never
returned); at the model's effort ceiling it climbs the MODEL axis one rung (keeping effort, which
stays runnable on a stronger model whose ceiling is ≥ — validated via `supports_effort`, never
assumed; in the current palette every stronger model's ceiling is ≥ the weaker's,
`plugins/fleet-core/scripts/fleet_commons/models.json` — haiku clamps at `high`, the rest run
`xhigh`). Rationale:
effort is the cheapest increment on the priced lever; model is the dominant spend axis, so it
climbs last. Built on the named `tier_palette` ops (`escalate`, `supports_effort`,
`effort_ceiling`), never raw index arithmetic.

KTD2 — **`escalate_tier` returns `None` at the top; callers convert that to HALT.** The palette's
`escalate` deliberately no-ops at the top rung (`tier_palette.py:158` — vocabulary contract,
`fleet_commons` untouched); the *runtime* semantics (R3: halt, not loop) belong to the consumer.
`None` is the unambiguous at-the-top signal; every caller (emit wiring, `/work` step) renders it
as an explicit HALT/end-clamp, never a silent same-tier re-run.

KTD3 — **Attendance is an emit-time property, not spec state:** `emit_workflow_script(spec,
unattended=False)` + CLI `emit --unattended`. Precedent: `outcome.py --autonomous`
(`outcome.py:1129-1133` — "operator is away"); attendance describes the *run*, not the plan, so it
does not enter the durable spec JSON (no schema change, existing specs round-trip byte-identical).

KTD4 — **The attended ask gate is throw-with-proposal + the existing #365 lever — no ask machinery
enters the emitted script.** An emitted workflow cannot question the operator mid-run; in attended
mode a refuted `escalate_on_signal` unit throws `verifier-disagreement` carrying an explicit
`escalation-proposal: re-run <unit> at <model>/<effort> (+1 <axis> rung)`. The operator confirms by
running the existing `/tier` mid-run patch (gated by `is_escalation`, #365) and re-emitting — the
ask gate is the `/work` operator loop, rhyming with `commands/tier.md:39-42`. In unattended mode
the emitted script itself retries the unit's `agent()` call once at the climbed tier and re-runs
the verify panel.

KTD5 — **Silent climbs are strictly bounded: one climb per unit per emitted run, ceiling-aware,
then HALT.** An unattended re-run that is refuted *again* throws — it never chains a second climb
in the same run (chained climbs are the "loop / silently overspend" failure the issue forbids). A
climb also never exceeds the #365 session ceiling when one is set (`clamp_tier_to_ceiling`
composition): a climb blocked by the ceiling HALTs with the proposal named rather than exceeding
or silently re-running.

KTD6 — **The cost delta is ordinal (rung arithmetic), not priced.** No price-per-tier data exists
anywhere in the repo (verified: `models.json` carries only rank/rung/ceiling); the cost-weighted
spend-delta classifier is #367's (same deferral `commands/tier.md:41-42` records). The `/work`
proposal and the throw-proposal both express the delta as `+1 <axis> rung (<old> → <new>)`.

KTD7 — **`pull_cord` is a return-contract alternative, always batched to ONE coordinator entry.**
The emitted gate helper accepts `{"pull_cord": "<reason>"}` as a valid-shape alternative to the
unit's required return keys (distinct from success and from the malformed/missing-output throw).
Cord units are excluded from completion; all cords collect into one workflow-level batch that
surfaces as a single escalation entry (attended AND unattended — the batching requirement in DoD-4
is absolute; the silent-climb permission of R6 is exercised on the refute path where the retry is
cleanly boundable, not on cords in v1 — recorded as a scope boundary).

## Implementation Units

### U1. `escalate_tier()` — the pair-level one-rung climb (R1)

**Goal:** `escalate_tier(tier, *, ceiling=None) -> Tier | None` in
`plugins/saga/scripts/execution_spec.py` beside `is_escalation` (KTD1/KTD2 semantics), plus a
module docstring note that the runtime ladder consumer lives here, vocabulary stays in the palette.

**Test scenarios** (`tests/test_saga_execution_spec.py`, following the `_spec_dict`/`ES` fixture
pattern at lines 18-48):
- `test_escalate_tier_one_rung_effort_first` — `sonnet/medium → sonnet/high`; never two rungs.
- `test_escalate_tier_model_climb_at_effort_ceiling` — a tier at its model's effort ceiling climbs
  the model axis one rung, keeping a runnable effort.
- `test_escalate_tier_top_of_ladder_returns_none` — the strongest runnable pair returns `None`.
- `test_escalate_tier_ceiling_blocks_climb` — a ceiling at the current tier returns `None`
  (blocked), never exceeds.
- `test_escalate_tier_never_unrunnable` — no input yields a pair failing `supports_effort`.

### U2. `escalate_on_signal` — refute-path wiring in the emitter (R2, R3, R5, R6)

**Goal:** a new optional `Unit.escalate_on_signal: bool` (absent ⇒ False; absent field round-trips
byte-identical, following the `min_tier` pattern at `execution_spec.py:707-710`), plus
`emit_workflow_script(spec, unattended=False)` and `emit --unattended`. In
`_emit_panel_reconciliation` (`execution_spec.py:1122-1216`): attended → the refute throw carries
the `escalation-proposal` line (KTD4); unattended → one in-script retry of the unit's `agent()`
call at the climbed tier, re-run panel, throw if refuted again or if `escalate_tier` returned
`None` (KTD5). Session-ceiling composition per KTD5.

**Composition exclusions (v1, enforced at `validate` — doc-review finding):**
`escalate_on_signal` is rejected with a `SpecError` on (a) a unit whose verify panel sets
`iterate_to_consensus` (`execution_spec.py:471` — nesting the consensus loop inside a climb retry
compounds retry loops into unbounded spend), and (b) a fan-out unit (`fanout=True`,
`execution_spec.py:669` — a climb re-runs the unit across ALL targets, multiplying the higher-tier
spend silently). Both are the "loop / silently overspend" failure the issue forbids; v1 supports
the singleton one-shot-panel path only. Lifting either exclusion is Follow-Up Work.

**Test scenarios** (`tests/test_saga_execution_spec.py`, asserting on emitted JS via the
`_emit_units` pattern):
- `test_escalate_on_signal_one_rung_reemit` — unattended emitted JS retries at exactly one rung up
  (the climbed model/effort literals appear once; the original tier's retry does not).
- `test_escalate_on_signal_top_of_ladder_halts` — a top-rung unit's emitted JS has no retry branch
  and the throw names at-top HALT.
- `test_escalate_attended_asks` — attended (default) emitted JS contains the escalation-proposal
  throw and NO in-script retry at a higher tier.
- `test_escalate_unattended_silent` — `unattended=True` emitted JS climbs without any operator-ask
  marker.
- `test_escalate_on_signal_absent_roundtrips` — a spec without the field round-trips byte-identical.
- `test_escalate_on_signal_rejects_iterate_to_consensus` — `validate` raises `SpecError` on the
  combination (composition exclusion a).
- `test_escalate_on_signal_rejects_fanout` — `validate` raises `SpecError` on a fan-out unit
  (composition exclusion b).

### U3. `pull_cord` — worker-initiated depth disposition (R7, R8)

**Goal:** the emitted gate helper (`_JS_GATE_HELPER`, `execution_spec.py:162` onward) accepts
`{"pull_cord": "<reason>"}` as a valid alternative return (KTD7); cord results are excluded from
unit completion; a workflow-level batch collects every cord and surfaces exactly one escalation
entry (one throw naming all cords + their one-rung proposals) at the end of the run.

**Test scenarios** (`tests/test_saga_execution_spec.py`):
- `test_pull_cord_disposition` — the emitted gate accepts the cord shape as distinct from success
  (required keys) and from the malformed/missing throw.
- `test_pull_cord_not_complete_batched` — the emitted JS never marks a cord unit complete, and two
  cord units produce ONE batched escalation entry, not two.

### U4. `/work` between-rounds recovery step (R4)

**Goal:** document the round-failure escalation proposal at the round-bump seam —
`plugins/saga/skills/work/references/pr-continuation-loop.md` `## Round bump` (line 41) plus the
Phase 0.4 pointer in `plugins/saga/skills/work/SKILL.md:115-128`: on a round-N failure row
(`pr-continuation-loop.md:33-35`), propose the next rung with the ordinal cost delta (KTD6),
end-clamp at the ladder boundary (`escalate_tier → None` ⇒ state "at top of ladder", propose
nothing), and gate on the #365 `is_escalation` confirm-before-re-emit pattern — a documented
affordance the operator confirms, never silently applied.

**Test expectation:** none — docs-only unit; R4's check is `/doc-review` (per the issue's own AC).

### U5. Docs + release surface (R9)

**Goal:** `plugins/saga/references/execution-spec.md` documents the new `escalate_on_signal` field,
the `pull_cord` disposition, and the `emit --unattended` flag; saga `0.67.0 → 0.68.0`;
CHANGELOG; marketplace sync; version-pin test (`tests/test_saga_plugin.py`); DECISIONS
`{#runtime-ladder-climbing-364}` (KTD1-KTD7). No new command ⇒ no docs-model/coverage-count churn
(the #365 lesson applies only when the command surface changes).

**Test expectation:** none — release-surface unit; guarded by the existing drift/parity tests.

## Scope Boundaries

**Out of scope (true non-goals, from the issue):**
- Multi-rung jumps ("escalate straight to opus/xhigh") — one rung per event, KTD1.
- Plan-time `segment_units()` merge logic (`execution_spec.py:1751-1770`) — untouched.
- team-execution's proceed-best-available cap and consensus-protocol iteration — separately owned.
- The silent-omission completeness gate (absent/malformed output) — distinct capability;
  `pull_cord` is worker-initiated *depth*, not absent output.
- Price-per-tier data / cost-weighted deltas — #367's classifier (KTD6).
- `fleet_commons` changes — the palette's `escalate` no-op-at-top contract is untouched (KTD2).

**Deferred to Follow-Up Work:**
- Unattended silent climb for the `pull_cord` path (v1 always batches to a single ask/halt entry —
  KTD7); revisit when a real unattended run demonstrates cords are frequent enough to matter.
- Chained climbs across runs with spend telemetry (needs #366/#367 ledger + classifier).
