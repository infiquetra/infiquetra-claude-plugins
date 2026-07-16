"""Contract tests for Saga's serialized concurrency governor (#350)."""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType, ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "plugins" / "saga" / "scripts" / "execution_spec.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("execution_spec", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["execution_spec"] = module
    spec.loader.exec_module(module)
    return module


M = _load()


@pytest.fixture(autouse=True)
def _external_engine_preflight_is_deterministically_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        M.engine_resolver,
        "preflight",
        lambda *_args, **_kwargs: {"available": True, "reason": "test snapshot"},
    )


def _routing_snapshots() -> dict[str, object]:
    return {
        "routing_overlay": M.engine_overlay.EngineOverlay(),
        "routing_calibration": M.engine_calibration.CalibrationSignals(),
    }


def _unit(
    unit_id: str,
    *,
    model: str = "sonnet",
    effort: str = "high",
    read_only: bool = False,
    engine: str | None = None,
    capability: str | None = None,
    verify_n: int | None = None,
    verify_tier: dict[str, str] | None = None,
) -> dict[str, object]:
    unit: dict[str, object] = {
        "unit_id": unit_id,
        "label": unit_id,
        "tier": {"model": model, "effort": effort},
        "prompt": f"run {unit_id}",
    }
    if read_only:
        unit["sandbox"] = {
            "mutation_policy": "read-only",
            "workspace_isolation": "disposable-worktree",
        }
    if engine is not None:
        unit["engine"] = engine
    if capability is not None:
        unit["capability"] = capability
    if verify_n is not None:
        verify: dict[str, object] = {"n": verify_n, "pass_rule": "majority"}
        if verify_tier is not None:
            verify["tier"] = verify_tier
        unit["verify"] = verify
    return unit


def _spec(
    units: list[dict[str, object]],
    *,
    concurrency: dict[str, int] | None = None,
) -> Any:
    data: dict[str, object] = {
        "name": "concurrency-test",
        "description": "exercise bounded admission",
        "units": units,
    }
    if concurrency is not None:
        data["concurrency"] = concurrency
    return M.ExecutionSpec.from_dict(data)


def _governor_unit(
    *,
    unit_id: str = "unit",
    model: str = "sonnet",
    effort: str = "high",
    mutation_policy: str = "read-write",
    engine: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        unit_id=unit_id,
        tier=SimpleNamespace(model=model, effort=effort),
        sandbox=SimpleNamespace(mutation_policy=mutation_policy),
        engine=engine,
    )


def test_policy_defaults_and_closed_serialized_block() -> None:
    policy = M.ConcurrencyPolicy()
    assert policy.to_dict() == {
        "max_concurrent": 3,
        "readonly_max_concurrent": 4,
        "aggregate_max_concurrent": 7,
    }
    assert policy.aggregate_max_concurrent == M.VERIFY_N_CAP

    with pytest.raises(M.ConcurrencyPolicyError, match="unknown field"):
        M.ConcurrencyPolicy.from_dict({"max_concurrent": 3, "burst": 9})


@pytest.mark.parametrize(
    "data, message",
    [
        ({"max_concurrent": True}, "positive integer"),
        ({"max_concurrent": 0}, "positive integer"),
        (
            {"max_concurrent": 5, "readonly_max_concurrent": 4},
            "exceeds readonly_max_concurrent",
        ),
        (
            {"readonly_max_concurrent": 8, "aggregate_max_concurrent": 7},
            "exceeds aggregate_max_concurrent",
        ),
    ],
)
def test_policy_rejects_invalid_values(data: dict[str, object], message: str) -> None:
    with pytest.raises(M.ConcurrencyPolicyError, match=message):
        M.ConcurrencyPolicy.from_dict(data)


