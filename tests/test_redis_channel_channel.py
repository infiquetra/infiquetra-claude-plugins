"""Tests for the redis-channel MCP server's ServerState (connect/disconnect/list).

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
    """Verify FastMCP wiring constructs cleanly + registers all expected tools."""
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
        expected = {
            "redis_channel_connect",
            "redis_channel_disconnect",
            "redis_channel_list",
            "reply",
        }
        assert expected <= tool_names


# ─── Phase 2 additions: consumer + reply ────────────────────────────────────


import threading  # noqa: E402
import time as _time  # noqa: E402

from server import notifier as notifier_mod  # noqa: E402, type: ignore[import-not-found]
from server import redis_consumer, redis_producer  # noqa: E402, type: ignore[import-not-found]


def test_connect_attaches_inbound_consumer(patched_state: channel.ServerState, fr: Any) -> None:
    """A message XADD'd to inbound after connect reaches the notifier."""
    rec = notifier_mod.RecordingNotifier()
    out = patched_state.connect(endpoint="mimir", session_name="with-consumer", notifier=rec)
    try:
        assert out["ok"] is True
        assert out["consumer_attached"] is True
        assert out["notifier_kind"] == "RecordingNotifier"

        # Simulate the router writing an inbound message
        stream = redis_consumer.inbound_stream("with-consumer")
        msg_id = fr.xadd(
            stream, {"payload": json.dumps({"text": "hi from router", "chat_id": "c1"})}
        )

        # Wait for the consumer thread to dispatch
        for _ in range(30):
            if rec.emitted:
                break
            _time.sleep(0.1)
        assert len(rec.emitted) == 1
        payload = rec.emitted[0]
        assert payload["text"] == "hi from router"
        assert payload["chat_id"] == "c1"
        assert payload["_msg_id"] == msg_id
    finally:
        patched_state.disconnect()


def test_disconnect_stops_consumer(patched_state: channel.ServerState, fr: Any) -> None:
    rec = notifier_mod.RecordingNotifier()
    patched_state.connect(endpoint="mimir", session_name="stop-test", notifier=rec)
    patched_state.disconnect()

    # Find any thread named redis-channel-consumer-stop-test — should be gone
    matches = [t for t in threading.enumerate() if "consumer-stop-test" in t.name]
    assert matches == [] or not any(t.is_alive() for t in matches)


def test_second_connect_replaces_consumer(patched_state: channel.ServerState, fr: Any) -> None:
    rec1 = notifier_mod.RecordingNotifier()
    patched_state.connect(endpoint="mimir", session_name="first", notifier=rec1)
    rec2 = notifier_mod.RecordingNotifier()
    patched_state.connect(endpoint="mimir", session_name="second", notifier=rec2)
    try:
        # Write to second's inbound — only rec2 sees it
        stream = redis_consumer.inbound_stream("second")
        fr.xadd(stream, {"payload": json.dumps({"text": "for second"})})
        for _ in range(30):
            if rec2.emitted:
                break
            _time.sleep(0.1)
        assert any(p["text"] == "for second" for p in rec2.emitted)
        assert rec1.emitted == []
    finally:
        patched_state.disconnect()


def test_reply_xadds_to_outbound(patched_state: channel.ServerState, fr: Any) -> None:
    patched_state.connect(endpoint="mimir", session_name="reply-test")
    try:
        out = patched_state.reply(
            chat_id="c-discord-123",
            text="hello back",
            voice=False,
        )
        assert out["ok"] is True
        assert out["session_name"] == "reply-test"
        assert out["chat_id"] == "c-discord-123"
        msg_id = out["msg_id"]
        # Now read the outbound stream to verify
        entries = fr.xrange(redis_producer.outbound_stream("reply-test"))
        assert len(entries) == 1
        written_id, fields = entries[0]
        assert written_id == msg_id
        payload = json.loads(fields["payload"])
        assert payload["session_name"] == "reply-test"
        assert payload["endpoint"] == "mimir"
        assert payload["chat_id"] == "c-discord-123"
        assert payload["text"] == "hello back"
        assert payload["voice"] is False
    finally:
        patched_state.disconnect()


def test_reply_propagates_voice_flag(patched_state: channel.ServerState, fr: Any) -> None:
    patched_state.connect(endpoint="mimir", session_name="voice-reply")
    try:
        patched_state.reply(chat_id="vc-1", text="speak this", voice=True)
        entries = fr.xrange(redis_producer.outbound_stream("voice-reply"))
        payload = json.loads(entries[0][1]["payload"])
        assert payload["voice"] is True
    finally:
        patched_state.disconnect()


def test_reply_in_reply_to(patched_state: channel.ServerState, fr: Any) -> None:
    patched_state.connect(endpoint="mimir", session_name="thread-reply")
    try:
        patched_state.reply(
            chat_id="c1",
            text="answer",
            in_reply_to="1716000000000-0",
        )
        entries = fr.xrange(redis_producer.outbound_stream("thread-reply"))
        payload = json.loads(entries[0][1]["payload"])
        assert payload["in_reply_to"] == "1716000000000-0"
    finally:
        patched_state.disconnect()


def test_reply_when_not_connected(patched_state: channel.ServerState) -> None:
    out = patched_state.reply(chat_id="c1", text="hi")
    assert out["ok"] is False
    assert "not connected" in out["error"]


def test_reply_validates_empty_text(patched_state: channel.ServerState, fr: Any) -> None:
    patched_state.connect(endpoint="mimir", session_name="validate-empty")
    try:
        out = patched_state.reply(chat_id="c1", text="")
        assert out["ok"] is False
        assert out["error"] == "invalid argument"
        assert "text" in out["detail"]
        # Whitespace-only also rejected
        out2 = patched_state.reply(chat_id="c1", text="   \n  ")
        assert out2["ok"] is False
    finally:
        patched_state.disconnect()


def test_reply_validates_empty_chat_id(patched_state: channel.ServerState, fr: Any) -> None:
    patched_state.connect(endpoint="mimir", session_name="validate-chat")
    try:
        out = patched_state.reply(chat_id="", text="hi")
        assert out["ok"] is False
        assert out["error"] == "invalid argument"
        assert "chat_id" in out["detail"]
    finally:
        patched_state.disconnect()
