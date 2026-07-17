"""Tests for the OutcomeOrchestrator dispatcher seam (U4).

Pins R5 (single dispatcher seam, HALT-not-degrade receipt), R6 (team-execution is the first real
backend), and R23 (a backend that cannot run halts visibly, never a silent substitute) — plus the
team_emitter wiring (R5) and integration with the U3 reconcile loop.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


D = _load("outcome_dispatcher")
ES = _load("execution_spec")
OUTCOME = _load("outcome")
STORE = _load("outcome_store")
SETTLEMENT = _load("dispatch_settlement")
RUN_LEDGER = sys.modules["run_ledger"]


def _req(backend: str, *, outcome_id: str = "ship-x", subplot_id: str = "build") -> Any:
    return SimpleNamespace(
        outcome_id=outcome_id,
        subplot_id=subplot_id,
        title="Build the thing",
        backend=backend,
        repo_root=Path("."),
    )


# --------------------------------------------------------------------------- dispatch (R5/R6)


def test_dispatch_team_execution_mints_leaf_with_return_channel() -> None:
    out = D.dispatch(_req("team-execution"))
    assert out["status"] == "dispatched"
    assert out["backend"] == "team-execution"
    assert out["leaf_saga_id"] == "leaf-ship-x-build"
    assert out["return_channel"] == "/resume leaf-ship-x-build"  # R9 re-entry token out


def test_dispatch_inline_is_available() -> None:
    assert D.dispatch(_req("inline"))["status"] == "dispatched"


def test_dispatch_preserves_optional_settlement_identity() -> None:
    req = _req("inline")
    req.dispatch_id = "outcome:ship-x:frontier:build"
    req.attempt = 2
    req.idempotency_key = "outcome:ship-x:build"

    result = D.dispatch(req)

    assert result["dispatch_id"] == req.dispatch_id
    assert result["attempt"] == 2
    assert result["idempotency_key"] == req.idempotency_key


@pytest.mark.parametrize(
    # The host-dependent backends are unavailable under the conservative DEFAULT_AVAILABLE floor
    # (inline / team-execution / manual). `manual` is now always-available (U9), so it dispatches.
    "backend",
    ["fork", "subagent", "cc-workflows-ultracode", "goal"],
)
def test_dispatch_unavailable_backend_halts_not_substitutes(backend: str) -> None:
    # R5/R23: a chosen-but-unavailable backend HALTS with a visible receipt — never a silent inline.
    out = D.dispatch(_req(backend))
    assert out["status"] == "halt"
    receipt = out["receipt"]
    assert receipt["backend"] == backend
    assert receipt["kind"] == "halt"
    assert "HALT" in receipt["reason"] and "substitute" in receipt["reason"]
    assert receipt["available"] == list(D.DEFAULT_AVAILABLE)


def test_dispatch_unknown_backend_is_rejected() -> None:
    with pytest.raises(D.DispatcherError, match="executor menu"):
        D.dispatch(_req("magic-backend"))


def test_custom_available_set() -> None:
    # If team-execution is not in the available set, it too halts (the seam is data-driven).
    assert D.dispatch(_req("team-execution"), available=("inline",))["status"] == "halt"


# --------------------------------------------------------------------------- make_dispatcher adapter


def test_make_dispatcher_returns_leaf_id_on_dispatch() -> None:
    disp = D.make_dispatcher()
    assert disp(_req("team-execution")) == "leaf-ship-x-build"


def test_make_dispatcher_raises_halt_with_receipt() -> None:
    disp = D.make_dispatcher()
    with pytest.raises(D.BackendHaltError) as exc:
        disp(_req("fork"))
    assert exc.value.receipt.backend == "fork"
    assert exc.value.receipt.subplot_id == "build"


def test_make_dispatcher_holds_lease_across_backend_settlement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authority = D.fleet_commons_shim.load("lease_broker")
    selected = authority.LeaseBroker(tmp_path / "authority")
    original_dispatch = D.dispatch

    def observing_dispatch(req: Any, *, available: Any) -> dict[str, Any]:
        live = selected.inspect()["leases"]
        assert len(live) == 1
        assert live[0]["session_id"] == "outcome:ship-x"
        assert live[0]["mutation"] == "none"
        return original_dispatch(req, available=available)

    monkeypatch.setattr(D, "dispatch", observing_dispatch)
    dispatcher = D.make_dispatcher(lease_authority=selected)

    assert dispatcher(_req("inline")) == "leaf-ship-x-build"
    assert selected.inspect()["leases"] == []


def test_make_dispatcher_refuses_capacity_before_backend_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authority = D.fleet_commons_shim.load("lease_broker")
    policy = D.fleet_commons_shim.load("concurrency_policy")
    selected = authority.LeaseBroker(tmp_path / "authority")
    limits = policy.AdmissionLimits()
    for index in range(limits.max_concurrent):
        selected.acquire_agent(
            owner_id=f"owner-{index}",
            session_id="outcome:ship-x",
            policy_sha256=limits.policy_sha256(),
            session_limit=limits.max_concurrent,
            aggregate_limit=limits.aggregate_max_concurrent,
            mutation="none",
            resource_ref={"logical_unit_id": f"existing-{index}"},
        )
    monkeypatch.setattr(
        D,
        "dispatch",
        lambda *_args, **_kwargs: pytest.fail("capacity denial must precede backend dispatch"),
    )

    with pytest.raises(D.DispatcherError, match="lease admission refused"):
        D.make_dispatcher(lease_authority=selected)(_req("inline"))


# --------------------------------------------------------------------------- team_emitter wiring (R5)


def _execution_spec_dict() -> dict[str, Any]:
    return {
        "name": "leaf-plan",
        "description": "a leaf plan",
        "repo": "/tmp/repo",
        "units": [
            {"unit_id": "U1", "label": "preflight", "tier": {"model": "haiku", "effort": "low"}},
            {
                "unit_id": "U2",
                "label": "build",
                "tier": {"model": "sonnet", "effort": "high"},
                "depends_on": ["U1"],
            },
        ],
    }


def test_team_execution_artifact_wires_team_emitter() -> None:
    spec = ES.ExecutionSpec.from_dict(_execution_spec_dict())
    art = D.team_execution_artifact(spec)
    assert "Team Structure" in art  # produced through recompile_for_tier's team_emitter leg (R5)
    assert "U1" in art and "U2" in art  # units preserved (by unit id)


# --------------------------------------------------------------------------- integration with advance


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    common = tmp_path / ".git"
    common.mkdir()
    monkeypatch.setattr(
        OUTCOME.outcome_store.subprocess,
        "run",
        lambda args, **kw: SimpleNamespace(returncode=0, stdout=str(common) + "\n", stderr=""),
    )
    return tmp_path


def test_advance_dispatches_team_execution_node(repo: Path) -> None:
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "team-execution"}],
    )
    result = OUTCOME.advance(repo, "ship-x", dispatcher=D.make_dispatcher())
    assert result.dispatched == ["build"]
    assert OUTCOME.attend(repo, "ship-x", "build") == "/resume leaf-ship-x-build"


def test_settlement_manifest_and_spawn_precede_outcome_dispatch(repo: Path) -> None:
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "team-execution"}],
    )
    ledger = RUN_LEDGER.RunLedger(repo / "settlement" / "facts.jsonl")
    dispatch_id, _units = SETTLEMENT.outcome_frontier_identity("ship-x", ["build"])

    def _dispatcher(req: Any) -> str:
        events = [
            record["event"]
            for record in RUN_LEDGER.read_facts(ledger)
            if record.get("dispatch_id") == dispatch_id
        ]
        assert events == ["manifest", "spawn"]
        return "leaf-ship-x-build"

    result = OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=_dispatcher,
        settlement_ledger=ledger,
        now=lambda: 1_700_000_000.0,
    )
    assert result.dispatched == ["build"]
    assert SETTLEMENT.open_positions(ledger)[0]["unit_id"] == "build"


def test_unexpected_dispatcher_crash_leaves_one_open_settlement_position(repo: Path) -> None:
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "team-execution"}],
    )
    ledger = RUN_LEDGER.RunLedger(repo / "settlement" / "facts.jsonl")
    dispatch_id, _units = SETTLEMENT.outcome_frontier_identity("ship-x", ["build"])

    def _crash(_req: Any) -> str:
        raise RuntimeError("unexpected dispatcher failure")

    with pytest.raises(RuntimeError, match="unexpected dispatcher failure"):
        OUTCOME.advance(
            repo,
            "ship-x",
            dispatcher=_crash,
            holder="crashed-dispatcher",
            settlement_ledger=ledger,
            now=lambda: 1_700_000_000.0,
        )

    records = [
        record
        for record in RUN_LEDGER.read_facts(ledger)
        if record.get("dispatch_id") == dispatch_id
    ]
    assert [record["event"] for record in records] == ["manifest", "spawn"]
    assert SETTLEMENT.open_positions(ledger) == [
        {
            "dispatch_id": dispatch_id,
            "unit_id": "build",
            "attempt": 1,
            "idempotency_key": "outcome:ship-x:build",
            "classification": "open",
        }
    ]


def test_crash_replay_preserves_backend_settlement_identity(repo: Path) -> None:
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "team-execution"}],
    )
    ledger = RUN_LEDGER.RunLedger(repo / "settlement" / "facts.jsonl")
    dispatch_id, _units = SETTLEMENT.outcome_frontier_identity("ship-x", ["build"])
    seen: list[Any] = []

    def _crash(req: Any) -> str:
        seen.append(req)
        raise RuntimeError("backend accepted launch before coordinator crash")

    with pytest.raises(RuntimeError, match="accepted launch"):
        OUTCOME.advance(
            repo,
            "ship-x",
            dispatcher=_crash,
            holder="replay-holder",
            settlement_ledger=ledger,
            now=lambda: 1_700_000_000.0,
        )

    def _replay(req: Any) -> str:
        seen.append(req)
        return "leaf-ship-x-build"

    replay = OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=_replay,
        holder="replay-holder",
        settlement_ledger=ledger,
        now=lambda: 1_700_000_001.0,
    )

    assert replay.dispatched == ["build"]
    assert [(req.dispatch_id, req.attempt, req.idempotency_key) for req in seen] == [
        (dispatch_id, 1, "outcome:ship-x:build"),
        (dispatch_id, 1, "outcome:ship-x:build"),
    ]
    assert len(SETTLEMENT.open_positions(ledger)) == 1


def test_outcome_writes_one_complete_manifest_for_the_ready_frontier(repo: Path) -> None:
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[
            {"subplot_id": "a", "title": "A", "backend": "team-execution"},
            {"subplot_id": "b", "title": "B", "backend": "team-execution"},
        ],
    )
    ledger = RUN_LEDGER.RunLedger(repo / "settlement" / "facts.jsonl")
    dispatch_id, _units = SETTLEMENT.outcome_frontier_identity("ship-x", ["a", "b"])
    seen: list[str] = []

    def _dispatcher(req: Any) -> str:
        seen.append(req.subplot_id)
        records = [
            record
            for record in RUN_LEDGER.read_facts(ledger)
            if record.get("dispatch_id") == dispatch_id
        ]
        manifests = [record for record in records if record.get("event") == "manifest"]
        assert len(manifests) == 1
        assert [unit["unit_id"] for unit in manifests[0]["units"]] == ["a", "b"]
        assert [record["unit_id"] for record in records if record.get("event") == "spawn"] == seen
        return f"leaf-ship-x-{req.subplot_id}"

    result = OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=_dispatcher,
        settlement_ledger=ledger,
        now=lambda: 1_700_000_000.0,
    )

    assert result.dispatched == ["a", "b"]
    assert {item["dispatch_id"] for item in SETTLEMENT.open_positions(ledger)} == {dispatch_id}


def test_pre_feature_inflight_commit_is_not_added_to_a_settlement_cohort(repo: Path) -> None:
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[
            {"subplot_id": "legacy", "title": "Legacy", "backend": "team-execution"},
            {
                "subplot_id": "next",
                "title": "Next",
                "backend": "team-execution",
                "depends_on": ["legacy"],
            },
        ],
    )
    store = STORE.Store.for_outcome("ship-x", repo).ensure()
    STORE.append_ledger(
        store,
        {
            "phase": "commit",
            "kind": "dispatch",
            "key": "dispatch:legacy",
            "subplot_id": "legacy",
            "leaf_saga_id": "leaf-ship-x-legacy",
        },
    )
    ledger = RUN_LEDGER.RunLedger(repo / "settlement" / "facts.jsonl")

    first = OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=lambda _req: pytest.fail("legacy dispatch must not be repeated"),
        settlement_ledger=ledger,
        now=lambda: 1_700_000_000.0,
    )
    assert first.dispatched == []
    assert RUN_LEDGER.read_facts(ledger) == []

    STORE.write_completion_event(
        store,
        STORE.CompletionEvent(
            subplot_id="legacy",
            state="done",
            idempotency_key="github-legacy",
            payload={"canonical": True},
        ),
    )
    second = OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=lambda req: f"leaf-ship-x-{req.subplot_id}",
        settlement_ledger=ledger,
        now=lambda: 1_700_000_001.0,
    )
    assert second.dispatched == ["next"]
    manifests = [
        record for record in RUN_LEDGER.read_facts(ledger) if record.get("event") == "manifest"
    ]
    assert [[unit["unit_id"] for unit in record["units"]] for record in manifests] == [["next"]]


def test_outcome_rate_limit_settles_then_next_advance_claims_retry(repo: Path) -> None:
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "team-execution"}],
    )
    ledger = RUN_LEDGER.RunLedger(repo / "settlement" / "facts.jsonl")
    dispatch_id, _units = SETTLEMENT.outcome_frontier_identity("ship-x", ["build"])
    first = OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=_rate_limited_dispatcher(),
        settlement_ledger=ledger,
        now=lambda: 1_700_000_000.0,
    )
    assert first.retriable == ["build"]
    assert SETTLEMENT.dead_letters(ledger, dispatch_id)[0].next_attempt == 2

    def _second(req: Any) -> str:
        spawns = [
            record
            for record in RUN_LEDGER.read_facts(ledger)
            if record.get("dispatch_id") == dispatch_id and record.get("event") == "spawn"
        ]
        assert [record["attempt"] for record in spawns] == [1, 2]
        assert {record["idempotency_key"] for record in spawns} == {"outcome:ship-x:build"}
        return "leaf-ship-x-build"

    second = OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=_second,
        settlement_ledger=ledger,
        now=lambda: 1_700_000_001.0,
    )
    assert second.dispatched == ["build"]
    assert SETTLEMENT.open_positions(ledger)[0]["attempt"] == 2


def test_outcome_casualty_blocks_new_cohort_but_allows_bound_retry(repo: Path) -> None:
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[
            {"subplot_id": "a", "title": "A", "backend": "team-execution"},
            {"subplot_id": "b", "title": "B", "backend": "team-execution"},
            {
                "subplot_id": "c",
                "title": "C",
                "backend": "team-execution",
                "depends_on": ["b"],
            },
        ],
    )
    ledger = RUN_LEDGER.RunLedger(repo / "settlement" / "facts.jsonl")
    dispatch_id, _units = SETTLEMENT.outcome_frontier_identity("ship-x", ["a", "b"])

    def _first(req: Any) -> str:
        if req.subplot_id == "a":
            return str(_rate_limited_dispatcher()(req))
        return "leaf-ship-x-b"

    first = OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=_first,
        settlement_ledger=ledger,
        now=lambda: 1_700_000_000.0,
    )
    assert first.retriable == ["a"]
    assert first.dispatched == ["b"]

    SETTLEMENT.settle_attempt(
        ledger,
        subplot_id="b",
        at="2023-11-14T22:13:21Z",
        dispatch_id=dispatch_id,
        unit_id="b",
        attempt=1,
        classification=SETTLEMENT.DELIVERED,
        reason="canonical completion",
        evidence_ref="github-completion",
        evidence_sha256="b" * 64,
    )
    store = STORE.Store.for_outcome("ship-x", repo).ensure()
    STORE.write_completion_event(
        store,
        STORE.CompletionEvent(
            subplot_id="b",
            state="done",
            idempotency_key="github-b",
            payload={"canonical": True},
        ),
    )

    second_calls: list[str] = []

    def _second(req: Any) -> str:
        second_calls.append(req.subplot_id)
        return f"leaf-ship-x-{req.subplot_id}"

    second = OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=_second,
        settlement_ledger=ledger,
        now=lambda: 1_700_000_001.0,
    )
    assert second_calls == ["a"]
    assert second.dispatched == ["a"]
    assert any(
        item["kind"] == "settlement-halt" and item["subplot_id"] == "c" for item in second.halted
    )

    SETTLEMENT.settle_attempt(
        ledger,
        subplot_id="a",
        at="2023-11-14T22:13:22Z",
        dispatch_id=dispatch_id,
        unit_id="a",
        attempt=2,
        classification=SETTLEMENT.DELIVERED,
        reason="retry completed",
        evidence_ref="github-completion",
        evidence_sha256="a" * 64,
    )
    STORE.write_completion_event(
        store,
        STORE.CompletionEvent(
            subplot_id="a",
            state="done",
            idempotency_key="github-a",
            payload={"canonical": True},
        ),
    )
    assert not SETTLEMENT.settlement_report(ledger, dispatch_id).halt_required

    third = OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=D.make_dispatcher(),
        settlement_ledger=ledger,
        now=lambda: 1_700_000_002.0,
    )
    assert third.dispatched == ["c"]


def test_outcome_retry_exhaustion_releases_lease_and_continues_independent_leaf(
    repo: Path,
) -> None:
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[
            {"subplot_id": "capped", "title": "Capped", "backend": "team-execution"},
            {
                "subplot_id": "independent",
                "title": "Independent",
                "backend": "team-execution",
            },
        ],
    )
    ledger = RUN_LEDGER.RunLedger(repo / "settlement" / "facts.jsonl")

    def only_capped(_spec: Any, _store: Any) -> Any:
        return lambda sid: sid == "capped"

    for tick in range(3):
        result = OUTCOME.advance(
            repo,
            "ship-x",
            dispatcher=_rate_limited_dispatcher(),
            gate_factory=only_capped,
            settlement_ledger=ledger,
            now=lambda tick=tick: 1_700_000_000.0 + tick,
        )
        assert result.retriable == ["capped"]

    calls: list[str] = []

    def _independent(req: Any) -> str:
        calls.append(req.subplot_id)
        return f"leaf-ship-x-{req.subplot_id}"

    result = OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=_independent,
        gate_factory=lambda _spec, _store: lambda _sid: True,
        settlement_ledger=ledger,
        now=lambda: 1_700_000_004.0,
    )

    assert calls == ["independent"]
    assert result.dispatched == ["independent"]
    assert any(
        item["kind"] == "settlement-halt" and item["subplot_id"] == "capped"
        for item in result.halted
    )
    assert (
        STORE.read_lease(STORE.Store.for_outcome("ship-x", repo).ensure(), "dispatch-capped")
        is None
    )
    intents_before = [
        record
        for record in STORE.read_ledger(STORE.Store.for_outcome("ship-x", repo).ensure())
        if record.get("phase") == "intent" and record.get("subplot_id") == "capped"
    ]

    again = OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=lambda _req: pytest.fail("an exhausted unit must not be dispatched"),
        gate_factory=lambda _spec, _store: lambda _sid: True,
        settlement_ledger=ledger,
        now=lambda: 1_700_000_005.0,
    )
    intents_after = [
        record
        for record in STORE.read_ledger(STORE.Store.for_outcome("ship-x", repo).ensure())
        if record.get("phase") == "intent" and record.get("subplot_id") == "capped"
    ]
    assert len(intents_after) == len(intents_before)
    assert any(item["subplot_id"] == "capped" for item in again.halted)


def test_outcome_harvest_settles_open_attempt_from_canonical_evidence(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "team-execution"}],
    )
    ledger = RUN_LEDGER.RunLedger(repo / "settlement" / "facts.jsonl")
    dispatch_id, _units = SETTLEMENT.outcome_frontier_identity("ship-x", ["build"])
    OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=D.make_dispatcher(),
        settlement_ledger=ledger,
        now=lambda: 1_700_000_000.0,
    )
    orchestrator = sys.modules.get("outcome_orchestrator") or _load("outcome_orchestrator")

    def _harvest(_spec: Any, *, store: Any, **_kwargs: Any) -> list[str]:
        STORE.write_completion_event(
            store,
            STORE.CompletionEvent(
                subplot_id="build",
                state="done",
                idempotency_key="github-build",
                payload={"canonical": True},
            ),
        )
        return ["build"]

    monkeypatch.setattr(orchestrator, "harvest", _harvest)
    harvester = OUTCOME.production_harvester(
        repo, settlement_ledger=ledger, now=lambda: 1_700_000_002.0
    )
    assert harvester(spec, STORE.Store.for_outcome("ship-x", repo).ensure()) == ["build"]
    report = SETTLEMENT.settlement_report(ledger, dispatch_id)
    assert report.entries[0].classification == "delivered"
    assert report.entries[0].evidence_ref == "outcome-completion:done"
    settlement = next(
        record
        for record in RUN_LEDGER.read_facts(ledger)
        if record.get("dispatch_id") == dispatch_id and record.get("event") == "settle"
    )
    assert settlement["at"] == "2023-11-14T22:13:22Z"
    completion = STORE.read_completion_events(STORE.Store.for_outcome("ship-x", repo), "build")[-1]
    assert settlement["evidence_sha256"] == SETTLEMENT.evidence_digest(completion.to_dict())


@pytest.mark.parametrize("state", ["failed", "rejected", "stalled"])
def test_outcome_harvest_negative_terminal_settles_fail_closed_and_enters_dlq(
    repo: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    spec = OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "team-execution"}],
    )
    ledger = RUN_LEDGER.RunLedger(repo / "settlement" / "facts.jsonl")
    dispatch_id, _units = SETTLEMENT.outcome_frontier_identity("ship-x", ["build"])
    OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=D.make_dispatcher(),
        settlement_ledger=ledger,
        now=lambda: 1_700_000_000.0,
    )
    store = STORE.Store.for_outcome("ship-x", repo).ensure()
    event = STORE.CompletionEvent(
        subplot_id="build",
        state=state,
        idempotency_key=f"terminal:build:{state}",
        payload={"reason": "terminal evidence"},
    )
    STORE.write_completion_event(store, event)
    orchestrator = sys.modules.get("outcome_orchestrator") or _load("outcome_orchestrator")
    monkeypatch.setattr(orchestrator, "harvest", lambda *args, **kwargs: [])

    OUTCOME.production_harvester(repo, settlement_ledger=ledger, now=lambda: 1_700_000_002.0)(
        spec, store
    )

    settlement = next(
        record
        for record in RUN_LEDGER.read_facts(ledger)
        if record.get("dispatch_id") == dispatch_id and record.get("event") == "settle"
    )
    assert settlement["classification"] == SETTLEMENT.SILENT_NOOP
    assert settlement["reason"] == f"outcome terminal completion fail-closed: {state}"
    assert "evidence_ref" not in settlement
    assert "evidence_sha256" not in settlement
    assert SETTLEMENT.dead_letters(ledger, dispatch_id)[0].unit_id == "build"


def test_outcome_harvest_reconciles_prior_completion_when_nothing_is_new(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "team-execution"}],
    )
    ledger = RUN_LEDGER.RunLedger(repo / "settlement" / "facts.jsonl")
    dispatch_id, _units = SETTLEMENT.outcome_frontier_identity("ship-x", ["build"])
    OUTCOME.advance(
        repo,
        "ship-x",
        dispatcher=D.make_dispatcher(),
        settlement_ledger=ledger,
        now=lambda: 1_700_000_000.0,
    )
    store = STORE.Store.for_outcome("ship-x", repo).ensure()
    STORE.write_completion_event(
        store,
        STORE.CompletionEvent(
            subplot_id="build",
            state="done",
            idempotency_key="already-canonical",
            payload={"canonical": True},
        ),
    )
    orchestrator = sys.modules.get("outcome_orchestrator") or _load("outcome_orchestrator")
    monkeypatch.setattr(orchestrator, "harvest", lambda *args, **kwargs: [])

    harvester = OUTCOME.production_harvester(
        repo, settlement_ledger=ledger, now=lambda: 1_700_000_002.0
    )
    assert harvester(spec, store) == []
    assert (
        SETTLEMENT.settlement_report(ledger, dispatch_id).entries[0].classification == "delivered"
    )
    assert len(STORE.read_completion_events(store, "build")) == 1


def test_advance_halts_visibly_on_unavailable_backend_no_silent_substitute(repo: Path) -> None:
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "fork"}],
    )
    # The reconcile loop catches the HALT per-leaf: surfaced in result.halted (visible), nothing
    # dispatched, nothing silently substituted to inline.
    result = OUTCOME.advance(repo, "ship-x", dispatcher=D.make_dispatcher())
    assert result.dispatched == []
    assert len(result.halted) == 1 and result.halted[0]["backend"] == "fork"
    store = STORE.Store.for_outcome("ship-x", repo)
    assert STORE.completed_subplots(store) == set()


def test_halt_does_not_leak_dispatch_lease_resurfaces_each_advance(repo: Path) -> None:
    # P1 regression: a HALT must release the per-subplot dispatch lock so the NEXT advance re-attempts
    # and re-surfaces the HALT, rather than the leaked lease silently masking it for the lease TTL.
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "fork"}],
    )
    r1 = OUTCOME.advance(repo, "ship-x", dispatcher=D.make_dispatcher())
    r2 = OUTCOME.advance(repo, "ship-x", dispatcher=D.make_dispatcher())
    assert len(r1.halted) == 1 and len(r2.halted) == 1  # re-surfaced, not masked by a leaked lease


def test_halt_does_not_starve_other_runnable_leaves(repo: Path) -> None:
    # P2 regression: one HALT leaf must NOT abort the whole tick — independent runnable leaves still
    # dispatch in the same advance.
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[
            {"subplot_id": "a", "title": "A", "backend": "team-execution"},
            {"subplot_id": "b", "title": "B", "backend": "fork"},
        ],
    )
    result = OUTCOME.advance(repo, "ship-x", dispatcher=D.make_dispatcher())
    assert result.dispatched == ["a"]  # the runnable leaf dispatched despite b's HALT
    assert [h["subplot_id"] for h in result.halted] == ["b"]


# --------------------------------------------------------------------------- #348/R4/KTD4: 429 retriable-pending


def _rate_limited_dispatcher(retry_after: float | None = 1.0) -> Any:
    """A dispatcher that always 429s (a restricted/engine-bridge dispatcher raising the 429-shape)."""

    def _disp(req: Any) -> str:
        raise D.BackendRateLimitError(
            D.RateLimitReceipt(
                outcome_id=req.outcome_id,
                subplot_id=req.subplot_id,
                backend=req.backend,
                reason="rate limited (429)",
                retry_after=retry_after,
            )
        )

    return _disp


def test_advance_classifies_429_as_retriable_pending_not_halt(repo: Path) -> None:
    # A 429 during dispatch is TRANSIENT: surfaced in result.retriable (NOT halted), nothing
    # dispatched, and NO commit record written -> the leaf's derived state stays ready (KTD4).
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "team-execution"}],
    )
    result = OUTCOME.advance(repo, "ship-x", dispatcher=_rate_limited_dispatcher())
    assert result.retriable == ["build"]
    assert result.dispatched == []
    assert result.halted == []  # a 429 is NOT operator-attention-worthy, unlike a HALT
    store = STORE.Store.for_outcome("ship-x", repo)
    # Derived-on-read: no committed dispatch record -> the leaf is still on the ready frontier.
    assert OUTCOME._dispatch_records(store) == {}
    assert STORE.completed_subplots(store) == set()


def test_retriable_leaf_is_re_picked_on_the_next_advance_call(repo: Path) -> None:
    # The re-pick contract (KTD4): a 429'd leaf that is left ready dispatches on the very next
    # advance() call once the backend is no longer rate-limited -- no operator action, no state edit.
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "team-execution"}],
    )
    r1 = OUTCOME.advance(repo, "ship-x", dispatcher=_rate_limited_dispatcher())
    assert r1.retriable == ["build"] and r1.dispatched == []
    r2 = OUTCOME.advance(repo, "ship-x", dispatcher=D.make_dispatcher())
    assert r2.dispatched == ["build"] and r2.retriable == []


def test_advance_loop_does_not_hammer_a_rate_limited_backend_within_a_call(repo: Path) -> None:
    # The per-call de-hammer guard: within one loop=True advance() a 429'd leaf is attempted at most
    # once, then skipped for the rest of the call while other leaves keep the loop ticking.
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[
            {"subplot_id": "a", "title": "A", "backend": "team-execution"},
            {"subplot_id": "b", "title": "B", "backend": "team-execution"},
        ],
    )
    calls: dict[str, int] = {"a": 0, "b": 0}

    def _disp(req: Any) -> str:
        calls[req.subplot_id] += 1
        if req.subplot_id == "a":
            raise D.BackendRateLimitError(
                D.RateLimitReceipt(
                    outcome_id=req.outcome_id,
                    subplot_id=req.subplot_id,
                    backend=req.backend,
                    reason="429",
                    retry_after=1.0,
                )
            )
        return f"leaf-{req.outcome_id}-{req.subplot_id}"

    result = OUTCOME.advance(repo, "ship-x", dispatcher=_disp, loop=True)
    assert result.dispatched == ["b"]
    assert result.retriable == ["a"]
    assert result.ticks >= 2  # the loop ticked again after b dispatched...
    assert calls["a"] == 1  # ...but a was NOT re-attempted (skipped via retriable_seen)


def test_make_dispatcher_translates_rate_limited_status_to_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Production-capable translation: a `rate_limited` dispatch result surfaces as BackendRateLimitError
    # (mirroring the halt branch), carrying the Retry-After hint. No in-scope backend emits this yet
    # (agy/codex bridge deferred, KTD2) -- this proves the dispatcher is CAPABLE the instant one does.
    receipt = D.RateLimitReceipt(
        outcome_id="ship-x",
        subplot_id="build",
        backend="team-execution",
        reason="429",
        retry_after=2.5,
    ).to_dict()
    monkeypatch.setattr(
        D, "dispatch", lambda req, **kw: {"status": "rate_limited", "receipt": receipt}
    )
    with pytest.raises(D.BackendRateLimitError) as exc:
        D.make_dispatcher()(_req("team-execution"))
    assert exc.value.receipt.retry_after == 2.5
    assert exc.value.receipt.to_dict()["kind"] == "rate_limited"


def test_cli_advance_uses_the_real_backend_seam(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # R5: the production /outcome advance routes through the real seam, not the U3 record-only default.
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "fork"}],
    )
    # R20 approval gate is upstream of the backend HALT — approve the frontier first so the leaf
    # actually reaches the dispatcher seam (an unapproved leaf is gated, never HALTed).
    assert OUTCOME.main(["--repo-root", str(repo), "approve", "ship-x"]) == 0
    capsys.readouterr()
    rc = OUTCOME.main(["--repo-root", str(repo), "advance", "ship-x"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert (
        out["dispatched"] == [] and len(out["halted"]) == 1
    )  # the seam HALTed fork, didn't dispatch


# --------------------------------------------------------------------------- CLI


def test_cli_dispatch_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    assert D.main(["ship-x", "build", "team-execution"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "dispatched" and out["return_channel"] == "/resume leaf-ship-x-build"
    assert D.main(["ship-x", "build", "fork"]) == 0
    halt = json.loads(capsys.readouterr().out)
    assert halt["status"] == "halt"


# --------------------------------------------------------- sandbox enforceability (U3)
# The resolved backend must be able to enforce the leaf's declared sandbox, or dispatch HALTs
# with the offending axis named -- never silently runs the leaf uncontained (R4).

OS = _load("outcome_spec")


def _req_sandbox(backend: str, sandbox: Any, **kw: Any) -> Any:
    req = _req(backend, **kw)
    req.sandbox = sandbox
    return req


def test_dispatch_halts_when_backend_cannot_enforce_sandbox() -> None:
    # inline cannot provide owned-worktree (halt-v1) -> halt receipt naming the axis.
    sb = OS.Sandbox.from_dict("sandboxed-mutate", "w")
    out = D.dispatch(_req_sandbox("inline", sb))
    assert out["status"] == "halt"
    assert "workspace_isolation" in out["receipt"]["reason"]
    assert out["receipt"]["backend"] == "inline"


def test_dispatch_enforceable_sandbox_dispatches() -> None:
    sb = OS.Sandbox.from_dict("read-only-verify", "w")
    assert D.dispatch(_req_sandbox("inline", sb))["status"] == "dispatched"


def test_dispatch_no_sandbox_is_backward_compatible() -> None:
    # A req without a sandbox attribute dispatches exactly as before (getattr default None).
    assert D.dispatch(_req("inline"))["status"] == "dispatched"


def test_make_dispatcher_raises_backend_halt_on_unenforceable_sandbox() -> None:
    # The halt flows through the make_dispatcher seam outcome.advance uses (BackendHaltError).
    sb = OS.Sandbox.from_dict("sandboxed-mutate", "w")
    dispatcher = D.make_dispatcher()
    with pytest.raises(D.BackendHaltError) as exc:
        dispatcher(_req_sandbox("inline", sb))
    assert "workspace_isolation" in exc.value.receipt.reason


def test_frontier_budget_downgrade_restamps_backends_enumeration() -> None:
    """KTD4 compat contract: the frontier-budget downgrade re-stamps the leaf recommender's
    full-enumeration ``backends`` payload so the authoritative enumeration never contradicts the
    downgraded ``recommended``.

    A wide frontier turns a ``cc-workflows-ultracode`` leaf recommendation into ``team-execution``
    (a dynamic workflow per leaf is expensive). The ``backends`` list must follow: team-execution
    reads ``recommended``, ultracode reads ``alternative`` carrying the ``budget_note`` reason.
    """
    # Narrow frontier: no downgrade, ultracode stays recommended in both keys.
    narrow = D.recommend_outcome_backend(frontier_width=1, broad_independent_fanout=True)
    assert narrow["recommended"] == "cc-workflows-ultracode"
    narrow_statuses = {b["backend"]: b["status"] for b in narrow["backends"]}
    assert narrow_statuses["cc-workflows-ultracode"] == "recommended"

    # Wide frontier: budget downgrade to team-execution AND the enumeration is re-stamped.
    wide = D.recommend_outcome_backend(frontier_width=20, broad_independent_fanout=True)
    assert wide["recommended"] == "team-execution"
    assert "budget_note" in wide
    assert "omit_ultracode" not in wide
    statuses = {b["backend"]: b["status"] for b in wide["backends"]}
    assert statuses == {
        "inline": "alternative",
        "team-execution": "recommended",
        "cc-workflows-ultracode": "alternative",
    }
    # Exactly one recommended entry and it matches the downgraded recommended key.
    recommended_entries = [b for b in wide["backends"] if b["status"] == "recommended"]
    assert len(recommended_entries) == 1
    assert recommended_entries[0]["backend"] == wide["recommended"]
    # The ultracode entry's note carries the budget_note reason.
    ultra_note = next(
        b["note"] for b in wide["backends"] if b["backend"] == "cc-workflows-ultracode"
    )
    assert ultra_note == wide["budget_note"]


# --------------------------------------------------------------------------- #373: captured run-start
# posture enforced at the dispatch seam (T8-F6-8 backends/degrade + T8-F5-7 spend envelope).

IE = _load("intent_envelope")
OC = _load("outcome_costs")


def _intent_373(**extra: Any) -> dict[str, Any]:
    """A valid committed intent built through the production capture path, plus #373 fields."""
    data: dict[str, Any] = IE.apply_answers({"run_mode": "attended"}).to_dict()
    data.update(extra)
    # Round-trip through the canonical schema so a mis-shaped fixture fails HERE, not downstream.
    return dict(IE.IntentEnvelope.from_dict(data).to_dict())


