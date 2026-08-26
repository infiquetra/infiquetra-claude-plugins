"""Long unit tasks spill out of run.json into their own files, transparently.

Measured on a real 75-unit run: run.json was 267,897 bytes and 223,040 of them -- 83% -- were
unit task text, rewritten whole on every ``save`` and parsed by every subcommand. A task longer
than ``TASK_SPILL_THRESHOLD`` is therefore written to ``TASK_DIR / "<unit>.task.md"`` at save
time and the record keeps a pointer; at load time the file is read back into ``unit.task``, so
every existing caller keeps working unchanged. A record written before the spill existed still
loads with its inline task, and a pointer whose file is gone loads as an empty task with a note
rather than raising.

This is a separate mechanism from the too-long-to-TYPE handover in ``pane_text`` -- its own
threshold (``PANE_TYPING_LIMIT``) and its own file name (``<unit>.md``) -- which stays as it is.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
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

_MARKER = "spill-marker-6f2a-must-not-appear-in-run-json"

LONG_TASK = (
    f"/saga:work docs/plans/{_MARKER}.md\n"
    "\n"
    "Stop storing full task prompts inside run.json. Every save rewrites the whole thing, every\n"
    "subcommand parses it, and no operator or agent can read their own run record. The spill\n"
    "keeps the record small: the pointer stays in run.json and the text moves to its own file.\n"
    + "Spill the task text out of the record. "
    * 12
)


@pytest.fixture(scope="module")
def orchestrate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_orchestrate_task_spill", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(orchestrate: ModuleType, *units: Any) -> Any:
    return orchestrate.Run(run_id="r1", source="a test", base="0" * 40, units=list(units))


def _run_path(cwd: Path) -> Path:
    return cwd / ".orchestrate" / "run.json"


def _spill_path(cwd: Path, name: str) -> Path:
    return cwd / ".orchestrate" / "tasks" / f"{name}.task.md"


def _write_raw_run(cwd: Path, units: list[dict[str, Any]]) -> Path:
    """A run.json written by hand the way an older version -- or a test -- writes it."""
    path = _run_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"run_id": "r1", "source": "a test", "base": "0" * 40, "units": units}
    path.write_text(json.dumps(payload))
    return path


def _read_run(cwd: Path) -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(_run_path(cwd).read_text())
    return raw


class TestALongTaskSpillsOnSave:
    """The record keeps the pointer; ``TASK_DIR`` keeps the text; callers see no difference."""

    def test_the_round_trip_is_byte_identical(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _run(orchestrate, orchestrate.Unit(name="build", vendor="claude", task=LONG_TASK)).save()

        loaded = orchestrate.Run.load()
        assert loaded.unit("build").task == LONG_TASK

    def test_the_saved_run_json_carries_no_task_text(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _run(orchestrate, orchestrate.Unit(name="build", vendor="claude", task=LONG_TASK)).save()

        assert _MARKER not in _run_path(tmp_path).read_text()
        record = _read_run(tmp_path)["units"][0]
        assert record["task"] == ""
        assert record["task_file"] == "build.task.md"

    def test_the_spill_file_holds_exactly_the_task(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The generated spill on disk begins with a stable ownership marker followed by task text."""
        monkeypatch.chdir(tmp_path)
        _run(orchestrate, orchestrate.Unit(name="build", vendor="claude", task=LONG_TASK)).save()

        marker = orchestrate.task_spill_marker("r1", "build")
        assert _spill_path(tmp_path, "build").read_text() == f"{marker}\n{LONG_TASK}"

    def test_a_task_one_over_the_threshold_spills(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        task = "x" * (orchestrate.TASK_SPILL_THRESHOLD + 1)
        _run(orchestrate, orchestrate.Unit(name="edge", vendor="claude", task=task)).save()

        record = _read_run(tmp_path)["units"][0]
        assert record["task"] == ""
        assert record["task_file"] == "edge.task.md"


class TestTaskSpillOwnershipAndNoClobber:
    """Generated spills carry run/unit ownership; unmarked or foreign files are protected."""

    def test_generated_spill_marker_parses_run_and_unit_identity(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _run(orchestrate, orchestrate.Unit(name="build", vendor="claude", task=LONG_TASK)).save()

        content = _spill_path(tmp_path, "build").read_text()
        owner = orchestrate.parse_task_spill_marker(content)
        assert owner == ("r1", "build")

    def test_unmarked_hand_authored_brief_is_never_overwritten_and_bytes_untouched(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        spill_file = _spill_path(tmp_path, "build")
        spill_file.parent.mkdir(parents=True, exist_ok=True)
        original_bytes = b"# Hand-authored brief\nDo not clobber this file.\n"
        spill_file.write_bytes(original_bytes)

        with pytest.raises(SystemExit) as exc_info:
            _run(orchestrate, orchestrate.Unit(name="build", vendor="claude", task=LONG_TASK)).save()

        assert "refusing to overwrite unmarked task file" in str(exc_info.value)
        assert "build.task.md" in str(exc_info.value)
        assert spill_file.read_bytes() == original_bytes

    def test_foreign_run_owned_task_file_is_never_overwritten(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        spill_file = _spill_path(tmp_path, "build")
        spill_file.parent.mkdir(parents=True, exist_ok=True)
        foreign_marker = orchestrate.task_spill_marker("other-run", "build")
        original_bytes = f"{foreign_marker}\nPrior run task instructions".encode()
        spill_file.write_bytes(original_bytes)

        with pytest.raises(SystemExit) as exc_info:
            _run(orchestrate, orchestrate.Unit(name="build", vendor="claude", task=LONG_TASK)).save()

        assert "refusing to overwrite task file" in str(exc_info.value)
        assert "other-run" in str(exc_info.value)
        assert "r1" in str(exc_info.value)
        assert "build.task.md" in str(exc_info.value)
        assert spill_file.read_bytes() == original_bytes

    def test_foreign_unit_owned_task_file_is_never_overwritten(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        spill_file = _spill_path(tmp_path, "build")
        spill_file.parent.mkdir(parents=True, exist_ok=True)
        foreign_marker = orchestrate.task_spill_marker("r1", "other-unit")
        original_bytes = f"{foreign_marker}\nOther unit task instructions".encode()
        spill_file.write_bytes(original_bytes)

        with pytest.raises(SystemExit) as exc_info:
            _run(orchestrate, orchestrate.Unit(name="build", vendor="claude", task=LONG_TASK)).save()

        assert "refusing to overwrite task file" in str(exc_info.value)
        assert "other-unit" in str(exc_info.value)
        assert "build.task.md" in str(exc_info.value)
        assert spill_file.read_bytes() == original_bytes

    def test_same_owner_rewrite_is_idempotent_and_updates_cleanly(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        r = _run(orchestrate, orchestrate.Unit(name="build", vendor="claude", task=LONG_TASK))
        r.save()

        updated_task = LONG_TASK + "\nAdditional instructions."
        r.units[0].task = updated_task
        r.save()

        loaded = orchestrate.Run.load()
        assert loaded.unit("build").task == updated_task
        marker = orchestrate.task_spill_marker("r1", "build")
        assert _spill_path(tmp_path, "build").read_text() == f"{marker}\n{updated_task}"

    def test_loading_unmarked_hand_authored_brief_loads_verbatim(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        brief_path = _spill_path(tmp_path, "hand_authored")
        brief_path.parent.mkdir(parents=True, exist_ok=True)
        brief_text = "# Custom Brief\n1. Do this.\n2. Do that.\n"
        brief_path.write_text(brief_text)

        _write_raw_run(
            tmp_path,
            [
                {
                    "name": "u",
                    "vendor": "claude",
                    "task": "",
                    "task_file": "hand_authored.task.md",
                    "status": "pending",
                }
            ],
        )

        loaded = orchestrate.Run.load()
        assert loaded.unit("u").task == brief_text
        assert loaded.unit("u").task_file == "hand_authored.task.md"


class TestAShortTaskStaysInline:
    """The spill is for the 83%; a short task never leaves the record."""

    def test_a_short_task_is_saved_inline_without_a_pointer(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _run(
            orchestrate, orchestrate.Unit(name="plan", vendor="claude", task="/saga:plan #456")
        ).save()

        record = _read_run(tmp_path)["units"][0]
        assert record["task"] == "/saga:plan #456"
        assert record["task_file"] is None
        assert not _spill_path(tmp_path, "plan").exists()

    def test_a_task_at_exactly_the_threshold_stays_inline(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only a task LONGER than the threshold spills -- the boundary itself stays inline."""
        monkeypatch.chdir(tmp_path)
        task = "x" * orchestrate.TASK_SPILL_THRESHOLD
        _run(orchestrate, orchestrate.Unit(name="edge", vendor="claude", task=task)).save()

        record = _read_run(tmp_path)["units"][0]
        assert record["task"] == task
        assert record["task_file"] is None
        assert not _spill_path(tmp_path, "edge").exists()


class TestOldFormatRecordsStillLoad:
    """A run.json with full inline tasks predates the spill and must keep working."""

    def test_a_long_inline_task_from_an_older_version_loads_intact(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_raw_run(
            tmp_path, [{"name": "old", "vendor": "claude", "task": LONG_TASK, "status": "pending"}]
        )
        monkeypatch.chdir(tmp_path)

        loaded = orchestrate.Run.load()
        assert loaded.unit("old").task == LONG_TASK
        assert loaded.unit("old").task_file is None

    def test_load_does_not_rewrite_the_record(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No migration at read time: the bytes on disk are exactly as the older version left them."""
        path = _write_raw_run(
            tmp_path, [{"name": "old", "vendor": "claude", "task": LONG_TASK, "status": "pending"}]
        )
        before = path.read_bytes()
        monkeypatch.chdir(tmp_path)

        orchestrate.Run.load()

        assert path.read_bytes() == before
        assert not _spill_path(tmp_path, "old").exists()

    def test_the_next_save_spills_the_old_inline_task(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Migration happens at write time, once, and the round trip survives it."""
        _write_raw_run(
            tmp_path, [{"name": "old", "vendor": "claude", "task": LONG_TASK, "status": "pending"}]
        )
        monkeypatch.chdir(tmp_path)
        loaded = orchestrate.Run.load()
        loaded.save()

        assert _MARKER not in _run_path(tmp_path).read_text()
        marker = orchestrate.task_spill_marker("r1", "old")
        assert _spill_path(tmp_path, "old").read_text() == f"{marker}\n{LONG_TASK}"
        assert orchestrate.Run.load().unit("old").task == LONG_TASK


class TestAMissingSpillFileStillLoads:
    """The run record must stay loadable even when its spill does not."""

    def test_a_deleted_spill_file_loads_as_empty_with_a_note(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_raw_run(
            tmp_path,
            [
                {
                    "name": "gone",
                    "vendor": "claude",
                    "task": "",
                    "task_file": "gone.task.md",
                    "status": "pending",
                },
                {"name": "kept", "vendor": "claude", "task": "still here", "status": "pending"},
            ],
        )
        monkeypatch.chdir(tmp_path)

        loaded = orchestrate.Run.load()  # must not raise

        gone = loaded.unit("gone")
        assert gone.task == ""
        assert "gone.task.md" in gone.note
        assert loaded.unit("kept").task == "still here"

    def test_an_existing_note_survives_the_loss(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The note about the missing file is appended, not substituted -- nothing is lost."""
        _write_raw_run(
            tmp_path,
            [
                {
                    "name": "gone",
                    "vendor": "claude",
                    "task": "",
                    "task_file": "gone.task.md",
                    "status": "pending",
                    "note": "launched by hand",
                }
            ],
        )
        monkeypatch.chdir(tmp_path)

        gone = orchestrate.Run.load().unit("gone")
        assert "launched by hand" in gone.note
        assert "gone.task.md" in gone.note


class TestCallersSeeNoDifference:
    """The whole design constraint: no caller of ``unit.task`` knows about the spill."""

    def test_reviews_separately_reads_a_spilled_task(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A regex over the task text works on the loaded run, spill or no spill."""
        monkeypatch.chdir(tmp_path)
        task = "/saga:code-review " + "r" * (orchestrate.TASK_SPILL_THRESHOLD * 2)
        _run(orchestrate, orchestrate.Unit(name="rev", vendor="claude", task=task)).save()

        assert orchestrate.Run.load().reviews_separately() is True

    def test_status_prints_a_spilled_task_like_any_other(
        self,
        orchestrate: ModuleType,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _run(orchestrate, orchestrate.Unit(name="build", vendor="claude", task=LONG_TASK)).save()

        assert orchestrate.cmd_status(argparse.Namespace()) == 0
        assert LONG_TASK[:44] in capsys.readouterr().out