def test_execution_spec_absent_and_explicit_policy_round_trip() -> None:
    absent = _spec([_unit("U")])
    assert "concurrency" not in absent.to_dict()

    explicit = _spec(
        [_unit("U")],
        concurrency={
            "max_concurrent": 2,
            "readonly_max_concurrent": 5,
            "aggregate_max_concurrent": 6,
        },
    )
    assert explicit.to_dict()["concurrency"] == {
        "max_concurrent": 2,
        "readonly_max_concurrent": 5,
        "aggregate_max_concurrent": 6,
    }
    rebuilt = M.ExecutionSpec.from_dict(explicit.to_dict())
    assert rebuilt.concurrency == explicit.concurrency


def test_resolution_ladder_and_run_override_wins() -> None:
    policy = M.ConcurrencyPolicy(
        max_concurrent=2,
        readonly_max_concurrent=4,
        aggregate_max_concurrent=7,
    )
    unit = _governor_unit(engine="lane/one")

    resolved = M.concurrency_governor.resolve_concurrency(
        policy,
        [unit],
        environment={"SAGA_MAX_CONCURRENT": "3"},
        lane_limits={"lane/one": 2},
        run_override=5,
    )

    assert resolved.width == 5
    assert resolved.source == "run"


def test_readonly_lift_precedes_tier_weighting_and_requires_explicit_evidence() -> None:
    policy = M.ConcurrencyPolicy()
    explicit = _governor_unit(mutation_policy="read-only")
    absent = _governor_unit()
    absent.sandbox = None

    readonly = M.concurrency_governor.resolve_concurrency(policy, [explicit], environment={})
    mixed = M.concurrency_governor.resolve_concurrency(
        policy,
        [explicit, absent],
        environment={},
    )

    assert readonly.width == 4
    assert mixed.width == 3


def test_tier_weighted_admission_uses_shared_cost_ordering() -> None:
    policy = M.ConcurrencyPolicy()
    cheap = M.concurrency_governor.resolve_concurrency(
        policy,
        [_governor_unit(model="haiku", effort="low")],
        environment={},
    )
    baseline = M.concurrency_governor.resolve_concurrency(
        policy,
        [_governor_unit()],
        environment={},
    )
    expensive = M.concurrency_governor.resolve_concurrency(
        policy,
        [_governor_unit(model="opus", effort="high")],
        environment={},
    )

    assert cheap.width == baseline.width > expensive.width
    assert cheap.width == policy.max_concurrent


def test_uniform_and_policy_chunkers_share_one_stable_primitive() -> None:
    assert "_bounded_ordered_chunks(" in inspect.getsource(M.concurrency_governor.ordered_chunks)
    assert "_bounded_ordered_chunks(" in inspect.getsource(
        M.concurrency_governor.ordered_policy_chunks
    )


def test_tier_weighting_never_widens_selected_readonly_ceiling() -> None:
    policy = M.ConcurrencyPolicy()
    cheap_readonly = M.concurrency_governor.resolve_concurrency(
        policy,
        [_governor_unit(model="haiku", effort="low", mutation_policy="read-only")],
        environment={},
    )

    assert cheap_readonly.width == policy.readonly_max_concurrent


def test_lane_override_applies_only_to_matching_engine_unit() -> None:
    policy = M.ConcurrencyPolicy()
    engine_unit = _governor_unit(engine="lane/one")
    local_unit = _governor_unit()

    engine_result = M.concurrency_governor.resolve_concurrency(
        policy,
        [engine_unit],
        environment={},
        lane_limits={"lane/one": 1},
    )
    local_result = M.concurrency_governor.resolve_concurrency(
        policy,
        [local_unit],
        environment={},
        lane_limits={"lane/one": 1},
    )

    assert engine_result.width == 1
    assert engine_result.source == "lane"
    assert local_result.width == 3


def test_resolved_lane_assignment_applies_to_capability_routed_unit() -> None:
    policy = M.ConcurrencyPolicy()
    unit = _governor_unit(unit_id="C0")

    result = M.concurrency_governor.resolve_concurrency(
        policy,
        [unit],
        environment={},
        lane_limits={"lane/selected": 1},
        lane_assignments={"C0": "lane/selected"},
    )

    assert result.width == 1
    assert result.source == "lane"


