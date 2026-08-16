"""Herdr event client, tracked subscriber, sentinel identity, and reconnect catch-up tests."""

from __future__ import annotations

import importlib.util
import json
import re
import socket
import subprocess
import sys
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "plugins" / "orchestrate" / "skills" / "orchestrate" / "scripts"
SCHEMA = ROOT / "plugins" / "orchestrate" / "tests" / "fixtures" / "herdr-api-schema.json"
OUTPUT_MATCH_CAPTURE = (
    ROOT / "plugins" / "orchestrate" / "tests" / "fixtures" / "captured-output-matched.json"
)


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


@pytest.fixture(autouse=True)
def _register_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REGISTER.REGISTER_DIR_ENV, str(tmp_path / "registers"))


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

    def __init__(
        self,
        path: Path,
        connections: Sequence[Sequence[Mapping[str, Any]]],
        *,
        request_gate: Callable[[Mapping[str, Any]], bool] | None = None,
    ) -> None:
        self.path = path
        self.connections = connections
        self.requests: list[dict[str, Any]] = []
        self.request_gate = request_gate
        self._ready = threading.Event()
        self._errors: list[BaseException] = []
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> _SubscriptionServer:
        self._thread.start()
        assert self._ready.wait(2), "fake herdr socket did not start"
        assert not self._errors, f"fake herdr socket failed during startup: {self._errors!r}"
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
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
                        response = {"id": request["id"], "result": {"type": "subscription_started"}}
                        stream.write(json.dumps(response).encode() + b"\n")
                        stream.flush()
                        if self.request_gate is None or self.request_gate(request):
                            for envelope in envelopes:
                                stream.write(json.dumps(envelope).encode() + b"\n")
                                stream.flush()
        except BaseException as exc:
            self._errors.append(exc)
            self._ready.set()
        finally:
            self.path.unlink(missing_ok=True)


class _RequestServer:
    """One schema-shaped request/response exchange over a real Unix socket."""

    def __init__(self, path: Path, response: Mapping[str, Any]) -> None:
        self.path = path
        self.response = dict(response)
        self.request: dict[str, Any] | None = None
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> _RequestServer:
        self._thread.start()
        assert self._ready.wait(2), "fake herdr request socket did not start"
        assert self._error is None, f"fake herdr request socket failed: {self._error!r}"
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._thread.join(timeout=3)
        assert not self._thread.is_alive(), "fake herdr request socket did not finish"
        assert self._error is None, f"fake herdr request socket failed: {self._error!r}"

    def _run(self) -> None:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(self.path))
                server.listen()
                self._ready.set()
                connection, _ = server.accept()
                with connection, connection.makefile("rwb") as stream:
                    self.request = json.loads(stream.readline())
                    stream.write(json.dumps(self.response).encode() + b"\n")
                    stream.flush()
        except BaseException as exc:
            self._error = exc
            self._ready.set()
        finally:
            self.path.unlink(missing_ok=True)


def _subscriber(
    tmp_path: Path,
    *,
    diagnostics: list[dict[str, Any]] | None = None,
    wakes: list[str] | None = None,
    snapshot_reader=None,
    subscriptions: Sequence[Mapping[str, Any]] | None = None,
    client=None,
) -> Any:
    return SUBSCRIBER.Subscriber(
        root=tmp_path,
        run_id="run-a",
        row_id="subscriber-a",
        pane_id="subscriber-pane",
        orchestrator_pane="orchestrator-pane",
        subscriptions=subscriptions or [{"type": "pane.exited"}],
        client=client or EVENTS.HerdrEventClient(tmp_path / "unused.sock"),
        snapshot_reader=snapshot_reader,
        wake_sender=(wakes if wakes is not None else []).append,
        diagnostic_sink=(diagnostics if diagnostics is not None else []).append,
    )


def _short_socket_path() -> Path:
    """macOS limits AF_UNIX paths to roughly 104 bytes; pytest's tmp_path can exceed that."""
    return Path("/tmp") / f"orchestrate-u3-{uuid.uuid4().hex}.sock"


def _session_snapshot_response(*, tabs=None, panes=None, agents=None) -> dict[str, Any]:
    return {
        "id": "orchestrate-snapshot",
        "result": {
            "type": "session_snapshot",
            "snapshot": {
                "version": "0.8.0",
                "protocol": 19,
                "workspaces": [],
                "tabs": tabs or [],
                "panes": panes or [],
                "layouts": [],
                "agents": agents or [],
            },
        },
    }


