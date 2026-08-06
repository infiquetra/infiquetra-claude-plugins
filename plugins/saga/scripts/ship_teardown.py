#!/usr/bin/env python3
"""ship_teardown.py — opened-resource manifest + reality-checked closing count (issue #347 U1).

The ship ceremony used to end at ``branch_delete`` and declare "done" with zero
accounting of what it had opened along the way — branches, worktrees, background
sessions, scratch directories, draft PRs. This module is the manifest primitive that
makes teardown honest:

* ``register`` / ``close`` — record a resource the ceremony (or ``/work`` /
  ``/outcome``) opens, at the moment it opens it (register-on-open, R1), and record
  when + how it was closed.
* ``reconcile`` — the derived, on-read closing count (R2): never a cached field,
  always recomputed by cross-checking the manifest against reality. An entry the
  manifest claims is closed but whose resource still exists on disk/upstream is a
  **discrepancy** — it counts as open and is named, never silently trusted (R5,
  KTD4). This is the same discipline as ``outcome_worktrees.live_worktrees()``
  reading existence from git rather than from the registry alone.

Storage (KTD2): a per-saga sidecar at
``.claude/saga/sagas/<saga_id>/opened_resources.json`` — same directory as
``merge_expectation.json`` / ``rollback_manifest.json``, same hardening (saga-id
traversal guard, wrapped ``JSONDecodeError``, atomic tmp-then-``os.replace`` writes).

House testability pattern (mirrors ``merge_watcher.py`` / ``ship_undo.py``): every
function that shells out takes a ``runner`` callable, defaulted to
``subprocess.run`` resolved at call time (never bound as a default argument).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess  # nosec B404
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Sibling-module imports (issue #347, U3): reclaim calls reversibility_certificate
# (the fleet's write authority) and, for .saga-worktrees-registered worktrees,
# outcome_store / outcome_worktrees as a library. Both are imported lazily inside
# reclaim's helpers (outcome_worktrees pulls the heavy outcome engine graph, and a
# top-level import would also risk a cycle) — this only puts the scripts dir on the
# path so those lazy imports resolve, mirroring ship_receipt.py's sys.path.insert.
sys.path.insert(0, str(Path(__file__).resolve().parent))

STATE_DIR = Path(".claude/saga")
SAGAS_DIR = STATE_DIR / "sagas"
MANIFEST_NAME = "opened_resources.json"

# The closed, KTD2-enumerated vocabulary of resource kinds a ceremony/work/outcome
# cleanup path can register. Kept as a tuple (not an Enum) to match the plain-string
# vocabulary style used elsewhere in this module family (ship_ceremony.TRANSITIONS).
RESOURCE_KINDS: tuple[str, ...] = (
    "branch",
    "worktree",
    "background_session",
    "scratch",
    "draft_pr",
)

# Per-entry reconcile status vocabulary (KTD4).
STATUS_OPEN = "open"
STATUS_CLOSED_VERIFIED = "closed-verified"
STATUS_DISCREPANCY = "discrepancy"

# saga_id becomes a path component under .claude/saga/sagas/ — a traversal value
# ("../..", absolute path) would read/write outside the sidecar directory. Single
# path segment, alphanumeric first char (also excludes "." / ".." / leading "-").
# Duplicated (not shared) from merge_watcher.py / ship_undo.py by house convention —
# each sidecar module stays dependency-free.
_SAGA_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_PR_NUMBER_RE = re.compile(r"[0-9]+")


class ShipTeardownError(Exception):
    """Base error for ship_teardown.py — always caught at the CLI boundary and
    reported as a message, never an uncaught traceback."""


class UnknownResourceError(ShipTeardownError):
    """``close()`` was called against a ``resource_id`` with no manifest entry —
    fail-loud, never a silent no-op (an unregistered close would hide a real leak)."""

    def __init__(self, saga_id: str, resource_id: str) -> None:
        self.saga_id = saga_id
        self.resource_id = resource_id
        super().__init__(
            f"no opened_resources.json entry {resource_id!r} for saga {saga_id!r}; "
            "close() refuses to invent an entry — register() it first"
        )


class InvalidResourceKindError(ShipTeardownError):
    """``register()`` was called with a kind outside ``RESOURCE_KINDS`` (KTD2's
    closed vocabulary)."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        super().__init__(f"invalid resource kind {kind!r}; expected one of {RESOURCE_KINDS}")


