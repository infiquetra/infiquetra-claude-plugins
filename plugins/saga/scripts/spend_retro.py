#!/usr/bin/env python3
"""Cross-run spend aggregator — tier-mix / premium-spend-share / spend-vs-outcome (#402 U3).

Reads every committed ``docs/outcomes/*/outcome-spec.json`` (never a new store, KTD4): the
leaf-produced, derived-on-read fact the binding ``/outcome`` campaign decision names. This is
the mechanism that makes "xhigh-Opus on everything is wasteful" a checkable claim instead of a
belief (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 7, recurring pattern 6).

Two figures never conflate (mirroring ``spend_estimate.py``'s KTD3 discipline at the
cross-run level): the **tier-mix** / **premium-spend-share** are computed from the ESTIMATED,
ordinal per-node tier (``spend_estimate.resolve_node_tier`` -- the committed spec carries no
per-node REAL cost breakdown, only the outcome-wide ``cost_rollup`` aggregate); the **realized**
tokens / wall_seconds / operator_touches / retries render separately, as real telemetry, never
coerced onto the ordinal axis.

Both real committed examples in this repo roll up empty today (``cost_rollup: {}``) -- this
module renders "no data yet" honestly for that case (the same U8 honesty rule
``outcome_costs.py`` already established), never a fabricated zero.

Pure reader + one journal APPEND: never rewrites an ``outcome-spec.json`` in place, never calls a
ledger-write function. Plan: ``docs/plans/2026-07-12-spend-observability-plan.md``. Issue: #402.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import execution_spec  # noqa: E402
import outcome_spec  # noqa: E402
import spend_estimate  # noqa: E402

SPEND_BASELINE = execution_spec.SPEND_BASELINE
is_escalation = execution_spec.is_escalation

DEFAULT_OUTCOMES_GLOB = "docs/outcomes/*/outcome-spec.json"
JOURNAL_PATH = Path("docs/engineering-journal/LEARNINGS.md")


class SpendRetroError(ValueError):
    """Raised for a malformed spend-retro input."""


@dataclass(frozen=True)
class OutcomeSpendRow:
    outcome_id: str
    node_count: int
    tier_mix: dict[str, int]
    """{'model/effort': node_count}."""
    premium_node_count: int
    total_estimate: int
    premium_estimate: int
    terminal_state_counts: dict[str, int]
    cost_rollup: dict[str, Any]
    has_real_telemetry: bool
    tier_provenance: dict[str, int] = field(default_factory=dict)
    """{'issue-tier-band' | 'default': node_count} — how each node's tier was resolved."""


@dataclass
class SpendSummary:
    rows: list[OutcomeSpendRow] = field(default_factory=list)

    @property
    def has_any_data(self) -> bool:
        return bool(self.rows)

    @property
    def any_real_telemetry(self) -> bool:
        return any(r.has_real_telemetry for r in self.rows)

    def aggregate_tier_mix(self) -> dict[str, int]:
        mix: dict[str, int] = {}
        for row in self.rows:
            for tier_str, count in row.tier_mix.items():
                mix[tier_str] = mix.get(tier_str, 0) + count
        return mix

    def aggregate_premium_share(self) -> float:
        """Fraction of ESTIMATED ordinal spend that came from premium-tier nodes, repo-wide."""
        total = sum(r.total_estimate for r in self.rows)
        if total <= 0:
            return 0.0
        premium = sum(r.premium_estimate for r in self.rows)
        return premium / total

    @property
    def all_tiers_defaulted(self) -> bool:
        """True when no node's tier came from an issue tier band — every estimate fell back to
        the SPEND_BASELINE default (no issue bodies supplied), so the premium share is a floor,
        not a derived fact."""
        return self.has_any_data and not any(
            row.tier_provenance.get("issue-tier-band") for row in self.rows
        )


def discover_outcomes(root: Path, glob: str = DEFAULT_OUTCOMES_GLOB) -> list[tuple[str, Path]]:
    """Every committed outcome-spec.json under ``root`` (never a new store, KTD4).

    Returns ``(outcome_dir_name, spec_path)`` pairs, sorted for deterministic iteration. An
    outcome directory with no ``outcome-spec.json`` (e.g. a bare example/template dir) is
    naturally excluded -- the glob only ever matches a real spec file.
    """
    return sorted(
        ((p.parent.name, p) for p in root.glob(glob)),
        key=lambda pair: pair[0],
    )


