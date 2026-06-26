"""Oracle tests for the canonical outcome spec + DAG validator (OutcomeOrchestrator U1).

Covers the plan's stated U1 test expectations and the four scenario categories:

* happy — a valid DAG round-trips JSON deterministically; the frontier/layers are correct;
* edge — single-node and pure-fan-out (no edges) specs; revision bump on an edge redirect;
* error — duplicate id / self-dep / cycle / missing dep / orphan(unreachable) / invalid
  ``child_spec_ref`` / closed-vocabulary violations each FAIL ``validate`` (before any
  dispatch — these are the load-bearing oracle: weakening them lets a malformed outcome run);
* integration — the CLI ``validate``/``layers`` entrypoints exercise the real load+validate path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "plugins" / "saga" / "scripts" / "outcome_spec.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("outcome_spec", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register BEFORE exec so `from __future__ import annotations` + dataclass field-type
    # resolution can look the module up (required on 3.14, harmless on 3.12).
    sys.modules["outcome_spec"] = module
    spec.loader.exec_module(module)
    return module


M = _load()


def _valid_spec_dict() -> dict[str, Any]:
    """A minimal valid 3-node DAG: a root, a dependent code leaf, and a non-code leaf."""
    return {
        "schema_version": 1,
        "outcome_id": "ship-feature-x",
        "spec_revision": 1,
        "objective": "Ship feature X end to end",
        "nodes": [
            {"subplot_id": "design", "title": "Design the API", "kind": "non-code"},
            {
                "subplot_id": "build",
                "title": "Build the endpoint",
                "kind": "code",
                "backend": "team-execution",
                "depends_on": ["design"],
            },
            {
                "subplot_id": "docs",
                "title": "Write the docs",
                "kind": "non-code",
                "depends_on": ["build"],
            },
        ],
        "decision_trail": [],
        "cost_rollup": {},
    }


def _spec(data: dict[str, Any]):
    return M.OutcomeSpec.from_dict(data)


# --------------------------------------------------------------------------- happy path


def test_valid_dag_round_trips_json() -> None:
    spec = _spec(_valid_spec_dict())
    spec.validate()  # does not raise
    # Round-trip is deterministic: from_json(to_json(x)) == x at the dict level.
    again = M.OutcomeSpec.from_json(spec.to_json())
    assert again.to_dict() == spec.to_dict()
    # to_json is stable text (idempotent re-serialization).
    assert again.to_json() == spec.to_json()


def test_to_json_is_stable_and_newline_terminated() -> None:
    spec = _spec(_valid_spec_dict())
    text = spec.to_json()
    assert text.endswith("\n")
    assert json.loads(text)["outcome_id"] == "ship-feature-x"


def test_to_json_is_text_stable_across_reparse() -> None:
    # Lock in determinism (sort_keys=False is safe only because to_dict emits a fixed
    # insertion order): serialize -> reparse -> reserialize must yield byte-identical text.
    spec = _spec(_valid_spec_dict())
    once = spec.to_json()
    twice = M.OutcomeSpec.from_json(once).to_json()
    assert once == twice


def test_dependency_layers_orders_by_dependency() -> None:
    spec = _spec(_valid_spec_dict())
    assert M.dependency_layers(spec) == [["design"], ["build"], ["docs"]]


def test_ready_frontier_is_level_triggered() -> None:
    spec = _spec(_valid_spec_dict())
    assert M.ready_frontier(spec, completed=set()) == ["design"]
    assert M.ready_frontier(spec, completed={"design"}) == ["build"]
    assert M.ready_frontier(spec, completed={"design", "build"}) == ["docs"]
    assert M.ready_frontier(spec, completed={"design", "build", "docs"}) == []


def test_node_property_helpers() -> None:
    spec = _spec(_valid_spec_dict())
    build = spec.node_by_id("build")
    assert build is not None
    assert not build.is_terminal
    assert not build.is_outcome
    build.state = "done"
    assert build.is_terminal


# --------------------------------------------------------------------------- edge cases


def test_single_node_spec_is_valid() -> None:
    spec = _spec(
        {
            "outcome_id": "o",
            "objective": "do one thing",
            "nodes": [{"subplot_id": "only", "title": "the only subplot"}],
        }
    )
    spec.validate()  # a lone node is not an orphan


def test_pure_fanout_no_edges_is_valid() -> None:
    # No edges at all -> every node is an independent root of the objective -> valid.
    spec = _spec(
        {
            "outcome_id": "o",
            "objective": "three independent things",
            "nodes": [
                {"subplot_id": "a", "title": "a"},
                {"subplot_id": "b", "title": "b"},
                {"subplot_id": "c", "title": "c"},
            ],
        }
    )
    spec.validate()
    assert M.dependency_layers(spec) == [["a", "b", "c"]]


def test_edge_redirect_increments_spec_revision() -> None:
    spec = _spec(_valid_spec_dict())
    assert spec.spec_revision == 1
    # Redirect docs' dependency from build -> design (still acyclic, still connected).
    spec.redirect_dependency("docs", old_dep="build", new_dep="design")
    assert spec.spec_revision == 2
    assert spec.node_by_id("docs").depends_on == ["design"]
    # The structural change is recorded in the canonical decision trail (R26).
    assert spec.decision_trail[-1]["revision"] == 2


def test_bump_revision_records_decision_trail() -> None:
    spec = _spec(_valid_spec_dict())
    rev = spec.bump_revision(reason="promote build to a child outcome", at="2026-06-25")
    assert rev == 2
    assert spec.decision_trail[-1] == {
        "revision": 2,
        "reason": "promote build to a child outcome",
        "at": "2026-06-25",
    }


def test_redirect_that_would_cycle_is_rejected() -> None:
    spec = _spec(_valid_spec_dict())
    # build depends on design; redirect design's (nonexistent) dep won't work — instead make
    # build depend on docs to force a cycle build->docs->build.
    with pytest.raises(M.OutcomeSpecError):
        spec.redirect_dependency("build", old_dep="design", new_dep="docs")


# --------------------------------------------------------------------------- error paths


def test_duplicate_subplot_id_fails() -> None:
    data = _valid_spec_dict()
    data["nodes"].append({"subplot_id": "build", "title": "dup"})
    with pytest.raises(M.OutcomeSpecError, match="duplicate subplot_id"):
        _spec(data).validate()


def test_self_dependency_fails() -> None:
    data = _valid_spec_dict()
    data["nodes"][0]["depends_on"] = ["design"]  # design depends on itself
    with pytest.raises(M.OutcomeSpecError, match="self-dependency"):
        _spec(data).validate()


@pytest.mark.parametrize("bad", ["a b", "a|b", "a`b", "a/b", "a\nb", "a:b", "a#b"])
def test_non_slug_subplot_id_is_rejected(bad: str) -> None:
    # subplot_id is an identifier (interpolated raw into markdown tables / Mermaid / paths) — a non-slug
    # id must fail validate BEFORE any dispatch (R31), not silently corrupt a downstream render (U8).
    data = _valid_spec_dict()
    data["nodes"][0]["subplot_id"] = bad
    with pytest.raises(M.OutcomeSpecError, match="slug"):
        _spec(data).validate()


def test_slug_subplot_ids_validate() -> None:
    data = _valid_spec_dict()
    for sid in ("magic-link", "a.b", "A_B", "step-3"):
        data["nodes"][0]["subplot_id"] = sid
        data["nodes"][1]["depends_on"] = [sid]
        _spec(data).validate()  # all valid slugs


def test_cycle_fails() -> None:
    data = _valid_spec_dict()
    # design -> build -> docs already; add design depends_on docs to close the loop.
    data["nodes"][0]["depends_on"] = ["docs"]
    with pytest.raises(M.OutcomeSpecError, match="cycle"):
        _spec(data).validate()


def test_missing_dependency_fails() -> None:
    data = _valid_spec_dict()
    data["nodes"][1]["depends_on"] = ["ghost"]
    with pytest.raises(M.OutcomeSpecError, match="not a declared node"):
        _spec(data).validate()


def test_pipeline_plus_independent_node_is_valid() -> None:
    # A connected pipeline (design->build->docs) PLUS one genuinely-independent subplot is a
    # legitimate DAG (e.g. an independent "update the changelog" task), not a hard failure.
    data = _valid_spec_dict()
    data["nodes"].append({"subplot_id": "changelog", "title": "update the changelog"})
    spec = _spec(data)
    spec.validate()  # does NOT raise — disconnection is advisory, not dispatch-blocking
    # ...but it IS surfaced as a non-fatal structural warning (2 components).
    warnings = M.structural_warnings(spec)
    assert len(warnings) == 1
    assert "2 disconnected components" in warnings[0]


def test_structural_warnings_flag_multi_node_island() -> None:
    # The exact "forgot to wire it in" error: a 2-node island disconnected from the main
    # graph. The old degree-0-only check silently PASSED this; the advisory now catches it.
    data = {
        "outcome_id": "o",
        "objective": "two workstreams",
        "nodes": [
            {"subplot_id": "a", "title": "a"},
            {"subplot_id": "b", "title": "b", "depends_on": ["a"]},
            {"subplot_id": "x", "title": "x"},
            {"subplot_id": "y", "title": "y", "depends_on": ["x"]},
        ],
    }
    spec = _spec(data)
    spec.validate()  # multiple components is legal
    warnings = M.structural_warnings(spec)
    assert len(warnings) == 1
    assert "2 disconnected components" in warnings[0]
    # both islands named in the advisory
    assert "a, b" in warnings[0] and "x, y" in warnings[0]


def test_connected_graph_has_no_structural_warnings() -> None:
    assert M.structural_warnings(_spec(_valid_spec_dict())) == []


def test_invalid_child_spec_ref_self_recursion_fails() -> None:
    data = _valid_spec_dict()
    data["nodes"][1]["child_spec_ref"] = "ship-feature-x"  # == parent outcome_id
    with pytest.raises(M.OutcomeSpecError, match="self-recursion"):
        _spec(data).validate()


def test_child_spec_ref_equal_subplot_id_fails() -> None:
    data = _valid_spec_dict()
    data["nodes"][1]["child_spec_ref"] = "build"  # == own subplot_id
    with pytest.raises(M.OutcomeSpecError, match="own subplot_id"):
        _spec(data).validate()


def test_child_spec_ref_sibling_collision_fails() -> None:
    # A child outcome must be a DISTINCT outcome; a ref to another declared subplot in the
    # same spec is locally incoherent and fails (was silently accepted before).
    data = _valid_spec_dict()
    data["nodes"][1]["child_spec_ref"] = "design"  # == a SIBLING subplot_id
    with pytest.raises(M.OutcomeSpecError, match="collides with a declared sibling"):
        _spec(data).validate()


def test_valid_child_spec_ref_is_an_outcome_node() -> None:
    data = _valid_spec_dict()
    data["nodes"][1]["child_spec_ref"] = "build-subgraph"  # a distinct child outcome
    spec = _spec(data)
    spec.validate()
    assert spec.node_by_id("build").is_outcome


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("kind", "binary", "kind"),
        ("state", "almost-done", "state"),
        ("backend", "magic", "backend"),
        ("degrade_policy", "yolo", "degrade_policy"),
    ],
)
def test_closed_vocabulary_violation_fails(field: str, value: str, match: str) -> None:
    data = _valid_spec_dict()
    data["nodes"][1][field] = value
    with pytest.raises(M.OutcomeSpecError, match=match):
        _spec(data).validate()


@pytest.mark.parametrize("field", ["timeout_seconds", "heartbeat_seconds"])
def test_nonpositive_liveness_budget_fails(field: str) -> None:
    data = _valid_spec_dict()
    data["nodes"][1][field] = 0
    with pytest.raises(M.OutcomeSpecError, match=field):
        _spec(data).validate()


def test_empty_outcome_id_fails() -> None:
    data = _valid_spec_dict()
    data["outcome_id"] = ""
    with pytest.raises(M.OutcomeSpecError, match="outcome_id"):
        _spec(data).validate()


def test_empty_objective_fails() -> None:
    data = _valid_spec_dict()
    data["objective"] = ""
    with pytest.raises(M.OutcomeSpecError, match="objective"):
        _spec(data).validate()


def test_no_nodes_fails() -> None:
    with pytest.raises(M.OutcomeSpecError, match="at least one node"):
        _spec({"outcome_id": "o", "objective": "x", "nodes": []}).validate()


def test_from_dict_requires_nodes_list() -> None:
    with pytest.raises(M.OutcomeSpecError, match="'nodes' list"):
        M.OutcomeSpec.from_dict({"outcome_id": "o", "objective": "x"})


def test_bad_timeout_type_fails() -> None:
    data = _valid_spec_dict()
    data["nodes"][1]["timeout_seconds"] = "soon"
    with pytest.raises(M.OutcomeSpecError, match="integer or null"):
        _spec(data)


def test_string_depends_on_is_rejected_not_char_iterated() -> None:
    # `"depends_on": "design"` (a bare string) must FAIL, not silently become
    # ['d','e','s','i','g','n']. Cleanest validator-bypass guarded here.
    data = _valid_spec_dict()
    data["nodes"][1]["depends_on"] = "design"
    with pytest.raises(M.OutcomeSpecError, match="depends_on must be a list"):
        _spec(data)


def test_string_guarantee_tags_is_rejected() -> None:
    data = _valid_spec_dict()
    data["nodes"][1]["guarantee_tags"] = "release"
    with pytest.raises(M.OutcomeSpecError, match="guarantee_tags must be a list"):
        _spec(data)


@pytest.mark.parametrize("field", ["timeout_seconds", "heartbeat_seconds"])
def test_bool_liveness_budget_is_rejected(field: str) -> None:
    # JSON `true` would coerce to a silent 1-second budget (bool is an int subclass) — reject.
    data = _valid_spec_dict()
    data["nodes"][1][field] = True
    with pytest.raises(M.OutcomeSpecError, match="bool"):
        _spec(data)


@pytest.mark.parametrize("field", ["timeout_seconds", "heartbeat_seconds"])
def test_float_liveness_budget_is_rejected(field: str) -> None:
    # 1.9 would silently truncate to 1 — reject in a doc advertised as deterministic.
    data = _valid_spec_dict()
    data["nodes"][1][field] = 1.9
    with pytest.raises(M.OutcomeSpecError, match="integer or null"):
        _spec(data)


@pytest.mark.parametrize("value", [-5, 0])
def test_nonpositive_spec_revision_is_rejected(value: int) -> None:
    # spec_revision is a monotonic drift-detector (R26); a negative/zero seed is a footgun.
    data = _valid_spec_dict()
    data["spec_revision"] = value
    with pytest.raises(M.OutcomeSpecError, match="spec_revision must be"):
        _spec(data)


def test_redirect_rejection_is_atomic() -> None:
    # A redirect that would introduce a cycle must leave the spec COMPLETELY untouched —
    # no mutated edge, no bumped revision, no decision-trail entry that lies about a rejected
    # change (the canonical-fidelity guard, R26).
    spec = _spec(_valid_spec_dict())
    assert spec.spec_revision == 1
    trail_len_before = len(spec.decision_trail)
    deps_before = list(spec.node_by_id("build").depends_on)
    with pytest.raises(M.OutcomeSpecError, match="cycle"):
        spec.redirect_dependency("build", old_dep="design", new_dep="docs")
    # nothing advanced
    assert spec.spec_revision == 1
    assert len(spec.decision_trail) == trail_len_before
    assert spec.node_by_id("build").depends_on == deps_before
    # and the spec is still valid (not left in a corrupted, cyclic state)
    spec.validate()


def test_redirect_to_undeclared_target_is_atomic() -> None:
    spec = _spec(_valid_spec_dict())
    with pytest.raises(M.OutcomeSpecError, match="not a declared node"):
        spec.redirect_dependency("build", old_dep="design", new_dep="ghost")
    assert spec.spec_revision == 1
    assert spec.decision_trail == []
    assert spec.node_by_id("build").depends_on == ["design"]


def test_to_dict_is_a_detached_snapshot() -> None:
    # Mutating the serialized output must NOT leak back into the live Node (no shared aliasing
    # of the open pass-through maps).
    data = _valid_spec_dict()
    data["nodes"][1]["github"] = {"nested": {"pr": 1}}
    spec = _spec(data)
    d = spec.to_dict()
    d["nodes"][1]["github"]["nested"]["pr"] = 999
    assert spec.node_by_id("build").github["nested"]["pr"] == 1
    # ...and from_dict is likewise detached from its source data.
    src: dict[str, Any] = {"subplot_id": "n", "title": "n", "github": {"nested": {"x": 1}}}
    node = M.Node.from_dict(src)
    src["github"]["nested"]["x"] = 7
    assert node.github["nested"]["x"] == 1


# --------------------------------------------------------------------------- integration (CLI)


def test_cli_validate_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "outcome-spec.json"
    p.write_text(M.OutcomeSpec.from_dict(_valid_spec_dict()).to_json(), encoding="utf-8")
    rc = M.main(["validate", str(p)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {
        "valid": True,
        "outcome_id": "ship-feature-x",
        "nodes": 3,
        "spec_revision": 1,
        "warnings": [],
    }


def test_cli_validate_reports_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = _valid_spec_dict()
    data["nodes"][1]["depends_on"] = ["ghost"]
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    rc = M.main(["validate", str(p)])
    assert rc == 1
    err = json.loads(capsys.readouterr().err)
    assert err["valid"] is False
    assert "not a declared node" in err["error"]


def test_cli_layers(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "outcome-spec.json"
    p.write_text(M.OutcomeSpec.from_dict(_valid_spec_dict()).to_json(), encoding="utf-8")
    rc = M.main(["layers", str(p)])
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == {"layers": [["design"], ["build"], ["docs"]]}
