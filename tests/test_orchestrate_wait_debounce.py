"""Wait's debounce: idle must persist across consecutive observations before a unit has settled.

An agent is also idle *between* turns -- it finishes a tool call, returns to the prompt, thinks,
and continues. One idle event from herdr once returned ``wait`` in that gap; the session was still
working, with uncommitted paths in its worktree. ``settle`` already required two readings; ``wait``
did not.

The agreement rule is driven through the real wait helpers with a fake event source and a fake
``herdr agent wait`` -- the production module is loaded by path, the way the other orchestrate
tests do. Only herdr itself is canned.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

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
    spec = importlib.util.spec_from_file_location("_orchestrate_wait_debounce", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _unit(orchestrate: ModuleType, name: str = "alpha", pane_id: str = "p1") -> Any:
    return orchestrate.Unit(
        name=name,
        vendor="claude",
        task="x",
        pane_id=pane_id,
        agent_name=name,
        status=orchestrate.RUNNING,
    )


def _event(pane_id: str, status: str) -> SimpleNamespace:
    return SimpleNamespace(pane_id=pane_id, agent_status=status)


class PollQueue:
    """One canned status per call, failing loudly if wait looks more often than the test prepared."""

    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.calls = 0

    def __call__(self, _unit: Any) -> str:
        self.calls += 1
        assert self.answers, f"poll asked {self.calls} times -- more than the test queued"
        return self.answers.pop(0)


class TestEventPathRequiresAgreeingObservations:
    """A single idle from the socket is the think-pause, not a settlement."""

    def test_one_idle_does_not_return(self, orchestrate: ModuleType) -> None:
        unit = _unit(orchestrate)
        slept: list[float] = []
        poll = PollQueue(["working"])
        result = orchestrate.wait_on_events(
            {unit.pane_id: unit},
            iter([_event(unit.pane_id, "idle")]),
            interval=20,
            needed=2,
            poll_unit=poll,
            sleep=slept.append,
        )
        assert result is None
        assert slept == [20]
        assert poll.calls == 1

    def test_idle_then_working_does_not_return(self, orchestrate: ModuleType) -> None:
        unit = _unit(orchestrate)
        slept: list[float] = []
        result = orchestrate.wait_on_events(
            {unit.pane_id: unit},
            iter([_event(unit.pane_id, "idle"), _event(unit.pane_id, "working")]),
            interval=20,
            needed=2,
            poll_unit=PollQueue(["working"]),
            sleep=slept.append,
        )
        assert result is None
        assert slept == [20]

    def test_consecutive_agreeing_idles_do_return(self, orchestrate: ModuleType) -> None:
        unit = _unit(orchestrate)
        slept: list[float] = []
        result = orchestrate.wait_on_events(
            {unit.pane_id: unit},
            iter([_event(unit.pane_id, "idle")]),
            interval=20,
            needed=2,
            poll_unit=PollQueue(["idle"]),
            sleep=slept.append,
        )
        assert result is not None
        assert result[0] is unit
        assert result[1] == "idle"
        assert slept == [20]

    def test_blocked_returns_promptly_and_is_named(self, orchestrate: ModuleType) -> None:
        unit = _unit(orchestrate)
        slept: list[float] = []
        poll = PollQueue([])
        result = orchestrate.wait_on_events(
            {unit.pane_id: unit},
            iter([_event(unit.pane_id, "blocked")]),
            interval=20,
            needed=2,
            poll_unit=poll,
            sleep=slept.append,
        )
        assert result is not None
        assert result[1] == "blocked"
        assert slept == []
        assert poll.calls == 0


class TestFallbackPathRequiresAgreeingObservations:
    """The degraded path must not reintroduce the one-sample defect."""

    def test_one_idle_does_not_return(self, orchestrate: ModuleType) -> None:
        unit = _unit(orchestrate)
        poll = PollQueue(["working"])
        result = _run_fallback(
            orchestrate,
            unit,
            poll=poll,
            sleep=lambda _s: None,
            exits=[(11, 0)],
            pids=[11, 12],
        )
        assert result is None
        assert poll.calls >= 1

    def test_idle_then_working_does_not_return(self, orchestrate: ModuleType) -> None:
        unit = _unit(orchestrate)
        poll = PollQueue(["idle", "working"])
        result = _run_fallback(
            orchestrate,
            unit,
            poll=poll,
            sleep=lambda _s: None,
            exits=[(11, 0)],
            pids=[11, 12],
        )
        assert result is None
        assert poll.calls == 2

    def test_consecutive_agreeing_idles_do_return(self, orchestrate: ModuleType) -> None:
        unit = _unit(orchestrate)
        slept: list[float] = []
        poll = PollQueue(["idle", "idle"])
        result = _run_fallback(
            orchestrate,
            unit,
            poll=poll,
            sleep=slept.append,
            exits=[(11, 0)],
            pids=[11],
        )
        assert result is not None
        assert result[0] is unit
        assert result[1] == "idle"
        assert slept == [20]
        assert poll.calls == 2

    def test_blocked_returns_promptly_and_is_named(self, orchestrate: ModuleType) -> None:
        unit = _unit(orchestrate)
        slept: list[float] = []
        poll = PollQueue(["blocked"])
        result = _run_fallback(
            orchestrate,
            unit,
            poll=poll,
            sleep=slept.append,
            exits=[(11, 0)],
            pids=[11],
        )
        assert result is not None
        assert result[1] == "blocked"
        assert slept == []


class TestOnceKeepsTheSingleSample:
    """``--once`` is settle's vocabulary, kept for a caller that wants the old behaviour."""

    def test_one_idle_event_returns(self, orchestrate: ModuleType) -> None:
        unit = _unit(orchestrate)
        slept: list[float] = []
        poll = PollQueue([])
        result = orchestrate.wait_on_events(
            {unit.pane_id: unit},
            iter([_event(unit.pane_id, "idle")]),
            interval=20,
            needed=1,
            poll_unit=poll,
            sleep=slept.append,
        )
        assert result is not None
        assert result[1] == "idle"
        assert slept == []
        assert poll.calls == 0


def _run_fallback(
    orchestrate: ModuleType,
    unit: Any,
    *,
    poll: PollQueue,
    sleep: Any,
    exits: list[tuple[int, int]],
    pids: list[int],
) -> tuple[Any, str] | None:
    remaining_exits = list(exits)
    remaining_pids = list(pids)

    class Proc:
        def __init__(self, pid: int) -> None:
            self.pid = pid

    def fake_popen(_unit: Any, _timeout: int) -> Proc:
        assert remaining_pids, "wait restarted more times than the test prepared pids"
        return Proc(remaining_pids.pop(0))

    def fake_wait() -> tuple[int, int]:
        if not remaining_exits:
            raise ChildProcessError
        return remaining_exits.pop(0)

    killed: list[int] = []
    return cast(
        "tuple[Any, str] | None",
        orchestrate.wait_on_agent_waits(
            [unit],
            timeout=30,
            interval=20,
            needed=2,
            poll_unit=poll,
            sleep=sleep,
            popen=fake_popen,
            wait_pid=fake_wait,
            kill_pid=lambda pid, _sig: killed.append(pid),
        ),
    )
