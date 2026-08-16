#!/usr/bin/env python3
"""The orchestration control flow: seven modules assembled into one supervised run.

Every other script here owns one mechanism and deliberately stops at its boundary. This module
is the only caller that sees two of them at once, so it owns every property that lives *between*
them:

- **Order.** ``activate_slot`` immediately before ``launch_child``; ``release_slot`` only after a
  verified completion has been recorded reaped; the run root recorded before the first launch;
  the presentation receipt created only after the rendered text reached the operator channel.
- **Custody.** The vendor, model, effort, scope and integration target the operator approved are
  the ones that reach the launcher. A resolver that would substitute is refused, not adapted to.
- **Authorisation.** ``phase="verified"`` is a claim. Reaping is authorised by an authenticated
  dispatch receipt, a settlement sealed under the same attempt, a recorded passing verdict, and
  the artifact on disk still carrying this dispatch's binding token.
- **Recovery.** Reservations belong to a coordinator, not to a clock. Startup names the occupied
  identities and takes an explicit abandon-or-resume decision for each one.
- **The channel.** An operator message is answered or explicitly parked, with a durable receipt,
  whether or not the mirror is busy. Nothing on the operator path reads the mirror's pane.

What this module does *not* do is decide anything a module already decides. It does not
re-implement the queue, re-derive a route, re-run a predicate, or interpret an agent's reported
status. Where a decision exists somewhere else, this calls it and honours the answer.

Two facts worth knowing before changing anything here:

**A shared fact needs one named owner and the name has to be enforced.** Every register write
this module performs goes through :func:`_write_owned`, which refuses any column outside
``OWNED_COLUMNS`` at runtime. Three columns are owned here and they are here because the
composition seam is the only place that can produce them.

**A green suite is the thing to distrust.** The reason this module exists is that seven passing
module suites can coexist with no working orchestrator. The tests that matter are the ones that
traverse the assembled path and the ones that inject a fault a removal proof cannot reach.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess  # nosec B404 - the subscriber is a first-party script, argv is built here
import sys
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

import accounting
import admission
import completion
import fleet_commons_shim
import herdr_events
import mirror as mirror_module
import planning
import register as register_store
import session_lifecycle
import subscriber as subscriber_module

tier_resolver = fleet_commons_shim.load("tier_resolver")

SUBSCRIBER_SCRIPT = Path(__file__).with_name("subscriber.py")

# ---------------------------------------------------------------------------- vocabulary

#: Event types this module refuses to subscribe to. Each carries no lifecycle state, so each
#: produces a wake with nothing new to read; a broad one produces a wake storm.
NON_STATE_SUBSCRIPTIONS = frozenset(
    {
        "pane.updated",
        "pane.focused",
        "pane.moved",
        "pane.scroll_changed",
        "pane.created",
        "layout.updated",
        "tab.focused",
        "tab.moved",
        "tab.renamed",
        "workspace.focused",
        "workspace.updated",
    }
)

#: Lifecycle subscriptions every run installs regardless of which panes exist.
RUN_SUBSCRIPTIONS: tuple[dict[str, Any], ...] = ({"type": "pane.exited"}, {"type": "tab.closed"})

#: The integration modes this control flow can actually land, which is not the whole planning
#: vocabulary. ``GitLanding.provision`` decides from ``spec.mutating`` alone: a mutating child gets
#: a branch worktree, a read-only child stays in the ambient checkout. There is no producer for a
#: declared destination path, and a plan cannot name one -- ``PlannedChild`` carries no destination
#: field. Supporting that mode means adding a destination to the planning contract *and* a landing
#: that provisions it, both outside this unit. Until then an approved mode outside this set is
#: refused rather than adapted into the nearest one that can be produced.
PRODUCIBLE_INTEGRATION_MODES = frozenset({"none", "branch"})

#: Admission statuses that mean "this row holds a slot". ``held`` is one of them: marking a
#: reservation active is what this control flow does immediately before handing a row to the
#: launcher, so a row left ``held`` by a launch that did not finish still holds a matching
#: reservation and must be able to reach the launcher again. Refusing it there is how a single
#: wrapper error turns into a lost child and a leaked slot. What stops a *second* coordinator
#: from launching it is the dispatch claim, not the admission status.
HOLDING_ADMISSION_STATUSES = frozenset({"reserved", "held"})


def producible_landing_mode(approved_mode: str) -> str:
    """The mode ``GitLanding.provision`` will actually produce for an approved mode.

    Derived from the provisioner's own rule rather than restated as a table, so the two cannot
    drift: mutating is every mode except ``none``, and every mutating child gets a branch.
    """
    return "none" if approved_mode == "none" else "branch"


PHASE_INDEX = {phase: index for index, phase in enumerate(register_store.PHASES)}

COMPLETION_PURPOSE = "completion"

#: The four accepted forms of ``/orchestrate <outcome>`` (R1).
OUTCOME_KINDS = ("issue", "parent_issue", "document", "prose")

# Composition's own columns. Writer is this module's single seam; the fact is what the write
# asserts. Nothing outside this list may be written from here, and the merger refuses the
# columns other modules own regardless.
OWNED_COLUMNS = (
    "completion_sentinel",
    "changed_paths_baseline",
    "post_verdict_observation",
    "coordinator_disposition",
    "dispatch_claim",
    "reap_fence",
    "artifact_protocol_sent",
)
COLUMN_OWNERSHIP: tuple[tuple[str, str, str], ...] = (
    (
        "completion_sentinel",
        "runner._write_owned",
        "this pane will print this marker when its deliverable is written; the subscription "
        "list is rebuilt from it after a restart",
    ),
    (
        "changed_paths_baseline",
        "runner._write_owned",
        "the repository snapshot the dispatch receipt was sealed against; a restarted "
        "coordinator cannot re-take it, and the receipt's digest proves it was not edited",
    ),
    (
        "post_verdict_observation",
        "runner._write_owned",
        "what the child's landing looked like at the instant its verdict was taken; a change "
        "between that instant and the reap means the child had not stopped",
    ),
    (
        "coordinator_disposition",
        "runner._write_owned",
        "this coordinator deliberately stopped pursuing this row, and why; a child that was "
        "abandoned on purpose is not a child that was lost",
    ),
    (
        "dispatch_claim",
        "runner._write_owned_unlocked",
        "one named coordinator, in one register generation, owns this row's dispatch; no other "
        "coordinator may hand it to the launcher",
    ),
    (
        "reap_fence",
        "runner._write_owned",
        "the producer was deliberately stopped at this instant so its evidence could be observed "
        "with nothing able to change it; a closed tab beside this record was not a crash",
    ),
    (
        "artifact_protocol_sent",
        "runner._write_owned",
        "the run-binding instructions actually reached this pane; a row with a pane and no "
        "record of this has a live, paid session that was never told where to write",
    ),
)


# ---------------------------------------------------------------------------- errors


class CompositionError(RuntimeError):
    """The assembled control flow refused to proceed."""


class ColumnOwnershipError(CompositionError):
    """This module attempted a register column it does not own."""


class PhaseOrderError(CompositionError):
    """A transition would move a row backwards through the lifecycle, or out of a terminal step."""


class RouteDivergedError(CompositionError):
    """The route about to run is not the route the operator approved."""


class AdmissionOrderError(CompositionError):
    """A row reached a launch or release step out of the admission sequence."""


class UnsupportedWorkShapeError(CompositionError):
    """The plan declares work this control flow has no path to carry out."""


class DispatchClaimError(CompositionError):
    """Another coordinator holds the durable claim on this row's dispatch."""


class UnconfirmedDispatchError(CompositionError):
    """A live pane's readiness was never confirmed, so no automatic recovery is safe.

    A row can reach this only before its completion sentinel was ever recorded -- readiness (a
    trust prompt, a timeout, an effort-application failure) never completed, so there is no
    idempotent identity this coordinator could use to resend anything without risking a second,
    contradictory instruction to a pane whose actual state it cannot see. It is offered by
    :meth:`Coordinator.interrupted_dispatches` and can be abandoned; it cannot be resumed
    automatically.
    """


class AcceptanceOrderError(CompositionError):
    """The acceptance receipt was asked for when the evidence it checks no longer exists."""


class SpendHaltError(CompositionError):
    """No further child may start under the approved ceiling."""


class SpendCeilingError(SpendHaltError):
    """The approved ceiling is met or exceeded."""


class SpendUnobservableError(SpendHaltError):
    """A launched metered child has reported no usage, so the run's spend is not yet knowable."""


class ApprovalError(CompositionError):
    """The plan about to run is not the plan the operator was shown and approved."""


class ReapAuthorizationError(CompositionError):
    """Nothing authenticated authorises closing this child."""


class ChildStillMutatingError(CompositionError):
    """The landing changed between the recorded verdict and the reap."""


class ArtifactAssignmentError(CompositionError):
    """Two children of this run would produce into one artifact location."""


class ConcurrentAttemptError(CompositionError):
    """A second dispatch was requested for a row whose current attempt is still open."""


class SubscriptionSetError(CompositionError):
    """The subscription list the subscriber would be started with is wrong."""


class SubscriberLivenessUnknownError(CompositionError):
    """Whether this run's subscriber is alive could not be established, by any source asked.

    The durable record answered "none recorded", or named a process id whose own identity could
    not be confirmed, and the process table -- the only independent source either question can be
    settled from -- could not be queried at all. That is not the same fact as "queried, and none
    found" or "queried, and it is not ours": both of those are established absences, safe to act
    on. A query that never completed has established nothing, and every caller that decides
    whether to start a second writer, adopt one, or archive this run must not read it as one.
    See :class:`SpendUnobservableError` for the same shape applied to a run's spend.
    """


class RetirementOrderError(CompositionError):
    """A writer or a reservation is still open, so the run cannot be retired."""


class OutcomeArgumentError(CompositionError):
    """The outcome argument is not one of the four accepted forms."""


class ParkQuestionError(CompositionError):
    """Raised by a handler to park a question with a reason instead of answering it."""


# ---------------------------------------------------------------------------- owned writes


def _assert_owned(fields: Mapping[str, Any]) -> None:
    foreign = sorted(set(fields) - set(OWNED_COLUMNS))
    if foreign:
        raise ColumnOwnershipError(
            f"the composition module does not own {foreign}; it writes only {list(OWNED_COLUMNS)}"
        )


def _write_owned(
    root: Path, row_id: str, fields: Mapping[str, Any], *, run_id: str
) -> dict[str, Any]:
    """The single register-write seam for this module, refusing any column it does not own.

    A docstring declaring single ownership was violated by the very next unit that touched the
    register, so this asserts at runtime instead of describing.
    """
    _assert_owned(fields)
    return register_store.upsert_row(root, row_id, dict(fields), run_id=run_id)


def _write_owned_unlocked(
    claimed: Path, row_id: str, fields: Mapping[str, Any], *, run_id: str
) -> dict[str, Any]:
    """The same seam for a caller that already holds this run's generation lock.

    The lock is not reentrant, so a read-check-write that has to be atomic cannot go through the
    public write. This exists so that transaction is still one seam rather than a second writer.
    """
    _assert_owned(fields)
    return register_store._upsert_rows_unlocked(claimed, {row_id: dict(fields)}, run_id=run_id)[
        row_id
    ]


# ---------------------------------------------------------------------------- lifecycle order


