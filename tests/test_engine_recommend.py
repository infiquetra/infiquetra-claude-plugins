"""Tests for the Saga advisory engine recommendation primitive (#391)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
REGISTRY_SCRIPT = SCRIPT_DIR / "engine_registry.py"
RECOMMEND_SCRIPT = SCRIPT_DIR / "engine_recommend.py"
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
REC = _load("engine_recommend", RECOMMEND_SCRIPT)


def _row(
    engine_id: str,
    *,
    variant: str = "default",
    rating: str = "MODERATE",
    input_usd: float = 0.000003,
    output_usd: float = 0.000006,
    cost_speed_rank: int = 3,
    cost_class: str = "metered",
    egress_policy: str = "networked",
    context_window: int = 100_000,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "engine_id": engine_id,
        "variant": variant,
        "substrate": "external",
        "egress_policy": egress_policy,
        "default_for_engine": True,
        "invocation": {
            "via": f"{engine_id}:delegate",
            "recipe": f"{engine_id} delegate --mode no-write",
            "write_capable": False,
        },
        "context_window": context_window,
        "cost_speed_rank": cost_speed_rank,
        "cost_per_token": {"input_usd": input_usd, "output_usd": output_usd},
        "cost_class": cost_class,
        "latency_class": "standard",
        "model_identity": f"{engine_id}-{variant}",
        "last_validated": "2026-07-09",
        "receipt_emitter": f"{engine_id}-bridge",
        "capability_profile": {
            "code-generation": {"rating": rating, "note": "fixture rating"},
        },
        "prompting_protocol": [f"Use {engine_id} for advisory output only."],
        "sources": [
            {
                "claim": "fixture source",
                "url": f"https://example.invalid/{engine_id}",
                "date": "2026-07-09",
                "tag": "LOCAL",
                "corroboration": "MODERATE",
            }
        ],
    }
    if cost_class == "metered":
        row["budget_ceiling_usd"] = 25.0
    return row


def _registry(tmp_path: Path, rows: list[dict[str, Any]]) -> Any:
    data = {
        "capabilities": list(REG.CAPABILITIES),
        "engines": rows,
        "roles": {},
    }
    path = tmp_path / "engine-registry.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return REG.Registry.load(path)


def _keys(result: Any) -> list[str]:
    return [candidate.key for candidate in result.candidates]


def test_recommendation_returns_metadata_and_filters_weak_by_default(tmp_path: Path) -> None:
    registry = _registry(
        tmp_path,
        [
            _row("metered", rating="STRONG", input_usd=0.000005, output_usd=0.000015),
            _row(
                "free",
                input_usd=0.0,
                output_usd=0.0,
                cost_speed_rank=5,
                cost_class="free",
            ),
            _row("weak-free", rating="WEAK", input_usd=0.0, output_usd=0.0, cost_class="free"),
        ],
    )

    result = REC.recommend({"capability": "code-generation"}, registry=registry)

    assert result.status == "ok"
    assert result.recommended is not None
    assert result.recommended.key == "free/default"
    assert "weak-free/default" not in _keys(result)
    assert result.recommended.cost_per_token == {"input_usd": 0.0, "output_usd": 0.0}
    assert result.recommended.unit_price_usd == 0.0
    assert result.recommended.egress_policy == "networked"
    assert result.recommended.prompting_protocol == ["Use free for advisory output only."]
    assert result.next_rung() is not None


def test_cheapest_viable_orders_by_unit_price_then_speed_then_registry_order(
    tmp_path: Path,
) -> None:
    registry = _registry(
        tmp_path,
        [
            _row("slow", input_usd=0.000004, output_usd=0.000006, cost_speed_rank=4),
            _row("fast", input_usd=0.000003, output_usd=0.000007, cost_speed_rank=2),
            _row("fast-later", input_usd=0.000003, output_usd=0.000007, cost_speed_rank=2),
        ],
    )

    result = REC.recommend({"capability": "code-generation"}, registry=registry)

    assert _keys(result) == ["fast/default", "fast-later/default", "slow/default"]


def test_free_first_orders_free_rows_before_metered_preserving_registry_order(
    tmp_path: Path,
) -> None:
    registry = _registry(
        tmp_path,
        [
            _row("metered-a"),
            _row("free-a", input_usd=0.0, output_usd=0.0, cost_class="free"),
            _row("metered-b"),
            _row("free-b", input_usd=0.0, output_usd=0.0, cost_class="free"),
        ],
    )

    result = REC.recommend(
        {"capability": "code-generation", "policy": "free-first"},
        registry=registry,
    )

    assert _keys(result) == [
        "free-a/default",
        "free-b/default",
        "metered-a/default",
        "metered-b/default",
    ]


def test_sensitive_recommendation_only_returns_local_only_candidates(tmp_path: Path) -> None:
    registry = _registry(
        tmp_path,
        [
            _row("networked", input_usd=0.0, output_usd=0.0, cost_class="free"),
            _row(
                "local",
                input_usd=0.000010,
                output_usd=0.000010,
                egress_policy="local-only",
            ),
        ],
    )

    result = REC.recommend(
        {"capability": "code-generation", "sensitive": True},
        registry=registry,
    )

    assert result.status == "ok"
    assert _keys(result) == ["local/default"]
    assert all(candidate.egress_policy == "local-only" for candidate in result.candidates)


def test_sensitive_recommendation_halts_without_network_alternatives(tmp_path: Path) -> None:
    registry = _registry(
        tmp_path,
        [
            _row("networked-a", input_usd=0.0, output_usd=0.0, cost_class="free"),
            _row("networked-b", rating="STRONG"),
        ],
    )

    result = REC.recommend(
        {"capability": "code-generation", "sensitive": True},
        registry=registry,
    )

    assert result.status == "halted"
    assert result.candidates == ()
    assert result.reason is not None
    assert "no local-only candidate" in result.reason
    assert "networked-a/default" not in result.reason


def test_token_estimate_filters_context_window(tmp_path: Path) -> None:
    registry = _registry(
        tmp_path,
        [
            _row("small", input_usd=0.0, output_usd=0.0, cost_class="free", context_window=100),
            _row("large", input_usd=0.00001, output_usd=0.00001, context_window=1_000),
        ],
    )

    result = REC.recommend(
        {"capability": "code-generation", "token_estimate": 500},
        registry=registry,
    )

    assert _keys(result) == ["large/default"]


def test_overlay_deprecated_rows_are_removed_from_recommendations(tmp_path: Path) -> None:
    registry = _registry(
        tmp_path,
        [
            _row("free", input_usd=0.0, output_usd=0.0, cost_class="free"),
            _row("metered"),
        ],
    )

    result = REC.recommend(
        {"capability": "code-generation"},
        registry=registry,
        overlay=SimpleNamespace(pins={}, deprecated=frozenset({"free/default"})),
    )

    assert _keys(result) == ["metered/default"]


@pytest.mark.parametrize(
    ("task", "match"),
    [
        ({}, "capability"),
        ({"capability": "telepathy"}, "unknown capability"),
        ({"capability": "code-generation", "policy": "random"}, "policy"),
        ({"capability": "code-generation", "policy": 1}, "policy"),
        ({"capability": "code-generation", "min_rating": "GREAT"}, "min_rating"),
        ({"capability": "code-generation", "min_rating": 1}, "min_rating"),
        ({"capability": "code-generation", "token_estimate": 1.5}, "token_estimate"),
        ({"capability": "code-generation", "limit": 0}, "limit"),
        ({"capability": "code-generation", "sensitive": "yes"}, "sensitive"),
    ],
)
def test_malformed_recommendation_task_errors(
    tmp_path: Path,
    task: dict[str, object],
    match: str,
) -> None:
    registry = _registry(tmp_path, [_row("metered")])

    with pytest.raises(REG.RegistryError, match=match):
        REC.recommend(task, registry=registry)


@pytest.mark.parametrize(
    ("task", "match"),
    [
        (REC.RecommendationTask(capability="", min_rating="MODERATE"), "capability"),
        (REC.RecommendationTask(capability="code-generation", policy=1), "policy"),
        (REC.RecommendationTask(capability="code-generation", min_rating=1), "min_rating"),
        (
            REC.RecommendationTask(capability="code-generation", token_estimate=1.5),
            "token_estimate",
        ),
        (REC.RecommendationTask(capability="code-generation", sensitive="yes"), "sensitive"),
    ],
)
def test_malformed_recommendation_task_dataclass_errors(
    tmp_path: Path,
    task: object,
    match: str,
) -> None:
    registry = _registry(tmp_path, [_row("metered")])

    with pytest.raises(REG.RegistryError, match=match):
        REC.recommend(task, registry=registry)


def test_recommendation_does_not_call_resolver_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = _load("engine_resolver_for_recommend_sentinel", RESOLVER_SCRIPT)
    registry = _registry(tmp_path, [_row("metered")])

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("recommend() must not call resolver preflight")

    monkeypatch.setattr(resolver, "preflight", _boom)

    result = REC.recommend({"capability": "code-generation"}, registry=registry)

    assert result.status == "ok"
    assert result.recommended is not None
