"""Tests for redis-channel registry config loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from server import registry  # type: ignore[import-not-found]


def write_config(path: Path, body: dict) -> Path:
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_load_registry_missing_file(tmp_path: Path) -> None:
    with pytest.raises(registry.RegistryNotFoundError):
        registry.load_registry(tmp_path / "absent.json")


def test_load_registry_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json}", encoding="utf-8")
    with pytest.raises(registry.RegistryParseError, match="invalid JSON"):
        registry.load_registry(p)


def test_load_registry_top_level_must_be_object(tmp_path: Path) -> None:
    p = write_config(tmp_path / "r.json", [])  # type: ignore[arg-type]
    p.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(registry.RegistryParseError, match="top-level"):
        registry.load_registry(p)


def test_load_registry_basic(tmp_path: Path) -> None:
    cfg = write_config(
        tmp_path / "r.json",
        {
            "endpoints": {
                "mimir": {
                    "redis_url": "redis://mac-mini:6379/0",
                    "redis_password_env": "HERMES_REDIS_PASSWORD",
                    "display_name": "Mimir",
                }
            }
        },
    )
    r = registry.load_registry(cfg)
    assert r.source == cfg
    assert set(r.endpoints) == {"mimir"}
    ep = r.endpoints["mimir"]
    assert ep.name == "mimir"
    assert ep.redis_url == "redis://mac-mini:6379/0"
    assert ep.redis_password_env == "HERMES_REDIS_PASSWORD"
    assert ep.display_name == "Mimir"
    # defaults applied
    assert r.defaults.heartbeat_seconds == 10
    assert r.defaults.registry_ttl_seconds == 60


def test_load_registry_defaults_override(tmp_path: Path) -> None:
    cfg = write_config(
        tmp_path / "r.json",
        {
            "endpoints": {},
            "defaults": {"heartbeat_seconds": 5, "registry_ttl_seconds": 30},
        },
    )
    r = registry.load_registry(cfg)
    assert r.defaults.heartbeat_seconds == 5
    assert r.defaults.registry_ttl_seconds == 30
    # untouched fields still default
    assert r.defaults.permission_window_seconds == 30


def test_endpoint_missing_redis_url_raises(tmp_path: Path) -> None:
    cfg = write_config(
        tmp_path / "r.json",
        {"endpoints": {"mimir": {"display_name": "Mimir"}}},
    )
    with pytest.raises(registry.RegistryParseError, match="redis_url"):
        registry.load_registry(cfg)


def test_endpoint_display_name_defaults_to_name(tmp_path: Path) -> None:
    cfg = write_config(
        tmp_path / "r.json",
        {"endpoints": {"foo": {"redis_url": "redis://h"}}},
    )
    r = registry.load_registry(cfg)
    assert r.endpoints["foo"].display_name == "foo"
    assert r.endpoints["foo"].redis_password_env is None


def test_registry_get_known_endpoint(tmp_path: Path) -> None:
    cfg = write_config(
        tmp_path / "r.json",
        {"endpoints": {"mimir": {"redis_url": "redis://h"}}},
    )
    r = registry.load_registry(cfg)
    assert r.get("mimir").name == "mimir"


def test_registry_get_unknown_endpoint_raises(tmp_path: Path) -> None:
    cfg = write_config(
        tmp_path / "r.json",
        {"endpoints": {"mimir": {"redis_url": "redis://h"}}},
    )
    r = registry.load_registry(cfg)
    with pytest.raises(registry.EndpointNotFoundError, match="available: mimir"):
        r.get("nope")
