---
title: Spend-delta machinery — silent-cheap/ask-expensive classifier, worth-it receipts, relative lever, spend authority
type: feat
status: active
date: 2026-07-06
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/367
---

# Spend-delta machinery — classifier, worth-it receipts, relative lever, spend authority

## Summary

Give `/plan` and `/work` one shared primitive for reasoning about tier-spend *direction*, then use it to
close four gaps: a `spend_delta(old, new) -> {cheapen | escalate | lateral}` classifier (the three-way
generalization of the existing `is_escalation`), a `validate()` hard-block requiring any above-baseline
tier to carry a `worth_it_because` justification + a named `cheaper_fallback`, a relative
`adjacent_tier(tier, direction)` lever (one notch cheaper/dearer), and an optional
`.saga/spend-authority.json` matrix configuring the silent/ask split. Backend `inline`. This is the
**final leaf** `sub-367` of `tier-effort-first-class` — merging it completes the outcome (9/9).

## Problem Frame

Tier changes are proposed, justified, approved, and recorded ad hoc. `is_escalation(old, new)`
(`execution_spec.py:1703`, #365) already answers the *two-way* "is this up-ladder?" but nothing answers
the *three-way* "cheaper, dearer, or a sideways trade?" — so every lever that needs "is this more or
less expensive?" hand-rolls its own notion. Premium tiers (`opus`/`fable`, `high`/`xhigh`) can ship with
no justification and no named cheaper fallback. Overriding a proposed tier forces an absolute re-pick
from the full `MODELS × EFFORTS` enum rather than "one notch cheaper." And the silent-cheap/ask-expensive
rule lives only in intake prose, not in any per-repo config.

Two primitives already exist to build on: `is_escalation` (the escalate half) and
`cheaper_fallback(model, effort)` (`tier_resolver.py:92`, #362 — "one rung down, model-first, floor is a
no-op"). The codebase now **forbids raw `MODELS.index()`** (`execution_spec.py:1684,2157`); all ordering
reasoning goes through the #370 named palette ops (`model_rank`/`effort_rank`/`stronger`/`escalate`).

## Requirements

- **R1.** `spend_delta(old: Tier, new: Tier) -> Literal["cheapen","escalate","lateral"]`: `escalate`
  when `new` is strictly stronger on ≥1 axis and weaker on none; `cheapen` when strictly weaker on ≥1
  axis and stronger on none; `lateral` for a mixed/sideways trade (stronger on one axis, weaker on the
  other) or an identical tier. Built on the named palette ops (`stronger`), never raw `.index()`.
- **R2.** `spend_delta` and `is_escalation` **share** a `_axis_deltas(old, new) -> (dm, de)` helper (each
  axis's strength direction ∈ {-1, 0, +1}, via the palette `stronger` op) — the real DRY win. But
  `is_escalation` keeps its **exact current semantics** (True iff stronger on *either* axis: `dm > 0 or
  de > 0`); it is **NOT** redefined as `spend_delta == "escalate"`. The two differ on purpose: a *mixed*
  move (stronger model, weaker effort) is `is_escalation == True` but `spend_delta == "lateral"`, and an
  *identical* tier is `is_escalation == False` but `spend_delta == "lateral"`. A grid guard test asserts
  `is_escalation` is unchanged from its pre-#367 definition, so #365's `/tier` gate is behavior-preserved.
- **R3.** `adjacent_tier(tier: Tier, direction: Literal["cheaper","dearer"]) -> Tier`: one notch along
  the ladder. `cheaper` reuses `tier_resolver.cheaper_fallback` (model-first); `dearer` is the symmetric
  one-rung-up via `escalate` (model-first). **Boundary calls raise** (cheapest→cheaper, dearest→dearer),
  never clamp or wrap — the issue's explicit contract.
- **R4.** `Unit` gains optional `worth_it_because: str` and `cheaper_fallback: Tier | None`.
  `validate(require_receipts=True)` **hard-blocks** any unit whose tier is **premium**
  (`is_escalation(SPEND_BASELINE=sonnet/high, tier)` is True — an opus/fable model or xhigh effort) and
  is missing `worth_it_because` OR whose `cheaper_fallback` is absent / not strictly cheaper
  (`spend_delta(tier, cheaper_fallback) != "cheapen"`). A non-premium tier needs neither. The check is
  **gated on `require_receipts`** (default off), enforced at the `/plan` authoring boundary, NOT on the
  unconditional `validate()` that emit and existing specs re-run (KTD8). Engine-owned (chaperone-dispatch)
  units are exempt — their tier is pinned by intent, not an operator choice.
- **R5.** Both new `Unit` fields round-trip **byte-identical** when absent (the `min_tier`/#366 precedent).
- **R6.** A `.saga/spend-authority.json` matrix + resolver stamps each unit `silent` or `ask`. The matrix
  configures a `silent_ceiling` tier: a unit tier that `is_escalation(silent_ceiling, tier)` → `ask`,
  else `silent`. **Absent file → default `silent_ceiling = sonnet/medium`**, so anything above the
  baseline resolves to `ask` (the safe side). Malformed matrix → loud error, never a silent default.
- **R7.** `plan/SKILL.md`'s override step offers the three-way relative choice
  (`cheaper` / `as-proposed` / `dearer`) via `adjacent_tier`, in place of an absolute re-pick, and
  documents the `worth_it_because` / `cheaper_fallback` authoring + the spend-authority stamp.
- **R8.** Release surface synced: saga `0.69.0 → 0.70.0` (plugin.json, marketplace, CHANGELOG, pin),
  `execution-spec.md` doc, DECISIONS entry. **No fleet-core change** (spend_delta/adjacent_tier are
  Tier-typed and live in saga; `cheaper_fallback` is reused, not modified).
- **R9.** Full gate green (pytest, ruff format+check, mypy, bandit-ll) **and** the diff-aware
  release-surface guard (`release_surface_diff_guard.py`) run against committed state before push
  (per LEARNINGS `{#fleet-core-release-surface-own-bump}`).

## Key Technical Decisions

**KTD1 — `spend_delta` is per-axis ordering (three-way), NOT `to_spend` magnitude.** The `lateral`
bucket exists for sideways axis trades (stronger model + weaker effort). `to_spend` (#366) is a *total
order* and — because the 16 cost-weight cells are all distinct — is injective, so `to_spend(a)==to_spend(b)`
is never true and a magnitude-based classifier could never yield `lateral`. A three-way classifier
therefore requires per-axis ordering via `stronger`, exactly what `is_escalation` already uses. `to_spend`
answers "how much?"; `spend_delta` answers "which way?" — different questions, different primitives.

**KTD2 — `spend_delta` and `is_escalation` share the axis-delta computation, but `is_escalation` is NOT
redefined as a `spend_delta` alias (doc-review P1).** They both compute per-axis strength direction via a
shared `_axis_deltas` helper (the DRY win), but the predicates genuinely differ: `is_escalation` = "up on
*either* axis" (a two-way "should the `/tier` gate ask?" check), whereas `spend_delta == "escalate"` =
"up on ≥1 axis and *down on none*". They diverge on mixed moves (is_escalation True / spend_delta lateral)
and identical tiers (is_escalation False / spend_delta lateral). Redefining `is_escalation` as
`spend_delta == "escalate"` would flip it False on every sideways trade and silently regress #365's `/tier`
confirmation gate — so `is_escalation` keeps its exact semantics; a grid guard test asserts it is unchanged.

**KTD3 — `spend_delta` + `adjacent_tier` live in `execution_spec.py`, not fleet_commons.** They are
`Tier`-typed (the `Tier` dataclass lives in `execution_spec`), and they sit beside `is_escalation` which
they generalize. `adjacent_tier("cheaper")` reuses `tier_resolver.cheaper_fallback` (fleet_commons, via
the shim) so the down-rung logic is not duplicated; `dearer` uses `tier_palette.escalate`. This keeps
#367 saga-only — no fleet-core release-surface bump.

**KTD4 — `adjacent_tier` raises at boundaries; `cheaper_fallback`'s floor no-op becomes a raise.**
`cheaper_fallback` returns the same tier at the ladder floor (a no-op). `adjacent_tier` detects that
no-op (result == input) and raises instead — the issue's "boundary calls raise rather than silently
clamping/wrapping." `dearer` raises symmetrically at the ceiling.

**KTD5 — one shared `sonnet/high` baseline for BOTH the worth-it hard-block and the spend-authority
default.** The hard-block triggers on `is_escalation(SPEND_BASELINE, tier)` and the absent-matrix
spend-authority default is `silent_ceiling = SPEND_BASELINE`, with `SPEND_BASELINE = sonnet/high`. Same
tier, same `is_escalation` predicate — the two levers cannot disagree about what "premium" means. **The
baseline is `sonnet/high`, not `sonnet/medium`** (KTD9): the issue's premium set "(opus, fable, xhigh in
either axis)" — which omits `high` — is authoritative over its own "sonnet/medium baseline" phrasing, and
`is_escalation(sonnet/high, tier)` yields *exactly* that set. A `sonnet/high` baseline avoids
retroactively flagging common `sonnet/high` units.

**KTD8 — the worth-it hard-block is `require_receipts`-gated, not unconditional (implementation-forced).**
The issue's AC says "fails `validate()`" but its non-goal says "no retroactive backfill — the rule applies
to newly authored/validated specs going forward." An unconditional `validate()` check contradicts the
non-goal (it runs on every emit and every existing spec — 75 emitter tests fail). Resolution: the check
is a `validate(require_receipts=True)` gate that `/plan` sets at authoring; `emit()` and existing specs
call the default `validate()` unchanged. This satisfies the AC's intent (premium tiers gated at authoring)
without the retroactive break. Interaction: `/tier`-patching (#365) a unit up to a premium tier also runs
through the authoring gate when re-validated with receipts required, so a patch-to-premium must carry
receipts — a deliberate extension of the rule to that lever.

**KTD9 — see KTD5:** `SPEND_BASELINE = sonnet/high`.

**KTD6 — `.saga/spend-authority.json` is a `silent_ceiling` tier, not a per-tier enumeration.** Modeled
on a signature-authority limit ("authorized silently up to tier X"), it is one tier the resolver
compares against via `is_escalation`. Simpler than a 16-cell map, and it composes with the same ordering
primitive. Absent → `sonnet/medium`; malformed (bad JSON, off-palette, unrunnable tier) → loud
`SpendAuthorityError` (the `tier_defaults.py` #368 precedent).

**KTD7 — test placement:** `spend_delta` + `adjacent_tier` → new `tests/test_spend_delta.py`; the
`validate()` worth-it hard-block → existing `tests/test_saga_execution_spec.py` (beside the other spec
validate tests); spend-authority → new `tests/test_spend_authority.py`. The issue's
`tests/test_execution_spec.py` does not exist (the #364/#366 reconciliation). AC `-k` selectors
(`spend_delta`, `worth_it_fallback`, `adjacent_tier_boundary`, `spend_authority_matrix`,
`spend_authority_absent_default`) become test-name fragments.

## Implementation Units

### U1. `spend_delta` classifier + `is_escalation` refactor

The shared three-way direction primitive.

**Scope:** Add a shared `_axis_deltas(old, new) -> (dm, de)` helper (per-axis strength direction via
`_tier_palette.stronger`, no raw `.index()`). Add `spend_delta(old, new) -> Literal[...]` on top of it
(KTD1). Refactor the existing `is_escalation` to compute `dm, de` from the same helper but keep its exact
predicate `dm > 0 or de > 0` (KTD2 — NOT a `spend_delta` alias). No raw `.index()`.

**Files:** `plugins/saga/scripts/execution_spec.py`.

**Test scenarios (`tests/test_spend_delta.py`, new):**
`test_spend_delta_escalate_both_axes` — `sonnet/medium → opus/high` == `escalate`.
`test_spend_delta_cheapen_both_axes` — `opus/high → sonnet/low` == `cheapen`.
`test_spend_delta_lateral_transposition` — a sideways trade (`opus/low → sonnet/xhigh`) == `lateral`.
`test_spend_delta_identical_is_lateral` — same tier == `lateral`.
`test_is_escalation_unchanged_over_grid` — for every ordered tier pair, `is_escalation(a,b)` equals its
pre-#367 definition (stronger on either axis), AND is True on a mixed move where `spend_delta` is
`lateral` (proving the two predicates are deliberately distinct, R2 behavior-preservation).

### U2. `adjacent_tier` relative lever

One notch cheaper/dearer, boundary-raising.

**Scope:** Add `adjacent_tier(tier, direction)` in `execution_spec.py`. `cheaper` reuses
`tier_resolver.cheaper_fallback` (loaded via the shim) + boundary-raise; `dearer` uses
`_tier_palette.escalate` (model-first) + boundary-raise (KTD3/KTD4).

**Files:** `plugins/saga/scripts/execution_spec.py`.

**Test scenarios (`tests/test_spend_delta.py`, new):**
`test_adjacent_tier_cheaper_and_dearer_mid_ladder` — a mid-ladder tier steps one rung each way, and each
result classifies `cheapen`/`escalate` respectively vs the original.
`test_adjacent_tier_boundary_raises` — cheapest tier `.cheaper` and dearest tier `.dearer` both **raise**
(not clamp/wrap).
`test_adjacent_tier_cheaper_matches_cheaper_fallback` — `adjacent_tier(t,"cheaper")` agrees with
`tier_resolver.cheaper_fallback` off the floor.

### U3. `worth_it_because` + `cheaper_fallback` validate hard-block

Premium spend is self-justifying and one documented downgrade away.

**Scope:** Add optional `Unit.worth_it_because: str` and `Unit.cheaper_fallback: Tier | None`
(from_dict/to_dict/round-trip byte-identical absent, R5). In `Unit.validate`, when
`is_escalation(Tier("sonnet","medium"), self.tier)` is True, require a non-empty `worth_it_because` and a
`cheaper_fallback` with `spend_delta(self.tier, cheaper_fallback) == "cheapen"` — else `SpecError`
(KTD5). Note: the `Unit.cheaper_fallback` *field* (a named Tier the author declares) shares a name with
`tier_resolver.cheaper_fallback` the *function* (which computes the one-rung-down default) — deliberate
(the field names what the function would suggest), but keep the distinction clear in code comments so the
implementer does not conflate the two.

**Files:** `plugins/saga/scripts/execution_spec.py`.

**Test scenarios (`tests/test_saga_execution_spec.py`, existing):**
`test_worth_it_fallback_required_above_baseline` — an `opus/high` (or `fable/xhigh`) unit missing
`worth_it_because` OR `cheaper_fallback` fails `validate()`; the same unit with both present and a
genuinely cheaper fallback passes.
`test_worth_it_fallback_not_required_at_baseline` — a `sonnet/medium` (or below) unit needs neither.
`test_worth_it_fields_absent_roundtrip` — a spec with neither field round-trips byte-identical.
`test_cheaper_fallback_not_actually_cheaper_fails` — a `cheaper_fallback` that isn't strictly cheaper
(`lateral`/`escalate`) fails validate.

### U4. `.saga/spend-authority.json` resolver

The silent/ask split as per-repo config, safe default.

**Scope:** Add `plugins/saga/scripts/spend_authority.py` mirroring `tier_defaults.py`: `SILENT_CEILING`
default `sonnet/medium`; `load_spend_authority(path=None)` reading `.saga/spend-authority.json`
(`{"silent_ceiling": {"model","effort"}}`), absent → default, malformed → `SpendAuthorityError`;
`resolve_spend_authority(tier, ceiling) -> "silent"|"ask"` = `ask` iff `is_escalation(ceiling, tier)`.

**Files:** `plugins/saga/scripts/spend_authority.py` (new).

**Test scenarios (`tests/test_spend_authority.py`, new):**
`test_spend_authority_matrix` — a populated matrix (`silent_ceiling = opus/high`) partitions a mixed-tier
set into the exact expected `{silent, ask}` (opus/high and below → silent; fable or xhigh above → ask).
`test_spend_authority_absent_default` — no file → every above-`sonnet/medium` tier resolves `ask`, never
`silent`.
`test_spend_authority_malformed_fails_loud` — bad JSON / off-palette / unrunnable ceiling → raises.

### U5. `plan/SKILL.md` override step + authoring docs

Producer/consumer wiring so the fields aren't dead-wired.

**Scope:** In `plan/SKILL.md` (the §5.2a tier-table area / the `/tier` mid-run lever), add the three-way
relative override (`cheaper` / `as-proposed` / `dearer`) computed by `adjacent_tier`, and document
authoring `worth_it_because` + `cheaper_fallback` for above-baseline units and the spend-authority
silent/ask stamp. Reference `spend_delta` as the shared classifier.

**Files:** `plugins/saga/skills/plan/SKILL.md`.

**Test expectation:** `none -- skill-doc wiring, covered by the U1-U4 primitive tests its prose points at`
(update `tests/test_saga_docs_coverage.py` only if it guards the changed section).

### U6. Release surface + journal

Installed metadata matches the diff (CLAUDE.md step 6 + the fleet-core lesson).

**Scope:** saga `0.69.0 → 0.70.0` (plugin.json, `sync_marketplace.py`, CHANGELOG, `test_saga_plugin.py`
pin); `execution-spec.md` documents `spend_delta`/`adjacent_tier`/the worth-it hard-block/spend-authority;
DECISIONS `{#spend-delta-machinery-367}`. Run `release_surface_diff_guard.py` (committed) before push —
confirm **only saga** changed, so only saga bumps.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`, `plugins/saga/references/execution-spec.md`,
`docs/engineering-journal/DECISIONS.md`.

**Test scenarios:** `tests/test_saga_plugin.py` version-pin + marketplace-parity pass at `0.70.0`.

## Dependency Order

`U1` (spend_delta) → `U2` (adjacent_tier uses spend_delta in tests), `U3` (hard-block uses spend_delta +
is_escalation), `U4` (resolver uses is_escalation). `U1-U4` → `U5` (docs reference all). `U5` → `U6`
(release last).

## Scope Boundaries

**Out of scope (true non-goals):**

- No UI/approval-prompt implementation for the `ask` path — #367 delivers the classification + the
  spec-level `silent`/`ask` stamp; how an ask is surfaced (single vs batched prompt) is a follow-on.
- No retroactive backfill of `worth_it_because`/`cheaper_fallback` onto existing plan artifacts — the
  hard-block applies to newly authored/validated specs going forward.
- No change to the emitted `.workflow.js` runtime path beyond consuming the fields already on the spec.
- No `team-execution` markdown-emitter change.
- No global/cross-repo authority registry beyond the single `.saga/spend-authority.json`.
- No `to_spend`-magnitude spend_delta (KTD1) and no new fleet_commons primitive — `cheaper_fallback` is
  reused as-is.

**Deferred to Follow-Up Work:** none — this is the final outcome leaf; the mechanism is complete.

## Verification

```bash
uv run pytest tests/test_spend_delta.py tests/test_spend_authority.py tests/test_saga_execution_spec.py \
  -k "spend_delta or adjacent_tier_boundary or worth_it_fallback or spend_authority or is_escalation" -v
uv run pytest && uv run ruff format --check . && uv run ruff check . && \
  uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run python tools/release_surface_diff_guard.py --base-ref $(git merge-base origin/main HEAD)
```

Expected: all green; each AC `-k` selector resolves; the diff-guard confirms only saga's surface moved.
