#!/usr/bin/env python3
"""Canonical append-only Team liveness facts and read-only projection (#357).

Every transition validates the complete subject identity and its predecessor while the run-fact
ledger's exclusive append lock is held.  Polling reads one verified snapshot and never heals,
creates, or appends state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_commons_shim  # noqa: E402
import run_ledger  # noqa: E402

SUBJECT_SCHEMA = "liveness.subject.v1"
EVENTS = frozenset(
    {
        "subject-open",
        "heartbeat",
        "scoped-activity-unattributed",
        "artifact-progress",
        "idle-notice",
        "idle-ack",
        "reping-intent",
        "reping-sent",
        "reping-send-failed",
        "reping-ack",
    }
)
CAUSES = frozenset(
    {"heartbeat-absent", "heartbeat-gap", "phi", "artifactless", "idle-unacknowledged"}
)
SUBJECT_KEY_KEYS = (
    "session_id",
    "subplot_id",
    "dispatch_id",
    "unit_id",
    "attempt",
    "resident_id",
    "agent_id",
    "lease_id",
    "resource_sha256",
    "broker_epoch",
    "fencing_sequence",
    "boot_id",
)
IDENTITY_KEYS = (
    "subject_schema",
    "subject_id",
    *SUBJECT_KEY_KEYS,
    "manifest_sha256",
    "spawn_sha256",
    "token_sha256",
    "ttl_seconds",
    "baseline_sha256",
    "path_set_sha256",
)
BASE_KEYS = frozenset({"schema", "kind", "subplot_id", "at", "event", "event_id", *IDENTITY_KEYS})
PAYLOAD_KEYS = {
    "subject-open": frozenset({"observed_monotonic", "source_ref"}),
    "heartbeat": frozenset({"observed_monotonic", "host_evidence_ref"}),
    "scoped-activity-unattributed": frozenset(
        {"baseline_digest", "current_digest", "interval_start", "interval_end"}
    ),
    "artifact-progress": frozenset(
        {
            "baseline_digest",
            "current_digest",
            "interval_start",
            "interval_end",
            "provenance_receipt",
            "covered_generation_ids",
        }
    ),
    "idle-notice": frozenset({"notice_id", "signal_ref", "signal_digest", "observed_monotonic"}),
    "idle-ack": frozenset({"notice_id", "ack_ref", "ack_digest", "observed_monotonic"}),
    "reping-intent": frozenset(
        {
            "generation_id",
            "cause",
            "anchor_ref",
            "opened_monotonic",
            "liveness_attempt",
            "retry_ordinal",
            "predecessor_failure_ref",
            "claim_key",
        }
    ),
    "reping-sent": frozenset(
        {
            "claim_key",
            "receipt_ref",
            "tool_use_id",
            "recipient",
            "request_digest",
            "accepted_monotonic",
            "response_window_seconds",
        }
    ),
    "reping-send-failed": frozenset(
        {"claim_key", "receipt_ref", "definitive_not_sent", "failed_monotonic"}
    ),
    "reping-ack": frozenset(
        {
            "sent_event_id",
            "response_ref",
            "correlation_digest",
            "covered_generation_ids",
            "observed_monotonic",
        }
    ),
}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SUBJECT_ID = re.compile(r"^subject:sha256:[0-9a-f]{64}$")
_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,255}$")
MAX_DEFINITIVE_NOT_SENT_RETRIES_PER_ATTEMPT = 1
_ALLOCATED_NOTICE = re.compile(r"^notice-([1-9][0-9]*)$")


class LivenessEventError(ValueError):
    """Malformed identity, event, transition, or stored liveness evidence."""


class _ReplayError(Exception):
    def __init__(self, record: dict[str, Any]) -> None:
        self.record = record


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _safe(value: object, field: str) -> str:
    if not isinstance(value, str) or not _SAFE.fullmatch(value):
        raise LivenessEventError(f"{field} must be a bounded safe identifier")
    return value


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise LivenessEventError(f"{field} must be a lowercase sha256 digest")
    return value


def _subject_id(value: object) -> str:
    if not isinstance(value, str) or not _SUBJECT_ID.fullmatch(value):
        raise LivenessEventError("subject_id must use subject:sha256:<lowercase digest>")
    return value


def _positive_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise LivenessEventError(f"{field} must be a positive integer")
    return value


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LivenessEventError(f"{field} must be a finite nonnegative number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise LivenessEventError(f"{field} must be a finite nonnegative number")
    return result


def _strings(value: object, field: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise LivenessEventError(f"{field} must be a list")
    items = tuple(_safe(item, f"{field}[]") for item in value)
    if len(items) != len(set(items)) or (nonempty and not items):
        raise LivenessEventError(f"{field} must contain unique identifiers")
    return items


@dataclass(frozen=True, slots=True)
class SubjectIdentity:
    session_id: str
    subplot_id: str
    dispatch_id: str
    unit_id: str
    attempt: int
    resident_id: str
    agent_id: str
    lease_id: str
    resource_sha256: str
    broker_epoch: str
    fencing_sequence: int
    boot_id: str
    manifest_sha256: str
    spawn_sha256: str
    token_sha256: str
    ttl_seconds: float
    baseline_sha256: str
    path_set_sha256: str

    @classmethod
    def from_dict(cls, value: object) -> SubjectIdentity:
        if not isinstance(value, dict):
            raise LivenessEventError("subject identity must be an object")
        expected = set(cls.__dataclass_fields__)
        if set(value) != expected:
            raise LivenessEventError(
                f"subject identity fields are not closed (expected {sorted(expected)})"
            )
        return cls(
            session_id=_safe(value["session_id"], "session_id"),
            subplot_id=_safe(value["subplot_id"], "subplot_id"),
            dispatch_id=_safe(value["dispatch_id"], "dispatch_id"),
            unit_id=_safe(value["unit_id"], "unit_id"),
            attempt=_positive_integer(value["attempt"], "attempt"),
            resident_id=_safe(value["resident_id"], "resident_id"),
            agent_id=_safe(value["agent_id"], "agent_id"),
            lease_id=_safe(value["lease_id"], "lease_id"),
            resource_sha256=_digest(value["resource_sha256"], "resource_sha256"),
            broker_epoch=_safe(value["broker_epoch"], "broker_epoch"),
            fencing_sequence=_positive_integer(value["fencing_sequence"], "fencing_sequence"),
            boot_id=_safe(value["boot_id"], "boot_id"),
            manifest_sha256=_digest(value["manifest_sha256"], "manifest_sha256"),
            spawn_sha256=_digest(value["spawn_sha256"], "spawn_sha256"),
            token_sha256=_digest(value["token_sha256"], "token_sha256"),
            ttl_seconds=_number(value["ttl_seconds"], "ttl_seconds"),
            baseline_sha256=_digest(value["baseline_sha256"], "baseline_sha256"),
            path_set_sha256=_digest(value["path_set_sha256"], "path_set_sha256"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "subplot_id": self.subplot_id,
            "dispatch_id": self.dispatch_id,
            "unit_id": self.unit_id,
            "attempt": self.attempt,
            "resident_id": self.resident_id,
            "agent_id": self.agent_id,
            "lease_id": self.lease_id,
            "resource_sha256": self.resource_sha256,
            "broker_epoch": self.broker_epoch,
            "fencing_sequence": self.fencing_sequence,
            "boot_id": self.boot_id,
            "manifest_sha256": self.manifest_sha256,
            "spawn_sha256": self.spawn_sha256,
            "token_sha256": self.token_sha256,
            "ttl_seconds": self.ttl_seconds,
            "baseline_sha256": self.baseline_sha256,
            "path_set_sha256": self.path_set_sha256,
        }

    @property
    def subject_id(self) -> str:
        subject_key = {key: getattr(self, key) for key in SUBJECT_KEY_KEYS}
        return f"subject:sha256:{_sha256(subject_key)}"

    def event_fields(self) -> dict[str, Any]:
        identity = self.to_dict()
        identity.pop("subplot_id")
        return {
            "subject_schema": SUBJECT_SCHEMA,
            "subject_id": self.subject_id,
            **identity,
        }


def generation_id(subject_id: str, cause: str, anchor_ref: str) -> str:
    _subject_id(subject_id)
    if cause not in CAUSES:
        raise LivenessEventError(f"unknown liveness cause {cause!r}")
    _safe(anchor_ref, "anchor_ref")
    return _sha256({"subject_id": subject_id, "cause": cause, "anchor_ref": anchor_ref})


def claim_key(
    subject_id: str,
    generation: str,
    liveness_attempt: int,
    retry_ordinal: int,
    predecessor_failure_ref: str | None,
) -> str:
    _subject_id(subject_id)
    _digest(generation, "generation_id")
    if liveness_attempt < 0 or retry_ordinal not in {0, 1}:
        raise LivenessEventError("invalid re-ping attempt or retry ordinal")
    if retry_ordinal == 0 and predecessor_failure_ref is not None:
        raise LivenessEventError("initial re-ping claim cannot have a predecessor failure")
    if retry_ordinal == 1 and predecessor_failure_ref is None:
        raise LivenessEventError("retry claim requires its predecessor failure")
    return _sha256(
        {
            "subject_id": subject_id,
            "generation_id": generation,
            "liveness_attempt": liveness_attempt,
            "retry_ordinal": retry_ordinal,
            "predecessor_failure_ref": predecessor_failure_ref,
        }
    )


def _identity_from_record(record: dict[str, Any]) -> SubjectIdentity:
    raw = {key: record.get(key) for key in SubjectIdentity.__dataclass_fields__}
    return SubjectIdentity.from_dict(raw)


def _validate_record(record: dict[str, Any]) -> None:
    event = record.get("event")
    if event not in EVENTS:
        raise LivenessEventError("stored liveness event is unknown")
    expected = BASE_KEYS | PAYLOAD_KEYS[str(event)] | {"prev_hash", "this_hash"}
    if set(record) != expected:
        raise LivenessEventError(f"stored {event} fields are not closed")
    identity = _identity_from_record(record)
    if record["subject_schema"] != SUBJECT_SCHEMA or record["subject_id"] != identity.subject_id:
        raise LivenessEventError("stored liveness subject identity is inconsistent")
    if record["subplot_id"] != identity.subplot_id:
        raise LivenessEventError("stored liveness subplot identity is inconsistent")
    _safe(record["event_id"], "event_id")
    _validate_payload(str(event), {key: record[key] for key in PAYLOAD_KEYS[str(event)]})


def _validate_payload(event: str, payload: dict[str, Any]) -> None:
    if set(payload) != PAYLOAD_KEYS[event]:
        raise LivenessEventError(f"{event} payload fields are not closed")
    if event == "subject-open":
        _number(payload["observed_monotonic"], "observed_monotonic")
        _safe(payload["source_ref"], "source_ref")
    elif event == "heartbeat":
        _number(payload["observed_monotonic"], "observed_monotonic")
        _safe(payload["host_evidence_ref"], "host_evidence_ref")
    elif event in {"scoped-activity-unattributed", "artifact-progress"}:
        _digest(payload["baseline_digest"], "baseline_digest")
        _digest(payload["current_digest"], "current_digest")
        start = _number(payload["interval_start"], "interval_start")
        end = _number(payload["interval_end"], "interval_end")
        if end <= start:
            raise LivenessEventError("artifact observation interval must increase")
        if payload["baseline_digest"] == payload["current_digest"]:
            raise LivenessEventError("artifact activity requires a changed digest")
        if event == "artifact-progress":
            _safe(payload["provenance_receipt"], "provenance_receipt")
            _strings(payload["covered_generation_ids"], "covered_generation_ids", nonempty=True)
    elif event == "idle-notice":
        _safe(payload["notice_id"], "notice_id")
        _safe(payload["signal_ref"], "signal_ref")
        _digest(payload["signal_digest"], "signal_digest")
        _number(payload["observed_monotonic"], "observed_monotonic")
    elif event == "idle-ack":
        _safe(payload["notice_id"], "notice_id")
        _safe(payload["ack_ref"], "ack_ref")
        _digest(payload["ack_digest"], "ack_digest")
        _number(payload["observed_monotonic"], "observed_monotonic")
    elif event == "reping-intent":
        _digest(payload["generation_id"], "generation_id")
        if payload["cause"] not in CAUSES:
            raise LivenessEventError("re-ping cause is unknown")
        _safe(payload["anchor_ref"], "anchor_ref")
        _number(payload["opened_monotonic"], "opened_monotonic")
        if not isinstance(payload["liveness_attempt"], int) or payload["liveness_attempt"] < 0:
            raise LivenessEventError("liveness_attempt must be a nonnegative integer")
        if payload["retry_ordinal"] not in {0, 1}:
            raise LivenessEventError("retry_ordinal must be zero or one")
        predecessor = payload["predecessor_failure_ref"]
        if predecessor is not None:
            _safe(predecessor, "predecessor_failure_ref")
        _digest(payload["claim_key"], "claim_key")
    elif event == "reping-sent":
        _digest(payload["claim_key"], "claim_key")
        for field in ("receipt_ref", "tool_use_id", "recipient"):
            _safe(payload[field], field)
        _digest(payload["request_digest"], "request_digest")
        _number(payload["accepted_monotonic"], "accepted_monotonic")
        if _number(payload["response_window_seconds"], "response_window_seconds") <= 0:
            raise LivenessEventError("response_window_seconds must be positive")
    elif event == "reping-send-failed":
        _digest(payload["claim_key"], "claim_key")
        _safe(payload["receipt_ref"], "receipt_ref")
        if payload["definitive_not_sent"] is not True:
            raise LivenessEventError("only a definitive non-send may be recorded as failed")
        _number(payload["failed_monotonic"], "failed_monotonic")
    elif event == "reping-ack":
        _safe(payload["sent_event_id"], "sent_event_id")
        _safe(payload["response_ref"], "response_ref")
        _digest(payload["correlation_digest"], "correlation_digest")
        _strings(payload["covered_generation_ids"], "covered_generation_ids", nonempty=True)
        _number(payload["observed_monotonic"], "observed_monotonic")


def _subject_records(records: tuple[dict[str, Any], ...], subject_id: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for record in records:
        if record.get("kind") != "liveness":
            continue
        _validate_record(record)
        if record.get("subject_id") == subject_id:
            selected.append(record)
    return selected


def _event_map(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        event_id = str(record["event_id"])
        if event_id in by_id:
            raise LivenessEventError("liveness event_id is duplicated")
        by_id[event_id] = record
    return by_id


def _current_generation(
    identity: SubjectIdentity,
    records: list[dict[str, Any]],
) -> tuple[str, str, str, float]:
    opened = next(record for record in records if record["event"] == "subject-open")
    heartbeats = [record for record in records if record["event"] == "heartbeat"]
    if not heartbeats:
        cause = "heartbeat-absent"
        anchor = str(opened["event_id"])
        opened_at = float(opened["observed_monotonic"])
    else:
        latest = max(heartbeats, key=lambda record: float(record["observed_monotonic"]))
        cause = "heartbeat-gap"
        anchor = str(latest["event_id"])
        opened_at = float(latest["observed_monotonic"])
    return generation_id(identity.subject_id, cause, anchor), cause, anchor, opened_at


def _claim_candidate(
    engine: Any,
    identity: SubjectIdentity,
    records: list[dict[str, Any]],
    generation: str,
    cause: str,
    anchor_ref: str,
    opened_at: float,
    now: float,
) -> tuple[Any | None, bool, bool, int]:
    claims = [
        record
        for record in records
        if record["event"] == "reping-intent" and record["generation_id"] == generation
    ]
    by_claim = {str(record["claim_key"]): record for record in claims}
    sent = [
        record
        for record in records
        if record["event"] == "reping-sent" and record["claim_key"] in by_claim
    ]
    failed = [
        record
        for record in records
        if record["event"] == "reping-send-failed" and record["claim_key"] in by_claim
    ]
    if len(sent) != len({record["claim_key"] for record in sent}):
        raise LivenessEventError("a re-ping claim has multiple accepted-send receipts")
    if len(failed) != len({record["claim_key"] for record in failed}):
        raise LivenessEventError("a re-ping claim has multiple failure receipts")
    if {record["claim_key"] for record in sent} & {record["claim_key"] for record in failed}:
        raise LivenessEventError("a re-ping claim is both sent and failed")

    sent_by_id = {str(record["event_id"]): record for record in sent}
    acknowledged_generations: set[str] = set()
    for ack in (record for record in records if record["event"] == "reping-ack"):
        if ack["sent_event_id"] not in sent_by_id:
            continue
        acknowledged_generations.update(ack["covered_generation_ids"])
    progress = [record for record in records if record["event"] == "artifact-progress"]
    latest_sent_at = max(
        (float(record["accepted_monotonic"]) for record in sent),
        default=opened_at,
    )
    for record in progress:
        if (
            generation in record["covered_generation_ids"]
            and float(record["interval_start"]) >= opened_at
            and float(record["interval_end"]) > max(opened_at, latest_sent_at)
        ):
            acknowledged_generations.add(generation)
    if generation in acknowledged_generations:
        return None, False, False, 0

    expired = [
        record
        for record in sent
        if now > float(record["accepted_monotonic"]) + float(record["response_window_seconds"])
    ]
    expired_attempts = {
        int(by_claim[str(record["claim_key"])]["liveness_attempt"]) for record in expired
    }
    unresolved = any(
        claim["claim_key"] not in {record["claim_key"] for record in sent + failed}
        for claim in claims
    )
    blocked = any(
        by_claim[str(record["claim_key"])]["retry_ordinal"]
        == MAX_DEFINITIVE_NOT_SENT_RETRIES_PER_ATTEMPT
        for record in failed
    )
    if unresolved or blocked or len(expired_attempts) >= 3:
        return None, unresolved, blocked, len(expired_attempts)

    active_sent = [record for record in sent if record not in expired]
    if active_sent:
        return None, False, False, len(expired_attempts)

    attempt = max(expired_attempts, default=-1) + 1
    attempt_claims = [record for record in claims if record["liveness_attempt"] == attempt]
    if not attempt_claims:
        predecessor = None
        ordinal = 0
    else:
        initial = next(
            (record for record in attempt_claims if record["retry_ordinal"] == 0),
            None,
        )
        if initial is None:
            raise LivenessEventError("re-ping retry exists without its initial claim")
        failure = next(
            (record for record in failed if record["claim_key"] == initial["claim_key"]),
            None,
        )
        if failure is None:
            return None, True, False, len(expired_attempts)
        predecessor = str(failure["event_id"])
        ordinal = 1
        if any(record["retry_ordinal"] == 1 for record in attempt_claims):
            return None, True, False, len(expired_attempts)
    key = claim_key(identity.subject_id, generation, attempt, ordinal, predecessor)
    return (
        engine.RePingCandidate(
            generation_id=generation,
            cause=cause,
            liveness_attempt=attempt,
            retry_ordinal=ordinal,
            claim_key=key,
            predecessor_failure_ref=predecessor,
        ),
        False,
        False,
        len(expired_attempts),
    )


def _project_records(
    records: tuple[dict[str, Any], ...],
    subject_id: str,
    *,
    now: float,
    current_boot_id: str | None,
) -> dict[str, Any]:
    current = _number(now, "now")
    _subject_id(subject_id)
    selected = _subject_records(records, subject_id)
    opens = [record for record in selected if record["event"] == "subject-open"]
    if len(opens) != 1:
        raise LivenessEventError("liveness subject requires exactly one subject-open")
    identity = _identity_from_record(opens[0])
    for record in selected:
        if _identity_from_record(record) != identity:
            raise LivenessEventError("cross-subject identity drift in liveness history")
    _event_map(selected)
    generation, cause, anchor_ref, opened_at = _current_generation(identity, selected)
    engine = fleet_commons_shim.load("liveness_engine")
    candidate, unresolved, blocked, expired_count = _claim_candidate(
        engine,
        identity,
        selected,
        generation,
        cause,
        anchor_ref,
        opened_at,
        current,
    )
    heartbeat_times = tuple(
        float(record["observed_monotonic"]) for record in selected if record["event"] == "heartbeat"
    )
    current_sent_times = [
        float(record["accepted_monotonic"])
        for record in selected
        if record["event"] == "reping-sent"
        and any(
            claim["event"] == "reping-intent"
            and claim["claim_key"] == record["claim_key"]
            and claim["generation_id"] == generation
            for claim in selected
        )
    ]
    progress_boundary = max([opened_at, *current_sent_times])
    progress = [
        float(record["interval_end"])
        for record in selected
        if record["event"] == "artifact-progress"
        and generation in record["covered_generation_ids"]
        and float(record["interval_start"]) >= opened_at
        and float(record["interval_end"]) > progress_boundary
    ]
    unattributed = [
        float(record["interval_end"])
        for record in selected
        if record["event"] == "scoped-activity-unattributed"
    ]
    notices = {
        str(record["notice_id"]): record for record in selected if record["event"] == "idle-notice"
    }
    acked_notices = {
        str(record["notice_id"]) for record in selected if record["event"] == "idle-ack"
    }
    pending = tuple(sorted(set(notices) - acked_notices))
    sent_by_id = {
        str(record["event_id"]): record for record in selected if record["event"] == "reping-sent"
    }
    host_ack_times = [
        float(record["observed_monotonic"])
        for record in selected
        if record["event"] == "reping-ack"
        and generation in record["covered_generation_ids"]
        and record["sent_event_id"] in sent_by_id
    ]
    decision = engine.evaluate(
        engine.LivenessObservation(
            subject_id=identity.subject_id,
            now=current,
            dispatched_at=float(opens[0]["observed_monotonic"]),
            heartbeat_times=heartbeat_times,
            last_progress=max(progress, default=None),
            last_host_ack=max(host_ack_times, default=None),
            last_unattributed_activity=max(unattributed, default=None),
            pending_notice_ids=pending,
            expired_unacknowledged_reping_windows=expired_count,
            reping_candidate=candidate,
            reping_send_unresolved=unresolved,
            reping_delivery_blocked=blocked,
            ttl_seconds=identity.ttl_seconds,
            subject_boot_id=identity.boot_id,
            current_boot_id=current_boot_id or identity.boot_id,
            evidence_refs=tuple(str(record["event_id"]) for record in selected),
        )
    ).to_dict()
    decision["generation"] = {
        "generation_id": generation,
        "cause": cause,
        "anchor_ref": anchor_ref,
        "opened_monotonic": opened_at,
    }
    return decision


def poll_subject(
    ledger: run_ledger.RunLedger,
    subject_id: str,
    *,
    now: float,
    current_boot_id: str | None = None,
) -> dict[str, Any]:
    snapshot = run_ledger.read_snapshot(ledger)
    if not snapshot.report.ok:
        return {
            "schema": "liveness_decision.v1",
            "subject_id": subject_id,
            "classification": "evidence-error",
            "phi": None,
            "sample_count": 0,
            "last_heartbeat": None,
            "last_progress": None,
            "pending_notice_ids": [],
            "reping": None,
            "terminal_authority": "none",
            "reason_code": "liveness-history-error:broken-chain",
            "evidence_refs": [],
            "generation": None,
        }
    try:
        return _project_records(
            snapshot.records,
            subject_id,
            now=now,
            current_boot_id=current_boot_id,
        )
    except Exception as exc:  # noqa: BLE001 - malformed history is a typed evidence error.
        return {
            "schema": "liveness_decision.v1",
            "subject_id": subject_id,
            "classification": "evidence-error",
            "phi": None,
            "sample_count": 0,
            "last_heartbeat": None,
            "last_progress": None,
            "pending_notice_ids": [],
            "reping": None,
            "terminal_authority": "none",
            "reason_code": f"liveness-history-error:{type(exc).__name__}",
            "evidence_refs": [],
            "generation": None,
        }


def _same_unhashed(existing: dict[str, Any], fact: dict[str, Any]) -> bool:
    return {
        key: value for key, value in existing.items() if key not in {"prev_hash", "this_hash"}
    } == fact


def _validate_transition(
    snapshot: run_ledger.LedgerSnapshot,
    identity: SubjectIdentity,
    fact: dict[str, Any],
) -> None:
    all_liveness = [record for record in snapshot.records if record.get("kind") == "liveness"]
    for record in all_liveness:
        _validate_record(record)
        if record["event_id"] == fact["event_id"]:
            if _same_unhashed(record, fact):
                raise _ReplayError(record)
            raise LivenessEventError("event_id replay changes immutable liveness evidence")
    selected = [record for record in all_liveness if record["subject_id"] == identity.subject_id]
    event = str(fact["event"])
    if event == "subject-open":
        if selected:
            raise LivenessEventError("subject-open identity drift or duplicate open")
        manifests = [
            record
            for record in snapshot.records
            if record.get("kind") == "dispatch-settlement"
            and record.get("event") == "manifest"
            and record.get("subplot_id") == identity.subplot_id
            and record.get("dispatch_id") == identity.dispatch_id
            and record.get("site") == "team-execution"
            and record.get("this_hash") == identity.manifest_sha256
        ]
        if len(manifests) != 1:
            raise LivenessEventError("subject-open has no exact #351 Team manifest binding")
        units = manifests[0].get("units")
        if not isinstance(units, list) or not any(
            isinstance(unit, dict) and unit.get("unit_id") == identity.unit_id for unit in units
        ):
            raise LivenessEventError("subject-open unit is absent from its #351 manifest")
        spawns = [
            record
            for record in snapshot.records
            if record.get("kind") == "dispatch-settlement"
            and record.get("event") == "spawn"
            and record.get("subplot_id") == identity.subplot_id
            and record.get("dispatch_id") == identity.dispatch_id
            and record.get("unit_id") == identity.unit_id
            and record.get("attempt") == identity.attempt
            and record.get("this_hash") == identity.spawn_sha256
        ]
        if len(spawns) != 1:
            raise LivenessEventError("subject-open has no exact #351 spawn-attempt binding")
        return
    opens = [record for record in selected if record["event"] == "subject-open"]
    if len(opens) != 1:
        raise LivenessEventError("event requires exactly one matching subject-open")
    if any(_identity_from_record(record) != identity for record in selected):
        raise LivenessEventError("event identity does not match subject-open")
    by_id = _event_map(selected)
    opened_at = float(opens[0]["observed_monotonic"])
    if event == "heartbeat":
        at = float(fact["observed_monotonic"])
        latest = max(
            (
                float(record["observed_monotonic"])
                for record in selected
                if record["event"] == "heartbeat"
            ),
            default=opened_at,
        )
        if at < latest:
            raise LivenessEventError("heartbeat monotonic time moved backward")
    elif event in {"scoped-activity-unattributed", "artifact-progress"}:
        if fact["baseline_digest"] != identity.baseline_sha256:
            raise LivenessEventError("artifact observation does not bind the subject baseline")
        if event == "artifact-progress":
            for generation in fact["covered_generation_ids"]:
                _digest(generation, "covered_generation_ids[]")
    elif event == "idle-notice":
        if any(record.get("notice_id") == fact["notice_id"] for record in selected):
            raise LivenessEventError("idle notice identity is already used")
    elif event == "idle-ack":
        notice = next(
            (
                record
                for record in selected
                if record["event"] == "idle-notice" and record["notice_id"] == fact["notice_id"]
            ),
            None,
        )
        if notice is None:
            raise LivenessEventError("idle ack has no matching notice")
        if any(
            record["event"] == "idle-ack" and record["notice_id"] == fact["notice_id"]
            for record in selected
        ):
            raise LivenessEventError("idle notice is already acknowledged")
    elif event == "reping-intent":
        decision = _project_records(
            snapshot.records,
            identity.subject_id,
            now=float(fact["opened_monotonic"]),
            current_boot_id=identity.boot_id,
        )
        candidate = decision.get("reping")
        if not isinstance(candidate, dict):
            raise LivenessEventError("poll exposes no claimable re-ping")
        expected = {
            "generation_id": candidate["generation_id"],
            "cause": candidate["cause"],
            "liveness_attempt": candidate["liveness_attempt"],
            "retry_ordinal": candidate["retry_ordinal"],
            "predecessor_failure_ref": candidate["predecessor_failure_ref"],
            "claim_key": candidate["claim_key"],
        }
        actual = {key: fact[key] for key in expected}
        if actual != expected or fact["anchor_ref"] != decision["generation"]["anchor_ref"]:
            raise LivenessEventError("re-ping claim does not match the lock-current poll candidate")
    elif event in {"reping-sent", "reping-send-failed"}:
        claim = next(
            (
                record
                for record in selected
                if record["event"] == "reping-intent" and record["claim_key"] == fact["claim_key"]
            ),
            None,
        )
        if claim is None:
            raise LivenessEventError("send result has no matching re-ping claim")
        if any(
            record["event"] in {"reping-sent", "reping-send-failed"}
            and record["claim_key"] == fact["claim_key"]
            for record in selected
        ):
            raise LivenessEventError("re-ping claim already has a send result")
    elif event == "reping-ack":
        sent = by_id.get(str(fact["sent_event_id"]))
        if sent is None or sent["event"] != "reping-sent":
            raise LivenessEventError("re-ping ack has no matching accepted send")
        claim = next(
            record
            for record in selected
            if record["event"] == "reping-intent" and record["claim_key"] == sent["claim_key"]
        )
        if claim["generation_id"] not in fact["covered_generation_ids"]:
            raise LivenessEventError("re-ping ack does not cover its sent generation")


def append_event(
    ledger: run_ledger.RunLedger,
    identity: SubjectIdentity,
    event: str,
    *,
    event_id: str,
    at: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if event not in EVENTS:
        raise LivenessEventError(f"unknown liveness event {event!r}")
    _safe(event_id, "event_id")
    _safe(at, "at")
    _validate_payload(event, payload)
    fact = run_ledger.build_fact(
        "liveness",
        subplot_id=identity.subplot_id,
        at=at,
        event=event,
        event_id=event_id,
        **identity.event_fields(),
        **payload,
    )

    def validate(snapshot: run_ledger.LedgerSnapshot) -> None:
        _validate_transition(snapshot, identity, fact)

    try:
        return run_ledger.append_fact_atomic(ledger, fact, validate_snapshot=validate)
    except _ReplayError as replay:
        return replay.record


def append_idle_notice(
    ledger: run_ledger.RunLedger,
    identity: SubjectIdentity,
    *,
    event_id: str,
    at: str,
    host_notice_id: str | None,
    signal_ref: str,
    signal_digest: str,
    observed_monotonic: float,
) -> dict[str, Any]:
    """Append a host idle notice, allocating a subject-local ID under the ledger lock."""

    _safe(event_id, "event_id")
    _safe(at, "at")
    _safe(signal_ref, "signal_ref")
    _digest(signal_digest, "signal_digest")
    observed = _number(observed_monotonic, "observed_monotonic")
    if host_notice_id is not None:
        _safe(host_notice_id, "host_notice_id")

    def build(snapshot: run_ledger.LedgerSnapshot) -> dict[str, Any]:
        selected = [
            record
            for record in snapshot.records
            if record.get("kind") == "liveness" and record.get("subject_id") == identity.subject_id
        ]
        for record in selected:
            _validate_record(record)
            if (
                record["event"] == "idle-notice"
                and record["signal_ref"] == signal_ref
                and record["signal_digest"] == signal_digest
                and float(record["observed_monotonic"]) == observed
                and (host_notice_id is None or record["notice_id"] == host_notice_id)
            ):
                raise _ReplayError(record)
        if host_notice_id is None:
            allocated = [
                int(match.group(1))
                for record in selected
                if record["event"] == "idle-notice"
                and (match := _ALLOCATED_NOTICE.fullmatch(str(record["notice_id"]))) is not None
            ]
            notice_id = f"notice-{max(allocated, default=0) + 1}"
        else:
            notice_id = host_notice_id
        payload = {
            "notice_id": notice_id,
            "signal_ref": signal_ref,
            "signal_digest": signal_digest,
            "observed_monotonic": observed,
        }
        _validate_payload("idle-notice", payload)
        fact = run_ledger.build_fact(
            "liveness",
            subplot_id=identity.subplot_id,
            at=at,
            event="idle-notice",
            event_id=event_id,
            **identity.event_fields(),
            **payload,
        )
        _validate_transition(snapshot, identity, fact)
        return fact

    try:
        return run_ledger.append_fact_built_atomic(ledger, build)
    except _ReplayError as replay:
        return replay.record


def _json_object(raw: str, field: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LivenessEventError(f"{field} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise LivenessEventError(f"{field} must be a JSON object")
    return value


def _ledger(args: argparse.Namespace) -> run_ledger.RunLedger:
    if args.ledger:
        return run_ledger.RunLedger(Path(args.ledger))
    if not args.repo_root:
        raise LivenessEventError("--repo-root or --ledger is required")
    return run_ledger.RunLedger.resolve(Path(args.repo_root).resolve())


def _cmd_subject_id(args: argparse.Namespace) -> int:
    identity = SubjectIdentity.from_dict(_json_object(args.identity_json, "identity-json"))
    print(json.dumps({"subject_id": identity.subject_id}, sort_keys=True))
    return 0


def _cmd_append(args: argparse.Namespace) -> int:
    identity = SubjectIdentity.from_dict(_json_object(args.identity_json, "identity-json"))
    record = append_event(
        _ledger(args),
        identity,
        args.event,
        event_id=args.event_id,
        at=args.at,
        payload=_json_object(args.payload_json, "payload-json"),
    )
    print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0


def _cmd_idle_notice(args: argparse.Namespace) -> int:
    identity = SubjectIdentity.from_dict(_json_object(args.identity_json, "identity-json"))
    record = append_idle_notice(
        _ledger(args),
        identity,
        event_id=args.event_id,
        at=args.at,
        host_notice_id=args.host_notice_id,
        signal_ref=args.signal_ref,
        signal_digest=args.signal_digest,
        observed_monotonic=args.observed_monotonic,
    )
    print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0


def _cmd_poll(args: argparse.Namespace) -> int:
    decision = poll_subject(
        _ledger(args),
        args.subject_id,
        now=args.now,
        current_boot_id=args.current_boot_id,
    )
    print(json.dumps(decision, sort_keys=True, separators=(",", ":")))
    return 0


def _cmd_describe(_args: argparse.Namespace) -> int:
    engine = fleet_commons_shim.load("liveness_engine")
    engine_path = Path(str(engine.__file__))
    print(
        json.dumps(
            {
                "subject_schema": SUBJECT_SCHEMA,
                "decision_schema": engine.DECISION_SCHEMA,
                "engine_protocol_version": engine.PROTOCOL_VERSION,
                "engine_sha256": hashlib.sha256(engine_path.read_bytes()).hexdigest(),
                "fleet_core_version": fleet_commons_shim.resolved_version(),
                "events": sorted(EVENTS),
                "max_definitive_not_sent_retries_per_attempt": (
                    MAX_DEFINITIVE_NOT_SENT_RETRIES_PER_ATTEMPT
                ),
            },
            sort_keys=True,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Saga canonical Team liveness fact protocol")
    parser.add_argument("--repo-root")
    parser.add_argument("--ledger")
    commands = parser.add_subparsers(dest="command", required=True)
    sid = commands.add_parser("subject-id")
    sid.add_argument("--identity-json", required=True)
    sid.set_defaults(func=_cmd_subject_id)
    append = commands.add_parser("append")
    append.add_argument("--identity-json", required=True)
    append.add_argument("--event", choices=sorted(EVENTS), required=True)
    append.add_argument("--event-id", required=True)
    append.add_argument("--at", required=True)
    append.add_argument("--payload-json", required=True)
    append.set_defaults(func=_cmd_append)
    idle_notice = commands.add_parser("idle-notice")
    idle_notice.add_argument("--identity-json", required=True)
    idle_notice.add_argument("--event-id", required=True)
    idle_notice.add_argument("--at", required=True)
    idle_notice.add_argument("--host-notice-id")
    idle_notice.add_argument("--signal-ref", required=True)
    idle_notice.add_argument("--signal-digest", required=True)
    idle_notice.add_argument("--observed-monotonic", type=float, required=True)
    idle_notice.set_defaults(func=_cmd_idle_notice)
    poll = commands.add_parser("poll")
    poll.add_argument("--subject-id", required=True)
    poll.add_argument("--now", type=float, required=True)
    poll.add_argument("--current-boot-id")
    poll.set_defaults(func=_cmd_poll)
    describe = commands.add_parser("describe")
    describe.set_defaults(func=_cmd_describe)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except LivenessEventError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
