"""Tests for the gate-divergence reader (issue #399).

Tests cover:

* **Zero-data contract** — an empty root reports "no data yet", never a fabricated 0%.
* **Per-gate rate** — a fixture set across >=2 gate ids produces the correct rubber-stamp rate
  and mean latency per gate id.
* **Read-only** — the reader never writes to the filesystem it scans.
* **CLI smoke** — ``--json`` against the committed fixture root emits valid JSON with a
  per-gate-id rate keyed by gate id (mirrors issue #399's own verification command).

Determinism / offline discipline: all tests construct envelope files inside ``tmp_path`` via
``saga.py``'s real ``save``/``encode_gate_divergence_entry`` so envelope format fidelity is
guaranteed; the reader is given the ``tmp_path`` root so the real ``.claude/saga/`` is never
read or written.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess  # nosec B404
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "plugins" / "saga" / "scripts"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "gate_divergence_sagas"


def _load_module(name: str) -> ModuleType:
    path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name.removesuffix(".py")] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def saga() -> ModuleType:
    return _load_module("saga.py")


@pytest.fixture(scope="module")
def gdr() -> ModuleType:
    """Loaded gate_divergence_reader module."""
    return _load_module("gate_divergence_reader.py")


_NOW = datetime(2026, 7, 4, 21, 0, 0, tzinfo=UTC)


def _write_saga(saga_mod: ModuleType, root: Path, saga_id: str, entries: list[str]) -> None:
    s = saga_mod.Saga(saga_id=saga_id, kind="task", id=saga_id, gate_divergence=entries)
    saga_mod.save(root, s, now=_NOW)


# ---------------------------------------------------------------------------
# Zero-data contract
# ---------------------------------------------------------------------------


def test_zero_data_reports_no_data_yet(gdr: ModuleType, tmp_path: Path) -> None:
    """An empty root reports no gates at all -- callers render 'no data yet', not 0%."""
    (tmp_path / ".claude" / "saga" / "sagas").mkdir(parents=True)
    summaries = gdr.read_gate_divergence(tmp_path)
    assert summaries == {}
    assert "no data yet" in gdr._render_text(summaries)


def test_zero_data_missing_sagas_dir(gdr: ModuleType, tmp_path: Path) -> None:
    """No .claude/saga/sagas/ directory at all -> same zero-data result."""
    summaries = gdr.read_gate_divergence(tmp_path)
    assert summaries == {}


# ---------------------------------------------------------------------------
# Per-gate rate
# ---------------------------------------------------------------------------


def test_per_gate_rate(saga: ModuleType, gdr: ModuleType, tmp_path: Path) -> None:
    """A fixture set across 2 gate ids produces the correct rubber-stamp rate per gate id."""
    _write_saga(
        saga,
        tmp_path,
        "task-1",
        [
            saga.encode_gate_divergence_entry("mode-select", "A", "A", False, 5.0),
            saga.encode_gate_divergence_entry("mode-select", "A", "B", True, 15.0),
        ],
    )
    _write_saga(
        saga,
        tmp_path,
        "task-2",
        [saga.encode_gate_divergence_entry("merge-confirm", "yes", "yes", False, None)],
    )
    summaries = gdr.read_gate_divergence(tmp_path)
    assert set(summaries) == {"mode-select", "merge-confirm"}
    assert summaries["mode-select"].interaction_count == 2
    assert summaries["mode-select"].rubber_stamp_rate == pytest.approx(0.5)
    assert summaries["mode-select"].mean_latency_seconds == pytest.approx(10.0)
    assert summaries["merge-confirm"].interaction_count == 1
    assert summaries["merge-confirm"].rubber_stamp_rate == pytest.approx(1.0)
    assert summaries["merge-confirm"].mean_latency_seconds is None


def test_malformed_entry_is_skipped_not_fatal(
    saga: ModuleType, gdr: ModuleType, tmp_path: Path
) -> None:
    """A corrupt gate_divergence entry is skipped rather than raising."""
    _write_saga(saga, tmp_path, "task-bad", ["not-valid-base64!!!"])
    summaries = gdr.read_gate_divergence(tmp_path)
    assert summaries == {}


# ---------------------------------------------------------------------------
# Read-only
# ---------------------------------------------------------------------------


def test_reader_is_read_only(saga: ModuleType, gdr: ModuleType, tmp_path: Path) -> None:
    """The reader never writes to disk -- no file under root changes after a run."""
    _write_saga(
        saga,
        tmp_path,
        "task-1",
        [saga.encode_gate_divergence_entry("g", "x", "x", False, 1.0)],
    )
    before = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in tmp_path.rglob("*") if p.is_file()}
    gdr.read_gate_divergence(tmp_path)
    after = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after


# ---------------------------------------------------------------------------
# CLI smoke against the committed fixture root (issue #399's own verification command)
# ---------------------------------------------------------------------------


def test_cli_json_against_committed_fixture() -> None:
    result = subprocess.run(  # nosec B603
        [
            sys.executable,
            str(SCRIPTS_DIR / "gate_divergence_reader.py"),
            "--root",
            str(FIXTURE_ROOT),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert len(payload) >= 2
    for gate_id, summary in payload.items():
        assert summary["gate_id"] == gate_id
        assert summary["interaction_count"] > 0


def test_cli_empty_root_reports_no_data_yet(tmp_path: Path) -> None:
    (tmp_path / ".claude" / "saga" / "sagas").mkdir(parents=True)
    result = subprocess.run(  # nosec B603
        [sys.executable, str(SCRIPTS_DIR / "gate_divergence_reader.py"), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "no data yet" in result.stdout
