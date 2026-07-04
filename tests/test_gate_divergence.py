"""Tests for the ``gate_divergence`` saga field and its encode/parse helpers (issue #399).

Tests cover:

* **Record** — a gate interaction appends a correctly-shaped ``gate_divergence`` entry.
* **Divergence bit** — ``true`` when the answer differs from the offered default, ``false``
  when it matches (computed by the caller before encoding, per KTD3).
* **Pipe-in-answer regression** — an answer containing a literal ``|`` survives the round trip
  (the corruption mode identified during doc-review, KTD1).
* **Round-trip** — multiple entries across two distinct gate ids survive save -> parse
  byte-identical.
* **Malformed entry** — ``parse_gate_divergence_entry`` raises ``ValueError`` on bad base64,
  bad JSON, or a missing required key.

Determinism / offline discipline: engine tests pass ``root=tmp_path`` and a fixed ``now`` so
nothing depends on the real filesystem, clock, or network.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "plugins" / "saga" / "scripts"


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
def saga(request: pytest.FixtureRequest) -> ModuleType:
    """Loaded saga engine module."""
    return _load_module("saga.py")


_NOW = datetime(2026, 7, 4, 21, 0, 0, tzinfo=UTC)


def test_records_interaction(saga: ModuleType, tmp_path: Path) -> None:
    """A gate interaction round-trips through save/parse without dropping the entry."""
    entry = saga.encode_gate_divergence_entry("mode-select", "A", "A", False, 5.0)
    s = saga.Saga(saga_id="task-gd-1", kind="task", id="gd-1", gate_divergence=[entry])
    saga.save(tmp_path, s, now=_NOW)

    restored = saga.restore(tmp_path, "task-gd-1")
    assert restored is not None
    assert len(restored.gate_divergence) == 1
    parsed = saga.parse_gate_divergence_entry(restored.gate_divergence[0])
    assert parsed["gate_id"] == "mode-select"
    assert parsed["offered"] == "A"
    assert parsed["answer"] == "A"
    assert parsed["divergence"] is False
    assert parsed["latency_seconds"] == 5.0


def test_divergence_bit(saga: ModuleType) -> None:
    """divergence is true when answer != offered, false when equal."""
    matching = saga.parse_gate_divergence_entry(
        saga.encode_gate_divergence_entry("g", "A", "A", False)
    )
    diverging = saga.parse_gate_divergence_entry(
        saga.encode_gate_divergence_entry("g", "A", "B", True)
    )
    assert matching["divergence"] is False
    assert diverging["divergence"] is True


def test_pipe_in_answer_survives(saga: ModuleType, tmp_path: Path) -> None:
    """An answer containing a literal '|' round-trips intact (KTD1 regression)."""
    tricky_answer = "fix it | ship as-is"
    entry = saga.encode_gate_divergence_entry("g", "offered", tricky_answer, True, None)
    s = saga.Saga(saga_id="task-gd-pipe", kind="task", id="gd-pipe", gate_divergence=[entry])
    saga.save(tmp_path, s, now=_NOW)

    restored = saga.restore(tmp_path, "task-gd-pipe")
    assert restored is not None
    assert len(restored.gate_divergence) == 1
    parsed = saga.parse_gate_divergence_entry(restored.gate_divergence[0])
    assert parsed["answer"] == tricky_answer


def test_roundtrip(saga: ModuleType, tmp_path: Path) -> None:
    """Multiple entries across two distinct gate ids survive save -> parse byte-identical."""
    entries = [
        saga.encode_gate_divergence_entry("gate-a", "x", "x", False, 1.0),
        saga.encode_gate_divergence_entry("gate-a", "x", "y", True, 2.5),
        saga.encode_gate_divergence_entry("gate-b", "z", "z", False, None),
    ]
    s = saga.Saga(saga_id="task-gd-multi", kind="task", id="gd-multi", gate_divergence=entries)
    saga.save(tmp_path, s, now=_NOW)

    restored = saga.restore(tmp_path, "task-gd-multi")
    assert restored is not None
    assert list(restored.gate_divergence) == entries


def test_second_save_replaces_not_accumulates(saga: ModuleType, tmp_path: Path) -> None:
    """A second save() on the same saga id REPLACES gate_divergence, never appends to it.

    Full-snapshot list semantics (matching gate_verdicts) mean each tick carries the complete
    current list, not a delta -- a caller that forgot this and expected accumulation would be
    silently wrong about how many interactions were recorded.
    """
    first_entry = saga.encode_gate_divergence_entry("g", "x", "x", False, 1.0)
    s1 = saga.Saga(
        saga_id="task-gd-replace", kind="task", id="gd-replace", gate_divergence=[first_entry]
    )
    saga.save(tmp_path, s1, now=_NOW)

    second_entry = saga.encode_gate_divergence_entry("g", "y", "z", True, 2.0)
    s2 = saga.Saga(
        saga_id="task-gd-replace", kind="task", id="gd-replace", gate_divergence=[second_entry]
    )
    saga.save(tmp_path, s2, now=_NOW)

    restored = saga.restore(tmp_path, "task-gd-replace")
    assert restored is not None
    assert list(restored.gate_divergence) == [second_entry]


def test_encode_empty_string_answer(saga: ModuleType) -> None:
    """An empty-string answer (operator hit Enter with no free text) round-trips cleanly."""
    entry = saga.encode_gate_divergence_entry("g", "recommended", "", True, None)
    parsed = saga.parse_gate_divergence_entry(entry)
    assert parsed["answer"] == ""
    assert parsed["divergence"] is True


def test_encode_unicode_answer(saga: ModuleType) -> None:
    """Unicode text in offered/answer round-trips without mangling."""
    entry = saga.encode_gate_divergence_entry("g", "選択肢A", "選択肢A ✅ — café", False, 3.0)
    parsed = saga.parse_gate_divergence_entry(entry)
    assert parsed["offered"] == "選択肢A"
    assert parsed["answer"] == "選択肢A ✅ — café"


def test_encode_negative_latency(saga: ModuleType) -> None:
    """A negative latency (e.g. from clock skew) is preserved, not rejected or clamped."""
    entry = saga.encode_gate_divergence_entry("g", "x", "x", False, -1.5)
    parsed = saga.parse_gate_divergence_entry(entry)
    assert parsed["latency_seconds"] == -1.5


def test_parse_rejects_bad_base64(saga: ModuleType) -> None:
    with pytest.raises(ValueError, match="not valid base64"):
        saga.parse_gate_divergence_entry("not-valid-base64!!!")


def test_parse_rejects_bad_json(saga: ModuleType) -> None:
    import base64

    bad = base64.b64encode(b"not json").decode("ascii")
    with pytest.raises(ValueError, match="invalid JSON"):
        saga.parse_gate_divergence_entry(bad)


def test_parse_rejects_deeply_nested_json_without_crashing(saga: ModuleType) -> None:
    """A maliciously deep-nested JSON payload raises ValueError, not an uncaught RecursionError.

    json.loads on ~200k levels of nesting raises RecursionError rather than JSONDecodeError;
    left uncaught this would crash gate_divergence_reader.py's main() on a single corrupt
    envelope instead of skipping that entry (security-lens finding).
    """
    import base64

    hostile = "[" * 200_000 + "]" * 200_000
    bad = base64.b64encode(hostile.encode("utf-8")).decode("ascii")
    with pytest.raises(ValueError, match="invalid JSON"):
        saga.parse_gate_divergence_entry(bad)


def test_parse_rejects_missing_required_key(saga: ModuleType) -> None:
    import base64
    import json

    blob = json.dumps({"gate_id": "g", "offered": "x"})  # missing answer/divergence
    bad = base64.b64encode(blob.encode("utf-8")).decode("ascii")
    with pytest.raises(ValueError, match="missing required key"):
        saga.parse_gate_divergence_entry(bad)
