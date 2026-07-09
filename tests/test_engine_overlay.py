"""Tests for Saga repo-local engine overlay state."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
SCRIPT = SCRIPT_DIR / "engine_overlay.py"


def _load() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("engine_overlay", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["engine_overlay"] = module
    spec.loader.exec_module(module)
    return module


OVERLAY = _load()


def test_absent_overlay_loads_empty(tmp_path: Path) -> None:
    overlay = OVERLAY.load_overlay(tmp_path)

    assert overlay.pins == {}
    assert overlay.deprecated == frozenset()


def test_save_load_roundtrip_preserves_pins_and_deprecations(tmp_path: Path) -> None:
    overlay = OVERLAY.EngineOverlay(
        pins={"code-generation": "codex/gpt-5.5-xhigh"},
        deprecated=frozenset({"agy/gemini-3.1-pro-high"}),
    )

    path = OVERLAY.save_overlay(tmp_path, overlay)
    loaded = OVERLAY.load_overlay(tmp_path)

    assert path == tmp_path / ".saga" / "engine-overlay.json"
    assert loaded == overlay
    assert json.loads(path.read_text(encoding="utf-8")) == overlay.to_json()


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ("{nope", "malformed JSON"),
        ({"version": 2, "pins": {}, "deprecated": []}, "version"),
        ({"version": 1, "pins": {"telepathy": "codex/default"}, "deprecated": []}, "telepathy"),
        ({"version": 1, "pins": {"debug": "codex"}, "deprecated": []}, "engine_id/variant"),
        ({"version": 1, "pins": {}, "deprecated": ["codex/default", "codex/default"]}, "duplicate"),
    ],
)
def test_malformed_overlay_fails_loudly(
    tmp_path: Path,
    payload: str | dict[str, object],
    match: str,
) -> None:
    path = tmp_path / ".saga" / "engine-overlay.json"
    path.parent.mkdir()
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(OVERLAY.EngineOverlayError, match=match):
        OVERLAY.load_overlay(tmp_path)


def test_failed_validation_leaves_prior_overlay_unchanged(tmp_path: Path) -> None:
    original = OVERLAY.EngineOverlay(pins={"debug": "codex/gpt-5.5-xhigh"})
    path = OVERLAY.save_overlay(tmp_path, original)
    before = path.read_text(encoding="utf-8")

    with pytest.raises(OVERLAY.EngineOverlayError, match="telepathy"):
        OVERLAY.EngineOverlay(pins={"telepathy": "codex/gpt-5.5-xhigh"})

    assert path.read_text(encoding="utf-8") == before


def test_mutation_helpers_return_valid_new_overlay() -> None:
    overlay = OVERLAY.EngineOverlay()
    overlay = OVERLAY.pin_engine(overlay, "debug", "codex/gpt-5.5-xhigh")
    overlay = OVERLAY.deprecate_engine(overlay, "agy/gemini-3.1-pro-high")

    assert overlay.pins == {"debug": "codex/gpt-5.5-xhigh"}
    assert overlay.deprecated == frozenset({"agy/gemini-3.1-pro-high"})
    assert OVERLAY.clear_pin(overlay, "debug").pins == {}
    assert OVERLAY.clear_deprecated(overlay, "agy/gemini-3.1-pro-high").deprecated == frozenset()
    assert OVERLAY.clear_all() == OVERLAY.EngineOverlay()


def test_gitignore_ignores_local_engine_overlay() -> None:
    assert ".saga/engine-overlay.json" in (ROOT / ".gitignore").read_text(encoding="utf-8")
