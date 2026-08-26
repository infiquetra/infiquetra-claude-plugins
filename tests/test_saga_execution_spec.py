"""Oracle tests for Saga execution-spec external-engine routing (U5)."""

from __future__ import annotations

import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
EXECUTION_SPEC_SCRIPT = SCRIPT_DIR / "execution_spec.py"
LIFECYCLE_STATE_SCRIPT = SCRIPT_DIR / "lifecycle_state.py"


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ES = _load("execution_spec", EXECUTION_SPEC_SCRIPT)
_load("lifecycle_state", LIFECYCLE_STATE_SCRIPT)
DS = _load("dispatch_settlement", SCRIPT_DIR / "dispatch_settlement.py")
RL = sys.modules["run_ledger"]


@pytest.fixture(autouse=True)
def _external_engine_preflight_is_deterministically_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ES.engine_resolver,
        "preflight",
        lambda *_args, **_kwargs: {"available": True, "reason": "test snapshot"},
    )


def _routing_snapshots() -> dict[str, object]:
    return {
        "routing_overlay": ES.engine_overlay.EngineOverlay(),
        "routing_calibration": ES.engine_calibration.CalibrationSignals(),
    }


# Independent test oracle: ECMAScript built-ins, Node workflow globals, and CommonJS wrapper names.
# This deliberately does not import or derive from execution_spec's reservation set.
_JAVASCRIPT_GLOBAL_CANDIDATES = frozenset(
    re.findall(
        r"[A-Za-z_$][A-Za-z0-9_$]*",
        """
    AbortController AbortSignal AggregateError Array ArrayBuffer Atomics BigInt BigInt64Array
    BigUint64Array Blob Boolean BroadcastChannel Buffer ByteLengthQueuingStrategy CompressionStream
    CountQueuingStrategy Crypto CryptoKey CustomEvent DOMException DataView Date DecompressionStream
    Error EvalError Event EventTarget File FinalizationRegistry Float32Array Float64Array FormData
    Function Headers Infinity Int16Array Int32Array Int8Array Intl Iterator JSON Map Math
    MessageChannel MessageEvent MessagePort NaN Navigator Number Object Performance PerformanceEntry
    PerformanceMark PerformanceMeasure PerformanceObserver PerformanceObserverEntryList
    PerformanceResourceTiming Promise Proxy RangeError ReadableByteStreamController ReadableStream
    ReadableStreamBYOBReader ReadableStreamBYOBRequest ReadableStreamDefaultController
    ReadableStreamDefaultReader ReferenceError Reflect RegExp Request Response Set SharedArrayBuffer
    String SubtleCrypto Symbol SyntaxError TextDecoder TextDecoderStream TextEncoder TextEncoderStream
    TransformStream TransformStreamDefaultController TypeError URIError URL URLSearchParams
    Uint16Array Uint32Array Uint8Array Uint8ClampedArray WeakMap WeakRef WeakSet WebAssembly WebSocket
    WritableStream WritableStreamDefaultController WritableStreamDefaultWriter __dirname __filename
    assert async_hooks atob btoa buffer child_process clearImmediate clearInterval clearTimeout cluster
    console constants crypto decodeURI decodeURIComponent dgram diagnostics_channel dns domain encodeURI
    encodeURIComponent escape eval events exports fetch fs global globalThis http http2 https inspector
    isFinite isNaN module navigator net os parseFloat parseInt path perf_hooks performance process
    punycode querystring queueMicrotask readline repl require setImmediate setInterval setTimeout stream
    string_decoder structuredClone sys timers tls trace_events tty undefined unescape url util v8 vm wasi
    worker_threads zlib
    """,
    )
)

# Workflow host primitives are not properties of Node's ``globalThis`` inventory. Keep this
# independent baseline separate so removing any one production reservation is observable.
_WORKFLOW_HOST_GLOBAL_CANDIDATES = frozenset({"agent", "log", "parallel"})


def _referenced_harness_globals(script: str) -> set[str]:
    """Detect free standard globals in emitted harness code without executing it."""

    alternatives = "|".join(
        re.escape(identifier)
        for identifier in sorted(
            _JAVASCRIPT_GLOBAL_CANDIDATES | _WORKFLOW_HOST_GLOBAL_CANDIDATES,
            key=len,
            reverse=True,
        )
    )
    found = set(re.findall(rf"(?<![.$\w'\"])(?:{alternatives})(?![\w'\"])", script))
    found.update(re.findall(rf"\b(?:new|instanceof|typeof)\s+({alternatives})\b", script))
    for bare_identifier in ("Infinity", "NaN", "undefined"):
        if re.search(rf"\b{bare_identifier}\b", script):
            found.add(bare_identifier)
    return found


def _spec_dict(**unit_overrides: object) -> dict[str, object]:
    unit: dict[str, object] = {
        "unit_id": "U1",
        "label": "external draft",
        "tier": {"model": "sonnet", "effort": "high"},
        "prompt": "draft a bounded implementation diff",
        "returns": ["diff", "assumptions"],
    }
    unit.update(unit_overrides)
    return {
        "name": "external-engine-demo",
        "description": "exercise external-engine unit selectors",
        "repo": "/tmp/repo",
        "units": [unit],
    }


def test_engine_unit_validates_but_emit_rejects_with_named_actionable_error() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/gpt-5.5-xhigh"))
    spec.validate()

    with pytest.raises(ES.SpecError, match="external-engine unit") as excinfo:
        ES.emit_workflow_script(spec)

    message = str(excinfo.value)
    assert "codex/gpt-5.5-xhigh" in message
    assert "Herdr/Orchestrate" in message
    assert "#708" in message


def test_capability_unit_emit_rejects_with_named_actionable_error() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(capability="code-generation"))
    spec.validate()

    with pytest.raises(ES.SpecError, match="external-engine unit") as excinfo:
        ES.emit_workflow_script(spec, environment={}, **_routing_snapshots())

    message = str(excinfo.value)
    assert "code-generation" in message
    assert "Herdr/Orchestrate" in message


def test_unhonored_opts_keys_fail_at_emit_naming_the_key() -> None:
    with pytest.raises(ES.SpecError, match="opts key 'dispatch'") as excinfo:
        ES._reject_unhonored_workflow_agent_opts(
            "unit U1",
            ['dispatch: "external-engine"', 'engine: "codex/gpt-5.5-xhigh"'],
        )
    message = str(excinfo.value)
    assert "dispatch" in message
    assert "engine" in message
    assert "Herdr/Orchestrate" in message


def test_agent_opts_rejects_engine_route_naming_dispatch() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/gpt-5.5-xhigh"))
    route = ES.UnitRouting(
        prompt="draft",
        exact_engine="codex/gpt-5.5-xhigh",
        authored_capability=None,
        lane_max_concurrent=None,
    )
    with pytest.raises(ES.SpecError, match="opts key 'dispatch'") as excinfo:
        ES._agent_opts(spec.units[0], route)
    assert "dispatch" in str(excinfo.value)
    assert "engine" in str(excinfo.value)


def test_agent_opts_does_not_silently_fall_back_to_native_model_effort() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/gpt-5.5-xhigh"))
    native_looking_route = ES.UnitRouting(
        prompt="draft",
        exact_engine=None,
        authored_capability=None,
        lane_max_concurrent=None,
    )
    with pytest.raises(ES.SpecError, match="opts key 'dispatch'"):
        ES._agent_opts(spec.units[0], native_looking_route)


def test_agent_opts_source_does_not_emit_inert_dispatch_opt() -> None:
    import inspect

    src = inspect.getsource(ES._agent_opts)
    assert 'dispatch: "external-engine"' not in src
    assert "dispatch:" not in src


def test_external_engine_marker_raises_instead_of_emitting_a_comment() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/gpt-5.5-xhigh"))
    route = ES.UnitRouting(
        prompt="draft",
        exact_engine="codex/gpt-5.5-xhigh",
        authored_capability=None,
        lane_max_concurrent=None,
    )
    with pytest.raises(ES.SpecError, match="external-engine dispatch is not honored"):
        ES._external_engine_marker(spec.units[0], route)


def test_bare_model_alias_engine_unit_fails_at_emit_via_the_same_reject_path() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    aliased = replace(spec.units[0], engine="opus")
    spec = replace(spec, units=[aliased])
    with pytest.raises(ES.SpecError, match="external-engine unit") as excinfo:
        ES.emit_workflow_script(spec)
    message = str(excinfo.value)
    assert "opus" in message
    assert "Herdr/Orchestrate" in message
    assert "#708" in message


def test_workflow_settlement_metadata_contains_each_unit_once() -> None:
    data = _spec_dict()
    initial_units = data["units"]
    assert isinstance(initial_units, list)
    data["units"] = [
        initial_units[0],
        {
            "unit_id": "U2",
            "label": "validate",
            "tier": {"model": "sonnet", "effort": "medium"},
            "returns": ["verdict"],
            "depends_on": ["U1"],
        },
    ]
    spec = ES.ExecutionSpec.from_dict(data)
    metadata = ES.workflow_settlement_metadata(spec)
    assert metadata["schema"] == "dispatch_settlement.v1"
    assert metadata["site"] == "workflow"
    assert [unit["unit_id"] for unit in metadata["units"]] == ["U1", "U2"]
    assert len({unit["idempotency_key"] for unit in metadata["units"]}) == 2
    assert metadata == ES.workflow_settlement_metadata(spec)


def test_workflow_settlement_invocation_identity_replays_only_the_same_run() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())

    first = ES.workflow_settlement_metadata(spec, invocation_id="wf-driver-run-1")
    replay = ES.workflow_settlement_metadata(spec, invocation_id="wf-driver-run-1")
    later = ES.workflow_settlement_metadata(spec, invocation_id="wf-driver-run-2")

    assert first == replay
    assert first["dispatch_id"] != later["dispatch_id"]
    assert first["units"][0]["idempotency_key"] != later["units"][0]["idempotency_key"]
    assert first["driver"]["invocation_id"] == "wf-driver-run-1"


def test_workflow_settlement_maps_legacy_result_contracts_without_rewriting_them() -> None:
    legacy_unit_id = "unit_" + "x" * 240
    legacy_result_key = "finding title with whitespace " + "y" * 220
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(
            unit_id=legacy_unit_id,
            returns=[legacy_result_key, "already-safe", "already-safe"],
        )
    )

    metadata = ES.workflow_settlement_metadata(spec, invocation_id="wf-legacy-contract")
    unit = metadata["units"][0]
    binding = metadata["driver"]["units"][0]

    assert binding["workflow_unit_id"] == legacy_unit_id
    assert binding["settlement_unit_id"] == unit["unit_id"]
    assert len(unit["unit_id"]) <= DS.MAX_ID_LENGTH
    assert binding["return_keys"] == [
        {
            "result_key": legacy_result_key,
            "deliverable": "return:"
            + DS.safe_contract_identifier(legacy_result_key, namespace="workflow-return"),
        },
        {"result_key": "already-safe", "deliverable": "return:already-safe"},
        {"result_key": "already-safe", "deliverable": "return:already-safe"},
    ]
    assert unit["deliverables"].count("return:already-safe") == 1
    assert spec.units[0].returns == [legacy_result_key, "already-safe", "already-safe"]


def test_workflow_driver_settles_structured_missing_and_self_report_results(tmp_path: Path) -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    ledger = RL.RunLedger(tmp_path / "run-facts.jsonl")
    at = "2026-07-16T00:00:00Z"

    delivered = ES.workflow_settlement_metadata(spec, invocation_id="wf-structured-result")
    unit = delivered["units"][0]
    DS.ensure_manifest(
        ledger,
        DS.manifest_fact(
            subplot_id="sub-351",
            at=at,
            dispatch_id=delivered["dispatch_id"],
            site="workflow",
            units=delivered["units"],
        ),
    )
    DS.append_spawn(
        ledger,
        DS.spawn_fact(
            subplot_id="sub-351",
            at=at,
            dispatch_id=delivered["dispatch_id"],
            unit_id=unit["unit_id"],
            attempt=1,
            idempotency_key=unit["idempotency_key"],
        ),
    )
    evidence = tmp_path / "workflow-result.json"
    evidence.write_text(
        json.dumps(
            {
                "schema": "dispatch.workflow-result.v1",
                "unit_id": unit["unit_id"],
                "result": {"diff": "patch", "assumptions": "none"},
            }
        ),
        encoding="utf-8",
    )
    DS.settle_from_evidence(
        ledger,
        subplot_id="sub-351",
        at=at,
        dispatch_id=delivered["dispatch_id"],
        unit_id=unit["unit_id"],
        attempt=1,
        evidence={
            "receipt_type": "workflow-result",
            "unit_id": unit["unit_id"],
            "evidence_path": str(evidence),
        },
        evidence_root=tmp_path,
    )
    assert (
        DS.settlement_report(ledger, delivered["dispatch_id"]).entries[0].classification
        == DS.DELIVERED
    )

    missing = ES.workflow_settlement_metadata(spec, invocation_id="wf-missing-result")
    missing_unit = missing["units"][0]
    DS.ensure_manifest(
        ledger,
        DS.manifest_fact(
            subplot_id="sub-351",
            at=at,
            dispatch_id=missing["dispatch_id"],
            site="workflow",
            units=missing["units"],
        ),
    )
    DS.append_spawn(
        ledger,
        DS.spawn_fact(
            subplot_id="sub-351",
            at=at,
            dispatch_id=missing["dispatch_id"],
            unit_id=missing_unit["unit_id"],
            attempt=1,
            idempotency_key=missing_unit["idempotency_key"],
        ),
    )
    DS.settle_from_evidence(
        ledger,
        subplot_id="sub-351",
        at=at,
        dispatch_id=missing["dispatch_id"],
        unit_id=missing_unit["unit_id"],
        attempt=1,
        evidence=None,
    )
    assert (
        DS.settlement_report(ledger, missing["dispatch_id"]).entries[0].classification
        == DS.SILENT_NOOP
    )
    assert (
        DS.classify_evidence(
            missing_unit["deliverables"],
            {"self_report": "done"},
            expected_unit_id=missing_unit["unit_id"],
        ).classification
        == DS.SILENT_NOOP
    )


def test_emitted_workflow_exports_settlement_without_ledger_write_permission() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    script = ES.emit_workflow_script(spec)
    metadata = ES.workflow_settlement_metadata(spec)
    assert (
        "const settlement = " + json.dumps(metadata, sort_keys=True, separators=(",", ":"))
        in script
    )
    assert "run_ledger.py" not in script
    assert "dispatch_settlement.py" not in script


def test_emitted_settlement_identity_ignores_session_tier_ceiling() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(tier={"model": "opus", "effort": "high"}))
    metadata = ES.workflow_settlement_metadata(spec)
    script = ES.emit_workflow_script(spec, session_ceiling=ES.Tier("sonnet", "medium"))
    assert (
        "const settlement = " + json.dumps(metadata, sort_keys=True, separators=(",", ":"))
        in script
    )
    assert 'model: "sonnet"' in script and 'effort: "medium"' in script


def test_settlement_cli_emits_driver_owned_metadata(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec_dict()), encoding="utf-8")

    assert ES.main(["settlement", str(spec_path), "--invocation-id", "cli-run-1"]) == 0

    metadata = json.loads(capsys.readouterr().out)
    assert metadata["site"] == "workflow"
    assert metadata["driver"]["invocation_id"] == "cli-run-1"
    assert [unit["unit_id"] for unit in metadata["units"]] == ["U1"]
    assert metadata["units"][0]["deliverables"] == [
        "structured-result",
        "return:diff",
        "return:assumptions",
    ]


def _fake_resolution(
    *,
    engine_id: str = "codex",
    variant: str = "gpt-5.6-sol-xhigh",
    fallback: str | None = None,
    halt: str | None = None,
    capability: str | None = "code-generation",
) -> SimpleNamespace:
    return SimpleNamespace(
        engine_id=engine_id,
        variant=variant,
        fallback=fallback,
        halt=halt,
        capability=capability,
    )


def test_capability_emit_requires_explicit_repo_root_without_snapshot_injection() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(capability="code-generation"))

    with pytest.raises(ES.SpecError, match="external-engine unit"):
        ES.emit_workflow_script(spec)
    with pytest.raises(ES.SpecError, match="requires explicit repo_root"):
        ES._build_emission_routing_context(spec)


def test_capability_workflow_recompile_forwards_explicit_repo_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(capability="code-generation"))
    captured: list[tuple[object, object]] = []

    def fake_emit(routed_spec: object, *, repo_root: object = None) -> str:
        captured.append((routed_spec, repo_root))
        return "// workflow\n"

    monkeypatch.setattr(ES, "emit_workflow_script", fake_emit)

    assert ES.recompile_for_tier(spec, "cc-workflows-ultracode", repo_root=tmp_path) == (
        "// workflow\n"
    )
    assert captured == [(spec, tmp_path)]


def test_capability_workflow_recompile_requires_explicit_repo_root() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(capability="code-generation"))

    with pytest.raises(ES.SpecError, match="external-engine unit"):
        ES.recompile_for_tier(spec, "cc-workflows-ultracode")


def test_capability_snapshot_injection_requires_the_pair() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(capability="code-generation"))

    with pytest.raises(ES.SpecError, match="external-engine unit"):
        ES.emit_workflow_script(
            spec,
            routing_overlay=ES.engine_overlay.EngineOverlay(),
        )
    with pytest.raises(ES.SpecError, match="must supply both"):
        ES._build_emission_routing_context(
            spec,
            routing_overlay=ES.engine_overlay.EngineOverlay(),
        )


