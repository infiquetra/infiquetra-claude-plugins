"""Herdr event client, tracked subscriber, revision guard, and reconnect catch-up tests."""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
import threading
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "plugins" / "orchestrate" / "skills" / "orchestrate" / "scripts"
SCHEMA = ROOT / "plugins" / "orchestrate" / "tests" / "fixtures" / "herdr-api-schema.json"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

EVENTS = _load("herdr_events", SCRIPT_DIR / "herdr_events.py")
REGISTER = _load("register", SCRIPT_DIR / "register.py")
SUBSCRIBER = _load("orchestrate_subscriber", SCRIPT_DIR / "subscriber.py")


def _schema_ref(name: str, group: str = "request") -> dict[str, Any]:
    captured = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return {
        "$schema": captured["$schema"],
        "schemas": captured["schemas"],
        "$ref": f"#/schemas/{group}/$defs/{name}",
    }


def _output_event(pane_id: str, sentinel: str, revision: int) -> dict[str, Any]:
    return {
        "event": "pane.output_matched",
        "data": {
            "pane_id": pane_id,
            "matched_line": f"child emitted {sentinel}",
            "read": {
                "pane_id": pane_id,
                "workspace_id": "w-test",
                "tab_id": "t-test",
                "source": "recent_unwrapped",
                "format": "text",
                "text": f"pre-existing scrollback\n{sentinel}\n",
                "revision": revision,
                "truncated": False,
            },
        },
    }


class _SubscriptionServer:
    """Tiny real Unix-socket peer that closes each accepted stream after its scripted events."""

    def __init__(self, path: Path, connections: Sequence[Sequence[Mapping[str, Any]]]) -> None:
        self.path = path
        self.connections = connections
        self.requests: list[dict[str, Any]] = []
        self._ready = threading.Event()
        self._errors: list[BaseException] = []
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> _SubscriptionServer:
        self._thread.start()
        assert self._ready.wait(2), "fake herdr socket did not start"
        assert not self._errors, f"fake herdr socket failed during startup: {self._errors!r}"
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        self._thread.join(timeout=3)
        assert not self._thread.is_alive(), "fake herdr socket did not finish"
        assert not self._errors, f"fake herdr socket failed: {self._errors!r}"

    def _run(self) -> None:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(self.path))
                server.listen()
                self._ready.set()
                for envelopes in self.connections:
                    connection, _ = server.accept()
                    with connection, connection.makefile("rwb") as stream:
                        request_line = stream.readline()
                        request = json.loads(request_line)
                        self.requests.append(request)
                        response = {
                            "id": request["id"],
                            "result": {"type": "subscription_started"},
                        }
                        stream.write(json.dumps(response).encode() + b"\n")
                        stream.flush()
                        for envelope in envelopes:
                            stream.write(json.dumps(envelope).encode() + b"\n")
                            stream.flush()
                    # Exiting the connection context performs a real peer close mid-stream.
        except BaseException as exc:  # noqa: BLE001
            self._errors.append(exc)
            self._ready.set()
        finally:
            self.path.unlink(missing_ok=True)


def _subscriber(
    tmp_path: Path,
    *,
    diagnostics: list[dict[str, Any]] | None = None,
    wakes: list[str] | None = None,
    snapshot_reader=None,  # noqa: ANN001
) -> Any:
    return SUBSCRIBER.Subscriber(
        root=tmp_path,
        run_id="run-a",
        row_id="subscriber-a",
        pane_id="subscriber-pane",
        orchestrator_pane="orchestrator-pane",
        subscriptions=[{"type": "pane.exited"}],
        client=EVENTS.HerdrEventClient(tmp_path / "unused.sock"),
        snapshot_reader=snapshot_reader,
        wake_sender=(wakes if wakes is not None else []).append,
        diagnostic_sink=(diagnostics if diagnostics is not None else []).append,
    )