def test_ac1_captured_posture_is_consumed_at_the_seam_not_re_derived(repo: Path) -> None:
    """AC1: backends_permitted + degrade_policy captured ONCE at run start decide the seam —
    dispatching a leaf whose backend is unmet reads the captured posture (no runtime
    ``available`` flags are passed at all, so the decision can only have come from the spec)."""
    OUTCOME.start(
        repo,
        "oc373",
        "Objective",
        nodes=[{"subplot_id": "build", "title": "B", "backend": "team-execution"}],
        intent=_intent_373(backends_permitted=["inline"]),
    )
    result = OUTCOME.advance(repo, "oc373")
    assert result.dispatched == []
    assert len(result.halted) == 1
    receipt = result.halted[0]
    assert receipt["backend"] == "team-execution"
    # The receipt's effective menu IS the captured set (captured ∩ runtime, runtime absent).
    assert receipt["available"] == ["inline"]
    assert "captured run-start posture" in receipt["reason"]


def test_ac2_unmet_prerequisite_with_no_degrade_posture_halts_by_default(repo: Path) -> None:
    """AC2: an unmet host prerequisite with NO degrade posture captured -> HALT by default,
    surfacing through the same BackendHaltError path the existing mechanism uses."""
    # Unit half: a restricted caller through make_dispatcher raises the SAME typed halt.
    envelope = IE.IntentEnvelope.from_dict(_intent_373(backends_permitted=["inline"]))
    effective = D.effective_available(envelope.backends_permitted, None)
    dispatcher = D.make_dispatcher(available=effective)
    with pytest.raises(D.BackendHaltError) as exc:
        dispatcher(_req("team-execution"))
    assert exc.value.receipt.backend == "team-execution"
    assert exc.value.receipt.available == ("inline",)

    # End-to-end half: the reconcile loop records the halt visibly, dispatches nothing.
    OUTCOME.start(
        repo,
        "oc373",
        "Objective",
        nodes=[{"subplot_id": "build", "title": "B", "backend": "team-execution"}],
        intent=_intent_373(backends_permitted=["inline"]),
    )
    result = OUTCOME.advance(repo, "oc373", attending=False)  # even unattended: no posture -> HALT
    assert result.dispatched == [] and result.degraded == []
    assert len(result.halted) == 1


