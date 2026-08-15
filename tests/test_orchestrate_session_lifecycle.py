"""Contract tests for orchestrate U4 session lifecycle behavior."""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace
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
EVENTS = _load("herdr_events")
SUBSCRIBER = _load("subscriber")
LIFECYCLE = _load("session_lifecycle")


def _record(root: Path, run_id: str) -> Path:
    directory = Path(str(REGISTER.register_dir()))
    path = directory / f"{run_id}.root"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(Path(root).resolve()), encoding="utf-8")
    path.chmod(384)
    return path


def _spec(**overrides: Any) -> Any:
    values = {
        "run_id": "run-a",
        "row_id": "child-a",
        "runtime": "codex",
        "work_shape": "work-high",
        "instruction": "Implement the bounded task.",
        "scope": ("src",),
        "mutating": False,
        "workspace": "workspace-a",
        "readiness_timeout": 0.1,
        "environment_command": (),
    }
    values.update(overrides)
    return LIFECYCLE.ChildSpec(**values)


IDENTITY = None


@pytest.fixture(autouse=True)
def _identity() -> None:
    global IDENTITY
    IDENTITY = LIFECYCLE.LaunchIdentity("actual-child", "workspace-a", "tab-a", "pane-a", True)


@pytest.fixture(autouse=True)
def _orchestrator_secret_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep per-run records out of the operator's home, and outside the test root.

    ``launch_child`` records the run root next to the run secret. The secret directory
    is refused if it sits inside the repository, and these tests use ``tmp_path`` as
    that repository, so the directory must be a sibling, not a child.
    """
    monkeypatch.setenv(
        "ORCHESTRATE_RUN_SECRET_DIR", str(tmp_path.parent / f"{tmp_path.name}-run-secrets")
    )
    monkeypatch.setenv(
        "ORCHESTRATE_REGISTER_DIR", str(tmp_path.parent / f"{tmp_path.name}-registers")
    )


class FakeGit:
    def __init__(self, root: Path, paths: list[frozenset[str]] | None = None) -> None:
        self.root = root
        self.paths = list(paths or [frozenset()])
        self.provisioned: list[Any] = []

    def base_commit(self, _root: Path) -> str:
        return "fake-base"

    def provision(self, _root: Path, spec: Any, *, base_commit: str | None = None) -> Any:
        self.provisioned.append(spec)
        return LIFECYCLE.Landing(self.root, "none", "none", base_commit, self.root)

    def changed_paths(self, _cwd: Path) -> frozenset[str]:
        return self.paths.pop(0) if len(self.paths) > 1 else self.paths[0]

    def observed_paths(
        self, cwd: Path, *, base_commit: str | None, upstream_commit: str | None = None
    ) -> frozenset[str]:
        return self.changed_paths(cwd)

    def fingerprint(self, _cwd: Path, _path: str) -> str:
        return "fake"

    def changed_paths_baseline(
        self, cwd: Path, *, base_commit: str | None = None, ambient_root: Path | None = None
    ) -> Any:
        paths = self.changed_paths(cwd)
        return LIFECYCLE.ChangedPathsBaseline(paths, tuple((path, "fake") for path in paths))


class FakeWrapper:
    def __init__(self, *, launch_error: Exception | None = None) -> None:
        self.launch_error = launch_error
        self.launches = 0
        self.previews = 0
        self.before_launch: Callable[[str], None] | None = None

    def preview(self, spec: Any, landing: Any, label: str, argv: list[str]) -> None:
        self.previews += 1

    def launch(self, spec: Any, landing: Any, label: str, argv: list[str]) -> Any:
        self.launches += 1
        if self.before_launch is not None:
            self.before_launch(label)
        if self.launch_error is not None:
            raise self.launch_error
        return IDENTITY


class FakeHerdr:
    def __init__(self) -> None:
        self.discovered = None
        self.text = "ready prompt"
        self.thinking_disabled = False
        self.sent: list[str] = []
        self.closed: list[str] = []
        self.present = True
        self.presence_checks = 0

    def discover_by_label(self, label: str, *, cwd: Path) -> Any:
        return self.discovered

    def pane_text(self, pane_id: str, *, cwd: Path) -> str:
        return self.text

    def send_line(self, pane_id: str, text: str, *, cwd: Path) -> None:
        self.sent.append(text)
        if text.startswith("/effort "):
            effort = text.split(maxsplit=1)[1]
            if self.thinking_disabled:
                self.text += f"\nReasoning effort set to {effort}, but thinking is currently disabled — it will take effect when thinking is re-enabled."
            else:
                self.text += f"\nReasoning effort: {effort} (requested; the effective tier depends on the active provider/model)."

    def close_tab(self, tab_id: str, *, cwd: Path) -> None:
        row = REGISTER.read_rows(cwd, run_id="run-a")["child-a"]
        assert row["phase"] == "reaped"
        self.closed.append(tab_id)

    def tab_present(self, tab_id: str, *, cwd: Path) -> bool:
        self.presence_checks += 1
        return self.present


class FakeInteraction:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.matches: list[str] = []
        self.accept_calls = 0

    def observe(
        self, *, pane_id: str, match: str, timeout: float, dispatch: Any, accept: Any = None
    ) -> Any:
        self.matches.append(match)
        baseline = dispatch()
        if self.fail:
            raise LIFECYCLE.NotReadyError("bounded readiness timeout")
        event = SimpleNamespace(revision=0)
        if accept is not None:
            self.accept_calls += 1
            assert accept(event, baseline)
        return (event, baseline)


def _launch(tmp_path: Path, spec: Any | None = None, **kwargs: Any) -> Any:
    child = spec or _spec()
    wrapper = kwargs.pop("wrapper", FakeWrapper())
    herdr = kwargs.pop("herdr", FakeHerdr())
    git = kwargs.pop("git", FakeGit(tmp_path))
    return LIFECYCLE.launch_child(tmp_path, child, wrapper=wrapper, herdr=herdr, git=git)


def test_register_row_and_run_label_exist_before_a_failing_launch(tmp_path: Path) -> None:
    wrapper = FakeWrapper(launch_error=RuntimeError("launch exploded"))

    def assert_write_ahead(label: str) -> None:
        row = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
        assert row["task"] == label == "orchestrate-run-a-child-a"
        assert row["phase"] == "launching"

    wrapper.before_launch = assert_write_ahead
    with pytest.raises(RuntimeError, match="launch exploded"):
        _launch(tmp_path, wrapper=wrapper)
    assert wrapper.launches == 1
    assert REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]["phase"] == "launching"


def test_launch_records_the_run_register_directory(tmp_path: Path) -> None:
    """The run's store is this argument, recorded before any landing exists."""
    _launch(tmp_path)
    import completion as completion_mod

    assert completion_mod.read_run_root("run-a") == tmp_path.resolve()


