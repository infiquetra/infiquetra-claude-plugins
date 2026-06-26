"""Tests for the mission-control secondary portfolio projection (U8 — R25).

Pins R25 (the projection is GENERATED from the spec + store, never hand-authored; it is a SECONDARY
view that never auto-closes the parent) and R17 (derived-on-read — every field computed, no
operator-writable status).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
ORCH = _load("outcome_orchestrator")
_load("outcome_dispatcher")
_load("outcome_merge")
_load("outcome_worktrees")
_load("outcome_decompose")
ENG = _load("outcome")
_load("outcome_report")
PROJ = _load("outcome_projection")


def _store(tmp_path: Path) -> Any:
    return STORE.Store(root=tmp_path / "store").ensure()


def _spec(nodes: list[dict[str, Any]]) -> Any:
    return SPEC.OutcomeSpec.from_dict({"outcome_id": "o", "objective": "Ship it", "nodes": nodes})


def _done(store: Any, sid: str, state: str = "done") -> None:
    STORE.write_completion_event(
        store,
        STORE.CompletionEvent(subplot_id=sid, state=state, idempotency_key=f"k:{sid}:{state}"),
    )


def test_projection_is_generated_from_state_no_status_field(tmp_path: Path) -> None:
    spec = _spec(
        [
            {"subplot_id": "a", "title": "a", "kind": "code"},
            {"subplot_id": "b", "title": "b", "kind": "code", "depends_on": ["a"]},
        ]
    )
    store = _store(tmp_path)
    _done(store, "a", "done")
    p = PROJ.project(spec, store)
    # R17: every per-node state is DERIVED, identical to derive_states — not a stored/operator-set scalar
    assert p["states"] == ENG.derive_states(spec, store)
    assert "status" not in p  # no operator-writable status field
    assert p["schema"] == "outcome-projection/1"


def test_projection_reports_progress_frontier_blocked(tmp_path: Path) -> None:
    spec = _spec(
        [
            {"subplot_id": "a", "title": "a", "kind": "code"},
            {"subplot_id": "b", "title": "b", "kind": "code", "depends_on": ["a"]},
        ]
    )
    store = _store(tmp_path)
    _done(store, "a", "done")
    p = PROJ.project(spec, store)
    assert p["progress"] == {"done": 1, "total": 2, "percent": 50}
    assert p["frontier"] == ["b"]  # a done -> b is the live frontier
    assert p["complete"] is False


def test_projection_frontier_excludes_terminal_and_dispatched(tmp_path: Path) -> None:
    # P2 regression: a negative-terminal node whose deps are satisfied must NOT be re-listed as a ready
    # frontier (a success-only ready_frontier did that); the frontier is derived from `states`.
    spec = _spec(
        [
            {"subplot_id": "failroot", "title": "f", "kind": "code"},
            {"subplot_id": "indep", "title": "i", "kind": "code"},
        ]
    )
    store = _store(tmp_path)
    _done(store, "failroot", "failed")  # a dead leaf with no deps
    p = PROJ.project(spec, store)
    assert p["states"]["failroot"] == "failed"
    assert "failroot" not in p["frontier"]  # the dead leaf is not presented as dispatchable
    assert p["frontier"] == ["indep"]  # consistent with the states map


def test_projection_never_auto_closes_the_parent(tmp_path: Path) -> None:
    # R25: the projection is a SECONDARY view — closing the parent stays the operator's keystroke.
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code"}])
    store = _store(tmp_path)
    _done(store, "a", "done")
    p = PROJ.project(spec, store)
    assert p["complete"] is True
    assert p["parent_close"] == "operator-keystroke-only"  # complete != auto-closed


def test_projection_is_deterministic(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code"}])
    store = _store(tmp_path)
    assert PROJ.project(spec, store) == PROJ.project(spec, store)  # generated, never hand-authored


def test_projection_surfaces_the_top_attention_item(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": "fail", "title": "f", "kind": "code"}])
    store = _store(tmp_path)
    _done(store, "fail", "failed")
    p = PROJ.project(spec, store)
    assert p["attention"]["count"] == 1
    assert p["attention"]["top"]["kind"] == "failure"


def test_projection_markdown_one_liner(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code"}])
    store = _store(tmp_path)
    line = PROJ.projection_markdown(spec, store)
    assert line.startswith("- **o** — Ship it") and line.endswith("\n")
    assert "0/1 (0%)" in line