# --------------------------------------------------------------------------- #
# Subprocess helper — runner injectable, never bound as a default argument.
# --------------------------------------------------------------------------- #


def _run(
    cmd: Sequence[str],
    *,
    cwd: Path,
    runner: Callable[..., Any] | None = None,
) -> subprocess.CompletedProcess[str]:
    run = runner if runner is not None else subprocess.run
    return run(  # nosec B603 — fixed argv, no shell
        list(cmd),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


# --------------------------------------------------------------------------- #
# Sidecar path + read/write (KTD2 hardening: traversal guard, atomic write,
# wrapped decode errors)
# --------------------------------------------------------------------------- #


def _validate_saga_id(saga_id: str) -> str:
    if not _SAGA_ID_RE.fullmatch(saga_id):
        raise ShipTeardownError(
            f"invalid saga_id {saga_id!r}: must be a single path-safe segment "
            "matching [A-Za-z0-9][A-Za-z0-9._-]* (e.g. issue-347)"
        )
    return saga_id


def manifest_path(repo_root: Path, saga_id: str) -> Path:
    return repo_root / SAGAS_DIR / _validate_saga_id(saga_id) / MANIFEST_NAME


def _read_manifest(repo_root: Path, saga_id: str) -> dict[str, dict[str, Any]]:
    """Read the manifest's ``{resource_id -> entry}`` map. An absent sidecar is an
    empty manifest (a ceremony that opened nothing may still reconcile clean) — this
    is deliberately NOT an error, unlike merge_expectation.json's ``validate`` path,
    because register-on-open naturally starts from nothing."""
    path = manifest_path(repo_root, saga_id)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ShipTeardownError(
                f"opened_resources.json at {path} is not valid JSON: {exc}"
            ) from exc
    entries = data.get("resources", {}) if isinstance(data, dict) else {}
    return {str(k): dict(v) for k, v in entries.items() if isinstance(v, dict)}


def _write_manifest(
    repo_root: Path, saga_id: str, entries: Mapping[str, Mapping[str, Any]]
) -> Path:
    path = manifest_path(repo_root, saga_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"resources": {k: dict(v) for k, v in entries.items()}}
    # Atomic replace (same idiom as merge_watcher._write_sidecar / saga.py's
    # _atomic_write) — a crash mid-write must never leave a torn manifest.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


# --------------------------------------------------------------------------- #
# register / close (R1)
# --------------------------------------------------------------------------- #


def register(
    repo_root: Path,
    saga_id: str,
    resource_id: str,
    *,
    kind: str,
    ref: str,
    opened_by: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Register a resource the ceremony opens, at the moment it opens it (R1).

    Idempotent per ``resource_id``: re-registering an entry that is still open
    refreshes ``opened_at``/``kind``/``ref``/``opened_by`` to the new call's values.
    Re-registering an entry that is already **closed** is a no-op — it does not
    reopen a closed resource; call ``close`` again if that is genuinely intended.
    """
    if kind not in RESOURCE_KINDS:
        raise InvalidResourceKindError(kind)
    entries = _read_manifest(repo_root, saga_id)
    existing = entries.get(resource_id)
    if existing is not None and existing.get("closed_at"):
        return dict(existing)
    entry = {
        "kind": kind,
        "ref": ref,
        "opened_at": now or datetime.now(UTC).isoformat(),
        "opened_by": opened_by,
        "closed_at": "",
        "close_evidence": "",
    }
    entries[resource_id] = entry
    _write_manifest(repo_root, saga_id, entries)
    return dict(entry)


def close(
    repo_root: Path,
    saga_id: str,
    resource_id: str,
    *,
    evidence: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Record ``closed_at`` + ``close_evidence`` on a registered entry. Refuses on
    an unknown ``resource_id`` (fail-loud — closing something never registered would
    hide a real accounting gap)."""
    entries = _read_manifest(repo_root, saga_id)
    if resource_id not in entries:
        raise UnknownResourceError(saga_id, resource_id)
    entry = dict(entries[resource_id])
    entry["closed_at"] = now or datetime.now(UTC).isoformat()
    entry["close_evidence"] = evidence
    entries[resource_id] = entry
    _write_manifest(repo_root, saga_id, entries)
    return dict(entry)


def read_manifest(repo_root: Path, saga_id: str) -> dict[str, dict[str, Any]]:
    """Public read accessor — the manifest as currently on disk (no reality probe;
    use ``reconcile`` for the reality-checked view)."""
    return _read_manifest(repo_root, saga_id)


# --------------------------------------------------------------------------- #
# reconcile — reality-checked closing count (R2, R5, KTD4)
# --------------------------------------------------------------------------- #


@dataclass
class ReconcileEntry:
    resource_id: str
    kind: str
    ref: str
    status: str  # open / closed-verified / discrepancy
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "kind": self.kind,
            "ref": self.ref,
            "status": self.status,
            "note": self.note,
        }


@dataclass
class ReconcileReport:
    saga_id: str
    entries: list[ReconcileEntry] = field(default_factory=list)

    @property
    def closing_count(self) -> int:
        return sum(1 for e in self.entries if e.status != STATUS_CLOSED_VERIFIED)

    @property
    def clean(self) -> bool:
        return self.closing_count == 0

    @property
    def blockers(self) -> list[ReconcileEntry]:
        return [e for e in self.entries if e.status != STATUS_CLOSED_VERIFIED]

    def lines(self) -> list[str]:
        out = []
        for e in self.blockers:
            note = f" ({e.note})" if e.note else ""
            out.append(f"{e.status}: {e.kind} {e.ref!r} [{e.resource_id}]{note}")
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "saga_id": self.saga_id,
            "closing_count": self.closing_count,
            "clean": self.clean,
            "entries": [e.to_dict() for e in self.entries],
            "blockers": self.lines(),
        }


