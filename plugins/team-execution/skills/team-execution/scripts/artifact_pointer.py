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
import os
import shlex
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
    """One typed artifact reference (R1): kind, locator, integrity hash, freshness epoch, deref."""

    kind: str
    locator: str
    hash: str
    epoch: str
    deref: str

    def to_json(self) -> str:
        """Serialize to a single-line JSON object (KTD3: one fenced ``artifact-pointer`` block)."""
        return json.dumps(
            {
                "kind": self.kind,
                "locator": self.locator,
                "hash": self.hash,
                "epoch": self.epoch,
                "deref": self.deref,
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


def snapshot(run_id: str, epoch: str, *, repo_root: Path) -> ArtifactPointer:
    """Build a Layer-1 diff pointer via the KTD1 temp-index tree snapshot + holding ref.

    Captures staged + unstaged + untracked files into a tree OID without touching the real index or
    working tree. Pins it with ``refs/team-execution/snapshots/<run-id>/<epoch>`` and records the base
    tree (``HEAD^{tree}`` at snapshot time) inside the fully-pinned deref command so it cannot drift if
    HEAD moves mid-run.
    """
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
    _git(["update-ref", ref, tree_oid], repo_root=repo_root)
    deref_cmd = f"git diff {base_tree} {tree_oid}"
    return ArtifactPointer(
        kind="diff", locator=ref, hash=tree_oid, epoch=str(epoch), deref=deref_cmd
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
    """L2 integrity: the CAS file exists AND its sha256 matches the pointer's hash."""
    store_root = resolve_store_root(repo_root)
    cas_path = store_root / pointer.locator
    if not cas_path.exists():
        raise PointerError(ERR_HASH_MISMATCH, f"stored artifact not found at {pointer.locator}")
    actual = hashlib.sha256(cas_path.read_bytes()).hexdigest()
    if actual != pointer.hash:
        raise PointerError(
            ERR_HASH_MISMATCH, f"stored artifact hash {actual} does not match pointer hash"
        )
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
    """Map every Layer-1 snapshot ref name to its on-disk loose-ref path (for age-based gc).

    Packed refs (no loose file) are skipped — best-effort, matching the store's degrade-not-break
    posture; ``git gc`` does not pack refs under a custom namespace by default.
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
        ref_path = common_dir / refname
        if ref_path.exists():
            paths[refname] = ref_path
    return paths


def _gc_snapshot_refs(repo_root: Path, cutoff: float) -> int:
    """Prune Layer-1 snapshot refs older than ``cutoff`` (mtime of the loose-ref file)."""
    removed = 0
    for refname, ref_path in _snapshot_ref_paths(repo_root).items():
        if ref_path.stat().st_mtime < cutoff:
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


def _deref_argv(command: str, *, expected_snapshot: str) -> list[str]:
    """Parse and validate the pointer's deref command into a fixed git argv (no shell exec).

    The command is generated by this module (``git diff [--stat] <base> <snapshot>``); we still parse
    and bind it to the pointer's own hash rather than exec a raw string, so a tampered command cannot
    smuggle in a different invocation.
    """
    tokens = shlex.split(command)
    if len(tokens) < 4 or tokens[0] != "git" or tokens[1] != "diff":
        raise PointerError(ERR_HASH_MISMATCH, f"malformed deref command: {command!r}")
    if tokens[-1] != expected_snapshot:
        raise PointerError(
            ERR_HASH_MISMATCH, "deref command snapshot tree does not match pointer hash"
        )
    return tokens[1:]


def deref(pointer: ArtifactPointer, *, repo_root: Path) -> str:
    """Verify (integrity + freshness) then dereference a pointer, returning the full artifact.

    Raises ``PointerError`` with a typed code on a verification failure (never returns wrong/stale
    bytes, R2). Dispatches by ``kind``: ``file`` uses the Layer-2 CAS (U3); everything else uses the
    Layer-1 git-object path, running the pinned deref command and returning its stdout (R5).
    """
    if pointer.kind == "file":
        return deref_file(pointer, repo_root=repo_root)
    _verify_integrity(pointer, repo_root=repo_root)
    _verify_freshness(pointer, repo_root=repo_root)
    argv = _deref_argv(pointer.deref, expected_snapshot=pointer.hash)
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
