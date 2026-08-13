"""Tests for the orchestrate register (U2): the whole state model for a herdr-driven run and the
Claude<->Codex handoff seam (R12).

Each of the seven scenarios from `.orchestrate/briefs/U2.md` gets its own test, named for the
scenario, asserting exactly what that scenario states — not something weaker that would still
report green.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "plugins" / "orchestrate" / "skills" / "orchestrate" / "scripts" / "register.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("orchestrate_register", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["orchestrate_register"] = module
    spec.loader.exec_module(module)
    return module


M = _load()


def _full_row(row_id: str = "child-1", run_id: str = "run-a") -> dict:
    """A row with every documented column populated, for the full-round-trip scenario."""
    return {
        "id": row_id,
        "run_id": run_id,
        "agent": "claude",
        "vendor": "anthropic",
        "model": "claude-sonnet-5",
        "effort": "high",
        "herdr_session": "sess-1",
        "workspace_id": "ws-1",
        "tab_id": "tab-1",
        "pane_id": "pane-1",
        "cwd": "/repo",
        "task": "implement U2",
        "work_shape": "implementation",
        "scope": "plugins/orchestrate/",
        "artifact_path": "plugins/orchestrate/skills/orchestrate/scripts/register.py",
        "predicate": "pytest tests/test_orchestrate_register.py",
        "integration_mode": "patch",
        "destination": "plugins/orchestrate/",
        "phase": "working",
        "expected_state": "working",
        "observed_state": "working",
        "dispatched_at": 1000.0,
        "deadline": None,
        "max_quiet_seconds": 600,
        "last_event_at": 1000.5,
        "tokens_observed": 1234,
        "tokens_reserved": 50000,
    }


# --------------------------------------------------------------------------- 1. fresh init


def test_fresh_register_initialises_with_a_schema_version(tmp_path: Path) -> None:
    # No register.json exists yet — read_register must still produce a document carrying a
    # schema_version, not an error and not a documentless empty dict.
    doc = M.read_register(tmp_path)
    assert doc["schema_version"] == M.SCHEMA_VERSION
    assert doc["rows"] == {}

    # The first real write persists that same schema_version to disk.
    M.upsert_row(tmp_path, "child-1", {"run_id": "run-a"})
    on_disk = json.loads(M.register_path(tmp_path).read_text())
    assert on_disk["schema_version"] == M.SCHEMA_VERSION


# --------------------------------------------------------------------------- 2. full round trip


def test_row_round_trips_every_column(tmp_path: Path) -> None:
    row = _full_row()
    stored = M.upsert_row(tmp_path, "child-1", row)
    assert stored == row

    reread = M.read_rows(tmp_path)["child-1"]
    assert reread == row
    # Every documented column is actually present, not merely a subset that happens to match.
    for column in M.ROW_COLUMNS:
        assert column in reread, f"column {column!r} missing after round trip"


# --------------------------------------------------------------------------- 3. atomic write


def test_atomic_write_leaves_no_partial_file_when_interrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Establish a known-good register first.
    M.upsert_row(tmp_path, "child-1", {"run_id": "run-a", "phase": "planned"})
    before = M.register_path(tmp_path).read_text()

    real_replace = __import__("os").replace

    def _boom(src, dst):  # noqa: ANN001
        if Path(dst) == M.register_path(tmp_path):
            raise OSError("simulated crash mid-write")
        return real_replace(src, dst)

    monkeypatch.setattr(M.os, "replace", _boom)

    with pytest.raises(OSError, match="simulated crash"):
        M.upsert_row(tmp_path, "child-2", {"run_id": "run-a", "phase": "planned"})

    # The live register file is untouched — still exactly the pre-interruption content, never a
    # half-written mixture of old and new.
    assert M.register_path(tmp_path).read_text() == before
    # And no stray full-length file was left at the real path under a different name that a
    # careless reader might mistake for the register.
    leftover_final_names = [
        p for p in tmp_path.glob("**/register.json*") if p != M.register_path(tmp_path)
    ]
    # Only the lock file (created by the locking context) and this call's now-orphaned temp file
    # (cleaned up by the finally-unlink) may remain; the *contents* of register.json itself must
    # never have moved.
    assert all(p.suffix in (".lock", ".tmp") or ".tmp" in p.name for p in leftover_final_names)


# --------------------------------------------------------------------------- 4. nested unknown key


def test_unknown_key_nested_in_child_row_is_preserved_on_write(tmp_path: Path) -> None:
    # A row as Codex might write it, carrying a column Claude's register.py has never heard of.
    codex_row = {
        "run_id": "run-a",
        "phase": "working",
        "codex_execution_class": "review-max",  # unknown to this module
    }
    M.upsert_row(tmp_path, "child-1", codex_row)

    # Claude's side now performs an ordinary update touching only a column IT knows about.
    M.upsert_row(tmp_path, "child-1", {"phase": "verified"})

    reread = M.read_rows(tmp_path)["child-1"]
    assert reread["phase"] == "verified"
    # The nested key neither runtime's write explicitly re-sent survives — this is the C4
    # requirement, and it is specifically about a key *inside* a row, not a top-level key.
    assert reread["codex_execution_class"] == "review-max"


# --------------------------------------------------------------------------- 5. unsupported schema


def test_unsupported_schema_version_halts_with_a_receipt_and_mutates_nothing(
    tmp_path: Path,
) -> None:
    path = M.register_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bogus = {"schema_version": 999, "rows": {"x": {"id": "x", "run_id": "r", "phase": "planned"}}}
    path.write_text(json.dumps(bogus))
    before = path.read_text()

    assert not M.halt_receipt_path(tmp_path).exists()

    with pytest.raises(M.UnsupportedSchemaVersionError, match="999"):
        M.read_register(tmp_path)

    # register.json itself was never touched.
    assert path.read_text() == before

    # A receipt was written recording the halt.
    receipt = json.loads(M.halt_receipt_path(tmp_path).read_text())
    assert receipt["found_schema_version"] == 999
    assert receipt["supported_schema_versions"] == sorted(M.SUPPORTED_SCHEMA_VERSIONS)

    # A subsequent write attempt against the same unsupported file also refuses, still without
    # mutating register.json.
    with pytest.raises(M.UnsupportedSchemaVersionError):
        M.upsert_row(tmp_path, "y", {"run_id": "r"})
    assert path.read_text() == before


# --------------------------------------------------------------------------- 6. concurrent writers


def test_two_sequential_writers_do_not_lose_the_first_writers_row(tmp_path: Path) -> None:
    M.upsert_row(tmp_path, "child-1", {"run_id": "run-a", "phase": "planned"})
    M.upsert_row(tmp_path, "child-2", {"run_id": "run-a", "phase": "planned"})

    rows = M.read_rows(tmp_path)
    assert set(rows) == {"child-1", "child-2"}


def test_two_concurrent_writers_do_not_lose_the_first_writers_row(tmp_path: Path) -> None:
    # Real concurrency, not just sequential calls: two threads racing upsert_row for two
    # different ids must both survive — this is what the exclusive flock actually buys.
    errors: list[BaseException] = []

    def _write(row_id: str) -> None:
        try:
            for _ in range(25):
                M.upsert_row(tmp_path, row_id, {"run_id": "run-a", "phase": "working"})
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_write, args=(rid,)) for rid in ("child-1", "child-2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    rows = M.read_rows(tmp_path)
    assert set(rows) == {"child-1", "child-2"}


# --------------------------------------------------------------------------- 7. retire a run


def test_retiring_a_run_moves_its_rows_and_leaves_other_runs_intact(tmp_path: Path) -> None:
    M.upsert_row(tmp_path, "a1", {"run_id": "run-a", "phase": "verified"})
    M.upsert_row(tmp_path, "a2", {"run_id": "run-a", "phase": "verified"})
    M.upsert_row(tmp_path, "b1", {"run_id": "run-b", "phase": "working"})

    final_path = M.retire_run(tmp_path, "run-a")

    assert final_path == M.final_register_path(tmp_path, "run-a")
    final_doc = json.loads(final_path.read_text())
    assert set(final_doc["rows"]) == {"a1", "a2"}

    live = M.read_rows(tmp_path)
    assert set(live) == {"b1"}
    assert live["b1"]["phase"] == "working"

    # Retiring run-a a second time is a harmless no-op (nothing left to retire).
    M.retire_run(tmp_path, "run-a")
    assert set(M.read_rows(tmp_path)) == {"b1"}