def _probe_branch_alive(repo_root: Path, ref: str, runner: Callable[..., Any] | None) -> bool:
    result = _run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=repo_root, runner=runner)
    return getattr(result, "returncode", 1) == 0


def _probe_worktree_alive(repo_root: Path, ref: str, runner: Callable[..., Any] | None) -> bool:
    result = _run(["git", "worktree", "list", "--porcelain"], cwd=repo_root, runner=runner)
    if getattr(result, "returncode", 1) != 0:
        # Degrade safe: an unreadable worktree list must never falsely report clean.
        return True
    target = str(Path(ref))
    for line in (result.stdout or "").splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree ") :].strip()
            if str(Path(path)) == target:
                return True
    return False


def _probe_scratch_alive(ref: str) -> bool:
    return Path(ref).exists()


def _probe_draft_pr_alive(
    repo_root: Path, ref: str, runner: Callable[..., Any] | None
) -> tuple[bool, str]:
    pr_number = ref.lstrip("#")
    if not _PR_NUMBER_RE.fullmatch(pr_number):
        # Not a plain PR number — refuse to pass it to gh; degrade safe (still alive).
        return True, f"ref {ref!r} is not a plain PR number; could not probe"
    result = _run(["gh", "pr", "view", pr_number, "--json", "state"], cwd=repo_root, runner=runner)
    if getattr(result, "returncode", 1) != 0:
        return True, "gh pr view failed; degrading safe (treated as still open)"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return True, "gh pr view returned unparseable JSON; degrading safe"
    state = str(payload.get("state", "")).upper()
    return state == "OPEN", f"live PR state: {state or 'UNKNOWN'}"


def _probe_closed_entry(
    repo_root: Path, kind: str, ref: str, runner: Callable[..., Any] | None
) -> tuple[bool, str]:
    """Probe whether a resource marked closed is, per reality, still alive
    (KTD4 — closed-but-alive is a discrepancy, never silently trusted).

    ``background_session`` has no liveness oracle (KTD4): a session closes only via
    explicit ``close`` with evidence, and that close is trusted once recorded — there
    is nothing to re-probe.
    """
    if kind == "branch":
        return _probe_branch_alive(repo_root, ref, runner), ""
    if kind == "worktree":
        return _probe_worktree_alive(repo_root, ref, runner), ""
    if kind == "scratch":
        return _probe_scratch_alive(ref), ""
    if kind == "draft_pr":
        return _probe_draft_pr_alive(repo_root, ref, runner)
    if kind == "background_session":
        return False, ""
    # Unknown kind on an otherwise-valid entry: degrade safe, never crash reconcile.
    return True, f"unrecognized kind {kind!r}; degrading safe"


