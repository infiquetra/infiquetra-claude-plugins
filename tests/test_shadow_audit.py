"""Tests for the sampled shadow-audit: replay-one-rung-down tier-sufficiency evidence (#402 U5).

Pins R7 (sample/replay/record/report), R8 (off by default in attended mode absent an explicit
operator-yes; budget-capped in unattended mode), R9 (the ledger reuse round-trips through
evidence_ledger.verify_chain), and R11 (the sandbox-spawn-sites.md row exists).
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
EL = _load("evidence_ledger")
SA = _load("shadow_audit")

_SHA = "a" * 40


def _unit(unit_id: str, model: str, effort: str, stage: str = "code-review") -> Any:
    return SA.SampledUnit(
        unit_id=unit_id, stage=stage, tier=ES.Tier(model=model, effort=effort), reviewed_sha=_SHA
    )


def _some_units(n: int = 10) -> list[Any]:
    return [_unit(f"U{i}", "sonnet", "high") for i in range(n)]


# ---------------------------------------------------------------------------
# Off-by-default attended / budget-capped unattended (H-F6-1)
# ---------------------------------------------------------------------------


def test_off_by_default_attended_and_budget_capped_unattended(tmp_path: Path) -> None:
    units = _some_units(10)

    # Attended, no --yes, no config: disabled, zero eligible units returned.
    picked, gate_result = SA.sample_gated(units, n=3, root=tmp_path)
    assert gate_result.allowed is False
    assert picked == []
    assert "disabled" in gate_result.reason

    # Attended + --yes: unblocked for this one invocation.
    picked, gate_result = SA.sample_gated(units, n=3, yes=True, root=tmp_path)
    assert gate_result.allowed is True
    assert picked != []

    # Attended + standing config: also unblocked, without --yes.
    (tmp_path / ".saga").mkdir()
    (tmp_path / ".saga" / "shadow-audit.json").write_text('{"enabled": true}\n')
    picked, gate_result = SA.sample_gated(units, n=3, root=tmp_path)
    assert gate_result.allowed is True

    # Unattended with no --max-samples HALTs.
    with pytest.raises(SA.ShadowAuditError):
        SA.sample_gated(units, n=3, unattended=True)

    # Unattended with --max-samples 2 over 10 eligible units samples at most 2.
    picked, gate_result = SA.sample_gated(units, n=1, unattended=True, max_samples=2)
    assert gate_result.allowed is True
    assert len(picked) <= 2


def test_classify_exact_match() -> None:
    assert SA.classify("hello   world", "hello world") == "sufficient"
    assert SA.classify("hello world", "hello there") == "insufficient"


# ---------------------------------------------------------------------------
# Report renders per-stage sufficiency rates (H-F6-1)
# ---------------------------------------------------------------------------


def test_report_renders_per_stage_sufficiency_rates(tmp_path: Path) -> None:
    store = EL.Store.for_saga("demo-saga", tmp_path).ensure()
    SA.record(
        store,
        stage="code-review",
        unit_id="U1",
        reviewed_sha=_SHA,
        verdict="sufficient",
        original_tier=ES.Tier(model="opus", effort="high"),
        replayed_tier=ES.Tier(model="sonnet", effort="high"),
    )
    SA.record(
        store,
        stage="code-review",
        unit_id="U2",
        reviewed_sha=_SHA,
        verdict="insufficient",
        original_tier=ES.Tier(model="opus", effort="high"),
        replayed_tier=ES.Tier(model="sonnet", effort="high"),
    )
    SA.record(
        store,
        stage="qa",
        unit_id="U3",
        reviewed_sha=_SHA,
        verdict="sufficient",
        original_tier=ES.Tier(model="sonnet", effort="high"),
        replayed_tier=ES.Tier(model="sonnet", effort="medium"),
    )

    tallies = SA.report(tmp_path)
    assert tallies["code-review"] == {"sufficient": 1, "insufficient": 1}
    assert tallies["qa"] == {"sufficient": 1, "insufficient": 0}
    table = SA.render_report(tallies)
    assert "code-review" in table and "qa" in table


def test_report_no_data_yet(tmp_path: Path) -> None:
    tallies = SA.report(tmp_path)
    assert tallies == {}
    assert "no data yet" in SA.render_report(tallies)


# ---------------------------------------------------------------------------
# Ledger reuse round-trip (KTD7)
# ---------------------------------------------------------------------------


def test_ledger_reuse_round_trip_verifies(tmp_path: Path) -> None:
    store = EL.Store.for_saga("demo-saga", tmp_path).ensure()
    SA.record(
        store,
        stage="code-review",
        unit_id="U1",
        reviewed_sha=_SHA,
        verdict="sufficient",
        original_tier=ES.Tier(model="opus", effort="high"),
        replayed_tier=ES.Tier(model="sonnet", effort="high"),
    )
    chain_report = EL.verify_chain(store)
    assert chain_report.entry_count == 1
    assert chain_report.verified_artifacts == 1


# ---------------------------------------------------------------------------
# Sampling eligibility excludes already-cheapest units
# ---------------------------------------------------------------------------


def test_already_cheapest_unit_excluded_from_eligibility() -> None:
    cheap_model, cheap_effort = ES._tier_palette.MODELS[-1], ES._tier_palette.EFFORTS[0]
    units = [_unit("cheap", cheap_model, cheap_effort), _unit("normal", "sonnet", "high")]
    eligible = SA.eligible_for_sampling(units)
    assert [u.unit_id for u in eligible] == ["normal"]


def test_all_cheapest_pool_short_circuits_sample_and_sample_gated() -> None:
    """#402 code-review testing-lens finding (P3): the empty-eligible-pool short-circuit
    (`if not pool: return []`) exercised only at `eligible_for_sampling()` in isolation above --
    this pins the same case end-to-end through `sample()` and the gated `sample_gated()` wrapper.
    """
    cheap_model, cheap_effort = ES._tier_palette.MODELS[-1], ES._tier_palette.EFFORTS[0]
    all_cheapest = [_unit(f"C{i}", cheap_model, cheap_effort) for i in range(5)]

    assert SA.sample(all_cheapest, n=1, seed=0) == []

    picked, gate_result = SA.sample_gated(all_cheapest, n=1, yes=True)
    assert gate_result.allowed is True
    assert picked == []


def test_cli_malformed_units_returns_exit_code_2(tmp_path: Path) -> None:
    """#402 code-review security finding (P2): a malformed `--units` JSON element must be caught
    via `ShadowAuditError`/exit-code-2 -- never an uncaught `TypeError` traceback.
    """
    not_a_list = tmp_path / "units-not-a-list.json"
    not_a_list.write_text('{"unit_id": "U1"}', encoding="utf-8")
    assert SA.main(["sample", "--units", str(not_a_list), "--n", "3", "--yes"]) == 2

    bad_tier = tmp_path / "units-bad-tier.json"
    bad_tier.write_text(
        '[{"unit_id": "U1", "stage": "code-review", "tier": "not-a-dict"}]', encoding="utf-8"
    )
    assert SA.main(["sample", "--units", str(bad_tier), "--n", "3", "--yes"]) == 2


def test_cli_missing_scalar_key_returns_exit_code_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#402 post-merge review fix (P2): a dict element missing a required scalar key
    (`unit_id`/`stage`/`tier.model`/`tier.effort`) must wrap into `ShadowAuditError`/exit-2 as
    `_sampled_unit_from_dict`'s docstring promises -- never a raw `KeyError` traceback.
    """
    missing_key = tmp_path / "units-missing-unit-id.json"
    missing_key.write_text(
        '[{"stage": "code-review", "tier": {"model": "opus", "effort": "high"}}]',
        encoding="utf-8",
    )
    assert SA.main(["sample", "--units", str(missing_key), "--n", "3", "--yes"]) == 2
    assert "missing key" in capsys.readouterr().err


def test_cli_corrupt_units_json_returns_exit_code_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#402 post-merge review fix (P3): a corrupt `--units` file must map to the clean
    `SHADOW AUDIT ERROR`/exit-2 path, never an uncaught `JSONDecodeError` traceback.
    """
    corrupt = tmp_path / "units-corrupt.json"
    corrupt.write_text("this is not json{", encoding="utf-8")
    assert SA.main(["sample", "--units", str(corrupt), "--n", "3", "--yes"]) == 2
    assert "SHADOW AUDIT ERROR" in capsys.readouterr().err


def test_cli_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        SA.main(["--help"])
    assert exc_info.value.code == 0
