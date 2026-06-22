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


# ---------------------------------------------------------------------------
# operator_choice provenance guard at SAVE time (U3 — R13/R14/R15)
#
# operator_choice = the authoritative operator pick; mode = the effective backend.
# They diverge legitimately ONLY on a recorded capability downgrade. A mode !=
# operator_choice tick with an EMPTY orchestration_downgrade is the issue-38 shape
# (mode masquerading as a choice the operator never made) and is rejected at save().
# A recommendation override (recommended-vs-operator_choice) is a SEPARATE pair and
# is NOT guarded here.
# ---------------------------------------------------------------------------


def test_normal_save_with_derived_operator_choice_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy path — a plain --orchestration-mode save (operator_choice derives equal to
    mode) is accepted; the derived operator_choice matches the mode."""
    saga_mod = _load("saga.py")
    monkeypatch.chdir(tmp_path)
    rc = saga_mod.main(
        [
            "save",
            "--kind",
            "task",
            "--id",
            "happy-degrade",
            "--orchestration-mode",
            "cc-workflows-ultracode",
        ]
    )
    assert rc == 0
    restored = saga_mod.restore(tmp_path, "task-happy-degrade")
    assert restored is not None
    assert restored.orchestration_mode == "cc-workflows-ultracode"
    assert restored.orchestration_operator_choice == "cc-workflows-ultracode"


def test_explicit_degrade_with_downgrade_note_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Edge — an explicit degrade (mode=inline, operator_choice=cc-workflows-ultracode,
    NON-EMPTY downgrade) is accepted and records the provenance: the effective backend,
    the operator's true pick, and the downgrade reason all persist."""
    saga_mod = _load("saga.py")
    monkeypatch.chdir(tmp_path)
    note = "Downgraded cc-workflows-ultracode -> inline: Workflow tool unavailable off-host."
    rc = saga_mod.main(
        [
            "save",
            "--kind",
            "task",
            "--id",
            "degrade-ok",
            "--orchestration-mode",
            "inline",
            "--orchestration-operator-choice",
            "cc-workflows-ultracode",
            "--orchestration-downgrade",
            note,
        ]
    )
    assert rc == 0
    restored = saga_mod.restore(tmp_path, "task-degrade-ok")
    assert restored is not None
    assert restored.orchestration_mode == "inline"
    assert restored.orchestration_operator_choice == "cc-workflows-ultracode"
    assert restored.orchestration_downgrade == note


def test_mode_masquerading_as_choice_without_downgrade_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Error — the issue-38 shape: mode=cc-workflows-ultracode, operator_choice=inline,
    EMPTY downgrade. The effective backend differs from the operator's pick with no
    recorded reason → non-zero exit and a clear message; nothing is persisted."""
    saga_mod = _load("saga.py")
    monkeypatch.chdir(tmp_path)
    rc = saga_mod.main(
        [
            "save",
            "--kind",
            "task",
            "--id",
            "issue-38-shape",
            "--orchestration-mode",
            "cc-workflows-ultracode",
            "--orchestration-operator-choice",
            "inline",
        ]
    )
    assert rc != 0
    err = capsys.readouterr().err
    assert "orchestration_mode" in err
    assert "orchestration_operator_choice" in err
    assert "downgrade" in err.lower()
    # Nothing was persisted.
    assert saga_mod.restore(tmp_path, "task-issue-38-shape") is None


def test_provenance_guard_raises_in_save_not_in_render_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard is SAVE-scoped: an unsaved render→parse round-trip with
    operator_choice != mode (and no downgrade) stays valid; only save() rejects it."""
    saga_mod = _load("saga.py")
    saga = saga_mod.Saga(
        saga_id="task-rp",
        kind="task",
        id="rp",
        orchestration_mode="cc-workflows-ultracode",
        orchestration_operator_choice="inline",
    )
    # render/parse never raises.
    reloaded = saga_mod.parse_envelope(saga_mod.render_envelope(saga))
    assert reloaded.orchestration_operator_choice == "inline"
    # save() rejects the same shape.
    monkeypatch.chdir(tmp_path)
    with pytest.raises(saga_mod.SagaSaveError):
        saga_mod.save(tmp_path, saga)