def test_planned_row_exists_before_mutating_worktree_provision(tmp_path: Path) -> None:

    class FailingProvisionGit(FakeGit):
        def provision(self, root: Path, spec: Any, *, base_commit: str | None = None) -> Any:
            row = REGISTER.read_rows(root, run_id="run-a")[spec.row_id]
            assert row["phase"] == "planned"
            assert row["task"] == "orchestrate-run-a-child-a"
            assert row["scope"] == ["src"]
            assert row["base_commit"] == "fake-base"
            raise LIFECYCLE.LandingError("environment setup failed")

    with pytest.raises(LIFECYCLE.LandingError, match="environment setup failed"):
        _launch(tmp_path, _spec(mutating=True), git=FailingProvisionGit(tmp_path))
    assert REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]["phase"] == "planned"


def test_retry_discovers_written_label_after_crash_before_identifier_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapper = FakeWrapper()
    herdr = FakeHerdr()
    original = REGISTER.upsert_row
    crashed = False

    def crash_before_identifiers(root: Path, row_id: str, fields: Any, **kwargs: Any) -> Any:
        nonlocal crashed
        if not crashed and "pane_id" in fields:
            crashed = True
            herdr.discovered = IDENTITY
            raise RuntimeError("crash after side effect")
        return original(root, row_id, fields, **kwargs)

    monkeypatch.setattr(REGISTER, "upsert_row", crash_before_identifiers)
    with pytest.raises(RuntimeError, match="crash after side effect"):
        _launch(tmp_path, wrapper=wrapper, herdr=herdr)
    recovered, _landing, _resolution = _launch(tmp_path, wrapper=wrapper, herdr=herdr)
    assert recovered == IDENTITY
    assert wrapper.launches == 1
    assert REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]["pane_id"] == "pane-a"


def test_launch_without_sentinel_is_not_ready_not_running(tmp_path: Path) -> None:
    child = _spec()
    identity, landing, resolution = _launch(tmp_path, child)
    herdr = FakeHerdr()
    with pytest.raises(LIFECYCLE.NotReadyError, match="readiness timeout"):
        LIFECYCLE.confirm_ready(
            tmp_path,
            child,
            identity,
            landing,
            resolution,
            herdr=herdr,
            interaction=FakeInteraction(fail=True),
            git=FakeGit(tmp_path),
            sentinel_nonce="timeout",
        )
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    assert row["phase"] == "launched"
    assert row["observed_state"] == "not_ready"
    assert row["observed_state_source"] == "inferred:readiness_timeout"


def test_trust_prompt_is_surfaced_before_any_dispatch(tmp_path: Path) -> None:
    child = _spec()
    identity, landing, resolution = _launch(tmp_path, child)
    herdr = FakeHerdr()
    herdr.text = "Do you trust the files in this workspace?"
    interaction = FakeInteraction()
    with pytest.raises(LIFECYCLE.TrustPromptError, match="trust prompt"):
        LIFECYCLE.confirm_ready(
            tmp_path,
            child,
            identity,
            landing,
            resolution,
            herdr=herdr,
            interaction=interaction,
            git=FakeGit(tmp_path),
        )
    assert interaction.matches == []
    assert herdr.sent == []
    assert (
        REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]["observed_state"] == "trust_prompt"
    )


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.com")
    _git(repo, "config", "user.name", "Tests")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".orchestrate/\n", encoding="utf-8")
    _git(repo, "add", "README.md", ".gitignore")
    _git(repo, "commit", "-q", "-m", "seed")


