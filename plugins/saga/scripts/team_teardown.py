#!/usr/bin/env python3
"""Non-skippable team-run teardown: closed event family, projection, terminal driver (#358).

Composes the #356 fleet broker (live register-on-spawn ownership plus the owner-admission
closing fence) with the #351 hash-chained ``run_fact.v1`` ledger (append-only history) and
#357 confirmed liveness decisions. This module adds **no** second registry, mutable status
store, TTL clock, heartbeat detector, or reaper decision engine (R1): live ownership is the
broker, history is the ledger, and every view here is projected from one chain-verified
ledger snapshot plus one lock-consistent broker snapshot. The two stores are **not**
transactionally atomic — action-time identity rechecks close that gap (R4).

Event family (``kind=teardown``, closed — R9): ``run-opened``, ``teardown-intent``,
``resource-attempt``, ``resource-result``, ``recovery-observation``, ``teardown-complete``.
Transition validation and append share the ledger's exclusive write lock via
``run_ledger.append_fact_built_atomic``. Facts carry bounded identity and evidence digests,
never prompts, message text, or stdout/stderr — and never a mutable open/closed summary.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_commons_shim  # noqa: E402
import run_ledger  # noqa: E402

TEARDOWN_SCHEMA = "team_teardown.v1"

EVENTS = frozenset(
    {
        "run-opened",
        "teardown-intent",
        "resource-attempt",
        "resource-result",
        "recovery-observation",
        "teardown-complete",
    }
)
TERMINAL_REASONS = frozenset({"success", "hard-fail", "operator-abort", "andon", "recovered-crash"})
DISPOSITIONS = frozenset({"released", "already-absent", "retained", "failed"})
# A finally-disposed action key converges: repeated reclaim may not act on it again (R4).
FINAL_DISPOSITIONS = frozenset({"released", "already-absent"})
ACTION_KINDS = frozenset({"resident-stop", "process-stop", "lease-release", "worktree-sweep"})
RESOURCE_KINDS = frozenset(
    {"resident-agent", "owned-subprocess", "outcome-worktree", "provisional-lease"}
)
# The subprocess stop policy is recorded on the broker lease at registration time (trusted
# store, spawn-time provenance) — never taken from caller prose at action time (R8).
SUBPROCESS_TERM_ONLY = "owned-subprocess:term-only"
SUBPROCESS_TERM_THEN_KILL = "owned-subprocess:term-then-kill"

_MAX_TEXT = 256
_MAX_EVIDENCE_REFS = 16


class TeardownError(ValueError):
    """A malformed teardown event, a refused transition, or corrupt decision input."""


class TeardownConflictError(TeardownError):
    """An event conflicts with an already-recorded event of the same identity."""


class _DuplicateEvent(Exception):  # noqa: N818 - a replay sentinel, not an error surface
    """Internal: the identical event already exists — idempotent replay, no append."""

    def __init__(self, existing: dict[str, Any]) -> None:
        self.existing = existing


def _bounded_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_TEXT:
        raise TeardownError(f"{name} must be a non-empty string of at most {_MAX_TEXT} chars")
    return value


def _sha256_hex(value: Any, name: str) -> str:
    text = _bounded_text(value, name)
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise TeardownError(f"{name} must be a lowercase sha256 hex digest")
    return text


def _evidence_refs(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise TeardownError("evidence_refs must be a list of bounded strings")
    if len(value) > _MAX_EVIDENCE_REFS:
        raise TeardownError(f"evidence_refs is bounded to {_MAX_EVIDENCE_REFS} entries")
    return [_bounded_text(item, "evidence_ref") for item in value]


def new_team_run_id() -> str:
    """A bounded, collision-resistant team run identity (also the broker owner_id)."""

    return f"team-run-{uuid.uuid4()}"


def action_key(team_run_id: str, resource_id: str, generation: str, action: str) -> str:
    """The stable idempotency key for one logical resource action (R2).

    Derived from trusted identity only — never prompts, paths, environment, or wall time.
    """

    payload = json.dumps(
        {
            "team_run_id": _bounded_text(team_run_id, "team_run_id"),
            "resource_id": _bounded_text(resource_id, "resource_id"),
            "generation": _bounded_text(generation, "generation"),
            "action": _bounded_text(action, "action"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def intent_id_for(team_run_id: str, terminal_reason: str) -> str:
    """Deterministic intent identity: repeated physical B8 entry converges to one intent (R3)."""

    if terminal_reason not in TERMINAL_REASONS:
        raise TeardownError(
            f"terminal_reason must be one of {sorted(TERMINAL_REASONS)}; found {terminal_reason!r}"
        )
    payload = f"{_bounded_text(team_run_id, 'team_run_id')}|{terminal_reason}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- event builders


def build_run_opened(
    *,
    subplot_id: str,
    at: str,
    team_run_id: str,
    owner_id: str,
    session_id: str,
    root_sha256: str,
) -> dict[str, Any]:
    return run_ledger.build_fact(
        "teardown",
        subplot_id=_bounded_text(subplot_id, "subplot_id"),
        at=at,
        event="run-opened",
        team_run_id=_bounded_text(team_run_id, "team_run_id"),
        owner_id=_bounded_text(owner_id, "owner_id"),
        session_id=_bounded_text(session_id, "session_id"),
        root_sha256=_sha256_hex(root_sha256, "root_sha256"),
    )


def build_teardown_intent(
    *,
    subplot_id: str,
    at: str,
    team_run_id: str,
    terminal_reason: str,
    close_generation: int,
) -> dict[str, Any]:
    if terminal_reason not in TERMINAL_REASONS:
        raise TeardownError(
            f"terminal_reason must be one of {sorted(TERMINAL_REASONS)}; found {terminal_reason!r}"
        )
    if not isinstance(close_generation, int) or close_generation < 1:
        raise TeardownError("close_generation must be a positive integer")
    return run_ledger.build_fact(
        "teardown",
        subplot_id=_bounded_text(subplot_id, "subplot_id"),
        at=at,
        event="teardown-intent",
        team_run_id=_bounded_text(team_run_id, "team_run_id"),
        intent_id=intent_id_for(team_run_id, terminal_reason),
        terminal_reason=terminal_reason,
        close_generation=close_generation,
    )


def build_resource_attempt(
    *,
    subplot_id: str,
    at: str,
    team_run_id: str,
    intent_id: str,
    resource_id: str,
    resource_kind: str,
    generation: str,
    action: str,
) -> dict[str, Any]:
    if resource_kind not in RESOURCE_KINDS:
        raise TeardownError(
            f"resource_kind must be one of {sorted(RESOURCE_KINDS)}; found {resource_kind!r}"
        )
    if action not in ACTION_KINDS:
        raise TeardownError(f"action must be one of {sorted(ACTION_KINDS)}; found {action!r}")
    return run_ledger.build_fact(
        "teardown",
        subplot_id=_bounded_text(subplot_id, "subplot_id"),
        at=at,
        event="resource-attempt",
        team_run_id=_bounded_text(team_run_id, "team_run_id"),
        intent_id=_sha256_hex(intent_id, "intent_id"),
        action_key=action_key(team_run_id, resource_id, generation, action),
        resource_id=_bounded_text(resource_id, "resource_id"),
        resource_kind=resource_kind,
        generation=_bounded_text(generation, "generation"),
        action=action,
    )


def build_resource_result(
    *,
    subplot_id: str,
    at: str,
    team_run_id: str,
    action_key_value: str,
    disposition: str,
    evidence_refs: Sequence[str],
    reason_code: str = "",
) -> dict[str, Any]:
    if disposition not in DISPOSITIONS:
        raise TeardownError(
            f"disposition must be one of {sorted(DISPOSITIONS)}; found {disposition!r}"
        )
    fields: dict[str, Any] = {
        "event": "resource-result",
        "team_run_id": _bounded_text(team_run_id, "team_run_id"),
        "action_key": _sha256_hex(action_key_value, "action_key"),
        "disposition": disposition,
        "evidence_refs": _evidence_refs(list(evidence_refs)),
    }
    if reason_code:
        fields["reason_code"] = _bounded_text(reason_code, "reason_code")
    return run_ledger.build_fact(
        "teardown",
        subplot_id=_bounded_text(subplot_id, "subplot_id"),
        at=at,
        **fields,
    )


def build_recovery_observation(
    *,
    subplot_id: str,
    at: str,
    team_run_id: str,
    observed_open: int,
    actions_taken: int,
    reason_code: str,
) -> dict[str, Any]:
    if not isinstance(observed_open, int) or observed_open < 0:
        raise TeardownError("observed_open must be a non-negative integer")
    if not isinstance(actions_taken, int) or actions_taken < 0:
        raise TeardownError("actions_taken must be a non-negative integer")
    return run_ledger.build_fact(
        "teardown",
        subplot_id=_bounded_text(subplot_id, "subplot_id"),
        at=at,
        event="recovery-observation",
        team_run_id=_bounded_text(team_run_id, "team_run_id"),
        observed_open=observed_open,
        actions_taken=actions_taken,
        reason_code=_bounded_text(reason_code, "reason_code"),
    )


def build_teardown_complete(
    *,
    subplot_id: str,
    at: str,
    team_run_id: str,
    intent_id: str,
    close_generation: int,
    released_count: int,
    already_absent_count: int,
) -> dict[str, Any]:
    if not isinstance(close_generation, int) or close_generation < 1:
        raise TeardownError("close_generation must be a positive integer")
    for name, value in (
        ("released_count", released_count),
        ("already_absent_count", already_absent_count),
    ):
        if not isinstance(value, int) or value < 0:
            raise TeardownError(f"{name} must be a non-negative integer")
    return run_ledger.build_fact(
        "teardown",
        subplot_id=_bounded_text(subplot_id, "subplot_id"),
        at=at,
        event="teardown-complete",
        team_run_id=_bounded_text(team_run_id, "team_run_id"),
        intent_id=_sha256_hex(intent_id, "intent_id"),
        close_generation=close_generation,
        released_count=released_count,
        already_absent_count=already_absent_count,
    )


# --------------------------------------------------------------------------- locked transitions


def _teardown_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(rec) for rec in records if rec.get("kind") == "teardown"]


def _run_records(records: Sequence[Mapping[str, Any]], team_run_id: str) -> list[dict[str, Any]]:
    return [rec for rec in _teardown_records(records) if rec.get("team_run_id") == team_run_id]


def _without_volatile(fact: Mapping[str, Any]) -> dict[str, Any]:
    """The identity-bearing content of a fact — chain fields and timestamp excluded."""

    return {k: v for k, v in fact.items() if k not in ("prev_hash", "this_hash", "at")}


def _last_result_by_action(
    run_records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for rec in run_records:
        if rec.get("event") == "resource-result":
            results[str(rec.get("action_key"))] = dict(rec)
    return results


def _attempts_by_action(
    run_records: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    attempts: dict[str, list[dict[str, Any]]] = {}
    for rec in run_records:
        if rec.get("event") == "resource-attempt":
            attempts.setdefault(str(rec.get("action_key")), []).append(dict(rec))
    return attempts


def _validate_transition(existing: Sequence[Mapping[str, Any]], fact: Mapping[str, Any]) -> None:
    """Refuse an event whose transition is invalid against the verified snapshot (R9).

    Raises :class:`_DuplicateEvent` for an identical replay (idempotent),
    :class:`TeardownConflictError` for a conflicting duplicate, and
    :class:`TeardownError` for an ordering violation.
    """

    event = fact.get("event")
    if event not in EVENTS:
        raise TeardownError(f"unknown teardown event {event!r}")
    run_id = str(fact.get("team_run_id"))
    run = _run_records(existing, run_id)
    opened = [rec for rec in run if rec.get("event") == "run-opened"]
    completes = [rec for rec in run if rec.get("event") == "teardown-complete"]

    def _replay_or_conflict(matching: Sequence[Mapping[str, Any]]) -> None:
        for rec in matching:
            if _without_volatile(rec) == _without_volatile(fact):
                raise _DuplicateEvent(dict(rec))
        if matching:
            raise TeardownConflictError(
                f"{event} for run {run_id!r} conflicts with an already-recorded event "
                "of the same identity"
            )

    if event == "run-opened":
        _replay_or_conflict(opened)
        return
    if not opened:
        raise TeardownError(f"{event} requires a prior run-opened for run {run_id!r}")

    if event == "recovery-observation":
        # Observations are always appendable for an opened run — they record honesty,
        # including "nothing was safe to reclaim", even after completion.
        return

    if completes and event != "teardown-complete":
        raise TeardownError(
            f"run {run_id!r} already recorded teardown-complete; {event} is refused"
        )

    if event == "teardown-intent":
        same_intent = [
            rec
            for rec in run
            if rec.get("event") == "teardown-intent"
            and rec.get("intent_id") == fact.get("intent_id")
        ]
        _replay_or_conflict(same_intent)
        return

    intents = {str(rec.get("intent_id")) for rec in run if rec.get("event") == "teardown-intent"}
    if event == "resource-attempt":
        if str(fact.get("intent_id")) not in intents:
            raise TeardownError(
                f"resource-attempt requires a recorded teardown-intent for run {run_id!r}"
            )
        key = str(fact.get("action_key"))
        last = _last_result_by_action(run).get(key)
        if last is not None and last.get("disposition") in FINAL_DISPOSITIONS:
            raise TeardownError(
                f"action {key} already reached final disposition "
                f"{last.get('disposition')!r}; repeated reclaim must not act again"
            )
        # An identical replay dedups; a differing attempt (e.g. under a recovery intent
        # after a failed result) is a legitimate new allocation, never a conflict.
        for rec in _attempts_by_action(run).get(key, []):
            if _without_volatile(rec) == _without_volatile(fact):
                raise _DuplicateEvent(dict(rec))
        return

    if event == "resource-result":
        key = str(fact.get("action_key"))
        attempts = _attempts_by_action(run).get(key, [])
        if not attempts:
            raise TeardownError(
                f"resource-result requires a prior resource-attempt for action {key}"
            )
        for rec in run:
            if (
                rec.get("event") == "resource-result"
                and str(rec.get("action_key")) == key
                and _without_volatile(rec) == _without_volatile(fact)
            ):
                raise _DuplicateEvent(dict(rec))
        last = _last_result_by_action(run).get(key)
        if last is not None and last.get("disposition") in FINAL_DISPOSITIONS:
            raise TeardownError(
                f"action {key} already reached final disposition {last.get('disposition')!r}"
            )
        return

    if event == "teardown-complete":
        _replay_or_conflict(completes)
        if str(fact.get("intent_id")) not in intents:
            raise TeardownError(
                f"teardown-complete requires its teardown-intent for run {run_id!r}"
            )
        results = _last_result_by_action(run)
        blocked = sorted(
            key for key, rec in results.items() if rec.get("disposition") not in FINAL_DISPOSITIONS
        )
        if blocked:
            raise TeardownError(
                f"teardown-complete refused: {len(blocked)} action(s) remain "
                f"retained/failed for run {run_id!r}"
            )
        dangling = sorted(key for key in _attempts_by_action(run) if key not in results)
        if dangling:
            raise TeardownError(
                f"teardown-complete refused: {len(dangling)} attempt(s) have no result "
                f"for run {run_id!r}"
            )
        return

    raise TeardownError(f"unhandled teardown event {event!r}")  # pragma: no cover


def append_teardown_event(ledger: run_ledger.RunLedger, fact: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the transition and append under the ledger's one exclusive lock (R9).

    An identical replay returns the existing record without appending (idempotent); a
    conflicting duplicate or an ordering violation raises. The returned record carries the
    chain fields of whichever record now represents the event.
    """

    if fact.get("kind") != "teardown":
        raise TeardownError("append_teardown_event only accepts kind=teardown facts")

    def _builder(snapshot: run_ledger.LedgerSnapshot) -> dict[str, Any]:
        _validate_transition(snapshot.records, fact)
        return dict(fact)

    try:
        return run_ledger.append_fact_built_atomic(ledger, _builder)
    except _DuplicateEvent as duplicate:
        return duplicate.existing


