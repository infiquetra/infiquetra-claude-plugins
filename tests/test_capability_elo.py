"""Elo updater and fallback-prior resolution tests (#459 R4/AE4)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CE = _load("capability_elo")
EC = _load("engine_calibration")
RES = _load("engine_resolver")
REG = _load("engine_registry")
RC = CE.reconcile
RL = CE.run_ledger


def _row(engine_id: str, *, cost_speed_rank: int = 3) -> dict[str, Any]:
    return {
        "engine_id": engine_id,
        "variant": "default",
        "substrate": "external",
        "egress_policy": "networked",
        "trust_tier": "advisory",
        "default_for_engine": True,
        "invocation": {
            "via": f"{engine_id}:delegate",
            "recipe": f"{engine_id} delegate --mode no-write",
            "write_capable": False,
        },
        "context_window": 100_000,
        "cost_speed_rank": cost_speed_rank,
        "cost_per_token": {"input_usd": 0.0, "output_usd": 0.0},
        "cost_class": "free",
        "latency_class": "standard",
        "model_identity": f"{engine_id}-default",
        "last_validated": "2026-06-01",
        "receipt_emitter": f"{engine_id}-bridge",
        "capability_profile": {"second-opinion": {"rating": "MODERATE", "note": "fixture"}},
        "prompting_protocol": [f"Use {engine_id} for advisory output only."],
        "sources": [{"claim": "fixture", "url": "https://example.invalid", "date": "2026-06-01"}],
    }


def _registry_path(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    data = {"capabilities": list(REG.CAPABILITIES), "engines": rows, "roles": {}}
    path = tmp_path / "engine-registry.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _ledger(tmp_path: Path) -> Any:
    return RL.RunLedger(path=tmp_path / "run-facts.jsonl")


def _panel_result(index: int, *, a_status: Any, b_status: Any) -> Any:
    return RC.build_result(
        reconciliation_id=f"recon-{index}",
        execution_id=f"exec-{index}",
        intent="second-opinion",
        adjudicator_id="claude/opus",
        source_finding_ids=("finding-a", "finding-b"),
        items=(
            RC.ReconciliationItem(
                source_finding_id="finding-a",
                status=a_status,
                adjudicator_id="claude/opus",
                rationale="Claude adjudicated member A's finding.",
            ),
            RC.ReconciliationItem(
                source_finding_id="finding-b",
                status=b_status,
                adjudicator_id="claude/opus",
                rationale="Claude adjudicated member B's finding.",
            ),
        ),
    )


def _seed_five_losses(ledger: Any) -> None:
    """Provider A's findings are all dropped; B's all reconciled — five reconciliations."""
    member_index = {"finding-a": ["enga/default"], "finding-b": ["engb/default"]}
    for index in range(5):
        RC.append_reconciliation_fact(
            ledger,
            _panel_result(
                index,
                a_status=RC.ReconciliationStatus.DROPPED,
                b_status=RC.ReconciliationStatus.RECONCILED,
            ),
            action="reconcile",
            subplot_id="leaf",
            at=f"2026-07-0{index + 1}T00:00:00Z",
            member_index=member_index,
        )


# --------------------------------------------------------------------------- pure Elo math


def test_expected_scores_are_symmetric() -> None:
    assert CE.expected(1200.0, 1200.0) == pytest.approx(0.5)
    assert CE.expected(1300.0, 1200.0) + CE.expected(1200.0, 1300.0) == pytest.approx(1.0)


def test_draw_at_equal_ratings_moves_nothing() -> None:
    scores: dict[tuple[str, str], float] = {}
    CE.apply_match(scores, CE.Match("second-opinion", "a", "b", True, "t"))
    assert scores[("a", "second-opinion")] == pytest.approx(CE.ELO_BASE)
    assert scores[("b", "second-opinion")] == pytest.approx(CE.ELO_BASE)


def test_win_transfers_rating_symmetrically() -> None:
    scores: dict[tuple[str, str], float] = {}
    CE.apply_match(scores, CE.Match("second-opinion", "a", "b", False, "t"))
    assert scores[("a", "second-opinion")] == pytest.approx(CE.ELO_BASE + CE.K / 2)
    assert scores[("b", "second-opinion")] == pytest.approx(CE.ELO_BASE - CE.K / 2)


# --------------------------------------------------------------------------- match derivation


def _fact(
    *,
    reconciliation_id: str = "recon-1",
    intent: str = "second-opinion",
    action: str = "reconcile",
    member_index: dict[str, list[str]] | None = None,
    items: list[dict[str, str]] | None = None,
    at: str = "t1",
) -> dict[str, Any]:
    return {
        "kind": "reconciliation",
        "reconciliation_id": reconciliation_id,
        "intent": intent,
        "action": action,
        "member_index": member_index
        if member_index is not None
        else {"finding-a": ["a"], "finding-b": ["b"]},
        "items": items
        if items is not None
        else [
            {"source_finding_id": "finding-a", "status": "dropped"},
            {"source_finding_id": "finding-b", "status": "reconciled"},
        ],
        "at": at,
    }


def test_derive_matches_produces_head_to_head_win() -> None:
    derivation = CE.derive_matches([_fact()])
    assert derivation.unattributed == 0
    assert derivation.matches == (CE.Match("second-opinion", "b", "a", False, "t1"),)


def test_solo_reconciliation_produces_no_match() -> None:
    fact = _fact(member_index={"finding-a": ["a"], "finding-b": ["a"]})
    assert CE.derive_matches([fact]).matches == ()


def test_unmapped_intent_is_skipped_and_counted() -> None:
    derivation = CE.derive_matches([_fact(intent="offload")])
    assert derivation.matches == ()
    assert derivation.unattributed == 1


def test_panel_empty_findings_do_not_attribute_and_score_zero() -> None:
    fact = _fact(
        member_index={"panel-empty:abc": ["a"], "finding-b": ["b"]},
        items=[
            {"source_finding_id": "panel-empty:abc", "status": "dropped"},
            {"source_finding_id": "finding-b", "status": "reconciled"},
        ],
    )
    derivation = CE.derive_matches([fact])
    # A has zero attributed non-empty findings (share 0.0); B survived (share 1.0) — B wins.
    assert derivation.matches == (CE.Match("second-opinion", "b", "a", False, "t1"),)


def test_equal_shares_produce_a_draw() -> None:
    fact = _fact(
        items=[
            {"source_finding_id": "finding-a", "status": "reconciled"},
            {"source_finding_id": "finding-b", "status": "reconciled"},
        ]
    )
    derivation = CE.derive_matches([fact])
    assert derivation.matches[0].draw is True


def test_apply_fact_does_not_double_count(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    member_index = {"finding-a": ["enga/default"], "finding-b": ["engb/default"]}
    result = _panel_result(
        0,
        a_status=RC.ReconciliationStatus.DROPPED,
        b_status=RC.ReconciliationStatus.RECONCILED,
    )
    for action in ("reconcile", "apply"):
        RC.append_reconciliation_fact(
            ledger,
            result,
            action=action,
            subplot_id="leaf",
            at="2026-07-01T00:00:00Z",
            member_index=member_index,
        )
    assert len(CE.derive(ledger).matches) == 1


# --------------------------------------------------------------------------- AE4 end-to-end


def test_elo_drop_reroutes_fallback_prior_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AE4: five straight losses drop A's Elo below B; a calibrated resolve stops selecting A
    while the authored rating (and the registry file bytes) stay untouched."""
    registry_path = _registry_path(tmp_path, [_row("enga"), _row("engb", cost_speed_rank=4)])
    registry_bytes = registry_path.read_bytes()
    registry = REG.Registry.load(registry_path)
    ledger = _ledger(tmp_path)
    _seed_five_losses(ledger)

    scores = CE.scores(ledger)
    assert scores[("engb/default", "second-opinion")] > scores[("enga/default", "second-opinion")]

    def fake_preflight(engine_id: str, **_kwargs: object) -> dict[str, bool | str]:
        return {"available": True, "reason": f"{engine_id} stubbed available"}

    monkeypatch.setattr(RES, "preflight", fake_preflight)
    request = {"capability": "second-opinion", "role_kind": "worker"}

    baseline = RES.resolve(request, mode="advisory", registry=registry, known_revision_dates={})
    assert baseline.engine_id == "enga"  # uncalibrated: registry order picks A

    calibration = EC.load_calibration(ledger)
    calibrated = RES.resolve(
        request,
        mode="advisory",
        registry=registry,
        known_revision_dates={},
        calibration=calibration,
    )
    assert calibrated.engine_id == "engb"
    assert calibrated.capability == "second-opinion"
    assert calibrated.rating_claimed == "MODERATE"

    # The authored rating field and the on-disk registry are untouched by every step above.
    entry = registry.by_key("enga/default")
    assert entry.capability_profile["second-opinion"]["rating"] == "MODERATE"
    assert registry_path.read_bytes() == registry_bytes


def test_signals_flag_band_divergence_with_enough_matches(tmp_path: Path) -> None:
    registry = REG.Registry.load(_registry_path(tmp_path, [_row("enga"), _row("engb")]))
    ledger = _ledger(tmp_path)
    _seed_five_losses(ledger)

    signals = CE.signals(ledger, registry, min_matches=5)

    assert [
        (signal["engine_key"], signal["capability"], signal["action"]) for signal in signals
    ] == [("enga/default", "second-opinion", "revalidate")]
    assert signals[0]["rival"] == "engb/default"


def test_signals_stay_silent_below_the_match_floor(tmp_path: Path) -> None:
    registry = REG.Registry.load(_registry_path(tmp_path, [_row("enga"), _row("engb")]))
    ledger = _ledger(tmp_path)
    _seed_five_losses(ledger)

    assert CE.signals(ledger, registry, min_matches=6) == []