def test_mutating_child_gets_worktree_and_environment_read_only_child_does_not(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    setup = (sys.executable, "-c", "from pathlib import Path; Path('.venv').mkdir()")
    git = LIFECYCLE.GitLanding()
    launch_base = git.base_commit(repo)
    mutating = git.provision(repo, _spec(mutating=True, environment_command=setup))
    read_only = git.provision(repo, _spec(row_id="read-only"))
    assert mutating.cwd != repo.resolve()
    assert (mutating.cwd / ".git").exists()
    assert (mutating.cwd / ".venv").is_dir()
    assert mutating.integration_mode == "branch"
    assert read_only == LIFECYCLE.Landing(
        repo.resolve(), "none", "none", launch_base, repo.resolve()
    )


def test_out_of_scope_change_fails_even_when_predicate_passes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    git = LIFECYCLE.GitLanding()
    baseline = git.changed_paths_baseline(repo)
    (repo / "src").mkdir()
    (repo / "src" / "allowed.py").write_text("ok\n", encoding="utf-8")
    (repo / "outside.txt").write_text("escaped\n", encoding="utf-8")
    with pytest.raises(LIFECYCLE.ScopeViolationError, match="outside.txt"):
        LIFECYCLE.check_completion_scope(
            _spec(),
            LIFECYCLE.Landing(repo, "none", "none"),
            baseline,
            predicate_passed=True,
            git=git,
        )


def test_modifying_a_preexisting_dirty_path_is_attributed_to_the_child(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    dirty = repo / "outside.txt"
    dirty.write_text("before dispatch\n", encoding="utf-8")
    git = LIFECYCLE.GitLanding()
    baseline = git.changed_paths_baseline(repo)
    dirty.write_text("child changed it\n", encoding="utf-8")
    with pytest.raises(LIFECYCLE.ScopeViolationError, match="outside.txt"):
        LIFECYCLE.check_completion_scope(
            _spec(),
            LIFECYCLE.Landing(repo, "none", "none"),
            baseline,
            predicate_passed=True,
            git=git,
        )


def test_scope_violation_distinguishes_shared_and_isolated_landings(tmp_path: Path) -> None:
    shared_repo = tmp_path / "shared"
    _init_repo(shared_repo)
    git = LIFECYCLE.GitLanding()
    shared_spec = _spec(scope=("reports/a",), mutating=False)
    shared_landing = git.provision(shared_repo, shared_spec)
    shared_baseline = git.changed_paths_baseline(
        shared_landing.cwd,
        base_commit=shared_landing.base_commit,
        ambient_root=shared_landing.ambient_root,
    )
    sibling_report = shared_repo / "reports" / "b" / "report.md"
    sibling_report.parent.mkdir(parents=True)
    sibling_report.write_text("sibling output\n", encoding="utf-8")
    with pytest.raises(LIFECYCLE.ScopeViolationError) as shared_error:
        LIFECYCLE.check_completion_scope(
            shared_spec, shared_landing, shared_baseline, predicate_passed=True, git=git
        )
    isolated_repo = tmp_path / "isolated"
    _init_repo(isolated_repo)
    isolated_spec = _spec(mutating=True, environment_command=())
    isolated_landing = git.provision(isolated_repo, isolated_spec)
    isolated_baseline = git.changed_paths_baseline(
        isolated_landing.cwd,
        base_commit=isolated_landing.base_commit,
        ambient_root=isolated_landing.ambient_root,
    )
    (isolated_landing.cwd / "outside.txt").write_text("child output\n", encoding="utf-8")
    with pytest.raises(LIFECYCLE.ScopeViolationError) as isolated_error:
        LIFECYCLE.check_completion_scope(
            isolated_spec, isolated_landing, isolated_baseline, predicate_passed=True, git=git
        )
    shared_message = str(shared_error.value)
    isolated_message = str(isolated_error.value)
    assert "shared-checkout landing" in shared_message
    assert "attribution to this child is not established" in shared_message
    assert "reports/b/report.md" in shared_message
    assert "isolated landing outside declared scope: outside.txt" in isolated_message
    assert "attribution to this child is not established" not in isolated_message


@pytest.mark.parametrize("mutating", [False, True])
@pytest.mark.parametrize("committed", [False, True])
def test_in_scope_change_is_allowed_in_each_child_landing(
    tmp_path: Path, mutating: bool, committed: bool
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    child = _spec(mutating=mutating, environment_command=())
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, child)
    baseline = git.changed_paths_baseline(
        landing.cwd, base_commit=landing.base_commit, ambient_root=landing.ambient_root
    )
    (landing.cwd / "src").mkdir()
    (landing.cwd / "src" / "ok.py").write_text("allowed\n", encoding="utf-8")
    if committed:
        _git(landing.cwd, "add", "src/ok.py")
        _git(landing.cwd, "commit", "-q", "-m", "allowed child change")
    result = LIFECYCLE.check_completion_scope(
        child, landing, baseline, predicate_passed=True, git=git
    )
    assert result.outside_scope == frozenset()
    assert result.new_changed_paths == frozenset({"src/ok.py"})


def test_committed_out_of_scope_change_is_compared_with_branch_base(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, _spec(mutating=True, environment_command=()))
    baseline = git.changed_paths_baseline(
        landing.cwd, base_commit=landing.base_commit, ambient_root=landing.ambient_root
    )
    (landing.cwd / "outside.txt").write_text("committed escape\n", encoding="utf-8")
    _git(landing.cwd, "add", "outside.txt")
    _git(landing.cwd, "commit", "-q", "-m", "child commit")
    with pytest.raises(LIFECYCLE.ScopeViolationError, match="outside.txt"):
        LIFECYCLE.check_completion_scope(
            _spec(mutating=True), landing, baseline, predicate_passed=True, git=git
        )


def test_read_only_child_commit_is_compared_with_its_launch_base(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    child = _spec(mutating=False)
    git = LIFECYCLE.GitLanding()
    _identity, landing, _resolution = _launch(repo, child, git=git)
    baseline = git.changed_paths_baseline(
        landing.cwd, base_commit=landing.base_commit, ambient_root=landing.ambient_root
    )
    (repo / "outside.txt").write_text("committed escape\n", encoding="utf-8")
    _git(repo, "add", "outside.txt")
    _git(repo, "commit", "-q", "-m", "read-only child commit")
    with pytest.raises(LIFECYCLE.ScopeViolationError, match="outside.txt"):
        LIFECYCLE.check_completion_scope(child, landing, baseline, predicate_passed=True, git=git)
    assert landing.base_commit is not None
    assert (
        REGISTER.read_rows(repo, run_id="run-a")[child.row_id]["base_commit"] == landing.base_commit
    )


def test_committed_ambient_checkout_change_is_included_in_scope_check(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, _spec(mutating=True, environment_command=()))
    baseline = git.changed_paths_baseline(
        landing.cwd, base_commit=landing.base_commit, ambient_root=landing.ambient_root
    )
    (repo / "outside.txt").write_text("ambient escape\n", encoding="utf-8")
    _git(repo, "add", "outside.txt")
    _git(repo, "commit", "-q", "-m", "ambient escape")
    with pytest.raises(LIFECYCLE.ScopeViolationError, match="outside.txt"):
        LIFECYCLE.check_completion_scope(
            _spec(mutating=True), landing, baseline, predicate_passed=True, git=git
        )


def test_in_scope_ambient_checkout_change_is_outside_a_mutating_child_landing(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, _spec(mutating=True, environment_command=()))
    baseline = git.changed_paths_baseline(
        landing.cwd, base_commit=landing.base_commit, ambient_root=landing.ambient_root
    )
    (repo / "src").mkdir()
    (repo / "src" / "ok.py").write_text("wrong tree\n", encoding="utf-8")
    with pytest.raises(LIFECYCLE.ScopeViolationError, match="ambient checkout: src/ok\\.py"):
        LIFECYCLE.check_completion_scope(
            _spec(mutating=True), landing, baseline, predicate_passed=True, git=git
        )


@pytest.mark.parametrize("sync_method", ["merge", "rebase"])
def test_child_history_excludes_upstream_paths_after_sync(tmp_path: Path, sync_method: str) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, _spec(mutating=True, environment_command=()))
    assert landing.base_commit is not None
    (repo / "docs").mkdir()
    (repo / "docs" / "upstream.md").write_text("operator change\n", encoding="utf-8")
    _git(repo, "add", "docs/upstream.md")
    _git(repo, "commit", "-q", "-m", "upstream change")
    upstream_commit = git.base_commit(repo)
    (landing.cwd / "src").mkdir()
    (landing.cwd / "src" / "ok.py").write_text("child change\n", encoding="utf-8")
    _git(landing.cwd, "add", "src/ok.py")
    _git(landing.cwd, "commit", "-q", "-m", "child change")
    if sync_method == "merge":
        _git(landing.cwd, "merge", "-q", "main", "-m", "merge upstream")
    else:
        _git(landing.cwd, "rebase", "-q", "main")
    assert git.committed_paths(
        landing.cwd, landing.base_commit, upstream_commit=upstream_commit
    ) == frozenset({"src/ok.py"})


@pytest.mark.parametrize("sync_method", ["merge", "rebase"])
def test_completion_scope_accepts_child_sync_when_upstream_is_in_dispatch_baseline(
    tmp_path: Path, sync_method: str
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    git = LIFECYCLE.GitLanding()
    child = _spec(mutating=True, environment_command=())
    landing = git.provision(repo, child)
    (repo / "docs").mkdir()
    (repo / "docs" / "upstream.md").write_text("operator change\n", encoding="utf-8")
    _git(repo, "add", "docs/upstream.md")
    _git(repo, "commit", "-q", "-m", "upstream change before dispatch")
    baseline = git.changed_paths_baseline(
        landing.cwd, base_commit=landing.base_commit, ambient_root=landing.ambient_root
    )
    (landing.cwd / "src").mkdir()
    (landing.cwd / "src" / "ok.py").write_text("child change\n", encoding="utf-8")
    _git(landing.cwd, "add", "src/ok.py")
    _git(landing.cwd, "commit", "-q", "-m", "child change")
    if sync_method == "merge":
        _git(landing.cwd, "merge", "-q", "main", "-m", "merge upstream")
    else:
        _git(landing.cwd, "rebase", "-q", "main")
    result = LIFECYCLE.check_completion_scope(
        child, landing, baseline, predicate_passed=True, git=git
    )
    assert result.new_changed_paths == frozenset({"src/ok.py"})
    assert result.outside_scope == frozenset()


def test_child_history_keeps_both_sides_of_an_amended_rename(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "old.py").write_text("old\n", encoding="utf-8")
    _git(repo, "add", "src/old.py")
    _git(repo, "commit", "-q", "-m", "add old path")
    git = LIFECYCLE.GitLanding()
    landing = git.provision(repo, _spec(mutating=True, environment_command=()))
    assert landing.base_commit is not None
    _git(landing.cwd, "mv", "src/old.py", "src/new.py")
    _git(landing.cwd, "commit", "-q", "-m", "rename child path")
    (landing.cwd / "src" / "new.py").write_text("amended\n", encoding="utf-8")
    _git(landing.cwd, "add", "src/new.py")
    _git(landing.cwd, "commit", "-q", "--amend", "--no-edit")
    assert git.committed_paths(
        landing.cwd, landing.base_commit, upstream_commit=git.base_commit(repo)
    ) == frozenset({"src/old.py", "src/new.py"})


def test_gitignored_paths_are_explicitly_outside_scope_observation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    with (repo / ".gitignore").open("a", encoding="utf-8") as stream:
        stream.write("ignored-dir/\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "ignore generated files")
    git = LIFECYCLE.GitLanding()
    baseline = git.changed_paths_baseline(repo, ambient_root=repo)
    ignored = repo / "ignored-dir" / "secret.txt"
    ignored.parent.mkdir()
    ignored.write_text("not observed by Git status\n", encoding="utf-8")
    result = LIFECYCLE.check_completion_scope(
        _spec(),
        LIFECYCLE.Landing(repo, "none", "none", ambient_root=repo),
        baseline,
        predicate_passed=True,
        git=git,
    )
    assert result.new_changed_paths == frozenset()
    assert LIFECYCLE.IGNORED_PATHS_LIMITATION.startswith("Git-ignored paths are outside")
    contract = (
        ROOT / "plugins" / "orchestrate" / "references" / "substrate-contract.md"
    ).read_text(encoding="utf-8")
    assert "Git-ignored paths are outside U4 scope observation" in contract


def test_unreleased_changelog_describes_the_final_release_state() -> None:
    changelog = (ROOT / "plugins" / "orchestrate" / "CHANGELOG.md").read_text(encoding="utf-8")
    release = changelog.split("## [0.3.0]", 1)[1].split("## [0.2.2]", 1)[0]
    assert "### Fixed" not in release
    assert "Every child records a launch commit" in release
    assert "continuously chatty panes remain" in release


def test_scope_and_cli_boundary_lessons_are_recorded_in_the_journal() -> None:
    learnings = (ROOT / "docs" / "engineering-journal" / "LEARNINGS.md").read_text(encoding="utf-8")
    assert "{#repair-the-input-class}" in learnings
    assert "name its input class" in learnings
    assert "enumerate every conditional" in learnings
    assert "{#cli-help-is-not-parser-grammar}" in learnings
    assert "Test an external command adapter with a rejecting argv grammar" in learnings


def test_reap_records_transition_before_closing_tab(tmp_path: Path) -> None:
    _record(tmp_path, "run-a")
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "verified", "tab_id": "tab-a", "cwd": str(tmp_path)},
        run_id="run-a",
        writer="write_phase",
    )
    herdr = FakeHerdr()
    LIFECYCLE.reap_verified(tmp_path, "child-a", herdr=herdr, run_id="run-a")
    assert herdr.closed == ["tab-a"]
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    assert row["phase"] == "reaped"
    assert row["expected_state"] == "exited"


def test_reap_writes_phase_and_expected_state_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _record(tmp_path, "run-a")
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {
            "run_id": "run-a",
            "phase": "verified",
            "expected_state": "working",
            "tab_id": "tab-a",
            "cwd": str(tmp_path),
        },
        run_id="run-a",
        writer="write_phase",
    )
    completed: list[str] = []
    real_upsert = LIFECYCLE.register_store.upsert_row
    real_write_phase = LIFECYCLE.register_store.write_phase

    def upsert(*args: Any, **kwargs: Any) -> Any:
        if completed:
            raise KeyboardInterrupt("interrupted between the two register writes")
        result = real_upsert(*args, **kwargs)
        completed.append("upsert")
        return result

    def write_phase(*args: Any, **kwargs: Any) -> Any:
        if completed:
            raise KeyboardInterrupt("interrupted between the two register writes")
        result = real_write_phase(*args, **kwargs)
        completed.append("write_phase")
        return result

    monkeypatch.setattr(LIFECYCLE.register_store, "upsert_row", upsert)
    monkeypatch.setattr(LIFECYCLE.register_store, "write_phase", write_phase)
    interrupted = False
    try:
        LIFECYCLE.reap_verified(tmp_path, "child-a", herdr=FakeHerdr(), run_id="run-a")
    except KeyboardInterrupt:
        interrupted = True
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    both = row.get("phase") == "reaped" and row.get("expected_state") == "exited"
    neither = row.get("phase") == "verified" and row.get("expected_state") == "working"
    assert both or neither, (row.get("phase"), row.get("expected_state"), interrupted)
    if not interrupted:
        assert both


def test_vanished_child_raises_unless_reap_was_recorded(tmp_path: Path) -> None:
    _record(tmp_path, "run-a")
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "launched", "tab_id": "tab-a", "cwd": str(tmp_path)},
        run_id="run-a",
        writer="write_phase",
    )
    herdr = FakeHerdr()
    herdr.present = False
    with pytest.raises(LIFECYCLE.VanishedChildError, match="before the register recorded"):
        LIFECYCLE.assert_child_not_vanished(tmp_path, "child-a", herdr=herdr, run_id="run-a")
    REGISTER.upsert_row(
        tmp_path, "child-a", {"phase": "reaped"}, run_id="run-a", writer="write_phase"
    )
    checks_before = herdr.presence_checks
    LIFECYCLE.assert_child_not_vanished(tmp_path, "child-a", herdr=herdr, run_id="run-a")
    assert herdr.presence_checks == checks_before