def _live_snapshot(
    *sessions: tuple[str, str, str, int, str], run_id: str = "run-a"
) -> dict[str, Any]:
    """Build a complete snapshot from row, pane, status, revision, and tab tuples."""
    tabs: list[dict[str, Any]] = []
    panes: list[dict[str, Any]] = []
    agents: list[dict[str, Any]] = []
    for row_id, pane_id, status, revision, tab_id in sessions:
        tabs.append(
            {
                "label": f"orchestrate-{run_id}-{row_id}",
                "tab_id": tab_id,
                "workspace_id": "workspace-a",
                "agent_status": status,
            }
        )
        pane = {
            "pane_id": pane_id,
            "tab_id": tab_id,
            "workspace_id": "workspace-a",
            "agent_status": status,
            "revision": revision,
        }
        panes.append(pane)
        agents.append(dict(pane))
    return {"tabs": tabs, "panes": panes, "agents": agents}


class _RequestClient:
    def __init__(self, result: Mapping[str, Any]) -> None:
        self.result = dict(result)
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, request_id: str, method: str, params: Mapping[str, Any]) -> dict[str, Any]:
        self.requests.append((request_id, method, dict(params)))
        return dict(self.result)


def test_subscribe_request_uses_dotted_types_and_validates_against_captured_schema() -> None:
    sentinel = SUBSCRIBER.make_sentinel("run-a", "child-a", "complete", nonce="n1")
    subscriptions = [
        {"type": "tab.closed"},
        {"type": "pane.exited"},
        SUBSCRIBER.output_match_subscription("pane-a", sentinel),
    ]
    request = EVENTS.build_subscribe_request("request-1", subscriptions)
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


def test_underscored_subscribe_type_is_a_hard_error() -> None:
    with pytest.raises(EVENTS.SubscriptionError, match="dotted request types"):
        EVENTS.build_subscribe_request("request-1", [{"type": "pane_exited"}])


def test_malformed_subscription_is_reported_instead_of_silently_dropped() -> None:
    malformed = {"type": "pane.output_matched", "pane_id": "pane-a", "source": "recent_unwrapped"}
    with pytest.raises(EVENTS.SubscriptionError, match="subscription 1: match must be an object"):
        EVENTS.build_subscribe_request("request-1", [{"type": "tab.closed"}, malformed])


def test_pane_output_matched_regex_decodes_matched_line() -> None:
    matched_line = "READY-42"
    pattern = "^READY-[0-9]+$"
    subscription = {
        "type": "pane.output_matched",
        "pane_id": "pane-a",
        "source": "recent_unwrapped",
        "match": {"type": "regex", "value": pattern},
    }
    jsonschema.Draft202012Validator(_schema_ref("Subscription")).validate(subscription)
    event = _output_event("pane-a", matched_line, revision=12)
    event["data"]["matched_line"] = matched_line
    received: list[Any] = []
    socket_path = _short_socket_path()

    def _regex_gate(request: Mapping[str, Any]) -> bool:
        sent = request["params"]["subscriptions"][0]["match"]
        assert sent["type"] == "regex"
        return (
            re.search(sent["value"], matched_line) is not None and sent["value"] not in matched_line
        )

    with _SubscriptionServer(socket_path, [[event]], request_gate=_regex_gate):
        EVENTS.HerdrEventClient(socket_path).subscribe_once([subscription], received.append)
    assert len(received) == 1
    assert received[0].matched_line == matched_line
    assert received[0].revision == 12


@pytest.mark.parametrize(
    ("match", "message"),
    [
        (
            {
                "type": "regex",
                "value": SUBSCRIBER.make_sentinel("run-a", "child-a", "complete", nonce="regex"),
            },
            "substring sentinel",
        ),
        ({"type": "substring", "value": "Ready."}, "complete orchestrate sentinel"),
    ],
)
def test_subscriber_rejects_output_matches_it_cannot_represent(
    tmp_path: Path, match: Mapping[str, Any], message: str
) -> None:
    subscription = {
        "type": "pane.output_matched",
        "pane_id": "pane-a",
        "source": "recent_unwrapped",
        "match": dict(match),
    }
    with pytest.raises(EVENTS.SubscriptionError, match=message):
        _subscriber(tmp_path, subscriptions=[subscription])


