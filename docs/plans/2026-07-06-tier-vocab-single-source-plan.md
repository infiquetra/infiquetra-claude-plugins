---
title: Single-source tier palette — models.json registry, ladder ops, effort ceilings, drift-proofing
type: refactor
status: active
date: 2026-07-06
origin: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
---

# Single-source tier palette — models.json registry, ladder ops, effort ceilings, drift-proofing

## Summary

Turn the fleet's model/effort vocabulary into a registry-backed, ladder-aware, drift-guarded single
source. The vocabulary tuples were already extracted to `fleet-core/scripts/fleet_commons/tier_palette.py`
by #362/#463; this issue makes that module *authoritative* — data-driven ordering from a `models.json`
registry, named `escalate`/`downgrade`/`clamp` ladder operations, per-model effort ceilings that HALT
unsupported `{model, effort}` combinations, a repo-wide bare-literal drift guard, an onboarding runbook,
and a sync guard so the operator-facing tier tables cannot drift from the catalog.

## Problem Frame

The tier vocabulary is defined once but not *enforced* as single-source: `MODELS`/`EFFORTS` are still
hand-ordered tuples (`tier_palette.py:21,24`), the ordering contract is guarded only by one example test,
per-model effort reachability is unvalidated (a `haiku`/`xhigh` teammate would resolve to an unrunnable
tier instead of halting), and nothing stops a second bare `"opus"` literal from appearing fleet-wide.
The `{#tier-vocab-ordering}` learning (`LEARNINGS.md:164`) already recorded that this tuple "used for
membership and ordering has two contracts" and bit the fleet once during #285.

**Reconciliation is the load-bearing frame.** Issue #370 was authored *before* #362 (dispatch tier
resolver) and #363 (effort first-class) merged. Its literal file list (`plugins/saga/scripts/tier_vocab.py`,
`plugins/saga/scripts/models.json`) is stale: the vocabulary now lives in the **fleet-core** plugin, one
AC is already satisfied, and one is half-satisfied. Planning against the issue's letter would rebuild a
second source-of-truth — the precise drift this issue exists to eliminate. This plan honors the issue's
*intent* (one canonical, registry-backed, guarded vocabulary) over its pre-merge *letter*.

## Current-state reconciliation (verified against the merged tree)

Every row below was verified by reading the current `main`, not the issue's pre-merge line numbers.

| #370 AC | Current state | Evidence | This plan |
|---|---|---|---|
| AC9 — `execution_spec` imports MODELS/EFFORTS, no inline def | **INTENT MET, literal check off** | re-export alias at `execution_spec.py:61-62` (no inline tuple) — but AC9's grep `^MODELS = ` still matches the alias line | U1 resolves: tighten the AC9 check to a tuple-literal pattern, or document the re-export as compliant (finding H) |
| AC8 — catalog drives both tables + `--check` | **PARTIAL** | `/plan` table already rendered from `tier_policy.json` via `render_tier_table.py`, guarded by `test_tier_resolver.py::test_skill_registry_sync`; team-execution table is prose-referenced, **not** guarded | Net-new = team-execution vocabulary guard (U5) |
| AC2 — MODELS/EFFORTS derived from `models.json` rank/rung | TODO | hand-ordered tuples at `tier_palette.py:21,24` | U1 |
| AC3 — `escalate`/`downgrade`/`clamp`; `segment_units` calls them | TODO | `segment_units()` still inlines `min(MODELS.index)`/`max(EFFORTS.index)` at `execution_spec.py:1600-1601` | U2 |
| AC5 — per-model `effort_ceiling`; clamp consults it | TODO | no ceiling data anywhere | U1 (data) + U2 (clamp) |
| AC6 — unsupported combo HALTs `validate()`; engine workers excluded | TODO | `Tier.validate()` (`execution_spec.py:409`) checks membership only | U3 |
| AC7 — parametrized ladder-monotonicity test | TODO | only the single example `test_segment_tier_merge_prefers_fable_and_xhigh` (`test_team_emitter.py:473`) | U3 |
| AC1 — zero bare model literals outside the vocab module | TODO | no guard exists | U4 |
| AC4 — `tier-palette.md` onboarding runbook + ordering guard | TODO | no runbook | U5 |