def reconcile(
    repo_root: Path,
    saga_id: str,
    *,
    runner: Callable[..., Any] | None = None,
) -> ReconcileReport:
    """Derive the closing count on read, reality-probing every closed entry (R2, R5).

    Open entries always count toward the closing count (nothing to probe — they are
    plainly not yet closed). Closed entries are probed per kind (KTD4); a probe that
    finds the resource still alive is reported as ``discrepancy`` and counts toward
    the closing count exactly like ``open`` — an entry the manifest claims is closed
    is never silently trusted.
    """
    entries = _read_manifest(repo_root, saga_id)
    report = ReconcileReport(saga_id=saga_id)
    for resource_id, entry in sorted(entries.items()):
        kind = str(entry.get("kind", ""))
        ref = str(entry.get("ref", ""))
        closed_at = entry.get("closed_at") or ""
        if not closed_at:
            report.entries.append(
                ReconcileEntry(resource_id, kind, ref, STATUS_OPEN, "not yet closed")
            )
            continue
        still_alive, note = _probe_closed_entry(repo_root, kind, ref, runner)
        if still_alive:
            report.entries.append(
                ReconcileEntry(
                    resource_id,
                    kind,
                    ref,
                    STATUS_DISCREPANCY,
                    note or "marked closed but resource still exists",
                )
            )
        else:
            report.entries.append(
                ReconcileEntry(resource_id, kind, ref, STATUS_CLOSED_VERIFIED, note)
            )
    return report


# --------------------------------------------------------------------------- #
# reclaim — certificate-gated merged-worktree reclamation, on-demand + idle
# (R6, R7, KTD6, KTD7, KTD8)
# --------------------------------------------------------------------------- #

# Per-candidate reclaim outcome vocabulary. Only ``removed`` frees disk; every other
# action leaves the worktree in place and is reported (never a silent drop).
ACTION_REMOVED = "removed"
ACTION_REMOVAL_FAILED = "removal-failed"
ACTION_SKIP_PRIMARY = "skipped-primary"
ACTION_SKIP_SELF = "skipped-self"
ACTION_SKIP_BARE = "skipped-bare"
ACTION_SKIP_PRUNABLE = "skipped-prunable"
ACTION_SKIP_DIRTY = "skipped-dirty"
ACTION_SKIP_UNMERGED = "skipped-unmerged"
ACTION_SKIP_RECENT = "skipped-recent-activity"
ACTION_SKIP_GATED = "skipped-gated"

_DURATION_RE = re.compile(r"(\d+)([smhd])")
_DURATION_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}

# The op kind reclaim routes every merged-worktree removal through (KTD7). Kept as a
# plain string so this module does not import reversibility_certificate at load time;
# reclaim resolves the real authority lazily and compares the verdict by value.
WORKTREE_RECLAIM_MERGED = "worktree-reclaim-merged"
_VERDICT_AUTHORIZED = "AUTHORIZED"


def _parse_duration(text: str) -> float:
    """``24h`` / ``30m`` / ``1d`` / ``90s`` → seconds. Raises on an unparseable value
    (a silently-misread bound would defeat the idle guard)."""
    match = _DURATION_RE.fullmatch(text.strip())
    if not match:
        raise ShipTeardownError(
            f"invalid --if-idle duration {text!r}; expected <int><s|m|h|d> (e.g. 24h)"
        )
    return float(int(match.group(1)) * _DURATION_UNIT_SECONDS[match.group(2)])


@dataclass
class WorktreeInfo:
    """One block parsed from ``git worktree list --porcelain``."""

    path: str
    head: str
    branch: str  # "refs/heads/x" or "" when detached/bare
    detached: bool
    bare: bool
    is_primary: bool


def _parse_worktree_list(stdout: str) -> list[WorktreeInfo]:
    """Parse ``git worktree list --porcelain`` into ordered blocks. The FIRST block is
    the main (primary) worktree — git always lists it first — so it is flagged
    ``is_primary`` and is never a reclaim candidate (KTD6)."""
    infos: list[WorktreeInfo] = []
    path = head = branch = ""
    detached = bare = False
    have_block = False

    def _flush() -> None:
        nonlocal path, head, branch, detached, bare, have_block
        if have_block and path:
            infos.append(
                WorktreeInfo(
                    path=path,
                    head=head,
                    branch=branch,
                    detached=detached,
                    bare=bare,
                    is_primary=(len(infos) == 0),
                )
            )
        path = head = branch = ""
        detached = bare = False
        have_block = False

    for raw in stdout.splitlines():
        line = raw.rstrip()
        if not line:
            _flush()
            continue
        have_block = True
        if line.startswith("worktree "):
            path = line[len("worktree ") :].strip()
        elif line.startswith("HEAD "):
            head = line[len("HEAD ") :].strip()
        elif line.startswith("branch "):
            branch = line[len("branch ") :].strip()
        elif line == "detached":
            detached = True
        elif line == "bare":
            bare = True
    _flush()
    return infos


