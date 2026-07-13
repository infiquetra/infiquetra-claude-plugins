"""Tests for the pre-run spend estimate, tier-value scoring, and post-run reconcile (#402 U1).

Pins R1 (an ordinal per-unit/per-node estimate), R2 (a post-run reconcile reading
``outcome_costs.py``'s rollup that writes nothing), R3 (the payoff-at-stake x
remaining-budget tier-value score), R9 (derived-on-read: no ledger-write function is ever
called), and R10 (ordinal only, never a fabricated token-to-ordinal exchange rate).
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
OS_ = _load("outcome_spec")
STORE = _load("outcome_store")
COSTS = _load("outcome_costs")
_load("tier_defaults")
SE = _load("spend_estimate")


def _unit(unit_id: str, model: str = "sonnet", effort: str = "high", **overrides: Any) -> Any:
    base: dict[str, Any] = {
        "unit_id": unit_id,
        "label": unit_id,
        "tier": {"model": model, "effort": effort},
        "prompt": "do the thing",
    }
    base.update(overrides)
    return ES.Unit.from_dict(base)


def _exec_spec(*units: Any) -> Any:
    return ES.ExecutionSpec(name="demo", description="demo spec", units=list(units))


def _node(subplot_id: str, **overrides: Any) -> Any:
    base: dict[str, Any] = {"subplot_id": subplot_id, "title": subplot_id}
    base.update(overrides)
    return OS_.Node.from_dict(base)


def _outcome_spec(*nodes: Any) -> Any:
    return OS_.OutcomeSpec(outcome_id="demo-outcome", objective="demo", nodes=list(nodes))


# ---------------------------------------------------------------------------
# Happy path -- estimate tables match hand-computed to_spend sums
# ---------------------------------------------------------------------------


def test_estimate_units_matches_hand_computed_to_spend_sum() -> None:
    units = [
        _unit("U1", "sonnet", "high"),
        _unit("U2", "haiku", "low"),
        _unit("U3", "opus", "high"),
    ]
    spec = _exec_spec(*units)
    estimates = SE.estimate_units(spec)
    cost_weights = SE._cost_weights()
    expected_total = sum(cost_weights.to_spend(u.tier.model, u.tier.effort) for u in units)
    assert sum(e.spend for e in estimates) == expected_total
    assert [e.unit_id for e in estimates] == ["U1", "U2", "U3"]
    table = SE.render_estimate_table(spec)
    assert f"**{expected_total}**" in table


def test_estimate_nodes_falls_back_to_baseline_without_tier_band() -> None:
    nodes = [_node("sub-1"), _node("sub-2")]
    spec = _outcome_spec(*nodes)
    estimates = SE.estimate_nodes(spec)
    assert all(e.provenance == "default" for e in estimates)
    assert all(e.tier == SE.SPEND_BASELINE for e in estimates)
    cost_weights = SE._cost_weights()
    expected = cost_weights.to_spend(SE.SPEND_BASELINE.model, SE.SPEND_BASELINE.effort)
    assert all(e.spend == expected for e in estimates)


def test_estimate_nodes_uses_issue_tier_band_when_present() -> None:
    node = _node("sub-1", github={"issue": "org/repo#1"})
    spec = _outcome_spec(node)
    issue_body = "### Recommended Tier Band\nopus/high\n"
    estimates = SE.estimate_nodes(spec, issue_bodies={"org/repo#1": issue_body})
    assert estimates[0].provenance == "issue-tier-band"
    assert estimates[0].tier.model == "opus"
    assert estimates[0].tier.effort == "high"


# ---------------------------------------------------------------------------
# Tier-value scoring matrix (T12-F5-7)
# ---------------------------------------------------------------------------


def test_tier_value_scoring_matrix() -> None:
    top_tier = ES.Tier(model=SE._tier_palette.MODELS[0], effort=SE._tier_palette.EFFORTS[-1])
    cheap_tier = ES.Tier(model=SE._tier_palette.MODELS[-1], effort=SE._tier_palette.EFFORTS[0])

    high_stakes_full_budget = SE.tier_value_score(
        top_tier,
        irreversible=True,
        gated=True,
        destructive=True,
        remaining_budget=100,
        envelope=100,
    )
    assert high_stakes_full_budget >= SE.ladder_dearness(top_tier)

    low_stakes_depleted_budget = SE.tier_value_score(
        cheap_tier,
        irreversible=False,
        gated=False,
        destructive=False,
        remaining_budget=0,
        envelope=100,
    )
    assert low_stakes_depleted_budget <= SE.ladder_dearness(cheap_tier)
    assert low_stakes_depleted_budget < high_stakes_full_budget


def test_tier_value_score_zero_envelope_treated_as_unbounded() -> None:
    # envelope <= 0 means "no envelope set" -- budget_fraction defaults to 1.0, never divides by 0.
    score = SE.tier_value_score(
        SE.SPEND_BASELINE,
        irreversible=True,
        gated=True,
        destructive=True,
        remaining_budget=0,
        envelope=0,
    )
    assert score == 1.0


# ---------------------------------------------------------------------------
# Reconcile: no-write guard + commensurable-only deltas + no-data-yet honesty (T12-F4-5)
# ---------------------------------------------------------------------------


def test_reconcile_no_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Set up the fixture data FIRST (record_cost legitimately writes) -- only reconcile() itself
    # is under test for the no-write guarantee.
    store = STORE.Store(root=tmp_path / "store").ensure()
    node = _node("sub-1")
    spec = _outcome_spec(node)
    COSTS.record_cost(
        store,
        "sub-1",
        executor="inline",
        tokens=1000,
        wall_seconds=10,
        operator_touches=2,
        retries=1,
    )

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("reconcile() must never call a ledger-write function")

    monkeypatch.setattr(STORE, "_write_once", _boom)
    monkeypatch.setattr(STORE, "append_ledger", _boom)

    report = SE.reconcile(spec, store)

    assert "status" not in report  # real data present -> not "no data yet"
    row = report["per_subplot"][0]
    assert row["no_data"] is False
    assert row["deltas"]["operator_touches"] == 2.0
    assert row["deltas"]["retries"] == 1.0
    # tokens/wall_seconds render as labeled context, never coerced onto the ordinal axis.
    assert row["context"]["tokens"] == 1000
    assert row["context"]["wall_seconds"] == 10
    assert "deltas" not in row["context"]


def test_reconcile_empty_rollup_renders_no_data_yet(tmp_path: Path) -> None:
    store = STORE.Store(root=tmp_path / "store").ensure()
    spec = _outcome_spec(_node("sub-1"), _node("sub-2"))

    report = SE.reconcile(spec, store)

    assert report["status"] == "no data yet"
    assert all(row["no_data"] for row in report["per_subplot"])
    assert all(row["deltas"] == {} for row in report["per_subplot"] if "deltas" in row)


def test_reconcile_flags_backend_mismatch(tmp_path: Path) -> None:
    store = STORE.Store(root=tmp_path / "store").ensure()
    node = _node("sub-1", backend="team-execution")
    spec = _outcome_spec(node)
    COSTS.record_cost(store, "sub-1", executor="inline")

    report = SE.reconcile(spec, store)
    row = report["per_subplot"][0]
    assert row["context"]["executor"] == "inline"
    assert row["context"]["declared_backend"] == "team-execution"
    assert row["context"]["backend_matches_executor"] is False


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_corrupt_spec_json_returns_exit_code_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#402 post-merge review fix (P3): a corrupt JSON input file must map to the clean
    `SPEND ESTIMATE ERROR`/exit-2 path, never an uncaught `JSONDecodeError` traceback.
    """
    corrupt = tmp_path / "spec-corrupt.json"
    corrupt.write_text("this is not json{", encoding="utf-8")
    assert SE.main(["estimate", "--spec", str(corrupt)]) == 2
    assert "SPEND ESTIMATE ERROR" in capsys.readouterr().err


def test_cli_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        SE.main(["--help"])
    assert exc_info.value.code == 0
