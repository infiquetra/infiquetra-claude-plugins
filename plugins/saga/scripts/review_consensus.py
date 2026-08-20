#!/usr/bin/env python3
"""Score Code Review lenses from the canonical roster and keep other gates separate."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

ROSTER_PATH = Path(__file__).resolve().parent.parent / "references" / "lens-roster.json"
ROSTER_SCHEMA = "lens_roster.v1"
OVERALL_RULE_ID = "derived-overall-minimum"
DIMENSION_FLOOR_RULE_ID = "applicable-dimension-floor"

__all__ = [
    "DEFAULT_SCORING_POLICY",
    "ContradictoryReviewEvidenceError",
    "FindingEvidence",
    "IndependentGateResult",
    "LensScore",
    "ReviewReadiness",
    "ReviewScoringError",
    "ReviewScoringPolicy",
    "evaluate_review_readiness",
    "load_scoring_policy",
    "score_lens_review",
]


class ReviewScoringError(ValueError):
    """The roster or a lens review cannot produce a trustworthy score."""


class ContradictoryReviewEvidenceError(ReviewScoringError):
    """Reported review evidence disagrees with the score it is meant to support."""


@dataclass(frozen=True)
class ReviewScoringPolicy:
    """Roster-owned score bounds, acceptance rules, and declared lens dimensions."""

    minimum_score: float
    maximum_score: float
    overall_minimum: float
    dimension_floor: float
    lens_dimensions: Mapping[str, tuple[str, ...]]

    def dimensions_for(self, lens_id: str) -> tuple[str, ...]:
        """Return the canonical dimension identifiers for one scoring lens."""
        try:
            return self.lens_dimensions[lens_id]
        except KeyError as exc:
            raise ReviewScoringError(f"unknown scoring lens {lens_id!r}") from exc


@dataclass(frozen=True)
class FindingEvidence:
    """Finding metadata linked to the dimension whose score reflects its evidence."""

    finding_id: str
    dimension_id: str
    critical: bool = False
    resolved: bool = False
    priority: str | None = None
    confidence: int | None = None


@dataclass(frozen=True)
class LensScore:
    """Validated, roster-bound score for one selected review lens."""

    lens_id: str
    dimension_scores: dict[str, float]
    non_applicable_dimensions: dict[str, str]
    derived_overall: float
    accepted: bool
    failing_dimensions: tuple[str, ...]
    findings: tuple[FindingEvidence, ...]


@dataclass(frozen=True)
class IndependentGateResult:
    """One non-scoring gate that retains authority over review readiness."""

    gate_id: str
    passed: bool


@dataclass(frozen=True)
class ReviewReadiness:
    """Numeric review acceptance plus independent, non-scoring gate state."""

    lens_scores: tuple[LensScore, ...]
    independent_gates: tuple[IndependentGateResult, ...]
    review_accepted: bool
    independent_gates_passed: bool
    failing_lenses: tuple[str, ...]
    failed_independent_gates: tuple[str, ...]
    can_proceed: bool


def load_scoring_policy(roster_path: Path = ROSTER_PATH) -> ReviewScoringPolicy:
    """Load and fail closed on the scoring contract owned by the canonical U4 roster."""
    try:
        payload = json.loads(roster_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewScoringError(f"cannot load lens roster {roster_path}: {exc}") from exc

    roster = _require_mapping(payload, label="lens roster")
    if roster.get("schema") != ROSTER_SCHEMA:
        raise ReviewScoringError(f"unsupported lens roster schema {roster.get('schema')!r}")

    score_scale = _require_mapping(roster.get("score_scale"), label="score_scale")
    minimum_score = _finite_number(score_scale.get("minimum"), label="score_scale.minimum")
    maximum_score = _finite_number(score_scale.get("maximum"), label="score_scale.maximum")
    if minimum_score >= maximum_score:
        raise ReviewScoringError("score_scale minimum must be lower than maximum")

    acceptance = _require_mapping(roster.get("acceptance"), label="acceptance")
    if acceptance.get("combiner") != "all":
        raise ReviewScoringError("acceptance rules must use the all combiner")
    if acceptance.get("only_acceptance_thresholds") is not True:
        raise ReviewScoringError("roster must identify its rules as the only acceptance thresholds")
    if acceptance.get("finding_priority_is_gate") is not False:
        raise ReviewScoringError("finding priority must remain metadata, not an acceptance gate")
    if acceptance.get("finding_confidence_is_gate") is not False:
        raise ReviewScoringError("finding confidence must remain metadata, not an acceptance gate")

    rules = _require_list(acceptance.get("rules"), label="acceptance.rules")
    rules_by_id: dict[str, Mapping[str, Any]] = {}
    for index, raw_rule in enumerate(rules):
        rule = _require_mapping(raw_rule, label=f"acceptance.rules[{index}]")
        rule_id = _nonempty_text(rule.get("id"), label=f"acceptance.rules[{index}].id")
        if rule_id in rules_by_id:
            raise ReviewScoringError(f"duplicate acceptance rule {rule_id!r}")
        rules_by_id[rule_id] = rule

    expected_rules = {
        OVERALL_RULE_ID: "derived_overall",
        DIMENSION_FLOOR_RULE_ID: "applicable_dimension",
    }
    if set(rules_by_id) != set(expected_rules):
        raise ReviewScoringError(
            "acceptance.rules must contain only the derived-overall minimum and dimension floor"
        )

    threshold_values: dict[str, float] = {}
    for rule_id, expected_metric in expected_rules.items():
        rule = rules_by_id[rule_id]
        if rule.get("metric") != expected_metric or rule.get("operator") != ">=":
            raise ReviewScoringError(f"acceptance rule {rule_id!r} has an unsupported predicate")
        threshold_values[rule_id] = _score_value(
            rule.get("value"),
            minimum_score=minimum_score,
            maximum_score=maximum_score,
            label=f"acceptance rule {rule_id!r}",
        )

    applicability = _require_mapping(roster.get("applicability"), label="applicability")
    if applicability.get("selected_lens_requires_applicable_dimension") is not True:
        raise ReviewScoringError("selected lenses must require an applicable dimension")
    if applicability.get("non_applicable_dimension_requires_cause") is not True:
        raise ReviewScoringError("non-applicable dimensions must require a cause")

    lenses = _require_list(roster.get("lenses"), label="lenses")
    lens_dimensions: dict[str, tuple[str, ...]] = {}
    for lens_index, raw_lens in enumerate(lenses):
        lens = _require_mapping(raw_lens, label=f"lenses[{lens_index}]")
        lens_id = _nonempty_text(lens.get("id"), label=f"lenses[{lens_index}].id")
        if lens_id in lens_dimensions:
            raise ReviewScoringError(f"duplicate lens identifier {lens_id!r}")
        raw_dimensions = _require_list(lens.get("dimensions"), label=f"lens {lens_id!r} dimensions")
        dimension_ids = tuple(
            _nonempty_text(
                _require_mapping(raw_dimension, label=f"lens {lens_id!r} dimension").get("id"),
                label=f"lens {lens_id!r} dimension id",
            )
            for raw_dimension in raw_dimensions
        )
        if not dimension_ids:
            raise ReviewScoringError(f"lens {lens_id!r} must declare at least one dimension")
        if len(set(dimension_ids)) != len(dimension_ids):
            raise ReviewScoringError(f"lens {lens_id!r} has duplicate dimension identifiers")
        lens_dimensions[lens_id] = dimension_ids

    if not lens_dimensions:
        raise ReviewScoringError("lens roster must declare at least one scoring lens")

    return ReviewScoringPolicy(
        minimum_score=minimum_score,
        maximum_score=maximum_score,
        overall_minimum=threshold_values[OVERALL_RULE_ID],
        dimension_floor=threshold_values[DIMENSION_FLOOR_RULE_ID],
        lens_dimensions=MappingProxyType(lens_dimensions),
    )


def score_lens_review(
    lens_id: str,
    applicable_dimensions: Mapping[str, float],
    *,
    non_applicable_dimensions: Mapping[str, str] | None = None,
    reported_overall: float | None = None,
    findings: Iterable[FindingEvidence] = (),
    policy: ReviewScoringPolicy | None = None,
) -> LensScore:
    """Validate and score one selected lens using only the roster's acceptance rules."""
    if policy is None:
        policy = DEFAULT_SCORING_POLICY
    lens_id = _nonempty_text(lens_id, label="lens_id")
    declared_dimensions = policy.dimensions_for(lens_id)
    dimension_scores = _normalize_dimension_scores(
        applicable_dimensions,
        policy=policy,
        lens_id=lens_id,
    )
    if not dimension_scores:
        raise ReviewScoringError(
            f"selected lens {lens_id!r} must provide at least one applicable dimension"
        )
    excluded_dimensions = _normalize_non_applicable_dimensions(
        non_applicable_dimensions or {}, lens_id=lens_id
    )

    duplicated = set(dimension_scores) & set(excluded_dimensions)
    if duplicated:
        raise ReviewScoringError(
            f"lens {lens_id!r} dimensions cannot be both applicable and non-applicable: "
            f"{sorted(duplicated)}"
        )

    provided_dimensions = set(dimension_scores) | set(excluded_dimensions)
    declared_set = set(declared_dimensions)
    unknown_dimensions = provided_dimensions - declared_set
    if unknown_dimensions:
        raise ReviewScoringError(
            f"lens {lens_id!r} has unknown dimensions: {sorted(unknown_dimensions)}"
        )
    missing_dimensions = declared_set - provided_dimensions
    if missing_dimensions:
        raise ReviewScoringError(
            f"lens {lens_id!r} has missing dimensions: {sorted(missing_dimensions)}"
        )

    ordered_scores = {
        dimension_id: dimension_scores[dimension_id]
        for dimension_id in declared_dimensions
        if dimension_id in dimension_scores
    }
    ordered_exclusions = {
        dimension_id: excluded_dimensions[dimension_id]
        for dimension_id in declared_dimensions
        if dimension_id in excluded_dimensions
    }
    derived_overall = math.fsum(ordered_scores.values()) / len(ordered_scores)

    if reported_overall is not None:
        normalized_overall = _score_value(
            reported_overall,
            minimum_score=policy.minimum_score,
            maximum_score=policy.maximum_score,
            label=f"lens {lens_id!r} reported overall",
        )
        if not math.isclose(normalized_overall, derived_overall):
            raise ContradictoryReviewEvidenceError(
                f"lens {lens_id!r} reported overall {normalized_overall} contradicts "
                f"derived overall {derived_overall}"
            )

    normalized_findings = _normalize_findings(
        findings,
        lens_id=lens_id,
        declared_dimensions=declared_set,
        dimension_scores=ordered_scores,
        dimension_floor=policy.dimension_floor,
    )
    failing_dimensions = tuple(
        dimension_id
        for dimension_id in declared_dimensions
        if dimension_id in ordered_scores and ordered_scores[dimension_id] < policy.dimension_floor
    )
    accepted = derived_overall >= policy.overall_minimum and not failing_dimensions

    return LensScore(
        lens_id=lens_id,
        dimension_scores=ordered_scores,
        non_applicable_dimensions=ordered_exclusions,
        derived_overall=derived_overall,
        accepted=accepted,
        failing_dimensions=failing_dimensions,
        findings=normalized_findings,
    )


