"""Oracle tests for the execution-spec schema + workflow-script emitter (U10, R9 keystone).

Covers the plan's stated test expectation: a spec emits a valid script with per-unit
tiers; missing enumerated targets (R10) and mis-tiered pilots (R3) are REJECTED at emit.

The R3/R10 rejection tests are the load-bearing oracle: they assert that a mis-built spec
FAILS emit, so weakening them would let an invalid (un-runnable / mis-tiered) workflow
escape authoring. They must never be loosened to "pass".
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "plugins" / "saga" / "scripts" / "execution_spec.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("execution_spec", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec so `from __future__ import annotations` +
    # dataclass field-type resolution can look the module up (required on Python 3.14;
    # harmless on 3.12).
    sys.modules["execution_spec"] = module
    spec.loader.exec_module(module)
    return module


def _valid_spec_dict() -> dict[str, object]:
    """A minimal valid spec: a haiku preflight, a sonnet build, an opus judgment unit."""
    return {
        "name": "demo-campaign",
        "description": "a demo execution spec",
        "repo": "/tmp/repo",
        "units": [
            {
                "unit_id": "U1",
                "label": "preflight",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "verify grounding facts on origin/main",
                "returns": ["ready", "drift"],
                "escalation": "HALT on drift",
            },
            {
                "unit_id": "U2",
                "label": "build",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "implement the unit",
                "depends_on": ["U1"],
                "returns": ["done", "files"],
            },
            {
                "unit_id": "U3",
                "label": "judge",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "review the diff",
                "depends_on": ["U2"],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Happy path: a valid spec emits a runnable script with per-unit tiers.
# ---------------------------------------------------------------------------


def test_valid_spec_emits_script_with_per_unit_tiers() -> None:
    mod = _load()
    spec = mod.ExecutionSpec.from_dict(_valid_spec_dict())
    spec.validate()  # no raise
    script = mod.emit_workflow_script(spec)

    # The harness shape: meta export + control-flow agent() calls, one per unit.
    assert "export const meta" in script
    assert script.count("await agent(") == 3
    # Per-unit {model, effort} tiers are rendered on each agent() call (R2(b)).
    assert 'model: "haiku"' in script
    assert 'effort: "low"' in script
    assert 'model: "sonnet"' in script
    assert 'effort: "high"' in script
    assert 'model: "opus"' in script
    # The repo constant is emitted when present.
    assert 'const REPO = "/tmp/repo"' in script
    # A dependency barrier is documented for the dependent unit.
    assert "depends_on: U1" in script


def test_round_trip_to_dict_from_dict() -> None:
    mod = _load()
    original = _valid_spec_dict()
    spec = mod.ExecutionSpec.from_dict(original)
    rebuilt = mod.ExecutionSpec.from_dict(spec.to_dict())
    assert rebuilt.name == spec.name
    assert [u.unit_id for u in rebuilt.units] == ["U1", "U2", "U3"]
    assert rebuilt.units[0].tier.model == "haiku"


# ---------------------------------------------------------------------------
# R10: a fan-out unit without enumerated targets FAILS emit.
# ---------------------------------------------------------------------------


def test_fanout_without_targets_fails_emit() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    units.append(
        {
            "unit_id": "U4",
            "label": "fan it out",
            "tier": {"model": "sonnet", "effort": "high"},
            "prompt": "run the op across targets",
            "fanout": True,
            # targets intentionally OMITTED -> R10 violation
        }
    )
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError) as exc:
        mod.emit_workflow_script(spec)
    assert "R10" in str(exc.value)
    assert "U4" in str(exc.value)


def test_fanout_with_enumerated_targets_emits_and_reconciles() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    units.append(
        {
            "unit_id": "U4",
            "label": "fan it out",
            "tier": {"model": "sonnet", "effort": "high"},
            "prompt": "run the op across targets",
            "fanout": True,
            "targets": ["alpha", "beta", "gamma"],
        }
    )
    spec = mod.ExecutionSpec.from_dict(data)
    script = mod.emit_workflow_script(spec)
    # Enumerated targets are surfaced AND a reconciliation instruction is baked in (R10).
    assert "alpha, beta, gamma" in script
    assert "RECONCILE" in script
    assert "FAN-OUT TARGETS (3" in script


def test_targets_without_fanout_flag_fails() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    units.append(
        {
            "unit_id": "U4",
            "label": "stray targets",
            "tier": {"model": "sonnet", "effort": "high"},
            "prompt": "x",
            "targets": ["a"],
            # fanout omitted -> targets without fanout is a malformed unit
        }
    )
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError):
        spec.validate()


# ---------------------------------------------------------------------------
# R3: a pilot at a different tier than its fan-out FAILS emit.
# ---------------------------------------------------------------------------


def test_pilot_same_tier_emits() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    units.append(
        {
            "unit_id": "Upilot",
            "label": "pilot one target",
            "tier": {"model": "sonnet", "effort": "high"},
            "prompt": "pilot the op on one target",
        }
    )
    units.append(
        {
            "unit_id": "Ufan",
            "label": "fan out same tier",
            "tier": {"model": "sonnet", "effort": "high"},
            "prompt": "run across targets",
            "fanout": True,
            "targets": ["a", "b"],
            "pilot": "Upilot",
        }
    )
    spec = mod.ExecutionSpec.from_dict(data)
    script = mod.emit_workflow_script(spec)  # no raise
    assert "pilot: Upilot" in script


def test_pilot_different_model_fails_emit() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    units.append(
        {
            "unit_id": "Upilot",
            "label": "pilot",
            "tier": {"model": "opus", "effort": "high"},  # opus pilot
            "prompt": "pilot",
        }
    )
    units.append(
        {
            "unit_id": "Ufan",
            "label": "fan out",
            "tier": {"model": "sonnet", "effort": "high"},  # sonnet fan-out -> tier mismatch
            "prompt": "fan",
            "fanout": True,
            "targets": ["a", "b"],
            "pilot": "Upilot",
        }
    )
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError) as exc:
        mod.emit_workflow_script(spec)
    assert "R3" in str(exc.value)
    assert "Ufan" in str(exc.value)


def test_pilot_different_effort_fails_emit() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    units.append(
        {
            "unit_id": "Upilot",
            "label": "pilot",
            "tier": {"model": "sonnet", "effort": "medium"},  # medium effort
            "prompt": "pilot",
        }
    )
    units.append(
        {
            "unit_id": "Ufan",
            "label": "fan out",
            "tier": {"model": "sonnet", "effort": "high"},  # high effort -> mismatch
            "prompt": "fan",
            "fanout": True,
            "targets": ["a", "b"],
            "pilot": "Upilot",
        }
    )
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError):
        mod.emit_workflow_script(spec)


# ---------------------------------------------------------------------------
# Cheap-tier budget rider baked into haiku agents (workflow_structuredoutput_budget).
# ---------------------------------------------------------------------------


def test_cheap_tier_agent_carries_budget_rider() -> None:
    mod = _load()
    spec = mod.ExecutionSpec.from_dict(_valid_spec_dict())
    script = mod.emit_workflow_script(spec)
    # U1 is haiku -> the budget rider (cap/emit/skim/batch) is baked into its prompt.
    assert "BUDGET DISCIPLINE" in script
    assert "MANDATORY EMIT" in script
    assert "SKIM" in script


def test_opus_agent_has_no_budget_rider() -> None:
    mod = _load()
    # A spec with ONLY opus units -> no budget rider anywhere (headroom).
    data: dict[str, object] = {
        "name": "rich",
        "description": "all opus",
        "units": [
            {
                "unit_id": "U1",
                "label": "judge",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "judge it",
            }
        ],
    }
    spec = mod.ExecutionSpec.from_dict(data)
    script = mod.emit_workflow_script(spec)
    assert "BUDGET DISCIPLINE" not in script


# ---------------------------------------------------------------------------
# Malformed specs are rejected with actionable messages.
# ---------------------------------------------------------------------------


def test_bad_tier_value_fails() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    first = units[0]
    assert isinstance(first, dict)
    first["tier"] = {"model": "gpt", "effort": "low"}
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError):
        spec.validate()


def test_duplicate_unit_id_fails() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    dup = dict(units[0])
    units.append(dup)
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError):
        spec.validate()


def test_unknown_dependency_fails() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    last = units[-1]
    assert isinstance(last, dict)
    last["depends_on"] = ["Unope"]
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError):
        spec.validate()


def test_empty_units_fails() -> None:
    mod = _load()
    spec = mod.ExecutionSpec.from_dict({"name": "x", "description": "y", "units": []})
    with pytest.raises(mod.SpecError):
        spec.validate()


# ---------------------------------------------------------------------------
# U1: dependency_layers (Kahn) -- topological waves, pilot-as-barrier, cycles.
# ---------------------------------------------------------------------------


def test_dependency_layers_two_independent_plus_one_dependent() -> None:
    mod = _load()
    data: dict[str, object] = {
        "name": "layered",
        "description": "two independent + one dependent",
        "units": [
            {
                "unit_id": "A",
                "label": "a",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "a",
            },
            {
                "unit_id": "B",
                "label": "b",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "b",
            },
            {
                "unit_id": "C",
                "label": "c",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "c",
                "depends_on": ["A", "B"],
            },
        ],
    }
    spec = mod.ExecutionSpec.from_dict(data)
    layers = mod.dependency_layers(spec)
    # 2 layers: {A, B} ready together, then C behind the barrier.
    assert layers == [["A", "B"], ["C"]]


def test_dependency_layers_single_unit() -> None:
    mod = _load()
    data: dict[str, object] = {
        "name": "solo",
        "description": "one unit, one layer",
        "units": [
            {
                "unit_id": "U1",
                "label": "only",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "x",
            }
        ],
    }
    spec = mod.ExecutionSpec.from_dict(data)
    assert mod.dependency_layers(spec) == [["U1"]]


def test_dependency_layers_pilot_is_an_implicit_barrier() -> None:
    mod = _load()
    # The pilot has NO explicit depends_on edge from the fan-out, yet R3 requires it to
    # land in an EARLIER layer than the fan-out it gates.
    data: dict[str, object] = {
        "name": "piloted",
        "description": "pilot gates a fan-out",
        "units": [
            {
                "unit_id": "Upilot",
                "label": "pilot",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "pilot one",
            },
            {
                "unit_id": "Ufan",
                "label": "fan",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "fan out",
                "fanout": True,
                "targets": ["a", "b"],
                "pilot": "Upilot",
            },
        ],
    }
    spec = mod.ExecutionSpec.from_dict(data)
    layers = mod.dependency_layers(spec)
    assert layers == [["Upilot"], ["Ufan"]]


def test_dependency_layers_cycle_fails() -> None:
    mod = _load()
    data: dict[str, object] = {
        "name": "cyclic",
        "description": "A->B->A",
        "units": [
            {
                "unit_id": "A",
                "label": "a",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "a",
                "depends_on": ["B"],
            },
            {
                "unit_id": "B",
                "label": "b",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "b",
                "depends_on": ["A"],
            },
        ],
    }
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError) as exc:
        mod.dependency_layers(spec)
    assert "cycle" in str(exc.value)


def test_dependency_cycle_fails_validate() -> None:
    mod = _load()
    data: dict[str, object] = {
        "name": "cyclic",
        "description": "A->B->A",
        "units": [
            {
                "unit_id": "A",
                "label": "a",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "a",
                "depends_on": ["B"],
            },
            {
                "unit_id": "B",
                "label": "b",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "b",
                "depends_on": ["A"],
            },
        ],
    }
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError):
        spec.validate()


# ---------------------------------------------------------------------------
# U1: the optional Verify (refute-N) panel -- validate, bounds, round-trip.
# ---------------------------------------------------------------------------


def test_verify_panel_validates_and_round_trips() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    second = units[1]
    assert isinstance(second, dict)
    second["verify"] = {"n": 3, "pass_rule": "majority"}
    spec = mod.ExecutionSpec.from_dict(data)
    spec.validate()  # no raise
    # to_dict -> from_dict preserves the verify panel.
    rebuilt = mod.ExecutionSpec.from_dict(spec.to_dict())
    panel = rebuilt.units[1].verify
    assert panel is not None
    assert panel.n == 3
    assert panel.pass_rule == "majority"


def test_verify_absent_round_trips_unchanged() -> None:
    mod = _load()
    # No verify on any unit -> to_dict emits no 'verify' key (team_emitter compat / R5).
    spec = mod.ExecutionSpec.from_dict(_valid_spec_dict())
    for unit_dict in (u.to_dict() for u in spec.units):
        assert "verify" not in unit_dict
    rebuilt = mod.ExecutionSpec.from_dict(spec.to_dict())
    assert all(u.verify is None for u in rebuilt.units)


def test_verify_n_at_cap_boundary_validates() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    first = units[0]
    assert isinstance(first, dict)
    first["verify"] = {"n": mod.VERIFY_N_CAP, "pass_rule": "unanimous"}
    spec = mod.ExecutionSpec.from_dict(data)
    spec.validate()  # N == CAP is allowed (no raise)


def test_verify_on_a_fanout_unit_validates() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    units.append(
        {
            "unit_id": "U4",
            "label": "fan with a panel",
            "tier": {"model": "sonnet", "effort": "high"},
            "prompt": "fan it out",
            "fanout": True,
            "targets": ["a", "b"],
            "verify": {"n": 3, "pass_rule": "majority"},
        }
    )
    spec = mod.ExecutionSpec.from_dict(data)
    spec.validate()  # no raise
    panel = spec.units[-1].verify
    assert panel is not None and panel.n == 3


def test_verify_n_zero_fails() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    first = units[0]
    assert isinstance(first, dict)
    first["verify"] = {"n": 0, "pass_rule": "majority"}
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError):
        spec.validate()


def test_verify_missing_pass_rule_fails() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    first = units[0]
    assert isinstance(first, dict)
    first["verify"] = {"n": 3}  # pass_rule omitted -> rejected at from_dict
    with pytest.raises(mod.SpecError):
        mod.ExecutionSpec.from_dict(data)


def test_verify_bad_pass_rule_fails() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    first = units[0]
    assert isinstance(first, dict)
    first["verify"] = {"n": 3, "pass_rule": "supermajority"}
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError):
        spec.validate()


def test_verify_n_above_cap_fails() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    first = units[0]
    assert isinstance(first, dict)
    first["verify"] = {"n": mod.VERIFY_N_CAP + 1, "pass_rule": "majority"}
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError) as exc:
        spec.validate()
    assert "cap" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# CLI surface (validate / emit) round-trips through a temp JSON file.
# ---------------------------------------------------------------------------


def test_cli_validate_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod = _load()
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_valid_spec_dict()))
    rc = mod.main(["validate", str(spec_path)])
    assert rc == 0
    assert "valid execution-spec" in capsys.readouterr().out


def test_cli_validate_rejects_bad_fanout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    units.append(
        {
            "unit_id": "U4",
            "label": "bad",
            "tier": {"model": "sonnet", "effort": "high"},
            "prompt": "x",
            "fanout": True,
        }
    )
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(data))
    rc = mod.main(["emit", str(spec_path)])
    assert rc == 2
    assert "SPEC ERROR" in capsys.readouterr().err


def test_cli_emit_writes_file(tmp_path: Path) -> None:
    mod = _load()
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_valid_spec_dict()))
    out = tmp_path / "out.workflow.js"
    rc = mod.main(["emit", str(spec_path), "-o", str(out)])
    assert rc == 0
    assert "await agent(" in out.read_text()


# ---------------------------------------------------------------------------
# U2: layer-parallel emission -- independent units share one parallel() wave;
# a dependent unit sits behind an await barrier in a later layer.
# ---------------------------------------------------------------------------


def _layered_spec_dict() -> dict[str, object]:
    """Two independent units (A, B) and a 3rd (C) dependent on both."""
    return {
        "name": "layered-emit",
        "description": "two independent + one dependent",
        "repo": "/tmp/repo",
        "units": [
            {
                "unit_id": "A",
                "label": "alpha",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "do a",
            },
            {
                "unit_id": "B",
                "label": "beta",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "do b",
            },
            {
                "unit_id": "C",
                "label": "gamma",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "do c",
                "depends_on": ["A", "B"],
            },
        ],
    }


def test_independent_units_emit_a_parallel_wave() -> None:
    mod = _load()
    spec = mod.ExecutionSpec.from_dict(_layered_spec_dict())
    script = mod.emit_workflow_script(spec)
    # A and B are independent -> one parallel([...]) wave, destructured into both vars.
    assert "await parallel([" in script
    assert "const [A, B] = await parallel([" in script
    # Two thunks in the wave, one per independent unit.
    assert script.count("() =>") == 2
    # The dependent unit C sits in a later layer, behind an await barrier (singleton).
    assert "const C = await agent(" in script
    # The parallel wave appears BEFORE C's awaited agent() (topological order).
    assert script.index("await parallel([") < script.index("const C = await agent(")
    # Per-unit tiers are preserved on the parallel members and the dependent unit.
    assert 'model: "sonnet"' in script
    assert 'model: "opus"' in script


def test_single_layer_singleton_uses_await_agent_not_parallel() -> None:
    mod = _load()
    # The all-serial _valid_spec_dict is three singleton layers -> no parallel().
    spec = mod.ExecutionSpec.from_dict(_valid_spec_dict())
    script = mod.emit_workflow_script(spec)
    assert "await parallel([" not in script
    assert script.count("await agent(") == 3


# ---------------------------------------------------------------------------
# U2: a verify {n, pass_rule} unit -> N verifier agent() calls in a parallel()
# panel + the pass-rule reconciliation, at the unit's own tier (R4).
# ---------------------------------------------------------------------------


def test_verify_panel_emits_n_verifier_agents_and_majority_check() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    second = units[1]  # U2, sonnet/high
    assert isinstance(second, dict)
    second["verify"] = {"n": 3, "pass_rule": "majority"}
    spec = mod.ExecutionSpec.from_dict(data)
    script = mod.emit_workflow_script(spec)
    # The panel is a parallel([...]) of N verifier thunks over U2's result.
    assert "U2_verdicts = await parallel([" in script
    # N=3 verifier agent() calls inside the panel.
    assert script.count("() => agent(") == 3
    # The verifiers are adversarial skeptics over the unit's output (refute, not redo).
    assert "REFUTE-N VERIFIER" in script
    # Majority pass-rule reconciliation: a finding survives unless >= ceil(3/2)=2 refute.
    assert "U2_refute_count >= 2" in script
    assert "majority" in script
    # The verifier tier == the unit tier (R4): U2 is sonnet/high -> verifiers are too.
    assert 'label: "build verifier"' in script


def test_unanimous_verify_panel_requires_all_to_refute() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    first = units[0]  # U1, haiku/low
    assert isinstance(first, dict)
    first["verify"] = {"n": 3, "pass_rule": "unanimous"}
    spec = mod.ExecutionSpec.from_dict(data)
    script = mod.emit_workflow_script(spec)
    # Unanimous: a finding survives unless ALL N refute -> threshold == n == 3.
    assert "U1_refute_count >= 3" in script
    assert "unanimous" in script


def test_haiku_verify_panel_carries_budget_rider() -> None:
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    first = units[0]  # U1 is haiku/low -> verifiers are haiku too (R4) -> budget rider.
    assert isinstance(first, dict)
    first["verify"] = {"n": 3, "pass_rule": "majority"}
    spec = mod.ExecutionSpec.from_dict(data)
    script = mod.emit_workflow_script(spec)
    # The cheap-tier verifier carries the structuredoutput-budget rider.
    assert "BUDGET DISCIPLINE" in script
    # The verifier panel is at haiku tier (R4).
    assert 'label: "preflight verifier"' in script
    assert 'model: "haiku"' in script


# ---------------------------------------------------------------------------
# U2 integration: a layered spec with a verify panel emits a script whose
# substrings confirm parallel waves, the verifier panel, the meta block, and
# every unit's tier; the inline baseline of the SAME spec stays serial.
# ---------------------------------------------------------------------------


def test_layered_spec_with_verify_panel_full_emission() -> None:
    mod = _load()
    data = _layered_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    # Put a verify panel on the dependent unit C.
    third = units[2]
    assert isinstance(third, dict)
    third["verify"] = {"n": 3, "pass_rule": "majority"}
    spec = mod.ExecutionSpec.from_dict(data)
    script = mod.emit_workflow_script(spec)

    # meta block.
    assert "export const meta" in script
    # A parallel( wave for the independent A/B layer.
    assert "await parallel([" in script
    # N=3 verifier agent() calls for C's panel.
    assert "C_verdicts = await parallel([" in script
    assert script.count("() => agent(") == 3
    assert "C_refute_count >= 2" in script
    # Every unit's model/effort tier is present.
    assert 'model: "sonnet"' in script
    assert 'model: "opus"' in script
    assert 'effort: "high"' in script


def test_inline_baseline_of_layered_spec_stays_serial() -> None:
    mod = _load()
    data = _layered_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    third = units[2]
    assert isinstance(third, dict)
    third["verify"] = {"n": 3, "pass_rule": "majority"}
    spec = mod.ExecutionSpec.from_dict(data)
    baseline = mod.emit_inline_baseline(spec)
    # The off-host floor is serial: no parallel() and no agent() harness.
    assert "parallel(" not in baseline
    assert "agent(" not in baseline
    # It still preserves every unit's tier annotation.
    assert "[tier: sonnet/high]" in baseline
    assert "[tier: opus/high]" in baseline


def test_unit_ids_colliding_to_one_js_var_fail_validate() -> None:
    """Two distinct unit_ids that sanitize to the same JS identifier (- and . both -> _) would
    emit a duplicate `const` — a SyntaxError in the emitted ESM. validate() must reject the
    collision up front rather than emit unloadable JS."""
    mod = _load()
    data = {
        "name": "collide",
        "description": "var collision",
        "units": [
            {
                "unit_id": "a-b",
                "label": "alpha",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "x",
            },
            {
                "unit_id": "a.b",
                "label": "beta",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "y",
            },
        ],
    }
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError) as exc:
        spec.validate()
    msg = str(exc.value)
    assert "a-b" in msg and "a.b" in msg
    # emit() calls validate() first, so it fails there too (never emits unloadable JS).
    with pytest.raises(mod.SpecError):
        mod.emit_workflow_script(spec)


def test_parallel_and_verify_agents_each_carry_their_own_tier() -> None:
    """Mutation guard: each emitted agent (parallel-wave thunk AND refute-N verifier) must
    carry ITS OWN {model, effort} — not a same-tier sibling's. Two independent units with
    DISTINCT tiers land in one parallel wave; the haiku/low unit also runs a 3-verifier
    panel (verifiers inherit the unit tier per R4). Asserting exact COUNTS (not bare
    substring presence) means dropping the `model:`/`effort:` line from `_emit_thunk` or
    `_emit_verify_panel` changes a count and fails this test — closing the tautology the
    `in`-based tier checks left open."""
    mod = _load()
    data = {
        "name": "tier-fidelity",
        "description": "distinct per-agent tiers",
        "units": [
            {
                "unit_id": "alpha",
                "label": "alpha worker",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "do the first independent piece",
            },
            {
                "unit_id": "beta",
                "label": "beta worker",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "do the second independent piece",
                "verify": {"n": 3, "pass_rule": "majority"},
            },
        ],
    }
    spec = mod.ExecutionSpec.from_dict(data)
    script = mod.emit_workflow_script(spec)
    # alpha and beta are independent -> one parallel() wave of two thunks.
    assert "await parallel([" in script
    # beta (haiku/low) emits 1 thunk + 3 verifiers = 4 agents at haiku/low.
    assert script.count('model: "haiku"') == 4
    assert script.count('effort: "low"') == 4
    # alpha (opus/high) emits exactly 1 thunk; no other agent is opus/high here.
    assert script.count('model: "opus"') == 1
    assert script.count('effort: "high"') == 1
    # model/effort are emitted in pairs on every agent -> the two counts track together.
    assert script.count("model: ") == script.count("effort: ")


# ---------------------------------------------------------------------------
# U1 tests: files round-trip, back-compat, segmentation, dependencies collapse, no-mutation
# ---------------------------------------------------------------------------


def test_unit_files_round_trip() -> None:
    mod = _load()
    data = {
        "unit_id": "U1",
        "label": "grounding",
        "tier": {"model": "haiku", "effort": "low"},
        "prompt": "run preflight",
        "files": ["plugins/saga/scripts/execution_spec.py", "tests/test_workflow_emitter.py"],
    }
    unit = mod.Unit.from_dict(data)
    assert unit.files == [
        "plugins/saga/scripts/execution_spec.py",
        "tests/test_workflow_emitter.py",
    ]

    # Round-trip
    dumped = unit.to_dict()
    assert dumped["files"] == [
        "plugins/saga/scripts/execution_spec.py",
        "tests/test_workflow_emitter.py",
    ]
    rebuilt = mod.Unit.from_dict(dumped)
    assert rebuilt.files == unit.files


def test_unit_no_files_back_compat() -> None:
    mod = _load()
    data = {
        "unit_id": "U1",
        "label": "grounding",
        "tier": {"model": "haiku", "effort": "low"},
        "prompt": "run preflight",
        # "files" is missing
    }
    unit = mod.Unit.from_dict(data)
    assert unit.files == []

    # Round-trip
    dumped = unit.to_dict()
    assert dumped["files"] == []
    rebuilt = mod.Unit.from_dict(dumped)
    assert rebuilt.files == []


def test_segment_units_grouping_and_boundaries() -> None:
    mod = _load()
    data = {
        "name": "segment-test",
        "description": "testing segmentation rules",
        "units": [
            # Two contiguous same plugin directory -> one segment ("worker-saga")
            {
                "unit_id": "U1",
                "label": "saga unit 1",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "saga-1",
                "files": ["plugins/saga/scripts/execution_spec.py"],
            },
            {
                "unit_id": "U2",
                "label": "saga unit 2",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "saga-2",
                "files": ["plugins/saga/scripts/team_emitter.py"],
            },
            # Change key to a different plugin directory -> opens a new segment ("worker-tests")
            {
                "unit_id": "U3",
                "label": "tests unit",
                "tier": {"model": "sonnet", "effort": "medium"},
                "prompt": "test-1",
                "files": ["tests/test_workflow_emitter.py"],
            },
            # Non-contiguous return to saga key -> opens a new segment ("worker-saga-2")
            {
                "unit_id": "U4",
                "label": "saga unit 3",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "saga-3",
                "files": ["plugins/saga/scripts/some_other.py"],
            },
            # Empty files unit -> key "" -> base_id "worker"
            {
                "unit_id": "U5",
                "label": "empty files unit",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "empty",
                "files": [],
            },
        ],
    }
    spec = mod.ExecutionSpec.from_dict(data)
    segments = mod.segment_units(spec)

    # We expect 4 segments:
    # 1. worker-saga with U1, U2
    # 2. worker-tests with U3
    # 3. worker-saga-2 with U4
    # 4. worker with U5
    assert len(segments) == 4

    assert segments[0].resident_id == "worker-saga"
    assert segments[0].unit_ids == ["U1", "U2"]

    assert segments[1].resident_id == "worker-tests"
    assert segments[1].unit_ids == ["U3"]

    assert segments[2].resident_id == "worker-saga-2"
    assert segments[2].unit_ids == ["U4"]

    assert segments[3].resident_id == "worker"
    assert segments[3].unit_ids == ["U5"]


def test_segment_units_tier_upgrade_only_max() -> None:
    mod = _load()

    # Test model axis: haiku + opus -> opus (at low effort)
    data_model = {
        "name": "tier-model",
        "description": "test model axis max",
        "units": [
            {
                "unit_id": "U1",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "u1",
                "files": ["plugins/saga/a.py"],
            },
            {
                "unit_id": "U2",
                "tier": {"model": "opus", "effort": "low"},
                "prompt": "u2",
                "files": ["plugins/saga/b.py"],
            },
        ],
    }
    spec_model = mod.ExecutionSpec.from_dict(data_model)
    segs_model = mod.segment_units(spec_model)
    assert len(segs_model) == 1
    assert segs_model[0].tier.model == "opus"
    assert segs_model[0].tier.effort == "low"

    # Test effort axis: low + high -> high (at haiku model)
    data_effort = {
        "name": "tier-effort",
        "description": "test effort axis max",
        "units": [
            {
                "unit_id": "U1",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "u1",
                "files": ["plugins/saga/a.py"],
            },
            {
                "unit_id": "U2",
                "tier": {"model": "haiku", "effort": "high"},
                "prompt": "u2",
                "files": ["plugins/saga/b.py"],
            },
        ],
    }
    spec_effort = mod.ExecutionSpec.from_dict(data_effort)
    segs_effort = mod.segment_units(spec_effort)
    assert len(segs_effort) == 1
    assert segs_effort[0].tier.model == "haiku"
    assert segs_effort[0].tier.effort == "high"

    # Test both axes together: {haiku, low} + {opus, high} -> {opus, high}
    data_both = {
        "name": "tier-both",
        "description": "test both axes max",
        "units": [
            {
                "unit_id": "U1",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "u1",
                "files": ["plugins/saga/a.py"],
            },
            {
                "unit_id": "U2",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "u2",
                "files": ["plugins/saga/b.py"],
            },
        ],
    }
    spec_both = mod.ExecutionSpec.from_dict(data_both)
    segs_both = mod.segment_units(spec_both)
    assert len(segs_both) == 1
    assert segs_both[0].tier.model == "opus"
    assert segs_both[0].tier.effort == "high"


def test_segment_units_dependencies_collapse() -> None:
    mod = _load()
    data = {
        "name": "dependencies-collapse",
        "description": "testing collapse of unit dependencies into segment dependencies",
        "units": [
            # Segment 1: worker-saga (U1, U2)
            {
                "unit_id": "U1",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "u1",
                "files": ["plugins/saga/a.py"],
            },
            {
                "unit_id": "U2",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "u2",
                "files": ["plugins/saga/b.py"],
                "depends_on": ["U1"],  # intra-segment dependency -> should be dropped
            },
            # Segment 2: worker-tests (U3)
            {
                "unit_id": "U3",
                "tier": {"model": "sonnet", "effort": "medium"},
                "prompt": "u3",
                "files": ["tests/test_a.py"],
                "depends_on": [
                    "U1",
                    "U2",
                ],  # cross-segment dependencies from worker-saga -> collapse to worker-saga
            },
            # Segment 3: worker-other (U4)
            {
                "unit_id": "U4",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "u4",
                "files": ["plugins/other/a.py"],
                "depends_on": ["U3", "U2"],  # cross-segment: worker-tests, worker-saga
            },
        ],
    }
    spec = mod.ExecutionSpec.from_dict(data)
    segments = mod.segment_units(spec)

    assert len(segments) == 3

    # Segment 1: worker-saga has no dependencies
    assert segments[0].resident_id == "worker-saga"
    assert segments[0].depends_on == []

    # Segment 2: worker-tests depends on worker-saga (deduplicated)
    assert segments[1].resident_id == "worker-tests"
    assert segments[1].depends_on == ["worker-saga"]

    # Segment 3: worker-other depends on worker-tests and worker-saga (in order of first encounter)
    assert segments[2].resident_id == "worker-other"
    assert segments[2].depends_on == ["worker-tests", "worker-saga"]


def test_segment_units_does_not_mutate_input_spec() -> None:
    mod = _load()
    data = {
        "name": "no-mutation",
        "description": "testing no mutation of spec",
        "units": [
            {
                "unit_id": "U1",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "u1",
                "files": ["plugins/saga/a.py"],
            },
            {
                "unit_id": "U2",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "u2",
                "files": ["plugins/saga/b.py"],
                "depends_on": ["U1"],
            },
        ],
    }
    spec = mod.ExecutionSpec.from_dict(data)

    # Save representation before calling segment_units
    before_dict = spec.to_dict()

    # Call segment_units
    _ = mod.segment_units(spec)

    # Save representation after calling segment_units
    after_dict = spec.to_dict()

    # Assert they are equal
    assert before_dict == after_dict


# ---------------------------------------------------------------------------
# U2: completeness-gate guard emission tests.
# ---------------------------------------------------------------------------


def test_emitted_null_check() -> None:
    """Verify that:
    - emitted JS contains the __gate helper (exactly once).
    - a guard call is emitted after EVERY unit-result agent() site.
    - NO guard after the verify-panel's verifier agents.
    - the guard HALTS on null (the emitted code throws, not pass-through).
    - a fan-out unit emits the count-reconcile guard arg.
    - only `returns`-bearing units emit the manifest guard arg.
    - a no-contract (prose/side-effect) unit emits the presence guard with expectsOutput false.
    """
    mod = _load()

    # We construct a spec dictionary containing:
    # U1: returns-bearing (schema) unit -> should emit returns guard arg
    # U2: no-contract unit (prose/side-effect) -> should emit expectsOutput false
    # U3: fan-out unit with targets -> should emit count-reconcile guard arg
    # U4: unit with verify panel -> should NOT emit guard after verify verifier agents
    # U5, U6: independent units in a parallel layer to test multi-unit parallel guards
    data = {
        "name": "completeness-gate-test",
        "description": "test completeness gates",
        "repo": "/tmp/repo",
        "units": [
            {
                "unit_id": "U1",
                "label": "schema-unit",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "prompt 1",
                "returns": ["key_a", "key_b"],
            },
            {
                "unit_id": "U2",
                "label": "prose-unit",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "prompt 2",
                "depends_on": ["U1"],
            },
            {
                "unit_id": "U3",
                "label": "fan-out-unit",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "prompt 3",
                "depends_on": ["U2"],
                "fanout": True,
                "targets": ["tgt1", "tgt2"],
            },
            {
                "unit_id": "U4",
                "label": "verify-unit",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "prompt 4",
                "depends_on": ["U3"],
                "verify": {"n": 3, "pass_rule": "majority"},
            },
            {
                "unit_id": "U5",
                "label": "parallel-1",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "prompt 5",
                "depends_on": ["U4"],
            },
            {
                "unit_id": "U6",
                "label": "parallel-2",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "prompt 6",
                "depends_on": ["U4"],
                "returns": ["par_ret"],
            },
        ],
    }

    spec = mod.ExecutionSpec.from_dict(data)
    script = mod.emit_workflow_script(spec)

    # 1. Helper __gate is defined exactly once in the preamble
    assert script.count("function __gate(result, opts)") == 1

    # 2. A guard call is emitted after EVERY unit-result agent() site:
    assert "__gate(U1, {" in script
    assert "__gate(U2, {" in script
    assert "__gate(U3, {" in script
    assert "__gate(U4, {" in script
    assert "__gate(U5, {" in script
    assert "__gate(U6, {" in script

    # 3. NO guard after the verify-panel's verifier agents.
    assert "__gate(U4_verdicts" not in script

    # 4. The guard HALTS on null (emitted code throws).
    assert "throw new Error" in script

    # 5. A fan-out unit (U3) emits the count-reconcile guard arg (targets count is 2).
    assert "targets: 2" in script

    # 6. Only returns-bearing units emit the manifest guard arg.
    assert 'returns: ["key_a", "key_b"]' in script
    u2_line = [line for line in script.splitlines() if "__gate(U2" in line][0]
    assert "returns:" not in u2_line

    # 7. A no-contract (prose/side-effect) unit (U2, U5) emits the presence guard with expectsOutput false.
    assert "expectsOutput: false" in u2_line

    u5_line = [line for line in script.splitlines() if "__gate(U5" in line][0]
    assert "expectsOutput: false" in u5_line

    # Check that schema-bearing U1 has expectsOutput: true
    u1_line = [line for line in script.splitlines() if "__gate(U1" in line][0]
    assert "expectsOutput: true" in u1_line


# ---------------------------------------------------------------------------
# U3: Verify panel iteration cap + typed verifier-disagreement tests.
# ---------------------------------------------------------------------------


def test_refuted_panel_emits_verifier_disagreement_halt() -> None:
    """A refuted panel emits a verifier-disagreement throw/halt, NOT a log-and-continue."""
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    second = units[1]
    assert isinstance(second, dict)
    second["verify"] = {"n": 3, "pass_rule": "majority"}

    spec = mod.ExecutionSpec.from_dict(data)
    script = mod.emit_workflow_script(spec)

    assert "throw new Error" in script
    assert "verifier-disagreement" in script
    assert "U2_refute_count" in script
    # It must throw verifier-disagreement and NOT just log and continue
    assert "log(" not in script or "log(" in script and "verifier-disagreement" in script
    assert "review before relying on it" not in script


def test_iterate_to_consensus_emits_loop() -> None:
    """iterate_to_consensus=True emits a re-run loop bounded by max_iterations."""
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    second = units[1]
    assert isinstance(second, dict)
    second["verify"] = {
        "n": 3,
        "pass_rule": "majority",
        "iterate_to_consensus": True,
        "max_iterations": 4,
    }

    spec = mod.ExecutionSpec.from_dict(data)
    script = mod.emit_workflow_script(spec)

    # Check that a loop is emitted
    assert "for (let iter = 1; iter <= 4; iter++)" in script
    assert "iter === 4" in script
    assert "verifier-disagreement" in script
    # Inside the loop, it should call agent and the gate
    assert "U2 = await agent(" in script
    assert "__gate(U2, {" in script
    # The verdicts parallel wave should be inside the loop
    assert "const verdicts = await parallel([" in script


def test_parallel_iterate_to_consensus_emits_loop_in_thunk() -> None:
    """iterate_to_consensus=True in a parallel layer emits a loop inside the thunk."""
    mod = _load()
    data = _layered_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    # A and B are independent. Give B verify iterate_to_consensus = True.
    first = units[1]  # B
    assert isinstance(first, dict)
    first["verify"] = {
        "n": 3,
        "pass_rule": "unanimous",
        "iterate_to_consensus": True,
        "max_iterations": 2,
    }

    spec = mod.ExecutionSpec.from_dict(data)
    script = mod.emit_workflow_script(spec)

    # Check that the loop is emitted inside the parallel wave's thunk
    assert "async () => {" in script
    assert "for (let iter = 1; iter <= 2; iter++)" in script
    assert "iter === 2" in script
    assert "result = await agent(" in script
    assert "__gate(result, {" in script
    # The verifier panel should run within the thunk too
    assert "const verdicts = await parallel([" in script
    # It should return result from the thunk
    assert "return result" in script


def test_max_iterations_invalid_raises_spec_error() -> None:
    """max_iterations < 1 raises SpecError at ExecutionSpec.from_dict / validate()."""
    mod = _load()
    data = _valid_spec_dict()
    units = data["units"]
    assert isinstance(units, list)
    second = units[1]
    assert isinstance(second, dict)

    # Test < 1 raises SpecError during validate
    second["verify"] = {"n": 3, "pass_rule": "majority", "max_iterations": 0}
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError) as exc:
        spec.validate()
    assert "max_iterations" in str(exc.value)

    # Test negative raises SpecError during validate
    second["verify"] = {"n": 3, "pass_rule": "majority", "max_iterations": -5}
    spec = mod.ExecutionSpec.from_dict(data)
    with pytest.raises(mod.SpecError):
        spec.validate()

    # Test non-integer raises SpecError during from_dict
    second["verify"] = {"n": 3, "pass_rule": "majority", "max_iterations": "invalid"}
    with pytest.raises(mod.SpecError) as exc:
        mod.ExecutionSpec.from_dict(data)
    assert "integer" in str(exc.value)


def test_no_verify_round_trips_unchanged() -> None:
    """A unit with NO verify round-trips unchanged (no verifier-disagreement code)."""
    mod = _load()
    spec = mod.ExecutionSpec.from_dict(_valid_spec_dict())
    script = mod.emit_workflow_script(spec)

    assert "verifier-disagreement" not in script
    assert "U1_refuted" not in script
    assert "U2_refuted" not in script
    assert "U3_refuted" not in script


def test_verify_fields_round_trip() -> None:
    """Verify.from_dict / to_dict round-trip the two new fields."""
    mod = _load()
    data = {
        "n": 5,
        "pass_rule": "majority",
        "iterate_to_consensus": True,
        "max_iterations": 10,
    }
    verify = mod.Verify.from_dict(data, "test")
    assert verify.n == 5
    assert verify.pass_rule == "majority"
    assert verify.iterate_to_consensus is True
    assert verify.max_iterations == 10

    serialized = verify.to_dict()
    assert serialized["n"] == 5
    assert serialized["pass_rule"] == "majority"
    assert serialized["iterate_to_consensus"] is True
    assert serialized["max_iterations"] == 10
