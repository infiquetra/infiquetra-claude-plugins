"""Dispatch proof-integrity tests for output attestation (#388)."""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R = _load("engine_resolver")
D = _load("engine_dispatch")
PM = D.pm
BR = D._bridge_receipt
OA = D.fleet_commons_shim.load("output_attestation")


def _reconciliation(evidence: Any) -> Any:
    return D.reconcile.build_result(
        reconciliation_id=f"attestation-{id(evidence)}",
        execution_id=evidence.execution_id,
        intent=evidence.intent,
        adjudicator_id="claude",
        evidence_digest=evidence.evidence_digest,
        source_finding_ids=evidence.source_finding_ids,
        items=tuple(
            D.reconcile.ReconciliationItem(
                source_finding_id=finding_id,
                status=D.reconcile.ReconciliationStatus.RECONCILED,
                adjudicator_id="claude",
                rationale="Claude reconciled the attested advisory evidence.",
            )
            for finding_id in evidence.source_finding_ids
        ),
    )


def _resolution() -> Any:
    return R.Resolution(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        effort="high",
        recipe="recipe",
        protocol=["Run read-only."],
        payload="Run read-only.",
        write_capable=False,
        fallback=None,
        halt=None,
    )


def _receipt(
    *,
    output: str = "external finding",
    attested_output: str | None = None,
    tokens: int = 42,
    emitter: str = "codex-bridge",
    artifact: str = "evidence",
) -> dict[str, Any]:
    attested = output if attested_output is None else attested_output
    receipt: dict[str, Any] = BR.emit_receipt(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        transport="cli",
        wall_time_s=0.5,
        bytes_produced=len(output.encode("utf-8")),
        runner={"pid": 4242, "argv": ["codex"], "exit_code": 0},
        receipt_emitter=emitter,
        run_id="proof-run-1",
        external_tokens=tokens,
        output_attestation=OA.emit_attestation(artifact=artifact, content=attested),
    )
    return receipt


def _manifest(receipt: dict[str, Any], *, output: str = "external finding") -> Any:
    evidence = D.dispatch(
        _resolution(),
        runner=lambda _invocation: {"status": "ok", "output": output, "receipt": receipt},
    )
    return D.build_dispatch_manifest(
        evidence,
        execution_id="exec-proof",
        saga_ref="saga-1",
        created_at="2026-07-09T00:00:00Z",
    )


def test_valid_attestation_can_run_as_requested() -> None:
    manifest = _manifest(_receipt())

    assert manifest.disposition is PM.Disposition.RAN_AS_REQUESTED
    assert manifest.bridge_run_key == "proof-run-1"


def test_canonical_codex_variant_matches_receipt_evidence_and_manifest() -> None:
    resolution = dataclasses.replace(
        _resolution(),
        variant="gpt-5.6-sol-high",
        effort="high",
        invocation={
            "via": "codex:delegate",
            "recipe": "recipe",
            "write_capable": False,
            "model": "gpt-5.6-sol",
            "effort": "high",
        },
    )
    receipt = _receipt()
    receipt["variant"] = "gpt-5.6-sol-high"
    evidence = D.dispatch(
        resolution,
        runner=lambda invocation: {
            "status": "ok",
            "output": "external finding",
            "receipt": receipt,
        },
    )
    manifest = D.build_dispatch_manifest(
        evidence,
        execution_id="exec-canonical",
        saga_ref="saga-1",
        created_at="2026-07-09T00:00:00Z",
        effort=resolution.effort,
    )

    assert evidence.variant == "gpt-5.6-sol-high"
    assert evidence.runner_receipt["variant"] == evidence.variant
    assert manifest.attribution.identity == "codex/gpt-5.6-sol-high"
    assert manifest.attribution.effort == "high"


def test_hash_mismatch_becomes_proof_integrity() -> None:
    manifest = _manifest(_receipt(attested_output="different"))

    assert manifest.disposition is PM.Disposition.PROOF_INTEGRITY
    assert "output-attestation-mismatch" in manifest.disposition_note


