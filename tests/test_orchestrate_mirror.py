"""Contract tests for the orchestrate mirror: the operator's channel and the clock.

Organised by the property each group establishes, not by function. The five scenarios the
unit is required to cover are a floor:

1. a request that would route a validity judgement through the mirror is refused (KTD6);
2. a return over its declared bound is rejected, not absorbed or truncated into success;
3. the mirror has a register row from creation, not from first use;
4. a mirror silent past its declared tolerance raises divergence;
5. a request is dispatched without blocking the caller.

Two of those get adversarial treatment rather than a happy path: the bound is probed at
exactly the boundary, in bytes rather than characters, and for whether a rejection leaves the
mirror usable; and the clock is probed for the states where a naive detector reports health it
has not established -- an unarmed row and an idle mirror.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
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
MIRROR = _load("mirror")

MIRROR_SOURCE = (SCRIPTS / "mirror.py").read_text(encoding="utf-8")

RUN_ID = "run-a"
ROW_ID = "mirror-a"
NONCE = "0123456789abcdef"


@pytest.fixture(autouse=True)
def _host_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep live registers and run secrets out of the operator's real host state.

    ``launch_child`` records the run root beside the run secret, and that directory is refused
    when it sits inside the repository -- these tests use ``tmp_path`` as the repository, so
    both directories must be siblings of it rather than children.
    """
    monkeypatch.setenv(
        "ORCHESTRATE_REGISTER_DIR", str(tmp_path.parent / f"{tmp_path.name}-registers")
    )
    monkeypatch.setenv(
        "ORCHESTRATE_RUN_SECRET_DIR", str(tmp_path.parent / f"{tmp_path.name}-run-secrets")
    )


# --------------------------------------------------------------------------- fakes

IDENTITY = LIFECYCLE.LaunchIdentity("claude-mirror-1", "ws-a", "tab-a", "pane-mirror", False)


class FakeGit:
    def __init__(self, root: Path) -> None:
        self.root = root

    def base_commit(self, _root: Path) -> str:
        return "fake-base"

    def provision(self, _root: Path, spec: Any, *, base_commit: str | None = None) -> Any:
        assert not spec.mutating, "the mirror is read-only and must stay in the ambient checkout"
        return LIFECYCLE.Landing(self.root, "none", "none", base_commit, self.root)

    def changed_paths(self, _cwd: Path) -> frozenset[str]:
        return frozenset()

    def observed_paths(self, _cwd: Path, **_kwargs: Any) -> frozenset[str]:
        return frozenset()

    def fingerprint(self, _cwd: Path, _path: str) -> str:
        return "fake"

    def changed_paths_baseline(self, _cwd: Path, **_kwargs: Any) -> Any:
        return LIFECYCLE.ChangedPathsBaseline(frozenset(), ())


class FakeWrapper:
    def __init__(self, *, launch_error: Exception | None = None) -> None:
        self.launch_error = launch_error
        self.previews = 0
        self.launches = 0
        self.before_preview: Callable[[], None] | None = None
        self.before_launch: Callable[[], None] | None = None

    def preview(self, _spec: Any, _landing: Any, _label: str, _argv: list[str]) -> None:
        self.previews += 1
        if self.before_preview is not None:
            self.before_preview()

    def launch(self, _spec: Any, _landing: Any, _label: str, _argv: list[str]) -> Any:
        self.launches += 1
        if self.before_launch is not None:
            self.before_launch()
        if self.launch_error is not None:
            raise self.launch_error
        return IDENTITY


class FakeHerdr:
    """Records every pane it is asked to touch, so 'one voice' is checkable."""

    def __init__(self) -> None:
        self.text = "ready prompt"
        self.sent: list[tuple[str, str]] = []
        self.reads: list[str] = []
        self.send_error: Exception | None = None
        self.closed: list[str] = []
        self.present = True

    def discover_by_label(self, _label: str, *, cwd: Path) -> Any:
        return None

    def pane_text(self, pane_id: str, *, cwd: Path) -> str:
        self.reads.append(pane_id)
        return self.text

    def send_line(self, pane_id: str, text: str, *, cwd: Path) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.sent.append((pane_id, text))

    def tab_present(self, _tab_id: str, *, cwd: Path) -> bool:
        return self.present

    def close_tab(self, tab_id: str, *, cwd: Path) -> None:
        self.closed.append(tab_id)


