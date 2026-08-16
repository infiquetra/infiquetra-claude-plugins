"""Staleness-verdict tests for the ledger-fed engine stale report (#459 R3/AE3)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

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


SR = _load("engine_stale_report")
REG = _load("engine_registry")
RL = SR.run_ledger


def _row(
    engine_id: str, *, capability: str = "adversarial-review", rating: str = "STRONG"
) -> dict[str, Any]:
    return {
        "engine_id": engine_id,
        "variant": "default",
        "substrate": "external",
        "egress_policy": "networked",
        "trust_tier": "advisory",
        "default_for_engine": True,
        "invocation": {
            "via": f"{engine_id}:delegate",
            "recipe": f"{engine_id} delegate --mode no-write",
            "write_capable": False,
        },
        "context_window": 100_000,
        "cost_speed_rank": 3,
        "cost_per_token": {"input_usd": 0.000003, "output_usd": 0.000006},
        "cost_class": "free",
        "latency_class": "standard",
        "model_identity": f"{engine_id}-default",
        "last_validated": "2026-06-01",
        "receipt_emitter": f"{engine_id}-bridge",
        "capability_profile": {capability: {"rating": rating, "note": "fixture"}},
        "prompting_protocol": [f"Use {engine_id} for advisory output only."],
        "sources": [{"claim": "fixture", "url": "https://example.invalid", "date": "2026-06-01"}],
    }


def _fix_cost(row: dict[str, Any]) -> dict[str, Any]:
    row["cost_per_token"] = {"input_usd": 0.0, "output_usd": 0.0}
    return row


def _registry(tmp_path: Path, rows: list[dict[str, Any]]) -> Any:
    data = {
        "capabilities": list(REG.CAPABILITIES),
        "engines": [_fix_cost(row) for row in rows],
        "roles": {},
    }
    path = tmp_path / "engine-registry.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return REG.Registry.load(path)


def _ledger(tmp_path: Path) -> Any:
    return RL.RunLedger(path=tmp_path / "run-facts.jsonl")


def _engine_fact(
    engine: str,
    *,
    at: str,
    status: str = "ok",
    proof: str = "ok",
    capability: str = "adversarial-review",
) -> Any:
    return RL.build_fact(
        "engine",
        subplot_id="leaf",
        at=at,
        engine=engine,
        variant="default",
        capability=capability,
        rating_claimed="STRONG",
        execution_id="exec-1",
        status=status,
        proof_integrity_status=proof,
        cost=0.0,
        latency_seconds=1.0,
        tokens=100,
    )


def _benchmark_fact(engine: str, *, at: str, contradicts: bool) -> Any:
    return RL.build_fact(
        "benchmark",
        subplot_id="leaf",
        at=at,
        engine=engine,
        variant="default",
        capability="adversarial-review",
        suite_id="adversarial-review-v1",
        probes_total=4,
        probes_passed=0 if contradicts else 4,
        measured_rating="WEAK" if contradicts else "STRONG",
        claimed_rating="STRONG",
        contradicts=contradicts,
    )


def _cells_by_key(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(c["engine_key"], c["capability"]): c for c in report["cells"]}


def test_all_verdicts_over_synthetic_fixtures(tmp_path: Path) -> None:
    """AE3: corroborated, contradicted (benchmark AND failure-share), unexercised — all at once."""
    registry = _registry(
        tmp_path,
        [_row("good"), _row("benchbad"), _row("flaky"), _row("silent")],
    )
    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _engine_fact("good", at="2026-07-01T00:00:00Z"))
    RL.append_fact(ledger, _engine_fact("good", at="2026-07-10T00:00:00Z"))
    RL.append_fact(ledger, _benchmark_fact("benchbad", at="2026-07-02T00:00:00Z", contradicts=True))
    for day in ("03", "04", "05"):
        RL.append_fact(
            ledger, _engine_fact("flaky", at=f"2026-07-{day}T00:00:00Z", status="halted")
        )

    report = SR.stale_report(registry, ledger, now=date(2026, 7, 13))
    cells = _cells_by_key(report)

    good = cells[("good/default", "adversarial-review")]
    assert good["verdict"] == "corroborated"
    assert good["evidence"]["latest_corroborated_at"] == "2026-07-10T00:00:00Z"
    assert cells[("benchbad/default", "adversarial-review")]["verdict"] == "contradicted"
    flaky = cells[("flaky/default", "adversarial-review")]
    assert flaky["verdict"] == "contradicted"
    assert flaky["evidence"]["fail_count"] == 3
    assert cells[("silent/default", "adversarial-review")]["verdict"] == "unexercised"
    assert "note" not in report


def test_facts_older_than_last_validated_do_not_corroborate(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [_row("good")])
    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _engine_fact("good", at="2026-05-01T00:00:00Z"))  # predates 2026-06-01

    report = SR.stale_report(registry, ledger, now=date(2026, 7, 13))

    cell = _cells_by_key(report)[("good/default", "adversarial-review")]
    assert cell["verdict"] == "unexercised"
    assert cell["evidence"]["ok_count"] == 0


def test_pending_engine_facts_are_not_failures(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [_row("good")])
    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _engine_fact("good", at="2026-07-01T00:00:00Z", status="pending"))
    RL.append_fact(ledger, _engine_fact("good", at="2026-07-01T00:01:00Z", status="ok"))
    RL.append_fact(ledger, _engine_fact("good", at="2026-07-01T00:02:00Z", status="pending"))
    RL.append_fact(ledger, _engine_fact("good", at="2026-07-01T00:03:00Z", status="ok"))

    report = SR.stale_report(registry, ledger, now=date(2026, 7, 13))
    cell = _cells_by_key(report)[("good/default", "adversarial-review")]
    assert cell["verdict"] == "corroborated"
    assert cell["evidence"]["ok_count"] == 2
    assert cell["evidence"]["fail_count"] == 0


def test_failed_proof_dispatches_do_not_corroborate(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [_row("good")])
    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _engine_fact("good", at="2026-07-01T00:00:00Z", proof="failed"))

    report = SR.stale_report(registry, ledger, now=date(2026, 7, 13))

    cell = _cells_by_key(report)[("good/default", "adversarial-review")]
    assert cell["verdict"] == "unexercised"  # one failure: too thin to contradict
    assert cell["evidence"]["fail_count"] == 1


def test_empty_ledger_reports_every_cell_unexercised_with_note(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [_row("good"), _row("silent")])
    ledger = _ledger(tmp_path)

    report = SR.stale_report(registry, ledger, now=date(2026, 7, 13))

    assert report["note"] == "no dispatch evidence yet"
    assert {cell["verdict"] for cell in report["cells"]} == {"unexercised"}


def test_chain_break_raises_instead_of_silently_skipping(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [_row("good")])
    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _engine_fact("good", at="2026-07-01T00:00:00Z"))
    RL.append_fact(ledger, _engine_fact("good", at="2026-07-02T00:00:00Z"))
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    ledger.path.write_text(lines[1] + "\n", encoding="utf-8")  # middle-deletion of the genesis

    with pytest.raises(SR.StaleReportError, match="chain verification failed"):
        SR.stale_report(registry, ledger, now=date(2026, 7, 13))


def test_cli_report_smoke(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registry_rows = [_fix_cost(_row("good"))]
    data = {"capabilities": list(REG.CAPABILITIES), "engines": registry_rows, "roles": {}}
    registry_path = tmp_path / "engine-registry.yaml"
    registry_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _engine_fact("good", at="2026-07-01T00:00:00Z"))

    def fake_resolve(cls: Any, root: Any, **_kwargs: Any) -> Any:  # noqa: ARG001
        return ledger

    original = RL.RunLedger.resolve
    RL.RunLedger.resolve = classmethod(fake_resolve)  # type: ignore[method-assign, assignment]
    try:
        code = SR.main(["report", "--root", str(tmp_path), "--registry", str(registry_path)])
    finally:
        RL.RunLedger.resolve = original  # type: ignore[method-assign]
    assert code == 0
    assert "corroborated" in capsys.readouterr().out
