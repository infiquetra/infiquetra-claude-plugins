"""Tests for the orchestrate register (U2): the whole state model for a herdr-driven run and the
Claude<->Codex handoff seam (R12).

Each of the unit's seven required scenarios gets its own test, named for the scenario, asserting
exactly what that scenario states — not something weaker that would still report green.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import stat
import subprocess
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


@pytest.fixture(autouse=True)
def _register_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    monkeypatch.setenv(M.REGISTER_DIR_ENV, str(tmp_path / "registers"))


def _record(root: Path, run_id: str) -> Path:
    """Plant the coordinator-recorded work location next to the live register."""
    directory = Path(str(M.register_dir()))
    path = directory / f"{run_id}.root"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(Path(root).resolve()), encoding="utf-8")
    path.chmod(384)
    return path


def _full_row(row_id: str = "child-1", run_id: str = "run-a") -> dict:
    """A row with every durable intent and outcome column populated."""
    return {
        "id": row_id,
        "run_id": run_id,
        "agent": "worker",
        "vendor": "runtime-a",
        "model": "model-a",
        "effort": "high",
        "task": "implement the register change",
        "work_shape": "implementation",
        "scope": "plugins/orchestrate/",
        "artifact_path": "plugins/orchestrate/skills/orchestrate/scripts/register.py",
        "predicate": "pytest tests/test_orchestrate_register.py",
        "integration_mode": "patch",
        "destination": "plugins/orchestrate/",
        "base_commit": "abc123",
        "phase": "working",
        "expected_state": "working",
        "dispatched_at": 1000.0,
        "deadline": None,
        "max_quiet_seconds": 600,
        "last_event_at": 1000.5,
        "tokens_observed": 1234,
        "tokens_reserved": 50000,
        "tokens_max": 50000,
    }


def test_fresh_register_initialises_with_a_schema_version(tmp_path: Path) -> None:
    doc = M.read_register("run-a")
    assert doc["schema_version"] == M.SCHEMA_VERSION
    assert doc["rows"] == {}
    M.upsert_row(tmp_path, "child-1", {"run_id": "run-a"}, run_id="run-a")
    on_disk = json.loads(M.register_path("run-a").read_text())
    assert on_disk["schema_version"] == M.SCHEMA_VERSION


def test_row_round_trips_intent_and_outcome_only(tmp_path: Path) -> None:
    row = _full_row()
    unowned = {key: value for key, value in row.items() if key not in M.COLUMN_WRITERS}
    M.upsert_row(tmp_path, "child-1", unowned, run_id="run-a")
    M.write_phase(tmp_path, "child-1", row["phase"], run_id="run-a")
    M.upsert_row(
        tmp_path,
        "child-1",
        {"tokens_observed": row["tokens_observed"]},
        run_id="run-a",
        writer=M.TOKENS_OBSERVED_WRITER,
    )
    M.upsert_row(
        tmp_path,
        "child-1",
        {"tokens_max": row["tokens_max"]},
        run_id="run-a",
        writer=M.TOKENS_MAX_WRITER,
    )
    M.upsert_row(
        tmp_path,
        "child-1",
        {"tokens_reserved": row["tokens_reserved"]},
        run_id="run-a",
        writer=M.TOKENS_RESERVED_WRITER,
    )
    stored = M.upsert_row(
        tmp_path,
        "child-1",
        {"artifact_path": row["artifact_path"]},
        run_id="run-a",
        writer=M.ARTIFACT_PATH_WRITER,
    )
    reread = M.read_rows(tmp_path, run_id="run-a")["child-1"]
    assert reread == stored
    for column in M.ROW_COLUMNS:
        assert column in reread, f"column {column!r} missing after round trip"
        assert reread[column] == row[column]
    assert M.REMOVED_ROW_COLUMNS.isdisjoint(reread)


@pytest.mark.parametrize("column", sorted(M.REMOVED_ROW_COLUMNS))
def test_writing_a_live_session_fact_is_refused(tmp_path: Path, column: str) -> None:
    with pytest.raises(M.RemovedColumnError, match="not durable register columns"):
        M.upsert_row(tmp_path, "child-1", {column: "observed-value"}, run_id="run-a")
    assert not M.register_path("run-a").exists()


@pytest.mark.parametrize("column", sorted(M.REMOVED_ROW_COLUMNS))
def test_reading_a_removed_column_is_loud(tmp_path: Path, column: str) -> None:
    row = M.upsert_row(tmp_path, "child-1", {"task": "work"}, run_id="run-a")
    with pytest.raises(M.RemovedColumnError, match="live session fact"):
        row[column]
    with pytest.raises(M.RemovedColumnError, match="live session fact"):
        row.get(column)
    with pytest.raises(M.RemovedColumnError, match="live session fact"):
        assert column in row


def test_production_has_no_in_process_session_fact_store_or_retired_writer() -> None:
    """The deleted cache and its write helpers cannot return under another call site."""
    scripts = SCRIPT.parent
    retired_names = {
        "_PROVISIONAL_SESSION_FACTS",
        "remember_provisional_session_facts",
        "provisional_session_fact",
        "record_observed_state",
        "record_observed_states",
    }
    violations: list[str] = []
    for path in sorted(scripts.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            name = node.id if isinstance(node, ast.Name) else None
            attribute = node.attr if isinstance(node, ast.Attribute) else None
            retired = retired_names.intersection({name, attribute})
            if retired:
                violations.append(
                    f"{path.name}:{getattr(node, 'lineno', 0)} retains {sorted(retired)}"
                )
    assert violations == [], "retired session-fact state remains:\n" + "\n".join(violations)


def test_a_new_writer_is_refused_without_naming_its_helper_or_payload_shape(tmp_path: Path) -> None:
    """The API boundary catches a future writer with a variable-built payload."""

    def future_writer(field: str) -> None:
        payload: dict[str, object] = {}
        payload[field] = "new live observation"
        M.upsert_row(tmp_path, "child-1", payload, run_id="run-a")

    for field in M.REMOVED_ROW_COLUMNS:
        with pytest.raises(M.RemovedColumnError, match="not durable register columns"):
            future_writer(field)
    assert not M.register_path("run-a").exists()


def test_register_row_copy_and_mutators_keep_removed_columns_loud(tmp_path: Path) -> None:
    row = M.upsert_row(tmp_path, "child-1", {"task": "work"}, run_id="run-a")
    copied = row.copy()
    assert isinstance(copied, M.RegisterRow)
    attempts = (
        lambda: row.__setitem__("pane_id", "pane-a"),
        lambda: row.setdefault("pane_id", "pane-a"),
        lambda: row.update({"pane_id": "pane-a"}),
        lambda: copied.__ior__({"pane_id": "pane-a"}),
        lambda: row | {"pane_id": "pane-a"},
        lambda: {"pane_id": "pane-a"} | row,
    )
    for attempt in attempts:
        with pytest.raises(M.RemovedColumnError, match="live session fact"):
            attempt()


def test_corrupt_register_is_reported_through_the_register_error_contract(tmp_path: Path) -> None:
    path = M.register_path("run-a")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(M.RegisterError, match="not readable JSON") as caught:
        M.read_rows(tmp_path, run_id="run-a")
    assert not isinstance(caught.value, json.JSONDecodeError)


def test_schema_one_rows_are_normalized_before_use_and_migrated_on_write(tmp_path: Path) -> None:
    _record(tmp_path, "run-a")
    path = M.register_path("run-a")
    legacy_row = {
        "id": "child-1",
        "run_id": "run-a",
        "phase": "working",
        **{column: f"stale-{column}" for column in M.REMOVED_ROW_COLUMNS},
    }
    path.write_text(
        json.dumps({"schema_version": 1, "run_id": "run-a", "rows": {"child-1": legacy_row}}),
        encoding="utf-8",
    )

    normalized = M.read_register("run-a")
    assert normalized["schema_version"] == M.SCHEMA_VERSION
    assert M.REMOVED_ROW_COLUMNS.isdisjoint(normalized["rows"]["child-1"])
    untouched = json.loads(path.read_text(encoding="utf-8"))
    assert untouched["schema_version"] == 1
    assert set(M.REMOVED_ROW_COLUMNS).issubset(untouched["rows"]["child-1"])

    M.write_phase(tmp_path, "child-1", "verified", run_id="run-a")
    migrated = json.loads(path.read_text(encoding="utf-8"))
    assert migrated["schema_version"] == M.SCHEMA_VERSION
    assert M.REMOVED_ROW_COLUMNS.isdisjoint(migrated["rows"]["child-1"])
    assert migrated["rows"]["child-1"]["phase"] == "verified"


def test_new_row_always_has_both_hang_detection_time_columns(tmp_path: Path) -> None:
    M.upsert_row(
        tmp_path, "only-deadline", {"run_id": "run-a", "deadline": 12345.0}, run_id="run-a"
    )
    only_deadline = M.read_rows(tmp_path, run_id="run-a")["only-deadline"]
    assert only_deadline["deadline"] == 12345.0
    assert only_deadline["max_quiet_seconds"] is None
    M.upsert_row(
        tmp_path, "only-quiet", {"run_id": "run-a", "max_quiet_seconds": 600}, run_id="run-a"
    )
    only_quiet = M.read_rows(tmp_path, run_id="run-a")["only-quiet"]
    assert only_quiet["max_quiet_seconds"] == 600
    assert only_quiet["deadline"] is None
    M.upsert_row(tmp_path, "neither", {"run_id": "run-a"}, run_id="run-a")
    neither = M.read_rows(tmp_path, run_id="run-a")["neither"]
    assert neither["deadline"] is None
    assert neither["max_quiet_seconds"] is None
    assert "base_commit" not in neither
    assert "tokens_observed" not in neither


def test_empty_batch_returns_without_taking_the_write_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    def _unexpected_lock(root: Path):
        pytest.fail(f"empty batch tried to lock {root}")

    monkeypatch.setattr(M, "_write_locked", _unexpected_lock)
    assert M.upsert_rows(tmp_path, {}, run_id="run-a") == {}
    assert not M.register_path("run-a").exists()


def test_failed_replace_leaves_live_register_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    M.upsert_row(
        tmp_path,
        "child-1",
        {"run_id": "run-a", "phase": "planned"},
        run_id="run-a",
        writer="write_phase",
    )
    before = M.register_path("run-a").read_text()
    real_replace = __import__("os").replace

    def _boom(src, dst):
        if Path(dst) == M.register_path("run-a"):
            raise OSError("simulated crash just before replace")
        return real_replace(src, dst)

    monkeypatch.setattr(M.os, "replace", _boom)
    with pytest.raises(OSError, match="simulated crash"):
        M.upsert_row(
            tmp_path,
            "child-2",
            {"run_id": "run-a", "phase": "planned"},
            run_id="run-a",
            writer="write_phase",
        )
    assert M.register_path("run-a").read_text() == before
    leftovers = [
        p for p in (tmp_path / "registers").glob("run-a.json*") if p != M.register_path("run-a")
    ]
    assert all(p.suffix == ".lock" or ".tmp" in p.name for p in leftovers)


def test_a_genuinely_interrupted_write_never_reaches_the_live_register_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    M.upsert_row(
        tmp_path,
        "child-1",
        {"run_id": "run-a", "phase": "planned"},
        run_id="run-a",
        writer="write_phase",
    )
    before = M.register_path("run-a").read_text()
    real_write = __import__("os").write
    calls = {"n": 0}

    def _torn_write(fd, data):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_write(fd, data[: max(1, len(data) // 3)])
        raise OSError("simulated crash mid-write, after a partial write already landed")

    monkeypatch.setattr(M.os, "write", _torn_write)
    with pytest.raises(OSError, match="simulated crash mid-write"):
        M.upsert_row(
            tmp_path,
            "child-2",
            {"run_id": "run-a", "phase": "planned"},
            run_id="run-a",
            writer="write_phase",
        )
    assert M.register_path("run-a").read_text() == before
    assert M.read_register("run-a")["rows"]["child-1"]["phase"] == "planned"
    assert "child-2" not in M.read_rows(tmp_path, run_id="run-a")
    monkeypatch.setattr(M.os, "write", real_write)
    M.upsert_row(tmp_path, "child-1", {"phase": "working"}, run_id="run-a", writer="write_phase")
    assert M.read_register("run-a")["rows"]["child-1"]["phase"] == "working"


def test_unknown_key_nested_in_child_row_is_preserved_on_write(tmp_path: Path) -> None:
    codex_row = {"run_id": "run-a", "phase": "working", "codex_execution_class": "review-max"}
    M.upsert_row(tmp_path, "child-1", codex_row, run_id="run-a", writer="write_phase")
    M.upsert_row(tmp_path, "child-1", {"phase": "verified"}, run_id="run-a", writer="write_phase")
    reread = M.read_rows(tmp_path, run_id="run-a")["child-1"]
    assert reread["phase"] == "verified"
    assert reread["codex_execution_class"] == "review-max"


def test_unknown_key_at_document_root_is_preserved_on_write(tmp_path: Path) -> None:
    M.upsert_row(
        tmp_path,
        "child-1",
        {"run_id": "run-a", "phase": "planned"},
        run_id="run-a",
        writer="write_phase",
    )
    path = M.register_path("run-a")
    doc = json.loads(path.read_text())
    doc["handoff_token"] = "abc123"
    path.write_text(json.dumps(doc))
    M.upsert_row(tmp_path, "child-1", {"phase": "working"}, run_id="run-a", writer="write_phase")
    on_disk = json.loads(path.read_text())
    assert on_disk["handoff_token"] == "abc123"
    assert on_disk["rows"]["child-1"]["phase"] == "working"


def test_unsupported_schema_version_halts_with_a_receipt_and_mutates_nothing(
    tmp_path: Path,
) -> None:
    path = M.register_path("run-a")
    path.parent.mkdir(parents=True, exist_ok=True)
    bogus = {"schema_version": 999, "rows": {"x": {"id": "x", "run_id": "r", "phase": "planned"}}}
    path.write_text(json.dumps(bogus))
    before = path.read_text()
    assert not M.halt_receipt_path("run-a").exists()
    with pytest.raises(M.UnsupportedSchemaVersionError, match="999"):
        M.read_register("run-a")
    assert path.read_text() == before
    receipt = json.loads(M.halt_receipt_path("run-a").read_text())
    assert receipt["found_schema_version"] == 999
    assert receipt["supported_schema_versions"] == sorted(M.SUPPORTED_SCHEMA_VERSIONS)
    with pytest.raises(M.UnsupportedSchemaVersionError):
        M.upsert_row(tmp_path, "y", {"run_id": "run-a"}, run_id="run-a")
    assert path.read_text() == before


def test_two_sequential_writers_do_not_lose_the_first_writers_row(tmp_path: Path) -> None:
    M.upsert_row(
        tmp_path,
        "child-1",
        {"run_id": "run-a", "phase": "planned"},
        run_id="run-a",
        writer="write_phase",
    )
    M.upsert_row(
        tmp_path,
        "child-2",
        {"run_id": "run-a", "phase": "planned"},
        run_id="run-a",
        writer="write_phase",
    )
    rows = M.read_rows(tmp_path, run_id="run-a")
    assert set(rows) == {"child-1", "child-2"}


def test_two_concurrent_writers_do_not_lose_the_first_writers_row(tmp_path: Path) -> None:
    errors: list[BaseException] = []

    def _write(row_id: str) -> None:
        try:
            for _ in range(25):
                M.upsert_row(
                    tmp_path,
                    row_id,
                    {"run_id": "run-a", "phase": "working"},
                    run_id="run-a",
                    writer="write_phase",
                )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_write, args=(rid,)) for rid in ("child-1", "child-2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    rows = M.read_rows(tmp_path, run_id="run-a")
    assert set(rows) == {"child-1", "child-2"}


def test_retiring_a_run_moves_its_rows_and_leaves_other_runs_intact(tmp_path: Path) -> None:
    _record(tmp_path, "run-a")
    _record(tmp_path, "run-b")
    M.upsert_row(
        tmp_path,
        "a1",
        {"run_id": "run-a", "phase": "verified"},
        run_id="run-a",
        writer="write_phase",
    )
    M.upsert_row(
        tmp_path,
        "a2",
        {"run_id": "run-a", "phase": "verified"},
        run_id="run-a",
        writer="write_phase",
    )
    M.upsert_row(
        tmp_path,
        "b1",
        {"run_id": "run-b", "phase": "working"},
        run_id="run-b",
        writer="write_phase",
    )
    final_path = M.retire_run(tmp_path, "run-a")
    assert final_path == M.final_register_path(tmp_path, "run-a")
    final_doc = json.loads(final_path.read_text())
    assert set(final_doc["rows"]) == {"a1", "a2"}
    live = M.read_rows(tmp_path, run_id="run-b")
    assert set(live) == {"b1"}
    assert live["b1"]["phase"] == "working"
    second_final_path = M.retire_run(tmp_path, "run-a")
    assert second_final_path == final_path
    archive_after_second_retire = json.loads(final_path.read_text())
    assert set(archive_after_second_retire["rows"]) == {"a1", "a2"}
    assert set(M.read_rows(tmp_path, run_id="run-b")) == {"b1"}


def test_retiring_a_run_with_nothing_live_and_no_prior_archive_writes_nothing(
    tmp_path: Path,
) -> None:
    result = M.retire_run(tmp_path, "run-never-registered")
    assert result is None
    assert not M.final_register_path(tmp_path, "run-never-registered").exists()


def test_retiring_a_run_preserves_a_document_root_key_in_the_live_register(tmp_path: Path) -> None:
    _record(tmp_path, "run-a")
    _record(tmp_path, "run-b")
    M.upsert_row(
        tmp_path,
        "a1",
        {"run_id": "run-a", "phase": "verified"},
        run_id="run-a",
        writer="write_phase",
    )
    M.upsert_row(
        tmp_path,
        "b1",
        {"run_id": "run-b", "phase": "working"},
        run_id="run-b",
        writer="write_phase",
    )
    path_a = M.register_path("run-a")
    doc_a = json.loads(path_a.read_text())
    doc_a["handoff_token"] = "still-here"
    path_a.write_text(json.dumps(doc_a))
    path_b = M.register_path("run-b")
    doc_b = json.loads(path_b.read_text())
    doc_b["handoff_token"] = "b-token"
    path_b.write_text(json.dumps(doc_b))
    M.retire_run(tmp_path, "run-a")
    assert not path_a.exists()
    archive = json.loads(M.final_register_path(tmp_path, "run-a").read_text())
    assert archive["handoff_token"] == "still-here"
    live_b = json.loads(path_b.read_text())
    assert live_b["handoff_token"] == "b-token"
    assert set(live_b["rows"]) == {"b1"}


def test_a_run_id_is_one_live_register_on_this_host(tmp_path: Path) -> None:
    """Two checkouts that name the same run share one live document.

    That is the host-global decision: same-host handoff needs it, and two unrelated
    projects that pick the same label collide on it. A later write must name the
    work location the first writer stamped; a second checkout is refused, not
    silently merged.
    """
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    M.upsert_row(
        repo_a,
        "child-1",
        {"run_id": "run-a", "phase": "planned"},
        run_id="run-a",
        writer="write_phase",
    )
    with pytest.raises(M.RegisterError, match="bound to"):
        M.upsert_row(
            repo_b,
            "child-1",
            {"run_id": "run-a", "phase": "working"},
            run_id="run-a",
            writer="write_phase",
        )
    assert M.register_path("run-a").parent == tmp_path / "registers"
    assert M.read_rows(repo_a, run_id="run-a")["child-1"]["phase"] == "planned"
    with pytest.raises(M.RegisterError, match="bound to"):
        M.read_rows(repo_b, run_id="run-a")


def test_the_live_register_is_not_inside_the_repository(tmp_path: Path) -> None:
    """A child working in the repository cannot write the live register by address."""
    repo = tmp_path / "repo"
    repo.mkdir()
    M.upsert_row(
        repo,
        "child-1",
        {"run_id": "run-a", "phase": "planned"},
        run_id="run-a",
        writer="write_phase",
    )
    live = M.register_path("run-a").resolve()
    assert not live.is_relative_to(repo.resolve())


def test_a_repo_local_file_is_not_the_live_register(tmp_path: Path) -> None:
    """A JSON document planted where the register used to live is not this run's store."""
    repo = tmp_path / "repo"
    repo.mkdir()
    planted = repo / ".orchestrate" / "register.json"
    planted.parent.mkdir()
    planted.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rows": {"planted": {"id": "planted", "run_id": "run-a", "phase": "verified"}},
            }
        ),
        encoding="utf-8",
    )
    assert "planted" not in M.read_rows(repo, run_id="run-a")
    M.upsert_row(
        repo,
        "child-1",
        {"run_id": "run-a", "phase": "planned"},
        run_id="run-a",
        writer="write_phase",
    )
    assert M.read_rows(repo, run_id="run-a")["child-1"]["phase"] == "planned"
    assert "planted" not in M.read_rows(repo, run_id="run-a")
    assert not M.register_path("run-a").is_relative_to(repo.resolve())


