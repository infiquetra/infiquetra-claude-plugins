#!/usr/bin/env python3
"""Pure policy helpers for external-engine chaperone economics (#381)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Literal

VERIFIABILITY_VALUES = ("test-gated", "unverifiable")
REVIEW_MODES = ("ratify-only", "full-review")
SAMPLE_RATINGS = ("WEAK", "MODERATE", "STRONG")

EVIDENCE_ESCALATION_BYTES = 32_768
BATCH_ESCALATION_UNITS = 5
SAMPLE_FRACTIONS = {
    "WEAK": 1.0,
    "MODERATE": 0.5,
    "STRONG": 0.2,
}

Verifiability = Literal["test-gated", "unverifiable"]
ReviewMode = Literal["ratify-only", "full-review"]
SampleRating = Literal["WEAK", "MODERATE", "STRONG"]


class ChaperonePolicyError(ValueError):
    """A chaperone economics input is outside the closed policy vocabulary."""


@dataclass(frozen=True)
class ChaperoneUnit:
    """The minimal per-unit data needed for chaperone economics decisions."""

    unit_id: str
    selector_kind: str
    selector: str
    intent: str = "offload"
    verifiability: Verifiability = "unverifiable"
    sandbox: str = ""
    write_mode: str = ""
    evidence_bytes: int = 0

    def __post_init__(self) -> None:
        if not self.unit_id:
            raise ChaperonePolicyError("unit_id must be non-empty")
        if not self.selector_kind or not self.selector:
            raise ChaperonePolicyError("selector_kind and selector must be non-empty")
        _validate_verifiability(self.verifiability)
        if self.evidence_bytes < 0:
            raise ChaperonePolicyError("evidence_bytes must be >= 0")

    @property
    def review_mode(self) -> ReviewMode:
        return review_mode_for(self.verifiability)

    @property
    def batchable(self) -> bool:
        return self.intent == "offload"

    @property
    def batch_key(self) -> tuple[str, ...]:
        if not self.batchable:
            return ("single", self.unit_id)
        return (
            self.selector_kind,
            self.selector,
            self.intent,
            self.verifiability,
            self.review_mode,
            self.sandbox,
            self.write_mode,
        )


@dataclass(frozen=True)
class ChaperoneDecision:
    """One batch's review/sampling/escalation decision."""

    batch_id: str
    unit_ids: tuple[str, ...]
    selector_kind: str
    selector: str
    verifiability: Verifiability
    review_mode: ReviewMode
    sample_rating: SampleRating
    sample_fraction: float
    sampled_unit_ids: tuple[str, ...]
    full_review_unit_ids: tuple[str, ...] = ()
    escalation_recommended: bool = False
    escalation_reason: str = ""
    cache_status: str = ""
    defective_sample_unit_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_provenance(self) -> dict[str, Any]:
        """Return a JSON-serializable advisory provenance payload."""
        data: dict[str, Any] = {
            "batch_id": self.batch_id,
            "unit_ids": list(self.unit_ids),
            "selector": {"kind": self.selector_kind, "value": self.selector},
            "verifiability": self.verifiability,
            "review_mode": self.review_mode,
            "sample_rating": self.sample_rating,
            "sample_fraction": self.sample_fraction,
            "sampled_unit_ids": list(self.sampled_unit_ids),
            "full_review_unit_ids": list(self.full_review_unit_ids),
            "escalation_recommended": self.escalation_recommended,
        }
        if self.escalation_reason:
            data["escalation_reason"] = self.escalation_reason
        if self.cache_status:
            data["cache_status"] = self.cache_status
        if self.defective_sample_unit_ids:
            data["defective_sample_unit_ids"] = list(self.defective_sample_unit_ids)
        return data


def review_mode_for(verifiability: str) -> ReviewMode:
    """Map an explicit verifiability signal to a chaperone review mode."""
    _validate_verifiability(verifiability)
    return "ratify-only" if verifiability == "test-gated" else "full-review"


def group_same_engine_batches(units: list[ChaperoneUnit]) -> list[list[ChaperoneUnit]]:
    """Group homogeneous offload units; unsafe/mixed units stay in smaller groups."""
    grouped: dict[tuple[str, ...], list[ChaperoneUnit]] = {}
    order: list[tuple[str, ...]] = []
    for unit in units:
        key = unit.batch_key
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(unit)
    return [grouped[key] for key in order]