def test_reap_refuses_a_directory_that_is_not_the_runs_work_location(tmp_path: Path) -> None:
    """A repository argument that does not bind the run must not close the tab."""
    repo = tmp_path / "repo"
    other = tmp_path / "other"
    repo.mkdir()
    other.mkdir()
    _record(repo, "run-a")
    REGISTER.upsert_row(
        repo,
        "child-a",
        {"run_id": "run-a", "phase": "verified", "tab_id": "tab-a", "cwd": str(repo)},
        run_id="run-a",
        writer="write_phase",
    )
    herdr = FakeHerdr()
    with pytest.raises(REGISTER.RegisterError, match="bound to"):
        LIFECYCLE.reap_verified(other, "child-a", herdr=herdr, run_id="run-a")
    assert herdr.closed == []
    assert REGISTER.read_rows(repo, run_id="run-a")["child-a"]["phase"] == "verified"
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(REGISTER.RegisterError, match="bound to"):
        LIFECYCLE.reap_verified(empty, "child-a", herdr=herdr, run_id="run-a")
    assert herdr.closed == []


def test_a_vanish_check_refuses_a_directory_that_is_not_the_runs_work_location(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    other = tmp_path / "other"
    repo.mkdir()
    other.mkdir()
    _record(repo, "run-a")
    REGISTER.upsert_row(
        repo,
        "child-a",
        {"run_id": "run-a", "phase": "launched", "tab_id": "tab-a", "cwd": str(repo)},
        run_id="run-a",
        writer="write_phase",
    )
    with pytest.raises(REGISTER.RegisterError, match="bound to"):
        LIFECYCLE.assert_child_not_vanished(other, "child-a", herdr=FakeHerdr(), run_id="run-a")


def test_reap_refuses_when_the_run_has_no_work_location(tmp_path: Path) -> None:
    """A destructive path must not guess a repository the run never bound."""
    path = REGISTER.register_path("run-a")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-a",
                "rows": {
                    "child-a": {
                        "id": "child-a",
                        "run_id": "run-a",
                        "phase": "verified",
                        "tab_id": "tab-a",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    empty = tmp_path / "empty"
    empty.mkdir()
    herdr = FakeHerdr()
    with pytest.raises(REGISTER.RegisterError, match="no recorded work location"):
        LIFECYCLE.reap_verified(empty, "child-a", herdr=herdr, run_id="run-a")
    assert herdr.closed == []


def test_reap_refuses_when_only_a_first_writer_stamp_exists(tmp_path: Path) -> None:
    """A stamp is continuity. Closing a tab requires the recorded root."""
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "verified", "tab_id": "tab-a", "cwd": str(tmp_path)},
        run_id="run-a",
        writer="write_phase",
    )
    herdr = FakeHerdr()
    with pytest.raises(REGISTER.RegisterError, match="no recorded work location"):
        LIFECYCLE.reap_verified(tmp_path, "child-a", herdr=herdr, run_id="run-a")
    assert herdr.closed == []
    assert REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]["phase"] == "verified"


