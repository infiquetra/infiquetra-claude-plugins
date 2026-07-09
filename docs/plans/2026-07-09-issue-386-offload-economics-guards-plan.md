---
title: Issue #386 Offload Economics Guards Plan
type: feat
status: active
date: 2026-07-09
origin: docs/sdlc-issue-drafts/plugin-fleet/pf-offload-economics-guards.md
---

# Issue #386 Offload Economics Guards Plan

## Summary

Add dispatch-time economics guards for external-engine `offload`: break-even halts on resident-Claude
token savings, provider budget ceilings on metered external spend, operator cost-delta previews, and
net-savings records in the dispatch manifest and run-fact ledger.

## Problem Frame

Issue #386 is open and Active as `infiquetra/infiquetra-claude-plugins#386`. The issue draft says
external-engine offload needs break-even, budget ceiling, preview, and net-savings proof; the July 6
scope note corrects the stale premise: `plugins/saga/scripts/run_ledger.py` already exists and records
run facts, so this work layers economics logic on that ledger rather than adding a second spend meter.

Relevant current surfaces:

- `plugins/saga/scripts/run_ledger.py:1` defines the canonical hash-chained `run_fact.v1` ledger;
  `plugins/saga/scripts/run_ledger.py:40` has the `engine` and `delegation` fact kinds.
- `plugins/saga/scripts/engine_dispatch.py:154` is the pre-run dispatch boundary; `:177` documents
  ledger facts as telemetry only; `:208` copies advisory chaperone provenance without gating today.
- `plugins/saga/scripts/engine_dispatch.py:432` records advisory engine facts with `cost`,
  `latency_seconds`, and `tokens`, and `:492` builds the typed `saga.manifest.v1` dispatch manifest.
- `plugins/saga/scripts/engine_registry.py:153` parses `cost_per_token`; `:305` defines `EngineEntry`;
  `:355` and `:372` require cost metadata, but no cost class or budget ceiling exists yet.
- `plugins/saga/scripts/chaperone_economics.py:31` already centralizes chaperone policy inputs and
  `:76` serializable chaperone decisions.
- `plugins/saga/scripts/engine_offer.py:88` defines the operator-facing offer shape; `:161` resolves
  lifecycle-stage offers but has no economics preview field today.
- `plugins/saga/scripts/provenance_manifest.py:330` defines the manifest envelope and rejects unknown
  keys in `from_dict`, so economics metadata must be schema-owned, not ad hoc.

## Requirements

R1. `offload` dispatch computes a pre-run economics decision before invoking the external adapter. The
decision must include estimated external provider cost when the engine has metered cost metadata,
estimated Claude-inline tokens avoided, estimated chaperone tokens required, and a human-readable
cost-delta preview.

R2. Break-even halt is based on resident-Claude token savings: if estimated chaperone tokens are
greater than or equal to estimated Claude-inline tokens avoided, `offload` halts before adapter
invocation and names the inline fallback. Do not compare USD, ordinal tier-spend, and tokens as if
they were one currency.

R3. Metered provider budget ceiling is checked before adapter invocation. The budget namespace is the
provider `engine_id`, not an individual variant. If prior ledgered provider spend plus the estimated
external provider cost would exceed the registry-authored ceiling, dispatch halts before the adapter
and names the ceiling and overshoot.

R4. Free-cost-class engines skip break-even and provider-ceiling checks, but still produce manifest
and run-ledger economics records with the external provider side treated as zero.

R5. Completed dispatch manifests include net-savings evidence: `engine_tokens_avoided`,
`chaperone_tokens_spent`, `net_savings_tokens`, and a status such as `positive`, `zero`, or
`negative`. Negative net savings is explicit, never a plain unlabelled number.

R6. Engine run-fact records include the same net-savings fields so downstream `/retro` and outcome
cost readers can derive rollups from `run_ledger.py` without reading manifest files.

R7. Operator-facing engine offers render a cost-delta preview when they offer `offload`, naming the
inline fallback when the estimate is uneconomic. Existing `none` and `second-opinion` offers remain
advisory and are not converted into gates.