def evaluate_review_readiness(
    lens_scores: Iterable[LensScore],
    independent_gates: Iterable[IndependentGateResult] = (),
) -> ReviewReadiness:
    """Combine lens acceptance with non-scoring gates without changing either result."""
    scores = tuple(lens_scores)
    if not scores:
        raise ReviewScoringError("review readiness requires at least one lens score")
    if any(not isinstance(score, LensScore) for score in scores):
        raise ReviewScoringError("review readiness accepts only LensScore values")
    lens_ids = [score.lens_id for score in scores]
    if len(set(lens_ids)) != len(lens_ids):
        raise ReviewScoringError("review readiness received duplicate lens scores")

    gates = tuple(independent_gates)
    gate_ids: list[str] = []
    for gate in gates:
        if not isinstance(gate, IndependentGateResult):
            raise ReviewScoringError(
                "review readiness accepts only IndependentGateResult gate values"
            )
        gate_ids.append(_nonempty_text(gate.gate_id, label="independent gate id"))
        if not isinstance(gate.passed, bool):
            raise ReviewScoringError(f"independent gate {gate.gate_id!r} passed must be boolean")
    if len(set(gate_ids)) != len(gate_ids):
        raise ReviewScoringError("review readiness received duplicate independent gates")

    failing_lenses = tuple(score.lens_id for score in scores if not score.accepted)
    failed_independent_gates = tuple(gate.gate_id for gate in gates if not gate.passed)
    review_accepted = not failing_lenses
    independent_gates_passed = not failed_independent_gates
    return ReviewReadiness(
        lens_scores=scores,
        independent_gates=gates,
        review_accepted=review_accepted,
        independent_gates_passed=independent_gates_passed,
        failing_lenses=failing_lenses,
        failed_independent_gates=failed_independent_gates,
        can_proceed=review_accepted and independent_gates_passed,
    )


