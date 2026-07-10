#!/usr/bin/env python3
"""Bridge signature policy for ``bridge_receipt.v1`` proof-integrity checks (#388)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_commons_shim  # noqa: E402

_output_attestation = fleet_commons_shim.load("output_attestation")

SCHEMA = "bridge_signatures.v1"
DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent / "references" / ("bridge-signatures.json")
)


def load_registry(path: Path | str = DEFAULT_REGISTRY_PATH) -> dict[str, dict[str, Any]]:
    """Load the emitter-keyed bridge signature registry."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema") != SCHEMA:
        raise ValueError(f"bridge signature registry must use schema {SCHEMA!r}")
    emitters = raw.get("emitters")
    if not isinstance(emitters, dict):
        raise ValueError("bridge signature registry requires an emitters object")
    out: dict[str, dict[str, Any]] = {}
    for emitter, policy in emitters.items():
        if not isinstance(emitter, str) or not emitter.strip():
            raise ValueError("bridge signature emitter keys must be non-empty strings")
        if not isinstance(policy, dict):
            raise ValueError(f"bridge signature policy for {emitter!r} must be an object")
        out[emitter] = dict(policy)
    return out


def bridge_run_key(receipt: dict[str, Any]) -> str:
    """Stable de-duplication/liveness key for one bridge run."""
    run_id = receipt.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        return run_id
    body = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    return "receipt-sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def validate_receipt_signature(
    receipt: dict[str, Any],
    *,
    evidence_text: str = "",
    evidence_digest: str | None = None,
    evidence_bytes: int | None = None,
    registry: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Validate a receipt against its emitter policy. Empty list means proof-integrity OK."""
    policies = registry if registry is not None else load_registry()
    emitter = receipt.get("receipt_emitter")
    if not isinstance(emitter, str) or not emitter.strip():
        return ["proof-integrity: missing receipt_emitter"]
    policy = policies.get(emitter)
    if policy is None:
        return [f"proof-integrity: unknown receipt_emitter {emitter!r}"]

    errors: list[str] = []
    for field in policy.get("required_fields", []):
        if field not in receipt:
            errors.append(f"proof-integrity: missing required field {field}")

    external_tokens = receipt.get("external_tokens")
    if "external_tokens" in receipt:
        if isinstance(external_tokens, bool) or not isinstance(external_tokens, (int, float)):
            errors.append("proof-integrity: external_tokens must be numeric")
        elif external_tokens < 0:
            errors.append("proof-integrity: external_tokens must be non-negative")
        elif external_tokens == 0 and not bool(policy.get("allow_zero_external_tokens")):
            errors.append("proof-integrity: zero-external-token")

    attestation = receipt.get("output_attestation")
    if "output_attestation" in receipt:
        if not isinstance(attestation, dict):
            errors.append(
                f"proof-integrity: output_attestation must be a dict, "
                f"got {type(attestation).__name__}"
            )
        else:
            errors.extend(
                _output_attestation.validate_attestation(
                    attestation,
                    expected_content=None if evidence_digest is not None else evidence_text,
                    require_non_empty=bool(policy.get("require_non_empty_output")),
                )
            )
            if evidence_digest is not None and attestation.get("sha256") != evidence_digest:
                errors.append("proof-integrity: output-attestation-mismatch")
            if evidence_bytes is not None and attestation.get("bytes") != evidence_bytes:
                errors.append("proof-integrity: output-attestation-bytes-mismatch")

    return errors


def liveness_errors(
    launched_keys: set[str] | list[str] | tuple[str, ...],
    consumed_keys: set[str] | list[str] | tuple[str, ...],
) -> list[str]:
    """Return named producer/consumer liveness contradictions for bridge run keys."""
    launched = {str(k) for k in launched_keys if str(k)}
    consumed = {str(k) for k in consumed_keys if str(k)}
    errors = [f"proof-integrity: launched-unconsumed {key}" for key in sorted(launched - consumed)]
    errors.extend(
        f"proof-integrity: consumed-unlaunched {key}" for key in sorted(consumed - launched)
    )
    return errors
