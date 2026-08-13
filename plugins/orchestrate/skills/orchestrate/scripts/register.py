#!/usr/bin/env python3
"""The orchestrate register: the whole state model for a run (KTD5) and the Claude<->Codex
handoff seam (R12).

One flat JSON document per repository at ``.orchestrate/register.json``, holding one row per
tracked entity — one per dispatched child, plus one for the mirror and one for the subscriber
(there is nothing structurally different about those two; they are ordinary rows with
``agent="mirror"`` / ``agent="subscriber"``). The register is global and keyed by ``run_id``, not
per-run: several runs can have live rows in the same file at once, and retiring one run
(:func:`retire_run`) only ever touches that run's own rows.

This module implements exactly two responsibilities: atomic durability (a reader never sees a
torn file, a lost update, or output from a corrupt state) and the row schema (the columns below).
It does not decide *when* to write a column — that is U3 (subscriber), U4 (reaping), U6 (spend
gate), U7 (hang detection), and U10 (handoff). Those units read this module's docstrings to know
what each column means.

Row columns, by group
----------------------
Identity   -- id, run_id, agent, vendor, model, effort
    ``id`` is this row's own key (also the dict key under ``rows``); ``run_id`` groups rows into
    one run for filtering and retirement; ``agent``/``vendor``/``model``/``effort`` name what was
    dispatched (``agent`` is a role such as "mirror"/"subscriber" for the two non-child rows).

Substrate  -- herdr_session, workspace_id, tab_id, pane_id, cwd
    Where the row's process actually lives in herdr. ``pane_id`` is the durable handle U3's
    subscriber re-attaches to on every reconnect (KTD12); it is the join key between this row and
    the herdr socket's events, so it must be recorded before the row is trusted as "launched".

Work       -- task, work_shape, scope, artifact_path, predicate, integration_mode, destination
    What the child was asked to do and how its result gets back in: ``work_shape`` feeds U1's
    ``resolve_for_runtime`` tier routing; ``predicate`` is the bounded, inline-run validity check
    the orchestrator itself evaluates (KTD6 — the mirror never decides); ``integration_mode`` /
    ``destination`` say how a verified artifact lands (e.g. patch application, PR, direct commit).

Lifecycle  -- phase, expected_state, observed_state
    ``phase`` is the closed, ordered vocabulary in ``PHASES`` below. ``expected_state`` /
    ``observed_state`` exist because a live child's own status report is not a completion signal:
    one measured child reported ``done`` and then returned to ``working`` three times in a single
    dispatch. Disagreement between what the orchestrator expects and what herdr currently reports
    is recorded as *divergence*, not silently resolved by trusting one detector over the other —
    that resolution is U3/U4's job, not this module's. See
    ``docs/engineering-journal/LEARNINGS.md#agent-lifecycle-detectors-lie`` for the durable,
    publicly readable record of the broader class this belongs to (vendor detectors disagreeing
    in vendor-specific, non-repeating ways).

Time       -- dispatched_at, dispatch_revision_baseline, deadline, max_quiet_seconds,
              last_event_at
    ``deadline`` and ``max_quiet_seconds`` are alternative hang-detection strategies for a row —
    a caller sets whichever fits that dispatch. :func:`upsert_row` seeds **both** to ``None`` at
    row creation (the other TIME/ACCOUNTING columns stay absent until some later phase transition
    sets them — see the forward-compatibility note below), so this pair specifically always
    round-trips identically regardless of which strategy a row uses.
    ``last_event_at`` **must be fed by pane output (herdr's ``revision`` counter), never by
    lifecycle state (``state_change_seq``)**: measured over one real dispatch window,
    ``state_change_seq`` moved twice and then sat still for minutes while the child worked hard,
    while ``revision`` moved roughly 47 times over the same window. A hang detector reading
    ``last_event_at`` from ``state_change_seq`` false-alarms on a healthy child; this module only
    defines the column, U7 is the reader that must honor this. See
    ``docs/engineering-journal/LEARNINGS.md#pane-revision-is-the-liveness-signal`` for the full
    write-up.
    ``dispatch_revision_baseline`` is the pane ``revision`` counter sampled immediately before
    dispatch. A ``pane.output_matched`` hit is honoured only when the event's current revision is
    greater than this baseline, so text left in pre-dispatch scrollback cannot satisfy a new run.

Accounting -- tokens_observed, tokens_reserved
    ``tokens_reserved`` is what U6's spend gate committed before dispatch; ``tokens_observed`` is
    the running actual, updated as events arrive. The gap between them is what the gate checks.

Forward compatibility (C4)
---------------------------
A key written by one runtime and unknown to the other must survive a write by the other, and that
includes a key **nested inside a child row**, not only an unknown top-level key. This module never
reconstructs a row through a fixed-field type — every row is a plain ``dict[str, Any]`` from JSON
load straight through to JSON dump, and :func:`upsert_row` merges the fields a caller passes into
whatever already exists rather than replacing the row wholesale. A caller that only knows about
its own runtime's columns can never erase a sibling runtime's extra columns just by touching one
field of the same row.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import threading
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = frozenset({1})

# Closed, ordered lifecycle vocabulary (U2 brief). U3/U4/U7 move a row through these in order;
# this module does not enforce the order, only that a written value is a member of the set.
PHASES = ("planned", "launching", "launched", "ready", "working", "verified", "reaped")

IDENTITY_COLUMNS = ("id", "run_id", "agent", "vendor", "model", "effort")
SUBSTRATE_COLUMNS = ("herdr_session", "workspace_id", "tab_id", "pane_id", "cwd")
WORK_COLUMNS = (
    "task",
    "work_shape",
    "scope",
    "artifact_path",
    "predicate",
    "integration_mode",
    "destination",
)
LIFECYCLE_COLUMNS = ("phase", "expected_state", "observed_state")
TIME_COLUMNS = (
    "dispatched_at",
    "dispatch_revision_baseline",
    "deadline",
    "max_quiet_seconds",
    "last_event_at",
)
ACCOUNTING_COLUMNS = ("tokens_observed", "tokens_reserved")

ROW_COLUMNS = (
    IDENTITY_COLUMNS
    + SUBSTRATE_COLUMNS
    + WORK_COLUMNS
    + LIFECYCLE_COLUMNS
    + TIME_COLUMNS
    + ACCOUNTING_COLUMNS
)

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class RegisterError(Exception):
    """Base error for register operations."""


class UnsupportedSchemaVersionError(RegisterError):
    """The register on disk carries a ``schema_version`` this code does not support (C3).

    Raised only after a halt receipt has been durably written; the register file itself is never
    touched in this path.
    """


# --------------------------------------------------------------------------- paths


def orchestrate_dir(root: Path) -> Path:
    return root / ".orchestrate"


def register_path(root: Path) -> Path:
    return orchestrate_dir(root) / "register.json"


def halt_receipt_path(root: Path) -> Path:
    return orchestrate_dir(root) / "halt-receipt.json"


def runs_dir(root: Path) -> Path:
    return orchestrate_dir(root) / "runs"


def _safe_run_id(run_id: str) -> str:
    if not run_id or not _SAFE_ID_RE.match(run_id):
        raise RegisterError(f"run_id {run_id!r} must be a non-empty [A-Za-z0-9._-]+ token")
    return run_id


def run_dir(root: Path, run_id: str) -> Path:
    return runs_dir(root) / _safe_run_id(run_id)


def final_register_path(root: Path, run_id: str) -> Path:
    return run_dir(root, run_id) / "register-final.json"


def _lock_path(root: Path) -> Path:
    return register_path(root).with_suffix(".json.lock")


# --------------------------------------------------------------------------- atomic write primitive


def _unique_tmp(path: Path) -> Path:
    """A temp sibling unique per process, thread, and instant — see run_ledger.py's identical
    reasoning: pid alone is not enough because two threads in one process can share one temp."""
    return path.with_name(
        f"{path.name}.{os.getpid()}.{threading.get_ident()}.{time.monotonic_ns()}.tmp"
    )


def _atomic_write_json(path: Path, doc: Mapping[str, Any]) -> None:
    """Write ``doc`` to ``path`` atomically: temp file + ``fsync`` + ``os.replace``.

    A reader never observes a partially written file — ``os.replace`` is atomic within a POSIX
    filesystem, so the file at ``path`` is either the previous complete content or the new
    complete content, never a torn mixture. The write into the temp file happens inside the same
    ``try``/``finally`` that cleans it up, so a failed write (e.g. disk full) cannot leave an
    orphan temp behind either.

    fsync before replace matters on top of that: ``Path.write_text`` only closes the file
    descriptor, it does not persist dirty pages, so a machine crash immediately after a
    *successful* replace could otherwise leave ``path`` present but empty. `run_ledger.py` and
    `manifest_store.py` elsewhere in this repository both fsync for the same reason before their
    own ``os.replace`` — this matches that idiom rather than only borrowing their temp-naming
    scheme.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _unique_tmp(path)
    payload = json.dumps(doc, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp, path)
    finally:
        if fd >= 0:
            os.close(fd)
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()


