#!/usr/bin/env python3
"""Realized economics: per-subplot cost telemetry + the per-outcome rollup (U10 — R24/R7).

R24 is the **falsifiable proof** of the whole thesis (a coordinated DAG of leaf sagas beats one long
inline thread): the runner records, per subplot, the **executor used, rough token/cost, wall-clock,
operator touches, retries, and accepted evidence**, and rolls it up per outcome. This module is both
halves —

* the **producer** `record_cost` (a leaf saga calls it as it finishes — the coordinator never runs the
  leaf, R3, so the leaf reports its own realized cost into the shared store), and
* the **consumer** `rollup`, which aggregates the per-subplot telemetry into the per-outcome answer,
  including the load-bearing **DAG-vs-one-thread** comparison: the DAG's **critical-path** wall (the
  parallel lower bound) vs the **serial** sum (one long thread), so the rollup answers *"did the DAG beat
  one long thread?"* with real numbers, not a slogan.

Honesty rules (the U8 stance, kept): missing telemetry renders **"no data yet"** (an empty rollup), never
a fabricated zero; a leaf that recorded nothing is COUNTED as missing, not summed as 0. Cost recorded
against a **pruned** subplot (no longer in the spec) is reconciled into a **`sunk`** bucket (the
pruned-node cost reconcile U7 deferred, R33) — accounted, never silently dropped.

The materialized rollup is written into the canonical `spec.cost_rollup` (R26) by a `cost_processor` the
`advance` loop runs, so the U8 report renders it with **no U8->U10 code dependency** (the edge is
U10 -> spec -> U8, never back). House pattern: pure functions over explicit values, `outcome` imported
lazily to avoid a cycle, no I/O at import.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome_store  # noqa: E402  (after the sys.path shim, by design)

# The numeric, summed-across-subplots cost fields (R24). ``executor`` (categorical) + ``evidence`` (list)
# are tracked separately. ``wall_seconds`` is summed for the SERIAL (one-thread) figure and chained for
# the PARALLEL (critical-path) figure.
_NUMERIC_FIELDS = ("tokens", "wall_seconds", "operator_touches", "retries")


def record_cost(
    store: Any,
    subplot_id: str,
    *,
    executor: str = "",
    tokens: float | None = None,
    wall_seconds: float | None = None,
    operator_touches: int | None = None,
    retries: int | None = None,
    evidence: str = "",
    at: float | None = None,
) -> None:
    """Record a subplot's realized cost telemetry (R24) — the leaf saga calls this as it finishes.

    A snapshot of the leaf's CURRENT realized totals; the latest record per subplot wins (a single leaf
    process writes its own cost serially, so write order is causal — but ``rollup`` still prefers the max
    ``at`` when present, per the append-only-ledger discipline). Only non-None fields are stored, so a
    partial report does not zero a field a later report would set.
    """
    outcome_store._safe_name(subplot_id, what="subplot_id")
    record: dict[str, Any] = {
        "phase": "cost",
        "kind": "cost",
        "subplot_id": subplot_id,
        "executor": executor,
        "evidence": evidence,
    }
    for field_name, value in (
        ("tokens", tokens),
        ("wall_seconds", wall_seconds),
        ("operator_touches", operator_touches),
        ("retries", retries),
    ):
        if value is not None:
            record[field_name] = value
    if at is not None:
        # Only a REAL timestamp is stored (a bool/str ``at`` is a caller error, not a 1.0/0.0 epoch or an
        # uncaught float() crash) — so the producer agrees with the consumer's "is this a timestamp" guard.
        if isinstance(at, bool) or not isinstance(at, (int, float)):
            raise ValueError(f"record_cost: at must be a real timestamp (got {type(at).__name__})")
        record["at"] = float(at)
    outcome_store.append_ledger(store, record)


def _at_of(rec: dict[str, Any]) -> float | None:
    """The record's ``at`` as a real timestamp, or None (a bool/str/absent ``at`` is NOT a timestamp)."""
    at = rec.get("at")
    return float(at) if isinstance(at, (int, float)) and not isinstance(at, bool) else None


def _latest_costs(store: Any) -> dict[str, dict[str, Any]]:
    """subplot_id -> its latest cost record, iterating the ledger in write order.

    The winner per subplot: when BOTH the candidate and the current winner are timestamped, the larger
    ``at`` wins (out-of-order safe — the append-only-ledger discipline); when EITHER is untimestamped,
    **write-order-last** wins (write order is causal, so a later untimestamped report supersedes an
    earlier timestamped one rather than being silently locked out).
    """
    latest: dict[str, dict[str, Any]] = {}
    for rec in outcome_store.read_ledger(store):
        if rec.get("kind") != "cost" or rec.get("phase") != "cost":
            continue
        sid = str(rec.get("subplot_id", ""))
        if not sid:
            continue
        cur = latest.get(sid)
        if cur is None:
            latest[sid] = rec
            continue
        rec_at, cur_at = _at_of(rec), _at_of(cur)
        if rec_at is not None and cur_at is not None:
            if (
                rec_at >= cur_at
            ):  # both timestamped -> newer wins; an out-of-order older one is ignored
                latest[sid] = rec
        else:
            latest[sid] = rec  # either untimestamped -> write-order-last wins (causal)
    return latest


def subplot_cost(store: Any, subplot_id: str) -> dict[str, Any]:
    """The realized cost telemetry for one subplot (empty dict if none recorded)."""
    return dict(_latest_costs(store).get(subplot_id, {}))


def _num(rec: dict[str, Any], field_name: str) -> float | None:
    val = rec.get(field_name)
    return float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else None