def sample_count(total: int, rating: str) -> int:
    """Return the deterministic sample size for a batch."""
    if total < 0:
        raise ChaperonePolicyError("total must be >= 0")
    rating_value = _validate_sample_rating(rating)
    if total == 0:
        return 0
    fraction = SAMPLE_FRACTIONS[rating_value]
    if rating_value == "WEAK":
        return total
    minimum = 2 if rating_value == "MODERATE" else 1
    return min(total, max(minimum, math.ceil(total * fraction)))


def sample_unit_ids(unit_ids: list[str], rating: str) -> tuple[str, ...]:
    """Pick stable sample unit ids from a batch."""
    count = sample_count(len(unit_ids), rating)
    return tuple(sorted(unit_ids)[:count])


def decide_batch(
    units: list[ChaperoneUnit],
    *,
    sample_rating: str,
    batch_id: str | None = None,
    cache_status: str = "",
) -> ChaperoneDecision:
    """Compute one batch's chaperone decision from homogeneous units."""
    if not units:
        raise ChaperonePolicyError("batch must contain at least one unit")
    rating = _validate_sample_rating(sample_rating)
    first = units[0]
    key = first.batch_key
    for unit in units[1:]:
        if unit.batch_key != key:
            raise ChaperonePolicyError("batch contains non-homogeneous units")

    unit_ids = tuple(unit.unit_id for unit in units)
    total_evidence = sum(unit.evidence_bytes for unit in units)
    escalation_reason = _escalation_reason(total_evidence, len(units))
    return ChaperoneDecision(
        batch_id=batch_id or _batch_id(first, unit_ids),
        unit_ids=unit_ids,
        selector_kind=first.selector_kind,
        selector=first.selector,
        verifiability=first.verifiability,
        review_mode=first.review_mode,
        sample_rating=rating,
        sample_fraction=SAMPLE_FRACTIONS[rating],
        sampled_unit_ids=sample_unit_ids(list(unit_ids), rating),
        full_review_unit_ids=unit_ids if first.review_mode == "full-review" else (),
        escalation_recommended=bool(escalation_reason),
        escalation_reason=escalation_reason,
        cache_status=cache_status,
    )


def with_sample_result(
    decision: ChaperoneDecision, defective_sample_unit_ids: list[str]
) -> ChaperoneDecision:
    """Escalate remaining units to full review when a sampled defect is found."""
    defects = tuple(sorted(defective_sample_unit_ids))
    if not defects:
        return decision
    unknown = sorted(set(defects) - set(decision.sampled_unit_ids))
    if unknown:
        raise ChaperonePolicyError(
            "defective sample ids were not in the sampled set: " + ", ".join(unknown)
        )
    unsampled = tuple(unit_id for unit_id in decision.unit_ids if unit_id not in decision.sampled_unit_ids)
    return replace(
        decision,
        full_review_unit_ids=tuple(sorted(set(decision.full_review_unit_ids) | set(unsampled))),
        defective_sample_unit_ids=defects,
    )


def _validate_verifiability(value: str) -> Verifiability:
    if value not in VERIFIABILITY_VALUES:
        raise ChaperonePolicyError(
            f"verifiability {value!r} not in {VERIFIABILITY_VALUES}"
        )
    return value  # type: ignore[return-value]


def _validate_sample_rating(value: str) -> SampleRating:
    if value not in SAMPLE_RATINGS:
        raise ChaperonePolicyError(f"sample rating {value!r} not in {SAMPLE_RATINGS}")
    return value  # type: ignore[return-value]


def _escalation_reason(total_evidence: int, batch_size: int) -> str:
    if total_evidence > EVIDENCE_ESCALATION_BYTES:
        return (
            f"evidence_bytes {total_evidence} exceeds threshold "
            f"{EVIDENCE_ESCALATION_BYTES}; propose one chaperone tier rung"
        )
    if batch_size > BATCH_ESCALATION_UNITS:
        return (
            f"batch_size {batch_size} exceeds threshold {BATCH_ESCALATION_UNITS}; "
            "propose one chaperone tier rung"
        )
    return ""


def _batch_id(first: ChaperoneUnit, unit_ids: tuple[str, ...]) -> str:
    return ":".join((first.selector_kind, first.selector, first.verifiability, ",".join(unit_ids)))
