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
                    "via": "codex:delegate",
                    "recipe": "codex exec -s read-only -c model_reasoning_effort=xhigh",
                    "write_capable": False,
                },
                "context_window": 400000,
                "cost_speed_rank": 2,
                "cost_per_token": {"input_usd": 0.000005, "output_usd": 0.000015},
                "latency_class": "standard",
                "model_identity": "gpt-5.5",
                "last_validated": "2026-06-27",
                "receipt_emitter": "codex-bridge",
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
                "cost_per_token": {"input_usd": 0.0000035, "output_usd": 0.0000105},
                "latency_class": "standard",
                "model_identity": "gemini-3.1-pro",
                "last_validated": "2026-06-20",
                "receipt_emitter": "agy-delegate",
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
        assert entry.receipt_emitter
    # the cross-family review panel (R16) is present and advisory (R13/R15).
    panel = registry.by_role("cross-family-review-panel")
    assert panel.verdict == "advisory"
    assert panel.verifier == "claude"


# ---- U3: transport / http-conditional invocation / receipt_emitter (R9/R11, KTD2/KTD3/KTD9) -----


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
        "cost_per_token": {"input_usd": 0.0, "output_usd": 0.0},
        "latency_class": "standard",
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


def _registry_with_extra_engine(extra_engine: dict[str, Any]) -> dict[str, Any]:
    data = _valid_registry_dict()
    data["engines"].append(extra_engine)
    return data


def test_transport_defaults_to_cli_for_existing_shape_rows(tmp_path: Path) -> None:
    registry = M.Registry.load(_write_registry(tmp_path, _valid_registry_dict()))
    for entry in registry.engines:
        assert entry.transport == "cli"
        assert entry.auth == {}


def test_transport_http_row_parses_with_required_invocation_fields(tmp_path: Path) -> None:
    data = _registry_with_extra_engine(_http_engine_row())
    registry = M.Registry.load(_write_registry(tmp_path, data))

    entry = registry.by_engine("ollama-cloud")
    assert entry.transport == "http"
    assert entry.invocation["base_url"] == "https://ollama.com/v1"
    assert entry.invocation["auth"]["key_env"] == "OLLAMA_API_KEY"
    assert entry.auth == {"mode": "bearer", "key_env": "OLLAMA_API_KEY"}


@pytest.mark.parametrize(
    "auth",
    [
        {"mode": "files", "paths": ["~/.codex/auth.json", "~/.codex/config.toml"]},
        {"mode": "env", "key_env": "CODEX_API_KEY"},
        {"mode": "bearer", "key_env": "CODEX_API_KEY"},
        {"mode": "secret-ref", "ref": "op://infiquetra/codex/api-key"},
    ],
)
def test_auth_modes_parse_to_engine_entry_auth(tmp_path: Path, auth: dict[str, Any]) -> None:
    data = _valid_registry_dict()
    data["engines"][0]["invocation"]["cli"] = "codex"
    data["engines"][0]["invocation"]["auth"] = auth

    registry = M.Registry.load(_write_registry(tmp_path, data))

    assert registry.by_engine("codex").auth == auth


@pytest.mark.parametrize(
    ("auth", "match"),
    [
        ({"mode": "carrier"}, "mode"),
        ({"mode": "files", "paths": []}, "paths"),
        ({"mode": "files", "paths": [""]}, "paths"),
        ({"mode": "env"}, "key_env"),
        ({"mode": "bearer"}, "key_env"),
        ({"mode": "secret-ref"}, "ref"),
    ],
)
def test_malformed_auth_modes_error(
    tmp_path: Path,
    auth: dict[str, Any],
    match: str,
) -> None:
    data = _valid_registry_dict()
    data["engines"][0]["invocation"]["cli"] = "codex"
    data["engines"][0]["invocation"]["auth"] = auth

    with pytest.raises(M.RegistryError, match=match):
        M.Registry.load(_write_registry(tmp_path, data))


def test_cli_row_with_auth_requires_cli_field(tmp_path: Path) -> None:
    data = _valid_registry_dict()
    data["engines"][0]["invocation"]["auth"] = {"mode": "env", "key_env": "CODEX_API_KEY"}

    with pytest.raises(M.RegistryError, match="cli"):
        M.Registry.load(_write_registry(tmp_path, data))


@pytest.mark.parametrize("missing_field", ["base_url", "model", "effort", "auth"])
def test_http_row_missing_required_invocation_field_errors(
    tmp_path: Path, missing_field: str
) -> None:
    row = _http_engine_row()
    del row["invocation"][missing_field]
    data = _registry_with_extra_engine(row)

    with pytest.raises(M.RegistryError, match=missing_field):
        M.Registry.load(_write_registry(tmp_path, data))


def test_http_row_bearer_auth_missing_key_env_errors(tmp_path: Path) -> None:
    row = _http_engine_row()
    del row["invocation"]["auth"]["key_env"]
    data = _registry_with_extra_engine(row)

    with pytest.raises(M.RegistryError, match="key_env"):
        M.Registry.load(_write_registry(tmp_path, data))


def test_http_row_rejects_auth_modes_the_bridge_cannot_consume(tmp_path: Path) -> None:
    row = _http_engine_row()
    row["invocation"]["auth"] = {"mode": "env", "key_env": "OLLAMA_API_KEY"}
    data = _registry_with_extra_engine(row)

    with pytest.raises(M.RegistryError, match="bearer"):
        M.Registry.load(_write_registry(tmp_path, data))


