"""Contract tests for orchestrate U5 completion behavior.

Every test here crosses the boundaries this unit actually owns: a real Git repository, real
files, and real subprocesses for predicate execution. The only hand-authored boundary is Herdr,
which this unit touches solely through U4's already-tested reap path.

The *child* boundary is real too, and that is not a detail. A test that produces the deliverable
from the pytest process certifies the settlement protocol under the permissions of the process
running the tests, which is not the permission posture a dispatched child has. Wherever the claim
under test is about what a child can do, the deliverable is written by a separate process --
:meth:`_Prepared.run_child_process` -- not by this one.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import os
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


# -------------------------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def _orchestrator_secret_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every test's per-run orchestrator secret out of the operator's home directory.

    The location is deliberately a sibling of the test repository rather than a path inside it:
    the module refuses a secret directory inside the repository, because every child's landing is
    inside the repository.
    """
    monkeypatch.setenv(COMPLETION.RUN_SECRET_DIR_ENV, str(tmp_path / "orchestrator-secrets"))


#: A stand-in child. It receives the same dispatch text a real child receives and does exactly
#: what that text asks: it writes the in-flight sibling, and nothing else.
_CHILD_SOURCE = """\
import json
import pathlib
import sys

indented = [line.strip() for line in sys.argv[1].splitlines() if line.startswith("  ")]
inflight, destination, token = indented
assert not pathlib.Path(destination).exists(), "the child must never see its destination"
pathlib.Path(inflight).write_text(
    json.dumps({"binding": token, "conclusion": "done"}), encoding="utf-8"
)
"""


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


def _baseline(git: Any, landing: Any) -> Any:
    return git.changed_paths_baseline(
        landing.cwd, base_commit=landing.base_commit, ambient_root=landing.ambient_root
    )


class _Prepared:
    def __init__(
        self, repo: Path, spec: Any, landing: Any, git: Any, receipt: Any, baseline: Any
    ) -> None:
        self.repo = repo
        self.spec = spec
        self.landing = landing
        self.git = git
        self.receipt = receipt
        # Taken before the receipt is issued and bound into it, exactly as the product does:
        # readiness produces the snapshot, the receipt binds it, evaluation compares it.
        self.baseline = baseline

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

    def run_child_process(self) -> subprocess.CompletedProcess[str]:
        """Produce the deliverable from a separate process, given only the dispatch text.

        This is the boundary the rest of the suite cannot cross by writing files itself: the
        deliverable is authored by a different process, in the landing, from
        :func:`artifact_instructions` and nothing else. The script lives outside the repository
        so its presence is not itself a boundary change.
        """
        script = self.repo.parent / f"child-{self.spec.row_id}.py"
        script.write_text(_CHILD_SOURCE, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(script), COMPLETION.artifact_instructions(self.receipt)],
            cwd=self.landing.cwd,
            capture_output=True,
            text=True,
            check=False,
        )

    def evaluate(self, **kwargs: Any) -> Any:
        return COMPLETION.evaluate_completion(
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
    record_root: bool = True,
    **spec_overrides: Any,
) -> _Prepared:
    spec = _spec(**spec_overrides)
    git = LIFECYCLE.GitLanding()
    if record_root:
        COMPLETION.record_run_root(repo, spec.run_id)
    landing = git.provision(repo, spec)
    REGISTER.upsert_row(
        repo, spec.row_id, {"run_id": spec.run_id, "phase": "working", "expected_state": "working"}
    )
    if predicate is None:
        artifacts = COMPLETION.artifact_landing(Path(landing.cwd), spec.run_id, spec.row_id)
        relative = artifacts.relative_to(Path(landing.cwd).resolve()) / artifact_name
        predicate = _predicate(relative.as_posix())
    baseline = _baseline(git, landing)
    receipt = COMPLETION.issue_receipt(
        spec,
        landing,
        predicate,
        artifact_name=artifact_name,
        git=git,
        changed_paths_baseline=baseline,
    )
    return _Prepared(repo, spec, landing, git, receipt, baseline)


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


# ---------------------------------------------------------------------- scenario 2: schema


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


# --------------------------------------------------------------------- scenario 3: closure


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
            spec,
            landing,
            predicate,
            artifact_name="report.json",
            git=git,
            changed_paths_baseline=_baseline(git, landing),
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
            spec,
            landing,
            predicate,
            artifact_name="report.json",
            git=git,
            changed_paths_baseline=_baseline(git, landing),
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


# ---------------------------------------------------------------------- scenario 4: settle


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


# --------------------------------------------------------------------- scenario 1: binding


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


# --------------------------------------------------------------------- scenario 5: content


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


# ---------------------------------------------------------------------- scenario 8: bounds


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


# ----------------------------------------------------------------- scenario 6: integration


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
        spec,
        landing,
        _predicate(relative.as_posix()),
        artifact_name="report.json",
        git=git,
        changed_paths_baseline=_baseline(git, landing),
    )
    prepared = _Prepared(repo, spec, landing, git, receipt, _baseline(git, landing))
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


# ------------------------------------------------------------------------ scenario 9: pass


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


# ---------------------------------------------------------------- scenario 7: depth sample


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


def _verifier_row(
    repo: Path,
    row_id: str = "verifier-1",
    *,
    run_id: str = "run-a",
    vendor: str = "grok",
    model: str = "grok-4.6",
    phase: str = "working",
    dispatched: bool = True,
    record_root: bool = True,
) -> None:
    """Register a verifier session.

    ``dispatched=True`` issues a real dispatch receipt for the verifier, because that is what the
    product does and it is the only part of a verifier row a child cannot forge. ``dispatched=False``
    plants the columns alone -- the shape a write-capable child can produce, which must be refused.
    """
    if dispatched:
        _prepare(
            repo,
            row_id=row_id,
            run_id=run_id,
            runtime=vendor,
            artifact_name="verdict.json",
            record_root=record_root,
        )
    REGISTER.upsert_row(
        repo, row_id, {"run_id": run_id, "vendor": vendor, "model": model, "phase": phase}
    )