def test_a_vanish_check_refuses_when_only_a_first_writer_stamp_exists(tmp_path: Path) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "launched", "tab_id": "tab-a", "cwd": str(tmp_path)},
        run_id="run-a",
        writer="write_phase",
    )
    with pytest.raises(REGISTER.RegisterError, match="no recorded work location"):
        LIFECYCLE.assert_child_not_vanished(tmp_path, "child-a", herdr=FakeHerdr(), run_id="run-a")


class _OutputMatchServer:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.request: dict[str, Any] | None = None
        self.ready = threading.Event()
        self.error: BaseException | None = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> _OutputMatchServer:
        self.thread.start()
        assert self.ready.wait(2)
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.thread.join(timeout=3)
        assert not self.thread.is_alive()
        assert self.error is None

    def _run(self) -> None:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(self.path))
                server.listen()
                self.ready.set()
                conn, _ = server.accept()
                with conn, conn.makefile("rwb") as stream:
                    self.request = json.loads(stream.readline())
                    match = self.request["params"]["subscriptions"][0]["match"]["value"]
                    pane_id = self.request["params"]["subscriptions"][0]["pane_id"]
                    stream.write(
                        json.dumps(
                            {
                                "id": "orchestrate-interaction",
                                "result": {"type": "subscription_started"},
                            }
                        ).encode()
                        + b"\n"
                    )
                    stream.write(
                        json.dumps(
                            {
                                "event": "pane.output_matched",
                                "data": {
                                    "pane_id": pane_id,
                                    "matched_line": match,
                                    "read": {"revision": 11},
                                },
                            }
                        ).encode()
                        + b"\n"
                    )
                    stream.flush()
        except BaseException as exc:
            self.error = exc
            self.ready.set()
        finally:
            self.path.unlink(missing_ok=True)