@contextmanager
def _write_locked(root: Path) -> Iterator[None]:
    """Serialize register read-modify-write cycles with one exclusive advisory lock.

    A single atomic write already guarantees no reader sees a torn file, but it does not by
    itself protect a *sequence* of read-then-write against a second writer's read-then-write
    landing in between (a lost-update race). This lock is what makes "two sequential writers do
    not lose the first writer's row" true even when the writers run concurrently.
    """
    lock_path = _lock_path(root)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@contextmanager
def _read_locked(root: Path) -> Iterator[None]:
    """Shared lock for reads; lock-free if no writer has ever taken the lock file yet."""
    try:
        fd = os.open(_lock_path(root), os.O_RDONLY)
    except FileNotFoundError:
        yield
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


# --------------------------------------------------------------------------- schema-version gate


def _write_halt_receipt(root: Path, *, found: Any) -> Path:
    receipt = {
        "reason": "unsupported_schema_version",
        "found_schema_version": found,
        "supported_schema_versions": sorted(SUPPORTED_SCHEMA_VERSIONS),
        "register_path": str(register_path(root)),
        "detected_at": time.time(),
    }
    path = halt_receipt_path(root)
    _atomic_write_json(path, receipt)
    return path


def _read_register_unlocked(root: Path) -> dict[str, Any]:
    """Load the register, or a fresh in-memory document if none exists yet.

    Returns the loaded document **as loaded** — every top-level key the file on disk carries,
    not a reconstructed ``{"schema_version", "rows"}`` envelope. This is the document-root half
    of C4: a key one runtime writes at the document root (e.g. a handoff cursor neither Claude's
    nor Codex's register.py necessarily knows about yet) must survive a write by the other, the
    same way an unknown key nested inside a child row already does. Only ``rows`` is normalized
    (defaulted to ``{}`` and type-checked) because every other function in this module indexes
    into it directly.

    Raises :class:`UnsupportedSchemaVersionError` — after writing a halt receipt and without
    touching ``register.json`` itself — if the file on disk carries a ``schema_version`` this
    code does not support (C3).
    """
    path = register_path(root)
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "rows": {}}

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RegisterError(f"{path}: register document must be a JSON object")

    version = raw.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        _write_halt_receipt(root, found=version)
        raise UnsupportedSchemaVersionError(
            f"register schema_version {version!r} is not supported "
            f"(supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}); halted without mutating "
            f"{path}"
        )

    rows = raw.get("rows", {})
    if not isinstance(rows, dict):
        raise RegisterError(f"{path}: 'rows' must be a JSON object keyed by row id")
    raw["rows"] = rows
    return raw