def _realpath(path: str) -> str:
    return os.path.realpath(path) if path else ""


def _self_toplevel(repo_root: Path, runner: Callable[..., Any] | None) -> str:
    """The realpath of the worktree ``reclaim`` itself runs in — never reclaimed
    (removing your own cwd's worktree would yank the ground out from under the run)."""
    result = _run(["git", "rev-parse", "--show-toplevel"], cwd=repo_root, runner=runner)
    if getattr(result, "returncode", 1) != 0:
        return _realpath(str(repo_root))
    return _realpath((result.stdout or "").strip())


def _worktree_is_dirty(worktree_path: str, runner: Callable[..., Any] | None) -> bool:
    """True if the worktree has uncommitted changes — or if its status is unreadable
    (degrade safe: never remove a worktree we cannot prove is clean, KTD6)."""
    try:
        result = _run(["git", "status", "--porcelain"], cwd=Path(worktree_path), runner=runner)
    except OSError:
        # A vanished/unreadable working directory (prunable worktree) must degrade to
        # "dirty" (skip), never crash the SessionStart hook — code-review P1.
        return True
    if getattr(result, "returncode", 1) != 0:
        return True
    return bool((result.stdout or "").strip())


def _is_merged(
    repo_root: Path, head: str, main_ref: str, runner: Callable[..., Any] | None
) -> bool:
    """Merged-ness per KTD6: ``git merge-base --is-ancestor <head> <main>`` (covers
    named branches AND detached HEADs). Return code 0 → ancestor of main → merged;
    anything else (not-ancestor rc 1, or an error) → treated as unmerged, left alone."""
    if not head:
        return False
    result = _run(
        ["git", "merge-base", "--is-ancestor", head, main_ref], cwd=repo_root, runner=runner
    )
    return getattr(result, "returncode", 1) == 0


def _candidate_activity_mtime(worktree_path: str) -> float | None:
    """Newest mtime among a candidate worktree's own top-level dir and its ``.git``
    gitdir pointer (KTD8 per-candidate bound). A live sibling session sitting clean on
    a just-merged head touches one of these; that keeps it out of an idle sweep."""
    newest: float | None = None
    for probe in (worktree_path, os.path.join(worktree_path, ".git")):
        try:
            mtime = os.stat(probe).st_mtime
        except OSError:
            continue
        newest = mtime if newest is None else max(newest, mtime)
    return newest


def _newest_activity_mtime(repo_root: Path, runner: Callable[..., Any] | None) -> float | None:
    """Newest mtime across the saga sidecars and the outcome worktree registries — the
    global idle-gate source (KTD8). ``None`` when nothing has ever been written (an
    untouched repo is trivially idle)."""
    newest: float | None = None
    sagas_dir = repo_root / SAGAS_DIR
    if sagas_dir.exists():
        for entry in sagas_dir.rglob("*"):
            if entry.is_file():
                try:
                    mtime = entry.stat().st_mtime
                except OSError:
                    continue
                newest = mtime if newest is None else max(newest, mtime)
    # Best-effort: fold in the outcome worktree registries (never fatal — a repo with
    # no outcome store simply has none, and a git failure resolving the common dir is
    # swallowed so idle detection never crashes the hook).
    try:
        import outcome_store  # noqa: PLC0415

        common = outcome_store.resolve_common_dir(repo_root, runner=runner)
        for registry in (common / outcome_store.STORE_NAMESPACE).glob("*/worktrees.json"):
            try:
                mtime = registry.stat().st_mtime
            except OSError:
                continue
            newest = mtime if newest is None else max(newest, mtime)
    except Exception:  # noqa: BLE001 — idle detection is best-effort, never fatal
        pass
    return newest


def _verdict_authorized(verdict: Any) -> bool:
    return str(verdict) == _VERDICT_AUTHORIZED


def _default_authorize(op_kind: str) -> Any:
    """Resolve the fleet's real write authority lazily (KTD7). Injectable in tests so a
    GATE verdict can be simulated without monkeypatching the registry."""
    import reversibility_certificate  # noqa: PLC0415

    return reversibility_certificate.authorize_write(op_kind)


