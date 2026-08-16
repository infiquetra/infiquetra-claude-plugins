#!/usr/bin/env python3
"""The review loop bound: iteration cap, delta-scoped re-review, class dedup, three verdicts.

A review that stops only when reviewers go quiet does not stop. The artifact changes every
repair, so each iteration has a new surface, and a finding keyed by location always looks
novel. This module is the stopping rule.

What it owns
------------
* At most :data:`MAX_ITERATIONS` **completed iterations per unit, for the life of one
  :class:`ReviewLoop` instance in one process**. A pass does not reset the counter. A
  further iteration is refused, not warned about. Reconstructing the object resets the
  cap and the escalation budget. Spanning a process restart requires durable state this
  module does not have.
* What "the delta" means for a unit. Unchanged paths are omitted. A path whose text
  changed is represented by a unified diff against the previous text, with **no context
  lines**, so unchanged lines of a changed path are not re-presented. The whole artifact
  is not handed back. Paths are compared exactly; this module does not normalize them.
* Recurrence of a *declared* defect class across iterations. The class is a field the
  reviewer set. Unit ids and defect classes are stored in one canonical form each
  (outer whitespace stripped) so two spellings of the same identifier cannot split
  the bound. Seen classes are never forgotten for that unit. This module has no
  summary field to infer a class from.
* Open classes require an authored disposition to pass. Silence — an empty report, or
  a delta that no longer contains the defective path — is not a fix.
  :meth:`ReviewReport.of` takes ``disposes``. Only ``pass`` needs it.
* Three verdicts: ``pass``, ``halt-and-repair``, ``halt-and-escalate``. A verdict is
  emitted only from a :class:`ReviewReport` or from :meth:`ReviewLoop.conclude_unperformed`.
  A bare sequence is not a report. An unperformed review is recorded separately and
  does not consume the iteration. :data:`MAX_UNPERFORMED` consecutive unperformed
  records on one open iteration are refused. An iteration that carries unperformed
  records cannot pass. :meth:`ReviewLoop.conclude_unperformed` is the exit when there
  is no review result; it never returns ``pass``.
* Mechanical escalation: the last allowed iteration concluding with any declared
  class still open, any undisposed class, or any unperformed record yields
  ``halt-and-escalate``. Recurrence is one sufficient trigger; it is not the only one.
  There is no remaining iteration in which to repair, so that verdict is never
  ``halt-and-repair``. Rank is not read. The unit is then **terminal**: no later call
  returns a verdict.
* An escalation budget of :data:`ESCALATION_BUDGET` per unit. The comparison that
  enforces it reads this name. No function here accepts a parameter that replaces it.
  At the shipped value of 1, a second escalation is prevented by terminality, not by
  the budget: raising the constant would not buy another escalation.

What it does not own
--------------------
The consensus panel — multiple reviewers, per-lens scoring, quorum, vendor exclusion — is a
separate module. This one takes findings the caller already has. There is no hook for a
panel, because a hook would force every layer that needs a bound to carry panel machinery
it does not use.
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

MAX_ITERATIONS = 3
ESCALATION_BUDGET = 1
MAX_UNPERFORMED = 3

VerdictKind = Literal["pass", "halt-and-repair", "halt-and-escalate"]
VERDICT_PASS: VerdictKind = "pass"
VERDICT_HALT_AND_REPAIR: VerdictKind = "halt-and-repair"
VERDICT_HALT_AND_ESCALATE: VerdictKind = "halt-and-escalate"
VERDICTS: frozenset[str] = frozenset(
    {VERDICT_PASS, VERDICT_HALT_AND_REPAIR, VERDICT_HALT_AND_ESCALATE}
)


class ReviewLoopError(Exception):
    """The review loop refused the request."""


class IterationBoundError(ReviewLoopError):
    """A unit already used its iteration cap."""


class EscalationBudgetError(ReviewLoopError):
    """A unit already used its one escalation."""


class UnitTerminalError(ReviewLoopError):
    """A unit has escalated and will not emit another verdict."""


class UnperformedBoundError(ReviewLoopError):
    """An open iteration already recorded its unperformed-review cap."""


@dataclass(frozen=True)
class Artifact:
    """A review surface keyed by path.

    Keys are compared exactly. This module does not normalize paths.
    """

    parts: tuple[tuple[str, str], ...]

    @classmethod
    def from_mapping(cls, parts: Mapping[str, str]) -> Artifact:
        if not isinstance(parts, Mapping):
            raise ReviewLoopError("artifact parts must be a mapping of path to text")
        normalized: list[tuple[str, str]] = []
        for path, text in parts.items():
            if not isinstance(path, str) or not path:
                raise ReviewLoopError("every artifact path must be a non-empty string")
            if not isinstance(text, str):
                raise ReviewLoopError(f"artifact text for {path!r} must be a string")
            normalized.append((path, text))
        return cls(tuple(sorted(normalized)))

    def mapping(self) -> dict[str, str]:
        return dict(self.parts)


@dataclass(frozen=True)
class Finding:
    """One reviewer finding. The class is declared, never inferred."""

    defect_class: str
    rank: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "defect_class", _canonical_defect_class(self.defect_class))
        if not isinstance(self.rank, str):
            raise ReviewLoopError("a finding rank must be a string")


@dataclass(frozen=True)
class ReviewReport:
    """A review that was performed. The type itself is that fact.

    Construct with :meth:`of`. A list or tuple is not a :class:`ReviewReport`.
    ``disposes`` is the authored claim that named classes are resolved. It is
    required to ``pass`` while earlier classes remain open. It is not inferred
    from an empty findings list.
    """

    findings: tuple[Finding, ...]
    disposes: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if isinstance(self.disposes, str | bytes) or not isinstance(self.disposes, Iterable):
            raise ReviewLoopError("disposes must be a collection of class names")
        object.__setattr__(
            self,
            "disposes",
            frozenset(_canonical_defect_class(name) for name in self.disposes),
        )
        raised = {finding.defect_class for finding in self.findings}
        overlap = raised & self.disposes
        if overlap:
            raise ReviewLoopError(
                "a report cannot dispose and re-raise " + ", ".join(sorted(overlap))
            )

    @classmethod
    def of(
        cls,
        findings: Sequence[Finding],
        *,
        disposes: Iterable[str] = (),
    ) -> ReviewReport:
        if isinstance(findings, str | bytes) or not isinstance(findings, Sequence):
            raise ReviewLoopError("ReviewReport.of requires a sequence of Finding values")
        if isinstance(disposes, str | bytes):
            raise ReviewLoopError("disposes must be a collection of class names")
        collected: list[Finding] = []
        for finding in findings:
            if not isinstance(finding, Finding):
                raise ReviewLoopError("findings must be Finding values")
            collected.append(finding)
        return cls(tuple(collected), frozenset(disposes))


@dataclass(frozen=True)
class ReviewScope:
    """What one iteration is allowed to look at."""

    unit_id: str
    iteration: int
    surface: Artifact
    scoped_to_delta: bool


@dataclass(frozen=True)
class Verdict:
    """The loop's decision after one performed review or an unperformed exit."""

    kind: VerdictKind
    iteration: int
    recurring_classes: frozenset[str]


