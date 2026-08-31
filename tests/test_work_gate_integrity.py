"""U1 #928 — merge-gate integrity pins.

Validates that saga.py save refuses non-canonical gate verdicts via the existing
parse_gate_verdict, preserves colon-bearing refs, records change_kinds, and
splits the override flag so the audit trail names its gate.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORK_SKILL = ROOT / "plugins" / "saga" / "skills" / "work" / "SKILL.md"
CODE_REVIEW_SKILL = ROOT / "plugins" / "saga" / "skills" / "code-review" / "SKILL.md"
SAGA_PY = ROOT / "plugins" / "saga" / "scripts" / "saga.py"


def _read_skill() -> str:
    return WORK_SKILL.read_text(encoding="utf-8")


def _section(text: str, start_heading: str, end_heading: str) -> str:
    s = text.find(start_heading)
    e = text.find(end_heading, s + len(start_heading))
    assert s >= 0, f"missing heading {start_heading}"
    assert e >= 0, f"missing heading {end_heading}"
    return text[s:e]


def _run_save(tmp_path: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(SAGA_PY),
        "save",
        "--id",
        "999",
        *extra_args,
    ]
    return subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, timeout=10)


# ---------------------------------------------------------------------------
# Happy path — valid verdicts save byte-identical
# ---------------------------------------------------------------------------


def test_valid_verdict_saves_byte_identical(tmp_path: Path) -> None:
    verdict = "tests:done:abc123"
    result = _run_save(tmp_path, "--gate-verdict", verdict)
    assert result.returncode == 0, f"valid save failed: {result.stderr}"
    # Verify stored value is byte-identical via restore.
    restore = subprocess.run(
        [sys.executable, str(SAGA_PY), "restore", "--saga-id", "issue-999"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert restore.returncode == 0
    import json

    payload = json.loads(restore.stdout)
    assert payload["gate_verdicts"] == [verdict]


def test_valid_verdict_with_colon_ref_survives_intact(tmp_path: Path) -> None:
    verdict = "tests:done:https://github.com/o/r/pull/9"
    result = _run_save(tmp_path, "--gate-verdict", verdict)
    assert result.returncode == 0, f"colon-bearing ref save failed: {result.stderr}"
    import json

    restore = subprocess.run(
        [sys.executable, str(SAGA_PY), "restore", "--saga-id", "issue-999"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    payload = json.loads(restore.stdout)
    assert payload["gate_verdicts"] == [verdict]
    # Also direct parse preserves ref.
    from plugins.saga.scripts import saga as saga_mod  # type: ignore

    g, s, ref = saga_mod.parse_gate_verdict(verdict)
    assert g == "tests" and s == "done" and ref == "https://github.com/o/r/pull/9"


# ---------------------------------------------------------------------------
# Error path — malformed verdicts are refused at save time with error at exit 2
# ---------------------------------------------------------------------------


def test_malformed_verdict_noncanonical_state_is_refused(tmp_path: Path) -> None:
    result = _run_save(tmp_path, "--gate-verdict", "tests:pass:abc123")
    assert result.returncode == 2, (
        f"expected exit 2, got {result.returncode}: {result.stderr} / {result.stdout}"
    )
    assert "error:" in result.stderr.lower()
    # Parser message must name the six canonical states.
    assert "must be one of" in result.stderr.lower()
    for state in ("done", "in-progress", "blocked", "failed", "halted", "not-reached"):
        assert state in result.stderr
    # No envelope and no state.json entry written.
    sagas_dir = tmp_path / ".claude" / "saga" / "sagas" / "issue-999"
    if sagas_dir.exists():
        assert list(sagas_dir.glob("*.md")) == []
    state_path = tmp_path / ".claude" / "saga" / "state.json"
    if state_path.exists():
        import json

        state = json.loads(state_path.read_text(encoding="utf-8"))
        sagas = state.get("sagas", {})
        assert "issue-999" not in sagas


def test_malformed_verdict_no_colon_is_refused(tmp_path: Path) -> None:
    result = _run_save(tmp_path, "--gate-verdict", "garbage")
    assert result.returncode == 2
    assert "error:" in result.stderr.lower()
    assert "no colon" in result.stderr.lower() or "colon" in result.stderr.lower()
    sagas_dir = tmp_path / ".claude" / "saga" / "sagas" / "issue-999"
    if sagas_dir.exists():
        assert list(sagas_dir.glob("*.md")) == []
    # Also test only one colon.
    result2 = _run_save(tmp_path, "--gate-verdict", "tests:done")
    assert result2.returncode == 2
    assert "error:" in result2.stderr.lower()


# ---------------------------------------------------------------------------
# change_kinds — writeup records the derived value and single-sources the gate
# ---------------------------------------------------------------------------


def test_work_writeup_records_change_kinds_and_single_sources_gate() -> None:
    text = _read_skill()
    sec = _section(text, "### 4.1 ", "### 4.2 ")
    collapsed = " ".join(sec.split())
    assert "change_kinds" in sec
    assert "requires_hard_test_gate" in collapsed
    # Same list / same value wording ensures single-source.
    assert "same" in collapsed.lower()
    assert "change_kinds" in collapsed and "requires_hard_test_gate" in collapsed


# ---------------------------------------------------------------------------
# Override split — helper refuses unnamed waiver, comment distinguishes gates
# ---------------------------------------------------------------------------


def test_override_without_gate_is_refused() -> None:
    from plugins.saga.scripts import issue_progress as ip

    with pytest.raises(ValueError):
        ip._override_line(None, "some rationale")
    with pytest.raises(ValueError):
        ip._override_line("", "some rationale")
    with pytest.raises(ValueError):
        ip._override_line("unknown-gate", "rationale")
    # Absent rationale yields no line, not a raise.
    assert ip._override_line("doc-review", None) is None
    assert ip._override_line("doc-review", "") is None
    assert ip._override_line("review-gate", None) is None


def test_override_renders_distinguishable_labels() -> None:
    from plugins.saga.scripts import issue_progress as ip

    doc_comment = ip.render_issue_comment(
        event="phase",
        issue_ref="o/r#1",
        destination="pr",
        doc_review_override="doc rationale",
    )
    review_comment = ip.render_issue_comment(
        event="phase",
        issue_ref="o/r#1",
        destination="pr",
        review_gate_override="review rationale",
    )
    assert "doc review override" in doc_comment
    assert "review rationale" not in doc_comment
    assert "review gate override" in review_comment
    assert "doc rationale" not in review_comment
    # Both distinguishable when both present.
    both = ip.render_issue_comment(
        event="phase",
        issue_ref="o/r#1",
        destination="pr",
        doc_review_override="doc",
        review_gate_override="rev",
    )
    assert "doc review override" in both
    assert "review gate override" in both
    assert both.count("override") == 2


def test_issue_progress_cli_both_flags_render() -> None:
    cmd = [
        sys.executable,
        str(ROOT / "plugins" / "saga" / "scripts" / "issue_progress.py"),
        "--event",
        "phase",
        "--issue-ref",
        "o/r#1",
        "--destination",
        "pr",
        "--doc-review-override",
        "doc override text",
        "--review-gate-override",
        "review override text",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert "doc review override" in result.stdout
    assert "review gate override" in result.stdout


# ---------------------------------------------------------------------------
# Anti-regression — merge confirmation, four outcomes, programmatic writes nothing
# ---------------------------------------------------------------------------


def test_merge_confirmation_still_present() -> None:
    text = _read_skill()
    # 5.4 lists four ceremony runs with --operator-confirmed on merge and branch_delete.
    assert "run --operator-confirmed merge" in text
    assert "run --operator-confirmed branch_delete" in text


def test_four_typed_review_outcomes_still_pinned() -> None:
    text = _read_skill()
    gate = _section(text, "### 5.3 ", "### 5.4 ")
    outcomes = tuple(re.findall(r"^- \*\*`([^`]+)`\*\* —", gate, flags=re.MULTILINE))
    assert outcomes == (
        "accepted",
        "repairs_requested",
        "cycle_cap_best_available",
        "review_incomplete",
    )


def test_programmatic_review_writes_nothing_still_pinned() -> None:
    text = CODE_REVIEW_SKILL.read_text(encoding="utf-8")
    # Multiple phrasings exist; check the canonical one.
    assert "ZERO durable writes" in text or "ZERO file writes" in text
    # Work's 5.2 also states the caller owns persistence.
    work = _read_skill()
    assert (
        "programmatic" in work.lower()
        and "writes nothing" in work.lower()
        or "caller owns persistence" in work.lower()
    )
    sec52 = _section(work, "### 5.2 ", "### 5.3 ")
    assert "outcome" in sec52.lower()


# ---------------------------------------------------------------------------
# Phase-4 skill contracts — gate verdict validation and override naming
# ---------------------------------------------------------------------------


def test_skill_names_gate_verdict_validation_at_save() -> None:
    text = _read_skill()
    sec = _section(text, "### 4.2 ", "### 4.3 ")
    collapsed = " ".join(sec.split()).lower()
    assert "parse_gate_verdict" in collapsed
    assert "refuses" in collapsed or "refuse" in collapsed
    assert "error:" in collapsed
    assert "exit 2" in collapsed


def test_skill_override_flag_names_its_gate() -> None:
    text = _read_skill()
    # Phase 1.3 doc-review gate uses doc flag, 5.3 review gate uses review flag.
    assert "--doc-review-override" in text
    assert "--review-gate-override" in text
    # 4.3 explains the two flags map to distinct labels.
    sec43 = _section(text, "### 4.3 ", "### 4.4 ")
    assert "doc review override" in sec43
    assert "review gate override" in sec43