def _outcome_row(
    outcome_id: str, spec: outcome_spec.OutcomeSpec, issue_bodies: dict[str, str] | None = None
) -> OutcomeSpendRow:
    estimates = spend_estimate.estimate_nodes(spec, issue_bodies)
    tier_mix: dict[str, int] = {}
    tier_provenance: dict[str, int] = {}
    premium_node_count = 0
    premium_estimate = 0
    total_estimate = 0
    for est in estimates:
        key = f"{est.tier.model}/{est.tier.effort}"
        tier_mix[key] = tier_mix.get(key, 0) + 1
        tier_provenance[est.provenance] = tier_provenance.get(est.provenance, 0) + 1
        total_estimate += est.spend
        if is_escalation(SPEND_BASELINE, est.tier):
            premium_node_count += 1
            premium_estimate += est.spend

    terminal_counts: dict[str, int] = {}
    for node in spec.nodes:
        if node.state in outcome_spec.TERMINAL_STATES:
            terminal_counts[node.state] = terminal_counts.get(node.state, 0) + 1

    return OutcomeSpendRow(
        outcome_id=outcome_id,
        node_count=len(spec.nodes),
        tier_mix=tier_mix,
        premium_node_count=premium_node_count,
        total_estimate=total_estimate,
        premium_estimate=premium_estimate,
        terminal_state_counts=terminal_counts,
        cost_rollup=dict(spec.cost_rollup),
        has_real_telemetry=bool(spec.cost_rollup),
        tier_provenance=tier_provenance,
    )


def build_spend_summary(
    outcomes: list[tuple[str, outcome_spec.OutcomeSpec]],
    issue_bodies: dict[str, str] | None = None,
) -> SpendSummary:
    """Aggregate every discovered outcome's tier-mix/premium-spend-share/spend-vs-outcome (R5).

    ``outcomes`` is a list of ``(outcome_id, OutcomeSpec)`` -- already-parsed, so this function
    performs no file I/O itself (the CLI/caller reads the committed JSON via
    ``discover_outcomes`` + ``outcome_spec.OutcomeSpec.from_dict``, never this function).
    """
    return SpendSummary(rows=[_outcome_row(oid, spec, issue_bodies) for oid, spec in outcomes])


def render_summary_table(summary: SpendSummary) -> str:
    if not summary.has_any_data:
        return "no data yet — no committed outcome-spec.json found in the repo."
    lines = [
        "| Outcome | Nodes | Premium nodes | Est. total | Est. premium share | Real telemetry |"
    ]
    lines.append("|---|---:|---:|---:|---:|---|")
    for row in summary.rows:
        share = (row.premium_estimate / row.total_estimate) if row.total_estimate else 0.0
        real = "yes" if row.has_real_telemetry else "no data yet"
        lines.append(
            f"| {row.outcome_id} | {row.node_count} | {row.premium_node_count} | "
            f"{row.total_estimate} | {share:.0%} | {real} |"
        )
    repo_share = summary.aggregate_premium_share()
    real_note = (
        "" if summary.any_real_telemetry else " (no outcome has recorded real telemetry yet)"
    )
    lines.append(f"\nRepo-wide estimated premium-spend share: {repo_share:.0%}{real_note}.")
    if summary.all_tiers_defaulted:
        lines.append(
            "Note: every node's tier fell back to the SPEND_BASELINE default (no issue tier "
            "bands supplied — pass --issue-bodies with fetched issue bodies to derive real "
            "tiers); the premium share above is a floor, not a derived fact."
        )
    return "\n".join(lines)


#: A `## YYYY-MM-DD` section heading — the only heading shape the journal convention allows.
_DATE_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)


def render_journal_section(summary: SpendSummary, on: _date | None = None) -> str:
    """A dated `### Spend Retro` ENTRY for LEARNINGS.md, without its `## <date>` heading.

    Emits an entry (``###``), not a section (``##``): the journal's sections are dates and its
    entries live under them. The previous shape, ``## <date> Spend Retro``, was neither — a
    date-prefixed heading that no `## YYYY-MM-DD` reader would recognize as a section (#659).
    """
    when = (on or _date.today()).isoformat()
    body = render_summary_table(summary)
    return (
        f"### Spend Retro {{#spend-retro-{when}}}\n\n"
        f"Auto-generated by `plugins/saga/scripts/spend_retro.py` (#402) — a cross-run "
        f"aggregation of every committed `docs/outcomes/*/outcome-spec.json`'s estimated "
        f"tier-mix and premium-spend share, so the 'xhigh-Opus is wasteful' claim is checkable "
        f"against real numbers instead of asserted.\n\n"
        f"{body}\n"
    )