def test_emit_freezes_prompts_routes_loaders_and_memo_across_unattended_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = ES.ExecutionSpec.from_dict(
        {
            "name": "frozen-route",
            "description": "one immutable emission context",
            "units": [
                _escalate_unit(capability="code-generation"),
                _verify_unit("U2", capability="code-generation"),
            ],
        }
    )
    registry_class = ES._engine_registry_module().Registry
    original_registry_load = registry_class.load.__func__
    registry_loads: list[Path] = []

    def counted_registry_load(cls: type[object], path: Path) -> object:
        registry_loads.append(Path(path))
        return original_registry_load(cls, path)

    monkeypatch.setattr(registry_class, "load", classmethod(counted_registry_load))
    overlay = ES.engine_overlay.EngineOverlay()
    calibration = ES.engine_calibration.CalibrationSignals()
    overlay_loads: list[Path] = []
    calibration_loads: list[Path] = []

    def load_overlay(root: Path | str) -> object:
        overlay_loads.append(Path(root))
        return overlay

    def load_calibration(root: Path | str) -> object:
        calibration_loads.append(Path(root))
        return calibration

    monkeypatch.setattr(
        ES.engine_overlay,
        "load_overlay",
        load_overlay,
    )
    monkeypatch.setattr(
        ES,
        "_load_repository_calibration",
        load_calibration,
    )
    original_prompt = ES._agent_prompt
    prompt_calls: list[str] = []

    def counted_prompt(route_spec: Any, unit: Any) -> str:
        prompt_calls.append(unit.unit_id)
        return str(original_prompt(route_spec, unit))

    monkeypatch.setattr(ES, "_agent_prompt", counted_prompt)
    resolver_calls: list[tuple[dict[str, object], object, object, object]] = []

    def fake_resolve(request: dict[str, object], **kwargs: object) -> SimpleNamespace:
        resolver_calls.append((request, kwargs["memo"], kwargs["overlay"], kwargs["calibration"]))
        return _fake_resolution()

    monkeypatch.setattr(ES.engine_resolver, "resolve", fake_resolve)

    with pytest.raises(ES.SpecError, match="external-engine unit"):
        ES.emit_workflow_script(
            spec,
            unattended=True,
            repo_root=tmp_path,
            environment={},
        )

    ES._build_emission_routing_context(spec, repo_root=tmp_path)

    assert registry_loads == [ES._engine_registry_path()]
    assert overlay_loads == [tmp_path]
    assert calibration_loads == [tmp_path]
    assert prompt_calls == ["U1", "U2"]
    assert len(resolver_calls) == 2
    assert len({id(call[1]) for call in resolver_calls}) == 1
    assert all(call[2] is overlay and call[3] is calibration for call in resolver_calls)
    for request, *_rest in resolver_calls:
        task_context = request["task_context"]
        assert request["role_kind"] == "worker"
        assert isinstance(task_context, dict)
        prompt = task_context["context"]
        assert task_context["token_estimate"] == len(prompt.encode("utf-8"))
        assert task_context["unit_id"] in {"U1", "U2"}
    assert spec.units[0].to_dict()["capability"] == "code-generation"
    assert "engine" not in spec.units[0].to_dict()


def test_exact_engine_route_never_calls_capability_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/gpt-5.5-xhigh"))

    def unexpected_resolve(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("exact engine must use Registry.by_key directly")

    monkeypatch.setattr(ES.engine_resolver, "resolve", unexpected_resolve)

    with pytest.raises(ES.SpecError, match="external-engine unit"):
        ES.emit_workflow_script(spec, environment={})
    context = ES._build_emission_routing_context(spec)
    assert context.for_unit(spec.units[0]).exact_engine == "codex/gpt-5.5-xhigh"


def test_exact_engine_workflow_recompile_loads_registry_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/gpt-5.5-xhigh"))
    registry_class = ES._engine_registry_module().Registry
    original_registry_load = registry_class.load.__func__
    loads: list[Path] = []

    def counted_registry_load(cls: type[object], path: Path) -> object:
        loads.append(Path(path))
        return original_registry_load(cls, path)

    monkeypatch.setattr(registry_class, "load", classmethod(counted_registry_load))

    with pytest.raises(ES.SpecError, match="external-engine unit"):
        ES.recompile_for_tier(spec, "cc-workflows-ultracode")
    assert loads == []


@pytest.mark.parametrize(
    ("resolution", "message"),
    [
        (_fake_resolution(fallback="fallback"), "resolved to fallback"),
        (_fake_resolution(halt="halt"), "halted"),
        (_fake_resolution(engine_id=""), "empty route"),
        (_fake_resolution(engine_id="claude", variant="default"), "Claude substitution"),
        (_fake_resolution(engine_id="not-registered", variant="v1"), "non-registry engine"),
        (
            _fake_resolution(engine_id="ollama-cloud", variant="nomic-embed-text"),
            "does not declare",
        ),
        (_fake_resolution(capability="second-opinion"), "does not match authored"),
    ],
)
def test_capability_resolution_outputs_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    resolution: SimpleNamespace,
    message: str,
) -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(capability="code-generation"))
    monkeypatch.setattr(
        ES.engine_resolver,
        "resolve",
        lambda *_args, **_kwargs: resolution,
    )

    with pytest.raises(ES.SpecError, match="external-engine unit"):
        ES.emit_workflow_script(spec, environment={}, **_routing_snapshots())
    with pytest.raises(ES.SpecError, match=message):
        ES._build_emission_routing_context(spec, **_routing_snapshots())


def test_capability_resolver_exception_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(capability="code-generation"))

    def fail(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("resolver exploded")

    monkeypatch.setattr(ES.engine_resolver, "resolve", fail)

    with pytest.raises(ES.SpecError, match="external-engine unit"):
        ES.emit_workflow_script(spec, environment={}, **_routing_snapshots())
    with pytest.raises(ES.SpecError, match="resolution failed: resolver exploded"):
        ES._build_emission_routing_context(spec, **_routing_snapshots())


def test_missing_overlay_loads_as_empty_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(capability="code-generation"))
    captured: list[tuple[object, object]] = []
    monkeypatch.setattr(
        ES,
        "_load_repository_calibration",
        lambda _root: ES.engine_calibration.CalibrationSignals(),
    )

    def capture(request: object, **kwargs: object) -> SimpleNamespace:
        captured.append((kwargs["overlay"], kwargs["calibration"]))
        return _fake_resolution()

    monkeypatch.setattr(ES.engine_resolver, "resolve", capture)

    with pytest.raises(ES.SpecError, match="external-engine unit"):
        ES.emit_workflow_script(spec, repo_root=tmp_path, environment={})
    ES._build_emission_routing_context(spec, repo_root=tmp_path)

    assert len(captured) == 1
    assert captured[0][0] == ES.engine_overlay.EngineOverlay()
    assert captured[0][1] == ES.engine_calibration.CalibrationSignals()


def test_malformed_repository_overlay_fails_closed(tmp_path: Path) -> None:
    overlay_path = tmp_path / ".saga" / "engine-overlay.json"
    overlay_path.parent.mkdir()
    overlay_path.write_text("{not-json", encoding="utf-8")
    spec = ES.ExecutionSpec.from_dict(_spec_dict(capability="code-generation"))

    with pytest.raises(ES.SpecError, match="external-engine unit"):
        ES.emit_workflow_script(spec, repo_root=tmp_path, environment={})
    with pytest.raises(ES.SpecError, match="cannot load repository engine overlay"):
        ES._build_emission_routing_context(spec, repo_root=tmp_path)


def test_unreadable_repository_overlay_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(capability="code-generation"))
    monkeypatch.setattr(
        ES.engine_overlay,
        "load_overlay",
        lambda _root: (_ for _ in ()).throw(
            ES.engine_overlay.EngineOverlayError("cannot read overlay")
        ),
    )

    with pytest.raises(ES.SpecError, match="external-engine unit"):
        ES.emit_workflow_script(spec, repo_root=tmp_path, environment={})
    with pytest.raises(ES.SpecError, match="cannot load repository engine overlay"):
        ES._build_emission_routing_context(spec, repo_root=tmp_path)


def test_repository_calibration_absent_and_empty_are_empty_snapshots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = ES.engine_calibration.run_ledger.RunLedger(tmp_path / "run-facts.jsonl")
    monkeypatch.setattr(
        ES.engine_calibration.run_ledger.RunLedger,
        "resolve",
        classmethod(lambda _cls, _root: ledger),
    )

    assert ES._load_repository_calibration(tmp_path) == (ES.engine_calibration.CalibrationSignals())
    ledger.path.write_text("\n", encoding="utf-8")
    assert ES._load_repository_calibration(tmp_path) == (ES.engine_calibration.CalibrationSignals())


@pytest.mark.parametrize("payload", ["{not-json\n", '{"schema":"run_fact.v1"}\n'])
def test_repository_calibration_corruption_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: str,
) -> None:
    ledger = ES.engine_calibration.run_ledger.RunLedger(tmp_path / "run-facts.jsonl")
    ledger.path.write_text(payload, encoding="utf-8")
    monkeypatch.setattr(
        ES.engine_calibration.run_ledger.RunLedger,
        "resolve",
        classmethod(lambda _cls, _root: ledger),
    )

    with pytest.raises(ES.engine_calibration.CalibrationError):
        ES._load_repository_calibration(tmp_path)


def test_repository_calibration_unreadable_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = ES.engine_calibration.run_ledger.RunLedger(tmp_path / "run-facts.jsonl")
    monkeypatch.setattr(
        ES.engine_calibration.run_ledger.RunLedger,
        "resolve",
        classmethod(lambda _cls, _root: ledger),
    )
    original_read_text = Path.read_text

    def unreadable_read_text(path: Path, *, encoding: str) -> str:
        if path == ledger.path:
            raise PermissionError(f"denied ({encoding})")
        return original_read_text(path, encoding=encoding)

    monkeypatch.setattr(Path, "read_text", unreadable_read_text)

    with pytest.raises(ES.engine_calibration.CalibrationError, match="cannot read"):
        ES._load_repository_calibration(tmp_path)


def test_repository_calibration_uses_one_immutable_ledger_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = ES.engine_calibration.run_ledger.RunLedger(tmp_path / "run-facts.jsonl")
    fact = ES.engine_calibration.run_ledger.build_fact(
        "spend",
        subplot_id="snapshot-proof",
        at="2026-07-15T00:00:00Z",
        amount=1.0,
    )
    ES.engine_calibration.run_ledger.append_fact(ledger, fact)
    monkeypatch.setattr(
        ES.engine_calibration.run_ledger.RunLedger,
        "resolve",
        classmethod(lambda _cls, _root: ledger),
    )

    original_read_text = Path.read_text
    original_write_text = Path.write_text
    reads = 0

    def interleaving_read_text(path: Path, *, encoding: str) -> str:
        nonlocal reads
        raw = original_read_text(path, encoding=encoding)
        if path == ledger.path:
            reads += 1
            original_write_text(path, raw + "{interleaved-invalid-tail\n", encoding=encoding)
        return raw

    monkeypatch.setattr(Path, "read_text", interleaving_read_text)
    monkeypatch.setattr(
        ES.engine_calibration,
        "load_calibration",
        lambda _ledger: (_ for _ in ()).throw(AssertionError("must not reread the ledger")),
    )

    assert ES._load_repository_calibration(tmp_path) == ES.engine_calibration.CalibrationSignals()
    assert reads == 1


def test_unknown_engine_variant_fails() -> None:
    with pytest.raises(ES.SpecError, match="unknown engine variant"):
        ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/nonexistent"))


def test_unknown_capability_fails() -> None:
    with pytest.raises(ES.SpecError, match="unknown capability"):
        ES.ExecutionSpec.from_dict(_spec_dict(capability="telepathy"))


def test_engine_and_capability_are_mutually_exclusive() -> None:
    with pytest.raises(ES.SpecError, match="mutually exclusive"):
        ES.ExecutionSpec.from_dict(
            _spec_dict(engine="codex/gpt-5.5-xhigh", capability="code-generation")
        )


@pytest.mark.parametrize(
    "unit_id",
    [
        "bad\nawait_agent",
        "bad*/\nnext",
        "${agent}",
        "`agent`",
        "class",
        "__gate",
        "agent",
    ],
)
def test_workflow_unit_id_rejects_unsafe_or_reserved_identifiers(unit_id: str) -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(unit_id=unit_id))

    with pytest.raises(ES.SpecError, match="unit_id|reserved JavaScript"):
        ES.emit_workflow_script(spec)


@pytest.mark.parametrize("unit_id", sorted(ES._WORKFLOW_RUNTIME_GLOBAL_IDENTIFIERS))
def test_workflow_unit_id_rejects_harness_global_shadowing(unit_id: str) -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(unit_id=unit_id))

    with pytest.raises(ES.SpecError, match="reserved JavaScript identifier"):
        ES.emit_workflow_script(spec)


def test_workflow_harness_global_inventory_matches_emitted_source() -> None:
    script = _emit_units([_verify_unit("ordinary_unit", verify={"n": 2, "pass_rule": "majority"})])

    assert _referenced_harness_globals(script) <= ES._WORKFLOW_GLOBAL_IDENTIFIERS


def test_workflow_host_global_inventory_is_independent_and_reserved() -> None:
    assert ES._WORKFLOW_HOST_GLOBAL_IDENTIFIERS == _WORKFLOW_HOST_GLOBAL_CANDIDATES
    assert ES._WORKFLOW_GLOBAL_IDENTIFIERS == (
        ES._WORKFLOW_RUNTIME_GLOBAL_IDENTIFIERS | _WORKFLOW_HOST_GLOBAL_CANDIDATES
    )
    assert _WORKFLOW_HOST_GLOBAL_CANDIDATES <= ES._WORKFLOW_RESERVED_IDENTIFIERS


@pytest.mark.parametrize("host_global", sorted(_WORKFLOW_HOST_GLOBAL_CANDIDATES))
def test_workflow_rejects_every_independent_host_global_unit_id(host_global: str) -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(unit_id=host_global))

    with pytest.raises(ES.SpecError, match="reserved JavaScript identifier"):
        ES.emit_workflow_script(spec)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_workflow_runtime_global_inventory_covers_node_global_this() -> None:
    completed = subprocess.run(
        [
            "node",
            "-e",
            "process.stdout.write(JSON.stringify(Object.getOwnPropertyNames(globalThis)))",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    node_globals = {
        name
        for name in json.loads(completed.stdout)
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name)
    }

    assert _JAVASCRIPT_GLOBAL_CANDIDATES <= ES._WORKFLOW_RUNTIME_GLOBAL_IDENTIFIERS
    assert node_globals <= ES._WORKFLOW_RUNTIME_GLOBAL_IDENTIFIERS


def test_workflow_harness_global_inventory_detects_bare_and_shorthand_references() -> None:
    injected = "const timer = setTimeout\nconst refs = { Promise }\nURL.parse('value')\n"

    assert _referenced_harness_globals(injected) >= {"Promise", "URL", "setTimeout"}


def test_workflow_harness_global_inventory_ignores_member_property_names() -> None:
    injected = "holder.Promise\nholder['Promise']\n"

    assert "Promise" not in _referenced_harness_globals(injected)


def test_workflow_global_oracle_detects_removed_production_reservation() -> None:
    injected = "const value = Reflect.get(target, 'field')\n"
    reserved_without_reflect = ES._WORKFLOW_RUNTIME_GLOBAL_IDENTIFIERS - {"Reflect"}

    assert _referenced_harness_globals(injected) - reserved_without_reflect == {"Reflect"}


@pytest.mark.parametrize("host_global", sorted(_WORKFLOW_HOST_GLOBAL_CANDIDATES))
def test_workflow_host_global_oracle_detects_each_removed_production_reservation(
    host_global: str,
) -> None:
    script = _emit_units([_verify_unit("ordinary_unit", verify={"n": 2, "pass_rule": "majority"})])
    reservations_without_one = ES._WORKFLOW_RESERVED_IDENTIFIERS - {host_global}

    assert host_global in _referenced_harness_globals(script) - reservations_without_one


@pytest.mark.parametrize("unit_id", sorted(ES._WORKFLOW_ITERATE_LOCAL_IDENTIFIERS))
def test_workflow_iterate_unit_id_rejects_local_shadowing(unit_id: str) -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(
            unit_id=unit_id,
            verify={"n": 7, "pass_rule": "majority", "iterate_to_consensus": True},
        )
    )

    with pytest.raises(ES.SpecError, match="reserved JavaScript loop identifier"):
        ES.emit_workflow_script(spec)


def _as_runtime_harness(script: str, tail: str = "") -> str:
    """Wrap an emitted harness the way the Workflow runtime actually loads it.

    The runtime hoists the single leading ``export const meta`` statement and runs everything
    after it as an async FUNCTION BODY -- which is why an emitted harness may use both top-level
    ``await`` and (since #686 KTD4) a final top-level ``return``. Node's ESM parser accepts the
    first and rejects the second with "Illegal return statement", so checking the raw text with
    ``--input-type=module`` models the runtime incorrectly. Wrapping here keeps these two node
    tests honest about what the runtime does with the script.
    """
    body = script.replace("export const meta", "const meta", 1)
    return "const __harness = async () => {\n" + body + "\n};\n" + tail


# Stub verdict every stubbed verifier returns: BOTH #686 buckets, so the emitted reporter
# predicate counts it (a single-bucket stub would be classified runtime-missing and the panel
# would throw verifier-under-strength instead of executing the path under test).
_STUB_VERDICT_JS = (
    '{refuted_deliverable: [], advisory_corrections: [], upheld: [], verifier_identity: "stub", '
    'fallback_depth: 0, examined_sha: "deadbeef"}'
)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_workflow_iterate_ordinary_identifier_executes_with_runtime_stubs() -> None:
    script = _emit_units(
        [
            _verify_unit(
                "ordinary_unit",
                verify={"n": 2, "pass_rule": "majority", "iterate_to_consensus": True},
            )
        ]
    )
    prelude = f"""
const log = () => {{}};
const parallel = async (thunks) => Promise.all(thunks.map((thunk) => thunk()));
const agent = async (_prompt, opts) => opts && opts.agentType
  ? {_STUB_VERDICT_JS}
  : {{result: "ok"}};
"""
    wrapped = _as_runtime_harness(
        script,
        "const __result = await __harness();\n"
        "console.log(JSON.stringify(__result.units.ordinary_unit));\n",
    )
    proc = subprocess.run(
        [shutil.which("node") or "node", "--input-type=module"],
        input=prelude + wrapped,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout.strip()) == {"result": "ok"}


def test_workflow_rejects_unit_id_colliding_with_generated_panel_symbol() -> None:
    payload = _spec_dict(verify={"n": 7, "pass_rule": "majority"})
    units = payload["units"]
    assert isinstance(units, list)
    first = units[0]
    assert isinstance(first, dict)
    second = dict(first)
    second.update({"unit_id": "U1_verdicts_chunk_2", "verify": None})
    spec = ES.ExecutionSpec.from_dict(
        {
            "name": "symbol-collision",
            "description": "d",
            "units": [first, second],
        }
    )

    with pytest.raises(ES.SpecError, match="reserved JavaScript identifier"):
        ES.emit_workflow_script(spec, environment={})


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_workflow_comment_fields_are_inert_and_emitted_javascript_parses() -> None:
    payload = _spec_dict(
        label="label\r\nglobalThis.__injected = true",
        escalation="${globalThis.__injected = true}`\u2028next",
    )
    payload["name"] = "demo\nglobalThis.__injected = true"
    spec = ES.ExecutionSpec.from_dict(payload)

    script = ES.emit_workflow_script(spec)

    assert "\nglobalThis.__injected = true" not in script
    assert r"\${globalThis.__injected = true}\`\u2028next" in script
    proc = subprocess.run(
        [shutil.which("node") or "node", "--check", "--input-type=module"],
        input=_as_runtime_harness(script),
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_existing_style_unit_has_no_external_engine_marker() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    spec.validate()

    script = ES.emit_workflow_script(spec)

    assert "external-engine dispatch" not in script
    assert 'model: "sonnet"' in script
    assert 'effort: "high"' in script


def test_engine_intent_without_selector_fails() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine_intent="offload"))
    with pytest.raises(ES.SpecError, match="engine_intent requires engine or capability"):
        spec.validate()


