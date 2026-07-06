#!/usr/bin/env python3
"""Ordinal cost-weight table — priced magnitude for the fleet tier lever (#366).

The tier vocabularies in ``tier_palette.py`` are *ordered* (strongest-first models,
weakest-first efforts) but not *priced*: nothing turns the ordering into a comparable
number. ``to_spend(model, effort)`` closes that gap by mapping every ``{model, effort}``
cell to a single ordinal weight, so any lever that needs to ask "how expensive is this
tier?" calls ONE function instead of hand-rolling index arithmetic (the drift
``{#tier-vocab-ordering}`` warns about).

The 4x4 weight grid lives in ``cost_weights.json`` beside this module (hand-authored,
non-linear so premium tiers cost disproportionately more). It is validated at IMPORT
against the live ``tier_palette`` ordering — completeness, per-axis strict monotonicity,
and off-palette-key rejection all raise ``CostWeightsError`` here rather than letting a
drifted table silently mis-price a run. A malformed table therefore fails fast and loud,
exactly like ``tier_palette`` failing on a malformed ``models.json``.

Weights are ORDINAL/RELATIVE, never dollar prices (#366 non-goal): stable across provider
price changes. The guard checks only the *per-axis* monotonic contract; the *cross-axis*
magnitude (is ``opus/low`` dearer than ``sonnet/xhigh``?) is the authored ordinal judgment
in the JSON values, not machine-checkable beyond the corner invariant enforced by the
per-axis walk (strongest/highest cell outranks the weakest/lowest).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import fleet_commons_shim  # noqa: E402  (after the sys.path bootstrap, by design)

_tier_palette = fleet_commons_shim.load("tier_palette")
MODELS: tuple[str, ...] = _tier_palette.MODELS
EFFORTS: tuple[str, ...] = _tier_palette.EFFORTS

COST_WEIGHTS_PATH = Path(__file__).resolve().parent / "cost_weights.json"


class CostWeightsError(ValueError):
    """Raised when ``cost_weights.json`` is malformed, incomplete, off-palette, or non-monotonic."""


def _load_table(path: Path = COST_WEIGHTS_PATH) -> dict[str, dict[str, int]]:
    """Read the raw ``weights`` map from the JSON registry (int cells only)."""
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    weights = raw.get("weights")
    if not isinstance(weights, dict):
        raise CostWeightsError(f"{path}: top-level 'weights' object is missing or not a map")
    table: dict[str, dict[str, int]] = {}
    for model, row in weights.items():
        if not isinstance(row, dict):
            raise CostWeightsError(f"cost weights for model {model!r} is not a map")
        cells: dict[str, int] = {}
        for effort, value in row.items():
            # bool is an int subclass -- reject it explicitly so `true` is never a weight.
            if not isinstance(value, int) or isinstance(value, bool):
                raise CostWeightsError(
                    f"cost weight for {model!r}/{effort!r} must be an int, got {value!r}"
                )
            cells[effort] = value
        table[model] = cells
    return table


def _validate_table(table: dict[str, dict[str, int]]) -> None:
    """Enforce completeness, off-palette rejection, and per-axis strict monotonicity.

    Every ``MODELS x EFFORTS`` cell must be present, no key may fall outside the palette,
    and every single step up either axis (stronger model, higher effort) must strictly
    increase the weight. Any violation raises ``CostWeightsError`` at import.
    """
    # Off-palette rejection: no model/effort key outside the closed vocabularies.
    for model, row in table.items():
        if model not in MODELS:
            raise CostWeightsError(
                f"cost_weights.json has off-palette model {model!r}; expected one of {MODELS}"
            )
        for effort in row:
            if effort not in EFFORTS:
                raise CostWeightsError(
                    f"cost_weights.json has off-palette effort {effort!r} under model {model!r}; "
                    f"expected one of {EFFORTS}"
                )
    # Completeness: every cell of the MODELS x EFFORTS grid present.
    for model in MODELS:
        if model not in table:
            raise CostWeightsError(f"cost_weights.json missing model {model!r}")
        for effort in EFFORTS:
            if effort not in table[model]:
                raise CostWeightsError(f"cost_weights.json missing cell {model!r}/{effort!r}")

    # Per-axis strict monotonicity. EFFORTS is weakest-first, so weight must strictly
    # increase along the tuple order; MODELS is strongest-first (rank 0 = most expensive),
    # so weight must strictly DECREASE along the tuple order (each weaker model is cheaper).
    for model in MODELS:
        for weaker, stronger in zip(EFFORTS, EFFORTS[1:], strict=False):
            if table[model][stronger] <= table[model][weaker]:
                raise CostWeightsError(
                    f"cost_weights.json non-monotonic on effort axis for model {model!r}: "
                    f"{stronger!r} ({table[model][stronger]}) must exceed "
                    f"{weaker!r} ({table[model][weaker]})"
                )
    for effort in EFFORTS:
        for stronger_model, weaker_model in zip(MODELS, MODELS[1:], strict=False):
            if table[weaker_model][effort] >= table[stronger_model][effort]:
                raise CostWeightsError(
                    f"cost_weights.json non-monotonic on model axis at effort {effort!r}: "
                    f"stronger model {stronger_model!r} ({table[stronger_model][effort]}) must "
                    f"exceed weaker model {weaker_model!r} ({table[weaker_model][effort]})"
                )


_WEIGHTS: dict[str, dict[str, int]] = _load_table()
_validate_table(_WEIGHTS)


def to_spend(model: str, effort: str) -> int:
    """Return the ordinal cost weight for a ``{model, effort}`` tier.

    Raises ``CostWeightsError`` for any model/effort outside the closed palette, so a
    typo prices loudly instead of silently returning a default.
    """
    if model not in _WEIGHTS:
        raise CostWeightsError(f"unknown model {model!r}; expected one of {MODELS}")
    row = _WEIGHTS[model]
    if effort not in row:
        raise CostWeightsError(f"unknown effort {effort!r}; expected one of {EFFORTS}")
    return row[effort]


def load_cost_weights() -> dict[str, dict[str, int]]:
    """Return a copy of the validated weight grid (defensive — callers cannot mutate the cache)."""
    return {model: dict(row) for model, row in _WEIGHTS.items()}
