"""Planning, routing, admission, and spend tests.

Each required scenario is its own test, named for the scenario, asserting the
decision the scenario names — not a weaker path that would stay green if the
control were deleted.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import subprocess
import sys
import threading
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "orchestrate" / "skills" / "orchestrate" / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REGISTER = _load("register")
ADMISSION = _load("admission")
ACCOUNTING = _load("accounting")
PLANNING = _load("planning")
EVENTS = _load("herdr_events")
SUBSCRIBER = _load("subscriber")


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REGISTER.REGISTER_DIR_ENV, str(tmp_path / "registers"))


def _child(
    row_id: str,
    work_shape: str,
    **fields: Any,
) -> dict[str, Any]:
    spec: dict[str, Any] = {"row_id": row_id, "work_shape": work_shape, "task": row_id}
    spec.update(fields)
    return spec


def _commit(
    tmp_path: Path,
    children: list[dict[str, Any]],
    *,
    run_id: str = "run-plan",
    per_vendor_limit: int = ADMISSION.DEFAULT_PER_VENDOR,
    aggregate_limit: int = ADMISSION.DEFAULT_AGGREGATE,
    is_vendor_available: Any = None,
    now: float | None = None,
) -> Any:
    built = PLANNING.plan(
        "deliver the outcome",
        children,
        run_id=run_id,
        is_vendor_available=is_vendor_available,
    )
    shown, _text = PLANNING.present_plan(built)
    return PLANNING.commit_plan(
        shown,
        tmp_path,
        per_vendor_limit=per_vendor_limit,
        aggregate_limit=aggregate_limit,
        now=now,
    )


# --------------------------------------------------------------------------- routing


def test_judgment_resolves_to_a_high_tier_and_mechanical_to_a_lower_tier() -> None:
    judgment = PLANNING.route("judgment", vendor="claude")
    mechanical = PLANNING.route("mechanical", vendor="claude")

    assert judgment.policy_effort == "high"
    assert judgment.effort == "high"
    assert judgment.execution_class == "review-high"
    assert mechanical.policy_effort == "medium"
    assert mechanical.effort == "medium"
    assert mechanical.execution_class == "work-medium"
    assert judgment.policy_model != mechanical.policy_model


def test_same_work_shape_resolves_to_different_models_for_different_runtimes() -> None:
    claude = PLANNING.route("review-high", vendor="claude")
    grok = PLANNING.route("review-high", vendor="grok")

    assert claude.model == "fable"
    assert grok.model == "grok-4.6"
    assert claude.model != grok.model
    assert claude.effort == grok.effort == "high"


def test_unavailable_preferred_vendor_falls_back_in_declared_order_and_records_it() -> None:
    available = {"qwen"}
    routed = PLANNING.route(
        "work-medium",
        is_vendor_available=available.__contains__,
    )

    assert routed.vendor == "qwen"
    assert routed.substitutions
    substitution = routed.substitutions[0]
    assert substitution["field"] == "vendor"
    assert substitution["from"] == PLANNING.DEFAULT_VENDOR_ORDER[0]
    assert substitution["to"] == "qwen"
    assert "unavailable" in substitution["reason"]
    assert PLANNING.DEFAULT_VENDOR_ORDER.index("qwen") > 0


def test_operator_vendor_override_is_recorded_as_explicit() -> None:
    routed = PLANNING.route("judgment", vendor="grok")

    assert routed.vendor == "grok"
    assert routed.override == {"kind": "explicit", "field": "vendor", "value": "grok"}
    assert routed.substitutions == ()


# --------------------------------------------------------------------------- admission


def test_exceeding_a_per_vendor_bound_queues_while_aggregate_room_remains(
    tmp_path: Path,
) -> None:
    committed = _commit(
        tmp_path,
        [
            _child("c1", "work-medium", vendor="claude"),
            _child("c2", "work-medium", vendor="claude"),
            _child("c3", "work-medium", vendor="codex"),
        ],
        per_vendor_limit=1,
        aggregate_limit=7,
    )

    by_id = {child.row_id: child for child in committed.children}
    assert by_id["c1"].admission == "reserved"
    assert by_id["c2"].admission == "queued"
    assert by_id["c3"].admission == "reserved"
    assert ADMISSION.queued_row_ids(tmp_path, run_id="run-plan") == ("c2",)
    rows = REGISTER.read_rows(tmp_path, run_id="run-plan")
    assert rows["c2"]["admission"] == "queued"
    assert rows["c2"]["tokens_reserved"] == ADMISSION.reserved_tokens_for("work-medium")


def test_slot_reservation_survives_restart(tmp_path: Path) -> None:
    _commit(
        tmp_path,
        [_child("held", "work-medium", vendor="claude")],
        per_vendor_limit=1,
        aggregate_limit=7,
    )
    on_disk = json.loads(REGISTER.register_path("run-plan").read_text(encoding="utf-8"))
    assert "held" in on_disk["admission"]["reservations"]

    # A new process image is a new import of the same file against the same
    # durable document. Occupancy must still see the reservation.
    reloaded = _load("admission")
    per_vendor, aggregate = reloaded.occupancy(tmp_path)
    assert per_vendor["claude"] == 1
    assert aggregate == 1

    second = reloaded.reserve_slot(
        tmp_path,
        "next",
        run_id="run-plan",
        vendor="claude",
        work_shape="work-medium",
        per_vendor_limit=1,
        aggregate_limit=7,
    )
    assert second.status == "queued"


def test_releasing_a_slot_advances_the_queue(tmp_path: Path) -> None:
    _commit(
        tmp_path,
        [
            _child("first", "work-medium", vendor="claude"),
            _child("waiting", "work-medium", vendor="claude"),
        ],
        per_vendor_limit=1,
        aggregate_limit=7,
    )
    assert ADMISSION.queued_row_ids(tmp_path, run_id="run-plan") == ("waiting",)

    promoted = ADMISSION.release_slot(
        tmp_path, "first", run_id="run-plan", per_vendor_limit=1, aggregate_limit=7
    )
    assert promoted is not None
    assert promoted.status == "reserved"
    assert promoted.row_id == "waiting"
    assert ADMISSION.queued_row_ids(tmp_path, run_id="run-plan") == ()
    rows = REGISTER.read_rows(tmp_path, run_id="run-plan")
    assert rows["waiting"]["admission"] == "reserved"


def test_dead_holder_slot_is_reclaimed_and_the_queue_advances(tmp_path: Path) -> None:
    _commit(
        tmp_path,
        [
            _child("dead", "work-medium", vendor="claude"),
            _child("waiting", "work-medium", vendor="claude"),
        ],
        per_vendor_limit=1,
        now=100.0,
    )
    reclaimed = ADMISSION.reclaim_dead_slots(
        tmp_path,
        run_id="run-plan",
        lease_seconds=10.0,
        now=120.0,
        per_vendor_limit=1,
    )
    assert reclaimed == ["dead"]
    assert ADMISSION.queued_row_ids(tmp_path, run_id="run-plan") == ()
    rows = REGISTER.read_rows(tmp_path, run_id="run-plan")
    assert rows["dead"]["admission"] == "reclaimed"
    assert rows["waiting"]["admission"] == "reserved"


def test_live_holder_with_a_pane_is_not_reclaimed(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("live", "work-medium", vendor="claude")], now=100.0)
    REGISTER.upsert_row(tmp_path, "live", {"pane_id": "w1:p2"}, run_id="run-plan")
    reclaimed = ADMISSION.reclaim_dead_slots(
        tmp_path, run_id="run-plan", lease_seconds=10.0, now=120.0
    )
    assert reclaimed == []
    per_vendor, _aggregate = ADMISSION.occupancy(tmp_path)
    assert per_vendor["claude"] == 1


def test_two_writers_cannot_both_take_the_last_vendor_slot(tmp_path: Path) -> None:
    _commit(
        tmp_path,
        [_child("seed", "work-medium", vendor="claude")],
        run_id="run-a",
        per_vendor_limit=2,
    )
    results: list[str] = []

    def _take(row_id: str) -> None:
        decision = ADMISSION.reserve_slot(
            tmp_path,
            row_id,
            run_id="run-a",
            vendor="claude",
            work_shape="work-medium",
            per_vendor_limit=2,
            aggregate_limit=7,
        )
        results.append(decision.status)

    first = threading.Thread(target=_take, args=("racer-1",))
    second = threading.Thread(target=_take, args=("racer-2",))
    first.start()
    second.start()
    first.join()
    second.join()
    assert sorted(results) == ["queued", "reserved"]


def test_two_runs_racing_for_the_last_vendor_slot_admit_exactly_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The host admission lock is what serializes two runs. The generation lock cannot.

    A start barrier plus a one-shot rendezvous after the occupancy read make a
    missing host lock a double-admit, not a lucky serial pass. With the lock,
    the second reader never arrives until the first write is durable, so the
    wait times out and the blocked run then sees a full vendor.
    """
    _commit(
        tmp_path,
        [
            _child("seed-1", "work-medium", vendor="claude"),
            _child("seed-2", "work-medium", vendor="claude"),
        ],
        run_id="run-seed",
        per_vendor_limit=3,
        aggregate_limit=7,
    )

    real_occupancy = ADMISSION._occupancy
    reads = 0
    reads_lock = threading.Lock()
    second_reader = threading.Event()

    def _occupancy_that_opens_the_race_window(claimed: Path) -> Any:
        nonlocal reads
        snapshot = real_occupancy(claimed)
        with reads_lock:
            reads += 1
            n = reads
        if n == 1:
            second_reader.wait(timeout=1.0)
        elif n == 2:
            second_reader.set()
        return snapshot

    monkeypatch.setattr(ADMISSION, "_occupancy", _occupancy_that_opens_the_race_window)

    results: list[str] = []
    start = threading.Barrier(2, timeout=5)

    def _take(run_id: str) -> None:
        start.wait()
        decision = ADMISSION.reserve_slot(
            tmp_path,
            "racer",
            run_id=run_id,
            vendor="claude",
            work_shape="work-medium",
            per_vendor_limit=3,
            aggregate_limit=7,
        )
        results.append(decision.status)

    first = threading.Thread(target=_take, args=("run-1",))
    second = threading.Thread(target=_take, args=("run-2",))
    first.start()
    second.start()
    first.join(timeout=10)
    second.join(timeout=10)
    assert not first.is_alive() and not second.is_alive()
    assert sorted(results) == ["queued", "reserved"]
    per_vendor, aggregate = ADMISSION.occupancy(tmp_path)
    assert per_vendor["claude"] == 3
    assert aggregate == 3


