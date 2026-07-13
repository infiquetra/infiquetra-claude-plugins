#!/usr/bin/env python3
"""Delegation liveness channel — the filesystem marker hooks arm/disarm/read (#384, U2).

``PreToolUse`` cannot see the calling agent's profile or intent (journaled twice,
``DECISIONS.md:1124,:1145``), so a filesystem marker under ``.claude/delegation/active.json``
is the only cross-call channel between the dispatch layer (which knows a delegation is about
to run) and the hooks (which only see the current tool call / transcript). This module is that
channel: ``arm``/``disarm`` are the dispatcher's writers, ``active`` is the hooks' reader.

FAIL-OPEN CONTRACT (load-bearing): ``active()`` must NEVER raise. Hooks call it on every
``PreToolUse``/``Stop``/``SubagentStop`` in every repo where saga is installed (per the plan's
"Fleet-wide hook blast radius" risk); a corrupt, missing, or unreadable marker file degrades to
"nothing is armed" rather than crashing a hook and breaking an unrelated turn. ``arm()`` may
raise (e.g. on a read-only filesystem) — that's surfaced to the dispatcher, which is expected to
record it as a named, fail-open condition (``tripwire_unarmed``) rather than blocking dispatch.

Entries are keyed by ``session_id`` so concurrent sessions are isolated; arming the same session
twice supersedes the existing entry in place (latest-wins, mirroring the ledger-reduction style
at ``outcome_report.py:71``). Entries older than ``DEFAULT_TTL_SECONDS`` are invisible to
``active()`` and are reaped (dropped) the next time the file is written.

WRITER SERIALIZATION (#520 F4): every read-modify-write over a marker file holds an exclusive
``fcntl.flock`` on a sibling ``<name>.lock`` file, so two concurrent ``arm()`` calls can never
lose each other's entry (the pre-#520 lock-free RMW was last-writer-wins — a silent, fail-open
loss of tripwire protection). Reads stay lock-free: ``active()``'s fail-open contract already
tolerates any in-flight state, and the tmp+rename write means a reader never sees a torn file.

This module also owns the durable delegation-integrity attempt counter (#520 F1) — the
``.claude/delegation/integrity.json`` sibling of ``active.json``, keyed ``session_id`` +
``engine``. The dispatch layer's re-queue-once-then-HALT guarantee (KTD7) is only real if the
consecutive-divergence count survives process boundaries; a module-level dict in the dispatcher
degrades to requeue-forever for one-process-per-attempt consumers.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# KTD4: default liveness TTL. A stale marker (crashed dispatcher, killed session) must not
# leave a delegation permanently armed; reads ignore anything older than this and a write
# reaps it from the file.
DEFAULT_TTL_SECONDS = 4 * 60 * 60  # 4 hours

DEFAULT_MARKER_RELATIVE_PATH = Path(".claude") / "delegation" / "active.json"
INTEGRITY_RELATIVE_PATH = Path(".claude") / "delegation" / "integrity.json"


@dataclass(frozen=True)
class DelegationEntry:
    engine: str
    session_id: str
    armed_at: float
    armed_by: str

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "session_id": self.session_id,
            "armed_at": self.armed_at,
            "armed_by": self.armed_by,
        }

    @classmethod
    def from_jsonable(cls, payload: dict[str, Any]) -> DelegationEntry | None:
        engine = payload.get("engine")
        session_id = payload.get("session_id")
        armed_at = payload.get("armed_at")
        armed_by = payload.get("armed_by")
        if not isinstance(engine, str) or not isinstance(session_id, str):
            return None
        if not isinstance(armed_at, (int, float)) or isinstance(armed_at, bool):
            return None
        if not isinstance(armed_by, str):
            return None
        return cls(
            engine=engine, session_id=session_id, armed_at=float(armed_at), armed_by=armed_by
        )


def _marker_path(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else Path.cwd()
    return base / DEFAULT_MARKER_RELATIVE_PATH


def _integrity_path(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else Path.cwd()
    return base / INTEGRITY_RELATIVE_PATH


@contextlib.contextmanager
def _write_lock(path: Path) -> Iterator[None]:
    """Hold an exclusive ``flock`` on ``<path>.lock`` around a read-modify-write (#520 F4).

    The lock file is a sibling (never the data file itself) so the tmp+rename atomic write in
    ``_write_json`` keeps working: locking the data file's own fd would be lost on ``os.replace``.
    May raise (unwritable parent, read-only filesystem) — same surfaced-to-the-dispatcher posture
    as ``arm()``. Lock files are never deleted; they are empty and bounded (one per marker file).
    """
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically (tmp + rename) — mirrors ``codex_delegate._write_json``.

    A mid-write kill must never leave a torn marker file behind: torn JSON would otherwise be
    indistinguishable from a genuinely corrupt file, and both must degrade to "unarmed"
    (``active()``'s fail-open contract) rather than wedging a hook.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def _read_entries_raw(path: Path) -> list[dict[str, Any]]:
    """Read the marker file's raw entry dicts. Returns ``[]`` on any error (fail-open)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        payload = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(payload, dict):
        return []
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _live_entries(path: Path, *, now: float, ttl_seconds: float) -> list[DelegationEntry]:
    """Parse + TTL-filter the marker file's entries. Never raises (fail-open)."""
    live: list[DelegationEntry] = []
    for raw_entry in _read_entries_raw(path):
        entry = DelegationEntry.from_jsonable(raw_entry)
        if entry is None:
            continue
        if now - entry.armed_at > ttl_seconds:
            continue
        live.append(entry)
    return live


def arm(
    engine: str,
    session_id: str,
    armed_by: str,
    *,
    root: Path | str | None = None,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    now: float | None = None,
) -> DelegationEntry:
    """Arm a delegation for ``session_id``, superseding any existing entry for that session.

    This is the dispatcher's writer and MAY raise (e.g. read-only filesystem, unwritable
    parent directory) — that's an expected, surfaced failure the dispatcher records as a named
    condition rather than a hook-facing concern. Reaps stale entries (past ``ttl_seconds``) and
    any other entry belonging to the same ``session_id`` before writing the new one, so a
    session can only ever have one live entry.
    """
    path = _marker_path(root)
    effective_now = time.time() if now is None else now
    entry = DelegationEntry(
        engine=engine, session_id=session_id, armed_at=effective_now, armed_by=armed_by
    )

    with _write_lock(path):
        live = _live_entries(path, now=effective_now, ttl_seconds=ttl_seconds)
        surviving = [existing for existing in live if existing.session_id != session_id]
        surviving.append(entry)
        _write_json(path, {"entries": [item.to_jsonable() for item in surviving]})
    return entry


def disarm(
    session_id: str,
    *,
    root: Path | str | None = None,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    now: float | None = None,
) -> bool:
    """Remove ``session_id``'s entry, if any. Returns whether a live entry was removed.

    Fail-open on read: an unreadable/corrupt marker file is treated as already-unarmed (returns
    ``False``) rather than raising. If the file cannot be *written* (e.g. read-only filesystem),
    the underlying ``OSError`` propagates — the same "dispatcher may see errors" posture as
    ``arm()``; hooks never call ``disarm()`` directly.
    """
    path = _marker_path(root)
    effective_now = time.time() if now is None else now

    # No marker file at all: nothing to remove, and taking the lock would create the lock
    # file's parent directory out of thin air — skip entirely.
    if not path.exists():
        return False
    with _write_lock(path):
        live = _live_entries(path, now=effective_now, ttl_seconds=ttl_seconds)
        removed = any(entry.session_id == session_id for entry in live)
        surviving = [entry for entry in live if entry.session_id != session_id]
        _write_json(path, {"entries": [item.to_jsonable() for item in surviving]})
    return removed


def active(
    session_id: str,
    *,
    root: Path | str | None = None,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    now: float | None = None,
) -> DelegationEntry | None:
    """Return ``session_id``'s live entry, or ``None`` if unarmed.

    FAIL-OPEN CONTRACT: NEVER raises. Every failure mode — missing marker file, corrupt JSON,
    unreadable file, malformed entry, stale (past-TTL) entry — is treated as "unarmed". Hooks
    depend on this: a raised exception here must never be able to break an unrelated turn.
    """
    try:
        path = _marker_path(root)
        effective_now = time.time() if now is None else now
        for entry in _live_entries(path, now=effective_now, ttl_seconds=ttl_seconds):
            if entry.session_id == session_id:
                return entry
        return None
    except Exception:  # noqa: BLE001 - fail-open contract: active() must never raise.
        return None


@dataclass(frozen=True)
class IntegrityEntry:
    """One durable consecutive-divergence counter, keyed ``session_id`` + ``engine`` (#520 F1)."""

    session_id: str
    engine: str
    attempts: int
    updated_at: float

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "engine": self.engine,
            "attempts": self.attempts,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_jsonable(cls, payload: dict[str, Any]) -> IntegrityEntry | None:
        session_id = payload.get("session_id")
        engine = payload.get("engine")
        attempts = payload.get("attempts")
        updated_at = payload.get("updated_at")
        if not isinstance(session_id, str) or not isinstance(engine, str):
            return None
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 0:
            return None
        if not isinstance(updated_at, (int, float)) or isinstance(updated_at, bool):
            return None
        return cls(
            session_id=session_id, engine=engine, attempts=attempts, updated_at=float(updated_at)
        )


def _live_integrity_entries(path: Path, *, now: float, ttl_seconds: float) -> list[IntegrityEntry]:
    """Parse + TTL-filter the integrity file's entries. Never raises (fail-open).

    The TTL reuses ``DEFAULT_TTL_SECONDS`` semantics: a counter left behind by a crashed or
    abandoned session must not HALT an unrelated dispatch hours later — stale entries are
    invisible on read and reaped on the next locked write.
    """
    live: list[IntegrityEntry] = []
    for raw_entry in _read_entries_raw(path):
        entry = IntegrityEntry.from_jsonable(raw_entry)
        if entry is None:
            continue
        if now - entry.updated_at > ttl_seconds:
            continue
        live.append(entry)
    return live


def integrity_attempts(
    session_id: str,
    engine: str,
    *,
    root: Path | str | None = None,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    now: float | None = None,
) -> int:
    """The live consecutive-divergence count for ``session_id`` + ``engine`` (0 when none).

    FAIL-OPEN read, mirroring ``active()``: never raises; any unreadable/corrupt/stale state
    reads as 0.
    """
    try:
        path = _integrity_path(root)
        effective_now = time.time() if now is None else now
        for entry in _live_integrity_entries(path, now=effective_now, ttl_seconds=ttl_seconds):
            if entry.session_id == session_id and entry.engine == engine:
                return entry.attempts
        return 0
    except Exception:  # noqa: BLE001 - fail-open read, same contract as active()
        return 0


def record_integrity_divergence(
    session_id: str,
    engine: str,
    *,
    root: Path | str | None = None,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    now: float | None = None,
) -> int:
    """Durably increment the consecutive-divergence counter; returns the new count (#520 F1).

    This is the dispatch layer's writer for KTD7 re-queue-once-then-HALT: the count must survive
    one-process-per-attempt consumers, so it lives here (the delegation-state marker family)
    rather than in dispatcher process memory. MAY raise (read-only filesystem, unwritable
    parent) — the dispatcher is expected to degrade to its in-process fallback, never crash.
    """
    path = _integrity_path(root)
    effective_now = time.time() if now is None else now
    with _write_lock(path):
        live = _live_integrity_entries(path, now=effective_now, ttl_seconds=ttl_seconds)
        current = next((e for e in live if e.session_id == session_id and e.engine == engine), None)
        attempts = (current.attempts if current is not None else 0) + 1
        surviving = [e for e in live if not (e.session_id == session_id and e.engine == engine)]
        surviving.append(
            IntegrityEntry(
                session_id=session_id, engine=engine, attempts=attempts, updated_at=effective_now
            )
        )
        _write_json(path, {"entries": [item.to_jsonable() for item in surviving]})
    return attempts


def clear_integrity_attempts(
    session_id: str,
    engine: str,
    *,
    root: Path | str | None = None,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    now: float | None = None,
) -> None:
    """Reset the counter for ``session_id`` + ``engine`` (corroborated acceptance, or post-HALT).

    Skips every write when no integrity file exists — a clean gated acceptance must never
    conjure ``.claude/delegation/`` out of thin air. MAY raise on a present-but-unwritable file,
    same posture as ``record_integrity_divergence``.
    """
    path = _integrity_path(root)
    if not path.exists():
        return
    effective_now = time.time() if now is None else now
    with _write_lock(path):
        live = _live_integrity_entries(path, now=effective_now, ttl_seconds=ttl_seconds)
        surviving = [e for e in live if not (e.session_id == session_id and e.engine == engine)]
        _write_json(path, {"entries": [item.to_jsonable() for item in surviving]})


def _cmd_arm(args: argparse.Namespace) -> int:
    entry = arm(args.engine, args.session_id, args.armed_by, root=args.root)
    print(json.dumps(entry.to_jsonable(), indent=2, sort_keys=True))
    return 0


def _cmd_disarm(args: argparse.Namespace) -> int:
    removed = disarm(args.session_id, root=args.root)
    print(json.dumps({"session_id": args.session_id, "removed": removed}, indent=2, sort_keys=True))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    entry = active(args.session_id, root=args.root)
    if entry is None:
        print(json.dumps({"session_id": args.session_id, "armed": False}, indent=2, sort_keys=True))
        return 0
    payload = entry.to_jsonable()
    payload["armed"] = True
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Delegation liveness channel (arm/disarm/status)")
    parser.add_argument("--root", type=Path, default=None, help="Repo root (default: cwd)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    arm_parser = subparsers.add_parser("arm", help="Arm a delegation for a session")
    arm_parser.add_argument("--engine", required=True)
    arm_parser.add_argument("--session-id", dest="session_id", required=True)
    arm_parser.add_argument("--armed-by", dest="armed_by", required=True)
    arm_parser.set_defaults(func=_cmd_arm)

    disarm_parser = subparsers.add_parser("disarm", help="Disarm a session's delegation")
    disarm_parser.add_argument("--session-id", dest="session_id", required=True)
    disarm_parser.set_defaults(func=_cmd_disarm)

    status_parser = subparsers.add_parser("status", help="Show a session's liveness status")
    status_parser.add_argument("--session-id", dest="session_id", required=True)
    status_parser.set_defaults(func=_cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
