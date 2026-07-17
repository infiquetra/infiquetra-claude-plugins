---
title: Lease-safe runtime continuity wave 1 - concurrency policy
type: feat
status: active
date: 2026-07-15
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/350
deepened: 2026-07-15
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
- **R6. Per-lane override and frozen capability routing.** Add optional positive `max_concurrent` to
  engine-registry entries and their parser. Before chunking, resolve every authored capability with
  the same repository overlay, calibration signals, role kind, and task context used by runtime
  dispatch; reject fallback, halt, missing, or non-registry results. Emit the resolved exact engine
  key as the sole runtime selector, preserve the authored capability as non-selector provenance, and
  apply the cap for that exact lane. Ordinary Claude units remain governed by the
  spec/env/tier/run policy. The immutable emit-scoped routing context uses `role_kind=worker`, the
  already-rendered unit prompt as `task_context.context`, its UTF-8 byte length as
  `task_context.token_estimate`, and the unit ID as `task_context.unit_id`; tests inject overlay and
  calibration objects directly, while production loads both once from the target repository root.
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
- **KTD8 - capability routes are frozen before admission.** A capability cannot remain late-bound
  after its lane cap is selected because overlay or calibration changes can make admission and
  dispatch name different engines. Emission resolves once through `engine_resolver.resolve`, emits
  only the resulting exact `engine` selector because the runtime contract requires capability XOR
  engine, and retains the authored capability only as provenance. Any unavailable or non-exact
  resolution halts emission rather than falling back or guessing a cap.

These decisions are recorded under `{#concurrency-policy-350}` in
`docs/engineering-journal/DECISIONS.md` before implementation starts.

## Implementation Units

### U1. Policy schema and resolution

Add `ConcurrencyPolicy`, default constants sourced from that type, validation, optional
`ExecutionSpec.concurrency`, and backward-compatible serialization. Add a pure resolver accepting an
explicit environment mapping and optional run override so tests never mutate process-global state.
Keep authored unit serialization unchanged when emission freezes a capability route.

**Files:** `plugins/saga/scripts/execution_spec.py`,
`plugins/saga/scripts/concurrency_governor.py` (new), `tests/test_concurrency_policy.py` (new).

**Tests:** `resolution_ladder`, `invalid_override_fails_emit`, `max_concurrent_field`, absent-block
round trip, and `VERIFY_N_CAP` derivation.

### U2. Tier and lane admission

Reuse fleet-core cost weights for tier admission. Extend engine-registry schema/parser with optional
positive `max_concurrent`; resolve it only for matching engine-owned units. Route capability selectors
  through the real overlay/calibration-aware resolver once, share that frozen exact identity between
  chunking and emitted options, and preserve engine registry fixtures that omit the field. Use one
  immutable per-emission routing context and one resolver memo; do not re-resolve per chunk or derive
  a second token estimate. Preserve capability provenance in the existing inert dispatch comment,
  not by adding a second runtime selector or changing serialized `Unit` data.

**Files:** `plugins/saga/scripts/concurrency_governor.py`,
`plugins/saga/references/engine-registry.yaml`, `plugins/saga/scripts/engine_registry.py`,
`tests/test_concurrency_policy.py`, `tests/test_saga_engine_registry.py`.

**Tests:** `tier_weighted_admission`, `per_lane_override`, invalid lane cap, non-engine unit ignores
lane cap, explicit run override wins after lane resolution, overlay and calibration each select an
alternate cap-one lane, emitted options contain only that exact engine selector, authored capability
round-trip remains unchanged, and fallback/halt/substitution inputs fail closed.

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
guard. Inventory rows name the source path, function, fan-out form, and governor entry point. The
guard reconstructs the emitted JavaScript stream across consecutive append calls, recognizes all
ECMAScript line terminators, and proves the reaching definition used by each bounded outer and inner
fan-out loop cannot be overwritten before use.

**Files:** `plugins/saga/references/concurrency-spawn-sites.md` (new),
`plugins/saga/references/sandbox-spawn-sites.md`, `tests/test_concurrency_conformance.py` (new).

**Tests:** clean-tree inventory parity, injected unbounded fan-out goes red, stale inventory row goes
red, prose-only `parallel` text is ignored, split append fragments and `U+2028`/`U+2029` trivia are
detected, an intervening governor-result overwrite fails, and every independently owned Workflow host
global reservation—including `parallel`—fails when removed from production.

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
| R6 | U2 | overlay/calibration frozen-route fixtures, exact emitted selector, `per_lane_override`, and registry validation |
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
one over-aggregate spec (named emit-time failure). Inspect one capability unit whose overlay selects a
cap-one lane: its inert marker retains the authored capability, its runtime options contain only the
resolved exact engine key, and its emitted wave is one-wide.

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
- Capability admission and emitted runtime selection cannot consume one frozen exact resolution, or
  the selected resolution falls back, halts, or names no registry key: stop and fail emission rather
  than retaining late-bound capability dispatch.
