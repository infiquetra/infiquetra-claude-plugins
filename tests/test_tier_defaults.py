"""Tests for persisted per-repo tier preferences (#368, AC1-AC4 + AC6-AC7)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"

# Registry defaults this suite pins against (tier_policy.json): mechanical -> sonnet/medium.
MECHANICAL_REGISTRY = {"model": "sonnet", "effort": "medium"}


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


TD = _load("tier_defaults", SCRIPT_DIR / "tier_defaults.py")


def _write_defaults(root: Path, data: object) -> Path:
    path = root / ".saga" / "tier-defaults.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")
    return path


def test_tier_defaults_overlay_precedence(tmp_path: Path) -> None:  # AC1
    _write_defaults(tmp_path, {"mechanical": {"model": "opus", "effort": "high"}})
    assert TD.resolve_tier_with_overlay("mechanical", root=tmp_path) == {
        "model": "opus",
        "effort": "high",
    }
    # The overlay overrode the registry's sonnet/medium for the same shape.
    assert TD.resolve_tier_with_overlay("mechanical", root=tmp_path) != MECHANICAL_REGISTRY


def test_tier_defaults_writeback(tmp_path: Path) -> None:  # AC2
    _write_defaults(tmp_path, {"judgment": {"model": "opus", "effort": "high"}})
    TD.write_tier_default("mechanical", "haiku", "low", root=tmp_path)
    got = TD.load_tier_defaults(root=tmp_path)
    assert got["mechanical"] == {"model": "haiku", "effort": "low"}
    assert got["judgment"] == {"model": "opus", "effort": "high"}  # unrelated key not clobbered


def test_tier_defaults_second_run_reuse(tmp_path: Path) -> None:  # AC3
    # First run confirms an override; a fresh resolve returns it (not re-derived).
    TD.write_tier_default("mechanical", "opus", "high", root=tmp_path)
    assert TD.resolve_tier_with_overlay("mechanical", root=tmp_path) == {
        "model": "opus",
        "effort": "high",
    }


def test_tier_defaults_malformed(tmp_path: Path) -> None:  # AC4
    # Missing -> clean registry fallback, no error.
    assert TD.resolve_tier_with_overlay("mechanical", root=tmp_path) == MECHANICAL_REGISTRY
    # Bad JSON -> raise.
    _write_defaults(tmp_path, "{not json")
    with pytest.raises(TD.TierDefaultsError):
        TD.load_tier_defaults(root=tmp_path)
    # Unknown work-shape -> raise.
    _write_defaults(tmp_path, {"nonsense-shape": {"model": "opus", "effort": "high"}})
    with pytest.raises(TD.TierDefaultsError, match="unknown work-shape"):
        TD.load_tier_defaults(root=tmp_path)
    # Off-palette / unrunnable -> raise.
    _write_defaults(tmp_path, {"mechanical": {"model": "haiku", "effort": "xhigh"}})
    with pytest.raises(TD.TierDefaultsError):
        TD.load_tier_defaults(root=tmp_path)


def test_tier_band_prefill_from_issue(tmp_path: Path) -> None:  # AC6
    band = {"model": "opus", "effort": "high"}
    # No repo override -> the issue band seeds the tier (over the registry default).
    assert TD.resolve_tier_for_plan("mechanical", issue_band=band, root=tmp_path) == band
    # No band, no override -> registry default.
    assert (
        TD.resolve_tier_for_plan("mechanical", issue_band=None, root=tmp_path)
        == MECHANICAL_REGISTRY
    )


def test_tier_defaults_vs_issue_band_precedence(tmp_path: Path) -> None:  # AC7
    _write_defaults(tmp_path, {"mechanical": {"model": "haiku", "effort": "low"}})
    band = {"model": "opus", "effort": "high"}
    # Repo override wins over the coarser issue band.
    assert TD.resolve_tier_for_plan("mechanical", issue_band=band, root=tmp_path) == {
        "model": "haiku",
        "effort": "low",
    }


# --- Issue-carried band parsing (#368 AC5/AC6 producer→consumer) ------------

MC_SCRIPT_DIR = ROOT / "plugins" / "mission-control" / "scripts"


def test_parse_tier_band_roundtrip(tmp_path: Path) -> None:
    """The band mission-control stamps is the band saga parses (format contract)."""
    if str(MC_SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(MC_SCRIPT_DIR))
    sdlc_manager = _load("sdlc_manager_for_band_roundtrip", MC_SCRIPT_DIR / "sdlc_manager.py")
    body = sdlc_manager._source_to_issue_body(
        "Fix the flaky retry loop", "defect", "campps", "infiquetra/widgets", None, None
    )
    band = TD.parse_tier_band(body)
    assert band == {"model": "opus", "effort": "high"}
    # And the parsed band feeds the precedence resolver (no overlay -> band wins).
    assert TD.resolve_tier_for_plan("mechanical", issue_band=band, root=tmp_path) == band


def test_parse_tier_band_absent() -> None:
    assert TD.parse_tier_band("### Objective\nDo the thing\n") is None
    assert TD.parse_tier_band("") is None


def test_parse_tier_band_invalid() -> None:
    # Present but unparseable value -> loud.
    with pytest.raises(TD.TierDefaultsError, match="model/effort"):
        TD.parse_tier_band("### Recommended Tier Band\nwhatever\n")
    # Off-palette model -> loud.
    with pytest.raises(TD.TierDefaultsError, match="not in"):
        TD.parse_tier_band("### Recommended Tier Band\ngpt/high\n")
    # On-palette but unrunnable pair -> loud.
    with pytest.raises(TD.TierDefaultsError, match="unrunnable"):
        TD.parse_tier_band("### Recommended Tier Band\nhaiku/xhigh\n")
    # Empty section (header present, no value) -> loud, it claims to be a band.
    with pytest.raises(TD.TierDefaultsError):
        TD.parse_tier_band("### Recommended Tier Band\n\n### Next Section\nx\n")


def test_parse_tier_band_fence_and_duplicate_hardening() -> None:
    """Verifier P1: only a real unfenced H3 header is a band; duplicates fail loud."""
    # Header text inside a fenced code block is NOT a band (e.g. Verification example output).
    fenced = "### Verification\n```\n### Recommended Tier Band\nopus/high\n```\n"
    assert TD.parse_tier_band(fenced) is None
    # A mid-line prose mention is not a header either.
    prose = "### Objective\nDocument the ### Recommended Tier Band feature.\n"
    assert TD.parse_tier_band(prose) is None
    # A fenced mention beside ONE real header parses the real one.
    both = fenced + "\n### Recommended Tier Band\nsonnet/medium\n"
    assert TD.parse_tier_band(both) == {"model": "sonnet", "effort": "medium"}
    # Two REAL headers is an ambiguous claim -> loud.
    dup = "### Recommended Tier Band\nopus/high\n\n### Recommended Tier Band\nsonnet/low\n"
    with pytest.raises(TD.TierDefaultsError, match="expected one"):
        TD.parse_tier_band(dup)
