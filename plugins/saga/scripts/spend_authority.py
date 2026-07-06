#!/usr/bin/env python3
"""Per-repo spend-authority matrix — the silent/ask split as config (#367 U4).

The asymmetric approval rule (cheapening proceeds silently, spend increases ask) lives only in intake
prose today. This makes it per-repo config: a committed ``.saga/spend-authority.json`` names a
``silent_ceiling`` tier — a signature-authority limit, "authorized silently up to tier X". A unit tier
*above* the ceiling on either axis resolves to ``ask``; at or below it resolves to ``silent``.

Modeled on ``tier_defaults.py`` (#368): the file is committed (``.saga/`` is not git-ignored), a missing
file falls back to the **safe default** ``silent_ceiling = sonnet/high`` (so any premium tier -- opus/fable
model or xhigh effort -- asks), and a malformed one (bad JSON, off-palette or unrunnable tier) fails loud.

The "above the ceiling on either axis" predicate is the same one ``execution_spec.is_escalation`` uses,
so the worth-it hard-block (#367 U3) and this spend-authority default cannot disagree about what
"expensive" means (KTD5). It is re-expressed here on dict tiers (to keep this module dependency-light,
like ``tier_defaults``) and pinned to ``is_escalation`` by an exhaustive grid guard test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_commons_shim  # noqa: E402  (after the sys.path shim, by design)

_tier_palette = fleet_commons_shim.load("tier_palette")
MODELS: tuple[str, ...] = _tier_palette.MODELS
EFFORTS: tuple[str, ...] = _tier_palette.EFFORTS

# Committed, per-repo (sibling of tier-defaults.json under .saga/, NOT the git-ignored cache).
AUTHORITY_PATH = Path(".saga/spend-authority.json")

# The safe default when no matrix file is present (#367 R6 / KTD5/KTD6): authorized silently up to
# sonnet/high, so any premium tier (opus/fable model or xhigh effort) asks. Same baseline as the U3
# worth-it hard-block (SPEND_BASELINE), so the two levers agree on what "premium" means.
DEFAULT_SILENT_CEILING: dict[str, str] = {"model": "sonnet", "effort": "high"}

Tier = dict[str, str]
Authority = Literal["silent", "ask"]


class SpendAuthorityError(ValueError):
    """Raised for a malformed ``.saga/spend-authority.json`` (bad JSON, off-palette or unrunnable tier)."""


def _authority_path(root: Path | None = None) -> Path:
    return (root or Path.cwd()) / AUTHORITY_PATH


def _validate_ceiling(tier: object, where: str) -> Tier:
    if not isinstance(tier, dict) or "model" not in tier or "effort" not in tier:
        raise SpendAuthorityError(
            f"{where}: silent_ceiling must be {{'model', 'effort'}}, got {tier!r}"
        )
    model, effort = str(tier["model"]), str(tier["effort"])
    if model not in MODELS:
        raise SpendAuthorityError(f"{where}: model {model!r} not in {MODELS}")
    if effort not in EFFORTS:
        raise SpendAuthorityError(f"{where}: effort {effort!r} not in {EFFORTS}")
    if not _tier_palette.supports_effort(model, effort):
        raise SpendAuthorityError(
            f"{where}: {model}/{effort} is unrunnable ({model}'s ceiling is "
            f"{_tier_palette.effort_ceiling(model)!r})"
        )
    return {"model": model, "effort": effort}


def load_spend_authority(root: Path | None = None) -> Tier:
    """Return the repo's ``silent_ceiling`` tier; missing file => the safe default, malformed => raise."""
    path = _authority_path(root)
    if not path.exists():
        return dict(DEFAULT_SILENT_CEILING)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SpendAuthorityError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(data, dict) or "silent_ceiling" not in data:
        raise SpendAuthorityError(
            f"{path}: top level must be an object with a 'silent_ceiling' tier"
        )
    return _validate_ceiling(data["silent_ceiling"], f"{path}[silent_ceiling]")


def _above_ceiling(tier: Tier, ceiling: Tier) -> bool:
    """True iff ``tier`` is stronger than ``ceiling`` on either axis.

    The same predicate as ``execution_spec.is_escalation(ceiling, tier)`` (KTD5), re-expressed on dict
    tiers via the palette ``stronger`` op (never raw index). An exhaustive grid guard test asserts the
    two agree, so the worth-it hard-block and the spend-authority default cannot drift.
    """
    model_up = (
        tier["model"] != ceiling["model"]
        and _tier_palette.stronger("model", tier["model"], ceiling["model"]) == tier["model"]
    )
    effort_up = (
        tier["effort"] != ceiling["effort"]
        and _tier_palette.stronger("effort", tier["effort"], ceiling["effort"]) == tier["effort"]
    )
    return model_up or effort_up


def resolve_spend_authority(
    tier: Tier, ceiling: Tier | None = None, root: Path | None = None
) -> Authority:
    """Resolve one unit tier to ``silent`` or ``ask``.

    ``ask`` iff the tier is above the silent ceiling on either axis; ``silent`` at or below it. When
    ``ceiling`` is not passed, it is loaded from ``.saga/spend-authority.json`` (or the safe default).
    """
    resolved_ceiling = ceiling if ceiling is not None else load_spend_authority(root)
    return "ask" if _above_ceiling(tier, resolved_ceiling) else "silent"
