"""Durable delegation audit store: a machine-local mirror that survives worktree teardown (#396).

Delegation evidence lives entirely inside disposable storage today. `agy_delegate.py`'s bundle
functions write every run's `envelope.json` / `result.json` (embedding a `bridge_receipt.v1` when
the run launched) under `repo_root/.claude/agy/runs/<run_id>` — inside the working tree, gone the
moment a disposable saga worktree is reclaimed. `engine_dispatch.py`'s dispatch-manifest write path
persists the equivalent `saga.manifest.v1` under the git-common-dir cache (`manifest_store.py`),
which is shared across worktrees of one checkout but still dies with the checkout itself.

This module is the durable mirror: every receipt, result snapshot, and provenance manifest a
delegation produces is ALSO written here, at a machine-local root outside any repository
(`~/.claude/delegation-audit` by default), resolvable by `run_id` (or the equivalent
`execution_id` — one identity namespace, see the plan's KTD8) alone, independent of whether the
originating bundle directory or its enclosing worktree still exists.

Deliberately the OPPOSITE store-root choice from `evidence_ledger.py` (#398): that ledger is
**committed**, per-saga (`docs/evidence/<saga-id>/`), because a fresh clone on a different machine
must verify a custody chain that belongs in PR history. This store answers a different question —
delegation evidence must survive worktree teardown on the SAME machine, never needs to reach a
different developer's clone, and committing raw diffs/receipts to every PR would bloat history for
no reader. Hence machine-local and git-ignored by construction (it lives outside any repo).

Duplicates the small atomic-write / write-once / path-traversal-guard primitives
`plugins/saga/scripts/outcome_store.py` already defines, rather than importing that module:
fleet-core must be installable/importable independent of the saga plugin (agy and team-execution
reach this module through `fleet_commons_shim.load("audit_store")`, never by vendoring saga's
script tree) — the same install-boundary rationale `bridge_receipt.py`'s own docstring documents
for reusing this exact pattern rather than reaching across a plugin boundary.

Store layout, under `audit_store_root`::

    runs/<id>/receipt.json           # raw bridge_receipt.v1, when the run produced one
    runs/<id>/result.json            # agy's full result_payload snapshot (status, agy_launched, ...)
    runs/<id>/manifest.json          # saga.manifest.v1 (engine_dispatch), carries `disposition`
    delegation-drafts/<id>/raw.diff  # write-once: the engine's raw pre-fix returned patch/output

No I/O at import. Pure-ish functions over an explicit `Store` value (the `outcome_store` /
`manifest_store` / `evidence_ledger` house pattern).
"""

from __future__ import annotations

import contextlib
import json
import os
import stat
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_AUDIT_STORE_ROOT = Path.home() / ".claude" / "delegation-audit"

RUNS_NAMESPACE = "runs"
DRAFTS_NAMESPACE = "delegation-drafts"


class AuditStoreError(ValueError):
    """An audit-store operation was rejected (path traversal, write-once collision)."""


# ---------------------------------------------------------------------------
# Safe names + atomic-write primitives (KTD2 — duplicated, not cross-imported)
# ---------------------------------------------------------------------------


def _safe_name(name: str, *, what: str = "id") -> str:
    """Reject a name that would escape the store directory (path traversal / separators)."""
    if not name:
        raise AuditStoreError(f"{what} must be non-empty")
    if "/" in name or "\\" in name or name in (".", "..") or "\x00" in name:
        raise AuditStoreError(f"{what} {name!r} must not contain a path separator or be '.'/'..'")
    return name


def _unique_tmp(path: Path) -> Path:
    """A temp sibling unique per process AND thread AND instant (mirrors ``outcome_store``)."""
    return path.with_name(
        f"{path.name}.{os.getpid()}.{threading.get_ident()}.{time.monotonic_ns()}.tmp"
    )