class _SilentOutputMatchServer(_OutputMatchServer):
    def _run(self) -> None:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(self.path))
                server.listen()
                self.ready.set()
                conn, _ = server.accept()
                with conn, conn.makefile("rwb") as stream:
                    self.request = json.loads(stream.readline())
                    stream.write(
                        json.dumps(
                            {
                                "id": "orchestrate-interaction",
                                "result": {"type": "subscription_started"},
                            }
                        ).encode()
                        + b"\n"
                    )
                    stream.flush()
                    time.sleep(0.15)
        except BaseException as exc:
            self.error = exc
            self.ready.set()
        finally:
            self.path.unlink(missing_ok=True)


class _ChattyOutputMatchServer(_OutputMatchServer):
    def _run(self) -> None:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(self.path))
                server.listen()
                self.ready.set()
                conn, _ = server.accept()
                with conn, conn.makefile("rwb") as stream:
                    self.request = json.loads(stream.readline())
                    pane_id = self.request["params"]["subscriptions"][0]["pane_id"]
                    stream.write(
                        json.dumps(
                            {
                                "id": "orchestrate-interaction",
                                "result": {"type": "subscription_started"},
                            }
                        ).encode()
                        + b"\n"
                    )
                    stream.flush()
                    while True:
                        try:
                            stream.write(
                                json.dumps(
                                    {
                                        "event": "pane.output_matched",
                                        "data": {
                                            "pane_id": pane_id,
                                            "matched_line": "still working",
                                            "read": {"revision": 0},
                                        },
                                    }
                                ).encode()
                                + b"\n"
                            )
                            stream.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            break
                        time.sleep(0.005)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except BaseException as exc:
            self.error = exc
            self.ready.set()
        finally:
            self.path.unlink(missing_ok=True)


def test_readiness_uses_output_match_and_never_agent_status_alone(tmp_path: Path) -> None:
    child = _spec()
    identity, landing, resolution = _launch(tmp_path, child)
    herdr = FakeHerdr()
    socket_path = Path("/tmp") / f"orchestrate-u4-{uuid.uuid4().hex}.sock"
    with _OutputMatchServer(socket_path) as peer:
        ready = LIFECYCLE.confirm_ready(
            tmp_path,
            child,
            identity,
            landing,
            resolution,
            herdr=herdr,
            interaction=LIFECYCLE.HerdrInteraction(socket_path),
            git=FakeGit(tmp_path),
            sentinel_nonce="socket",
        )
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    assert ready.readiness_sentinel not in herdr.sent[-1]
    assert "part 1:" in herdr.sent[-1] and "part 2:" in herdr.sent[-1]
    assert row["phase"] == "ready"
    assert row["observed_state_source"] == "observed:pane.output_matched"
    assert peer.request is not None
    assert peer.request["params"]["subscriptions"][0]["type"] == "pane.output_matched"


def test_real_socket_readiness_timeout_is_bounded_and_records_not_ready(tmp_path: Path) -> None:
    child = _spec(readiness_timeout=0.05)
    identity, landing, resolution = _launch(tmp_path, child)
    herdr = FakeHerdr()
    socket_path = Path("/tmp") / f"orchestrate-u4-{uuid.uuid4().hex}.sock"
    with _SilentOutputMatchServer(socket_path):
        started = time.monotonic()
        with pytest.raises(LIFECYCLE.NotReadyError, match="within 0.05s"):
            LIFECYCLE.confirm_ready(
                tmp_path,
                child,
                identity,
                landing,
                resolution,
                herdr=herdr,
                interaction=LIFECYCLE.HerdrInteraction(socket_path),
                git=FakeGit(tmp_path),
                sentinel_nonce="bounded",
            )
        elapsed = time.monotonic() - started
    assert elapsed < 0.14
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    assert row["observed_state"] == "not_ready"
    assert row["observed_state_source"] == "inferred:readiness_timeout"


