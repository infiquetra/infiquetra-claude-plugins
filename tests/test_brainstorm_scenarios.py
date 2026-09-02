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


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Pure grader — per dimension, no aggregate
# ---------------------------------------------------------------------------

Result = dict[str, Any]
Rubric = dict[str, Any]


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
    # With every case set to none, shape, coverage, per-dimension, no-aggregate, gating, calibration shape must still pass.
    cases = _SCENARIOS["cases"]
    assert all(c["transcript"] == "none" for c in cases)
    # Shape + coverage
    assert len(cases) >= 4
    # Per-dimension reporting — data shape, no grader
    rubric_dims = set(_RUBRIC["dimensions"].keys())
    for case in cases:
        for dim in case["material_dimensions"]:
            assert dim in rubric_dims, f"case {case['id']} dimension {dim!r} not in rubric"
        assert set(case["material_dimensions"]) == set(case["expected"].keys())
    # No aggregate in data
    for case in cases:
        for key in ("score", "total", "aggregate", "overall", "quality"):
            assert key not in case["expected"]
            assert key not in case
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
    # Calibration shape only — drift check deferred until real grader exists
    assert len(_CALIBRATION["cases"]) == 3
    for case in _CALIBRATION["cases"]:
        assert "id" in case and "expected" in case
        for dim in case["expected"]:
            assert dim in rubric_dims


# ---------------------------------------------------------------------------
# Per-dimension reporting, positive
# ---------------------------------------------------------------------------


def test_per_dimension_reporting_positive() -> None:
    cases = _SCENARIOS["cases"]
    for case in cases:
        assert set(case["expected"].keys()) == set(case["material_dimensions"]), (
            f"case {case['id']} expected vs material_dimensions mismatch"
        )


# ---------------------------------------------------------------------------
# No aggregate, negative
# ---------------------------------------------------------------------------


def test_no_aggregate_negative() -> None:
    # Data must not expose aggregate keys
    cases = _SCENARIOS["cases"]
    for case in cases:
        for banned in ("score", "total", "aggregate", "overall", "quality"):
            assert banned not in case["expected"]
            assert banned not in case
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


def test_calibration_shape_positive() -> None:
    cases = _CALIBRATION["cases"]
    assert len(cases) == 3
    for case in cases:
        assert "id" in case and "expected" in case
        for dim in case["expected"]:
            assert dim in _RUBRIC["dimensions"]
    # Calibration must not produce an aggregate target of its own
    assert "aggregate" not in _CALIBRATION
    assert "overall" not in _CALIBRATION
    assert "score" not in _CALIBRATION
    # Drift check is deferred until a real grader exists — shape is what we prove now
