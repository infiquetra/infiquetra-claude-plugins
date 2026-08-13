"""Contract tests for orchestrate U5 completion behavior.

Every test here crosses the boundaries this unit actually owns: a real Git repository, real
files, and real subprocesses for predicate execution. The only hand-authored boundary is Herdr,
which this unit touches solely through U4's already-tested reap path.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "orchestrate" / "skills" / "orchestrate" / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REGISTER = _load("register")
_load("herdr_events")
SUBSCRIBER = _load("subscriber")
LIFECYCLE = _load("session_lifecycle")
COMPLETION = _load("completion")


# --------------------------------------------------------------------------- fixtures


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _init_repo(repo: Path, *, ignore_orchestrate: bool = True) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.com")
    _git(repo, "config", "user.name", "Tests")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    ignore = "__pycache__/\n"
    if ignore_orchestrate:
        ignore = ".orchestrate/\n" + ignore
    (repo / ".gitignore").write_text(ignore, encoding="utf-8")
    (repo / "checks").mkdir()
    (repo / "checks" / "helpers.py").write_text(
        "REQUIRED_KEYS = ('binding', 'conclusion')\n", encoding="utf-8"
    )
    (repo / "checks" / "check.py").write_text(
        "import json, sys\n"
        "from helpers import REQUIRED_KEYS\n"
        "payload = json.loads(open(sys.argv[1], encoding='utf-8').read())\n"
        "missing = [key for key in REQUIRED_KEYS if key not in payload]\n"
        "sys.exit(1 if missing else 0)\n",
        encoding="utf-8",
    )
    _git(repo, "add", "README.md", ".gitignore", "checks")
    _git(repo, "commit", "-q", "-m", "seed")


def _spec(**overrides: Any) -> Any:
    values: dict[str, Any] = {
        "run_id": "run-a",
        "row_id": "child-a",
        "runtime": "codex",
        "work_shape": "mechanical",
        "instruction": "Produce the deliverable.",
        "scope": ("src",),
        "mutating": False,
        "workspace": "workspace-a",
        "readiness_timeout": 0.1,
        "environment_command": (),
    }
    values.update(overrides)
    return LIFECYCLE.ChildSpec(**values)


def _predicate(*args: str, **overrides: Any) -> Any:
    argv = (sys.executable, "checks/check.py", *args)
    return COMPLETION.PredicateSpec(argv=argv, **overrides)


class _Prepared:
    def __init__(self, repo: Path, spec: Any, landing: Any, git: Any, receipt: Any) -> None:
        self.repo = repo
        self.spec = spec
        self.landing = landing
        self.git = git
        self.receipt = receipt
        self.baseline = git.changed_paths_baseline(
            landing.cwd, base_commit=landing.base_commit, ambient_root=landing.ambient_root
        )

    def write_deliverable(
        self, payload: dict[str, Any] | None = None, *, path: Path | None = None
    ) -> Path:
        """Write a complete, correctly bound deliverable to the in-flight path."""
        document = {"binding": self.receipt.binding_token, "conclusion": "done"}
        if payload is not None:
            document = payload
        target = path if path is not None else self.receipt.inflight_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document), encoding="utf-8")
        return target

    def evaluate(self, **kwargs: Any) -> Any:
        return COMPLETION.evaluate_completion(
            self.repo,
            self.spec,
            self.landing,
            self.baseline,
            self.receipt,
            git=self.git,
            **kwargs,
        )


def _prepare(
    repo: Path,
    *,
    predicate: Any | None = None,
    artifact_name: str = "report.json",
    **spec_overrides: Any,
) -> _Prepared:
    spec = _spec(**spec_overrides)
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, spec)
    REGISTER.upsert_row(
        repo, spec.row_id, {"run_id": spec.run_id, "phase": "working", "expected_state": "working"}
    )
    if predicate is None:
        artifacts = COMPLETION.artifact_landing(Path(landing.cwd), spec.run_id, spec.row_id)
        relative = artifacts.relative_to(Path(landing.cwd).resolve()) / artifact_name
        predicate = _predicate(relative.as_posix())
    receipt = COMPLETION.issue_receipt(
        repo, spec, landing, predicate, artifact_name=artifact_name, git=git
    )
    return _Prepared(repo, spec, landing, git, receipt)


class FakeHerdr:
    """The one hand-authored boundary: Herdr's tab presence and close, as U4 uses them."""

    def __init__(self) -> None:
        self.present = True
        self.closed: list[str] = []

    def tab_present(self, tab_id: str, *, cwd: Path) -> bool:
        return self.present

    def close_tab(self, tab_id: str, *, cwd: Path) -> None:
        self.closed.append(tab_id)
        self.present = False


