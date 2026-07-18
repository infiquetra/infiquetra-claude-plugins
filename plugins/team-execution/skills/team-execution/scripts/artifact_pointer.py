#!/usr/bin/env python3
"""Typed artifact pointers for team-execution — Layer 1 (git-object diff pointers).

A pointer replaces an inlined artifact (a full ``git diff``, a changed file, a symbol) in a
spawned-agent prompt with a small typed reference the already-capable receiver dereferences itself
(issue #291, KTD3). A pointer carries four load-bearing fields beside its ``kind`` — ``locator``,
``hash`` (integrity), ``epoch`` (freshness), and a self-describing ``deref`` command — so a receiving
agent needs zero prior knowledge to fetch and verify the bytes (R1).

Layer 1 (this unit) uses a git **tree object** as the locator's target. The snapshot is built without
touching the user's real index or working tree (KTD1): a temp index seeded from ``HEAD`` via
``git read-tree`` under ``GIT_INDEX_FILE``, then ``git add -A`` + ``git write-tree`` — the resulting
tree OID covers staged, unstaged, *and* untracked files. A holding ref
``refs/team-execution/snapshots/<run-id>/<epoch>`` pins the tree against ``git gc``. Because git is
content-addressed, the tree OID *is* the integrity hash — no second checksum (KTD2). Freshness is the
epoch: a newer epoch ref for the same run-id supersedes an older pointer (monotonic supersession).

Verification (``deref``) is two checks, one pointer (KTD2): integrity = the tree OID is resolvable
AND the holding ref still points at it; freshness = no newer epoch exists for the run-id. Either
failure exits non-zero with a typed code (``POINTER_HASH_MISMATCH`` / ``POINTER_STALE``) on stderr so
the orchestrator can branch on it (R2).

Layer 2 (this unit adds ``store``/``gc``) covers non-git artifacts a repo has no tree object for. It is
a write-once, content-addressed store at ``.claude/team-execution/artifacts/objects/<sha256[:2]>/<sha256>``
(sha256 *is* the integrity hash, mirroring L1's git-object-IS-the-hash design). Storage location reuses
Step B0a's ignored-directory safety check: ``.claude/`` under the repo only when git-ignored there,
else ``~/.claude/team-execution/state/<repo>/artifacts`` (never risk committing run-state). Freshness is
a small JSON sidecar (``index.json``) keyed ``<run-id>/<epoch>`` (KTD2) recording, per run-id, every
epoch's hash and the latest epoch seen — a newer epoch for the same run-id supersedes an older pointer,
matching L1's monotonic-supersession semantics exactly. ``gc`` reclaims both L2 CAS entries and L1
snapshot refs older than a TTL (default 7 days, R9's bounded-store requirement); younger entries survive
untouched.

House pattern (precedent ``plugins/saga/scripts/outcome_github.py``): ``subprocess.run`` is resolved
at call time (never bound as a default arg) so a test could monkeypatch it; git is invoked with a
fixed argv and no shell. Python 3.12, stdlib only, no I/O at import.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import re
import subprocess  # nosec B404 — git only, fixed argv, no shell
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SNAPSHOT_REF_PREFIX = "refs/team-execution/snapshots"
POINTER_KINDS = ("diff", "file", "symbol")

# Layer-2 content-addressed store layout (relative to the resolved store root, KTD2/R8).
CAS_SUBDIR = "objects"
INDEX_FILENAME = "index.json"
DEFAULT_GC_MAX_AGE_DAYS = 7.0

# Typed error codes the orchestrator branches on (R2/KTD2). Stable strings, printed to stderr.
ERR_HASH_MISMATCH = "POINTER_HASH_MISMATCH"
ERR_STALE = "POINTER_STALE"

# A CAS address is a lowercase sha256 hex digest. A pointer's ``hash`` is untrusted input (it travels
# inside spawn prompts), so it is validated against this before it is ever used to build a path.
_SHA256_HEX = re.compile(r"\A[0-9a-f]{64}\Z")
_SUBJECT_ID = re.compile(r"\Asubject:sha256:[0-9a-f]{64}\Z")

# A git object id is 40 hex chars (sha1) or 64 (sha256). A diff pointer's base/snapshot tree OIDs are
# untrusted input, so they are validated against this before being placed on a git argv — a tampered
# ``deref`` field must never reach git (see ``_diff_argv``).
_GIT_OID = re.compile(r"\A[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")

# A ref-name segment (run-id / epoch) is interpolated into a holding-ref path passed to
# ``git update-ref``. Constrain it up front so a hostile segment cannot inject ref-path structure;
# git's own ref-name rules are only the backstop.
_REF_SEGMENT = re.compile(r"\A[A-Za-z0-9._-]+\Z")

LIVENESS_BASELINE_SCHEMA = "liveness.artifact-baseline.v1"
LIVENESS_OBSERVATION_SCHEMA = "liveness.artifact-observation.v1"
EXCLUSIVE_PROVENANCE_SCHEMA = "liveness.exclusive-provenance.v1"
_LIVENESS_BASELINE_KEYS = frozenset(
    {
        "schema",
        "paths",
        "path_set_sha256",
        "baseline_digest",
        "observed_monotonic",
    }
)
_PROVENANCE_KEYS = frozenset(
    {
        "schema",
        "subject_id",
        "lease_id",
        "resource_sha256",
        "token_sha256",
        "broker_epoch",
        "fencing_sequence",
        "paths",
        "path_set_sha256",
        "baseline_digest",
        "current_digest",
        "interval_start",
        "interval_end",
        "custody_ref",
        "covered_generation_ids",
    }
)


def _is_sha256_hex(value: str) -> bool:
    return bool(_SHA256_HEX.match(value))


def _is_git_oid(value: str) -> bool:
    return bool(_GIT_OID.match(value))


def _validate_ref_segment(value: str, *, label: str) -> None:
    if not _REF_SEGMENT.match(value) or ".." in value:
        raise ValueError(
            f"{label} {value!r} is not a ref-name-safe segment ([A-Za-z0-9._-], no '..')"
        )


class GitError(RuntimeError):
    """A git subprocess failed unexpectedly (not a typed verification failure)."""


class PointerError(RuntimeError):
    """A typed verification failure carrying a stable code the orchestrator can branch on."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ArtifactPointer:
    """One typed artifact reference (R1): kind, locator, integrity hash, freshness epoch, deref, base.

    ``base`` is the diff base tree OID for ``kind == "diff"`` (empty for ``file`` / ``symbol``). It is
    a first-class validated field, never parsed out of ``deref``: the L1 deref argv is rebuilt
    deterministically from ``base`` + ``hash`` so a tampered ``deref`` string can never reach git.
    """

    kind: str
    locator: str
    hash: str
    epoch: str
    deref: str
    base: str = ""

    def to_json(self) -> str:
        """Serialize to a single-line JSON object (KTD3: one fenced ``artifact-pointer`` block)."""
        return json.dumps(
            {
                "kind": self.kind,
                "locator": self.locator,
                "hash": self.hash,
                "epoch": self.epoch,
                "deref": self.deref,
                "base": self.base,
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, raw: str) -> ArtifactPointer:
        """Parse a pointer JSON object, rejecting an unknown kind or a missing field."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"artifact pointer is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("artifact pointer must be a JSON object")
        missing = {"kind", "locator", "hash", "epoch", "deref"} - set(data)
        if missing:
            raise ValueError(f"artifact pointer missing fields: {', '.join(sorted(missing))}")
        kind = str(data["kind"])
        if kind not in POINTER_KINDS:
            raise ValueError(f"unknown pointer kind {kind!r} (want one of {POINTER_KINDS})")
        return cls(
            kind=kind,
            locator=str(data["locator"]),
            hash=str(data["hash"]),
            epoch=str(data["epoch"]),
            deref=str(data["deref"]),
            base=str(data.get("base", "")),
        )


def _git(
    args: list[str],
    *,
    repo_root: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run ``git -C <repo_root> <args>``; raise ``GitError`` on failure when ``check``.

    ``subprocess.run`` is referenced at call time (not bound as a default) so a test can monkeypatch
    ``artifact_pointer.subprocess.run`` — precedent ``outcome_github.py:38``.
    """
    full_env = {**os.environ, **env} if env is not None else None
    result = subprocess.run(  # nosec B603 B607 — fixed 'git' argv, no shell
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        env=full_env,
    )
    if check and result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def resolve_repo_root(repo_root_arg: str | None) -> Path:
    """Resolve the repo root from ``--repo-root`` or ``git rev-parse --show-toplevel`` in cwd."""
    if repo_root_arg:
        return Path(repo_root_arg).resolve()
    result = subprocess.run(  # nosec B603 B607 — fixed 'git' argv, no shell
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(f"not inside a git repo: {result.stderr.strip()}")
    return Path(result.stdout.strip())


def _require_dense_worktree(repo_root: Path) -> None:
    """Refuse to snapshot a sparse-checkout worktree (KTD7 loud-fail → orchestrator inlines).

    ``git add -A`` under a temp index can drop skip-worktree paths, yielding a tree that is MISSING
    entries — ``git diff base snapshot`` would then render phantom deletions (silently-wrong bytes,
    violating R2). Sparse-checkout is unsupported by L1; fail loudly here so the orchestrator falls
    back to inlined content (KTD7) rather than shipping a wrong diff.
    """
    result = _git(["config", "--bool", "core.sparseCheckout"], repo_root=repo_root, check=False)
    if result.returncode == 0 and result.stdout.strip() == "true":
        raise GitError(
            "sparse-checkout is not supported by Layer-1 snapshots (git add -A can drop "
            "skip-worktree paths); inline the artifact instead (KTD7 fallback)"
        )


def _finite_nonnegative(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite nonnegative number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{field} must be a finite nonnegative number")
    return result


def _liveness_paths(paths: object, *, repo_root: Path) -> tuple[str, ...]:
    if not isinstance(paths, (list, tuple)) or not paths:
        raise ValueError("liveness paths must be a non-empty list")
    root = repo_root.resolve(strict=True)
    normalized: list[str] = []
    for raw in paths:
        if not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw:
            raise ValueError("liveness paths must be non-empty repo-relative POSIX paths")
        candidate = Path(raw)
        if (
            candidate.is_absolute()
            or raw.startswith("-")
            or any(part in {"", ".", ".."} for part in candidate.parts)
        ):
            raise ValueError(f"liveness path escapes or is not canonical: {raw!r}")
        if candidate.parts[0] == ".git":
            raise ValueError("liveness paths cannot address Git control state")
        resolved = (root / candidate).resolve(strict=False)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"liveness path escapes through a symlink: {raw!r}") from exc
        normalized.append(candidate.as_posix())
    ordered = tuple(sorted(normalized))
    if len(ordered) != len(set(ordered)):
        raise ValueError("liveness paths must be unique")
    return ordered


def _path_set_digest(paths: tuple[str, ...]) -> str:
    return hashlib.sha256(
        json.dumps(list(paths), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _scoped_worktree_digest(paths: tuple[str, ...], *, repo_root: Path) -> str:
    """Hash only declared working-tree paths through a temporary Git index."""
    _require_dense_worktree(repo_root)
    fd, index_path = tempfile.mkstemp(prefix="te-liveness-index-")
    os.close(fd)
    os.unlink(index_path)
    try:
        env = {"GIT_INDEX_FILE": index_path}
        _git(["read-tree", "HEAD"], repo_root=repo_root, env=env)
        _git(["add", "-A", "--", *paths], repo_root=repo_root, env=env)
        listing = _git(
            ["ls-files", "--stage", "-z", "--", *paths],
            repo_root=repo_root,
            env=env,
        ).stdout
    finally:
        if os.path.exists(index_path):
            os.unlink(index_path)
    payload = {
        "paths": list(paths),
        "entries_sha256": hashlib.sha256(listing.encode()).hexdigest(),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def capture_liveness_baseline(
    paths: object,
    *,
    repo_root: Path,
    observed_monotonic: float,
) -> dict[str, Any]:
    """Capture a scoped digest immediately before a resident spawn without creating a ref."""
    normalized = _liveness_paths(paths, repo_root=repo_root)
    observed = _finite_nonnegative(observed_monotonic, "observed_monotonic")
    return {
        "schema": LIVENESS_BASELINE_SCHEMA,
        "paths": list(normalized),
        "path_set_sha256": _path_set_digest(normalized),
        "baseline_digest": _scoped_worktree_digest(normalized, repo_root=repo_root),
        "observed_monotonic": observed,
    }


def _validated_baseline(value: object, *, repo_root: Path) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _LIVENESS_BASELINE_KEYS:
        raise ValueError("liveness baseline fields are not closed")
    if value["schema"] != LIVENESS_BASELINE_SCHEMA:
        raise ValueError("liveness baseline schema is unsupported")
    paths = _liveness_paths(value["paths"], repo_root=repo_root)
    if value["path_set_sha256"] != _path_set_digest(paths):
        raise ValueError("liveness baseline path-set digest does not match")
    if not _is_sha256_hex(value["baseline_digest"]):
        raise ValueError("liveness baseline digest is invalid")
    return {
        **value,
        "paths": list(paths),
        "observed_monotonic": _finite_nonnegative(
            value["observed_monotonic"], "baseline.observed_monotonic"
        ),
    }


def _validate_exclusive_provenance(
    value: object,
    *,
    repo_root: Path,
    baseline: dict[str, Any],
    current_digest: str,
    interval_end: float,
    subject_identity: object,
) -> tuple[str, tuple[str, ...]]:
    if not isinstance(value, dict) or set(value) != _PROVENANCE_KEYS:
        raise ValueError("exclusive provenance fields are not closed")
    if value["schema"] != EXCLUSIVE_PROVENANCE_SCHEMA:
        raise ValueError("exclusive provenance schema is unsupported")
    if not isinstance(value["subject_id"], str) or not _SUBJECT_ID.fullmatch(value["subject_id"]):
        raise ValueError("exclusive provenance subject_id is invalid")
    for field in ("resource_sha256", "token_sha256"):
        if not _is_sha256_hex(value[field]):
            raise ValueError(f"exclusive provenance {field} is invalid")
    if not isinstance(value["lease_id"], str) or not value["lease_id"]:
        raise ValueError("exclusive provenance lease_id is required")
    if not isinstance(value["broker_epoch"], str) or not value["broker_epoch"]:
        raise ValueError("exclusive provenance broker_epoch is required")
    if not isinstance(value["fencing_sequence"], int) or value["fencing_sequence"] < 1:
        raise ValueError("exclusive provenance fencing_sequence must be positive")
    if not isinstance(value["custody_ref"], str) or not value["custody_ref"]:
        raise ValueError("exclusive provenance custody_ref is required")
    paths = _liveness_paths(value["paths"], repo_root=repo_root)
    if list(paths) != baseline["paths"]:
        raise ValueError("exclusive provenance paths do not match the baseline")
    if value["path_set_sha256"] != baseline["path_set_sha256"]:
        raise ValueError("exclusive provenance path-set digest does not match")
    if value["baseline_digest"] != baseline["baseline_digest"]:
        raise ValueError("exclusive provenance baseline digest does not match")
    if value["current_digest"] != current_digest:
        raise ValueError("exclusive provenance current digest does not match")
    interval_start = _finite_nonnegative(value["interval_start"], "interval_start")
    proven_end = _finite_nonnegative(value["interval_end"], "interval_end")
    if interval_start != baseline["observed_monotonic"] or proven_end != interval_end:
        raise ValueError("exclusive provenance interval does not bind this observation")
    covered = value["covered_generation_ids"]
    if not isinstance(covered, list) or not covered or len(covered) != len(set(covered)):
        raise ValueError("exclusive provenance requires unique covered generation IDs")
    for generation in covered:
        if not isinstance(generation, str) or not _is_sha256_hex(generation):
            raise ValueError("exclusive provenance generation ID is invalid")
    if not isinstance(subject_identity, dict):
        raise ValueError("exclusive provenance requires the canonical liveness identity")
    for provenance_field, identity_field in (
        ("subject_id", "subject_id"),
        ("lease_id", "lease_id"),
        ("resource_sha256", "resource_sha256"),
        ("token_sha256", "token_sha256"),
        ("broker_epoch", "broker_epoch"),
        ("fencing_sequence", "fencing_sequence"),
    ):
        if value[provenance_field] != subject_identity.get(identity_field):
            raise ValueError(
                f"exclusive provenance {provenance_field} does not match the liveness subject"
            )
    if (
        subject_identity.get("baseline_sha256") != baseline["baseline_digest"]
        or subject_identity.get("path_set_sha256") != baseline["path_set_sha256"]
    ):
        raise ValueError("exclusive provenance baseline does not match the liveness subject")
    return value["custody_ref"], tuple(covered)


def observe_liveness_paths(
    baseline_value: object,
    *,
    repo_root: Path,
    observed_monotonic: float,
    exclusive_provenance: object | None = None,
    subject_identity: object | None = None,
) -> dict[str, Any]:
    """Compare the declared scope and distinguish activity from attributed progress."""
    baseline = _validated_baseline(baseline_value, repo_root=repo_root)
    interval_end = _finite_nonnegative(observed_monotonic, "observed_monotonic")
    if interval_end <= baseline["observed_monotonic"]:
        raise ValueError("liveness observation interval must increase")
    paths = tuple(baseline["paths"])
    current_digest = _scoped_worktree_digest(paths, repo_root=repo_root)
    common = {
        "schema": LIVENESS_OBSERVATION_SCHEMA,
        "paths": list(paths),
        "path_set_sha256": baseline["path_set_sha256"],
        "baseline_digest": baseline["baseline_digest"],
        "current_digest": current_digest,
        "interval_start": baseline["observed_monotonic"],
        "interval_end": interval_end,
    }
    if current_digest == baseline["baseline_digest"]:
        if exclusive_provenance is not None:
            raise ValueError("exclusive provenance cannot upgrade an unchanged scope")
        return {
            **common,
            "classification": "unchanged",
            "event": None,
            "payload": None,
            "provenance_ref": None,
            "covered_generation_ids": [],
        }
    if exclusive_provenance is None:
        return {
            **common,
            "classification": "scoped-activity-unattributed",
            "event": "scoped-activity-unattributed",
            "payload": {
                "baseline_digest": baseline["baseline_digest"],
                "current_digest": current_digest,
                "interval_start": baseline["observed_monotonic"],
                "interval_end": interval_end,
            },
            "provenance_ref": None,
            "covered_generation_ids": [],
        }
    custody_ref, covered = _validate_exclusive_provenance(
        exclusive_provenance,
        repo_root=repo_root,
        baseline=baseline,
        current_digest=current_digest,
        interval_end=interval_end,
        subject_identity=subject_identity,
    )
    return {
        **common,
        "classification": "artifact-progress",
        "event": "artifact-progress",
        "payload": {
            "baseline_digest": baseline["baseline_digest"],
            "current_digest": current_digest,
            "interval_start": baseline["observed_monotonic"],
            "interval_end": interval_end,
            "provenance_receipt": custody_ref,
            "covered_generation_ids": list(covered),
        },
        "provenance_ref": custody_ref,
        "covered_generation_ids": list(covered),
    }


def snapshot(run_id: str, epoch: str, *, repo_root: Path) -> ArtifactPointer:
    """Build a Layer-1 diff pointer via the KTD1 temp-index tree snapshot + holding ref.

    Captures staged + unstaged + untracked files into a tree OID without touching the real index or
    working tree. Pins it with ``refs/team-execution/snapshots/<run-id>/<epoch>`` (created WITH a
    reflog so gc can reclaim it by age even after ``git gc`` packs the loose ref away) and records the
    base tree (``HEAD^{tree}`` at snapshot time) as the pointer's first-class ``base`` field so the
    deref is fully pinned and cannot drift if HEAD moves mid-run.
    """
    _validate_ref_segment(run_id, label="run id")
    _validate_ref_segment(epoch, label="epoch")
    _require_dense_worktree(repo_root)
    base_tree = _git(["rev-parse", "HEAD^{tree}"], repo_root=repo_root).stdout.strip()
    fd, index_path = tempfile.mkstemp(prefix="te-artifact-index-")
    os.close(fd)
    # A seeded temp index yields a *different* on-disk file than the seed; remove the empty stub so
    # git initializes the index itself from HEAD, matching a normal working-tree read-tree.
    os.unlink(index_path)
    try:
        env = {"GIT_INDEX_FILE": index_path}
        _git(["read-tree", "HEAD"], repo_root=repo_root, env=env)
        _git(["add", "-A"], repo_root=repo_root, env=env)
        tree_oid = _git(["write-tree"], repo_root=repo_root, env=env).stdout.strip()
    finally:
        if os.path.exists(index_path):
            os.unlink(index_path)
    ref = f"{SNAPSHOT_REF_PREFIX}/{run_id}/{epoch}"
    # --create-reflog forces a reflog for this custom namespace (git does not log it by default). The
    # reflog file (``.git/logs/<ref>``) survives ``git gc`` — which packs the loose ref away — giving
    # gc a durable age signal (see ``_snapshot_ref_paths``).
    _git(["update-ref", "--create-reflog", ref, tree_oid], repo_root=repo_root)
    deref_cmd = f"git diff {base_tree} {tree_oid}"
    return ArtifactPointer(
        kind="diff", locator=ref, hash=tree_oid, epoch=str(epoch), deref=deref_cmd, base=base_tree
    )


# ---------------------------------------------------------------------------
# Layer 2 — content-addressed store for non-git artifacts (U3, KTD2/R8/R9/R10)
# ---------------------------------------------------------------------------


def _repo_display_name(repo_root: Path) -> str:
    """A stable, filesystem-safe segment for the home-fallback namespace (B0a precedent)."""
    return repo_root.name or "repo"


def _claude_dir_is_ignored(repo_root: Path) -> bool:
    """Whether ``.claude`` is git-ignored in the target repo (Step B0a's safety check).

    A directory-only gitignore pattern (``.claude/``) only matches once git can tell the path is a
    directory, which for a not-yet-created ``.claude/`` it cannot — so probe a path *under* it
    instead of the bare directory name (``git check-ignore .claude`` false-negatives on a fresh
    checkout even when ``.claude/`` is correctly ignored).
    """
    probe = ".claude/team-execution/artifacts/.probe"
    result = _git(["check-ignore", "-q", probe], repo_root=repo_root, check=False)
    return result.returncode == 0


def resolve_store_root(repo_root: Path) -> Path:
    """Resolve the Layer-2 CAS root, mirroring Step B0a: repo ``.claude/`` only when git-ignored
    there, else the home-directory fallback so run-state is never at risk of being committed."""
    if _claude_dir_is_ignored(repo_root):
        return repo_root / ".claude" / "team-execution" / "artifacts"
    return (
        Path.home()
        / ".claude"
        / "team-execution"
        / "state"
        / _repo_display_name(repo_root)
        / "artifacts"
    )


def _cas_path(store_root: Path, sha256_hex: str) -> Path:
    return store_root / CAS_SUBDIR / sha256_hex[:2] / sha256_hex


def _read_index(store_root: Path) -> dict[str, Any]:
    index_path = store_root / INDEX_FILENAME
    if not index_path.exists():
        return {}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_index(store_root: Path, index: dict[str, Any]) -> None:
    store_root.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(index, sort_keys=True, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=store_root, prefix=".index-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_name, store_root / INDEX_FILENAME)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def _record_epoch(store_root: Path, run_id: str, epoch: str, sha256_hex: str) -> None:
    """Record ``sha256_hex`` as the artifact for ``<run-id>/<epoch>`` (KTD2 freshness sidecar)."""
    index = _read_index(store_root)
    run_entry = index.setdefault(run_id, {"latest_epoch": None, "epochs": {}})
    run_entry["epochs"][str(epoch)] = sha256_hex
    try:
        epoch_num = int(epoch)
    except ValueError:
        epoch_num = (
            None  # non-numeric epoch: freshness not enforced, mirrors L1's opaque-epoch path
        )
    if epoch_num is not None:
        current_latest = run_entry.get("latest_epoch")
        if current_latest is None or epoch_num > int(current_latest):
            run_entry["latest_epoch"] = epoch_num
    _write_index(store_root, index)


def store(run_id: str, epoch: str, file_path: Path, *, repo_root: Path) -> ArtifactPointer:
    """Write-once content-addressed store of ``file_path`` (KTD2). Same bytes → same CAS path, no
    duplicate write; different bytes → different path (sha256 dedup). Records the epoch freshness
    sidecar and returns a Layer-2 ``file`` pointer with a self-describing deref command."""
    content = file_path.read_bytes()
    sha256_hex = hashlib.sha256(content).hexdigest()
    store_root = resolve_store_root(repo_root)
    cas_path = _cas_path(store_root, sha256_hex)
    cas_path.parent.mkdir(parents=True, exist_ok=True)
    if not cas_path.exists():
        fd, tmp_name = tempfile.mkstemp(dir=cas_path.parent, prefix=".artifact-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(content)
            os.replace(tmp_name, cas_path)  # atomic create; content-addressed so no clobber risk
        except Exception:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise
    _record_epoch(store_root, run_id, epoch, sha256_hex)
    locator = f"{CAS_SUBDIR}/{sha256_hex[:2]}/{sha256_hex}"
    return ArtifactPointer(
        kind="file",
        locator=locator,
        hash=sha256_hex,
        epoch=f"{run_id}/{epoch}",
        deref=f"{Path(__file__).name} deref '<pointer-json>'",
    )


def _verify_l2_integrity(pointer: ArtifactPointer, *, repo_root: Path) -> Path:
    """L2 integrity: the CAS file exists AND its sha256 matches the pointer's hash.

    The stored path is rebuilt from the *validated* hash, never joined from the free-form
    ``locator``. A pointer is untrusted input — it travels inside spawn prompts — so a
    ``locator`` of ``/etc/passwd`` or ``../../secret`` would otherwise escape the store and read
    an arbitrary file, and the mismatch error would leak that file's sha256 (a hash oracle).
    Confining the address to ``<store>/objects/<hash[:2]>/<hash>`` built from a 64-hex-char digest
    removes both: the only file addressable is one whose name already equals its own hash.
    """
    if not _is_sha256_hex(pointer.hash):
        raise PointerError(ERR_HASH_MISMATCH, "pointer hash is not a sha256 digest")
    expected_locator = f"{CAS_SUBDIR}/{pointer.hash[:2]}/{pointer.hash}"
    if pointer.locator != expected_locator:
        raise PointerError(ERR_HASH_MISMATCH, "pointer locator does not match its content hash")
    store_root = resolve_store_root(repo_root)
    cas_path = _cas_path(store_root, pointer.hash)
    # A CAS entry is a plain file whose name equals its own hash; a symlink there could redirect the
    # read/re-hash to an arbitrary target (needs a local store write — out of the pointer threat
    # model, but cheap to deny). Reject it, and use ONE message for every miss so nothing
    # distinguishes "absent" from "present-but-wrong" (closes a low-value store-membership oracle).
    if cas_path.is_symlink() or not cas_path.is_file():
        raise PointerError(ERR_HASH_MISMATCH, "stored artifact does not match pointer hash")
    actual = hashlib.sha256(cas_path.read_bytes()).hexdigest()
    if actual != pointer.hash:
        raise PointerError(ERR_HASH_MISMATCH, "stored artifact does not match pointer hash")
    return cas_path


def _verify_l2_freshness(pointer: ArtifactPointer, *, repo_root: Path) -> None:
    """L2 freshness: no newer epoch exists for the same run-id (monotonic supersession, KTD2)."""
    run_id, _, epoch_str = pointer.epoch.partition("/")
    try:
        my_epoch = int(epoch_str)
    except ValueError:
        return  # non-numeric epoch: freshness is not enforced (contract carries it as opaque)
    store_root = resolve_store_root(repo_root)
    run_entry = _read_index(store_root).get(run_id)
    if not run_entry:
        return
    latest = run_entry.get("latest_epoch")
    if latest is not None and int(latest) > my_epoch:
        raise PointerError(
            ERR_STALE,
            f"epoch {latest} supersedes pointer epoch {my_epoch} for run {run_id}",
        )


def deref_file(pointer: ArtifactPointer, *, repo_root: Path) -> str:
    """Verify (integrity + freshness) then return a Layer-2 stored artifact's content.

    Raises ``PointerError`` with a typed code on a verification failure (never returns wrong/stale
    bytes, R2), mirroring the Layer-1 ``deref`` contract exactly.
    """
    cas_path = _verify_l2_integrity(pointer, repo_root=repo_root)
    _verify_l2_freshness(pointer, repo_root=repo_root)
    return cas_path.read_bytes().decode("utf-8", errors="replace")


def _snapshot_ref_paths(repo_root: Path) -> dict[str, Path]:
    """Map every Layer-1 snapshot ref name to its reflog file (``.git/logs/<refname>``), for age gc.

    ``git gc`` packs refs under ANY namespace into ``packed-refs`` and deletes the loose ref file
    (verified empirically), so the loose-ref path is NOT a durable age signal. The reflog file
    (created via ``update-ref --create-reflog`` in ``snapshot``) survives packing; its *file mtime*
    does not (gc's internal ``reflog expire`` rewrites the file and resets it), so gc dates a ref by
    the reflog ENTRY timestamp instead — see ``_reflog_creation_time``. Refs enumerate via
    ``for-each-ref`` (which sees packed refs); one with no reflog is skipped — degrade-not-break.
    """
    common_dir_raw = _git(["rev-parse", "--git-common-dir"], repo_root=repo_root).stdout.strip()
    common_dir = Path(common_dir_raw)
    if not common_dir.is_absolute():
        common_dir = (repo_root / common_dir).resolve()
    listing = _git(
        ["for-each-ref", "--format=%(refname)", f"{SNAPSHOT_REF_PREFIX}/"],
        repo_root=repo_root,
        check=False,
    )
    paths: dict[str, Path] = {}
    for refname in listing.stdout.splitlines():
        reflog_path = common_dir / "logs" / refname
        if reflog_path.exists():
            paths[refname] = reflog_path
    return paths


def _reflog_creation_time(reflog_path: Path) -> float | None:
    """Return the unix timestamp of a reflog's first (creation) entry, or ``None`` if unreadable.

    This is the durable age signal. ``git gc`` runs ``git reflog expire`` internally, which rewrites
    the reflog file and resets its FILE mtime to now (even when it expires zero entries) — so the file
    mtime is unusable for age. The per-entry commit timestamp embedded in the reflog line IS preserved
    by ``reflog expire``. Line format: ``<old> <new> <name> <email> <ts> <tz>\\t<msg>`` — the timestamp
    is the second-to-last space-separated token before the tab (robust to spaces in the committer name).
    """
    try:
        first_line = reflog_path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return None
    parts = first_line.split("\t", 1)[0].split()
    if len(parts) < 2:
        return None
    try:
        return float(parts[-2])
    except ValueError:
        return None


def _gc_snapshot_refs(repo_root: Path, cutoff: float) -> int:
    """Prune Layer-1 snapshot refs whose reflog creation entry predates ``cutoff``.

    Age comes from the reflog ENTRY timestamp (``_reflog_creation_time``), which survives both
    ``git gc``'s ref-packing and its internal ``reflog expire`` — unlike the reflog file mtime, which
    gc resets. A ref whose reflog is unreadable is left alone (degrade-not-break)."""
    removed = 0
    for refname, reflog_path in _snapshot_ref_paths(repo_root).items():
        created = _reflog_creation_time(reflog_path)
        if created is not None and created < cutoff:
            _git(["update-ref", "-d", refname], repo_root=repo_root, check=False)
            removed += 1
    return removed


def _prune_index(store_root: Path, stale_hashes: set[str]) -> None:
    index = _read_index(store_root)
    changed = False
    for run_id in list(index):
        entry = index[run_id]
        epochs = entry.get("epochs", {})
        kept = {k: v for k, v in epochs.items() if v not in stale_hashes}
        if len(kept) != len(epochs):
            changed = True
        if not kept:
            del index[run_id]
            continue
        entry["epochs"] = kept
        remaining_nums = [int(k) for k in kept if k.lstrip("-").isdigit()]
        entry["latest_epoch"] = max(remaining_nums) if remaining_nums else None
    if changed:
        _write_index(store_root, index)


def _gc_store(repo_root: Path, cutoff: float) -> int:
    """Reclaim Layer-2 CAS entries older than ``cutoff``; prune their freshness-index entries."""
    store_root = resolve_store_root(repo_root)
    objects_dir = store_root / CAS_SUBDIR
    if not objects_dir.exists():
        return 0
    removed = 0
    stale_hashes: set[str] = set()
    for shard in objects_dir.iterdir():
        if not shard.is_dir():
            continue
        for entry in shard.iterdir():
            if entry.stat().st_mtime < cutoff:
                stale_hashes.add(entry.name)
                entry.unlink()
                removed += 1
        with contextlib.suppress(OSError):
            shard.rmdir()  # only succeeds if the shard is now empty
    if stale_hashes:
        _prune_index(store_root, stale_hashes)
    return removed


def gc(
    *,
    repo_root: Path,
    max_age_days: float = DEFAULT_GC_MAX_AGE_DAYS,
    now: Callable[[], float] = time.time,
) -> dict[str, int]:
    """Reclaim Layer-2 CAS entries AND Layer-1 snapshot refs older than ``max_age_days`` (R9's
    bounded-store requirement). Entries younger than the TTL are left untouched."""
    cutoff = now() - max_age_days * 86400
    return {
        "artifacts_removed": _gc_store(repo_root, cutoff),
        "snapshot_refs_removed": _gc_snapshot_refs(repo_root, cutoff),
    }


def _verify_integrity(pointer: ArtifactPointer, *, repo_root: Path) -> None:
    """L1 integrity: the tree OID resolves as a tree AND the holding ref still points at it."""
    # Defense-in-depth: gate the untrusted hash to an OID shape before it reaches git plumbing, so a
    # leading-`-` value can never be interpreted as an option token (the plumbing here is read-only,
    # so this hardens rather than fixes).
    if not _is_git_oid(pointer.hash):
        raise PointerError(ERR_HASH_MISMATCH, "pointer hash is not a git object id")
    kind = _git(["cat-file", "-t", pointer.hash], repo_root=repo_root, check=False)
    if kind.returncode != 0 or kind.stdout.strip() != "tree":
        raise PointerError(ERR_HASH_MISMATCH, f"tree {pointer.hash} not resolvable")
    ref_oid = _git(
        ["rev-parse", "--verify", "--quiet", pointer.locator], repo_root=repo_root, check=False
    )
    if ref_oid.returncode != 0 or ref_oid.stdout.strip() != pointer.hash:
        raise PointerError(
            ERR_HASH_MISMATCH,
            f"ref {pointer.locator} does not point at {pointer.hash}",
        )


def _verify_freshness(pointer: ArtifactPointer, *, repo_root: Path) -> None:
    """L1 freshness: no newer epoch ref exists for the same run-id (monotonic supersession)."""
    try:
        my_epoch = int(pointer.epoch)
    except ValueError:
        return  # non-numeric epoch: freshness is not enforced (contract carries it as opaque)
    run_prefix = pointer.locator.rsplit("/", 1)[0]  # refs/team-execution/snapshots/<run-id>
    listing = _git(
        ["for-each-ref", "--format=%(refname)", f"{run_prefix}/"],
        repo_root=repo_root,
        check=False,
    )
    for refname in listing.stdout.splitlines():
        segment = refname.rsplit("/", 1)[-1]
        try:
            other_epoch = int(segment)
        except ValueError:
            continue
        if other_epoch > my_epoch:
            raise PointerError(
                ERR_STALE,
                f"epoch {other_epoch} supersedes pointer epoch {my_epoch} for {run_prefix}",
            )


def _diff_argv(base: str, snapshot: str) -> list[str]:
    """Build the Layer-1 deref argv deterministically from validated tree OIDs (never parse ``deref``).

    A pointer is untrusted input (it travels inside spawn prompts), so the free-form ``deref`` string
    is NEVER parsed into argv: a tampered ``deref`` like ``git diff --output=/path <base> <snapshot>``
    would otherwise smuggle an arbitrary-file-write option onto the git command. Rebuilding argv from
    the pointer's ``base`` + ``snapshot`` OIDs — each constrained to a hex object id, so no option
    token is representable — removes that surface entirely (the L1 analogue of the L2 hash-derived-path
    confinement).
    """
    for oid, label in ((base, "base"), (snapshot, "snapshot")):
        if not _is_git_oid(oid):
            raise PointerError(ERR_HASH_MISMATCH, f"{label} tree is not a git object id")
    return ["diff", base, snapshot]


def deref(pointer: ArtifactPointer, *, repo_root: Path) -> str:
    """Verify (integrity + freshness) then dereference a pointer, returning the full artifact.

    Raises ``PointerError`` with a typed code on a verification failure (never returns wrong/stale
    bytes, R2). Dispatches by ``kind``: ``file`` uses the Layer-2 CAS (U3); ``diff`` uses the Layer-1
    git-object path, rebuilding the diff argv deterministically from the validated base + snapshot
    OIDs (R5). ``symbol`` pointers are NOT dereferenced here — they are resolved with grep/read.
    """
    if pointer.kind == "file":
        return deref_file(pointer, repo_root=repo_root)
    if pointer.kind == "symbol":
        raise ValueError(
            "symbol pointers are resolved with grep/read, not the deref CLI "
            "(only diff and file kinds are dereferenceable)"
        )
    _verify_integrity(pointer, repo_root=repo_root)
    _verify_freshness(pointer, repo_root=repo_root)
    argv = _diff_argv(pointer.base, pointer.hash)
    return _git(argv, repo_root=repo_root).stdout


def _cmd_snapshot(args: argparse.Namespace) -> int:
    root = resolve_repo_root(args.repo_root)
    pointer = snapshot(args.run, args.epoch, repo_root=root)
    print(pointer.to_json())
    return 0


def _cmd_deref(args: argparse.Namespace) -> int:
    root = resolve_repo_root(args.repo_root)
    pointer = ArtifactPointer.from_json(args.pointer)
    sys.stdout.write(deref(pointer, repo_root=root))
    return 0


def _cmd_store(args: argparse.Namespace) -> int:
    root = resolve_repo_root(args.repo_root)
    pointer = store(args.run, args.epoch, Path(args.file), repo_root=root)
    print(pointer.to_json())
    return 0


def _cmd_gc(args: argparse.Namespace) -> int:
    root = resolve_repo_root(args.repo_root)
    result = gc(repo_root=root, max_age_days=args.max_age_days)
    print(json.dumps(result, sort_keys=True))
    return 0


def _json_object(raw: str, field: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _cmd_liveness_baseline(args: argparse.Namespace) -> int:
    root = resolve_repo_root(args.repo_root)
    baseline = capture_liveness_baseline(
        args.path,
        repo_root=root,
        observed_monotonic=args.observed_monotonic,
    )
    print(json.dumps(baseline, sort_keys=True, separators=(",", ":")))
    return 0


def _cmd_liveness_observe(args: argparse.Namespace) -> int:
    root = resolve_repo_root(args.repo_root)
    provenance = (
        None
        if args.exclusive_provenance_json is None
        else _json_object(args.exclusive_provenance_json, "exclusive-provenance-json")
    )
    result = observe_liveness_paths(
        _json_object(args.baseline_json, "baseline-json"),
        repo_root=root,
        observed_monotonic=args.observed_monotonic,
        exclusive_provenance=provenance,
        subject_identity=(
            None
            if args.subject_identity_json is None
            else _json_object(args.subject_identity_json, "subject-identity-json")
        ),
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Typed artifact pointers for team-execution (L1).")
    parser.add_argument(
        "--repo-root", default=None, help="repo root (default: git toplevel of cwd)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="build a Layer-1 diff pointer (tree OID + holding ref)")
    snap.add_argument("--run", required=True, help="run id (holding-ref namespace segment)")
    snap.add_argument("--epoch", required=True, help="freshness epoch (consensus iteration)")
    snap.set_defaults(func=_cmd_snapshot)

    dr = sub.add_parser("deref", help="verify + dereference a pointer JSON to its full artifact")
    dr.add_argument("pointer", help="the pointer JSON object")
    dr.set_defaults(func=_cmd_deref)

    st = sub.add_parser("store", help="write-once content-addressed store of FILE (Layer 2)")
    st.add_argument("--run", required=True, help="run id (freshness sidecar namespace segment)")
    st.add_argument("--epoch", required=True, help="freshness epoch (consensus iteration)")
    st.add_argument("file", help="path to the artifact to store")
    st.set_defaults(func=_cmd_store)

    gcp = sub.add_parser("gc", help="reclaim Layer-2 store entries and Layer-1 snapshot refs")
    gcp.add_argument(
        "--max-age-days",
        type=float,
        default=DEFAULT_GC_MAX_AGE_DAYS,
        help=f"reclaim entries older than this (default {DEFAULT_GC_MAX_AGE_DAYS})",
    )
    gcp.set_defaults(func=_cmd_gc)

    baseline = sub.add_parser(
        "liveness-baseline",
        help="capture a declared-path digest immediately before a resident spawn",
    )
    baseline.add_argument("--path", action="append", required=True, help="repo-relative path")
    baseline.add_argument("--observed-monotonic", type=float, required=True)
    baseline.set_defaults(func=_cmd_liveness_baseline)

    observe = sub.add_parser(
        "liveness-observe",
        help="compare a liveness baseline without creating a durable pointer",
    )
    observe.add_argument("--baseline-json", required=True)
    observe.add_argument("--observed-monotonic", type=float, required=True)
    observe.add_argument("--exclusive-provenance-json")
    observe.add_argument("--subject-identity-json")
    observe.set_defaults(func=_cmd_liveness_observe)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except PointerError as exc:
        print(exc.code, file=sys.stderr)
        if exc.detail:
            print(exc.detail, file=sys.stderr)
        return 1
    except (GitError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
