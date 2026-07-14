#!/usr/bin/env python3
"""Durable gate records with a declared operator-absence contract (#371).

A gate is a **record**, not a widget call: question, options, a machine-readable
``absence_behavior`` declaring what silence means, the eventual answer, the answerer, timestamps,
and the transport — persisted BEFORE any transport is invoked. ``AskUserQuestion`` is demoted to
one pluggable transport among several; a widget timeout, a dropped session, or a primitive error
can therefore never be mistaken for an affirmative answer, because consumers read the persisted
record (``poll_gate``), never a transport call's raw return value.

Storage — derived-on-read, write-once commits (the ``/outcome`` campaign's posture applied here):

* ``<gates_dir>/<gate_id>/record.json``     — the declaration. Created atomically once
  (``os.link``, the same write-once mechanism as ``outcome_store`` completion events) and never
  rewritten. Re-opening the same gate with identical parameters resumes it; a mismatch is an error.
* ``<gates_dir>/<gate_id>/resolution.json`` — the answer. Write-once via ``os.link``: of two
  concurrent satisfy attempts on a local POSIX filesystem, exactly one creates this file; the
  other fails loudly. This file is the authoritative commit point for "answered".
* ``<gates_dir>/<gate_id>/absence.jsonl``   — append-only audit of absence events (every
  ``resolve-absent`` call appends; repeats are recorded, never deduplicated away — an audit trail
  must not under-report repeat silence, cf. issue #598 item 1).
* ``<gates_dir>/<gate_id>/answer.json``     — the file-sentinel transport's inbox (written by an
  operator or router process, ingested by ``poll_gate`` through the same satisfy path).

Status is DERIVED on every read, never held in memory across a session boundary: a resolution
file means ``answered`` (or ``answered-by-default`` when it was applied by the declared
safe-default absence behavior); otherwise the last absence event means ``halted``/``escalated``;
otherwise ``pending``. A session restart re-reads the same pending record instead of re-prompting.

Absence behaviors (default ``HALT``, matching the fleet's HALT-not-degrade posture):

* ``HALT``                      — the gate stays unanswered; consumers stop. A late live answer
  may still satisfy it.
* ``safe-default-with-record``  — the declared ``safe_default`` option becomes the answer, with
  ``applied_by_absence: true`` and answerer ``absence:safe-default`` recorded (never silent).
* ``escalate``                  — surface the composed notice to a human channel and HALT pending
  a live response (no new notification surface; the session relays the notice over whatever
  channel is connected).

Operator-absence contract — the deliberate position this module enforces (#371, binding on #449):
**derived provenance is not operator presence.** An answerer carrying a reserved prefix
(``carried-forward:`` — the #433 tightening-repost approval provenance — or ``absence:``) can
never satisfy a gate record as a live answer; ``satisfy_gate_record`` rejects it. A
carried-forward frontier approval remains valid for exactly what #433 defined it for (the R20
frontier dispatch gate); it does not constitute an operator answering a gate. Consumers (#449's
envelope-authorized merge) classify with :func:`classify_answerer` / :func:`is_operator_answerer`.

Threat model (self-attested seams, stated plainly): ``satisfy`` trusts its caller — the session
that ran the transport — to relay the answer faithfully, and ``opened_by``/``answerer`` are
self-attested strings, not authenticated identities. Sender authorization is the transport's job,
upstream (the same stance as ``outcome_gate_transport``). What the record proves is the declared
contract, the timing, the transport, and the provenance CLASS of the answer — not the biological
identity of the answerer. A consumer that bypasses this module and reads a widget return value
directly is out of contract; the companion lint (``lint_gate_absence_contract.py``) makes such
sites visible at build time but cannot stop a rogue runtime consumer.

Stdlib-only; imports no saga sibling.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

HALT = "HALT"
SAFE_DEFAULT_WITH_RECORD = "safe-default-with-record"
ESCALATE = "escalate"
ABSENCE_BEHAVIORS = (HALT, SAFE_DEFAULT_WITH_RECORD, ESCALATE)
DEFAULT_ABSENCE_BEHAVIOR = HALT

TRANSPORT_ASK_USER_QUESTION = "ask-user-question"
TRANSPORT_FILE_SENTINEL = "file-sentinel"
# Transports a gate may be OPENED on (each is registered in TRANSPORTS below).
OPEN_TRANSPORTS = (TRANSPORT_ASK_USER_QUESTION, TRANSPORT_FILE_SENTINEL)
# Transports a late/live ANSWER may arrive over. A gate escalated (or halted) while unattended is
# legitimately answered later over the fleet's channel surfaces; the record keeps the actual
# arrival transport as provenance. Closed vocabulary — anything else is an error.
ANSWER_TRANSPORTS = (*OPEN_TRANSPORTS, "redis-channel", "discord")
# The pseudo-transport recorded when a safe-default absence resolution supplies the answer.
ABSENCE_TRANSPORT = "absence"

STATUS_PENDING = "pending"
STATUS_ANSWERED = "answered"
STATUS_ANSWERED_BY_DEFAULT = "answered-by-default"
STATUS_HALTED = "halted"
STATUS_ESCALATED = "escalated"

# Statuses whose answer a consumer may act on. HALT/escalated/pending never yield an answer.
CONSUMABLE_STATUSES = (STATUS_ANSWERED, STATUS_ANSWERED_BY_DEFAULT)

PROVENANCE_OPERATOR = "operator"
PROVENANCE_ABSENCE_SAFE_DEFAULT = "absence-safe-default"

# Reserved answerer prefixes — derived provenance classes, never operator presence (#371 contract).
CARRIED_FORWARD_PREFIX = "carried-forward:"
ABSENCE_PREFIX = "absence:"
RESERVED_ANSWERER_PREFIXES = (CARRIED_FORWARD_PREFIX, ABSENCE_PREFIX)

# Binding vocabulary — the dispatch-era hooks #449 consumes. Closed: unknown keys are errors.
BINDING_STR_KEYS = ("outcome_id", "saga_id", "leaf_id")
BINDING_INT_KEYS = ("spec_revision", "intent_revision")

_GATE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,199}$")

_RECORD_KEYS = frozenset(
    {
        "schema_version",
        "gate_id",
        "question",
        "options",
        "absence_behavior",
        "safe_default",
        "transport",
        "opened_by",
        "created_at",
        "binding",
    }
)
_RESOLUTION_KEYS = frozenset(
    {
        "schema_version",
        "gate_id",
        "answer",
        "answerer",
        "answer_transport",
        "answered_at",
        "provenance",
        "applied_by_absence",
    }
)
_ABSENCE_EVENT_KEYS = frozenset({"behavior", "reason", "at"})
_INBOX_REQUIRED_KEYS = frozenset({"answer", "answerer"})
_INBOX_OPTIONAL_KEYS = frozenset({"at"})


class GateRecordError(Exception):
    """Any gate-record contract violation. Fail closed: never guess, never silently proceed."""


# ---------------------------------------------------------------------------
# Strict value helpers — input we cannot strictly understand is an error, including value TYPES.
# ---------------------------------------------------------------------------


def _require_str(value: Any, where: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str:
        raise GateRecordError(f"{where}: expected a string, got {type(value).__name__}")
    if not allow_empty and not value.strip():
        raise GateRecordError(f"{where}: must be a non-empty string")
    return value


def _require_int(value: Any, where: str) -> int:
    if type(value) is not int:  # type(True) is bool -> a bool is an error here, not a 1
        raise GateRecordError(f"{where}: expected an integer, got {type(value).__name__}")
    return value


def _require_bool(value: Any, where: str) -> bool:
    if type(value) is not bool:
        raise GateRecordError(f"{where}: expected a boolean, got {type(value).__name__}")
    return value


def _require_keys(data: Mapping[str, Any], required: frozenset[str], where: str) -> None:
    missing = required - data.keys()
    unknown = data.keys() - required
    if missing:
        raise GateRecordError(f"{where}: missing key(s) {sorted(missing)}")
    if unknown:
        raise GateRecordError(f"{where}: unknown key(s) {sorted(unknown)}")


def _now_iso(now: str | None) -> str:
    if now is not None:
        return _require_str(now, "timestamp")
    return datetime.now(tz=UTC).isoformat()


# ---------------------------------------------------------------------------
# Answerer classification — the operator-absence contract's enforcement point.
# ---------------------------------------------------------------------------


def classify_answerer(answerer: Any) -> str:
    """Classify an answerer string: ``operator`` | ``derived`` | ``absence``.

    ``derived`` is the ``carried-forward:`` provenance class #433's tightening-repost writes into
    ``approvals/r<rev>.json``; ``absence`` is this module's own safe-default resolution class.
    Neither is operator presence. Anything else (a non-empty, non-reserved string) classifies as
    ``operator`` — self-attested, per the module threat model.
    """
    value = _require_str(answerer, "answerer")
    # Classification normalizes a COPY (strip + casefold) so trivial mutations of a reserved
    # prefix (" carried-forward:x", "Carried-Forward:x") cannot re-class derived provenance as
    # operator presence. The stored answerer string stays verbatim — only the class is derived
    # from the normalized form.
    probe = value.strip().casefold()
    if probe.startswith(CARRIED_FORWARD_PREFIX):
        return "derived"
    if probe.startswith(ABSENCE_PREFIX):
        return "absence"
    return "operator"


def is_operator_answerer(answerer: Any) -> bool:
    """Whether ``answerer`` counts as live operator presence under the #371 contract."""
    return classify_answerer(answerer) == "operator"


