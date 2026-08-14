#!/usr/bin/env python3
"""The orchestrate register: the whole state model for a run (KTD5) and the Claude<->Codex
handoff seam (R12).

One flat JSON document **per run**, addressed by ``run_id`` alone, held outside every working
tree (default ``~/.orchestrate/registers/<run_id>.json``, relocatable by
``ORCHESTRATE_REGISTER_DIR``). One row per tracked entity — one per dispatched child, plus
one for the mirror and one for the subscriber (there is nothing structurally different about
those two; they are ordinary rows with ``agent="mirror"`` / ``agent="subscriber"``). A
``run_id`` is host-global: two callers that name the same id share one live document, which
is what same-host Claude↔Codex handoff needs in **one checkout**, and what two unrelated
projects that pick the same label collide on. Two checkouts of one ``run_id`` are a
collision, not a handoff. :func:`retire_run` forgets the per-run secret first, then
archives the document and deletes the live file and the recorded-root sidecar. Forgetting
the key requires the coordinator-recorded work location, including on the no-live-file
branch; a second retire repairs a leftover key only when that record is still there to
name the generation. Every decision and mutation API takes ``run_id`` as a required
argument; a row cannot be named without naming its run. A repository argument constrains
the operation to a work location whose provenance matches the operation, or it is refused.

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

Work       -- task, work_shape, scope, artifact_path, predicate, integration_mode, destination,
              base_commit
    What the child was asked to do and how its result gets back in: ``work_shape`` feeds U1's
    ``resolve_for_runtime`` tier routing; ``predicate`` is the bounded, inline-run validity check
    the orchestrator itself evaluates (KTD6 — the mirror never decides); ``integration_mode`` /
    ``destination`` say how a verified artifact lands (e.g. patch application, PR, direct commit).
    ``base_commit`` is the immutable Git reference used to create a branch-integrating child and
    is the committed-diff reference for its final scope check.

Lifecycle  -- phase, expected_state, observed_state, observed_state_source
    ``phase`` is the closed, ordered vocabulary in ``PHASES`` below. ``expected_state`` /
    ``observed_state`` exist because a live child's own status report is not a completion signal:
    one measured child reported ``done`` and then returned to ``working`` three times in a single
    dispatch. Disagreement between what the orchestrator expects and what herdr currently reports
    is recorded as *divergence*, not silently resolved by trusting one detector over the other —
    that resolution is U3/U4's job, not this module's. ``observed_state_source`` records how the
    state was learned. Values beginning with ``observed:`` came directly from a process or herdr
    event; values beginning with ``inferred:`` were concluded from container presence or absence.
    See
    ``docs/engineering-journal/LEARNINGS.md#agent-lifecycle-detectors-lie`` for the durable,
    publicly readable record of the broader class this belongs to (vendor detectors disagreeing
    in vendor-specific, non-repeating ways).

Time       -- dispatched_at, deadline, max_quiet_seconds, last_event_at
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
Completion -- dispatch_receipt, completion
    Written by U5 through the same merge-update API, and named here so the operator's view of the
    table is documented in one place. ``dispatch_receipt`` is the expected evidence identity the
    orchestrator establishes *before* a child is dispatched: the run-binding token, the artifact's
    destination and its pre-dispatch state, and the predicate's dependency closure and content
    digest. ``completion`` is the durable verdict: result, a reason from a closed failure
    vocabulary, the artifact digest, and the predicate outcome. The verdict deliberately does not
    live in ``observed_state`` -- that column is owned by the liveness detectors and is rewritten by
    the subscriber's snapshot catch-up for every row with a live pane, so a failure recorded there
    would be erased while the child's pane is still open. ``PHASES`` has no member meaning
    "evaluated and failed", so a failed completion leaves ``phase`` untouched and this key is what
    keeps a failed child distinguishable from a working one.

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
import subprocess  # nosec B404 -- fixed argv, no shell
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
    "base_commit",
)
LIFECYCLE_COLUMNS = ("phase", "expected_state", "observed_state", "observed_state_source")
TIME_COLUMNS = (
    "dispatched_at",
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

# Inherited git identity makes every directory report the same store. Membership
# probes already strip these; canonicalizing a work location must too.
_GIT_IDENTITY_ENV = frozenset(
    {
        "GIT_DIR",
        "GIT_COMMON_DIR",
        "GIT_WORK_TREE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_CEILING_DIRECTORIES",
    }
)


class RegisterError(Exception):
    """Base error for register operations."""


class UnsupportedSchemaVersionError(RegisterError):
    """The register on disk carries a ``schema_version`` this code does not support (C3).

    Raised only after a halt receipt has been durably written; the register file itself is never
    touched in this path.
    """


# --------------------------------------------------------------------------- paths


REGISTER_DIR_ENV = "ORCHESTRATE_REGISTER_DIR"
DEFAULT_REGISTER_DIR = Path("~/.orchestrate/registers")


def orchestrate_dir(root: Path) -> Path:
    return root / ".orchestrate"


def register_dir() -> Path:
    """Where this host keeps live per-run registers, outside every working tree."""
    override = os.environ.get(REGISTER_DIR_ENV)
    directory = (
        Path(override).expanduser().resolve()
        if override
        else DEFAULT_REGISTER_DIR.expanduser().resolve()
    )
    _refuse_default_host_dir_under_pytest(directory, label="register")
    return directory


def _refuse_default_host_dir_under_pytest(directory: Path, *, label: str) -> None:
    """Refuse the product default during pytest so a missing fixture cannot write there.

    The forbidden location is ``~/.orchestrate``, not "anywhere under ``$HOME``". A pytest
    tmp that happens to live under the operator's home is legitimate. Opt out with
    ``ORCHESTRATE_ALLOW_DEFAULT_HOST_DIR``.
    """
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if os.environ.get("ORCHESTRATE_ALLOW_DEFAULT_HOST_DIR"):
        return
    forbidden = (Path.home() / ".orchestrate").expanduser().resolve()
    try:
        if directory == forbidden or directory.is_relative_to(forbidden):
            raise RegisterError(
                f"the {label} directory {directory} is the host default under {forbidden} "
                "while pytest is running; set ORCHESTRATE_REGISTER_DIR and "
                "ORCHESTRATE_RUN_SECRET_DIR to an isolated directory (the suite fixture "
                "does this) or set ORCHESTRATE_ALLOW_DEFAULT_HOST_DIR to opt out"
            )
    except OSError:
        return


def _safe_run_id(run_id: str) -> str:
    if not run_id or not _SAFE_ID_RE.match(run_id):
        raise RegisterError(f"run_id {run_id!r} must be a non-empty [A-Za-z0-9._-]+ token")
    return run_id


def register_path(run_id: str) -> Path:
    """The live register for one run.

    Addressed by run identity, not by a repository root. A child cannot write this file by
    working in its landing: the path is not inside any landing. Two calls with the same
    ``run_id`` share one document.
    """
    return register_dir() / f"{_safe_run_id(run_id)}.json"


def halt_receipt_path(run_id: str) -> Path:
    return register_dir() / f"{_safe_run_id(run_id)}.halt-receipt.json"


def runs_dir(root: Path) -> Path:
    return orchestrate_dir(root) / "runs"


def run_dir(root: Path, run_id: str) -> Path:
    return runs_dir(root) / _safe_run_id(run_id)


def final_register_path(root: Path, run_id: str) -> Path:
    return run_dir(root, run_id) / "register-final.json"


def _lock_path(run_id: str) -> Path:
    return register_path(run_id).with_suffix(".json.lock")


def _same_dir(left: Path, right: Path) -> bool:
    """Filesystem identity, not text equality of resolved strings."""
    try:
        return left.resolve().samefile(right.resolve())
    except OSError:
        return left.resolve() == right.resolve()


def canonical_work_location(root: Path) -> Path:
    """The git top level that contains ``root``, or ``root`` resolved if git cannot name one.

    A user-facing directory is often a package subdirectory. The run's work location is
    the repository, not the package. Failure to resolve (bare repo, not a repo, git
    missing) is not an error: the resolved path is used as-is so a temporary directory
    and a non-repository ``--root`` keep working.
    """
    claimed = Path(root).resolve()
    env = {key: value for key, value in os.environ.items() if key not in _GIT_IDENTITY_ENV}
    try:
        result = subprocess.run(  # nosec B603 -- fixed argv, no shell
            ["git", "-C", str(claimed), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
    except OSError:
        return claimed
    toplevel = result.stdout.strip()
    if result.returncode != 0 or not toplevel:
        return claimed
    resolved = Path(toplevel).resolve()
    try:
        claimed.relative_to(resolved)
    except ValueError:
        # git walked up to a repository that does not contain this directory
        # (a pytest tmp next to an unrelated checkout). That is not a work
        # location for this caller.
        return claimed
    return resolved


def iter_live_run_ids() -> tuple[str, ...]:
    directory = register_dir()
    if not directory.is_dir():
        return ()
    ids: list[str] = []
    for path in directory.glob("*.json"):
        if path.name.endswith(".halt-receipt.json"):
            continue
        ids.append(path.stem)
    return tuple(sorted(ids))


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
def _write_locked(run_id: str) -> Iterator[None]:
    """Serialize register read-modify-write cycles with one exclusive advisory lock.

    A single atomic write already guarantees no reader sees a torn file, but it does not by
    itself protect a *sequence* of read-then-write against a second writer's read-then-write
    landing in between (a lost-update race). This lock is what makes "two sequential writers do
    not lose the first writer's row" true even when the writers run concurrently.
    """
    lock_path = _lock_path(run_id)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@contextmanager
def _read_locked(run_id: str) -> Iterator[None]:
    """Shared lock for reads; lock-free if no writer has ever taken the lock file yet."""
    try:
        fd = os.open(_lock_path(run_id), os.O_RDONLY)
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


def _write_halt_receipt(run_id: str, *, found: Any) -> Path:
    receipt = {
        "reason": "unsupported_schema_version",
        "found_schema_version": found,
        "supported_schema_versions": sorted(SUPPORTED_SCHEMA_VERSIONS),
        "register_path": str(register_path(run_id)),
        "detected_at": time.time(),
    }
    path = halt_receipt_path(run_id)
    _atomic_write_json(path, receipt)
    return path


def _read_register_unlocked(run_id: str) -> dict[str, Any]:
    """Load the register, or a fresh in-memory document if none exists yet.

    Returns the loaded document **as loaded** — every top-level key the file on disk carries,
    not a reconstructed ``{"schema_version", "rows"}`` envelope. This is the document-root half
    of C4: a key one runtime writes at the document root (e.g. a handoff cursor neither Claude's
    nor Codex's register.py necessarily knows about yet) must survive a write by the other, the
    same way an unknown key nested inside a child row already does. Only ``rows`` is normalized
    (defaulted to ``{}`` and type-checked) because every other function in this module indexes
    into it directly.

    Raises :class:`UnsupportedSchemaVersionError` — after writing a halt receipt and without
    touching the live register — if the file on disk carries a ``schema_version`` this
    code does not support (C3).
    """
    path = register_path(run_id)
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "run_id": _safe_run_id(run_id), "rows": {}}

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RegisterError(f"{path}: register document must be a JSON object")

    version = raw.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        _write_halt_receipt(run_id, found=version)
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


def read_register(run_id: str) -> dict[str, Any]:
    """Read the whole register document for one run, shared-locked."""
    with _read_locked(run_id):
        return _read_register_unlocked(run_id)


def run_work_location(run_id: str) -> Path | None:
    """This run's work location, or ``None`` if nothing has recorded one yet.

    Prefers the recorded run root written by :func:`completion.record_run_root` — that
    value has orchestrator-side provenance. Falls back to the document's stamped
    ``repo_root``, which is whatever directory the *first* writer passed. Binding
    against the stamp proves later callers agree with the first writer, not that the
    first writer named the true repository.
    """
    run_id = _safe_run_id(run_id)
    doc: Mapping[str, Any] = {}
    if register_path(run_id).exists():
        doc = read_register(run_id)
    return _expected_archive_root(run_id, doc)


def recorded_work_location(run_id: str) -> Path | None:
    """The coordinator-recorded work location, or ``None`` if none was recorded.

    This is the sidecar written by :func:`completion.record_run_root`. It does not
    fall back to the first-writer stamp.
    """
    return _recorded_root(_safe_run_id(run_id))


def _recorded_root(run_id: str) -> Path | None:
    path = register_dir() / f"{run_id}.root"
    if not path.exists():
        return None
    try:
        material = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not material:
        return None
    return Path(material).resolve()


def _live_document_has_rows(run_id: str) -> bool:
    path = register_path(run_id)
    if not path.exists():
        return False
    doc = _read_register_unlocked(run_id)
    rows = doc.get("rows", {})
    return bool(rows)


def assert_root_belongs_to_run(
    root: Path,
    run_id: str,
    *,
    require_binding: bool = True,
    require_recorded: bool = False,
) -> Path | None:
    """Refuse a claimed work location that disagrees with this run.

    ``root`` is canonicalized to the git top level before comparison.

    ``require_recorded=True`` (session-closing and key deletion) binds only against
    the coordinator-recorded root. A first-writer stamp is not enough.

    ``require_binding=True`` (destructive continuity paths) raises when neither a
    recorded root nor a stamp exists. ``require_binding=False`` (reads of a run
    that has never been written) returns ``None`` only when the live document is
    genuinely empty; a nonempty unbound document is refused.
    """
    run_id = _safe_run_id(run_id)
    claimed = canonical_work_location(root)
    if require_recorded:
        expected = _recorded_root(run_id)
        if expected is None:
            raise RegisterError(
                f"run {run_id!r} has no recorded work location; refusing to "
                "authorize a session-closing operation from a caller-supplied directory"
            )
        if not _same_dir(claimed, expected):
            raise RegisterError(
                f"run {run_id!r} is bound to {expected} and the caller named {claimed}; "
                "a repository argument must name this run's recorded work location"
            )
        return expected

    expected = run_work_location(run_id)
    if expected is None:
        if require_binding or _live_document_has_rows(run_id):
            raise RegisterError(
                f"run {run_id!r} has no recorded or stamped work location; refusing to "
                "bind a caller-supplied directory"
            )
        return None
    if not _same_dir(claimed, expected):
        raise RegisterError(
            f"run {run_id!r} is bound to {expected} and the caller named {claimed}; "
            "a repository argument must name this run's work location"
        )
    return expected


def read_rows(root: Path, *, run_id: str) -> dict[str, dict[str, Any]]:
    """Rows for one run.

    The live file is addressed by ``run_id``. ``root`` is the claimed work location
    (canonicalized to the git top level). When the run already has a recorded root
    or a stamp, a disagreeing ``root`` is refused. A run that has never been written
    has nothing to bind against; that read is empty and ``root`` does not constrain
    it. A nonempty live document with no binding is refused.
    """
    assert_root_belongs_to_run(root, run_id, require_binding=False)
    doc = read_register(_safe_run_id(run_id))
    return {rid: dict(row) for rid, row in doc["rows"].items()}


def rows_stamped_against(root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Operator view: every live row whose document was stamped against ``root``.

    ``root`` is canonicalized to the git top level before comparison. Keyed by
    ``(run_id, row_id)``. Two runs that share a row id both appear. This is not a
    decision or mutation path — it cannot be indexed by row id alone.
    """
    target = canonical_work_location(root)
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for live_id in iter_live_run_ids():
        doc = read_register(live_id)
        stamped = doc.get("repo_root")
        if not isinstance(stamped, str):
            continue
        if _same_dir(Path(stamped), target):
            for rid, row in doc["rows"].items():
                merged[(live_id, rid)] = dict(row)
    return merged


# --------------------------------------------------------------------------- public write API


def upsert_row(
    root: Path, row_id: str, fields: Mapping[str, Any], *, run_id: str
) -> dict[str, Any]:
    """Create or merge-update one row.

    ``run_id`` is required and addresses the live file. A ``run_id`` also present in
    ``fields`` must agree; it is not a substitute for the argument. ``fields`` is merged
    into whatever already exists at ``row_id`` — it does not replace the row wholesale —
    so a caller that only knows a subset of columns can never erase columns it has never
    heard of (C4). Every other column is optional and simply absent until some later
    phase transition sets it, **except** ``deadline`` / ``max_quiet_seconds``, which are
    seeded to ``None`` on row creation so that pair specifically always round-trips.

    Returns the row exactly as stored, id included.
    """
    return upsert_rows(root, {row_id: fields}, run_id=run_id)[row_id]


def upsert_rows(
    root: Path, updates: Mapping[str, Mapping[str, Any]], *, run_id: str
) -> dict[str, dict[str, Any]]:
    """Create or merge-update several rows in one locked, atomic register rewrite.

    ``run_id`` is required. ``root`` is canonicalized to the git top level and must
    name this run's work location once one exists (recorded run root, else the first
    writer's stamp). The first write of an unrecorded run stamps that canonical
    path; later writes must agree with it. A nonempty live document with no binding
    is refused rather than stamped. There is no scan of other live documents and no
    guess from ``fields``.
    """
    run_id = _safe_run_id(run_id)
    normalized = {row_id: dict(fields) for row_id, fields in updates.items()}
    if not normalized:
        return {}
    for row_id, fields in normalized.items():
        if not row_id:
            raise RegisterError("row_id must be non-empty")
        _validate_phase(fields)
        named = fields.get("run_id")
        if named is not None and str(named) != run_id:
            raise RegisterError(
                f"fields name run_id {named!r} but this write is addressed at {run_id!r}"
            )

    claimed = canonical_work_location(root)
    with _write_locked(run_id):
        doc = _read_register_unlocked(run_id)
        expected = _expected_archive_root(run_id, doc)
        if expected is not None:
            if not _same_dir(claimed, expected):
                raise RegisterError(
                    f"run {run_id!r} is bound to {expected} and the caller named {claimed}; "
                    "a repository argument must name this run's work location"
                )
            doc["repo_root"] = str(expected)
        else:
            if doc.get("rows"):
                raise RegisterError(
                    f"run {run_id!r} has a nonempty live register with no work location; "
                    "refusing to stamp a caller-supplied directory"
                )
            doc["repo_root"] = str(claimed)
        doc["run_id"] = run_id
        rows = doc["rows"]
        merged_rows: dict[str, dict[str, Any]] = {}
        for row_id, fields in normalized.items():
            existing = rows.get(row_id, {})
            is_new_row = not existing
            merged = {**existing, **fields, "id": row_id, "run_id": run_id}
            if is_new_row:
                for column in _TIME_STRATEGY_COLUMNS:
                    merged.setdefault(column, None)
            rows[row_id] = merged
            merged_rows[row_id] = dict(merged)
        doc["rows"] = rows
        _atomic_write_json(register_path(run_id), doc)
        return merged_rows


def _expected_archive_root(run_id: str, doc: Mapping[str, Any]) -> Path | None:
    """Work location from orchestrator-private state: sidecar first, then stamped root."""
    recorded = _recorded_root(run_id)
    if recorded is not None:
        return recorded
    stamped = doc.get("repo_root")
    if isinstance(stamped, str) and stamped:
        return Path(stamped).resolve()
    return None


def retire_run(root: Path, run_id: str) -> Path | None:
    """Archive this run's live register into the recorded work location and delete the live file.

    The archive destination and the authority to forget the per-run secret are the
    coordinator-recorded root, not the first-writer stamp. The caller-supplied ``root``
    is canonicalized to the git top level and must name that recorded directory by
    filesystem identity. A mismatch raises and leaves the live file, sidecar, and key
    untouched.

    Observation and destruction share one lock. *"The live file is absent"* is not
    proof the key belongs to a retired generation: a later caller can record a root,
    mint a key, and write a live row in the gap. The no-live branch therefore forgets
    the key only when the recorded root is still present and matches. No recorded
    root is a true no-op — a leftover key is left alone, because it may belong to a
    newly minted generation.

    The per-run secret is forgotten **before** the live file is removed. A crash after
    that point leaves a live register whose receipts no longer unseal — this module
    already calls that the correct failure — and a re-run completes because the live
    file is still there. A second retire repairs a leftover key only when the sidecar
    still names the generation.

    The durable copy is written after the secret is gone and before the live file is
    removed. The lock file is left in place: unlinking it while held, or after release,
    is an inode race.

    Genuinely idempotent when nothing is live **and** nothing is recorded:

    - No live file, recorded root matches, archive exists -> that archive is left
      untouched, the secret is forgotten if it was retained, the sidecar is cleared,
      and the archive path is returned.
    - No live file and no recorded root -> the key is not touched, then the archive
      at the caller-named path if one exists, else ``None``.
    """
    run_id = _safe_run_id(run_id)
    live = register_path(run_id)
    claimed = canonical_work_location(root)
    sidecar = register_dir() / f"{run_id}.root"

    with _write_locked(run_id):
        recorded = _recorded_root(run_id)
        if not live.exists():
            if recorded is None:
                existing = final_register_path(claimed, run_id)
                return existing if existing.exists() else None
            if not _same_dir(claimed, recorded):
                raise RegisterError(
                    f"run {run_id!r} is bound to {recorded} and retire_run was called "
                    f"with {claimed}; the archive destination is the recorded work "
                    "location, so a mismatch leaves the key and sidecar untouched"
                )
            _forget_run_secret(claimed, run_id)
            with contextlib.suppress(FileNotFoundError):
                sidecar.unlink()
            existing = final_register_path(recorded, run_id)
            return existing if existing.exists() else None

        if recorded is None:
            raise RegisterError(
                f"run {run_id!r} has no recorded work location; refusing to archive "
                "it under a caller-supplied directory"
            )
        if not _same_dir(claimed, recorded):
            raise RegisterError(
                f"run {run_id!r} is bound to {recorded} and retire_run was called with "
                f"{claimed}; the archive destination is the recorded work location, so a "
                "mismatch leaves the live register untouched"
            )

        doc = _read_register_unlocked(run_id)
        doc["repo_root"] = str(recorded)
        _forget_run_secret(claimed, run_id)
        rows: dict[str, dict[str, Any]] = doc["rows"]
        final_path = final_register_path(recorded, run_id)
        if not rows and final_path.exists():
            live.unlink(missing_ok=True)
            with contextlib.suppress(FileNotFoundError):
                sidecar.unlink()
            return final_path

        final_doc = {
            "schema_version": doc["schema_version"],
            "run_id": run_id,
            "retired_at": time.time(),
            "rows": rows,
        }
        for key, value in doc.items():
            if key not in final_doc and key != "rows":
                final_doc[key] = value
        _atomic_write_json(final_path, final_doc)
        live.unlink(missing_ok=True)
        with contextlib.suppress(FileNotFoundError):
            sidecar.unlink()
        return final_path


def reconcile_stamp(run_id: str, recorded: Path) -> None:
    """Rewrite a disagreeing first-writer stamp to the recorded work location.

    Called from :func:`completion.record_run_root` after the sidecar is written so
    the operator view does not keep listing the run under a package directory.
    Missing live files are ignored.
    """
    run_id = _safe_run_id(run_id)
    expected = Path(recorded).resolve()
    with _write_locked(run_id):
        if not register_path(run_id).exists():
            return
        doc = _read_register_unlocked(run_id)
        stamped = doc.get("repo_root")
        if not isinstance(stamped, str) or not stamped:
            return
        if _same_dir(Path(stamped), expected):
            return
        doc["repo_root"] = str(expected)
        _atomic_write_json(register_path(run_id), doc)


def _forget_run_secret(root: Path, run_id: str) -> None:
    try:
        import completion as completion_mod
    except ImportError:
        return
    completion_mod.forget_run_secret(root, run_id)


# --------------------------------------------------------------------------- thin CLI


def _cli_show(root: Path, run_id: str | None) -> int:
    if run_id is None:
        merged = rows_stamped_against(root)
        printable = {f"{run}/{row}": value for (run, row), value in merged.items()}
        print(json.dumps(printable, indent=2, sort_keys=True))
        return 0
    print(json.dumps(read_rows(root, run_id=run_id), indent=2, sort_keys=True))
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
    root = canonical_work_location(args.root)
    try:
        if args.command == "show":
            return _cli_show(root, args.run_id)
        if args.command == "retire":
            return _cli_retire(root, args.run_id)
    except RegisterError as exc:
        print(f"error: {exc}", flush=True)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