def _artifact_digest(prepared: _Prepared) -> str:
    """Digest whichever side of the settlement the deliverable is currently on."""
    path = prepared.receipt.artifact_path
    if not path.is_file():
        path = prepared.receipt.inflight_path
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _sample(prepared: _Prepared, *, register: bool = True, **overrides: Any) -> Any:
    if register:
        _verifier_row(prepared.repo, run_id=prepared.spec.run_id)
    values: dict[str, Any] = {
        "verifier_row_id": "verifier-1",
        "verifier_vendor": "grok",
        "verifier_model": "grok-4.6",
        "artifact_digest": _artifact_digest(prepared),
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


def test_a_depth_sample_round_trips_through_the_register_it_is_recorded_in(
    tmp_path: Path,
) -> None:
    """The record the operator can actually see, not a mapping that never left memory."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()
    sample = _sample(prepared)

    assert prepared.evaluate(depth_sample=sample).verified is True
    stored = REGISTER.read_rows(repo)["child-a"]["completion"]["depth_sample"]
    assert COMPLETION.DepthSample.from_mapping(stored) == sample


def test_a_verified_judgment_child_has_its_verifier_and_claims_on_record(
    tmp_path: Path,
) -> None:
    """A sampled child and a child whose sample certified nothing must not be the same green row.

    Everything the plan requires durably -- verifier identity, the claims, where each was checked,
    and how each was disposed -- is read back out of the register here, not out of the in-memory
    result object.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()

    assert prepared.evaluate(depth_sample=_sample(prepared)).verified is True
    recorded = REGISTER.read_rows(repo)["child-a"]["completion"]["depth_sample"]
    assert recorded["verifier_row_id"] == "verifier-1"
    assert recorded["verifier_vendor"] == "grok"
    assert recorded["verifier_model"] == "grok-4.6"
    assert recorded["claims"] == [
        {
            "claim": "the migration is reversible",
            "evidence_location": "report.json:12",
            "disposition": "supported",
        }
    ]


def test_a_depth_sample_naming_a_verifier_that_never_existed_is_rejected(
    tmp_path: Path,
) -> None:
    """An unchecked string is not an independent verifier session."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()

    result = prepared.evaluate(
        depth_sample=_sample(prepared, register=False, verifier_row_id="verifier-that-never-was")
    )
    assert result.verified is False
    assert result.reason == "depth_sample_invalid"
    assert "no row in the register" in result.detail


def test_a_depth_sample_naming_a_verifier_that_never_started_is_rejected(tmp_path: Path) -> None:
    """The honest never-started state: a dispatch was issued and the session never came up."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()
    _verifier_row(repo, phase="planned")

    result = prepared.evaluate(depth_sample=_sample(prepared, register=False))
    assert result.verified is False
    assert result.reason == "depth_sample_invalid"
    assert "is not one of the phases past launch" in result.detail


def test_a_verifier_phase_outside_the_register_vocabulary_is_not_a_started_dispatch(
    tmp_path: Path,
) -> None:
    """The check is membership of the started phases, not the absence of three known strings.

    Refusing ``planned`` and ``launching`` by name accepts everything nobody thought of. The empty
    string and a value that is not a phase at all both mean the same thing this check exists to
    refuse -- no dispatch was observed to start -- and a name-based refusal reads both as started.
    A phase column is writable, so the values reaching this check are not limited to the ones the
    lifecycle writes.

    This does not make the column trustworthy. A planted ``working`` still passes, and that is the
    named residual. It makes the check refuse the class it says it refuses.

    The values are written straight into ``register.json`` rather than through ``upsert_row``,
    which validates the phase and would refuse them. That is not a way around the test: the
    register is Git-ignored and sits inside every child's landing, so a direct file write is the
    access a child actually has, and it is the premise the dispatch receipt is sealed against.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()

    def plant_phase(value: str) -> None:
        path = REGISTER.register_path(repo)
        document = json.loads(path.read_text(encoding="utf-8"))
        document["rows"]["verifier-1"]["phase"] = value
        path.write_text(json.dumps(document), encoding="utf-8")

    _verifier_row(repo, phase="working")
    for phase in ("", "garbage", "launchd"):
        plant_phase(phase)
        assert REGISTER.read_rows(repo)["verifier-1"]["phase"] == phase
        result = prepared.evaluate(depth_sample=_sample(prepared, register=False))
        assert result.verified is False, phase
        assert result.reason == "depth_sample_invalid", phase
        assert "is not one of the phases past launch" in result.detail, phase

    assert COMPLETION.PHASES_PAST_LAUNCH == ("launched", "ready", "working", "verified", "reaped")
    assert "planned" not in COMPLETION.PHASES_PAST_LAUNCH
    assert "launching" not in COMPLETION.PHASES_PAST_LAUNCH


def test_a_depth_sample_from_another_run_is_not_this_runs_verifier(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()
    _verifier_row(repo, run_id="run-elsewhere")

    result = prepared.evaluate(depth_sample=_sample(prepared, register=False))
    assert result.verified is False
    assert result.reason == "depth_sample_invalid"
    assert "was dispatched for run" in result.detail


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("verifier_vendor", "codex", "its authenticated dispatch names"),
        ("verifier_model", "a-more-credible-model", "the register records"),
    ],
)
def test_a_depth_sample_misattributing_the_verifier_is_rejected(
    tmp_path: Path, field: str, value: str, expected: str
) -> None:
    """A sample cannot credit its read to a different session than the one that performed it."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()

    misattributed: dict[str, Any] = {field: value}
    result = prepared.evaluate(depth_sample=_sample(prepared, **misattributed))
    assert result.verified is False
    assert result.reason == "depth_sample_invalid"
    # Vendor is checked against the verifier's own authenticated dispatch; model is still checked
    # against a writable register column, and the two messages say which is which on purpose.
    assert expected in result.detail


def test_an_inconclusive_only_depth_sample_does_not_certify_judgment_work(
    tmp_path: Path,
) -> None:
    """Absence of a refutation is not a confirmation."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()

    inconclusive = COMPLETION.SampledClaim("no data is lost", "report.json:40", "inconclusive")
    result = prepared.evaluate(depth_sample=_sample(prepared, claims=(inconclusive,)))
    assert result.verified is False
    assert result.reason == "depth_sample_inconclusive"
    assert REGISTER.read_rows(repo)["child-a"]["phase"] == "working"


@pytest.mark.parametrize(
    "mapping",
    [
        {"claims": []},
        {"verifier_row_id": "v", "verifier_vendor": "grok", "verifier_model": "m"},
        {
            "verifier_row_id": "v",
            "verifier_vendor": "grok",
            "verifier_model": "m",
            "artifact_digest": "sha256:0",
            "claims": [{"claim": "", "evidence_location": "x", "disposition": "supported"}],
        },
        {
            "verifier_row_id": "v",
            "verifier_vendor": "grok",
            "verifier_model": "m",
            "artifact_digest": "sha256:0",
            "claims": [
                {"claim": "a", "evidence_location": "x", "disposition": "supported"},
                "not a claim at all",
            ],
        },
    ],
)
def test_a_malformed_depth_mapping_records_a_closed_failure_instead_of_raising(
    tmp_path: Path, mapping: dict[str, Any]
) -> None:
    """A control that raises instead of recording is a fail-open one level up.

    The register would otherwise still show a working child with no verdict, and neither
    ``failed_rows`` nor the next catch-up pass would list it.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()

    result = prepared.evaluate(depth_sample=mapping)
    assert result.verified is False
    assert result.reason == "depth_sample_invalid"
    assert REGISTER.read_rows(repo)["child-a"]["completion"]["result"] == "failed"
    assert COMPLETION.is_working_not_failed(repo, "child-a") is False


def test_a_verifier_reads_the_settled_artifact_and_the_second_evaluation_verifies(
    tmp_path: Path,
) -> None:
    """The reachable sequence for judgment work, end to end.

    The verifier contract requires a read of the *settled* artifact, and settlement happens
    inside evaluation -- so the first evaluation must leave the artifact settled and the child
    unverified, and the second must accept a sample taken against what is now on disk. This is
    the ordering that was previously unreachable: the second evaluation used to fail
    ``artifact_unsettled`` before it ever looked at the new sample.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()

    first = prepared.evaluate()
    assert first.verified is False
    assert first.reason == "depth_sample_missing"
    settled = prepared.receipt.artifact_path
    assert settled.is_file()
    assert not prepared.receipt.inflight_path.exists()

    # The verifier now reads the settled path -- the only artifact that exists at this point.
    digest = "sha256:" + hashlib.sha256(settled.read_bytes()).hexdigest()
    second = prepared.evaluate(depth_sample=_sample(prepared, artifact_digest=digest))
    assert second.verified is True, second.detail
    assert REGISTER.read_rows(repo)["child-a"]["phase"] == "verified"


# ------------------------------------------------- carried requirement: read-only landings


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
            spec,
            landing,
            _predicate("x"),
            artifact_name="report.json",
            git=git,
            changed_paths_baseline=_baseline(git, landing),
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


# ----------------------------------------------- failed predicate is not a new phase (3.1)


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


# -------------------------------------------------------------------------------- adapters


def test_the_git_adapter_reports_a_missing_revision_rather_than_raising(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    git = LIFECYCLE.GitLanding()
    assert git.rev_parse(repo, "no-such-branch") is None
    assert git.rev_parse(repo, "main") == git.base_commit(repo)


def test_the_git_adapter_answers_the_invisibility_question_not_the_ignore_rule_question(
    tmp_path: Path,
) -> None:
    """An ignore rule and invisibility to the boundary are different questions.

    A tracked path stays visible to ``git status`` and to the committed-diff comparison whatever
    the ignore rules say, so an artifact tree someone force-added is *not* outside the boundary
    even though ``git check-ignore`` still matches it.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    git = LIFECYCLE.GitLanding()
    assert git.is_invisible_to_boundary(repo, ".orchestrate/artifacts") is True
    assert git.is_invisible_to_boundary(repo, "src/thing.py") is False

    forced = repo / ".orchestrate" / "artifacts" / "run-a" / "child-a" / "report.json"
    forced.parent.mkdir(parents=True)
    forced.write_text("{}\n", encoding="utf-8")
    _git(repo, "add", "-f", ".orchestrate/artifacts")
    _git(repo, "commit", "-q", "-m", "an operator archives an artifact")
    assert git.is_invisible_to_boundary(repo, ".orchestrate/artifacts") is False


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


# ----------------------------------------- remaining members of each control's input class


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
    baseline = _baseline(git, landing)
    receipt = COMPLETION.issue_receipt(
        spec,
        landing,
        _predicate(relative.as_posix()),
        artifact_name="report.json",
        git=git,
        changed_paths_baseline=baseline,
    )
    return _Prepared(repo, spec, landing, git, receipt, baseline)


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


# ---------------------------------------------- the child process boundary and its posture


def test_no_runtimes_launch_posture_forbids_the_write_its_dispatch_requires(
    tmp_path: Path,
) -> None:
    """Every child is told to write an artifact, so no child may be launched unable to write.

    The launch posture is composed here the way the product composes it, from the specification
    through ``_runtime_resolution``, not by reading the table directly.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    git = LIFECYCLE.GitLanding()
    forbidding = {"read-only", "plan", "--disable-write"}
    for runtime in ("claude", "codex", "grok", "muse", "qwen", "agy"):
        spec = _spec(runtime=runtime, row_id=f"child-{runtime}", work_shape="scan-low")
        landing = git.provision(repo, spec)
        _, argv = LIFECYCLE._runtime_resolution(spec, landing)
        assert not forbidding.intersection(argv), (runtime, argv)
    assert LIFECYCLE.permission_argv("codex") == ["--sandbox", "workspace-write"]
    assert LIFECYCLE.permission_argv("grok") == ["--sandbox", "workspace"]
    assert LIFECYCLE.permission_argv("qwen") == ["--sandbox"]
    assert LIFECYCLE.permission_argv("agy") == ["--sandbox"]
    # Claude and Muse expose no positive flag at all; the empty list is the honest answer, not a
    # missing case, and the boundary check is what contains them.
    assert LIFECYCLE.permission_argv("claude") == []
    assert LIFECYCLE.permission_argv("muse") == []
    assert LIFECYCLE.permission_argv("unknown-runtime") == []


def test_a_deliverable_written_by_a_real_child_process_settles_and_verifies(
    tmp_path: Path,
) -> None:
    """The settlement protocol, executed by a process that is not the one asserting about it.

    What this does not establish: that a particular vendor's sandbox permits the write. No
    supported CLI is invoked here and none should be from a test. What it does establish is that
    a separate process, given only the dispatch text, produces something this module settles and
    verifies -- and the companion test below shows what happens when that process cannot write.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)

    completed = prepared.run_child_process()
    assert completed.returncode == 0, completed.stderr
    assert prepared.receipt.inflight_path.is_file()

    result = prepared.evaluate()
    assert result.verified is True, result.detail
    assert prepared.receipt.artifact_path.is_file()


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores file modes")
def test_a_child_process_that_cannot_write_its_artifact_directory_fails_completion(
    tmp_path: Path,
) -> None:
    """The failure a no-write launch posture produces, reproduced from a real child process.

    This is the shape of the defect the read-only posture caused: a well-behaved child, doing
    exactly what it was told, unable to create the file the protocol requires, and a completion
    that fails ``artifact_unsettled`` for a child that did nothing wrong.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    artifacts = prepared.receipt.artifact_path.parent
    artifacts.chmod(0o500)
    try:
        completed = prepared.run_child_process()
        assert completed.returncode != 0
        assert not prepared.receipt.inflight_path.exists()
        result = prepared.evaluate()
    finally:
        artifacts.chmod(0o700)
    assert result.verified is False
    assert result.reason == "artifact_unsettled"


def test_two_read_only_children_both_produce_their_deliverables_from_their_own_processes(
    tmp_path: Path,
) -> None:
    """The carried U4 requirement, with the child boundary crossed rather than assumed."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    first = _prepare(repo, row_id="child-a", scope=("reports/a",))
    second = _prepare(repo, row_id="child-b", scope=("reports/b",))
    assert first.run_child_process().returncode == 0
    assert second.run_child_process().returncode == 0

    first_result = first.evaluate()
    second_result = second.evaluate()
    assert first_result.verified is True, first_result.detail
    assert second_result.verified is True, second_result.detail
    assert first_result.scope is not None and first_result.scope.outside_scope == frozenset()
    assert second_result.scope is not None and second_result.scope.outside_scope == frozenset()


# -------------------------------------------------------------- the receipt's own identity


def test_a_receipt_issued_for_another_child_cannot_verify_this_one(tmp_path: Path) -> None:
    """A correctly bound artifact for one child must not become another child's pass."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    first = _prepare(repo, row_id="child-a")
    second = _prepare(repo, row_id="child-b")
    second.run_child_process()

    result = COMPLETION.evaluate_completion(
        first.spec, second.landing, second.baseline, second.receipt, git=second.git
    )
    assert result.verified is False
    assert result.reason == "receipt_mismatch"
    assert "row_id" in result.detail
    assert REGISTER.read_rows(repo)["child-a"].get("phase") == "working"


def test_a_receipt_from_another_run_cannot_verify_this_child(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.run_child_process()
    other_run = replace(prepared.spec, run_id="run-b")

    result = COMPLETION.evaluate_completion(
        other_run, prepared.landing, prepared.baseline, prepared.receipt, git=prepared.git
    )
    assert result.verified is False
    assert result.reason == "receipt_mismatch"
    assert "run_id" in result.detail


# ---------------------------------------------------- the durable receipt is authenticated


def _stored_receipt(repo: Path, row_id: str = "child-a") -> dict[str, Any]:
    return dict(REGISTER.read_rows(repo)[row_id]["dispatch_receipt"])


def test_a_restarted_orchestrator_evaluates_through_the_durable_receipt(
    tmp_path: Path,
) -> None:
    """The path the receipt is persisted for, exercised rather than assumed.

    Every other evaluation in this suite passes the in-memory receipt object, which is the one
    path a restart does not have.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.run_child_process()

    reloaded = COMPLETION.read_receipt(repo, "child-a")
    assert reloaded == prepared.receipt
    result = COMPLETION.evaluate_completion(
        prepared.spec, prepared.landing, prepared.baseline, reloaded, git=prepared.git
    )
    assert result.verified is True, result.detail


