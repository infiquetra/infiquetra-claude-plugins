#!/usr/bin/env python3
"""Override-rate reader: R12 analysis half (U13).

Scans all saga envelopes and surfaces:

* **override_rate** — fraction of decisions where the operator's explicit pick
  (``orchestration_operator_choice``) differs from the recommender's suggestion
  (``orchestration_recommended``).  Only sagas where *both* fields are non-empty
  are counted — ``""`` means "no recommendation recorded" and is excluded.
* **over_tier** — cases where the operator escalated to a richer backend than
  the recommendation (``inline`` → ``team-execution`` or
  ``cc-workflows-ultracode``; ``team-execution`` → ``cc-workflows-ultracode``).
* **under_tier** — cases where the operator de-escalated to a cheaper backend
  (``cc-workflows-ultracode`` → ``team-execution`` or ``inline``;
  ``team-execution`` → ``inline``).
* **budget_exhaustion** — sagas that recorded a non-empty
  ``orchestration_downgrade`` note; each note is a capability-portable
  off-host degradation event (U12 / R11).

Zero-data contract (no sagas / no recorded decisions):
  All rates are ``None`` (not 0.0) so callers can distinguish "no data yet"
  from "data shows 0 %".  A ``None`` rate MUST print "no data yet" rather than
  divide-by-zero.

CLI::

    python3 override_rate_reader.py [--root <path>]
    python3 override_rate_reader.py [--root <path>] --json

Pure functions + injectable ``root`` follow the ``saga.py`` house pattern so
offline tests never touch the real filesystem.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Tier ordering (for over/under-tier classification)
# ---------------------------------------------------------------------------

# The three orchestration backends, ranked cheapest → richest.
# A pick richer than the recommendation = over-tier; cheaper = under-tier.
_TIER_ORDER: dict[str, int] = {
    "inline": 0,
    "team-execution": 1,
    "cc-workflows-ultracode": 2,
}


def _tier_rank(mode: str) -> int | None:
    """Return the numeric tier rank for *mode*, or None for unknown / empty."""
    return _TIER_ORDER.get(mode)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionRecord:
    """One orchestration decision pulled from a saga envelope."""

    saga_id: str
    recommended: str  # orchestration_recommended (may be "")
    operator_choice: str  # orchestration_operator_choice (may be "")
    actual_mode: str  # orchestration_mode (the running mode, may differ)
    downgrade: str  # orchestration_downgrade (non-empty → degradation event)


@dataclass(frozen=True)
class OverrideRateSummary:
    """The full R12 surface.

    ``override_rate`` / ``over_tier_rate`` / ``under_tier_rate`` are ``None``
    when there are no recorded decisions (zero-data guard).
    """

    total_sagas: int
    decisions_with_data: int  # sagas where both recommended + choice are non-empty
    override_count: int  # decisions where choice != recommended
    over_tier_count: int  # decision escalated to richer backend
    under_tier_count: int  # decision de-escalated to cheaper backend
    budget_exhaustion_count: int  # sagas with non-empty orchestration_downgrade

    @property
    def override_rate(self) -> float | None:
        """Fraction of decisions where operator overrode the recommendation."""
        if self.decisions_with_data == 0:
            return None
        return self.override_count / self.decisions_with_data

    @property
    def over_tier_rate(self) -> float | None:
        """Fraction of decisions that escalated to a richer backend."""
        if self.decisions_with_data == 0:
            return None
        return self.over_tier_count / self.decisions_with_data

    @property
    def under_tier_rate(self) -> float | None:
        """Fraction of decisions that de-escalated to a cheaper backend."""
        if self.decisions_with_data == 0:
            return None
        return self.under_tier_count / self.decisions_with_data

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_sagas": self.total_sagas,
            "decisions_with_data": self.decisions_with_data,
            "override_count": self.override_count,
            "over_tier_count": self.over_tier_count,
            "under_tier_count": self.under_tier_count,
            "budget_exhaustion_count": self.budget_exhaustion_count,
            "override_rate": self.override_rate,
            "over_tier_rate": self.over_tier_rate,
            "under_tier_rate": self.under_tier_rate,
        }


# ---------------------------------------------------------------------------
# Saga envelope reader (avoids importing saga.py to stay lightweight)
# ---------------------------------------------------------------------------

_STATE_DIR = Path(".claude/saga")
_SAGAS_DIR = _STATE_DIR / "sagas"
_ENVELOPE_FIELDS = {
    "orchestration_recommended",
    "orchestration_operator_choice",
    "orchestration_mode",
    "orchestration_downgrade",
    "saga_id",
}


def _parse_frontmatter_fields(text: str, fields: set[str]) -> dict[str, str]:
    """Extract a subset of YAML-like frontmatter fields from an envelope file.

    Only parses the leading ``---`` block; stops at the second ``---`` delimiter
    or EOF.  Each line is ``key: value``; multi-word values are captured verbatim.
    Returns ``""`` for fields not present in the frontmatter (backward-compat).
    """
    result: dict[str, str] = dict.fromkeys(fields, "")
    in_front = False
    for line in text.splitlines():
        if line.strip() == "---":
            if not in_front:
                in_front = True
                continue
            else:
                break  # closing delimiter
        if not in_front:
            continue
        if ":" in line:
            key, _, raw_val = line.partition(":")
            key = key.strip()
            if key in fields:
                result[key] = raw_val.strip()
    return result


def _all_latest_envelopes(root: Path) -> list[Path]:
    """Return the newest envelope file for every saga directory under *root*.

    Uses filename ordering (same lexicographic contract as ``saga.py``) — mtime
    is never consulted.
    """
    sagas_dir = root / _SAGAS_DIR
    if not sagas_dir.is_dir():
        return []
    envelopes: list[Path] = []
    for saga_dir in sagas_dir.iterdir():
        if not saga_dir.is_dir():
            continue
        candidates = [p for p in saga_dir.iterdir() if p.is_file() and p.suffix == ".md"]
        if not candidates:
            continue
        # Filename-ordered: sort lexicographically (timestamp prefix ensures order).
        envelopes.append(max(candidates, key=lambda p: p.name))
    return envelopes


# ---------------------------------------------------------------------------
# Core analysis function
# ---------------------------------------------------------------------------


def read_override_rate(root: Path) -> tuple[OverrideRateSummary, list[DecisionRecord]]:
    """Scan all saga envelopes under *root* and return R12 signals.

    Returns ``(summary, records)`` where *records* is the raw per-saga list.
    Both are derived purely from envelope files — no subprocess, no network.
    """
    envelopes = _all_latest_envelopes(root)
    records: list[DecisionRecord] = []

    for env_path in envelopes:
        try:
            text = env_path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_frontmatter_fields(text, _ENVELOPE_FIELDS)
        records.append(
            DecisionRecord(
                saga_id=fm.get("saga_id", env_path.parent.name),
                recommended=fm.get("orchestration_recommended", ""),
                operator_choice=fm.get("orchestration_operator_choice", ""),
                actual_mode=fm.get("orchestration_mode", ""),
                downgrade=fm.get("orchestration_downgrade", ""),
            )
        )

    total_sagas = len(records)
    decisions_with_data = 0
    override_count = 0
    over_tier_count = 0
    under_tier_count = 0
    budget_exhaustion_count = 0

    for rec in records:
        # Budget-exhaustion: any recorded downgrade note.
        if rec.downgrade:
            budget_exhaustion_count += 1

        # Override-rate: only when both fields are present.
        if not rec.recommended or not rec.operator_choice:
            continue
        decisions_with_data += 1

        if rec.operator_choice != rec.recommended:
            override_count += 1
            rec_rank = _tier_rank(rec.recommended)
            choice_rank = _tier_rank(rec.operator_choice)
            if rec_rank is not None and choice_rank is not None:
                if choice_rank > rec_rank:
                    over_tier_count += 1
                elif choice_rank < rec_rank:
                    under_tier_count += 1

    summary = OverrideRateSummary(
        total_sagas=total_sagas,
        decisions_with_data=decisions_with_data,
        override_count=override_count,
        over_tier_count=over_tier_count,
        under_tier_count=under_tier_count,
        budget_exhaustion_count=budget_exhaustion_count,
    )
    return summary, records


# ---------------------------------------------------------------------------
# Human-readable report
# ---------------------------------------------------------------------------


def _pct(rate: float | None) -> str:
    """Format a rate as a percentage string, or 'no data yet'."""
    if rate is None:
        return "no data yet"
    return f"{rate * 100:.1f}%"


def format_report(summary: OverrideRateSummary, records: list[DecisionRecord]) -> str:
    """Return a human-readable R12 signal report."""
    lines: list[str] = [
        "## R12 Orchestration Signals",
        "",
        f"Sagas scanned: {summary.total_sagas}",
        f"Decisions with recommendation data: {summary.decisions_with_data}",
        "",
        "### Override Rate",
        f"  Operator overrode the recommendation: {_pct(summary.override_rate)}"
        + (
            f" ({summary.override_count}/{summary.decisions_with_data})"
            if summary.decisions_with_data > 0
            else ""
        ),
        "",
        "### Tier Direction (of overrides)",
        f"  Over-tier (escalated to richer backend):  {_pct(summary.over_tier_rate)}"
        + (
            f" ({summary.over_tier_count}/{summary.decisions_with_data})"
            if summary.decisions_with_data > 0
            else ""
        ),
        f"  Under-tier (de-escalated to cheaper backend): {_pct(summary.under_tier_rate)}"
        + (
            f" ({summary.under_tier_count}/{summary.decisions_with_data})"
            if summary.decisions_with_data > 0
            else ""
        ),
        "",
        "### Budget-Exhaustion / Capability Degradation",
        f"  Sagas with a recorded orchestration downgrade: {summary.budget_exhaustion_count}",
    ]

    if summary.decisions_with_data == 0:
        lines += [
            "",
            "No recommendation data recorded yet.  Override-rate and tier-direction",
            "signals accrue as /plan records recommended vs operator-chosen backends.",
            "Run again after a few orchestration decisions to see signal.",
        ]

    if any(r.downgrade for r in records):
        lines.append("")
        lines.append("### Downgrade Notes")
        for rec in records:
            if rec.downgrade:
                lines.append(f"  {rec.saga_id}: {rec.downgrade}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Surface R12 override-rate + budget-exhaustion signals from saga data."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repo root (default: cwd).  Must contain .claude/saga/.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit a machine-readable JSON summary instead of the human report.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    summary, records = read_override_rate(root)

    if args.as_json:
        print(json.dumps(summary.as_dict(), indent=2))
    else:
        print(format_report(summary, records))


if __name__ == "__main__":
    main(sys.argv[1:])
