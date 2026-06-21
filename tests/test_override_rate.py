"""Tests for the R12 override-rate reader (U13).

Tests cover:

* **Fixtures with data** → correct override-rate, over/under-tier, and
  budget-exhaustion counts.
* **Empty corpus** → all rates are None ("no data yet"), no divide-by-zero.
* **Partial data** (only one of recommended/choice recorded) → excluded from
  denominator.
* **Tier direction** → over-tier and under-tier detection.
* **Budget-exhaustion** → ``orchestration_downgrade`` non-empty → counted.
* **Format report** → zero-data string contains "no data yet"; data present
  shows percentages.
* **CLI smoke** → ``--json`` flag emits valid JSON; no filesystem side-effects.

Determinism / offline discipline:
  All tests construct envelope files inside ``tmp_path``; the reader is given
  the ``tmp_path`` root so the real ``.claude/saga/`` is never read or written.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "plugins" / "saga" / "scripts"


def _load_module(name: str) -> ModuleType:
    path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name.removesuffix(".py")] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def orr() -> ModuleType:
    """Loaded override_rate_reader module."""
    return _load_module("override_rate_reader.py")


@pytest.fixture
def saga() -> ModuleType:
    """Loaded saga engine module (the real producer of envelope frontmatter)."""
    return _load_module("saga.py")


# ---------------------------------------------------------------------------
# Envelope fixture helpers
# ---------------------------------------------------------------------------

_SAGA_DIR_TMPL = ".claude/saga/sagas"


def _write_envelope(
    root: Path,
    saga_id: str,
    *,
    recommended: str = "",
    operator_choice: str = "",
    mode: str = "inline",
    downgrade: str = "",
) -> Path:
    """Write a minimal saga envelope file to *root*."""
    saga_dir = root / _SAGA_DIR_TMPL / saga_id
    saga_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"saga_id: {saga_id}",
        "kind: issue",
        "id: 1",
        "schema_version: 1.0",
        f"orchestration_mode: {mode}",
        f"orchestration_recommended: {recommended}",
        f"orchestration_operator_choice: {operator_choice}",
        f"orchestration_downgrade: {downgrade}",
        "---",
        "",
        "## body",
    ]
    path = saga_dir / "20260621-120000.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Zero-data (empty corpus) tests
# ---------------------------------------------------------------------------


def test_empty_corpus_returns_none_rates(orr: ModuleType, tmp_path: Path) -> None:
    """An empty saga directory yields None for all rates (no divide-by-zero)."""
    # Create the sagas directory so the reader finds it but no envelopes.
    (tmp_path / _SAGA_DIR_TMPL).mkdir(parents=True)
    summary, records = orr.read_override_rate(tmp_path)
    assert summary.total_sagas == 0
    assert summary.decisions_with_data == 0
    assert summary.override_rate is None
    assert summary.over_tier_rate is None
    assert summary.under_tier_rate is None
    assert summary.budget_exhaustion_count == 0
    assert records == []


def test_empty_corpus_missing_sagas_dir(orr: ModuleType, tmp_path: Path) -> None:
    """No ``.claude/saga/sagas/`` directory at all → same zero-data result."""
    summary, records = orr.read_override_rate(tmp_path)
    assert summary.total_sagas == 0
    assert summary.override_rate is None


# ---------------------------------------------------------------------------
# Partial data (only one field recorded) tests
# ---------------------------------------------------------------------------


def test_saga_with_only_recommended_excluded(orr: ModuleType, tmp_path: Path) -> None:
    """A saga with recommended but no operator_choice is not counted in decisions_with_data."""
    _write_envelope(tmp_path, "issue-1", recommended="team-execution", operator_choice="")
    summary, records = orr.read_override_rate(tmp_path)
    assert summary.total_sagas == 1
    assert summary.decisions_with_data == 0
    assert summary.override_rate is None


def test_saga_with_only_operator_choice_excluded(orr: ModuleType, tmp_path: Path) -> None:
    """A saga with operator_choice but no recommended is not counted."""
    _write_envelope(tmp_path, "issue-1", recommended="", operator_choice="inline")
    summary, records = orr.read_override_rate(tmp_path)
    assert summary.total_sagas == 1
    assert summary.decisions_with_data == 0
    assert summary.override_rate is None


# ---------------------------------------------------------------------------
# No-override tests
# ---------------------------------------------------------------------------


def test_no_override_when_choice_matches_recommendation(orr: ModuleType, tmp_path: Path) -> None:
    """Operator followed the recommendation → override_rate == 0.0."""
    _write_envelope(
        tmp_path,
        "issue-1",
        recommended="team-execution",
        operator_choice="team-execution",
        mode="team-execution",
    )
    summary, _ = orr.read_override_rate(tmp_path)
    assert summary.decisions_with_data == 1
    assert summary.override_count == 0
    assert summary.override_rate == pytest.approx(0.0)
    assert summary.over_tier_count == 0
    assert summary.under_tier_count == 0


# ---------------------------------------------------------------------------
# Override tests — mixed corpus
# ---------------------------------------------------------------------------


def test_override_rate_computed_correctly(orr: ModuleType, tmp_path: Path) -> None:
    """3 sagas: 1 follows recommendation, 2 override → rate = 2/3."""
    _write_envelope(tmp_path, "issue-1", recommended="inline", operator_choice="inline")
    _write_envelope(tmp_path, "issue-2", recommended="inline", operator_choice="team-execution")
    _write_envelope(
        tmp_path,
        "issue-3",
        recommended="team-execution",
        operator_choice="cc-workflows-ultracode",
    )
    summary, _ = orr.read_override_rate(tmp_path)
    assert summary.total_sagas == 3
    assert summary.decisions_with_data == 3
    assert summary.override_count == 2
    assert summary.override_rate == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# Over-tier tests
# ---------------------------------------------------------------------------


def test_over_tier_inline_to_team_execution(orr: ModuleType, tmp_path: Path) -> None:
    """inline → team-execution is an over-tier escalation."""
    _write_envelope(tmp_path, "issue-1", recommended="inline", operator_choice="team-execution")
    summary, _ = orr.read_override_rate(tmp_path)
    assert summary.over_tier_count == 1
    assert summary.under_tier_count == 0


def test_over_tier_inline_to_ultracode(orr: ModuleType, tmp_path: Path) -> None:
    """inline → cc-workflows-ultracode is an over-tier escalation."""
    _write_envelope(
        tmp_path,
        "issue-1",
        recommended="inline",
        operator_choice="cc-workflows-ultracode",
    )
    summary, _ = orr.read_override_rate(tmp_path)
    assert summary.over_tier_count == 1
    assert summary.under_tier_count == 0


def test_over_tier_team_execution_to_ultracode(orr: ModuleType, tmp_path: Path) -> None:
    """team-execution → cc-workflows-ultracode is an over-tier escalation."""
    _write_envelope(
        tmp_path,
        "issue-1",
        recommended="team-execution",
        operator_choice="cc-workflows-ultracode",
    )
    summary, _ = orr.read_override_rate(tmp_path)
    assert summary.over_tier_count == 1
    assert summary.under_tier_count == 0


# ---------------------------------------------------------------------------
# Under-tier tests
# ---------------------------------------------------------------------------


def test_under_tier_team_execution_to_inline(orr: ModuleType, tmp_path: Path) -> None:
    """team-execution → inline is an under-tier de-escalation."""
    _write_envelope(tmp_path, "issue-1", recommended="team-execution", operator_choice="inline")
    summary, _ = orr.read_override_rate(tmp_path)
    assert summary.under_tier_count == 1
    assert summary.over_tier_count == 0


def test_under_tier_ultracode_to_inline(orr: ModuleType, tmp_path: Path) -> None:
    """cc-workflows-ultracode → inline is an under-tier de-escalation."""
    _write_envelope(
        tmp_path,
        "issue-1",
        recommended="cc-workflows-ultracode",
        operator_choice="inline",
    )
    summary, _ = orr.read_override_rate(tmp_path)
    assert summary.under_tier_count == 1
    assert summary.over_tier_count == 0


def test_under_tier_ultracode_to_team_execution(orr: ModuleType, tmp_path: Path) -> None:
    """cc-workflows-ultracode → team-execution is an under-tier de-escalation."""
    _write_envelope(
        tmp_path,
        "issue-1",
        recommended="cc-workflows-ultracode",
        operator_choice="team-execution",
    )
    summary, _ = orr.read_override_rate(tmp_path)
    assert summary.under_tier_count == 1
    assert summary.over_tier_count == 0


# ---------------------------------------------------------------------------
# Budget-exhaustion / downgrade tests
# ---------------------------------------------------------------------------


def test_no_downgrade_no_budget_exhaustion(orr: ModuleType, tmp_path: Path) -> None:
    """A saga with no downgrade note → budget_exhaustion_count == 0."""
    _write_envelope(tmp_path, "issue-1", downgrade="")
    summary, _ = orr.read_override_rate(tmp_path)
    assert summary.budget_exhaustion_count == 0


def test_downgrade_note_counted(orr: ModuleType, tmp_path: Path) -> None:
    """A non-empty orchestration_downgrade → counted as a degradation event."""
    _write_envelope(
        tmp_path,
        "issue-1",
        downgrade="off-host: Workflow tool unavailable; downgraded inline",
    )
    summary, _ = orr.read_override_rate(tmp_path)
    assert summary.budget_exhaustion_count == 1


def test_multiple_downgrades_all_counted(orr: ModuleType, tmp_path: Path) -> None:
    """Multiple sagas with downgrade notes → all counted."""
    _write_envelope(tmp_path, "issue-1", downgrade="downgraded to inline")
    _write_envelope(tmp_path, "issue-2", downgrade="downgraded to team-execution")
    _write_envelope(tmp_path, "issue-3", downgrade="")
    summary, _ = orr.read_override_rate(tmp_path)
    assert summary.budget_exhaustion_count == 2
    assert summary.total_sagas == 3


# ---------------------------------------------------------------------------
# Mixed corpus tests (comprehensive)
# ---------------------------------------------------------------------------


def test_full_corpus(orr: ModuleType, tmp_path: Path) -> None:
    """Full corpus: 5 sagas with mixed conditions."""
    # Saga 1: follows recommendation (inline → inline)
    _write_envelope(tmp_path, "issue-1", recommended="inline", operator_choice="inline")
    # Saga 2: over-tier (inline → team-execution)
    _write_envelope(tmp_path, "issue-2", recommended="inline", operator_choice="team-execution")
    # Saga 3: under-tier (cc-workflows-ultracode → inline) + downgrade
    _write_envelope(
        tmp_path,
        "issue-3",
        recommended="cc-workflows-ultracode",
        operator_choice="inline",
        downgrade="off-host downgrade to inline",
    )
    # Saga 4: no recommendation data (partial — excluded from denominator)
    _write_envelope(tmp_path, "issue-4", recommended="", operator_choice="")
    # Saga 5: downgrade only, no recommendation data
    _write_envelope(tmp_path, "issue-5", downgrade="downgraded to team-execution")

    summary, records = orr.read_override_rate(tmp_path)
    assert summary.total_sagas == 5
    assert summary.decisions_with_data == 3
    assert summary.override_count == 2
    assert summary.over_tier_count == 1
    assert summary.under_tier_count == 1
    assert summary.budget_exhaustion_count == 2
    assert summary.override_rate == pytest.approx(2 / 3)
    assert summary.over_tier_rate == pytest.approx(1 / 3)
    assert summary.under_tier_rate == pytest.approx(1 / 3)


# ---------------------------------------------------------------------------
# format_report tests
# ---------------------------------------------------------------------------


def test_format_report_no_data_says_no_data_yet(orr: ModuleType, tmp_path: Path) -> None:
    """Zero-data report contains 'no data yet' in override-rate line."""
    (tmp_path / _SAGA_DIR_TMPL).mkdir(parents=True)
    summary, records = orr.read_override_rate(tmp_path)
    report = orr.format_report(summary, records)
    assert "no data yet" in report
    # Must not contain a percentage sign in the override rate line.
    # (Rates are None; only budget-exhaustion count, which is 0, is shown.)
    assert "Override Rate" in report
    assert "no data yet" in report


def test_format_report_with_data_shows_percentages(orr: ModuleType, tmp_path: Path) -> None:
    """When data is present, the report shows percentages."""
    _write_envelope(tmp_path, "issue-1", recommended="inline", operator_choice="team-execution")
    _write_envelope(tmp_path, "issue-2", recommended="inline", operator_choice="inline")
    summary, records = orr.read_override_rate(tmp_path)
    report = orr.format_report(summary, records)
    assert "%" in report
    # Override count = 1, decisions = 2 → 50.0%
    assert "50.0%" in report


def test_format_report_shows_downgrade_notes(orr: ModuleType, tmp_path: Path) -> None:
    """Downgrade notes appear in the report under a dedicated section."""
    _write_envelope(
        tmp_path,
        "issue-1",
        downgrade="off-host: downgraded to inline",
    )
    summary, records = orr.read_override_rate(tmp_path)
    report = orr.format_report(summary, records)
    assert "Downgrade Notes" in report
    assert "off-host: downgraded to inline" in report


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------


def test_cli_json_output(orr: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
    """``--json`` flag emits valid JSON with the expected keys."""
    _write_envelope(tmp_path, "issue-1", recommended="inline", operator_choice="team-execution")
    orr.main(["--root", str(tmp_path), "--json"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    expected_keys = {
        "total_sagas",
        "decisions_with_data",
        "override_count",
        "over_tier_count",
        "under_tier_count",
        "budget_exhaustion_count",
        "override_rate",
        "over_tier_rate",
        "under_tier_rate",
    }
    assert expected_keys <= set(data.keys())
    assert data["override_count"] == 1
    assert data["decisions_with_data"] == 1


def test_cli_human_report(
    orr: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,  # type: ignore[type-arg]
) -> None:
    """Default (no ``--json``) emits a human-readable report."""
    (tmp_path / _SAGA_DIR_TMPL).mkdir(parents=True)
    orr.main(["--root", str(tmp_path)])
    captured = capsys.readouterr()
    assert "R12 Orchestration Signals" in captured.out
    assert "no data yet" in captured.out


def test_cli_no_filesystem_side_effects(orr: ModuleType, tmp_path: Path) -> None:
    """Reader never writes to disk."""
    _write_envelope(tmp_path, "issue-1", recommended="inline", operator_choice="inline")
    before = {str(p) for p in tmp_path.rglob("*") if p.is_file()}
    orr.read_override_rate(tmp_path)
    after = {str(p) for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after, "read_override_rate wrote unexpected files"


# ---------------------------------------------------------------------------
# as_dict round-trip
# ---------------------------------------------------------------------------


def test_summary_as_dict_round_trips(orr: ModuleType, tmp_path: Path) -> None:
    """``summary.as_dict()`` contains all expected keys and correct values."""
    _write_envelope(tmp_path, "issue-1", recommended="team-execution", operator_choice="inline")
    summary, _ = orr.read_override_rate(tmp_path)
    d = summary.as_dict()
    assert d["total_sagas"] == 1
    assert d["decisions_with_data"] == 1
    assert d["override_count"] == 1
    assert d["under_tier_count"] == 1
    assert d["over_tier_count"] == 0
    assert d["override_rate"] == pytest.approx(1.0)
    assert d["under_tier_rate"] == pytest.approx(1.0)
    assert d["over_tier_rate"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# End-to-end producer → consumer (R12)
# ---------------------------------------------------------------------------


def _stub_saga_git(saga: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``saga.save``'s subprocess seam a no-op so the test never shells out.

    ``save`` threads ``runner`` as a keyword-only default captured at definition
    time, so we patch both ``saga.subprocess.run`` and the captured default on the
    git-touching functions (mirrors test_saga_saga's ``_set_runner``).
    """

    def fake_run(*_args: object, **_kwargs: object) -> object:
        from types import SimpleNamespace

        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(saga.subprocess, "run", fake_run)
    for fn_name in ("save", "current_git_state"):
        fn = getattr(saga, fn_name)
        new_kwdefaults = dict(fn.__kwdefaults__ or {})
        new_kwdefaults["runner"] = fake_run
        monkeypatch.setattr(fn, "__kwdefaults__", new_kwdefaults)


