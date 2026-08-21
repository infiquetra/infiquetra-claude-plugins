"""Focused state-machine and transport tests for Code Review consensus (U6)."""

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


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_consensus_cycles", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["review_consensus_cycles"] = module
    spec.loader.exec_module(module)
    return module


CONSENSUS: Any = _load_module()


def _score(
    lens_id: str,
    value: float,
    *,
    findings: tuple[Any, ...] = (),
) -> Any:
    dimensions = dict.fromkeys(CONSENSUS.DEFAULT_SCORING_POLICY.dimensions_for(lens_id), value)
    return CONSENSUS.score_lens_review(lens_id, dimensions, findings=findings)


def _delta(
    lens_id: str,
    reviewed_revision: str,
    checked_revision: str,
    *,
    passed: bool,
) -> Any:
    return CONSENSUS.DeltaCheckResult(
        lens_id=lens_id,
        reviewed_revision=reviewed_revision,
        checked_revision=checked_revision,
        passed=passed,
        cause="No regression in the reviewed lens."
        if passed
        else "The repair regressed this lens.",
        evidence_refs=(f"delta:{lens_id}:{checked_revision}",),
    )


def _finding(
    lens_id: str,
    finding_id: str,
    *,
    autofix_class: str = "safe_auto",
    owner: str = "review-fixer",
    severity: str = "P1",
) -> Any:
    return CONSENSUS.ReviewFinding(
        finding_id=finding_id,
        lens_id=lens_id,
        dimension_id=(
            None
            if lens_id == "external-reviewer"
            else CONSENSUS.DEFAULT_SCORING_POLICY.dimensions_for(lens_id)[0]
        ),
        title=f"Repair {finding_id}",
        severity=severity,
        file=f"src/{lens_id}.py",
        line=10,
        why_it_matters="The reviewed behavior remains incorrect.",
        autofix_class=autofix_class,
        owner=owner,
        requires_verification=True,
        confidence=100,
        evidence=(f"src/{lens_id}.py:10",),
        suggested_fix="Apply the bounded repair and rerun this lens.",
    )


def _accepted_result() -> Any:
    state = CONSENSUS.ReviewCycleState(("correctness",))
    return state.record_cycle("revision-1", {"correctness": _score("correctness", 9.4)})


def _repairs_result() -> Any:
    state = CONSENSUS.ReviewCycleState(("correctness",))
    return state.record_cycle("revision-1", {"correctness": _score("correctness", 8.9)})


def _cycle_cap_result() -> Any:
    state = CONSENSUS.ReviewCycleState(("correctness",))
    state.record_cycle("revision-1", {"correctness": _score("correctness", 8.9)})
    state.record_cycle("revision-2", {"correctness": _score("correctness", 8.8)})
    return state.record_cycle("revision-3", {"correctness": _score("correctness", 8.7)})


def _incomplete_result() -> Any:
    state = CONSENSUS.ReviewCycleState(("correctness",))
    return state.handle_runner_delivery(
        {"session_outcome": "died", "reason": "bounded retries exhausted"}
    ).review_result


def test_only_failing_lenses_are_rerun_and_accepted_revisions_are_retained() -> None:
    state = CONSENSUS.ReviewCycleState(("correctness", "security", "testing"))

    first = state.record_cycle(
        "revision-1",
        {
            "correctness": _score("correctness", 8.9),
            "security": _score("security", 8.9),
            "testing": _score("testing", 9.4),
        },
    )
    assert first.outcome == "repairs_requested"
    assert state.next_lenses == ("correctness", "security")

    second = state.record_cycle(
        "revision-2",
        {
            "correctness": _score("correctness", 9.4),
            "security": _score("security", 8.9),
        },
    )
    assert second.outcome == "repairs_requested"
    assert state.next_lenses == ("security",)

    final = state.record_cycle(
        "revision-3",
        {"security": _score("security", 9.4)},
        delta_checks=(
            _delta("correctness", "revision-2", "revision-3", passed=True),
            _delta("testing", "revision-1", "revision-3", passed=True),
        ),
    )

    assert final.outcome == "accepted"
    assert [record.attempted_lenses for record in final.cycle_history] == [
        ("correctness", "security", "testing"),
        ("correctness", "security"),
        ("security",),
    ]
    assert {result.lens_id: result.reviewed_revision for result in final.lens_results} == {
        "correctness": "revision-2",
        "security": "revision-3",
        "testing": "revision-1",
    }


