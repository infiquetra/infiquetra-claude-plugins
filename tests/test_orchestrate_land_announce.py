"""Land-time announcement: a merge that happened must be announced, whatever happens next.

Two P1 defects in ``cmd_land``, one shape -- work recorded as done when it did not happen:

(a) ``land`` merged units in a loop and announced the whole batch only AFTER the loop, so a
    conflict on a later unit returned before any announcement ran. The units that DID merge were
    classified as already landed on the next ``land``, and never announced: the board was
    permanently wrong about work that really happened. Each unit is now announced the moment its
    own merge lands, before the next merge is attempted.

(b) ``announce_units`` attempted the progress comment even when the Status field write had
    already failed, and ``land`` returned 0 having merely printed both results. A transient
    controller failure left the board stale forever, silently. A failed status write now attempts
    no comment, and a failed writeback is visible in ``land``'s own result: exit 2 (distinct from
    exit 1, a land that could not merge), the unit named, and ``announce`` named as the retry.

The controller subprocess boundary is faked, but every assertion reads the arguments actually
passed and counts the calls actually made -- both defects are about calls that did not happen.
The merges are real: the tests drive ``cmd_land`` against a temporary git repository.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable
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
CONTROLLER = (
    Path(__file__).resolve().parents[1] / "plugins" / "saga" / "scripts" / "reconcile_controller.py"
)

ISSUES = {"work-alpha": "infiquetra/orch#101", "work-beta": "infiquetra/orch#102"}


@pytest.fixture(scope="module")
def orchestrate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_orchestrate_land_announce", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------------ a fake reconcile_controller

_FLAG_ARGS = ("--op", "--repo", "--number", "--target-state", "--payload", "--repo-root")


def _options_of(argv: list[str]) -> dict[str, str]:
    """Read the controller CLI flags out of one captured argv."""
    opts: dict[str, str] = {}
    i = 0
    while i < len(argv):
        if argv[i] in _FLAG_ARGS and i + 1 < len(argv):
            opts[argv[i]] = argv[i + 1]
            i += 2
        else:
            i += 1
    return opts


class FakeReconcileController:
    """Stand-in for the ``reconcile_controller`` subprocess, with a switchable failure mode.

    Records every controller argv exactly as passed; anything that is not a controller
    invocation (git, above all) goes to the real ``subprocess.run``, so the merge under test is
    a real merge. ``fail`` is a predicate on the argv: when it holds, the call returns non-zero
    with nothing written -- the shape of the transient controller failure both defects are about.
    """

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.fail: Callable[[list[str]], bool] = lambda argv: False
        self._real_run = subprocess.run

    def __call__(self, cmd: Any, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        argv = [str(part) for part in cmd]
        if not any(part.endswith("reconcile_controller.py") for part in argv):
            return self._real_run(cmd, *args, **kwargs)
        self.calls.append(argv)
        if self.fail(argv):
            return subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr="transient controller failure"
            )
        record = {"status": "written", "key": "fake", "op_kind": _options_of(argv)["--op"]}
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(record) + "\n", stderr="")

    def ops(self) -> list[str]:
        return [_options_of(call)["--op"] for call in self.calls]

    def numbers(self) -> list[str]:
        """The issue number each call targeted -- with distinct issue refs, the unit of a call."""
        return [_options_of(call)["--number"] for call in self.calls]


@pytest.fixture
def fake_controller(monkeypatch: pytest.MonkeyPatch) -> FakeReconcileController:
    """Patch the subprocess boundary and pin the controller resolution to the real script."""
    fake = FakeReconcileController()
    monkeypatch.setattr(subprocess, "run", fake)
    assert CONTROLLER.is_file(), "saga's reconcile_controller must exist in this checkout"
    monkeypatch.setenv("ORCHESTRATE_RECONCILE_CONTROLLER", str(CONTROLLER))
    return fake


# ----------------------------------------------------------------- the repositories under test


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _commit(cwd: Path, name: str) -> None:
    (cwd / name).write_text(name + "\n")
    _git(cwd, "add", name)
    _git(cwd, "commit", "-m", f"add {name}")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A run branch plus two unit branches that cannot conflict: each adds its own file."""
    r = tmp_path / "clean-repo"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "test@example.com")
    _git(r, "config", "user.name", "Test")
    _commit(r, "base.txt")
    _git(r, "branch", "orch/r1")
    for unit in ("work-alpha", "work-beta"):
        _git(r, "checkout", "-b", f"orch/r1-{unit}", "orch/r1")
        _commit(r, f"{unit}.txt")
        _git(r, "checkout", "main")
    return r


