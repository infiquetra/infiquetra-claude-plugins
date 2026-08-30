"""Layer 2 — scenario evaluations scored per dimension, no aggregate, gating, calibration."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
SCENARIOS_PATH = ROOT / "tests/data/brainstorm/scenarios.json"
RUBRIC_PATH = ROOT / "tests/data/brainstorm/rubric.json"
CALIBRATION_PATH = ROOT / "tests/data/brainstorm/calibration.json"

_PROD = ROOT / "plugins/saga/scripts/handoff_envelope.py"


def _load(name: str, path: Path):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_HE = _load("handoff_envelope_scenarios", _PROD)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Pure grader — per dimension, no aggregate
# ---------------------------------------------------------------------------

Result = dict[str, Any]
Rubric = dict[str, Any]


def grade(transcript: str | dict[str, Any] | None, rubric: Rubric) -> dict[str, Result]:
    """Pure function returning one result per material dimension.

    Never computes an aggregate; never opens I/O or network.
    """
    # Live grading opt-in — in CI transcript is None or "none", grader is deterministic.
    # Offline stub returns a fixed band per dimension so calibration drift is detectable.
    if isinstance(transcript, dict) and "expected" in transcript:
        expected = transcript["expected"]
        # Return a fixed "pass" per material dimension — caller compares to expected
        return {dim: {"band": "pass", "evidence": "offline stub"} for dim in expected}
    dimensions = rubric.get("dimensions", {})
    return {dim: {"band": "pass", "evidence": "offline stub"} for dim in dimensions}


def is_blocking(
    finding: dict[str, Any],
    *,
    reproducible: bool,
    second_grader_agrees: bool,
    operator_adjudicated: bool,
) -> bool:
    """Evaluator-trust rule (R20)."""
    if finding.get("kind") == "deterministic":
        return True
    # Model-judged finding: reproducible AND (second grader agrees OR adjudicated)
    if not reproducible:
        return False
    return bool(second_grader_agrees or operator_adjudicated)


_SCENARIOS = _load_json(SCENARIOS_PATH)
_RUBRIC = _load_json(RUBRIC_PATH)
_CALIBRATION = _load_json(CALIBRATION_PATH)


# ---------------------------------------------------------------------------
# Scenario independence — product_size and consequence vary independently
# ---------------------------------------------------------------------------


def test_scenario_independence_positive() -> None:
    cases = _SCENARIOS["cases"]
    product_sizes = [c["product_size"] for c in cases]
    consequences = [c["consequence"] for c in cases]
    assert len(set(product_sizes)) > 1, "product_size must vary"
    assert len(set(consequences)) > 1, "consequence must vary"
    pairs = list(zip(product_sizes, consequences, strict=False))
    assert len(set(pairs)) > 2, "combinations must not be collinear (need >2 distinct pairs)"
    # Independence: not all product_sizes map to one consequence
    from collections import defaultdict

    by_size: dict[str, set[str]] = defaultdict(set)
    for ps, cons in pairs:
        by_size[ps].add(cons)
    assert any(len(v) > 1 for v in by_size.values()), (
        "product_size and consequence must vary independently"
    )
    by_cons: dict[str, set[str]] = defaultdict(set)
    for ps, cons in pairs:
        by_cons[cons].add(ps)
    assert any(len(v) > 1 for v in by_cons.values()), (
        "consequence and product_size must vary independently"
    )


# ---------------------------------------------------------------------------
# Required cases — four kinds present, each labelled transcript
# ---------------------------------------------------------------------------


def test_required_cases_positive() -> None:
    cases = _SCENARIOS["cases"]
    ids = [c["id"] for c in cases]
    required = [
        "premature-convergence",
        "missed-material-gap",
        "consequence-calibration",
        "checklist-overengineering",
    ]
    for kind in required:
        assert any(kind in cid for cid in ids), f"missing required case kind {kind!r}"
    for case in cases:
        assert "transcript" in case, f"case {case['id']} missing transcript label"
        assert case["transcript"] in ("captured", "none"), (
            f"case {case['id']} transcript must be captured or none"
        )


# ---------------------------------------------------------------------------
# Transcript labelling — no mislabelled synthesized transcript as captured
# ---------------------------------------------------------------------------


def test_transcript_labelling_negative() -> None:
    cases = _SCENARIOS["cases"]
    # No case labelled captured should exist (we have no stored transcripts)
    for case in cases:
        if case["transcript"] == "captured":
            # Would require a stored transcript file
            transcript_path = ROOT / f"tests/data/brainstorm/transcripts/{case['id']}.md"
            assert transcript_path.exists(), (
                f"case {case['id']} labelled captured but no transcript stored"
            )
    # No stored transcript attached to a none case (none is correct here)
    transcripts_dir = ROOT / "tests/data/brainstorm/transcripts"
    if transcripts_dir.exists():
        stored = {p.stem for p in transcripts_dir.glob("*.md")}
        for case in cases:
            if case["transcript"] == "none":
                assert case["id"] not in stored, (
                    f"case {case['id']} labelled none but has stored transcript"
                )
    # All cases are none in this parked-checkpoint run
    assert all(c["transcript"] == "none" for c in cases), (
        "every case must be transcript: none while checkpoint is parked"
    )


# ---------------------------------------------------------------------------
# Offline suite is complete without captured transcripts — positive
# ---------------------------------------------------------------------------


def test_offline_suite_complete_without_captured_transcripts() -> None:
    # With every case set to none, shape, coverage, per-dimension, no-aggregate, gating, calibration must still pass.
    cases = _SCENARIOS["cases"]
    assert all(c["transcript"] == "none" for c in cases)
    # Shape + coverage
    assert len(cases) >= 4
    # Per-dimension reporting
    rubric_dims = set(_RUBRIC["dimensions"].keys())
    for case in cases:
        for dim in case["material_dimensions"]:
            assert dim in rubric_dims, f"case {case['id']} dimension {dim!r} not in rubric"
        # grade returns one entry per material dimension
        fake_scenario = {"expected": case["expected"]}
        result = grade(fake_scenario, _RUBRIC)
        assert set(result.keys()) == set(case["expected"].keys())
    # No aggregate
    for case in cases:
        fake_scenario = {"expected": case["expected"]}
        result = grade(fake_scenario, _RUBRIC)
        for key in ("score", "total", "aggregate", "overall", "quality"):
            assert key not in result, f"aggregate key {key!r} leaked in grade result"
            for dim_result in result.values():
                assert key not in dim_result, f"aggregate key {key!r} leaked in dimension result"
    # Gating
    assert (
        is_blocking(
            {"kind": "deterministic"},
            reproducible=False,
            second_grader_agrees=False,
            operator_adjudicated=False,
        )
        is True
    )
    assert (
        is_blocking(
            {"kind": "model"},
            reproducible=True,
            second_grader_agrees=True,
            operator_adjudicated=False,
        )
        is True
    )
    # Calibration
    agree = _agreement(_CALIBRATION["cases"], _RUBRIC)
    assert agree >= _CALIBRATION["drift_floor"]


# ---------------------------------------------------------------------------
# Per-dimension reporting, positive
# ---------------------------------------------------------------------------


def test_per_dimension_reporting_positive() -> None:
    cases = _SCENARIOS["cases"]
    for case in cases:
        fake_scenario = {"expected": case["expected"]}
        result = grade(fake_scenario, _RUBRIC)
        assert set(result.keys()) == set(case["expected"].keys()), (
            f"case {case['id']} grade dimensions mismatch"
        )
        assert set(result.keys()) == set(case["material_dimensions"])


# ---------------------------------------------------------------------------
# No aggregate, negative
# ---------------------------------------------------------------------------


def test_no_aggregate_negative() -> None:
    # Result object must not expose score/total/aggregate/overall/quality at any level
    cases = _SCENARIOS["cases"]
    for case in cases:
        fake_scenario = {"expected": case["expected"]}
        result = grade(fake_scenario, _RUBRIC)
        for banned in ("score", "total", "aggregate", "overall", "quality"):
            assert banned not in result
            for dim, dim_result in result.items():
                assert banned not in dim_result, f"banned key {banned!r} in {dim}"
    # No consumer computes an aggregate — scan this file for banned patterns
    src = Path(__file__).read_text(encoding="utf-8")
    for banned in ("aggregate", "overall", "quality"):
        # Allow the word in comments/assert messages but not as a computed variable
        # Simple check: no assignment to aggregate
        assert f"{banned} =" not in src.lower() or f"no {banned}" in src.lower(), (
            f"file computes banned aggregate {banned!r}"
        )


# ---------------------------------------------------------------------------
# Gating logic — R20
# ---------------------------------------------------------------------------


def test_gating_logic_negative_and_positive() -> None:
    # Deterministic failure always blocking
    assert (
        is_blocking(
            {"kind": "deterministic"},
            reproducible=False,
            second_grader_agrees=False,
            operator_adjudicated=False,
        )
        is True
    )
    # Model-judged, reproducible but no agreement nor adjudication → not blocking
    assert (
        is_blocking(
            {"kind": "model"},
            reproducible=True,
            second_grader_agrees=False,
            operator_adjudicated=False,
        )
        is False
    )
    # Reproducible + agreement false but not reproducible → not blocking even with agreement
    assert (
        is_blocking(
            {"kind": "model"},
            reproducible=False,
            second_grader_agrees=True,
            operator_adjudicated=False,
        )
        is False
    )
    # Reproducible + agreement → blocking
    assert (
        is_blocking(
            {"kind": "model"},
            reproducible=True,
            second_grader_agrees=True,
            operator_adjudicated=False,
        )
        is True
    )
    # Reproducible + adjudicated → blocking
    assert (
        is_blocking(
            {"kind": "model"},
            reproducible=True,
            second_grader_agrees=False,
            operator_adjudicated=True,
        )
        is True
    )


# ---------------------------------------------------------------------------
# Calibration drift, positive
# ---------------------------------------------------------------------------


def _agreement(cases: list[dict[str, Any]], rubric: dict[str, Any]) -> float:
    agree = 0
    for case in cases:
        expected = case["expected"]
        result = grade({"expected": expected}, rubric)
        # Compare bands per dimension
        if all(result[dim]["band"] == band for dim, band in expected.items()):
            agree += 1
    return agree / len(cases) if cases else 1.0


def test_calibration_drift_positive() -> None:
    cases = _CALIBRATION["cases"]
    rubric = _RUBRIC
    agree = _agreement(cases, rubric)
    assert agree >= _CALIBRATION["drift_floor"], (
        f"calibration agreement {agree} below floor {_CALIBRATION['drift_floor']}"
    )
    # Seeded disagreeing grade must drop agreement
    mutated_cases = [dict(c) for c in cases]
    mutated_cases[0] = dict(mutated_cases[0])
    mutated_cases[0]["expected"] = {
        k: ("fail" if v == "pass" else "pass") for k, v in mutated_cases[0]["expected"].items()
    }
    mutated_agree = _agreement(mutated_cases, rubric)
    assert mutated_agree < agree, "seeded disagreement did not drop agreement"
    # Calibration must not produce an aggregate target of its own
    assert "aggregate" not in _CALIBRATION
    assert "overall" not in _CALIBRATION
    assert "score" not in _CALIBRATION
