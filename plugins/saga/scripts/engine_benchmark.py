#!/usr/bin/env python3
"""Fixed-suite engine benchmark harness (#459 R2, T2-F1-7) — active measurement, proposal-only.

Distinct from the passive telemetry ledger: this harness RUNS a real query against a real engine
(operator-invoked via ``--runner-cmd``; the runner is injected in library use) and grades the
output with DETERMINISTIC string checks only (``contains`` / ``regex`` / ``json-parses``) — no
LLM-graded scoring, so no external engine ever judges anything
({#external-engines-never-gatekeepers}, #283; nuanced judgment stays with the human reading the
`/retro` proposal). The measured pass share maps to a ``WEAK``/``MODERATE``/``STRONG`` rating via
the suite's thresholds; a measured-vs-claimed contradiction emits a
``registry_calibration_proposal.v1`` CELL — never a write. NO code path in this module opens
``engine-registry.yaml`` for writing; suite probes are versioned by immutable ``suite_id``
(editing probes requires a new ``suite_id`` — see ``references/benchmark-loop.md``).
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess  # noqa: S404 - operator-invoked live runner, shell=False, split argv
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_ledger  # noqa: E402
from engine_registry import RATINGS, EngineEntry, Registry  # noqa: E402

BENCHMARK_SUITE_SCHEMA = "benchmark_suite.v1"
CALIBRATION_PROPOSAL_SCHEMA = "registry_calibration_proposal.v1"
GRADER_KINDS = ("contains", "regex", "json-parses")
DEFAULT_SUITE = Path(__file__).resolve().parent.parent / "references" / "benchmark-suite.yaml"
DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "references" / "engine-registry.yaml"
_RUNNER_TIMEOUT_SECONDS = 600

Runner = Callable[[EngineEntry, str], str]


class BenchmarkError(ValueError):
    """A malformed suite, probe, or benchmark input."""


@dataclass(frozen=True)
class Probe:
    """One deterministic eval probe."""

    probe_id: str
    prompt: str
    grader_kind: str
    grader_value: str


@dataclass(frozen=True)
class Suite:
    """One versioned, immutable per-capability eval suite."""

    suite_id: str
    capability: str
    thresholds: dict[str, float]
    probes: tuple[Probe, ...]


@dataclass(frozen=True)
class BenchmarkResult:
    """One measured suite run against one registry row."""

    engine_key: str
    engine_id: str
    variant: str
    capability: str
    suite_id: str
    probes_total: int
    probes_passed: int
    measured_rating: str
    claimed_rating: str
    contradicts: bool


def _parse_probe(raw: Any, where: str) -> Probe:
    if not isinstance(raw, dict):
        raise BenchmarkError(f"{where}: probe must be a mapping")
    probe_id = raw.get("id")
    prompt = raw.get("prompt")
    grader = raw.get("grader")
    if not isinstance(probe_id, str) or not probe_id:
        raise BenchmarkError(f"{where}: probe id must be a non-empty string")
    if not isinstance(prompt, str) or not prompt:
        raise BenchmarkError(f"{where}: probe {probe_id!r} prompt must be a non-empty string")
    if not isinstance(grader, dict):
        raise BenchmarkError(f"{where}: probe {probe_id!r} grader must be a mapping")
    kind = grader.get("kind")
    if kind not in GRADER_KINDS:
        raise BenchmarkError(
            f"{where}: probe {probe_id!r} grader kind {kind!r} not in {GRADER_KINDS}"
        )
    value = ""
    if kind == "contains":
        value = grader.get("value", "")
        if not isinstance(value, str) or not value:
            raise BenchmarkError(f"{where}: probe {probe_id!r} contains grader needs a value")
    elif kind == "regex":
        value = grader.get("pattern", "")
        if not isinstance(value, str) or not value:
            raise BenchmarkError(f"{where}: probe {probe_id!r} regex grader needs a pattern")
        try:
            re.compile(value)
        except re.error as exc:
            raise BenchmarkError(
                f"{where}: probe {probe_id!r} regex pattern is invalid: {exc}"
            ) from exc
    return Probe(probe_id=probe_id, prompt=prompt, grader_kind=str(kind), grader_value=str(value))


def _parse_thresholds(raw: Any, where: str) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise BenchmarkError(f"{where}: thresholds must be a mapping")
    thresholds: dict[str, float] = {}
    for rating in ("STRONG", "MODERATE"):
        value = raw.get(rating)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BenchmarkError(f"{where}: thresholds must set a numeric {rating} floor")
        if not 0.0 < float(value) <= 1.0:
            raise BenchmarkError(f"{where}: {rating} floor must be in (0, 1]")
        thresholds[rating] = float(value)
    if thresholds["STRONG"] <= thresholds["MODERATE"]:
        raise BenchmarkError(f"{where}: STRONG floor must exceed the MODERATE floor")
    return thresholds


def load_suites(path: str | Path = DEFAULT_SUITE) -> dict[str, Suite]:
    """Load and strictly validate the fixed suite fixture, keyed by capability."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != BENCHMARK_SUITE_SCHEMA:
        raise BenchmarkError(f"benchmark suite must declare schema {BENCHMARK_SUITE_SCHEMA!r}")
    raw_suites = data.get("suites")
    if not isinstance(raw_suites, list) or not raw_suites:
        raise BenchmarkError("benchmark suite fixture needs a non-empty suites list")
    suites: dict[str, Suite] = {}
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_suites):
        where = f"suite[{index}]"
        if not isinstance(raw, dict):
            raise BenchmarkError(f"{where}: suite must be a mapping")
        suite_id = raw.get("suite_id")
        capability = raw.get("capability")
        if not isinstance(suite_id, str) or not suite_id:
            raise BenchmarkError(f"{where}: suite_id must be a non-empty string")
        if suite_id in seen_ids:
            raise BenchmarkError(f"{where}: duplicate suite_id {suite_id!r}")
        seen_ids.add(suite_id)
        if not isinstance(capability, str) or not capability:
            raise BenchmarkError(f"{where}: capability must be a non-empty string")
        if capability in suites:
            raise BenchmarkError(f"{where}: duplicate capability {capability!r}")
        raw_probes = raw.get("probes")
        if not isinstance(raw_probes, list) or not raw_probes:
            raise BenchmarkError(f"{where}: probes must be a non-empty list")
        suites[capability] = Suite(
            suite_id=suite_id,
            capability=capability,
            thresholds=_parse_thresholds(raw.get("thresholds"), where),
            probes=tuple(_parse_probe(p, where) for p in raw_probes),
        )
    return suites


