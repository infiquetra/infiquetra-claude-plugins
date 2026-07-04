---
title: "enhancement: engine-registry schema currency — capability vocabulary, profile inheritance, cost metadata, CI validation and staleness gates"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Stand up the external-engine offload lane"
wave: wave-1
---

# enhancement: engine-registry schema currency — capability vocabulary, profile inheritance, cost metadata, CI validation and staleness gates

### Objective
Stand up the external-engine offload lane

### Summary
`plugins/saga/references/engine-registry.yaml` and its loader
(`plugins/saga/scripts/engine_registry.py`) are the single source of truth for which external
engine handles which capability, at what cost, and how current that claim is. Six independently
found ideation facets converge on the same underlying gap: the registry's closed capability
vocabulary is narrower than what local models actually do, onboarding a model variant means
hand-authoring seven capability cells instead of inheriting a family default, cost/latency is
absent so routing changes can't reprice the fleet, `Registry.validate()` and the already-built
`Registry.stale()` API are never invoked by CI, and the offer/routing policy that consumes this
data is scattered in resolver branches rather than expressed as registry rows. This issue lands
all six as one coherent schema-and-CI change to the registry and its loader — not six separate
patches — because they share one file, one loader, and one validation entry point.

### Problem Frame
The registry and loader exist and are load-bearing today. Confirmed directly in this repo:

- `plugins/saga/scripts/engine_registry.py:13-21` — `CAPABILITIES` is a closed 7-value tuple
  (`code-generation`, `adversarial-review`, `second-opinion`, `debug`, `refactor`, `scaffold`,
  `long-form-writing`) with no `bulk-classification`, `structured-extraction`, or `embedding`
  entries — the shapes local/Ollama-class models are actually good at have no vocabulary slot
  (grounds `T2-F3-3`).
- `plugins/saga/scripts/engine_registry.py:106-133` (`_parse_capability_profile`) requires a
  `capability_profile` mapping keyed by every declared capability, hand-authored per engine
  variant row in `plugins/saga/references/engine-registry.yaml` — there is no family-default /
  override-merge step, so onboarding one more `codex`/`agy` variant means re-authoring all seven
  cells from scratch (grounds `T2-F6-5`).
- `plugins/saga/scripts/engine_registry.py:164-180` (`EngineEntry`) carries `cost_speed_rank`
  (an ordinal) and `context_window`, but no cost-per-token or latency-class field — nothing a
  consumer can reprice against when routing changes (grounds `H-F4-9`).
- `plugins/saga/scripts/engine_registry.py:377-385` (`Registry.stale`) is a fully implemented,
  currently-inert static method — it is exercised by unit tests
  (`tests/test_saga_engine_registry.py`, confirmed present via `grep -n "Registry.load"`) but
  never wired to a dispatch-time warning or a CI gate. `Registry.validate()`
  (`plugins/saga/scripts/engine_registry.py:305-334`) is likewise called only from
  `Registry.from_dict` at load time inside the test suite — `.github/workflows/ci.yml` (confirmed
  via `grep -n "pytest\|ruff\|mypy" .github/workflows/ci.yml`, run 2026-07-03) runs the full
  pytest suite, ruff, and mypy, but has no dedicated step that fails specifically when
  `engine-registry.yaml` itself is malformed or stale against a known model-release date — that
  signal is buried inside general test pass/fail, not a named, addressable CI gate (grounds
  `T2-F2-4` and `T2-F3-8`/`T1-F2-6`, which are one staleness mechanism named twice by independent
  ideation streams).
- Offer/routing policy today lives as resolver logic rather than registry data: no
  `surface_intent_defaults`-shaped file exists anywhere in the repo (confirmed via
  `find . -iname "*engine*"`, run 2026-07-03, turned up no such file) — the mapping from a named
  surface (e.g., `code-review`, `work`) to its default routing intent is not a retunable
  single-cell data file, it is implicit in whichever resolver branch was last edited (grounds
  `T1-F4-2`).

