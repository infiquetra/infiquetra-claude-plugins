#!/usr/bin/env python3
"""Plan a run: route each child, then stop.

This module decides the split and the route. It never launches a child. The
operator is shown the plan before :func:`commit_plan` writes reservations.
Dispatch is a later unit.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import admission
import completion
import fleet_commons_shim
import register as register_store

tier_resolver = fleet_commons_shim.load("tier_resolver")

DEFAULT_VENDOR_ORDER = ("claude", "codex", "grok", "qwen", "muse", "agy")
INTEGRATION_MODES = frozenset({"none", "branch", "path"})
SILENT_VENDORS = frozenset({"muse", "agy"})

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
    tokens_max: int
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
    """A run plan. Commit requires a presentation receipt, not a boolean."""

    run_id: str
    outcome: str
    children: tuple[PlannedChild, ...]
    ceiling: float | None = None
    per_vendor_limit: int = admission.DEFAULT_PER_VENDOR
    aggregate_limit: int = admission.DEFAULT_AGGREGATE


@dataclass(frozen=True)
class PresentationReceipt:
    """Digest of the rendered plan. The composition unit is the real producer."""

    run_id: str
    digest: str
    text: str


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


def _require_child_contract(row_id: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    scope = spec.get("scope")
    if not isinstance(scope, str) or not scope.strip():
        raise PlanningError(f"child {row_id!r} needs a non-empty scope")
    artifact = spec.get("artifact_path")
    if not isinstance(artifact, str) or not artifact.strip():
        raise PlanningError(f"child {row_id!r} needs a non-empty artifact_path")
    mode = spec.get("integration_mode")
    if not isinstance(mode, str) or mode not in INTEGRATION_MODES:
        raise PlanningError(
            f"child {row_id!r} needs an explicit integration_mode in {sorted(INTEGRATION_MODES)}"
        )
    try:
        predicate = completion.PredicateSpec.from_mapping(spec.get("predicate"))
    except completion.PredicateSchemaError as exc:
        raise PlanningError(f"child {row_id!r} predicate is not the closed schema: {exc}") from exc
    raw_max = spec.get("tokens_max")
    if isinstance(raw_max, bool) or not isinstance(raw_max, (int, float)) or int(raw_max) <= 0:
        raise PlanningError(f"child {row_id!r} needs a positive tokens_max")
    return {
        "scope": scope.strip(),
        "artifact_path": artifact.strip(),
        "integration_mode": mode,
        "predicate": predicate.to_mapping(),
        "tokens_max": int(raw_max),
    }


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
        contract = _require_child_contract(row_id, spec)
        routed = route(
            work_shape,
            vendor=spec.get("vendor"),
            model=spec.get("model"),
            effort=spec.get("effort"),
            is_vendor_available=is_vendor_available,
        )
        if routed.vendor in SILENT_VENDORS and ceiling is not None:
            # A silent vendor cannot prove actuals. The declared maximum is the
            # charge; it is not observed usage.
            pass
        planned.append(
            PlannedChild(
                row_id=row_id,
                task=str(spec.get("task") or outcome),
                work_shape=work_shape,
                execution_class=routed.execution_class,
                vendor=routed.vendor,
                model=routed.model,
                effort=routed.effort,
                scope=contract["scope"],
                artifact_path=contract["artifact_path"],
                predicate=dict(contract["predicate"]),
                integration_mode=contract["integration_mode"],
                tokens_reserved=contract["tokens_max"],
                tokens_max=contract["tokens_max"],
                substitutions=routed.substitutions,
                override=routed.override,
                policy_model=routed.policy_model,
                policy_effort=routed.policy_effort,
                fallbacks=routed.fallbacks,
                workspace_boundary=routed.workspace_boundary,
            )
        )
    resolved = admission.host_policy()
    return Plan(
        run_id=register_store._safe_run_id(run_id),
        outcome=outcome,
        children=tuple(planned),
        ceiling=ceiling,
        per_vendor_limit=resolved.per_vendor,
        aggregate_limit=resolved.aggregate,
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
    lines.append(
        f"Host bounds: per-vendor {built.per_vendor_limit}, aggregate {built.aggregate_limit}"
    )
    for child in built.children:
        lines.append(
            f"- {child.row_id}: {child.vendor} {child.model}/{child.effort} "
            f"shape={child.work_shape} class={child.execution_class} "
            f"tokens_max={child.tokens_max} reserved={child.tokens_reserved}"
        )
        lines.append(f"    scope: {child.scope}")
        lines.append(f"    artifact_path: {child.artifact_path}")
        lines.append(f"    integration_mode: {child.integration_mode}")
        lines.append(f"    predicate: {json.dumps(dict(child.predicate), sort_keys=True)}")
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


def plan_digest(built: Plan) -> str:
    return hashlib.sha256(render_plan(built).encode("utf-8")).hexdigest()


def presentation_receipt_path(run_id: str) -> Path:
    return register_store.register_dir() / f"{register_store._safe_run_id(run_id)}.presented"


def present_plan(built: Plan) -> tuple[Plan, str]:
    """Render the full child contract. Does not write a receipt. Launches nothing."""
    return built, render_plan(built)


def issue_presentation_receipt(built: Plan) -> PresentationReceipt:
    """Write the digest this commit will require.

    This unit is not the operator channel. The composition unit is the producer
    that should call this after the operator has actually been shown the text.
    """
    text = render_plan(built)
    receipt = PresentationReceipt(run_id=built.run_id, digest=plan_digest(built), text=text)
    path = presentation_receipt_path(built.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    register_store._atomic_write_json(
        path, {"run_id": receipt.run_id, "digest": receipt.digest, "text": receipt.text}
    )
    return receipt


def load_presentation_receipt(run_id: str) -> PresentationReceipt:
    path = presentation_receipt_path(run_id)
    if not path.exists():
        raise PlanningError(
            "no presentation receipt for this plan; the composition unit writes one "
            "after the operator channel delivers the rendered text"
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    return PresentationReceipt(str(raw["run_id"]), str(raw["digest"]), str(raw.get("text") or ""))


def commit_plan(
    built: Plan,
    root: Path,
    *,
    receipt: PresentationReceipt | None = None,
    per_vendor_limit: int | None = None,
    aggregate_limit: int | None = None,
    now: float | None = None,
) -> Plan:
    """Reserve slots and write planned rows. Requires a matching presentation receipt.

    Does not launch. A queued child is written as queued, not as an error.
    """
    shown = receipt if receipt is not None else load_presentation_receipt(built.run_id)
    expected = plan_digest(built)
    if shown.run_id != built.run_id or shown.digest != expected:
        raise PlanningError("presentation receipt does not match this plan")
    committed: list[PlannedChild] = []
    for child in built.children:
        decision = admission.reserve_slot(
            root,
            child.row_id,
            run_id=built.run_id,
            vendor=child.vendor,
            work_shape=child.execution_class,
            tokens_max=child.tokens_max,
            per_vendor_limit=per_vendor_limit,
            aggregate_limit=aggregate_limit,
            now=now,
        )
        register_store.upsert_row(
            root,
            child.row_id,
            {
                "phase": "planned",
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
                "tokens_reserved": child.tokens_max,
                "tokens_max": child.tokens_max,
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
