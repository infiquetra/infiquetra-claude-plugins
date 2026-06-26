#!/usr/bin/env python3
"""Leaf liveness enforcement — heartbeats + the ``stalled`` terminal (U9 — R31).

A dispatched leaf can hang: a ``cc-workflows`` / ``/goal`` run that never returns, a forked agent that
died. R31 says such a leaf must be **reclaimed and paged**, not waited on forever. Each node carries two
optional budgets (declared in U1): ``heartbeat_seconds`` (the max gap between liveness pings) and
``timeout_seconds`` (the max total runtime). When a dispatched, non-terminal leaf breaches either, it
reaches the **defined ``stalled`` terminal** (a negative terminal, like the U6 ``rejected`` /the U7
worktree-removed) that **cascades** to its downstream subtree (R22) — so dependents do not hang on a dead
leaf — and it **pages once** (the terminal is idempotent, not re-recorded every tick).

Liveness is derived-on-read from the durable store (R17/R29): the dispatch time is the leaf's ``commit``
ledger record's ``at``, and a leaf optionally records ``heartbeat`` ledger records as it runs. A leaf
with **neither** budget set is never liveness-killed (the operator opted out of a timeout). ``now`` is
injected so the check is unit-testable with no wall clock.

House pattern (mirrors ``outcome_worktrees`` / ``outcome_merge``): pure functions over explicit values,
``outcome`` imported lazily to avoid a cycle, no I/O at import.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome_orchestrator  # noqa: E402  (after the sys.path shim, by design)
import outcome_store  # noqa: E402

# The negative terminal a hung leaf reaches (R31). ``stalled`` is in NODE_STATES + TERMINAL_STATES and
# cascades like a block (R22) — a sticky terminal, not retried, until the operator intervenes.
STALLED_STATE = "stalled"


def record_heartbeat(store: Any, subplot_id: str, *, at: float) -> None:
    """Record a leaf liveness ping in the ledger (a running leaf calls this to push back its deadline)."""
    outcome_store._safe_name(subplot_id, what="subplot_id")
    outcome_store.append_ledger(
        store, {"phase": "heartbeat", "kind": "liveness", "subplot_id": subplot_id, "at": float(at)}
    )


def _dispatch_at(store: Any) -> dict[str, float]:
    """subplot_id -> the ``at`` of its settled (``commit``) dispatch record (when the leaf was launched)."""
    out: dict[str, float] = {}
    for rec in outcome_store.read_ledger(store):
        if rec.get("kind") == "dispatch" and rec.get("phase") == "commit":
            sid = str(rec.get("subplot_id", ""))
            at = rec.get("at")
            if sid and isinstance(at, (int, float)) and not isinstance(at, bool):
                out[sid] = float(at)
    return out


def _last_heartbeat(store: Any) -> dict[str, float]:
    """subplot_id -> the **maximum** ``at`` of its ``heartbeat`` records (latest BY TIMESTAMP, not by
    ledger write order). Heartbeats are written by leaf processes NOT under the coordinator lease, so
    they can arrive out of order (a buffered/replayed flush) — taking the max ``at`` is robust to that.
    """
    out: dict[str, float] = {}
    for rec in outcome_store.read_ledger(store):
        if rec.get("kind") == "liveness" and rec.get("phase") == "heartbeat":
            sid = str(rec.get("subplot_id", ""))
            at = rec.get("at")
            if sid and isinstance(at, (int, float)) and not isinstance(at, bool):
                out[sid] = max(out.get(sid, float("-inf")), float(at))
    return out


def _is_stalled(node: Any, *, dispatched_at: float, last_beat: float | None, now: float) -> str:
    """Return a non-empty reason if the leaf has breached a liveness budget, else ''.

    ``heartbeat_seconds`` is checked against the **last activity** = ``max(dispatched_at, last
    heartbeat)`` — floored at the dispatch time so a **pre-dispatch heartbeat** (clock skew between the
    coordinator and a leaf process) can never make a freshly-launched leaf look idle. ``timeout_seconds``
    is checked against the **dispatch time** (absolute runtime). A node with neither budget is never
    stalled.
    """
    hb = node.heartbeat_seconds
    to = node.timeout_seconds
    if hb is not None:
        last_activity = max(dispatched_at, last_beat) if last_beat is not None else dispatched_at
        if now - last_activity > hb:
            gap = round(now - last_activity)
            return f"no heartbeat for {gap}s (> {hb}s budget) — leaf reclaimed (R31)"
    if to is not None and now - dispatched_at > to:
        ran = round(now - dispatched_at)
        return f"ran {ran}s (> {to}s timeout) — leaf reclaimed (R31)"
    return ""


def _record_terminal(store: Any, sid: str, reason: str) -> None:
    """Record the ``stalled`` terminal at a fresh attempt, idempotently (pages ONCE — the U6 pattern)."""
    existing = outcome_store.read_completion_events(store, sid)
    if any(e.state == STALLED_STATE for e in existing):
        return
    attempt = max((e.attempt for e in existing), default=0) + 1
    outcome_store.write_completion_event(
        store,
        outcome_store.CompletionEvent(
            subplot_id=sid,
            state=STALLED_STATE,
            idempotency_key=f"stalled:{sid}",
            attempt=attempt,
            payload={"reason": reason},
        ),
    )


def harvest_liveness(spec: Any, store: Any, *, now: float) -> dict[str, Any]:
    """One liveness pass for ``advance`` (R31): reclaim every hung dispatched leaf as ``stalled`` + cascade.

    Derived-on-read: for each node that is currently **dispatched** (a settled commit, not yet terminal),
    breach of ``heartbeat_seconds`` or ``timeout_seconds`` records the ``stalled`` terminal (idempotent ->
    pages once) and its downstream subtree cascades (R22 ``blocked_subtree``). Runs under the held
    coordinator lease (single-writer, R13). Returns ``{stalled, cascade_paused}``.
    """
    import outcome as outcome_engine

    states = outcome_engine.derive_states(spec, store)
    dispatched_at = _dispatch_at(store)
    last_beat = _last_heartbeat(store)
    stalled: list[str] = []
    for node in spec.nodes:
        sid = node.subplot_id
        if states.get(sid) != "dispatched":
            continue  # only a live, dispatched leaf can stall (terminal/ready/blocked cannot)
        at = dispatched_at.get(sid)
        if at is None:
            continue  # no dispatch timestamp (legacy record) -> cannot judge liveness, skip
        reason = _is_stalled(node, dispatched_at=at, last_beat=last_beat.get(sid), now=now)
        if reason:
            _record_terminal(store, sid, reason)
            stalled.append(sid)
    cascade = sorted(outcome_orchestrator.blocked_subtree(spec, set(stalled)))
    return {"stalled": stalled, "cascade_paused": cascade}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Outcome leaf liveness (U9/R31) — describe the policy."
    )
    parser.parse_args(argv)
    print(
        json.dumps(
            {
                "stalled_state": STALLED_STATE,
                "policy": "a dispatched leaf breaching heartbeat_seconds or timeout_seconds reaches the "
                "stalled terminal (idempotent -> pages once) and cascades to its downstream (R22/R31)",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
