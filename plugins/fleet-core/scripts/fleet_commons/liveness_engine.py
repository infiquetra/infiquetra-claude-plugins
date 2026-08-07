#!/usr/bin/env python3
"""Pure fleet liveness scoring and signal fusion.

The engine accepts normalized immutable observations and performs no I/O.  Adapters retain custody
of their ledgers and authority: Outcome's legacy fixed budgets remain its terminal decision, while a
Team adapter may act only on ``TEAM_REPING_CONFIRMED`` after three receipt-proven response windows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

DECISION_SCHEMA = "liveness_decision.v1"
PROTOCOL_VERSION = 1
MAX_PHI = 16.0


class LivenessInputError(ValueError):
    """A normalized observation violates the engine's closed numeric contract."""


class Classification(StrEnum):
    HEALTHY = "healthy"
    HEARTBEAT_SUSPECT = "heartbeat-suspect"
    CHATTY_ARTIFACTLESS = "chatty-artifactless"
    SCOPED_ACTIVITY_UNATTRIBUTED = "scoped-activity-unattributed"
    REPING_REQUIRED = "reping-required"
    REPING_SEND_UNRESOLVED = "reping-send-unresolved"
    REPING_DELIVERY_BLOCKED = "reping-delivery-blocked"
    CONFIRMED_STALLED = "confirmed-stalled"
    EVIDENCE_ERROR = "evidence-error"


class TerminalAuthority(StrEnum):
    NONE = "none"
    TEAM_REPING_CONFIRMED = "team-reping-confirmed"


@dataclass(frozen=True, slots=True)
class LivenessPolicy:
    """Bounded scoring policy shared by every adapter."""

    phi_threshold: float = 8.0
    minimum_intervals: int = 5
    maximum_intervals: int = 100
    standard_deviation_floor_seconds: float = 1.0
    future_skew_tolerance_seconds: float = 5.0
    maximum_phi: float = MAX_PHI
    required_expired_reping_windows: int = 3


DEFAULT_POLICY = LivenessPolicy()


@dataclass(frozen=True, slots=True)
class RePingCandidate:
    generation_id: str
    cause: str
    liveness_attempt: int
    retry_ordinal: int
    claim_key: str
    predecessor_failure_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation_id": self.generation_id,
            "cause": self.cause,
            "liveness_attempt": self.liveness_attempt,
            "retry_ordinal": self.retry_ordinal,
            "claim_key": self.claim_key,
            "predecessor_failure_ref": self.predecessor_failure_ref,
        }


@dataclass(frozen=True, slots=True)
class LivenessObservation:
    """One adapter-verified projection consumed by :func:`evaluate`."""

    subject_id: str
    now: float
    dispatched_at: float
    heartbeat_times: tuple[float, ...] = ()
    last_progress: float | None = None
    last_host_ack: float | None = None
    last_unattributed_activity: float | None = None
    pending_notice_ids: tuple[str, ...] = ()
    expired_unacknowledged_reping_windows: int = 0
    reping_candidate: RePingCandidate | None = None
    reping_send_unresolved: bool = False
    reping_delivery_blocked: bool = False
    ttl_seconds: float | None = None
    subject_boot_id: str | None = None
    current_boot_id: str | None = None
    evidence_error: str | None = None
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PhiScore:
    phi: float | None
    sample_count: int
    last_heartbeat: float | None
    suspicion_anchor: float


@dataclass(frozen=True, slots=True)
class LivenessDecision:
    subject_id: str
    classification: Classification
    phi: float | None
    sample_count: int
    last_heartbeat: float | None
    last_progress: float | None
    pending_notice_ids: tuple[str, ...]
    reping: RePingCandidate | None
    terminal_authority: TerminalAuthority
    reason_code: str
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": DECISION_SCHEMA,
            "subject_id": self.subject_id,
            "classification": self.classification.value,
            "phi": self.phi,
            "sample_count": self.sample_count,
            "last_heartbeat": self.last_heartbeat,
            "last_progress": self.last_progress,
            "pending_notice_ids": list(self.pending_notice_ids),
            "reping": None if self.reping is None else self.reping.to_dict(),
            "terminal_authority": self.terminal_authority.value,
            "reason_code": self.reason_code,
            "evidence_refs": list(self.evidence_refs),
        }


