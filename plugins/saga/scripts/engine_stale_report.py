#!/usr/bin/env python3
"""Ledger-fed engine-registry staleness report (#459 R3, T2-F4-7).

A pure derive-on-read reducer: it joins the hash-chained run-fact ledger (`run_ledger.py`)
against every `engine-registry.yaml` cell — one cell per `(engine_key, capability)` — and emits
one of three verdicts per cell:

* ``corroborated`` — at least one ok dispatch/benchmark fact strictly newer than the row's
  ``last_validated`` and nothing contradicting; carries ``latest_corroborated_at`` (the
  `/retro` calibration pass's `last_validated`-bump source).
* ``contradicted`` — a joined benchmark fact with ``contradicts: true``, or at least
  ``min_samples`` joined dispatch facts with a failure share at/above ``failure_share_floor``.
* ``unexercised`` — no joined evidence newer than ``last_validated`` (this is a *distinct*
  signal from SPC drift, which detects a shift in a live series; see
  ``provider_control_chart.py``). Below-threshold failure-only evidence also stays
  ``unexercised`` — too thin to contradict, nothing corroborates — with the raw counts carried
  in the evidence block so nothing is hidden.

The reducer chain-verifies the ledger first and RAISES on a break (a visible evidence failure,
never a silent skip). It never writes anything: every verdict terminates in a `/retro`-surfaced
proposal a human applies by hand ({#external-engines-never-gatekeepers}, #283).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_ledger  # noqa: E402
from engine_registry import EngineEntry, Registry  # noqa: E402

STALE_REPORT_SCHEMA = "engine_stale_report.v1"
DEFAULT_MIN_SAMPLES = 3
DEFAULT_FAILURE_SHARE_FLOOR = 0.5
DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "references" / "engine-registry.yaml"

_JOINED_KINDS = frozenset({"engine", "benchmark"})


class StaleReportError(ValueError):
    """A broken ledger chain or malformed staleness input — a visible evidence failure."""


def verified_records(ledger: run_ledger.RunLedger) -> tuple[dict[str, Any], ...]:
    """One chain-verified ledger snapshot; RAISES on any chain break (never silently skips)."""
    snapshot = run_ledger.read_snapshot(ledger)
    if not snapshot.report.ok:
        raise StaleReportError(
            f"run-fact chain verification failed: {snapshot.report.reason} "
            f"(record {snapshot.report.break_index})"
        )
    return snapshot.records


def _fact_date(fact: dict[str, Any]) -> date | None:
    raw = fact.get("at")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _joined_facts(
    records: tuple[dict[str, Any], ...],
    entry: EngineEntry,
    capability: str,
) -> list[dict[str, Any]]:
    """Facts joinable to one registry cell and strictly newer than its ``last_validated``."""
    joined: list[dict[str, Any]] = []
    for fact in records:
        if fact.get("kind") not in _JOINED_KINDS:
            continue
        if fact.get("engine") != entry.engine_id or fact.get("variant") != entry.variant:
            continue
        if fact.get("capability") != capability:
            continue
        fact_date = _fact_date(fact)
        if fact_date is None or fact_date <= entry.last_validated:
            continue
        joined.append(fact)
    return joined


def _dispatch_ok(fact: dict[str, Any]) -> bool:
    if fact.get("status") != "ok":
        return False
    return fact.get("proof_integrity_status") != "failed"


def _benchmark_ok(fact: dict[str, Any]) -> bool:
    return fact.get("contradicts") is False


def _cell_verdict(
    joined: list[dict[str, Any]],
    *,
    min_samples: int,
    failure_share_floor: float,
) -> tuple[str, dict[str, Any]]:
    dispatch_facts = [f for f in joined if f.get("kind") == "engine"]
    benchmark_facts = [f for f in joined if f.get("kind") == "benchmark"]
    ok_facts = [f for f in dispatch_facts if _dispatch_ok(f)] + [
        f for f in benchmark_facts if _benchmark_ok(f)
    ]
    fail_count = len(dispatch_facts) - sum(1 for f in dispatch_facts if _dispatch_ok(f))
    benchmark_contradictions = sum(1 for f in benchmark_facts if f.get("contradicts") is True)

    latest_ok = max((f.get("at", "") for f in ok_facts), default="")
    evidence = {
        "ok_count": len(ok_facts),
        "fail_count": fail_count,
        "benchmark_contradictions": benchmark_contradictions,
        "latest_corroborated_at": latest_ok,
    }

    if not joined:
        return "unexercised", evidence
    if benchmark_contradictions > 0:
        return "contradicted", evidence
    if (
        len(dispatch_facts) >= min_samples
        and fail_count / len(dispatch_facts) >= failure_share_floor
    ):
        return "contradicted", evidence
    if ok_facts:
        return "corroborated", evidence
    # Failure-only evidence below the sample floor: too thin to contradict, nothing corroborates.
    return "unexercised", evidence


def stale_report(
    registry: Registry,
    ledger: run_ledger.RunLedger,
    *,
    now: date | None = None,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    failure_share_floor: float = DEFAULT_FAILURE_SHARE_FLOOR,
) -> dict[str, Any]:
    """One verdict per registry cell — derive-on-read, chain-verified, never a write."""
    records = verified_records(ledger)
    cells: list[dict[str, Any]] = []
    any_evidence = False
    for entry in registry.engines:
        for capability in sorted(entry.capability_profile):
            joined = _joined_facts(records, entry, capability)
            verdict, evidence = _cell_verdict(
                joined, min_samples=min_samples, failure_share_floor=failure_share_floor
            )
            if joined:
                any_evidence = True
            cells.append(
                {
                    "engine_key": entry.key,
                    "engine_id": entry.engine_id,
                    "variant": entry.variant,
                    "capability": capability,
                    "verdict": verdict,
                    "last_validated": entry.last_validated.isoformat(),
                    "evidence": evidence,
                }
            )
    report: dict[str, Any] = {
        "schema": STALE_REPORT_SCHEMA,
        "generated_at": (now or date.today()).isoformat(),
        "chain_ok": True,
        "cells": cells,
    }
    if not any_evidence:
        report["note"] = "no dispatch evidence yet"
    return report


def _format_report(report: dict[str, Any]) -> str:
    lines = [f"engine stale report ({report['generated_at']})"]
    if report.get("note"):
        lines.append(f"note: {report['note']}")
    for cell in report["cells"]:
        evidence = cell["evidence"]
        lines.append(
            f"{cell['engine_key']} {cell['capability']}: {cell['verdict']} "
            f"(ok={evidence['ok_count']} fail={evidence['fail_count']} "
            f"benchmark_contradictions={evidence['benchmark_contradictions']} "
            f"last_validated={cell['last_validated']})"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ledger-fed engine-registry staleness report (#459 R3) — read-only."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    report_parser = commands.add_parser("report", help="emit per-cell staleness verdicts")
    report_parser.add_argument("--root", type=Path, default=Path("."), help="repository root")
    report_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    report_parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    report_parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    try:
        registry = Registry.load(args.registry)
        ledger = run_ledger.RunLedger.resolve(args.root)
        report = stale_report(registry, ledger, min_samples=args.min_samples)
    except Exception as exc:  # noqa: BLE001 - CLI boundary: named failure, non-zero exit
        print(f"STALE REPORT ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else _format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
