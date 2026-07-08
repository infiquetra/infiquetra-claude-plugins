"""Tests for the empty-delivery HALT check at the delegated-unit boundary (U5)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "plugins" / "saga" / "scripts" / "check_empty_delivery.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_empty_delivery", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_empty_delivery"] = module
    spec.loader.exec_module(module)
    return module


M = _load()


def test_halts_on_empty_delivery() -> None:
    verdict = M.check_empty_delivery([], claims_delivery=True)
    assert verdict.halt is True
    assert verdict.changed_path_count == 0
    assert verdict.claims_delivery is True
    assert "empty delivery" in verdict.reason


def test_autocommits_on_delivery() -> None:
    # "autocommits" selector: asserts the PROCEED verdict authorizing the
    # documented chaperone commit step. The helper itself never commits.
    verdict = M.check_empty_delivery(["plugins/saga/scripts/foo.py"], claims_delivery=True)
    assert verdict.halt is False
    assert verdict.changed_path_count == 1
    assert verdict.claims_delivery is True


def test_no_delivery_claimed_with_zero_paths_is_ok() -> None:
    verdict = M.check_empty_delivery([], claims_delivery=False)
    assert verdict.halt is False
    assert verdict.claims_delivery is False
    assert "no delivery claimed" in verdict.reason.lower() or "read-only" in verdict.reason.lower()


def test_no_delivery_claimed_with_paths_is_also_ok() -> None:
    verdict = M.check_empty_delivery(["some/file.py"], claims_delivery=False)
    assert verdict.halt is False


def test_verdict_to_dict_roundtrip() -> None:
    verdict = M.check_empty_delivery([], claims_delivery=True)
    d = verdict.to_dict()
    assert d == {
        "halt": True,
        "reason": verdict.reason,
        "changed_path_count": 0,
        "claims_delivery": True,
    }


def test_parse_porcelain_z_splits_nul_separated_records() -> None:
    raw = b" M foo.py\0?? bar.py\0"
    paths = M._parse_porcelain_z(raw)
    assert paths == [" M foo.py", "?? bar.py"]


def test_parse_porcelain_z_empty_bytes_is_no_paths() -> None:
    assert M._parse_porcelain_z(b"") == []


def test_git_status_changed_paths_reports_real_changes(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "new_file.txt").write_text("hello\n", encoding="utf-8")
    paths = M.git_status_changed_paths(cwd=str(tmp_path))
    assert any("new_file.txt" in p for p in paths)


def test_cli_outside_git_repo_is_clean_error(tmp_path: Path) -> None:
    # A directory with no .git anywhere above it in the tree it's isolated to.
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--claims-delivery", "--cwd", str(tmp_path)],
        cwd="/",
        capture_output=True,
        text=True,
    )
    # Should exit non-zero with a clean JSON error, never an uncaught traceback.
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "error" in result.stderr


def test_cli_claims_delivery_zero_paths_exits_nonzero(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--claims-delivery", "--cwd", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert '"halt": true' in result.stdout


def test_cli_delivery_with_changes_exits_zero(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "changed.txt").write_text("x\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--claims-delivery", "--cwd", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert '"halt": false' in result.stdout
