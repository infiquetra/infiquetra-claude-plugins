#!/usr/bin/env python3
"""Golden-fixture drift check for fake-adapter test data (#458, T11-F1-6).

A fake is only trustworthy if its fixture data still matches what the **real producer** actually
emits. The hazard (``docs/engineering-journal/LEARNINGS.md`` ``{#fake-adapter-hides-real-path-mismatch}``):
``FakeWT``'s hand-crafted ``git worktree list --porcelain`` fixture was shaped to already match the
queried path, so every test passed while the real adapter (realpath-canonicalized) diverged.

This checker pins each fake's fixture data to a **golden artifact derived from the real producer**
and flags **drift** — a golden that was deleted or mutated away from its pinned SHA256. The manifest
(``tests/fixtures/golden/manifest.json``) records, per golden: the fake that consumes it, the real
producer that generates it, the file path, and its pinned hash.

Modes:

* ``--check`` (default) — recompute each golden's SHA256, flag a missing (deleted) or mismatched
  (mutated) golden. Strict exit non-zero on drift unless ``--advisory`` (report, exit 0). CI runs it
  advisory per the facet's advisory rollout.
* ``--regenerate`` — re-derive each golden from its real producer and rewrite the manifest hash. Run
  this deliberately when the real producer's output legitimately changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess  # nosec B404 — git CLI only, fixed argv, no shell
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "tests" / "fixtures" / "golden" / "manifest.json"

_SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")


@dataclass
class Drift:
    """One flagged golden — deleted or mutated away from its pinned hash."""

    path: str
    kind: str  # "deleted" | "mutated"
    detail: str


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Real producer: a normalized `git worktree list --porcelain` capture
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(  # nosec B603 B607 — fixed argv, no shell
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    )
    return result.stdout


def capture_worktree_porcelain() -> str:
    """Derive a deterministic golden from the REAL ``git worktree list --porcelain`` producer.

    Builds a throwaway 2-worktree git repo, runs the real porcelain command, then normalizes the two
    machine-specific values (the temp root path -> ``<ROOT>``, commit SHAs -> ``<SHA>``) so the
    golden is byte-stable across machines/CI while still being real producer output — the exact
    field grammar (``worktree``/``HEAD``/``branch`` lines, blank-line record separator) a fake must
    honour.
    """
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        repo = root / "repo"
        repo.mkdir()
        env_args = ["-c", "init.defaultBranch=main", "-c", "user.email=t@t", "-c", "user.name=t"]
        _git([*env_args, "init"], repo)
        (repo / "f.txt").write_text("x\n", encoding="utf-8")
        _git([*env_args, "add", "."], repo)
        _git([*env_args, "commit", "-m", "init"], repo)
        _git([*env_args, "worktree", "add", "-b", "feature", str(root / "wt-feature")], repo)
        raw = _git([*env_args, "worktree", "list", "--porcelain"], repo)
    # Normalize the two volatile axes so the golden is reproducible.
    real_root = os.path.realpath(td)
    normalized = raw.replace(real_root, "<ROOT>").replace(td, "<ROOT>")
    normalized = _SHA_RE.sub("<SHA>", normalized)
    return normalized


_PRODUCERS = {
    "git worktree list --porcelain": capture_worktree_porcelain,
}


# ---------------------------------------------------------------------------
# Fake consumers: behavioral pairing (#588)
# ---------------------------------------------------------------------------


def consume_worktree_porcelain(golden_content: str) -> None:
    """Consume git worktree porcelain golden fixture data into FakeWT (#588)."""
    tests_dir = REPO_ROOT / "tests"
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))
    import fakes_registry

    fake = fakes_registry.FakeWT(seed_porcelain=golden_content, root="/test_root")
    ops = fake.ops()
    paths = ops.list_paths()
    expected_repo = "/test_root/repo"
    expected_feature = "/test_root/wt-feature"
    if expected_repo not in paths or expected_feature not in paths:
        raise ValueError(f"FakeWT failed to parse expected worktree paths from golden, got {paths}")
    if not ops.exists(expected_repo) or not ops.exists(expected_feature):
        raise ValueError("FakeWT ops.exists failed for golden paths")
    if ops.exists("/test_root/absent_path"):
        raise ValueError("FakeWT ops.exists returned True for non-existent path")


_CONSUMERS: dict[str, Callable[[str], None]] = {
    "worktree-liveness-oracle": consume_worktree_porcelain,
}


# ---------------------------------------------------------------------------
# Manifest load / check / regenerate
# ---------------------------------------------------------------------------


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    return data


def check_goldens(manifest_path: Path) -> list[Drift]:
    """Return every drifted golden (deleted, mutated, unpaired, or consumer failure)."""
    manifest = load_manifest(manifest_path)
    drifts: list[Drift] = []
    for entry in manifest.get("goldens", []):
        rel = entry["path"]
        # ``path`` is repo-relative; resolve it against the repo root.
        golden = _resolve_golden(rel)
        if not golden.exists():
            drifts.append(Drift(rel, "deleted", "golden artifact is missing"))
            continue
        actual = sha256_of(golden)
        if actual != entry["sha256"]:
            drifts.append(Drift(rel, "mutated", f"sha256 {actual} != pinned {entry['sha256']}"))
            continue

        # Behavioral pairing check (#588)
        fake_id = entry.get("fake", "")
        base_id = fake_id.split()[0] if fake_id else ""
        consumer = _CONSUMERS.get(fake_id) or _CONSUMERS.get(base_id)
        if not consumer:
            drifts.append(
                Drift(rel, "unpaired", f"no registered consumer consumes fake {fake_id!r}")
            )
            continue
        try:
            content = golden.read_text(encoding="utf-8")
            consumer(content)
        except Exception as exc:
            drifts.append(
                Drift(rel, "consumer_failure", f"registered fake failed to consume golden: {exc}")
            )
    return drifts


def _resolve_golden(rel: str) -> Path:
    return Path(rel) if Path(rel).is_absolute() else (REPO_ROOT / rel)


def regenerate(manifest_path: Path) -> None:
    """Re-derive each golden from its real producer and rewrite the manifest's pinned hashes."""
    manifest = load_manifest(manifest_path)
    for entry in manifest.get("goldens", []):
        producer = entry["producer"]
        if producer not in _PRODUCERS:
            raise SystemExit(f"unknown producer {producer!r} for golden {entry['path']!r}")
        content = _PRODUCERS[producer]()
        golden = _resolve_golden(entry["path"])
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(content, encoding="utf-8")
        entry["sha256"] = sha256_of(golden)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--check",
        action="store_true",
        help="check goldens for drift (the default mode; a no-op flag)",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="re-derive goldens from the real producer and rewrite the manifest hashes",
    )
    parser.add_argument(
        "--advisory", action="store_true", help="report drift but always exit 0 (CI rollout mode)"
    )
    args = parser.parse_args(argv)

    if args.regenerate:
        regenerate(args.manifest)
        print(f"check_fake_fixtures: regenerated goldens from real producers -> {args.manifest}")
        return 0

    drifts = check_goldens(args.manifest)
    for d in drifts:
        print(f"DRIFT [{d.kind}] {d.path}: {d.detail}")
    if not drifts:
        print("check_fake_fixtures: OK — all goldens present and match their pinned hash")
        return 0
    print(f"check_fake_fixtures: {len(drifts)} golden(s) drifted from the real producer")
    return 0 if args.advisory else 1


if __name__ == "__main__":
    raise SystemExit(main())