def test_live_zero_revision_output_match_is_honoured_by_identity(tmp_path: Path) -> None:
    sentinel = SUBSCRIBER.make_sentinel("run-a", "child-a", "complete", nonce="live-zero")
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "working"},
        run_id="run-a",
        writer="write_phase",
    )
    diagnostics: list[dict[str, Any]] = []
    wakes: list[str] = []
    subscription = SUBSCRIBER.output_match_subscription("pane-a", sentinel)
    subscriber = _subscriber(
        tmp_path, diagnostics=diagnostics, wakes=wakes, subscriptions=[subscription]
    )
    socket_path = _short_socket_path()
    with _SubscriptionServer(
        socket_path, [[_output_event("pane-a", sentinel, revision=0)]]
    ) as peer:
        EVENTS.HerdrEventClient(socket_path).subscribe_once([subscription], subscriber.handle_event)
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    assert isinstance(row["last_event_at"], float)
    assert len(wakes) == 1
    assert diagnostics == []
    assert len(peer.requests) == 1


def test_pre_dispatch_prompt_echo_cannot_satisfy_sentinel_match(tmp_path: Path) -> None:
    sentinel = SUBSCRIBER.make_sentinel("run-a", "child-a", "complete", nonce="echo-safe")
    prompt = SUBSCRIBER.sentinel_assembly_instructions(
        sentinel, when="the completion predicate has passed"
    )
    assert sentinel not in prompt
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "working"},
        run_id="run-a",
        writer="write_phase",
    )
    diagnostics: list[dict[str, Any]] = []
    wakes: list[str] = []
    subscription = SUBSCRIBER.output_match_subscription("pane-a", sentinel)
    subscriber = _subscriber(
        tmp_path, diagnostics=diagnostics, wakes=wakes, subscriptions=[subscription]
    )
    envelope = _output_event("pane-a", sentinel, revision=0)
    envelope["data"]["matched_line"] = prompt
    envelope["data"]["read"]["text"] = prompt
    socket_path = _short_socket_path()
    with _SubscriptionServer(socket_path, [[envelope]]):
        EVENTS.HerdrEventClient(socket_path).subscribe_once([subscription], subscriber.handle_event)
    assert wakes == []
    assert [item["code"] for item in diagnostics] == ["sentinel_mismatch"]
    assert "last_event_at" not in REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]


def test_live_output_match_capture_validates_and_decodes_zero_revision() -> None:
    captured = json.loads(OUTPUT_MATCH_CAPTURE.read_text(encoding="utf-8"))
    assert isinstance(captured, list) and len(captured) == 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    envelope_schema = {
        "$schema": schema["$schema"],
        "schemas": schema["schemas"],
        "$ref": "#/schemas/subscription_event",
    }
    jsonschema.Draft202012Validator(envelope_schema).validate(captured[0])
    event = EVENTS.decode_event(captured[0])
    assert event.name == "pane.output_matched"
    assert event.revision == 0
    assert captured[0]["data"]["read"]["text"] == "captured pane output\nmatched substring\n"
    assert "dispatch_revision_baseline" not in captured[0]["data"]["read"]["text"]


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


def test_catch_up_failure_is_reported_while_events_continue_and_connections_are_bounded() -> None:
    socket_path = _short_socket_path()
    received: list[str] = []
    diagnostics: list[str] = []
    catch_up_calls: list[int] = []
    first = {"event": "tab_closed", "data": {"type": "tab_closed", "tab_id": "t1"}}
    second = {"event": "tab_closed", "data": {"type": "tab_closed", "tab_id": "t2"}}

    def _broken_catch_up() -> None:
        catch_up_calls.append(len(catch_up_calls) + 1)
        raise EVENTS.ProtocolError("unsupported snapshot shape")

    with _SubscriptionServer(socket_path, [[first], [second]]) as peer:
        EVENTS.HerdrEventClient(socket_path).run_forever(
            [{"type": "tab.closed"}],
            lambda event: received.append(event.data["tab_id"]),
            _broken_catch_up,
            reconnect_delay=0,
            max_connections=2,
            diagnostic=diagnostics.append,
        )
    assert received == ["t1", "t2"]
    assert catch_up_calls == [1, 2]
    assert diagnostics == [
        "catch-up failed after subscription was accepted: unsupported snapshot shape",
        "catch-up failed after subscription was accepted: unsupported snapshot shape",
    ]
    assert [request["id"] for request in peer.requests] == [
        "orchestrate-subscribe-1",
        "orchestrate-subscribe-2",
    ]