# --------------------------------------------------------------------------- decision input


@dataclass(frozen=True)
class DecisionInput:
    """One immutable decision input: a chain-verified ledger view + one broker snapshot.

    The two reads are lock-consistent individually, not atomic across stores (R4) —
    consumers must recheck identity at action time.
    """

    ledger_records: tuple[dict[str, Any], ...]
    broker_view: dict[str, Any]


def read_decision_input(ledger: run_ledger.RunLedger, broker: Any) -> DecisionInput:
    snapshot = run_ledger.read_snapshot(ledger)
    if not snapshot.report.ok:
        raise TeardownError(
            f"refusing decisions on a broken run-fact chain: {snapshot.report.reason}"
        )
    try:
        view = broker.inspect()
    except Exception as exc:
        raise TeardownError(f"broker snapshot unavailable or corrupt: {exc}") from exc
    if not isinstance(view, dict):
        raise TeardownError("broker inspect() returned a non-object snapshot")
    return DecisionInput(
        ledger_records=tuple(dict(rec) for rec in snapshot.records),
        broker_view=view,
    )


def _classify_lease(lease: Mapping[str, Any]) -> tuple[str, str]:
    """Map one broker lease to its (resource_kind, action) per the resource action matrix."""

    pool = lease.get("pool")
    if pool == "worktree":
        return "outcome-worktree", "worktree-sweep"
    agent_type = str(lease.get("agent_type") or "")
    if agent_type in (SUBPROCESS_TERM_ONLY, SUBPROCESS_TERM_THEN_KILL):
        return "owned-subprocess", "process-stop"
    if lease.get("agent_id"):
        return "resident-agent", "resident-stop"
    return "provisional-lease", "lease-release"


