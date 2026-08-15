#!/usr/bin/env python3
"""Plan a run: route each child, then stop.

This module decides the split and the route. It never launches a child. The
operator is shown the plan before :func:`commit_plan` writes reservations.
Dispatch is a later unit.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import admission
import fleet_commons_shim
import register as register_store

tier_resolver = fleet_commons_shim.load("tier_resolver")

DEFAULT_VENDOR_ORDER = ("claude", "codex", "grok", "qwen", "muse", "agy")

# Portable work-shape names (tier_policy.json / role-tier aliases) onto the
# execution-class vocabulary that resolve_for_runtime understands. Execution
# class names pass through unchanged.
SHAPE_TO_EXECUTION_CLASS: dict[str, str] = {
    "judgment": "review-high",
    "adversarial-review": "review-high",
    "second-opinion": "review-max",
    "divergence": "review-high",
    "mechanical": "work-medium",
    "contract-test": "test-medium",
    "purely-mechanical": "scan-low",
    "mechanical-scan": "scan-low",
    "read-only-survey": "scan-low",
    "offload-test-gated": "test-medium",
    "offload": "work-medium",
}


class PlanningError(Exception):
    """The plan could not be built, shown, or committed."""


@dataclass(frozen=True)
class RouteDecision:
    """One child's vendor, model, and effort, with every substitution recorded."""

    vendor: str
    model: str
    effort: str
    work_shape: str
    execution_class: str
    policy_model: str
    policy_effort: str
    fallbacks: tuple[dict[str, str], ...]
    substitutions: tuple[dict[str, str], ...]
    override: dict[str, str] | None
    workspace_boundary: str
    effort_application: dict[str, str]
    tokens_reserved: int


@dataclass(frozen=True)
class PlannedChild:
    """One child on a plan. Nothing here has been launched."""

    row_id: str
    task: str
    work_shape: str
    execution_class: str
    vendor: str
    model: str
    effort: str
    scope: str
    artifact_path: str
    predicate: Mapping[str, Any]
    integration_mode: str
    tokens_reserved: int
    substitutions: tuple[dict[str, str], ...]
    override: dict[str, str] | None
    policy_model: str
    policy_effort: str
    fallbacks: tuple[dict[str, str], ...]
    workspace_boundary: str
    admission: str | None = None
    admission_reason: str = ""


@dataclass(frozen=True)
class Plan:
    """A run plan. ``presented`` is the operator-seen flag :func:`commit_plan` requires."""

    run_id: str
    outcome: str
    children: tuple[PlannedChild, ...]
    presented: bool = False
    ceiling: float | None = None


def execution_class_for(work_shape: str) -> str:
    """Map a work shape or role-tier alias onto an execution class."""
    if work_shape in SHAPE_TO_EXECUTION_CLASS:
        return SHAPE_TO_EXECUTION_CLASS[work_shape]
    classes = tier_resolver._execution_classes()
    if work_shape in classes:
        return work_shape
    raise PlanningError(
        f"unknown work_shape {work_shape!r}; expected a tier_policy key, "
        f"a role-tier alias, or an execution class in {sorted(classes)}"
    )


def _policy_tier(work_shape: str) -> tuple[str, str]:
    try:
        resolution = tier_resolver.resolve(None, work_shape)
    except tier_resolver.TierResolverError:
        return "", ""
    return resolution.model, resolution.effort


def _vendor_candidates(preferred: str) -> tuple[str, ...]:
    rest = [vendor for vendor in DEFAULT_VENDOR_ORDER if vendor != preferred]
    return (preferred, *rest)


def route(
    work_shape: str,
    *,
    vendor: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    is_vendor_available: Callable[[str], bool] | None = None,
) -> RouteDecision:
    """Resolve vendor, model, and effort for one child.

    Availability is injected so a test can take a vendor away. The default treats
    every supported runtime as available — PATH probing is the caller's job.
    """
    available = is_vendor_available or (lambda _vendor: True)
    execution_class = execution_class_for(work_shape)
    policy_model, policy_effort = _policy_tier(work_shape)
    requested_vendor = vendor or DEFAULT_VENDOR_ORDER[0]
    override: dict[str, str] | None = None
    if vendor is not None:
        override = {"kind": "explicit", "field": "vendor", "value": vendor}
    substitutions: list[dict[str, str]] = []
    skipped: list[str] = []
    selected_vendor: str | None = None
    for candidate in _vendor_candidates(requested_vendor):
        if available(candidate):
            selected_vendor = candidate
            if candidate != requested_vendor:
                substitutions.append(
                    {
                        "field": "vendor",
                        "from": requested_vendor,
                        "to": candidate,
                        "reason": (
                            f"{requested_vendor} unavailable; skipped also: "
                            f"{', '.join(skipped) if skipped else '(none)'}"
                        ),
                    }
                )
            break
        skipped.append(candidate)
    if selected_vendor is None:
        raise PlanningError(
            f"no available vendor for {work_shape!r}; tried {_vendor_candidates(requested_vendor)}"
        )
    resolved = tier_resolver.resolve_for_runtime(execution_class, selected_vendor)
    chosen_model = model if model is not None else resolved.model
    chosen_effort = effort if effort is not None else resolved.effort
    if model is not None:
        extra = {"kind": "explicit", "field": "model", "value": model}
        override = extra if override is None else {**override, "model": model}
        if model != resolved.model:
            substitutions.append(
                {
                    "field": "model",
                    "from": resolved.model,
                    "to": model,
                    "reason": "explicit operator model override",
                }
            )
    if effort is not None:
        if override is None:
            override = {"kind": "explicit", "field": "effort", "value": effort}
        else:
            override = {**override, "effort": effort}
        if effort != resolved.effort:
            substitutions.append(
                {
                    "field": "effort",
                    "from": resolved.effort,
                    "to": effort,
                    "reason": "explicit operator effort override",
                }
            )
    return RouteDecision(
        vendor=selected_vendor,
        model=chosen_model,
        effort=chosen_effort,
        work_shape=work_shape,
        execution_class=execution_class,
        policy_model=policy_model,
        policy_effort=policy_effort,
        fallbacks=tuple(dict(item) for item in resolved.fallbacks),
        substitutions=tuple(substitutions),
        override=override,
        workspace_boundary=resolved.workspace_boundary,
        effort_application=dict(resolved.effort_application),
        tokens_reserved=admission.reserved_tokens_for(execution_class),
    )