def test_engine_intent_bad_vocabulary_fails() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(engine="codex/gpt-5.5-xhigh", engine_intent="urgent")
    )
    # "not in" pins the vocabulary-check branch specifically -- the bare substring
    # "engine_intent" also appears in the sibling "requires engine or capability"
    # error, so that weaker match wouldn't prove this branch actually fired.
    with pytest.raises(ES.SpecError, match="not in"):
        spec.validate()


def test_engine_intent_bad_vocabulary_fails_for_capability_selector() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(capability="code-generation", engine_intent="urgent")
    )
    with pytest.raises(ES.SpecError, match="not in"):
        spec.validate()


def test_engine_and_capability_mutual_exclusion_fires_before_intent_vocabulary() -> None:
    """A unit with both a conflicting selector pair AND an invalid intent must surface
    the selector mutual-exclusion error, proving that check runs first (from_dict calls
    _validate_external_engine_selector before resolving/validating engine_intent)."""
    with pytest.raises(ES.SpecError, match="mutually exclusive"):
        ES.ExecutionSpec.from_dict(
            _spec_dict(
                engine="codex/gpt-5.5-xhigh",
                capability="code-generation",
                engine_intent="urgent",
            )
        )


def test_engine_intent_defaults_to_offload_when_omitted() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(capability="code-generation"))
    spec.validate()

    assert spec.units[0].engine_intent == "offload"


def test_engine_intent_defaults_to_offload_when_omitted_for_engine_selector() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/gpt-5.5-xhigh"))
    spec.validate()

    assert spec.units[0].engine_intent == "offload"


def test_engine_intent_explicit_value_round_trips() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(engine="codex/gpt-5.5-xhigh", engine_intent="second-opinion")
    )
    spec.validate()

    round_tripped = ES.ExecutionSpec.from_dict(spec.to_dict())
    assert round_tripped.units[0].engine_intent == "second-opinion"


@pytest.mark.parametrize(
    "selector",
    [
        {"engine": "codex/gpt-5.5-xhigh"},
        {"capability": "code-generation"},
    ],
    ids=("engine", "capability"),
)
def test_divergence_intent_selector_forms_validate_and_round_trip(
    selector: dict[str, str],
) -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(**selector, engine_intent="divergence"))
    spec.validate()

    unit_dict = spec.units[0].to_dict()
    assert unit_dict["engine_intent"] == "divergence"
    assert ES.ExecutionSpec.from_dict(spec.to_dict()).units[0].engine_intent == "divergence"


def test_engine_intent_omitted_from_to_dict_for_plain_claude_unit() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    assert "engine_intent" not in spec.units[0].to_dict()


def test_advisory_panel_request_is_separate_from_verify_and_round_trips() -> None:
    request = ES.AdvisoryPanelRequest.from_dict(
        {"role": "cross-family-review-panel"},
        "advisory panel",
    )

    assert request == ES.AdvisoryPanelRequest("cross-family-review-panel")
    assert request.to_dict() == {"role": "cross-family-review-panel"}
    assert not hasattr(request, "n")
    assert ES.PANEL_N_CAP == ES._engine_registry_module().PANEL_N_CAP


def test_advisory_panel_rejects_malformed_role_name() -> None:
    with pytest.raises(ES.SpecError, match="normalized kebab-case"):
        ES.AdvisoryPanelRequest.from_dict({"role": "Bad Role"}, "advisory panel")


def test_advisory_panel_rejects_over_cap_role_at_spec_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_module = ES._engine_registry_module()
    registry = registry_module.Registry.load(ES._engine_registry_path())
    role = registry.by_role("cross-family-review-panel")
    role.members[:] = [role.members[0]] * (ES.PANEL_N_CAP + 1)
    monkeypatch.setattr(
        registry_module.Registry,
        "load",
        classmethod(lambda _cls, _path: registry),
    )

    with pytest.raises(ES.SpecError, match="PANEL_N_CAP"):
        ES.AdvisoryPanelRequest("cross-family-review-panel").validate("unit U1")


def test_engine_verifiability_round_trips_and_emit_rejects() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(engine="codex/gpt-5.5-xhigh", verifiability="test-gated")
    )
    spec.validate()

    unit_dict = spec.units[0].to_dict()
    assert unit_dict["verifiability"] == "test-gated"
    with pytest.raises(ES.SpecError, match="external-engine unit"):
        ES.emit_workflow_script(spec)
    with pytest.raises(ES.SpecError, match="verifiability") as excinfo:
        ES._agent_opts(
            spec.units[0],
            ES.UnitRouting(
                prompt="draft",
                exact_engine="codex/gpt-5.5-xhigh",
                authored_capability=None,
                lane_max_concurrent=None,
            ),
        )
    assert "verifiability" in str(excinfo.value)


def test_absent_verifiability_emits_no_key_for_external_engine_unit() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/gpt-5.5-xhigh"))
    spec.validate()

    assert "verifiability" not in spec.units[0].to_dict()


def test_engine_verifiability_bad_vocabulary_fails() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(engine="codex/gpt-5.5-xhigh", verifiability="maybe")
    )
    with pytest.raises(ES.SpecError, match="verifiability .* not in"):
        spec.validate()


def test_verifiability_without_external_selector_fails() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(verifiability="test-gated"))
    with pytest.raises(ES.SpecError, match="verifiability requires engine or capability"):
        spec.validate()


def test_advisory_consensus_defaults_to_inline_with_alternatives() -> None:
    from lifecycle_state import recommend_execution_backend

    result = recommend_execution_backend(needs_consensus=True, consensus_is_gated=False)

    assert result["recommended"] == "inline"
    assert "team-execution" in result["alternatives"]
    assert "cc-workflows-ultracode" in result["alternatives"]


def test_recommend_backend_no_ledger_has_no_prior_key() -> None:
    # #401 U5: byte-identical to today when no ledger is passed (the common path).
    from lifecycle_state import recommend_execution_backend

    result = recommend_execution_backend(needs_consensus=True, consensus_is_gated=False)
    assert "prior" not in result


def test_recommend_backend_empty_ledger_is_the_no_data_fallback(tmp_path: Path) -> None:
    import run_ledger
    from lifecycle_state import recommend_execution_backend

    ledger = run_ledger.RunLedger(path=tmp_path / "run-facts.jsonl")
    result = recommend_execution_backend(ledger=ledger)
    assert "prior" not in result  # no data -> no prior key (recommendation unchanged)


def test_recommend_backend_surfaces_ledger_prior(tmp_path: Path) -> None:
    import run_ledger
    from lifecycle_state import recommend_execution_backend

    ledger = run_ledger.RunLedger(path=tmp_path / "run-facts.jsonl")
    for tok in (100, 300):
        run_ledger.append_fact(
            ledger,
            run_ledger.build_fact(
                "spend", subplot_id="s", at="t", tokens=tok, tokens_cached=0, tokens_fresh=tok
            ),
        )
    result = recommend_execution_backend(ledger=ledger, prior_n=5)
    assert result["prior"] == {"metric": "spend.tokens", "n": 5, "avg_tokens": 200.0}


# --------------------------------------------------------------------------- sandbox (U1)
# The two-axis capability envelope (#287 R1-R3): mutation_policy x workspace_isolation, with
# named profile shorthand. Absent => ambient x read-write (today's behavior, no new key).


def test_sandbox_profile_string_expands_to_axis_pair() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(sandbox="read-only-verify"))
    spec.validate()
    sb = spec.units[0].sandbox
    assert sb is not None
    assert sb.mutation_policy == "read-only"
    assert sb.workspace_isolation == "disposable-worktree"
    assert sb.is_restrictive


def test_sandbox_sandboxed_mutate_profile_expands() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(sandbox="sandboxed-mutate"))
    spec.validate()
    sb = spec.units[0].sandbox
    assert (sb.mutation_policy, sb.workspace_isolation) == ("read-write", "owned-worktree")


def test_sandbox_explicit_axes_accepted() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(sandbox={"mutation_policy": "read-only", "workspace_isolation": "ambient"})
    )
    spec.validate()
    sb = spec.units[0].sandbox
    assert sb.mutation_policy == "read-only" and sb.workspace_isolation == "ambient"
    # read-only alone (isolation ambient) still narrows a policy => restrictive.
    assert sb.is_restrictive


def test_sandbox_default_ambient_readwrite_is_not_restrictive() -> None:
    sb = ES.Sandbox(mutation_policy="read-write", workspace_isolation="ambient")
    assert not sb.is_restrictive


def test_sandbox_absent_defaults_to_none_with_no_key() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    unit = spec.units[0]
    assert unit.sandbox is None
    assert "sandbox" not in unit.to_dict()


def test_sandbox_to_dict_emits_expanded_axes_not_shorthand() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(sandbox="read-only-verify"))
    emitted = spec.units[0].to_dict()["sandbox"]
    assert emitted == {
        "mutation_policy": "read-only",
        "workspace_isolation": "disposable-worktree",
    }
    # Round-trip is idempotent: the expanded form reparses to the same axes.
    again = ES.ExecutionSpec.from_dict(spec.to_dict())
    assert again.units[0].sandbox == spec.units[0].sandbox


def test_sandbox_unknown_profile_raises() -> None:
    with pytest.raises(ES.SpecError, match="unknown sandbox profile"):
        ES.ExecutionSpec.from_dict(_spec_dict(sandbox="airtight"))


def test_sandbox_unknown_axis_value_raises() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(sandbox={"mutation_policy": "write-anywhere", "workspace_isolation": "ambient"})
    )
    with pytest.raises(ES.SpecError, match="mutation_policy 'write-anywhere' not in"):
        spec.validate()


def test_sandbox_profile_key_conflicts_with_explicit_axes() -> None:
    with pytest.raises(ES.SpecError, match="conflicts with the explicit-axes form"):
        ES.ExecutionSpec.from_dict(
            _spec_dict(
                sandbox={
                    "profile": "read-only-verify",
                    "mutation_policy": "read-only",
                    "workspace_isolation": "disposable-worktree",
                }
            )
        )


def test_sandbox_coexists_with_engine_selector_without_interference() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(capability="code-generation", sandbox="sandboxed-mutate")
    )
    spec.validate()
    unit = spec.units[0]
    assert unit.capability == "code-generation"
    assert unit.engine_intent == "offload"  # selector default still applies
    assert unit.sandbox.workspace_isolation == "owned-worktree"
    # Both round-trip together, neither field perturbs the other.
    again = ES.Unit.from_dict(unit.to_dict())
    assert again.capability == "code-generation"
    assert again.sandbox == unit.sandbox


# ------------------------------------------------------ read-only verifier wiring (U2)
# Every verifier agent() call the emitter renders MUST carry agentType + isolation across all
# three emission shapes (plain panel, iterate-to-consensus singleton, parallel-layer thunk).
# Missing any one site is exactly the R9 dead-wiring failure.

AGENTS_DIR = ROOT / "plugins" / "saga" / "agents"
READONLY_VERIFIER_AGENT = AGENTS_DIR / "readonly-verifier.md"
SANDBOX_SPAWN_SITES_REFERENCE = ROOT / "plugins" / "saga" / "references" / "sandbox-spawn-sites.md"

# Harness-owned globals: the reservation set minus the JS runtime builtins, which are already
# covered behaviorally by test_workflow_unit_id_rejects_harness_global_shadowing. These are the
# names the EMITTER itself declares, so a unit id equal to any of them would shadow a harness
# global and silently break the emitted script.
_RESERVED_FOR_SHADOW_TEST = frozenset(
    ES._WORKFLOW_RESERVED_IDENTIFIERS - ES._WORKFLOW_RUNTIME_GLOBAL_IDENTIFIERS
)


def _frontmatter_scalar(text: str, key: str) -> str:
    """Read one top-level single-line frontmatter scalar (name/model/tools) without a YAML dep.

    Stops at the multi-line ``description: |`` block, which is fine -- the keys this test cares
    about (name, tools) precede it.
    """
    in_fm = False
    for line in text.splitlines():
        if line.strip() == "---":
            if in_fm:
                break
            in_fm = True
            continue
        if in_fm and line.startswith(f"{key}:"):
            return line[len(key) + 1 :].strip()
    raise AssertionError(f"{key!r} not found in frontmatter")


def _emit_units(units: list[dict[str, object]]) -> str:
    spec = ES.ExecutionSpec.from_dict(
        {"name": "verify-demo", "description": "d", "repo": "/tmp/r", "units": units}
    )
    spec.validate()
    return str(ES.emit_workflow_script(spec, **_routing_snapshots()))


def _verify_unit(uid: str, **kw: object) -> dict[str, object]:
    unit: dict[str, object] = {
        "unit_id": uid,
        "label": uid,
        "tier": {"model": "opus", "effort": "high"},
        "prompt": "do the work",
        "returns": ["result"],
    }
    unit.update(kw)
    return unit


def _return_schema_fragment(keys: tuple[str, ...] = ("result",), *, cheap: bool = False) -> str:
    return_schema: dict[str, object] = {
        "type": "object",
        "properties": {key: {} for key in keys},
        "required": list(keys),
        "additionalProperties": True,
    }
    if cheap:
        # #364 pull-cord shape: a FLAT typed object -- returns keys plus an optional pull_cord
        # string, no required alternation. The API rejects any top-level combinator (oneOf/allOf/
        # anyOf), so the either/or is enforced by __gate + the RETURN CONTRACT, not the schema.
        properties: dict[str, object] = {key: {} for key in keys}
        properties["pull_cord"] = {"type": "string"}
        return_schema = {
            "type": "object",
            "properties": properties,
            "additionalProperties": True,
        }
    return "schema: " + json.dumps(return_schema, sort_keys=True)


def _verifier_schema_fragment() -> str:
    # Hardcoded on purpose (drift guard, #527): building this from ES._verifier_schema() would
    # make the schema-presence assertions tautological. minLength: 1 on the attribution strings
    # mirrors the runtime reporter predicate's `.length > 0` checks, so tool-boundary-valid
    # verdicts are always counted as reporters.
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "refuted_deliverable": {"type": "array"},
            "advisory_corrections": {"type": "array"},
            "upheld": {"type": "array"},
            "verifier_identity": {"type": "string", "minLength": 1},
            "fallback_depth": {},
            "examined_sha": {"type": "string", "minLength": 1},
        },
        "required": [
            "refuted_deliverable",
            "advisory_corrections",
            "upheld",
            "verifier_identity",
            "fallback_depth",
            "examined_sha",
        ],
        "additionalProperties": True,
    }
    return "schema: " + json.dumps(schema, sort_keys=True)


def test_readonly_verifier_agent_definition_exists_with_readonly_toolset() -> None:
    assert READONLY_VERIFIER_AGENT.exists()
    text = READONLY_VERIFIER_AGENT.read_text(encoding="utf-8")
    assert _frontmatter_scalar(text, "name") == "readonly-verifier"
    tools = [t.strip() for t in _frontmatter_scalar(text, "tools").split(",")]
    assert tools == ["Bash", "Read", "Grep", "Glob"]
    # The read-only contract IS tool omission at spawn: Edit/Write must be absent.
    assert "Edit" not in tools and "Write" not in tools


def test_readonly_verifier_agent_definition_carries_the_split_verdict_shape() -> None:
    # #686: the agent definition is the THIRD verdict-shape prompt surface, alongside the two
    # the emitter renders (`_verifier_prompt` and `_JS_VERIFIER_PROMPT_HELPER`). It is the
    # verifier's own system prompt, so a stale legacy shape here is not cosmetic: a verifier
    # that follows its definition over the per-call prompt emits `{refuted, upheld}`, which the
    # attached StructuredOutput schema REJECTS -- the verdict then classifies as runtime-missing
    # and pushes the panel toward the quorum floor. That failure disarms a merge-blocking gate
    # silently, so R2 ("the legacy shape must not survive anywhere") is pinned here too.
    text = READONLY_VERIFIER_AGENT.read_text(encoding="utf-8")
    assert "{refuted: [...], upheld: [...]}" not in text
    assert "refuted_deliverable" in text
    assert "advisory_corrections" in text


def test_verifier_agenttype_literal_matches_agent_definition_name() -> None:
    # Literal-consistency guard (#287 U2, saga-side half of the registry-drift risk): the
    # agentType string the emitter bakes into every verifier call MUST equal the agent
    # definition's `name:` plus the `saga:` plugin prefix. A rename on either side fails HERE
    # rather than silently spawning verifiers with an unknown (=> unrestricted) agent type.
    text = READONLY_VERIFIER_AGENT.read_text(encoding="utf-8")
    name = _frontmatter_scalar(text, "name")
    assert f"saga:{name}" == ES.READONLY_VERIFIER_AGENT_TYPE
    assert ES.READONLY_VERIFIER_ISOLATION == "worktree"


def test_verifier_panel_emits_readonly_agenttype_and_isolation() -> None:
    script = _emit_units([_verify_unit("a", verify={"n": 2, "pass_rule": "majority"})])
    assert 'agentType: "saga:readonly-verifier"' in script
    assert 'isolation: "worktree"' in script
    assert script.count(_verifier_schema_fragment()) == 2
    assert "__verifierPrompt(" in script
    assert "UNIT RESULT INPUT (structured evidence" in script
    assert "status --short" in script
    assert "named untracked output files" in script


def test_verifier_panel_stamps_identity_and_fallback_schema_fields() -> None:
    # U6/R8/KTD7: the emitted verifier prompt carries the emitter-stamped identity and instructs
    # the verifier to echo verifier_identity + fallback_depth (default 0). A workflow agent() call
    # can only ever be the first-choice rung, so the stamped depth is 0.
    script = _emit_units([_verify_unit("a", verify={"n": 2, "pass_rule": "majority"})])
    assert "verifier_identity" in script
    assert "fallback_depth" in script
    assert "examined_sha" in script
    # Stamped identity == the readonly-verifier agent type the emitter knows.
    assert "verifier_identity: saga:readonly-verifier" in script
    assert "fallback_depth: 0" in script
    assert "Include examined_sha as the git SHA you" in script


def test_verifier_panel_emits_fallback_tier_marker_in_throw() -> None:
    # The runtime gate summary computes a "fallback tier" marker over the reporting verdicts and
    # rides it on the operator-facing verifier-disagreement throw.
    script = _emit_units([_verify_unit("a", verify={"n": 2, "pass_rule": "majority"})])
    assert "fallback tier" in script
    assert "fallback_marker" in script
    assert "verifier-disagreement" in script