def _validate_phase(fields: Mapping[str, Any]) -> None:
    phase = fields.get("phase")
    if phase is not None and phase not in PHASES:
        raise RegisterError(f"phase {phase!r} is not one of {PHASES}")


# The two alternative hang-detection strategies (see the Time group docstring above). Both are
# seeded to None at row creation so this pair — and only this pair — always round-trips
# identically regardless of which strategy a given row uses; every other optional column stays
# genuinely absent until some later phase transition sets it.
_TIME_STRATEGY_COLUMNS = ("deadline", "max_quiet_seconds")


# --------------------------------------------------------------------------- public read API


def read_register(root: Path) -> dict[str, Any]:
    """Read the whole register document (schema_version + rows), shared-locked."""
    with _read_locked(root):
        return _read_register_unlocked(root)


def read_rows(root: Path, *, run_id: str | None = None) -> dict[str, dict[str, Any]]:
    """All rows, optionally filtered to one ``run_id``. Each row is returned as stored, including
    any keys this module does not know about (C4)."""
    doc = read_register(root)
    rows: dict[str, dict[str, Any]] = doc["rows"]
    if run_id is None:
        return {rid: dict(row) for rid, row in rows.items()}
    return {rid: dict(row) for rid, row in rows.items() if row.get("run_id") == run_id}


