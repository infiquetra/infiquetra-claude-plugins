"""Board writeback: a run's phase boundaries land on its issues' board cards, or not at all.

The observed failure this exists for: a 75-unit run crossed nine phases while the card for issue 52
never left status ``Idea`` and received zero comments -- the write was allowlisted and
idempotency-keyed the whole time, and was simply never called. So the run file may carry an
``issues`` mapping (unit name -> ``owner/repo#N``), ``land`` announces the units it just merged,
and every write goes through saga's ``reconcile_controller`` -- never a second door to GitHub.

The controller subprocess is faked, but the fake is faithful to the one contract that matters
here: one write per idempotency key, with the key assembled from the ARGUMENTS exactly the way
saga's ``reversibility_certificate.idempotency_key`` does. Every assertion reads what orchestrate
actually passed, not that a mock was waved at. The merging tests drive ``cmd_land`` against a real
git repository, the way ``test_orchestrate_launch_and_land`` does, because the merge is what the
writeback hangs off.
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
CONTROLLER = (
    Path(__file__).resolve().parents[1] / "plugins" / "saga" / "scripts" / "reconcile_controller.py"
)


@pytest.fixture(scope="module")
def orchestrate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_orchestrate_board_writeback", SCRIPT)
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


def _key_of(argv: list[str]) -> str:
    """The idempotency key these arguments produce -- the certificate's recipe, rebuilt here.

    ``reversibility_certificate.idempotency_key`` is ``{op}:{repo}#{number}:{target_state}``.
    Keying the fake's ledger on this means a second call with the same arguments skips, and any
    drift in what orchestrate passes -- a timestamp in the discriminator, a renamed flag -- turns
    into a second write the tests would see."""
    opts = _options_of(argv)
    return f"{opts['--op']}:{opts['--repo']}#{opts['--number']}:{opts['--target-state']}"


class FakeReconcileController:
    """Stand-in for the ``reconcile_controller`` subprocess, driven entirely by its arguments.

    Implements the controller's load-bearing contract -- authorize, then one write per
    idempotency key, keyed into a ledger so a repeat is a skip -- without any of saga's other
    machinery. Anything that is not a controller invocation (git, above all) goes to the real
    ``subprocess.run``, so the merge under test is a real merge."""

    def __init__(self, ledger_dir: Path) -> None:
        self.ledger_dir = ledger_dir
        self.calls: list[list[str]] = []
        self.status_writes: list[dict[str, Any]] = []
        self.comment_writes: list[dict[str, Any]] = []
        self._real_run = subprocess.run

    def __call__(self, cmd: Any, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        argv = [str(part) for part in cmd]
        if not any(part.endswith("reconcile_controller.py") for part in argv):
            return self._real_run(cmd, *args, **kwargs)
        self.calls.append(argv)
        opts = _options_of(argv)
        key = _key_of(argv)
        ledger_file = self.ledger_dir / (
            key.replace(":", "_").replace("#", "_").replace("/", "_") + ".json"
        )
        if ledger_file.exists():
            record = {"status": "skipped", "key": key}
        else:
            ledger_file.parent.mkdir(parents=True, exist_ok=True)
            ledger_file.write_text(json.dumps({"key": key}))
            record = {"status": "written", "key": key}
            repo, number = opts["--repo"], int(opts["--number"])
            if opts["--op"] == "set-field-status":
                self.status_writes.append(
                    {"repo": repo, "number": number, "status": opts["--target-state"]}
                )
            elif opts["--op"] == "issue-progress-comment":
                body = json.loads(opts.get("--payload", "{}")).get("body", "")
                self.comment_writes.append({"repo": repo, "number": number, "body": body})
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(record) + "\n", stderr="")


@pytest.fixture
def fake_controller(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeReconcileController:
    """Patch the subprocess boundary and pin the controller resolution to the real script."""
    fake = FakeReconcileController(tmp_path / "board-progression-ledger")
    monkeypatch.setattr(subprocess, "run", fake)
    assert CONTROLLER.is_file(), "saga's reconcile_controller must exist in this checkout"
    monkeypatch.setenv("ORCHESTRATE_RECONCILE_CONTROLLER", str(CONTROLLER))
    return fake


# ----------------------------------------------------------------- the repository under test


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _commit(cwd: Path, name: str) -> None:
    (cwd / name).write_text(name + "\n")
    _git(cwd, "add", name)
    _git(cwd, "commit", "-m", f"add {name}")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A run branch plus one unit branch per name, each with one commit of its own."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "test@example.com")
    _git(r, "config", "user.name", "Test")
    _commit(r, "base.txt")
    _git(r, "branch", "orch/r1")
    for unit in ("work-alpha", "settle-gamma"):
        _git(r, "checkout", "-b", f"orch/r1-{unit}", "orch/r1")
        _commit(r, f"{unit}.txt")
        _git(r, "checkout", "main")
    return r


def _write_run(
    repo: Path,
    units: list[dict[str, Any]],
    issues: dict[str, str] | None = None,
    status_map: dict[str, str] | None = None,
) -> None:
    base = subprocess.run(
        ["git", "rev-parse", "main"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    payload: dict[str, Any] = {
        "run_id": "r1",
        "source": "board writeback test",
        "base": base,
        "branch": "orch/r1",
        "units": units,
    }
    if issues is not None:
        payload["issues"] = issues
    if status_map is not None:
        payload["status_map"] = status_map
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


# ----------------------------------------------------------------- the status mapping


class TestStatusMapping:
    """A unit's name prefix lands its card on the ladder; the run's map overrides key by key."""

    def test_the_default_prefixes(self, orchestrate: ModuleType) -> None:
        assert orchestrate.mapped_status("plan-interview") == "Shaping"
        assert orchestrate.mapped_status("docreview-pass") == "Shaping"
        assert orchestrate.mapped_status("work-52-build") == "Active"
        assert orchestrate.mapped_status("fix-52-claude") == "Active"
        assert orchestrate.mapped_status("codereview-52") == "Verify"
        assert orchestrate.mapped_status("landed-52") == "Done"

    def test_the_bare_prefix_is_a_unit_name_too(self, orchestrate: ModuleType) -> None:
        assert orchestrate.mapped_status("plan") == "Shaping"

    def test_matching_stops_at_a_word_boundary(self, orchestrate: ModuleType) -> None:
        """A bare string prefix would make ``planner-notes`` a plan phase; it is not."""
        assert orchestrate.mapped_status("planner-notes") is None
        assert orchestrate.mapped_status("settle-debounce") is None

    def test_the_status_map_overrides_key_by_key(self, orchestrate: ModuleType) -> None:
        overrides = {"work": "Ready"}
        assert orchestrate.mapped_status("work-52-build", overrides) == "Ready"
        assert orchestrate.mapped_status("plan-interview", overrides) == "Shaping"

    def test_a_specific_name_beats_a_shorter_prefix(self, orchestrate: ModuleType) -> None:
        overrides = {"work-52-build": "Done", "work": "Verify"}
        assert orchestrate.mapped_status("work-52-build", overrides) == "Done"

    def test_the_defaults_never_leave_the_ladder(self, orchestrate: ModuleType) -> None:
        assert set(orchestrate.DEFAULT_STATUS_MAP.values()) <= set(orchestrate.STATUS_LADDER)

    def test_issue_refs_split_into_repo_and_number(self, orchestrate: ModuleType) -> None:
        assert orchestrate.parse_issue_ref("infiquetra/orch#52") == ("infiquetra/orch", 52)
        assert orchestrate.parse_issue_ref("not-an-issue-ref") is None
        assert orchestrate.parse_issue_ref("owner/repo#") is None


class TestNoIssuesMeansNoWrite:
    """Absent mapping: the run writes nothing, and nothing about the existing flow changes."""

    def test_land_merges_but_writes_nothing(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("work-alpha")])  # run.json carries no `issues` key at all
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 0

        assert fake_controller.calls == []
        assert _on(repo, "orch/r1", "work-alpha.txt"), "land itself must be unaffected"

    def test_announce_is_a_noop(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(repo, [_unit("work-alpha")])
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_announce(argparse.Namespace(units=["work-alpha"])) == 0
        assert fake_controller.calls == []
        assert "no `issues` mapping" in capsys.readouterr().out

    def test_a_run_file_from_before_the_field_still_loads(
        self, orchestrate: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A run.json written before this feature has neither field; both default to nothing."""
        _write_run(repo, [_unit("work-alpha")])
        monkeypatch.chdir(repo)
        r = orchestrate.Run.load()
        assert r.issues == {}
        assert r.status_map == {}
        r.save()
        payload = json.loads((repo / ".orchestrate" / "run.json").read_text())
        assert payload["issues"] == {}
        assert payload["status_map"] == {}


