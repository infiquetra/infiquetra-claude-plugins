"""MCP server (stdio) for redis-channel.

Phase 1 tools:
    - redis_channel_connect(endpoint=..., session_name=...)
    - redis_channel_disconnect()
    - redis_channel_list()

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
import json
import logging
import os
import signal
import socket
import sys
import threading
import time
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import CallToolResult, TextContent

from . import __version__
from .notifier import AsyncNotifier, ChannelNotifier, NoopNotifier
from .presence import (
    Presence,
    build_metadata,
    disambiguate_if_collision,
    list_live_sessions,
)
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

log = logging.getLogger("redis_channel.channel")


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
        # `debug` controls how chatty Claude should be in the terminal after
        # replying. Default off (quiet). Set via the connect tool's `debug`
        # arg; surfaced in connect's response so the slash-command markdown
        # + agent coach can steer Claude's reply-narration behavior.
        self._debug: bool = False

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._presence is not None

    @property
    def debug(self) -> bool:
        with self._lock:
            return self._debug

    def connect(
        self,
        *,
        endpoint: str,
        session_name: str | None,
        notifier: ChannelNotifier | None = None,
        debug: bool = False,
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
                # Auto-disambiguate only when the user didn't supply an
                # explicit name. An explicit name is treated as intent — we
                # let the regular reconnect/replace semantics handle it.
                if session_name is None:
                    resolved_name = disambiguate_if_collision(
                        client,
                        resolved_name,
                        host=socket.gethostname(),
                        pid=os.getpid(),
                    )
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
                self._debug = bool(debug)
                return {
                    "ok": True,
                    "session_name": metadata.session_name,
                    "endpoint": endpoint,
                    "endpoint_display": ep.display_name,
                    "debug": self._debug,
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
                        "error": "not connected — call redis_channel_connect first",
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
                        "error": "not connected — call redis_channel_connect first",
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
        self._debug = False


_STATE = ServerState()


def _format_registry_error(err: RegistryError) -> dict[str, Any]:
    if isinstance(err, RegistryNotFoundError):
        return {
            "ok": False,
            "error": "registry not configured",
            "detail": str(err),
            "hint": (
                "Create ~/.claude/channels/redis-channel/registry.json or run "
                "/redis-channel-configure"
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
    """Construct the FastMCP app with all redis-channel tools registered."""
    app = FastMCP(
        name=f"redis-channel v{__version__}",
        instructions=(
            "Generic Redis-streams bridge for Claude Code sessions. "
            "Pair with a router (e.g. hermes-claude-code-router) on the consumer "
            "side. The connect tool registers presence + starts the inbound "
            "consumer; reply XADDs outbound messages."
        ),
    )

    @app.tool(
        name="redis_channel_connect",
        description=(
            "Connect this Claude Code session to a redis-channel endpoint "
            "(typically a Hermes profile like 'mimir'). Registers in the shared "
            "Redis registry, starts a 10s heartbeat, and attaches an inbound "
            "consumer that emits notifications/claude/channel for each XADD'd "
            "inbound message. Returns the resolved session_name + metadata. "
            "Pass debug=true to opt into verbose reply narration in the local "
            "terminal (useful for dev/test); default false = quiet."
        ),
    )
    async def redis_channel_connect(
        endpoint: str = "mimir",
        session_name: str | None = None,
        debug: bool = False,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        notifier = _build_async_notifier(ctx)
        return _STATE.connect(
            endpoint=endpoint,
            session_name=session_name,
            notifier=notifier,
            debug=debug,
        )

    @app.tool(
        name="redis_channel_disconnect",
        description=(
            "Gracefully disconnect from the redis-channel endpoint: stops "
            "heartbeat + consumer, removes the session from the registry, "
            "and emits an 'unregistered' lifecycle event."
        ),
    )
    async def redis_channel_disconnect() -> dict[str, Any]:
        return _STATE.disconnect()

    @app.tool(
        name="redis_channel_list",
        description=(
            "List all live Claude Code sessions registered at the connected "
            "endpoint. Filters out sessions whose heartbeat has expired and "
            "lazily GCs them from the registry. Requires a prior connect."
        ),
    )
    async def redis_channel_list() -> dict[str, Any]:
        return _STATE.list_sessions()

    @app.tool(
        name="reply",
        description=(
            "Send a reply to the originating chat surface. The router on the "
            "other side of the redis-channel listens to outbound messages and "
            "writes them to the corresponding Discord channel/DM/thread/voice. "
            "Set voice=True to request TTS playback in the originating voice "
            "channel (router may ignore if the source wasn't voice). chat_id "
            "must match the value provided on the inbound notification. "
            "Optionally pass in_reply_to=<original message_id from the "
            "inbound notification's _msg_id field> to thread the reply. "
            "The `text` argument IS the user-facing message — it's what the "
            "recipient reads or hears via TTS. Do NOT put internal reasoning, "
            "tool-call narration, or terminal-only commentary in `text`."
        ),
    )
    async def reply(
        chat_id: str,
        text: str,
        voice: bool = False,
        in_reply_to: str | None = None,
    ) -> CallToolResult:
        result = _STATE.reply(
            chat_id=chat_id,
            text=text,
            voice=voice,
            in_reply_to=in_reply_to,
        )
        if not result.get("ok"):
            # Error path: surface the structured error as JSON text content so
            # Claude can read it and the user can see what went wrong.
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(result))],
                structuredContent=result,
                isError=True,
            )
        # Success: return ONLY structuredContent — no TextContent echo. The
        # v0.4.4 echo was intended to make the terminal render the sent text,
        # but Claude Code does not render MCP TextContent as chat output
        # (debug log: "Tool ... not found in render-time tools"). Worse, the
        # echo signals to Claude that the text was "already delivered as
        # user-visible content," which appears to suppress text_block emission
        # alongside the tool call — leaving only "Called plugin:..." in the
        # terminal. Removing the echo eliminates that false signal; the
        # text_block in Claude's assistant turn is now the only path to making
        # the answer visible locally.
        return CallToolResult(
            content=[],
            structuredContent=result,
            isError=False,
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


def _enable_channel_capability(app: FastMCP) -> None:
    """Declare the `claude/channel` experimental capability in the initialize
    response so Claude Code accepts our `notifications/claude/channel` events.

    Without this, Claude Code logs: "Channel notifications skipped: server did
    not declare claude/channel capability" and silently drops every channel
    notification we emit — which makes Phase 2's text bridge a no-op from
    Claude Code's perspective.

    FastMCP doesn't expose a constructor param for experimental_capabilities,
    so we patch the underlying server's create_initialization_options to inject
    the capability whenever it's called (which happens once per `app.run()`).
    """
    server = app._mcp_server  # noqa: SLF001
    original = server.create_initialization_options

    def patched(notification_options=None, experimental_capabilities=None):  # noqa: ANN001, ANN202
        experimental_capabilities = dict(experimental_capabilities or {})
        experimental_capabilities.setdefault("claude/channel", {})
        return original(notification_options, experimental_capabilities)

    server.create_initialization_options = patched  # type: ignore[method-assign]


def run() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    log.info("redis-channel v%s starting (stdio)", __version__)
    atexit.register(_STATE.shutdown)
    _install_signal_handlers()
    app = build_app()
    _enable_channel_capability(app)
    app.run()  # blocks until stdio closes
    return 0
