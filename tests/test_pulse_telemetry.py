"""Tests for the `/pulse` live-telemetry surface (#400).

AC-to-test mapping (docs/plans/2026-07-13-400-pulse-live-telemetry-plan.md §5):

* AC1 — board state read through the REAL mission-control path: the board payload is seeded at
  the ``sdlc_manager._graphql`` seam and rendered by the real ``board_view`` grouping code,
  fed to Pulse through its injected runner. No fixture fallback: the item disappears from the
  render when the seeded payload omits it.
* AC2 — run state from real saga ticks (``saga.save`` envelope files, two lifecycle
  transitions) and ledger state from real appended, hash-chained facts.
* AC3 — Pulse writes nothing anywhere (byte-hash before/after) and owns no status field.
* AC4 — ``test_drives_real_run_and_surface_updates``: a real state-transition diff.
* AC5 — absent ledger / broken chain / unavailable board degrade EXPLICITLY, never as zeros.
* AC6 — no experiment-loop primitives in the snapshot schema.

All tests are offline and deterministic: injected runners, injected ``now``, tmp roots.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
SAGA_SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
MC_SCRIPTS = ROOT / "plugins" / "mission-control" / "scripts"

TICK_1 = datetime(2026, 7, 13, 10, 0, 0, tzinfo=UTC)
TICK_2 = datetime(2026, 7, 13, 11, 0, 0, tzinfo=UTC)


def _load(name: str, scripts_dir: Path) -> ModuleType:
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, scripts_dir / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pulse = _load("pulse", SAGA_SCRIPTS)
run_ledger = _load("run_ledger", SAGA_SCRIPTS)
saga = _load("saga", SAGA_SCRIPTS)
sdlc_manager = _load("sdlc_manager", MC_SCRIPTS)


def _no_git(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(returncode=1, stdout="", stderr="")


def _ledger(tmp_path: Path) -> Any:
    return run_ledger.RunLedger(path=tmp_path / "ledger" / "run-facts.jsonl")


def _spend_fact(tokens: int, cached: int, fresh: int, *, at: str, wall: float = 10.0) -> Any:
    return run_ledger.build_fact(
        "spend",
        subplot_id="leaf-400",
        at=at,
        tokens=tokens,
        tokens_cached=cached,
        tokens_fresh=fresh,
        wall_seconds=wall,
    )


def _save_tick(root: Path, *, phase: int, phase_status: str, now: datetime) -> None:
    s = saga.Saga(
        saga_id="issue-400",
        kind="issue",
        id="400",
        lifecycle_phase="work",
        phase=phase,
        phase_status=phase_status,
        next_step=f"phase-{phase} step",
    )
    saga.save(root, s, now=now, runner=_no_git)


def _snap(
    tmp_path: Path,
    ledger: Any,
    *,
    at: str = "2026-07-13T12:00:00+00:00",
    focus_saga: str | None = None,
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        pulse.build_snapshot(
            at=at,
            repo_root=tmp_path,
            projects=[],
            no_board=True,
            sdlc_manager_path=pulse.default_sdlc_manager(ROOT),
            ledger=ledger,
            max_sagas=10,
            focus_saga=focus_saga,
        ),
    )


# ===========================================================================
# AC1 — board state through the real mission-control read path
# ===========================================================================


def _seeded_item(number: int, title: str, status: str) -> dict[str, Any]:
    return {
        "createdAt": "2026-07-10T00:00:00Z",
        "fieldValues": {"nodes": [{"field": {"name": "Status"}, "name": status}]},
        "content": {
            "title": title,
            "number": number,
            "repository": {"name": "pulse-repo"},
            "labels": {"nodes": [{"name": "capability"}]},
        },
    }


def _board_runner_through_real_path(
    monkeypatch: pytest.MonkeyPatch, items: list[dict[str, Any]]
) -> Any:
    """An injected Pulse runner that executes the REAL sdlc_manager board_view JSON path
    in-process, seeded at the ``_graphql`` seam — no live GitHub, no fixture short-circuit."""
    monkeypatch.setattr(
        sdlc_manager,
        "load_config",
        lambda: {
            "project_mappings": {"projects": {"operations": {"number": 7, "name": "Operations"}}}
        },
    )
    monkeypatch.setattr(
        sdlc_manager,
        "_graphql",
        lambda _query, _variables=None: {
            "organization": {
                "projectV2": {
                    "id": "P7",
                    "items": {"nodes": items, "pageInfo": {"hasNextPage": False}},
                }
            }
        },
    )

    def runner(cmd: list[str], **_kwargs: Any) -> SimpleNamespace:
        assert "--project" in cmd and "json" in cmd, cmd
        project = cmd[cmd.index("--project") + 1]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sdlc_manager.board_view(project, None, "json")
        return SimpleNamespace(returncode=0, stdout=buf.getvalue(), stderr="")

    return runner


def test_board_state_renders_seeded_item_through_mission_control_read_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = _seeded_item(987, "Distinctive pulse board item", "Active")
    runner = _board_runner_through_real_path(monkeypatch, [item])
    board = pulse.read_board_state(
        ["operations"], sdlc_manager_path=pulse.default_sdlc_manager(ROOT), runner=runner
    )
    assert board["status"] == "ok"
    ops = board["projects"]["operations"]
    assert ops["columns"]["Active"]["count"] == 1
    assert ops["items"] == [
        {
            "repo": "pulse-repo",
            "number": 987,
            "title": "Distinctive pulse board item",
            "status": "Active",
            "created_at": "2026-07-10T00:00:00Z",
        }
    ]
    rendered = pulse.render(
        pulse.snapshot(
            at="t",
            board=board,
            runs={"status": "no-data", "total": 0, "sagas": [], "focus_ticks": None},
            ledger={"status": "no-data", "path": "x", "chain": {}},
            outcome_costs={"status": "no-data", "reason": "none"},
        )
    )
    assert "pulse-repo#987" in rendered
    assert "Distinctive pulse board item" in rendered


def test_board_item_absent_when_seed_omits_it_proves_no_fixture_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _board_runner_through_real_path(monkeypatch, [])
    board = pulse.read_board_state(
        ["operations"], sdlc_manager_path=pulse.default_sdlc_manager(ROOT), runner=runner
    )
    assert board["status"] == "ok"
    assert board["projects"]["operations"]["items"] == []
    assert "987" not in json.dumps(board)


def test_board_unavailable_labels_not_zero(tmp_path: Path) -> None:
    def failing_runner(_cmd: list[str], **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(returncode=1, stdout="", stderr="gh not authenticated")

    board = pulse.read_board_state(
        ["operations"],
        sdlc_manager_path=pulse.default_sdlc_manager(ROOT),
        runner=failing_runner,
    )
    assert board["status"] == "unavailable"
    assert "gh not authenticated" in board["reason"]
    assert board["projects"] == {}
    rendered = pulse.render(
        pulse.snapshot(
            at="t",
            board=board,
            runs={"status": "no-data", "total": 0, "sagas": [], "focus_ticks": None},
            ledger={"status": "no-data", "path": "x", "chain": {}},
            outcome_costs={"status": "no-data", "reason": "none"},
        )
    )
    assert "unavailable" in rendered
    assert "0 items" not in rendered  # unavailable is never presented as an empty board


def test_board_no_project_requested_is_no_data() -> None:
    board = pulse.read_board_state([], sdlc_manager_path=pulse.default_sdlc_manager(ROOT))
    assert board["status"] == "no-data"
    assert board["reason"] == "no project requested"


def test_board_missing_script_is_unavailable(tmp_path: Path) -> None:
    board = pulse.read_board_state(
        ["operations"], sdlc_manager_path=tmp_path / "nope" / "sdlc_manager.py"
    )
    assert board["status"] == "unavailable"
    assert "not found" in board["reason"]


# ===========================================================================
# AC2 — run state reflects real tick transitions; ledger reflects appended facts
# ===========================================================================


def test_run_state_reflects_each_tick_transition(tmp_path: Path) -> None:
    _save_tick(tmp_path, phase=1, phase_status="in_progress", now=TICK_1)
    first = pulse.read_run_state(tmp_path)
    assert first["status"] == "ok"
    assert first["sagas"][0]["saga_id"] == "issue-400"
    assert first["sagas"][0]["phase"] == 1
    assert first["sagas"][0]["phase_status"] == "in_progress"
    render_1 = pulse.render(_snap(tmp_path, _ledger(tmp_path)))
    assert "phase=1 status=in_progress" in render_1

    _save_tick(tmp_path, phase=2, phase_status="complete", now=TICK_2)
    second = pulse.read_run_state(tmp_path)
    assert second["sagas"][0]["phase"] == 2
    assert second["sagas"][0]["phase_status"] == "complete"
    render_2 = pulse.render(_snap(tmp_path, _ledger(tmp_path)))
    assert "phase=2 status=complete" in render_2
    assert render_1 != render_2  # the surface changed BECAUSE the underlying ticks changed


def test_focus_saga_renders_whole_tick_trajectory(tmp_path: Path) -> None:
    _save_tick(tmp_path, phase=1, phase_status="in_progress", now=TICK_1)
    _save_tick(tmp_path, phase=2, phase_status="complete", now=TICK_2)
    runs = pulse.read_run_state(tmp_path, focus_saga="issue-400")
    assert [t["phase"] for t in runs["focus_ticks"]] == [1, 2]
    rendered = pulse.render(_snap(tmp_path, _ledger(tmp_path), focus_saga="issue-400"))
    assert "focus trajectory (2 tick(s)" in rendered
    assert "tick 1:" in rendered and "tick 2:" in rendered


def test_ledger_panel_reflects_appended_facts(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    run_ledger.append_fact(
        ledger, _spend_fact(1200, 800, 400, at="2026-07-13T10:00:00+00:00", wall=30.0)
    )
    state = pulse.read_ledger_state(ledger)
    assert state["status"] == "ok"
    assert state["chain"]["ok"] is True
    assert state["fact_counts"]["spend"] == 1
    assert state["spend"]["tokens"]["sum"] == 1200.0
    assert state["reuse_ratio"] == pytest.approx(800 / 1200)
    assert state["last_fact_at"] == "2026-07-13T10:00:00+00:00"
    rendered = pulse.render(_snap(tmp_path, ledger))
    assert "1200 tokens" in rendered
    assert "reuse 0.67" in rendered
    assert "30 wall-s" in rendered


# ===========================================================================
# AC3 — derived-on-read: zero writes, no pulse-owned status field
# ===========================================================================


def _tree_digest(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_pulse_writes_nothing_anywhere(tmp_path: Path) -> None:
    _save_tick(tmp_path, phase=1, phase_status="in_progress", now=TICK_1)
    ledger = _ledger(tmp_path)
    run_ledger.append_fact(ledger, _spend_fact(100, 50, 50, at="2026-07-13T10:00:00+00:00"))
    before = _tree_digest(tmp_path)
    snap = _snap(tmp_path, ledger, focus_saga="issue-400")
    pulse.render(snap)
    json.dumps(snap)
    after = _tree_digest(tmp_path)
    assert before == after  # every byte under saga dir + ledger dir is untouched


def test_no_pulse_owned_status_field(tmp_path: Path) -> None:
    # The run panel projects EXACTLY fields the saga scanner already derives — no new field.
    _save_tick(tmp_path, phase=1, phase_status="in_progress", now=TICK_1)
    candidate_keys = set(saga.scan(tmp_path)[0].keys())
    assert set(pulse.RUN_FIELDS) <= candidate_keys
    # And the ledger schema is untouched: no pulse-owned fact kind.
    assert (
        frozenset({"spend", "cache", "engine", "delegation", "reconciliation"})
        == run_ledger.FACT_KINDS
    )


# ===========================================================================
# AC4 — end-to-end: drive a real run, observe the surface update
# ===========================================================================


def test_drives_real_run_and_surface_updates(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)

    # Tick 1 of a real disposable saga + the first real hash-chained spend fact.
    _save_tick(tmp_path, phase=1, phase_status="in_progress", now=TICK_1)
    run_ledger.append_fact(
        ledger, _spend_fact(1200, 800, 400, at="2026-07-13T10:00:00+00:00", wall=30.0)
    )
    snap_a = _snap(tmp_path, ledger, at="2026-07-13T10:01:00+00:00")
    render_a = pulse.render(snap_a)

    # Advance the run: a second lifecycle tick + a second appended fact.
    _save_tick(tmp_path, phase=2, phase_status="complete", now=TICK_2)
    run_ledger.append_fact(
        ledger, _spend_fact(300, 0, 300, at="2026-07-13T11:00:00+00:00", wall=12.0)
    )
    snap_b = _snap(tmp_path, ledger, at="2026-07-13T11:01:00+00:00")
    render_b = pulse.render(snap_b)

    # State-transition diff, not "renders without error":
    # 1. the run row advanced with the real tick transition,
    assert snap_a["runs"]["sagas"][0]["phase"] == 1
    assert snap_a["runs"]["sagas"][0]["phase_status"] == "in_progress"
    assert snap_b["runs"]["sagas"][0]["phase"] == 2
    assert snap_b["runs"]["sagas"][0]["phase_status"] == "complete"
    # 2. the ledger fact count and totals moved by exactly the appended amounts,
    assert snap_a["ledger"]["fact_counts"]["spend"] == 1
    assert snap_b["ledger"]["fact_counts"]["spend"] == 2
    assert snap_a["ledger"]["spend"]["tokens"]["sum"] == 1200.0
    assert snap_b["ledger"]["spend"]["tokens"]["sum"] == 1500.0
    assert snap_b["ledger"]["last_fact_at"] == "2026-07-13T11:00:00+00:00"
    # 3. and the rendered surface reflects both transitions.
    assert "phase=1 status=in_progress" in render_a
    assert "1200 tokens" in render_a
    assert "phase=2 status=complete" in render_b
    assert "1500 tokens" in render_b
    assert render_a != render_b


# ===========================================================================
# AC5 — explicit degrade: absent ledger, broken chain
# ===========================================================================


def test_absent_ledger_renders_no_data_yet(tmp_path: Path) -> None:
    ledger = run_ledger.RunLedger(path=tmp_path / "never-written.jsonl")
    state = pulse.read_ledger_state(ledger)
    assert state["status"] == "no-data"
    assert state["fact_counts"] is None  # no fabricated zero counts
    assert state["spend"] is None
    rendered = pulse.render(_snap(tmp_path, ledger))
    assert "no data yet" in rendered
    assert "0 tokens" not in rendered
    assert "chain ok" not in rendered


def test_broken_chain_renders_banner_not_aggregates(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    run_ledger.append_fact(ledger, _spend_fact(1200, 800, 400, at="2026-07-13T10:00:00+00:00"))
    run_ledger.append_fact(ledger, _spend_fact(300, 0, 300, at="2026-07-13T11:00:00+00:00"))
    # Tamper a value in the FIRST record in place — the chain must detect the silent bury.
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace('"tokens":1200', '"tokens":9999')
    ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    state = pulse.read_ledger_state(ledger)
    assert state["status"] == "chain-broken"
    assert state["chain"]["ok"] is False
    assert state["chain"]["break_index"] == 0
    assert state["fact_counts"] is None  # aggregates suppressed — no longer trustworthy
    assert state["spend"] is None
    rendered = pulse.render(_snap(tmp_path, ledger))
    assert "chain BROKEN" in rendered
    assert "suppressed" in rendered
    assert "9999" not in rendered  # the tampered number is never cited as an aggregate


# ===========================================================================
# AC6 — no experiment-loop primitives (continuous view, not /optimize)
# ===========================================================================


def _all_keys(obj: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(str(k))
            keys |= _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _all_keys(v)
    return keys


def test_snapshot_schema_has_no_experiment_keys(tmp_path: Path) -> None:
    _save_tick(tmp_path, phase=1, phase_status="in_progress", now=TICK_1)
    ledger = _ledger(tmp_path)
    run_ledger.append_fact(ledger, _spend_fact(100, 50, 50, at="2026-07-13T10:00:00+00:00"))
    snap = _snap(tmp_path, ledger, focus_saga="issue-400")
    assert snap["schema"] == "pulse_snapshot.v1"
    assert _all_keys(snap) & {"target", "baseline", "budget", "stop"} == set()


# ===========================================================================
# Outcome-costs panel honesty
# ===========================================================================


def test_outcome_costs_no_specs_is_no_data(tmp_path: Path) -> None:
    state = pulse.read_outcome_costs_state(tmp_path)
    assert state["status"] == "no-data"
    assert state["rollup"] is None


def test_outcome_costs_unreadable_spec_is_unavailable(tmp_path: Path) -> None:
    spec_dir = tmp_path / "docs" / "outcomes" / "broken-outcome"
    spec_dir.mkdir(parents=True)
    (spec_dir / "outcome-spec.json").write_text("{not json", encoding="utf-8")
    state = pulse.read_outcome_costs_state(tmp_path)
    assert state["status"] == "unavailable"
    assert "broken-outcome" in state["reason"]
    assert state["rollup"] is None


# ===========================================================================
# --watch (bounded loop) and --json (machine shape)
# ===========================================================================


def test_watch_renders_n_times_then_terminates(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    renders: list[str] = []
    sleeps: list[float] = []
    rc = pulse.watch(
        lambda: _snap(tmp_path, ledger),
        renders.append,
        interval=15.0,
        iterations=2,
        sleep=sleeps.append,
    )
    assert rc == 0
    assert len(renders) == 2
    assert sleeps == [15.0]  # sleeps BETWEEN renders only, then terminates


def test_main_json_emits_schema(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = pulse.main(
        [
            "--repo-root",
            str(tmp_path),
            "--no-board",
            "--json",
            "--ledger-path",
            str(tmp_path / "run-facts.jsonl"),
        ]
    )
    assert rc == 0
    snap = json.loads(capsys.readouterr().out)
    assert snap["schema"] == "pulse_snapshot.v1"
    assert snap["board"]["status"] == "no-data"
    assert snap["ledger"]["status"] == "no-data"
    assert snap["runs"]["status"] == "no-data"
    assert snap["outcome_costs"]["status"] == "no-data"


def test_main_watch_requires_iterations(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        pulse.main(["--repo-root", str(tmp_path), "--no-board", "--watch"])
