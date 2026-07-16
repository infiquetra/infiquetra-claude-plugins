#!/usr/bin/env python3
"""Append-only dispatch manifests, settlement, casualty reports, and derived retries (#351).

The run-fact ledger is the only durable store. Manifests, spawn attempts, terminal settlements, and
late deliveries are ``run_fact.v1`` records with ``kind=dispatch-settlement``. Reports, open
positions, and the dead-letter view are derived from one verified snapshot on every read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_ledger  # noqa: E402

FACT_KIND = "dispatch-settlement"
EVENT_MANIFEST = "manifest"
EVENT_SPAWN = "spawn"
EVENT_SETTLE = "settle"
EVENT_LATE_DELIVERY = "late-delivery"
EVENTS = frozenset({EVENT_MANIFEST, EVENT_SPAWN, EVENT_SETTLE, EVENT_LATE_DELIVERY})

SITES = frozenset({"outcome", "team-execution", "workflow"})
DELIVERED = "delivered"
RATE_KILLED = "rate-killed"
IDLE = "idle"
SILENT_NOOP = "silent-no-op"
LEDGER_CLASSIFICATIONS = frozenset({DELIVERED, RATE_KILLED, IDLE, SILENT_NOOP})
CASUALTY_CLASSIFICATIONS = frozenset({RATE_KILLED, IDLE, SILENT_NOOP})

DELIVERY_RECEIPTS = frozenset({"artifact", "worker-manifest", "workflow-result"})
RATE_RECEIPT = "rate_limited"
IDLE_RECEIPT = "idle"
TRUSTED_RECEIPTS = DELIVERY_RECEIPTS | {RATE_RECEIPT, IDLE_RECEIPT}

DEFAULT_THRESHOLD_PERCENT = 0
DEFAULT_MAX_ATTEMPTS = 3
MAX_ATTEMPTS_LIMIT = 3
MAX_ID_LENGTH = 200
MAX_REASON_LENGTH = 500
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class DispatchSettlementError(ValueError):
    """A malformed fact, illegal transition, or broken evidence chain."""


@dataclass(frozen=True)
class UnitSpec:
    unit_id: str
    idempotency_key: str
    deliverables: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "idempotency_key": self.idempotency_key,
            "deliverables": list(self.deliverables),
        }


@dataclass(frozen=True)
class Classification:
    classification: str
    reason: str
    evidence_ref: str = ""
    evidence_sha256: str = ""


@dataclass(frozen=True)
class CasualtyEntry:
    unit_id: str
    attempt: int
    classification: str
    reason: str
    evidence_ref: str
    spawned: bool
    settled: bool


@dataclass(frozen=True)
class AttemptCohort:
    attempt: int
    expected: int
    settled: int
    casualties: int
    casualty_rate_percent: float | None
    threshold_percent: int
    complete: bool
    halt_required: bool


@dataclass(frozen=True)
class CasualtyReport:
    dispatch_id: str
    site: str
    entries: tuple[CasualtyEntry, ...]
    cohorts: tuple[AttemptCohort, ...]
    halt_required: bool
    evidence_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatch_id": self.dispatch_id,
            "site": self.site,
            "entries": [asdict(entry) for entry in self.entries],
            "cohorts": [asdict(cohort) for cohort in self.cohorts],
            "halt_required": self.halt_required,
            "evidence_error": self.evidence_error,
        }


@dataclass(frozen=True)
class DeadLetter:
    dispatch_id: str
    unit_id: str
    previous_attempt: int
    next_attempt: int
    idempotency_key: str
    classification: str
    reason: str


def _identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise DispatchSettlementError(
            f"{field} must be 1..{MAX_ID_LENGTH} safe identifier characters"
        )
    text = value.strip()
    if not text or len(text) > MAX_ID_LENGTH or _ID_RE.fullmatch(text) is None:
        raise DispatchSettlementError(
            f"{field} must be 1..{MAX_ID_LENGTH} safe identifier characters"
        )
    return text


def _bounded_text(value: object, *, field: str, limit: int = MAX_REASON_LENGTH) -> str:
    if not isinstance(value, str):
        raise DispatchSettlementError(f"{field} must be non-empty printable text <= {limit} chars")
    text = value.strip()
    if not text or len(text) > limit or any(ord(char) < 32 for char in text):
        raise DispatchSettlementError(f"{field} must be non-empty printable text <= {limit} chars")
    return text


def _digest(value: object, *, field: str = "evidence_sha256") -> str:
    if not isinstance(value, str):
        raise DispatchSettlementError(f"{field} must be a lowercase SHA-256 digest")
    text = value.strip().lower()
    if _SHA256_RE.fullmatch(text) is None:
        raise DispatchSettlementError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _timestamp(value: object) -> str:
    if not isinstance(value, str):
        raise DispatchSettlementError("at must be an ISO-8601 UTC timestamp")
    text = _bounded_text(value, field="at", limit=100)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DispatchSettlementError("at must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != datetime.min.replace(tzinfo=UTC).utcoffset():
        raise DispatchSettlementError("at must be an ISO-8601 UTC timestamp")
    return text


def _attempt(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DispatchSettlementError("attempt must be an integer >= 1")
    return value


def _threshold(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise DispatchSettlementError("casualty_threshold_percent must be an integer 0..100")
    return value


def _max_attempts(value: object) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= MAX_ATTEMPTS_LIMIT
    ):
        raise DispatchSettlementError(f"max_attempts must be an integer 1..{MAX_ATTEMPTS_LIMIT}")
    return value


def _unit(value: UnitSpec | Mapping[str, Any]) -> UnitSpec:
    if isinstance(value, UnitSpec):
        candidate = value
    else:
        raw_deliverables = value.get("deliverables", ())
        if not isinstance(raw_deliverables, Sequence) or isinstance(raw_deliverables, (str, bytes)):
            raise DispatchSettlementError("unit deliverables must be a list of identifiers")
        candidate = UnitSpec(
            unit_id=_identifier(value.get("unit_id", ""), field="unit_id"),
            idempotency_key=_identifier(value.get("idempotency_key", ""), field="idempotency_key"),
            deliverables=tuple(_identifier(item, field="deliverable") for item in raw_deliverables),
        )
    unit_id = _identifier(candidate.unit_id, field="unit_id")
    idempotency_key = _identifier(candidate.idempotency_key, field="idempotency_key")
    deliverables = tuple(_identifier(item, field="deliverable") for item in candidate.deliverables)
    if not deliverables or len(set(deliverables)) != len(deliverables):
        raise DispatchSettlementError("unit deliverables must be non-empty and unique")
    return UnitSpec(unit_id, idempotency_key, deliverables)


def _units(values: Iterable[UnitSpec | Mapping[str, Any]]) -> tuple[UnitSpec, ...]:
    normalized = tuple(_unit(value) for value in values)
    if not normalized:
        raise DispatchSettlementError("a manifest needs at least one unit")
    ids = [unit.unit_id for unit in normalized]
    if len(set(ids)) != len(ids):
        raise DispatchSettlementError("manifest unit_id values must be unique")
    return normalized


def _fact_records(snapshot: run_ledger.LedgerSnapshot, dispatch_id: str) -> list[dict[str, Any]]:
    if not snapshot.report.ok:
        raise DispatchSettlementError(f"broken run-fact chain: {snapshot.report.reason}")
    for record in snapshot.records:
        if record.get("kind") == FACT_KIND:
            _validate_stored_fact(record)
    return [
        record
        for record in snapshot.records
        if record.get("kind") == FACT_KIND and record.get("dispatch_id") == dispatch_id
    ]


def _manifest(records: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    manifests = [record for record in records if record.get("event") == EVENT_MANIFEST]
    if len(manifests) > 1:
        raise DispatchSettlementError("dispatch has duplicate manifest records")
    return manifests[0] if manifests else None


def _manifest_units(manifest: Mapping[str, Any]) -> dict[str, UnitSpec]:
    raw = manifest.get("units", ())
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise DispatchSettlementError("stored manifest units are malformed")
    units = _units(raw)
    return {unit.unit_id: unit for unit in units}


def manifest_fact(
    *,
    subplot_id: str,
    at: str,
    dispatch_id: str,
    site: str,
    units: Iterable[UnitSpec | Mapping[str, Any]],
    casualty_threshold_percent: int = DEFAULT_THRESHOLD_PERCENT,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> dict[str, Any]:
    site_name = str(site).strip()
    if site_name not in SITES:
        raise DispatchSettlementError(f"site must be one of {sorted(SITES)}")
    normalized = _units(units)
    return run_ledger.build_fact(
        FACT_KIND,
        subplot_id=_identifier(subplot_id, field="subplot_id"),
        at=_timestamp(at),
        event=EVENT_MANIFEST,
        dispatch_id=_identifier(dispatch_id, field="dispatch_id"),
        site=site_name,
        units=[unit.to_dict() for unit in normalized],
        casualty_threshold_percent=_threshold(casualty_threshold_percent),
        max_attempts=_max_attempts(max_attempts),
    )


def spawn_fact(
    *,
    subplot_id: str,
    at: str,
    dispatch_id: str,
    unit_id: str,
    attempt: int,
    idempotency_key: str,
) -> dict[str, Any]:
    return run_ledger.build_fact(
        FACT_KIND,
        subplot_id=_identifier(subplot_id, field="subplot_id"),
        at=_timestamp(at),
        event=EVENT_SPAWN,
        dispatch_id=_identifier(dispatch_id, field="dispatch_id"),
        unit_id=_identifier(unit_id, field="unit_id"),
        attempt=_attempt(attempt),
        idempotency_key=_identifier(idempotency_key, field="idempotency_key"),
    )


def settle_fact(
    *,
    subplot_id: str,
    at: str,
    dispatch_id: str,
    unit_id: str,
    attempt: int,
    classification: str,
    reason: str,
    evidence_ref: str = "",
    evidence_sha256: str = "",
) -> dict[str, Any]:
    cls = str(classification).strip()
    if cls not in LEDGER_CLASSIFICATIONS:
        raise DispatchSettlementError(
            f"classification must be one of {sorted(LEDGER_CLASSIFICATIONS)}"
        )
    fields: dict[str, Any] = {
        "event": EVENT_SETTLE,
        "dispatch_id": _identifier(dispatch_id, field="dispatch_id"),
        "unit_id": _identifier(unit_id, field="unit_id"),
        "attempt": _attempt(attempt),
        "classification": cls,
        "reason": _bounded_text(reason, field="reason"),
    }
    if cls == SILENT_NOOP:
        if evidence_ref or evidence_sha256:
            raise DispatchSettlementError("silent-no-op must not carry fabricated evidence")
    else:
        fields["evidence_ref"] = _identifier(evidence_ref, field="evidence_ref")
        fields["evidence_sha256"] = _digest(evidence_sha256)
    return run_ledger.build_fact(
        FACT_KIND,
        subplot_id=_identifier(subplot_id, field="subplot_id"),
        at=_timestamp(at),
        **fields,
    )


def late_delivery_fact(
    *,
    subplot_id: str,
    at: str,
    dispatch_id: str,
    unit_id: str,
    attempt: int,
    evidence_ref: str,
    evidence_sha256: str,
) -> dict[str, Any]:
    return run_ledger.build_fact(
        FACT_KIND,
        subplot_id=_identifier(subplot_id, field="subplot_id"),
        at=_timestamp(at),
        event=EVENT_LATE_DELIVERY,
        dispatch_id=_identifier(dispatch_id, field="dispatch_id"),
        unit_id=_identifier(unit_id, field="unit_id"),
        attempt=_attempt(attempt),
        evidence_ref=_identifier(evidence_ref, field="evidence_ref"),
        evidence_sha256=_digest(evidence_sha256),
    )


def _canonical_fact(
    fact: Mapping[str, Any], *, expected_event: str | None = None
) -> dict[str, Any]:
    """Rebuild a settlement fact from its closed event schema and reject every extra field."""
    event = str(fact.get("event", "")).strip()
    if expected_event is not None and event != expected_event:
        raise DispatchSettlementError(f"expected {expected_event!r} settlement event")
    common = {
        "subplot_id": fact.get("subplot_id", ""),
        "at": fact.get("at", ""),
        "dispatch_id": fact.get("dispatch_id", ""),
    }
    if event == EVENT_MANIFEST:
        raw_units = fact.get("units", ())
        if not isinstance(raw_units, Sequence) or isinstance(raw_units, (str, bytes)):
            raise DispatchSettlementError("manifest units must be a list")
        canonical = manifest_fact(
            **common,
            site=str(fact.get("site", "")),
            units=raw_units,
            casualty_threshold_percent=_threshold(fact.get("casualty_threshold_percent")),
            max_attempts=_max_attempts(fact.get("max_attempts")),
        )
    elif event == EVENT_SPAWN:
        canonical = spawn_fact(
            **common,
            unit_id=fact.get("unit_id", ""),
            attempt=_attempt(fact.get("attempt")),
            idempotency_key=fact.get("idempotency_key", ""),
        )
    elif event == EVENT_SETTLE:
        canonical = settle_fact(
            **common,
            unit_id=fact.get("unit_id", ""),
            attempt=_attempt(fact.get("attempt")),
            classification=str(fact.get("classification", "")),
            reason=fact.get("reason", ""),
            evidence_ref=str(fact.get("evidence_ref", "")),
            evidence_sha256=str(fact.get("evidence_sha256", "")),
        )
    elif event == EVENT_LATE_DELIVERY:
        canonical = late_delivery_fact(
            **common,
            unit_id=fact.get("unit_id", ""),
            attempt=_attempt(fact.get("attempt")),
            evidence_ref=fact.get("evidence_ref", ""),
            evidence_sha256=fact.get("evidence_sha256", ""),
        )
    else:
        raise DispatchSettlementError(f"unknown dispatch-settlement event {event!r}")
    if dict(fact) != canonical:
        missing = sorted(set(canonical) - set(fact))
        extra = sorted(set(fact) - set(canonical))
        detail = []
        if missing:
            detail.append(f"missing={missing}")
        if extra:
            detail.append(f"extra={extra}")
        if not detail:
            detail.append("field values are not canonical")
        raise DispatchSettlementError("malformed dispatch-settlement fact: " + "; ".join(detail))
    return canonical


def _validate_stored_fact(record: Mapping[str, Any]) -> None:
    payload = {key: value for key, value in record.items() if key not in {"prev_hash", "this_hash"}}
    _canonical_fact(payload)


def append_manifest(ledger: run_ledger.RunLedger, fact: Mapping[str, Any]) -> dict[str, Any]:
    canonical = _canonical_fact(fact, expected_event=EVENT_MANIFEST)
    dispatch_id = str(canonical["dispatch_id"])

    def validate(snapshot: run_ledger.LedgerSnapshot) -> None:
        if _manifest(_fact_records(snapshot, dispatch_id)) is not None:
            raise DispatchSettlementError(f"dispatch {dispatch_id!r} already has a manifest")

    return run_ledger.append_fact_atomic(ledger, canonical, validate_snapshot=validate)


def ensure_manifest(ledger: run_ledger.RunLedger, fact: Mapping[str, Any]) -> dict[str, Any]:
    """Append a manifest once; an identical existing manifest is an idempotent success."""
    canonical = _canonical_fact(fact, expected_event=EVENT_MANIFEST)
    dispatch_id = str(canonical["dispatch_id"])
    try:
        return append_manifest(ledger, canonical)
    except DispatchSettlementError as exc:
        if "already has a manifest" not in str(exc):
            raise
    records = _fact_records(_verified_snapshot(ledger), dispatch_id)
    existing = _require_manifest(records, dispatch_id)
    immutable = {
        "schema",
        "kind",
        "subplot_id",
        "event",
        "dispatch_id",
        "site",
        "units",
        "casualty_threshold_percent",
        "max_attempts",
    }
    expected = {key: canonical.get(key) for key in immutable}
    actual = {key: existing.get(key) for key in immutable}
    if actual != expected:
        raise DispatchSettlementError(f"manifest drift for dispatch {dispatch_id!r}")
    return dict(existing)


def _require_manifest(records: Sequence[Mapping[str, Any]], dispatch_id: str) -> Mapping[str, Any]:
    manifest = _manifest(records)
    if manifest is None:
        raise DispatchSettlementError(f"dispatch {dispatch_id!r} has no manifest")
    return manifest


def append_spawn(ledger: run_ledger.RunLedger, fact: Mapping[str, Any]) -> dict[str, Any]:
    canonical = _canonical_fact(fact, expected_event=EVENT_SPAWN)
    dispatch_id = str(canonical["dispatch_id"])
    unit_id = str(canonical["unit_id"])
    attempt = int(canonical["attempt"])
    key = str(canonical["idempotency_key"])

    def validate(snapshot: run_ledger.LedgerSnapshot) -> None:
        records = _fact_records(snapshot, dispatch_id)
        manifest = _require_manifest(records, dispatch_id)
        units = _manifest_units(manifest)
        if unit_id not in units:
            raise DispatchSettlementError(f"unit {unit_id!r} is not declared in the manifest")
        if key != units[unit_id].idempotency_key:
            raise DispatchSettlementError(f"idempotency-key drift for unit {unit_id!r}")
        if attempt > _max_attempts(manifest.get("max_attempts")):
            raise DispatchSettlementError("attempt exceeds manifest max_attempts")
        spawns = [
            record
            for record in records
            if record.get("event") == EVENT_SPAWN and record.get("unit_id") == unit_id
        ]
        if any(record.get("attempt") == attempt for record in spawns):
            raise DispatchSettlementError("duplicate spawn attempt")
        previous_attempts = sorted(int(record["attempt"]) for record in spawns)
        expected_attempt = 1 if not previous_attempts else previous_attempts[-1] + 1
        if attempt != expected_attempt:
            raise DispatchSettlementError(
                f"attempt gap for unit {unit_id!r}: expected {expected_attempt}, got {attempt}"
            )
        if attempt > 1:
            previous = attempt - 1
            settled = [
                record
                for record in records
                if record.get("event") == EVENT_SETTLE
                and record.get("unit_id") == unit_id
                and record.get("attempt") == previous
            ]
            if (
                len(settled) != 1
                or settled[0].get("classification") not in CASUALTY_CLASSIFICATIONS
            ):
                raise DispatchSettlementError(
                    "retry requires one terminal non-delivered settlement"
                )
            late = any(
                record.get("event") == EVENT_LATE_DELIVERY
                and record.get("unit_id") == unit_id
                and record.get("attempt") == previous
                for record in records
            )
            if late:
                raise DispatchSettlementError("late delivery observed before retry claim")

    return run_ledger.append_fact_atomic(ledger, canonical, validate_snapshot=validate)


def append_settlement(ledger: run_ledger.RunLedger, fact: Mapping[str, Any]) -> dict[str, Any]:
    canonical = _canonical_fact(fact, expected_event=EVENT_SETTLE)
    dispatch_id = str(canonical["dispatch_id"])
    unit_id = str(canonical["unit_id"])
    attempt = int(canonical["attempt"])

    def validate(snapshot: run_ledger.LedgerSnapshot) -> None:
        records = _fact_records(snapshot, dispatch_id)
        _require_manifest(records, dispatch_id)
        spawned = any(
            record.get("event") == EVENT_SPAWN
            and record.get("unit_id") == unit_id
            and record.get("attempt") == attempt
            for record in records
        )
        if not spawned:
            raise DispatchSettlementError("settlement requires a matching spawn")
        settled = any(
            record.get("event") == EVENT_SETTLE
            and record.get("unit_id") == unit_id
            and record.get("attempt") == attempt
            for record in records
        )
        if settled:
            raise DispatchSettlementError("duplicate settlement")

    return run_ledger.append_fact_atomic(ledger, canonical, validate_snapshot=validate)


def append_late_delivery(ledger: run_ledger.RunLedger, fact: Mapping[str, Any]) -> dict[str, Any]:
    canonical = _canonical_fact(fact, expected_event=EVENT_LATE_DELIVERY)
    dispatch_id = str(canonical["dispatch_id"])
    unit_id = str(canonical["unit_id"])
    attempt = int(canonical["attempt"])

    def validate(snapshot: run_ledger.LedgerSnapshot) -> None:
        records = _fact_records(snapshot, dispatch_id)
        _require_manifest(records, dispatch_id)
        settlements = [
            record
            for record in records
            if record.get("event") == EVENT_SETTLE
            and record.get("unit_id") == unit_id
            and record.get("attempt") == attempt
        ]
        if (
            len(settlements) != 1
            or settlements[0].get("classification") not in CASUALTY_CLASSIFICATIONS
        ):
            raise DispatchSettlementError(
                "late delivery requires one prior non-delivered settlement"
            )
        if any(
            record.get("event") == EVENT_LATE_DELIVERY
            and record.get("unit_id") == unit_id
            and record.get("attempt") == attempt
            for record in records
        ):
            raise DispatchSettlementError("duplicate late delivery")

    return run_ledger.append_fact_atomic(ledger, canonical, validate_snapshot=validate)


def classify_evidence(
    expected_deliverables: Sequence[str],
    evidence: Mapping[str, Any] | None,
    *,
    expected_unit_id: str | None = None,
) -> Classification:
    """Classify trusted evidence; untrusted prose never produces a delivered result."""
    expected = {_identifier(item, field="deliverable") for item in expected_deliverables}
    if not evidence:
        return Classification(SILENT_NOOP, "no trusted delivery or runtime evidence")
    receipt_type = str(evidence.get("receipt_type", "")).strip()
    if receipt_type not in TRUSTED_RECEIPTS:
        if set(evidence) <= {"self_report", "prose"}:
            return Classification(SILENT_NOOP, "agent self-report is not settlement evidence")
        raise DispatchSettlementError(f"unknown evidence receipt_type {receipt_type!r}")
    common_keys = {"receipt_type", "trusted", "unit_id", "evidence_ref", "evidence_sha256"}
    expected_keys = common_keys | ({"outputs"} if receipt_type in DELIVERY_RECEIPTS else set())
    if set(evidence) != expected_keys:
        raise DispatchSettlementError(
            f"{receipt_type} evidence must contain exactly {sorted(expected_keys)}"
        )
    if evidence.get("trusted") is not True:
        raise DispatchSettlementError("recognized settlement evidence must be host-trusted")
    evidence_unit = _identifier(evidence.get("unit_id", ""), field="evidence unit_id")
    if expected_unit_id is not None and evidence_unit != _identifier(
        expected_unit_id, field="unit_id"
    ):
        raise DispatchSettlementError("settlement evidence unit_id does not match the spawned unit")
    evidence_ref = _identifier(evidence.get("evidence_ref", ""), field="evidence_ref")
    evidence_sha = _digest(evidence.get("evidence_sha256", ""))
    if receipt_type == RATE_RECEIPT:
        return Classification(
            RATE_KILLED, "trusted host rate-limit receipt", evidence_ref, evidence_sha
        )
    if receipt_type == IDLE_RECEIPT:
        return Classification(IDLE, "trusted runtime idle receipt", evidence_ref, evidence_sha)
    outputs_raw = evidence.get("outputs", ())
    if not isinstance(outputs_raw, Sequence) or isinstance(outputs_raw, (str, bytes)):
        raise DispatchSettlementError("delivery evidence outputs must be a list")
    normalized_outputs = [_identifier(item, field="output") for item in outputs_raw]
    if len(normalized_outputs) != len(set(normalized_outputs)):
        raise DispatchSettlementError("delivery evidence outputs must be unique")
    outputs = set(normalized_outputs)
    missing = sorted(expected - outputs)
    if missing:
        return Classification(
            SILENT_NOOP,
            f"trusted delivery evidence missing required outputs: {', '.join(missing)}",
        )
    return Classification(
        DELIVERED, "all expected deliverables present", evidence_ref, evidence_sha
    )


def settle_from_evidence(
    ledger: run_ledger.RunLedger,
    *,
    subplot_id: str,
    at: str,
    dispatch_id: str,
    unit_id: str,
    attempt: int,
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    snapshot = _verified_snapshot(ledger)
    records = _fact_records(snapshot, _identifier(dispatch_id, field="dispatch_id"))
    manifest = _require_manifest(records, dispatch_id)
    units = _manifest_units(manifest)
    if unit_id not in units:
        raise DispatchSettlementError(f"unit {unit_id!r} is not declared in the manifest")
    result = classify_evidence(units[unit_id].deliverables, evidence, expected_unit_id=unit_id)
    return settle_attempt(
        ledger,
        subplot_id=subplot_id,
        at=at,
        dispatch_id=dispatch_id,
        unit_id=unit_id,
        attempt=attempt,
        classification=result.classification,
        reason=result.reason,
        evidence_ref=result.evidence_ref,
        evidence_sha256=result.evidence_sha256,
    )


def _verified_snapshot(ledger: run_ledger.RunLedger) -> run_ledger.LedgerSnapshot:
    snapshot = run_ledger.read_snapshot(ledger)
    if not snapshot.report.ok:
        raise DispatchSettlementError(f"broken run-fact chain: {snapshot.report.reason}")
    for record in snapshot.records:
        if record.get("kind") == FACT_KIND:
            _validate_stored_fact(record)
    return snapshot


def settlement_report(ledger: run_ledger.RunLedger, dispatch_id: str) -> CasualtyReport:
    dispatch = _identifier(dispatch_id, field="dispatch_id")
    records = _fact_records(_verified_snapshot(ledger), dispatch)
    manifest = _require_manifest(records, dispatch)
    units = _manifest_units(manifest)
    threshold = _threshold(manifest.get("casualty_threshold_percent"))
    spawns = [record for record in records if record.get("event") == EVENT_SPAWN]
    settles = {
        (str(record.get("unit_id")), int(record.get("attempt", 0))): record
        for record in records
        if record.get("event") == EVENT_SETTLE
    }
    entries: list[CasualtyEntry] = []
    attempts = {1} | {int(record["attempt"]) for record in spawns}
    for attempt in sorted(attempts):
        cohort_units = (
            sorted(units)
            if attempt == 1
            else sorted(
                str(record["unit_id"]) for record in spawns if record.get("attempt") == attempt
            )
        )
        spawned_units = {
            str(record["unit_id"]) for record in spawns if record.get("attempt") == attempt
        }
        for unit_id in cohort_units:
            settlement = settles.get((unit_id, attempt))
            entries.append(
                CasualtyEntry(
                    unit_id=unit_id,
                    attempt=attempt,
                    classification=(
                        str(settlement.get("classification"))
                        if settlement is not None
                        else ("open" if unit_id in spawned_units else "unspawned")
                    ),
                    reason=(str(settlement.get("reason", "")) if settlement is not None else ""),
                    evidence_ref=(
                        str(settlement.get("evidence_ref", "")) if settlement is not None else ""
                    ),
                    spawned=unit_id in spawned_units,
                    settled=settlement is not None,
                )
            )
    cohorts: list[AttemptCohort] = []
    for attempt in sorted(attempts):
        cohort = [entry for entry in entries if entry.attempt == attempt]
        expected = len(cohort)
        settled_count = sum(entry.settled for entry in cohort)
        casualties = sum(entry.classification in CASUALTY_CLASSIFICATIONS for entry in cohort)
        complete = expected > 0 and settled_count == expected
        halt = complete and casualties * 100 > threshold * expected
        cohorts.append(
            AttemptCohort(
                attempt=attempt,
                expected=expected,
                settled=settled_count,
                casualties=casualties,
                casualty_rate_percent=(100.0 * casualties / expected if expected else None),
                threshold_percent=threshold,
                complete=complete,
                halt_required=halt,
            )
        )
    late_deliveries = {
        (str(record.get("unit_id")), _attempt(record.get("attempt")))
        for record in records
        if record.get("event") == EVENT_LATE_DELIVERY
    }
    current: list[str] = []
    for unit_id in sorted(units):
        unit_spawns = [record for record in spawns if record.get("unit_id") == unit_id]
        if not unit_spawns:
            current.append("unspawned")
            continue
        latest_attempt = max(_attempt(record.get("attempt")) for record in unit_spawns)
        settlement = settles.get((unit_id, latest_attempt))
        if settlement is None:
            current.append("open")
        elif (unit_id, latest_attempt) in late_deliveries:
            current.append(DELIVERED)
        else:
            current.append(str(settlement.get("classification")))
    current_complete = all(value in LEDGER_CLASSIFICATIONS for value in current)
    current_casualties = sum(value in CASUALTY_CLASSIFICATIONS for value in current)
    progress_halt = not current_complete or current_casualties * 100 > threshold * len(units)
    return CasualtyReport(
        dispatch_id=dispatch,
        site=str(manifest.get("site")),
        entries=tuple(entries),
        cohorts=tuple(cohorts),
        # Cohorts preserve historical casualty rates. The live gate uses each unit's latest attempt,
        # so successful bounded retry can clear a prior casualty without erasing its audit trail.
        halt_required=progress_halt,
    )


def open_positions(ledger: run_ledger.RunLedger) -> list[dict[str, Any]]:
    records = [
        record for record in _verified_snapshot(ledger).records if record.get("kind") == FACT_KIND
    ]
    settled = {
        (record.get("dispatch_id"), record.get("unit_id"), record.get("attempt"))
        for record in records
        if record.get("event") == EVENT_SETTLE
    }
    positions = [
        {
            "dispatch_id": record.get("dispatch_id"),
            "unit_id": record.get("unit_id"),
            "attempt": record.get("attempt"),
            "idempotency_key": record.get("idempotency_key"),
            "classification": "open",
        }
        for record in records
        if record.get("event") == EVENT_SPAWN
        and (record.get("dispatch_id"), record.get("unit_id"), record.get("attempt")) not in settled
    ]
    return sorted(
        positions,
        key=lambda item: (str(item["dispatch_id"]), str(item["unit_id"]), int(item["attempt"])),
    )


def dead_letters(ledger: run_ledger.RunLedger, dispatch_id: str | None = None) -> list[DeadLetter]:
    snapshot = _verified_snapshot(ledger)
    records = [
        record
        for record in snapshot.records
        if record.get("kind") == FACT_KIND
        and (dispatch_id is None or record.get("dispatch_id") == dispatch_id)
    ]
    dispatches = sorted(
        {
            str(record.get("dispatch_id"))
            for record in records
            if record.get("event") == EVENT_MANIFEST
        }
    )
    letters: list[DeadLetter] = []
    for dispatch in dispatches:
        scoped = [record for record in records if record.get("dispatch_id") == dispatch]
        manifest = _require_manifest(scoped, dispatch)
        units = _manifest_units(manifest)
        max_attempts = _max_attempts(manifest.get("max_attempts"))
        for unit_id, unit in sorted(units.items()):
            spawns = sorted(
                (
                    record
                    for record in scoped
                    if record.get("event") == EVENT_SPAWN and record.get("unit_id") == unit_id
                ),
                key=lambda record: int(record["attempt"]),
            )
            if not spawns:
                continue
            latest_attempt = int(spawns[-1]["attempt"])
            settlements = [
                record
                for record in scoped
                if record.get("event") == EVENT_SETTLE
                and record.get("unit_id") == unit_id
                and record.get("attempt") == latest_attempt
            ]
            if len(settlements) != 1:
                continue
            settlement = settlements[0]
            if settlement.get("classification") not in CASUALTY_CLASSIFICATIONS:
                continue
            if latest_attempt >= max_attempts:
                continue
            if any(
                record.get("event") == EVENT_LATE_DELIVERY
                and record.get("unit_id") == unit_id
                and record.get("attempt") == latest_attempt
                for record in scoped
            ):
                continue
            letters.append(
                DeadLetter(
                    dispatch_id=dispatch,
                    unit_id=unit_id,
                    previous_attempt=latest_attempt,
                    next_attempt=latest_attempt + 1,
                    idempotency_key=unit.idempotency_key,
                    classification=str(settlement.get("classification")),
                    reason=str(settlement.get("reason", "")),
                )
            )
    return letters


def claim_retry(
    ledger: run_ledger.RunLedger,
    *,
    subplot_id: str,
    at: str,
    dispatch_id: str,
    unit_id: str,
) -> dict[str, Any]:
    matching = [item for item in dead_letters(ledger, dispatch_id) if item.unit_id == unit_id]
    if len(matching) != 1:
        raise DispatchSettlementError("unit is not currently retry-eligible")
    item = matching[0]
    return append_spawn(
        ledger,
        spawn_fact(
            subplot_id=subplot_id,
            at=at,
            dispatch_id=dispatch_id,
            unit_id=unit_id,
            attempt=item.next_attempt,
            idempotency_key=item.idempotency_key,
        ),
    )


def terminal_attempt_status(
    ledger: run_ledger.RunLedger,
    *,
    dispatch_id: str,
    unit_id: str,
) -> dict[str, Any] | None:
    """Return a settled unit's non-retriable status without mutating either ledger."""
    dispatch = _identifier(dispatch_id, field="dispatch_id")
    unit = _identifier(unit_id, field="unit_id")
    scoped = _fact_records(_verified_snapshot(ledger), dispatch)
    manifest = _require_manifest(scoped, dispatch)
    if unit not in _manifest_units(manifest):
        raise DispatchSettlementError(f"unit {unit!r} is not declared in the manifest")
    spawns = sorted(
        (
            record
            for record in scoped
            if record.get("event") == EVENT_SPAWN and record.get("unit_id") == unit
        ),
        key=lambda record: _attempt(record.get("attempt")),
    )
    if not spawns:
        return None
    latest_attempt = _attempt(spawns[-1].get("attempt"))
    settlements = [
        record
        for record in scoped
        if record.get("event") == EVENT_SETTLE
        and record.get("unit_id") == unit
        and record.get("attempt") == latest_attempt
    ]
    if not settlements:
        return None
    if len(settlements) != 1:
        raise DispatchSettlementError("attempt has duplicate settlements")
    settlement = settlements[0]
    classification = str(settlement.get("classification"))
    late = any(
        record.get("event") == EVENT_LATE_DELIVERY
        and record.get("unit_id") == unit
        and record.get("attempt") == latest_attempt
        for record in scoped
    )
    if (
        classification in CASUALTY_CLASSIFICATIONS
        and latest_attempt < _max_attempts(manifest.get("max_attempts"))
        and not late
    ):
        return None
    status = (
        "late-delivered"
        if late
        else "already-delivered"
        if classification == DELIVERED
        else "retry-exhausted"
    )
    return {
        "status": status,
        "dispatch_id": dispatch,
        "unit_id": unit,
        "attempt": latest_attempt,
        "classification": classification,
        "reason": str(settlement.get("reason", "")),
    }


