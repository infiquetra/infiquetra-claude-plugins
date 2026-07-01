"""Oracle tests for the Saga external-engine registry loader (U1)."""

from __future__ import annotations

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "plugins" / "saga" / "scripts" / "engine_registry.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("engine_registry", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass field-type resolution can look the module up.
    sys.modules["engine_registry"] = module
    spec.loader.exec_module(module)
    return module


M = _load()


def _valid_registry_dict() -> dict[str, Any]:
    return {
        "capabilities": list(M.CAPABILITIES),
        "engines": [
            {
                "engine_id": "codex",
                "variant": "gpt-5.5-xhigh",
                "substrate": "external",
                "default_for_engine": True,
                "invocation": {
                    "via": "codex:codex-rescue",
                    "recipe": "codex -s read-only --effort xhigh",
                    "write_capable": False,
                },
                "context_window": 400000,
                "cost_speed_rank": 2,
                "model_identity": "gpt-5.5",
                "last_validated": "2026-06-27",
                "capability_profile": {
                    "code-generation": {
                        "rating": "STRONG",
                        "note": "structured-output fidelity, multi-file refactor",
                    },
                    "debug": {
                        "rating": "STRONG",
                        "note": "tool-orchestrated debugging",
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
                "capability_profile": {
                    "code-generation": {
                        "rating": "STRONG",
                        "note": "same rating as codex, cheaper/faster tie-break wins",
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


def test_happy_path_lookups_by_capability_engine_and_role(tmp_path: Path) -> None:
    registry = M.Registry.load(_write_registry(tmp_path, _valid_registry_dict()))

    assert registry.by_capability("debug").key == "codex/gpt-5.5-xhigh"
    assert registry.by_capability("code-generation").key == "agy/gemini-3.1-pro-high"
    assert registry.by_engine("codex").key == "codex/gpt-5.5-xhigh"
    assert registry.by_role("cross-family-review-panel").members == [
        "codex/gpt-5.5-xhigh",
        "agy/gemini-3.1-pro-high",
    ]


def test_ambiguous_engine_default_errors(tmp_path: Path) -> None:
    data = _valid_registry_dict()
    data["engines"][0]["default_for_engine"] = False
    second_codex_variant = deepcopy(data["engines"][0])
    second_codex_variant["variant"] = "gpt-5.5-medium"
    second_codex_variant["cost_speed_rank"] = 3
    data["engines"].append(second_codex_variant)

    with pytest.raises(M.RegistryError, match="ambiguous default"):
        M.Registry.load(_write_registry(tmp_path, data))


def test_stale_true_when_last_validated_predates_revision_and_false_otherwise(
    tmp_path: Path,
) -> None:
    registry = M.Registry.load(_write_registry(tmp_path, _valid_registry_dict()))
    entry = registry.by_engine("codex")

    assert M.Registry.stale(entry, {"gpt-5.5": "2026-06-28"})
    assert not M.Registry.stale(entry, {"gpt-5.5": "2026-06-27"})
    assert not M.Registry.stale(entry, {"gemini-3.1-pro": "2026-07-01"})


def test_unknown_capability_key_errors(tmp_path: Path) -> None:
    data = _valid_registry_dict()
    data["engines"][0]["capability_profile"]["telepathy"] = {
        "rating": "STRONG",
        "note": "not in the closed vocabulary",
    }

    with pytest.raises(M.RegistryError, match="telepathy"):
        M.Registry.load(_write_registry(tmp_path, data))


def test_missing_sources_errors(tmp_path: Path) -> None:
    data = _valid_registry_dict()
    del data["engines"][0]["sources"]

    with pytest.raises(M.RegistryError, match="sources"):
        M.Registry.load(_write_registry(tmp_path, data))


@pytest.mark.parametrize("value", [None, "fast"])
def test_missing_or_non_integer_cost_speed_rank_errors(tmp_path: Path, value: object) -> None:
    data = _valid_registry_dict()
    if value is None:
        del data["engines"][0]["cost_speed_rank"]
    else:
        data["engines"][0]["cost_speed_rank"] = value

    with pytest.raises(M.RegistryError, match="cost_speed_rank"):
        M.Registry.load(_write_registry(tmp_path, data))


def test_role_member_referencing_non_existent_variant_errors(tmp_path: Path) -> None:
    data = _valid_registry_dict()
    data["roles"]["cross-family-review-panel"]["members"] = ["codex/missing-variant"]

    with pytest.raises(M.RegistryError, match="non-existent variant"):
        M.Registry.load(_write_registry(tmp_path, data))


def test_shipped_seed_registry_loads_and_resolves() -> None:
    """U7: the checked-in seed registry validates and routes sanely (R3/R21)."""
    registry = M.Registry.load(ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml")

    assert len(registry.engines) >= 3
    # KTD9: a 3-way STRONG tie on adversarial-review resolves to the cheapest cost_speed_rank.
    assert registry.by_capability("adversarial-review").cost_speed_rank == 2
    # every seeded row carries source attribution + an orderable cost_speed_rank (seed requirement).
    for entry in registry.engines:
        assert entry.sources
        assert isinstance(entry.cost_speed_rank, int)
    # the cross-family review panel (R16) is present and advisory (R13/R15).
    panel = registry.by_role("cross-family-review-panel")
    assert panel.verdict == "advisory"
    assert panel.verifier == "claude"