@dataclass
class _UnitState:
    completed_iterations: int = 0
    open: bool = False
    pending_iteration: int = 0
    last_artifact: Artifact | None = None
    seen_classes: set[str] = field(default_factory=set)
    open_classes: set[str] = field(default_factory=set)
    escalated_classes: set[str] = field(default_factory=set)
    escalations: int = 0
    unperformed: int = 0
    terminal: bool = False
    last_verdict: str | None = None


def delta_of(previous: Artifact, current: Artifact) -> Artifact:
    """The change since ``previous``: diffs for paths that changed, nothing for the rest.

    Unchanged paths are omitted. Added, removed, and edited paths appear as unified
    diffs against the previous text (the empty string when the path was absent),
    with no context lines.
    """
    if not isinstance(previous, Artifact) or not isinstance(current, Artifact):
        raise ReviewLoopError("delta_of requires Artifact values")
    before = previous.mapping()
    after = current.mapping()
    parts: dict[str, str] = {}
    for path in sorted(set(before) | set(after)):
        old = before.get(path, "")
        new = after.get(path, "")
        if old == new:
            continue
        parts[path] = _unified_diff(old, new)
    return Artifact.from_mapping(parts)


def _unified_diff(before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="previous",
            tofile="current",
            n=0,
        )
    )


