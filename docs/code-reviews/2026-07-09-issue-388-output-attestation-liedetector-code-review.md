# Code Review: Issue 388 Output Attestation Lie Detector

| Field | Value |
| --- | --- |
| Target | `work/388-output-attestation-liedetector` |
| Reviewed revision | `71233f0b9c83b3debc78ca72da5afa4d0e5a3b90` |
| Base | `origin/main` merge-base `237415446a2d93f304a7fbefdea3366020980b9d` |
| Linked issue | `#388` |
| Plan | `docs/plans/2026-07-09-issue-388-output-attestation-liedetector-plan.md` |
| Work session | `docs/work-sessions/2026-07-09-issue-388-output-attestation-liedetector.md` |
| Blocked | Yes |

## Scope Check

Scope Check: REQUIREMENTS MISSING

Intent: add proof-of-origin, output attestation, external token accounting, liveness, and lie-detector
coverage for external-engine bridge outputs.

Delivered: the diff adds receipt proof fields, proof-integrity disposition, emitter policy, bridge
emitter updates, token fact de-duplication, release surfaces, and tests, but two safety requirements are
not yet enforced by production code.

## Plan Completion

- U1 Bridge Signature Registry And Validator: DONE. `plugins/saga/references/bridge-signatures.json`
  and `plugins/saga/scripts/bridge_signatures.py` exist with emitter-keyed policy and drift tests.
- U2 Shared Output Attestation Shape Bridge Emission: PARTIAL. Bridge emitters stamp attestations, but
  non-HTTP artifacts are not bound to the manifested evidence during validation.
- U3 Dispatch Proof-Integrity Disposition: PARTIAL. Proof-integrity exists and blocks gates, but the
  hash-bound evidence check does not cover Agy/Codex artifacts.
- U4 Engine Token Accounting Exactly Once: DONE. Run-ledger facts carry `bridge_run_key`,
  `external_tokens`, and proof status, with de-duplication before append.
- U5 Producer Consumer Liveness Join: NOT-DONE. The diff adds a helper and tests for set comparison, but
  no production path joins launched keys to consumed manifest keys.
- U6 Lie-Detector Fixtures: PARTIAL. Zero-token and missing-emitter fixtures exist; the CLI artifact
  mismatch case is not covered for Agy/Codex.
- U7 Release Surfaces, Journal, Docs: DONE. Plugin metadata, changelogs, marketplace, Saga references,
  team-execution docs, and work-session are updated.

COMPLETION: 3/7 DONE, 3 PARTIAL, 1 NOT-DONE, 0 CHANGED, 0 UNVERIFIABLE

## Findings

### P1

| # | File | Issue | Reviewer | Confidence | Route |
| --- | --- | --- | --- | --- | --- |
| 1 | `plugins/saga/scripts/bridge_signatures.py:88` | Output attestation only hash-checks artifacts named `evidence`, while Agy and Codex emit `summary` / `last-message.txt`; tampered or empty manifested evidence can still pass proof-integrity. | correctness/security | 100 | manual |
| 2 | `plugins/saga/scripts/bridge_signatures.py:100` | Producer/consumer liveness is only a helper; no production join compares launched run facts to consumed manifests, so launched-unconsumed and consumed-unlaunched contradictions do not fail any gate. | correctness/reliability | 100 | manual |

## Finding Details

### 1. CLI attestations are not bound to manifested evidence

`bridge_signatures.validate_receipt_signature()` passes `expected_content` only when
`attestation.get("artifact") == "evidence"` (`plugins/saga/scripts/bridge_signatures.py:88`). The HTTP
bridge uses `artifact="evidence"`, but Agy emits `artifact="summary"`
(`plugins/agy/scripts/agy_delegate.py:1497`) and Codex emits `artifact="last-message.txt"`
(`plugins/codex/scripts/codex_delegate.py:1429`). Those receipt attestations validate shape and
non-emptiness but skip the hash comparison against `evidence.evidence`, so a caller can manifest empty or
different evidence while keeping a non-empty attested artifact.

Impact: R2 and the lie-detector goal are not met for the CLI bridges; `RAN_AS_REQUESTED` can be assigned
without proving the accepted evidence is the bytes the bridge attested.

Suggested fix: make emitter policy declare which artifact must bind to `evidence_text`, or always compare
the attested artifact to `evidence_text` for required bridge output. Add Agy/Codex mismatch tests.

Validation: Real in new code, introduced by this diff, and not handled elsewhere. The only
`expected_content` binding is the artifact-name check above.

### 2. Liveness contract is not wired into a production check

`bridge_signatures.liveness_errors()` can identify launched-unconsumed and consumed-unlaunched keys
(`plugins/saga/scripts/bridge_signatures.py:100`), but repository search shows it is used only by
`tests/test_chaperone_liveness.py`. Run-ledger facts and manifests now carry `bridge_run_key`, but no
production function or gate reads both stores and applies the helper.

Impact: R6/R7 say these contradictions must fail. Today they only fail if a test calls the helper
directly; normal dispatch/manifest/ledger flows can leave a launched key unconsumed, or a consumed key
without a launch fact, without surfacing proof-integrity.

Suggested fix: add a production liveness join over run-ledger engine facts and manifest store records
that returns/raises the `proof-integrity` errors, and test it with real ledger and manifest records.

Validation: Real in new code, introduced by this diff, and not handled elsewhere. The only call sites are
the direct helper tests.

## Coverage

Selected lenses: correctness, security, testing, maintainability/conventions, reliability, and
adversarial/red-team.

Checks reviewed:

- `uv run pytest --ignore tests/test_redis_channel_channel.py --ignore tests/test_redis_channel_notifier.py`
  passed with 2718 passed, 1 skipped.
- `uv run pytest` remains environment-blocked because local `mcp` is absent for two redis-channel tests.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy plugins/ scripts/ tests/
  --ignore-missing-imports`, `python3 -m py_compile ...`, `git diff --check`, marketplace check, and
  release parity check passed before this review.

Residual risk: no PR should open until the P1 findings are fixed and this code-review gate is rerun
against the new HEAD.
