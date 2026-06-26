#!/usr/bin/env python3
"""Outcome store: the git-common-dir cache, completion events, locks, and replay ledger (U2).

The `OutcomeOrchestrator`'s **canonical** state is the committed `outcome-spec.json` (structure +
decision-trail + cost, U1) plus **GitHub** (completion). This module is the **performance cache and
coordination substrate** that sits beside them (R27): it lives under the repo's *git common dir* so it
is shared by every worktree of the repo but is **never committed**, and deleting it loses **no
canonical state** — the next reconcile rebuilds it from the spec + GitHub.

What lives here (KTD15 — the primitives all three plan reviewers flagged as under-defined):

* **Completion events** (R9/R10/R28) — one immutable, write-once JSON file *per leaf per attempt*
  under ``events/``. No shared append log, so two leaves finishing at once never contend; an
  idempotency key dedups exact re-delivery while a genuine retry (a new ``attempt``) proceeds.
* **Atomic + write-once writes** (R30 durability) — every mutable file is temp + ``os.replace`` (no
  reader ever sees a torn file); every write-once file is temp + ``os.link`` (atomic create that
  refuses to clobber). A malformed file is quarantined and skipped, never fatal.
* **Replay ledger** (R30) — an append-only ``ledger.jsonl`` (``O_APPEND``) of intent/commit records
  that tolerates a torn **trailing** line on read and **self-heals** it before the next append (so a
  post-crash append never merges into the broken line and bricks the ledger). ``replay_pending``
  returns intents with no matching commit so a crash *after* a side effect but *before* its commit
  record replays idempotently (the effect itself dedups via the completion-event idempotency key).
* **Leases** (R13) — a lease-based ``coordinator.lock`` (one reconcile loop mutates at a time; a
  second ``advance`` no-ops on a held lease and reclaims a stale one — the reclaim is best-effort,
  with dispatch-lock + idempotency as defense-in-depth) and per-subplot dispatch locks (no duplicate
  dispatch).
* **Offline queue** (R34) — GitHub mutations queue under ``offline-queue/`` with a retry budget and
  **exponential backoff**; on reconnect **GitHub wins for completion** (a server-superseded queued
  write is dropped, not replayed) and retry exhaustion pages the operator rather than looping.

House pattern (mirrors ``outcome_spec.py`` / ``saga.py``): pure-ish functions over an explicit
``Store`` value, dependency-injected ``runner``/``now`` so the module is unit-testable offline with no
real git repo and no wall clock, and no I/O at import.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess  # nosec B404 — git rev-parse only, no shell, fixed argv
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Make sibling scripts importable when this module is loaded by path (tests, CLI) so the
# completion-state vocabulary stays single-sourced in ``outcome_spec`` (no duplicated truth).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome_spec  # noqa: E402  (after the sys.path shim, by design)

# The subdirectory under the git common dir that holds every outcome's cache. Namespaced so it never
# collides with git's own internals or another tool's scratch space.
STORE_NAMESPACE = "saga-outcomes"

# A completion event records a leaf reaching a TERMINAL state (the only states that unlock or
# permanently close a node for the parent barrier). Single-sourced from the spec layer.
COMPLETION_STATES = outcome_spec.TERMINAL_STATES
SUCCESS_STATES = outcome_spec.SUCCESS_STATES

# Ledger phases: a side-effecting op writes an ``intent``, performs the effect, then writes a
# ``commit``. An intent with no matching commit (same idempotency key) is replayable.
LEDGER_PHASES = ("intent", "commit")


class OutcomeStoreError(ValueError):
    """A store operation violated an invariant or hit unrecoverable corruption.

    Torn trailing ledger lines and malformed individual files are NOT errors (they are tolerated /
    quarantined); this is raised only for genuinely unrecoverable conditions (e.g. git unavailable
    when resolving the common dir, or a path-traversal id).
    """


# ---------------------------------------------------------------------------
# Safe names + git-common-dir resolution (R27 — same path from every worktree)
# ---------------------------------------------------------------------------


def _safe_name(name: str, *, what: str = "id") -> str:
    """Reject a name that would escape the store directory (path traversal / separators)."""
    if not name:
        raise OutcomeStoreError(f"{what} must be non-empty")
    if "/" in name or "\\" in name or name in (".", "..") or "\x00" in name:
        raise OutcomeStoreError(f"{what} {name!r} must not contain a path separator or be '.'/'..'")
    return name


def resolve_common_dir(repo_root: Path, *, runner: Callable[..., Any] | None = None) -> Path:
    """Resolve the repo's git **common** dir as an absolute path (R27).

    ``git rev-parse --git-common-dir`` returns the *shared* git dir: ``.git`` in the main worktree
    and the **same** main-repo ``.git`` (absolute) from any linked worktree. Resolving it to an
    absolute path therefore yields an identical store root from every worktree — which is exactly
    what makes the cache shared-but-uncommitted. Raises if git is unavailable (the cache cannot be
    located, a hard error — callers fall back to canonical spec + GitHub).

    ``runner`` defaults to ``subprocess.run`` resolved at CALL time (not bound as a default arg) so
    a test can monkeypatch ``outcome_store.subprocess.run`` and have it take effect here.
    """
    run = runner if runner is not None else subprocess.run
    try:
        result = run(  # nosec B603 — fixed argv, no shell
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise OutcomeStoreError(f"could not run git to resolve the common dir: {exc}") from exc
    if getattr(result, "returncode", 1) != 0:
        raise OutcomeStoreError(
            f"git rev-parse --git-common-dir failed in {repo_root}: {(result.stderr or '').strip()}"
        )
    raw = (result.stdout or "").strip()
    if not raw:
        raise OutcomeStoreError(f"git rev-parse --git-common-dir returned nothing in {repo_root}")
    common = Path(raw)
    if not common.is_absolute():
        common = Path(repo_root) / common
    return common.resolve()


@dataclass(frozen=True)
class Store:
    """A handle to one outcome's cache directory tree under the git common dir.

    ``root`` is the per-outcome directory (``<common-dir>/saga-outcomes/<outcome-id>``). The store is
    constructed either by resolving the common dir (``Store.for_outcome``) or directly from a path
    (tests, and any caller that already knows the location).
    """

    root: Path

    @classmethod
    def for_outcome(
        cls,
        outcome_id: str,
        repo_root: Path,
        *,
        runner: Callable[..., Any] | None = None,
    ) -> Store:
        common = resolve_common_dir(repo_root, runner=runner)
        return cls(root=common / STORE_NAMESPACE / _safe_name(outcome_id, what="outcome_id"))

    @property
    def events_dir(self) -> Path:
        return self.root / "events"

    @property
    def locks_dir(self) -> Path:
        return self.root / "locks"

    @property
    def offline_dir(self) -> Path:
        return self.root / "offline-queue"

    @property
    def quarantine_dir(self) -> Path:
        return self.root / "quarantine"

    @property
    def ledger_path(self) -> Path:
        return self.root / "ledger.jsonl"

    def ensure(self) -> Store:
        """Create the directory tree (idempotent). Returns self for chaining."""
        for d in (self.events_dir, self.locks_dir, self.offline_dir, self.quarantine_dir):
            d.mkdir(parents=True, exist_ok=True)
        return self


# ---------------------------------------------------------------------------
# Atomic + write-once primitives (R30 durability)
# ---------------------------------------------------------------------------


def _unique_tmp(path: Path) -> Path:
    """A temp sibling unique per process AND thread AND instant.

    pid alone is NOT enough: two threads in one process writing the same target would share one
    temp and clobber each other (one ``os.replace`` then a spurious ``FileNotFoundError`` on the
    other). pid + thread id + a monotonic nonce makes every writer's temp distinct.
    """
    return path.with_name(
        f"{path.name}.{os.getpid()}.{threading.get_ident()}.{time.monotonic_ns()}.tmp"
    )


def _atomic_write(path: Path, content: str) -> None:
    """Overwrite ``path`` atomically (temp + ``os.replace``) so no reader sees a torn file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _unique_tmp(path)
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)  # atomic on POSIX within a filesystem


