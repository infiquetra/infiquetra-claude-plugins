"""SPC drift-flag tests for the provider control chart reducer (#459 R5/AE5)."""

from __future__ import annotations

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


PCC = _load("provider_control_chart")
RL = PCC.run_ledger


def _ledger(tmp_path: Path) -> Any:
    return RL.RunLedger(path=tmp_path / "run-facts.jsonl")


def _engine_fact(
    engine: str,
    *,
    at: str,
    latency: float,
    cost: float = 0.01,
    variant: str = "default",
) -> Any:
    return RL.build_fact(
        "engine",
        subplot_id="leaf",
        at=at,
        engine=engine,
        variant=variant,
        capability="code-generation",
        rating_claimed="MODERATE",
        execution_id="exec-1",
        status="ok",
        proof_integrity_status="ok",
        cost=cost,
        latency_seconds=latency,
        tokens=100,
    )


def _baseline(noise_low: float = 0.9, noise_high: float = 1.1, n: int = 12) -> list[float]:
    return [noise_low if i % 2 == 0 else noise_high for i in range(n)]


def _seed_series(
    ledger: Any, engine: str, series: list[float], *, variant: str = "default"
) -> None:
    for index, latency in enumerate(series):
        RL.append_fact(
            ledger,
            _engine_fact(
                engine, at=f"2026-07-01T00:{index:02d}:00Z", latency=latency, variant=variant
            ),
        )


# --------------------------------------------------------------------------- pure chart math


def test_spc_drift_flag_on_sustained_spike_not_common_cause(tmp_path: Path) -> None:
    """AE5: a sustained ~3x latency spike flags provider X out-of-control; provider Y's
    same-variance common-cause noise stays in-control."""
    ledger = _ledger(tmp_path)
    _seed_series(ledger, "spiky", _baseline() + [3.0] * 6)
    _seed_series(ledger, "steady", _baseline(n=18))

    flags = PCC.provider_flags(ledger)

    assert flags["spiky"]["latency_seconds"].status == "out-of-control"
    assert flags["spiky"]["latency_seconds"].rule == "rule-1-beyond-limit"
    assert flags["steady"]["latency_seconds"].status == "in-control"
    assert PCC.drift_flagged(ledger) == frozenset({"spiky"})


def test_thin_series_is_no_data_never_a_flag() -> None:
    verdict = PCC.control_chart([1.0] * 12)  # baseline_n points, nothing post-baseline
    assert verdict.status == "no-data"
    assert PCC.control_chart([]).status == "no-data"


def test_rule_4_run_of_eight_fires_below_the_limit() -> None:
    series = _baseline() + [1.3] * 8  # above centerline 1.0, below UCL 1.0 + 2.66*0.2
    verdict = PCC.control_chart(series)
    assert verdict.status == "out-of-control"
    assert verdict.rule == "rule-4-run-of-8"
    assert len(verdict.breach_indices) == 8


def test_seven_point_run_stays_in_control() -> None:
    assert PCC.control_chart(_baseline() + [1.3] * 7).status == "in-control"


def test_zero_and_absent_metric_values_are_excluded(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    # 12 measured baseline points plus a long tail of unmeasured zeros: still no-data post-baseline.
    _seed_series(ledger, "quiet", _baseline() + [0.0] * 10)

    verdict = PCC.provider_flags(ledger)["quiet"]["latency_seconds"]

    assert verdict.status == "no-data"


def test_drift_aggregates_across_variants_per_engine_id(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    series = _baseline() + [3.0] * 6
    for index, latency in enumerate(series):
        variant = "fast" if index % 2 == 0 else "slow"
        RL.append_fact(
            ledger,
            _engine_fact(
                "multi", at=f"2026-07-01T00:{index:02d}:00Z", latency=latency, variant=variant
            ),
        )

    assert PCC.drift_flagged(ledger) == frozenset({"multi"})


def test_chain_break_raises_instead_of_silently_skipping(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _seed_series(ledger, "spiky", _baseline() + [3.0] * 6)
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    ledger.path.write_text("\n".join(lines[2:]) + "\n", encoding="utf-8")

    with pytest.raises(PCC.ControlChartError, match="chain verification failed"):
        PCC.provider_flags(ledger)


def test_cli_report_smoke(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ledger = _ledger(tmp_path)
    _seed_series(ledger, "spiky", _baseline() + [3.0] * 6)

    def fake_resolve(cls: Any, root: Any, **_kwargs: Any) -> Any:  # noqa: ARG001
        return ledger

    original = RL.RunLedger.resolve
    RL.RunLedger.resolve = classmethod(fake_resolve)  # type: ignore[method-assign, assignment]
    try:
        code = PCC.main(["report", "--root", str(tmp_path), "--json"])
    finally:
        RL.RunLedger.resolve = original  # type: ignore[method-assign]
    assert code == 0
    assert "out-of-control" in capsys.readouterr().out