def _short_socket_path() -> Path:
    """macOS limits AF_UNIX paths to roughly 104 bytes; pytest's tmp_path can exceed that."""
    return Path("/tmp") / f"orchestrate-u3-{uuid.uuid4().hex}.sock"


# --------------------------------------------------------------------------- scenario 1


def test_subscribe_request_uses_dotted_types_and_validates_against_captured_schema() -> None:
    sentinel = SUBSCRIBER.make_sentinel("run-a", "child-a", "complete", nonce="n1")
    subscriptions = [
        {"type": "tab.closed"},
        {"type": "pane.exited"},
        SUBSCRIBER.output_match_subscription("pane-a", sentinel),
    ]
    request = EVENTS.build_subscribe_request("request-1", subscriptions)

    # The authority is the schema captured from the installed herdr binary, not a second expected
    # dict authored beside the serializer. Removing or misspelling any required field fails here.
    captured = json.loads(SCHEMA.read_text(encoding="utf-8"))
    request_schema = {
        "$schema": captured["$schema"],
        "schemas": captured["schemas"],
        "$ref": "#/schemas/request",
    }
    jsonschema.Draft202012Validator(request_schema).validate(request)
    jsonschema.Draft202012Validator(_schema_ref("EventsSubscribeParams")).validate(
        request["params"]
    )
    for subscription in request["params"]["subscriptions"]:
        jsonschema.Draft202012Validator(_schema_ref("Subscription")).validate(subscription)


# --------------------------------------------------------------------------- scenario 2


def test_underscored_subscribe_type_is_a_hard_error() -> None:
    with pytest.raises(EVENTS.SubscriptionError, match="dotted request types"):
        EVENTS.build_subscribe_request("request-1", [{"type": "pane_exited"}])


# --------------------------------------------------------------------------- scenario 3


def test_malformed_subscription_is_reported_instead_of_silently_dropped() -> None:
    malformed = {
        "type": "pane.output_matched",
        "pane_id": "pane-a",
        "source": "recent_unwrapped",
        # Deliberately no match object.
    }
    with pytest.raises(EVENTS.SubscriptionError, match=r"subscription 1: match must be an object"):
        EVENTS.build_subscribe_request("request-1", [{"type": "tab.closed"}, malformed])


# --------------------------------------------------------------------------- scenario 4


def test_pane_output_matched_regex_decodes_matched_line() -> None:
    sentinel = SUBSCRIBER.make_sentinel("run-a", "child-a", "complete", nonce="n1")
    subscription = SUBSCRIBER.output_match_subscription(
        "pane-a", rf"{sentinel}.*complete", match_type="regex"
    )
    jsonschema.Draft202012Validator(_schema_ref("Subscription")).validate(subscription)

    decoded = EVENTS.decode_event(_output_event("pane-a", sentinel, revision=12))
    assert decoded.matched_line == f"child emitted {sentinel}"
    assert decoded.revision == 12


# --------------------------------------------------------------------------- scenario 5


def test_sentinel_in_pre_dispatch_scrollback_does_not_satisfy_match(tmp_path: Path) -> None:
    sentinel = SUBSCRIBER.make_sentinel("run-a", "child-a", "complete", nonce="old")
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {
            "run_id": "run-a",
            "pane_id": "pane-a",
            "phase": "working",
            "dispatch_revision_baseline": 41,
        },
    )
    diagnostics: list[dict[str, Any]] = []
    wakes: list[str] = []
    subscriber = _subscriber(tmp_path, diagnostics=diagnostics, wakes=wakes)
    socket_path = _short_socket_path()

    # The fake herdr peer searches already-present text and returns the hit at the exact revision
    # sampled before dispatch. This crosses the actual socket/decoder/dispatcher path.
    with _SubscriptionServer(
        socket_path, [[_output_event("pane-a", sentinel, revision=41)]]
    ) as peer:
        EVENTS.HerdrEventClient(socket_path).subscribe_once(
            [SUBSCRIBER.output_match_subscription("pane-a", sentinel)],
            subscriber.handle_event,
        )

    row = REGISTER.read_rows(tmp_path)["child-a"]
    assert "last_event_at" not in row
    assert wakes == []
    assert [item["code"] for item in diagnostics] == ["stale_output_match"]
    assert len(peer.requests) == 1


