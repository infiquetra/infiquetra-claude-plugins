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
import base64
import importlib.util
import inspect
import json
import sys
import time
from collections.abc import Callable, Mapping
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
        self.snapshot_error: Exception | None = None

    def snapshot(self, *, cwd: Path) -> dict[str, Any]:
        if self.snapshot_error is not None:
            raise self.snapshot_error
        if not self.present:
            return {"tabs": [], "panes": [], "agents": []}
        return {
            "tabs": [
                {
                    "label": LIFECYCLE.task_label(RUN_ID, ROW_ID),
                    "tab_id": IDENTITY.tab_id,
                    "workspace_id": IDENTITY.workspace_id,
                }
            ],
            "panes": [
                {
                    "pane_id": IDENTITY.pane_id,
                    "tab_id": IDENTITY.tab_id,
                    "workspace_id": IDENTITY.workspace_id,
                    "cwd": str(cwd),
                    "foreground_cwd": str(cwd),
                    "agent_status": "working",
                }
            ],
            "agents": [
                {
                    "pane_id": IDENTITY.pane_id,
                    "tab_id": IDENTITY.tab_id,
                    "workspace_id": IDENTITY.workspace_id,
                    "cwd": str(cwd),
                    "foreground_cwd": str(cwd),
                    "agent_status": "working",
                }
            ],
        }

    def discover_by_label(self, label: str, *, cwd: Path) -> Any:
        return LIFECYCLE.HerdrControl.discover_by_label(self, label, cwd=cwd)

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
    acknowledge: bool = True,
    **kwargs: Any,
) -> Any:
    """Create a mirror, and by default confirm its subscription the way composition must.

    ``acknowledge=False`` leaves the wire unconfirmed, which is the state a composition that
    forgot to hand the subscriber the mirror's subscription would be in.
    """
    session = MIRROR.create_mirror(
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
    if acknowledge:
        MIRROR.acknowledge_subscription(session, list(session.subscriptions), now=0.5)
    return session


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
        "repository_changes": [],
        "repository_observed": False,
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
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(surviving)


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


def test_a_mirror_role_lands_in_the_identity_write_and_a_writerless_upsert_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The identity must be one write, and the column stays owned."""
    payloads: list[Mapping[str, Any]] = []
    real_upsert = MIRROR.register_store.upsert_row

    def tracking_upsert(root: Path, row_id: str, fields: Mapping[str, Any], **kwargs: Any) -> Any:
        payloads.append(dict(fields))
        return real_upsert(root, row_id, fields, **kwargs)

    def split_write_role(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("role must not be a second public write")

    monkeypatch.setattr(MIRROR.register_store, "upsert_row", tracking_upsert)
    monkeypatch.setattr(MIRROR.register_store, "write_role", split_write_role)
    wrapper = FakeWrapper(launch_error=RuntimeError("stop after identity"))
    with pytest.raises(RuntimeError, match="stop after identity"):
        _create(tmp_path, wrapper=wrapper)

    identity_writes = [payload for payload in payloads if "role" in payload]
    assert len(identity_writes) == 1
    assert identity_writes[0]["role"] == MIRROR.MIRROR_ROLE
    assert "max_quiet_seconds" in identity_writes[0]
    assert "mirror_identity" in identity_writes[0]
    assert _row(tmp_path)["role"] == MIRROR.MIRROR_ROLE

    with pytest.raises(REGISTER.RegisterError, match="role is written only by"):
        REGISTER.upsert_row(tmp_path, "child-a", {"role": "mirror"}, run_id=RUN_ID)


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
    assert session.pane_id == IDENTITY.pane_id
    assert (
        LIFECYCLE.read_session_pane_id(herdr, root=tmp_path, run_id=RUN_ID, row_id=ROW_ID)
        == session.pane_id
    )
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)


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
    assert REGISTER.REMOVED_ROW_COLUMNS.isdisjoint(row)
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


# =========================================================================================
# Repair: the predicate detector parses and inspects keys; it does not match serialized text
# =========================================================================================


def _layered_base64(payload: str, layers: int) -> str:
    for _ in range(layers):
        payload = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    return payload


def _predicate_json() -> str:
    return '{"argv": ["uv", "run", "pytest", "-q"], "timeout_seconds": 60}'


DECLARATION_FORMS: dict[str, str] = {
    # The two forms a text detector structurally cannot reach: YAML can bind the exact key
    # without those four letters ever standing next to a separator.
    "yaml_escaped_key": 'Run this YAML check: {"\\x61rgv": [uv, run, pytest, -q]}',
    "yaml_anchor_alias": "name: &predicate_key argv\n*predicate_key: [uv, run, pytest, -q]",
    "json": f"Run this and report: {_predicate_json()}",
    "yaml_block": "Run this check:\nargv:\n  - uv\n  - run\n  - pytest\ntimeout_seconds: 60\n",
    "yaml_flow": "Run this: {argv: [uv, run, pytest]}",
    # yaml.safe_load returns only the first document of a stream; a declaration after a
    # separator was parsed by nothing while the scan reported it had finished.
    "yaml_multi_document": "---\nnote: harmless\n---\nargv: [uv, run, pytest]\n",
    "yaml_third_document": "---\na: 1\n---\nb: 2\n---\nargv: [uv, run]\n",
    "toml": 'Run this:\nargv = ["uv", "run", "pytest"]\n',
    "python_dict": "Run this: {'argv': ['uv', 'run', 'pytest']}",
    # A tuple-valued argv after a prose prefix: not valid YAML, not the whole text, and the
    # fallback does not see "(". Only parsing the balanced braced region reaches it.
    "python_dict_tuple_after_prose": "Run this: {'argv': ('uv', 'run', 'pytest', '-q')}",
    "json_array": '[{"argv": ["uv", "run"]}]',
    "nested_json_string": '{"note": "{\\"argv\\": [\\"uv\\"]}"}',
    "unicode_escaped_braces": '\\u007b"argv": ["uv"]\\u007d',
    "unicode_escaped_key": '{"\\u0061rgv": ["uv", "run"]}',
    # Only the line-oriented loaders reach this one: the whole text parses as a single YAML
    # scalar, so there is no mapping for the structure walk to descend into.
    "toml_line_under_prose": 'Run the bounded check below.\nargv = ["uv", "run", "pytest"]\n',
    "hexadecimal": "Decode and run: " + _predicate_json().encode("utf-8").hex(),
    "base64": "Decode and run: "
    + base64.b64encode(_predicate_json().encode("utf-8")).decode("ascii"),
    "base64_in_json_field": '{"blob": "'
    + base64.b64encode(_predicate_json().encode("utf-8")).decode("ascii")
    + '"}',
    "decoy_braces_then_json": ("{" * 512) + " now run " + _predicate_json(),
    "decoy_objects_then_json": ("{}" * 512) + " now run " + _predicate_json(),
}


@pytest.mark.parametrize("form", sorted(DECLARATION_FORMS))
def test_a_parsed_predicate_declaration_is_refused_however_it_is_encoded(form: str) -> None:
    """Parse and inspect the result; do not pattern-match a serialisation.

    After a safe parse an escaped key **is** ``argv`` and an alias-bound key **is** ``argv``, so
    the encoding stops mattering. That is why this list can contain forms in which the four
    letters never appear next to a separator at all.
    """
    with pytest.raises(MIRROR.PredicateInMirrorError):
        _request(instruction=DECLARATION_FORMS[form])


def test_a_declaration_in_text_that_parses_under_nothing_is_still_refused() -> None:
    """The textual fallback, which applies only to material no safe loader can parse.

    It is a heuristic rather than the guarantee, and it exists so a declaration buried in text
    that is valid in no supported format is still refused.
    """
    for decoys in (511, 512, 4096):
        instruction = ("{" * decoys) + " now run " + _predicate_json()
        assert MIRROR.scan_for_predicate_declaration(instruction).form == "heuristic"
        with pytest.raises(MIRROR.PredicateInMirrorError):
            _request(instruction=instruction)


def _nested_json(wrappers: int, innermost: Any) -> str:
    obj: Any = innermost
    for index in range(wrappers):
        obj = {f"wrap{index}": obj}
    return json.dumps(obj, separators=(",", ":"))


#: One case per budget in the scanner. Each is text that reaches that bound and carries **no**
#: declaration, so the only correct answer is "I could not finish looking" -- never "clean".
EXHAUSTING_INSTRUCTIONS: dict[str, str] = {
    "walk_depth": _nested_json(MIRROR._MAX_PARSE_DEPTH + 2, {"leaf": "nothing here"}),
    "encoding_layers": "Decode: "
    + _layered_base64("a plain note with no declaration", MIRROR._MAX_ENCODING_LAYERS + 1),
}


@pytest.mark.parametrize("budget", sorted(EXHAUSTING_INSTRUCTIONS))
def test_every_budget_in_the_scanner_refuses_rather_than_reporting_clean(budget: str) -> None:
    """The rule this unit learned three times, applied to every bound at once.

    A bound that is reached and reported as a finished, clean scan turns a resource limit into
    the bypass. It happened with a decode budget, then a line sweep, then the structure walk --
    each fixed alone while the next one waited. These cases carry no declaration at all: the
    refusal is entirely because the scan cannot say they are clean.
    """
    text = EXHAUSTING_INSTRUCTIONS[budget]
    scan = MIRROR.scan_for_predicate_declaration(text)
    assert scan.found is False
    assert scan.complete is False, f"{budget} was exhausted and still reported a finished scan"
    assert scan.suspicious is True
    with pytest.raises(MIRROR.PredicateInMirrorError, match="could not be fully examined"):
        _request(instruction=text)


def test_every_bound_on_the_budget_records_exhaustion() -> None:
    """The uniformity check: exhausting *any* bound must mark the scan unfinished.

    Two of these — the node ceiling and the decoded-byte ceiling — are backstops that no
    instruction under the byte cap is likely to reach, which is exactly why they are exercised
    directly rather than only through text. A bound nobody can reach today is still a bound that
    a later change can reach, and the defect this unit paid for three times was a bound that
    could be reached without saying so.
    """
    budget = MIRROR._ScanBudget(decoded_bytes=10)
    assert budget.finished is True

    # depth
    deep = MIRROR._ScanBudget(decoded_bytes=10)
    assert deep.visit({}, MIRROR._MAX_PARSE_DEPTH + 1) is False
    assert deep.finished is False

    # node ceiling
    nodes = MIRROR._ScanBudget(decoded_bytes=10)
    nodes.nodes = 0
    assert nodes.visit({}, 0) is False
    assert nodes.finished is False

    # decoded bytes
    decoded = MIRROR._ScanBudget(decoded_bytes=4)
    assert decoded.take_decoded(2) is True
    assert decoded.take_decoded(99) is False
    assert decoded.finished is False

    # embedded regions
    regions = MIRROR._ScanBudget(decoded_bytes=10)
    regions.regions = 0
    assert regions.take_region() is False
    assert regions.finished is False

    # every one of them recorded a reason, so the refusal can say which bound ended the look
    for exhausted in (deep, nodes, decoded, regions):
        assert exhausted.reasons


def test_a_text_with_more_embedded_regions_than_the_bound_is_refused() -> None:
    """The region bound, end to end, on text carrying no declaration at all."""
    text = "note " + " ".join("{}" for _ in range(MIRROR._MAX_EMBEDDED_REGIONS + 5))
    scan = MIRROR.scan_for_predicate_declaration(text)
    assert scan.found is False
    assert scan.complete is False
    with pytest.raises(MIRROR.PredicateInMirrorError, match="could not be fully examined"):
        _request(instruction=text)


def test_completeness_is_decided_in_exactly_one_place() -> None:
    """Structural, because remembering is what failed three times.

    Every bound funnels through one budget object and the scan constructs one ``ScanResult``,
    so a bound added later cannot report a clean scan by forgetting to say otherwise. If this
    test fails, a second decision point has appeared and the guarantee is back to being a
    convention.
    """
    tree = ast.parse(MIRROR_SOURCE)
    constructions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ScanResult"
    ]
    assert len(constructions) == 1, f"ScanResult is constructed {len(constructions)} times"
    keywords = {kw.arg for kw in constructions[0].keywords}
    assert "complete" in keywords


def test_a_declaration_below_the_old_depth_cliff_is_refused() -> None:
    """The exact case that reached the pane: nine wrappers around a real declaration.

    Depth 7 refused and depth 9 did not, because the walk returned a bare "not found" at its
    limit and the caller could not tell that answer from "not present".
    """
    declaration = {"argv": ["uv", "run", "pytest", "-q"]}
    for wrappers in (0, 7, 8, 9, 12, 20):
        text = _nested_json(wrappers, declaration)
        assert MIRROR.scan_for_predicate_declaration(text).found is True, wrappers
        with pytest.raises(MIRROR.PredicateInMirrorError):
            _request(instruction=text)


def test_a_realistically_nested_document_is_still_readable() -> None:
    """Raising the depth limit is not the fix, but refusing real documents would be a new one.

    A workflow or manifest nests well under the limit; the limit exists to bound hostile input,
    which is why refusing at it costs nothing.
    """
    assert _request(instruction=_nested_json(12, {"steps": ["build", "test"], "runs-on": "linux"}))


def test_an_alias_amplified_document_is_examined_in_bounded_time() -> None:
    """The memoised walk is what bounds alias amplification -- not a count of alias-looking text.

    A 424-byte document using YAML's numeric anchors took over nine seconds to scan, because the
    counter that was supposed to stop it only recognised letter aliases. A shared node is now
    examined once.
    """
    document = "a0: &1 [x, y, z, w, v, u, t, s, r, q, p, o, n, m, l, k]\n"
    previous = 1
    for level in range(1, 8):
        document += f"a{level}: &{level + 1} [" + ", ".join([f"*{previous}"] * 16) + "]\n"
        previous = level + 1
    document += f"top: *{previous}\n"

    started = time.monotonic()
    scan = MIRROR.scan_for_predicate_declaration(document)
    elapsed = time.monotonic() - started
    assert scan.found is False
    assert elapsed < 2.0, f"alias-amplified scan took {elapsed:.1f}s"
    # And it is *examined*, not merely survived: without memoisation the node budget is what
    # ends the walk, which is honest but refuses a document carrying no declaration at all.
    assert scan.complete is True
    assert _request(instruction=document)


BENIGN_INSTRUCTIONS: dict[str, str] = {
    "english_residual": "Run the tests and tell me whether they pass.",
    "long_repo_paths": (
        "Compare plugins/orchestrate/skills/orchestrate/scripts/mirror and "
        "plugins/orchestrate/skills/orchestrate/scripts/register and summarise the difference."
    ),
    "mentions_permission_argv": (
        "Read session_lifecycle and explain what permission_argv: returns for each runtime."
    ),
    "ordinary_synthesis": "Compare the two child reports and state where they disagree.",
    "json_without_argv": 'Summarise this config: {"timeout_seconds": 60, "retries": 3}',
    # Every one of these was refused by the previous text-matching detector. The mirror exists
    # to read this repository's source, so refusing them was as much a defect as accepting a
    # declaration -- and one change fixed both directions.
    "argv_assigned_from_a_call": (
        "Read the launcher modules and explain why argv = permission_argv(runtime)."
    ),
    "argv_annotation_in_prose": (
        "Compare how argv: list[str] is validated across the launcher modules."
    ),
    "sys_argv_attribute": "Explain sys.argv: list[str] in the launcher.",
    "star_argv_parameter": "Explain def main(*argv: str) -> int in the launcher.",
    "parameter_named_argv": "Describe parameter argv: list[str] on the entry point.",
    "os_argv_attribute": "What does os.argv: refer to here?",
    "argv_documentation_heading": "Summarise the section titled argv: and what it covers.",
    "an_annotation_block": "Explain these annotations:\nargv: list[str]\nenv: dict[str, str]\n",
    # Parses into a structure that carries no declaration -- the line is commented out. The
    # textual fallback would match it, which is exactly why the fallback is confined to
    # material no loader could parse.
    "a_config_with_the_line_commented_out": (
        'Summarise this config:\n# argv = ["uv", "run", "pytest"]\nname = "report"\n'
    ),
    "seventeen_commit_ids": "Summarise these commits: "
    + " ".join(["a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"] * 17),
}


@pytest.mark.parametrize("case", sorted(BENIGN_INSTRUCTIONS))
def test_reading_work_is_not_mistaken_for_a_declaration(case: str) -> None:
    """A mirror that refuses ordinary synthesis is as broken as one that accepts a predicate.

    The English case is the disclosed residual: it asks for a check in prose and is accepted,
    because no detector for intent is achievable. That is stated rather than papered over.
    """
    assert _request(instruction=BENIGN_INSTRUCTIONS[case])


def test_an_argv_bound_to_a_string_is_not_the_predicate_schemas_shape() -> None:
    """Precision comes from binding the rule to the schema, not from a looser pattern.

    ``PredicateSpec`` rejects an ``argv`` that is a command string outright, so a mapping whose
    ``argv`` is a string is not a declaration -- which is exactly why a type annotation survives.
    """
    assert _request(instruction='{"argv": "uv run pytest -q"}')
    assert MIRROR.scan_for_predicate_declaration("argv: list[str]").found is False
    with pytest.raises(MIRROR.PredicateInMirrorError):
        _request(instruction='{"argv": ["uv", "run"]}')


def test_the_scan_names_the_loader_that_parsed_the_declaration() -> None:
    """Which path caught it is the difference between the guarantee and the heuristic."""
    assert MIRROR.scan_for_predicate_declaration(_predicate_json()).form == "json"
    assert MIRROR.scan_for_predicate_declaration("argv:\n  - uv\n  - run\n").form == "yaml"
    assert MIRROR.scan_for_predicate_declaration('argv = ["uv", "run"]').form == "toml"
    # The whole text is one YAML scalar, so only the line-oriented loaders reach the
    # declaration. The textual fallback would also refuse it -- but as a heuristic, not as a
    # parse, and the form is how that difference stays visible.
    assert (
        MIRROR.scan_for_predicate_declaration(
            'Run the bounded check below.\nargv = ["uv", "run", "pytest"]\n'
        ).form
        == "toml"
    )


def test_escaped_text_is_resolved_so_the_catch_is_structural_not_heuristic() -> None:
    """Both routes refuse it; only one of them is the guarantee.

    Resolving ``\\uXXXX`` first turns a declaration written with escaped braces into something a
    loader can parse, so it is caught by the parser rather than falling through to the textual
    fallback. The form is how that difference is observable.
    """
    escaped = '\\u007b"argv": ["uv"]\\u007d'
    assert MIRROR.scan_for_predicate_declaration(escaped).form == "json"
    with pytest.raises(MIRROR.PredicateInMirrorError):
        _request(instruction=escaped)


@pytest.mark.parametrize("layers", [1, 2, 3, 4])
def test_layered_base64_is_unwrapped_rather_than_capped_at_one_layer(layers: int) -> None:
    """The previous revision followed one layer and called the second a stated limit.

    Each layer strictly shrinks the text, so unwrapping terminates on its own and there is no
    cliff to document -- which is what lets every published page say Base64 is caught without
    an asterisk.
    """
    payload = _predicate_json()
    for _ in range(layers):
        payload = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    assert MIRROR.scan_for_predicate_declaration(f"Decode and run: {payload}").form == "encoded"
    with pytest.raises(MIRROR.PredicateInMirrorError):
        _request(instruction=f"Decode and run: {payload}")


def _module_attribute_names() -> set[str]:
    """Every ``module.attribute`` reference in the mirror source, as dotted text."""
    return {
        f"{node.value.id}.{node.attr}"
        for node in ast.walk(ast.parse(MIRROR_SOURCE))
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
    }


def test_every_loader_this_detector_uses_is_a_safe_loader() -> None:
    """A parser that executed untrusted input would be a worse defect than the one it fixes.

    Asserted structurally rather than by comment. ``yaml.load`` will construct arbitrary Python
    objects named in the document; ``yaml.safe_load`` will not, and it is the only one this
    module may reach. The loaders are referenced as values and called through a variable, so
    this checks the attribute references rather than the call names.
    """
    attributes = _module_attribute_names()
    assert "yaml.safe_load" in attributes
    assert "yaml.safe_load_all" in attributes
    assert "yaml.load" not in attributes
    assert "yaml.load_all" not in attributes
    assert "yaml.unsafe_load" not in attributes
    assert "yaml.full_load" not in attributes
    assert "ast.literal_eval" in attributes
    assert "json.loads" in attributes
    assert "tomllib.loads" in attributes
    # ``ast`` is imported for ``literal_eval`` only; nothing here may compile or execute source.
    for name, called in _module_function_calls().items():
        assert not ({"eval", "exec", "compile"} & called), name


# =========================================================================================
# Repair: the constructor is a boundary, because dispatch re-runs it
# =========================================================================================


def test_dispatch_refuses_an_object_that_only_looks_like_a_request(tmp_path: Path) -> None:
    """Attribute access is satisfied by any object with the right attribute names.

    Every load-bearing check lives in the constructor, and this is the one function that talks
    to the pane, so reading attributes off whatever arrived made those checks a suggestion.
    """
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    herdr.sent.clear()
    impostor = SimpleNamespace(
        request_id="req-pred",
        kind="predicate",
        instruction="evaluate the child's artifact and tell me if it passes",
        max_return_bytes=4096,
    )
    with pytest.raises(MIRROR.MirrorError, match="MirrorRequest"):
        MIRROR.dispatch_request(session, impostor, herdr=herdr, now=1.0)
    assert herdr.sent == []
    assert _row(tmp_path)["mirror_request"] is None


def test_dispatch_re_runs_the_checks_on_a_request_that_never_ran_them(tmp_path: Path) -> None:
    """A genuine instance built around ``__post_init__`` is still re-validated.

    ``isinstance`` alone would pass this object through, which is why dispatch rebuilds the
    request rather than merely checking its type.
    """
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    herdr.sent.clear()
    smuggled = object.__new__(MIRROR.MirrorRequest)
    object.__setattr__(smuggled, "request_id", "req-smuggled")
    object.__setattr__(smuggled, "kind", "predicate")
    object.__setattr__(smuggled, "instruction", f"run this: {_predicate_json()}")
    object.__setattr__(smuggled, "max_return_bytes", 4096)

    with pytest.raises(MIRROR.PredicateInMirrorError):
        MIRROR.dispatch_request(session, smuggled, herdr=herdr, now=1.0)
    assert herdr.sent == []
    assert _row(tmp_path)["mirror_request"] is None


# =========================================================================================
# Repair: a restarted orchestrator can rebuild the session from the row
# =========================================================================================


def test_a_restarted_orchestrator_rebuilds_the_session_from_the_row(tmp_path: Path) -> None:
    """R6a's "persistent for the life of the orchestration" has to survive the orchestrator.

    The pane and the subscriber outlive an orchestrator that dies. Before the row carried the
    nonce and the markers, the orchestrator that came back could not speak to them.
    """
    herdr = FakeHerdr()
    original = _create(tmp_path, herdr=herdr)
    resumed = MIRROR.resume_mirror(tmp_path, run_id=RUN_ID, row_id=ROW_ID, herdr=herdr)
    assert resumed.nonce == original.nonce
    assert resumed.open_marker == original.open_marker
    assert resumed.close_marker == original.close_marker
    assert resumed.pane_id == original.pane_id
    assert resumed.tab_id == original.tab_id
    assert resumed.runtime == original.runtime
    assert resumed.max_quiet_seconds == original.max_quiet_seconds
    assert resumed.subscriptions == original.subscriptions


def test_a_resumed_session_collects_a_return_the_original_session_dispatched(
    tmp_path: Path,
) -> None:
    """The end the restart exists for: the answer is not lost with the orchestrator."""
    herdr = FakeHerdr()
    original = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(original, _request(), herdr=herdr, now=100.0)
    herdr.text = _pane_block(original, "req-1", "the distilled answer")

    del original
    resumed = MIRROR.resume_mirror(tmp_path, run_id=RUN_ID, herdr=herdr)
    assert MIRROR.collect_return(resumed, herdr=herdr, now=110.0).material == "the distilled answer"


def test_resume_refuses_to_guess_between_two_mirrors(tmp_path: Path) -> None:
    _create(tmp_path)
    _create(tmp_path, row_id="mirror-b", nonce="fedcba9876543210")
    with pytest.raises(MIRROR.MirrorNotRegisteredError, match="name the"):
        MIRROR.resume_mirror(tmp_path, run_id=RUN_ID)


def test_resume_refuses_when_the_live_pane_cannot_be_asked_for(tmp_path: Path) -> None:
    """The write-ahead row exists from creation; that is not the same as a live session."""
    wrapper = FakeWrapper(launch_error=RuntimeError("launch exploded"))
    with pytest.raises(RuntimeError):
        _create(tmp_path, wrapper=wrapper)
    herdr = FakeHerdr()
    herdr.snapshot_error = LIFECYCLE.LaunchProtocolError("terminal query failed")
    with pytest.raises(LIFECYCLE.LaunchProtocolError, match="query failed"):
        MIRROR.resume_mirror(tmp_path, run_id=RUN_ID, herdr=herdr)


# =========================================================================================
# Repair: a missing subscription is loud, not silent
# =========================================================================================


def test_a_subscriber_started_without_the_mirrors_subscription_is_refused(
    tmp_path: Path,
) -> None:
    """The cross-unit omission this unit could previously only warn about in prose."""
    session = _create(tmp_path, acknowledge=False)
    other = SUBSCRIBER.output_match_subscription(
        "pane-child", SUBSCRIBER.make_sentinel(RUN_ID, "child-a", "completion", nonce="abc")
    )
    with pytest.raises(MIRROR.MirrorSubscriptionMissingError, match="never wake"):
        MIRROR.acknowledge_subscription(session, [other], now=1.0)
    assert (
        MIRROR.mirror_status(tmp_path, run_id=RUN_ID, row_id=ROW_ID)["subscription_acknowledged"]
        is False
    )


def test_an_unconfirmed_subscription_is_not_reported_as_a_hang(tmp_path: Path) -> None:
    """A mirror nobody is listening to and a hung mirror produce the same silence.

    Reporting the first as the second sends the operator hunting a hang that is not there.
    """
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr, acknowledge=False)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)
    with pytest.raises(MIRROR.MirrorSubscriptionUnconfirmedError, match="not a hang"):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=2.0)

    MIRROR.acknowledge_subscription(session, list(session.subscriptions), now=3.0)
    assert MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=4.0).state == "working"


def test_an_idle_unconfirmed_mirror_is_still_idle(tmp_path: Path) -> None:
    """The confirmation gates the outstanding-request path only; idle is not an alarm state."""
    _create(tmp_path, acknowledge=False)
    assert MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1e6).state == "idle"


# =========================================================================================
# Repair: pane revision distinguishes a thinking mirror from a dead one
# =========================================================================================


def _snapshot(pane_id: str, revision: int | None) -> dict[str, Any]:
    pane: dict[str, Any] = {
        "pane_id": pane_id,
        "tab_id": IDENTITY.tab_id,
        "workspace_id": IDENTITY.workspace_id,
    }
    if revision is not None:
        pane["revision"] = revision
    return {
        "tabs": [
            {
                "label": LIFECYCLE.task_label(RUN_ID, ROW_ID),
                "tab_id": IDENTITY.tab_id,
                "workspace_id": IDENTITY.workspace_id,
            }
        ],
        "panes": [pane],
        "agents": [],
    }


def test_pane_revision_advances_the_clock_and_tells_thinking_from_dead(tmp_path: Path) -> None:
    """The signal the subscription path cannot carry without waking the operator's channel.

    ``register.py`` names herdr's pane-output ``revision`` counter as the feed for this and
    names this unit as its reader. Two mirrors, same silence on the subscription path: the one
    whose pane is still emitting is working, the one whose pane has stopped is a hang.
    """
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr, max_quiet_seconds=100.0)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1_000.0)

    # The first look establishes the baseline and does not advance the clock: a counter is only
    # evidence of emission when there is a previous one to compare it against.
    first = MIRROR.observe_pane_activity(
        tmp_path, run_id=RUN_ID, row_id=ROW_ID, snapshot=_snapshot(session.pane_id, 5), now=1_010.0
    )
    assert first.advanced is False
    assert first.revision == 5

    # Thinking: the pane keeps emitting, so successive ticks keep the clock fed.
    for tick, revision in ((1_050.0, 12), (1_150.0, 47)):
        activity = MIRROR.observe_pane_activity(
            tmp_path,
            run_id=RUN_ID,
            row_id=ROW_ID,
            snapshot=_snapshot(session.pane_id, revision),
            now=tick,
        )
        assert activity.advanced is True
        assert activity.revision == revision
    live = MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1_200.0)
    assert live.state == "working"
    assert live.reference_source == "pane_revision"
    assert live.quiet_seconds == 50.0

    # Dead: the counter stops moving, and the same tick no longer feeds the clock.
    still = MIRROR.observe_pane_activity(
        tmp_path, run_id=RUN_ID, row_id=ROW_ID, snapshot=_snapshot(session.pane_id, 47), now=1_400.0
    )
    assert still.advanced is False
    with pytest.raises(MIRROR.MirrorQuietTooLongError, match="pane_revision"):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1_400.0)


def test_re_observing_an_unchanged_counter_is_not_activity(tmp_path: Path) -> None:
    """Otherwise a supervision loop would keep a dead mirror alive by asking about it."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr, max_quiet_seconds=10.0)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)
    MIRROR.observe_pane_activity(
        tmp_path, run_id=RUN_ID, row_id=ROW_ID, snapshot=_snapshot(session.pane_id, 5), now=2.0
    )
    before = REGISTER.register_path(RUN_ID).read_bytes()
    for tick in (100.0, 200.0, 300.0):
        assert (
            MIRROR.observe_pane_activity(
                tmp_path,
                run_id=RUN_ID,
                row_id=ROW_ID,
                snapshot=_snapshot(session.pane_id, 5),
                now=tick,
            ).advanced
            is False
        )
    assert REGISTER.register_path(RUN_ID).read_bytes() == before
    with pytest.raises(MIRROR.MirrorQuietTooLongError):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=300.0)