# ---------------------------------------------------------------------------
# Validation of the persisted shapes (closed schemas, exact keys, strict types).
# ---------------------------------------------------------------------------


def validate_binding(binding: Any) -> dict[str, Any]:
    """Validate a binding dict against the closed vocabulary. Empty dict allowed."""
    if not isinstance(binding, dict):
        raise GateRecordError(f"binding: expected an object, got {type(binding).__name__}")
    out: dict[str, Any] = {}
    for key, value in binding.items():
        if key in BINDING_STR_KEYS:
            out[key] = _require_str(value, f"binding.{key}")
        elif key in BINDING_INT_KEYS:
            out[key] = _require_int(value, f"binding.{key}")
        else:
            raise GateRecordError(
                f"binding: unknown key {key!r} (known: "
                f"{sorted(BINDING_STR_KEYS + BINDING_INT_KEYS)})"
            )
    return out


def _validate_declaration(data: Mapping[str, Any], where: str) -> dict[str, Any]:
    _require_keys(data, _RECORD_KEYS, where)
    if data["schema_version"] != SCHEMA_VERSION:
        raise GateRecordError(
            f"{where}: schema_version {data['schema_version']!r} != {SCHEMA_VERSION}"
        )
    gate_id = _require_str(data["gate_id"], f"{where}: gate_id")
    if not _GATE_ID_RE.match(gate_id):
        raise GateRecordError(f"{where}: gate_id {gate_id!r} is not a valid gate id slug")
    _require_str(data["question"], f"{where}: question")
    options = data["options"]
    if type(options) is not list or len(options) < 2:
        raise GateRecordError(f"{where}: options must be a list of at least 2 options")
    for i, opt in enumerate(options):
        _require_str(opt, f"{where}: options[{i}]")
    if len(set(options)) != len(options):
        raise GateRecordError(f"{where}: options contain duplicates")
    behavior = _require_str(data["absence_behavior"], f"{where}: absence_behavior")
    if behavior not in ABSENCE_BEHAVIORS:
        raise GateRecordError(
            f"{where}: absence_behavior {behavior!r} not in {list(ABSENCE_BEHAVIORS)}"
        )
    safe_default = data["safe_default"]
    if behavior == SAFE_DEFAULT_WITH_RECORD:
        _require_str(safe_default, f"{where}: safe_default")
        if safe_default not in options:
            raise GateRecordError(f"{where}: safe_default {safe_default!r} is not one of options")
    elif safe_default is not None:
        raise GateRecordError(
            f"{where}: safe_default is only meaningful with "
            f"absence_behavior={SAFE_DEFAULT_WITH_RECORD!r}"
        )
    transport = _require_str(data["transport"], f"{where}: transport")
    if transport not in OPEN_TRANSPORTS:
        raise GateRecordError(f"{where}: transport {transport!r} not in {list(OPEN_TRANSPORTS)}")
    _require_str(data["opened_by"], f"{where}: opened_by", allow_empty=True)
    _require_str(data["created_at"], f"{where}: created_at")
    validate_binding(data["binding"])
    return dict(data)