def test_ac3_captured_posture_degrades_exactly_one_rung(repo: Path) -> None:
    """AC3 control: with operator_away_one_rung captured and the IMMEDIATE lower rung
    permitted, an autonomous+away leaf degrades exactly one DEGRADE_LADDER rung."""
    OUTCOME.start(
        repo,
        "oc373",
        "Objective",
        nodes=[{"subplot_id": "build", "title": "B", "backend": "cc-workflows-ultracode"}],
        intent=_intent_373(
            backends_permitted=["inline", "team-execution"],
            degrade_policy="operator_away_one_rung",
        ),
    )
    result = OUTCOME.advance(repo, "oc373", attending=False)
    assert result.dispatched == ["build"]
    assert len(result.degraded) == 1
    assert result.degraded[0]["from_backend"] == "cc-workflows-ultracode"
    assert result.degraded[0]["to_backend"] == "team-execution"  # exactly one rung, never two


def test_ac3_two_rung_unavailable_halts_never_cascades(repo: Path) -> None:
    """AC3: when the immediate lower rung is NOT permitted, the run HALTs — it never silently
    cascades two rungs down to inline, even though inline is permitted and would run."""
    OUTCOME.start(
        repo,
        "oc373",
        "Objective",
        nodes=[{"subplot_id": "build", "title": "B", "backend": "cc-workflows-ultracode"}],
        intent=_intent_373(
            backends_permitted=["inline"],  # team-execution (the immediate rung) NOT permitted
            degrade_policy="operator_away_one_rung",
        ),
    )
    result = OUTCOME.advance(repo, "oc373", attending=False)
    assert result.dispatched == [] and result.degraded == []
    assert len(result.halted) == 1
    assert "no lower rung" in result.halted[0]["reason"]


