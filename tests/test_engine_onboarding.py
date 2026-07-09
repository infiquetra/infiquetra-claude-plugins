"""Tests for safe external-engine provider onboarding (#455)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
REGISTRY_PATH = ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml"
SCRIPT = SCRIPT_DIR / "engine_onboarding.py"
WRAPPER = ROOT / "tools" / "add-engine.sh"


def _load() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("engine_onboarding", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ONBOARDING = _load()
CONFORMANCE = importlib.import_module("engine_registry_conformance")


def _spec() -> dict[str, Any]:
    return {
        "transport": "http",
        "engine_id": "fixture-http",
        "variant": "fixture-chat",
        "base_url": "https://api.example.com/v1",
        "model": "fixture-chat",
        "auth_key_env": "FIXTURE_API_KEY",
        "context_window": 32768,
        "cost_speed_rank": 99,
        "cost_class": "metered",
        "cost_per_token": {"input_usd": 0.000001, "output_usd": 0.000002},
        "budget_ceiling_usd": 5.0,
        "latency_class": "standard",
        "model_identity": "fixture-chat",
        "last_validated": "2026-07-09",
        "capability_profile": {
            "code-generation": {
                "rating": "MODERATE",
                "note": "fixture provider onboarding proof",
            }
        },
        "prompting_protocol": ["Return advisory evidence only."],
        "sources": [
            {
                "claim": "OpenAI-compatible endpoint and model id",
                "url": "https://api.example.com/docs",
                "date": "2026-07-09",
                "tag": "OFFICIAL",
                "corroboration": "STRONG",
            }
        ],
    }


def _write_spec(tmp_path: Path, data: dict[str, Any] | None = None) -> Path:
    path = tmp_path / "provider.json"
    path.write_text(json.dumps(_spec() if data is None else data), encoding="utf-8")
    return path


def _copy_registry(tmp_path: Path) -> Path:
    path = tmp_path / "engine-registry.yaml"
    path.write_text(REGISTRY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def test_dry_run_builds_probationary_generic_http_row_without_writing(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path)
    registry = _copy_registry(tmp_path)
    before = registry.read_text(encoding="utf-8")

    result = ONBOARDING.onboard(spec, registry)

    assert not result.applied
    assert result.engine_key == "fixture-http/fixture-chat"
    assert result.row["trust_tier"] == "probation"
    assert result.row["invocation"]["via"] == "engine-bridge-http"
    assert result.row["invocation"]["write_capable"] is False
    assert result.row["receipt_emitter"] == "http-bridge"
    assert registry.read_text(encoding="utf-8") == before


def test_apply_inserts_only_row_before_roles_and_registry_loads(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path)
    registry = _copy_registry(tmp_path)
    before = registry.read_text(encoding="utf-8")

    result = ONBOARDING.onboard(spec, registry, apply=True)

    after = registry.read_text(encoding="utf-8")
    assert result.applied
    assert after.replace(result.fragment + "\n", "", 1) == before
    assert after.index(result.fragment) < after.index("roles:")
    loaded = ONBOARDING.Registry.load(registry)
    entry = loaded.by_key("fixture-http/fixture-chat")
    assert entry.trust_tier == "probation"
    assert entry.default_for_engine is True


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda data: data.pop("capability_profile"), "capability_profile"),
        (lambda data: data.__setitem__("capability_profile", {}), "capability_profile"),
        (lambda data: data.__setitem__("sources", []), "sources"),
        (lambda data: data.pop("auth_key_env"), "auth_key_env"),
        (lambda data: data.pop("model"), "model"),
        (lambda data: data["cost_per_token"].pop("output_usd"), "cost_per_token"),
        (lambda data: data.__setitem__("base_url", "http://user:pass@example.com?q=1"), "base_url"),
    ],
)
def test_invalid_spec_names_field_and_writes_nothing(
    tmp_path: Path,
    mutate: Any,
    message: str,
) -> None:
    data = _spec()
    mutate(data)
    spec = _write_spec(tmp_path, data)
    registry = _copy_registry(tmp_path)
    before = registry.read_bytes()

    with pytest.raises(ONBOARDING.OnboardingError, match=message):
        ONBOARDING.onboard(spec, registry, apply=True)

    assert registry.read_bytes() == before


def test_cli_transport_is_rejected_without_a_real_wrapper(tmp_path: Path) -> None:
    data = _spec()
    data["transport"] = "cli"
    spec = _write_spec(tmp_path, data)
    registry = _copy_registry(tmp_path)

    with pytest.raises(ONBOARDING.OnboardingError, match="CLI providers need a real wrapper"):
        ONBOARDING.onboard(spec, registry)


def test_embedding_capability_is_rejected_by_chat_completions_scaffolder(tmp_path: Path) -> None:
    data = _spec()
    data["capability_profile"] = {
        "embedding": {"rating": "STRONG", "note": "not a chat capability"}
    }

    with pytest.raises(ONBOARDING.OnboardingError, match="chat/completions"):
        ONBOARDING.onboard(_write_spec(tmp_path, data), _copy_registry(tmp_path))


def test_second_apply_rejects_duplicate_and_preserves_first_result(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path)
    registry = _copy_registry(tmp_path)
    ONBOARDING.onboard(spec, registry, apply=True)
    after_first = registry.read_bytes()

    with pytest.raises(ONBOARDING.OnboardingError, match="already contains"):
        ONBOARDING.onboard(spec, registry, apply=True)

    assert registry.read_bytes() == after_first


def test_concurrent_registry_edit_aborts_without_overwriting_it(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path)
    registry = _copy_registry(tmp_path)

    def concurrent_edit() -> None:
        registry.write_text(
            registry.read_text(encoding="utf-8") + "\n# concurrent operator edit\n",
            encoding="utf-8",
        )

    with pytest.raises(ONBOARDING.OnboardingError, match="changed during onboarding"):
        ONBOARDING.onboard(spec, registry, apply=True, before_replace=concurrent_edit)

    assert registry.read_text(encoding="utf-8").endswith("# concurrent operator edit\n")
    assert "fixture-http" not in registry.read_text(encoding="utf-8")


def test_conformance_failure_prevents_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _write_spec(tmp_path)
    registry = _copy_registry(tmp_path)
    before = registry.read_bytes()
    issue = CONFORMANCE.ConformanceIssue(
        "fixture-http/fixture-chat",
        "dispatch-invocation",
        "dead wired",
    )
    monkeypatch.setattr(
        ONBOARDING,
        "check_registry",
        lambda _registry: CONFORMANCE.ConformanceReport(1, (issue,)),
    )

    with pytest.raises(ONBOARDING.OnboardingError, match="dead wired"):
        ONBOARDING.onboard(spec, registry, apply=True)

    assert registry.read_bytes() == before


def test_shell_wrapper_forwards_to_python_dry_run(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path)
    registry = _copy_registry(tmp_path)

    completed = subprocess.run(
        [str(WRAPPER), "--spec", str(spec), "--registry", str(registry)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "trust_tier: probation" in completed.stdout
    assert "validated probationary engine row fixture-http/fixture-chat" in completed.stdout