@dataclass(frozen=True)
class DispatchClaim:
    """Durable ownership of one row's dispatch, held by one coordinator in one generation.

    This exists because every other guard against launching a child twice reads state and then
    acts on it. Two coordinators can both pass every read before either acts: the in-memory
    dispatch set is local to one Python object, and marking a reservation active accepts a
    reservation that is already active, so it is not a compare-and-set on *dispatch*. The claim
    is: it is taken under this run's generation lock, in the same transaction as the launchability
    re-read, and a coordinator that does not hold it never reaches the launcher.

    ``pid`` is recorded as *evidence for a human*, never as a decision. A dead process is not
    authority to take a claim -- recovery here is by an explicit ownership decision, the same rule
    that governs another run's abandoned reservations -- but an operator deciding whether to
    resume or abandon should be told whether the claimant is still running.
    """

    coordinator_id: str
    pid: int
    generation: str
    attempts: int
    claimed_at: float

    def to_mapping(self) -> dict[str, Any]:
        return {
            "coordinator_id": self.coordinator_id,
            "pid": self.pid,
            "generation": self.generation,
            "attempts": self.attempts,
            "claimed_at": self.claimed_at,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DispatchClaim:
        return cls(
            coordinator_id=str(value.get("coordinator_id") or ""),
            pid=int(value.get("pid") or 0),
            generation=str(value.get("generation") or ""),
            attempts=int(value.get("attempts") or 0),
            claimed_at=float(value.get("claimed_at") or 0.0),
        )


def process_is_running(pid: int) -> bool:
    """Whether a process with this id exists. Evidence for an operator, not a decision.

    An unknown answer is reported as running, because "I could not tell" must not read as "it is
    safe to take this over".
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_exit(pid: int, *, timeout: float, poll_interval: float = 0.05) -> bool:
    """Poll until ``pid`` is gone or ``timeout`` elapses. Returns whether it is gone."""
    deadline = time.monotonic() + timeout
    while process_is_running(pid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_interval)
    return True


def claim_of(row: Mapping[str, Any]) -> DispatchClaim | None:
    stored = row.get("dispatch_claim")
    return DispatchClaim.from_mapping(stored) if isinstance(stored, Mapping) else None


def is_abandoned(row: Mapping[str, Any]) -> bool:
    """Whether this coordinator deliberately stopped pursuing this row."""
    disposition = row.get("coordinator_disposition")
    return isinstance(disposition, Mapping) and disposition.get("state") == "abandoned"


def _producer_confirmed_stopped(row: Mapping[str, Any]) -> bool:
    """Whether abandoning this row also established that nothing is still running for it.

    "No longer awaited" and "the producer stopped" are two different facts (:meth:`abandon_child`
    proves the second, it does not assume it from the first), and only the second one licenses
    excluding a row from spend or from :meth:`Coordinator.outstanding_writers`. A row abandoned
    without that proof is still, for every purpose this predicate gates, exactly as unresolved as
    a row nobody has decided anything about yet.
    """
    disposition = row.get("coordinator_disposition")
    return isinstance(disposition, Mapping) and disposition.get("producer_stopped") is True


def is_terminal(phase: Any) -> bool:
    return phase in register_store.TERMINAL_PHASES


def assert_forward_transition(current: Any, target: str, *, row_id: str) -> None:
    """Permit only the declared forward phase sequence, and never leave a terminal step.

    The register refuses ``planned`` written over a terminal row. It does not refuse
    ``working`` written over ``verified``, or ``launching`` written over ``working`` -- the
    ordering is not knowable to a passive state store, which is why it is checked here, at the
    only place that knows which operation is being attempted next.
    """
    if target not in PHASE_INDEX:
        raise PhaseOrderError(f"{target!r} is not one of {register_store.PHASES}")
    if current is None:
        return
    if current not in PHASE_INDEX:
        raise PhaseOrderError(f"row {row_id!r} carries unknown phase {current!r}")
    if current == "reaped" and target != "reaped":
        raise PhaseOrderError(
            f"row {row_id!r} is reaped; a terminal row is never moved back into runnable work"
        )
    if PHASE_INDEX[target] < PHASE_INDEX[current]:
        raise PhaseOrderError(
            f"row {row_id!r} is {current!r} and this step would move it to {target!r}; "
            "the lifecycle runs forward only"
        )


# ---------------------------------------------------------------------------- R1 argument forms


@dataclass(frozen=True)
class OutcomeRequest:
    """One ``/orchestrate <outcome>`` argument, resolved into text a plan can be built from."""

    kind: str
    argument: str
    outcome: str
    source: dict[str, Any]


class IssueReader(Protocol):
    """Whatever can turn an issue reference into a title, a body, and its children."""

    def read_issue(self, reference: str) -> Mapping[str, Any]: ...


def _issue_reference(argument: str) -> str | None:
    """``123``, ``#123`` and ``owner/repo#123`` are issue references; nothing else is."""
    text = argument.strip()
    if not text or "\n" in text:
        return None
    body = text
    if "#" in text:
        prefix, _, number = text.partition("#")
        if not number.isdigit():
            return None
        if prefix and (prefix.count("/") != 1 or not all(prefix.split("/"))):
            return None
        return text
    return text if body.isdigit() else None


def parse_outcome(
    argument: str,
    *,
    issue_reader: IssueReader | None = None,
    root: Path | None = None,
) -> OutcomeRequest:
    """Resolve one outcome argument into planning input (R1).

    Nothing is decomposed before invocation: a bare issue number, an issue that turns out to
    have children, a path to a requirements document, and a prose prompt each arrive here and
    each leave as an ``OutcomeRequest`` a plan can be built from. Reading an issue is injected,
    because this module never reaches a network and a document is read from disk.
    """
    if not isinstance(argument, str) or not argument.strip():
        raise OutcomeArgumentError("an outcome argument must be non-empty text")
    reference = _issue_reference(argument)
    if reference is not None:
        if issue_reader is None:
            raise OutcomeArgumentError(
                f"{argument!r} names issue {reference} and no issue reader was supplied; "
                "this module never reaches a network by itself"
            )
        issue = issue_reader.read_issue(reference)
        title = str(issue.get("title") or "").strip()
        body = str(issue.get("body") or "").strip()
        children = [str(item) for item in issue.get("children") or []]
        kind = "parent_issue" if children else "issue"
        lines = [f"{reference}: {title}" if title else reference]
        if body:
            lines.append(body)
        if children:
            lines.append("Sub-issues: " + ", ".join(children))
        return OutcomeRequest(
            kind=kind,
            argument=argument,
            outcome="\n\n".join(lines),
            source={"reference": reference, "title": title, "children": children},
        )

    candidate = Path(argument).expanduser()
    if not candidate.is_absolute() and root is not None:
        candidate = root / candidate
    if "\n" not in argument and candidate.is_file():
        text = candidate.read_text(encoding="utf-8")
        return OutcomeRequest(
            kind="document",
            argument=argument,
            outcome=text,
            source={"path": str(candidate), "bytes": len(text.encode("utf-8"))},
        )

    return OutcomeRequest(
        kind="prose",
        argument=argument,
        outcome=argument.strip(),
        source={"bytes": len(argument.encode("utf-8"))},
    )


# ---------------------------------------------------------------------------- approved plan


def artifact_relpath(run_id: str, row_id: str, artifact_path: str) -> str:
    """Where one attempt's deliverable settles, relative to that child's landing.

    Derived from :func:`completion.artifact_landing` rather than restated, so the two cannot
    drift. It is knowable before the landing exists, which is what lets a plan declare a
    predicate naming the settled path -- the predicate is written before anything is provisioned,
    and a predicate that names the wrong path fails at issue rather than at evaluation.
    """
    base = completion.artifact_landing(Path("."), run_id, row_id)
    return (PurePosixPath(base.as_posix()) / PurePosixPath(artifact_path).name).as_posix()


def approved_plan_path(run_id: str) -> Path:
    """Where the approved plan is kept.

    Deliberately not ``*.json``: ``iter_live_run_ids`` treats every json file beside the live
    registers as a run document.
    """
    safe = register_store._safe_run_id(run_id)
    return register_store.register_dir() / f"{safe}.approved-plan"


def _child_to_mapping(child: planning.PlannedChild) -> dict[str, Any]:
    return {
        "row_id": child.row_id,
        "task": child.task,
        "work_shape": child.work_shape,
        "execution_class": child.execution_class,
        "vendor": child.vendor,
        "model": child.model,
        "effort": child.effort,
        "scope": list(child.scope),
        "artifact_path": child.artifact_path,
        "predicate": dict(child.predicate),
        "integration_mode": child.integration_mode,
        "tokens_reserved": child.tokens_reserved,
        "tokens_max": child.tokens_max,
        "substitutions": [dict(item) for item in child.substitutions],
        "override": dict(child.override) if child.override else None,
        "policy_model": child.policy_model,
        "policy_effort": child.policy_effort,
        "fallbacks": [dict(item) for item in child.fallbacks],
        "workspace_boundary": child.workspace_boundary,
        "admission": child.admission,
        "admission_reason": child.admission_reason,
    }


def _child_from_mapping(value: Mapping[str, Any]) -> planning.PlannedChild:
    return planning.PlannedChild(
        row_id=str(value["row_id"]),
        task=str(value["task"]),
        work_shape=str(value["work_shape"]),
        execution_class=str(value["execution_class"]),
        vendor=str(value["vendor"]),
        model=str(value["model"]),
        effort=str(value["effort"]),
        scope=tuple(str(item) for item in value["scope"]),
        artifact_path=str(value["artifact_path"]),
        predicate=dict(value["predicate"]),
        integration_mode=str(value["integration_mode"]),
        tokens_reserved=int(value["tokens_reserved"]),
        tokens_max=int(value["tokens_max"]),
        substitutions=tuple(dict(item) for item in value["substitutions"]),
        override=dict(value["override"]) if value.get("override") else None,
        policy_model=str(value["policy_model"]),
        policy_effort=str(value["policy_effort"]),
        fallbacks=tuple(dict(item) for item in value["fallbacks"]),
        workspace_boundary=str(value["workspace_boundary"]),
        admission=(str(value["admission"]) if value.get("admission") is not None else None),
        admission_reason=str(value.get("admission_reason") or ""),
    )


def plan_to_mapping(built: planning.Plan) -> dict[str, Any]:
    return {
        "run_id": built.run_id,
        "outcome": built.outcome,
        "children": [_child_to_mapping(child) for child in built.children],
        "ceiling": built.ceiling,
        "per_vendor_limit": built.per_vendor_limit,
        "aggregate_limit": built.aggregate_limit,
    }


def plan_from_mapping(value: Mapping[str, Any]) -> planning.Plan:
    return planning.Plan(
        run_id=str(value["run_id"]),
        outcome=str(value["outcome"]),
        children=tuple(_child_from_mapping(item) for item in value["children"]),
        ceiling=(float(value["ceiling"]) if value.get("ceiling") is not None else None),
        per_vendor_limit=int(value["per_vendor_limit"]),
        aggregate_limit=int(value["aggregate_limit"]),
    )


def persist_approved_plan(built: planning.Plan) -> Path:
    """Keep the exact plan the operator approved, so a restart can enforce its bounds.

    ``commit_plan`` does not persist the approved spend ceiling, and the ceiling is what every
    later admission decision is measured against. This file is untrusted on the way back in:
    :func:`load_approved_plan` re-renders it and requires the digest to equal the presentation
    receipt's, which is itself bound to the live register generation. An edited ceiling changes
    the rendered text, changes the digest, and is refused.
    """
    path = approved_plan_path(built.run_id)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    register_store._atomic_write_json(path, plan_to_mapping(built))
    return path


def load_approved_plan(run_id: str) -> planning.Plan:
    """The approved plan, or a refusal. Never a plan this run's operator did not approve."""
    path = approved_plan_path(run_id)
    if not path.exists():
        raise ApprovalError(
            f"run {run_id!r} has no approved plan on disk; nothing has been shown to the operator"
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ApprovalError(f"the approved plan for run {run_id!r} is unreadable: {exc}") from exc
    try:
        built = plan_from_mapping(raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise ApprovalError(f"the approved plan for run {run_id!r} is malformed: {exc}") from exc
    receipt = planning.load_presentation_receipt(run_id)
    if planning.plan_digest(built) != receipt.digest:
        raise ApprovalError(
            f"the stored plan for run {run_id!r} does not render to the digest the operator "
            "approved; it is not the plan that was shown"
        )
    return built


def forget_approved_plan(run_id: str) -> None:
    path = approved_plan_path(run_id)
    with contextlib.suppress(FileNotFoundError):
        path.unlink()


# ---------------------------------------------------------------------------- evidence


@dataclass(frozen=True)
class LedgerEntry:
    at: float
    kind: str
    fields: dict[str, Any]

    def to_mapping(self) -> dict[str, Any]:
        return {"at": self.at, "kind": self.kind, **self.fields}


class Ledger:
    """An append-only JSONL record under the run's evidence directory.

    Append-only and flushed on every write, because the record has to survive the process that
    was writing it. A ledger that is only complete when the coordinator exits cleanly cannot
    describe a coordinator that did not.
    """

    def __init__(self, path: Path, *, clock: Callable[[], float]) -> None:
        self.path = path
        self.clock = clock

    def append(self, kind: str, **fields: Any) -> LedgerEntry:
        entry = LedgerEntry(self.clock(), kind, dict(fields))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry.to_mapping(), sort_keys=True, default=str)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return entry

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        found: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                found.append(json.loads(line))
        return found


# ---------------------------------------------------------------------------- subscriptions


def _completion_subscription(row: Mapping[str, Any], pane_id: str | None) -> dict[str, Any] | None:
    record = row.get("completion_sentinel")
    if not isinstance(record, Mapping):
        return None
    sentinel = record.get("sentinel")
    if pane_id is None:
        return None
    if not isinstance(sentinel, str) or not sentinel:
        return None
    return subscriber_module.output_match_subscription(pane_id, sentinel)


def subscriptions_for(
    root: Path,
    *,
    run_id: str,
    herdr: session_lifecycle.HerdrControl | None = None,
) -> tuple[dict[str, Any], ...]:
    """The complete subscription list the subscriber must be started with, from the register.

    ``Subscriber`` takes its subscriptions at construction and has no API to add one mid-run, so
    this is rebuilt and the process restarted whenever the set changes. That is safe rather than
    wasteful: the subscriber runs a bounded ``session.snapshot`` catch-up on every accepted
    subscription, including startup, so a restart reconciles rather than loses.

    Three classes, and no fourth:

    - the run's lifecycle events, which carry state;
    - one nonce-bound completion sentinel per launched child, and one usage needle per child
      whose vendor reports usage at all;
    - the mirror's own return subscription, read from the column ``mirror.py`` owns. Omitting it
      is a total, silent loss of the mirror's clock and every one of its returns, so it is taken
      from the register rather than remembered.
    """
    rows = register_store.read_rows(root, run_id=run_id)
    control = herdr or session_lifecycle.HerdrControl()
    built: list[dict[str, Any]] = [dict(item) for item in RUN_SUBSCRIPTIONS]
    for row_id, row in sorted(rows.items()):
        if register_store.is_supervisory_row(row):
            continue
        pane_id = (
            None
            if row.get("phase") == "planned"
            else session_lifecycle.read_session_pane_id(
                control, root=root, run_id=run_id, row_id=row_id
            )
        )
        subscription = _completion_subscription(row, pane_id)
        if subscription is not None:
            built.append(subscription)
        vendor = str(row.get("vendor") or "")
        if pane_id is not None and accounting.vendor_reports_usage(vendor):
            built.append(subscriber_module.usage_match_subscription(pane_id))
    for row_id, row in sorted(mirror_module.find_mirror_rows(rows).items()):
        expected = mirror_module.expected_subscription(row)
        pane_id = session_lifecycle.read_session_pane_id(
            control, root=root, run_id=run_id, row_id=row_id
        )
        if expected is not None and pane_id is not None:
            built.append(dict(expected))
        vendor = str(row.get("vendor") or "")
        if expected is not None and pane_id is not None and accounting.vendor_reports_usage(vendor):
            built.append(subscriber_module.usage_match_subscription(pane_id))
    assert_subscription_set(built)
    return tuple(built)


def assert_subscription_set(subscriptions: Sequence[Mapping[str, Any]]) -> None:
    """Refuse a set that carries no state or that the subscriber would reject at startup."""
    for index, subscription in enumerate(subscriptions):
        kind = subscription.get("type")
        if kind in NON_STATE_SUBSCRIPTIONS:
            raise SubscriptionSetError(
                f"subscription {index} is {kind!r}, which carries no lifecycle state; every "
                "delivery would wake the orchestrator with nothing new to read"
            )
    herdr_events.build_subscribe_request("orchestrate-composition", subscriptions)
    subscriber_module._sentinel_expectations(subscriptions)


def subscriber_argv(
    *,
    root: Path,
    run_id: str,
    row_id: str,
    pane_id: str,
    orchestrator_pane: str,
    subscriptions: Sequence[Mapping[str, Any]],
    python: str | None = None,
) -> list[str]:
    """The exact command line the subscriber process is started with."""
    return [
        python or sys.executable,
        str(SUBSCRIBER_SCRIPT),
        "--root",
        str(root),
        "--run-id",
        run_id,
        "--row-id",
        row_id,
        "--pane-id",
        pane_id,
        "--orchestrator-pane",
        orchestrator_pane,
        "--subscriptions-json",
        json.dumps([dict(item) for item in subscriptions], sort_keys=True),
    ]


@dataclass(frozen=True)
class OrphanScan:
    """What a process-table search for a live subscriber found, and whether the search completed.

    Mirrors the predicate scanner's ``ScanResult`` (``mirror.py``): a query that raised has
    established nothing about whether a matching process exists, and returning ``process=None``
    for that outcome would be reporting an absence the search never observed. ``complete`` is the
    field every caller must read before trusting ``process is None`` to mean "none is running".
    """

    process: dict[str, Any] | None
    complete: bool


class SubscriberSupervisor(Protocol):
    """The subscriber's parent lifecycle, addressable by handle *and* by durable record.

    The handle half is enough while one coordinator lives. It is not enough across a restart: the
    subscriber is deliberately the process that outlives its parent, so a new coordinator has to
    be able to ask about, adopt, and stop a process it never started. That is what the record half
    is for, and why it is a durable description rather than an object.
    """

    def start(self, argv: Sequence[str]) -> Any: ...

    def is_alive(self, handle: Any) -> bool: ...

    def stop(self, handle: Any) -> None: ...

    def describe(self, handle: Any) -> dict[str, Any]: ...

    def is_record_alive(self, record: Mapping[str, Any], *, signature: Sequence[str]) -> bool: ...

    def stop_record(self, record: Mapping[str, Any]) -> None: ...

    def find_orphan(self, *, signature: Sequence[str]) -> OrphanScan: ...


class SubprocessSubscriberSupervisor:
    """Run the subscriber as a real child process and answer for it from the process, not a row.

    Pane presence leaves a killed subscriber recorded as working, and its own register row says
    ``working`` because it wrote that before it died. The only detector that reaches an
    uncatchable kill is the process itself, which is why liveness is asked of the process here
    and nowhere else.
    """

    def __init__(self, *, popen: Callable[..., Any] | None = None) -> None:
        self.popen = popen or subprocess.Popen

    def start(self, argv: Sequence[str]) -> Any:
        return self.popen(list(argv))  # nosec B603 - argv is built by subscriber_argv

    def is_alive(self, handle: Any) -> bool:
        return handle is not None and handle.poll() is None

    def stop(self, handle: Any) -> None:
        if handle is None or handle.poll() is not None:
            return
        handle.terminate()
        try:
            handle.wait(timeout=10)
        except subprocess.TimeoutExpired:
            handle.kill()
            handle.wait(timeout=10)

    def describe(self, handle: Any) -> dict[str, Any]:
        return {"pid": int(handle.pid)}

    def is_record_alive(self, record: Mapping[str, Any], *, signature: Sequence[str]) -> bool:
        """The recorded pid is running, *and* it is still the process this record named.

        A pid that exists proves only that some process holds that number now -- the operating
        system reuses process ids, and a stale record left by a subscriber that crashed or was
        already reaped can point at a number an unrelated process has since acquired. Asking only
        ``process_is_running`` here is the record-present half of the same question
        :meth:`find_orphan` already answers for the record-missing half: this reuses that same
        scan, by the same signature, and requires the pid it finds to be the pid the record named,
        rather than trusting the number alone.
        """
        pid = int(record.get("pid") or 0)
        if pid <= 0 or not process_is_running(pid):
            return False
        scan = self.find_orphan(signature=signature)
        if not scan.complete:
            raise SubscriberLivenessUnknownError(
                f"process {pid} still holds the recorded pid, but the process table could not be "
                "queried to confirm it is still this run's subscriber; the identity check that "
                "would tell them apart from a reused pid did not complete"
            )
        return scan.process is not None and int(scan.process.get("pid") or 0) == pid

    def stop_record(self, record: Mapping[str, Any]) -> None:
        """Stop a process this object holds no handle for, and wait for it to actually be gone.

        :meth:`stop` can ``wait`` on its ``Popen`` handle; a process known only by pid has no
        handle to wait on, so this polls liveness the way that wait is simulated everywhere else
        in this module. Returning as soon as the signal is sent -- the previous behaviour -- told
        a caller the writer was stopped when only a request to stop it had been made, which is
        exactly the gap between an intent and a confirmed fact this build keeps re-learning not to
        conflate. Escalates to ``SIGKILL`` once, then gives up: a caller that still finds the
        process alive after this returns is told the truth, not a comforting guess.
        """
        pid = int(record.get("pid") or 0)
        if pid <= 0 or not process_is_running(pid):
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGTERM)
        if _wait_for_exit(pid, timeout=10.0):
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)
        _wait_for_exit(pid, timeout=10.0)

    def find_orphan(self, *, signature: Sequence[str]) -> OrphanScan:
        """A live process on this host whose command line carries every token in ``signature``.

        The durable record is written only after :meth:`start` returns, so its absence answers
        "this coordinator has not recorded a subscriber", never "no subscriber process exists" --
        the subscriber is deliberately the process meant to outlive its parent, so a crash or a
        failed write in the gap between those two moments is not a corner case to enumerate
        around, it is the shape of the architecture. This asks the process table itself, the same
        way :meth:`HerdrControl.discover_by_label` answers for a native session the register
        cannot yet describe -- an independent source, not an inference from this run's own
        bookkeeping.

        Returns an :class:`OrphanScan` rather than a bare ``dict | None``: "the table was asked
        and named nothing" and "the table could not be asked" are different facts, and folding
        them into the same ``None`` is what let a query failure be read as a clean absence.
        """
        try:
            completed = subprocess.run(  # nosec B603 B607 - fixed argv, no shell, read-only query
                ["ps", "-eo", "pid=,command="],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return OrphanScan(process=None, complete=False)
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            pid_text, _, command = line.partition(" ")
            if not all(token in command for token in signature):
                continue
            try:
                pid = int(pid_text)
            except ValueError:
                continue
            if process_is_running(pid):
                return OrphanScan(process={"pid": pid}, complete=True)
        return OrphanScan(process=None, complete=True)


def subscriber_record_path(run_id: str) -> Path:
    """Where the running subscriber's identity is kept, beside the live register.

    Deliberately not ``*.json``: every json file beside the live registers is read as a run
    document.
    """
    safe = register_store._safe_run_id(run_id)
    return register_store.register_dir() / f"{safe}.subscriber"


def read_subscriber_record(run_id: str) -> dict[str, Any] | None:
    """The subscriber this run last started, as a new coordinator can see it."""
    path = subscriber_record_path(run_id)
    if not path.exists():
        return None
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return dict(stored) if isinstance(stored, Mapping) else None


def write_subscriber_record(run_id: str, record: Mapping[str, Any]) -> Path:
    path = subscriber_record_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    register_store._atomic_write_json(path, dict(record))
    return path


def forget_subscriber_record(run_id: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        subscriber_record_path(run_id).unlink()


# ---------------------------------------------------------------------------- reap authority


@dataclass(frozen=True)
class ReapAuthorization:
    """What authorised closing one child, with every part named so each can be re-checked."""

    row_id: str
    nonce: str
    artifact_path: str
    artifact_digest: str
    integration: str


def reap_authorization(root: Path, row_id: str, *, run_id: str) -> ReapAuthorization:
    """Authorise a reap from authenticated evidence for *this* attempt, never from ``phase``.

    ``phase`` is a writable register column. A child that produced nothing can set it to
    ``verified`` and have its tab closed as a success; that failure was reproduced, and the reap
    gate one layer down still reads the phase. So four independent things are required here and
    none of them is the phase by itself:

    1. a dispatch receipt that unseals under this run's secret and was issued under this store;
    2. a settlement sealed under that same receipt's nonce, so evidence from an earlier attempt
       cannot authorise this one;
    3. a recorded verdict whose result is a pass;
    4. the artifact still on disk, still carrying this dispatch's binding token, still digesting
       to the value the verdict was recorded against.

    What it does not establish: a runtime whose sandbox does not deny the register directory can
    read this run's key and seal payloads that verify. ``references/predicates.md`` states that
    boundary; this closes every route that does not require the key.
    """
    rows = register_store.read_rows(root, run_id=run_id)
    row = rows.get(row_id)
    if row is None:
        raise ReapAuthorizationError(f"unknown child row {row_id!r}")
    phase = row.get("phase")
    if phase not in {"verified", "reaped"}:
        raise ReapAuthorizationError(
            f"child {row_id!r} is {phase!r}; a child is closed only after a recorded pass"
        )
    try:
        receipt = completion.read_receipt(root, row_id, run_id=run_id)
    except completion.CompletionError as exc:
        raise ReapAuthorizationError(
            f"child {row_id!r} has no authenticated dispatch receipt, so nothing binds its "
            f"evidence to a dispatch: {exc}"
        ) from exc
    try:
        settlement = completion.settlement_record(receipt)
    except completion.CompletionError as exc:
        raise ReapAuthorizationError(
            f"child {row_id!r} has an unauthenticated settlement record: {exc}"
        ) from exc
    if settlement is None:
        raise ReapAuthorizationError(
            f"child {row_id!r} has no settlement record; no artifact was ever renamed into "
            "place for it, so there is nothing a predicate could have read"
        )
    if settlement.nonce != receipt.nonce:
        raise ReapAuthorizationError(
            f"child {row_id!r} settled under attempt {settlement.nonce!r} and its current "
            f"dispatch is {receipt.nonce!r}; evidence from one attempt cannot close another"
        )
    record = completion.completion_record(root, row_id, run_id=run_id)
    if record is None:
        raise ReapAuthorizationError(
            f"child {row_id!r} carries phase {phase!r} with no completion record at all; "
            "the phase is a claim and this is the evidence it claims to summarise"
        )
    if record.get("result") != "verified":
        raise ReapAuthorizationError(
            f"child {row_id!r} has a recorded verdict of {record.get('result')!r} "
            f"({record.get('reason')!r})"
        )
    artifact = Path(settlement.artifact_path)
    try:
        digest = completion.assert_artifact_binding(artifact, receipt)
    except (OSError, completion.ArtifactError) as exc:
        raise ReapAuthorizationError(
            f"child {row_id!r} passed against an artifact that no longer satisfies its own "
            f"dispatch binding: {exc}"
        ) from exc
    if record.get("artifact_digest") != digest:
        raise ReapAuthorizationError(
            f"child {row_id!r} was verified against digest {record.get('artifact_digest')!r} "
            f"and the artifact now digests to {digest!r}; the evidence changed after the verdict"
        )
    integration = record.get("integration")
    if not isinstance(integration, str) or not integration:
        raise ReapAuthorizationError(
            f"child {row_id!r} has no recorded integration result; a change that never landed "
            "must not have its worktree destroyed"
        )
    return ReapAuthorization(
        row_id=row_id,
        nonce=receipt.nonce,
        artifact_path=settlement.artifact_path,
        artifact_digest=digest,
        integration=integration,
    )


# ---------------------------------------------------------------------------- reconciliation


@dataclass(frozen=True)
class Orphan:
    """One reservation held by something other than this coordinator's live run."""

    run_id: str
    row_id: str
    vendor: str
    work_shape: str
    tokens_reserved: int
    state: str
    work_location: str
    phase: str | None
    pane_id: str | None
    tab_id: str | None
    #: Present when this row's dispatch was claimed. ``claimant_running`` is evidence for the
    #: operator making the decision, never the decision itself.
    claimed_by: str | None = None
    claimant_running: bool | None = None
    attempts: int = 0


@dataclass(frozen=True)
class ReconciliationReport:
    """What startup found, and what was decided about each of it."""

    orphans: tuple[Orphan, ...]
    decisions: dict[str, str]
    abandoned: tuple[str, ...]
    resumed: tuple[str, ...]
    promoted: tuple[str, ...]
    queued_here: tuple[str, ...]


def _host_queue() -> set[tuple[str, str]]:
    """Every queued entry on this host, as ``(run_id, row_id)``."""
    waiting: set[tuple[str, str]] = set()
    with admission.admission_locked():
        for run_id in register_store.iter_live_run_ids():
            doc = register_store._read_register_unlocked(run_id)
            for entry in admission._admission_doc(doc)["queue"]:
                if isinstance(entry, Mapping) and entry.get("row_id"):
                    waiting.add((run_id, str(entry["row_id"])))
    return waiting


def host_reservations(
    *,
    exclude_run: str | None = None,
    herdr: session_lifecycle.HerdrControl | None = None,
) -> tuple[Orphan, ...]:
    """Every reservation on this host, with the identity of its occupant.

    Read-only, and deliberately without a clock. A planned reservation has no wall-clock
    expiry: an operator who approves a plan and walks away must not lose the slot to a timer,
    and a timer would equally steal a slot from a live but paused child. The consequence is
    that a dead coordinator's reservations are freed by someone deciding to free them, which is
    why this names the occupants instead of judging them.
    """
    found: list[Orphan] = []
    control = herdr or session_lifecycle.HerdrControl()
    with admission.admission_locked():
        for run_id in register_store.iter_live_run_ids():
            if exclude_run is not None and run_id == exclude_run:
                continue
            doc = register_store._read_register_unlocked(run_id)
            state = admission._admission_doc(doc)
            rows = doc.get("rows", {})
            for row_id, reservation in sorted(state["reservations"].items()):
                if not isinstance(reservation, Mapping):
                    continue
                row = rows.get(row_id, {})
                phase = row.get("phase") if isinstance(row.get("phase"), str) else None
                work_location = Path(str(reservation.get("work_location") or "."))
                if phase == "planned":
                    pane_id = None
                    tab_id = None
                else:
                    pane_id = session_lifecycle.read_session_pane_id(
                        control, root=work_location, run_id=run_id, row_id=str(row_id)
                    )
                    tab_id = session_lifecycle.read_session_tab_id(
                        control, root=work_location, run_id=run_id, row_id=str(row_id)
                    )
                found.append(
                    Orphan(
                        run_id=run_id,
                        row_id=str(row_id),
                        vendor=str(reservation.get("vendor") or ""),
                        work_shape=str(reservation.get("work_shape") or ""),
                        tokens_reserved=int(reservation.get("tokens_reserved") or 0),
                        state=str(reservation.get("state") or "reserved"),
                        work_location=str(reservation.get("work_location") or ""),
                        phase=phase,
                        pane_id=pane_id,
                        tab_id=tab_id,
                    )
                )
    return tuple(found)


# ---------------------------------------------------------------------------- the channel


@dataclass(frozen=True)
class OperatorContext:
    """What the orchestrator knows when an operator message arrives."""

    question: str
    question_id: str
    mirror_request: dict[str, Any] | None
    rows: Mapping[str, Mapping[str, Any]]

    @property
    def mirror_busy(self) -> bool:
        return self.mirror_request is not None


@dataclass(frozen=True)
class OperatorDisposition:
    """The durable receipt that one operator question was answered or explicitly parked."""

    question_id: str
    question: str
    disposition: str
    text: str
    mirror_request_outstanding: bool
    at: float


class OperatorChannel(Protocol):
    """The one voice. The mirror never reaches this."""

    def deliver(self, text: str) -> None: ...

    def ask(self, prompt: str, options: Sequence[str]) -> str: ...


# ---------------------------------------------------------------------------- attempts


@dataclass(frozen=True)
class Attempt:
    """Everything one dispatch needs to be evaluated, rebuildable after a restart."""

    spec: session_lifecycle.ChildSpec
    landing: session_lifecycle.Landing
    baseline: session_lifecycle.ChangedPathsBaseline
    receipt: completion.DispatchReceipt


def _baseline_to_mapping(
    baseline: session_lifecycle.ChangedPathsBaseline,
) -> dict[str, Any]:
    return {
        "paths": sorted(baseline.paths),
        "fingerprints": [[path, value] for path, value in baseline.fingerprints],
        "ambient_paths": sorted(baseline.ambient_paths),
        "ambient_fingerprints": [[path, value] for path, value in baseline.ambient_fingerprints],
        "ambient_base_commit": baseline.ambient_base_commit,
    }


def _baseline_from_mapping(value: Mapping[str, Any]) -> session_lifecycle.ChangedPathsBaseline:
    return session_lifecycle.ChangedPathsBaseline(
        paths=frozenset(str(item) for item in value["paths"]),
        fingerprints=tuple((str(pair[0]), str(pair[1])) for pair in value["fingerprints"]),
        ambient_paths=frozenset(str(item) for item in value.get("ambient_paths") or ()),
        ambient_fingerprints=tuple(
            (str(pair[0]), str(pair[1])) for pair in value.get("ambient_fingerprints") or ()
        ),
        ambient_base_commit=(
            str(value["ambient_base_commit"])
            if value.get("ambient_base_commit") is not None
            else None
        ),
    )


# ---------------------------------------------------------------------------- reports


@dataclass(frozen=True)
class SupervisionReport:
    subscriber_alive: bool
    subscriber_respawned: bool
    mirror_state: str
    mirror_detail: str


@dataclass(frozen=True)
class LaunchReport:
    launched: tuple[str, ...]
    withheld: dict[str, str]


@dataclass(frozen=True)
class AcceptanceReceipt:
    """The Phase 1 pass criteria, computed from the durable record rather than from a claim."""

    run_id: str
    no_child_lost: bool
    no_duplicate_launched: bool
    no_false_completion: bool
    operator_answered_while_mirror_busy: bool
    spend_recorded: bool
    spend_tokens: float | None
    detail: dict[str, Any]

    @property
    def passed(self) -> bool:
        return (
            self.no_child_lost
            and self.no_duplicate_launched
            and self.no_false_completion
            and self.operator_answered_while_mirror_busy
            and self.spend_recorded
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "passed": self.passed,
            "no_child_lost": self.no_child_lost,
            "no_duplicate_launched": self.no_duplicate_launched,
            "no_false_completion": self.no_false_completion,
            "operator_answered_while_mirror_busy": self.operator_answered_while_mirror_busy,
            "spend_recorded": self.spend_recorded,
            "spend_tokens": self.spend_tokens,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------- the coordinator


class Coordinator:
    """One run's control flow. Every collaborator is injected, so every path is reachable."""

    def __init__(
        self,
        root: Path,
        *,
        run_id: str,
        workspace: str,
        orchestrator_pane: str,
        subscriber_pane: str,
        wrapper: Any,
        herdr: Any,
        git: Any,
        interaction: Any,
        channel: OperatorChannel,
        supervisor: SubscriberSupervisor,
        clock: Callable[[], float] = time.time,
        subscriber_row_id: str = "",
        mirror_row_id: str = "mirror",
        readiness_timeout: float = 30.0,
        environment_command: Sequence[str] = ("uv", "sync", "--locked", "--extra", "dev"),
        coordinator_id: str | None = None,
    ) -> None:
        self.root = register_store.canonical_work_location(root)
        self.run_id = register_store._safe_run_id(run_id)
        self.workspace = workspace
        self.orchestrator_pane = orchestrator_pane
        self.subscriber_pane = subscriber_pane
        self.wrapper = wrapper
        self.herdr = herdr
        self.git = git
        self.interaction = interaction
        self.channel = channel
        self.supervisor = supervisor
        self.clock = clock
        self.subscriber_row_id = subscriber_row_id or f"subscriber-{self.run_id}"
        self.mirror_row_id = mirror_row_id
        self.readiness_timeout = readiness_timeout
        self.environment_command = tuple(environment_command)
        # One coordinator object is one dispatch owner. A restarted coordinator is a *different*
        # owner on purpose: it must take over an interrupted dispatch by an explicit decision
        # rather than by inheriting a name.
        self.coordinator_id = coordinator_id or uuid.uuid4().hex
        self._subscriber_handle: Any = None
        self._installed_subscriptions: tuple[dict[str, Any], ...] = ()
        self._attempts: dict[str, Attempt] = {}
        self._dispatching: set[str] = set()
        evidence = register_store.run_dir(self.root, self.run_id)
        self.run_log = Ledger(evidence / "run-log.jsonl", clock=clock)
        self.operator_log = Ledger(evidence / "operator-log.jsonl", clock=clock)
        self._reconciled = False

    # ------------------------------------------------------------------ small readers

    @property
    def evidence_dir(self) -> Path:
        return register_store.run_dir(self.root, self.run_id)

    def rows(self) -> dict[str, dict[str, Any]]:
        return register_store.read_rows(self.root, run_id=self.run_id)

    def child_rows(self) -> dict[str, dict[str, Any]]:
        """Every row this run dispatched as work: not the subscriber, not the mirror."""
        found: dict[str, dict[str, Any]] = {}
        for row_id, row in self.rows().items():
            if register_store.is_supervisory_row(row) or row_id == self.subscriber_row_id:
                continue
            found[row_id] = row
        return found

    def approved_plan(self) -> planning.Plan:
        return load_approved_plan(self.run_id)

    def approved_ceiling(self) -> float:
        ceiling = self.approved_plan().ceiling
        if ceiling is None:
            raise SpendHaltError(
                f"the approved plan for run {self.run_id!r} declares no spend ceiling; this "
                "control flow does not start a child under an unbounded budget"
            )
        return float(ceiling)

    # ------------------------------------------------------------------ run start

    def start_run(self) -> Path:
        """Record the run's trusted work location before anything is launched or issued.

        Receipt issuance precedes dispatch, so recording the root at launch time is already too
        late for the first child. The same path is the one every later ``launch_child`` receives.
        """
        recorded = completion.record_run_root(self.root, self.run_id)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.run_log.append("run_started", run_id=self.run_id, root=str(recorded))
        return recorded

    # ------------------------------------------------------------------ plan and approval

    def plan_run(
        self,
        request: OutcomeRequest,
        children: Sequence[Mapping[str, Any]],
        *,
        ceiling: float,
        is_vendor_available: Callable[[str], bool] | None = None,
    ) -> planning.Plan:
        built = planning.plan(
            request.outcome,
            children,
            run_id=self.run_id,
            ceiling=ceiling,
            is_vendor_available=is_vendor_available,
        )
        self.assert_plan_is_executable(built)
        self.assert_exclusive_artifact_assignment(built)
        self.run_log.append(
            "planned",
            outcome_kind=request.kind,
            children=[child.row_id for child in built.children],
            ceiling=ceiling,
        )
        return built

    def assert_plan_is_executable(self, built: planning.Plan) -> None:
        """Refuse a plan this control flow cannot carry out, before anything durable is written.

        Planning's vocabularies are wider than what the assembled loop can execute, and the two
        gaps are refused here rather than discovered after the operator has approved a plan and a
        child has burned its tokens:

        **An integration mode with no landing.** See :func:`producible_landing_mode`.

        **Judgment-shaped work.** The predicate contract requires a two-evaluation sequence for it:
        evaluate once so the artifact settles, dispatch an independent verifier as an ordinary
        receipt-bearing child against that settled artifact, then evaluate again with its sample.
        This control flow has no verifier dispatch: it accepts a caller-supplied depth sample and
        does not plan, reserve, launch, receipt or collect a verifier of its own. Without one the
        child would run, produce, and then never verify -- the completion gate refuses a verifier
        that holds no dispatch receipt, so it fails closed rather than falsely passing, but the
        operator would only learn that after paying for the work. Refusing at plan time is the
        same fail-closed answer given before it costs anything.
        """
        for child in built.children:
            expected = producible_landing_mode(child.integration_mode)
            if expected != child.integration_mode:
                raise RouteDivergedError(
                    f"child {child.row_id!r} declares integration mode "
                    f"{child.integration_mode!r} and this control flow can only land "
                    f"{sorted(PRODUCIBLE_INTEGRATION_MODES)}; it would run and record "
                    f"{expected!r} instead"
                )
            if completion.is_judgment_shaped(child.work_shape):
                raise UnsupportedWorkShapeError(
                    f"child {child.row_id!r} declares judgment-shaped work "
                    f"({child.work_shape!r}), which requires an independently dispatched verifier "
                    "this control flow does not yet dispatch; plan it as mechanical work or wait "
                    "for the verifier dispatch path"
                )

    def assert_exclusive_artifact_assignment(self, built: planning.Plan) -> None:
        """No two children of this run may produce into one artifact location.

        The evaluator sees one receipt and one landing; only this module sees the whole run's
        assignment graph. A shared location lets a sibling change the settled bytes after the
        digest was recorded, leaving a durable passing verdict that no longer describes the file
        the operator reads.
        """
        seen: dict[str, str] = {}
        for child in built.children:
            location = artifact_relpath(built.run_id, child.row_id, child.artifact_path)
            if location in seen:
                raise ArtifactAssignmentError(
                    f"children {seen[location]!r} and {child.row_id!r} would both produce "
                    f"{location}; one attempt is one exclusive artifact location"
                )
            seen[location] = child.row_id
        # Planning a row this run already carries is a *backwards* transition to ``planned``: a
        # retry or re-plan that puts a row which has moved on back into runnable work. A reaped
        # row would come back with its old pane and expected-exit fields attached; a row whose
        # attempt already failed would be replanned while its evidence and its reservation
        # still describe the attempt that failed.
        live = self.child_rows()
        for child in built.children:
            row = live.get(child.row_id)
            if row is None:
                continue
            assert_forward_transition(row.get("phase"), "planned", row_id=child.row_id)
            self._assert_no_open_attempt(child.row_id, row)

    def approve_plan(self, built: planning.Plan) -> planning.PresentationReceipt:
        """Deliver the rendered plan, take the operator's decision, then create the receipt.

        A callable receipt writer cannot prove a human saw anything, and this cannot either: what
        it establishes is that the receipt does not exist unless the operator channel accepted the
        exact rendered text and the operator's answer was an approval. A channel that raises, or a
        declined plan, leaves no receipt, and ``commit_plan`` refuses without one.
        """
        _built, text = planning.present_plan(built)
        self.channel.deliver(text)
        decision = self.channel.ask(
            "Approve this plan and reserve its slots?", ("approve", "decline")
        )
        if decision != "approve":
            self.run_log.append("plan_declined", decision=decision)
            raise ApprovalError(
                f"the operator answered {decision!r}; no presentation receipt was created and "
                "nothing may be committed against this plan"
            )
        receipt = planning.issue_presentation_receipt(built)
        persist_approved_plan(built)
        self.run_log.append("plan_approved", digest=receipt.digest, generation=receipt.generation)
        return receipt

    def commit(self) -> planning.Plan:
        """Reserve the approved plan's slots. Reads the approval from disk, never from memory."""
        built = self.approved_plan()
        receipt = planning.load_presentation_receipt(self.run_id)
        committed = planning.commit_plan(built, self.root, receipt=receipt)
        self.run_log.append(
            "plan_committed",
            admissions={child.row_id: child.admission for child in committed.children},
        )
        return committed

    # ------------------------------------------------------------------ reconciliation

    def reconcile_startup(
        self,
        *,
        decide: Callable[[Orphan], str] | None = None,
    ) -> ReconciliationReport:
        """Name every reservation this coordinator does not own and decide each one explicitly.

        There is no timer here and there must not be one. A reservation is released because a
        decision was taken about its named occupant, not because it is old.
        """
        orphans = (
            host_reservations(exclude_run=self.run_id, herdr=self.herdr)
            + self.interrupted_dispatches()
        )
        queued_before = _host_queue()
        chooser = decide or self._ask_about_orphan
        decisions: dict[str, str] = {}
        abandoned: list[str] = []
        resumed: list[str] = []
        for orphan in orphans:
            key = f"{orphan.run_id}/{orphan.row_id}"
            answer = chooser(orphan)
            decisions[key] = answer
            mine = orphan.run_id == self.run_id
            if answer == "abandon":
                if mine:
                    self.abandon_child(
                        orphan.row_id, "abandoned at startup reconciliation by operator decision"
                    )
                else:
                    admission.abandon_slot(
                        Path(orphan.work_location or self.root),
                        orphan.row_id,
                        run_id=orphan.run_id,
                    )
                abandoned.append(key)
            else:
                if mine:
                    # Resuming means this coordinator takes the claim. Without that the row stays
                    # owned by a coordinator that is not here, and every later launch refuses it.
                    self.adopt_dispatch_claim(orphan.row_id)
                resumed.append(key)
            self.run_log.append(
                "orphan_reservation",
                occupant=key,
                vendor=orphan.vendor,
                phase=orphan.phase,
                pane_id=orphan.pane_id,
                own_run=mine,
                claimant=orphan.claimed_by,
                claimant_running=orphan.claimant_running,
                decision=answer,
            )
        # Freeing a slot promotes from inside ``abandon_slot``, so the report is the difference
        # between what was waiting before reconciliation and what is still waiting after. Counting
        # only this loop's own promotions would report nothing on the common path and read as
        # "reconciliation advanced nothing" when it had already advanced everything.
        decision = admission.advance_queue()
        while decision is not None:
            decision = admission.advance_queue()
        still_queued = _host_queue()
        promoted = sorted(queued_before - still_queued)
        self._reconciled = True
        report = ReconciliationReport(
            orphans=orphans,
            decisions=decisions,
            abandoned=tuple(abandoned),
            resumed=tuple(resumed),
            promoted=tuple(row_id for _run, row_id in promoted),
            queued_here=admission.queued_row_ids(self.root, run_id=self.run_id),
        )
        self.run_log.append(
            "reconciled",
            orphans=[f"{item.run_id}/{item.row_id}" for item in orphans],
            abandoned=list(report.abandoned),
            promoted=list(report.promoted),
        )
        return report

    def interrupted_dispatches(self) -> tuple[Orphan, ...]:
        """This run's own rows whose dispatch was claimed and never finished.

        Reconciliation deliberately excludes other runs' *live* work by looking only at
        reservations it does not own. That left this run's own interrupted dispatch invisible: a
        launcher error or a crash after the slot was taken leaves the row holding a slot, claimed,
        with no pane, and nothing ever offered it to anyone. The slot stayed occupied and the
        child was neither retried nor abandoned.

        A row is interrupted when it has been claimed for dispatch, is not terminal, is not
        abandoned, and has not recorded ``artifact_protocol_sent`` -- the durable proof that the
        child was actually told where to write. That single fact covers three shapes, not one, and
        which applies is decided later, in :meth:`launch_ready_children`, by what else the row
        carries:

        - **no pane at all.** The launcher never returned, or returned and this coordinator has
          not yet persisted the identity. The launcher's own label recovery is the right next
          step, and that only runs if a coordinator is allowed to hand the row over again.
        - **a pane, a sealed receipt, and no confirmation.** The launcher returned and readiness
          confirmed, but somewhere between the receipt sealing and the artifact-protocol send
          landing -- a persistence failure, a control-plane send that failed -- this coordinator
          lost track of whether the child was ever told its task. The sealed receipt is what makes
          resending safe here, whether or not a completion sentinel was ever durably paired with
          it.
        - **a pane and no sealed receipt.** Readiness itself never completed (a trust prompt, a
          timeout, an effort-application failure), so there is no idempotent identity to resend at
          all. A pane on its own used to mean "the ordinary guards handle it"; they handle a
          *healthy* pane, which is exactly the one row that already carries this marker and so
          never reaches here.

        No clock. A row is offered because of what it is, not because of how long it has been
        that way.
        """
        found: list[Orphan] = []
        reservations: Mapping[str, Any] = {}
        with admission.admission_locked():
            doc = register_store._read_register_unlocked(self.run_id)
            reservations = admission._admission_doc(doc)["reservations"]
        for row_id, row in sorted(self.child_rows().items()):
            claim = claim_of(row)
            if claim is None:
                continue
            if is_terminal(row.get("phase")):
                continue
            if is_abandoned(row):
                continue
            if isinstance(row.get("artifact_protocol_sent"), Mapping):
                continue
            reservation = reservations.get(row_id)
            reservation = reservation if isinstance(reservation, Mapping) else {}
            phase = row.get("phase") if isinstance(row.get("phase"), str) else None
            if phase == "planned":
                pane_id = None
                tab_id = None
            else:
                pane_id = session_lifecycle.read_session_pane_id(
                    self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
                )
                tab_id = session_lifecycle.read_session_tab_id(
                    self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
                )
            found.append(
                Orphan(
                    run_id=self.run_id,
                    row_id=row_id,
                    vendor=str(row.get("vendor") or ""),
                    work_shape=str(reservation.get("work_shape") or row.get("work_shape") or ""),
                    tokens_reserved=int(row.get("tokens_reserved") or 0),
                    state=str(reservation.get("state") or row.get("admission") or ""),
                    work_location=str(self.root),
                    phase=phase,
                    pane_id=pane_id,
                    tab_id=tab_id,
                    claimed_by=claim.coordinator_id,
                    claimant_running=process_is_running(claim.pid),
                    attempts=claim.attempts,
                )
            )
        return tuple(found)

    def _ask_about_orphan(self, orphan: Orphan) -> str:
        if orphan.run_id == self.run_id:
            state = (
                f"holds a {orphan.vendor} slot with no pane"
                if not orphan.pane_id
                else f"holds a live pane ({orphan.pane_id}) that was never confirmed to have "
                "received its task or its artifact instructions"
            )
            return self.channel.ask(
                f"This run's child {orphan.row_id!r} {state} "
                f"(phase {orphan.phase}, {orphan.attempts} dispatch attempt(s), claimed by "
                f"{orphan.claimed_by}, whose process is "
                f"{'running' if orphan.claimant_running else 'not running'}). Its dispatch did "
                "not finish. Resume it or abandon it?",
                ("resume", "abandon"),
            )
        return self.channel.ask(
            "Reservation "
            f"{orphan.run_id}/{orphan.row_id} holds a {orphan.vendor} slot "
            f"(state {orphan.state}, phase {orphan.phase}, pane {orphan.pane_id}) at "
            f"{orphan.work_location}. Resume it or abandon it?",
            ("resume", "abandon"),
        )

    def catch_up(self) -> list[subscriber_module.CatchUpRecord]:
        """One bounded snapshot reconciliation, run by this coordinator on startup and respawn."""
        snapshot = self.herdr.snapshot(cwd=self.root)
        records = subscriber_module.catch_up(self.root, snapshot, run_id=self.run_id)
        diverged = [record.row_id for record in records if record.diverged]
        self.run_log.append("catch_up", rows=len(records), diverged=diverged)
        return records

    # ------------------------------------------------------------------ the subscriber

    def _subscriber_signature(self) -> tuple[str, str, str, str, str]:
        """This run's subscriber, described the one way a process table can be asked about it."""
        return (
            str(SUBSCRIBER_SCRIPT),
            "--run-id",
            self.run_id,
            "--row-id",
            self.subscriber_row_id,
        )

    def _resolve_subscriber_record(self) -> dict[str, Any] | None:
        """This run's subscriber, from its durable record or, absent one, the process table.

        The record is written only after :meth:`SubscriberSupervisor.start` returns, so its
        absence answers "this run has not recorded a subscriber", never "no subscriber exists" --
        that is the fourth appearance of this build's own naming for the shape, and the subscriber
        is deliberately the process meant to outlive its parent, so the gap between those two
        moments is not a corner case, it is the architecture. Every caller that decides whether a
        subscriber of this run is alive goes through this one function -- :meth:`ensure_subscriber`
        to decide adopt-or-replace-or-start, :meth:`running_subscriber` to answer retirement, and
        :meth:`stop_writers` to decide what to stop -- so a fifth route to the same wrong inference
        has nowhere left to open.

        The process table itself can fail to answer -- a transient ``ps`` failure, not a process
        table that was asked and named nothing. :meth:`SubscriberSupervisor.find_orphan` reports
        that as an :class:`OrphanScan` whose ``complete`` is ``False`` rather than folding it into
        the same ``None`` a clean absence returns; this function is the one place that scan is
        read, so this is the one place that distinction either survives or is lost. It is not
        lost: an incomplete scan raises rather than returning ``None``, because every caller here
        would otherwise read that ``None`` as "no subscriber exists" and act on it -- starting a
        second writer, or archiving beside a live one.
        """
        recorded = read_subscriber_record(self.run_id)
        if recorded is not None:
            return recorded
        scan = self.supervisor.find_orphan(signature=self._subscriber_signature())
        if not scan.complete:
            raise SubscriberLivenessUnknownError(
                f"run {self.run_id!r} has no durable subscriber record, and the process table "
                "could not be queried to check for one started but never recorded; that is not "
                'the same fact as "none is running", and nothing here may treat it as one'
            )
        return scan.process

    def ensure_subscriber(self) -> bool:
        """Start or restart the subscriber against the current subscription set.

        Returns whether a process was started. The set is recomputed from the register on every
        call, so a child launched since the last start is subscribed to rather than invisible.

        Reading the durable record, deciding adopt-or-replace-or-start, and writing the new
        record back is one transaction, serialised under this run's generation lock. Without that,
        two coordinators can both read "no record" before either writes one: both then start a
        process, and the second write silently buries the first record with no trace either
        process ever raced. The lock is not reentrant, so nothing inside it may call back into a
        function that takes it again -- :meth:`_acknowledge_mirror_subscription` writes register
        rows through the ordinary locked path, and stays outside.

        A record read as absent still asks the process table (:meth:`_resolve_subscriber_record`)
        before this concludes nothing is running: a subscriber discovered that way carries no
        recorded subscription set, so it always falls into the "different subscription set" branch
        below rather than being silently adopted on a guess -- stopped, then replaced by a process
        this coordinator starts and records itself.
        """
        wanted = subscriptions_for(self.root, run_id=self.run_id, herdr=self.herdr)
        alive = self.supervisor.is_alive(self._subscriber_handle)
        if alive and wanted == self._installed_subscriptions:
            return False
        if self._subscriber_handle is not None and alive:
            self.supervisor.stop(self._subscriber_handle)
            self._subscriber_handle = None

        adopted = False
        started = False
        adopted_pid: Any = None
        replaced_pid: Any = None
        with register_store.generation_locked(self.run_id):
            # A coordinator that has just started holds no handle, and the subscriber is
            # deliberately the process that outlives its parent. Without asking the durable
            # record first, a restart starts a second event stream beside a first one it cannot
            # see: two writers of the same row's observed state and token counts, duplicate
            # wakes, and a retirement that "closed every writer" while one of them was still
            # running.
            recorded = self._resolve_subscriber_record()
            if self._subscriber_handle is None and recorded is not None:
                if self.supervisor.is_record_alive(
                    recorded, signature=self._subscriber_signature()
                ):
                    if list(recorded.get("subscriptions") or []) == [dict(x) for x in wanted]:
                        self._installed_subscriptions = wanted
                        adopted = True
                        adopted_pid = recorded.get("pid")
                    else:
                        self.supervisor.stop_record(recorded)
                        replaced_pid = recorded.get("pid")
                        forget_subscriber_record(self.run_id)
                else:
                    forget_subscriber_record(self.run_id)
            if not adopted:
                argv = subscriber_argv(
                    root=self.root,
                    run_id=self.run_id,
                    row_id=self.subscriber_row_id,
                    pane_id=self.subscriber_pane,
                    orchestrator_pane=self.orchestrator_pane,
                    subscriptions=wanted,
                )
                self._subscriber_handle = self.supervisor.start(argv)
                self._installed_subscriptions = wanted
                write_subscriber_record(
                    self.run_id,
                    {
                        **self.supervisor.describe(self._subscriber_handle),
                        "coordinator_id": self.coordinator_id,
                        "run_id": self.run_id,
                        "row_id": self.subscriber_row_id,
                        "started_at": self.clock(),
                        "subscriptions": [dict(item) for item in wanted],
                    },
                )
                started = True

        if adopted:
            self.run_log.append("subscriber_adopted", pid=adopted_pid, subscriptions=len(wanted))
        else:
            if replaced_pid is not None:
                self.run_log.append(
                    "subscriber_replaced",
                    pid=replaced_pid,
                    detail="the running subscriber holds a different subscription set",
                )
            self.run_log.append("subscriber_started", subscriptions=len(wanted))
        self._acknowledge_mirror_subscription()
        return started

    def running_subscriber(self) -> dict[str, Any] | None:
        """The subscriber this run has running, from the durable record, or ``None``.

        Asked of the record rather than of this object's handle, because the question retirement
        needs answered is "is any subscriber of this run still alive", not "does this coordinator
        remember starting one". Routed through :meth:`_resolve_subscriber_record` so a missing or
        unreadable record falls back to the process table before this answers "none" -- the same
        fallback :meth:`ensure_subscriber` and :meth:`stop_writers` use, so this and retirement
        cannot disagree about what exists.
        """
        recorded = self._resolve_subscriber_record()
        if recorded is None:
            return None
        alive = self.supervisor.is_record_alive(recorded, signature=self._subscriber_signature())
        return recorded if alive else None

    def _acknowledge_mirror_subscription(self) -> None:
        """Tell the mirror the wire exists, or let it say loudly that it does not.

        A mirror row is written *before* its launch side effect, so a mirror whose launch failed
        exists as a row with no pane and no recorded subscription. That row has no returns to lose
        and nothing to confirm, and treating it as a missing wire would let one failed mirror
        launch stop the subscriber from ever starting — which would take the whole run down for a
        component the operator can see failed. It is skipped, and only skipped when the mirror
        module itself reports no expected subscription: a launched mirror always has one.
        """
        rows = self.rows()
        for row_id, row in sorted(mirror_module.find_mirror_rows(rows).items()):
            if mirror_module.expected_subscription(row) is None:
                self.run_log.append(
                    "mirror_unlaunched",
                    row_id=row_id,
                    detail="the mirror row records no return subscription, so it never finished "
                    "launching; there is no wire to confirm",
                )
                continue
            session = mirror_module.resume_mirror(
                self.root, run_id=self.run_id, row_id=row_id, herdr=self.herdr
            )
            mirror_module.acknowledge_subscription(
                session, list(self._installed_subscriptions), now=self.clock()
            )

    def supervise(self) -> SupervisionReport:
        """One supervision tick: admission, the subscriber process, then the mirror clock.

        Liveness is asked of the durable record rather than of this object's handle. A coordinator
        that adopted a running subscriber holds no handle for it, and asking the handle would
        report a divergence that did not happen -- writing a false ``exited`` onto the
        subscriber's row and raising a false alarm on every tick after a restart.
        """
        try:
            reclaimed = admission.reclaim_dead_slots(
                self.root, run_id=self.run_id, herdr=self.herdr
            )
        except admission.AdmissionError as exc:
            self.run_log.append("admission_reclaim_incomplete", detail=str(exc))
        else:
            for row_id in reclaimed:
                self.run_log.append("admission_reclaimed", row_id=row_id)
        alive = self.running_subscriber() is not None
        respawned = False
        if not alive:
            self.run_log.append(
                "subscriber_divergence",
                row_id=self.subscriber_row_id,
                detail="the subscriber process is not running; its event stream is gone",
            )
            self._subscriber_handle = None
            self._installed_subscriptions = ()
            self.ensure_subscriber()
            self.catch_up()
            respawned = True
        state, detail = self._mirror_liveness()
        return SupervisionReport(
            subscriber_alive=self.running_subscriber() is not None,
            subscriber_respawned=respawned,
            mirror_state=state,
            mirror_detail=detail,
        )

    def _mirror_liveness(self) -> tuple[str, str]:
        rows = self.rows()
        mirrors = mirror_module.find_mirror_rows(rows)
        if not mirrors:
            return "absent", "this run has no mirror row"
        row_id = next(iter(sorted(mirrors)))
        try:
            pane_id = session_lifecycle.read_session_pane_id(
                self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
            )
        except session_lifecycle.SessionLifecycleError as exc:
            return "unknown", f"the terminal multiplexer could not answer for the mirror: {exc}"
        if pane_id is None:
            if mirror_module.expected_subscription(mirrors[row_id]) is None:
                return "unlaunched", f"mirror row {row_id!r} never finished launching"
            return "diverged", f"mirror row {row_id!r} has no live pane"
        try:
            snapshot = self.herdr.snapshot(cwd=self.root)
            mirror_module.observe_pane_activity(
                self.root,
                run_id=self.run_id,
                row_id=row_id,
                snapshot=snapshot,
                now=self.clock(),
            )
        except (session_lifecycle.SessionLifecycleError, mirror_module.MirrorError) as exc:
            return "unknown", f"the mirror's live activity could not be determined: {exc}"
        try:
            liveness = mirror_module.check_liveness(
                self.root, run_id=self.run_id, row_id=row_id, now=self.clock()
            )
        except mirror_module.MirrorQuietTooLongError as exc:
            self.run_log.append("mirror_divergence", row_id=row_id, detail=str(exc))
            return "diverged", str(exc)
        return liveness.state, liveness.reference_source or ""

    # ------------------------------------------------------------------ the mirror

    def create_mirror(
        self,
        *,
        runtime: str = "claude",
        max_quiet_seconds: float = 600.0,
        nonce: str | None = None,
    ) -> mirror_module.MirrorSession:
        session = mirror_module.create_mirror(
            self.root,
            run_id=self.run_id,
            row_id=self.mirror_row_id,
            runtime=runtime,
            workspace=self.workspace,
            max_quiet_seconds=max_quiet_seconds,
            wrapper=self.wrapper,
            herdr=self.herdr,
            git=self.git,
            interaction=self.interaction,
            nonce=nonce,
            readiness_timeout=self.readiness_timeout,
            environment_command=(),
        )
        self.run_log.append("mirror_created", row_id=session.row_id, pane_id=session.pane_id)
        self.ensure_subscriber()
        return session

    def mirror_session(self) -> mirror_module.MirrorSession:
        """Rebuild the live mirror from its durable row -- the restart path's only handle."""
        return mirror_module.resume_mirror(
            self.root, run_id=self.run_id, row_id=self.mirror_row_id, herdr=self.herdr
        )

    def ask_mirror(self, request: mirror_module.MirrorRequest) -> str:
        session = self.mirror_session()
        request_id = mirror_module.dispatch_request(
            session, request, herdr=self.herdr, now=self.clock(), git=self.git
        )
        self.run_log.append("mirror_dispatched", request_id=request_id, request_kind=request.kind)
        return request_id

    def collect_mirror(self) -> mirror_module.MirrorReturn:
        session = self.mirror_session()
        returned = mirror_module.collect_return(
            session, herdr=self.herdr, now=self.clock(), git=self.git
        )
        self.run_log.append(
            "mirror_returned", request_id=returned.request_id, bytes=returned.byte_length
        )
        return returned

    def _outstanding_mirror_request(self) -> dict[str, Any] | None:
        """Read the mirror's state from the register. Never from its pane."""
        row = self.rows().get(self.mirror_row_id)
        return mirror_module.outstanding_request(row) if row is not None else None

    # ------------------------------------------------------------------ the operator channel

    def handle_operator_message(
        self,
        question: str,
        *,
        answer: Callable[[OperatorContext], str],
        question_id: str | None = None,
    ) -> OperatorDisposition:
        """Answer an operator question, or park it with a reason. Never drop it.

        Nothing on this path reads the mirror's pane, waits for a mirror return, or blocks on a
        subscription: the mirror's state is taken from its register row, and an outstanding
        request is reported to the handler as context rather than waited on. Every exit records a
        disposition first, including the exits that raise -- a question that killed the handler is
        parked, not lost.
        """
        qid = question_id or uuid.uuid4().hex
        outstanding = self._outstanding_mirror_request()
        context = OperatorContext(question, qid, outstanding, self.rows())
        try:
            reply = answer(context)
        except ParkQuestionError as exc:
            return self._record_disposition(qid, question, "parked", str(exc), outstanding)
        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised unchanged
            self._record_disposition(
                qid,
                question,
                "parked",
                f"the handler raised {type(exc).__name__}: {exc}",
                outstanding,
            )
            raise
        if not isinstance(reply, str) or not reply.strip():
            return self._record_disposition(
                qid, question, "parked", "the handler produced no answer", outstanding
            )
        try:
            self.channel.deliver(reply)
        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised unchanged
            self._record_disposition(
                qid, question, "parked", f"delivery failed: {exc}", outstanding
            )
            raise
        return self._record_disposition(qid, question, "answered", reply, outstanding)

    def _record_disposition(
        self,
        question_id: str,
        question: str,
        disposition: str,
        text: str,
        outstanding: Mapping[str, Any] | None,
    ) -> OperatorDisposition:
        entry = self.operator_log.append(
            "operator_question",
            question_id=question_id,
            question=question,
            disposition=disposition,
            text=text,
            mirror_request_outstanding=outstanding is not None,
            mirror_request_id=(outstanding or {}).get("request_id"),
        )
        return OperatorDisposition(
            question_id=question_id,
            question=question,
            disposition=disposition,
            text=text,
            mirror_request_outstanding=outstanding is not None,
            at=entry.at,
        )

    def open_operator_questions(self) -> tuple[str, ...]:
        """Question ids recorded as parked and never subsequently answered."""
        parked: dict[str, str] = {}
        for entry in self.operator_log.entries():
            if entry.get("kind") != "operator_question":
                continue
            parked[str(entry.get("question_id"))] = str(entry.get("disposition"))
        return tuple(sorted(qid for qid, state in parked.items() if state == "parked"))

    # ------------------------------------------------------------------ spend

    def _native_session_may_exist(self, row_id: str, row: Mapping[str, Any]) -> bool:
        """Whether the substrate might already hold a live session for this row.

        ``phase == "launching"`` is written *before* the native launcher is called, so it cannot
        by itself distinguish "the launcher was never invoked" from "the launcher returned an
        identity and this coordinator has not yet persisted it" -- the exact window
        :func:`session_lifecycle.launch_child` was built to recover from, and the window a
        durable marker written by *this process* can never close on its own: it only ever records
        what this process did, never what the native launcher produced on the other side of that
        boundary. Only asking the substrate settles it, by the same deterministic, run-bound
        label the launcher itself would use (:func:`session_lifecycle.task_label`), so a match
        here is the same session a resumed dispatch would recover.

        An answer the substrate could not give is not proof of absence. Both here and in
        :meth:`_assert_child_never_ran`, "I could not tell" is folded into "a session may exist" --
        the same posture this module already takes toward a metered vendor's genuine silence.
        """
        del row
        try:
            return (
                session_lifecycle.read_session_pane_id(
                    self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
                )
                is not None
            )
        except session_lifecycle.SessionLifecycleError:
            return True

    def spend_status(self, *, launching_row_id: str | None = None) -> tuple[str, str]:
        """``ok``, ``unknown`` or ``exceeded``, with the reason named.

        Both refusing answers stop a launch; they are separated so the operator is told the true
        cause. ``unknown`` is a launched metered child that has not yet printed a usage line --
        fail-closed by the accounting contract, and cleared by the next usage event rather than
        by a timer. Classification reads only accounting's own public predicates, so the
        authorisation itself stays in :func:`accounting.check_spend`.

        ``launching_row_id`` is the row this call is itself about to recover or launch. Its own
        presence does not block that recovery; every other ambiguous launch still does.
        """
        ceiling = self.approved_ceiling()
        unresolved: list[str] = []
        pending: list[str] = []
        abandoned_row_ids: set[str] = set()
        absent_launches: set[str] = set()
        for row_id, row in sorted(self.child_rows().items()):
            phase = row.get("phase")
            if phase not in accounting.LAUNCHED_PHASES or phase == "planned":
                continue
            observed = row.get("tokens_observed")
            observed_is_number = isinstance(observed, (int, float)) and not isinstance(
                observed, bool
            )
            if is_abandoned(row) and _producer_confirmed_stopped(row) and not observed_is_number:
                # This coordinator deliberately stopped pursuing this row, recorded why, and
                # (:meth:`abandon_child`) either proved it never held a session or stopped the one
                # it held and confirmed the tab gone. Only an unrecorded stopped producer is
                # excused here: "no longer awaited" is not "no longer spending", and recorded
                # usage remains part of the run total even after its producer is gone. A row
                # abandoned without a confirmed stop falls through to the same checks an ordinary
                # row gets below, so its spend still gates the run until absence is established.
                abandoned_row_ids.add(row_id)
                continue
            if phase == "launching":
                if row_id == launching_row_id:
                    absent_launches.add(row_id)
                    continue
                if self._native_session_may_exist(row_id, row):
                    unresolved.append(row_id)
                else:
                    absent_launches.add(row_id)
                continue
            vendor = str(row.get("vendor") or row.get("agent") or "")
            if not accounting.vendor_reports_usage(vendor):
                continue
            if not observed_is_number:
                pending.append(row_id)
        if unresolved:
            return (
                "unknown",
                f"rows {unresolved} carry launch intent and the live owner could not establish "
                "that no session exists; no further child starts",
            )
        if pending:
            return (
                "unknown",
                f"rows {pending} are launched under a metered vendor and have reported no usage; "
                "the run's spend is not yet knowable, so no further child starts",
            )
        try:
            accounting.check_spend(
                self.root,
                run_id=self.run_id,
                ceiling=ceiling,
                exclude_row_ids=abandoned_row_ids | absent_launches,
            )
        except accounting.AccountingError as exc:
            return "exceeded", str(exc)
        return "ok", ""

    def record_step_failure(self, kind: str, row_id: str, exc: BaseException) -> None:
        """Emit on the failing path too, because silence is not evidence of progress.

        Every step below records its own success. A step that records nothing when it raises
        leaves a run log that reads as "activated a slot, then stopped happening", which is
        indistinguishable from a coordinator that is still working. A monitor that only emits on
        success cannot tell a crash from a slow child.
        """
        self.run_log.append(kind, row_id=row_id, error=type(exc).__name__, detail=str(exc))

    def assert_spend_allows_a_launch(self, *, launching_row_id: str | None = None) -> None:
        state, detail = self.spend_status(launching_row_id=launching_row_id)
        if state == "ok":
            return
        self.run_log.append("spend_halt", state=state, detail=detail)
        if state == "unknown":
            raise SpendUnobservableError(detail)
        raise SpendCeilingError(detail)

    # ------------------------------------------------------------------ launching

    def launch_ready_children(self) -> LaunchReport:
        """Launch every reserved, launchable child of the approved plan, in plan order."""
        if not self._reconciled:
            raise AdmissionOrderError(
                "startup reconciliation has not run; a coordinator that has not decided about "
                "the reservations already on this host must not add to them"
            )
        built = self.approved_plan()
        launched: list[str] = []
        withheld: dict[str, str] = {}
        for child in built.children:
            try:
                row = self.rows().get(child.row_id, {})
                if self._needs_protocol_redelivery(row):
                    self.redeliver_artifact_protocol(child.row_id)
                elif self._needs_completion_binding(row):
                    self.bind_and_redeliver_completion(child.row_id)
                elif self._stalled_before_confirmation(row):
                    raise UnconfirmedDispatchError(
                        f"row {child.row_id!r} holds a live pane whose readiness was never "
                        "confirmed; no automatic recovery is safe for it, so it can only be "
                        "abandoned explicitly"
                    )
                else:
                    self.launch_child(child)
            except SpendHaltError as exc:
                withheld[child.row_id] = str(exc)
                self.record_step_failure("launch_withheld", child.row_id, exc)
                for remaining in built.children[built.children.index(child) + 1 :]:
                    withheld.setdefault(remaining.row_id, str(exc))
                break
            except (
                AdmissionOrderError,
                PhaseOrderError,
                ConcurrentAttemptError,
                DispatchClaimError,
                UnconfirmedDispatchError,
                session_lifecycle.SessionLifecycleError,
            ) as exc:
                # One child's launcher error must not end the sweep. The failed row keeps its
                # claim and its held slot, which is what makes it recoverable rather than lost:
                # this coordinator will retry it on a later sweep, and a coordinator that comes
                # back after a crash is offered the same row as an explicit decision.
                withheld[child.row_id] = str(exc)
                self.record_step_failure("launch_withheld", child.row_id, exc)
                continue
            launched.append(child.row_id)
        return LaunchReport(tuple(launched), withheld)

    def launch_child(self, child: planning.PlannedChild) -> Attempt:
        """Admit, launch, confirm, bind, and dispatch one approved child, in that order."""
        row = self.rows().get(child.row_id, {})
        # Ordering, not duplication: the claim transaction below re-checks these under the lock
        # and is the authority. Checking them here first is what makes a row that must not be
        # relaunched report *that*, rather than whichever later gate happens to notice something.
        assert_forward_transition(row.get("phase"), "launching", row_id=child.row_id)
        self._assert_no_open_attempt(child.row_id, row)
        self._assert_reserved_for(child, row)
        self.assert_spend_allows_a_launch(launching_row_id=child.row_id)
        resolution = self._assert_route_custody(child)

        # Everything above reads and then decides, so two coordinators can both pass it. The
        # claim below is the first step that reads and writes in one locked transaction, which is
        # why it is the one that actually serialises dispatch, and why it re-checks launchability
        # from the row it read under the lock rather than trusting the reads above.
        claim = self.claim_dispatch(child)
        self.run_log.append(
            "dispatch_claimed",
            row_id=child.row_id,
            coordinator=claim.coordinator_id,
            attempts=claim.attempts,
        )

        admission.activate_slot(self.root, child.row_id, run_id=self.run_id)
        self.run_log.append("slot_activated", row_id=child.row_id, vendor=child.vendor)

        spec = self.child_spec(child)
        self._dispatching.add(child.row_id)
        try:  # noqa: PLR1702 - the failure recorder wraps the whole dispatch on purpose
            # Everything between ``claim_dispatch`` returning and here ran outside the lock that
            # serialises taking the claim, so it proves nothing about *still holding* it: an
            # explicit resume decision made by a different coordinator -- or a second thread of
            # this same one -- can have adopted it in the meantime, and that overwrite is this
            # build's deliberate policy (:meth:`adopt_dispatch_claim`), not a bug to route around.
            # What must not happen is a coordinator that no longer holds the claim reaching the
            # one call only the holder may make. Re-reading the claim immediately before it is
            # the only way the answer is still current.
            self._assert_dispatch_claim_still_mine(child.row_id, claim)
            identity, landing, launched_resolution = session_lifecycle.launch_child(
                self.root,
                spec,
                wrapper=self.wrapper,
                herdr=self.herdr,
                git=self.git,
                claim_guard=lambda: self._verify_claim_unlocked(child.row_id, claim),
            )
            self._assert_launched_custody(child, launched_resolution, landing)
            self.run_log.append(
                "child_launched",
                row_id=child.row_id,
                vendor=child.vendor,
                model=child.model,
                effort=child.effort,
                pane_id=identity.pane_id,
                tab_id=identity.tab_id,
            )
            ready = session_lifecycle.confirm_ready(
                self.root,
                spec,
                identity,
                landing,
                resolution,
                herdr=self.herdr,
                interaction=self.interaction,
                git=self.git,
            )
            receipt = completion.issue_receipt(
                spec,
                landing,
                completion.PredicateSpec.from_mapping(child.predicate),
                artifact_name=PurePosixPath(child.artifact_path).name,
                git=self.git,
                changed_paths_baseline=ready.changed_paths_baseline,
            )
            sentinel = subscriber_module.make_sentinel(
                self.run_id, child.row_id, COMPLETION_PURPOSE
            )
            _write_owned(
                self.root,
                child.row_id,
                {
                    "completion_sentinel": {"sentinel": sentinel},
                    "changed_paths_baseline": _baseline_to_mapping(ready.changed_paths_baseline),
                },
                run_id=self.run_id,
            )
            self.herdr.send_line(
                identity.pane_id,
                completion.artifact_instructions(receipt)
                + "\n"
                + subscriber_module.sentinel_assembly_instructions(
                    sentinel, when="the deliverable is completely written and you have stopped"
                ),
                cwd=landing.cwd,
            )
            _write_owned(
                self.root,
                child.row_id,
                {"artifact_protocol_sent": {"at": self.clock(), "nonce": receipt.nonce}},
                run_id=self.run_id,
            )
        except Exception as exc:
            # The slot is held and, past the launcher, a session may exist. Neither is unwound
            # here: closing a live session on a failed *later* step would destroy work, and a
            # held reservation with no pane, or a live pane with no recorded
            # ``artifact_protocol_sent``, is exactly what startup reconciliation's explicit
            # resume-or-abandon decision is for -- ownership, never a clock. What must not
            # happen is that it goes unrecorded.
            self.record_step_failure("child_launch_failed", child.row_id, exc)
            raise
        finally:
            self._dispatching.discard(child.row_id)

        attempt = Attempt(spec, landing, ready.changed_paths_baseline, receipt)
        self._attempts[child.row_id] = attempt
        self.run_log.append("child_dispatched", row_id=child.row_id, nonce=receipt.nonce)
        self.ensure_subscriber()
        return attempt

    def _needs_protocol_redelivery(self, row: Mapping[str, Any]) -> bool:
        """Whether a row has a live pane and already-sealed evidence, but no confirmed delivery.

        ``completion_sentinel`` present is what tells the three shapes in
        :meth:`interrupted_dispatches` apart: it is written only after the dispatch receipt was
        sealed, which happens only after readiness was confirmed. A row with a pane and that
        marker got everything right up to the one control-plane call that can fail ambiguously.
        """
        if (
            is_terminal(row.get("phase"))
            or is_abandoned(row)
            or isinstance(row.get("artifact_protocol_sent"), Mapping)
            or not isinstance(row.get("completion_sentinel"), Mapping)
        ):
            return False
        return self._live_pane_id(row) is not None

    def _needs_completion_binding(self, row: Mapping[str, Any]) -> bool:
        """Whether a row has a sealed receipt but never reached the write that binds it.

        ``completion.issue_receipt`` and the sentinel-and-baseline write that follows it are two
        separate register writes, not one. A failure strictly between them leaves the receipt --
        durable, authoritative proof that readiness completed -- sealed with nothing that could
        yet resend a task the child was never actually told, and :meth:`_stalled_before_confirmation`
        would otherwise misclassify that row as one where readiness never happened at all, the
        exact "no record of X read as X does not exist" shape this build keeps re-finding. The
        receipt's presence is checked directly rather than inferred from ``completion_sentinel``,
        because the receipt is the earlier of the two facts and cannot itself be false.
        """
        if (
            is_terminal(row.get("phase"))
            or is_abandoned(row)
            or isinstance(row.get("artifact_protocol_sent"), Mapping)
            or isinstance(row.get("completion_sentinel"), Mapping)
            or not isinstance(row.get(completion.DISPATCH_RECEIPT_KEY), Mapping)
        ):
            return False
        return self._live_pane_id(row) is not None

    def _stalled_before_confirmation(self, row: Mapping[str, Any]) -> bool:
        """Whether a row has a live pane but never reached a sealed, resendable dispatch.

        The mirror image of :meth:`_needs_protocol_redelivery` and :meth:`_needs_completion_binding`
        together: a pane exists, but readiness itself never completed (a trust prompt, a timeout,
        an effort-application failure), so there is no sealed receipt at all -- not merely no
        completion sentinel -- and therefore no idempotent identity this coordinator could resend
        without risking a second, contradictory instruction to a pane whose actual state it cannot
        see.
        """
        if (
            row.get("phase") in {"planned", "launching"}
            or is_terminal(row.get("phase"))
            or is_abandoned(row)
            or isinstance(row.get("artifact_protocol_sent"), Mapping)
            or isinstance(row.get("completion_sentinel"), Mapping)
            or isinstance(row.get(completion.DISPATCH_RECEIPT_KEY), Mapping)
        ):
            return False
        return self._live_pane_id(row) is not None

    def _live_pane_id(self, row: Mapping[str, Any]) -> str | None:
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id:
            raise CompositionError("a live pane query requires a row identifier")
        return session_lifecycle.read_session_pane_id(
            self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
        )

    def bind_and_redeliver_completion(self, row_id: str) -> None:
        """Finish binding a sealed receipt that never reached its sentinel write, then deliver it.

        Reached only for a row :meth:`_needs_completion_binding` has already established never got
        as far as the artifact-protocol send, so nothing has reached the pane for this attempt yet:
        a fresh completion sentinel is exactly as safe to mint as the first one would have been,
        and the changed-paths snapshot the receipt was sealed against is still the current state of
        the worktree, because nothing has been told to touch it. Both would stop being safe to take
        the moment a task reaches the pane, which is why this binds and sends in the same call
        rather than leaving the binding for a later sweep to find undone again.
        """
        row = self.rows().get(row_id, {})
        claim = claim_of(row)
        if claim is None or claim.coordinator_id != self.coordinator_id:
            raise DispatchClaimError(
                f"row {row_id!r} redelivery requires this coordinator's own dispatch claim; "
                "reconcile the run and resume it before redelivering"
            )
        receipt = completion.read_receipt(self.root, row_id, run_id=self.run_id)
        pane_id = session_lifecycle.read_session_pane_id(
            self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
        )
        if pane_id is None:
            raise CompositionError(
                f"row {row_id!r} has no live pane; there is nothing to redeliver to"
            )
        landing_cwd = Path(receipt.landing_cwd)
        baseline = self.git.changed_paths_baseline(
            landing_cwd,
            base_commit=receipt.base_commit,
            ambient_root=(Path(receipt.ambient_root) if receipt.ambient_root else None),
        )
        sentinel = subscriber_module.make_sentinel(self.run_id, row_id, COMPLETION_PURPOSE)
        _write_owned(
            self.root,
            row_id,
            {
                "completion_sentinel": {"sentinel": sentinel},
                "changed_paths_baseline": _baseline_to_mapping(baseline),
            },
            run_id=self.run_id,
        )
        self.herdr.send_line(
            pane_id,
            completion.artifact_instructions(receipt)
            + "\n"
            + subscriber_module.sentinel_assembly_instructions(
                sentinel, when="the deliverable is completely written and you have stopped"
            ),
            cwd=landing_cwd,
        )
        _write_owned(
            self.root,
            row_id,
            {"artifact_protocol_sent": {"at": self.clock(), "nonce": receipt.nonce}},
            run_id=self.run_id,
        )
        self.run_log.append("completion_bound_and_redelivered", row_id=row_id, nonce=receipt.nonce)

    def redeliver_artifact_protocol(self, row_id: str) -> None:
        """Resend the artifact protocol to a pane that was never confirmed to have received it.

        A row this far into dispatch already carries a sealed receipt, a completion sentinel, and
        a changed-paths baseline -- reissuing any of those would put two producers on one artifact
        (:meth:`_assert_no_open_attempt`). What can fail ambiguously is the one control-plane call
        that tells the child what those already-sealed identifiers are. The instructions are
        idempotent under their own nonce, so resending them to the pane the launcher already
        returned is safe whether or not the first attempt landed: it opens no second session,
        seals no second receipt, and a child that already read them once reads the same thing
        again.
        """
        row = self.rows().get(row_id, {})
        claim = claim_of(row)
        if claim is None or claim.coordinator_id != self.coordinator_id:
            raise DispatchClaimError(
                f"row {row_id!r} redelivery requires this coordinator's own dispatch claim; "
                "reconcile the run and resume it before redelivering"
            )
        pane_id = session_lifecycle.read_session_pane_id(
            self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
        )
        if pane_id is None:
            raise CompositionError(
                f"row {row_id!r} has no live pane; there is nothing to redeliver to"
            )
        sentinel_field = row.get("completion_sentinel")
        if not isinstance(sentinel_field, Mapping) or not sentinel_field.get("sentinel"):
            raise CompositionError(
                f"row {row_id!r} has a pane but no recorded completion sentinel; its dispatch "
                "receipt was never sealed, so redelivery has nothing to send"
            )
        receipt = completion.read_receipt(self.root, row_id, run_id=self.run_id)
        self.herdr.send_line(
            pane_id,
            completion.artifact_instructions(receipt)
            + "\n"
            + subscriber_module.sentinel_assembly_instructions(
                str(sentinel_field["sentinel"]),
                when="the deliverable is completely written and you have stopped",
            ),
            cwd=Path(receipt.landing_cwd),
        )
        _write_owned(
            self.root,
            row_id,
            {"artifact_protocol_sent": {"at": self.clock(), "nonce": receipt.nonce}},
            run_id=self.run_id,
        )
        self.run_log.append("artifact_protocol_redelivered", row_id=row_id, nonce=receipt.nonce)

    def child_spec(self, child: planning.PlannedChild) -> session_lifecycle.ChildSpec:
        """The launch specification, carrying the approved route and nothing recomputed.

        ``work_shape`` is the plan's *execution class* because that is the value
        ``planning.route`` resolved the model and effort against; passing the portable shape
        would make the launcher resolve a different tier. ``mutating`` is derived from the
        approved integration mode, which the operator saw: a child that must land a change
        needs an isolated worktree, and one that only produces a deliverable does not.
        """
        return session_lifecycle.ChildSpec(
            run_id=self.run_id,
            row_id=child.row_id,
            runtime=child.vendor,
            work_shape=child.execution_class,
            instruction=child.task,
            scope=tuple(child.scope),
            mutating=child.integration_mode != "none",
            workspace=self.workspace,
            readiness_timeout=self.readiness_timeout,
            environment_command=self.environment_command,
        )

    def claim_dispatch(self, child: planning.PlannedChild) -> DispatchClaim:
        """Take durable, generation-bound ownership of this row's dispatch, or refuse.

        One locked transaction: read the row, re-check the facts that decide whether it may still
        be handed to the launcher, inspect any existing claim, and write this coordinator's claim.
        A second coordinator that reached the same point either blocks on the lock and then finds
        a claim it does not own, or takes the claim first and the first one finds it. Neither can
        reach the launcher without holding it.

        The checks re-run here are the ones that decide *double dispatch* and can be answered from
        the row alone -- phase and pane. The receipt and reservation checks stay outside because
        they read the register through APIs that take this same non-reentrant lock; they are a
        pre-filter, and the claim is the decision.

        An existing claim held by a different coordinator is refused outright. It is not overridden
        because its holder looks dead: taking a claim on that evidence is a clock wearing a
        different hat, and it is how two coordinators end up launching one child. Recovering a
        claim is an explicit ownership decision -- see :meth:`interrupted_dispatches`.
        """
        claimed = register_store.canonical_work_location(self.root)
        generation = register_store.read_generation_sidecar(self.run_id) or ""
        with register_store.generation_locked(self.run_id):
            doc = register_store._read_register_unlocked(self.run_id)
            row = doc.get("rows", {}).get(child.row_id, {})
            assert_forward_transition(row.get("phase"), "launching", row_id=child.row_id)
            existing = claim_of(row)
            attempts = 0
            if existing is not None:
                if existing.coordinator_id != self.coordinator_id:
                    raise DispatchClaimError(
                        f"row {child.row_id!r} is claimed for dispatch by coordinator "
                        f"{existing.coordinator_id!r} (process {existing.pid}, "
                        f"{'running' if process_is_running(existing.pid) else 'not running'}); "
                        "this coordinator does not own it. Reconcile the run and decide whether "
                        "to resume or abandon it before launching."
                    )
                attempts = existing.attempts
            claim = DispatchClaim(
                coordinator_id=self.coordinator_id,
                pid=os.getpid(),
                generation=generation,
                attempts=attempts + 1,
                claimed_at=self.clock(),
            )
            _write_owned_unlocked(
                claimed, child.row_id, {"dispatch_claim": claim.to_mapping()}, run_id=self.run_id
            )
        return claim

    def adopt_dispatch_claim(self, row_id: str) -> DispatchClaim | None:
        """Take over an interrupted dispatch after an explicit decision to resume it."""
        claimed = register_store.canonical_work_location(self.root)
        generation = register_store.read_generation_sidecar(self.run_id) or ""
        with register_store.generation_locked(self.run_id):
            doc = register_store._read_register_unlocked(self.run_id)
            row = doc.get("rows", {}).get(row_id, {})
            existing = claim_of(row)
            if existing is None:
                return None
            claim = DispatchClaim(
                coordinator_id=self.coordinator_id,
                pid=os.getpid(),
                generation=generation,
                attempts=existing.attempts,
                claimed_at=self.clock(),
            )
            _write_owned_unlocked(
                claimed, row_id, {"dispatch_claim": claim.to_mapping()}, run_id=self.run_id
            )
        return claim

    def release_dispatch_claim(self, row_id: str) -> None:
        """Forget the claim once the dispatch it owned is finished with."""
        _write_owned(self.root, row_id, {"dispatch_claim": None}, run_id=self.run_id)

    def _assert_dispatch_claim_still_mine(self, row_id: str, claim: DispatchClaim) -> None:
        """Refuse to proceed on a claim that has already changed hands -- a fast, early check.

        This is deliberately *not* the check that makes launch-once true. It runs before
        ``session_lifecycle.launch_child`` does any work, so a claim already lost is reported
        without paying for admission, git provisioning, or a wrapper preview first -- ordering,
        the same way the guards at the top of :meth:`launch_child` are ordering rather than the
        authority. A claim found valid *here* can still be taken by an explicit resume before the
        native launcher runs; :func:`session_lifecycle.launch_child`'s ``claim_guard`` is what
        that cannot get past, because it re-reads the claim inside the same lock hold that makes
        the native call, not a moment before it.
        """
        current = claim_of(self.rows().get(row_id, {}))
        if current != claim:
            raise DispatchClaimError(
                f"row {row_id!r}'s dispatch claim is no longer the one this coordinator took "
                f"(attempt {claim.attempts} at {claim.claimed_at:g}); a later transaction -- "
                "another coordinator's explicit resume decision, or a second thread of this one "
                "-- holds it now, and only the current holder may reach the native launcher"
            )

    def _verify_claim_unlocked(self, row_id: str, claim: DispatchClaim) -> None:
        """The authoritative claim re-check: read without taking the lock, because it is held.

        Passed into :func:`session_lifecycle.launch_child` as ``claim_guard`` and called from
        *inside* one continuous hold of this run's generation lock that also covers the native
        launch call and the identity write that follows it. ``adopt_dispatch_claim`` needs the
        same lock to replace this row's claim, so whichever of the two reaches it first is the
        one the native launcher answers to -- this is not a narrower window, it is the same
        transaction as the one that could steal the claim. Calling any of the *locked* public
        register functions here would deadlock: the lock this runs inside is not reentrant, so
        the read has to go through the unlocked primitive directly, exactly like
        :meth:`claim_dispatch` and :meth:`adopt_dispatch_claim` already do.
        """
        doc = register_store._read_register_unlocked(self.run_id)
        current = claim_of(doc.get("rows", {}).get(row_id, {}))
        if current != claim:
            raise DispatchClaimError(
                f"row {row_id!r}'s dispatch claim changed hands at the moment this coordinator "
                f"reached the native launcher (attempt {claim.attempts} at {claim.claimed_at:g}); "
                "another coordinator's explicit resume decision holds it now, and the launcher "
                "was not called"
            )

    def _assert_no_open_attempt(self, row_id: str, row: Mapping[str, Any]) -> None:
        if row_id in self._dispatching:
            raise ConcurrentAttemptError(
                f"row {row_id!r} is already being dispatched by this coordinator"
            )
        if not isinstance(row.get(completion.DISPATCH_RECEIPT_KEY), Mapping):
            return
        try:
            receipt = completion.read_receipt(self.root, row_id, run_id=self.run_id)
        except completion.CompletionError:
            return
        settlement = completion.settlement_record(receipt)
        if settlement is None or settlement.nonce != receipt.nonce:
            raise ConcurrentAttemptError(
                f"row {row_id!r} already has dispatch {receipt.nonce!r} open and unsettled; a "
                "second attempt would put two producers on one artifact"
            )

    def reservation_for(self, row_id: str) -> Mapping[str, Any] | None:
        """The reservation record admission holds for one row, or ``None``."""
        doc = register_store.read_register(self.run_id)
        reservation = admission._admission_doc(doc)["reservations"].get(row_id)
        return reservation if isinstance(reservation, Mapping) else None

    def _assert_reserved_for(self, child: planning.PlannedChild, row: Mapping[str, Any]) -> None:
        """Launch only from a reservation whose identity is the approved child's.

        The status column and the reservation record are two different facts, and the check is
        against the record: a row can carry ``admission="reserved"`` with no reservation behind
        it, and an active child with no reservation is exactly the row that escapes the host-wide
        work-in-progress bound. The row's own ``work_shape`` column is the portable shape the plan
        declared, while the reservation holds the execution class the slot was taken under, so
        comparing the column would compare two different vocabularies.
        """
        status = row.get("admission")
        if status == "queued":
            raise AdmissionOrderError(
                f"row {child.row_id!r} is queued; it waits for admission to promote it rather "
                "than being launched"
            )
        if status not in HOLDING_ADMISSION_STATUSES:
            raise AdmissionOrderError(
                f"row {child.row_id!r} has admission status {status!r}; only a row holding a "
                f"matching reservation is launched, and a holding row is one of "
                f"{sorted(HOLDING_ADMISSION_STATUSES)}"
            )
        reservation = self.reservation_for(child.row_id)
        if reservation is None:
            raise AdmissionOrderError(
                f"row {child.row_id!r} is marked {status!r} and admission holds no reservation "
                "for it; launching would put an active child outside the host-wide bound"
            )
        state = str(reservation.get("state") or "")
        if state not in admission.HOLDING_STATES:
            raise AdmissionOrderError(
                f"row {child.row_id!r} holds a reservation in state {state!r}, which is not a "
                f"holding state ({sorted(admission.HOLDING_STATES)})"
            )
        stored = (
            str(reservation.get("vendor") or ""),
            str(reservation.get("work_shape") or ""),
            int(reservation.get("tokens_reserved") or 0),
        )
        wanted = (child.vendor, child.execution_class, child.tokens_max)
        if stored != wanted:
            raise AdmissionOrderError(
                f"row {child.row_id!r} holds a reservation for {stored} and the approved plan "
                f"names {wanted}; release and replan rather than launching under the wrong slot"
            )

    def _assert_route_custody(self, child: planning.PlannedChild) -> Any:
        """Refuse, before any side effect, when the launch would not be the approved one.

        The operator approved a vendor, a model, an effort, a scope, an integration mode and the
        landing that mode implies. Every one of those is compared here, against what this control
        flow can predict the launcher will do, because a comparison made after the native side
        effect is a report rather than a refusal.

        Two of them are checked and not merely carried:

        ``launch_child`` re-resolves model and effort from the work shape and runtime rather than
        accepting them, so an operator-approved override -- the one case where the approved values
        are deliberately not the policy values -- silently becomes the policy values at launch.

        ``GitLanding.provision`` decides the landing from ``spec.mutating`` alone and never sees
        the approved mode: it produces a branch worktree for a mutating child and the ambient
        checkout for a read-only one. An approved mode it cannot produce is therefore refused
        here rather than adapted into the nearest one it can, because "isolated more than the
        operator asked" is still a landing the operator did not approve and the register would
        record it as though they had.

        The permission posture is deliberately not a separate comparison.
        ``session_lifecycle.permission_argv`` is a pure function of the runtime, and the runtime
        is compared. A check that can never fail on its own reports coverage it does not have.
        """
        resolution = tier_resolver.resolve_for_runtime(child.execution_class, child.vendor)
        if (resolution.model, resolution.effort) != (child.model, child.effort):
            raise RouteDivergedError(
                f"row {child.row_id!r} was approved as {child.vendor} "
                f"{child.model}/{child.effort} and the launcher would resolve "
                f"{resolution.model}/{resolution.effort}; a substitution requires a new plan"
            )
        expected_mode = producible_landing_mode(child.integration_mode)
        if expected_mode != child.integration_mode:
            raise RouteDivergedError(
                f"row {child.row_id!r} was approved with integration mode "
                f"{child.integration_mode!r} and this control flow can only land "
                f"{sorted(PRODUCIBLE_INTEGRATION_MODES)}; launching it would run and record "
                f"{expected_mode!r} against an approval that said {child.integration_mode!r}. "
                "Re-plan the child with a mode that can be landed."
            )
        return resolution

    def _assert_launched_custody(
        self,
        child: planning.PlannedChild,
        resolution: Any,
        landing: session_lifecycle.Landing,
    ) -> None:
        """Compare what actually launched, and what the register now records, with the approval.

        The pre-launch check predicts; this one observes. Both exist because the prediction is
        made from this control flow's model of the launcher, and a model that has drifted from
        the launcher is exactly the failure the prediction cannot see.
        """
        if (resolution.model, resolution.effort) != (child.model, child.effort):
            raise RouteDivergedError(
                f"row {child.row_id!r} launched as {resolution.model}/{resolution.effort} "
                f"against an approved {child.model}/{child.effort}"
            )
        if landing.integration_mode != child.integration_mode:
            raise RouteDivergedError(
                f"row {child.row_id!r} landed as {landing.integration_mode!r} against an "
                f"approved {child.integration_mode!r}; the register would record a landing the "
                "operator did not approve"
            )
        # The approval names a mode, not a destination -- ``PlannedChild`` carries no destination
        # field, so there is nothing from the operator to compare this against. What there is:
        # this control flow's own deterministic naming rule (``GitLanding.provision`` names a
        # mutating child's branch by :func:`session_lifecycle.task_label`, and a read-only child
        # lands at the literal ``"none"``). A landing whose destination diverges from that rule
        # was produced by a provisioner this control flow does not recognise as its own, and
        # recording it would carry a destination nothing approved.
        expected_destination = (
            session_lifecycle.task_label(self.run_id, child.row_id)
            if child.integration_mode != "none"
            else "none"
        )
        if landing.destination != expected_destination:
            raise RouteDivergedError(
                f"row {child.row_id!r} landed at destination {landing.destination!r}, and this "
                f"control flow's own deterministic naming rule for it is "
                f"{expected_destination!r}; the register would record a destination nothing "
                "approved"
            )
        row = self.rows().get(child.row_id, {})
        recorded_scope = tuple(str(item) for item in row.get("scope") or ())
        actual = (
            str(row.get("vendor") or ""),
            str(row.get("model") or ""),
            str(row.get("effort") or ""),
            str(row.get("integration_mode") or ""),
            recorded_scope,
        )
        expected = (
            child.vendor,
            child.model,
            child.effort,
            child.integration_mode,
            tuple(child.scope),
        )
        if actual != expected:
            raise RouteDivergedError(
                f"row {child.row_id!r} records {actual} after launch against an approved "
                f"{expected}; the register would carry false provenance for cost and scope"
            )

    # ------------------------------------------------------------------ completion

    def attempt_for(self, row_id: str) -> Attempt:
        """The open attempt for one row, from memory or rebuilt from the durable record.

        Everything but the changed-paths baseline is either on the sealed receipt or on the
        register. The baseline is a snapshot taken at readiness and cannot be re-taken once the
        child has written, so it is persisted at dispatch -- and the receipt's digest over it is
        what makes reading it back safe.
        """
        cached = self._attempts.get(row_id)
        if cached is not None:
            return cached
        rows = self.rows()
        row = rows.get(row_id)
        if row is None:
            raise CompositionError(f"unknown child row {row_id!r}")
        receipt = completion.read_receipt(self.root, row_id, run_id=self.run_id)
        stored = row.get("changed_paths_baseline")
        if not isinstance(stored, Mapping):
            raise CompositionError(
                f"row {row_id!r} has a dispatch receipt but no recorded changed-paths baseline; "
                "the snapshot its receipt was sealed against cannot be re-taken after the child "
                "has written, so this attempt cannot be evaluated"
            )
        baseline = _baseline_from_mapping(stored)
        landing = session_lifecycle.Landing(
            cwd=Path(receipt.landing_cwd),
            integration_mode=receipt.integration_mode,
            destination=receipt.destination,
            base_commit=receipt.base_commit,
            ambient_root=(Path(receipt.ambient_root) if receipt.ambient_root else None),
        )
        spec = session_lifecycle.ChildSpec(
            run_id=receipt.run_id,
            row_id=receipt.row_id,
            runtime=receipt.runtime,
            work_shape=receipt.work_shape,
            instruction=str(row.get("task") or ""),
            scope=tuple(receipt.scope),
            mutating=receipt.mutating,
            workspace=self.workspace,
            readiness_timeout=self.readiness_timeout,
            environment_command=self.environment_command,
        )
        attempt = Attempt(spec, landing, baseline, receipt)
        self._attempts[row_id] = attempt
        return attempt

    def integrate_child(
        self,
        row_id: str,
        *,
        depth_sample: Any = None,
    ) -> completion.CompletionResult:
        """Consume a completion wake: settle, run the predicate inline, verify, record.

        The sentinel only wakes this. Nothing here trusts it as a completion verdict, the
        predicate runs in this process rather than in the mirror, and the whole chain runs before
        anything is closed.
        """
        try:
            attempt = self.attempt_for(row_id)
            if not isinstance(self.rows().get(row_id, {}).get("reap_fence"), Mapping):
                # A fenced row's tab is deliberately gone. Asking the vanished-child detector
                # about it would report this control flow's own closure as a fault, which is the
                # difference between "the session disappeared" and "I stopped it on purpose".
                session_lifecycle.assert_child_not_vanished(
                    self.root, row_id, run_id=self.run_id, herdr=self.herdr
                )
            result = completion.evaluate_completion(
                attempt.spec,
                attempt.landing,
                attempt.baseline,
                attempt.receipt,
                git=self.git,
                depth_sample=depth_sample,
            )
        except Exception as exc:
            self.record_step_failure("integration_failed", row_id, exc)
            raise
        _write_owned(
            self.root,
            row_id,
            {
                "post_verdict_observation": {
                    "digest": self._landing_digest(attempt),
                    "at": self.clock(),
                }
            },
            run_id=self.run_id,
        )
        self.run_log.append(
            "child_evaluated",
            row_id=row_id,
            verified=result.verified,
            reason=result.reason,
            artifact_digest=result.artifact_digest,
        )
        return result

    def _landing_drift(self, row_id: str, row: Mapping[str, Any]) -> str | None:
        """Whether a reaped child's landing still matches what was observed behind its fence."""
        recorded = row.get("post_verdict_observation")
        if not isinstance(recorded, Mapping) or not recorded.get("digest"):
            return (
                f"row {row_id!r} is reaped with no record of what its landing looked like when "
                "its producer was stopped"
            )
        try:
            current = self._landing_digest(self.attempt_for(row_id))
        except (CompositionError, completion.CompletionError) as exc:
            return f"row {row_id!r} landing could not be re-observed: {exc}"
        if current != recorded["digest"]:
            return (
                f"row {row_id!r} landing changed after the verdict that closed it; the change "
                "was never evaluated"
            )
        return None

    def _landing_digest(self, attempt: Attempt) -> str:
        """One comparable value for everything repository-visible in a child's landing."""
        return completion.baseline_digest(
            self.git.changed_paths_baseline(
                attempt.landing.cwd,
                base_commit=attempt.landing.base_commit,
                ambient_root=attempt.landing.ambient_root,
            )
        )

    def reap_child(self, row_id: str) -> ReapAuthorization:
        """Close a verified child, then release its slot and let admission promote the next one.

        The order is the whole point. Release before a recorded reap frees a slot for work that
        may still be running; a reap without a release makes the host bound a one-way ratchet in
        which every finished child permanently consumes a slot and queued work never starts.
        """
        try:
            row = self.rows().get(row_id, {})
            assert_forward_transition(row.get("phase"), "reaped", row_id=row_id)
            authorization = reap_authorization(self.root, row_id, run_id=self.run_id)
            self._assert_child_stopped_mutating(row_id)
            self._fence_producer(row_id)
            authorization = self._reobserve_behind_the_fence(row_id, authorization)
            session_lifecycle.reap_verified(self.root, row_id, run_id=self.run_id, herdr=self.herdr)
            reaped = self.rows().get(row_id, {}).get("phase")
            if reaped != "reaped":
                raise ReapAuthorizationError(
                    f"row {row_id!r} is {reaped!r} after the reap step; the slot is not released "
                    "until the register records the child closed"
                )
        except Exception as exc:
            self.record_step_failure("reap_refused", row_id, exc)
            raise
        try:
            promoted = admission.release_slot(self.root, row_id, run_id=self.run_id)
        except Exception as exc:
            # The child is closed and its slot is not free. That is the one-way ratchet in its
            # purest form, and the only thing worse than it happening is it happening quietly.
            self.record_step_failure("slot_release_failed", row_id, exc)
            raise
        self._attempts.pop(row_id, None)
        self.release_dispatch_claim(row_id)
        self.run_log.append(
            "child_reaped",
            row_id=row_id,
            nonce=authorization.nonce,
            artifact_digest=authorization.artifact_digest,
            promoted=promoted.row_id if promoted is not None else None,
        )
        return authorization

    def _assert_child_stopped_mutating(self, row_id: str) -> None:
        """The child must not still be writing when its tab is closed.

        The artifact itself is covered by :func:`reap_authorization`, which re-digests it. This
        covers everything else in the landing over the window between the recorded verdict and the
        reap -- a window nothing else observes at all. A child that kept working after it passed
        has produced changes nobody evaluated, and closing its tab is how those changes stop being
        recoverable. The comparison is against a durable observation taken at the verdict, so it
        survives a restart between the two steps.
        """
        attempt = self.attempt_for(row_id)
        recorded = self.rows().get(row_id, {}).get("post_verdict_observation")
        if not isinstance(recorded, Mapping) or not recorded.get("digest"):
            raise ReapAuthorizationError(
                f"row {row_id!r} carries no observation of its landing at the instant of its "
                "verdict; nothing has established that the child stopped"
            )
        current = self._landing_digest(attempt)
        if current != recorded["digest"]:
            raise ChildStillMutatingError(
                f"the landing for {row_id!r} changed after its verdict was recorded; the child "
                "had not stopped, and closing its tab now would discard whatever it did next"
            )

    def _fence_producer(self, row_id: str) -> None:
        """Stop the producer, so what is observed next cannot change while it is observed.

        Comparing a digest and then closing a tab as a separate step leaves a window in which the
        child is still running: it can write after the comparison and before the closure, and the
        row is then recorded reaped with that write never evaluated. A comparison cannot close
        that window, however carefully it is written, because the thing it compares is still
        moving. The only way to observe evidence that cannot change is to stop the thing that
        changes it first.

        The fence is written **before** the tab is closed, and that ordering is the whole reason
        this is a protocol rather than two calls. A crash between the two leaves a closed tab
        beside a live row, which the vanished-child detector reports as a fault; the fence record
        is what tells a coordinator coming back that the closure was deliberate and where in the
        sequence it stopped.

        The record and the closure are two different facts, and a retry must not treat the first
        as proof of the second. A crash -- or a control-plane failure -- strictly between writing
        the fence and the close call landing leaves the fence durable and the producer still
        running; returning early on a retry because the fence already exists would reap behind a
        tab nobody ever actually closed, the exact window this fence exists to remove. So a retry
        skips only the *write*, never the check: it always asks whether the current run-bound tab
        is still present and closes it if so, until that question answers no.

        Only a child that has already passed is fenced. A failing verdict never reaches here, so
        the operator keeps the live session in exactly the case where recovering a defective
        artifact from it is cheap.
        """
        row = self.rows().get(row_id, {})
        fence = row.get("reap_fence")
        tab_id = session_lifecycle.read_session_tab_id(
            self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
        )
        cwd = Path(completion.read_receipt(self.root, row_id, run_id=self.run_id).landing_cwd)
        if not isinstance(fence, Mapping):
            _write_owned(
                self.root,
                row_id,
                {
                    "reap_fence": {
                        "at": self.clock(),
                        "coordinator_id": self.coordinator_id,
                    }
                },
                run_id=self.run_id,
            )
            self.run_log.append("producer_fenced", row_id=row_id, tab_id=tab_id)
        if tab_id is not None:
            self.herdr.close_tab(tab_id, cwd=cwd)
            # A close request returning without raising is a request accepted, not an effect
            # observed: asking again is the only thing that tells the two apart, and only a "no"
            # here is the proof :meth:`_reobserve_behind_the_fence` and ``reap_verified`` are
            # allowed to build on.
            remaining = session_lifecycle.read_session_tab_id(
                self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
            )
            if remaining is not None:
                raise ChildStillMutatingError(
                    f"row {row_id!r}'s tab {remaining!r} was asked to close but is still present; "
                    "its producer is not confirmed stopped, so this reap is refused rather than "
                    "recorded"
                )
            self.run_log.append("producer_stop_confirmed", row_id=row_id, tab_id=tab_id)

    def _reobserve_behind_the_fence(
        self, row_id: str, authorization: ReapAuthorization
    ) -> ReapAuthorization:
        """Re-run the evidence chain now that nothing can change what it reads.

        Everything checked before the fence was checked against a moving target. This is the same
        check against a stopped one, and it is the answer that gets recorded: the landing digest
        and the artifact's own binding are taken again, and a disagreement refuses the reap rather
        than reporting it. The row stays non-terminal and the work stays on disk, which is the
        recoverable outcome; recording ``reaped`` would have made it the unrecoverable one.
        """
        attempt = self.attempt_for(row_id)
        recorded = self.rows().get(row_id, {}).get("post_verdict_observation")
        expected = recorded.get("digest") if isinstance(recorded, Mapping) else None
        behind_the_fence = self._landing_digest(attempt)
        if expected != behind_the_fence:
            raise ChildStillMutatingError(
                f"the landing for {row_id!r} changed between its verdict and the moment its "
                "producer was stopped; that change was never evaluated, and closing the row as "
                "verified would record a pass over work nobody read"
            )
        checked = reap_authorization(self.root, row_id, run_id=self.run_id)
        if checked.artifact_digest != authorization.artifact_digest:
            raise ChildStillMutatingError(
                f"the artifact for {row_id!r} digests differently once its producer is stopped; "
                "the evidence that authorised this reap is not the evidence on disk"
            )
        _write_owned(
            self.root,
            row_id,
            {
                "post_verdict_observation": {
                    "digest": behind_the_fence,
                    "at": self.clock(),
                    "behind_fence": True,
                }
            },
            run_id=self.run_id,
        )
        return checked

    def abandon_child(self, row_id: str, reason: str) -> None:
        """Stop pursuing a child on purpose, and record that it was on purpose.

        Abandoning frees the slot. It used to leave the run's spend permanently unknowable: a row
        that reached ``launching`` is a launched phase to the accounting contract, which fails
        closed for a metered vendor with no usage line, so one abandoned child stopped every
        remaining child from starting. That is only the right answer when the child might actually
        have spent something. When it never got a session at all, "it observed zero tokens" is a
        fact rather than an assumption, and this establishes it rather than assuming it: the row
        must never have carried a pane, and the launcher's own label discovery must not find a
        session running under this child's run-bound label.

        "No longer awaited" is what abandonment always establishes -- the operator's decision that
        this run stops pursuing this child, which is legitimate and useful on its own. It does not
        by itself mean "the producer stopped" or "its cost no longer counts": those are separate
        facts, and a row that might hold a session gets them the same way a reap does, by closing
        its tab and asking the substrate again rather than assuming the request worked. A child
        whose producer cannot be confirmed stopped keeps failing closed on spend and keeps
        blocking retirement, exactly as if nobody had decided anything about it, because nothing
        about "no longer awaited" makes either of those questions answered.
        """
        row = self.rows().get(row_id, {})
        never_ran = self._assert_child_never_ran(row_id)
        producer_stopped = never_ran or self._stop_abandoned_producer(row_id, row)
        _write_owned(
            self.root,
            row_id,
            {
                "coordinator_disposition": {
                    "state": "abandoned",
                    "reason": reason,
                    "at": self.clock(),
                    "never_ran": never_ran,
                    "producer_stopped": producer_stopped,
                }
            },
            run_id=self.run_id,
        )
        if never_ran:
            accounting.record_observed_tokens(
                self.root,
                row_id,
                0,
                run_id=self.run_id,
                kind=accounting.USAGE_KIND_CUMULATIVE,
            )
        admission.abandon_slot(self.root, row_id, run_id=self.run_id)
        self.release_dispatch_claim(row_id)
        self.run_log.append(
            "child_abandoned",
            row_id=row_id,
            reason=reason,
            never_ran=never_ran,
            producer_stopped=producer_stopped,
        )

    def _assert_child_never_ran(self, row_id: str) -> bool:
        """Whether this child demonstrably never got a session, from evidence rather than hope."""
        row = self.rows().get(row_id, {})
        if isinstance(row.get("tokens_observed"), (int, float)) and not isinstance(
            row.get("tokens_observed"), bool
        ):
            return False
        return not self._native_session_may_exist(row_id, row)

    def _stop_abandoned_producer(self, row_id: str, row: Mapping[str, Any]) -> bool:
        """Close a possibly-live producer and prove it is gone, or report that it is not.

        Reached only once :meth:`_assert_child_never_ran` has already failed to prove the row
        never held a session, so a live pane is a real possibility here, not an edge case. This
        asks the same substrate a reap asks (:meth:`_fence_producer`) rather than trusting a close
        request's successful return: a tab that is still present after asking it to close is not
        stopped, whatever the request itself reported. Returns whether absence was confirmed --
        never a guess, because a caller that cannot tell must keep failing closed the same way an
        unmetered vendor's silence already does.
        """
        try:
            tab_id = session_lifecycle.read_session_tab_id(
                self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
            )
        except session_lifecycle.SessionLifecycleError:
            return False
        if tab_id is None:
            return not self._native_session_may_exist(row_id, row)
        self.herdr.close_tab(tab_id, cwd=self.root)
        try:
            return (
                session_lifecycle.read_session_tab_id(
                    self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
                )
                is None
            )
        except session_lifecycle.SessionLifecycleError:
            return False

    # ------------------------------------------------------------------ retirement

    def outstanding_writers(self) -> dict[str, str]:
        """Everything that could still write this run's register, named.

        The mirror is on this list. It is excluded from the run's spend and from the
        work-in-progress bound because it is not one of the outcome's children, but it is a live
        session that writes its own register columns, and retiring a run underneath it is how a
        late write recreates a live document beside the archive.
        """
        outstanding: dict[str, str] = {}
        running = self.running_subscriber()
        if running is not None:
            outstanding["subscriber"] = (
                f"a subscriber of this run (process {running.get('pid')}, started by coordinator "
                f"{running.get('coordinator_id')}) is still holding the event stream"
            )
        rows = self.rows()
        for row_id, _row in sorted(mirror_module.find_mirror_rows(rows).items()):
            try:
                observed_state = session_lifecycle.read_session_observed_state(
                    self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
                )
            except session_lifecycle.SessionLifecycleError as exc:
                outstanding[f"mirror:{row_id}"] = (
                    f"the terminal multiplexer could not answer whether the mirror is live: {exc}"
                )
                continue
            if observed_state is not None:
                outstanding[f"mirror:{row_id}"] = (
                    f"the mirror is {observed_state!r} and has not been closed"
                )
        for row_id, row in sorted(self.child_rows().items()):
            phase = row.get("phase")
            if phase == "reaped":
                continue
            if is_abandoned(row):
                if _producer_confirmed_stopped(row):
                    continue
                outstanding[row_id] = (
                    f"child is {phase!r}, abandoned, but its producer was never confirmed stopped"
                )
                continue
            outstanding[row_id] = f"child is {phase!r} and was not deliberately abandoned"
        with admission.admission_locked():
            doc = register_store._read_register_unlocked(self.run_id)
            reservations = admission._admission_doc(doc)["reservations"]
            queue = admission._admission_doc(doc)["queue"]
        for row_id in sorted(reservations):
            outstanding[f"reservation:{row_id}"] = "a reservation is still held"
        for entry in queue:
            if isinstance(entry, Mapping) and entry.get("row_id"):
                outstanding[f"queued:{entry['row_id']}"] = "a queued child is still waiting"
        return outstanding

    def retire(self) -> Path | None:
        """Stop every writer, free every slot, then archive the run as one generation."""
        outstanding = self.outstanding_writers()
        if outstanding:
            raise RetirementOrderError(
                "the run still has open writers or reservations and cannot be retired: "
                + "; ".join(f"{key} ({value})" for key, value in sorted(outstanding.items()))
            )
        # Seal the gate result while the register and the run key still exist. Retirement is what
        # removes every input the criteria read, so a receipt computed afterwards is computed over
        # nothing. Sealing here means the documented order cannot produce a vacuous pass whichever
        # way round the operator calls the two.
        if self.sealed_acceptance_receipt() is None:
            self.acceptance_receipt()
        archive = register_store.retire_run(self.root, self.run_id)
        forget_approved_plan(self.run_id)
        forget_subscriber_record(self.run_id)
        self._subscriber_handle = None
        self._installed_subscriptions = ()
        self.run_log.append("run_retired", archive=str(archive) if archive else None)
        return archive

    def stop_writers(self) -> dict[str, str]:
        """Stop the subscriber and close the mirror, so retirement has something to succeed at.

        A stop *requested* and a stop *confirmed* are different facts, and only the second is
        safe to act on: forgetting the durable record, or the in-memory handle, before the
        process is actually gone leaves a live writer this coordinator can no longer even find,
        which is worse than the divergence it would have reported honestly. So every stop here is
        followed by a liveness re-check, and the record or handle is discarded only when that
        re-check says the writer is gone; a writer that would not die stays visible to
        :meth:`outstanding_writers`, and retirement refuses on it rather than archiving beside it.
        """
        stopped: dict[str, str] = {}
        if self._subscriber_handle is not None:
            self.supervisor.stop(self._subscriber_handle)
            if self.supervisor.is_alive(self._subscriber_handle):
                stopped["subscriber"] = "stop requested but the process is still alive"
            else:
                self._subscriber_handle = None
                stopped["subscriber"] = "stopped"
        # A subscriber this coordinator did not start is still this run's writer. Stopping only
        # what this object happens to hold is how retirement completed while a prior generation's
        # subscriber was alive and able to write the live register back beside the archive. The
        # same is true of a subscriber this run started but never durably recorded -- resolved the
        # same way :meth:`running_subscriber` resolves it, so what gets stopped here is exactly
        # what would otherwise block retirement.
        recorded = self._resolve_subscriber_record()
        signature = self._subscriber_signature()
        if recorded is not None:
            if self.supervisor.is_record_alive(recorded, signature=signature):
                self.supervisor.stop_record(recorded)
                if self.supervisor.is_record_alive(recorded, signature=signature):
                    stopped[f"subscriber:{recorded.get('pid')}"] = (
                        "stop requested from the durable record but the process is still alive"
                    )
                else:
                    stopped[f"subscriber:{recorded.get('pid')}"] = "stopped from the durable record"
                    forget_subscriber_record(self.run_id)
            else:
                forget_subscriber_record(self.run_id)
        self._installed_subscriptions = ()
        rows = self.rows()
        for row_id, _row in sorted(mirror_module.find_mirror_rows(rows).items()):
            try:
                tab_id = session_lifecycle.read_session_tab_id(
                    self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
                )
            except session_lifecycle.SessionLifecycleError as exc:
                stopped[row_id] = f"the terminal multiplexer could not answer: {exc}"
                continue
            if tab_id is not None:
                self.herdr.close_tab(tab_id, cwd=self.root)
            # A close request returning without raising is a request accepted, not an effect
            # observed -- the same distinction the reap fence and the abandon path already draw
            # for a child's tab. Asking again is the only thing that tells them apart, and only a
            # "no" here is what :meth:`outstanding_writers` is allowed to read as this writer
            # being gone; the documented shutdown order (stop writers, then retire) depends on
            # this column meaning what it claims.
            try:
                still_present = (
                    session_lifecycle.read_session_tab_id(
                        self.herdr, root=self.root, run_id=self.run_id, row_id=row_id
                    )
                    is not None
                )
            except session_lifecycle.SessionLifecycleError as exc:
                stopped[row_id] = f"close requested but confirmation failed: {exc}"
                continue
            if still_present:
                stopped[row_id] = "close requested but the tab is still present"
                continue
            stopped[row_id] = "closed"
        self.run_log.append("writers_stopped", stopped=stopped)
        return stopped

    # ------------------------------------------------------------------ acceptance

    @property
    def receipt_path(self) -> Path:
        return self.evidence_dir / "acceptance-receipt.json"

    def is_retired(self) -> bool:
        """Whether this run's live register is gone, which is what retirement leaves behind."""
        return not register_store.register_path(self.run_id).exists()

    def sealed_acceptance_receipt(self) -> dict[str, Any] | None:
        """The receipt written while the evidence still existed, or ``None``."""
        if not self.receipt_path.exists():
            return None
        try:
            stored = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return dict(stored) if isinstance(stored, Mapping) else None

    def acceptance_receipt(self) -> AcceptanceReceipt:
        """Compute and seal the Phase 1 pass criteria from the durable record.

        Every criterion is derived from the register, the sealed receipts and the two ledgers.
        None of them is a claim this module makes about itself.

        **It refuses to answer once the evidence is gone.** Retirement archives and deletes the
        live register and the run key, and every criterion here reads the live register. Computed
        after retirement this returned a pass: no rows means no child was lost and none was falsely
        completed, and the spend total of nothing is zero. A gate that passes by having nothing
        left to check is worse than a gate that fails, so this refuses instead and points at the
        receipt sealed while the evidence still existed.
        """
        if self.is_retired():
            sealed = self.sealed_acceptance_receipt()
            raise AcceptanceOrderError(
                f"run {self.run_id!r} is retired: its live register and run key are gone, so "
                "every criterion here would be computed over nothing and would pass. "
                + (
                    f"The receipt sealed before retirement is at {self.receipt_path}."
                    if sealed is not None
                    else "No receipt was sealed before retirement, so this run has no gate result."
                )
            )
        rows = self.child_rows()
        detail: dict[str, Any] = {}

        lost = []
        for row_id, row in sorted(rows.items()):
            if row.get("phase") != "reaped" and not is_abandoned(row):
                lost.append(row_id)
        detail["unaccounted_children"] = lost

        launches: dict[str, list[str]] = {}
        for entry in self.run_log.entries():
            if entry.get("kind") == "child_launched":
                launches.setdefault(str(entry.get("row_id")), []).append(str(entry.get("pane_id")))
        duplicated = {row_id: panes for row_id, panes in launches.items() if len(set(panes)) > 1}
        detail["duplicate_launches"] = duplicated

        false_completion = []
        for row_id, row in sorted(rows.items()):
            if row.get("phase") != "reaped":
                continue
            try:
                reap_authorization(self.root, row_id, run_id=self.run_id)
            except ReapAuthorizationError as exc:
                false_completion.append({"row_id": row_id, "detail": str(exc)})
                continue
            # The evidence chain proves the *artifact*. A child that kept writing elsewhere in its
            # landing after its verdict produced changes nobody evaluated, and a receipt that only
            # re-checks the artifact reports that run as clean.
            drift = self._landing_drift(row_id, row)
            if drift is not None:
                false_completion.append({"row_id": row_id, "detail": drift})
        detail["unauthorised_reaps"] = false_completion

        answered_while_busy = [
            entry
            for entry in self.operator_log.entries()
            if entry.get("kind") == "operator_question"
            and entry.get("disposition") == "answered"
            and entry.get("mirror_request_outstanding") is True
        ]
        detail["answered_while_mirror_busy"] = len(answered_while_busy)
        detail["parked_questions"] = list(self.open_operator_questions())

        spend: float | None
        unresolved: list[str] = []
        absent_launches: set[str] = set()
        for row_id, row in sorted(rows.items()):
            if row.get("phase") != "launching" or is_abandoned(row):
                continue
            if self._native_session_may_exist(row_id, row):
                unresolved.append(row_id)
            else:
                absent_launches.add(row_id)
        if unresolved:
            spend = None
            detail["spend_error"] = (
                f"rows {unresolved} carry launch intent and the live owner could not establish "
                "that no session exists; the run's spend is not yet knowable"
            )
        else:
            try:
                spend = accounting.run_actual_tokens(
                    self.root, run_id=self.run_id, exclude_row_ids=absent_launches
                )
            except accounting.AccountingError as exc:
                spend = None
                detail["spend_error"] = str(exc)

        receipt = AcceptanceReceipt(
            run_id=self.run_id,
            no_child_lost=not lost,
            no_duplicate_launched=not duplicated,
            no_false_completion=not false_completion,
            operator_answered_while_mirror_busy=bool(answered_while_busy),
            spend_recorded=spend is not None,
            spend_tokens=spend,
            detail=detail,
        )
        path = self.evidence_dir / "acceptance-receipt.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        register_store._atomic_write_json(path, receipt.to_mapping())
        return receipt


__all__ = [
    "AcceptanceOrderError",
    "AcceptanceReceipt",
    "AdmissionOrderError",
    "ApprovalError",
    "ArtifactAssignmentError",
    "Attempt",
    "COLUMN_OWNERSHIP",
    "ChildStillMutatingError",
    "ColumnOwnershipError",
    "CompositionError",
    "ConcurrentAttemptError",
    "Coordinator",
    "DispatchClaim",
    "DispatchClaimError",
    "LaunchReport",
    "Ledger",
    "OWNED_COLUMNS",
    "OperatorChannel",
    "OperatorContext",
    "OperatorDisposition",
    "Orphan",
    "OrphanScan",
    "OutcomeArgumentError",
    "OutcomeRequest",
    "PRODUCIBLE_INTEGRATION_MODES",
    "ParkQuestionError",
    "PhaseOrderError",
    "ReapAuthorization",
    "ReapAuthorizationError",
    "ReconciliationReport",
    "RetirementOrderError",
    "RouteDivergedError",
    "SpendCeilingError",
    "SpendHaltError",
    "SpendUnobservableError",
    "SubprocessSubscriberSupervisor",
    "SubscriberLivenessUnknownError",
    "SubscriberSupervisor",
    "SubscriptionSetError",
    "SupervisionReport",
    "UnconfirmedDispatchError",
    "UnsupportedWorkShapeError",
    "artifact_relpath",
    "assert_forward_transition",
    "assert_subscription_set",
    "forget_approved_plan",
    "host_reservations",
    "is_terminal",
    "load_approved_plan",
    "parse_outcome",
    "persist_approved_plan",
    "plan_from_mapping",
    "plan_to_mapping",
    "producible_landing_mode",
    "reap_authorization",
    "subscriber_argv",
    "subscriptions_for",
]
