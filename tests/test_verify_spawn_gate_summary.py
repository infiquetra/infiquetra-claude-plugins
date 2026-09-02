"""Unit tests for the pure verify-panel fallback-tier gate-summary render helper (#390 U6, R8).

``render_fallback_tier_marker`` is deliberately a pure function so the "fallback tier N" marker
formatting is testable in isolation, with no workflow emission. The #325 fallback ladder itself is
untouched by this attribution wiring (binding decision {#readonly-verifier-fallback-ladder-325}).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

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
# The helper moved to the cc-workflows plugin with the emission path (#925/U4); it
# reuses the execution_spec module registered above for the spec schema.
_EMITTER_PATH = (
    ROOT / "plugins" / "cc-workflows" / "skills" / "cc-workflows" / "scripts" / "emitter.py"
)
_emitter_spec = importlib.util.spec_from_file_location("cc_workflows_emitter", _EMITTER_PATH)
assert _emitter_spec is not None and _emitter_spec.loader is not None
EMITTER = importlib.util.module_from_spec(_emitter_spec)
sys.modules["cc_workflows_emitter"] = EMITTER
_emitter_spec.loader.exec_module(EMITTER)


def test_fallback_tier_2_rendered() -> None:
    # A reporter that descended to rung 2 (general-purpose) renders an explicit tier-2 marker
    # naming the degraded agent identity.
    marker = EMITTER.render_fallback_tier_marker(
        [{"verifier_identity": "general-purpose", "fallback_depth": 2}]
    )
    assert "fallback tier 2" in marker
    assert "general-purpose" in marker


def test_no_fallback_marker_on_first_choice() -> None:
    # Every reporter sat on the first-choice saga:readonly-verifier rung (depth 0) => no marker.
    marker = EMITTER.render_fallback_tier_marker(
        [
            {"verifier_identity": "saga:readonly-verifier", "fallback_depth": 0},
            {"verifier_identity": "saga:readonly-verifier", "fallback_depth": 0},
        ]
    )
    assert marker == ""


def test_mixed_panel_names_only_the_degraded_reporter() -> None:
    # One rung-2 reporter among rung-0 reporters => the marker fires and names ONLY the degraded
    # reporter, never the first-choice ones.
    marker = EMITTER.render_fallback_tier_marker(
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
    assert (
        EMITTER.render_fallback_tier_marker([{"verifier_identity": "saga:readonly-verifier"}]) == ""
    )


def test_missing_identity_falls_back_to_placeholder() -> None:
    marker = EMITTER.render_fallback_tier_marker([{"fallback_depth": 1}])
    assert "fallback tier 1" in marker
    assert "unknown-verifier" in marker


def test_empty_panel_renders_no_marker() -> None:
    assert EMITTER.render_fallback_tier_marker([]) == ""


@pytest.mark.parametrize(
    ("raw_depth", "expected"),
    [
        pytest.param(True, "", id="bool-true-clamps-to-zero"),
        pytest.param("not-a-number", "", id="unparseable-string-clamps-to-zero"),
        pytest.param(None, "", id="none-clamps-to-zero"),
        pytest.param("2.7", "", id="decimal-string-clamps-to-zero"),
        pytest.param(-1, "", id="negative-clamps-to-zero"),
        pytest.param(2.7, "fallback tier 2", id="float-truncates"),
        pytest.param("3", "fallback tier 3", id="integer-string-parses"),
    ],
)
def test_malformed_fallback_depth_defensive_clamp(raw_depth: object, expected: str) -> None:
    """The defensive-coercion branches (#390 review F4): malformed depths from a degraded
    reporter's verdict clamp to 0 (no marker) rather than crashing or rendering junk; the
    emitted JS marker mirrors this exact coercion table."""
    marker = EMITTER.render_fallback_tier_marker(
        [{"verifier_identity": "explore", "fallback_depth": raw_depth}]
    )
    if expected:
        assert expected in marker
    else:
        assert marker == ""