## Requirements

- **R1 (AC2/AC9).** `MODELS`/`EFFORTS` derive from a `models.json` registry (explicit `rank`/`rung`),
  not hand-ordered tuples; `execution_spec.py` continues to import them (no re-declaration). A mis-ranked
  registry row fails an ordering guard.
- **R2 (AC3).** `escalate(tier, steps)`, `downgrade(tier, steps)`, `clamp(tier, floor, ceiling)` exist as
  named, bound-respecting operations in `tier_palette.py` (escalate past the strongest rung is a no-op,
  not an error); `segment_units()` calls them instead of inlining index arithmetic.
- **R3 (AC5).** Each model in `models.json` carries an `effort_ceiling`; `clamp()`/`escalate()` consult it,
  and a clamp is surfaced as a note rather than applied silently.
- **R4 (AC6).** An unsupported `{model, effort}` combination assigned to a Claude teammate (e.g.
  `haiku`/`xhigh`) makes `validate()` HALT loudly (never silent clamp); engine-owned chaperone-dispatch
  workers are excluded from this per-teammate ceiling check.
- **R5 (AC7).** A parametrized ladder-monotonicity test asserts, for every adjacent pair in `MODELS` and
  `EFFORTS`, that `segment_units()`'s merge picks the stronger member.
- **R6 (AC1).** A repo-wide drift guard asserts zero bare model/effort literal strings outside the
  canonical home (`tier_palette.py`, `models.json`) and its sanctioned re-export shims; red when a bare
  literal is reintroduced, green on the merged tree.
- **R7 (AC4).** `plugins/fleet-core/references/tier-palette.md` onboarding runbook exists and encodes the
  `{#tier-vocab-ordering}` rule ("grep for `.index(` before extending the tuple"); a parametrized
  ordering guard fails when a new model is mis-inserted at the wrong rank.
- **R8 (AC8).** The operator-facing tier vocabulary in `team-execution/SKILL.md` is drift-guarded against
  the catalog (the `/plan` table is already guarded); a scratch edit that diverges the displayed
  vocabulary from the catalog fails a `--check`/test.
- **R9 (release surface).** The fleet-behavior change is reflected in the correct plugin release surfaces
  (fleet-core primary), with drift-guard version pins moved in lockstep.

## Key Technical Decisions

- **KTD1 — Extend the existing `tier_palette.py` in fleet-core; do NOT create `tier_vocab.py`.**
  #370's DoD#1 predates #463's extraction. The canonical vocab module already exists at
  `fleet-core/scripts/fleet_commons/tier_palette.py` with `MODELS`/`EFFORTS`/`model_rank`/`effort_rank`
  and the ORDERING-IS-LOAD-BEARING docstring. Creating a second `tier_vocab.py` would manufacture the
  exact drift the issue kills. Consequence: the new module code, `models.json`, and the runbook live in
  **fleet-core**, and the primary release surface is fleet-core — not saga (reconciles the issue's stale
  path list and release checklist).

- **KTD2 — `models.json` (model→`rank`/`rung`/`effort_ceiling`) is a NEW registry, separate from the
  existing `tier_policy.json` (work-shape→default tier).** They answer different questions — *what is the
  ordered vocabulary* vs *what tier does a work-shape default to*. Keep them distinct files; do not merge.
  `tier_palette.py` derives `MODELS`/`EFFORTS` from `models.json` at import; `tier_policy.json` is untouched.

