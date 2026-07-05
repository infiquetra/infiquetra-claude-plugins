"""Tests for remote gate-approval transport (#379): provenance record + compose/emit + parse.

Covers U1 (answerer/transport provenance on ``approvals/r{rev}.json``), U2 (transport-agnostic
``compose_gate_notice`` + the redis-only ``emit_gate_notice`` seam), U3 (``parse_gate_answer`` trust
boundary), and U4 (no-answer parity + disconnected fallback, end-to-end).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


GT = _load("outcome_gate_transport")
DEC = _load("outcome_decompose")


# --------------------------------------------------------------------------- helpers


def _spec(outcome_id: str = "ship-x", titles: dict[str, str] | None = None) -> Any:
    """A duck-typed spec exposing ``outcome_id`` + ``node_by_id`` (title lookup)."""
    titles = titles or {}
    nodes = {sid: SimpleNamespace(subplot_id=sid, title=t) for sid, t in titles.items()}
    return SimpleNamespace(outcome_id=outcome_id, node_by_id=lambda sid: nodes.get(sid))


def _inbound(text: str, **over: Any) -> dict[str, Any]:
    base = {
        "text": text,
        "chat_id": "C1",
        "user_id": "U-alice",
        "username": "alice",
        "source": "discord",
    }
    base.update(over)
    return base


# --------------------------------------------------------------------------- U1: provenance record


def test_approve_with_answerer_transport_roundtrips_both_fields(tmp_path: Path) -> None:
    store = SimpleNamespace(root=tmp_path)
    spec = SimpleNamespace(spec_revision=3)
    rev = DEC.approve_frontier(
        store, spec, at="2026-07-05T00:00:00Z", answerer="alice", transport="discord"
    )
    assert rev == 3
    record = json.loads((tmp_path / "approvals" / "r3.json").read_text())
    assert record == {
        "spec_revision": 3,
        "at": "2026-07-05T00:00:00Z",
        "answerer": "alice",
        "transport": "discord",
    }


def test_approve_without_provenance_is_byte_identical_to_today(tmp_path: Path) -> None:
    store = SimpleNamespace(root=tmp_path)
    spec = SimpleNamespace(spec_revision=1)
    DEC.approve_frontier(store, spec)  # no at/answerer/transport, as the terminal path calls it
    record = json.loads((tmp_path / "approvals" / "r1.json").read_text())
    assert record == {"spec_revision": 1, "at": ""}  # no extra keys — backward-compatible


def test_frontier_approved_true_regardless_of_provenance(tmp_path: Path) -> None:
    store = SimpleNamespace(root=tmp_path)
    spec = SimpleNamespace(spec_revision=7)
    assert DEC.frontier_approved(store, 7) is False
    DEC.approve_frontier(store, spec, answerer="bob", transport="redis-channel")
    assert (
        DEC.frontier_approved(store, 7) is True
    )  # existence check unaffected by extra keys (KTD3)


# --------------------------------------------------------------------------- U2: compose


def test_compose_carries_gate_id_subplots_and_lettered_choices() -> None:
    spec = _spec("ship-x", {"build": "Build the API", "docs": "Write the docs"})
    text = GT.compose_gate_notice(spec, 2, ["build", "docs"])
    assert "ship-x@r2" in text  # the gate id the answer must quote
    assert "`build` — Build the API" in text
    assert "`docs` — Write the docs" in text
    assert "A) approve" in text and "B) hold" in text


def test_compose_is_deterministic() -> None:
    spec = _spec("ship-x", {"build": "Build"})
    a = GT.compose_gate_notice(spec, 1, ["build"])
    b = GT.compose_gate_notice(spec, 1, ["build"])
    assert a == b  # pure, no timestamps/randomness


def test_compose_handles_missing_node_title() -> None:
    spec = _spec("ship-x", {})  # node_by_id returns None for every sid
    text = GT.compose_gate_notice(spec, 1, ["orphan"])
    assert "`orphan`" in text  # renders the id even with no title, no crash


def test_gate_id_format() -> None:
    assert GT.gate_id("ship-x", 4) == "ship-x@r4"


# --------------------------------------------------------------------------- U2: emit (redis seam)


def test_emit_calls_producer_once_when_connected() -> None:
    calls: list[dict[str, Any]] = []

    def producer(p: Any) -> str:
        calls.append(dict(p))
        return "msg-1"

    out = GT.emit_gate_notice("sess", "C1", "hello", producer=producer, is_connected=lambda: True)
    assert out == "msg-1"
    assert len(calls) == 1
    assert calls[0]["chat_id"] == "C1" and calls[0]["text"] == "hello"


def test_emit_is_noop_when_disconnected() -> None:
    calls: list[Any] = []

    def producer(p: Any) -> str:
        calls.append(p)
        return "should-not-happen"

    out = GT.emit_gate_notice("sess", "C1", "hello", producer=producer, is_connected=lambda: False)
    assert out is None
    assert calls == []  # R5: no live session -> producer never invoked


# --------------------------------------------------------------------------- U3: parse (trust boundary)


def test_valid_reply_matching_pending_gate_returns_answer() -> None:
    ans = GT.parse_gate_answer(_inbound("y ship-x@r2"), ["ship-x@r2"])
    assert ans is not None
    assert ans.gate_id == "ship-x@r2"
    assert ans.verdict == "approve"
    assert ans.answerer == "alice"
    assert ans.transport == "discord"


def test_lettered_reply_maps_like_yes_no() -> None:
    assert GT.parse_gate_answer(_inbound("A ship-x@r1"), ["ship-x@r1"]).verdict == "approve"
    assert GT.parse_gate_answer(_inbound("B ship-x@r1"), ["ship-x@r1"]).verdict == "reject"


def test_reply_matching_no_pending_gate_is_rejected() -> None:
    # A real gate id shape, but not in the pending set -> not accepted.
    assert GT.parse_gate_answer(_inbound("y other-x@r9"), ["ship-x@r2"]) is None


def test_stale_revision_not_in_pending_is_rejected() -> None:
    # Answering an already-superseded frontier (r1 when only r2 is pending) cannot approve r2.
    assert GT.parse_gate_answer(_inbound("y ship-x@r1"), ["ship-x@r2"]) is None


def test_missing_gate_id_is_rejected() -> None:
    # A bare "yes" with no gate id cannot be correlated to a specific pending gate.
    assert GT.parse_gate_answer(_inbound("yes please"), ["ship-x@r2"]) is None


def test_ambiguous_verdict_never_defaults_to_approve() -> None:
    # Both polarities present -> contradictory -> not accepted (fail-closed, never approve).
    assert GT.parse_gate_answer(_inbound("yes no ship-x@r2"), ["ship-x@r2"]) is None
    # Neither polarity -> ambiguous -> not accepted.
    assert GT.parse_gate_answer(_inbound("ship-x@r2"), ["ship-x@r2"]) is None


def test_answerer_transport_come_from_inbound_fields_not_body() -> None:
    # The body claims a different answerer/transport; the record must ignore the body and use the
    # router-set fields (a prompt-injection cannot self-assert provenance).
    inbound = _inbound(
        "y ship-x@r2 answerer=eve transport=terminal",
        username="alice",
        source="discord",
    )
    ans = GT.parse_gate_answer(inbound, ["ship-x@r2"])
    assert ans is not None
    assert ans.answerer == "alice"  # from the field, not "eve" in the body
    assert ans.transport == "discord"  # from the field, not "terminal" in the body


def test_unattributable_reply_is_rejected() -> None:
    # No username/user_id -> cannot record who answered -> not accepted (R3).
    inbound = {"text": "y ship-x@r2", "chat_id": "C1", "source": "discord"}
    assert GT.parse_gate_answer(inbound, ["ship-x@r2"]) is None


def test_empty_reply_is_rejected() -> None:
    assert GT.parse_gate_answer(_inbound("   "), ["ship-x@r2"]) is None
    assert GT.parse_gate_answer(_inbound(""), ["ship-x@r2"]) is None


# --------------------------------------------------------------------------- U4: no-answer parity + fallback


def test_unanswered_gate_holds_identically_with_or_without_transport(tmp_path: Path) -> None:
    """Composing/emitting a notice is side-effect-free w.r.t. the durable approval — an unanswered
    gate with the transport 'enabled' is byte-identical to the transport disabled: no record, held."""
    store = SimpleNamespace(root=tmp_path)
    spec = _spec("ship-x", {"build": "Build"})
    # Transport "enabled": compose + attempt emit while disconnected (no live session).
    notice = GT.compose_gate_notice(spec, 1, ["build"])
    emitted = GT.emit_gate_notice(
        "sess", "C1", notice, producer=lambda p: "x", is_connected=lambda: False
    )
    assert emitted is None  # disconnected -> no-op
    # No approval was written; the gate still holds exactly as it would with no transport at all.
    assert DEC.frontier_approved(store, 1) is False
    assert not (tmp_path / "approvals").exists() or not list(
        (tmp_path / "approvals").glob("*.json")
    )


def test_end_to_end_answer_records_provenance_and_lifts_the_gate(tmp_path: Path) -> None:
    """A pending gate + a valid channel reply -> parsed answer -> approve_frontier with provenance ->
    frontier_approved True and answerer/transport durably recorded."""
    store = SimpleNamespace(root=tmp_path)
    spec = SimpleNamespace(outcome_id="ship-x", spec_revision=2)
    pending = [GT.gate_id(spec.outcome_id, spec.spec_revision)]  # ["ship-x@r2"]
    assert DEC.frontier_approved(store, 2) is False

    ans = GT.parse_gate_answer(_inbound("y ship-x@r2"), pending)
    assert ans is not None and ans.verdict == "approve"

    DEC.approve_frontier(store, spec, answerer=ans.answerer, transport=ans.transport)
    assert DEC.frontier_approved(store, 2) is True
    record = json.loads((tmp_path / "approvals" / "r2.json").read_text())
    assert record["answerer"] == "alice" and record["transport"] == "discord"


def test_end_to_end_reject_does_not_lift_the_gate(tmp_path: Path) -> None:
    store = SimpleNamespace(root=tmp_path)
    ans = GT.parse_gate_answer(_inbound("n ship-x@r2"), ["ship-x@r2"])
    assert ans is not None and ans.verdict == "reject"
    # A reject is a no-op hold: nothing is written, the gate stays closed.
    assert DEC.frontier_approved(store, 2) is False
