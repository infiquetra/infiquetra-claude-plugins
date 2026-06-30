"""Unit tests for the pure saga-spore core (U1, issue #281).

Covers the offline-testable heart of the PreCompact->SessionStart spore: serialization under the R5
byte budget (frontier never dropped), the on-disk dump/load seam with the R9 mismatch guard, active-saga
resolution against a really-written saga, deadline-bounded outcome discovery (KTD4), and the DAG freeze.
The real cross-process, real-git end-to-end seam is U5 (tests/test_spore_seam_roundtrip.py)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "plugins" / "saga" / "scripts"
SCRIPT = SCRIPTS / "saga_spore.py"


def _load() -> ModuleType:
    # saga_spore imports its siblings outcome / outcome_store / saga; make scripts dir importable first.
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("saga_spore", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["saga_spore"] = module
    spec.loader.exec_module(module)
    return module


M = _load()

_NOW = "2026-06-30T20:00:00+00:00"


def _saga_box(**over: Any) -> dict[str, Any]:
    box = {
        "saga_id": "issue-281",
        "lifecycle_phase": "work",
        "phase_status": "in_progress",
        "status": "active",
        "next_step": "U2: build the PreCompact hook",
    }
    box.update(over)
    return box


def _spore(
    *, dag: dict[str, Any] | None, box: dict[str, Any] | None = None, **prov: Any
) -> dict[str, Any]:
    provenance = {
        "schema": M.SCHEMA,
        "generated_at": _NOW,
        "session_id": "sess-abc",
        "repo_root": "/repo",
        "saga_id": (box or {}).get("saga_id", "issue-281") if box is not None else "issue-281",
        "spec_revision": dag.get("spec_revision") if dag else None,
        "source_tick": ".claude/saga/sagas/issue-281/20260630-200000.md",
    }
    provenance.update(prov)
    pointers: dict[str, Any] = {"plan_path": "docs/plans/p.md", "issue_ref": "o/r#281"}
    if dag:
        pointers["outcome_id"] = dag["outcome_id"]
    return {
        "provenance": provenance,
        "saga_box": _saga_box() if box is None else box,
        "dag": dag,
        "pointers": pointers,
    }


def _dag(*, frontier: list[str], leaves: dict[str, dict[str, Any]], rev: int = 4) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for info in leaves.values():
        counts[info["state"]] = counts.get(info["state"], 0) + 1
    return {
        "outcome_id": "ship-auth",
        "objective": "ship auth",
        "spec_revision": rev,
        "counts": counts,
        "frontier": frontier,
        "complete": False,
        "leaves": leaves,
    }


# --------------------------------------------------------------------------- serialize (R5/R10)


def test_serialize_single_saga_leads_with_authority_and_facts() -> None:
    block = M.serialize(_spore(dag=None))
    assert block.startswith("=== SAGA SPORE")
    assert "AUTHORITY:" in block and "authoritative" in block.lower()
    assert "issue-281" in block
    assert "U2: build the PreCompact hook" in block  # next_step carried
    assert "OUTCOME DAG" not in block  # single-saga: no DAG section
    assert len(block) <= M.SPORE_BUDGET_CHARS


def test_serialize_campaign_inlines_ready_frontier_and_leaves() -> None:
    dag = _dag(
        frontier=["U9", "U10"],
        leaves={
            "U8": {"state": "done", "gated": False, "last_completion_event_ref": "attempt:1:done"},
            "U9": {"state": "ready", "gated": True, "last_completion_event_ref": None},
            "U10": {"state": "ready", "gated": False, "last_completion_event_ref": None},
            "U11": {"state": "blocked", "gated": False, "last_completion_event_ref": None},
        },
    )
    block = M.serialize(_spore(dag=dag))
    assert "OUTCOME DAG" in block
    assert "READY FRONTIER (act on these): U9, U10" in block
    assert "U9: ready [gated]" in block  # per-leaf state + gated flag
    assert "U8: done" in block
    assert "counts:" in block and "done=1" in block


def test_serialize_over_budget_keeps_full_frontier_drops_detail_with_counted_pointer() -> None:
    # 5 ready (the resumable core) + 400 done leaves: well over the 9k budget.
    leaves: dict[str, dict[str, Any]] = {}
    frontier = []
    for i in range(5):
        sid = f"R{i:03d}"
        leaves[sid] = {"state": "ready", "gated": False, "last_completion_event_ref": None}
        frontier.append(sid)
    for i in range(400):
        leaves[f"D{i:03d}"] = {
            "state": "done",
            "gated": False,
            "last_completion_event_ref": "attempt:1:done",
        }
    block = M.serialize(_spore(dag=_dag(frontier=frontier, leaves=leaves)))
    assert len(block) <= M.SPORE_BUDGET_CHARS  # budget respected
    # every ready/frontier leaf survives, both in the frontier line and as a detail line
    for sid in frontier:
        assert sid in block
        assert f"{sid}: ready" in block
    assert "more leaves — see" in block  # counted-drop pointer, never silent
    assert "=== END SPORE ===" in block


def test_serialize_core_over_budget_emits_full_frontier_and_logs_spill() -> None:
    # A frontier so wide the resumable CORE alone exceeds budget (F3 degenerate case).
    frontier = [f"leaf-{i:04d}" for i in range(1200)]
    leaves = {
        sid: {"state": "ready", "gated": False, "last_completion_event_ref": None}
        for sid in frontier
    }
    block = M.serialize(_spore(dag=_dag(frontier=frontier, leaves=leaves)))
    # The frontier is NEVER sacrificed — every id is present even though we blow the budget.
    assert frontier[0] in block and frontier[-1] in block
    assert "spore note" in block and "exceeds" in block  # spill logged in-band, not silent


def test_serialize_no_active_saga_states_it() -> None:
    block = M.serialize(_spore(dag=None, box={}, saga_id=None))
    assert "ACTIVE SAGA: (none resolved" in block


# --------------------------------------------------------------------------- dump / load_and_validate


def test_dump_load_roundtrip_returns_the_block() -> None:
    spore = _spore(
        dag=_dag(
            frontier=["U9"],
            leaves={"U9": {"state": "ready", "gated": False, "last_completion_event_ref": None}},
        )
    )
    text = M.dump(spore)
    block = M.load_and_validate(text, "sess-abc", "/repo")
    assert block == M.serialize(spore)
    assert "READY FRONTIER (act on these): U9" in block


@pytest.mark.parametrize(
    "session_id,repo_root",
    [("WRONG", "/repo"), ("sess-abc", "/other-repo")],
)
def test_load_and_validate_skips_on_mismatch(session_id: str, repo_root: str) -> None:
    text = M.dump(_spore(dag=None))
    assert M.load_and_validate(text, session_id, repo_root) is None


def test_load_and_validate_rejects_malformed_or_incomplete() -> None:
    assert M.load_and_validate("{not json", "sess-abc", "/repo") is None
    assert M.load_and_validate(json.dumps({"schema": "other"}), "sess-abc", "/repo") is None
    # missing saga_id -> skip (R9 content guard)
    bad = json.dumps(
        {
            "schema": M.SCHEMA,
            "session_id": "sess-abc",
            "repo_root": "/repo",
            "saga_id": "",
            "block": "x",
        }
    )
    assert M.load_and_validate(bad, "sess-abc", "/repo") is None
    # empty block -> skip
    noblock = json.dumps(
        {
            "schema": M.SCHEMA,
            "session_id": "sess-abc",
            "repo_root": "/repo",
            "saga_id": "s",
            "block": "",
        }
    )
    assert M.load_and_validate(noblock, "sess-abc", "/repo") is None


# --------------------------------------------------------------------------- spore_path


def test_spore_path_rejects_traversal() -> None:
    assert M.spore_path(Path("/c"), "sess-1") == Path("/c/saga-spores/sess-1.json")
    with pytest.raises(M.outcome_store.OutcomeStoreError):
        M.spore_path(Path("/c"), "a/b")


# --------------------------------------------------------------------------- resolve_active_saga (real)


def _fake_git_runner(*_a: Any, **_k: Any) -> SimpleNamespace:
    return SimpleNamespace(returncode=1, stdout="", stderr="")


def test_resolve_active_saga_reads_real_saga(tmp_path: Path) -> None:
    saga = M.saga
    obj = saga.Saga(
        saga_id="issue-9",
        kind="issue",
        id="9",
        lifecycle_phase="work",
        phase_status="in_progress",
        status="active",
        next_step="do the thing",
        plan_path="docs/plans/x.md",
        issue_ref="o/r#9",
        blockers="waiting on review",
        open_questions=["which model?"],
        checks_run=["pytest"],
    )
    saga.save(tmp_path, obj, runner=_fake_git_runner)

    box = M.resolve_active_saga(tmp_path)
    assert box is not None
    assert box["saga_id"] == "issue-9"
    assert box["lifecycle_phase"] == "work"
    assert box["phase_status"] == "in_progress"
    assert box["status"] == "active"
    assert box["next_step"] == "do the thing"
    assert box["blockers"] == "waiting on review"
    assert box["open_questions"] == ["which model?"]
    assert "checks_run" not in box  # C1: never carried
    assert box["_pointers"]["plan_path"] == "docs/plans/x.md"
    assert box["_pointers"]["issue_ref"] == "o/r#9"


def test_resolve_active_saga_absent_or_malformed(tmp_path: Path) -> None:
    assert M.resolve_active_saga(tmp_path) is None  # no state.json
    state = tmp_path / ".claude" / "saga" / "state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("{not json", encoding="utf-8")
    assert M.resolve_active_saga(tmp_path) is None


# --------------------------------------------------------------------------- resolve_outcome_id (KTD4)


def _make_outcomes(common: Path, *ids: str) -> None:
    for oid in ids:
        (common / "saga-outcomes" / oid).mkdir(parents=True, exist_ok=True)


def test_resolve_outcome_id_leaf_fast_path_handles_hyphens(tmp_path: Path) -> None:
    _make_outcomes(tmp_path, "ship-auth", "ship")
    # leaf-<outcome_id>-<subplot_id>; both halves hyphenated -> longest existing-dir prefix wins.
    assert M.resolve_outcome_id("leaf-ship-auth-U3", tmp_path, repo_root=tmp_path) == "ship-auth"
    # a leaf for the shorter outcome resolves to it, not the longer one.
    assert M.resolve_outcome_id("leaf-ship-U1", tmp_path, repo_root=tmp_path) == "ship"


def test_resolve_outcome_id_empty_dir_is_none(tmp_path: Path) -> None:
    assert M.resolve_outcome_id("issue-281", tmp_path, repo_root=tmp_path) is None


def test_resolve_outcome_id_single_noncomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_outcomes(tmp_path, "done-one", "live-one")
    monkeypatch.setattr(M, "_outcome_is_complete", lambda _r, oid: oid == "done-one")
    assert M.resolve_outcome_id("issue-281", tmp_path, repo_root=tmp_path) == "live-one"


def test_resolve_outcome_id_ambiguous_two_noncomplete_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_outcomes(tmp_path, "live-a", "live-b")
    monkeypatch.setattr(M, "_outcome_is_complete", lambda _r, _o: False)  # both non-complete
    assert M.resolve_outcome_id("issue-281", tmp_path, repo_root=tmp_path) is None


# --------------------------------------------------------------------------- build_spore (assembly)


def test_build_spore_assembles_provenance_dag_and_pointers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        M,
        "resolve_active_saga",
        lambda _r: {
            **_saga_box(),
            "_pointers": {"plan_path": "p.md", "issue_ref": "o/r#281", "work_session_paths": []},
        },
    )
    monkeypatch.setattr(M.outcome_store, "resolve_common_dir", lambda _r: tmp_path / ".git")
    monkeypatch.setattr(M, "resolve_outcome_id", lambda *_a, **_k: "ship-auth")
    monkeypatch.setattr(
        M,
        "freeze_dag",
        lambda _r, _oid: _dag(
            frontier=["U9"],
            leaves={"U9": {"state": "ready", "gated": False, "last_completion_event_ref": None}},
        ),
    )
    monkeypatch.setattr(
        M.saga,
        "latest_envelope_for",
        lambda _r, _sid: tmp_path / ".claude/saga/sagas/issue-281/t.md",
    )

    spore = M.build_spore(tmp_path, "sess-1", now=_NOW)
    assert spore["provenance"]["session_id"] == "sess-1"
    assert spore["provenance"]["saga_id"] == "issue-281"
    assert spore["provenance"]["spec_revision"] == 4
    assert spore["dag"]["outcome_id"] == "ship-auth"
    assert spore["pointers"]["outcome_id"] == "ship-auth"
    assert "_pointers" not in spore["saga_box"]  # split out of the box
    assert "READY FRONTIER" in M.serialize(spore)  # assembled spore renders cleanly


def test_build_spore_single_saga_no_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        M,
        "resolve_active_saga",
        lambda _r: {
            **_saga_box(),
            "_pointers": {"plan_path": "", "issue_ref": "", "work_session_paths": []},
        },
    )
    monkeypatch.setattr(M.outcome_store, "resolve_common_dir", lambda _r: tmp_path / ".git")
    monkeypatch.setattr(M, "resolve_outcome_id", lambda *_a, **_k: None)
    monkeypatch.setattr(M.saga, "latest_envelope_for", lambda _r, _sid: None)

    spore = M.build_spore(tmp_path, "sess-2", now=_NOW)
    assert spore["dag"] is None
    assert spore["provenance"]["spec_revision"] is None
    assert spore["provenance"]["source_tick"] == ""


# --------------------------------------------------------------------------- freeze_dag (KTD3)


def test_freeze_dag_assembles_from_status(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = SimpleNamespace(
        nodes=[
            SimpleNamespace(subplot_id="U8", gated=True),
            SimpleNamespace(subplot_id="U9", gated=False),
        ]
    )
    status = {
        "outcome_id": "ship-auth",
        "objective": "ship auth",
        "spec_revision": 7,
        "states": {"U8": "ready", "U9": "done"},
        "counts": {"ready": 1, "done": 1},
        "frontier": ["U8"],
        "complete": False,
    }
    monkeypatch.setattr(M.outcome, "load_spec", lambda *_a, **_k: spec)
    monkeypatch.setattr(M.outcome, "_store", lambda *_a, **_k: object())
    monkeypatch.setattr(M.outcome, "status", lambda *_a, **_k: status)
    monkeypatch.setattr(
        M.outcome_store,
        "read_completion_events",
        lambda _store, sid: [SimpleNamespace(attempt=1, state="done")] if sid == "U9" else [],
    )
    dag = M.freeze_dag(Path("/repo"), "ship-auth")
    assert dag is not None
    assert dag["frontier"] == ["U8"]
    assert dag["leaves"]["U8"] == {
        "state": "ready",
        "gated": True,
        "last_completion_event_ref": None,
    }
    assert dag["leaves"]["U9"]["state"] == "done"
    assert dag["leaves"]["U9"]["last_completion_event_ref"] == "attempt:1:done"
    assert dag["counts"] == {"ready": 1, "done": 1}


def test_freeze_dag_none_outcome_and_corrupt_status(monkeypatch: pytest.MonkeyPatch) -> None:
    assert M.freeze_dag(Path("/repo"), None) is None

    def _boom(*_a: Any, **_k: Any) -> Any:
        raise ValueError("corrupt spec")

    monkeypatch.setattr(M.outcome, "load_spec", _boom)
    assert M.freeze_dag(Path("/repo"), "ship-auth") is None
