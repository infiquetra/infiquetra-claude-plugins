#!/usr/bin/env python3
"""Register-owned admission: per-vendor and aggregate work-in-progress bounds.

Reservations are durable rows in the live register, not process memory. A rejected
child and a queued child are different outcomes: exceeding a per-vendor bound
enqueues even when aggregate capacity remains, and :func:`advance_queue` is the
only thing that turns a queued child into a reservation.

The generation lock is per run and is not reentrant. Per-vendor and aggregate
bounds span runs, so every mutation here takes the host admission lock first,
then the run's generation lock, and writes the document itself (queue and
reservations live at the document root). Canonicalize the work location before
either lock.
"""

from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import register as register_store

ACTIVE_PHASES = frozenset({"launching", "launched", "ready", "working"})
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


def reserved_tokens_for(work_shape: str) -> int:
    return RESERVED_TOKENS_BY_CLASS.get(work_shape, DEFAULT_RESERVED_TOKENS)


def admission_lock_path() -> Path:
    return register_store.register_dir() / "admission.lock"


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
            existing = rows.get(row_id, {})
            merged = {**existing, **fields, "id": row_id, "run_id": run_id}
            if not existing:
                for column in register_store._TIME_STRATEGY_COLUMNS:
                    merged.setdefault(column, None)
            rows[row_id] = merged
        doc["rows"] = rows
    register_store._atomic_write_json(register_store.register_path(run_id), doc)


def _occupancy(
    claimed: Path,
) -> tuple[dict[str, int], int, dict[tuple[str, str], dict[str, Any]]]:
    """Per-vendor counts, aggregate count, and occupying (run, row) pairs."""
    per_vendor: dict[str, int] = {}
    occupying: dict[tuple[str, str], dict[str, Any]] = {}
    for run_id in register_store.iter_live_run_ids():
        doc = register_store._read_register_unlocked(run_id)
        stored = register_store.stored_work_location(run_id, doc)
        if stored is None or not register_store._same_dir(stored, claimed):
            continue
        state = _admission_doc(doc)
        for row_id, reservation in state["reservations"].items():
            if not isinstance(reservation, dict):
                continue
            vendor = str(reservation.get("vendor") or "")
            occupying[(run_id, str(row_id))] = {
                "vendor": vendor,
                "source": "reservation",
            }
            per_vendor[vendor] = per_vendor.get(vendor, 0) + 1
        for row_id, row in doc.get("rows", {}).items():
            key = (run_id, str(row_id))
            if key in occupying:
                continue
            if row.get("phase") in ACTIVE_PHASES:
                vendor = str(row.get("vendor") or row.get("agent") or "")
                occupying[key] = {"vendor": vendor, "source": "phase"}
                per_vendor[vendor] = per_vendor.get(vendor, 0) + 1
    return per_vendor, sum(per_vendor.values()), occupying


def occupancy(root: Path) -> tuple[dict[str, int], int]:
    """Current per-vendor and aggregate occupancy for this work location."""
    claimed = register_store.canonical_work_location(root)
    with admission_locked():
        per_vendor, aggregate, _ = _occupancy(claimed)
    return per_vendor, aggregate


def reserve_slot(
    root: Path,
    row_id: str,
    *,
    run_id: str,
    vendor: str,
    work_shape: str,
    per_vendor_limit: int = DEFAULT_PER_VENDOR,
    aggregate_limit: int = DEFAULT_AGGREGATE,
    now: float | None = None,
) -> AdmissionDecision:
    """Reserve a slot or enqueue. Durable. Does not launch."""
    if not row_id or not vendor:
        raise AdmissionError("row_id and vendor must be non-empty")
    claimed = register_store.canonical_work_location(root)
    run_id = register_store._safe_run_id(run_id)
    tokens = reserved_tokens_for(work_shape)
    when = time.time() if now is None else now
    with admission_locked(), register_store.generation_locked(run_id):
        per_vendor, aggregate, occupying = _occupancy(claimed)
        if (run_id, row_id) in occupying:
            return AdmissionDecision("reserved", row_id, vendor, tokens, "already reserved")
        doc = register_store._read_register_unlocked(run_id)
        state = _admission_doc(doc)
        if any(
            isinstance(entry, dict) and entry.get("row_id") == row_id for entry in state["queue"]
        ):
            return AdmissionDecision(
                "queued",
                row_id,
                vendor,
                tokens,
                "already queued",
            )
        vendor_count = per_vendor.get(vendor, 0)
        if vendor_count >= per_vendor_limit:
            state["queue"].append(
                {
                    "row_id": row_id,
                    "vendor": vendor,
                    "work_shape": work_shape,
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
                        "phase": "planned",
                        "vendor": vendor,
                        "agent": vendor,
                        "work_shape": work_shape,
                        "tokens_reserved": tokens,
                        "admission": "queued",
                    }
                },
            )
            return AdmissionDecision(
                "queued",
                row_id,
                vendor,
                tokens,
                f"per-vendor bound {per_vendor_limit} reached for {vendor}",
            )
        if aggregate >= aggregate_limit:
            state["queue"].append(
                {
                    "row_id": row_id,
                    "vendor": vendor,
                    "work_shape": work_shape,
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
                        "phase": "planned",
                        "vendor": vendor,
                        "agent": vendor,
                        "work_shape": work_shape,
                        "tokens_reserved": tokens,
                        "admission": "queued",
                    }
                },
            )
            return AdmissionDecision(
                "queued",
                row_id,
                vendor,
                tokens,
                f"aggregate bound {aggregate_limit} reached",
            )
        state["reservations"][row_id] = {
            "vendor": vendor,
            "reserved_at": when,
            "work_shape": work_shape,
        }
        _write_admission(
            claimed,
            run_id,
            queue=state["queue"],
            reservations=state["reservations"],
            row_updates={
                row_id: {
                    "phase": "planned",
                    "vendor": vendor,
                    "agent": vendor,
                    "work_shape": work_shape,
                    "tokens_reserved": tokens,
                    "admission": "reserved",
                }
            },
        )
        return AdmissionDecision("reserved", row_id, vendor, tokens, "reserved")


