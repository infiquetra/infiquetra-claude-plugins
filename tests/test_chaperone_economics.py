"""Tests for Saga chaperone economics policy helpers (#381)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
HELPER_SCRIPT = SCRIPT_DIR / "chaperone_economics.py"


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


C = _load("chaperone_economics", HELPER_SCRIPT)


def _unit(unit_id: str, **overrides: object) -> object:
    data = {
        "unit_id": unit_id,
        "selector_kind": "engine",
        "selector": "codex/gpt-5.5-xhigh",
        "intent": "offload",
        "verifiability": "test-gated",
        "sandbox": "read-only",
        "write_mode": "no-write",
    }
    data.update(overrides)
    return C.ChaperoneUnit(**data)


def test_same_engine_offload_units_group_into_one_batch() -> None:
    groups = C.group_same_engine_batches([_unit("U1"), _unit("U2"), _unit("U3")])

    assert [[unit.unit_id for unit in group] for group in groups] == [["U1", "U2", "U3"]]

    decision = C.decide_batch(groups[0], sample_rating="STRONG", batch_id="batch-1")
    assert decision.batch_id == "batch-1"
    assert decision.review_mode == "ratify-only"
    assert decision.sample_fraction == 0.2
    assert decision.sampled_unit_ids == ("U1",)
    assert decision.full_review_unit_ids == ()


def test_mixed_engine_or_intent_units_do_not_share_batch() -> None:
    groups = C.group_same_engine_batches(
        [
            _unit("U1"),
            _unit("U2", selector="agy/gemini-3.1-pro-high"),
            _unit("U3", intent="second-opinion"),
        ]
    )

    assert [[unit.unit_id for unit in group] for group in groups] == [["U1"], ["U2"], ["U3"]]


def test_unverifiable_units_keep_full_review() -> None:
    decision = C.decide_batch([_unit("U1", verifiability="unverifiable")], sample_rating="STRONG")

    assert decision.review_mode == "full-review"
    assert decision.full_review_unit_ids == ("U1",)


@pytest.mark.parametrize(
    ("rating", "total", "expected"),
    [
        ("WEAK", 5, 5),
        ("MODERATE", 5, 3),
        ("MODERATE", 1, 1),
        ("STRONG", 5, 1),
        ("STRONG", 11, 3),
    ],
)
def test_sample_count_mapping_is_pinned(rating: str, total: int, expected: int) -> None:
    assert C.sample_count(total, rating) == expected


def test_sampled_defect_escalates_unsampled_units_to_full_review() -> None:
    decision = C.decide_batch(
        [_unit("U1"), _unit("U2"), _unit("U3"), _unit("U4"), _unit("U5")],
        sample_rating="STRONG",
        batch_id="batch-1",
    )

    escalated = C.with_sample_result(decision, ["U1"])

    assert escalated.defective_sample_unit_ids == ("U1",)
    assert escalated.full_review_unit_ids == ("U2", "U3", "U4", "U5")


def test_unknown_verifiability_or_rating_fails_loudly() -> None:
    with pytest.raises(C.ChaperonePolicyError, match="verifiability"):
        _unit("U1", verifiability="maybe")

    with pytest.raises(C.ChaperonePolicyError, match="sample rating"):
        C.sample_count(3, "OK")


def test_escalation_thresholds_and_provenance_are_serializable() -> None:
    decision = C.decide_batch(
        [_unit("U1", evidence_bytes=40_000)],
        sample_rating="STRONG",
        batch_id="batch-1",
        cache_status="hit",
    )

    provenance = decision.to_provenance()

    assert provenance["escalation_recommended"] is True
    assert "evidence_bytes 40000 exceeds threshold" in provenance["escalation_reason"]
    assert provenance["cache_status"] == "hit"
    assert provenance["unit_ids"] == ["U1"]
    assert provenance["selector"] == {"kind": "engine", "value": "codex/gpt-5.5-xhigh"}
