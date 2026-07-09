---
title: Issue #388 Output Attestation Lie-Detector Plan
type: feat
status: active
date: 2026-07-09
origin: docs/sdlc-issue-drafts/plugin-fleet/pf-output-attestation-liedetector.md
---

# Issue #388 Output Attestation Lie-Detector Plan

## Summary

Add the missing proof-of-output layer underneath the existing external-engine safety stack. The work
extends bridge receipts with output attestation and external-token proof, validates those proofs at
dispatch/manifest time, records exactly-once token ledger facts, and adds lie-detector fixtures for
silent Claude fallback and no-op engine bundles.

---

## Problem Frame

Issue #388 was drafted before #383, #384, #390, and #386 landed. Current `engine_dispatch.py` already
requires schema-valid `bridge_receipt.v1` before `RAN_AS_REQUESTED`, refuses `SUBSTITUTED_ENGINE`, and
requires observer corroboration for gated dispatch. Current `bridge_receipt.v1` proves a bridge process
or HTTP call ran, but it does not prove that the accepted output is the exact output that bridge
produced, nor that an external-token-producing run consumed non-zero external tokens.

The remaining gap is narrower and sharper: a bridge can produce a schema-valid receipt while the
bundle output is empty, hash-mismatched, tokenless, or never consumed by the chaperone path. This plan
closes that gap without granting external engines any verifier authority.

---

## Current-State Evidence

| Surface | Current behavior | Evidence |
| --- | --- | --- |
| Advisory evidence | `runner_receipt` is optional on `AdvisoryEvidence`; receipt-less old paths can still exist. | `plugins/saga/scripts/engine_dispatch.py:44` |
| Manifest disposition | `RAN_AS_REQUESTED` is emitted only after `bridge_receipt.v1` validates; invalid/missing receipts become `UNPROVEN`. | `plugins/saga/scripts/engine_dispatch.py:631` |
| Gate satisfaction | `satisfy_gate()` still requires Claude verification plus observer corroboration and refuses `SUBSTITUTED_ENGINE`. | `plugins/saga/scripts/engine_dispatch.py:774` |
| Receipt schema | `bridge_receipt.v1` validates common runner fields and transport-specific runner shape, but has no output hash or token proof fields. | `plugins/fleet-core/scripts/fleet_commons/bridge_receipt.py:34` |
| Ledger writes | `_record_advisory_facts()` appends one `engine` fact per dispatch call and has no receipt/run id de-duplication key. | `plugins/saga/scripts/engine_dispatch.py:526` |
| Bundle proof | Agy already writes `agy.git-proof.v1`; Codex writes bundle diff artifacts, but Saga does not validate a shared output-attestation record. | `plugins/agy/scripts/agy_delegate.py:1502`, `plugins/codex/scripts/codex_delegate.py:1220` |
| Chaperone contract | Team-execution docs describe dispatch and manifest construction, but not producer/consumer liveness by shared receipt id. | `plugins/team-execution/skills/team-execution/references/external-engine-workers.md:220` |

---

## Requirements

R1. Dispatch must reject an external-engine result when the bridge receipt lacks required output
attestation for that engine's registered receipt emitter.

R2. Dispatch must reject empty output-attestation payloads and hash mismatches between the bridge's
declared output artifact and the evidence that would otherwise be accepted or manifested.

R3. Output-attestation failure must produce a distinct machine-readable halt/disposition reason, not
`RAN_AS_REQUESTED`, not a vague `UNPROVEN`, and not a misleading plain fallback.

R4. Bridge receipts for token-producing engines must carry external-token accounting; zero external
tokens must fail loud before the run can satisfy a gate.

R5. Engine token/cost facts must be written at most once per bridge run, even if a retry or requeue sees
the same receipt/run id again.

R6. The producer+consumer liveness contract must fail when a bridge launches and produces a result that
is never consumed into the chaperone manifest path.

R7. The same liveness contract must fail when a result is consumed without a matching launch/receipt
record.

R8. A bridge-signature registry must enumerate every registered `receipt_emitter` and the proof fields
required for it; missing or stale registry entries must fail CI.

R9. Lie-detector fixtures must prove that a Claude-only answer dressed up as delegated output and a
zero-external-call transcript both fail with named proof-integrity errors.

R10. Release surfaces must be updated in the same PR for Saga and any bridge plugin whose emitted
receipt/result shape changes.

