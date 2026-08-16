#!/usr/bin/env python3
"""Consensus-panel policy: layer configuration, roster custody, quorum, and instruments.

The review-loop bound deliberately does not import this module, and this module does not import
the loop bound. A layer chooses whether it has a panel. A panel then decides whether its complete
set of voting seats permits work to proceed.

Proceeding and halting are asymmetric. Proceeding requires a performed, schema-complete response
from every constructed voting seat and no blocking gate rank. One blocking gate rank is sufficient
to halt, even when another seat is missing. A missing or malformed response is never treated as a
clean review, and an under-strength roster never acquires the authority of the requested quorum.

The normal roster builder excludes the vendor that built the unit from every roster and also
excludes the home vendor from an external-only roster. It permits at most one seat per vendor,
because vendor identity is this module's unit of independent judgment. Constructors are not a
security boundary in Python, so :func:`evaluate_panel` rebuilds and revalidates the configuration,
roster, seats, and responses before it can return ``proceed``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

PanelPolicy = Literal["required", "optional", "absent"]
PANEL_REQUIRED: Literal["required"] = "required"
PANEL_OPTIONAL: Literal["optional"] = "optional"
PANEL_ABSENT: Literal["absent"] = "absent"

LAYER_PANEL_POLICIES: Mapping[str, PanelPolicy] = MappingProxyType(
    {
        "code-review": PANEL_REQUIRED,
        "qa": PANEL_REQUIRED,
        "doc-review": PANEL_OPTIONAL,
        "orchestration-plan": PANEL_ABSENT,
    }
)

Instrument = Literal["gate", "score"]
GATE: Literal["gate"] = "gate"
SCORE: Literal["score"] = "score"

RosterMode = Literal["standard", "external-only"]
STANDARD_ROSTER: Literal["standard"] = "standard"
EXTERNAL_ONLY_ROSTER: Literal["external-only"] = "external-only"

PanelDecision = Literal["proceed", "halt"]
PANEL_PROCEED: Literal["proceed"] = "proceed"
PANEL_HALT: Literal["halt"] = "halt"

RANKS: tuple[str, ...] = ("P0", "P1", "P2", "P3", "pass")
_RANK_ORDER: Mapping[str, int] = MappingProxyType(
    {rank: position for position, rank in enumerate(RANKS)}
)


class ConsensusPanelError(Exception):
    """The panel refused an invalid configuration, roster, or response."""


@dataclass(frozen=True, slots=True)
class Dimension:
    """One declared review dimension and the instrument that measures it.

    A gate uses a blocking rank and cannot carry a numeric threshold. A score uses a numeric
    convergence threshold and cannot carry a blocking rank. Scores describe convergence; they do
    not decide whether the panel permits work to proceed.
    """

    name: str
    instrument: Instrument
    threshold: float | None = None
    blocking_rank: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_non_empty(self.name, what="dimension name"))
        if self.instrument not in {GATE, SCORE}:
            raise ConsensusPanelError(
                f"unknown instrument {self.instrument!r}; expected {GATE!r} or {SCORE!r}"
            )
        if self.instrument == GATE:
            if self.threshold is not None:
                raise ConsensusPanelError("a gate dimension refuses a numeric threshold")
            if self.blocking_rank not in _RANK_ORDER or self.blocking_rank == "pass":
                raise ConsensusPanelError(
                    "a gate dimension needs a blocking_rank from P0, P1, P2, or P3"
                )
            return
        if self.blocking_rank is not None:
            raise ConsensusPanelError("a score dimension refuses a blocking rank")
        _require_score(self.threshold, what=f"threshold for score dimension {self.name!r}")

    @classmethod
    def gate(cls, name: str, *, blocking_rank: str = "P1") -> Dimension:
        return cls(name=name, instrument=GATE, blocking_rank=blocking_rank)

    @classmethod
    def score(cls, name: str, *, threshold: float = 9.0) -> Dimension:
        return cls(name=name, instrument=SCORE, threshold=threshold)


@dataclass(frozen=True, slots=True)
class PanelConfiguration:
    """Whether one lifecycle layer has a panel and, when enabled, its dimensions."""

    layer: str
    policy: PanelPolicy
    enabled: bool
    dimensions: tuple[Dimension, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ConsensusPanelError("panel enabled must be a boolean")
        expected = LAYER_PANEL_POLICIES.get(self.layer)
        if expected is None:
            raise ConsensusPanelError(
                f"unknown review layer {self.layer!r}; expected one of "
                f"{sorted(LAYER_PANEL_POLICIES)}"
            )
        if self.policy != expected:
            raise ConsensusPanelError(
                f"layer {self.layer!r} has panel policy {expected!r}, not {self.policy!r}"
            )
        if expected == PANEL_REQUIRED and not self.enabled:
            raise ConsensusPanelError(f"layer {self.layer!r} requires a consensus panel")
        if expected == PANEL_ABSENT and self.enabled:
            raise ConsensusPanelError(
                "the orchestration-plan review has one voter and cannot enable a panel"
            )
        collected = tuple(self.dimensions)
        object.__setattr__(self, "dimensions", collected)
        if not self.enabled and collected:
            raise ConsensusPanelError("a disabled panel cannot declare dimensions")
        if self.enabled and not collected:
            raise ConsensusPanelError("an enabled panel needs at least one dimension")
        if not all(type(dimension) is Dimension for dimension in collected):
            raise ConsensusPanelError("panel dimensions must be Dimension values")
        if self.enabled and not any(dimension.instrument == GATE for dimension in collected):
            raise ConsensusPanelError("an enabled panel needs at least one gate dimension")
        names = [dimension.name for dimension in collected]
        if len(names) != len(set(names)):
            raise ConsensusPanelError("panel dimension names must be unique")

    @classmethod
    def for_layer(
        cls,
        layer: str,
        *,
        dimensions: Sequence[Dimension] = (),
        enabled: bool | None = None,
    ) -> PanelConfiguration:
        policy = LAYER_PANEL_POLICIES.get(layer)
        if policy is None:
            raise ConsensusPanelError(
                f"unknown review layer {layer!r}; expected one of {sorted(LAYER_PANEL_POLICIES)}"
            )
        if enabled is None:
            enabled = policy == PANEL_REQUIRED
        return cls(layer=layer, policy=policy, enabled=enabled, dimensions=tuple(dimensions))


@dataclass(frozen=True, slots=True)
class ReviewerCandidate:
    """A possible voting seat before builder and external-only exclusions are applied."""

    seat_id: str
    vendor: str
    lens: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "seat_id", _require_non_empty(self.seat_id, what="reviewer seat_id")
        )
        object.__setattr__(self, "vendor", _require_non_empty(self.vendor, what="reviewer vendor"))
        object.__setattr__(self, "lens", _require_non_empty(self.lens, what="reviewer lens"))


_SEAT_CONSTRUCTOR = object()


@dataclass(frozen=True, slots=True, init=False)
class VotingSeat:
    """An eligible reviewer minted through the normal roster-building API."""

    seat_id: str
    vendor: str
    lens: str

    def __init__(
        self,
        seat_id: str,
        vendor: str,
        lens: str,
        *,
        _constructor: object,
    ) -> None:
        if _constructor is not _SEAT_CONSTRUCTOR:
            raise ConsensusPanelError("voting seats must be constructed by build_roster")
        object.__setattr__(self, "seat_id", _require_non_empty(seat_id, what="voting seat_id"))
        object.__setattr__(self, "vendor", _canonical_vendor(vendor))
        object.__setattr__(self, "lens", _require_non_empty(lens, what="voting seat lens"))


@dataclass(frozen=True, slots=True)
class ExcludedCandidate:
    """A requested reviewer that cannot become a voting seat."""

    candidate: ReviewerCandidate
    reason: str


@dataclass(frozen=True, slots=True)
class PanelRoster:
    """The full requested denominator after structural exclusions."""

    layer: str
    mode: RosterMode
    built_vendor: str
    home_vendor: str
    quorum: int
    seats: tuple[VotingSeat, ...]
    excluded: tuple[ExcludedCandidate, ...]

    def __post_init__(self) -> None:
        policy = LAYER_PANEL_POLICIES.get(self.layer)
        if policy is None:
            raise ConsensusPanelError(
                f"unknown review layer {self.layer!r}; expected one of "
                f"{sorted(LAYER_PANEL_POLICIES)}"
            )
        if policy == PANEL_ABSENT:
            raise ConsensusPanelError("the orchestration-plan review cannot have a panel roster")
        if self.mode not in {STANDARD_ROSTER, EXTERNAL_ONLY_ROSTER}:
            raise ConsensusPanelError(f"unknown roster mode {self.mode!r}")
        _require_quorum(self.quorum)
        built = _canonical_vendor(self.built_vendor)
        home = _canonical_vendor(self.home_vendor)
        object.__setattr__(self, "built_vendor", built)
        object.__setattr__(self, "home_vendor", home)
        if type(self.seats) is not tuple:
            raise ConsensusPanelError("voting seats must be held in an immutable tuple")
        if type(self.excluded) is not tuple:
            raise ConsensusPanelError("excluded candidates must be held in an immutable tuple")
        vendors: list[str] = []
        for seat in self.seats:
            if type(seat) is not VotingSeat:
                raise ConsensusPanelError("a roster may contain only VotingSeat values")
            seat_id = _require_non_empty(seat.seat_id, what="voting seat_id")
            vendor = _canonical_vendor(seat.vendor)
            _require_non_empty(seat.lens, what=f"lens for voting seat {seat_id!r}")
            if vendor == built:
                raise ConsensusPanelError("the unit builder's vendor cannot hold a voting seat")
            if self.mode == EXTERNAL_ONLY_ROSTER and vendor == home:
                raise ConsensusPanelError(
                    "the home vendor cannot hold a voting seat in an external-only roster"
                )
            vendors.append(vendor)
        identifiers = [seat.seat_id for seat in self.seats]
        if len(identifiers) != len(set(identifiers)):
            raise ConsensusPanelError("voting seat identifiers must be unique")
        if len(vendors) != len(set(vendors)):
            raise ConsensusPanelError("voting seat vendors must be unique")
        excluded_identifiers: list[str] = []
        for item in self.excluded:
            if type(item) is not ExcludedCandidate or type(item.candidate) is not ReviewerCandidate:
                raise ConsensusPanelError("excluded candidates must be ExcludedCandidate values")
            expected_reason = _eligibility_exclusion(
                item.candidate,
                built_vendor=built,
                home_vendor=home,
                mode=self.mode,
            )
            if expected_reason is None or item.reason != expected_reason:
                raise ConsensusPanelError("an excluded candidate needs its structural reason")
            excluded_identifiers.append(item.candidate.seat_id)
        all_identifiers = identifiers + excluded_identifiers
        if len(all_identifiers) != len(set(all_identifiers)):
            raise ConsensusPanelError("reviewer seat identifiers must be unique across the roster")


def build_roster(
    candidates: Sequence[ReviewerCandidate],
    *,
    layer: str,
    built_vendor: str,
    home_vendor: str,
    mode: RosterMode = STANDARD_ROSTER,
    quorum: int,
) -> PanelRoster:
    """Apply the structural exclusions and retain the requested quorum unchanged."""
    if isinstance(candidates, str | bytes) or not isinstance(candidates, Sequence):
        raise ConsensusPanelError("candidates must be a sequence of ReviewerCandidate values")
    if mode not in {STANDARD_ROSTER, EXTERNAL_ONLY_ROSTER}:
        raise ConsensusPanelError(f"unknown roster mode {mode!r}")
    _require_quorum(quorum)
    built = _canonical_vendor(built_vendor)
    home = _canonical_vendor(home_vendor)
    seats: list[VotingSeat] = []
    excluded: list[ExcludedCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, ReviewerCandidate):
            raise ConsensusPanelError("candidates must be ReviewerCandidate values")
        if candidate.seat_id in seen:
            raise ConsensusPanelError(f"duplicate reviewer seat_id {candidate.seat_id!r}")
        seen.add(candidate.seat_id)
        seat, reason = _construct_voting_seat(
            candidate,
            built_vendor=built,
            home_vendor=home,
            mode=mode,
        )
        if seat is None:
            excluded.append(ExcludedCandidate(candidate=candidate, reason=reason))
        else:
            seats.append(seat)
    return PanelRoster(
        layer=layer,
        mode=mode,
        built_vendor=built,
        home_vendor=home,
        quorum=quorum,
        seats=tuple(seats),
        excluded=tuple(excluded),
    )


def _construct_voting_seat(
    candidate: ReviewerCandidate,
    *,
    built_vendor: str,
    home_vendor: str,
    mode: RosterMode,
) -> tuple[VotingSeat | None, str]:
    """The normal voting-seat construction site used by :func:`build_roster`."""
    reason = _eligibility_exclusion(
        candidate,
        built_vendor=built_vendor,
        home_vendor=home_vendor,
        mode=mode,
    )
    if reason is not None:
        return None, reason
    return (
        VotingSeat(
            seat_id=candidate.seat_id,
            vendor=candidate.vendor,
            lens=candidate.lens,
            _constructor=_SEAT_CONSTRUCTOR,
        ),
        "",
    )


def _eligibility_exclusion(
    candidate: ReviewerCandidate,
    *,
    built_vendor: str,
    home_vendor: str,
    mode: RosterMode,
) -> str | None:
    vendor = _canonical_vendor(candidate.vendor)
    if vendor == built_vendor:
        return "builder-vendor"
    if mode == EXTERNAL_ONLY_ROSTER and vendor == home_vendor:
        return "home-vendor-external-only"
    return None


@dataclass(frozen=True, slots=True)
class DimensionAssessment:
    """One reviewer's value for one dimension; exactly one instrument value is present."""

    dimension: str
    rank: str | None = None
    score: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "dimension",
            _require_non_empty(self.dimension, what="assessment dimension"),
        )
        if (self.rank is None) == (self.score is None):
            raise ConsensusPanelError("an assessment must carry exactly one of rank or score")
        if self.rank is not None and self.rank not in _RANK_ORDER:
            raise ConsensusPanelError(f"unknown gate rank {self.rank!r}; expected one of {RANKS}")
        if self.score is not None:
            _require_score(self.score, what=f"score for dimension {self.dimension!r}")

    @classmethod
    def gate(cls, dimension: str, rank: str) -> DimensionAssessment:
        return cls(dimension=dimension, rank=rank)

    @classmethod
    def score_value(cls, dimension: str, score: float) -> DimensionAssessment:
        return cls(dimension=dimension, score=score)


