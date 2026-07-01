"""Oracle tests for the Saga external-engine dispatch adapter (U4)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
REGISTRY_SCRIPT = SCRIPT_DIR / "engine_registry.py"
RESOLVER_SCRIPT = SCRIPT_DIR / "engine_resolver.py"
DISPATCH_SCRIPT = SCRIPT_DIR / "engine_dispatch.py"


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REG = _load("engine_registry", REGISTRY_SCRIPT)
R = _load("engine_resolver", RESOLVER_SCRIPT)
D = _load("engine_dispatch", DISPATCH_SCRIPT)


def _resolution(
    *,
    engine_id: str = "codex",
    variant: str = "gpt-5.5-xhigh",
    payload: str = "Run read-only.\n\nReturn a unified diff.",
    halt: str | None = None,
) -> Any:
    return R.Resolution(
        engine_id=engine_id,
        variant=variant,
        effort="high",
        recipe="recipe",
        protocol=["Run read-only."],
        payload=payload,
        write_capable=False,
        fallback=None,
        halt=halt,
    )


def test_codex_invocation_preserves_payload_byte_for_byte_and_read_only() -> None:
    payload = "Run read-only.\n\nReturn the diff exactly.\nTrailing spaces:  "
    resolution = _resolution(payload=payload)

    invocation = D.build_codex_invocation(resolution)

    assert invocation == {
        "via": "codex:codex-rescue",
        "task": payload,
        "sandbox": "read-only",
    }
    assert invocation["task"].encode("utf-8") == payload.encode("utf-8")


def test_agy_envelope_is_no_write_and_forwards_model_verbatim() -> None:
    payload = "Use the no-write envelope.\n\nReturn evidence only."
    model = "  Gemini 3.1 Pro (High)  "
    resolution = _resolution(
        engine_id="agy",
        variant="gemini-3.1-pro-high",
        payload=payload,
    )

    envelope = D.build_agy_envelope(resolution, model=model)

    assert envelope["schema"] == "agy.delegation.v1"
    assert envelope["mode"] == "no-write"
    assert envelope["task"] == payload
    assert envelope["model"] == model


@pytest.mark.parametrize(
    "status",
    ["timeout", "no-output", "error", "malformed", "clone-failed"],
)
def test_dispatch_failure_status_halts_with_downgrade_note_and_no_verdict(
    status: str,
) -> None:
    calls: list[dict[str, Any]] = []

    def runner(invocation: dict[str, Any]) -> dict[str, str]:
        calls.append(invocation)
        return {"status": status, "output": "wrapper failed"}

    evidence = D.dispatch(_resolution(), runner=runner)

    assert len(calls) == 1
    assert evidence.halt is not None
    assert evidence.evidence == ""
    assert evidence.provenance["status"] == status
    assert "note" in evidence.provenance
    assert "Downgraded external engine codex" in evidence.provenance["note"]
    assert status in evidence.provenance["note"]
    assert not hasattr(evidence, "gated_verdict")
    assert "gated_verdict" not in evidence.provenance


def test_dispatch_short_circuits_when_resolution_already_halted() -> None:
    called = False

    def runner(_invocation: dict[str, Any]) -> dict[str, str]:
        nonlocal called
        called = True
        raise AssertionError("runner must not be called for a halted resolution")

    evidence = D.dispatch(_resolution(halt="preflight halted"), runner=runner)

    assert called is False
    assert evidence.halt == "preflight halted"
    assert evidence.evidence == ""
    assert evidence.provenance["status"] == "halted"


def test_satisfy_gate_requires_claude_verification() -> None:
    unverified = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="external finding",
        provenance={"engine": "codex", "variant": "gpt-5.5-xhigh", "status": "ok"},
    )

    with pytest.raises(D.DispatchError):
        D.satisfy_gate(unverified)

    verified = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="Claude verified external finding",
        provenance={"engine": "codex", "variant": "gpt-5.5-xhigh", "status": "ok"},
        verified_by_claude=True,
    )

    assert D.satisfy_gate(verified) is None


def test_dispatch_returns_advisory_evidence_without_tree_mutation_surface() -> None:
    payload = "Change plugins/saga/scripts/example.py.\n\nReturn the patch as evidence."

    def runner(invocation: dict[str, Any]) -> dict[str, str]:
        assert invocation["sandbox"] == "read-only"
        return {
            "status": "ok",
            "output": "diff --git a/example.py b/example.py\n+proposed evidence only",
        }

    evidence = D.dispatch(_resolution(payload=payload), runner=runner)

    assert isinstance(evidence, D.AdvisoryEvidence)
    assert evidence.evidence.startswith("diff --git")
    assert evidence.halt is None
    assert evidence.provenance == {
        "engine": "codex",
        "variant": "gpt-5.5-xhigh",
        "status": "ok",
    }
    assert not hasattr(evidence, "gated_verdict")