# --------------------------------------------------------------------------- public write API


def upsert_row(root: Path, row_id: str, fields: Mapping[str, Any]) -> dict[str, Any]:
    """Create or merge-update one row.

    ``fields`` is merged into whatever already exists at ``row_id`` — it does not replace the row
    wholesale — so a caller that only knows a subset of columns (its own runtime's, say) can never
    erase columns it has never heard of (C4). A brand-new row requires ``run_id`` in ``fields`` (or
    already present in an existing row of the same id); every other column is optional and simply
    absent until some later phase transition sets it, **except** ``deadline`` /
    ``max_quiet_seconds``, which are seeded to ``None`` on row creation (not merely left absent) so
    that pair specifically always round-trips (see the Time group docstring above).

    Returns the row exactly as stored, id included.
    """
    if not row_id:
        raise RegisterError("row_id must be non-empty")
    _validate_phase(fields)

    with _write_locked(root):
        doc = _read_register_unlocked(root)
        rows = doc["rows"]
        existing = rows.get(row_id, {})
        is_new_row = not existing
        if is_new_row and "run_id" not in fields:
            raise RegisterError(f"new row {row_id!r} requires 'run_id' in fields")
        merged = {**existing, **dict(fields), "id": row_id}
        if is_new_row:
            for column in _TIME_STRATEGY_COLUMNS:
                merged.setdefault(column, None)
        rows[row_id] = merged
        doc["rows"] = rows
        _atomic_write_json(register_path(root), doc)
        return dict(merged)


def retire_run(root: Path, run_id: str) -> Path | None:
    """Move every row belonging to ``run_id`` out of the live register and into
    ``.orchestrate/runs/<run_id>/register-final.json``. Rows belonging to any other run are left
    untouched in the live register.

    The durable copy under ``runs/<run_id>/`` is written **before** the live register is
    rewritten: a crash between the two steps leaves the run's rows present in both places
    (recoverable by re-running: the live rows are still there, so a retry recomputes and rewrites
    the same archive), never in neither.

    Genuinely idempotent, including the case that matters most — retrying **after** a fully
    successful retirement, not just recovering from a crash mid-retirement:

    - No live rows for ``run_id`` and an archive already exists at
      ``runs/<run_id>/register-final.json`` -> that archive is left untouched and its path is
      returned. Nothing is recomputed from the (now-empty) live set, so a second, third, or Nth
      call after success can never overwrite the one durable record of that run with ``{}``.
    - No live rows and no archive either -> there is nothing to retire (``run_id`` was never
      registered, or every row for it was already archived by someone else). This is not an
      error; ``None`` is returned and nothing is written.
    """
    _safe_run_id(run_id)
    with _write_locked(root):
        doc = _read_register_unlocked(root)
        rows: dict[str, dict[str, Any]] = doc["rows"]
        retiring = {rid: row for rid, row in rows.items() if row.get("run_id") == run_id}
        final_path = final_register_path(root, run_id)

        if not retiring:
            return final_path if final_path.exists() else None

        remaining = {rid: row for rid, row in rows.items() if row.get("run_id") != run_id}
        final_doc = {
            "schema_version": doc["schema_version"],
            "run_id": run_id,
            "retired_at": time.time(),
            "rows": retiring,
        }
        _atomic_write_json(final_path, final_doc)

        doc["rows"] = remaining
        _atomic_write_json(register_path(root), doc)
        return final_path


# --------------------------------------------------------------------------- thin CLI


def _cli_show(root: Path, run_id: str | None) -> int:
    rows = read_rows(root, run_id=run_id)
    print(json.dumps(rows, indent=2, sort_keys=True))
    return 0


def _cli_retire(root: Path, run_id: str) -> int:
    final_path = retire_run(root, run_id)
    print(str(final_path) if final_path is not None else "nothing to retire")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Inspect and retire the orchestrate register.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser("show", help="print rows as JSON")
    show.add_argument("--run-id", default=None)

    retire = sub.add_parser(
        "retire", help="retire a run's rows to runs/<run_id>/register-final.json"
    )
    retire.add_argument("run_id")

    args = parser.parse_args(argv)
    try:
        if args.command == "show":
            return _cli_show(args.root, args.run_id)
        if args.command == "retire":
            return _cli_retire(args.root, args.run_id)
    except RegisterError as exc:
        print(f"error: {exc}", flush=True)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