@dataclass(frozen=True, slots=True)
class ReviewerResponse:
    """A performed response from one constructed voting seat."""

    seat_id: str
    assessments: tuple[DimensionAssessment, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "seat_id",
            _require_non_empty(self.seat_id, what="response seat_id"),
        )
        collected = tuple(self.assessments)
        if not all(isinstance(item, DimensionAssessment) for item in collected):
            raise ConsensusPanelError("assessments must be DimensionAssessment values")
        names = [item.dimension for item in collected]
        if len(names) != len(set(names)):
            raise ConsensusPanelError("one response cannot repeat a dimension")
        object.__setattr__(self, "assessments", collected)

    @classmethod
    def of(
        cls,
        seat_id: str,
        assessments: Sequence[DimensionAssessment],
    ) -> ReviewerResponse:
        if isinstance(assessments, str | bytes) or not isinstance(assessments, Sequence):
            raise ConsensusPanelError("assessments must be a sequence")
        return cls(seat_id=seat_id, assessments=tuple(assessments))


@dataclass(frozen=True, slots=True)
class BlockingAssessment:
    """A gate rank that is at least as severe as that dimension's blocking rank."""

    seat_id: str
    dimension: str
    rank: str


@dataclass(frozen=True, slots=True)
class InvalidResponse:
    """A voting seat whose returned value could not be treated as a performed review."""

    seat_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class SeatScore:
    """One non-binding score paired with the seat that supplied it."""

    seat_id: str
    value: float


