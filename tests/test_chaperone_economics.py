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
    data: dict[str, object] = {
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


def test_divergence_intent_stays_distinct_and_unbatched() -> None:
    groups = C.group_same_engine_batches(
        [_unit("U1", intent="divergence"), _unit("U2", intent="divergence")]
    )

    assert [[unit.unit_id for unit in group] for group in groups] == [["U1"], ["U2"]]
    assert [group[0].intent for group in groups] == ["divergence", "divergence"]


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


def _offload_input(**overrides: object) -> object:
    data: dict[str, object] = {
        "engine_id": "codex",
        "cost_class": "metered",
        "estimated_external_cost_usd": 0.004,
        "provider_budget_ceiling_usd": 25.0,
        "prior_provider_spend_usd": 5.0,
        "claude_inline_tokens_estimate": 1_000,
        "chaperone_tokens_estimate": 200,
        "inline_fallback": "inline",
    }
    data.update(overrides)
    return C.OffloadEconomicsInput(**data)


def test_metered_offload_economics_proceeds_with_positive_net_savings() -> None:
    decision = C.decide_offload_economics(_offload_input())

    assert decision.status == "proceed"
    assert decision.proceed is True
    assert decision.net_savings.to_dict() == {
        "engine_tokens_avoided": 1000,
        "chaperone_tokens_spent": 200,
        "net_savings_tokens": 800,
        "net_savings_status": "positive",
        "external_cost_usd": 0.004,
    }
    assert decision.projected_provider_spend_usd == 5.004
    assert decision.preview == (
        "offload codex: save 800 tokens (inline 1000 - chaperone 200); "
        "external cost $0.0040; budget $5.0040/$25.0000"
    )


def test_free_class_offload_skips_break_even_and_ceiling_checks() -> None:
    decision = C.decide_offload_economics(
        _offload_input(
            engine_id="ollama-cloud",
            cost_class="free",
            estimated_external_cost_usd=None,
            provider_budget_ceiling_usd=None,
            claude_inline_tokens_estimate=None,
            chaperone_tokens_estimate=None,
        )
    )

    assert decision.status == "free-class-proceed"
    assert decision.proceed is True
    assert decision.net_savings.external_cost_usd == 0.0
    assert decision.net_savings.net_savings_status == "zero"
    assert decision.preview == (
        "offload ollama-cloud: free provider class; net 0 tokens, external cost $0.0000"
    )


def test_break_even_halt_uses_token_savings_only() -> None:
    decision = C.decide_offload_economics(
        _offload_input(claude_inline_tokens_estimate=1_000, chaperone_tokens_estimate=1_000)
    )

    assert decision.status == "break-even-halt"
    assert decision.proceed is False
    assert decision.net_savings.net_savings_status == "zero"
    assert decision.reason == "chaperone tokens 1000 >= inline tokens 1000"
    assert (
        decision.preview == "offload codex: halt; chaperone 1000 tokens >= inline 1000; use inline"
    )


def test_budget_ceiling_halt_uses_provider_spend_only() -> None:
    decision = C.decide_offload_economics(
        _offload_input(
            estimated_external_cost_usd=0.25,
            provider_budget_ceiling_usd=5.20,
            prior_provider_spend_usd=5.0,
        )
    )

    assert decision.status == "budget-ceiling-halt"
    assert decision.proceed is False
    assert decision.projected_provider_spend_usd == 5.25
    assert "exceeds ceiling $5.2000 by $0.0500" in decision.reason
    assert decision.preview == (
        "offload codex: halt; provider spend $5.2500/$5.2000 would exceed ceiling by $0.0500"
    )


def test_missing_metered_estimates_halt_without_exception() -> None:
    decision = C.decide_offload_economics(
        _offload_input(estimated_external_cost_usd=None, chaperone_tokens_estimate=None)
    )

    assert decision.status == "economics-missing-halt"
    assert decision.proceed is False
    assert decision.missing_fields == ("estimated_external_cost_usd", "chaperone_tokens_estimate")
    assert decision.net_savings.to_dict() == {
        "engine_tokens_avoided": 1000,
        "chaperone_tokens_spent": 0,
        "net_savings_tokens": 1000,
        "net_savings_status": "positive",
    }


def test_offload_economics_rejects_negative_estimates() -> None:
    with pytest.raises(C.ChaperonePolicyError, match="estimated_external_cost_usd"):
        _offload_input(estimated_external_cost_usd=-0.01)

    with pytest.raises(C.ChaperonePolicyError, match="chaperone_tokens_estimate"):
        _offload_input(chaperone_tokens_estimate=-1)


def test_offload_economics_preview_and_provenance_are_stable() -> None:
    input_data = _offload_input()

    first = C.decide_offload_economics(input_data)
    second = C.decide_offload_economics(input_data)

    assert first.preview == second.preview
    assert first.to_provenance() == second.to_provenance()
    assert first.to_provenance()["net_savings"]["net_savings_tokens"] == 800