def test_a_planted_binding_token_in_the_register_does_not_authenticate(tmp_path: Path) -> None:
    """Forgery one: a child rewrites the expected identity to one it already holds."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    stored = _stored_receipt(repo)
    stored["binding_token"] = "ORCHESTRATE-ARTIFACT-BINDING:run-previous:child-a:old"
    REGISTER.upsert_row(repo, "child-a", {"dispatch_receipt": stored})
    prepared.receipt.inflight_path.write_text(
        json.dumps({"binding": stored["binding_token"], "conclusion": "done"}), encoding="utf-8"
    )

    with pytest.raises(COMPLETION.ReceiptAuthenticationError, match="did not authenticate"):
        COMPLETION.read_receipt(repo, "child-a")


def test_a_replaced_predicate_in_the_register_does_not_authenticate(tmp_path: Path) -> None:
    """Forgery two: a child swaps in a predicate that always passes and fixes up the digest."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    stored = _stored_receipt(repo)
    always_true = {"argv": ["/usr/bin/true"], "timeout_seconds": 5.0, "max_output_bytes": 1024}
    spec = COMPLETION.PredicateSpec.from_mapping(always_true)
    closure = COMPLETION.predicate_closure(Path(prepared.landing.cwd), spec)
    stored["predicate"] = always_true
    stored["predicate_closure"] = list(closure)
    stored["predicate_digest"] = COMPLETION.closure_digest(
        Path(prepared.landing.cwd), spec, closure
    )
    REGISTER.upsert_row(repo, "child-a", {"dispatch_receipt": stored})
    prepared.run_child_process()

    with pytest.raises(COMPLETION.ReceiptAuthenticationError, match="did not authenticate"):
        COMPLETION.read_receipt(repo, "child-a")


def test_a_receipt_with_an_added_field_does_not_authenticate(tmp_path: Path) -> None:
    """The digest covers the record as stored, so a smuggled key is a mismatch, not a no-op."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _prepare(repo)
    stored = _stored_receipt(repo)
    stored["smuggled"] = "ignored on the way back into the dataclass"
    REGISTER.upsert_row(repo, "child-a", {"dispatch_receipt": stored})

    with pytest.raises(COMPLETION.ReceiptAuthenticationError):
        COMPLETION.read_receipt(repo, "child-a")


def test_a_receipt_stripped_of_its_authentication_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _prepare(repo)
    stored = _stored_receipt(repo)
    stored.pop(COMPLETION.AUTHENTICATION_KEY)
    REGISTER.upsert_row(repo, "child-a", {"dispatch_receipt": stored})

    with pytest.raises(COMPLETION.ReceiptAuthenticationError, match="no authentication"):
        COMPLETION.read_receipt(repo, "child-a")


def test_a_receipt_naming_a_run_this_host_never_issued_is_refused(tmp_path: Path) -> None:
    """Naming another run changes which secret the digest must match, never whether one is needed."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _prepare(repo)
    stored = _stored_receipt(repo)
    stored["run_id"] = "run-invented"
    REGISTER.upsert_row(repo, "child-a", {"dispatch_receipt": stored})

    with pytest.raises(COMPLETION.RunSecretError, match="no orchestrator secret"):
        COMPLETION.read_receipt(repo, "child-a")


def test_a_forged_settlement_record_cannot_replay_a_direct_write(tmp_path: Path) -> None:
    """The settlement record is authenticated for the same reason the receipt is.

    Without that, a child writes the destination directly, plants a settlement record whose
    digest matches what it wrote, and this module replays a settlement that never happened.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    destination = prepared.receipt.artifact_path
    destination.write_text(
        json.dumps({"binding": prepared.receipt.binding_token, "conclusion": "done"}),
        encoding="utf-8",
    )
    REGISTER.upsert_row(
        repo,
        "child-a",
        {
            "settlement": {
                "nonce": prepared.receipt.nonce,
                "artifact_relpath": prepared.receipt.artifact_relpath,
                "artifact_path": str(destination),
                "digest": "sha256:" + hashlib.sha256(destination.read_bytes()).hexdigest(),
                "settled_at": time.time(),
                COMPLETION.AUTHENTICATION_KEY: "hmac-sha256:" + "0" * 64,
            }
        },
    )

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "artifact_unsettled"
    assert "did not authenticate" in result.detail


def test_a_run_secret_inside_the_repository_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every child's landing is inside the repository, so a secret there is a child-writable key."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    monkeypatch.setenv(COMPLETION.RUN_SECRET_DIR_ENV, str(repo / ".orchestrate" / "secrets"))
    with pytest.raises(COMPLETION.RunSecretError, match="inside the repository"):
        COMPLETION.run_secret(repo, "run-a")


def test_a_run_secret_readable_beyond_its_owner_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    COMPLETION.run_secret(repo, "run-a")
    key = COMPLETION.run_secret_dir() / "run-a.key"
    key.chmod(0o644)
    with pytest.raises(COMPLETION.RunSecretError, match="accessible beyond its owner"):
        COMPLETION.run_secret(repo, "run-a")


def test_the_run_secret_is_stable_for_a_run_and_distinct_between_runs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    first = COMPLETION.run_secret(repo, "run-a")
    assert COMPLETION.run_secret(repo, "run-a") == first
    assert COMPLETION.run_secret(repo, "run-b") != first
    assert len(first) == COMPLETION.RUN_SECRET_BYTES


# ------------------------------------------- the artifact path the catch-up consumer reads


def test_catch_up_does_not_ask_for_attention_before_the_child_has_settled(
    tmp_path: Path,
) -> None:
    """At issue time the artifact is required to be absent, so declaring it then is a false alarm.

    The shipped subscriber treats a declared artifact path that does not exist as an
    operator-attention signal. Every reconnect of every in-flight child would raise one.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    REGISTER.upsert_row(repo, "child-a", {"pane_id": "pane-a"})

    records = SUBSCRIBER.catch_up(
        repo,
        {"panes": [{"pane_id": "pane-a", "agent_status": "working"}], "agents": []},
        run_id="run-a",
    )
    assert [record.artifact_exists for record in records] == [None]

    prepared.run_child_process()
    assert prepared.evaluate().verified is True
    records = SUBSCRIBER.catch_up(
        repo,
        {"panes": [{"pane_id": "pane-a", "agent_status": "working"}], "agents": []},
        run_id="run-a",
    )
    assert [record.artifact_exists for record in records] == [True]


def test_catch_up_finds_a_mutating_childs_artifact_in_its_worktree(tmp_path: Path) -> None:
    """The consumer resolves a relative path against the ambient checkout; a worktree is not it."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _mutating_prepared(repo)
    worktree = Path(prepared.landing.cwd)
    (worktree / "src").mkdir()
    (worktree / "src" / "landed.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(worktree, "add", "src/landed.py")
    _git(worktree, "commit", "-q", "-m", "child work")
    prepared.run_child_process()
    assert prepared.evaluate().verified is True
    REGISTER.upsert_row(repo, "child-m", {"pane_id": "pane-m"})

    records = SUBSCRIBER.catch_up(
        repo,
        {"panes": [{"pane_id": "pane-m", "agent_status": "working"}], "agents": []},
        run_id="run-a",
    )
    assert [record.artifact_exists for record in records] == [True]


# --------------------------------------------------- re-evaluation and the phase invariant


def test_re_evaluating_an_unchanged_verified_child_reaches_the_same_verdict(
    tmp_path: Path,
) -> None:
    """Restart catch-up re-evaluates. Settlement is one-shot, so it must replay, not re-consume."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.run_child_process()

    assert prepared.evaluate().verified is True
    second = prepared.evaluate()
    assert second.verified is True, second.detail
    assert REGISTER.read_rows(repo)["child-a"]["phase"] == "verified"


def test_re_evaluating_a_mutating_child_replays_the_settlement_from_its_repository(
    tmp_path: Path,
) -> None:
    """The settlement record lives in the repository's register, never in the child's worktree.

    A mutating child's landing is a worktree, so the landing path and the repository are two
    different directories and only one of them has a register. Reading the settlement from the
    landing finds nothing, the replay never happens, and the second evaluation sees a destination
    that changed during the dispatch window -- a correct child failing on its second look, which is
    the restart path and the one judgment work depends on.

    Every other replay test uses a read-only child, where the two paths are the same and the
    distinction cannot be observed. This one exists because that made a wrong path invisible.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _mutating_prepared(repo)
    worktree = Path(prepared.landing.cwd)
    assert worktree != repo.resolve()
    (worktree / "src").mkdir()
    (worktree / "src" / "landed.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(worktree, "add", "src/landed.py")
    _git(worktree, "commit", "-q", "-m", "child work")
    prepared.run_child_process()

    assert prepared.evaluate().verified is True
    assert "settlement" in REGISTER.read_rows(repo)["child-m"]

    second = prepared.evaluate()
    assert second.verified is True, second.detail
    assert REGISTER.read_rows(repo)["child-m"]["phase"] == "verified"


def test_a_failing_re_evaluation_removes_the_verified_phase(tmp_path: Path) -> None:
    """A failed verdict must never coexist with a phase the reap gate reads as a pass."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.run_child_process()
    REGISTER.upsert_row(repo, "child-a", {"tab_id": "tab-a"})
    assert prepared.evaluate().verified is True
    assert REGISTER.read_rows(repo)["child-a"]["phase"] == "verified"

    prepared.receipt.artifact_path.write_text("tampered after the pass\n", encoding="utf-8")
    second = prepared.evaluate()
    assert second.verified is False
    row = REGISTER.read_rows(repo)["child-a"]
    assert row["completion"]["result"] == "failed"
    assert row["phase"] == "working"
    with pytest.raises(LIFECYCLE.SessionLifecycleError, match="must be verified before reap"):
        LIFECYCLE.reap_verified(repo, "child-a", herdr=FakeHerdr())


