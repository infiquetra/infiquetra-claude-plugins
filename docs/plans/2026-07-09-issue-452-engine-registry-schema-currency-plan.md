---
title: Issue #452 Engine Registry Schema Currency Plan
type: feat
status: active
date: 2026-07-09
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json
---

# Issue #452 Engine Registry Schema Currency Plan

## Summary

Extend the Saga external-engine registry schema so capability vocabulary, family defaults, authored
cost metadata, staleness checks, and surface-intent defaults live in registry-owned data with named CI
coverage. The plan keeps external engines advisory-only and avoids changing `Registry.by_capability`
rating precedence while making the data richer and self-policing.

## Problem Frame

`plugins/saga/scripts/engine_registry.py:13` defines a closed seven-value capability vocabulary, and
`plugins/saga/references/engine-registry.yaml:11` mirrors those values in checked-in data. New local and
Ollama-class use cases need vocabulary slots for `bulk-classification`, `structured-extraction`, and
`embedding` without weakening validation.

Today every row repeats its own `capability_profile`: `_parse_capability_profile` validates only the row
mapping at `plugins/saga/scripts/engine_registry.py:109`, and `EngineEntry.from_dict` requires that
mapping directly at `plugins/saga/scripts/engine_registry.py:294`. There is no pre-validation family
default merge.

The loader already has a `Registry.stale()` API at `plugins/saga/scripts/engine_registry.py:464`, but
CI has no named engine-registry validation step: `.github/workflows/ci.yml:43` runs the broad pytest
suite and `.github/workflows/ci.yml:140` starts ruff, with no explicit registry lint/staleness job.
`engine_offer.py` also carries hard-coded stage/shape defaults at
`plugins/saga/scripts/engine_offer.py:293`, so surface routing policy is not yet retunable data.

## Sources And Research

- GitHub issue: `infiquetra/infiquetra-claude-plugins#452`.
- Primary ideation source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`, including
  `T2-F3-3`, `T2-F6-5`, `T2-F2-4`, and `T2-F3-8`.
- Absorbed supporting source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json`, including
  `T1-F2-6` and `T1-F4-2`.
- External source for embedding row: `https://ollama.com/library/nomic-embed-text`, which identifies
  `nomic-embed-text` as an embeddings-only model.
- Existing binding decisions: `{#external-engines-never-gatekeepers}`,
  `{#external-engine-chaperone-dispatch}`, `{#provider-auth-preflight-389}`, and
  `{#engine-offer-helper-451}` in `docs/engineering-journal/DECISIONS.md`.

## Requirements

R1. `CAPABILITIES` and `engine-registry.yaml` include `bulk-classification`,
`structured-extraction`, and `embedding`; at least one local/Ollama-class row supports the new
capabilities, and existing seven-capability lookups keep their current winners.

R2. `model_identity`-keyed family defaults can define a `capability_profile` once; per-row overrides
merge over the family default before validation.

R3. The merged post-inheritance profile for every pre-existing row matches the current validated profile
captured in test fixtures. Inheritance reduces authoring, not data meaning.

R4. `EngineEntry` carries authored `cost_per_token` and `latency_class` metadata alongside
`cost_speed_rank`, and a resolver/offer output path reads those fields so a metadata-only change is
observable in output.

R5. CI has a named engine-registry validation step that loads the real
`plugins/saga/references/engine-registry.yaml` and fails distinctly on malformed rows.

R6. A registry-adjacent `model-releases.yaml` watch file feeds `Registry.stale()` so CI fails when a
row's `last_validated` predates a newer known release for that row's `model_identity`.

R7. The same staleness mechanism emits a dispatch-time non-blocking warning when a stale row is about
to run. This warning must not become a gate or fallback by itself.

R8. A registry-adjacent `surface_intent_defaults.yaml` file maps named Saga surfaces to default routing
intents; `engine_offer.py` resolves defaults from that file rather than hard-coded stage branches.

