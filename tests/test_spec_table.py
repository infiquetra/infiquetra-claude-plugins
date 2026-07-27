"""Tests for the execution-spec approval table (#668).

The table is what an operator actually reads at a backend-approval gate, so the assertions here
are about *decision-relevant* content, not cosmetics: the declared tier of every unit, the
dependency waves, the spend-versus-budget verdict, and -- the load-bearing one -- whether the
chosen backend can enforce what the spec declares.

The enforceability rows are read from ``execution_spec``'s own registries, never a second copy, so
these tests also pin that coupling: a registry edit must move the table.
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
ST = _load("spec_table")


def _unit(unit_id: str, model: str = "sonnet", effort: str = "high", **over: Any) -> dict[str, Any]:
    unit: dict[str, Any] = {
        "unit_id": unit_id,
        "label": f"do {unit_id}",
        "tier": {"model": model, "effort": effort},
        "prompt": f"work on {unit_id}",
        "returns": "a summary",
        "depends_on": [],
    }
    unit.update(over)
    return unit


def _spec(*units: dict[str, Any], **over: Any) -> Any:
    data: dict[str, Any] = {
        "name": "test-spec",
        "description": "a spec for tests",
        "repo": "infiquetra/example",
        "units": list(units),
    }
    data.update(over)
    return ES.ExecutionSpec.from_dict(data)


# --------------------------------------------------------------------------- shape


def test_every_unit_appears_with_its_declared_tier() -> None:
    spec = _spec(_unit("U1", "opus", "high"), _unit("U2", "haiku", "low", depends_on=["U1"]))
    out = ST.render(spec)
    assert "`U1`" in out and "`U2`" in out
    assert "`opus:high`" in out
    assert "`haiku:low`" in out


def test_dependency_waves_show_what_runs_in_parallel() -> None:
    spec = _spec(_unit("U1"), _unit("U2", depends_on=["U1"]), _unit("U3", depends_on=["U1"]))
    out = ST.render(spec)
    assert "2 in parallel" in out, "U2 and U3 share a wave and must be reported as concurrent"


def test_serial_chain_reports_no_parallelism() -> None:
    spec = _spec(_unit("U1"), _unit("U2", depends_on=["U1"]))
    # The section header always says "runs in parallel"; the per-wave suffix is the signal.
    assert "— 2 in parallel" not in ST.render(spec)


def test_over_budget_is_called_out() -> None:
    spec = _spec(_unit("U1", "opus", "high"), cost_budget=1)
    assert "OVER BUDGET" in ST.render(spec)


def test_within_budget_is_not_flagged() -> None:
    spec = _spec(_unit("U1", "haiku", "low"), cost_budget=10_000)
    out = ST.render(spec)
    assert "OVER BUDGET" not in out
    assert "/ 10000" in out


def test_fanout_without_targets_is_flagged_because_emit_will_fail() -> None:
    spec = _spec(_unit("U1", fanout=True, targets=[]))
    assert "no targets" in ST.render(spec)


def test_verify_panel_renders_n_and_pass_rule() -> None:
    spec = _spec(_unit("U1", verify={"n": 3, "pass_rule": "majority"}))
    assert "verify n=3/majority" in ST.render(spec)


def test_cycle_is_reported_not_raised() -> None:
    spec = _spec(_unit("U1", depends_on=["U2"]), _unit("U2", depends_on=["U1"]))
    out = ST.render(spec)
    assert "Cannot compute" in out, "a cyclic spec must still render its unit table"


# ------------------------------------------------------------------- enforceability


def test_workflow_backend_enforces_both_sandbox_axes_for_a_verify_panel() -> None:
    spec = _spec(_unit("U1", verify={"n": 3, "pass_rule": "majority"}))
    out = ST.render(spec, backend="cc-workflows-ultracode")
    assert "sandbox: read-only | enforced" in out
    assert "sandbox: disposable worktree | enforced" in out
    assert "NOT enforceable" not in out


def test_team_execution_enforces_neither_axis_for_the_same_spec() -> None:
    """The team-vs-workflow asymmetry, surfaced at the approval gate rather than in source."""
    spec = _spec(_unit("U1", verify={"n": 3, "pass_rule": "majority"}))
    out = ST.render(spec, backend="team-execution")
    assert out.count("NOT enforceable") == 2
    assert "pick another backend" in out


def test_unknown_backend_enforces_nothing() -> None:
    """Unknown is never permissive -- matches the emitter's own R3/R4 stance."""
    spec = _spec(_unit("U1", verify={"n": 3, "pass_rule": "majority"}))
    rows = ST.enforcement_rows(spec, "some-future-backend")
    sandbox = [r for r in rows if r[0].startswith("sandbox:")]
    assert sandbox and all("NOT" in status for _, status, _ in sandbox)


