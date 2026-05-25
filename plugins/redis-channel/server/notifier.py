"""Channel-notification emission.

The Consumer thread needs to push `notifications/claude/channel` events
out through the MCP `ServerSession`. `send_notification` is an async
method that must run on the asyncio loop that owns the session — but
the Consumer runs on a plain `threading.Thread`. This module bridges
the two.

`AsyncNotifier` is the production implementation: it captures both
references at connect-time and uses `asyncio.run_coroutine_threadsafe`
to schedule the send. `RecordingNotifier` is the test seam — it records
emitted payloads without touching asyncio at all.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

from mcp.types import Notification

log = logging.getLogger(__name__)

CHANNEL_NOTIFICATION_METHOD = "notifications/claude/channel"


class ChannelNotifier(Protocol):
    """Thread-safe notification emitter consumed by `Consumer.on_message`."""

    def emit(self, payload: dict[str, Any]) -> None: ...


class AsyncNotifier:
    """Sends notifications/claude/channel to the connected MCP client.

    Constructed inside an MCP tool handler so the asyncio loop + session
    are available. The emit() method is called from the consumer thread.
    """

    def __init__(self, session: Any, loop: asyncio.AbstractEventLoop) -> None:
        self._session = session
        self._loop = loop

    def emit(self, payload: dict[str, Any]) -> None:
        # The generic Notification[dict, str] form lets us emit non-standard
        # method names that aren't in the MCP SDK's ServerNotification union.
        # FastMCP/ServerSession serializes the payload by Pydantic dump, so
        # the runtime accepts this even though static types reject it.
        if self._loop.is_closed():
            # Don't even create the coroutine — that would leak un-awaited.
            log.debug("AsyncNotifier: loop closed, dropping payload")
            return
        notif = Notification[dict, str](
            method=CHANNEL_NOTIFICATION_METHOD,
            params=payload,
        )
        coro = self._session.send_notification(notif)  # type: ignore[arg-type]
        try:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        except RuntimeError:
            # Loop transitioned to closed between the check and the schedule.
            # Close the coroutine explicitly so we don't leak.
            coro.close()
            log.debug("AsyncNotifier: loop closed mid-emit, dropping payload")


class RecordingNotifier:
    """Test-only notifier: appends payloads to a list. Threadsafe."""

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self.emitted: list[dict[str, Any]] = []

    def emit(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self.emitted.append(payload)


class NoopNotifier:
    """No-op notifier used when no MCP session is attached (e.g. early
    Phase 1 tests). Drops every emit silently."""

    def emit(self, payload: dict[str, Any]) -> None:
        log.debug("NoopNotifier dropping payload (no session attached)")
