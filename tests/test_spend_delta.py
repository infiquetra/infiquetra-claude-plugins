"""Tests for #367 U1 (spend_delta + is_escalation) and U2 (adjacent_tier).

Covers `-k spend_delta` and `-k adjacent_tier_boundary`. The is_escalation grid test is the R2
behavior-preservation guard: is_escalation keeps its exact pre-#367 semantics and deliberately differs
from `spend_delta == "escalate"` on mixed/identical moves.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
EXECUTION_SPEC_SCRIPT = SCRIPT_DIR / "execution_spec.py"


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ES = _load("execution_spec", EXECUTION_SPEC_SCRIPT)


def _t(model: str, effort: str) -> Any:
    return ES.Tier(model=model, effort=effort)


def test_spend_delta_escalate_both_axes() -> None:
    assert ES.spend_delta(_t("sonnet", "medium"), _t("opus", "high")) == "escalate"


def test_spend_delta_cheapen_both_axes() -> None:
    assert ES.spend_delta(_t("opus", "high"), _t("sonnet", "low")) == "cheapen"


def test_spend_delta_lateral_transposition() -> None:
    # opus/low -> sonnet/xhigh: weaker model, stronger effort -> a sideways trade, not a direction.
    assert ES.spend_delta(_t("opus", "low"), _t("sonnet", "xhigh")) == "lateral"


def test_spend_delta_identical_is_lateral() -> None:
    assert ES.spend_delta(_t("sonnet", "high"), _t("sonnet", "high")) == "lateral"


def test_spend_delta_one_axis_up_other_same_is_escalate() -> None:
    assert ES.spend_delta(_t("sonnet", "medium"), _t("sonnet", "high")) == "escalate"
    assert ES.spend_delta(_t("sonnet", "medium"), _t("opus", "medium")) == "escalate"


def test_spend_delta_one_axis_down_other_same_is_cheapen() -> None:
    assert ES.spend_delta(_t("opus", "high"), _t("opus", "medium")) == "cheapen"


def test_is_escalation_unchanged_over_grid() -> None:
    """is_escalation keeps its exact pre-#367 semantics (stronger on either axis), and deliberately
    differs from spend_delta==escalate on a mixed move."""
    for m1 in ES.MODELS:
        for e1 in ES.EFFORTS:
            for m2 in ES.MODELS:
                for e2 in ES.EFFORTS:
                    old, new = _t(m1, e1), _t(m2, e2)
                    model_up = m1 != m2 and ES._tier_palette.stronger("model", m2, m1) == m2
                    effort_up = e1 != e2 and ES._tier_palette.stronger("effort", e2, e1) == e2
                    assert ES.is_escalation(old, new) == (model_up or effort_up)
    # The two predicates are distinct: a mixed move is an escalation but a lateral spend_delta.
    assert ES.is_escalation(_t("sonnet", "xhigh"), _t("opus", "low")) is True
    assert ES.spend_delta(_t("sonnet", "xhigh"), _t("opus", "low")) == "lateral"


def test_adjacent_tier_cheaper_and_dearer_mid_ladder() -> None:
    t = _t("sonnet", "high")
    cheaper = ES.adjacent_tier(t, "cheaper")
    dearer = ES.adjacent_tier(t, "dearer")
    assert ES.spend_delta(t, cheaper) == "cheapen"
    assert ES.spend_delta(t, dearer) == "escalate"


def test_adjacent_tier_boundary_raises() -> None:
    cheapest = _t("haiku", "low")  # weakest model, weakest effort
    dearest = _t("fable", "xhigh")  # strongest model, highest effort
    with pytest.raises(ES.SpecError, match="cheapest"):
        ES.adjacent_tier(cheapest, "cheaper")
    with pytest.raises(ES.SpecError, match="dearest"):
        ES.adjacent_tier(dearest, "dearer")


def test_adjacent_tier_cheaper_matches_cheaper_fallback() -> None:
    t = _t("opus", "high")
    m, e = ES._tier_resolver.cheaper_fallback(t.model, t.effort)
    result = ES.adjacent_tier(t, "cheaper")
    assert (result.model, result.effort) == (m, e)


def test_adjacent_tier_dearer_inverts_cheaper() -> None:
    t = _t("sonnet", "high")
    assert ES.adjacent_tier(ES.adjacent_tier(t, "dearer"), "cheaper") == t