def release_slot(
    root: Path,
    row_id: str,
    *,
    run_id: str,
    per_vendor_limit: int = DEFAULT_PER_VENDOR,
    aggregate_limit: int = DEFAULT_AGGREGATE,
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
        return _advance_queue_locked(
            claimed,
            per_vendor_limit=per_vendor_limit,
            aggregate_limit=aggregate_limit,
            now=now,
        )


def _advance_queue_locked(
    claimed: Path,
    *,
    per_vendor_limit: int,
    aggregate_limit: int,
    now: float | None,
) -> AdmissionDecision | None:
    """Caller holds the host admission lock and does not hold a generation lock."""
    when = time.time() if now is None else now
    for run_id in register_store.iter_live_run_ids():
        doc = register_store._read_register_unlocked(run_id)
        stored = register_store.stored_work_location(run_id, doc)
        if stored is None or not register_store._same_dir(stored, claimed):
            continue
        state = _admission_doc(doc)
        if not state["queue"]:
            continue
        remaining: list[Any] = []
        promoted: AdmissionDecision | None = None
        for entry in state["queue"]:
            if not isinstance(entry, dict) or promoted is not None:
                remaining.append(entry)
                continue
            row_id = str(entry.get("row_id") or "")
            vendor = str(entry.get("vendor") or "")
            work_shape = str(entry.get("work_shape") or "work-medium")
            per_vendor, aggregate, occupying = _occupancy(claimed)
            if (run_id, row_id) in occupying:
                continue
            if per_vendor.get(vendor, 0) >= per_vendor_limit or aggregate >= aggregate_limit:
                remaining.append(entry)
                continue
            tokens = reserved_tokens_for(work_shape)
            with register_store.generation_locked(run_id):
                live = _admission_doc(register_store._read_register_unlocked(run_id))
                live["reservations"][row_id] = {
                    "vendor": vendor,
                    "reserved_at": when,
                    "work_shape": work_shape,
                }
                live_queue = [
                    item
                    for item in live["queue"]
                    if not (isinstance(item, dict) and item.get("row_id") == row_id)
                ]
                _write_admission(
                    claimed,
                    run_id,
                    queue=live_queue,
                    reservations=live["reservations"],
                    row_updates={
                        row_id: {
                            "admission": "reserved",
                            "tokens_reserved": tokens,
                            "vendor": vendor,
                            "agent": vendor,
                            "work_shape": work_shape,
                            "phase": "planned",
                        }
                    },
                )
            promoted = AdmissionDecision("reserved", row_id, vendor, tokens, "advanced from queue")
        if promoted is not None:
            return promoted
    return None


def advance_queue(
    root: Path,
    *,
    per_vendor_limit: int = DEFAULT_PER_VENDOR,
    aggregate_limit: int = DEFAULT_AGGREGATE,
    now: float | None = None,
) -> AdmissionDecision | None:
    claimed = register_store.canonical_work_location(root)
    with admission_locked():
        return _advance_queue_locked(
            claimed,
            per_vendor_limit=per_vendor_limit,
            aggregate_limit=aggregate_limit,
            now=now,
        )


def reclaim_dead_slots(
    root: Path,
    *,
    run_id: str,
    lease_seconds: float = DEFAULT_LEASE_SECONDS,
    now: float | None = None,
    per_vendor_limit: int = DEFAULT_PER_VENDOR,
    aggregate_limit: int = DEFAULT_AGGREGATE,
) -> list[str]:
    """Release reservations whose holder died or whose row is already reaped."""
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
                reserved_at = (
                    float(reservation["reserved_at"])
                    if isinstance(reservation, dict)
                    and isinstance(reservation.get("reserved_at"), (int, float))
                    else when
                )
                phase = row.get("phase")
                pane_id = row.get("pane_id")
                dead = phase == "reaped" or (not pane_id and (when - reserved_at) >= lease_seconds)
                if dead:
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
            _advance_queue_locked(
                claimed,
                per_vendor_limit=per_vendor_limit,
                aggregate_limit=aggregate_limit,
                now=now,
            )
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
