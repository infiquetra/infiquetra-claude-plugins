---
title: "enhancement: collapse deliberate parallel houses into one ordered vocabulary source"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Establish single-source-of-truth for shared primitives"
wave: wave-2
slug: pf-single-vocab-source
---

# enhancement: collapse deliberate parallel houses into one ordered vocabulary source

### Objective
Establish single-source-of-truth for shared primitives (Wave 2 of the plugin-fleet
consolidation).

## Summary

`execution_spec.py` and `outcome_spec.py` each hand-type their own copies of the fleet's
tier vocabulary (`MODELS`, `EFFORTS`, `MUTATION_POLICIES`, `WORKSPACE_ISOLATIONS`,
`SANDBOX_PROFILES`), held in sync only by a cross-module drift-guard test — the module's
own comment calls this a "deliberate parallel house." A third, unguarded copy of the model
tier vocabulary is hand-retyped in prose at `execution-spec.md:138`. This issue collapses
all of that into one ordered vocabulary module (`tier_vocab.py`) that the code modules
import, adds a declarative `drift_pairs` registry so every remaining code↔code and
code↔doc mirror is tested by construction instead of by memory, and — reaching for the
generator end of the same fix — converts the two known rendered-mirror surfaces (the
`/plan` unit-tier table and the team-execution Step A7 worker table) into generated blocks
driven by one fleet registry with a CI check that catches un-regenerated drift.

## Problem Frame

Three escalating instances of the same defect, all rooted in the fleet's habit of hand-
mirroring shared vocabulary instead of sourcing it once:

1. **Code↔code parallel house (guarded, but by a confession).** `execution_spec.py`
   defines `MODELS`, `EFFORTS` (`plugins/saga/scripts/execution_spec.py:50-53`),
   `MUTATION_POLICIES` (`:74`), and `SANDBOX_PROFILES` (`:452` references the tuple).
   `outcome_spec.py` independently retypes `MUTATION_POLICIES`
   (`plugins/saga/scripts/outcome_spec.py:102`), `WORKSPACE_ISOLATIONS` (`:103`), and
   `SANDBOX_PROFILES` (`:104`), with its own comment admitting "the two copies are kept
   identical by a drift-guard test" (`outcome_spec.py:100`, `:125`). A drift TEST is a
   confession that two sources exist where one should — the fix is to delete the second
   source, not to keep testing that it hasn't drifted.
2. **Code↔doc parallel house (currently unguarded).** `execution-spec.md:138` re-types the
   same closed tier vocabulary as prose — `` `fable|opus|sonnet|haiku` `` — with no drift
   test at all. This is exactly the class of stale hand-mirror that let 343 cards pass a
   dead validator in `card_validator.py` (issue #222, cited in the grounding brief §3
   consumer-side finding 1).
3. **Rendered-mirror surfaces (also unguarded, also drift-prone).** The `/plan` unit-tier
   table (`plugins/saga/skills/plan/SKILL.md:296-309`) and the team-execution Step A7
   worker table (`plugins/team-execution/skills/team-execution/SKILL.md:225-235`, further
   detailed in `references/external-engine-workers.md`) are two independently hand-typed
   renderings of the same tier/intent vocabulary. A prior incident already reproduced this
   exact class of drift for `ENGINE_INTENTS`: authored in `plan/SKILL.md:303-304`, rendered
   in the team-execution worker table, per the grounding brief §1 corrections intake item
   (c). Commit `46b7001` shipped yet another one-off, hand-written "registration drift
   guard" for a different pair — the incident-driven, per-pair guard pattern is already
   recurring in this repo rather than being solved once.

The `{#tier-vocab-ordering}` binding decision constrains every remediation here: the tier
tuples are ORDERED escalation ladders (strongest-first `MODELS`, weakest-first `EFFORTS`),
not closed sets — index-based upgrade-only merges depend on that ordering surviving any
refactor.

## Definition of Done

- `plugins/saga/scripts/tier_vocab.py` added as the single ordered source for `MODELS`,
  `EFFORTS`, `MUTATION_POLICIES`, `WORKSPACE_ISOLATIONS`, and `SANDBOX_PROFILES`, preserving
  existing ordering (strongest-first `MODELS`, weakest-first `EFFORTS`) and any
  index-based merge semantics that read from it.
- `execution_spec.py` and `outcome_spec.py` both import these names from `tier_vocab.py`;
  the verbatim tuple/dict literals are deleted from both modules.