# --------------------------------------------------------------------------- spend


def test_vendor_without_usage_consumes_its_declared_reservation(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("silent", "work-medium", vendor="muse")])
    reserved = ADMISSION.reserved_tokens_for("work-medium")
    row = REGISTER.read_rows(tmp_path, run_id="run-plan")["silent"]
    assert row["tokens_reserved"] == reserved
    assert row.get("tokens_observed") is None

    ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=reserved + 1, row_id="silent")
    with pytest.raises(ACCOUNTING.AccountingError, match="reached the captured cost"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=reserved, row_id="silent")


def test_reaching_the_spend_ceiling_halts_and_reports(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("metered", "work-medium", vendor="claude")])
    ACCOUNTING.record_observed_tokens(tmp_path, "metered", 1000, run_id="run-plan")
    with pytest.raises(ACCOUNTING.AccountingError, match="1000") as halted:
        ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=1000, row_id="metered")
    assert "HALT" in str(halted.value)
    ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=1001, row_id="metered")


def test_missing_telemetry_fails_closed_rather_than_passing(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("quiet", "work-medium", vendor="claude")])
    with pytest.raises(ACCOUNTING.AccountingError, match="no tokens_observed") as closed:
        ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=1_000_000, row_id="quiet")
    assert "fail closed" in str(closed.value)