- **KTD3 — `effort_ceiling` is the single support mechanism; no separate `MODEL_EFFORT_SUPPORT` matrix.**
  #370 AC5/AC6 offer "matrix OR ceiling-derived equivalent." Choose ceiling-derived to avoid two
  overlapping structures: `supported(model, effort) := effort_rank(effort) <= effort_rank(model.effort_ceiling)`.
  One datum (`effort_ceiling`) drives both the clamp (R3) and the validate-halt (R4).

- **KTD4 — The unsupported-combo HALT lives in `Tier.validate()` (`execution_spec.py:409`) and excludes
  engine-owned chaperone units.** After the existing membership checks, add a ceiling check that raises
  `SpecError` for Claude teammates. Units carrying `engine`/`capability` (intent `offload`/`second-opinion`,
  per `{#external-engine-chaperone-dispatch}`, #318) are excluded — they stay pinned to their chaperone
  tiers. HALT, never silent clamp (honors the `/outcome` HALT-not-degrade binding).

- **KTD5 — R8 reuses the existing render/sync infra, extended to the team-execution vocabulary — not a
  parallel `tier_catalog.py`.** The `/plan` table is already registry-driven (`render_tier_table.py`) and
  guarded (`test_skill_registry_sync`). The net-new work is a sync guard over the vocabulary cells the
  **team-execution** SKILL.md displays (tier pairs + `ENGINE_INTENTS`). If the team-execution "worker
  table" is an illustrative template rather than a work-shape catalog, the guard targets the displayed
  vocabulary tokens, not a full table re-render — the check is "no bare vocabulary token in that SKILL.md
  diverges from the catalog," which composes with R6's fleet-wide guard.

- **KTD6 — Release surface is fleet-core primary.** fleet-core `plugin.json`/`CHANGELOG.md`/marketplace
  entry bump (the module lives there). saga bumps only if its shim or `plan/SKILL.md` block changes;
  saga ALSO bumps because U2/U3 modify `execution_spec.py` (the `segment_units` refactor + the new
  `Tier.validate` HALT are saga behavior changes); team-execution bumps only if U5 edits its SKILL.md
  content for R8. Reconciles #370's stale "saga plugin.json" checklist against where the code actually lives.

## Implementation Units

Dependency order: U1 → {U2, U4, U5} → U3 → U6. Each unit is independently landable and testable.

### U1. `models.json` registry + registry-derived MODELS/EFFORTS

Create `plugins/fleet-core/scripts/fleet_commons/models.json` — one row per model with an explicit
integer `rank` and an `effort_ceiling`, one row per effort with an explicit `rung`. Refactor
`tier_palette.py` to derive `MODELS`/`EFFORTS` from the registry at import (strongest-first / weakest-first
per the existing docstring contract), replacing the hand-ordered literal tuples while keeping the public
names and `model_rank`/`effort_rank` API identical.

**Effort-ceiling anchor (confirm before locking — finding C):** the issue's canonical unsupported example
is `haiku`/`xhigh`, which fixes `haiku`'s `effort_ceiling` at `high`; the other three models default to
`xhigh` (full range) unless build-time evidence narrows them. These ceiling values are load-bearing data —
verify them at build rather than treating this default as settled fact.

**AC9 resolution (finding H):** the re-export at `execution_spec.py:61-62` satisfies AC9's *intent* (no
inline tuple) but AC9's grep `^MODELS = ` still matches the alias line. Either tighten AC9's check to a
tuple-literal pattern (e.g. `^MODELS = \(`) or record the re-export as compliant — do not report AC9
"passing" against its unmodified grep.

**Files:** `plugins/fleet-core/scripts/fleet_commons/models.json` (new),
`plugins/fleet-core/scripts/fleet_commons/tier_palette.py` (refactor `:21,24`).

**Failure modes:** empty registry; duplicate ranks; a rank gap; a model row missing `effort_ceiling`;
registry file missing at import. Each must fail loudly at import, never produce a silently mis-ordered tuple.

