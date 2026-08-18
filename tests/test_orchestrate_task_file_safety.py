"""A unit name and a ``task_file`` pointer are trust boundaries; neither leaves the task dir.

Two reviewer findings on the task-spill unit, both reproduced:

- ``spill_unit`` built the spill path straight from the unit name, and in Python an absolute
  right-hand operand discards the left when joined, while ``..`` traverses -- a plan naming a
  unit ``/tmp/victim`` made ``Run.save()`` write ``/tmp/victim.task.md``, and ``read_unit``
  joined a stored pointer onto ``TASK_DIR`` with no containment check, so a crafted pointer
  read a file from anywhere on disk.
- ``read_unit`` treated every ``OSError`` as "the file is gone", so a directory standing where
  the spill should be, or a permission error, silently emptied the task AND dropped the pointer,
  making the loss permanent at the next save.

Names are therefore refused at the boundaries where they enter a run -- ``start`` and
``expand`` -- and independently every pointer must resolve beneath ``TASK_DIR`` on save and on
load, symlinks resolved, so a run record edited by hand cannot do what a validated name never
can. Only a genuinely missing file still loads as an empty task with its note.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
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

_MARKER = "safety-marker-9c41-must-not-leak-outside-the-task-dir"

LONG_TASK = (
    f"/saga:work docs/plans/{_MARKER}.md\n"
    "\n"
    "A unit name is one path component, not a path. The spill writes the task under the task\n"
    "directory and the run record keeps a pointer to it; neither may reach anything outside.\n"
    + "Contain the task spill inside the task directory. "
    * 8
)


@pytest.fixture(scope="module")
def orchestrate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_orchestrate_task_file_safety", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repository with one commit, so ``start`` can resolve HEAD."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "test@example.com")
    _git(r, "config", "user.name", "Test")
    (r / "base.txt").write_text("base\n")
    _git(r, "add", "base.txt")
    _git(r, "commit", "-m", "base")
    return r


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    """A directory beside the repository -- outside it, and outside ``TASK_DIR``."""
    d = tmp_path / "outside"
    d.mkdir()
    return d


def _task_dir(repo: Path) -> Path:
    return repo / ".orchestrate" / "tasks"


def _write_plan(repo: Path, units: list[dict[str, Any]]) -> Path:
    plan = repo / "plan.json"
    plan.write_text(json.dumps({"run_id": "r1", "source": "a test", "units": units}))
    return plan


def _write_raw_run(repo: Path, units: list[dict[str, Any]]) -> Path:
    """A run.json written by hand -- the case that never passed through name validation."""
    path = repo / ".orchestrate" / "run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"run_id": "r1", "source": "a test", "base": "0" * 40, "units": units}
    path.write_text(json.dumps(payload))
    return path


def _unit_row(name: str, **over: Any) -> dict[str, Any]:
    return {"name": name, "vendor": "claude", "task": "", "status": "pending", **over}


def _traversal(repo: Path, target: Path) -> str:
    """A pointer of pure ``..`` components, relative to the task dir, reaching ``target``."""
    return os.path.relpath(target, _task_dir(repo))


def _branch_exists(repo: Path, branch: str) -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", branch], cwd=repo, capture_output=True
    )
    return probe.returncode == 0


class TestAUnitNameIsOneSafePathComponent:
    """Names enter a run at ``start`` and ``expand``; a bad one fails before anything exists."""

    def test_an_absolute_name_is_rejected_at_start_and_writes_nothing_outside(
        self,
        orchestrate: ModuleType,
        repo: Path,
        outside: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        plan = _write_plan(repo, [_unit_row(str(outside / "victim"), task=LONG_TASK)])
        monkeypatch.chdir(repo)

        with pytest.raises(SystemExit):
            orchestrate.cmd_start(argparse.Namespace(plan=str(plan), base=None))

        assert list(outside.iterdir()) == [], "nothing may be written outside the task dir"
        assert not (repo / ".orchestrate").exists(), "the run record must not be written"
        assert not _branch_exists(repo, "orch/r1"), "no run branch before the name is refused"

    def test_a_traversing_name_is_rejected_at_start_and_writes_nothing_outside(
        self,
        orchestrate: ModuleType,
        repo: Path,
        outside: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        escaped = outside / "escaped"
        plan = _write_plan(repo, [_unit_row(_traversal(repo, escaped), task=LONG_TASK)])
        monkeypatch.chdir(repo)

        with pytest.raises(SystemExit):
            orchestrate.cmd_start(argparse.Namespace(plan=str(plan), base=None))

        assert not escaped.with_name("escaped.task.md").exists()
        assert list(outside.iterdir()) == []
        assert not (repo / ".orchestrate").exists()

    @pytest.mark.parametrize("name", ["", ".", ".."])
    def test_the_other_unsafe_names_are_rejected_before_anything_is_written(
        self,
        orchestrate: ModuleType,
        repo: Path,
        name: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        plan = _write_plan(repo, [_unit_row(name, task=LONG_TASK)])
        monkeypatch.chdir(repo)

        with pytest.raises(SystemExit):
            orchestrate.cmd_start(argparse.Namespace(plan=str(plan), base=None))

        assert not (repo / ".orchestrate").exists()

    def test_an_absolute_name_is_rejected_at_expand_and_leaves_the_record_untouched(
        self,
        orchestrate: ModuleType,
        repo: Path,
        outside: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        run_path = _write_raw_run(repo, [_unit_row("seed", task="x")])
        before = run_path.read_bytes()
        plan = _write_plan(repo, [_unit_row(str(outside / "victim"), task=LONG_TASK)])
        monkeypatch.chdir(repo)

        with pytest.raises(SystemExit):
            orchestrate.cmd_expand(argparse.Namespace(plan=str(plan)))

        assert list(outside.iterdir()) == []
        assert run_path.read_bytes() == before

    def test_a_traversing_name_is_rejected_at_expand_and_leaves_the_record_untouched(
        self,
        orchestrate: ModuleType,
        repo: Path,
        outside: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        run_path = _write_raw_run(repo, [_unit_row("seed", task="x")])
        before = run_path.read_bytes()
        escaped = outside / "escaped"
        plan = _write_plan(repo, [_unit_row(_traversal(repo, escaped), task=LONG_TASK)])
        monkeypatch.chdir(repo)

        with pytest.raises(SystemExit):
            orchestrate.cmd_expand(argparse.Namespace(plan=str(plan)))

        assert not escaped.with_name("escaped.task.md").exists()
        assert run_path.read_bytes() == before


class TestATaskFilePointerNeverLeavesTheTaskDirectory:
    """Containment is checked on save AND on load, symlinks resolved before comparing.

    Independent of the name check by construction: the load side reads records that were
    written by hand and never saw ``start`` or ``expand``, and the save side builds the run
    in memory, bypassing both boundaries.
    """

    def test_an_absolute_pointer_is_rejected_on_load(
        self,
        orchestrate: ModuleType,
        repo: Path,
        outside: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = outside / "victim.task.md"
        target.write_text("contents of a file outside the task dir")
        _write_raw_run(repo, [_unit_row("u", task_file=str(target))])
        monkeypatch.chdir(repo)

        with pytest.raises(SystemExit):
            orchestrate.Run.load()

    def test_a_traversing_pointer_is_rejected_on_load(
        self,
        orchestrate: ModuleType,
        repo: Path,
        outside: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = outside / "escaped.task.md"
        target.write_text("contents of a file outside the task dir")
        _write_raw_run(repo, [_unit_row("u", task_file=_traversal(repo, target))])
        monkeypatch.chdir(repo)

        with pytest.raises(SystemExit):
            orchestrate.Run.load()

    def test_an_escaping_name_is_rejected_on_save(
        self,
        orchestrate: ModuleType,
        repo: Path,
        outside: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A run built in memory never passed through ``start``; save must still refuse it."""
        monkeypatch.chdir(repo)
        victim = outside / "victim"
        r = orchestrate.Run(
            run_id="r1",
            source="a test",
            base="0" * 40,
            units=[orchestrate.Unit(name=str(victim), vendor="claude", task=LONG_TASK)],
        )

        with pytest.raises(SystemExit):
            r.save()

        assert not victim.with_name("victim.task.md").exists()
        assert list(outside.iterdir()) == []
        assert not (repo / ".orchestrate" / "run.json").exists()

    def test_a_traversing_name_is_rejected_on_save(
        self,
        orchestrate: ModuleType,
        repo: Path,
        outside: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(repo)
        escaped = outside / "escaped"
        r = orchestrate.Run(
            run_id="r1",
            source="a test",
            base="0" * 40,
            units=[
                orchestrate.Unit(name=_traversal(repo, escaped), vendor="claude", task=LONG_TASK)
            ],
        )

        with pytest.raises(SystemExit):
            r.save()

        assert not escaped.with_name("escaped.task.md").exists()
        assert list(outside.iterdir()) == []

    def test_a_symlink_out_of_the_directory_is_rejected_on_load(
        self,
        orchestrate: ModuleType,
        repo: Path,
        outside: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Resolving symlinks is what catches this: the link itself sits inside ``TASK_DIR``."""
        target = outside / "target.task.md"
        target.write_text("contents of a file outside the task dir")
        task_dir = _task_dir(repo)
        task_dir.mkdir(parents=True)
        (task_dir / "link.task.md").symlink_to(target)
        _write_raw_run(repo, [_unit_row("u", task_file="link.task.md")])
        monkeypatch.chdir(repo)

        with pytest.raises(SystemExit):
            orchestrate.Run.load()

        assert target.read_text() == "contents of a file outside the task dir"

    def test_save_does_not_write_through_a_planted_symlink(
        self,
        orchestrate: ModuleType,
        repo: Path,
        outside: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = outside / "victim.task.md"
        target.write_text("sentinel")
        task_dir = _task_dir(repo)
        task_dir.mkdir(parents=True)
        (task_dir / "evil.task.md").symlink_to(target)
        monkeypatch.chdir(repo)
        r = orchestrate.Run(
            run_id="r1",
            source="a test",
            base="0" * 40,
            units=[orchestrate.Unit(name="evil", vendor="claude", task=LONG_TASK)],
        )

        with pytest.raises(SystemExit):
            r.save()

        assert target.read_text() == "sentinel", "the long task must not go through the link"


class TestARealReadFailureSurfacesInsteadOfEmptyingTheTask:
    """Only a genuinely missing file loads as an empty task; every other failure raises.

    The old code caught ``OSError`` and dropped the pointer, so the next save made the loss
    permanent and the unit could later be launched with no instructions.
    """

    def test_a_directory_where_the_spill_should_be_raises(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        task_dir = _task_dir(repo)
        task_dir.mkdir(parents=True)
        (task_dir / "gone.task.md").mkdir()
        _write_raw_run(repo, [_unit_row("gone", task_file="gone.task.md")])
        monkeypatch.chdir(repo)

        with pytest.raises(IsADirectoryError):
            orchestrate.Run.load()

    @pytest.mark.skipif(
        hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores file modes"
    )
    def test_an_unreadable_spill_file_raises(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        task_dir = _task_dir(repo)
        task_dir.mkdir(parents=True)
        locked = task_dir / "locked.task.md"
        locked.write_text("the instructions")
        locked.chmod(0o000)
        _write_raw_run(repo, [_unit_row("locked", task_file="locked.task.md")])
        monkeypatch.chdir(repo)
        try:
            with pytest.raises(PermissionError):
                orchestrate.Run.load()
        finally:
            locked.chmod(0o644)


class TestWhatMustKeepWorking:
    """The remediation narrows, not moves, the behaviour of the spill."""

    def test_a_missing_spill_still_loads_as_an_empty_task_with_its_note(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_raw_run(repo, [_unit_row("gone", task_file="gone.task.md")])
        monkeypatch.chdir(repo)

        loaded = orchestrate.Run.load()  # must not raise

        gone = loaded.unit("gone")
        assert gone.task == ""
        assert gone.task_file is None
        assert "gone.task.md" in gone.note

    def test_a_normal_long_task_round_trips_byte_identically(
        self,
        orchestrate: ModuleType,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(repo)
        r = orchestrate.Run(
            run_id="r1",
            source="a test",
            base="0" * 40,
            units=[orchestrate.Unit(name="build", vendor="claude", task=LONG_TASK)],
        )
        r.save()

        spill = _task_dir(repo) / "build.task.md"
        assert spill.read_text() == LONG_TASK
        assert _MARKER not in (repo / ".orchestrate" / "run.json").read_text()
        assert orchestrate.Run.load().unit("build").task == LONG_TASK