def _canonical_unit_id(unit_id: str) -> str:
    if not isinstance(unit_id, str):
        raise ReviewLoopError("unit_id must be a non-empty string")
    canonical = unit_id.strip()
    if not canonical:
        raise ReviewLoopError("unit_id must be a non-empty string")
    return canonical


def _canonical_defect_class(name: object) -> str:
    if not isinstance(name, str):
        raise ReviewLoopError("a finding must declare a defect class")
    canonical = name.strip()
    if not canonical:
        raise ReviewLoopError("a finding must declare a defect class")
    return canonical


def _declared_classes(findings: Sequence[Finding]) -> frozenset[str]:
    classes: set[str] = set()
    for finding in findings:
        if not isinstance(finding, Finding):
            raise ReviewLoopError("findings must be Finding values")
        classes.add(_canonical_defect_class(finding.defect_class))
    return frozenset(classes)


def _close_terminal(state: _UnitState) -> None:
    state.open = False
    state.pending_iteration = 0
    state.terminal = True


def _spend_escalation(state: _UnitState, unit: str, classes: set[str]) -> None:
    if state.escalations >= ESCALATION_BUDGET:
        _close_terminal(state)
        raise EscalationBudgetError(
            f"unit {unit!r} already used its {ESCALATION_BUDGET} escalation; "
            "a further escalation is refused"
        )
    state.escalations += 1
    state.escalated_classes |= classes


