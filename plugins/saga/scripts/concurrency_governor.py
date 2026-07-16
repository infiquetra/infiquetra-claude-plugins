#!/usr/bin/env python3
"""Pure concurrency-policy schema and resolution helpers for Saga emitters.

The governor decides an authored wave width before workflow text is rendered. It does not launch,
sleep, retry, or maintain runtime state. Invalid policy inputs fail at the emit boundary instead of
being clamped into a different operator instruction.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import fleet_commons_shim

DEFAULT_MAX_CONCURRENT = 3
DEFAULT_READONLY_MAX_CONCURRENT = 4
DEFAULT_AGGREGATE_MAX_CONCURRENT = 7
MAX_CONCURRENT_ENV = "SAGA_MAX_CONCURRENT"

_cost_weights = fleet_commons_shim.load("cost_weights")
_BASELINE_WEIGHT = int(_cost_weights.to_spend("sonnet", "high"))
_POLICY_KEYS = frozenset({"max_concurrent", "readonly_max_concurrent", "aggregate_max_concurrent"})


class ConcurrencyPolicyError(ValueError):
    """A malformed or unsafe concurrency policy."""


class TierLike(Protocol):
    @property
    def model(self) -> str: ...

    @property
    def effort(self) -> str: ...


class SandboxLike(Protocol):
    @property
    def mutation_policy(self) -> str: ...


class UnitLike(Protocol):
    @property
    def unit_id(self) -> str: ...

    @property
    def tier(self) -> TierLike: ...

    @property
    def sandbox(self) -> SandboxLike | None: ...

    @property
    def engine(self) -> str | None: ...


@dataclass(frozen=True)
class ConcurrencyPolicy:
    """Closed serialized policy block for one execution specification."""

    max_concurrent: int = DEFAULT_MAX_CONCURRENT
    readonly_max_concurrent: int = DEFAULT_READONLY_MAX_CONCURRENT
    aggregate_max_concurrent: int = DEFAULT_AGGREGATE_MAX_CONCURRENT

    def validate(self, where: str = "concurrency") -> None:
        for name, value in self.to_dict().items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ConcurrencyPolicyError(f"{where}.{name} must be a positive integer")
        if self.max_concurrent > self.readonly_max_concurrent:
            raise ConcurrencyPolicyError(
                f"{where}: max_concurrent {self.max_concurrent} exceeds "
                f"readonly_max_concurrent {self.readonly_max_concurrent}"
            )
        if self.readonly_max_concurrent > self.aggregate_max_concurrent:
            raise ConcurrencyPolicyError(
                f"{where}: readonly_max_concurrent {self.readonly_max_concurrent} exceeds "
                f"aggregate_max_concurrent {self.aggregate_max_concurrent}"
            )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], where: str = "concurrency") -> ConcurrencyPolicy:
        unknown = sorted(set(data) - _POLICY_KEYS)
        if unknown:
            raise ConcurrencyPolicyError(f"{where}: unknown field(s): {', '.join(unknown)}")
        values: dict[str, int] = {}
        for key in _POLICY_KEYS:
            if key not in data:
                continue
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ConcurrencyPolicyError(f"{where}.{key} must be a positive integer")
            values[key] = value
        policy = cls(**values)
        policy.validate(where)
        return policy

    def to_dict(self) -> dict[str, int]:
        return {
            "max_concurrent": self.max_concurrent,
            "readonly_max_concurrent": self.readonly_max_concurrent,
            "aggregate_max_concurrent": self.aggregate_max_concurrent,
        }


@dataclass(frozen=True)
class ResolvedConcurrency:
    """One effective wave width plus the precedence rung that selected it."""

    width: int
    source: str


def _positive_width(value: Any, source: str, ceiling: int) -> int:
    if isinstance(value, bool):
        raise ConcurrencyPolicyError(f"{source} must be a positive integer")
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped.isascii() or not stripped.isdecimal() or stripped.startswith("0"):
            raise ConcurrencyPolicyError(f"{source} must be a canonical positive integer")
        parsed = int(stripped)
    elif isinstance(value, int):
        parsed = value
    else:
        raise ConcurrencyPolicyError(f"{source} must be a positive integer")
    if parsed < 1:
        raise ConcurrencyPolicyError(f"{source} must be a positive integer")
    if parsed > ceiling:
        raise ConcurrencyPolicyError(
            f"{source} width {parsed} exceeds aggregate_max_concurrent {ceiling}"
        )
    return parsed


def _all_explicit_readonly(units: Sequence[UnitLike]) -> bool:
    return bool(units) and all(
        unit.sandbox is not None and unit.sandbox.mutation_policy == "read-only" for unit in units
    )


def _pre_tier_width(
    policy: ConcurrencyPolicy,
    units: Sequence[UnitLike],
    environment: Mapping[str, str],
) -> tuple[int, str]:
    """Resolve the cohort-wide spec, environment, and read-only rungs."""

    width = policy.max_concurrent
    source = "spec"
    if MAX_CONCURRENT_ENV in environment:
        width = _positive_width(
            environment[MAX_CONCURRENT_ENV],
            MAX_CONCURRENT_ENV,
            policy.aggregate_max_concurrent,
        )
        source = "environment"
    if _all_explicit_readonly(units):
        width = max(width, policy.readonly_max_concurrent)
        source = "read-only"
    return width, source


def _tier_width(width: int, units: Sequence[UnitLike]) -> int:
    """Apply cost admission without widening the selected non-tier ceiling."""

    if not units:
        return width
    max_weight = max(
        int(_cost_weights.to_spend(unit.tier.model, unit.tier.effort)) for unit in units
    )
    weighted = max(1, (width * _BASELINE_WEIGHT) // max_weight)
    return min(width, weighted)


def _lane_key(
    unit: UnitLike,
    lane_limits: Mapping[str, int | None],
    lane_assignments: Mapping[str, str | None],
) -> str | None:
    selector = lane_assignments.get(unit.unit_id, unit.engine)
    if selector is None or lane_limits.get(selector) is None:
        return None
    return selector


def resolve_concurrency(
    policy: ConcurrencyPolicy,
    units: Sequence[UnitLike],
    *,
    environment: Mapping[str, str] | None = None,
    lane_limits: Mapping[str, int | None] | None = None,
    lane_assignments: Mapping[str, str | None] | None = None,
    run_override: int | None = None,
) -> ResolvedConcurrency:
    """Resolve spec, env, read-only, tier, lane, then explicit-run precedence."""

    policy.validate()
    environment = environment or {}
    lane_limits = lane_limits or {}
    lane_assignments = lane_assignments or {}
    width, source = _pre_tier_width(policy, units, environment)
    for lane_key in {
        _lane_key(unit, lane_limits, lane_assignments)
        for unit in units
        if _lane_key(unit, lane_limits, lane_assignments) is not None
    }:
        assert lane_key is not None
        lane_value = lane_limits[lane_key]
        assert lane_value is not None
        _positive_width(
            lane_value,
            f"engine lane max_concurrent ({lane_key})",
            policy.aggregate_max_concurrent,
        )

    if run_override is not None:
        return ResolvedConcurrency(
            width=_positive_width(
                run_override,
                "run max_concurrent override",
                policy.aggregate_max_concurrent,
            ),
            source="run",
        )

    width = _tier_width(width, units)
    if units:
        source = "tier"

    lane_keys = {_lane_key(unit, lane_limits, lane_assignments) for unit in units}
    lane_keys.discard(None)
    has_ordinary = any(_lane_key(unit, lane_limits, lane_assignments) is None for unit in units)
    if len(lane_keys) > 1 or (lane_keys and has_ordinary):
        raise ConcurrencyPolicyError(
            "mixed engine-lane cohort has no single concurrency width; use ordered_policy_chunks"
        )
    if lane_keys:
        lane_key = next(key for key in lane_keys if key is not None)
        lane_value = lane_limits[lane_key]
        assert lane_value is not None
        width = _positive_width(
            lane_value,
            f"engine lane max_concurrent ({lane_key})",
            policy.aggregate_max_concurrent,
        )
        source = "lane"

    return ResolvedConcurrency(width=width, source=source)


def ordered_policy_chunks[T: UnitLike](
    values: Sequence[T],
    policy: ConcurrencyPolicy,
    *,
    environment: Mapping[str, str] | None = None,
    lane_limits: Mapping[str, int | None] | None = None,
    lane_assignments: Mapping[str, str | None] | None = None,
    run_override: int | None = None,
) -> list[list[T]]:
    """Chunk a heterogeneous cohort while preserving local and exact-lane limits.

    Ordinary units share the resolved spec/environment/read-only/tier limit. Each configured,
    resolved external lane gets its own post-tier limit. Declaration order is stable; a chunk closes
    before adding a unit that would exceed either its bucket limit or the run-wide aggregate ceiling.
    """

    policy.validate()
    if not values:
        return []
    environment = environment or {}
    lane_limits = lane_limits or {}
    lane_assignments = lane_assignments or {}
    base_width, _source = _pre_tier_width(policy, values, environment)
    for lane_key in {
        _lane_key(unit, lane_limits, lane_assignments)
        for unit in values
        if _lane_key(unit, lane_limits, lane_assignments) is not None
    }:
        assert lane_key is not None
        lane_value = lane_limits[lane_key]
        assert lane_value is not None
        _positive_width(
            lane_value,
            f"engine lane max_concurrent ({lane_key})",
            policy.aggregate_max_concurrent,
        )

    bucket_limits: dict[str | None, int]
    if run_override is not None:
        global_width = _positive_width(
            run_override,
            "run max_concurrent override",
            policy.aggregate_max_concurrent,
        )
        bucket_limits = {
            _lane_key(unit, lane_limits, lane_assignments): global_width for unit in values
        }
    else:
        global_width = policy.aggregate_max_concurrent
        grouped: dict[str | None, list[T]] = {}
        for unit in values:
            grouped.setdefault(_lane_key(unit, lane_limits, lane_assignments), []).append(unit)
        bucket_limits = {}
        for key, units in grouped.items():
            tier_width = _tier_width(base_width, units)
            if key is None:
                bucket_limits[key] = tier_width
                continue
            lane_value = lane_limits[key]
            assert lane_value is not None
            bucket_limits[key] = _positive_width(
                lane_value,
                f"engine lane max_concurrent ({key})",
                policy.aggregate_max_concurrent,
            )

    return _bounded_ordered_chunks(
        values,
        global_width=global_width,
        bucket_key=lambda unit: _lane_key(unit, lane_limits, lane_assignments),
        bucket_limits=bucket_limits,
    )


def _bounded_ordered_chunks[T, K: Hashable](
    values: Sequence[T],
    *,
    global_width: int,
    bucket_key: Callable[[T], K],
    bucket_limits: Mapping[K, int],
) -> list[list[T]]:
    """One stable chunk primitive for uniform and bucket-aware cohorts."""

    if global_width < 1:
        raise ConcurrencyPolicyError("chunk width must be a positive integer")
    if any(width < 1 for width in bucket_limits.values()):
        raise ConcurrencyPolicyError("bucket chunk width must be a positive integer")

    chunks: list[list[T]] = []
    current: list[T] = []
    counts: dict[K, int] = {}
    for unit in values:
        key = bucket_key(unit)
        if key not in bucket_limits:
            raise ConcurrencyPolicyError(f"missing chunk limit for bucket {key!r}")
        would_exceed = len(current) >= global_width or counts.get(key, 0) >= bucket_limits[key]
        if current and would_exceed:
            chunks.append(current)
            current = []
            counts = {}
        current.append(unit)
        counts[key] = counts.get(key, 0) + 1
    if current:
        chunks.append(current)
    return chunks


def ordered_chunks[T](values: Sequence[T], width: int) -> list[list[T]]:
    """Split values into stable, non-empty chunks while preserving declaration order."""

    return _bounded_ordered_chunks(
        values,
        global_width=width,
        bucket_key=lambda _value: None,
        bucket_limits={None: width},
    )