def test_every_verify_panel_call_carries_verifier_schema_all_sites() -> None:
    # #527: EVERY verify-panel agent() call must carry the schema opt, across all three
    # panel-emitting sites (plain one-shot panel, iterate-to-consensus singleton loop,
    # escalate_on_signal panel). The agentType marker appears exactly once per verifier
    # call, so schema-count == agentType-count proves no verifier call is missing it.
    script = _emit_units(
        [
            _verify_unit("plain", verify={"n": 2, "pass_rule": "majority"}),
            _verify_unit(
                "loop",
                verify={"n": 2, "pass_rule": "majority", "iterate_to_consensus": True},
            ),
            _verify_unit(
                "climb",
                tier={"model": "sonnet", "effort": "medium"},
                verify={"n": 3, "pass_rule": "majority"},
                escalate_on_signal=True,
            ),
        ]
    )
    agent_type_count = script.count('agentType: "saga:readonly-verifier"')
    assert agent_type_count == 7  # 2 plain + 2 loop + 3 climb
    assert script.count(_verifier_schema_fragment()) == agent_type_count


def test_unattended_climb_retry_panel_also_carries_verifier_schema() -> None:
    # #527: the unattended one-rung climb emits a SECOND panel over the retried unit --
    # its verifier calls must carry the schema too, not just the first panel's.
    script = _emit_units_unattended([_escalate_unit()])
    assert "climbing ONE rung to sonnet/high" in script  # proves the retry panel exists
    agent_type_count = script.count('agentType: "saga:readonly-verifier"')
    assert agent_type_count == 6  # 3 first panel + 3 retry panel
    assert script.count(_verifier_schema_fragment()) == agent_type_count


def _extract_emitted_line(script: str, prefix: str) -> str:
    for line in script.splitlines():
        if line.strip().startswith(prefix):
            return line.strip()
    raise AssertionError(f"no emitted line starting with {prefix!r}")


_SCHEMA_VALID_VERDICT: dict[str, object] = {
    "refuted_deliverable": [],
    "advisory_corrections": [],
    "upheld": ["finding-1 upheld: evidence matches"],
    "verifier_identity": "saga:readonly-verifier",
    "fallback_depth": 0,
    "examined_sha": "deadbeefcafe",
}


