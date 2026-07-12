"""Tests for the /delegation-audit CLI query surface (#396, U5)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_PATH = ROOT / "plugins" / "saga" / "scripts" / "delegation_audit_query.py"
AUDIT_STORE_PATH = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "audit_store.py"


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def audit_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    return _load_module(AUDIT_STORE_PATH, "audit_store")


def _valid_receipt(run_id: str) -> dict[str, object]:
    return {
        "schema": "bridge_receipt.v1",
        "engine_id": "agy",
        "variant": "flash",
        "transport": "cli",
        "wall_time_s": 1.0,
        "bytes_produced": 10,
        "runner": {"pid": 1, "argv": ["agy"], "exit_code": 0},
        "run_id": run_id,
    }


def test_cli_reports_no_ops_and_clean_runs(audit_store: ModuleType, tmp_path: Path) -> None:
    store = audit_store.Store.for_root(tmp_path / "audit-store")
    audit_store.mirror_manifest(store, "real-run", {"disposition": "ran-as-requested"})
    audit_store.mirror_receipt(store, "real-run", _valid_receipt("real-run"))
    audit_store.mirror_manifest(store, "fallback-run", {"disposition": "ran-as-requested"})

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--audit-store",
            str(tmp_path / "audit-store"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["run_count"] == 2
    assert report["flagged_count"] == 1
    assert {entry["run_id"] for entry in report["flagged"]} == {"fallback-run"}
    assert {entry["run_id"] for entry in report["clean"]} == {"real-run"}


def test_cli_handles_empty_store(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--audit-store",
            str(tmp_path / "empty-audit-store"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["run_count"] == 0
    assert report["flagged_count"] == 0
    assert report["flagged"] == []
    assert report["clean"] == []


def test_cli_run_id_filter_scopes_to_named_runs(audit_store: ModuleType, tmp_path: Path) -> None:
    store = audit_store.Store.for_root(tmp_path / "audit-store")
    audit_store.mirror_manifest(store, "run-a", {"disposition": "ran-as-requested"})
    audit_store.mirror_manifest(store, "run-b", {"disposition": "fell-back-to-claude"})

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--audit-store",
            str(tmp_path / "audit-store"),
            "--run-id",
            "run-b",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["run_count"] == 1