This is the primary consolidation target for its ideation theme in
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/`: `T2-F3-3` is tagged `structural`/primary,
`T2-F6-5`, `H-F4-9`, `T2-F2-4`, `T2-F3-8`, `T1-F2-6`, and `T1-F4-2` are absorbed facets of the same
registry-schema-currency problem (theme T2, frames F2/F3/F6/F4, plus theme T1 frames F2/F4). Binding
decision `{#external-engines-never-gatekeepers}` (#283) constrains all of this: none of the added
fields or gates change who is verifier-of-record — they only make the registry's existing data more
complete, more current, and more self-policing.

### Key Decisions
- **One registry, one loader, one PR.** All six facets touch the same two files
  (`engine-registry.yaml`, `engine_registry.py`) and the same validation entry point
  (`Registry.validate()`); this ships as one coherent schema revision, not six independent patches
  that could drift out of sync with each other.
- **Widen the vocabulary, don't fork it.** `CAPABILITIES` grows to include
  `bulk-classification`, `structured-extraction`, and `embedding` alongside the existing seven —
  existing capability keys and existing tests keep passing unchanged; this is additive to the
  closed vocabulary, not a redesign of `by_capability` resolution mechanics.
- **Family inheritance is a pre-validation merge step, not a schema relaxation.** A
  `model_identity`-keyed family-default block is merged with per-variant override cells before
  `_parse_capability_profile` runs; the resulting merged profile must be schema-identical to what
  today's hand-authored profile looks like — this reduces authoring cost, it does not loosen
  validation.
- **Cost metadata is authored, not measured.** `cost_speed_rank` stays as the existing ordinal;
  new `cost_per_token` / `latency_class` fields are single-write authored price metadata (an
  oracle), matching the `H-F4-9` framing explicitly — this is distinct from usage telemetry and
  ships no telemetry-collection mechanism.
- **Staleness is one mechanism serving two call sites.** `Registry.stale()` already exists
  (`engine_registry.py:377-385`); this issue adds exactly one `model-releases.yaml` watch file and
  wires `Registry.stale()` to both a dispatch-time warning and a CI failure — `T2-F3-8` and
  `T1-F2-6` describe the same mechanism from two ideation streams and must not become two
  divergent implementations.
- **Routing policy becomes registry-adjacent data, not resolver branches.** A
  `surface_intent_defaults` data file sits beside `engine-registry.yaml`, consumed by whatever
  offer/routing helper reads it (per `{#operator-choice-framework}`, routing stays doc-driven and
  CLI-driven, not a hidden resolver default) — this issue adds the data file and one consuming
  read path; it does not redesign the offer helper itself (see `pf-engine-offer-helper`, a
  sibling issue in this same wave, for the offer primitive).

### Actors
- A1. `plugins/saga/references/engine-registry.yaml` — the registry data file; gains new
  capability keys, family-default blocks, cost/latency fields.
- A2. `plugins/saga/scripts/engine_registry.py` — the loader; gains vocabulary entries, an
  inheritance-merge step, cost/latency parsing, and a `stale()`-consuming CI entry point.
- A3. CI (`.github/workflows/ci.yml` or a new step) — the caller of `Registry.validate()` and the
  new staleness check.
- A4. `model-releases.yaml` (new) — the watch file `Registry.stale()` compares
  `last_validated` against.
- A5. `surface_intent_defaults` data file (new) — consumed by the routing/offer read path.
- A6. Any lifecycle stage or plan-time consumer reading registry prices (e.g., `/plan`'s offload
  recommendation) — a downstream consumer of the new cost fields.

### Requirements
**Capability vocabulary (T2-F3-3)**
R1. `CAPABILITIES` includes `bulk-classification`, `structured-extraction`, and `embedding` in
addition to the existing seven values, and `Registry.by_capability("bulk-classification")`
resolves to a local/Ollama-class row that rates it, while all seven pre-existing capability
resolutions keep passing unchanged.

**Family inheritance (T2-F6-5)**
R2. A `model_identity`-keyed family-default `capability_profile` block is defined once per model
family; a per-variant row that supplies no override for a given capability inherits the family
default value; a per-variant row that supplies an explicit override for a capability wins over
the family default.
R3. The merged (post-inheritance) capability profile for every existing row is byte-identical to
that row's pre-refactor, already-validated profile — this is a authoring-cost reduction, not a
data change.

**Cost/latency metadata (H-F4-9)**
R4. Each `EngineEntry` carries authored `cost_per_token` and `latency_class` fields alongside the
existing `cost_speed_rank`; at least one consumer (e.g., a routing-recommendation code path) reads
these fields rather than hardcoding a price assumption.

**CI validation (T2-F2-4)**
R5. A named CI step runs `Registry.load` (which internally calls `Registry.validate()`) against
the real `plugins/saga/references/engine-registry.yaml` and fails distinctly (not merely as part
of the general pytest pass/fail) when a row is malformed.

**Staleness gate (T2-F3-8 + T1-F2-6, one mechanism)**
R6. A `model-releases.yaml` watch file records known model release dates; a CI check calls
`Registry.stale()` for every registry row against that file and fails when a row's
`last_validated` predates a newer known release for its `model_identity`.
R7. The same `Registry.stale()` mechanism is also invoked at dispatch time (not only in CI) and
emits a non-blocking warning (not a hard failure) when a stale row is about to be dispatched to.

**Routing policy as data (T1-F4-2)**
R8. A `surface_intent_defaults` data file, sitting beside `engine-registry.yaml`, maps each named
surface key to its default routing intent; a documented consuming read path resolves every named
surface key to its documented default intent by reading this file, not by branching in resolver
code.

### Key Flows
F1. **Widened capability resolution.** Trigger: a caller invokes
`Registry.by_capability("bulk-classification")`. The registry resolves to the local/Ollama-class
row rating that capability, using the same rating/cost-tiebreak ordering `by_capability` already
uses for the original seven capabilities. Covers R1.
F2. **Variant onboarding via inheritance.** Trigger: a new model variant row is added under an
existing `model_identity` family with only an override for one capability. The loader merges the
family-default profile with the row's override before validation; the merged profile passes
`Registry.validate()` without the seven cells being hand-authored. Covers R2, R3.
F3. **CI catches a broken registry row.** Trigger: a PR introduces a malformed row (e.g., missing
`cost_per_token` or an unrated capability). The named CI validation step fails and names the
offending row; reverting the row makes the same step pass. Covers R5.
F4. **CI catches a stale row; dispatch warns on the same row.** Trigger: `model-releases.yaml`
records a newer release for a `model_identity` than a row's `last_validated`. The CI staleness
check fails and names the row; independently, a dispatch-time call for that row emits a warning
(non-blocking) rather than a hard failure. Covers R6, R7.
F5. **Surface-key routing lookup.** Trigger: a routing/offer helper resolves the default intent
for a named surface (e.g., `code-review`). It reads `surface_intent_defaults` and returns the
documented default without any resolver-code branch keyed on that surface name. Covers R8.

### Acceptance Examples
AE1. **Covers R1.** `Registry.by_capability("bulk-classification")` resolves to a specific
Ollama-class row; the pre-existing `Registry.by_capability("code-generation")` (and the other six
original capabilities) still resolve exactly as before.
AE2. **Covers R2, R3.** A golden-snapshot test asserts the merged (post-inheritance) profile for
every pre-existing row in `engine-registry.yaml` is byte-identical to its pre-refactor validated
profile, and a row with one override cell shows that override winning over its family default.
AE3. **Covers R4.** A test asserts a routing-recommendation consumer's output changes when a
row's `cost_per_token` changes, without any code edit to the consumer.
AE4. **Covers R5.** `uv run pytest tests/test_engine_registry_lint.py` fails when a deliberately
broken row (e.g., a duplicate capability key) is introduced into a test fixture, and passes on the
real `engine-registry.yaml`.
AE5. **Covers R6.** A test seeds `model-releases.yaml` with a release date newer than a row's
`last_validated` and asserts the CI staleness check flags exactly that row; a row with a current
`last_validated` passes.
AE6. **Covers R7.** A test asserts a dispatch-time call for the same stale row emits a warning and
still completes dispatch (non-blocking), distinguishing it from the CI check's hard failure.
AE7. **Covers R8.** A test asserts every surface key named in `surface_intent_defaults` resolves,
via the consuming read path, to its documented default intent with no matching branch left in
resolver code for that key.

### Out-of-scope / non-goals
- This issue changes the registry schema, the loader, and CI wiring. It does not build the
  `engine_offer` helper or its remembered-preference store — that is `pf-engine-offer-helper`
  (sibling issue, same wave), which consumes `surface_intent_defaults` and other registry data but
  is scoped and shipped separately.
- It does not add a new dispatch mechanism or change chaperone-dispatch semantics — offload and
  second-opinion dispatch already exist per `{#external-engine-chaperone-dispatch}` (#318); this
  issue only makes the data those mechanisms read more complete and more current.
- It does not implement usage-telemetry collection — the new cost/latency fields are authored
  price metadata (a single-write oracle), not measured runtime telemetry; that remains a distinct,
  unscoped follow-up if ever pursued.
- It does not change `{#external-engines-never-gatekeepers}` (#283) — none of the new fields,
  gates, or staleness checks grant an external engine a gating role; Claude remains
  verifier-of-record.
- It does not redesign `by_capability`'s existing rating/cost-tiebreak resolution order — the
  widened vocabulary uses that same ordering unchanged.

### Dependencies / Assumptions
- Binding: DECISIONS `{#external-engines-never-gatekeepers}` (#283) — none of this issue's changes
  alter who gates a decision.
- Binding: DECISIONS `{#external-engine-chaperone-dispatch}` (#318) — dispatch mechanics are
  unchanged; only the registry data feeding them is enriched.
- Reuses the existing, already-implemented `Registry.validate()`
  (`plugins/saga/scripts/engine_registry.py:305-334`) and `Registry.stale()`
  (`plugins/saga/scripts/engine_registry.py:377-385`) — this issue wires them to CI and dispatch,
  it does not reimplement them.
- Verified absent today: no `surface_intent_defaults`-shaped file and no dedicated CI step
  invoking `Registry.validate()` or `Registry.stale()` against the real registry file exist in
  this repo (confirmed via `find . -iname "*engine*"` and `grep -n "pytest\|ruff\|mypy"
  .github/workflows/ci.yml`, run 2026-07-03).
- Grounding references (absorbed ideas, from
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` and
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json`):
  - `T2-F3-3` (primary, tier `structural`) — "Widen the capability vocabulary to what local models
    are actually for." Basis: `dod_sketch` calls for extending `CAPABILITIES` with
    `bulk-classification`/`structured-extraction`/`embedding` plus an Ollama row rating them and an
    `engine-dispatch.md` routing note, verified by a test asserting `by_capability` resolves the
    new capability to the local row while existing seven-capability tests still pass.
  - `T2-F6-5` (facet, tier `quick-win`) — "Capability-profile family inheritance so onboarding a
    variant isn't 7 hand-authored cells." Basis: `dod_sketch` calls for
    `model_identity`-family-default inheritance-merge before validation plus a registry refactor
    collapsing duplicated codex/agy variant cells to deltas, verified by a golden snapshot
    asserting merged profiles are byte-identical to pre-refactor validated profiles and an override
    cell wins over the family default.
  - `H-F4-9` (facet, tier `quick-win`, basis type `reasoned`) — "Provider registry entries carry
    cost/latency metadata so routing changes reprice the whole fleet." Basis: `dod_sketch` calls
    for cost-per-token/latency-class fields on engine entries plus one converted consumer (e.g.
    `/plan`'s offload recommendation reading registry prices) plus a router-plugin doc note,
    verified by a test asserting the consumer routes from registry prices.
  - `T2-F2-4` (facet, tier `quick-win`) — "Run `Registry.validate()` on `engine-registry.yaml` in
    CI." Basis: `dod_sketch` calls for a `validate-engine-registry` CI step plus
    `test_engine_registry_lint.py` calling `Registry.load` on the real
    `references/engine-registry.yaml`, verified by CI going red on a deliberately broken row and
    green once fixed.
  - `T2-F3-8` (facet, tier `quick-win`) — "Staleness-to-freshness CI guard." Basis: `dod_sketch`
    calls for a `model-releases.yaml` watch file plus a CI check calling `Registry.stale()` that
    fails/annotates when a row's `last_validated` predates a newer known release, verified by a
    test with a seeded newer release asserting the check flags exactly the stale row and passes
    when `last_validated` is current.
  - `T1-F2-6` (facet, tier `quick-win`) — "Automated engine-registry staleness gate — remove the
    manual 'is this profile current?' check." Basis: `dod_sketch` calls for a known-model-revisions
    data file plus a stale-check preflight (warn at dispatch, fail in CI) wired to `Registry.stale`,
    verified by a test where a stale entry warns at dispatch and exits nonzero in CI while a
    current entry passes. Consolidated with `T2-F3-8` as one mechanism serving both the CI-fail and
    dispatch-warn call sites.
  - `T1-F4-2` (facet, tier `structural`) — "Registry-driven surface×intent default matrix as a
    single retune lever." Basis: `dod_sketch` calls for a `surface_intent_defaults` data file
    beside the engine registry, consumed by the shared offer block, verified by a unit test that
    every named surface key resolves its documented default intent (policy-as-data, one-cell
    retune).
  - Consolidation rationale (`docs/plans/plugin-fleet-ideation-2026-07-03/` issue-map,
    `issue-map-final.json`): all seven facets touch the same registry file and loader and share one
    validation entry point — vocabulary widening, inheritance, cost metadata, CI validation, and
    the staleness gate are one schema-currency change, and the surface-intent default matrix is the
    registry-adjacent data layer that the offload lane's routing consumes; shipping them separately
    risks the registry and its consumers drifting out of step within the same PR cycle.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/references/engine-registry.yaml` — widened `capabilities` list, family-default
  blocks, new cost/latency fields per row.
- `plugins/saga/scripts/engine_registry.py` — `CAPABILITIES` tuple, inheritance-merge step,
  `cost_per_token`/`latency_class` parsing, `stale()` call sites wired to CI and dispatch.
- `plugins/saga/references/model-releases.yaml` (new) — known-model-revision watch file for the
  staleness gate.
- `plugins/saga/references/surface_intent_defaults.yaml` (new, or similarly named) — the
  surface→intent default data file.
- `.github/workflows/ci.yml` — new named step(s) invoking `Registry.load`/`Registry.validate()`
  and the staleness check against the real registry file.
- `plugins/saga/references/engine-dispatch.md` — routing note documenting the new capabilities
  and dispatch-time staleness warning.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — plugin metadata sync.
- `plugins/saga/CHANGELOG.md` — entry for the schema changes.
- `docs/engineering-journal/DECISIONS.md` — entry recording the family-inheritance and
  authored-cost-metadata choices, each with a revisit-when condition.
- `tests/test_saga_engine_registry.py` — extended coverage for widened vocabulary, inheritance
  merge, and cost/latency fields.
- `tests/test_engine_registry_lint.py` (new) — CI-invoked schema self-policing test.
- `tests/test_engine_registry_staleness.py` (new, or folded into the lint test) — staleness-gate
  coverage.

### Tests to add or update
- Capability vocabulary: `by_capability("bulk-classification")` resolves to the correct local
  row; all seven pre-existing capability resolutions unchanged.
- Family inheritance: golden-snapshot byte-identity for merged pre-existing profiles; an override
  cell wins over its family default.
- Cost/latency: a consumer's routing recommendation changes when `cost_per_token` changes.
- CI validation: `test_engine_registry_lint.py` fails on a deliberately broken row and passes on
  the real registry file.
- Staleness gate: a seeded newer release in `model-releases.yaml` flags exactly the stale row in
  CI; a dispatch-time call for the same row warns without blocking.
- Surface-intent defaults: every named surface key resolves its documented default intent via the
  consuming read path, with no matching resolver-code branch remaining for that key.

## Grounding References
- source_context: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` (ids
  `T2-F3-3`, `T2-F6-5`, `H-F4-9`, `T2-F2-4`, `T2-F3-8`)
- source_context: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (ids
  `T1-F2-6`, `T1-F4-2`)
- source_context: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2 (binding-decision
  register)

## Definition of Done
Widened `CAPABILITIES` vocabulary, family-default inheritance-merge, and authored cost/latency
fields land in `engine-registry.yaml`/`engine_registry.py` with byte-identical merged profiles for
existing rows. A named CI step invokes `Registry.validate()` and `Registry.stale()` (via a new
`model-releases.yaml` watch file) against the real registry, failing distinctly on a broken or
stale row, while the same `stale()` call also warns non-blockingly at dispatch time. A
`surface_intent_defaults` data file resolves every named surface to its documented default intent
with no resolver-code branch remaining. Release-surface metadata and `DECISIONS.md` entries ship
in the same PR, and the full test/lint/type suite stays green.

### Acceptance criteria
- [ ] `CAPABILITIES` includes `bulk-classification`, `structured-extraction`, `embedding` and
  `by_capability("bulk-classification")` resolves to a local/Ollama-class row while all seven
  pre-existing capability resolutions still pass. Check:
  `uv run pytest tests/test_saga_engine_registry.py -k capability_vocabulary` → passes.
- [ ] A family-default inheritance-merge step produces byte-identical merged profiles for every
  pre-existing row, and an override cell wins over its family default. Check:
  `uv run pytest tests/test_saga_engine_registry.py -k family_inheritance` → passes.
- [ ] `EngineEntry` carries `cost_per_token`/`latency_class`, and at least one consumer's output
  changes when a row's `cost_per_token` changes. Check:
  `uv run pytest tests/test_saga_engine_registry.py -k cost_metadata` → passes.
- [ ] A named CI step runs `Registry.load` against the real `engine-registry.yaml` and fails
  distinctly on a deliberately broken row, passing once fixed. Check:
  `uv run pytest tests/test_engine_registry_lint.py` → passes; `git diff --name-only` includes
  `.github/workflows/ci.yml` with a named validation step.
- [ ] A `model-releases.yaml` watch file plus a CI check flags exactly a row whose
  `last_validated` predates a newer known release, and passes when current. Check:
  `uv run pytest tests/test_engine_registry_lint.py -k staleness_ci` → passes.
- [ ] The same `Registry.stale()` mechanism, invoked at dispatch time, emits a non-blocking
  warning for a stale row rather than a hard failure. Check:
  `uv run pytest tests/test_saga_engine_registry.py -k dispatch_stale_warning` → passes.
- [ ] A `surface_intent_defaults` data file resolves every named surface key to its documented
  default intent via a documented read path, with no resolver-code branch remaining for that key.
  Check: `uv run pytest tests/test_saga_engine_registry.py -k surface_intent_defaults` → passes.
- [ ] `DECISIONS.md` carries an entry for the family-inheritance and authored-cost-metadata
  choices, each with a revisit-when condition. Check:
  `grep -n "revisit-when" docs/engineering-journal/DECISIONS.md` → includes new entries for this
  change.
- [ ] Release-surface metadata (plugin version, marketplace entry, CHANGELOG) is updated in the
  same PR. Check: `git diff --name-only` includes `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, and `plugins/saga/CHANGELOG.md`.
- [ ] Full suite, format, lint, and types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

### Verification
```bash
# Registry loader tests, including new vocabulary/inheritance/cost coverage
uv run pytest tests/test_saga_engine_registry.py -v

# CI-invoked schema self-policing and staleness gate
uv run pytest tests/test_engine_registry_lint.py -v

# Confirm CI wiring is present, not just the test file
grep -n "engine.registry\|Registry.validate\|Registry.stale" .github/workflows/ci.yml

# Confirm DECISIONS.md carries the required entries
grep -n "revisit-when" docs/engineering-journal/DECISIONS.md | tail -5

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the CI file names a step that runs `Registry.load`/`Registry.validate()` and
the staleness check against the real `engine-registry.yaml`; `DECISIONS.md` contains new entries
with revisit-when conditions for the family-inheritance and authored-cost-metadata choices.

### Recommended executor profile
- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** This is a schema-and-loader extension plus CI wiring against an
  already-implemented, already-tested loader (`Registry.validate()` and `Registry.stale()` both
  exist today and only need new call sites and new fields) — there is no architectural ambiguity
  to resolve; the vocabulary, inheritance-merge shape, and dispatch/CI split are already specified
  by the absorbed `dod_sketch`es. Sonnet/medium is sufficient; no case for opus (no judgment call
  or novel design decision) or an external engine (this is registry/schema/CI work, not something
  an external engine would generate or review with an advantage).

### Release-surface checklist
This issue changes plugin behavior (registry schema, loader parsing, and a new CI gate), so the
following must land in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `.claude-plugin/marketplace.json` — plugin metadata sync.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the widened vocabulary, family inheritance,
  cost/latency fields, the new CI validation step, the staleness gate, and the
  `surface_intent_defaults` data file.
- [ ] Drift-guard/lint test (`tests/test_engine_registry_lint.py`) wired into
  `.github/workflows/ci.yml` as a named step, so a future malformed or stale registry row fails CI
  instead of silently drifting.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` (ids `T2-F3-3`,
  `T2-F6-5`, `H-F4-9`, `T2-F2-4`, `T2-F3-8`) and
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (ids `T1-F2-6`, `T1-F4-2`)
- Source type: ideation-survivor
- Source title: Engine-registry schema currency: capability vocabulary, profile inheritance, cost
  metadata, CI validation and staleness gates

### Context library links

_none_

### Intent

`plugins/saga/references/engine-registry.yaml` and its loader (`plugins/saga/scripts/engine_registry.py`) are the single source of truth for which external engine handles which capability, at what cost, and how current that claim is. Six independently found ideation facets converge on the same underlying gap: the registry's closed capability vocabulary is narrower than what local models actually do, onboarding a model variant means hand-authoring seven capability cells instead of inheriting a family default, cost/latency is absent so routing changes can't reprice the fleet, `Registry.validate()` and the already-built `Registry.stale()` API are never invoked by CI, and the offer/routing policy that consumes this data is scattered in resolver branches rather than expressed as registry rows. This issue lands all six as one coherent schema-and-CI change to the registry and its loader — not six separate patches — because they share one file, one loader, and one validation entry point.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/452
- Number: 452
- Created at: 2026-07-04T08:22:19.873998+00:00