def test_usage_line_from_output_match_is_the_observed_column(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("metered", "work-medium", vendor="claude")])
    REGISTER.upsert_row(tmp_path, "metered", {"pane_id": "pane-a"}, run_id="run-plan")
    subscriber = SUBSCRIBER.Subscriber(
        root=tmp_path,
        run_id="run-plan",
        row_id="subscriber-a",
        pane_id="subscriber-pane",
        orchestrator_pane="orchestrator-pane",
        subscriptions=[SUBSCRIBER.usage_match_subscription("pane-a")],
        client=EVENTS.HerdrEventClient(tmp_path / "unused.sock"),
        snapshot_reader=lambda: {"panes": [], "agents": []},
        wake_sender=lambda _text: None,
        diagnostic_sink=lambda _payload: None,
    )
    subscriber.handle_event(
        EVENTS.decode_event(
            {
                "event": "pane.output_matched",
                "data": {
                    "pane_id": "pane-a",
                    "matched_line": "tokens used: 321",
                    "read": {"revision": 0, "text": "tokens used: 321\n"},
                },
            }
        )
    )
    row = REGISTER.read_rows(tmp_path, run_id="run-plan")["metered"]
    assert row["tokens_observed"] == 321


# --------------------------------------------------------------------------- planning never launches; operator sees the plan first