@pytest.fixture
def conflicting_repo(tmp_path: Path) -> Path:
    """Two unit branches that rewrite the same file differently: the second merge conflicts."""
    r = tmp_path / "conflicting-repo"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "test@example.com")
    _git(r, "config", "user.name", "Test")
    _commit(r, "base.txt")
    (r / "shared.txt").write_text("base\n")
    _git(r, "add", "shared.txt")
    _git(r, "commit", "-m", "add shared.txt")
    _git(r, "branch", "orch/r1")
    for unit, content in (("work-alpha", "alpha\n"), ("work-beta", "beta\n")):
        _git(r, "checkout", "-b", f"orch/r1-{unit}", "orch/r1")
        (r / "shared.txt").write_text(content)
        _git(r, "add", "shared.txt")
        _git(r, "commit", "-m", f"{unit} rewrites shared.txt")
        _git(r, "checkout", "main")
    return r


def _write_run(repo: Path, units: list[dict[str, Any]], issues: dict[str, str] | None) -> None:
    base = subprocess.run(
        ["git", "rev-parse", "main"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    payload: dict[str, Any] = {
        "run_id": "r1",
        "source": "land-announce test",
        "base": base,
        "branch": "orch/r1",
        "units": units,
    }
    if issues is not None:
        payload["issues"] = issues
    path = repo / ".orchestrate" / "run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _unit(name: str, **over: Any) -> dict[str, Any]:
    return {
        "name": name,
        "vendor": "claude",
        "task": "x",
        "branch": f"orch/r1-{name}",
        "status": "done",
        **over,
    }


def _on(repo: Path, branch: str, path: str) -> bool:
    got = subprocess.run(
        ["git", "cat-file", "-e", f"{branch}:{path}"], cwd=repo, capture_output=True
    )
    return got.returncode == 0


def _read(repo: Path, branch: str, path: str) -> str:
    got = subprocess.run(
        ["git", "cat-file", "-p", f"{branch}:{path}"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return got.stdout


def _current_branch(repo: Path) -> str:
    got = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return got.stdout.strip()


def _fail_op(op: str) -> Callable[[list[str]], bool]:
    """A failure predicate for the fake controller: fail exactly one op kind."""
    return lambda argv: _options_of(argv)["--op"] == op


# ----------------------------------------------------------------- P1 (a): conflicts and announcements


class TestAConflictCannotUnannounceAnEarlierMerge:
    """Merge work-alpha, conflict on work-beta: alpha's announcement must survive the return."""

    def test_the_first_unit_is_announced_before_the_conflict_is_hit(
        self,
        orchestrate: ModuleType,
        conflicting_repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(conflicting_repo, [_unit("work-alpha"), _unit("work-beta")], ISSUES)
        monkeypatch.chdir(conflicting_repo)
        orchestrate.cmd_land(argparse.Namespace())

        # Exactly alpha's two writes, in order, and nothing was ever attempted for beta.
        assert fake_controller.ops() == ["set-field-status", "issue-progress-comment"]
        assert fake_controller.numbers() == ["101", "101"]
        comment_opts = _options_of(fake_controller.calls[1])
        assert comment_opts["--target-state"] == "orchestrate:r1:work-alpha:Active/Implementing"
        assert "work-alpha" in json.loads(comment_opts["--payload"])["body"]

    def test_the_announcement_survives_the_nonzero_return(
        self,
        orchestrate: ModuleType,
        conflicting_repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(conflicting_repo, [_unit("work-alpha"), _unit("work-beta")], ISSUES)
        monkeypatch.chdir(conflicting_repo)
        rc = orchestrate.cmd_land(argparse.Namespace())

        assert rc == 1, "the conflict still fails the land"
        assert len(fake_controller.calls) == 2, "alpha's writes happened despite the return 1"
        # Alpha's merge is on the run branch, the conflict is named, and the tree is restored.
        assert _read(conflicting_repo, "orch/r1", "shared.txt") == "alpha\n"
        out = capsys.readouterr().out
        assert "CONFLICT landing work-beta" in out
        assert "git merge --no-ff orch/r1-work-beta" in out
        assert _current_branch(conflicting_repo) == "main"

    def test_rerunning_land_does_not_double_announce_the_first_unit(
        self,
        orchestrate: ModuleType,
        conflicting_repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(conflicting_repo, [_unit("work-alpha"), _unit("work-beta")], ISSUES)
        monkeypatch.chdir(conflicting_repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 1
        assert len(fake_controller.calls) == 2
        capsys.readouterr()

        # Alpha is now already-landed, so the second land re-classifies it and calls nothing;
        # beta still conflicts. Were the first land's announcement lost, nothing would re-drive it.
        assert orchestrate.cmd_land(argparse.Namespace()) == 1
        assert len(fake_controller.calls) == 2, "no new controller calls for an announced unit"
        assert "board writeback work-alpha" not in capsys.readouterr().out


# ----------------------------------------------------------------- P1 (b): failed writeback, failed land


class TestAFailedStatusWriteAttemptsNoComment:
    """One failure is a failure; a comment describing a write that did not happen is worse."""

    def test_no_progress_comment_is_attempted(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_controller.fail = _fail_op("set-field-status")
        _write_run(repo, [_unit("work-alpha")], {"work-alpha": "infiquetra/orch#101"})
        monkeypatch.chdir(repo)
        rc = orchestrate.cmd_land(argparse.Namespace())

        assert rc == 2
        assert fake_controller.ops() == ["set-field-status"], "the comment must not be attempted"
        assert fake_controller.numbers() == ["101"]

    def test_the_failed_writeback_does_not_block_the_merge(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_controller.fail = _fail_op("set-field-status")
        _write_run(repo, [_unit("work-alpha")], {"work-alpha": "infiquetra/orch#101"})
        monkeypatch.chdir(repo)
        orchestrate.cmd_land(argparse.Namespace())

        assert _on(repo, "orch/r1", "work-alpha.txt"), "the code is landed; only the claim failed"
        assert _current_branch(repo) == "main"


class TestAFailedWritebackIsVisibleInLandsResult:
    """The failure is in the result itself: a distinct exit status and the unit named."""

    def test_the_failed_unit_is_named_with_its_retry(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        fake_controller.fail = lambda argv: True
        _write_run(repo, [_unit("work-alpha")], {"work-alpha": "infiquetra/orch#101"})
        monkeypatch.chdir(repo)
        rc = orchestrate.cmd_land(argparse.Namespace())

        assert rc == 2
        out = capsys.readouterr().out
        assert "BOARD WRITEBACK FAILED: work-alpha (infiquetra/orch#101)" in out
        assert "orchestrate.py announce work-alpha" in out

    def test_a_failed_comment_write_is_reported_the_same_way(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        fake_controller.fail = _fail_op("issue-progress-comment")
        _write_run(repo, [_unit("work-alpha")], {"work-alpha": "infiquetra/orch#101"})
        monkeypatch.chdir(repo)
        rc = orchestrate.cmd_land(argparse.Namespace())

        assert rc == 2
        assert fake_controller.ops() == ["set-field-status", "issue-progress-comment"]
        assert "BOARD WRITEBACK FAILED: work-alpha" in capsys.readouterr().out

    def test_a_merge_failure_and_a_writeback_failure_are_tellable_apart(
        self,
        orchestrate: ModuleType,
        repo: Path,
        conflicting_repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # A land that failed to merge returns 1, even with a working controller.
        _write_run(conflicting_repo, [_unit("work-alpha"), _unit("work-beta")], ISSUES)
        monkeypatch.chdir(conflicting_repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 1

        # A land whose merges all landed but whose writeback failed returns 2, not 1 and not 0.
        fake_controller.fail = lambda argv: True
        _write_run(repo, [_unit("work-alpha")], {"work-alpha": "infiquetra/orch#101"})
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 2


class TestALaterLandDoesNotSilentlyRedriveAFailedWriteback:
    """The retry door is `announce`, named at the failure: a next land owes nothing."""

    def test_a_second_land_calls_nothing_and_succeeds(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        fake_controller.fail = lambda argv: True
        _write_run(repo, [_unit("work-alpha")], {"work-alpha": "infiquetra/orch#101"})
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 2
        assert len(fake_controller.calls) == 1

        capsys.readouterr()
        assert orchestrate.cmd_land(argparse.Namespace()) == 0
        assert len(fake_controller.calls) == 1, "the failed writeback is announced, not re-driven"
        assert "already there: work-alpha" in capsys.readouterr().out


# ----------------------------------------------------------------- the unchanged happy paths


class TestANormalLandAnnouncesOncePerLandedUnit:
    def test_exactly_one_status_write_and_one_comment_per_unit(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("work-alpha"), _unit("work-beta")], ISSUES)
        monkeypatch.chdir(repo)
        rc = orchestrate.cmd_land(argparse.Namespace())

        assert rc == 0
        assert fake_controller.ops() == [
            "set-field-status",
            "issue-progress-comment",
            "set-field-status",
            "issue-progress-comment",
        ]
        assert fake_controller.numbers() == ["101", "101", "102", "102"]
        comment_states = [
            _options_of(call)["--target-state"]
            for call in fake_controller.calls
            if _options_of(call)["--op"] == "issue-progress-comment"
        ]
        assert comment_states == [
            "orchestrate:r1:work-alpha:Active/Implementing",
            "orchestrate:r1:work-beta:Active/Implementing",
        ]
        assert _on(repo, "orch/r1", "work-alpha.txt")
        assert _on(repo, "orch/r1", "work-beta.txt")


class TestARunWithNoIssuesStillLandsUnchanged:
    def test_land_merges_and_announces_nothing(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("work-alpha"), _unit("work-beta")], issues=None)
        monkeypatch.chdir(repo)
        rc = orchestrate.cmd_land(argparse.Namespace())

        assert rc == 0
        assert fake_controller.calls == []
        assert _on(repo, "orch/r1", "work-alpha.txt")
        assert _on(repo, "orch/r1", "work-beta.txt")
