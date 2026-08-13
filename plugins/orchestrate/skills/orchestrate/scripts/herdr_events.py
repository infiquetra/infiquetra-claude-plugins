#!/usr/bin/env python3
"""Small newline-delimited JSON client for herdr's event socket.

Subscription names use herdr's dotted request vocabulary. Broadcast envelopes use a separate,
underscored vocabulary; callers must not translate one into the other. The committed schema
fixture is captured from ``herdr api schema --output`` and the tests validate requests against it.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SOCKET_PATH = Path("~/.config/herdr/herdr.sock").expanduser()

# Protocol 19's request-side Subscription variants. This is intentionally not EventKind: those
# broadcast names are underscored and are invalid in an events.subscribe request.
SUBSCRIPTION_TYPES = frozenset(
    {
        "workspace.created",
        "workspace.updated",
        "workspace.metadata_updated",
        "workspace.renamed",
        "workspace.moved",
        "workspace.reordered",
        "workspace.closed",
        "workspace.focused",
        "worktree.created",
        "worktree.opened",
        "worktree.removed",
        "tab.created",
        "tab.closed",
        "tab.focused",
        "tab.renamed",
        "tab.moved",
        "pane.created",
        "pane.closed",
        "pane.updated",
        "pane.focused",
        "pane.moved",
        "pane.exited",
        "pane.agent_detected",
        "pane.output_matched",
        "pane.agent_status_changed",
        "pane.scroll_changed",
        "layout.updated",
    }
)
READ_SOURCES = frozenset({"visible", "recent", "recent_unwrapped", "detection"})
MATCH_TYPES = frozenset({"substring", "regex"})


class HerdrEventError(RuntimeError):
    """Base error for event-client failures."""


class SubscriptionError(HerdrEventError):
    """A requested subscription does not satisfy herdr's published contract."""


class ProtocolError(HerdrEventError):
    """The socket returned malformed JSON or an unexpected response shape."""


class SocketUnavailableError(HerdrEventError):
    """The configured herdr socket could not be opened."""


@dataclass(frozen=True)
class HerdrEvent:
    """One decoded broadcast or subscription event."""

    name: str
    data: dict[str, Any]
    raw: dict[str, Any]

    @property
    def pane_id(self) -> str | None:
        value = self.data.get("pane_id")
        return value if isinstance(value, str) else None

    @property
    def matched_line(self) -> str | None:
        value = self.data.get("matched_line")
        return value if isinstance(value, str) else None

    @property
    def revision(self) -> int | None:
        read = self.data.get("read")
        value = read.get("revision") if isinstance(read, Mapping) else self.data.get("revision")
        return value if isinstance(value, int) and not isinstance(value, bool) else None


def _validate_match(value: Any, *, index: int) -> None:
    if not isinstance(value, Mapping):
        raise SubscriptionError(f"subscription {index}: match must be an object")
    match_type = value.get("type")
    match_value = value.get("value")
    if match_type not in MATCH_TYPES:
        raise SubscriptionError(f"subscription {index}: match.type must be 'substring' or 'regex'")
    if not isinstance(match_value, str) or not match_value:
        raise SubscriptionError(f"subscription {index}: match.value must be a non-empty string")


def validate_subscription(subscription: Mapping[str, Any], *, index: int = 0) -> None:
    """Fail loudly when one subscription would not satisfy the protocol-19 request shape."""
    event_type = subscription.get("type")
    if not isinstance(event_type, str) or not event_type:
        raise SubscriptionError(f"subscription {index}: type must be a non-empty string")
    if event_type not in SUBSCRIPTION_TYPES:
        raise SubscriptionError(
            f"subscription {index}: unsupported request type {event_type!r}; "
            "events.subscribe uses dotted request types, not underscored broadcast names"
        )

    if event_type == "pane.output_matched":
        pane_id = subscription.get("pane_id")
        source = subscription.get("source")
        if not isinstance(pane_id, str) or not pane_id:
            raise SubscriptionError(f"subscription {index}: pane.output_matched requires pane_id")
        if source not in READ_SOURCES:
            raise SubscriptionError(
                f"subscription {index}: source must be one of {sorted(READ_SOURCES)}"
            )
        _validate_match(subscription.get("match"), index=index)
    elif event_type in {"pane.agent_status_changed", "pane.scroll_changed"}:
        pane_id = subscription.get("pane_id")
        if not isinstance(pane_id, str) or not pane_id:
            raise SubscriptionError(f"subscription {index}: {event_type} requires pane_id")


