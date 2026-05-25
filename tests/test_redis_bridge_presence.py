"""Tests for redis-bridge presence (registry HSET + heartbeat thread).

Uses fakeredis to model the Redis backend so tests run without a server.
"""

from __future__ import annotations

import time
from typing import Any

import fakeredis
import pytest
from server import presence  # type: ignore[import-not-found]


# Return type is Any (not fakeredis.FakeRedis) so redis-py's wide
# Awaitable[X] | X union return types don't poison every call site.
# Runtime is the real fakeredis client; only typing is loosened.
@pytest.fixture
def fr() -> Any:
    return fakeredis.FakeRedis(decode_responses=True)


def make_meta(name: str = "test-abc") -> presence.SessionMetadata:
    return presence.build_metadata(
        session_name=name,
        endpoint="mimir",
        cwd="/tmp/proj",
        host="testhost",
        git_branch="main",
        started_at=1000.0,
    )


def test_session_metadata_round_trip() -> None:
    meta = make_meta()
    body = meta.to_json()
    restored = presence.SessionMetadata.from_json(body)
    assert restored == meta


def test_build_metadata_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "time", lambda: 1234.5)
    meta = presence.build_metadata(session_name="x", endpoint="mimir")
    assert meta.session_name == "x"
    assert meta.endpoint == "mimir"
    assert meta.started_at == 1234.5
    assert meta.pid > 0
    assert meta.host  # non-empty
    assert meta.cwd  # non-empty


def test_presence_start_writes_registry_and_hb(fr: Any) -> None:
    meta = make_meta()
    p = presence.Presence(fr, meta, heartbeat_seconds=1, ttl_seconds=10)
    p.start()
    try:
        raw = fr.hget(presence.REGISTRY_KEY, meta.session_name)
        assert raw is not None
        assert presence.SessionMetadata.from_json(raw) == meta
        assert fr.exists(presence.hb_key(meta.session_name)) == 1
        # TTL should be roughly the configured value.
        assert 1 <= fr.ttl(presence.hb_key(meta.session_name)) <= 10
    finally:
        p.stop()


def test_presence_stop_cleans_up(fr: Any) -> None:
    meta = make_meta()
    p = presence.Presence(fr, meta, heartbeat_seconds=1, ttl_seconds=10)
    p.start()
    p.stop()
    assert fr.hget(presence.REGISTRY_KEY, meta.session_name) is None
    assert fr.exists(presence.hb_key(meta.session_name)) == 0


def test_presence_is_idempotent_on_double_stop(fr: Any) -> None:
    meta = make_meta()
    p = presence.Presence(fr, meta, heartbeat_seconds=1, ttl_seconds=10)
    p.start()
    p.stop()
    p.stop()  # must not raise


def test_presence_rejects_double_start(fr: Any) -> None:
    p = presence.Presence(fr, make_meta(), heartbeat_seconds=1, ttl_seconds=10)
    p.start()
    try:
        with pytest.raises(RuntimeError, match="already started"):
            p.start()
    finally:
        p.stop()


def test_presence_rejects_ttl_le_heartbeat(fr: Any) -> None:
    with pytest.raises(ValueError, match="ttl_seconds"):
        presence.Presence(fr, make_meta(), heartbeat_seconds=10, ttl_seconds=10)
    with pytest.raises(ValueError):
        presence.Presence(fr, make_meta(), heartbeat_seconds=10, ttl_seconds=5)


def test_presence_context_manager(fr: Any) -> None:
    meta = make_meta()
    with presence.Presence(fr, meta, heartbeat_seconds=1, ttl_seconds=10):
        assert fr.exists(presence.hb_key(meta.session_name)) == 1
    assert fr.exists(presence.hb_key(meta.session_name)) == 0


def test_heartbeat_refreshes_ttl(fr: Any) -> None:
    """After more than one heartbeat tick, the hb key must still exist
    (heartbeat re-set it before the previous expiry)."""
    meta = make_meta()
    # ttl just barely above heartbeat to force the test to depend on refresh
    p = presence.Presence(fr, meta, heartbeat_seconds=1, ttl_seconds=2)
    p.start()
    try:
        time.sleep(1.3)
        assert fr.exists(presence.hb_key(meta.session_name)) == 1
        time.sleep(1.3)
        assert fr.exists(presence.hb_key(meta.session_name)) == 1
    finally:
        p.stop()


def test_list_live_sessions_filters_by_hb(fr: Any) -> None:
    meta1 = make_meta("live-1")
    meta2 = make_meta("live-2")
    p1 = presence.Presence(fr, meta1, heartbeat_seconds=1, ttl_seconds=10)
    p2 = presence.Presence(fr, meta2, heartbeat_seconds=1, ttl_seconds=10)
    p1.start()
    p2.start()
    try:
        live = presence.list_live_sessions(fr)
        assert set(live) == {"live-1", "live-2"}
    finally:
        p1.stop()
        p2.stop()


def test_list_live_sessions_skips_stale(fr: Any) -> None:
    meta_live = make_meta("live")
    meta_stale = make_meta("stale")
    fr.hset(presence.REGISTRY_KEY, "live", meta_live.to_json())
    fr.hset(presence.REGISTRY_KEY, "stale", meta_stale.to_json())
    fr.set(presence.hb_key("live"), str(time.time()), ex=60)
    # no hb key for "stale"
    live = presence.list_live_sessions(fr)
    assert set(live) == {"live"}


def test_list_live_sessions_gc_stale(fr: Any) -> None:
    meta_live = make_meta("live")
    meta_stale = make_meta("stale")
    fr.hset(presence.REGISTRY_KEY, "live", meta_live.to_json())
    fr.hset(presence.REGISTRY_KEY, "stale", meta_stale.to_json())
    fr.set(presence.hb_key("live"), str(time.time()), ex=60)
    presence.list_live_sessions(fr, gc_stale=True)
    assert fr.hget(presence.REGISTRY_KEY, "stale") is None
    assert fr.hget(presence.REGISTRY_KEY, "live") is not None


def test_list_live_sessions_handles_corrupt_entry(fr: Any) -> None:
    fr.hset(presence.REGISTRY_KEY, "broken", "{not valid json}")
    fr.set(presence.hb_key("broken"), str(time.time()), ex=60)
    live = presence.list_live_sessions(fr)
    assert live == {}


def test_lifecycle_events_published(fr: Any) -> None:
    meta = make_meta("pub-test")
    pubsub = fr.pubsub()
    pubsub.subscribe(presence.events_channel(meta.session_name))
    pubsub.get_message(timeout=0.1)  # subscribe ack
    p = presence.Presence(fr, meta, heartbeat_seconds=1, ttl_seconds=10)
    p.start()
    p.stop(reason="test")
    msgs = []
    while True:
        m = pubsub.get_message(timeout=0.1)
        if m is None:
            break
        if m.get("type") == "message":
            msgs.append(m)
    pubsub.close()
    types_seen = []
    for m in msgs:
        import json as _json

        payload = _json.loads(m["data"])
        types_seen.append(payload["type"])
        assert payload["session_name"] == meta.session_name
        assert payload["v"] == 1
    assert "registered" in types_seen
    assert "unregistered" in types_seen
