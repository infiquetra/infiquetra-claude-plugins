"""Land completed units without touching the operator's checkout.

These tests use real repositories and real linked worktrees.  The contract under test is Git's
behavior: a landing worktree must be detached because the run branch may already be checked out,
and a merge conflict must leave a usable recovery surface rather than an aborted merge.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "orchestrate"
    / "skills"
    / "orchestrate"
    / "scripts"
    / "orchestrate.py"
)


@pytest.fixture(scope="module")
def orchestrate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_orchestrate_land_worktree", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _git_out(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, path: str, content: str | None = None) -> None:
    (repo / path).write_text(content if content is not None else f"{path}\n")
    _git(repo, "add", path)
    _git(repo, "commit", "-m", f"write {path}")


def _repo(tmp_path: Path, units: tuple[str, ...], *, conflicting: bool = False) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _commit(repo, "base.txt", "base\n")
    if conflicting:
        _commit(repo, "shared.txt", "base\n")
    _git(repo, "branch", "orch/r1")

    for unit in units:
        _git(repo, "checkout", "-b", f"orch/r1-{unit}", "orch/r1")
        if conflicting:
            _commit(repo, "shared.txt", f"{unit}\n")
        else:
            _commit(repo, f"{unit}.txt")
        _git(repo, "checkout", "main")
    return repo


def _unit(name: str, **overrides: Any) -> dict[str, Any]:
    return {
        "name": name,
        "vendor": "claude",
        "task": "test landing",
        "branch": f"orch/r1-{name}",
        "status": "done",
        **overrides,
    }


def _write_run(repo: Path, units: list[dict[str, Any]], **overrides: Any) -> Path:
    payload = {
        "run_id": "r1",
        "source": "land-worktree test",
        "base": _git_out(repo, "rev-parse", "main"),
        "branch": "orch/r1",
        "units": units,
        **overrides,
    }
    run_file = repo / ".orchestrate" / "run.json"
    run_file.parent.mkdir(parents=True, exist_ok=True)
    run_file.write_text(json.dumps(payload, indent=2) + "\n")
    return run_file


def _land_path(repo: Path) -> Path:
    return repo / ".orchestrate" / "land-r1"


def _branch_file(repo: Path, branch: str, path: str) -> str:
    return _git_out(repo, "show", f"{branch}:{path}")


def _land(orchestrate: ModuleType) -> int:
    return int(orchestrate.cmd_land(argparse.Namespace(clean=False)))


def _clean_merged(orchestrate: ModuleType) -> int:
    return int(orchestrate.cmd_clean(argparse.Namespace(merged=True, branches=False, all=False)))


def test_land_succeeds_with_a_dirty_operator_tree_and_preserves_its_changes(
    orchestrate: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo(tmp_path, ("alpha",))
    _write_run(repo, [_unit("alpha")])
    dirty_path = repo / "base.txt"
    dirty_path.write_text("operator edit\n")
    before_status = _git_out(repo, "status", "--porcelain", "--untracked-files=no")
    before_bytes = dirty_path.read_bytes()
    monkeypatch.chdir(repo)

    assert _land(orchestrate) == 0

    assert _branch_file(repo, "orch/r1", "alpha.txt") == "alpha.txt"
    assert dirty_path.read_bytes() == before_bytes
    assert _git_out(repo, "status", "--porcelain", "--untracked-files=no") == before_status


def test_two_units_land_and_the_throwaway_worktree_is_removed(
    orchestrate: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo(tmp_path, ("alpha", "beta"))
    _write_run(repo, [_unit("alpha"), _unit("beta")])
    monkeypatch.chdir(repo)

    assert _land(orchestrate) == 0

    assert _branch_file(repo, "orch/r1", "alpha.txt") == "alpha.txt"
    assert _branch_file(repo, "orch/r1", "beta.txt") == "beta.txt"
    assert not _land_path(repo).exists()
    assert str(_land_path(repo)) not in _git_out(repo, "worktree", "list", "--porcelain")


def test_conflict_retains_and_reports_the_detached_landing_worktree(
    orchestrate: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _repo(tmp_path, ("alpha", "beta"), conflicting=True)
    run_file = _write_run(repo, [_unit("alpha"), _unit("beta")])
    monkeypatch.chdir(repo)

    assert _land(orchestrate) == 1

    record = json.loads(run_file.read_text())
    retained = Path(record["conflict_worktree"])
    output = capsys.readouterr().out
    assert retained == _land_path(repo)
    assert retained.is_dir()
    assert str(retained) in output
    assert "CONFLICT landing beta" in output
    assert "on orch/r1, finish" not in output
    assert "UU shared.txt" in _git_out(retained, "status", "--porcelain")
    assert _branch_file(repo, "orch/r1", "shared.txt") == "alpha"


def test_clean_merged_recognises_and_keeps_a_retained_conflict_worktree(
    orchestrate: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _repo(tmp_path, ("alpha", "beta"), conflicting=True)
    run_file = _write_run(repo, [_unit("alpha"), _unit("beta")])
    monkeypatch.chdir(repo)
    assert _land(orchestrate) == 1
    capsys.readouterr()
    retained = Path(json.loads(run_file.read_text())["conflict_worktree"])

    assert _clean_merged(orchestrate) == 0

    output = capsys.readouterr().out
    assert retained.is_dir()
    assert str(retained) in output
    assert "kept" in output


def test_land_advances_a_run_branch_checked_out_in_the_dirty_operator_tree(
    orchestrate: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _repo(tmp_path, ("alpha",))
    _write_run(repo, [_unit("alpha")])
    _git(repo, "checkout", "orch/r1")
    dirty_path = repo / "base.txt"
    dirty_path.write_text("operator edit on run branch\n")
    before_bytes = dirty_path.read_bytes()
    old_tip = _git_out(repo, "rev-parse", "orch/r1")
    monkeypatch.chdir(repo)

    assert _land(orchestrate) == 0

    new_tip = _git_out(repo, "rev-parse", "orch/r1")
    assert new_tip != old_tip
    assert _branch_file(repo, "orch/r1", "alpha.txt") == "alpha.txt"
    assert dirty_path.read_bytes() == before_bytes
    assert _git_out(repo, "rev-parse", "--abbrev-ref", "HEAD") == "orch/r1"
    output = capsys.readouterr().out
    assert "checked out" in output
    assert "uncommitted files" in output


def test_a_worktree_already_holding_the_run_branch_does_not_block_land(
    orchestrate: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo(tmp_path, ("alpha",))
    _write_run(repo, [_unit("alpha")])
    retained = tmp_path / "retained-conflict"
    _git(repo, "worktree", "add", str(retained), "orch/r1")
    monkeypatch.chdir(repo)

    assert _land(orchestrate) == 0

    assert retained.is_dir()
    assert _branch_file(repo, "orch/r1", "alpha.txt") == "alpha.txt"
    assert not _land_path(repo).exists()


def test_land_path_cannot_collide_with_a_unit_named_for_the_land_worktree(
    orchestrate: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo(tmp_path, ())
    unit_worktree = repo.parent / "orch-land-r1"
    _git(
        repo,
        "worktree",
        "add",
        str(unit_worktree),
        "-b",
        "orch/r1-land-r1",
        "orch/r1",
    )
    _commit(unit_worktree, "unit.txt")
    _write_run(repo, [_unit("land-r1", worktree=str(unit_worktree))])
    monkeypatch.chdir(repo)

    assert _land(orchestrate) == 0

    assert unit_worktree.is_dir()
    assert unit_worktree != _land_path(repo)
    assert _branch_file(repo, "orch/r1", "unit.txt") == "unit.txt"
    assert not _land_path(repo).exists()


def test_land_fails_loudly_when_the_run_branch_does_not_resolve(
    orchestrate: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo(tmp_path, ("alpha",))
    _write_run(repo, [_unit("alpha")])
    _git(repo, "branch", "-D", "orch/r1")
    monkeypatch.chdir(repo)

    with pytest.raises(SystemExit, match=r"orch/r1.*does not resolve"):
        _land(orchestrate)

    assert not _land_path(repo).exists()
