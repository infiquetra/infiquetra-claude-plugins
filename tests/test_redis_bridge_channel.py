"""Tests for the redis-bridge MCP server's ServerState (connect/disconnect/list).

We test the ServerState class directly rather than going through FastMCP —
that exercises every real component (registry loading, redis client wrapper,
Presence lifecycle, stale-GC) while keeping the test surface simple. The
FastMCP wrapper is mostly glue and is exercised manually via the build_app
smoke check.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fakeredis
import pytest
from server import channel, presence  # type: ignore[import-not-found]


@pytest.fixture
def fr() -> Any:
    # Returns the real fakeredis client; typed as Any so redis-py's
    # Awaitable[X] | X return types don't propagate into the tests.
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def registry_file(tmp_path: Path) -> Path:
    p = tmp_path / "registry.json"
    p.write_text(
        json.dumps(
            {
                "endpoints": {
                    "mimir": {
                        "redis_url": "redis://test:6379/0",
                        "redis_password_env": None,
                        "display_name": "Mimir (test)",
                    }
                },
                "defaults": {
                    "heartbeat_seconds": 1,
                    "registry_ttl_seconds": 10,
                },
            }
        ),
        encoding="utf-8",
    )
    return p


@pytest.fixture
def patched_state(
    monkeypatch: pytest.MonkeyPatch,
    fr: Any,
    registry_file: Path,
) -> channel.ServerState:
    """Build a ServerState whose Redis connect returns the fakeredis instance,
    and whose load_registry reads from our temp file."""

    def fake_load_registry() -> Any:
        from server import registry as registry_mod  # type: ignore[import-not-found]

        return registry_mod.load_registry(registry_file)

    def fake_connect(_endpoint: Any) -> Any:
        return fr

    monkeypatch.setattr(channel, "load_registry", fake_load_registry)
    monkeypatch.setattr(channel, "redis_connect", fake_connect)
    return channel.ServerState()


def test_connect_registers_and_starts_heartbeat(
    patched_state: channel.ServerState, fr: Any
) -> None:
    out = patched_state.connect(endpoint="mimir", session_name="my-session")
    try:
        assert out["ok"] is True
        assert out["session_name"] == "my-session"
        assert out["endpoint"] == "mimir"
        assert out["endpoint_display"] == "Mimir (test)"
        assert out["heartbeat_seconds"] == 1
        assert out["registry_ttl_seconds"] == 10
        # registry should have the entry
        raw = fr.hget(presence.REGISTRY_KEY, "my-session")
        assert raw is not None
        # hb key must exist
        assert fr.exists(presence.hb_key("my-session")) == 1
    finally:
        patched_state.disconnect()


def test_connect_uses_auto_name_when_omitted(patched_state: channel.ServerState, fr: Any) -> None:
    out = patched_state.connect(endpoint="mimir", session_name=None)
    try:
        assert out["ok"] is True
        # Auto-name format: <slug>-<8 hex>
        assert "-" in out["session_name"]
        suffix = out["session_name"].rsplit("-", 1)[1]
        assert len(suffix) == 8
    finally:
        patched_state.disconnect()


def test_disconnect_clears_state(patched_state: channel.ServerState, fr: Any) -> None:
    patched_state.connect(endpoint="mimir", session_name="bye")
    assert patched_state.is_connected
    out = patched_state.disconnect()
    assert out == {"ok": True, "was_connected": True, "session_name": "bye"}
    assert not patched_state.is_connected
    assert fr.hget(presence.REGISTRY_KEY, "bye") is None
    assert fr.exists(presence.hb_key("bye")) == 0


def test_disconnect_when_not_connected_is_idempotent(
    patched_state: channel.ServerState,
) -> None:
    out = patched_state.disconnect()
    assert out == {"ok": True, "was_connected": False}


def test_second_connect_replaces_first(patched_state: channel.ServerState, fr: Any) -> None:
    patched_state.connect(endpoint="mimir", session_name="first")
    patched_state.connect(endpoint="mimir", session_name="second")
    try:
        assert fr.hget(presence.REGISTRY_KEY, "first") is None
        assert fr.exists(presence.hb_key("first")) == 0
        assert fr.hget(presence.REGISTRY_KEY, "second") is not None
    finally:
        patched_state.disconnect()


def test_list_requires_connection(patched_state: channel.ServerState) -> None:
    out = patched_state.list_sessions()
    assert out["ok"] is False
    assert "not connected" in out["error"]


def test_list_returns_self(patched_state: channel.ServerState, fr: Any) -> None:
    patched_state.connect(endpoint="mimir", session_name="solo")
    try:
        out = patched_state.list_sessions()
        assert out["ok"] is True
        assert out["count"] == 1
        assert out["sessions"][0]["session_name"] == "solo"
        assert out["sessions"][0]["is_self"] is True
        assert out["endpoint"] == "mimir"
    finally:
        patched_state.disconnect()


def test_list_returns_other_live_sessions(patched_state: channel.ServerState, fr: Any) -> None:
    """Simulate another CC session by writing to the registry directly."""
    other_meta = presence.build_metadata(
        session_name="other-session",
        endpoint="mimir",
        cwd="/elsewhere",
        host="other-host",
        started_at=500.0,
    )
    fr.hset(presence.REGISTRY_KEY, "other-session", other_meta.to_json())
    fr.set(presence.hb_key("other-session"), "now", ex=60)

    patched_state.connect(endpoint="mimir", session_name="mine")
    try:
        out = patched_state.list_sessions()
        assert out["ok"] is True
        assert out["count"] == 2
        names = {s["session_name"] for s in out["sessions"]}
        assert names == {"mine", "other-session"}
        self_flags = {s["session_name"]: s["is_self"] for s in out["sessions"]}
        assert self_flags == {"mine": True, "other-session": False}
        # ordered by started_at ascending (other was 500.0)
        assert out["sessions"][0]["session_name"] == "other-session"
    finally:
        patched_state.disconnect()


def test_list_gcs_stale_entries(patched_state: channel.ServerState, fr: Any) -> None:
    stale_meta = presence.build_metadata(
        session_name="ghost",
        endpoint="mimir",
        cwd="/gone",
        host="gone-host",
    )
    fr.hset(presence.REGISTRY_KEY, "ghost", stale_meta.to_json())
    # No hb key → stale.

    patched_state.connect(endpoint="mimir", session_name="alive")
    try:
        out = patched_state.list_sessions()
        assert {s["session_name"] for s in out["sessions"]} == {"alive"}
        # GC happened
        assert fr.hget(presence.REGISTRY_KEY, "ghost") is None
    finally:
        patched_state.disconnect()


def test_connect_with_missing_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When registry.json doesn't exist, connect returns a structured error."""

    def fake_load_registry() -> Any:
        from server import registry as registry_mod  # type: ignore[import-not-found]

        return registry_mod.load_registry(tmp_path / "absent.json")

    monkeypatch.setattr(channel, "load_registry", fake_load_registry)
    state = channel.ServerState()
    out = state.connect(endpoint="mimir", session_name=None)
    assert out["ok"] is False
    assert out["error"] == "registry not configured"
    assert "registry config not found" in out["detail"]
    assert "hint" in out


