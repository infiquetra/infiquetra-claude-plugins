"""Unit tests for team-execution typed artifact pointers — Layer 1 (U1).

All git behavior is exercised against real scratch repos built in ``tmp_path`` fixtures; git is
never mocked (KTD1's temp-index guarantee and the holding-ref retention can only be shown against a
real object store).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT = (
    ROOT
    / "plugins"
    / "team-execution"
    / "skills"
    / "team-execution"
    / "scripts"
    / "artifact_pointer.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("artifact_pointer", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["artifact_pointer"] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "initial")
    return path


def test_contract_round_trips_all_kinds() -> None:
    """Construct -> serialize -> parse round-trips every field for diff/file/symbol kinds."""
    ap = _load()
    for kind, locator in (
        ("diff", "refs/team-execution/snapshots/run-1/0"),
        ("file", "src/app.py"),
        ("symbol", "src/app.py#handler"),
    ):
        pointer = ap.ArtifactPointer(
            kind=kind, locator=locator, hash="deadbeef", epoch="3", deref="git diff A B"
        )
        parsed = ap.ArtifactPointer.from_json(pointer.to_json())
        assert parsed == pointer
        assert parsed.kind == kind


def test_from_json_rejects_unknown_kind_and_missing_fields() -> None:
    ap = _load()
    import json

    good = {
        "kind": "diff",
        "locator": "r",
        "hash": "h",
        "epoch": "0",
        "deref": "git diff A B",
    }
    try:
        ap.ArtifactPointer.from_json(json.dumps({**good, "kind": "bogus"}))
        raise AssertionError("expected ValueError for unknown kind")
    except ValueError:
        pass
    incomplete = dict(good)
    del incomplete["hash"]
    try:
        ap.ArtifactPointer.from_json(json.dumps(incomplete))
        raise AssertionError("expected ValueError for missing field")
    except ValueError:
        pass


def test_snapshot_captures_staged_unstaged_untracked(tmp_path: Path) -> None:
    """The tree OID covers staged + unstaged + untracked files (KTD1)."""
    repo = _init_repo(tmp_path / "repo")
    ap = _load()

    (repo / "tracked.txt").write_text("unstaged change\n", encoding="utf-8")  # unstaged
    (repo / "staged.txt").write_text("staged new\n", encoding="utf-8")
    _git(repo, "add", "staged.txt")  # staged
    (repo / "untracked.txt").write_text("untracked new\n", encoding="utf-8")  # untracked

    pointer = ap.snapshot("run-1", "0", repo_root=repo)
    diff = ap.deref(pointer, repo_root=repo)

    assert "unstaged change" in diff
    assert "staged new" in diff
    assert "untracked new" in diff


def test_snapshot_leaves_real_index_and_worktree_untouched(tmp_path: Path) -> None:
    """The real index and working tree are byte-identical before and after snapshot (KTD1)."""
    repo = _init_repo(tmp_path / "repo")
    ap = _load()

    (repo / "tracked.txt").write_text("unstaged change\n", encoding="utf-8")
    (repo / "staged.txt").write_text("staged new\n", encoding="utf-8")
    _git(repo, "add", "staged.txt")
    (repo / "untracked.txt").write_text("untracked new\n", encoding="utf-8")

    status_before = _git(repo, "status", "--porcelain=v1")
    index_tree_before = _git(repo, "write-tree")  # OID of the *real* index

    ap.snapshot("run-1", "0", repo_root=repo)

    assert _git(repo, "status", "--porcelain=v1") == status_before
    assert _git(repo, "write-tree") == index_tree_before
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "unstaged change\n"


def test_holding_ref_survives_gc(tmp_path: Path) -> None:
    """The snapshot tree survives ``git gc --prune=now`` via its holding ref (issue Q1)."""
    repo = _init_repo(tmp_path / "repo")
    ap = _load()

    (repo / "untracked.txt").write_text("keep me\n", encoding="utf-8")
    pointer = ap.snapshot("run-1", "0", repo_root=repo)

    _git(repo, "gc", "--prune=now")

    assert _git(repo, "cat-file", "-t", pointer.hash) == "tree"
    diff = ap.deref(pointer, repo_root=repo)
    assert "keep me" in diff


def test_byte_drift_raises_hash_mismatch(tmp_path: Path) -> None:
    """Moving the holding ref to a different tree while keeping the pointer -> HASH_MISMATCH."""
    repo = _init_repo(tmp_path / "repo")
    ap = _load()

    (repo / "untracked.txt").write_text("original\n", encoding="utf-8")
    pointer = ap.snapshot("run-1", "0", repo_root=repo)

    other_tree = _git(repo, "rev-parse", "HEAD^{tree}")  # a different, valid tree OID
    _git(repo, "update-ref", pointer.locator, other_tree)

    try:
        ap.deref(pointer, repo_root=repo)
        raise AssertionError("expected PointerError")
    except ap.PointerError as exc:
        assert exc.code == ap.ERR_HASH_MISMATCH


def test_superseding_epoch_raises_stale(tmp_path: Path) -> None:
    """A newer epoch ref for the same run-id makes an older pointer STALE (freshness)."""
    repo = _init_repo(tmp_path / "repo")
    ap = _load()

    (repo / "untracked.txt").write_text("epoch 0\n", encoding="utf-8")
    old_pointer = ap.snapshot("run-1", "0", repo_root=repo)

    (repo / "untracked.txt").write_text("epoch 1\n", encoding="utf-8")
    ap.snapshot("run-1", "1", repo_root=repo)  # supersedes epoch 0

    # Integrity still holds for the old pointer (its ref + tree are intact)...
    assert _git(repo, "rev-parse", old_pointer.locator) == old_pointer.hash
    try:
        ap.deref(old_pointer, repo_root=repo)
        raise AssertionError("expected PointerError")
    except ap.PointerError as exc:
        assert exc.code == ap.ERR_STALE


def test_deref_resolves_from_linked_worktree(tmp_path: Path) -> None:
    """A pointer snapshotted in the main repo dereferences from a linked worktree (KTD7)."""
    repo = _init_repo(tmp_path / "repo")
    ap = _load()

    (repo / "untracked.txt").write_text("shared object\n", encoding="utf-8")
    pointer = ap.snapshot("run-1", "0", repo_root=repo)

    worktree = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", str(worktree), "HEAD")

    diff = ap.deref(pointer, repo_root=worktree)
    assert "shared object" in diff


def test_cli_deref_prints_typed_code_to_stderr(tmp_path: Path) -> None:
    """The CLI exits non-zero and prints the typed code to stderr on a stale pointer."""
    repo = _init_repo(tmp_path / "repo")

    (repo / "untracked.txt").write_text("epoch 0\n", encoding="utf-8")
    snap0 = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo),
            "snapshot",
            "--run",
            "r",
            "--epoch",
            "0",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    pointer_json = snap0.stdout.strip()
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo),
            "snapshot",
            "--run",
            "r",
            "--epoch",
            "1",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(repo), "deref", pointer_json],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "POINTER_STALE" in result.stderr
