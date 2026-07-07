"""Unit tests for the pure verify-panel fallback-tier gate-summary render helper (#390 U6, R8).

``render_fallback_tier_marker`` is deliberately a pure function so the "fallback tier N" marker
formatting is testable in isolation, with no workflow emission. The #325 fallback ladder itself is
untouched by this attribution wiring (binding decision {#readonly-verifier-fallback-ladder-325}).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
_SPEC_PATH = SCRIPT_DIR / "execution_spec.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
_spec = importlib.util.spec_from_file_location("execution_spec", _SPEC_PATH)
assert _spec is not None and _spec.loader is not None
ES = importlib.util.module_from_spec(_spec)
sys.modules["execution_spec"] = ES
_spec.loader.exec_module(ES)


def test_fallback_tier_2_rendered() -> None:
    # A reporter that descended to rung 2 (general-purpose) renders an explicit tier-2 marker
    # naming the degraded agent identity.
    marker = ES.render_fallback_tier_marker(
        [{"verifier_identity": "general-purpose", "fallback_depth": 2}]
    )
    assert "fallback tier 2" in marker
    assert "general-purpose" in marker


def test_no_fallback_marker_on_first_choice() -> None:
    # Every reporter sat on the first-choice saga:readonly-verifier rung (depth 0) => no marker.
    marker = ES.render_fallback_tier_marker(
        [
            {"verifier_identity": "saga:readonly-verifier", "fallback_depth": 0},
            {"verifier_identity": "saga:readonly-verifier", "fallback_depth": 0},
        ]
    )
    assert marker == ""


def test_mixed_panel_names_only_the_degraded_reporter() -> None:
    # One rung-2 reporter among rung-0 reporters => the marker fires and names ONLY the degraded
    # reporter, never the first-choice ones.
    marker = ES.render_fallback_tier_marker(
        [
            {"verifier_identity": "saga:readonly-verifier", "fallback_depth": 0},
            {"verifier_identity": "general-purpose", "fallback_depth": 2},
            {"verifier_identity": "saga:readonly-verifier", "fallback_depth": 0},
        ]
    )
    assert "fallback tier 2" in marker
    assert "general-purpose" in marker
    assert "saga:readonly-verifier" not in marker


def test_missing_fallback_depth_defaults_to_zero() -> None:
    # A verdict that omits fallback_depth entirely is treated as depth 0 (no marker).
    assert ES.render_fallback_tier_marker([{"verifier_identity": "saga:readonly-verifier"}]) == ""


def test_missing_identity_falls_back_to_placeholder() -> None:
    marker = ES.render_fallback_tier_marker([{"fallback_depth": 1}])
    assert "fallback tier 1" in marker
    assert "unknown-verifier" in marker


def test_empty_panel_renders_no_marker() -> None:
    assert ES.render_fallback_tier_marker([]) == ""
