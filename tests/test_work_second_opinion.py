"""Executable `/work` debounce and persistence contracts for issue #394."""

from __future__ import annotations

import importlib.util
import stat
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
SECOND_OPINION = SCRIPTS / "second_opinion.py"
REGISTRY = ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml"


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SO = _load("work_second_opinion", SECOND_OPINION)
REG = SO.Registry.load(REGISTRY)


@pytest.fixture(autouse=True)
def _isolated_fleet_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFIQUETRA_FLEET_STATE_DIR", str(tmp_path / "fleet-leases"))


def _attempt(
    number: int,
    *targets: str,
    result: str = "fail",
) -> Any:
    return SO.WorkAttempt(
        attempt_id=f"attempt-{number}",
        change_ref=f"change-{number}",
        result=result,
        failing_test_files=tuple(targets),
    )


def _record(state: Any, *attempts: Any, preference: str | None = None) -> tuple[Any, list[Any]]:
    offers: list[Any] = []
    for attempt in attempts:
        result = SO.record_work_attempt(state, attempt, preference_intent=preference)
        state = result.state
        if result.offer is not None:
            offers.append(result.offer)
    return state, offers


def _resolution() -> Any:
    return SO.engine_resolver.Resolution(
        engine_id="codex",
        variant="gpt-5.5-high",
        effort="high",
        recipe="review independently",
        protocol=["Review the selected finding."],
        payload="Review the selected finding.",
        write_capable=False,
        fallback=None,
        halt=None,
    )


def _lease_admission() -> Any:
    return SO.engine_dispatch.LeaseAdmission(
        policy_sha256="a" * 64,
        session_limit=1,
        aggregate_limit=1,
        mutation="none",
    )


