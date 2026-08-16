"""Tests for the orchestration consensus panel and the single-voter plan rigor pass."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "orchestrate" / "skills" / "orchestrate" / "scripts"
PANEL_PATH = SCRIPTS / "consensus_panel.py"
PLANNING_PATH = SCRIPTS / "planning.py"


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PANEL = _load("consensus_panel", PANEL_PATH)
PLANNING = _load("planning", PLANNING_PATH)
PANEL_SOURCE = PANEL_PATH.read_text(encoding="utf-8")
PLANNING_SOURCE = PLANNING_PATH.read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolate_runtime_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORCHESTRATE_REGISTER_DIR", str(tmp_path / "registers"))
    monkeypatch.setenv("ORCHESTRATE_RUN_SECRET_DIR", str(tmp_path / "secrets"))


def _dimensions() -> tuple[Any, ...]:
    return (
        PANEL.Dimension.gate("design", blocking_rank="P1"),
        PANEL.Dimension.score("clarity", threshold=9.0),
    )


def _configuration() -> Any:
    return PANEL.PanelConfiguration.for_layer("code-review", dimensions=_dimensions())


def _candidate(seat_id: str, vendor: str) -> Any:
    return PANEL.ReviewerCandidate(seat_id=seat_id, vendor=vendor, lens=f"{seat_id}-lens")


def _roster(
    *candidates: Any,
    quorum: int | None = None,
    mode: str = "standard",
    layer: str = "code-review",
) -> Any:
    return PANEL.build_roster(
        candidates,
        layer=layer,
        built_vendor="builder",
        home_vendor="home",
        mode=mode,
        quorum=quorum if quorum is not None else len(candidates),
    )


def _response(seat_id: str, *, rank: str = "pass", score: float = 9.5) -> Any:
    return PANEL.ReviewerResponse.of(
        seat_id,
        (
            PANEL.DimensionAssessment.gate("design", rank),
            PANEL.DimensionAssessment.score_value("clarity", score),
        ),
    )


def _plan_digest(path: Path) -> str:
    return str(PLANNING.plan_file_digest(path))


def _enclosing_function(tree: ast.AST, target: ast.AST) -> str | None:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    current: ast.AST | None = target
    while current is not None:
        if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
            return current.name
        current = parents.get(current)
    return None


def test_a_reviewer_whose_vendor_built_the_unit_is_excluded_from_the_roster() -> None:
    roster = PANEL.build_roster(
        (
            _candidate("builder-seat", "builder-vendor"),
            _candidate("independent-seat", "independent-vendor"),
        ),
        layer="code-review",
        built_vendor="BUILDER-VENDOR",
        home_vendor="home-vendor",
        quorum=1,
    )
    assert tuple(seat.seat_id for seat in roster.seats) == ("independent-seat",)
    assert [(item.candidate.seat_id, item.reason) for item in roster.excluded] == [
        ("builder-seat", "builder-vendor")
    ]
    assert all(seat.vendor != "builder-vendor" for seat in roster.seats)


def test_losing_a_voting_seat_below_quorum_halts_without_scoring_a_smaller_denominator() -> None:
    roster = _roster(
        _candidate("one", "vendor-one"),
        _candidate("two", "vendor-two"),
        _candidate("three", "vendor-three"),
        quorum=3,
    )
    outcome = PANEL.evaluate_panel(
        _configuration(),
        roster,
        (_response("one"), _response("two")),
    )
    assert outcome.decision == PANEL.PANEL_HALT
    assert outcome.reason == "quorum-lost"
    assert outcome.responded_seats == ("one", "two")
    assert outcome.missing_seats == ("three",)
    assert outcome.decision != PANEL.PANEL_PROCEED


def test_a_missing_seat_above_quorum_still_cannot_authorize_proceeding() -> None:
    roster = _roster(
        _candidate("one", "vendor-one"),
        _candidate("two", "vendor-two"),
        _candidate("three", "vendor-three"),
        quorum=2,
    )
    outcome = PANEL.evaluate_panel(
        _configuration(),
        roster,
        (_response("one"), _response("two")),
    )
    assert outcome.decision == PANEL.PANEL_HALT
    assert outcome.reason == "voting-seat-missing"
    assert outcome.missing_seats == ("three",)


def test_one_blocking_voice_halts_when_the_other_seat_would_proceed() -> None:
    roster = _roster(
        _candidate("escalates", "vendor-one"),
        _candidate("would-proceed", "vendor-two"),
        quorum=2,
    )
    outcome = PANEL.evaluate_panel(
        _configuration(),
        roster,
        (_response("escalates", rank="P1"), _response("would-proceed", rank="pass")),
    )
    assert outcome.decision == PANEL.PANEL_HALT
    assert outcome.reason == "blocking-gate"
    assert [(item.seat_id, item.rank) for item in outcome.blocking] == [("escalates", "P1")]
    assert outcome.missing_seats == ()


def test_a_score_records_convergence_but_cannot_override_clean_gate_ranks() -> None:
    roster = _roster(
        _candidate("one", "vendor-one"),
        _candidate("two", "vendor-two"),
        quorum=2,
    )
    outcome = PANEL.evaluate_panel(
        _configuration(),
        roster,
        (_response("one", score=9.5), _response("two", score=3.0)),
    )
    assert outcome.decision == PANEL.PANEL_PROCEED
    assert outcome.reason == "all-voting-seats-clear"
    assert [(item.seat_id, item.value) for item in outcome.scores["clarity"]] == [
        ("one", 9.5),
        ("two", 3.0),
    ]
    assert outcome.score_convergence["clarity"] is False


def test_each_dimension_refuses_the_other_instruments_configuration_and_value() -> None:
    with pytest.raises(PANEL.ConsensusPanelError, match="gate dimension refuses"):
        PANEL.Dimension(
            name="evidence",
            instrument=PANEL.GATE,
            threshold=8.0,
            blocking_rank="P1",
        )
    with pytest.raises(PANEL.ConsensusPanelError, match="score dimension refuses"):
        PANEL.Dimension(
            name="clarity",
            instrument=PANEL.SCORE,
            threshold=9.0,
            blocking_rank="P2",
        )

    roster = _roster(_candidate("one", "vendor-one"), quorum=1)
    config = _configuration()
    gate_with_score = PANEL.ReviewerResponse.of(
        "one",
        (
            PANEL.DimensionAssessment.score_value("design", 10.0),
            PANEL.DimensionAssessment.score_value("clarity", 10.0),
        ),
    )
    gate_outcome = PANEL.evaluate_panel(config, roster, (gate_with_score,))
    assert gate_outcome.decision == PANEL.PANEL_HALT
    assert gate_outcome.invalid_responses[0].seat_id == "one"
    assert (
        "gate dimension 'design' refuses a numeric score"
        in gate_outcome.invalid_responses[0].reason
    )

    score_with_rank = PANEL.ReviewerResponse.of(
        "one",
        (
            PANEL.DimensionAssessment.gate("design", "pass"),
            PANEL.DimensionAssessment.gate("clarity", "P3"),
        ),
    )
    score_outcome = PANEL.evaluate_panel(config, roster, (score_with_rank,))
    assert score_outcome.decision == PANEL.PANEL_HALT
    assert score_outcome.invalid_responses[0].seat_id == "one"
    assert "score dimension 'clarity' refuses a rank" in score_outcome.invalid_responses[0].reason


def test_the_rigor_pass_applies_a_safe_fix_and_reports_the_remainder_without_a_decision(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "orchestration-plan.md"
    plan_path.write_text("# Plan\n\nOwner: nobody\n\nMissing acceptance test.\n", encoding="utf-8")
    plan_path.chmod(0o640)
    report = PLANNING.run_plan_rigor_pass(
        plan_path,
        (
            PLANNING.PlanRigorFinding(
                finding_id="owner",
                summary="The owner is absent.",
                evidence="The Owner field says nobody.",
                recommendation="Name the operator.",
                safe_edit=PLANNING.SafePlanEdit("Owner: nobody", "Owner: operator"),
            ),
            PLANNING.PlanRigorFinding(
                finding_id="acceptance",
                summary="The acceptance test is unspecified.",
                evidence="The plan says the test is missing.",
                recommendation="The operator should choose a measurable acceptance test.",
            ),
        ),
        expected_digest=_plan_digest(plan_path),
    )
    assert "Owner: operator" in plan_path.read_text(encoding="utf-8")
    assert plan_path.stat().st_mode & 0o777 == 0o640
    assert [
        (item.finding_id, item.evidence, item.before, item.after) for item in report.applied
    ] == [("owner", "The Owner field says nobody.", "Owner: nobody", "Owner: operator")]
    assert len(report.remaining) == 1
    assert report.remaining[0].finding_id == "acceptance"
    assert report.remaining[0].recommendation.startswith("The operator")
    assert not hasattr(report, "verdict")
    with pytest.raises((AttributeError, TypeError)):
        report.verdict = "pass"

    report_fields = set(PLANNING.PlanRigorReport.__dataclass_fields__)
    assert report_fields == {"plan_path", "applied", "remaining"}
    planning_tree = ast.parse(PLANNING_SOURCE)
    imports = {
        alias.name
        for node in ast.walk(planning_tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert "consensus_panel" not in imports


def test_an_ambiguous_safe_fix_is_reported_instead_of_guessed(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("owner: none\nowner: none\n", encoding="utf-8")
    report = PLANNING.run_plan_rigor_pass(
        plan_path,
        (
            PLANNING.PlanRigorFinding(
                finding_id="owner",
                summary="Owner absent.",
                evidence="Two identical owner fields exist.",
                recommendation="Choose the intended field.",
                safe_edit=PLANNING.SafePlanEdit("owner: none", "owner: operator"),
            ),
        ),
        expected_digest=_plan_digest(plan_path),
    )
    assert report.applied == ()
    assert report.remaining[0].reason.endswith("found 2")
    assert plan_path.read_text(encoding="utf-8") == "owner: none\nowner: none\n"


def test_rigor_edits_preserve_unrelated_line_endings_and_match_exact_crlf_anchors(
    tmp_path: Path,
) -> None:
    mixed = tmp_path / "mixed.md"
    mixed.write_bytes(b"# Plan\nOwner: nobody\nPasted\r\nRest\n")
    PLANNING.run_plan_rigor_pass(
        mixed,
        (
            PLANNING.PlanRigorFinding(
                finding_id="owner",
                summary="Owner absent.",
                evidence="The owner field is empty.",
                recommendation="Name the operator.",
                safe_edit=PLANNING.SafePlanEdit("Owner: nobody", "Owner: operator"),
            ),
        ),
        expected_digest=_plan_digest(mixed),
    )
    assert mixed.read_bytes() == b"# Plan\nOwner: operator\nPasted\r\nRest\n"

    crlf = tmp_path / "crlf.md"
    crlf.write_bytes(b"Owner: nobody\r\nNext\r\n")
    report = PLANNING.run_plan_rigor_pass(
        crlf,
        (
            PLANNING.PlanRigorFinding(
                finding_id="owner",
                summary="Owner absent.",
                evidence="The owner field is empty.",
                recommendation="Name the operator.",
                safe_edit=PLANNING.SafePlanEdit(
                    "Owner: nobody\r\n",
                    "Owner: operator\r\n",
                ),
            ),
        ),
        expected_digest=_plan_digest(crlf),
    )
    assert [item.finding_id for item in report.applied] == ["owner"]
    assert crlf.read_bytes() == b"Owner: operator\r\nNext\r\n"


def test_rigor_pass_refuses_a_symlink_instead_of_replacing_it(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("Owner: nobody\n", encoding="utf-8")
    link = tmp_path / "plan.md"
    link.symlink_to(target)
    expected = hashlib.sha256(target.read_bytes()).hexdigest()
    finding = PLANNING.PlanRigorFinding(
        finding_id="owner",
        summary="Owner absent.",
        evidence="The owner field is empty.",
        recommendation="Name the operator.",
        safe_edit=PLANNING.SafePlanEdit("Owner: nobody", "Owner: operator"),
    )

    with pytest.raises(PLANNING.PlanningError, match="must not be a symlink"):
        PLANNING.run_plan_rigor_pass(link, (finding,), expected_digest=expected)

    assert link.is_symlink()
    assert target.read_text(encoding="utf-8") == "Owner: nobody\n"


def test_rigor_pass_refuses_a_stale_expected_digest(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("Owner: nobody\n", encoding="utf-8")
    expected = _plan_digest(plan_path)
    plan_path.write_text("Owner: operator\n", encoding="utf-8")

    with pytest.raises(PLANNING.PlanningError, match="changed after"):
        PLANNING.run_plan_rigor_pass(plan_path, (), expected_digest=expected)

    assert plan_path.read_text(encoding="utf-8") == "Owner: operator\n"


def test_rigor_pass_refuses_a_change_made_while_it_is_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("Owner: nobody\n", encoding="utf-8")
    expected = _plan_digest(plan_path)
    original_atomic_write = PLANNING._atomic_write_plan_text

    def _change_then_write(path: Path, text: str, *, expected_digest: str) -> None:
        path.write_text("Owner: someone else\n", encoding="utf-8")
        original_atomic_write(path, text, expected_digest=expected_digest)

    monkeypatch.setattr(PLANNING, "_atomic_write_plan_text", _change_then_write)
    finding = PLANNING.PlanRigorFinding(
        finding_id="owner",
        summary="Owner absent.",
        evidence="The owner field is empty.",
        recommendation="Name the operator.",
        safe_edit=PLANNING.SafePlanEdit("Owner: nobody", "Owner: operator"),
    )

    with pytest.raises(PLANNING.PlanningError, match="changed while"):
        PLANNING.run_plan_rigor_pass(
            plan_path,
            (finding,),
            expected_digest=expected,
        )

    assert plan_path.read_text(encoding="utf-8") == "Owner: someone else\n"


def test_rigor_anchors_are_evaluated_only_against_the_reviewed_text(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("alpha\nbeta\n", encoding="utf-8")
    report = PLANNING.run_plan_rigor_pass(
        plan_path,
        (
            PLANNING.PlanRigorFinding(
                finding_id="one",
                summary="First edit.",
                evidence="Alpha is present.",
                recommendation="Replace alpha.",
                safe_edit=PLANNING.SafePlanEdit("alpha", "gamma"),
            ),
            PLANNING.PlanRigorFinding(
                finding_id="two",
                summary="Second edit.",
                evidence="Gamma is claimed to be present.",
                recommendation="Replace gamma.",
                safe_edit=PLANNING.SafePlanEdit("gamma", "delta"),
            ),
        ),
        expected_digest=_plan_digest(plan_path),
    )

    assert plan_path.read_text(encoding="utf-8") == "gamma\nbeta\n"
    assert [item.finding_id for item in report.applied] == ["one"]
    assert report.remaining[0].finding_id == "two"
    assert report.remaining[0].reason.endswith("found 0")


def test_rigor_pass_refuses_overlapping_anchors(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("alpha beta\n", encoding="utf-8")
    report = PLANNING.run_plan_rigor_pass(
        plan_path,
        (
            PLANNING.PlanRigorFinding(
                finding_id="whole",
                summary="Whole phrase.",
                evidence="The phrase is present.",
                recommendation="Replace the phrase.",
                safe_edit=PLANNING.SafePlanEdit("alpha beta", "gamma"),
            ),
            PLANNING.PlanRigorFinding(
                finding_id="part",
                summary="Part of phrase.",
                evidence="The word is present.",
                recommendation="Replace the word.",
                safe_edit=PLANNING.SafePlanEdit("beta", "delta"),
            ),
        ),
        expected_digest=_plan_digest(plan_path),
    )

    assert plan_path.read_text(encoding="utf-8") == "gamma\n"
    assert [item.finding_id for item in report.applied] == ["whole"]
    assert report.remaining[0].reason == "safe edit overlaps a previously accepted anchor"


def test_under_external_only_the_home_vendor_cannot_be_constructed_as_a_voting_seat() -> None:
    roster = PANEL.build_roster(
        (
            _candidate("home-seat", "HOME-VENDOR"),
            _candidate("external-seat", "external-vendor"),
        ),
        layer="code-review",
        built_vendor="builder-vendor",
        home_vendor="home-vendor",
        mode=PANEL.EXTERNAL_ONLY_ROSTER,
        quorum=1,
    )
    assert [(seat.seat_id, seat.vendor) for seat in roster.seats] == [
        ("external-seat", "external-vendor")
    ]
    assert [(item.candidate.seat_id, item.reason) for item in roster.excluded] == [
        ("home-seat", "home-vendor-external-only")
    ]
    assert all(seat.vendor != roster.home_vendor for seat in roster.seats)

    with pytest.raises(PANEL.ConsensusPanelError, match="constructed by build_roster"):
        PANEL.VotingSeat(
            "bypass",
            "home-vendor",
            "lens",
            _constructor=object(),
        )


@pytest.mark.parametrize("ineligible_vendor", ["home", "builder"])
def test_evaluation_revalidates_forged_voting_seat_eligibility(ineligible_vendor: str) -> None:
    seat = object.__new__(PANEL.VotingSeat)
    object.__setattr__(seat, "seat_id", "forged")
    object.__setattr__(seat, "vendor", ineligible_vendor.upper())
    object.__setattr__(seat, "lens", "forged-lens")
    roster = object.__new__(PANEL.PanelRoster)
    object.__setattr__(roster, "layer", "code-review")
    object.__setattr__(roster, "mode", PANEL.EXTERNAL_ONLY_ROSTER)
    object.__setattr__(roster, "built_vendor", "builder")
    object.__setattr__(roster, "home_vendor", "home")
    object.__setattr__(roster, "quorum", 1)
    object.__setattr__(roster, "seats", (seat,))
    object.__setattr__(roster, "excluded", ())

    with pytest.raises(PANEL.ConsensusPanelError, match="structurally ineligible"):
        PANEL.evaluate_panel(_configuration(), roster, (_response("forged"),))


def test_evaluation_revalidates_forged_layer_policy() -> None:
    configuration = object.__new__(PANEL.PanelConfiguration)
    object.__setattr__(configuration, "layer", "orchestration-plan")
    object.__setattr__(configuration, "policy", PANEL.PANEL_ABSENT)
    object.__setattr__(configuration, "enabled", True)
    object.__setattr__(configuration, "dimensions", _dimensions())
    roster = _roster(_candidate("one", "vendor-one"), quorum=1)

    with pytest.raises(PANEL.ConsensusPanelError, match="one voter"):
        PANEL.evaluate_panel(configuration, roster, (_response("one"),))


def test_evaluation_refuses_a_mutable_roster_denominator_even_after_it_is_shrunk() -> None:
    seats = list(
        _roster(
            _candidate("one", "vendor-one"),
            _candidate("two", "vendor-two"),
            _candidate("three", "vendor-three"),
            quorum=3,
        ).seats
    )
    roster = object.__new__(PANEL.PanelRoster)
    object.__setattr__(roster, "layer", "code-review")
    object.__setattr__(roster, "mode", PANEL.STANDARD_ROSTER)
    object.__setattr__(roster, "built_vendor", "builder")
    object.__setattr__(roster, "home_vendor", "home")
    object.__setattr__(roster, "quorum", 2)
    object.__setattr__(roster, "seats", seats)
    object.__setattr__(roster, "excluded", ())
    seats.pop()

    with pytest.raises(PANEL.ConsensusPanelError, match="immutable tuple"):
        PANEL.evaluate_panel(
            _configuration(),
            roster,
            (_response("one"), _response("two")),
        )


def test_roster_requires_one_independent_vendor_per_voting_seat() -> None:
    with pytest.raises(PANEL.ConsensusPanelError, match="vendors must be unique"):
        _roster(
            _candidate("one", "same-vendor"),
            _candidate("two", "SAME-VENDOR"),
            _candidate("three", "same-vendor"),
            quorum=3,
        )


def test_enabled_panel_requires_a_gate_dimension() -> None:
    with pytest.raises(PANEL.ConsensusPanelError, match="at least one gate"):
        PANEL.PanelConfiguration.for_layer(
            "code-review",
            dimensions=(PANEL.Dimension.score("clarity", threshold=9.0),),
        )


def test_schema_invalid_response_halts_without_losing_another_seats_blocker() -> None:
    roster = _roster(
        _candidate("blocker", "vendor-one"),
        _candidate("malformed", "vendor-two"),
        quorum=2,
    )
    malformed = PANEL.ReviewerResponse.of(
        "malformed",
        (PANEL.DimensionAssessment.gate("design", "pass"),),
    )

    for responses in (
        (_response("blocker", rank="P0"), malformed),
        (malformed, _response("blocker", rank="P0")),
    ):
        outcome = PANEL.evaluate_panel(_configuration(), roster, responses)
        assert outcome.decision == PANEL.PANEL_HALT
        assert outcome.reason == "blocking-gate"
        assert [(item.seat_id, item.rank) for item in outcome.blocking] == [("blocker", "P0")]
        assert outcome.responded_seats == ("blocker",)
        assert outcome.missing_seats == ("malformed",)
        assert [item.seat_id for item in outcome.invalid_responses] == ["malformed"]


def test_an_empty_score_series_is_not_convergence() -> None:
    roster = PANEL.build_roster(
        (
            _candidate("home", "home"),
            _candidate("builder", "builder"),
        ),
        layer="code-review",
        built_vendor="builder",
        home_vendor="home",
        mode=PANEL.EXTERNAL_ONLY_ROSTER,
        quorum=2,
    )
    outcome = PANEL.evaluate_panel(_configuration(), roster, ())

    assert outcome.decision == PANEL.PANEL_HALT
    assert outcome.reason == "quorum-lost"
    assert outcome.scores["clarity"] == ()
    assert outcome.score_convergence["clarity"] is False


def test_scores_are_paired_with_seats_and_ordered_by_the_roster() -> None:
    roster = _roster(
        _candidate("one", "vendor-one"),
        _candidate("two", "vendor-two"),
        quorum=2,
    )
    outcome = PANEL.evaluate_panel(
        _configuration(),
        roster,
        (_response("two", score=2.0), _response("one", score=9.5)),
    )

    assert outcome.responded_seats == ("one", "two")
    assert [(item.seat_id, item.value) for item in outcome.scores["clarity"]] == [
        ("one", 9.5),
        ("two", 2.0),
    ]


def test_outcome_names_candidates_excluded_before_voting() -> None:
    roster = PANEL.build_roster(
        (
            _candidate("excluded", "builder"),
            _candidate("seated", "external"),
        ),
        layer="code-review",
        built_vendor="builder",
        home_vendor="home",
        quorum=1,
    )
    outcome = PANEL.evaluate_panel(_configuration(), roster, (_response("seated"),))

    assert outcome.decision == PANEL.PANEL_PROCEED
    assert [(item.candidate.seat_id, item.reason) for item in outcome.excluded_candidates] == [
        ("excluded", "builder-vendor")
    ]


def test_configuration_and_roster_must_name_the_same_review_layer() -> None:
    roster = _roster(_candidate("one", "vendor-one"), quorum=1, layer="qa")

    with pytest.raises(PANEL.ConsensusPanelError, match="does not match"):
        PANEL.evaluate_panel(_configuration(), roster, (_response("one"),))


def test_layer_policy_requires_code_review_and_qa_allows_doc_review_and_excludes_the_plan() -> None:
    dimensions = _dimensions()
    assert PANEL.PanelConfiguration.for_layer("code-review", dimensions=dimensions).enabled is True
    assert PANEL.PanelConfiguration.for_layer("qa", dimensions=dimensions).enabled is True
    assert PANEL.PanelConfiguration.for_layer("doc-review").enabled is False
    assert (
        PANEL.PanelConfiguration.for_layer(
            "doc-review", enabled=True, dimensions=dimensions
        ).enabled
        is True
    )
    plan = PANEL.PanelConfiguration.for_layer("orchestration-plan")
    assert plan.enabled is False
    assert plan.dimensions == ()
    with pytest.raises(PANEL.ConsensusPanelError, match="one voter"):
        PANEL.PanelConfiguration.for_layer(
            "orchestration-plan",
            enabled=True,
            dimensions=dimensions,
        )


def test_the_panel_and_review_loop_are_separate_modules_in_both_directions() -> None:
    panel_tree = ast.parse(PANEL_SOURCE)
    loop_path = SCRIPTS / "review_loop.py"
    loop_tree = ast.parse(loop_path.read_text(encoding="utf-8"))

    def _imports(tree: ast.AST) -> set[str]:
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    imported.add(node.module)
                imported.update(alias.name for alias in node.names)
        return imported

    assert "review_loop" not in _imports(panel_tree)
    assert "consensus_panel" not in _imports(loop_tree)
    assert "review_loop" in _imports(ast.parse("from review_loop import ReviewLoop"))