**Test scenarios (`tests/test_tier_vocab_single_source.py`):** `test_registry_rank_order` — derived tuple
order equals registry `rank`/`rung` order; a scratch mis-ranked row (opus↔haiku swap) reds it. Import-time
validation raises on duplicate/gapped rank and on a missing `effort_ceiling`.

### U2. Ladder ops + effort-ceiling clamp, `segment_units()` refactor

Add `escalate(tier, steps=1)`, `downgrade(tier, steps=1)`, `clamp(tier, floor=None, ceiling=None)` to
`tier_palette.py`, each honoring the ordering contract; `escalate`/`clamp` consult the per-model
`effort_ceiling` (R3/KTD3) and surface a clamp as a returned note, never silently. Refactor
`segment_units()` (`execution_spec.py:1600-1601`) to call these instead of inlining
`min(MODELS.index(...))`/`max(EFFORTS.index(...))`.

**Files:** `plugins/fleet-core/scripts/fleet_commons/tier_palette.py` (ladder ops),
`plugins/saga/scripts/execution_spec.py` (`segment_units` refactor).

**Failure modes:** escalate past the strongest model/effort (must no-op, not raise); downgrade past the
weakest (no-op); `clamp` with floor > ceiling; clamping `haiku` toward `xhigh` (resolves to haiku's real
ceiling with a surfaced note).

**Test scenarios (`tests/test_tier_vocab_single_source.py`):** `test_ladder_ops_bounds` (escalate/downgrade/
clamp bounds, past-strongest no-op); `test_effort_ceiling_clamp` (haiku/xhigh clamps to haiku's ceiling
with a note). **Regression:** `tests/test_team_emitter.py::test_segment_tier_merge_prefers_fable_and_xhigh`
must stay green against the refactored `segment_units()`.

### U3. Unsupported-combo HALT in `validate()` + ladder-monotonicity guard

Extend `Tier.validate()` (`execution_spec.py:409`) so an effort exceeding the model's `effort_ceiling`
raises `SpecError` for a Claude teammate; exclude engine/capability chaperone units (KTD4). Add a
parametrized ladder-monotonicity test over all adjacent `MODELS`/`EFFORTS` pairs (R5).

**Files:** `plugins/saga/scripts/execution_spec.py` (`Tier.validate`),
`tests/test_tier_vocab_single_source.py`.

**Failure modes:** `haiku`/`xhigh` on a Claude worker (must HALT); the same combo on an engine-owned
chaperone unit (must be allowed — excluded); a valid at-ceiling combo (`haiku`/ceiling) must pass.

**Test scenarios:** `test_unsupported_combo_halts` (asserts a typed non-zero failure, not a silent clamp;
plus the engine-unit exclusion passes); `test_ladder_monotonicity` (parametrized; swapping opus/haiku in a
scratch registry copy fails it).

### U4. Repo-wide bare-literal drift guard

New guard test asserting no bare model/effort literal appears **as a tier value** in the dispatch-logic
Python surface outside the canonical home (`tier_palette.py`, `models.json`) and its re-export shim
(`fleet_commons_shim.py`). **Scan surface is Python only** — the 33 agent-frontmatter `.md` `model:`
literals are the explicitly deferred non-goal and are OUT of the guard's scope.

**The exact scan surface + exception rule is the load-bearing decision of this unit (finding A, P1).** A
naive "any string containing `opus`" guard collides with ~205 legitimate Python occurrences — e.g.
`team_emitter.py:53-56` uses model names as dict *keys* in a work-shape map, and tests/registries name
models as data. The guard must target vocabulary-defining / tier-value literals in dispatch logic, not
incidental model-name mentions, and must be anchored on the AC's own example (a bare literal reintroduced
into `execution_spec.py` reds it). Pin this surface before writing the guard.

**Files:** `tests/test_tier_vocab_single_source.py` (new guard); any dispatch-logic source the guard flags.

