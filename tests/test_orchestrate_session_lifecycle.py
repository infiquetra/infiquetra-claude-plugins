"""Contract tests for orchestrate U4 session lifecycle behavior."""

from __future__ import annotations

import importlib.util
import json
import socket
import subprocess
import sys
import threading
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


class FakeGit:
    def __init__(self, root: Path, paths: list[frozenset[str]] | None = None) -> None:
        self.root = root
        self.paths = list(paths or [frozenset()])
        self.provisioned: list[Any] = []

    def provision(self, _root: Path, spec: Any) -> Any:
        self.provisioned.append(spec)
        return LIFECYCLE.Landing(self.root, "none", "none")

    def changed_paths(self, _cwd: Path) -> frozenset[str]:
        return self.paths.pop(0) if len(self.paths) > 1 else self.paths[0]

    def changed_paths_baseline(self, cwd: Path) -> Any:
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
        self.revision = 10
        self.sent: list[str] = []
        self.closed: list[str] = []
        self.present = True
        self.presence_checks = 0

    def discover_by_label(self, label: str, *, cwd: Path) -> Any:
        return self.discovered

    def pane_text(self, pane_id: str, *, cwd: Path) -> str:
        return self.text

    def pane_revision(self, pane_id: str, *, cwd: Path) -> int:
        return self.revision

    def send_line(self, pane_id: str, text: str, *, cwd: Path) -> None:
        self.sent.append(text)
        if text.startswith("/effort "):
            effort = text.split(maxsplit=1)[1]
            self.text += (
                f"\nReasoning effort: {effort} "
                "(requested; the effective tier depends on the active provider/model)."
            )

    def close_tab(self, tab_id: str, *, cwd: Path) -> None:
        row = REGISTER.read_rows(cwd)["child-a"]
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
        self,
        *,
        pane_id: str,
        match: str,
        timeout: float,
        dispatch: Any,
        accept: Any = None,
    ) -> Any:
        self.matches.append(match)
        baseline = dispatch()
        if self.fail:
            raise LIFECYCLE.NotReadyError("bounded readiness timeout")
        event = SimpleNamespace(revision=0)
        if accept is not None:
            self.accept_calls += 1
            assert accept(event, baseline)
        return event, baseline


def _launch(tmp_path: Path, spec: Any | None = None, **kwargs: Any) -> Any:
    child = spec or _spec()
    wrapper = kwargs.pop("wrapper", FakeWrapper())
    herdr = kwargs.pop("herdr", FakeHerdr())
    git = kwargs.pop("git", FakeGit(tmp_path))
    return LIFECYCLE.launch_child(tmp_path, child, wrapper=wrapper, herdr=herdr, git=git)


# Scenario 1: write-ahead launch -------------------------------------------------------------


def test_register_row_and_run_label_exist_before_a_failing_launch(tmp_path: Path) -> None:
    wrapper = FakeWrapper(launch_error=RuntimeError("launch exploded"))

    def assert_write_ahead(label: str) -> None:
        row = REGISTER.read_rows(tmp_path)["child-a"]
        assert row["task"] == label == "orchestrate-run-a-child-a"
        assert row["phase"] == "launching"

    wrapper.before_launch = assert_write_ahead
    with pytest.raises(RuntimeError, match="launch exploded"):
        _launch(tmp_path, wrapper=wrapper)

    assert wrapper.launches == 1
    assert REGISTER.read_rows(tmp_path)["child-a"]["phase"] == "launching"


# Scenario 2: recover an orphaned launch -----------------------------------------------------


def test_retry_discovers_written_label_after_crash_before_identifier_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapper = FakeWrapper()
    herdr = FakeHerdr()
    original = REGISTER.upsert_row
    crashed = False

    def crash_before_identifiers(root: Path, row_id: str, fields: Any) -> Any:
        nonlocal crashed
        if not crashed and "pane_id" in fields:
            crashed = True
            herdr.discovered = IDENTITY
            raise RuntimeError("crash after side effect")
        return original(root, row_id, fields)

    monkeypatch.setattr(REGISTER, "upsert_row", crash_before_identifiers)
    with pytest.raises(RuntimeError, match="crash after side effect"):
        _launch(tmp_path, wrapper=wrapper, herdr=herdr)

    recovered, _landing, _resolution = _launch(tmp_path, wrapper=wrapper, herdr=herdr)
    assert recovered == IDENTITY
    assert wrapper.launches == 1
    assert REGISTER.read_rows(tmp_path)["child-a"]["pane_id"] == "pane-a"


# Scenario 3: launch success without readiness -----------------------------------------------


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
    row = REGISTER.read_rows(tmp_path)["child-a"]
    assert row["phase"] == "launched"
    assert row["observed_state"] == "not_ready"
    assert row["observed_state_source"] == "inferred:readiness_timeout"


# Scenario 4: trust prompt -------------------------------------------------------------------


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
    assert REGISTER.read_rows(tmp_path)["child-a"]["observed_state"] == "trust_prompt"


# Scenario 5: mutating worktree plus environment ---------------------------------------------


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.com")
    _git(repo, "config", "user.name", "Tests")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")


