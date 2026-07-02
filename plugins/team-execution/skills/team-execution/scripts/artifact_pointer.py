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

House pattern (precedent ``plugins/saga/scripts/outcome_github.py``): ``subprocess.run`` is resolved
at call time (never bound as a default arg) so a test could monkeypatch it; git is invoked with a
fixed argv and no shell. Python 3.12, stdlib only, no I/O at import.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess  # nosec B404 — git only, fixed argv, no shell
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

SNAPSHOT_REF_PREFIX = "refs/team-execution/snapshots"
POINTER_KINDS = ("diff", "file", "symbol")

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
    bytes, R2). On success runs the pinned deref command and returns its stdout (the full diff, R5).
    """
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