def _finite_nonnegative(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LivenessInputError(f"{field} must be a finite nonnegative number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise LivenessInputError(f"{field} must be a finite nonnegative number")
    return number


def _validate_policy(policy: LivenessPolicy) -> None:
    _finite_nonnegative(policy.phi_threshold, "policy.phi_threshold")
    _finite_nonnegative(
        policy.standard_deviation_floor_seconds,
        "policy.standard_deviation_floor_seconds",
    )
    _finite_nonnegative(
        policy.future_skew_tolerance_seconds, "policy.future_skew_tolerance_seconds"
    )
    _finite_nonnegative(policy.maximum_phi, "policy.maximum_phi")
    if policy.minimum_intervals < 1:
        raise LivenessInputError("policy.minimum_intervals must be positive")
    if policy.maximum_intervals < policy.minimum_intervals:
        raise LivenessInputError("policy.maximum_intervals must cover minimum_intervals")
    if policy.standard_deviation_floor_seconds <= 0:
        raise LivenessInputError("policy.standard_deviation_floor_seconds must be positive")
    if policy.required_expired_reping_windows < 1:
        raise LivenessInputError("policy.required_expired_reping_windows must be positive")


def phi_score(
    *,
    dispatched_at: float,
    heartbeat_times: tuple[float, ...],
    now: float,
    policy: LivenessPolicy = DEFAULT_POLICY,
) -> PhiScore:
    """Compute bounded phi over deduplicated positive post-dispatch intervals.

    The dispatch timestamp is the first sample anchor.  Zero through four complete intervals retain
    the compatibility fallback and return ``phi=None``.  Future beats inside the configured skew
    tolerance clamp to ``now``; larger future skew is invalid evidence, and a dispatch beyond that
    tolerance ahead of ``now`` (a rolled-back or corrupt clock, R4/R12) can never read healthy.
    """

    _validate_policy(policy)
    dispatch = _finite_nonnegative(dispatched_at, "dispatched_at")
    current = _finite_nonnegative(now, "now")
    if dispatch > current + policy.future_skew_tolerance_seconds:
        raise LivenessInputError("dispatch exceeds the future-skew tolerance")
    normalized: set[float] = set()
    for index, raw in enumerate(heartbeat_times):
        beat = _finite_nonnegative(raw, f"heartbeat_times[{index}]")
        if beat < dispatch:
            continue
        if beat > current + policy.future_skew_tolerance_seconds:
            raise LivenessInputError("heartbeat exceeds the future-skew tolerance")
        normalized.add(min(beat, current))
    ordered = sorted(normalized)
    points = [dispatch, *[beat for beat in ordered if beat > dispatch]]
    intervals = [
        right - left for left, right in zip(points, points[1:], strict=False) if right > left
    ]
    intervals = intervals[-policy.maximum_intervals :]
    last_heartbeat = points[-1] if len(points) > 1 else None
    anchor = max(dispatch, last_heartbeat) if last_heartbeat is not None else dispatch
    # R4: no sample — the dispatch anchor included — may extend liveness into the future; a
    # within-tolerance future dispatch clamps to ``now`` exactly like a within-tolerance beat.
    anchor = min(anchor, current)
    if len(intervals) < policy.minimum_intervals:
        return PhiScore(None, len(intervals), last_heartbeat, anchor)

    mean = sum(intervals) / len(intervals)
    variance = sum((item - mean) ** 2 for item in intervals) / len(intervals)
    deviation = max(math.sqrt(variance), policy.standard_deviation_floor_seconds)
    delay = max(0.0, current - anchor)
    tail = 0.5 * math.erfc((delay - mean) / (deviation * math.sqrt(2.0)))
    phi = min(policy.maximum_phi, -math.log10(max(tail, 10 ** (-policy.maximum_phi))))
    return PhiScore(phi, len(intervals), last_heartbeat, anchor)


def _decision(
    observation: LivenessObservation,
    score: PhiScore,
    classification: Classification,
    reason_code: str,
    *,
    terminal_authority: TerminalAuthority = TerminalAuthority.NONE,
    reping: RePingCandidate | None = None,
) -> LivenessDecision:
    return LivenessDecision(
        subject_id=observation.subject_id,
        classification=classification,
        phi=score.phi,
        sample_count=score.sample_count,
        last_heartbeat=score.last_heartbeat,
        last_progress=observation.last_progress,
        pending_notice_ids=observation.pending_notice_ids,
        reping=reping,
        terminal_authority=terminal_authority,
        reason_code=reason_code,
        evidence_refs=observation.evidence_refs,
    )


def evaluate(
    observation: LivenessObservation,
    policy: LivenessPolicy = DEFAULT_POLICY,
) -> LivenessDecision:
    """Fuse normalized evidence into one closed ``liveness_decision.v1`` value."""

    if not observation.subject_id:
        raise LivenessInputError("subject_id must be non-empty")
    if observation.evidence_error:
        empty = PhiScore(None, 0, None, observation.dispatched_at)
        return _decision(
            observation,
            empty,
            Classification.EVIDENCE_ERROR,
            "adapter-evidence-error",
        )
    try:
        score = phi_score(
            dispatched_at=observation.dispatched_at,
            heartbeat_times=observation.heartbeat_times,
            now=observation.now,
            policy=policy,
        )
        current = _finite_nonnegative(observation.now, "now")
        progress = (
            None
            if observation.last_progress is None
            else _finite_nonnegative(observation.last_progress, "last_progress")
        )
        host_ack = (
            None
            if observation.last_host_ack is None
            else _finite_nonnegative(observation.last_host_ack, "last_host_ack")
        )
        unattributed = (
            None
            if observation.last_unattributed_activity is None
            else _finite_nonnegative(
                observation.last_unattributed_activity,
                "last_unattributed_activity",
            )
        )
        ttl = (
            None
            if observation.ttl_seconds is None
            else _finite_nonnegative(observation.ttl_seconds, "ttl_seconds")
        )
    except LivenessInputError:
        empty = PhiScore(None, 0, None, observation.dispatched_at)
        return _decision(observation, empty, Classification.EVIDENCE_ERROR, "invalid-observation")

    if (
        observation.subject_boot_id is not None
        and observation.current_boot_id is not None
        and observation.subject_boot_id != observation.current_boot_id
    ):
        return _decision(observation, score, Classification.EVIDENCE_ERROR, "boot-identity-changed")

    phi_suspect = score.phi is not None and score.phi >= policy.phi_threshold
    cold_start_suspect = (
        score.phi is None and ttl is not None and current - score.suspicion_anchor > ttl
    )
    suspicious = phi_suspect or cold_start_suspect
    refutation = (
        max(value for value in (progress, host_ack) if value is not None)
        if (progress is not None or host_ack is not None)
        else None
    )
    if suspicious and refutation is not None and refutation >= score.suspicion_anchor:
        return _decision(observation, score, Classification.HEALTHY, "trusted-signal-refuted")
    if not suspicious:
        return _decision(observation, score, Classification.HEALTHY, "within-liveness-policy")

    if observation.expired_unacknowledged_reping_windows >= policy.required_expired_reping_windows:
        return _decision(
            observation,
            score,
            Classification.CONFIRMED_STALLED,
            "three-proven-reping-windows-expired",
            terminal_authority=TerminalAuthority.TEAM_REPING_CONFIRMED,
        )
    if observation.reping_delivery_blocked:
        return _decision(
            observation,
            score,
            Classification.REPING_DELIVERY_BLOCKED,
            "definitive-reping-retry-exhausted",
        )
    if observation.reping_send_unresolved:
        return _decision(
            observation,
            score,
            Classification.REPING_SEND_UNRESOLVED,
            "reping-send-outcome-unresolved",
        )
    if unattributed is not None and (progress is None or unattributed > progress):
        return _decision(
            observation,
            score,
            Classification.SCOPED_ACTIVITY_UNATTRIBUTED,
            "scoped-change-has-no-exclusive-provenance",
            reping=observation.reping_candidate,
        )
    if host_ack is not None and (progress is None or host_ack > progress):
        return _decision(
            observation,
            score,
            Classification.CHATTY_ARTIFACTLESS,
            "idle-ack-is-not-progress",
            reping=observation.reping_candidate,
        )
    if observation.reping_candidate is not None:
        return _decision(
            observation,
            score,
            Classification.REPING_REQUIRED,
            "adaptive-suspicion-needs-proven-reping",
            reping=observation.reping_candidate,
        )
    return _decision(
        observation,
        score,
        Classification.HEARTBEAT_SUSPECT,
        "phi-threshold" if phi_suspect else "ttl-cold-start",
    )