def test_mutating_child_gets_worktree_and_environment_read_only_child_does_not(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    setup = (
        sys.executable,
        "-c",
        "from pathlib import Path; Path('.venv').mkdir()",
    )
    git = LIFECYCLE.GitLanding()
    mutating = git.provision(
        repo,
        _spec(mutating=True, environment_command=setup),
    )
    read_only = git.provision(repo, _spec(row_id="read-only"))

    assert mutating.cwd != repo.resolve()
    assert (mutating.cwd / ".git").exists()
    assert (mutating.cwd / ".venv").is_dir()
    assert mutating.integration_mode == "branch"
    assert read_only == LIFECYCLE.Landing(repo.resolve(), "none", "none")


# Scenario 6: total scope boundary ------------------------------------------------------------


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


# Scenario 7: write-ahead reap ---------------------------------------------------------------


def test_reap_records_transition_before_closing_tab(tmp_path: Path) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "verified", "tab_id": "tab-a", "cwd": str(tmp_path)},
    )
    herdr = FakeHerdr()
    LIFECYCLE.reap_verified(tmp_path, "child-a", herdr=herdr)
    assert herdr.closed == ["tab-a"]
    assert REGISTER.read_rows(tmp_path)["child-a"]["phase"] == "reaped"


# Scenario 8: unrecorded disappearance --------------------------------------------------------


def test_vanished_child_raises_unless_reap_was_recorded(tmp_path: Path) -> None:
    REGISTER.upsert_row(
        tmp_path,
        "child-a",
        {"run_id": "run-a", "phase": "launched", "tab_id": "tab-a", "cwd": str(tmp_path)},
    )
    herdr = FakeHerdr()
    herdr.present = False
    with pytest.raises(LIFECYCLE.VanishedChildError, match="before the register recorded"):
        LIFECYCLE.assert_child_not_vanished(tmp_path, "child-a", herdr=herdr)

    REGISTER.upsert_row(tmp_path, "child-a", {"phase": "reaped"})
    checks_before = herdr.presence_checks
    LIFECYCLE.assert_child_not_vanished(tmp_path, "child-a", herdr=herdr)
    assert herdr.presence_checks == checks_before


# Scenario 9: readiness is an interaction, not agent_status ----------------------------------


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

    def __exit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
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
        except BaseException as exc:  # noqa: BLE001
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

    row = REGISTER.read_rows(tmp_path)["child-a"]
    assert ready.readiness_sentinel not in herdr.sent[-1]
    assert "part 1:" in herdr.sent[-1] and "part 2:" in herdr.sent[-1]
    assert row["phase"] == "ready"
    assert row["observed_state_source"] == "observed:pane.output_matched"
    assert peer.request is not None
    assert peer.request["params"]["subscriptions"][0]["type"] == "pane.output_matched"


# Additional contract seams -----------------------------------------------------------------


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
    assert interaction.matches[0].startswith(f"Reasoning effort: {resolution.effort}")
    assert interaction.matches[1].startswith(SUBSCRIBER.SENTINEL_MARKER)
    assert interaction.accept_calls == 1


def test_agent_wrapper_adapter_crosses_subprocess_and_parses_returned_ids(tmp_path: Path) -> None:
    binary = tmp_path / "fake-agent"
    binary.write_text(
        """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
cwd = args[args.index('--cwd') + 1]
workspace = args[args.index('--workspace') + 1]
if '--dry-run' in args:
    print(f'cwd={os.path.abspath(cwd)}')
    print(f'herdr_workspace={workspace}')
else:
    print(json.dumps({'agent_name': 'actual', 'workspace_id': 'w1', 'tab_id': 't1',
                      'pane_id': 'p1', 'reused': True}))
""",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    landing = LIFECYCLE.Landing(tmp_path, "none", "none")
    wrapper = LIFECYCLE.AgentWrapper(str(binary))
    child = _spec(workspace="w1")
    wrapper.preview(child, landing, "label", ["--model", "model"])
    identity = wrapper.launch(child, landing, "label", ["--model", "model"])
    assert identity == LIFECYCLE.LaunchIdentity("actual", "w1", "t1", "p1", True)


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
    row = REGISTER.read_rows(tmp_path)["child-a"]
    assert ready.readiness_sentinel not in herdr.sent[-1]
    assert "part 1:" in herdr.sent[-1]
    assert "part 2:" in herdr.sent[-1]
    assert "dispatch_revision_baseline" not in row
    assert row["phase"] == "ready"


def test_permission_argv_uses_real_read_only_flags_without_claiming_qwen_scope() -> None:
    assert LIFECYCLE.permission_argv("codex", mutating=False) == ["--sandbox", "read-only"]
    assert LIFECYCLE.permission_argv("claude", mutating=False) == [
        "--permission-mode",
        "plan",
    ]
    assert LIFECYCLE.permission_argv("qwen", mutating=False) == []
    assert LIFECYCLE.permission_argv("codex", mutating=True) == [
        "--sandbox",
        "workspace-write",
    ]
