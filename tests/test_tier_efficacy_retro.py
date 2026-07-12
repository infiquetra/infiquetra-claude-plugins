"""Tests for the `/retro` tier-efficacy pass (#402 U4).

Pins R6 (an overspent/zero-marginal-finding fixture history yields a gated downgrade proposal,
and the target `.saga/tier-defaults.json` fixture file is provably unchanged after the pass
runs) and KTD5 (this module never calls `tier_defaults.write_tier_default`).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

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


ES = _load("execution_spec")
TD = _load("tier_defaults")
TE = _load("tier_efficacy")


def _record(work_shape: str, model: str, effort: str, spend: int, marginal_findings: int) -> Any:
    return TE.RunRecord(
        work_shape=work_shape,
        tier=ES.Tier(model=model, effort=effort),
        spend=spend,
        marginal_findings=marginal_findings,
    )


def test_overspent_zero_marginal_yields_downgrade_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A .saga/tier-defaults.json FIXTURE, isolated to tmp_path -- never the real repo file.
    fixture_path = tmp_path / ".saga" / "tier-defaults.json"
    fixture_path.parent.mkdir(parents=True)
    fixture_path.write_text('{"judgment": {"model": "opus", "effort": "high"}}\n')
    original_bytes = fixture_path.read_text()

    history = [
        _record("judgment", "opus", "high", spend=10, marginal_findings=0),
        _record("judgment", "opus", "high", spend=10, marginal_findings=0),
        _record("judgment", "opus", "high", spend=10, marginal_findings=0),
        _record("judgment", "opus", "high", spend=10, marginal_findings=0),
    ]

    proposals = TE.propose_downgrades(history, min_samples=3)

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.work_shape == "judgment"
    assert proposal.current_tier == ES.Tier(model="opus", effort="high")
    assert proposal.n_runs == 4
    assert proposal.total_spend == 40

    preview = TE.render_diff_preview(proposals, root=tmp_path)
    assert "judgment" in preview
    assert proposal.proposed_tier.model in preview or proposal.proposed_tier.effort in preview

    # The AC's exact assertion: the target fixture file is byte-unchanged after the pass runs.
    assert fixture_path.read_text() == original_bytes


def test_mixed_evidence_proposes_no_change() -> None:
    history = [
        _record("judgment", "opus", "high", spend=10, marginal_findings=0),
        _record("judgment", "opus", "high", spend=10, marginal_findings=2),  # real findings
        _record("judgment", "opus", "high", spend=10, marginal_findings=0),
        _record("judgment", "opus", "high", spend=10, marginal_findings=0),
    ]
    assert TE.propose_downgrades(history, min_samples=3) == []


def test_below_min_samples_proposes_no_change() -> None:
    history = [
        _record("judgment", "opus", "high", spend=10, marginal_findings=0),
        _record("judgment", "opus", "high", spend=10, marginal_findings=0),
    ]
    assert TE.propose_downgrades(history, min_samples=3) == []


def test_differing_tiers_within_a_work_shape_is_ambiguous_no_proposal() -> None:
    history = [
        _record("judgment", "opus", "high", spend=10, marginal_findings=0),
        _record("judgment", "sonnet", "high", spend=10, marginal_findings=0),
        _record("judgment", "opus", "high", spend=10, marginal_findings=0),
    ]
    assert TE.propose_downgrades(history, min_samples=3) == []


def test_already_cheapest_tier_proposes_nothing() -> None:
    cheap_model, cheap_effort = ES._tier_palette.MODELS[-1], ES._tier_palette.EFFORTS[0]
    history = [
        _record("mechanical", cheap_model, cheap_effort, spend=1, marginal_findings=0)
        for _ in range(4)
    ]
    assert TE.propose_downgrades(history, min_samples=3) == []


def test_write_tier_default_never_called(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("tier_efficacy must never call write_tier_default")

    monkeypatch.setattr(TD, "write_tier_default", _boom)

    history = [_record("judgment", "opus", "high", spend=10, marginal_findings=0) for _ in range(3)]
    proposals = TE.propose_downgrades(history)
    # Exact min_samples boundary (3 records, default min_samples=3): must still yield a proposal
    # (a #402 code-review testing-lens finding -- this boundary was exercised but never asserted,
    # so a `<` -> `<=` mutation in the len(records) check would have slipped through silently).
    assert len(proposals) == 1
    TE.render_diff_preview(proposals)


def test_min_samples_boundary_one_below_yields_no_proposal() -> None:
    """`min_samples - 1` records must NOT propose -- the exact-boundary complement of the test above."""
    history = [_record("judgment", "opus", "high", spend=10, marginal_findings=0) for _ in range(2)]
    assert TE.propose_downgrades(history, min_samples=3) == []


def test_at_or_below_baseline_tier_proposes_no_change_even_with_clean_history() -> None:
    """#402 code-review correctness finding (P1): a work-shape already at-or-below SPEND_BASELINE
    (sonnet/high) must never get a downgrade proposal, no matter how clean its findings history is
    or how many runs support it -- there is no over-spend to correct. Regression guard for the
    missing `is_escalation(SPEND_BASELINE, current_tier)` gate found during code-review.
    """
    at_baseline = [
        _record("mechanical", "sonnet", "high", spend=10, marginal_findings=0) for _ in range(5)
    ]
    assert TE.propose_downgrades(at_baseline, min_samples=3) == []

    below_baseline = [
        _record("mechanical", "sonnet", "low", spend=5, marginal_findings=0) for _ in range(5)
    ]
    assert TE.propose_downgrades(below_baseline, min_samples=3) == []


def test_cli_malformed_history_returns_exit_code_2(tmp_path: Path) -> None:
    """#402 code-review security finding (P2): a malformed `--history` JSON element (wrong shape,
    not a dict, or a non-dict `tier`) must be caught and reported via the module's own
    `TierEfficacyError`/exit-code-2 contract -- never an uncaught `TypeError` traceback.
    """
    malformed = tmp_path / "history.json"
    malformed.write_text('["not-a-record-object"]', encoding="utf-8")
    assert TE.main(["--history", str(malformed)]) == 2

    malformed_tier = tmp_path / "history-bad-tier.json"
    malformed_tier.write_text(
        '[{"work_shape": "x", "tier": "not-a-dict", "spend": 1, "marginal_findings": 0}]',
        encoding="utf-8",
    )
    assert TE.main(["--history", str(malformed_tier)]) == 2


def test_cli_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        TE.main(["--help"])
    assert exc_info.value.code == 0
