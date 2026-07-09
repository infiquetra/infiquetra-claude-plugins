"""Tests for the Saga engine-registry lint gate."""

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
LINT_SCRIPT = SCRIPT_DIR / "check_engine_registry.py"


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
LINT = _load("check_engine_registry", LINT_SCRIPT)


def _registry_dict(*, last_validated: str = "2026-07-06") -> dict[str, Any]:
    return {
        "capabilities": list(REG.CAPABILITIES),
        "engines": [
            {
                "engine_id": "codex",
                "variant": "gpt-5.5-high",
                "substrate": "external",
                "egress_policy": "networked",
                "trust_tier": "advisory",
                "default_for_engine": True,
                "invocation": {
                    "via": "codex:delegate",
                    "recipe": "codex exec -s read-only -c model_reasoning_effort=high",
                    "write_capable": False,
                    "cli": "codex",
                    "auth": {"mode": "files", "paths": ["~/.codex/auth.json"]},
                },
                "context_window": 400000,
                "cost_speed_rank": 2,
                "cost_per_token": {"input_usd": 0.000005, "output_usd": 0.000015},
                "cost_class": "metered",
                "budget_ceiling_usd": 25.0,
                "latency_class": "standard",
                "model_identity": "gpt-5.5",
                "last_validated": last_validated,
                "receipt_emitter": "codex-bridge",
                "capability_profile": {
                    "code-generation": {"rating": "STRONG", "note": "bounded implementation"}
                },
                "prompting_protocol": ["Run read-only.", "Return a unified diff."],
                "sources": [
                    {
                        "claim": "registry fixture",
                        "url": "https://example.invalid/registry",
                        "date": last_validated,
                        "tag": "LOCAL",
                        "corroboration": "STRONG",
                    }
                ],
            }
        ],
        "roles": {
            "cross-family-review-panel": {
                "members": ["codex/gpt-5.5-high"],
                "verdict": "advisory",
                "verifier": "claude",
            }
        },
    }


def _write_yaml(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_lint_registry_accepts_current_rows(tmp_path: Path) -> None:
    registry_path = _write_yaml(tmp_path / "engine-registry.yaml", _registry_dict())
    releases_path = _write_yaml(tmp_path / "model-releases.yaml", {"gpt-5.5": "2026-07-06"})

    registry = LINT.lint_registry(registry_path, releases_path)

    assert len(registry.engines) == 1


def test_lint_registry_rejects_stale_rows_with_names(tmp_path: Path) -> None:
    registry_path = _write_yaml(
        tmp_path / "engine-registry.yaml",
        _registry_dict(last_validated="2026-07-05"),
    )
    releases_path = _write_yaml(
        tmp_path / "model-releases.yaml",
        {"model_releases": {"gpt-5.5": "2026-07-06"}},
    )

    with pytest.raises(LINT.EngineRegistryLintError, match="codex/gpt-5.5-high"):
        LINT.lint_registry(registry_path, releases_path)


def test_lint_registry_rejects_malformed_rows(tmp_path: Path) -> None:
    data = _registry_dict()
    del data["engines"][0]["cost_per_token"]
    registry_path = _write_yaml(tmp_path / "engine-registry.yaml", data)
    releases_path = _write_yaml(tmp_path / "model-releases.yaml", {"gpt-5.5": "2026-07-06"})

    with pytest.raises(REG.RegistryError, match="cost_per_token"):
        LINT.lint_registry(registry_path, releases_path)
