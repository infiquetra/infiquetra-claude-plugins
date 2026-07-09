#!/usr/bin/env python3
"""Pure policy helpers for external-engine chaperone economics (#381)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Literal

VERIFIABILITY_VALUES = ("test-gated", "unverifiable")
REVIEW_MODES = ("ratify-only", "full-review")
SAMPLE_RATINGS = ("WEAK", "MODERATE", "STRONG")
COST_CLASSES = ("metered", "free")
OFFLOAD_ECONOMICS_STATUSES = (
    "proceed",
    "free-class-proceed",
    "break-even-halt",
    "budget-ceiling-halt",
    "economics-missing-halt",
)
NET_SAVINGS_STATUSES = ("positive", "zero", "negative")

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
CostClass = Literal["metered", "free"]
OffloadEconomicsStatus = Literal[
    "proceed",
    "free-class-proceed",
    "break-even-halt",
    "budget-ceiling-halt",
    "economics-missing-halt",
]
NetSavingsStatus = Literal["positive", "zero", "negative"]


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


@dataclass(frozen=True)
class NetSavingsRecord:
    """Unit-safe token savings record for one offload decision."""

    engine_tokens_avoided: int
    chaperone_tokens_spent: int
    net_savings_tokens: int
    net_savings_status: NetSavingsStatus
    external_cost_usd: float | None = None

    @classmethod
    def from_estimates(
        cls,
        *,
        engine_tokens_avoided: int,
        chaperone_tokens_spent: int,
        external_cost_usd: float | None = None,
    ) -> NetSavingsRecord:
        avoided = _validate_non_negative_int(engine_tokens_avoided, "engine_tokens_avoided")
        spent = _validate_non_negative_int(chaperone_tokens_spent, "chaperone_tokens_spent")
        external_cost = _validate_optional_non_negative_float(
            external_cost_usd, "external_cost_usd"
        )
        net = avoided - spent
        if net > 0:
            status: NetSavingsStatus = "positive"
        elif net == 0:
            status = "zero"
        else:
            status = "negative"
        return cls(
            engine_tokens_avoided=avoided,
            chaperone_tokens_spent=spent,
            net_savings_tokens=net,
            net_savings_status=status,
            external_cost_usd=external_cost,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "engine_tokens_avoided": self.engine_tokens_avoided,
            "chaperone_tokens_spent": self.chaperone_tokens_spent,
            "net_savings_tokens": self.net_savings_tokens,
            "net_savings_status": self.net_savings_status,
        }
        if self.external_cost_usd is not None:
            data["external_cost_usd"] = self.external_cost_usd
        return data


@dataclass(frozen=True)
class OffloadEconomicsInput:
    """Inputs needed to decide whether an offload is economically safe to run."""

    engine_id: str
    cost_class: CostClass
    estimated_external_cost_usd: float | None = None
    provider_budget_ceiling_usd: float | None = None
    prior_provider_spend_usd: float = 0.0
    claude_inline_tokens_estimate: int | None = None
    chaperone_tokens_estimate: int | None = None
    inline_fallback: str = "inline"

    def __post_init__(self) -> None:
        if not self.engine_id:
            raise ChaperonePolicyError("engine_id must be non-empty")
        _validate_cost_class(self.cost_class)
        _validate_optional_non_negative_float(
            self.estimated_external_cost_usd, "estimated_external_cost_usd"
        )
        _validate_optional_non_negative_float(
            self.provider_budget_ceiling_usd, "provider_budget_ceiling_usd"
        )
        _validate_non_negative_float(self.prior_provider_spend_usd, "prior_provider_spend_usd")
        _validate_optional_non_negative_int(
            self.claude_inline_tokens_estimate, "claude_inline_tokens_estimate"
        )
        _validate_optional_non_negative_int(
            self.chaperone_tokens_estimate, "chaperone_tokens_estimate"
        )
        if not self.inline_fallback:
            raise ChaperonePolicyError("inline_fallback must be non-empty")


@dataclass(frozen=True)
class OffloadEconomicsDecision:
    """A dispatch-ready offload economics decision and preview."""

    engine_id: str
    cost_class: CostClass
    status: OffloadEconomicsStatus
    proceed: bool
    preview: str
    net_savings: NetSavingsRecord
    reason: str = ""
    missing_fields: tuple[str, ...] = ()
    provider_budget_ceiling_usd: float | None = None
    prior_provider_spend_usd: float = 0.0
    projected_provider_spend_usd: float | None = None
    inline_fallback: str = "inline"

    def to_provenance(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "engine_id": self.engine_id,
            "cost_class": self.cost_class,
            "status": self.status,
            "proceed": self.proceed,
            "preview": self.preview,
            "net_savings": self.net_savings.to_dict(),
            "prior_provider_spend_usd": self.prior_provider_spend_usd,
            "inline_fallback": self.inline_fallback,
        }
        if self.reason:
            data["reason"] = self.reason
        if self.missing_fields:
            data["missing_fields"] = list(self.missing_fields)
        if self.provider_budget_ceiling_usd is not None:
            data["provider_budget_ceiling_usd"] = self.provider_budget_ceiling_usd
        if self.projected_provider_spend_usd is not None:
            data["projected_provider_spend_usd"] = self.projected_provider_spend_usd
        return data


def decide_offload_economics(input_data: OffloadEconomicsInput) -> OffloadEconomicsDecision:
    """Return the dispatch-time economics decision for one ``offload`` route."""
    if input_data.cost_class == "free":
        record = NetSavingsRecord.from_estimates(
            engine_tokens_avoided=input_data.claude_inline_tokens_estimate or 0,
            chaperone_tokens_spent=input_data.chaperone_tokens_estimate or 0,
            external_cost_usd=0.0,
        )
        return _offload_decision(
            input_data,
            status="free-class-proceed",
            proceed=True,
            net_savings=record,
            projected_provider_spend_usd=input_data.prior_provider_spend_usd,
            preview=(
                f"offload {input_data.engine_id}: free provider class; "
                f"net {record.net_savings_tokens} tokens, external cost $0.0000"
            ),
        )

    missing = _missing_metered_fields(input_data)
    if missing:
        record = NetSavingsRecord.from_estimates(
            engine_tokens_avoided=input_data.claude_inline_tokens_estimate or 0,
            chaperone_tokens_spent=input_data.chaperone_tokens_estimate or 0,
            external_cost_usd=input_data.estimated_external_cost_usd,
        )
        return _offload_decision(
            input_data,
            status="economics-missing-halt",
            proceed=False,
            net_savings=record,
            reason="missing required metered economics estimates: " + ", ".join(missing),
            missing_fields=missing,
            preview=(
                f"offload {input_data.engine_id}: halt; missing metered economics "
                f"estimates: {', '.join(missing)}"
            ),
        )

    assert input_data.estimated_external_cost_usd is not None
    assert input_data.provider_budget_ceiling_usd is not None
    assert input_data.claude_inline_tokens_estimate is not None
    assert input_data.chaperone_tokens_estimate is not None

    record = NetSavingsRecord.from_estimates(
        engine_tokens_avoided=input_data.claude_inline_tokens_estimate,
        chaperone_tokens_spent=input_data.chaperone_tokens_estimate,
        external_cost_usd=input_data.estimated_external_cost_usd,
    )
    if input_data.chaperone_tokens_estimate >= input_data.claude_inline_tokens_estimate:
        return _offload_decision(
            input_data,
            status="break-even-halt",
            proceed=False,
            net_savings=record,
            projected_provider_spend_usd=(
                input_data.prior_provider_spend_usd + input_data.estimated_external_cost_usd
            ),
            reason=(
                f"chaperone tokens {input_data.chaperone_tokens_estimate} >= "
                f"inline tokens {input_data.claude_inline_tokens_estimate}"
            ),
            preview=(
                f"offload {input_data.engine_id}: halt; chaperone "
                f"{input_data.chaperone_tokens_estimate} tokens >= inline "
                f"{input_data.claude_inline_tokens_estimate}; use "
                f"{input_data.inline_fallback}"
            ),
        )

    projected_spend = input_data.prior_provider_spend_usd + input_data.estimated_external_cost_usd
    if projected_spend > input_data.provider_budget_ceiling_usd:
        overshoot = projected_spend - input_data.provider_budget_ceiling_usd
        return _offload_decision(
            input_data,
            status="budget-ceiling-halt",
            proceed=False,
            net_savings=record,
            projected_provider_spend_usd=projected_spend,
            reason=(
                f"projected provider spend ${projected_spend:.4f} exceeds ceiling "
                f"${input_data.provider_budget_ceiling_usd:.4f} by ${overshoot:.4f}"
            ),
            preview=(
                f"offload {input_data.engine_id}: halt; provider spend "
                f"${projected_spend:.4f}/${input_data.provider_budget_ceiling_usd:.4f} "
                f"would exceed ceiling by ${overshoot:.4f}"
            ),
        )

    return _offload_decision(
        input_data,
        status="proceed",
        proceed=True,
        net_savings=record,
        projected_provider_spend_usd=projected_spend,
        preview=(
            f"offload {input_data.engine_id}: save {record.net_savings_tokens} tokens "
            f"(inline {record.engine_tokens_avoided} - chaperone "
            f"{record.chaperone_tokens_spent}); external cost "
            f"${input_data.estimated_external_cost_usd:.4f}; budget "
            f"${projected_spend:.4f}/${input_data.provider_budget_ceiling_usd:.4f}"
        ),
    )


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
    unsampled = tuple(
        unit_id for unit_id in decision.unit_ids if unit_id not in decision.sampled_unit_ids
    )
    return replace(
        decision,
        full_review_unit_ids=tuple(sorted(set(decision.full_review_unit_ids) | set(unsampled))),
        defective_sample_unit_ids=defects,
    )


def _validate_verifiability(value: str) -> Verifiability:
    if value not in VERIFIABILITY_VALUES:
        raise ChaperonePolicyError(f"verifiability {value!r} not in {VERIFIABILITY_VALUES}")
    return value  # type: ignore[return-value]


def _validate_sample_rating(value: str) -> SampleRating:
    if value not in SAMPLE_RATINGS:
        raise ChaperonePolicyError(f"sample rating {value!r} not in {SAMPLE_RATINGS}")
    return value  # type: ignore[return-value]


def _validate_cost_class(value: str) -> CostClass:
    if value not in COST_CLASSES:
        raise ChaperonePolicyError(f"cost_class {value!r} not in {COST_CLASSES}")
    return value  # type: ignore[return-value]


def _validate_non_negative_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ChaperonePolicyError(f"{name} must be an integer")
    if value < 0:
        raise ChaperonePolicyError(f"{name} must be >= 0")
    return value


def _validate_optional_non_negative_int(value: int | None, name: str) -> int | None:
    if value is None:
        return None
    return _validate_non_negative_int(value, name)


def _validate_non_negative_float(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ChaperonePolicyError(f"{name} must be a number")
    if value < 0:
        raise ChaperonePolicyError(f"{name} must be >= 0")
    return float(value)


def _validate_optional_non_negative_float(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    return _validate_non_negative_float(value, name)


def _missing_metered_fields(input_data: OffloadEconomicsInput) -> tuple[str, ...]:
    fields = (
        ("estimated_external_cost_usd", input_data.estimated_external_cost_usd),
        ("provider_budget_ceiling_usd", input_data.provider_budget_ceiling_usd),
        ("claude_inline_tokens_estimate", input_data.claude_inline_tokens_estimate),
        ("chaperone_tokens_estimate", input_data.chaperone_tokens_estimate),
    )
    return tuple(name for name, value in fields if value is None)


def _offload_decision(
    input_data: OffloadEconomicsInput,
    *,
    status: OffloadEconomicsStatus,
    proceed: bool,
    net_savings: NetSavingsRecord,
    preview: str,
    reason: str = "",
    missing_fields: tuple[str, ...] = (),
    projected_provider_spend_usd: float | None = None,
) -> OffloadEconomicsDecision:
    return OffloadEconomicsDecision(
        engine_id=input_data.engine_id,
        cost_class=input_data.cost_class,
        status=status,
        proceed=proceed,
        preview=preview,
        net_savings=net_savings,
        reason=reason,
        missing_fields=missing_fields,
        provider_budget_ceiling_usd=input_data.provider_budget_ceiling_usd,
        prior_provider_spend_usd=input_data.prior_provider_spend_usd,
        projected_provider_spend_usd=projected_provider_spend_usd,
        inline_fallback=input_data.inline_fallback,
    )


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