def _normalize_dimension_scores(
    values: Mapping[str, float],
    *,
    policy: ReviewScoringPolicy,
    lens_id: str,
) -> dict[str, float]:
    if not isinstance(values, Mapping):
        raise ReviewScoringError(f"lens {lens_id!r} applicable dimensions must be a mapping")
    normalized: dict[str, float] = {}
    for raw_dimension_id, value in values.items():
        dimension_id = _nonempty_text(
            raw_dimension_id, label=f"lens {lens_id!r} applicable dimension id"
        )
        normalized[dimension_id] = _score_value(
            value,
            minimum_score=policy.minimum_score,
            maximum_score=policy.maximum_score,
            label=f"lens {lens_id!r} dimension {dimension_id!r}",
        )
    return normalized


def _normalize_non_applicable_dimensions(
    values: Mapping[str, str], *, lens_id: str
) -> dict[str, str]:
    if not isinstance(values, Mapping):
        raise ReviewScoringError(f"lens {lens_id!r} non-applicable dimensions must be a mapping")
    normalized: dict[str, str] = {}
    for raw_dimension_id, raw_cause in values.items():
        dimension_id = _nonempty_text(
            raw_dimension_id, label=f"lens {lens_id!r} non-applicable dimension id"
        )
        try:
            cause = _nonempty_text(
                raw_cause,
                label=f"non-applicable dimension {dimension_id!r} cause",
            )
        except ReviewScoringError as exc:
            raise ReviewScoringError(
                f"lens {lens_id!r} non-applicable dimension {dimension_id!r} requires a cause"
            ) from exc
        normalized[dimension_id] = cause
    return normalized


