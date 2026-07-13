#!/usr/bin/env python3
"""SPC (XmR) control charts over per-provider cost/latency run facts (#459 R5, T2-F5-7).

Shift detection, explicitly distinct from the staleness report (``engine_stale_report.py``):
SPC answers "did this provider's cost/latency time series SHIFT out of its own control band?"
(common-cause variation stays quiet), while staleness answers "which registry cells have no
recent corroborating evidence at all?". An individuals + moving-range (XmR) chart with two
conservative Western-Electric-style rules:

* rule 1 — any post-baseline point beyond ``centerline ± 2.66 × mR̄`` (LCL floored at 0);
* rule 4 — eight consecutive post-baseline points on one side of the centerline.

Derive-on-read and chain-verified first (a chain break RAISES — visible evidence failure).
A drift flag DEPRIORITIZES a provider at resolution time (reorder within an authored rating
band, never exclusion) and surfaces to `/retro` as a ``revalidate`` proposal — it never writes
``engine-registry.yaml`` ({#external-engines-never-gatekeepers}, #283). Metric values <= 0 are
excluded as unmeasured (``engine_dispatch._num`` writes 0.0 for absent metrics — a zero is
"no data", never a real observation).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_ledger  # noqa: E402

DEFAULT_BASELINE_N = 12
XMR_LIMIT_FACTOR = 2.66
RUN_LENGTH = 8
METRICS = ("cost", "latency_seconds")

STATUS_NO_DATA = "no-data"
STATUS_IN_CONTROL = "in-control"
STATUS_OUT_OF_CONTROL = "out-of-control"


class ControlChartError(ValueError):
    """A broken ledger chain or malformed control-chart input — a visible evidence failure."""


@dataclass(frozen=True)
class ChartVerdict:
    """One metric series' XmR verdict."""

    status: str
    centerline: float
    ucl: float
    lcl: float
    breach_indices: tuple[int, ...]
    rule: str


_NO_DATA = ChartVerdict(STATUS_NO_DATA, 0.0, 0.0, 0.0, (), "")


def control_chart(series: list[float], *, baseline_n: int = DEFAULT_BASELINE_N) -> ChartVerdict:
    """XmR verdict over ``series``: baseline the first ``baseline_n`` points, judge the rest.

    Fewer than ``baseline_n + 1`` points is ``no-data`` — never a flag from thin evidence.
    """
    if baseline_n < 2:
        raise ControlChartError("baseline_n must be at least 2")
    if len(series) < baseline_n + 1:
        return _NO_DATA
    baseline = series[:baseline_n]
    centerline = sum(baseline) / len(baseline)
    moving_ranges = [abs(b - a) for a, b in zip(baseline, baseline[1:], strict=False)]
    mr_bar = sum(moving_ranges) / len(moving_ranges)
    ucl = centerline + XMR_LIMIT_FACTOR * mr_bar
    lcl = max(0.0, centerline - XMR_LIMIT_FACTOR * mr_bar)

    rule1 = tuple(
        i
        for i, value in enumerate(series[baseline_n:], start=baseline_n)
        if value > ucl or value < lcl
    )
    if rule1:
        return ChartVerdict(
            STATUS_OUT_OF_CONTROL, centerline, ucl, lcl, rule1, "rule-1-beyond-limit"
        )

    run_side = 0
    run_start = baseline_n
    for i, value in enumerate(series[baseline_n:], start=baseline_n):
        side = 1 if value > centerline else -1 if value < centerline else 0
        if side != 0 and side == run_side:
            if i - run_start + 1 >= RUN_LENGTH:
                return ChartVerdict(
                    STATUS_OUT_OF_CONTROL,
                    centerline,
                    ucl,
                    lcl,
                    tuple(range(run_start, i + 1)),
                    "rule-4-run-of-8",
                )
        else:
            run_side = side
            run_start = i
            # A run of exactly RUN_LENGTH can only complete on a later point; length-1 never fires.
    return ChartVerdict(STATUS_IN_CONTROL, centerline, ucl, lcl, (), "")


def _verified_records(ledger: run_ledger.RunLedger) -> tuple[dict[str, Any], ...]:
    snapshot = run_ledger.read_snapshot(ledger)
    if not snapshot.report.ok:
        raise ControlChartError(
            f"run-fact chain verification failed: {snapshot.report.reason} "
            f"(record {snapshot.report.break_index})"
        )
    return snapshot.records


def _metric_value(fact: dict[str, Any], metric: str) -> float | None:
    value = fact.get(metric)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if float(value) > 0.0 else None  # <= 0 is "unmeasured", never observed


def provider_flags(
    ledger: run_ledger.RunLedger,
    *,
    baseline_n: int = DEFAULT_BASELINE_N,
) -> dict[str, dict[str, ChartVerdict]]:
    """Per-provider (``engine_id``, across variants) XmR verdicts for each metric series."""
    records = _verified_records(ledger)
    by_provider: dict[str, list[dict[str, Any]]] = {}
    for fact in records:
        if fact.get("kind") != "engine":
            continue
        engine_id = str(fact.get("engine", ""))
        if engine_id:
            by_provider.setdefault(engine_id, []).append(fact)

    out: dict[str, dict[str, ChartVerdict]] = {}
    for engine_id, facts in by_provider.items():
        ordered = sorted(facts, key=lambda f: str(f.get("at", "")))  # stable: ledger order on ties
        verdicts: dict[str, ChartVerdict] = {}
        for metric in METRICS:
            series = [v for f in ordered if (v := _metric_value(f, metric)) is not None]
            verdicts[metric] = control_chart(series, baseline_n=baseline_n)
        out[engine_id] = verdicts
    return out


def drift_flagged(
    ledger: run_ledger.RunLedger,
    *,
    baseline_n: int = DEFAULT_BASELINE_N,
) -> frozenset[str]:
    """Providers with any out-of-control metric — the resolution-time deprioritization input."""
    return frozenset(
        engine_id
        for engine_id, verdicts in provider_flags(ledger, baseline_n=baseline_n).items()
        if any(v.status == STATUS_OUT_OF_CONTROL for v in verdicts.values())
    )


def _verdict_payload(verdict: ChartVerdict) -> dict[str, Any]:
    return {
        "status": verdict.status,
        "centerline": round(verdict.centerline, 6),
        "ucl": round(verdict.ucl, 6),
        "lcl": round(verdict.lcl, 6),
        "breach_indices": list(verdict.breach_indices),
        "rule": verdict.rule,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SPC control charts over provider cost/latency run facts (#459 R5)."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    report_parser = commands.add_parser("report", help="emit per-provider XmR verdicts")
    report_parser.add_argument("--root", type=Path, default=Path("."), help="repository root")
    report_parser.add_argument("--baseline-n", type=int, default=DEFAULT_BASELINE_N)
    report_parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    try:
        ledger = run_ledger.RunLedger.resolve(args.root)
        flags = provider_flags(ledger, baseline_n=args.baseline_n)
    except Exception as exc:  # noqa: BLE001 - CLI boundary: named failure, non-zero exit
        print(f"CONTROL CHART ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        payload = {
            engine_id: {metric: _verdict_payload(v) for metric, v in verdicts.items()}
            for engine_id, verdicts in flags.items()
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif not flags:
        print("no engine dispatch telemetry yet")
    else:
        for engine_id in sorted(flags):
            for metric, verdict in flags[engine_id].items():
                suffix = f" ({verdict.rule})" if verdict.rule else ""
                print(f"{engine_id} {metric}: {verdict.status}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
