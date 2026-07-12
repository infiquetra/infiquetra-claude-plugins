#!/usr/bin/env python3
"""`/retro` tier-efficacy pass — evidence-tuned tier-default proposals, never auto-applied (#402 U4).

Mines a repo's completed-run cost-vs-outcome history (spend from `spend_retro.py`'s aggregation,
joined against each check's verdict history from `evidence_ledger.py`'s `latest()` reader --
`superseded_fail`/attempt-count is the "marginal findings"/"rework" signal) and, for a work-shape
running consistently above baseline tier with ZERO marginal findings across enough runs, proposes
a one-rung-cheaper `.saga/tier-defaults.json` diff.

This module NEVER calls `tier_defaults.write_tier_default()` -- it renders a candidate diff for
`/retro`'s new Phase-5(e) propose-diff-and-wait step (mirroring existing (b)/(c): refine-lifecycle
/ refine-directives) to show the operator, exactly like every other self-edit `/retro` proposes.
The tiered self-edit safety contract's ONE auto-apply carve-out is a pure new journal entry; a
tier-default change is not that, so it is always propose-diff-and-wait here.

Plan: `docs/plans/2026-07-12-spend-observability-plan.md` (KTD5). Issue: #402.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import execution_spec  # noqa: E402
import tier_defaults  # noqa: E402

Tier = execution_spec.Tier

DEFAULT_MIN_SAMPLES = 3


class TierEfficacyError(ValueError):
    """Raised for a malformed tier-efficacy input."""


@dataclass(frozen=True)
class RunRecord:
    """One completed run's cost-vs-outcome for a work-shape (the pure-function test boundary).

    In a real (non-test) invocation, `/retro`'s Phase 1.10 assembles these by joining
    `spend_retro.py`'s per-outcome spend aggregation with each check's verdict history from
    `evidence_ledger.py`'s `latest()` reader: a run whose only attempt passed clean contributes
    `marginal_findings=0`; a `superseded_fail` or a multi-attempt history contributes nonzero.
    """

    work_shape: str
    tier: Tier
    spend: int
    marginal_findings: int


@dataclass(frozen=True)
class DowngradeProposal:
    work_shape: str
    current_tier: Tier
    proposed_tier: Tier
    n_runs: int
    total_spend: int
    rationale: str


def propose_downgrades(
    history: list[RunRecord], min_samples: int = DEFAULT_MIN_SAMPLES
) -> list[DowngradeProposal]:
    """Mine `history` for an overspent/zero-marginal-finding pattern per work-shape (R6).

    A work-shape proposes a downgrade only when ALL of: at least `min_samples` runs exist, EVERY
    run recorded zero marginal findings (any nonzero anywhere is mixed evidence -- no proposal),
    and every run shares the SAME tier (a work-shape whose runs used different tiers over time is
    an ambiguous signal, not a clean one). A work-shape already at the cheapest tier
    (`adjacent_tier` raises) proposes nothing -- there is no cheaper rung to suggest.
    """
    by_shape: dict[str, list[RunRecord]] = {}
    for rec in history:
        by_shape.setdefault(rec.work_shape, []).append(rec)

    proposals: list[DowngradeProposal] = []
    for work_shape, records in by_shape.items():
        if len(records) < min_samples:
            continue
        if any(r.marginal_findings > 0 for r in records):
            continue
        tiers = {(r.tier.model, r.tier.effort) for r in records}
        if len(tiers) != 1:
            continue
        current_tier = records[0].tier
        try:
            proposed_tier = execution_spec.adjacent_tier(current_tier, "cheaper")
        except execution_spec.SpecError:
            continue
        total_spend = sum(r.spend for r in records)
        proposals.append(
            DowngradeProposal(
                work_shape=work_shape,
                current_tier=current_tier,
                proposed_tier=proposed_tier,
                n_runs=len(records),
                total_spend=total_spend,
                rationale=(
                    f"{len(records)} runs at {current_tier.model}/{current_tier.effort} with zero "
                    f"marginal findings; one rung down is {proposed_tier.model}/{proposed_tier.effort}."
                ),
            )
        )
    return proposals


def render_diff_preview(proposals: list[DowngradeProposal], root: Path | None = None) -> str:
    """Render a human-readable diff preview against `.saga/tier-defaults.json` -- READ ONLY.

    Never calls `tier_defaults.write_tier_default()`. Reads the current overlay (if any) only to
    show what changes; the operator applies it themselves (via `/plan`'s own write-back flow or
    a manual edit) after reviewing.
    """
    if not proposals:
        return "no downgrade proposals -- either insufficient samples or mixed cost-vs-outcome evidence."
    current = tier_defaults.load_tier_defaults(root)
    lines = ["Proposed .saga/tier-defaults.json diff (PREVIEW ONLY -- never auto-applied):", ""]
    for p in proposals:
        existing = current.get(p.work_shape)
        existing_str = (
            f"{existing['model']}/{existing['effort']}"
            if existing
            else "(unset -- registry default)"
        )
        lines.append(f"  {p.work_shape}:")
        lines.append(f"    - {existing_str}")
        lines.append(f"    + {p.proposed_tier.model}/{p.proposed_tier.effort}")
        lines.append(f"    ({p.rationale})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _record_from_dict(data: dict) -> RunRecord:
    return RunRecord(
        work_shape=str(data["work_shape"]),
        tier=Tier(model=str(data["tier"]["model"]), effort=str(data["tier"]["effort"])),
        spend=int(data["spend"]),
        marginal_findings=int(data["marginal_findings"]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="/retro tier-efficacy pass: propose (never apply) tier-default downgrades (#402 U4)."
    )
    parser.add_argument(
        "--history", type=Path, required=True, help="a JSON list of RunRecord dicts"
    )
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    parser.add_argument(
        "--root", type=Path, default=None, help="repo root (for tier-defaults.json)"
    )
    args = parser.parse_args(argv)
    try:
        raw = json.loads(args.history.read_text(encoding="utf-8"))
        history = [_record_from_dict(r) for r in raw]
        proposals = propose_downgrades(history, min_samples=args.min_samples)
        print(render_diff_preview(proposals, root=args.root))
        return 0
    except (
        execution_spec.SpecError,
        tier_defaults.TierDefaultsError,
        TierEfficacyError,
        KeyError,
    ) as exc:
        print(f"TIER EFFICACY ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