R11. External engines remain advisory/generator-only. None of these proof checks lets engine output
satisfy a gate without Claude adjudication and the existing gate checks.

---

## Key Technical Decisions

KTD1. Add proof fields to `bridge_receipt.v1` as validated optional extensions: The base receipt schema
keeps backward compatibility, while `bridge_signatures.py` enforces required proof fields per
`receipt_emitter`. This avoids a broad receipt schema version bump while still making #388 engines fail
loud.

KTD2. Use a shared fleet-commons output-attestation helper: Agy, Codex, and HTTP bridges must produce
the same `output_attestation.v1` shape through `fleet_commons_shim`, avoiding saga-local imports that
would break installed plugin layouts.

KTD3. Introduce a distinct proof-integrity disposition/halt: Invalid output hashes, zero external
tokens, and liveness contradictions are proof failures, not simple missing proof and not ordinary
fallback. Manifest/readers should show them as a named proof-integrity class.

KTD4. De-duplicate ledger writes by bridge run key: The run ledger remains append-only, so de-duplication
must happen before append by deriving a stable `bridge_run_key` from receipt `run_id` or receipt hash and
skipping already-recorded engine facts with the same key.

KTD5. Treat producer and consumer liveness as a joined receipt-run invariant: A launch receipt alone is
not enough, and a manifest alone is not enough. The accepted path needs both sides to reference the same
bridge run key.

KTD6. Keep #390 substitution and #384 observer semantics ahead of proof checks where they already carry
stronger meaning: Existing `DELEGATION_INTEGRITY` and `SUBSTITUTED_ENGINE` dispositions must not be
collapsed into #388 proof-integrity errors.

KTD7. Registry drives bridge proof expectations: `engine-registry.yaml` already carries
`receipt_emitter`; #388 adds a signature registry keyed by that value rather than branching on
`engine_id` in dispatch.

---

## High-Level Technical Design

The proof path is a three-part contract:

1. Bridge emits `bridge_receipt.v1` with `run_id`, `external_tokens`, and `output_attestation`.
2. Dispatch validates the receipt through the base receipt validator plus the emitter-specific
   `bridge_signatures.py` policy before building manifest disposition.
3. Manifest/ledger records carry the bridge run key so producer and consumer liveness can be checked
   deterministically.

ASCII flow:

```text
bridge run
  -> bridge_receipt.v1
      -> output_attestation.v1
      -> external_tokens
      -> run_id / bridge_run_key
  -> engine_dispatch.dispatch()
      -> base receipt validation
      -> bridge-signature validation
      -> proof-integrity halt or advisory evidence
  -> record_dispatch_manifest()
      -> consumer record references same bridge_run_key
  -> satisfy_gate()
      -> Claude verification + observer corroboration + non-proof-failed manifest
```

---

## Implementation Units

### U1. Bridge Signature Registry And Validator

Add the emitter-keyed policy layer that says which receipts require output attestation, token proof,
and transcript signatures.

**Goal:** Create a single source of truth for proof requirements per `receipt_emitter` and a validator
dispatch can call without per-engine branching.

**Requirements:** R1, R3, R8, R11.

**Dependencies:** None.

**Files:** `plugins/saga/references/bridge-signatures.json`,
`plugins/saga/scripts/bridge_signatures.py`, `tests/test_bridge_signatures.py`,
`tests/test_bridge_receipt_drift.py`, `plugins/saga/references/engine-registry.yaml`.

**Approach:** Define signature rows keyed by `receipt_emitter` values already present in
`engine-registry.yaml`: `codex-bridge`, `agy-delegate`, `http-bridge`. Each row declares required
fields (`output_attestation`, `external_tokens`, `run_id`) and zero-token behavior. Add drift tests so
every registry emitter has a signature row and every signature row names a live emitter.

**Patterns to follow:** `tests/test_bridge_receipt_drift.py` for registry-to-emitter drift checks;
`plugins/saga/scripts/engine_registry.py` for closed-vocabulary validation style.

**Test scenarios:** Happy path: a complete codex/agy/http signature validates. Error path: missing
signature row fails CI. Error path: receipt for a required emitter without `output_attestation` returns
a named `proof-integrity` error. Edge case: extra unknown signature row fails reverse drift.

**Verification:** `uv run pytest tests/test_bridge_signatures.py tests/test_bridge_receipt_drift.py -v`.

### U2. Shared Output Attestation Shape And Bridge Emission

