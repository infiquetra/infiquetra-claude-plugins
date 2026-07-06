#!/usr/bin/env python3
"""Dispatch-time tier resolver — maps a work shape to a ``{model, effort}`` tier (#362).

One callable seam for tier decisions that today live scattered across team-execution's 25
hardcoded agent ``model:`` literals, the prose-only heuristic table at
``plugins/saga/skills/plan/SKILL.md:298-304``, and assorted per-call literals. ``resolve()``
reads defaults from the machine-readable ``tier_policy.json`` registry (U1) and never hardcodes
a heuristic in code.

Imports ``MODELS``, ``EFFORTS``, ``model_rank``, ``effort_rank`` from ``tier_palette`` via
``fleet_commons_shim`` — never re-declaring the tuples (KTD1/KTD2).

``work_shape`` is the primary registry key; ``role_kind`` is an optional coarse refiner reserved
for a future v2 (unused today — v1 resolves purely from ``work_shape``). A ``role-tier:``
frontmatter value (KTD7) is a small alias that maps onto a ``work_shape`` registry row before
lookup, so migrated team-execution agents resolve through the same registry as everything else.

``cheaper_fallback`` steps exactly one rung down the ordered ladder (KTD3, ``{#tier-vocab-ordering}``):
weaken the model one ``MODELS`` rung first; once already at the weakest model, drop effort one
``EFFORTS`` rung instead. At the ladder floor (weakest model, lowest effort) the fallback equals
the resolved tier — a no-op floor, not an error.

The expensive-tier gate (KTD4, ``{#operator-choice-framework}``) sets ``needs_confirm`` when the
resolved tier is the strongest model (``fable``) or the highest effort (``xhigh``); the gate
itself is doc/CLI-driven and runtime-injected by the caller, not enforced here.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import fleet_commons_shim  # noqa: E402

_tier_palette = fleet_commons_shim.load("tier_palette")
MODELS: tuple[str, ...] = _tier_palette.MODELS
EFFORTS: tuple[str, ...] = _tier_palette.EFFORTS
model_rank = _tier_palette.model_rank
effort_rank = _tier_palette.effort_rank

TIER_POLICY_PATH = Path(__file__).resolve().parent / "tier_policy.json"

# The strongest model / highest effort rungs (KTD4): resolving to either gates on operator confirm.
_EXPENSIVE_MODELS = frozenset({MODELS[0]})
_EXPENSIVE_EFFORTS = frozenset({EFFORTS[-1]})

# KTD7: role-tier is a small agent-facing vocabulary mapping onto work-shape registry keys.
# Migrating team-execution's 25 agents onto these preserves each agent's pre-migration model
# (adversarial-review->opus, contract-test->sonnet, mechanical-scan->haiku).
ROLE_TIER_ALIASES: dict[str, str] = {
    "adversarial-review": "judgment",
    "contract-test": "mechanical",
    "mechanical-scan": "purely-mechanical",
}


class TierResolverError(ValueError):
    """Raised for an unresolvable work_shape/role_kind or an invalid override/ceiling."""


@dataclass(frozen=True)
class Resolution:
    model: str
    effort: str
    because: str
    cheaper_fallback: tuple[str, str]
    needs_confirm: bool


def load_policy(path: Path | None = None) -> dict[str, dict[str, str]]:
    """Load the work-shape -> tier registry (U1's ``tier_policy.json``)."""
    policy_path = path if path is not None else TIER_POLICY_PATH
    data: Any = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TierResolverError(f"tier policy at {policy_path} must be a JSON object")
    return data


def _canonical_work_shape(work_shape: str) -> str:
    """Map a ``role-tier:`` alias (KTD7) onto its registry work-shape key, else pass through."""
    return ROLE_TIER_ALIASES.get(work_shape, work_shape)


def cheaper_fallback(model: str, effort: str) -> tuple[str, str]:
    """One rung down the ladder (KTD3): weaken model first, then effort; floor is a no-op."""
    rung = model_rank(model)
    if rung < len(MODELS) - 1:
        return MODELS[rung + 1], effort
    tier = effort_rank(effort)
    if tier > 0:
        return model, EFFORTS[tier - 1]
    return model, effort


def resolve(
    role_kind: str | None,
    work_shape: str,
    envelope_ceiling: str | None = None,
    operator_override: dict[str, str] | None = None,
    *,
    policy: dict[str, dict[str, str]] | None = None,
) -> Resolution:
    """Resolve ``(role_kind, work_shape, envelope_ceiling, operator_override)`` to a tier.

    ``role_kind`` is accepted and validated shape-wise but unused in v1 (reserved coarse
    refiner). ``work_shape`` (after resolving any ``role-tier:`` alias) is the registry lookup
    key. ``envelope_ceiling``, when supplied, clamps the resolved model to no stronger than the
    ceiling (forward-compat for #366's spend envelope; ``None`` is honored as "no ceiling", never
    an error). ``operator_override`` replaces ``model``/``effort`` outright when supplied.
    """
    if role_kind is not None and not isinstance(role_kind, str):
        raise TierResolverError("role_kind must be a string or None")

    registry = policy if policy is not None else load_policy()
    key = _canonical_work_shape(work_shape)
    if key not in registry:
        raise TierResolverError(
            f"unknown work_shape {work_shape!r}; expected one of {sorted(registry)} "
            f"or a role-tier alias in {sorted(ROLE_TIER_ALIASES)}"
        )

    row = registry[key]
    model = str(row["default_model"])
    effort = str(row["default_effort"])
    because = str(row["rationale"])

    if operator_override:
        override_model = operator_override.get("model")
        override_effort = operator_override.get("effort")
        if override_model is not None:
            if override_model not in MODELS:
                raise TierResolverError(
                    f"operator_override model {override_model!r} not in {MODELS}"
                )
            model = override_model
        if override_effort is not None:
            if override_effort not in EFFORTS:
                raise TierResolverError(
                    f"operator_override effort {override_effort!r} not in {EFFORTS}"
                )
            effort = override_effort
        because = f"operator override ({model}/{effort}) of default: {because}"

    if envelope_ceiling is not None:
        if envelope_ceiling not in MODELS:
            raise TierResolverError(f"envelope_ceiling {envelope_ceiling!r} not in {MODELS}")
        if model_rank(model) < model_rank(envelope_ceiling):
            because = f"{because} (clamped to envelope_ceiling={envelope_ceiling})"
            model = envelope_ceiling

    needs_confirm = model in _EXPENSIVE_MODELS or effort in _EXPENSIVE_EFFORTS

    return Resolution(
        model=model,
        effort=effort,
        because=because,
        cheaper_fallback=cheaper_fallback(model, effort),
        needs_confirm=needs_confirm,
    )


def _cli_resolve(args: argparse.Namespace) -> int:
    operator_override: dict[str, str] | None = None
    if args.override_model or args.override_effort:
        operator_override = {}
        if args.override_model:
            operator_override["model"] = args.override_model
        if args.override_effort:
            operator_override["effort"] = args.override_effort

    try:
        result = resolve(
            args.role_kind,
            args.work_shape,
            envelope_ceiling=args.envelope_ceiling,
            operator_override=operator_override,
        )
    except TierResolverError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = {
        "model": result.model,
        "effort": result.effort,
        "because": result.because,
        "cheaper_fallback": {
            "model": result.cheaper_fallback[0],
            "effort": result.cheaper_fallback[1],
        },
        "needs_confirm": result.needs_confirm,
    }
    print(json.dumps(payload, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tier_resolver")
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve_parser = subparsers.add_parser(
        "resolve", help="Resolve a work_shape (or role-tier alias) to a {model, effort} tier"
    )
    resolve_parser.add_argument(
        "--role-kind", default=None, help="Reserved coarse refiner (v1: unused)"
    )
    resolve_parser.add_argument(
        "--work-shape", required=True, help="Registry key or role-tier alias"
    )
    resolve_parser.add_argument(
        "--envelope-ceiling", default=None, help="Clamp the resolved model to no stronger than this"
    )
    resolve_parser.add_argument("--override-model", default=None, help="Operator model override")
    resolve_parser.add_argument("--override-effort", default=None, help="Operator effort override")
    resolve_parser.set_defaults(func=_cli_resolve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