# --------------------------------------------------------------------------- scenario 2: schema


@pytest.mark.parametrize(
    ("declaration", "match"),
    [
        ("pytest -q tests/test_x.py", "declared as text"),
        ({"argv": "pytest -q tests/test_x.py"}, "not a command string"),
        ({"argv": ["bash", "-c", "test -s report.md"]}, "is a shell"),
        ({"argv": ["/usr/bin/env", "sh", "checks/check.sh"]}, "launches another program"),
        ({"argv": ["timeout", "5", "python3", "check.py"]}, "launches another program"),
        ({"argv": ["python3", "-c", "import sys; sys.exit(0)"]}, "inline-source flag"),
        ({"argv": ["python3", "check.py"], "shell": "true"}, "unknown predicate keys"),
        ({"argv": []}, "at least the program"),
    ],
)
def test_shell_shaped_predicate_declarations_are_rejected_by_the_schema(
    declaration: Any, match: str
) -> None:
    with pytest.raises(COMPLETION.PredicateSchemaError, match=match):
        COMPLETION.PredicateSpec.from_mapping(declaration)


@pytest.mark.parametrize(
    "declaration",
    [
        {"argv": ["python3", "check.py"], "timeout_seconds": COMPLETION.MAX_TIMEOUT_SECONDS + 1},
        {"argv": ["python3", "check.py"], "max_output_bytes": COMPLETION.MAX_OUTPUT_BYTES + 1},
        {"argv": ["python3", "check.py"], "timeout_seconds": 0},
        {"argv": ["python3", "check.py"], "timeout_seconds": "fast"},
    ],
)
def test_unbounded_predicate_limits_are_rejected_rather_than_clamped(declaration: Any) -> None:
    with pytest.raises(COMPLETION.PredicateSchemaError):
        COMPLETION.PredicateSpec.from_mapping(declaration)


def test_a_valid_declaration_round_trips_through_the_schema() -> None:
    spec = COMPLETION.PredicateSpec.from_mapping(
        {"argv": ["python3", "checks/check.py"], "timeout_seconds": 5.0, "max_output_bytes": 1024}
    )
    assert COMPLETION.PredicateSpec.from_mapping(spec.to_mapping()) == spec


# --------------------------------------------------------------------------- scenario 3: closure


def test_predicate_entry_point_inside_the_write_scope_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "self_check.py").write_text("import sys; sys.exit(0)\n", encoding="utf-8")
    _git(repo, "add", "src")
    _git(repo, "commit", "-q", "-m", "predicate inside scope")
    git = LIFECYCLE.GitLanding()
    spec = _spec(mutating=True, environment_command=())
    landing = git.provision(repo, spec)
    predicate = COMPLETION.PredicateSpec(argv=(sys.executable, "src/self_check.py"))

    with pytest.raises(COMPLETION.PredicateScopeError, match="src/self_check.py"):
        COMPLETION.issue_receipt(
            repo, spec, landing, predicate, artifact_name="report.json", git=git
        )


def test_predicate_importing_a_module_inside_the_write_scope_is_rejected(tmp_path: Path) -> None:
    """The child rewrites what the predicate imports, which is exactly as compromised."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "oracle.py").write_text("THRESHOLD = 1\n", encoding="utf-8")
    (repo / "checks" / "importing_check.py").write_text(
        "import sys\nsys.path.insert(0, 'src')\nfrom src.oracle import THRESHOLD\nsys.exit(0)\n",
        encoding="utf-8",
    )
    _git(repo, "add", "src", "checks")
    _git(repo, "commit", "-q", "-m", "predicate importing scope")
    git = LIFECYCLE.GitLanding()
    spec = _spec(mutating=True, environment_command=())
    landing = git.provision(repo, spec)
    predicate = COMPLETION.PredicateSpec(argv=(sys.executable, "checks/importing_check.py"))

    with pytest.raises(COMPLETION.PredicateScopeError, match="src/oracle.py"):
        COMPLETION.issue_receipt(
            repo, spec, landing, predicate, artifact_name="report.json", git=git
        )


def test_transitive_import_two_levels_deep_is_still_in_the_closure(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "deep.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "checks" / "middle.py").write_text(
        "import sys\nsys.path.insert(0, 'src')\nfrom src.deep import VALUE\n", encoding="utf-8"
    )
    (repo / "checks" / "entry.py").write_text("import middle\n", encoding="utf-8")
    closure = COMPLETION.predicate_closure(
        repo, COMPLETION.PredicateSpec(argv=(sys.executable, "checks/entry.py"))
    )
    assert "src/deep.py" in closure


def test_a_dependency_closure_larger_than_its_bound_fails_closed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    for index in range(6):
        (repo / "checks" / f"mod_{index}.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "checks" / "wide.py").write_text(
        "".join(f"import mod_{index}\n" for index in range(6)), encoding="utf-8"
    )
    predicate = COMPLETION.PredicateSpec(argv=(sys.executable, "checks/wide.py"))
    with pytest.raises(COMPLETION.PredicateClosureError, match="closure"):
        COMPLETION.predicate_closure(repo, predicate, max_files=3)


def test_a_dynamically_imported_dependency_is_outside_the_documented_closure(
    tmp_path: Path,
) -> None:
    """Pins the stated limit: only statically visible imports are followed."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "late.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "checks" / "dynamic.py").write_text(
        "import importlib\nimportlib.import_module('src.late')\n", encoding="utf-8"
    )
    closure = COMPLETION.predicate_closure(
        repo, COMPLETION.PredicateSpec(argv=(sys.executable, "checks/dynamic.py"))
    )
    assert "src/late.py" not in closure


