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

## Next Step

Commit the scoped implementation, run the Saga code-review gate against the committed diff, address
any findings, then push/open PR for issue #388.