class TestALandedUnitAnnounces:
    """One landed unit produces one status set and one comment, through the controller's CLI."""

    def test_one_status_set_and_one_comment(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(repo, [_unit("work-alpha")], issues={"work-alpha": "infiquetra/orch#52"})
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 0

        assert len(fake_controller.status_writes) == 1
        assert fake_controller.status_writes[0] == {
            "repo": "infiquetra/orch",
            "number": 52,
            "status": "Active",
        }
        assert len(fake_controller.comment_writes) == 1
        comment = fake_controller.comment_writes[0]
        assert comment["repo"] == "infiquetra/orch"
        assert comment["number"] == 52
        assert "work-alpha" in comment["body"], "the comment must name what happened"
        assert "board writeback work-alpha -> Active" in capsys.readouterr().out

    def test_the_arguments_carry_the_issue_and_the_ladder_status(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("work-alpha")], issues={"work-alpha": "infiquetra/orch#52"})
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 0
        assert len(fake_controller.calls) == 2

        status_opts = _options_of(fake_controller.calls[0])
        assert status_opts["--op"] == "set-field-status"
        assert status_opts["--repo"] == "infiquetra/orch"
        assert status_opts["--number"] == "52"
        assert status_opts["--target-state"] == "Active"
        assert Path(status_opts["--repo-root"]).resolve() == repo.resolve()

        comment_opts = _options_of(fake_controller.calls[1])
        assert comment_opts["--op"] == "issue-progress-comment"
        # A stable discriminator, so a re-driven boundary meets the key it already wrote.
        assert comment_opts["--target-state"] == "orchestrate:r1:work-alpha:Active"
        assert "work-alpha" in json.loads(comment_opts["--payload"])["body"]

    def test_the_status_map_overrides_what_lands(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(
            repo,
            [_unit("work-alpha")],
            issues={"work-alpha": "infiquetra/orch#52"},
            status_map={"work": "Ready"},
        )
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 0
        assert fake_controller.status_writes == [
            {"repo": "infiquetra/orch", "number": 52, "status": "Ready"}
        ]

    def test_an_unmapped_prefix_announces_nothing(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _write_run(repo, [_unit("settle-gamma")], issues={"settle-gamma": "infiquetra/orch#52"})
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_announce(argparse.Namespace(units=["settle-gamma"])) == 0
        assert fake_controller.calls == []
        assert "no status mapped" in capsys.readouterr().out

    def test_a_malformed_issue_ref_is_skipped_not_fatal(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("work-alpha")], issues={"work-alpha": "not-an-issue-ref"})
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 0
        assert fake_controller.calls == []
        assert _on(repo, "orch/r1", "work-alpha.txt"), "the merge must not care about the ref"


class TestRerunsDoNotDuplicate:
    """The controller's idempotency key is what makes a second round a skip, not a second post."""

    def test_announcing_the_same_boundary_twice_posts_one_comment(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("work-alpha")], issues={"work-alpha": "infiquetra/orch#52"})
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 0
        assert orchestrate.cmd_announce(argparse.Namespace(units=["work-alpha"])) == 0

        assert len(fake_controller.comment_writes) == 1
        assert len(fake_controller.status_writes) == 1
        # Both rounds drove the boundary; the second was skipped by the ledger, not silence.
        assert len(fake_controller.calls) == 4
        assert _key_of(fake_controller.calls[1]) == _key_of(fake_controller.calls[3])
        assert _key_of(fake_controller.calls[0]) == _key_of(fake_controller.calls[2])

    def test_a_second_land_writes_nothing_new(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(repo, [_unit("work-alpha")], issues={"work-alpha": "infiquetra/orch#52"})
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 0
        assert orchestrate.cmd_land(argparse.Namespace()) == 0

        assert len(fake_controller.comment_writes) == 1
        assert len(fake_controller.status_writes) == 1
        assert len(fake_controller.calls) == 2, "nothing new landed, so nothing new was announced"


class TestAMissingControllerNeverFailsALand:
    """A machine without saga says so on stderr and carries on; the merge is the land's job."""

    def test_land_succeeds_and_says_so_on_stderr(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("ORCHESTRATE_RECONCILE_CONTROLLER", str(repo / "no-such-controller.py"))
        _write_run(repo, [_unit("work-alpha")], issues={"work-alpha": "infiquetra/orch#52"})
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 0

        assert _on(repo, "orch/r1", "work-alpha.txt"), "the merge must happen regardless"
        assert fake_controller.calls == []
        assert "reconcile_controller" in capsys.readouterr().err

    def test_announce_succeeds_too(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("ORCHESTRATE_RECONCILE_CONTROLLER", str(repo / "no-such-controller.py"))
        _write_run(repo, [_unit("work-alpha")], issues={"work-alpha": "infiquetra/orch#52"})
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_announce(argparse.Namespace(units=["work-alpha"])) == 0
        assert fake_controller.calls == []
        assert "not importable" in capsys.readouterr().err


class TestControllerResolution:
    def test_the_env_override_points_at_the_script(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        script = tmp_path / "reconcile_controller.py"
        script.write_text("# stand-in\n")
        monkeypatch.setenv("ORCHESTRATE_RECONCILE_CONTROLLER", str(script))
        assert orchestrate.reconcile_controller_path() == script

    def test_a_missing_env_override_is_not_importable(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ORCHESTRATE_RECONCILE_CONTROLLER", str(tmp_path / "missing.py"))
        assert orchestrate.reconcile_controller_path() is None

    def test_the_repo_layout_resolves_without_any_env(
        self, orchestrate: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """This checkout ships the saga plugin beside the orchestrate plugin."""
        monkeypatch.delenv("ORCHESTRATE_RECONCILE_CONTROLLER", raising=False)
        path = orchestrate.reconcile_controller_path()
        assert path is not None
        assert path.name == "reconcile_controller.py"