Make bridges emit a common output-attestation record that binds the returned evidence to a concrete
output artifact hash.

**Goal:** A bridge result must name the produced artifact, byte count, SHA-256 hash, and empty-output
status in a shared shape.

**Requirements:** R1, R2, R8, R10.

**Dependencies:** U1.

**Files:** `plugins/fleet-core/scripts/fleet_commons/output_attestation.py`,
`plugins/agy/scripts/agy_delegate.py`, `plugins/codex/scripts/codex_delegate.py`,
`plugins/saga/scripts/engine_bridge_http.py`, `tests/test_output_attestation.py`,
`tests/test_agy_apply_policy.py`, `tests/test_codex_delegate_modes.py`,
`tests/test_engine_bridge_http.py`.

**Approach:** Add `output_attestation.v1` builder/validator in fleet-commons and load it through each
plugin's `fleet_commons_shim`. For CLI bridge bundles, hash `diff.patch` or the explicit output artifact
already written by the bridge. For HTTP bridge rows, hash the returned response body/evidence text.
Receipts carry the attestation under a top-level `output_attestation` key and keep `bytes_produced`
consistent with the attested artifact.

**Patterns to follow:** `bridge_receipt.py` for fleet-commons schema helpers; `agy_delegate.py`
`_write_git_proof()` for bundle proof records; `codex_delegate.py` bundle writer tests for preserved
`diff.patch`.

**Test scenarios:** Happy path: agy/codex bundle with non-empty diff emits a valid attestation. Edge
case: read-only reviewer with no diff emits an explicit empty attestation that signature policy can
reject when the row requires output. Error path: attestation hash differs from artifact bytes. Error
path: HTTP bridge evidence text hash mismatch fails validation.

**Verification:** `uv run pytest tests/test_output_attestation.py tests/test_agy_apply_policy.py tests/test_codex_delegate_modes.py tests/test_engine_bridge_http.py -v`.

### U3. Dispatch Proof-Integrity Disposition

Wire signature and attestation validation into dispatch and manifest disposition without weakening
existing receipt, substitution, and observer gates.

**Goal:** A proof-invalid engine result becomes a named proof-integrity halt/disposition before it can
be manifested as accepted evidence.

**Requirements:** R1, R2, R3, R11.

**Dependencies:** U1, U2.

**Files:** `plugins/saga/scripts/engine_dispatch.py`,
`plugins/saga/scripts/provenance_manifest.py`, `plugins/saga/scripts/manifest_reader.py`,
`tests/test_engine_dispatch_attestation.py`, `tests/test_provenance_manifest.py`,
`tests/test_manifest_reader.py`, `plugins/saga/references/saga-spec.md`.

**Approach:** Add a new manifest disposition such as `PROOF_INTEGRITY` / `proof-integrity` and keep
precedence explicit: `DELEGATION_INTEGRITY` and existing halt paths keep their current meaning;
`SUBSTITUTED_ENGINE` stays above ordinary proof validation; proof-integrity catches invalid attestation,
zero-token, and liveness proof failures that are not already classified. `satisfy_gate()` rejects the
new disposition with a specific error. The manifest reader reports it separately from `UNPROVEN`.

**Patterns to follow:** Existing `SUBSTITUTED_ENGINE` and `DELEGATION_INTEGRITY` disposition branches in
`engine_dispatch.py`; strict enum validation in `provenance_manifest.py`.

**Test scenarios:** Happy path: valid receipt plus valid attestation can still become
`RAN_AS_REQUESTED` after existing checks. Error path: empty bundle diff produces `proof-integrity` and
cannot satisfy a gate. Error path: hash mismatch names expected and observed hash prefixes. Regression:
substituted-engine valid receipt still reports `SUBSTITUTED_ENGINE`, not proof-integrity.

**Verification:** `uv run pytest tests/test_engine_dispatch_attestation.py tests/test_provenance_manifest.py tests/test_manifest_reader.py -v`.

### U4. External Token Accounting And Exactly-Once Ledger Writes

Use receipt-level token proof to halt zero-token delegated runs and make run-ledger writes idempotent by
bridge run key.

**Goal:** A token-producing engine cannot claim a real delegated run with zero external tokens, and
retries cannot double-count the same bridge run.

**Requirements:** R4, R5, R8, R11.

**Dependencies:** U1, U2, U3.