def _owned_leases(view: Mapping[str, Any], owner_id: str) -> list[dict[str, Any]]:
    leases = view.get("leases")
    if not isinstance(leases, list):
        raise TeardownError("broker snapshot has no lease list")
    return [dict(lease) for lease in leases if lease.get("owner_id") == owner_id]


def project(decision: DecisionInput, team_run_id: str) -> dict[str, Any]:
    """The derived ``team_teardown.v1`` terminal contract — never a stored summary (R9)."""

    run = _run_records(decision.ledger_records, team_run_id)
    opened = [rec for rec in run if rec.get("event") == "run-opened"]
    if not opened:
        raise TeardownError(f"unknown team run {team_run_id!r}: no run-opened fact")
    owner_id = str(opened[0].get("owner_id"))
    intents = [rec for rec in run if rec.get("event") == "teardown-intent"]
    completes = [rec for rec in run if rec.get("event") == "teardown-complete"]
    results = _last_result_by_action(run)
    attempts = _attempts_by_action(run)

    open_leases = _owned_leases(decision.broker_view, owner_id)
    resources: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for lease in open_leases:
        kind, action = _classify_lease(lease)
        resource_id = str(lease.get("lease_id"))
        generation = f"{lease.get('fencing_sequence')}"
        key = action_key(team_run_id, resource_id, generation, action)
        last = results.get(key)
        resources.append(
            {
                "resource_id": resource_id,
                "generation": generation,
                "kind": kind,
                "owner_ref": owner_id,
                "action": action,
                "disposition": str(last.get("disposition")) if last else "open",
                "evidence_refs": list(last.get("evidence_refs", [])) if last else [],
            }
        )
        seen_ids.add(key)
    for key, attempt_list in attempts.items():
        if key in seen_ids:
            continue
        attempt = attempt_list[-1]
        last = results.get(key)
        resources.append(
            {
                "resource_id": str(attempt.get("resource_id")),
                "generation": str(attempt.get("generation")),
                "kind": str(attempt.get("resource_kind")),
                "owner_ref": owner_id,
                "action": str(attempt.get("action")),
                "disposition": str(last.get("disposition")) if last else "attempted",
                "evidence_refs": list(last.get("evidence_refs", [])) if last else [],
            }
        )

    dispositions = [res["disposition"] for res in resources]
    open_count = len(open_leases)
    projection = {
        "schema": TEARDOWN_SCHEMA,
        "team_run_id": team_run_id,
        "owner_id": owner_id,
        "session_id": str(opened[0].get("session_id")),
        "root_sha256": str(opened[0].get("root_sha256")),
        "terminal_reason": str(intents[-1].get("terminal_reason")) if intents else None,
        "intent_id": str(intents[-1].get("intent_id")) if intents else None,
        "resources": resources,
        "open_count": open_count,
        "released_count": dispositions.count("released"),
        "already_absent_count": dispositions.count("already-absent"),
        "retained_count": dispositions.count("retained"),
        "failed_count": dispositions.count("failed"),
        "completion_fact_ref": str(completes[-1]["this_hash"]) if completes else None,
    }
    return projection