- A `drift_pairs` registry (source locator, mirror locator, extractor function) is added,
  registering at minimum: the (now-collapsed) `execution_spec.py`↔`outcome_spec.py` pair
  (kept as a regression guard against reintroduction), the `readonly-verifier` agentType
  literal-consistency pair, and the new `execution_spec.py`↔`execution-spec.md:138`
  code↔doc tier-vocab pair.
- One parametrized `tests/test_fleet_mirror_drift.py` (or equivalent) replaces the ad hoc,
  per-pair hand-written drift tests, asserting every registered pair stays byte-equal (or
  set-equal, per extractor) on the extracted slice.
- A fleet registry artifact (e.g. `fleet/registry.json` or equivalent) plus a render script
  generate the `/plan` unit-tier table block in `plan/SKILL.md` and the team-execution
  Step A7 worker table block in `team-execution/SKILL.md` from one source, with a CI check
  that fails if the rendered block in either file does not match a fresh render.
- Existing test suites (`tests/test_saga_execution_spec.py` and any `outcome_spec`
  equivalents) pass unmodified in behavior (only import source changes).
- `grep` across the repo confirms no second literal copy of the migrated tuples remains
  outside `tier_vocab.py`.

### Acceptance criteria
- [ ] AC1 (T14-F3-2). Editing `execution_spec.py` and `outcome_spec.py` to both import
  `MODELS`/`EFFORTS`/`MUTATION_POLICIES`/`WORKSPACE_ISOLATIONS`/`SANDBOX_PROFILES` from a
  single `tier_vocab.py` collapses the existing cross-module drift-guard test to an
  import-identity assertion. Check: `uv run pytest tests/ -k mirror_drift_execution_outcome`
  passes, and the test body asserts `execution_spec.MODELS is tier_vocab.MODELS` (or
  equivalent identity/import check) rather than value comparison.
- [ ] AC2 (T14-F3-2). `grep -rn 'MODELS = \|EFFORTS = \|MUTATION_POLICIES = \|WORKSPACE_ISOLATIONS = \|SANDBOX_PROFILES = ' plugins/saga/scripts/` returns exactly one definition site per name (in `tier_vocab.py`), not two.
- [ ] AC3 (T14-F3-2). `tier_vocab.MODELS` remains ordered strongest-first and
  `tier_vocab.EFFORTS` remains ordered weakest-first, and any index-based upgrade-only
  merge logic that reads these tuples continues to pass its existing tests unmodified.
- [ ] AC4 (T14-F4-2). A `drift_pairs` registry entry for
  `execution_spec.py`↔`execution-spec.md:138` exists; editing the code-side tier tuple
  without updating `execution-spec.md:138` causes the new parametrized drift test to fail.
  Check: `uv run pytest tests/test_fleet_mirror_drift.py -k execution_spec_doc_pair` fails
  on a deliberately mismatched fixture and passes once both sides match.
- [ ] AC5 (T14-F4-2). The `readonly-verifier` agentType literal-consistency check is expressed
  as a registered `drift_pairs` entry consumed by the same parametrized test, not as a
  separate hand-written test function.
- [ ] AC6 (H-F4-1). At least the `/plan` unit-tier table
  (`plugins/saga/skills/plan/SKILL.md:296-309`) and the team-execution Step A7 worker table
  (`plugins/team-execution/skills/team-execution/SKILL.md:225-235`) are converted to
  generated blocks (clearly delimited, e.g. HTML-comment markers) rendered from one fleet
  registry source, in ladder order for any ordered vocabulary.
- [ ] AC7 (H-F4-1). A CI check (script or test) regenerates both blocks from the registry and
  fails the build if the regenerated output differs from what is committed in
  `plan/SKILL.md` or `team-execution/SKILL.md`.
- [ ] AC8 (H-F4-1). At least one of the `drift_pairs` registry's guard tests is auto-enumerated
  from the registry's declared producer/consumer pairs (i.e., adding a registry row alone
  is sufficient to add drift coverage, with no new hand-written test function required),
  replacing at least one previously hand-written guard test.

### Out-of-scope / non-goals
In scope: collapsing the five named tier/policy vocabularies into `tier_vocab.py`; the
`drift_pairs` registry and its parametrized test; converting exactly the two named
rendered-mirror surfaces (`/plan` tier table, team-execution worker table) to generated
blocks with a CI regen check.

Out of scope / non-goals:
- Renaming or changing the *values* of any existing tier/policy vocabulary (this is a
  source-of-truth consolidation, not a vocabulary redesign).