def _write_temp_0600(tmp: Path, content: str) -> None:
    """Write ``content`` to ``tmp`` mode ``0600`` — no pre-replace world-readable window.

    This store mirrors receipts, agy result payloads, provenance manifests, and raw pre-fix
    engine output — content this diff's own docstring already flags as potentially sensitive.
    Mirrors ``manifest_store.py``'s ``_atomic_write_manifest`` precedent (``os.fchmod(fd,
    0o600)``) for the identical ``manifest.json`` content this module also mirrors, rather than
    the weaker unrestricted-mode ``outcome_store.py`` primitives this module otherwise matches.
    """
    fd = os.open(
        tmp,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(fd, 0o600)  # belt-and-suspenders against an inherited restrictive umask
        payload = memoryview(content.encode("utf-8"))
        while payload:
            written = os.write(fd, payload)
            payload = payload[written:]
    finally:
        os.close(fd)


def _atomic_write(path: Path, content: str) -> None:
    """Overwrite ``path`` atomically (temp + ``os.replace``) so no reader sees a torn file."""
    _ensure_private_dir(path.parent)
    tmp = _unique_tmp(path)
    _write_temp_0600(tmp, content)
    os.replace(tmp, path)


def _write_once(path: Path, content: str) -> bool:
    """Create ``path`` atomically, refusing to clobber an existing file.

    Returns True if this call created the file, False if it already existed. Uses temp +
    ``os.link`` so a crash mid-write leaves only the temp file, never a torn final file.
    """
    _ensure_private_dir(path.parent)
    tmp = _unique_tmp(path)
    _write_temp_0600(tmp, content)
    try:
        os.link(tmp, path)
        return True
    except FileExistsError:
        return False
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _refuse_unsafe_ancestors(path: Path) -> None:
    """Refuse symlinked or world-writable existing components strictly below the user's home.

    The scope test is lexical on the expanded absolute path: the home directory itself and any
    path outside home entirely (e.g. system temp roots, whose sticky world-writable mode is
    expected) are exempt. Components are inspected with ``lstat``, never resolved, so a
    symlinked ancestor is refused before any ``mkdir`` traverses it.

    Reach differs per branch because ``Store.for_root`` canonicalizes the root with
    ``resolve()`` before any write path gets here. Mode bits survive that resolution, so the
    world-writable refusal covers every caller; symlink identity does not, so the symlink
    refusal covers direct callers of this function and the window after resolution — not a
    symlinked ancestor of a root that ``for_root`` already collapsed.
    """
    home = Path.home()
    candidate = path if path.is_absolute() else Path(os.path.abspath(path))
    if not candidate.is_relative_to(home) or candidate == home:
        return
    current = home
    for part in candidate.relative_to(home).parts:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            return  # nothing exists from here down; creation below is 0o700
        except PermissionError as exc:
            raise AuditStoreError(f"audit-store ancestor is not inspectable: {current}") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise AuditStoreError(f"audit-store ancestor is a symlink: {current}")
        if stat.S_ISDIR(metadata.st_mode) and metadata.st_mode & 0o002:
            raise AuditStoreError(f"audit-store ancestor is world-writable: {current}")


def _ensure_private_dir(path: Path) -> None:
    _refuse_unsafe_ancestors(path)
    missing: list[Path] = []
    current = path
    while not current.exists() and not current.is_symlink():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        os.chmod(directory, 0o700, follow_symlinks=False)
    metadata = path.lstat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise AuditStoreError(f"audit-store directory is unsafe: {path}")


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Store:
    """A handle to the durable audit-store root."""

    root: Path

    @classmethod
    def for_root(cls, root: Path | str | None) -> Store:
        """Resolve a ``Store`` — ``root`` overrides, ``None`` resolves ``DEFAULT_AUDIT_STORE_ROOT``.

        Real-world "on by default" behavior lives at each caller's outermost entry point (agy's CLI
        ``main()``; the documented chaperone call site for ``engine_dispatch.py``, which has no
        CLI) — this classmethod itself has no opinion about whether mirroring should happen at
        all; a caller that never constructs a ``Store`` never touches the filesystem here.
        """
        resolved = Path(root) if root is not None else DEFAULT_AUDIT_STORE_ROOT
        return cls(root=resolved.expanduser().resolve())

    def run_dir(self, run_id: str) -> Path:
        return self.root / RUNS_NAMESPACE / _safe_name(run_id, what="run_id")

    def receipt_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "receipt.json"

    def result_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "result.json"

    def manifest_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "manifest.json"

    def noncanonical_manifest_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "noncanonical-manifest.json"

    def draft_dir(self, run_id: str) -> Path:
        return self.root / DRAFTS_NAMESPACE / _safe_name(run_id, what="run_id")

    def draft_path(self, run_id: str) -> Path:
        return self.draft_dir(run_id) / "raw.diff"

    def ensure(self) -> Store:
        _ensure_private_dir(self.root)
        return self


# ---------------------------------------------------------------------------
# Mirror writes (overwrite-in-place — these mirror a bundle/manifest's own
# mutability contract, never a custody-critical write-once artifact)
# ---------------------------------------------------------------------------


def mirror_receipt(store: Store, run_id: str, receipt: dict[str, Any]) -> Path:
    """Mirror a raw ``bridge_receipt.v1`` payload, keyed by ``run_id``/``execution_id`` (KTD8)."""
    path = store.receipt_path(run_id)
    _atomic_write(path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return path


def mirror_result(store: Store, run_id: str, result_payload: dict[str, Any]) -> Path:
    """Mirror agy's full ``result_payload`` snapshot, keyed by ``run_id``."""
    path = store.result_path(run_id)
    _atomic_write(path, json.dumps(result_payload, indent=2, sort_keys=True) + "\n")
    return path


def mirror_manifest(store: Store, run_id: str, manifest: dict[str, Any]) -> Path:
    """Mirror a ``saga.manifest.v1`` payload, keyed by ``execution_id`` (KTD8).

    Overwrites any prior mirrored manifest for the same id — mirrors ``manifest_store.write_manifest``'s
    own "never write-once, overwrite in place" contract, since a manifest may be updated in place
    (e.g. an adjudication written after the claimed-layer manifest).
    """
    path = store.manifest_path(run_id)
    _atomic_write(path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return path


def mirror_noncanonical_manifest(store: Store, run_id: str, manifest: dict[str, Any]) -> Path:
    """Mirror compatibility evidence without replacing the canonical manifest mirror."""

    path = store.noncanonical_manifest_path(run_id)
    _atomic_write(path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return path


# ---------------------------------------------------------------------------
# Resolve reads — never raise on absent/corrupt; that is data, not an error
# ---------------------------------------------------------------------------


def resolve_receipt(store: Store, run_id: str) -> dict[str, Any] | None:
    return _read_json(store.receipt_path(run_id))


def resolve_result(store: Store, run_id: str) -> dict[str, Any] | None:
    return _read_json(store.result_path(run_id))


def resolve_manifest(store: Store, run_id: str) -> dict[str, Any] | None:
    return _read_json(store.manifest_path(run_id))


def resolve_noncanonical_manifest(store: Store, run_id: str) -> dict[str, Any] | None:
    """Resolve compatibility evidence from its noncanonical audit namespace."""

    return _read_json(store.noncanonical_manifest_path(run_id))


def list_runs(store: Store) -> list[str]:
    """List every run id with at least one mirrored artifact, sorted for determinism."""
    runs_dir = store.root / RUNS_NAMESPACE
    if not runs_dir.is_dir():
        return []
    return sorted(entry.name for entry in runs_dir.iterdir() if entry.is_dir())


# ---------------------------------------------------------------------------
# Write-once pre-fix draft snapshot (R3/KTD7) — the chaperone-dispatch hook
# ---------------------------------------------------------------------------


def write_once_draft(store: Store, run_id: str, content: str) -> Path:
    """Write-once the engine's raw pre-fix returned patch/output, keyed by ``run_id``.

    Raises ``AuditStoreError`` on a second write attempt for the same ``run_id`` — always, even
    when the content is byte-identical (the DoD's own acceptance wording: "refuses to overwrite an
    existing snapshot for that run_id"), never a silent overwrite.
    """
    path = store.draft_path(run_id)
    if path.exists():
        raise AuditStoreError(
            f"a draft snapshot already exists for run_id={run_id!r} at {path} — write-once, "
            "refusing to overwrite"
        )
    created = _write_once(path, content)
    if not created:
        # A concurrent writer won the race between the exists() check and _write_once.
        raise AuditStoreError(
            f"a draft snapshot already exists for run_id={run_id!r} at {path} — write-once, "
            "refusing to overwrite"
        )
    return path


def resolve_draft(store: Store, run_id: str) -> str | None:
    path = store.draft_path(run_id)
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