def test_unknown_transport_value_rejected(tmp_path: Path) -> None:
    row = _http_engine_row(transport="carrier-pigeon")
    data = _registry_with_extra_engine(row)

    with pytest.raises(M.RegistryError, match="transport"):
        M.Registry.load(_write_registry(tmp_path, data))


def test_missing_receipt_emitter_errors(tmp_path: Path) -> None:
    data = _valid_registry_dict()
    del data["engines"][0]["receipt_emitter"]

    with pytest.raises(M.RegistryError, match="receipt_emitter"):
        M.Registry.load(_write_registry(tmp_path, data))


def test_by_capability_routing_stability_regression_shipped_registry_winners_unchanged() -> None:
    """U3/KTD3: adding the http rows must not reroute any existing capability winner.

    Bakes today's by_capability winners as literals (engine/variant keys) against the
    shipped registry -- if the new ollama-cloud/deepseek rows ever rate a capability
    at or above the current winner, this regression reds.
    """
    registry = M.Registry.load(ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml")

    expected_winners = {
        "code-generation": "codex/gpt-5.5-xhigh",
        "adversarial-review": "codex/gpt-5.5-high",
        "second-opinion": "agy/gemini-3.1-pro-high",
        "debug": "codex/gpt-5.5-xhigh",
        "refactor": "codex/gpt-5.5-high",
        "scaffold": "agy/gemini-3.5-flash-high",
        "long-form-writing": "codex/gpt-5.5-high",
    }
    for capability, expected_key in expected_winners.items():
        assert registry.by_capability(capability).key == expected_key, capability


def test_shipped_registry_resolves_new_schema_currency_capabilities() -> None:
    registry = M.Registry.load(ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml")

    assert registry.by_capability("bulk-classification").key == "ollama-cloud/gpt-oss-120b"
    assert registry.by_capability("structured-extraction").key == "ollama-cloud/gpt-oss-120b"
    assert registry.by_capability("embedding").key == "ollama-cloud/nomic-embed-text"


def test_shipped_registry_materializes_codex_family_defaults() -> None:
    registry = M.Registry.load(ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml")
    codex_rows = [entry for entry in registry.engines if entry.model_identity == "gpt-5.5"]

    assert len(codex_rows) == 2
    for entry in codex_rows:
        assert entry.capability_profile["adversarial-review"]["rating"] == "STRONG"
        assert entry.capability_profile["refactor"]["rating"] == "MODERATE"


def test_family_defaults_merge_before_validation(tmp_path: Path) -> None:
    data = _valid_registry_dict()
    data["model_families"] = {
        "gpt-5.5": {
            "capability_profile": {
                "debug": {"rating": "MODERATE", "note": "family default"},
                "refactor": {"rating": "WEAK", "note": "family default"},
            }
        }
    }
    del data["engines"][0]["capability_profile"]["debug"]
    data["engines"][0]["capability_profile"]["refactor"] = {
        "rating": "STRONG",
        "note": "row override",
    }

    entry = M.Registry.load(_write_registry(tmp_path, data)).by_engine("codex")

    assert entry.capability_profile["debug"]["note"] == "family default"
    assert entry.capability_profile["refactor"]["rating"] == "STRONG"
    assert entry.capability_profile["refactor"]["note"] == "row override"


def test_cost_and_latency_metadata_are_required_and_validated(tmp_path: Path) -> None:
    data = _valid_registry_dict()

    registry = M.Registry.load(_write_registry(tmp_path, data))
    assert registry.by_engine("codex").cost_per_token == {
        "input_usd": 0.000005,
        "output_usd": 0.000015,
    }
    assert registry.by_engine("codex").latency_class == "standard"

    missing = deepcopy(data)
    del missing["engines"][0]["cost_per_token"]
    with pytest.raises(M.RegistryError, match="cost_per_token"):
        M.Registry.load(_write_registry(tmp_path, missing))

    negative = deepcopy(data)
    negative["engines"][0]["cost_per_token"]["input_usd"] = -1
    with pytest.raises(M.RegistryError, match="non-negative"):
        M.Registry.load(_write_registry(tmp_path, negative))

    bad_latency = deepcopy(data)
    bad_latency["engines"][0]["latency_class"] = "instant"
    with pytest.raises(M.RegistryError, match="latency_class"):
        M.Registry.load(_write_registry(tmp_path, bad_latency))


def test_shipped_registry_http_rows_parse_and_are_advisory_only(tmp_path: Path) -> None:
    """The new ollama-cloud/deepseek rows load as transport=http with receipt_emitter set,
    conservative legacy seed ratings, and cost_speed_rank in the 5-6 range (KTD3)."""
    registry = M.Registry.load(ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml")

    for engine_id in ("ollama-cloud", "deepseek"):
        entry = registry.by_engine(engine_id)
        assert entry.transport == "http"
        assert entry.receipt_emitter == "http-bridge"
        assert entry.cost_speed_rank in (5, 6)
        legacy_claims = {
            capability: claim
            for capability, claim in entry.capability_profile.items()
            if capability not in {"bulk-classification", "structured-extraction", "embedding"}
        }
        for claim in legacy_claims.values():
            assert claim["rating"] in ("WEAK", "MODERATE")


def test_shipped_registry_rows_expose_auth_and_cli_rows_have_cli() -> None:
    registry = M.Registry.load(ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml")

    for entry in registry.engines:
        assert entry.auth
        if entry.transport == "cli":
            assert entry.invocation["cli"] in {"codex", "agy"}
            assert entry.auth["mode"] == "files"
            assert entry.auth["paths"]