def test_retiring_a_run_frees_its_id(tmp_path: Path) -> None:
    """After retirement the live file is gone and the id may be reused."""
    _record(tmp_path, "run-a")
    M.upsert_row(
        tmp_path,
        "child-1",
        {"run_id": "run-a", "phase": "verified"},
        run_id="run-a",
        writer="write_phase",
    )
    assert M.retire_run(tmp_path, "run-a") is not None
    assert not M.register_path("run-a").exists()
    M.upsert_row(
        tmp_path,
        "child-2",
        {"run_id": "run-a", "phase": "planned"},
        run_id="run-a",
        writer="write_phase",
    )
    assert M.read_rows(tmp_path, run_id="run-a")["child-2"]["phase"] == "planned"
    assert "child-1" not in M.read_rows(tmp_path, run_id="run-a")


def test_a_write_cannot_name_a_row_without_naming_its_run(tmp_path: Path) -> None:
    """The mutation API has no form that guesses the run from the row id."""
    import inspect

    assert "run_id" in inspect.signature(M.upsert_row).parameters
    assert inspect.signature(M.upsert_row).parameters["run_id"].default is inspect.Parameter.empty
    assert inspect.signature(M.upsert_rows).parameters["run_id"].default is inspect.Parameter.empty
    assert inspect.signature(M.read_rows).parameters["run_id"].default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        M.upsert_row(tmp_path, "child-a", {"phase": "working"}, writer="write_phase")
    with pytest.raises(TypeError):
        M.read_rows(tmp_path)


