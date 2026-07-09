# Issue 388: Output Attestation Lie Detector

## Goal

Make external-engine outputs prove their origin before Saga treats them as ran-as-requested evidence:
receipt emitter identity, stable run id, nonzero external token proof, hash-bound output attestation,
liveness join keys, proof-integrity disposition, and run-ledger de-duplication.

## Built

- Added shared `output_attestation.v1` helper in fleet-core.
- Extended `bridge_receipt.v1` with optional `receipt_emitter`, `run_id`, `external_tokens`, and
  `output_attestation` fields while preserving base receipt compatibility.
- Added Saga bridge signature policy for `agy-delegate`, `codex-bridge`, and `http-bridge`.
- Classified missing attestation, hash mismatch, and zero external token receipts as
  `proof-integrity`; `satisfy_gate()` refuses proof-integrity manifests.
- Threaded `bridge_run_key`, external token proof, proof status, and proof errors into run-ledger
  engine facts, with de-duplication by bridge run key.
- Updated HTTP, Agy, and Codex bridge emitters to stamp run ids, token proof, and output attestations.
- Updated Saga/team-execution references, manifest consumer matrix, changelogs, plugin metadata, and
  marketplace registry for release-surface parity.

## Key Decisions

- `bridge_run_key` is additive in `saga.manifest.v1`; consumers use it for liveness joins and
  run-ledger de-duplication without breaking older manifest readers.
- Agy token proof currently uses stdout plus stderr bytes as the available nonzero external-work proxy,
  because the wrapper does not expose provider token usage yet.
- Codex attests `last-message.txt`, HTTP attests the evidence payload, and Agy attests the summary
  payload. Dispatch hash-checks attestations that bind the `evidence` artifact.

## Checks Run

- `uv run python scripts/sync_marketplace.py --check` — passed.
- `uv run python scripts/check_release_surface_parity.py` — passed.
- `uv run pytest tests/test_saga_plugin.py tests/test_agy_plugin.py tests/test_codex_plugin.py -v` —
  45 passed.
- `uv run pytest tests/test_bridge_receipt_drift.py tests/test_fleet_commons_resolution.py -v` —
  38 passed.
- `uv run pytest tests/test_provenance_manifest.py tests/test_manifest_reader.py tests/test_run_ledger.py -v` —
  44 passed.
- `uv run pytest tests/test_output_attestation.py tests/test_bridge_signatures.py tests/test_engine_dispatch_attestation.py tests/test_engine_dispatch_ledger.py tests/test_chaperone_liveness.py tests/test_bridge_lie_detector.py tests/test_saga_engine_dispatch.py tests/test_engine_bridge_http.py tests/test_agy_delegate_contract.py tests/test_codex_delegate_contract.py -v` —
  156 passed.
- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed.
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — passed.
- `python3 -m py_compile plugins/fleet-core/scripts/fleet_commons/output_attestation.py plugins/fleet-core/scripts/fleet_commons/bridge_receipt.py plugins/saga/scripts/bridge_signatures.py plugins/saga/scripts/engine_dispatch.py plugins/saga/scripts/provenance_manifest.py plugins/saga/scripts/engine_bridge_http.py plugins/agy/scripts/agy_delegate.py plugins/codex/scripts/codex_delegate.py` —
  passed.
- `git diff --check` — passed.
- `uv run pytest` — collection blocked before execution because local env is missing `mcp` for
  `tests/test_redis_channel_channel.py` and `tests/test_redis_channel_notifier.py`.
- `uv run pytest --ignore tests/test_redis_channel_channel.py --ignore tests/test_redis_channel_notifier.py` —
  2718 passed, 1 skipped.

## Code Review Round 1

Artifact: `docs/code-reviews/2026-07-09-issue-388-output-attestation-liedetector-code-review.md`.

Findings:

- P1: `bridge_signatures.validate_receipt_signature()` only hash-checked attestations whose
  `artifact` was `evidence`, leaving Agy `summary` and Codex `last-message.txt` receipts able to satisfy
  proof policy without binding the manifest evidence text.