def test_a_pane_absent_from_the_snapshot_is_not_invented_as_activity(tmp_path: Path) -> None:
    """Pane absence is a different failure, and one the ordinary divergence machinery reaches."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)
    activity = MIRROR.observe_pane_activity(
        tmp_path,
        run_id=RUN_ID,
        row_id=ROW_ID,
        snapshot={"tabs": [], "panes": [], "agents": []},
        now=2.0,
    )
    assert activity == MIRROR.MirrorActivity(revision=None, advanced=False, advanced_at=None)
    assert "mirror_pane_activity" not in _row(tmp_path)


def test_a_present_pane_without_a_valid_revision_is_not_read_as_silence(tmp_path: Path) -> None:
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)

    with pytest.raises(MIRROR.MirrorError, match="valid output revision"):
        MIRROR.observe_pane_activity(
            tmp_path,
            run_id=RUN_ID,
            row_id=ROW_ID,
            snapshot=_snapshot(session.pane_id, None),
            now=2.0,
        )
    assert "mirror_pane_activity" not in _row(tmp_path)


def test_the_revision_reader_never_reaches_a_wake(tmp_path: Path) -> None:
    """A heartbeat *subscription* would wake the operator's channel on a timer; this does not.

    The reader takes a snapshot, which is why it can feed the clock without going anywhere near
    the subscriber's wake path.
    """
    parameters = inspect.signature(MIRROR.observe_pane_activity).parameters
    assert "snapshot" in parameters
    assert not {"wake_sender", "client", "subscriber", "interaction"} & set(parameters)
    calls = _module_function_calls()["observe_pane_activity"]
    assert "wake_sender" not in calls
    assert "output_match_subscription" not in calls


# =========================================================================================
# Repair: non-finite clock inputs cannot report health
# =========================================================================================


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_quiet_bound_is_refused_at_creation(tmp_path: Path, bad: float) -> None:
    with pytest.raises(MIRROR.MirrorNotArmedError, match="finite"):
        _create(tmp_path, max_quiet_seconds=bad)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_a_non_finite_quiet_bound_on_the_row_is_not_reported_healthy(
    tmp_path: Path, bad: float
) -> None:
    """The affirmative state ``MirrorNotArmedError`` exists to prevent, reached by another door.

    Every ordered comparison with NaN is false, so ``quiet > bound`` is false forever and a
    dead mirror reported ``working`` at one million seconds. Infinity did the same, honestly.
    """
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)
    REGISTER.upsert_row(tmp_path, ROW_ID, {"max_quiet_seconds": bad}, run_id=RUN_ID)
    with pytest.raises(MIRROR.MirrorNotArmedError, match="finite"):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1_000_000.0)


def test_a_non_finite_dispatch_instant_is_not_reported_healthy(tmp_path: Path) -> None:
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)
    row = _row(tmp_path)
    row["mirror_request"]["dispatched_at"] = float("nan")
    REGISTER.upsert_row(tmp_path, ROW_ID, {"mirror_request": row["mirror_request"]}, run_id=RUN_ID)
    with pytest.raises(MIRROR.MirrorNotArmedError, match="finite"):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1_000_000.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_a_non_finite_instant_is_refused_by_every_clock_entry_point(
    tmp_path: Path, bad: float
) -> None:
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    with pytest.raises(MIRROR.MirrorNotArmedError, match="finite"):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=bad)
    with pytest.raises(MIRROR.MirrorNotArmedError, match="finite"):
        MIRROR.dispatch_request(session, _request(), herdr=herdr, now=bad)


@pytest.mark.parametrize("bad", [0, -1, "4096"])
def test_a_zero_or_negative_default_return_bound_is_refused_at_creation(
    tmp_path: Path, bad: Any
) -> None:
    """The charter interpolates this as the session's standing default.

    Zero would tell the mirror its default budget is nothing, making every return that honoured
    the charter oversized.
    """
    with pytest.raises(MIRROR.MirrorError, match="max_return_bytes"):
        _create(tmp_path, max_return_bytes=bad)


# =========================================================================================
# Repair: the read-only contract is observed, even though it cannot be attributed
# =========================================================================================


class MutableFakeGit(FakeGit):
    """A checkout whose repository-visible state the test can move under the mirror."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.paths: set[str] = set()
        self.contents: dict[str, str] = {}

    def changed_paths_baseline(self, _cwd: Path, **_kwargs: Any) -> Any:
        paths = frozenset(self.paths)
        return LIFECYCLE.ChangedPathsBaseline(
            paths, tuple(sorted((p, self.contents.get(p, "v1")) for p in paths))
        )