class ReviewLoop:
    """In-memory bound on review iterations for one or more units.

    The bound is the lifetime of this object. It is not durable across process
    restart.
    """

    def __init__(self) -> None:
        self._units: dict[str, _UnitState] = {}

    def begin_iteration(self, unit_id: str, artifact: Artifact) -> ReviewScope:
        """Open the next iteration, or refuse if the unit is already at the cap."""
        unit = _canonical_unit_id(unit_id)
        if not isinstance(artifact, Artifact):
            raise ReviewLoopError("artifact must be an Artifact")
        state = self._units.setdefault(unit, _UnitState())
        if state.terminal:
            raise UnitTerminalError(f"unit {unit!r} has spent its escalation and is closed")
        if state.open:
            raise ReviewLoopError(f"unit {unit!r} still has an open iteration")
        next_iteration = state.completed_iterations + 1
        if next_iteration > MAX_ITERATIONS:
            raise IterationBoundError(
                f"unit {unit!r} already used {MAX_ITERATIONS} iterations; "
                "a further iteration is refused"
            )
        if next_iteration == 1:
            surface = artifact
            scoped_to_delta = False
        else:
            if state.last_artifact is None:
                raise ReviewLoopError(f"unit {unit!r} has no previous artifact to difference")
            surface = delta_of(state.last_artifact, artifact)
            scoped_to_delta = True
        state.open = True
        state.pending_iteration = next_iteration
        state.last_artifact = artifact
        state.unperformed = 0
        return ReviewScope(
            unit_id=unit,
            iteration=next_iteration,
            surface=surface,
            scoped_to_delta=scoped_to_delta,
        )

    def record_unperformed(self, unit_id: str) -> None:
        """Record that the review did not happen.

        Emits no verdict. Does not consume the iteration. A later
        :meth:`conclude_iteration` on the same open iteration is still the same
        numbered iteration. :data:`MAX_UNPERFORMED` consecutive records on this
        open iteration are refused. :meth:`conclude_unperformed` is the exit
        when there is no review result.
        """
        unit = _canonical_unit_id(unit_id)
        state = self._units.get(unit)
        if state is not None and state.terminal:
            raise UnitTerminalError(f"unit {unit!r} has spent its escalation and is closed")
        if state is None or not state.open:
            raise ReviewLoopError(f"unit {unit!r} has no open iteration")
        if state.unperformed >= MAX_UNPERFORMED:
            raise UnperformedBoundError(
                f"unit {unit!r} already recorded {MAX_UNPERFORMED} unperformed "
                "reviews on this iteration; a further unperformed review is refused"
            )
        state.unperformed += 1

    def conclude_unperformed(self, unit_id: str) -> Verdict:
        """End the open iteration without a review result. Never returns ``pass``."""
        unit = _canonical_unit_id(unit_id)
        state = self._units.get(unit)
        if state is not None and state.terminal:
            raise UnitTerminalError(f"unit {unit!r} has spent its escalation and is closed")
        if state is None or not state.open:
            raise ReviewLoopError(f"unit {unit!r} has no open iteration")
        if state.unperformed < 1:
            raise ReviewLoopError(
                f"unit {unit!r} has no unperformed review to conclude; "
                "record_unperformed first or submit a ReviewReport"
            )
        iteration = state.pending_iteration
        if iteration == MAX_ITERATIONS:
            _spend_escalation(state, unit, set(state.open_classes))
            kind: VerdictKind = VERDICT_HALT_AND_ESCALATE
        else:
            kind = VERDICT_HALT_AND_REPAIR
        return self._close(state, kind, iteration, frozenset())

    def conclude_iteration(self, unit_id: str, report: ReviewReport) -> Verdict:
        """Close the open iteration and emit one of the three verdicts.

        ``report`` must be a :class:`ReviewReport`. A sequence is not accepted.
        ``pass`` requires every previously open class to be named in
        ``report.disposes`` and requires this iteration to carry no unperformed
        records.
        """
        unit = _canonical_unit_id(unit_id)
        state = self._units.get(unit)
        if state is not None and state.terminal:
            raise UnitTerminalError(f"unit {unit!r} has spent its escalation and is closed")
        if state is None or not state.open:
            raise ReviewLoopError(f"unit {unit!r} has no open iteration")
        if not isinstance(report, ReviewReport):
            raise ReviewLoopError(
                "conclude_iteration requires a ReviewReport; "
                "a sequence is not evidence that a review was performed"
            )
        iteration = state.pending_iteration
        classes = _declared_classes(report.findings)
        disposed = report.disposes
        unknown = disposed - state.open_classes
        if unknown:
            raise ReviewLoopError(
                "cannot dispose " + ", ".join(sorted(unknown)) + ": not an open class"
            )
        remaining_open = (state.open_classes - disposed) | classes
        recurring = classes & state.seen_classes
        unfinished = bool(classes or remaining_open or state.unperformed)
        if iteration == MAX_ITERATIONS and unfinished:
            _spend_escalation(state, unit, remaining_open or set(classes))
            kind: VerdictKind = VERDICT_HALT_AND_ESCALATE
        elif classes:
            kind = VERDICT_HALT_AND_REPAIR
        elif remaining_open:
            raise ReviewLoopError(
                "pass requires explicit disposal of open classes: "
                + ", ".join(sorted(remaining_open))
            )
        elif state.unperformed:
            kind = VERDICT_HALT_AND_REPAIR
        else:
            kind = VERDICT_PASS
        state.open_classes = remaining_open
        state.seen_classes |= classes
        return self._close(state, kind, iteration, frozenset(recurring))

    def _close(
        self,
        state: _UnitState,
        kind: VerdictKind,
        iteration: int,
        recurring: frozenset[str],
    ) -> Verdict:
        state.completed_iterations = iteration
        state.open = False
        state.pending_iteration = 0
        state.last_verdict = kind
        if kind == VERDICT_HALT_AND_ESCALATE:
            state.terminal = True
        return Verdict(kind=kind, iteration=iteration, recurring_classes=recurring)