class FakeInteraction:
    def observe(
        self,
        *,
        pane_id: str,
        match: str,
        timeout: float,
        dispatch: Any,
        accept: Any = None,
    ) -> Any:
        state = dispatch()
        return SimpleNamespace(revision=0), state


# --------------------------------------------------------------------------- helpers


def _create(
    tmp_path: Path,
    *,
    herdr: FakeHerdr | None = None,
    wrapper: FakeWrapper | None = None,
    **kwargs: Any,
) -> Any:
    return MIRROR.create_mirror(
        tmp_path,
        run_id=kwargs.pop("run_id", RUN_ID),
        row_id=kwargs.pop("row_id", ROW_ID),
        runtime=kwargs.pop("runtime", "claude"),
        workspace=kwargs.pop("workspace", "ws-a"),
        max_quiet_seconds=kwargs.pop("max_quiet_seconds", 600.0),
        wrapper=wrapper or FakeWrapper(),
        herdr=herdr or FakeHerdr(),
        git=FakeGit(tmp_path),
        interaction=FakeInteraction(),
        nonce=kwargs.pop("nonce", NONCE),
        **kwargs,
    )


def _request(**overrides: Any) -> Any:
    values: dict[str, Any] = {
        "request_id": "req-1",
        "kind": "synthesis",
        "instruction": "Compare the two child reports and state where they disagree.",
    }
    values.update(overrides)
    return MIRROR.MirrorRequest(**values)


def _pane_block(session: Any, request_id: str, material: str, *, prefix: str = "") -> str:
    """A pane transcript containing one complete return block for ``request_id``."""
    return (
        f"{prefix}"
        "thinking out loud, which the orchestrator never reads\n"
        f"{session.open_marker}\n"
        f"request: {request_id}\n"
        f"{material}\n"
        f"{session.close_marker}\n"
    )


def _row(tmp_path: Path, row_id: str = ROW_ID) -> dict[str, Any]:
    row: dict[str, Any] = REGISTER.read_rows(tmp_path, run_id=RUN_ID)[row_id]
    return row


def _module_function_calls() -> dict[str, set[str]]:
    """Every called name, grouped by the top-level function it appears in."""
    tree = ast.parse(MIRROR_SOURCE)
    calls: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        names: set[str] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Attribute):
                    names.add(func.attr)
                elif isinstance(func, ast.Name):
                    names.add(func.id)
        calls[node.name] = names
    return calls


# =========================================================================================
# Property: the mirror never evaluates a validity predicate (KTD6, R6b) -- scenario 1
# =========================================================================================


@pytest.mark.parametrize("kind", MIRROR.DECIDING_KINDS)
def test_a_request_that_asks_the_mirror_to_decide_is_refused_by_name(kind: str) -> None:
    with pytest.raises(MIRROR.PredicateInMirrorError) as caught:
        _request(kind=kind)
    message = str(caught.value)
    assert kind in message
    # The refusal has to say where the work does belong, or the caller's next move is a guess.
    assert "evaluate_completion" in message


def test_the_accepted_request_vocabulary_is_closed() -> None:
    with pytest.raises(MIRROR.MirrorError, match="vocabulary is closed"):
        _request(kind="whatever-looks-useful")
    for kind in MIRROR.READING_KINDS:
        assert _request(kind=kind).kind == kind


def test_an_instruction_carrying_a_predicate_declaration_is_refused() -> None:
    declaration = '{"argv": ["uv", "run", "pytest", "-q"], "timeout_seconds": 60}'
    with pytest.raises(MIRROR.PredicateInMirrorError, match="argv"):
        _request(instruction=f"Please run this check and tell me the result: {declaration}")