def test_a_repository_change_during_a_request_is_observed_and_recorded(tmp_path: Path) -> None:
    """Detection was the gap: the mirror declares no artifact, so no scope check ever ran on it."""
    herdr = FakeHerdr()
    git = MutableFakeGit(tmp_path)
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0, git=git)

    git.paths.add("src/touched.py")
    herdr.text = _pane_block(session, "req-1", "a conclusion")
    returned = MIRROR.collect_return(session, herdr=herdr, now=2.0, git=git)

    assert returned.repository_changes == frozenset({"src/touched.py"})
    status = MIRROR.mirror_status(tmp_path, run_id=RUN_ID, row_id=ROW_ID)
    assert status["last_return"]["repository_changes"] == ["src/touched.py"]
    assert status["last_return"]["repository_observed"] is True


def test_an_edit_to_an_already_dirty_file_is_observed(tmp_path: Path) -> None:
    """A path-set comparison alone would miss this; the fingerprints are why it does not."""
    herdr = FakeHerdr()
    git = MutableFakeGit(tmp_path)
    git.paths.add("src/already.py")
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0, git=git)

    git.contents["src/already.py"] = "v2"
    herdr.text = _pane_block(session, "req-1", "a conclusion")
    returned = MIRROR.collect_return(session, herdr=herdr, now=2.0, git=git)
    assert returned.repository_changes == frozenset({"src/already.py"})