def test_critical_typed_finding_cannot_bypass_scoring_or_result_validation() -> None:
    finding = _finding("correctness", "F-critical-route", severity="P0")
    state = CONSENSUS.ReviewCycleState(("correctness",))

    with pytest.raises(
        CONSENSUS.ContradictoryReviewEvidenceError,
        match="unresolved critical finding.*passing score",
    ):
        state.record_cycle(
            "revision-1",
            {"correctness": _score("correctness", 9.4)},
            findings=(finding,),
        )
    assert state.cycle_count == 0

    accepted_payload = _accepted_result().to_dict()
    fix_requests = CONSENSUS.consolidate_fix_requests((finding,))
    accepted_payload["findings"] = [finding.to_dict()]
    accepted_payload["fix_requests"] = [item.to_dict() for item in fix_requests]
    accepted_payload["unresolved_fix_ids"] = [item.fix_id for item in fix_requests]
    accepted_payload["residual_summary"]["unresolved_fix_ids"] = [
        item.fix_id for item in fix_requests
    ]
    with pytest.raises(
        CONSENSUS.ContradictoryReviewEvidenceError,
        match="unresolved critical finding.*passing score",
    ):
        CONSENSUS.ReviewResult.from_dict(accepted_payload)

    noncritical = _finding("correctness", "F-priority-metadata", severity="P1")
    noncritical_evidence = CONSENSUS.FindingEvidence(
        finding_id=noncritical.finding_id,
        dimension_id=noncritical.dimension_id,
        critical=False,
        resolved=False,
        priority=noncritical.severity,
        confidence=noncritical.confidence,
    )
    metadata_state = CONSENSUS.ReviewCycleState(("correctness",))
    metadata_result = metadata_state.record_cycle(
        "revision-1",
        {
            "correctness": _score(
                "correctness",
                9.4,
                findings=(noncritical_evidence,),
            )
        },
        findings=(noncritical,),
    )

    assert metadata_result.outcome == "accepted"
    assert metadata_result.fix_requests


def test_three_failing_cycles_return_latest_revision_and_complete_residuals() -> None:
    state = CONSENSUS.ReviewCycleState(("correctness", "security"))

    for cycle in (1, 2):
        result = state.record_cycle(
            f"revision-{cycle}",
            {
                "correctness": _score("correctness", 8.9),
                "security": _score("security", 8.8),
            },
            findings=(
                _finding("correctness", "F-correctness"),
                _finding("security", "F-security"),
            ),
        )
        assert result.outcome == "repairs_requested"

    final = state.record_cycle(
        "revision-3",
        {
            "correctness": _score("correctness", 8.7),
            "security": _score("security", 8.6),
        },
        findings=(
            _finding("correctness", "F-correctness"),
            _finding("security", "F-security"),
        ),
    )

    residual = final.residual_summary.to_dict()
    assert final.outcome == "cycle_cap_best_available"
    assert final.best_available_revision == "revision-3"
    assert set(residual["final_lens_scores"]) == {"correctness", "security"}
    assert set(residual["unresolved_fix_ids"]) == set(final.unresolved_fix_ids)
    assert set(final.unresolved_fix_ids) == {request.fix_id for request in final.fix_requests}


def test_a_fourth_cycle_is_never_attempted() -> None:
    state = CONSENSUS.ReviewCycleState(("correctness",))
    state.record_cycle("revision-1", {"correctness": _score("correctness", 8.9)})
    state.record_cycle("revision-2", {"correctness": _score("correctness", 8.8)})
    state.record_cycle("revision-3", {"correctness": _score("correctness", 8.7)})

    with pytest.raises(CONSENSUS.ReviewConsensusError, match="no further cycle|fourth"):
        state.record_cycle("revision-4", {"correctness": _score("correctness", 9.4)})


