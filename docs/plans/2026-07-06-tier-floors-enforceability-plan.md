---
title: Tier floors & backend enforceability — halt, never silently under-tier
type: feat
status: active
date: 2026-07-06
origin: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
---

# Tier floors & backend enforceability — halt, never silently under-tier

## Summary

Give the fleet's tier ladder a **floor** and a **backend-enforceability guarantee**, both failing
loud at emit time rather than degrading silently at runtime. Two mechanisms land this PR: a
`TIER_ENFORCEABLE_BY_BACKEND` matrix that HALTs when a backend cannot spawn a unit's declared model
(the `fable`-on-team-execution case), and an optional `Unit.min_tier` floor that pulls a merged
segment up. A third mechanism from issue #369 — agent-owned `tier-floor:` frontmatter — is **deferred
to a follow-up** (operator decision, 2026-07-06): it has no live producer until the per-teammate
tier-override lever (`{#team-execution-per-teammate-effort}`) exists, so shipping it now would be a
field with only a test for a consumer.

## Problem Frame

The tier vocabulary is an ordered escalation ladder (`MODELS`/`EFFORTS`, now canonical in
`plugins/fleet-core/scripts/fleet_commons/tier_palette.py` after #370). Today the ladder has a
**ceiling** — `segment_units()` merges member tiers upgrade-only via `_tier_palette.strongest(...)`
(`plugins/saga/scripts/execution_spec.py:1617-1620`) — and one enforceability matrix for a *different*
axis (`SANDBOX_ENFORCEABLE_BY_BACKEND`, `execution_spec.py:115-119`, halt-not-degrade). It has no
**floor** and no tier-enforceability guarantee, so two silent-under-tier failure modes exist:

1. A plan-authored `fable/xhigh` unit validates fine against the vocabulary but, routed to
   team-execution, is spawned by `agentType` at the session-global tier — the `fable/xhigh` row the
   worker table renders is **cosmetic, not enforced** (verified: all 25 `plugins/team-execution/agents/*.md`
   pin `model:` ∈ {opus, sonnet, haiku}; **none** pin `fable`, and none set `effort:`).
2. `segment_units()` can only pull a cheap unit *up* by chance of the merge math — there is no way to
   assert "this unit must never resolve below opus/high" as an invariant the merge respects.

## Requirements

R1. A unit whose `tier.model` a target backend cannot spawn HALTs at emit with a **named** `SpecError`
    (e.g. `fable/xhigh` routed to team-execution).

R2. The same tier passes emit on a backend whose enforceable set includes the model (`inline`,
    `cc-workflows-ultracode`).

R3. A backend **absent** from `TIER_ENFORCEABLE_BY_BACKEND` enforces nothing (empty set) — any
    authored model on it halts. Unknown is never permissive (mirrors `SANDBOX_ENFORCEABLE_BY_BACKEND`
    R4).

R4. An optional `Unit.min_tier` floor pulls a merged segment containing a cheaper unit up to **at
    least** the floor tier, via the palette's ladder ops (never bare index arithmetic).

R5. An off-palette `Unit.min_tier` (model/effort not drawn from `MODELS`/`EFFORTS`) fails
    validation/emit with a **named** error.

R6. A spec with **no** `min_tier` declared round-trips through `to_dict`/`from_dict` **byte-identical**
    — no new key emitted.

R7. Existing `segment_units()` golden tests and the full repo gate (pytest, ruff format, ruff check,
    mypy, bandit) stay green — no regression for specs without a floor/tier-halt.

R8. Release surfaces updated in the same PR: `plugins/saga/.claude-plugin/plugin.json` version bump,
    `plugins/saga/CHANGELOG.md` entry, `.claude-plugin/marketplace.json` saga sync, and
    `docs/engineering-journal/DECISIONS.md` KTD entries.

## Key Technical Decisions

KTD1 — **`TIER_ENFORCEABLE_BY_BACKEND` + `unenforceable_tier()` live in `execution_spec.py`, beside
`SANDBOX_ENFORCEABLE_BY_BACKEND`.** The issue calls it a "sibling structure"; both are backend-keyed
(backends are an execution/outcome-spec concept, not a vocabulary concept), and the sandbox matrix is
deliberately kept out of the palette so the module needn't import `outcome_spec`. The vocabulary
palette stays vocabulary-only.

KTD2 — **v1 enforces the MODEL axis only.** `TIER_ENFORCEABLE_BY_BACKEND: dict[str, frozenset[str]]`
maps a backend to the set of models it can spawn: `inline` and `cc-workflows-ultracode` → all `MODELS`
(per-call tier); `team-execution` → `{"opus", "sonnet", "haiku"}` (its agent-frontmatter set; **no
fable**). `fable/xhigh` on team-execution halts via `fable ∉ set`. The **effort** axis (`xhigh`)
enforceability is entangled with per-teammate effort — the QUEUED `{#team-execution-per-teammate-effort}`
lever — so it rides with the deferred mechanism 3 rather than half-shipping here. A backend absent from
the matrix → `frozenset()` (R3).

KTD3 — **`Unit.min_tier: Tier | None` reuses the `Tier` type and the optional-field pattern** already
used by `sandbox`/`verify`: `from_dict` parses only when the key is present, `to_dict` emits only when
non-None (→ byte-identical round-trip, R6), and `validate` delegates to `Tier.validate`, which already
rejects off-palette models/efforts and unrunnable pairs (→ R5). The floor is validated as a normal
(non-engine) tier, so an on-palette-but-unrunnable floor (e.g. `haiku/xhigh` — haiku's ceiling is
`high`) also halts. The per-axis clamp in `segment_units()` cannot introduce an unrunnable pair: it
only raises `model` toward `fable` (fable/opus/sonnet all reach `xhigh`), and an unrunnable floor is
rejected by `validate` before it can ever apply.

KTD4 — **The floor clamp reuses the palette's `strongest()`/`stronger()` ladder ops** (#370), never
re-derived `MODELS.index()`/`EFFORTS.index()` arithmetic — the invariant `{#tier-vocab-ordering}`
protects. Because a segment collapses to **one** resident spawn, any member unit's floor raises the
**whole** merged segment tier (the strongest of {merged tier, all member floors}).

KTD5 — **Mechanism 3 (agent-owned `tier-floor:` frontmatter) is deferred** to a follow-up issue that
lands it together with the per-teammate tier-override lever, so the field ships with a real producer
*and* consumer. No team-execution plugin changes in this PR (operator decision, 2026-07-06).

## Implementation Units

### U1. `TIER_ENFORCEABLE_BY_BACKEND` matrix + `unenforceable_tier()` helper

Add the matrix and helper to `execution_spec.py` immediately after
`SANDBOX_ENFORCEABLE_BY_BACKEND` (`:115-119`) and `unenforceable_sandbox_axis()` (`:588-606`),
mirroring their shape and comments. `unenforceable_tier(backend, tier)` returns the offending
`(axis, value)` (`("model", tier.model)`) when `tier.model` is not in the backend's enforceable set,
else `None` — signature-parallel to `unenforceable_sandbox_axis`. Unlike the sandbox helper, it is
**not** duck-typed across houses: it takes an execution-spec `Tier` only. `outcome_spec.Node`
(`plugins/saga/scripts/outcome_spec.py:187`) carries no `{model, effort}` tier, so there is no
Node-house tier to enforce and no dual-house generality to add.

**Test scenarios** (`tests/test_saga_execution_spec.py`):
- `test_unenforceable_tier_halts_fable_on_team_execution` — `unenforceable_tier("team-execution",
  Tier("fable","xhigh"))` returns `("model","fable")`.
- `test_unenforceable_tier_passes_reachable_model` — `unenforceable_tier("team-execution",
  Tier("opus","high"))` and `("inline", Tier("fable","xhigh"))` both return `None`.
- `test_unenforceable_tier_unknown_backend_never_permissive` — an unlisted backend (e.g. `"fork"`)
  returns the offending model for any authored tier (R3).

### U2. `Unit.min_tier` field + validation + round-trip + `segment_units()` clamp

Add `min_tier: Tier | None = None` to `Unit` (after `sandbox`, `:650`). Wire it into
`Unit.validate` (delegate to `Tier.validate` with a `min_tier` `where`), `Unit.from_dict` (parse only
when present, mirroring `sandbox`), and `Unit.to_dict` (emit only when non-None). In `segment_units()`
at `:1617-1620`, after the `strongest(...)` merge, pull `seg_tier` up to the strongest of {merged
tier, every member unit's `min_tier`} using `_tier_palette.stronger`/`strongest`.

**Test scenarios** (`tests/test_saga_execution_spec.py`):
- `test_min_tier_pulls_cheap_segment_up` — a segment with one `min_tier=opus/high` unit and one
  cheaper unit merges to at least `opus/high`.
- `test_off_palette_min_tier_fails_emit` — a `min_tier` model/effort off `MODELS`/`EFFORTS` fails
  validation with a named error.
- `test_absent_min_tier_round_trips_byte_identical` — a spec with no `min_tier` survives
  `to_dict`/`from_dict` unchanged (no new key).

### U3. Wire the tier-enforceability HALT into the team-execution emit path

Depends on U1. In `team_emitter.py`, add a loop beside the existing sandbox-halt loop
(`:216-225`) that calls `mod.unenforceable_tier("team-execution", unit.tier)` and raises
`mod.SpecError(...)` (via the same identity-preserving `mod` handle) with a message naming the unit,
the offending model, and the reroute remedy (inline / cc-workflows), matching the sandbox-halt
message shape.

**Test scenarios** (`tests/test_team_emitter.py`):
- `test_fable_xhigh_unit_halts_on_non_enforcing_backend` — an ExecutionSpec with a `fable/xhigh` unit
  raises `SpecError` from `emit_team_structure`. Note `emit_team_structure` is team-execution-only
  (no backend parameter), so the "passes on an enforcing backend (inline / cc-workflows)" half of the
  issue AC is asserted at the **helper** level in U1's `test_unenforceable_tier_passes_reachable_model`
  (`unenforceable_tier("inline", Tier("fable","xhigh")) is None`), not by re-driving this emitter — the
  team_emitter test owns only the HALT branch.

### U4. Release surface + journal

Depends on U1–U3. Bump `plugins/saga/.claude-plugin/plugin.json` 0.64.0 → 0.65.0, add a
`plugins/saga/CHANGELOG.md` entry (new `Unit.min_tier` schema field + tier-enforceability emit halt),
sync the saga version in `.claude-plugin/marketplace.json` (via `scripts/sync_marketplace.py` then
`python3 -m json.tool` validation), and record KTD1–KTD5 in `docs/engineering-journal/DECISIONS.md`
(with a `LEARNINGS.md` entry only if the build surfaces a non-obvious mechanism).

**Test expectation:** none — release-surface/config unit. Guarded by the existing metadata
drift-guard tests + `python3 -m json.tool` on marketplace.json.

## Scope Boundaries

**Out of scope (true non-goals):**
- Changing `SANDBOX_ENFORCEABLE_BY_BACKEND` or any sandbox-axis behavior — the tier matrix is a
  sibling, not a modification.
- Backfilling `min_tier` onto existing units — it is optional; v1 enforces only where declared.
- Any `inline`-backend change — inline already spawns arbitrary `{model, effort}` per call.

**Deferred to follow-up work** (operator decision 2026-07-06, KTD5):
- Mechanism 3 — agent-owned `tier-floor:` frontmatter on `plugins/team-execution/agents/*.md` and its
  spawn-path clamp, to land WITH the per-teammate tier-override lever
  (`{#team-execution-per-teammate-effort}`) so it has a real producer.
- The `tests/test_team_emitter.py::test_plan_assigning_below_floor_is_clamped_or_fails` acceptance
  test (belongs to mechanism 3).
- Effort-axis (`xhigh`) enforceability in `TIER_ENFORCEABLE_BY_BACKEND` (entangled with per-teammate
  effort; rides with mechanism 3).
- team-execution plugin release surface (`plugins/team-execution/.claude-plugin/plugin.json`,
  `CHANGELOG.md`) — untouched this PR since no team-execution files change.

**Issue disposition.** This PR delivers #369 in two parts. It satisfies the issue's tier-floor and
backend-enforceability headline via mechanisms 1 & 2 (`Unit.min_tier` is a live floor with a real
producer and consumer). It does **not** satisfy the issue's literal DoD line-item for mechanism 3, so
#369 is **not** auto-closed by this PR. At merge, file a mechanism-3 follow-up issue (via
`mission-control`, carrying the `{#team-execution-per-teammate-effort}` producer) and leave #369 open,
re-scoped to track that follow-up — or close #369 with a comment pointing at the follow-up if the
operator prefers. Use `re #369` (not `Fixes #369`) in the PR body to avoid auto-close on partial
delivery.
