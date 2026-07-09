#!/usr/bin/env python3
"""Recommend viable Saga external-engine candidates without dispatching them."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine_registry import (  # noqa: E402
    CAPABILITIES,
    RATINGS,
    CapabilityCandidate,
    Registry,
    RegistryError,
)

POLICIES = ("cheapest-viable", "free-first")
DEFAULT_MIN_RATING = "MODERATE"
_RATING_SCORE = {rating: index for index, rating in enumerate(RATINGS, start=1)}

RecommendationStatus = Literal["ok", "empty", "halted"]


@dataclass(frozen=True)
class RecommendationTask:
    """Task shape used to rank advisory engine candidates."""

    capability: str
    policy: str = "cheapest-viable"
    sensitive: bool = False
    token_estimate: int | None = None
    min_rating: str = DEFAULT_MIN_RATING
    limit: int | None = None


@dataclass(frozen=True)
class RecommendationCandidate:
    """One viable advisory candidate with dispatch-relevant metadata copied from the registry."""

    key: str
    engine_id: str
    variant: str
    capability: str
    rating: str
    substrate: str
    egress_policy: str
    context_window: int
    cost_speed_rank: int
    registry_order: int
    cost_per_token: dict[str, float]
    unit_price_usd: float
    cost_class: str
    budget_ceiling_usd: float | None
    latency_class: str
    prompting_protocol: list[str]
    transport: str
    receipt_emitter: str
    reason: str


@dataclass(frozen=True)
class RecommendationResult:
    """Advisory recommendation ladder for one task."""

    status: RecommendationStatus
    capability: str
    policy: str
    sensitive: bool
    min_rating: str
    token_estimate: int | None
    candidates: tuple[RecommendationCandidate, ...]
    reason: str | None = None

    @property
    def recommended(self) -> RecommendationCandidate | None:
        return self.candidates[0] if self.candidates else None

    def next_rung(self, index: int = 1) -> RecommendationCandidate | None:
        if index < 0:
            raise RegistryError("next_rung index must be non-negative")
        try:
            return self.candidates[index]
        except IndexError:
            return None


def recommend(
    task: RecommendationTask | Mapping[str, Any],
    *,
    registry: Registry,
    overlay: Any | None = None,
) -> RecommendationResult:
    """Return a read-only recommendation ladder for a task.

    Recommendation uses the registry's existing ranked candidates as its source of truth,
    then filters by viability and applies the selected advisory ordering policy. It does
    not call resolver preflight, dispatch, or write any manifest/gate state.
    """

    normalized = _coerce_task(task)
    _validate_task(normalized, registry)

    try:
        ranked = registry.ranked_candidates(normalized.capability, overlay=overlay)
    except RegistryError as exc:
        if _capability_is_known(normalized.capability, registry) and "supports capability" in str(
            exc
        ):
            return _empty_result(normalized, "empty", str(exc))
        raise

    viable = [
        candidate
        for candidate in ranked
        if _meets_rating_floor(candidate, normalized.min_rating)
        and _fits_context(candidate, normalized.token_estimate)
    ]
    if normalized.sensitive:
        viable = [
            candidate for candidate in viable if candidate.entry.egress_policy == "local-only"
        ]
        if not viable:
            return _empty_result(
                normalized,
                "halted",
                (
                    f"no local-only candidate supports capability {normalized.capability!r} "
                    f"at min_rating {normalized.min_rating}"
                ),
            )

    if not viable:
        return _empty_result(
            normalized,
            "empty",
            (
                f"no viable candidate supports capability {normalized.capability!r} "
                f"at min_rating {normalized.min_rating}"
            ),
        )

    ordered = _order_candidates(viable, normalized.policy)
    if normalized.limit is not None:
        ordered = ordered[: normalized.limit]

    return RecommendationResult(
        status="ok",
        capability=normalized.capability,
        policy=normalized.policy,
        sensitive=normalized.sensitive,
        min_rating=normalized.min_rating,
        token_estimate=normalized.token_estimate,
        candidates=tuple(_candidate_payload(candidate) for candidate in ordered),
    )


def _coerce_task(task: RecommendationTask | Mapping[str, Any]) -> RecommendationTask:
    if isinstance(task, RecommendationTask):
        return RecommendationTask(
            capability=_required_string(task.capability, "capability"),
            policy=_required_string(task.policy, "policy"),
            sensitive=_optional_bool(task.sensitive, "sensitive"),
            token_estimate=_optional_int(task.token_estimate, "token_estimate"),
            min_rating=_required_string(task.min_rating, "min_rating"),
            limit=_optional_int(task.limit, "limit"),
        )
    if not isinstance(task, Mapping):
        raise RegistryError("recommendation task must be a mapping or RecommendationTask")
    capability = task.get("capability")
    return RecommendationTask(
        capability=_required_string(capability, "capability"),
        policy=_required_string(task.get("policy", "cheapest-viable"), "policy"),
        sensitive=_optional_bool(task.get("sensitive", False), "sensitive"),
        token_estimate=_optional_int(task.get("token_estimate"), "token_estimate"),
        min_rating=_required_string(task.get("min_rating", DEFAULT_MIN_RATING), "min_rating"),
        limit=_optional_int(task.get("limit"), "limit"),
    )


def _validate_task(task: RecommendationTask, registry: Registry) -> None:
    if task.capability not in CAPABILITIES:
        raise RegistryError(f"unknown capability key {task.capability!r}")
    if task.capability not in registry.capabilities:
        raise RegistryError(f"capability {task.capability!r} is not declared in this registry")
    if task.policy not in POLICIES:
        raise RegistryError(f"recommendation policy {task.policy!r} not in {POLICIES}")
    if task.min_rating not in RATINGS:
        raise RegistryError(f"min_rating {task.min_rating!r} not in {RATINGS}")
    if task.limit is not None and task.limit <= 0:
        raise RegistryError("limit must be a positive integer")


def _optional_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise RegistryError(f"{field} must be a boolean")
    return value


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise RegistryError(f"{field} must be a non-empty string")
    return value


def _optional_int(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise RegistryError(f"{field} must be an integer")
    if value < 0:
        raise RegistryError(f"{field} must be non-negative")
    return value


def _capability_is_known(capability: str, registry: Registry) -> bool:
    return capability in CAPABILITIES and capability in registry.capabilities


def _meets_rating_floor(candidate: CapabilityCandidate, min_rating: str) -> bool:
    return candidate.rating_score >= _RATING_SCORE[min_rating]


def _fits_context(candidate: CapabilityCandidate, token_estimate: int | None) -> bool:
    return token_estimate is None or token_estimate <= candidate.entry.context_window


def _order_candidates(
    candidates: list[CapabilityCandidate],
    policy: str,
) -> list[CapabilityCandidate]:
    if policy == "free-first":
        return sorted(
            candidates,
            key=lambda candidate: (
                0 if candidate.entry.cost_class == "free" else 1,
                candidate.entry.registry_order,
            ),
        )
    if policy == "cheapest-viable":
        return sorted(
            candidates,
            key=lambda candidate: (
                _unit_price(candidate),
                candidate.entry.cost_speed_rank,
                candidate.entry.registry_order,
            ),
        )
    raise RegistryError(f"recommendation policy {policy!r} not in {POLICIES}")


def _candidate_payload(candidate: CapabilityCandidate) -> RecommendationCandidate:
    entry = candidate.entry
    return RecommendationCandidate(
        key=entry.key,
        engine_id=entry.engine_id,
        variant=entry.variant,
        capability=candidate.capability,
        rating=candidate.rating,
        substrate=entry.substrate,
        egress_policy=entry.egress_policy,
        context_window=entry.context_window,
        cost_speed_rank=entry.cost_speed_rank,
        registry_order=entry.registry_order,
        cost_per_token=dict(entry.cost_per_token),
        unit_price_usd=_unit_price(candidate),
        cost_class=entry.cost_class,
        budget_ceiling_usd=entry.budget_ceiling_usd,
        latency_class=entry.latency_class,
        prompting_protocol=list(entry.prompting_protocol),
        transport=entry.transport,
        receipt_emitter=entry.receipt_emitter,
        reason=candidate.reason,
    )


def _unit_price(candidate: CapabilityCandidate) -> float:
    return float(candidate.entry.cost_per_token["input_usd"]) + float(
        candidate.entry.cost_per_token["output_usd"]
    )


def _empty_result(
    task: RecommendationTask,
    status: RecommendationStatus,
    reason: str,
) -> RecommendationResult:
    return RecommendationResult(
        status=status,
        capability=task.capability,
        policy=task.policy,
        sensitive=task.sensitive,
        min_rating=task.min_rating,
        token_estimate=task.token_estimate,
        candidates=(),
        reason=reason,
    )
