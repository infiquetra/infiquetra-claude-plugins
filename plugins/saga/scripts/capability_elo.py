#!/usr/bin/env python3
"""Elo-style per-(engine, capability) ratings from live reconciliation outcomes (#459 R4, T2-F5-5).

Derive-on-read: scores are a chronological fold over head-to-head matches derived from validated
``reconciliation`` run facts — there is NO persisted score file (the run-ledger "no committed
summary" discipline). Elo learns from **live** reconciliation win/loss outcomes; the benchmark
harness (``engine_benchmark.py``) actively runs a **fixed** suite. Both feed `/retro` proposals;
neither substitutes for the other, and neither ever writes ``engine-registry.yaml``
({#external-engines-never-gatekeepers}, #283) — an Elo divergence only ever proposes
``revalidate`` with a direction, never a concrete rating value (rating values come only from
measured benchmark evidence).

Match derivation needs the optional ``member_index`` reconciliation-fact field (panel-member
attribution, appended by ``engine_dispatch.dispatch_advisory_panel`` since #459): a solo
reconciliation produces NO match — no synthetic opponents, no fabricated signal. Until real
panels run with attribution, ``scores`` legitimately reports no data; the signal accrues over
time (the same posture as `/retro` Phase 1.6/1.10 telemetry).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reconcile  # noqa: E402
import run_ledger  # noqa: E402
from engine_registry import _RATING_SCORE, Registry  # noqa: E402

ELO_BASE = 1200.0
K = 32.0
DEFAULT_MIN_MATCHES = 5
DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "references" / "engine-registry.yaml"

# Explicit intent -> registry-capability attribution. Intents with no clean mapping are SKIPPED
# and counted in ``MatchDerivation.unattributed`` (zero-data honesty — never guessed). "offload"
# spans too many capabilities to attribute one cell; second-opinion maps 1:1; divergence review
# (independent takes compared adversarially) attributes to adversarial-review.
INTENT_CAPABILITY = {
    "second-opinion": "second-opinion",
    "divergence": "adversarial-review",
}

_EMPTY_FINDING_PREFIX = "panel-empty:"


class CapabilityEloError(ValueError):
    """A malformed Elo input (distinct from a ledger chain break, which reconcile raises)."""


@dataclass(frozen=True)
class Match:
    """One head-to-head reconciliation outcome between two panel members."""

    capability: str
    winner: str
    loser: str
    draw: bool
    at: str


@dataclass(frozen=True)
class MatchDerivation:
    """Derived matches plus the count of reconciliations skipped for unmapped intents."""

    matches: tuple[Match, ...]
    unattributed: int


def expected(rating_a: float, rating_b: float) -> float:
    """Textbook Elo expected score of A against B."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def apply_match(scores: dict[tuple[str, str], float], match: Match) -> None:
    """Fold one match into ``scores`` (keyed ``(engine_key, capability)``), mutating in place."""
    key_winner = (match.winner, match.capability)
    key_loser = (match.loser, match.capability)
    rating_winner = scores.get(key_winner, ELO_BASE)
    rating_loser = scores.get(key_loser, ELO_BASE)
    score_winner = 0.5 if match.draw else 1.0
    scores[key_winner] = rating_winner + K * (score_winner - expected(rating_winner, rating_loser))
    scores[key_loser] = rating_loser + K * (
        (1.0 - score_winner) - expected(rating_loser, rating_winner)
    )


def _survival_share(
    member: str,
    member_index: dict[str, list[str]],
    statuses: dict[str, str],
) -> float:
    """A member's reconciled share over its attributed non-empty findings (0.0 when none)."""
    attributed = [
        finding_id
        for finding_id, members in member_index.items()
        if member in members and not finding_id.startswith(_EMPTY_FINDING_PREFIX)
    ]
    if not attributed:
        return 0.0
    reconciled = sum(
        1
        for finding_id in attributed
        if statuses.get(finding_id) == reconcile.ReconciliationStatus.RECONCILED.value
    )
    return reconciled / len(attributed)


def derive_matches(reconciliation_facts: list[dict[str, Any]]) -> MatchDerivation:
    """Derive pairwise matches from validated reconciliation facts (head-to-head evidence only).

    Deduplicates by ``reconciliation_id`` using the RECONCILE-action fact; requires a
    ``member_index`` with at least two distinct members (a solo reconciliation is no match);
    skips-and-counts intents outside :data:`INTENT_CAPABILITY`.
    """
    matches: list[Match] = []
    unattributed = 0
    seen: set[str] = set()
    for fact in reconciliation_facts:
        if fact.get("action") != reconcile.ReconciliationAction.RECONCILE.value:
            continue
        reconciliation_id = str(fact.get("reconciliation_id", ""))
        if not reconciliation_id or reconciliation_id in seen:
            continue
        seen.add(reconciliation_id)
        member_index = fact.get("member_index")
        if not isinstance(member_index, dict):
            continue
        members = sorted({m for member_list in member_index.values() for m in member_list})
        if len(members) < 2:
            continue
        capability = INTENT_CAPABILITY.get(str(fact.get("intent", "")))
        if capability is None:
            unattributed += 1
            continue
        statuses = {
            str(item["source_finding_id"]): str(item["status"]) for item in fact.get("items", [])
        }
        shares = {member: _survival_share(member, member_index, statuses) for member in members}
        at = str(fact.get("at", ""))
        for i, member_a in enumerate(members):
            for member_b in members[i + 1 :]:
                share_a, share_b = shares[member_a], shares[member_b]
                if share_a == share_b:
                    matches.append(Match(capability, member_a, member_b, True, at))
                elif share_a > share_b:
                    matches.append(Match(capability, member_a, member_b, False, at))
                else:
                    matches.append(Match(capability, member_b, member_a, False, at))
    return MatchDerivation(matches=tuple(matches), unattributed=unattributed)


