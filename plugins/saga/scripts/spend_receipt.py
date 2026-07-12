#!/usr/bin/env python3
"""Itemized per-unit/per-tier spend receipt + cheap-fallback counterfactual (#402 U2).

Renders a receipt for a single-session ``execution_spec.ExecutionSpec`` (or an
``outcome_spec.OutcomeSpec`` via ``spend_estimate.resolve_node_tier``): the ordinal spend at the
tier a unit actually ran at, and a `counterfactual_total` -- the sum of each unit's declared
fallback-tier cost -- so an operator sees not just "what did this cost" but "what would the
all-cheap-fallback plan have cost, and what did we give up by not taking it."

Fallback-tier resolution priority per unit (KTD2 -- ``execution_spec.Unit`` already carries the
issue's anticipated fallback-tier/justification fields, no stub needed there):

1. the unit's own declared ``cheaper_fallback`` (an author-confirmed, evidence-backed choice);
2. else ``execution_spec.adjacent_tier(tier, "cheaper")`` (the generic one-rung-down default);
3. else, for an outcome-DAG node with no unit-level field at all,
   ``spend_estimate.resolve_node_tier``'s own fallback (KTD1).

A unit already at the cheapest tier (``adjacent_tier`` raises) reports "already cheapest -- no
counterfactual" rather than propagating the exception -- the boundary is expected, not an error.

Pure reader: this module never calls a ledger-write function and never writes the reviewed spec
back to disk (R9). Plan: ``docs/plans/2026-07-12-spend-observability-plan.md``. Issue: #402.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import execution_spec  # noqa: E402
import spend_estimate  # noqa: E402

Tier = execution_spec.Tier

_ALREADY_CHEAPEST = "already cheapest -- no counterfactual"


class SpendReceiptError(ValueError):
    """Raised for a malformed receipt input."""


@dataclass(frozen=True)
class UnitReceipt:
    unit_id: str
    tier: Tier
    spend: int
    fallback_tier: Tier | None
    fallback_spend: int | None
    fallback_source: str
    """One of 'declared', 'adjacent', or 'already-cheapest' (never a silent 4th state)."""
    tradeoff: str
    above_fallback: bool


def _resolve_unit_fallback(unit: execution_spec.Unit) -> tuple[Tier | None, str]:
    """Resolve a unit's fallback tier per the priority order (KTD2)."""
    if unit.cheaper_fallback is not None:
        return unit.cheaper_fallback, "declared"
    try:
        return execution_spec.adjacent_tier(unit.tier, "cheaper"), "adjacent"
    except execution_spec.SpecError:
        return None, "already-cheapest"


def _cost_weights() -> Any:
    return spend_estimate._cost_weights()


def receipt_for_units(spec: execution_spec.ExecutionSpec) -> list[UnitReceipt]:
    """The itemized receipt for a single-session ``ExecutionSpec`` (R4)."""
    cost_weights = _cost_weights()
    out: list[UnitReceipt] = []
    for unit in spec.units:
        spend = execution_spec.unit_spend(unit)
        fallback, source = _resolve_unit_fallback(unit)
        if fallback is None:
            out.append(
                UnitReceipt(
                    unit_id=unit.unit_id,
                    tier=unit.tier,
                    spend=spend,
                    fallback_tier=None,
                    fallback_spend=None,
                    fallback_source=source,
                    tradeoff=_ALREADY_CHEAPEST,
                    above_fallback=False,
                )
            )
            continue
        fallback_spend = cost_weights.to_spend(fallback.model, fallback.effort)
        above = fallback_spend < spend
        tradeoff = ""
        if above:
            tradeoff = unit.worth_it_because or "no justification recorded"
        out.append(
            UnitReceipt(
                unit_id=unit.unit_id,
                tier=unit.tier,
                spend=spend,
                fallback_tier=fallback,
                fallback_spend=fallback_spend,
                fallback_source=source,
                tradeoff=tradeoff,
                above_fallback=above,
            )
        )
    return out


def counterfactual_total(receipts: list[UnitReceipt]) -> int:
    """Sum of each unit's declared fallback-tier cost (R4's exact AC).

    A unit already at the cheapest tier contributes its OWN (unchanged) spend to the
    counterfactual -- there is no cheaper alternative to substitute, so the honest counterfactual
    for that unit is what it already costs, not a fabricated lower number.
    """
    total = 0
    for r in receipts:
        total += r.fallback_spend if r.fallback_spend is not None else r.spend
    return total


def render_receipt(spec: execution_spec.ExecutionSpec) -> str:
    receipts = receipt_for_units(spec)
    actual_total = sum(r.spend for r in receipts)
    cf_total = counterfactual_total(receipts)
    lines = [
        "| Unit | Tier | Spend | Fallback | Fallback spend | Tradeoff |",
        "|---|---|---:|---|---:|---|",
    ]
    for r in receipts:
        fallback_str = (
            f"{r.fallback_tier.model}/{r.fallback_tier.effort}" if r.fallback_tier else "-"
        )
        fb_spend_str = str(r.fallback_spend) if r.fallback_spend is not None else "-"
        lines.append(
            f"| {r.unit_id} | {r.tier.model}/{r.tier.effort} | {r.spend} | {fallback_str} | "
            f"{fb_spend_str} | {r.tradeoff or '-'} |"
        )
    lines.append(f"| **total** | | **{actual_total}** | | **{cf_total}** | |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_execution_spec(path: Path) -> execution_spec.ExecutionSpec:
    return execution_spec.ExecutionSpec.from_dict(json.loads(path.read_text(encoding="utf-8")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Itemized spend receipt + cheap-fallback counterfactual (#402 U2)."
    )
    parser.add_argument("--spec", type=Path, required=True, help="an execution-spec.json")
    args = parser.parse_args(argv)
    try:
        spec = _load_execution_spec(args.spec)
        print(render_receipt(spec))
        return 0
    except (execution_spec.SpecError, SpendReceiptError) as exc:
        print(f"SPEND RECEIPT ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