def test_commit_refuses_until_the_operator_has_been_shown_the_plan(
    tmp_path: Path,
) -> None:
    built = PLANNING.plan(
        "deliver the outcome",
        [_child("c1", "judgment")],
        run_id="run-plan",
    )
    with pytest.raises(PLANNING.PlanningError, match="has not been shown"):
        PLANNING.commit_plan(built, tmp_path)
    assert not REGISTER.register_path("run-plan").exists()

    shown, text = PLANNING.present_plan(built)
    assert "c1" in text
    assert "claude" in text
    committed = PLANNING.commit_plan(shown, tmp_path)
    assert committed.children[0].admission == "reserved"


def test_planning_never_launches_a_child(tmp_path: Path) -> None:
    source = inspect.getsource(PLANNING)
    assert "launch_child" not in source
    assert "session_lifecycle" not in source

    launched: list[str] = []

    def _record_launch(*_args: Any, **_kwargs: Any) -> None:
        launched.append("launched")

    fake = ModuleType("session_lifecycle")
    fake.launch_child = _record_launch  # type: ignore[attr-defined]
    sys.modules["session_lifecycle"] = fake
    try:
        built = PLANNING.plan(
            "deliver the outcome",
            [_child("c1", "mechanical")],
            run_id="run-plan",
        )
        shown, _text = PLANNING.present_plan(built)
        PLANNING.commit_plan(shown, tmp_path)
    finally:
        sys.modules.pop("session_lifecycle", None)
    assert launched == []
    row = REGISTER.read_rows(tmp_path, run_id="run-plan")["c1"]
    assert row["phase"] == "planned"
    assert row["admission"] == "reserved"


# --------------------------------------------------------------------------- git timeout and missing-sibling location


def test_canonical_work_location_passes_a_timeout_to_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[float | None] = []

    def _fake_run(*_args: Any, **kwargs: Any) -> Any:
        timeout = kwargs.get("timeout")
        seen.append(timeout)
        raise subprocess.TimeoutExpired(
            cmd=["git"], timeout=0.0 if timeout is None else float(timeout)
        )

    monkeypatch.setattr(REGISTER.subprocess, "run", _fake_run)
    intended = tmp_path / "missing" / "child"
    result = REGISTER.canonical_work_location(intended)
    assert seen == [REGISTER.GIT_LOCATION_TIMEOUT_SECONDS]
    assert result == intended.resolve()


def test_nonexistent_siblings_do_not_collapse_to_their_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    asked: list[str] = []

    def _not_a_repo(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        asked.append(argv[argv.index("-C") + 1])
        return subprocess.CompletedProcess(argv, 1, "", "not a git repository")

    monkeypatch.setattr(REGISTER.subprocess, "run", _not_a_repo)
    future_a = parent / "future-a"
    future_b = parent / "future-b"
    located_a = REGISTER.canonical_work_location(future_a)
    located_b = REGISTER.canonical_work_location(future_b)
    assert located_a == future_a.resolve()
    assert located_b == future_b.resolve()
    assert located_a != located_b
    assert Path(asked[0]) == parent.resolve()
    assert located_a != parent.resolve()


def test_reservation_at_one_missing_sibling_does_not_occupy_the_other(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()

    def _not_a_repo(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1, "", "not a git repository")

    monkeypatch.setattr(REGISTER.subprocess, "run", _not_a_repo)
    future_a = parent / "future-a"
    future_b = parent / "future-b"
    first = ADMISSION.reserve_slot(
        future_a,
        "a1",
        run_id="run-a",
        vendor="claude",
        work_shape="work-medium",
        per_vendor_limit=1,
    )
    second = ADMISSION.reserve_slot(
        future_b,
        "b1",
        run_id="run-b",
        vendor="claude",
        work_shape="work-medium",
        per_vendor_limit=1,
    )
    assert first.status == "reserved"
    assert second.status == "reserved"
    per_a, _agg_a = ADMISSION.occupancy(future_a)
    per_b, _agg_b = ADMISSION.occupancy(future_b)
    assert per_a["claude"] == 1
    assert per_b["claude"] == 1