def test_a_reaped_row_is_not_demoted_by_a_later_evaluation(tmp_path: Path) -> None:
    """``reaped`` is past this question; the invariant is about ``verified``, not about history."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.run_child_process()
    REGISTER.upsert_row(repo, "child-a", {"tab_id": "tab-a"})
    assert prepared.evaluate().verified is True
    LIFECYCLE.reap_verified(repo, "child-a", herdr=FakeHerdr())

    prepared.receipt.artifact_path.write_text("tampered after the reap\n", encoding="utf-8")
    assert prepared.evaluate().verified is False
    assert REGISTER.read_rows(repo)["child-a"]["phase"] == "reaped"


# ------------------------------------------------------- what Python executes on an import


def _package_repo(repo: Path) -> None:
    _init_repo(repo)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "__init__.py").write_text("MARKER = 'genuine'\n", encoding="utf-8")
    (repo / "pkg" / "oracle.py").write_text("VERDICT = True\n", encoding="utf-8")
    (repo / "checks" / "package_check.py").write_text(
        "import sys\nimport pkg.oracle\nsys.exit(0 if pkg.oracle.VERDICT else 1)\n",
        encoding="utf-8",
    )
    _git(repo, "add", "pkg", "checks")
    _git(repo, "commit", "-q", "-m", "package")


def test_a_parent_package_initializer_is_in_the_closure(tmp_path: Path) -> None:
    """Python executes ``pkg/__init__.py`` before ``pkg/oracle.py``; the closure must say so."""
    repo = tmp_path / "repo"
    _package_repo(repo)
    predicate = COMPLETION.PredicateSpec(argv=(sys.executable, "checks/package_check.py"))

    closure = COMPLETION.predicate_closure(repo, predicate)
    assert "pkg/__init__.py" in closure
    assert "pkg/oracle.py" in closure


def test_a_child_that_may_rewrite_a_parent_initializer_cannot_be_certified_by_that_predicate(
    tmp_path: Path,
) -> None:
    """The initializer decides what the imported module resolves to, so it is predicate code."""
    repo = tmp_path / "repo"
    _package_repo(repo)
    spec = _spec(mutating=True, environment_command=(), scope=("pkg/__init__.py",))
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, spec)
    predicate = COMPLETION.PredicateSpec(argv=(sys.executable, "checks/package_check.py"))

    with pytest.raises(COMPLETION.PredicateScopeError, match="pkg/__init__.py"):
        COMPLETION.issue_receipt(
            spec,
            landing,
            predicate,
            artifact_name="report.json",
            git=git,
            changed_paths_baseline=_baseline(git, landing),
        )


def test_a_namespace_package_without_an_initializer_still_resolves(tmp_path: Path) -> None:
    """A missing initializer is not an error; PEP 420 packages simply contribute no such file."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "ns").mkdir()
    (repo / "ns" / "leaf.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "checks" / "ns_check.py").write_text("import ns.leaf\n", encoding="utf-8")
    predicate = COMPLETION.PredicateSpec(argv=(sys.executable, "checks/ns_check.py"))

    closure = COMPLETION.predicate_closure(repo, predicate)
    assert "ns/leaf.py" in closure


# ------------------------------------------- the observer can see the evidence it protects


def test_a_predicate_that_rewrites_the_settled_artifact_fails_as_a_side_effect(
    tmp_path: Path,
) -> None:
    """The artifact directory is invisible to Git by design, so Git status cannot police it.

    Before this, a predicate could rewrite the settled file after its digest was taken and still
    return a pass, leaving a recorded digest that no longer matched the bytes on disk.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "checks" / "rewriter.py").write_text(
        "import pathlib, sys\npathlib.Path(sys.argv[1]).write_text('FORGED-AFTER-BIND')\n",
        encoding="utf-8",
    )
    _git(repo, "add", "checks/rewriter.py")
    _git(repo, "commit", "-q", "-m", "rewriting predicate")
    spec = _spec()
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, spec)
    REGISTER.upsert_row(repo, "child-a", {"run_id": "run-a", "phase": "working"})
    artifacts = COMPLETION.artifact_landing(Path(landing.cwd), "run-a", "child-a")
    relative = (artifacts.relative_to(Path(landing.cwd).resolve()) / "report.json").as_posix()
    predicate = COMPLETION.PredicateSpec(argv=(sys.executable, "checks/rewriter.py", relative))
    receipt = COMPLETION.issue_receipt(
        spec,
        landing,
        predicate,
        artifact_name="report.json",
        git=git,
        changed_paths_baseline=_baseline(git, landing),
    )
    prepared = _Prepared(repo, spec, landing, git, receipt, _baseline(git, landing))
    prepared.run_child_process()

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "predicate_side_effect"
    assert "report.json" in result.detail
    assert prepared.receipt.artifact_path.read_text(encoding="utf-8") == "FORGED-AFTER-BIND"


# ----------------------------------------------- tracked artifacts are refused at dispatch


def test_a_force_added_artifact_tree_is_refused_at_issue_not_blamed_on_the_child(
    tmp_path: Path,
) -> None:
    """An operator's ``git add -f`` used to fail every later child on the boundary check.

    Refusing at issue time makes it one actionable message before dispatch instead of a control
    firing on the orchestrator's own rename.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.run_child_process()
    assert prepared.evaluate().verified is True
    _git(repo, "add", "-f", ".orchestrate/artifacts")
    _git(repo, "commit", "-q", "-m", "an operator archives the artifact")

    with pytest.raises(COMPLETION.LandingNotExclusiveError, match="git rm -r --cached"):
        _prepare(repo, row_id="child-a")


# ------------------------------------------------------- the default nobody was exercising


def test_the_default_environment_command_installs_what_a_predicate_needs(tmp_path: Path) -> None:
    """A default nothing exercises is untested, and the default is what most callers get.

    ``uv sync`` without ``--extra dev`` produces a worktree with no pytest, ruff or mypy -- the
    exact programs a predicate is most likely to be -- and this field exists precisely because a
    fresh worktree cannot otherwise run the predicate at all.
    """
    spec = LIFECYCLE.ChildSpec(
        run_id="run-a",
        row_id="child-a",
        runtime="codex",
        work_shape="mechanical",
        instruction="Produce the deliverable.",
        scope=("src",),
        mutating=True,
        workspace="workspace-a",
    )
    assert spec.environment_command == ("uv", "sync", "--locked", "--extra", "dev")
    # The same helper that masked the environment default masks this one: every lifecycle test
    # overrides it. Pinning the value is the minimum a default in a public signature deserves.
    assert spec.readiness_timeout == 30.0

    invoked: list[list[str]] = []

    def runner(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        invoked.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, "", "")

    repo = tmp_path / "repo"
    _init_repo(repo)
    real = LIFECYCLE.GitLanding()

    def recording(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if argv[:1] == ["git"]:
            return subprocess.run(argv, **kwargs)
        return runner(argv, **kwargs)

    real.runner = recording
    real.provision(repo, spec)
    assert ["uv", "sync", "--locked", "--extra", "dev"] in invoked


def test_the_unfiltered_failed_rows_view_spans_every_run(tmp_path: Path) -> None:
    """``run_id=None`` is the default, and it was the one shape no test constructed.

    The operator's "what stalled" view is most useful unfiltered -- several runs can hold live
    rows in one register at once -- so the default is the call most real callers make.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    first = _prepare(repo, row_id="child-a")
    first.write_deliverable({"binding": first.receipt.binding_token})
    first.evaluate()
    second = _prepare(repo, row_id="child-b", run_id="run-b")
    second.write_deliverable({"binding": second.receipt.binding_token})
    second.evaluate()

    assert sorted(COMPLETION.failed_rows(repo)) == ["child-a", "child-b"]
    assert sorted(COMPLETION.failed_rows(repo, run_id="run-b")) == ["child-b"]


# ---- the receipt binds every input the evaluator branches on ------------------------------
#
# The class here is not "the identity labels". It is the mechanical answer to "what does
# evaluate_completion read before deciding?", and taking that answer needs two passes in this
# order: enumerate the signature, then the attribute reads. Collecting `spec.`/`landing.` reads
# finds everything hanging off an object and cannot see a plain parameter -- which is how the
# repository root, the first argument, stayed off a list that was being called complete. The
# parameterised cases below substitute an attribute; the root has its own cases further down,
# because it is refused by raising rather than by a recorded verdict.


def _substitute(prepared: _Prepared, label: str) -> tuple[Any, Any, Any]:
    """Return (spec, landing, baseline) with exactly one deciding input replaced."""
    spec, landing, baseline = prepared.spec, prepared.landing, prepared.baseline
    if label == "runtime":
        spec = replace(spec, runtime="grok")
    elif label == "work_shape":
        # The receipt was issued for judgment work; a mechanical shape skips the depth gate.
        spec = replace(spec, work_shape="mechanical")
    elif label == "mutating":
        spec = replace(spec, mutating=True)
    elif label == "scope":
        spec = replace(spec, scope=("src", "reports"))
    elif label == "integration_mode":
        landing = replace(landing, integration_mode="path")
    elif label == "destination":
        landing = replace(landing, destination="somewhere-else")
    elif label == "base_commit":
        landing = replace(landing, base_commit="0" * 40)
    elif label == "ambient_root":
        landing = replace(landing, ambient_root=prepared.repo / "elsewhere")
    else:  # pragma: no cover - a label with no substitution is a test bug
        raise AssertionError(label)
    return spec, landing, baseline


@pytest.mark.parametrize(
    "label",
    [
        "runtime",
        "work_shape",
        "mutating",
        "scope",
        "integration_mode",
        "destination",
        "base_commit",
        "ambient_root",
    ],
)
def test_every_deciding_input_is_bound_to_the_receipt(tmp_path: Path, label: str) -> None:
    """One case per input the evaluator branches on, each failing if its comparison is removed.

    Binding run, row and landing stops one child's evidence verifying another child's row and
    stops nothing else. A receipt issued for judgment work verified under a mechanical shape; an
    out-of-scope write verified under a widened scope. Each of these arrives as a separate
    argument, so each is sealed and compared.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()
    spec, landing, baseline = _substitute(prepared, label)

    result = COMPLETION.evaluate_completion(
        spec, landing, baseline, prepared.receipt, git=prepared.git
    )
    assert result.verified is False
    assert result.reason == "receipt_mismatch"
    assert label in result.detail
    assert REGISTER.read_rows(repo)["child-a"]["phase"] == "working"


def test_a_widened_scope_cannot_excuse_a_write_the_dispatch_forbade(tmp_path: Path) -> None:
    """The reproduction, rather than the label: an out-of-scope write under a broadened scope."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, scope=("reports/a",))
    prepared.run_child_process()
    stray = repo / "reports" / "b" / "notes.md"
    stray.parent.mkdir(parents=True)
    stray.write_text("outside the declared scope\n", encoding="utf-8")

    widened = replace(prepared.spec, mutating=True, scope=("reports",))
    result = COMPLETION.evaluate_completion(
        widened, prepared.landing, prepared.baseline, prepared.receipt, git=prepared.git
    )
    assert result.verified is False
    assert result.reason == "receipt_mismatch"


def test_a_baseline_taken_after_the_write_it_would_excuse_is_refused(tmp_path: Path) -> None:
    """A baseline is repository state at an instant, and the landing does not say which instant.

    The same landing has different, equally valid snapshots before and after a write, so binding
    the landing says nothing about when the snapshot was taken. Re-taking the baseline after an
    out-of-scope write makes that write invisible to the boundary check.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, scope=("reports/a",))
    prepared.run_child_process()
    stray = repo / "reports" / "a" / "notes.md"
    stray.parent.mkdir(parents=True)
    stray.write_text("written into the shared checkout\n", encoding="utf-8")

    # With the bound baseline this is a boundary violation, which is the honest verdict.
    assert prepared.evaluate().reason == "scope_violation"

    # With a baseline taken after the write, the violation disappears -- so the substitution is
    # refused before the boundary check ever runs.
    laundered = _baseline(prepared.git, prepared.landing)
    result = COMPLETION.evaluate_completion(
        prepared.spec, prepared.landing, laundered, prepared.receipt, git=prepared.git
    )
    assert result.verified is False
    assert result.reason == "receipt_mismatch"
    assert "changed_paths_baseline" in result.detail


def test_the_bound_baseline_digest_distinguishes_two_snapshots_of_one_landing(
    tmp_path: Path,
) -> None:
    """The digest is the binding, so it must move when the snapshot does and not otherwise."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    git = LIFECYCLE.GitLanding()
    spec = _spec()
    landing = git.provision(repo, spec)
    before = _baseline(git, landing)
    assert COMPLETION.baseline_digest(before) == COMPLETION.baseline_digest(_baseline(git, landing))

    (repo / "reports").mkdir()
    (repo / "reports" / "note.md").write_text("a change\n", encoding="utf-8")
    assert COMPLETION.baseline_digest(_baseline(git, landing)) != COMPLETION.baseline_digest(before)


def test_the_receipt_round_trip_preserves_every_deciding_input(tmp_path: Path) -> None:
    """Whatever is sealed must survive the register, or the restart path compares a different set."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment", scope=("reports/a",))
    reloaded = COMPLETION.read_receipt(repo, "child-a")
    assert reloaded == prepared.receipt
    assert reloaded.root == str(repo.resolve())
    assert reloaded.work_shape == "judgment"
    assert reloaded.scope == ("reports/a",)
    assert reloaded.mutating is False
    assert reloaded.runtime == "codex"
    assert reloaded.baseline_digest == COMPLETION.baseline_digest(prepared.baseline)


# ---- the predicate's descendants ----------------------------------------------------------

_DESCENDANT_PREDICATE = """\
import subprocess
import sys

# A predicate that passes immediately and leaves something behind to rewrite the evidence.
subprocess.Popen(
    [
        sys.executable,
        "-c",
        "import sys, time; time.sleep(float(sys.argv[1])); "
        "open(sys.argv[2], 'w').write('FORGED-BY-DESCENDANT')",
        sys.argv[2],
        sys.argv[1],
    ]
)
sys.exit(0)
"""