def _write_once(path: Path, content: str) -> bool:
    """Create ``path`` atomically, refusing to clobber an existing file.

    Returns True if this call created the file, False if it already existed (the write-once /
    immutability guarantee for completion events). Uses temp + ``os.link`` so a crash mid-write
    leaves only the temp file, never a torn final file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _unique_tmp(path)
    tmp.write_text(content, encoding="utf-8")
    try:
        os.link(tmp, path)  # atomic create; raises FileExistsError if path is taken
        return True
    except FileExistsError:
        return False
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()


def _read_json_or_quarantine(path: Path, *, quarantine_dir: Path) -> dict[str, Any] | None:
    """Read+parse a JSON file; on malformed content move it to ``quarantine/`` and return None.

    A malformed cache file is never fatal (R30/KTD15): it is set aside (so it stops tripping every
    read) and the caller treats it as absent. A missing file simply returns None.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        dest = quarantine_dir / f"{path.name}.{time.monotonic_ns()}"
        with contextlib.suppress(OSError):
            os.replace(path, dest)
        return None
    if not isinstance(data, dict):
        return None
    return data


# ---------------------------------------------------------------------------
# Completion events (R9 / R10 / R28) — one immutable file per leaf per attempt
# ---------------------------------------------------------------------------


@dataclass
class CompletionEvent:
    """A leaf reaching a terminal state — the durable unit that unlocks the Kahn layer (R10)."""

    subplot_id: str
    state: str
    idempotency_key: str
    attempt: int = 1
    at: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        _safe_name(self.subplot_id, what="subplot_id")
        if self.state not in COMPLETION_STATES:
            raise OutcomeStoreError(
                f"completion state {self.state!r} is not terminal {tuple(sorted(COMPLETION_STATES))}"
            )
        if not self.idempotency_key:
            raise OutcomeStoreError("completion event needs a non-empty idempotency_key")
        if not isinstance(self.attempt, int) or isinstance(self.attempt, bool) or self.attempt < 1:
            raise OutcomeStoreError(f"attempt must be an int >= 1, got {self.attempt!r}")

    @property
    def is_success(self) -> bool:
        return self.state in SUCCESS_STATES

    def to_dict(self) -> dict[str, Any]:
        return {
            "subplot_id": self.subplot_id,
            "state": self.state,
            "idempotency_key": self.idempotency_key,
            "attempt": self.attempt,
            "at": self.at,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompletionEvent:
        return cls(
            subplot_id=str(data.get("subplot_id", "")),
            state=str(data.get("state", "")),
            idempotency_key=str(data.get("idempotency_key", "")),
            attempt=int(data.get("attempt", 1)),
            at=str(data.get("at", "")),
            payload=dict(data.get("payload", {})),
        )


def _event_path(store: Store, subplot_id: str, attempt: int) -> Path:
    safe = _safe_name(subplot_id, what="subplot_id")
    return store.events_dir / f"{safe}.a{attempt}.json"


def read_completion_events(store: Store, subplot_id: str) -> list[CompletionEvent]:
    """Every recorded completion event for a subplot, ordered by attempt (malformed ones skipped)."""
    safe = _safe_name(subplot_id, what="subplot_id")
    events: list[CompletionEvent] = []
    if not store.events_dir.exists():
        return events
    for path in sorted(store.events_dir.glob(f"{safe}.a*.json")):
        data = _read_json_or_quarantine(path, quarantine_dir=store.quarantine_dir)
        if data is not None:
            events.append(CompletionEvent.from_dict(data))
    events.sort(key=lambda e: e.attempt)
    return events


def write_completion_event(store: Store, event: CompletionEvent) -> str:
    """Record a completion event, deduping exact re-delivery by idempotency key.

    Returns ``"written"`` if a new immutable event file was created, or ``"skipped"`` if an event
    with the SAME ``idempotency_key`` already exists for this subplot (a duplicate delivery). A
    genuine retry carries a new ``attempt`` (and a fresh idempotency key) and proceeds to its own
    write-once file. Two different leaves write different files, so there is no contention (R10).
    """
    event.validate()
    store.ensure()
    for existing in read_completion_events(store, event.subplot_id):
        if existing.idempotency_key == event.idempotency_key:
            return "skipped"
    path = _event_path(store, event.subplot_id, event.attempt)
    created = _write_once(path, json.dumps(event.to_dict(), indent=2, sort_keys=False) + "\n")
    if not created:
        # The write-once slot is already taken. Re-read the existing key: a concurrent delivery of
        # the SAME idempotency key lost the os.link race but is still a duplicate — converge to the
        # same idempotent "skipped" the serial dedup scan above would have returned (the read scan
        # can miss a sibling that links between our scan and our link). Only a DIFFERENT key in the
        # same subplot+attempt slot is a genuine divergent-completion conflict, which we surface.
        existing_data = _read_json_or_quarantine(path, quarantine_dir=store.quarantine_dir)
        existing_key = (existing_data or {}).get("idempotency_key")
        if existing_key == event.idempotency_key:
            return "skipped"
        raise OutcomeStoreError(
            f"completion slot {path.name} already holds a different event "
            f"(existing key {existing_key!r} != {event.idempotency_key!r}) — use a new attempt"
        )
    return "written"


def completed_subplots(store: Store, *, successful_only: bool = True) -> set[str]:
    """The set of subplot ids that have a recorded terminal completion (the frontier input, R10).

    **Success is sticky** (``successful_only=True``, default): a subplot counts as completed if ANY
    attempt reached a SUCCESS state. A later ``failed`` attempt does NOT un-complete a leaf that
    already succeeded — once a code leaf's PR merged (``done``) it stays done for unlocking
    dependents; an *earlier-than-latest* spurious re-run must never re-lock the frontier (R10). A
    genuine post-merge negative (a merged PR later closed → ``rejected``) is a distinct GitHub
    transition handled by the negative-state path (U6), not by completion-attempt recency here.

    With ``successful_only=False`` the result is every subplot that has reached ANY terminal at least
    once — the input to cascade reasoning over negative terminals (R22/R32).
    """
    done: set[str] = set()
    if not store.events_dir.exists():
        return done
    for path in sorted(store.events_dir.glob("*.a*.json")):
        data = _read_json_or_quarantine(path, quarantine_dir=store.quarantine_dir)
        if data is None:
            continue
        ev = CompletionEvent.from_dict(data)
        if ev.is_success or not successful_only:
            done.add(ev.subplot_id)
    return done


# ---------------------------------------------------------------------------
# Replay ledger (R30) — append-only, torn-trailing-line tolerant
# ---------------------------------------------------------------------------


def _heal_torn_tail(path: Path) -> None:
    """Truncate an unterminated (newline-less) trailing fragment so the next append starts clean.

    A crash mid-append — or a short ``os.write`` on ENOSPC/signal — can leave the file ending
    without a newline. Appending onto that would concatenate the new record INTO the broken line:
    the first post-crash append would be silently lost and a second would push the garbage into a
    non-trailing position, permanently bricking ``read_ledger`` (the exact crash R30's ledger exists
    to survive). Healing chops only the unterminated fragment; every complete line is preserved. The
    torn fragment was an incomplete record with no commit, so dropping it is correct — its intent (if
    any) is re-derived from the spec on the next reconcile.
    """
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            if fh.tell() == 0:
                return
            fh.seek(-1, os.SEEK_END)
            if fh.read(1) == b"\n":
                return  # clean tail — nothing to heal
            fh.seek(0)
            data = fh.read()
    except FileNotFoundError:
        return
    idx = data.rfind(b"\n")
    os.truncate(path, idx + 1)  # keep through the last newline; idx == -1 -> truncate to empty


def append_ledger(store: Store, record: dict[str, Any]) -> None:
    """Append one JSON record as a single line under ``O_APPEND`` (concurrent-writer safe).

    Heals a torn trailing fragment first (so a post-crash append never merges into a broken line),
    then writes, looping on the ``os.write`` return so a short write never itself leaves a torn line.
    A single ``os.write`` of a line under ``PIPE_BUF`` is atomic with ``O_APPEND``. Records carry at
    least a ``phase`` (``intent``/``commit``) and an idempotency ``key`` so ``replay_pending`` pairs
    them.
    """
    store.root.mkdir(parents=True, exist_ok=True)
    _heal_torn_tail(store.ledger_path)
    payload = memoryview((json.dumps(record, sort_keys=False) + "\n").encode("utf-8"))
    fd = os.open(store.ledger_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        while payload:
            written = os.write(fd, payload)
            payload = payload[written:]
    finally:
        os.close(fd)


def read_ledger(store: Store) -> list[dict[str, Any]]:
    """Read every well-formed ledger record, tolerating a single torn **trailing** line.

    A crash mid-append can leave the last line truncated; that line is dropped. Corruption that is
    NOT the trailing line raises — both an unparseable line AND a line that parses to valid JSON but
    is not an object (a bare scalar/list left by a truncation). The trailing-tear tolerance is a
    precise allowance, not a blanket "skip bad lines".
    """
    try:
        raw = store.ledger_path.read_text(encoding="utf-8")
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
                break  # torn trailing line — tolerated
            raise OutcomeStoreError(f"corrupt ledger line {i + 1} (not the trailing line)") from exc
        if not isinstance(obj, dict):
            if i == last:
                break  # a non-object trailing line — tolerated like a torn tail
            raise OutcomeStoreError(f"corrupt ledger line {i + 1}: not a JSON object")
        records.append(obj)
    return records


def replay_pending(store: Store) -> list[dict[str, Any]]:
    """Intent records with no matching commit — the ops to re-drive on crash recovery (R30).

    Pairing is by idempotency ``key``: an ``intent`` whose ``key`` never got a ``commit`` line means
    the process died after (or during) the side effect but before recording success. Re-driving is
    safe because the effect itself dedups on the same key (completion-event idempotency / GitHub
    state), so replay never double-applies.
    """
    committed: set[str] = set()
    intents: dict[str, dict[str, Any]] = {}
    for rec in read_ledger(store):
        key = str(rec.get("key", ""))
        if not key:
            continue
        phase = rec.get("phase")
        if phase == "commit":
            committed.add(key)
        elif phase == "intent":
            intents.setdefault(key, rec)
    return [rec for key, rec in intents.items() if key not in committed]


# ---------------------------------------------------------------------------
# Leases (R13) — coordinator singleton + per-subplot dispatch locks
# ---------------------------------------------------------------------------


@dataclass
class Lease:
    holder: str
    expires_at: float  # epoch seconds

    def to_dict(self) -> dict[str, Any]:
        return {"holder": self.holder, "expires_at": self.expires_at}


def _lock_path(store: Store, name: str) -> Path:
    return store.locks_dir / f"{_safe_name(name, what='lock')}.lock"


def acquire_lease(
    store: Store,
    name: str,
    holder: str,
    ttl_seconds: float,
    *,
    now: Callable[[], float] = time.time,
) -> bool:
    """Acquire (or refresh, or reclaim-if-stale) a lease. Returns True iff this holder now holds it.

    - free slot  -> created, return True (atomic, race-safe — ``os.link`` write-once);
    - held by us -> refreshed, return True;
    - held by another, **unexpired** -> return False (the second ``advance`` no-ops, R13);
    - held by another, **expired**   -> reclaimed (atomically replaced), return True.

    The free-slot create and held-fresh reject are race-safe. The stale **reclaim** is best-effort:
    two callers that both observe the same expired lease can both return True for an instant (a
    read-then-replace TOCTOU). This is acceptable here by **defense in depth**, not by luck — a brief
    double-coordinator window cannot cause a duplicate *effect* because the per-subplot dispatch lock
    (also a lease) plus completion-event idempotency are the real anti-duplication guarantees, and
    the cache is non-authoritative (GitHub wins). A true fencing token for strict single-writer
    exclusivity lands with the coordinator runtime that consumes it (U6) — adding the field here with
    no consumer would be dead wiring. Single-machine occasional-overlap is the target; cross-host
    coordination is out of core scope.
    """
    if ttl_seconds <= 0:
        raise OutcomeStoreError("lease ttl_seconds must be > 0")
    store.locks_dir.mkdir(parents=True, exist_ok=True)
    path = _lock_path(store, name)
    current = now()
    lease = Lease(holder=holder, expires_at=current + ttl_seconds)
    payload = json.dumps(lease.to_dict(), sort_keys=False) + "\n"

    if _write_once(path, payload):
        return True  # free slot, atomically created
    existing = _read_json_or_quarantine(path, quarantine_dir=store.quarantine_dir)
    if existing is None:
        # malformed/quarantined -> treat as free, take it
        _atomic_write(path, payload)
        return True
    held_by = str(existing.get("holder", ""))
    expires_at = float(existing.get("expires_at", 0))
    if held_by == holder:
        _atomic_write(path, payload)  # refresh our own lease
        return True
    if current >= expires_at:
        _atomic_write(path, payload)  # stale -> reclaim
        return True
    return False  # held and fresh


def read_lease(store: Store, name: str) -> Lease | None:
    data = _read_json_or_quarantine(_lock_path(store, name), quarantine_dir=store.quarantine_dir)
    if data is None:
        return None
    return Lease(holder=str(data.get("holder", "")), expires_at=float(data.get("expires_at", 0)))


def release_lease(store: Store, name: str, holder: str) -> bool:
    """Release a lease iff held by ``holder``. Returns True if released, False otherwise."""
    lease = read_lease(store, name)
    if lease is None or lease.holder != holder:
        return False
    try:
        _lock_path(store, name).unlink()
        return True
    except FileNotFoundError:
        return False


# Convenience wrappers for the two named lock kinds (R13).
COORDINATOR_LOCK = "coordinator"


def acquire_coordinator(
    store: Store, holder: str, ttl_seconds: float, *, now: Callable[[], float] = time.time
) -> bool:
    return acquire_lease(store, COORDINATOR_LOCK, holder, ttl_seconds, now=now)


def acquire_dispatch(
    store: Store,
    subplot_id: str,
    holder: str,
    ttl_seconds: float,
    *,
    now: Callable[[], float] = time.time,
) -> bool:
    """Per-subplot dispatch lock — prevents two coordinators dispatching the same leaf twice."""
    return acquire_lease(
        store, f"dispatch-{_safe_name(subplot_id, what='subplot_id')}", holder, ttl_seconds, now=now
    )


# ---------------------------------------------------------------------------
# Offline queue (R34) — GitHub wins for completion; retry budget; page on exhaustion
# ---------------------------------------------------------------------------

DEFAULT_MAX_ATTEMPTS = 5
# Exponential backoff base (seconds); the Nth retry waits DEFAULT_BACKOFF_BASE * 2**(attempts-1).
DEFAULT_BACKOFF_BASE = 2.0


def enqueue_offline(
    store: Store, mutation: dict[str, Any], *, max_attempts: int | None = None
) -> Path:
    """Queue a GitHub mutation for later delivery (atomic write). Returns the queued file path."""
    store.ensure()
    key = str(mutation.get("key", ""))
    if not key:
        raise OutcomeStoreError("queued mutation needs a non-empty 'key'")
    record = {
        "key": key,
        "mutation": mutation,
        "attempts": int(mutation.get("attempts", 0)),
        "max_attempts": int(max_attempts if max_attempts is not None else DEFAULT_MAX_ATTEMPTS),
        "next_retry_at": 0.0,  # due immediately on first drain
    }
    # Monotonic-ordered filename so drain is FIFO and two enqueues never collide.
    name = f"{time.monotonic_ns():020d}-{_safe_name(key, what='key')}.json"
    path = store.offline_dir / name
    _atomic_write(path, json.dumps(record, indent=2, sort_keys=False) + "\n")
    return path


@dataclass
class DrainResult:
    sent: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)  # server-superseded -> GitHub wins
    paged: list[str] = field(default_factory=list)  # retry budget exhausted -> page operator
    deferred: list[str] = field(default_factory=list)  # not yet due (still in exp-backoff window)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sent": self.sent,
            "dropped": self.dropped,
            "paged": self.paged,
            "deferred": self.deferred,
        }