def test_the_stamped_view_keeps_two_runs_that_share_a_row_id(tmp_path: Path) -> None:
    """The operator view is keyed by (run, row), so one row id cannot hide another."""
    M.upsert_row(tmp_path, "child-a", {"phase": "verified"}, run_id="run-a", writer="write_phase")
    M.upsert_row(tmp_path, "child-a", {"phase": "working"}, run_id="run-b", writer="write_phase")
    merged = M.rows_stamped_against(tmp_path)
    assert merged["run-a", "child-a"]["phase"] == "verified"
    assert merged["run-b", "child-a"]["phase"] == "working"
    assert "child-a" not in merged


def test_retiring_against_the_wrong_work_location_leaves_the_live_file(tmp_path: Path) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    _record(repo_a, "run-a")
    M.upsert_row(repo_a, "child-1", {"phase": "verified"}, run_id="run-a", writer="write_phase")
    before = M.register_path("run-a").read_text()
    with pytest.raises(M.RegisterError, match="bound to"):
        M.retire_run(repo_b, "run-a")
    assert M.register_path("run-a").read_text() == before
    assert not M.final_register_path(repo_b, "run-a").exists()
    assert not M.final_register_path(repo_a, "run-a").exists()


def test_pytest_refuses_the_default_host_register_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(M.REGISTER_DIR_ENV, raising=False)
    monkeypatch.delenv("ORCHESTRATE_ALLOW_DEFAULT_HOST_DIR", raising=False)
    with pytest.raises(M.RegisterError, match="host default"):
        M.register_dir()


