---
title: Lease-safe runtime continuity wave 1 - concurrency policy
type: feat
status: active
date: 2026-07-15
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/350
---

# Lease-safe runtime continuity wave 1 - concurrency policy

## Summary

Implement issue #350 as the first independent leaf of outcome `lease-safe-runtime-continuity`.
Promote concurrency from the isolated `VERIFY_N_CAP = 7` literal into a serialized
`ExecutionSpec.concurrency` policy, resolve one deterministic cap for every emitted fan-out, chunk
dependency layers and verify panels through the same primitive, add tier and engine-lane modulation,
and fail emission when the spec's aggregate in-flight bound exceeds the fleet ceiling. Ship the Saga
plugin release surfaces in the same PR.

Destination is merge. Execution uses an approved Verified Workflow. Root owns implementation, Git,
integration, PR, merge, issue closure, and board reconciliation; agent-lens roles are read-only and
gate on independently recorded evidence.

## Current State

- `plugins/saga/scripts/execution_spec.py` owns both emitters' structured source model. It defines
  `VERIFY_N_CAP = 7`, validates `Verify.n`, computes dependency layers, emits verify-panel fan-out in
  `_emit_panel_reconciliation`, and emits a whole dependency layer as one `parallel([...])` call in
  `emit_workflow_script`.
- `ExecutionSpec` has no concurrency block today. Its optional run-level controls (`cost_budget`,
  `spend_envelope`, `intent`) establish the backward-compatible convention: an absent optional block
  emits no key and preserves existing specs.
- `plugins/fleet-core/scripts/fleet_commons/cost_weights.py` and `cost_weights.json` already own the
  validated model/effort weight table. A second tier table would drift.
- `plugins/saga/references/engine-registry.yaml` is the canonical external engine/lane registry.
- `plugins/saga/references/sandbox-spawn-sites.md` inventories sandbox-sensitive spawn sites, not
  concurrency policy coverage. Concurrency needs a sibling inventory with a distinct contract.
- The issue's mention of `team_emitter.py` is conditional. Live inspection found no executable
  `parallel([...])` runtime emission there, so it is not an implementation target unless a test proves
  a real fan-out seam was missed.

## Requirements

- **R1. Canonical policy schema.** Add an optional `ExecutionSpec.concurrency: ConcurrencyPolicy`
  block with `max_concurrent` default 3, `readonly_max_concurrent` default 4, and
  `aggregate_max_concurrent` default 7. Validate positive integers and
  `base <= readonly <= aggregate`; round-trip through `to_dict`/`from_dict`; derive `VERIFY_N_CAP`
  from the policy defaults rather than another literal.
- **R2. Resolution order.** Resolve spec default, `SAGA_MAX_CONCURRENT`, all-read-only cohort lift,
  tier-weighted admission, engine-lane `max_concurrent`, then explicit run override. Invalid
  authored/env/run/lane values or any effective width above the aggregate ceiling fail emission with
  the source rung named. The run override remains the highest-precedence operator instruction; a lane
  is the most specific automatic rung and therefore overrides tier/env/spec.
- **R3. One chunking primitive.** Dependency-layer and verify-panel fan-out both use one ordered
  chunk helper. Sequential chunks preserve dependency barriers; panel result arrays are concatenated
  in verifier order before reconciliation.
- **R4. Read-only lift.** A dependency layer whose units all explicitly declare
  `mutation_policy=read-only` raises the pre-tier candidate to
  `max(resolved_base, readonly_max_concurrent)`. Missing sandbox or any read-write unit keeps the
  resolved base. Tier weighting then applies, so read-only never bypasses cost admission. A verify
  panel uses the subject unit's resolved policy and never infers read-only from role prose.
- **R5. Tier-weighted admission.** Reuse `fleet_commons.cost_weights.to_spend`. Use the existing
  `sonnet/high` weight (12) as the baseline and compute
  `max(1, floor(resolved_base * 12 / max_unit_weight))`, capped by the non-tier width available to
  the wave. Cheap tiers therefore admit more than expensive tiers under the same authored base
  without creating a second weight vocabulary.
- **R6. Per-lane override.** Add optional positive `max_concurrent` to engine-registry entries and
  their parser. Apply it only to units actually routed to that external engine lane. Ordinary Claude
  units remain governed by the spec/env/tier/run policy.
