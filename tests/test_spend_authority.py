"""Tests for #367 U4: the .saga/spend-authority.json resolver.

Covers `-k spend_authority_matrix` and `-k spend_authority_absent_default`, plus the exhaustive grid
guard that pins `_above_ceiling` to `execution_spec.is_escalation` so the two levers cannot drift (KTD5).
"""

from __future__ import annotations

import importlib.util
import json
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
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SA = _load("spend_authority", SCRIPT_DIR / "spend_authority.py")
ES = _load("execution_spec", SCRIPT_DIR / "execution_spec.py")


def _write_matrix(root: Path, model: str, effort: str) -> None:
    (root / ".saga").mkdir(parents=True, exist_ok=True)
    (root / ".saga" / "spend-authority.json").write_text(
        json.dumps({"silent_ceiling": {"model": model, "effort": effort}}), encoding="utf-8"
    )


def test_spend_authority_matrix(tmp_path: Path) -> None:
    # silent_ceiling = opus/high: opus/high and below -> silent; stronger on either axis -> ask.
    _write_matrix(tmp_path, "opus", "high")
    ceiling = SA.load_spend_authority(tmp_path)
    assert SA.resolve_spend_authority({"model": "opus", "effort": "high"}, ceiling) == "silent"
    assert SA.resolve_spend_authority({"model": "sonnet", "effort": "medium"}, ceiling) == "silent"
    assert SA.resolve_spend_authority({"model": "fable", "effort": "high"}, ceiling) == "ask"
    assert SA.resolve_spend_authority({"model": "opus", "effort": "xhigh"}, ceiling) == "ask"


def test_spend_authority_absent_default(tmp_path: Path) -> None:
    # No file -> safe default silent_ceiling = sonnet/high; any premium tier (opus/fable / xhigh) -> ask.
    ceiling = SA.load_spend_authority(tmp_path)
    assert ceiling == {"model": "sonnet", "effort": "high"}
    assert SA.resolve_spend_authority({"model": "opus", "effort": "high"}, ceiling) == "ask"
    assert SA.resolve_spend_authority({"model": "opus", "effort": "low"}, ceiling) == "ask"
    assert SA.resolve_spend_authority({"model": "sonnet", "effort": "xhigh"}, ceiling) == "ask"
    assert SA.resolve_spend_authority({"model": "sonnet", "effort": "high"}, ceiling) == "silent"
    assert SA.resolve_spend_authority({"model": "sonnet", "effort": "medium"}, ceiling) == "silent"
    assert SA.resolve_spend_authority({"model": "haiku", "effort": "low"}, ceiling) == "silent"


def test_spend_authority_absent_default_no_ceiling_arg(tmp_path: Path) -> None:
    # resolve_spend_authority loads the default itself when no ceiling is passed.
    assert SA.resolve_spend_authority({"model": "opus", "effort": "high"}, root=tmp_path) == "ask"
    assert (
        SA.resolve_spend_authority({"model": "haiku", "effort": "low"}, root=tmp_path) == "silent"
    )


def test_spend_authority_malformed_fails_loud(tmp_path: Path) -> None:
    _write_matrix(tmp_path, "gpt5", "high")  # off-palette model
    with pytest.raises(SA.SpendAuthorityError, match="not in"):
        SA.load_spend_authority(tmp_path)
    _write_matrix(tmp_path, "haiku", "xhigh")  # unrunnable tier
    with pytest.raises(SA.SpendAuthorityError, match="unrunnable"):
        SA.load_spend_authority(tmp_path)
    (tmp_path / ".saga" / "spend-authority.json").write_text("not json{", encoding="utf-8")
    with pytest.raises(SA.SpendAuthorityError, match="not valid JSON"):
        SA.load_spend_authority(tmp_path)
    (tmp_path / ".saga" / "spend-authority.json").write_text('{"nope": 1}', encoding="utf-8")
    with pytest.raises(SA.SpendAuthorityError, match="silent_ceiling"):
        SA.load_spend_authority(tmp_path)


def test_spend_authority_above_matches_is_escalation() -> None:
    """Exhaustive grid: _above_ceiling(tier, ceiling) == is_escalation(ceiling, tier) (KTD5)."""
    for m1 in SA.MODELS:
        for e1 in SA.EFFORTS:
            for m2 in SA.MODELS:
                for e2 in SA.EFFORTS:
                    ceiling = {"model": m1, "effort": e1}
                    tier = {"model": m2, "effort": e2}
                    expected = ES.is_escalation(
                        ES.Tier(model=m1, effort=e1), ES.Tier(model=m2, effort=e2)
                    )
                    assert SA._above_ceiling(tier, ceiling) == expected