def open_runs(decision: DecisionInput, *, root_sha256: str | None = None) -> list[str]:
    """Team runs with a run-opened fact and no teardown-complete, oldest first.

    ``root_sha256`` scopes discovery to one canonical repository (R5): runs opened against a
    different broker root are never surfaced to this repository's hooks or CLI.
    """

    opened: list[str] = []
    completed: set[str] = set()
    for rec in _teardown_records(decision.ledger_records):
        run_id = str(rec.get("team_run_id"))
        if rec.get("event") == "run-opened":
            if root_sha256 is not None and rec.get("root_sha256") != root_sha256:
                continue
            if run_id not in opened:
                opened.append(run_id)
        elif rec.get("event") == "teardown-complete":
            completed.add(run_id)
    return [run_id for run_id in opened if run_id not in completed]


# --------------------------------------------------------------------------- run lifecycle


def default_broker() -> Any:
    """The canonical fleet lease authority, or a typed failure naming the install gap."""

    try:
        authority = fleet_commons_shim.load("lease_broker")
        broker = authority.LeaseBroker()
    except Exception as exc:  # noqa: BLE001 - plugin skew is named at the runtime boundary
        raise TeardownError(
            f"team teardown requires lease-capable fleet-core; install/update fleet-core: {exc}"
        ) from exc
    for required in ("close_owner_admission", "inspect_owner_admission", "sweep", "inspect"):
        if not callable(getattr(broker, required, None)):
            raise TeardownError(
                f"installed fleet-core lease broker lacks {required}(); update fleet-core"
            )
    return broker


def open_run(
    ledger: run_ledger.RunLedger,
    broker: Any,
    *,
    subplot_id: str,
    session_id: str,
    at: str,
    team_run_id: str | None = None,
) -> dict[str, Any]:
    """B0: open one bounded team run. The run's owner identity IS its team_run_id (R2)."""

    run_id = team_run_id if team_run_id is not None else new_team_run_id()
    fact = build_run_opened(
        subplot_id=subplot_id,
        at=at,
        team_run_id=run_id,
        owner_id=run_id,
        session_id=session_id,
        root_sha256=str(broker.root_sha256),
    )
    return append_teardown_event(ledger, fact)


# --------------------------------------------------------------------------- terminal driver


@dataclass(frozen=True)
class ActionOutcome:
    """One typed action result. Adapters return this — never prose (R4)."""

    disposition: str
    evidence_refs: tuple[str, ...] = ()
    reason_code: str = ""

    def validated(self) -> ActionOutcome:
        if self.disposition not in DISPOSITIONS:
            raise TeardownError(
                f"adapter disposition must be one of {sorted(DISPOSITIONS)}; "
                f"found {self.disposition!r}"
            )
        _evidence_refs(list(self.evidence_refs))
        if self.reason_code:
            _bounded_text(self.reason_code, "reason_code")
        return self


def _retain(reason_code: str) -> Callable[[Mapping[str, Any]], ActionOutcome]:
    def _adapter(_lease: Mapping[str, Any]) -> ActionOutcome:
        return ActionOutcome(disposition="retained", reason_code=reason_code)

    return _adapter


@dataclass(frozen=True)
class ReclaimAdapters:
    """Injected typed action adapters, one per resource kind (KTD4).

    The default for every slot is conservative retain — a driver wired without a trusted
    adapter can never destroy anything; the run stays a truthful blocked terminal (KTD6).
    """

    resident_stop: Callable[[Mapping[str, Any]], ActionOutcome] = field(
        default_factory=lambda: _retain("no-resident-runtime-adapter")
    )
    process_stop: Callable[[Mapping[str, Any]], ActionOutcome] = field(
        default_factory=lambda: _retain("no-process-adapter")
    )
    lease_release: Callable[[Mapping[str, Any]], ActionOutcome] = field(
        default_factory=lambda: _retain("no-lease-adapter")
    )
    worktree_sweep: Callable[[Mapping[str, Any]], ActionOutcome] = field(
        default_factory=lambda: _retain("no-worktree-adapter")
    )

    def for_action(self, action: str) -> Callable[[Mapping[str, Any]], ActionOutcome]:
        selected = {
            "resident-stop": self.resident_stop,
            "process-stop": self.process_stop,
            "lease-release": self.lease_release,
            "worktree-sweep": self.worktree_sweep,
        }.get(action)
        if selected is None:
            return _retain(f"unknown-action:{action}")
        return selected


def request(
    ledger: run_ledger.RunLedger,
    broker: Any,
    *,
    subplot_id: str,
    team_run_id: str,
    terminal_reason: str,
    at: str,
) -> dict[str, Any]:
    """Record teardown intent (close fence + intent fact) without acting — the bounded
    ``SessionEnd`` path (R5). A recorded request is evidence of the ask, never of closure."""

    close = broker.close_owner_admission(owner_id=team_run_id)
    intent = build_teardown_intent(
        subplot_id=subplot_id,
        at=at,
        team_run_id=team_run_id,
        terminal_reason=terminal_reason,
        close_generation=int(close["close_generation"]),
    )
    record = append_teardown_event(ledger, intent)
    return {
        "schema": TEARDOWN_SCHEMA,
        "recorded": "teardown-intent",
        "team_run_id": team_run_id,
        "intent_id": record["intent_id"],
        "close_generation": int(close["close_generation"]),
        "complete": False,
    }