- P1: the liveness helper existed as a pure set comparison, but production dispatch code had no
  ledger-to-manifest join that could detect launched-unconsumed or consumed-unlaunched bridge runs.

Fixes:

- Validate every receipt `output_attestation` against the manifested evidence text, regardless of the
  attestation artifact label.
- Added `bridge_liveness_errors()` in Saga dispatch to compare run-ledger `engine` facts carrying
  `bridge_run_key` against persisted provenance manifests carrying `bridge_run_key`.
- Added regression tests for non-`evidence` artifact hash mismatch and real ledger/manifest liveness
  joins.

Additional checks:

- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — passed.
- `uv run pytest tests/test_chaperone_liveness.py -v` — 5 passed.
- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed.
- `git diff --check` — passed.
- `uv run pytest tests/test_output_attestation.py tests/test_bridge_signatures.py tests/test_engine_dispatch_attestation.py tests/test_engine_dispatch_ledger.py tests/test_chaperone_liveness.py tests/test_bridge_lie_detector.py tests/test_saga_engine_dispatch.py tests/test_engine_bridge_http.py tests/test_agy_delegate_contract.py tests/test_codex_delegate_contract.py -v` — 160 passed.
- `uv run pytest tests/test_bridge_receipt_drift.py tests/test_fleet_commons_resolution.py tests/test_provenance_manifest.py tests/test_manifest_reader.py tests/test_run_ledger.py tests/test_manifest_consumer_matrix.py -v` — 85 passed.
- `uv run python scripts/sync_marketplace.py --check` — passed.
- `COVERAGE_FILE=.coverage.release-388 uv run pytest tests/test_saga_plugin.py tests/test_agy_plugin.py tests/test_codex_plugin.py -v` — 45 passed.

## Code Review Follow-Up

Additional review findings fixed before PR:

- P1: `satisfy_gate()` could accept proof-integrity-failed evidence when no manifest was passed. The
  gate now checks receipt proof-integrity directly from `AdvisoryEvidence`.
- P1: malformed proof-extension fields, such as invalid `output_attestation` digests, were classified
  as `UNPROVEN` through base receipt validation. Dispatch now keeps base receipt failures as
  `UNPROVEN` and classifies proof-extension failures as `PROOF_INTEGRITY`.
- P1: a receipt for a different engine or variant could satisfy proof checks for the dispatched
  evidence. Dispatch now rejects receipt engine/variant mismatches as proof-integrity failures.
- P2: the liveness gate initially compared the repo-wide ledger against one saga manifest store without
  scoping. Gate enforcement now filters liveness to the evidence/manifest bridge key being accepted.
- P2: Codex receipt `external_tokens` fell back to stdout/stderr bytes when parsed token usage was
  absent. Codex now emits `0` without parsed positive token usage, letting the zero-token proof gate
  fail closed.

Additional checks:

- `COVERAGE_FILE=.coverage.issue388-main-* uv run pytest tests/test_output_attestation.py tests/test_bridge_signatures.py tests/test_engine_dispatch_attestation.py tests/test_engine_dispatch_ledger.py tests/test_chaperone_liveness.py tests/test_bridge_lie_detector.py tests/test_saga_engine_dispatch.py tests/test_engine_bridge_http.py tests/test_agy_delegate_contract.py tests/test_codex_delegate_contract.py -v` — 166 passed.
- `COVERAGE_FILE=.coverage.issue388-drift-* uv run pytest tests/test_bridge_receipt_drift.py tests/test_fleet_commons_resolution.py tests/test_provenance_manifest.py tests/test_manifest_reader.py tests/test_run_ledger.py tests/test_manifest_consumer_matrix.py -v` — 85 passed.
- `COVERAGE_FILE=.coverage.issue388-release-* uv run pytest tests/test_saga_plugin.py tests/test_agy_plugin.py tests/test_codex_plugin.py -v` — 45 passed.
- `uv run python scripts/sync_marketplace.py --check` — passed.
- `uv run python scripts/check_release_surface_parity.py` — passed.
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — passed.
- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed.
- `git diff --check` — passed.

## Next Step

Commit the review follow-up fixes, run Saga code-review round 2 against the fixed commit, then
push/open PR issue #388.