def test_prose_that_merely_mentions_a_check_is_not_mistaken_for_a_predicate() -> None:
    """The guard detects the declaration, not the vocabulary.

    A detector that refused any instruction mentioning tests would make the mirror useless for
    the reading work it exists to do, and would be a keyword filter dressed as a control.
    """
    assert _request(
        instruction="Read the failing pytest output in the log and summarise the failure modes."
    )


def test_the_mirror_module_can_neither_execute_a_program_nor_reach_the_completion_module() -> None:
    """The structural half of KTD6: there is no route here to the code that runs predicates.

    What this does not establish is stated in the module docstring: Herdr is driven through an
    injected adapter, and that adapter runs programs.
    """
    tree = ast.parse(MIRROR_SOURCE)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "subprocess" not in imported
    assert "completion" not in imported

    forbidden = {"system", "popen", "spawnv", "spawnl", "execv", "execvp", "eval", "exec"}
    for name, called in _module_function_calls().items():
        assert not (called & forbidden), f"{name} executes a program: {sorted(called & forbidden)}"


def test_the_mirror_never_writes_the_phase_that_gates_completion() -> None:
    """A mirror that says 'it passes' must change nothing.

    This is the containment that survives an instruction written in plain English, which no
    parser can catch: ``phase`` is not a column this module owns, so a mirror's opinion cannot
    become a verified row.
    """
    assert "phase" not in MIRROR.OWNED_COLUMNS
    with pytest.raises(MIRROR.ColumnOwnershipError, match="phase"):
        MIRROR._write_owned(Path("/unused"), ROW_ID, {"phase": "verified"}, run_id=RUN_ID)


# =========================================================================================
# Property: a return over its bound is rejected, never absorbed (R6) -- scenario 2
# =========================================================================================


def test_a_return_over_the_declared_bound_is_rejected(tmp_path: Path) -> None:
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(max_return_bytes=64), herdr=herdr, now=100.0)
    herdr.text = _pane_block(session, "req-1", "x" * 65)

    with pytest.raises(MIRROR.DistillationBoundError) as caught:
        MIRROR.collect_return(session, herdr=herdr, now=110.0)
    assert "65" in str(caught.value)


def test_a_return_of_exactly_the_bound_is_accepted(tmp_path: Path) -> None:
    """The boundary itself, because an off-by-one here rejects correct returns forever."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(max_return_bytes=64), herdr=herdr, now=100.0)
    herdr.text = _pane_block(session, "req-1", "x" * 64)

    returned = MIRROR.collect_return(session, herdr=herdr, now=110.0)
    assert returned.byte_length == 64
    assert returned.material == "x" * 64


def test_the_bound_is_measured_in_bytes_not_characters(tmp_path: Path) -> None:
    """Thirty-two two-byte characters are sixty-four bytes, and the bound is a byte bound."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(max_return_bytes=63), herdr=herdr, now=100.0)
    herdr.text = _pane_block(session, "req-1", "é" * 32)

    with pytest.raises(MIRROR.DistillationBoundError, match="64 bytes"):
        MIRROR.collect_return(session, herdr=herdr, now=110.0)