def test_retire_without_a_live_file_refuses_a_directory_that_is_not_recorded(
    tmp_path: Path,
) -> None:
    """A missing live file does not authorize forgetting the key."""
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    _record(repo_a, "run-a")
    key = tmp_path / "registers" / "run-a.key"
    sidecar = M.register_dir() / "run-a.root"
    assert sidecar.is_file()
    with pytest.raises(M.RegisterError, match="bound to"):
        M.retire_run(repo_b, "run-a")
    assert sidecar.is_file()
    assert sidecar.read_text(encoding="utf-8").strip() == str(repo_a.resolve())
    assert not key.exists()


def test_retire_without_a_live_file_does_not_forget_a_key_with_no_recorded_root(
    tmp_path: Path,
) -> None:
    """No sidecar, no delete. A leftover key may belong to a new generation."""
    empty = tmp_path / "empty"
    empty.mkdir()
    assert M.retire_run(empty, "run-a") is None
    assert not (M.register_dir() / "run-a.root").exists()


def test_retire_without_a_live_file_clears_the_recorded_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    sidecar = _record(repo, "run-a")
    result = M.retire_run(repo, "run-a")
    assert result is None
    assert not sidecar.exists()


def test_retire_refuses_when_only_a_first_writer_stamp_exists(tmp_path: Path) -> None:
    """A stamp is continuity. It is not enough to archive or forget the key."""
    M.upsert_row(tmp_path, "child-1", {"phase": "verified"}, run_id="run-a", writer="write_phase")
    live = M.register_path("run-a")
    before = live.read_text()
    with pytest.raises(M.RegisterError, match="no recorded work location"):
        M.retire_run(tmp_path, "run-a")
    assert live.read_text() == before