def _descendant_prepared(repo: Path, delay: str) -> _Prepared:
    (repo / "checks" / "spawner.py").write_text(_DESCENDANT_PREDICATE, encoding="utf-8")
    _git(repo, "add", "checks/spawner.py")
    _git(repo, "commit", "-q", "-m", "a predicate that outlives itself")
    spec = _spec()
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, spec)
    REGISTER.upsert_row(repo, "child-a", {"run_id": "run-a", "phase": "working"})
    artifacts = COMPLETION.artifact_landing(Path(landing.cwd), "run-a", "child-a")
    relative = (artifacts.relative_to(Path(landing.cwd).resolve()) / "report.json").as_posix()
    predicate = COMPLETION.PredicateSpec(
        argv=(sys.executable, "checks/spawner.py", relative, delay)
    )
    baseline = _baseline(git, landing)
    receipt = COMPLETION.issue_receipt(
        spec,
        landing,
        predicate,
        artifact_name="report.json",
        git=git,
        changed_paths_baseline=baseline,
    )
    return _Prepared(repo, spec, landing, git, receipt, baseline)


def test_a_predicate_descendant_cannot_rewrite_the_evidence_after_the_pass(
    tmp_path: Path,
) -> None:
    """Waiting for the direct process only establishes that *that* process finished.

    A descendant outlives it, is reparented away, and writes after the after-snapshot has already
    certified the evidence -- so completion recorded a pass whose durable digest no longer matched
    the file. The predicate now runs in its own process group and the group is killed before this
    returns, so "the predicate has finished" includes everything it started.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _descendant_prepared(repo, delay="1.0")
    prepared.run_child_process()

    result = prepared.evaluate()
    assert result.verified is True, result.detail
    recorded = str(result.artifact_digest)

    # Well past the descendant's delay: if anything survived the kill, it has written by now.
    time.sleep(2.0)
    on_disk = "sha256:" + hashlib.sha256(prepared.receipt.artifact_path.read_bytes()).hexdigest()
    assert on_disk == recorded
    assert b"FORGED-BY-DESCENDANT" not in prepared.receipt.artifact_path.read_bytes()


def test_a_descendant_that_writes_before_the_kill_is_still_observed(tmp_path: Path) -> None:
    """The kill closes the window; it does not replace the observation that covers it."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _descendant_prepared(repo, delay="0")
    prepared.run_child_process()

    result = prepared.evaluate()
    if result.verified:
        # The descendant lost the race and was killed before writing: the evidence is intact,
        # which is the other honest outcome of the same control.
        assert b"FORGED-BY-DESCENDANT" not in prepared.receipt.artifact_path.read_bytes()
    else:
        assert result.reason == "predicate_side_effect"


def test_a_descendant_outlives_its_parent_and_the_group_kill_is_what_ends_it(
    tmp_path: Path,
) -> None:
    """The production shape, with no predicate involved: leader exits, descendant does not.

    This is the mechanism the artifact test depends on. A group leader that spawns a child and
    exits leaves that child running and reparented, so the group is *not* empty once the leader
    has been waited for -- which is exactly the window in which the old code took its
    after-snapshot and called the evidence certified.
    """
    leader = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-c",
            "import subprocess, sys; "
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
            "sys.exit(0)",
        ],
        start_new_session=True,
    )
    leader.wait()
    try:
        assert COMPLETION._process_group_is_empty(leader.pid) is False
        assert COMPLETION._drain_process_group(leader.pid, timeout=5.0) is True
        assert COMPLETION._process_group_is_empty(leader.pid) is True
    finally:
        COMPLETION._kill_process_group(leader.pid)


def test_a_predicate_whose_group_will_not_die_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A defensive branch that a real process cannot reach, pinned by forcing the condition.

    Nothing on this host survives SIGKILL long enough to exercise this for real, so the drain
    result is forced. What is being pinned is the decision -- an undrained group is a refusal,
    not a pass -- not the drain mechanism, which the helper test covers.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.run_child_process()
    monkeypatch.setattr(COMPLETION, "_drain_process_group", lambda *a, **k: False)

    result = prepared.evaluate()
    assert result.verified is False
    assert result.reason == "predicate_descendants"
    # The explanation lives on the predicate outcome, which is what the register persists.
    assert result.predicate is not None
    assert "did not stop" in result.predicate.output


# ---- `reaped` is terminal in both directions ----------------------------------------------


def test_a_passing_re_evaluation_does_not_resurrect_a_reaped_row(tmp_path: Path) -> None:
    """The demotion half of the phase invariant was tested; the promotion half was not.

    Catch-up re-evaluates run-bound artifacts on startup, a reaped child still has a settlement
    record and a file on disk, and settlement replays cleanly -- so a closed tab came back as a
    live `verified` child and the next vanish check raised on its missing tab.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.run_child_process()
    REGISTER.upsert_row(repo, "child-a", {"tab_id": "tab-a"})
    assert prepared.evaluate().verified is True
    LIFECYCLE.reap_verified(repo, "child-a", herdr=FakeHerdr())
    assert REGISTER.read_rows(repo)["child-a"]["phase"] == "reaped"

    second = prepared.evaluate()
    assert second.verified is True, second.detail
    row = REGISTER.read_rows(repo)["child-a"]
    assert row["phase"] == "reaped"
    assert row["completion"]["result"] == "verified"
    # The vanish check must not see a live verified child whose tab is closed.
    LIFECYCLE.assert_child_not_vanished(repo, "child-a", herdr=FakeHerdr())


@pytest.mark.parametrize("passing", [True, False])
def test_a_reaped_row_keeps_its_phase_whichever_way_the_verdict_goes(
    tmp_path: Path, passing: bool
) -> None:
    """Both members of the branch `_record` takes on a terminal phase."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    prepared.run_child_process()
    REGISTER.upsert_row(repo, "child-a", {"tab_id": "tab-a"})
    assert prepared.evaluate().verified is True
    LIFECYCLE.reap_verified(repo, "child-a", herdr=FakeHerdr())
    if not passing:
        prepared.receipt.artifact_path.write_text("tampered after the reap\n", encoding="utf-8")

    result = prepared.evaluate()
    assert result.verified is passing
    assert REGISTER.read_rows(repo)["child-a"]["phase"] == "reaped"


# ---- the verifier must be a dispatch this orchestrator issued -----------------------------


def test_a_planted_verifier_row_does_not_satisfy_the_verifier_check(tmp_path: Path) -> None:
    """A column-only check certifies exactly the store the sealed records exist because we distrust.

    A write-capable child can plant a row with the right run, phase, vendor and model. Requiring
    an authenticated dispatch receipt is the part it cannot forge -- and without this the forgery
    was *more* convincing once the sample was persisted, because the planted identity went into
    the durable completion record.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()
    _verifier_row(repo, "planted-verifier", dispatched=False)

    result = prepared.evaluate(
        depth_sample=_sample(prepared, register=False, verifier_row_id="planted-verifier")
    )
    assert result.verified is False
    assert result.reason == "depth_sample_invalid"
    assert "carries no dispatch this orchestrator issued" in result.detail
    assert REGISTER.read_rows(repo)["child-a"].get("phase") == "working"


def test_a_verifier_whose_receipt_was_tampered_with_is_not_a_session(tmp_path: Path) -> None:
    """The verifier's dispatch is authenticated, so editing it is the same refusal as editing any."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()
    sample = _sample(prepared)
    stored = dict(REGISTER.read_rows(repo)["verifier-1"]["dispatch_receipt"])
    stored["runtime"] = "an-invented-vendor"
    REGISTER.upsert_row(repo, "verifier-1", {"dispatch_receipt": stored})

    result = prepared.evaluate(depth_sample=sample)
    assert result.verified is False
    assert result.reason == "depth_sample_invalid"
    assert "carries no dispatch this orchestrator issued" in result.detail


def test_a_relaundered_baseline_is_caught_when_only_a_fingerprint_moved(tmp_path: Path) -> None:
    """The path set alone does not distinguish two snapshots of the same landing.

    A file that was already dirty when the child started is in both baselines, so re-taking the
    snapshot after the child modifies it changes no path — only that path's content fingerprint.
    A digest over names would call the two snapshots identical and let the modification through.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    already_dirty = repo / "reports" / "a" / "notes.md"
    already_dirty.parent.mkdir(parents=True)
    already_dirty.write_text("present before the child started\n", encoding="utf-8")

    prepared = _prepare(repo, scope=("reports/a",))
    prepared.run_child_process()
    already_dirty.write_text("modified during the child's window\n", encoding="utf-8")

    laundered = _baseline(prepared.git, prepared.landing)
    assert set(laundered.paths) == set(prepared.baseline.paths)
    assert COMPLETION.baseline_digest(laundered) != COMPLETION.baseline_digest(prepared.baseline)

    result = COMPLETION.evaluate_completion(
        prepared.spec, prepared.landing, laundered, prepared.receipt, git=prepared.git
    )
    assert result.verified is False
    assert result.reason == "receipt_mismatch"
    assert "changed_paths_baseline" in result.detail


# ---- the operator-facing surfaces do not call detection "containment" ---------------------


def _flowed(relative: str) -> str:
    """Markdown and docstrings wrap, so compare on whitespace-collapsed prose."""
    return " ".join((ROOT / relative).read_text(encoding="utf-8").split()).lower()


_SURFACES = (
    "plugins/orchestrate/README.md",
    "plugins/orchestrate/references/predicates.md",
    "plugins/orchestrate/references/substrate-contract.md",
    "plugins/orchestrate/skills/orchestrate/SKILL.md",
)


def test_no_surface_calls_the_boundary_check_containment() -> None:
    """The boundary check observes after the fact; it does not prevent a write.

    Telling an operator that it "contains" a child inside the workspace describes a control that
    does not exist: it runs after the child has stopped, reports rather than blocks, sees only
    tracked and non-ignored paths, and cannot establish authorship in a shared checkout. A child
    that writes a Git-ignored workspace path outside its artifact directory produces no violation
    at all. "Containment" belongs to the runtime posture, which really does prevent writes outside
    the workspace.
    """

    for relative in _SURFACES:
        text = _flowed(relative)
        assert "containment inside the workspace is the boundary check" not in text, relative
        assert "what contains a child *inside* the workspace is the boundary check" not in text
    detection = _flowed("plugins/orchestrate/references/predicates.md")
    assert "post-hoc, partial, repository-visible change detection" in detection
    assert "reports rather than prevents" in detection
    posture = _flowed("plugins/orchestrate/skills/orchestrate/scripts/session_lifecycle.py")
    assert "post-hoc, partial, repository-visible change detection" in posture
    assert "the only *containment* in the word's real sense" in posture


# ---- the repository is derived, never supplied beside the receipt --------------------------


def _second_repository(tmp_path: Path, prepared: _Prepared, **columns: Any) -> Path:
    """A second repository whose own bookkeeping happens to use the same row id."""
    other = tmp_path / "repo-b"
    _init_repo(other)
    REGISTER.upsert_row(other, prepared.spec.row_id, {"run_id": "run-b", **columns})
    return other


def test_the_repository_is_not_an_argument_a_caller_can_supply(tmp_path: Path) -> None:
    """The deletion itself, pinned on the signature.

    Successive rounds added a comparison here, and each caught the case it was written for while
    the class stayed open, because every one of them compared a supplied repository against the
    copy made from that same supplied value at issue time. That catches a caller who changes it
    between issuing and evaluating. It cannot catch one that was wrong when it was copied -- and
    the copy is made at issuance, which is the first observation and therefore has nothing to
    compare against at all.

    So the parameter is gone rather than checked: issuance derives the repository from the
    landing and refuses a landing that is not the same git repository as that store, and every
    later control takes the sealed value off the receipt. Evaluation still has two objects that
    name a repository; it raises rather than records when the landing does not belong to the
    receipt's.
    """
    for name in ("issue_receipt", "evaluate_completion", "settle_artifact", "settlement_record"):
        parameters = inspect.signature(getattr(COMPLETION, name)).parameters
        assert "root" not in parameters, f"{name} takes a repository a caller could disagree with"

    # One exception, and it is why ``assert_receipt_root`` still exists: this function is handed a
    # repository and a row id and has no receipt yet, so the repository has to be supplied. There
    # the two values have independent origins, which is what makes comparing them a real check.
    assert "root" in inspect.signature(COMPLETION.read_receipt).parameters


def test_a_receipt_records_the_repository_of_the_landing_it_was_issued_against(
    tmp_path: Path,
) -> None:
    """Issuance has one source for the repository, so the receipt cannot be sealed against another.

    A second repository stands beside this one, carrying a row under the same id, and the only
    thing that decides where the dispatch is filed is the landing the receipt is issued against.
    The verdict follows it there and nothing lands in the other repository at any point.
    """
    repo = tmp_path / "repo-a"
    _init_repo(repo)
    prepared = _prepare(repo)
    other = _second_repository(tmp_path, prepared, phase="working", expected_state="working")

    assert prepared.receipt.root == str(repo.resolve())
    assert prepared.receipt.root == str(Path(prepared.landing.ambient_root).resolve())

    # The sealed receipt went into its own repository's register; the other one has no dispatch.
    assert COMPLETION.read_receipt(repo, prepared.spec.row_id).nonce == prepared.receipt.nonce
    assert "dispatch_receipt" not in REGISTER.read_rows(other)[prepared.spec.row_id]

    prepared.run_child_process()
    result = prepared.evaluate()
    assert result.verified is True, result.detail
    assert REGISTER.read_rows(repo)[prepared.spec.row_id]["phase"] == "verified"

    foreign = REGISTER.read_rows(other)[prepared.spec.row_id]
    assert foreign["phase"] == "working"
    assert "completion" not in foreign
    assert "settlement" not in foreign


def test_a_mutating_childs_receipt_records_the_repository_and_not_its_worktree(
    tmp_path: Path,
) -> None:
    """The landing carries two paths and only one of them has a register.

    ``cwd`` is where the child works, which for a mutating child is a worktree under
    ``.orchestrate/`` that no other part of the run reads. ``ambient_root`` is the checkout the run
    is actually tracked in. Deriving from the nearer path would be the original defect in a new
    place: the verdict filed where nothing else about the run is recorded.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, mutating=True, environment_command=())

    assert Path(prepared.landing.cwd) != repo.resolve()
    assert prepared.receipt.root == str(repo.resolve())
    assert COMPLETION.landing_root(prepared.landing, git=prepared.git) == repo.resolve()