**Files:** `plugins/fleet-core/scripts/fleet_commons/bridge_receipt.py`,
`plugins/saga/scripts/engine_dispatch.py`, `plugins/saga/scripts/run_ledger.py`,
`plugins/saga/references/run-fact-ledger.md`, `tests/test_engine_dispatch_ledger.py`,
`tests/test_run_ledger.py`.

**Approach:** Extend receipt emission with optional `external_tokens` and stable `run_id`. Signature
rows declare whether zero is allowed. `engine_dispatch` derives `bridge_run_key` from `run_id` when
present, otherwise from a canonical receipt hash. `_record_advisory_facts()` checks existing `engine`
facts for the same key before appending. The ledger record carries `bridge_run_key`,
`external_tokens`, and proof-integrity status fields for rollups.

**Patterns to follow:** `run_ledger.py` append-only hash-chain semantics; #386 economics fields in
`_economics_fact_fields()` and `tests/test_run_ledger.py`.

**Test scenarios:** Happy path: non-zero external tokens write exactly one engine fact. Error path:
zero external tokens produce proof-integrity halt and still write one auditable engine fact. Called
twice: same receipt/run id writes one engine fact, not two. Edge case: missing `run_id` falls back to a
stable receipt hash key.

**Verification:** `uv run pytest tests/test_engine_dispatch_ledger.py tests/test_run_ledger.py -v`.

### U5. Producer And Consumer Liveness Join

Record and validate that a launched bridge run was actually consumed by the chaperone manifest path, and
that consumed results have a launch record.

**Goal:** The e2e contract fails both launched-but-unconsumed and consumed-but-unlaunched cases.

**Requirements:** R6, R7, R11.

**Dependencies:** U3, U4.

**Files:** `plugins/saga/scripts/engine_dispatch.py`, `plugins/saga/scripts/manifest_store.py`,
`plugins/team-execution/skills/team-execution/references/external-engine-workers.md`,
`tests/test_chaperone_liveness.py`, `tests/test_saga_engine_dispatch.py`.

**Approach:** Stamp `bridge_run_key` onto dispatch evidence provenance and manifest attribution or a
new typed manifest subrecord. Add a small liveness helper that can read launch evidence from receipt or
bundle metadata and consumer evidence from manifest write/readback. `record_dispatch_manifest()` is the
consumer boundary; it must preserve the bridge run key. Tests simulate both halves independently rather
than requiring live external engines.

**Patterns to follow:** `delegation_audit.corroborate()` for fail-closed-but-non-crashing observer
logic; `manifest_store.py` strict read/write boundaries.

**Test scenarios:** Happy path: receipt launch key and manifest consumer key match. Error path:
launched-but-unconsumed returns a named liveness failure. Error path: consumed-but-unlaunched returns a
named liveness failure. Called twice: repeated manifest read stays idempotent.

**Verification:** `uv run pytest tests/test_chaperone_liveness.py tests/test_saga_engine_dispatch.py -v`.

### U6. Lie-Detector Fixtures And Adversarial Regression Suite

Add intentionally fake bridge runs that look plausible until the new proof checks inspect them.

**Goal:** Prove the stack rejects Claude-only answers dressed up as delegated output, zero-call
transcripts, empty bundles, and hash mismatches.

**Requirements:** R2, R4, R8, R9.

**Dependencies:** U1 through U5.

**Files:** `tests/fixtures/bridge-lie-detector/`, `tests/test_bridge_lie_detector.py`,
`tests/test_bridge_signatures.py`, `tests/test_engine_dispatch_attestation.py`,
`plugins/saga/references/engine-dispatch.md`.

**Approach:** Add small fixture transcripts/bundles for: zero external calls, no diff, mismatched hash,
and plausible prose with missing bridge signature. Keep fixtures local and deterministic. Tests assert
named messages such as `proof-integrity`, `zero-external-token`, `output-attestation-mismatch`, and
`launched-unconsumed`.

**Patterns to follow:** `tests/test_bridge_receipt_drift.py` adversarial static-analysis fixtures and
`tests/test_engine_output_trust_boundary.py` malicious-output fixtures.

**Test scenarios:** Error path: zero-call transcript exits non-zero with clone-detected-style message.
Error path: empty-bundle diff fails. Error path: hash-mismatched bundle fails. Error path: Claude-only
answer without signature fails even when prose looks successful.

**Verification:** `uv run pytest tests/test_bridge_lie_detector.py tests/test_bridge_signatures.py tests/test_engine_dispatch_attestation.py -v`.