@dataclass(frozen=True, slots=True)
class PanelOutcome:
    """A panel decision plus non-binding score convergence."""

    decision: PanelDecision
    reason: str
    responded_seats: tuple[str, ...]
    missing_seats: tuple[str, ...]
    invalid_responses: tuple[InvalidResponse, ...]
    excluded_candidates: tuple[ExcludedCandidate, ...]
    blocking: tuple[BlockingAssessment, ...]
    scores: Mapping[str, tuple[SeatScore, ...]] = field(default_factory=dict)
    score_convergence: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scores", MappingProxyType(dict(self.scores)))
        object.__setattr__(
            self,
            "score_convergence",
            MappingProxyType(dict(self.score_convergence)),
        )


def evaluate_panel(
    configuration: PanelConfiguration,
    roster: PanelRoster,
    responses: Sequence[ReviewerResponse],
) -> PanelOutcome:
    """Apply asymmetric panel authority.

    A blocking gate rank halts immediately. Without one, the panel proceeds only when the roster
    can satisfy its original quorum and every constructed voting seat returned one value for every
    declared dimension. Score thresholds are recorded but never consulted for the decision.
    """
    configuration = _validated_configuration_snapshot(configuration)
    roster = _validated_roster_snapshot(roster)
    if configuration.layer != roster.layer:
        raise ConsensusPanelError(
            f"panel configuration layer {configuration.layer!r} does not match "
            f"roster layer {roster.layer!r}"
        )
    if isinstance(responses, str | bytes) or not isinstance(responses, Sequence):
        raise ConsensusPanelError("responses must be a sequence of ReviewerResponse values")
    response_values = tuple(responses)
    by_seat: dict[str, ReviewerResponse] = {}
    invalid_by_seat: dict[str, InvalidResponse] = {}
    received: set[str] = set()
    allowed = {seat.seat_id for seat in roster.seats}
    dimensions = {dimension.name: dimension for dimension in configuration.dimensions}
    for response in response_values:
        if type(response) is not ReviewerResponse:
            raise ConsensusPanelError("responses must be ReviewerResponse values")
        try:
            seat_id = _require_non_empty(response.seat_id, what="response seat_id")
        except (AttributeError, ConsensusPanelError) as exc:
            raise ConsensusPanelError("a response could not identify its voting seat") from exc
        if seat_id not in allowed:
            raise ConsensusPanelError(f"response from unknown voting seat {seat_id!r}")
        if seat_id in received:
            raise ConsensusPanelError(f"duplicate response from seat {seat_id!r}")
        received.add(seat_id)
        try:
            snapshot = _validated_response_snapshot(response)
            _validate_response_schema(snapshot, dimensions)
        except ConsensusPanelError as exc:
            invalid_by_seat[seat_id] = InvalidResponse(seat_id=seat_id, reason=str(exc))
            continue
        by_seat[seat_id] = snapshot

    blocking: list[BlockingAssessment] = []
    scores_by_seat: dict[str, dict[str, float]] = {
        name: {} for name, dimension in dimensions.items() if dimension.instrument == SCORE
    }
    seat_order = tuple(seat.seat_id for seat in roster.seats)
    for seat_id in seat_order:
        evaluated_response = by_seat.get(seat_id)
        if evaluated_response is None:
            continue
        assessments = {item.dimension: item for item in evaluated_response.assessments}
        for name, dimension in dimensions.items():
            assessment = assessments[name]
            if dimension.instrument == GATE:
                rank = assessment.rank
                blocking_rank = dimension.blocking_rank
                if rank is None or blocking_rank is None:
                    raise AssertionError("validated gate assessment is missing its rank")
                if _RANK_ORDER[rank] <= _RANK_ORDER[blocking_rank]:
                    blocking.append(
                        BlockingAssessment(
                            seat_id=seat_id,
                            dimension=name,
                            rank=rank,
                        )
                    )
            else:
                score = assessment.score
                if score is None:
                    raise AssertionError("validated score assessment is missing its value")
                scores_by_seat[name][seat_id] = score

    responded = tuple(seat_id for seat_id in seat_order if seat_id in by_seat)
    missing = tuple(seat_id for seat_id in seat_order if seat_id not in by_seat)
    invalid = tuple(
        invalid_by_seat[seat_id] for seat_id in seat_order if seat_id in invalid_by_seat
    )
    frozen_scores = {
        name: tuple(
            SeatScore(seat_id=seat_id, value=values[seat_id])
            for seat_id in seat_order
            if seat_id in values
        )
        for name, values in scores_by_seat.items()
    }
    convergence = {
        name: bool(roster.seats)
        and len(values) == len(roster.seats)
        and all(item.value >= _score_threshold(dimensions[name]) for item in values)
        for name, values in frozen_scores.items()
    }

    if blocking:
        return _outcome(
            PANEL_HALT,
            "blocking-gate",
            responded,
            missing,
            invalid,
            roster.excluded,
            blocking,
            frozen_scores,
            convergence,
        )
    if len(roster.seats) < roster.quorum or len(responded) < roster.quorum:
        return _outcome(
            PANEL_HALT,
            "quorum-lost",
            responded,
            missing,
            invalid,
            roster.excluded,
            blocking,
            frozen_scores,
            convergence,
        )
    if missing:
        return _outcome(
            PANEL_HALT,
            "voting-seat-missing",
            responded,
            missing,
            invalid,
            roster.excluded,
            blocking,
            frozen_scores,
            convergence,
        )
    return _outcome(
        PANEL_PROCEED,
        "all-voting-seats-clear",
        responded,
        missing,
        invalid,
        roster.excluded,
        blocking,
        frozen_scores,
        convergence,
    )