def build_subscribe_request(
    request_id: str, subscriptions: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Validate every subscription and build one ``events.subscribe`` request."""
    if not request_id:
        raise SubscriptionError("request_id must be non-empty")
    serialized: list[dict[str, Any]] = []
    for index, subscription in enumerate(subscriptions):
        if not isinstance(subscription, Mapping):
            raise SubscriptionError(f"subscription {index}: expected an object")
        validate_subscription(subscription, index=index)
        serialized.append(dict(subscription))
    if not serialized:
        raise SubscriptionError("events.subscribe requires at least one subscription")
    return {
        "id": request_id,
        "method": "events.subscribe",
        "params": {"subscriptions": serialized},
    }


def decode_event(payload: Mapping[str, Any]) -> HerdrEvent:
    """Decode a broadcast or subscription envelope without changing its event name."""
    name = payload.get("event")
    data = payload.get("data")
    if not isinstance(name, str) or not isinstance(data, Mapping):
        raise ProtocolError("event envelope requires string 'event' and object 'data'")
    decoded = HerdrEvent(name=name, data=dict(data), raw=dict(payload))
    if name == "pane.output_matched" and (
        decoded.pane_id is None or decoded.matched_line is None or decoded.revision is None
    ):
        raise ProtocolError("pane.output_matched requires pane_id, matched_line, and read.revision")
    return decoded


def _decode_line(line: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"herdr returned malformed JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("herdr response must be a JSON object")
    return payload


def _write_request(stream: Any, request: Mapping[str, Any]) -> None:
    stream.write(json.dumps(request, separators=(",", ":")).encode("utf-8") + b"\n")
    stream.flush()


class HerdrEventClient:
    """Open the Unix socket, issue requests, and hold event subscriptions across reconnects."""

    def __init__(self, socket_path: Path = DEFAULT_SOCKET_PATH) -> None:
        self.socket_path = socket_path.expanduser()

    def _connect(self) -> socket.socket:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(str(self.socket_path))
        except OSError as exc:
            sock.close()
            raise SocketUnavailableError(
                f"cannot connect to herdr event socket at {self.socket_path}: {exc}; "
                "confirm the herdr server is running with 'herdr status server'"
            ) from exc
        return sock

    def request(self, request_id: str, method: str, params: Mapping[str, Any]) -> dict[str, Any]:
        """Send one ordinary request on a short-lived connection and return its result."""
        request = {"id": request_id, "method": method, "params": dict(params)}
        with self._connect() as sock, sock.makefile("rwb") as stream:
            _write_request(stream, request)
            line = stream.readline()
        if not line:
            raise ProtocolError(f"herdr closed the socket before replying to {method}")
        response = _decode_line(line)
        if "error" in response:
            raise ProtocolError(f"herdr rejected {method}: {response['error']}")
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise ProtocolError(f"herdr reply to {method} did not contain an object result")
        return dict(result)

    def subscribe_once(
        self,
        subscriptions: Sequence[Mapping[str, Any]],
        on_event: Callable[[HerdrEvent], None],
        *,
        request_id: str = "orchestrate-subscribe",
        after_subscribed: Callable[[], None] | None = None,
    ) -> None:
        """Hold one subscription until the peer closes the stream."""
        request = build_subscribe_request(request_id, subscriptions)
        with self._connect() as sock, sock.makefile("rwb") as stream:
            _write_request(stream, request)
            line = stream.readline()
            if not line:
                raise ProtocolError("herdr closed the socket before confirming the subscription")
            response = _decode_line(line)
            expected = {"type": "subscription_started"}
            if response.get("result") != expected:
                raise ProtocolError(
                    "events.subscribe expected result {'type': 'subscription_started'}, "
                    f"received {response!r}"
                )
            if after_subscribed is not None:
                after_subscribed()

            while line := stream.readline():
                on_event(decode_event(_decode_line(line)))

    def run_forever(
        self,
        subscriptions: Sequence[Mapping[str, Any]],
        on_event: Callable[[HerdrEvent], None],
        catch_up: Callable[[], None],
        *,
        reconnect_delay: float = 1.0,
        stop_event: threading.Event | None = None,
        max_connections: int | None = None,
        diagnostic: Callable[[str], None] | None = None,
    ) -> None:
        """Reconnect after every close and run exactly one catch-up per accepted connection."""
        stop = stop_event or threading.Event()
        connected = 0
        while not stop.is_set():

            def _connected_catch_up() -> None:
                nonlocal connected
                connected += 1
                catch_up()

            try:
                self.subscribe_once(
                    subscriptions,
                    on_event,
                    request_id=f"orchestrate-subscribe-{connected + 1}",
                    after_subscribed=_connected_catch_up,
                )
            except HerdrEventError as exc:
                if diagnostic is not None:
                    diagnostic(str(exc))
                if connected == 0 and isinstance(exc, SubscriptionError):
                    raise

            if max_connections is not None and connected >= max_connections:
                return
            if not stop.is_set() and reconnect_delay > 0:
                stop.wait(reconnect_delay)


def unix_time() -> float:
    """Clock seam used when a handled output event updates ``last_event_at``."""
    return time.time()