def test_ac3_baseline_legacy_path_still_cascades_without_a_captured_posture(repo: Path) -> None:
    """Baseline control proving AC3 could go red: the SAME two-rung scenario WITHOUT a
    captured posture still takes the unchanged legacy degrade path (first available lower
    rung — here two rungs down to inline). The one-rung strictness is the captured posture's
    doing, not a change to degrade_decision (the issue's out-of-scope guarantee)."""
    OUTCOME.start(
        repo,
        "oc373",
        "Objective",
        nodes=[{"subplot_id": "build", "title": "B", "backend": "cc-workflows-ultracode"}],
    )
    result = OUTCOME.advance(repo, "oc373", available=("inline", "manual"), attending=False)
    assert result.dispatched == ["build"]
    assert len(result.degraded) == 1
    assert result.degraded[0]["to_backend"] == "inline"  # legacy: cascades past team-execution


def test_ac3_presence_conditions_still_halt_under_a_permissive_posture() -> None:
    """The captured one-rung permission feeds the UNCHANGED presence-conditional mechanism:
    attending / guarantee-bearing / side-effected still HALT exactly as before."""
    for kwargs in (
        {"attending": True, "guarantee_bearing": False, "had_side_effect": False},
        {"attending": False, "guarantee_bearing": True, "had_side_effect": False},
        {"attending": False, "guarantee_bearing": False, "had_side_effect": True},
    ):
        action, _, reason = D.captured_degrade_decision(
            "cc-workflows-ultracode",
            effective=("inline", "team-execution"),
            degrade_policy="operator_away_one_rung",
            **kwargs,
        )
        assert action == "halt", (kwargs, reason)