def _reap_via_registry(
    repo_root: Path, worktree_path: str, runner: Callable[..., Any] | None
) -> bool | None:
    """Strictly route a managed outcome path through its registry-owned reaper.

    ``None`` is reserved for paths outside ``.saga-worktrees``. Once a path enters the canonical
    managed namespace, store resolution, strict registry parsing, exact entry lookup, and path binding
    must all succeed; any ambiguity raises so the caller cannot fall through to raw Git removal.
    """
    saga_root = _realpath(str(repo_root / ".saga-worktrees"))
    target = _realpath(worktree_path)
    if not saga_root or not (target == saga_root or target.startswith(saga_root + os.sep)):
        return None
    try:
        rel = os.path.relpath(target, saga_root)
    except ValueError as exc:
        raise ShipTeardownError(
            f"managed outcome worktree path could not be resolved safely: {worktree_path}"
        ) from exc
    parts = rel.split(os.sep)
    if len(parts) != 2 or any(part in ("", os.curdir, os.pardir) for part in parts):
        raise ShipTeardownError(
            "managed outcome worktree retained: expected canonical "
            f".saga-worktrees/<outcome>/<subplot> path, found {worktree_path}"
        )
    outcome_id, subplot_id = parts[0], parts[1]
    try:
        import outcome_store  # noqa: PLC0415
        import outcome_worktrees  # noqa: PLC0415

        store = outcome_store.Store.for_outcome(outcome_id, repo_root, runner=runner)
    except Exception as exc:  # noqa: BLE001 — plugin/store skew must retain managed resources
        raise ShipTeardownError(
            f"managed outcome worktree retained: cannot resolve store for {outcome_id!r}: {exc}"
        ) from exc
    try:
        registry = outcome_worktrees.read_registry_strict(store)
    except outcome_worktrees.WorktreeError as exc:
        raise ShipTeardownError(
            f"managed outcome worktree retained: registry is unreadable or corrupt: {exc}"
        ) from exc
    entry = registry.get(subplot_id)
    if entry is None:
        raise ShipTeardownError(
            f"managed outcome worktree retained: registry entry {subplot_id!r} is missing"
        )
    if _realpath(str(entry.get("path", ""))) != target:
        raise ShipTeardownError(
            f"managed outcome worktree retained: registry entry {subplot_id!r} names a different path"
        )
    ops = outcome_worktrees.git_worktree_ops(repo_root, runner=runner)
    try:
        return outcome_worktrees.reap_worktree(store, subplot_id, ops)
    except outcome_worktrees.WorktreeError as exc:
        # Ship teardown holds no reap authority of its own. An entry that fails strict
        # prevalidation must stay intact for the canonical outcome reaper; falling back to plain
        # git removal would sever the registry's ownership record (#677/U3).
        raise ShipTeardownError(
            f"registered outcome worktree retained for canonical registry-owned reap: {exc}"
        ) from exc


def _remove_worktree(
    repo_root: Path, worktree_path: str, runner: Callable[..., Any] | None
) -> tuple[bool, str]:
    """Remove one merged+clean worktree. Registered ``.saga-worktrees`` worktrees route
    through ``reap_worktree`` (registry deregisters); everything else uses a plain
    ``git worktree remove`` (no ``--force`` — a failed removal is kept + reported,
    mirroring ``reap_worktree``'s no-silent-leak discipline)."""
    try:
        reaped = _reap_via_registry(repo_root, worktree_path, runner)
    except ShipTeardownError as exc:
        return False, str(exc)
    if reaped is True:
        return True, "reaped via outcome_worktrees.reap_worktree (registry deregistered)"
    if reaped is False:
        return False, "reap_worktree removal failed — registry entry kept for a later pass"
    result = _run(["git", "worktree", "remove", worktree_path], cwd=repo_root, runner=runner)
    if getattr(result, "returncode", 1) == 0:
        return True, "git worktree remove"
    return False, (getattr(result, "stderr", "") or "git worktree remove failed").strip()


@dataclass
class ReclaimEntry:
    path: str
    head: str
    branch: str
    action: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "head": self.head,
            "branch": self.branch,
            "action": self.action,
            "note": self.note,
        }