@pytest.mark.parametrize(
    ("lane_limit", "expected_chunks"),
    [
        (5, [["E0", "E1", "L0", "L1", "L2"], ["L3"]]),
        (1, [["E0"], ["E1", "L0", "L1", "L2"], ["L3"]]),
    ],
)
def test_mixed_layer_keeps_ordinary_and_exact_lane_limits(
    monkeypatch: pytest.MonkeyPatch,
    lane_limit: int,
    expected_chunks: list[list[str]],
) -> None:
    engine = "codex/gpt-5.5-xhigh"
    spec = _spec(
        [
            _unit("E0", engine=engine),
            _unit("E1", engine=engine),
            _unit("L0"),
            _unit("L1"),
            _unit("L2"),
            _unit("L3"),
        ]
    )
    monkeypatch.setattr(
        M,
        "_engine_lane_context",
        lambda units, _routing_context: (
            {engine: lane_limit},
            {unit.unit_id: engine for unit in units if unit.engine == engine},
        ),
    )

    chunks = M.concurrency_chunks(spec, spec.units, environment={})

    assert [[unit.unit_id for unit in chunk] for chunk in chunks] == expected_chunks
    assert all(
        sum(unit.engine is None for unit in chunk) <= M.ConcurrencyPolicy().max_concurrent
        for chunk in chunks
    )
    assert all(sum(unit.engine == engine for unit in chunk) <= lane_limit for chunk in chunks)


