"""Oracle tests for capability-portable degradation (U12, R11).

Every authored plan carries a runnable inline/serial baseline; on an off-host resume the
Workflow tool is re-checked, a one-line downgrade is surfaced, and ONLY the orchestration
tier recompiles down (unit specs + per-unit ``{model, effort}`` tiers preserved). The
downgrade is recorded on the saga.

AE3 is the load-bearing oracle: an off-host resume must DOWNGRADE WITH A NOTE — it must
NEVER error and NEVER silently run nothing. The tests asserting a runnable, non-empty
``to`` tier and that no input raises must not be loosened to "pass".
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"


def _load(script_name: str) -> ModuleType:
    path = SCRIPTS / script_name
    spec = importlib.util.spec_from_file_location(script_name.removesuffix(".py"), path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so `from __future__ import annotations` + dataclass field-type
    # resolution can look the module up (required on Python 3.14; harmless on 3.12).
    sys.modules[script_name.removesuffix(".py")] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def lifecycle() -> ModuleType:
    return _load("lifecycle_state.py")


@pytest.fixture
def es() -> ModuleType:
    return _load("execution_spec.py")


def _spec_dict() -> dict[str, object]:
    """A small valid spec spanning three distinct per-unit tiers (so tier-preservation
    across a recompile is observable)."""
    return {
        "name": "degrade-demo",
        "description": "capability-portable degradation demo",
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
                "label": "fan out",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "audit each target",
                "depends_on": ["U2"],
                "fanout": True,
                "targets": ["a", "b", "c"],
            },
        ],
    }


# ---------------------------------------------------------------------------
# recheck_orchestration_capability — the capability probe (R11)
# ---------------------------------------------------------------------------


def test_on_host_keeps_authored_tier_no_downgrade(lifecycle: ModuleType) -> None:
    """A capable host (Workflow tool available) keeps the authored dynamic-workflow tier."""
    result = lifecycle.recheck_orchestration_capability(
        orchestration_mode="cc-workflows-ultracode",
        workflow_available=True,
    )
    assert result["downgraded"] is False
    assert result["to"] == "cc-workflows-ultracode"
    assert result["note"] == ""


def test_off_host_downgrades_with_a_one_line_note(lifecycle: ModuleType) -> None:
    """AE3 — off-host resume of a dynamic-workflow plan DOWNGRADES with a surfaceable note."""
    result = lifecycle.recheck_orchestration_capability(
        orchestration_mode="cc-workflows-ultracode",
        workflow_available=False,
    )
    assert result["downgraded"] is True
    assert result["from"] == "cc-workflows-ultracode"
    # Recompiled DOWN to a host-portable tier (not the dynamic-workflow tier).
    assert result["to"] == "team-execution"
    assert result["to"] != "cc-workflows-ultracode"
    # The downgrade is SURFACED: a non-empty, single-line note.
    assert result["note"]
    assert "\n" not in result["note"]


def test_off_host_never_lands_on_an_unrunnable_or_empty_tier(lifecycle: ModuleType) -> None:
    """AE3 — the landing tier is NEVER empty and NEVER the host-dependent tier (never run
    nothing). Floor to inline if the requested fallback is itself host-dependent."""
    result = lifecycle.recheck_orchestration_capability(
        orchestration_mode="cc-workflows-ultracode",
        workflow_available=False,
        fallback_mode="cc-workflows-ultracode",  # a host-dependent (unavailable) fallback
    )
    assert result["downgraded"] is True
    assert result["to"] == "inline"  # floored to the always-runnable baseline
    assert result["to"]  # never empty


def test_inline_fallback_is_honored_when_requested(lifecycle: ModuleType) -> None:
    result = lifecycle.recheck_orchestration_capability(
        orchestration_mode="cc-workflows-ultracode",
        workflow_available=False,
        fallback_mode="inline",
    )
    assert result["downgraded"] is True
    assert result["to"] == "inline"


def test_team_execution_tier_is_host_portable_no_downgrade(lifecycle: ModuleType) -> None:
    """team-execution runs on any host, so an off-host resume of a team-execution plan is
    NOT a downgrade — it runs as authored."""
    result = lifecycle.recheck_orchestration_capability(
        orchestration_mode="team-execution",
        workflow_available=False,
    )
    assert result["downgraded"] is False
    assert result["to"] == "team-execution"
    assert result["note"] == ""


def test_inline_tier_off_host_is_a_noop(lifecycle: ModuleType) -> None:
    result = lifecycle.recheck_orchestration_capability(
        orchestration_mode="inline",
        workflow_available=False,
    )
    assert result["downgraded"] is False
    assert result["to"] == "inline"


def test_empty_or_unknown_mode_floors_to_inline_never_errors(lifecycle: ModuleType) -> None:
    """AE3 — an empty or unrecognized stored mode floors to the inline baseline rather than
    raising or returning nothing."""
    for mode in ("", "garbage-tier", "Inline", "WORKFLOW"):
        result = lifecycle.recheck_orchestration_capability(
            orchestration_mode=mode,
            workflow_available=False,
        )
        assert result["to"] == "inline"
        assert result["to"]  # never empty — never "run nothing"


@pytest.mark.parametrize("mode", ["cc-workflows-ultracode", "team-execution", "inline", "", "x"])
@pytest.mark.parametrize("available", [True, False])
def test_recheck_never_errors_and_always_returns_a_runnable_tier(
    lifecycle: ModuleType, mode: str, available: bool
) -> None:
    """AE3 sweep — across the full cross product, the probe never raises and ALWAYS names a
    runnable orchestration tier (one of the known tiers, never empty)."""
    result = lifecycle.recheck_orchestration_capability(
        orchestration_mode=mode,
        workflow_available=available,
    )
    assert result["to"] in lifecycle.ORCHESTRATION_TIERS
    assert isinstance(result["downgraded"], bool)
    assert "note" in result


def test_recheck_cli_emits_json(lifecycle: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    rc = lifecycle.main(
        [
            "recheck-capability",
            "--orchestration-mode",
            "cc-workflows-ultracode",
            "--no-workflow",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["downgraded"] is True
    assert payload["to"] == "team-execution"


# ---------------------------------------------------------------------------
# The recompile preserves unit specs + per-unit tiers (R11)
# ---------------------------------------------------------------------------


def test_recompile_to_inline_preserves_every_unit_and_its_tier(es: ModuleType) -> None:
    """R11 — recompiling DOWN to inline keeps every unit AND its per-unit {model, effort}
    tier; only the orchestration tier (dispatch shape) changes."""
    spec = es.ExecutionSpec.from_dict(_spec_dict())
    baseline = es.recompile_for_tier(spec, "inline")
    # Every unit survives.
    for unit in spec.units:
        assert unit.unit_id in baseline
        assert unit.label in baseline
        # The per-unit tier is preserved (rendered verbatim).
        assert f"{unit.tier.model}/{unit.tier.effort}" in baseline


def test_recompile_to_workflow_tier_emits_the_dynamic_script(es: ModuleType) -> None:
    spec = es.ExecutionSpec.from_dict(_spec_dict())
    out = es.recompile_for_tier(spec, "cc-workflows-ultracode")
    assert "await agent(" in out  # the dynamic harness, not the baseline
    # Per-unit tiers preserved in the dynamic emit too.
    assert '"opus"' in out and '"haiku"' in out and '"sonnet"' in out


def test_recompile_unknown_tier_floors_to_runnable_baseline(es: ModuleType) -> None:
    """AE3 — an unknown target tier still yields a runnable (non-empty) baseline, never an
    empty or un-runnable artifact."""
    spec = es.ExecutionSpec.from_dict(_spec_dict())
    out = es.recompile_for_tier(spec, "some-future-tier")
    assert out.strip()  # non-empty
    assert "U1" in out  # the units are present and runnable


def test_inline_baseline_is_host_independent_no_agent_harness(es: ModuleType) -> None:
    """The baseline is the always-runnable floor: it dispatches nothing in parallel and
    calls no agent() harness — it runs without the Workflow tool."""
    spec = es.ExecutionSpec.from_dict(_spec_dict())
    baseline = es.emit_inline_baseline(spec)
    assert "await agent(" not in baseline
    assert "serial" in baseline.lower()


def test_inline_baseline_enumerates_fanout_targets(es: ModuleType) -> None:
    """R10 carries into the baseline — fan-out targets are enumerated, never silently
    filtered, even in the serial floor."""
    spec = es.ExecutionSpec.from_dict(_spec_dict())
    baseline = es.emit_inline_baseline(spec)
    for target in ("a", "b", "c"):
        assert target in baseline
    assert "reconcile" in baseline.lower()


def test_inline_baseline_rejects_a_mis_built_spec(es: ModuleType) -> None:
    """A mis-built spec (R10 fan-out with no targets) has no valid baseline either —
    emit fails loudly rather than producing a silent-filter floor."""
    bad = _spec_dict()
    units = cast("list[dict[str, object]]", bad["units"])
    units[2]["targets"] = []  # fan-out with no enumerated targets
    spec = es.ExecutionSpec.from_dict(bad)
    with pytest.raises(es.SpecError):
        es.emit_inline_baseline(spec)


def test_baseline_cli_writes_a_file(es: ModuleType, tmp_path: Path) -> None:
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(_spec_dict()))
    out_file = tmp_path / "baseline.md"
    rc = es.main(["baseline", str(spec_file), "-o", str(out_file)])
    assert rc == 0
    body = out_file.read_text()
    assert "Inline/serial baseline" in body
    assert "U1" in body


# ---------------------------------------------------------------------------
# The downgrade is RECORDED on the saga (R11), backward-compatibly
# ---------------------------------------------------------------------------


def test_saga_records_the_downgrade_note(tmp_path: Path) -> None:
    saga_mod = _load("saga.py")
    note = "Downgraded cc-workflows-ultracode -> team-execution: Workflow tool unavailable."
    saga = saga_mod.Saga(
        saga_id="task-degrade",
        kind="task",
        id="degrade",
        orchestration_mode="team-execution",
        orchestration_downgrade=note,
    )
    text = saga_mod.render_envelope(saga)
    assert "orchestration_downgrade:" in text
    reloaded = saga_mod.parse_envelope(text)
    assert reloaded.orchestration_downgrade == note


def test_absent_downgrade_field_still_loads(tmp_path: Path) -> None:
    """Backward-compat — an older saga lacking the field parses with the "" default."""
    saga_mod = _load("saga.py")
    saga = saga_mod.Saga(saga_id="task-old", kind="task", id="old")
    text = saga_mod.render_envelope(saga)
    # Simulate an older file by stripping the new line entirely.
    stripped = "\n".join(
        line for line in text.splitlines() if not line.startswith("orchestration_downgrade:")
    )
    assert "orchestration_downgrade:" not in stripped
    reloaded = saga_mod.parse_envelope(stripped)
    assert reloaded.orchestration_downgrade == ""
