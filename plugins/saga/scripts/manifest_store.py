#!/usr/bin/env python3
"""Manifest store: the git-common-dir carrier for provenance manifests (U2/KTD1/R19).

One JSON file per delegated invocation at
``<git-common-dir>/saga-manifests/<saga-id>/<execution-id>.json``, resolved through the same
``resolve_common_dir()`` ``outcome_store.py`` uses for the outcome cache — the only candidate
that satisfies R19 for delegations that never emit a ``CompletionEvent`` (agy runs during plain
``/work``, team-execution outside an outcome). Rejected carriers (KTD1): ``CompletionEvent.payload``
alone (outcome leaves only), a saga tick pointer (per-checkout, git-ignored, worktree-local).

This module also owns the typed ``manifest_ref`` pointer helper for the outcome-leaf case: a
manifest written here can be referenced from a ``CompletionEvent.payload["manifest_ref"]`` as a
common-dir-relative path, giving R19-breadth *and* a documented reader contract on the previously
open ``payload`` dict.

House pattern (mirrors ``outcome_store.py``): pure-ish functions over an explicit ``Store`` value,
dependency-injected ``runner`` so this is unit-testable offline with no real git repo. No I/O at
import.

CLI::

    python3 manifest_store.py write --repo-root <path> --saga-id <id> --execution-id <id> --file <manifest.json>
    python3 manifest_store.py read --repo-root <path> --saga-id <id> --execution-id <id>
    python3 manifest_store.py list --repo-root <path> --saga-id <id> [--json]

``record-completeness`` (persisting the ``output_completeness`` subrecord for spec-driven runs) is
added in U4 — out of scope here.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome_store  # noqa: E402  (after the sys.path shim, by design)

# Subdirectory under the git common dir that holds every saga's manifest tree. Namespaced
# separately from ``outcome_store.STORE_NAMESPACE`` — manifests exist independent of the
# OutcomeOrchestrator (R19 breadth: plain /work delegations never touch outcome-spec).
MANIFEST_NAMESPACE = "saga-manifests"

# The documented payload key a CompletionEvent uses to point at a manifest (closes the issue's
# "not yet a consumer surface" note on outcome_store.py's open payload dict).
MANIFEST_REF_KEY = "manifest_ref"


class ManifestStoreError(ValueError):
    """A manifest-store operation was rejected (bad id, missing file, malformed JSON)."""


def _safe_name(name: str, *, what: str = "id") -> str:
    """Reject a name that would escape the store directory (path traversal / separators).

    Parity with ``outcome_store._safe_name`` (V9/KTD1's shared carrier convention) —
    duplicated rather than imported since it is a private helper of a sibling module.
    """
    if not name:
        raise ManifestStoreError(f"{what} must be non-empty")
    if "/" in name or "\\" in name or name in (".", "..") or "\x00" in name:
        raise ManifestStoreError(
            f"{what} {name!r} must not contain a path separator or be '.'/'..'"
        )
    return name


@dataclass(frozen=True)
class Store:
    """A handle to one saga's manifest directory under the git common dir.

    ``root`` is the per-saga directory (``<common-dir>/saga-manifests/<saga-id>``). A store is
    constructed either by resolving the common dir (``Store.for_saga``) or with a direct path
    (tests, or any caller that already knows the location).
    """

    root: Path

    @classmethod
    def for_saga(
        cls,
        saga_id: str,
        repo_root: Path,
        *,
        runner: Any = None,
    ) -> Store:
        common = outcome_store.resolve_common_dir(repo_root, runner=runner)
        return cls(root=common / MANIFEST_NAMESPACE / _safe_name(saga_id, what="saga_id"))

    def ensure(self) -> Store:
        """Create the directory tree (idempotent). Returns self for chaining."""
        self.root.mkdir(parents=True, exist_ok=True)
        return self

    def manifest_path(self, execution_id: str) -> Path:
        safe = _safe_name(execution_id, what="execution_id")
        return self.root / f"{safe}.json"


# ---------------------------------------------------------------------------
# Write / read / list
# ---------------------------------------------------------------------------


def write_manifest(store: Store, execution_id: str, manifest: dict[str, Any]) -> Path:
    """Write ``manifest`` (a plain dict — already-validated ``to_dict()`` output) atomically.

    Overwrites any prior manifest for the same execution id (a manifest may be updated in place,
    e.g. an adjudication written after the claimed-layer manifest, D5/U3) — never write-once.
    """
    path = store.manifest_path(execution_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    outcome_store._atomic_write(path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return path


def read_manifest(store: Store, execution_id: str) -> dict[str, Any] | None:
    """Read a manifest by execution id. Returns None if absent or malformed (never fatal)."""
    path = store.manifest_path(execution_id)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def list_manifests(store: Store) -> list[str]:
    """List execution ids with a manifest under ``store.root`` (empty list if the dir is absent)."""
    if not store.root.is_dir():
        return []
    return sorted(p.stem for p in store.root.glob("*.json"))


# ---------------------------------------------------------------------------
# CompletionEvent.payload["manifest_ref"] pointer helper (outcome-leaf case)
# ---------------------------------------------------------------------------


def manifest_ref(saga_id: str, execution_id: str) -> str:
    """The typed ``manifest_ref`` pointer value: a common-dir-relative path.

    Relative to the git common dir (not absolute) so the pointer stays valid across machines/
    clones — a reader resolves it against its own ``resolve_common_dir()`` call, exactly the way
    the manifest tree itself is resolved.
    """
    safe_saga = _safe_name(saga_id, what="saga_id")
    safe_execution = _safe_name(execution_id, what="execution_id")
    return f"{MANIFEST_NAMESPACE}/{safe_saga}/{safe_execution}.json"


def set_manifest_ref(payload: dict[str, Any], saga_id: str, execution_id: str) -> dict[str, Any]:
    """Return a copy of ``payload`` with ``manifest_ref`` set (does not mutate the input)."""
    updated = dict(payload)
    updated[MANIFEST_REF_KEY] = manifest_ref(saga_id, execution_id)
    return updated


def resolve_manifest_ref(
    payload: dict[str, Any],
    repo_root: Path,
    *,
    runner: Any = None,
) -> dict[str, Any] | None:
    """Resolve a ``CompletionEvent.payload["manifest_ref"]`` pointer back to its manifest dict.

    Returns None when the payload carries no pointer, the pointer is malformed, or the target
    file is absent/unreadable — the pointer is advisory (R8), never a hard dependency.
    """
    ref = payload.get(MANIFEST_REF_KEY)
    if not isinstance(ref, str) or not ref.strip():
        return None
    common = outcome_store.resolve_common_dir(repo_root, runner=runner)
    path = (common / ref).resolve()
    # Refuse to read outside the manifest tree even if a stray pointer tries to escape it.
    root = (common / MANIFEST_NAMESPACE).resolve()
    if root not in path.parents and path != root:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manifest store: write/read/list carrier CLI.")
    parser.add_argument("--repo-root", default=".", help="Repo root (any worktree; default cwd).")
    parser.add_argument("--saga-id", required=True, help="Saga id the manifest belongs to.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_write = sub.add_parser("write", help="Write a manifest from a JSON file.")
    p_write.add_argument("--execution-id", required=True)
    p_write.add_argument("--file", required=True, help="Path to a JSON manifest dict.")

    p_read = sub.add_parser("read", help="Read a manifest and print it as JSON.")
    p_read.add_argument("--execution-id", required=True)

    sub.add_parser("list", help="List execution ids with a manifest for this saga.")

    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root)
    store = Store.for_saga(args.saga_id, repo_root).ensure()

    if args.command == "write":
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            print("manifest file must contain a JSON object", file=sys.stderr)
            return 1
        path = write_manifest(store, args.execution_id, data)
        print(str(path))
        return 0

    if args.command == "read":
        manifest = read_manifest(store, args.execution_id)
        if manifest is None:
            print(f"no manifest for execution_id={args.execution_id!r}", file=sys.stderr)
            return 1
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "list":
        for execution_id in list_manifests(store):
            print(execution_id)
        return 0

    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
