---
title: Issue #381 Cheap Chaperoning Plan
type: feat
status: active
date: 2026-07-09
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json
---

# Issue #381 Cheap Chaperoning Plan

## Summary

Add the chaperone-economics layer around external-engine dispatch: same-engine batching, explicit
verifiability signals, evidence-size tier escalation, acceptance sampling, and content-addressed payload
caching. The implementation keeps external engines advisory-only and records every chaperone decision in
existing Saga/team-execution evidence surfaces.

## Problem Frame

Issue #381 is requirements-ready and traces five surviving T1 ideas into one coherent capability:
`T1-F1-6`, `T1-F1-5`, `T1-F3-4`, `T1-F5-4`, and `T1-F2-7`. The current protocol already has one
Claude chaperone own resolve, dispatch, verify, apply, test, and manifest for an external-engine unit
(`plugins/team-execution/skills/team-execution/references/external-engine-workers.md:16`), and the gate
still requires Claude verification plus observer corroboration (`plugins/saga/scripts/engine_dispatch.py:628`).

What is missing is the cost-control layer that makes that protocol scale: batching homogeneous units
under one chaperone context load, lowering review effort only when a real test oracle exists, escalating
review when evidence volume grows, sampling low-risk batches without silently accepting defects, and
avoiding redundant payload assembly for identical redispatches.

## Requirements

R1. Same-engine offload units can be grouped into one chaperone context package without giving the
external engine direct wave-scheduling, git, or gate authority.

R2. Every unit inside a batch still emits distinct per-unit evidence and a distinct manifest path; a
batch-level success must not stand in for per-unit `verified_by_claude=True`.

R3. Chaperone review tier is keyed by explicit verifiability: test-gated offload units may use a
ratify-only cheaper chaperone path, while unverifiable units keep full chaperone review.

R4. Evidence-size escalation is visible and recorded. A large evidence payload or large batch may propose
or perform only one legal rung of chaperone-tier escalation, never a silent arbitrary retier.

R5. Acceptance sampling is deterministic from a WEAK/MODERATE/STRONG verifiability rating. A sampled
defect escalates the remaining unsampled batch to full review.

R6. Payload assembly cache hits are keyed by `unit_id`, protocol hash, and context hash, preserve the
exact assembled payload bytes, and expose hit/miss provenance without module-global state.

R7. Existing external-engine safety invariants stay intact: external output is advisory input, dispatch
payload preservation still holds, `satisfy_gate()` remains the gate consumer, and substituted or
uncorroborated evidence still cannot satisfy gates.

R8. Saga and team-execution release surfaces stay synchronized: plugin metadata, marketplace metadata,
changelogs, and drift-guard tests all tell the same story.

## Key Technical Decisions

KTD1. Put chaperone economics in a small pure Saga helper, not in prose-only docs: a new
`plugins/saga/scripts/chaperone_economics.py` should hold batch grouping, verifiability, escalation, and
sampling decisions. `engine_dispatch.py` should only stamp the resulting decision data into advisory
evidence provenance at the dispatch boundary.

KTD2. Add an explicit `Unit.verifiability` field instead of inferring test-gated status from plan prose:
`execution_spec.py` already validates engine selectors and carries per-unit tiers; an explicit
`verifiability: test-gated|unverifiable` field makes the offload tier split auditable, serializable, and
testable. Absent values must preserve today's behavior by defaulting external-engine units to
`unverifiable`.

KTD3. Batch only homogeneous external-engine offload units: a batch key must include resolved
engine/variant or selector, intent, chaperone tier mode, and compatible write/test handling. Mixed-engine,
second-opinion, substituted, or sandbox-incompatible units fall back to one-unit packages.

KTD4. Reuse existing tier vocabulary and one-rung escalation: the plan table is generated from
`tier_policy.json`, and `execution_spec.escalate_tier()` already models the one-rung rule. The
implementation must update the registry/render path rather than hand-editing the generated plan table.