def test_cycle_three_score_regression_is_reported_but_adds_no_gate() -> None:
    state = CONSENSUS.ReviewCycleState(("correctness",))
    state.record_cycle("revision-1", {"correctness": _score("correctness", 8.9)})
    state.record_cycle("revision-2", {"correctness": _score("correctness", 8.8)})
    final = state.record_cycle("revision-3", {"correctness": _score("correctness", 8.0)})

    assert final.outcome == "cycle_cap_best_available"
    assert any(
        regression.cycle == 3
        and regression.previous_overall == pytest.approx(8.8)
        and regression.current_overall == pytest.approx(8.0)
        for regression in final.residual_summary.score_regressions
    )


def test_delivery_exhaustion_returns_incomplete_without_a_cycle_or_score() -> None:
    state = CONSENSUS.ReviewCycleState(("correctness",))

    resolution = state.handle_runner_delivery(
        {"session_outcome": "died", "reason": "bounded retries exhausted"}
    )

    assert resolution.status == "incomplete"
    assert resolution.review_result is not None
    assert resolution.review_result.outcome == "review_incomplete"
    assert resolution.review_result.lens_results == ()
    assert resolution.review_result.cycle_history == ()
    assert state.cycle_count == 0


def test_result_serialization_round_trips_schema_revision_bindings_and_routes() -> None:
    state = CONSENSUS.ReviewCycleState(
        ("correctness",),
        evidence_ledger={"lens:correctness": "ledger-entry-1"},
    )
    result = state.record_cycle(
        "0123456789abcdef0123456789abcdef01234567",
        {"correctness": _score("correctness", 9.4)},
    )

    serialized = result.to_json()
    restored = CONSENSUS.ReviewResult.from_json(serialized)
    payload = json.loads(serialized)

    assert restored.to_json() == serialized
    assert payload["schema"] == "review_result.v1"
    assert payload["collection_operation"] == {
        "operation": "collect",
        "schema": "review_result.v1",
    }
    assert payload["revision_binding"]["lens_revisions"] == {
        "correctness": "0123456789abcdef0123456789abcdef01234567"
    }
    assert payload["evidence_ledger"] == {"lens:correctness": "ledger-entry-1"}
    assert "verdict" not in payload


def test_unknown_result_schema_is_refused_instead_of_guessed() -> None:
    payload = _accepted_result().to_dict()
    payload["schema"] = "review_result.v2"

    with pytest.raises(
        CONSENSUS.UnsupportedReviewResultSchemaError,
        match="unsupported review result schema",
    ):
        CONSENSUS.ReviewResult.from_dict(payload)


def test_each_outcome_allows_only_its_named_resume_transition() -> None:
    results = (
        _accepted_result(),
        _repairs_result(),
        _cycle_cap_result(),
        _incomplete_result(),
    )

    for result in results:
        assert result.resume_transitions == (result.next_action,)
        assert result.require_resume_transition(result.next_action) == result.next_action
        with pytest.raises(CONSENSUS.ReviewConsensusError, match="does not allow transition"):
            result.require_resume_transition("undefined_transition")


def test_failed_delta_check_returns_an_accepted_lens_to_the_failing_set() -> None:
    state = CONSENSUS.ReviewCycleState(("correctness", "security"))
    state.record_cycle(
        "revision-1",
        {
            "correctness": _score("correctness", 9.4),
            "security": _score("security", 8.9),
        },
    )
    state.record_cycle(
        "revision-2",
        {"security": _score("security", 8.8)},
    )

    result = state.record_cycle(
        "revision-3",
        {"security": _score("security", 9.4)},
        delta_checks=(_delta("correctness", "revision-1", "revision-3", passed=False),),
    )

    retained = next(item for item in result.lens_results if item.lens_id == "correctness")
    assert result.outcome == "cycle_cap_best_available"
    assert result.failing_lenses == ("correctness",)
    assert state.next_lenses == ()
    assert retained.accepted is False


def test_passing_delta_check_retains_original_revision_without_a_full_rerun() -> None:
    state = CONSENSUS.ReviewCycleState(("correctness", "security"))
    state.record_cycle(
        "revision-1",
        {
            "correctness": _score("correctness", 9.4),
            "security": _score("security", 8.9),
        },
    )

    result = state.record_cycle(
        "revision-2",
        {"security": _score("security", 9.4)},
        delta_checks=(_delta("correctness", "revision-1", "revision-2", passed=True),),
    )

    retained = next(item for item in result.lens_results if item.lens_id == "correctness")
    assert result.outcome == "accepted"
    assert retained.reviewed_revision == "revision-1"
    assert retained.delta_check is not None
    assert result.cycle_history[1].attempted_lenses == ("security",)