def reclaim_all(
    ledger: run_ledger.RunLedger,
    broker: Any,
    adapters: ReclaimAdapters,
    *,
    subplot_id: str,
    team_run_id: str,
    terminal_reason: str,
    at_provider: Callable[[], str],
    max_actions: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """The idempotent Step B8 driver (R3/R4): close, snapshot, act, re-reconcile, receipt.

    Ordering: (1) close owner admission (idempotent — after this no new resource can race
    the zero-open receipt); (2) one verified decision input; (3) recover crash-orphaned
    action keys as ``already-absent``; (4) typed actions per owned resource, each rechecked
    by its adapter at action time; (5) fresh re-reconcile; (6) re-verify the still-closed
    close generation; (7) append ``teardown-complete`` only at zero open with no
    retained/failed keys. Repeated calls converge by stable action keys. ``dry_run``
    projects without closing, acting, or appending — census evidence, never completion.
    """

    if dry_run:
        return project(read_decision_input(ledger, broker), team_run_id)

    # A completed teardown is final: a repeated physical entry converges to the recorded
    # receipt without re-opening the state machine (R3 — once logically).
    prior = project(read_decision_input(ledger, broker), team_run_id)
    if prior["completion_fact_ref"] is not None:
        return prior

    close = broker.close_owner_admission(owner_id=team_run_id)
    generation = int(close["close_generation"])
    intent = append_teardown_event(
        ledger,
        build_teardown_intent(
            subplot_id=subplot_id,
            at=at_provider(),
            team_run_id=team_run_id,
            terminal_reason=terminal_reason,
            close_generation=generation,
        ),
    )
    intent_id = str(intent["intent_id"])

    decision = read_decision_input(ledger, broker)
    run = _run_records(decision.ledger_records, team_run_id)
    owned = _owned_leases(decision.broker_view, team_run_id)
    results = _last_result_by_action(run)
    attempts = _attempts_by_action(run)

    present_keys: dict[str, dict[str, Any]] = {}
    for lease in owned:
        kind, action = _classify_lease(lease)
        key = action_key(
            team_run_id, str(lease.get("lease_id")), f"{lease.get('fencing_sequence')}", action
        )
        present_keys[key] = {"lease": lease, "kind": kind, "action": action}

    # R4 crash seam: an attempt with no result whose resource is no longer present was
    # acted on before the fact could land — reconcile trusted reality, never act again.
    for key in sorted(attempts):
        if key in results or key in present_keys:
            continue
        append_teardown_event(
            ledger,
            build_resource_result(
                subplot_id=subplot_id,
                at=at_provider(),
                team_run_id=team_run_id,
                action_key_value=key,
                disposition="already-absent",
                evidence_refs=["reconciled:resource-absent-at-recovery"],
                reason_code="recovered-after-crash",
            ),
        )

    actions_taken = 0
    for key in sorted(present_keys):
        if max_actions is not None and actions_taken >= max_actions:
            break
        last = results.get(key)
        if last is not None and str(last.get("disposition")) in FINAL_DISPOSITIONS:
            continue
        entry = present_keys[key]
        lease = entry["lease"]
        append_teardown_event(
            ledger,
            build_resource_attempt(
                subplot_id=subplot_id,
                at=at_provider(),
                team_run_id=team_run_id,
                intent_id=intent_id,
                resource_id=str(lease.get("lease_id")),
                resource_kind=entry["kind"],
                generation=f"{lease.get('fencing_sequence')}",
                action=entry["action"],
            ),
        )
        try:
            outcome = adapters.for_action(entry["action"])(lease).validated()
        except TeardownError:
            raise
        except Exception as exc:  # noqa: BLE001 - a failed action is evidence, never dropped
            outcome = ActionOutcome(
                disposition="failed",
                reason_code=f"action-exception:{type(exc).__name__}",
            )
        append_teardown_event(
            ledger,
            build_resource_result(
                subplot_id=subplot_id,
                at=at_provider(),
                team_run_id=team_run_id,
                action_key_value=key,
                disposition=outcome.disposition,
                evidence_refs=list(outcome.evidence_refs),
                reason_code=outcome.reason_code,
            ),
        )
        actions_taken += 1

    final = read_decision_input(ledger, broker)
    final_run = _run_records(final.ledger_records, team_run_id)
    final_results = _last_result_by_action(final_run)
    still_open = _owned_leases(final.broker_view, team_run_id)
    blocked = sorted(
        key
        for key, rec in final_results.items()
        if str(rec.get("disposition")) not in FINAL_DISPOSITIONS
    )
    dangling = sorted(key for key in _attempts_by_action(final_run) if key not in final_results)

    verify = broker.inspect_owner_admission(team_run_id)
    if verify is None or int(verify["close_generation"]) != generation:
        raise TeardownError(
            f"owner admission for {team_run_id!r} is no longer the closed generation "
            f"{generation}; refusing completion (R3)"
        )

    if not still_open and not blocked and not dangling:
        dispositions = [str(rec.get("disposition")) for rec in final_results.values()]
        append_teardown_event(
            ledger,
            build_teardown_complete(
                subplot_id=subplot_id,
                at=at_provider(),
                team_run_id=team_run_id,
                intent_id=intent_id,
                close_generation=generation,
                released_count=dispositions.count("released"),
                already_absent_count=dispositions.count("already-absent"),
            ),
        )
    return project(read_decision_input(ledger, broker), team_run_id)


# --------------------------------------------------------------------------- action adapters


def _current_head(broker: Any, lease: Mapping[str, Any]) -> tuple[dict[str, Any] | None, Any]:
    """Re-read one lease's current broker head immediately before action (R4).

    Returns ``(head, token)`` — ``head`` is None when the lease no longer exists, and the
    token is built from the broker's own defining module (a second module load yields a
    different dataclass whose equality never matches).
    """

    lease_id = str(lease.get("lease_id"))
    view = broker.inspect()
    head = next(
        (item for item in view.get("leases", []) if item.get("lease_id") == lease_id),
        None,
    )
    if head is None:
        return None, None
    authority_module = sys.modules[type(broker).__module__]
    token = authority_module.FencingToken(str(view["broker_epoch"]), int(head["fencing_sequence"]))
    return head, token


def make_resident_stop_adapter(broker: Any) -> Callable[[Mapping[str, Any]], ActionOutcome]:
    """Resident teammates release only against broker-recorded terminal evidence (R7/R8).

    The stop request itself is a host-runtime act (Step B8 step 1); this adapter's
    authority is the ``child_terminal_at`` receipt the host hook recorded. Silence,
    timeout, and a missing receipt retain the lease — they are never terminal evidence.
    """

    def _resident_stop(lease: Mapping[str, Any]) -> ActionOutcome:
        head, token = _current_head(broker, lease)
        lease_id = str(lease.get("lease_id"))
        if head is None:
            return ActionOutcome(
                disposition="already-absent",
                evidence_refs=(f"broker:lease-absent:{lease_id}",),
                reason_code="lease-already-released",
            )
        if head.get("fencing_sequence") != lease.get("fencing_sequence"):
            return ActionOutcome(disposition="retained", reason_code="lease-generation-superseded")
        if not head.get("child_terminal_at"):
            return ActionOutcome(disposition="retained", reason_code="no-terminal-receipt")
        released = broker.release(lease_id, token=token, owner_id=str(lease.get("owner_id")))
        if released:
            return ActionOutcome(
                disposition="released",
                evidence_refs=(
                    f"broker:terminal-at:{head['child_terminal_at']}",
                    f"broker:released:{lease_id}",
                ),
            )
        return ActionOutcome(
            disposition="already-absent",
            evidence_refs=(f"broker:release-noop:{lease_id}",),
            reason_code="lease-already-released",
        )

    return _resident_stop


def make_process_stop_adapter(
    broker: Any,
    *,
    kill: Callable[[int, int], None] | None = None,
    sleep: Callable[[float], None] | None = None,
    term_wait_seconds: float = 5.0,
    poll_interval_seconds: float = 0.1,
) -> Callable[[Mapping[str, Any]], ActionOutcome]:
    """Signal only a process whose PID, start identity, boot, and run ownership all match
    the registration-time lease (R8). ``SIGTERM`` first; ``SIGKILL`` only when the lease
    was registered with the explicit ``term-then-kill`` escalation class. Every ambiguity
    fails safe as ``retained`` — a wrong signal is worse than a leaked process.
    """

    import signal as _signal

    providers = broker.providers
    send = kill if kill is not None else os.kill
    wait = sleep if sleep is not None else time.sleep

    def _gone(pid: int, start: str) -> bool:
        if not providers.process_exists(pid):
            return True
        return bool(providers.process_identity(pid) != start)

    def _await_exit(pid: int, start: str) -> bool:
        waited = 0.0
        while waited < term_wait_seconds:
            if _gone(pid, start):
                return True
            wait(poll_interval_seconds)
            waited += poll_interval_seconds
        return _gone(pid, start)

    def _process_stop(lease: Mapping[str, Any]) -> ActionOutcome:
        head, token = _current_head(broker, lease)
        lease_id = str(lease.get("lease_id"))
        if head is None:
            return ActionOutcome(
                disposition="already-absent",
                evidence_refs=(f"broker:lease-absent:{lease_id}",),
                reason_code="lease-already-released",
            )
        if head.get("fencing_sequence") != lease.get("fencing_sequence"):
            return ActionOutcome(disposition="retained", reason_code="lease-generation-superseded")
        pid_raw = head.get("owner_pid")
        start = head.get("owner_process_start")
        recorded_boot = head.get("boot_id")
        if pid_raw is None or not start:
            return ActionOutcome(disposition="retained", reason_code="process-identity-unrecorded")
        pid = int(pid_raw)
        current_boot = providers.boot_id()
        if recorded_boot != current_boot:
            # A different boot: the registered process is provably gone. If the PID exists
            # now it belongs to an unrelated post-reboot process — never signal it.
            return _release_absent(head, token, lease, "boot-identity-changed")
        if not providers.process_exists(pid):
            return _release_absent(head, token, lease, "process-not-running")
        current = providers.process_identity(pid)
        if current is None:
            return ActionOutcome(disposition="retained", reason_code="process-identity-unavailable")
        if current != start:
            return _release_absent(head, token, lease, "pid-identity-mismatch")
        try:
            send(pid, _signal.SIGTERM)
        except PermissionError:
            return ActionOutcome(disposition="retained", reason_code="signal-permission-denied")
        except ProcessLookupError:
            return _release_absent(head, token, lease, "exited-during-signal")
        if _await_exit(pid, start):
            return _release_stopped(head, token, lease, "sigterm")
        if head.get("agent_type") != SUBPROCESS_TERM_THEN_KILL:
            return ActionOutcome(
                disposition="retained", reason_code="alive-after-term-no-escalation"
            )
        try:
            send(pid, _signal.SIGKILL)
        except ProcessLookupError:
            return _release_stopped(head, token, lease, "exited-before-kill")
        if _await_exit(pid, start):
            return _release_stopped(head, token, lease, "term-then-kill")
        return ActionOutcome(disposition="failed", reason_code="alive-after-kill")

    def _release_absent(
        head: Mapping[str, Any], token: Any, lease: Mapping[str, Any], reason: str
    ) -> ActionOutcome:
        broker.release(
            str(head.get("lease_id") or lease.get("lease_id")),
            token=token,
            owner_id=str(lease.get("owner_id")),
        )
        return ActionOutcome(
            disposition="already-absent",
            evidence_refs=(f"process:absence-proof:{reason}",),
            reason_code=reason,
        )

    def _release_stopped(
        head: Mapping[str, Any], token: Any, lease: Mapping[str, Any], receipt: str
    ) -> ActionOutcome:
        broker.release(
            str(head.get("lease_id") or lease.get("lease_id")),
            token=token,
            owner_id=str(lease.get("owner_id")),
        )
        return ActionOutcome(
            disposition="released",
            evidence_refs=(f"process:signal-receipt:{receipt}",),
        )

    return _process_stop


def make_worktree_sweep_adapter(
    broker: Any,
    *,
    worktree_reaper: Callable[[Any], bool] | None = None,
) -> Callable[[Mapping[str, Any]], ActionOutcome]:
    """Worktrees go through the canonical #356 ``sweep`` only (R6) — never a direct
    ``git worktree remove``. Without an injected validated reaper the sweep can still
    release expired agent debris, but every worktree stays visibly retained.
    """

    def _worktree_sweep(lease: Mapping[str, Any]) -> ActionOutcome:
        lease_id = str(lease.get("lease_id"))
        head, _token = _current_head(broker, lease)
        if head is None:
            return ActionOutcome(
                disposition="already-absent",
                evidence_refs=(f"broker:lease-absent:{lease_id}",),
                reason_code="lease-already-released",
            )
        swept = broker.sweep(worktree_reaper=worktree_reaper)
        result = swept.to_dict() if hasattr(swept, "to_dict") else dict(swept)
        if lease_id in result.get("reaped_worktree_leases", []):
            return ActionOutcome(
                disposition="released",
                evidence_refs=(f"sweep:reaped:{lease_id}",),
            )
        retained_reason = result.get("retained", {}).get(lease_id)
        if retained_reason is not None:
            return ActionOutcome(disposition="retained", reason_code=f"sweep:{retained_reason}")
        follow_up, _ = _current_head(broker, lease)
        if follow_up is None:
            return ActionOutcome(
                disposition="already-absent",
                evidence_refs=(f"sweep:lease-gone:{lease_id}",),
                reason_code="released-by-sweep",
            )
        return ActionOutcome(disposition="retained", reason_code="not-a-sweep-candidate")

    return _worktree_sweep


def register_subprocess(
    broker: Any,
    *,
    team_run_id: str,
    session_id: str,
    pid: int,
    argv_digest: str,
    policy_sha256: str,
    session_limit: int,
    aggregate_limit: int,
    escalation: str = "term-only",
    ttl_seconds: int = 3600,
    mutation: str = "read-write",
) -> Any:
    """B1: register one coordinator-created subprocess in the broker before it matters (R2/R8).

    The stop policy rides the lease's ``agent_type`` — recorded at spawn time in the
    trusted store, never taken from caller prose at action time. The lease's
    ``owner_pid``/``owner_process_start``/``boot_id`` capture the child's exact identity.
    ``mutation`` must match the session's pinned admission snapshot (the broker refuses a
    mixed snapshot while the session holds live leases).
    """

    if escalation not in ("term-only", "term-then-kill"):
        raise TeardownError("escalation must be term-only or term-then-kill")
    agent_type = (
        SUBPROCESS_TERM_THEN_KILL if escalation == "term-then-kill" else SUBPROCESS_TERM_ONLY
    )
    digest = _bounded_text(argv_digest, "argv_digest")
    return broker.acquire_agent(
        owner_id=_bounded_text(team_run_id, "team_run_id"),
        session_id=_bounded_text(session_id, "session_id"),
        policy_sha256=policy_sha256,
        session_limit=session_limit,
        aggregate_limit=aggregate_limit,
        mutation=mutation,
        ttl_seconds=ttl_seconds,
        resource_ref={"logical_unit_id": f"subprocess:{digest[:32]}:{pid}"},
        owner_pid=pid,
        agent_type=agent_type,
    )


# --------------------------------------------------------------------------- idle eviction


def authorize_resident_stop(
    broker: Any,
    decision: Mapping[str, Any] | None,
    *,
    team_run_id: str,
    lease_id: str,
    explicit_shed: bool = False,
) -> dict[str, Any]:
    """The R7/KTD5 eviction gate: only a #357 ``confirmed-stalled`` decision or an explicit
    segment-boundary shed, paired with current #356 ownership, authorizes a resident stop.

    Phi suspicion, chat activity, a bare idle notice, pending ack/re-ping, pointer age, and
    agent prose are never authorization. The returned record is the *stop intent* for the
    host runtime; the release itself still flows through
    :func:`make_resident_stop_adapter`, which requires the broker-recorded terminal receipt.
    """

    def _refuse(reason: str) -> dict[str, Any]:
        return {"authorized": False, "reason_code": reason, "lease_id": lease_id}

    head, _token = _current_head(broker, {"lease_id": lease_id})
    if head is None:
        return _refuse("lease-absent")
    if str(head.get("owner_id")) != team_run_id:
        return _refuse("not-owned-by-run")
    warm = {
        "authorized": True,
        "lease_id": lease_id,
        "generation": f"{head.get('fencing_sequence')}",
        "agent_id": head.get("agent_id"),
    }
    if explicit_shed:
        return {**warm, "reason_code": "segment-boundary-shed"}
    if not isinstance(decision, Mapping):
        return _refuse("no-liveness-decision")
    classification = str(decision.get("classification") or "unknown")
    if classification != "confirmed-stalled":
        return _refuse(f"liveness-{classification}-not-actionable")
    if str(decision.get("terminal_authority") or "none") == "none":
        return _refuse("confirmed-without-terminal-authority")
    return {
        **warm,
        "reason_code": "confirmed-stalled",
        "liveness_generation": decision.get("generation"),
    }


# --------------------------------------------------------------------------- production wiring


def production_adapters(
    broker: Any,
    *,
    worktree_reaper: Callable[[Any], bool] | None = None,
    kill: Callable[[int, int], None] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> ReclaimAdapters:
    """The trusted production adapter set (KTD4): identity-checked broker release for
    provisional leases, terminal-receipt-gated resident release, exact-identity process
    stop with policy-bound escalation, and the canonical #356 worktree sweep."""

    def _lease_release(lease: Mapping[str, Any]) -> ActionOutcome:
        lease_id = str(lease.get("lease_id"))
        head, token = _current_head(broker, lease)
        if head is None:
            return ActionOutcome(
                disposition="already-absent",
                evidence_refs=(f"broker:lease-absent:{lease_id}",),
                reason_code="lease-already-released",
            )
        if head.get("fencing_sequence") != lease.get("fencing_sequence"):
            return ActionOutcome(
                disposition="retained",
                reason_code="lease-generation-superseded",
            )
        released = broker.release(lease_id, token=token, owner_id=str(lease.get("owner_id")))
        if released:
            return ActionOutcome(
                disposition="released",
                evidence_refs=(f"broker:released:{lease_id}",),
            )
        return ActionOutcome(
            disposition="already-absent",
            evidence_refs=(f"broker:release-noop:{lease_id}",),
            reason_code="lease-already-released",
        )

    return ReclaimAdapters(
        lease_release=_lease_release,
        resident_stop=make_resident_stop_adapter(broker),
        process_stop=make_process_stop_adapter(broker, kill=kill, sleep=sleep),
        worktree_sweep=make_worktree_sweep_adapter(broker, worktree_reaper=worktree_reaper),
    )


def recover(
    ledger: run_ledger.RunLedger,
    broker: Any,
    adapters: ReclaimAdapters,
    *,
    subplot_id: str,
    expired_only: bool,
    max_actions: int,
    at_provider: Callable[[], str],
) -> dict[str, Any]:
    """One bounded recovery pass over this repository's open runs (R5).

    Discovery is read-only; every destructive step re-enters the same idempotent
    :func:`reclaim_all` state machine under the same guards. ``expired_only`` skips any
    run that still holds a live-derived lease — a crashed coordinator's leases derive
    ``expired`` after TTL, and only then does recovery act. An observation fact is
    appended per run even when nothing was safe to reclaim.
    """

    if max_actions < 0:
        raise TeardownError("max_actions must be non-negative")
    decision = read_decision_input(ledger, broker)
    runs = open_runs(decision, root_sha256=str(broker.root_sha256))
    passes: list[dict[str, Any]] = []
    budget = max_actions
    for run_id in runs:
        owned = _owned_leases(decision.broker_view, run_id)
        live = [item for item in owned if item.get("derived_state") == "live"]
        if expired_only and live:
            append_teardown_event(
                ledger,
                build_recovery_observation(
                    subplot_id=subplot_id,
                    at=at_provider(),
                    team_run_id=run_id,
                    observed_open=len(owned),
                    actions_taken=0,
                    reason_code="expired-only-live-owner",
                ),
            )
            passes.append({"team_run_id": run_id, "actions_taken": 0, "skipped": "live-owner"})
            continue
        if budget <= 0:
            append_teardown_event(
                ledger,
                build_recovery_observation(
                    subplot_id=subplot_id,
                    at=at_provider(),
                    team_run_id=run_id,
                    observed_open=len(owned),
                    actions_taken=0,
                    reason_code="recovery-action-budget-exhausted",
                ),
            )
            passes.append({"team_run_id": run_id, "actions_taken": 0, "skipped": "budget"})
            continue
        before = len(
            [
                rec
                for rec in _run_records(read_decision_input(ledger, broker).ledger_records, run_id)
                if rec.get("event") == "resource-result"
            ]
        )
        projection = reclaim_all(
            ledger,
            broker,
            adapters,
            subplot_id=subplot_id,
            team_run_id=run_id,
            terminal_reason="recovered-crash",
            at_provider=at_provider,
            max_actions=budget,
        )
        after = len(
            [
                rec
                for rec in _run_records(read_decision_input(ledger, broker).ledger_records, run_id)
                if rec.get("event") == "resource-result"
            ]
        )
        taken = max(0, after - before)
        budget -= taken
        append_teardown_event(
            ledger,
            build_recovery_observation(
                subplot_id=subplot_id,
                at=at_provider(),
                team_run_id=run_id,
                observed_open=int(projection["open_count"]),
                actions_taken=taken,
                reason_code="recovery-pass",
            ),
        )
        passes.append(
            {
                "team_run_id": run_id,
                "actions_taken": taken,
                "open_count": projection["open_count"],
                "complete": projection["completion_fact_ref"] is not None,
            }
        )
    return {
        "schema": TEARDOWN_SCHEMA,
        "recovered_runs": passes,
        "expired_only": expired_only,
        "max_actions": max_actions,
    }


# --------------------------------------------------------------------------- CLI


def _now_utc_text() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _cli_ledger(repo_root: str) -> run_ledger.RunLedger:
    return run_ledger.RunLedger.resolve(Path(repo_root).resolve())


def _print_json(value: Mapping[str, Any]) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--subplot-id", default="team-execution-run")
    commands = parser.add_subparsers(dest="command", required=True)

    open_parser = commands.add_parser("open-run", help="B0: open one bounded team run")
    open_parser.add_argument("--session-id", required=True)
    open_parser.add_argument("--team-run-id", default=None)

    status_parser = commands.add_parser("status", help="derived team_teardown.v1 projection")
    status_parser.add_argument("--team-run-id", default=None)

    request_parser = commands.add_parser(
        "request", help="record teardown intent for this session's open runs (bounded)"
    )
    request_parser.add_argument("--session-id", required=True)
    request_parser.add_argument("--reason", default="operator-abort")
    request_parser.add_argument("--team-run-id", default=None)

    reclaim_parser = commands.add_parser(
        "reclaim-all", help="Step B8: idempotent terminal reclamation for one run"
    )
    reclaim_parser.add_argument("--team-run-id", required=True)
    reclaim_parser.add_argument("--reason", default="success")
    reclaim_parser.add_argument("--max-actions", type=int, default=None)
    reclaim_parser.add_argument("--dry-run", action="store_true")

    recover_parser = commands.add_parser(
        "recover", help="bounded recovery pass over this repository's open runs"
    )
    recover_parser.add_argument("--expired-only", action="store_true")
    recover_parser.add_argument("--max-actions", type=int, default=4)
    return parser


def _matching_open_runs(
    decision: DecisionInput, *, root_sha256: str, session_id: str | None
) -> list[str]:
    runs = open_runs(decision, root_sha256=root_sha256)
    if session_id is None:
        return runs
    matched: list[str] = []
    for rec in _teardown_records(decision.ledger_records):
        if (
            rec.get("event") == "run-opened"
            and rec.get("session_id") == session_id
            and str(rec.get("team_run_id")) in runs
        ):
            matched.append(str(rec.get("team_run_id")))
    return matched


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        ledger = _cli_ledger(args.repo_root)
        broker = default_broker()
        if args.command == "open-run":
            record = open_run(
                ledger,
                broker,
                subplot_id=args.subplot_id,
                session_id=args.session_id,
                at=_now_utc_text(),
                team_run_id=args.team_run_id,
            )
            _print_json({"opened": record["team_run_id"], "fact_ref": record["this_hash"]})
        elif args.command == "status":
            decision = read_decision_input(ledger, broker)
            if args.team_run_id is not None:
                _print_json(project(decision, args.team_run_id))
            else:
                _print_json(
                    {
                        "schema": TEARDOWN_SCHEMA,
                        "open_runs": open_runs(decision, root_sha256=str(broker.root_sha256)),
                    }
                )
        elif args.command == "request":
            decision = read_decision_input(ledger, broker)
            targets = (
                [args.team_run_id]
                if args.team_run_id is not None
                else _matching_open_runs(
                    decision,
                    root_sha256=str(broker.root_sha256),
                    session_id=args.session_id,
                )
            )
            recorded = [
                request(
                    ledger,
                    broker,
                    subplot_id=args.subplot_id,
                    team_run_id=run_id,
                    terminal_reason=args.reason,
                    at=_now_utc_text(),
                )
                for run_id in targets
            ]
            _print_json({"schema": TEARDOWN_SCHEMA, "requested": recorded})
        elif args.command == "reclaim-all":
            _print_json(
                reclaim_all(
                    ledger,
                    broker,
                    production_adapters(broker),
                    subplot_id=args.subplot_id,
                    team_run_id=args.team_run_id,
                    terminal_reason=args.reason,
                    at_provider=_now_utc_text,
                    max_actions=args.max_actions,
                    dry_run=args.dry_run,
                )
            )
        else:
            _print_json(
                recover(
                    ledger,
                    broker,
                    production_adapters(broker),
                    subplot_id=args.subplot_id,
                    expired_only=args.expired_only,
                    max_actions=args.max_actions,
                    at_provider=_now_utc_text,
                )
            )
    except TeardownError as exc:
        print(
            json.dumps({"error": "team-teardown", "reason": str(exc)}),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
