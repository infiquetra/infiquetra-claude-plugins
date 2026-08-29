"""Contract checks for Work's consumption of Code Review's typed result.

Work is a Markdown skill, so these tests read the shipped skill text directly. They do not use a
fixture that merely repeats the intended review behavior.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
WORK_SKILL = ROOT / "plugins" / "saga" / "skills" / "work" / "SKILL.md"
EXPECTED_OUTCOMES = (
    "accepted",
    "repairs_requested",
    "cycle_cap_best_available",
    "review_incomplete",
)


def _read_skill() -> str:
    return WORK_SKILL.read_text(encoding="utf-8")


def _section(text: str, start_heading: str, end_heading: str) -> str:
    start = text.find(start_heading)
    end = text.find(end_heading, start + len(start_heading))
    assert start >= 0, f"missing Work contract heading: {start_heading}"
    assert end >= 0, f"missing Work contract boundary: {end_heading}"
    return text[start:end]


def _gate_contract() -> str:
    # W8 (sdlc#89) deleted the 5.3b Verify section outright, so the gate region now
    # ends at the 5.4 heading; the section contract itself is unchanged.
    return _section(_read_skill(), "### 5.3 ", "### 5.4 ")


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _outcome_route(outcome: str) -> str:
    match = re.search(
        rf"^- \*\*`{re.escape(outcome)}`\*\* — (?P<body>.*?)(?=^- \*\*`|\n\n)",
        _gate_contract(),
        flags=re.DOTALL | re.MULTILINE,
    )
    assert match is not None, f"Work has no route for review outcome {outcome!r}"
    return _collapse(match.group("body"))


def test_work_names_exactly_the_four_typed_review_outcomes() -> None:
    outcomes = tuple(re.findall(r"^- \*\*`([^`]+)`\*\* —", _gate_contract(), flags=re.MULTILINE))
    assert outcomes == EXPECTED_OUTCOMES


def test_accepted_proceeds_even_with_priority_2_findings() -> None:
    route = _outcome_route("accepted")
    assert "proceed to PR-ready" in route
    assert "Priority 2 findings" in route


def test_repairs_requested_blocks_and_preserves_work_as_the_only_mutator() -> None:
    route = _outcome_route("repairs_requested")
    contract = _collapse(_gate_contract())
    assert "block PR-ready" in route
    assert "route the consolidated fix requests through Work" in route
    assert "`/code-review` never changes reviewed code" in contract
    assert "Work is the only mutator" in contract


def test_cycle_cap_best_available_proceeds_and_surfaces_residuals() -> None:
    route = _outcome_route("cycle_cap_best_available")
    assert "proceed with the cycle-three best-available revision" in route
    assert "surface every residual" in route


def test_review_incomplete_blocks_and_reports_that_review_did_not_run() -> None:
    route = _outcome_route("review_incomplete")
    assert "block PR-ready" in route
    assert "review did not run" in route
    assert "delivery did not establish a review" in route


def test_stale_review_still_blocks_as_a_freshness_check() -> None:
    contract = _collapse(_gate_contract())
    assert "a **stale** review blocks PR-ready" in contract
    assert "freshness decision, not an acceptance decision" in contract
    assert "git rev-list <REVIEWED_SHA>..HEAD --count" in contract
    assert "count `> 0`" in contract
    assert "keep PR-ready blocked and re-run `/code-review`" in contract


def test_priority_and_confidence_never_form_an_acceptance_gate() -> None:
    text = _read_skill()
    contract = _collapse(_gate_contract())
    assert "Finding Priority and confidence are reporting and routing metadata" in contract
    assert "neither can change the typed outcome" in contract

    obsolete_priority_rules = (r"\bP0\b", r"\bP1\b", r"Priority 0", r"Priority 1", r"P-level")
    for pattern in obsolete_priority_rules:
        assert re.search(pattern, text, flags=re.IGNORECASE) is None, (
            f"Work still contains the obsolete Priority acceptance rule {pattern!r}"
        )


def test_work_does_not_recompute_or_add_a_terminal_score_threshold() -> None:
    contract = _collapse(_gate_contract())
    assert "outcome set" in contract
    assert (
        "does not recompute scores, inspect thresholds, or derive acceptance from findings"
        in contract
    )
    assert re.search(r"below[- ]?5|<\s*5(?:\.0)?|5\.0\s+terminal", contract, re.IGNORECASE) is None


def test_work_reads_outcome_as_the_typed_results_only_decision_field() -> None:
    phase = _section(_read_skill(), "### 5.2 ", "### 5.3 ")
    collapsed = _collapse(phase)
    assert "The result's `outcome` is the sole decision field" in collapsed
    assert "envelope's verdict" not in collapsed
    assert "verdict in the header" not in collapsed
