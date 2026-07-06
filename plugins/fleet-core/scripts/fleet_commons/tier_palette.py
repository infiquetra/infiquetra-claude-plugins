#!/usr/bin/env python3
"""Canonical fleet tier palette — the model/effort vocabulary shared across plugins.

Moved verbatim from ``plugins/saga/scripts/execution_spec.py`` (fleet-commons first
mover, issue #463 / DECISIONS ``{#fleet-commons-mechanism-463}``), then made
registry-backed in #370: the ordered ``MODELS`` / ``EFFORTS`` tuples are **derived at
import** from the explicit ``rank`` / ``rung`` indices in ``models.json`` rather than
hand-ordered here. saga re-exports these names through its vendored
``fleet_commons_shim``; other consumers load this module the same way. Content changes
here are additive-only within fleet-core 0.x (KTD5): a consumer never breaks because
fleet-core updated.

ORDERING IS LOAD-BEARING (``{#tier-vocab-ordering}``): consumers merge tiers
upgrade-only via ``min(MODELS.index)`` / ``max(EFFORTS.index)``, so MODELS is
strongest-first and EFFORTS is weakest-first. Use ``model_rank()`` / ``effort_rank()``
(or the ``escalate`` / ``downgrade`` / ``clamp`` ladder ops) instead of re-deriving
index arithmetic. To add a model/effort, edit ``models.json`` — never a second bare
literal. See ``plugins/fleet-core/references/tier-palette.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

MODELS_REGISTRY_PATH = Path(__file__).resolve().parent / "models.json"


class TierPaletteError(ValueError):
    """Raised when ``models.json`` is malformed (bad rank/rung/ceiling)."""


def _load_registry(path: Path = MODELS_REGISTRY_PATH) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _derive_ordered(rows: dict, index_key: str, kind: str) -> tuple[str, ...]:
    """Return names ordered by their explicit integer index (0..n-1, contiguous, unique).

    A missing/duplicate/gapped/non-int index raises ``TierPaletteError`` at import —
    a silently mis-ordered tuple would corrupt every upgrade-only tier merge downstream.
    """
    indexed: list[tuple[int, str]] = []
    seen: set[int] = set()
    for name, row in rows.items():
        if index_key not in row:
            raise TierPaletteError(f"{kind} {name!r} missing {index_key!r} in models.json")
        idx = row[index_key]
        if not isinstance(idx, int) or isinstance(idx, bool):
            raise TierPaletteError(f"{kind} {name!r} {index_key} must be an int, got {idx!r}")
        if idx in seen:
            raise TierPaletteError(f"{kind} {index_key} {idx} is duplicated in models.json")
        seen.add(idx)
        indexed.append((idx, name))
    if seen != set(range(len(indexed))):
        raise TierPaletteError(
            f"{kind} {index_key} values {sorted(seen)} are not contiguous 0..{len(indexed) - 1}"
        )
    return tuple(name for _, name in sorted(indexed))


def _derive_effort_ceilings(registry: dict, efforts: tuple[str, ...]) -> dict[str, str]:
    """Map each model to its ``effort_ceiling``; raise on a missing/unknown ceiling."""
    ceilings: dict[str, str] = {}
    for name, row in registry["models"].items():
        ceiling = row.get("effort_ceiling")
        if ceiling is None:
            raise TierPaletteError(f"model {name!r} missing 'effort_ceiling' in models.json")
        if ceiling not in efforts:
            raise TierPaletteError(
                f"model {name!r} effort_ceiling {ceiling!r} is not a known effort {efforts}"
            )
        ceilings[name] = ceiling
    return ceilings


_REGISTRY = _load_registry()

# Closed model vocabulary, strongest-first — derived from models.json ``rank``.
# Consumers validate authored tiers against this set so a typo ("opus-high") fails
# loudly instead of silently producing an un-runnable dispatch.
MODELS = _derive_ordered(_REGISTRY["models"], "rank", "model")

# Closed effort vocabulary, weakest-first — derived from models.json ``rung``.
EFFORTS = _derive_ordered(_REGISTRY["efforts"], "rung", "effort")

# Per-model effort ceiling: the strongest effort the model actually runs. haiku
# clamps below xhigh; the ladder ops and Tier.validate() consult this (#370).
_EFFORT_CEILINGS = _derive_effort_ceilings(_REGISTRY, EFFORTS)

# Models cheap enough that budget-discipline lessons (brevity, mandatory final
# emit, skim-don't-read, batch concurrency) MUST be baked into generated agent
# prompts. Public at the canonical home; saga's re-export keeps its private
# ``_CHEAP_MODELS`` alias.
CHEAP_MODELS = ("haiku",)

# Delegation-intent vocabulary for an engine/capability unit: ``offload`` wants a
# cheap chaperone (the delegation is net-negative otherwise); ``second-opinion``
# wants an expensive one (adversarial verification IS the product).
ENGINE_INTENTS = ("offload", "second-opinion")


def model_rank(model: str) -> int:
    """Rank of ``model`` with 0 the strongest; raises ValueError when unknown."""
    try:
        return MODELS.index(model)
    except ValueError:
        raise ValueError(f"unknown model {model!r}; expected one of {MODELS}") from None


def effort_rank(effort: str) -> int:
    """Rank of ``effort`` with 0 the weakest; raises ValueError when unknown."""
    try:
        return EFFORTS.index(effort)
    except ValueError:
        raise ValueError(f"unknown effort {effort!r}; expected one of {EFFORTS}") from None


def effort_ceiling(model: str) -> str:
    """The strongest effort ``model`` actually runs; raises ValueError when unknown."""
    try:
        return _EFFORT_CEILINGS[model]
    except KeyError:
        raise ValueError(f"unknown model {model!r}; expected one of {MODELS}") from None
