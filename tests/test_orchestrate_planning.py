"""Planning, routing, admission, and spend tests.

Each required scenario is its own test, named for the scenario, asserting the
decision the scenario names — not a weaker path that would stay green if the
control were deleted.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
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


def _child(row_id: str, work_shape: str, **fields: Any) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "row_id": row_id,
        "work_shape": work_shape,
        "task": row_id,
        "scope": "plugins/orchestrate/",
        "artifact_path": f"artifacts/{row_id}.json",
        "predicate": {"argv": ["true"], "timeout_seconds": 30.0, "max_output_bytes": 4096},
        "integration_mode": "none",
        "tokens_max": 20000,
    }
    spec.update(fields)
    return spec


def _session_snapshot(
    run_id: str,
    row_id: str,
    *,
    pane_id: str = "pane-a",
    status: str = "working",
    cwd: Path | None = None,
) -> dict[str, Any]:
    tab_id = f"tab-{row_id}"
    workspace_id = "workspace-a"
    location = str((cwd or ROOT).resolve())
    return {
        "tabs": [
            {
                "label": f"orchestrate-{run_id}-{row_id}",
                "tab_id": tab_id,
                "workspace_id": workspace_id,
                "agent_status": status,
            }
        ],
        "panes": [
            {
                "pane_id": pane_id,
                "tab_id": tab_id,
                "workspace_id": workspace_id,
                "cwd": location,
                "foreground_cwd": location,
                "agent_status": status,
                "revision": 1,
            }
        ],
        "agents": [
            {
                "pane_id": pane_id,
                "tab_id": tab_id,
                "workspace_id": workspace_id,
                "cwd": location,
                "foreground_cwd": location,
                "agent_status": status,
            }
        ],
    }


class SnapshotHerdr:
    def __init__(self, snapshot: dict[str, Any] | None = None, error: Exception | None = None):
        self.current = snapshot or {"tabs": [], "panes": [], "agents": []}
        self.error = error
        self.asks = 0

    def snapshot(self, *, cwd: Path) -> dict[str, Any]:
        self.asks += 1
        if self.error is not None:
            raise self.error
        return self.current


def _commit(
    tmp_path: Path,
    children: list[dict[str, Any]],
    *,
    run_id: str = "run-plan",
    per_vendor_limit: int | None = None,
    aggregate_limit: int | None = None,
    is_vendor_available: Any = None,
    now: float | None = None,
) -> Any:
    if per_vendor_limit is not None or aggregate_limit is not None:
        ADMISSION.write_host_policy(
            per_vendor=per_vendor_limit
            if per_vendor_limit is not None
            else ADMISSION.DEFAULT_PER_VENDOR,
            aggregate=aggregate_limit
            if aggregate_limit is not None
            else ADMISSION.DEFAULT_AGGREGATE,
        )
    built = PLANNING.plan(
        "deliver the outcome", children, run_id=run_id, is_vendor_available=is_vendor_available
    )
    PLANNING.issue_presentation_receipt(built)
    return PLANNING.commit_plan(built, tmp_path, now=now)


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
    routed = PLANNING.route("work-medium", is_vendor_available=available.__contains__)
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


def test_exceeding_a_per_vendor_bound_queues_while_aggregate_room_remains(tmp_path: Path) -> None:
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
    promoted = ADMISSION.release_slot(tmp_path, "first", run_id="run-plan")
    assert promoted is not None
    assert promoted.status == "reserved"
    assert promoted.row_id == "waiting"
    assert ADMISSION.queued_row_ids(tmp_path, run_id="run-plan") == ()
    rows = REGISTER.read_rows(tmp_path, run_id="run-plan")
    assert rows["waiting"]["admission"] == "reserved"


def test_gone_holder_slot_is_reclaimed_and_the_queue_advances(tmp_path: Path) -> None:
    _commit(
        tmp_path,
        [
            _child("dead", "work-medium", vendor="claude"),
            _child("waiting", "work-medium", vendor="claude"),
        ],
        per_vendor_limit=1,
        now=100.0,
    )
    ADMISSION.activate_slot(tmp_path, "dead", run_id="run-plan", now=100.0)
    herdr = SnapshotHerdr()
    reclaimed = ADMISSION.reclaim_dead_slots(
        tmp_path, run_id="run-plan", lease_seconds=10.0, now=120.0, herdr=herdr
    )
    assert reclaimed == ["dead"]
    assert ADMISSION.queued_row_ids(tmp_path, run_id="run-plan") == ()
    rows = REGISTER.read_rows(tmp_path, run_id="run-plan")
    assert rows["dead"]["admission"] == "reclaimed"
    assert rows["waiting"]["admission"] == "reserved"


def test_failed_owner_query_keeps_the_slot_and_queue_intact(tmp_path: Path) -> None:
    _commit(
        tmp_path,
        [
            _child("uncertain", "work-medium", vendor="claude"),
            _child("waiting", "work-medium", vendor="claude"),
        ],
        per_vendor_limit=1,
        now=100.0,
    )
    ADMISSION.activate_slot(tmp_path, "uncertain", run_id="run-plan", now=100.0)
    failed = SnapshotHerdr(error=ADMISSION.session_lifecycle.LaunchProtocolError("query failed"))
    with pytest.raises(ADMISSION.AdmissionError, match="could not ask"):
        ADMISSION.reclaim_dead_slots(
            tmp_path,
            run_id="run-plan",
            lease_seconds=10.0,
            now=120.0,
            herdr=failed,
        )
    assert ADMISSION.queued_row_ids(tmp_path, run_id="run-plan") == ("waiting",)
    rows = REGISTER.read_rows(tmp_path, run_id="run-plan")
    assert rows["uncertain"]["admission"] == "held"
    assert rows["waiting"]["admission"] == "queued"


def test_live_holder_with_a_pane_is_not_reclaimed(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("live", "work-medium", vendor="claude")], now=100.0)
    ADMISSION.activate_slot(tmp_path, "live", run_id="run-plan", now=100.0)
    herdr = SnapshotHerdr(_session_snapshot("run-plan", "live", pane_id="w1:p2", cwd=tmp_path))
    reclaimed = ADMISSION.reclaim_dead_slots(
        tmp_path, run_id="run-plan", lease_seconds=10.0, now=120.0, herdr=herdr
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

    def _occupancy_that_opens_the_race_window(claimed: Path | None = None) -> Any:
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
    assert not first.is_alive() and (not second.is_alive())
    assert sorted(results) == ["queued", "reserved"]
    per_vendor, aggregate = ADMISSION.occupancy(tmp_path)
    assert per_vendor["claude"] == 3
    assert aggregate == 3


def test_vendor_without_usage_consumes_its_declared_reservation(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("silent", "work-medium", vendor="muse")])
    reserved = ADMISSION.reserved_tokens_for("work-medium")
    row = REGISTER.read_rows(tmp_path, run_id="run-plan")["silent"]
    assert row["tokens_reserved"] == reserved
    assert row.get("tokens_observed") is None
    REGISTER.upsert_row(
        tmp_path, "silent", {"phase": "working"}, run_id="run-plan", writer="write_phase"
    )
    ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=reserved + 1, row_id="silent")
    with pytest.raises(ACCOUNTING.AccountingError, match="reached the captured cost"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=reserved, row_id="silent")


def test_reaching_the_spend_ceiling_halts_and_reports(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("metered", "work-medium", vendor="claude")])
    REGISTER.upsert_row(
        tmp_path, "metered", {"phase": "working"}, run_id="run-plan", writer="write_phase"
    )
    ACCOUNTING.record_observed_tokens(tmp_path, "metered", 1000, run_id="run-plan")
    with pytest.raises(ACCOUNTING.AccountingError, match="1000") as halted:
        ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=1000, row_id="metered")
    assert "HALT" in str(halted.value)
    ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=1001, row_id="metered")


def test_missing_telemetry_fails_closed_rather_than_passing(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("quiet", "work-medium", vendor="claude")])
    REGISTER.upsert_row(
        tmp_path, "quiet", {"phase": "working"}, run_id="run-plan", writer="write_phase"
    )
    with pytest.raises(ACCOUNTING.AccountingError, match="no tokens_observed") as closed:
        ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=1000000, row_id="quiet")
    assert "fail closed" in str(closed.value)


def test_usage_line_from_output_match_is_the_observed_column(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("metered", "work-medium", vendor="claude")])
    REGISTER.upsert_row(
        tmp_path, "metered", {"phase": "working"}, run_id="run-plan", writer="write_phase"
    )
    snapshot = _session_snapshot("run-plan", "metered", cwd=tmp_path)
    subscriber = SUBSCRIBER.Subscriber(
        root=tmp_path,
        run_id="run-plan",
        row_id="subscriber-a",
        pane_id="subscriber-pane",
        orchestrator_pane="orchestrator-pane",
        subscriptions=[SUBSCRIBER.usage_match_subscription("pane-a")],
        client=EVENTS.HerdrEventClient(tmp_path / "unused.sock"),
        snapshot_reader=lambda: snapshot,
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


def test_an_ordinary_token_line_leaves_the_subscriber_alive_and_the_spend_gate_refuses(
    tmp_path: Path,
) -> None:
    _commit(tmp_path, [_child("metered", "work-medium", vendor="claude")])
    REGISTER.upsert_row(
        tmp_path,
        "metered",
        {"phase": "working"},
        run_id="run-plan",
        writer="write_phase",
    )
    snapshot = _session_snapshot("run-plan", "metered", cwd=tmp_path)
    subscriber = SUBSCRIBER.Subscriber(
        root=tmp_path,
        run_id="run-plan",
        row_id="subscriber-a",
        pane_id="subscriber-pane",
        orchestrator_pane="orchestrator-pane",
        subscriptions=[SUBSCRIBER.usage_match_subscription("pane-a")],
        client=EVENTS.HerdrEventClient(tmp_path / "unused.sock"),
        snapshot_reader=lambda: snapshot,
        wake_sender=lambda _text: None,
        diagnostic_sink=lambda _payload: None,
    )
    good = {
        "event": "pane.output_matched",
        "data": {
            "pane_id": "pane-a",
            "matched_line": "tokens used: 321",
            "read": {"revision": 0, "text": "tokens used: 321\n"},
        },
    }
    noisy = {
        "event": "pane.output_matched",
        "data": {
            "pane_id": "pane-a",
            "matched_line": "warning: refresh token expired",
            "read": {"revision": 0, "text": "warning: refresh token expired\n"},
        },
    }
    subscriber.handle_event(EVENTS.decode_event(good))
    subscriber.handle_event(EVENTS.decode_event(noisy))
    subscriber.handle_event(EVENTS.decode_event(noisy))
    row = REGISTER.read_rows(tmp_path, run_id="run-plan")["metered"]
    assert row["tokens_observed"] == 321
    assert row[ACCOUNTING.USAGE_UNPARSEABLE_KEY] is True
    with pytest.raises(ACCOUNTING.AccountingError, match="unparseable"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=1_000_000, row_id="metered")
    with pytest.raises(ACCOUNTING.AccountingError, match="unparseable"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=1_000_000)


def test_a_writerless_agent_upsert_cannot_change_what_the_run_is_charged(
    tmp_path: Path,
) -> None:
    ADMISSION.reserve_slot(
        tmp_path,
        "c1",
        run_id="run-a",
        vendor="muse",
        work_shape="work-medium",
        tokens_max=8000,
    )
    REGISTER.write_phase(tmp_path, "c1", "working", run_id="run-a")
    with pytest.raises(ACCOUNTING.AccountingError, match="8000"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=1000)
    REGISTER.upsert_row(tmp_path, "c1", {"agent": "subscriber"}, run_id="run-a")
    assert REGISTER.read_rows(tmp_path, run_id="run-a")["c1"]["agent"] == "subscriber"
    with pytest.raises(ACCOUNTING.AccountingError, match="8000"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=1000)


def test_a_writerless_tokens_reserved_upsert_cannot_change_what_the_run_is_charged(
    tmp_path: Path,
) -> None:
    ADMISSION.reserve_slot(
        tmp_path,
        "c1",
        run_id="run-a",
        vendor="muse",
        work_shape="work-medium",
        tokens_max=8000,
    )
    REGISTER.write_phase(tmp_path, "c1", "working", run_id="run-a")
    with pytest.raises(ACCOUNTING.AccountingError, match="8000"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=1000)
    with pytest.raises(REGISTER.RegisterError, match="tokens_reserved"):
        REGISTER.upsert_row(tmp_path, "c1", {"tokens_reserved": 1}, run_id="run-a")
    assert REGISTER.read_rows(tmp_path, run_id="run-a")["c1"]["tokens_reserved"] == 8000
    with pytest.raises(ACCOUNTING.AccountingError, match="8000"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=1000)


def test_a_supervisory_row_is_not_charged_against_the_run(tmp_path: Path) -> None:
    ADMISSION.reserve_slot(
        tmp_path,
        "c1",
        run_id="run-a",
        vendor="muse",
        work_shape="work-medium",
        tokens_max=8000,
    )
    REGISTER.write_phase(tmp_path, "c1", "working", run_id="run-a")
    REGISTER.upsert_row(
        tmp_path,
        "subscriber-a",
        {"agent": "subscriber", "role": "subscriber"},
        run_id="run-a",
        writer=REGISTER.ROLE_WRITER,
    )
    REGISTER.write_phase(tmp_path, "subscriber-a", "working", run_id="run-a")
    assert ACCOUNTING.run_actual_tokens(tmp_path, run_id="run-a") == 8000.0
    assert REGISTER.is_supervisory_row(REGISTER.read_rows(tmp_path, run_id="run-a")["subscriber-a"])
    assert not REGISTER.is_supervisory_row(REGISTER.read_rows(tmp_path, run_id="run-a")["c1"])


def test_commit_refuses_until_the_operator_has_been_shown_the_plan(tmp_path: Path) -> None:
    built = PLANNING.plan("deliver the outcome", [_child("c1", "judgment")], run_id="run-plan")
    with pytest.raises(PLANNING.PlanningError, match="presentation receipt"):
        PLANNING.commit_plan(built, tmp_path)
    assert not REGISTER.register_path("run-plan").exists()
    _shown, text = PLANNING.present_plan(built)
    assert "c1" in text
    assert "claude" in text
    assert "scope:" in text
    assert "artifact_path:" in text
    assert "predicate:" in text
    assert "integration_mode:" in text
    PLANNING.issue_presentation_receipt(built)
    committed = PLANNING.commit_plan(built, tmp_path)
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
            "deliver the outcome", [_child("c1", "mechanical")], run_id="run-plan"
        )
        PLANNING.issue_presentation_receipt(built)
        PLANNING.commit_plan(built, tmp_path)
    finally:
        sys.modules.pop("session_lifecycle", None)
    assert launched == []
    row = REGISTER.read_rows(tmp_path, run_id="run-plan")["c1"]
    assert row["phase"] == "planned"
    assert row["admission"] == "reserved"


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
    assert second.status == "queued"
    per_vendor, aggregate = ADMISSION.occupancy(future_a)
    assert per_vendor["claude"] == 1
    assert aggregate == 1


def test_promoting_a_finished_child_does_not_rewrite_its_phase(tmp_path: Path) -> None:
    _commit(
        tmp_path,
        [
            _child("alive", "work-medium", vendor="claude"),
            _child("finished", "work-medium", vendor="claude"),
        ],
        per_vendor_limit=1,
    )
    REGISTER.upsert_row(
        tmp_path,
        "finished",
        {"phase": "reaped"},
        run_id="run-plan",
        writer="write_phase",
    )
    promoted = ADMISSION.release_slot(tmp_path, "alive", run_id="run-plan")
    finished = REGISTER.read_rows(tmp_path, run_id="run-plan")["finished"]
    assert finished["phase"] == "reaped"
    assert "finished" not in ADMISSION.queued_row_ids(tmp_path, run_id="run-plan")
    assert promoted is None or promoted.row_id != "finished"


def test_an_active_phase_without_a_reservation_is_not_occupancy(tmp_path: Path) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "escaped",
        {"agent": "claude", "vendor": "claude", "phase": "launching"},
        run_id="run-a",
        writer="write_phase",
    )
    per_vendor, aggregate = ADMISSION.occupancy(tmp_path)
    assert aggregate == 0
    assert per_vendor == {}
    assert ADMISSION.unreserved_active(tmp_path) == (("run-a", "escaped"),)


def test_admission_never_writes_phase_on_reserve(tmp_path: Path) -> None:
    ADMISSION.reserve_slot(
        tmp_path, "c1", run_id="run-a", vendor="claude", work_shape="work-medium", tokens_max=20000
    )
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["c1"]
    assert "phase" not in row
    assert row["admission"] == "reserved"


def test_activate_slot_holds_the_reservation_and_does_not_launch(tmp_path: Path) -> None:
    ADMISSION.reserve_slot(
        tmp_path, "c1", run_id="run-a", vendor="claude", work_shape="work-medium", tokens_max=20000
    )
    ADMISSION.activate_slot(tmp_path, "c1", run_id="run-a", now=50.0)
    doc = json.loads(REGISTER.register_path("run-a").read_text(encoding="utf-8"))
    reservation = doc["admission"]["reservations"]["c1"]
    assert reservation["state"] == "held"
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["c1"]
    assert "phase" not in row
    assert row["admission"] == "held"


def test_reserve_does_not_write_a_host_policy_file(tmp_path: Path) -> None:
    ADMISSION.reserve_slot(
        tmp_path,
        "a1",
        run_id="run-a",
        vendor="claude",
        work_shape="work-medium",
        tokens_max=20000,
        per_vendor_limit=1,
    )
    assert not ADMISSION.policy_path().exists()
    assert ADMISSION.host_policy() == ADMISSION.HostPolicy(
        ADMISSION.DEFAULT_PER_VENDOR, ADMISSION.DEFAULT_AGGREGATE
    )
    second = ADMISSION.reserve_slot(
        tmp_path, "b1", run_id="run-b", vendor="claude", work_shape="work-medium", tokens_max=20000
    )
    assert second.status == "reserved"


def test_explicit_host_policy_write_is_the_durable_rule(tmp_path: Path) -> None:
    ADMISSION.write_host_policy(per_vendor=1, aggregate=7)
    first = ADMISSION.reserve_slot(
        tmp_path, "a1", run_id="run-a", vendor="claude", work_shape="work-medium", tokens_max=20000
    )
    second = ADMISSION.reserve_slot(
        tmp_path, "b1", run_id="run-b", vendor="claude", work_shape="work-medium", tokens_max=20000
    )
    assert first.status == "reserved"
    assert second.status == "queued"
    assert ADMISSION.host_policy().per_vendor == 1


def test_reusing_a_row_id_for_a_different_vendor_is_refused(tmp_path: Path) -> None:
    first = ADMISSION.reserve_slot(
        tmp_path,
        "child",
        run_id="run-a",
        vendor="claude",
        work_shape="work-medium",
        tokens_max=20000,
    )
    assert first.status == "reserved"
    with pytest.raises(ADMISSION.AdmissionError, match="release and replan"):
        ADMISSION.reserve_slot(
            tmp_path,
            "child",
            run_id="run-a",
            vendor="codex",
            work_shape="work-medium",
            tokens_max=20000,
        )
    stored = json.loads(REGISTER.register_path("run-a").read_text(encoding="utf-8"))
    assert stored["admission"]["reservations"]["child"]["vendor"] == "claude"


def test_a_planned_reservation_is_not_reclaimed_by_the_lease_timer(tmp_path: Path) -> None:
    ADMISSION.reserve_slot(
        tmp_path,
        "planned-child",
        run_id="run-a",
        vendor="claude",
        work_shape="work-medium",
        tokens_max=20000,
        now=100.0,
    )
    reclaimed = ADMISSION.reclaim_dead_slots(
        tmp_path, run_id="run-a", lease_seconds=10.0, now=111.0
    )
    assert reclaimed == []
    per_vendor, _aggregate = ADMISSION.occupancy(tmp_path)
    assert per_vendor["claude"] == 1


def test_an_observed_exit_is_reclaimed_even_when_the_pane_id_remains(tmp_path: Path) -> None:
    ADMISSION.reserve_slot(
        tmp_path,
        "gone",
        run_id="run-a",
        vendor="claude",
        work_shape="work-medium",
        tokens_max=20000,
        now=100.0,
    )
    ADMISSION.activate_slot(tmp_path, "gone", run_id="run-a", now=100.0)
    REGISTER.write_phase(tmp_path, "gone", "working", run_id="run-a")
    herdr = SnapshotHerdr(
        _session_snapshot("run-a", "gone", pane_id="w1:p9", status="exited", cwd=tmp_path)
    )
    reclaimed = ADMISSION.reclaim_dead_slots(
        tmp_path, run_id="run-a", lease_seconds=10.0, now=1000.0, herdr=herdr
    )
    assert reclaimed == ["gone"]


def test_a_declared_lease_is_the_only_timer_on_a_reserved_child(tmp_path: Path) -> None:
    ADMISSION.reserve_slot(
        tmp_path,
        "leased",
        run_id="run-a",
        vendor="claude",
        work_shape="work-medium",
        tokens_max=20000,
        now=100.0,
        lease_until=110.0,
    )
    assert ADMISSION.reclaim_dead_slots(tmp_path, run_id="run-a", now=109.0) == []
    assert ADMISSION.reclaim_dead_slots(tmp_path, run_id="run-a", now=110.0) == ["leased"]


def test_plan_refuses_a_child_without_the_completion_contract() -> None:
    with pytest.raises(PLANNING.PlanningError, match="non-empty scope"):
        PLANNING.plan("outcome", [{"row_id": "c1", "work_shape": "judgment"}], run_id="run-a")


def test_silent_vendor_without_a_declared_maximum_is_refused() -> None:
    with pytest.raises(PLANNING.PlanningError, match="tokens_max"):
        PLANNING.plan(
            "outcome",
            [
                {
                    "row_id": "c1",
                    "work_shape": "work-medium",
                    "vendor": "muse",
                    "scope": "plugins/orchestrate/",
                    "artifact_path": "artifacts/c1.json",
                    "predicate": {
                        "argv": ["true"],
                        "timeout_seconds": 1.0,
                        "max_output_bytes": 128,
                    },
                    "integration_mode": "none",
                }
            ],
            run_id="run-a",
        )


def test_unaccounted_child_fails_the_run_spend_gate(tmp_path: Path) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "escaped",
        {"agent": "claude", "vendor": "claude", "phase": "working"},
        run_id="run-a",
        writer="write_phase",
    )
    with pytest.raises(ACCOUNTING.AccountingError, match="no tokens_observed"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=1000000)


def test_usage_parser_does_not_count_remaining_context_or_drop_input() -> None:
    assert ACCOUNTING.parse_usage_line("input 120 output 340 tokens") == 460
    assert ACCOUNTING.parse_usage_line("tokens used: 321") == 321
    assert ACCOUNTING.parse_usage_line("context left: 45000 tokens") is None
    assert ACCOUNTING.parse_usage_line("ETA 3 tokens/sec") is None


def test_redelivered_usage_line_is_not_counted_twice(tmp_path: Path) -> None:
    REGISTER.upsert_row(tmp_path, "metered", {"vendor": "claude"}, run_id="run-a")
    ACCOUNTING.apply_output_match(tmp_path, "metered", "tokens used: 321", run_id="run-a")
    ACCOUNTING.apply_output_match(tmp_path, "metered", "tokens used: 321", run_id="run-a")
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["metered"]
    assert row["tokens_observed"] == 321


def test_concurrent_observed_token_writes_sum_exactly(tmp_path: Path) -> None:
    """The generation lock is what makes add-to-observed atomic.

    Processes, not threads: the register lock is ``fcntl.flock`` on one open
    file description, which threads in one process share. Each worker adds a
    fixed amount once. The exact sum is the decision. A missing lock loses
    updates and the total comes in short.
    """
    REGISTER.upsert_row(tmp_path, "metered", {"vendor": "claude"}, run_id="run-a")
    workers = 20
    increment = 10
    script = f"import sys\nsys.path.insert(0, {str(SCRIPTS)!r})\nfrom pathlib import Path\nimport accounting\naccounting.record_observed_tokens(Path({str(tmp_path)!r}), 'metered', {increment}, run_id='run-a')\n"
    env = os.environ.copy()
    procs = [
        subprocess.Popen([sys.executable, "-c", script], env=env, cwd=str(ROOT))
        for _ in range(workers)
    ]
    assert [proc.wait() for proc in procs] == [0] * workers
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["metered"]
    assert row["tokens_observed"] == workers * increment


def _record_root(root: Path, run_id: str) -> None:
    path = REGISTER.register_dir() / f"{run_id}.root"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(root.resolve()), encoding="utf-8")
    path.chmod(384)


def test_commit_does_not_write_the_settled_artifact_column(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("child-a", "work-medium")])
    REGISTER.write_phase(tmp_path, "child-a", "launched", run_id="run-plan")
    snapshot = _session_snapshot("run-plan", "child-a", cwd=tmp_path)
    before = {
        record.row_id: record
        for record in SUBSCRIBER.catch_up(tmp_path, snapshot, run_id="run-plan")
    }
    row = REGISTER.read_rows(tmp_path, run_id="run-plan")["child-a"]
    assert "artifact_path" not in row
    assert row["declared_artifact_path"] == "artifacts/child-a.json"
    assert before["child-a"].artifact_exists is None
    artifact = tmp_path / "artifacts" / "child-a.json"
    artifact.parent.mkdir()
    artifact.write_text("{}", encoding="utf-8")
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"artifact_path": str(artifact)},
        run_id="run-plan",
        writer=REGISTER.ARTIFACT_PATH_WRITER,
    )
    after = {
        record.row_id: record
        for record in SUBSCRIBER.catch_up(tmp_path, snapshot, run_id="run-plan")
    }
    assert after["child-a"].artifact_exists is True


def test_a_terminal_row_cannot_be_replanned(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("c1", "work-medium", vendor="claude")])
    REGISTER.upsert_row(
        tmp_path, "c1", {"phase": "reaped"}, run_id="run-plan", writer="write_phase"
    )
    with pytest.raises(ADMISSION.AdmissionError, match="reaped"):
        _commit(tmp_path, [_child("c1", "work-medium", vendor="claude")])
    assert REGISTER.read_rows(tmp_path, run_id="run-plan")["c1"]["phase"] == "reaped"


def test_activate_slot_refuses_a_terminal_row(tmp_path: Path) -> None:
    ADMISSION.reserve_slot(
        tmp_path, "c1", run_id="run-a", vendor="claude", work_shape="work-medium", tokens_max=20000
    )
    REGISTER.upsert_row(tmp_path, "c1", {"phase": "reaped"}, run_id="run-a", writer="write_phase")
    with pytest.raises(ADMISSION.AdmissionError, match="reaped"):
        ADMISSION.activate_slot(tmp_path, "c1", run_id="run-a")


def test_snapshot_absence_does_not_free_an_unexpired_live_holder(tmp_path: Path) -> None:
    ADMISSION.reserve_slot(
        tmp_path,
        "live",
        run_id="run-a",
        vendor="claude",
        work_shape="work-medium",
        tokens_max=20000,
        now=100.0,
    )
    ADMISSION.activate_slot(tmp_path, "live", run_id="run-a", now=100.0)
    REGISTER.upsert_row(
        tmp_path,
        "live",
        {"phase": "working"},
        run_id="run-a",
        writer="write_phase",
    )
    records = SUBSCRIBER.catch_up(tmp_path, {"tabs": [], "panes": [], "agents": []}, run_id="run-a")
    assert records[0].observed_state == "exited"
    assert records[0].observed_state_source == "inferred:snapshot_absence"
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["live"]
    reclaimed = ADMISSION.reclaim_dead_slots(
        tmp_path,
        run_id="run-a",
        lease_seconds=3600.0,
        now=101.0,
        herdr=SnapshotHerdr(),
    )
    assert reclaimed == []
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)
    per_vendor, _aggregate = ADMISSION.occupancy(tmp_path)
    assert per_vendor["claude"] == 1


def test_silent_vendor_observed_value_cannot_lower_the_declared_maximum(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("silent", "work-medium", vendor="muse", tokens_max=20000)])
    REGISTER.upsert_row(
        tmp_path, "silent", {"phase": "working"}, run_id="run-plan", writer="write_phase"
    )
    ACCOUNTING.record_observed_tokens(tmp_path, "silent", 1, run_id="run-plan")
    row = REGISTER.read_rows(tmp_path, run_id="run-plan")["silent"]
    assert row["tokens_max"] == 20000
    assert row["tokens_observed"] == 1
    assert ACCOUNTING.run_actual_tokens(tmp_path, run_id="run-plan") == 20000.0


def test_commit_refuses_when_the_host_policy_has_drifted(tmp_path: Path) -> None:
    built = PLANNING.plan(
        "deliver the outcome",
        [_child("c1", "work-medium"), _child("c2", "work-medium")],
        run_id="run-plan",
    )
    PLANNING.issue_presentation_receipt(built)
    ADMISSION.write_host_policy(per_vendor=4, aggregate=7)
    with pytest.raises(PLANNING.PlanningError, match="host policy drifted"):
        PLANNING.commit_plan(built, tmp_path)


def test_retire_forgets_the_presentation_receipt(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("c1", "work-medium")])
    _record_root(tmp_path, "run-plan")
    receipt_path = PLANNING.presentation_receipt_path("run-plan")
    generation_path = REGISTER.generation_sidecar_path("run-plan")
    assert receipt_path.exists()
    assert generation_path.exists()
    REGISTER.retire_run(tmp_path, "run-plan")
    assert not receipt_path.exists()
    assert not generation_path.exists()
    rebuilt = PLANNING.plan("deliver the outcome", [_child("c1", "work-medium")], run_id="run-plan")
    with pytest.raises(PLANNING.PlanningError, match="presentation receipt"):
        PLANNING.commit_plan(rebuilt, tmp_path)


def test_queue_promotes_the_oldest_eligible_entry(tmp_path: Path) -> None:
    ADMISSION.write_host_policy(per_vendor=1, aggregate=7)
    _commit(
        tmp_path,
        [
            _child("older-held", "work-medium", vendor="claude"),
            _child("older-wait", "work-medium", vendor="claude"),
        ],
        run_id="run-z",
        now=10.0,
    )
    _commit(
        tmp_path, [_child("newer-wait", "work-medium", vendor="claude")], run_id="run-a", now=20.0
    )
    promoted = ADMISSION.release_slot(tmp_path, "older-held", run_id="run-z")
    assert promoted is not None
    assert promoted.row_id == "older-wait"


def test_replayed_usage_events_are_not_counted_twice(tmp_path: Path) -> None:
    REGISTER.upsert_row(tmp_path, "metered", {"vendor": "claude"}, run_id="run-a")
    ACCOUNTING.apply_output_match(tmp_path, "metered", "tokens used: 100", run_id="run-a")
    ACCOUNTING.apply_output_match(tmp_path, "metered", "tokens used: 200", run_id="run-a")
    ACCOUNTING.apply_output_match(tmp_path, "metered", "tokens used: 100", run_id="run-a")
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["metered"]
    assert row["tokens_observed"] == 200
    ACCOUNTING.apply_output_match(tmp_path, "metered", "input 100 output 0 tokens", run_id="run-a")
    ACCOUNTING.apply_output_match(tmp_path, "metered", "input 200 output 0 tokens", run_id="run-a")
    ACCOUNTING.apply_output_match(tmp_path, "metered", "input 100 output 0 tokens", run_id="run-a")
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["metered"]
    assert row["tokens_observed"] == 600


def test_a_planned_child_has_spent_zero(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("quiet", "work-medium", vendor="claude")])
    ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=1)
    assert ACCOUNTING.run_actual_tokens(tmp_path, run_id="run-plan") == 0.0


def test_a_planned_silent_vendor_has_spent_zero(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("quiet", "work-medium", vendor="muse")])
    ACCOUNTING.check_spend(tmp_path, run_id="run-plan", ceiling=1)
    assert ACCOUNTING.run_actual_tokens(tmp_path, run_id="run-plan") == 0.0


def test_a_phaseless_metered_row_fails_closed(tmp_path: Path) -> None:
    REGISTER.upsert_row(tmp_path, "metered", {"vendor": "claude"}, run_id="run-a")
    ACCOUNTING.record_observed_tokens(tmp_path, "metered", 200, run_id="run-a")
    with pytest.raises(ACCOUNTING.AccountingError, match="unknown phase"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=1)
    with pytest.raises(ACCOUNTING.AccountingError, match="unknown phase"):
        ACCOUNTING.run_actual_tokens(tmp_path, run_id="run-a")


def test_a_phaseless_silent_vendor_fails_closed(tmp_path: Path) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "silent",
        {"vendor": "muse", "tokens_max": 20000},
        run_id="run-a",
        writer=REGISTER.TOKENS_MAX_WRITER,
    )
    with pytest.raises(ACCOUNTING.AccountingError, match="unknown phase"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=1)


def test_child_contract_matches_the_launch_boundary() -> None:
    with pytest.raises(PLANNING.PlanningError, match="repository-relative"):
        PLANNING.plan("outcome", [_child("c1", "work-medium", scope="../outside")], run_id="run-a")
    with pytest.raises(PLANNING.PlanningError, match="repository-relative"):
        PLANNING.plan(
            "outcome",
            [_child("c1", "work-medium", artifact_path="../../outside.json")],
            run_id="run-a",
        )
    with pytest.raises(PLANNING.PlanningError, match="positive integer tokens_max"):
        PLANNING.plan("outcome", [_child("c1", "work-medium", tokens_max=1.9)], run_id="run-a")
    built = PLANNING.plan(
        "outcome", [_child("c1", "work-medium", scope=("src/", "tests/"))], run_id="run-a"
    )
    assert built.children[0].scope == ("src", "tests")


def test_host_policy_file_has_a_closed_schema(tmp_path: Path) -> None:
    path = ADMISSION.policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    with pytest.raises(ADMISSION.AdmissionError, match=str(path)):
        ADMISSION.read_host_policy()
    path.write_text('{"per_vendor": true, "aggregate": 3.9}', encoding="utf-8")
    with pytest.raises(ADMISSION.AdmissionError, match="positive integer"):
        ADMISSION.read_host_policy()
    path.unlink()
    assert ADMISSION.host_policy() == ADMISSION.HostPolicy(
        ADMISSION.DEFAULT_PER_VENDOR, ADMISSION.DEFAULT_AGGREGATE
    )


def test_admission_refuses_foreign_row_columns(tmp_path: Path) -> None:
    claimed = REGISTER.canonical_work_location(tmp_path)
    ADMISSION.reserve_slot(
        tmp_path, "c1", run_id="run-a", vendor="claude", work_shape="work-medium", tokens_max=20000
    )
    with ADMISSION.admission_locked(), REGISTER.generation_locked("run-a"):
        doc = REGISTER._read_register_unlocked("run-a")
        state = ADMISSION._admission_doc(doc)
        with pytest.raises(ADMISSION.AdmissionError, match="does not write"):
            ADMISSION._write_admission(
                claimed,
                "run-a",
                queue=state["queue"],
                reservations=state["reservations"],
                row_updates={"c1": {"observed_state": "exited", "phase": "planned"}},
            )


def test_a_reservation_names_its_occupant(tmp_path: Path) -> None:
    ADMISSION.reserve_slot(
        tmp_path, "c1", run_id="run-a", vendor="claude", work_shape="work-medium", tokens_max=20000
    )
    doc = json.loads(REGISTER.register_path("run-a").read_text(encoding="utf-8"))
    reservation = doc["admission"]["reservations"]["c1"]
    assert reservation["run_id"] == "run-a"
    assert reservation["row_id"] == "c1"
    assert reservation["vendor"] == "claude"
    assert reservation["work_location"]
    assert reservation["lease_until"] is None


def test_identical_delta_usage_lines_are_added(tmp_path: Path) -> None:
    REGISTER.upsert_row(tmp_path, "metered", {"vendor": "claude"}, run_id="run-a")
    ACCOUNTING.apply_output_match(tmp_path, "metered", "input 100 output 50 tokens", run_id="run-a")
    ACCOUNTING.apply_output_match(tmp_path, "metered", "input 100 output 50 tokens", run_id="run-a")
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["metered"]
    assert row["tokens_observed"] == 300


def test_an_unparseable_mark_survives_a_later_parseable_sample(tmp_path: Path) -> None:
    """A later valid delta is a different sample, not a recovery of the earlier line."""
    REGISTER.upsert_row(
        tmp_path,
        "metered",
        {"vendor": "claude", "phase": "working"},
        run_id="run-a",
        writer="write_phase",
    )
    ACCOUNTING.apply_output_match(tmp_path, "metered", "input 100 output 0 tokens", run_id="run-a")
    ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=500, row_id="metered")
    ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=500)
    ACCOUNTING.apply_output_match(
        tmp_path, "metered", "input 400 output 0 tokens; total: 900", run_id="run-a"
    )
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["metered"]
    assert row["tokens_observed"] == 100
    assert row[ACCOUNTING.USAGE_UNPARSEABLE_KEY] is True
    with pytest.raises(ACCOUNTING.AccountingError, match="unparseable"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=500, row_id="metered")
    with pytest.raises(ACCOUNTING.AccountingError, match="unparseable"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=500)
    ACCOUNTING.apply_output_match(tmp_path, "metered", "input 100 output 0 tokens", run_id="run-a")
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["metered"]
    assert row["tokens_observed"] == 200
    assert row[ACCOUNTING.USAGE_UNPARSEABLE_KEY] is True
    with pytest.raises(ACCOUNTING.AccountingError, match="unparseable"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=500, row_id="metered")
    with pytest.raises(ACCOUNTING.AccountingError, match="unparseable"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=500)
    with pytest.raises(REGISTER.RegisterError, match="usage_unparseable"):
        REGISTER.upsert_row(
            tmp_path, "metered", {ACCOUNTING.USAGE_UNPARSEABLE_KEY: False}, run_id="run-a"
        )
    with pytest.raises(ACCOUNTING.AccountingError, match="unparseable"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=500)


def test_an_ambiguous_usage_line_is_refused(tmp_path: Path) -> None:
    REGISTER.upsert_row(tmp_path, "metered", {"vendor": "claude"}, run_id="run-a")
    ACCOUNTING.apply_output_match(tmp_path, "metered", "tokens used: 100", run_id="run-a")
    with pytest.raises(ACCOUNTING.AccountingError, match="both the delta and cumulative"):
        ACCOUNTING.classify_usage_line("input 100 output 50 tokens; total tokens: 900")
    ACCOUNTING.apply_output_match(
        tmp_path,
        "metered",
        "input 100 output 50 tokens; total tokens: 900",
        run_id="run-a",
    )
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["metered"]
    assert row[ACCOUNTING.USAGE_UNPARSEABLE_KEY] is True
    with pytest.raises(ACCOUNTING.AccountingError, match="unparseable"):
        ACCOUNTING.check_spend(tmp_path, run_id="run-a", ceiling=1_000_000, row_id="metered")


def test_an_emptied_generation_sidecar_is_restored_from_the_register(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("c1", "work-medium")])
    sidecar = REGISTER.generation_sidecar_path("run-plan")
    stamped = sidecar.read_text(encoding="utf-8").strip()
    sidecar.write_text("", encoding="utf-8")
    rebuilt = PLANNING.plan("deliver the outcome", [_child("c1", "work-medium")], run_id="run-plan")
    receipt = PLANNING.issue_presentation_receipt(rebuilt)
    assert receipt.generation == stamped
    assert sidecar.read_text(encoding="utf-8").strip() == stamped
    second = PLANNING.commit_plan(rebuilt, tmp_path, receipt=receipt)
    assert second.children[0].admission == "reserved"
    assert second.children[0].admission_reason == "already reserved"
    doc = json.loads(REGISTER.register_path("run-plan").read_text(encoding="utf-8"))
    assert doc["generation"] == stamped


def test_a_deleted_generation_sidecar_is_restored_from_the_register(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("c1", "work-medium")])
    sidecar = REGISTER.generation_sidecar_path("run-plan")
    stamped = sidecar.read_text(encoding="utf-8").strip()
    sidecar.unlink()
    rebuilt = PLANNING.plan("deliver the outcome", [_child("c1", "work-medium")], run_id="run-plan")
    receipt = PLANNING.issue_presentation_receipt(rebuilt)
    assert receipt.generation == stamped
    second = PLANNING.commit_plan(rebuilt, tmp_path, receipt=receipt)
    assert second.children[0].admission == "reserved"
    assert second.children[0].admission_reason == "already reserved"


def test_an_unreadable_generation_sidecar_is_treated_as_absent(tmp_path: Path) -> None:
    _commit(tmp_path, [_child("c1", "work-medium")])
    sidecar = REGISTER.generation_sidecar_path("run-plan")
    stamped = sidecar.read_text(encoding="utf-8").strip()
    sidecar.write_bytes(b"\xff\xfe")
    rebuilt = PLANNING.plan("deliver the outcome", [_child("c1", "work-medium")], run_id="run-plan")
    receipt = PLANNING.issue_presentation_receipt(rebuilt)
    assert receipt.generation == stamped
    assert sidecar.read_text(encoding="utf-8").strip() == stamped


def test_retire_cannot_split_a_commit_from_its_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built = PLANNING.plan(
        "deliver the outcome",
        [_child("c1", "work-medium", vendor="claude")],
        run_id="run-plan",
    )
    PLANNING.issue_presentation_receipt(built)
    _record_root(tmp_path, "run-plan")
    reserved = threading.Event()
    real = ADMISSION._reserve_unlocked

    def _signal_after_reserve(*args: Any, **kwargs: Any) -> Any:
        result = real(*args, **kwargs)
        reserved.set()
        return result

    monkeypatch.setattr(ADMISSION, "_reserve_unlocked", _signal_after_reserve)
    results: dict[str, Any] = {}

    def _commit() -> None:
        results["plan"] = PLANNING.commit_plan(built, tmp_path)

    def _retire() -> None:
        reserved.wait(timeout=5)
        results["archive"] = REGISTER.retire_run(tmp_path, "run-plan")

    first = threading.Thread(target=_commit)
    second = threading.Thread(target=_retire)
    first.start()
    second.start()
    first.join(timeout=10)
    second.join(timeout=10)
    assert not first.is_alive() and not second.is_alive()
    assert results["plan"].children[0].admission == "reserved"
    live = REGISTER.register_path("run-plan")
    if live.exists():
        doc = json.loads(live.read_text(encoding="utf-8"))
    else:
        archive = results["archive"]
        assert archive is not None
        doc = json.loads(archive.read_text(encoding="utf-8"))
    assert "c1" in doc.get("admission", {}).get("reservations", {})
    assert doc["rows"]["c1"]["phase"] == "planned"
