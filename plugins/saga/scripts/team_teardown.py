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
import sys
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