def _validate_resolution(data: Mapping[str, Any], declaration: Mapping[str, Any]) -> dict[str, Any]:
    where = f"gate {declaration['gate_id']}: resolution"
    _require_keys(data, _RESOLUTION_KEYS, where)
    if data["schema_version"] != SCHEMA_VERSION:
        raise GateRecordError(f"{where}: schema_version mismatch")
    if data["gate_id"] != declaration["gate_id"]:
        raise GateRecordError(
            f"{where}: gate_id {data['gate_id']!r} does not match its declaration"
        )
    answer = _require_str(data["answer"], f"{where}: answer")
    if answer not in declaration["options"]:
        raise GateRecordError(f"{where}: answer {answer!r} is not one of the declared options")
    answerer = _require_str(data["answerer"], f"{where}: answerer")
    transport = _require_str(data["answer_transport"], f"{where}: answer_transport")
    if transport not in (*ANSWER_TRANSPORTS, ABSENCE_TRANSPORT):
        raise GateRecordError(f"{where}: answer_transport {transport!r} is unknown")
    _require_str(data["answered_at"], f"{where}: answered_at")
    provenance = _require_str(data["provenance"], f"{where}: provenance")
    if provenance not in (PROVENANCE_OPERATOR, PROVENANCE_ABSENCE_SAFE_DEFAULT):
        raise GateRecordError(f"{where}: provenance {provenance!r} is unknown")
    _require_bool(data["applied_by_absence"], f"{where}: applied_by_absence")
    # Read-side cross-field invariant (re-panel hardening): the write seams already refuse a
    # derived/absence-class answerer as a live operator answer, so a PERSISTED resolution that
    # pairs operator provenance with a reserved-class answerer (or absence provenance with a
    # non-absence answerer) is internally inconsistent — a tampered store or a buggy writer —
    # and must not load as consumable. Same contract, enforced at read as well as write.
    answerer_class = classify_answerer(answerer)
    if provenance == PROVENANCE_OPERATOR and answerer_class != "operator":
        raise GateRecordError(
            f"{where}: provenance {PROVENANCE_OPERATOR!r} with a {answerer_class}-class "
            f"answerer {answerer!r} — derived provenance is not operator presence"
        )
    if provenance == PROVENANCE_ABSENCE_SAFE_DEFAULT and answerer_class != "absence":
        raise GateRecordError(
            f"{where}: provenance {PROVENANCE_ABSENCE_SAFE_DEFAULT!r} with a "
            f"{answerer_class}-class answerer {answerer!r} — an absence resolution must "
            f"carry an {ABSENCE_PREFIX}* answerer"
        )
    return dict(data)