@dataclass
class ReclaimReport:
    entries: list[ReclaimEntry] = field(default_factory=list)
    idle_noop: bool = False
    idle_reason: str = ""

    @property
    def removed(self) -> list[ReclaimEntry]:
        return [e for e in self.entries if e.action == ACTION_REMOVED]

    @property
    def skipped(self) -> list[ReclaimEntry]:
        return [e for e in self.entries if e.action != ACTION_REMOVED]

    @property
    def failures(self) -> list[ReclaimEntry]:
        return [e for e in self.entries if e.action == ACTION_REMOVAL_FAILED]

    def lines(self) -> list[str]:
        if self.idle_noop:
            return [f"not idle — reclaim skipped ({self.idle_reason})"]
        out = []
        for e in self.entries:
            note = f" — {e.note}" if e.note else ""
            ref = e.branch or e.head or "(detached)"
            out.append(f"{e.action}: {e.path} [{ref}]{note}")
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "idle_noop": self.idle_noop,
            "idle_reason": self.idle_reason,
            "removed": [e.to_dict() for e in self.removed],
            "skipped": [e.to_dict() for e in self.skipped],
            "entries": [e.to_dict() for e in self.entries],
        }


def reclaim(
    repo_root: Path,
    *,
    main_ref: str = "main",
    if_idle: str | None = None,
    runner: Callable[..., Any] | None = None,
    authorize: Callable[[str], Any] | None = None,
    now: float | None = None,
) -> ReclaimReport:
    """Sweep every linked worktree and remove merged-branch, clean ones under an
    AUTHORIZED certificate; leave unmerged/dirty ones untouched and reported (R6, R7).

    On-demand (``if_idle=None``): skips only dirty and unmerged worktrees. Idle mode
    (``if_idle='24h'``): first the global gate — if the newest mtime among the saga
    sidecars / worktree registries is younger than the bound, the whole call no-ops
    (exit-0 "not idle", KTD8); then the SAME bound is applied per candidate, so a
    merged+clean worktree with recent activity (a live sibling session on a just-merged
    head) is skipped even though it would otherwise be reclaimable.
    """
    now_ts = now if now is not None else time.time()
    authorize_fn = authorize if authorize is not None else _default_authorize

    bound: float | None = None
    if if_idle is not None:
        bound = _parse_duration(if_idle)
        newest = _newest_activity_mtime(repo_root, runner)
        if newest is not None and (now_ts - newest) < bound:
            age = now_ts - newest
            return ReclaimReport(
                idle_noop=True,
                idle_reason=f"newest activity {age:.0f}s ago < bound {bound:.0f}s",
            )

    result = _run(["git", "worktree", "list", "--porcelain"], cwd=repo_root, runner=runner)
    report = ReclaimReport()
    if getattr(result, "returncode", 1) != 0:
        # Degrade safe: an unreadable worktree list removes nothing.
        return report

    infos = _parse_worktree_list(result.stdout or "")
    self_top = _self_toplevel(repo_root, runner)

    for info in infos:
        canon = _realpath(info.path)
        if info.is_primary:
            report.entries.append(
                ReclaimEntry(
                    info.path,
                    info.head,
                    info.branch,
                    ACTION_SKIP_PRIMARY,
                    "primary worktree — never reclaimed",
                )
            )
            continue
        if canon and canon == self_top:
            report.entries.append(
                ReclaimEntry(
                    info.path,
                    info.head,
                    info.branch,
                    ACTION_SKIP_SELF,
                    "the worktree reclaim runs in — never reclaimed",
                )
            )
            continue
        if info.bare:
            report.entries.append(
                ReclaimEntry(
                    info.path,
                    info.head,
                    info.branch,
                    ACTION_SKIP_BARE,
                    "bare worktree — nothing to reclaim",
                )
            )
            continue
        if not os.path.isdir(info.path):
            # Prunable worktree: git still lists it but the working directory is gone
            # (removed out-of-band). Report it instead of crashing on cwd probes.
            report.entries.append(
                ReclaimEntry(
                    info.path,
                    info.head,
                    info.branch,
                    ACTION_SKIP_PRUNABLE,
                    "working directory missing (prunable) — run 'git worktree prune'",
                )
            )
            continue
        if _worktree_is_dirty(info.path, runner):
            report.entries.append(
                ReclaimEntry(
                    info.path,
                    info.head,
                    info.branch,
                    ACTION_SKIP_DIRTY,
                    "uncommitted changes — left untouched",
                )
            )
            continue
        if not _is_merged(repo_root, info.head, main_ref, runner):
            report.entries.append(
                ReclaimEntry(
                    info.path,
                    info.head,
                    info.branch,
                    ACTION_SKIP_UNMERGED,
                    f"head not an ancestor of {main_ref} — left untouched",
                )
            )
            continue
        if bound is not None:
            cand_mtime = _candidate_activity_mtime(info.path)
            if cand_mtime is not None and (now_ts - cand_mtime) < bound:
                age = now_ts - cand_mtime
                report.entries.append(
                    ReclaimEntry(
                        info.path,
                        info.head,
                        info.branch,
                        ACTION_SKIP_RECENT,
                        f"recent activity {age:.0f}s ago < bound {bound:.0f}s "
                        "(sibling-session guard)",
                    )
                )
                continue
        verdict = authorize_fn(WORKTREE_RECLAIM_MERGED)
        if not _verdict_authorized(verdict):
            report.entries.append(
                ReclaimEntry(
                    info.path,
                    info.head,
                    info.branch,
                    ACTION_SKIP_GATED,
                    f"reversibility certificate verdict {str(verdict)!r} — not removed",
                )
            )
            continue
        removed, note = _remove_worktree(repo_root, info.path, runner)
        report.entries.append(
            ReclaimEntry(
                info.path,
                info.head,
                info.branch,
                ACTION_REMOVED if removed else ACTION_REMOVAL_FAILED,
                note,
            )
        )
    return report


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root", type=Path, default=Path.cwd(), help="repo root (default: cwd)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_register = sub.add_parser("register", help="register an opened resource")
    p_register.add_argument("--saga-id", required=True)
    p_register.add_argument("--resource-id", required=True)
    p_register.add_argument("--kind", required=True, choices=RESOURCE_KINDS)
    p_register.add_argument("--ref", required=True)
    p_register.add_argument("--opened-by", required=True)

    p_close = sub.add_parser("close", help="record a resource as closed")
    p_close.add_argument("--saga-id", required=True)
    p_close.add_argument("--resource-id", required=True)
    p_close.add_argument("--evidence", required=True)

    p_reconcile = sub.add_parser(
        "reconcile", help="read-only: print CLEAN or HALT + named blockers"
    )
    p_reconcile.add_argument("--saga-id", required=True)

    p_reclaim = sub.add_parser(
        "reclaim",
        help="remove merged-branch, clean worktrees under an AUTHORIZED certificate",
    )
    p_reclaim.add_argument("--main-ref", default="main", help="the merged-into ref (default: main)")
    p_reclaim.add_argument(
        "--if-idle",
        default=None,
        metavar="DURATION",
        help="no-op unless idle past DURATION (e.g. 24h); also skips recently-active worktrees",
    )
    p_reclaim.add_argument(
        "--quiet", action="store_true", help="suppress per-worktree report lines (hook path)"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root

    try:
        if args.command == "register":
            result = register(
                repo_root,
                args.saga_id,
                args.resource_id,
                kind=args.kind,
                ref=args.ref,
                opened_by=args.opened_by,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
        elif args.command == "close":
            result = close(repo_root, args.saga_id, args.resource_id, evidence=args.evidence)
            print(json.dumps(result, indent=2, sort_keys=True))
        elif args.command == "reconcile":
            report = reconcile(repo_root, args.saga_id)
            if report.clean:
                print("CLEAN")
                return 0
            print("HALT")
            for line in report.lines():
                print(f"  - {line}")
            return 1
        elif args.command == "reclaim":
            reclaim_report = reclaim(repo_root, main_ref=args.main_ref, if_idle=args.if_idle)
            if reclaim_report.idle_noop:
                if not args.quiet:
                    print(reclaim_report.lines()[0])
                return 0
            if not args.quiet:
                for line in reclaim_report.lines():
                    print(f"  - {line}")
                print(
                    f"reclaimed {len(reclaim_report.removed)}, "
                    f"skipped {len(reclaim_report.skipped)}"
                )
            # A failed removal is a real problem (kept + reported); surface it as a
            # non-zero exit even on the --quiet hook path so it is not silently lost.
            return 1 if reclaim_report.failures else 0
        else:  # pragma: no cover - argparse enforces valid choices
            parser.error(f"unknown command {args.command!r}")
            return 2
    except ShipTeardownError as exc:
        print(f"ship_teardown: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
