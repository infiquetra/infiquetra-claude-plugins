#!/usr/bin/env python3
"""Repo-local Saga external-engine route overlay state."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine_registry import CAPABILITIES

OVERLAY_VERSION = 1
OVERLAY_PATH = Path(".saga") / "engine-overlay.json"


class EngineOverlayError(ValueError):
    """Raised when the repo-local engine overlay is malformed."""


@dataclass(frozen=True)
class EngineOverlay:
    """Validated local pins and deprecations for registry routing."""

    pins: Mapping[str, str] | None = None
    deprecated: frozenset[str] | set[str] | list[str] | tuple[str, ...] = frozenset()

    def __post_init__(self) -> None:
        pins = dict(self.pins or {})
        deprecated = frozenset(self.deprecated or ())
        for capability, engine_key in pins.items():
            _validate_capability(capability)
            _validate_engine_key(engine_key)
        for engine_key in deprecated:
            _validate_engine_key(engine_key)
        object.__setattr__(self, "pins", pins)
        object.__setattr__(self, "deprecated", deprecated)

    def to_json(self) -> dict[str, object]:
        return {
            "version": OVERLAY_VERSION,
            "pins": dict(sorted(dict(self.pins).items())),
            "deprecated": sorted(self.deprecated),
        }


def overlay_path(repo_root: Path | str) -> Path:
    return Path(repo_root) / OVERLAY_PATH


def load_overlay(repo_root: Path | str) -> EngineOverlay:
    """Load repo-local overlay state, returning an empty overlay when absent."""
    path = overlay_path(repo_root)
    if not path.exists():
        return EngineOverlay()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EngineOverlayError(f"{path}: malformed JSON: {exc.msg}") from exc
    except OSError as exc:
        raise EngineOverlayError(f"{path}: cannot read overlay: {exc}") from exc
    return overlay_from_json(raw, path=path)


def overlay_from_json(raw: Any, *, path: Path | None = None) -> EngineOverlay:
    where = str(path) if path is not None else "engine overlay"
    if not isinstance(raw, dict):
        raise EngineOverlayError(f"{where}: expected a JSON object")
    if raw.get("version") != OVERLAY_VERSION:
        raise EngineOverlayError(f"{where}: expected version {OVERLAY_VERSION}")

    raw_pins = raw.get("pins", {})
    if not isinstance(raw_pins, dict):
        raise EngineOverlayError(f"{where}: 'pins' must be an object")
    pins: dict[str, str] = {}
    for capability, engine_key in raw_pins.items():
        if not isinstance(capability, str):
            raise EngineOverlayError(f"{where}: pin capability {capability!r} must be a string")
        if not isinstance(engine_key, str):
            raise EngineOverlayError(f"{where}: pin for {capability!r} must be an engine key")
        _validate_capability(capability)
        _validate_engine_key(engine_key)
        pins[capability] = engine_key

    raw_deprecated = raw.get("deprecated", [])
    if not isinstance(raw_deprecated, list):
        raise EngineOverlayError(f"{where}: 'deprecated' must be a list")
    deprecated: list[str] = []
    seen: set[str] = set()
    for index, engine_key in enumerate(raw_deprecated):
        if not isinstance(engine_key, str):
            raise EngineOverlayError(f"{where}: deprecated[{index}] must be an engine key")
        _validate_engine_key(engine_key)
        if engine_key in seen:
            raise EngineOverlayError(f"{where}: duplicate deprecated engine key {engine_key!r}")
        seen.add(engine_key)
        deprecated.append(engine_key)

    return EngineOverlay(pins=pins, deprecated=frozenset(deprecated))


def save_overlay(repo_root: Path | str, overlay: EngineOverlay) -> Path:
    """Persist overlay state through an atomic local file replace."""
    clean = EngineOverlay(pins=dict(overlay.pins), deprecated=frozenset(overlay.deprecated))
    path = overlay_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(clean.to_json(), indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return path


def pin_engine(overlay: EngineOverlay, capability: str, engine_key: str) -> EngineOverlay:
    _validate_capability(capability)
    _validate_engine_key(engine_key)
    pins = dict(overlay.pins)
    pins[capability] = engine_key
    return EngineOverlay(pins=pins, deprecated=frozenset(overlay.deprecated))


def deprecate_engine(overlay: EngineOverlay, engine_key: str) -> EngineOverlay:
    _validate_engine_key(engine_key)
    return EngineOverlay(
        pins=dict(overlay.pins),
        deprecated=frozenset({*overlay.deprecated, engine_key}),
    )


def clear_pin(overlay: EngineOverlay, capability: str) -> EngineOverlay:
    _validate_capability(capability)
    pins = dict(overlay.pins)
    pins.pop(capability, None)
    return EngineOverlay(pins=pins, deprecated=frozenset(overlay.deprecated))


def clear_deprecated(overlay: EngineOverlay, engine_key: str) -> EngineOverlay:
    _validate_engine_key(engine_key)
    deprecated = set(overlay.deprecated)
    deprecated.discard(engine_key)
    return EngineOverlay(pins=dict(overlay.pins), deprecated=frozenset(deprecated))


def clear_all() -> EngineOverlay:
    return EngineOverlay()


def overlay_fingerprint(overlay: EngineOverlay | None) -> str:
    if overlay is None:
        return ""
    return json.dumps(overlay.to_json(), sort_keys=True, separators=(",", ":"))


def _validate_capability(capability: str) -> None:
    if capability not in CAPABILITIES:
        raise EngineOverlayError(f"unknown capability key {capability!r}")


def _validate_engine_key(engine_key: str) -> None:
    if not isinstance(engine_key, str) or engine_key.count("/") != 1:
        raise EngineOverlayError(f"engine key {engine_key!r} must be engine_id/variant")
    engine_id, variant = engine_key.split("/", 1)
    if not engine_id or not variant:
        raise EngineOverlayError(f"engine key {engine_key!r} must be engine_id/variant")