def _validate_absence_event(data: Mapping[str, Any], where: str) -> dict[str, Any]:
    _require_keys(data, _ABSENCE_EVENT_KEYS, where)
    behavior = _require_str(data["behavior"], f"{where}: behavior")
    if behavior not in ABSENCE_BEHAVIORS:
        raise GateRecordError(f"{where}: behavior {behavior!r} not in {list(ABSENCE_BEHAVIORS)}")
    _require_str(data["reason"], f"{where}: reason")
    _require_str(data["at"], f"{where}: at")
    return dict(data)


# ---------------------------------------------------------------------------
# The derived record.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateRecord:
    """One gate, derived on read from its declaration + resolution + absence-event files."""

    declaration: dict[str, Any]
    resolution: dict[str, Any] | None
    absence_events: list[dict[str, Any]]

    @property
    def gate_id(self) -> str:
        return str(self.declaration["gate_id"])

    @property
    def status(self) -> str:
        if self.resolution is not None:
            if self.resolution["applied_by_absence"]:
                return STATUS_ANSWERED_BY_DEFAULT
            return STATUS_ANSWERED
        for event in reversed(self.absence_events):
            if event["behavior"] == HALT:
                return STATUS_HALTED
            if event["behavior"] == ESCALATE:
                return STATUS_ESCALATED
        return STATUS_PENDING

    @property
    def consumable(self) -> bool:
        return self.status in CONSUMABLE_STATUSES

    @property
    def answer(self) -> str | None:
        """The answer a consumer may act on — ``None`` unless the status is consumable."""
        if self.resolution is None or not self.consumable:
            return None
        return str(self.resolution["answer"])

    def to_public_dict(self) -> dict[str, Any]:
        return {
            **self.declaration,
            "status": self.status,
            "consumable": self.consumable,
            "answer": self.answer,
            "resolution": self.resolution,
            "absence_events": list(self.absence_events),
        }


# ---------------------------------------------------------------------------
# Filesystem plumbing.
# ---------------------------------------------------------------------------


def _gate_dir(gates_dir: Path, gate_id: str) -> Path:
    if not _GATE_ID_RE.match(gate_id):
        raise GateRecordError(f"gate_id {gate_id!r} is not a valid gate id slug")
    return Path(gates_dir) / gate_id