def test_the_rejection_does_not_reproduce_the_material_it_rejected(tmp_path: Path) -> None:
    """An error that quoted the oversized return would perform the absorption it reports."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(max_return_bytes=16), herdr=herdr, now=100.0)
    secret = "RAW-MATERIAL-THE-ORCHESTRATOR-MUST-NOT-ABSORB"
    herdr.text = _pane_block(session, "req-1", secret)

    with pytest.raises(MIRROR.DistillationBoundError) as caught:
        MIRROR.collect_return(session, herdr=herdr, now=110.0)
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value)


def test_a_rejected_return_leaves_the_mirror_usable(tmp_path: Path) -> None:
    """Rejection closes the request; it does not damage the session.

    The phase stays where the lifecycle left it, the outstanding request is cleared, and the
    next request dispatches -- so a return that was too long costs a round trip rather than
    the mirror.
    """
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    phase_before = _row(tmp_path)["phase"]
    MIRROR.dispatch_request(session, _request(max_return_bytes=16), herdr=herdr, now=100.0)
    herdr.text = _pane_block(session, "req-1", "y" * 200)
    with pytest.raises(MIRROR.DistillationBoundError):
        MIRROR.collect_return(session, herdr=herdr, now=110.0)

    row = _row(tmp_path)
    assert row["phase"] == phase_before
    assert row["mirror_request"] is None
    assert row["mirror_last_return"]["outcome"] == "rejected_oversized"

    MIRROR.dispatch_request(
        session, _request(request_id="req-2", max_return_bytes=64), herdr=herdr, now=120.0
    )
    herdr.text += _pane_block(session, "req-2", "shorter conclusion")
    assert MIRROR.collect_return(session, herdr=herdr, now=130.0).material == "shorter conclusion"


def test_a_declared_bound_above_the_ceiling_is_refused() -> None:
    """A byte bound is not eroded by deletion; it is eroded by being raised."""
    with pytest.raises(MIRROR.DistillationBoundError, match="ceiling"):
        _request(max_return_bytes=MIRROR.MAX_DECLARABLE_RETURN_BYTES + 1)
    assert _request(max_return_bytes=MIRROR.MAX_DECLARABLE_RETURN_BYTES).max_return_bytes


def test_a_rejected_return_is_durably_recorded_rather_than_silently_dropped(
    tmp_path: Path,
) -> None:
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(max_return_bytes=8), herdr=herdr, now=100.0)
    herdr.text = _pane_block(session, "req-1", "z" * 40)
    with pytest.raises(MIRROR.DistillationBoundError):
        MIRROR.collect_return(session, herdr=herdr, now=111.0)

    status = MIRROR.mirror_status(tmp_path, run_id=RUN_ID, row_id=ROW_ID)
    assert status["last_return"] == {
        "request_id": "req-1",
        "outcome": "rejected_oversized",
        "byte_length": 40,
        "max_return_bytes": 8,
        "at": 111.0,
    }


# =========================================================================================
# Property: the mirror has a register row from creation (R6c) -- scenario 3
# =========================================================================================


def test_the_mirror_row_exists_before_any_launch_side_effect(tmp_path: Path) -> None:
    """From creation, not from first use -- and not from a launch that succeeded.

    A mirror registered only after a successful launch is invisible in exactly the case the
    operator most needs to see it.
    """
    seen: list[dict[str, Any]] = []
    wrapper = FakeWrapper(launch_error=RuntimeError("launch exploded"))
    wrapper.before_preview = lambda: seen.append(_row(tmp_path))
    wrapper.before_launch = lambda: seen.append(_row(tmp_path))

    with pytest.raises(RuntimeError, match="launch exploded"):
        _create(tmp_path, wrapper=wrapper)

    assert len(seen) == 2
    for row in seen:
        assert row["role"] == MIRROR.MIRROR_ROLE
        assert row["max_quiet_seconds"] == 600.0
    surviving = _row(tmp_path)
    assert surviving["role"] == MIRROR.MIRROR_ROLE
    assert surviving.get("pane_id") is None


def test_the_mirror_row_is_identified_by_role_not_by_agent(tmp_path: Path) -> None:
    """``agent`` carries the launcher's actual agent name for every launched row.

    Writing ``mirror`` over it would make this module the second writer of a column the
    session lifecycle owns, which is the defect class this build has paid for repeatedly.
    """
    _create(tmp_path)
    row = _row(tmp_path)
    assert row["agent"] == IDENTITY.agent_name
    assert row["role"] == MIRROR.MIRROR_ROLE
    assert MIRROR.find_mirror_rows(REGISTER.read_rows(tmp_path, run_id=RUN_ID)) == {ROW_ID: row}


def test_a_row_that_is_not_a_mirror_is_refused_by_every_mirror_operation(tmp_path: Path) -> None:
    REGISTER.upsert_row(tmp_path, "child-a", {"agent": "codex"}, run_id=RUN_ID)
    with pytest.raises(MIRROR.MirrorNotRegisteredError, match="role"):
        MIRROR.mirror_status(tmp_path, run_id=RUN_ID, row_id="child-a")
    with pytest.raises(MIRROR.MirrorNotRegisteredError):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id="missing-entirely", now=1.0)


def test_the_mirror_is_launched_through_the_ordinary_session_path(tmp_path: Path) -> None:
    """It is a session, so it gets the write-ahead launch, the label, and the readiness gate."""
    herdr = FakeHerdr()
    wrapper = FakeWrapper()
    session = _create(tmp_path, herdr=herdr, wrapper=wrapper)
    row = _row(tmp_path)
    assert wrapper.previews == 1 and wrapper.launches == 1
    assert row["task"] == LIFECYCLE.task_label(RUN_ID, ROW_ID)
    assert row["phase"] == "ready"
    assert row["pane_id"] == session.pane_id == IDENTITY.pane_id


def test_the_mirrors_return_subscription_is_a_valid_herdr_subscription(tmp_path: Path) -> None:
    """The subscriber is what turns a return into a wake, so the subscription must be real."""
    session = _create(tmp_path)
    assert len(session.subscriptions) == 1
    subscription = session.subscriptions[0]
    EVENTS.validate_subscription(subscription)
    assert subscription["pane_id"] == session.pane_id
    assert subscription["match"]["value"] == session.close_marker
    # The subscriber refuses any output subscription that is not a complete sentinel.
    SUBSCRIBER._sentinel_expectations([subscription])


# =========================================================================================
# Property: a silent mirror is detectable only by a clock (R6c) -- scenario 4
# =========================================================================================


def test_a_mirror_silent_past_its_tolerance_raises_divergence(tmp_path: Path) -> None:
    """The failure with no disagreement in it: expected and observed agree, and it is dead."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr, max_quiet_seconds=300.0)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1_000.0)

    with pytest.raises(MIRROR.MirrorQuietTooLongError, match="req-1"):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1_000.0 + 300.001)