def test_child_exit_during_disconnect_is_detected_by_reconnect_catch_up(tmp_path: Path) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "expected_state": "working", "phase": "working"},
        run_id="run-a",
        writer="write_phase",
    )
    snapshots: list[dict[str, Any]] = [
        _live_snapshot(("child-a", "pane-a", "working", 7, "tab-a")),
        {"tabs": [], "panes": [], "agents": []},
    ]
    snapshot_calls: list[int] = []

    def _next_snapshot() -> Mapping[str, Any]:
        index = len(snapshot_calls)
        snapshot_calls.append(index)
        return snapshots[index]

    wakes: list[str] = []
    subscriber = _subscriber(tmp_path, wakes=wakes, snapshot_reader=_next_snapshot)
    socket_path = _short_socket_path()
    with _SubscriptionServer(socket_path, [[], []]) as peer:
        EVENTS.HerdrEventClient(socket_path).run_forever(
            [{"type": "pane.exited"}],
            subscriber.handle_event,
            subscriber.run_catch_up,
            reconnect_delay=0,
            max_connections=2,
        )
    assert snapshot_calls == [0, 1]
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)
    assert len(wakes) == 1
    assert "child-a" in wakes[0]
    assert len(peer.requests) == 2


def test_unregistered_pane_event_mutates_no_row_and_reports_once(tmp_path: Path) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "working"},
        run_id="run-a",
        writer="write_phase",
    )
    before = REGISTER.register_path("run-a").read_bytes()
    diagnostics: list[dict[str, Any]] = []
    wakes: list[str] = []
    subscriber = _subscriber(
        tmp_path,
        diagnostics=diagnostics,
        wakes=wakes,
        snapshot_reader=lambda: _live_snapshot(("child-a", "pane-a", "working", 1, "tab-a")),
    )
    event = EVENTS.decode_event(
        {
            "event": "pane_exited",
            "data": {"type": "pane_exited", "pane_id": "not-registered", "workspace_id": "w1"},
        }
    )
    subscriber.handle_event(event)
    subscriber.handle_event(event)
    assert REGISTER.register_path("run-a").read_bytes() == before
    assert wakes == []
    assert [item["code"] for item in diagnostics] == ["unregistered_pane"]


def test_missing_socket_fails_with_actionable_message(tmp_path: Path) -> None:
    missing = _short_socket_path()
    with pytest.raises(EVENTS.SocketUnavailableError) as error:
        EVENTS.HerdrEventClient(missing).subscribe_once(
            [{"type": "pane.exited"}], lambda event: None
        )
    message = str(error.value)
    assert str(missing) in message
    assert "herdr status server" in message


def test_session_snapshot_response_validates_against_fixture_and_is_unwrapped(
    tmp_path: Path,
) -> None:
    pane = {
        "pane_id": "pane-a",
        "terminal_id": "terminal-a",
        "workspace_id": "workspace-a",
        "tab_id": "tab-a",
        "focused": False,
        "agent_status": "working",
        "revision": 8,
    }
    agent = {**pane, "agent_status": "done", "revision": 9}
    tab = {
        "tab_id": "tab-a",
        "workspace_id": "workspace-a",
        "number": 1,
        "label": "orchestrate-run-a-child-a",
        "focused": False,
        "pane_count": 1,
        "agent_status": "done",
    }
    response = _session_snapshot_response(tabs=[tab], panes=[pane], agents=[agent])
    captured = json.loads(SCHEMA.read_text(encoding="utf-8"))
    response_schema = {
        "$schema": captured["$schema"],
        "schemas": captured["schemas"],
        "$ref": "#/schemas/success_response",
    }
    jsonschema.Draft202012Validator(response_schema).validate(response)
    socket_path = _short_socket_path()
    client = EVENTS.HerdrEventClient(socket_path)
    subscriber = _subscriber(tmp_path, client=client)
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "expected_state": "done"},
        run_id="run-a",
    )
    with _RequestServer(socket_path, response) as server:
        snapshot = subscriber._read_snapshot()
    assert snapshot == response["result"]["snapshot"]
    assert server.request == {
        "id": "orchestrate-snapshot",
        "method": "session.snapshot",
        "params": {},
    }
    records = SUBSCRIBER.catch_up(tmp_path, snapshot, run_id="run-a")
    assert records[0].observed_state == "done"
    assert records[0].revision == 9


def test_session_snapshot_response_without_snapshot_is_a_protocol_error(tmp_path: Path) -> None:
    subscriber = _subscriber(tmp_path, client=_RequestClient({"type": "session_snapshot"}))
    with pytest.raises(EVENTS.ProtocolError, match="result\\.snapshot"):
        subscriber._read_snapshot()