@pytest.mark.parametrize("session_outcome", ["ran-empty", "died"])
def test_terminal_empty_or_dead_runner_delivery_does_not_consume_a_cycle(
    session_outcome: str,
) -> None:
    state = CONSENSUS.ReviewCycleState(("correctness",))

    resolution = state.handle_runner_delivery({"session_outcome": session_outcome})

    assert resolution.status == "incomplete"
    assert resolution.review_result is not None
    assert resolution.review_result.outcome == "review_incomplete"
    assert state.cycle_count == 0


def test_pending_runner_is_collected_once_and_never_read_as_empty_or_relaunched() -> None:
    state = CONSENSUS.ReviewCycleState(("correctness",))
    calls: list[dict[str, Any]] = []

    def collect(invocation: dict[str, Any]) -> dict[str, Any]:
        calls.append(invocation)
        return {
            "session_outcome": "ran",
            "findings": [{"content": "whole-diff evidence"}],
        }

    resolution = state.handle_runner_delivery(
        {
            "session_outcome": "pending",
            "handle": {"request_digest": "digest", "result_path": "result.json"},
        },
        collector=collect,
    )

    assert resolution.status == "ready"
    assert resolution.payload["findings"] == [{"content": "whole-diff evidence"}]
    assert calls == [
        {
            "operation": "collect",
            "handle": {"request_digest": "digest", "result_path": "result.json"},
        }
    ]
    assert state.cycle_count == 0


def test_cycle_state_round_trips_and_resumes_the_same_selective_rerun() -> None:
    state = CONSENSUS.ReviewCycleState(("correctness", "security"))
    state.record_cycle(
        "revision-1",
        {
            "correctness": _score("correctness", 9.4),
            "security": _score("security", 8.9),
        },
    )

    restored = CONSENSUS.ReviewCycleState.from_json(state.to_json())
    assert restored.next_lenses == ("security",)
    assert restored.cycle_count == 1

    result = restored.record_cycle(
        "revision-2",
        {"security": _score("security", 9.4)},
        delta_checks=(_delta("correctness", "revision-1", "revision-2", passed=True),),
    )
    assert result.outcome == "accepted"


def test_external_whole_diff_finding_is_adjudicated_but_never_scores_or_gates() -> None:
    finding = _finding(
        "external-reviewer",
        "external-new-finding",
        autofix_class="advisory",
        owner="downstream-resolver",
    )
    external = CONSENSUS.ExternalAdvisoryReview(
        reviewer_id="external-seat-1",
        reviewer_vendor="vendor-b",
        home_vendor="vendor-a",
        request_id="request-1",
        request_digest="digest-1",
        reviewed_revision="revision-1",
        findings=(finding,),
        adjudications=(
            CONSENSUS.ExternalFindingAdjudication(
                finding_id="external-new-finding",
                decision="keep",
                rationale="The independent whole-diff evidence is valid.",
                final_severity="P1",
                final_status="active",
            ),
        ),
    )
    state = CONSENSUS.ReviewCycleState(("correctness",))

    result = state.record_cycle(
        "revision-1",
        {"correctness": _score("correctness", 9.4)},
        external_review=external,
    )

    assert result.outcome == "accepted"
    assert result.lens_results[0].score.derived_overall == pytest.approx(9.4)
    assert "external-reviewer" not in result.attempted_lenses
    assert [item.finding_id for item in result.findings] == ["external-new-finding"]
    assert result.external_advisory_reviews[0].scoring_authority is False


def test_finding_routes_serialize_into_consolidated_fix_requests() -> None:
    state = CONSENSUS.ReviewCycleState(("correctness",))
    result = state.record_cycle(
        "revision-1",
        {"correctness": _score("correctness", 8.9)},
        findings=(_finding("correctness", "F-route"),),
    )

    payload = result.to_dict()
    assert payload["findings"][0]["autofix_class"] == "safe_auto"
    assert payload["findings"][0]["owner"] == "review-fixer"
    assert payload["fix_requests"][0]["finding_ids"] == ["F-route"]
    assert payload["fix_requests"][0]["touched_paths"] == ["src/correctness.py"]