# --------------------------------------------------------------------------- scenario 6


def test_socket_close_mid_stream_triggers_reconnect_and_catch_up(tmp_path: Path) -> None:
    socket_path = _short_socket_path()
    received: list[str] = []
    catch_ups: list[int] = []
    first = {"event": "tab_closed", "data": {"type": "tab_closed", "tab_id": "t1"}}
    second = {"event": "tab_closed", "data": {"type": "tab_closed", "tab_id": "t2"}}

    with _SubscriptionServer(socket_path, [[first], [second]]) as peer:
        EVENTS.HerdrEventClient(socket_path).run_forever(
            [{"type": "tab.closed"}],
            lambda event: received.append(event.data["tab_id"]),
            lambda: catch_ups.append(len(catch_ups) + 1),
            reconnect_delay=0,
            max_connections=2,
        )

    assert received == ["t1", "t2"]
    assert catch_ups == [1, 2]
    assert len(peer.requests) == 2


# --------------------------------------------------------------------------- scenario 7


def test_child_exit_during_disconnect_is_detected_by_reconnect_catch_up(
    tmp_path: Path,
) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {
            "run_id": "run-a",
            "pane_id": "pane-a",
            "expected_state": "working",
            "observed_state": "working",
        },
    )
    snapshots: list[dict[str, Any]] = [
        {
            "panes": [{"pane_id": "pane-a", "agent_status": "working", "revision": 7}],
            "agents": [{"pane_id": "pane-a", "agent_status": "working", "revision": 7}],
        },
        {"panes": [], "agents": []},
    ]
    snapshot_calls: list[int] = []

    def _next_snapshot() -> Mapping[str, Any]:
        index = len(snapshot_calls)
        snapshot_calls.append(index)
        return snapshots[index]

    wakes: list[str] = []
    subscriber = _subscriber(tmp_path, wakes=wakes, snapshot_reader=_next_snapshot)
    socket_path = _short_socket_path()

    # The first accepted stream closes for real. The child disappears before the reconnect's
    # snapshot, and no pane_exited event is ever sent; only catch-up can discover the loss.
    with _SubscriptionServer(socket_path, [[], []]) as peer:
        EVENTS.HerdrEventClient(socket_path).run_forever(
            [{"type": "pane.exited"}],
            subscriber.handle_event,
            subscriber.run_catch_up,
            reconnect_delay=0,
            max_connections=2,
        )

    assert snapshot_calls == [0, 1]
    assert REGISTER.read_rows(tmp_path)["child-a"]["observed_state"] == "exited"
    assert len(wakes) == 1
    assert "child-a" in wakes[0]
    assert len(peer.requests) == 2


# --------------------------------------------------------------------------- scenario 8


def test_unregistered_pane_event_mutates_no_row_and_reports_once(tmp_path: Path) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "pane_id": "pane-a", "observed_state": "working"},
    )
    before = REGISTER.register_path(tmp_path).read_bytes()
    diagnostics: list[dict[str, Any]] = []
    wakes: list[str] = []
    subscriber = _subscriber(tmp_path, diagnostics=diagnostics, wakes=wakes)
    event = EVENTS.decode_event(
        {
            "event": "pane_exited",
            "data": {"type": "pane_exited", "pane_id": "not-registered", "workspace_id": "w1"},
        }
    )

    subscriber.handle_event(event)
    subscriber.handle_event(event)

    assert REGISTER.register_path(tmp_path).read_bytes() == before
    assert wakes == []
    assert [item["code"] for item in diagnostics] == ["unregistered_pane"]