def test_run_forever_fails_fast_on_first_missing_socket(tmp_path: Path) -> None:
    stop = threading.Event()

    def _record_first_error(message: str) -> None:
        assert "herdr status server" in message
        stop.set()

    with pytest.raises(EVENTS.SocketUnavailableError):
        EVENTS.HerdrEventClient(_short_socket_path()).run_forever(
            [{"type": "pane.exited"}],
            lambda event: None,
            lambda: None,
            reconnect_delay=0,
            stop_event=stop,
            diagnostic=_record_first_error,
        )


def test_main_returns_nonzero_and_registers_exit_when_socket_start_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:

    def _fail_start(self, *args, **kwargs) -> None:
        raise EVENTS.SocketUnavailableError("cannot open repair-test socket")

    monkeypatch.setattr(EVENTS.HerdrEventClient, "run_forever", _fail_start)
    result = SUBSCRIBER.main(
        [
            "--root",
            str(tmp_path),
            "--run-id",
            "run-a",
            "--row-id",
            "subscriber-a",
            "--pane-id",
            "subscriber-pane",
            "--orchestrator-pane",
            "orchestrator-pane",
            "--socket",
            str(_short_socket_path()),
            "--subscriptions-json",
            '[{"type":"pane.exited"}]',
        ]
    )
    assert result == 1
    assert "error: cannot open repair-test socket" in capsys.readouterr().err
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["subscriber-a"]
    assert row["expected_state"] == "working"
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)


def test_identity_matched_sentinel_updates_liveness_and_wakes(tmp_path: Path) -> None:
    sentinel = SUBSCRIBER.make_sentinel("run-a", "child-a", "ready", nonce="new")
    REGISTER.upsert_row(tmp_path, "child-a", {"run_id": "run-a"}, run_id="run-a")
    wakes: list[str] = []
    subscriber = _subscriber(
        tmp_path,
        wakes=wakes,
        subscriptions=[SUBSCRIBER.output_match_subscription("pane-a", sentinel)],
    )
    subscriber.handle_event(EVENTS.decode_event(_output_event("pane-a", sentinel, revision=42)))
    assert isinstance(
        REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]["last_event_at"], float
    )
    assert len(wakes) == 1
    assert "child-a" in wakes[0]


def test_multiple_sentinel_interactions_for_one_pane_are_each_honoured(tmp_path: Path) -> None:
    ready = SUBSCRIBER.make_sentinel("run-a", "child-a", "ready", nonce="ready")
    complete = SUBSCRIBER.make_sentinel("run-a", "child-a", "complete", nonce="complete")
    REGISTER.upsert_row(tmp_path, "child-a", {"run_id": "run-a"}, run_id="run-a")
    wakes: list[str] = []
    subscriber = _subscriber(
        tmp_path,
        wakes=wakes,
        subscriptions=[
            SUBSCRIBER.output_match_subscription("pane-a", ready),
            SUBSCRIBER.output_match_subscription("pane-a", complete),
        ],
    )
    subscriber.handle_event(EVENTS.decode_event(_output_event("pane-a", ready, revision=11)))
    subscriber.handle_event(EVENTS.decode_event(_output_event("pane-a", complete, revision=12)))
    assert len(wakes) == 2


def test_registered_pane_exited_event_wakes_without_copying_exit_state(tmp_path: Path) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "working"},
        run_id="run-a",
        writer="write_phase",
    )
    wakes: list[str] = []
    subscriber = _subscriber(
        tmp_path,
        wakes=wakes,
        snapshot_reader=lambda: _live_snapshot(("child-a", "pane-a", "exited", 1, "tab-a")),
    )
    event = EVENTS.decode_event(
        {
            "event": "pane_exited",
            "data": {"type": "pane_exited", "pane_id": "pane-a", "workspace_id": "w1"},
        }
    )
    subscriber.handle_event(event)
    assert len(wakes) == 1
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)


def test_registered_pane_closed_event_wakes_without_copying_exit_state(tmp_path: Path) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "working"},
        run_id="run-a",
        writer="write_phase",
    )
    wakes: list[str] = []
    subscriber = _subscriber(
        tmp_path,
        wakes=wakes,
        snapshot_reader=lambda: _live_snapshot(("child-a", "pane-a", "exited", 1, "tab-a")),
    )
    event = EVENTS.decode_event(
        {
            "event": "pane_closed",
            "data": {"type": "pane_closed", "pane_id": "pane-a", "workspace_id": "w1"},
        }
    )
    subscriber.handle_event(event)
    assert len(wakes) == 1
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(
        REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    )