def _normalize_findings(
    findings: Iterable[FindingEvidence],
    *,
    lens_id: str,
    declared_dimensions: set[str],
    dimension_scores: Mapping[str, float],
    dimension_floor: float,
) -> tuple[FindingEvidence, ...]:
    normalized = tuple(findings)
    finding_ids: set[str] = set()
    for finding in normalized:
        if not isinstance(finding, FindingEvidence):
            raise ReviewScoringError(f"lens {lens_id!r} findings must be FindingEvidence values")
        finding_id = _nonempty_text(finding.finding_id, label="finding_id")
        dimension_id = _nonempty_text(
            finding.dimension_id, label=f"finding {finding_id!r} dimension"
        )
        if finding_id in finding_ids:
            raise ReviewScoringError(f"lens {lens_id!r} has duplicate finding {finding_id!r}")
        finding_ids.add(finding_id)
        if dimension_id not in declared_dimensions:
            raise ReviewScoringError(
                f"finding {finding_id!r} names unknown dimension {dimension_id!r}"
            )
        if not isinstance(finding.critical, bool) or not isinstance(finding.resolved, bool):
            raise ReviewScoringError(
                f"finding {finding_id!r} critical and resolved fields must be boolean"
            )
        if finding.critical and not finding.resolved:
            if dimension_id not in dimension_scores:
                raise ContradictoryReviewEvidenceError(
                    f"unresolved critical finding {finding_id!r} contradicts non-applicable "
                    f"dimension {dimension_id!r}"
                )
            if dimension_scores[dimension_id] >= dimension_floor:
                raise ContradictoryReviewEvidenceError(
                    f"unresolved critical finding {finding_id!r} contradicts passing score "
                    f"for dimension {dimension_id!r}"
                )
    return normalized


def _require_mapping(value: object, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReviewScoringError(f"{label} must be an object")
    return value


def _require_list(value: object, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReviewScoringError(f"{label} must be a list")
    return value


def _nonempty_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewScoringError(f"{label} must be non-empty text")
    return value.strip()


def _finite_number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReviewScoringError(f"{label} must be a finite number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ReviewScoringError(f"{label} must be a finite number")
    return normalized


def _score_value(
    value: object,
    *,
    minimum_score: float,
    maximum_score: float,
    label: str,
) -> float:
    try:
        normalized = _finite_number(value, label=label)
    except ReviewScoringError as exc:
        raise ReviewScoringError(
            f"{label} must be a finite number within {minimum_score}..{maximum_score}"
        ) from exc
    if not minimum_score <= normalized <= maximum_score:
        raise ReviewScoringError(
            f"{label} must be a finite number within {minimum_score}..{maximum_score}"
        )
    return normalized


DEFAULT_SCORING_POLICY = load_scoring_policy()