- **R7. Aggregate guard.** Before rendering, compute the issue-defined conservative product for
  each dependency layer: emitted layer chunk width multiplied by the largest co-running verifier
  chunk width for that layer (factor 1 when the layer has no panel). Fail, do not clamp, when the
  maximum product exceeds `aggregate_max_concurrent`; name the layer, both factors, product, and
  ceiling. This follows AC8 literally even where today's sequential panel emission makes the product
  conservative.
- **R8. Drift guard.** Add `plugins/saga/references/concurrency-spawn-sites.md` as the canonical
  inventory of executable fan-out sites and a conformance test that parses the inventory and source.
  It must fail for an injected unbounded `parallel(...)` site and for a stale inventory entry.
- **R9. Compatibility.** Specs without `concurrency` serialize as before and emit with default
  behavior. No changes to `/optimize`, runtime 429 retry, team-execution reviewer scheduling, or
  external-engine chaperone behavior.
- **R10. Release integrity.** Bump Saga, update Saga CHANGELOG and marketplace metadata, run the
  release-surface parity/diff guards, and record the durable policy decisions in the engineering
  journal in the same commit.

## Data Contract

The optional JSON block is closed and contains only:

```json
{
  "concurrency": {
    "max_concurrent": 3,
    "readonly_max_concurrent": 4,
    "aggregate_max_concurrent": 7
  }
}
```

All values are positive integers; unknown keys fail `from_dict`; validation requires
`max_concurrent <= readonly_max_concurrent <= aggregate_max_concurrent`. An absent block resolves to
these fleet defaults but remains absent on round-trip. `SAGA_MAX_CONCURRENT` supplies only the
environment rung. Read-only lifting occurs before tier weighting. The explicit run override is an
emitter argument, not persisted spec state. An engine-registry variant may add one optional positive
`max_concurrent` key; variants that omit it remain byte-compatible. Environment, lane, and run values
above the aggregate ceiling fail rather than clamp.

## Traceability and Dependencies

- AC1 and AC3 map to R1/R2; AC2 to R3; AC4 to R3; AC5 to R4; AC6 to R5; AC7 to R2/R6; AC8 to R7;
  AC9 to R8; AC10 to R1; the issue's release checklist maps to R10.
