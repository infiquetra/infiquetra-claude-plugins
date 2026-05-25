"""MCP server (stdio) for redis-bridge.

Phase 1 exposes three tools:
    - redis_bridge_connect(endpoint=..., session_name=...)
    - redis_bridge_disconnect()
    - redis_bridge_list()

The server is single-session: at most one active Presence at a time per
process. A second `connect` call disconnects the previous session first
(common when re-running the slash command after a config change).

Phase 2+ will add channel notifications (`notifications/claude/channel`),
a `reply` tool, and AskUserQuestion interception. This file is the seam
where that wiring lands.
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import signal
import sys
import threading
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import __version__
from .presence import Presence, build_metadata, list_live_sessions
from .redis_client import connect as redis_connect
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

    Wrapped in a lock so heartbeat thread (in Presence) and tool-handler
    threads (FastMCP can dispatch concurrently) don't race on lifecycle.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._presence: Presence | None = None
        self._client: Any | None = None
        self._endpoint_name: str | None = None

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._presence is not None

    def connect(self, *, endpoint: str, session_name: str | None) -> dict[str, Any]:
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
                self._presence = presence
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

    def shutdown(self) -> None:
        """Best-effort cleanup on process exit."""
        with self._lock:
            if self._presence is not None:
                self._disconnect_locked(reason="shutdown")

    def _disconnect_locked(self, *, reason: str) -> None:
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


def build_app() -> FastMCP:
    """Construct the FastMCP app with all Phase 1 tools registered."""
    app = FastMCP(
        name=f"redis-bridge v{__version__}",
        instructions=(
            "Generic Redis-streams bridge for Claude Code sessions. "
            "Pair with a router (e.g. hermes-claude-code-router) on the consumer "
            "side. Phase 1: presence + listing. Later phases add bidirectional "
            "channel notifications + reply tool."
        ),
    )

    @app.tool(
        name="redis_bridge_connect",
        description=(
            "Connect this Claude Code session to a redis-bridge endpoint "
            "(typically a Hermes profile like 'mimir'). Registers in the shared "
            "Redis registry and starts a 10s heartbeat. Returns the resolved "
            "session_name and endpoint metadata."
        ),
    )
    def redis_bridge_connect(
        endpoint: str = "mimir",
        session_name: str | None = None,
    ) -> dict[str, Any]:
        return _STATE.connect(endpoint=endpoint, session_name=session_name)

    @app.tool(
        name="redis_bridge_disconnect",
        description=(
            "Gracefully disconnect from the redis-bridge endpoint: stops "
            "heartbeat, removes the session from the registry, and emits an "
            "'unregistered' lifecycle event."
        ),
    )
    def redis_bridge_disconnect() -> dict[str, Any]:
        return _STATE.disconnect()

    @app.tool(
        name="redis_bridge_list",
        description=(
            "List all live Claude Code sessions registered at the connected "
            "endpoint. Filters out sessions whose heartbeat has expired and "
            "lazily GCs them from the registry. Requires a prior connect."
        ),
    )
    def redis_bridge_list() -> dict[str, Any]:
        return _STATE.list_sessions()

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
