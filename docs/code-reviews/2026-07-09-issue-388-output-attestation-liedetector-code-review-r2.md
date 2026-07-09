# Issue 388 Output Attestation Lie Detector Code Review R2

| Field | Value |
| --- | --- |
| Target | `work/388-output-attestation-liedetector` |
| Reviewed revision | `10dab6b3785ebdb7322108de3248b2de6306f51a` |
| Base | `origin/main` merge-base `237415446a2d93f304a7fbefdea3366020980b9d` |
| Linked issue | `#388` |
| Plan | `docs/plans/2026-07-09-issue-388-output-attestation-liedetector-plan.md` |
| Work session | `docs/work-sessions/2026-07-09-issue-388-output-attestation-liedetector.md` |
| Prior review | `docs/code-reviews/2026-07-09-issue-388-output-attestation-liedetector-code-review.md` |
| Blocked | No |

## Scope Check

CLEAN.

Intent: make external-engine outputs prove origin, token activity, attested output bytes, and
producer/consumer liveness before Saga treats them as ran-as-requested evidence.

Delivered: added shared output attestations, bridge signature policy, proof-integrity disposition and
gate refusal, bridge-run liveness enforcement, receipt identity checks, strict Codex token proof, ledger
de-duplication, docs/release surfaces, and regression coverage.

## Plan Completion

| Unit | Status | Evidence |
| --- | --- | --- |
| U1 Bridge signature registry | DONE | `plugins/saga/references/bridge-signatures.json`; `plugins/saga/scripts/bridge_signatures.py`; `tests/test_bridge_signatures.py`. |
| U2 Shared output attestation and bridge emission | DONE | `plugins/fleet-core/scripts/fleet_commons/output_attestation.py`; Agy/Codex/HTTP bridge receipt emission. |
| U3 Dispatch proof-integrity disposition | DONE | `plugins/saga/scripts/provenance_manifest.py`; `plugins/saga/scripts/engine_dispatch.py`; `tests/test_engine_dispatch_attestation.py`. |
| U4 Token accounting and exactly-once ledger writes | DONE | run-ledger proof fields and de-dupe in `plugins/saga/scripts/engine_dispatch.py`; `tests/test_engine_dispatch_ledger.py`. |
| U5 Producer and consumer liveness join | DONE | scoped `bridge_liveness_errors()` plus `satisfy_gate(..., ledger=..., store=...)`; `tests/test_chaperone_liveness.py`. |
| U6 Lie-detector regressions | CHANGED | Deterministic in-test adversarial fixtures rather than a fixture directory; covered by `tests/test_bridge_lie_detector.py`, `tests/test_engine_dispatch_attestation.py`, and `tests/test_chaperone_liveness.py`. |
| U7 Release surfaces, journal, and docs | DONE | plugin metadata, changelogs, marketplace, dispatch docs, team-execution docs, and engineering journal updated. |

COMPLETION: 6 DONE, 1 CHANGED, 0 PARTIAL, 0 NOT-DONE, 0 UNVERIFIABLE.

## Review Findings

No P0/P1/P2/P3 findings remain.

Previously validated findings were rechecked and fixed:

- Non-`evidence` artifacts are hash-bound to manifested evidence.
- Liveness is wired into the production gate path with explicit ledger/store inputs.
- `satisfy_gate()` rejects proof-integrity failures even without a manifest.
- Malformed proof-extension fields classify as `PROOF_INTEGRITY`, not `UNPROVEN`.
- Cross-engine or cross-variant receipts are proof-integrity failures.
- Codex no longer treats stdout/stderr bytes as external token proof.
- Liveness gate checks are scoped to the current bridge key to avoid repo-wide ledger false positives.

## Review Lenses

| Lens | Result |
| --- | --- |
| correctness / reliability | Pass |
| security / API contract | Pass |
| testing | Pass |
| maintainability / conventions | Pass |
| adversarial / agent-native | Pass |

## Checks

- `COVERAGE_FILE=.coverage.issue388-main-* uv run pytest tests/test_output_attestation.py tests/test_bridge_signatures.py tests/test_engine_dispatch_attestation.py tests/test_engine_dispatch_ledger.py tests/test_chaperone_liveness.py tests/test_bridge_lie_detector.py tests/test_saga_engine_dispatch.py tests/test_engine_bridge_http.py tests/test_agy_delegate_contract.py tests/test_codex_delegate_contract.py -v` — 166 passed.
- `COVERAGE_FILE=.coverage.issue388-drift-* uv run pytest tests/test_bridge_receipt_drift.py tests/test_fleet_commons_resolution.py tests/test_provenance_manifest.py tests/test_manifest_reader.py tests/test_run_ledger.py tests/test_manifest_consumer_matrix.py -v` — 85 passed.
- `COVERAGE_FILE=.coverage.issue388-release-* uv run pytest tests/test_saga_plugin.py tests/test_agy_plugin.py tests/test_codex_plugin.py -v` — 45 passed.
- `uv run python scripts/sync_marketplace.py --check` — passed.
- `uv run python scripts/check_release_surface_parity.py` — passed.
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — passed.
- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed.
- `git diff --check` — passed.

## Coverage

Suppressed findings: none.

Residual risks: live external provider token accounting remains limited by what bridges expose. Agy still
uses stdout/stderr byte count as a nonzero external-work proxy because it does not expose provider token
usage yet; Codex now fails closed to zero when parsed token usage is absent.

Testing gaps: full `uv run pytest` still requires the local `mcp` package for redis-channel tests; the
prior broad run with those tests ignored passed 2718 tests and 1 skipped.

> Verdict: clean for PR.
