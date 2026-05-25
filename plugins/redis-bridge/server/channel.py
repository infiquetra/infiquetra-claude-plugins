"""MCP server (stdio) for redis-bridge.

Phase 1 tools:
    - redis_bridge_connect(endpoint=..., session_name=...)
    - redis_bridge_disconnect()
    - redis_bridge_list()

Phase 2 additions:
    - reply(chat_id, text, voice=False, source_msg_id=None)
    - On connect: spawn a consumer thread that XREADGROUPs the inbound
      stream and emits each message as a `notifications/claude/channel`
      MCP notification on the session.

Single-session per process: at most one active Presence+Consumer pair
at a time. A second `connect` call replaces the previous one.
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import logging
import signal
import sys
import threading
import time
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from . import __version__
from .notifier import AsyncNotifier, ChannelNotifier, NoopNotifier
from .presence import Presence, build_metadata, list_live_sessions
from .protocol import Outbound
from .redis_client import connect as redis_connect
from .redis_consumer import Consumer
from .redis_producer import publish_outbound
from .registry import (
    EndpointNotFoundError,
    RegistryError,
    RegistryNotFoundError,
    load_registry,
)
from .session_id import resolve_session_name

log = logging.getLogger("redis_bridge.channel")


class ServerState:
    """Single-active-session state for the channel server.

    Wrapped in a lock so heartbeat thread (Presence), consumer thread,
    and tool-handler threads (FastMCP can dispatch concurrently) don't
    race on lifecycle.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._presence: Presence | None = None
        self._consumer: Consumer | None = None
        self._notifier: ChannelNotifier | None = None
        self._client: Any | None = None
        self._endpoint_name: str | None = None

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._presence is not None

    def connect(
        self,
        *,
        endpoint: str,
        session_name: str | None,
        notifier: ChannelNotifier | None = None,
    ) -> dict[str, Any]:
        """Open the channel: register presence, start consumer.

        `notifier` is the surface to which inbound stream messages are
        forwarded. In production it's the AsyncNotifier built from the
        MCP session + loop; in tests it's a RecordingNotifier or NoopNotifier.
        """
        try:
            with self._lock:
                if self._presence is not None:
                    self._disconnect_locked(reason="reconnect")

                registry = load_registry()
                ep = registry.get(endpoint)
                resolved_name = resolve_session_name(session_name)
                client = redis_connect(ep)
                metadata = build_metadata(
                    session_name=resolved_name,
                    endpoint=endpoint,
                )
                presence = Presence(
                    client,
                    metadata,
                    heartbeat_seconds=registry.defaults.heartbeat_seconds,
                    ttl_seconds=registry.defaults.registry_ttl_seconds,
                )
                presence.start()

                resolved_notifier: ChannelNotifier = notifier or NoopNotifier()
                consumer = Consumer(
                    client,
                    resolved_name,
                    on_message=resolved_notifier.emit,
                    block_ms=registry.defaults.consumer_block_ms,
                )
                consumer.start()

                self._presence = presence
                self._consumer = consumer
                self._notifier = resolved_notifier
                self._client = client
                self._endpoint_name = endpoint
                return {
                    "ok": True,
                    "session_name": metadata.session_name,
                    "endpoint": endpoint,
                    "endpoint_display": ep.display_name,
                    "host": metadata.host,
                    "cwd": metadata.cwd,
                    "heartbeat_seconds": registry.defaults.heartbeat_seconds,
                    "registry_ttl_seconds": registry.defaults.registry_ttl_seconds,
                    "consumer_attached": True,
                    "notifier_kind": type(resolved_notifier).__name__,
                }
        except RegistryError as e:
            return _format_registry_error(e)
        except ValueError as e:
            return {"ok": False, "error": "invalid argument", "detail": str(e)}
        except RuntimeError as e:
            return {"ok": False, "error": "runtime error", "detail": str(e)}
        except Exception as e:  # noqa: BLE001
            log.exception("connect failed")
            return {"ok": False, "error": type(e).__name__, "detail": str(e)}

    def disconnect(self) -> dict[str, Any]:
        try:
            with self._lock:
                if self._presence is None:
                    return {"ok": True, "was_connected": False}
                session_name = self._presence.session_name
                self._disconnect_locked(reason="user")
                return {"ok": True, "was_connected": True, "session_name": session_name}
        except Exception as e:  # noqa: BLE001
            log.exception("disconnect failed")
            return {"ok": False, "error": type(e).__name__, "detail": str(e)}

    def list_sessions(self) -> dict[str, Any]:
        try:
            with self._lock:
                if self._client is None:
                    return {
                        "ok": False,
                        "error": "not connected — call redis_bridge_connect first",
                    }
                sessions = list_live_sessions(self._client, gc_stale=True)
                return {
                    "ok": True,
                    "endpoint": self._endpoint_name,
                    "count": len(sessions),
                    "sessions": [
                        {
                            "session_name": m.session_name,
                            "host": m.host,
                            "cwd": m.cwd,
                            "git_branch": m.git_branch,
                            "started_at": m.started_at,
                            "pid": m.pid,
                            "is_self": (
                                self._presence is not None
                                and m.session_name == self._presence.session_name
                            ),
                        }
                        for m in sorted(sessions.values(), key=lambda meta: meta.started_at)
                    ],
                }
        except Exception as e:  # noqa: BLE001
            log.exception("list failed")
            return {"ok": False, "error": type(e).__name__, "detail": str(e)}

    def reply(
        self,
        *,
        chat_id: str,
        text: str,
        voice: bool = False,
        in_reply_to: str | None = None,
    ) -> dict[str, Any]:
        """XADD an Outbound payload to the active session's outbound stream."""
        try:
            if not chat_id or not chat_id.strip():
                raise ValueError("chat_id must be non-empty")
            if not text or not text.strip():
                raise ValueError("text must be non-empty")
            with self._lock:
                if self._presence is None or self._client is None:
                    return {
                        "ok": False,
                        "error": "not connected — call redis_bridge_connect first",
                    }
                session_name = self._presence.session_name
                endpoint = self._endpoint_name or ""
                client = self._client

            # Validate via Pydantic; rejects empty text, malformed chat_id, etc.
            payload = Outbound(
                session_name=session_name,
                endpoint=endpoint,
                chat_id=chat_id,
                text=text,
                voice=voice,
                in_reply_to=in_reply_to,
                ts=time.time(),
            )
            msg_id = publish_outbound(
                client,
                session_name,
                payload.model_dump(mode="json", exclude_none=True),
            )
            return {
                "ok": True,
                "session_name": session_name,
                "chat_id": chat_id,
                "msg_id": msg_id,
            }
        except ValueError as e:
            return {"ok": False, "error": "invalid argument", "detail": str(e)}
        except Exception as e:  # noqa: BLE001
            log.exception("reply failed")
            return {"ok": False, "error": type(e).__name__, "detail": str(e)}

    def shutdown(self) -> None:
        """Best-effort cleanup on process exit."""
        with self._lock:
            if self._presence is not None:
                self._disconnect_locked(reason="shutdown")

    def _disconnect_locked(self, *, reason: str) -> None:
        # Order: stop consumer first (so it doesn't try to ack on a stale
        # client), then presence, then close the client.
        if self._consumer is not None:
            try:
                self._consumer.stop()
            except Exception:  # noqa: BLE001
                log.exception("consumer.stop raised during disconnect")
            self._consumer = None
        if self._presence is not None:
            try:
                self._presence.stop(reason=reason)
            except Exception:  # noqa: BLE001
                log.exception("presence.stop raised during disconnect")
            self._presence = None
        if self._client is not None:
            try:
                close = getattr(self._client, "close", None)
                if callable(close):
                    close()
            except Exception:  # noqa: BLE001
                log.exception("redis client close raised during disconnect")
            self._client = None
        self._endpoint_name = None
        self._notifier = None


