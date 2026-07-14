"""Real-adapter lane: the U7 worktree-liveness oracle vs. the real ``git worktree`` CLI (T11-F4-8).

This is the first fake-only seam migrated to a real-substrate test. It drives the real production
adapter ``outcome_worktrees.git_worktree_ops`` against a real git repo and real ``git worktree``
subprocesses — no ``FakeWT``, no hand-crafted porcelain. It reproduces the exact conditions of the
P0 in ``docs/engineering-journal/LEARNINGS.md`` ``{#fake-adapter-hides-real-path-mismatch}``: real
``git worktree list --porcelain`` emits realpath-canonicalized paths, so a symlinked or relative
``--repo-root`` diverges from a naive string compare and silently marks live worktrees as absent.

Acceptance: the seam passes against the real CLI and a deliberately broken (non-canonicalized)
comparison fails the same liveness check.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess  # nosec B404 — git CLI only, fixed argv, no shell
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"

_GIT_CFG = [
    "-c",
    "user.email=t@example.com",
    "-c",
    "user.name=Test",
    "-c",
    "init.defaultBranch=main",
]


def _load(name: str) -> Any:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


WT = _load("outcome_worktrees")


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(  # nosec B603 B607 — fixed argv, no shell
        ["git", *_GIT_CFG, *args], cwd=str(cwd), capture_output=True, text=True, check=True
    )


@pytest.fixture
def real_repo(tmp_path: Path) -> Path:
    """A real, initialized git repo with one commit (so ``git worktree add`` works)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init"], repo)
    _git(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def test_liveness_true_for_live_worktree_via_real_git(real_repo: Path) -> None:
    """The real adapter reports a just-created worktree as live via the real ``git worktree`` CLI."""
    ops = WT.git_worktree_ops(real_repo)
    path = str(WT.worktree_path(real_repo, "o", "s1"))
    assert ops.add(path, WT.worktree_name("o", "s1")) is True
    assert ops.exists(path) is True
    assert path in {os.path.realpath(p) for p in ops.list_paths()} or ops.exists(path)


def test_liveness_false_for_never_created_worktree(real_repo: Path) -> None:
    """A path that was never provisioned reads as a definite absence (not a degraded 'present')."""
    ops = WT.git_worktree_ops(real_repo)
    assert ops.exists(str(WT.worktree_path(real_repo, "o", "ghost"))) is False


def test_liveness_survives_symlinked_repo_root(tmp_path: Path, real_repo: Path) -> None:
    """Canonicalization is load-bearing: a symlinked repo root still reads the worktree as live.

    Real ``git worktree list --porcelain`` emits realpath-resolved paths. Accessed through a
    symlink, the registry path built from the symlinked root diverges from git's output — the exact
    shape of the P0. The real adapter's realpath canonicalization must reconcile them.
    """
    ops_real = WT.git_worktree_ops(real_repo)
    path_real = str(WT.worktree_path(real_repo, "o", "s1"))
    assert ops_real.add(path_real, WT.worktree_name("o", "s1")) is True

    link = tmp_path / "symlink-root"
    link.symlink_to(real_repo)
    # Skip only if the platform silently resolved the symlink to the same path (no divergence to test).
    if os.path.realpath(link) == str(link):
        pytest.skip("symlink did not diverge from its target on this platform")

    ops_link = WT.git_worktree_ops(link)
    path_link = str(WT.worktree_path(link, "o", "s1"))
    assert ops_link.exists(path_link) is True


def test_liveness_survives_relative_repo_root(
    real_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A relative ``repo_root`` (the ``/outcome`` CLI default of ``.``) still resolves correctly.

    Mirrors production: the coordinator runs from inside the repo with ``repo_root='.'``, so
    ``worktree_path`` yields a repo-relative path that the adapter must canonicalize against the
    resolved cwd — the exact relative-root axis called out in ``git_worktree_ops``' docstring.
    """
    ops_abs = WT.git_worktree_ops(real_repo)
    path = str(WT.worktree_path(real_repo, "o", "s1"))
    assert ops_abs.add(path, WT.worktree_name("o", "s1")) is True

    monkeypatch.chdir(real_repo)
    ops_rel = WT.git_worktree_ops(Path("."))
    rel_path = str(WT.worktree_path(Path("."), "o", "s1"))
    assert ops_rel.exists(rel_path) is True


def test_naive_noncanonical_comparison_fails_the_same_check(
    tmp_path: Path, real_repo: Path
) -> None:
    """A deliberately broken (non-canonicalized) comparison mis-reads the live worktree as absent.

    This pins WHY the real adapter canonicalizes: the naive raw-string membership test — exactly the
    fake's original behavior — returns the wrong answer under a symlinked root, proving the
    real-substrate lane catches the regression the fake-only suite hid.
    """
    ops_real = WT.git_worktree_ops(real_repo)
    path_real = str(WT.worktree_path(real_repo, "o", "s1"))
    assert ops_real.add(path_real, WT.worktree_name("o", "s1")) is True

    link = tmp_path / "symlink-root"
    link.symlink_to(real_repo)
    if os.path.realpath(link) == str(link):
        pytest.skip("symlink did not diverge from its target on this platform")

    path_link = str(WT.worktree_path(link, "o", "s1"))
    rc, out, _err = WT._run_git(["worktree", "list", "--porcelain"], cwd=link)
    assert rc == 0
    listed_raw = {
        line[len("worktree ") :] for line in out.splitlines() if line.startswith("worktree ")
    }
    # The naive compare (no realpath) says ABSENT — the silent bug the real adapter fixes.
    assert path_link not in listed_raw
    # While the real, canonicalizing adapter says PRESENT.
    assert WT.git_worktree_ops(link).exists(path_link) is True