def test_registered_tab_closed_events_resolve_rows_without_copying_exit_state(
    tmp_path: Path,
) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "working"},
        run_id="run-a",
        writer="write_phase",
    )
    wakes: list[str] = []
    diagnostics: list[dict[str, Any]] = []
    subscriber = _subscriber(
        tmp_path,
        diagnostics=diagnostics,
        wakes=wakes,
        snapshot_reader=lambda: _live_snapshot(("child-a", "pane-a", "exited", 1, "tab-a")),
    )
    event = EVENTS.decode_event(
        {
            "event": "tab_closed",
            "data": {"type": "tab_closed", "tab_id": "tab-a", "workspace_id": "w1"},
        }
    )
    subscriber.handle_event(event)
    subscriber.handle_event(event)
    assert len(wakes) == 2
    assert diagnostics == []
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(
        REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    )


def test_registered_non_state_event_does_not_send_an_empty_wake(tmp_path: Path) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "working"},
        run_id="run-a",
        writer="write_phase",
    )
    before = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    wakes: list[str] = []
    subscriber = _subscriber(
        tmp_path,
        wakes=wakes,
        snapshot_reader=lambda: _live_snapshot(("child-a", "pane-a", "working", 1, "tab-a")),
    )
    event = EVENTS.decode_event(
        {
            "event": "pane_updated",
            "data": {"type": "pane_updated", "pane_id": "pane-a", "workspace_id": "w1"},
        }
    )
    subscriber.handle_event(event)
    assert REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"] == before
    assert wakes == []


def test_sentinel_identity_mismatch_rejects_event_before_liveness_update(tmp_path: Path) -> None:
    expected = SUBSCRIBER.make_sentinel("run-a", "child-a", "complete", nonce="expected")
    wrong_run = SUBSCRIBER.make_sentinel("run-b", "child-a", "complete", nonce="expected")
    REGISTER.upsert_row(tmp_path, "child-a", {"run_id": "run-a"}, run_id="run-a")
    diagnostics: list[dict[str, Any]] = []
    wakes: list[str] = []
    subscriber = _subscriber(
        tmp_path,
        diagnostics=diagnostics,
        wakes=wakes,
        subscriptions=[SUBSCRIBER.output_match_subscription("pane-a", expected)],
    )
    subscriber.handle_event(EVENTS.decode_event(_output_event("pane-a", wrong_run, revision=5)))
    assert [item["code"] for item in diagnostics] == ["sentinel_mismatch"]
    assert "last_event_at" not in REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    assert wakes == []


def test_output_match_needs_no_cross_counter_revision_baseline(tmp_path: Path) -> None:
    sentinel = SUBSCRIBER.make_sentinel("run-a", "child-a", "complete", nonce="expected")
    REGISTER.upsert_row(tmp_path, "child-a", {"run_id": "run-a"}, run_id="run-a")
    diagnostics: list[dict[str, Any]] = []
    wakes: list[str] = []
    subscriber = _subscriber(
        tmp_path,
        diagnostics=diagnostics,
        wakes=wakes,
        subscriptions=[SUBSCRIBER.output_match_subscription("pane-a", sentinel)],
    )
    subscriber.handle_event(EVENTS.decode_event(_output_event("pane-a", sentinel, revision=5)))
    assert diagnostics == []
    assert isinstance(
        REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]["last_event_at"], float
    )
    assert len(wakes) == 1


@pytest.mark.parametrize(
    ("purpose", "nonce"), [("ready", "expected"), ("complete", "earlier-dispatch")]
)
def test_output_match_requires_active_purpose_and_nonce(
    tmp_path: Path, purpose: str, nonce: str
) -> None:
    expected = SUBSCRIBER.make_sentinel("run-a", "child-a", "complete", nonce="expected")
    wrong = SUBSCRIBER.make_sentinel("run-a", "child-a", purpose, nonce=nonce)
    REGISTER.upsert_row(tmp_path, "child-a", {"run_id": "run-a"}, run_id="run-a")
    diagnostics: list[dict[str, Any]] = []
    wakes: list[str] = []
    subscriber = _subscriber(
        tmp_path,
        diagnostics=diagnostics,
        wakes=wakes,
        subscriptions=[SUBSCRIBER.output_match_subscription("pane-a", expected)],
    )
    subscriber.handle_event(EVENTS.decode_event(_output_event("pane-a", wrong, revision=5)))
    assert [item["code"] for item in diagnostics] == ["sentinel_mismatch"]
    assert "last_event_at" not in REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    assert wakes == []


