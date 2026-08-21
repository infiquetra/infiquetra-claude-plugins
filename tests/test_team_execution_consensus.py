"""Drift-guard tests for the Team Execution consensus contract (#293 U4).

The reviewer documents retain reviewer-facing instructions, while Saga's canonical lens roster and
shared scorer own acceptance policy. These tests bind each guard to the surface that now owns it.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "team-execution"
ARCHITECTURE_REVIEWER = PLUGIN_ROOT / "agents" / "architecture-reviewer.md"
CONSENSUS_PROTOCOL = (
    PLUGIN_ROOT / "skills" / "team-execution" / "references" / "consensus-protocol.md"
)
REVIEWER_REGISTRY = (
    PLUGIN_ROOT / "skills" / "team-execution" / "references" / "reviewer-registry.md"
)
EXTERNAL_ENGINE_WORKERS = (
    PLUGIN_ROOT / "skills" / "team-execution" / "references" / "external-engine-workers.md"
)
ROSTER = ROOT / "plugins" / "saga" / "references" / "lens-roster.json"
SCORER = ROOT / "plugins" / "saga" / "scripts" / "review_consensus.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_roster() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_read(ROSTER)))


def _load_scorer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_consensus_for_consensus_guards", SCORER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCORING: Any = _load_scorer()


def test_dimension_exclusion_replaces_fabricated_default() -> None:
    """R7: architecture-reviewer.md no longer fabricates a default score for a non-applicable
    dimension -- it excludes the dimension and names the applicable-dimensions denominator."""
    doc = _read(ARCHITECTURE_REVIEWER)

    assert "8.0 default" not in doc
    assert "N/A (8.0" not in doc
    # Broader than the two literal strings above: catches a differently-worded reintroduction
    # of a fabricated numeric default (e.g. "N/A (7.5 default)"), not just the exact old value.
    assert not re.search(r"N/A\s*\(\d", doc)
    assert "EXCLUDE" in doc
    assert "static-non-applicable" in doc
    assert "avg of 4 applicable" in doc


def test_consensus_gate_evaluates_applicable_dimensions() -> None:
    """R7/R8: the roster and shared scorer own the denominator and both thresholds."""
    roster = _load_roster()
    acceptance = roster["acceptance"]
    rules = {rule["id"]: rule for rule in acceptance["rules"]}

    assert acceptance["combiner"] == "all"
    assert acceptance["only_acceptance_thresholds"] is True
    assert rules["derived-overall-minimum"] == {
        "id": "derived-overall-minimum",
        "metric": "derived_overall",
        "operator": ">=",
        "value": 9.0,
    }
    assert rules["applicable-dimension-floor"] == {
        "id": "applicable-dimension-floor",
        "metric": "applicable_dimension",
        "operator": ">=",
        "value": 7.0,
    }
    assert roster["applicability"] == {
        "selected_lens_requires_applicable_dimension": True,
        "non_applicable_dimension_requires_cause": True,
    }

    policy = SCORING.load_scoring_policy(ROSTER)
    assert policy.overall_minimum == 9.0
    assert policy.dimension_floor == 7.0

    lens_id = "correctness"
    dimensions = policy.dimensions_for(lens_id)
    excluded_dimension = dimensions[0]
    applicable_scores = dict.fromkeys(dimensions[1:], 9.0)
    excluded_result = SCORING.score_lens_review(
        lens_id,
        applicable_scores,
        non_applicable_dimensions={excluded_dimension: "static-non-applicable"},
        policy=policy,
    )
    assert excluded_result.derived_overall == 9.0
    assert excluded_result.accepted is True

    below_overall = SCORING.score_lens_review(
        lens_id,
        dict.fromkeys(dimensions, 8.9),
        policy=policy,
    )
    assert below_overall.accepted is False
    assert below_overall.failing_dimensions == ()

    floor_lens = "architecture-maintainability"
    floor_scores = dict.fromkeys(policy.dimensions_for(floor_lens), 10.0)
    floor_dimension = next(iter(floor_scores))
    floor_scores[floor_dimension] = 6.9
    below_floor = SCORING.score_lens_review(floor_lens, floor_scores, policy=policy)
    assert below_floor.derived_overall >= policy.overall_minimum
    assert below_floor.accepted is False
    assert below_floor.failing_dimensions == (floor_dimension,)


def test_static_skip_no_floor() -> None:
    """AE3 boundary: both docs state a precondition exclusion is recorded with cause
    static-non-applicable and is never a failure -- it never enters re-review or escalation,
    and the exclusion vocabulary is shared with the Layer A execution-spec.md contract."""
    reviewer_doc = _read(ARCHITECTURE_REVIEWER)
    protocol_doc = _read(CONSENSUS_PROTOCOL)

    assert "static-non-applicable" in reviewer_doc
    assert "static-non-applicable" in protocol_doc
    # Shared vocabulary with the Layer A contract (execution-spec.md), named explicitly so a
    # reader can trace both surfaces to the same two-kinds concept.
    assert "execution-spec.md" in protocol_doc

    # Never a NEEDS REVISION / re-review trigger on its own.
    assert "never itself" in reviewer_doc or "never a NEEDS REVISION" in reviewer_doc
    assert "never a failure signal" in protocol_doc
    assert "does not trigger the re-review" in protocol_doc
    assert "is never re-run on that basis" in protocol_doc


def test_dimension_granular_exclusion_still_scores_remaining_dimensions() -> None:
    """Edge case: exclusion is dimension-granular -- the reviewer doc still requires scoring
    the four precondition-independent dimensions when only ADR-coverage is excluded."""
    doc = _read(ARCHITECTURE_REVIEWER)

    assert "Score the remaining\nfour dimensions normally" in doc or (
        "remaining" in doc and "four dimensions" in doc
    )
    # The other four dimensions have no repo-state precondition -- they are never excludable.
    for dimension in (
        "Pattern Consistency",
        "Separation of Concerns",
        "Dependency Direction",
        "Convention Adherence",
    ):
        assert dimension in doc


def test_external_advisory_seat_is_distinct_from_reviewer_tables() -> None:
    doc = _read(REVIEWER_REGISTRY)
    advisory_section = doc.split("## External Advisory Seat (Non-Scoring)", 1)[1]
    base_and_optional = doc.split("## External Advisory Seat (Non-Scoring)", 1)[0]

    assert 'role_kind="advisory-reviewer"' in advisory_section
    assert "excluded from reviewer selection counts" in advisory_section
    assert "Claude-only reviewer flow proceeds unchanged" in advisory_section
    assert "external-advisory" not in base_and_optional
    assert "advisory-reviewer" not in base_and_optional


def test_external_advisory_seat_is_always_excluded_from_consensus_gate() -> None:
    roster = _load_roster()
    seat = roster["participant_defaults"]["external_advisory_seat"]
    policy = SCORING.load_scoring_policy(ROSTER)
    doc = _read(CONSENSUS_PROTOCOL)

    assert seat == {
        "id": "external-reviewer",
        "scoring": False,
        "consensus_denominator": False,
        "applies_acceptance_rules": [],
    }
    assert seat["id"] not in policy.lens_dimensions
    with pytest.raises(SCORING.ReviewScoringError, match="unknown scoring lens"):
        SCORING.score_lens_review(
            seat["id"],
            {"whole-diff": policy.maximum_score},
            policy=policy,
        )

    assert "External Advisory Seat: report-only" in doc
    assert "Read the external seat's defaults from the roster." in doc
    assert (
        "never passed to `score_lens_review` or\n`evaluate_review_readiness` as a scoring lens"
    ) in doc


def test_convergence_report_buckets_are_documented() -> None:
    doc = _read(CONSENSUS_PROTOCOL)

    for bucket in ("`converged`", "`Claude-only`", "`external-only`", "`conflicting`"):
        assert bucket in doc
    assert "key/fingerprint based" in doc
    assert "Absence is not a panel failure" in doc


def test_external_engine_worker_contract_names_advisory_reviewer_role() -> None:
    doc = _read(EXTERNAL_ENGINE_WORKERS)

    assert 'role_kind="advisory-reviewer"' in doc
    assert "halt-not-fallback role" in doc
    assert "recorded as absent/halted" in doc
    assert "satisfy_gate()` refuses" in doc
