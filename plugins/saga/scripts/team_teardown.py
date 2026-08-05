#!/usr/bin/env python3
"""Non-skippable team-run teardown: closed event family, projection, terminal driver (#358).

Retires the #356 fleet lease authority from the teardown contract (#677/U2). Resources
are no longer enumerated from leases: the census reads the per-outcome **worktree
registries** (``<git-common-dir>/saga-outcomes/*/worktrees.json``) cross-checked with
``git worktree list``, and every view here is projected from one chain-verified
``run_fact.v1`` ledger snapshot plus one read-only registry census. The ledger remains
append-only history; this module adds **no** second registry, mutable status store, TTL
clock, heartbeat detector, or reaper decision engine (R1) — and per KTD12 it performs
**no worktree removal at all**: the sweep is report-only, because teardown never
reclaimed worktrees even when the lease authority existed (no production caller ever
injected a reaper).

Event family (``kind=teardown``, closed — R9): ``run-opened``, ``teardown-intent``,
``resource-attempt``, ``resource-result``, ``recovery-observation``, ``teardown-complete``.
Transition validation and append share the ledger's exclusive write lock via
``run_ledger.append_fact_built_atomic``. Facts carry bounded identity and evidence digests,
never prompts, message text, or stdout/stderr — and never a mutable open/closed summary.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import sys
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome_store  # noqa: E402
import outcome_worktrees  # noqa: E402
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
# The closed action vocabulary is frozen even though #677/U2 retired every discovery
# source except the worktree sweep: ledger facts recorded under the lease-era kinds
# remain valid reads, and a driver wired for an unknown/retired action conservatively
# retains rather than acts (KTD6).
ACTION_KINDS = frozenset({"resident-stop", "process-stop", "lease-release", "worktree-sweep"})
RESOURCE_KINDS = frozenset(
    {"resident-agent", "owned-subprocess", "outcome-worktree", "provisional-lease"}
)

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
    """A bounded, collision-resistant team run identity (the run's owner_id)."""

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
        # close_generation is deliberately NOT intent identity (it is excluded from
        # intent_id): under #358 it carried the lease-authority close fence's generation,
        # which could be re-issued; a re-issued close had to replay the one logical
        # intent, never poison the run with a permanent conflict. #677/U2 retired the
        # fence (the driver now records the vestigial constant 1), but the exclusion
        # stays so lease-era ledgers keep replaying cleanly.
        for rec in same_intent:
            existing_identity = {
                k: v for k, v in _without_volatile(rec).items() if k != "close_generation"
            }
            fact_identity = {
                k: v for k, v in _without_volatile(fact).items() if k != "close_generation"
            }
            if existing_identity == fact_identity:
                raise _DuplicateEvent(dict(rec))
        if same_intent:
            raise TeardownConflictError(
                f"{event} for run {run_id!r} conflicts with an already-recorded event "
                "of the same identity"
            )
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

    Validation here is ledger-internal by design: the zero-open recheck lives in
    :func:`reclaim_all`, the only sanctioned ``teardown-complete`` emitter. A direct
    append that bypasses the driver cannot fabricate closure — :func:`project` derives
    ``open_count`` live from the registry census, so a completion fact recorded over an
    unsettled resource stays visibly inconsistent.
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
    """One immutable decision input: a chain-verified ledger view + one registry census.

    The two reads are consistent individually, not atomic across stores (R4) — the
    driver re-reads the census after acting. Census entries carry ``outcome_id``,
    ``subplot_id``, ``path``, and ``live`` (git still lists the path).
    """

    ledger_records: tuple[dict[str, Any], ...]
    worktrees: tuple[dict[str, Any], ...]


def _worktree_census(repo_root: Path) -> tuple[dict[str, Any], ...]:
    """One read-only census of registered outcome worktrees across every outcome store.

    The enumeration source is the per-outcome worktree registry cross-checked with
    ``git worktree list`` via :func:`outcome_worktrees.live_worktrees` (#677/U2) — the
    lease list it replaces no longer exists. The census enumerates in order to REPORT,
    never to remove: entries are read through the lenient registry path (a malformed
    registry reads as empty, never fatal), and entries without a usable path are
    skipped.
    """

    root = Path(repo_root)
    try:
        common = outcome_store.resolve_common_dir(root)
    except outcome_store.OutcomeStoreError as exc:
        raise TeardownError(f"cannot enumerate worktrees without git: {exc}") from exc
    namespace = common / outcome_store.STORE_NAMESPACE
    if not namespace.is_dir():
        return ()
    ops = outcome_worktrees.git_worktree_ops(root)
    items: list[dict[str, Any]] = []
    for registry_path in sorted(namespace.glob("*/worktrees.json")):
        store = outcome_store.Store(root=registry_path.parent)
        outcome_id = registry_path.parent.name
        live = outcome_worktrees.live_worktrees(store, ops)
        for sid, entry in sorted(outcome_worktrees.read_registry(store).items()):
            path = str(entry.get("path", ""))
            if not path:
                continue
            items.append(
                {
                    "outcome_id": outcome_id,
                    "subplot_id": sid,
                    "path": path,
                    "live": sid in live,
                }
            )
    return tuple(items)


def read_decision_input(ledger: run_ledger.RunLedger, *, repo_root: Path) -> DecisionInput:
    snapshot = run_ledger.read_snapshot(ledger)
    if not snapshot.report.ok:
        raise TeardownError(
            f"refusing decisions on a broken run-fact chain: {snapshot.report.reason}"
        )
    return DecisionInput(
        ledger_records=tuple(dict(rec) for rec in snapshot.records),
        worktrees=_worktree_census(repo_root),
    )


def _worktree_generation(item: Mapping[str, Any]) -> str:
    """The registry coordinates of one census entry — its stable generation string."""

    return f"{item.get('outcome_id')}:{item.get('subplot_id')}"


def _worktree_action_key(team_run_id: str, item: Mapping[str, Any]) -> str:
    return action_key(
        team_run_id, str(item.get("path")), _worktree_generation(item), "worktree-sweep"
    )


def _present_keys(team_run_id: str, worktrees: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    keys: dict[str, Any] = {}
    for item in worktrees:
        keys[_worktree_action_key(team_run_id, item)] = item
    return keys


def project(decision: DecisionInput, team_run_id: str) -> dict[str, Any]:
    """The derived ``team_teardown.v1`` terminal contract — never a stored summary (R9).

    ``open_count`` counts census entries whose action key has not reached a final
    disposition: the registry never shrinks on its own (#677/U2 removed the only
    automatic deregisterer along with the reap path), so "still open" means "still
    unsettled", which is exactly what the completion gate rechecks.
    """

    run = _run_records(decision.ledger_records, team_run_id)
    opened = [rec for rec in run if rec.get("event") == "run-opened"]
    if not opened:
        raise TeardownError(f"unknown team run {team_run_id!r}: no run-opened fact")
    owner_id = str(opened[0].get("owner_id"))
    intents = [rec for rec in run if rec.get("event") == "teardown-intent"]
    completes = [rec for rec in run if rec.get("event") == "teardown-complete"]
    results = _last_result_by_action(run)
    attempts = _attempts_by_action(run)

    resources: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    open_count = 0
    for item in decision.worktrees:
        resource_id = str(item.get("path"))
        generation = _worktree_generation(item)
        key = action_key(team_run_id, resource_id, generation, "worktree-sweep")
        last = results.get(key)
        disposition = str(last.get("disposition")) if last else "open"
        if disposition not in FINAL_DISPOSITIONS:
            open_count += 1
        resources.append(
            {
                "resource_id": resource_id,
                "generation": generation,
                "kind": "outcome-worktree",
                "owner_ref": owner_id,
                "action": "worktree-sweep",
                "disposition": disposition,
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

    ``root_sha256`` scopes discovery to one canonical repository (R5): runs opened against
    a different repository identity are never surfaced to this repository's hooks or CLI.
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


def repository_root_sha256(ledger: run_ledger.RunLedger) -> str:
    """The canonical repository identity run-opened facts are scoped by (#677/U2).

    Replaces the lease authority's root digest: the ledger is anchored under the
    repository's git common dir (``<common-dir>/saga-run-facts/run-facts.jsonl``), so
    the resolved common-dir path is a stable, dependency-free identity anchor. It is a
    path digest — a relocated clone gets a fresh identity, exactly like the old root.
    """

    common_dir = Path(ledger.path).parent.parent
    return hashlib.sha256(str(common_dir).encode("utf-8")).hexdigest()


def open_run(
    ledger: run_ledger.RunLedger,
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
        root_sha256=repository_root_sha256(ledger),
    )
    return append_teardown_event(ledger, fact)


# --------------------------------------------------------------------------- terminal driver


# Reason codes only the driver itself may write into a resource-result fact. The
# recovery budget is counted at the source (ReclaimStats increments only in the
# adapter action loop, never in the crash-reconcile loop), so the exemption cannot
# be spoofed through the budget — but an adapter outcome carrying a reserved code
# would still impersonate driver bookkeeping in the durable evidence, so
# validated() refuses the whole set from the adapter surface.
_RECOVERED_AFTER_CRASH = "recovered-after-crash"
_DRIVER_RESERVED_REASON_CODES = frozenset({_RECOVERED_AFTER_CRASH})


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
        if self.reason_code in _DRIVER_RESERVED_REASON_CODES:
            raise TeardownError(
                f"reason_code {self.reason_code!r} is driver-reserved bookkeeping; "
                "adapters must not emit it"
            )
        return self


def _retain(reason_code: str) -> Callable[[Mapping[str, Any]], ActionOutcome]:
    def _adapter(_resource: Mapping[str, Any]) -> ActionOutcome:
        return ActionOutcome(disposition="retained", reason_code=reason_code)

    return _adapter


@dataclass(frozen=True)
class ReclaimAdapters:
    """Injected typed action adapters, one per action kind (KTD4).

    The default for every slot is conservative retain — a driver wired without a trusted
    adapter can never destroy anything; the run stays a truthful blocked terminal (KTD6).
    #677/U2 retired every discovery source except the worktree sweep, so the other slots
    are unreachable in production; they keep their conservative defaults.
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


@dataclass
class ReclaimStats:
    """Per-call accounting a caller reads even when :func:`reclaim_all` raises mid-flight.

    ``actions_taken`` counts the budgeted actions THIS call completed (adapter invoked
    and its result fact landed), incremented at the source inside the per-run guard.
    Callers that need the count on the raise path pass an instance in; inferring it
    afterwards from ledger snapshots is exactly the differential instrument that
    fabricated baselines, inherited ledger failures, and charged concurrent racers'
    work to the wrong pass.
    """

    actions_taken: int = 0


def request(
    ledger: run_ledger.RunLedger,
    *,
    subplot_id: str,
    team_run_id: str,
    terminal_reason: str,
    at: str,
) -> dict[str, Any]:
    """Record teardown intent without acting — the bounded ``SessionEnd`` path (R5).

    A recorded request is evidence of the ask, never of closure. #677/U2 retired the
    owner-admission close fence that used to precede the intent; ``close_generation``
    stays in the fact shape as the vestigial constant 1.
    """

    intent = build_teardown_intent(
        subplot_id=subplot_id,
        at=at,
        team_run_id=team_run_id,
        terminal_reason=terminal_reason,
        close_generation=1,
    )
    record = append_teardown_event(ledger, intent)
    return {
        "schema": TEARDOWN_SCHEMA,
        "recorded": "teardown-intent",
        "team_run_id": team_run_id,
        "intent_id": record["intent_id"],
        "close_generation": 1,
        "complete": False,
    }


def _reclaim_lock_path(ledger: run_ledger.RunLedger, team_run_id: str) -> Path:
    digest = hashlib.sha256(_bounded_text(team_run_id, "team_run_id").encode("utf-8"))
    return ledger.path.with_suffix(ledger.path.suffix + f".reclaim-{digest.hexdigest()[:16]}")


@contextlib.contextmanager
def _reclaim_guard(ledger: run_ledger.RunLedger, team_run_id: str) -> Iterator[Path]:
    """One exclusive per-run mutex around the B8 action phase (R3).

    The ledger dedups facts, but without this lock two concurrent physical passes could
    both invoke an adapter for the same action key (both snapshot before either result
    lands). Freshness of the attempt append cannot arbitrate — a dead predecessor's
    dangling attempt must stay re-actable — so serialization is structural: a live racer
    blocks here; a crashed holder's flock releases with its process.
    """

    lock_path = _reclaim_lock_path(ledger, team_run_id)
    try:
        # The guard may run before any append has provisioned the store directory
        # (an operator reclaim on a fresh repository) — provision it, and surface any
        # filesystem refusal as the module's typed failure, never a raw traceback.
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as exc:
        raise TeardownError(f"cannot provision the reclaim guard at {lock_path}: {exc}") from exc
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield lock_path
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def reclaim_all(
    ledger: run_ledger.RunLedger,
    adapters: ReclaimAdapters,
    *,
    subplot_id: str,
    team_run_id: str,
    terminal_reason: str,
    at_provider: Callable[[], str],
    repo_root: Path,
    max_actions: int | None = None,
    dry_run: bool = False,
    stats: ReclaimStats | None = None,
) -> dict[str, Any]:
    """The idempotent Step B8 driver (R3/R4): snapshot, act, re-reconcile, receipt.

    Ordering: (1) one verified decision input (ledger snapshot + registry census);
    (2) recover crash-orphaned action keys as ``already-absent``; (3) typed actions per
    census entry, each rechecked by its adapter at action time; (4) fresh re-reconcile;
    (5) append ``teardown-complete`` only when no census entry is unsettled and no
    retained/failed or dangling keys remain. Repeated calls converge by stable action
    keys; concurrent physical passes for one run serialize on :func:`_reclaim_guard` so
    each logical action invokes its adapter once. ``dry_run`` projects without acting
    or appending — census evidence, never completion. ``stats`` receives this call's
    budgeted action count as it accrues — crash-orphan reconciles never increment it,
    and it stays readable when the call raises mid-flight.

    #677/U2 retired the owner-admission fence and its still-closed recheck: there is no
    spawn racing completion anymore because the census is read at decision time and
    re-read after acting, and adapters only ever REPORT worktree state.
    """

    if dry_run:
        return project(read_decision_input(ledger, repo_root=repo_root), team_run_id)

    with _reclaim_guard(ledger, team_run_id) as lock_path:
        projection = _reclaim_all_locked(
            ledger,
            adapters,
            subplot_id=subplot_id,
            team_run_id=team_run_id,
            terminal_reason=terminal_reason,
            at_provider=at_provider,
            repo_root=repo_root,
            max_actions=max_actions,
            stats=stats if stats is not None else ReclaimStats(),
        )
        if projection["completion_fact_ref"] is not None:
            # Completion is final: every later pass short-circuits read-only on the
            # recorded receipt, so unlinking under the lock reclaims the per-run sidecar
            # without a lock-split hazard — a holder of a fresh inode can only observe
            # the receipt, never act.
            lock_path.unlink(missing_ok=True)
        return projection


def _reclaim_all_locked(
    ledger: run_ledger.RunLedger,
    adapters: ReclaimAdapters,
    *,
    subplot_id: str,
    team_run_id: str,
    terminal_reason: str,
    at_provider: Callable[[], str],
    repo_root: Path,
    max_actions: int | None,
    stats: ReclaimStats,
) -> dict[str, Any]:
    # A completed teardown is final: a repeated physical entry converges to the recorded
    # receipt without re-opening the state machine (R3 — once logically). Checked under
    # the guard so a racer that waited out the winner sees the winner's receipt.
    prior = project(read_decision_input(ledger, repo_root=repo_root), team_run_id)
    if prior["completion_fact_ref"] is not None:
        return prior

    intent = append_teardown_event(
        ledger,
        build_teardown_intent(
            subplot_id=subplot_id,
            at=at_provider(),
            team_run_id=team_run_id,
            terminal_reason=terminal_reason,
            close_generation=1,
        ),
    )
    intent_id = str(intent["intent_id"])

    decision = read_decision_input(ledger, repo_root=repo_root)
    run = _run_records(decision.ledger_records, team_run_id)
    results = _last_result_by_action(run)
    attempts = _attempts_by_action(run)

    present_keys = _present_keys(team_run_id, decision.worktrees)

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
                reason_code=_RECOVERED_AFTER_CRASH,
            ),
        )

    # The budgeted-action count lives on `stats`, not a local: the caller's accounting
    # must survive a mid-flight raise, and counting at the source — inside the guard,
    # only in THIS loop — is what keeps the crash-reconcile loop above budget-exempt
    # by construction.
    for key in sorted(present_keys):
        if max_actions is not None and stats.actions_taken >= max_actions:
            break
        last = results.get(key)
        if last is not None and str(last.get("disposition")) in FINAL_DISPOSITIONS:
            continue
        item = present_keys[key]
        append_teardown_event(
            ledger,
            build_resource_attempt(
                subplot_id=subplot_id,
                at=at_provider(),
                team_run_id=team_run_id,
                intent_id=intent_id,
                resource_id=str(item.get("path")),
                resource_kind="outcome-worktree",
                generation=_worktree_generation(item),
                action="worktree-sweep",
            ),
        )
        try:
            outcome = adapters.for_action("worktree-sweep")(item).validated()
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
        stats.actions_taken += 1

    final = read_decision_input(ledger, repo_root=repo_root)
    final_run = _run_records(final.ledger_records, team_run_id)
    final_results = _last_result_by_action(final_run)
    still_open = sorted(
        key
        for key, item in _present_keys(team_run_id, final.worktrees).items()
        if str(final_results.get(key, {}).get("disposition", "")) not in FINAL_DISPOSITIONS
    )
    blocked = sorted(
        key
        for key, rec in final_results.items()
        if str(rec.get("disposition")) not in FINAL_DISPOSITIONS
    )
    dangling = sorted(key for key in _attempts_by_action(final_run) if key not in final_results)

    if not still_open and not blocked and not dangling:
        dispositions = [str(rec.get("disposition")) for rec in final_results.values()]
        append_teardown_event(
            ledger,
            build_teardown_complete(
                subplot_id=subplot_id,
                at=at_provider(),
                team_run_id=team_run_id,
                intent_id=intent_id,
                close_generation=1,
                released_count=dispositions.count("released"),
                already_absent_count=dispositions.count("already-absent"),
            ),
        )
    return project(read_decision_input(ledger, repo_root=repo_root), team_run_id)


# --------------------------------------------------------------------------- action adapters


def make_worktree_sweep_adapter(
    ops: outcome_worktrees.WorktreeOps,
) -> Callable[[Mapping[str, Any]], ActionOutcome]:
    """Report one registered worktree's disposition against git — never remove anything.

    #677/U2 re-keyed the #358 sweep's five lease-indexed outcomes (plan R5c) onto
    worktree path. The two retained rows (the sweep's retained-with-reason branch and
    its never-a-candidate fallthrough) converge on ``retained`` / ``worktree-listed``:
    git still lists the worktree, and teardown never removes — there is no sweep
    decision engine left to encode. The two lease-absent rows converge on
    ``already-absent`` / ``worktree-not-listed``, whose meaning CHANGED with the
    re-key: it now means "git no longer lists this worktree" (previously "the lease
    head is gone", which said nothing about disk). The released-by-reap row has no
    successor: the reap branch and its reaper seam were deleted with the lease
    authority — this unit removes nothing from disk under any input (KTD12), so
    #358's R6 prohibition on a direct ``git worktree remove`` has nothing left to
    guard.
    """

    def _worktree_sweep(resource: Mapping[str, Any]) -> ActionOutcome:
        ref = _worktree_generation(resource)
        path = str(resource.get("path", ""))
        if path and ops.exists(path):
            return ActionOutcome(disposition="retained", reason_code="worktree-listed")
        return ActionOutcome(
            disposition="already-absent",
            evidence_refs=(f"worktree:path-absent:{ref}",),
            reason_code="worktree-not-listed",
        )

    return _worktree_sweep


# --------------------------------------------------------------------------- production wiring


def production_adapters(repo_root: Path) -> ReclaimAdapters:
    """The trusted production adapter set (#677/U2): the report-only worktree sweep over
    git's live listing. The resident-stop, process-stop, and lease-release slots keep
    their conservative retain defaults — no census source enumerates those resources
    anymore, and a driver wired without a trusted adapter can never destroy anything."""

    return ReclaimAdapters(
        worktree_sweep=make_worktree_sweep_adapter(outcome_worktrees.git_worktree_ops(repo_root))
    )


def _observe_recovery(
    ledger: run_ledger.RunLedger,
    *,
    subplot_id: str,
    at: str,
    team_run_id: str,
    observed_open: int,
    actions_taken: int,
    reason_code: str,
) -> str | None:
    """Best-effort recovery-observation append; returns the failure's type name, if any.

    Evidence recording must never abort the batch: when the ledger itself refuses the
    observation, the loss is reported in the run's in-memory pass entry and the loop
    continues to the next run — raising here would destroy every later run's recovery
    along with the evidence.
    """

    try:
        append_teardown_event(
            ledger,
            build_recovery_observation(
                subplot_id=subplot_id,
                at=at,
                team_run_id=team_run_id,
                observed_open=observed_open,
                actions_taken=actions_taken,
                reason_code=reason_code,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - evidence loss is reported in-memory, never fatal
        return type(exc).__name__
    return None


def recover(
    ledger: run_ledger.RunLedger,
    adapters: ReclaimAdapters,
    *,
    subplot_id: str,
    expired_only: bool,
    max_actions: int,
    at_provider: Callable[[], str],
    repo_root: Path,
) -> dict[str, Any]:
    """One bounded recovery pass over this repository's open runs (R5).

    Discovery is read-only; every destructive step re-enters the same idempotent
    :func:`reclaim_all` state machine under the same guards. ``expired_only`` skips any
    run while the census still sees a git-listed worktree — with the lease authority
    gone (#677/U2), a live worktree is the only liveness signal teardown has, and
    recovery never finalizes reporting over one. An observation fact is appended per run
    even when nothing was safe to reclaim. Per-run isolation is total: the pass body
    degrades to the run's pass entry on failure, and the budget charge is counted at the
    source (:class:`ReclaimStats`, inside the per-run guard) rather than inferred from
    ledger snapshots — accounting has no failable read of its own, so the only
    degradable bookkeeping left is the observation append (``evidence_error``).
    """

    if max_actions < 0:
        raise TeardownError("max_actions must be non-negative")
    decision = read_decision_input(ledger, repo_root=repo_root)
    runs = open_runs(decision, root_sha256=repository_root_sha256(ledger))
    passes: list[dict[str, Any]] = []
    budget = max_actions
    live = [item for item in decision.worktrees if item.get("live")]
    for run_id in runs:
        if expired_only and live:
            entry: dict[str, Any] = {
                "team_run_id": run_id,
                "actions_taken": 0,
                "skipped": "live-worktrees",
            }
            lost = _observe_recovery(
                ledger,
                subplot_id=subplot_id,
                at=at_provider(),
                team_run_id=run_id,
                observed_open=len(decision.worktrees),
                actions_taken=0,
                reason_code="expired-only-live-worktrees",
            )
            if lost is not None:
                entry["evidence_error"] = lost
            passes.append(entry)
            continue
        if budget <= 0:
            entry = {"team_run_id": run_id, "actions_taken": 0, "skipped": "budget"}
            lost = _observe_recovery(
                ledger,
                subplot_id=subplot_id,
                at=at_provider(),
                team_run_id=run_id,
                observed_open=len(decision.worktrees),
                actions_taken=0,
                reason_code="recovery-action-budget-exhausted",
            )
            if lost is not None:
                entry["evidence_error"] = lost
            passes.append(entry)
            continue
        # Per-run isolation: one run's refused pass (a blocked terminal, a conflicted
        # ledger, a corrupt registry entry, an adapter refusal) is that run's evidence —
        # it must never head-of-line block recovery of every newer open run. The net is
        # deliberately wide; the observation append records the type as the evidence.
        stats = ReclaimStats()
        run_error: str | None = None
        projection: dict[str, Any] | None = None
        try:
            projection = reclaim_all(
                ledger,
                adapters,
                subplot_id=subplot_id,
                team_run_id=run_id,
                terminal_reason="recovered-crash",
                at_provider=at_provider,
                repo_root=repo_root,
                max_actions=budget,
                stats=stats,
            )
        except Exception as exc:  # noqa: BLE001 - one run's failure is evidence, not a pass abort
            run_error = type(exc).__name__
        # Counted at the source: reclaim_all increments `stats` at each budgeted action,
        # under the per-run guard, so the charge is exact for THIS call even when the
        # pass raised mid-flight. It is never inferred from before/after ledger
        # snapshots — a differential read can fail independently, lacks a baseline when
        # its first read fails, and attributes a concurrent racer's results to this
        # pass; an in-memory increment can do none of those.
        taken = min(budget, stats.actions_taken)
        budget -= taken
        entry = {"team_run_id": run_id, "actions_taken": taken}
        if run_error is None and projection is not None:
            observed_open = int(projection["open_count"])
            reason_code = "recovery-pass"
            entry["open_count"] = projection["open_count"]
            entry["complete"] = projection["completion_fact_ref"] is not None
        else:
            observed_open = len(decision.worktrees)
            reason_code = f"recovery-run-error:{run_error}"
            entry["error"] = run_error
        lost = _observe_recovery(
            ledger,
            subplot_id=subplot_id,
            at=at_provider(),
            team_run_id=run_id,
            observed_open=observed_open,
            actions_taken=taken,
            reason_code=reason_code,
        )
        if lost is not None:
            entry["evidence_error"] = lost
        passes.append(entry)
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
        repo_root = Path(args.repo_root).resolve()
        ledger = _cli_ledger(args.repo_root)
        if args.command == "open-run":
            record = open_run(
                ledger,
                subplot_id=args.subplot_id,
                session_id=args.session_id,
                at=_now_utc_text(),
                team_run_id=args.team_run_id,
            )
            _print_json({"opened": record["team_run_id"], "fact_ref": record["this_hash"]})
        elif args.command == "status":
            decision = read_decision_input(ledger, repo_root=repo_root)
            if args.team_run_id is not None:
                _print_json(project(decision, args.team_run_id))
            else:
                _print_json(
                    {
                        "schema": TEARDOWN_SCHEMA,
                        "open_runs": open_runs(
                            decision, root_sha256=repository_root_sha256(ledger)
                        ),
                    }
                )
        elif args.command == "request":
            decision = read_decision_input(ledger, repo_root=repo_root)
            targets = (
                [args.team_run_id]
                if args.team_run_id is not None
                else _matching_open_runs(
                    decision,
                    root_sha256=repository_root_sha256(ledger),
                    session_id=args.session_id,
                )
            )
            recorded = [
                request(
                    ledger,
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
                    production_adapters(repo_root),
                    subplot_id=args.subplot_id,
                    team_run_id=args.team_run_id,
                    terminal_reason=args.reason,
                    at_provider=_now_utc_text,
                    repo_root=repo_root,
                    max_actions=args.max_actions,
                    dry_run=args.dry_run,
                )
            )
        else:
            _print_json(
                recover(
                    ledger,
                    production_adapters(repo_root),
                    subplot_id=args.subplot_id,
                    expired_only=args.expired_only,
                    max_actions=args.max_actions,
                    at_provider=_now_utc_text,
                    repo_root=repo_root,
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
