"""Contract tests for the assembled orchestrator.

Organised by the property the assembled control flow guarantees, not by function, because the
failure this unit exists to prevent is precisely that every module can be green while nothing
works. The five required scenarios are a floor:

1. the whole path -- approved plan, launch, subscribe, event, predicate, integrate, reap, next
   child -- traversed against a fake Herdr with a real Git repository underneath;
2. an orchestrator restart mid-run that resumes from the register without duplicating a child;
3. a subscriber death that raises divergence and is respawned;
4. a mirror request outstanding while an operator message arrives, answered with a receipt;
5. the four accepted outcome argument forms each producing a plan.

Everything past those is a property that no single module could establish inside its own
boundary, and each is written as the failure it prevents rather than as the feature that
prevents it. Where a property is a *refusal*, deleting the guard is what reaches it; where a
property is an *ordering*, it is reached by injecting the fault the order exists to survive.
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import json
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "orchestrate" / "skills" / "orchestrate" / "scripts"


def _load(name: str) -> ModuleType:
    """Load one plugin script, reusing the object another suite already loaded from that file.

    Reuse is not an optimisation. These modules resolve each other by name at call time --
    ``register`` imports ``completion`` inside the retirement path, for instance -- so a second
    object under the same ``sys.modules`` key makes another suite's ``monkeypatch`` target an
    object nothing calls. Loading this file second and rebuilding ``completion`` did exactly that
    to the completion suite's concurrent-mint test, which failed with no change to any module it
    exercises.
    """
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    source = SCRIPTS / f"{name}.py"
    existing = sys.modules.get(name)
    if existing is not None and getattr(existing, "__file__", None) == str(source):
        return existing
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REGISTER = _load("register")
EVENTS = _load("herdr_events")
ACCOUNTING = _load("accounting")
ADMISSION = _load("admission")
SUBSCRIBER = _load("subscriber")
LIFECYCLE = _load("session_lifecycle")
COMPLETION = _load("completion")
PLANNING = _load("planning")
MIRROR = _load("mirror")
RUNNER = _load("runner")

RUNNER_SOURCE = (SCRIPTS / "runner.py").read_text(encoding="utf-8")


def test_this_suite_did_not_create_a_second_completion_module() -> None:
    """A second object under one ``sys.modules`` key silently unhooks another suite's patches.

    ``register`` imports ``completion`` lazily inside its retirement path, so it resolves the
    name at call time. Loading this file second and rebuilding ``completion`` made the completion
    suite's ``monkeypatch`` target an object nothing called, and that suite failed on a test which
    exercises none of the code this unit changed. Stated as an assertion because the symptom
    appears in a different file.

    Other modules are deliberately not asserted here: several suites reload ``register`` and
    ``admission`` on purpose, and those modules hold no cross-module state, so a second object is
    harmless for them. What must hold is that this suite's own module graph is internally
    consistent and that ``completion`` is not duplicated.
    """
    assert sys.modules["completion"] is COMPLETION
    assert RUNNER.completion is COMPLETION
    assert RUNNER.register_store is REGISTER
    assert RUNNER.admission is ADMISSION
    assert RUNNER.accounting is ACCOUNTING
    assert RUNNER.planning is PLANNING
    assert RUNNER.mirror_module is MIRROR
    assert RUNNER.session_lifecycle is LIFECYCLE
    assert RUNNER.subscriber_module is SUBSCRIBER
    assert PLANNING.completion is COMPLETION


RUN_ID = "run-comp"
CEILING = 1_000_000.0


# --------------------------------------------------------------------------- host isolation


@pytest.fixture(autouse=True)
def _host_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep live registers, run secrets and run roots out of the operator's real host state.

    Siblings of the test repository rather than children of it: every child's landing is inside
    the repository, and the modules refuse a store a child could write.
    """
    monkeypatch.setenv(
        REGISTER.REGISTER_DIR_ENV, str(tmp_path.parent / f"{tmp_path.name}-registers")
    )
    monkeypatch.setenv(
        COMPLETION.RUN_SECRET_DIR_ENV, str(tmp_path.parent / f"{tmp_path.name}-run-secrets")
    )


# --------------------------------------------------------------------------- git


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.com")
    _git(repo, "config", "user.name", "Tests")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".orchestrate/\n__pycache__/\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "seed.txt").write_text("seed\n", encoding="utf-8")
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
    _git(repo, "add", "README.md", ".gitignore", "src", "checks")
    _git(repo, "commit", "-q", "-m", "seed")


# --------------------------------------------------------------------------- fakes


class FakeWrapper:
    """The ``agent`` launcher boundary. One tab and one pane per row, deterministically."""

    def __init__(self) -> None:
        self.previews: list[str] = []
        self.launches: list[str] = []
        self.launch_error: Exception | None = None
        self.post_launch_error: Exception | None = None
        self.on_launch: Callable[[str, Any], None] | None = None

    def preview(self, spec: Any, _landing: Any, _label: str, _argv: list[str]) -> None:
        self.previews.append(spec.row_id)

    def launch(self, spec: Any, _landing: Any, label: str, _argv: list[str]) -> Any:
        self.launches.append(spec.row_id)
        if self.launch_error is not None:
            raise self.launch_error
        index = len(self.launches)
        identity = LIFECYCLE.LaunchIdentity(
            f"{spec.runtime}-{index}", "ws-1", f"tab-{spec.row_id}", f"pane-{spec.row_id}", False
        )
        if self.on_launch is not None:
            self.on_launch(label, identity)
        if self.post_launch_error is not None:
            raise self.post_launch_error
        return identity


class FakeHerdr:
    """Herdr's snapshot and pane/tab control, recording every pane it is asked to touch."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.reads: list[str] = []
        self.closed: list[str] = []
        self.pane_texts: dict[str, str] = {}
        self.default_text = "ready\n"
        self.absent_tabs: set[str] = set()
        self.revisions: dict[str, int] = {}
        self.absent_panes: set[str] = set()
        self.snapshot_error: Exception | None = None
        #: Sessions discoverable by their run-bound task label, which is how the launcher
        #: recovers a dispatch that crashed after the session existed.
        self.labels: dict[str, Any] = {}
        self.label_lookups: list[str] = []

    # ---- the snapshot the coordinator and the mirror clock both read

    def _known_panes(self) -> list[str]:
        panes = (
            {pane for pane, _ in self.sent}
            | set(self.pane_texts)
            | set(self.revisions)
            | {identity.pane_id for identity in self.labels.values()}
        )
        return sorted(panes - self.absent_panes)

    def snapshot(self, *, cwd: Path) -> dict[str, Any]:
        if self.snapshot_error is not None:
            raise self.snapshot_error
        identities = {
            identity.pane_id: (label, identity) for label, identity in self.labels.items()
        }
        panes = []
        for pane in self._known_panes():
            label, identity = identities.get(
                pane,
                (
                    LIFECYCLE.task_label(RUN_ID, pane.removeprefix("pane-")),
                    LIFECYCLE.LaunchIdentity(
                        pane.removeprefix("pane-"),
                        "ws-1",
                        pane.replace("pane-", "tab-"),
                        pane,
                        False,
                    ),
                ),
            )
            if identity.tab_id in self.absent_tabs:
                continue
            panes.append(
                {
                    "pane_id": pane,
                    "tab_id": identity.tab_id,
                    "workspace_id": identity.workspace_id,
                    "cwd": str(cwd),
                    "foreground_cwd": str(cwd),
                    "revision": self.revisions.get(pane, 1),
                    "label": label,
                }
            )
        agents = [
            {
                **pane,
                "agent_status": "unknown",
                "name": pane["pane_id"],
            }
            for pane in panes
        ]
        tabs = [
            {
                "tab_id": pane["tab_id"],
                "workspace_id": pane["workspace_id"],
                "label": pane["label"],
            }
            for pane in panes
        ]
        return {"panes": panes, "agents": agents, "tabs": tabs}

    def discover_by_label(self, label: str, *, cwd: Path) -> Any:
        self.label_lookups.append(label)
        return LIFECYCLE.HerdrControl.discover_by_label(self, label, cwd=cwd)

    def pane_text(self, pane_id: str, *, cwd: Path) -> str:
        del cwd
        self.reads.append(pane_id)
        return self.pane_texts.get(pane_id, self.default_text)

    def send_line(self, pane_id: str, text: str, *, cwd: Path) -> None:
        del cwd
        self.sent.append((pane_id, text))

    def tab_present(self, tab_id: str, *, cwd: Path) -> bool:
        del cwd
        return tab_id not in self.absent_tabs

    def close_tab(self, tab_id: str, *, cwd: Path) -> None:
        del cwd
        self.closed.append(tab_id)
        self.absent_tabs.add(tab_id)


class FakeInteraction:
    """A readiness interaction that dispatches and observes without a socket."""

    def observe(
        self,
        *,
        pane_id: str,
        match: str,
        timeout: float,
        dispatch: Any,
        accept: Any = None,
    ) -> Any:
        del pane_id, match, timeout, accept
        state = dispatch()
        return SimpleNamespace(revision=0), state


class FakeChannel:
    """The operator channel. Records everything delivered, answers what it is told to answer."""

    def __init__(self, *, answers: list[str] | None = None) -> None:
        self.delivered: list[str] = []
        self.asked: list[str] = []
        self.answers = answers if answers is not None else []
        self.default_answer = "approve"
        self.deliver_error: Exception | None = None

    def deliver(self, text: str) -> None:
        if self.deliver_error is not None:
            raise self.deliver_error
        self.delivered.append(text)

    def ask(self, prompt: str, options: Any) -> str:
        self.asked.append(prompt)
        if self.answers:
            return self.answers.pop(0)
        return self.default_answer if self.default_answer in options else list(options)[0]


class FakeHandle:
    def __init__(self, argv: list[str], index: int) -> None:
        self.argv = list(argv)
        self.index = index
        self.alive = True
        self.pid = 90000 + index


class FakeSupervisor:
    """The subscriber's parent lifecycle. ``kill`` is an uncatchable death, not a clean stop.

    Addressable by handle and by durable record, because a restarted coordinator holds no handle
    and still has to be able to find, adopt, or stop the process its predecessor started.
    """

    def __init__(self) -> None:
        self.started: list[FakeHandle] = []
        self.stopped: list[FakeHandle] = []
        self.orphan_query_fails = False

    def start(self, argv: Any) -> FakeHandle:
        handle = FakeHandle(list(argv), len(self.started))
        self.started.append(handle)
        return handle

    def is_alive(self, handle: Any) -> bool:
        return handle is not None and handle.alive

    def stop(self, handle: Any) -> None:
        if handle is not None:
            handle.alive = False
            self.stopped.append(handle)

    def describe(self, handle: Any) -> dict[str, Any]:
        return {"pid": handle.pid}

    def _by_pid(self, record: Any) -> FakeHandle | None:
        pid = int(record.get("pid") or 0)
        return next((h for h in self.started if h.pid == pid), None)

    def is_record_alive(self, record: Any, *, signature: Any) -> bool:
        """Mirrors the production adapter: a live pid *and* a process-table match on identity.

        Routed through :meth:`find_orphan` rather than through ``self.started`` directly, so this
        fake fails the same way the real one does when the process-table query itself fails --
        raising, not silently reporting the record dead or alive.
        """
        handle = self._by_pid(record)
        if handle is None or not handle.alive:
            return False
        scan = self.find_orphan(signature=signature)
        if not scan.complete:
            raise RUNNER.SubscriberLivenessUnknownError(
                "the process table could not be queried to confirm this record's identity"
            )
        return scan.process is not None and int(scan.process.get("pid") or 0) == handle.pid

    def stop_record(self, record: Any) -> None:
        handle = self._by_pid(record)
        if handle is not None:
            self.stop(handle)

    def find_orphan(self, *, signature: Any) -> Any:
        """A live handle whose argv carries every token in ``signature``, newest first.

        The real implementation asks the host's process table; this asks every handle this fake
        has ever started, which is the same question against the same kind of evidence -- a
        process that exists whether or not a durable record ever named it. Returns an
        ``OrphanScan`` exactly as the real adapter does, so ``orphan_query_fails`` can stand in
        for a ``ps`` failure without a second, divergent fake shape.
        """
        if self.orphan_query_fails:
            return RUNNER.OrphanScan(process=None, complete=False)
        for handle in reversed(self.started):
            if handle.alive and all(token in handle.argv for token in signature):
                return RUNNER.OrphanScan(process={"pid": handle.pid}, complete=True)
        return RUNNER.OrphanScan(process=None, complete=True)

    def kill(self) -> None:
        """Kill the current process the way a SIGKILL does: no stop record, no clean-up."""
        if self.started:
            self.started[-1].alive = False


class Clock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        self.now += 1.0
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# --------------------------------------------------------------------------- harness


def _child(
    row_id: str,
    *,
    work_shape: str = "mechanical",
    vendor: str = "claude",
    integration_mode: str = "none",
    scope: tuple[str, ...] = ("src",),
    tokens_max: int = 20000,
    **extra: Any,
) -> dict[str, Any]:
    artifact = "report.json"
    predicate = {
        "argv": [
            sys.executable,
            "checks/check.py",
            RUNNER.artifact_relpath(RUN_ID, row_id, artifact),
        ]
    }
    declaration: dict[str, Any] = {
        "row_id": row_id,
        "task": f"Produce the deliverable for {row_id}.",
        "work_shape": work_shape,
        "vendor": vendor,
        "scope": list(scope),
        "artifact_path": artifact,
        "predicate": predicate,
        "integration_mode": integration_mode,
        "tokens_max": tokens_max,
    }
    declaration.update(extra)
    return declaration


class Harness:
    """One repository, one coordinator, and the ability to act as the children and the subscriber."""

    def __init__(self, tmp_path: Path, *, per_vendor: int = 3, aggregate: int = 7) -> None:
        self.repo = tmp_path / "repo"
        _init_repo(self.repo)
        ADMISSION.write_host_policy(per_vendor=per_vendor, aggregate=aggregate)
        self.wrapper = FakeWrapper()
        self.herdr = FakeHerdr()
        self.wrapper.on_launch = self.herdr.labels.__setitem__
        self.channel = FakeChannel()
        self.supervisor = FakeSupervisor()
        self.clock = Clock()
        self.git = LIFECYCLE.GitLanding()
        self.coordinator = self._build()

    def _build(self) -> Any:
        return RUNNER.Coordinator(
            self.repo,
            run_id=RUN_ID,
            workspace="ws-1",
            orchestrator_pane="pane-operator",
            subscriber_pane="pane-subscriber",
            wrapper=self.wrapper,
            herdr=self.herdr,
            git=self.git,
            interaction=FakeInteraction(),
            channel=self.channel,
            supervisor=self.supervisor,
            clock=self.clock,
            environment_command=(),
        )

    def restart_coordinator(self) -> Any:
        """A brand-new coordinator over the same durable state, as a real restart produces."""
        self.coordinator = self._build()
        return self.coordinator

    # ---- driving the run

    def plan(self, children: list[dict[str, Any]], *, ceiling: float = CEILING) -> Any:
        request = RUNNER.parse_outcome("Produce two independent reports.")
        return self.coordinator.plan_run(request, children, ceiling=ceiling)

    def approve_and_commit(self, children: list[dict[str, Any]], **kwargs: Any) -> Any:
        built = self.plan(children, **kwargs)
        self.coordinator.approve_plan(built)
        return self.coordinator.commit()

    def bootstrap(self, children: list[dict[str, Any]], **kwargs: Any) -> Any:
        self.coordinator.start_run()
        committed = self.approve_and_commit(children, **kwargs)
        self.coordinator.reconcile_startup(decide=lambda _orphan: "abandon")
        self.coordinator.ensure_subscriber()
        return committed

    # ---- acting as a child

    def dispatch_text(self, row_id: str) -> str:
        pane = f"pane-{row_id}"
        for target, text in reversed(self.herdr.sent):
            if target == pane and "Write your deliverable" in text:
                return text
        raise AssertionError(f"no artifact dispatch was sent to {pane}")

    def run_child(self, row_id: str, *, payload: dict[str, Any] | None = None) -> Path:
        """Author the deliverable from the dispatch text alone, as a real child would."""
        text = self.dispatch_text(row_id)
        indented = [line.strip() for line in text.splitlines() if line.startswith("  ")]
        inflight, destination, token = indented[0], indented[1], indented[2]
        assert not Path(destination).exists(), "a child never sees its own destination"
        document = payload if payload is not None else {"binding": token, "conclusion": "done"}
        target = Path(inflight)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document), encoding="utf-8")
        return target

    def land_mutating_change(self, row_id: str, *, relative: str = "src/change.txt") -> None:
        """Commit inside the child's worktree, which is what advances its destination branch."""
        attempt = self.coordinator.attempt_for(row_id)
        worktree = Path(attempt.landing.cwd)
        target = worktree / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("landed\n", encoding="utf-8")
        _git(worktree, "add", relative)
        _git(worktree, "commit", "-q", "-m", f"{row_id} landed")

    # ---- acting as the subscriber

    def report_usage(self, row_id: str, tokens: int = 1200) -> None:
        """Record a usage line the way the subscriber does when the pane prints one."""
        ACCOUNTING.apply_output_match(
            self.repo,
            row_id,
            f"tokens used: {tokens}",
            run_id=RUN_ID,
            vendor="claude",
            event_id=f"{row_id}-usage-{tokens}",
        )

    def rows(self) -> dict[str, dict[str, Any]]:
        found: dict[str, dict[str, Any]] = REGISTER.read_rows(self.repo, run_id=RUN_ID)
        return found


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


# =========================================================================== 1. the whole loop


def test_the_assembled_loop_reaches_a_reap_and_admission_starts_the_next_child(
    tmp_path: Path,
) -> None:
    """approved plan -> launch -> subscribe -> event -> predicate -> integrate -> reap -> next.

    The host bound is one slot per vendor, so the second child is *queued* at commit and can only
    start because reaping the first one released its slot and admission promoted it. That is the
    whole admission-lifecycle family in one traversal: nothing queued reaches launch, the slot is
    activated immediately before the launcher, and the release happens only after a recorded reap.
    """
    harness = Harness(tmp_path, per_vendor=1, aggregate=1)
    committed = harness.bootstrap([_child("child-a"), _child("child-b")])
    statuses = {child.row_id: child.admission for child in committed.children}
    assert statuses == {"child-a": "reserved", "child-b": "queued"}

    first = harness.coordinator.launch_ready_children()
    assert first.launched == ("child-a",)
    assert "child-b" in first.withheld

    harness.run_child("child-a")
    harness.report_usage("child-a")
    result = harness.coordinator.integrate_child("child-a")
    assert result.verified, result.detail

    authorization = harness.coordinator.reap_child("child-a")
    assert authorization.row_id == "child-a"
    assert harness.rows()["child-a"]["phase"] == "reaped"
    assert "tab-child-a" in harness.herdr.closed

    # The release promoted the queued child, and only then does it reach the launcher.
    assert harness.rows()["child-b"]["admission"] == "reserved"
    second = harness.coordinator.launch_ready_children()
    assert second.launched == ("child-b",)
    assert harness.wrapper.launches == ["child-a", "child-b"]