KTD5. Record chaperone decisions without changing `saga.manifest.v1`: use
`AdvisoryEvidence.provenance["chaperone"]` for chaperone tier, verifiability, sampling, batch id, and
cache hit/miss. Per-unit manifests remain distinct v1 manifests with existing attribution/disposition
semantics; do not add manifest fields named verdict, authority, gate, or any equivalent gate surface.

KTD6. Payload caching is run-scoped and content-addressed: extend `RunMemo` or add a sibling memo object
owned by the caller. Do not add module-global cache state, filesystem caches, or context truncation.

## High-Level Technical Design

The change adds a policy layer beside the existing resolver/dispatch layer, then documents how
team-execution consumes it.

1. `execution_spec.py` accepts and emits `Unit.verifiability`, validates its closed vocabulary, and
keeps the default backward-compatible.
2. `chaperone_economics.py` accepts unit descriptors and returns typed decisions: batch key, review
mode, proposed tier, sample set, full-review escalation flag, and provenance payload.
3. `engine_resolver.py` accepts a run-scoped payload memo when resolving a unit and reuses assembled
payload only when protocol and context hashes match the same unit id.
4. `engine_dispatch.py` threads the chaperone decision into `AdvisoryEvidence.provenance` without
changing manifest schema or which evidence can satisfy a gate.
5. `external-engine-workers.md`, the `/plan` tier table source, and release surfaces document the new
contract.

### Pinned Policy Constants

These constants are deliberately simple and testable for the first shipped version.

| Policy | Value | Reason |
| --- | --- | --- |
| Verifiability values | `test-gated`, `unverifiable` | Closed vocabulary prevents prose inference. |
| Test-gated review mode | `ratify-only` | Chaperone confirms test oracle and provenance instead of rereading every line at full depth. |
| Unverifiable review mode | `full-review` | Chaperone remains the only real gate for opaque prose/output. |
| Evidence-size escalation | `evidence_bytes > 32768` or `batch_size > 5` proposes one rung | Keeps the first threshold concrete while avoiding arbitrary multi-rung climbs. |
| WEAK sample fraction | `1.0` | Weak batches get full review; sampling buys nothing when confidence is low. |
| MODERATE sample fraction | `0.5`, rounded up, minimum `2` | Review enough items to catch common batch-shape defects without full cost. |
| STRONG sample fraction | `0.2`, rounded up, minimum `1` | Strong mechanically verifiable batches still get a sentinel review. |
| Sample selection | stable sort by `unit_id`, then deterministic hash by `batch_id` for ties | Re-runs select the same units without persisting hidden state. |
| Sampled defect consequence | all remaining unsampled units become `full-review` | No silent pass-through after one sampled defect. |

## Implementation Units

### U1. Add Chaperone Economics Policy Helper

Create the pure decision layer that the docs and dispatch surfaces can share.

**Goal:** Provide testable functions for same-engine batch grouping, verifiability-mode selection,
evidence-size escalation, and WEAK/MODERATE/STRONG acceptance sampling.

**Requirements:** R1, R3, R4, R5, R7.

**Dependencies:** None.

**Files:** `plugins/saga/scripts/chaperone_economics.py`; `tests/test_chaperone_economics.py`.

**Approach:** Define small frozen dataclasses or typed dicts for unit inputs and chaperone decisions.
The helper should be pure: no GitHub, filesystem, network, or engine calls. Use closed values for
`verifiability`, `review_mode`, and `sample_rating`; reject unknowns loudly.

**Patterns to follow:** `engine_resolver.RunMemo` is explicit and caller-owned
(`plugins/saga/scripts/engine_resolver.py:55`); `execution_spec.escalate_tier()` is the existing
one-rung model (`plugins/saga/scripts/execution_spec.py:1889`).