def test_ac4_ac5_under_ceiling_dispatch_clears_silently(repo: Path) -> None:
    """AC4+AC5: a spend envelope captured at run start is checked against outcome_costs's
    leaf-produced actuals pre-dispatch; an under-ceiling dispatch clears with NO halt/receipt."""
    OUTCOME.start(
        repo,
        "oc373",
        "Objective",
        nodes=[{"subplot_id": "a", "title": "A"}, {"subplot_id": "b", "title": "B"}],
        intent=_intent_373(spend_envelope={"cost_ceiling_tokens": 1000}),
    )
    store = STORE.Store.for_outcome("oc373", repo)
    OC.record_cost(store, "a", executor="inline", tokens=400)  # leaf-produced actuals, under
    result = OUTCOME.advance(repo, "oc373")
    assert sorted(result.dispatched) == ["a", "b"]
    assert result.halted == [] and result.gated == []  # silent: no interrupt, no receipt


def test_ac6_over_ceiling_dispatch_halts_for_step_up_never_degrades(repo: Path) -> None:
    """AC6: an over-ceiling dispatch raises the typed spend halt and NEVER falls through to a
    degraded tier/backend — the leaf stays ready (paused), nothing dispatched."""
    OUTCOME.start(
        repo,
        "oc373",
        "Objective",
        nodes=[{"subplot_id": "a", "title": "A"}],
        intent=_intent_373(spend_envelope={"cost_ceiling_tokens": 1000}),
    )
    store = STORE.Store.for_outcome("oc373", repo)
    OC.record_cost(store, "a", executor="inline", tokens=1200)  # actuals past the ceiling
    result = OUTCOME.advance(repo, "oc373", attending=False)  # even away: spend never degrades
    assert result.dispatched == [] and result.degraded == []
    assert len(result.halted) == 1
    receipt = result.halted[0]
    assert receipt["kind"] == "spend-halt"  # distinct code path from the backend-menu halt
    assert "step-up" in receipt["reason"]
    assert receipt["actual_tokens"] == 1200.0 and receipt["cost_ceiling_tokens"] == 1000.0
    # The leaf is paused, not consumed: derived state stays ready for a stepped-up retry.
    assert result.status["states"]["a"] == "ready"


