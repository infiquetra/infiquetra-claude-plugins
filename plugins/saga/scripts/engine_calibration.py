#!/usr/bin/env python3
"""`/retro` engine-registry calibration aggregator (#459 R6, T1-F3-7) — proposal-only, never a write.

Aggregates the four earned-ratings signal families — benchmark contradictions
(``engine_benchmark.py``), staleness verdicts (``engine_stale_report.py``), Elo divergences
(``capability_elo.py``), and SPC drift flags (``provider_control_chart.py``) — into one
``registry_calibration_proposal.v1`` that `/retro` Phase 1.11 reads and Phase 5(f) surfaces with
propose-diff-and-wait. Mirrors ``tier_efficacy.py``: a proposal engine that NEVER writes.

This module exposes **no write API for `engine-registry.yaml`** — ``report`` takes a loaded
``Registry`` and ``render_diff_preview`` opens the YAML read-only to show what would change.
``approval_required`` is always true: a proposal is never an authorization, and only a human
applies the hand-edit ({#external-engines-never-gatekeepers}, #283).

Deterministic per-cell aggregation precedence:

1. benchmark contradiction -> ``rating-change`` to the MEASURED rating (+ ``last_validated`` now);
2. staleness ``contradicted`` / Elo divergence / provider SPC drift -> ``revalidate`` (signal
   attached, no invented rating value);
3. staleness ``corroborated`` -> ``last-validated-bump`` to ``latest_corroborated_at``;
4. ``unexercised`` cells are listed as calibration *candidates*, not diffs;
5. no signals at all -> ``status: "no-proposal"`` (zero-data contract — never fabricated).

``CalibrationSignals`` is the runtime (R4/R5) consumption object: one chain-verified
``load_calibration`` read produces the Elo map + drift flags that
``engine_registry.ranked_candidates(..., calibration=...)`` uses to reorder WITHIN an authored
rating band — opt-in, deprioritize-never-exclude, and no I/O in the resolver hot path unless the
caller threads it explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capability_elo  # noqa: E402
import engine_stale_report  # noqa: E402
import provider_control_chart  # noqa: E402
import run_ledger  # noqa: E402
from engine_registry import Registry  # noqa: E402

CALIBRATION_PROPOSAL_SCHEMA = "registry_calibration_proposal.v1"
DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "references" / "engine-registry.yaml"


class CalibrationError(ValueError):
    """A malformed calibration input (chain breaks raise from the underlying readers)."""


@dataclass(frozen=True)
class CalibrationSignals:
    """The runtime earned-ratings signals object (duck-typed by ``ranked_candidates``)."""

    elo: Mapping[tuple[str, str], float] = field(default_factory=dict)
    drift_flagged: frozenset[str] = frozenset()

    def fingerprint(self) -> str:
        """Deterministic content hash — the resolver memo-key component."""
        payload = {
            "elo": {f"{key}::{capability}": value for (key, capability), value in self.elo.items()},
            "drift_flagged": sorted(self.drift_flagged),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def calibration_fingerprint(signals: CalibrationSignals | None) -> str:
    """The memo-key fingerprint (``""`` for ``None`` — the uncalibrated key)."""
    return "" if signals is None else signals.fingerprint()


def load_calibration(
    ledger: run_ledger.RunLedger,
    *,
    baseline_n: int = provider_control_chart.DEFAULT_BASELINE_N,
) -> CalibrationSignals:
    """One chain-verified read producing both runtime signals.

    Compute once per run and thread explicitly — never called from inside the resolver.
    """
    return CalibrationSignals(
        elo=capability_elo.scores(ledger),
        drift_flagged=provider_control_chart.drift_flagged(ledger, baseline_n=baseline_n),
    )


def _fact_date(at: str) -> str:
    try:
        return datetime.fromisoformat(at.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return ""


def _latest_benchmarks(
    records: tuple[dict[str, Any], ...],
    extra_results: list[dict[str, Any]] | None,
) -> dict[tuple[str, str], dict[str, Any]]:
    """The latest benchmark measurement per (engine_key, capability) cell."""
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for fact in records:
        if fact.get("kind") != "benchmark":
            continue
        engine_key = f"{fact.get('engine', '')}/{fact.get('variant', '')}"
        capability = str(fact.get("capability", ""))
        if not capability:
            continue
        key = (engine_key, capability)
        prior = latest.get(key)
        if prior is None or str(fact.get("at", "")) >= str(prior.get("at", "")):
            latest[key] = dict(fact)
    for result in extra_results or []:
        engine_key = str(result.get("engine_key", ""))
        capability = str(result.get("capability", ""))
        if engine_key and capability:
            latest[(engine_key, capability)] = dict(result)
    return latest


def report(
    registry: Registry,
    ledger: run_ledger.RunLedger,
    *,
    now: date | None = None,
    benchmark_results: list[dict[str, Any]] | None = None,
    min_matches: int = capability_elo.DEFAULT_MIN_MATCHES,
    baseline_n: int = provider_control_chart.DEFAULT_BASELINE_N,
) -> dict[str, Any]:
    """The aggregated ``registry_calibration_proposal.v1`` — derive-on-read, never a write."""
    today = now or date.today()
    records = engine_stale_report.verified_records(ledger)  # raises on a chain break (visible)
    stale = engine_stale_report.stale_report(registry, ledger, now=today)
    elo_signals = capability_elo.signals(ledger, registry, min_matches=min_matches)
    drift = provider_control_chart.drift_flagged(ledger, baseline_n=baseline_n)
    benchmarks = _latest_benchmarks(records, benchmark_results)

    elo_by_cell = {(s["engine_key"], s["capability"]): s for s in elo_signals}
    cells: list[dict[str, Any]] = []
    unexercised: list[dict[str, Any]] = []
    for stale_cell in stale["cells"]:
        engine_key = str(stale_cell["engine_key"])
        capability = str(stale_cell["capability"])
        cell_key = (engine_key, capability)
        verdict = str(stale_cell["verdict"])
        current = {
            "rating": _authored_rating(registry, engine_key, capability),
            "last_validated": stale_cell["last_validated"],
        }
        benchmark = benchmarks.get(cell_key)
        if benchmark is not None and "at" in benchmark:
            # A ledger benchmark older than the row's last_validated is pre-revalidation
            # history, not live disagreement — never propose from it.
            benchmark_date = _fact_date(str(benchmark.get("at", "")))
            if not benchmark_date or benchmark_date <= str(current["last_validated"]):
                benchmark = None
        elo_signal = elo_by_cell.get(cell_key)
        provider_drift = str(stale_cell["engine_id"]) in drift
        signals_block: dict[str, Any] = {
            "benchmark": _benchmark_signal(benchmark),
            "staleness": verdict,
            "elo": _elo_signal(elo_signal),
            "spc": "out-of-control" if provider_drift else None,
        }

        if benchmark is not None and benchmark.get("contradicts") is True:
            cells.append(
                _cell(
                    engine_key,
                    capability,
                    "rating-change",
                    current,
                    {
                        "rating": str(benchmark.get("measured_rating", "")),
                        "last_validated": today.isoformat(),
                    },
                    signals_block,
                )
            )
        elif verdict == "contradicted" or elo_signal is not None or provider_drift:
            cells.append(_cell(engine_key, capability, "revalidate", current, None, signals_block))
        elif verdict == "corroborated":
            bumped = _fact_date(str(stale_cell["evidence"].get("latest_corroborated_at", "")))
            if bumped and bumped > str(current["last_validated"]):
                cells.append(
                    _cell(
                        engine_key,
                        capability,
                        "last-validated-bump",
                        current,
                        {"rating": current["rating"], "last_validated": bumped},
                        signals_block,
                    )
                )
        else:
            unexercised.append({"engine_key": engine_key, "capability": capability})

    return {
        "schema": CALIBRATION_PROPOSAL_SCHEMA,
        "generated_at": today.isoformat(),
        "status": "proposal" if cells else "no-proposal",
        "approval_required": True,  # ALWAYS — a proposal is never an authorization
        "cells": cells,
        "unexercised": unexercised,
        "evidence": {"ledger_path": str(ledger.path), "chain_ok": True},
    }


def _authored_rating(registry: Registry, engine_key: str, capability: str) -> str:
    entry = registry.by_key(engine_key)
    claim = entry.capability_profile.get(capability, {})
    return str(claim.get("rating", ""))


def _benchmark_signal(benchmark: dict[str, Any] | None) -> dict[str, Any] | None:
    if benchmark is None:
        return None
    return {
        "suite_id": str(benchmark.get("suite_id", "")),
        "measured": str(benchmark.get("measured_rating", "")),
        "passed": benchmark.get("probes_passed"),
        "total": benchmark.get("probes_total"),
        "contradicts": bool(benchmark.get("contradicts")),
    }


def _elo_signal(signal: dict[str, Any] | None) -> dict[str, Any] | None:
    if signal is None:
        return None
    return {
        "elo": signal.get("elo"),
        "rival": signal.get("rival"),
        "rival_elo": signal.get("rival_elo"),
        "matches": signal.get("matches"),
    }


def _cell(
    engine_key: str,
    capability: str,
    action: str,
    current: dict[str, Any],
    proposed: dict[str, Any] | None,
    signals_block: dict[str, Any],
) -> dict[str, Any]:
    cell: dict[str, Any] = {
        "engine_key": engine_key,
        "capability": capability,
        "action": action,
        "current": current,
        "signals": signals_block,
    }
    if proposed is not None:
        cell["proposed"] = proposed
    return cell


def render_diff_preview(proposal: dict[str, Any], registry_path: str | Path) -> str:
    """A unified-diff-style PREVIEW of the proposed cell edits — READ ONLY.

    Reads the registry YAML only to confirm the current values it renders; the operator applies
    any edit by hand after `/retro` Phase 5(f). This function never writes.
    """
    if proposal.get("status") != "proposal" or not proposal.get("cells"):
        return "no calibration proposal -- no earned-ratings evidence disagrees with the registry."
    data = yaml.safe_load(Path(registry_path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CalibrationError(f"registry must be a mapping: {registry_path}")
    lines = [
        "Proposed engine-registry.yaml diff (PREVIEW ONLY -- a human applies it by hand;",
        "{#external-engines-never-gatekeepers}, #283):",
        "",
    ]
    for cell in proposal["cells"]:
        current = cell["current"]
        lines.append(f"  {cell['engine_key']} [{cell['capability']}] ({cell['action']}):")
        if cell["action"] == "revalidate":
            lines.append(
                f"    ! revalidate: rating {current['rating']}, "
                f"last_validated {current['last_validated']} "
                f"(signals: {_signal_summary(cell['signals'])})"
            )
            continue
        proposed = cell.get("proposed", {})
        lines.append(
            f"    - rating: {current['rating']} / last_validated: {current['last_validated']}"
        )
        lines.append(
            f"    + rating: {proposed.get('rating', current['rating'])} / "
            f"last_validated: {proposed.get('last_validated', current['last_validated'])}"
        )
    return "\n".join(lines)


def _signal_summary(signals_block: dict[str, Any]) -> str:
    parts = [f"staleness={signals_block.get('staleness')}"]
    if signals_block.get("elo") is not None:
        parts.append("elo-divergence")
    if signals_block.get("spc") is not None:
        parts.append("spc-drift")
    if signals_block.get("benchmark") is not None:
        parts.append("benchmark")
    return ", ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="/retro engine-registry calibration aggregator (#459 R6) — proposal-only."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("report", "emit the aggregated registry_calibration_proposal.v1"),
        ("preview", "render the read-only diff preview for /retro Phase 5(f)"),
    ):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("--root", type=Path, default=Path("."), help="repository root")
        sub.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
        sub.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    try:
        registry = Registry.load(args.registry)
        ledger = run_ledger.RunLedger.resolve(args.root)
        proposal = report(registry, ledger)
        if args.command == "preview":
            print(render_diff_preview(proposal, args.registry))
            return 0
    except Exception as exc:  # noqa: BLE001 - CLI boundary: named failure, non-zero exit
        print(f"CALIBRATION ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(proposal, indent=2, sort_keys=True))
    else:
        print(f"status: {proposal['status']} (approval_required: true)")
        for cell in proposal["cells"]:
            print(f"  {cell['engine_key']} [{cell['capability']}]: {cell['action']}")
        if proposal["unexercised"]:
            print(f"  unexercised cells: {len(proposal['unexercised'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