def test_catch_up_reports_run_bound_artifact_presence(tmp_path: Path) -> None:
    present = tmp_path / "artifacts" / "present.md"
    present.parent.mkdir()
    present.write_text("result", encoding="utf-8")
    REGISTER.upsert_row(
        tmp_path,
        "present",
        {"run_id": "run-a", "artifact_path": "artifacts/present.md"},
        run_id="run-a",
        writer=REGISTER.ARTIFACT_PATH_WRITER,
    )
    REGISTER.upsert_row(
        tmp_path,
        "missing",
        {"run_id": "run-a", "artifact_path": "artifacts/missing.md"},
        run_id="run-a",
        writer=REGISTER.ARTIFACT_PATH_WRITER,
    )
    snapshot = _live_snapshot(
        ("present", "p1", "working", 1, "tab-present"),
        ("missing", "p2", "working", 1, "tab-missing"),
    )
    records = {
        record.row_id: record for record in SUBSCRIBER.catch_up(tmp_path, snapshot, run_id="run-a")
    }
    assert records["present"].artifact_exists is True
    assert records["missing"].artifact_exists is False


def test_catch_up_keeps_observations_out_of_the_register(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for row_id in ("child-a", "child-b"):
        REGISTER.upsert_row(tmp_path, row_id, {"run_id": "run-a"}, run_id="run-a")
    snapshot = _live_snapshot(
        ("child-a", "pane-a", "working", 1, "tab-a"),
        ("child-b", "pane-b", "blocked", 2, "tab-b"),
    )
    real_upsert_rows = REGISTER.upsert_rows
    batches: list[dict[str, dict[str, Any]]] = []

    def _record_batch(
        root: Path,
        updates: Mapping[str, Mapping[str, Any]],
        *,
        run_id: str,
        writer: str = "",
        **_kwargs: Any,
    ):
        batches.append({row_id: dict(fields) for row_id, fields in updates.items()})
        return real_upsert_rows(root, updates, run_id=run_id, writer=writer)

    monkeypatch.setattr(SUBSCRIBER.register_store, "upsert_rows", _record_batch)
    records = {
        record.row_id: record for record in SUBSCRIBER.catch_up(tmp_path, snapshot, run_id="run-a")
    }
    assert batches == []
    on_disk = json.loads(REGISTER.register_path("run-a").read_text(encoding="utf-8"))
    assert "observed_state" not in on_disk["rows"]["child-a"]
    assert "observed_state_source" not in on_disk["rows"]["child-b"]
    assert records["child-a"].observed_state == "working"
    assert records["child-b"].observed_state == "blocked"


def test_catch_up_refuses_a_directory_that_is_not_the_runs_work_location(tmp_path: Path) -> None:
    REGISTER.upsert_row(tmp_path, "child-a", {"run_id": "run-a"}, run_id="run-a")
    other = tmp_path / "other"
    other.mkdir()
    snapshot = _live_snapshot(("child-a", "pane-a", "exited", 1, "tab-a"))
    with pytest.raises(REGISTER.RegisterError, match="bound to"):
        SUBSCRIBER.catch_up(other, snapshot, run_id="run-a")
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(
        REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    )


def test_the_subscriber_command_refuses_a_disagreeing_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    REGISTER.upsert_row(tmp_path, "child-a", {"run_id": "run-a"}, run_id="run-a")
    other = tmp_path / "other"
    other.mkdir()
    ran: list[str] = []
    monkeypatch.setattr(SUBSCRIBER.Subscriber, "run", lambda self: ran.append("ran"))
    rc = SUBSCRIBER.main(
        [
            "--root",
            str(other),
            "--run-id",
            "run-a",
            "--row-id",
            "sub-a",
            "--pane-id",
            "pane-a",
            "--orchestrator-pane",
            "orch",
            "--subscriptions-json",
            '[{"type":"pane.exited"}]',
        ]
    )
    assert rc == 1
    assert ran == []
    assert "bound to" in capsys.readouterr().err


def test_the_subscriber_command_accepts_a_package_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The documented `--root "$PWD"` from a package subdirectory names the repository."""
    repo = tmp_path / "repo"
    package = repo / "packages" / "tool"
    package.mkdir(parents=True)
    _git_init(repo)
    REGISTER.upsert_row(repo, "child-a", {"run_id": "run-a"}, run_id="run-a")
    seen: list[Path] = []

    def _run(self: Any) -> None:
        seen.append(Path(self.root))

    monkeypatch.setattr(SUBSCRIBER.Subscriber, "run", _run)
    rc = SUBSCRIBER.main(
        [
            "--root",
            str(package),
            "--run-id",
            "run-a",
            "--row-id",
            "sub-a",
            "--pane-id",
            "pane-a",
            "--orchestrator-pane",
            "orch",
            "--subscriptions-json",
            '[{"type":"pane.exited"}]',
        ]
    )
    assert rc == 0
    assert seen == [repo.resolve()]


def test_catch_up_refuses_a_nonempty_unbound_register(tmp_path: Path) -> None:
    path = REGISTER.register_path("run-a")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-a",
                "rows": {
                    "child-a": {
                        "id": "child-a",
                        "run_id": "run-a",
                        "pane_id": "pane-a",
                        "observed_state": "working",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    snapshot = _live_snapshot(("child-a", "pane-a", "exited", 1, "tab-a"))
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(REGISTER.RegisterError, match="no recorded or stamped"):
        SUBSCRIBER.catch_up(empty, snapshot, run_id="run-a")
    assert json.loads(path.read_text())["rows"]["child-a"]["observed_state"] == "working"


def _git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "tests@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Tests"], cwd=repo, check=True)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)


def test_catch_up_for_one_run_does_not_write_another_runs_row(tmp_path: Path) -> None:
    """A catch-up that names run B must not mutate run A, even when they share a row id."""
    REGISTER.upsert_row(tmp_path, "child-a", {"run_id": "run-a"}, run_id="run-a")
    REGISTER.upsert_row(tmp_path, "child-a", {"run_id": "run-b"}, run_id="run-b")
    before_a = REGISTER.register_path("run-a").read_bytes()
    snapshot = _live_snapshot(("child-a", "pane-b", "exited", 1, "tab-b"), run_id="run-b")
    records = SUBSCRIBER.catch_up(tmp_path, snapshot, run_id="run-b")
    assert records[0].observed_state == "exited"
    assert REGISTER.register_path("run-a").read_bytes() == before_a
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(
        REGISTER.read_rows(tmp_path, run_id="run-b")["child-a"]
    )


def test_once_diagnostic_resets_after_reconnect_catch_up(tmp_path: Path) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "working"},
        run_id="run-a",
        writer="write_phase",
    )
    diagnostics: list[dict[str, Any]] = []
    subscriber = _subscriber(
        tmp_path,
        diagnostics=diagnostics,
        snapshot_reader=lambda: _live_snapshot(("child-a", "pane-a", "working", 1, "tab-a")),
    )
    event = EVENTS.decode_event(
        {
            "event": "pane_exited",
            "data": {"type": "pane_exited", "pane_id": "unknown-pane", "workspace_id": "w1"},
        }
    )
    subscriber.handle_event(event)
    subscriber.handle_event(event)
    subscriber.run_catch_up()
    subscriber.handle_event(event)
    assert [item["code"] for item in diagnostics] == ["unregistered_pane", "unregistered_pane"]


def test_subscriber_carries_an_ordinary_register_row(tmp_path: Path) -> None:
    subscriber = _subscriber(tmp_path)
    subscriber.register_self()
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["subscriber-a"]
    assert row["run_id"] == "run-a"
    assert row["agent"] == "subscriber"
    assert row["role"] == "subscriber"
    assert row["expected_state"] == "working"
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)


def test_subscriber_row_uses_pane_presence_and_records_process_exit(tmp_path: Path) -> None:

    class _StoppingClient:
        def run_forever(self, *args, **kwargs) -> None:
            return

    subscriber = SUBSCRIBER.Subscriber(
        root=tmp_path,
        run_id="run-a",
        row_id="subscriber-a",
        pane_id="subscriber-pane",
        orchestrator_pane="orchestrator-pane",
        subscriptions=[{"type": "pane.exited"}],
        client=_StoppingClient(),
        snapshot_reader=lambda: _live_snapshot(
            ("subscriber-a", "subscriber-pane", "unknown", 1, "subscriber-tab")
        ),
        wake_sender=lambda text: None,
        diagnostic_sink=lambda payload: None,
    )
    subscriber.register_self()
    records = SUBSCRIBER.catch_up(tmp_path, subscriber.snapshot_reader(), run_id="run-a")
    assert records[0].observed_state == "working"
    assert records[0].diverged is False
    subscriber.run()
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["subscriber-a"]
    assert row["expected_state"] == "working"
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)
