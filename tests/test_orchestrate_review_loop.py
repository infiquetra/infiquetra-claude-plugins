"""Tests for the orchestrate review loop bound.

Each required scenario is its own test, named for the scenario, asserting the
decision the scenario names — not a weaker path that would stay green if the
control were deleted.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
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


def _finding(defect_class: str, rank: str = "lowest", *, blocking: bool = False) -> Any:
    return LOOP.Finding(defect_class=defect_class, rank=rank, blocking=blocking)


def _report(
    *defect_classes: str,
    rank: str = "lowest",
    blocking: bool = False,
    disposes: tuple[str, ...] = (),
) -> Any:
    return LOOP.ReviewReport.of(
        [_finding(name, rank=rank, blocking=blocking) for name in defect_classes],
        disposes=disposes,
    )


def _empty_report(*disposes: str) -> Any:
    return LOOP.ReviewReport.of((), disposes=disposes)


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


def test_a_changed_path_delta_does_not_include_unchanged_lines() -> None:
    previous = _artifact(doc="alpha\nbeta\ngamma\ndelta\nepsilon\n")
    current = _artifact(doc="alpha\nbeta\nGAMMA\ndelta\nepsilon\n")
    surface = LOOP.delta_of(previous, current).mapping()["doc"]
    assert "alpha" not in surface
    assert "beta" not in surface
    assert "delta" not in surface
    assert "epsilon" not in surface
    assert "-gamma" in surface
    assert "+GAMMA" in surface


@pytest.mark.parametrize("rank", ["lowest", "advisory", "P0", "blocking", ""])
def test_a_recurring_non_blocking_class_on_the_last_iteration_escalates_regardless_of_rank(
    rank: str,
) -> None:
    loop = LOOP.ReviewLoop()
    unit = f"unit-rank-{rank or 'empty'}"
    defect = "recurring-class"
    _repair_once(loop, unit, _artifact(doc="first"), defect)
    loop.begin_iteration(unit, _artifact(doc="disposed"))
    disposed = loop.conclude_iteration(unit, _empty_report(defect))
    assert disposed.kind == LOOP.VERDICT_PASS
    loop.begin_iteration(unit, _artifact(doc="last"))
    verdict = loop.conclude_iteration(unit, _report(defect, rank=rank, blocking=False))
    assert verdict.kind == LOOP.VERDICT_HALT_AND_ESCALATE
    assert verdict.iteration == LOOP.MAX_ITERATIONS
    assert defect in verdict.recurring_classes


@pytest.mark.parametrize("rank", ["lowest", "P0", "blocking", "unshippable"])
def test_only_new_non_blocking_findings_on_the_last_iteration_close_without_escalation(
    rank: str,
) -> None:
    loop = LOOP.ReviewLoop()
    unit = "unit-novel"
    loop.begin_iteration(unit, _artifact(doc="v0"))
    assert loop.conclude_iteration(unit, _empty_report()).kind == LOOP.VERDICT_PASS
    loop.begin_iteration(unit, _artifact(doc="v1"))
    assert loop.conclude_iteration(unit, _empty_report()).kind == LOOP.VERDICT_PASS
    loop.begin_iteration(unit, _artifact(doc="v2"))
    verdict = loop.conclude_iteration(unit, _report("new-class", rank=rank, blocking=False))
    assert verdict.kind == LOOP.VERDICT_PASS
    assert verdict.iteration == LOOP.MAX_ITERATIONS
    assert verdict.recurring_classes == frozenset()
    assert loop._units[unit].terminal is False
    with pytest.raises(LOOP.IterationBoundError):
        loop.begin_iteration(unit, _artifact(doc="v3"))


def test_a_new_blocking_finding_on_the_last_iteration_escalates() -> None:
    loop = LOOP.ReviewLoop()
    unit = "unit-new-blocking"
    for index in range(LOOP.MAX_ITERATIONS - 1):
        loop.begin_iteration(unit, _artifact(doc=f"v{index}"))
        assert loop.conclude_iteration(unit, _empty_report()).kind == LOOP.VERDICT_PASS
    loop.begin_iteration(unit, _artifact(doc="last"))
    verdict = loop.conclude_iteration(
        unit,
        _report("new-blocking-class", rank="advisory", blocking=True),
    )
    assert verdict.kind == LOOP.VERDICT_HALT_AND_ESCALATE
    assert verdict.recurring_classes == frozenset()


def test_findings_filed_when_the_last_iteration_closes_are_reachable_from_the_verdict() -> None:
    loop = LOOP.ReviewLoop()
    unit = "unit-filed"
    for index in range(LOOP.MAX_ITERATIONS - 1):
        loop.begin_iteration(unit, _artifact(doc=f"v{index}"))
        loop.conclude_iteration(unit, _empty_report())
    loop.begin_iteration(unit, _artifact(doc="last"))
    report = LOOP.ReviewReport.of(
        (
            _finding("documentation", blocking=False),
            _finding("naming", rank="note", blocking=False),
        )
    )
    verdict = loop.conclude_iteration(unit, report)
    assert verdict.kind == LOOP.VERDICT_PASS
    assert verdict.findings == report.findings


@pytest.mark.parametrize("blocking", [False, True])
def test_findings_before_the_last_iteration_still_halt_for_repair(blocking: bool) -> None:
    loop = LOOP.ReviewLoop()
    loop.begin_iteration("unit-early-finding", _artifact(doc="v0"))
    verdict = loop.conclude_iteration(
        "unit-early-finding",
        _report("early-class", blocking=blocking),
    )
    assert verdict.kind == LOOP.VERDICT_HALT_AND_REPAIR
    assert verdict.iteration < LOOP.MAX_ITERATIONS


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
    tainted = loop.conclude_iteration("unit-spin", _empty_report())
    assert tainted.kind == LOOP.VERDICT_HALT_AND_REPAIR
    assert tainted.kind != LOOP.VERDICT_PASS


def test_a_caller_with_no_review_result_exits_without_passing() -> None:
    loop = LOOP.ReviewLoop()
    loop.begin_iteration("unit-none", _artifact(doc="v0"))
    loop.record_unperformed("unit-none")
    loop.record_unperformed("unit-none")
    loop.record_unperformed("unit-none")
    with pytest.raises(LOOP.UnperformedBoundError):
        loop.record_unperformed("unit-none")
    verdict = loop.conclude_unperformed("unit-none")
    assert verdict.kind == LOOP.VERDICT_HALT_AND_REPAIR
    assert verdict.kind != LOOP.VERDICT_PASS
    assert verdict.iteration == 1
    second = loop.begin_iteration("unit-none", _artifact(doc="v1"))
    assert second.iteration == 2
    loop.record_unperformed("unit-none")
    assert loop.conclude_iteration("unit-none", _empty_report()).kind != LOOP.VERDICT_PASS


def test_an_iteration_with_unperformed_records_cannot_pass() -> None:
    loop = LOOP.ReviewLoop()
    loop.begin_iteration("unit-taint", _artifact(doc="v0"))
    loop.record_unperformed("unit-taint")
    verdict = loop.conclude_iteration("unit-taint", _empty_report())
    assert verdict.kind == LOOP.VERDICT_HALT_AND_REPAIR


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
    assert loop.conclude_iteration(unit, _empty_report("x")).kind == LOOP.VERDICT_PASS
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


def test_an_empty_delta_does_not_pass_an_open_class() -> None:
    loop = LOOP.ReviewLoop()
    artifact = _artifact(doc="the defect is in this file\n")
    loop.begin_iteration("unit-silence", artifact)
    assert loop.conclude_iteration("unit-silence", _report("absence-inferred")).kind == (
        LOOP.VERDICT_HALT_AND_REPAIR
    )
    second = loop.begin_iteration("unit-silence", artifact)
    assert second.scoped_to_delta is True
    assert second.surface.mapping() == {}
    with pytest.raises(LOOP.ReviewLoopError, match="explicit disposal"):
        loop.conclude_iteration("unit-silence", _empty_report())
    assert loop._units["unit-silence"].open is True
    verdict = loop.conclude_iteration("unit-silence", _empty_report("absence-inferred"))
    assert verdict.kind == LOOP.VERDICT_PASS


def test_an_unrelated_path_edit_does_not_pass_an_open_class() -> None:
    loop = LOOP.ReviewLoop()
    loop.begin_iteration("unit-side", _artifact(broken="bad\n", notes="ok\n"))
    loop.conclude_iteration("unit-side", _report("absence-inferred"))
    second = loop.begin_iteration("unit-side", _artifact(broken="bad\n", notes="changed\n"))
    assert list(second.surface.mapping()) == ["notes"]
    assert "broken" not in second.surface.mapping()
    with pytest.raises(LOOP.ReviewLoopError, match="explicit disposal"):
        loop.conclude_iteration("unit-side", _empty_report())
    verdict = loop.conclude_iteration("unit-side", _empty_report("absence-inferred"))
    assert verdict.kind == LOOP.VERDICT_PASS


def test_disposing_and_re_raising_the_same_class_is_refused() -> None:
    with pytest.raises(LOOP.ReviewLoopError, match="dispose and re-raise"):
        LOOP.ReviewReport.of([_finding("absence-inferred")], disposes=["absence-inferred"])


def test_disposing_a_class_that_was_never_open_is_refused() -> None:
    loop = LOOP.ReviewLoop()
    loop.begin_iteration("unit-typo", _artifact(doc="v0"))
    with pytest.raises(LOOP.ReviewLoopError, match="not an open class"):
        loop.conclude_iteration("unit-typo", _empty_report("never-raised"))


def test_last_iteration_with_undisposed_classes_escalates() -> None:
    loop = LOOP.ReviewLoop()
    unit = "unit-last-open"
    _repair_once(loop, unit, _artifact(doc="v0"), "absence-inferred")
    _repair_once(loop, unit, _artifact(doc="v1"), "other")
    loop.begin_iteration(unit, _artifact(doc="v2"))
    verdict = loop.conclude_iteration(unit, _empty_report())
    assert verdict.kind == LOOP.VERDICT_HALT_AND_ESCALATE
    assert loop._units[unit].terminal is True


def test_unit_ids_that_differ_only_by_outer_whitespace_are_one_unit() -> None:
    loop = LOOP.ReviewLoop()
    first = loop.begin_iteration("U6 ", _artifact(doc="v0"))
    assert first.unit_id == "U6"
    loop.conclude_iteration("U6", _report("x"))
    second = loop.begin_iteration("  U6", _artifact(doc="v1"))
    assert second.unit_id == "U6"
    assert second.iteration == 2
    assert set(loop._units) == {"U6"}


def test_defect_classes_that_differ_only_by_outer_whitespace_are_one_class() -> None:
    loop = LOOP.ReviewLoop()
    loop.begin_iteration("unit-cls", _artifact(doc="v0"))
    loop.conclude_iteration("unit-cls", _report(" absence-inferred "))
    loop.begin_iteration("unit-cls", _artifact(doc="v1"))
    verdict = loop.conclude_iteration("unit-cls", _report("absence-inferred"))
    assert verdict.kind == LOOP.VERDICT_HALT_AND_REPAIR
    assert "absence-inferred" in verdict.recurring_classes
    assert loop._units["unit-cls"].open_classes == {"absence-inferred"}


def test_unit_id_and_defect_class_are_canonicalised_at_one_site_each() -> None:
    tree = ast.parse(SOURCE)
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def _enclosing_function(node: ast.AST) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        current: ast.AST | None = node
        while current is not None:
            if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
                return current
            current = parents.get(current)
        return None

    strip_functions: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "strip":
            continue
        owner = _enclosing_function(node)
        assert owner is not None, "str.strip is used outside a function"
        strip_functions[owner.name] = strip_functions.get(owner.name, 0) + 1
    assert strip_functions == {
        "_canonical_unit_id": 1,
        "_canonical_defect_class": 1,
    }

    by_name = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    for name, parameter in (
        ("_canonical_unit_id", "unit_id"),
        ("_canonical_defect_class", "name"),
    ):
        function = by_name[name]
        returns = [
            stmt.value
            for stmt in function.body
            if isinstance(stmt, ast.Return) and stmt.value is not None
        ]
        assert returns, f"{name} has no return"
        for value in returns:
            assert isinstance(value, ast.Name), f"{name} returns {ast.dump(value)}"
            assert value.id != parameter, f"{name} returns the raw identifier"


def test_begin_iteration_resets_the_unperformed_counter() -> None:
    loop = LOOP.ReviewLoop()
    loop.begin_iteration("unit-reset", _artifact(doc="v0"))
    for _ in range(LOOP.MAX_UNPERFORMED):
        loop.record_unperformed("unit-reset")
    loop.conclude_unperformed("unit-reset")
    loop.begin_iteration("unit-reset", _artifact(doc="v1"))
    loop.record_unperformed("unit-reset")
    assert loop._units["unit-reset"].unperformed == 1


def test_blocking_is_a_required_keyword_boolean_and_is_not_derived_from_rank() -> None:
    signature = inspect.signature(LOOP.Finding)
    parameter = signature.parameters["blocking"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty

    with pytest.raises(TypeError, match="blocking"):
        LOOP.Finding("declared-class", "lowest")
    with pytest.raises(TypeError, match="positional"):
        LOOP.Finding("declared-class", "lowest", False)
    for value in ("blocking", "P0", 0, 1, None):
        with pytest.raises(LOOP.ReviewLoopError, match="blocking as a boolean"):
            LOOP.Finding("declared-class", "lowest", blocking=value)

    tree = ast.parse(SOURCE)
    conclude = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "conclude_iteration"
    )
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "rank" for node in ast.walk(conclude)
    )


def test_the_last_iteration_escalation_guard_reads_only_its_declared_evidence() -> None:
    tree = ast.parse(SOURCE)
    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "final_escalation"
            for target in node.targets
        )
    ]
    assert len(assignments) == 1
    value = assignments[0].value
    assert isinstance(value, ast.Call)
    assert isinstance(value.func, ast.Name) and value.func.id == "bool"
    assert len(value.args) == 1 and isinstance(value.args[0], ast.BoolOp)
    assert isinstance(value.args[0].op, ast.Or)
    assert {ast.unparse(operand) for operand in value.args[0].values} == {
        "recurring",
        "unresolved_prior",
        "blocking_classes",
        "state.unperformed",
    }


def test_a_blank_defect_class_is_refused() -> None:
    with pytest.raises(LOOP.ReviewLoopError, match="declare a defect class"):
        LOOP.Finding("", "lowest", blocking=False)
    with pytest.raises(LOOP.ReviewLoopError, match="declare a defect class"):
        LOOP.Finding("   ", "lowest", blocking=False)


def test_a_review_report_cannot_be_built_from_a_bare_string() -> None:
    with pytest.raises(LOOP.ReviewLoopError, match="sequence of Finding"):
        LOOP.ReviewReport.of("not-findings")


def test_artifact_text_must_be_a_string() -> None:
    with pytest.raises(LOOP.ReviewLoopError, match="must be a string"):
        LOOP.Artifact.from_mapping({"doc": 1})  # type: ignore[dict-item]


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