R9. Saga release surfaces and the engineering journal are updated in the same PR.

## Key Technical Decisions

KTD1. Additive capability vocabulary only: widen `CAPABILITIES` and registry data, but preserve existing
`Registry.by_capability` rating, `cost_speed_rank`, and registry-order precedence.

KTD2. Family inheritance is a pre-validation materialization step: load top-level `model_families`,
merge each row's overrides over its `model_identity` default, then validate the resulting profile with
the existing strict parser.

KTD3. `cost_per_token` is structured authored metadata: store `{input_usd, output_usd}` under one
`cost_per_token` field and validate non-negative numeric values. Keep `cost_speed_rank` as the stable
ordering tie-breaker to avoid silent routing changes.

KTD4. Resolver output is the first cost consumer: extend `Resolution` with `cost_per_token`,
`latency_class`, and an optional estimate when `token_estimate` is present. Do not make cost metadata
change `by_capability` winners in this PR.

KTD5. Registry staleness has two severities over one mechanism: CI hard-fails stale rows, while
dispatch records a non-blocking warning in resolution/evidence provenance.

KTD6. Surface-intent policy moves to data, not a second resolver: `engine_offer.py` owns the read path
for `surface_intent_defaults.yaml`, preserving repo-local preference override behavior.

## High-Level Technical Design

Add two registry-adjacent files:

```text
plugins/saga/references/model-releases.yaml
plugins/saga/references/surface_intent_defaults.yaml
```

The registry load path becomes:

```text
YAML -> parse capabilities -> materialize family defaults -> EngineEntry.from_dict -> Registry.validate
```

The warning path becomes:

```text
engine_resolver.resolve -> row selected -> model-releases.yaml read -> Registry.stale
  -> Resolution.warnings -> engine_dispatch.dispatch evidence provenance
```

The CI path becomes a named workflow step that runs a small script, for example
`plugins/saga/scripts/check_engine_registry.py`, against the checked-in registry and model-release watch
file.

## Implementation Units

### U1. Widen Registry Capability Vocabulary

Add the new capability keys and seed checked-in registry support without changing existing winners.

**Goal:** Make `bulk-classification`, `structured-extraction`, and `embedding` valid closed-vocabulary
capabilities and resolvable from registry data.

**Requirements:** R1.

**Files:** `plugins/saga/scripts/engine_registry.py`,
`plugins/saga/references/engine-registry.yaml`, `tests/test_saga_engine_registry.py`.

**Approach:** Add the three values to `CAPABILITIES` and the YAML `capabilities` list. Add supporting
ratings to a verified local/Ollama-class row for bulk classification and structured extraction. Add a
dedicated `ollama-cloud/nomic-embed-text` row for `embedding`, backed by the official Ollama model
library's embeddings-only model description. Keep all existing capability ratings sufficient to preserve
current lookup winners.

**Test scenarios:**

- Happy path: `Registry.by_capability("bulk-classification")` resolves to the intended local/Ollama-class
  row.
- Happy path: `structured-extraction` and `embedding` are accepted closed-vocabulary values and have at
  least one supporting registry row.
- Regression: each original capability still resolves to the same engine/variant as before.
- Error path: an unknown capability key still raises `RegistryError`.

**Verification:** `uv run pytest tests/test_saga_engine_registry.py -k capability -v`.

### U2. Materialize Family Defaults Before Strict Validation

Introduce `model_identity` family defaults that reduce duplicated capability cells while preserving the
post-merge profile.

**Goal:** Let rows inherit a family-level `capability_profile` and override only changed cells.

**Requirements:** R2, R3.

**Files:** `plugins/saga/scripts/engine_registry.py`,
`plugins/saga/references/engine-registry.yaml`, `tests/test_saga_engine_registry.py`.