def test_chatty_socket_readiness_still_honors_the_outer_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    child = _spec(readiness_timeout=0.05)
    identity, landing, resolution = _launch(tmp_path, child)
    socket_path = Path("/tmp") / f"orchestrate-u4-{uuid.uuid4().hex}.sock"
    moments = iter((0.0, 0.0, 1.0))
    monkeypatch.setattr(LIFECYCLE.time, "monotonic", lambda: next(moments, 1.0))
    with (
        _ChattyOutputMatchServer(socket_path),
        pytest.raises(LIFECYCLE.NotReadyError, match="within 0.05s"),
    ):
        LIFECYCLE.confirm_ready(
            tmp_path,
            child,
            identity,
            landing,
            resolution,
            herdr=FakeHerdr(),
            interaction=LIFECYCLE.HerdrInteraction(socket_path),
            git=FakeGit(tmp_path),
            sentinel_nonce="chatty-bounded",
        )
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    assert row["observed_state"] == "not_ready"
    assert row["observed_state_source"] == "inferred:readiness_timeout"


def test_qwen_effort_command_is_sent_and_acknowledged_before_readiness(tmp_path: Path) -> None:
    child = _spec(runtime="qwen")
    identity, landing, resolution = _launch(tmp_path, child)
    herdr = FakeHerdr()
    interaction = FakeInteraction()
    LIFECYCLE.confirm_ready(
        tmp_path,
        child,
        identity,
        landing,
        resolution,
        herdr=herdr,
        interaction=interaction,
        git=FakeGit(tmp_path),
        sentinel_nonce="qwen",
    )
    assert herdr.sent[0] == f"/effort {resolution.effort}"
    assert interaction.matches[0] == "Reasoning effort"
    assert interaction.matches[1].startswith(SUBSCRIBER.SENTINEL_MARKER)
    assert interaction.accept_calls == 1


def test_qwen_disabled_thinking_has_an_actionable_effort_error(tmp_path: Path) -> None:
    child = _spec(runtime="qwen")
    identity, landing, resolution = _launch(tmp_path, child)
    herdr = FakeHerdr()
    herdr.thinking_disabled = True
    with pytest.raises(LIFECYCLE.NotReadyError, match="thinking is disabled"):
        LIFECYCLE.confirm_ready(
            tmp_path,
            child,
            identity,
            landing,
            resolution,
            herdr=herdr,
            interaction=FakeInteraction(),
            git=FakeGit(tmp_path),
        )
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    assert row["observed_state"] == "not_ready"
    assert row["observed_state_source"] == "inferred:effort_not_applied"


def test_qwen_effort_timeout_is_recorded_before_readiness_dispatch(tmp_path: Path) -> None:
    child = _spec(runtime="qwen")
    identity, landing, resolution = _launch(tmp_path, child)
    interaction = FakeInteraction(fail=True)
    with pytest.raises(LIFECYCLE.NotReadyError, match="bounded readiness timeout"):
        LIFECYCLE.confirm_ready(
            tmp_path,
            child,
            identity,
            landing,
            resolution,
            herdr=FakeHerdr(),
            interaction=interaction,
            git=FakeGit(tmp_path),
        )
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    assert interaction.matches == ["Reasoning effort"]
    assert row["observed_state"] == "not_ready"
    assert row["observed_state_source"] == "inferred:effort_timeout"


def test_agent_wrapper_adapter_crosses_subprocess_and_parses_returned_ids(tmp_path: Path) -> None:
    binary = tmp_path / "fake-agent"
    binary.write_text(
        "#!/usr/bin/env python3\nimport json, os, sys\nargs = sys.argv[1:]\ncwd = args[args.index('--cwd') + 1]\nworkspace = args[args.index('--workspace') + 1]\nif '--dry-run' in args:\n    print(f\"cwd={os.environ.get('FAKE_AGENT_CWD', os.path.abspath(cwd))}\")\n    print(f\"herdr_workspace={os.environ.get('FAKE_AGENT_WORKSPACE', workspace)}\")\nelse:\n    print(json.dumps({'agent_name': 'actual', 'workspace_id': 'w1', 'tab_id': 't1',\n                      'pane_id': 'p1', 'reused': True}))\n",
        encoding="utf-8",
    )
    binary.chmod(493)
    landing = LIFECYCLE.Landing(tmp_path, "none", "none")
    wrapper = LIFECYCLE.AgentWrapper(str(binary))
    child = _spec(workspace="w1")
    wrapper.preview(child, landing, "label", ["--model", "model"])
    identity = wrapper.launch(child, landing, "label", ["--model", "model"])
    assert identity == LIFECYCLE.LaunchIdentity("actual", "w1", "t1", "p1", True)


def test_agent_preview_rejects_a_different_resolved_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "fake-agent"
    binary.write_text(
        "#!/bin/sh\nprintf 'cwd=%s\\nherdr_workspace=workspace-a\\n' \"$FAKE_AGENT_CWD\"\n",
        encoding="utf-8",
    )
    binary.chmod(493)
    monkeypatch.setenv("FAKE_AGENT_CWD", str(tmp_path / "wrong"))
    with pytest.raises(LIFECYCLE.LaunchPreviewError, match="does not equal"):
        LIFECYCLE.AgentWrapper(str(binary)).preview(
            _spec(), LIFECYCLE.Landing(tmp_path, "none", "none"), "label", []
        )


def test_agent_preview_rejects_a_different_workspace(tmp_path: Path) -> None:
    binary = tmp_path / "fake-agent"
    binary.write_text(
        f"#!/bin/sh\nprintf 'cwd=%s\\nherdr_workspace=other-workspace\\n' {str(tmp_path)!r}\n",
        encoding="utf-8",
    )
    binary.chmod(493)
    with pytest.raises(LIFECYCLE.LaunchPreviewError, match="does not contain"):
        LIFECYCLE.AgentWrapper(str(binary)).preview(
            _spec(), LIFECYCLE.Landing(tmp_path, "none", "none"), "label", []
        )