def test_silence_of_exactly_the_tolerance_is_not_divergence(tmp_path: Path) -> None:
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr, max_quiet_seconds=300.0)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1_000.0)

    liveness = MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1_300.0)
    assert liveness.state == "working"
    assert liveness.quiet_seconds == 300.0


def test_an_idle_mirror_is_never_reported_as_hung(tmp_path: Path) -> None:
    """Between requests a mirror is legitimately silent forever.

    A clock armed on an idle row would alarm on every healthy run, and an alarm that always
    fires is an alarm nobody reads.
    """
    _create(tmp_path, max_quiet_seconds=1.0)
    liveness = MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1_000_000_000.0)
    assert liveness.state == "idle"
    assert liveness.quiet_seconds is None


def test_a_row_with_no_declared_tolerance_is_not_reported_healthy(tmp_path: Path) -> None:
    """Unarmed is a third state, distinct from healthy and from hung."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=10.0)
    REGISTER.upsert_row(tmp_path, ROW_ID, {"max_quiet_seconds": None}, run_id=RUN_ID)

    with pytest.raises(MIRROR.MirrorNotArmedError, match="not armed"):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1_000_000.0)


def test_an_observed_event_moves_the_clocks_reference_forward(tmp_path: Path) -> None:
    """``last_event_at`` is the subscriber's, and the clock reads it rather than owning it."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr, max_quiet_seconds=100.0)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1_000.0)
    with pytest.raises(MIRROR.MirrorQuietTooLongError):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1_200.0)

    REGISTER.upsert_row(tmp_path, ROW_ID, {"last_event_at": 1_150.0}, run_id=RUN_ID)
    liveness = MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1_200.0)
    assert liveness.quiet_seconds == 50.0