**Test scenarios:** Happy path: three units with the same engine, intent `offload`, compatible
verifiability, and clean sample rating produce one batch decision and per-unit ids remain intact.
Edge: mixed engine, second-opinion intent, or incompatible sandbox/write metadata splits into separate
one-unit batches. Failure: unknown verifiability or sample rating raises a clear error. Sampling:
WEAK/MODERATE/STRONG map to deterministic fractions and a sampled defect flips the decision to full
review for unsampled units.

**Verification:** `uv run pytest tests/test_chaperone_economics.py -q` proves policy behavior without
requiring an external engine.

### U2. Add Explicit Verifiability To Execution Specs And Plan Tier Policy

Make "test-gated" a first-class authored signal rather than prose.

**Goal:** Let plan/workflow authors mark external-engine units as `test-gated` or `unverifiable`, then
render the correct chaperone tier recommendation.

**Requirements:** R3, R4, R7.

**Dependencies:** U1.

**Files:** `plugins/saga/scripts/execution_spec.py`; `tests/test_saga_execution_spec.py`;
`plugins/fleet-core/scripts/fleet_commons/tier_policy.json`; `plugins/saga/skills/plan/SKILL.md`;
`tests/test_tier_resolver.py`; `tests/test_tier_vocab_single_source.py`.

**Approach:** Add optional `Unit.verifiability` with closed values. Default external-engine units to
`unverifiable` when the field is absent so older specs keep the current full-review posture. Update the
tier-policy source and renderer so the generated `/plan` table gains a test-gated offload row, instead
of hand-editing the generated block.

**Patterns to follow:** `Unit.engine_intent` already defaults to `offload` when a unit carries `engine`
or `capability` (`plugins/saga/scripts/execution_spec.py:888`). The generated tier table is guarded
against manual drift (`plugins/saga/skills/plan/SKILL.md:298`).

**Test scenarios:** Happy path: an external-engine unit with `verifiability: test-gated` validates and
emits the cheaper ratify-only tier marker. Edge: absent verifiability defaults to `unverifiable` and
emits byte-compatible existing output where possible. Failure: invalid verifiability value fails spec
validation. Drift guard: rendered plan table equals the tier-policy renderer output.

**Verification:** `uv run pytest tests/test_saga_execution_spec.py tests/test_tier_resolver.py tests/test_tier_vocab_single_source.py -q`.

### U3. Document Batched Chaperone Context Packages

Update the team-execution protocol that operators and future workers read.

**Goal:** Extend the external-engine worker contract to cover batch context packages, per-unit manifest
preservation, verifiability, escalation, and sampling behavior.

**Requirements:** R1, R2, R3, R4, R5, R7.

**Dependencies:** U1, U2.

**Files:** `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`;
`plugins/team-execution/skills/team-execution/references/worker-manifest.md`;
`tests/test_team_execution_plugin.py`.

**Approach:** Add a batch context-package variant beside the existing single-unit package. The package
should name `batch_id`, `unit_ids`, per-unit `selector`, `intent`, `verifiability`, `write_set`,
`test_oracle`, and manifest identity. State explicitly that batching amortizes the chaperone context
load only; it does not merge unit manifests, gate evidence, or let an engine touch the tree.

**Patterns to follow:** `external-engine-workers.md` already defines the one-worker chaperone ownership
boundary (`plugins/team-execution/skills/team-execution/references/external-engine-workers.md:16`) and
the context package fields (`plugins/team-execution/skills/team-execution/references/external-engine-workers.md:38`).

**Test scenarios:** Documentation contract test asserts the reference contains the batch fields,
per-unit manifest invariant, sampled-defect full-review rule, and no new gatekeeper wording. Edge:
historical changelog mentions are excluded the same way existing team-execution tests handle historical
terms.

**Verification:** `uv run pytest tests/test_team_execution_plugin.py -q`.

### U4. Thread Chaperone Decisions Through Dispatch Evidence