def test_carried_downgrade_note_does_not_launder_a_fresh_issue38_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression — a legit degrade tick records a downgrade note; a LATER issue-38-shape
    tick (mode=cc-workflows-ultracode, operator_choice=inline, NO new note) must STILL be
    rejected. _merge carries the prior note forward as a scalar, but a stale note from a
    DIFFERENT divergence cannot justify a fresh, opposite one (the guard validates this
    tick's assertion, not the laundered carry-forward)."""
    saga_mod = _load("saga.py")
    monkeypatch.chdir(tmp_path)
    note = "Downgraded cc-workflows-ultracode -> inline: Workflow tool unavailable off-host."
    # Tick 1: a legitimate degrade — accepted, note recorded.
    rc1 = saga_mod.main(
        [
            "save",
            "--kind",
            "task",
            "--id",
            "launder",
            "--orchestration-mode",
            "inline",
            "--orchestration-operator-choice",
            "cc-workflows-ultracode",
            "--orchestration-downgrade",
            note,
        ]
    )
    assert rc1 == 0
    # Tick 2: the issue-38 shape with NO fresh downgrade — the carried note must not launder it.
    rc2 = saga_mod.main(
        [
            "save",
            "--kind",
            "task",
            "--id",
            "launder",
            "--orchestration-mode",
            "cc-workflows-ultracode",
            "--orchestration-operator-choice",
            "inline",
        ]
    )
    assert rc2 != 0
    err = capsys.readouterr().err
    assert "orchestration_mode" in err and "downgrade" in err.lower()
    # The rejected tick was not persisted: the saga still reflects tick 1's legit degrade.
    restored = saga_mod.restore(tmp_path, "task-launder")
    assert restored is not None
    assert restored.orchestration_mode == "inline"
    assert restored.orchestration_operator_choice == "cc-workflows-ultracode"


def test_partial_tick_introducing_divergence_via_carry_forward_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression — a partial tick that sets ONLY --orchestration-operator-choice (so the
    incoming mode defaults equal to it, but the prior tick's higher mode carries forward)
    produces a mode != operator_choice divergence in the merged saga with no note. The
    guard validates the merged state, so this asymmetric-carry-forward issue-38 shape is
    rejected even though the incoming tick alone looked self-consistent."""
    saga_mod = _load("saga.py")
    monkeypatch.chdir(tmp_path)
    # Tick 1: a clean cc-workflows-ultracode run (operator_choice derives equal, no divergence).
    rc1 = saga_mod.main(
        [
            "save",
            "--kind",
            "task",
            "--id",
            "partial",
            "--orchestration-mode",
            "cc-workflows-ultracode",
        ]
    )
    assert rc1 == 0
    # Tick 2: set ONLY operator_choice=inline. Incoming mode defaults to "inline" (== choice, no
    # incoming divergence), but merged carries mode=cc-workflows-ultracode forward -> divergence, no note.
    rc2 = saga_mod.main(
        ["save", "--kind", "task", "--id", "partial", "--orchestration-operator-choice", "inline"]
    )
    assert rc2 != 0
    restored = saga_mod.restore(tmp_path, "task-partial")
    assert restored is not None
    assert restored.orchestration_mode == "cc-workflows-ultracode"
    assert restored.orchestration_operator_choice == "cc-workflows-ultracode"


def test_progress_tick_without_orchestration_args_carries_choice_forward(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (no false positive) — after a cc-workflows-ultracode tick, a plain progress
    save that passes NO orchestration args must SUCCEED: mode and operator_choice both carry
    forward (not re-stamped to "inline"), so the guard sees no divergence. Without this, every
    multi-tick /work or /loop run on a non-inline saga would wrongly reject its own progress
    ticks (the auto-derive must not fabricate an operator_choice on a tick that asserts none)."""
    saga_mod = _load("saga.py")
    monkeypatch.chdir(tmp_path)
    # Tick 1: explicit cc-workflows-ultracode.
    rc1 = saga_mod.main(
        [
            "save",
            "--kind",
            "task",
            "--id",
            "progress",
            "--orchestration-mode",
            "cc-workflows-ultracode",
            "--lifecycle-phase",
            "work",
            "--phase",
            "1",
        ]
    )
    assert rc1 == 0
    # Tick 2: a plain phase-progress save, NO orchestration args at all.
    rc2 = saga_mod.main(
        [
            "save",
            "--kind",
            "task",
            "--id",
            "progress",
            "--lifecycle-phase",
            "work",
            "--phase",
            "2",
            "--phase-status",
            "complete",
        ]
    )
    assert rc2 == 0
    restored = saga_mod.restore(tmp_path, "task-progress")
    assert restored is not None
    # The real backend choice carried forward, not re-stamped to inline.
    assert restored.orchestration_mode == "cc-workflows-ultracode"
    assert restored.orchestration_operator_choice == "cc-workflows-ultracode"
    assert restored.phase == 2


def test_upgrade_masquerade_with_a_note_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Error — a divergence where the effective mode is a RICHER tier than the operator's pick
    (mode=cc-workflows-ultracode, operator_choice=inline) is an UPGRADE, not a capability
    downgrade; a downgrade note must not justify it. The note is direction-checked: only
    mode tier < operator_choice tier is a legitimate downgrade."""
    saga_mod = _load("saga.py")
    monkeypatch.chdir(tmp_path)
    rc = saga_mod.main(
        [
            "save",
            "--kind",
            "task",
            "--id",
            "upgrade",
            "--orchestration-mode",
            "cc-workflows-ultracode",
            "--orchestration-operator-choice",
            "inline",
            "--orchestration-downgrade",
            "bogus note claiming a downgrade",
        ]
    )
    assert rc != 0
    err = capsys.readouterr().err
    assert "RICHER" in err or "UPGRADE" in err
    assert saga_mod.restore(tmp_path, "task-upgrade") is None


def test_whitespace_only_downgrade_note_does_not_justify_divergence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Error — a blank/whitespace-only downgrade note is not a justification; a genuine-direction
    degrade (mode=inline < operator_choice=cc-workflows-ultracode) with a "   " note is still
    rejected (the note is stripped before the truthiness check)."""
    saga_mod = _load("saga.py")
    monkeypatch.chdir(tmp_path)
    rc = saga_mod.main(
        [
            "save",
            "--kind",
            "task",
            "--id",
            "blank-note",
            "--orchestration-mode",
            "inline",
            "--orchestration-operator-choice",
            "cc-workflows-ultracode",
            "--orchestration-downgrade",
            "   ",
        ]
    )
    assert rc != 0
    assert saga_mod.restore(tmp_path, "task-blank-note") is None


def test_genuine_downgrade_direction_with_a_real_note_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy — the legitimate degrade direction (effective mode a LOWER tier than the pick) with
    a real note is accepted, confirming the direction check doesn't reject valid downgrades."""
    saga_mod = _load("saga.py")
    monkeypatch.chdir(tmp_path)
    rc = saga_mod.main(
        [
            "save",
            "--kind",
            "task",
            "--id",
            "real-degrade",
            "--orchestration-mode",
            "team-execution",
            "--orchestration-operator-choice",
            "cc-workflows-ultracode",
            "--orchestration-downgrade",
            "Workflow tool unavailable; recompiled to team-execution.",
        ]
    )
    assert rc == 0
    restored = saga_mod.restore(tmp_path, "task-real-degrade")
    assert restored is not None
    assert restored.orchestration_mode == "team-execution"
    assert restored.orchestration_operator_choice == "cc-workflows-ultracode"