def drain_offline(
    store: Store,
    *,
    sender: Callable[[dict[str, Any]], bool],
    is_superseded: Callable[[dict[str, Any]], bool] = lambda _m: False,
    now: Callable[[], float] = time.time,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
) -> DrainResult:
    """Attempt to deliver queued mutations FIFO with the R34 policy made concrete.

    For each queued mutation, in order:
    - if it is not yet due (``now() < next_retry_at``) -> **defer** it, untouched (the exponential
      backoff window from a prior failure has not elapsed);
    - if ``is_superseded(mutation)`` -> **drop** it (GitHub is authoritative for completion; a
      queued write the server already obsoleted must not be replayed) and remove the file;
    - else call ``sender(mutation)``; on success remove the file (``sent``);
    - on failure bump ``attempts`` and set ``next_retry_at = now + backoff_base * 2**(attempts-1)``
      (exponential backoff); if ``attempts`` reaches ``max_attempts`` the mutation is moved to
      ``quarantine/`` and the operator is **paged** instead of looping forever.

    ``sender`` / ``is_superseded`` / ``now`` are injected so the full policy (incl. backoff timing)
    is testable with no network and no wall clock.
    """
    result = DrainResult()
    if not store.offline_dir.exists():
        return result
    current = now()
    for path in sorted(store.offline_dir.glob("*.json")):
        record = _read_json_or_quarantine(path, quarantine_dir=store.quarantine_dir)
        if record is None:
            continue  # malformed -> already quarantined
        key = str(record.get("key", ""))
        if current < float(record.get("next_retry_at", 0.0)):
            result.deferred.append(key)
            continue  # still inside its backoff window
        mutation = record.get("mutation", {})
        if not isinstance(mutation, dict):
            mutation = {}
        if is_superseded(mutation):
            result.dropped.append(key)
            _remove(path)
            continue
        try:
            ok = sender(mutation)
        except Exception:  # noqa: BLE001 — a sender blowing up is a delivery failure, not fatal
            ok = False
        if ok:
            result.sent.append(key)
            _remove(path)
            continue
        attempts = int(record.get("attempts", 0)) + 1
        max_attempts = int(record.get("max_attempts", DEFAULT_MAX_ATTEMPTS))
        if attempts >= max_attempts:
            result.paged.append(key)
            store.quarantine_dir.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(path, store.quarantine_dir / path.name)
            except OSError:
                _remove(path)
        else:
            record["attempts"] = attempts
            record["next_retry_at"] = current + backoff_base * (2 ** (attempts - 1))
            _atomic_write(path, json.dumps(record, indent=2, sort_keys=False) + "\n")
    return result