- Migrating every mirror pair in the fleet into the `drift_pairs` registry in this issue —
  only the three named above (execution_spec↔outcome_spec, readonly-verifier agentType,
  execution_spec↔execution-spec.md) plus the two named rendered surfaces are required;
  further registry rows are follow-up work.
- Building a general-purpose templating engine for `SKILL.md` files — the render script
  only needs to own the specific tables named in this issue's Acceptance Criteria.
- Changing `ENGINE_INTENTS` authoring location or team-execution's external-engine worker
  semantics (`{#external-engine-chaperone-dispatch}` stays as-is); only the *rendering* of
  the worker table becomes generated.
- Any change to `{#tier-vocab-ordering}` semantics itself — this issue must preserve, not
  revisit, that binding decision.

## Grounding References

- `T14-F3-2` (primary) — basis: `execution_spec.py` inline comment, "outcome_spec.py
  mirrors these three names verbatim (deliberate parallel house, different error type) — a
  cross-module drift-guard test asserts the two copies stay identical"
  (`plugins/saga/scripts/outcome_spec.py:100`, `:125`). Engages `{#tier-vocab-ordering}` by
  requiring the collapsed source to keep ordered arrays and index-merge semantics intact.
- `T14-F4-2` (facet) — basis: the same guarded execution_spec/outcome_spec comment,
  contrasted with the unguarded `execution-spec.md:138` prose re-listing of
  `` `fable|opus|sonnet|haiku` ``; grounding brief §3 consumer-side finding 1 (stale
  hand-mirror in `card_validator.py` let 343 cards pass a dead validator, issue #222).
- `H-F4-1` (facet) — basis: grounding brief §1 corrections intake item (c), the
  `ENGINE_INTENTS` producer/consumer pair authored in `plan/SKILL.md:303-304` and rendered
  in the team-execution Step A7 worker table (`team-execution/SKILL.md:225-235`,
  `references/external-engine-workers.md`); grounding brief §3 finding 1 (contract-mirror
  drift recurred across 4 independent repos); commit `46b7001`, which shipped yet another
  one-off, hand-written "registration drift guard" — evidence the incident-driven,
  per-pair guard pattern is already recurring in this repo.
- Binding decision `{#tier-vocab-ordering}` — "Tier tuples are ordered escalation ladders,
  not just closed sets" — constrains the collapsed source module to preserve ordering.
- Binding decision `{#plugin-portfolio-groom-17-to-7}` — plugin sprawl is an active
  concern; this issue adds no new plugin, only a new module and registry inside existing
  plugins (`saga`, `team-execution`).
- Consolidation rationale (from issue-map): same target (N mirrored tuples) across all
  three absorbed ideas, escalating mechanism — import one source where possible, register
  declared mirror pairs where import is impossible, and generate rendered surfaces from a
  fleet registry where the mirror is a rendering, not a literal copy.

## Recommended Executor Profile

- Model: sonnet
- Effort: high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- Backend: team-execution
- External-LLM posture: none
- Justification: this is bounded, mechanical refactoring (move literals, add a registry,
  add a render script and CI check) against a well-specified target with existing tests to
  hold the line — it does not require opus-level judgment. `effort: high` reflects the
  number of coordinated touch points (two Python modules, two Markdown skill files, a new
  registry format, a new test file) rather than any need for deeper reasoning per touch
  point.

## Release-Surface Checklist

This issue changes plugin-internal behavior (test structure, generated documentation
blocks) but not the public skill/command surface of either plugin. Confirm in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — bump patch version if `tier_vocab.py` is
      treated as a new public module surface within the plugin; otherwise confirm no bump
      is needed and record why.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — bump patch version to reflect
      the generated-block change to `SKILL.md`'s worker table.
- [ ] `.claude-plugin/marketplace.json` — update version entries for `saga` and
      `team-execution` to match the bumped `plugin.json` values.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the `tier_vocab.py` consolidation and
      the new `drift_pairs` registry.
- [ ] `plugins/team-execution/CHANGELOG.md` — entry describing the Step A7 worker table
      becoming a generated block.
- [ ] Version/metadata drift-guard tests (if any exist in `tests/`) — updated or confirmed
      still green against the bumped versions.
- [ ] `docs/engineering-journal/DECISIONS.md` — entry recording the "generator over guard"
      pattern choice for future mirror-pair incidents, per project CLAUDE.md's requirement
      to capture plugin-pattern decisions.

## Files Expected to Change

Indicative only; `/plan` determines the exact set.
- `plugins/saga/scripts/tier_vocab.py` — new, single ordered vocabulary source.
- `plugins/saga/scripts/execution_spec.py` — import from `tier_vocab.py`; delete local
  tuple literals.
- `plugins/saga/scripts/outcome_spec.py` — import from `tier_vocab.py`; delete local
  tuple/dict literals (`MUTATION_POLICIES`, `WORKSPACE_ISOLATIONS`, `SANDBOX_PROFILES`).
- `plugins/saga/scripts/drift_pairs.py` (or `tests/drift_pairs.py`) — new registry of
  source/mirror/extractor triples.
- `tests/test_fleet_mirror_drift.py` — new parametrized test replacing hand-written
  per-pair drift tests.
- `fleet/registry.json` (or equivalent path) — new machine-readable tier/engine/intent
  registry.
- `scripts/render_registry.py` (or equivalent path) — new render script + CI check.
- `plugins/saga/skills/plan/SKILL.md` — unit-tier table (`:296-309`) converted to a
  generated block.
- `plugins/team-execution/skills/team-execution/SKILL.md` — Step A7 worker table
  (`:225-235`) converted to a generated block.
- `plugins/saga/references/execution-spec.md` — tier vocabulary at `:138` registered as a
  drift-guarded mirror of `execution_spec.py`.

## Tests to Add or Update

- `tests/test_fleet_mirror_drift.py` — new parametrized test iterating the `drift_pairs`
  registry; must include cases for execution_spec↔outcome_spec (now identity-based),
  execution_spec↔execution-spec.md (value-based), and the readonly-verifier agentType
  pair.
- `tests/test_saga_execution_spec.py` (existing) — confirm still green after the import
  change; no behavior change expected.
- New render-check test (or CI script invocation) asserting the `/plan` tier table and
  team-execution worker table match a fresh render from `fleet/registry.json`.

### Verification
```bash
# Collapsed vocabulary source imports cleanly and existing tests stay green
uv run pytest tests/test_saga_execution_spec.py -v

# New parametrized drift-pairs test covers all three registered pairs
uv run pytest tests/test_fleet_mirror_drift.py -v

# No second literal copy of the migrated tuples remains
grep -rn 'MODELS = \|EFFORTS = \|MUTATION_POLICIES = \|WORKSPACE_ISOLATIONS = \|SANDBOX_PROFILES = ' plugins/saga/scripts/

# Generated blocks match a fresh render (fails the build if stale)
python3 scripts/render_registry.py --check

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the drift-pairs test fails only when a deliberately introduced
mismatch is injected between a registered pair, and passes once the pair is realigned;
`render_registry.py --check` exits non-zero on a stale committed block and zero once
regenerated.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T14.json (ids T14-F3-2,
  T14-F4-2, H-F4-1) and issue-map-final.json (slug pf-single-vocab-source)
- Source type: ideation survivors (issue-map consolidation)
- Source title: Collapse the deliberate parallel houses: one ordered vocabulary module,
  declarative mirror-drift registry, generated mirrors

### Intent

`execution_spec.py` and `outcome_spec.py` each hand-type their own copies of the fleet's tier vocabulary (`MODELS`, `EFFORTS`, `MUTATION_POLICIES`, `WORKSPACE_ISOLATIONS`, `SANDBOX_PROFILES`), held in sync only by a cross-module drift-guard test — the module's own comment calls this a "deliberate parallel house." A third, unguarded copy of the model tier vocabulary is hand-retyped in prose at `execution-spec.md:138`. This issue collapses all of that into one ordered vocabulary module (`tier_vocab.py`) that the code modules import, adds a declarative `drift_pairs` registry so every remaining code↔code and code↔doc mirror is tested by construction instead of by memory, and — reaching for the generator end of the same fix — converts the two known rendered-mirror surfaces (the `/plan` unit-tier table and the team-execution Step A7 worker table) into generated blocks driven by one fleet registry with a CI check that catches un-regenerated drift.

### Context library links

_none_

### Files expected to change

- `references/external-engine-workers.md`
- `plugins/saga/scripts/tier_vocab.py`
- `tests/test_fleet_mirror_drift.py`
- `fleet/registry.json`
- `plan/SKILL.md`
- `team-execution/SKILL.md`
- `tests/test_saga_execution_spec.py`
- `plugins/saga/.claude-plugin/plugin.json`

### Tests to add or update

- `tests/test_fleet_mirror_drift.py`
- `tests/test_saga_execution_spec.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/419
- Number: 419
- Created at: 2026-07-04T08:07:40.874525+00:00