def test_exact_lane_can_widen_above_spec_default(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = "codex/gpt-5.5-xhigh"
    governor_units = [_governor_unit(unit_id=f"E{index}", engine=engine) for index in range(5)]
    result = M.concurrency_governor.resolve_concurrency(
        M.ConcurrencyPolicy(max_concurrent=2),
        governor_units,
        environment={"SAGA_MAX_CONCURRENT": "1"},
        lane_limits={engine: 5},
    )
    assert result.width == 5
    assert result.source == "lane"

    spec = _spec(
        [_unit(f"E{index}", engine=engine) for index in range(5)],
        concurrency={
            "max_concurrent": 2,
            "readonly_max_concurrent": 3,
            "aggregate_max_concurrent": 7,
        },
    )
    monkeypatch.setattr(
        M,
        "_engine_lane_context",
        lambda units, _routing_context: (
            {engine: 5},
            {unit.unit_id: engine for unit in units},
        ),
    )

    chunks = M.concurrency_chunks(
        spec,
        spec.units,
        environment={"SAGA_MAX_CONCURRENT": "1"},
    )
    assert [[unit.unit_id for unit in chunk] for chunk in chunks] == [
        ["E0", "E1", "E2", "E3", "E4"]
    ]


def test_low_lane_limit_does_not_serialize_ordinary_units(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = "codex/gpt-5.5-xhigh"
    spec = _spec(
        [
            _unit("E0", engine=engine),
            _unit("L0"),
            _unit("E1", engine=engine),
            _unit("L1"),
        ]
    )
    monkeypatch.setattr(
        M,
        "_engine_lane_context",
        lambda units, _routing_context: (
            {engine: 1},
            {unit.unit_id: engine for unit in units if unit.engine == engine},
        ),
    )

    script = M.emit_workflow_script(spec, environment={})

    assert "const [E0, L0] = await parallel([" in script
    assert "const [E1, L1] = await parallel([" in script


def test_registry_lane_limit_flows_through_emitter_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = "codex/gpt-5.5-xhigh"
    registry = M._engine_registry_path().read_text(encoding="utf-8")
    needle = "  - engine_id: codex\n    variant: gpt-5.5-xhigh\n"
    assert needle in registry
    registry_path = tmp_path / "engine-registry.yaml"
    registry_path.write_text(
        registry.replace(needle, needle + "    max_concurrent: 1\n", 1),
        encoding="utf-8",
    )
    monkeypatch.setattr(M, "_engine_registry_path", lambda: registry_path)
    spec = _spec(
        [
            _unit("E0", engine=engine),
            _unit("L0"),
            _unit("E1", engine=engine),
            _unit("L1"),
        ]
    )

    script = M.emit_workflow_script(spec, environment={"SAGA_MAX_CONCURRENT": "3"})

    assert "const [E0, L0] = await parallel([" in script
    assert "const [E1, L1] = await parallel([" in script


def test_exact_and_capability_selectors_share_selected_registry_lane(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = "codex/gpt-5.6-sol-xhigh"
    registry = M._engine_registry_path().read_text(encoding="utf-8")
    needle = "  - engine_id: codex\n    variant: gpt-5.6-sol-xhigh\n"
    assert needle in registry
    registry_path = tmp_path / "engine-registry.yaml"
    registry_path.write_text(
        registry.replace(needle, needle + "    max_concurrent: 1\n", 1),
        encoding="utf-8",
    )
    monkeypatch.setattr(M, "_engine_registry_path", lambda: registry_path)
    spec = _spec(
        [
            _unit("E0", engine=engine),
            _unit("C0", capability="code-generation"),
            _unit("L0"),
        ]
    )

    chunks = M.concurrency_chunks(
        spec,
        spec.units,
        environment={},
        **_routing_snapshots(),
    )

    assert [[unit.unit_id for unit in chunk] for chunk in chunks] == [
        ["E0"],
        ["C0", "L0"],
    ]


@pytest.mark.parametrize("selection_source", ["overlay", "calibration"])
def test_capability_snapshot_selects_exact_capped_lane_for_admission_and_runtime(
    selection_source: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capability = "code-generation"
    selected = "codex/gpt-5.6-terra-xhigh"
    registry = M._engine_registry_path().read_text(encoding="utf-8")
    needle = "  - engine_id: codex\n    variant: gpt-5.6-terra-xhigh\n"
    assert needle in registry
    registry_path = tmp_path / "engine-registry.yaml"
    registry_path.write_text(
        registry.replace(needle, needle + "    max_concurrent: 1\n", 1),
        encoding="utf-8",
    )
    monkeypatch.setattr(M, "_engine_registry_path", lambda: registry_path)
    overlay = M.engine_overlay.EngineOverlay()
    calibration = M.engine_calibration.CalibrationSignals()
    if selection_source == "overlay":
        overlay = M.engine_overlay.EngineOverlay(pins={capability: selected})
    else:
        calibration = M.engine_calibration.CalibrationSignals(elo={(selected, capability): 9000.0})
    snapshots = {
        "routing_overlay": overlay,
        "routing_calibration": calibration,
    }
    spec = _spec(
        [
            _unit("C0", capability=capability),
            _unit("C1", capability=capability),
            _unit("L0"),
        ]
    )

    chunks = M.concurrency_chunks(spec, spec.units, environment={}, **snapshots)
    script = M.emit_workflow_script(spec, environment={}, **snapshots)

    assert all(sum(unit.capability == capability for unit in chunk) <= 1 for chunk in chunks)
    assert script.count(f'engine: "{selected}"') == 2
    assert 'capability: "code-generation"' not in script
    assert script.count(f"capability={capability} resolved_engine={selected}") == 2


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"environment": {"SAGA_MAX_CONCURRENT": "03"}}, "SAGA_MAX_CONCURRENT"),
        ({"environment": {"SAGA_MAX_CONCURRENT": "8"}}, "exceeds aggregate"),
        ({"run_override": 3.5}, "run max_concurrent override"),
        ({"lane_limits": {"lane/one": 0}}, "engine lane max_concurrent"),
    ],
)
def test_invalid_resolution_inputs_fail_with_source(
    kwargs: dict[str, object], message: str
) -> None:
    unit = _governor_unit(engine="lane/one")
    with pytest.raises(M.ConcurrencyPolicyError, match=message):
        M.concurrency_governor.resolve_concurrency(M.ConcurrencyPolicy(), [unit], **kwargs)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"environment": {"SAGA_MAX_CONCURRENT": "bad"}, "run_override": 2},
            "SAGA_MAX_CONCURRENT",
        ),
        (
            {"lane_limits": {"lane/one": 0}, "run_override": 2},
            "engine lane max_concurrent",
        ),
    ],
)
def test_run_override_does_not_hide_invalid_lower_rung(
    kwargs: dict[str, object], message: str
) -> None:
    unit = _governor_unit(engine="lane/one")
    with pytest.raises(M.ConcurrencyPolicyError, match=message):
        M.concurrency_governor.resolve_concurrency(M.ConcurrencyPolicy(), [unit], **kwargs)