- Any P0-P3 document-review or code-review finding remains unresolved, any required validator lacks
  gate-capable evidence, or release metadata drifts: no PR/merge.

## Attempt 5 Review Result

The operator approved one fifth remediation attempt after four review cycles exposed structural
weaknesses that narrower patches did not close. This attempt is limited to the following repairs:

1. Resolve both exact engine and capability selectors to the selected engine-registry lane before
   concurrency admission. Pass the resolved lane identity to the governor separately from the
   authored selector so exact and capability-routed units share one lane cap without changing emitted
   routing metadata.
2. Make JavaScript fan-out discovery trivia-aware across whitespace, block comments, and line comments
   between `parallel`, `(`, and `[`, while continuing to ignore prose-only mentions.
3. Replace function-scope governor-name checks with an AST dataflow proof from the governor result,
   through the bounded outer chunk loop and inner thunk/verifier loop, to the emitted parallel block.
   Mutation tests must fail when either loop bypasses the bounded collection.
4. Replace the production-derived JavaScript-global test oracle with an independent
   ECMAScript/workflow baseline and Node `globalThis` readback. Mutation evidence must prove that
   removing a production reservation while injecting its free reference is detected, while property
   accesses remain excluded.

Attempt 5 passed 4,375 tests plus Ruff, MyPy, release parity, marketplace sync, and diff checks, but
the required security reviewer reproduced one capability-lane cap bypass and three conformance-oracle
gaps. Its architecture receipt was also invalid because the reviewer wrote ignored `.coverage` state.
No attempt-5 review receipt authorizes integration.

## Attempt 6 Remediation Scope

The operator approved attempt 6 with frozen capability-to-engine resolution and fresh Sol/max repair,
security, and architecture contexts. This attempt is limited to five closures:

1. Resolve a capability once with the actual overlay/calibration-aware resolver, bind concurrency and
   emitted runtime dispatch to the same exact engine key, retain capability only as provenance, and
   fail closed on fallback, halt, or non-exact output. The resolver request uses `role_kind=worker`,
   the rendered unit prompt plus its UTF-8 byte count and unit ID, and one emit-scoped overlay,
   calibration snapshot, and memo loaded from the target repository root.
2. Reconstruct consecutive emitted JavaScript fragments before fan-out detection and recognize
   whitespace, block comments, line comments, CR/LF, `U+2028`, and `U+2029` trivia.
3. Replace assignment-name existence with a reaching-definition/dominance proof that rejects
   overwrite, alias substitution, dead-branch dummy calls, or post-assignment mutation before either
   bounded loop consumes the governor result.
4. Add a test-owned Workflow host-global baseline, separate from Node `globalThis`, and mutation-test
   every production reservation including `parallel` while retaining member-property exclusions.
5. Run every reviewer and validator with coverage, bytecode, UV, XDG, Ruff, and MyPy caches outside
   the protected worktree; reject any attempt whose before/after workspace audit changes.

No broader routing feature, public unit-schema change, runtime scheduler, automatic attempt 7, or
relaxation of the required review evidence is authorized.

## Attempt 7 Remediation Scope

The operator explicitly approved attempt 7 after the attempt-6 architecture seal stopped on two
P2 findings. This attempt is limited to the following closures:

1. Snapshot the supplied environment, or `os.environ` when none is supplied, exactly once at
   `emit_workflow_script` entry. Pass that immutable emit-scoped copy to aggregate validation,
   worker chunking, verifier admission, and retry-panel rendering so one emission cannot observe
   multiple environment revisions.
2. Extend the conformance reaching-definition proof to track direct aliases of the governed chunk
   collection and reject any mutation through an alias before the bounded outer loop consumes the
   original collection.
3. Add exact mutation regressions for an environment change between aggregate preflight and
   rendering, and for `chunk_alias = layer_chunks; chunk_alias.append(concrete_units)` before the
   original-name loop.
4. Rerun focused tests and checks, then use fresh Sol/max architecture and security reviews,
   Sol/high testing review, and a Terra/medium concurrency validator before the full deterministic
   gate and integration.

No other implementation surface, evidence relaxation, or review-model downgrade is authorized.