def test_a_landing_that_does_not_name_its_repository_cannot_be_issued_a_receipt(
    tmp_path: Path,
) -> None:
    """Refused at issuance rather than defaulted to the working directory.

    ``ambient_root`` is optional on the landing type, so a hand-built landing can omit it. A
    fallback to ``cwd`` would look harmless on a read-only landing, where the two paths are the
    same, and would quietly seal a mutating child's worktree as its repository. A refusal is the
    only answer to "which repository is this?" that cannot be wrong.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    spec = _spec()
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, spec)
    anonymous = LIFECYCLE.Landing(
        landing.cwd, landing.integration_mode, landing.destination, landing.base_commit
    )
    assert anonymous.ambient_root is None

    with pytest.raises(COMPLETION.ReceiptRootError) as raised:
        COMPLETION.issue_receipt(
            spec,
            anonymous,
            _predicate("x"),
            artifact_name="report.json",
            git=git,
            changed_paths_baseline=_baseline(git, landing),
        )
    assert "does not name the repository" in str(raised.value)


def test_a_landing_cannot_name_a_repository_it_does_not_belong_to(tmp_path: Path) -> None:
    """cwd and ambient_root are independently settable; issuance refuses when they disagree.

    Deriving the repository from ambient_root removed the parameter and left the pair on the
    type. A receipt sealed from those two fields is internally consistent, so every later
    comparison agrees -- a check of a value against a copy of that value. Membership is the
    git common directory at each path, not whether one path is a descendant of the other.

    Sibling checkouts: issuance raises, neither register gains a receipt or a completion, and
    the artifact is not settled.
    """
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    _init_repo(repo_a)
    _init_repo(repo_b)
    spec = _spec()
    git = LIFECYCLE.GitLanding()
    honest = git.provision(repo_a, spec)
    poisoned = replace(honest, ambient_root=repo_b.resolve())
    REGISTER.upsert_row(
        repo_b,
        spec.row_id,
        {"run_id": spec.run_id, "phase": "working", "expected_state": "working"},
    )
    artifacts = COMPLETION.artifact_landing(Path(poisoned.cwd), spec.run_id, spec.row_id)
    relative = artifacts.relative_to(Path(poisoned.cwd).resolve()) / "report.json"

    with pytest.raises(
        COMPLETION.ReceiptRootError, match="does not belong to the repository"
    ) as raised:
        COMPLETION.issue_receipt(
            spec,
            poisoned,
            _predicate(relative.as_posix()),
            artifact_name="report.json",
            git=git,
            changed_paths_baseline=_baseline(git, poisoned),
        )
    assert str(repo_b.resolve()) in str(raised.value)

    with pytest.raises(COMPLETION.ReceiptRootError, match="does not belong to the repository"):
        COMPLETION.landing_root(poisoned, git=git)

    assert spec.row_id not in REGISTER.read_rows(repo_a)
    row_b = REGISTER.read_rows(repo_b)[spec.row_id]
    assert row_b["phase"] == "working"
    assert "dispatch_receipt" not in row_b
    assert "completion" not in row_b
    assert not (artifacts / "report.json").exists()


def test_evaluating_with_another_repositorys_receipt_raises_and_writes_neither_register(
    tmp_path: Path,
) -> None:
    """A receipt from another repository cannot select that repository's register.

    Repository A holds an honest verified child. Repository B holds a child with the same row
    id, evaluated with A's authentic receipt. The false pass is already refused. The remaining
    harm is the false write: recording the mismatch under A demotes A's verified row, and
    recording it under B still writes a verdict into a store this pairing has no business
    touching once the two arguments disagree about the repository. The caller sees the
    exception. A's verified row stays verified. B stays working and has no completion record.
    """
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    _init_repo(repo_a)
    _init_repo(repo_b)
    spec = _spec()
    git = LIFECYCLE.GitLanding()

    landing_a = git.provision(repo_a, spec)
    REGISTER.upsert_row(
        repo_a,
        spec.row_id,
        {"run_id": spec.run_id, "phase": "working", "expected_state": "working"},
    )
    artifacts_a = COMPLETION.artifact_landing(Path(landing_a.cwd), spec.run_id, spec.row_id)
    rel_a = artifacts_a.relative_to(Path(landing_a.cwd).resolve()) / "report.json"
    baseline_a = _baseline(git, landing_a)
    receipt_a = COMPLETION.issue_receipt(
        spec,
        landing_a,
        _predicate(rel_a.as_posix()),
        artifact_name="report.json",
        git=git,
        changed_paths_baseline=baseline_a,
    )
    prepared_a = _Prepared(repo_a, spec, landing_a, git, receipt_a, baseline_a)
    prepared_a.run_child_process()
    first = COMPLETION.evaluate_completion(spec, landing_a, baseline_a, receipt_a, git=git)
    assert first.verified is True, first.detail
    assert REGISTER.read_rows(repo_a)[spec.row_id]["phase"] == "verified"

    landing_b = git.provision(repo_b, spec)
    REGISTER.upsert_row(
        repo_b,
        spec.row_id,
        {"run_id": spec.run_id, "phase": "working", "expected_state": "working"},
    )
    baseline_b = _baseline(git, landing_b)
    prepared_b = _Prepared(repo_b, spec, landing_b, git, receipt_a, baseline_b)
    prepared_b.run_child_process()

    with pytest.raises(
        COMPLETION.ReceiptRootError, match="does not belong to the repository"
    ) as raised:
        COMPLETION.evaluate_completion(spec, landing_b, baseline_b, receipt_a, git=git)
    assert str(Path(receipt_a.root).resolve()) in str(raised.value)

    row_a = REGISTER.read_rows(repo_a)[spec.row_id]
    row_b = REGISTER.read_rows(repo_b)[spec.row_id]
    assert row_a["phase"] == "verified"
    assert (row_a.get("completion") or {}).get("result") == "verified"
    assert row_b["phase"] == "working"
    assert "completion" not in row_b


def _nested_repositories(tmp_path: Path) -> tuple[Path, Path]:
    """An independent git repository living inside another independent git repository."""
    outer = tmp_path / "outer"
    nested = outer / "nested"
    _init_repo(outer)
    _init_repo(nested)
    return outer, nested


def test_a_nested_repository_is_not_the_checkout_that_contains_it(tmp_path: Path) -> None:
    """Path ancestry is not membership: a nested checkout is a descendant and a different store.

    Issuance of a landing that works in the nested repository and names the outer one as its
    store must refuse before it writes the outer register. The nested path sits inside the
    outer path, so a descendant check accepts this pairing and files a durable pass in the
    wrong repository.
    """
    outer, nested = _nested_repositories(tmp_path)
    spec = _spec()
    git = LIFECYCLE.GitLanding()
    honest = git.provision(nested, spec)
    poisoned = replace(honest, ambient_root=outer.resolve())
    REGISTER.upsert_row(
        outer, spec.row_id, {"run_id": spec.run_id, "phase": "working", "expected_state": "working"}
    )
    artifacts = COMPLETION.artifact_landing(Path(poisoned.cwd), spec.run_id, spec.row_id)
    relative = artifacts.relative_to(Path(poisoned.cwd).resolve()) / "report.json"

    with pytest.raises(COMPLETION.ReceiptRootError, match="does not belong to the repository"):
        COMPLETION.issue_receipt(
            spec,
            poisoned,
            _predicate(relative.as_posix()),
            artifact_name="report.json",
            git=git,
            changed_paths_baseline=_baseline(git, poisoned),
        )
    with pytest.raises(COMPLETION.ReceiptRootError, match="does not belong to the repository"):
        COMPLETION.landing_root(poisoned, git=git)

    row_outer = REGISTER.read_rows(outer)[spec.row_id]
    assert row_outer["phase"] == "working"
    assert "dispatch_receipt" not in row_outer
    assert "completion" not in row_outer
    assert spec.row_id not in REGISTER.read_rows(nested)
    assert not (artifacts / "report.json").exists()


def test_evaluating_a_nested_repository_with_the_containing_checkouts_receipt_writes_neither(
    tmp_path: Path,
) -> None:
    """A nested checkout's landing must not select the containing checkout's register.

    The outer repository holds an honest verified child. The nested repository holds a child
    with the same row id, evaluated with the outer receipt. Path ancestry lets that pairing
    through and the mismatch refusal demotes the outer row. Membership refuses; the outer
    verified row stays verified; the nested row gains no completion.
    """
    outer, nested = _nested_repositories(tmp_path)
    spec = _spec()
    git = LIFECYCLE.GitLanding()

    landing_outer = git.provision(outer, spec)
    REGISTER.upsert_row(
        outer, spec.row_id, {"run_id": spec.run_id, "phase": "working", "expected_state": "working"}
    )
    artifacts_outer = COMPLETION.artifact_landing(Path(landing_outer.cwd), spec.run_id, spec.row_id)
    rel_outer = artifacts_outer.relative_to(Path(landing_outer.cwd).resolve()) / "report.json"
    baseline_outer = _baseline(git, landing_outer)
    receipt_outer = COMPLETION.issue_receipt(
        spec,
        landing_outer,
        _predicate(rel_outer.as_posix()),
        artifact_name="report.json",
        git=git,
        changed_paths_baseline=baseline_outer,
    )
    _Prepared(outer, spec, landing_outer, git, receipt_outer, baseline_outer).run_child_process()
    first = COMPLETION.evaluate_completion(
        spec, landing_outer, baseline_outer, receipt_outer, git=git
    )
    assert first.verified is True, first.detail
    assert REGISTER.read_rows(outer)[spec.row_id]["phase"] == "verified"

    landing_nested = git.provision(nested, spec)
    REGISTER.upsert_row(
        nested,
        spec.row_id,
        {"run_id": spec.run_id, "phase": "working", "expected_state": "working"},
    )
    artifacts_nested = COMPLETION.artifact_landing(
        Path(landing_nested.cwd), spec.run_id, spec.row_id
    )
    rel_nested = artifacts_nested.relative_to(Path(landing_nested.cwd).resolve()) / "report.json"
    baseline_nested = _baseline(git, landing_nested)
    COMPLETION.issue_receipt(
        spec,
        landing_nested,
        _predicate(rel_nested.as_posix()),
        artifact_name="report.json",
        git=git,
        changed_paths_baseline=baseline_nested,
    )

    with pytest.raises(COMPLETION.ReceiptRootError, match="does not belong to the repository"):
        COMPLETION.evaluate_completion(
            spec, landing_nested, baseline_nested, receipt_outer, git=git
        )

    row_outer = REGISTER.read_rows(outer)[spec.row_id]
    row_nested = REGISTER.read_rows(nested)[spec.row_id]
    assert row_outer["phase"] == "verified"
    assert (row_outer.get("completion") or {}).get("result") == "verified"
    assert row_nested["phase"] == "working"
    assert "completion" not in row_nested


def test_a_linked_worktree_belongs_to_the_repository_it_was_cut_from(tmp_path: Path) -> None:
    """A mutating child's worktree shares the main checkout's object store.

    A stricter check that required the working directory to be the repository root, or to match
    provision's path layout by string, would refuse this landing. Membership must accept it.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, mutating=True, environment_command=())
    assert Path(prepared.landing.cwd) != repo.resolve()
    assert Path(prepared.landing.cwd).is_relative_to(repo.resolve())
    assert COMPLETION.landing_root(prepared.landing, git=prepared.git) == repo.resolve()
    # Issuance already wrote the receipt under the main checkout. The evaluate-time
    # check must accept the same pairing; a root-only or exact-layout predicate
    # refuses it before any verdict is recorded.
    COMPLETION.assert_landing_in_receipt_repository(
        prepared.landing, prepared.receipt, git=prepared.git
    )
    assert prepared.receipt.root == str(repo.resolve())