# --------------------------------------------------------------------------- scenario 9


def test_missing_socket_fails_with_actionable_message(tmp_path: Path) -> None:
    missing = _short_socket_path()
    with pytest.raises(EVENTS.SocketUnavailableError) as error:
        EVENTS.HerdrEventClient(missing).subscribe_once(
            [{"type": "pane.exited"}], lambda event: None
        )
    message = str(error.value)
    assert str(missing) in message
    assert "herdr status server" in message


# --------------------------------------------------------------------------- supporting unit contracts


def test_current_sentinel_revision_updates_liveness_and_wakes(tmp_path: Path) -> None:
    sentinel = SUBSCRIBER.make_sentinel("run-a", "child-a", "ready", nonce="new")
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "pane_id": "pane-a", "dispatch_revision_baseline": 41},
    )
    wakes: list[str] = []
    subscriber = _subscriber(tmp_path, wakes=wakes)

    subscriber.handle_event(EVENTS.decode_event(_output_event("pane-a", sentinel, revision=42)))

    assert isinstance(REGISTER.read_rows(tmp_path)["child-a"]["last_event_at"], float)
    assert len(wakes) == 1
    assert "child-a" in wakes[0]


def test_catch_up_reports_run_bound_artifact_presence(tmp_path: Path) -> None:
    present = tmp_path / "artifacts" / "present.md"
    present.parent.mkdir()
    present.write_text("result", encoding="utf-8")
    REGISTER.upsert_row(
        tmp_path,
        "present",
        {"run_id": "run-a", "pane_id": "p1", "artifact_path": "artifacts/present.md"},
    )
    REGISTER.upsert_row(
        tmp_path,
        "missing",
        {"run_id": "run-a", "pane_id": "p2", "artifact_path": "artifacts/missing.md"},
    )
    snapshot = {
        "panes": [
            {"pane_id": "p1", "agent_status": "working", "revision": 1},
            {"pane_id": "p2", "agent_status": "working", "revision": 1},
        ],
        "agents": [],
    }

    records = {record.row_id: record for record in SUBSCRIBER.catch_up(tmp_path, snapshot)}

    assert records["present"].artifact_exists is True
    assert records["missing"].artifact_exists is False


def test_subscriber_carries_an_ordinary_register_row(tmp_path: Path) -> None:
    subscriber = _subscriber(tmp_path)
    subscriber.register_self()

    row = REGISTER.read_rows(tmp_path)["subscriber-a"]
    assert row["run_id"] == "run-a"
    assert row["agent"] == "subscriber"
    assert row["pane_id"] == "subscriber-pane"
    assert row["expected_state"] == "working"
    assert row["observed_state"] == "working"


def test_subscriber_row_uses_pane_presence_and_records_process_exit(tmp_path: Path) -> None:
    class _StoppingClient:
        def run_forever(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            return

    subscriber = SUBSCRIBER.Subscriber(
        root=tmp_path,
        run_id="run-a",
        row_id="subscriber-a",
        pane_id="subscriber-pane",
        orchestrator_pane="orchestrator-pane",
        subscriptions=[{"type": "pane.exited"}],
        client=_StoppingClient(),
        snapshot_reader=lambda: {
            "panes": [{"pane_id": "subscriber-pane", "agent_status": "unknown", "revision": 1}],
            "agents": [],
        },
        wake_sender=lambda text: None,
        diagnostic_sink=lambda payload: None,
    )
    subscriber.register_self()

    records = SUBSCRIBER.catch_up(tmp_path, subscriber.snapshot_reader(), run_id="run-a")
    assert records[0].observed_state == "working"
    assert records[0].diverged is False

    subscriber.run()
    row = REGISTER.read_rows(tmp_path)["subscriber-a"]
    assert row["expected_state"] == "working"
    assert row["observed_state"] == "exited"