## Attempt 8 Remediation Scope

The operator explicitly approved attempt 8 after the attempt-7 frozen review barrier. The six P2
review findings consolidate into five technical repairs, plus one P3 documentation correction:

1. Replace sibling-only alias tracking with a conservative, control-flow-aware proof. Alias binding
   or mutation inside a compound statement, assignment expression, unbound mutator, or unknown helper
   must kill the reaching governor definition unless the operation is explicitly proven read-only.
2. Pair emitted `parallel([` opens with their real JavaScript closes. Comment-shaped or string-shaped
   `])` text cannot terminate the member-analysis region, and every member emitter before the actual
   close must derive from the governed chunk.
3. Preserve pending JavaScript fragment reconstruction across statements proven not to mutate the
   output collection. Unknown output-list mutation or escape while a possible callee fragment is
   pending fails closed as unsupported source instead of silently resetting state.
4. Add the full environment and exact/capability lane consumer matrix for normal verifier panels,
   iterate-to-consensus panels, and unattended retry panels. Mutation-kill each forwarding edge so the
   tests prove the immutable emit snapshot and frozen route/lane context reach every consumer.
5. Correct the execution-spec reference: capability selectors freeze to one exact emitted engine and
   survive only as inert provenance; aggregate validation, worker chunks, verifier admission, and
   retries share one immutable emit-scoped environment snapshot.

Root remains the only source and Git writer. A fresh Sol/max repair-design context may propose the
bounded implementation, but root audits and applies it. Focused validation uses Terra/medium; fresh
architecture and security reviews use Sol/max; testing uses Sol/high. The full deterministic gate and
integration run only after every affected review returns without P0-P3 findings.

No parser rewrite outside the test-owned conformance oracle, production routing change, schema change,
evidence relaxation, or review-model downgrade is authorized.

## Attempt 9 Remediation Scope

The operator explicitly approved attempt 9 after the attempt-8 review barrier stopped on three P2
conformance-oracle findings. This attempt is limited to the following closures:

1. Carry governed alias-state transfer through each inner member-loop body, not merely to the loop
   statement. Mutation, escape, rebinding, unknown helpers, unbound mutators, and compound-statement
   mutation of the governed collection must invalidate both worker and verifier member emitters.
2. Extend the JavaScript lexical close scanner to recognize regular-expression literals, including
   escapes and character classes, or fail closed when slash syntax is ambiguous. Regex text containing
   `]` or `)` cannot close the surrounding `parallel([` region.
3. Track output-list aliases across fragment reconstruction so aliases bound before an opener can
   contribute fragments, while alias mutation, escape, unknown helpers, and unbound mutators fail
   closed. A mixed `lines.append(...)` / alias `.append(...)` stream must not hide a parallel opener.
4. Add exact mutation fixtures for all three bypasses, plus positive controls proving legitimate inner
   loops, regex literals, division expressions, and output aliases remain analyzable.
5. Rerun focused checks, then use fresh Sol/max adversarial review, Sol/high testing review, and a
   Terra/medium concurrency validator before the full deterministic gate and integration.

Root remains the only source and Git writer. No production routing, execution schema, governor,
release-surface, or public behavior change is authorized by this remediation. Any P0-P3 finding after
attempt 9 halts and pages the operator; there is no automatic attempt 10.

## Attempt 10 Consolidation Scope

The operator explicitly approved attempt 10 after concluding that repeated syntax-specific repairs
were overfitting a test-only oracle. This attempt replaces the miniature Python/JavaScript analyzer
with one explicit production emission boundary and a smaller structural contract:

1. Introduce one private `_emit_parallel_wave` helper in `execution_spec.py`. It owns the only emitted
   `parallel([` open/close pair, snapshots the supplied bounded member sequence before invoking its
   member renderer, and preserves the current emitted JavaScript byte-for-byte.
2. Route both verifier-panel chunks and dependency-layer worker chunks through that helper. Each call
   must pass the direct chunk target produced by the existing governor-backed outer loop; aliases,
   alternate collections, and raw parallel emission remain outside the accepted structure.
3. Replace the conformance oracle's hand-written output-alias, Python dataflow, and JavaScript lexical
   reconstruction with structural checks: exactly the two inventoried helper call sites exist, each
   consumes its loop's direct governor-derived chunk target, and no other output sink emits a raw
   parallel opener.
4. Add focused helper tests proving stable order, one emission per snapshotted member even when the
   original list is mutated by a callback, exact open/close output, inventory drift rejection, raw
   emitter rejection, direct-chunk enforcement, and governor-call enforcement.