def _write_once(path: Path, content: str) -> bool:
    """Atomic create-or-refuse (temp + ``os.link``), mirroring ``outcome_store``'s convention."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    tmp.write_text(content, encoding="utf-8")
    try:
        os.link(tmp, path)
        return True
    except FileExistsError:
        return False
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()


def _read_json(path: Path, where: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GateRecordError(f"{where}: not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise GateRecordError(f"{where}: expected a JSON object")
    return data


# ---------------------------------------------------------------------------
# The transport seam — how an ANSWER arrives. The record schema, poll, and satisfy are
# transport-agnostic; a transport contributes only a ``collect`` strategy. ``ask-user-question``
# is a PUSH transport (the session that ran the widget pushes the answer via ``satisfy``);
# ``file-sentinel`` is a PULL transport (``poll`` ingests a dropped answer file). Neither is
# special-cased anywhere else.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CollectedAnswer:
    answer: str
    answerer: str
    at: str | None


def _inbox_path(gates_dir: Path, gate_id: str) -> Path:
    return _gate_dir(gates_dir, gate_id) / "answer.json"


def _collect_push(gates_dir: Path, record: GateRecord) -> CollectedAnswer | None:
    """Push transports never read an inbox. A stray inbox file is a transport mismatch — error."""
    inbox = _inbox_path(gates_dir, record.gate_id)
    if inbox.exists():
        raise GateRecordError(
            f"gate {record.gate_id}: answer sentinel present but the gate's transport is "
            f"{record.declaration['transport']!r} (push) — mismatched transport, refusing to ingest"
        )
    return None


def _collect_file_sentinel(gates_dir: Path, record: GateRecord) -> CollectedAnswer | None:
    inbox = _inbox_path(gates_dir, record.gate_id)
    if not inbox.exists():
        return None
    where = f"gate {record.gate_id}: answer sentinel"
    data = _read_json(inbox, where)
    unknown = data.keys() - (_INBOX_REQUIRED_KEYS | _INBOX_OPTIONAL_KEYS)
    missing = _INBOX_REQUIRED_KEYS - data.keys()
    if missing:
        raise GateRecordError(f"{where}: missing key(s) {sorted(missing)}")
    if unknown:
        raise GateRecordError(f"{where}: unknown key(s) {sorted(unknown)}")
    answer = _require_str(data["answer"], f"{where}: answer")
    answerer = _require_str(data["answerer"], f"{where}: answerer")
    at = None if "at" not in data else _require_str(data["at"], f"{where}: at")
    return CollectedAnswer(answer=answer, answerer=answerer, at=at)


TRANSPORTS: dict[str, Callable[[Path, GateRecord], CollectedAnswer | None]] = {
    TRANSPORT_ASK_USER_QUESTION: _collect_push,
    TRANSPORT_FILE_SENTINEL: _collect_file_sentinel,
}


# ---------------------------------------------------------------------------
# Core verbs.
# ---------------------------------------------------------------------------


def open_gate(
    gates_dir: Path | str,
    gate_id: str,
    question: str,
    options: list[str],
    *,
    absence_behavior: str = DEFAULT_ABSENCE_BEHAVIOR,
    transport: str = TRANSPORT_ASK_USER_QUESTION,
    safe_default: str | None = None,
    opened_by: str = "",
    binding: dict[str, Any] | None = None,
    now: str | None = None,
) -> tuple[GateRecord, bool]:
    """Persist the gate's declaration BEFORE any transport is invoked. Returns (record, created).

    Re-opening an existing gate with an identical declaration (everything but ``created_at``)
    resumes it — ``created`` is False and the persisted record is returned unchanged, so a session
    restart lands on the same pending gate instead of re-prompting. A parameter mismatch against
    the existing declaration is an error, never a silent reuse.
    """
    gates_dir = Path(gates_dir)
    declaration = _validate_declaration(
        {
            "schema_version": SCHEMA_VERSION,
            "gate_id": gate_id,
            "question": question,
            "options": options,
            "absence_behavior": absence_behavior,
            "safe_default": safe_default,
            "transport": transport,
            "opened_by": opened_by,
            "created_at": _now_iso(now),
            "binding": binding if binding is not None else {},
        },
        "open_gate",
    )
    record_path = _gate_dir(gates_dir, gate_id) / "record.json"
    created = _write_once(record_path, json.dumps(declaration, indent=2) + "\n")
    if not created:
        existing = load_gate(gates_dir, gate_id)
        immutable = {k: v for k, v in declaration.items() if k != "created_at"}
        persisted = {k: v for k, v in existing.declaration.items() if k != "created_at"}
        if immutable != persisted:
            raise GateRecordError(
                f"gate {gate_id}: already open with a different declaration — refusing to reuse "
                f"(open a new gate id for a different decision)"
            )
        return existing, False
    return load_gate(gates_dir, gate_id), True


def load_gate(gates_dir: Path | str, gate_id: str) -> GateRecord:
    """Read one gate from disk, strictly validating every artifact. Status is derived, not stored."""
    gates_dir = Path(gates_dir)
    gate_dir = _gate_dir(gates_dir, gate_id)
    record_path = gate_dir / "record.json"
    if not record_path.exists():
        raise GateRecordError(f"gate {gate_id}: no record at {record_path}")
    declaration = _validate_declaration(
        _read_json(record_path, f"gate {gate_id}: record"), f"gate {gate_id}: record"
    )
    if declaration["gate_id"] != gate_id:
        raise GateRecordError(
            f"gate {gate_id}: record declares gate_id {declaration['gate_id']!r} — corrupt store"
        )
    resolution: dict[str, Any] | None = None
    resolution_path = gate_dir / "resolution.json"
    if resolution_path.exists():
        resolution = _validate_resolution(
            _read_json(resolution_path, f"gate {gate_id}: resolution"), declaration
        )
    events: list[dict[str, Any]] = []
    events_path = gate_dir / "absence.jsonl"
    if events_path.exists():
        for i, line in enumerate(events_path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            where = f"gate {gate_id}: absence event {i}"
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateRecordError(f"{where}: not valid JSON ({exc})") from exc
            if not isinstance(raw, dict):
                raise GateRecordError(f"{where}: expected a JSON object")
            events.append(_validate_absence_event(raw, where))
    return GateRecord(declaration=declaration, resolution=resolution, absence_events=events)


def _commit_resolution(
    gates_dir: Path,
    record: GateRecord,
    *,
    answer: str,
    answerer: str,
    answer_transport: str,
    provenance: str,
    applied_by_absence: bool,
    now: str | None,
) -> GateRecord:
    resolution = _validate_resolution(
        {
            "schema_version": SCHEMA_VERSION,
            "gate_id": record.gate_id,
            "answer": answer,
            "answerer": answerer,
            "answer_transport": answer_transport,
            "answered_at": _now_iso(now),
            "provenance": provenance,
            "applied_by_absence": applied_by_absence,
        },
        record.declaration,
    )
    path = _gate_dir(gates_dir, record.gate_id) / "resolution.json"
    if not _write_once(path, json.dumps(resolution, indent=2) + "\n"):
        raise GateRecordError(
            f"gate {record.gate_id}: already answered — the resolution is write-once"
        )
    return load_gate(gates_dir, record.gate_id)


def satisfy_gate_record(
    gates_dir: Path | str,
    gate_id: str,
    *,
    answer: str,
    answerer: str,
    answer_transport: str | None = None,
    now: str | None = None,
) -> GateRecord:
    """Capture a LIVE answer into the record. The record, not the transport return, is the truth.

    Enforces the operator-absence contract: an answerer classifying as ``derived``
    (``carried-forward:*``) or ``absence`` is rejected — derived provenance never counts as
    operator presence. Allowed while pending, halted, or escalated (a late live answer resolves a
    halt — that is the whole point of ``escalate``); write-once thereafter.
    """
    gates_dir = Path(gates_dir)
    record = load_gate(gates_dir, gate_id)
    if record.resolution is not None:
        raise GateRecordError(f"gate {gate_id}: already answered — the resolution is write-once")
    cls = classify_answerer(answerer)
    if cls != "operator":
        raise GateRecordError(
            f"gate {gate_id}: answerer {answerer!r} classifies as {cls!r} — derived provenance is "
            f"not operator presence and cannot satisfy a gate record (#371 operator-absence "
            f"contract)"
        )
    transport = record.declaration["transport"] if answer_transport is None else answer_transport
    if transport not in ANSWER_TRANSPORTS:
        raise GateRecordError(
            f"gate {gate_id}: answer_transport {transport!r} not in {list(ANSWER_TRANSPORTS)}"
        )
    if answer not in record.declaration["options"]:
        raise GateRecordError(
            f"gate {gate_id}: answer {answer!r} is not one of the declared options "
            f"{record.declaration['options']} — a free-text divergence means the option set was "
            f"wrong; open a corrected gate instead"
        )
    return _commit_resolution(
        gates_dir,
        record,
        answer=answer,
        answerer=answerer,
        answer_transport=str(transport),
        provenance=PROVENANCE_OPERATOR,
        applied_by_absence=False,
        now=now,
    )


def _append_absence_event(
    gates_dir: Path, gate_id: str, *, behavior: str, reason: str, now: str | None
) -> None:
    event = _validate_absence_event(
        {"behavior": behavior, "reason": reason, "at": _now_iso(now)}, "resolve_absence"
    )
    path = _gate_dir(gates_dir, gate_id) / "absence.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")


def resolve_absence(
    gates_dir: Path | str,
    gate_id: str,
    *,
    reason: str,
    now: str | None = None,
) -> GateRecord:
    """Resolve silence (timeout, transport error, dropped call) by the DECLARED behavior only.

    The caller cannot choose a behavior here — the declaration decides. Silence therefore never
    resolves to an implicit affirmative: HALT/escalate leave the gate unanswered (and repeat calls
    append further audit events, never deduplicated); safe-default records the declared default
    with ``applied_by_absence: true`` and the ``absence:safe-default`` answerer, never silently.
    """
    gates_dir = Path(gates_dir)
    _require_str(reason, "resolve_absence: reason")
    record = load_gate(gates_dir, gate_id)
    if record.resolution is not None:
        raise GateRecordError(
            f"gate {gate_id}: already answered — absence resolution no longer applies"
        )
    behavior = record.declaration["absence_behavior"]
    if behavior == SAFE_DEFAULT_WITH_RECORD:
        # The resolution file is the authoritative commit; the audit event follows it. A crash
        # between the two loses only the audit line — the resolution self-describes via
        # applied_by_absence, so the record can never claim a live answer it did not get.
        _commit_resolution(
            gates_dir,
            record,
            answer=str(record.declaration["safe_default"]),
            answerer=f"{ABSENCE_PREFIX}safe-default",
            answer_transport=ABSENCE_TRANSPORT,
            provenance=PROVENANCE_ABSENCE_SAFE_DEFAULT,
            applied_by_absence=True,
            now=now,
        )
        _append_absence_event(gates_dir, gate_id, behavior=behavior, reason=reason, now=now)
        return load_gate(gates_dir, gate_id)
    _append_absence_event(gates_dir, gate_id, behavior=behavior, reason=reason, now=now)
    return load_gate(gates_dir, gate_id)


def poll_gate(gates_dir: Path | str, gate_id: str, *, now: str | None = None) -> GateRecord:
    """Re-derive the gate's state from disk; pull transports ingest a waiting answer here.

    A pending ``file-sentinel`` gate with a valid inbox is satisfied through the SAME
    ``satisfy_gate_record`` path (identical validation, identical record semantics); an invalid
    inbox raises — surfaced, never skipped. Poll never invents an answer: a silent gate stays
    pending/halted/escalated with ``consumable: false``.
    """
    gates_dir = Path(gates_dir)
    record = load_gate(gates_dir, gate_id)
    if record.resolution is not None:
        return record
    collect = TRANSPORTS[record.declaration["transport"]]
    collected = collect(gates_dir, record)
    if collected is None:
        return record
    return satisfy_gate_record(
        gates_dir,
        gate_id,
        answer=collected.answer,
        answerer=collected.answerer,
        answer_transport=record.declaration["transport"],
        now=collected.at if collected.at is not None else now,
    )


def consumable_answer(record: GateRecord) -> str | None:
    """The answer a consumer may act on, or ``None``. Never an implicit default."""
    return record.answer


def compose_escalation_notice(record: GateRecord, *, gates_dir: Path | str = ".saga/gates") -> str:
    """Render the escalation text a session relays over its connected human channel (pure)."""
    lines = [
        f"Escalated gate `{record.gate_id}` — a decision is HALTED pending a live operator answer.",
        "",
        f"Question: {record.declaration['question']}",
        "Options:",
    ]
    lines.extend(f"  - {opt}" for opt in record.declaration["options"])
    lines += [
        "",
        "Answer with:",
        f"  python3 plugins/saga/scripts/gate_record.py satisfy --gates-dir {gates_dir} "
        f'--gate-id {record.gate_id} --answer "<option>" --answerer <your-name>',
    ]
    return "\n".join(lines)


def list_gates(
    gates_dir: Path | str,
    *,
    status: str | None = None,
    binding: dict[str, Any] | None = None,
) -> list[GateRecord]:
    """Enumerate gate records, optionally filtered by status and/or binding entries."""
    gates_dir = Path(gates_dir)
    wanted_binding = validate_binding(binding) if binding is not None else {}
    records: list[GateRecord] = []
    if not gates_dir.exists():
        return records
    for child in sorted(gates_dir.iterdir()):
        if not (child / "record.json").exists():
            continue
        record = load_gate(gates_dir, child.name)
        if status is not None and record.status != status:
            continue
        if wanted_binding and any(
            record.declaration["binding"].get(k) != v for k, v in wanted_binding.items()
        ):
            continue
        records.append(record)
    return records


# ---------------------------------------------------------------------------
# CLI — the surface saga skills and team-execution shell out to.
# ---------------------------------------------------------------------------


def _parse_binding_args(pairs: list[str]) -> dict[str, Any]:
    binding: dict[str, Any] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise GateRecordError(f"--binding {pair!r}: expected key=value")
        if key in BINDING_INT_KEYS:
            if not value.isdigit():
                raise GateRecordError(f"--binding {key}: expected an integer, got {value!r}")
            binding[key] = int(value)
        else:
            binding[key] = value
    return validate_binding(binding)


def _print_record(record: GateRecord, extra: dict[str, Any] | None = None) -> None:
    payload = record.to_public_dict()
    if extra:
        payload.update(extra)
    print(json.dumps(payload, indent=2))


def _cli_open(args: argparse.Namespace) -> int:
    record, created = open_gate(
        args.gates_dir,
        args.gate_id,
        args.question,
        list(args.option),
        absence_behavior=args.absence_behavior,
        transport=args.transport,
        safe_default=args.safe_default,
        opened_by=args.opened_by,
        binding=_parse_binding_args(args.binding),
    )
    _print_record(record, {"created": created})
    return 0


def _cli_poll(args: argparse.Namespace) -> int:
    _print_record(poll_gate(args.gates_dir, args.gate_id))
    return 0


def _cli_satisfy(args: argparse.Namespace) -> int:
    record = satisfy_gate_record(
        args.gates_dir,
        args.gate_id,
        answer=args.answer,
        answerer=args.answerer,
        answer_transport=args.answer_transport,
    )
    _print_record(record)
    return 0


def _cli_resolve_absent(args: argparse.Namespace) -> int:
    record = resolve_absence(args.gates_dir, args.gate_id, reason=args.reason)
    extra: dict[str, Any] = {}
    if record.status == STATUS_ESCALATED:
        extra["escalation_notice"] = compose_escalation_notice(record, gates_dir=args.gates_dir)
    _print_record(record, extra)
    return 0


def _cli_list(args: argparse.Namespace) -> int:
    records = list_gates(
        args.gates_dir,
        status=args.status,
        binding=_parse_binding_args(args.binding) if args.binding else None,
    )
    print(json.dumps([r.to_public_dict() for r in records], indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gate_record",
        description="Durable gate records with a declared operator-absence contract (#371).",
    )
    parser.add_argument("--gates-dir", default=".saga/gates", help="gate-record store root")
    sub = parser.add_subparsers(dest="command", required=True)

    p_open = sub.add_parser("open", help="persist the gate declaration BEFORE any transport call")
    p_open.add_argument("--gate-id", required=True)
    p_open.add_argument("--question", required=True)
    p_open.add_argument("--option", action="append", required=True, help="repeatable (>= 2)")
    p_open.add_argument(
        "--absence-behavior",
        default=DEFAULT_ABSENCE_BEHAVIOR,
        choices=list(ABSENCE_BEHAVIORS),
        help=f"declared no-answer behavior (default {DEFAULT_ABSENCE_BEHAVIOR})",
    )
    p_open.add_argument(
        "--transport", default=TRANSPORT_ASK_USER_QUESTION, choices=list(OPEN_TRANSPORTS)
    )
    p_open.add_argument("--safe-default", default=None)
    p_open.add_argument("--opened-by", default="")
    p_open.add_argument("--binding", action="append", default=[], help="key=value (repeatable)")
    p_open.set_defaults(func=_cli_open)

    p_poll = sub.add_parser("poll", help="re-derive gate state; pull transports ingest here")
    p_poll.add_argument("--gate-id", required=True)
    p_poll.set_defaults(func=_cli_poll)

    p_satisfy = sub.add_parser("satisfy", help="capture a live operator answer into the record")
    p_satisfy.add_argument("--gate-id", required=True)
    p_satisfy.add_argument("--answer", required=True)
    p_satisfy.add_argument("--answerer", required=True)
    p_satisfy.add_argument("--answer-transport", default=None, choices=list(ANSWER_TRANSPORTS))
    p_satisfy.set_defaults(func=_cli_satisfy)

    p_absent = sub.add_parser(
        "resolve-absent", help="resolve silence by the gate's DECLARED absence behavior"
    )
    p_absent.add_argument("--gate-id", required=True)
    p_absent.add_argument("--reason", required=True)
    p_absent.set_defaults(func=_cli_resolve_absent)

    p_list = sub.add_parser("list", help="enumerate gate records (status/binding filters)")
    p_list.add_argument("--status", default=None)
    p_list.add_argument("--binding", action="append", default=[], help="key=value (repeatable)")
    p_list.set_defaults(func=_cli_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (GateRecordError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
