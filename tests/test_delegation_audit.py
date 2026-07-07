"""Tests for the fleet-core engine-parametrized delegation auditor (#384, U1)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
MODULE_PATH = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "delegation_audit.py"
AGY_DELEGATE_PATH = ROOT / "plugins" / "agy" / "scripts" / "agy_delegate.py"
FIXTURES = ROOT / "tests" / "fixtures" / "delegation"


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def delegation_audit() -> ModuleType:
    return _load_module(MODULE_PATH, "delegation_audit")


@pytest.fixture
def agy_delegate() -> ModuleType:
    return _load_module(AGY_DELEGATE_PATH, "agy_delegate")


# --- classify() happy path -----------------------------------------------------------------


def test_classify_agy_real(delegation_audit: ModuleType) -> None:
    result = delegation_audit.classify(FIXTURES / "real-agy.jsonl", "agy")
    assert result.classification == "real"
    assert result.command_seen is True
    assert result.claude_file_tool_seen is False
    assert result.evidence


def test_classify_codex_real(delegation_audit: ModuleType) -> None:
    result = delegation_audit.classify(FIXTURES / "real-codex.jsonl", "codex")
    assert result.classification == "real"
    assert result.command_seen is True
    assert result.claude_file_tool_seen is False


def test_classify_agy_fallback_suspected(delegation_audit: ModuleType) -> None:
    result = delegation_audit.classify(FIXTURES / "claude-clone-agy.jsonl", "agy")
    assert result.classification == "fallback_suspected"
    assert result.command_seen is False
    assert result.claude_file_tool_seen is True


def test_classify_codex_fallback_suspected(delegation_audit: ModuleType) -> None:
    result = delegation_audit.classify(FIXTURES / "claude-clone-codex.jsonl", "codex")
    assert result.classification == "fallback_suspected"
    assert result.claude_file_tool_seen is True


# --- classify() edge cases -----------------------------------------------------------------


def test_classify_empty_transcript(delegation_audit: ModuleType) -> None:
    result = delegation_audit.classify(FIXTURES / "empty.jsonl", "agy")
    assert result.classification == "fallback_suspected"
    assert result.command_seen is False
    assert result.claude_file_tool_seen is False
    assert result.evidence == []


def test_classify_over_byte_cap_uses_capped_prefix(delegation_audit: ModuleType, tmp_path: Path) -> None:
    big = tmp_path / "big.jsonl"
    line = json.dumps({"tool_name": "Read"}) + "\n"
    # Write well past a tiny cap to prove capped streaming doesn't error.
    with big.open("w", encoding="utf-8") as fh:
        for _ in range(200):
            fh.write(line)
        fh.write(
            json.dumps(
                {
                    "type": "tool_use",
                    "tool_name": "Bash",
                    "arguments": {"command": "python3 plugins/agy/scripts/agy_delegate.py --launch-agy"},
                }
            )
            + "\n"
        )

    # Cap smaller than the file: classification must run to completion without raising, and
    # since the real command only shows up after the cap, it must not be seen.
    tiny_cap = len(line) * 5
    lines = list(delegation_audit._iter_capped_lines(big, byte_cap=tiny_cap))  # noqa: SLF001
    assert lines  # streamed without error
    total_bytes = sum(len(entry.encode("utf-8")) for entry in lines)
    assert total_bytes <= tiny_cap + len(line)


def test_classify_unknown_engine_raises(delegation_audit: ModuleType) -> None:
    with pytest.raises(delegation_audit.UnknownEngineError):
        delegation_audit.classify(FIXTURES / "real-agy.jsonl", "not-a-real-engine")


# --- corroborate() -----------------------------------------------------------------


def test_corroborate_missing_bundle_root_is_unproven(delegation_audit: ModuleType, tmp_path: Path) -> None:
    result = delegation_audit.corroborate("agy", since_ts=None, root=tmp_path)
    assert result.launched is False
    assert result.receipt_present is False
    assert result.problems


def test_corroborate_agy_launched_true_embedded_receipt(delegation_audit: ModuleType, tmp_path: Path) -> None:
    run_dir = tmp_path / ".claude" / "agy" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "result.json").write_text(
        json.dumps({"status": "success", "agy_launched": True, "receipt": {"schema": "bridge_receipt.v1"}}),
        encoding="utf-8",
    )
    result = delegation_audit.corroborate("agy", since_ts=None, root=tmp_path)
    assert result.launched is True
    assert result.receipt_present is True
    assert result.statuses == ["success"]


def test_corroborate_codex_launched_false(delegation_audit: ModuleType, tmp_path: Path) -> None:
    run_dir = tmp_path / ".claude" / "codex" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "result.json").write_text(
        json.dumps({"status": "codex_unavailable", "codex_launched": False}),
        encoding="utf-8",
    )
    result = delegation_audit.corroborate("codex", since_ts=None, root=tmp_path)
    assert result.launched is False
    assert result.receipt_present is False


def test_corroborate_corrupt_result_json_never_raises(delegation_audit: ModuleType, tmp_path: Path) -> None:
    run_dir = tmp_path / ".claude" / "agy" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "result.json").write_text("{not valid json", encoding="utf-8")
    result = delegation_audit.corroborate("agy", since_ts=None, root=tmp_path)
    assert result.launched is False
    assert result.problems


def test_corroborate_missing_result_json_never_raises(delegation_audit: ModuleType, tmp_path: Path) -> None:
    run_dir = tmp_path / ".claude" / "agy" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    result = delegation_audit.corroborate("agy", since_ts=None, root=tmp_path)
    assert result.launched is False
    assert result.problems


# --- reconcile() -----------------------------------------------------------------


def test_reconcile_real_agrees(delegation_audit: ModuleType) -> None:
    classification = delegation_audit.classify(FIXTURES / "real-agy.jsonl", "agy")
    corroboration = delegation_audit.BundleCorroboration(
        engine="agy", launched=True, receipt_present=True, statuses=["success"]
    )
    assert delegation_audit.reconcile(classification, corroboration, "ok") == "real"


def test_reconcile_fallback_suspected_short_circuits(delegation_audit: ModuleType) -> None:
    classification = delegation_audit.classify(FIXTURES / "claude-clone-agy.jsonl", "agy")
    corroboration = delegation_audit.BundleCorroboration(engine="agy", launched=False, receipt_present=False)
    assert delegation_audit.reconcile(classification, corroboration, "ok") == "fallback_suspected"


def test_reconcile_divergence_flagged_delegation_integrity(delegation_audit: ModuleType) -> None:
    classification = delegation_audit.classify(FIXTURES / "real-agy.jsonl", "agy")
    corroboration = delegation_audit.BundleCorroboration(engine="agy", launched=False, receipt_present=False)
    assert delegation_audit.reconcile(classification, corroboration, "ok") == "delegation_integrity"


# --- R7 fixture-parity: every fixture classifies identically via both auditors ---------------


@pytest.mark.parametrize(
    "fixture_name",
    ["real-agy.jsonl", "claude-clone-agy.jsonl", "empty.jsonl"],
)
def test_fixture_parity_with_agy_delegate(
    delegation_audit: ModuleType, agy_delegate: ModuleType, fixture_name: str
) -> None:
    path = FIXTURES / fixture_name
    fleet_result = delegation_audit.classify(path, "agy")
    agy_result = agy_delegate.classify_transcript(path)

    assert fleet_result.classification == agy_result.classification
    assert fleet_result.command_seen == agy_result.agy_command_seen
    assert fleet_result.claude_file_tool_seen == agy_result.claude_file_tool_seen


def test_fixture_parity_original_agy_fixtures(delegation_audit: ModuleType, agy_delegate: ModuleType) -> None:
    original_fixtures = ROOT / "tests" / "fixtures" / "agy" / "transcripts"
    for path in sorted(original_fixtures.glob("*.jsonl")):
        fleet_result = delegation_audit.classify(path, "agy")
        agy_result = agy_delegate.classify_transcript(path)
        assert fleet_result.classification == agy_result.classification, path
        assert fleet_result.command_seen == agy_result.agy_command_seen, path
        assert fleet_result.claude_file_tool_seen == agy_result.claude_file_tool_seen, path