def test_the_clock_writes_nothing(tmp_path: Path) -> None:
    """Raising divergence is advisory. What to do about a quiet mirror is a decision."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr, max_quiet_seconds=5.0)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)
    path = REGISTER.register_path(RUN_ID)
    before = path.read_bytes()

    with pytest.raises(MIRROR.MirrorQuietTooLongError):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1_000.0)
    assert path.read_bytes() == before


def test_the_clock_takes_an_injected_instant_rather_than_reading_the_system_clock() -> None:
    """A test that sleeps is flaky by construction, so the time source is a parameter."""
    for function in (MIRROR.check_liveness, MIRROR.dispatch_request, MIRROR.collect_return):
        parameter = inspect.signature(function).parameters["now"]
        assert parameter.default is inspect.Parameter.empty, function.__name__
    imported = {
        alias.name
        for node in ast.walk(ast.parse(MIRROR_SOURCE))
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "time" not in imported


# =========================================================================================
# Property: dispatch does not block the caller -- scenario 5
# =========================================================================================


def test_dispatch_returns_without_waiting_for_the_return(tmp_path: Path) -> None:
    """It sends and returns: no subscription held open, no pane polled, no event awaited.

    What this establishes is that *this* call does not wait. It does not establish that the
    orchestrator answers the operator while a request is outstanding -- that is a property of
    the calling control flow and is established end to end, not here.
    """
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    herdr.reads.clear()
    herdr.sent.clear()

    assert MIRROR.dispatch_request(session, _request(), herdr=herdr, now=5.0) == "req-1"
    assert herdr.reads == []
    assert len(herdr.sent) == 1
    # Nothing has come back, and dispatch did not wait to find that out.
    with pytest.raises(MIRROR.NoReturnAvailableError):
        MIRROR.collect_return(session, herdr=herdr, now=6.0)


def test_dispatch_cannot_block_on_an_event_because_it_has_no_way_to() -> None:
    """``HerdrInteraction`` is the blocking primitive in this codebase; dispatch never sees one."""
    parameters = inspect.signature(MIRROR.dispatch_request).parameters
    assert "interaction" not in parameters
    assert "timeout" not in parameters
    assert "observe" not in _module_function_calls()["dispatch_request"]


def test_the_outstanding_request_is_durable_before_the_line_is_sent(tmp_path: Path) -> None:
    """Write-ahead: a send that fails leaves an armed clock, not an idle-looking mirror."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    herdr.send_error = LIFECYCLE.LaunchProtocolError("herdr pane run failed")

    with pytest.raises(LIFECYCLE.LaunchProtocolError):
        MIRROR.dispatch_request(session, _request(), herdr=herdr, now=7.0)

    outstanding = _row(tmp_path)["mirror_request"]
    assert outstanding["request_id"] == "req-1"
    assert outstanding["dispatched_at"] == 7.0


def test_a_second_request_while_one_is_outstanding_is_refused_explicitly(tmp_path: Path) -> None:
    """Refused with a reason, never silently dropped (R8)."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)

    with pytest.raises(MIRROR.MirrorBusyError, match="req-1"):
        MIRROR.dispatch_request(session, _request(request_id="req-2"), herdr=herdr, now=2.0)


def test_dispatch_addresses_only_the_mirrors_own_pane(tmp_path: Path) -> None:
    """One voice on the operator's channel, and it is not the mirror's (R9)."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)
    assert {pane for pane, _text in herdr.sent} == {session.pane_id}


# =========================================================================================
# Property: a return is bound to the request that asked for it
# =========================================================================================