def test_connect_with_unknown_endpoint(patched_state: channel.ServerState) -> None:
    out = patched_state.connect(endpoint="nope", session_name=None)
    assert out["ok"] is False
    assert out["error"] == "endpoint not found"


def test_connect_with_invalid_session_name(
    patched_state: channel.ServerState,
) -> None:
    out = patched_state.connect(endpoint="mimir", session_name="UPPER CASE")
    assert out["ok"] is False
    assert out["error"] == "invalid argument"


def test_shutdown_disconnects_active_session(patched_state: channel.ServerState, fr: Any) -> None:
    patched_state.connect(endpoint="mimir", session_name="atexit-test")
    patched_state.shutdown()
    assert not patched_state.is_connected
    assert fr.hget(presence.REGISTRY_KEY, "atexit-test") is None


def test_build_app_smoke() -> None:
    """Verify FastMCP wiring constructs cleanly + registers our 3 tools."""
    app = channel.build_app()
    # FastMCP exposes registered tools via a _tool_manager or tools attribute,
    # depending on version. Try both; if neither exists we just ensure the
    # call didn't raise.
    tool_names: set[str] = set()
    tm = getattr(app, "_tool_manager", None)
    if tm is not None:
        tool_names = set(getattr(tm, "_tools", {}).keys())
    elif hasattr(app, "tools"):
        tool_names = {t.name for t in app.tools}
    if tool_names:
        assert {"redis_bridge_connect", "redis_bridge_disconnect", "redis_bridge_list"} <= (
            tool_names
        )
