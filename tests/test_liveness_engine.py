"""Pure shared liveness-engine contract for issue #357."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
MODULE = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "liveness_engine.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("test_liveness_engine_module", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LV = _load()


def _beats() -> tuple[float, ...]:
    return (10.0, 20.0, 30.0, 40.0, 50.0, 60.0)


def _observation(**changes: object) -> object:
    values = {
        "subject_id": "subject-1",
        "now": 65.0,
        "dispatched_at": 0.0,
        "heartbeat_times": _beats(),
    }
    values.update(changes)
    return LV.LivenessObservation(**values)


def test_five_intervals_enable_phi_while_sparse_history_returns_null() -> None:
    sparse = LV.phi_score(dispatched_at=0, heartbeat_times=(10, 20, 30, 40), now=50)
    ready = LV.phi_score(dispatched_at=0, heartbeat_times=(10, 20, 30, 40, 50), now=60)
    assert sparse.phi is None and sparse.sample_count == 4
    assert ready.phi is not None and ready.sample_count == 5


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4])
def test_sparse_history_zero_through_four_intervals_returns_null_phi(count: int) -> None:
    beats = tuple(float(10 * (index + 1)) for index in range(count))
    score = LV.phi_score(dispatched_at=0, heartbeat_times=beats, now=100)
    assert score.phi is None
    assert score.sample_count == count


def test_steady_intervals_are_healthy_and_long_silence_crosses_phi_eight() -> None:
    healthy = LV.evaluate(_observation(now=65.0))
    suspect = LV.evaluate(_observation(now=160.0))
    assert healthy.classification == LV.Classification.HEALTHY
    assert suspect.phi is not None and suspect.phi >= 8
    assert suspect.classification == LV.Classification.HEARTBEAT_SUSPECT
    assert suspect.terminal_authority == LV.TerminalAuthority.NONE


def test_order_duplicates_and_pre_dispatch_beats_do_not_change_phi() -> None:
    ordered = LV.phi_score(dispatched_at=5, heartbeat_times=_beats(), now=100)
    noisy = LV.phi_score(
        dispatched_at=5,
        heartbeat_times=(60, 20, 10, 20, 0, 50, 40, 30),
        now=100,
    )
    assert noisy.sample_count == ordered.sample_count
    assert noisy.phi == ordered.phi


def test_window_is_bounded_to_latest_one_hundred_intervals() -> None:
    beats = tuple(float(value) for value in range(1, 151))
    score = LV.phi_score(dispatched_at=0, heartbeat_times=beats, now=151)
    assert score.sample_count == 100


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, True, "1"])
def test_invalid_numeric_input_becomes_evidence_error(bad: object) -> None:
    decision = LV.evaluate(_observation(now=bad))
    assert decision.classification == LV.Classification.EVIDENCE_ERROR
    assert decision.terminal_authority == LV.TerminalAuthority.NONE


def test_future_skew_clamps_inside_tolerance_and_rejects_outside() -> None:
    inside = LV.phi_score(dispatched_at=0, heartbeat_times=(1, 2, 3, 4, 11), now=10)
    assert inside.last_heartbeat == 10
    with pytest.raises(LV.LivenessInputError, match="future-skew"):
        LV.phi_score(dispatched_at=0, heartbeat_times=(1, 2, 3, 4, 20), now=10)


def test_clock_rollback_fails_closed_and_zero_variance_is_finite() -> None:
    rollback = LV.evaluate(
        _observation(
            dispatched_at=100,
            heartbeat_times=(110, 120, 130, 140, 150),
            now=90,
        )
    )
    assert rollback.classification == LV.Classification.EVIDENCE_ERROR
    steady = LV.phi_score(dispatched_at=0, heartbeat_times=(10, 20, 30, 40, 50), now=100)
    assert steady.phi is not None and 0 <= steady.phi <= 16


def test_future_dispatch_without_heartbeats_is_evidence_error_not_healthy() -> None:
    # R4/R12 regression: a far-future dispatch with no post-now beats must read evidence-error,
    # never healthy — the sparse fallback cannot launder a corrupt or rolled-back clock.
    decision = LV.evaluate(_observation(now=100.0, dispatched_at=200.0, heartbeat_times=()))
    assert decision.classification == LV.Classification.EVIDENCE_ERROR
    assert decision.reason_code == "invalid-observation"
    with pytest.raises(LV.LivenessInputError, match="future-skew"):
        LV.phi_score(dispatched_at=200.0, heartbeat_times=(), now=100.0)
    # dispatch skew at the tolerance boundary is still valid sparse evidence
    within = LV.evaluate(_observation(now=100.0, dispatched_at=105.0, heartbeat_times=()))
    assert within.classification == LV.Classification.HEALTHY


def test_phi_threshold_boundary_is_inclusive_at_eight() -> None:
    # With _beats() the anchor is 60 and deviation floors at 1.0s: now=75.6 computes phi just
    # under 8 (healthy) and now=75.7 just over (suspect) — the crossing itself, not the cap.
    below = LV.evaluate(_observation(now=75.6))
    above = LV.evaluate(_observation(now=75.7))
    assert below.phi is not None and below.phi < 8.0
    assert below.classification == LV.Classification.HEALTHY
    assert above.phi is not None and 8.0 <= above.phi < 16.0
    assert above.classification == LV.Classification.HEARTBEAT_SUSPECT
    assert above.reason_code == "phi-threshold"
    # phi == threshold exactly flags suspicion: the comparison is inclusive (>=)
    pinned = LV.LivenessPolicy(phi_threshold=below.phi)
    at_threshold = LV.evaluate(_observation(now=75.6), pinned)
    assert at_threshold.classification == LV.Classification.HEARTBEAT_SUSPECT


def test_phi_matches_the_hand_computed_normal_tail_golden_value() -> None:
    # Five exact 10s intervals -> Normal(10, 1) after the deviation floor; delay 14 gives
    # tail = 0.5*erfc(4/sqrt(2)) = 3.167124183311996e-05, phi = -log10(tail) = 4.499334907556478.
    score = LV.phi_score(
        dispatched_at=0.0, heartbeat_times=(10.0, 20.0, 30.0, 40.0, 50.0), now=64.0
    )
    assert score.phi == pytest.approx(4.499334907556478, rel=1e-12)


def test_phi_is_monotonic_for_a_fixed_sample() -> None:
    values = [
        LV.phi_score(dispatched_at=0, heartbeat_times=_beats(), now=now).phi
        for now in (60, 70, 80, 100, 160)
    ]
    assert all(value is not None for value in values)
    assert values == sorted(values)


def test_ttl_cold_start_is_suspicion_only() -> None:
    decision = LV.evaluate(
        _observation(
            now=301,
            heartbeat_times=(),
            lease_ttl_seconds=300,
            reping_candidate=LV.RePingCandidate("g", "heartbeat-absent", 0, 0, "c"),
        )
    )
    assert decision.phi is None
    assert decision.classification == LV.Classification.REPING_REQUIRED
    assert decision.terminal_authority == LV.TerminalAuthority.NONE


def test_lease_ttl_cold_start_boundary_is_strict() -> None:
    # elapsed == ttl stays healthy (strict >); the first instant past the ttl is suspicion.
    at_ttl = LV.evaluate(_observation(now=300.0, heartbeat_times=(), lease_ttl_seconds=300))
    over = LV.evaluate(_observation(now=300.5, heartbeat_times=(), lease_ttl_seconds=300))
    assert at_ttl.classification == LV.Classification.HEALTHY
    assert over.phi is None
    assert over.classification == LV.Classification.HEARTBEAT_SUSPECT
    assert over.reason_code == "lease-ttl-cold-start"


def test_renewal_or_expiry_alone_is_not_an_engine_input() -> None:
    fields = set(LV.LivenessObservation.__dataclass_fields__)
    assert "lease_renewed_at" not in fields
    assert "lease_expired" not in fields


def test_trusted_progress_or_host_ack_refutes_suspicion_but_unattributed_activity_does_not() -> (
    None
):
    progress = LV.evaluate(_observation(now=160, last_progress=120))
    ack = LV.evaluate(_observation(now=160, last_host_ack=120))
    unattributed = LV.evaluate(_observation(now=160, last_unattributed_activity=120))
    assert progress.classification == LV.Classification.HEALTHY
    assert ack.classification == LV.Classification.HEALTHY
    assert unattributed.classification == LV.Classification.SCOPED_ACTIVITY_UNATTRIBUTED


def test_idle_ack_is_not_progress() -> None:
    decision = LV.evaluate(_observation(now=160, last_host_ack=55))
    assert decision.classification == LV.Classification.CHATTY_ARTIFACTLESS


def test_three_proven_expired_windows_are_the_only_terminal_authority() -> None:
    two = LV.evaluate(_observation(now=160, expired_unacknowledged_reping_windows=2))
    three = LV.evaluate(_observation(now=160, expired_unacknowledged_reping_windows=3))
    assert two.terminal_authority == LV.TerminalAuthority.NONE
    assert three.classification == LV.Classification.CONFIRMED_STALLED
    assert three.terminal_authority == LV.TerminalAuthority.TEAM_REPING_CONFIRMED


def test_unresolved_and_exhausted_delivery_are_nonterminal() -> None:
    unresolved = LV.evaluate(_observation(now=160, reping_send_unresolved=True))
    blocked = LV.evaluate(_observation(now=160, reping_delivery_blocked=True))
    assert unresolved.classification == LV.Classification.REPING_SEND_UNRESOLVED
    assert blocked.classification == LV.Classification.REPING_DELIVERY_BLOCKED
    assert unresolved.terminal_authority == blocked.terminal_authority == LV.TerminalAuthority.NONE


def test_boot_change_is_evidence_error_not_death() -> None:
    decision = LV.evaluate(
        _observation(now=160, subject_boot_id="boot-a", current_boot_id="boot-b")
    )
    assert decision.classification == LV.Classification.EVIDENCE_ERROR
    assert decision.terminal_authority == LV.TerminalAuthority.NONE


def test_decision_serialization_is_closed_and_stable() -> None:
    decision = LV.evaluate(_observation())
    assert set(decision.to_dict()) == {
        "schema",
        "subject_id",
        "classification",
        "phi",
        "sample_count",
        "last_heartbeat",
        "last_progress",
        "pending_notice_ids",
        "reping",
        "terminal_authority",
        "reason_code",
        "evidence_refs",
    }