def test_ac6_at_ceiling_exhausts_the_budget(repo: Path) -> None:
    """Boundary: actuals exactly AT the ceiling exhaust the budget (authorized only while
    strictly below) — the documented claim a crafted just-at-ceiling input would falsify."""
    OUTCOME.start(
        repo,
        "oc373",
        "Objective",
        nodes=[{"subplot_id": "a", "title": "A"}],
        intent=_intent_373(spend_envelope={"cost_ceiling_tokens": 1000}),
    )
    store = STORE.Store.for_outcome("oc373", repo)
    OC.record_cost(store, "a", executor="inline", tokens=1000)
    result = OUTCOME.advance(repo, "oc373")
    assert result.dispatched == []
    assert len(result.halted) == 1 and result.halted[0]["kind"] == "spend-halt"


def test_ac6_tier_escalating_leaf_halts_within_ceiling_leaf_dispatches(repo: Path) -> None:
    """AC6 tier half: a leaf whose declared tier is STRONGER than the captured ceiling halts
    for step-up; a within-ceiling sibling dispatches in the same tick (per-leaf gate)."""
    OUTCOME.start(
        repo,
        "oc373",
        "Objective",
        nodes=[
            {"subplot_id": "hi", "title": "H", "tier": "opus"},
            {"subplot_id": "lo", "title": "L", "tier": "haiku"},
        ],
        intent=_intent_373(spend_envelope={"tier_ceiling": "sonnet"}),
    )
    result = OUTCOME.advance(repo, "oc373")
    assert result.dispatched == ["lo"]
    assert len(result.halted) == 1
    receipt = result.halted[0]
    assert receipt["kind"] == "spend-halt" and receipt["subplot_id"] == "hi"
    assert receipt["requested_tier"] == "opus" and receipt["tier_ceiling"] == "sonnet"


