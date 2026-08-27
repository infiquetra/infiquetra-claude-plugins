"""Several independent Code Review controllers in one run, each owning its own target (#877).

One review phase is still one controller.  What this proves is the *other* shape: a run carrying
several independent child lifecycles, each with its own frozen review target and its own typed
``review_result.v1``.  Before this, Orchestrate refused that at both load and expand, so a campaign
with three ready targets could only review them serially through a single run-global controller --
and that controller carries ``review_outcome``, ``review_resubmit_pending`` and
``operator_fix_requests``, so serial reuse risks reading one target's typed state as another's.

The guard itself is not weakened.  An *unscoped* second controller is still the accidental panel it
has always been, and still fails with the same message.  What distinguishes the deliberate shape is
that every controller declares its own ``lifecycle``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "orchestrate"
    / "skills"
    / "orchestrate"
    / "scripts"
    / "orchestrate.py"
)


@pytest.fixture(scope="module")
def orchestrate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_orchestrate_scoped_controllers", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _controller(
    orchestrate: ModuleType,
    name: str,
    *,
    lifecycle: str | None = None,
    status: str | None = None,
) -> Any:
    return orchestrate.Unit(
        name=name,
        vendor="grok",
        task="/saga:code-review review the frozen target",
        role="review-controller",
        lifecycle=lifecycle,
        merge=False,
        status=status or orchestrate.PENDING,
    )


def _run(orchestrate: ModuleType, *units: Any, ceiling: int | None = None) -> Any:
    return orchestrate.Run(
        run_id="scoped-run",
        source="test",
        base="base",
        units=list(units),
        review_controller_ceiling=ceiling,
    )


# --- 1. the single-controller default is untouched, including today's error ------------------


def test_single_controller_run_still_resolves_to_that_controller(orchestrate: ModuleType) -> None:
    run = _run(orchestrate, _controller(orchestrate, "cr"))
    assert run.review_controller().name == "cr"
    assert orchestrate.assert_single_review_controller(run.units) is None


def test_two_unscoped_controllers_still_fail_with_todays_message(orchestrate: ModuleType) -> None:
    """The accidental panel must keep failing exactly as it did, or the guard is weakened."""
    units = [_controller(orchestrate, "cr-a"), _controller(orchestrate, "cr-b")]
    with pytest.raises(SystemExit) as excinfo:
        orchestrate.assert_single_review_controller(units)
    assert "create exactly one" in str(excinfo.value)

    with pytest.raises(SystemExit) as accessor:
        _run(orchestrate, *units).review_controller()
    assert "more than one Code Review controller" in str(accessor.value)


def test_partially_scoped_controllers_are_refused(orchestrate: ModuleType) -> None:
    """Scoping is all-or-nothing; one missing lifecycle is still the accidental panel."""
    units = [
        _controller(orchestrate, "cr-a", lifecycle="c2"),
        _controller(orchestrate, "cr-b"),
    ]
    with pytest.raises(SystemExit) as excinfo:
        orchestrate.assert_single_review_controller(units)
    assert "create exactly one" in str(excinfo.value)


def test_two_controllers_claiming_one_lifecycle_are_refused(orchestrate: ModuleType) -> None:
    units = [
        _controller(orchestrate, "cr-a", lifecycle="c2"),
        _controller(orchestrate, "cr-b", lifecycle="c2"),
    ]
    with pytest.raises(SystemExit) as excinfo:
        orchestrate.assert_single_review_controller(units)
    assert "both claim" in str(excinfo.value)


# --- 2. several scoped controllers load, and each owns its own typed state -------------------


def test_three_scoped_controllers_load(orchestrate: ModuleType) -> None:
    """The blocked Auralis shape: three ready targets, three independent controllers."""
    units = [
        _controller(orchestrate, "cr-c2", lifecycle="c2"),
        _controller(orchestrate, "cr-c4", lifecycle="c4"),
        _controller(orchestrate, "cr-c6", lifecycle="c6"),
    ]
    assert orchestrate.assert_single_review_controller(units) is None
    run = _run(orchestrate, *units)
    assert [u.name for u in run.review_controllers()] == ["cr-c2", "cr-c4", "cr-c6"]


def test_each_scoped_controller_keeps_its_own_typed_state(orchestrate: ModuleType) -> None:
    """The whole point: one controller's typed state is never legible as another's."""
    run = _run(
        orchestrate,
        _controller(orchestrate, "cr-c2", lifecycle="c2"),
        _controller(orchestrate, "cr-c4", lifecycle="c4"),
        _controller(orchestrate, "cr-c6", lifecycle="c6"),
    )
    c2, c4, c6 = run.review_controllers()

    run.write_review_slot(c2, review_outcome="accepted", review_resubmit_pending=False)
    run.write_review_slot(c4, review_outcome="repairs_requested", review_resubmit_pending=True)

    assert run.review_slot(c2)["review_outcome"] == "accepted"
    assert run.review_slot(c4)["review_outcome"] == "repairs_requested"
    assert run.review_slot(c6)["review_outcome"] is None
    assert run.review_slot(c2)["review_resubmit_pending"] is False
    assert run.review_slot(c4)["review_resubmit_pending"] is True

    # And nothing leaked into the run-level single-controller view.
    assert run.review_outcome is None
    assert run.review_resubmit_pending is False


def test_operator_fix_requests_do_not_leak_between_controllers(orchestrate: ModuleType) -> None:
    run = _run(
        orchestrate,
        _controller(orchestrate, "cr-c2", lifecycle="c2"),
        _controller(orchestrate, "cr-c4", lifecycle="c4"),
    )
    c2, c4 = run.review_controllers()
    run.review_slot(c2)["operator_fix_requests"].append({"fix_id": "only-c2"})
    assert run.review_slot(c4)["operator_fix_requests"] == []
    assert run.operator_fix_requests == []


def test_scoped_state_round_trips_through_save_and_load(
    orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    run = _run(
        orchestrate,
        _controller(orchestrate, "cr-c2", lifecycle="c2"),
        _controller(orchestrate, "cr-c4", lifecycle="c4"),
        ceiling=2,
    )
    run.write_review_slot(run.review_controllers()[0], review_outcome="accepted")
    run.save()

    reloaded = orchestrate.Run.load()
    assert reloaded.review_controller_ceiling == 2
    assert reloaded.review_states["cr-c2"]["review_outcome"] == "accepted"
    assert reloaded.review_states.get("cr-c4", {}).get("review_outcome") is None
    assert [u.lifecycle for u in reloaded.review_controllers()] == ["c2", "c4"]


# --- 3. a result routed to the wrong controller is refused ----------------------------------


def test_selecting_a_controller_by_name_or_lifecycle(orchestrate: ModuleType) -> None:
    run = _run(
        orchestrate,
        _controller(orchestrate, "cr-c2", lifecycle="c2"),
        _controller(orchestrate, "cr-c4", lifecycle="c4"),
    )
    assert run.review_controller_for("cr-c4").name == "cr-c4"
    assert run.review_controller_for("c4").name == "cr-c4"


def test_result_aimed_at_a_non_controller_unit_is_refused(orchestrate: ModuleType) -> None:
    worker = orchestrate.Unit(
        name="w1", vendor="claude", task="/saga:work build it", role="review-fixer"
    )
    run = _run(orchestrate, _controller(orchestrate, "cr-c2", lifecycle="c2"), worker)
    with pytest.raises(SystemExit) as excinfo:
        run.review_controller_for("w1")
    assert "is not a Code Review controller" in str(excinfo.value)


def test_result_aimed_at_an_unknown_controller_is_refused(orchestrate: ModuleType) -> None:
    run = _run(orchestrate, _controller(orchestrate, "cr-c2", lifecycle="c2"))
    with pytest.raises(SystemExit) as excinfo:
        run.review_controller_for("cr-c9")
    assert "no Code Review controller" in str(excinfo.value)


def test_ambiguous_result_is_refused_rather_than_guessed(orchestrate: ModuleType) -> None:
    """Guessing would write one target's typed state into another's slot."""
    run = _run(
        orchestrate,
        _controller(orchestrate, "cr-c2", lifecycle="c2"),
        _controller(orchestrate, "cr-c4", lifecycle="c4"),
    )
    with pytest.raises(SystemExit) as excinfo:
        run.review_controller()
    assert "--controller" in str(excinfo.value)


# --- 4. the declared concurrency ceiling is honoured -----------------------------------------


def test_ceiling_holds_back_surplus_controllers(orchestrate: ModuleType) -> None:
    run = _run(
        orchestrate,
        _controller(orchestrate, "cr-c2", lifecycle="c2"),
        _controller(orchestrate, "cr-c4", lifecycle="c4"),
        _controller(orchestrate, "cr-c6", lifecycle="c6"),
        ceiling=2,
    )
    assert [u.name for u in run.eligible()] == ["cr-c2", "cr-c4"]


def test_ceiling_counts_already_running_controllers(orchestrate: ModuleType) -> None:
    run = _run(
        orchestrate,
        _controller(orchestrate, "cr-c2", lifecycle="c2", status=orchestrate.RUNNING),
        _controller(orchestrate, "cr-c4", lifecycle="c4"),
        _controller(orchestrate, "cr-c6", lifecycle="c6"),
        ceiling=2,
    )
    assert [u.name for u in run.eligible()] == ["cr-c4"]


def test_no_ceiling_means_no_holdback(orchestrate: ModuleType) -> None:
    run = _run(
        orchestrate,
        _controller(orchestrate, "cr-c2", lifecycle="c2"),
        _controller(orchestrate, "cr-c4", lifecycle="c4"),
        _controller(orchestrate, "cr-c6", lifecycle="c6"),
    )
    assert len(run.eligible()) == 3


def test_ceiling_never_holds_back_non_controller_units(orchestrate: ModuleType) -> None:
    worker = orchestrate.Unit(
        name="w1", vendor="claude", task="/saga:work build", role="review-fixer"
    )
    run = _run(
        orchestrate,
        _controller(orchestrate, "cr-c2", lifecycle="c2", status=orchestrate.RUNNING),
        _controller(orchestrate, "cr-c4", lifecycle="c4"),
        worker,
        ceiling=1,
    )
    assert [u.name for u in run.eligible()] == ["w1"]


# --- 5. a code-review PATH segment is not an invocation ---------------------------------------


@pytest.mark.parametrize(
    "task",
    [
        "/saga:doc-review docs/code-review/2026-08-27-target.md",
        "/saga:work write the result to docs/code-review/out.md",
        "/saga:plan consult the docs/code-review directory",
        "see plugins/saga/code-review/references for the lens list",
        "read a/b/code-review.md first",
    ],
)
def test_a_code_review_path_segment_is_not_a_controller(orchestrate: ModuleType, task: str) -> None:
    """The misclassification that made the one-controller error unreadable.

    Three ordinary Document Review units were classified as Code Review controllers purely because
    their brief named the directory where committed typed results live, so an operator hitting the
    error could not tell a real second controller from a false positive.
    """
    assert orchestrate.is_code_review_task(task) is False
    unit = orchestrate.Unit(name="u", vendor="claude", task=task)
    assert orchestrate.is_review_controller(unit) is False


@pytest.mark.parametrize(
    "task",
    [
        "/saga:code-review review the frozen target",
        "$saga:code-review at revision 9c06fb4",
        "/code-review the diff",
        "First fetch, then /saga:code-review the run branch",
    ],
)
def test_real_invocations_still_classify(orchestrate: ModuleType, task: str) -> None:
    """Narrowing must not cost a genuine invocation in any supported spelling."""
    assert orchestrate.is_code_review_task(task) is True


def test_explicit_role_still_wins_over_task_text(orchestrate: ModuleType) -> None:
    """An explicit role is authoritative in both directions; text is only the legacy fallback."""
    pathy = orchestrate.Unit(
        name="cr",
        vendor="grok",
        task="/saga:doc-review docs/code-review/x.md",
        role="review-controller",
    )
    assert orchestrate.is_review_controller(pathy) is True

    worker = orchestrate.Unit(
        name="w", vendor="claude", task="/saga:code-review something", role="review-fixer"
    )
    assert orchestrate.is_review_controller(worker) is False
