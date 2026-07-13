"""`/retro` calibration-proposal aggregation + never-writes tests (#459 R6/AE6), plus the
calibration-aware ranking parity guards (R4/R5 runtime consumption)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
RETRO_SKILL = ROOT / "plugins" / "saga" / "skills" / "retro" / "SKILL.md"
REAL_REGISTRY = ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


EC = _load("engine_calibration")
REG = _load("engine_registry")
RES = _load("engine_resolver")
RC = EC.capability_elo.reconcile
RL = EC.run_ledger


def _row(
    engine_id: str,
    *,
    capability: str = "adversarial-review",
    rating: str = "MODERATE",
    cost_speed_rank: int = 3,
) -> dict[str, Any]:
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
        "capability_profile": {capability: {"rating": rating, "note": "fixture"}},
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


def _engine_fact(
    engine: str, *, at: str, latency: float = 1.0, capability: str = "adversarial-review"
) -> Any:
    return RL.build_fact(
        "engine",
        subplot_id="leaf",
        at=at,
        engine=engine,
        variant="default",
        capability=capability,
        rating_claimed="MODERATE",
        execution_id="exec-1",
        status="ok",
        proof_integrity_status="ok",
        cost=0.01,
        latency_seconds=latency,
        tokens=100,
    )


def _benchmark_fact(engine: str, *, at: str) -> Any:
    return RL.build_fact(
        "benchmark",
        subplot_id="leaf",
        at=at,
        engine=engine,
        variant="default",
        capability="adversarial-review",
        suite_id="adversarial-review-v1",
        probes_total=4,
        probes_passed=0,
        measured_rating="WEAK",
        claimed_rating="STRONG",
        contradicts=True,
    )


def _seed_elo_losses(ledger: Any, loser: str, winner: str) -> None:
    member_index = {"finding-a": [f"{loser}/default"], "finding-b": [f"{winner}/default"]}
    for index in range(5):
        result = RC.build_result(
            reconciliation_id=f"recon-{loser}-{index}",
            execution_id=f"exec-{loser}-{index}",
            intent="second-opinion",
            adjudicator_id="claude/opus",
            source_finding_ids=("finding-a", "finding-b"),
            items=(
                RC.ReconciliationItem(
                    source_finding_id="finding-a",
                    status=RC.ReconciliationStatus.DROPPED,
                    adjudicator_id="claude/opus",
                    rationale="Claude dropped the loser's finding.",
                ),
                RC.ReconciliationItem(
                    source_finding_id="finding-b",
                    status=RC.ReconciliationStatus.RECONCILED,
                    adjudicator_id="claude/opus",
                    rationale="Claude reconciled the winner's finding.",
                ),
            ),
        )
        RC.append_reconciliation_fact(
            ledger,
            result,
            action="reconcile",
            subplot_id="leaf",
            at=f"2026-07-0{index + 1}T00:00:00Z",
            member_index=member_index,
        )


def _all_signal_fixture(tmp_path: Path) -> tuple[Path, Any, Any]:
    """Registry + ledger carrying all four signal families (AE6's seeded fragments)."""
    registry_path = _registry_path(
        tmp_path,
        [
            _row("benchprov", rating="STRONG"),
            _row("goodprov"),
            _row("eloloser", capability="second-opinion"),
            _row("elowinner", capability="second-opinion"),
            _row("spiky", capability="code-generation"),
        ],
    )
    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _benchmark_fact("benchprov", at="2026-07-02T00:00:00Z"))
    RL.append_fact(ledger, _engine_fact("goodprov", at="2026-07-05T00:00:00Z"))
    RL.append_fact(ledger, _engine_fact("goodprov", at="2026-07-10T00:00:00Z"))
    _seed_elo_losses(ledger, "eloloser", "elowinner")
    for index in range(18):
        latency = 1.0 if index < 12 else 3.0
        RL.append_fact(
            ledger,
            _engine_fact(
                "spiky",
                at=f"2026-07-11T00:{index:02d}:00Z",
                latency=latency,
                capability="code-generation",
            ),
        )
    return registry_path, REG.Registry.load(registry_path), ledger