def load_suite(capability: str, path: str | Path = DEFAULT_SUITE) -> Suite:
    suites = load_suites(path)
    suite = suites.get(capability)
    if suite is None:
        raise BenchmarkError(
            f"no benchmark suite for capability {capability!r} (available: {sorted(suites)})"
        )
    return suite


def grade(probe: Probe, output: str) -> bool:
    """Deterministic string-check grading only — never an LLM judgment."""
    if not isinstance(output, str):
        return False
    if probe.grader_kind == "contains":
        return probe.grader_value in output
    if probe.grader_kind == "regex":
        return re.search(probe.grader_value, output) is not None
    if probe.grader_kind == "json-parses":
        try:
            json.loads(output)
        except (json.JSONDecodeError, ValueError):
            return False
        return True
    raise BenchmarkError(f"unknown grader kind {probe.grader_kind!r}")


def measured_rating(passed: int, total: int, thresholds: dict[str, float]) -> str:
    """Pass-share -> rating via the suite's floors (below MODERATE is WEAK)."""
    if total <= 0:
        raise BenchmarkError("measured_rating needs at least one probe")
    share = passed / total
    if share >= thresholds["STRONG"]:
        return "STRONG"
    if share >= thresholds["MODERATE"]:
        return "MODERATE"
    return "WEAK"


def run_suite(
    entry: EngineEntry,
    suite: Suite,
    runner: Runner,
    *,
    ledger: run_ledger.RunLedger | None = None,
    subplot_id: str = "",
    at: str = "",
) -> BenchmarkResult:
    """Run every probe through the injected runner and grade deterministically.

    When ``ledger`` + ``subplot_id`` + ``at`` are all supplied (the same telemetry-only trio as
    ``engine_dispatch.dispatch``), one ``benchmark`` run fact is appended; otherwise no I/O
    happens at all. The registry row is read-only input — this function NEVER writes it.
    """
    claim = entry.capability_profile.get(suite.capability)
    if not isinstance(claim, dict) or "rating" not in claim:
        raise BenchmarkError(
            f"{entry.key} does not claim capability {suite.capability!r}; nothing to measure"
        )
    claimed = str(claim["rating"])
    if claimed not in RATINGS:
        raise BenchmarkError(f"{entry.key} carries unknown rating {claimed!r}")
    passed = sum(1 for probe in suite.probes if grade(probe, runner(entry, probe.prompt)))
    measured = measured_rating(passed, len(suite.probes), suite.thresholds)
    result = BenchmarkResult(
        engine_key=entry.key,
        engine_id=entry.engine_id,
        variant=entry.variant,
        capability=suite.capability,
        suite_id=suite.suite_id,
        probes_total=len(suite.probes),
        probes_passed=passed,
        measured_rating=measured,
        claimed_rating=claimed,
        contradicts=measured != claimed,
    )
    if ledger is not None and subplot_id and at:
        run_ledger.append_fact(
            ledger,
            run_ledger.build_fact(
                "benchmark",
                subplot_id=subplot_id,
                at=at,
                engine=result.engine_id,
                variant=result.variant,
                capability=result.capability,
                suite_id=result.suite_id,
                probes_total=result.probes_total,
                probes_passed=result.probes_passed,
                measured_rating=result.measured_rating,
                claimed_rating=result.claimed_rating,
                contradicts=result.contradicts,
            ),
        )
    return result