R8. None of these economics guards create a new external-engine verdict role. Break-even and budget
halts are dispatch-time resolution outcomes; Claude remains verifier-of-record for any output that
does run.

R9. Metered `offload` dispatch without the required economics estimates halts before adapter
invocation with an `economics-missing` style reason. Missing data must not silently bypass break-even
or provider-ceiling checks.

R10. Saga release surfaces stay synchronized in the same PR: `plugins/saga/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, and version/parity tests.

## Key Technical Decisions

KTD1. Reuse the run-fact ledger, not a second meter: `run_ledger.py` is the canonical telemetry
substrate, so #386 reads and appends `engine` facts there instead of creating a new spend file.

KTD2. Split economics into two explicit units: resident-Claude token savings decide break-even, while
provider USD decides provider budget ceilings. This avoids a false comparison between Claude tier
weights, tokens, and external provider dollars.

KTD3. Extend `chaperone_economics.py` as the pure policy module: it already owns chaperone policy and
serializable provenance, so estimate, preview, break-even, ceiling, and net-savings helpers belong
there rather than being scattered through `engine_dispatch.py`.

KTD4. Registry rows get explicit `cost_class`: use `metered` or `free`, with `budget_ceiling_usd`
required for metered rows and forbidden for free rows. Rows with the same `engine_id` share a provider
budget namespace and must declare the same metered ceiling. A zero `cost_per_token` alone is not the
free class, because zero could mean missing pricing or temporary seed data.

KTD5. Dispatch halts before `runner(invocation)`: `engine_dispatch.dispatch()` is the last boundary
that has the `Resolution`, runner, ledger, chaperone metadata, and ability to prove the adapter was
not invoked.

KTD6. Manifest economics is schema-owned: add a typed optional economics record to
`provenance_manifest.py` and have `build_dispatch_manifest()` populate it from dispatch provenance.
Do not rely on unknown manifest keys; the schema correctly rejects them today.

KTD7. Cost preview is advisory UI, not authority: `engine_offer.py` may render economics lines for
operators, but the enforceable halts live at dispatch time so silent/unattended paths still obey them.

## Implementation Units

### U1. Registry Cost Policy Fields

Add explicit cost-class and budget-ceiling metadata to engine registry rows and loader validation.

**Goal:** Make every engine row state whether provider spend is metered or free, and make metered
ceilings available to resolver/dispatch code.

**Requirements:** R3, R4.

**Files:** `plugins/saga/references/engine-registry.yaml`, `plugins/saga/scripts/engine_registry.py`,
`plugins/saga/scripts/engine_registry_cli.py`, `tests/test_saga_engine_registry.py`,
`tests/test_engine_registry_lint.py`.

**Approach:** Add closed vocabulary `COST_CLASSES = ("metered", "free")`, parse `cost_class`, and add
`budget_ceiling_usd: float | None` to `EngineEntry`. Require metered rows to carry a non-negative
ceiling and forbid a ceiling on free rows. Keep `cost_per_token` required for all rows so existing
visibility and estimates remain stable; free rows must have zero input/output cost and tests should
fail if a free row has non-zero cost. Validate that rows sharing an `engine_id` either share the same
metered ceiling or fail loudly, so the "per-provider" ceiling does not split by variant. Update the
CLI list/JSON payload to expose `cost_class` and `budget_ceiling_usd`.

**Test scenarios:** Happy path: shipped registry loads with `cost_class` on every row and metered rows
expose ceilings. Edge case: free rows with zero cost load and no ceiling. Error path: unknown class,
missing metered ceiling, inconsistent ceilings across two variants of the same `engine_id`, free row
with non-zero `cost_per_token`, and metered row with negative ceiling raise `RegistryError`.
Integration: CLI row payload includes the new fields without changing existing winner stability tests.

**Verification:** `uv run pytest tests/test_saga_engine_registry.py tests/test_engine_registry_lint.py -v`.

### U2. Pure Offload Economics Helper

Extend chaperone economics with deterministic, unit-safe estimate and preview helpers.

**Goal:** Keep break-even, ceiling, preview, and net-savings math in one testable policy layer.

**Requirements:** R1, R2, R3, R4, R5, R9.

**Files:** `plugins/saga/scripts/chaperone_economics.py`, `tests/test_chaperone_economics.py`.

**Approach:** Add dataclasses such as `OffloadEconomicsInput`, `OffloadEconomicsDecision`, and
`NetSavingsRecord`. Inputs carry engine identity, cost class, optional `estimated_external_cost_usd`,
optional `provider_budget_ceiling_usd`, prior provider spend, `claude_inline_tokens_estimate`, and
`chaperone_tokens_estimate`. The helper returns `proceed`, `break-even-halt`, `budget-ceiling-halt`,
`economics-missing-halt`, or `free-class-proceed`, plus a short preview string. It must reject
negative estimates and mixed unknown units loudly.

**Test scenarios:** Happy path: economical metered dispatch proceeds and renders positive token
savings plus external USD estimate. Edge case: free class proceeds without break-even/ceiling checks
and still returns a zero external-cost record. Error path: chaperone estimate equal to inline estimate
returns `break-even-halt`; prior spend plus estimate over ceiling returns `budget-ceiling-halt`;
missing required metered estimates returns `economics-missing-halt`; negative estimates raise
`ChaperonePolicyError`. Called twice: same input returns byte-stable preview text and record values.

**Verification:** `uv run pytest tests/test_chaperone_economics.py -v`.

### U3. Dispatch-Time Halt Wiring

Wire economics decisions into resolver/dispatch so uneconomic offload never calls the adapter.

**Goal:** Apply break-even and budget ceiling checks at the last safe pre-adapter boundary.

**Requirements:** R1, R2, R3, R4, R7, R8, R9.

**Files:** `plugins/saga/scripts/engine_resolver.py`, `plugins/saga/scripts/engine_dispatch.py`,
`tests/test_saga_engine_resolver.py`, `tests/test_saga_engine_dispatch.py`.

**Approach:** Thread `cost_class` and `budget_ceiling_usd` through `Resolution` beside existing
`cost_per_token`, `latency_class`, and `estimated_input_cost_usd`. In `dispatch()`, before
`runner(invocation)`, build the economics decision for `offload` when `chaperone` or explicit
economics metadata is present. For metered engines, missing required estimate fields must produce a
typed halt instead of running unpriced. Compute prior provider spend from `run_ledger` `engine` facts
for the same provider. If the decision halts, return an `AdvisoryEvidence` with
`status: halted`, a specific halt string, and economics provenance; assert the runner was not called.
For free-class engines, skip checks and continue.

**Test scenarios:** Happy path: economical metered dispatch invokes runner once and stores economics
provenance. Edge case: free-class dispatch invokes runner even with missing budget ceiling. Error path:
break-even, budget-ceiling, and missing-economics decisions return halted evidence without runner
invocation. Integration: the existing short-circuit behavior for `resolution.halt` remains earlier
than economics and still does not call the runner; external engines still cannot carry gatekeeper keys.

**Verification:** `uv run pytest tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py -v`.

### U4. Manifest And Ledger Net-Savings Records

Persist completed-dispatch economics in both manifests and run facts.

**Goal:** Make net savings durable and queryable without parsing ad hoc provenance blobs.

**Requirements:** R5, R6, R8.

**Files:** `plugins/saga/scripts/provenance_manifest.py`, `plugins/saga/scripts/engine_dispatch.py`,
`plugins/saga/scripts/run_ledger.py`, `plugins/saga/references/run-fact-ledger.md`,
`tests/test_provenance_manifest.py`, `tests/test_saga_engine_dispatch.py`, `tests/test_run_ledger.py`.

**Approach:** Add a typed optional manifest economics record with fields
`engine_tokens_avoided`, `chaperone_tokens_spent`, `net_savings_tokens`, `net_savings_status`, and
optional `external_cost_usd`. Update `Manifest.to_dict()` / `from_dict()` unknown-key sets. In
`build_dispatch_manifest()`, copy the record from `evidence.provenance["economics"]` when present.
In `_record_advisory_facts()`, append those numeric fields onto the existing `engine` fact. Add a
small derive-on-read helper only if tests need provider-specific prior spend; otherwise keep rollups
generic.

**Test scenarios:** Happy path: manifest round-trips positive net savings and run-ledger engine fact
contains numeric savings fields. Edge case: zero net savings is status `zero`, not positive. Error
path: negative net savings is status `negative` and survives manifest/readback. Integration: unknown
manifest economics keys still raise `ManifestError`, preserving strict schema behavior.

**Verification:** `uv run pytest tests/test_provenance_manifest.py tests/test_saga_engine_dispatch.py tests/test_run_ledger.py -v`.

### U5. Offer Preview, Docs, And Release Surfaces

Expose cost-delta previews to operators and keep package metadata in sync.

**Goal:** Show economics before offload is selected while keeping enforcement in dispatch.

**Requirements:** R7, R8, R10.

**Files:** `plugins/saga/scripts/engine_offer.py`, `tests/test_engine_offer.py`,
`plugins/saga/references/engine-dispatch.md`, `plugins/saga/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`.

**Approach:** Add an optional `cost_delta_preview` field to `EngineOffer` and its JSON output. Populate
it only for `offload` offers when enough estimate inputs are available; otherwise render no preview
rather than fabricating numbers. Document that preview is advisory and dispatch remains the hard stop.
Bump Saga from `0.75.12` to the next patch version and update parity tests.

**Test scenarios:** Happy path: an offload work offer with estimates includes external cost,
inline-token estimate, net token delta, and cheaper inline fallback when uneconomic. Edge case:
`none` and `second-opinion` offers do not render offload savings claims. Error path: malformed
estimate inputs raise `EngineOfferError`. Integration: marketplace/plugin versions, changelog, and
release-surface parity checks all agree.

**Verification:** `uv run pytest tests/test_engine_offer.py tests/test_saga_plugin.py -v`,
`uv run python scripts/sync_marketplace.py --check`, and
`uv run python scripts/check_release_surface_parity.py`.

## Scope Boundaries

- Do not add provider billing integrations or live pricing fetches. Registry-authored `cost_per_token`
  and cost class are the source for v1.
- Do not change the existing `offload` chaperone tier default (`sonnet/medium`) in this issue.
- Do not add an external-engine gatekeeper or verdict path. Economics halts are pre-dispatch routing
  outcomes, not output adjudication.
- Do not replace #366 run-scoped ordinal `cost_budget`; this issue handles external-engine offload
  economics and net-savings telemetry.
- Do not create a second committed or machine-local spend ledger. Use `run_ledger.py`.

## Risks And Mitigations

| risk | mitigation |
|---|---|
| Unit confusion between dollars, tokens, and ordinal tier spend creates false savings claims. | KTD2 keeps break-even token-based and provider ceilings USD-based; tests cover mixed/unknown unit rejection. |
| Dispatch halts after adapter invocation, wasting the exact spend it should prevent. | U3 tests runner call count for break-even and ceiling halts. |
| Free-class engines accidentally skip manifest accounting. | U2/U4 require free-class net-savings records even while skipping pre-run checks. |
| Manifest schema drift silently drops economics fields. | U4 updates typed schema and preserves unknown-key rejection tests. |
| Budget ceiling reads stale or unrelated ledger facts. | U3 reads only `engine` facts for the same provider key and tests prior-spend filtering. |

## Backend And Destination

Destination: `merge`.

Recommended backend: `inline`. The work is deterministic Python/schema/test work in one repository with
clear seams and no deployment. Escalate to `team-execution` only if implementation discovers a broader
cross-module economics abstraction than this plan anticipates.

## Verification

Run focused checks first:

```bash
uv run pytest tests/test_chaperone_economics.py tests/test_saga_engine_registry.py tests/test_engine_registry_lint.py tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_provenance_manifest.py tests/test_run_ledger.py tests/test_engine_offer.py tests/test_saga_plugin.py -v
uv run python scripts/sync_marketplace.py --check
uv run python scripts/check_release_surface_parity.py
uv run ruff check .
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
git diff --check
```

Before PR, run the repo's normal CI-parity pytest gate unless the focused checks reveal a narrower
failure surface that must be fixed first.
