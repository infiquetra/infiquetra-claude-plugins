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
import re
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


def _assignments_of(argv: list[str]) -> list[tuple[str, str]]:
    """The ``(field, option)`` assignments one captured controller argv submits.

    Absent an ``assignments`` payload this is the single ``Status`` write the path made before the
    pair existed, which is the same fallback ``board_progression.normalize_assignments`` applies."""
    opts = _options_of(argv)
    raw = json.loads(opts.get("--payload", "{}")).get("assignments")
    if not raw:
        return [("Status", opts["--target-state"])]
    return [(str(field), str(option)) for field, option in raw]


def _key_of(argv: list[str]) -> str:
    """The idempotency key these arguments produce -- the certificate's recipe, rebuilt here.

    ``reversibility_certificate.idempotency_key`` is ``{op}:{repo}#{number}:{target_state}``, and
    for ``set-field-status`` it carries the field name too. Since #927 the field and the value are
    the WHOLE submission's identity (``board_progression.assignment_identity``), so a
    ``(Stage, Status)`` pair and a ``Status``-only write to the same option get different keys
    instead of colliding on one and skipping the second as already-applied.

    Keying the fake's ledger on this means a second call with the same arguments skips, and any
    drift in what orchestrate passes -- a timestamp in the discriminator, a renamed flag -- turns
    into a second write the tests would see."""
    opts = _options_of(argv)
    stem = f"{opts['--op']}:{opts['--repo']}#{opts['--number']}"
    if opts["--op"] != "set-field-status":
        return f"{stem}:{opts['--target-state']}"
    assignments = _assignments_of(argv)
    fields = "+".join(field for field, _ in assignments)
    options = "+".join(option for _, option in assignments)
    return f"{stem}:{fields}:{options}"


