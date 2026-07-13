"""Tests for the chaperone-dispatch write-once pre-fix draft snapshot (#396, U6).

The chaperone-dispatch protocol (`plugins/team-execution/skills/team-execution/references/
external-engine-workers.md` §5 step 1 "Verify") has no executable `chaperone.py` of its own — the
chaperone is a live Claude agent following that documented protocol, calling straight into
`fleet_commons/audit_store.py`'s `write_once_draft`. These tests exercise that exact primitive
against the documented contract: capture the engine's raw pre-fix output before any fix is applied,
then prove the stored snapshot recovers the same fix-delta the chaperone itself would record.
"""

from __future__ import annotations

import difflib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
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
    # Never resolve DEFAULT_AUDIT_STORE_ROOT against the real developer home directory (R5/KTD6).
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    return _load_module(AUDIT_STORE_PATH, "audit_store")


_RAW_ENGINE_OUTPUT = (
    "--- a/example.py\n"
    "+++ b/example.py\n"
    "@@ -1,2 +1,2 @@\n"
    "-def greet():\n"
    "-    return 'hi'\n"
    "+def greet():\n"
    "+    return 'hii'\n"
)

# The chaperone's own fix corrects a typo the raw engine output introduced ('hii' -> 'hi there').
_CHAPERONE_APPLIED_FIX = (
    "--- a/example.py\n"
    "+++ b/example.py\n"
    "@@ -1,2 +1,2 @@\n"
    "-def greet():\n"
    "-    return 'hi'\n"
    "+def greet():\n"
    "+    return 'hi there'\n"
)


def test_draft_snapshot_matches_fix_delta(audit_store: ModuleType, tmp_path: Path) -> None:
    """The write-once snapshot, diffed against the final applied fix, equals the chaperone's own
    recorded fix-delta (the literal DoD acceptance check for issue #396)."""
    store = audit_store.Store.for_root(tmp_path / "audit-store")

    # Step 1 (Verify): the chaperone snapshots the raw engine output write-once, before any fix.
    audit_store.write_once_draft(store, "exec-1", _RAW_ENGINE_OUTPUT)

    # The chaperone's own recorded fix-delta (what it would independently compute and record when
    # it applies its fix), computed directly against the raw content — not through the snapshot.
    chaperone_fix_delta = "".join(
        difflib.unified_diff(
            _RAW_ENGINE_OUTPUT.splitlines(keepends=True),
            _CHAPERONE_APPLIED_FIX.splitlines(keepends=True),
            fromfile="raw",
            tofile="fixed",
        )
    )

    # Diffing the stored snapshot against the same final content reproduces that identical delta.
    stored_raw = audit_store.resolve_draft(store, "exec-1")
    assert stored_raw is not None
    snapshot_delta = "".join(
        difflib.unified_diff(
            stored_raw.splitlines(keepends=True),
            _CHAPERONE_APPLIED_FIX.splitlines(keepends=True),
            fromfile="raw",
            tofile="fixed",
        )
    )

    assert snapshot_delta == chaperone_fix_delta


def test_draft_snapshot_keyed_by_execution_id_not_run_id(
    audit_store: ModuleType, tmp_path: Path
) -> None:
    """The chaperone-dispatch protocol keys by `execution_id`; agy keys by `run_id` — one identity
    namespace (KTD8), so both resolve through the same `run_id` parameter name."""
    store = audit_store.Store.for_root(tmp_path / "audit-store")

    audit_store.write_once_draft(store, "worker-1-unit-3", _RAW_ENGINE_OUTPUT)

    assert audit_store.resolve_draft(store, "worker-1-unit-3") == _RAW_ENGINE_OUTPUT
