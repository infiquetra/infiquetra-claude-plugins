"""Tests for the Saga engine registry operator CLI."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
SCRIPT = SCRIPT_DIR / "engine_registry_cli.py"


def _load() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("engine_registry_cli", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["engine_registry_cli"] = module
    spec.loader.exec_module(module)
    return module


C = _load()
REGISTRY_MODULE = importlib.import_module("engine_registry")


def _row(
    engine_id: str,
    variant: str,
    *,
    cost_speed_rank: int,
    registry_rating: str,
    debug_rating: str | None = None,
) -> dict[str, Any]:
    profile = {
        "code-generation": {"rating": registry_rating, "note": "fixture"},
    }
    if debug_rating is not None:
        profile["debug"] = {"rating": debug_rating, "note": "fixture"}
    return {
        "engine_id": engine_id,
        "variant": variant,
        "substrate": "external",
        "default_for_engine": True,
        "invocation": {
            "via": f"{engine_id}:delegate",
            "recipe": f"{engine_id} delegate --mode no-write",
            "write_capable": False,
        },
        "context_window": 400000,
        "cost_speed_rank": cost_speed_rank,
        "cost_per_token": {"input_usd": 0.000001, "output_usd": 0.000002},
        "cost_class": "metered",
        "budget_ceiling_usd": 25.0,
        "latency_class": "standard",
        "model_identity": f"{engine_id}-{variant}",
        "last_validated": "2026-07-09",
        "receipt_emitter": f"{engine_id}-bridge",
        "capability_profile": profile,
        "prompting_protocol": ["Return advisory output only."],
        "sources": [
            {
                "claim": "fixture",
                "url": "https://example.invalid/fixture",
                "date": "2026-07-09",
                "tag": "LOCAL",
                "corroboration": "MODERATE",
            }
        ],
    }


def _write_registry(tmp_path: Path) -> Path:
    data = {
        "capabilities": list(REGISTRY_MODULE.CAPABILITIES),
        "engines": [
            _row("codex", "gpt-5.5-xhigh", cost_speed_rank=2, registry_rating="STRONG"),
            _row(
                "agy",
                "gemini-3.1-pro-high",
                cost_speed_rank=1,
                registry_rating="STRONG",
                debug_rating="MODERATE",
            ),
        ],
        "roles": {
            "cross-family-review-panel": {
                "members": ["codex/gpt-5.5-xhigh", "agy/gemini-3.1-pro-high"],
                "verdict": "advisory",
                "verifier": "claude",
            }
        },
    }
    path = tmp_path / "engine-registry.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _args(tmp_path: Path, registry: Path, *args: str) -> list[str]:
    return ["--repo-root", str(tmp_path), "--registry", str(registry), *args]


def test_list_includes_rows_metadata_currency_and_overlay_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = _write_registry(tmp_path)

    assert C.main(_args(tmp_path, registry, "engines", "list")) == 0

    out = capsys.readouterr().out
    assert "codex/gpt-5.5-xhigh" in out
    assert "agy/gemini-3.1-pro-high" in out
    assert "cost_speed_rank" in out
    assert "cost_class" in out
    assert "budget_ceiling_usd" in out
    assert "latency_class" in out
    assert "current" in out
    assert "active" in out


def test_list_json_includes_cost_policy_fields(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = _write_registry(tmp_path)

    assert C.main(_args(tmp_path, registry, "engines", "list", "--json")) == 0

    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["cost_class"] == "metered"
    assert rows[0]["budget_ceiling_usd"] == 25.0


def test_pin_writes_overlay_and_explain_shows_pinned_route(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = _write_registry(tmp_path)

    assert (
        C.main(
            _args(
                tmp_path,
                registry,
                "engines",
                "pin",
                "code-generation",
                "codex/gpt-5.5-xhigh",
            )
        )
        == 0
    )
    assert C.main(_args(tmp_path, registry, "route", "explain", "code-generation")) == 0

    out = capsys.readouterr().out
    overlay = json.loads((tmp_path / ".saga" / "engine-overlay.json").read_text(encoding="utf-8"))
    assert overlay["pins"] == {"code-generation": "codex/gpt-5.5-xhigh"}
    assert "selected: codex/gpt-5.5-xhigh" in out
    assert "selected by local overlay pin" in out


def test_deprecate_skips_row_in_route_explain(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = _write_registry(tmp_path)

    assert C.main(_args(tmp_path, registry, "engines", "deprecate", "agy/gemini-3.1-pro-high")) == 0
    assert C.main(_args(tmp_path, registry, "route", "explain", "code-generation")) == 0

    out = capsys.readouterr().out
    assert "selected: codex/gpt-5.5-xhigh" in out
    assert "deprecated: agy/gemini-3.1-pro-high" in out
    assert "- agy/gemini-3.1-pro-high" not in out


def test_route_explain_is_read_only_and_deterministic(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = _write_registry(tmp_path)
    assert (
        C.main(
            _args(
                tmp_path,
                registry,
                "engines",
                "pin",
                "code-generation",
                "codex/gpt-5.5-xhigh",
            )
        )
        == 0
    )
    capsys.readouterr()
    overlay_path = tmp_path / ".saga" / "engine-overlay.json"
    before = overlay_path.read_text(encoding="utf-8")
    before_mtime = overlay_path.stat().st_mtime_ns

    assert C.main(_args(tmp_path, registry, "route", "explain", "code-generation")) == 0
    first = capsys.readouterr().out
    assert C.main(_args(tmp_path, registry, "route", "explain", "code-generation")) == 0
    second = capsys.readouterr().out

    assert first == second
    assert overlay_path.read_text(encoding="utf-8") == before
    assert overlay_path.stat().st_mtime_ns == before_mtime


def test_unknown_capability_returns_nonzero_with_registry_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = _write_registry(tmp_path)

    assert C.main(_args(tmp_path, registry, "route", "explain", "telepathy")) == 2

    err = capsys.readouterr().err
    assert "unknown capability key 'telepathy'" in err
