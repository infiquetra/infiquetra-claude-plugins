---
title: /tier mid-run lever — session ceiling + re-emit from the canonical spec
type: feat
status: active
date: 2026-07-06
origin: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
---

# /tier mid-run lever — session ceiling + re-emit from the canonical spec

## Summary

Give the operator a live, mid-run lever over model/effort tier that never requires aborting and
re-planning. Two cooperating mechanisms: a **session ceiling** (a run-scoped `{model, effort}` cap the
emitters clamp every unit down to) and a **mid-run patch** (edit not-yet-run units' tiers in the
canonical `ExecutionSpec`, re-validate, re-emit), with an **escalation gate** (an up-ladder move asks;
cheapen/lateral proceeds). Delivered across the saga and team-execution plugins per issue #365, all
seven requirements (operator decision 2026-07-06: build R7 in full).

## Problem Frame

The fleet's only operator-facing tier lever today is the one-time `/plan`-authored per-unit tier table,
baked into the `ExecutionSpec` JSON at emit time. Session mining across 3 repos recorded operators
pausing mid-run to manually negotiate a model change with no first-class command (grounding brief
pattern 6). The tier resolver already has a model-only `envelope_ceiling` clamp
(`tier_resolver.resolve()`, `plugins/fleet-core/scripts/fleet_commons/tier_resolver.py:152-157`, built
forward-compat for #366) and the palette has a 2-axis `clamp(kind, value, ceiling=…)` ladder op
(#370) — so this rides existing primitives rather than inventing arithmetic.

## Requirements

R1. `/tier <ceiling>` writes a session-local override file recording a run-scoped tier ceiling.

R2. The emit path reads the session-override on every emit and clamps any unit/segment tier above the
    ceiling **down** to it, via the palette's 2-axis `clamp` — never raising a tier.

R3. Every clamp is logged (unit id, original tier, clamped tier) and does not re-prompt.

R4. `/tier <unit-selector> <new-tier>` edits the tier of the named **not-yet-run** unit(s) in the
    canonical `ExecutionSpec` JSON, leaving already-run units untouched.

R5. After a patch, re-run `execution_spec.py validate` (hard block on failure) then `emit` to
    regenerate the downstream `.workflow.js`.

R6. A mid-run **escalation** (up-ladder) is routed through the escalation gate and requires explicit
    operator confirmation before validate/emit; a cheapen-or-lateral move proceeds without a prompt.

R7. For team-execution, `team_emitter` reads the same session-override when emitting worker rows so a
    tier change written between segments affects only the next (not-yet-shed) segment's worker spec.

R8. Full repo gate stays green; release surfaces updated for **both** plugins (new command, new schema,
    resolver/emitter behavior).

## Key Technical Decisions

KTD1 — **Session-override file: git-ignored, session-local, one schema.** Path
`.claude/saga/tier-session-override.json` (the saga machine-local cache home, never `git add`ed).
Schema: `{"ceiling": {"model": str, "effort": str} | null, "unit_overrides": {"<unit_id>": {"model":
str, "effort": str}}}`. A small read/write module (`plugins/saga/scripts/tier_session.py`) owns the
schema + validation (off-palette values fail loud). The file is machine-local and single (one override
per checkout); per-session isolation for concurrent sessions is out of scope for v1 (single-operator
assumption).

KTD2 — **Enforcement point is EMIT (the single uniform point); inline is advisory.** Both emitters
(`execution_spec.emit_workflow_script` and `team_emitter.emit_team_structure`) read the session
override and clamp each unit/segment tier down to the ceiling before rendering — one uniform
enforcement point for every backend whose tier is baked at emit (workflow + team-execution). The
resolver's `envelope_ceiling` is **deliberately not touched**: it lives in shared `fleet_commons` under
an additive-only 0.x contract, has **no live caller** (verified — only doc references), and is reserved
for #366's spend envelope; clamping the final `seg.tier` at emit already covers both axes *after* the
resolve cascade runs, so extending the resolver would be both redundant and an additive-only-contract
risk. The `inline` backend has no emit step, so it honors the ceiling **advisorily** (the operator /
Claude reads the file). Clamp uses `tier_palette.clamp` (2-axis, downward-only) — never re-derived index
math (`{#tier-vocab-ordering}`).

KTD3 — **The clamp is a pure shared helper.** `clamp_tier_to_ceiling(tier, ceiling) -> Tier` in
`execution_spec.py`, downward-only (a ceiling never raises a tier). Both emitters call it, so the
R2/R7 behavior is one tested function.

KTD4 — **Mid-run patch is a pure function + a CLI-driven re-emit.** `patch_spec_tiers(spec,
unit_overrides, already_run_ids) -> spec` edits only units whose id is **not** in `already_run_ids` —
the pure, tested contract. The `/tier` command derives `already_run_ids` from live run-state (the
saga's completed-units / the workflow manifest); **absent reliable run-state for a backend, the patch
is conservative** — it refuses (or warns and requires an explicit force) rather than silently patching
a unit that may already have run. Patch → `validate` (hard gate, raises `SpecError` on failure — never
emit an invalid spec) → `emit`. Rides the existing `execution_spec.py validate`/`emit` CLI seam; no new
re-emit machinery.

KTD5 — **Escalation gate is the minimal ask-rule, not a spend-delta classifier.** An up-ladder move (by
palette strength on either axis) requires operator confirmation; cheapen/lateral proceeds. The
sophisticated spend-delta classifier is #367's deliverable (unbuilt) — this issue implements only the
minimal gate its consumer (`/tier` patch) needs, and defers cost-weighted asymmetry to #367.

KTD6 — **`/tier` is a command doc over Python helpers.** `plugins/saga/commands/tier.md` (matching the
saga `commands/*.md` house pattern) orchestrates the `tier_session.py` write + the patch/validate/emit
helpers; all logic is in tested Python, the doc is thin.

## Implementation Units

### U1. Session-override module + `/tier` command doc

`plugins/saga/scripts/tier_session.py`: read/write `.claude/saga/tier-session-override.json`, schema +
off-palette validation (reject a ceiling/override drawn off `MODELS`/`EFFORTS`). `plugins/saga/commands/tier.md`:
the `/tier` command doc (ceiling form + mid-run patch form), thin over the Python helpers.

**Test scenarios** (`tests/test_tier_session.py`):
- `test_tier_ceiling_write` — `/tier sonnet/medium` writes a well-formed override file (round-trips).
- `test_tier_session_off_palette_rejected` — an off-palette ceiling/override fails loud.

### U2. Ceiling clamp helper (pure)

`clamp_tier_to_ceiling(tier, ceiling) -> Tier` in `execution_spec.py` — downward-only, 2-axis via
`tier_palette.clamp` (clamp model and effort each to no stronger than the ceiling). The single clamp
primitive both emitters call (U3). The resolver is deliberately untouched (KTD2).

**Test scenarios** (`tests/test_saga_execution_spec.py`):
- `test_tier_ceiling_clamp` — a sonnet/medium ceiling clamps an opus/high tier to sonnet/medium.
- `test_tier_ceiling_never_escalates` — a ceiling weaker than the tier is a no-op (a ceiling never
  raises a tier), on both the model and effort axes.

### U3. Emit-time ceiling application (both emitters) — R2 + R7

Both `execution_spec.emit_workflow_script` and `team_emitter.emit_team_structure` read the session
override (when present) and clamp each unit/segment tier via `clamp_tier_to_ceiling` before rendering,
logging each downgrade. This is the single R2 enforcement point and the R7 team-execution seam.

**Test scenarios** (`tests/test_saga_execution_spec.py`, `tests/test_team_emitter.py`):
- `test_workflow_emit_honors_session_ceiling` — an emitted `.workflow.js` reflects clamped tiers.
- `test_team_emit_honors_session_ceiling` — an emitted team structure reflects the ceiling (each
  worker row clamped).
- `test_segment_boundary_tier_override` — the R7 isolation property: given a set of already-shed (run)
  unit ids, a re-emit after an override write clamps only the **not-yet-shed** segment's worker rows,
  leaving an already-shed segment's recorded tier untouched. (R7's "only the next segment" is the U4
  not-yet-run filter applied at the segment boundary — team_emitter honors the current override at
  emit; it does not re-consult per live spawn, which team-execution's skill-driven flow does not do.)

### U4. Mid-run patch + validate-gate + re-emit + escalation gate — R4/R5/R6

`patch_spec_tiers(spec, unit_overrides, already_run_ids)` (not-yet-run only) in `execution_spec.py`;
an `is_escalation(old_tier, new_tier)` helper (up-ladder by palette strength). The `/tier` patch path:
gate escalations (ask), patch, `validate` (hard block), `emit`.

**Test scenarios** (`tests/test_saga_execution_spec.py`):
- `test_tier_patch_unrun_only` — a patch touches only not-yet-run units; already-run untouched.
- `test_tier_patch_validate_gate` — an invalid patched spec hard-blocks before emit.
- `test_tier_patch_reemit` — a valid patch re-emits a valid workflow, already-run units untouched.
- `test_tier_patch_spend_delta_gate` — an up-ladder patch flags escalation (confirm required); a
  cheapen/lateral does not.

### U5. Docs + release surface (both plugins)

`plugins/saga/skills/plan/SKILL.md`: note the mid-run lever + its relation to the authored tier table.
`plugins/team-execution/skills/team-execution/SKILL.md`: note the segment-boundary override read. Bump
`plugins/saga` and `plugins/team-execution` plugin.json + CHANGELOGs, sync `.claude-plugin/marketplace.json`,
update drift-guard version pins, record KTD1-KTD6 in `DECISIONS.md`.

**Test expectation:** none — docs/release-surface unit; guarded by the metadata drift-guard tests +
`python3 -m json.tool` on marketplace.json.

## Scope Boundaries

**Out of scope (true non-goals):**
- Building the spend-delta classifier as a general fleet primitive — #367's deliverable; U4 ships only
  the minimal escalation ask-gate (KTD5).
- A runtime-injection override outside the CLI-driven / spec-re-emit seam (`{#operator-choice-framework}`
  stays doc-only/CLI-driven).
- Retroactive edits to already-run units' recorded tier history.
- Changing team-execution's existing proceed-best-available cap or other segment-boundary behavior.

**Deferred to follow-up work:**
- Cost-weighted spend-delta asymmetry (fable/xhigh cost weighting) — lands with #367.
