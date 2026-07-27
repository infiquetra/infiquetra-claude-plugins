"""Tests for the cross-run spend aggregator — tier-mix / premium-spend-share (#402 U3).

Pins R5 (a golden spend-summary over a fixture set of leaf-produced ledgers), R9
(derived-on-read: never rewrites an outcome-spec.json or calls a ledger-write function), and
KTD4 (both real committed outcome-spec.json examples roll up empty today -- "no data yet" is the
honest, non-crashing render for that case).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import date
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


OS_ = _load("outcome_spec")
STORE = _load("outcome_store")
_load("evidence_ledger")
_load("execution_spec")
_load("spend_estimate")
SR = _load("spend_retro")


def _node(subplot_id: str, **overrides: Any) -> Any:
    base: dict[str, Any] = {"subplot_id": subplot_id, "title": subplot_id}
    base.update(overrides)
    return OS_.Node.from_dict(base)


def _spec(outcome_id: str, nodes: list[Any], cost_rollup: dict[str, Any] | None = None) -> Any:
    return OS_.OutcomeSpec(
        outcome_id=outcome_id, objective="demo", nodes=nodes, cost_rollup=cost_rollup or {}
    )


# ---------------------------------------------------------------------------
# Golden spend-summary (T12-F2-8)
# ---------------------------------------------------------------------------


def test_golden_spend_summary(tmp_path: Path) -> None:
    outcomes_dir = tmp_path / "docs" / "outcomes"
    (outcomes_dir / "outcome-a").mkdir(parents=True)
    (outcomes_dir / "outcome-b").mkdir(parents=True)

    spec_a = _spec(
        "outcome-a",
        [_node("sub-1"), _node("sub-2")],  # both default to SPEND_BASELINE (sonnet/high)
        cost_rollup={"tokens": 500},
    )
    spec_b = _spec(
        "outcome-b",
        [_node("sub-3", github={"issue": "org/repo#3"})],
        cost_rollup={},
    )
    (outcomes_dir / "outcome-a" / "outcome-spec.json").write_text(spec_a.to_json())
    (outcomes_dir / "outcome-b" / "outcome-spec.json").write_text(spec_b.to_json())

    issue_bodies = {"org/repo#3": "### Recommended Tier Band\nopus/high\n"}
    discovered = SR.discover_outcomes(tmp_path)
    assert [oid for oid, _ in discovered] == ["outcome-a", "outcome-b"]

    parsed = [
        (oid, OS_.OutcomeSpec.from_dict(json.loads(p.read_text(encoding="utf-8"))))
        for oid, p in discovered
    ]
    summary = SR.build_spend_summary(parsed, issue_bodies=issue_bodies)

    row_a = next(r for r in summary.rows if r.outcome_id == "outcome-a")
    row_b = next(r for r in summary.rows if r.outcome_id == "outcome-b")

    assert row_a.tier_mix == {"sonnet/high": 2}
    assert row_a.premium_node_count == 0
    assert row_a.has_real_telemetry is True

    assert row_b.tier_mix == {"opus/high": 1}
    assert row_b.premium_node_count == 1  # opus/high is above SPEND_BASELINE (sonnet/high)
    assert row_b.has_real_telemetry is False

    # Exact expected aggregate figures (the golden values).
    cost_weights = sys.modules["spend_estimate"]._cost_weights()
    sonnet_high = cost_weights.to_spend("sonnet", "high")
    opus_high = cost_weights.to_spend("opus", "high")
    expected_total = 2 * sonnet_high + opus_high
    expected_premium = opus_high
    total = sum(r.total_estimate for r in summary.rows)
    premium = sum(r.premium_estimate for r in summary.rows)
    assert total == expected_total
    assert premium == expected_premium
    assert summary.aggregate_premium_share() == pytest.approx(expected_premium / expected_total)


# ---------------------------------------------------------------------------
# Derived-on-read (R9)
# ---------------------------------------------------------------------------


def test_derived_on_read_never_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outcomes_dir = tmp_path / "docs" / "outcomes" / "outcome-a"
    outcomes_dir.mkdir(parents=True)
    spec_path = outcomes_dir / "outcome-spec.json"
    spec = _spec("outcome-a", [_node("sub-1")])
    original_bytes = spec.to_json()
    spec_path.write_text(original_bytes)

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("spend_retro must never call a ledger-write function")

    monkeypatch.setattr(STORE, "_write_once", _boom)
    monkeypatch.setattr(STORE, "append_ledger", _boom)
    evidence_ledger = sys.modules["evidence_ledger"]
    monkeypatch.setattr(evidence_ledger, "write", _boom)

    discovered = SR.discover_outcomes(tmp_path)
    parsed = [
        (oid, OS_.OutcomeSpec.from_dict(json.loads(p.read_text(encoding="utf-8"))))
        for oid, p in discovered
    ]
    SR.build_spend_summary(parsed)

    # The committed spec file itself must be byte-unchanged -- read-only, never rewritten.
    assert spec_path.read_text() == original_bytes


def test_journal_write_opens_a_new_top_section(tmp_path: Path) -> None:
    """A retro for a date with no section opens one ABOVE the current newest (#659).

    The previous implementation used ``open("a")``, which filed the entry at the very bottom of
    a newest-first file — under whatever stale date heading happened to sit there. That is the
    drift #659 was raised for, so the direction is pinned here.
    """
    journal = tmp_path / "LEARNINGS.md"
    journal.write_text("# Learnings\n\n## 2026-07-11\n\n### Older thing {#older}\n\nbody\n")
    summary = SR.SpendSummary(rows=[])

    SR.write_to_journal(summary, journal_path=journal, on=date(2026, 7, 12))

    text = journal.read_text()
    assert text.startswith("# Learnings\n")
    assert text.index("## 2026-07-12") < text.index("## 2026-07-11"), "new section must be on top"
    assert text.index("### Spend Retro") < text.index("### Older thing")
    assert "### Older thing {#older}\n\nbody" in text, "existing content must be untouched"
    assert "no data yet" in text


def test_journal_write_reuses_a_same_day_section(tmp_path: Path) -> None:
    """A second retro on the same day lands inside that day's section, not a duplicate heading."""
    journal = tmp_path / "LEARNINGS.md"
    journal.write_text("# Learnings\n\n## 2026-07-12\n\n### Earlier today {#earlier}\n\nbody\n")

    SR.write_to_journal(SR.SpendSummary(rows=[]), journal_path=journal, on=date(2026, 7, 12))

    text = journal.read_text()
    assert text.count("## 2026-07-12") == 1, "must not open a duplicate date heading"
    assert "### Earlier today {#earlier}\n\nbody" in text


def test_journal_write_emits_an_entry_not_a_section(tmp_path: Path) -> None:
    """`## <date> Spend Retro` was neither a date section nor an entry — it is now an entry."""
    journal = tmp_path / "LEARNINGS.md"
    journal.write_text("# Learnings\n\n## 2026-07-11\n\n### Older {#older}\n\nbody\n")

    SR.write_to_journal(SR.SpendSummary(rows=[]), journal_path=journal, on=date(2026, 7, 12))

    text = journal.read_text()
    assert "## 2026-07-12 Spend Retro" not in text
    assert "### Spend Retro {#spend-retro-2026-07-12}" in text
    # Every `##` heading in the result is a bare date — the shape the journal lint enforces.
    for line in text.splitlines():
        if line.startswith("## "):
            assert re.fullmatch(r"## \d{4}-\d{2}-\d{2}", line), f"non-date section: {line!r}"


# ---------------------------------------------------------------------------
# Zero-data / real-repo-state honesty
# ---------------------------------------------------------------------------


def test_zero_outcomes_renders_no_data_yet(tmp_path: Path) -> None:
    summary = SR.build_spend_summary([])
    assert summary.has_any_data is False
    assert "no data yet" in SR.render_summary_table(summary)


def test_outcomes_with_empty_rollup_render_no_data_yet_without_crashing(tmp_path: Path) -> None:
    # A direct regression guard: both real committed docs/outcomes/*/outcome-spec.json examples
    # roll up empty today (verified during grounding) -- this must render honestly, never crash.
    spec = _spec("outcome-a", [_node("sub-1"), _node("sub-2")], cost_rollup={})
    summary = SR.build_spend_summary([("outcome-a", spec)])
    assert summary.has_any_data is True  # nodes exist and estimate, even with no real telemetry
    assert summary.any_real_telemetry is False
    table = SR.render_summary_table(summary)
    assert "no data yet" in table  # the real-telemetry column/footnote says so


def test_real_repo_committed_outcomes_do_not_crash() -> None:
    # Regression guard against the two actual files this issue's grounding found.
    discovered = SR.discover_outcomes(ROOT)
    assert len(discovered) >= 2
    parsed = [
        (oid, OS_.OutcomeSpec.from_dict(json.loads(p.read_text(encoding="utf-8"))))
        for oid, p in discovered
    ]
    summary = SR.build_spend_summary(parsed)
    assert summary.any_real_telemetry is False  # both roll up empty today
    SR.render_summary_table(summary)  # must not raise


def test_cli_corrupt_outcome_spec_json_returns_exit_code_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#402 post-merge review fix (P3): a corrupt committed outcome-spec.json must map to the
    clean `SPEND RETRO ERROR`/exit-2 path, never an uncaught `JSONDecodeError` traceback.
    """
    outcomes_dir = tmp_path / "docs" / "outcomes" / "outcome-a"
    outcomes_dir.mkdir(parents=True)
    (outcomes_dir / "outcome-spec.json").write_text("this is not json{", encoding="utf-8")
    assert SR.main(["report", "--root", str(tmp_path)]) == 2
    assert "SPEND RETRO ERROR" in capsys.readouterr().err


def test_cli_issue_bodies_derives_premium_share_and_provenance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#402 post-merge review fix (P2): the CLI must be able to reach the issue-tier-band
    resolution path -- before `--issue-bodies` existed, every node structurally defaulted to
    SPEND_BASELINE and the CLI's premium share could never be anything but 0%.
    """
    outcomes_dir = tmp_path / "docs" / "outcomes" / "outcome-a"
    outcomes_dir.mkdir(parents=True)
    spec = _spec("outcome-a", [_node("sub-1", github={"issue": "org/repo#3"}), _node("sub-2")])
    (outcomes_dir / "outcome-spec.json").write_text(spec.to_json())

    bodies_path = tmp_path / "issue-bodies.json"
    bodies_path.write_text(
        json.dumps({"org/repo#3": "### Recommended Tier Band\nopus/high\n"}), encoding="utf-8"
    )

    args = ["report", "--root", str(tmp_path), "--json", "--issue-bodies", str(bodies_path)]
    assert SR.main(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tiers_defaulted"] is False
    assert payload["repo_wide_premium_share"] > 0.0
    (row,) = payload["rows"]
    assert row["tier_provenance"] == {"issue-tier-band": 1, "default": 1}
    assert row["premium_node_count"] == 1


def test_cli_without_issue_bodies_labels_defaulted_floor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Honesty companion to the fix above: with no `--issue-bodies`, the all-default 0% premium
    share must be visibly labeled a floor (JSON flag + table note), not presented as derived.
    """
    outcomes_dir = tmp_path / "docs" / "outcomes" / "outcome-a"
    outcomes_dir.mkdir(parents=True)
    spec = _spec("outcome-a", [_node("sub-1")])
    (outcomes_dir / "outcome-spec.json").write_text(spec.to_json())

    assert SR.main(["report", "--root", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tiers_defaulted"] is True
    assert payload["rows"][0]["tier_provenance"] == {"default": 1}

    assert SR.main(["report", "--root", str(tmp_path)]) == 0
    assert "floor, not a derived fact" in capsys.readouterr().out


def test_cli_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        SR.main(["--help"])
    assert exc_info.value.code == 0