5. Rerun focused and full gates, then use fresh Sol/max adversarial, security, and architecture review,
   Sol/high testing review, and Terra/medium concurrency validation before integration.

This is an internal consolidation, not a new scheduler, routing behavior, schema, dependency, or public
API. Root remains the sole source and Git writer. Any P0-P3 finding after attempt 10 halts and pages the
operator; there is no automatic attempt 11.

## Final Receipt-Chain Correction

After the operator directed the autonomous outcome to continue, the fresh immutable-subject
architecture lens found one P2 in the test-owned structural guard: a raw `parallel([` delimiter
could be assigned to a local static name and appended later without reaching direct sink inspection.
The bounded correction rejects raw parallel delimiter literals at any static assignment outside the
sole `_emit_parallel_wave` framing helper and adds the exact local-opener/local-closer mutation test.
It does not change production behavior, routing, the governor, the schema, or the public API. The
workflow rebuilds its subject and reviewer chain from the corrected tree; it does not reuse the
superseded subject's acceptance evidence.

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | execution_class | runtime_agent_name | vehicle | mutation | required_evidence | role_lens_sha256 | profile_sha256 | expected_model | expected_effort | validator_required | validator_disabled | deterministic_contract_sha256 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repair-design | - | - | architecture-reviewer | agent-lens | preferred | review-max | review_max | auto | none | scored-review,findings | e48b37cea0b26bf39cae4d6611b4219e907d52d284ba6b9489b523a4b16c835f | ee2062e446db24856e6893dd290183b66b9387f19d97e8a39a7631de453adb9f | gpt-5.6-sol | max | n/a | n/a | - |
| implement | repair-design | - | root | root | n/a | - | - | root | root-only | authorized-diff,mutation-tests,focused-tests | - | - | - | - | n/a | n/a | - |
| pre-review-devils | implement | preflight | devils-advocate-reviewer | agent-lens | preferred | review-max | review_max | auto | none | scored-review,findings | 129f6dca0702ffcd4be7f9e5d0939e8e6806788846ba4058044c931883ef0e63 | ee2062e446db24856e6893dd290183b66b9387f19d97e8a39a7631de453adb9f | gpt-5.6-sol | max | n/a | n/a | - |
| pre-review-testing | implement | preflight | testing-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,test-gaps | a867575e24c86b0573485d1d8bbd81514af3654d544342677b85f4bed0d9af63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| pre-validate-concurrency | implement | preflight | concurrency-tester | agent-lens | preferred | test-medium | test_medium | auto | none | tester-evidence | d40188645b7876e32ea592dd9799ee2ad7a2e230d82341611708dd492837b3da | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| repair-preflight | pre-review-devils,pre-review-testing,pre-validate-concurrency | - | root | root | n/a | - | - | root | root-only | fixed-findings,focused-tests | - | - | - | - | n/a | n/a | - |
| review-devils | repair-preflight | final | devils-advocate-reviewer | agent-lens | preferred | review-max | review_max | auto | none | scored-review,findings | 129f6dca0702ffcd4be7f9e5d0939e8e6806788846ba4058044c931883ef0e63 | ee2062e446db24856e6893dd290183b66b9387f19d97e8a39a7631de453adb9f | gpt-5.6-sol | max | n/a | n/a | - |
| review-security | repair-preflight | final | security-reviewer | agent-lens | preferred | review-max | review_max | auto | none | scored-review,findings | bf5bc1b66c0ee3d06071976b659c522c23057c56de5f6cc010556b2653c86980 | ee2062e446db24856e6893dd290183b66b9387f19d97e8a39a7631de453adb9f | gpt-5.6-sol | max | n/a | n/a | - |
| review-architecture | repair-preflight | final | architecture-reviewer | agent-lens | preferred | review-max | review_max | auto | none | scored-review,findings | e48b37cea0b26bf39cae4d6611b4219e907d52d284ba6b9489b523a4b16c835f | ee2062e446db24856e6893dd290183b66b9387f19d97e8a39a7631de453adb9f | gpt-5.6-sol | max | n/a | n/a | - |
| review-testing | repair-preflight | final | testing-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,test-gaps | a867575e24c86b0573485d1d8bbd81514af3654d544342677b85f4bed0d9af63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| validate-concurrency | repair-preflight | final | concurrency-tester | agent-lens | preferred | test-medium | test_medium | auto | none | tester-evidence | d40188645b7876e32ea592dd9799ee2ad7a2e230d82341611708dd492837b3da | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-concurrency | - | root | root | n/a | - | - | root | root-only | fixed-findings,full-gate,release-parity,git-receipt | - | - | - | - | n/a | n/a | - |

