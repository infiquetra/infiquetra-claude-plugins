---
title: "capability: single-source tier palette (tier_vocab module, models.json registry, ladder ops, drift-proofing)"
repo: infiquetra-claude-plugins
type: capability
tier: structural
objective: "Make tier+effort a first-class priced resolvable lever"
wave: wave-1
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
executor_profile: {model: sonnet, effort: high, backend: inline, external_llm: none}
---

# capability: single-source tier palette (tier_vocab module, models.json registry, ladder ops, drift-proofing)

### Intent
Extract the fleet's model/effort vocabulary — today a single hardcoded pair of tuples in
`plugins/saga/scripts/execution_spec.py:52-53` that every other surface (the `/plan` tier table,
the team-execution worker table, 25 agent-frontmatter `model:` literals) re-derives or hand-copies —
into one canonical, registry-backed module that the rest of the fleet imports. Add named ladder
operations (`escalate`/`downgrade`/`clamp`) on top of it, encode per-model effort ceilings as data,
and wire drift guards so the palette can only grow through one file, not a fleet-wide manual sweep.

## Problem / Motivation

- **Single source of vocabulary truth, but not enforced.** `MODELS = ("fable", "opus", "sonnet",
  "haiku")` and `EFFORTS = ("low", "medium", "high", "xhigh")` are defined once, in
  `plugins/saga/scripts/execution_spec.py:52-53`, with an explicit load-bearing ordering contract
  in the comment directly above them (`execution_spec.py:49-51`: "ORDERING IS LOAD-BEARING:
  `segment_units()` merges tiers upgrade-only via `min(MODELS.index)` / `max(EFFORTS.index)`, so
  MODELS is strongest-first and EFFORTS is weakest-first"). Nothing stops a second bare literal
  from appearing anywhere else in the fleet.
- **The vocabulary is already re-typed as English in two operator-facing tables** that must be
  hand-kept in sync with the code tuples: the `/plan` per-unit tier table
  (`plugins/saga/skills/plan/SKILL.md:298-304`) and the team-execution Step A7 worker table
  (`plugins/team-execution/skills/team-execution/SKILL.md:226-234`). Per the grounding brief's
  Corrections intake (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §1/`ENGINE_INTENTS`
  producer/consumer note): this producer/consumer pair is authored in one file and rendered in
  another with no sync check.
- **`fable`/`xhigh` are unreachable outside the saga plan vocabulary** — confirmed in the same
  grounding brief (§1, "Model/effort reality"): every agent frontmatter across all 8 plugins
  hardcodes a `model:` literal (opus/sonnet/haiku) with zero `effort:` fields, and there is no
  dispatch-time override lever anywhere except saga's readonly-verifier per-call pattern.
- **The ordering contract already bit the fleet once.** `docs/engineering-journal/LEARNINGS.md:164`
  (`{#tier-vocab-ordering}`) documents that enabling `fable`/`xhigh` for issue #285 looked like
  "append two tuple entries" but a wrong insertion point would have silently mis-tiered every merge
  through `segment_units()`'s `min(MODELS.index(...))` / `max(EFFORTS.index(...))` arithmetic
  (`execution_spec.py:1474-1475`); the only guard today is one example test,
  `test_segment_tier_merge_prefers_fable_and_xhigh` (`tests/test_team_emitter.py:473`). The
  learning's generalizable rule — "grep for `.index(` before extending a closed vocabulary; a tuple
  used for membership and ordering has two contracts" — is not yet encoded as a standing guard.
- **Per-model effort reachability is unvalidated.** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  §5 cites the QUEUED seed `{#team-execution-per-teammate-effort}`: "Haiku may clamp the top
  effort tiers; verify per-model effort support when built." Today nothing encodes or enforces
  this — a per-teammate override to `haiku`/`xhigh` would silently resolve to an unrunnable
  combination instead of halting.
- **Consumer-side evidence of exactly this drift class already exists.** The grounding brief §3
  cites a real contract-mirror drift incident (`card_validator.py`, issue #222) where a
  hand-copied schema drifted from its source — the same failure shape this issue prevents for the
  tier vocabulary.

## Definition of Done

Merged PR(s) delivering:

1. `plugins/saga/scripts/tier_vocab.py` — the ordered `MODELS`/`EFFORTS` tuples plus the
   ORDERING-IS-LOAD-BEARING contract as a module docstring, imported by `execution_spec.py` (no
   re-declaration).
2. `plugins/saga/scripts/models.json` — a registry with one row per model (explicit integer
   `rank`) and one row per effort (explicit `rung` index) plus a per-model `effort_ceiling` field;
   `tier_vocab.py` derives `MODELS`/`EFFORTS` from this registry at import time instead of hand
   ordering them in code.
3. `escalate(tier, steps)`, `downgrade(tier, steps)`, `clamp(tier, floor, ceiling)` named ladder
   operations in `tier_vocab.py`, each honoring the ordering contract and each including a bound
   test (escalate past the strongest rung is a no-op, not an error); `segment_units()` in
   `execution_spec.py` refactored to call these instead of inlining
   `min(MODELS.index(...))`/`max(EFFORTS.index(...))`.
4. A `MODEL_EFFORT_SUPPORT` matrix (or equivalent `effort_ceiling`-consulting `clamp()`/`escalate()`
   path) that makes an unsupported `{model, effort}` combination (e.g. `haiku`/`xhigh`) fail
   `validate()` loudly instead of silently clamping or running unrunnable.
5. A repo-wide drift-guard test asserting zero bare model-literal strings (`"opus"`, `'haiku'`,
   `"fable"`, `"sonnet"`, and effort literals) outside `tier_vocab.py`/`models.json`.
6. A `tier_catalog --check` mode (or equivalent CI-collected test) asserting the `/plan` tier table
   (`plugins/saga/skills/plan/SKILL.md`) and the team-execution worker table
   (`plugins/team-execution/skills/team-execution/SKILL.md`) match the catalog data, so the two
   hand-maintained operator-facing tables cannot silently drift from the code vocabulary.
7. `plugins/saga/references/tier-palette.md` — an onboarding runbook for adding a new model/effort,
   encoding the `{#tier-vocab-ordering}` generalizable rule as an explicit step ("grep for
   `.index(` on the tuple before extending it").
8. Release-surface updates (see checklist below) reflecting the new module/registry as a
   fleet-behavior change.

Verify: guard tests red before extraction (confirming they actually catch the drift class), green
after; `test_segment_tier_merge_prefers_fable_and_xhigh` (`tests/test_team_emitter.py:473`) still
passes against the registry-derived tuples; a deliberately mis-inserted fake model in the registry
fails the ordering guard.

### Acceptance criteria
- [ ] **AC1 (T3-F1-1).** Zero bare model-literal strings exist outside `tier_vocab.py`/`models.json`.
  Check: the drift-guard test fails when a bare literal is temporarily reintroduced into
  `execution_spec.py`, and passes on the merged tree —
  `uv run pytest tests/test_tier_vocab_single_source.py -k no_bare_literals` → passes.
- [ ] **AC2 (T3-F4-2).** `MODELS`/`EFFORTS` are derived from `models.json`'s explicit `rank`/`rung`
  fields, not hand-ordered in code; inserting a fake model row at an incorrect rank makes the
  ordering guard fail. Check: `uv run pytest tests/test_tier_vocab_single_source.py -k
  registry_rank_order` → passes on correct data, fails when a scratch test mis-ranks a row.
- [ ] **AC3 (T3-F4-4).** `escalate()`/`downgrade()`/`clamp()` exist as named, tested operations honoring
  ladder bounds (escalate past the strongest model/effort is a no-op, not an error), and
  `segment_units()` calls them instead of inlining index arithmetic. Check: `uv run pytest
  tests/test_tier_vocab_single_source.py -k ladder_ops` and existing
  `tests/test_team_emitter.py -k test_segment_tier_merge_prefers_fable_and_xhigh` both pass.
- [ ] **AC4 (T3-F1-7).** `plugins/saga/references/tier-palette.md` onboarding runbook exists and a
  parametrized ordering/`.index(`-coverage guard test fails when a new model is mis-inserted at
  the wrong rank, and passes on a correct prepend. Check: `uv run pytest
  tests/test_tier_vocab_single_source.py -k onboarding_guard` → passes; manually mis-inserting a
  fake `"model6"` at the wrong index reds it.
- [ ] **AC5 (T3-F4-8).** Each model in `models.json` carries an `effort_ceiling`; `clamp()`/`escalate()`
  consult it so escalating a `haiku` unit toward `xhigh` resolves to `haiku`'s real ceiling (not an
  unrunnable tier), with the clamp surfaced as a note rather than silent. Check: `uv run pytest
  tests/test_tier_vocab_single_source.py -k effort_ceiling_clamp` → passes.
- [ ] **AC6 (T3-F6-6).** A `MODEL_EFFORT_SUPPORT` matrix (or ceiling-derived equivalent) makes
  `validate()` halt loudly on an unsupported `{model, effort}` combination assigned to a Claude
  teammate (e.g. `haiku`/`xhigh`), rather than clamping silently; engine-owned chaperone-dispatch
  workers (per `{#external-engine-chaperone-dispatch}`, issue #318) are excluded from this
  per-teammate override path. Check: `uv run pytest tests/test_tier_vocab_single_source.py -k
  unsupported_combo_halts` → the test asserts a non-zero/typed-failure result, not a silent clamp.
- [ ] **AC7 (T3-F6-5).** A parametrized ladder-monotonicity test asserts, for every adjacent pair in
  `MODELS` and in `EFFORTS`, that `segment_units()`'s merge picks the stronger member. Check:
  `uv run pytest tests/test_tier_vocab_single_source.py -k ladder_monotonicity` → passes; swapping
  `opus`/`haiku` in a scratch copy of the registry fails it.
- [ ] **AC8 (T3-F4-7).** A `tier_catalog` data structure (or equivalent) drives both the `/plan` tier
  table and the team-execution worker table, with a `--check` mode (or CI test) that fails when
  either rendered table drifts from the catalog. Check: `uv run pytest
  tests/test_tier_vocab_single_source.py -k tier_catalog_check` → passes on the merged tree; a
  scratch edit to `plugins/saga/skills/plan/SKILL.md`'s tier table without updating the catalog
  fails `--check`.
- [ ] **AC9.** `execution_spec.py` no longer defines `MODELS`/`EFFORTS` inline — it imports them from
  `tier_vocab.py`. Check: `grep -n '^MODELS = \|^EFFORTS = ' plugins/saga/scripts/execution_spec.py`
  → no match; `grep -n 'from .tier_vocab import\|from tier_vocab import'
  plugins/saga/scripts/execution_spec.py` → match found.

### Out-of-scope / non-goals
**In scope:** one canonical vocabulary module + JSON registry, ladder operations, per-model effort
ceilings, the drift guards enumerated above, the operator-facing tier-table sync check, and the
onboarding runbook.

**Non-goals (deferred, explicitly out of scope for this issue):**
- Wiring per-teammate effort overrides into team-execution's spawn path end-to-end (the QUEUED seed
  `{#team-execution-per-teammate-effort}`'s full feature) — this issue only builds the registry
  data and the validation halt the spawn path will later consume; the spawn-path plumbing itself
  is separate follow-on work.
- Changing agent-frontmatter `model:` literals across the 25+ agent definition files to read from
  the registry — that is a mechanical fleet-wide edit better scoped as its own follow-on once the
  registry is merged and stable.
- Any external-engine/chaperone-dispatch tier behavior — engine workers stay pinned to their
  chaperone tiers per `{#external-engine-chaperone-dispatch}` (#318) and are explicitly excluded
  from the per-teammate override validated by AC6.
- Introducing new models/efforts beyond the current four-model/four-effort vocabulary — this issue
  ships the mechanism for future additions (the runbook + guards), not a vocabulary expansion.

## Grounding References

| Absorbed idea | Basis | Role |
|---|---|---|
| `T3-F1-1` | `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §1 ("fable/xhigh unreachable outside saga plan vocabulary"); `plugins/saga/scripts/execution_spec.py:52-53` (sole MODELS/EFFORTS definition); consumer-side signal §3 (`card_validator.py` contract-mirror drift → #222) | primary |
| `T3-F4-2` | `docs/engineering-journal/LEARNINGS.md:164` `{#tier-vocab-ordering}` — "grep for `.index(` before extending a closed vocabulary; a tuple used for membership and ordering has two contracts" | facet |
| `T3-F4-4` | `plugins/saga/scripts/execution_spec.py:49-53` ordering comment + `segment_units()` merge arithmetic (`:1474-1475`) | facet |
| `T3-F1-7` | `docs/engineering-journal/LEARNINGS.md:164` `{#tier-vocab-ordering}` — evidence `execution_spec.py:49-56`, guard test `test_segment_tier_merge_prefers_fable_and_xhigh` (`tests/test_team_emitter.py:473`) | facet |
| `T3-F6-5` | Same learning; generalizes the single example test into a parametrized ladder-monotonicity invariant over all adjacent pairs | facet |
| `T3-F4-8` | `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §5, QUEUED `{#team-execution-per-teammate-effort}` — "Haiku may clamp the top effort tiers; verify per-model effort support when built" | facet |
| `T3-F6-6` | Same QUEUED seed, extended with a `MODEL_EFFORT_SUPPORT` matrix and HALT-not-degrade behavior; honors `{#external-engine-chaperone-dispatch}` (#318, engine workers excluded) and the `/outcome` campaign's HALT-not-degrade binding | facet |
| `T3-F4-7` | `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §1 Corrections intake — `ENGINE_INTENTS` producer/consumer pair authored in `plan/SKILL.md:303-304`, rendered in `team-execution/SKILL.md:229-233`; org convention of schema-validate-in-CI + `--check` (`context_census.py --check`) per §4 | facet |

**Binding decisions this issue builds on / must not contradict:**
- `{#tier-vocab-ordering}` — tier tuples are ordered escalation ladders, not just closed sets. This
  issue's entire premise operationalizes this decision; it does not revisit it.
- `{#external-engine-chaperone-dispatch}` (#318) — external engines in teams are chaperone dispatch
  only; AC6 explicitly excludes engine-owned workers from the per-teammate override.
- `/outcome` campaign HALT-not-degrade binding — AC6's unsupported-combo behavior is a halt, never
  a silent clamp/degrade.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External LLM:** none
- **Justification:** this is a mechanical-but-careful refactor (extract existing tuples into a
  registry, add named wrapper functions, add guard tests) rather than novel design or adversarial
  judgment — sonnet/high is cost-justified per the fleet's own work-shape heuristic
  (`plugins/saga/skills/plan/SKILL.md`: "Mechanical, deterministic, scripted transforms" →
  `sonnet/medium` or higher for larger bounded surfaces). No external-LLM chaperone dispatch is
  warranted; this stays inline within saga's own script tree.

## Release-Surface Checklist

This issue changes saga's script behavior (new module, new registry file, new CLI-adjacent
`--check` mode) and touches operator-facing skill documentation (`plan/SKILL.md`,
`team-execution/SKILL.md`), so the following must update in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the new tier-vocab
      module/registry and behavior change.
- [ ] `.claude-plugin/marketplace.json` — saga entry version/description kept in sync with the
      plugin.json bump.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the `tier_vocab.py`/`models.json` extraction,
      ladder operations, and drift guards.
- [ ] Drift-guard/version-metadata tests (repo's existing marketplace/plugin-metadata drift tests)
      updated or confirmed still green against the version bump.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` / `CHANGELOG.md` — updated only if the
      `tier_catalog --check` wiring touches `team-execution/SKILL.md`'s rendered table (AC8); if the
      catalog only reads the file for comparison and does not change its content, note "no release
      surface change" explicitly rather than skipping the checklist silently.

## Files Expected to Change

- `plugins/saga/scripts/tier_vocab.py` — new module (MODELS/EFFORTS derivation, ladder ops).
- `plugins/saga/scripts/models.json` — new registry (rank/rung/effort_ceiling data).
- `plugins/saga/scripts/execution_spec.py` — import from `tier_vocab.py`; `segment_units()`
  refactored onto `escalate`/`downgrade`/`clamp`.
- `plugins/saga/scripts/tier_catalog.py` (or equivalent) — new `--check` mode driving both
  operator-facing tables.
- `plugins/saga/references/tier-palette.md` — new onboarding runbook.
- `plugins/saga/skills/plan/SKILL.md` — tier table sourced from `tier_catalog` (no manual drift).
- `plugins/team-execution/skills/team-execution/SKILL.md` — worker table sourced from
  `tier_catalog` (no manual drift).
- `tests/test_tier_vocab_single_source.py` — new drift/ordering/ceiling/support-matrix tests.
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface updates.

## Tests to Add or Update

- `tests/test_tier_vocab_single_source.py::test_no_bare_model_literals_outside_module` — drift
  guard; red before extraction, green after.
- `tests/test_tier_vocab_single_source.py::test_registry_rank_order` — asserts derived tuple order
  equals registry rank order; fails on a scratch mis-ranked row.
- `tests/test_tier_vocab_single_source.py::test_ladder_ops_bounds` — escalate/downgrade/clamp bound
  behavior (escalate past strongest is a no-op).
- `tests/test_tier_vocab_single_source.py::test_ladder_monotonicity` — parametrized over all
  adjacent MODELS/EFFORTS pairs.
- `tests/test_tier_vocab_single_source.py::test_effort_ceiling_clamp` — haiku/xhigh clamps to
  haiku's ceiling with a surfaced note.
- `tests/test_tier_vocab_single_source.py::test_unsupported_combo_halts` — unsupported combo halts
  `validate()` rather than clamping silently.
- `tests/test_tier_vocab_single_source.py::test_tier_catalog_check` — `--check` fails on table
  drift from the catalog.
- `tests/test_team_emitter.py::test_segment_tier_merge_prefers_fable_and_xhigh` — existing test,
  confirmed unchanged and still passing against registry-derived tuples.

### Verification
```bash
# New tier-vocab suite: drift guard, registry ordering, ladder ops, ceilings, support matrix, catalog check
uv run pytest tests/test_tier_vocab_single_source.py -v

# Existing ordering-contract regression stays green against registry-derived tuples
uv run pytest tests/test_team_emitter.py -k test_segment_tier_merge_prefers_fable_and_xhigh

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; deliberately reintroducing a bare model literal or a mis-ranked registry row
turns the corresponding new test red.

## Handoff Maturity

requirements-ready

## Suggested Next Action

Use `/plan <issue>` to create an implementation plan.

## Source Context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T3.json` (ids `T3-F1-1`,
  `T3-F4-2`, `T3-F4-4`, `T3-F1-7`, `T3-F6-5`, `T3-F4-8`, `T3-F6-6`, `T3-F4-7`)
- Source type: ideation survivors + issue-map consolidation
- Source title: Single-source tier palette: tier_vocab module, models.json registry, ladder
  operations, and drift-proofing guards

### Context library links

_none_

### Files expected to change

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/saga/scripts/tier_vocab.py`
- `plugins/saga/scripts/models.json`
- `plugins/saga/skills/plan/SKILL.md`
- `plugins/team-execution/skills/team-execution/SKILL.md`
- `plugins/saga/references/tier-palette.md`
- `plan/SKILL.md`
- `team-execution/SKILL.md`

### Tests to add or update

- `tests/test_team_emitter.py`
- `tests/test_tier_vocab_single_source.py`

### Objective

"Make tier+effort a first-class priced resolvable lever"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/370
- Number: 370
- Created at: 2026-07-04T07:52:12.953449+00:00

