"""One append-only, hash-chained, producer-owned run-fact ledger (`run_fact.v1`, #401).

A single canonical shape for realized-run telemetry — spend / cache / engine-usage / delegation — that
the wave-1 writers (#349, #351, #366/#367, #386, #393, …) all append into, so the fleet inherits one
format instead of N incompatible ones. Landed empty of most consumers on purpose (#338 substrate-first).

Design (KTD1-KTD7 of the #401 plan):

* **Saga-local, distinct from the replay ledger.** This is *not* `outcome_store`'s replay
  `ledger.jsonl` (append-only but un-chained, for crash-replay). The run-fact ledger is a separate,
  **hash-chained** file under `<git-common-dir>/saga-run-facts/run-facts.jsonl` that reuses the same
  durable-append discipline (`resolve_common_dir`, `O_APPEND`, `_heal_torn_tail`) and adds a
  `prev_hash`→`this_hash` chain.
* **Tamper-evidence, not tamper-resistance.** `verify_chain` detects any in-place mutation, reorder, or
  middle-deletion of a record (each `this_hash` covers the record incl. its `prev_hash`; each
  `prev_hash` pins its predecessor). It does **not** defend against a full-access writer who recomputes
  a fresh consistent chain, nor against trailing truncation (a valid prefix is a valid chain) — that is
  out of scope and acceptable: the store lives in the machine-local, never-committed git-common-dir
  cache. The real threat this closes is accidental corruption + a *silent in-place bury* of a fact.
* **Producer-owned, derive-on-read.** Every fact carries the `subplot_id` it accounts for. Ordinary
  runtime telemetry is leaf-produced; coordinator/driver-owned dispatch settlement is the explicit
  exception because manifest and pre-submit spawn facts must exist before a leaf can write. There is
  **no committed status/summary field** — views are computed from the record stream on each read.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sys
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome_store  # noqa: E402  (after the sys.path shim, by design)

RUN_FACT_SCHEMA = "run_fact.v1"
FACT_KINDS = frozenset(
    {
        "spend",
        "cache",
        "engine",
        "delegation",
        "reconciliation",
        "benchmark",
        "dispatch-settlement",
        "liveness",
        "teardown",
    }
)

# Fields set by the ledger itself (chain links) — never part of a caller-supplied fact payload.
_CHAIN_FIELDS = ("prev_hash", "this_hash")


class RunLedgerError(ValueError):
    """A malformed fact or a broken ledger invariant (distinct from a chain *verdict*)."""


@dataclass(frozen=True)
class RunLedger:
    """A handle to the single repo-level run-fact ledger file.

    Construct with an explicit ``path`` (tests, or any caller that knows the location) or resolve the
    git-common-dir location with :meth:`resolve`. One file per repo (shared across worktrees, never
    committed) so ``last_n_prior`` spans runs.
    """

    path: Path

    @classmethod
    def resolve(cls, repo_root: Path, *, runner: Callable[..., Any] | None = None) -> RunLedger:
        common = outcome_store.resolve_common_dir(repo_root, runner=runner)
        return cls(path=common / "saga-run-facts" / "run-facts.jsonl")


@dataclass(frozen=True)
class ChainReport:
    """The verdict of :func:`verify_chain`. ``ok`` is the headline; ``break_index``/``reason`` locate
    the first broken record when ``ok`` is False."""

    ok: bool
    break_index: int | None
    reason: str


@dataclass(frozen=True)
class LedgerSnapshot:
    """One lock-consistent read of the complete ledger and its chain verdict."""

    records: tuple[dict[str, Any], ...]
    report: ChainReport


# --------------------------------------------------------------------------- schema


def build_fact(kind: str, *, subplot_id: str, at: str, **fields: Any) -> dict[str, Any]:
    """Build a `run_fact.v1` payload (without chain fields). ``fields`` are the kind-specific values.

    ``subplot_id`` is the leaf or unit the fact accounts for. Most facts are leaf-produced;
    ``dispatch-settlement`` facts are coordinator/driver-produced around that leaf's runtime call.
    ``at`` is caller-supplied so the ledger remains deterministic. Rejects an unknown ``kind`` and
    any attempt to set a reserved chain field.
    """
    if kind not in FACT_KINDS:
        raise RunLedgerError(
            f"unknown run-fact kind {kind!r} (expected one of {sorted(FACT_KINDS)})"
        )
    if not subplot_id:
        raise RunLedgerError("a run-fact needs a non-empty accounted subplot_id (KTD4)")
    reserved = set(fields) & set(_CHAIN_FIELDS)
    if reserved:
        raise RunLedgerError(f"caller may not set reserved chain field(s): {sorted(reserved)}")
    return {"schema": RUN_FACT_SCHEMA, "kind": kind, "subplot_id": subplot_id, "at": at, **fields}


# --------------------------------------------------------------------------- hash chain


def _canonical(payload: dict[str, Any]) -> str:
    """Deterministic serialization for hashing — sorted keys, tight separators."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _hash(record_without_this_hash: dict[str, Any]) -> str:
    """The chain hash over a record's full content **including** its ``prev_hash`` (SHA-256)."""
    return hashlib.sha256(_canonical(record_without_this_hash).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- append / read / verify


def _lock_path(ledger: RunLedger) -> Path:
    return ledger.path.with_suffix(ledger.path.suffix + ".lock")


def _fsync_directory(path: Path) -> None:
    """Persist directory-entry changes before a caller relies on a newly created ledger."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def _write_locked(ledger: RunLedger) -> Iterator[None]:
    """Serialize ledger repair and writes with one creating exclusive advisory lock."""
    parent_existed = ledger.path.parent.exists()
    ledger.path.parent.mkdir(parents=True, exist_ok=True)
    if not parent_existed:
        _fsync_directory(ledger.path.parent.parent)
    lock_path = _lock_path(ledger)
    lock_existed = lock_path.exists()
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    if not lock_existed:
        _fsync_directory(lock_path.parent)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@contextmanager
def _read_locked(ledger: RunLedger) -> Iterator[None]:
    """Take a shared lock when one exists without creating any durable read-side state."""
    try:
        fd = os.open(_lock_path(ledger), os.O_RDONLY)
    except FileNotFoundError:
        # No writer lock exists yet. A lock-free snapshot is a valid pre-write/prefix view.
        yield
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _read_unlocked(ledger: RunLedger) -> list[dict[str, Any]]:
    try:
        raw = ledger.path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    lines = raw.splitlines()
    last = len(lines) - 1
    records: list[dict[str, Any]] = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError) as exc:
            if i == last:
                break
            raise RunLedgerError(f"corrupt run-fact line {i + 1} (not the trailing line)") from exc
        if not isinstance(obj, dict):
            if i == last:
                break
            raise RunLedgerError(f"corrupt run-fact line {i + 1}: not a JSON object")
        records.append(obj)
    return records


def _verify_records(records: Iterable[dict[str, Any]]) -> ChainReport:
    expected_prev = ""
    for i, rec in enumerate(records):
        stored = rec.get("this_hash")
        if not isinstance(stored, str) or not stored:
            return ChainReport(False, i, "record missing this_hash")
        recomputed = _hash({k: v for k, v in rec.items() if k != "this_hash"})
        if recomputed != stored:
            return ChainReport(False, i, "this_hash mismatch — record was mutated in place")
        if str(rec.get("prev_hash", "")) != expected_prev:
            return ChainReport(False, i, "prev_hash link broken — record reordered or deleted")
        expected_prev = stored
    return ChainReport(True, None, "ok")


def _snapshot_unlocked(ledger: RunLedger, *, heal: bool) -> LedgerSnapshot:
    if heal:
        outcome_store._heal_torn_tail(ledger.path)
    records = tuple(_read_unlocked(ledger))
    return LedgerSnapshot(records=records, report=_verify_records(records))


def read_snapshot(ledger: RunLedger) -> LedgerSnapshot:
    """Return one strictly non-mutating, verified, lock-consistent in-memory snapshot."""
    with _read_locked(ledger):
        return _snapshot_unlocked(ledger, heal=False)


def append_fact_atomic(
    ledger: RunLedger,
    fact: dict[str, Any],
    *,
    validate_snapshot: Callable[[LedgerSnapshot], None] | None = None,
) -> dict[str, Any]:
    """Validate state and append while holding the same lock and verified snapshot."""
    with _write_locked(ledger):
        snapshot = _snapshot_unlocked(ledger, heal=True)
        if not snapshot.report.ok:
            raise RunLedgerError(
                f"refusing append to broken run-fact chain: {snapshot.report.reason}"
            )
        if validate_snapshot is not None:
            validate_snapshot(snapshot)
        return _append_snapshot_fact_unlocked(ledger, snapshot, fact)


def _append_snapshot_fact_unlocked(
    ledger: RunLedger,
    snapshot: LedgerSnapshot,
    fact: dict[str, Any],
) -> dict[str, Any]:
    """Append one fact while the caller holds ``ledger``'s write lock."""

    prev_hash = str(snapshot.records[-1].get("this_hash", "")) if snapshot.records else ""
    record = {k: v for k, v in fact.items() if k not in _CHAIN_FIELDS}
    record["prev_hash"] = prev_hash
    record["this_hash"] = _hash(record)
    payload = memoryview((_canonical(record) + "\n").encode("utf-8"))
    ledger_existed = ledger.path.exists()
    fd = os.open(ledger.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.fchmod(fd, 0o600)
    try:
        while payload:
            written = os.write(fd, payload)
            payload = payload[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    if not ledger_existed:
        _fsync_directory(ledger.path.parent)
    return record


def append_fact_built_atomic(
    ledger: RunLedger,
    builder: Callable[[LedgerSnapshot], dict[str, Any]],
) -> dict[str, Any]:
    """Build from and append to one verified snapshot under the same write lock."""

    with _write_locked(ledger):
        snapshot = _snapshot_unlocked(ledger, heal=True)
        if not snapshot.report.ok:
            raise RunLedgerError(
                f"refusing append to broken run-fact chain: {snapshot.report.reason}"
            )
        fact = builder(snapshot)
        if not isinstance(fact, dict):
            raise RunLedgerError("atomic fact builder must return a dict")
        return _append_snapshot_fact_unlocked(ledger, snapshot, fact)


def append_fact(ledger: RunLedger, fact: dict[str, Any]) -> dict[str, Any]:
    """Chain ``fact`` onto the ledger and append it. Returns the written record (with chain fields).

    ``prev_hash`` is the current tail's ``this_hash`` (``""`` for the genesis record); ``this_hash``
    covers the whole record incl. ``prev_hash``. Reuses ``outcome_store``'s O_APPEND + torn-tail
    discipline so a concurrent or post-crash append never bricks the file.
    """
    return append_fact_atomic(ledger, fact)


def read_facts(ledger: RunLedger) -> list[dict[str, Any]]:
    """Every well-formed fact, tolerating a single torn **trailing** line (an incomplete append).

    A non-trailing corrupt/non-object line raises — the tolerance is precise, not "skip bad lines"
    (mirrors ``outcome_store.read_ledger``). A torn tail is a dropped incomplete write, **not** a chain
    break — ``verify_chain`` runs over the healed prefix.
    """
    return list(read_snapshot(ledger).records)


def _tail_hash(ledger: RunLedger) -> str:
    """The current tail record's ``this_hash`` (``""`` when the ledger is empty/absent)."""
    records = read_snapshot(ledger).records
    return str(records[-1].get("this_hash", "")) if records else ""


def verify_chain(ledger: RunLedger) -> ChainReport:
    """Recompute the chain; report the first break, if any.

    Fails (``ok=False``) on: an in-place field mutation (recomputed ``this_hash`` ≠ stored), a missing
    ``this_hash``, or a broken ``prev_hash`` link (reorder or middle-deletion). A clean trailing torn
    line is already dropped by :func:`read_facts` and is not a break. Trailing truncation of whole
    records is **not** detected (a valid prefix is a valid chain — the documented threat-model bound).
    """
    return read_snapshot(ledger).report


# --------------------------------------------------------------------------- derive-on-read views


def _facts(ledger: RunLedger, kind: str | None) -> list[dict[str, Any]]:
    facts = read_facts(ledger)
    return facts if kind is None else [f for f in facts if f.get("kind") == kind]


def _numeric_fields(records: Iterable[dict[str, Any]]) -> set[str]:
    fields: set[str] = set()
    for rec in records:
        for k, v in rec.items():
            if k in _CHAIN_FIELDS or k in ("schema", "kind", "subplot_id", "at"):
                continue
            if isinstance(v, bool):  # bool is an int subclass — exclude it from numeric aggregation
                continue
            if isinstance(v, (int, float)):
                fields.add(k)
    return fields


def rollup(ledger: RunLedger, kind: str | None = None) -> dict[str, dict[str, float]]:
    """Per-numeric-field ``{sum, avg, count}`` over the facts (optionally filtered by ``kind``).

    Derive-on-read (KTD3): computed from the record stream each call, never a committed summary.
    """
    records = _facts(ledger, kind)
    out: dict[str, dict[str, float]] = {}
    for field in sorted(_numeric_fields(records)):
        vals = [
            float(r[field])
            for r in records
            if isinstance(r.get(field), (int, float)) and not isinstance(r.get(field), bool)
        ]
        if vals:
            out[field] = {"sum": sum(vals), "avg": sum(vals) / len(vals), "count": float(len(vals))}
    return out


def reuse_ratio(ledger: RunLedger) -> float | None:
    """Cached-token reuse ratio over ``spend`` facts: cached / (cached + fresh).

    Returns ``None`` (a **defined empty**, not a crash) when there is no spend data — callers treat
    ``None`` as "no signal yet".
    """
    cached = 0.0
    fresh = 0.0
    for f in _facts(ledger, "spend"):
        c, fr = f.get("tokens_cached"), f.get("tokens_fresh")
        if isinstance(c, (int, float)) and not isinstance(c, bool):
            cached += float(c)
        if isinstance(fr, (int, float)) and not isinstance(fr, bool):
            fresh += float(fr)
    total = cached + fresh
    return cached / total if total > 0 else None


def last_n_prior(ledger: RunLedger, kind: str, field: str, n: int) -> float | None:
    """Average of ``field`` over the last ``n`` facts of ``kind`` — the "last N runs averaged X" prior.

    Returns ``None`` when there is no data for that kind/field (defined empty). ``n <= 0`` also yields
    ``None`` (no window).
    """
    if n <= 0:
        return None
    vals = [
        float(f[field])
        for f in _facts(ledger, kind)
        if isinstance(f.get(field), (int, float)) and not isinstance(f.get(field), bool)
    ]
    window = vals[-n:]
    return sum(window) / len(window) if window else None
