#!/usr/bin/env python3
"""Score Code Review lenses from the canonical roster and keep other gates separate.

Private Internals:
    All functions, classes, and module attributes prefixed with a leading underscore
    (`_`) or omitted from `__all__` are private implementation details and subject to
    internal change without notice. External consumers and direct-drive sessions
    should rely strictly on the public symbols exported in `__all__`.

Exception Hierarchy (read before writing an `except` clause):
    `ReviewScoringError(ValueError)` is the root of every error class this module defines.
    `ContradictoryReviewEvidenceError` and `ReviewConsensusError` each subclass
    `ReviewScoringError`, and `UnsupportedReviewResultSchemaError` subclasses
    `ReviewConsensusError`. The nesting runs the opposite way from what the names
    suggest: `ReviewConsensusError` does NOT catch `ReviewScoringError` or
    `ContradictoryReviewEvidenceError`. Catch `ReviewScoringError` to cover the
    whole module; catch a narrower class only when that specific failure is meant
    to be handled differently.

Public Entry Points and State Machine Overview:
    1. Scoring Individual Lenses:
       - `score_lens_review(lens_id, applicable_dimensions, ...)`: Validates rubric
         dimension scores against the canonical roster policy and returns a `LensScore`.
    2. Review Cycle State Machine:
       - `ReviewCycleState(selected_lenses=...)`: Instantiates the 3-cycle controller.
       - `ReviewFinding(...)`: Defines structured findings with severity, owner, and actionability.
       - `ReviewCycleState.record_cycle(revision, lens_scores, ...)`: Records a review
         round, reconciles findings, updates failing lenses, and determines outcome.
       - `resolve_lens_selection` / `launch_approved_lenses`: persist conditional-lens approval
         against reviewed commit + cycle on this same state; refuse Agent spawn until it exists.
    3. Gate Readiness Evaluation:
       - `evaluate_review_readiness(lens_scores, independent_gates=...)`: Combines lens
         scores with independent non-scoring gate results into a composite readiness decision.

Worked Example (Direct State-Machine Drive):
    >>> import review_consensus as rc
    >>>
    >>> # 1. Score the required lenses against the canonical rubric policy
    >>> policy = rc.DEFAULT_SCORING_POLICY
    >>> correctness_dims = dict.fromkeys(policy.dimensions_for("correctness"), 9.5)
    >>> correctness_score = rc.score_lens_review("correctness", correctness_dims)
    >>>
    >>> # 2. Initialize the cycle state machine with selected lenses
    >>> state = rc.ReviewCycleState(["correctness"])
    >>> assert state.next_lenses == ("correctness",)
    >>>
    >>> # 3. Construct any structured review findings
    >>> finding = rc.ReviewFinding(
    ...     finding_id="F01",
    ...     lens_id="correctness",
    ...     dimension_id=policy.dimensions_for("correctness")[0],
    ...     title="Documented boundary check",
    ...     severity="P2",
    ...     file="plugins/saga/scripts/review_consensus.py",
    ...     line=1,
    ...     why_it_matters="Ensures callers understand parameter contracts.",
    ...     autofix_class="safe_auto",
    ...     owner="review-fixer",
    ...     requires_verification=True,
    ...     confidence=100,
    ...     evidence=("plugins/saga/scripts/review_consensus.py:1",),
    ... )
    >>>
    >>> # 4. Record the cycle for the reviewed revision
    >>> result = state.record_cycle(
    ...     revision="a1b2c3d4e5f6",
    ...     lens_scores={"correctness": correctness_score},
    ...     findings=[finding],
    ... )
    >>> assert result.outcome == "accepted"
    >>>
    >>> # 5. Evaluate overall review readiness with independent verification gates
    >>> gate = rc.IndependentGateResult(gate_id="unit-tests", passed=True)
    >>> readiness = rc.evaluate_review_readiness(
    ...     lens_scores=[item.score for item in result.lens_results],
    ...     independent_gates=[gate],
    ... )
    >>> assert readiness.can_proceed is True
    >>> assert readiness.review_accepted is True
    >>> assert readiness.independent_gates_passed is True
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

ROSTER_PATH = Path(__file__).resolve().parent.parent / "references" / "lens-roster.json"
ROSTER_SCHEMA = "lens_roster.v1"
OVERALL_RULE_ID = "derived-overall-minimum"
DIMENSION_FLOOR_RULE_ID = "applicable-dimension-floor"
REVIEW_RESULT_SCHEMA = "review_result.v1"
REVIEW_CYCLE_STATE_SCHEMA = "review_cycle_state.v1"
MAX_REVIEW_CYCLES = 3

ReviewOutcome = Literal[
    "accepted",
    "repairs_requested",
    "cycle_cap_best_available",
    "review_incomplete",
]
RunnerDeliveryStatus = Literal["ready", "pending", "incomplete"]
LensLaunchChoice = Literal["accept-recommended", "always-on-only", "customize"]
LensApprovalSource = Literal["operator", "caller", "orchestrate"]
LensQuestionKind = Literal["full", "delta"]

_OUTCOME_NEXT_ACTION: Mapping[ReviewOutcome, str] = MappingProxyType(
    {
        "accepted": "continue",
        "repairs_requested": "dispatch_repairs",
        "cycle_cap_best_available": "continue_with_best_available",
        "review_incomplete": "report_review_incomplete",
    }
)

__all__ = [
    "DEFAULT_SCORING_POLICY",
    "MAX_REVIEW_CYCLES",
    "REVIEW_CYCLE_STATE_SCHEMA",
    "REVIEW_RESULT_SCHEMA",
    "ContradictoryReviewEvidenceError",
    "CycleRecord",
    "DeltaCheckResult",
    "ExternalAdvisoryReview",
    "ExternalFindingAdjudication",
    "FindingEvidence",
    "FixRequest",
    "AgentCallTranscript",
    "ALWAYS_ON_LENSES",
    "ConditionalLensRecommendation",
    "IndependentGateResult",
    "LensApprovalRecord",
    "LensReviewResult",
    "LensSelectionDecision",
    "LensSelectionQuestion",
    "LensScore",
    "ResidualSummary",
    "ReviewConsensusError",
    "ReviewCycleState",
    "ReviewFinding",
    "ReviewResult",
    "ReviewReadiness",
    "RunnerDeliveryResolution",
    "ScoreRegression",
    "ReviewScoringError",
    "ReviewScoringPolicy",
    "UnsupportedReviewResultSchemaError",
    "consolidate_fix_requests",
    "always_on_lenses",
    "evaluate_review_readiness",
    "launch_approved_lenses",
    "load_scoring_policy",
    "recommend_conditional_lenses",
    "resolve_lens_selection",
    "score_lens_review",
]


class ReviewScoringError(ValueError):
    """The roster or a lens review cannot produce a trustworthy score."""


class ContradictoryReviewEvidenceError(ReviewScoringError):
    """Reported review evidence disagrees with the score it is meant to support."""


class ReviewConsensusError(ReviewScoringError):
    """Cycle state or a typed review result violates the consensus contract."""


class UnsupportedReviewResultSchemaError(ReviewConsensusError):
    """A consumer received a result or state schema it cannot interpret safely."""


@dataclass(frozen=True)
class ReviewScoringPolicy:
    """Roster-owned score bounds, acceptance rules, and declared lens dimensions."""

    minimum_score: float
    maximum_score: float
    overall_minimum: float
    dimension_floor: float
    lens_dimensions: Mapping[str, tuple[str, ...]]

    def dimensions_for(self, lens_id: str) -> tuple[str, ...]:
        """Return the canonical dimension identifiers for one scoring lens."""
        try:
            return self.lens_dimensions[lens_id]
        except KeyError as exc:
            raise ReviewScoringError(f"unknown scoring lens {lens_id!r}") from exc


@dataclass(frozen=True)
class FindingEvidence:
    """Finding metadata linked to the dimension whose score reflects its evidence."""

    finding_id: str
    dimension_id: str
    critical: bool = False
    resolved: bool = False
    priority: str | None = None
    confidence: int | None = None


@dataclass(frozen=True)
class LensScore:
    """Validated, roster-bound score for one selected review lens."""

    lens_id: str
    dimension_scores: dict[str, float]
    non_applicable_dimensions: dict[str, str]
    derived_overall: float
    accepted: bool
    failing_dimensions: tuple[str, ...]
    findings: tuple[FindingEvidence, ...]


@dataclass(frozen=True)
class IndependentGateResult:
    """One non-scoring gate that retains authority over review readiness."""

    gate_id: str
    passed: bool


@dataclass(frozen=True)
class ReviewReadiness:
    """Numeric review acceptance plus independent, non-scoring gate state."""

    lens_scores: tuple[LensScore, ...]
    independent_gates: tuple[IndependentGateResult, ...]
    review_accepted: bool
    independent_gates_passed: bool
    failing_lenses: tuple[str, ...]
    failed_independent_gates: tuple[str, ...]
    can_proceed: bool


_FINDING_SEVERITIES = frozenset({"P0", "P1", "P2", "P3"})
_AUTOFIX_CLASSES = frozenset({"safe_auto", "gated_auto", "manual", "advisory"})
_FIX_AUTOFIX_CLASSES = frozenset({"safe_auto", "gated_auto", "manual"})
_FINDING_OWNERS = frozenset({"review-fixer", "downstream-resolver", "human", "release"})
_CONFIDENCE_ANCHORS = frozenset({0, 25, 50, 75, 100})


def _review_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewConsensusError(f"{label} must be non-empty text")
    return value.strip()


def _review_text_tuple(values: Iterable[object], *, label: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ReviewConsensusError(f"{label} must be an iterable of text values")
    result = tuple(
        _review_text(value, label=f"{label}[{index}]") for index, value in enumerate(values)
    )
    if len(set(result)) != len(result):
        raise ReviewConsensusError(f"{label} must not contain duplicates")
    return result


def _review_mapping(value: object, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReviewConsensusError(f"{label} must be an object")
    return value


def _review_mapping_list(value: object, *, label: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise ReviewConsensusError(f"{label} must be a list")
    return tuple(
        _review_mapping(item, label=f"{label}[{index}]") for index, item in enumerate(value)
    )


def _review_text_mapping(value: object, *, label: str) -> dict[str, str]:
    raw = _review_mapping(value, label=label)
    return {
        _review_text(key, label=f"{label} key"): _review_text(item, label=f"{label}[{key!r}]")
        for key, item in raw.items()
    }


def _plain_dataclass(value: object) -> dict[str, Any]:
    return json.loads(json.dumps(asdict(value), sort_keys=True))


_LENS_LAUNCH_CHOICES = frozenset({"accept-recommended", "always-on-only", "customize"})
_LENS_APPROVAL_SOURCES = frozenset({"operator", "caller", "orchestrate"})


@dataclass(frozen=True)
class ConditionalLensRecommendation:
    """One judged conditional lens plus the one-line reason the operator sees."""

    lens_id: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"lens_id": self.lens_id, "reason": self.reason}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ConditionalLensRecommendation:
        mapping = _review_mapping(payload, label="conditional recommendation")
        return cls(
            lens_id=_review_text(mapping.get("lens_id"), label="recommendation lens_id"),
            reason=_review_text(mapping.get("reason"), label="recommendation reason"),
        )


@dataclass(frozen=True)
class LensApprovalRecord:
    """Operator (or caller) approval bound to one reviewed commit and cycle."""

    reviewed_commit: str
    cycle: int
    approved_conditionals: tuple[str, ...]
    recommended: tuple[ConditionalLensRecommendation, ...]
    source: LensApprovalSource
    question_asked: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewed_commit": self.reviewed_commit,
            "cycle": self.cycle,
            "approved_conditionals": list(self.approved_conditionals),
            "recommended": [item.to_dict() for item in self.recommended],
            "source": self.source,
            "question_asked": self.question_asked,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> LensApprovalRecord:
        mapping = _review_mapping(payload, label="lens approval")
        source = mapping.get("source")
        if source not in _LENS_APPROVAL_SOURCES:
            raise ReviewConsensusError(f"unsupported lens approval source {source!r}")
        cycle = mapping.get("cycle")
        if not isinstance(cycle, int) or isinstance(cycle, bool) or cycle < 1:
            raise ReviewConsensusError("lens approval cycle must be a positive integer")
        recommended = tuple(
            ConditionalLensRecommendation.from_dict(item)
            for item in _review_mapping_list(
                mapping.get("recommended", []),
                label="approval recommended",
            )
        )
        asked = mapping.get("question_asked")
        if not isinstance(asked, bool):
            raise ReviewConsensusError("lens approval question_asked must be a boolean")
        return cls(
            reviewed_commit=_review_text(
                mapping.get("reviewed_commit"), label="approval reviewed_commit"
            ),
            cycle=cycle,
            approved_conditionals=_require_roster_conditionals(
                mapping.get("approved_conditionals", ()),
                label="approved_conditionals",
            ),
            recommended=recommended,
            source=source,
            question_asked=asked,
        )


@dataclass(frozen=True)
class LensSelectionQuestion:
    """The one batched conditional-lens question, or a repair-cycle delta."""

    kind: LensQuestionKind
    recommended: tuple[ConditionalLensRecommendation, ...]
    delta_added: tuple[ConditionalLensRecommendation, ...] = ()
    delta_removed: tuple[str, ...] = ()
    choices: tuple[LensLaunchChoice, ...] = (
        "accept-recommended",
        "always-on-only",
        "customize",
    )
    default_choice: LensLaunchChoice = "accept-recommended"
    combine_with_backend: bool = True


@dataclass(frozen=True)
class LensSelectionDecision:
    """Launch set plus whether the operator still has to answer."""

    reviewed_commit: str
    cycle: int
    launch_set: tuple[str, ...]
    approved_conditionals: tuple[str, ...]
    recommended: tuple[ConditionalLensRecommendation, ...]
    needs_question: bool
    paused: bool
    reused: bool
    question: LensSelectionQuestion | None = None
    approval: LensApprovalRecord | None = None


class AgentCallTranscript:
    """Ordered approval and Agent-spawn events for one lens launch."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def record_approval(self, reviewed_commit: str, cycle: int) -> None:
        self.events.append(("approval", f"{reviewed_commit}:{cycle}"))

    def spawn_agent(self, lens_id: str) -> None:
        self.events.append(("agent", lens_id))

    @property
    def agent_calls(self) -> tuple[str, ...]:
        return tuple(lens_id for kind, lens_id in self.events if kind == "agent")

    @property
    def conditional_agent_calls(self) -> tuple[str, ...]:
        always_on = set(always_on_lenses())
        return tuple(lens_id for lens_id in self.agent_calls if lens_id not in always_on)


