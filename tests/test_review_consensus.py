"""Focused behavior tests for Code Review scoring and independent gates (U5)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "plugins" / "saga" / "scripts" / "review_consensus.py"
ROSTER_PATH = ROOT / "plugins" / "saga" / "references" / "lens-roster.json"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_consensus", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["review_consensus"] = module
    spec.loader.exec_module(module)
    return module


CONSENSUS: Any = _load_module()


def _scores(
    lens_id: str = "correctness",
    score: float = 9.4,
) -> dict[str, float]:
    return dict.fromkeys(CONSENSUS.DEFAULT_SCORING_POLICY.dimensions_for(lens_id), score)


def _score_lens(
    *,
    lens_id: str = "correctness",
    score: float = 9.4,
    **kwargs: Any,
) -> Any:
    return CONSENSUS.score_lens_review(lens_id, _scores(lens_id, score), **kwargs)


def test_lens_averaging_nine_point_four_with_no_low_dimension_is_accepted() -> None:
    result = _score_lens(reported_overall=9.4)

    assert result.derived_overall == pytest.approx(9.4)
    assert result.accepted is True
    assert result.failing_dimensions == ()


def test_lens_averaging_nine_point_four_with_a_six_point_nine_dimension_fails_floor() -> None:
    dimensions = _scores("architecture-maintainability")
    values = (6.9, 9.8, 9.8, 9.8, 9.8, 9.85, 9.85)
    for dimension_id, value in zip(dimensions, values, strict=True):
        dimensions[dimension_id] = value

    result = CONSENSUS.score_lens_review(
        "architecture-maintainability",
        dimensions,
        reported_overall=9.4,
    )

    assert result.derived_overall == pytest.approx(9.4)
    assert result.accepted is False
    assert result.failing_dimensions == (next(iter(dimensions)),)


def test_exact_overall_and_dimension_boundaries_are_inclusive() -> None:
    dimensions = _scores(score=9.5)
    first_dimension = next(iter(dimensions))
    dimensions[first_dimension] = 7.0

    result = CONSENSUS.score_lens_review(
        "correctness",
        dimensions,
        reported_overall=9.0,
    )

    assert result.derived_overall == pytest.approx(9.0)
    assert result.accepted is True
    assert result.failing_dimensions == ()


def test_mean_below_nine_fails_even_when_every_dimension_clears_the_floor() -> None:
    result = _score_lens(score=8.9, reported_overall=8.9)

    assert result.derived_overall == pytest.approx(8.9)
    assert result.accepted is False
    assert result.failing_dimensions == ()


def test_dimension_below_seven_fails_even_when_mean_reaches_nine() -> None:
    dimensions = _scores(score=9.525)
    first_dimension = next(iter(dimensions))
    dimensions[first_dimension] = 6.9

    result = CONSENSUS.score_lens_review(
        "correctness",
        dimensions,
        reported_overall=9.0,
    )

    assert result.derived_overall == pytest.approx(9.0)
    assert result.accepted is False
    assert result.failing_dimensions == (first_dimension,)


def test_selected_lens_with_no_applicable_dimensions_is_rejected() -> None:
    with pytest.raises(
        CONSENSUS.ReviewScoringError,
        match="at least one applicable dimension",
    ):
        CONSENSUS.score_lens_review("correctness", {})


def test_reported_overall_that_disagrees_with_dimensions_is_contradictory() -> None:
    with pytest.raises(
        CONSENSUS.ContradictoryReviewEvidenceError,
        match="reported overall",
    ):
        _score_lens(score=7.0, reported_overall=9.9)


def test_non_applicable_dimension_requires_a_recorded_cause() -> None:
    dimensions = _scores()
    excluded_dimension = next(iter(dimensions))
    del dimensions[excluded_dimension]

    with pytest.raises(
        CONSENSUS.ReviewScoringError,
        match="non-applicable dimension.*cause",
    ):
        CONSENSUS.score_lens_review(
            "correctness",
            dimensions,
            non_applicable_dimensions={excluded_dimension: ""},
        )


def test_non_applicable_dimension_with_a_cause_is_excluded_from_the_mean() -> None:
    dimensions = _scores()
    excluded_dimension = next(iter(dimensions))
    del dimensions[excluded_dimension]

    result = CONSENSUS.score_lens_review(
        "correctness",
        dimensions,
        non_applicable_dimensions={
            excluded_dimension: "The reviewed change has no state transition."
        },
        reported_overall=9.4,
    )

    assert result.accepted is True
    assert result.derived_overall == pytest.approx(9.4)
    assert result.non_applicable_dimensions == {
        excluded_dimension: "The reviewed change has no state transition."
    }


def test_dimension_at_four_point_nine_uses_the_same_floor_failure_path() -> None:
    dimensions = _scores("architecture-maintainability", score=10.0)
    first_dimension = next(iter(dimensions))
    dimensions[first_dimension] = 4.9

    result = CONSENSUS.score_lens_review("architecture-maintainability", dimensions)

    assert result.derived_overall >= CONSENSUS.DEFAULT_SCORING_POLICY.overall_minimum
    assert result.accepted is False
    assert result.failing_dimensions == (first_dimension,)


def test_passing_dimension_with_unresolved_critical_evidence_is_contradictory() -> None:
    dimension_id = next(iter(_scores()))
    finding = CONSENSUS.FindingEvidence(
        finding_id="F-critical",
        dimension_id=dimension_id,
        critical=True,
        resolved=False,
        priority="P3",
        confidence=0,
    )

    with pytest.raises(
        CONSENSUS.ContradictoryReviewEvidenceError,
        match="unresolved critical finding.*passing score",
    ):
        _score_lens(score=9.0, findings=(finding,))


def test_critical_evidence_with_honest_low_score_is_valid_but_fails_floor() -> None:
    dimensions = _scores(score=9.525)
    dimension_id = next(iter(dimensions))
    dimensions[dimension_id] = 6.9
    finding = CONSENSUS.FindingEvidence(
        finding_id="F-critical",
        dimension_id=dimension_id,
        critical=True,
        resolved=False,
        priority="P3",
        confidence=0,
    )

    result = CONSENSUS.score_lens_review(
        "correctness",
        dimensions,
        reported_overall=9.0,
        findings=(finding,),
    )

    assert result.accepted is False
    assert result.failing_dimensions == (dimension_id,)


def test_priority_and_confidence_metadata_are_not_acceptance_gates() -> None:
    dimension_id = next(iter(_scores()))
    finding = CONSENSUS.FindingEvidence(
        finding_id="F-metadata-only",
        dimension_id=dimension_id,
        critical=False,
        resolved=False,
        priority="P0",
        confidence=100,
    )

    result = _score_lens(score=9.0, findings=(finding,))

    assert result.accepted is True


def test_built_versus_planned_failure_blocks_readiness_outside_scoring() -> None:
    score = _score_lens()
    readiness = CONSENSUS.evaluate_review_readiness(
        (score,),
        (
            CONSENSUS.IndependentGateResult("built-versus-planned", False),
            CONSENSUS.IndependentGateResult("scanner", True),
            CONSENSUS.IndependentGateResult("test", True),
            CONSENSUS.IndependentGateResult("deployment", True),
        ),
    )

    assert score.accepted is True
    assert score.derived_overall == pytest.approx(9.4)
    assert readiness.review_accepted is True
    assert readiness.independent_gates_passed is False
    assert readiness.failed_independent_gates == ("built-versus-planned",)
    assert readiness.can_proceed is False


def test_passed_scanner_test_and_deployment_gates_do_not_change_score() -> None:
    score = _score_lens()
    readiness = CONSENSUS.evaluate_review_readiness(
        (score,),
        (
            CONSENSUS.IndependentGateResult("scanner", True),
            CONSENSUS.IndependentGateResult("test", True),
            CONSENSUS.IndependentGateResult("deployment", True),
            CONSENSUS.IndependentGateResult("casualty", True),
            CONSENSUS.IndependentGateResult("operational-safety", True),
        ),
    )

    assert readiness.lens_scores == (score,)
    assert score.derived_overall == pytest.approx(9.4)
    assert readiness.review_accepted is True
    assert readiness.independent_gates_passed is True
    assert readiness.can_proceed is True


@pytest.mark.parametrize(
    "gate_id",
    ["scanner", "test", "deployment", "casualty", "operational-safety"],
)
def test_failed_safety_gate_blocks_readiness_without_changing_acceptance(gate_id: str) -> None:
    score = _score_lens()

    readiness = CONSENSUS.evaluate_review_readiness(
        (score,),
        (CONSENSUS.IndependentGateResult(gate_id, False),),
    )

    assert score.accepted is True
    assert score.derived_overall == pytest.approx(9.4)
    assert readiness.review_accepted is True
    assert readiness.failed_independent_gates == (gate_id,)
    assert readiness.can_proceed is False


def test_declared_dimensions_must_be_accounted_for_exactly_once() -> None:
    missing = _scores()
    missing.pop(next(iter(missing)))
    with pytest.raises(CONSENSUS.ReviewScoringError, match="missing dimensions"):
        CONSENSUS.score_lens_review("correctness", missing)

    unknown = _scores()
    unknown["invented-dimension"] = 9.4
    with pytest.raises(CONSENSUS.ReviewScoringError, match="unknown dimensions"):
        CONSENSUS.score_lens_review("correctness", unknown)


@pytest.mark.parametrize("invalid_score", [True, -0.1, 10.1, float("nan"), float("inf")])
def test_dimension_scores_must_be_finite_roster_scale_numbers(invalid_score: object) -> None:
    dimensions: dict[str, object] = {}
    dimensions.update(_scores())
    dimensions[next(iter(dimensions))] = invalid_score

    with pytest.raises(CONSENSUS.ReviewScoringError, match="finite number within"):
        CONSENSUS.score_lens_review("correctness", dimensions)


def test_policy_values_and_dimensions_are_loaded_from_the_u4_roster() -> None:
    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    rules = {rule["id"]: rule["value"] for rule in roster["acceptance"]["rules"]}
    policy = CONSENSUS.DEFAULT_SCORING_POLICY

    assert policy.overall_minimum == rules["derived-overall-minimum"]
    assert policy.dimension_floor == rules["applicable-dimension-floor"]
    assert policy.minimum_score == roster["score_scale"]["minimum"]
    assert policy.maximum_score == roster["score_scale"]["maximum"]
    assert policy.dimensions_for("correctness") == tuple(
        dimension["id"]
        for dimension in next(lens for lens in roster["lenses"] if lens["id"] == "correctness")[
            "dimensions"
        ]
    )

    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "9.0" not in source
    assert "7.0" not in source
    assert "5.0" not in source
