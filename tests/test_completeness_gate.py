"""Unit tests for the completeness-gate oracle (U1)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "plugins" / "saga" / "scripts" / "completeness_gate.py"


def _load():
    spec = importlib.util.spec_from_file_location("completeness_gate", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["completeness_gate"] = module
    spec.loader.exec_module(module)
    return module


def test_missing_output_null() -> None:
    """Test that null-when-expected trips missing-output."""
    cg = _load()
    contract = cg.Contract(expects_output=True)
    fail = cg.classify(None, contract=contract, unit_id="U1")
    assert fail is not None
    assert fail.failure_class == cg.FailureClass.MISSING_OUTPUT
    assert fail.unit_id == "U1"


def test_malformed_output() -> None:
    """Test that a structurally truncated output trips malformed-output."""
    cg = _load()
    contract = cg.Contract(expects_output=True)
    fail = cg.classify('{"key": "value', contract=contract, unit_id="U2")
    assert fail is not None
    assert fail.failure_class == cg.FailureClass.MALFORMED_OUTPUT
    assert fail.unit_id == "U2"


def test_missing_output_fanout() -> None:
    """Test that a fan-out shortfall trips missing-output."""
    cg = _load()
    contract = cg.Contract(expects_output=True, target_count=12)
    # 9 elements instead of 12
    fail = cg.classify([1, 2, 3, 4, 5, 6, 7, 8, 9], contract=contract, unit_id="U3")
    assert fail is not None
    assert fail.failure_class == cg.FailureClass.MISSING_OUTPUT
    assert fail.unit_id == "U3"
    assert "shortfall" in fail.message.lower()
    assert "3" in fail.message


def test_manifest_missing_key() -> None:
    """Test that a missing required key trips missing-output, naming the key."""
    cg = _load()
    contract = cg.Contract(
        expects_output=True, returns=["migration_sql", "rollback_sql", "test_file"]
    )
    res = {"migration_sql": "SELECT 1;", "test_file": "test.py"}
    fail = cg.classify(res, contract=contract, unit_id="U4")
    assert fail is not None
    assert fail.failure_class == cg.FailureClass.MISSING_OUTPUT
    assert fail.unit_id == "U4"
    assert "rollback_sql" in fail.message


def test_legitimate_empty() -> None:
    """Test that a legitimately-empty no-contract leaf does not trip."""
    cg = _load()
    contract = cg.Contract(expects_output=False)
    fail = cg.classify(None, contract=contract, unit_id="U5")
    assert fail is None


def test_all_required_keys_present() -> None:
    """Test that all required keys present passes."""
    cg = _load()
    contract = cg.Contract(
        expects_output=True, returns=["migration_sql", "rollback_sql", "test_file"]
    )
    res = {"migration_sql": "SELECT 1;", "rollback_sql": "SELECT 2;", "test_file": "test.py"}
    fail = cg.classify(res, contract=contract, unit_id="U6")
    assert fail is None


def test_enum_extensibility_dispatch() -> None:
    """Test that a new enum member does not break dispatch."""
    cg = _load()
    # Simulating a dispatcher that maps failure classes to handlers
    dispatcher = {
        cg.FailureClass.MISSING_OUTPUT: lambda x: f"missing: {x}",
        cg.FailureClass.MALFORMED_OUTPUT: lambda x: f"malformed: {x}",
        cg.FailureClass.VERIFIER_DISAGREEMENT: lambda x: f"verifier: {x}",
    }
    # Future/extensible class string should fall back gracefully
    new_class = "tool-denial"
    handler = dispatcher.get(new_class, lambda x: f"default: {x}")
    result = handler("some detail")
    assert result == "default: some detail"


def test_self_test_cli() -> None:
    """Test the --self-test CLI command runs successfully."""
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"], capture_output=True, text=True, check=True
    )
    assert res.returncode == 0
    assert "caught" in res.stdout
    assert "missing-output" in res.stdout
    assert "malformed-output" in res.stdout