**Failure modes:** a bare `"opus"` reintroduced into `execution_spec.py` must red the guard; a model name
used as a work-shape dict key (`team_emitter.py`) or an English mention in a docstring must not (the rule
must be precise, not a blanket skip that guts the guard, nor a broad scan that drowns in the 205 sites).

**Test scenarios:** `test_no_bare_model_literals_outside_module` — red when a bare literal is injected into
a scanned source file, green on the merged tree.

### U5. Team-execution vocabulary sync guard + onboarding runbook

Extend the existing render/sync mechanism (KTD5) to guard the tier vocabulary the team-execution SKILL.md
displays against the catalog, and write `plugins/fleet-core/references/tier-palette.md` — an onboarding
runbook for adding a model/effort that encodes the `{#tier-vocab-ordering}` rule as an explicit step.

**Files:** `plugins/fleet-core/references/tier-palette.md` (new); the render/check helper
(extend `render_tier_table.py` or a sibling); `plugins/team-execution/skills/team-execution/SKILL.md`
(only if a displayed vocabulary token must change to match the catalog); `tests/test_tier_vocab_single_source.py`.

**Failure modes:** a scratch edit that diverges a displayed tier token in team-execution SKILL.md from the
catalog must fail `--check`; the runbook's mis-insertion example must actually red the ordering guard.

**Test scenarios:** `test_tier_catalog_check` (team-execution vocabulary drift fails the check);
`test_onboarding_guard` (mis-inserting a fake `"model6"` at the wrong rank reds it).

### U6. Release surfaces

Bump fleet-core `plugin.json`/`CHANGELOG.md` + the marketplace entry (new module/registry/runbook) **AND**
saga `plugin.json`/`CHANGELOG.md` — U2/U3 change `execution_spec.py` behavior (the `segment_units` refactor
and the new `Tier.validate` HALT are shipped saga changes, not internal-only). Bump team-execution only if
U5 edits its shipped `SKILL.md`. Move any drift-guard version pins in lockstep.

**Files:** `plugins/fleet-core/.claude-plugin/plugin.json`, `plugins/fleet-core/CHANGELOG.md`,
`.claude-plugin/marketplace.json`; conditionally saga/team-execution surfaces; any metadata drift-guard
test pins.

**Test expectation:** the repo's existing marketplace/plugin-metadata drift tests stay green against the
bumps; `release_surface_diff_guard` passes against the committed diff. Feature behavior is covered by U1–U5;
this unit is release-metadata only.

## Scope Boundaries

**In scope:** one canonical vocabulary module (extended, per KTD1) + `models.json` registry, ladder
operations, per-model effort ceilings, the drift guards (R5/R6/R7), the team-execution vocabulary sync
guard (R8), and the onboarding runbook.

**Deferred to follow-up work (explicitly out of scope):**

- Wiring per-teammate effort overrides into team-execution's spawn path end-to-end
  (`{#team-execution-per-teammate-effort}`) — this issue builds the registry data + the validate-halt the
  spawn path will later consume, not the plumbing (that is sub-368 / a separate leaf).
- Migrating the 25+ agent-frontmatter `model:` literals to read from the registry — a mechanical
  fleet-wide edit better scoped once the registry is stable.
- Any external-engine/chaperone-dispatch tier behavior — engine workers stay pinned to chaperone tiers
  (#318) and are excluded from the AC6 ceiling check.

**True non-goals:** introducing new models/efforts beyond the current four-model/four-effort vocabulary —
this ships the *mechanism* for future additions (runbook + guards), not a vocabulary expansion.

## Notes for the reviewer

The headline decision to ratify is **KTD1** (extend `tier_palette.py` in fleet-core rather than create
`tier_vocab.py` in saga as the stale issue literally says). Everything downstream — file locations,
release surface (fleet-core, not saga), and the "AC9 done / AC8 half-done" reframing — follows from it.
