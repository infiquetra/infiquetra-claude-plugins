#!/usr/bin/env python3
"""Plan a run: route each child, then stop.

This module decides the split and the route. It never launches a child. The
operator is shown the plan before :func:`commit_plan` writes reservations.
Dispatch is a later unit.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import stat
import uuid
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
    scope: tuple[str, ...]
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
    """Digest of the rendered plan, bound to one register generation."""

    run_id: str
    digest: str
    text: str
    generation: str


@dataclass(frozen=True, slots=True)
class SafePlanEdit:
    """An exact, review-authored replacement that is safe only when uniquely anchored."""

    before: str
    after: str

    def __post_init__(self) -> None:
        if not self.before:
            raise PlanningError("a safe plan edit needs non-empty text to replace")
        if self.before == self.after:
            raise PlanningError("a safe plan edit must change the plan")


@dataclass(frozen=True, slots=True)
class PlanRigorFinding:
    """One evidence-backed finding from the rigor pass.

    ``safe_edit`` is absent when the operator must decide the remainder. The recommendation is
    required in both cases so an edit that becomes unsafe still has a useful handoff.
    """

    finding_id: str
    summary: str
    evidence: str
    recommendation: str
    safe_edit: SafePlanEdit | None = None

    def __post_init__(self) -> None:
        for field_name in ("finding_id", "summary", "evidence", "recommendation"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise PlanningError(f"plan rigor {field_name} must be a non-empty string")
            object.__setattr__(self, field_name, value.strip())
        if self.safe_edit is not None and not isinstance(self.safe_edit, SafePlanEdit):
            raise PlanningError("safe_edit must be a SafePlanEdit")


@dataclass(frozen=True, slots=True)
class AppliedPlanFix:
    """A safe edit applied to the plan from a uniquely anchored finding."""

    finding_id: str
    evidence: str
    before: str
    after: str


@dataclass(frozen=True, slots=True)
class PlanRigorRemainder:
    """A finding handed to the operator with a recommendation."""

    finding_id: str
    summary: str
    evidence: str
    recommendation: str
    reason: str


@dataclass(frozen=True, slots=True)
class PlanRigorReport:
    """Safe fixes and remaining choices handed to the orchestration plan's only voter.

    The slotted type has no decision field. It cannot acquire one dynamically, so this pass can
    report and edit but cannot manufacture the operator's decision.
    """

    plan_path: Path
    applied: tuple[AppliedPlanFix, ...]
    remaining: tuple[PlanRigorRemainder, ...]


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
    raw_scope = spec.get("scope")
    if isinstance(raw_scope, str):
        scope_seq: tuple[str, ...] = (raw_scope,)
    elif isinstance(raw_scope, Sequence) and not isinstance(raw_scope, (bytes, bytearray)):
        scope_seq = tuple(str(item) for item in raw_scope)
    else:
        raise PlanningError(f"child {row_id!r} needs a non-empty scope")
    try:
        scope = register_store.normalize_repo_relative_paths(scope_seq, what="scope")
    except register_store.RegisterError as exc:
        raise PlanningError(f"child {row_id!r} {exc}") from exc
    artifact = spec.get("artifact_path")
    if not isinstance(artifact, str) or not artifact.strip():
        raise PlanningError(f"child {row_id!r} needs a non-empty artifact_path")
    try:
        declared = register_store.normalize_repo_relative_paths(
            (artifact.strip(),), what="artifact_path"
        )
    except register_store.RegisterError as exc:
        raise PlanningError(f"child {row_id!r} {exc}") from exc
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
    if isinstance(raw_max, bool) or not isinstance(raw_max, int) or raw_max <= 0:
        raise PlanningError(f"child {row_id!r} needs a positive integer tokens_max")
    return {
        "scope": scope,
        "artifact_path": declared[0],
        "integration_mode": mode,
        "predicate": predicate.to_mapping(),
        "tokens_max": raw_max,
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
        lines.append(f"    scope: {', '.join(child.scope)}")
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
    return register_store.presentation_sidecar_path(run_id)


def _mint_generation(run_id: str) -> str:
    """Return this run's generation, creating the sidecar only when none exists.

    An empty or unreadable sidecar is absent. If the live register already
    carries a stamp, restore that generation rather than minting a second one.
    The write is atomic and holds the generation lock.
    """
    with register_store.generation_locked(run_id):
        existing = register_store.read_generation_sidecar(run_id)
        if existing:
            return existing
        stamped = register_store.stamped_generation(run_id)
        generation = stamped if stamped else uuid.uuid4().hex
        register_store.write_generation_sidecar(run_id, generation)
        return generation


def present_plan(built: Plan) -> tuple[Plan, str]:
    """Render the full child contract. Does not write a receipt. Launches nothing."""
    return built, render_plan(built)


def run_plan_rigor_pass(
    plan_path: Path,
    findings: Sequence[PlanRigorFinding],
    *,
    expected_digest: str,
) -> PlanRigorReport:
    """Apply uniquely anchored safe edits and hand every other finding to the operator.

    Evidence and recommendations are mandatory on :class:`PlanRigorFinding`. A proposed edit is
    applied only when its exact ``before`` text occurs once in the bytes the reviewer examined.
    An absent, ambiguous, or overlapping anchor becomes a remainder instead of a guessed edit. All
    accepted edits land in one atomic write after the complete pass, provided the file still has
    the caller's expected digest.
    """
    if not isinstance(plan_path, Path):
        raise PlanningError("plan_path must be a pathlib.Path")
    if plan_path.is_symlink():
        raise PlanningError(f"orchestration plan must not be a symlink: {plan_path}")
    if not plan_path.is_file():
        raise PlanningError(f"orchestration plan is not a file: {plan_path}")
    if isinstance(findings, str | bytes) or not isinstance(findings, Sequence):
        raise PlanningError("plan rigor findings must be a sequence")
    _require_file_digest(expected_digest)

    original_bytes = plan_path.read_bytes()
    actual_digest = _bytes_digest(original_bytes)
    if actual_digest != expected_digest:
        raise PlanningError("orchestration plan changed after the findings were authored")
    try:
        text = original_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PlanningError(f"orchestration plan is not valid UTF-8: {plan_path}") from exc
    applied: list[AppliedPlanFix] = []
    remaining: list[PlanRigorRemainder] = []
    accepted: list[tuple[int, int, SafePlanEdit]] = []
    seen: set[str] = set()
    finding_by_id: dict[str, PlanRigorFinding] = {}
    for finding in findings:
        if not isinstance(finding, PlanRigorFinding):
            raise PlanningError("plan rigor findings must be PlanRigorFinding values")
        if finding.finding_id in seen:
            raise PlanningError(f"duplicate plan rigor finding_id {finding.finding_id!r}")
        seen.add(finding.finding_id)
        finding_by_id[finding.finding_id] = finding
        edit = finding.safe_edit
        if edit is None:
            remaining.append(_rigor_remainder(finding, reason="operator decision required"))
            continue
        offsets = _anchor_offsets(text, edit.before)
        occurrences = len(offsets)
        if occurrences != 1:
            remaining.append(
                _rigor_remainder(
                    finding,
                    reason=f"safe edit expected one anchor and found {occurrences}",
                )
            )
            continue
        start = offsets[0]
        end = start + len(edit.before)
        if any(
            start < accepted_end and accepted_start < end
            for accepted_start, accepted_end, _ in accepted
        ):
            remaining.append(
                _rigor_remainder(
                    finding,
                    reason="safe edit overlaps a previously accepted anchor",
                )
            )
            continue
        accepted.append((start, end, edit))
        applied.append(
            AppliedPlanFix(
                finding_id=finding.finding_id,
                evidence=finding.evidence,
                before=edit.before,
                after=edit.after,
            )
        )

    revised = text
    for start, end, edit in sorted(accepted, key=lambda item: item[0], reverse=True):
        revised = f"{revised[:start]}{edit.after}{revised[end:]}"
    if revised == text and applied:
        remaining.extend(
            _rigor_remainder(
                finding_by_id[item.finding_id],
                reason="composed safe edits leave the plan byte-identical",
            )
            for item in applied
        )
        applied.clear()
    elif revised != text:
        _atomic_write_plan_text(plan_path, revised, expected_digest=actual_digest)
    return PlanRigorReport(
        plan_path=plan_path,
        applied=tuple(applied),
        remaining=tuple(remaining),
    )


def _rigor_remainder(finding: PlanRigorFinding, *, reason: str) -> PlanRigorRemainder:
    return PlanRigorRemainder(
        finding_id=finding.finding_id,
        summary=finding.summary,
        evidence=finding.evidence,
        recommendation=finding.recommendation,
        reason=reason,
    )


def plan_file_digest(plan_path: Path) -> str:
    """Return the SHA-256 digest a caller must bind to rigor findings."""
    if not isinstance(plan_path, Path):
        raise PlanningError("plan_path must be a pathlib.Path")
    if plan_path.is_symlink():
        raise PlanningError(f"orchestration plan must not be a symlink: {plan_path}")
    if not plan_path.is_file():
        raise PlanningError(f"orchestration plan is not a file: {plan_path}")
    return _bytes_digest(plan_path.read_bytes())


def _anchor_offsets(text: str, anchor: str) -> tuple[int, ...]:
    offsets: list[int] = []
    start = 0
    while True:
        found = text.find(anchor, start)
        if found < 0:
            return tuple(offsets)
        offsets.append(found)
        start = found + 1


def _bytes_digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_file_digest(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PlanningError("expected_digest must be a lowercase SHA-256 digest")
    return value


def _atomic_write_plan_text(path: Path, text: str, *, expected_digest: str) -> None:
    """Replace a repository plan atomically without changing its permission bits."""
    if path.is_symlink():
        raise PlanningError(f"orchestration plan must not be a symlink: {path}")
    current_bytes = path.read_bytes()
    if _bytes_digest(current_bytes) != expected_digest:
        raise PlanningError("orchestration plan changed while the rigor pass was running")
    mode = stat.S_IMODE(path.stat().st_mode)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(text.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        if path.is_symlink() or _bytes_digest(path.read_bytes()) != expected_digest:
            raise PlanningError("orchestration plan changed while the rigor pass was running")
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


def issue_presentation_receipt(built: Plan) -> PresentationReceipt:
    """Write the digest this commit will require.

    This unit is not the operator channel. The composition unit is the producer
    that should call this after the operator has actually been shown the text.
    The receipt is bound to a generation sidecar that ``retire_run`` forgets
    with the live register.
    """
    text = render_plan(built)
    generation = _mint_generation(built.run_id)
    receipt = PresentationReceipt(
        run_id=built.run_id,
        digest=plan_digest(built),
        text=text,
        generation=generation,
    )
    path = presentation_receipt_path(built.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    register_store._atomic_write_json(
        path,
        {
            "run_id": receipt.run_id,
            "digest": receipt.digest,
            "text": receipt.text,
            "generation": receipt.generation,
        },
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
    generation = str(raw.get("generation") or "")
    stored = register_store.read_generation_sidecar(run_id)
    if not generation or stored is None:
        raise PlanningError("presentation receipt is not bound to a live generation")
    if stored != generation:
        raise PlanningError("presentation receipt generation does not match this run")
    return PresentationReceipt(
        str(raw["run_id"]),
        str(raw["digest"]),
        str(raw.get("text") or ""),
        generation,
    )


def _require_matching_host_policy(built: Plan) -> None:
    current = admission.host_policy()
    if current.per_vendor != built.per_vendor_limit or current.aggregate != built.aggregate_limit:
        raise PlanningError(
            "host policy drifted: rendered per-vendor "
            f"{built.per_vendor_limit}, aggregate {built.aggregate_limit}; "
            f"current per-vendor {current.per_vendor}, aggregate {current.aggregate}"
        )


def commit_plan(
    built: Plan,
    root: Path,
    *,
    receipt: PresentationReceipt | None = None,
    now: float | None = None,
) -> Plan:
    """Reserve slots and write planned rows. Requires a matching presentation receipt.

    Does not launch. A queued child is written as queued, not as an error.
    The durable host policy must still equal the rendered bounds. This function
    does not accept a per-call limit the rendered plan does not own.
    """
    shown = receipt if receipt is not None else load_presentation_receipt(built.run_id)
    expected = plan_digest(built)
    if shown.run_id != built.run_id or shown.digest != expected:
        raise PlanningError("presentation receipt does not match this plan")
    if not shown.generation:
        raise PlanningError("presentation receipt is not bound to a live generation")
    claimed = register_store.canonical_work_location(root)
    committed: list[PlannedChild] = []
    with (
        admission.admission_locked(),
        register_store.generation_locked(built.run_id),
    ):
        _require_matching_host_policy(built)
        if register_store.read_generation_sidecar(built.run_id) != shown.generation:
            raise PlanningError("presentation receipt generation does not match this run")
        register_store.stamp_generation(built.run_id, shown.generation, already_locked=True)
        for child in built.children:
            decision = admission._reserve_under_admission_lock(
                claimed,
                child.row_id,
                run_id=built.run_id,
                vendor=child.vendor,
                work_shape=child.execution_class,
                tokens_max=child.tokens_max,
                now=now,
                already_holding_generation=True,
            )
            register_store.write_phase(
                root, child.row_id, "planned", run_id=built.run_id, claimed=claimed
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
                    "scope": list(child.scope),
                    "declared_artifact_path": child.artifact_path,
                    "predicate": dict(child.predicate),
                    "integration_mode": child.integration_mode,
                    "tokens_max": child.tokens_max,
                    "substitutions": [dict(item) for item in child.substitutions],
                    "override": dict(child.override) if child.override else None,
                    "workspace_boundary": child.workspace_boundary,
                },
                run_id=built.run_id,
                writer=register_store.TOKENS_MAX_WRITER,
                already_locked=True,
                claimed=claimed,
            )
            committed.append(
                replace(
                    child,
                    admission=decision.status,
                    admission_reason=decision.reason,
                )
            )
    return replace(built, children=tuple(committed))