def test_enforceability_reads_the_live_registry_not_a_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _spec(_unit("U1", verify={"n": 3, "pass_rule": "majority"}))
    assert "NOT enforceable" not in ST.render(spec, backend="cc-workflows-ultracode")
    monkeypatch.setitem(ES.SANDBOX_ENFORCEABLE_BY_BACKEND, "cc-workflows-ultracode", frozenset())
    assert "NOT enforceable" in ST.render(spec, backend="cc-workflows-ultracode")


def test_spec_with_no_restrictive_axis_says_so() -> None:
    spec = _spec(_unit("U1"))
    out = ST.render(spec, backend="team-execution")
    assert "no restrictive sandbox axis" in out


# ----------------------------------------------------------------------------- CLI


def test_cli_renders_a_real_spec(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "spec.json"
    path.write_text(
        json.dumps(
            {
                "name": "cli-spec",
                "description": "d",
                "repo": "o/r",
                "units": [_unit("U1", "opus", "high")],
            }
        ),
        encoding="utf-8",
    )
    assert ST.main([str(path), "--backend", "inline"]) == 0
    out = capsys.readouterr().out
    assert "cli-spec" in out and "`opus:high`" in out


def test_cli_missing_file_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert ST.main([str(tmp_path / "nope.json")]) == 2
    assert "no such spec" in capsys.readouterr().err


def test_cli_malformed_json_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert ST.main([str(path)]) == 2
    assert "not valid JSON" in capsys.readouterr().err


def test_cli_invalid_spec_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "invalid.json"
    # A structurally malformed unit -- an unknown model is rejected by Tier.from_dict.
    bad = _unit("U1")
    bad["tier"] = {"model": "not-a-model", "effort": "high"}
    path.write_text(
        json.dumps({"name": "x", "description": "d", "repo": "o/r", "units": [bad]}),
        encoding="utf-8",
    )
    assert ST.main([str(path)]) == 2
    assert "invalid spec" in capsys.readouterr().err


def test_cli_rejects_an_unknown_backend(tmp_path: Path) -> None:
    path = tmp_path / "spec.json"
    path.write_text(
        json.dumps({"name": "n", "description": "d", "repo": "o/r", "units": [_unit("U1")]}),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit):
        ST.main([str(path), "--backend", "not-a-backend"])


# ---------------------------------------------------------------------------
# Concurrent-writer safety (#671)
# ---------------------------------------------------------------------------


def test_conflicting_units_render_a_halt_warning() -> None:
    """The operator sees the collision at the approval gate, not as a surprise at emit."""
    table = ST.render(
        _spec(_unit("U1", files=["auth.py"]), _unit("U2", files=["auth.py"])),
        backend="cc-workflows-ultracode",
    )
    assert "### Concurrent-writer safety" in table
    assert "`U1` + `U2`" in table
    assert "`auth.py`" in table
    assert "will HALT" in table
    assert "merge them into one unit" in table, "the render must name the preferred repair"


def test_a_clean_parallel_wave_says_so_explicitly() -> None:
    """Silence would be ambiguous — an operator cannot tell 'checked and safe' from 'not checked'."""
    table = ST.render(_spec(_unit("U1", files=["a.py"]), _unit("U2", files=["b.py"])))
    assert "### Concurrent-writer safety" in table
    assert "no write can be lost to a race" in table
    assert "HALT" not in table


def test_a_fully_sequential_spec_omits_the_section() -> None:
    """Nothing runs concurrently, so there is no concurrency question to answer."""
    table = ST.render(
        _spec(_unit("U1", files=["a.py"]), _unit("U2", files=["a.py"], depends_on=["U1"]))
    )
    assert "### Concurrent-writer safety" not in table


def test_a_dependency_cycle_does_not_double_report() -> None:
    """`dependency_layers` already raised for the cycle; the conflict section must not re-raise."""
    table = ST.render(
        _spec(
            _unit("U1", files=["a.py"], depends_on=["U2"]),
            _unit("U2", files=["a.py"], depends_on=["U1"]),
        )
    )
    assert "Cannot compute" in table
    assert "### Concurrent-writer safety" not in table