def proposal(
    result: BenchmarkResult,
    entry: EngineEntry,
    *,
    now: date | None = None,
) -> dict[str, Any] | None:
    """A `registry_calibration_proposal.v1` CELL when measured contradicts claimed, else None.

    A proposal is never an authorization: ``approval_required`` is always true, and applying it
    is a human hand-edit surfaced through `/retro` Phase 5(f) — this module has no write path.
    """
    if not result.contradicts:
        return None
    return {
        "engine_key": entry.key,
        "capability": result.capability,
        "action": "rating-change",
        "approval_required": True,
        "current": {
            "rating": result.claimed_rating,
            "last_validated": entry.last_validated.isoformat(),
        },
        "proposed": {
            "rating": result.measured_rating,
            "last_validated": (now or date.today()).isoformat(),
        },
        "signals": {
            "benchmark": {
                "suite_id": result.suite_id,
                "measured": result.measured_rating,
                "passed": result.probes_passed,
                "total": result.probes_total,
            }
        },
    }


def _command_runner(command: str) -> Runner:
    """A live operator-supplied runner: the probe prompt on stdin, the engine's reply on stdout."""
    argv = shlex.split(command)
    if not argv:
        raise BenchmarkError("--runner-cmd must be a non-empty command")

    def run(entry: EngineEntry, prompt: str) -> str:
        completed = subprocess.run(  # noqa: S603 - operator-invoked, shell=False, split argv
            argv,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=_RUNNER_TIMEOUT_SECONDS,
            check=False,
        )
        return completed.stdout

    return run


def _resolve_entry(registry: Registry, engine: str) -> EngineEntry:
    if "/" in engine:
        return registry.by_key(engine)
    return registry.by_engine(engine)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fixed-suite engine benchmark harness (#459 R2) — proposal-only, never a write."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="run one capability suite against one engine")
    run_parser.add_argument("--engine", required=True, help="engine_id or engine_id/variant")
    run_parser.add_argument("--capability", required=True)
    run_parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    run_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    run_parser.add_argument(
        "--runner-cmd",
        required=True,
        help="live runner command (probe prompt on stdin, engine reply on stdout)",
    )
    run_parser.add_argument("--root", type=Path, default=Path("."), help="repository root")
    run_parser.add_argument(
        "--ledger", action="store_true", help="append a benchmark run fact to the run ledger"
    )
    run_parser.add_argument("--subplot-id", default="benchmark-cli")
    run_parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    try:
        registry = Registry.load(args.registry)
        entry = _resolve_entry(registry, args.engine)
        suite = load_suite(args.capability, args.suite)
        ledger = run_ledger.RunLedger.resolve(args.root) if args.ledger else None
        at = f"{date.today().isoformat()}T00:00:00Z" if args.ledger else ""
        result = run_suite(
            entry,
            suite,
            _command_runner(args.runner_cmd),
            ledger=ledger,
            subplot_id=args.subplot_id if args.ledger else "",
            at=at,
        )
        cell = proposal(result, entry)
    except Exception as exc:  # noqa: BLE001 - CLI boundary: named failure, non-zero exit
        print(f"BENCHMARK ERROR: {exc}", file=sys.stderr)
        return 2
    payload: dict[str, Any] = {
        "engine_key": result.engine_key,
        "capability": result.capability,
        "suite_id": result.suite_id,
        "probes_passed": result.probes_passed,
        "probes_total": result.probes_total,
        "measured_rating": result.measured_rating,
        "claimed_rating": result.claimed_rating,
        "contradicts": result.contradicts,
        "proposal": cell,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"{result.engine_key} {result.capability}: measured {result.measured_rating} "
            f"({result.probes_passed}/{result.probes_total}) vs claimed {result.claimed_rating}"
        )
        if cell is not None:
            print(
                "PROPOSAL (human-applied via /retro, never a write): "
                f"{cell['engine_key']} {cell['capability']} rating "
                f"{cell['current']['rating']} -> {cell['proposed']['rating']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