def _cells_by_action(proposal: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_action: dict[str, list[dict[str, Any]]] = {}
    for cell in proposal["cells"]:
        by_action.setdefault(cell["action"], []).append(cell)
    return by_action


# --------------------------------------------------------------------------- AE6


def test_proposal_only_never_writes_registry(tmp_path: Path) -> None:
    """AE6: all four signal families aggregate into one proposal with a rating-change and a
    last-validated bump; the registry file is byte-identical before and after report + preview."""
    registry_path, registry, ledger = _all_signal_fixture(tmp_path)
    registry_bytes = registry_path.read_bytes()

    proposal = EC.report(registry, ledger, now=date(2026, 7, 13))
    preview = EC.render_diff_preview(proposal, registry_path)

    assert proposal["schema"] == "registry_calibration_proposal.v1"
    assert proposal["status"] == "proposal"
    assert proposal["approval_required"] is True
    by_action = _cells_by_action(proposal)

    rating_changes = by_action["rating-change"]
    assert [(c["engine_key"], c["capability"]) for c in rating_changes] == [
        ("benchprov/default", "adversarial-review")
    ]
    assert rating_changes[0]["proposed"] == {"rating": "WEAK", "last_validated": "2026-07-13"}

    bumps = by_action["last-validated-bump"]
    assert [(c["engine_key"], c["proposed"]["last_validated"]) for c in bumps] == [
        ("goodprov/default", "2026-07-10")
    ]

    revalidate_keys = {(c["engine_key"], c["capability"]) for c in by_action["revalidate"]}
    assert ("eloloser/default", "second-opinion") in revalidate_keys  # Elo divergence
    assert ("spiky/default", "code-generation") in revalidate_keys  # SPC drift

    assert "PREVIEW ONLY" in preview
    assert "benchprov/default" in preview

    # The one non-negotiable seam: nothing above wrote the registry.
    assert registry_path.read_bytes() == registry_bytes


def test_empty_ledger_yields_no_proposal(tmp_path: Path) -> None:
    registry_path = _registry_path(tmp_path, [_row("goodprov")])
    registry = REG.Registry.load(registry_path)
    ledger = _ledger(tmp_path)

    proposal = EC.report(registry, ledger, now=date(2026, 7, 13))

    assert proposal["status"] == "no-proposal"
    assert proposal["cells"] == []
    assert proposal["approval_required"] is True
    assert {(c["engine_key"], c["capability"]) for c in proposal["unexercised"]} == {
        ("goodprov/default", "adversarial-review")
    }
    assert "no calibration proposal" in EC.render_diff_preview(proposal, registry_path)


def test_chain_break_raises_a_visible_evidence_failure(tmp_path: Path) -> None:
    registry_path, registry, ledger = _all_signal_fixture(tmp_path)
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    ledger.path.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="chain verification failed"):
        EC.report(registry, ledger, now=date(2026, 7, 13))


def test_benchmark_contradiction_beats_bump_on_the_same_cell(tmp_path: Path) -> None:
    registry_path = _registry_path(tmp_path, [_row("benchprov", rating="STRONG")])
    registry = REG.Registry.load(registry_path)
    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _engine_fact("benchprov", at="2026-07-05T00:00:00Z"))
    RL.append_fact(ledger, _benchmark_fact("benchprov", at="2026-07-06T00:00:00Z"))

    proposal = EC.report(registry, ledger, now=date(2026, 7, 13))

    assert [c["action"] for c in proposal["cells"]] == ["rating-change"]


def test_pre_revalidation_benchmarks_never_propose(tmp_path: Path) -> None:
    registry_path = _registry_path(tmp_path, [_row("benchprov", rating="STRONG")])
    registry = REG.Registry.load(registry_path)
    ledger = _ledger(tmp_path)
    # The benchmark predates the row's last_validated (2026-06-01): history, not disagreement.
    RL.append_fact(ledger, _benchmark_fact("benchprov", at="2026-05-01T00:00:00Z"))

    proposal = EC.report(registry, ledger, now=date(2026, 7, 13))

    assert proposal["status"] == "no-proposal"