def _identity_of(argv: list[str]) -> dict[str, str]:
    """The `field` identity the REAL controller records for this argv.

    `board_progression.assignment_identity` joins a submission's field names, sorted, with `+`, and
    both key-minting sites put the result in the record's `field`. Orchestrate reads it back to
    prove the saga that EXECUTED the call carried both halves: a saga older than the pair contract
    drops `payload["assignments"]`, writes `--field Status` alone, and still reports `written`. A
    fake that omitted `field` reproduced that older saga exactly, so it agreed with the defect.
    """
    opts = _options_of(argv)
    if opts.get("--op") != "set-field-status":
        return {}
    assignments = json.loads(opts.get("--payload", "{}") or "{}").get("assignments")
    if not assignments:
        return {"field": "Status"}
    return {"field": "+".join(sorted(str(field) for field, _option in assignments))}


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
        # Swappable so a test can stand in a saga that predates the pair contract -- the one thing
        # this fake cannot reproduce by argument alone, because it is a property of the executor.
        self.identity_of: Callable[[list[str]], dict[str, str]] = _identity_of
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
            record = {"status": "skipped", "key": key, **self.identity_of(argv)}
        else:
            ledger_file.parent.mkdir(parents=True, exist_ok=True)
            ledger_file.write_text(json.dumps({"key": key}))
            record = {"status": "written", "key": key, **self.identity_of(argv)}
            repo, number = opts["--repo"], int(opts["--number"])
            if opts["--op"] == "set-field-status":
                # BOTH assignments are recorded, not just the target-state. A test that reads one
                # field passes on a half-write: `Ready for Active` is a legal Status on its own, so
                # a Status-only submission looks like success while Stage stays where it was.
                self.status_writes.append(
                    {"repo": repo, "number": number, "assignments": _assignments_of(argv)}
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
    status_map: dict[str, Any] | None = None,
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
    """A unit's name prefix lands its card on a live rung; the run's map overrides key by key."""

    def test_the_default_prefixes(self, orchestrate: ModuleType) -> None:
        assert orchestrate.mapped_status("plan-interview") == ("Planning", "Designing")
        assert orchestrate.mapped_status("docreview-pass") == ("Planning", "Ready for Active")
        assert orchestrate.mapped_status("work-52-build") == ("Active", "Implementing")
        assert orchestrate.mapped_status("fix-52-claude") == ("Active", "Implementing")
        assert orchestrate.mapped_status("codereview-52") == ("Active", "Code review")
        # `landed` is retired, so it takes the ordinary unmapped path rather than a rung.
        assert orchestrate.mapped_status("landed-52") is None

    def test_the_bare_prefix_is_a_unit_name_too(self, orchestrate: ModuleType) -> None:
        assert orchestrate.mapped_status("plan") == ("Planning", "Designing")

    def test_matching_stops_at_a_word_boundary(self, orchestrate: ModuleType) -> None:
        """A bare string prefix would make ``planner-notes`` a plan phase; it is not."""
        assert orchestrate.mapped_status("planner-notes") is None
        assert orchestrate.mapped_status("settle-debounce") is None

    def test_the_status_map_overrides_key_by_key(self, orchestrate: ModuleType) -> None:
        overrides = {"work": ["Active", "Integrating"]}
        assert orchestrate.mapped_status("work-52-build", overrides) == ("Active", "Integrating")
        assert orchestrate.mapped_status("plan-interview", overrides) == ("Planning", "Designing")

    def test_a_specific_name_beats_a_shorter_prefix(self, orchestrate: ModuleType) -> None:
        overrides = {
            "work-52-build": ["Active", "Ready to merge"],
            "work": ["Active", "Integrating"],
        }
        assert orchestrate.mapped_status("work-52-build", overrides) == ("Active", "Ready to merge")

    def test_a_pre_pair_string_override_fails_loud(self, orchestrate: ModuleType) -> None:
        """A run file written before #927 holds a bare Status string. That is not a rung, and
        returning None for it would turn a stale configuration into a silent no-announce."""
        with pytest.raises(ValueError, match="not a \\(Stage, Status\\) pair"):
            orchestrate.mapped_status("work-52-build", {"work": "Ready"})

    def test_the_defaults_never_leave_the_live_vocabulary(self, orchestrate: ModuleType) -> None:
        """Re-aimed from the hard-coded ladder at the board's own authority. The assertion is not
        weaker -- it still fails on an invented rung -- it now fails on a STALE one too, which the
        ladder could not, because the ladder was itself the stale copy."""
        live = orchestrate.live_rungs()
        assert live, "mission-control's schema must resolve from this checkout"
        off = [
            (key, rung)
            for key, rung in orchestrate.DEFAULT_STATUS_MAP.items()
            if tuple(rung) not in live
        ]
        assert off == [], f"rungs the board does not carry: {off}"

    def test_the_rungs_never_move_a_card_backwards(self, orchestrate: ModuleType) -> None:
        """Ladder order plan -> docreview -> work -> fix -> codereview -> landed must be
        non-decreasing in the schema's own stage order, or a boundary un-advances the card."""
        stages = list(orchestrate.stage_statuses())
        order = ["plan", "docreview", "work", "fix", "codereview"]
        indices = [stages.index(orchestrate.DEFAULT_STATUS_MAP[key][0]) for key in order]
        assert indices == sorted(indices), (
            f"a rung moves the card backwards: {dict(zip(order, indices, strict=True))}"
        )

    def test_no_rung_reaches_verify_or_retro(self, orchestrate: ModuleType) -> None:
        """Neither stage is reachable, because Orchestrate can check neither W-D2 conjunct.

        `cmd_land` merges onto the run branch rather than the default branch, and the module carries
        no deployment or artifact-verification signal, so a gate on the rule would be permanently
        false. `landed` is retired for that reason; `codereview` was remapped for the same one.
        """
        offenders = {
            key: rung
            for key, rung in orchestrate.DEFAULT_STATUS_MAP.items()
            if rung[0] in ("Verify", "Retro")
        }
        assert offenders == {}, f"rungs reaching a post-merge stage: {offenders}"
        assert "landed" not in orchestrate.DEFAULT_STATUS_MAP

    def test_no_retired_token_survives_in_the_module(self, orchestrate: ModuleType) -> None:
        """``Idea``, ``Ready`` and ``Done`` are options on neither live field."""
        source = Path(orchestrate.__file__ or SCRIPT).read_text()
        assert not re.search(r'"(Idea|Ready|Done)"', source), (
            "a retired board token survives in orchestrate.py"
        )
        assert not hasattr(orchestrate, "STATUS_LADDER"), (
            "the hard-coded ladder is replaced by the resolved vocabulary, not kept beside it"
        )

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
            "assignments": [("Stage", "Active"), ("Status", "Implementing")],
        }
        assert len(fake_controller.comment_writes) == 1
        comment = fake_controller.comment_writes[0]
        assert comment["repo"] == "infiquetra/orch"
        assert comment["number"] == 52
        assert "work-alpha" in comment["body"], "the comment must name what happened"
        assert "board stage: Active" in comment["body"]
        assert "board status: Implementing" in comment["body"]
        assert "board writeback work-alpha -> Active/Implementing" in capsys.readouterr().out

    def test_the_arguments_carry_the_issue_and_both_halves_of_the_rung(
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
        # --target-state names the Status half, because that is the field the controller can read
        # back for its drift check; the payload carries the whole pair.
        assert status_opts["--target-state"] == "Implementing"
        assert json.loads(status_opts["--payload"])["assignments"] == [
            ["Stage", "Active"],
            ["Status", "Implementing"],
        ]
        assert Path(status_opts["--repo-root"]).resolve() == repo.resolve()

        comment_opts = _options_of(fake_controller.calls[1])
        assert comment_opts["--op"] == "issue-progress-comment"
        # A stable discriminator, so a re-driven boundary meets the key it already wrote.
        assert comment_opts["--target-state"] == "orchestrate:r1:work-alpha:Active/Implementing"
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
            status_map={"work": ["Active", "Integrating"]},
        )
        monkeypatch.chdir(repo)
        assert orchestrate.cmd_land(argparse.Namespace()) == 0
        assert fake_controller.status_writes == [
            {
                "repo": "infiquetra/orch",
                "number": 52,
                "assignments": [("Stage", "Active"), ("Status", "Integrating")],
            }
        ]

    def test_a_rung_the_board_does_not_carry_fails_loud(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An unresolvable rung is a FAILURE record, never a skip.

        Skipping is how six stale rungs stayed invisible: every board write this file made halted
        in front of mission-control's writer and the run said nothing about it."""
        _write_run(
            repo,
            [_unit("work-alpha")],
            issues={"work-alpha": "infiquetra/orch#52"},
            status_map={"work": ["Active", "Invented status"]},
        )
        monkeypatch.chdir(repo)
        r = orchestrate.Run.load()
        records = orchestrate.announce_units(r, ["work-alpha"])
        assert fake_controller.calls == [], "an unresolvable rung must not reach the controller"
        assert "skipped" not in records[0]
        assert records[0]["writes"][0]["status"] == "failed"
        assert (
            "is not a live (Stage, Status) option combination" in records[0]["writes"][0]["error"]
        )
        assert orchestrate._failed_writebacks(records) == records

    def test_a_pre_pair_override_fails_loud_rather_than_half_writing(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A run file carrying the pre-#927 single-string override submits nothing at all."""
        _write_run(
            repo,
            [_unit("work-alpha")],
            issues={"work-alpha": "infiquetra/orch#52"},
            status_map={"work": "Ready"},
        )
        monkeypatch.chdir(repo)
        r = orchestrate.Run.load()
        records = orchestrate.announce_units(r, ["work-alpha"])
        assert fake_controller.calls == []
        assert records[0]["writes"][0]["status"] == "failed"
        assert "not a (Stage, Status) pair" in records[0]["writes"][0]["error"]

    def test_an_unresolvable_schema_fails_loud_on_stderr(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        """No schema means no way to tell a live rung from an invented one -- and that is a FAILURE.

        An earlier form recorded a skip here. `report_announcements` prints a skip only under
        `verbose`, both `cmd_land` call sites pass the default False, and `_failed_writebacks`
        excludes skips by design -- so `land` wrote nothing to any board, printed nothing about it,
        and exited 0. That is the same silence this whole change exists to end, one layer up.
        """
        monkeypatch.setenv("ORCHESTRATE_SDLC_SCHEMA", str(tmp_path / "no-such-schema.json"))
        _write_run(repo, [_unit("work-alpha")], issues={"work-alpha": "infiquetra/orch#52"})
        monkeypatch.chdir(repo)
        r = orchestrate.Run.load()
        records = orchestrate.announce_units(r, ["work-alpha"])

        assert fake_controller.calls == [], "no rung can be validated, so nothing is submitted"
        assert "skipped" not in records[0], "a skip is invisible and exits 0; this must not be one"
        assert records[0]["writes"][0]["status"] == "failed"
        assert "not resolvable" in records[0]["writes"][0]["error"]
        assert orchestrate._failed_writebacks(records) == records, "land must exit non-zero"
        assert "sdlc-schema.json is not resolvable" in capsys.readouterr().err, (
            "the sibling missing-controller branch prints unconditionally; so must this one"
        )

    def test_a_saga_too_old_to_execute_the_pair_is_caught(
        self,
        orchestrate: ModuleType,
        repo: Path,
        fake_controller: FakeReconcileController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The pair's one uncloseable door: Orchestrate does not run the saga, it shells out to it.

        A saga older than the pair contract has no `normalize_assignments`. It ignores
        `payload["assignments"]`, builds `--field Status --option <status>` alone, mints the
        pre-pair single-field key and returns `written` -- so every downstream signal agrees the
        move landed while `Stage` never moved, the progress comment asserts a `board stage:` line
        for it, and `land` exits 0. The record carried the discriminator all along and nothing read
        it: `field` is the composite identity from a pair-aware saga, the bare readable field from
        an older one.
        """

        def _old_saga(argv: list[str]) -> dict[str, str]:
            opts = _options_of(argv)
            return {"field": "Status"} if opts.get("--op") == "set-field-status" else {}

        monkeypatch.setattr(fake_controller, "identity_of", _old_saga)
        _write_run(repo, [_unit("work-alpha")], issues={"work-alpha": "infiquetra/orch#52"})
        monkeypatch.chdir(repo)
        r = orchestrate.Run.load()
        records = orchestrate.announce_units(r, ["work-alpha"])

        status_write = records[0]["writes"][0]
        assert status_write["status"] == "failed", "a half-executed pair must not report success"
        assert "predates" in status_write["error"]
        assert status_write["retryable"] is False, "a retry cannot fix an old install"
        assert len(records[0]["writes"]) == 1, "and the progress comment must NOT be posted"
        assert fake_controller.comment_writes == []
        assert orchestrate._failed_writebacks(records) == records

    def test_a_pair_aware_saga_records_the_identity_orchestrate_expects(
        self, orchestrate: ModuleType, tmp_path: Path
    ) -> None:
        """`pair_identity` is a restatement of saga's own helper; drive the REAL one and compare.

        Orchestrate cannot import `board_progression` -- saga is a separate plugin resolved at
        runtime and may be absent -- so the shape is restated. This is what stops the restatement
        drifting away from the function it mirrors.
        """
        spec = importlib.util.spec_from_file_location(
            "_bp_for_identity",
            Path(__file__).resolve().parents[1]
            / "plugins"
            / "saga"
            / "scripts"
            / "board_progression.py",
        )
        assert spec is not None and spec.loader is not None
        bp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bp)

        rung = ("Active", "Implementing")
        field, _state = bp.assignment_identity([("Stage", rung[0]), ("Status", rung[1])])
        assert field == orchestrate.pair_identity(rung)
        # And order-independently, because the identity names the move, not the typing order.
        reversed_field, _ = bp.assignment_identity([("Status", rung[1]), ("Stage", rung[0])])
        assert reversed_field == field

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


class TestTheSchemaResolverAndItsReporting:
    """The resolution and reporting branches the cycle-2 review found untested."""

    def test_a_corrupt_schema_falls_through_rather_than_raising(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Malformed JSON is a broken install, not a crash in the middle of a land."""
        broken = tmp_path / "broken-schema.json"
        broken.write_text("{ not json at all", encoding="utf-8")
        monkeypatch.setenv("ORCHESTRATE_SDLC_SCHEMA", str(broken))
        assert orchestrate.stage_statuses() == {}
        assert orchestrate.live_rungs() == set()

    def test_a_schema_with_the_wrong_shape_resolves_to_nothing(
        self, orchestrate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Valid JSON carrying no stage_statuses block is not a vocabulary."""
        wrong = tmp_path / "wrong-shape.json"
        wrong.write_text(json.dumps({"workflows": {"stage_flow": {}}}), encoding="utf-8")
        monkeypatch.setenv("ORCHESTRATE_SDLC_SCHEMA", str(wrong))
        assert orchestrate.stage_statuses() == {}

    def test_installs_are_ordered_by_version_not_by_string(self, orchestrate: ModuleType) -> None:
        """Lexicographic ordering put 0.136.0 ahead of every later release.

        This resolver decides which saga executes every board submission Orchestrate makes, and a
        saga older than the pair contract drops the assignments payload silently. Sixty saga copies
        are installed across two plugin roots on the machine this was measured on.
        """
        ranked = sorted(
            [
                Path("/c/saga/0.9.0/scripts/reconcile_controller.py"),
                Path("/c/saga/0.10.0/scripts/reconcile_controller.py"),
                Path("/c/saga/0.136.0/scripts/reconcile_controller.py"),
                Path("/c/saga/0.151.0/scripts/reconcile_controller.py"),
            ],
            key=lambda path: (orchestrate._version_rank(path), str(path)),
            reverse=True,
        )
        assert ranked[0].parts[-3] == "0.151.0"
        assert [path.parts[-3] for path in ranked] == ["0.151.0", "0.136.0", "0.10.0", "0.9.0"]
        assert orchestrate._version_rank(Path("/c/saga/scripts/x.py")) == ()

    def test_the_company_plugin_root_is_searched(self, orchestrate: ModuleType) -> None:
        """`~/.claude-company` is a SECOND plugin tree beside `~/.claude`, not a symlink to it."""
        patterns = " ".join(orchestrate._INSTALL_PATTERNS)
        assert "~/.claude-company/" in patterns
        assert "~/.claude/" in patterns

    def test_a_failure_reason_is_printed_not_just_its_status(
        self, orchestrate: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The reason was always built and never printed, so a failure read as one bare word."""
        records = [
            {
                "unit": "work-alpha",
                "issue": "infiquetra/orch#52",
                "status": "Active/Implementing",
                "writes": [
                    {
                        "status": "failed",
                        "op_kind": "set-field-status",
                        "retryable": False,
                        "error": "the rung is not a live option combination",
                    }
                ],
            }
        ]
        orchestrate.report_announcements(records)
        out = capsys.readouterr().out
        assert "board writeback work-alpha -> Active/Implementing" in out
        assert "the rung is not a live option combination" in out

    def test_the_retry_door_is_named_only_when_a_retry_can_clear_it(
        self, orchestrate: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`announce` is idempotency-keyed, so a repeat is safe -- but safe is not a remedy."""
        stuck = {
            "unit": "work-alpha",
            "issue": "infiquetra/orch#52",
            "status": "Active/Implementing",
            "writes": [
                {"status": "failed", "retryable": False, "error": "the installed saga is too old"}
            ],
        }
        transient = {
            "unit": "work-beta",
            "issue": "infiquetra/orch#53",
            "status": "Active/Implementing",
            "writes": [{"status": "failed", "error": "transient controller failure"}],
        }
        orchestrate._report_failed_writebacks([stuck, transient])
        out = capsys.readouterr().out
        assert "the installed saga is too old" in out
        assert "a retry cannot clear this on its own" in out
        assert "orchestrate.py announce work-beta" in out
        assert "orchestrate.py announce work-alpha" not in out