def test_a_subdirectory_of_the_same_repository_still_belongs(tmp_path: Path) -> None:
    """An ordinary subdirectory of the same checkout is still that checkout.

    Stated residual on the working-directory side. The store-side residual is the opposite
    shape -- a subdirectory named as the store -- and is refused below.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src").mkdir()
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, _spec())
    inside = replace(landing, cwd=repo / "src")
    assert COMPLETION.landing_root(inside, git=git) == repo.resolve()


def _linked_worktree(repo: Path, name: str) -> Path:
    path = repo.parent / name
    _git(repo, "worktree", "add", "-q", "-b", f"branch-{name}", str(path))
    return path


def _issue_honest(repo: Path, spec: Any, git: Any) -> tuple[Any, Any, Any]:
    landing = git.provision(repo, spec)
    REGISTER.upsert_row(
        repo, spec.row_id, {"run_id": spec.run_id, "phase": "working", "expected_state": "working"}
    )
    artifacts = COMPLETION.artifact_landing(Path(landing.cwd), spec.run_id, spec.row_id)
    relative = artifacts.relative_to(Path(landing.cwd).resolve()) / "report.json"
    baseline = _baseline(git, landing)
    receipt = COMPLETION.issue_receipt(
        spec,
        landing,
        _predicate(relative.as_posix()),
        artifact_name="report.json",
        git=git,
        changed_paths_baseline=baseline,
    )
    return landing, baseline, receipt


@pytest.mark.parametrize(
    "store_kind",
    ["sibling-worktree", "other-worktree", "subdirectory"],
)
def test_a_store_that_is_not_the_run_register_is_refused_at_issue(
    tmp_path: Path, store_kind: str
) -> None:
    """The store is a register directory, not a repository.

    Three shapes that share the object store with the work and are not the run's
    register: a sibling linked worktree, another worktree of the same repository,
    and a subdirectory of the checkout. Each is refused before the register is written.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src").mkdir()
    spec = _spec()
    git = LIFECYCLE.GitLanding()
    COMPLETION.record_run_root(repo, spec.run_id)
    honest = git.provision(repo, spec)
    if store_kind == "sibling-worktree":
        store = _linked_worktree(repo, "side-tree")
    elif store_kind == "other-worktree":
        first = _linked_worktree(repo, "side-tree")
        store = _linked_worktree(repo, "side-tree-2")
        honest = replace(honest, cwd=first)
    else:
        store = repo / "src"
    poisoned = replace(honest, ambient_root=store.resolve())
    REGISTER.upsert_row(
        store, spec.row_id, {"run_id": spec.run_id, "phase": "working", "expected_state": "working"}
    )
    artifacts = COMPLETION.artifact_landing(Path(poisoned.cwd), spec.run_id, spec.row_id)
    relative = artifacts.relative_to(Path(poisoned.cwd).resolve()) / "report.json"

    with pytest.raises(COMPLETION.ReceiptRootError):
        COMPLETION.issue_receipt(
            spec,
            poisoned,
            _predicate(relative.as_posix()),
            artifact_name="report.json",
            git=git,
            changed_paths_baseline=_baseline(git, poisoned),
        )
    row = REGISTER.read_rows(store).get(spec.row_id, {})
    assert "dispatch_receipt" not in row
    assert "completion" not in row
    assert spec.row_id not in REGISTER.read_rows(repo)


@pytest.mark.parametrize(
    "store_kind",
    ["sibling-worktree", "other-worktree", "subdirectory"],
)
def test_a_store_that_is_not_the_run_register_is_refused_at_evaluation(
    tmp_path: Path, store_kind: str
) -> None:
    """Evaluating against a receipt whose store is the wrong working tree writes neither register."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src").mkdir()
    spec = _spec()
    git = LIFECYCLE.GitLanding()
    if store_kind == "sibling-worktree":
        store = _linked_worktree(repo, "side-tree")
    elif store_kind == "other-worktree":
        store = _linked_worktree(repo, "side-tree-2")
    else:
        store = repo / "src"
    _, _, receipt = _issue_honest(store, spec, git)
    landing_work = git.provision(repo, spec)
    baseline_work = _baseline(git, landing_work)

    with pytest.raises(COMPLETION.ReceiptRootError):
        COMPLETION.evaluate_completion(spec, landing_work, baseline_work, receipt, git=git)
    assert "completion" not in REGISTER.read_rows(store).get(spec.row_id, {})
    work_row = REGISTER.read_rows(repo).get(spec.row_id, {})
    assert "completion" not in work_row


def test_a_recorded_run_root_that_disagrees_with_the_claimed_store_is_refused(
    tmp_path: Path,
) -> None:
    """The new property, independent of any path relationship between cwd and store."""
    repo = tmp_path / "repo"
    other = tmp_path / "other"
    _init_repo(repo)
    _init_repo(other)
    spec = _spec()
    git = LIFECYCLE.GitLanding()
    COMPLETION.record_run_root(repo, spec.run_id)
    landing = git.provision(other, spec)
    REGISTER.upsert_row(
        other, spec.row_id, {"run_id": spec.run_id, "phase": "working", "expected_state": "working"}
    )
    artifacts = COMPLETION.artifact_landing(Path(landing.cwd), spec.run_id, spec.row_id)
    relative = artifacts.relative_to(Path(landing.cwd).resolve()) / "report.json"
    with pytest.raises(COMPLETION.ReceiptRootError, match="not the register directory recorded"):
        COMPLETION.issue_receipt(
            spec,
            landing,
            _predicate(relative.as_posix()),
            artifact_name="report.json",
            git=git,
            changed_paths_baseline=_baseline(git, landing),
        )
    assert "dispatch_receipt" not in REGISTER.read_rows(other)[spec.row_id]


def test_a_run_with_no_recorded_root_does_not_mint_one_from_the_landing(tmp_path: Path) -> None:
    """In-flight runs keep working; the landing is not promoted to the run root.

    Containment and git identity still run. The class those two close is smaller than
    the property: a mutating child's worktree has five ancestor stores that pass both.
    This test pins the decision -- accept, and do not write the record.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    spec = _spec()
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, spec)
    assert COMPLETION.read_run_root(spec.run_id) is None
    REGISTER.upsert_row(
        repo, spec.row_id, {"run_id": spec.run_id, "phase": "working", "expected_state": "working"}
    )
    artifacts = COMPLETION.artifact_landing(Path(landing.cwd), spec.run_id, spec.row_id)
    relative = artifacts.relative_to(Path(landing.cwd).resolve()) / "report.json"
    receipt = COMPLETION.issue_receipt(
        spec,
        landing,
        _predicate(relative.as_posix()),
        artifact_name="report.json",
        git=git,
        changed_paths_baseline=_baseline(git, landing),
    )
    assert receipt.root == str(repo.resolve())
    assert receipt.run_root is None
    assert COMPLETION.read_run_root(spec.run_id) is None


def test_a_read_only_child_still_verifies_against_the_recorded_root(tmp_path: Path) -> None:
    """The legitimate read-only shape, both directions: issue and evaluate."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo)
    assert prepared.receipt.run_root == str(repo.resolve())
    prepared.run_child_process()
    result = prepared.evaluate()
    assert result.verified is True, result.detail


def test_membership_probes_ignore_an_inherited_git_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GIT_DIR makes every checkout report the same object store. The probe must not inherit it."""
    outer, nested = _nested_repositories(tmp_path)
    monkeypatch.setenv("GIT_DIR", str((outer / ".git").resolve()))
    monkeypatch.setenv("GIT_COMMON_DIR", str((outer / ".git").resolve()))
    git = LIFECYCLE.GitLanding()
    spec = _spec()
    honest = git.provision(nested, spec)
    poisoned = replace(honest, ambient_root=outer.resolve())
    with pytest.raises(COMPLETION.ReceiptRootError):
        COMPLETION.landing_root(poisoned, git=git)
    assert COMPLETION._same_repository(git, nested, outer) is False


def test_a_receipt_copied_into_another_repositorys_register_is_refused_when_it_is_read(
    tmp_path: Path,
) -> None:
    """The seal is intact and it is still the wrong register.

    Reading is the one place a repository must be supplied, because the receipt is being fetched
    rather than handed over. The per-run secret does not close this on its own: it is named for
    the run alone and stored outside every repository, so two checkouts running one run id share
    it and a receipt sealed under either authenticates under both. Nothing else in the unseal path
    mentions a repository, which is why the sealed one has to be checked against the register it
    came out of.
    """
    repo = tmp_path / "repo-a"
    _init_repo(repo)
    other = tmp_path / "repo-b"
    _init_repo(other)
    prepared = _prepare(repo)
    sealed = REGISTER.read_rows(repo)[prepared.spec.row_id]["dispatch_receipt"]
    REGISTER.upsert_row(
        other,
        prepared.spec.row_id,
        {"run_id": prepared.spec.run_id, "dispatch_receipt": sealed},
    )

    with pytest.raises(COMPLETION.ReceiptRootError) as raised:
        COMPLETION.read_receipt(other, prepared.spec.row_id)
    assert "issued under" in str(raised.value)

    # The same bytes read out of the register that issued them are accepted, so the refusal is
    # about which repository asked and not about the record being damaged by the copy.
    assert COMPLETION.read_receipt(repo, prepared.spec.row_id).nonce == prepared.receipt.nonce


