"""Benchmark-harness proposal tests (#459 R2/AE2) — proposal-only, never a registry write."""

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
SUITE_PATH = ROOT / "plugins" / "saga" / "references" / "benchmark-suite.yaml"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


EB = _load("engine_benchmark")
REG = _load("engine_registry")
RL = EB.run_ledger


def _row(engine_id: str, *, rating: str = "STRONG") -> dict[str, Any]:
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
        "cost_per_token": {"input_usd": 0.0, "output_usd": 0.0},
        "cost_class": "free",
        "latency_class": "standard",
        "model_identity": f"{engine_id}-default",
        "last_validated": "2026-06-01",
        "receipt_emitter": f"{engine_id}-bridge",
        "capability_profile": {"adversarial-review": {"rating": rating, "note": "fixture"}},
        "prompting_protocol": [f"Use {engine_id} for advisory output only."],
        "sources": [{"claim": "fixture", "url": "https://example.invalid", "date": "2026-06-01"}],
    }


def _registry_path(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    data = {"capabilities": list(REG.CAPABILITIES), "engines": rows, "roles": {}}
    path = tmp_path / "engine-registry.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _failing_runner(_entry: Any, _prompt: str) -> str:
    return "no useful analysis"


# --------------------------------------------------------------------------- AE2


def test_contradicted_rating_emits_proposal_never_a_write(tmp_path: Path) -> None:
    """AE2: authored STRONG, measured WEAK -> a registry diff PROPOSAL naming the row and
    capability, and the on-disk registry fixture is byte-identical before and after."""
    registry_path = _registry_path(tmp_path, [_row("fakeprov", rating="STRONG")])
    registry_bytes = registry_path.read_bytes()
    registry = REG.Registry.load(registry_path)
    entry = registry.by_key("fakeprov/default")
    suite = EB.load_suite("adversarial-review", SUITE_PATH)

    result = EB.run_suite(entry, suite, _failing_runner)
    cell = EB.proposal(result, entry, now=date(2026, 7, 13))

    assert result.measured_rating == "WEAK"
    assert result.contradicts is True
    assert cell is not None
    assert cell["engine_key"] == "fakeprov/default"
    assert cell["capability"] == "adversarial-review"
    assert cell["action"] == "rating-change"
    assert cell["approval_required"] is True
    assert cell["current"]["rating"] == "STRONG"
    assert cell["proposed"]["rating"] == "WEAK"
    assert registry_path.read_bytes() == registry_bytes


def test_agreeing_measurement_emits_no_proposal(tmp_path: Path) -> None:
    registry = REG.Registry.load(_registry_path(tmp_path, [_row("fakeprov", rating="WEAK")]))
    entry = registry.by_key("fakeprov/default")
    suite = EB.load_suite("adversarial-review", SUITE_PATH)

    result = EB.run_suite(entry, suite, _failing_runner)

    assert result.contradicts is False
    assert EB.proposal(result, entry, now=date(2026, 7, 13)) is None


# --------------------------------------------------------------------------- grading + thresholds


def test_measured_rating_threshold_boundaries() -> None:
    thresholds = {"STRONG": 0.8, "MODERATE": 0.5}
    assert EB.measured_rating(4, 5, thresholds) == "STRONG"  # 0.8 floor is inclusive
    assert EB.measured_rating(2, 4, thresholds) == "MODERATE"
    assert EB.measured_rating(1, 4, thresholds) == "WEAK"
    with pytest.raises(EB.BenchmarkError, match="at least one probe"):
        EB.measured_rating(0, 0, thresholds)


def test_each_grader_kind_passes_and_fails() -> None:
    contains = EB.Probe("p1", "prompt", "contains", "def slugify(")
    assert EB.grade(contains, "def slugify(s):\n    ...")
    assert not EB.grade(contains, "def slug(s): ...")

    regex = EB.Probe("p2", "prompt", "regex", r"(?i)off.by.one")
    assert EB.grade(regex, "classic Off-by-one at line 7")
    assert not EB.grade(regex, "looks fine to me")

    json_probe = EB.Probe("p3", "prompt", "json-parses", "")
    assert EB.grade(json_probe, '{"name": "demo", "version": "1.2.3"}')
    assert not EB.grade(json_probe, "not json at all")


def test_shipped_suite_fixture_loads_and_validates() -> None:
    suites = EB.load_suites(SUITE_PATH)
    assert {"adversarial-review", "code-generation"} <= set(suites)
    for suite in suites.values():
        assert suite.thresholds["STRONG"] > suite.thresholds["MODERATE"]
        assert suite.probes


def test_suite_loader_rejects_malformed_fixtures(tmp_path: Path) -> None:
    def write(data: dict[str, Any]) -> Path:
        path = tmp_path / "suite.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return path

    base_probe = {"id": "p1", "prompt": "x", "grader": {"kind": "contains", "value": "y"}}

    with pytest.raises(EB.BenchmarkError, match="schema"):
        EB.load_suites(write({"schema": "wrong", "suites": []}))
    with pytest.raises(EB.BenchmarkError, match="grader kind"):
        EB.load_suites(
            write(
                {
                    "schema": "benchmark_suite.v1",
                    "suites": [
                        {
                            "suite_id": "s1",
                            "capability": "adversarial-review",
                            "thresholds": {"STRONG": 0.8, "MODERATE": 0.5},
                            "probes": [
                                {"id": "p1", "prompt": "x", "grader": {"kind": "llm-judge"}}
                            ],
                        }
                    ],
                }
            )
        )
    with pytest.raises(EB.BenchmarkError, match="thresholds"):
        EB.load_suites(
            write(
                {
                    "schema": "benchmark_suite.v1",
                    "suites": [
                        {
                            "suite_id": "s1",
                            "capability": "adversarial-review",
                            "probes": [base_probe],
                        }
                    ],
                }
            )
        )
    with pytest.raises(EB.BenchmarkError, match="STRONG floor must exceed"):
        EB.load_suites(
            write(
                {
                    "schema": "benchmark_suite.v1",
                    "suites": [
                        {
                            "suite_id": "s1",
                            "capability": "adversarial-review",
                            "thresholds": {"STRONG": 0.5, "MODERATE": 0.5},
                            "probes": [base_probe],
                        }
                    ],
                }
            )
        )
    with pytest.raises(EB.BenchmarkError, match="duplicate suite_id"):
        EB.load_suites(
            write(
                {
                    "schema": "benchmark_suite.v1",
                    "suites": [
                        {
                            "suite_id": "s1",
                            "capability": "adversarial-review",
                            "thresholds": {"STRONG": 0.8, "MODERATE": 0.5},
                            "probes": [base_probe],
                        },
                        {
                            "suite_id": "s1",
                            "capability": "code-generation",
                            "thresholds": {"STRONG": 0.8, "MODERATE": 0.5},
                            "probes": [base_probe],
                        },
                    ],
                }
            )
        )


def test_unclaimed_capability_is_an_error_not_a_guess(tmp_path: Path) -> None:
    registry = REG.Registry.load(_registry_path(tmp_path, [_row("fakeprov")]))
    entry = registry.by_key("fakeprov/default")
    suite = EB.load_suite("code-generation", SUITE_PATH)

    with pytest.raises(EB.BenchmarkError, match="does not claim capability"):
        EB.run_suite(entry, suite, _failing_runner)


# --------------------------------------------------------------------------- ledger telemetry


def test_benchmark_fact_appended_only_with_the_full_telemetry_trio(tmp_path: Path) -> None:
    registry = REG.Registry.load(_registry_path(tmp_path, [_row("fakeprov")]))
    entry = registry.by_key("fakeprov/default")
    suite = EB.load_suite("adversarial-review", SUITE_PATH)
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")

    EB.run_suite(entry, suite, _failing_runner, ledger=ledger)  # missing subplot_id/at: no I/O
    assert RL.read_facts(ledger) == []

    EB.run_suite(
        entry,
        suite,
        _failing_runner,
        ledger=ledger,
        subplot_id="bench-leaf",
        at="2026-07-13T00:00:00Z",
    )
    facts = RL.read_facts(ledger)
    assert len(facts) == 1
    fact = facts[0]
    assert fact["kind"] == "benchmark"
    assert fact["engine"] == "fakeprov"
    assert fact["capability"] == "adversarial-review"
    assert fact["suite_id"] == "adversarial-review-v1"
    assert fact["measured_rating"] == "WEAK"
    assert fact["claimed_rating"] == "STRONG"
    assert fact["contradicts"] is True
    assert RL.verify_chain(ledger).ok
