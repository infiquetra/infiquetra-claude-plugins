"""Tests for the session-local tier override (#365 U1)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TS = _load("tier_session", SCRIPT_DIR / "tier_session.py")


def test_tier_ceiling_write(tmp_path: Path) -> None:
    TS.set_ceiling("sonnet", "medium", root=tmp_path)
    data = TS.read_session_override(root=tmp_path)
    assert data["ceiling"] == {"model": "sonnet", "effort": "medium"}
    assert data["unit_overrides"] == {}
    # File lands under the git-ignored saga cache dir.
    assert (tmp_path / ".claude/saga/tier-session-override.json").exists()


def test_tier_session_unit_override_round_trip(tmp_path: Path) -> None:
    TS.set_unit_override("U3", "opus", "high", root=tmp_path)
    data = TS.read_session_override(root=tmp_path)
    assert data["unit_overrides"]["U3"] == {"model": "opus", "effort": "high"}


def test_tier_session_off_palette_rejected(tmp_path: Path) -> None:
    with pytest.raises(TS.TierSessionError, match="not in"):
        TS.set_ceiling("gpt-5", "medium", root=tmp_path)
    with pytest.raises(TS.TierSessionError, match="not in"):
        TS.set_unit_override("U1", "sonnet", "turbo", root=tmp_path)


def test_tier_session_unrunnable_rejected(tmp_path: Path) -> None:
    # #365 gate P0: an on-palette-but-unrunnable tier (haiku's ceiling is high) is rejected loudly, so
    # it can never be clamped-to and rendered into an emitted artifact.
    with pytest.raises(TS.TierSessionError, match="unrunnable"):
        TS.set_ceiling("haiku", "xhigh", root=tmp_path)
    with pytest.raises(TS.TierSessionError, match="unrunnable"):
        TS.set_unit_override("U1", "haiku", "xhigh", root=tmp_path)


def test_tier_session_absent_is_empty(tmp_path: Path) -> None:
    assert TS.read_session_override(root=tmp_path) == {"ceiling": None, "unit_overrides": {}}


def test_tier_session_clear(tmp_path: Path) -> None:
    TS.set_ceiling("haiku", "low", root=tmp_path)
    assert TS.clear(root=tmp_path) is True
    assert TS.clear(root=tmp_path) is False  # idempotent
    assert TS.read_session_override(root=tmp_path)["ceiling"] is None