@dataclass(frozen=True)
class ReviewFinding:
    """A structured Code Review finding with routing metadata.

    Attributes:
        finding_id: Unique string identifier for the finding (e.g. 'F01'). Must be non-empty.
        lens_id: Identifier of the reporting review lens (e.g. 'correctness', 'security').
        dimension_id: Dimension within the lens rubric (e.g.
            'boundary-types-serialization-numeric-time'). This argument has no default and must
            always be passed - pass `None` explicitly for a finding that names no dimension.
            `ReviewCycleState.record_cycle` rejects a `None` dimension_id, so any finding routed
            through a review cycle must name a real dimension of its lens.
        title: Short summary describing the defect or concern.
        severity: Priority level ('P0', 'P1', 'P2', or 'P3').
        file: Relative path to the primary file containing the issue.
        line: 1-indexed line number in `file` (integer >= 1).
        why_it_matters: Explanation of the impact, risk, or rationale.
        autofix_class: Actionability classification ('safe_auto', 'gated_auto', 'manual',
            or 'advisory').
        owner: Responsible party ('review-fixer', 'downstream-resolver', 'human', or 'release').
        requires_verification: Whether remediation requires automated verification.
        confidence: Confidence score anchor (must be one of 0, 25, 50, 75, 100).
        evidence: Non-empty sequence of evidence citations (e.g. file:line references).
        pre_existing: Whether the issue was present prior to the reviewed revision (default: False).
        suggested_fix: Optional proposed remediation text.
        touched_paths: Sequence of all affected file paths (defaults to `(file,)` if omitted).
        status: Finding lifecycle status ('active', 'dismissed', or 'resolved'; default: 'active').
    """

    finding_id: str
    lens_id: str
    dimension_id: str | None
    title: str
    severity: str
    file: str
    line: int
    why_it_matters: str
    autofix_class: str
    owner: str
    requires_verification: bool
    confidence: int
    evidence: tuple[str, ...]
    pre_existing: bool = False
    suggested_fix: str | None = None
    touched_paths: tuple[str, ...] = ()
    status: str = "active"

    def __post_init__(self) -> None:
        for field_name in ("finding_id", "lens_id", "title", "file", "why_it_matters"):
            object.__setattr__(
                self,
                field_name,
                _review_text(getattr(self, field_name), label=f"finding {field_name}"),
            )
        if self.severity not in _FINDING_SEVERITIES:
            raise ReviewConsensusError(f"unsupported finding severity {self.severity!r}")
        if self.autofix_class not in _AUTOFIX_CLASSES:
            raise ReviewConsensusError(f"unsupported autofix_class {self.autofix_class!r}")
        if self.owner not in _FINDING_OWNERS:
            raise ReviewConsensusError(f"unsupported finding owner {self.owner!r}")
        if self.status not in {"active", "dismissed", "resolved"}:
            raise ReviewConsensusError(f"unsupported finding status {self.status!r}")
        if isinstance(self.line, bool) or not isinstance(self.line, int) or self.line < 1:
            raise ReviewConsensusError("finding line must be an integer >= 1")
        if not isinstance(self.requires_verification, bool) or not isinstance(
            self.pre_existing, bool
        ):
            raise ReviewConsensusError("finding boolean fields must be boolean")
        if isinstance(self.confidence, bool) or self.confidence not in _CONFIDENCE_ANCHORS:
            raise ReviewConsensusError("finding confidence must use a declared anchor")
        evidence = _review_text_tuple(self.evidence, label="finding evidence")
        if not evidence:
            raise ReviewConsensusError("finding requires evidence")
        touched = _review_text_tuple(
            self.touched_paths or (self.file,), label="finding touched_paths"
        )
        if self.file not in touched:
            touched = (self.file, *touched)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "touched_paths", touched)
        if self.dimension_id is not None:
            object.__setattr__(
                self,
                "dimension_id",
                _review_text(self.dimension_id, label="finding dimension_id"),
            )
        if self.suggested_fix is not None:
            object.__setattr__(
                self,
                "suggested_fix",
                _review_text(self.suggested_fix, label="finding suggested_fix"),
            )

    def to_dict(self) -> dict[str, Any]:
        return _plain_dataclass(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReviewFinding:
        try:
            return cls(**dict(payload))
        except TypeError as exc:
            raise ReviewConsensusError(f"invalid review finding: {exc}") from exc


@dataclass(frozen=True)
class FixRequest:
    """A deterministic repair request for one overlapping path group."""

    fix_id: str
    finding_ids: tuple[str, ...]
    autofix_class: str
    owner: str
    touched_paths: tuple[str, ...]
    summary: str
    requires_verification: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "fix_id", _review_text(self.fix_id, label="fix_id"))
        object.__setattr__(
            self,
            "finding_ids",
            _review_text_tuple(self.finding_ids, label="fix request finding_ids"),
        )
        object.__setattr__(
            self,
            "touched_paths",
            _review_text_tuple(self.touched_paths, label="fix request touched_paths"),
        )
        object.__setattr__(self, "summary", _review_text(self.summary, label="fix request summary"))
        if not self.finding_ids or not self.touched_paths:
            raise ReviewConsensusError("fix request requires findings and touched paths")
        if self.autofix_class not in _FIX_AUTOFIX_CLASSES:
            raise ReviewConsensusError("fix request must be actionable")
        if self.owner not in _FINDING_OWNERS:
            raise ReviewConsensusError(f"unsupported fix owner {self.owner!r}")
        if not isinstance(self.requires_verification, bool):
            raise ReviewConsensusError("fix request requires_verification must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return _plain_dataclass(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> FixRequest:
        try:
            return cls(**dict(payload))
        except TypeError as exc:
            raise ReviewConsensusError(f"invalid fix request: {exc}") from exc


@dataclass(frozen=True)
class ExternalFindingAdjudication:
    """Code Review's disposition of one whole-diff external finding."""

    finding_id: str
    decision: str
    rationale: str
    final_severity: str
    final_status: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "finding_id", _review_text(self.finding_id, label="adjudication finding_id")
        )
        object.__setattr__(
            self, "rationale", _review_text(self.rationale, label="adjudication rationale")
        )
        if self.decision not in {"keep", "downgrade", "dismiss"}:
            raise ReviewConsensusError(f"unsupported adjudication {self.decision!r}")
        if self.final_severity not in _FINDING_SEVERITIES:
            raise ReviewConsensusError(f"unsupported final severity {self.final_severity!r}")
        if self.final_status not in {"active", "dismissed"}:
            raise ReviewConsensusError(f"unsupported final status {self.final_status!r}")

    def to_dict(self) -> dict[str, Any]:
        return _plain_dataclass(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ExternalFindingAdjudication:
        try:
            return cls(**dict(payload))
        except TypeError as exc:
            raise ReviewConsensusError(f"invalid external adjudication: {exc}") from exc


@dataclass(frozen=True)
class ExternalAdvisoryReview:
    """Request-bound, cross-vendor whole-diff evidence with no scoring authority."""

    reviewer_id: str
    reviewer_vendor: str
    home_vendor: str
    request_id: str
    request_digest: str
    reviewed_revision: str
    findings: tuple[ReviewFinding, ...]
    adjudications: tuple[ExternalFindingAdjudication, ...]
    whole_diff: bool = True
    request_bound: bool = True
    scoring_authority: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "reviewer_id",
            "reviewer_vendor",
            "home_vendor",
            "request_id",
            "request_digest",
            "reviewed_revision",
        ):
            object.__setattr__(
                self,
                field_name,
                _review_text(getattr(self, field_name), label=f"external {field_name}"),
            )
        if self.reviewer_vendor.casefold() == self.home_vendor.casefold():
            raise ReviewConsensusError("external advisory review must use another vendor")
        if not (self.whole_diff and self.request_bound):
            raise ReviewConsensusError("external advisory review lost a lifecycle safeguard")
        if self.scoring_authority:
            raise ReviewConsensusError("external advisory review cannot score")
        findings = tuple(self.findings)
        adjudications = tuple(self.adjudications)
        if any(finding.lens_id != "external-reviewer" for finding in findings):
            raise ReviewConsensusError("external findings must name the external-reviewer seat")
        by_id = {item.finding_id: item for item in adjudications}
        if len(by_id) != len(adjudications) or set(by_id) != {
            finding.finding_id for finding in findings
        }:
            raise ReviewConsensusError("every external finding requires one adjudication")
        rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        for finding in findings:
            item = by_id[finding.finding_id]
            if item.decision == "keep" and (
                item.final_severity != finding.severity or item.final_status != "active"
            ):
                raise ReviewConsensusError("kept external finding must remain active")
            if item.decision == "downgrade" and (
                item.final_status != "active" or rank[item.final_severity] <= rank[finding.severity]
            ):
                raise ReviewConsensusError("external downgrade must lower severity")
            if item.decision == "dismiss" and (
                item.final_status != "dismissed" or item.final_severity != finding.severity
            ):
                raise ReviewConsensusError("dismissed finding keeps its audit severity")
        object.__setattr__(self, "findings", findings)
        object.__setattr__(self, "adjudications", adjudications)

    @property
    def adjudicated_findings(self) -> tuple[ReviewFinding, ...]:
        by_id = {item.finding_id: item for item in self.adjudications}
        return tuple(
            replace(
                finding,
                severity=by_id[finding.finding_id].final_severity,
                status=by_id[finding.finding_id].final_status,
            )
            for finding in self.findings
        )

    def to_dict(self) -> dict[str, Any]:
        return _plain_dataclass(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ExternalAdvisoryReview:
        data = dict(payload)
        data["findings"] = tuple(
            ReviewFinding.from_dict(item)
            for item in _review_mapping_list(data.get("findings"), label="external findings")
        )
        data["adjudications"] = tuple(
            ExternalFindingAdjudication.from_dict(item)
            for item in _review_mapping_list(
                data.get("adjudications"), label="external adjudications"
            )
        )
        data.pop("external_only_admitted", None)  # retired with #776 transport
        try:
            return cls(**data)
        except TypeError as exc:
            raise ReviewConsensusError(f"invalid external advisory review: {exc}") from exc


@dataclass(frozen=True)
class DeltaCheckResult:
    """A narrow check of an accepted lens against a later candidate revision."""

    lens_id: str
    reviewed_revision: str
    checked_revision: str
    passed: bool
    cause: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("lens_id", "reviewed_revision", "checked_revision", "cause"):
            object.__setattr__(
                self,
                field_name,
                _review_text(getattr(self, field_name), label=f"delta {field_name}"),
            )
        if not isinstance(self.passed, bool):
            raise ReviewConsensusError("delta-check passed must be boolean")
        evidence = _review_text_tuple(self.evidence_refs, label="delta evidence_refs")
        if not evidence:
            raise ReviewConsensusError("delta-check requires evidence")
        object.__setattr__(self, "evidence_refs", evidence)

    def to_dict(self) -> dict[str, Any]:
        return _plain_dataclass(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> DeltaCheckResult:
        try:
            return cls(**dict(payload))
        except TypeError as exc:
            raise ReviewConsensusError(f"invalid delta-check: {exc}") from exc


def _finding_evidence_to_dict(finding: FindingEvidence) -> dict[str, Any]:
    return _plain_dataclass(finding)


def _finding_evidence_from_dict(payload: Mapping[str, Any]) -> FindingEvidence:
    try:
        return FindingEvidence(**dict(payload))
    except TypeError as exc:
        raise ReviewConsensusError(f"invalid scoring finding: {exc}") from exc


@dataclass(frozen=True)
class LensReviewResult:
    """A retained U5 score bound to the revision that lens actually reviewed."""

    lens_id: str
    reviewed_revision: str
    cycle: int
    score: LensScore
    delta_check: DeltaCheckResult | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "lens_id", _review_text(self.lens_id, label="lens result lens_id"))
        object.__setattr__(
            self,
            "reviewed_revision",
            _review_text(self.reviewed_revision, label="lens result reviewed_revision"),
        )
        if (
            isinstance(self.cycle, bool)
            or not isinstance(self.cycle, int)
            or not 1 <= self.cycle <= MAX_REVIEW_CYCLES
        ):
            raise ReviewConsensusError("lens result has an invalid cycle")
        if not isinstance(self.score, LensScore) or self.score.lens_id != self.lens_id:
            raise ReviewConsensusError("lens result carries a mismatched U5 score")
        if self.delta_check is not None and (
            self.delta_check.lens_id != self.lens_id
            or self.delta_check.reviewed_revision != self.reviewed_revision
        ):
            raise ReviewConsensusError("lens result carries a mismatched delta-check")

    @property
    def accepted(self) -> bool:
        return self.score.accepted and (self.delta_check is None or self.delta_check.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lens_id": self.lens_id,
            "reviewed_revision": self.reviewed_revision,
            "cycle": self.cycle,
            "applicable_dimensions": dict(self.score.dimension_scores),
            "non_applicable_dimensions": dict(self.score.non_applicable_dimensions),
            "derived_overall": self.score.derived_overall,
            "score_accepted": self.score.accepted,
            "accepted": self.accepted,
            "failing_dimensions": list(self.score.failing_dimensions),
            "scoring_findings": [_finding_evidence_to_dict(item) for item in self.score.findings],
            "delta_check": (self.delta_check.to_dict() if self.delta_check is not None else None),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> LensReviewResult:
        lens_id = _review_text(payload.get("lens_id"), label="lens result lens_id")
        score = score_lens_review(
            lens_id,
            _review_mapping(payload.get("applicable_dimensions"), label="applicable_dimensions"),
            non_applicable_dimensions=_review_text_mapping(
                payload.get("non_applicable_dimensions"),
                label="non_applicable_dimensions",
            ),
            reported_overall=payload.get("derived_overall"),
            findings=tuple(
                _finding_evidence_from_dict(item)
                for item in _review_mapping_list(
                    payload.get("scoring_findings"), label="scoring_findings"
                )
            ),
        )
        raw_delta = payload.get("delta_check")
        result = cls(
            lens_id=lens_id,
            reviewed_revision=payload.get("reviewed_revision"),
            cycle=payload.get("cycle"),
            score=score,
            delta_check=(
                DeltaCheckResult.from_dict(_review_mapping(raw_delta, label="delta_check"))
                if raw_delta is not None
                else None
            ),
        )
        if (
            payload.get("score_accepted") is not score.accepted
            or payload.get("accepted") is not result.accepted
            or tuple(payload.get("failing_dimensions", ())) != score.failing_dimensions
        ):
            raise ReviewConsensusError("serialized lens result contradicts its U5 score")
        return result


@dataclass(frozen=True)
class ScoreRegression:
    """A score decrease reported in residuals, never a separate gate."""

    lens_id: str
    previous_revision: str
    current_revision: str
    previous_overall: float
    current_overall: float
    cycle: int

    def __post_init__(self) -> None:
        if self.current_overall >= self.previous_overall:
            raise ReviewConsensusError("score regression must decrease the overall")
        if not 1 <= self.cycle <= MAX_REVIEW_CYCLES:
            raise ReviewConsensusError("score regression has an invalid cycle")

    def to_dict(self) -> dict[str, Any]:
        return _plain_dataclass(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ScoreRegression:
        try:
            return cls(**dict(payload))
        except TypeError as exc:
            raise ReviewConsensusError(f"invalid score regression: {exc}") from exc


@dataclass(frozen=True)
class CycleRecord:
    """One successfully integrated revision and the scores it consumed."""

    cycle: int
    revision: str
    attempted_lenses: tuple[str, ...]
    lens_results: tuple[LensReviewResult, ...]
    delta_checks: tuple[DeltaCheckResult, ...]
    failing_lenses: tuple[str, ...]
    unresolved_fix_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not 1 <= self.cycle <= MAX_REVIEW_CYCLES:
            raise ReviewConsensusError("cycle record has an invalid cycle")
        object.__setattr__(self, "revision", _review_text(self.revision, label="cycle revision"))
        for field_name in ("attempted_lenses", "failing_lenses", "unresolved_fix_ids"):
            object.__setattr__(
                self,
                field_name,
                _review_text_tuple(getattr(self, field_name), label=f"cycle {field_name}"),
            )
        if tuple(item.lens_id for item in self.lens_results) != self.attempted_lenses:
            raise ReviewConsensusError("cycle results do not match attempted lenses")

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "revision": self.revision,
            "attempted_lenses": list(self.attempted_lenses),
            "lens_results": [item.to_dict() for item in self.lens_results],
            "delta_checks": [item.to_dict() for item in self.delta_checks],
            "failing_lenses": list(self.failing_lenses),
            "unresolved_fix_ids": list(self.unresolved_fix_ids),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CycleRecord:
        return cls(
            cycle=payload.get("cycle"),
            revision=payload.get("revision"),
            attempted_lenses=tuple(payload.get("attempted_lenses", ())),
            lens_results=tuple(
                LensReviewResult.from_dict(item)
                for item in _review_mapping_list(
                    payload.get("lens_results"), label="cycle lens_results"
                )
            ),
            delta_checks=tuple(
                DeltaCheckResult.from_dict(item)
                for item in _review_mapping_list(
                    payload.get("delta_checks"), label="cycle delta_checks"
                )
            ),
            failing_lenses=tuple(payload.get("failing_lenses", ())),
            unresolved_fix_ids=tuple(payload.get("unresolved_fix_ids", ())),
        )


@dataclass(frozen=True)
class ResidualSummary:
    """Final scores, unresolved fixes, and non-gating regressions."""

    lens_results: tuple[LensReviewResult, ...]
    unresolved_fix_ids: tuple[str, ...]
    score_regressions: tuple[ScoreRegression, ...]
    review_incomplete_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_lens_scores": {
                item.lens_id: {
                    "derived_overall": item.score.derived_overall,
                    "accepted": item.accepted,
                    "reviewed_revision": item.reviewed_revision,
                    "failing_dimensions": list(item.score.failing_dimensions),
                    "delta_check": (
                        item.delta_check.to_dict() if item.delta_check is not None else None
                    ),
                }
                for item in self.lens_results
            },
            "unresolved_fix_ids": list(self.unresolved_fix_ids),
            "score_regressions": [item.to_dict() for item in self.score_regressions],
            "review_incomplete_reason": self.review_incomplete_reason,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        lens_results: tuple[LensReviewResult, ...],
    ) -> ResidualSummary:
        result = cls(
            lens_results=lens_results,
            unresolved_fix_ids=tuple(payload.get("unresolved_fix_ids", ())),
            score_regressions=tuple(
                ScoreRegression.from_dict(item)
                for item in _review_mapping_list(
                    payload.get("score_regressions"), label="score_regressions"
                )
            ),
            review_incomplete_reason=payload.get("review_incomplete_reason"),
        )
        if payload.get("final_lens_scores") != result.to_dict()["final_lens_scores"]:
            raise ReviewConsensusError("residual scores contradict the lens results")
        return result


def _is_fix_request_candidate(finding: ReviewFinding) -> bool:
    """Return whether an unresolved finding is actionable by the repair loop."""
    return (
        finding.status == "active"
        and not finding.pre_existing
        and finding.autofix_class != "advisory"
    )


def _score_with_typed_findings(
    score: LensScore,
    findings: Iterable[ReviewFinding],
    *,
    policy: ReviewScoringPolicy,
) -> LensScore:
    """Reconcile routed findings with scoring evidence before a result can carry either."""
    typed_findings = tuple(findings)
    scoring_by_id = {item.finding_id: item for item in score.findings}
    if len(scoring_by_id) != len(score.findings):
        raise ReviewConsensusError(f"lens {score.lens_id!r} has duplicate scoring findings")

    for finding in typed_findings:
        if not isinstance(finding, ReviewFinding) or finding.lens_id != score.lens_id:
            raise ReviewConsensusError(
                f"lens {score.lens_id!r} received a mismatched typed finding"
            )
        if finding.dimension_id is None:
            raise ReviewConsensusError(
                f"finding {finding.finding_id!r} requires a dimension before scoring"
            )

        existing = scoring_by_id.get(finding.finding_id)
        resolved = finding.status != "active"
        if existing is not None:
            if existing.dimension_id != finding.dimension_id:
                raise ReviewConsensusError(
                    f"finding {finding.finding_id!r} contradicts its scoring dimension"
                )
            if existing.resolved is not resolved:
                raise ReviewConsensusError(
                    f"finding {finding.finding_id!r} contradicts its scoring status"
                )
            if existing.priority not in {None, finding.severity}:
                raise ReviewConsensusError(
                    f"finding {finding.finding_id!r} contradicts its scoring priority"
                )
            if existing.confidence not in {None, finding.confidence}:
                raise ReviewConsensusError(
                    f"finding {finding.finding_id!r} contradicts its scoring confidence"
                )

        scoring_by_id[finding.finding_id] = FindingEvidence(
            finding_id=finding.finding_id,
            dimension_id=finding.dimension_id,
            critical=_is_fix_request_candidate(finding)
            and (finding.severity == "P0" or (existing is not None and existing.critical)),
            resolved=resolved,
            priority=finding.severity,
            confidence=finding.confidence,
        )

    return score_lens_review(
        score.lens_id,
        score.dimension_scores,
        non_applicable_dimensions=score.non_applicable_dimensions,
        reported_overall=score.derived_overall,
        findings=tuple(sorted(scoring_by_id.values(), key=lambda item: item.finding_id)),
        policy=policy,
    )


@dataclass(frozen=True)
class ReviewResult:
    """The versioned result callers persist and route without rescoring."""

    selected_lenses: tuple[str, ...]
    attempted_lenses: tuple[str, ...]
    lens_results: tuple[LensReviewResult, ...]
    findings: tuple[ReviewFinding, ...]
    cycle_history: tuple[CycleRecord, ...]
    failing_lenses: tuple[str, ...]
    fix_requests: tuple[FixRequest, ...]
    unresolved_fix_ids: tuple[str, ...]
    best_available_revision: str | None
    residual_summary: ResidualSummary
    outcome: ReviewOutcome
    evidence_ledger: Mapping[str, str]
    external_advisory_reviews: tuple[ExternalAdvisoryReview, ...] = ()
    schema: str = REVIEW_RESULT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REVIEW_RESULT_SCHEMA:
            raise UnsupportedReviewResultSchemaError(
                f"unsupported review result schema {self.schema!r}"
            )
        for field_name in (
            "selected_lenses",
            "attempted_lenses",
            "failing_lenses",
            "unresolved_fix_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                _review_text_tuple(getattr(self, field_name), label=field_name),
            )
        if not self.selected_lenses:
            raise ReviewConsensusError("review result requires selected lenses")
        if self.outcome not in _OUTCOME_NEXT_ACTION:
            raise ReviewConsensusError(f"unsupported review outcome {self.outcome!r}")
        if not set(self.attempted_lenses) <= set(self.selected_lenses):
            raise ReviewConsensusError("attempted lenses must be selected")
        if len(self.cycle_history) > MAX_REVIEW_CYCLES:
            raise ReviewConsensusError("a fourth cycle is not representable")
        if tuple(item.cycle for item in self.cycle_history) != tuple(
            range(1, len(self.cycle_history) + 1)
        ):
            raise ReviewConsensusError("cycle history must be contiguous")
        results_by_id = {item.lens_id: item for item in self.lens_results}
        if len(results_by_id) != len(self.lens_results):
            raise ReviewConsensusError("duplicate lens results")
        findings_by_lens: dict[str, list[ReviewFinding]] = {
            lens_id: [] for lens_id in results_by_id
        }
        for finding in self.findings:
            if not isinstance(finding, ReviewFinding):
                raise ReviewConsensusError("review result findings must be ReviewFinding values")
            if finding.lens_id == "external-reviewer":
                continue
            if finding.lens_id not in findings_by_lens:
                raise ReviewConsensusError(
                    f"finding {finding.finding_id!r} names a lens without a score"
                )
            findings_by_lens[finding.lens_id].append(finding)
        for lens_id, lens_result in results_by_id.items():
            reconciled = _score_with_typed_findings(
                lens_result.score,
                findings_by_lens[lens_id],
                policy=DEFAULT_SCORING_POLICY,
            )
            if reconciled != lens_result.score:
                raise ReviewConsensusError(
                    f"lens {lens_id!r} scoring findings contradict the typed findings"
                )
        calculated_failing = tuple(
            lens_id
            for lens_id in self.selected_lenses
            if lens_id in results_by_id and not results_by_id[lens_id].accepted
        )
        if self.outcome != "review_incomplete":
            if set(results_by_id) != set(self.selected_lenses):
                raise ReviewConsensusError("scoring result requires every selected lens")
            if self.failing_lenses != calculated_failing:
                raise ReviewConsensusError("failing lenses contradict retained scores")
            if not self.cycle_history:
                raise ReviewConsensusError("scoring result requires a completed cycle")
        if self.outcome == "accepted" and self.failing_lenses:
            raise ReviewConsensusError("accepted result cannot carry failing lenses")
        if self.outcome == "repairs_requested" and (
            not self.failing_lenses or len(self.cycle_history) >= MAX_REVIEW_CYCLES
        ):
            raise ReviewConsensusError("repairs_requested requires a cycle remaining")
        if self.outcome == "cycle_cap_best_available" and (
            not self.failing_lenses or len(self.cycle_history) != MAX_REVIEW_CYCLES
        ):
            raise ReviewConsensusError("cycle cap requires three unsuccessful cycles")
        if self.cycle_history:
            if self.best_available_revision != self.cycle_history[-1].revision:
                raise ReviewConsensusError("best available must be the latest reviewed revision")
        elif self.best_available_revision is not None:
            raise ReviewConsensusError("result without a cycle has no best revision")
        fix_ids = {item.fix_id for item in self.fix_requests}
        if not set(self.unresolved_fix_ids) <= fix_ids:
            raise ReviewConsensusError("unresolved identifiers must name fix requests")
        if self.residual_summary.unresolved_fix_ids != self.unresolved_fix_ids:
            raise ReviewConsensusError("residual fixes contradict the typed result")
        object.__setattr__(
            self,
            "evidence_ledger",
            MappingProxyType(
                dict(
                    sorted(
                        _review_text_mapping(self.evidence_ledger, label="evidence_ledger").items()
                    )
                )
            ),
        )

    @property
    def next_action(self) -> str:
        return _OUTCOME_NEXT_ACTION[self.outcome]

    @property
    def resume_transitions(self) -> tuple[str, ...]:
        return (self.next_action,)

    @property
    def collection_operation(self) -> Mapping[str, str]:
        return MappingProxyType({"operation": "collect", "schema": REVIEW_RESULT_SCHEMA})

    @property
    def revision_binding(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "best_available_revision": self.best_available_revision,
                "lens_revisions": {
                    item.lens_id: item.reviewed_revision for item in self.lens_results
                },
            }
        )

    def require_resume_transition(self, transition: str) -> str:
        transition = _review_text(transition, label="resume transition")
        if transition not in self.resume_transitions:
            raise ReviewConsensusError(
                f"outcome {self.outcome!r} does not allow transition {transition!r}"
            )
        return transition

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "collection_operation": dict(self.collection_operation),
            "revision_binding": dict(self.revision_binding),
            "selected_lenses": list(self.selected_lenses),
            "attempted_lenses": list(self.attempted_lenses),
            "lens_results": [item.to_dict() for item in self.lens_results],
            "findings": [item.to_dict() for item in self.findings],
            "cycle_history": [item.to_dict() for item in self.cycle_history],
            "failing_lenses": list(self.failing_lenses),
            "fix_requests": [item.to_dict() for item in self.fix_requests],
            "unresolved_fix_ids": list(self.unresolved_fix_ids),
            "best_available_revision": self.best_available_revision,
            "residual_summary": self.residual_summary.to_dict(),
            "outcome": self.outcome,
            "next_action": self.next_action,
            "resume_transitions": list(self.resume_transitions),
            "evidence_ledger": dict(self.evidence_ledger),
            "external_advisory_reviews": [
                item.to_dict() for item in self.external_advisory_reviews
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReviewResult:
        if "verdict" in payload:
            raise ReviewConsensusError("outcome is the only decision field")
        schema = payload.get("schema")
        if schema != REVIEW_RESULT_SCHEMA:
            raise UnsupportedReviewResultSchemaError(f"unsupported review result schema {schema!r}")
        lens_results = tuple(
            LensReviewResult.from_dict(item)
            for item in _review_mapping_list(payload.get("lens_results"), label="lens_results")
        )
        outcome = payload.get("outcome")
        if outcome not in _OUTCOME_NEXT_ACTION:
            raise ReviewConsensusError(f"unsupported review outcome {outcome!r}")
        result = cls(
            schema=schema,
            selected_lenses=tuple(payload.get("selected_lenses", ())),
            attempted_lenses=tuple(payload.get("attempted_lenses", ())),
            lens_results=lens_results,
            findings=tuple(
                ReviewFinding.from_dict(item)
                for item in _review_mapping_list(payload.get("findings"), label="findings")
            ),
            cycle_history=tuple(
                CycleRecord.from_dict(item)
                for item in _review_mapping_list(
                    payload.get("cycle_history"), label="cycle_history"
                )
            ),
            failing_lenses=tuple(payload.get("failing_lenses", ())),
            fix_requests=tuple(
                FixRequest.from_dict(item)
                for item in _review_mapping_list(payload.get("fix_requests"), label="fix_requests")
            ),
            unresolved_fix_ids=tuple(payload.get("unresolved_fix_ids", ())),
            best_available_revision=payload.get("best_available_revision"),
            residual_summary=ResidualSummary.from_dict(
                _review_mapping(payload.get("residual_summary"), label="residual_summary"),
                lens_results=lens_results,
            ),
            outcome=outcome,
            evidence_ledger=_review_text_mapping(
                payload.get("evidence_ledger"), label="evidence_ledger"
            ),
            external_advisory_reviews=tuple(
                ExternalAdvisoryReview.from_dict(item)
                for item in _review_mapping_list(
                    payload.get("external_advisory_reviews"),
                    label="external_advisory_reviews",
                )
            ),
        )
        fixed_fields = {
            "collection_operation": dict(result.collection_operation),
            "revision_binding": dict(result.revision_binding),
            "next_action": result.next_action,
            "resume_transitions": list(result.resume_transitions),
        }
        if any(payload.get(key) != value for key, value in fixed_fields.items()):
            raise ReviewConsensusError("result routing fields contradict its outcome")
        return result

    @classmethod
    def from_json(cls, payload: str) -> ReviewResult:
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ReviewConsensusError(f"review result is not valid JSON: {exc}") from exc
        return cls.from_dict(_review_mapping(decoded, label="review result"))


@dataclass(frozen=True)
class RunnerDeliveryResolution:
    """A delivery is ready, pending collection, or terminally incomplete."""

    status: RunnerDeliveryStatus
    payload: Mapping[str, Any]
    review_result: ReviewResult | None = None


def consolidate_fix_requests(findings: Iterable[ReviewFinding]) -> tuple[FixRequest, ...]:
    """Consolidate actionable findings without joining disjoint worker paths."""
    candidates = sorted(
        (item for item in findings if _is_fix_request_candidate(item)),
        key=lambda item: (
            item.owner,
            item.autofix_class,
            item.touched_paths,
            item.finding_id,
        ),
    )
    groups: list[dict[str, Any]] = []
    for finding in candidates:
        matching = [
            index
            for index, group in enumerate(groups)
            if group["owner"] == finding.owner
            and group["autofix_class"] == finding.autofix_class
            and group["paths"] & set(finding.touched_paths)
        ]
        if not matching:
            groups.append(
                {
                    "owner": finding.owner,
                    "autofix_class": finding.autofix_class,
                    "paths": set(finding.touched_paths),
                    "findings": [finding],
                }
            )
            continue
        target = groups[matching[0]]
        target["paths"].update(finding.touched_paths)
        target["findings"].append(finding)
        for index in reversed(matching[1:]):
            other = groups.pop(index)
            target["paths"].update(other["paths"])
            target["findings"].extend(other["findings"])

    requests: list[FixRequest] = []
    for group in groups:
        grouped = sorted(group["findings"], key=lambda item: item.finding_id)
        finding_ids = tuple(item.finding_id for item in grouped)
        identity = "|".join((group["owner"], group["autofix_class"], *finding_ids)).encode()
        requests.append(
            FixRequest(
                fix_id=f"fix-{hashlib.sha256(identity).hexdigest()[:12]}",
                finding_ids=finding_ids,
                autofix_class=group["autofix_class"],
                owner=group["owner"],
                touched_paths=tuple(sorted(group["paths"])),
                summary="; ".join(item.title for item in grouped),
                requires_verification=any(item.requires_verification for item in grouped),
            )
        )
    return tuple(
        sorted(
            requests,
            key=lambda item: (
                item.owner,
                item.autofix_class,
                item.touched_paths,
                item.fix_id,
            ),
        )
    )


class ReviewCycleState:
    """Three-cycle review consensus state machine controller.

    Manages the multi-round review lifecycle across up to `MAX_REVIEW_CYCLES` (3),
    tracking attempted lenses, failing lenses, consolidated fix requests, delta checks,
    and cumulative review outcomes ('accepted', 'repairs_requested',
    'cycle_cap_best_available', or 'review_incomplete').
    """

    def __init__(
        self,
        selected_lenses: Iterable[str],
        *,
        evidence_ledger: Mapping[str, str] | None = None,
        policy: ReviewScoringPolicy | None = None,
    ) -> None:
        """Initialize review cycle state for a set of selected lenses.

        Args:
            selected_lenses: Iterable of lens identifiers (e.g. 'correctness', 'security')
                to run and track across cycles. Must contain at least one valid lens from the policy.
            evidence_ledger: Optional initial mapping of evidence keys to values.
            policy: Optional custom `ReviewScoringPolicy` (defaults to `DEFAULT_SCORING_POLICY`).

        Raises:
            ReviewConsensusError: If `selected_lenses` is empty or contains duplicates.
            ReviewScoringError: If `selected_lenses` names a lens the policy does not define.
                This is NOT a `ReviewConsensusError` - see the module docstring's exception
                hierarchy note before writing an `except` clause around this constructor.
        """
        self._policy = policy or DEFAULT_SCORING_POLICY
        self._selected_lenses = _review_text_tuple(selected_lenses, label="selected_lenses")
        if not self._selected_lenses:
            raise ReviewConsensusError("cycle state requires selected lenses")
        for lens_id in self._selected_lenses:
            self._policy.dimensions_for(lens_id)
        self._evidence_ledger = _review_text_mapping(evidence_ledger or {}, label="evidence_ledger")
        self._lens_results: dict[str, LensReviewResult] = {}
        self._findings: tuple[ReviewFinding, ...] = ()
        self._cycle_history: tuple[CycleRecord, ...] = ()
        self._failing_lenses = self._selected_lenses
        self._resolved_fix_ids: set[str] = set()
        self._score_regressions: tuple[ScoreRegression, ...] = ()
        self._external_reviews: tuple[ExternalAdvisoryReview, ...] = ()
        self._lens_approvals: tuple[LensApprovalRecord, ...] = ()
        self._terminal_outcome: ReviewOutcome | None = None
        self._review_incomplete_reason: str | None = None

    @property
    def selected_lenses(self) -> tuple[str, ...]:
        return self._selected_lenses

    @property
    def cycle_count(self) -> int:
        return len(self._cycle_history)

    @property
    def next_lenses(self) -> tuple[str, ...]:
        if self._terminal_outcome is not None:
            return ()
        return self._selected_lenses if not self._cycle_history else self._failing_lenses

    @property
    def cycle_history(self) -> tuple[CycleRecord, ...]:
        return self._cycle_history

    @property
    def failing_lenses(self) -> tuple[str, ...]:
        return self._failing_lenses

    @property
    def lens_approvals(self) -> tuple[LensApprovalRecord, ...]:
        return self._lens_approvals

    def lens_approval_for(self, reviewed_commit: str, cycle: int) -> LensApprovalRecord | None:
        commit = _review_text(reviewed_commit, label="reviewed_commit")
        if not isinstance(cycle, int) or isinstance(cycle, bool) or cycle < 1:
            raise ReviewConsensusError("lens approval cycle must be a positive integer")
        for item in reversed(self._lens_approvals):
            if item.reviewed_commit == commit and item.cycle == cycle:
                return item
        return None

    def latest_lens_approval(self) -> LensApprovalRecord | None:
        if not self._lens_approvals:
            return None
        return self._lens_approvals[-1]

    def record_lens_approval(self, approval: LensApprovalRecord) -> LensApprovalRecord:
        """Persist a commit+cycle approval without changing scoring or selected lenses."""
        if not isinstance(approval, LensApprovalRecord):
            raise ReviewConsensusError("lens approval must be a LensApprovalRecord")
        if approval.cycle > MAX_REVIEW_CYCLES:
            raise ReviewConsensusError(f"lens approval cycle cannot exceed {MAX_REVIEW_CYCLES}")
        known = set(self._policy.lens_dimensions)
        always_on = set(always_on_lenses())
        for lens_id in approval.approved_conditionals:
            if lens_id not in known:
                raise ReviewConsensusError(f"approved conditional {lens_id!r} is not a roster lens")
            if lens_id in always_on:
                raise ReviewConsensusError(
                    f"always-on lens {lens_id!r} is not a conditional approval"
                )
        remaining = tuple(
            item
            for item in self._lens_approvals
            if not (
                item.reviewed_commit == approval.reviewed_commit and item.cycle == approval.cycle
            )
        )
        self._lens_approvals = (*remaining, approval)
        return approval

    def record_cycle(
        self,
        revision: str,
        lens_scores: Mapping[str, LensScore],
        *,
        findings: Iterable[ReviewFinding] = (),
        delta_checks: Iterable[DeltaCheckResult] = (),
        external_review: ExternalAdvisoryReview | None = None,
        resolved_fix_ids: Iterable[str] = (),
        evidence_ledger: Mapping[str, str] | None = None,
    ) -> ReviewResult:
        """Record one review cycle iteration for the current active lenses.

        Advances the review state machine by evaluating provided lens scores,
        reconciling typed findings, validating any required delta checks for
        retained lenses, and computing the current or terminal review outcome.

        Call Order and Lifecycle:
            1. Initialize `ReviewCycleState(selected_lenses=...)`.
            2. Cycle 1 expects scores for all `selected_lenses` (`state.next_lenses`).
            3. If every attempted lens meets policy acceptance criteria (overall minimum and
               dimension floors) and no supplied delta-check failed, the outcome is 'accepted'.
               A failing `DeltaCheckResult` returns its retained lens to the failing set, so a
               cycle whose `lens_scores` all pass can still come back 'repairs_requested'.
            4. If any lens fails, outcome is 'repairs_requested'. In the subsequent cycle,
               `state.next_lenses` contains only the failing lenses.
            5. Subsequent cycles (up to `MAX_REVIEW_CYCLES` = 3) must provide scores for
               `state.next_lenses`. If the candidate cycle would be terminal, `delta_checks`
               must be supplied for previously accepted retained lenses.
            6. Reaching `MAX_REVIEW_CYCLES` with failing lenses results in
               'cycle_cap_best_available'.

        Args:
            revision: Git commit SHA or revision identifier evaluated in this cycle.
            lens_scores: Mapping of lens_id to `LensScore` for each lens in `state.next_lenses`.
            findings: Optional sequence of `ReviewFinding` objects discovered during this cycle.
            delta_checks: Optional sequence of `DeltaCheckResult` objects verifying retained lenses
                against the new revision when reaching a terminal candidate state.
            external_review: Optional `ExternalAdvisoryReview` holding non-scoring advisory evidence.
            resolved_fix_ids: Optional sequence of fix IDs that were resolved in this revision.
            evidence_ledger: Optional mapping of additional evidence key-value pairs.

        Returns:
            ReviewResult: The updated immutable review result reflecting the cumulative state,
            including `outcome` ('accepted', 'repairs_requested', or 'cycle_cap_best_available'),
            `lens_results`, `findings`, `fix_requests`, and `residual_summary`.

        Raises:
            ReviewConsensusError: If the state is already terminal, if `lens_scores` does not
                match `next_lenses`, if a typed finding names an unattempted lens or a `None`
                dimension, if a finding contradicts the scoring evidence already recorded for it,
                or if delta-checks are missing, duplicated, or bound to the wrong revision.
            ReviewScoringError: If reconciling the typed findings re-scores a lens into an
                invalid state - for example a finding naming a dimension its lens does not
                define. `ContradictoryReviewEvidenceError` (also a `ReviewScoringError`) is
                raised when an unresolved critical finding - a P0 that is active, not
                `pre_existing`, and not `advisory` - contradicts the score it is attached to, by
                naming a dimension recorded as non-applicable or by sitting on a dimension that
                scored at or above the floor. Neither class is a `ReviewConsensusError`; see the
                module docstring's exception hierarchy note.
        """
        if self._terminal_outcome is not None or self.cycle_count >= MAX_REVIEW_CYCLES:
            raise ReviewConsensusError("review is terminal; no further cycle is allowed")
        revision = _review_text(revision, label="reviewed revision")
        expected = self.next_lenses
        if set(lens_scores) != set(expected):
            raise ReviewConsensusError(
                f"expected scores for {list(expected)}, got {sorted(lens_scores)}"
            )
        cycle_findings = tuple(findings)
        if any(item.lens_id not in expected for item in cycle_findings):
            raise ReviewConsensusError("cycle finding belongs to an unattempted lens")
        cycle = self.cycle_count + 1
        next_results = dict(self._lens_results)
        regressions = list(self._score_regressions)
        attempts: list[LensReviewResult] = []
        for lens_id in expected:
            score = lens_scores[lens_id]
            if not isinstance(score, LensScore) or score.lens_id != lens_id:
                raise ReviewConsensusError(f"mismatched score for {lens_id!r}")
            score = _score_with_typed_findings(
                score,
                (finding for finding in cycle_findings if finding.lens_id == lens_id),
                policy=self._policy,
            )
            prior = next_results.get(lens_id)
            if prior is not None and score.derived_overall < prior.score.derived_overall:
                regressions.append(
                    ScoreRegression(
                        lens_id=lens_id,
                        previous_revision=prior.reviewed_revision,
                        current_revision=revision,
                        previous_overall=prior.score.derived_overall,
                        current_overall=score.derived_overall,
                        cycle=cycle,
                    )
                )
            current = LensReviewResult(lens_id, revision, cycle, score)
            next_results[lens_id] = current
            attempts.append(current)

        score_failures = {item.lens_id for item in attempts if not item.accepted}
        terminal_candidate = not score_failures or cycle == MAX_REVIEW_CYCLES
        checks = tuple(delta_checks)
        if len({item.lens_id for item in checks}) != len(checks):
            raise ReviewConsensusError("duplicate delta-check")
        expected_checks = {
            lens_id
            for lens_id, item in next_results.items()
            if item.score.accepted and item.reviewed_revision != revision
        }
        if terminal_candidate and {item.lens_id for item in checks} != expected_checks:
            raise ReviewConsensusError(f"expected delta-checks for {sorted(expected_checks)}")
        if not terminal_candidate and checks:
            raise ReviewConsensusError("delta-checks require a candidate final revision")
        delta_failures: set[str] = set()
        for check in checks:
            retained = next_results[check.lens_id]
            if (
                check.reviewed_revision != retained.reviewed_revision
                or check.checked_revision != revision
            ):
                raise ReviewConsensusError("delta-check revision binding is invalid")
            next_results[check.lens_id] = replace(retained, delta_check=check)
            if not check.passed:
                delta_failures.add(check.lens_id)
        failing_set = score_failures | delta_failures
        failing = tuple(lens_id for lens_id in self._selected_lenses if lens_id in failing_set)

        next_findings = self._merge_findings(
            revision=revision,
            attempted_lenses=expected,
            findings=cycle_findings,
            external_review=external_review,
        )
        fix_requests = consolidate_fix_requests(next_findings)
        fix_ids = {item.fix_id for item in fix_requests}
        newly_resolved = set(_review_text_tuple(resolved_fix_ids, label="resolved_fix_ids"))
        if not newly_resolved <= fix_ids:
            raise ReviewConsensusError("resolved identifier does not name a current fix")
        next_resolved = (self._resolved_fix_ids & fix_ids) | newly_resolved
        unresolved = tuple(item.fix_id for item in fix_requests if item.fix_id not in next_resolved)

        record = CycleRecord(
            cycle=cycle,
            revision=revision,
            attempted_lenses=expected,
            lens_results=tuple(attempts),
            delta_checks=checks,
            failing_lenses=failing,
            unresolved_fix_ids=unresolved,
        )
        self._lens_results = next_results
        self._findings = next_findings
        self._cycle_history = (*self._cycle_history, record)
        self._failing_lenses = failing
        self._resolved_fix_ids = next_resolved
        self._score_regressions = tuple(regressions)
        if evidence_ledger is not None:
            self._evidence_ledger.update(
                _review_text_mapping(evidence_ledger, label="evidence_ledger")
            )
        if external_review is not None:
            self._external_reviews = (*self._external_reviews, external_review)
        if not failing:
            self._terminal_outcome = "accepted"
        elif cycle == MAX_REVIEW_CYCLES:
            self._terminal_outcome = "cycle_cap_best_available"
        return self.result()

    def handle_runner_delivery(
        self,
        delivery: Mapping[str, Any],
        *,
        collector: Callable[[dict[str, Any]], Mapping[str, Any]] | None = None,
    ) -> RunnerDeliveryResolution:
        """Process an asynchronous runner delivery payload.

        Args:
            delivery: Mapping whose 'session_outcome' is one of 'pending', 'ran', 'ran-empty',
                'died', or 'not-started', plus an optional 'reason' or 'handle'. Any other value
                is rejected - in particular 'ready' is a `RunnerDeliveryResolution.status` value,
                never an accepted input.
            collector: Optional callback to collect pending runner results.

        Returns:
            RunnerDeliveryResolution whose status is 'ready', 'pending', or 'incomplete'. Note the
            status vocabulary differs from the input vocabulary above: 'ran' maps to 'ready', and
            'ran-empty' / 'died' / 'not-started' map to 'incomplete' via `mark_review_incomplete`.

        Raises:
            ReviewConsensusError: If 'session_outcome' is missing or unknown.
        """
        outcome = delivery.get("session_outcome")
        if outcome == "pending":
            if collector is None:
                return RunnerDeliveryResolution("pending", delivery)
            handle = _review_mapping(delivery.get("handle"), label="pending runner handle")
            return self.handle_runner_delivery(
                collector({"operation": "collect", "handle": dict(handle)})
            )
        if outcome == "ran":
            return RunnerDeliveryResolution("ready", delivery)
        if outcome in {"ran-empty", "died", "not-started"}:
            reason = delivery.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                reason = f"reviewer delivery ended as {outcome}"
            result = self.mark_review_incomplete(reason)
            return RunnerDeliveryResolution("incomplete", delivery, result)
        raise ReviewConsensusError("unknown runner session_outcome")

    def mark_review_incomplete(self, reason: str) -> ReviewResult:
        """Mark the review as terminally incomplete with a specified failure reason.

        Args:
            reason: Non-empty description explaining why the review could not complete.

        Returns:
            ReviewResult: Terminal review result with outcome 'review_incomplete'.

        Raises:
            ReviewConsensusError: If the review already reached a terminal outcome.
        """
        if self._terminal_outcome is not None:
            raise ReviewConsensusError("review already has a terminal outcome")
        self._review_incomplete_reason = _review_text(reason, label="review incomplete reason")
        self._terminal_outcome = "review_incomplete"
        return self.result()

    def result(self) -> ReviewResult:
        """Compute and return the current or terminal immutable ReviewResult.

        Returns:
            ReviewResult: The current aggregated review result reflecting all recorded cycles.

        Raises:
            ReviewConsensusError: If no cycle has been recorded and no outcome has been set.
        """
        if self._terminal_outcome is None:
            if not self._cycle_history:
                raise ReviewConsensusError("review has no result yet")
            outcome: ReviewOutcome = "repairs_requested"
        else:
            outcome = self._terminal_outcome
        lens_results = tuple(
            self._lens_results[lens_id]
            for lens_id in self._selected_lenses
            if lens_id in self._lens_results
        )
        fix_requests = consolidate_fix_requests(self._findings)
        unresolved = tuple(
            item.fix_id for item in fix_requests if item.fix_id not in self._resolved_fix_ids
        )
        attempted = tuple(
            lens_id
            for lens_id in self._selected_lenses
            if any(lens_id in record.attempted_lenses for record in self._cycle_history)
        )
        residual = ResidualSummary(
            lens_results,
            unresolved,
            self._score_regressions,
            self._review_incomplete_reason,
        )
        return ReviewResult(
            selected_lenses=self._selected_lenses,
            attempted_lenses=attempted,
            lens_results=lens_results,
            findings=self._findings,
            cycle_history=self._cycle_history,
            failing_lenses=self._failing_lenses,
            fix_requests=fix_requests,
            unresolved_fix_ids=unresolved,
            best_available_revision=(
                self._cycle_history[-1].revision if self._cycle_history else None
            ),
            residual_summary=residual,
            outcome=outcome,
            evidence_ledger=self._evidence_ledger,
            external_advisory_reviews=self._external_reviews,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize review cycle state to a JSON-compatible dictionary."""
        current_outcome = (
            self._terminal_outcome
            if self._terminal_outcome is not None
            else ("repairs_requested" if self._cycle_history else None)
        )
        return {
            "schema": REVIEW_CYCLE_STATE_SCHEMA,
            "selected_lenses": list(self._selected_lenses),
            "lens_results": [item.to_dict() for item in self._lens_results.values()],
            "findings": [item.to_dict() for item in self._findings],
            "cycle_history": [item.to_dict() for item in self._cycle_history],
            "failing_lenses": list(self._failing_lenses),
            "resolved_fix_ids": sorted(self._resolved_fix_ids),
            "score_regressions": [item.to_dict() for item in self._score_regressions],
            "external_advisory_reviews": [item.to_dict() for item in self._external_reviews],
            "lens_approvals": [item.to_dict() for item in self._lens_approvals],
            "evidence_ledger": dict(self._evidence_ledger),
            "terminal_outcome": self._terminal_outcome,
            "current_outcome": current_outcome,
            "review_incomplete_reason": self._review_incomplete_reason,
        }

    def to_json(self) -> str:
        """Serialize review cycle state to a canonical JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReviewCycleState:
        """Instantiate a ReviewCycleState from a serialized dictionary payload.

        Args:
            payload: Mapping adhering to the review_cycle_state.v1 schema.

        Returns:
            ReviewCycleState instance restored to the serialized point in the lifecycle.

        Raises:
            UnsupportedReviewResultSchemaError: If schema version does not match.
            ReviewConsensusError: If the payload contains contradictory or invalid state.
        """
        schema = payload.get("schema")
        if schema != REVIEW_CYCLE_STATE_SCHEMA:
            raise UnsupportedReviewResultSchemaError(
                f"unsupported review cycle state schema {schema!r}"
            )
        state = cls(
            payload.get("selected_lenses", ()),
            evidence_ledger=_review_text_mapping(
                payload.get("evidence_ledger"), label="evidence_ledger"
            ),
        )
        lens_results = tuple(
            LensReviewResult.from_dict(item)
            for item in _review_mapping_list(
                payload.get("lens_results"), label="state lens_results"
            )
        )
        state._lens_results = {item.lens_id: item for item in lens_results}
        state._findings = tuple(
            ReviewFinding.from_dict(item)
            for item in _review_mapping_list(payload.get("findings"), label="state findings")
        )
        state._cycle_history = tuple(
            CycleRecord.from_dict(item)
            for item in _review_mapping_list(
                payload.get("cycle_history"), label="state cycle_history"
            )
        )
        state._failing_lenses = _review_text_tuple(
            payload.get("failing_lenses", ()), label="failing_lenses"
        )
        state._resolved_fix_ids = set(
            _review_text_tuple(payload.get("resolved_fix_ids", ()), label="resolved_fix_ids")
        )
        state._score_regressions = tuple(
            ScoreRegression.from_dict(item)
            for item in _review_mapping_list(
                payload.get("score_regressions"), label="score_regressions"
            )
        )
        state._external_reviews = tuple(
            ExternalAdvisoryReview.from_dict(item)
            for item in _review_mapping_list(
                payload.get("external_advisory_reviews"),
                label="external_advisory_reviews",
            )
        )
        raw_approvals = payload.get("lens_approvals", [])
        if raw_approvals is None:
            raw_approvals = []
        state._lens_approvals = tuple(
            LensApprovalRecord.from_dict(item)
            for item in _review_mapping_list(
                raw_approvals,
                label="lens_approvals",
            )
        )
        terminal = payload.get("terminal_outcome")
        if terminal not in {
            None,
            "accepted",
            "cycle_cap_best_available",
            "review_incomplete",
        }:
            raise ReviewConsensusError(f"unsupported terminal outcome {terminal!r}")
        state._terminal_outcome = terminal
        state._review_incomplete_reason = payload.get("review_incomplete_reason")
        expected_current = state.to_dict()["current_outcome"]
        if payload.get("current_outcome") != expected_current:
            raise ReviewConsensusError("serialized state outcome is contradictory")
        if state._cycle_history and (
            state._cycle_history[-1].failing_lenses != state._failing_lenses
        ):
            raise ReviewConsensusError("state failing lenses contradict the last cycle")
        if expected_current is not None:
            state.result()
        return state

    @classmethod
    def from_json(cls, payload: str) -> ReviewCycleState:
        """Instantiate a ReviewCycleState from a serialized JSON string.

        Args:
            payload: JSON string adhering to the review_cycle_state.v1 schema.

        Returns:
            ReviewCycleState instance.

        Raises:
            ReviewConsensusError: If JSON decoding fails or state is invalid.
        """
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ReviewConsensusError(f"cycle state is not valid JSON: {exc}") from exc
        return cls.from_dict(_review_mapping(decoded, label="review cycle state"))

    def _merge_findings(
        self,
        *,
        revision: str,
        attempted_lenses: tuple[str, ...],
        findings: tuple[ReviewFinding, ...],
        external_review: ExternalAdvisoryReview | None,
    ) -> tuple[ReviewFinding, ...]:
        if any(item.lens_id not in attempted_lenses for item in findings):
            raise ReviewConsensusError("cycle finding belongs to an unattempted lens")
        retained = [
            item
            for item in self._findings
            if item.lens_id not in attempted_lenses
            and (external_review is None or item.lens_id != "external-reviewer")
        ]
        merged = [*retained, *findings]
        if external_review is not None:
            if external_review.reviewed_revision != revision:
                raise ReviewConsensusError("external review revision does not match cycle")
            merged.extend(external_review.adjudicated_findings)
        if len({item.finding_id for item in merged}) != len(merged):
            raise ReviewConsensusError("duplicate finding identifier")
        severity_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        return tuple(
            sorted(
                merged,
                key=lambda item: (
                    severity_rank[item.severity],
                    -item.confidence,
                    item.file,
                    item.line,
                    item.finding_id,
                ),
            )
        )


def always_on_lenses(roster_path: Path = ROSTER_PATH) -> tuple[str, ...]:
    """Return the roster's always-on lens identifiers in roster order."""
    try:
        payload = json.loads(roster_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewScoringError(f"cannot load lens roster {roster_path}: {exc}") from exc
    roster = _require_mapping(payload, label="lens roster")
    if roster.get("schema") != ROSTER_SCHEMA:
        raise ReviewScoringError(f"unsupported lens roster schema {roster.get('schema')!r}")
    lenses = _require_list(roster.get("lenses"), label="lenses")
    always_on: list[str] = []
    for index, raw_lens in enumerate(lenses):
        lens = _require_mapping(raw_lens, label=f"lenses[{index}]")
        lens_id = _nonempty_text(lens.get("id"), label=f"lenses[{index}].id")
        trigger = _require_mapping(lens.get("trigger"), label=f"lens {lens_id!r} trigger")
        if trigger.get("class") == "always-on":
            always_on.append(lens_id)
    if not always_on:
        raise ReviewScoringError("roster must declare always-on lenses")
    return tuple(always_on)


def _conditional_lens_ids(roster_path: Path = ROSTER_PATH) -> frozenset[str]:
    try:
        payload = json.loads(roster_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewScoringError(f"cannot load lens roster {roster_path}: {exc}") from exc
    roster = _require_mapping(payload, label="lens roster")
    lenses = _require_list(roster.get("lenses"), label="lenses")
    conditionals: set[str] = set()
    for index, raw_lens in enumerate(lenses):
        lens = _require_mapping(raw_lens, label=f"lenses[{index}]")
        lens_id = _nonempty_text(lens.get("id"), label=f"lenses[{index}].id")
        trigger = _require_mapping(lens.get("trigger"), label=f"lens {lens_id!r} trigger")
        if trigger.get("class") == "conditional":
            conditionals.add(lens_id)
    return frozenset(conditionals)


def _require_roster_conditionals(lens_ids: Iterable[str], *, label: str) -> tuple[str, ...]:
    """Fail closed on any id that is not a roster conditional lens.

    `record_lens_approval` validates what it is handed, so the deserialize path has to
    validate too: without this, a round-tripped `review_cycle_state.v1` payload could
    restore an approval naming a lens the roster does not have and `launch_approved_lenses`
    would spawn it.
    """
    values = _review_text_tuple(lens_ids, label=label)
    always_on = set(always_on_lenses())
    conditionals = _conditional_lens_ids()
    for lens_id in values:
        if lens_id in always_on:
            raise ReviewConsensusError(f"always-on lens {lens_id!r} is not a conditional approval")
        if lens_id not in conditionals:
            raise ReviewConsensusError(f"approved conditional {lens_id!r} is not a roster lens")
    return values


def recommend_conditional_lenses(
    judged_applicable: Mapping[str, str],
) -> tuple[ConditionalLensRecommendation, ...]:
    """Validate judged conditional recommendations against the roster.

    `judged_applicable` maps a roster conditional lens id to one plain-language
    reason. Always-on lenses are not recommendations — they auto-run.
    """
    mapping = _review_mapping(judged_applicable, label="judged_applicable")
    conditionals = _conditional_lens_ids()
    always_on = set(always_on_lenses())
    recommendations: list[ConditionalLensRecommendation] = []
    seen: set[str] = set()
    for lens_id, reason in mapping.items():
        identifier = _review_text(lens_id, label="recommended lens_id")
        if identifier in seen:
            raise ReviewConsensusError(f"duplicate conditional recommendation {identifier!r}")
        seen.add(identifier)
        if identifier in always_on:
            raise ReviewConsensusError(
                f"always-on lens {identifier!r} is not a conditional recommendation"
            )
        if identifier not in conditionals:
            raise ReviewConsensusError(f"unknown conditional lens {identifier!r}")
        recommendations.append(
            ConditionalLensRecommendation(
                lens_id=identifier,
                reason=_review_text(reason, label=f"reason for {identifier}"),
            )
        )
    return tuple(recommendations)


def _validate_conditionals(lens_ids: Iterable[str]) -> tuple[str, ...]:
    values = _review_text_tuple(lens_ids, label="conditional lenses")
    always_on = set(always_on_lenses())
    conditionals = _conditional_lens_ids()
    cleaned: list[str] = []
    for lens_id in values:
        if lens_id in always_on:
            continue
        if lens_id not in conditionals:
            raise ReviewConsensusError(f"unknown conditional lens {lens_id!r}")
        cleaned.append(lens_id)
    return tuple(cleaned)


def _approved_from_choice(
    choice: LensLaunchChoice,
    recommended: tuple[ConditionalLensRecommendation, ...],
    customized: tuple[str, ...],
) -> tuple[str, ...]:
    if choice == "accept-recommended":
        return tuple(item.lens_id for item in recommended)
    if choice == "always-on-only":
        return ()
    return customized


def _launch_set(approved_conditionals: tuple[str, ...]) -> tuple[str, ...]:
    always_on = always_on_lenses()
    return (*always_on, *approved_conditionals)


def _question(
    kind: LensQuestionKind,
    recommended: tuple[ConditionalLensRecommendation, ...],
    *,
    delta_added: tuple[ConditionalLensRecommendation, ...] = (),
    delta_removed: tuple[str, ...] = (),
) -> LensSelectionQuestion:
    return LensSelectionQuestion(
        kind=kind,
        recommended=recommended,
        delta_added=delta_added,
        delta_removed=delta_removed,
    )


def _paused_decision(
    reviewed_commit: str,
    cycle: int,
    recommended: tuple[ConditionalLensRecommendation, ...],
    question: LensSelectionQuestion,
    *,
    reused: bool = False,
) -> LensSelectionDecision:
    return LensSelectionDecision(
        reviewed_commit=reviewed_commit,
        cycle=cycle,
        launch_set=always_on_lenses(),
        approved_conditionals=(),
        recommended=recommended,
        needs_question=True,
        paused=True,
        reused=reused,
        question=question,
        approval=None,
    )


def _approved_decision(
    approval: LensApprovalRecord,
    *,
    needs_question: bool = False,
    reused: bool = False,
    question: LensSelectionQuestion | None = None,
) -> LensSelectionDecision:
    return LensSelectionDecision(
        reviewed_commit=approval.reviewed_commit,
        cycle=approval.cycle,
        launch_set=_launch_set(approval.approved_conditionals),
        approved_conditionals=approval.approved_conditionals,
        recommended=approval.recommended,
        needs_question=needs_question,
        paused=False,
        reused=reused,
        question=question,
        approval=approval,
    )


def resolve_lens_selection(
    *,
    reviewed_commit: str,
    cycle: int,
    recommended: Iterable[ConditionalLensRecommendation] = (),
    state: ReviewCycleState | None = None,
    operator_choice: LensLaunchChoice | None = None,
    customized_conditionals: Iterable[str] = (),
    caller_selection: Iterable[str] | None = None,
    caller_source: LensApprovalSource = "caller",
) -> LensSelectionDecision:
    """Resolve the approved conditional set for one reviewed commit and cycle.

    Always-on lenses auto-run. A caller- or Orchestrate-supplied selection is
    approval and is not re-asked. Repair cycles reuse a prior approval unless the
    judged applicable set changed; then only the delta is asked. Dismissal or no
    answer pauses with no conditional launches and no persisted approval.
    """
    commit = _review_text(reviewed_commit, label="reviewed_commit")
    if not isinstance(cycle, int) or isinstance(cycle, bool) or cycle < 1:
        raise ReviewConsensusError("lens approval cycle must be a positive integer")
    if cycle > MAX_REVIEW_CYCLES:
        raise ReviewConsensusError(f"lens approval cycle cannot exceed {MAX_REVIEW_CYCLES}")
    recommendations = tuple(recommended)
    for item in recommendations:
        if not isinstance(item, ConditionalLensRecommendation):
            raise ReviewConsensusError("recommended lenses must be typed recommendations")
    recommend_conditional_lenses({item.lens_id: item.reason for item in recommendations})
    customized = _validate_conditionals(customized_conditionals)
    if operator_choice is not None and operator_choice not in _LENS_LAUNCH_CHOICES:
        raise ReviewConsensusError(f"unsupported lens selection choice {operator_choice!r}")
    if caller_source not in _LENS_APPROVAL_SOURCES:
        raise ReviewConsensusError(f"unsupported lens approval source {caller_source!r}")

    if caller_selection is not None:
        approved = _validate_conditionals(caller_selection)
        approval = LensApprovalRecord(
            reviewed_commit=commit,
            cycle=cycle,
            approved_conditionals=approved,
            recommended=recommendations,
            source=caller_source,
            question_asked=False,
        )
        if state is not None:
            state.record_lens_approval(approval)
        return _approved_decision(approval)

    if state is not None:
        exact = state.lens_approval_for(commit, cycle)
        if exact is not None:
            return _approved_decision(exact, reused=True)
        prior = state.latest_lens_approval()
        if prior is not None:
            recommended_set = {item.lens_id for item in recommendations}
            prior_recommended = {item.lens_id for item in prior.recommended}
            prior_approved = prior.approved_conditionals
            # Applicability is a set, not an ordering: the same judgement rebuilt in a
            # different order is unchanged and must not re-ask. Only a conditional the
            # prior judgement never raised is a new question; one that merely stopped
            # applying is dropped silently because it has no work left to do.
            added = tuple(item for item in recommendations if item.lens_id not in prior_recommended)
            removed = tuple(lens_id for lens_id in prior_approved if lens_id not in recommended_set)
            still_applicable = tuple(
                lens_id for lens_id in prior_approved if lens_id in recommended_set
            )
            if not added:
                reused = LensApprovalRecord(
                    reviewed_commit=commit,
                    cycle=cycle,
                    approved_conditionals=still_applicable,
                    recommended=recommendations,
                    source=prior.source,
                    question_asked=False,
                )
                state.record_lens_approval(reused)
                return _approved_decision(reused, reused=True)
            question = _question(
                "delta",
                recommendations,
                delta_added=added,
                delta_removed=removed,
            )
            if operator_choice is None:
                return _paused_decision(commit, cycle, recommendations, question, reused=True)
            # A delta question decides only the delta: previously approved lenses that
            # still apply are kept, and previously declined ones stay declined.
            if operator_choice == "accept-recommended":
                approved = (*still_applicable, *(item.lens_id for item in added))
            elif operator_choice == "always-on-only":
                approved = still_applicable
            else:
                extra = tuple(lens_id for lens_id in customized if lens_id not in still_applicable)
                approved = (*still_applicable, *extra)
            approval = LensApprovalRecord(
                reviewed_commit=commit,
                cycle=cycle,
                approved_conditionals=approved,
                recommended=recommendations,
                source="operator",
                question_asked=True,
            )
            state.record_lens_approval(approval)
            return _approved_decision(approval, question=question)

    question = _question("full", recommendations)
    if operator_choice is None:
        return _paused_decision(commit, cycle, recommendations, question)
    approved = _approved_from_choice(operator_choice, recommendations, customized)
    approval = LensApprovalRecord(
        reviewed_commit=commit,
        cycle=cycle,
        approved_conditionals=approved,
        recommended=recommendations,
        source="operator",
        question_asked=True,
    )
    if state is not None:
        state.record_lens_approval(approval)
    return _approved_decision(approval, question=question)


def _spawn_lens_agent(
    lens_id: str,
    *,
    allowed_conditionals: frozenset[str],
    agent: AgentCallTranscript,
) -> None:
    always_on = set(always_on_lenses())
    if lens_id in always_on:
        agent.spawn_agent(lens_id)
        return
    if lens_id not in allowed_conditionals:
        raise ReviewConsensusError(
            f"refusing Agent spawn for unapproved conditional lens {lens_id!r}"
        )
    agent.spawn_agent(lens_id)


def launch_approved_lenses(
    *,
    reviewed_commit: str,
    cycle: int,
    state: ReviewCycleState | None = None,
    decision: LensSelectionDecision | None = None,
    extra_lenses: Iterable[str] = (),
    agent: AgentCallTranscript | None = None,
) -> tuple[str, ...]:
    """Spawn always-on lenses, then only approved conditionals.

    A conditional lens is never passed to the Agent spawn until an approval
    record exists for this reviewed commit and cycle. Extra/hidden lenses are
    refused before the spawn call.
    """
    transcript = agent if agent is not None else AgentCallTranscript()
    commit = _review_text(reviewed_commit, label="reviewed_commit")
    if not isinstance(cycle, int) or isinstance(cycle, bool) or cycle < 1:
        raise ReviewConsensusError("lens approval cycle must be a positive integer")
    approval: LensApprovalRecord | None = None
    paused = False
    if decision is not None:
        if decision.reviewed_commit != commit or decision.cycle != cycle:
            raise ReviewConsensusError("launch decision does not match reviewed commit+cycle")
        paused = decision.paused
        approval = decision.approval
    if approval is None and state is not None:
        approval = state.lens_approval_for(commit, cycle)
    allowed = frozenset(approval.approved_conditionals if approval is not None else ())
    if paused:
        allowed = frozenset()
    launched: list[str] = []
    seen: set[str] = set()

    def _launch_once(lens_id: str) -> None:
        # A lens only reaches `seen` after passing the spawn guard, so skipping a repeat
        # never bypasses validation — it just stops one lens being reviewed twice.
        if lens_id in seen:
            return
        _spawn_lens_agent(lens_id, allowed_conditionals=allowed, agent=transcript)
        seen.add(lens_id)
        launched.append(lens_id)

    for lens_id in always_on_lenses():
        _launch_once(lens_id)
    if approval is not None and not paused:
        transcript.record_approval(approval.reviewed_commit, approval.cycle)
        if state is not None and state.lens_approval_for(commit, cycle) is None:
            state.record_lens_approval(approval)
        for lens_id in approval.approved_conditionals:
            _launch_once(lens_id)
    for lens_id in _review_text_tuple(extra_lenses, label="extra_lenses") if extra_lenses else ():
        _launch_once(lens_id)
    return tuple(launched)


def load_scoring_policy(roster_path: Path = ROSTER_PATH) -> ReviewScoringPolicy:
    """Load and fail closed on the scoring contract owned by the canonical U4 roster."""
    try:
        payload = json.loads(roster_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewScoringError(f"cannot load lens roster {roster_path}: {exc}") from exc

    roster = _require_mapping(payload, label="lens roster")
    if roster.get("schema") != ROSTER_SCHEMA:
        raise ReviewScoringError(f"unsupported lens roster schema {roster.get('schema')!r}")

    score_scale = _require_mapping(roster.get("score_scale"), label="score_scale")
    minimum_score = _finite_number(score_scale.get("minimum"), label="score_scale.minimum")
    maximum_score = _finite_number(score_scale.get("maximum"), label="score_scale.maximum")
    if minimum_score >= maximum_score:
        raise ReviewScoringError("score_scale minimum must be lower than maximum")

    acceptance = _require_mapping(roster.get("acceptance"), label="acceptance")
    if acceptance.get("combiner") != "all":
        raise ReviewScoringError("acceptance rules must use the all combiner")
    if acceptance.get("only_acceptance_thresholds") is not True:
        raise ReviewScoringError("roster must identify its rules as the only acceptance thresholds")
    if acceptance.get("finding_priority_is_gate") is not False:
        raise ReviewScoringError("finding priority must remain metadata, not an acceptance gate")
    if acceptance.get("finding_confidence_is_gate") is not False:
        raise ReviewScoringError("finding confidence must remain metadata, not an acceptance gate")

    rules = _require_list(acceptance.get("rules"), label="acceptance.rules")
    rules_by_id: dict[str, Mapping[str, Any]] = {}
    for index, raw_rule in enumerate(rules):
        rule = _require_mapping(raw_rule, label=f"acceptance.rules[{index}]")
        rule_id = _nonempty_text(rule.get("id"), label=f"acceptance.rules[{index}].id")
        if rule_id in rules_by_id:
            raise ReviewScoringError(f"duplicate acceptance rule {rule_id!r}")
        rules_by_id[rule_id] = rule

    expected_rules = {
        OVERALL_RULE_ID: "derived_overall",
        DIMENSION_FLOOR_RULE_ID: "applicable_dimension",
    }
    if set(rules_by_id) != set(expected_rules):
        raise ReviewScoringError(
            "acceptance.rules must contain only the derived-overall minimum and dimension floor"
        )

    threshold_values: dict[str, float] = {}
    for rule_id, expected_metric in expected_rules.items():
        rule = rules_by_id[rule_id]
        if rule.get("metric") != expected_metric or rule.get("operator") != ">=":
            raise ReviewScoringError(f"acceptance rule {rule_id!r} has an unsupported predicate")
        threshold_values[rule_id] = _score_value(
            rule.get("value"),
            minimum_score=minimum_score,
            maximum_score=maximum_score,
            label=f"acceptance rule {rule_id!r}",
        )

    applicability = _require_mapping(roster.get("applicability"), label="applicability")
    if applicability.get("selected_lens_requires_applicable_dimension") is not True:
        raise ReviewScoringError("selected lenses must require an applicable dimension")
    if applicability.get("non_applicable_dimension_requires_cause") is not True:
        raise ReviewScoringError("non-applicable dimensions must require a cause")

    lenses = _require_list(roster.get("lenses"), label="lenses")
    lens_dimensions: dict[str, tuple[str, ...]] = {}
    for lens_index, raw_lens in enumerate(lenses):
        lens = _require_mapping(raw_lens, label=f"lenses[{lens_index}]")
        lens_id = _nonempty_text(lens.get("id"), label=f"lenses[{lens_index}].id")
        if lens_id in lens_dimensions:
            raise ReviewScoringError(f"duplicate lens identifier {lens_id!r}")
        raw_dimensions = _require_list(lens.get("dimensions"), label=f"lens {lens_id!r} dimensions")
        dimension_ids = tuple(
            _nonempty_text(
                _require_mapping(raw_dimension, label=f"lens {lens_id!r} dimension").get("id"),
                label=f"lens {lens_id!r} dimension id",
            )
            for raw_dimension in raw_dimensions
        )
        if not dimension_ids:
            raise ReviewScoringError(f"lens {lens_id!r} must declare at least one dimension")
        if len(set(dimension_ids)) != len(dimension_ids):
            raise ReviewScoringError(f"lens {lens_id!r} has duplicate dimension identifiers")
        lens_dimensions[lens_id] = dimension_ids

    if not lens_dimensions:
        raise ReviewScoringError("lens roster must declare at least one scoring lens")

    return ReviewScoringPolicy(
        minimum_score=minimum_score,
        maximum_score=maximum_score,
        overall_minimum=threshold_values[OVERALL_RULE_ID],
        dimension_floor=threshold_values[DIMENSION_FLOOR_RULE_ID],
        lens_dimensions=MappingProxyType(lens_dimensions),
    )


def score_lens_review(
    lens_id: str,
    applicable_dimensions: Mapping[str, float],
    *,
    non_applicable_dimensions: Mapping[str, str] | None = None,
    reported_overall: float | None = None,
    findings: Iterable[FindingEvidence] = (),
    policy: ReviewScoringPolicy | None = None,
) -> LensScore:
    """Validate and score one selected lens using only the roster's acceptance rules."""
    if policy is None:
        policy = DEFAULT_SCORING_POLICY
    lens_id = _nonempty_text(lens_id, label="lens_id")
    declared_dimensions = policy.dimensions_for(lens_id)
    dimension_scores = _normalize_dimension_scores(
        applicable_dimensions,
        policy=policy,
        lens_id=lens_id,
    )
    if not dimension_scores:
        raise ReviewScoringError(
            f"selected lens {lens_id!r} must provide at least one applicable dimension"
        )
    excluded_dimensions = _normalize_non_applicable_dimensions(
        non_applicable_dimensions or {}, lens_id=lens_id
    )

    duplicated = set(dimension_scores) & set(excluded_dimensions)
    if duplicated:
        raise ReviewScoringError(
            f"lens {lens_id!r} dimensions cannot be both applicable and non-applicable: "
            f"{sorted(duplicated)}"
        )

    provided_dimensions = set(dimension_scores) | set(excluded_dimensions)
    declared_set = set(declared_dimensions)
    unknown_dimensions = provided_dimensions - declared_set
    if unknown_dimensions:
        raise ReviewScoringError(
            f"lens {lens_id!r} has unknown dimensions: {sorted(unknown_dimensions)}"
        )
    missing_dimensions = declared_set - provided_dimensions
    if missing_dimensions:
        raise ReviewScoringError(
            f"lens {lens_id!r} has missing dimensions: {sorted(missing_dimensions)}"
        )

    ordered_scores = {
        dimension_id: dimension_scores[dimension_id]
        for dimension_id in declared_dimensions
        if dimension_id in dimension_scores
    }
    ordered_exclusions = {
        dimension_id: excluded_dimensions[dimension_id]
        for dimension_id in declared_dimensions
        if dimension_id in excluded_dimensions
    }
    derived_overall = math.fsum(ordered_scores.values()) / len(ordered_scores)

    if reported_overall is not None:
        normalized_overall = _score_value(
            reported_overall,
            minimum_score=policy.minimum_score,
            maximum_score=policy.maximum_score,
            label=f"lens {lens_id!r} reported overall",
        )
        if not math.isclose(normalized_overall, derived_overall):
            raise ContradictoryReviewEvidenceError(
                f"lens {lens_id!r} reported overall {normalized_overall} contradicts "
                f"derived overall {derived_overall}"
            )

    normalized_findings = _normalize_findings(
        findings,
        lens_id=lens_id,
        declared_dimensions=declared_set,
        dimension_scores=ordered_scores,
        dimension_floor=policy.dimension_floor,
    )
    failing_dimensions = tuple(
        dimension_id
        for dimension_id in declared_dimensions
        if dimension_id in ordered_scores and ordered_scores[dimension_id] < policy.dimension_floor
    )
    accepted = derived_overall >= policy.overall_minimum and not failing_dimensions

    return LensScore(
        lens_id=lens_id,
        dimension_scores=ordered_scores,
        non_applicable_dimensions=ordered_exclusions,
        derived_overall=derived_overall,
        accepted=accepted,
        failing_dimensions=failing_dimensions,
        findings=normalized_findings,
    )


def evaluate_review_readiness(
    lens_scores: Iterable[LensScore],
    independent_gates: Iterable[IndependentGateResult] = (),
) -> ReviewReadiness:
    """Combine lens acceptance with non-scoring gates without changing either result.

    Evaluates whether a change is ready to proceed by combining the scoring outcomes
    of review lenses with independent binary gate results (e.g. CI checks, test suites,
    linter runs). Both all review lenses and all independent gates must pass for
    `can_proceed` to be True.

    Call Order:
        Typically invoked after scoring review lenses - directly via `score_lens_review`, or
        from a recorded cycle as `[item.score for item in ReviewResult.lens_results]`
        (`ReviewResult` carries `lens_results`, a tuple of `LensReviewResult`; it has no
        `lens_scores` attribute) - and after collecting results for the independent
        non-scoring verification gates.

    Args:
        lens_scores: Non-empty iterable of unique `LensScore` objects to evaluate.
        independent_gates: Optional iterable of unique `IndependentGateResult` objects
            representing non-scoring verification gates.

    Returns:
        ReviewReadiness: An immutable readiness object containing:
            - `can_proceed`: True if `review_accepted` and `independent_gates_passed` are both True.
            - `review_accepted`: True if all provided `LensScore` instances are accepted.
            - `independent_gates_passed`: True if all provided `IndependentGateResult`
              instances passed.
            - `failing_lenses`: Tuple of lens IDs that failed scoring acceptance.
            - `failed_independent_gates`: Tuple of gate IDs that did not pass.
            - `lens_scores`: Tuple of the evaluated `LensScore` instances.
            - `independent_gates`: Tuple of the evaluated `IndependentGateResult` instances.

    Raises:
        ReviewScoringError: If `lens_scores` is empty, contains non-LensScore items,
            or contains duplicate lens IDs; or if `independent_gates` contains invalid
            gate values or duplicate gate IDs.
    """
    scores = tuple(lens_scores)
    if not scores:
        raise ReviewScoringError("review readiness requires at least one lens score")
    if any(not isinstance(score, LensScore) for score in scores):
        raise ReviewScoringError("review readiness accepts only LensScore values")
    lens_ids = [score.lens_id for score in scores]
    if len(set(lens_ids)) != len(lens_ids):
        raise ReviewScoringError("review readiness received duplicate lens scores")

    gates = tuple(independent_gates)
    gate_ids: list[str] = []
    for gate in gates:
        if not isinstance(gate, IndependentGateResult):
            raise ReviewScoringError(
                "review readiness accepts only IndependentGateResult gate values"
            )
        gate_ids.append(_nonempty_text(gate.gate_id, label="independent gate id"))
        if not isinstance(gate.passed, bool):
            raise ReviewScoringError(f"independent gate {gate.gate_id!r} passed must be boolean")
    if len(set(gate_ids)) != len(gate_ids):
        raise ReviewScoringError("review readiness received duplicate independent gates")

    failing_lenses = tuple(score.lens_id for score in scores if not score.accepted)
    failed_independent_gates = tuple(gate.gate_id for gate in gates if not gate.passed)
    review_accepted = not failing_lenses
    independent_gates_passed = not failed_independent_gates
    return ReviewReadiness(
        lens_scores=scores,
        independent_gates=gates,
        review_accepted=review_accepted,
        independent_gates_passed=independent_gates_passed,
        failing_lenses=failing_lenses,
        failed_independent_gates=failed_independent_gates,
        can_proceed=review_accepted and independent_gates_passed,
    )


def _normalize_dimension_scores(
    values: Mapping[str, float],
    *,
    policy: ReviewScoringPolicy,
    lens_id: str,
) -> dict[str, float]:
    if not isinstance(values, Mapping):
        raise ReviewScoringError(f"lens {lens_id!r} applicable dimensions must be a mapping")
    normalized: dict[str, float] = {}
    for raw_dimension_id, value in values.items():
        dimension_id = _nonempty_text(
            raw_dimension_id, label=f"lens {lens_id!r} applicable dimension id"
        )
        normalized[dimension_id] = _score_value(
            value,
            minimum_score=policy.minimum_score,
            maximum_score=policy.maximum_score,
            label=f"lens {lens_id!r} dimension {dimension_id!r}",
        )
    return normalized


def _normalize_non_applicable_dimensions(
    values: Mapping[str, str], *, lens_id: str
) -> dict[str, str]:
    if not isinstance(values, Mapping):
        raise ReviewScoringError(f"lens {lens_id!r} non-applicable dimensions must be a mapping")
    normalized: dict[str, str] = {}
    for raw_dimension_id, raw_cause in values.items():
        dimension_id = _nonempty_text(
            raw_dimension_id, label=f"lens {lens_id!r} non-applicable dimension id"
        )
        try:
            cause = _nonempty_text(
                raw_cause,
                label=f"non-applicable dimension {dimension_id!r} cause",
            )
        except ReviewScoringError as exc:
            raise ReviewScoringError(
                f"lens {lens_id!r} non-applicable dimension {dimension_id!r} requires a cause"
            ) from exc
        normalized[dimension_id] = cause
    return normalized


def _normalize_findings(
    findings: Iterable[FindingEvidence],
    *,
    lens_id: str,
    declared_dimensions: set[str],
    dimension_scores: Mapping[str, float],
    dimension_floor: float,
) -> tuple[FindingEvidence, ...]:
    normalized = tuple(findings)
    finding_ids: set[str] = set()
    for finding in normalized:
        if not isinstance(finding, FindingEvidence):
            raise ReviewScoringError(f"lens {lens_id!r} findings must be FindingEvidence values")
        finding_id = _nonempty_text(finding.finding_id, label="finding_id")
        dimension_id = _nonempty_text(
            finding.dimension_id, label=f"finding {finding_id!r} dimension"
        )
        if finding_id in finding_ids:
            raise ReviewScoringError(f"lens {lens_id!r} has duplicate finding {finding_id!r}")
        finding_ids.add(finding_id)
        if dimension_id not in declared_dimensions:
            raise ReviewScoringError(
                f"finding {finding_id!r} names unknown dimension {dimension_id!r}"
            )
        if not isinstance(finding.critical, bool) or not isinstance(finding.resolved, bool):
            raise ReviewScoringError(
                f"finding {finding_id!r} critical and resolved fields must be boolean"
            )
        if finding.critical and not finding.resolved:
            if dimension_id not in dimension_scores:
                raise ContradictoryReviewEvidenceError(
                    f"unresolved critical finding {finding_id!r} contradicts non-applicable "
                    f"dimension {dimension_id!r}"
                )
            if dimension_scores[dimension_id] >= dimension_floor:
                raise ContradictoryReviewEvidenceError(
                    f"unresolved critical finding {finding_id!r} contradicts passing score "
                    f"for dimension {dimension_id!r}"
                )
    return normalized


def _require_mapping(value: object, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReviewScoringError(f"{label} must be an object")
    return value


def _require_list(value: object, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReviewScoringError(f"{label} must be a list")
    return value


def _nonempty_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewScoringError(f"{label} must be non-empty text")
    return value.strip()


def _finite_number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReviewScoringError(f"{label} must be a finite number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ReviewScoringError(f"{label} must be a finite number")
    return normalized


def _score_value(
    value: object,
    *,
    minimum_score: float,
    maximum_score: float,
    label: str,
) -> float:
    try:
        normalized = _finite_number(value, label=label)
    except ReviewScoringError as exc:
        raise ReviewScoringError(
            f"{label} must be a finite number within {minimum_score}..{maximum_score}"
        ) from exc
    if not minimum_score <= normalized <= maximum_score:
        raise ReviewScoringError(
            f"{label} must be a finite number within {minimum_score}..{maximum_score}"
        )
    return normalized


DEFAULT_SCORING_POLICY = load_scoring_policy()
ALWAYS_ON_LENSES = always_on_lenses()