def test_a_clean_request_window_reports_no_repository_change(tmp_path: Path) -> None:
    herdr = FakeHerdr()
    git = MutableFakeGit(tmp_path)
    git.paths.add("src/untouched.py")
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0, git=git)
    herdr.text = _pane_block(session, "req-1", "a conclusion")
    returned = MIRROR.collect_return(session, herdr=herdr, now=2.0, git=git)
    assert returned.repository_changes == frozenset()
    MIRROR.assert_no_repository_change(returned)


def test_escalating_an_observed_change_is_the_callers_choice(tmp_path: Path) -> None:
    """Collection reports; escalation is opt-in, because attribution is not established.

    The mirror shares the operator's checkout on purpose -- a mirror reading an isolated
    worktree would describe a repository nobody is working in -- so the operator's own edit
    lands in the same window and failing the return on it would be a false alarm.
    """
    herdr = FakeHerdr()
    git = MutableFakeGit(tmp_path)
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0, git=git)
    git.paths.add("docs/edited.md")
    herdr.text = _pane_block(session, "req-1", "a conclusion")

    returned = MIRROR.collect_return(session, herdr=herdr, now=2.0, git=git)
    with pytest.raises(MIRROR.MirrorWroteRepositoryError, match="not established"):
        MIRROR.assert_no_repository_change(returned)


