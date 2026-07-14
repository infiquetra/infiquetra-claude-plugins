"""Tests for the golden-fixture drift checker (#458, T11-F1-6).

Pins the acceptance criterion: deleting or mutating a fake's golden fixture is flagged by
``scripts/check_fake_fixtures.py``. Tests run against an isolated copy of the manifest + golden in
``tmp_path`` so they never touch the committed fixtures.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"


def _load_checker() -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "check_fake_fixtures", SCRIPTS / "check_fake_fixtures.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: dataclass processing looks __module__ up in sys.modules (py3.12+).
    sys.modules["check_fake_fixtures"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def checker() -> ModuleType:
    return _load_checker()


def _seed_golden(tmp_path: Path, content: str = "worktree <ROOT>/repo\nHEAD <SHA>\n") -> Path:
    """Write an isolated golden + a manifest pinning its real hash; return the manifest path."""
    import hashlib

    golden_rel = "tests/fixtures/golden/worktree_list_porcelain.golden.txt"
    golden = tmp_path / golden_rel
    golden.parent.mkdir(parents=True, exist_ok=True)
    golden.write_text(content, encoding="utf-8")
    sha = hashlib.sha256(content.encode()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "goldens": [
                    {
                        "fake": "worktree-liveness-oracle",
                        "producer": "git worktree list --porcelain",
                        "path": str(golden),  # absolute so the checker resolves it in tmp
                        "sha256": sha,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_check_passes_when_golden_matches(checker: ModuleType, tmp_path: Path) -> None:
    manifest = _seed_golden(tmp_path)
    assert checker.check_goldens(manifest) == []


def test_golden_drift_mutated_is_flagged(checker: ModuleType, tmp_path: Path) -> None:
    """A golden mutated away from its pinned hash is flagged as drift."""
    manifest = _seed_golden(tmp_path)
    golden = Path(json.loads(manifest.read_text())["goldens"][0]["path"])
    golden.write_text("worktree <ROOT>/repo\nHEAD <SHA>\nMUTATED\n", encoding="utf-8")

    drifts = checker.check_goldens(manifest)
    assert len(drifts) == 1
    assert drifts[0].kind == "mutated"


def test_golden_drift_deleted_is_flagged(checker: ModuleType, tmp_path: Path) -> None:
    """A deleted golden is flagged as drift."""
    manifest = _seed_golden(tmp_path)
    golden = Path(json.loads(manifest.read_text())["goldens"][0]["path"])
    golden.unlink()

    drifts = checker.check_goldens(manifest)
    assert len(drifts) == 1
    assert drifts[0].kind == "deleted"


def test_golden_drift_strict_exit_nonzero(checker: ModuleType, tmp_path: Path) -> None:
    """The CLI exits non-zero on drift by default, and 0 under --advisory."""
    manifest = _seed_golden(tmp_path)
    golden = Path(json.loads(manifest.read_text())["goldens"][0]["path"])
    golden.write_text("drifted\n", encoding="utf-8")

    assert checker.main(["--manifest", str(manifest)]) == 1
    assert checker.main(["--manifest", str(manifest), "--advisory"]) == 0


def test_committed_golden_matches_real_producer(checker: ModuleType) -> None:
    """The shipped golden is byte-identical to a fresh capture of the real producer.

    This is the 'derived from the real producer' guarantee: the committed golden is not a
    hand-crafted fixture but exactly what real ``git worktree list --porcelain`` emits (normalized).
    """
    committed = (ROOT / "tests/fixtures/golden/worktree_list_porcelain.golden.txt").read_text(
        encoding="utf-8"
    )
    assert checker.capture_worktree_porcelain() == committed


def test_committed_manifest_is_in_sync(checker: ModuleType) -> None:
    """The committed manifest's pinned hash matches the committed golden (no un-regenerated drift)."""
    assert checker.check_goldens(checker.DEFAULT_MANIFEST) == []
