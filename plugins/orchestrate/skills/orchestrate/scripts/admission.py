#!/usr/bin/env python3
"""Register-owned admission: per-vendor and aggregate work-in-progress bounds.

Admission owns reservations, the queue, and the host policy. It does not own
``phase``. Occupancy for the bound is the reservation set. Rows that are
active without a reservation are reconciliation evidence, not enforcement.

The generation lock is per run and is not reentrant. Bounds are host-wide, so
every mutation takes the host admission lock first, then the run's generation
lock. Canonicalize a work location before either lock. When writing a run that
is not the caller's, use that run's stored work location.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import register as register_store

ACTIVE_PHASES = frozenset({"launching", "launched", "ready", "working"})
TERMINAL_PHASES = frozenset({"verified", "reaped"})
TERMINAL_OBSERVED = frozenset({"exited"})
HOLDING_STATES = frozenset({"reserved", "held"})
DEFAULT_LEASE_SECONDS = 3600.0
DEFAULT_PER_VENDOR = 3
DEFAULT_AGGREGATE = 7

RESERVED_TOKENS_BY_CLASS = {
    "review-max": 80000,
    "review-high": 50000,
    "work-high": 50000,
    "work-medium": 20000,
    "test-medium": 15000,
    "scan-low": 8000,
    "monitor-low": 8000,
}
DEFAULT_RESERVED_TOKENS = 20000


class AdmissionError(Exception):
    """An admission decision could not be made or recorded."""


@dataclass(frozen=True)
class AdmissionDecision:
    """The outcome of one reservation attempt."""

    status: str
    row_id: str
    vendor: str
    tokens_reserved: int
    reason: str


@dataclass(frozen=True)
class HostPolicy:
    """The host-wide bound: operator file, else module defaults."""

    per_vendor: int
    aggregate: int


def reserved_tokens_for(work_shape: str) -> int:
    return RESERVED_TOKENS_BY_CLASS.get(work_shape, DEFAULT_RESERVED_TOKENS)


def admission_lock_path() -> Path:
    return register_store.register_dir() / "admission.lock"


def policy_path() -> Path:
    # Not `*.json`: iter_live_run_ids treats every json file as a run document.
    return register_store.register_dir() / "admission.policy"


@contextmanager
def admission_locked() -> Iterator[None]:
    """Host-wide exclusive lock for per-vendor and aggregate slot mutations.

    Taken *before* the per-run generation lock. Never the reverse.
    """
    path = admission_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _admission_doc(doc: Mapping[str, Any]) -> dict[str, Any]:
    raw = doc.get("admission")
    if not isinstance(raw, dict):
        return {"queue": [], "reservations": {}}
    queue = raw.get("queue")
    reservations = raw.get("reservations")
    return {
        "queue": list(queue) if isinstance(queue, list) else [],
        "reservations": dict(reservations) if isinstance(reservations, dict) else {},
    }


def read_host_policy() -> HostPolicy | None:
    """The file, or ``None``. Absence means the module defaults, not a blank cheque."""
    path = policy_path()
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return HostPolicy(int(raw["per_vendor"]), int(raw["aggregate"]))


def resolve_host_policy(
    *,
    per_vendor: int | None = None,
    aggregate: int | None = None,
) -> HostPolicy:
    """File if present, else module defaults. Arguments override for this call only.

    Never writes. Reserve, release, and reclaim do not create a policy file.
    """
    stored = read_host_policy()
    base = stored or HostPolicy(DEFAULT_PER_VENDOR, DEFAULT_AGGREGATE)
    policy = HostPolicy(
        base.per_vendor if per_vendor is None else int(per_vendor),
        base.aggregate if aggregate is None else int(aggregate),
    )
    if policy.per_vendor < 1 or policy.aggregate < 1:
        raise AdmissionError("host policy limits must be at least 1")
    return policy


def write_host_policy(*, per_vendor: int, aggregate: int) -> HostPolicy:
    """Explicit operator-facing writer. Not called from reserve, release, or reclaim."""
    policy = HostPolicy(int(per_vendor), int(aggregate))
    if policy.per_vendor < 1 or policy.aggregate < 1:
        raise AdmissionError("host policy limits must be at least 1")
    path = policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with admission_locked():
        register_store._atomic_write_json(
            path, {"per_vendor": policy.per_vendor, "aggregate": policy.aggregate}
        )
    return policy


def host_policy() -> HostPolicy:
    """What the host will enforce without a per-call override."""
    return resolve_host_policy()


def _write_admission(
    claimed: Path,
    run_id: str,
    *,
    queue: list[Any],
    reservations: dict[str, Any],
    row_updates: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    doc = register_store._read_register_unlocked(run_id)
    stored = register_store.stored_work_location(run_id, doc)
    if stored is not None and not register_store._same_dir(claimed, stored):
        raise AdmissionError(f"run {run_id!r} is bound to {stored} and admission named {claimed}")
    if stored is None:
        if doc.get("rows"):
            raise AdmissionError(
                f"run {run_id!r} has a nonempty live register with no work location"
            )
        doc["repo_root"] = str(claimed)
    else:
        doc["repo_root"] = str(stored)
    doc["run_id"] = run_id
    doc["admission"] = {"queue": queue, "reservations": reservations}
    if row_updates:
        rows = doc["rows"]
        for row_id, fields in row_updates.items():
            if "phase" in fields:
                raise AdmissionError("admission does not write phase")
            existing = rows.get(row_id, {})
            merged = {**existing, **fields, "id": row_id, "run_id": run_id}
            if not existing:
                for column in register_store._TIME_STRATEGY_COLUMNS:
                    merged.setdefault(column, None)
            rows[row_id] = merged
        doc["rows"] = rows
    register_store._atomic_write_json(register_store.register_path(run_id), doc)


def _reservation_counts(
    reservation: Mapping[str, Any],
) -> bool:
    return isinstance(reservation, dict) and reservation.get("state") in HOLDING_STATES


def _occupancy(
    _claimed: Path | None = None,
) -> tuple[dict[str, int], int, dict[tuple[str, str], dict[str, Any]]]:
    """Per-vendor counts from reservations on every live run."""
    per_vendor: dict[str, int] = {}
    occupying: dict[tuple[str, str], dict[str, Any]] = {}
    for run_id in register_store.iter_live_run_ids():
        doc = register_store._read_register_unlocked(run_id)
        state = _admission_doc(doc)
        for row_id, reservation in state["reservations"].items():
            if not _reservation_counts(reservation):
                continue
            vendor = str(reservation.get("vendor") or "")
            occupying[(run_id, str(row_id))] = {
                "vendor": vendor,
                "source": "reservation",
                "state": reservation.get("state"),
            }
            per_vendor[vendor] = per_vendor.get(vendor, 0) + 1
    return per_vendor, sum(per_vendor.values()), occupying


def occupancy(root: Path | None = None) -> tuple[dict[str, int], int]:
    """Current host-wide per-vendor and aggregate occupancy."""
    del root
    with admission_locked():
        per_vendor, aggregate, _ = _occupancy()
    return per_vendor, aggregate


def unreserved_active(root: Path | None = None) -> tuple[tuple[str, str], ...]:
    """Rows in an active phase with no reservation. Evidence, not the bound."""
    del root
    found: list[tuple[str, str]] = []
    with admission_locked():
        _per_vendor, _aggregate, occupying = _occupancy()
        for run_id in register_store.iter_live_run_ids():
            doc = register_store._read_register_unlocked(run_id)
            for row_id, row in doc.get("rows", {}).items():
                if row.get("agent") in {"subscriber", "mirror"}:
                    continue
                if row.get("phase") not in ACTIVE_PHASES:
                    continue
                if (run_id, str(row_id)) in occupying:
                    continue
                found.append((run_id, str(row_id)))
    return tuple(found)


def _identity_matches(
    stored: Mapping[str, Any],
    *,
    vendor: str,
    work_shape: str,
    tokens: int,
) -> bool:
    return (
        str(stored.get("vendor") or "") == vendor
        and str(stored.get("work_shape") or "") == work_shape
        and int(stored.get("tokens_reserved") or 0) == tokens
    )


def reserve_slot(
    root: Path,
    row_id: str,
    *,
    run_id: str,
    vendor: str,
    work_shape: str,
    tokens_max: int | None = None,
    per_vendor_limit: int | None = None,
    aggregate_limit: int | None = None,
    now: float | None = None,
    lease_until: float | None = None,
) -> AdmissionDecision:
    """Reserve a slot or enqueue. Durable. Does not launch. Does not write phase."""
    if not row_id or not vendor:
        raise AdmissionError("row_id and vendor must be non-empty")
    claimed = register_store.canonical_work_location(root)
    run_id = register_store._safe_run_id(run_id)
    tokens = reserved_tokens_for(work_shape) if tokens_max is None else int(tokens_max)
    if tokens <= 0:
        raise AdmissionError("tokens_max must be a positive integer")
    when = time.time() if now is None else now
    with admission_locked(), register_store.generation_locked(run_id):
        policy = resolve_host_policy(per_vendor=per_vendor_limit, aggregate=aggregate_limit)
        per_vendor, aggregate, _occupying = _occupancy()
        doc = register_store._read_register_unlocked(run_id)
        state = _admission_doc(doc)
        existing = state["reservations"].get(row_id)
        if isinstance(existing, dict) and _reservation_counts(existing):
            if _identity_matches(existing, vendor=vendor, work_shape=work_shape, tokens=tokens):
                return AdmissionDecision("reserved", row_id, vendor, tokens, "already reserved")
            raise AdmissionError(
                f"row {row_id!r} is reserved for vendor {existing.get('vendor')!r} "
                f"shape {existing.get('work_shape')!r}; release and replan to change it"
            )
        queued = next(
            (
                entry
                for entry in state["queue"]
                if isinstance(entry, dict) and entry.get("row_id") == row_id
            ),
            None,
        )
        if queued is not None:
            if _identity_matches(queued, vendor=vendor, work_shape=work_shape, tokens=tokens):
                return AdmissionDecision("queued", row_id, vendor, tokens, "already queued")
            raise AdmissionError(
                f"row {row_id!r} is queued for a different vendor or shape; "
                "release and replan to change it"
            )
        row = doc.get("rows", {}).get(row_id, {})
        if row.get("phase") in TERMINAL_PHASES:
            raise AdmissionError(
                f"row {row_id!r} is {row.get('phase')}; release and replan rather than reuse it"
            )
        vendor_count = per_vendor.get(vendor, 0)
        if vendor_count >= policy.per_vendor or aggregate >= policy.aggregate:
            reason = (
                f"per-vendor bound {policy.per_vendor} reached for {vendor}"
                if vendor_count >= policy.per_vendor
                else f"aggregate bound {policy.aggregate} reached"
            )
            state["queue"].append(
                {
                    "row_id": row_id,
                    "vendor": vendor,
                    "work_shape": work_shape,
                    "tokens_reserved": tokens,
                    "enqueued_at": when,
                }
            )
            _write_admission(
                claimed,
                run_id,
                queue=state["queue"],
                reservations=state["reservations"],
                row_updates={
                    row_id: {
                        "vendor": vendor,
                        "agent": vendor,
                        "work_shape": work_shape,
                        "tokens_reserved": tokens,
                        "tokens_max": tokens,
                        "admission": "queued",
                    }
                },
            )
            return AdmissionDecision("queued", row_id, vendor, tokens, reason)
        state["reservations"][row_id] = {
            "vendor": vendor,
            "reserved_at": when,
            "work_shape": work_shape,
            "tokens_reserved": tokens,
            "state": "reserved",
            "lease_until": lease_until,
        }
        _write_admission(
            claimed,
            run_id,
            queue=state["queue"],
            reservations=state["reservations"],
            row_updates={
                row_id: {
                    "vendor": vendor,
                    "agent": vendor,
                    "work_shape": work_shape,
                    "tokens_reserved": tokens,
                    "tokens_max": tokens,
                    "admission": "reserved",
                }
            },
        )
        return AdmissionDecision("reserved", row_id, vendor, tokens, "reserved")


def activate_slot(root: Path, row_id: str, *, run_id: str, now: float | None = None) -> None:
    """Mark a matching reservation held. Does not write phase. Does not launch."""
    claimed = register_store.canonical_work_location(root)
    run_id = register_store._safe_run_id(run_id)
    when = time.time() if now is None else now
    with admission_locked(), register_store.generation_locked(run_id):
        doc = register_store._read_register_unlocked(run_id)
        state = _admission_doc(doc)
        reservation = state["reservations"].get(row_id)
        if not isinstance(reservation, dict) or reservation.get("state") not in HOLDING_STATES:
            raise AdmissionError(f"row {row_id!r} has no reservation to activate")
        reservation = dict(reservation)
        reservation["state"] = "held"
        reservation["held_at"] = when
        state["reservations"][row_id] = reservation
        _write_admission(
            claimed,
            run_id,
            queue=state["queue"],
            reservations=state["reservations"],
            row_updates={row_id: {"admission": "held"}},
        )


def abandon_slot(root: Path, row_id: str, *, run_id: str) -> None:
    """Record that a reserved child will not launch. Frees the slot."""
    release_slot(root, row_id, run_id=run_id)


def release_slot(
    root: Path,
    row_id: str,
    *,
    run_id: str,
    now: float | None = None,
) -> AdmissionDecision | None:
    """Release one reservation and advance the queue."""
    claimed = register_store.canonical_work_location(root)
    run_id = register_store._safe_run_id(run_id)
    with admission_locked():
        with register_store.generation_locked(run_id):
            doc = register_store._read_register_unlocked(run_id)
            state = _admission_doc(doc)
            reservation = state["reservations"].pop(row_id, None)
            row_updates: dict[str, dict[str, Any]] = {}
            if reservation is not None:
                row_updates[row_id] = {"admission": "released"}
            _write_admission(
                claimed,
                run_id,
                queue=state["queue"],
                reservations=state["reservations"],
                row_updates=row_updates or None,
            )
        return _advance_until_full(now=now)


def _advance_until_full(*, now: float | None) -> AdmissionDecision | None:
    """Promote while capacity remains. Caller holds the admission lock only."""
    last: AdmissionDecision | None = None
    while True:
        promoted = _advance_queue_locked(now=now)
        if promoted is None:
            return last
        last = promoted


def _advance_queue_locked(*, now: float | None) -> AdmissionDecision | None:
    """Caller holds the host admission lock and does not hold a generation lock."""
    when = time.time() if now is None else now
    policy = resolve_host_policy()
    for run_id in register_store.iter_live_run_ids():
        doc = register_store._read_register_unlocked(run_id)
        stored = register_store.stored_work_location(run_id, doc)
        if stored is None:
            continue
        state = _admission_doc(doc)
        if not state["queue"]:
            continue
        remaining: list[Any] = []
        chosen: dict[str, Any] | None = None
        dirty = False
        for entry in state["queue"]:
            if not isinstance(entry, dict):
                remaining.append(entry)
                continue
            row_id = str(entry.get("row_id") or "")
            vendor = str(entry.get("vendor") or "")
            work_shape = str(entry.get("work_shape") or "work-medium")
            tokens = int(entry.get("tokens_reserved") or reserved_tokens_for(work_shape))
            row = doc.get("rows", {}).get(row_id, {})
            per_vendor, aggregate, occupying = _occupancy()
            if (run_id, row_id) in occupying or row.get("phase") in TERMINAL_PHASES:
                dirty = True
                continue
            if chosen is None and (
                per_vendor.get(vendor, 0) < policy.per_vendor and aggregate < policy.aggregate
            ):
                chosen = {
                    "row_id": row_id,
                    "vendor": vendor,
                    "work_shape": work_shape,
                    "tokens": tokens,
                }
                dirty = True
                continue
            remaining.append(entry)
        if chosen is not None:
            row_id = str(chosen["row_id"])
            vendor = str(chosen["vendor"])
            work_shape = str(chosen["work_shape"])
            tokens = int(chosen["tokens"])
            with register_store.generation_locked(run_id):
                live = _admission_doc(register_store._read_register_unlocked(run_id))
                live["reservations"][row_id] = {
                    "vendor": vendor,
                    "reserved_at": when,
                    "work_shape": work_shape,
                    "tokens_reserved": tokens,
                    "state": "reserved",
                    "lease_until": None,
                }
                _write_admission(
                    stored,
                    run_id,
                    queue=remaining,
                    reservations=live["reservations"],
                    row_updates={
                        row_id: {
                            "admission": "reserved",
                            "tokens_reserved": tokens,
                            "tokens_max": tokens,
                            "vendor": vendor,
                            "agent": vendor,
                            "work_shape": work_shape,
                        }
                    },
                )
            return AdmissionDecision("reserved", row_id, vendor, tokens, "advanced from queue")
        if dirty:
            with register_store.generation_locked(run_id):
                live = _admission_doc(register_store._read_register_unlocked(run_id))
                _write_admission(
                    stored,
                    run_id,
                    queue=remaining,
                    reservations=live["reservations"],
                )
    return None


def advance_queue(
    root: Path | None = None, *, now: float | None = None
) -> AdmissionDecision | None:
    del root
    with admission_locked():
        return _advance_queue_locked(now=now)


def _is_dead(
    reservation: Mapping[str, Any],
    row: Mapping[str, Any],
    *,
    now: float,
    hold_lease: float,
) -> bool:
    """Reclaim from reservation state and terminal evidence, not from 'no pane'."""
    if row.get("observed_state") in TERMINAL_OBSERVED:
        return True
    if row.get("phase") in TERMINAL_PHASES:
        return True
    state = str(reservation.get("state") or "reserved")
    if state == "abandoned":
        return True
    if state == "reserved":
        lease_until = reservation.get("lease_until")
        return lease_until is not None and now >= float(lease_until)
    if state == "held":
        held_at = reservation.get("held_at", reservation.get("reserved_at"))
        started = float(held_at) if isinstance(held_at, (int, float)) else now
        return not row.get("pane_id") and (now - started) >= hold_lease
    return False


def reclaim_dead_slots(
    root: Path,
    *,
    run_id: str,
    lease_seconds: float = DEFAULT_LEASE_SECONDS,
    now: float | None = None,
) -> list[str]:
    """Release reservations whose holder is abandoned, expired, or observed dead."""
    claimed = register_store.canonical_work_location(root)
    run_id = register_store._safe_run_id(run_id)
    when = time.time() if now is None else now
    reclaimed: list[str] = []
    with admission_locked():
        with register_store.generation_locked(run_id):
            doc = register_store._read_register_unlocked(run_id)
            state = _admission_doc(doc)
            rows = doc.get("rows", {})
            kept: dict[str, Any] = {}
            updates: dict[str, dict[str, Any]] = {}
            for row_id, reservation in state["reservations"].items():
                row = rows.get(row_id, {})
                if isinstance(reservation, dict) and _is_dead(
                    reservation, row, now=when, hold_lease=lease_seconds
                ):
                    reclaimed.append(str(row_id))
                    updates[str(row_id)] = {"admission": "reclaimed"}
                else:
                    kept[row_id] = reservation
            if reclaimed:
                _write_admission(
                    claimed,
                    run_id,
                    queue=state["queue"],
                    reservations=kept,
                    row_updates=updates,
                )
        if reclaimed:
            _advance_until_full(now=now)
    return reclaimed


def queued_row_ids(root: Path, *, run_id: str) -> tuple[str, ...]:
    claimed = register_store.canonical_work_location(root)
    register_store.assert_root_belongs_to_run(claimed, run_id, require_binding=False)
    doc = register_store.read_register(run_id)
    state = _admission_doc(doc)
    ids: list[str] = []
    for entry in state["queue"]:
        if isinstance(entry, dict) and entry.get("row_id"):
            ids.append(str(entry["row_id"]))
    return tuple(ids)