### U7. Release Surfaces, Journal, And Docs

Update the plugin metadata and operator-facing docs so installed plugin behavior matches the code.

**Goal:** The shipped surfaces describe proof-integrity, bridge signatures, token accounting, and
liveness accurately.

**Requirements:** R10, R11.

**Dependencies:** U1 through U6.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `plugins/agy/.claude-plugin/plugin.json`,
`plugins/agy/CHANGELOG.md`, `plugins/codex/.claude-plugin/plugin.json`,
`plugins/codex/CHANGELOG.md`, `docs/engineering-journal/DECISIONS.md`,
`plugins/saga/references/engine-dispatch.md`,
`plugins/team-execution/skills/team-execution/references/external-engine-workers.md`,
`tests/test_saga_plugin.py`, `tests/test_agy_plugin.py`, `tests/test_codex_plugin.py`.

**Approach:** Bump Saga and any bridge plugin whose emitted receipt/bundle schema changes. Record the
proof-integrity KTDs in the engineering journal. Update dispatch and chaperone docs to say existing
Claude-verifier authority is unchanged.

**Patterns to follow:** #386 release-surface parity and `scripts/sync_marketplace.py`.

**Test scenarios:** Metadata parity: marketplace matches plugin JSON. Changelog drift: changed plugin
has a top entry. Docs drift: `external-engine-workers.md` references bridge-run liveness and the shared
signature registry.

**Verification:** `uv run pytest tests/test_saga_plugin.py tests/test_agy_plugin.py tests/test_codex_plugin.py -v`; `uv run python scripts/sync_marketplace.py --check`; `uv run python scripts/check_release_surface_parity.py`.

---

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Proof-integrity overlaps with existing `UNPROVEN`, `SUBSTITUTED_ENGINE`, or `DELEGATION_INTEGRITY`. | Pin disposition precedence in U3 tests and docs. |
| Receipt extension breaks installed plugin import layout. | Put shared helpers in fleet-commons and load through existing shims. |
| Retry de-duplication hides distinct runs with identical text output. | Prefer receipt `run_id`; use receipt hash fallback only when run id absent, and document that fallback. |
| HTTP rows lack bundle files. | Hash HTTP response evidence text through the same output-attestation shape rather than requiring a diff file. |
| Lie-detector fixtures become brittle transcripts. | Keep fixtures minimal and assert named classifier outcomes, not full transcript formatting. |

---

## Scope Boundaries

- Do not grant external engines gatekeeper/verifier authority; Claude remains verifier-of-record.
- Do not redesign team-execution residency, consensus, or chaperone roster.
- Do not backfill historical manifests or run-ledger facts emitted before this change.
- Do not add live provider billing API integrations; external token proof is receipt/bridge emitted.
- Do not build a general cryptographic signing system. This is hash-bound output attestation and
  bridge-run liveness, not PKI.

## Deferred Follow-Up Work

- Cross-repo or SaaS-level bridge attestation services can become a later issue if local
  `output_attestation.v1` proves insufficient.
- Long-running monitoring dashboards for proof-integrity rates remain outside this implementation PR.

---

## Backend Destination

Destination: `merge`.

Recommended backend: `inline`. The issue profile specifies inline, and the work is repo-local with
strong existing test seams. Escalate to `team-execution` only if implementation discovers a consensus
choice around disposition taxonomy or bridge receipt schema versioning that cannot be resolved with
local tests.

---

## Verification

Focused checks:

```bash
uv run pytest tests/test_bridge_signatures.py tests/test_output_attestation.py tests/test_engine_dispatch_attestation.py -v
uv run pytest tests/test_engine_dispatch_ledger.py tests/test_chaperone_liveness.py tests/test_bridge_lie_detector.py -v
uv run pytest tests/test_provenance_manifest.py tests/test_manifest_reader.py tests/test_run_ledger.py -v
uv run pytest tests/test_agy_apply_policy.py tests/test_codex_delegate_modes.py tests/test_engine_bridge_http.py -v
uv run pytest tests/test_saga_plugin.py tests/test_agy_plugin.py tests/test_codex_plugin.py -v
uv run python scripts/sync_marketplace.py --check
uv run python scripts/check_release_surface_parity.py
```

Before PR:

```bash
uv run --with pytest --with pytest-cov --with fakeredis python -m pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
git diff --check
```