def test_a_nonempty_unbound_register_is_refused(tmp_path: Path) -> None:
    """The unbound exception is for a genuinely empty document, not a planted one."""
    path = M.register_path("run-a")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-a",
                "rows": {"child-a": {"id": "child-a", "run_id": "run-a", "phase": "working"}},
            }
        ),
        encoding="utf-8",
    )
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(M.RegisterError, match="no recorded or stamped"):
        M.read_rows(empty, run_id="run-a")
    with pytest.raises(M.RegisterError, match="no work location"):
        M.upsert_row(empty, "child-a", {"phase": "working"}, run_id="run-a", writer="write_phase")
    assert json.loads(path.read_text())["rows"]["child-a"]["phase"] == "working"


def test_a_package_directory_is_canonicalized_to_the_repository(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    package = repo / "packages" / "tool"
    package.mkdir(parents=True)
    _git_init(repo)
    M.upsert_row(package, "child-1", {"phase": "planned"}, run_id="run-a", writer="write_phase")
    doc = json.loads(M.register_path("run-a").read_text())
    assert Path(doc["repo_root"]).resolve() == repo.resolve()
    rows = M.read_rows(package, run_id="run-a")
    assert rows["child-1"]["phase"] == "planned"
    assert ("run-a", "child-1") in M.rows_stamped_against(package)


def test_a_recorded_root_rewrites_a_disagreeing_stamp(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    package = repo / "packages" / "tool"
    package.mkdir(parents=True)
    _git_init(repo)
    M.upsert_row(repo, "child-1", {"phase": "planned"}, run_id="run-a", writer="write_phase")
    path = M.register_path("run-a")
    doc = json.loads(path.read_text())
    doc["repo_root"] = str(package.resolve())
    path.write_text(json.dumps(doc), encoding="utf-8")
    _record(repo, "run-a")
    M.reconcile_stamp("run-a", repo)
    assert ("run-a", "child-1") in M.rows_stamped_against(repo)
    M.upsert_row(package, "child-1", {"phase": "working"}, run_id="run-a", writer="write_phase")
    assert Path(json.loads(path.read_text())["repo_root"]).resolve() == repo.resolve()


def test_a_noncanonical_stored_root_is_reachable_from_the_repository(tmp_path: Path) -> None:
    """A value written before canonicalize still compares as the repository."""
    repo = tmp_path / "repo"
    package = repo / "packages" / "tool"
    package.mkdir(parents=True)
    _git_init(repo)
    M.upsert_row(repo, "child-1", {"phase": "planned"}, run_id="run-a", writer="write_phase")
    sidecar = _record(package, "run-a")
    assert sidecar.read_text(encoding="utf-8").strip() == str(package.resolve())
    assert M.read_rows(repo, run_id="run-a")["child-1"]["phase"] == "planned"
    assert M.read_rows(package, run_id="run-a")["child-1"]["phase"] == "planned"
    M.upsert_row(repo, "child-1", {"phase": "working"}, run_id="run-a", writer="write_phase")
    assert M.read_rows(package, run_id="run-a")["child-1"]["phase"] == "working"


def test_a_package_path_stored_on_disk_compares_as_the_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The comparison canonicalizes the stored side, not only the caller.

    Sidecar and stamp hold a package subdirectory (mode 0600). The stored
    value is handed to the comparison resolved, not as a git top level, so
    a comparison that only resolves the expected side cannot agree.
    """
    repo = tmp_path / "repo"
    package = repo / "packages" / "tool"
    package.mkdir(parents=True)
    _git_init(repo)
    M.upsert_row(repo, "child-1", {"phase": "planned"}, run_id="run-a", writer="write_phase")
    path = M.register_path("run-a")
    doc = json.loads(path.read_text())
    doc["repo_root"] = str(package.resolve())
    path.write_text(json.dumps(doc), encoding="utf-8")
    sidecar = _record(package, "run-a")
    assert stat.S_IMODE(sidecar.stat().st_mode) == 384
    assert sidecar.read_text(encoding="utf-8").strip() == str(package.resolve())
    stored = package.resolve()

    def resolve_only(file_path: Path) -> Path:
        info = file_path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise M.RegisterError(f"run root {file_path} is a symlink; it must be a regular file")
        if info.st_mode & 63:
            raise M.RegisterError(
                f"run root {file_path} is accessible beyond its owner (mode {stat.S_IMODE(info.st_mode):04o})"
            )
        material = file_path.read_bytes().decode("utf-8").strip()
        return Path(material).resolve()

    monkeypatch.setattr(M, "_read_recorded_root_file", resolve_only)
    monkeypatch.setattr(M, "run_work_location", lambda _run_id: stored)
    for claimed in (repo, package):
        recorded = M.assert_root_belongs_to_run(claimed, "run-a", require_recorded=True)
        assert recorded is not None
        assert recorded.resolve() == repo.resolve()
        bound = M.assert_root_belongs_to_run(claimed, "run-a")
        assert bound is not None
        assert bound.resolve() == repo.resolve()


def test_a_recorded_root_readable_beyond_its_owner_is_refused(tmp_path: Path) -> None:
    """The register's sidecar reader refuses a widened mode, not only the completion reader."""
    repo = tmp_path / "repo"
    repo.mkdir()
    sidecar = _record(repo, "run-a")
    sidecar.chmod(420)
    with pytest.raises(M.RegisterError, match="accessible beyond its owner"):
        M.recorded_work_location("run-a")
    with pytest.raises(M.RegisterError, match="accessible beyond its owner"):
        M.assert_root_belongs_to_run(repo, "run-a", require_recorded=True)


def test_owned_columns_refuse_a_foreign_upsert(tmp_path: Path) -> None:
    with pytest.raises(M.RegisterError, match="written only by write_phase"):
        M.upsert_row(tmp_path, "child-1", {"phase": "working"}, run_id="run-a")
    with pytest.raises(M.RegisterError, match="written only by record_observed_tokens"):
        M.upsert_row(tmp_path, "child-1", {"tokens_observed": 1}, run_id="run-a")
    with pytest.raises(M.RegisterError, match="written only by commit_plan"):
        M.upsert_row(tmp_path, "child-1", {"tokens_max": 2}, run_id="run-a")
    stored = M.write_phase(tmp_path, "child-1", "working", run_id="run-a")
    assert stored["phase"] == "working"


def test_planned_cannot_replace_a_terminal_phase(tmp_path: Path) -> None:
    M.upsert_row(tmp_path, "child-1", {"phase": "reaped"}, run_id="run-a", writer="write_phase")
    with pytest.raises(M.RegisterError, match="refusing to write planned over a terminal phase"):
        M.write_phase(tmp_path, "child-1", "planned", run_id="run-a")


def test_artifact_path_refuses_a_foreign_writer(tmp_path: Path) -> None:
    with pytest.raises(M.RegisterError, match="written only by settle_artifact"):
        M.upsert_row(
            tmp_path,
            "child-1",
            {"artifact_path": "artifacts/child.json"},
            run_id="run-a",
        )
    stored = M.upsert_row(
        tmp_path,
        "child-1",
        {"artifact_path": "artifacts/child.json"},
        run_id="run-a",
        writer=M.ARTIFACT_PATH_WRITER,
    )
    assert stored["artifact_path"] == "artifacts/child.json"


def test_a_nonexistent_package_directory_stamps_the_repository(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _git_init(repo)
    future = repo / "packages" / "future-tool"
    M.upsert_row(future, "child-1", {"phase": "planned"}, run_id="run-a", writer="write_phase")
    stamped = json.loads(M.register_path("run-a").read_text())["repo_root"]
    assert Path(stamped).resolve() == repo.resolve()
    future.mkdir(parents=True)
    M.upsert_row(future, "child-1", {"phase": "working"}, run_id="run-a", writer="write_phase")
    assert M.read_rows(repo, run_id="run-a")["child-1"]["phase"] == "working"


def _git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "tests@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Tests"], cwd=repo, check=True)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