def test_ac6_spend_halt_is_a_distinct_typed_error() -> None:
    """AC6: the spend halt is its own typed error — NOT a BackendHaltError — so backend
    unavailability handling can never accidentally swallow a spend denial."""
    spend = IE.SpendEnvelope.from_dict({"cost_ceiling_tokens": 100})
    with pytest.raises(D.SpendHaltError) as exc:
        D.authorize_dispatch_spend(
            spend, outcome_id="oc", subplot_id="a", backend="inline", actual_tokens=5000
        )
    assert not isinstance(exc.value, D.BackendHaltError)
    assert exc.value.receipt.to_dict()["kind"] == "spend-halt"
    # Silent-clear control: under the ceiling the same call returns None (no receipt at all).
    assert (
        D.authorize_dispatch_spend(
            spend, outcome_id="oc", subplot_id="a", backend="inline", actual_tokens=50
        )
        is None
    )


def test_spend_halt_resurfaces_each_advance_with_bounded_ledger(repo: Path) -> None:
    """A persistently over-ceiling run re-surfaces the spend halt on every advance while the
    ledger stays bounded (append-once on its own spend:<sid> dedup lane)."""
    OUTCOME.start(
        repo,
        "oc373",
        "Objective",
        nodes=[{"subplot_id": "a", "title": "A"}],
        intent=_intent_373(spend_envelope={"cost_ceiling_tokens": 100}),
    )
    store = STORE.Store.for_outcome("oc373", repo)
    OC.record_cost(store, "a", executor="inline", tokens=500)
    r1 = OUTCOME.advance(repo, "oc373")
    r2 = OUTCOME.advance(repo, "oc373")
    assert len(r1.halted) == 1 and len(r2.halted) == 1  # re-surfaced both ticks
    halts = [rec for rec in STORE.read_ledger(store) if rec.get("phase") == "halt"]
    assert len(halts) == 1  # appended once