def write_to_journal(
    summary: SpendSummary, journal_path: Path = JOURNAL_PATH, on: _date | None = None
) -> None:
    """Insert the retro entry at the TOP of the journal, never at the end.

    The journal is newest-first (`LEARNINGS.md` says so in its own header), so an ``open("a")``
    append filed this entry at the bottom, under whatever stale date heading happened to sit
    there — the exact drift #659 was raised for. Existing content is never edited: the entry is
    spliced in above the current newest section, reusing that section's heading when the dates
    match and opening a new one when they do not.
    """
    when = (on or _date.today()).isoformat()
    entry = render_journal_section(summary, on=on)
    text = journal_path.read_text(encoding="utf-8") if journal_path.exists() else ""

    match = _DATE_HEADING.search(text)
    if match is None:
        # No sections yet: open one after whatever preamble exists.
        head = text.rstrip("\n")
        joiner = "\n\n" if head else ""
        journal_path.write_text(f"{head}{joiner}## {when}\n\n{entry}", encoding="utf-8")
        return

    if match.group(1) == when:
        # Same day: land inside the existing section, above its first entry.
        at = match.end() + 1
        journal_path.write_text(
            f"{text[:at]}\n{entry}\n{text[at:].lstrip(chr(10))}", encoding="utf-8"
        )
        return

    at = match.start()
    journal_path.write_text(f"{text[:at]}## {when}\n\n{entry}\n{text[at:]}", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cross-run spend aggregator: tier-mix / premium-spend-share (#402 U3)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_report = sub.add_parser("report", help="print the aggregate spend-summary table")
    p_report.add_argument("--root", type=Path, default=Path("."), help="repo root")
    p_report.add_argument("--json", action="store_true", help="emit JSON instead of a table")

    p_append = sub.add_parser(
        "append", help="append a new dated spend-summary section to the journal"
    )
    p_append.add_argument("--root", type=Path, default=Path("."), help="repo root")
    p_append.add_argument("--journal", type=Path, default=None, help="override the journal path")

    for p_sub in (p_report, p_append):
        p_sub.add_argument(
            "--issue-bodies",
            type=Path,
            default=None,
            help="JSON object of {issue-ref: already-fetched issue body text} for "
            "issue-tier-band resolution; without it every node's tier falls back to the "
            "SPEND_BASELINE default and the premium share is a labeled floor",
        )

    args = parser.parse_args(argv)
    try:
        issue_bodies: dict[str, str] | None = None
        if args.issue_bodies is not None:
            raw_bodies = json.loads(args.issue_bodies.read_text(encoding="utf-8"))
            if not isinstance(raw_bodies, dict):
                raise SpendRetroError(
                    f"expected --issue-bodies to be a JSON object, got {type(raw_bodies).__name__}"
                )
            issue_bodies = {str(k): str(v) for k, v in raw_bodies.items()}
        specs = [
            (oid, outcome_spec.OutcomeSpec.from_dict(json.loads(p.read_text(encoding="utf-8"))))
            for oid, p in discover_outcomes(args.root)
        ]
        summary = build_spend_summary(specs, issue_bodies)
        if args.cmd == "report":
            if args.json:
                print(
                    json.dumps(
                        {
                            "rows": [
                                {
                                    "outcome_id": r.outcome_id,
                                    "node_count": r.node_count,
                                    "tier_mix": r.tier_mix,
                                    "premium_node_count": r.premium_node_count,
                                    "total_estimate": r.total_estimate,
                                    "premium_estimate": r.premium_estimate,
                                    "terminal_state_counts": r.terminal_state_counts,
                                    "has_real_telemetry": r.has_real_telemetry,
                                    "tier_provenance": r.tier_provenance,
                                }
                                for r in summary.rows
                            ],
                            "repo_wide_premium_share": summary.aggregate_premium_share(),
                            "tiers_defaulted": summary.all_tiers_defaulted,
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                print(render_summary_table(summary))
            return 0
        if args.cmd == "append":
            journal_path = args.journal or (args.root / JOURNAL_PATH)
            write_to_journal(summary, journal_path)
            print(f"appended spend-retro section to {journal_path}")
            return 0
    except (outcome_spec.OutcomeSpecError, SpendRetroError, json.JSONDecodeError) as exc:
        print(f"SPEND RETRO ERROR: {exc}", file=sys.stderr)
        return 2

    parser.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
