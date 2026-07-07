"""Oracle tests for the Saga external-engine resolver (U2/U3)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
REGISTRY_SCRIPT = SCRIPT_DIR / "engine_registry.py"
RESOLVER_SCRIPT = SCRIPT_DIR / "engine_resolver.py"


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


REG = _load("engine_registry", REGISTRY_SCRIPT)
R = _load("engine_resolver", RESOLVER_SCRIPT)


def _valid_registry_dict() -> dict[str, Any]:
    return {
        "capabilities": list(REG.CAPABILITIES),
        "engines": [
            {
                "engine_id": "codex",
                "variant": "gpt-5.5-xhigh",
                "substrate": "external",
                "default_for_engine": True,
                "invocation": {
                    "via": "codex:delegate",
                    "recipe": "codex exec -s read-only -c model_reasoning_effort=xhigh",
                    "write_capable": False,
                },
                "context_window": 400000,
                "cost_speed_rank": 2,
                "model_identity": "gpt-5.5",
                "last_validated": "2026-06-27",
                "receipt_emitter": "codex-bridge",
                "capability_profile": {
                    "code-generation": {
                        "rating": "STRONG",
                        "note": "structured-output fidelity, multi-file refactor",
                    },
                    "adversarial-review": {
                        "rating": "STRONG",
                        "note": "hardest reviewer tasks",
                    },
                    "debug": {
                        "rating": "STRONG",
                        "note": "tool-orchestrated debugging",
                    },
                    "long-form-writing": {
                        "rating": "WEAK",
                        "note": "route prose-heavy work to Claude",
                    },
                },
                "prompting_protocol": [
                    "Run read-only when generating against the repo.",
                    "Return a unified diff plus assumptions.",
                ],
                "sources": [
                    {
                        "claim": "top composite reasoning",
                        "url": "https://example.invalid/codex",
                        "date": "2026-06-27",
                        "tag": "OFFICIAL",
                        "corroboration": "STRONG",
                    }
                ],
            },
            {
                "engine_id": "agy",
                "variant": "gemini-3.1-pro-high",
                "substrate": "in-repo",
                "default_for_engine": True,
                "invocation": {
                    "via": "agy:delegate",
                    "recipe": "agy delegate --mode no-write",
                    "write_capable": False,
                    "model": "Gemini 3.1 Pro (High)",
                },
                "context_window": 1000000,
                "cost_speed_rank": 1,
                "model_identity": "gemini-3.1-pro",
                "last_validated": "2026-06-20",
                "receipt_emitter": "agy-delegate",
                "capability_profile": {
                    "code-generation": {
                        "rating": "MODERATE",
                        "note": "useful second implementation opinion",
                    },
                    "adversarial-review": {
                        "rating": "MODERATE",
                        "note": "cross-family reviewer",
                    },
                    "debug": {
                        "rating": "MODERATE",
                        "note": "useful second opinion",
                    },
                },
                "prompting_protocol": [
                    "Use the no-write envelope for evidence-only work.",
                    "Return findings for Claude verification.",
                ],
                "sources": [
                    {
                        "claim": "large context review path",
                        "url": "https://example.invalid/agy",
                        "date": "2026-06-20",
                        "tag": "LOCAL",
                        "corroboration": "MODERATE",
                    }
                ],
            },
        ],
        "roles": {
            "cross-family-review-panel": {
                "members": ["codex/gpt-5.5-xhigh", "agy/gemini-3.1-pro-high"],
                "verdict": "advisory",
                "verifier": "claude",
            }
        },
    }


def _write_registry(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "engine-registry.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture
def registry(tmp_path: Path) -> Any:
    return REG.Registry.load(_write_registry(tmp_path, _valid_registry_dict()))


@pytest.fixture
def engine_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        R,
        "preflight",
        lambda engine_id, **_kwargs: {"available": True, "reason": f"{engine_id} available"},
    )


@pytest.mark.usefixtures("engine_available")
def test_capability_dispatch_returns_variant_protocol_and_payload(registry: Any) -> None:
    context = "Implement the bounded change."

    resolution = R.resolve(
        {
            "capability": "code-generation",
            "role_kind": "generator",
            "task_context": {"context": context},
        },
        mode="dispatch",
        registry=registry,
    )

    assert resolution.engine_id == "codex"
    assert resolution.variant == "gpt-5.5-xhigh"
    assert resolution.effort == "xhigh"
    assert resolution.recipe == "codex exec -s read-only -c model_reasoning_effort=xhigh"
    assert resolution.protocol == [
        "Run read-only when generating against the repo.",
        "Return a unified diff plus assumptions.",
    ]
    assert resolution.payload == "\n".join(resolution.protocol) + "\n\n" + context
    assert resolution.write_capable is False
    assert resolution.fallback is None
    assert resolution.halt is None


@pytest.mark.usefixtures("engine_available")
def test_engine_advisory_returns_default_variant(registry: Any) -> None:
    resolution = R.resolve(
        {"engine": "codex", "role_kind": "advisory-reviewer"},
        mode="advisory",
        registry=registry,
    )

    assert resolution.engine_id == "codex"
    assert resolution.variant == "gpt-5.5-xhigh"
    assert resolution.payload == "\n".join(resolution.protocol)
    assert resolution.fallback is None
    assert resolution.halt is None


@pytest.mark.usefixtures("engine_available")
def test_payload_preserves_protocol_line_order_byte_for_byte(registry: Any) -> None:
    resolution = R.resolve(
        {
            "capability": "code-generation",
            "role_kind": "worker",
            "task_context": {"context": "Caller context."},
        },
        mode="dispatch",
        registry=registry,
    )

    expected_protocol_bytes = "\n".join(resolution.protocol).encode("utf-8")
    payload_prefix = resolution.payload.encode("utf-8").split(b"\n\n", 1)[0]
    assert payload_prefix == expected_protocol_bytes
    assert resolution.payload.splitlines()[: len(resolution.protocol)] == resolution.protocol


def test_long_form_writing_worker_no_fit_falls_back_not_halts(registry: Any) -> None:
    resolution = R.resolve(
        {
            "capability": "long-form-writing",
            "role_kind": "worker",
            "task_context": {"context": "Draft the decision entry."},
        },
        mode="dispatch",
        registry=registry,
    )

    assert resolution.engine_id == "claude"
    assert resolution.fallback is not None
    assert "long-form-writing" in resolution.fallback
    assert "WEAK rating" in resolution.fallback
    assert resolution.halt is None


def test_panel_with_unavailable_member_halts_not_fallbacks(
    registry: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_preflight(engine_id: str, **_kwargs: object) -> dict[str, bool | str]:
        if engine_id == "agy":
            return {"available": False, "reason": "agy is not installed"}
        return {"available": True, "reason": f"{engine_id} available"}

    monkeypatch.setattr(R, "preflight", fake_preflight)

    resolution = R.resolve(
        {
            "capability": "adversarial-review",
            "role_kind": "panel",
            "task_context": {
                "context": "Review the readiness packet.",
                "role": "cross-family-review-panel",
            },
        },
        mode="advisory",
        registry=registry,
    )

    assert resolution.fallback is None
    assert resolution.halt is not None
    assert "cross-family-review-panel" in resolution.halt
    assert "agy/gemini-3.1-pro-high" in resolution.halt


def test_named_unavailable_engine_halts_even_for_worker(
    registry: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        R,
        "preflight",
        lambda _engine_id, **_kwargs: {"available": False, "reason": "codex is not installed"},
    )

    resolution = R.resolve(
        {"engine": "codex", "role_kind": "worker"},
        mode="dispatch",
        registry=registry,
    )

    assert resolution.fallback is None
    assert resolution.halt is not None
    assert "codex/gpt-5.5-xhigh" in resolution.halt
    assert "not installed" in resolution.halt


def test_task_token_estimate_exceeding_context_window_halts(registry: Any) -> None:
    resolution = R.resolve(
        {
            "engine": "codex",
            "role_kind": "worker",
            "task_context": {
                "context": "Small text; token estimate comes from the caller.",
                "token_estimate": 400001,
            },
        },
        mode="dispatch",
        registry=registry,
    )

    assert resolution.fallback is None
    assert resolution.halt is not None
    assert "token_estimate 400001" in resolution.halt
    assert "context_window 400000" in resolution.halt
    assert "truncate" in resolution.halt


def test_preflight_available_when_cli_and_config_present() -> None:
    result = R.preflight(
        "codex",
        which=lambda cli: f"/usr/bin/{cli}",
        config_exists=lambda engine_id: engine_id == "codex",
    )

    assert result["available"] is True
    assert "no live API call" in str(result["reason"])


def test_preflight_reports_not_configured_when_config_absent() -> None:
    result = R.preflight(
        "codex",
        which=lambda cli: f"/usr/bin/{cli}",
        config_exists=lambda _engine_id: False,
    )

    assert result["available"] is False
    assert "not configured" in str(result["reason"])


def test_preflight_reports_not_installed_when_cli_absent() -> None:
    result = R.preflight(
        "agy",
        which=lambda _cli: None,
        config_exists=lambda _engine_id: True,
    )

    assert result["available"] is False
    assert "not installed" in str(result["reason"])


@pytest.mark.usefixtures("engine_available")
def test_resolve_role_expands_to_per_member_advisory_resolutions(registry: Any) -> None:
    resolutions = R.resolve_role("cross-family-review-panel", registry=registry)
    members = registry.by_role("cross-family-review-panel").members

    assert len(resolutions) == len(members)
    assert [f"{r.engine_id}/{r.variant}" for r in resolutions] == members
    # each member carries its OWN protocol (different engine families, R16/F3)
    assert all(r.protocol for r in resolutions)
    assert R.panel_halt(resolutions) is None


def test_resolve_role_halts_panel_when_member_unavailable(
    registry: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_preflight(engine_id: str, **_kwargs: object) -> dict[str, bool | str]:
        if engine_id == "agy":
            return {"available": False, "reason": "agy is not installed"}
        return {"available": True, "reason": f"{engine_id} available"}

    monkeypatch.setattr(R, "preflight", fake_preflight)

    resolutions = R.resolve_role("cross-family-review-panel", registry=registry)
    halt = R.panel_halt(resolutions)

    # R17: an unavailable panel member halts the panel; no Claude substitution.
    assert halt is not None
    assert "agy" in halt


# ---- U4: transport-aware preflight (KTD4) + RunMemo (KTD5, R5/R11) -----------


def _http_engine_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "engine_id": "ollama-cloud",
        "variant": "gpt-oss-120b",
        "substrate": "external",
        "default_for_engine": True,
        "transport": "http",
        "invocation": {
            "via": "engine-bridge-http",
            "recipe": "POST https://ollama.com/v1/chat/completions",
            "write_capable": False,
            "base_url": "https://ollama.com/v1",
            "model": "gpt-oss:120b",
            "effort": "default",
            "auth": {"mode": "bearer", "key_env": "OLLAMA_API_KEY"},
        },
        "context_window": 128000,
        "cost_speed_rank": 5,
        "model_identity": "gpt-oss-120b",
        "last_validated": "2026-07-06",
        "receipt_emitter": "http-bridge",
        "capability_profile": {
            "code-generation": {"rating": "MODERATE", "note": "seed rating"},
        },
        "prompting_protocol": ["Resolve the bearer token at request-build time only."],
        "sources": [
            {
                "claim": "OpenAI-compatible base URL",
                "url": "https://docs.ollama.com/api/openai-compatibility",
                "date": "2026-07-06",
                "tag": "OFFICIAL",
                "corroboration": "STRONG",
            }
        ],
    }
    row.update(overrides)
    return row


def _http_entry(**overrides: Any) -> Any:
    return REG.EngineEntry.from_dict(_http_engine_row(**overrides), registry_order=0)


def test_preflight_http_transport_never_touches_which_or_config_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = _http_entry()
    monkeypatch.setenv("OLLAMA_API_KEY", "sk-fake")

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("http preflight must not call CLI which/config_exists")

    result = R.preflight("ollama-cloud", which=_boom, config_exists=_boom, entry=entry)

    assert result["available"] is True
    assert "no live API call" in str(result["reason"])


def test_preflight_http_transport_unavailable_when_bearer_key_env_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = _http_entry()
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)

    result = R.preflight("ollama-cloud", entry=entry)

    assert result["available"] is False
    assert "OLLAMA_API_KEY" in str(result["reason"])


def test_preflight_http_transport_available_when_auth_not_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = _http_entry(
        invocation={
            "via": "engine-bridge-http",
            "recipe": "POST https://ollama.com/v1/chat/completions",
            "write_capable": False,
            "base_url": "https://ollama.com/v1",
            "model": "gpt-oss:120b",
            "effort": "default",
            "auth": {"mode": "none"},
        }
    )

    result = R.preflight("ollama-cloud", entry=entry)

    assert result["available"] is True
    assert "no live API call" in str(result["reason"])


def test_preflight_cli_transport_unaffected_by_entry_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # KTD4/R11: preflight with no entry supplied (or a cli-transport entry) keeps
    # the pre-U4 shutil.which + config-file behavior byte-identical.
    result = R.preflight(
        "codex",
        which=lambda cli: f"/usr/bin/{cli}",
        config_exists=lambda engine_id: engine_id == "codex",
    )

    assert result["available"] is True
    assert "CLI and config present" in str(result["reason"])


def test_run_memo_caches_preflight_result_per_engine_id() -> None:
    memo = R.RunMemo()
    calls: list[str] = []

    def fake_which(cli: str) -> str:
        calls.append(cli)
        return f"/usr/bin/{cli}"

    for _ in range(5):
        result = R.preflight(
            "codex",
            which=fake_which,
            config_exists=lambda _engine_id: True,
            memo=memo,
        )
        assert result["available"] is True

    assert len(calls) == 1


def test_run_memo_none_probes_every_call_byte_identical_to_no_memo() -> None:
    calls: list[str] = []

    def fake_which(cli: str) -> str:
        calls.append(cli)
        return f"/usr/bin/{cli}"

    for _ in range(3):
        R.preflight(
            "codex",
            which=fake_which,
            config_exists=lambda _engine_id: True,
            memo=None,
        )

    assert len(calls) == 3


@pytest.mark.usefixtures("engine_available")
def test_resolve_with_memo_returns_same_resolution_as_without(registry: Any) -> None:
    request = {
        "capability": "code-generation",
        "role_kind": "generator",
        "task_context": {"context": "Implement the bounded change."},
    }

    without_memo = R.resolve(request, mode="dispatch", registry=registry)
    with_memo = R.resolve(request, mode="dispatch", registry=registry, memo=R.RunMemo())

    assert without_memo == with_memo