# --------------------------------------------------------------------------- runtime signals


def test_load_calibration_and_fingerprint(tmp_path: Path) -> None:
    _, _, ledger = _all_signal_fixture(tmp_path)

    signals = EC.load_calibration(ledger)

    assert "spiky" in signals.drift_flagged
    assert (
        signals.elo[("elowinner/default", "second-opinion")]
        > signals.elo[("eloloser/default", "second-opinion")]
    )
    assert EC.calibration_fingerprint(None) == ""
    assert EC.calibration_fingerprint(signals) == signals.fingerprint()
    assert EC.calibration_fingerprint(EC.CalibrationSignals()) != signals.fingerprint()


def test_ranked_candidates_calibration_none_is_byte_identical(tmp_path: Path) -> None:
    registry = REG.Registry.load(REAL_REGISTRY)
    for capability in registry.capabilities:
        assert registry.ranked_candidates(capability) == registry.ranked_candidates(
            capability, calibration=None
        )


def test_drift_flag_deprioritizes_within_band_but_never_excludes_or_crosses_bands(
    tmp_path: Path,
) -> None:
    rows = [
        _row("driftprov", cost_speed_rank=1),
        _row("calmprov", cost_speed_rank=2),
        _row("weakprov", rating="WEAK", cost_speed_rank=1),
    ]
    registry = REG.Registry.load(_registry_path(tmp_path, rows))
    calibration = EC.CalibrationSignals(elo={}, drift_flagged=frozenset({"driftprov"}))

    ranked = registry.ranked_candidates("adversarial-review", calibration=calibration)
    keys = [candidate.entry.key for candidate in ranked]

    # Deprioritized within the MODERATE band, never excluded, never below the WEAK band.
    assert keys == ["calmprov/default", "driftprov/default", "weakprov/default"]


def test_overlay_pin_beats_calibration_reorder(tmp_path: Path) -> None:
    rows = [_row("driftprov", cost_speed_rank=1), _row("calmprov", cost_speed_rank=2)]
    registry = REG.Registry.load(_registry_path(tmp_path, rows))
    calibration = EC.CalibrationSignals(elo={}, drift_flagged=frozenset({"driftprov"}))

    class _Overlay:
        pins = {"adversarial-review": "driftprov/default"}
        deprecated: set[str] = set()

    ranked = registry.ranked_candidates(
        "adversarial-review", overlay=_Overlay(), calibration=calibration
    )

    assert ranked[0].entry.key == "driftprov/default"
    assert ranked[0].pinned is True


def test_run_memo_differentiates_calibration_fingerprints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [_row("driftprov", cost_speed_rank=1), _row("calmprov", cost_speed_rank=2)]
    registry = REG.Registry.load(_registry_path(tmp_path, rows))

    def fake_preflight(engine_id: str, **_kwargs: object) -> dict[str, bool | str]:
        return {"available": True, "reason": f"{engine_id} stubbed available"}

    monkeypatch.setattr(RES, "preflight", fake_preflight)
    memo = RES.RunMemo()
    request = {"capability": "adversarial-review", "role_kind": "worker"}

    plain = RES.resolve(
        request, mode="advisory", registry=registry, memo=memo, known_revision_dates={}
    )
    calibrated = RES.resolve(
        request,
        mode="advisory",
        registry=registry,
        memo=memo,
        known_revision_dates={},
        calibration=EC.CalibrationSignals(elo={}, drift_flagged=frozenset({"driftprov"})),
    )

    assert plain.engine_id == "driftprov"  # memoized uncalibrated decision
    assert calibrated.engine_id == "calmprov"  # distinct memo key: not served the stale entry


# --------------------------------------------------------------------------- SKILL drift guards


def test_retro_skill_carries_the_calibration_passes() -> None:
    skill = RETRO_SKILL.read_text(encoding="utf-8")
    assert "1.11" in skill
    assert "5(f)" in skill
    assert "{#external-engines-never-gatekeepers}" in skill
    assert "engine_calibration.py" in skill
    assert "never writes `engine-registry.yaml`" in skill
