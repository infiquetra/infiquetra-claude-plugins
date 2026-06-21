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