Record the advisory decision data at the dispatch boundary without weakening gates or changing the
manifest schema.

**Goal:** Add explicit evidence provenance for chaperone tier, review mode, batch id, sampling decision,
cache hit/miss, and evidence-size escalation to each unit's advisory evidence.

**Requirements:** R2, R4, R5, R7.

**Dependencies:** U1, U2.

**Files:** `plugins/saga/scripts/engine_dispatch.py`; `tests/test_saga_engine_dispatch.py`.

**Approach:** Add an optional chaperone decision argument to `dispatch()` that writes advisory metadata
under `evidence.provenance["chaperone"]`. Preserve default behavior exactly when no decision is supplied.
Do not modify `provenance_manifest.py`; distinct per-unit manifests remain v1 manifests written by the
existing `record_dispatch_manifest()` path.

**Patterns to follow:** `dispatch(expected_identity=...)` stamps optional provenance without changing
default behavior (`tests/test_saga_engine_dispatch.py:1008`); `satisfy_gate()` refuses evidence unless
Claude verification and observer corroboration hold (`plugins/saga/scripts/engine_dispatch.py:628`).

**Test scenarios:** Happy path: a chaperone decision appears on evidence provenance for every unit in a
batch. Edge: no decision supplied leaves provenance identical to today. Failure: a sampled defect marks
remaining units full-review, and unsampled units cannot be marked verified without that recorded policy
decision. Safety: `provenance_manifest.py` has no schema diff and no verdict/gate authority surface.

**Verification:** `uv run pytest tests/test_saga_engine_dispatch.py -q`.

### U5. Add Run-Scoped Content-Addressed Payload Cache

Avoid redundant assembly while preserving byte identity.

**Goal:** Cache `_assemble_payload` output by `unit_id`, protocol hash, and context hash for redispatches
inside a run.

**Requirements:** R6, R7.

**Dependencies:** U1.

**Files:** `plugins/saga/scripts/engine_resolver.py`; `tests/test_saga_engine_resolver.py`.

**Approach:** Extend `RunMemo` or add `PayloadMemo` with `payload(unit_id, protocol_hash, context_hash)`
and `store_payload(...)`. Thread an optional unit id from `task_context` into `_resolution_from_entry()`.
When no memo or no unit id is supplied, behavior stays identical. On cache hit, still run the same
payload preservation check before returning.

**Patterns to follow:** Existing `RunMemo` caches only caller-owned run-scoped data and keeps
`memo=None` byte-identical (`plugins/saga/scripts/engine_resolver.py:55`). `_assemble_payload` currently
preserves protocol bytes and has one narrow responsibility (`plugins/saga/scripts/engine_resolver.py:559`).

**Test scenarios:** Happy path: same unit id, same protocol, same context hits cache and returns the
same bytes. Edge: context change, protocol change, or unit id change misses cache. Failure: non-string
context still raises the existing `RegistryError`. Byte preservation: cache hit still passes the
protocol preservation assertion.

**Verification:** `uv run pytest tests/test_saga_engine_resolver.py -q`.

### U6. Update Release Surfaces And Drift Guards

Make installed plugin metadata reflect the behavior change.

**Goal:** Bump both affected plugin release surfaces and update changelogs/tests in the same PR.

**Requirements:** R8.

**Dependencies:** U2, U3, U4, U5.

**Files:** `plugins/saga/.claude-plugin/plugin.json`; `plugins/team-execution/.claude-plugin/plugin.json`;
`.claude-plugin/marketplace.json`; `plugins/saga/CHANGELOG.md`;
`plugins/team-execution/CHANGELOG.md`; `tests/test_saga_plugin.py`;
`tests/test_team_execution_plugin.py`.

**Approach:** Bump `saga` and `team-execution` versions once each. Keep marketplace descriptions and
test assertions synchronized with plugin metadata. Mention issue #381 and the five shipped economics
pieces in changelogs.