def test_six_unit_layer_emits_two_ordered_three_wide_waves() -> None:
    spec = _spec([_unit(f"U{index}") for index in range(6)])

    script = M.emit_workflow_script(spec, environment={})

    assert "const [U0, U1, U2] = await parallel([" in script
    assert "const [U3, U4, U5] = await parallel([" in script
    assert script.index("[U0, U1, U2]") < script.index("[U3, U4, U5]")
    assert script.count("concurrency chunk") == 2


def test_dependent_layer_starts_after_every_chunk_in_prior_layer() -> None:
    upstream = [_unit(f"U{index}") for index in range(6)]
    dependent = _unit("D")
    dependent["depends_on"] = [f"U{index}" for index in range(6)]
    spec = _spec([*upstream, dependent])

    script = M.emit_workflow_script(spec, environment={})

    final_wave = script.index("const [U3, U4, U5] = await parallel([")
    final_wave_close = script.index("])", final_wave)
    dependent_start = script.index("const D = await agent(")
    assert final_wave < final_wave_close < dependent_start


def test_serialized_nondefault_policy_controls_emitted_worker_chunks() -> None:
    spec = _spec(
        [_unit(f"U{index}") for index in range(5)],
        concurrency={
            "max_concurrent": 2,
            "readonly_max_concurrent": 3,
            "aggregate_max_concurrent": 7,
        },
    )

    script = M.emit_workflow_script(spec, environment={})

    assert "const [U0, U1] = await parallel([" in script
    assert "const [U2, U3] = await parallel([" in script
    assert "const [U4] = await parallel([" in script


def test_valid_environment_override_controls_emitted_worker_chunks() -> None:
    spec = _spec([_unit(f"U{index}") for index in range(4)])

    script = M.emit_workflow_script(spec, environment={"SAGA_MAX_CONCURRENT": "2"})

    assert "const [U0, U1] = await parallel([" in script
    assert "const [U2, U3] = await parallel([" in script


def test_emit_snapshots_environment_before_aggregate_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_environment = {"SAGA_MAX_CONCURRENT": "1"}
    original_max_concurrent_agents = M.max_concurrent_agents

    def mutate_source_after_preflight(*args: object, **kwargs: object) -> int:
        result = original_max_concurrent_agents(*args, **kwargs)
        source_environment["SAGA_MAX_CONCURRENT"] = "2"
        return int(result)

    monkeypatch.setattr(M, "max_concurrent_agents", mutate_source_after_preflight)
    spec = _spec([_unit("U0"), _unit("U1")])

    script = M.emit_workflow_script(spec, environment=source_environment)

    assert source_environment["SAGA_MAX_CONCURRENT"] == "2"
    assert "const [U0] = await parallel([" in script
    assert "const [U1] = await parallel([" in script
    assert "const [U0, U1] = await parallel([" not in script