## Workflow Operating Contract

- The authorized subject is this issue's plan, implementation paths, and exact release surfaces. Root
  records the pre-existing Git baseline before `implement`; unrelated worktree paths are excluded.
- Inside `implement`, root may consume one fresh, non-gate implementation proposal from a generic
  worker pinned to `gpt-5.6-sol` at `max`. That worker receives only the four open technical findings,
  authorized paths, required mutation fixtures, and output contract; it works in a disposable copy and
  cannot touch the protected source worktree, Git, GitHub, credentials, or external services. Root
  verifies its host-issued `turn_context`, audits the resulting diff, and is the sole process that
  applies accepted changes. Missing or mismatched model/effort proof halts instead of falling back.
- Agent-lens rows authorize `mutation=none` and no external mutation. Current MultiAgent V2 may
  reapply the parent's permission profile, so the named profile is not claimed as an OS-enforced
  read-only sandbox. Root records a baseline, audits the worktree after every attempt, and treats any
  child-created diff as workflow-integrity failure. Root runs commands; the required concurrency
  tester independently evaluates command evidence and semantics. The installed registry currently
  has no deterministic-validator role, so none is fabricated.
- Each tester row binds its `tester-evidence.v1` result to one protected composite command-output
  record, as required by the installed schema. The record contains the ordered focused tests, Ruff,
  format, mypy, and diff checks; typed cases all reference that same immutable record.
- `vehicle=auto` requests named profiles. Every Sol/max row is actually dispatched in a fresh native
  context and must show matching host-issued model/effort readback before its findings are consumed;
  a mismatch is discarded and halts rather than silently substituting another model. Because the
  current host join may still classify an otherwise matching child receipt as diagnostic rather than
  gate-authoritative, each such row declares preferred independence: root preserves the diagnostic
  review and immediately repeats the same lens through a truthful `verified-workflow-inline` receipt
  with no child/model/effort claim. The inline duplicate supplies gate evidence without pretending to
  be independent; no selected lens is skipped.
- Every P0-P3 finding is fixed by root and returned to the affected role in a new attempt. The
  operator explicitly approved attempt 10 with the model/class assignments above and the consolidation
  scope recorded in this plan. Any P0-P3 finding after attempt 10 halts and pages the operator; there
  is no automatic attempt 11. Any further model/class change requires another approved workflow
  candidate.
- Every no-mutation row runs with `COVERAGE_FILE`, `PYTHONPYCACHEPREFIX`, `UV_CACHE_DIR`,
  `XDG_CACHE_HOME`, and `MYPY_CACHE_DIR` under a unique `/tmp` root, pytest cache disabled, and Ruff
  cache disabled. Root snapshots ordinary and ignored files plus Git control state immediately before
  and after each row; any delta invalidates that row.
- Git mutation, PR creation, merge, issue/board mutation, and completion remain root-only. No deploy,
  credential, production-data, force-push, or branch-deletion action is authorized.
- Workflow intents, receipts, findings, command logs, workspace audits, PR URL, merge SHA, issue close,
  and board reconciliation are retained in the Verified Workflow evidence root and the issue/PR.

## Completion Gate

Completion requires all issue acceptance criteria, zero open P0-P3 doc/code review findings, the
required validator passing with gate-capable evidence, full verification green, one atomic issue PR
merged, issue #350 closed, its Operations card reconciled, outcome node receipt recorded, and the
outcome worktree returned to a clean state except for the next planned wave. The attempt-6 stop-gate
record and attempt-7 closeout must retain the relevant Sol/max `turn_context` evidence, fresh Sol/max
security and architecture receipts, and clean before/after mutation audits for every no-write row.

Attempt 7 repaired and regression-tested the two attempt-6 findings, but its frozen review barrier
did not pass. The Sol/max architecture review recorded one P2 alias/control-flow escape and one P3
contract-documentation drift. The Sol/max security review recorded three P2 conformance bypasses:
unbound or unknown-helper alias mutation, comment-shaped false parallel closes, and fragment-stream
reset after a read-only `lines` access. The Sol/high testing review recorded two P2 proof gaps: the
missing environment/lane consumer matrix for verifier and retry paths, plus the overlapping unknown-
helper alias escape. All review rows used the approved model/effort, shared input digest, and one clean
before/after mutation audit. Per the operating contract, the workflow is halted at the attempt-8
operator gate; no full gate, validator pass, integration, commit, or PR is claimed for attempt 7.