def _outcome(
    decision: PanelDecision,
    reason: str,
    responded: tuple[str, ...],
    missing: tuple[str, ...],
    invalid: tuple[InvalidResponse, ...],
    excluded: tuple[ExcludedCandidate, ...],
    blocking: Sequence[BlockingAssessment],
    scores: Mapping[str, tuple[SeatScore, ...]],
    convergence: Mapping[str, bool],
) -> PanelOutcome:
    return PanelOutcome(
        decision=decision,
        reason=reason,
        responded_seats=responded,
        missing_seats=missing,
        invalid_responses=invalid,
        excluded_candidates=excluded,
        blocking=tuple(blocking),
        scores=scores,
        score_convergence=convergence,
    )


def _validated_configuration_snapshot(configuration: object) -> PanelConfiguration:
    """Rebuild the policy declaration at the consequence boundary."""
    if type(configuration) is not PanelConfiguration:
        raise ConsensusPanelError("evaluate_panel requires an enabled PanelConfiguration")
    try:
        raw_dimensions = configuration.dimensions
        if type(raw_dimensions) is not tuple:
            raise ConsensusPanelError("panel dimensions must be held in an immutable tuple")
        dimensions: list[Dimension] = []
        for dimension in raw_dimensions:
            if type(dimension) is not Dimension:
                raise ConsensusPanelError("panel dimensions must be Dimension values")
            dimensions.append(
                Dimension(
                    name=dimension.name,
                    instrument=dimension.instrument,
                    threshold=dimension.threshold,
                    blocking_rank=dimension.blocking_rank,
                )
            )
        snapshot = PanelConfiguration(
            layer=configuration.layer,
            policy=configuration.policy,
            enabled=configuration.enabled,
            dimensions=tuple(dimensions),
        )
    except AttributeError as exc:
        raise ConsensusPanelError("panel configuration is incomplete") from exc
    if not snapshot.enabled:
        raise ConsensusPanelError("evaluate_panel requires an enabled PanelConfiguration")
    return snapshot


