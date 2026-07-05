"""Tests for /outcome start --from-objective ingestion (#375, AC1-AC9).

Offline: a fake ``runner`` returns fixture GraphQL JSON, so the whole ingestion path (query normalize
-> edge inference -> node assembly -> spec) runs with no live ``gh``.
"""

from __future__ import annotations

import importlib.util
import json
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


# Dependency order (mirrors test_outcome_board_sync.py).
SPEC_MOD = _load("outcome_spec")
STORE_MOD = _load("outcome_store")
_load("outcome_orchestrator")
_load("outcome_dispatcher")
_load("outcome_merge")
_load("outcome_worktrees")
_load("outcome_decompose")
ENG = _load("outcome")
_load("reversibility_certificate")
BOARD_MOD = _load("outcome_board_sync")
DISC = _load("discover_subissues")
EDGES = _load("outcome_edges")


# --------------------------------------------------------------------------- fixtures


class _FakeResult:
    def __init__(self, stdout: str) -> None:
        self.returncode = 0
        self.stdout = stdout
        self.stderr = ""


def _sub(
    number: int,
    title: str,
    *,
    state: str = "OPEN",
    state_reason: str | None = None,
    labels: list[str] | None = None,
    tracked: list[int] | None = None,
) -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "state": state,
        "stateReason": state_reason,
        "url": f"https://github.com/o/r/issues/{number}",
        "labels": {"nodes": [{"name": name} for name in (labels or [])]},
        "assignees": {"nodes": []},
        "trackedIssues": {"nodes": [{"number": t} for t in (tracked or [])]},
    }


def _runner_for(subs: list[dict[str, Any]], *, parent_title: str = "Objective X") -> Any:
    payload = {
        "data": {
            "repository": {
                "issue": {
                    "number": 100,
                    "title": parent_title,
                    "state": "OPEN",
                    "subIssues": {"totalCount": len(subs), "nodes": subs},
                }
            }
        }
    }

    def _run(cmd: list[str], **kwargs: Any) -> _FakeResult:
        return _FakeResult(json.dumps(payload))

    return _run


# --------------------------------------------------------------------------- U1: normalize + fetch


def test_normalize_surfaces_state_reason_and_blocked_by() -> None:
    runner = _runner_for([_sub(2, "B", state="CLOSED", state_reason="COMPLETED", tracked=[1])])
    data = DISC.fetch_objective("o", "r", 100, runner=runner)
    sub = data["subissues"][0]
    assert sub["state_reason"] == "COMPLETED"
    assert sub["blocked_by"] == [1]


# --------------------------------------------------------------------------- U2: edge inference


def _ns(number: int, blocked_by: list[int] | None = None) -> dict[str, Any]:
    """A NORMALIZED sub-issue dict (the mapper's actual input contract — post-normalize())."""
    return {"number": number, "blocked_by": blocked_by or []}


def test_edges_linear_chain() -> None:
    """AC5: a linear blocked-by chain yields matching depends_on edges."""
    subs = [_ns(1), _ns(2, [1]), _ns(3, [2])]
    deps, dropped = EDGES.edges_from_relationships(subs)
    assert deps == {"sub-2": ["sub-1"], "sub-3": ["sub-2"]}
    assert dropped == []


def test_edges_cycle_dropped_and_reported() -> None:
    """AC6: a cyclic pair is dropped (one edge) and reported, leaving an acyclic map."""
    subs = [_ns(1, [2]), _ns(2, [1])]
    deps, dropped = EDGES.edges_from_relationships(subs)
    # exactly one direction kept, the reverse reported as a cycle
    kept_edges = [(k, t) for k, ts in deps.items() for t in ts]
    assert len(kept_edges) == 1
    assert any(d["reason"] == "cycle" for d in dropped)


def test_edges_dangling_dropped() -> None:
    """A blocked_by referencing a non-ingested number is dropped (KTD3)."""
    deps, dropped = EDGES.edges_from_relationships([_ns(1, [999])])
    assert deps == {}
    assert dropped == [{"reason": "dangling", "from": "sub-1", "to": "sub-999"}]


# --------------------------------------------------------------------------- U3: node assembly


def test_nodes_from_objective_count_kind_state() -> None:
    """AC2 node count; AC3 kind-from-label; AC4 closed sub-issue -> terminal state."""
    subs = [
        _sub(1, "A"),  # open, unlabeled -> code / pending
        _sub(2, "B", labels=["non-code"]),  # -> non-code
        _sub(3, "C", state="CLOSED", state_reason="COMPLETED"),  # -> done
        _sub(4, "D", state="CLOSED", state_reason="NOT_PLANNED"),  # -> rejected
    ]
    nodes, _dropped, title = ENG.nodes_from_objective("o", "r", 100, runner=_runner_for(subs))
    assert len(nodes) == 4  # AC2
    by = {n["subplot_id"]: n for n in nodes}
    assert by["sub-1"]["kind"] == "code" and by["sub-1"]["state"] == "pending"
    assert by["sub-2"]["kind"] == "non-code"  # AC3
    assert by["sub-3"]["state"] == "done"  # AC4
    assert by["sub-4"]["state"] == "rejected"  # AC4 (not_planned)
    assert title == "Objective X"
    # AC5/AC7 stamp: sub-issue's own number, fully-qualified
    assert by["sub-1"]["github"] == {"repo": "o/r", "issue": "o/r#1", "sub_issue": 1}


def test_github_stamp_is_consumable_by_board_sync_parser() -> None:
    """AC7/AC8 foundation: the github stamp resolves through the parser both consumers use."""
    nodes, _d, _t = ENG.nodes_from_objective("o", "r", 100, runner=_runner_for([_sub(5, "E")]))
    stamp = nodes[0]["github"]
    issue_raw = str(stamp.get("issue", "") or stamp.get("sub_issue", ""))
    parsed = BOARD_MOD._parse_issue_ref(issue_raw)
    assert parsed == ("o/r", 5)


# --------------------------------------------------------------------------- U4: end-to-end start


def test_start_from_objective_produces_valid_spec() -> None:
    """AC1/AC9: a 3-sub-issue objective yields a validate-passing 3-node DAG with correct edges.

    Builds the spec via ``OutcomeSpec.from_dict`` (the construction ``start()`` does internally) to
    exercise the ingestion->spec path offline, without ``start()``'s git-backed store setup.
    """
    subs = [_sub(1, "A"), _sub(2, "B", tracked=[1]), _sub(3, "C", tracked=[2])]
    nodes, dropped, title = ENG.nodes_from_objective("o", "r", 100, runner=_runner_for(subs))
    spec = SPEC_MOD.OutcomeSpec.from_dict(
        {"outcome_id": "oc-375", "objective": title, "nodes": nodes}
    )
    spec.validate()  # AC1 — must not raise
    assert len(spec.nodes) == 3  # AC9
    by = {n.subplot_id: n for n in spec.nodes}
    assert by["sub-2"].depends_on == ["sub-1"]
    assert by["sub-3"].depends_on == ["sub-2"]
    assert dropped == []


def test_starter_nodes_unchanged() -> None:
    """R7: the no-flag default (_starter_nodes) is untouched — still a 2-node design->build skeleton."""
    nodes = ENG._starter_nodes()
    assert len(nodes) == 2