@pytest.mark.parametrize(
    "admission_source",
    ["environment", "exact-lane", "capability-lane"],
)
@pytest.mark.parametrize(
    ("consumer", "panel_prefixes"),
    [
        ("singleton-normal", ("U_verdicts",)),
        ("layer-normal", ("U_verdicts",)),
        ("singleton-consensus", ("verdicts",)),
        ("thunk-consensus", ("verdicts",)),
        ("singleton-unattended-retry", ("U_verdicts", "U_retry_verdicts")),
    ],
)
def test_emit_uses_one_frozen_admission_snapshot_across_every_panel_consumer(
    admission_source: str,
    consumer: str,
    panel_prefixes: tuple[str, ...],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_engine = "codex/gpt-5.6-sol-xhigh"
    source_environment = {"SAGA_MAX_CONCURRENT": "1"} if admission_source == "environment" else {}
    expected_environment = dict(source_environment)
    emit_kwargs: dict[str, object] = {}
    unit_engine: str | None = None
    unit_capability: str | None = None

    if admission_source != "environment":
        registry = M._engine_registry_path().read_text(encoding="utf-8")
        needle = "  - engine_id: codex\n    variant: gpt-5.6-sol-xhigh\n"
        assert needle in registry
        registry_path = tmp_path / "engine-registry.yaml"
        registry_path.write_text(
            registry.replace(needle, needle + "    max_concurrent: 1\n", 1),
            encoding="utf-8",
        )
        monkeypatch.setattr(M, "_engine_registry_path", lambda: registry_path)
        if admission_source == "exact-lane":
            unit_engine = selected_engine
        else:
            capability = "code-generation"
            unit_capability = capability
            emit_kwargs.update(
                routing_overlay=M.engine_overlay.EngineOverlay(pins={capability: selected_engine}),
                routing_calibration=M.engine_calibration.CalibrationSignals(),
            )

    unit = _unit(
        "U",
        verify_n=3,
        engine=unit_engine,
        capability=unit_capability,
    )
    if consumer in {"singleton-consensus", "thunk-consensus"}:
        verify = unit["verify"]
        assert isinstance(verify, dict)
        verify["iterate_to_consensus"] = True
    if consumer == "singleton-unattended-retry":
        unit["escalate_on_signal"] = True
        emit_kwargs["unattended"] = True
    units = [unit]
    if consumer in {"layer-normal", "thunk-consensus"}:
        units.append(_unit("Peer"))
    spec = _spec(units)

    original_build_context = M._build_emission_routing_context
    original_resolved_concurrency = M.resolved_concurrency
    built_contexts: list[Any] = []
    resolved_calls: list[tuple[Mapping[str, str], object, list[str], int, str]] = []

    def record_build_context(*args: object, **kwargs: object) -> object:
        context = original_build_context(*args, **kwargs)
        built_contexts.append(context)
        return context

    def record_resolved_concurrency(*args: object, **kwargs: object) -> object:
        environment = cast(Mapping[str, str], kwargs["environment"])
        routing_context = kwargs["routing_context"]
        cohort = cast(Sequence[Any], args[1])
        if not resolved_calls:
            source_environment["SAGA_MAX_CONCURRENT"] = "3"
        result = original_resolved_concurrency(*args, **kwargs)
        resolved_calls.append(
            (
                environment,
                routing_context,
                [member.unit_id for member in cohort],
                result.width,
                result.source,
            )
        )
        return result

    monkeypatch.setattr(M, "_build_emission_routing_context", record_build_context)
    monkeypatch.setattr(M, "resolved_concurrency", record_resolved_concurrency)

    script = M.emit_workflow_script(
        spec,
        environment=source_environment,
        **emit_kwargs,
    )

    assert source_environment == {"SAGA_MAX_CONCURRENT": "3"}
    assert len(built_contexts) == 1
    context = built_contexts[0]
    assert isinstance(context.units, MappingProxyType)
    assert isinstance(context.lane_limits, MappingProxyType)
    assert isinstance(context.lane_assignments, MappingProxyType)
    assert resolved_calls
    assert all(call[0] is resolved_calls[0][0] for call in resolved_calls)
    assert all(dict(call[0]) == expected_environment for call in resolved_calls)
    assert all(call[1] is context for call in resolved_calls)
    target_calls = [call for call in resolved_calls if call[2] == ["U"]]
    assert target_calls
    assert all(call[3] == 1 for call in target_calls)

    for prefix in panel_prefixes:
        assert f"const {prefix} = await parallel([" in script
        assert f"const {prefix}_chunk_2 = await parallel([" in script
        assert f"const {prefix}_chunk_3 = await parallel([" in script

    if admission_source == "environment":
        assert not context.lane_assignments
    else:
        assert context.lane_assignments["U"] == selected_engine
        assert context.lane_limits[selected_engine] == 1
        assert all(call[4] == "lane" for call in target_calls)
        assert f'engine: "{selected_engine}"' in script
        assert "capability:" not in script


def test_readonly_layer_emits_four_wide_then_remainder() -> None:
    spec = _spec([_unit(f"U{index}", read_only=True) for index in range(5)])

    script = M.emit_workflow_script(spec, environment={})

    assert "const [U0, U1, U2, U3] = await parallel([" in script
    assert "const [U4] = await parallel([" in script


def test_seven_member_panel_is_chunked_and_reconciled_in_order() -> None:
    spec = _spec([_unit("U", verify_n=7)])

    script = M.emit_workflow_script(spec, environment={})

    assert "const U_verdicts = await parallel([" in script
    assert script.count("const U_verdicts_chunk_") == 2
    assert script.count("agentType:") == 7
    assert "U_verdicts.push(...U_verdicts_chunk_2, ...U_verdicts_chunk_3)" in script


def test_panel_admission_uses_explicit_effective_verify_tier() -> None:
    spec = _spec(
        [
            _unit(
                "U",
                model="haiku",
                effort="low",
                verify_n=3,
                verify_tier={"model": "opus", "effort": "high"},
            )
        ]
    )

    script = M.emit_workflow_script(spec, environment={})

    assert "const U_verdicts = await parallel([" in script
    assert script.count("const U_verdicts_chunk_") == 2


def test_aggregate_guard_uses_effective_verify_tier_width() -> None:
    spec = _spec(
        [
            _unit(
                "A",
                model="haiku",
                effort="low",
                verify_n=3,
                verify_tier={"model": "opus", "effort": "high"},
            ),
            _unit("B", model="haiku", effort="low"),
            _unit("C", model="haiku", effort="low"),
        ]
    )

    assert M.max_concurrent_agents(spec, environment={}) == 3
    assert "const [A, B, C] = await parallel([" in M.emit_workflow_script(spec, environment={})


def test_unattended_retry_panel_re_resolves_climbed_tier_width() -> None:
    unit = _unit("U", model="sonnet", effort="high", verify_n=3)
    unit["escalate_on_signal"] = True
    spec = _spec([unit])

    script = M.emit_workflow_script(spec, unattended=True, environment={})

    assert "const U_verdicts = await parallel([" in script
    assert "const U_retry_verdicts = await parallel([" in script
    assert script.count("const U_retry_verdicts_chunk_") == 2


def test_unattended_retry_panel_preserves_explicit_verify_tier_width() -> None:
    unit = _unit(
        "U",
        model="haiku",
        effort="low",
        verify_n=3,
        verify_tier={"model": "opus", "effort": "high"},
    )
    unit["escalate_on_signal"] = True
    spec = _spec([unit])

    script = M.emit_workflow_script(spec, unattended=True, environment={})

    assert "climbing ONE rung to haiku/medium" in script
    assert script.count("const U_verdicts_chunk_") == 2
    assert script.count("const U_retry_verdicts_chunk_") == 2


def test_aggregate_guard_names_factors_product_and_ceiling() -> None:
    spec = _spec(
        [
            _unit("A", verify_n=3),
            _unit("B"),
            _unit("C"),
        ]
    )

    with pytest.raises(
        M.SpecError,
        match=r"layer 1 aggregate concurrency 3 x 3 = 9 exceeds aggregate_max_concurrent 7",
    ):
        M.emit_workflow_script(spec, environment={})


def test_explicit_run_override_above_aggregate_fails_before_emission() -> None:
    spec = _spec([_unit("U")])

    with pytest.raises(M.SpecError, match="run max_concurrent override.*exceeds aggregate"):
        M.emit_workflow_script(spec, environment={}, run_max_concurrent=8)


def test_cli_explicit_run_override_chunks_emission(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "name": "cli-override",
                "description": "operator run width",
                "units": [_unit(f"U{index}") for index in range(3)],
            }
        ),
        encoding="utf-8",
    )

    rc = M.main(["emit", str(spec_path), "--max-concurrent", "2"])

    assert rc == 0
    output = capsys.readouterr().out
    assert "const [U0, U1] = await parallel([" in output
    assert "const [U2] = await parallel([" in output
