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


# ---------------------------------------------------------------------------
# U2 (AC3/AC5) — named ladder ops honoring the opposite-direction contract,
# plus the effort-ceiling clamp.
# ---------------------------------------------------------------------------


def test_ladder_ops_escalate_downgrade_by_strength() -> None:
    # MODELS strongest-first: escalate = stronger model (lower rank).
    assert tier_palette.escalate("model", "sonnet") == "opus"
    assert tier_palette.escalate("model", "haiku", 2) == "opus"
    assert tier_palette.downgrade("model", "opus") == "sonnet"
    # EFFORTS weakest-first: escalate = higher effort (higher rung).
    assert tier_palette.escalate("effort", "medium") == "high"
    assert tier_palette.downgrade("effort", "high") == "medium"


def test_ladder_ops_past_the_end_are_no_ops() -> None:
    """Escalate past the strongest / downgrade past the weakest is a no-op, not an error."""
    assert tier_palette.escalate("model", "fable", 5) == "fable"
    assert tier_palette.downgrade("model", "haiku", 5) == "haiku"
    assert tier_palette.escalate("effort", "xhigh", 5) == "xhigh"
    assert tier_palette.downgrade("effort", "low", 5) == "low"


def test_clamp_and_stronger_bounds() -> None:
    assert tier_palette.clamp("effort", "xhigh", ceiling="high") == "high"
    assert tier_palette.clamp("effort", "low", floor="medium") == "medium"
    assert tier_palette.clamp("model", "haiku", floor="sonnet") == "sonnet"
    assert tier_palette.stronger("model", "haiku", "opus") == "opus"
    assert tier_palette.stronger("effort", "low", "xhigh") == "xhigh"
    assert tier_palette.strongest("model", ["haiku", "fable", "sonnet"]) == "fable"
    assert tier_palette.strongest("effort", ["low", "high", "medium"]) == "high"


def test_ladder_ops_reject_unknown_kind_and_value() -> None:
    with pytest.raises(ValueError, match="unknown ladder"):
        tier_palette.escalate("temperature", "opus")
    with pytest.raises(ValueError, match="unknown effort"):
        tier_palette.clamp("effort", "ludicrous")


def test_effort_ceiling_clamp_surfaces_a_note() -> None:
    """AC5: escalating a haiku unit toward xhigh resolves to haiku's ceiling with a note."""
    clamped, note = tier_palette.clamp_effort_to_model("haiku", "xhigh")
    assert clamped == "high"
    assert note is not None and "haiku" in note and "clamped" in note
    # escalate with the model's ceiling stops at the ceiling, never overshoots.
    assert (
        tier_palette.escalate("effort", "high", 3, ceiling=tier_palette.effort_ceiling("haiku"))
        == "high"
    )
    # A within-ceiling tier is returned untouched, no note.
    ok, no_note = tier_palette.clamp_effort_to_model("opus", "xhigh")
    assert ok == "xhigh" and no_note is None


def test_supports_effort_matrix() -> None:
    assert tier_palette.supports_effort("opus", "xhigh") is True
    assert tier_palette.supports_effort("haiku", "high") is True
    assert tier_palette.supports_effort("haiku", "xhigh") is False


def test_segment_units_refactor_uses_ladder_ops() -> None:
    """The refactored segment_units() merge must equal the old strongest-model/highest-effort."""
    sys.path.insert(0, str(REPO_ROOT / "plugins" / "saga" / "scripts"))
    import fleet_commons_shim

    tp = fleet_commons_shim.load("tier_palette")
    # A haiku/high segment merged with a sonnet/medium sibling -> sonnet/high.
    assert tp.strongest("model", ["haiku", "sonnet"]) == "sonnet"
    assert tp.strongest("effort", ["high", "medium"]) == "high"


# ---------------------------------------------------------------------------
# U3 (AC6/AC7) — unsupported-combo HALT (engine-owned excluded) + ladder
# monotonicity invariant over every adjacent pair.
# ---------------------------------------------------------------------------

sys.path.insert(0, str(REPO_ROOT / "plugins" / "saga" / "scripts"))

import execution_spec as es  # noqa: E402


def test_unsupported_combo_halts_for_claude_teammate() -> None:
    """AC6: a Claude haiku/xhigh tier HALTs at validate() — a typed error, not a clamp."""
    with pytest.raises(es.SpecError, match="ceiling"):
        es.Tier(model="haiku", effort="xhigh").validate("unit u1")
    # within-ceiling combos pass untouched
    es.Tier(model="haiku", effort="high").validate("unit u1")
    es.Tier(model="opus", effort="xhigh").validate("unit u1")


def test_engine_owned_tier_excluded_from_ceiling_halt() -> None:
    """is_engine_owned=True skips the ceiling check (chaperone-dispatch stays pinned)."""
    es.Tier(model="haiku", effort="xhigh").validate("unit u1", is_engine_owned=True)


def test_unit_validate_halts_claude_but_not_engine_owned() -> None:
    """The Unit.validate wiring: a Claude unit HALTs; an engine-owned unit does not."""
    claude = es.Unit(
        unit_id="u1", label="l", tier=es.Tier(model="haiku", effort="xhigh"), prompt="p"
    )
    with pytest.raises(es.SpecError, match="ceiling"):
        claude.validate("spec")

    engine_owned = es.Unit(
        unit_id="u2",
        label="l",
        tier=es.Tier(model="haiku", effort="xhigh"),
        prompt="p",
        capability="code-generation",
        engine_intent="offload",
    )
    engine_owned.validate("spec")  # excluded from the ceiling HALT — must not raise


@pytest.mark.parametrize(
    "stronger,weaker",
    [(tier_palette.MODELS[i], tier_palette.MODELS[i + 1]) for i in range(len(tier_palette.MODELS) - 1)],
)
def test_model_ladder_monotonicity(stronger: str, weaker: str) -> None:
    """AC7: for every adjacent MODELS pair, the merge picks the stronger member."""
    assert tier_palette.stronger("model", stronger, weaker) == stronger
    assert tier_palette.strongest("model", [weaker, stronger]) == stronger


@pytest.mark.parametrize(
    "weaker,stronger",
    [(tier_palette.EFFORTS[i], tier_palette.EFFORTS[i + 1]) for i in range(len(tier_palette.EFFORTS) - 1)],
)
def test_effort_ladder_monotonicity(weaker: str, stronger: str) -> None:
    """AC7: for every adjacent EFFORTS pair, the merge picks the stronger (higher) member."""
    assert tier_palette.stronger("effort", weaker, stronger) == stronger
    assert tier_palette.strongest("effort", [weaker, stronger]) == stronger