def critical_path_wall(spec: Any, wall_by_sid: dict[str, float]) -> float:
    """The longest dependency chain by ``wall_seconds`` — the DAG's parallel-wall lower bound.

    A node with no recorded wall contributes 0 to the path (it cannot inflate the parallel estimate).
    Computed over the spec's declared edges in dependency order (the spec is acyclic — ``validate``).
    """
    best: dict[str, float] = {}
    # spec.nodes are not guaranteed topologically sorted; iterate layers for a correct longest-path.
    import outcome_spec

    for layer in outcome_spec.dependency_layers(spec):
        for sid in layer:
            node = spec.node_by_id(sid)
            deps = node.depends_on if node is not None else []
            upstream = max((best.get(d, 0.0) for d in deps), default=0.0)
            best[sid] = upstream + wall_by_sid.get(sid, 0.0)
    return max(best.values(), default=0.0)


def rollup(spec: Any, store: Any) -> dict[str, Any]:
    """The per-outcome realized-cost rollup (R24) — empty ``{}`` when NO leaf has recorded cost.

    Sums the numeric fields across the spec's subplots, tallies executors, and computes the
    **DAG-vs-one-thread** comparison: ``wall_seconds_parallel`` (the critical path) vs
    ``wall_seconds_serial`` (the sum) with ``beat_one_thread`` = parallel < serial. ``leaves_with_cost`` /
    ``leaves_total`` make missing telemetry explicit (a leaf with no record is NOT summed as 0). Cost
    recorded against a subplot no longer in the spec (pruned) is reconciled into ``sunk`` (R33), never
    dropped.
    """
    costs = _latest_costs(store)
    spec_ids = {n.subplot_id for n in spec.nodes}

    # Per-field VALUES collected per subplot, so a field with NO contributor is OMITTED (never emitted as
    # a fabricated 0.0) — the U8 honesty stance at per-field granularity, not just whole-rollup.
    field_values: dict[str, list[float]] = {f: [] for f in _NUMERIC_FIELDS}
    by_executor: dict[str, int] = {}
    wall_by_sid: dict[str, float] = {}
    leaves_with_cost = 0
    for node in spec.nodes:
        rec = costs.get(node.subplot_id)
        if not rec:
            continue
        leaves_with_cost += 1
        for f in _NUMERIC_FIELDS:
            v = _num(rec, f)
            if v is not None:
                field_values[f].append(v)
        wall = _num(rec, "wall_seconds")
        if wall is not None:
            wall_by_sid[node.subplot_id] = wall
        ex = str(rec.get("executor", "")) or "unknown"
        by_executor[ex] = by_executor.get(ex, 0) + 1

    # Sunk cost (R33): telemetry against pruned subplots no longer in the spec — accounted, not dropped.
    sunk_values: dict[str, list[float]] = {f: [] for f in _NUMERIC_FIELDS}
    sunk_ids: list[str] = []
    for sid, rec in costs.items():
        if sid in spec_ids:
            continue
        sunk_ids.append(sid)
        for f in _NUMERIC_FIELDS:
            v = _num(rec, f)
            if v is not None:
                sunk_values[f].append(v)

    if leaves_with_cost == 0 and not sunk_ids:
        return {}  # no telemetry at all -> the U8 report renders "no data yet" (never a fabricated zero)

    result: dict[str, Any] = {
        "by_executor": by_executor,
        "leaves_with_cost": leaves_with_cost,
        "leaves_total": len(spec.nodes),
    }
    # Emit a numeric total ONLY when at least one leaf reported it (an omitted field is "no data yet",
    # never a hard 0.0). math.fsum is order-independent so the totals do not drift with declaration order.
    for f in ("tokens", "operator_touches", "retries"):
        if field_values[f]:
            result[f] = math.fsum(field_values[f])
    if field_values["wall_seconds"]:
        serial = math.fsum(field_values["wall_seconds"])
        parallel = critical_path_wall(spec, wall_by_sid)
        result["wall_seconds_serial"] = serial
        result["wall_seconds_parallel"] = parallel
        # parallel <= serial always; a real DAG win is serial EXCEEDING parallel beyond float noise (a
        # pure serial chain is parallel==serial -> not a win, even with 1-ULP accumulation-order drift).
        result["beat_one_thread"] = bool(serial - parallel > 1e-9 * max(abs(serial), 1.0))
    if sunk_ids:
        sunk: dict[str, Any] = {"subplots": sorted(sunk_ids)}
        for f in _NUMERIC_FIELDS:
            if sunk_values[f]:
                sunk[f] = math.fsum(sunk_values[f])
        result["sunk"] = sunk
    return result


def materialize(spec: Any, store: Any) -> bool:
    """Recompute the rollup and write it into ``spec.cost_rollup`` IF it changed. Returns True if changed.

    The producer->spec edge that lets the U8 report render the realized cost with no U8->U10 dependency.
    Guarded on change so it does not churn the canonical spec every tick.
    """
    new = rollup(spec, store)
    if new == spec.cost_rollup:
        return False
    spec.cost_rollup = new
    return True


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Outcome economics rollup (U10/R24) — describe the fields."
    )
    parser.parse_args(argv)
    print(
        json.dumps(
            {
                "per_subplot": ["executor", *_NUMERIC_FIELDS, "evidence"],
                "rollup": "sums per outcome + DAG-vs-one-thread (critical-path parallel vs serial sum); "
                "missing telemetry -> 'no data yet'; pruned-node cost -> sunk (R33)",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
