"""Tests for #366 U4: the effort-escrow ledger.

Covers the acceptance criteria
`uv run pytest tests/test_effort_ledger.py -k refund` and `-k escalation_before_execution`
plus the absent-policy safe default and the actual-vs-planned round-trip.
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
EFFORT_LEDGER_SCRIPT = SCRIPT_DIR / "effort_ledger.py"


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


EL = _load("effort_ledger", EFFORT_LEDGER_SCRIPT)


def _ledger() -> Any:
    return EL.EffortLedger(policy=EL.EffortPolicy())


def test_refund_unused_allocation() -> None:
    """A unit that under-spends its declared allocation refunds the unused remainder to the pool."""
    ledger = _ledger()
    ledger.allocate("U1", 10)
    refund = ledger.record_actual("U1", 6)
    assert refund == 4
    assert ledger.pool == 4
    assert ledger.actuals["U1"] == 6


def test_refund_none_when_over_or_exact() -> None:
    ledger = _ledger()
    ledger.allocate("U1", 10)
    assert ledger.record_actual("U1", 10) == 0  # exact spend -> no refund
    ledger.allocate("U2", 5)
    assert ledger.record_actual("U2", 8) == 0  # over-spend -> no negative "refund"
    assert ledger.pool == 0


def test_refund_disabled_by_policy() -> None:
    ledger = EL.EffortLedger(policy=EL.EffortPolicy(refund_unused=False))
    ledger.allocate("U1", 10)
    assert ledger.record_actual("U1", 6) == 0
    assert ledger.pool == 0


def test_record_actual_for_unallocated_unit_raises() -> None:
    ledger = _ledger()
    with pytest.raises(EL.EffortLedgerError, match="un-allocated"):
        ledger.record_actual("U9", 3)


def test_escalation_before_execution() -> None:
    """A risky unit that would exceed its allocation raises an escalation-request BEFORE it runs."""
    ledger = _ledger()
    ledger.allocate("U2", 5)
    request = ledger.request_escalation("U2", 12, reason="risky refactor")
    assert request is not None
    assert request.allocated == 5
    assert request.requested == 12
    # Surfaced ahead of execution: the unit has no recorded actual yet.
    assert "U2" not in ledger.actuals
    assert ledger.escalations == [request]


def test_escalation_within_allocation_is_none() -> None:
    ledger = _ledger()
    ledger.allocate("U1", 10)
    assert ledger.request_escalation("U1", 8) is None
    assert ledger.escalations == []


def test_absent_policy_default(tmp_path: Path) -> None:
    """With no effort-policy.yaml present, the ledger resolves the documented safe default."""
    policy = EL.load_policy(tmp_path / "nonexistent.yaml")
    assert policy.refund_unused is True
    assert policy.surface_escalation_before_execution is True
    assert policy.auto_approve_escalation is False


def test_shipped_policy_matches_safe_default() -> None:
    """The committed effort-policy.yaml parses to the same safe defaults it documents."""
    policy = EL.load_policy(EL.DEFAULT_POLICY_PATH)
    assert policy.refund_unused is True
    assert policy.surface_escalation_before_execution is True
    assert policy.auto_approve_escalation is False


def test_ledger_actual_vs_planned_roundtrip(tmp_path: Path) -> None:
    """save/load conserves allocations, actuals, pool, and escalations."""
    ledger = _ledger()
    ledger.allocate("U1", 10)
    ledger.allocate("U2", 5)
    ledger.record_actual("U1", 6)  # refunds 4 to pool
    ledger.request_escalation("U2", 12, reason="needs more")
    path = tmp_path / "ledger.json"
    ledger.save(path)

    restored = EL.EffortLedger.load(path)
    assert restored.to_dict() == ledger.to_dict()
    assert restored.pool == 4
    assert restored.allocations == {"U1": 10, "U2": 5}
    assert restored.actuals == {"U1": 6}
    assert len(restored.escalations) == 1


def test_cli_allocate_record_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The CLI surface /work invokes: allocate -> record -> report persists across calls."""
    ledger_path = tmp_path / "ledger.json"
    assert (
        EL.main(["--ledger", str(ledger_path), "allocate", "--unit", "U1", "--amount", "10"]) == 0
    )
    assert EL.main(["--ledger", str(ledger_path), "record", "--unit", "U1", "--actual", "6"]) == 0
    capsys.readouterr()  # drain
    assert EL.main(["--ledger", str(ledger_path), "report"]) == 0
    out = capsys.readouterr().out
    assert '"pool": 4' in out