**Approach:** Add a top-level `model_families` mapping keyed by `model_identity`. Before
`EngineEntry.from_dict`, materialize each raw row by deep-copying the matching family profile and
overlaying row-level `capability_profile` cells. Run the existing `_parse_capability_profile` on the
materialized mapping; do not allow partial profiles after materialization. Store a test fixture of the
current pre-refactor row profiles and assert materialized profiles match it for existing rows.

**Test scenarios:**

- Happy path: a row with one override inherits the rest of its family profile.
- Override path: an explicit row override wins over the family default.
- Regression: existing checked-in rows materialize to the captured pre-refactor profiles.
- Error path: a row whose `model_identity` has no family defaults and no complete row profile fails with
  a clear `RegistryError`.

**Verification:** `uv run pytest tests/test_saga_engine_registry.py -k family -v`.

### U3. Add Authored Cost And Latency Metadata

Parse, validate, and expose registry-authored price and latency metadata.

**Goal:** Make cost/latency visible to consumers without changing capability winner selection.

**Requirements:** R4.

**Files:** `plugins/saga/scripts/engine_registry.py`,
`plugins/saga/scripts/engine_resolver.py`, `plugins/saga/references/engine-registry.yaml`,
`tests/test_saga_engine_registry.py`, `tests/test_saga_engine_resolver.py`.

**Approach:** Add `cost_per_token: {input_usd, output_usd}` and `latency_class` to each registry row.
Validate non-negative numeric token costs and a small closed latency vocabulary such as `fast`,
`standard`, `slow`, and `batch`. Extend `EngineEntry` and `Resolution` with these fields; include an
optional estimate derived from `task_context["token_estimate"]` when present. Preserve
`cost_speed_rank` in `Registry.by_capability`.

**Test scenarios:**

- Happy path: checked-in rows expose `cost_per_token` and `latency_class`.
- Consumer path: changing a fixture row's `cost_per_token` changes resolver output without code edits.
- Error path: missing or negative token cost fails registry validation.
- Regression: `by_capability` winners remain stable when ratings and `cost_speed_rank` are unchanged.

**Verification:** `uv run pytest tests/test_saga_engine_registry.py tests/test_saga_engine_resolver.py -k cost -v`.

### U4. Add Named Registry Validation And Staleness CI

Wire the existing validation and staleness APIs into a named CI gate.

**Goal:** Make malformed or stale registry rows fail with a dedicated, addressable CI signal.

**Requirements:** R5, R6.

**Files:** `.github/workflows/ci.yml`, `plugins/saga/scripts/check_engine_registry.py`,
`plugins/saga/references/model-releases.yaml`, `tests/test_engine_registry_lint.py`.

**Approach:** Add a small CLI that loads the real registry, loads `model-releases.yaml`, calls
`Registry.validate()` through `Registry.load`, and checks every row with `Registry.stale()`. Wire it into
CI as a named step before broad pytest or near the release parity checks. Keep test fixtures local and
seed deliberately broken/stale rows so the test proves the gate's failure class.

**Test scenarios:**

- Happy path: real `engine-registry.yaml` and `model-releases.yaml` pass.
- Error path: a malformed fixture row produces a distinct validation failure naming the row.
- Staleness path: a fixture release date newer than `last_validated` flags exactly that row.
- Current path: a row validated on or after the known release date passes.

**Verification:** `uv run pytest tests/test_engine_registry_lint.py -v` and
`grep -n "Engine Registry" .github/workflows/ci.yml`.

### U5. Emit Dispatch-Time Staleness Warnings

Surface the same stale-row signal during dispatch without making it a gate.

**Goal:** Operators see stale registry data at runtime, while dispatch continues unless another existing
gate fails.

**Requirements:** R7.

**Files:** `plugins/saga/scripts/engine_resolver.py`, `plugins/saga/scripts/engine_dispatch.py`,
`plugins/saga/references/model-releases.yaml`, `tests/test_saga_engine_resolver.py`,
`tests/test_saga_engine_dispatch.py`.