def plan(
    outcome: str,
    children: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    ceiling: float | None = None,
    is_vendor_available: Callable[[str], bool] | None = None,
) -> Plan:
    """Build a plan from child declarations. Writes nothing. Launches nothing."""
    if not outcome.strip():
        raise PlanningError("outcome must be non-empty")
    if not children:
        raise PlanningError("a plan needs at least one child")
    planned: list[PlannedChild] = []
    seen: set[str] = set()
    for index, spec in enumerate(children):
        row_id = str(spec.get("row_id") or f"child-{index + 1}")
        if row_id in seen:
            raise PlanningError(f"duplicate child row_id {row_id!r}")
        seen.add(row_id)
        work_shape = str(spec.get("work_shape") or "")
        if not work_shape:
            raise PlanningError(f"child {row_id!r} is missing work_shape")
        routed = route(
            work_shape,
            vendor=spec.get("vendor"),
            model=spec.get("model"),
            effort=spec.get("effort"),
            is_vendor_available=is_vendor_available,
        )
        predicate = spec.get("predicate")
        if not isinstance(predicate, Mapping):
            predicate = {
                "argv": ["true"],
                "timeout_seconds": 30.0,
                "max_output_bytes": 4096,
            }
        planned.append(
            PlannedChild(
                row_id=row_id,
                task=str(spec.get("task") or outcome),
                work_shape=work_shape,
                execution_class=routed.execution_class,
                vendor=routed.vendor,
                model=routed.model,
                effort=routed.effort,
                scope=str(spec.get("scope") or ""),
                artifact_path=str(spec.get("artifact_path") or ""),
                predicate=dict(predicate),
                integration_mode=str(spec.get("integration_mode") or "none"),
                tokens_reserved=routed.tokens_reserved,
                substitutions=routed.substitutions,
                override=routed.override,
                policy_model=routed.policy_model,
                policy_effort=routed.policy_effort,
                fallbacks=routed.fallbacks,
                workspace_boundary=routed.workspace_boundary,
            )
        )
    return Plan(
        run_id=register_store._safe_run_id(run_id),
        outcome=outcome,
        children=tuple(planned),
        presented=False,
        ceiling=ceiling,
    )


def render_plan(built: Plan) -> str:
    """Plain-text plan the operator sees before any reservation is written."""
    lines = [
        f"Plan for run {built.run_id}",
        f"Outcome: {built.outcome}",
        f"Children: {len(built.children)}",
    ]
    if built.ceiling is not None:
        lines.append(f"Spend ceiling: {built.ceiling:g} tokens")
    for child in built.children:
        lines.append(
            f"- {child.row_id}: {child.vendor} {child.model}/{child.effort} "
            f"shape={child.work_shape} class={child.execution_class} "
            f"reserved={child.tokens_reserved}"
        )
        if child.override is not None:
            lines.append(f"    override: {child.override}")
        for item in child.substitutions:
            lines.append(
                f"    substitution: {item.get('field')} "
                f"{item.get('from')} -> {item.get('to')} ({item.get('reason')})"
            )
        if child.admission:
            lines.append(f"    admission: {child.admission} ({child.admission_reason})")
    return "\n".join(lines) + "\n"


def present_plan(built: Plan) -> tuple[Plan, str]:
    """Mark the plan as shown. Writes nothing. Launches nothing."""
    text = render_plan(built)
    return replace(built, presented=True), text


def commit_plan(
    built: Plan,
    root: Path,
    *,
    per_vendor_limit: int = admission.DEFAULT_PER_VENDOR,
    aggregate_limit: int = admission.DEFAULT_AGGREGATE,
    now: float | None = None,
) -> Plan:
    """Reserve slots and write planned rows. Refuses unless the plan was presented.

    Does not launch. A queued child is written as queued, not as an error.
    """
    if not built.presented:
        raise PlanningError("the operator has not been shown this plan")
    committed: list[PlannedChild] = []
    for child in built.children:
        decision = admission.reserve_slot(
            root,
            child.row_id,
            run_id=built.run_id,
            vendor=child.vendor,
            work_shape=child.execution_class,
            per_vendor_limit=per_vendor_limit,
            aggregate_limit=aggregate_limit,
            now=now,
        )
        register_store.upsert_row(
            root,
            child.row_id,
            {
                "task": child.task,
                "work_shape": child.work_shape,
                "execution_class": child.execution_class,
                "vendor": child.vendor,
                "agent": child.vendor,
                "model": child.model,
                "effort": child.effort,
                "scope": child.scope,
                "artifact_path": child.artifact_path,
                "predicate": dict(child.predicate),
                "integration_mode": child.integration_mode,
                "tokens_reserved": child.tokens_reserved,
                "substitutions": [dict(item) for item in child.substitutions],
                "override": dict(child.override) if child.override else None,
                "workspace_boundary": child.workspace_boundary,
            },
            run_id=built.run_id,
        )
        committed.append(
            replace(
                child,
                admission=decision.status,
                admission_reason=decision.reason,
            )
        )
    return replace(built, children=tuple(committed))