def test_default_herdr_session_is_fixed_across_launch_and_register(tmp_path: Path) -> None:
    child = _spec()
    argv = LIFECYCLE.AgentWrapper._argv(
        child, LIFECYCLE.Landing(tmp_path, "none", "none"), "label", [], dry_run=True
    )
    session_at = argv.index("--herdr-session")
    assert argv[session_at + 1] == "default"
    assert "herdr_session" not in LIFECYCLE.ChildSpec.__dataclass_fields__
    assert LIFECYCLE.HerdrInteraction().socket_path == EVENTS.DEFAULT_SOCKET_PATH
    _launch(tmp_path, child)
    assert REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]["herdr_session"] == "default"


def test_withdrawn_revision_baseline_has_no_schema_or_control_wiring() -> None:
    assert "dispatch_revision_baseline" not in REGISTER.ROW_COLUMNS
    assert not hasattr(LIFECYCLE.HerdrControl, "pane_revision")
    assert hasattr(LIFECYCLE.GitLanding, "fingerprint")
    assert not hasattr(LIFECYCLE.GitLanding, "_fingerprint")
    assert "revision sample" not in (LIFECYCLE.launch_child.__doc__ or "")


def test_herdr_cli_adapter_validates_real_argument_shapes_and_label_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "herdr"
    log = tmp_path / "herdr-argv.jsonl"
    snapshot = {
        "tabs": [{"label": "target-label", "tab_id": "tab-a", "workspace_id": "work-a"}],
        "panes": [{"pane_id": "pane-a", "tab_id": "tab-a"}],
        "agents": [{"name": "actual-agent", "pane_id": "pane-a"}],
    }
    binary.write_text(
        f"#!/usr/bin/env python3\nimport json, os, sys\nargs = sys.argv[1:]\nwith open({str(log)!r}, 'a', encoding='utf-8') as stream:\n    stream.write(json.dumps(args) + '\\n')\nif args[:2] != ['--session', 'default']:\n    print('missing fixed default session: ' + repr(args), file=sys.stderr)\n    raise SystemExit(8)\nargs = args[2:]\nsnapshot = {snapshot!r}\nif os.environ.get('FAKE_HERDR_DUPLICATE') == '1':\n    snapshot['tabs'].append({{'label': 'target-label', 'tab_id': 'tab-b', 'workspace_id': 'work-a'}})\n    snapshot['panes'].append({{'pane_id': 'pane-b', 'tab_id': 'tab-b'}})\nif args == ['api', 'snapshot']:\n    print(json.dumps({{'result': {{'snapshot': snapshot}}}}))\nelif args == ['pane', 'read', 'pane-a', '--source', 'recent-unwrapped']:\n    print('pane content')\nelif args == ['pane', 'run', 'pane-a', 'dispatch text']:\n    pass\nelif args == ['tab', 'close', 'tab-a']:\n    pass\nelse:\n    print('unexpected argv: ' + repr(args), file=sys.stderr)\n    raise SystemExit(9)\n",
        encoding="utf-8",
    )
    binary.chmod(493)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    control = LIFECYCLE.HerdrControl()
    assert control.pane_text("pane-a", cwd=tmp_path).strip() == "pane content"
    assert control.discover_by_label("target-label", cwd=tmp_path) == LIFECYCLE.LaunchIdentity(
        "actual-agent", "work-a", "tab-a", "pane-a", True
    )
    assert control.discover_by_label("missing-label", cwd=tmp_path) is None
    control.send_line("pane-a", "dispatch text", cwd=tmp_path)
    assert control.tab_present("tab-a", cwd=tmp_path)
    control.close_tab("tab-a", cwd=tmp_path)
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    prefix = ["--session", "default"]
    assert prefix + ["pane", "read", "pane-a", "--source", "recent-unwrapped"] in calls
    assert prefix + ["pane", "run", "pane-a", "dispatch text"] in calls
    assert prefix + ["tab", "close", "tab-a"] in calls
    assert calls.count(prefix + ["api", "snapshot"]) == 3
    monkeypatch.setenv("FAKE_HERDR_DUPLICATE", "1")
    with pytest.raises(LIFECYCLE.LaunchProtocolError, match="more than one"):
        control.discover_by_label("target-label", cwd=tmp_path)


def test_dispatch_echo_never_contains_the_assembled_readiness_sentinel(tmp_path: Path) -> None:
    child = _spec()
    identity, landing, resolution = _launch(tmp_path, child)
    herdr = FakeHerdr()
    ready = LIFECYCLE.confirm_ready(
        tmp_path,
        child,
        identity,
        landing,
        resolution,
        herdr=herdr,
        interaction=FakeInteraction(),
        git=FakeGit(tmp_path),
        sentinel_nonce="not-echoed",
    )
    row = REGISTER.read_rows(tmp_path, run_id="run-a")["child-a"]
    assert ready.readiness_sentinel not in herdr.sent[-1]
    assert "part 1:" in herdr.sent[-1]
    assert "part 2:" in herdr.sent[-1]
    assert row["phase"] == "ready"


def test_permission_argv_is_the_workspace_write_posture_for_every_child() -> None:
    """One posture, not two, and the read-only distinction is not expressed as a flag.

    Every child -- mutating or not -- is dispatched with an artifact it must write, and no
    supported CLI accepts a repository-relative path allowlist, so a read-only flag never
    contained a read-only child; it only made its dispatch impossible to satisfy. Containment
    inside the workspace is the Git boundary check, whose repository write allowlist for a
    read-only child is empty.
    """
    assert LIFECYCLE.permission_argv("codex") == ["--sandbox", "workspace-write"]
    assert LIFECYCLE.permission_argv("grok") == ["--sandbox", "workspace"]
    assert LIFECYCLE.permission_argv("qwen") == ["--sandbox"]
    assert LIFECYCLE.permission_argv("agy") == ["--sandbox"]
    assert LIFECYCLE.permission_argv("claude") == []
    assert LIFECYCLE.permission_argv("muse") == []
    assert LIFECYCLE.permission_argv("unknown-runtime") == []
    for runtime in ("claude", "codex", "grok", "muse", "qwen", "agy"):
        argv = LIFECYCLE.permission_argv(runtime)
        assert "read-only" not in argv and "plan" not in argv
        assert "--disable-write" not in argv
