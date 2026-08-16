"""Tests for the orchestrate review loop bound.

Each required scenario is its own test, named for the scenario, asserting the
decision the scenario names — not a weaker path that would stay green if the
control were deleted.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "orchestrate" / "skills" / "orchestrate" / "scripts"
SOURCE_PATH = SCRIPTS / "review_loop.py"


def _load() -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("review_loop", SOURCE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["review_loop"] = module
    spec.loader.exec_module(module)
    return module


LOOP = _load()
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


def _artifact(**parts: str) -> Any:
    return LOOP.Artifact.from_mapping(parts)


def _finding(defect_class: str, rank: str = "lowest") -> Any:
    return LOOP.Finding(defect_class=defect_class, rank=rank)


def _report(*defect_classes: str, rank: str = "lowest") -> Any:
    return LOOP.ReviewReport.of([_finding(name, rank=rank) for name in defect_classes])


def _empty_report() -> Any:
    return LOOP.ReviewReport.of(())


def _repair_once(loop: Any, unit_id: str, artifact: Any, defect_class: str) -> Any:
    loop.begin_iteration(unit_id, artifact)
    return loop.conclude_iteration(unit_id, _report(defect_class))


def _drive_same_class_to_last_iteration(loop: Any, unit_id: str, defect_class: str) -> None:
    for index in range(LOOP.MAX_ITERATIONS - 1):
        verdict = _repair_once(loop, unit_id, _artifact(doc=f"{unit_id}-{index}"), defect_class)
        assert verdict.kind == LOOP.VERDICT_HALT_AND_REPAIR
    loop.begin_iteration(unit_id, _artifact(doc=f"{unit_id}-last"))


def test_a_fourth_iteration_is_refused() -> None:
    loop = LOOP.ReviewLoop()
    unit = "unit-cap"
    for index in range(LOOP.MAX_ITERATIONS):
        loop.begin_iteration(unit, _artifact(doc=f"v{index}"))
        verdict = loop.conclude_iteration(unit, _empty_report())
        assert verdict.kind == LOOP.VERDICT_PASS
        assert verdict.iteration == index + 1
    with pytest.raises(LOOP.IterationBoundError, match="further iteration is refused") as caught:
        loop.begin_iteration(unit, _artifact(doc="v-overflow"))
    assert "3" in str(caught.value)


def test_a_re_review_receives_only_the_delta() -> None:
    loop = LOOP.ReviewLoop()
    first = loop.begin_iteration(
        "unit-delta",
        _artifact(keep="unchanged\n", edit="before\n", drop="gone\n"),
    )
    assert first.scoped_to_delta is False
    assert first.surface.mapping() == {
        "keep": "unchanged\n",
        "edit": "before\n",
        "drop": "gone\n",
    }
    loop.conclude_iteration("unit-delta", _report("needs-repair"))

    second = loop.begin_iteration(
        "unit-delta",
        _artifact(keep="unchanged\n", edit="after\n", add="new\n"),
    )
    assert second.scoped_to_delta is True
    surface = second.surface.mapping()
    assert "keep" not in surface
    assert surface["edit"] != "after\n"
    assert "-before" in surface["edit"]
    assert "+after" in surface["edit"]
    assert "+new" in surface["add"]
    assert "-gone" in surface["drop"]
    assert "unchanged" not in surface["edit"]
    assert "unchanged" not in surface["add"]
    assert "unchanged" not in surface["drop"]


@pytest.mark.parametrize("rank", ["lowest", "advisory", "blocking", ""])
def test_the_same_declared_class_in_a_third_iteration_yields_halt_and_escalate_regardless_of_its_rank(
    rank: str,
) -> None:
    loop = LOOP.ReviewLoop()
    unit = f"unit-rank-{rank or 'empty'}"
    defect = "recurring-class"
    _drive_same_class_to_last_iteration(loop, unit, defect)
    verdict = loop.conclude_iteration(unit, _report(defect, rank=rank))
    assert verdict.kind == LOOP.VERDICT_HALT_AND_ESCALATE
    assert verdict.iteration == LOOP.MAX_ITERATIONS
    assert defect in verdict.recurring_classes


def test_findings_on_the_last_iteration_escalate_even_when_the_class_is_new() -> None:
    """A last-iteration finding cannot be repaired. The verdict must say so.

    The earlier scenario that a novel last-iteration class stayed in
    ``halt-and-repair`` made the verdict a lie: the next begin is refused.
    Recurrence is sufficient to escalate. It is not required.
    """
    loop = LOOP.ReviewLoop()
    unit = "unit-novel"
    _repair_once(loop, unit, _artifact(doc="v0"), "first")
    _repair_once(loop, unit, _artifact(doc="v1"), "second")
    loop.begin_iteration(unit, _artifact(doc="v2"))
    verdict = loop.conclude_iteration(unit, _report("third", rank="lowest"))
    assert verdict.kind == LOOP.VERDICT_HALT_AND_ESCALATE
    assert verdict.iteration == LOOP.MAX_ITERATIONS
    assert verdict.recurring_classes == frozenset()
    assert loop._units[unit].terminal is True
    with pytest.raises(LOOP.UnitTerminalError):
        loop.begin_iteration(unit, _artifact(doc="v3"))


def test_three_novel_classes_end_in_a_verdict_not_a_refused_repair() -> None:
    loop = LOOP.ReviewLoop()
    unit = "unit-fresh"
    first = _repair_once(loop, unit, _artifact(doc="v0"), "alpha")
    second = _repair_once(loop, unit, _artifact(doc="v1"), "beta")
    third = _repair_once(loop, unit, _artifact(doc="v2"), "gamma")
    assert first.kind == LOOP.VERDICT_HALT_AND_REPAIR
    assert first.iteration == 1
    assert second.kind == LOOP.VERDICT_HALT_AND_REPAIR
    assert second.iteration == 2
    assert third.kind == LOOP.VERDICT_HALT_AND_ESCALATE
    assert third.iteration == 3
    state = loop._units[unit]
    assert state.last_verdict == LOOP.VERDICT_HALT_AND_ESCALATE
    assert state.terminal is True
    assert "gamma" in state.escalated_classes
    with pytest.raises(LOOP.UnitTerminalError):
        loop.begin_iteration(unit, _artifact(doc="v3"))


def test_a_second_escalation_for_one_unit_is_refused() -> None:
    loop = LOOP.ReviewLoop()
    _drive_same_class_to_last_iteration(loop, "unit-once", "sticky")
    first = loop.conclude_iteration("unit-once", _report("sticky"))
    assert first.kind == LOOP.VERDICT_HALT_AND_ESCALATE

    with pytest.raises(LOOP.UnitTerminalError, match="spent its escalation"):
        loop.begin_iteration("unit-once", _artifact(doc="again"))
    with pytest.raises(LOOP.UnitTerminalError, match="spent its escalation"):
        loop.conclude_iteration("unit-once", _empty_report())

    _drive_same_class_to_last_iteration(loop, "unit-other", "sticky")
    other = loop.conclude_iteration("unit-other", _report("sticky"))
    assert other.kind == LOOP.VERDICT_HALT_AND_ESCALATE


def test_an_iteration_with_no_findings_passes_only_from_a_performed_report() -> None:
    loop = LOOP.ReviewLoop()
    scope = loop.begin_iteration("unit-pass", _artifact(doc="done"))
    assert scope.iteration == 1
    verdict = loop.conclude_iteration("unit-pass", _empty_report())
    assert verdict.kind == LOOP.VERDICT_PASS
    assert verdict.kind in LOOP.VERDICTS


def test_a_bare_sequence_cannot_conclude_an_iteration() -> None:
    loop = LOOP.ReviewLoop()
    loop.begin_iteration("unit-seq", _artifact(doc="x"))
    with pytest.raises(LOOP.ReviewLoopError, match="ReviewReport") as caught:
        loop.conclude_iteration("unit-seq", [])
    assert "sequence is not evidence" in str(caught.value)
    with pytest.raises(LOOP.ReviewLoopError, match="ReviewReport"):
        loop.conclude_iteration("unit-seq", ())
    # The iteration is still open; a performed empty report can still conclude it.
    verdict = loop.conclude_iteration("unit-seq", _empty_report())
    assert verdict.kind == LOOP.VERDICT_PASS
    assert verdict.iteration == 1


def test_an_unperformed_review_does_not_emit_a_verdict_or_consume_the_iteration() -> None:
    loop = LOOP.ReviewLoop()
    scope = loop.begin_iteration("unit-miss", _artifact(doc="v0"))
    assert scope.iteration == 1
    assert loop.record_unperformed("unit-miss") is None
    with pytest.raises(LOOP.ReviewLoopError, match="still has an open iteration"):
        loop.begin_iteration("unit-miss", _artifact(doc="v1"))
    verdict = loop.conclude_iteration("unit-miss", _report("still-here"))
    assert verdict.kind == LOOP.VERDICT_HALT_AND_REPAIR
    assert verdict.iteration == 1


def test_unperformed_reviews_on_one_iteration_are_capped() -> None:
    loop = LOOP.ReviewLoop()
    loop.begin_iteration("unit-spin", _artifact(doc="v0"))
    for _ in range(LOOP.MAX_UNPERFORMED):
        loop.record_unperformed("unit-spin")
    with pytest.raises(LOOP.UnperformedBoundError, match="unperformed"):
        loop.record_unperformed("unit-spin")
    verdict = loop.conclude_iteration("unit-spin", _empty_report())
    assert verdict.kind == LOOP.VERDICT_PASS
    assert verdict.iteration == 1


def test_a_unit_that_has_escalated_returns_no_later_verdict() -> None:
    loop = LOOP.ReviewLoop()
    _drive_same_class_to_last_iteration(loop, "unit-closed", "sticky")
    verdict = loop.conclude_iteration("unit-closed", _report("sticky"))
    assert verdict.kind == LOOP.VERDICT_HALT_AND_ESCALATE
    with pytest.raises(LOOP.UnitTerminalError):
        loop.begin_iteration("unit-closed", _artifact(doc="later"))
    with pytest.raises(LOOP.UnitTerminalError):
        loop.conclude_iteration("unit-closed", _empty_report())
    with pytest.raises(LOOP.UnitTerminalError):
        loop.record_unperformed("unit-closed")


def test_the_class_that_caused_escalation_is_not_forgotten() -> None:
    loop = LOOP.ReviewLoop()
    _drive_same_class_to_last_iteration(loop, "unit-keep", "sticky")
    loop.conclude_iteration("unit-keep", _report("sticky"))
    state = loop._units["unit-keep"]
    assert "sticky" in state.escalated_classes
    assert "sticky" in state.seen_classes
    assert state.terminal is True
    tree = ast.parse(SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr in {
                    "seen_classes",
                    "escalated_classes",
                }:
                    pytest.fail(
                        f"{target.attr} is reassigned at line {node.lineno}; "
                        "seen classes must only grow"
                    )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"clear", "difference_update", "intersection_update"}
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr in {"seen_classes", "escalated_classes"}
        ):
            pytest.fail(f"{node.func.value.attr}.{node.func.attr} at line {node.lineno}")


def test_a_pass_does_not_reset_the_per_unit_iteration_cap() -> None:
    loop = LOOP.ReviewLoop()
    unit = "unit-life"
    loop.begin_iteration(unit, _artifact(doc="v0"))
    assert loop.conclude_iteration(unit, _empty_report()).kind == LOOP.VERDICT_PASS
    loop.begin_iteration(unit, _artifact(doc="v1"))
    assert loop.conclude_iteration(unit, _report("x")).kind == LOOP.VERDICT_HALT_AND_REPAIR
    loop.begin_iteration(unit, _artifact(doc="v2"))
    assert loop.conclude_iteration(unit, _empty_report()).kind == LOOP.VERDICT_PASS
    with pytest.raises(LOOP.IterationBoundError, match="further iteration is refused"):
        loop.begin_iteration(unit, _artifact(doc="v3"))


def test_an_escalation_refusal_closes_the_iteration_and_the_unit() -> None:
    loop = LOOP.ReviewLoop()
    unit = "unit-wedge"
    _repair_once(loop, unit, _artifact(doc="v0"), "sticky")
    _repair_once(loop, unit, _artifact(doc="v1"), "sticky")
    loop.begin_iteration(unit, _artifact(doc="v2"))
    state = loop._units[unit]
    state.escalations = 1
    assert state.open is True
    with pytest.raises(LOOP.EscalationBudgetError, match="further escalation is refused"):
        loop.conclude_iteration(unit, _report("sticky"))
    assert state.open is False
    assert state.terminal is True
    with pytest.raises(LOOP.UnitTerminalError):
        loop.conclude_iteration(unit, _empty_report())


def test_the_escalation_budget_is_a_constant_with_no_parameter_path_to_change_it() -> None:
    """The comparison that refuses a second escalation reads ESCALATION_BUDGET.

    A name scan of parameters stays green if the constant is replaced by an
    innocuous argument. This walk fails unless every comparison against the
    escalation count uses that name.
    """
    tree = ast.parse(SOURCE)
    bindings: list[ast.Assign | ast.AnnAssign] = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == "ESCALATION_BUDGET"
                for target in statement.targets
            ):
                bindings.append(statement)
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "ESCALATION_BUDGET"
        ):
            bindings.append(statement)
    assert len(bindings) == 1, f"ESCALATION_BUDGET is bound {len(bindings)} times at module level"
    bound = bindings[0]
    value = bound.value
    assert isinstance(value, ast.Constant)
    assert value.value == 1

    stores = [
        name
        for name in ast.walk(tree)
        if isinstance(name, ast.Name)
        and name.id == "ESCALATION_BUDGET"
        and isinstance(name.ctx, ast.Store)
    ]
    assert len(stores) == 1, "ESCALATION_BUDGET is assigned more than once"

    operands = _escalation_guard_operands(tree)
    assert operands, "the escalation count is never compared"
    for operand in operands:
        assert isinstance(operand, ast.Name), (
            f"escalation guard reads {ast.dump(operand)}, not ESCALATION_BUDGET"
        )
        assert operand.id == "ESCALATION_BUDGET"


def _is_escalations_access(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "escalations"


def _escalation_guard_operands(tree: ast.AST) -> list[ast.AST]:
    operands: list[ast.AST] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        sides: list[ast.AST] = [node.left, *node.comparators]
        if any(_is_escalations_access(side) for side in sides):
            operands.extend(side for side in sides if not _is_escalations_access(side))
    return operands