def test_a_closure_change_after_dispatch_fails_before_the_predicate_runs(tmp_path: Path) -> None:
    """The dynamic half: the child weakened a closure file outside its declared scope."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.write_deliverable()
    (repo / "checks" / "helpers.py").write_text("REQUIRED_KEYS = ()\n", encoding="utf-8")

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "predicate_tampered"
    assert result.predicate is None


# --------------------------------------------------------------------------- scenario 4: settle


def test_an_artifact_written_directly_to_the_destination_is_not_settled(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.write_deliverable(path=prepared.receipt.artifact_path)

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "artifact_unsettled"
    assert "in-flight" in result.detail


def test_a_destination_touched_alongside_a_valid_inflight_file_is_not_settled(
    tmp_path: Path,
) -> None:
    """Pins the pre-dispatch destination state, not merely the presence of an in-flight file."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.write_deliverable()
    prepared.receipt.artifact_path.write_text("{}", encoding="utf-8")

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "artifact_unsettled"
    assert "changed during the dispatch window" in result.detail


def test_a_child_that_produced_nothing_fails_with_a_recorded_verdict(tmp_path: Path) -> None:
    """The commonest real failure: the child died, stalled, or ignored the protocol entirely.

    Nothing exists at either path, so the destination is unchanged and only the in-flight
    requirement stands between "produced nothing" and an unhandled rename of a missing file.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "artifact_unsettled"
    assert "did not produce a settleable deliverable" in result.detail
    assert REGISTER.read_rows(repo)["child-a"]["completion"]["reason"] == "artifact_unsettled"


def test_an_inflight_symlink_is_refused_rather_than_renamed_into_place(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_text("{}", encoding="utf-8")
    prepared = _prepare(repo)
    prepared.receipt.inflight_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.receipt.inflight_path.symlink_to(elsewhere)

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "artifact_unsettled"


def test_settlement_does_not_claim_to_detect_delete_then_recreate(tmp_path: Path) -> None:
    """Pins the documented limit of the settlement control.

    The orchestrator performs the rename, so the destination is provably the in-flight file. It
    does not and cannot establish how the child produced that in-flight file.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.receipt.inflight_path.parent.mkdir(parents=True, exist_ok=True)
    with prepared.receipt.inflight_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"binding": prepared.receipt.binding_token, "conclusion": "ok"}))

    result = prepared.evaluate()
    assert result.verified is True


# --------------------------------------------------------------------------- scenario 1: binding