- The parent context is the approved
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json` revision 3; issue #350's published
  ACs remain the implementation authority. The operator approved the exact Verified Workflow digest
  recorded below; any digest or role/model/effort change reopens the gate.
- There is no semantic code prerequisite: #350 and #351 are the two ready wave-1 leaves. Merged #350
  unblocks #356. Because both leaves edit Saga release surfaces, delivery is serialized: merge #350,
  refresh #351 from the new `main`, then implement/merge #351. This is a Git/release collision barrier,
  not a behavioral dependency, and #350 must not consume #351 settlement behavior.
- No external service, credential, deployment environment, or named human reviewer is required.

## Key Technical Decisions

- **KTD1 - one nested schema, no duplicate top-level field.** `max_concurrent` lives only in
  `ExecutionSpec.concurrency`. This satisfies the issue's serialized ExecutionSpec requirement
  without creating two sources of truth.
- **KTD2 - explicit override is truly last.** The complete order is spec, env, tier, lane, run. The
  issue calls lane the most specific rung among automatic policy inputs while separately requiring a
  run-time override. Treating lane as higher than the explicit run request would make that request
  cosmetic.
- **KTD3 - reuse fleet cost weights.** `cost_weights.to_spend` remains the only model/effort weight
  authority. The governor imports through the existing fleet-commons shim and fails loudly if an
  authored tier is outside that vocabulary.
- **KTD4 - explicit mutation evidence only.** Read-only lift requires every unit in the emitted
  cohort to declare the existing read-only mutation policy. Absence is conservative read-write.
- **KTD5 - AC8's product is the guard contract.** For each layer, multiply emitted worker-chunk width
  by the largest resolved verifier-chunk width, using factor 1 without a panel. The current emitter
  may sequence some panels, but the documented guard remains the conservative product the issue and
  acceptance selector require rather than silently substituting a different overlap model.
- **KTD6 - separate concurrency inventory.** Sandbox and concurrency inventories cross-link but do
  not share rows; their enforcement questions and failure messages are different.
- **KTD7 - no speculative team-emitter edit.** Only executable fan-out call sites proven by the
  conformance inventory are changed. Markdown descriptions and static tables are not runtime spawn
  sites.

These decisions are recorded under `{#concurrency-policy-350}` in
`docs/engineering-journal/DECISIONS.md` before implementation starts.

## Implementation Units

### U1. Policy schema and resolution

Add `ConcurrencyPolicy`, default constants sourced from that type, validation, optional
`ExecutionSpec.concurrency`, and backward-compatible serialization. Add a pure resolver accepting an
explicit environment mapping and optional run override so tests never mutate process-global state.

**Files:** `plugins/saga/scripts/execution_spec.py`,
`plugins/saga/scripts/concurrency_governor.py` (new), `tests/test_concurrency_policy.py` (new).

**Tests:** `resolution_ladder`, `invalid_override_fails_emit`, `max_concurrent_field`, absent-block
round trip, and `VERIFY_N_CAP` derivation.

### U2. Tier and lane admission

Reuse fleet-core cost weights for tier admission. Extend engine-registry schema/parser with optional
positive `max_concurrent`; resolve it only for matching engine-owned units. Preserve engine registry
fixtures that omit the field.

**Files:** `plugins/saga/scripts/concurrency_governor.py`,
`plugins/saga/references/engine-registry.yaml`, `plugins/saga/scripts/engine_registry.py`,
`tests/test_concurrency_policy.py`, `tests/test_saga_engine_registry.py`.

**Tests:** `tier_weighted_admission`, `per_lane_override`, invalid lane cap, non-engine unit ignores
lane cap, and explicit run override wins after lane resolution.

**Depends on:** U1.

### U3. Shared chunking and aggregate guard

Route dependency-layer and panel emission through one stable chunk helper. Preserve ordering and
panel reconciliation semantics. Compute and validate the aggregate bound before any workflow text is
emitted.

**Files:** `plugins/saga/scripts/execution_spec.py`,
`plugins/saga/scripts/concurrency_governor.py`, `tests/test_concurrency_policy.py`,
`tests/test_saga_execution_spec.py`.

**Tests:** `layer_wave_chunking`, `panel_chunking`, `readonly_lift`, `aggregate_guard`, dependency
order across chunks, and panel result concatenation.

**Depends on:** U1, U2.

### U4. Spawn-site conformance

Create the concurrency inventory, cross-link the sandbox inventory, and add a source-aware drift
guard. Inventory rows name the source path, function, fan-out form, and governor entry point.

**Files:** `plugins/saga/references/concurrency-spawn-sites.md` (new),
`plugins/saga/references/sandbox-spawn-sites.md`, `tests/test_concurrency_conformance.py` (new).

**Tests:** clean-tree inventory parity, injected unbounded fan-out goes red, stale inventory row goes
red, and prose-only `parallel` text is ignored.

**Depends on:** U3.

### U5. Release and full gate

Bump Saga 0.96.0 to 0.97.0 (new backward-compatible policy capability, matching Saga's current minor
cadence), update marketplace and CHANGELOG, record KTDs, regenerate metadata, and run narrow then full
checks.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`,
`.claude-plugin/marketplace.json`, `docs/engineering-journal/DECISIONS.md`, and any existing version
guard fixture that pins Saga, specifically `tests/test_saga_plugin.py`'s current `0.96.0` literal.

**Depends on:** U4.

## Requirement Coverage

| Requirement | Implementation | Primary evidence |
|---|---|---|
| R1 | U1 | `max_concurrent_field`, round-trip, derived-cap tests |
| R2 | U1, U2 | `resolution_ladder`, invalid override, lane/run precedence |
| R3 | U3 | `layer_wave_chunking`, `panel_chunking`, ordering tests |
| R4 | U3 | `readonly_lift` plus mixed/absent mutation cases |
| R5 | U2 | `tier_weighted_admission` using fleet-core weights |
| R6 | U2 | `per_lane_override` and registry validation |
| R7 | U3 | `aggregate_guard` with factor/product diagnostics |
| R8 | U4 | conformance suite and injected-unbounded fixture |
| R9 | U1-U4 | absent-block, existing golden, and scoped non-goal regressions |
| R10 | U5 | metadata parity, sync, diff guard, changelog/version assertions |

## Verification

Run in order; any failure blocks integration:

```bash
uv run pytest tests/test_concurrency_policy.py tests/test_concurrency_conformance.py -v
uv run pytest tests/test_saga_execution_spec.py tests/test_saga_engine_registry.py -v
grep -n '^VERIFY_N_CAP = ' plugins/saga/scripts/execution_spec.py
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run pytest
uv run python scripts/check_release_surface_parity.py
uv run python scripts/sync_marketplace.py --check
uv run python tools/release_surface_diff_guard.py --base-ref origin/main
```

Manual evidence: inspect one emitted six-unit default layer (two three-wide chunks), one all-read-only
layer (four-wide then remainder), one seven-member panel (no chunk wider than its resolved cap), and
one over-aggregate spec (named emit-time failure).

## Failure Modes and Stop Conditions

- A lower-precedence rung silently wins, an invalid value is clamped, or environment access makes
  tests order-dependent: stop and repair U1 before emitter changes.
- Tier admission introduces a second weight table or crosses plugin install boundaries incorrectly:
  stop and use the fleet-commons shim.
- Chunking changes dependency or verifier result order: stop; do not paper over with golden updates.
- The aggregate implementation uses addition, maximum, or an inferred runtime schedule instead of
  AC8's layer-width times verifier-width product: stop and restore the published contract.
- A real executable fan-out cannot be routed through the shared governor without expanding into
  `/optimize`, team-execution scheduling, or runtime 429 behavior: stop and return for scope review.
- Any P0-P3 document-review or code-review finding remains unresolved, any required validator lacks
  gate-capable evidence, or release metadata drifts: no PR/merge.

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | execution_class | runtime_agent_name | vehicle | mutation | required_evidence | role_lens_sha256 | profile_sha256 | expected_model | expected_effort | validator_required | validator_disabled | deterministic_contract_sha256 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| implement | - | - | root | root | n/a | - | - | root | root-only | authorized-diff,focused-tests | - | - | - | - | n/a | n/a | - |
| review-devils | implement | review | devils-advocate-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | 129f6dca0702ffcd4be7f9e5d0939e8e6806788846ba4058044c931883ef0e63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-security | implement | review | security-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | bf5bc1b66c0ee3d06071976b659c522c23057c56de5f6cc010556b2653c86980 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-architecture | implement | review | architecture-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | e48b37cea0b26bf39cae4d6611b4219e907d52d284ba6b9489b523a4b16c835f | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-testing | implement | review | testing-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,test-gaps | a867575e24c86b0573485d1d8bbd81514af3654d544342677b85f4bed0d9af63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| validate-concurrency | implement | validate | concurrency-tester | agent-lens | preferred | test-medium | test_medium | auto | none | tester-evidence,command-results | d40188645b7876e32ea592dd9799ee2ad7a2e230d82341611708dd492837b3da | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-concurrency | - | root | root | n/a | - | - | root | root-only | fixed-findings,full-gate,release-parity,git-receipt | - | - | - | - | n/a | n/a | - |

## Workflow Operating Contract

- The authorized subject is this issue's implementation paths plus exact release surfaces. Root
  records the pre-existing Git baseline before `implement`; unrelated worktree paths are excluded.
- Agent-lens rows authorize `mutation=none` and no external mutation. Current MultiAgent V2 may
  reapply the parent's permission profile, so the named profile is not claimed as an OS-enforced
  read-only sandbox. Root records a baseline, audits the worktree after every attempt, and treats any
  child-created diff as workflow-integrity failure. Root runs commands; the required concurrency
  tester independently evaluates command evidence and semantics. The installed registry currently
  has no deterministic-validator role, so none is fabricated.
- `vehicle=auto` requests named profiles. If the host cannot produce gate-capable named-profile
  attestation, the role runs inline in a fresh bounded context; missing required independence or
  validator evidence blocks the gate rather than being waived.
- Every P0-P3 finding is fixed by root and returned to the affected role in a new attempt. Three
  unsuccessful remediation cycles halt and page the operator. A model/class change requires a new
  approved workflow candidate.
- Git mutation, PR creation, merge, issue/board mutation, and completion remain root-only. No deploy,
  credential, production-data, force-push, or branch-deletion action is authorized.
- Workflow intents, receipts, findings, command logs, workspace audits, PR URL, merge SHA, issue close,
  and board reconciliation are retained in the Verified Workflow evidence root and the issue/PR.

## Completion Gate

Completion requires all issue acceptance criteria, zero open P0-P3 doc/code review findings, the
required validator passing with gate-capable evidence, full verification green, one atomic issue PR
merged, issue #350 closed, its Operations card reconciled, outcome node receipt recorded, and the
outcome worktree returned to a clean state except for the next planned wave.
