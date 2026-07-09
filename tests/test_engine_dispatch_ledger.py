"""Run-ledger proof fields and bridge-run de-duplication (#388)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

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
RL = D.run_ledger
BR = D._bridge_receipt
OA = D.fleet_commons_shim.load("output_attestation")


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


def _receipt(*, tokens: int = 42) -> dict[str, Any]:
    receipt: dict[str, Any] = BR.emit_receipt(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        transport="cli",
        wall_time_s=0.5,
        bytes_produced=len("external finding"),
        runner={"pid": 4242, "argv": ["codex"], "exit_code": 0},
        receipt_emitter="codex-bridge",
        run_id="ledger-run-1",
        external_tokens=tokens,
        output_attestation=OA.emit_attestation(artifact="evidence", content="external finding"),
    )
    return receipt


def test_engine_fact_records_bridge_run_key_and_external_tokens(tmp_path: Path) -> None:
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")
    D.dispatch(
        _resolution(),
        runner=lambda _invocation: {
            "status": "ok",
            "output": "external finding",
            "tokens": 42,
            "receipt": _receipt(),
        },
        ledger=ledger,
        subplot_id="sub-388",
        at="2026-07-09T00:00:00Z",
    )

    fact = RL.read_facts(ledger)[0]

    assert fact["bridge_run_key"] == "ledger-run-1"
    assert fact["external_tokens"] == 42.0
    assert fact["proof_integrity_status"] == "ok"


def test_same_bridge_run_key_writes_engine_fact_once(tmp_path: Path) -> None:
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")
    runner = lambda _invocation: {  # noqa: E731 - local test seam
        "status": "ok",
        "output": "external finding",
        "tokens": 42,
        "receipt": _receipt(),
    }

    for _ in range(2):
        D.dispatch(
            _resolution(),
            runner=runner,
            ledger=ledger,
            subplot_id="sub-388",
            at="2026-07-09T00:00:00Z",
        )

    assert [fact["kind"] for fact in RL.read_facts(ledger)] == ["engine"]


def test_zero_token_halt_is_ledgered_once_as_failed_proof(tmp_path: Path) -> None:
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")
    D.dispatch(
        _resolution(),
        runner=lambda _invocation: {
            "status": "ok",
            "output": "external finding",
            "tokens": 0,
            "receipt": _receipt(tokens=0),
        },
        ledger=ledger,
        subplot_id="sub-388",
        at="2026-07-09T00:00:00Z",
    )

    fact = RL.read_facts(ledger)[0]

    assert fact["external_tokens"] == 0.0
    assert fact["proof_integrity_status"] == "failed"
    assert "zero-external-token" in fact["proof_integrity_errors"][0]