def test_non_evidence_artifact_hash_mismatch_becomes_proof_integrity() -> None:
    manifest = _manifest(_receipt(artifact="summary", attested_output="different"))

    assert manifest.disposition is PM.Disposition.PROOF_INTEGRITY
    assert "output-attestation-mismatch" in manifest.disposition_note


def test_zero_external_tokens_becomes_proof_integrity() -> None:
    manifest = _manifest(_receipt(tokens=0))

    assert manifest.disposition is PM.Disposition.PROOF_INTEGRITY
    assert "zero-external-token" in manifest.disposition_note


def test_missing_signature_fields_become_proof_integrity() -> None:
    receipt = _receipt()
    receipt.pop("output_attestation")

    manifest = _manifest(receipt)

    assert manifest.disposition is PM.Disposition.PROOF_INTEGRITY
    assert "missing required field output_attestation" in manifest.disposition_note


def test_malformed_proof_extension_becomes_proof_integrity() -> None:
    receipt = _receipt()
    receipt["output_attestation"]["sha256"] = "not-a-valid-digest"

    manifest = _manifest(receipt)

    assert manifest.disposition is PM.Disposition.PROOF_INTEGRITY
    assert "output_attestation sha256" in manifest.disposition_note


def test_receipt_identity_mismatch_becomes_proof_integrity() -> None:
    receipt = _receipt()
    receipt["engine_id"] = "agy"
    receipt["variant"] = "gemini-3.1-pro-high"

    manifest = _manifest(receipt)

    assert manifest.disposition is PM.Disposition.PROOF_INTEGRITY
    assert "receipt-engine-mismatch" in manifest.disposition_note
    assert "receipt-variant-mismatch" in manifest.disposition_note


def test_substituted_engine_still_outranks_proof_integrity() -> None:
    evidence = D.dispatch(
        _resolution(),
        runner=lambda _invocation: {
            "status": "ok",
            "output": "external finding",
            "receipt": _receipt(tokens=0),
        },
        expected_identity="agy/gemini-3.5-flash-high",
    )

    manifest = D.build_dispatch_manifest(
        evidence,
        execution_id="exec-sub",
        saga_ref="saga-1",
        created_at="2026-07-09T00:00:00Z",
    )

    assert manifest.disposition is PM.Disposition.SUBSTITUTED_ENGINE


def test_satisfy_gate_refuses_proof_integrity_manifest() -> None:
    evidence = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="external finding",
        provenance={"status": "ok", "observer_corroborated": True},
        execution_id="exec-gate",
        verified_by_claude=True,
        runner_receipt=_receipt(tokens=0),
    )
    manifest = D.build_dispatch_manifest(
        evidence,
        execution_id="exec-gate",
        saga_ref="saga-1",
        created_at="2026-07-09T00:00:00Z",
    )

    with pytest.raises(D.DispatchError, match="proof-integrity"):
        verified = dataclasses.replace(evidence, verified_by_claude=True)
        D.satisfy_gate(verified, manifest, reconciliation=_reconciliation(verified))


def test_satisfy_gate_refuses_proof_integrity_evidence_without_manifest() -> None:
    evidence = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="external finding",
        provenance={"status": "ok", "observer_corroborated": True},
        execution_id="proof-without-manifest",
        verified_by_claude=True,
        runner_receipt=_receipt(tokens=0),
    )

    with pytest.raises(D.DispatchError, match="zero-external-token"):
        D.satisfy_gate(evidence, reconciliation=_reconciliation(evidence))


def test_satisfy_gate_refuses_cross_engine_receipt_without_manifest() -> None:
    receipt = _receipt()
    receipt["engine_id"] = "agy"
    evidence = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="external finding",
        provenance={"status": "ok", "observer_corroborated": True},
        execution_id="cross-engine-proof",
        verified_by_claude=True,
        runner_receipt=receipt,
    )

    with pytest.raises(D.DispatchError, match="receipt-engine-mismatch"):
        D.satisfy_gate(evidence, reconciliation=_reconciliation(evidence))
