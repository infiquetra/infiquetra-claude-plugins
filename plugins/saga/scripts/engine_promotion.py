#!/usr/bin/env python3
"""Assess probationary engine promotion from verified run-fact evidence."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_ledger  # noqa: E402
from engine_registry import Registry, RegistryError  # noqa: E402

DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "references" / "engine-registry.yaml"
REQUIRED_RUNS = 5


class PromotionError(ValueError):
    """The promotion target or its evidence cannot be assessed safely."""


@dataclass(frozen=True)
class PromotionAssessment:
    """One exact-variant, evidence-only promotion assessment."""

    engine_key: str
    required_runs: int
    matching_runs: int
    inspected_runs: int
    qualifying_runs: int
    inspected_run_keys: tuple[str | None, ...]
    eligible: bool
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready representation."""
        return {
            "eligible": self.eligible,
            "engine_key": self.engine_key,
            "inspected_run_keys": list(self.inspected_run_keys),
            "inspected_runs": self.inspected_runs,
            "matching_runs": self.matching_runs,
            "qualifying_runs": self.qualifying_runs,
            "reasons": list(self.reasons),
            "required_runs": self.required_runs,
        }


def assess_promotion(
    engine_key: str,
    *,
    registry_path: Path | str = DEFAULT_REGISTRY,
    ledger: run_ledger.RunLedger,
) -> PromotionAssessment:
    """Assess the five latest exact-variant facts without mutating registry or ledger."""
    engine_id, variant = _parse_engine_key(engine_key)
    normalized_key = f"{engine_id}/{variant}"
    try:
        registry = Registry.load(registry_path)
        entry = registry.by_key(normalized_key)
    except (RegistryError, UnicodeError, yaml.YAMLError) as exc:
        raise PromotionError(str(exc)) from exc
    if entry.trust_tier != "probation":
        raise PromotionError(
            f"engine variant {normalized_key!r} has trust_tier {entry.trust_tier!r}; "
            "promotion assessment is not applicable"
        )

    facts = _read_verified_snapshot(ledger)
    matches = [
        fact
        for fact in facts
        if fact.get("kind") == "engine"
        and fact.get("engine") == engine_id
        and fact.get("variant") == variant
    ]
    window = matches[-REQUIRED_RUNS:]
    reasons: list[str] = []
    if len(matches) < REQUIRED_RUNS:
        reasons.append(f"need {REQUIRED_RUNS} exact-variant engine facts; found {len(matches)}")

    qualifying = 0
    inspected_keys: list[str | None] = []
    seen_run_keys: set[str] = set()
    first_window_number = len(matches) - len(window) + 1
    for offset, fact in enumerate(window):
        raw_key = fact.get("bridge_run_key")
        run_key = raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None
        inspected_keys.append(run_key)
        problems: list[str] = []
        if fact.get("status") != "ok":
            problems.append(f"status={fact.get('status')!r}, expected 'ok'")
        if fact.get("proof_integrity_status") != "ok":
            problems.append(
                f"proof_integrity_status={fact.get('proof_integrity_status')!r}, expected 'ok'"
            )
        if run_key is None:
            problems.append("bridge_run_key is missing or empty")
        elif run_key in seen_run_keys:
            problems.append("bridge_run_key is duplicated in the promotion window")
        else:
            seen_run_keys.add(run_key)
        if problems:
            label = run_key or f"matching fact {first_window_number + offset}"
            reasons.append(f"{label}: {', '.join(problems)}")
        else:
            qualifying += 1

    eligible = len(window) == REQUIRED_RUNS and qualifying == REQUIRED_RUNS
    return PromotionAssessment(
        engine_key=normalized_key,
        required_runs=REQUIRED_RUNS,
        matching_runs=len(matches),
        inspected_runs=len(window),
        qualifying_runs=qualifying,
        inspected_run_keys=tuple(inspected_keys),
        eligible=eligible,
        reasons=tuple(reasons),
    )


def _parse_engine_key(engine_key: str) -> tuple[str, str]:
    value = engine_key.strip()
    engine_id, separator, variant = value.partition("/")
    if not separator or not engine_id or not variant or "/" in variant:
        raise PromotionError("engine key must use the exact <engine>/<variant> form")
    return engine_id, variant


def _read_verified_snapshot(ledger: run_ledger.RunLedger) -> list[dict[str, Any]]:
    try:
        before = run_ledger.read_facts(ledger)
        report = run_ledger.verify_chain(ledger)
        after = run_ledger.read_facts(ledger)
    except (run_ledger.RunLedgerError, UnicodeError) as exc:
        raise PromotionError(f"run-fact ledger is corrupt: {exc}") from exc
    if before != after:
        raise PromotionError(
            "run-fact ledger changed during assessment; retry with a stable ledger"
        )
    if not report.ok:
        record = "unknown" if report.break_index is None else str(report.break_index + 1)
        raise PromotionError(f"run-fact ledger chain failed at record {record}: {report.reason}")
    return cast(list[dict[str, Any]], after)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine_key", help="exact engine variant in <engine>/<variant> form")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="engine registry YAML")
    parser.add_argument(
        "--ledger",
        help="run-fact ledger JSONL (defaults to the current repository's shared ledger)",
    )
    parser.add_argument("--json", action="store_true", help="emit one JSON object")
    return parser


def _render_text(assessment: PromotionAssessment) -> str:
    disposition = "eligible" if assessment.eligible else "not eligible"
    keys = ", ".join(key or "<missing>" for key in assessment.inspected_run_keys) or "none"
    lines = [
        f"promotion {disposition}: {assessment.engine_key}",
        (
            f"matching={assessment.matching_runs} inspected={assessment.inspected_runs} "
            f"qualifying={assessment.qualifying_runs} required={assessment.required_runs}"
        ),
        f"bridge run keys: {keys}",
    ]
    lines.extend(f"reason: {reason}" for reason in assessment.reasons)
    if assessment.eligible:
        lines.append(
            "next step: change trust_tier from probation to advisory in a reviewed registry PR"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        ledger = (
            run_ledger.RunLedger(path=Path(args.ledger))
            if args.ledger
            else run_ledger.RunLedger.resolve(Path.cwd())
        )
        assessment = assess_promotion(
            args.engine_key,
            registry_path=args.registry,
            ledger=ledger,
        )
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"engine promotion assessment failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(assessment.as_dict(), sort_keys=True))
    else:
        print(_render_text(assessment))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
