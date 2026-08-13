"""Tests for the orchestrate register (U2): the whole state model for a herdr-driven run and the
Claude<->Codex handoff seam (R12).

Each of the unit's seven required scenarios gets its own test, named for the scenario, asserting
exactly what that scenario states — not something weaker that would still report green.
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
        "base_commit": "abc123",
        "phase": "working",
        "expected_state": "working",
        "observed_state": "working",
        "observed_state_source": "observed:session_snapshot",
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


def test_new_row_always_has_both_hang_detection_time_columns(tmp_path: Path) -> None:
    # Repair round 1 (R7): the module docstring claims deadline/max_quiet_seconds "always exist"
    # on a row regardless of which hang-detection strategy it uses. That was previously false —
    # upsert_row only wrote what a caller passed. Fixed by seeding both to None at row creation.
    M.upsert_row(tmp_path, "only-deadline", {"run_id": "run-a", "deadline": 12345.0})
    only_deadline = M.read_rows(tmp_path)["only-deadline"]
    assert only_deadline["deadline"] == 12345.0
    assert only_deadline["max_quiet_seconds"] is None

    M.upsert_row(tmp_path, "only-quiet", {"run_id": "run-a", "max_quiet_seconds": 600})
    only_quiet = M.read_rows(tmp_path)["only-quiet"]
    assert only_quiet["max_quiet_seconds"] == 600
    assert only_quiet["deadline"] is None

    M.upsert_row(tmp_path, "neither", {"run_id": "run-a"})
    neither = M.read_rows(tmp_path)["neither"]
    assert neither["deadline"] is None
    assert neither["max_quiet_seconds"] is None

    # Other, genuinely optional columns are still simply absent rather than seeded — the seeding
    # is specific to this one alternative-strategy pair, not a blanket "every column exists."
    assert "base_commit" not in neither
    assert "tokens_observed" not in neither


def test_empty_batch_returns_without_taking_the_write_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _unexpected_lock(root: Path):  # noqa: ANN202
        pytest.fail(f"empty batch tried to lock {root}")

    monkeypatch.setattr(M, "_write_locked", _unexpected_lock)

    assert M.upsert_rows(tmp_path, {}) == {}
    assert not M.register_path(tmp_path).exists()


# --------------------------------------------------------------------------- 3. atomic write
#
# Repair round 1 (R3): the original test here stubbed ``os.replace`` to raise *after* the temp
# file had already been written in full, then asserted the live register was untouched. That is a
# real, worth-keeping property, but it is a **failed replace**, not an **interrupted write** — the
# temp file it produces is complete, never torn, so nothing in the old test ever created a partial
# file and asked whether one remained. Picking option (a) from the repair brief: the test below
# genuinely produces a torn temp file (a truncated write, the way a real crash mid-``os.write``
# would leave one) and asks the real question — does a torn *sibling* file ever leak into or
# affect the live register. The old, still-valid failed-replace property is kept under an honest
# name rather than dropped.


def test_failed_replace_leaves_live_register_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Establish a known-good register first.
    M.upsert_row(tmp_path, "child-1", {"run_id": "run-a", "phase": "planned"})
    before = M.register_path(tmp_path).read_text()

    real_replace = __import__("os").replace

    def _boom(src, dst):  # noqa: ANN001
        if Path(dst) == M.register_path(tmp_path):
            raise OSError("simulated crash just before replace")
        return real_replace(src, dst)

    monkeypatch.setattr(M.os, "replace", _boom)

    with pytest.raises(OSError, match="simulated crash"):
        M.upsert_row(tmp_path, "child-2", {"run_id": "run-a", "phase": "planned"})

    # The live register file is untouched — still exactly the pre-failure content, never a
    # half-written mixture of old and new. A failed replace never reaches the real path at all.
    assert M.register_path(tmp_path).read_text() == before
    # And the orphaned temp this attempt wrote (its finally-unlink runs, but only after the
    # monkeypatched os.replace already raised) is never mistaken for the live register: nothing
    # non-temp, non-lock is left beside it.
    leftovers = [p for p in tmp_path.glob("**/register.json*") if p != M.register_path(tmp_path)]
    assert all(p.suffix == ".lock" or ".tmp" in p.name for p in leftovers)


def test_a_genuinely_interrupted_write_never_reaches_the_live_register_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Repair round 2 (P2): the prior version of this test planted an already-torn file at a
    # ``*.tmp`` path and asserted readers ignore it — a test of path selection, not of an
    # interrupted write (it would still pass with the write loop deleted). This version makes
    # ``_atomic_write_json``'s own ``os.write`` loop produce the interruption: the first call
    # transfers a real partial write (a legitimate ``os.write`` outcome on its own), the second
    # raises mid-write, the way a real crash could land between two calls. If register.py's write
    # loop were ever replaced with something that doesn't call ``os.write`` at all, this stub
    # would simply never fire and the test would fail to observe the interruption it expects.
    M.upsert_row(tmp_path, "child-1", {"run_id": "run-a", "phase": "planned"})
    before = M.register_path(tmp_path).read_text()

    real_write = __import__("os").write
    calls = {"n": 0}

    def _torn_write(fd, data):  # noqa: ANN001
        calls["n"] += 1
        if calls["n"] == 1:
            # A real partial write: only a third of the requested bytes actually land on disk,
            # which is a legitimate os.write outcome by itself, not yet a failure.
            return real_write(fd, data[: max(1, len(data) // 3)])
        raise OSError("simulated crash mid-write, after a partial write already landed")

    monkeypatch.setattr(M.os, "write", _torn_write)

    with pytest.raises(OSError, match="simulated crash mid-write"):
        M.upsert_row(tmp_path, "child-2", {"run_id": "run-a", "phase": "planned"})

    # The live register path was never replaced into — it is byte-identical to its
    # pre-interruption content, and the row from before the interrupted write is still readable.
    assert M.register_path(tmp_path).read_text() == before
    assert M.read_register(tmp_path)["rows"]["child-1"]["phase"] == "planned"
    assert "child-2" not in M.read_rows(tmp_path)

    # And an ordinary subsequent write (write restored to the real implementation) proceeds
    # normally, unaffected by the interrupted attempt that preceded it.
    monkeypatch.setattr(M.os, "write", real_write)
    M.upsert_row(tmp_path, "child-1", {"phase": "working"})
    assert M.read_register(tmp_path)["rows"]["child-1"]["phase"] == "working"


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


def test_unknown_key_at_document_root_is_preserved_on_write(tmp_path: Path) -> None:
    # Repair round 1 (R2): the brief's scenario 4 says "not only an unknown top-level key" —
    # meaning both the nested case above AND this one must survive. A document-root key, e.g. a
    # handoff cursor one runtime writes that the other's register.py has never heard of, must
    # equally survive an ordinary write by the other runtime.
    M.upsert_row(tmp_path, "child-1", {"run_id": "run-a", "phase": "planned"})
    path = M.register_path(tmp_path)
    doc = json.loads(path.read_text())
    doc["handoff_token"] = "abc123"  # unknown to this module, added directly on disk
    path.write_text(json.dumps(doc))

    M.upsert_row(tmp_path, "child-1", {"phase": "working"})

    on_disk = json.loads(path.read_text())
    assert on_disk["handoff_token"] == "abc123"
    assert on_disk["rows"]["child-1"]["phase"] == "working"


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

    # Repair round 1 (R1): retiring run-a a SECOND time — after it already succeeded — must not
    # destroy the archive the first call just wrote. The live register no longer has run-a's
    # rows, so a naive re-retire recomputes an empty set and would overwrite the archive with it.
    second_final_path = M.retire_run(tmp_path, "run-a")
    assert second_final_path == final_path
    archive_after_second_retire = json.loads(final_path.read_text())
    assert set(archive_after_second_retire["rows"]) == {"a1", "a2"}  # NOT emptied
    # Other runs are still untouched.
    assert set(M.read_rows(tmp_path)) == {"b1"}


def test_retiring_a_run_with_nothing_live_and_no_prior_archive_writes_nothing(
    tmp_path: Path,
) -> None:
    # A run_id that was never registered (or whose rows were already retired by a run that never
    # wrote an archive in this test's tmp_path) has nothing to retire. This is not an error;
    # nothing is written, and None signals "there was no archive to point at."
    result = M.retire_run(tmp_path, "run-never-registered")
    assert result is None
    assert not M.final_register_path(tmp_path, "run-never-registered").exists()


def test_retiring_a_run_preserves_a_document_root_key_in_the_live_register(
    tmp_path: Path,
) -> None:
    # Repair round 2 (P2): upsert_row's preservation of an unknown document-root key (R2) was
    # covered; retire_run's was not, even though it rewrites the live register through the exact
    # same _read_register_unlocked -> mutate -> _atomic_write_json path. A future edit that
    # reintroduces envelope reconstruction inside retire_run specifically would break the
    # Claude<->Codex handoff on every retirement while leaving every existing test green.
    M.upsert_row(tmp_path, "a1", {"run_id": "run-a", "phase": "verified"})
    M.upsert_row(tmp_path, "b1", {"run_id": "run-b", "phase": "working"})

    path = M.register_path(tmp_path)
    doc = json.loads(path.read_text())
    doc["handoff_token"] = "still-here"  # unknown to this module, added directly on disk
    path.write_text(json.dumps(doc))

    M.retire_run(tmp_path, "run-a")

    live_on_disk = json.loads(path.read_text())
    assert live_on_disk["handoff_token"] == "still-here"
    assert set(live_on_disk["rows"]) == {"b1"}