def test_a_verifier_dispatched_in_another_repository_does_not_satisfy_the_depth_gate(
    tmp_path: Path,
) -> None:
    """The verifier's receipt is the one this module fetches rather than receives.

    Every other receipt arrives as an argument and carries the repository the verdict lands in.
    The verifier's is loaded by row id out of whatever register is being evaluated, so a genuine
    verifier dispatch from another checkout of the same run authenticates here -- the seal proves
    the orchestrator issued it, and the secret is shared by run id across repositories.
    """
    repo = tmp_path / "repo-a"
    _init_repo(repo)
    other = tmp_path / "repo-b"
    _init_repo(other)

    # Repository A dispatches a real verifier and holds an authentic sealed receipt for it.
    _verifier_row(repo, "verifier-1", dispatched=True, phase="working", record_root=False)
    foreign = REGISTER.read_rows(repo)["verifier-1"]["dispatch_receipt"]

    # Repository B runs the same run and has no verifier of its own, so it borrows A's.
    prepared = _prepare(other, work_shape="judgment")
    prepared.run_child_process()
    REGISTER.upsert_row(
        other,
        "verifier-1",
        {
            "run_id": prepared.spec.run_id,
            "vendor": "grok",
            "model": "grok-4.6",
            "phase": "working",
            "dispatch_receipt": foreign,
        },
    )

    result = prepared.evaluate(
        depth_sample=_sample(prepared, register=False, verifier_row_id="verifier-1")
    )
    assert result.verified is False
    assert result.reason == "depth_sample_invalid"
    assert "issued under" in result.detail
    assert REGISTER.read_rows(other)[prepared.spec.row_id]["phase"] != "verified"


# ---- what the verifier check establishes, and where it stops -------------------------------


def test_moving_the_unsealed_verifier_phase_presents_a_verifier_that_never_ran(
    tmp_path: Path,
) -> None:
    """Documented behaviour rather than a refusal, because the code cannot refuse it.

    The verifier's dispatch is sealed and its vendor comes from that seal, so a planted row is
    caught. Whether the verifier *ran* is answered from ``phase``, which is an ordinary register
    column that any write-capable actor can set -- the same untrusted store the dispatch receipt
    is sealed against. So a verifier with a genuine receipt that never started is refused while
    the column reads ``planned``, and accepted the moment the column reads ``working``.

    Closing this needs evidence observed after launch, and both observers are other units: the
    launch transition and the liveness stream. This test exists so the claim in the surfaces and
    the behaviour of the code say the same thing.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    prepared = _prepare(repo, work_shape="judgment")
    prepared.run_child_process()
    _verifier_row(repo, "verifier-1", dispatched=True, phase="planned")

    refused = prepared.evaluate(
        depth_sample=_sample(prepared, register=False, verifier_row_id="verifier-1")
    )
    assert refused.verified is False
    assert refused.reason == "depth_sample_invalid"
    assert "is not one of the phases past launch" in refused.detail

    REGISTER.upsert_row(repo, "verifier-1", {"phase": "working"})
    accepted = prepared.evaluate(
        depth_sample=_sample(prepared, register=False, verifier_row_id="verifier-1")
    )
    assert accepted.verified is True, accepted.detail
    assert REGISTER.read_rows(repo)["child-a"]["completion"]["depth_sample"] is not None


#: Sentences that would be false about the verifier check, in any file that mentions it.
#:
#: These are bans rather than requirements because a *presence* assertion cannot detect a
#: contradiction. Requiring a disclaimer somewhere in a file is satisfied by one honest paragraph,
#: and leaves every overclaiming sentence elsewhere in that same file green -- which is exactly
#: how a class docstring four hundred lines from the disclaimer went on calling the persisted
#: sample a proven blind read while the test that exists to catch that passed.
_VERIFIER_OVERCLAIMS = (
    "verifier's blind read",
    "a blind read of",
    "proves the verifier ran",
    "proof that the verifier ran",
    "establishes that the verifier ran",
    "confirms that the verifier ran",
    "an independent verifier's depth sample",
)

#: Phrasings that claim path ancestry, or a previous check, closed repository membership.
#: A presence assertion that the honest sentence is somewhere in the file cannot detect these.
_MEMBERSHIP_OVERCLAIMS = (
    "cannot do so and remain internally consistent",
    "the two remaining pairs are closed",
    "two remaining pairs are closed",
)


def test_no_surface_claims_the_verifier_check_proves_the_verifier_ran() -> None:
    """The columns the check reads are named as columns, wherever the check is described.

    Two halves, and only the first can catch a contradiction. The bans say the overclaim is
    absent from every surface that could carry it; the presence assertions say the honest
    statement is still there on the surfaces that describe the check. Deleting the honest
    paragraph fails the second half; adding a contradiction beside it fails the first.

    The ban list has a known weakness, and it is the same one twice over: it catches the phrasings
    someone thought of. It is a floor, not a proof.
    """
    described_in = (
        "plugins/orchestrate/references/predicates.md",
        "plugins/orchestrate/CHANGELOG.md",
        "plugins/orchestrate/skills/orchestrate/SKILL.md",
        "plugins/orchestrate/skills/orchestrate/scripts/completion.py",
    )
    for relative in (*described_in, *_SURFACES):
        text = _flowed(relative)
        for phrase in _VERIFIER_OVERCLAIMS:
            assert phrase not in text, f"{relative} claims {phrase!r}"

    # One sentence, worded identically everywhere, so the four surfaces cannot drift into four
    # different sizes of the same claim. Three of them said something slightly smaller or larger
    # than the others at some point in this build, and each difference had to be found by reading.
    established = "a verifier was dispatched in this repository, for this run, with this vendor"
    for relative in described_in:
        text = _flowed(relative)
        assert "not that it ran" in text or "does not establish that the verifier ran" in text, (
            relative
        )
        assert established in text, relative
    contract = _flowed("plugins/orchestrate/references/predicates.md")
    assert "the same defect against two different columns of the same untrusted store" in contract


def test_no_surface_claims_path_ancestry_closed_repository_membership() -> None:
    """A descendant path can be a different git repository.

    The honest sentence (membership is the common directory) can sit next to a sentence that
    still says the pair is closed or that a landing cannot name another repository and remain
    consistent. Presence of the honest sentence cannot detect that.
    """
    surfaces = (
        *_SURFACES,
        "plugins/orchestrate/CHANGELOG.md",
        "plugins/orchestrate/skills/orchestrate/scripts/completion.py",
        "docs/engineering-journal/DECISIONS.md",
        "docs/engineering-journal/LEARNINGS.md",
    )
    for relative in surfaces:
        text = _flowed(relative)
        for phrase in _MEMBERSHIP_OVERCLAIMS:
            assert phrase not in text, f"{relative} claims {phrase!r}"
        assert "cannot do so and remain internally consistent" not in text, relative


def test_every_identity_paragraph_describes_the_argument_list_the_evaluator_takes() -> None:
    """Three paragraphs describe the same list and one of them was updated at a time.

    The module's opening contract is the first thing a reader of ``completion.py`` meets, the
    skill paragraph is what a later unit implements from, and the reference is what a reviewer
    checks against. When one is edited and its siblings are not, the file that is wrong is
    whichever one the next person happens to read -- and a later unit implementing the stale
    paragraph would pass a repository the evaluator no longer accepts.

    So the count and the deletion are asserted on all three, together, rather than left to a
    reading pass that has to be repeated whenever the signature moves.
    """
    module_doc = " ".join((COMPLETION.__doc__ or "").split())
    skill = _flowed("plugins/orchestrate/skills/orchestrate/SKILL.md")
    contract = _flowed("plugins/orchestrate/references/predicates.md")

    for text, label in (
        (module_doc, "completion.py module docstring"),
        (skill, "SKILL.md"),
        (contract, "predicates.md"),
    ):
        assert "four independent arguments" in text, label
        assert "raises rather than records" in text, label
    for text, label in ((module_doc, "completion.py module docstring"), (skill, "SKILL.md")):
        assert "specification, landing, baseline and receipt" in text, label
        assert "not a fifth" in text, label
    assert "**derived, not supplied**" in contract


def test_the_persisted_depth_sample_type_describes_a_claim_and_not_a_proven_read() -> None:
    """The object a later unit actually reads is the one whose name has to be honest.

    A downstream unit reading ``completion.depth_sample`` off a verified row does not read the
    reference document or the check's docstring; it reads this type. Naming it a blind read tells
    that unit two things the module does not establish -- that the read happened, and that it was
    blind -- and blindness is a named non-enforcement in this same module.
    """
    doc = " ".join((COMPLETION.DepthSample.__doc__ or "").split())
    assert doc, "the persisted sample type carries no description at all"
    assert "claimed" in doc
    assert "does not establish that the verifier ran" in doc
    for phrase in _VERIFIER_OVERCLAIMS:
        assert phrase not in doc, phrase


# ---- the group kill covers the group, and the prose says so --------------------------------


def test_no_surface_claims_the_group_kill_ends_everything_the_predicate_started() -> None:
    """A descendant that calls ``setsid`` leaves the group and outlives the kill.

    The residual table already says so. The sentences introducing it claimed a totality the table
    denies, which is the more dangerous half: a reader who stops at the claim never reaches the
    table.

    The third phrasing was an internal comment two lines above the kill, which the first two bans
    could not see. That is this test's standing weakness and it is worth saying out loud: banning
    the sentences someone wrote is not the same as establishing that no sentence overclaims. Each
    ban is a phrasing that was actually in the file and had to be narrowed, not a guess.
    """
    for relative in (
        "plugins/orchestrate/references/predicates.md",
        "plugins/orchestrate/skills/orchestrate/scripts/completion.py",
    ):
        text = _flowed(relative)
        assert "after the kill there is nothing left to write" not in text, relative
        assert "nothing the predicate started is still able to write" not in text, relative
        assert "nothing the predicate started may outlive it" not in text, relative
    contract = _flowed("plugins/orchestrate/references/predicates.md")
    assert "group membership is the whole of the claim" in contract
    assert 'narrower than "nothing can still write"' in contract


def test_the_release_notes_do_not_promote_a_sealed_field_into_a_compared_one() -> None:
    """The changelog listed a field that is sealed and deliberately never compared.

    An operator reading it would believe `write_scope` is a check that can fire, and three
    consistency fields are deciding inputs. Both are the same overclaim as the prose defects above,
    one surface further out: the detailed reference had it right and the release notes did not
    catch up.
    """
    notes = _flowed("plugins/orchestrate/CHANGELOG.md")
    assert "`write_scope` is sealed and deliberately **not** compared" in notes
    assert "as consistency fields rather than deciding inputs" in notes
    # The same two statements in the document the release notes summarise, so the pair cannot
    # drift apart again without one of these failing.
    contract = _flowed("plugins/orchestrate/references/predicates.md")
    assert "`write_scope` is sealed and deliberately **not** compared" in contract
    assert "calling them deciding inputs would be" in contract