def test_real_saga_save_feeds_override_rate_reader(
    orr: ModuleType,
    saga: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,  # type: ignore[type-arg]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: the REAL ``saga.py save`` producer feeds the R12 consumer.

    Exercises the full producer→consumer path (NOT hand-crafted frontmatter):
    drive ``saga.main(["save", ...])`` twice through ``_build_save_saga`` — once
    recording an override (mode != recommended) and once a match — then run the
    override-rate reader over the same saga dir and assert it sees real data
    (denominator > 0, the override counted), i.e. NOT "no data yet".
    """
    monkeypatch.chdir(tmp_path)
    _stub_saga_git(saga, monkeypatch)

    # Decision 1: an OVERRIDE — operator chose cc-workflows-ultracode over the
    # recommended team-execution. operator_choice auto-derives from --orchestration-mode.
    assert (
        saga.main(
            [
                "save",
                "--kind",
                "task",
                "--id",
                "override-decision",
                "--lifecycle-phase",
                "plan",
                "--orchestration-mode",
                "cc-workflows-ultracode",
                "--orchestration-recommended",
                "team-execution",
            ]
        )
        == 0
    )
    # Decision 2: operator FOLLOWED the recommendation (mode == recommended).
    assert (
        saga.main(
            [
                "save",
                "--kind",
                "task",
                "--id",
                "matched-decision",
                "--lifecycle-phase",
                "plan",
                "--orchestration-mode",
                "inline",
                "--orchestration-recommended",
                "inline",
            ]
        )
        == 0
    )
    capsys.readouterr()  # discard the save JSON the CLI prints

    # Consumer reads the SAME root the producer wrote to.
    summary, records = orr.read_override_rate(tmp_path)

    # Real data, not "no data yet": both decisions recorded both fields.
    assert summary.total_sagas == 2
    assert summary.decisions_with_data == 2
    assert summary.override_count == 1  # only decision 1 overrode
    assert summary.over_tier_count == 1  # team-execution → cc-workflows-ultracode is over-tier
    assert summary.under_tier_count == 0
    assert summary.override_rate == pytest.approx(0.5)

    # The human report must NOT fall through to the zero-data branch.
    report = orr.format_report(summary, records)
    assert "no data yet" not in report
    assert "50.0%" in report

    # The override decision's operator_choice auto-derived from --orchestration-mode.
    override_rec = next(r for r in records if r.recommended == "team-execution")
    assert override_rec.operator_choice == "cc-workflows-ultracode"
    assert override_rec.actual_mode == "cc-workflows-ultracode"