def _remove(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        path.unlink()


# ---------------------------------------------------------------------------
# CLI — paths / ledger / events (testable, no I/O at import)
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Inspect an outcome store (cache).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_paths = sub.add_parser("paths", help="resolve and print the store paths for an outcome")
    p_paths.add_argument("outcome_id")
    p_paths.add_argument("--repo-root", default=".")

    p_ledger = sub.add_parser("ledger", help="dump the replay ledger of a store root")
    p_ledger.add_argument("store_root")

    p_pending = sub.add_parser("pending", help="dump replay-pending intents of a store root")
    p_pending.add_argument("store_root")

    args = parser.parse_args(argv)
    try:
        if args.command == "paths":
            store = Store.for_outcome(args.outcome_id, Path(args.repo_root))
            print(
                json.dumps(
                    {
                        "root": str(store.root),
                        "events": str(store.events_dir),
                        "ledger": str(store.ledger_path),
                        "locks": str(store.locks_dir),
                        "offline_queue": str(store.offline_dir),
                    }
                )
            )
            return 0
        if args.command == "ledger":
            print(json.dumps({"records": read_ledger(Store(root=Path(args.store_root)))}))
            return 0
        if args.command == "pending":
            print(json.dumps({"pending": replay_pending(Store(root=Path(args.store_root)))}))
            return 0
    except OutcomeStoreError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
