"""Tests for the itemized spend receipt + cheap-fallback counterfactual (#402 U2).

Pins R4 (counterfactual total == sum of each unit's declared fallback-tier cost, and every
above-fallback unit names a tradeoff), R9 (derived-on-read), and R10 (ordinal only).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ES = _load("execution_spec")
STORE = _load("outcome_store")
_load("evidence_ledger")
SE = _load("spend_estimate")
SR = _load("spend_receipt")


def _unit(unit_id: str, model: str, effort: str, **overrides: Any) -> Any:
    base: dict[str, Any] = {
        "unit_id": unit_id,
        "label": unit_id,
        "tier": {"model": model, "effort": effort},
        "prompt": "do the thing",
    }
    base.update(overrides)
    return ES.Unit.from_dict(base)


def _spec(*units: Any) -> Any:
    return ES.ExecutionSpec(name="demo", description="demo spec", units=list(units))


def test_counterfactual_total_matches_fallback_sum() -> None:
    top_model, top_effort = SE._tier_palette.MODELS[0], SE._tier_palette.EFFORTS[-1]
    units = [
        _unit("U1", top_model, top_effort, worth_it_because="deep judgment call"),
        _unit("U2", "haiku", "low"),  # baseline; adjacent_tier below sonnet/high is a cheapen
    ]
    spec = _spec(*units)
    receipts = SR.receipt_for_units(spec)
    cost_weights = SR._cost_weights()

    expected = sum(
        (
            cost_weights.to_spend(r.fallback_tier.model, r.fallback_tier.effort)
            if r.fallback_tier is not None
            else r.spend
        )
        for r in receipts
    )
    assert SR.counterfactual_total(receipts) == expected


def test_above_fallback_unit_names_tradeoff_others_do_not() -> None:
    top_model, top_effort = SE._tier_palette.MODELS[0], SE._tier_palette.EFFORTS[-1]
    cheap_model, cheap_effort = SE._tier_palette.MODELS[-1], SE._tier_palette.EFFORTS[0]
    units = [
        _unit("U1", top_model, top_effort, worth_it_because="deep judgment call"),
        _unit("U2", cheap_model, cheap_effort),
    ]
    spec = _spec(*units)
    receipts = {r.unit_id: r for r in SR.receipt_for_units(spec)}

    assert receipts["U1"].above_fallback is True
    assert receipts["U1"].tradeoff == "deep judgment call"


def test_unit_with_no_declared_fallback_uses_adjacent_tier() -> None:
    unit = _unit("U1", SE._tier_palette.MODELS[0], SE._tier_palette.EFFORTS[-1])
    assert unit.cheaper_fallback is None
    spec = _spec(unit)
    receipts = SR.receipt_for_units(spec)
    expected_fallback = ES.adjacent_tier(unit.tier, "cheaper")
    assert receipts[0].fallback_tier == expected_fallback
    assert receipts[0].fallback_source == "adjacent"


def test_unit_already_cheapest_renders_without_raising() -> None:
    cheap_model, cheap_effort = SE._tier_palette.MODELS[-1], SE._tier_palette.EFFORTS[0]
    unit = _unit("U1", cheap_model, cheap_effort)
    spec = _spec(unit)

    receipts = SR.receipt_for_units(spec)  # must not raise

    assert receipts[0].fallback_tier is None
    assert receipts[0].fallback_source == "already-cheapest"
    assert receipts[0].tradeoff == SR._ALREADY_CHEAPEST
    # Rendering must also not raise, and must surface the counterfactual placeholder.
    table = SR.render_receipt(spec)
    assert "already cheapest" in table


def test_declared_cheaper_fallback_takes_priority_over_adjacent() -> None:
    top_model, top_effort = SE._tier_palette.MODELS[0], SE._tier_palette.EFFORTS[-1]
    # A declared cheaper_fallback two rungs down from adjacent_tier's one-rung default.
    declared = ES.Tier(model=SE._tier_palette.MODELS[-1], effort=SE._tier_palette.EFFORTS[0])
    unit = _unit(
        "U1",
        top_model,
        top_effort,
        worth_it_because="justify",
        cheaper_fallback=declared.to_dict(),
    )
    spec = _spec(unit)
    receipts = SR.receipt_for_units(spec)
    assert receipts[0].fallback_tier == declared
    assert receipts[0].fallback_source == "declared"


def test_derived_on_read_no_write(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("spend_receipt must never call a ledger-write function")

    monkeypatch.setattr(STORE, "_write_once", _boom)
    monkeypatch.setattr(STORE, "append_ledger", _boom)
    evidence_ledger = sys.modules["evidence_ledger"]
    monkeypatch.setattr(evidence_ledger, "write", _boom)

    unit = _unit("U1", "sonnet", "high")
    spec = _spec(unit)
    SR.render_receipt(spec)  # must not touch any write function


def test_cli_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        SR.main(["--help"])
    assert exc_info.value.code == 0