def _prepared(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(SO.engine_resolver, "resolve", lambda *_args, **_kwargs: _resolution())
    finding = SO.FindingSnapshot(
        finding_id="F1",
        title="A finding that needs a second opinion",
        severity="P1",
        why_it_matters="A review surface must remain Claude-owned.",
        evidence=("The verdict derives from final Claude state.",),
        suggested_fix="Keep external output advisory.",
        reviewed_revision="abc123",
        excerpts=(
            SO.SourceExcerpt(
                path="plugins/saga/scripts/engine_dispatch.py",
                start_line=1,
                end_line=2,
                content="return final_claude_finding",
            ),
        ),
    )
    return SO.prepare_second_opinion(
        finding,
        registry=REG,
        requested_by="human",
        reason="Check this finding before selecting another fix.",
        lease_admission=_lease_admission(),
    )


def test_three_target_specific_attempts_emit_one_exact_debounced_offer() -> None:
    state = SO.WorkSecondOpinionState(round=1)
    state, offers = _record(
        state,
        _attempt(1, "./tests/test_work.py::test_stuck", "tests/test_incidental.py::test_noise"),
        _attempt(2, "tests/test_work.py::test_stuck"),
    )
    assert offers == []

    result = SO.record_work_attempt(
        state,
        _attempt(3, "tests/test_work.py::test_stuck", "tests/test_other.py::test_extra"),
    )
    assert result.offer is not None
    assert result.offer.target == "tests/test_work.py"
    assert result.offer.disposition == "offered"
    assert result.offer.tier == {"model": "opus", "effort": "high"}
    assert result.offer_line == (
        "Second opinion available: tests/test_work.py failed after 3 fix attempts; "
        "dispatch an advisory second opinion?"
    )

    fourth = SO.record_work_attempt(
        result.state,
        _attempt(4, "tests/test_work.py::test_stuck"),
    )
    assert fourth.offer is None
    assert len(fourth.state.offers) == 1


def test_pass_and_target_absence_reset_only_the_required_streak() -> None:
    state = SO.WorkSecondOpinionState(round=1)
    state, offers = _record(
        state,
        _attempt(1, "tests/test_alpha.py::test_a"),
        _attempt(2, "tests/test_alpha.py::test_a"),
        _attempt(3, "tests/test_beta.py::test_b"),
        _attempt(4, "tests/test_alpha.py::test_a"),
        _attempt(5, "tests/test_alpha.py::test_a"),
    )
    assert offers == []

    state, offers = _record(
        state,
        _attempt(6, result="pass"),
        _attempt(7, "tests/test_alpha.py::test_a"),
        _attempt(8, "tests/test_alpha.py::test_a"),
        _attempt(9, "tests/test_alpha.py::test_a"),
    )
    assert [offer.target for offer in offers] == ["tests/test_alpha.py"]


@pytest.mark.parametrize(
    "reset_attempt",
    [
        _attempt(4, result="pass"),
        _attempt(4, "tests/test_other.py::test_other"),
    ],
    ids=("pass", "target-absence"),
)
def test_reset_expires_an_unaccepted_offer_before_any_runner_path(reset_attempt: Any) -> None:
    state, offers = _record(
        SO.WorkSecondOpinionState(round=1),
        _attempt(1, "tests/test_work.py::test_stuck"),
        _attempt(2, "tests/test_work.py::test_stuck"),
        _attempt(3, "tests/test_work.py::test_stuck"),
    )
    reset = SO.record_work_attempt(state, reset_attempt).state
    assert reset.offers[0].disposition == "unavailable"
    with pytest.raises(SO.WorkSecondOpinionStateError, match="active failure streak"):
        SO.accept_work_offer(reset, offer_id=offers[0].offer_id, prepared=object())


def test_same_attempt_is_noop_and_lexical_target_wins_same_threshold() -> None:
    state = SO.WorkSecondOpinionState(round=2)
    state, _ = _record(
        state,
        _attempt(1, "tests/test_z.py::test_z", "tests/test_a.py::test_a"),
        _attempt(2, "tests/test_z.py::test_z", "tests/test_a.py::test_a"),
    )
    result = SO.record_work_attempt(
        state,
        _attempt(3, "tests/test_z.py::test_z", "tests/test_a.py::test_a"),
    )
    assert result.offer is not None
    assert result.offer.target == "tests/test_a.py"

    rerun = SO.record_work_attempt(
        result.state, _attempt(3, "tests/test_z.py::test_z", "tests/test_a.py::test_a")
    )
    assert rerun.state == result.state
    assert rerun.offer is None
    with pytest.raises(SO.WorkSecondOpinionStateError, match="different completed attempt"):
        SO.record_work_attempt(result.state, _attempt(3, "tests/test_a.py::test_changed"))


def test_none_suppresses_but_offload_cannot_change_second_opinion_trigger() -> None:
    attempts = tuple(_attempt(number, "tests/test_work.py::test_stuck") for number in range(1, 4))
    none_state, none_offers = _record(
        SO.WorkSecondOpinionState(round=1), *attempts, preference="none"
    )
    assert none_offers == []
    assert len(none_state.attempts) == 3

    _state, offload_offers = _record(
        SO.WorkSecondOpinionState(round=1),
        *attempts,
        preference="offload",
    )
    assert len(offload_offers) == 1
    assert offload_offers[0].disposition == "offered"


@pytest.mark.parametrize(
    "target",
    [
        "/tmp/test_escape.py::test_x",
        "tests/../test_escape.py::test_x",
        "not-a-pytest-file",
        "C:\\repo\\tests\\test_escape.py::test_x",
    ],
)
def test_invalid_pytest_targets_fail_before_state_mutation(target: str) -> None:
    with pytest.raises(SO.WorkSecondOpinionStateError):
        _attempt(1, target)


def test_sidecar_save_load_is_atomic_private_and_fails_closed(tmp_path: Path) -> None:
    session = tmp_path / "2026-07-10-topic.md"
    path = SO.work_second_opinion_sidecar(session)
    state, offers = _record(
        SO.WorkSecondOpinionState(round=3),
        _attempt(1, "tests/test_work.py::test_stuck"),
        _attempt(2, "tests/test_work.py::test_stuck"),
        _attempt(3, "tests/test_work.py::test_stuck"),
    )
    assert offers
    SO.save_work_second_opinion_state(path, state)

    assert SO.load_work_second_opinion_state(path, round=3) == state
    resumed = _load("work_second_opinion_resume", SECOND_OPINION)
    assert resumed.load_work_second_opinion_state(path, round=3).to_dict() == state.to_dict()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(SO.WorkSecondOpinionStateError, match="does not match current round"):
        SO.load_work_second_opinion_state(path, round=4)

    malformed = tmp_path / "malformed.json"
    malformed.write_text("", encoding="utf-8")
    with pytest.raises(SO.WorkSecondOpinionStateError, match="cannot read"):
        SO.load_work_second_opinion_state(malformed, round=3)
    with pytest.raises(SO.WorkSecondOpinionStateError, match="MAX_TARGETS_PER_ATTEMPT"):
        _attempt(4, *(f"tests/test_{index}.py::test_x" for index in range(257)))
    capped = SO.WorkSecondOpinionState(
        round=3,
        attempts=tuple(_attempt(index, result="pass") for index in range(1, 65)),
    )
    with pytest.raises(SO.WorkSecondOpinionStateError, match="MAX_WORK_ATTEMPTS"):
        SO.record_work_attempt(capped, _attempt(65, result="pass"))


def test_offer_outcomes_persist_request_identity_before_single_dispatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state, offers = _record(
        SO.WorkSecondOpinionState(round=1),
        _attempt(1, "tests/test_work.py::test_stuck"),
        _attempt(2, "tests/test_work.py::test_stuck"),
        _attempt(3, "tests/test_work.py::test_stuck"),
    )
    offer = offers[0]
    prepared = _prepared(monkeypatch)
    accepted = SO.accept_work_offer(state, offer_id=offer.offer_id, prepared=prepared)
    persisted = accepted.offers[0]
    assert persisted.disposition == "accepted"
    assert persisted.request_id == prepared.request_id
    assert persisted.request_digest == prepared.request_digest
    assert persisted.execution_id == prepared.execution_id
    sidecar = tmp_path / "work-second-opinion.json"
    SO.save_work_second_opinion_state(sidecar, accepted)
    assert SO.load_work_second_opinion_state(sidecar, round=1) == accepted

    calls = 0

    def runner(_invocation: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        rows = [{"content": "The original finding remains correct."}]
        return {
            "status": "success",
            "output": SO.reconcile.render_source_findings(SO.reconcile.parse_source_findings(rows)),
            "findings": rows,
        }

    store = SO.SecondOpinionClaimStore(tmp_path / "claims.json")
    SO.dispatch_second_opinion(prepared, runner=runner, claim_store=store)
    retry = SO.dispatch_second_opinion(prepared, runner=runner, claim_store=store)
    assert calls == 1
    assert retry.halt is not None

    declined = SO.set_work_offer_disposition(
        state,
        offer_id=offer.offer_id,
        disposition="declined",
    )
    assert declined.offers[0].disposition == "declined"
    unattended = SO.set_work_offer_disposition(
        state,
        offer_id=offer.offer_id,
        disposition="unattended",
    )
    assert unattended.offers[0].disposition == "unattended"


def test_terminal_dispatch_outcome_is_saved_unavailable_and_cannot_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state, offers = _record(
        SO.WorkSecondOpinionState(round=1),
        _attempt(1, "tests/test_work.py::test_stuck"),
        _attempt(2, "tests/test_work.py::test_stuck"),
        _attempt(3, "tests/test_work.py::test_stuck"),
    )
    prepared = _prepared(monkeypatch)
    accepted = SO.accept_work_offer(state, offer_id=offers[0].offer_id, prepared=prepared)
    calls = 0

    def timeout_runner(_invocation: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"status": "timeout", "output": "runner timed out"}

    store = SO.SecondOpinionClaimStore(tmp_path / "claims.json")
    evidence = SO.dispatch_second_opinion(prepared, runner=timeout_runner, claim_store=store)
    unavailable = SO.record_work_dispatch_outcome(
        accepted,
        offer_id=offers[0].offer_id,
        evidence=evidence,
    )
    sidecar = tmp_path / "work-second-opinion.json"
    SO.save_work_second_opinion_state(sidecar, unavailable)

    assert unavailable.offers[0].disposition == "unavailable"
    assert (
        SO.load_work_second_opinion_state(sidecar, round=1).offers[0].disposition == "unavailable"
    )
    retry = SO.dispatch_second_opinion(prepared, runner=timeout_runner, claim_store=store)
    assert calls == 1
    assert retry.halt is not None
