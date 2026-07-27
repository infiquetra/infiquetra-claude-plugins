"""Concurrent-writer conflict detection across dependency waves (#671).

Two units that run at the same time and declare the same file race on a shared working tree.
Claude Code has no cross-agent file lock, and the fleet lease never fenced the spawn kinds that
matter here — a PreToolUse-stamped, non-worktree reservation claims with no ``worktree_root``, so
``assert_write_target`` returns without a containment check (the deliberate #616 carve-out, pinned
by ``test_stamped_non_isolated_claim_leaves_write_unfenced``). Detection therefore has to happen
at emit, before anything spawns.

Measured baseline that motivated the shape of this check: across the 18 execution specs committed
to ``docs/plans/`` at the time of writing — 97 units, all 97 declaring ``files``, 92 waves — only
4 waves ran more than one unit and **zero** same-wave pairs shared a file. The check is therefore
prophylactic against today's specs and must not fire on them; the regression test at the bottom
pins exactly that.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
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


ES = _load("execution_spec")


def _unit(unit_id: str, files: list[str], **over: Any) -> dict[str, Any]:
    unit: dict[str, Any] = {
        "unit_id": unit_id,
        "label": unit_id,
        "prompt": "do the thing",
        "tier": {"model": "sonnet", "effort": "high"},
        "files": files,
    }
    unit.update(over)
    return unit


def _spec(*units: dict[str, Any]) -> Any:
    return ES.ExecutionSpec.from_dict(
        {"name": "conflict-demo", "description": "d", "units": list(units)}
    )


# --- detection ---------------------------------------------------------------


def test_disjoint_files_in_one_wave_are_fine() -> None:
    spec = _spec(_unit("U1", ["a.py"]), _unit("U2", ["b.py"]))
    assert ES.wave_file_conflicts(spec) == []


def test_same_file_in_one_wave_conflicts() -> None:
    spec = _spec(_unit("U1", ["a.py"]), _unit("U2", ["a.py"]))
    (conflict,) = ES.wave_file_conflicts(spec)
    assert (conflict.wave, conflict.left, conflict.right) == (1, "U1", "U2")
    assert conflict.files == ("a.py",)


def test_a_dependency_edge_resolves_the_conflict() -> None:
    """The cheap repair: sequence them. They no longer share a wave, so they cannot race."""
    spec = _spec(_unit("U1", ["a.py"]), _unit("U2", ["a.py"], depends_on=["U1"]))
    assert ES.wave_file_conflicts(spec) == []


def test_units_in_different_waves_never_conflict() -> None:
    spec = _spec(
        _unit("U1", ["a.py"]),
        _unit("U2", ["b.py"], depends_on=["U1"]),
        _unit("U3", ["a.py"], depends_on=["U2"]),
    )
    assert ES.wave_file_conflicts(spec) == []


def test_every_declared_path_participates_not_just_the_first() -> None:
    """Fix 1 vs `segment_units`, which keys only on `files[0]`.

    U1's collision is on its SECOND declared path. A first-file-only comparison misses it.
    """
    spec = _spec(_unit("U1", ["a.py", "shared.py"]), _unit("U2", ["b.py", "shared.py"]))
    (conflict,) = ES.wave_file_conflicts(spec)
    assert conflict.files == ("shared.py",)


def test_shared_file_across_different_plugin_directories_conflicts() -> None:
    """Fix 2: exact paths, not the `plugins/<name>` directory prefix.

    These two units key to different directories, so `segment_units` would place them in separate
    resident segments and never notice they both edit the same conftest.
    """
    spec = _spec(
        _unit("U1", ["plugins/saga/x.py", "tests/conftest.py"]),
        _unit("U2", ["plugins/mission-control/y.py", "tests/conftest.py"]),
    )
    (conflict,) = ES.wave_file_conflicts(spec)
    assert conflict.files == ("tests/conftest.py",)


def test_non_adjacent_units_in_the_same_wave_conflict() -> None:
    """Fix 3: `segment_units` groups only CONTIGUOUS runs, so it cannot see this pair.

    U1 and U3 both touch `shared.py`; U2 sits between them in declaration order and touches
    neither. All three are dependency-free, so all three run together.
    """
    spec = _spec(
        _unit("U1", ["shared.py"]),
        _unit("U2", ["unrelated.py"]),
        _unit("U3", ["shared.py"]),
    )
    (conflict,) = ES.wave_file_conflicts(spec)
    assert (conflict.left, conflict.right) == ("U1", "U3")


def test_every_conflicting_pair_is_reported() -> None:
    spec = _spec(_unit("U1", ["a.py"]), _unit("U2", ["a.py"]), _unit("U3", ["a.py"]))
    pairs = {(c.left, c.right) for c in ES.wave_file_conflicts(spec)}
    assert pairs == {("U1", "U2"), ("U1", "U3"), ("U2", "U3")}


def test_units_declaring_no_files_never_conflict() -> None:
    """An empty `files` list is not a wildcard — absence of a claim is not a claim on everything."""
    spec = _spec(_unit("U1", []), _unit("U2", []))
    assert ES.wave_file_conflicts(spec) == []


def test_a_single_unit_wave_cannot_conflict() -> None:
    assert ES.wave_file_conflicts(_spec(_unit("U1", ["a.py"]))) == []


# --- the halt ----------------------------------------------------------------


def test_assert_raises_and_names_both_units_and_the_file() -> None:
    spec = _spec(_unit("U1", ["a.py"]), _unit("U2", ["a.py"]))
    with pytest.raises(ES.SpecError) as excinfo:
        ES.assert_no_wave_file_conflicts(spec)
    message = str(excinfo.value)
    assert "U1" in message and "U2" in message and "a.py" in message
    assert "depends_on" in message, "the message must name the repair"


def test_assert_is_silent_on_a_clean_spec() -> None:
    ES.assert_no_wave_file_conflicts(_spec(_unit("U1", ["a.py"]), _unit("U2", ["b.py"])))


def test_workflow_emit_halts_on_a_conflict() -> None:
    spec = _spec(_unit("U1", ["a.py"]), _unit("U2", ["a.py"]))
    with pytest.raises(ES.SpecError, match="run concurrently declare the same file"):
        ES.emit_workflow_script(spec)


def test_workflow_emit_succeeds_once_sequenced() -> None:
    spec = _spec(_unit("U1", ["a.py"]), _unit("U2", ["a.py"], depends_on=["U1"]))
    assert "agent(" in ES.emit_workflow_script(spec)


# --- the historical corpus must stay clean -----------------------------------


def test_committed_specs_have_no_wave_conflicts() -> None:
    """Regression sentinel over every spec in `docs/plans/`.

    This check ships as a HALT, so a false positive would block real work. The measured baseline
    is zero conflicts across all 18; if that ever changes, it should change because a genuinely
    conflicting spec was authored — not because the detector drifted.
    """
    specs = sorted(ROOT.glob("docs/plans/*-spec.json"))
    assert len(specs) >= 18, "corpus shrank — re-check the baseline before trusting this test"
    for path in specs:
        spec = ES.ExecutionSpec.from_dict(json.loads(path.read_text(encoding="utf-8")))
        assert ES.wave_file_conflicts(spec) == [], path.name