def test_ac7_spec_with_no_intent_dispatches_unchanged(repo: Path) -> None:
    """AC7: a fixture spec lacking the new fields round-trips byte-identical and dispatches
    exactly as today (full menu through the production dispatcher, no spend gate)."""
    spec = OUTCOME.start(
        repo,
        "oc373",
        "Objective",
        nodes=[{"subplot_id": "build", "title": "B", "backend": "team-execution"}],
    )
    # Round-trip control: serialize -> reparse -> reserialize is byte-identical (no new keys).
    assert OUTCOME.outcome_spec.OutcomeSpec.from_json(spec.to_json()).to_json() == spec.to_json()
    assert "intent" not in spec.to_dict()
    assert all("tier" not in n for n in spec.to_dict()["nodes"])
    result = OUTCOME.advance(repo, "oc373", dispatcher=D.make_dispatcher())
    assert result.dispatched == ["build"] and result.halted == []


def test_ac7_pre_373_intent_leaves_the_seam_byte_identical(repo: Path) -> None:
    """AC7 (the #380-envelope half): an intent carrying NONE of the #373 fields engages no
    posture — the legacy degrade path decides identically to the no-intent baseline."""
    OUTCOME.start(
        repo,
        "oc373",
        "Objective",
        nodes=[{"subplot_id": "build", "title": "B", "backend": "cc-workflows-ultracode"}],
        intent=_intent_373(),  # run_mode + gates only — no backends/degrade/spend capture
    )
    result = OUTCOME.advance(repo, "oc373", available=("inline", "manual"), attending=False)
    assert result.dispatched == ["build"]
    assert result.degraded and result.degraded[0]["to_backend"] == "inline"  # legacy cascade
