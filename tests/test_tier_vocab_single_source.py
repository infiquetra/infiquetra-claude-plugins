"""Single-source tier palette guards (#370).

Covers the registry-derived vocabulary (U1), the ladder operations and effort-ceiling
clamp (U2), the unsupported-combo HALT + ladder-monotonicity invariant (U3), the
repo-wide bare-literal drift guard (U4), and the operator-table sync check + onboarding
guard (U5). The vocabulary now lives in fleet-core's ``tier_palette.py``, derived from
``models.json`` — these tests are the standing drift guards the issue's Definition of
Done requires.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
FLEET_CORE_SCRIPTS = REPO_ROOT / "plugins" / "fleet-core" / "scripts"
MODELS_JSON = FLEET_CORE_SCRIPTS / "fleet_commons" / "models.json"

sys.path.insert(0, str(FLEET_CORE_SCRIPTS))

from fleet_commons import tier_palette  # noqa: E402
from fleet_commons.tier_palette import TierPaletteError  # noqa: E402


# ---------------------------------------------------------------------------
# U1 (AC2) — MODELS/EFFORTS derive from models.json's explicit rank/rung.
# ---------------------------------------------------------------------------


def test_registry_rank_order() -> None:
    """The derived tuples equal the registry's explicit rank/rung ordering."""
    registry = tier_palette._load_registry()
    models_by_rank = tuple(
        name for name, _ in sorted(registry["models"].items(), key=lambda kv: kv[1]["rank"])
    )
    efforts_by_rung = tuple(
        name for name, _ in sorted(registry["efforts"].items(), key=lambda kv: kv[1]["rung"])
    )
    assert tier_palette.MODELS == models_by_rank
    assert tier_palette.EFFORTS == efforts_by_rung
    # The public vocabulary must not have drifted from the historical order either.
    assert tier_palette.MODELS == ("fable", "opus", "sonnet", "haiku")
    assert tier_palette.EFFORTS == ("low", "medium", "high", "xhigh")


def test_registry_rank_order_rejects_mis_ranked_row() -> None:
    """A scratch registry that swaps two ranks derives a different (wrong) order."""
    scratch = {
        "fable": {"rank": 1, "effort_ceiling": "xhigh"},  # deliberately swapped with opus
        "opus": {"rank": 0, "effort_ceiling": "xhigh"},
        "sonnet": {"rank": 2, "effort_ceiling": "xhigh"},
        "haiku": {"rank": 3, "effort_ceiling": "high"},
    }
    derived = tier_palette._derive_ordered(scratch, "rank", "model")
    assert derived == ("opus", "fable", "sonnet", "haiku")
    assert derived != tier_palette.MODELS  # the guard would catch this drift


def test_registry_rejects_duplicate_rank() -> None:
    scratch = {"a": {"rank": 0}, "b": {"rank": 0}}
    with pytest.raises(TierPaletteError, match="duplicated"):
        tier_palette._derive_ordered(scratch, "rank", "model")


def test_registry_rejects_gapped_rank() -> None:
    scratch = {"a": {"rank": 0}, "b": {"rank": 2}}
    with pytest.raises(TierPaletteError, match="not contiguous"):
        tier_palette._derive_ordered(scratch, "rank", "model")


def test_registry_rejects_missing_effort_ceiling() -> None:
    scratch = {"models": {"a": {"rank": 0}}, "efforts": {"low": {"rung": 0}}}
    with pytest.raises(TierPaletteError, match="missing 'effort_ceiling'"):
        tier_palette._derive_effort_ceilings(scratch, ("low",))


def test_effort_ceiling_values_anchor_on_haiku() -> None:
    """haiku's ceiling is 'high' (the issue's canonical unsupported combo is haiku/xhigh)."""
    assert tier_palette.effort_ceiling("haiku") == "high"
    for model in ("fable", "opus", "sonnet"):
        assert tier_palette.effort_ceiling(model) == "xhigh"
    with pytest.raises(ValueError, match="unknown model"):
        tier_palette.effort_ceiling("gpt-9")
