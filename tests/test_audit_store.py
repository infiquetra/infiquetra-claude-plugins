"""Tests for the fleet-core durable delegation audit store (#396, U1)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
MODULE_PATH = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "audit_store.py"


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
    # Never resolve DEFAULT_AUDIT_STORE_ROOT against the real developer home directory (R5/KTD6).
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    return _load_module(MODULE_PATH, "audit_store")


def _receipt(run_id: str = "run-1") -> dict[str, object]:
    return {
        "schema": "bridge_receipt.v1",
        "engine_id": "agy",
        "variant": "flash",
        "transport": "cli",
        "wall_time_s": 1.5,
        "bytes_produced": 42,
        "runner": {"pid": 123, "argv": ["agy"], "exit_code": 0},
        "run_id": run_id,
    }


def test_mirror_receipt_resolvable_by_run_id_alone(audit_store: ModuleType, tmp_path: Path) -> None:
    store = audit_store.Store.for_root(tmp_path / "audit-store")
    audit_store.mirror_receipt(store, "run-1", _receipt("run-1"))

    resolved = audit_store.resolve_receipt(store, "run-1")

    assert resolved is not None
    assert resolved["run_id"] == "run-1"


def test_mirror_result_resolvable_when_no_receipt(audit_store: ModuleType, tmp_path: Path) -> None:
    store = audit_store.Store.for_root(tmp_path / "audit-store")
    result_payload = {"status": "success", "agy_launched": False, "run_id": "run-2"}

    audit_store.mirror_result(store, "run-2", result_payload)

    assert audit_store.resolve_result(store, "run-2") == result_payload
    assert audit_store.resolve_receipt(store, "run-2") is None


def test_mirror_manifest_resolvable_by_id(audit_store: ModuleType, tmp_path: Path) -> None:
    store = audit_store.Store.for_root(tmp_path / "audit-store")
    manifest = {"execution_id": "exec-1", "disposition": "ran-as-requested"}

    audit_store.mirror_manifest(store, "exec-1", manifest)

    assert audit_store.resolve_manifest(store, "exec-1") == manifest


def test_manifest_mirror_overwrites_in_place(audit_store: ModuleType, tmp_path: Path) -> None:
    store = audit_store.Store.for_root(tmp_path / "audit-store")
    audit_store.mirror_manifest(store, "exec-1", {"disposition": "ran-as-requested"})

    audit_store.mirror_manifest(store, "exec-1", {"disposition": "rejected-offload"})

    assert audit_store.resolve_manifest(store, "exec-1") == {"disposition": "rejected-offload"}


def test_default_root_resolves_under_home_dot_claude_delegation_audit(
    audit_store: ModuleType,
) -> None:
    store = audit_store.Store.for_root(None)

    assert store.root == (Path.home() / ".claude" / "delegation-audit").resolve()


def test_run_id_path_traversal_rejected(audit_store: ModuleType, tmp_path: Path) -> None:
    store = audit_store.Store.for_root(tmp_path / "audit-store")

    with pytest.raises(audit_store.AuditStoreError):
        audit_store.mirror_receipt(store, "../../etc", _receipt())


def test_list_runs_reflects_every_mirrored_run(audit_store: ModuleType, tmp_path: Path) -> None:
    store = audit_store.Store.for_root(tmp_path / "audit-store")
    audit_store.mirror_result(store, "run-a", {"status": "success"})
    audit_store.mirror_manifest(store, "run-b", {"disposition": "ran-as-requested"})

    assert audit_store.list_runs(store) == ["run-a", "run-b"]


def test_list_runs_empty_store_returns_empty_list(audit_store: ModuleType, tmp_path: Path) -> None:
    store = audit_store.Store.for_root(tmp_path / "audit-store")

    assert audit_store.list_runs(store) == []


def test_resolve_receipt_missing_run_returns_none(audit_store: ModuleType, tmp_path: Path) -> None:
    store = audit_store.Store.for_root(tmp_path / "audit-store")

    assert audit_store.resolve_receipt(store, "never-existed") is None


def test_resolve_corrupt_json_returns_none_never_raises(
    audit_store: ModuleType, tmp_path: Path
) -> None:
    store = audit_store.Store.for_root(tmp_path / "audit-store")
    path = store.receipt_path("run-corrupt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    assert audit_store.resolve_receipt(store, "run-corrupt") is None


def test_write_once_draft_then_resolve(audit_store: ModuleType, tmp_path: Path) -> None:
    store = audit_store.Store.for_root(tmp_path / "audit-store")

    audit_store.write_once_draft(store, "run-1", "--- a/foo\n+++ b/foo\n")

    assert audit_store.resolve_draft(store, "run-1") == "--- a/foo\n+++ b/foo\n"


def test_resolve_draft_missing_returns_none(audit_store: ModuleType, tmp_path: Path) -> None:
    store = audit_store.Store.for_root(tmp_path / "audit-store")

    assert audit_store.resolve_draft(store, "never-existed") is None
