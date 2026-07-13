#!/usr/bin/env python3
"""Pre-run ordinal spend estimate, tier-value scoring, and post-run reconcile (#402 U1).

Three readers over already-shipped substrate — nothing here writes a ledger, a status field, or
a tier default:

* ``estimate_units`` / ``render_estimate_table`` — the ordinal `Estimate` column `/plan`'s Phase
  5.2a Step 1 tier table renders for a single-session ``execution_spec.ExecutionSpec``'s units
  (the issue's own DoD anchor, `plugins/saga/skills/plan/SKILL.md` Phase 5.2a). Reuses
  ``execution_spec.unit_spend()`` verbatim -- this module does not re-derive the cost-weight
  table.
* ``resolve_node_tier`` / ``estimate_nodes`` -- a separate, reusable node-tier resolver for the
  ``/outcome`` DAG (``outcome_spec.Node``) granularity that ``spend_receipt.py`` and
  ``spend_retro.py`` also consume. ``outcome_spec.Node`` carries no tier field, so the tier is
  resolved from durable state only: the node's linked GitHub issue's stamped ``### Recommended
  Tier Band`` (via ``tier_defaults.parse_tier_band``), else the shared ``SPEND_BASELINE``. The
  git-ignored saga cache (``orchestration_ref`` / ``.claude/saga/``) is deliberately never
  consulted here -- it is machine-local and "the anchor, not the authority"
  (``resume/SKILL.md``), and this resolver must work long after the fact, possibly from a
  different machine or a fresh clone.
* ``tier_value_score`` -- a payoff-at-stake x remaining-spend-envelope scoring helper (R3),
  deterministic and Claude-side (never an external engine), expressed on the same normalized
  ladder-dearness scale a tier itself occupies so a score is directly comparable to "the top
  rung" or "a pushed-down rung."
* ``reconcile`` -- the post-run estimate/actual/delta reader over ``outcome_costs.py``'s rollup.
  Never invents a token-to-ordinal exchange rate: only ``operator_touches``/``retries`` (both
  implicitly estimated at 0 in a clean-run baseline) get a numeric delta against the estimate;
  ``tokens``/``wall_seconds`` render as labeled, non-commensurable real-world context.

Plan: ``docs/plans/2026-07-12-spend-observability-plan.md`` (KTD1-3). Issue: #402.
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
import fleet_commons_shim  # noqa: E402  (after the sys.path shim, by design)
import outcome_costs  # noqa: E402
import outcome_spec  # noqa: E402
import tier_defaults  # noqa: E402

_tier_palette = fleet_commons_shim.load("tier_palette")

Tier = execution_spec.Tier
SPEND_BASELINE = execution_spec.SPEND_BASELINE

# Fields outcome_costs.py's rollup records that share the estimate's implicit clean-run baseline
# (both estimated at 0) -- the ONLY fields the post-run reconcile deltas numerically (KTD3). The
# remaining real-telemetry fields (tokens/wall_seconds) are rendered as labeled context, never
# coerced onto the ordinal axis.
_COMMENSURABLE_FIELDS = ("operator_touches", "retries")
_CONTEXT_ONLY_FIELDS = ("tokens", "wall_seconds")


class SpendEstimateError(ValueError):
    """Raised for a malformed spend-estimate input (never for 'no data yet')."""


# ---------------------------------------------------------------------------
# ExecutionSpec.Unit-level estimate (R1 -- the /plan Phase 5.2a surface)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnitEstimate:
    unit_id: str
    label: str
    tier: Tier
    spend: int


def estimate_units(spec: execution_spec.ExecutionSpec) -> list[UnitEstimate]:
    """Ordinal per-unit estimate for a single-session ``ExecutionSpec`` (R1)."""
    return [
        UnitEstimate(
            unit_id=u.unit_id, label=u.label, tier=u.tier, spend=execution_spec.unit_spend(u)
        )
        for u in spec.units
    ]


def render_estimate_table(spec: execution_spec.ExecutionSpec) -> str:
    """Render the Estimate column `/plan` Phase 5.2a Step 1 joins onto its own tier table.

    This is a markdown table fragment -- `/plan` composes it beside the Work-shape/Default-tier/
    Rationale columns it already renders; this function does not invent a second table.
    """
    estimates = estimate_units(spec)
    lines = ["| Unit | Tier | Estimate |", "|---|---|---:|"]
    total = 0
    for e in estimates:
        lines.append(f"| {e.unit_id} | {e.tier.model}/{e.tier.effort} | {e.spend} |")
        total += e.spend
    lines.append(f"| **total** | | **{total}** |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# outcome_spec.Node-level fallback-tier resolver (KTD1/KTD2 -- reused by U2/U3)
# ---------------------------------------------------------------------------


def resolve_node_tier(node: outcome_spec.Node, issue_body: str | None = None) -> tuple[Tier, str]:
    """Resolve one outcome-DAG node's tier for estimate/receipt/retro use (KTD1).

    Returns ``(tier, provenance)``. ``provenance`` is ``"issue-tier-band"`` when the node's
    linked issue carries a parseable ``### Recommended Tier Band``, else ``"default"`` (the
    explicit, clearly-labeled ``SPEND_BASELINE`` fallback -- never blended in as if it were a
    real, derived estimate).

    ``issue_body`` is the ALREADY-FETCHED GitHub issue body text (the caller fetches it via
    ``gh issue view <node.github['issue']>`` off the node's own committed ``github`` field before
    calling this). This function performs no I/O itself, so it stays a pure, offline-testable
    function -- the git-ignored saga cache (`orchestration_ref` / `.claude/saga/`) is
    deliberately never consulted (KTD1: durable committed/GitHub state only).
    """
    if issue_body:
        band = tier_defaults.parse_tier_band(issue_body)
        if band is not None:
            return Tier(model=str(band["model"]), effort=str(band["effort"])), "issue-tier-band"
    return SPEND_BASELINE, "default"


@dataclass(frozen=True)
class NodeEstimate:
    subplot_id: str
    tier: Tier
    provenance: str
    spend: int


def estimate_nodes(
    spec: outcome_spec.OutcomeSpec, issue_bodies: dict[str, str] | None = None
) -> list[NodeEstimate]:
    """Ordinal per-node estimate for an `/outcome` DAG (KTD1). ``/plan`` never renders this
    table itself (it is single-session-scoped) -- ``spend_receipt.py``/``spend_retro.py``
    consume it directly for cross-run aggregation.
    """
    bodies = issue_bodies or {}
    out: list[NodeEstimate] = []
    for node in spec.nodes:
        issue_ref = str(node.github.get("issue", "")) if node.github else ""
        tier, provenance = resolve_node_tier(node, bodies.get(issue_ref))
        out.append(
            NodeEstimate(
                subplot_id=node.subplot_id,
                tier=tier,
                provenance=provenance,
                spend=_cost_weights().to_spend(tier.model, tier.effort),
            )
        )
    return out


def _cost_weights() -> Any:
    return fleet_commons_shim.load("cost_weights")


# ---------------------------------------------------------------------------
# R3 -- tier-value scoring (payoff-at-stake x remaining spend envelope)
# ---------------------------------------------------------------------------


def ladder_dearness(tier: Tier) -> float:
    """This tier's combined model+effort ladder position, normalized to ``[0, 1]``.

    ``0.0`` is the cheapest runnable tier on the palette, ``1.0`` is the dearest. Built on the
    public ``model_rank``/``effort_rank`` ops (never a raw private index), so a score computed
    here is directly comparable against any other tier's own dearness -- including "the top
    ladder rung" (dearness ``1.0``) and "a pushed-down rung" (some tier's own dearness < the
    unit's current tier).
    """
    n_models = len(_tier_palette.MODELS)
    n_efforts = len(_tier_palette.EFFORTS)
    # MODELS is strongest-first (rank 0 = strongest), so invert to a "model strength" where
    # larger = dearer; EFFORTS is weakest-first (rank 0 = weakest), already dearer-is-larger.
    model_strength = (n_models - 1) - _tier_palette.model_rank(tier.model)
    effort_strength = _tier_palette.effort_rank(tier.effort)
    max_total = (n_models - 1) + (n_efforts - 1)
    if max_total <= 0:
        return 0.0
    return (model_strength + effort_strength) / max_total


def tier_value_score(
    tier: Tier,
    *,
    irreversible: bool,
    gated: bool,
    destructive: bool,
    remaining_budget: int,
    envelope: int,
) -> float:
    """Recommendation-strength signal in ``[0, 1]``, on the SAME scale as ``ladder_dearness`` (R3).

    Factors payoff-at-stake (the abstract ``{irreversible, gated, destructive}`` signal triple --
    at the `/plan` `ExecutionSpec.Unit` level this is derived from the unit's own `sandbox`
    (mutation_policy=read-write + workspace_isolation=ambient => higher irreversibility),
    `verify` panel, and fan-out `pilot` role; at the `outcome_spec.Node` level it is read
    directly from the node's own `gated`/`risky`/`destructive` fields) and the fraction of the
    spend envelope remaining. A unit at maximum stakes with a full remaining budget scores at
    the top of the ladder (``1.0``, matching ``ladder_dearness`` of the dearest tier); a unit at
    minimum stakes with a depleted budget scores at the bottom (``0.0``, matching the cheapest
    tier). ``tier`` is accepted for API symmetry with ``ladder_dearness`` callers but the score
    itself does not depend on the CURRENT tier -- it answers "how much is escalation worth here,"
    not "how dear is what's already assigned."
    """
    del tier  # symmetry parameter; the score is tier-independent by design (see docstring)
    stake = (int(irreversible) + int(gated) + int(destructive)) / 3.0
    budget_fraction = 1.0 if envelope <= 0 else max(0.0, min(1.0, remaining_budget / envelope))
    return stake * budget_fraction


# ---------------------------------------------------------------------------
# R2/KTD3 -- post-run reconcile (reads outcome_costs.py's rollup; writes nothing)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubplotReconcile:
    subplot_id: str
    estimate: int
    estimate_provenance: str
    deltas: dict[str, float]
    """Numeric delta (actual - estimated-baseline-of-0) for each commensurable field present."""
    context: dict[str, Any]
    """Real-telemetry fields rendered as labeled context, never coerced into the ordinal axis."""
    no_data: bool


def reconcile(
    spec: outcome_spec.OutcomeSpec,
    store: Any,
    issue_bodies: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Post-run estimate/actual/delta over ``outcome_costs.py``'s rollup (R2). Pure read.

    Never calls a ledger-write function (``outcome_store._write_once``, ``append_ledger``, or
    ``evidence_ledger.write``) -- this function only reads ``spec``/``store`` and returns a
    plain dict; the caller decides how (or whether) to print it.
    """
    node_estimates = {e.subplot_id: e for e in estimate_nodes(spec, issue_bodies)}
    per_subplot: list[SubplotReconcile] = []
    for node in spec.nodes:
        est = node_estimates[node.subplot_id]
        rec = outcome_costs.subplot_cost(store, node.subplot_id)
        if not rec:
            per_subplot.append(
                SubplotReconcile(
                    subplot_id=node.subplot_id,
                    estimate=est.spend,
                    estimate_provenance=est.provenance,
                    deltas={},
                    context={},
                    no_data=True,
                )
            )
            continue
        deltas: dict[str, float] = {}
        for field_name in _COMMENSURABLE_FIELDS:
            actual = rec.get(field_name)
            if isinstance(actual, (int, float)) and not isinstance(actual, bool):
                # The estimate's implicit clean-run baseline for these two fields is 0.
                deltas[field_name] = float(actual) - 0.0
        context: dict[str, Any] = {}
        for field_name in _CONTEXT_ONLY_FIELDS:
            if field_name in rec:
                context[field_name] = rec[field_name]
        if "executor" in rec:
            context["executor"] = rec["executor"]
            context["declared_backend"] = node.backend
            context["backend_matches_executor"] = rec["executor"] == node.backend
        per_subplot.append(
            SubplotReconcile(
                subplot_id=node.subplot_id,
                estimate=est.spend,
                estimate_provenance=est.provenance,
                deltas=deltas,
                context=context,
                no_data=False,
            )
        )

    any_data = any(not r.no_data for r in per_subplot)
    result: dict[str, Any] = {
        "per_subplot": [
            {
                "subplot_id": r.subplot_id,
                "estimate": r.estimate,
                "estimate_provenance": r.estimate_provenance,
                "no_data": r.no_data,
                **({} if r.no_data else {"deltas": r.deltas, "context": r.context}),
            }
            for r in per_subplot
        ],
        "estimate_total": sum(r.estimate for r in per_subplot),
    }
    if not any_data:
        result["status"] = "no data yet"
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_execution_spec(path: Path) -> execution_spec.ExecutionSpec:
    return execution_spec.ExecutionSpec.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _load_outcome_spec(path: Path) -> outcome_spec.OutcomeSpec:
    return outcome_spec.OutcomeSpec.from_dict(json.loads(path.read_text(encoding="utf-8")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pre-run spend estimate + tier-value scoring + post-run reconcile (#402 U1)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_est = sub.add_parser("estimate", help="render the ordinal estimate table")
    group = p_est.add_mutually_exclusive_group(required=True)
    group.add_argument("--spec", type=Path, help="an execution-spec.json (single-session units)")
    group.add_argument("--outcome-spec", type=Path, help="an outcome-spec.json (/outcome DAG)")

    p_rec = sub.add_parser("reconcile", help="print estimate/actual/delta from the cost ledger")
    p_rec.add_argument("--outcome-spec", type=Path, required=True)
    p_rec.add_argument(
        "--store-root", type=Path, required=True, help="the outcome's cost-ledger store root"
    )

    args = parser.parse_args(argv)
    try:
        if args.cmd == "estimate":
            if args.spec:
                spec = _load_execution_spec(args.spec)
                print(render_estimate_table(spec))
            else:
                out_spec = _load_outcome_spec(args.outcome_spec)
                for e in estimate_nodes(out_spec):
                    print(
                        f"{e.subplot_id}  {e.tier.model}/{e.tier.effort}  {e.spend}  ({e.provenance})"
                    )
            return 0
        if args.cmd == "reconcile":
            import outcome_store

            out_spec = _load_outcome_spec(args.outcome_spec)
            store = outcome_store.Store(root=args.store_root).ensure()
            report = reconcile(out_spec, store)
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0
    except (
        execution_spec.SpecError,
        outcome_spec.OutcomeSpecError,
        SpendEstimateError,
        json.JSONDecodeError,
    ) as exc:
        print(f"SPEND ESTIMATE ERROR: {exc}", file=sys.stderr)
        return 2

    parser.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