def _validated_roster_snapshot(roster: object) -> PanelRoster:
    """Rebuild roster eligibility and its immutable denominator before granting permission."""
    if type(roster) is not PanelRoster:
        raise ConsensusPanelError("evaluate_panel requires a PanelRoster")
    try:
        if type(roster.seats) is not tuple:
            raise ConsensusPanelError("voting seats must be held in an immutable tuple")
        if type(roster.excluded) is not tuple:
            raise ConsensusPanelError("excluded candidates must be held in an immutable tuple")
        built = _canonical_vendor(roster.built_vendor)
        home = _canonical_vendor(roster.home_vendor)
        rebuilt_seats: list[VotingSeat] = []
        for seat in roster.seats:
            if type(seat) is not VotingSeat:
                raise ConsensusPanelError("a roster may contain only VotingSeat values")
            candidate = ReviewerCandidate(
                seat_id=seat.seat_id,
                vendor=seat.vendor,
                lens=seat.lens,
            )
            rebuilt, reason = _construct_voting_seat(
                candidate,
                built_vendor=built,
                home_vendor=home,
                mode=roster.mode,
            )
            if rebuilt is None:
                raise ConsensusPanelError(
                    f"voting seat {candidate.seat_id!r} is structurally ineligible: {reason}"
                )
            rebuilt_seats.append(rebuilt)
        rebuilt_excluded: list[ExcludedCandidate] = []
        for item in roster.excluded:
            if type(item) is not ExcludedCandidate or type(item.candidate) is not ReviewerCandidate:
                raise ConsensusPanelError("excluded candidates must be ExcludedCandidate values")
            candidate = ReviewerCandidate(
                seat_id=item.candidate.seat_id,
                vendor=item.candidate.vendor,
                lens=item.candidate.lens,
            )
            rebuilt_excluded.append(ExcludedCandidate(candidate=candidate, reason=item.reason))
        return PanelRoster(
            layer=roster.layer,
            mode=roster.mode,
            built_vendor=built,
            home_vendor=home,
            quorum=roster.quorum,
            seats=tuple(rebuilt_seats),
            excluded=tuple(rebuilt_excluded),
        )
    except AttributeError as exc:
        raise ConsensusPanelError("panel roster is incomplete") from exc