def test_a_block_from_an_earlier_request_is_not_collected_as_the_current_one(
    tmp_path: Path,
) -> None:
    """The markers are stable for the mirror's life, so the pane still holds old blocks."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)
    herdr.text = _pane_block(session, "req-1", "first answer")
    assert MIRROR.collect_return(session, herdr=herdr, now=2.0).material == "first answer"

    MIRROR.dispatch_request(session, _request(request_id="req-2"), herdr=herdr, now=3.0)
    with pytest.raises(MIRROR.NoReturnAvailableError, match="earlier request"):
        MIRROR.collect_return(session, herdr=herdr, now=4.0)


def test_an_unopened_or_unclosed_block_is_not_a_return(tmp_path: Path) -> None:
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)

    herdr.text = f"{session.open_marker}\nrequest: req-1\nhalf an answer\n"
    with pytest.raises(MIRROR.NoReturnAvailableError):
        MIRROR.collect_return(session, herdr=herdr, now=2.0)

    herdr.text = f"request: req-1\nan answer with no opening\n{session.close_marker}\n"
    with pytest.raises(MIRROR.NoReturnAvailableError):
        MIRROR.collect_return(session, herdr=herdr, now=2.0)


def test_collecting_with_nothing_outstanding_is_refused(tmp_path: Path) -> None:
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    with pytest.raises(MIRROR.NoReturnAvailableError, match="no outstanding request"):
        MIRROR.collect_return(session, herdr=herdr, now=1.0)


def test_the_charter_never_contains_an_assembled_marker(tmp_path: Path) -> None:
    """Otherwise every echo of the dispatch prompt would look like a completed return."""
    session = _create(tmp_path)
    charter = MIRROR.mirror_charter(
        session.open_marker, session.close_marker, max_return_bytes=4096
    )
    assert session.open_marker not in charter
    assert session.close_marker not in charter
    assert "never address the operator" in charter.lower()


# =========================================================================================
# Property: this module writes only the columns it owns
# =========================================================================================


def test_writing_a_column_this_module_does_not_own_is_refused() -> None:
    for column in ("artifact_path", "observed_state", "phase", "completion", "tokens_reserved"):
        with pytest.raises(MIRROR.ColumnOwnershipError, match=column):
            MIRROR._write_owned(Path("/unused"), ROW_ID, {column: "anything"}, run_id=RUN_ID)


def test_every_register_write_in_this_module_goes_through_the_owned_seam() -> None:
    """Ownership recorded somewhere checkable, rather than in a comment that drifts."""
    for name, called in _module_function_calls().items():
        if name == "_write_owned":
            continue
        assert "upsert_row" not in called, f"{name} writes the register outside the owned seam"
        assert "upsert_rows" not in called, f"{name} writes the register outside the owned seam"


def test_a_full_mirror_cycle_leaves_columns_this_module_does_not_own_untouched(
    tmp_path: Path,
) -> None:
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    settled = _row(tmp_path)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)
    herdr.text = _pane_block(session, "req-1", "a distilled conclusion")
    MIRROR.collect_return(session, herdr=herdr, now=2.0)

    row = _row(tmp_path)
    assert "artifact_path" not in row
    assert "completion" not in row
    assert row["phase"] == settled["phase"]
    assert row["observed_state"] == settled["observed_state"]
    assert row["observed_state_source"] == settled["observed_state_source"]
    changed = {key for key in row if row[key] != settled.get(key)}
    assert changed <= set(MIRROR.OWNED_COLUMNS)


# =========================================================================================
# Property: the mirror's context is managed deliberately (R6a)
# =========================================================================================


def test_a_context_reset_is_refused_while_a_request_is_outstanding(tmp_path: Path) -> None:
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)
    with pytest.raises(MIRROR.MirrorBusyError):
        MIRROR.request_context_reset(session, "compact", herdr=herdr)


def test_a_runtime_whose_context_commands_are_unknown_is_refused_rather_than_guessed(
    tmp_path: Path,
) -> None:
    """Sending an unrecognised slash command is a silent no-op that looks like a reset."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr, runtime="codex")
    with pytest.raises(MIRROR.UnsupportedContextCommandError, match="codex"):
        MIRROR.request_context_reset(session, "compact", herdr=herdr)


def test_a_context_reset_sends_the_established_command(tmp_path: Path) -> None:
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    herdr.sent.clear()
    assert MIRROR.request_context_reset(session, "clear", herdr=herdr) == "/clear"
    assert herdr.sent == [(session.pane_id, "/clear")]
    with pytest.raises(MIRROR.MirrorError, match="context action"):
        MIRROR.request_context_reset(session, "restart", herdr=herdr)


# =========================================================================================
# Property: creation refuses a mirror that could not be watched
# =========================================================================================


@pytest.mark.parametrize("bad", [0, -1, "600"])
def test_a_mirror_cannot_be_created_without_a_usable_quiet_bound(tmp_path: Path, bad: Any) -> None:
    """The clock is the only detector this failure has, so creating without one is refused."""
    with pytest.raises(MIRROR.MirrorError, match="max_quiet_seconds"):
        _create(tmp_path, max_quiet_seconds=bad)
    assert not REGISTER.read_rows(tmp_path, run_id=RUN_ID)
