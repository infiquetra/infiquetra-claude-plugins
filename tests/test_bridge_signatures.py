"""Tests for bridge-signature proof policy (#388)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).parent.parent
SAGA_SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
REGISTRY_PATH = ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml"


def _load(name: str, path: Path) -> ModuleType:
    if str(SAGA_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SAGA_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BS = _load("bridge_signatures_under_test", SAGA_SCRIPTS / "bridge_signatures.py")
ER = _load("engine_registry_for_bridge_signatures", SAGA_SCRIPTS / "engine_registry.py")
BR = BS.fleet_commons_shim.load("bridge_receipt")
OA = BS.fleet_commons_shim.load("output_attestation")


def _receipt(**overrides: Any) -> dict[str, Any]:
    values = {
        "engine_id": "codex",
        "variant": "gpt-5.5-xhigh",
        "transport": "cli",
        "wall_time_s": 1.0,
        "bytes_produced": len("external finding"),
        "runner": {"pid": 1, "argv": ["codex"], "exit_code": 0},
        "receipt_emitter": "codex-bridge",
        "run_id": "run-1",
        "external_tokens": 25,
        "output_attestation": OA.emit_attestation(
            artifact="evidence",
            content="external finding",
        ),
    }
    values.update(overrides)
    receipt: dict[str, Any] = BR.emit_receipt(**values)
    return receipt


def test_signature_registry_covers_every_engine_registry_emitter() -> None:
    registry = ER.Registry.load(REGISTRY_PATH)
    emitters = {entry.receipt_emitter for entry in registry.engines}

    assert set(BS.load_registry()) == emitters


def test_valid_signature_receipt_passes() -> None:
    assert BS.validate_receipt_signature(_receipt(), evidence_text="external finding") == []


def test_missing_output_attestation_fails_named_proof_integrity() -> None:
    receipt = _receipt(output_attestation=None)
    receipt.pop("output_attestation", None)

    errors = BS.validate_receipt_signature(receipt, evidence_text="external finding")

    assert "proof-integrity: missing required field output_attestation" in errors


def test_zero_external_tokens_fail_loud() -> None:
    errors = BS.validate_receipt_signature(
        _receipt(external_tokens=0),
        evidence_text="external finding",
    )

    assert "proof-integrity: zero-external-token" in errors


def test_hash_mismatch_fails_when_attestation_binds_evidence() -> None:
    errors = BS.validate_receipt_signature(
        _receipt(),
        evidence_text="different output",
    )

    assert any("output-attestation-mismatch" in error for error in errors)


def test_liveness_join_names_both_missing_halves() -> None:
    errors = BS.liveness_errors({"run-launched"}, {"run-consumed"})

    assert errors == [
        "proof-integrity: launched-unconsumed run-launched",
        "proof-integrity: consumed-unlaunched run-consumed",
    ]