**Approach:** Have resolver read the model-release watch file through an injectable seam and append a
warning to `Resolution.warnings` when `Registry.stale(entry, releases)` is true. Have dispatch copy those
warnings into advisory evidence provenance. Do not set `fallback`, `halt`, or `verified_by_claude` from
the warning.

**Test scenarios:**

- Warning path: stale selected row adds a warning and dispatch returns advisory evidence with that
  warning in provenance.
- Non-blocking path: stale row still completes dispatch when the runner succeeds.
- Current path: current row emits no warning.
- Gate boundary: warning alone cannot satisfy or fail `satisfy_gate`.

**Verification:** `uv run pytest tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py -k stale -v`.

### U6. Move Surface Intent Defaults To Data And Release Surfaces

Make lifecycle-stage offer defaults data-driven and publish the schema change.

**Goal:** Replace hard-coded stage/default routing policy with a registry-adjacent data file, then bump
Saga release surfaces.

**Requirements:** R8, R9.

**Files:** `plugins/saga/scripts/engine_offer.py`,
`plugins/saga/references/surface_intent_defaults.yaml`, `tests/test_engine_offer.py`,
`plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`, `docs/engineering-journal/DECISIONS.md`.

**Approach:** Add a data file mapping each `STAGES` surface and unit shape to the default intent/model
effort currently encoded by `JUDGMENT_DEFAULT_STAGES` and `_default_preference_for_shape`. Teach
`resolve_offer` to load defaults from the data file while preserving stored repo preferences as the
highest-priority override. Add a drift test that every `STAGES` value has a data row and no stage name is
left in a hard-coded default branch. Bump Saga from `0.75.9` to `0.75.10`.

**Test scenarios:**

- Happy path: every stage resolves its documented default through `surface_intent_defaults.yaml`.
- Preference path: `.saga/engine-prefs.json` still overrides data defaults.
- Error path: missing stage or invalid intent/model/effort in the data file raises `EngineOfferError`.
- Release path: Saga plugin metadata, marketplace entry, changelog, and version assertion agree.

**Verification:** `uv run pytest tests/test_engine_offer.py tests/test_saga_plugin.py -v`.

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Vocabulary widening accidentally changes existing routing winners. | Snapshot current original-capability winners and assert they remain stable after U1/U3. |
| Family defaults silently loosen schema validation. | Materialize to a full profile before calling the existing strict parser; test missing default failure. |
| Authored cost data is mistaken for telemetry. | Name it authored metadata in docs/changelog; do not add runtime measurement collection. |
| Dispatch staleness warning becomes an accidental gate. | Keep warning in `Resolution.warnings` and evidence provenance only; do not touch `fallback`, `halt`, or `satisfy_gate` decisions. |
| CI duplicate work becomes noisy. | Make the named engine-registry step small and diagnostic; broad pytest remains the comprehensive suite. |

## Scope Boundaries

- No new external-engine dispatch mechanism.
- No change to Claude as verifier-of-record or to `{#external-engines-never-gatekeepers}`.
- No usage telemetry or measured cost collection.
- No redesign of `Registry.by_capability` ordering beyond preserving current precedence.
- No production deployment or credential mutation.

## Verification Plan

- `uv run pytest tests/test_saga_engine_registry.py -v`
- `uv run pytest tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py -k stale -v`
- `uv run pytest tests/test_engine_registry_lint.py -v`
- `uv run pytest tests/test_engine_offer.py tests/test_saga_plugin.py -v`
- `grep -n "Engine Registry" .github/workflows/ci.yml`
- `uv run python scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python marketplace/validator/validate.py`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
- `git diff --check`

## Route

Destination: `merge`, per outcome authorization.

Execution backend: `inline`, recommended because the work is one repo, one plugin family, and already
has clear issue requirements plus local tests. Escalate to `team-execution` only if implementation
uncovers a broad resolver/dispatch compatibility break.

Next command: `/doc-review docs/plans/2026-07-09-issue-452-engine-registry-schema-currency-plan.md`
