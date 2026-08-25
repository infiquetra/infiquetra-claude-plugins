"""Lens-selection interaction contract for Code Review (#778)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "plugins" / "saga" / "scripts" / "review_consensus.py"
SKILL_PATH = ROOT / "plugins" / "saga" / "skills" / "code-review" / "SKILL.md"

ALWAYS_ON = {
    "architecture-maintainability",
    "correctness",
    "security",
    "testing",
}


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_consensus_lens_selection", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["review_consensus_lens_selection"] = module
    spec.loader.exec_module(module)
    return module


CONSENSUS: Any = _load_module()


def _doc_only() -> Any:
    return CONSENSUS.recommend_conditional_lenses(
        {
            "documentation-clarity": ("the change is documentation-only operator guidance"),
        }
    )


def _api_agent() -> Any:
    return CONSENSUS.recommend_conditional_lenses(
        {
            "api-contract": "the change exposes an agent-facing interface contract",
            "agent-usability": ("the change alters a skill agents must discover and operate"),
        }
    )


def test_always_on_four_are_pinned_and_cannot_be_omitted() -> None:
    assert set(CONSENSUS.ALWAYS_ON_LENSES) == ALWAYS_ON
    assert len(CONSENSUS.ALWAYS_ON_LENSES) == 4
    for lens_id in ALWAYS_ON:
        remaining = set(CONSENSUS.ALWAYS_ON_LENSES) - {lens_id}
        assert remaining != ALWAYS_ON


def test_documentation_only_diff_recommends_documentation_clarity() -> None:
    recs = _doc_only()
    assert [item.lens_id for item in recs] == ["documentation-clarity"]
    assert recs[0].reason


def test_documentation_only_decline_launches_always_on_four_only() -> None:
    recs = _doc_only()
    state = CONSENSUS.ReviewCycleState(CONSENSUS.always_on_lenses())
    decision = CONSENSUS.resolve_lens_selection(
        reviewed_commit="doc-rev",
        cycle=1,
        recommended=recs,
        state=state,
        operator_choice="always-on-only",
    )
    transcript = CONSENSUS.AgentCallTranscript()
    launched = CONSENSUS.launch_approved_lenses(
        reviewed_commit="doc-rev",
        cycle=1,
        state=state,
        decision=decision,
        agent=transcript,
    )
    assert launched == CONSENSUS.always_on_lenses()
    assert "documentation-clarity" not in launched
    assert transcript.conditional_agent_calls == ()


def test_api_agent_diff_approve_launches_conditionals_plus_always_on() -> None:
    recs = _api_agent()
    assert [item.lens_id for item in recs] == ["api-contract", "agent-usability"]
    state = CONSENSUS.ReviewCycleState(CONSENSUS.always_on_lenses())
    decision = CONSENSUS.resolve_lens_selection(
        reviewed_commit="api-rev",
        cycle=1,
        recommended=recs,
        state=state,
        operator_choice="accept-recommended",
    )
    transcript = CONSENSUS.AgentCallTranscript()
    launched = CONSENSUS.launch_approved_lenses(
        reviewed_commit="api-rev",
        cycle=1,
        state=state,
        decision=decision,
        agent=transcript,
    )
    assert launched == (
        *CONSENSUS.always_on_lenses(),
        "api-contract",
        "agent-usability",
    )
    assert transcript.conditional_agent_calls == ("api-contract", "agent-usability")
    approval = state.lens_approval_for("api-rev", 1)
    assert approval is not None
    assert approval.approved_conditionals == ("api-contract", "agent-usability")
    assert approval.source == "operator"


def test_unapproved_conditional_fails_before_agent_call() -> None:
    transcript = CONSENSUS.AgentCallTranscript()
    with pytest.raises(CONSENSUS.ReviewConsensusError, match="unapproved"):
        CONSENSUS.launch_approved_lenses(
            reviewed_commit="no-approval",
            cycle=1,
            extra_lenses=("documentation-clarity",),
            agent=transcript,
        )
    assert "documentation-clarity" not in transcript.agent_calls
    assert transcript.conditional_agent_calls == ()
    assert ("agent", "documentation-clarity") not in transcript.events


def test_no_conditional_agent_call_before_approval_record_in_transcript() -> None:
    recs = _api_agent()
    state = CONSENSUS.ReviewCycleState(CONSENSUS.always_on_lenses())
    transcript = CONSENSUS.AgentCallTranscript()
    with pytest.raises(CONSENSUS.ReviewConsensusError, match="unapproved"):
        CONSENSUS.launch_approved_lenses(
            reviewed_commit="order-rev",
            cycle=1,
            extra_lenses=("api-contract",),
            agent=transcript,
        )
    assert all(event[0] != "approval" for event in transcript.events), (
        "no approval record may exist when the unapproved spawn is refused"
    )
    assert transcript.conditional_agent_calls == ()

    decision = CONSENSUS.resolve_lens_selection(
        reviewed_commit="order-rev",
        cycle=1,
        recommended=recs,
        state=state,
        operator_choice="accept-recommended",
    )
    launched = CONSENSUS.launch_approved_lenses(
        reviewed_commit="order-rev",
        cycle=1,
        state=state,
        decision=decision,
        agent=transcript,
    )
    approval_indexes = [
        index for index, event in enumerate(transcript.events) if event[0] == "approval"
    ]
    assert approval_indexes, "approval must be recorded before conditional Agent calls"
    first_approval = approval_indexes[0]
    early_conditionals = [
        event
        for index, event in enumerate(transcript.events)
        if index < first_approval and event[0] == "agent" and event[1] not in ALWAYS_ON
    ]
    assert early_conditionals == []
    assert "api-contract" in launched


def test_caller_supplied_selection_is_approval_without_a_question() -> None:
    recs = _api_agent()
    state = CONSENSUS.ReviewCycleState(CONSENSUS.always_on_lenses())
    decision = CONSENSUS.resolve_lens_selection(
        reviewed_commit="caller-rev",
        cycle=1,
        recommended=recs,
        state=state,
        caller_selection=("api-contract", "agent-usability"),
        caller_source="orchestrate",
    )
    assert decision.needs_question is False
    assert decision.paused is False
    assert decision.approval is not None
    assert decision.approval.source == "orchestrate"
    assert decision.approval.question_asked is False
    transcript = CONSENSUS.AgentCallTranscript()
    launched = CONSENSUS.launch_approved_lenses(
        reviewed_commit="caller-rev",
        cycle=1,
        state=state,
        decision=decision,
        agent=transcript,
    )
    assert launched == (
        *CONSENSUS.always_on_lenses(),
        "api-contract",
        "agent-usability",
    )


def test_unchanged_repair_cycle_does_not_reask() -> None:
    recs = _api_agent()
    state = CONSENSUS.ReviewCycleState(CONSENSUS.always_on_lenses())
    first = CONSENSUS.resolve_lens_selection(
        reviewed_commit="repair-1",
        cycle=1,
        recommended=recs,
        state=state,
        operator_choice="accept-recommended",
    )
    assert first.needs_question is False
    second = CONSENSUS.resolve_lens_selection(
        reviewed_commit="repair-2",
        cycle=2,
        recommended=recs,
        state=state,
    )
    assert second.needs_question is False
    assert second.reused is True
    assert second.approved_conditionals == ("api-contract", "agent-usability")
    assert second.paused is False


def test_materially_changed_diff_asks_once_about_only_the_delta() -> None:
    recs = _api_agent()
    state = CONSENSUS.ReviewCycleState(CONSENSUS.always_on_lenses())
    CONSENSUS.resolve_lens_selection(
        reviewed_commit="delta-1",
        cycle=1,
        recommended=recs,
        state=state,
        operator_choice="accept-recommended",
    )
    widened = CONSENSUS.recommend_conditional_lenses(
        {
            "api-contract": "the change exposes an agent-facing interface contract",
            "agent-usability": ("the change alters a skill agents must discover and operate"),
            "documentation-clarity": "repair added operator-facing documentation",
        }
    )
    waiting = CONSENSUS.resolve_lens_selection(
        reviewed_commit="delta-2",
        cycle=2,
        recommended=widened,
        state=state,
    )
    assert waiting.needs_question is True
    assert waiting.paused is True
    assert waiting.question is not None
    assert waiting.question.kind == "delta"
    assert [item.lens_id for item in waiting.question.delta_added] == ["documentation-clarity"]
    assert waiting.question.delta_removed == ()
    transcript = CONSENSUS.AgentCallTranscript()
    paused_launch = CONSENSUS.launch_approved_lenses(
        reviewed_commit="delta-2",
        cycle=2,
        state=state,
        decision=waiting,
        agent=transcript,
    )
    assert paused_launch == CONSENSUS.always_on_lenses()
    assert transcript.conditional_agent_calls == ()

    accepted = CONSENSUS.resolve_lens_selection(
        reviewed_commit="delta-2",
        cycle=2,
        recommended=widened,
        state=state,
        operator_choice="accept-recommended",
    )
    assert accepted.needs_question is False
    assert "documentation-clarity" in accepted.approved_conditionals
    assert "api-contract" in accepted.approved_conditionals


def test_dismissal_or_no_answer_pauses_without_conditional_launches() -> None:
    recs = _doc_only()
    decision = CONSENSUS.resolve_lens_selection(
        reviewed_commit="pause-rev",
        cycle=1,
        recommended=recs,
    )
    assert decision.needs_question is True
    assert decision.paused is True
    assert decision.approval is None
    transcript = CONSENSUS.AgentCallTranscript()
    launched = CONSENSUS.launch_approved_lenses(
        reviewed_commit="pause-rev",
        cycle=1,
        decision=decision,
        agent=transcript,
    )
    assert launched == CONSENSUS.always_on_lenses()
    assert transcript.conditional_agent_calls == ()
    assert all(event[0] != "approval" for event in transcript.events)


def test_hidden_supplemental_lens_is_refused_before_agent_call() -> None:
    recs = _doc_only()
    state = CONSENSUS.ReviewCycleState(CONSENSUS.always_on_lenses())
    decision = CONSENSUS.resolve_lens_selection(
        reviewed_commit="hidden-rev",
        cycle=1,
        recommended=recs,
        state=state,
        operator_choice="accept-recommended",
    )
    transcript = CONSENSUS.AgentCallTranscript()
    with pytest.raises(CONSENSUS.ReviewConsensusError, match="unapproved"):
        CONSENSUS.launch_approved_lenses(
            reviewed_commit="hidden-rev",
            cycle=1,
            state=state,
            decision=decision,
            extra_lenses=("adversarial",),
            agent=transcript,
        )
    assert "adversarial" not in transcript.agent_calls


def test_approval_round_trips_on_existing_cycle_state() -> None:
    recs = _doc_only()
    state = CONSENSUS.ReviewCycleState(CONSENSUS.always_on_lenses())
    CONSENSUS.resolve_lens_selection(
        reviewed_commit="persist-rev",
        cycle=1,
        recommended=recs,
        state=state,
        operator_choice="accept-recommended",
    )
    restored = CONSENSUS.ReviewCycleState.from_json(state.to_json())
    approval = restored.lens_approval_for("persist-rev", 1)
    assert approval is not None
    assert approval.approved_conditionals == ("documentation-clarity",)
    assert approval.reviewed_commit == "persist-rev"
    assert approval.cycle == 1


def test_skill_states_always_on_set_and_batched_conditional_question() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    assert "always-on" in skill
    for lens_id in ALWAYS_ON:
        assert lens_id in skill
    for choice in ("accept-recommended", "always-on-only", "customize"):
        assert choice in skill
    assert "pauses" in skill
    assert "caller" in skill.lower() or "Orchestrate" in skill