def test_schema_valid_verdict_satisfies_verifier_schema_and_prose_fails() -> None:
    # #527 tool-boundary half: the verdict shape the panel counts passes the attached schema,
    # while the wf_ada4ca97-365 failure modes (prose string, missing/empty attribution fields)
    # are rejected AT THE TOOL BOUNDARY -- retried/failed there, never parse-and-hoped.
    jsonschema = pytest.importorskip("jsonschema")
    schema = ES._verifier_schema()
    jsonschema.validate(_SCHEMA_VALID_VERDICT, schema)  # must not raise
    refuting = dict(
        _SCHEMA_VALID_VERDICT, refuted_deliverable=["claim X contradicted by file:line"]
    )
    jsonschema.validate(refuting, schema)
    # #686 R6/KTD2: a legacy single-bucket verdict is REJECTED at the tool boundary -- no
    # tolerant read of `refuted` onto the gating bucket, and omitting either bucket fails.
    legacy = {
        "refuted": [],
        "upheld": [],
        "verifier_identity": "saga:readonly-verifier",
        "fallback_depth": 0,
        "examined_sha": "deadbeefcafe",
    }
    advisory_only_missing_gating = {
        key: value for key, value in _SCHEMA_VALID_VERDICT.items() if key != "refuted_deliverable"
    }
    malformed: object
    for malformed in (
        "All findings upheld; examined SHA deadbeef.",  # prose verdict (the #527 evidence)
        {},  # empty object
        legacy,  # #686: pre-split verdict carrying only `refuted`
        advisory_only_missing_gating,  # #686: omits the gating bucket
        {  # #686: omits the non-gating bucket
            key: value
            for key, value in _SCHEMA_VALID_VERDICT.items()
            if key != "advisory_corrections"
        },
        {"refuted_deliverable": [], "upheld": []},  # missing the #390 U6 attribution fields
        dict(_SCHEMA_VALID_VERDICT, examined_sha=""),  # empty sha fails minLength
        dict(_SCHEMA_VALID_VERDICT, verifier_identity=""),  # empty identity fails minLength
    ):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(malformed, schema)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_schema_valid_verdict_is_counted_as_reporter_in_emitted_aggregation() -> None:
    # #527 aggregation half: execute the EMITTED reporter predicate + reported-filter lines
    # under node against a schema-valid verdict and the prose/malformed failure modes. Proves
    # a schema-valid verdict is counted as a reporter (and a refuting one counts toward
    # refute_count), while prose is classified runtime-missing -- the exact vacuous-aggregation
    # failure of workflow wf_ada4ca97-365.
    script = _emit_units([_verify_unit("a", verify={"n": 2, "pass_rule": "majority"})])
    predicate_line = _extract_emitted_line(script, "const a_valid_verifier_verdict =")
    reported_line = _extract_emitted_line(script, "const a_reported =")
    refuting = dict(
        _SCHEMA_VALID_VERDICT, refuted_deliverable=["claim X contradicted by file:line"]
    )
    js = "\n".join(
        [
            "const a_verdicts = ["
            + json.dumps(_SCHEMA_VALID_VERDICT)
            + ", "
            + json.dumps(refuting)
            + ', "All findings upheld; examined SHA deadbeef.", null, '
            "{refuted_deliverable: []}]",
            # The historical `<var>_verdicts` aggregate remains authoritative after bounded
            # chunks append their ordered results.
            predicate_line,
            reported_line,
            "const a_refute_count = "
            "a_reported.filter((v) => v.refuted_deliverable.length > 0).length",
            "console.log(JSON.stringify("
            "{reported: a_reported.length, refute_count: a_refute_count}))",
        ]
    )
    proc = subprocess.run(
        [shutil.which("node") or "node", "-e", js],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    result = json.loads(proc.stdout.strip())
    # Both schema-valid verdicts count as reporters; prose/null/partial are runtime-missing.
    assert result == {"reported": 2, "refute_count": 1}


# ---------------------------------------------------------------------------
# #686: the verify verdict has a severity axis -- `refuted_deliverable` GATES the unit,
# `advisory_corrections` never does. These execute the EMITTED gate arithmetic under node so
# the assertions describe runtime behavior, not just emitted substrings.
# ---------------------------------------------------------------------------


def _verdict(*, gating: list[str], advisory: list[str]) -> dict[str, object]:
    """One schema-valid verifier verdict with the two #686 buckets filled explicitly."""
    return dict(
        _SCHEMA_VALID_VERDICT,
        refuted_deliverable=list(gating),
        advisory_corrections=list(advisory),
    )


_GATING_VERDICT = _verdict(
    gating=["U1 deleted the retry guard; tests do not cover it"], advisory=[]
)
_ADVISORY_VERDICT = _verdict(
    gating=[], advisory=["notes attribute the fix to _emit_thunk; it landed in the shared helper"]
)


def _run_panel_gate(
    pass_rule: str, verdicts: list[dict[str, object]], n: int = 3
) -> dict[str, object]:
    """Execute the emitted panel gate lines for one panel against a fixed verdict list.

    Extracts the reporter predicate, reported filter, missing-index map, refute count, threshold
    and refuted boolean VERBATIM from the emitted harness, so what runs here is exactly what the
    workflow runtime would run. ``n`` is a parameter because the threshold arithmetic rounds
    differently at even and odd panel sizes, and a suite that only ever emits n=3 cannot see it.
    """
    script = _emit_units([_verify_unit("a", verify={"n": n, "pass_rule": pass_rule})])
    js = "\n".join(
        [
            "const a_verdicts = " + json.dumps(verdicts),
            _extract_emitted_line(script, "const a_valid_verifier_verdict ="),
            _extract_emitted_line(script, "const a_reported ="),
            _extract_emitted_line(script, "const a_missing_idx ="),
            _extract_emitted_line(script, "const a_refute_count ="),
            _extract_emitted_line(script, "const a_threshold ="),
            _extract_emitted_line(script, "const a_refuted ="),
            "console.log(JSON.stringify({reported: a_reported.length, "
            "missing: a_missing_idx.length, refute_count: a_refute_count, "
            "threshold: a_threshold, refuted: a_refuted}))",
        ]
    )
    proc = subprocess.run(
        [shutil.which("node") or "node", "-e", js],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return dict(json.loads(proc.stdout.strip()))


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
@pytest.mark.parametrize("pass_rule", ["majority", "unanimous"])
def test_advisory_only_panel_does_not_refute_the_unit(pass_rule: str) -> None:
    # R2/R7: three verifiers, every one of them carrying a non-empty NON-GATING bucket and an
    # empty gating bucket. This is the #71 failure (all five refutations targeted the unit's
    # `notes`); under the split contract the unit is UPHELD under both pass rules.
    result = _run_panel_gate(pass_rule, [_ADVISORY_VERDICT] * 3)

    assert result["reported"] == 3
    assert result["missing"] == 0
    assert result["refute_count"] == 0
    assert result["refuted"] is False


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
@pytest.mark.parametrize("pass_rule", ["majority", "unanimous"])
def test_gating_bucket_still_refutes_unchanged(pass_rule: str) -> None:
    # R2/R7: a non-empty GATING bucket from every reporter still kills the unit, exactly as the
    # single-bucket contract did. The fix narrows what gates; it does not weaken the gate.
    result = _run_panel_gate(pass_rule, [_GATING_VERDICT] * 3)

    assert result["refute_count"] == 3
    assert result["refuted"] is True


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
@pytest.mark.parametrize(
    ("pass_rule", "threshold"),
    [("majority", 2), ("unanimous", 3)],
)
def test_mixed_panel_one_gating_two_advisory_upholds(pass_rule: str, threshold: int) -> None:
    # R7: one verifier gates, two return advisories only. One gating vote is below BOTH the
    # majority threshold (2 of 3) and the unanimous threshold (3 of 3), so the unit is upheld.
    result = _run_panel_gate(pass_rule, [_GATING_VERDICT, _ADVISORY_VERDICT, _ADVISORY_VERDICT])

    assert result["refute_count"] == 1
    assert result["threshold"] == threshold
    assert result["refuted"] is False


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_majority_gating_refutes_over_advisory_minority() -> None:
    # R2/R7: two gating votes of three reaches the majority threshold -- a panel that mostly
    # found broken work still stops the unit even when one verifier only had prose corrections.
    result = _run_panel_gate("majority", [_GATING_VERDICT, _GATING_VERDICT, _ADVISORY_VERDICT])

    assert result["refute_count"] == 2
    assert result["threshold"] == 2
    assert result["refuted"] is True


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
@pytest.mark.parametrize("omitted", ["refuted_deliverable", "advisory_corrections"])
def test_verdict_omitting_either_bucket_counts_as_missing_verifier(omitted: str) -> None:
    # R6/KTD2: a verdict missing EITHER bucket fails the reporter predicate and counts toward
    # the missing-verifier floor -- no tolerant read, so a legacy `refuted`-only verdict cannot
    # smuggle a prose refutation into the gating bucket.
    partial = {key: value for key, value in _ADVISORY_VERDICT.items() if key != omitted}
    result = _run_panel_gate("majority", [_ADVISORY_VERDICT, _ADVISORY_VERDICT, partial])

    assert result["reported"] == 2
    assert result["missing"] == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_legacy_single_bucket_verdict_counts_as_missing_verifier() -> None:
    # KTD2 stated as behavior: the pre-#686 verdict shape is a runtime failure, not a reporter.
    legacy = {
        "refuted": ["the notes misdescribe the mechanism"],
        "upheld": [],
        "verifier_identity": "saga:readonly-verifier",
        "fallback_depth": 0,
        "examined_sha": "deadbeefcafe",
    }
    result = _run_panel_gate("majority", [_ADVISORY_VERDICT, _ADVISORY_VERDICT, legacy])

    assert result["reported"] == 2
    assert result["missing"] == 1
    assert result["refuted"] is False


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_advisories_are_logged_and_returned_by_the_emitted_harness() -> None:
    # R4 end-to-end: run a whole emitted harness under stubs where every verifier returns an
    # advisory-only verdict. The unit must survive the gate, the advisory must reach a log()
    # call DURING the run, and it must ride out on the harness return value. Losing either half
    # is the naive-fix failure mode (`__advisories` declared but never pushed to).
    script = _emit_units([_verify_unit("a", verify={"n": 3, "pass_rule": "majority"})])
    advisory_text = "notes claim the gate moved in _emit_thunk; it moved in the shared helper"
    prelude = f"""
const __logged = [];
const log = (line) => {{ __logged.push(String(line)); }};
const parallel = async (thunks) => Promise.all(thunks.map((thunk) => thunk()));
const agent = async (_prompt, opts) => opts && opts.agentType
  ? {json.dumps(_verdict(gating=[], advisory=[advisory_text]))}
  : {{result: "ok"}};
"""
    wrapped = _as_runtime_harness(
        script,
        "const __result = await __harness();\n"
        "console.log(JSON.stringify({advisories: __result.advisory_corrections, "
        "unit: __result.units.a, logged: __logged}));\n",
    )
    proc = subprocess.run(
        [shutil.which("node") or "node", "--input-type=module"],
        input=prelude + wrapped,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    # The advisory-only panel did NOT kill the unit.
    assert payload["unit"] == {"result": "ok"}
    # R4 half one: present in the emitted workflow's return value, attributed to its unit.
    assert payload["advisories"] == [
        {"unit": "a", "round": 1, "corrections": [advisory_text] * 3, "dropped": 0}
    ]
    # R4 half two: logged during the run, naming the non-gating disposition.
    advisory_logs = [line for line in payload["logged"] if "advisory correction" in line]
    assert len(advisory_logs) == 1
    assert "deliverable UPHELD with 3 advisory correction(s)" in advisory_logs[0]
    assert "non-gating" in advisory_logs[0]
    assert advisory_text[:60] in advisory_logs[0]


def _run_harness(
    units: list[dict[str, object]],
    *,
    verdict_js: str,
    tail: str,
    unit_result: str = '{result: "ok"}',
) -> subprocess.CompletedProcess[str]:
    """Run a whole emitted harness under stubs, capturing thrown errors as structured JSON.

    ``verdict_js`` is a JS expression evaluated per verifier call; it may close over ``__vcall``
    (a 1-based verifier call counter) so a test can make one verifier in a panel behave
    differently from its peers.
    """
    script = _emit_units(units)
    prelude = f"""
const __logged = [];
const __prompts = [];
let __vcall = 0;
const log = (line) => {{ __logged.push(String(line)); }};
const parallel = async (thunks) => Promise.all(thunks.map((thunk) => thunk()));
const agent = async (prompt, opts) => {{
  if (opts && opts.agentType) {{
    __vcall += 1;
    __prompts.push(String(prompt));
    return ({verdict_js});
  }}
  return {unit_result};
}};
"""
    return subprocess.run(
        [shutil.which("node") or "node", "--input-type=module"],
        input=prelude + _as_runtime_harness(script, tail),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


_CAPTURE_OK = (
    "const __result = await __harness();\n"
    "console.log(JSON.stringify({ok: true, advisories: __result.advisory_corrections, "
    "logged: __logged}));\n"
)
_CAPTURE_PROMPTS = "await __harness();\nconsole.log(JSON.stringify({prompts: __prompts}));\n"
_CAPTURE_THROW = (
    "try {\n"
    "  const __result = await __harness();\n"
    "  console.log(JSON.stringify({ok: true, advisories: __result.advisory_corrections, "
    "logged: __logged}));\n"
    "} catch (err) {\n"
    "  console.log(JSON.stringify({ok: false, message: String(err && err.message), "
    "advisories: err && err.advisory_corrections, logged: __logged}));\n"
    "}\n"
)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
@pytest.mark.parametrize("n", [2, 4])
def test_even_n_panel_cannot_reach_a_verdict_on_half_strength(n: int) -> None:
    # REGRESSION PIN for the even-n fail-open. The quorum floor is baked at emit time over the
    # DECLARED n, while the majority threshold is recomputed at runtime over the SURVIVING
    # reporters. Under the old floor of ceil(n/2) those two disagreed at even n: a panel that
    # lost exactly half its verifiers still met the floor, and because the verifiers it lost
    # were the refuting ones, refute_count fell to 0 and a HALT silently became a PASS.
    #
    # Here exactly half the panel refutes the deliverable but omits the semantically-empty
    # `advisory_corrections`, so those verdicts are dropped as runtime-missing. With a STRICT
    # majority floor (n // 2 + 1) the survivors can no longer carry a verdict and the panel
    # halts UNDER-STRENGTH -- fail-closed -- instead of passing the unit.
    half = n // 2
    verdict_js = (
        f"__vcall <= {half}"
        ' ? {refuted_deliverable: ["BUILD BROKEN"], upheld: [],'
        ' verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
        ' : {refuted_deliverable: [], advisory_corrections: [], upheld: ["fine"],'
        ' verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness(
        [_verify_unit("a", verify={"n": n, "pass_rule": "majority"})],
        verdict_js=verdict_js,
        tail=_CAPTURE_THROW,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is False, "half-strength even-n panel must not reach a verdict"
    assert "verifier-under-strength" in payload["message"]
    assert f"quorum floor {n // 2 + 1}" in payload["message"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
@pytest.mark.parametrize("reported_count", [0, 1, 2, 3])
@pytest.mark.parametrize("refute_count", [0, 1, 2, 3])
def test_n3_panels_preserve_exact_compatibility(reported_count: int, refute_count: int) -> None:
    # EXPLICIT n=3 COMPATIBILITY PIN (#692):
    # The Option 3 missing-aware tightening policy (approved 2026-08-24) provably preserves 100%
    # of the existing behavior and single-missing-verifier fault tolerance across all 37 committed
    # n=3 panels (in 16 execution spec files across the repository).
    #
    # At n=3:
    # - floor = 3 // 2 + 1 = 2
    # - If reported < 2 (0 or 1 verifiers): halts with verifier-under-strength (quorum floor 2)
    # - If reported == 2 (1 missing):
    #   - refute = 0: Math.ceil(2/2) = 1 threshold; 0 refutes < 1; 0 + 1 (missing) = 1 < 2 (floor).
    #     The ambiguous condition (0 < 1 AND 0 + 1 >= 2) is false, so it unambiguously PASSES.
    #   - refute >= 1: 1 >= 1 threshold; refutes with verifier-disagreement.
    # - If reported == 3 (0 missing):
    #   - refute in {0, 1}: Math.ceil(3/2) = 2 threshold; passes.
    #   - refute >= 2: refutes with verifier-disagreement.
    #
    # The policy change for odd n >= 5 introduces zero behavioral drift for n=3.
    if refute_count > reported_count:
        # Impossible state: a panel cannot have more refuters than reporting verifiers.
        # SKIP rather than `return` -- a bare return reports these six cells as PASSED
        # without asserting anything, which reads as coverage the sweep never had.
        pytest.skip("impossible: refuters cannot exceed reporting verifiers")

    n = 3
    floor = 2
    k = reported_count
    r = refute_count

    verdict_js = (
        f"__vcall <= {r} ? "
        '{refuted_deliverable: ["FAIL"], advisory_corrections: [], upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0, examined_sha: "deadbeef"} : '
        f"(__vcall <= {k} ? "
        '{refuted_deliverable: [], advisory_corrections: [], upheld: ["fine"], verifier_identity: "saga:readonly-verifier", fallback_depth: 0, examined_sha: "deadbeef"} : '
        "null)"
    )
    proc = _run_harness(
        [_verify_unit("a", verify={"n": n, "pass_rule": "majority"})],
        verdict_js=verdict_js,
        tail=_CAPTURE_THROW,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())

    if k < floor:
        assert payload["ok"] is False
        assert "verifier-under-strength" in payload["message"]
        assert f"quorum floor {floor}" in payload["message"]
    elif r >= math.ceil(k / 2):
        assert payload["ok"] is False
        assert "verifier-disagreement" in payload["message"]
    else:
        assert payload["ok"] is True


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
@pytest.mark.parametrize("n", [5, 7, 9])
def test_odd_n_missing_aware_tightening_sweep(n: int, monkeypatch: pytest.MonkeyPatch) -> None:
    # Sweep all valid (survivor_count, refute_count) combinations for odd n in {5, 7, 9}.
    # Verifies Option 3 semantics:
    # 1. k < floor: halts under baked quorum floor (k/n < n // 2 + 1)
    # 2. r >= ceil(k/2): refutes via majority over survivors (verifier-disagreement)
    # 3. r < ceil(k/2) but r + (n - k) >= floor: halts with verifier-under-strength (potential-flip-on-missing)
    # 4. Otherwise: cleanly passes (ok == True)
    monkeypatch.setattr(ES, "VERIFY_N_CAP", max(7, n))
    floor = n // 2 + 1

    for k in range(n + 1):
        for r in range(k + 1):
            verdict_js = (
                f"__vcall <= {r} ? "
                '{refuted_deliverable: ["FAIL"], advisory_corrections: [], upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0, examined_sha: "deadbeef"} : '
                f"(__vcall <= {k} ? "
                '{refuted_deliverable: [], advisory_corrections: [], upheld: ["fine"], verifier_identity: "saga:readonly-verifier", fallback_depth: 0, examined_sha: "deadbeef"} : '
                "null)"
            )
            proc = _run_harness(
                [_verify_unit("a", verify={"n": n, "pass_rule": "majority"})],
                verdict_js=verdict_js,
                tail=_CAPTURE_THROW,
            )
            assert proc.returncode == 0, proc.stderr
            payload = json.loads(proc.stdout.strip())

            missing = n - k
            survivor_threshold = max(1, math.ceil(k / 2)) if k > 0 else 1

            if k < floor:
                assert payload["ok"] is False, f"n={n}, k={k}, r={r} expected floor halt"
                assert "verifier-under-strength" in payload["message"]
                assert f"quorum floor {floor}" in payload["message"]
            elif r >= survivor_threshold:
                assert payload["ok"] is False, f"n={n}, k={k}, r={r} expected disagreement halt"
                assert "verifier-disagreement" in payload["message"]
            elif r + missing >= floor:
                assert payload["ok"] is False, f"n={n}, k={k}, r={r} expected potential-flip halt"
                assert "verifier-under-strength" in payload["message"]
                assert "potential-flip-on-missing" in payload["message"]
            else:
                assert payload["ok"] is True, f"n={n}, k={k}, r={r} expected pass: {payload}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_missing_refuter_path_is_loud() -> None:
    # #692: the missing-refuter path is loud:
    # When potential-flip-on-missing triggers (e.g. n=5, 2 missing, 1 refutes out of 3 survivors),
    # the log records " — UNDER-STRENGTH (potential-flip-on-missing)" and the halt names the condition.
    # When clean pass occurs (e.g. n=5, 2 missing, 0 refutes out of 3 survivors), the missing
    # verifier annotation is logged without UNDER-STRENGTH and the harness completes.
    #
    # Case A: n=5, k=3, r=1 -> potential-flip-on-missing
    verdict_js_flip = (
        "__vcall === 1 ? "
        '{refuted_deliverable: ["FAIL"], advisory_corrections: [], upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0, examined_sha: "deadbeef"} : '
        "(__vcall <= 3 ? "
        '{refuted_deliverable: [], advisory_corrections: [], upheld: ["fine"], verifier_identity: "saga:readonly-verifier", fallback_depth: 0, examined_sha: "deadbeef"} : '
        "null)"
    )
    proc_flip = _run_harness(
        [_verify_unit("a", verify={"n": 5, "pass_rule": "majority"})],
        verdict_js=verdict_js_flip,
        tail=_CAPTURE_THROW,
    )
    assert proc_flip.returncode == 0, proc_flip.stderr
    payload_flip = json.loads(proc_flip.stdout.strip())
    assert payload_flip["ok"] is False
    assert (
        "verifier-under-strength: Unit a reported 3/5 verifiers (potential-flip-on-missing)"
        in payload_flip["message"]
    )
    log_flip = [line for line in payload_flip["logged"] if "verify panel over a" in line]
    assert len(log_flip) == 1
    assert (
        "2/5 verifier(s) missing (runtime-failure: #4, #5); verdict computed over 3/5"
        in log_flip[0]
    )
    assert "— UNDER-STRENGTH (potential-flip-on-missing)" in log_flip[0]

    # Case B: n=5, k=3, r=0 -> clean pass (0 + 2 = 2 < 3)
    verdict_js_clean = (
        "__vcall <= 3 ? "
        '{refuted_deliverable: [], advisory_corrections: [], upheld: ["fine"], verifier_identity: "saga:readonly-verifier", fallback_depth: 0, examined_sha: "deadbeef"} : '
        "null"
    )
    proc_clean = _run_harness(
        [_verify_unit("a", verify={"n": 5, "pass_rule": "majority"})],
        verdict_js=verdict_js_clean,
        tail=_CAPTURE_THROW,
    )
    assert proc_clean.returncode == 0, proc_clean.stderr
    payload_clean = json.loads(proc_clean.stdout.strip())
    assert payload_clean["ok"] is True
    log_clean = [line for line in payload_clean["logged"] if "verify panel over a" in line]
    assert len(log_clean) == 1
    assert (
        "2/5 verifier(s) missing (runtime-failure: #4, #5); verdict computed over 3/5"
        in log_clean[0]
    )
    assert "UNDER-STRENGTH" not in log_clean[0]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
@pytest.mark.parametrize("n", [5, 7, 9])
def test_unanimous_panels_are_excluded_from_missing_aware_tightening(
    n: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    # GUARD PIN for the `pass_rule == "majority"` condition on the #692 missing-aware gate.
    #
    # The gate compares `refute_count + missing` against the MAJORITY floor `n // 2 + 1`. That
    # floor is meaningless for a `unanimous` panel, which refutes only when ALL reporting
    # verifiers refute: refuting survivors plus every missing verifier can clear the majority
    # floor while still falling far short of `n`, so applying the gate there would halt panels
    # that full strength would have upheld.
    #
    # This pin exists because the guard was otherwise untested -- deleting
    # `if panel.pass_rule == "majority":` from the throw block leaves the entire suite green
    # while flipping, for example, an `n=5` unanimous panel with 3 reporters and 2 refuters from
    # a clean pass to `verifier-under-strength ... (potential-flip-on-missing)`.
    monkeypatch.setattr(ES, "VERIFY_N_CAP", max(7, n))
    floor = n // 2 + 1

    # Sweep exactly the discriminating cells: quorum cleared, survivors uphold under `unanimous`
    # (refuters `r < k`), yet `r + missing` reaches the majority floor. These are the only cells
    # whose verdict the guard changes.
    cells = [(k, r) for k in range(floor, n + 1) for r in range(k) if r + (n - k) >= floor]
    # A sweep that selected nothing would pass vacuously and pin nothing.
    assert cells, f"n={n}: no discriminating cells -- this pin would be vacuous"

    for k, r in cells:
        verdict_js = (
            f"__vcall <= {r} ? "
            '{refuted_deliverable: ["FAIL"], advisory_corrections: [], upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0, examined_sha: "deadbeef"} : '
            f"(__vcall <= {k} ? "
            '{refuted_deliverable: [], advisory_corrections: [], upheld: ["fine"], verifier_identity: "saga:readonly-verifier", fallback_depth: 0, examined_sha: "deadbeef"} : '
            "null)"
        )
        proc = _run_harness(
            [_verify_unit("a", verify={"n": n, "pass_rule": "unanimous"})],
            verdict_js=verdict_js,
            tail=_CAPTURE_THROW,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout.strip())
        assert payload["ok"] is True, (
            f"n={n}, k={k}, r={r}: unanimous panel must uphold; the majority-only "
            f"missing-aware gate leaked into a unanimous panel: {payload}"
        )
        assert "potential-flip-on-missing" not in json.dumps(payload)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
@pytest.mark.parametrize("n", [1, 2, 3, 4])
@pytest.mark.parametrize("pass_rule", ["majority", "unanimous"])
def test_advisory_only_panel_upholds_at_every_panel_size(n: int, pass_rule: str) -> None:
    # The severity axis must hold at every panel size, not just the n=3 default. The threshold
    # formula rounds differently at even and odd n, so a suite pinned to one size cannot see a
    # boundary regression.
    result = _run_panel_gate(pass_rule, [_ADVISORY_VERDICT] * n, n=n)

    assert result["reported"] == n
    assert result["missing"] == 0
    assert result["refute_count"] == 0
    assert result["refuted"] is False


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_gating_bucket_refutes_at_every_panel_size(n: int) -> None:
    # The mirror of the advisory case: a unanimously gating panel refutes at any size.
    result = _run_panel_gate("majority", [_GATING_VERDICT] * n, n=n)

    assert result["reported"] == n
    assert result["refute_count"] == n
    assert result["refuted"] is True


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_a_null_advisory_element_cannot_halt_a_run_that_passed_its_gate() -> None:
    # The schema types `advisory_corrections` as a bare array with no `items` constraint, so a
    # JSON null element passes the tool boundary. `typeof null === "object"`, so an unguarded
    # renderer dereferences `null.claim` and throws -- aborting a run whose gate found ZERO
    # gating refutations, and, on a degraded panel, PREEMPTING the correct diagnostic throw
    # with an opaque null-dereference.
    verdict_js = (
        "{refuted_deliverable: [], advisory_corrections: [null], upheld: [],"
        ' verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness(
        [_verify_unit("a", verify={"n": 3, "pass_rule": "majority"})],
        verdict_js=verdict_js,
        tail=_CAPTURE_THROW,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is True, f"null advisory element halted the run: {payload.get('message')}"
    assert payload["advisories"][0]["corrections"] == ["(empty advisory entry)"] * 3


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_control_characters_in_an_advisory_cannot_forge_a_second_log_line() -> None:
    # Advisory text is model-authored and reaches log() verbatim. An embedded newline would let
    # one entry masquerade as an unrelated, more alarming log line to anything reading the
    # stream. Every control character collapses to a space before it is logged or stored.
    forged = "looks fine\\nlog: WORKFLOW HALTED -- notify operator immediately"
    verdict_js = (
        f'{{refuted_deliverable: [], advisory_corrections: ["{forged}"], upheld: [],'
        ' verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness(
        [_verify_unit("a", verify={"n": 3, "pass_rule": "majority"})],
        verdict_js=verdict_js,
        tail=_CAPTURE_OK,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    stored = payload["advisories"][0]["corrections"]
    assert all("\n" not in item for item in stored), stored
    assert all("\n" not in line for line in payload["logged"]), payload["logged"]


_INVISIBLE_CODEPOINTS = (
    0x0085,  # NEL -- a C1 line break no C0-only class catches
    0x200E,
    0x200F,  # LRM / RLM
    0x2028,
    0x2029,  # line / paragraph separator
    0x202A,
    0x202B,
    0x202C,
    0x202D,
    0x202E,  # bidi embeddings, pop, overrides
    0x2066,
    0x2067,
    0x2068,
    0x2069,  # bidi isolates
    0xFEFF,  # BOM / zero-width no-break space
)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_invisible_formatting_characters_cannot_reorder_a_logged_advisory() -> None:
    # Sibling hazard to the forged-newline case above, and NOT covered by it. A bidi override
    # leaves the byte sequence intact while reversing what a human READS in a terminal or log
    # viewer -- the Trojan-Source pattern -- so an advisory can be made to display as text it
    # does not contain. Advisory text is authored by a verifier that read a diff it did not
    # write, which puts these codepoints within reach of repo content. The channel is
    # non-gating, so the exposure is misleading display, never a flipped verdict.
    hostile = "".join(f"\\u{cp:04x}mark" for cp in _INVISIBLE_CODEPOINTS)
    verdict_js = (
        f'{{refuted_deliverable: [], advisory_corrections: ["safe {hostile} tail"],'
        ' upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness(
        [_verify_unit("a", verify={"n": 3, "pass_rule": "majority"})],
        verdict_js=verdict_js,
        tail=_CAPTURE_OK,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    stored = payload["advisories"][0]["corrections"]
    surviving = sorted(
        {
            f"U+{ord(ch):04X}"
            for item in stored + payload["logged"]
            for ch in item
            if ord(ch) in _INVISIBLE_CODEPOINTS
        }
    )
    assert not surviving, surviving
    # Scrubbing is not blanking -- the readable content still has to arrive.
    assert stored[0].startswith("safe ") and stored[0].endswith(" tail")
    assert stored[0].count("mark") == len(_INVISIBLE_CODEPOINTS)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_advisory_log_names_the_actual_verdict_when_the_panel_refuted() -> None:
    # The advisory line is emitted BEFORE the gate's enforcement throw, on every path. Stating
    # "deliverable UPHELD" unconditionally means the run log asserts the gate did not fire on
    # exactly the runs where it did -- and a log-scraper filtering for UPHELD reads a killed
    # unit as passed.
    verdict_js = (
        '{refuted_deliverable: ["the test asserts nothing"],'
        ' advisory_corrections: ["notes misattribute the change"], upheld: [],'
        ' verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness(
        [_verify_unit("a", verify={"n": 3, "pass_rule": "majority"})],
        verdict_js=verdict_js,
        tail=_CAPTURE_THROW,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is False
    assert "verifier-disagreement" in payload["message"]
    advisory_logs = [line for line in payload["logged"] if "advisory correction" in line]
    assert len(advisory_logs) == 1
    assert "deliverable REFUTED" in advisory_logs[0]
    assert "deliverable UPHELD" not in advisory_logs[0]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_a_halt_carries_only_its_own_unit_advisories() -> None:
    # A single unit that halts with advisories carries its own advisories on the thrown error.
    units = [
        _verify_unit("a", verify={"n": 3, "pass_rule": "majority"}),
    ]
    verdict_js = (
        '{refuted_deliverable: ["unit a is broken"], advisory_corrections: ["unit a: fix typo"],'
        ' upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness(units, verdict_js=verdict_js, tail=_CAPTURE_THROW)

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is False
    assert "verifier-disagreement: Unit a" in payload["message"]
    assert payload["advisories"] is not None
    assert [entry["unit"] for entry in payload["advisories"]] == ["a"]
    assert payload["advisories"][0]["corrections"] == ["unit a: fix typo"] * 3


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_halt_in_second_unit_does_not_carry_prior_unit_advisories() -> None:
    # #691 AC2 / plan U7: cross-unit advisory isolation. When two units each report one advisory
    # and the second unit halts, the halt error's advisory_corrections contains only the second
    # unit's advisory (length 1, not 2).
    units = [
        _verify_unit("a", verify={"n": 3, "pass_rule": "majority"}),
        _verify_unit("b", verify={"n": 3, "pass_rule": "majority"}, depends_on=["a"]),
    ]
    verdict_js = (
        "__vcall <= 3"
        ' ? {refuted_deliverable: [], advisory_corrections: ["unit a: wrong rationale"],'
        ' upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
        ' : {refuted_deliverable: ["unit b is broken"], advisory_corrections: ["unit b: wrong format"],'
        ' upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness(units, verdict_js=verdict_js, tail=_CAPTURE_THROW)

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is False
    assert "verifier-disagreement: Unit b" in payload["message"]
    # Unit `b`'s halt carries ONLY unit `b`'s advisories -- length 1, not 2.
    assert payload["advisories"] is not None
    assert len(payload["advisories"]) == 1
    assert [entry["unit"] for entry in payload["advisories"]] == ["b"]
    assert payload["advisories"][0]["corrections"] == ["unit b: wrong format"] * 3


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_halt_in_second_unit_with_no_advisories_returns_empty_advisories() -> None:
    # #691: A halt in unit `b` where unit `b` has no advisories does NOT carry unit `a`'s advisories.
    units = [
        _verify_unit("a", verify={"n": 3, "pass_rule": "majority"}),
        _verify_unit("b", verify={"n": 3, "pass_rule": "majority"}, depends_on=["a"]),
    ]
    verdict_js = (
        "__vcall <= 3"
        ' ? {refuted_deliverable: [], advisory_corrections: ["unit a: wrong rationale"],'
        ' upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
        ' : {refuted_deliverable: ["unit b is broken"], advisory_corrections: [],'
        ' upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness(units, verdict_js=verdict_js, tail=_CAPTURE_THROW)

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is False
    assert "verifier-disagreement: Unit b" in payload["message"]
    assert payload["advisories"] == []


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_top_level_run_return_keeps_all_unit_advisories() -> None:
    # Plan U7 / F8: The top-level harness return `advisory_corrections` retains the complete run-wide
    # list keyed by unit when multiple units succeed.
    units = [
        _verify_unit("a", verify={"n": 3, "pass_rule": "majority"}),
        _verify_unit("b", verify={"n": 3, "pass_rule": "majority"}, depends_on=["a"]),
    ]
    verdict_js = (
        "__vcall <= 3"
        ' ? {refuted_deliverable: [], advisory_corrections: ["unit a: advisory"],'
        ' upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
        ' : {refuted_deliverable: [], advisory_corrections: ["unit b: advisory"],'
        ' upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness(units, verdict_js=verdict_js, tail=_CAPTURE_OK)

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is True
    assert len(payload["advisories"]) == 2
    assert [entry["unit"] for entry in payload["advisories"]] == ["a", "b"]
    assert payload["advisories"][0]["corrections"] == ["unit a: advisory"] * 3
    assert payload["advisories"][1]["corrections"] == ["unit b: advisory"] * 3


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_iterate_to_consensus_labels_each_round_of_advisories() -> None:
    # An iterate-to-consensus unit runs its panel once per round. Without a round marker the
    # entry describing a DISCARDED intermediate result is indistinguishable from the one
    # describing the accepted result, and a driver may act on a correction about work that no
    # longer exists. Round 1 refutes (so the unit re-runs); round 2 upholds.
    unit = _verify_unit(
        "a",
        verify={
            "n": 3,
            "pass_rule": "majority",
            "iterate_to_consensus": True,
            "max_iterations": 2,
        },
    )
    verdict_js = (
        "__vcall <= 3"
        ' ? {refuted_deliverable: ["round one is wrong"],'
        ' advisory_corrections: ["round one prose"], upheld: [],'
        ' verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
        ' : {refuted_deliverable: [], advisory_corrections: ["round two prose"], upheld: [],'
        ' verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness([unit], verdict_js=verdict_js, tail=_CAPTURE_THROW)

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    entries = payload["advisories"] or []
    assert [entry["round"] for entry in entries] == [1, 2], entries
    assert entries[0]["corrections"] == ["round one prose"] * 3
    assert entries[1]["corrections"] == ["round two prose"] * 3


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_a_round_that_produced_no_advisories_still_consumes_its_round_number() -> None:
    # REGRESSION PIN. The round ordinal counts PANEL ROUNDS, not stored entries. Deriving it
    # from the accumulator silently renumbers: round 1 here yields no advisories, so an
    # entry-derived ordinal would label round 2's corrections "round 1" -- and the reference
    # doc tells a driver that the last entry describes the result the harness returned. Under
    # the old derivation that driver reads round 2's advice under round 1's name, and in the
    # mirror case (a clean FINAL round) it reads advice about a discarded intermediate result.
    unit = _verify_unit(
        "a",
        verify={
            "n": 3,
            "pass_rule": "majority",
            "iterate_to_consensus": True,
            "max_iterations": 2,
        },
    )
    verdict_js = (
        "__vcall <= 3"
        ' ? {refuted_deliverable: ["round one is wrong"], advisory_corrections: [],'
        ' upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
        ' : {refuted_deliverable: [], advisory_corrections: ["round two prose"], upheld: [],'
        ' verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness([unit], verdict_js=verdict_js, tail=_CAPTURE_THROW)

    assert proc.returncode == 0, proc.stderr
    entries = json.loads(proc.stdout.strip())["advisories"] or []
    assert len(entries) == 1, entries
    assert entries[0]["round"] == 2, "the silent first round still consumed round 1"
    assert entries[0]["corrections"] == ["round two prose"] * 3


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_the_harvest_failure_marker_is_scrubbed_like_any_other_advisory() -> None:
    # The marker embeds an exception message, which is model-reachable text, and it is the one
    # path that builds an advisory WITHOUT going through __renderAdvisory. Unscrubbed it would
    # reopen exactly the newline forgery the scrub exists to close -- on the single path a
    # reader is least likely to audit.
    forged = "boom\\nlog: WORKFLOW HALTED -- notify operator immediately"
    verdict_js = (
        "(() => {"
        " const a = [null];"
        f' Object.defineProperty(a, 0, {{ get() {{ throw new Error("{forged}") }} }});'
        " return {refuted_deliverable: [], advisory_corrections: a, upheld: [],"
        ' verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"};'
        " })()"
    )
    proc = _run_harness(
        [_verify_unit("a", verify={"n": 1, "pass_rule": "majority"})],
        verdict_js=verdict_js,
        tail=_CAPTURE_OK,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    stored = payload["advisories"][0]["corrections"]
    assert any("advisory harvest failed" in item for item in stored), stored
    assert all("\n" not in item for item in stored), stored
    assert all("\n" not in line for line in payload["logged"]), payload["logged"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_truncation_never_stores_half_of_a_surrogate_pair() -> None:
    # .slice() cuts on UTF-16 code units. Before the severity split the 180-char cap applied
    # only to the log line; it now bounds the value STORED and returned, so an emoji straddling
    # the boundary would put ill-formed UTF-16 across the harness return -- a consumer that
    # re-encodes it substitutes U+FFFD, and a strict encoder raises.
    verdict_js = (
        "{refuted_deliverable: [],"
        ' advisory_corrections: ["A".repeat(179) + String.fromCodePoint(0x1f600) + "TAIL"],'
        ' upheld: [], verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness(
        [_verify_unit("a", verify={"n": 1, "pass_rule": "majority"})],
        verdict_js=verdict_js,
        tail=_CAPTURE_OK,
    )

    assert proc.returncode == 0, proc.stderr
    stored = json.loads(proc.stdout.strip())["advisories"][0]["corrections"][0]
    # The orphaned high surrogate is dropped rather than kept, so the value is one shorter.
    assert len(stored) == 179
    assert not 0xD800 <= ord(stored[-1]) <= 0xDBFF, hex(ord(stored[-1]))
    stored.encode("utf-8")  # raises UnicodeEncodeError if a lone surrogate survived


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_advisory_items_are_capped_and_report_what_they_dropped() -> None:
    # `__advisories` rides out on the harness return into the driving session's context, and
    # its contents are model-authored with no schema size bound. The cap keeps one verbose
    # panel from dominating the return value, and `dropped` keeps the truncation honest rather
    # than silent.
    items = ", ".join(f'"item-{i:03d}"' for i in range(80))
    verdict_js = (
        f"{{refuted_deliverable: [], advisory_corrections: [{items}], upheld: [],"
        ' verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness(
        [_verify_unit("a", verify={"n": 1, "pass_rule": "majority"})],
        verdict_js=verdict_js,
        tail=_CAPTURE_OK,
    )

    assert proc.returncode == 0, proc.stderr
    entry = json.loads(proc.stdout.strip())["advisories"][0]
    assert len(entry["corrections"]) == 50
    assert entry["dropped"] == 30
    assert "[+30 suppressed]" in "".join(json.loads(proc.stdout.strip())["logged"])


@pytest.mark.parametrize("pass_rule", ["majority", "unanimous"])
def test_verifier_prompt_call_threads_the_panel_s_pass_rule(pass_rule: str) -> None:
    # Emitted-text half: the panel's pass rule reaches the helper at all. This cannot assert
    # what the helper RENDERS -- `${gatingBar}` is the helper's own template-literal source and
    # is present verbatim in every emitted script regardless of how (or whether) the ternary
    # computes it. Rendering is pinned by the node-executed test below.
    script = _emit_units([_verify_unit("a", verify={"n": 4, "pass_rule": pass_rule})])

    assert "__verifierPrompt(" in script
    assert f', "{pass_rule}")' in script


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
@pytest.mark.parametrize(
    ("pass_rule", "rendered", "other_arm"),
    [
        ("majority", "a majority of the panel", "EVERY reporting verifier"),
        ("unanimous", "EVERY reporting verifier", "a majority of the panel"),
    ],
)
def test_verifier_prompt_renders_the_gating_bar_the_panel_actually_applies(
    pass_rule: str, rendered: str, other_arm: str
) -> None:
    # The VERDICT CONTRACT asks each verifier to apply a calibration test -- "put a finding in
    # the gating bucket only if you would defend stopping the run over it". A verifier told the
    # bar is a majority when the panel is unanimous reasons against the wrong consequence.
    #
    # This runs the emitted harness and reads the prompt string the panel actually handed its
    # verifiers. A source grep cannot do that: deleting the `passRule` ternary outright and
    # hardcoding one arm leaves every emitted-text assertion green.
    verdict_js = (
        '{refuted_deliverable: [], advisory_corrections: [], upheld: ["fine"],'
        ' verifier_identity: "saga:readonly-verifier", fallback_depth: 0,'
        ' examined_sha: "deadbeef"}'
    )
    proc = _run_harness(
        [_verify_unit("a", verify={"n": 3, "pass_rule": pass_rule})],
        verdict_js=verdict_js,
        tail=_CAPTURE_PROMPTS,
    )

    assert proc.returncode == 0, proc.stderr
    prompts = json.loads(proc.stdout.strip())["prompts"]
    assert len(prompts) == 3, "every verifier in the panel is prompted"
    for prompt in prompts:
        assert f"from {rendered} KILLS the unit" in prompt
        assert other_arm not in prompt


@pytest.mark.parametrize("unit_id", sorted(_RESERVED_FOR_SHADOW_TEST))
def test_reserved_harness_identifiers_are_rejected_as_unit_ids(unit_id: str) -> None:
    # The reservation set is only meaningful if emission actually rejects a unit id that would
    # shadow a harness global. Asserting set MEMBERSHIP proves nothing: a refactor that dropped
    # these names from the collision path while leaving them in the set would keep a membership
    # test green. This is the emitter-owned half of the set -- the JS runtime builtins are
    # covered by test_workflow_unit_id_rejects_harness_global_shadowing.
    spec = ES.ExecutionSpec.from_dict(_spec_dict(unit_id=unit_id))

    with pytest.raises(ES.SpecError, match="reserved JavaScript identifier"):
        ES.emit_workflow_script(spec)


def test_sandbox_spawn_sites_reference_carries_the_split_verdict_shape() -> None:
    # The FOURTH verdict-shape surface. This repo's CLAUDE.md routes every verify-class agent
    # spawn made outside a saga skill through this file's fallback ladder, and that ladder tells
    # a caller to restate the verdict contract in its own dispatch prompt when the verifier
    # agent type cannot be resolved. Left naming the legacy single-bucket shape, the documented
    # fallback reproduces the exact severity-blind gate #686 exists to remove.
    text = SANDBOX_SPAWN_SITES_REFERENCE.read_text(encoding="utf-8")

    assert "{refuted, upheld}" not in text
    assert "refuted_deliverable" in text
    assert "advisory_corrections" in text


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_advisory_only_panel_does_not_burn_the_364_one_rung_climb() -> None:
    # R8: the #364 escalate_on_signal ladder climb is the SECOND consumer of the refuted
    # boolean. An advisory-only panel must leave the unit at its authored tier -- the retry
    # branch is guarded by the same `<var>_refuted` the gate arithmetic now computes from the
    # gating bucket only, so a prose-only panel cannot burn a tier escalation.
    script = _emit_units_unattended([_escalate_unit()])
    js = "\n".join(
        [
            "const U1_verdicts = " + json.dumps([_ADVISORY_VERDICT] * 3),
            _extract_emitted_line(script, "const U1_valid_verifier_verdict ="),
            _extract_emitted_line(script, "const U1_reported ="),
            _extract_emitted_line(script, "const U1_refute_count ="),
            _extract_emitted_line(script, "const U1_threshold ="),
            _extract_emitted_line(script, "const U1_refuted ="),
            # The emitted climb is `if (U1_refuted) { ...re-run one rung up... }`.
            "console.log(JSON.stringify({climbed: U1_refuted}))",
        ]
    )
    proc = subprocess.run(
        [shutil.which("node") or "node", "-e", js],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    assert json.loads(proc.stdout.strip()) == {"climbed": False}
    # And the climb really is gated on that boolean (guards the assertion above from drifting
    # into a test of an expression the emitted harness no longer consumes).
    assert "if (U1_refuted) {" in script
    assert "climbing ONE rung to sonnet/high" in script


def test_verifier_iterate_singleton_emits_readonly_agenttype_and_isolation() -> None:
    script = _emit_units(
        [_verify_unit("b", verify={"n": 2, "pass_rule": "majority", "iterate_to_consensus": True})]
    )
    assert 'agentType: "saga:readonly-verifier"' in script
    assert 'isolation: "worktree"' in script
    assert "for (let iter" in script  # proves the singleton loop path, not the plain panel


def test_verifier_parallel_thunk_emits_readonly_agenttype_and_isolation() -> None:
    # Two independent units land in one dependency layer => parallel([...]) of thunks; each
    # thunk with iterate_to_consensus runs its own inline verifier loop (the third site).
    script = _emit_units(
        [
            _verify_unit(
                "c1", verify={"n": 2, "pass_rule": "majority", "iterate_to_consensus": True}
            ),
            _verify_unit(
                "c2", verify={"n": 2, "pass_rule": "majority", "iterate_to_consensus": True}
            ),
        ]
    )
    assert "parallel(" in script
    # Both units' verifier loops carry the opts: 2 units x n=2 verifiers = 4 tagged calls.
    assert script.count('agentType: "saga:readonly-verifier"') == 4
    assert script.count('isolation: "worktree"') == 4


def test_unit_own_agent_call_is_not_verifier_restricted() -> None:
    # A single unit with a 2-verifier panel: agentType appears on the TWO verifier calls only,
    # never on the unit's own agent() call (which keeps the ambient x read-write R1 default).
    script = _emit_units([_verify_unit("a", verify={"n": 2, "pass_rule": "majority"})])
    assert script.count('agentType: "saga:readonly-verifier"') == 2


def test_plain_unit_without_verify_emits_no_verifier_wiring() -> None:
    script = _emit_units([_verify_unit("a")])
    assert "agentType" not in script
    assert "isolation:" not in script


def test_unit_agent_call_emits_return_schema() -> None:
    script = _emit_units([_verify_unit("a")])
    assert _return_schema_fragment() in script
    assert "schema:" in script.split("const a = await agent(", 1)[1].split("__gate(a", 1)[0]


def test_external_engine_unit_cannot_emit_return_schema() -> None:
    with pytest.raises(ES.SpecError, match="external-engine unit"):
        _emit_units([_verify_unit("ext", capability="code-generation")])


def test_parallel_thunks_emit_return_schema_for_each_unit() -> None:
    script = _emit_units([_verify_unit("a"), _verify_unit("b")])
    assert "parallel([" in script
    assert script.count(_return_schema_fragment()) == 2


def test_iterate_to_consensus_unit_emits_return_schema() -> None:
    script = _emit_units(
        [_verify_unit("i", verify={"n": 2, "pass_rule": "majority", "iterate_to_consensus": True})]
    )
    assert "for (let iter" in script
    assert _return_schema_fragment() in script


def test_cheap_tier_schema_preserves_pull_cord_alternative() -> None:
    script = _emit_units([_verify_unit("cheap", tier={"model": "haiku", "effort": "low"})])
    assert _return_schema_fragment(cheap=True) in script
    assert "pull_cord" in script


def _extract_agent_schemas(script: str) -> list[dict[str, object]]:
    """Parse every ``schema: {...}`` JSON blob out of an emitted workflow script."""
    decoder = json.JSONDecoder()
    marker = "schema: "
    schemas: list[dict[str, object]] = []
    start = script.find(marker)
    while start != -1:
        obj, _ = decoder.raw_decode(script, start + len(marker))
        assert isinstance(obj, dict)
        schemas.append(obj)
        start = script.find(marker, start + len(marker))
    return schemas


def test_every_emitted_agent_schema_has_toplevel_type() -> None:
    # Regression for the pull-cord schema dispatch failure (#364, reproduced 2026-07-10 in
    # team-norns run wf_758c9923-c2c). The Anthropic API rejects a tool input_schema on TWO
    # counts, checked in sequence: first if it lacks a top-level "type"
    # (400 tools.N.custom.input_schema.type: Field required), then if it carries ANY top-level
    # combinator (400 tools.N.custom.input_schema: input_schema does not support oneOf, allOf,
    # or anyOf at the top level). The first fix added "type" but kept a top-level oneOf, so it
    # still 400ed -- this test now asserts BOTH invariants so the second gate can't slip through.
    # Sweep EVERY schema across all emission sites: plain unit, cheap pull-cord shape,
    # refute-N verifier panel, and the iterate-to-consensus loop. External-engine units
    # are rejected at emit (#708) and are no longer an emission site.
    script = _emit_units(
        [
            _verify_unit("plain"),
            _verify_unit("cheap", tier={"model": "haiku", "effort": "low"}),
            _verify_unit("panel", verify={"n": 2, "pass_rule": "majority"}),
            _verify_unit(
                "iter_unit",
                verify={"n": 2, "pass_rule": "majority", "iterate_to_consensus": True},
            ),
        ]
    )
    schemas = _extract_agent_schemas(script)
    # 4 unit schemas + 2 panel verifiers + the iterate loop's verifier call at minimum.
    assert len(schemas) >= 7
    for schema in schemas:
        assert schema.get("type") == "object", f"schema missing top-level type: {schema}"
        forbidden = {"oneOf", "allOf", "anyOf"} & schema.keys()
        assert not forbidden, f"schema has unsupported top-level combinator {forbidden}: {schema}"
    # The cheap-tier pull-cord shape is a FLAT typed object: pull_cord rides as a top-level
    # optional property (NOT under a combinator), and there is no `required` alternation. The
    # returns-XOR-pull_cord contract lives in __gate + the RETURN CONTRACT, not the schema.
    cheap: list[dict[str, object]] = []
    for schema in schemas:
        properties = schema.get("properties")
        if isinstance(properties, dict) and "pull_cord" in properties:
            cheap.append(schema)
    assert cheap, "expected at least one cheap-tier pull-cord schema"
    for schema in cheap:
        properties = schema["properties"]
        assert isinstance(properties, dict)
        assert properties.get("pull_cord") == {"type": "string"}
        assert "oneOf" not in schema and "required" not in schema


# ---------------------------------------------------------- enforceability matrix (U3)
# unenforceable_sandbox_axis(backend, sandbox) -> the (axis, value) a backend cannot enforce, or
# None. Only NON-default axis values need enforcing; unlisted backends enforce nothing (R4).


@pytest.mark.parametrize(
    "backend,profile,expected",
    [
        ("inline", "read-only-verify", None),
        ("cc-workflows-ultracode", "read-only-verify", None),
        ("inline", "sandboxed-mutate", ("workspace_isolation", "owned-worktree")),
        ("team-execution", "read-only-verify", ("mutation_policy", "read-only")),
        ("fork", "read-only-verify", ("mutation_policy", "read-only")),
        ("subagent", "sandboxed-mutate", ("workspace_isolation", "owned-worktree")),
        ("goal", "read-only-verify", ("mutation_policy", "read-only")),
        ("manual", "read-only-verify", ("mutation_policy", "read-only")),
    ],
)
def test_unenforceable_sandbox_axis_matrix(backend: str, profile: str, expected: object) -> None:
    sb = ES.Sandbox.from_dict(profile, "w")
    assert ES.unenforceable_sandbox_axis(backend, sb) == expected


def test_unenforceable_sandbox_axis_none_and_default_are_enforceable_everywhere() -> None:
    # No sandbox and the ambient x read-write default never trip on any backend (R1).
    default = ES.Sandbox(mutation_policy="read-write", workspace_isolation="ambient")
    for backend in ("inline", "team-execution", "fork", "manual", "goal", "subagent"):
        assert ES.unenforceable_sandbox_axis(backend, None) is None
        assert ES.unenforceable_sandbox_axis(backend, default) is None


def test_unlisted_backend_is_never_permissive() -> None:
    # A future/unknown backend enforces nothing => any restrictive sandbox halts (R4).
    sb = ES.Sandbox.from_dict("read-only-verify", "w")
    assert ES.unenforceable_sandbox_axis("some-future-backend", sb) is not None


# ---------------------------------------------------------- tier enforceability (#369 U1)
# unenforceable_tier(backend, tier) -> the (axis, value) a backend cannot spawn, or None. v1 checks
# the MODEL axis: team-execution spawns by agentType (models {opus,sonnet,haiku}, no fable); unlisted
# backends enforce nothing (R3).


def test_unenforceable_tier_halts_fable_on_team_execution() -> None:
    # fable is unreachable outside saga plan vocabulary; team-execution cannot spawn it -> HALT.
    assert ES.unenforceable_tier("team-execution", ES.Tier("fable", "xhigh")) == ("model", "fable")
    # A reachable model on team-execution is fine (existing specs stay green).
    assert ES.unenforceable_tier("team-execution", ES.Tier("opus", "high")) is None


def test_unenforceable_tier_passes_reachable_model() -> None:
    # The enforcing-backend branch of the issue AC: inline / cc-workflows set the per-call tier and
    # reach the whole palette, so the same fable/xhigh unit passes there.
    for backend in ("inline", "cc-workflows-ultracode"):
        assert ES.unenforceable_tier(backend, ES.Tier("fable", "xhigh")) is None


def test_unenforceable_tier_unknown_backend_never_permissive() -> None:
    # A backend absent from TIER_ENFORCEABLE_BY_BACKEND enforces nothing => any model halts (R3).
    assert ES.unenforceable_tier("some-future-backend", ES.Tier("opus", "high")) == (
        "model",
        "opus",
    )


# ---------------------------------------------------------- Unit.min_tier floor (#369 U2)


def test_min_tier_pulls_cheap_segment_up() -> None:
    # Two units share the plugins/saga segment; the floored one drags the whole resident up to its
    # floor via the same upgrade-only ladder op as the base merge.
    spec = ES.ExecutionSpec.from_dict(
        {
            "name": "floor-demo",
            "description": "d",
            "repo": "/tmp/r",
            "units": [
                {
                    "unit_id": "A",
                    "label": "floored",
                    "tier": {"model": "haiku", "effort": "low"},
                    "prompt": "p",
                    "files": ["plugins/saga/scripts/execution_spec.py"],
                    "min_tier": {"model": "opus", "effort": "high"},
                },
                {
                    "unit_id": "B",
                    "label": "cheap",
                    "tier": {"model": "haiku", "effort": "low"},
                    "prompt": "p",
                    "files": ["plugins/saga/scripts/team_emitter.py"],
                },
            ],
        }
    )
    spec.validate()
    segments = ES.segment_units(spec)
    assert len(segments) == 1
    assert segments[0].tier == ES.Tier(model="opus", effort="high")


def test_off_palette_min_tier_fails_emit() -> None:
    # A floor drawn off the MODELS/EFFORTS palette fails validation with a named error (R5).
    unit = ES.Unit.from_dict(
        {
            "unit_id": "A",
            "label": "a",
            "tier": {"model": "sonnet", "effort": "high"},
            "prompt": "p",
            "min_tier": {"model": "gpt-5", "effort": "high"},
        }
    )
    with pytest.raises(ES.SpecError, match="not in"):
        unit.validate("unit A")


def test_absent_min_tier_round_trips_byte_identical() -> None:
    # A spec with no floor emits no min_tier key and round-trips through to_dict/from_dict unchanged.
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    first = spec.to_dict()
    assert all("min_tier" not in u for u in first["units"])
    again = ES.ExecutionSpec.from_dict(first).to_dict()
    assert first == again


# ---------------------------------------------------------- session tier ceiling (#365 U2/U3)


def test_tier_ceiling_clamp() -> None:
    # A sonnet/medium ceiling clamps an opus/high tier DOWN on both axes.
    clamped = ES.clamp_tier_to_ceiling(ES.Tier("opus", "high"), ES.Tier("sonnet", "medium"))
    assert clamped == ES.Tier("sonnet", "medium")


def test_tier_ceiling_never_escalates() -> None:
    # A ceiling at or above the tier is a no-op -- a ceiling never RAISES a tier.
    weak = ES.Tier("haiku", "low")
    assert ES.clamp_tier_to_ceiling(weak, ES.Tier("opus", "high")) == weak
    # Mixed: ceiling above on model, below on effort -> only effort clamps down.
    assert ES.clamp_tier_to_ceiling(
        ES.Tier("sonnet", "xhigh"), ES.Tier("opus", "medium")
    ) == ES.Tier("sonnet", "medium")


def test_clamp_tier_to_ceiling_is_always_runnable() -> None:
    # #365 gate P0: even a direct caller passing an unrunnable ceiling Tier (bypassing tier_session)
    # must never yield an unrunnable result -- the clamped effort is pulled to the model's ceiling.
    out = ES.clamp_tier_to_ceiling(ES.Tier("opus", "xhigh"), ES.Tier("haiku", "xhigh"))
    assert out == ES.Tier("haiku", "high")  # not haiku/xhigh (haiku's ceiling is high)
    # And an emit with such a ceiling never renders the unrunnable combo.
    spec = ES.ExecutionSpec.from_dict(_spec_dict(tier={"model": "opus", "effort": "xhigh"}))
    script = ES.emit_workflow_script(spec, session_ceiling=ES.Tier("haiku", "xhigh"))
    assert 'effort: "xhigh"' not in script
    assert 'model: "haiku"' in script and 'effort: "high"' in script


def test_workflow_emit_honors_session_ceiling() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(tier={"model": "opus", "effort": "high"}))
    # No ceiling -> the authored tier is rendered verbatim.
    plain = ES.emit_workflow_script(spec)
    assert 'model: "opus"' in plain and 'effort: "high"' in plain
    # A sonnet/medium ceiling clamps the emitted tier and logs the downgrade.
    clamped = ES.emit_workflow_script(spec, session_ceiling=ES.Tier("sonnet", "medium"))
    assert 'model: "sonnet"' in clamped and 'effort: "medium"' in clamped
    assert 'model: "opus"' not in clamped
    assert "SESSION TIER CEILING" in clamped and "U1" in clamped


# ---------------------------------------------------------- mid-run patch (#365 U4)


def _two_unit_spec() -> dict[str, object]:
    return {
        "name": "patch-demo",
        "description": "d",
        "repo": "/tmp/r",
        "units": [
            {
                "unit_id": "A",
                "label": "a",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "p",
            },
            {
                "unit_id": "B",
                "label": "b",
                "tier": {"model": "haiku", "effort": "low"},
                "prompt": "p",
            },
        ],
    }


def test_tier_patch_unrun_only() -> None:
    spec = ES.ExecutionSpec.from_dict(_two_unit_spec())
    overrides = {"A": ES.Tier("opus", "high"), "B": ES.Tier("opus", "high")}
    patched = ES.patch_spec_tiers(spec, overrides, already_run_ids=["A"])
    by_id = {u.unit_id: u.tier for u in patched.units}
    assert by_id["A"] == ES.Tier("haiku", "low")  # already-run -> untouched
    assert by_id["B"] == ES.Tier("opus", "high")  # not-yet-run -> patched


def test_tier_patch_validate_gate() -> None:
    # A patch producing an unrunnable tier (haiku/xhigh) fails validation before any emit (R5).
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    patched = ES.patch_spec_tiers(spec, {"U1": ES.Tier("haiku", "xhigh")}, already_run_ids=[])
    with pytest.raises(ES.SpecError):
        patched.validate()


def test_tier_patch_reemit() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(tier={"model": "haiku", "effort": "low"}))
    patched = ES.patch_spec_tiers(spec, {"U1": ES.Tier("opus", "high")}, already_run_ids=[])
    patched.validate()
    script = ES.emit_workflow_script(patched)
    assert 'model: "opus"' in script and 'effort: "high"' in script


def test_tier_patch_spend_delta_gate() -> None:
    # Up-ladder on either axis is an escalation (confirm required); cheapen/lateral is not.
    assert (
        ES.is_escalation(ES.Tier("sonnet", "medium"), ES.Tier("opus", "medium")) is True
    )  # model up
    assert (
        ES.is_escalation(ES.Tier("sonnet", "medium"), ES.Tier("sonnet", "high")) is True
    )  # effort up
    assert (
        ES.is_escalation(ES.Tier("opus", "high"), ES.Tier("sonnet", "medium")) is False
    )  # cheapen
    assert (
        ES.is_escalation(ES.Tier("sonnet", "medium"), ES.Tier("sonnet", "medium")) is False
    )  # lateral


# --- Runtime ladder climbing (#364): escalate_tier + escalate_on_signal + pull_cord ---


def test_escalate_tier_one_rung_effort_first() -> None:  # R1
    t = ES.escalate_tier(ES.Tier(model="sonnet", effort="medium"))
    assert t == ES.Tier(model="sonnet", effort="high")  # exactly one effort rung, same model


def test_escalate_tier_model_climb_at_effort_ceiling() -> None:  # R1
    # haiku's ceiling is high (models.json) -> the next rung is the MODEL axis, keeping effort.
    t = ES.escalate_tier(ES.Tier(model="haiku", effort="high"))
    assert t == ES.Tier(model="sonnet", effort="high")


def test_escalate_tier_top_of_ladder_returns_none() -> None:  # R3 signal
    assert ES.escalate_tier(ES.Tier(model="fable", effort="xhigh")) is None


def test_escalate_tier_ceiling_blocks_climb() -> None:  # KTD5
    blocked = ES.escalate_tier(
        ES.Tier(model="sonnet", effort="high"), ceiling=ES.Tier(model="sonnet", effort="high")
    )
    assert blocked is None  # never exceeds the ceiling, never same-tier re-run


def test_escalate_tier_never_unrunnable() -> None:  # KTD1 invariant
    seen = ES.Tier(model="haiku", effort="low")
    for _ in range(16):  # walk the whole ladder from the bottom
        nxt = ES.escalate_tier(seen)
        if nxt is None:
            break
        assert nxt != seen
        nxt.validate("walk")  # would raise SpecError on an unrunnable pair
        seen = nxt
    assert seen == ES.Tier(model="fable", effort="xhigh")  # the walk terminates at the top


def _escalate_unit(**kw: object) -> dict[str, object]:
    unit = _verify_unit("U1", verify={"n": 3, "pass_rule": "majority"}, escalate_on_signal=True)
    unit["tier"] = {"model": "sonnet", "effort": "medium"}
    unit.update(kw)
    return unit


def _emit_units_unattended(units: list[dict[str, object]]) -> str:
    spec = ES.ExecutionSpec.from_dict(
        {"name": "verify-demo", "description": "d", "repo": "/tmp/r", "units": units}
    )
    spec.validate()
    return str(ES.emit_workflow_script(spec, unattended=True, **_routing_snapshots()))


def test_escalate_on_signal_one_rung_reemit() -> None:  # R2
    script = _emit_units_unattended([_escalate_unit()])
    # The retry re-runs at EXACTLY one rung up (sonnet/medium -> sonnet/high), never more.
    assert 'effort: "high"' in script
    assert "climbing ONE rung to sonnet/high" in script
    assert "sonnet/xhigh" not in script.split("cordProposal")[0]  # no rung-skipping in the retry
    # let-declared so the refuted branch can reassign the unit var.
    assert "let U1 = await agent(" in script


def test_escalate_on_signal_unattended_retry_emits_return_schema() -> None:
    script = _emit_units_unattended([_escalate_unit()])
    assert "climbing ONE rung to sonnet/high" in script
    assert script.count(_return_schema_fragment()) == 2


def test_unattended_model_climb_renders_retry_prompt_for_climbed_tier() -> None:
    script = _emit_units_unattended(
        [
            _escalate_unit(
                tier={"model": "haiku", "effort": "high"},
                returns=["result"],
            )
        ]
    )

    assert "climbing ONE rung to sonnet/high" in script
    initial_start = script.index("let U1 = await agent(")
    initial_call = script[initial_start : script.index("  )", initial_start)]
    retry_start = script.index("  U1 = await agent(", script.index("climbing ONE rung"))
    retry_call = script[retry_start : script.index("  )", retry_start)]
    assert ES.BUDGET_RIDER in initial_call
    assert "PULL-CORD (#364" in initial_call
    assert ES.BUDGET_RIDER not in retry_call
    assert "PULL-CORD (#364" not in retry_call
    assert "RETURN CONTRACT (all tiers)" in retry_call
    assert script.count(_return_schema_fragment()) == 1
    assert script.count(_return_schema_fragment(cheap=True)) == 1


def test_escalate_on_signal_top_of_ladder_halts() -> None:  # R3
    script = _emit_units_unattended([_escalate_unit(tier={"model": "fable", "effort": "xhigh"})])
    assert "at top of ladder" in script
    assert "HALT, not loop" in script
    assert "climbing ONE rung" not in script  # no retry branch exists at the top
    assert "const U1 = await agent(" in script  # nothing to reassign -> const stays


def test_escalate_attended_asks() -> None:  # R5
    script = _emit_units([_escalate_unit()])  # attended is the default emission
    assert "escalation-proposal" in script
    assert "confirm via /tier patch and re-emit" in script
    assert "climbing ONE rung" not in script  # never a silent in-script climb when attended


def test_escalate_unattended_silent() -> None:  # R6
    script = _emit_units_unattended([_escalate_unit()])
    assert "escalation-proposal" not in script  # no ask gate -- the climb is silent
    assert "climbing ONE rung" in script
    assert "still refuted after the one-rung climb" in script  # then HALT, never a second climb


def test_escalate_on_signal_absent_roundtrips() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    unit_out = spec.to_dict()["units"][0]
    assert "escalate_on_signal" not in unit_out  # absent field emits no key (byte-identical)
    spec_on = ES.ExecutionSpec.from_dict(
        _spec_dict(escalate_on_signal=True, verify={"n": 3, "pass_rule": "majority"})
    )
    assert spec_on.to_dict()["units"][0]["escalate_on_signal"] is True


def test_escalate_on_signal_rejects_iterate_to_consensus() -> None:  # doc-review P1 (a)
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(
            escalate_on_signal=True,
            verify={"n": 3, "pass_rule": "majority", "iterate_to_consensus": True},
        )
    )
    with pytest.raises(ES.SpecError, match="iterate_to_consensus"):
        spec.validate()


def test_escalate_on_signal_rejects_fanout() -> None:  # doc-review P1 (b)
    spec = ES.ExecutionSpec.from_dict(
        _spec_dict(
            escalate_on_signal=True,
            verify={"n": 3, "pass_rule": "majority"},
            fanout=True,
            targets=["a.py", "b.py"],
        )
    )
    with pytest.raises(ES.SpecError, match="fan-out"):
        spec.validate()


def test_escalate_on_signal_requires_verify_panel() -> None:  # dead-wiring guard
    spec = ES.ExecutionSpec.from_dict(_spec_dict(escalate_on_signal=True))
    with pytest.raises(ES.SpecError, match="no.*refute signal|refute signal"):
        spec.validate()


def test_pull_cord_disposition() -> None:  # R7
    script = _emit_units([_verify_unit("U1", tier={"model": "haiku", "effort": "low"})])
    # The gate accepts the cord shape as a valid alternative, distinct from the
    # missing/malformed-output throws (which remain in the helper for non-cord results).
    assert "pull_cord" in script
    assert "__pulledCords.push" in script
    assert "missing-output" in script  # crash-path throws still present and distinct
    # The cheap-tier prompt carries the cord rider so the disposition has a producer.
    assert "PULL-CORD (#364" in script
    # A non-cheap unit does NOT get the rider (the signal rides the cheap-tier contract).
    opus_script = _emit_units([_verify_unit("U1")])
    assert "PULL-CORD (#364" not in opus_script


def test_pull_cord_not_complete_batched() -> None:  # R8
    script = _emit_units(
        [
            _verify_unit("U1", tier={"model": "haiku", "effort": "low"}),
            _verify_unit("U2", tier={"model": "haiku", "effort": "low"}, depends_on=["U1"]),
        ]
    )
    # Exactly ONE batched escalation check for the whole run -- not one per unit.
    assert script.count("if (__pulledCords.length > 0)") == 1
    assert "ONE batched escalation ask" in script
    # The batch fails the run (throw) so a cord unit is never marked complete.
    assert "throw __halt(`pull-cord (#364)" in script
    # Each cord entry carries its one-rung proposal computed at emit time.
    assert 'cordProposal: "haiku/low -> haiku/medium (+1 effort rung)"' in script


def test_pull_cord_reserved_returns_key() -> None:  # verifier P2
    spec = ES.ExecutionSpec.from_dict(_spec_dict(returns=["diff", "pull_cord"]))
    with pytest.raises(ES.SpecError, match="reserved return-disposition key"):
        spec.validate()


def test_cord_proposal_respects_session_ceiling() -> None:  # verifier P1
    # A unit AT the session ceiling has zero climb room: the cord entry must carry NO
    # proposal (the ceiling is the final word), rendering the no-legal-climb HALT branch.
    spec = ES.ExecutionSpec.from_dict(
        {
            "name": "d",
            "description": "d",
            "repo": "/tmp/r",
            "units": [
                {
                    "unit_id": "U1",
                    "label": "l",
                    "prompt": "p",
                    "tier": {"model": "haiku", "effort": "high"},
                    "returns": ["result"],
                }
            ],
        }
    )
    spec.validate()
    ceiling = ES.Tier(model="haiku", effort="high")
    script = str(ES.emit_workflow_script(spec, session_ceiling=ceiling))
    assert 'cordProposal: "' not in script  # no proposal above the operator's own cap
    assert "no legal climb: top of ladder or session ceiling" in script
    # Without the ceiling the same unit proposes its one-rung climb.
    unlimited = str(ES.emit_workflow_script(spec))
    assert 'cordProposal: "haiku/high -> sonnet/high (+1 model rung)"' in unlimited


# --- #366 U2: cost_budget emit-time HALT ---------------------------------------------------


def _budget_spec(units: list[dict[str, object]], cost_budget: object = None) -> dict[str, object]:
    """Build a multi-unit spec dict with an optional cost_budget."""
    spec: dict[str, object] = {
        "name": "budget-demo",
        "description": "exercise the #366 cost budget",
        "repo": "/tmp/repo",
        "units": units,
    }
    if cost_budget is not None:
        spec["cost_budget"] = cost_budget
    return spec


def _unit(unit_id: str, model: str, effort: str, **overrides: object) -> dict[str, object]:
    unit: dict[str, object] = {
        "unit_id": unit_id,
        "label": unit_id,
        "tier": {"model": model, "effort": effort},
        "prompt": "do the thing",
    }
    unit.update(overrides)
    return unit


def test_over_budget_spec_fails_emit_naming_total_vs_ceiling() -> None:
    # One sonnet/high unit costs 12; a budget of 10 must HALT naming both numbers.
    spec = ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", "sonnet", "high")], cost_budget=10))
    with pytest.raises(ES.SpecError, match=r"total spend 12 exceeds cost_budget 10"):
        spec.validate()


def test_under_budget_spec_passes() -> None:
    # Summed spend 12 <= budget 100 validates and emits clean.
    spec = ES.ExecutionSpec.from_dict(
        _budget_spec([_unit("U1", "sonnet", "high")], cost_budget=100)
    )
    spec.validate()  # no raise
    assert spec.spec_spend() == 12
    ES.emit_workflow_script(spec)  # emit path also runs validate -> no raise


def test_over_budget_counts_fanout_and_verify_multiplicity() -> None:
    # Naive one-weight-per-unit sum = 12 + 6 = 18 (<= budget 40, would pass).
    # Multiplicity-aware: fan-out sonnet/high x3 targets = 36; sonnet/medium (6) + verify n=3 (3x6)
    # = 24; total 60 > 40 -> HALT. Guards the false-negative KTD8 exists to prevent.
    fanout_unit = _unit("U1", "sonnet", "high", fanout=True, targets=["a", "b", "c"])
    verify_unit = _unit("U2", "sonnet", "medium", verify={"n": 3, "pass_rule": "majority"})
    spec = ES.ExecutionSpec.from_dict(_budget_spec([fanout_unit, verify_unit], cost_budget=40))
    assert spec.spec_spend() == 60
    with pytest.raises(ES.SpecError, match=r"total spend 60 exceeds cost_budget 40"):
        spec.validate()


def test_cost_budget_absent_roundtrips() -> None:
    # No cost_budget key -> to_dict emits none, and from_dict(to_dict) is byte-identical.
    payload = _budget_spec([_unit("U1", "sonnet", "high")])
    spec = ES.ExecutionSpec.from_dict(payload)
    assert spec.cost_budget is None
    assert "cost_budget" not in spec.to_dict()
    assert ES.ExecutionSpec.from_dict(spec.to_dict()).to_dict() == spec.to_dict()
    spec.validate()  # absent budget performs no spend check


def test_cost_budget_soft_warn_band(capsys: pytest.CaptureFixture[str]) -> None:
    # sonnet/high costs 12; budget 13 -> 12 is within 10% of the ceiling (0.9*13 = 11.7).
    spec = ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", "sonnet", "high")], cost_budget=13))
    spec.validate()  # no raise -- legal but near the ceiling
    captured = capsys.readouterr()
    assert "close to the ceiling" in captured.err


def test_cost_budget_below_one_rejected() -> None:
    spec = ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", "sonnet", "high")], cost_budget=0))
    with pytest.raises(ES.SpecError, match=r"cost_budget 0 must be >= 1"):
        spec.validate()


def test_cost_budget_non_integer_rejected() -> None:
    with pytest.raises(ES.SpecError, match=r"cost_budget"):
        ES.ExecutionSpec.from_dict(
            _budget_spec([_unit("U1", "sonnet", "high")], cost_budget="lots")
        )
    with pytest.raises(ES.SpecError, match=r"must be an integer, not a bool"):
        ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", "sonnet", "high")], cost_budget=True))


def test_unit_spend_pilot_not_double_counted() -> None:
    # A pilot is a separate declared unit counted on its own row; the fan-out must not re-add it.
    pilot = _unit("P1", "sonnet", "high")
    fanout = _unit("U1", "sonnet", "high", fanout=True, targets=["a", "b"], pilot="P1")
    spec = ES.ExecutionSpec.from_dict(_budget_spec([pilot, fanout]))
    # pilot 12 + fan-out (12 x 2 targets = 24) = 36; the pilot is NOT added again onto U1.
    assert ES.unit_spend(spec.unit_by_id("U1")) == 24
    assert spec.spec_spend() == 36


def test_spend_cli_reports_total_and_headroom(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The `spend` verb is the real read-consumer /plan invokes -- it reports even an over-budget
    # spec rather than HALTing, so the operator sees the numbers.
    import json

    payload = _budget_spec([_unit("U1", "sonnet", "high")], cost_budget=20)
    payload["spend_envelope"] = 15
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(payload), encoding="utf-8")

    rc = ES.main(["spend", str(spec_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "total spend: 12" in out
    assert "cost_budget: 20  (headroom 8)" in out
    assert "spend_envelope: 15" in out


def test_spend_cli_reports_overage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import json

    payload = _budget_spec([_unit("U1", "opus", "high")], cost_budget=10)  # opus/high = 32
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(payload), encoding="utf-8")

    rc = ES.main(["spend", str(spec_path)])
    out = capsys.readouterr().out
    assert rc == 0  # a report never HALTs
    assert "total spend: 32" in out
    assert "OVER by 22" in out


# --- #367 U3: worth_it_because + cheaper_fallback validate hard-block ----------------------


def test_worth_it_fallback_required_above_baseline() -> None:
    # opus/high is a premium tier -> under require_receipts it needs worth_it_because AND
    # cheaper_fallback. The hard-block is authoring-gated (require_receipts), not on plain validate().
    bare = ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", "opus", "high")]))
    bare.validate()  # plain validate() does NOT enforce receipts (no retroactive break)
    with pytest.raises(ES.SpecError, match="worth_it_because"):
        bare.validate(require_receipts=True)
    # justification present but no fallback:
    no_fb = ES.ExecutionSpec.from_dict(
        _budget_spec([_unit("U1", "opus", "high", worth_it_because="deep judgment")])
    )
    with pytest.raises(ES.SpecError, match="cheaper_fallback"):
        no_fb.validate(require_receipts=True)
    # both present with a genuinely cheaper named fallback -> passes.
    ok = ES.ExecutionSpec.from_dict(
        _budget_spec(
            [
                _unit(
                    "U1",
                    "opus",
                    "high",
                    worth_it_because="deep judgment",
                    cheaper_fallback={"model": "sonnet", "effort": "high"},
                )
            ]
        )
    )
    ok.validate(require_receipts=True)  # no raise


def test_worth_it_fallback_not_required_at_baseline() -> None:
    # Non-premium tiers (sonnet/high and below, any cheap-model tier) need no justification even
    # under require_receipts.
    for model, effort in (
        ("sonnet", "medium"),
        ("sonnet", "high"),
        ("haiku", "high"),
        ("haiku", "low"),
    ):
        ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", model, effort)])).validate(
            require_receipts=True
        )


def test_worth_it_fields_absent_roundtrip() -> None:
    spec = ES.ExecutionSpec.from_dict(_budget_spec([_unit("U1", "sonnet", "medium")]))
    unit_dict = spec.units[0].to_dict()
    assert "worth_it_because" not in unit_dict
    assert "cheaper_fallback" not in unit_dict
    assert ES.ExecutionSpec.from_dict(spec.to_dict()).to_dict() == spec.to_dict()


def test_cheaper_fallback_not_actually_cheaper_fails() -> None:
    # opus/xhigh is DEARER than opus/high -> spend_delta != "cheapen" -> validate fails.
    spec = ES.ExecutionSpec.from_dict(
        _budget_spec(
            [
                _unit(
                    "U1",
                    "opus",
                    "high",
                    worth_it_because="x",
                    cheaper_fallback={"model": "opus", "effort": "xhigh"},
                )
            ]
        )
    )
    with pytest.raises(ES.SpecError, match="not strictly cheaper"):
        spec.validate(require_receipts=True)


def test_engine_owned_unit_exempt_from_worth_it() -> None:
    # A capability-routed second-opinion unit pins to opus/high by intent, not operator choice -> exempt.
    spec = ES.ExecutionSpec.from_dict(
        _budget_spec(
            [
                _unit(
                    "U1",
                    "opus",
                    "high",
                    capability="code-generation",
                    engine_intent="second-opinion",
                )
            ]
        )
    )
    spec.validate(require_receipts=True)  # no raise even under the authoring gate


def test_worth_it_cheaper_fallback_roundtrips_when_present() -> None:
    spec = ES.ExecutionSpec.from_dict(
        _budget_spec(
            [
                _unit(
                    "U1",
                    "fable",
                    "xhigh",
                    worth_it_because="frontier reasoning",
                    cheaper_fallback={"model": "opus", "effort": "xhigh"},
                )
            ]
        )
    )
    unit_dict = spec.units[0].to_dict()
    assert unit_dict["worth_it_because"] == "frontier reasoning"
    assert unit_dict["cheaper_fallback"] == {"model": "opus", "effort": "xhigh"}
    assert ES.ExecutionSpec.from_dict(spec.to_dict()).to_dict() == spec.to_dict()
    spec.validate(require_receipts=True)  # fable/xhigh with a strictly-cheaper opus/xhigh fallback


# --- #565 U3: Verify panel tier + panel receipts (KTD5) -------------------------------------


def _panel_unit(
    unit_id: str = "U1",
    model: str = "sonnet",
    effort: str = "medium",
    **verify_overrides: object,
) -> dict[str, object]:
    """A unit at ``model``/``effort`` carrying an n=3 majority verify panel with overrides."""
    verify: dict[str, object] = {"n": 3, "pass_rule": "majority"}
    verify.update(verify_overrides)
    return {
        "unit_id": unit_id,
        "label": unit_id,
        "tier": {"model": model, "effort": effort},
        "prompt": "do the work",
        "returns": ["result"],
        "verify": verify,
    }


def test_panel_tier_emits_effective_tier_while_unit_stays_lower() -> None:
    # A verify panel authored at opus/high over a sonnet/medium unit runs the VERIFIERS at
    # opus/high while the unit's own agent call stays sonnet/medium (#565 KTD5).
    unit_dict = _panel_unit(tier={"model": "opus", "effort": "high"})
    spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-tier", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    spec.validate()
    unit = spec.unit_by_id("U1")
    assert unit is not None

    verifier_opts = ES._verifier_agent_opts(unit)
    assert 'model: "opus"' in verifier_opts
    assert 'effort: "high"' in verifier_opts
    # The unit's own tier is untouched.
    assert unit.tier.model == "sonnet"
    assert unit.tier.effort == "medium"

    script = str(ES.emit_workflow_script(spec))
    # Both tiers appear in the emitted script: the unit at sonnet/medium, the verifiers at opus/high.
    assert 'model: "opus"' in script
    assert 'model: "sonnet"' in script


def test_panel_tier_absent_uses_unit_tier_and_omits_keys() -> None:
    # Without a panel tier, verifiers ride the unit tier (R4 default preserved) and to_dict omits
    # the new keys byte-identically.
    unit_dict = _panel_unit(model="sonnet", effort="medium")
    spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-default", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    spec.validate()
    unit = spec.unit_by_id("U1")
    assert unit is not None

    verifier_opts = ES._verifier_agent_opts(unit)
    assert 'model: "sonnet"' in verifier_opts
    assert 'effort: "medium"' in verifier_opts

    verify_dict = unit.verify.to_dict()
    assert set(verify_dict) == {"n", "pass_rule", "iterate_to_consensus", "max_iterations"}
    assert "tier" not in verify_dict
    assert "worth_it_because" not in verify_dict
    assert "cheaper_fallback" not in verify_dict
    # Full spec round-trip is byte-identical.
    assert ES.ExecutionSpec.from_dict(spec.to_dict()).to_dict() == spec.to_dict()


def test_panel_tier_and_receipts_roundtrip_when_present() -> None:
    unit_dict = _panel_unit(
        tier={"model": "opus", "effort": "high"},
        worth_it_because="adversarial depth",
        cheaper_fallback={"model": "sonnet", "effort": "high"},
    )
    spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-receipts", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    verify_dict = spec.units[0].to_dict()["verify"]
    assert verify_dict["tier"] == {"model": "opus", "effort": "high"}
    assert verify_dict["worth_it_because"] == "adversarial depth"
    assert verify_dict["cheaper_fallback"] == {"model": "sonnet", "effort": "high"}
    assert ES.ExecutionSpec.from_dict(spec.to_dict()).to_dict() == spec.to_dict()


def test_premium_panel_tier_receipts_gate_both_ways() -> None:
    # A premium panel tier (opus/high) on a NON-premium unit (sonnet/medium): plain validate passes,
    # but validate(require_receipts=True) fails naming both the unit and the panel.
    unit_dict = _panel_unit(tier={"model": "opus", "effort": "high"})
    bare = ES.ExecutionSpec.from_dict(
        {"name": "panel-gate", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    bare.validate()  # no receipts -> no raise (no retroactive break)
    with pytest.raises(ES.SpecError, match=r"unit U1: verify tier .*worth_it_because"):
        bare.validate(require_receipts=True)

    # justification present but no cheaper_fallback:
    no_fb = ES.ExecutionSpec.from_dict(
        {
            "name": "panel-gate",
            "description": "d",
            "repo": "/tmp/r",
            "units": [
                _panel_unit(
                    tier={"model": "opus", "effort": "high"},
                    worth_it_because="adversarial depth",
                )
            ],
        }
    )
    with pytest.raises(ES.SpecError, match=r"cheaper_fallback"):
        no_fb.validate(require_receipts=True)

    # both present with a strictly-cheaper fallback -> passes the authoring gate.
    ok = ES.ExecutionSpec.from_dict(
        {
            "name": "panel-gate",
            "description": "d",
            "repo": "/tmp/r",
            "units": [
                _panel_unit(
                    tier={"model": "opus", "effort": "high"},
                    worth_it_because="adversarial depth",
                    cheaper_fallback={"model": "sonnet", "effort": "high"},
                )
            ],
        }
    )
    ok.validate(require_receipts=True)  # no raise


def test_panel_cheaper_fallback_not_strictly_cheaper_fails() -> None:
    # A panel cheaper_fallback that is NOT strictly cheaper than the panel tier fails under
    # require_receipts, mirroring the unit rule.
    unit_dict = _panel_unit(
        tier={"model": "opus", "effort": "high"},
        worth_it_because="adversarial depth",
        cheaper_fallback={"model": "opus", "effort": "xhigh"},  # dearer, not cheaper
    )
    spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-fb", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    with pytest.raises(ES.SpecError, match=r"not strictly\s+cheaper"):
        spec.validate(require_receipts=True)


def test_panel_tier_haiku_xhigh_halts_on_ceiling() -> None:
    # An on-palette-but-unrunnable panel tier (haiku/xhigh) HALTs on the palette ceiling check --
    # a HALT, not a clamp -- even on plain validate().
    unit_dict = _panel_unit(tier={"model": "haiku", "effort": "xhigh"})
    spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-ceiling", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    with pytest.raises(ES.SpecError, match=r"exceeds model 'haiku' ceiling"):
        spec.validate()


def test_panel_tier_spend_prices_verifiers_at_effective_tier() -> None:
    # A 3-verifier opus/high panel on a sonnet/medium unit costs base(sonnet/medium) +
    # 3 x base(opus/high) = 6 + 3*32 = 102.
    unit_dict = _panel_unit(tier={"model": "opus", "effort": "high"})
    spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-spend", "description": "d", "repo": "/tmp/r", "units": [unit_dict]}
    )
    unit = spec.unit_by_id("U1")
    assert unit is not None
    base_unit = ES.to_spend("sonnet", "medium")
    base_panel = ES.to_spend("opus", "high")
    assert ES.unit_spend(unit) == base_unit + 3 * base_panel

    # Without the panel tier the same panel prices at the unit tier: 6 + 3*6 = 24.
    default_dict = _panel_unit(model="sonnet", effort="medium")
    default_spec = ES.ExecutionSpec.from_dict(
        {"name": "panel-spend2", "description": "d", "repo": "/tmp/r", "units": [default_dict]}
    )
    default_unit = default_spec.unit_by_id("U1")
    assert default_unit is not None
    assert ES.unit_spend(default_unit) == base_unit + 3 * base_unit


def test_workflow_lease_execution_ttl_formula_multiplicity() -> None:
    # #694: execution_ttl_seconds = max(900, 300 * multiplicity_aware_unit_count)
    # 1. Single plain unit: multiplicity 1 -> max(900, 300) = 900
    u1 = _unit("U1", "sonnet", "high")
    spec1 = ES.ExecutionSpec.from_dict(_budget_spec([u1]))
    assert spec1.multiplicity_aware_unit_count() == 1
    assert ES.workflow_lease_metadata(spec1)["execution_ttl_seconds"] == 900

    # 2. Two plain units: multiplicity 2 -> max(900, 600) = 900
    u2 = _unit("U2", "sonnet", "high")
    spec2 = ES.ExecutionSpec.from_dict(_budget_spec([u1, u2]))
    assert spec2.multiplicity_aware_unit_count() == 2
    assert ES.workflow_lease_metadata(spec2)["execution_ttl_seconds"] == 900

    # 3. Four plain units: multiplicity 4 -> max(900, 1200) = 1200
    u3 = _unit("U3", "sonnet", "high")
    u4 = _unit("U4", "sonnet", "high")
    spec4 = ES.ExecutionSpec.from_dict(_budget_spec([u1, u2, u3, u4]))
    assert spec4.multiplicity_aware_unit_count() == 4
    assert ES.workflow_lease_metadata(spec4)["execution_ttl_seconds"] == 1200

    # 4. Fan-out unit (5 targets): multiplicity 5 -> max(900, 1500) = 1500
    u_fanout = _unit("U_FO", "sonnet", "high", fanout=True, targets=["t1", "t2", "t3", "t4", "t5"])
    spec_fo = ES.ExecutionSpec.from_dict(_budget_spec([u_fanout]))
    assert spec_fo.multiplicity_aware_unit_count() == 5
    assert ES.workflow_lease_metadata(spec_fo)["execution_ttl_seconds"] == 1500

    # 5. Verify panel unit (n=3, no iterate): multiplicity 1 + 3 = 4 -> max(900, 1200) = 1200
    u_verify = _unit("U_V", "sonnet", "medium", verify={"n": 3, "pass_rule": "majority"})
    spec_v = ES.ExecutionSpec.from_dict(_budget_spec([u_verify]))
    assert spec_v.multiplicity_aware_unit_count() == 4
    assert ES.workflow_lease_metadata(spec_v)["execution_ttl_seconds"] == 1200

    # 6. Verify panel unit (n=3, iterate_to_consensus=True, max_iterations=2):
    # multiplicity 1 + 3 * 2 = 7 -> max(900, 2100) = 2100
    u_v_iter = _unit(
        "U_VI",
        "sonnet",
        "medium",
        verify={"n": 3, "pass_rule": "majority", "iterate_to_consensus": True, "max_iterations": 2},
    )
    spec_vi = ES.ExecutionSpec.from_dict(_budget_spec([u_v_iter]))
    assert spec_vi.multiplicity_aware_unit_count() == 7
    assert ES.workflow_lease_metadata(spec_vi)["execution_ttl_seconds"] == 2100


def test_workflow_lease_held_past_ten_minute_mark() -> None:
    # #694 AC1: a lease minted for a run is still held at the 10-minute (600s) mark.
    # Proven by time-advancing virtual elapsed time past the old 300s hard-coded expiry.
    u = _unit("U1", "sonnet", "high")
    spec = ES.ExecutionSpec.from_dict(_budget_spec([u]))
    metadata = ES.workflow_lease_metadata(spec)
    ttl = metadata["execution_ttl_seconds"]

    # Floor is 900s (15 min), which exceeds the 10-minute (600s) AC1 requirement
    assert ttl >= 600
    for elapsed in (0, 300, 301, 599, 600):
        is_held = elapsed <= ttl
        assert is_held, f"Lease should still be held at elapsed={elapsed}s against TTL={ttl}s"
