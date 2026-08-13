"""Execution-class vocabulary and the runtime sibling of ``resolve()``.

The plan named ``tests/test_fleet_core_lineage_models.py``. This file is used instead:
KTD7 refused to port ``lineage_models``, and naming the suite after the thing we
deliberately did not adopt would mislead the next reader.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import pathlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
FLEET_CORE_SCRIPTS = REPO_ROOT / "plugins" / "fleet-core" / "scripts"
MODELS_JSON = FLEET_CORE_SCRIPTS / "fleet_commons" / "models.json"

sys.path.insert(0, str(FLEET_CORE_SCRIPTS))

from fleet_commons import tier_palette, tier_resolver  # noqa: E402
from fleet_commons.tier_resolver import (  # noqa: E402
    Resolution,
    RuntimeResolution,
    TierResolverError,
    adapt_runtime_argv,
    resolve,
    resolve_for_runtime,
)

# The twelve existing production/test modules the brief listed as resolve() consumers.
_EXISTING_RESOLVE_CONSUMERS = (
    "plugins/fleet-core/scripts/fleet_commons/intent_envelope.py",
    "plugins/fleet-core/scripts/fleet_commons/render_tier_table.py",
    "plugins/fleet-core/scripts/fleet_commons/tier_resolver.py",
    "plugins/saga/scripts/execution_spec.py",
    "plugins/saga/scripts/team_emitter.py",
    "plugins/saga/scripts/tier_defaults.py",
    "tests/test_agent_spec_lint.py",
    "tests/test_effort_rider.py",
    "tests/test_intent_envelope.py",
    "tests/test_spend_delta.py",
    "tests/test_tier_resolver.py",
    "tests/test_tier_vocab_single_source.py",
)


def _registry() -> dict[str, Any]:
    loaded = json.loads(MODELS_JSON.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_existing_models_and_efforts_readers_are_unaffected() -> None:
    """Added version-2 keys must not change the Claude vocabulary or its derivation."""
    registry = _registry()
    assert registry["models"] == {
        "fable": {"rank": 0, "effort_ceiling": "xhigh"},
        "opus": {"rank": 1, "effort_ceiling": "xhigh"},
        "sonnet": {"rank": 2, "effort_ceiling": "xhigh"},
        "haiku": {"rank": 3, "effort_ceiling": "high"},
    }
    assert registry["efforts"] == {
        "low": {"rung": 0},
        "medium": {"rung": 1},
        "high": {"rung": 2},
        "xhigh": {"rung": 3},
    }
    assert "lineage_models" not in registry
    assert "lineage_efforts" not in registry
    assert registry["schema_version"] == 2
    assert set(registry["scalar_efforts"]) == {"low", "medium", "high", "xhigh", "max"}
    assert tier_palette.MODELS == ("fable", "opus", "sonnet", "haiku")
    assert tier_palette.EFFORTS == ("low", "medium", "high", "xhigh")
    assert tier_palette.SCALAR_EFFORTS == ("low", "medium", "high", "xhigh", "max")
    models_by_rank = tuple(
        name for name, _ in sorted(registry["models"].items(), key=lambda kv: kv[1]["rank"])
    )
    efforts_by_rung = tuple(
        name for name, _ in sorted(registry["efforts"].items(), key=lambda kv: kv[1]["rung"])
    )
    assert models_by_rank == tier_palette.MODELS
    assert efforts_by_rung == tier_palette.EFFORTS


def test_existing_resolve_call_sites_are_unaffected_by_the_sibling() -> None:
    """``resolve()`` keeps its signature, return type, and positional call shape."""
    signature = inspect.signature(resolve)
    assert list(signature.parameters) == [
        "role_kind",
        "work_shape",
        "envelope_ceiling",
        "operator_override",
        "policy",
    ]
    assert signature.parameters["policy"].kind is inspect.Parameter.KEYWORD_ONLY
    result = resolve(None, "judgment")
    assert isinstance(result, Resolution)
    assert not isinstance(result, RuntimeResolution)
    assert (result.model, result.effort) == ("opus", "high")
    policy = tier_resolver.load_policy()
    for work_shape, row in policy.items():
        resolved = resolve(None, work_shape)
        assert resolved.model == row["default_model"]
        assert resolved.effort == row["default_effort"]
    # Positional form used by plugins/saga/scripts/tier_defaults.py:71.
    positional = resolve(None, "mechanical")
    assert (positional.model, positional.effort) == ("sonnet", "medium")
    # The sibling is a different callable; wrapping resolve still sees the original.
    resolve_fn = resolve
    wrapped = resolve_fn(None, "purely-mechanical")
    assert (wrapped.model, wrapped.effort) == ("haiku", "low")
    assert resolve_for_runtime is not resolve
    assert "resolve_for_runtime" in inspect.getsource(tier_resolver)

    saga_scripts = REPO_ROOT / "plugins" / "saga" / "scripts"
    if str(saga_scripts) not in sys.path:
        sys.path.insert(0, str(saga_scripts))

    defaults_spec = importlib.util.spec_from_file_location(
        "u1_tier_defaults_consumer", saga_scripts / "tier_defaults.py"
    )
    assert defaults_spec is not None and defaults_spec.loader is not None
    defaults_mod = importlib.util.module_from_spec(defaults_spec)
    sys.modules["u1_tier_defaults_consumer"] = defaults_mod
    defaults_spec.loader.exec_module(defaults_mod)
    assert defaults_mod._registry_default("judgment") == {"model": "opus", "effort": "high"}

    emitter_spec = importlib.util.spec_from_file_location(
        "u1_team_emitter_consumer", saga_scripts / "team_emitter.py"
    )
    assert emitter_spec is not None and emitter_spec.loader is not None
    emitter_mod = importlib.util.module_from_spec(emitter_spec)
    sys.modules["u1_team_emitter_consumer"] = emitter_mod
    emitter_spec.loader.exec_module(emitter_mod)
    wrapped_calls: list[tuple[Any, ...]] = []

    def _wrapped_resolve(
        role_kind: str | None,
        work_shape: str,
        envelope_ceiling: str | None = None,
        operator_override: dict[str, str] | None = None,
        *,
        policy: dict[str, dict[str, str]] | None = None,
    ) -> Resolution:
        del envelope_ceiling, policy
        wrapped_calls.append((role_kind, work_shape, operator_override))
        return resolve(role_kind, work_shape, operator_override=operator_override)

    # Live wrap: agent-frontmatter layer calls the real resolve() through the
    # function object the emitter holds (team_emitter.py:129).
    live_seg = SimpleNamespace(tier=SimpleNamespace(model="opus", effort=None))
    live_effort, live_layer = emitter_mod.resolve_teammate_effort(live_seg, None)
    assert live_layer == "agent-frontmatter"
    assert live_effort == "high"
    injected_effort, injected_layer = emitter_mod.resolve_teammate_effort(
        live_seg, None, resolve=_wrapped_resolve
    )
    assert injected_layer == "agent-frontmatter"
    assert injected_effort == "high"
    assert wrapped_calls == [(None, "judgment", None)]
    assert "plugins/saga/scripts/tier_defaults.py" in _EXISTING_RESOLVE_CONSUMERS
    assert "plugins/saga/scripts/team_emitter.py" in _EXISTING_RESOLVE_CONSUMERS


def test_one_work_shape_resolves_to_different_models_for_claude_and_codex() -> None:
    claude = resolve_for_runtime("review-high", "claude")
    codex = resolve_for_runtime("review-high", "codex")
    assert claude.model == "fable"
    assert codex.model == "gpt-5.6-sol"
    assert claude.model != codex.model
    assert claude.effort == "high"
    assert codex.effort == "high"
    assert claude.workspace_boundary == "read-only"
    assert codex.workspace_boundary == "read-only"


def test_each_runtime_resolves_to_concrete_pair_and_correct_argv() -> None:
    expected = {
        "claude": (
            "fable",
            "max",
            ["--model", "fable", "--effort", "max"],
            {"mode": "argv"},
        ),
        "codex": (
            "gpt-5.6-sol",
            "max",
            ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=max"],
            {"mode": "argv"},
        ),
        "grok": (
            "grok-4.6",
            "xhigh",
            ["--model", "grok-4.6", "--reasoning-effort", "xhigh"],
            {"mode": "argv"},
        ),
        "muse": (
            "muse-spark-1.2-contributor",
            "xhigh",
            ["--model", "muse-spark-1.2-contributor", "--reasoning-effort", "xhigh"],
            {"mode": "argv"},
        ),
        "qwen": (
            "qwen3.8-max-preview",
            "max",
            ["--model", "qwen3.8-max-preview"],
            {"mode": "in_session", "command": "/effort max"},
        ),
        "agy": (
            "gemini-3.1-pro-high",
            "high",
            ["--model", "gemini-3.1-pro-high", "--effort", "high"],
            {"mode": "argv"},
        ),
    }
    assert set(expected) == set(tier_resolver.SUPPORTED_RUNTIMES)
    for runtime, (model, effort, argv, application) in expected.items():
        resolved = resolve_for_runtime("review-max", runtime)
        assert resolved.model == model, runtime
        assert resolved.effort == effort, runtime
        assert resolved.effort_application == application, runtime
        assert adapt_runtime_argv(runtime, resolved.model, resolved.effort) == argv
        # Authoritative max must collapse before it can reach a vendor that
        # cannot represent it as a launch flag.
        assert adapt_runtime_argv(runtime, model, "max") == argv
        if runtime in {"grok", "muse", "agy"}:
            assert "max" not in argv
    qwen_low = resolve_for_runtime("scan-low", "qwen")
    assert qwen_low.effort == "low"
    assert qwen_low.effort_application == {"mode": "in_session", "command": "/effort low"}
    assert adapt_runtime_argv("qwen", qwen_low.model, qwen_low.effort) == [
        "--model",
        "qwen3.7-plus",
    ]


def test_unknown_work_shape_raises_rather_than_defaulting() -> None:
    with pytest.raises(TierResolverError, match="unknown work_shape"):
        resolve_for_runtime("judgment", "claude")
    with pytest.raises(TierResolverError, match="unknown work_shape"):
        resolve_for_runtime("not-a-real-class", "codex")


def test_unknown_runtime_raises() -> None:
    with pytest.raises(TierResolverError, match="unknown runtime"):
        resolve_for_runtime("review-high", "opencode")
    with pytest.raises(TierResolverError, match="unknown runtime"):
        adapt_runtime_argv("hermes", "fable", "high")


def test_fallbacks_are_returned_in_declared_order() -> None:
    registry = _registry()
    declared = registry["execution_classes"]["review-max"]["fallbacks"]
    assert [row["model"] for row in declared] == ["gpt-5.6-terra", "gpt-5.5"]
    claude = resolve_for_runtime("review-max", "claude")
    assert [row["model"] for row in claude.fallbacks] == ["opus", "sonnet"]
    assert [row["effort"] for row in claude.fallbacks] == ["max", "max"]
    codex = resolve_for_runtime("review-max", "codex")
    assert [row["model"] for row in codex.fallbacks] == ["gpt-5.6-terra", "gpt-5.5"]
    assert [row["effort"] for row in codex.fallbacks] == ["max", "max"]
    grok = resolve_for_runtime("review-max", "grok")
    assert [row["model"] for row in grok.fallbacks] == ["grok-4.5", "grok-4.5"]
    assert [row["effort"] for row in grok.fallbacks] == ["xhigh", "xhigh"]
    muse = resolve_for_runtime("review-max", "muse")
    assert [row["model"] for row in muse.fallbacks] == [
        "muse-spark-1.2-contributor",
        "muse-spark-1.2-contributor",
    ]
    assert [row["effort"] for row in muse.fallbacks] == ["xhigh", "xhigh"]
    agy = resolve_for_runtime("review-max", "agy")
    assert [row["model"] for row in agy.fallbacks] == [
        "gemini-3.6-flash-high",
        "gemini-3.5-flash-high",
    ]
    assert [row["effort"] for row in agy.fallbacks] == ["high", "high"]
    qwen = resolve_for_runtime("review-max", "qwen")
    assert [row["model"] for row in qwen.fallbacks] == ["qwen3.7-plus", "qwen3.6-plus"]
    assert [row["effort"] for row in qwen.fallbacks] == ["max", "max"]
    review_high = resolve_for_runtime("review-high", "claude")
    assert [row["model"] for row in review_high.fallbacks] == ["opus", "sonnet"]
    assert [row["effort"] for row in review_high.fallbacks] == ["high", "high"]


def test_resolver_does_not_predict_another_program_settings() -> None:
    """Settings-file prediction was the wrong problem; the functions must stay gone."""
    source = inspect.getsource(tier_resolver)
    for gone in (
        "qwen_ambient_effort",
        "_assert_qwen_can_deliver",
        "_load_qwen_json_object",
        "_discover_qwen_home",
        "_require_qwen_cwd",
        "trustedFolders",
        "reasoningEffort",
    ):
        assert gone not in source
    assert "cwd" not in inspect.signature(resolve_for_runtime).parameters
    assert "cwd" not in inspect.signature(adapt_runtime_argv).parameters