def test_repository_observation_is_absent_rather_than_faked_without_a_git_adapter(
    tmp_path: Path,
) -> None:
    """A caller that supplies no boundary gets an honest "not observed", not a clean bill."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)
    herdr.text = _pane_block(session, "req-1", "a conclusion")
    MIRROR.collect_return(session, herdr=herdr, now=2.0)
    status = MIRROR.mirror_status(tmp_path, run_id=RUN_ID, row_id=ROW_ID)
    assert status["last_return"]["repository_observed"] is False


# =========================================================================================
# Repair: a counter is only evidence when there is a previous one to compare it against
# =========================================================================================


def test_the_first_look_at_a_counter_does_not_advance_the_clock(tmp_path: Path) -> None:
    """A late first tick used to report a long-dead mirror as ``working``.

    The first observation has nothing to compare against, so treating it as an advance turned a
    supervision loop that started late into a source of health the counter never established.
    It delayed a hang rather than suppressing it, which is why it was survivable -- and it made
    calling the reader strictly worse than not calling it, because the dispatch clock had
    already tripped.
    """
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr, max_quiet_seconds=30.0)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1.0)

    first = MIRROR.observe_pane_activity(
        tmp_path, run_id=RUN_ID, row_id=ROW_ID, snapshot=_snapshot(session.pane_id, 7), now=1e6
    )
    assert first.advanced is False
    assert first.advanced_at is None
    with pytest.raises(MIRROR.MirrorQuietTooLongError, match="dispatch"):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1e6)


def test_a_supervision_loop_that_starts_late_does_not_postpone_the_hang(tmp_path: Path) -> None:
    """A regular supervision loop: the hang must fire on the bound, not one tick later."""
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr, max_quiet_seconds=30.0)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1_000.0)
    for tick in (1_010.0, 1_020.0):
        MIRROR.observe_pane_activity(
            tmp_path,
            run_id=RUN_ID,
            row_id=ROW_ID,
            snapshot=_snapshot(session.pane_id, 4),
            now=tick,
        )
    with pytest.raises(MIRROR.MirrorQuietTooLongError):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1_031.0)


def test_a_counter_that_restarts_re_baselines_instead_of_sticking(tmp_path: Path) -> None:
    """A herdr reconnect restarts the pane's series; the old high-water mark must not stick.

    Previously a decrease wrote nothing at all, so real output stayed invisible until the new
    series climbed past the old maximum. Re-baselining without advancing keeps the safe
    direction -- a restarted pane is not evidence of emission -- while letting the feed recover.
    """
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr, max_quiet_seconds=100.0)
    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=1_000.0)
    for tick, revision in ((1_010.0, 40), (1_020.0, 47)):
        MIRROR.observe_pane_activity(
            tmp_path,
            run_id=RUN_ID,
            row_id=ROW_ID,
            snapshot=_snapshot(session.pane_id, revision),
            now=tick,
        )

    reset = MIRROR.observe_pane_activity(
        tmp_path, run_id=RUN_ID, row_id=ROW_ID, snapshot=_snapshot(session.pane_id, 1), now=1_030.0
    )
    assert reset.advanced is False
    assert _row(tmp_path)["mirror_pane_activity"]["revision"] == 1

    climbing = MIRROR.observe_pane_activity(
        tmp_path, run_id=RUN_ID, row_id=ROW_ID, snapshot=_snapshot(session.pane_id, 2), now=1_040.0
    )
    assert climbing.advanced is True
    live = MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=1_050.0)
    assert live.reference_source == "pane_revision"


def test_a_replacement_subscriber_cannot_inherit_a_dead_acknowledgement(tmp_path: Path) -> None:
    """The acknowledgement is durable; the subscriber process is not.

    A caller presenting a list without the mirror's subscription is evidence the wire is gone,
    so the previous confirmation is retracted rather than left standing for a replacement
    process to inherit.
    """
    herdr = FakeHerdr()
    session = _create(tmp_path, herdr=herdr)
    assert MIRROR.mirror_status(tmp_path, run_id=RUN_ID, row_id=ROW_ID)["subscription_acknowledged"]

    with pytest.raises(MIRROR.MirrorSubscriptionMissingError, match="retracted"):
        MIRROR.acknowledge_subscription(session, [], now=5.0)
    assert (
        MIRROR.mirror_status(tmp_path, run_id=RUN_ID, row_id=ROW_ID)["subscription_acknowledged"]
        is False
    )

    MIRROR.dispatch_request(session, _request(), herdr=herdr, now=6.0)
    with pytest.raises(MIRROR.MirrorSubscriptionUnconfirmedError):
        MIRROR.check_liveness(tmp_path, run_id=RUN_ID, row_id=ROW_ID, now=7.0)


#: Reading requests the fail-closed caps used to refuse. Each was a real refusal of ordinary
#: synthesis work, which is as much a defect in this unit as an accepted declaration.
CAPPED_READING_REQUESTS: dict[str, str] = {
    # 201 lines: one over the old line-sweep cap. Comparing two children's reports is the
    # example this unit uses for work that must leave the operator's channel.
    "a_201_line_comparison": "\n".join(
        f"child report line {index}: the two reports agree on this point" for index in range(201)
    ),
    # 17 starred identifiers: one over the old alias cap, which counted Python and markdown
    # shapes rather than YAML aliases.
    "seventeen_starred_python_names": (
        "Compare how the launcher modules use *args, *kwargs, *values, *items, *rest, *extra, "
        "*params, *opts, *flags, *names, *keys, *vals, *data, *meta, *cfg, *env and *ctx."
    ),
    "seventeen_markdown_emphases": "Summarise the *bounded*, *closed*, *predicate*, *mirror*, "
    "*clock*, *quiet*, *return*, *scan*, *parse*, *safe*, *loader*, *budget*, *depth*, *node*, "
    "*layer*, *region* and *fallback* terms.",
    # 33 short Base64 notes: one over the old decoded-candidate count. A count is not a measure
    # of work; these are 33 tiny payloads.
    "thirty_three_base64_notes": " ".join(
        base64.b64encode(f"note number {index} with enough text to decode".encode()).decode("ascii")
        for index in range(33)
    ),
}


@pytest.mark.parametrize("case", sorted(CAPPED_READING_REQUESTS))
def test_a_bound_sized_to_stop_an_attack_does_not_refuse_ordinary_reading(case: str) -> None:
    """Fail-closed is right; fail-closed at a threshold ordinary prose crosses is not.

    Each of these was refused as unexaminable. The bound was not wrong to exist — it was set
    where reading work lives, and one of them was counting a text shape that this repository's
    own source produces sixty-eight times.
    """
    assert _request(instruction=CAPPED_READING_REQUESTS[case])


def test_a_declaration_past_the_old_line_cap_is_still_parsed() -> None:
    """Removing the cap is only safe if the sweep actually reaches what the cap was hiding.

    With the sweep truncated at two hundred lines this declaration is reached by no loader, and
    the textual fallback is suppressed because a balanced region elsewhere parsed. Asserting the
    *form* is what makes the difference visible: parsed by TOML, not guessed at by a heuristic.
    """
    filler = "\n".join(f"child report line {index}: the reports agree" for index in range(250))
    buried = filler + '\nargv = ["uv", "run", "pytest"]\n'
    assert MIRROR.scan_for_predicate_declaration(buried).form == "toml"
    with pytest.raises(MIRROR.PredicateInMirrorError):
        _request(instruction=buried)


def test_the_whole_documents_this_mirror_exists_to_read_can_be_pasted() -> None:
    """The bluntest version of the same check: the unit's own pages, offered as material."""
    for path in (
        "plugins/orchestrate/references/operator-channel.md",
        "plugins/orchestrate/skills/orchestrate/SKILL.md",
    ):
        text = (ROOT / path).read_text(encoding="utf-8")
        excerpt = text[: MIRROR.MAX_INSTRUCTION_BYTES - 512]
        assert _request(instruction=f"Summarise this page:\n{excerpt}"), path
