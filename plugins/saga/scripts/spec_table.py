#!/usr/bin/env python3
"""Render an execution spec as an operator-readable approval table (#668).

Every backend approval is an operator decision, and an operator cannot approve what they cannot
read. Before this module the only rendering of a spec was ``json.dumps`` -- ``/plan`` Step 5 asked
the operator to "confirm the tier assignments and the control-flow structure" while handing them a
JSON blob, and ``outcome.py`` carried 25 ``json.dumps`` calls and no table at all.

The approval question is not "what is in this spec" but **"what am I authorizing, at what tier,
under what enforcement, in what order, for what spend"**. So the table leads with the answer to
that question and the enforceability matrices sit beside the backend name -- a backend that cannot
enforce a sandbox axis the spec declares is the single most decision-relevant fact at an approval
gate, and it was previously invisible without reading ``execution_spec.py``'s source.

Rendered at every backend-approval point, not just ``/outcome``: ``/plan`` Step 5 (the primary
one), ``/tier`` after a mid-run patch, ``/work`` before execution, and ``/outcome`` dispatch.

House pattern (mirrors ``render_tier_table.py`` and ``execution_spec.py``): pure functions, no I/O
at import, markdown out. Table facts come from the spec and from ``execution_spec``'s own
enforceability registries -- never a second hand-maintained copy, so a registry edit is the only
way to change what this reports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import execution_spec as es  # noqa: E402

# Backends an operator can be asked to approve. Ordered cheapest-ceremony first.
KNOWN_BACKENDS = ("inline", "cc-workflows-ultracode", "team-execution")

_AXIS_LABEL = {
    "read-only": "read-only",
    "disposable-worktree": "disposable worktree",
    "owned-worktree": "owned worktree",
    "read-write": "read-write",
}


def _fmt_tier(tier: es.Tier | None) -> str:
    if tier is None:
        return "—"
    return f"`{tier.model}:{tier.effort}`"


def _unit_flags(unit: es.Unit) -> str:
    """The per-unit facts that change what an approval means."""
    flags: list[str] = []
    if unit.pilot:
        flags.append(f"pilot←`{unit.pilot}`")
    if unit.fanout:
        n = len(unit.targets or [])
        flags.append(f"fan-out ×{n}" if n else "fan-out (**no targets — emit will FAIL**)")
    if unit.verify:
        v = unit.verify
        panel = f"verify n={v.n}/{v.pass_rule}"
        if v.tier is not None:
            panel += f" @{v.tier.model}:{v.tier.effort}"
        if v.iterate_to_consensus:
            panel += f" ×{v.max_iterations}"
        flags.append(panel)
    if unit.engine:
        flags.append(f"engine=`{unit.engine}`")
    if unit.sandbox is not None:
        sb = unit.sandbox
        parts = [
            _AXIS_LABEL.get(sb.mutation_policy, sb.mutation_policy),
            _AXIS_LABEL.get(sb.workspace_isolation, sb.workspace_isolation),
        ]
        flags.append("sandbox: " + " + ".join(parts))
    if unit.escalation:
        flags.append("escalation")
    return "<br>".join(flags) if flags else "—"


def _sandbox_axes(unit: es.Unit) -> set[str]:
    if unit.sandbox is None:
        return set()
    return {unit.sandbox.mutation_policy, unit.sandbox.workspace_isolation}


def enforcement_rows(spec: es.ExecutionSpec, backend: str) -> list[tuple[str, str, str]]:
    """What this backend can and cannot enforce, against what the spec actually declares.

    Reads ``execution_spec``'s own registries. A backend absent from a registry enforces
    nothing -- unknown is never permissive, matching the emitter's own R3/R4 stance.
    """
    sandbox_ok = es.SANDBOX_ENFORCEABLE_BY_BACKEND.get(backend, frozenset())
    tier_ok = es.TIER_ENFORCEABLE_BY_BACKEND.get(backend, frozenset())

    declared_axes: set[str] = set()
    for unit in spec.units:
        declared_axes |= _sandbox_axes(unit)
        if unit.verify is not None:
            # Verifiers are always spawned read-only into a disposable worktree (KTD6).
            declared_axes |= {"read-only", "disposable-worktree"}
    # Default axes are a no-op every backend "enforces"; only restrictive ones matter.
    restrictive = {a for a in declared_axes if a not in ("read-write", "ambient")}

    declared_models = {u.tier.model for u in spec.units}
    for unit in spec.units:
        if unit.verify is not None and unit.verify.tier is not None:
            declared_models.add(unit.verify.tier.model)

    rows: list[tuple[str, str, str]] = []
    for axis in sorted(restrictive):
        label = _AXIS_LABEL.get(axis, axis)
        if axis in sandbox_ok:
            rows.append((f"sandbox: {label}", "enforced", "structurally guaranteed by the backend"))
        else:
            rows.append(
                (
                    f"sandbox: {label}",
                    "**NOT enforceable**",
                    "emit HALTs rather than render a guarantee it cannot keep",
                )
            )
    for model in sorted(declared_models):
        if model in tier_ok:
            rows.append((f"tier: {model}", "reachable", "backend can spawn at this model"))
        else:
            rows.append(
                (
                    f"tier: {model}",
                    "**NOT reachable**",
                    "emit HALTs — the backend cannot spawn this model",
                )
            )
    return rows


def render(
    spec: es.ExecutionSpec,
    *,
    backend: str | None = None,
    concurrency: int | None = None,
) -> str:
    """Render the whole approval view. Pure: no file or process I/O."""
    out: list[str] = []
    units_by_id = {u.unit_id: u for u in spec.units}

    out.append(f"## Execution plan — {spec.name}")
    out.append("")
    if spec.description:
        out.append(spec.description)
        out.append("")

    total_spend = sum(es.unit_spend(u) for u in spec.units)
    summary = [
        ("Backend", f"`{backend}`" if backend else "_not yet chosen_"),
        ("Units", str(len(spec.units))),
        ("Repo", f"`{spec.repo}`" if spec.repo else "—"),
    ]
    if concurrency is not None:
        summary.append(("Max concurrent", str(concurrency)))
    budget = spec.cost_budget
    if budget is not None:
        over = " ⚠️ **OVER BUDGET**" if total_spend > budget else ""
        summary.append(("Spend / budget", f"{total_spend} / {budget}{over}"))
    else:
        summary.append(("Spend (ordinal)", str(total_spend)))

    out.append("| | |")
    out.append("|---|---|")
    for k, v in summary:
        out.append(f"| **{k}** | {v} |")
    out.append("")

    # --- per-unit table ---
    out.append("### Units")
    out.append("")
    out.append("| Unit | Label | Tier | Depends on | Shape | Spend |")
    out.append("|---|---|---|---|---|---|")
    for unit in spec.units:
        deps = ", ".join(f"`{d}`" for d in unit.depends_on) if unit.depends_on else "—"
        label = unit.label or "—"
        out.append(
            f"| `{unit.unit_id}` | {label} | {_fmt_tier(unit.tier)} | {deps} "
            f"| {_unit_flags(unit)} | {es.unit_spend(unit)} |"
        )
    out.append("")

    # --- execution order ---
    try:
        layers = es.dependency_layers(spec)
    except es.SpecError as exc:
        out.append(f"### Execution order\n\n⚠️ **Cannot compute — {exc}**\n")
        layers = []
    if layers:
        out.append("### Execution order")
        out.append("")
        out.append("Each wave runs in parallel; waves are sequenced by a dependency barrier.")
        out.append("")
        for i, layer in enumerate(layers, start=1):
            names = ", ".join(
                f"`{uid}`" + (f" ({units_by_id[uid].label})" if units_by_id[uid].label else "")
                for uid in layer
            )
            width = f" — {len(layer)} in parallel" if len(layer) > 1 else ""
            out.append(f"{i}. {names}{width}")
        out.append("")

    # --- enforceability ---
    if backend:
        rows = enforcement_rows(spec, backend)
        out.append(f"### What `{backend}` can enforce")
        out.append("")
        if not any(req.startswith("sandbox:") for req, _, _ in rows):
            out.append(
                "This spec declares no restrictive sandbox axis, so no isolation guarantee is "
                "being asked of the backend."
            )
            out.append("")
        if rows:
            out.append("| Requirement | Status | Consequence |")
            out.append("|---|---|---|")
            for req, status, why in rows:
                out.append(f"| {req} | {status} | {why} |")
            out.append("")
            if any("NOT" in s for _, s, _ in rows):
                out.append(
                    "⚠️ At least one declared requirement is unenforceable on this backend. "
                    "`emit` will HALT rather than silently downgrade — pick another backend or "
                    "relax the requirement."
                )
                out.append("")
    return "\n".join(out).rstrip() + "\n"


def _load(path: Path) -> es.ExecutionSpec:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return es.ExecutionSpec.from_dict(data)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="spec_table.py",
        description="Render an execution spec as an operator approval table.",
    )
    ap.add_argument("spec", type=Path, help="path to a spec JSON")
    ap.add_argument(
        "--backend",
        choices=KNOWN_BACKENDS,
        help="backend being approved; adds the enforceability section",
    )
    ap.add_argument(
        "--concurrency", type=int, default=None, help="resolved max concurrent agents, if known"
    )
    args = ap.parse_args(argv)

    try:
        spec = _load(args.spec)
        table = render(spec, backend=args.backend, concurrency=args.concurrency)
    except FileNotFoundError:
        print(f"spec_table: no such spec: {args.spec}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"spec_table: {args.spec} is not valid JSON: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        # Deliberately broad, and deliberately covering render as well as load: a bad spec can
        # fail at either boundary. A tier naming an unknown model parses fine but raises
        # fleet_commons' CostWeightsError inside unit_spend, and future registries may raise
        # their own types. This is a read-only renderer at an approval gate -- an unreadable
        # spec must print why and exit 2, never traceback at the operator.
        print(f"spec_table: invalid spec: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(table, end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