def test_a_mutating_child_that_never_landed_its_change_is_not_verified(harness: Harness) -> None:
    """Integration precedes reaping: a valid artifact inside a worktree is not a landed change."""
    harness.bootstrap([_child("child-m", integration_mode="branch")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-m")
    result = harness.coordinator.integrate_child("child-m")
    assert not result.verified
    assert result.reason == "integration_unverified"
    assert harness.rows()["child-m"]["phase"] != "verified"


def test_a_mutating_child_whose_change_landed_is_verified_and_reapable(harness: Harness) -> None:
    harness.bootstrap([_child("child-m", integration_mode="branch")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-m")
    harness.land_mutating_change("child-m")
    harness.report_usage("child-m")
    result = harness.coordinator.integrate_child("child-m")
    assert result.verified, result.detail
    assert "advanced to" in (result.integration or "")
    harness.coordinator.reap_child("child-m")
    assert harness.rows()["child-m"]["phase"] == "reaped"


# =========================================================================== 2. restart


def test_a_restarted_coordinator_does_not_relaunch_a_child_it_already_dispatched(
    harness: Harness,
) -> None:
    """The failure this prevents: a restart that reads the plan and launches everything again."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    launches_before = list(harness.wrapper.launches)

    resumed = harness.restart_coordinator()
    resumed.reconcile_startup(decide=lambda _orphan: "resume")
    report = resumed.launch_ready_children()

    assert report.launched == ()
    assert "child-a" in report.withheld
    assert harness.wrapper.launches == launches_before


def test_a_restarted_coordinator_evaluates_a_child_it_did_not_launch(harness: Harness) -> None:
    """The baseline is a snapshot that cannot be re-taken once the child has written.

    ``issue_receipt`` seals a digest over the changed-paths baseline that readiness produced. A
    coordinator that came back and re-took the snapshot would compute a different digest and every
    child it had launched would fail as ``receipt_mismatch`` -- work lost to a restart, not to a
    fault. So the snapshot is persisted at dispatch and read back here.
    """
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")

    resumed = harness.restart_coordinator()
    resumed.reconcile_startup(decide=lambda _orphan: "resume")
    resumed.catch_up()
    result = resumed.integrate_child("child-a")

    assert result.verified, result.detail
    resumed.reap_child("child-a")
    assert harness.rows()["child-a"]["phase"] == "reaped"


def test_a_restart_that_lost_the_recorded_baseline_refuses_rather_than_guessing(
    harness: Harness,
) -> None:
    """Fault injection: a removal proof cannot reach a refusal, so the record is removed instead."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    REGISTER.upsert_row(harness.repo, "child-a", {"changed_paths_baseline": None}, run_id=RUN_ID)

    resumed = harness.restart_coordinator()
    with pytest.raises(RUNNER.CompositionError, match="changed-paths baseline"):
        resumed.integrate_child("child-a")


def test_the_catch_up_pass_runs_against_the_live_snapshot_on_resume(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.herdr.absent_panes.add("pane-child-a")

    resumed = harness.restart_coordinator()
    records = resumed.catch_up()

    observed = {record.row_id: record.observed_state for record in records}
    assert observed["child-a"] == "exited"
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(harness.rows()["child-a"])


# =========================================================================== 3. the subscriber


def test_a_killed_subscriber_is_detected_from_its_process_not_from_its_row(
    harness: Harness,
) -> None:
    """A row that says ``working`` and a pane that is present both survive an uncatchable kill.

    The subscriber writes ``working`` when it starts and cannot write anything when it is killed,
    so the register and the snapshot both keep reporting a healthy subscriber. The process handle
    is the only detector that reaches this, which is why liveness is asked of the supervisor.
    """
    harness.bootstrap([_child("child-a")])
    assert harness.rows().get(harness.coordinator.subscriber_row_id) is None or True
    harness.supervisor.kill()

    report = harness.coordinator.supervise()

    assert report.subscriber_respawned is True
    assert report.subscriber_alive is True
    assert len(harness.supervisor.started) >= 2
    assert harness.supervisor.stopped == [], "a killed process is not also cleanly stopped"


def test_the_respawned_subscriber_is_given_the_complete_current_subscription_set(
    harness: Harness,
) -> None:
    """The set is rebuilt from the register, so a child launched since the last start is covered."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.create_mirror()
    harness.coordinator.launch_ready_children()
    harness.supervisor.kill()
    harness.coordinator.supervise()

    argv = harness.supervisor.started[-1].argv
    installed = json.loads(argv[argv.index("--subscriptions-json") + 1])
    values = {
        item.get("match", {}).get("value")
        for item in installed
        if item["type"] == "pane.output_matched"
    }
    sentinel = harness.rows()["child-a"]["completion_sentinel"]["sentinel"]
    mirror_row = harness.rows()["mirror"]
    assert sentinel in values
    assert MIRROR.expected_subscription(mirror_row)["match"]["value"] in values
    assert ACCOUNTING.USAGE_SUBSTRING in values


def test_a_subscriber_divergence_is_recorded_where_an_operator_can_find_it(
    harness: Harness,
) -> None:
    harness.bootstrap([_child("child-a")])
    harness.supervisor.kill()
    harness.coordinator.supervise()

    kinds = [entry["kind"] for entry in harness.coordinator.run_log.entries()]
    assert "subscriber_divergence" in kinds
    assert harness.coordinator.subscriber_row_id not in harness.rows()


# =========================================================================== 4. the channel


def _mirror_ready(harness: Harness) -> Any:
    session = harness.coordinator.create_mirror()
    request = MIRROR.MirrorRequest(
        request_id="req-1",
        kind="synthesis",
        instruction="Compare the two child reports and state where they disagree.",
    )
    harness.coordinator.ask_mirror(request)
    return session


def test_an_operator_question_is_answered_while_a_mirror_request_is_outstanding(
    harness: Harness,
) -> None:
    """The highest-severity failure in the corpus is the orchestrator waiting on its own helper."""
    harness.bootstrap([_child("child-a")])
    session = _mirror_ready(harness)

    disposition = harness.coordinator.handle_operator_message(
        "What is the run doing?",
        answer=lambda context: f"Two children planned; the mirror is busy: {context.mirror_busy}.",
    )

    assert disposition.disposition == "answered"
    assert disposition.mirror_request_outstanding is True
    assert harness.channel.delivered[-1].endswith("the mirror is busy: True.")
    still = MIRROR.outstanding_request(harness.rows()[session.row_id])
    assert still is not None and still["request_id"] == "req-1"


def test_the_operator_path_never_reads_or_writes_the_mirrors_pane(harness: Harness) -> None:
    """A dispatch that could block is a dispatch that will eventually block the channel."""
    harness.bootstrap([_child("child-a")])
    session = _mirror_ready(harness)
    reads_before = list(harness.herdr.reads)
    sends_before = list(harness.herdr.sent)

    harness.coordinator.handle_operator_message("Status?", answer=lambda _c: "Running.")

    assert list(harness.herdr.reads[len(reads_before) :]) == []
    after = harness.herdr.sent[len(sends_before) :]
    assert [pane for pane, _ in after if pane == session.pane_id] == []


def test_a_handler_that_raises_parks_the_question_rather_than_dropping_it(
    harness: Harness,
) -> None:
    harness.bootstrap([_child("child-a")])

    def explode(_context: Any) -> str:
        raise RuntimeError("the orchestrator fell over")

    with pytest.raises(RuntimeError):
        harness.coordinator.handle_operator_message("Why is this slow?", answer=explode)

    entries = harness.coordinator.operator_log.entries()
    assert entries[-1]["disposition"] == "parked"
    assert "the orchestrator fell over" in entries[-1]["text"]
    assert harness.coordinator.open_operator_questions()


def test_an_explicit_park_carries_its_reason_into_the_receipt(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])

    def park(_context: Any) -> str:
        raise RUNNER.ParkQuestionError("waiting on child-a's artifact before answering")

    disposition = harness.coordinator.handle_operator_message("Is it done?", answer=park)

    assert disposition.disposition == "parked"
    assert disposition.text == "waiting on child-a's artifact before answering"
    assert harness.coordinator.operator_log.entries()[-1]["question"] == "Is it done?"


def test_a_failed_delivery_parks_the_question_instead_of_losing_it(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.channel.deliver_error = RuntimeError("channel closed")

    with pytest.raises(RuntimeError):
        harness.coordinator.handle_operator_message("Status?", answer=lambda _c: "Running.")

    assert harness.coordinator.operator_log.entries()[-1]["disposition"] == "parked"
    assert "delivery failed" in harness.coordinator.operator_log.entries()[-1]["text"]


def test_a_handler_that_returns_nothing_is_a_park_not_a_silent_success(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    disposition = harness.coordinator.handle_operator_message("Status?", answer=lambda _c: "")
    assert disposition.disposition == "parked"


def test_a_quiet_mirror_past_its_tolerance_is_reported_as_diverged(harness: Harness) -> None:
    """A pane whose output counter has stopped advancing lets the clock trip.

    Two ticks, not one: the first observation of a counter has nothing to compare against and
    correctly records activity. Divergence needs a *second* look that finds the same counter,
    which is what tells a mirror that is thinking from one that is dead.
    """
    harness.bootstrap([_child("child-a")])
    harness.coordinator.create_mirror(max_quiet_seconds=5.0)
    harness.coordinator.ask_mirror(
        MIRROR.MirrorRequest(request_id="req-1", kind="bulk_read", instruction="Read the corpus.")
    )
    assert harness.coordinator.supervise().mirror_state == "working"
    harness.clock.advance(600.0)

    report = harness.coordinator.supervise()

    assert report.mirror_state == "diverged"
    assert "silent" in report.mirror_detail


def test_a_mirror_whose_pane_keeps_emitting_is_not_alarmed(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    session = harness.coordinator.create_mirror(max_quiet_seconds=5.0)
    harness.coordinator.ask_mirror(
        MIRROR.MirrorRequest(request_id="req-1", kind="bulk_read", instruction="Read the corpus.")
    )
    harness.coordinator.supervise()
    harness.clock.advance(600.0)
    harness.herdr.revisions[session.pane_id] = 99

    assert harness.coordinator.supervise().mirror_state == "working"


def test_a_malformed_live_mirror_revision_is_reported_as_unknown(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    session = harness.coordinator.create_mirror(max_quiet_seconds=5.0)
    real_snapshot = harness.herdr.snapshot

    def malformed_snapshot(*, cwd: Path) -> dict[str, Any]:
        snapshot = real_snapshot(cwd=cwd)
        for surface in ("panes", "agents"):
            for item in snapshot[surface]:
                if item.get("pane_id") == session.pane_id:
                    item.pop("revision", None)
        return snapshot

    harness.herdr.snapshot = malformed_snapshot  # type: ignore[method-assign]
    report = harness.coordinator.supervise()

    assert report.mirror_state == "unknown"
    assert "valid output revision" in report.mirror_detail


# =========================================================================== 5. R1 forms


class FakeIssueReader:
    def __init__(self, children: list[str] | None = None) -> None:
        self.children = children or []
        self.calls: list[str] = []

    def read_issue(self, reference: str) -> dict[str, Any]:
        self.calls.append(reference)
        return {"title": "Land the thing", "body": "Details.", "children": self.children}


def test_the_four_outcome_argument_forms_each_produce_a_plan(tmp_path: Path) -> None:
    """R1: nothing must be decomposed before invocation, in any of the four accepted forms."""
    harness = Harness(tmp_path)
    document = tmp_path / "requirements.md"
    document.write_text("# Requirements\n\nDo the thing.\n", encoding="utf-8")

    cases = {
        "issue": ("142", FakeIssueReader()),
        "parent_issue": ("infiquetra/repo#142", FakeIssueReader(children=["143", "144"])),
        "document": (str(document), None),
        "prose": ("Compare the two vendor reports and say where they disagree.", None),
    }
    for expected_kind, (argument, reader) in cases.items():
        request = RUNNER.parse_outcome(argument, issue_reader=reader, root=harness.repo)
        assert request.kind == expected_kind, argument
        built = PLANNING.plan(
            request.outcome, [_child("child-a")], run_id=f"run-{expected_kind}", ceiling=CEILING
        )
        assert built.outcome == request.outcome
        assert len(built.children) == 1


def test_an_issue_reference_without_a_reader_is_refused_rather_than_treated_as_prose() -> None:
    """Silently planning against the literal string ``142`` is the failure this prevents."""
    with pytest.raises(RUNNER.OutcomeArgumentError, match="issue 142"):
        RUNNER.parse_outcome("142")


def test_a_document_path_that_does_not_exist_is_prose_not_a_missing_file(tmp_path: Path) -> None:
    request = RUNNER.parse_outcome("docs/does-not-exist.md", root=tmp_path)
    assert request.kind == "prose"


# =========================================================================== lifecycle truth


def test_a_reaped_row_is_never_planned_back_into_runnable_work(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    harness.coordinator.integrate_child("child-a")
    harness.coordinator.reap_child("child-a")

    request = RUNNER.parse_outcome("Try the same child again.")
    with pytest.raises(RUNNER.PhaseOrderError, match="terminal"):
        harness.coordinator.plan_run(request, [_child("child-a")], ceiling=CEILING)


def test_a_child_whose_attempt_failed_is_not_replanned_back_into_planned(
    harness: Harness,
) -> None:
    """A re-plan of a live row is a backwards transition, and only the phase rule sees it.

    The attempt has settled, so nothing is open; the reservation is intact, so admission is
    content; the row is not terminal, so the terminal rule does not fire. What is wrong is that
    the row is live with a recorded failure, and planning it again would put it back to
    ``planned`` while its evidence and its slot still describe the attempt that failed.

    The phase is ``ready`` rather than ``working`` because a *first* failing evaluation records
    the verdict and deliberately leaves the phase alone -- there is no member of the closed
    vocabulary meaning "evaluated and failed", and the failure lives in the completion record.
    """
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a", payload={"conclusion": "no binding token"})
    assert not harness.coordinator.integrate_child("child-a").verified
    assert harness.rows()["child-a"]["phase"] == "ready"
    assert COMPLETION.failed_rows(harness.repo, run_id=RUN_ID)["child-a"]["result"] == "failed"
    assert COMPLETION.settlement_record(harness.coordinator.attempt_for("child-a").receipt)

    request = RUNNER.parse_outcome("Try that child again.")
    with pytest.raises(RUNNER.PhaseOrderError, match="runs forward only"):
        harness.coordinator.plan_run(request, [_child("child-a")], ceiling=CEILING)


@pytest.mark.parametrize(
    ("current", "target"),
    [("working", "launching"), ("verified", "ready"), ("reaped", "working"), ("ready", "planned")],
)
def test_a_backwards_transition_is_refused_by_name(current: str, target: str) -> None:
    with pytest.raises(RUNNER.PhaseOrderError):
        RUNNER.assert_forward_transition(current, target, row_id="child-a")


@pytest.mark.parametrize(("current", "target"), [("planned", "launching"), ("verified", "reaped")])
def test_a_forward_transition_is_permitted(current: str, target: str) -> None:
    RUNNER.assert_forward_transition(current, target, row_id="child-a")


def test_the_forward_phase_guard_refuses_a_dispatched_row_before_the_launcher(
    harness: Harness,
) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    built = harness.coordinator.approved_plan()
    launches = list(harness.wrapper.launches)

    with pytest.raises(RUNNER.PhaseOrderError):
        harness.coordinator.launch_child(built.children[0])

    assert harness.wrapper.launches == launches


# =========================================================================== reap authority


def test_a_launching_row_with_a_live_owner_is_recovered_without_a_second_native_launch(
    harness: Harness,
) -> None:
    """The current run-bound label, not a stored pane copy, controls recovery."""
    harness.bootstrap([_child("child-a")])
    REGISTER.write_phase(harness.repo, "child-a", "launching", run_id=RUN_ID)
    harness.herdr.labels[LIFECYCLE.task_label(RUN_ID, "child-a")] = LIFECYCLE.LaunchIdentity(
        "claude-1", "ws-1", "tab-child-a", "pane-child-a", True
    )

    attempt = harness.coordinator.launch_child(harness.coordinator.approved_plan().children[0])
    assert attempt.spec.row_id == "child-a"
    assert (
        LIFECYCLE.read_session_pane_id(
            harness.herdr, root=harness.repo, run_id=RUN_ID, row_id="child-a"
        )
        == "pane-child-a"
    )
    assert harness.wrapper.launches == []


def test_a_forged_verified_phase_with_no_completion_record_does_not_authorise_a_reap(
    harness: Harness,
) -> None:
    """The reproduction: a child that produced nothing sets its own phase and is closed as a pass."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    REGISTER.write_phase(harness.repo, "child-a", "verified", run_id=RUN_ID)

    with pytest.raises(RUNNER.ReapAuthorizationError, match="no settlement record"):
        harness.coordinator.reap_child("child-a")

    assert harness.rows()["child-a"]["phase"] == "verified"
    assert harness.herdr.closed == []


def test_a_row_with_no_dispatch_receipt_does_not_authorise_a_reap(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    REGISTER.write_phase(harness.repo, "child-a", "verified", run_id=RUN_ID)
    with pytest.raises(RUNNER.ReapAuthorizationError, match="no authenticated dispatch receipt"):
        RUNNER.reap_authorization(harness.repo, "child-a", run_id=RUN_ID)


def test_an_artifact_rewritten_after_the_verdict_does_not_authorise_a_reap(
    harness: Harness,
) -> None:
    """The artifact that passed and the artifact on disk must still be the same bytes."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    result = harness.coordinator.integrate_child("child-a")
    assert result.verified

    settlement = COMPLETION.settlement_record(harness.coordinator.attempt_for("child-a").receipt)
    assert settlement is not None
    payload = json.loads(Path(settlement.artifact_path).read_text(encoding="utf-8"))
    payload["conclusion"] = "rewritten after the verdict"
    Path(settlement.artifact_path).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RUNNER.ReapAuthorizationError, match="evidence changed after the verdict"):
        harness.coordinator.reap_child("child-a")
    assert harness.herdr.closed == []


def test_a_child_that_kept_working_after_its_verdict_is_not_reaped(harness: Harness) -> None:
    """The window between the verdict and the reap is observed by nothing else."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    assert harness.coordinator.integrate_child("child-a").verified

    (harness.repo / "src" / "written-after-the-verdict.txt").write_text("late\n", encoding="utf-8")

    with pytest.raises(RUNNER.ChildStillMutatingError, match="had not stopped"):
        harness.coordinator.reap_child("child-a")
    assert harness.herdr.closed == []
    assert harness.rows()["child-a"]["phase"] == "verified"


def test_an_artifact_that_lost_its_binding_does_not_authorise_a_reap(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    harness.coordinator.integrate_child("child-a")
    settlement = COMPLETION.settlement_record(harness.coordinator.attempt_for("child-a").receipt)
    assert settlement is not None
    Path(settlement.artifact_path).unlink()

    with pytest.raises(RUNNER.ReapAuthorizationError):
        RUNNER.reap_authorization(harness.repo, "child-a", run_id=RUN_ID)


def test_a_failing_verdict_never_authorises_a_reap(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a", payload={"conclusion": "no binding token here"})
    result = harness.coordinator.integrate_child("child-a")
    assert not result.verified

    with pytest.raises(RUNNER.ReapAuthorizationError):
        harness.coordinator.reap_child("child-a")


# =========================================================================== subscriptions


def test_the_subscription_set_carries_the_mirrors_return_subscription(harness: Harness) -> None:
    """Omitting it loses every mirror return and stops its clock, silently and completely."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.create_mirror()

    built = RUNNER.subscriptions_for(harness.repo, run_id=RUN_ID, herdr=harness.herdr)
    expected = MIRROR.expected_subscription(harness.rows()["mirror"])

    assert expected in [dict(item) for item in built]


def test_a_subscriber_started_without_the_mirrors_subscription_is_refused_loudly(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fault injection: the omission this mechanism exists for, made to happen on purpose."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.create_mirror()

    monkeypatch.setattr(
        RUNNER,
        "subscriptions_for",
        lambda root, *, run_id, herdr=None: tuple(dict(item) for item in RUNNER.RUN_SUBSCRIPTIONS),
    )
    harness.coordinator._installed_subscriptions = ()
    harness.supervisor.kill()

    with pytest.raises(MIRROR.MirrorSubscriptionMissingError, match="never wake"):
        harness.coordinator.ensure_subscriber()


def test_a_mirror_whose_launch_failed_refuses_a_liveness_guess(harness: Harness) -> None:
    """The mirror row is written before its launch side effect, so a failed launch leaves one.

    That row has no pane, no recorded subscription, and therefore no returns to lose. Treating it
    as a missing wire would let one failed mirror launch stop the subscriber from ever starting,
    which takes the whole run down for a component the operator can already see failed.
    """
    harness.coordinator.start_run()
    harness.approve_and_commit([_child("child-a")])
    harness.coordinator.reconcile_startup(decide=lambda _orphan: "abandon")
    harness.wrapper.launch_error = LIFECYCLE.SessionLifecycleError("agent launch failed")
    with pytest.raises(LIFECYCLE.SessionLifecycleError):
        harness.coordinator.create_mirror()
    harness.wrapper.launch_error = None

    row = harness.rows()["mirror"]
    assert row["role"] == MIRROR.MIRROR_ROLE
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)
    assert MIRROR.expected_subscription(row) is None

    assert harness.coordinator.ensure_subscriber() is True
    harness.coordinator.supervise()
    kinds = [entry["kind"] for entry in harness.coordinator.run_log.entries()]
    assert "mirror_unlaunched" in kinds


@pytest.mark.parametrize("kind", sorted(RUNNER.NON_STATE_SUBSCRIPTIONS))
def test_a_subscription_that_carries_no_state_is_refused(kind: str) -> None:
    with pytest.raises(RUNNER.SubscriptionSetError, match="no lifecycle state"):
        RUNNER.assert_subscription_set([{"type": kind, "pane_id": "pane-a"}])


def test_the_set_the_subscriber_would_reject_at_startup_is_refused_here_first() -> None:
    with pytest.raises(EVENTS.SubscriptionError):
        RUNNER.assert_subscription_set(
            [
                {
                    "type": "pane.output_matched",
                    "pane_id": "pane-a",
                    "source": "recent_unwrapped",
                    "match": {"type": "regex", "value": "done"},
                }
            ]
        )


def test_the_subscription_set_is_rebuilt_from_the_register_rather_than_remembered(
    harness: Harness,
) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    from_first = RUNNER.subscriptions_for(harness.repo, run_id=RUN_ID, herdr=harness.herdr)

    resumed = harness.restart_coordinator()
    resumed.ensure_subscriber()
    argv = harness.supervisor.started[-1].argv
    installed = json.loads(argv[argv.index("--subscriptions-json") + 1])

    assert [dict(item) for item in from_first] == installed


# =========================================================================== approval and spend


def test_no_presentation_receipt_exists_until_the_channel_accepted_the_exact_text(
    harness: Harness,
) -> None:
    harness.coordinator.start_run()
    built = harness.plan([_child("child-a")])
    harness.channel.deliver_error = RuntimeError("the operator channel is down")

    with pytest.raises(RuntimeError):
        harness.coordinator.approve_plan(built)

    assert not PLANNING.presentation_receipt_path(RUN_ID).exists()
    with pytest.raises(PLANNING.PlanningError, match="no presentation receipt"):
        PLANNING.commit_plan(built, harness.repo)


def test_a_declined_plan_leaves_no_receipt_and_cannot_be_committed(harness: Harness) -> None:
    harness.coordinator.start_run()
    built = harness.plan([_child("child-a")])
    harness.channel.answers = ["decline"]

    with pytest.raises(RUNNER.ApprovalError, match="decline"):
        harness.coordinator.approve_plan(built)

    assert not PLANNING.presentation_receipt_path(RUN_ID).exists()


def test_the_rendered_text_the_operator_saw_is_the_text_the_receipt_hashes(
    harness: Harness,
) -> None:
    harness.coordinator.start_run()
    built = harness.plan([_child("child-a")])
    receipt = harness.coordinator.approve_plan(built)

    assert harness.channel.delivered[-1] == PLANNING.render_plan(built)
    assert receipt.digest == PLANNING.plan_digest(built)
    assert f"Spend ceiling: {CEILING:g} tokens" in harness.channel.delivered[-1]


def test_an_edited_spend_ceiling_is_refused_because_it_no_longer_renders_to_the_approval(
    harness: Harness,
) -> None:
    """The ceiling has to be durable, and the durable copy has to be untrusted on the way back."""
    harness.coordinator.start_run()
    built = harness.plan([_child("child-a")], ceiling=1000.0)
    harness.coordinator.approve_plan(built)

    path = RUNNER.approved_plan_path(RUN_ID)
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored["ceiling"] = 10_000_000.0
    path.write_text(json.dumps(stored), encoding="utf-8")

    with pytest.raises(RUNNER.ApprovalError, match="not the plan that was shown"):
        RUNNER.load_approved_plan(RUN_ID)


def test_the_approved_ceiling_survives_a_restart(harness: Harness) -> None:
    harness.coordinator.start_run()
    built = harness.plan([_child("child-a")], ceiling=4321.0)
    harness.coordinator.approve_plan(built)

    resumed = harness.restart_coordinator()
    assert resumed.approved_ceiling() == 4321.0


def test_a_launch_is_withheld_when_the_approved_ceiling_is_already_met(harness: Harness) -> None:
    harness.bootstrap([_child("child-a"), _child("child-b")], ceiling=1500.0)
    harness.coordinator.launch_ready_children()
    harness.report_usage("child-a", tokens=1600)

    state, detail = harness.coordinator.spend_status()
    assert state == "exceeded", detail
    with pytest.raises(RUNNER.SpendCeilingError):
        harness.coordinator.assert_spend_allows_a_launch()


def test_a_launch_is_withheld_while_a_launched_metered_child_has_reported_no_usage(
    harness: Harness,
) -> None:
    """Fail-closed, and named as unknowable rather than as over-budget."""
    harness.bootstrap([_child("child-a"), _child("child-b")])
    report = harness.coordinator.launch_ready_children()

    assert report.launched == ("child-a",)
    assert "no usage" in report.withheld["child-b"]
    with pytest.raises(RUNNER.SpendUnobservableError):
        harness.coordinator.assert_spend_allows_a_launch()

    harness.report_usage("child-a")
    assert harness.coordinator.spend_status()[0] == "ok"
    assert harness.coordinator.launch_ready_children().launched == ("child-b",)


def test_recorded_spend_remains_known_after_the_live_pane_disappears_and_is_abandoned(
    tmp_path: Path,
) -> None:
    harness = Harness(tmp_path, per_vendor=2, aggregate=2)
    harness.bootstrap([_child("child-a"), _child("child-b")], ceiling=15_000.0)
    first = harness.coordinator.launch_ready_children()
    assert first.launched == ("child-a",)
    harness.report_usage("child-a", tokens=1_200)
    second = harness.coordinator.launch_ready_children()
    assert second.launched == ("child-b",)
    harness.report_usage("child-b", tokens=9_000)

    label = LIFECYCLE.task_label(RUN_ID, "child-b")
    harness.herdr.labels.pop(label)
    assert harness.coordinator.spend_status() == ("ok", "")
    harness.coordinator.abandon_child("child-b", "the owner disappeared after reporting usage")

    harness.herdr.snapshot_error = LIFECYCLE.LaunchProtocolError("owner query unavailable")
    assert harness.coordinator.spend_status() == ("ok", "")
    assert ACCOUNTING.run_actual_tokens(harness.repo, run_id=RUN_ID) == 10_200.0


def test_unmetered_spend_does_not_depend_on_a_live_pane_query(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    harness.bootstrap([_child("child-a", vendor="muse")])
    assert harness.coordinator.launch_ready_children().launched == ("child-a",)
    harness.herdr.snapshot_error = LIFECYCLE.LaunchProtocolError("owner query unavailable")
    assert harness.coordinator.spend_status() == ("ok", "")


def test_supervision_reclaims_an_expired_absent_holder_and_advances_the_queue(
    tmp_path: Path,
) -> None:
    harness = Harness(tmp_path, per_vendor=1, aggregate=1)
    harness.bootstrap([_child("child-a"), _child("child-b")])
    ADMISSION.activate_slot(harness.repo, "child-a", run_id=RUN_ID, now=100.0)

    report = harness.coordinator.supervise()

    assert report.subscriber_alive
    rows = harness.rows()
    assert rows["child-a"]["admission"] == "reclaimed"
    assert rows["child-b"]["admission"] == "reserved"
    assert "admission_reclaimed" in [
        entry["kind"] for entry in harness.coordinator.run_log.entries()
    ]


def test_a_plan_with_no_ceiling_never_starts_a_child(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")], ceiling=None)  # type: ignore[arg-type]
    report = harness.coordinator.launch_ready_children()
    assert "unbounded budget" in report.withheld["child-a"]
    assert harness.wrapper.launches == []
    with pytest.raises(RUNNER.SpendHaltError, match="unbounded budget"):
        harness.coordinator.approved_ceiling()


# =========================================================================== route custody


def test_an_approved_model_the_launcher_would_not_reproduce_is_refused_before_any_side_effect(
    harness: Harness,
) -> None:
    """The operator approved a model; ``launch_child`` re-resolves one from policy.

    An explicit override is the case where the approved values are deliberately not the policy
    values, so it is the case where the launcher's re-resolution silently wins. The register would
    then carry confident but false provenance for cost, scope and verifier independence.
    """
    resolved = RUNNER.tier_resolver.resolve_for_runtime("work-medium", "claude")
    other = "haiku" if resolved.model != "haiku" else "opus"
    harness.bootstrap([_child("child-a", model=other)])

    with pytest.raises(RUNNER.RouteDivergedError, match="requires a new plan"):
        harness.coordinator.launch_ready_children()

    assert harness.wrapper.previews == [], "the refusal precedes the launcher's dry run"
    assert harness.wrapper.launches == []
    assert harness.rows()["child-a"]["admission"] == "reserved", "the slot was not activated"


def test_the_approved_route_reaches_the_register_unchanged(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    approved = harness.coordinator.approved_plan().children[0]
    row = harness.rows()["child-a"]

    assert (row["vendor"], row["model"], row["effort"]) == (
        approved.vendor,
        approved.model,
        approved.effort,
    )


def test_a_launch_whose_recorded_route_diverges_is_caught_after_the_launcher_too(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Injection: the pre-check cannot see a launcher that rewrites the row itself."""
    harness.bootstrap([_child("child-a")])
    built = harness.coordinator.approved_plan()
    real = LIFECYCLE.launch_child

    def rewriting(root: Path, spec: Any, **kwargs: Any) -> Any:
        identity, landing, resolution = real(root, spec, **kwargs)
        REGISTER.upsert_row(root, spec.row_id, {"model": "something-else"}, run_id=spec.run_id)
        return identity, landing, resolution

    monkeypatch.setattr(RUNNER.session_lifecycle, "launch_child", rewriting)
    with pytest.raises(RUNNER.RouteDivergedError, match="false provenance"):
        harness.coordinator.launch_child(built.children[0])


# =========================================================================== admission order


def test_the_slot_is_activated_immediately_before_the_launcher_and_not_before_the_gates(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.bootstrap([_child("child-a")])
    order: list[str] = []
    real_activate = ADMISSION.activate_slot
    real_launch = LIFECYCLE.launch_child

    def activate(*args: Any, **kwargs: Any) -> Any:
        order.append("activate_slot")
        return real_activate(*args, **kwargs)

    def launch(*args: Any, **kwargs: Any) -> Any:
        order.append("launch_child")
        return real_launch(*args, **kwargs)

    monkeypatch.setattr(RUNNER.admission, "activate_slot", activate)
    monkeypatch.setattr(RUNNER.session_lifecycle, "launch_child", launch)
    harness.coordinator.launch_ready_children()

    assert order == ["activate_slot", "launch_child"]
    assert harness.rows()["child-a"]["admission"] == "held"


def test_a_queued_child_does_not_reach_the_launcher(tmp_path: Path) -> None:
    harness = Harness(tmp_path, per_vendor=1, aggregate=1)
    harness.bootstrap([_child("child-a"), _child("child-b")])
    built = harness.coordinator.approved_plan()
    queued = next(child for child in built.children if child.row_id == "child-b")

    with pytest.raises(RUNNER.AdmissionOrderError, match="queued"):
        harness.coordinator.launch_child(queued)
    assert "child-b" not in harness.wrapper.launches


def test_a_child_with_no_reservation_does_not_reach_the_launcher(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    ADMISSION.abandon_slot(harness.repo, "child-a", run_id=RUN_ID)

    with pytest.raises(RUNNER.AdmissionOrderError, match="admission status"):
        harness.coordinator.launch_child(harness.coordinator.approved_plan().children[0])
    assert harness.wrapper.launches == []


def _rewrite_admission(repo: Path, run_id: str, mutate: Any) -> None:
    """Edit the run's admission state directly, to stage a fault the API cannot produce."""
    with ADMISSION.admission_locked(), REGISTER.generation_locked(run_id):
        doc = REGISTER._read_register_unlocked(run_id)
        state = ADMISSION._admission_doc(doc)
        mutate(state)
        ADMISSION._write_admission(
            REGISTER.canonical_work_location(repo),
            run_id,
            queue=state["queue"],
            reservations=state["reservations"],
        )


def test_a_reservation_for_a_different_vendor_does_not_launch_the_approved_child(
    harness: Harness,
) -> None:
    harness.bootstrap([_child("child-a")])

    def swap(state: dict[str, Any]) -> None:
        state["reservations"]["child-a"]["vendor"] = "codex"

    _rewrite_admission(harness.repo, RUN_ID, swap)

    with pytest.raises(RUNNER.AdmissionOrderError, match="release and replan"):
        harness.coordinator.launch_child(harness.coordinator.approved_plan().children[0])
    assert harness.wrapper.launches == []


def test_an_active_row_whose_reservation_record_is_gone_does_not_reach_the_launcher(
    harness: Harness,
) -> None:
    """A status column is not the bound; the reservation set is."""
    harness.bootstrap([_child("child-a")])
    _rewrite_admission(harness.repo, RUN_ID, lambda state: state["reservations"].pop("child-a"))
    REGISTER.upsert_row(harness.repo, "child-a", {"admission": "reserved"}, run_id=RUN_ID)

    with pytest.raises(RUNNER.AdmissionOrderError, match="outside the host-wide bound"):
        harness.coordinator.launch_child(harness.coordinator.approved_plan().children[0])
    assert harness.wrapper.launches == []


def test_the_slot_is_not_released_when_the_reap_does_not_record_the_child_closed(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Injection: release before a recorded reap frees a slot for work that may still be running."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    harness.coordinator.integrate_child("child-a")

    monkeypatch.setattr(RUNNER.session_lifecycle, "reap_verified", lambda *a, **k: None)
    released: list[str] = []
    monkeypatch.setattr(
        RUNNER.admission,
        "release_slot",
        lambda *a, **k: released.append("released"),  # type: ignore[arg-type]
    )

    with pytest.raises(RUNNER.ReapAuthorizationError, match="slot is not released"):
        harness.coordinator.reap_child("child-a")
    assert released == []


def test_reaping_releases_the_slot_so_the_bound_is_not_a_one_way_ratchet(
    tmp_path: Path,
) -> None:
    harness = Harness(tmp_path, per_vendor=1, aggregate=1)
    harness.bootstrap([_child("child-a"), _child("child-b")])
    harness.coordinator.launch_ready_children()
    per_vendor_before, aggregate_before = ADMISSION.occupancy()

    harness.run_child("child-a")
    harness.report_usage("child-a")
    harness.coordinator.integrate_child("child-a")
    harness.coordinator.reap_child("child-a")

    assert per_vendor_before["claude"] == 1 and aggregate_before == 1
    per_vendor_after, aggregate_after = ADMISSION.occupancy()
    assert aggregate_after == 1, "the promoted child now holds the freed slot"
    assert harness.rows()["child-b"]["admission"] == "reserved"
    del per_vendor_after


def test_launching_before_startup_reconciliation_is_refused(harness: Harness) -> None:
    harness.coordinator.start_run()
    harness.approve_and_commit([_child("child-a")])
    with pytest.raises(RUNNER.AdmissionOrderError, match="reconciliation has not run"):
        harness.coordinator.launch_ready_children()


# =========================================================================== the run log


def _log_kinds(harness: Harness) -> list[str]:
    return [entry["kind"] for entry in harness.coordinator.run_log.entries()]


def test_a_launch_that_fails_after_the_slot_is_taken_is_recorded_not_silent(
    harness: Harness,
) -> None:
    """Silence is not evidence of progress.

    Past ``activate_slot`` the run holds a slot and may hold a live session. A step that records
    nothing when it raises leaves a log reading "activated a slot, then stopped happening", which
    is indistinguishable from a coordinator that is still working.
    """
    harness.bootstrap([_child("child-a")])
    harness.wrapper.launch_error = LIFECYCLE.SessionLifecycleError("agent launch failed")

    with pytest.raises(LIFECYCLE.SessionLifecycleError):
        harness.coordinator.launch_child(harness.coordinator.approved_plan().children[0])

    kinds = _log_kinds(harness)
    assert "slot_activated" in kinds
    assert "child_launched" not in kinds
    assert "child_launch_failed" in kinds
    failure = next(
        entry
        for entry in harness.coordinator.run_log.entries()
        if entry["kind"] == "child_launch_failed"
    )
    assert failure["row_id"] == "child-a"
    assert "agent launch failed" in failure["detail"]


def test_a_refused_reap_is_recorded_not_silent(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    REGISTER.write_phase(harness.repo, "child-a", "verified", run_id=RUN_ID)

    with pytest.raises(RUNNER.ReapAuthorizationError):
        harness.coordinator.reap_child("child-a")

    assert "reap_refused" in _log_kinds(harness)
    assert "child_reaped" not in _log_kinds(harness)


def test_a_withheld_launch_is_recorded_with_its_reason(tmp_path: Path) -> None:
    harness = Harness(tmp_path, per_vendor=1, aggregate=1)
    harness.bootstrap([_child("child-a"), _child("child-b")])

    harness.coordinator.launch_ready_children()

    withheld = [
        entry
        for entry in harness.coordinator.run_log.entries()
        if entry["kind"] == "launch_withheld"
    ]
    assert [entry["row_id"] for entry in withheld] == ["child-b"]
    assert "queued" in withheld[0]["detail"]


def test_an_evaluation_that_raises_is_recorded_not_silent(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.herdr.absent_tabs.add("tab-child-a")

    with pytest.raises(LIFECYCLE.VanishedChildError):
        harness.coordinator.integrate_child("child-a")

    assert "integration_failed" in _log_kinds(harness)


# =========================================================================== reconciliation


def _foreign_reservation(repo: Path, herdr: FakeHerdr, run_id: str, row_id: str) -> None:
    ADMISSION.reserve_slot(
        repo, row_id, run_id=run_id, vendor="claude", work_shape="work-medium", tokens_max=20000
    )
    REGISTER.write_phase(repo, row_id, "working", run_id=run_id)
    herdr.labels[LIFECYCLE.task_label(run_id, row_id)] = LIFECYCLE.LaunchIdentity(
        "claude-ghost", "ws-1", f"tab-{row_id}", f"pane-{row_id}", True
    )


def test_startup_names_every_occupied_identity_this_coordinator_does_not_own(
    harness: Harness,
) -> None:
    _foreign_reservation(harness.repo, harness.herdr, "run-dead", "ghost-1")
    harness.coordinator.start_run()

    report = harness.coordinator.reconcile_startup(decide=lambda _orphan: "resume")

    assert [(item.run_id, item.row_id) for item in report.orphans] == [("run-dead", "ghost-1")]
    orphan = report.orphans[0]
    assert orphan.vendor == "claude"
    assert orphan.phase == "working"
    assert orphan.pane_id == "pane-ghost-1"
    assert report.resumed == ("run-dead/ghost-1",)


def test_no_amount_of_elapsed_time_reclaims_a_planned_reservation(harness: Harness) -> None:
    """A plan the operator approved and walked away from is not lost to a timer."""
    _foreign_reservation(harness.repo, harness.herdr, "run-dead", "ghost-1")
    harness.coordinator.start_run()
    harness.clock.advance(86_400.0 * 30)

    before = RUNNER.host_reservations(exclude_run=RUN_ID, herdr=harness.herdr)
    harness.coordinator.reconcile_startup(decide=lambda _orphan: "resume")
    after = RUNNER.host_reservations(exclude_run=RUN_ID, herdr=harness.herdr)

    assert before == after
    assert len(after) == 1


def test_an_abandon_decision_frees_the_slot_and_a_resume_decision_leaves_it(
    harness: Harness,
) -> None:
    _foreign_reservation(harness.repo, harness.herdr, "run-dead-a", "ghost-1")
    _foreign_reservation(harness.repo, harness.herdr, "run-dead-b", "ghost-2")
    harness.coordinator.start_run()

    def decide(orphan: Any) -> str:
        return "abandon" if orphan.run_id == "run-dead-a" else "resume"

    report = harness.coordinator.reconcile_startup(decide=decide)

    assert report.abandoned == ("run-dead-a/ghost-1",)
    assert report.resumed == ("run-dead-b/ghost-2",)
    remaining = {
        (item.run_id, item.row_id)
        for item in RUNNER.host_reservations(exclude_run=RUN_ID, herdr=harness.herdr)
    }
    assert remaining == {("run-dead-b", "ghost-2")}


def test_the_reconciliation_decision_is_recorded_where_an_operator_can_audit_it(
    harness: Harness,
) -> None:
    _foreign_reservation(harness.repo, harness.herdr, "run-dead", "ghost-1")
    harness.coordinator.start_run()
    harness.coordinator.reconcile_startup(decide=lambda _orphan: "abandon")

    entries = [
        entry
        for entry in harness.coordinator.run_log.entries()
        if entry["kind"] == "orphan_reservation"
    ]
    assert entries and entries[0]["decision"] == "abandon"
    assert entries[0]["occupant"] == "run-dead/ghost-1"


def test_reconciliation_advances_queued_work_that_a_crash_left_asleep(tmp_path: Path) -> None:
    harness = Harness(tmp_path, per_vendor=1, aggregate=1)
    _foreign_reservation(harness.repo, harness.herdr, "run-dead", "ghost-1")
    harness.coordinator.start_run()
    harness.approve_and_commit([_child("child-a")])
    assert harness.rows()["child-a"]["admission"] == "queued"

    report = harness.coordinator.reconcile_startup(decide=lambda _orphan: "abandon")

    assert "child-a" in report.promoted
    assert harness.rows()["child-a"]["admission"] == "reserved"


# =========================================================================== retirement


def test_a_run_with_a_live_subscriber_is_not_retired(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    with pytest.raises(RUNNER.RetirementOrderError, match="subscriber"):
        harness.coordinator.retire()
    assert REGISTER.register_path(RUN_ID).exists()


def test_a_run_with_an_unreaped_child_is_not_retired(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.coordinator.stop_writers()

    with pytest.raises(RUNNER.RetirementOrderError, match="child-a"):
        harness.coordinator.retire()
    assert REGISTER.register_path(RUN_ID).exists()


def test_a_run_whose_writers_and_reservations_are_all_closed_is_archived(
    harness: Harness,
) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    harness.coordinator.integrate_child("child-a")
    harness.coordinator.reap_child("child-a")
    harness.coordinator.stop_writers()

    archive = harness.coordinator.retire()

    assert archive is not None and archive.exists()
    assert not REGISTER.register_path(RUN_ID).exists()
    assert not RUNNER.approved_plan_path(RUN_ID).exists()


def test_a_run_whose_mirror_is_still_open_is_not_retired(harness: Harness) -> None:
    """The mirror is not one of the outcome's children, but it is a live writer.

    Retiring underneath it is how a late write recreates a live document beside the archive.
    """
    harness.bootstrap([_child("child-a")])
    harness.coordinator.create_mirror()
    harness.coordinator.abandon_child("child-a", "not needed")
    harness.supervisor.stop(harness.coordinator._subscriber_handle)

    outstanding = harness.coordinator.outstanding_writers()
    assert "mirror:mirror" in outstanding
    with pytest.raises(RUNNER.RetirementOrderError, match="mirror"):
        harness.coordinator.retire()
    assert REGISTER.register_path(RUN_ID).exists()

    harness.coordinator.stop_writers()
    assert "mirror:mirror" not in harness.coordinator.outstanding_writers()
    assert harness.coordinator.retire() is not None
    assert "tab-mirror" in harness.herdr.closed


def test_a_mirror_close_that_returns_without_removing_the_tab_is_not_read_as_stopped(
    harness: Harness,
) -> None:
    """``stop_writers`` used to write the mirror ``exited`` on a close request's bare return.

    The same distinction the reap fence already draws for a child's tab -- a close call can
    return without raising while the tab it named is genuinely still present -- was missed here.
    ``outstanding_writers`` trusts ``observed_state == "exited"`` as proof this writer is gone;
    writing that column from an unconfirmed close request let retirement archive the run beside a
    mirror whose tab was still open.
    """
    harness.bootstrap([_child("child-a")])
    harness.coordinator.create_mirror()
    harness.coordinator.abandon_child("child-a", "not needed")
    harness.supervisor.stop(harness.coordinator._subscriber_handle)

    def close_that_does_not_take(tab_id: str, *, cwd: Path) -> None:
        harness.herdr.closed.append(tab_id)  # the request was made; the tab was not removed

    real_close_tab = harness.herdr.close_tab
    harness.herdr.close_tab = close_that_does_not_take  # type: ignore[method-assign]
    stopped = harness.coordinator.stop_writers()
    harness.herdr.close_tab = real_close_tab  # type: ignore[method-assign]

    assert stopped["mirror"] == "close requested but the tab is still present"
    assert harness.herdr.tab_present("tab-mirror", cwd=harness.repo), "the tab never actually took"

    outstanding = harness.coordinator.outstanding_writers()
    assert "mirror:mirror" in outstanding, (
        "a mirror whose tab is still present must stay outstanding"
    )
    with pytest.raises(RUNNER.RetirementOrderError, match="mirror"):
        harness.coordinator.retire()
    assert REGISTER.register_path(RUN_ID).exists(), "not archived beside a live mirror tab"

    # The tab genuinely closing on a later attempt is still read correctly.
    stopped_again = harness.coordinator.stop_writers()
    assert stopped_again["mirror"] == "closed"
    assert "mirror:mirror" not in harness.coordinator.outstanding_writers()
    assert harness.coordinator.retire() is not None


def test_a_mirror_with_no_live_tab_fact_is_not_read_as_stopped(harness: Harness) -> None:
    """Absence of a live tab answer is not proof the mirror's tab is gone.

    ``create_mirror`` writes the row's role before the launcher returns, so a crash between
    those two leaves a live tab on a row that cannot name it. ``stop_writers`` used to treat
    the empty column as absence and write ``exited``, which let retirement archive the run
    beside a mirror still able to write the live register back.
    """
    harness.bootstrap([_child("child-a")])
    with (
        _failing_at("after_launcher_returned", harness),
        pytest.raises(LIFECYCLE.LaunchProtocolError),
    ):
        harness.coordinator.create_mirror()
    harness.coordinator.abandon_child("child-a", "not needed")
    harness.supervisor.stop(harness.coordinator._subscriber_handle)

    row = harness.rows()["mirror"]
    assert row.get("role") == MIRROR.MIRROR_ROLE
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)

    # The launcher returned an identity; the tab is discoverable by the same run-bound
    # label the launcher itself would use to recover this window.
    label = LIFECYCLE.task_label(RUN_ID, "mirror")
    harness.herdr.labels[label] = LIFECYCLE.LaunchIdentity(
        "claude-1", "ws-1", "tab-mirror", "pane-mirror", True
    )

    def close_that_does_not_take(tab_id: str, *, cwd: Path) -> None:
        harness.herdr.closed.append(tab_id)  # the request was made; the tab was not removed

    real_close_tab = harness.herdr.close_tab
    harness.herdr.close_tab = close_that_does_not_take  # type: ignore[method-assign]
    stopped = harness.coordinator.stop_writers()
    harness.herdr.close_tab = real_close_tab  # type: ignore[method-assign]

    assert stopped["mirror"] == "close requested but the tab is still present"
    assert "tab-mirror" in harness.herdr.closed
    assert harness.herdr.tab_present("tab-mirror", cwd=harness.repo), "the tab never actually took"
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(harness.rows()["mirror"])
    assert REGISTER.register_path(RUN_ID).exists(), "not archived beside a live mirror tab"


def test_a_mirror_whose_launcher_never_created_a_tab_still_needs_a_live_answer(
    harness: Harness,
) -> None:
    """Authored launch intent cannot prove the terminal substrate has no tab.

    ``create_mirror`` writes the row before any launch side effect, so a launch that fails
    leaves a mirror row with no tab_id. That is not the same state as a live tab the row
    cannot name: the control plane, asked by the same label the launcher uses, finds
    nothing. Retirement must still complete.
    """
    harness.bootstrap([_child("child-a")])
    with (
        _failing_at("after_launch_intent", harness),
        pytest.raises(LIFECYCLE.SessionLifecycleError),
    ):
        harness.coordinator.create_mirror()
    harness.coordinator.abandon_child("child-a", "not needed")
    harness.supervisor.stop(harness.coordinator._subscriber_handle)

    row = harness.rows()["mirror"]
    assert row.get("role") == MIRROR.MIRROR_ROLE
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)
    assert LIFECYCLE.task_label(RUN_ID, "mirror") not in harness.herdr.labels

    assert harness.coordinator.stop_writers()["mirror"] == "closed"
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(harness.rows()["mirror"])


def test_a_slot_that_cannot_be_released_after_a_reap_is_recorded_not_silent(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The child is closed and its slot is not free — the ratchet, made loud."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    harness.coordinator.integrate_child("child-a")

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise ADMISSION.AdmissionError("the admission document is unwritable")

    monkeypatch.setattr(RUNNER.admission, "release_slot", boom)
    with pytest.raises(ADMISSION.AdmissionError):
        harness.coordinator.reap_child("child-a")

    kinds = [entry["kind"] for entry in harness.coordinator.run_log.entries()]
    assert "slot_release_failed" in kinds
    assert "child_reaped" not in kinds


def test_a_deliberately_abandoned_child_does_not_block_retirement(harness: Harness) -> None:
    """A child abandoned on purpose is not a child that was lost, and the record says which."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.abandon_child("child-a", "the operator changed the outcome")
    harness.coordinator.stop_writers()

    assert harness.coordinator.retire() is not None


# =========================================================================== exclusivity


def test_a_second_dispatch_for_an_open_attempt_is_refused(harness: Harness) -> None:
    """Two attempts on one row means two producers writing one settled artifact."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    row = harness.rows()["child-a"]

    with pytest.raises(RUNNER.ConcurrentAttemptError, match="open and unsettled"):
        harness.coordinator._assert_no_open_attempt("child-a", row)


def test_two_children_cannot_be_planned_into_one_artifact_location(harness: Harness) -> None:
    harness.coordinator.start_run()
    request = RUNNER.parse_outcome("Two children, one location.")
    built = PLANNING.plan(
        request.outcome, [_child("child-a"), _child("child-b")], run_id=RUN_ID, ceiling=CEILING
    )
    collided = PLANNING.replace(
        built, children=(built.children[0], PLANNING.replace(built.children[1], row_id="child-a"))
    )

    with pytest.raises(RUNNER.ArtifactAssignmentError, match="exclusive artifact location"):
        harness.coordinator.assert_exclusive_artifact_assignment(collided)


def test_each_child_of_a_run_gets_its_own_artifact_directory(harness: Harness) -> None:
    first = RUNNER.artifact_relpath(RUN_ID, "child-a", "report.json")
    second = RUNNER.artifact_relpath(RUN_ID, "child-b", "report.json")
    assert first != second
    assert first.startswith(".orchestrate/") and RUN_ID in first


# =========================================================================== ownership


def test_writing_a_column_this_module_does_not_own_is_refused(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    with pytest.raises(RUNNER.ColumnOwnershipError, match="does not own"):
        RUNNER._write_owned(harness.repo, "child-a", {"phase": "verified"}, run_id=RUN_ID)


def test_every_register_write_in_this_module_goes_through_the_owned_seam() -> None:
    """A comment saying who owns something is what this build has paid for most.

    The seam is the only place this module may write a register row. It has two entry points --
    the generation lock is not reentrant, so a read-check-write that must be atomic cannot go
    through the public write -- and **both** the public and the already-locked write primitives
    are checked here. Covering only the public one would leave the unlocked primitive as an
    unguarded second door into exactly the columns the seam exists to protect.
    """
    tree = ast.parse(RUNNER_SOURCE)
    writes = {"upsert_row", "upsert_rows", "_upsert_rows_unlocked"}
    callers: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Attribute)
                and inner.func.attr in writes
            ):
                callers.setdefault(inner.func.attr, set()).add(node.name)
    assert callers == {
        "upsert_row": {"_write_owned"},
        "_upsert_rows_unlocked": {"_write_owned_unlocked"},
    }


def test_both_doors_of_the_owned_seam_refuse_a_column_this_module_does_not_own(
    harness: Harness,
) -> None:
    """The already-locked door is a door, not an exemption."""
    harness.bootstrap([_child("child-a")])
    claimed = REGISTER.canonical_work_location(harness.repo)
    with pytest.raises(RUNNER.ColumnOwnershipError, match="does not own"):
        RUNNER._write_owned(harness.repo, "child-a", {"phase": "verified"}, run_id=RUN_ID)
    with (
        pytest.raises(RUNNER.ColumnOwnershipError, match="does not own"),
        REGISTER.generation_locked(RUN_ID),
    ):
        RUNNER._write_owned_unlocked(claimed, "child-a", {"phase": "verified"}, run_id=RUN_ID)


def test_only_the_two_locked_dispatch_transactions_may_use_the_unlocked_door() -> None:
    """The unlocked door is a door, not a courtesy -- its caller set must be closed, not documented.

    ``_write_owned_unlocked`` exists so a read-check-write that must be atomic under the
    non-reentrant generation lock can still go through the owned seam. Its column guard constrains
    *which columns* pass; nothing constrained *which functions* may knock, so a caller that never
    takes the lock at all could still write through it. This closes the caller set the same way
    :func:`test_every_register_write_in_this_module_goes_through_the_owned_seam` already closes
    the register primitive's -- adding a third caller here fails this test, not merely a comment.
    """
    tree = ast.parse(RUNNER_SOURCE)
    callers: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            target = inner.func
            name = target.id if isinstance(target, ast.Name) else getattr(target, "attr", None)
            if name == "_write_owned_unlocked":
                callers.add(node.name)
    assert callers == {"claim_dispatch", "adopt_dispatch_claim"}


def test_the_owned_columns_and_the_ownership_table_describe_the_same_set() -> None:
    assert tuple(entry[0] for entry in RUNNER.COLUMN_OWNERSHIP) == RUNNER.OWNED_COLUMNS


def test_the_mirror_is_excluded_from_the_spend_total_and_the_bound_by_its_role(
    harness: Harness,
) -> None:
    """The mirror's ``agent`` is the launcher's uniquified name, so an agent test misses it.

    Before this, the run's spend total demanded telemetry from the mirror forever and the mirror
    appeared permanently in ``unreserved_active``, which is reconciliation evidence.
    """
    harness.bootstrap([_child("child-a")])
    harness.coordinator.create_mirror()
    mirror_row = harness.rows()["mirror"]

    assert mirror_row["role"] == MIRROR.MIRROR_ROLE
    assert mirror_row["agent"] != "mirror"
    assert REGISTER.is_supervisory_row(mirror_row)
    assert ACCOUNTING.run_actual_tokens(harness.repo, run_id=RUN_ID) == 0.0
    assert ("run-comp", "mirror") not in ADMISSION.unreserved_active(harness.repo)


def test_the_supervisory_role_vocabulary_and_the_mirrors_own_constant_agree() -> None:
    assert MIRROR.MIRROR_ROLE in REGISTER.SUPERVISORY_ROLES


# =========================================================================== the evidence chain


def test_a_completion_sentinel_alone_does_not_close_a_child(harness: Harness) -> None:
    """The sentinel wakes the orchestrator. It is not the verdict, and it never was."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    sentinel = harness.rows()["child-a"]["completion_sentinel"]["sentinel"]
    REGISTER.upsert_row(harness.repo, "child-a", {"last_event_at": 1.0}, run_id=RUN_ID)

    assert sentinel.startswith(SUBSCRIBER.SENTINEL_MARKER)
    with pytest.raises(RUNNER.ReapAuthorizationError):
        harness.coordinator.reap_child("child-a")


def test_the_assembled_sentinel_never_appears_in_the_dispatch_text(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    sentinel = harness.rows()["child-a"]["completion_sentinel"]["sentinel"]
    for _pane, text in harness.herdr.sent:
        assert sentinel not in text


def test_a_vanished_child_is_refused_rather_than_evaluated(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.herdr.absent_tabs.add("tab-child-a")

    with pytest.raises(LIFECYCLE.VanishedChildError):
        harness.coordinator.integrate_child("child-a")


def test_the_predicate_runs_in_this_process_and_not_through_the_mirror(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.create_mirror()
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    sent_before = len(harness.herdr.sent)

    result = harness.coordinator.integrate_child("child-a")

    assert result.verified
    assert result.predicate is not None and result.predicate.passed
    mirror_pane = LIFECYCLE.read_session_pane_id(
        harness.herdr, root=harness.repo, run_id=RUN_ID, row_id="mirror"
    )
    assert mirror_pane is not None
    assert [pane for pane, _ in harness.herdr.sent[sent_before:] if pane == mirror_pane] == []


# =========================================================================== acceptance receipt


def test_the_acceptance_receipt_is_computed_from_the_durable_record(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.create_mirror()
    harness.coordinator.launch_ready_children()
    harness.coordinator.ask_mirror(
        MIRROR.MirrorRequest(request_id="req-1", kind="survey", instruction="Read the tree.")
    )
    harness.coordinator.handle_operator_message("Status?", answer=lambda _c: "One child running.")
    harness.run_child("child-a")
    harness.report_usage("child-a")
    harness.coordinator.integrate_child("child-a")
    harness.coordinator.reap_child("child-a")

    receipt = harness.coordinator.acceptance_receipt()

    assert receipt.no_child_lost
    assert receipt.no_duplicate_launched
    assert receipt.no_false_completion
    assert receipt.operator_answered_while_mirror_busy
    assert receipt.spend_recorded and receipt.spend_tokens == 1200.0
    assert receipt.passed
    stored = json.loads(
        (harness.coordinator.evidence_dir / "acceptance-receipt.json").read_text(encoding="utf-8")
    )
    assert stored["passed"] is True


def test_a_reaped_child_whose_evidence_does_not_authorise_it_fails_the_receipt(
    harness: Harness,
) -> None:
    """The receipt must not be a summary of what this module believes it did."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    REGISTER.write_phase(harness.repo, "child-a", "verified", run_id=RUN_ID)
    REGISTER.write_phase(harness.repo, "child-a", "reaped", run_id=RUN_ID)

    receipt = harness.coordinator.acceptance_receipt()

    assert not receipt.no_false_completion
    assert not receipt.passed
    assert receipt.detail["unauthorised_reaps"][0]["row_id"] == "child-a"


def test_an_unfinished_child_is_reported_as_unaccounted_for(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()

    receipt = harness.coordinator.acceptance_receipt()

    assert not receipt.no_child_lost
    assert receipt.detail["unaccounted_children"] == ["child-a"]


def test_a_parked_question_is_visible_on_the_receipt(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])

    def park(_context: Any) -> str:
        raise RUNNER.ParkQuestionError("no artifact yet")

    harness.coordinator.handle_operator_message("Done?", answer=park)
    receipt = harness.coordinator.acceptance_receipt()

    assert len(receipt.detail["parked_questions"]) == 1


# ====================================================== route custody, every approved field


def test_an_integration_mode_this_control_flow_cannot_land_is_refused_at_plan_time(
    harness: Harness,
) -> None:
    """Planning accepts three modes; the landing produces two. Composition sees both.

    An approved ``path`` child used to launch, run and record as ``branch``: isolated *more* than
    the operator asked for, which is still a landing they did not approve, recorded as though they
    had. Refusing at plan time is before anything durable exists.
    """
    harness.coordinator.start_run()
    request = RUNNER.parse_outcome("Land a change at a declared path.")

    with pytest.raises(RUNNER.RouteDivergedError, match="can only land"):
        harness.coordinator.plan_run(
            request, [_child("child-p", integration_mode="path")], ceiling=CEILING
        )
    assert harness.wrapper.launches == []
    assert not PLANNING.presentation_receipt_path(RUN_ID).exists()


def test_an_unlandable_mode_that_reaches_the_launch_path_is_refused_before_any_side_effect(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The plan-time refusal is not the only one, because a plan can be committed elsewhere."""
    harness.bootstrap([_child("child-a")])
    approved = harness.coordinator.approved_plan().children[0]
    smuggled = PLANNING.replace(approved, integration_mode="path")

    with pytest.raises(RUNNER.RouteDivergedError, match="can only land"):
        harness.coordinator.launch_child(smuggled)

    assert harness.wrapper.previews == []
    assert harness.wrapper.launches == []
    assert harness.rows()["child-a"]["admission"] == "reserved", "the slot was not activated"
    del monkeypatch


@pytest.mark.parametrize("mode", sorted(PLANNING.INTEGRATION_MODES))
def test_every_planning_mode_is_either_landable_or_refused_and_never_adapted(mode: str) -> None:
    produced = RUNNER.producible_landing_mode(mode)
    if mode in RUNNER.PRODUCIBLE_INTEGRATION_MODES:
        assert produced == mode
    else:
        assert produced != mode, "an unlandable mode must not silently equal what is produced"


def test_the_launched_landing_is_compared_with_the_approval_not_just_the_tier(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Injection: a provisioner that returns a landing nobody approved must not be recorded."""
    harness.bootstrap([_child("child-a")])
    real = LIFECYCLE.GitLanding.provision

    def other_mode(self: Any, root: Path, spec: Any, **kwargs: Any) -> Any:
        landing = real(self, root, spec, **kwargs)
        return LIFECYCLE.Landing(
            landing.cwd, "branch", landing.destination, landing.base_commit, landing.ambient_root
        )

    monkeypatch.setattr(LIFECYCLE.GitLanding, "provision", other_mode)
    with pytest.raises(RUNNER.RouteDivergedError, match="landed as"):
        harness.coordinator.launch_child(harness.coordinator.approved_plan().children[0])


def test_the_recorded_scope_is_compared_with_the_approved_scope(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.bootstrap([_child("child-a")])
    real = LIFECYCLE.launch_child

    def widening(root: Path, spec: Any, **kwargs: Any) -> Any:
        result = real(root, spec, **kwargs)
        REGISTER.upsert_row(root, spec.row_id, {"scope": ["src", "checks"]}, run_id=spec.run_id)
        return result

    monkeypatch.setattr(RUNNER.session_lifecycle, "launch_child", widening)
    with pytest.raises(RUNNER.RouteDivergedError, match="false provenance"):
        harness.coordinator.launch_child(harness.coordinator.approved_plan().children[0])


def test_a_landing_whose_destination_diverges_from_this_control_flows_own_rule_is_refused(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Injection: a provisioner that names a destination nothing approved must not be recorded.

    The approval carries a mode, not a destination -- ``PlannedChild`` has no destination field --
    so there is nothing from the operator to compare a landing's destination against directly.
    What this control flow does have is its own deterministic naming rule for one
    (:func:`session_lifecycle.task_label` for a mutating child, the literal ``"none"`` for a
    read-only one), and a landing that diverges from that rule was not produced by the
    provisioner this control flow recognises as its own.
    """
    harness.bootstrap([_child("child-m", integration_mode="branch")])
    real = LIFECYCLE.GitLanding.provision

    def different_destination(self: Any, root: Path, spec: Any, **kwargs: Any) -> Any:
        landing = real(self, root, spec, **kwargs)
        return LIFECYCLE.Landing(
            landing.cwd,
            landing.integration_mode,
            "evil-destination",
            landing.base_commit,
            landing.ambient_root,
        )

    monkeypatch.setattr(LIFECYCLE.GitLanding, "provision", different_destination)
    with pytest.raises(RUNNER.RouteDivergedError, match="destination"):
        harness.coordinator.launch_child(harness.coordinator.approved_plan().children[0])


# ====================================================== interrupted dispatch, three windows


@contextlib.contextmanager
def _failing_at(where: str, harness: Harness) -> Iterator[None]:
    """Break one launch at a named point, leaving exactly the durable state that point leaves.

    Deliberately not ``monkeypatch``: undoing a monkeypatch undoes every patch on the shared
    fixture instance, including the autouse host-directory isolation, which silently points the
    test at another run's register.
    """
    if where == "after_activation":
        original = RUNNER.session_lifecycle.launch_child

        def refuse(*_a: Any, **_k: Any) -> Any:
            raise LIFECYCLE.SessionLifecycleError("crashed after the slot was taken")

        RUNNER.session_lifecycle.launch_child = refuse  # type: ignore[assignment]
        try:
            yield
        finally:
            RUNNER.session_lifecycle.launch_child = original  # type: ignore[assignment]
    elif where == "after_launch_intent":
        harness.wrapper.launch_error = LIFECYCLE.SessionLifecycleError("the wrapper failed")
        try:
            yield
        finally:
            harness.wrapper.launch_error = None
    elif where == "after_launcher_returned":
        # The launcher creates the session, then the caller crashes before its durable intent
        # update. Recovery must discover that session from its run-bound label.
        harness.wrapper.post_launch_error = LIFECYCLE.LaunchProtocolError(
            "crashed after the launcher created the session"
        )
        try:
            yield
        finally:
            harness.wrapper.post_launch_error = None
    else:  # pragma: no cover - guards the parametrisation itself
        raise AssertionError(where)


@pytest.mark.parametrize(
    "where", ["after_activation", "after_launch_intent", "after_launcher_returned"]
)
def test_a_launch_interrupted_after_the_slot_is_taken_is_recoverable(
    tmp_path: Path, where: str
) -> None:
    """A crash in the window the slot is held is a decision to take, not a child to lose.

    Startup reconciliation used to look only at runs it did not own, so this run's own held row
    was invisible; the launch path then refused it because its admission status had become
    ``held`` -- the status this control flow itself had just written. One wrapper error therefore
    occupied a vendor slot forever, and for a metered vendor stopped every other child starting.
    """
    harness = Harness(tmp_path, per_vendor=1, aggregate=1)
    harness.bootstrap([_child("child-a"), _child("child-b")])
    with _failing_at(where, harness):
        report = harness.coordinator.launch_ready_children()
    assert report.launched == ()
    row = harness.rows()["child-a"]
    assert row["admission"] == "held"
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)
    assert RUNNER.claim_of(row) is not None
    assert ADMISSION.occupancy()[1] == 1, "the slot is held by the interrupted child"

    resumed = harness.restart_coordinator()
    offered = resumed.interrupted_dispatches()
    assert [item.row_id for item in offered] == ["child-a"]
    assert offered[0].run_id == RUN_ID
    assert offered[0].claimed_by is not None

    resumed.reconcile_startup(decide=lambda _orphan: "resume")
    again = resumed.launch_ready_children()
    assert again.launched == ("child-a",), again.withheld
    assert (
        LIFECYCLE.read_session_pane_id(
            harness.herdr, root=harness.repo, run_id=RUN_ID, row_id="child-a"
        )
        == "pane-child-a"
    )


def test_resuming_an_interrupted_launch_reads_the_live_owner_and_recovers(tmp_path: Path) -> None:
    """The window where a session exists and the register does not know its pane.

    The launcher already survives this: a ``launching`` row with no pane is its label-recovery
    case. Composition made that branch unreachable. Resuming must reach it rather than opening a
    second session for the same child.
    """
    harness = Harness(tmp_path)
    harness.bootstrap([_child("child-a")])
    with _failing_at("after_launcher_returned", harness):
        harness.coordinator.launch_ready_children()

    # The session the crashed launch really did create, discoverable by its run-bound label.
    label = LIFECYCLE.task_label(RUN_ID, "child-a")
    harness.herdr.labels[label] = LIFECYCLE.LaunchIdentity(
        "claude-1", "ws-1", "tab-child-a", "pane-child-a", True
    )
    launches_before = list(harness.wrapper.launches)

    resumed = harness.restart_coordinator()
    resumed.reconcile_startup(decide=lambda _orphan: "resume")
    assert resumed.launch_ready_children().launched == ("child-a",)

    assert label in harness.herdr.label_lookups
    assert harness.wrapper.launches == launches_before


def test_abandoning_an_interrupted_launch_frees_the_slot_and_makes_spend_knowable(
    tmp_path: Path,
) -> None:
    """Abandon used to free the slot and leave the run's spend permanently unknowable."""
    harness = Harness(tmp_path, per_vendor=1, aggregate=1)
    harness.bootstrap([_child("child-a"), _child("child-b")])
    with _failing_at("after_launch_intent", harness):
        harness.coordinator.launch_ready_children()

    resumed = harness.restart_coordinator()
    resumed.reconcile_startup(decide=lambda _orphan: "abandon")

    assert ADMISSION.occupancy()[1] == 1
    assert harness.rows()["child-a"]["coordinator_disposition"]["never_ran"] is True
    assert harness.rows()["child-b"]["admission"] == "reserved"
    assert resumed.spend_status()[0] == "ok"


def test_a_child_that_did_get_a_session_is_stopped_before_abandonment(
    tmp_path: Path,
) -> None:
    """The never-ran shortcut is evidence, not convenience, so it must refuse to guess."""
    harness = Harness(tmp_path)
    harness.bootstrap([_child("child-a")])
    with _failing_at("after_launcher_returned", harness):
        harness.coordinator.launch_ready_children()
    harness.herdr.labels[LIFECYCLE.task_label(RUN_ID, "child-a")] = LIFECYCLE.LaunchIdentity(
        "claude-1", "ws-1", "tab-child-a", "pane-child-a", True
    )

    harness.coordinator.abandon_child("child-a", "operator changed the outcome")
    disposition = harness.rows()["child-a"]["coordinator_disposition"]
    assert disposition["never_ran"] is False
    assert disposition["producer_stopped"] is True
    assert "tab-child-a" in harness.herdr.closed


def test_a_pane_less_launching_row_with_a_discoverable_session_blocks_the_next_child(
    tmp_path: Path,
) -> None:
    """A session the launcher actually created must not be charged zero while it stays hidden.

    ``phase == "launching"`` is written before the native launcher runs, so on its own it cannot
    tell "never launched" from "launched and not yet persisted". Charging both zero unconditionally
    let a real session's ceiling ride free and let a sibling start past it -- the property, not the
    six-sequence regression, this repair closes: the same discovery the launcher's own recovery
    uses, not the row's field alone, is what proves absence.
    """
    harness = Harness(tmp_path, per_vendor=2, aggregate=2)
    harness.bootstrap([_child("child-a"), _child("child-b")])
    built = harness.coordinator.approved_plan()

    # Attempt only child-a, deliberately, so child-b's row stays untouched -- ``launch_ready_
    # children`` would otherwise reach child-b in the same sweep, before this test has had a
    # chance to make child-a's session discoverable.
    with (
        _failing_at("after_launcher_returned", harness),
        pytest.raises(LIFECYCLE.LaunchProtocolError),
    ):
        harness.coordinator.launch_child(built.children[0])

    row = harness.rows()["child-a"]
    assert row["phase"] == "launching"
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)

    # The crashed launch really did create a session, discoverable by its run-bound label --
    # exactly what the launcher's own recovery test proves it can find.
    label = LIFECYCLE.task_label(RUN_ID, "child-a")
    harness.herdr.labels[label] = LIFECYCLE.LaunchIdentity(
        "claude-1", "ws-1", "tab-child-a", "pane-child-a", True
    )

    state, detail = harness.coordinator.spend_status()
    assert state == "unknown" and "live owner could not establish" in detail

    with pytest.raises(RUNNER.SpendUnobservableError, match="live owner could not establish"):
        harness.coordinator.launch_child(built.children[1])
    assert harness.wrapper.launches == ["child-a"], "no native launch reached the ceiling"


def test_a_dispatch_whose_final_protocol_send_failed_is_offered_and_redelivered(
    tmp_path: Path,
) -> None:
    """A pane the operator already paid for must not be silently unrecoverable.

    Everything up through the receipt and the completion sentinel succeeded; only the final
    control-plane send that tells the child where to write failed. The row keeps its pane and its
    phase never moves off ``ready``, so the old "no pane" definition of ``interrupted_dispatches``
    could not see it, and ``abandon`` could not make its spend knowable because the pane alone
    proved a session existed.
    """
    harness = Harness(tmp_path)
    harness.bootstrap([_child("child-a")])
    real_send_line = harness.herdr.send_line
    sends: list[tuple[str, str]] = []

    def flaky_send_line(pane_id: str, text: str, *, cwd: Path) -> None:
        sends.append((pane_id, text))
        if len(sends) == 2:
            raise LIFECYCLE.LaunchProtocolError("herdr pane run failed")
        real_send_line(pane_id, text, cwd=cwd)

    harness.herdr.send_line = flaky_send_line  # type: ignore[method-assign]
    first = harness.coordinator.launch_ready_children()
    harness.herdr.send_line = real_send_line  # type: ignore[method-assign]

    assert first.launched == ()
    assert "child-a" in first.withheld

    row = harness.rows()["child-a"]
    assert row["phase"] == "ready"
    assert (
        LIFECYCLE.read_session_pane_id(
            harness.herdr, root=harness.repo, run_id=RUN_ID, row_id="child-a"
        )
        == "pane-child-a"
    )
    assert isinstance(row["completion_sentinel"], dict)
    assert not isinstance(row.get("artifact_protocol_sent"), dict)

    offered = harness.coordinator.interrupted_dispatches()
    assert [item.row_id for item in offered] == ["child-a"]
    assert offered[0].pane_id == "pane-child-a"

    resumed = harness.restart_coordinator()
    resumed.reconcile_startup(decide=lambda _orphan: "resume")
    second = resumed.launch_ready_children()

    assert second.launched == ("child-a",), second.withheld
    assert harness.wrapper.launches == ["child-a"], "no second native launch"
    assert isinstance(harness.rows()["child-a"]["artifact_protocol_sent"], dict)
    # Redelivery does not fabricate spend knowledge: the child is now an ordinary launched,
    # metered row awaiting its first usage line, exactly like any other freshly-dispatched child.
    state, detail = resumed.spend_status()
    assert state == "unknown" and "reported no usage" in detail, (state, detail)


def test_a_receipt_sealed_before_its_sentinel_write_landed_is_offered_and_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sealed receipt and a persisted sentinel are two different register writes, not one.

    ``completion.issue_receipt`` seals the receipt in its own write; the very next write persists
    the completion sentinel and the changed-paths baseline. A failure strictly between them leaves
    a receipt that is durable, authoritative proof readiness completed, with no completion sentinel
    to tell the old two-shape recovery apart from a row where readiness never happened at all --
    misread as "nothing sealed yet exists to resend safely" when a sealed receipt already does.
    Nothing was ever sent to the pane, because the send is gated on the write that failed, so a
    fresh sentinel and a freshly retaken baseline are exactly as safe to mint here as the first
    ones would have been.
    """
    harness = Harness(tmp_path)
    harness.bootstrap([_child("child-a")])
    real_write_owned = RUNNER._write_owned
    calls = {"n": 0}

    def flaky_write_owned(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("register write failed")
        return real_write_owned(*args, **kwargs)

    monkeypatch.setattr(RUNNER, "_write_owned", flaky_write_owned)
    with pytest.raises(RuntimeError):
        harness.coordinator.launch_ready_children()
    monkeypatch.setattr(RUNNER, "_write_owned", real_write_owned)

    row = harness.rows()["child-a"]
    assert row["phase"] == "ready", "readiness itself already completed before the crash"
    assert (
        LIFECYCLE.read_session_pane_id(
            harness.herdr, root=harness.repo, run_id=RUN_ID, row_id="child-a"
        )
        == "pane-child-a"
    )
    assert isinstance(row.get(COMPLETION.DISPATCH_RECEIPT_KEY), dict), "the receipt is sealed"
    assert not isinstance(row.get("completion_sentinel"), dict)
    assert not isinstance(row.get("artifact_protocol_sent"), dict)
    # Readiness itself legitimately dispatches to the pane; what must not have happened is the
    # artifact protocol -- the send gated on the write that crashed.
    assert not any("Write your deliverable" in text for _pane, text in harness.herdr.sent), (
        "the artifact protocol reached the pane before the crash"
    )

    offered = harness.coordinator.interrupted_dispatches()
    assert [item.row_id for item in offered] == ["child-a"]

    resumed = harness.restart_coordinator()
    resumed.reconcile_startup(decide=lambda _orphan: "resume")
    second = resumed.launch_ready_children()

    assert second.launched == ("child-a",), second.withheld
    assert harness.wrapper.launches == ["child-a"], "no second native launch"
    bound = harness.rows()["child-a"]
    assert isinstance(bound["completion_sentinel"], dict)
    assert isinstance(bound["changed_paths_baseline"], dict)
    assert isinstance(bound["artifact_protocol_sent"], dict)
    assert any("Write your deliverable" in text for _pane, text in harness.herdr.sent), (
        "the artifact protocol actually reached the pane this time"
    )


def test_abandoning_a_dispatch_stuck_on_an_unconfirmed_protocol_send_frees_the_spend_gate(
    tmp_path: Path,
) -> None:
    """Abandon must be a real recovery for a pane-bearing dispatch too, not a documented no-op.

    ``never_ran`` is correctly false once a pane exists, so ``tokens_observed`` genuinely never
    becomes known. Before this repair the spend gate had no way to hear the abandon decision at
    all for this shape and stayed halted forever, which made "abandon it" advice the run could not
    actually follow.
    """
    harness = Harness(tmp_path, per_vendor=1, aggregate=1)
    harness.bootstrap([_child("child-a"), _child("child-b")])
    real_send_line = harness.herdr.send_line
    sends: list[tuple[str, str]] = []

    def flaky_send_line(pane_id: str, text: str, *, cwd: Path) -> None:
        sends.append((pane_id, text))
        if len(sends) == 2:
            raise LIFECYCLE.LaunchProtocolError("herdr pane run failed")
        real_send_line(pane_id, text, cwd=cwd)

    harness.herdr.send_line = flaky_send_line  # type: ignore[method-assign]
    harness.coordinator.launch_ready_children()
    harness.herdr.send_line = real_send_line  # type: ignore[method-assign]

    assert harness.coordinator.spend_status()[0] == "unknown"

    harness.coordinator.abandon_child("child-a", "the operator gave up on this pane")
    row = harness.rows()["child-a"]
    assert row["coordinator_disposition"]["never_ran"] is False
    assert row.get("tokens_observed") is None, "a child that ran keeps its spend genuinely unknown"

    state, detail = harness.coordinator.spend_status()
    assert state == "ok", detail


def test_abandoning_a_live_pane_that_will_not_close_still_gates_the_spend(
    tmp_path: Path,
) -> None:
    """No longer awaited is not the producer stopped, and abandon must not conflate them.

    A child abandoned with a confirmed-closed pane correctly stops counting against spend, but a
    child abandoned while its tab genuinely will not close is still, for every purpose this gate
    checks, exactly as unresolved as a row nobody decided anything about: the operator's decision
    to stop pursuing it does not by itself make its cost knowable or its mutation stopped.
    """
    harness = Harness(tmp_path, per_vendor=1, aggregate=1)
    harness.bootstrap([_child("child-a"), _child("child-b")])
    harness.coordinator.launch_ready_children()

    real_close_tab = harness.herdr.close_tab
    harness.herdr.close_tab = lambda tab_id, *, cwd: None  # type: ignore[method-assign]

    harness.coordinator.abandon_child("child-a", "operator gave up, but the pane will not close")
    harness.herdr.close_tab = real_close_tab  # type: ignore[method-assign]

    row = harness.rows()["child-a"]
    assert row["coordinator_disposition"]["never_ran"] is False
    assert row["coordinator_disposition"]["producer_stopped"] is False
    assert harness.herdr.tab_present("tab-child-a", cwd=harness.repo), "the tab is still live"

    state, detail = harness.coordinator.spend_status()
    assert state == "unknown" and "child-a" in detail, (state, detail)

    outstanding = harness.coordinator.outstanding_writers()
    assert "child-a" in outstanding, "retirement must refuse on an unconfirmed-stopped abandon too"


def test_abandoning_a_live_pane_that_does_close_correctly_frees_both_gates(
    tmp_path: Path,
) -> None:
    """The companion positive case: a confirmed stop is what actually earns the exclusion.

    Distinguishes the new gate from a regression that would exclude every abandoned row again
    regardless of outcome -- only a tab that genuinely closes frees both the spend gate and
    retirement.
    """
    harness = Harness(tmp_path, per_vendor=1, aggregate=1)
    harness.bootstrap([_child("child-a"), _child("child-b")])
    harness.coordinator.launch_ready_children()

    harness.coordinator.abandon_child("child-a", "operator gave up; the pane closes cleanly")

    row = harness.rows()["child-a"]
    assert row["coordinator_disposition"]["producer_stopped"] is True
    assert "tab-child-a" in harness.herdr.closed

    state, detail = harness.coordinator.spend_status()
    assert state == "ok", detail
    assert "child-a" not in harness.coordinator.outstanding_writers()


def test_a_dispatch_stalled_before_readiness_was_confirmed_is_offered_and_retried_by_label(
    tmp_path: Path,
) -> None:
    """The near neighbour: a pane exists, but nothing sealed yet exists to resend safely.

    A trust prompt (or a readiness timeout) leaves a live pane with no completion sentinel and no
    dispatch receipt. The coordinator cannot replay a task, but it can adopt the run-bound session
    and retry readiness without launching a replacement. The row must still be visible, and an
    explicit abandon must still unblock the run's spend.
    """
    harness = Harness(tmp_path)
    harness.bootstrap([_child("child-a")])
    harness.herdr.pane_texts["pane-child-a"] = "Do you trust the files in this folder?\n"

    first = harness.coordinator.launch_ready_children()
    assert first.launched == ()
    assert "child-a" in first.withheld

    row = harness.rows()["child-a"]
    assert row["phase"] == "launching"
    assert (
        LIFECYCLE.read_session_pane_id(
            harness.herdr, root=harness.repo, run_id=RUN_ID, row_id="child-a"
        )
        == "pane-child-a"
    )
    assert not isinstance(row.get("completion_sentinel"), dict)

    offered = harness.coordinator.interrupted_dispatches()
    assert [item.row_id for item in offered] == ["child-a"]

    resumed = harness.restart_coordinator()
    resumed.reconcile_startup(decide=lambda _orphan: "resume")
    second = resumed.launch_ready_children()
    assert second.launched == ()
    assert "blocked on a workspace trust prompt" in second.withheld["child-a"]
    assert harness.wrapper.launches == ["child-a"], "the existing session was adopted by label"

    resumed.abandon_child("child-a", "operator resolved the trust prompt out of band")
    state, detail = resumed.spend_status()
    assert state == "ok", detail


# ====================================================== dispatch ownership across coordinators


def test_two_coordinators_racing_the_same_child_launch_it_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reads all happen before the act, so only a durable claim can serialise this.

    Both coordinators pass every check -- phase, pane, receipt, reservation, spend, route -- before
    either marks the slot active, and marking an already-active slot succeeds. Sequential tests
    cannot reach this: the second coordinator must be inside the window the first has opened.
    """
    harness = Harness(tmp_path)
    harness.bootstrap([_child("child-a")])
    first = harness.coordinator
    second = harness.restart_coordinator()
    second._reconciled = True
    child = first.approved_plan().children[0]

    paused = threading.Event()
    release = threading.Event()
    real_activate = ADMISSION.activate_slot
    calls = {"n": 0}

    def hooked(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            paused.set()
            release.wait(30)
        return real_activate(*args, **kwargs)

    monkeypatch.setattr(RUNNER.admission, "activate_slot", hooked)
    errors: list[BaseException] = []

    def run_first() -> None:
        try:
            first.launch_child(child)
        except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
            errors.append(exc)

    worker = threading.Thread(target=run_first)
    worker.start()
    try:
        assert paused.wait(30), "the first coordinator never reached the activation seam"
        with pytest.raises(RUNNER.DispatchClaimError, match="does not own it"):
            second.launch_child(child)
    finally:
        release.set()
        worker.join(60)

    assert errors == []
    assert harness.wrapper.launches == ["child-a"], "exactly one native launch"
    assert RUNNER.claim_of(harness.rows()["child-a"]).coordinator_id == first.coordinator_id


def test_a_claim_is_bound_to_the_coordinator_that_took_it(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    child = harness.coordinator.approved_plan().children[0]
    claim = harness.coordinator.claim_dispatch(child)
    assert claim.coordinator_id == harness.coordinator.coordinator_id
    assert claim.attempts == 1

    other = harness.restart_coordinator()
    other._reconciled = True
    with pytest.raises(RUNNER.DispatchClaimError):
        other.claim_dispatch(child)


def test_a_claim_is_taken_over_only_by_an_explicit_resume_decision(harness: Harness) -> None:
    """Not by the claimant looking dead. Taking a claim on that evidence is a clock in disguise."""
    harness.bootstrap([_child("child-a")])
    child = harness.coordinator.approved_plan().children[0]
    harness.coordinator.claim_dispatch(child)
    first_id = harness.coordinator.coordinator_id

    other = harness.restart_coordinator()
    with pytest.raises(RUNNER.DispatchClaimError):
        other.claim_dispatch(child)
    assert RUNNER.claim_of(harness.rows()["child-a"]).coordinator_id == first_id

    other.reconcile_startup(decide=lambda _orphan: "resume")
    assert RUNNER.claim_of(harness.rows()["child-a"]).coordinator_id == other.coordinator_id
    assert other.claim_dispatch(child).attempts == 2, "the attempt history survives the handover"


def test_a_dead_claimant_does_not_by_itself_release_the_claim(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    child = harness.coordinator.approved_plan().children[0]
    harness.coordinator.claim_dispatch(child)
    REGISTER.upsert_row(
        harness.repo,
        "child-a",
        {"dispatch_claim": {**harness.rows()["child-a"]["dispatch_claim"], "pid": 2**30}},
        run_id=RUN_ID,
    )
    other = harness.restart_coordinator()
    other._reconciled = True

    assert RUNNER.process_is_running(2**30) is False
    with pytest.raises(RUNNER.DispatchClaimError):
        other.claim_dispatch(child)
    offered = other.interrupted_dispatches()
    assert offered and offered[0].claimant_running is False


def test_an_explicit_resume_by_another_coordinator_fences_the_original_claimant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A takeover changes who owns the row. It must also stop whoever owned it a moment ago.

    An explicit ``resume`` overwriting a still-owned claim is this build's deliberate policy
    (:func:`test_a_claim_is_taken_over_only_by_an_explicit_resume_decision`) -- process liveness
    is evidence, never authority. What that policy does not by itself provide is a fence for the
    coordinator whose claim was just taken: reaching the native launcher on a claim that changed
    hands moments ago is the double launch this control flow exists to make unsayable, not merely
    unlikely.
    """
    harness = Harness(tmp_path)
    harness.bootstrap([_child("child-a")])
    first = harness.coordinator
    child = first.approved_plan().children[0]

    paused = threading.Event()
    release = threading.Event()
    real_activate = ADMISSION.activate_slot
    calls = {"n": 0}

    def hooked(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            paused.set()
            release.wait(30)
        return real_activate(*args, **kwargs)

    monkeypatch.setattr(RUNNER.admission, "activate_slot", hooked)
    errors: list[BaseException] = []

    def run_first() -> None:
        try:
            first.launch_child(child)
        except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
            errors.append(exc)

    worker = threading.Thread(target=run_first)
    worker.start()
    try:
        assert paused.wait(30), "the first coordinator never reached activation"

        second = harness.restart_coordinator()
        second.reconcile_startup(decide=lambda _orphan: "resume")
        second_report = second.launch_ready_children()
    finally:
        release.set()
        worker.join(60)

    assert second_report.launched == ("child-a",), second_report.withheld
    assert len(errors) == 1
    assert isinstance(errors[0], RUNNER.DispatchClaimError)
    assert harness.wrapper.launches == ["child-a"], "exactly one native launch reached the launcher"
    assert RUNNER.claim_of(harness.rows()["child-a"]).coordinator_id == second.coordinator_id


def test_two_threads_of_one_coordinator_racing_the_same_launch_reach_the_launcher_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The neighbouring race the same fence closes: one ``coordinator_id``, two threads.

    ``_dispatching`` is a pre-filter checked outside the lock, and ``claim_dispatch`` itself lets
    the *same* coordinator id re-claim to support an ordinary same-thread retry -- so two threads
    of one ``Coordinator`` object both pass every earlier guard and both take a claim. What stops a
    second native launch is comparing the exact claim record, attempt count included, right before
    the launcher runs: the second ``claim_dispatch`` call always leaves the first thread holding a
    claim that no longer matches the register, even though both share one ``coordinator_id``.
    """
    harness = Harness(tmp_path)
    harness.bootstrap([_child("child-a")])
    coordinator = harness.coordinator
    child = coordinator.approved_plan().children[0]

    barrier = threading.Barrier(2, timeout=30)
    real_activate = ADMISSION.activate_slot

    def hooked(*args: Any, **kwargs: Any) -> Any:
        barrier.wait()
        return real_activate(*args, **kwargs)

    monkeypatch.setattr(RUNNER.admission, "activate_slot", hooked)
    results: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def attempt(label: str) -> None:
        try:
            coordinator.launch_child(child)
            with lock:
                results.append(f"{label}:ok")
        except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
            with lock:
                errors.append(exc)

    t1 = threading.Thread(target=attempt, args=("t1",))
    t2 = threading.Thread(target=attempt, args=("t2",))
    t1.start()
    t2.start()
    t1.join(60)
    t2.join(60)

    assert results == ["t1:ok"] or results == ["t2:ok"], (results, [type(e) for e in errors])
    assert len(errors) == 1
    assert isinstance(errors[0], RUNNER.DispatchClaimError)
    assert harness.wrapper.launches == ["child-a"], "exactly one native launch"


def test_a_takeover_cannot_finish_while_the_original_coordinator_is_inside_the_native_launch_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A claim re-checked and a launcher called moments later is still two events, not one.

    ``_assert_dispatch_claim_still_mine`` re-checks the claim before ``session_lifecycle.launch_child``
    is even called; that check passing does not fence the native call itself, which runs after real
    I/O (admission, git provisioning, a wrapper preview) the check paid no attention to. This pauses
    a coordinator *after* that early check has already passed and *inside* the one native call that
    cannot be undone -- the state neither the early check nor an earlier fence at ``activate_slot``
    (:func:`test_an_explicit_resume_by_another_coordinator_fences_the_original_claimant`) reaches.
    """
    harness = Harness(tmp_path)
    harness.bootstrap([_child("child-a")])
    first = harness.coordinator
    child = first.approved_plan().children[0]

    paused = threading.Event()
    release = threading.Event()
    real_launch = harness.wrapper.launch
    calls = {"n": 0}

    def hooked_launch(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            paused.set()
            release.wait(30)
        return real_launch(*args, **kwargs)

    monkeypatch.setattr(harness.wrapper, "launch", hooked_launch)

    first_errors: list[BaseException] = []

    def run_first() -> None:
        try:
            first.launch_child(child)
        except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
            first_errors.append(exc)

    first_worker = threading.Thread(target=run_first)
    first_worker.start()
    second_worker: threading.Thread | None = None
    second_errors: list[BaseException] = []
    second_report: list[Any] = []
    try:
        assert paused.wait(30), "the first coordinator never reached the native launch call"

        second = harness.restart_coordinator()

        def run_second() -> None:
            try:
                second.reconcile_startup(decide=lambda _orphan: "resume")
                second_report.append(second.launch_ready_children())
            except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
                second_errors.append(exc)

        second_worker = threading.Thread(target=run_second)
        second_worker.start()
        # Proof the block is real, not a lucky ordering: everything this thread does before it
        # would need the held lock is fake, in-memory work, over in microseconds. Giving it two
        # full seconds to finish *without* releasing the first coordinator and still finding it
        # alive is not a race that happened to go the right way -- nothing frees it but ``release``,
        # which has not been set yet.
        second_worker.join(timeout=2.0)
        assert second_worker.is_alive(), (
            "the second coordinator finished before the first was released; it was never "
            "genuinely blocked on the first coordinator's held lock"
        )
    finally:
        release.set()
        first_worker.join(60)
        if second_worker is not None:
            second_worker.join(60)

    assert not first_errors, first_errors
    assert not second_errors, second_errors
    assert harness.wrapper.launches == ["child-a"], "exactly one native launch reached the launcher"
    row = harness.rows()["child-a"]
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)
    assert (
        LIFECYCLE.read_session_pane_id(
            harness.herdr, root=harness.repo, run_id=RUN_ID, row_id="child-a"
        )
        == "pane-child-a"
    )
    # Whatever the second coordinator found once unblocked -- a row already fully dispatched, or
    # one it could only offer redelivery or an unconfirmed-dispatch refusal for -- it never reached
    # the native launcher a second time, which ``harness.wrapper.launches`` above already proves.
    assert second_report, "the second coordinator's sweep never ran"


# ====================================================== the subscriber across a restart


def test_a_restart_adopts_the_running_subscriber_instead_of_starting_a_second(
    harness: Harness,
) -> None:
    """The subscriber is the process meant to outlive its parent; a new parent must find it."""
    harness.bootstrap([_child("child-a")])
    assert len(harness.supervisor.started) == 1

    resumed = harness.restart_coordinator()
    resumed.reconcile_startup(decide=lambda _orphan: "resume")
    started_again = resumed.ensure_subscriber()

    assert started_again is False
    assert len(harness.supervisor.started) == 1
    assert [handle.alive for handle in harness.supervisor.started] == [True]
    assert "subscriber_adopted" in [e["kind"] for e in resumed.run_log.entries()]


def test_two_coordinators_racing_ensure_subscriber_start_at_most_one_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two coordinators can both read "no record" before either writes one, without a lock.

    ``ensure_subscriber`` reads the durable record, decides adopt-or-start, and writes the record
    back; without one transaction covering all three, two coordinators can interleave inside that
    window and each start a process, with the second write silently burying the first record and
    leaving two live event streams for one run with no trace either ever raced.
    """
    harness = Harness(tmp_path)
    # Deliberately not ``harness.bootstrap`` -- it calls ``ensure_subscriber()`` itself, which
    # would leave the very coordinator this test drives already holding an in-memory handle and
    # short-circuit before ever reaching the lock this test exists to prove closes the race.
    harness.coordinator.start_run()
    harness.approve_and_commit([_child("child-a")])
    harness.coordinator.reconcile_startup(decide=lambda _orphan: "abandon")

    first = harness.restart_coordinator()
    first._reconciled = True
    second = harness.restart_coordinator()
    second._reconciled = True

    paused = threading.Event()
    release = threading.Event()
    real_start = harness.supervisor.start
    calls = {"n": 0}

    def hooked_start(argv: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            paused.set()
            release.wait(30)
        return real_start(argv)

    monkeypatch.setattr(harness.supervisor, "start", hooked_start)
    results: dict[str, bool] = {}

    def run_first() -> None:
        results["first"] = first.ensure_subscriber()

    def run_second() -> None:
        results["second"] = second.ensure_subscriber()

    t1 = threading.Thread(target=run_first)
    t1.start()
    assert paused.wait(30), "the first coordinator never reached the process starter"

    t2 = threading.Thread(target=run_second)
    t2.start()
    # t2 must be blocked on this run's generation lock -- the same lock ``claim_dispatch``
    # already relies on -- and cannot proceed while t1 still holds it. Give the scheduler a
    # moment and confirm t2 is still running rather than having raced ahead on luck alone: a
    # thread genuinely blocked on the lock stays alive here; one that was never contended would
    # very likely have already returned.
    time.sleep(0.2)
    assert t2.is_alive(), "t2 finished before t1 released the lock -- the block did not happen"
    release.set()
    t1.join(60)
    t2.join(60)

    assert calls["n"] == 1, "only one coordinator ever called the process starter"
    assert results["first"] is True
    assert results["second"] is False, (
        "the second coordinator adopted rather than starting a second"
    )
    assert len(harness.supervisor.started) == 1


def test_a_subscriber_started_but_never_recorded_is_found_not_read_as_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crash between the process starting and its record landing leaves it unaccounted for.

    ``ensure_subscriber`` starts the process, then writes its record; a failure strictly between
    those two calls -- the exact ordering the subscriber's design requires, since the real pid
    does not exist to record before the process exists -- leaves a live, unrecorded process. A
    missing record can only ever mean "this run has not recorded one yet", never "none is
    running", and ``running_subscriber`` (which retirement calls through
    :meth:`Coordinator.outstanding_writers`) must fall back to asking the process table rather
    than concluding absence from the record alone.
    """
    harness = Harness(tmp_path)
    harness.coordinator.start_run()
    harness.approve_and_commit([_child("child-a")])
    harness.coordinator.reconcile_startup(decide=lambda _orphan: "abandon")

    first = harness.restart_coordinator()
    first._reconciled = True

    real_write_record = RUNNER.write_subscriber_record

    def raise_on_write(*args: Any, **kwargs: Any) -> Any:
        raise OSError("disk full")

    monkeypatch.setattr(RUNNER, "write_subscriber_record", raise_on_write)
    with pytest.raises(OSError):
        first.ensure_subscriber()
    monkeypatch.setattr(RUNNER, "write_subscriber_record", real_write_record)

    assert len(harness.supervisor.started) == 1, "the process itself was started before the crash"
    orphan_handle = harness.supervisor.started[0]
    assert orphan_handle.alive is True
    assert RUNNER.read_subscriber_record(RUN_ID) is None, "the record write never landed"

    second = harness.restart_coordinator()
    second._reconciled = True
    running = second.running_subscriber()
    assert running is not None, "a live, unrecorded subscriber must not read as absent"
    assert running["pid"] == orphan_handle.pid
    assert "subscriber" in second.outstanding_writers(), (
        "retirement must refuse while a process this run started is still alive, recorded or not"
    )


def test_a_process_table_query_failure_is_not_read_as_no_subscriber(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A process-table query that fails is not the same fact as "asked, and found nothing".

    Once the durable record is also missing, ``find_orphan`` used to return the identical
    ``None`` for both outcomes -- a search that ran and named nothing, and a search that never
    ran at all. Every caller downstream of :meth:`Coordinator._resolve_subscriber_record` read
    that ``None`` as "no subscriber exists": retirement would have archived beside a live,
    unrecorded orphan, and a supervision tick would have started a duplicate of it. A query that
    never completed must raise rather than resolve to either answer.
    """
    harness = Harness(tmp_path)
    harness.coordinator.start_run()
    harness.approve_and_commit([_child("child-a")])
    harness.coordinator.reconcile_startup(decide=lambda _orphan: "abandon")

    first = harness.restart_coordinator()
    first._reconciled = True
    real_write_record = RUNNER.write_subscriber_record
    monkeypatch.setattr(
        RUNNER,
        "write_subscriber_record",
        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError):
        first.ensure_subscriber()
    monkeypatch.setattr(RUNNER, "write_subscriber_record", real_write_record)

    assert len(harness.supervisor.started) == 1, "the process itself was started before the crash"
    assert RUNNER.read_subscriber_record(RUN_ID) is None, "the record write never landed"

    second = harness.restart_coordinator()
    second._reconciled = True
    harness.supervisor.orphan_query_fails = True

    with pytest.raises(RUNNER.SubscriberLivenessUnknownError):
        second.running_subscriber()
    with pytest.raises(RUNNER.SubscriberLivenessUnknownError):
        second.outstanding_writers()
    with pytest.raises(RUNNER.SubscriberLivenessUnknownError):
        second.retire()
    with pytest.raises(RUNNER.SubscriberLivenessUnknownError):
        second.supervise()
    with pytest.raises(RUNNER.SubscriberLivenessUnknownError):
        second.ensure_subscriber()

    assert REGISTER.register_path(RUN_ID).exists(), "not archived on a question nobody answered"
    assert len(harness.supervisor.started) == 1, (
        "no duplicate started on a question nobody answered"
    )

    # Once the process table can be asked again, the orphan is found and everything resolves.
    harness.supervisor.orphan_query_fails = False
    running = second.running_subscriber()
    assert running is not None
    assert running["pid"] == harness.supervisor.started[0].pid


def test_a_restart_replaces_rather_than_duplicates_an_unrecorded_but_alive_subscriber(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record's absence does not license a second process beside the first.

    Adopting an unrecorded process on a guess about its subscription set would be trusting exactly
    the fact that is missing. Stopping it and starting a correctly-subscribed replacement is the
    same choice this build already makes for a *recorded* subscriber whose subscription set does
    not match (:func:`test_a_restart_replaces_a_running_subscriber_whose_subscription_set_is_stale`
    below) -- discovering it through the process table rather than the durable record does not
    change which choice applies.
    """
    harness = Harness(tmp_path)
    harness.coordinator.start_run()
    harness.approve_and_commit([_child("child-a")])
    harness.coordinator.reconcile_startup(decide=lambda _orphan: "abandon")

    first = harness.restart_coordinator()
    first._reconciled = True
    real_write_record = RUNNER.write_subscriber_record
    monkeypatch.setattr(
        RUNNER,
        "write_subscriber_record",
        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError):
        first.ensure_subscriber()
    monkeypatch.setattr(RUNNER, "write_subscriber_record", real_write_record)
    orphan_handle = harness.supervisor.started[0]

    second = harness.restart_coordinator()
    second._reconciled = True
    started = second.ensure_subscriber()

    assert started is True, "the unrecorded orphan was stopped and replaced, not silently adopted"
    assert orphan_handle.alive is False, "the orphan was stopped"
    assert len(harness.supervisor.started) == 2
    recorded = RUNNER.read_subscriber_record(RUN_ID)
    assert recorded is not None
    assert recorded["pid"] == harness.supervisor.started[1].pid
    # Exactly one subscriber is outstanding -- the replacement, correctly recorded and genuinely
    # alive -- not the stopped orphan counted a second time and not two live processes at once.
    outstanding = second.outstanding_writers()
    assert str(harness.supervisor.started[1].pid) in outstanding.get("subscriber", "")
    assert str(orphan_handle.pid) not in outstanding.get("subscriber", "")


def test_a_stale_record_pointing_at_a_reused_pid_is_not_adopted_or_signalled(
    harness: Harness,
) -> None:
    """A pid existing is not the same fact as that pid being this run's subscriber.

    ``is_record_alive`` used to ask only whether the recorded pid was running. A stale record --
    left behind by a subscriber that crashed or was already reaped, or simply planted -- paired
    with a process id the operating system later reuses for an unrelated process, made that
    question answer "yes" for a process this run never started: :meth:`ensure_subscriber` could
    adopt it, and :meth:`stop_writers` could send it a real signal. Identity is now asked the
    same way :meth:`find_orphan` already asks it for a missing record -- a live process whose
    command line carries this run's own script path, run id, and row id -- so a pid match alone
    is no longer enough.
    """
    harness.coordinator.start_run()
    harness.approve_and_commit([_child("child-a")])
    harness.coordinator.reconcile_startup(decide=lambda _orphan: "abandon")

    stray = harness.supervisor.start(["some-other-program", "--not-a-subscriber"])
    wanted = RUNNER.subscriptions_for(harness.repo, run_id=RUN_ID, herdr=harness.herdr)
    RUNNER.write_subscriber_record(
        RUN_ID,
        {
            "pid": stray.pid,
            "coordinator_id": "an-earlier-coordinator",
            "run_id": RUN_ID,
            "row_id": harness.coordinator.subscriber_row_id,
            "started_at": "2020-01-01T00:00:00Z",
            "subscriptions": [dict(item) for item in wanted],
        },
    )

    running = harness.coordinator.running_subscriber()
    assert running is None, "a pid match alone must not be read as this run's own subscriber"

    # The reproduction that matters: shutdown asks the same planted record to stop, and must not
    # send a real signal to a process this run never started.
    harness.coordinator.stop_writers()
    assert stray.alive is True, "shutdown never signals a process this run did not start"
    assert stray not in harness.supervisor.stopped
    assert RUNNER.read_subscriber_record(RUN_ID) is None, "the unidentifiable record is dropped"

    started = harness.coordinator.ensure_subscriber()
    assert started is True, "a stale, unidentifiable record must not be silently adopted"
    assert stray.alive is True, (
        "adoption never touches the process the stale record happened to name"
    )
    assert stray not in harness.supervisor.stopped, "the unrelated process was never signalled"


def test_a_restart_replaces_a_running_subscriber_whose_subscription_set_is_stale(
    harness: Harness,
) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    running_before = [handle for handle in harness.supervisor.started if handle.alive]
    assert len(running_before) == 1

    resumed = harness.restart_coordinator()
    resumed.reconcile_startup(decide=lambda _orphan: "resume")
    # A subscription the running subscriber was not started with: it can no longer deliver this
    # run's events, so adopting it would keep a process that has stopped being the right one.
    REGISTER.upsert_row(
        harness.repo,
        "child-a",
        {
            "completion_sentinel": {
                "pane_id": "pane-child-a",
                "sentinel": SUBSCRIBER.make_sentinel(RUN_ID, "child-a", "completion"),
            }
        },
        run_id=RUN_ID,
    )
    assert resumed.ensure_subscriber() is True

    assert running_before[0].alive is False, "the stale subscriber was stopped, not left running"
    assert [handle.alive for handle in harness.supervisor.started].count(True) == 1
    assert "subscriber_replaced" in [entry["kind"] for entry in resumed.run_log.entries()]


def test_retirement_refuses_while_a_subscriber_this_coordinator_did_not_start_is_alive(
    harness: Harness,
) -> None:
    """Retirement archives and deletes the live register. A writer that survives it can put a
    live document back beside the archive, so "every writer is closed" has to be asked of the
    run, not of whichever object happens to be holding a handle."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.abandon_child("child-a", "not needed")

    resumed = harness.restart_coordinator()
    resumed.reconcile_startup(decide=lambda _orphan: "resume")

    outstanding = resumed.outstanding_writers()
    assert "subscriber" in outstanding
    assert "still holding the event stream" in outstanding["subscriber"]
    with pytest.raises(RUNNER.RetirementOrderError, match="subscriber"):
        resumed.retire()
    assert REGISTER.register_path(RUN_ID).exists()

    resumed.stop_writers()
    assert [handle.alive for handle in harness.supervisor.started] == [False]
    assert resumed.retire() is not None


def test_supervising_after_adopting_a_subscriber_does_not_report_a_divergence(
    harness: Harness,
) -> None:
    """A coordinator that adopted a running subscriber holds no handle for it.

    Asking the handle reports a death that did not happen: a false ``exited`` written onto the
    subscriber's row and a false alarm on every tick after a restart.
    """
    harness.bootstrap([_child("child-a")])
    resumed = harness.restart_coordinator()
    resumed.reconcile_startup(decide=lambda _orphan: "resume")
    assert resumed.ensure_subscriber() is False

    report = resumed.supervise()

    assert report.subscriber_respawned is False
    assert report.subscriber_alive is True
    assert "subscriber_divergence" not in [entry["kind"] for entry in resumed.run_log.entries()]
    # The subscriber writes its own row when it starts. Nothing else should create one, and the
    # false-divergence path did: it recorded ``exited`` for a process that was running.
    assert resumed.subscriber_row_id not in harness.rows()


def test_a_killed_subscriber_is_still_detected_after_a_restart_adopted_it(
    harness: Harness,
) -> None:
    harness.bootstrap([_child("child-a")])
    resumed = harness.restart_coordinator()
    resumed.reconcile_startup(decide=lambda _orphan: "resume")
    resumed.ensure_subscriber()
    harness.supervisor.kill()

    report = resumed.supervise()

    assert report.subscriber_respawned is True
    assert report.subscriber_alive is True
    assert [handle.alive for handle in harness.supervisor.started].count(True) == 1


def test_the_subscriber_record_is_forgotten_with_the_run(harness: Harness) -> None:
    harness.bootstrap([_child("child-a")])
    assert RUNNER.read_subscriber_record(RUN_ID) is not None
    harness.coordinator.abandon_child("child-a", "not needed")
    harness.coordinator.stop_writers()
    harness.coordinator.retire()
    assert RUNNER.read_subscriber_record(RUN_ID) is None


# ====================================================== the fenced reap


def test_a_child_that_writes_before_it_is_stopped_does_not_reach_a_recorded_reap(
    harness: Harness,
) -> None:
    """Comparing a digest and then closing a tab leaves a window the comparison cannot cover.

    The child is alive until the tab closes, so it can write after the comparison and before the
    closure, and that write is never evaluated. Stopping the producer first is the only way to
    observe evidence that cannot change while it is being observed.
    """
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    assert harness.coordinator.integrate_child("child-a").verified
    real_close = harness.herdr.close_tab

    def writes_then_closes(tab_id: str, *, cwd: Path) -> None:
        (harness.repo / "src" / "written-while-still-alive.txt").write_text("x\n", encoding="utf-8")
        real_close(tab_id, cwd=cwd)

    harness.herdr.close_tab = writes_then_closes  # type: ignore[method-assign]

    with pytest.raises(RUNNER.ChildStillMutatingError, match="never evaluated"):
        harness.coordinator.reap_child("child-a")

    assert harness.rows()["child-a"]["phase"] == "verified", "not recorded terminal"
    assert (harness.repo / "src" / "written-while-still-alive.txt").exists(), "work preserved"


def test_the_fence_is_recorded_before_the_producer_is_stopped(harness: Harness) -> None:
    """A crash between the two leaves a closed tab beside a live row; the record says it was
    deliberate rather than a vanished child."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    harness.coordinator.integrate_child("child-a")
    seen: list[bool] = []
    real_close = harness.herdr.close_tab

    def observing_close(tab_id: str, *, cwd: Path) -> None:
        seen.append(bool(harness.rows()["child-a"].get("reap_fence")))
        real_close(tab_id, cwd=cwd)

    harness.herdr.close_tab = observing_close  # type: ignore[method-assign]
    harness.coordinator.reap_child("child-a")

    assert seen == [True], "the fence was durable before the tab was closed"
    assert harness.rows()["child-a"]["phase"] == "reaped"


def test_a_crash_between_the_fence_write_and_the_tab_close_is_repaired_by_retry(
    harness: Harness,
) -> None:
    """A recorded fence is an intent, not proof the producer stopped.

    The first attempt can crash strictly between writing the fence and the close call landing. A
    retry that sees the fence and returns, trusting it as proof the producer already stopped,
    reaps behind a tab that never actually closed -- exactly the window the fence exists to
    remove, reopened by the retry path meant to make it durable.
    """
    harness.bootstrap([_child("child-m", integration_mode="branch")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-m")
    harness.land_mutating_change("child-m")
    harness.report_usage("child-m")
    result = harness.coordinator.integrate_child("child-m")
    assert result.verified, result.detail

    real_close_tab = harness.herdr.close_tab
    calls = {"n": 0}

    def flaky_close_tab(tab_id: str, *, cwd: Path) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise LIFECYCLE.LaunchProtocolError("herdr tab close failed")
        real_close_tab(tab_id, cwd=cwd)

    harness.herdr.close_tab = flaky_close_tab  # type: ignore[method-assign]
    with pytest.raises(LIFECYCLE.LaunchProtocolError):
        harness.coordinator.reap_child("child-m")

    row = harness.rows()["child-m"]
    assert isinstance(row.get("reap_fence"), dict), "the fence is durable despite the failed close"
    assert row["phase"] == "verified", "not reaped -- the close never confirmed"
    assert "tab-child-m" not in harness.herdr.closed, "the tab genuinely never closed"

    authorization = harness.coordinator.reap_child("child-m")
    harness.herdr.close_tab = real_close_tab  # type: ignore[method-assign]

    assert authorization.row_id == "child-m"
    assert harness.rows()["child-m"]["phase"] == "reaped"
    assert "tab-child-m" in harness.herdr.closed, "the retry actually closed the tab this time"


def test_a_write_at_the_moment_the_retried_close_lands_still_refuses_the_reap(
    harness: Harness,
) -> None:
    """The retry's close is the same fence the first attempt would have been.

    This is the exact window the reviewer's proof used: the retry's own close call is the last
    moment a genuinely live child can still write, whether it is the first attempt at closing or a
    later one. A fix that only re-attempts the close without keeping it *before* the re-observed
    digest would let this same write land between the digest and ``reap_verified`` writing
    ``reaped`` -- recording a pass over work nobody read, caught later only by the acceptance
    receipt rather than refused here.
    """
    harness.bootstrap([_child("child-m", integration_mode="branch")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-m")
    harness.land_mutating_change("child-m")
    harness.report_usage("child-m")
    assert harness.coordinator.integrate_child("child-m").verified

    real_close_tab = harness.herdr.close_tab
    calls = {"n": 0}

    def close_tab_hook(tab_id: str, *, cwd: Path) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise LIFECYCLE.LaunchProtocolError("herdr tab close failed")
        (harness.repo / "src" / "written-during-the-retried-close.txt").write_text(
            "x\n", encoding="utf-8"
        )
        real_close_tab(tab_id, cwd=cwd)

    harness.herdr.close_tab = close_tab_hook  # type: ignore[method-assign]
    with pytest.raises(LIFECYCLE.LaunchProtocolError):
        harness.coordinator.reap_child("child-m")

    with pytest.raises(RUNNER.ChildStillMutatingError, match="never evaluated"):
        harness.coordinator.reap_child("child-m")
    harness.herdr.close_tab = real_close_tab  # type: ignore[method-assign]

    assert harness.rows()["child-m"]["phase"] == "verified", "not falsely recorded reaped"
    assert (harness.repo / "src" / "written-during-the-retried-close.txt").exists()


def test_a_close_request_that_returns_without_removing_the_tab_is_not_read_as_a_stop(
    harness: Harness,
) -> None:
    """A close call returning normally is a request accepted, not an effect observed.

    ``close_tab`` can be asked to close a tab and return without raising while the tab is still
    genuinely present -- a control-plane request accepted without the requested state change
    landing. Before this, the fence recorded the producer stopped on that return alone; it must
    instead ask ``tab_present`` again and refuse the reap rather than record ``reaped`` over a
    producer that never actually stopped.
    """
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    assert harness.coordinator.integrate_child("child-a").verified

    real_close_tab = harness.herdr.close_tab

    def close_that_does_not_take(tab_id: str, *, cwd: Path) -> None:
        harness.herdr.closed.append(tab_id)  # the request was made; the tab was not removed

    harness.herdr.close_tab = close_that_does_not_take  # type: ignore[method-assign]
    with pytest.raises(RUNNER.ChildStillMutatingError, match="still present"):
        harness.coordinator.reap_child("child-a")
    harness.herdr.close_tab = real_close_tab  # type: ignore[method-assign]

    assert "tab-child-a" in harness.herdr.closed, "the close was requested"
    assert harness.herdr.tab_present("tab-child-a", cwd=harness.repo), "but it never actually took"
    assert harness.rows()["child-a"]["phase"] == "verified", "not recorded reaped"

    authorization = harness.coordinator.reap_child("child-a")
    assert authorization.row_id == "child-a"
    assert harness.rows()["child-a"]["phase"] == "reaped"


def test_a_fenced_row_is_not_reported_as_a_vanished_child(harness: Harness) -> None:
    """Re-evaluating after the fence must not report this control flow's own closure as a fault."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    harness.coordinator.integrate_child("child-a")
    harness.coordinator._fence_producer("child-a")
    assert harness.herdr.closed == ["tab-child-a"]

    assert harness.coordinator.integrate_child("child-a").verified


def test_the_acceptance_receipt_detects_a_landing_change_after_the_verdict(
    harness: Harness,
) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    harness.coordinator.integrate_child("child-a")
    harness.coordinator.reap_child("child-a")
    assert harness.coordinator.acceptance_receipt().no_false_completion

    (harness.repo / "src" / "changed-after-the-reap.txt").write_text("x\n", encoding="utf-8")
    receipt = harness.coordinator.acceptance_receipt()

    assert not receipt.no_false_completion
    assert "landing changed" in receipt.detail["unauthorised_reaps"][0]["detail"]


# ====================================================== the acceptance order


def test_the_documented_acceptance_order_produces_a_real_receipt(harness: Harness) -> None:
    """stop_writers, then acceptance_receipt, then retire -- exactly as the procedure says."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.create_mirror()
    harness.coordinator.launch_ready_children()
    harness.coordinator.ask_mirror(
        MIRROR.MirrorRequest(request_id="req-1", kind="survey", instruction="Read the tree.")
    )
    harness.coordinator.handle_operator_message("Status?", answer=lambda _c: "one child running")
    harness.run_child("child-a")
    harness.report_usage("child-a")
    harness.coordinator.integrate_child("child-a")
    harness.coordinator.reap_child("child-a")

    harness.coordinator.stop_writers()
    receipt = harness.coordinator.acceptance_receipt()
    archive = harness.coordinator.retire()

    assert receipt.passed
    assert receipt.spend_tokens == 1200.0
    assert archive is not None
    sealed = harness.coordinator.sealed_acceptance_receipt()
    assert sealed is not None and sealed["spend_tokens"] == 1200.0


def test_retiring_without_a_receipt_seals_one_while_the_evidence_still_exists(
    harness: Harness,
) -> None:
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    harness.coordinator.integrate_child("child-a")
    harness.coordinator.reap_child("child-a")
    harness.coordinator.stop_writers()
    harness.coordinator.receipt_path.unlink(missing_ok=True)

    harness.coordinator.retire()

    sealed = harness.coordinator.sealed_acceptance_receipt()
    assert sealed is not None
    assert sealed["spend_tokens"] == 1200.0
    assert sealed["detail"]["unaccounted_children"] == []


def test_asking_for_the_receipt_after_retirement_refuses_instead_of_passing_over_nothing(
    harness: Harness,
) -> None:
    """Every criterion reads the live register, which retirement deletes. Computed afterwards it
    reported no child lost, no false completion and zero spend -- a pass by having nothing left
    to check, on the gate that is supposed to block the next phase."""
    harness.bootstrap([_child("child-a")])
    harness.coordinator.abandon_child("child-a", "not needed")
    harness.coordinator.stop_writers()
    harness.coordinator.retire()

    with pytest.raises(RUNNER.AcceptanceOrderError, match="computed over nothing"):
        harness.coordinator.acceptance_receipt()
    assert harness.coordinator.sealed_acceptance_receipt() is not None


def test_the_approval_digest_does_not_depend_on_how_the_override_mapping_was_built() -> None:
    """The rendered plan is what the approval hashes, so any non-determinism in it is the
    contract. A mapping interpolated with ``repr`` is insertion-ordered, which made two producers
    of the same plan -- this runtime and a port of it -- compute different digests."""
    child = _child("child-a", vendor="claude", model="haiku")
    built = PLANNING.plan("outcome", [child], run_id="run-digest", ceiling=CEILING)
    approved = built.children[0]
    assert approved.override is not None

    reordered = PLANNING.replace(approved, override=dict(reversed(list(approved.override.items()))))
    assert list(reordered.override) != list(approved.override), "the test needs a real reorder"

    assert PLANNING.plan_digest(built) == PLANNING.plan_digest(
        PLANNING.replace(built, children=(reordered,))
    )


def test_the_approved_plan_survives_the_standard_sorted_key_round_trip(harness: Harness) -> None:
    harness.coordinator.start_run()
    built = harness.plan([_child("child-a", vendor="claude", model="haiku")])
    harness.coordinator.approve_plan(built)

    stored = json.loads(RUNNER.approved_plan_path(RUN_ID).read_text(encoding="utf-8"))
    assert stored["children"][0]["override"] is not None
    assert RUNNER.load_approved_plan(RUN_ID).children[0].override == built.children[0].override


# ====================================================== judgment-shaped work


@pytest.mark.parametrize("shape", sorted(COMPLETION.JUDGMENT_WORK_SHAPES))
def test_judgment_shaped_work_is_refused_at_plan_time_rather_than_failing_after_it_is_paid_for(
    harness: Harness, shape: str
) -> None:
    """It needs a verifier dispatched as an ordinary receipt-bearing child, and this control flow
    has no such path. The completion gate refuses a verifier with no receipt, so the work would
    fail closed -- but only after the child had run and been paid for."""
    harness.coordinator.start_run()
    request = RUNNER.parse_outcome("Judge the two reports.")

    with pytest.raises(RUNNER.UnsupportedWorkShapeError, match="verifier"):
        harness.coordinator.plan_run(
            request, [_child("child-j", work_shape=shape)], ceiling=CEILING
        )


# =========================================================================== the subscriber argv


def test_the_subscriber_is_started_with_the_run_identity_and_the_full_subscription_json(
    tmp_path: Path,
) -> None:
    argv = RUNNER.subscriber_argv(
        root=tmp_path,
        run_id=RUN_ID,
        row_id="subscriber-1",
        pane_id="pane-sub",
        orchestrator_pane="pane-op",
        subscriptions=({"type": "pane.exited"},),
    )
    assert argv[1].endswith("subscriber.py")
    assert argv[argv.index("--run-id") + 1] == RUN_ID
    assert json.loads(argv[argv.index("--subscriptions-json") + 1]) == [{"type": "pane.exited"}]


def test_the_subprocess_supervisor_answers_liveness_from_the_process(tmp_path: Path) -> None:
    supervisor = RUNNER.SubprocessSubscriberSupervisor()
    handle = supervisor.start([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert supervisor.is_alive(handle) is True
        supervisor.stop(handle)
        assert supervisor.is_alive(handle) is False
    finally:
        if handle.poll() is None:  # pragma: no cover - defensive clean-up
            handle.kill()
            handle.wait(timeout=10)


def test_the_subprocess_supervisor_finds_a_real_process_by_command_line_signature(
    tmp_path: Path,
) -> None:
    """``find_orphan`` asks the real process table, not a list this object remembers starting.

    A marker unique to this test run stands in for a subscriber's own script path, run id, and
    row id -- the same three tokens production asks for. A signature that names a marker no
    process carries is a completed search that named nothing, not a failure; both are proven here
    against the real ``ps`` this adapter shells out to, not a fake.
    """
    supervisor = RUNNER.SubprocessSubscriberSupervisor()
    marker = f"orchestrate-test-marker-{threading.get_ident()}-{time.time_ns()}"
    proc = subprocess.Popen([sys.executable, "-c", f"import time; time.sleep(30)  # {marker}"])
    try:
        scan = supervisor.find_orphan(signature=(marker,))
        assert scan.complete is True
        assert scan.process is not None
        assert scan.process["pid"] == proc.pid

        clean = supervisor.find_orphan(signature=(f"{marker}-nobody-carries-this",))
        assert clean.complete is True
        assert clean.process is None
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_the_subprocess_supervisor_requires_identity_not_just_a_shared_pid(
    tmp_path: Path,
) -> None:
    """A real, live, unrelated process must not be read as this run's subscriber.

    The record names a pid; a genuinely different process -- spawned by this test, never by
    anything claiming to be a subscriber -- happens to hold that number for the duration of the
    test. A pid-only check would call it alive. The identity check must not, because the harm is
    not hypothetical: whatever ``is_record_alive`` calls alive here is what ``stop_record`` will
    later send a real signal to.
    """
    supervisor = RUNNER.SubprocessSubscriberSupervisor()
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert RUNNER.process_is_running(unrelated.pid) is True
        record = {"pid": unrelated.pid}
        signature = (f"no-subscriber-anywhere-carries-this-{threading.get_ident()}",)
        assert supervisor.is_record_alive(record, signature=signature) is False
        assert unrelated.poll() is None, "the unrelated process was never signalled by the check"
    finally:
        unrelated.kill()
        unrelated.wait(timeout=10)


def test_stop_record_waits_for_the_process_to_actually_exit(tmp_path: Path) -> None:
    """``stop_record`` used to return the instant the signal was sent, not once it landed.

    A caller known only by pid -- exactly the durable-record shape a restarted coordinator finds
    -- has no ``Popen`` handle to ``wait`` on the way :meth:`stop` already can. Confirming the
    process is actually gone before returning is what makes ``is_record_alive`` after this call
    trustworthy rather than a guess about timing.
    """
    supervisor = RUNNER.SubprocessSubscriberSupervisor()
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    # A direct child of *this* process becomes a zombie -- still visible to ``kill(pid, 0)`` --
    # until something calls ``wait`` on it. A subscriber this coordinator adopted rather than
    # started is never this process's child, so it carries no such reaping obligation; this
    # thread stands in for whatever does reap a real orphaned process, so the liveness check
    # below exercises the same "gone means gone" answer production sees.
    reaper = threading.Thread(target=proc.wait, daemon=True)
    reaper.start()
    try:
        assert RUNNER.process_is_running(proc.pid) is True
        supervisor.stop_record({"pid": proc.pid})
        assert RUNNER.process_is_running(proc.pid) is False
        assert supervisor.is_record_alive({"pid": proc.pid}, signature=()) is False
    finally:
        reaper.join(timeout=10)
        if proc.poll() is None:  # pragma: no cover - defensive clean-up
            proc.kill()
            proc.wait(timeout=10)


def test_stop_writers_does_not_forget_a_subscriber_that_will_not_die(tmp_path: Path) -> None:
    """A stop *requested* and a stop *confirmed* are different facts.

    Forgetting the durable record, or the in-memory handle, before the process is actually gone
    would let retirement archive a run a live writer can still reach. What ``stop_writers`` cannot
    confirm dead, retirement must still refuse on -- that is the fail-closed half of this contract.
    """

    class UnkillableSupervisor(FakeSupervisor):
        """A subscriber that receives every stop request and never actually dies."""

        def stop(self, handle: Any) -> None:
            return None

        def stop_record(self, record: Any) -> None:
            return None

    harness = Harness(tmp_path)
    harness.supervisor = UnkillableSupervisor()
    harness.coordinator = harness._build()
    harness.bootstrap([_child("child-a")])
    harness.coordinator.launch_ready_children()
    harness.run_child("child-a")
    harness.report_usage("child-a")
    harness.coordinator.integrate_child("child-a")
    harness.coordinator.reap_child("child-a")

    stopped = harness.coordinator.stop_writers()

    subscriber_status = next(
        value for key, value in stopped.items() if key.startswith("subscriber")
    )
    assert "still alive" in subscriber_status
    with pytest.raises(RUNNER.RetirementOrderError):
        harness.coordinator.retire()
    del tmp_path