_STATE = ServerState()


def _format_registry_error(err: RegistryError) -> dict[str, Any]:
    if isinstance(err, RegistryNotFoundError):
        return {
            "ok": False,
            "error": "registry not configured",
            "detail": str(err),
            "hint": (
                "Create ~/.claude/channels/redis-bridge/registry.json or run "
                "/redis-bridge-configure"
            ),
        }
    if isinstance(err, EndpointNotFoundError):
        return {"ok": False, "error": "endpoint not found", "detail": str(err)}
    return {"ok": False, "error": "registry parse error", "detail": str(err)}


def _build_async_notifier(ctx: Context | None) -> ChannelNotifier:
    """If we have an MCP session + running loop, build a real notifier.

    Falls back to NoopNotifier if Context isn't injected (test code paths
    that call ServerState.connect directly should pass their own notifier).
    """
    if ctx is None:
        return NoopNotifier()
    try:
        session = ctx.session
        loop = asyncio.get_running_loop()
    except Exception:  # noqa: BLE001
        return NoopNotifier()
    return AsyncNotifier(session, loop)


def build_app() -> FastMCP:
    """Construct the FastMCP app with all redis-bridge tools registered."""
    app = FastMCP(
        name=f"redis-bridge v{__version__}",
        instructions=(
            "Generic Redis-streams bridge for Claude Code sessions. "
            "Pair with a router (e.g. hermes-claude-code-router) on the consumer "
            "side. The connect tool registers presence + starts the inbound "
            "consumer; reply XADDs outbound messages."
        ),
    )

    @app.tool(
        name="redis_bridge_connect",
        description=(
            "Connect this Claude Code session to a redis-bridge endpoint "
            "(typically a Hermes profile like 'mimir'). Registers in the shared "
            "Redis registry, starts a 10s heartbeat, and attaches an inbound "
            "consumer that emits notifications/claude/channel for each XADD'd "
            "inbound message. Returns the resolved session_name + metadata."
        ),
    )
    async def redis_bridge_connect(
        endpoint: str = "mimir",
        session_name: str | None = None,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        notifier = _build_async_notifier(ctx)
        return _STATE.connect(
            endpoint=endpoint,
            session_name=session_name,
            notifier=notifier,
        )

    @app.tool(
        name="redis_bridge_disconnect",
        description=(
            "Gracefully disconnect from the redis-bridge endpoint: stops "
            "heartbeat + consumer, removes the session from the registry, "
            "and emits an 'unregistered' lifecycle event."
        ),
    )
    async def redis_bridge_disconnect() -> dict[str, Any]:
        return _STATE.disconnect()

    @app.tool(
        name="redis_bridge_list",
        description=(
            "List all live Claude Code sessions registered at the connected "
            "endpoint. Filters out sessions whose heartbeat has expired and "
            "lazily GCs them from the registry. Requires a prior connect."
        ),
    )
    async def redis_bridge_list() -> dict[str, Any]:
        return _STATE.list_sessions()

    @app.tool(
        name="reply",
        description=(
            "Send a reply to the originating chat surface. The router on the "
            "other side of the redis-bridge listens to outbound messages and "
            "writes them to the corresponding Discord channel/DM/thread/voice. "
            "Set voice=True to request TTS playback in the originating voice "
            "channel (router may ignore if the source wasn't voice). chat_id "
            "must match the value provided on the inbound notification. "
            "Optionally pass in_reply_to=<original message_id from the "
            "inbound notification's _msg_id field> to thread the reply."
        ),
    )
    async def reply(
        chat_id: str,
        text: str,
        voice: bool = False,
        in_reply_to: str | None = None,
    ) -> dict[str, Any]:
        return _STATE.reply(
            chat_id=chat_id,
            text=text,
            voice=voice,
            in_reply_to=in_reply_to,
        )

    return app


def _install_signal_handlers() -> None:
    def _handle(signum, _frame) -> None:  # noqa: ANN001
        log.info("received signal %s — shutting down", signum)
        _STATE.shutdown()
        sys.exit(0)

    # Signal handlers can only be installed in the main thread; if we're
    # not, FastMCP / atexit will still cover cleanup.
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(ValueError):
            signal.signal(sig, _handle)


def run() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    log.info("redis-bridge v%s starting (stdio)", __version__)
    atexit.register(_STATE.shutdown)
    _install_signal_handlers()
    app = build_app()
    app.run()  # blocks until stdio closes
    return 0