def test_an_artifact_from_a_previous_run_does_not_satisfy_the_predicate(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    stale_token = COMPLETION.artifact_binding_token("run-previous", "child-a", "old")
    prepared.write_deliverable({"binding": stale_token, "conclusion": "stale but complete"})

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "artifact_binding"
    assert "run-previous" in result.detail


def test_an_artifact_with_no_binding_at_all_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.write_deliverable({"binding": "none", "conclusion": "complete"})

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "artifact_binding"
    assert "no run binding at all" in result.detail


def test_the_expected_binding_is_established_before_the_child_can_write_anything(
    tmp_path: Path,
) -> None:
    """The receipt is orchestrator-computed and durable before dispatch, never read from disk."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)

    stored = REGISTER.read_rows(repo)["child-a"]["dispatch_receipt"]
    assert stored["binding_token"] == prepared.receipt.binding_token
    assert not prepared.receipt.artifact_path.exists()
    assert not prepared.receipt.inflight_path.exists()
    assert COMPLETION.read_receipt(repo, "child-a").binding_token == prepared.receipt.binding_token


def test_a_re_dispatch_of_the_same_row_rejects_the_previous_attempts_artifact(
    tmp_path: Path,
) -> None:
    """Same run, same row, same path -- staleness that a per-run directory cannot rule out."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    first = _prepare(repo)
    first.write_deliverable()
    assert first.evaluate().verified is True

    second = _prepare(repo)
    second.receipt.inflight_path.write_text(
        first.receipt.artifact_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    result = second.evaluate()
    assert result.verified is False
    assert result.reason == "artifact_binding"


# --------------------------------------------------------------------------- scenario 5: content


def test_a_truncated_but_syntactically_valid_artifact_fails_rather_than_passing(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.write_deliverable({"binding": prepared.receipt.binding_token})

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "predicate_failed"
    assert result.predicate is not None and result.predicate.returncode == 1


# --------------------------------------------------------------------------- scenario 8: bounds


def test_a_predicate_that_hangs_is_a_failure(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "checks" / "hang.py").write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    prepared = _prepare(
        repo,
        predicate=COMPLETION.PredicateSpec(
            argv=(sys.executable, "checks/hang.py"), timeout_seconds=0.5
        ),
    )
    prepared.write_deliverable()

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "predicate_timeout"


def test_a_predicate_that_exceeds_its_output_limit_is_a_failure(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "checks" / "spew.py").write_text(
        "import sys\nfor _ in range(20000):\n    sys.stdout.write('x' * 200 + '\\n')\n",
        encoding="utf-8",
    )
    prepared = _prepare(
        repo,
        predicate=COMPLETION.PredicateSpec(
            argv=(sys.executable, "checks/spew.py"), timeout_seconds=30.0, max_output_bytes=4096
        ),
    )
    prepared.write_deliverable()

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "predicate_output_limit"


def test_a_predicate_that_never_stops_spewing_is_killed_at_the_cap_not_at_the_deadline(
    tmp_path: Path,
) -> None:
    """Pins the *streaming* cap rather than the post-exit size check.

    A predicate that exits on its own can be measured after the fact. One that never exits has to
    be killed while it is still writing, or the cap bounds nothing.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "checks" / "forever.py").write_text(
        "import sys\nwhile True:\n    sys.stdout.write('x' * 1000)\n    sys.stdout.flush()\n",
        encoding="utf-8",
    )
    prepared = _prepare(
        repo,
        predicate=COMPLETION.PredicateSpec(
            argv=(sys.executable, "checks/forever.py"),
            timeout_seconds=30.0,
            max_output_bytes=4096,
        ),
    )
    prepared.write_deliverable()

    started = time.monotonic()
    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "predicate_output_limit"
    assert time.monotonic() - started < 15.0


def test_a_predicate_that_errors_is_a_failure_never_a_pass(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(
        repo, predicate=COMPLETION.PredicateSpec(argv=("orchestrate-no-such-program",))
    )
    prepared.write_deliverable()

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "predicate_error"


def test_a_predicate_that_raises_is_a_failure(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "checks" / "boom.py").write_text("raise SystemError('boom')\n", encoding="utf-8")
    prepared = _prepare(
        repo, predicate=COMPLETION.PredicateSpec(argv=(sys.executable, "checks/boom.py"))
    )
    prepared.write_deliverable()

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "predicate_failed"


def test_a_predicate_that_writes_into_the_landing_fails_the_predicate_not_the_child(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "checks" / "dirty.py").write_text(
        "open('predicate-residue.txt', 'w').write('x')\n", encoding="utf-8"
    )
    prepared = _prepare(
        repo, predicate=COMPLETION.PredicateSpec(argv=(sys.executable, "checks/dirty.py"))
    )
    prepared.write_deliverable()

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "predicate_side_effect"
    assert "predicate-residue.txt" in result.detail


# --------------------------------------------------------------------- scenario 6: integration


def _mutating_prepared(repo: Path, row_id: str = "child-m") -> _Prepared:
    return _prepare(repo, row_id=row_id, mutating=True, environment_command=(), scope=("src",))


def test_reaping_is_refused_while_the_destination_branch_is_unchanged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _mutating_prepared(repo)
    prepared.write_deliverable()

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "integration_unverified"
    assert REGISTER.read_rows(repo)["child-m"]["phase"] != "verified"
    with pytest.raises(LIFECYCLE.SessionLifecycleError, match="must be verified before reap"):
        LIFECYCLE.reap_verified(repo, "child-m", herdr=FakeHerdr())


def test_reaping_is_permitted_once_the_destination_branch_advances(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _mutating_prepared(repo)
    worktree = Path(prepared.landing.cwd)
    (worktree / "src").mkdir()
    (worktree / "src" / "landed.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(worktree, "add", "src/landed.py")
    _git(worktree, "commit", "-q", "-m", "child work")
    prepared.write_deliverable()
    REGISTER.upsert_row(repo, "child-m", {"tab_id": "tab-m", "cwd": str(worktree)})

    result = prepared.evaluate()
    assert result.verified is True, result.detail
    herdr = FakeHerdr()
    LIFECYCLE.reap_verified(repo, "child-m", herdr=herdr)
    assert herdr.closed == ["tab-m"]
    assert REGISTER.read_rows(repo)["child-m"]["phase"] == "reaped"


def test_reaping_is_refused_while_a_path_destination_is_unchanged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "delivered.txt").write_text("before\n", encoding="utf-8")
    spec = _spec(row_id="child-p")
    git = LIFECYCLE.GitLanding()
    landing = LIFECYCLE.Landing(
        repo.resolve(), "path", "delivered.txt", git.base_commit(repo), repo.resolve()
    )
    REGISTER.upsert_row(repo, "child-p", {"run_id": "run-a", "phase": "working"})
    artifacts = COMPLETION.artifact_landing(repo.resolve(), "run-a", "child-p")
    relative = artifacts.relative_to(repo.resolve()) / "report.json"
    receipt = COMPLETION.issue_receipt(
        repo,
        spec,
        landing,
        _predicate(relative.as_posix()),
        artifact_name="report.json",
        git=git,
    )
    prepared = _Prepared(repo, spec, landing, git, receipt)
    prepared.write_deliverable()

    assert prepared.evaluate().reason == "integration_unverified"


def test_read_only_work_integrates_nowhere_and_is_permitted_under_mode_none(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.write_deliverable()
    REGISTER.upsert_row(repo, "child-a", {"tab_id": "tab-a"})

    result = prepared.evaluate()
    assert result.verified is True, result.detail
    assert result.integration is not None and "none" in result.integration
    herdr = FakeHerdr()
    LIFECYCLE.reap_verified(repo, "child-a", herdr=herdr)
    assert herdr.closed == ["tab-a"]


# --------------------------------------------------------------------------- scenario 9: pass


def test_a_passing_predicate_on_a_settled_bound_artifact_reaps_cleanly(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    inflight = prepared.write_deliverable()
    REGISTER.upsert_row(repo, "child-a", {"tab_id": "tab-a"})

    result = prepared.evaluate()
    assert result.verified is True, result.detail
    assert not inflight.exists()
    assert prepared.receipt.artifact_path.is_file()
    expected = hashlib.sha256(prepared.receipt.artifact_path.read_bytes()).hexdigest()
    assert result.artifact_digest == "sha256:" + expected
    row = REGISTER.read_rows(repo)["child-a"]
    assert row["phase"] == "verified"
    assert row["completion"]["result"] == "verified"
    LIFECYCLE.reap_verified(repo, "child-a", herdr=FakeHerdr())


# --------------------------------------------------------------------- scenario 7: depth sample


@pytest.mark.parametrize(
    ("work_shape", "judgment"),
    [
        ("judgment", True),
        ("second-opinion", True),
        ("divergence", True),
        ("adversarial-review", True),
        ("mechanical", False),
        ("purely-mechanical", False),
        ("read-only-survey", False),
        ("offload", False),
        ("offload-test-gated", False),
        ("contract-test", False),
        ("mechanical-scan", False),
    ],
)
def test_every_work_shape_in_the_authoritative_vocabulary_is_classified(
    work_shape: str, judgment: bool
) -> None:
    assert COMPLETION.is_judgment_shaped(work_shape) is judgment


def test_a_judgment_shaped_child_cannot_reach_verified_on_mechanical_coverage_alone(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.write_deliverable()

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "depth_sample_missing"
    assert result.predicate is not None and result.predicate.passed is True


def _sample(prepared: _Prepared, **overrides: Any) -> Any:
    digest = "sha256:" + hashlib.sha256(prepared.receipt.inflight_path.read_bytes()).hexdigest()
    values: dict[str, Any] = {
        "verifier_row_id": "verifier-1",
        "verifier_vendor": "grok",
        "verifier_model": "grok-4.6",
        "artifact_digest": digest,
        "claims": (
            COMPLETION.SampledClaim("the migration is reversible", "report.json:12", "supported"),
        ),
    }
    values.update(overrides)
    return COMPLETION.DepthSample(**values)


def test_a_judgment_shaped_child_reaches_verified_with_an_independent_depth_sample(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.write_deliverable()

    result = prepared.evaluate(depth_sample=_sample(prepared))
    assert result.verified is True, result.detail


def test_a_depth_sample_from_the_child_itself_is_not_an_independent_reader(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.write_deliverable()

    result = prepared.evaluate(depth_sample=_sample(prepared, verifier_row_id="child-a"))
    assert result.verified is False
    assert result.reason == "depth_sample_invalid"


def test_a_depth_sample_recorded_against_another_artifact_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.write_deliverable()

    result = prepared.evaluate(depth_sample=_sample(prepared, artifact_digest="sha256:" + "0" * 64))
    assert result.verified is False
    assert result.reason == "depth_sample_invalid"


def test_an_unsupported_sampled_claim_blocks_verification(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.write_deliverable()

    unsupported = COMPLETION.SampledClaim("no data is lost", "report.json:40", "unsupported")
    result = prepared.evaluate(depth_sample=_sample(prepared, claims=(unsupported,)))
    assert result.verified is False
    assert result.reason == "depth_sample_unsupported"


@pytest.mark.parametrize(
    "claim",
    [
        ("", "report.json:1", "supported"),
        ("a claim", "  ", "supported"),
        ("a claim", "report.json:1", "probably"),
    ],
)
def test_an_incomplete_sampled_claim_is_rejected(claim: tuple[str, str, str]) -> None:
    with pytest.raises(COMPLETION.DepthSampleError):
        COMPLETION.SampledClaim(*claim)


def test_a_depth_sample_with_no_claims_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.write_deliverable()

    result = prepared.evaluate(depth_sample=_sample(prepared, claims=()))
    assert result.verified is False
    assert result.reason == "depth_sample_invalid"


def test_a_depth_sample_round_trips_through_its_register_mapping(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.write_deliverable()
    sample = _sample(prepared)
    assert COMPLETION.DepthSample.from_mapping(sample.to_mapping()) == sample


# ----------------------------------------------------- carried requirement: read-only landings


def test_two_read_only_children_with_disjoint_scopes_both_complete_cleanly(
    tmp_path: Path,
) -> None:
    """The requirement carried from U4: the ordinary multi-child configuration must pass.

    Each child's deliverable lands in a directory that is exclusively its own and invisible to
    the repository boundary, so neither is attributed the other's output.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    first = _prepare(repo, row_id="child-a", scope=("reports/a",))
    second = _prepare(repo, row_id="child-b", scope=("reports/b",))
    first.write_deliverable()
    second.write_deliverable()

    first_result = first.evaluate()
    second_result = second.evaluate()
    assert first_result.verified is True, first_result.detail
    assert second_result.verified is True, second_result.detail
    assert first_result.scope is not None and first_result.scope.outside_scope == frozenset()
    assert second_result.scope is not None and second_result.scope.outside_scope == frozenset()


def test_a_read_only_child_writing_into_the_repository_still_fails_the_boundary(
    tmp_path: Path,
) -> None:
    """A read-only child's declared scope is a read scope, never a repository write allowlist."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, scope=("reports/a",))
    prepared.write_deliverable()
    stray = repo / "reports" / "a" / "notes.md"
    stray.parent.mkdir(parents=True)
    stray.write_text("written into the shared checkout\n", encoding="utf-8")

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "scope_violation"
    assert "reports/a/notes.md" in result.detail


def test_a_boundary_violation_fails_completion_even_when_the_predicate_passes(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _mutating_prepared(repo)
    worktree = Path(prepared.landing.cwd)
    (worktree / "outside.txt").write_text("escaped\n", encoding="utf-8")
    prepared.write_deliverable()

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "scope_violation"
    assert result.predicate is not None and result.predicate.passed is True


def test_a_repository_that_does_not_ignore_the_state_directory_fails_closed(
    tmp_path: Path,
) -> None:
    """The read-only repair depends on the artifact landing being outside Git's view."""
    repo = tmp_path / "repo"
    _init_repo(repo, ignore_orchestrate=False)
    spec = _spec()
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, spec)
    with pytest.raises(COMPLETION.LandingNotExclusiveError, match="not ignored"):
        COMPLETION.issue_receipt(
            repo, spec, landing, _predicate("x"), artifact_name="report.json", git=git
        )


def test_every_child_may_write_only_its_own_artifact_directory(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    git = LIFECYCLE.GitLanding()
    read_only = _spec(scope=("reports/a",))
    mutating = _spec(row_id="child-m", mutating=True, environment_command=(), scope=("src",))
    read_only_landing = git.provision(repo, read_only)
    mutating_landing = git.provision(repo, mutating)

    assert COMPLETION.write_scope_for(read_only, read_only_landing) == (
        ".orchestrate/artifacts/run-a/child-a",
    )
    assert COMPLETION.write_scope_for(mutating, mutating_landing) == (
        "src",
        ".orchestrate/artifacts/run-a/child-m",
    )
    assert COMPLETION.repository_scope_for(read_only).scope == ()
    assert COMPLETION.repository_scope_for(mutating).scope == ("src",)


# --------------------------------------------------- failed predicate is not a new phase (3.1)


def test_a_failed_predicate_leaves_the_phase_alone_and_records_a_durable_verdict(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.write_deliverable({"binding": prepared.receipt.binding_token})

    result = prepared.evaluate()
    assert result.verified is False
    row = REGISTER.read_rows(repo)["child-a"]
    assert row["phase"] == "working"
    assert row["completion"]["result"] == "failed"
    assert row["completion"]["reason"] == "predicate_failed"
    assert COMPLETION.failed_rows(repo, run_id="run-a") == {"child-a": row["completion"]}
    assert COMPLETION.is_working_not_failed(repo, "child-a") is False


def test_no_completion_outcome_writes_a_phase_outside_the_closed_vocabulary(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    payloads: list[dict[str, Any]] = [
        {"binding": "wrong"},
        {"binding": None},
        {"binding": None, "conclusion": "ok"},
    ]
    for index, payload in enumerate(payloads):
        prepared = _prepare(repo, row_id=f"child-{index}")
        document = dict(payload)
        if document.get("binding") is None:
            document["binding"] = prepared.receipt.binding_token
        prepared.write_deliverable(document)
        prepared.evaluate()
        assert REGISTER.read_rows(repo)[f"child-{index}"]["phase"] in REGISTER.PHASES


def test_a_snapshot_catch_up_pass_does_not_erase_a_recorded_completion_failure(
    tmp_path: Path,
) -> None:
    """Why the verdict does not live in ``observed_state``: catch-up owns that column.

    The catch-up pass below is the shipped U3 consumer, not a stand-in, and it demonstrably
    rewrites ``observed_state`` for a live pane while leaving the completion verdict intact.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.write_deliverable({"binding": prepared.receipt.binding_token})
    prepared.evaluate()
    REGISTER.upsert_row(
        repo, "child-a", {"pane_id": "pane-a", "observed_state": "predicate_failed"}
    )

    SUBSCRIBER.catch_up(
        repo,
        {"panes": [{"pane_id": "pane-a", "agent_status": "working"}], "agents": []},
        run_id="run-a",
    )
    row = REGISTER.read_rows(repo)["child-a"]
    assert row["observed_state"] == "working"
    assert row["completion"]["reason"] == "predicate_failed"


# --------------------------------------------------------------------------- adapters


def test_the_git_adapter_reports_a_missing_revision_rather_than_raising(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    git = LIFECYCLE.GitLanding()
    assert git.rev_parse(repo, "no-such-branch") is None
    assert git.rev_parse(repo, "main") == git.base_commit(repo)


def test_the_git_adapter_answers_the_ignore_question(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    git = LIFECYCLE.GitLanding()
    assert git.is_ignored(repo, ".orchestrate/artifacts") is True
    assert git.is_ignored(repo, "src/thing.py") is False


def test_a_receipt_round_trips_through_its_register_mapping(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    assert COMPLETION.DispatchReceipt.from_mapping(prepared.receipt.to_mapping()) == (
        prepared.receipt
    )


def test_dispatch_instructions_name_the_inflight_path_and_the_binding(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    text = COMPLETION.artifact_instructions(prepared.receipt)
    assert str(prepared.receipt.inflight_path) in text
    assert prepared.receipt.binding_token in text


def test_completing_a_row_that_was_never_bound_to_a_dispatch_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    REGISTER.upsert_row(repo, "child-z", {"run_id": "run-a", "phase": "working"})
    with pytest.raises(COMPLETION.CompletionError, match="no dispatch receipt"):
        COMPLETION.read_receipt(repo, "child-z")


def test_an_artifact_above_the_binding_read_bound_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.write_deliverable()
    with pytest.raises(COMPLETION.ArtifactError, match="binding-check bound"):
        COMPLETION.assert_artifact_binding(
            prepared.receipt.inflight_path, prepared.receipt, max_bytes=4
        )


def test_the_artifact_landing_is_exclusive_per_run_and_row(tmp_path: Path) -> None:
    landing = tmp_path
    first = COMPLETION.artifact_landing(landing, "run-a", "child-a")
    same_run = COMPLETION.artifact_landing(landing, "run-a", "child-b")
    other_run = COMPLETION.artifact_landing(landing, "run-b", "child-a")
    assert len({first, same_run, other_run}) == 3
    with pytest.raises(COMPLETION.CompletionError, match="run_id"):
        COMPLETION.artifact_landing(landing, "../escape", "child-a")


def test_the_completion_result_is_recorded_for_a_row_that_was_never_evaluated(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    REGISTER.upsert_row(repo, "child-z", {"run_id": "run-a", "phase": "working"})
    assert COMPLETION.completion_record(repo, "child-z") is None
    assert COMPLETION.completion_record(repo, "absent") is None
    assert COMPLETION.is_working_not_failed(repo, "child-z") is True


def test_replacing_the_spec_scope_does_not_mutate_the_original(tmp_path: Path) -> None:
    spec = _spec(scope=("reports/a",))
    narrowed = COMPLETION.repository_scope_for(spec)
    assert spec.scope == ("reports/a",)
    assert narrowed.scope == ()
    assert replace(spec, scope=()) == narrowed


# ----------------------------------------------- remaining members of each control's input class


def test_an_artifact_bound_to_a_different_child_in_the_same_run_is_rejected(
    tmp_path: Path,
) -> None:
    """Same run and same nonce shape, wrong child -- the binding is per dispatch, not per run."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    sibling_token = COMPLETION.artifact_binding_token("run-a", "child-b", prepared.receipt.nonce)
    prepared.write_deliverable({"binding": sibling_token, "conclusion": "complete"})

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "artifact_binding"
    assert "child-b" in result.detail


def test_a_relative_import_into_the_write_scope_is_in_the_closure(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "oracle.py").write_text("THRESHOLD = 1\n", encoding="utf-8")
    (repo / "src" / "relative_check.py").write_text(
        "from .oracle import THRESHOLD\n", encoding="utf-8"
    )
    closure = COMPLETION.predicate_closure(
        repo, COMPLETION.PredicateSpec(argv=(sys.executable, "src/relative_check.py"))
    )
    assert "src/oracle.py" in closure


def test_a_path_argument_is_a_closure_root_not_only_the_entry_point(tmp_path: Path) -> None:
    """For a runner such as pytest the path arguments *are* the check."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "suite.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    closure = COMPLETION.predicate_closure(
        repo, COMPLETION.PredicateSpec(argv=("pytest", "-q", "src/suite.py"))
    )
    assert closure == ("src/suite.py",)


def test_a_directory_argument_expands_to_its_python_members(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "one.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "src" / "two.py").write_text("VALUE = 2\n", encoding="utf-8")
    (repo / "src" / "notes.md").write_text("not code\n", encoding="utf-8")
    closure = COMPLETION.predicate_closure(
        repo, COMPLETION.PredicateSpec(argv=("pytest", "-q", "src"))
    )
    assert closure == ("src/one.py", "src/two.py")


def _path_mode_prepared(repo: Path, row_id: str) -> _Prepared:
    spec = _spec(row_id=row_id)
    git = LIFECYCLE.GitLanding()
    landing = LIFECYCLE.Landing(
        repo.resolve(), "path", "delivered.txt", git.base_commit(repo), repo.resolve()
    )
    REGISTER.upsert_row(repo, row_id, {"run_id": "run-a", "phase": "working"})
    artifacts = COMPLETION.artifact_landing(repo.resolve(), "run-a", row_id)
    relative = artifacts.relative_to(repo.resolve()) / "report.json"
    receipt = COMPLETION.issue_receipt(
        repo, spec, landing, _predicate(relative.as_posix()), artifact_name="report.json", git=git
    )
    return _Prepared(repo, spec, landing, git, receipt)


def test_a_changed_path_destination_satisfies_the_integration_gate(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "delivered.txt").write_text("before\n", encoding="utf-8")
    _git(repo, "add", "delivered.txt")
    _git(repo, "commit", "-q", "-m", "destination")
    prepared = _path_mode_prepared(repo, "child-p")
    prepared.write_deliverable()
    (repo / "delivered.txt").write_text("after\n", encoding="utf-8")

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "scope_violation"
    assert COMPLETION.verify_integration(
        prepared.receipt, prepared.landing, git=prepared.git
    ).startswith("path delivered.txt changed")


def test_an_unsupported_integration_mode_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    broken = replace(prepared.receipt, integration_mode="teleport")
    with pytest.raises(COMPLETION.CompletionError, match="unsupported integration mode"):
        COMPLETION.verify_integration(broken, prepared.landing, git=prepared.git)


def test_a_missing_destination_branch_is_refused_rather_than_treated_as_landed(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _mutating_prepared(repo, "child-gone")
    broken = replace(prepared.receipt, destination="orchestrate-never-created")
    with pytest.raises(COMPLETION.CompletionError, match="does not exist"):
        COMPLETION.verify_integration(broken, prepared.landing, git=prepared.git)


def test_every_recorded_failure_reason_is_in_the_closed_vocabulary(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.write_deliverable({"binding": prepared.receipt.binding_token})
    result = prepared.evaluate()
    assert result.reason in COMPLETION.FAILURE_REASONS
    assert len(set(COMPLETION.FAILURE_REASONS)) == len(COMPLETION.FAILURE_REASONS)