**Patterns to follow:** Saga metadata is currently pinned at `0.75.5` in
`tests/test_saga_plugin.py:42`; team-execution metadata is pinned at `2.13.0` in
`tests/test_team_execution_plugin.py:59`.

**Test scenarios:** Metadata tests prove plugin version equals marketplace version. Release-surface
parity scripts pass. Changelog entries name batching, verifiability, escalation, sampling, and payload
cache.

**Verification:** `uv run pytest tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match tests/test_team_execution_plugin.py::test_team_execution_metadata_is_v2_and_marketplace_matches -q`; `uv run python scripts/sync_marketplace.py --check`; `uv run python scripts/check_release_surface_parity.py`.

## Scope Boundaries

- Do not let external engines become gatekeepers or reviewers of record.
- Do not add a new external-engine executor kind to team-execution; the ordinary Claude chaperone remains
  the owner.
- Do not add persistent filesystem or module-global payload caches.
- Do not solve broader team-side worker-cache scheduling; this cache is unit/payload-scoped only.
- Do not add self-tuning run-fact feedback or registry calibration.
- Do not change live provider credential semantics from issue #389.

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Sampling could look like silent acceptance | Require a recorded sampling decision before unsampled units can be marked verified; sampled defect forces full review. |
| Verifiability inference could be wrong | Use explicit `Unit.verifiability`; default absent values to `unverifiable`. |
| Generated tier table drifts | Update `tier_policy.json`/renderer path and run the existing tier drift guards. |
| Manifest schema change grows blast radius | Prefer existing advisory provenance/attribution surfaces; if schema must change, make it versioned and guard no-verdict fields. |
| Cache hides payload mutation | Key by unit id plus protocol/context hashes and rerun byte-preservation checks on cache hits. |

## Sources

| Source | Evidence |
| --- | --- |
| Issue #381 | Requirements-ready issue with labels `needs-plan`, `enhancement`, `tier-structural`; parser reports `can_plan=true`. |
| `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` | Source ideas `T1-F1-6`, `T1-F1-5`, `T1-F3-4`, `T1-F5-4`, `T1-F2-7`. |
| `plugins/team-execution/skills/team-execution/references/external-engine-workers.md:16` | Existing chaperone ownership contract. |
| `plugins/saga/scripts/engine_resolver.py:55` | Existing caller-owned `RunMemo` pattern. |
| `plugins/saga/scripts/engine_resolver.py:559` | Current uncached payload assembly seam. |
| `plugins/saga/scripts/engine_dispatch.py:628` | Existing gate check remains the authority. |
| `plugins/saga/skills/plan/SKILL.md:298` | Generated tier table must not be hand-edited. |
| `tests/test_saga_plugin.py:42` and `tests/test_team_execution_plugin.py:59` | Current release-surface version guards. |

## Verification Plan

Run focused checks first:

- `uv run pytest tests/test_chaperone_economics.py tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_saga_execution_spec.py tests/test_team_execution_plugin.py tests/test_saga_plugin.py -q`
- `uv run pytest tests/test_tier_resolver.py tests/test_tier_vocab_single_source.py -q`
- `uv run ruff check plugins/saga/scripts/chaperone_economics.py plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_dispatch.py plugins/saga/scripts/execution_spec.py tests/test_chaperone_economics.py tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_saga_execution_spec.py tests/test_team_execution_plugin.py tests/test_saga_plugin.py`
- `uv run mypy plugins/saga/scripts/chaperone_economics.py plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_dispatch.py plugins/saga/scripts/execution_spec.py tests/test_chaperone_economics.py tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_saga_execution_spec.py --ignore-missing-imports`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python scripts/check_release_surface_parity.py`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`

Use full `uv run pytest -q` as CI/closeout evidence if the local environment has the redis-channel `mcp`
dependency available; otherwise record that local blocker and rely on GitHub Actions for the full matrix.