def _validated_response_snapshot(response: ReviewerResponse) -> ReviewerResponse:
    """Rebuild one returned response so forged dataclass state cannot authorize work."""
    try:
        if type(response.assessments) is not tuple:
            raise ConsensusPanelError("response assessments must be held in an immutable tuple")
        assessments: list[DimensionAssessment] = []
        for item in response.assessments:
            if type(item) is not DimensionAssessment:
                raise ConsensusPanelError("assessments must be DimensionAssessment values")
            assessments.append(
                DimensionAssessment(
                    dimension=item.dimension,
                    rank=item.rank,
                    score=item.score,
                )
            )
        return ReviewerResponse(seat_id=response.seat_id, assessments=tuple(assessments))
    except AttributeError as exc:
        raise ConsensusPanelError("response is incomplete") from exc


def _validate_response_schema(
    response: ReviewerResponse,
    dimensions: Mapping[str, Dimension],
) -> None:
    assessments = {item.dimension: item for item in response.assessments}
    missing_dimensions = set(dimensions) - set(assessments)
    extra_dimensions = set(assessments) - set(dimensions)
    if missing_dimensions or extra_dimensions:
        raise ConsensusPanelError(
            f"response does not match the declared dimensions; "
            f"missing={sorted(missing_dimensions)}, extra={sorted(extra_dimensions)}"
        )
    for name, dimension in dimensions.items():
        assessment = assessments[name]
        if dimension.instrument == GATE and assessment.score is not None:
            raise ConsensusPanelError(f"gate dimension {name!r} refuses a numeric score")
        if dimension.instrument == SCORE and assessment.rank is not None:
            raise ConsensusPanelError(f"score dimension {name!r} refuses a rank")


def _score_threshold(dimension: Dimension) -> float:
    threshold = dimension.threshold
    if threshold is None:
        raise ConsensusPanelError(f"score dimension {dimension.name!r} needs a threshold")
    return threshold


def _canonical_vendor(vendor: str) -> str:
    return _require_non_empty(vendor, what="vendor").casefold()


def _require_non_empty(value: object, *, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConsensusPanelError(f"{what} must be a non-empty string")
    return value.strip()


def _require_score(value: object, *, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConsensusPanelError(f"{what} must be a number from 0 through 10")
    number = float(value)
    if not 0.0 <= number <= 10.0:
        raise ConsensusPanelError(f"{what} must be a number from 0 through 10")
    return number


def _require_quorum(quorum: object) -> int:
    if isinstance(quorum, bool) or not isinstance(quorum, int) or quorum <= 0:
        raise ConsensusPanelError("quorum must be a positive integer")
    return quorum
