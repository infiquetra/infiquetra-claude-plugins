#!/usr/bin/env python3
"""Canonical fleet tier palette — the model/effort vocabulary shared across plugins.

Moved verbatim from ``plugins/saga/scripts/execution_spec.py`` (fleet-commons first
mover, issue #463 / DECISIONS ``{#fleet-commons-mechanism-463}``). saga re-exports
these names through its vendored ``fleet_commons_shim``; other consumers load this
module the same way. Content changes here are additive-only within fleet-core 0.x
(KTD5): a consumer never breaks because fleet-core updated.

ORDERING IS LOAD-BEARING (``{#tier-vocab-ordering}``): consumers merge tiers
upgrade-only via ``min(MODELS.index)`` / ``max(EFFORTS.index)``, so MODELS is
strongest-first and EFFORTS is weakest-first. Use ``model_rank()`` /
``effort_rank()`` instead of re-deriving index arithmetic.
"""

from __future__ import annotations

# Closed model vocabulary, strongest-first. Consumers validate authored tiers
# against this set so a typo ("opus-high") fails loudly instead of silently
# producing an un-runnable dispatch.
MODELS = ("fable", "opus", "sonnet", "haiku")

# Closed effort vocabulary, weakest-first.
EFFORTS = ("low", "medium", "high", "xhigh")

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