def match_counts(derivation: MatchDerivation) -> dict[tuple[str, str], int]:
    """Matches per (engine_key, capability) cell — the ``min_matches`` evidence floor input."""
    counts: dict[tuple[str, str], int] = {}
    for match in derivation.matches:
        for member in (match.winner, match.loser):
            key = (member, match.capability)
            counts[key] = counts.get(key, 0) + 1
    return counts


def derive(ledger: run_ledger.RunLedger) -> MatchDerivation:
    """Chain-verified read (via ``reconcile.read_reconciliation_facts``) plus match derivation."""
    return derive_matches(reconcile.read_reconciliation_facts(ledger))


def scores(ledger: run_ledger.RunLedger) -> dict[tuple[str, str], float]:
    """Elo scores keyed ``(engine_key, capability)`` — a chronological fold, never persisted."""
    derivation = derive(ledger)
    out: dict[tuple[str, str], float] = {}
    for match in sorted(derivation.matches, key=lambda m: m.at):  # stable: ledger order on ties
        apply_match(out, match)
    return out


def signals(
    ledger: run_ledger.RunLedger,
    registry: Registry,
    *,
    min_matches: int = DEFAULT_MIN_MATCHES,
) -> list[dict[str, Any]]:
    """R6 proposal candidates: cells whose Elo standing diverges from the authored ordering.

    A cell signals when, against a rival row for the same capability (both with at least
    ``min_matches`` matches), its Elo underperforms its authored standing — the authored rating
    ordering is inverted, or a shared rating band diverges by more than one K-step. The signal
    only ever proposes ``revalidate`` with a direction — never a concrete rating value.
    """
    elo = scores(ledger)
    counts = match_counts(derive(ledger))
    out: list[dict[str, Any]] = []
    entries = registry.engines
    for capability in registry.capabilities:
        rows = [e for e in entries if capability in e.capability_profile]
        for entry in rows:
            key = (entry.key, capability)
            if key not in elo or counts.get(key, 0) < min_matches:
                continue
            rating = _RATING_SCORE[str(entry.capability_profile[capability]["rating"])]
            for rival in rows:
                if rival.key == entry.key:
                    continue
                rival_key = (rival.key, capability)
                if rival_key not in elo or counts.get(rival_key, 0) < min_matches:
                    continue
                rival_rating = _RATING_SCORE[str(rival.capability_profile[capability]["rating"])]
                inverted = rating >= rival_rating and elo[key] < elo[rival_key]
                band_divergence = rating == rival_rating and elo[rival_key] - elo[key] > K
                if inverted and (rating > rival_rating or band_divergence):
                    out.append(
                        {
                            "engine_key": entry.key,
                            "capability": capability,
                            "action": "revalidate",
                            "direction": "down",
                            "elo": round(elo[key], 2),
                            "rival": rival.key,
                            "rival_elo": round(elo[rival_key], 2),
                            "matches": counts[key],
                        }
                    )
                    break
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Derive-on-read capability Elo from reconciliation outcomes (#459 R4)."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    report_parser = commands.add_parser("report", help="emit per-cell Elo scores and signals")
    report_parser.add_argument("--root", type=Path, default=Path("."), help="repository root")
    report_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    report_parser.add_argument("--min-matches", type=int, default=DEFAULT_MIN_MATCHES)
    report_parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    try:
        ledger = run_ledger.RunLedger.resolve(args.root)
        registry = Registry.load(args.registry)
        derivation = derive(ledger)
        elo = scores(ledger)
        divergences = signals(ledger, registry, min_matches=args.min_matches)
    except Exception as exc:  # noqa: BLE001 - CLI boundary: named failure, non-zero exit
        print(f"CAPABILITY ELO ERROR: {exc}", file=sys.stderr)
        return 2
    payload = {
        "scores": {f"{key}::{capability}": round(v, 2) for (key, capability), v in elo.items()},
        "matches": len(derivation.matches),
        "unattributed_matches": derivation.unattributed,
        "signals": divergences,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif not elo:
        print("no reconciliation match evidence yet")
    else:
        for cell, value in sorted(payload["scores"].items()):
            print(f"{cell}: {value}")
        for signal in divergences:
            print(
                f"signal: {signal['engine_key']} {signal['capability']} revalidate "
                f"(elo {signal['elo']} < rival {signal['rival']} {signal['rival_elo']})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
