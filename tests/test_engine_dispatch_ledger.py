"""Run-ledger proof fields, bridge-run de-duplication (#388), and dispatch-fact chain custody
plus registry-cell join fields (#459 R1/AE1)."""

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


def _dispatch_n_facts(ledger: Any, n: int) -> None:
    """Append ``n`` engine facts through the real dispatch write path (no receipt: no dedup)."""
    for index in range(n):
        D.dispatch(
            _resolution(),
            runner=lambda _invocation: {"status": "ok", "output": "external finding", "tokens": 7},
            ledger=ledger,
            subplot_id="sub-459",
            at=f"2026-07-1{index}T00:00:00Z",
        )


def test_chain_verification_fails_on_mutated_dispatch_record(tmp_path: Path) -> None:
    """AE1: mutating the middle dispatch record in place fails chain verification; reverting
    the mutation restores a passing chain."""
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")
    _dispatch_n_facts(ledger, 3)
    original = ledger.path.read_bytes()
    lines = original.decode("utf-8").splitlines()
    assert len(lines) == 3

    import json as _json

    record = _json.loads(lines[1])
    record["cost"] = 999.0  # in-place payload mutation, chain fields untouched
    lines[1] = _json.dumps(record, sort_keys=True, separators=(",", ":"))
    ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = RL.verify_chain(ledger)
    assert not report.ok
    assert report.break_index == 1
    assert "this_hash mismatch" in report.reason

    ledger.path.write_bytes(original)
    assert RL.verify_chain(ledger).ok


def test_chain_verification_fails_on_deleted_dispatch_record(tmp_path: Path) -> None:
    """AE1: deleting an earlier dispatch record breaks the prev_hash link."""
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")
    _dispatch_n_facts(ledger, 3)
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    ledger.path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")

    report = RL.verify_chain(ledger)
    assert not report.ok
    assert "prev_hash link broken" in report.reason


def test_engine_fact_carries_capability_claimed_rating_and_execution_id(tmp_path: Path) -> None:
    """#459 R1: capability-resolved dispatches stamp the registry-cell join fields."""
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")
    resolution = R.Resolution(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        effort="high",
        recipe="recipe",
        protocol=["Run read-only."],
        payload="Run read-only.",
        write_capable=False,
        fallback=None,
        halt=None,
        capability="adversarial-review",
        rating_claimed="STRONG",
    )
    D.dispatch(
        resolution,
        runner=lambda _invocation: {"status": "ok", "output": "external finding", "tokens": 7},
        ledger=ledger,
        subplot_id="sub-459",
        at="2026-07-13T00:00:00Z",
        execution_id="exec-459",
    )

    fact = RL.read_facts(ledger)[0]
    assert fact["capability"] == "adversarial-review"
    assert fact["rating_claimed"] == "STRONG"
    assert fact["execution_id"] == "exec-459"


def test_explicit_engine_dispatch_records_empty_join_fields(tmp_path: Path) -> None:
    """Explicit-engine resolutions (no capability route) carry empty-string join fields."""
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")
    D.dispatch(
        _resolution(),
        runner=lambda _invocation: {"status": "ok", "output": "external finding", "tokens": 7},
        ledger=ledger,
        subplot_id="sub-459",
        at="2026-07-13T00:00:00Z",
    )

    fact = RL.read_facts(ledger)[0]
    assert fact["capability"] == ""
    assert fact["rating_claimed"] == ""
    assert fact["execution_id"] == ""


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