def prepare_attempt(
    ledger: run_ledger.RunLedger,
    *,
    subplot_id: str,
    at: str,
    dispatch_id: str,
    site: str,
    unit: UnitSpec | Mapping[str, Any],
    casualty_threshold_percent: int = DEFAULT_THRESHOLD_PERCENT,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> dict[str, Any]:
    """Ensure a one-unit manifest and atomically record or recover the current attempt.

    A prior open attempt is returned unchanged: its pre-call spawn already exists and replay uses the
    same stable idempotency key. A settled casualty claims the next derived DLQ attempt.
    """
    normalized = _unit(unit)
    scoped = _fact_records(_verified_snapshot(ledger), dispatch_id)
    manifest = _manifest(scoped)
    if manifest is None:
        ensure_manifest(
            ledger,
            manifest_fact(
                subplot_id=subplot_id,
                at=at,
                dispatch_id=dispatch_id,
                site=site,
                units=[normalized],
                casualty_threshold_percent=casualty_threshold_percent,
                max_attempts=max_attempts,
            ),
        )
        scoped = _fact_records(_verified_snapshot(ledger), dispatch_id)
        manifest = _require_manifest(scoped, dispatch_id)
    declared = _manifest_units(manifest).get(normalized.unit_id)
    if declared != normalized:
        raise DispatchSettlementError(
            f"unit {normalized.unit_id!r} does not match its dispatch manifest"
        )
    if manifest.get("site") != site:
        raise DispatchSettlementError("attempt site does not match its dispatch manifest")
    spawns = sorted(
        (
            record
            for record in scoped
            if record.get("event") == EVENT_SPAWN and record.get("unit_id") == normalized.unit_id
        ),
        key=lambda record: int(record["attempt"]),
    )
    if not spawns:
        return append_spawn(
            ledger,
            spawn_fact(
                subplot_id=subplot_id,
                at=at,
                dispatch_id=dispatch_id,
                unit_id=normalized.unit_id,
                attempt=1,
                idempotency_key=normalized.idempotency_key,
            ),
        )
    latest = spawns[-1]
    latest_attempt = int(latest["attempt"])
    has_settlement = any(
        record.get("event") == EVENT_SETTLE
        and record.get("unit_id") == normalized.unit_id
        and record.get("attempt") == latest_attempt
        for record in scoped
    )
    if not has_settlement:
        return dict(latest)
    terminal = terminal_attempt_status(ledger, dispatch_id=dispatch_id, unit_id=normalized.unit_id)
    if terminal is not None:
        return terminal
    return claim_retry(
        ledger,
        subplot_id=subplot_id,
        at=at,
        dispatch_id=dispatch_id,
        unit_id=normalized.unit_id,
    )


def settle_attempt(
    ledger: run_ledger.RunLedger,
    *,
    subplot_id: str,
    at: str,
    dispatch_id: str,
    unit_id: str,
    attempt: int,
    classification: str,
    reason: str,
    evidence_ref: str = "",
    evidence_sha256: str = "",
) -> dict[str, Any]:
    """Settle one bound attempt; a delivered result after a casualty is a late delivery."""
    bound_attempt = _attempt(attempt)
    scoped = _fact_records(
        _verified_snapshot(ledger), _identifier(dispatch_id, field="dispatch_id")
    )
    existing = [
        record
        for record in scoped
        if record.get("event") == EVENT_SETTLE
        and record.get("unit_id") == unit_id
        and record.get("attempt") == bound_attempt
    ]
    if len(existing) > 1:
        raise DispatchSettlementError("attempt has duplicate settlements")
    if existing:
        prior = existing[0]
        prior_classification = str(prior.get("classification"))
        if prior_classification == classification:
            comparable = {"classification", "reason", "evidence_ref", "evidence_sha256"}
            candidate = settle_fact(
                subplot_id=subplot_id,
                at=at,
                dispatch_id=dispatch_id,
                unit_id=unit_id,
                attempt=bound_attempt,
                classification=classification,
                reason=reason,
                evidence_ref=evidence_ref,
                evidence_sha256=evidence_sha256,
            )
            if {key: prior.get(key) for key in comparable} != {
                key: candidate.get(key) for key in comparable
            }:
                raise DispatchSettlementError(
                    f"attempt {bound_attempt} has contradictory settlement evidence"
                )
            return dict(prior)
        if classification == DELIVERED and prior_classification in CASUALTY_CLASSIFICATIONS:
            prior_late = next(
                (
                    record
                    for record in scoped
                    if record.get("event") == EVENT_LATE_DELIVERY
                    and record.get("unit_id") == unit_id
                    and record.get("attempt") == bound_attempt
                ),
                None,
            )
            if prior_late is not None:
                if (
                    prior_late.get("evidence_ref") != evidence_ref
                    or prior_late.get("evidence_sha256") != evidence_sha256
                ):
                    raise DispatchSettlementError(
                        f"attempt {bound_attempt} has contradictory late-delivery evidence"
                    )
                return dict(prior_late)
            return append_late_delivery(
                ledger,
                late_delivery_fact(
                    subplot_id=subplot_id,
                    at=at,
                    dispatch_id=dispatch_id,
                    unit_id=unit_id,
                    attempt=bound_attempt,
                    evidence_ref=evidence_ref,
                    evidence_sha256=evidence_sha256,
                ),
            )
        raise DispatchSettlementError(
            f"attempt {bound_attempt} already settled as {prior_classification!r}"
        )
    return append_settlement(
        ledger,
        settle_fact(
            subplot_id=subplot_id,
            at=at,
            dispatch_id=dispatch_id,
            unit_id=unit_id,
            attempt=bound_attempt,
            classification=classification,
            reason=reason,
            evidence_ref=evidence_ref,
            evidence_sha256=evidence_sha256,
        ),
    )


def reconcile_leaks(
    ledger: run_ledger.RunLedger,
    *,
    stale_worktrees: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    positions = open_positions(ledger)
    projected: list[dict[str, Any]] = []
    for raw in stale_worktrees:
        projected.append(
            {
                "dispatch_id": _identifier(
                    raw.get("dispatch_id", "worktree-registry"), field="dispatch_id"
                ),
                "unit_id": _identifier(raw.get("unit_id", ""), field="unit_id"),
                "attempt": _attempt(raw.get("attempt", 1)),
                "classification": "leaked-worktree",
                "worktree": _bounded_text(raw.get("worktree", "unknown"), field="worktree"),
            }
        )
    projected.sort(key=lambda item: (str(item["dispatch_id"]), str(item["unit_id"])))
    return {
        "open_positions": positions,
        "stale_worktrees": projected,
        "open_count": len(positions) + len(projected),
    }


def settlement_metadata(
    *,
    dispatch_id: str,
    site: str,
    units: Iterable[UnitSpec | Mapping[str, Any]],
    casualty_threshold_percent: int = DEFAULT_THRESHOLD_PERCENT,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> dict[str, Any]:
    """Deterministic, filesystem-free metadata for driver-materialized workflow settlement."""
    normalized = _units(units)
    if site not in SITES:
        raise DispatchSettlementError(f"site must be one of {sorted(SITES)}")
    return {
        "schema": "dispatch_settlement.v1",
        "dispatch_id": _identifier(dispatch_id, field="dispatch_id"),
        "site": site,
        "units": [unit.to_dict() for unit in normalized],
        "casualty_threshold_percent": _threshold(casualty_threshold_percent),
        "max_attempts": _max_attempts(max_attempts),
    }


def evidence_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def iso_at(timestamp: float) -> str:
    """Deterministic UTC ISO rendering for an injected runtime clock."""
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")


def outcome_unit(outcome_id: str, subplot_id: str) -> UnitSpec:
    """Build the stable unit contract shared by every outcome frontier cohort."""
    outcome = _identifier(outcome_id, field="outcome_id")
    subplot = _identifier(subplot_id, field="subplot_id")
    key = f"outcome:{outcome}:{subplot}"
    if len(key) > MAX_ID_LENGTH:
        key = f"outcome:{hashlib.sha256(outcome.encode()).hexdigest()[:24]}:{hashlib.sha256(subplot.encode()).hexdigest()[:24]}"
    return UnitSpec(
        unit_id=subplot,
        idempotency_key=key,
        deliverables=("canonical-completion",),
    )


def outcome_frontier_identity(
    outcome_id: str, subplot_ids: Iterable[str]
) -> tuple[str, tuple[UnitSpec, ...]]:
    """Name one complete ready-frontier cohort before any member is spawned."""
    outcome = _identifier(outcome_id, field="outcome_id")
    units = tuple(
        sorted((outcome_unit(outcome, sid) for sid in subplot_ids), key=lambda u: u.unit_id)
    )
    units = _units(units)
    roster_digest = evidence_digest([unit.unit_id for unit in units])[:24]
    dispatch_id = (
        f"outcome:{hashlib.sha256(outcome.encode()).hexdigest()[:32]}:frontier:{roster_digest}"
    )
    return _identifier(dispatch_id, field="dispatch_id"), units


def outcome_dispatch_bindings(
    ledger: run_ledger.RunLedger, outcome_id: str, subplot_ids: Iterable[str]
) -> dict[str, tuple[str, UnitSpec]]:
    """Recover each outcome unit's original cohort so retries never invent a new dispatch."""
    outcome = _identifier(outcome_id, field="outcome_id")
    wanted = {_identifier(sid, field="subplot_id") for sid in subplot_ids}
    if not wanted:
        return {}
    records = [
        record
        for record in _verified_snapshot(ledger).records
        if record.get("kind") == FACT_KIND and record.get("event") == EVENT_MANIFEST
    ]
    bindings: dict[str, tuple[str, UnitSpec]] = {}
    prefix = f"outcome:{hashlib.sha256(outcome.encode()).hexdigest()[:32]}:"
    for manifest in records:
        dispatch_id = str(manifest.get("dispatch_id", ""))
        if manifest.get("site") != "outcome" or not dispatch_id.startswith(prefix):
            continue
        for unit_id, unit in _manifest_units(manifest).items():
            if unit_id not in wanted:
                continue
            existing = bindings.get(unit_id)
            if existing is not None and existing[0] != dispatch_id:
                raise DispatchSettlementError(
                    f"outcome unit {unit_id!r} is bound to multiple dispatch cohorts"
                )
            bindings[unit_id] = (dispatch_id, unit)
    return bindings


def outcome_reports(ledger: run_ledger.RunLedger, outcome_id: str) -> list[CasualtyReport]:
    """Return every cohort report for one outcome in stable dispatch order."""
    outcome = _identifier(outcome_id, field="outcome_id")
    manifests = [
        record
        for record in _verified_snapshot(ledger).records
        if record.get("kind") == FACT_KIND
        and record.get("event") == EVENT_MANIFEST
        and record.get("site") == "outcome"
        and str(record.get("dispatch_id", "")).startswith(
            f"outcome:{hashlib.sha256(outcome.encode()).hexdigest()[:32]}:"
        )
    ]
    return [
        settlement_report(ledger, dispatch_id)
        for dispatch_id in sorted(str(record["dispatch_id"]) for record in manifests)
    ]


def latest_attempt(ledger: run_ledger.RunLedger, *, dispatch_id: str, unit_id: str) -> int | None:
    """Return the latest spawned attempt for a bound unit, if one exists."""
    records = _fact_records(_verified_snapshot(ledger), dispatch_id)
    attempts = [
        _attempt(record.get("attempt"))
        for record in records
        if record.get("event") == EVENT_SPAWN and record.get("unit_id") == unit_id
    ]
    return max(attempts) if attempts else None


def _json_value(raw: str) -> Any:
    candidate = Path(raw)
    try:
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    except OSError:
        pass
    return json.loads(raw)


def _ledger(args: argparse.Namespace) -> run_ledger.RunLedger:
    return (
        run_ledger.RunLedger(Path(args.ledger_path))
        if args.ledger_path
        else run_ledger.RunLedger.resolve(Path(args.repo_root))
    )


def _print(value: object, *, as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(value, sort_keys=True, indent=2))
    else:
        print(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch settlement ledger and derive-on-read views"
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--ledger-path", default="")
    parser.add_argument("--subplot-id", default="")
    sub = parser.add_subparsers(dest="command", required=True)

    manifest_cmd = sub.add_parser("manifest")
    manifest_cmd.add_argument("--dispatch-id", required=True)
    manifest_cmd.add_argument("--site", required=True, choices=sorted(SITES))
    manifest_cmd.add_argument("--units-json", required=True)
    manifest_cmd.add_argument("--at", required=True)
    manifest_cmd.add_argument("--casualty-threshold-percent", type=int, default=0)
    manifest_cmd.add_argument("--max-attempts", type=int, default=3)

    spawn_cmd = sub.add_parser("spawn")
    spawn_cmd.add_argument("--dispatch-id", required=True)
    spawn_cmd.add_argument("--unit-id", required=True)
    spawn_cmd.add_argument("--attempt", type=int, required=True)
    spawn_cmd.add_argument("--idempotency-key", required=True)
    spawn_cmd.add_argument("--at", required=True)

    settle_cmd = sub.add_parser("settle")
    settle_cmd.add_argument("--dispatch-id", required=True)
    settle_cmd.add_argument("--unit-id", required=True)
    settle_cmd.add_argument("--attempt", type=int, required=True)
    settle_cmd.add_argument(
        "--evidence-json",
        required=True,
        help="trusted structured receipt object/path, or null when no evidence returned",
    )
    settle_cmd.add_argument("--at", required=True)

    late_cmd = sub.add_parser("late-delivery")
    late_cmd.add_argument("--dispatch-id", required=True)
    late_cmd.add_argument("--unit-id", required=True)
    late_cmd.add_argument("--attempt", type=int, required=True)
    late_cmd.add_argument("--evidence-ref", required=True)
    late_cmd.add_argument("--evidence-sha256", required=True)
    late_cmd.add_argument("--at", required=True)

    claim_cmd = sub.add_parser("claim-retry")
    claim_cmd.add_argument("--dispatch-id", required=True)
    claim_cmd.add_argument("--unit-id", required=True)
    claim_cmd.add_argument("--at", required=True)

    report_cmd = sub.add_parser("report")
    report_cmd.add_argument("--dispatch-id", required=True)
    sub.add_parser("dlq").add_argument("--dispatch-id", default="")
    reconcile_cmd = sub.add_parser("reconcile")
    reconcile_cmd.add_argument("--leaks", action="store_true", required=True)
    reconcile_cmd.add_argument("--worktree-state-json", default="[]")
    reconcile_cmd.add_argument("--outcome-id", default="")

    args = parser.parse_args(argv)
    ledger = _ledger(args)
    subplot_id = args.subplot_id or getattr(args, "dispatch_id", "dispatch-settlement")
    try:
        if args.command == "manifest":
            raw_units = _json_value(args.units_json)
            if not isinstance(raw_units, list):
                raise DispatchSettlementError("--units-json must decode to a list")
            record = append_manifest(
                ledger,
                manifest_fact(
                    subplot_id=subplot_id,
                    at=args.at,
                    dispatch_id=args.dispatch_id,
                    site=args.site,
                    units=raw_units,
                    casualty_threshold_percent=args.casualty_threshold_percent,
                    max_attempts=args.max_attempts,
                ),
            )
            _print(record)
        elif args.command == "spawn":
            _print(
                append_spawn(
                    ledger,
                    spawn_fact(
                        subplot_id=subplot_id,
                        at=args.at,
                        dispatch_id=args.dispatch_id,
                        unit_id=args.unit_id,
                        attempt=args.attempt,
                        idempotency_key=args.idempotency_key,
                    ),
                )
            )
        elif args.command == "settle":
            evidence = _json_value(args.evidence_json)
            if evidence is not None and not isinstance(evidence, dict):
                raise DispatchSettlementError("--evidence-json must decode to an object or null")
            _print(
                settle_from_evidence(
                    ledger,
                    subplot_id=subplot_id,
                    at=args.at,
                    dispatch_id=args.dispatch_id,
                    unit_id=args.unit_id,
                    attempt=args.attempt,
                    evidence=evidence,
                )
            )
        elif args.command == "late-delivery":
            _print(
                append_late_delivery(
                    ledger,
                    late_delivery_fact(
                        subplot_id=subplot_id,
                        at=args.at,
                        dispatch_id=args.dispatch_id,
                        unit_id=args.unit_id,
                        attempt=args.attempt,
                        evidence_ref=args.evidence_ref,
                        evidence_sha256=args.evidence_sha256,
                    ),
                )
            )
        elif args.command == "claim-retry":
            _print(
                claim_retry(
                    ledger,
                    subplot_id=subplot_id,
                    at=args.at,
                    dispatch_id=args.dispatch_id,
                    unit_id=args.unit_id,
                )
            )
        elif args.command == "report":
            _print(settlement_report(ledger, args.dispatch_id).to_dict())
        elif args.command == "dlq":
            _print([asdict(item) for item in dead_letters(ledger, args.dispatch_id or None)])
        elif args.command == "reconcile":
            raw_worktrees = _json_value(args.worktree_state_json)
            if not isinstance(raw_worktrees, list):
                raise DispatchSettlementError("--worktree-state-json must decode to a list")
            if args.outcome_id:
                import outcome_store  # noqa: PLC0415 - optional outcome adapter
                import outcome_worktrees  # noqa: PLC0415 - optional outcome adapter

                store = outcome_store.Store.for_outcome(args.outcome_id, Path(args.repo_root))
                raw_worktrees.extend(
                    outcome_worktrees.stale_worktree_debits(
                        store,
                        outcome_worktrees.git_worktree_ops(Path(args.repo_root)),
                        outcome_id=args.outcome_id,
                    )
                )
            _print(reconcile_leaks(ledger, stale_worktrees=raw_worktrees))
    except (DispatchSettlementError, run_ledger.RunLedgerError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
