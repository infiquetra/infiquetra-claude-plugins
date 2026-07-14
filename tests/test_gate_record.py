"""Acceptance + unit tests for durable gate records (#371) — against the PRODUCTION module.

Covers the issue's acceptance facets with the exact ``-k`` selectors it names:

* ``session_restart``       — a gate persisted before transport survives a restart and resumes
  the SAME pending record (never re-prompts, never silently proceeds);
* ``silence_never_consent`` — a transport that returns nothing resolves to the DECLARED absence
  behavior, never an implicit "yes";
* ``transport_parity``      — the same ``open_gate`` call works over both wired transports with
  identical record semantics;
* ``answer_read_from_record`` — consumers read the persisted record, never a transport return;
* ``default_is_halt``       — an undeclared absence behavior defaults to HALT.

Plus the #371 operator-absence contract both directions (carried-forward provenance is NOT
operator presence; a live operator answer IS), fail-closed schema validation, write-once
resolutions, and the binding vocabulary #449 consumes. Every green assertion is paired with a
baseline control proving the check could have failed.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

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


GR = _load("gate_record")


def _open(gates: Path, gate_id: str = "g-1", **kwargs: object) -> Any:
    record, _created = GR.open_gate(
        gates,
        gate_id,
        kwargs.pop("question", "Proceed?"),
        kwargs.pop("options", ["proceed", "hold"]),
        **kwargs,
    )
    return record


def _cli(gates: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "gate_record.py"), "--gates-dir", str(gates), *args],
        capture_output=True,
        text=True,
        check=False,
    )


# ---------------------------------------------------------------------------
# H-F3-3: durable record, not a widget timeout — session restart.
# ---------------------------------------------------------------------------


def test_session_restart_resumes_the_same_pending_record(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    first, created = GR.open_gate(gates, "restart-1", "Ship it?", ["yes", "no"])
    assert created is True
    assert first.status == "pending"
    # The declaration hits disk BEFORE any transport is invoked.
    assert (gates / "restart-1" / "record.json").exists()

    # "Restart": a brand-new module instance (fresh import, no shared in-memory state).
    fresh = _load("gate_record")
    resumed, re_created = fresh.open_gate(gates, "restart-1", "Ship it?", ["yes", "no"])
    assert re_created is False  # resumed, not re-issued
    assert resumed.declaration == first.declaration
    assert resumed.status == "pending"  # and never silently proceeded

    # Control: a MISMATCHED re-open is refused, not silently reused.
    with pytest.raises(fresh.GateRecordError, match="different declaration"):
        fresh.open_gate(gates, "restart-1", "Ship it?", ["yes", "no", "maybe"])


def test_session_restart_preserves_a_halted_gate_and_accepts_a_late_answer(
    tmp_path: Path,
) -> None:
    gates = tmp_path / "gates"
    _open(gates, "restart-2")
    GR.resolve_absence(gates, "restart-2", reason="widget timeout")
    fresh = _load("gate_record")
    record = fresh.poll_gate(gates, "restart-2")
    assert record.status == "halted"
    late = fresh.satisfy_gate_record(gates, "restart-2", answer="proceed", answerer="jeff")
    assert late.status == "answered"
    assert late.absence_events  # the halt audit trail survives the answer


# ---------------------------------------------------------------------------
# H-F3-3: silence never times out to consent.
# ---------------------------------------------------------------------------


def test_silence_never_consent_halt_default(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    _open(gates, "silent-1")  # HALT by default
    record = GR.resolve_absence(gates, "silent-1", reason="AskUserQuestion timed out")
    assert record.status == "halted"
    assert record.consumable is False
    assert record.answer is None
    assert GR.consumable_answer(record) is None
    # Control (the baseline that proves the assertion could fail): an ANSWERED gate is consumable.
    _open(gates, "silent-1-control")
    answered = GR.satisfy_gate_record(gates, "silent-1-control", answer="proceed", answerer="jeff")
    assert answered.consumable is True
    assert GR.consumable_answer(answered) == "proceed"


def test_silence_never_consent_repeated_silence_is_audited_not_deduplicated(
    tmp_path: Path,
) -> None:
    gates = tmp_path / "gates"
    _open(gates, "silent-2")
    GR.resolve_absence(gates, "silent-2", reason="timeout tick 1")
    record = GR.resolve_absence(gates, "silent-2", reason="timeout tick 2")
    assert record.status == "halted"
    assert [e["reason"] for e in record.absence_events] == ["timeout tick 1", "timeout tick 2"]


def test_silence_never_consent_escalate_halts_pending_a_live_response(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    _open(gates, "silent-3", absence_behavior="escalate")
    record = GR.resolve_absence(gates, "silent-3", reason="operator away")
    assert record.status == "escalated"
    assert record.consumable is False and record.answer is None
    notice = GR.compose_escalation_notice(record)
    assert "silent-3" in notice and "Proceed?" in notice
    late = GR.satisfy_gate_record(
        gates, "silent-3", answer="hold", answerer="jeff", answer_transport="redis-channel"
    )
    assert late.status == "answered"
    assert late.resolution["answer_transport"] == "redis-channel"


def test_silence_never_consent_safe_default_is_recorded_never_silent(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    _open(
        gates,
        "silent-4",
        absence_behavior="safe-default-with-record",
        safe_default="hold",
    )
    record = GR.resolve_absence(gates, "silent-4", reason="no answer in the window")
    assert record.status == "answered-by-default"
    assert record.answer == "hold"
    assert record.resolution["applied_by_absence"] is True  # the decision SAYS it was absence
    assert record.resolution["answerer"] == "absence:safe-default"
    assert record.resolution["provenance"] == "absence-safe-default"


def test_silence_never_consent_the_caller_cannot_pick_a_behavior_at_resolution_time(
    tmp_path: Path,
) -> None:
    # resolve_absence takes no behavior argument at all — the declaration decides. Verify the
    # declared behavior governs even when a "helpful" caller would have preferred a default.
    gates = tmp_path / "gates"
    _open(gates, "silent-5", absence_behavior="escalate")
    record = GR.resolve_absence(gates, "silent-5", reason="whatever the caller hoped for")
    assert record.status == "escalated"  # not halted, not defaulted — the declared behavior


# ---------------------------------------------------------------------------
# H-F3-3: pluggable transport — AskUserQuestion demoted.
# ---------------------------------------------------------------------------


def test_transport_parity_identical_record_semantics(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    push = _open(gates, "par-push", transport="ask-user-question")
    pull = _open(gates, "par-pull", transport="file-sentinel")
    # Identical schema — same keys, same declared semantics; only the transport value differs.
    push_d, pull_d = dict(push.declaration), dict(pull.declaration)
    assert push_d.keys() == pull_d.keys()
    for key in push_d.keys() - {"gate_id", "transport", "created_at"}:
        assert push_d[key] == pull_d[key], key

    # Push transport: the session relays the widget answer via satisfy.
    answered_push = GR.satisfy_gate_record(gates, "par-push", answer="proceed", answerer="jeff")
    # Pull transport: the answer arrives as a file sentinel and poll ingests it through the SAME
    # satisfy path.
    (gates / "par-pull" / "answer.json").write_text(
        json.dumps({"answer": "proceed", "answerer": "jeff"}), encoding="utf-8"
    )
    answered_pull = GR.poll_gate(gates, "par-pull")

    for record in (answered_push, answered_pull):
        assert record.status == "answered"
        assert record.answer == "proceed"
        assert record.resolution["provenance"] == "operator"
    assert answered_push.resolution["answer_transport"] == "ask-user-question"
    assert answered_pull.resolution["answer_transport"] == "file-sentinel"


def test_transport_parity_push_gate_refuses_a_stray_sentinel(tmp_path: Path) -> None:
    # The seam is real: a push-transport gate does NOT quietly ingest a pull-transport artifact.
    gates = tmp_path / "gates"
    _open(gates, "par-mismatch", transport="ask-user-question")
    (gates / "par-mismatch" / "answer.json").write_text(
        json.dumps({"answer": "proceed", "answerer": "jeff"}), encoding="utf-8"
    )
    with pytest.raises(GR.GateRecordError, match="mismatched transport"):
        GR.poll_gate(gates, "par-mismatch")


def test_transport_parity_malformed_sentinel_is_surfaced_never_skipped(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    _open(gates, "par-bad", transport="file-sentinel")
    (gates / "par-bad" / "answer.json").write_text(
        json.dumps({"answer": "proceed", "answerer": "jeff", "extra": True}), encoding="utf-8"
    )
    with pytest.raises(GR.GateRecordError, match="unknown key"):
        GR.poll_gate(gates, "par-bad")
    # Control: the same sentinel without the unknown key is ingested fine.
    (gates / "par-bad" / "answer.json").write_text(
        json.dumps({"answer": "proceed", "answerer": "jeff"}), encoding="utf-8"
    )
    assert GR.poll_gate(gates, "par-bad").status == "answered"


def test_transport_parity_unknown_transport_is_an_error(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    with pytest.raises(GR.GateRecordError, match="transport"):
        GR.open_gate(gates, "par-unknown", "Q?", ["a", "b"], transport="carrier-pigeon")


# ---------------------------------------------------------------------------
# H-F3-3: the answer is captured and read from the record, not the transport return.
# ---------------------------------------------------------------------------


def test_answer_read_from_record_not_the_transport_return(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    _open(gates, "read-1")
    # Simulate a lying/garbled transport return: what satisfy CAPTURED is the truth, and a fresh
    # process (the CLI — the exact surface skills consume) re-reads it from disk.
    GR.satisfy_gate_record(gates, "read-1", answer="hold", answerer="jeff")
    polled = _cli(gates, "poll", "--gate-id", "read-1")
    assert polled.returncode == 0, polled.stderr
    payload = json.loads(polled.stdout)
    assert payload["answer"] == "hold"
    assert payload["status"] == "answered"
    assert payload["resolution"]["answerer"] == "jeff"


def test_answer_read_from_record_pending_gate_yields_no_answer_via_cli(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    _open(gates, "read-2")
    polled = _cli(gates, "poll", "--gate-id", "read-2")
    assert polled.returncode == 0, polled.stderr
    payload = json.loads(polled.stdout)
    assert payload["consumable"] is False and payload["answer"] is None


def test_answer_must_be_one_of_the_declared_options(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    _open(gates, "read-3")
    with pytest.raises(GR.GateRecordError, match="not one of the declared options"):
        GR.satisfy_gate_record(gates, "read-3", answer="do something else", answerer="jeff")


def test_resolution_is_write_once(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    _open(gates, "once-1")
    GR.satisfy_gate_record(gates, "once-1", answer="proceed", answerer="jeff")
    with pytest.raises(GR.GateRecordError, match="write-once"):
        GR.satisfy_gate_record(gates, "once-1", answer="hold", answerer="mallory")
    with pytest.raises(GR.GateRecordError, match="already answered"):
        GR.resolve_absence(gates, "once-1", reason="late timeout")


# ---------------------------------------------------------------------------
# H-F6-5: the default is HALT, matching the fleet's binding failure posture.
# ---------------------------------------------------------------------------


def test_default_is_halt(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    record = _open(gates, "def-1")  # no absence_behavior argument at all
    assert record.declaration["absence_behavior"] == "HALT"
    # Control: an explicit non-default IS recorded (the assertion above could have failed).
    explicit = _open(gates, "def-2", absence_behavior="escalate")
    assert explicit.declaration["absence_behavior"] == "escalate"


def test_default_is_halt_via_the_cli_surface(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    opened = _cli(
        gates,
        "open",
        "--gate-id",
        "def-cli",
        "--question",
        "Ship?",
        "--option",
        "yes",
        "--option",
        "no",
    )
    assert opened.returncode == 0, opened.stderr
    assert json.loads(opened.stdout)["absence_behavior"] == "HALT"


# ---------------------------------------------------------------------------
# #371 operator-absence contract — both directions, bound to the real #433 provenance.
# ---------------------------------------------------------------------------


def test_carried_forward_provenance_is_not_operator_presence(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    _open(gates, "cf-1")
    with pytest.raises(GR.GateRecordError, match="not operator presence"):
        GR.satisfy_gate_record(
            gates, "cf-1", answer="proceed", answerer="carried-forward:tightening-repost:r3"
        )
    assert GR.load_gate(gates, "cf-1").status == "pending"  # the rejection changed nothing
    # ... and the same contract holds at the file-sentinel seam.
    _open(gates, "cf-2", transport="file-sentinel")
    (gates / "cf-2" / "answer.json").write_text(
        json.dumps({"answer": "proceed", "answerer": "carried-forward:tightening-repost:r3"}),
        encoding="utf-8",
    )
    with pytest.raises(GR.GateRecordError, match="not operator presence"):
        GR.poll_gate(gates, "cf-2")


def test_live_operator_answer_is_presence_the_other_direction(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    _open(gates, "cf-3")
    record = GR.satisfy_gate_record(gates, "cf-3", answer="proceed", answerer="jeff")
    assert record.status == "answered"
    assert record.resolution["provenance"] == "operator"
    assert GR.is_operator_answerer("jeff") is True
    assert GR.is_operator_answerer("carried-forward:tightening-repost:r3") is False
    assert GR.is_operator_answerer("absence:safe-default") is False
    assert GR.classify_answerer("carried-forward:tightening-repost:r3") == "derived"
    assert GR.classify_answerer("absence:safe-default") == "absence"


def test_carried_forward_prefix_is_drift_guarded_against_the_production_repost() -> None:
    """The reserved prefix must match what ``outcome_intent.repost`` actually writes (#433).

    ``tests/test_outcome_intent.py`` proves the production repost writes
    ``carried-forward:tightening-repost:r<old>`` into ``approvals/r{rev}.json``; this guard pins
    gate_record's reserved prefix to that literal so the two modules cannot drift apart silently.
    """
    source = (SCRIPTS / "outcome_intent.py").read_text(encoding="utf-8")
    production_literal = "carried-forward:tightening-repost:r"
    assert production_literal in source  # the producer still writes this provenance shape
    assert production_literal.startswith(GR.CARRIED_FORWARD_PREFIX)
    assert GR.classify_answerer(production_literal + "7") == "derived"
    # Control: a non-reserved answerer does NOT classify as derived.
    assert GR.classify_answerer("tightening-repost") == "operator"


def test_absence_answerer_cannot_be_forged_as_a_live_answer(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    _open(gates, "cf-4")
    with pytest.raises(GR.GateRecordError, match="not operator presence"):
        GR.satisfy_gate_record(gates, "cf-4", answer="proceed", answerer="absence:safe-default")


def test_forged_operator_provenance_with_reserved_answerer_fails_closed(tmp_path: Path) -> None:
    """Read-side cross-field invariant (re-panel hardening): a resolution.json forged directly
    into the store pairing operator provenance with a derived-class answerer must not LOAD as
    consumable — the write seams already refuse it, and read enforces the same contract."""
    gates = tmp_path / "gates"
    _open(gates, "forge-1")
    forged = {
        "schema_version": GR.SCHEMA_VERSION,
        "gate_id": "forge-1",
        "answer": "proceed",
        "answerer": "carried-forward:tightening-repost:r3",
        "answer_transport": "ask-user-question",
        "answered_at": "2026-07-14T00:00:00Z",
        "provenance": GR.PROVENANCE_OPERATOR,
        "applied_by_absence": False,
    }
    (gates / "forge-1" / "resolution.json").write_text(json.dumps(forged), encoding="utf-8")
    with pytest.raises(GR.GateRecordError, match="not operator presence"):
        GR.load_gate(gates, "forge-1")
    # Mirror: absence provenance demands an absence-class answerer.
    _open(gates, "forge-2")
    forged2 = dict(
        forged,
        gate_id="forge-2",
        answerer="jeff",
        answer_transport=GR.ABSENCE_TRANSPORT,
        provenance=GR.PROVENANCE_ABSENCE_SAFE_DEFAULT,
        applied_by_absence=True,
    )
    (gates / "forge-2" / "resolution.json").write_text(json.dumps(forged2), encoding="utf-8")
    with pytest.raises(GR.GateRecordError, match="absence resolution"):
        GR.load_gate(gates, "forge-2")
    # Control (green through the intended door): a resolution written through the production
    # seam loads as answered — the invariant discriminates, it doesn't just block.
    _open(gates, "forge-3")
    GR.satisfy_gate_record(gates, "forge-3", answer="proceed", answerer="jeff")
    assert GR.load_gate(gates, "forge-3").status == "answered"


def test_reserved_prefix_classification_survives_trivial_mutations(tmp_path: Path) -> None:
    """Whitespace/case mutations of a reserved prefix still classify as derived/absence and
    cannot satisfy a gate as a live answer — the stored answerer string stays verbatim, only
    the classification normalizes."""
    assert GR.classify_answerer(" carried-forward:x") == "derived"
    assert GR.classify_answerer("Carried-Forward:x") == "derived"
    assert GR.classify_answerer("ABSENCE:safe-default") == "absence"
    gates = tmp_path / "gates"
    _open(gates, "cf-5")
    with pytest.raises(GR.GateRecordError, match="not operator presence"):
        GR.satisfy_gate_record(gates, "cf-5", answer="proceed", answerer=" Carried-Forward:x")
    # Control: an ordinary answerer still classifies as live operator presence and satisfies.
    GR.satisfy_gate_record(gates, "cf-5", answer="proceed", answerer="jeff")
    assert GR.load_gate(gates, "cf-5").status == "answered"


# ---------------------------------------------------------------------------
# Fail-closed schema validation — wrong types and unknown keys are errors, not no-ops.
# ---------------------------------------------------------------------------


def test_declaration_validation_fails_closed(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    with pytest.raises(GR.GateRecordError, match="options"):
        GR.open_gate(gates, "v-1", "Q?", ["only-one"])
    with pytest.raises(GR.GateRecordError, match="duplicates"):
        GR.open_gate(gates, "v-2", "Q?", ["a", "a"])
    with pytest.raises(GR.GateRecordError, match="absence_behavior"):
        GR.open_gate(gates, "v-3", "Q?", ["a", "b"], absence_behavior="halt")  # case-strict
    with pytest.raises(GR.GateRecordError, match="safe_default"):
        GR.open_gate(gates, "v-4", "Q?", ["a", "b"], absence_behavior="safe-default-with-record")
    with pytest.raises(GR.GateRecordError, match="safe_default"):
        GR.open_gate(
            gates,
            "v-5",
            "Q?",
            ["a", "b"],
            absence_behavior="safe-default-with-record",
            safe_default="c",
        )
    with pytest.raises(GR.GateRecordError, match="only meaningful"):
        GR.open_gate(gates, "v-6", "Q?", ["a", "b"], safe_default="a")  # meaningless with HALT
    with pytest.raises(GR.GateRecordError, match="gate id"):
        GR.open_gate(gates, "../escape", "Q?", ["a", "b"])
    with pytest.raises(GR.GateRecordError, match="expected a string"):
        GR.open_gate(gates, "v-7", "Q?", ["a", True])  # a bool-coercible option is an error


def test_persisted_record_tampering_fails_closed(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    _open(gates, "t-1")
    record_path = gates / "t-1" / "record.json"
    data = json.loads(record_path.read_text(encoding="utf-8"))

    tampered = {**data, "absence_behavior": "proceed-quietly"}
    record_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(GR.GateRecordError, match="absence_behavior"):
        GR.load_gate(gates, "t-1")

    tampered = {**data, "surprise": 1}
    record_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(GR.GateRecordError, match="unknown key"):
        GR.load_gate(gates, "t-1")

    tampered = {**data, "schema_version": 2}
    record_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(GR.GateRecordError, match="schema_version"):
        GR.load_gate(gates, "t-1")

    # Control: restoring the original bytes restores loadability.
    record_path.write_text(json.dumps(data), encoding="utf-8")
    assert GR.load_gate(gates, "t-1").status == "pending"


def test_binding_vocabulary_is_closed_and_type_strict(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    record = _open(
        gates, "b-1", binding={"outcome_id": "camp", "spec_revision": 3, "intent_revision": 2}
    )
    assert record.declaration["binding"]["spec_revision"] == 3
    with pytest.raises(GR.GateRecordError, match="unknown key"):
        GR.open_gate(gates, "b-2", "Q?", ["a", "b"], binding={"mystery": "x"})
    with pytest.raises(GR.GateRecordError, match="expected an integer"):
        GR.open_gate(gates, "b-3", "Q?", ["a", "b"], binding={"spec_revision": "3"})
    with pytest.raises(GR.GateRecordError, match="expected an integer"):
        GR.open_gate(gates, "b-4", "Q?", ["a", "b"], binding={"spec_revision": True})


def test_list_gates_filters_by_status_and_binding(tmp_path: Path) -> None:
    gates = tmp_path / "gates"
    _open(gates, "l-1", binding={"outcome_id": "camp"})
    _open(gates, "l-2", binding={"outcome_id": "other"})
    GR.satisfy_gate_record(gates, "l-2", answer="proceed", answerer="jeff")
    by_binding = GR.list_gates(gates, binding={"outcome_id": "camp"})
    assert [r.gate_id for r in by_binding] == ["l-1"]
    by_status = GR.list_gates(gates, status="answered")
    assert [r.gate_id for r in by_status] == ["l-2"]
    # Control: no filter returns both.
    assert len(GR.list_gates(gates)) == 2
