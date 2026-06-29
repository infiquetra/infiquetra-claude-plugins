"""Unit tests for the shared glyph-card renderer and per-surface projections (U1/U3, #278).

Tests are falsifiable and state-driven — they exercise real behaviour rather than keyword
presence.  Conventions mirror tests/test_completeness_gate.py and tests/test_outcome_projection.py:
dynamic module load via importlib.util.spec_from_file_location, factory helpers for specs,
derived-state asserts.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import types
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "plugins" / "saga" / "scripts" / "status_card.py"


def _load() -> ModuleType:
    """Dynamically load status_card as a module (mirrors test_completeness_gate.py)."""
    spec = importlib.util.spec_from_file_location("status_card", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["status_card"] = module
    spec.loader.exec_module(module)
    return module


SC = _load()


# ── Factory helpers ────────────────────────────────────────────────────────────────────────────


def _header(surface: str = "/work", id: str = "saga-1", round: int | None = None) -> object:
    return SC.CardHeader(surface=surface, id=id, round=round)


def _row(
    key: str,
    label: str,
    state_name: str,
    ref: str | None = None,
) -> object:
    state = SC.CardState(state_name)
    return SC.CardRow(key=key, label=label, state=state, ref=ref)


def _gate_spec(rows: list[object]) -> Any:
    return SC.CardSpec(
        archetype="gate-sequence",
        header=_header(),
        rows=tuple(rows),
    )


def _summary_spec(rows: list[object]) -> Any:
    return SC.CardSpec(
        archetype="summary-projection",
        header=_header(surface="/outcome", id="o-1"),
        rows=tuple(rows),
    )


# ── Test 1: both archetypes render a well-formed card ─────────────────────────────────────────


def test_gate_sequence_renders_well_formed() -> None:
    """A gate-sequence card renders with borders, a header, and one body line per row."""
    spec = _gate_spec(
        [
            _row("impl", "Implementation", "done", ref="saga-1/tick.md"),
            _row("tests", "Tests", "in-progress", ref="saga-1/gate_verdicts"),
            _row("merge", "Merge", "not-reached"),
        ]
    )
    card = SC.render(spec)

    lines = card.splitlines()
    # Top border, header, separator, 3 body rows, bottom border = 7 minimum
    assert len(lines) >= 7, f"too few lines: {len(lines)}"
    assert lines[0] == "═" * SC._CARD_WIDTH
    assert "/work" in lines[1]
    assert lines[2] == "═" * SC._CARD_WIDTH
    # Bottom border is the 7th line (index 6)
    assert lines[6] == "═" * SC._CARD_WIDTH


def test_summary_projection_renders_well_formed() -> None:
    """A summary-projection card renders the full fixed row set."""
    spec = _summary_spec(
        [
            _row("progress", "Progress", "in-progress", ref="o-1/spec.md"),
            _row("frontier", "Ready frontier", "done", ref="o-1/store"),
            _row("blocked", "Blocked", "blocked", ref="o-1/store#blocked"),
            _row("attention", "Attention", "not-reached"),
        ]
    )
    card = SC.render(spec)
    assert "Progress" in card
    assert "Ready frontier" in card
    assert "Attention" in card


# ── Test 2: constant size (AE1) ───────────────────────────────────────────────────────────────


def _body_line_count(card: str, card_width: int) -> int:
    """Return the number of body lines between the header separator and the bottom border."""
    borders_seen = 0
    in_body = False
    count = 0
    for line in card.splitlines():
        if line == "═" * card_width:
            borders_seen += 1
            if borders_seen == 2:
                in_body = True  # body starts after the 2nd border (header separator)
            elif borders_seen == 3:
                break  # body ends at the 3rd border (bottom border)
        elif in_body:
            count += 1
    return count


def test_gate_sequence_constant_height_by_state_change() -> None:
    """AE1: gate-sequence card body has the same line count when 1 vs all 5 rows are done."""
    five_rows = [_row(f"g{i}", f"Gate {i}", "done", ref=f"ref-{i}") for i in range(5)]
    spec_all_done = _gate_spec(five_rows)

    one_done = [_row("g0", "Gate 0", "done", ref="ref-0")] + [
        _row(f"g{i}", f"Gate {i}", "not-reached") for i in range(1, 5)
    ]
    spec_one_done = _gate_spec(one_done)

    card_all = SC.render(spec_all_done)
    card_one = SC.render(spec_one_done)

    assert _body_line_count(card_all, SC._CARD_WIDTH) == 5
    assert _body_line_count(card_one, SC._CARD_WIDTH) == 5


def test_summary_projection_constant_height_for_varying_summary_counts() -> None:
    """AE1: a summary-projection card has identical body height for 3-item and 30-item summaries.

    The caller is responsible for collapsing N dynamic items into the fixed row set; the renderer
    always emits exactly len(rows) body lines.
    """

    # 4-row summary-projection regardless of how many items the caller summarised.
    def _make_summary(note: str) -> object:
        return _summary_spec(
            [
                _row("progress", f"Progress ({note})", "in-progress", ref="o/spec"),
                _row("frontier", "Ready frontier", "done", ref="o/store"),
                _row("blocked", "Blocked", "blocked", ref="o/store#b"),
                _row("attention", "Attention", "not-reached"),
            ]
        )

    card_3 = SC.render(_make_summary("3 items"))
    card_30 = SC.render(_make_summary("30 items"))

    # Body height must be identical (4 rows in both cases).
    assert _body_line_count(card_3, SC._CARD_WIDTH) == 4
    assert _body_line_count(card_30, SC._CARD_WIDTH) == 4
    assert _body_line_count(card_3, SC._CARD_WIDTH) == _body_line_count(card_30, SC._CARD_WIDTH)


# ── Test 3: determinism + no writable status field (AE2 / R2) ────────────────────────────────


def test_render_is_deterministic() -> None:
    """AE2: the same CardSpec renders byte-identical output on every call."""
    spec = _gate_spec(
        [
            _row("impl", "Implementation", "done", ref="tick.md"),
            _row("tests", "Tests", "in-progress", ref="gate_verdicts"),
            _row("merge", "Merge", "not-reached"),
        ]
    )
    assert SC.render(spec) == SC.render(spec)
    assert SC.render(spec) == SC.render(spec)


def test_no_writable_status_field_on_card_spec() -> None:
    """AE2/R2: there is no field on CardSpec or CardRow that sets the displayed glyph independently of state.

    The glyph is a pure function of state via GLYPH_MAP — you cannot set a 'display_glyph'
    override on the spec.
    """
    import dataclasses

    row_fields = {f.name for f in dataclasses.fields(SC.CardRow)}
    # These would be violation fields — none should exist.
    forbidden = {"display_glyph", "override_glyph", "status_override", "display_status"}
    assert not (row_fields & forbidden), f"writable display fields found: {row_fields & forbidden}"

    spec_fields = {f.name for f in dataclasses.fields(SC.CardSpec)}
    assert not (spec_fields & forbidden), (
        f"writable display fields found: {spec_fields & forbidden}"
    )


def test_glyph_is_pure_function_of_state() -> None:
    """AE2: changing only the state of a row changes only its glyph in the rendered output."""
    spec_done = _gate_spec([_row("r", "My Gate", "done", ref="r.md")])
    spec_fail = _gate_spec([_row("r", "My Gate", "failed", ref="r.md")])

    card_done = SC.render(spec_done)
    card_fail = SC.render(spec_fail)

    assert SC.GLYPH_MAP["done"] in card_done
    assert SC.GLYPH_MAP["failed"] in card_fail
    # The done glyph must not appear in the failed card's body row.
    body_done = [ln for ln in card_done.splitlines() if "My Gate" in ln][0]
    body_fail = [ln for ln in card_fail.splitlines() if "My Gate" in ln][0]
    assert SC.GLYPH_MAP["done"] in body_done
    assert SC.GLYPH_MAP["failed"] in body_fail
    assert SC.GLYPH_MAP["done"] not in body_fail


# ── Test 4: failure and halt representable (AE9) ─────────────────────────────────────────────


def test_failed_row_renders_glyph_and_footer_ref() -> None:
    """AE9: a row with state=failed renders ✗ and carries a footer ref."""
    spec = _gate_spec([_row("tests", "Tests", "failed", ref="saga/gate_verdicts")])
    card = SC.render(spec)

    assert "✗" in card
    assert "[1] saga/gate_verdicts" in card


def test_halted_row_renders_glyph_and_footer_ref() -> None:
    """AE9: a row with state=halted renders ‖ and carries a footer ref."""
    spec = _gate_spec([_row("review", "Reviewer panel", "halted", ref="saga/review.md")])
    card = SC.render(spec)

    assert "‖" in card
    assert "[1] saga/review.md" in card


def test_failed_and_halted_distinct_glyphs() -> None:
    """AE9: failed and halted use distinct, visually unmistakable glyphs."""
    assert SC.GLYPH_MAP["failed"] != SC.GLYPH_MAP["halted"]
    assert SC.GLYPH_MAP["failed"] == "✗"
    assert SC.GLYPH_MAP["halted"] == "‖"


# ── Test 5: unknown/not-reached carries no footer ref (AE7 / R13) ────────────────────────────


def test_not_reached_row_carries_no_footer_index() -> None:
    """AE7/R13: a NOT_REACHED cell occupies its body line but has no footer index."""
    spec = _gate_spec(
        [
            _row("impl", "Implementation", "done", ref="tick.md"),
            _row("merge", "Merge", "not-reached"),  # no ref; should not appear in footer
        ]
    )
    card = SC.render(spec)

    # Body: done row gets [1], not-reached row gets nothing.
    assert "·" in card  # not-reached glyph present
    assert "[1]" in card  # done row is indexed
    assert "[2]" not in card  # not-reached row is NOT indexed


def test_not_reached_ref_is_silently_ignored() -> None:
    """R13: even if a ref is supplied for a NOT_REACHED row, it must not appear in the footer."""
    spec = _gate_spec([_row("x", "X", "not-reached", ref="should-not-appear-in-footer")])
    card = SC.render(spec)

    assert "should-not-appear-in-footer" not in card
    assert "[1]" not in card


# ── Test 6: label and glyph rename via display maps (AE8 / R9) ───────────────────────────────


def test_glyph_map_rename_changes_only_display_not_wire_state() -> None:
    """AE8/R9: changing GLYPH_MAP changes only the rendered glyph; the wire state value is unchanged."""
    original_glyph = SC.GLYPH_MAP["done"]

    try:
        SC.GLYPH_MAP["done"] = "OK"  # operator-driven glyph swap

        spec = _gate_spec([_row("r", "My Row", "done", ref="r.md")])
        card = SC.render(spec)

        # Rendered card shows the new glyph.
        body_line = [ln for ln in card.splitlines() if "My Row" in ln][0]
        assert "OK" in body_line, "renamed glyph not reflected in render"
        assert original_glyph not in body_line, "old glyph should be gone after map edit"

        # The wire state value on the row is unchanged — it is the frozen enum value "done".
        row = spec.rows[0]
        assert str(row.state) == "done", "wire state value must not change"
        assert row.state == SC.CardState.DONE
    finally:
        SC.GLYPH_MAP["done"] = original_glyph  # restore


def test_operator_label_map_rename_changes_only_label_not_wire_state() -> None:
    """AE8/R9: changing OPERATOR_LABEL_MAP changes only the label returned by display_state_label;
    the stored wire state value is not affected."""
    original_label = SC.OPERATOR_LABEL_MAP["blocked"]

    try:
        SC.OPERATOR_LABEL_MAP["blocked"] = "stalled"

        assert SC.display_state_label(SC.CardState.BLOCKED) == "stalled"
        # Wire value is still the enum member's value string.
        assert SC.CardState.BLOCKED.value == "blocked"
    finally:
        SC.OPERATOR_LABEL_MAP["blocked"] = original_label  # restore


# ── Test 7: --self-test CLI entrypoint (mirrors test_completeness_gate.py::test_self_test_cli) ──


def test_self_test_cli() -> None:
    """The --self-test flag runs clean and emits expected status tokens."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0
    # Self-test must confirm glyphs and structural checks.
    assert "glyphs-present" in result.stdout
    assert "footer-indexed" in result.stdout
    assert "not-reached-no-index" in result.stdout
    assert "determinism" in result.stdout
    assert "self-test: all checks passed" in result.stdout


# ── U3: per-surface projection builders ──────────────────────────────────────────────────────────
# Fixture helpers: use types.SimpleNamespace to mock Saga objects without importing the Saga
# dataclass (which would create a hard import dependency between the test and saga.py internals).

_ABSENT_SENTINEL = object()  # placeholder — the real ABSENT is not a list; isinstance check passes


def _mock_saga(
    saga_id: str = "saga-test-1",
    phase_status: str = "pending",
    review_paths: object = _ABSENT_SENTINEL,
    qa_paths: object = _ABSENT_SENTINEL,
    gate_verdicts: object = _ABSENT_SENTINEL,
    pr_refs: object = _ABSENT_SENTINEL,
    head_sha: str = "",
    destination: str = "plan-only",
) -> object:
    """Build a lightweight mock saga object for projection tests."""
    # Use a non-list sentinel for ABSENT fields (isinstance(obj, list) returns False for sentinel).
    return types.SimpleNamespace(
        saga_id=saga_id,
        phase_status=phase_status,
        review_paths=review_paths,
        qa_paths=qa_paths,
        gate_verdicts=gate_verdicts,
        pr_refs=pr_refs,
        head_sha=head_sha,
        destination=destination,
    )


# ── Fixture text for /code-review tests (based on real artifact format) ───────────────────────────

_CODE_REVIEW_CLEAN = """\
# Code Review — feature-branch (#42)

**Verdict:** **CLEAN** — approved for merge.

Scope Check: CLEAN

## Plan-completion audit

| Unit | Status | Evidence |
|------|--------|----------|
| U1   | DONE   | tests pass |
| U2   | DONE   | reviewer confirmed |

## Lenses applied: security · architecture · testing

Reviewers: Claude (primary) + agy (fan-out second opinion).

## Validators

All validators passed.
"""

_CODE_REVIEW_BLOCKED = """\
# Code Review — hotfix-branch (#99)

**Verdict:** **BLOCKED** — P0 unresolved.

Scope Check: DRIFT DETECTED

## Plan-completion audit

| Unit | Status | Evidence |
|------|--------|----------|
| U1   | DONE   | ok |
| U2   | NOT-DONE | missing tests |

## Lenses: security

Reviewers: Claude.
"""

# ── Fixture text for /qa tests (based on real qa-issue-201-2026-06-07.md format) ──────────────────

_QA_SHIP = """\
---
date: 2026-06-29
target: infiquetra/infiquetra-claude-plugins#278
tier: Standard
reviewed_revision: abc1234
verdict: ship-with-deferred
health_score: 95
type: qa
---

# QA: Gate Status Card (#278)

## Health Score

Overall **95 / 100**.

| risk class | score | result |
|------------|:-----:|--------|
| docs       | 90    | pass   |
| config     | 100   | pass   |
| behavior   | 95    | pass   |

## Ship Verdict

**`ship-with-deferred`** at Standard tier.

## Findings

No P0 or P1 findings.
"""

_QA_FAIL = """\
---
date: 2026-06-29
target: infiquetra/infiquetra-claude-plugins#278
tier: Standard
reviewed_revision: abc1234
verdict: fail
health_score: 40
type: qa
---

# QA: Gate Status Card (#278)

## Health Score

Overall **40 / 100**.

| risk class | score | result |
|------------|:-----:|--------|
| docs       | 30    | fail   |
| behavior   | 50    | pass   |

## Ship Verdict

**`fail`** — P1 unresolved.

## Findings

### F1 — P1 critical regression
Evidence: tests broken.
"""


# ── project_work tests ────────────────────────────────────────────────────────────────────────────


def test_project_work_rows_complete() -> None:
    """project_work produces exactly 8 rows in the correct order."""
    saga = _mock_saga(phase_status="in_progress")
    spec = SC.project_work(saga)
    assert spec.archetype == "gate-sequence"
    labels = [r.label for r in spec.rows]
    assert labels == [
        "Implementation",
        "Doc-review",
        "Tests",
        "Reviewer panel",
        "Scanners",
        "CI",
        "Merge (HITL)",
        "Deploy (HITL)",
    ], f"unexpected row labels: {labels}"


def test_project_work_impl_state_from_phase_status() -> None:
    """project_work Implementation row derives from phase_status."""
    for phase_status, expected in [
        ("complete", "done"),
        ("in_progress", "in-progress"),
        ("pending", "not-reached"),
    ]:
        saga = _mock_saga(phase_status=phase_status)
        spec = SC.project_work(saga)
        impl_row = spec.rows[0]
        assert impl_row.key == "impl"
        assert str(impl_row.state) == expected, (
            f"phase_status={phase_status!r} → expected {expected!r}, got {impl_row.state!r}"
        )


def test_project_work_ae4_tests_cell_in_progress_while_running() -> None:
    """AE4: Tests cell is in-progress when gate_verdicts contains tests:in-progress."""
    saga = _mock_saga(gate_verdicts=["tests:in-progress:saga-1/gate_verdicts"])
    spec = SC.project_work(saga)
    tests_row = next(r for r in spec.rows if r.key == "tests")
    assert tests_row.state == SC.CardState.IN_PROGRESS, (
        f"expected in-progress, got {tests_row.state}"
    )
    assert tests_row.ref == "saga-1/gate_verdicts"


def test_project_work_ae4_tests_cell_done_only_on_gate_verdict_done() -> None:
    """AE4: Tests cell is done only when gate_verdicts shows tests:done — not from checks_run."""
    saga = _mock_saga(gate_verdicts=["tests:done:saga-1/gate_verdicts"])
    spec = SC.project_work(saga)
    tests_row = next(r for r in spec.rows if r.key == "tests")
    assert tests_row.state == SC.CardState.DONE
    assert tests_row.ref == "saga-1/gate_verdicts"


def test_project_work_ae4_tests_cell_failed_on_gate_verdict_failed() -> None:
    """AE4: Tests cell is failed when gate_verdicts shows tests:failed."""
    saga = _mock_saga(gate_verdicts=["tests:failed:saga-1/gate_verdicts"])
    spec = SC.project_work(saga)
    tests_row = next(r for r in spec.rows if r.key == "tests")
    assert tests_row.state == SC.CardState.FAILED
    assert tests_row.ref is not None


def test_project_work_ae4_tests_cell_not_reached_without_gate_verdicts() -> None:
    """AE4: Tests cell is not-reached (no ref) when gate_verdicts is absent."""
    saga = _mock_saga()  # gate_verdicts is _ABSENT_SENTINEL (not a list)
    spec = SC.project_work(saga)
    tests_row = next(r for r in spec.rows if r.key == "tests")
    assert tests_row.state == SC.CardState.NOT_REACHED
    assert tests_row.ref is None


def test_project_work_ae6_reviewer_panel_ref_from_review_paths() -> None:
    """AE6: Reviewer panel cell carries a resolvable ref to the code-review artifact."""
    saga = _mock_saga(review_paths=["docs/reviews/2026-06-29-myfeature-review.md"])
    spec = SC.project_work(saga)
    panel_row = next(r for r in spec.rows if r.key == "panel")
    assert panel_row.state == SC.CardState.DONE
    assert panel_row.ref == "docs/reviews/2026-06-29-myfeature-review.md"


def test_project_work_ae7_undeterminable_cell_not_reached_no_ref() -> None:
    """AE7: a cell whose source signal is absent renders NOT_REACHED with ref=None."""
    saga = _mock_saga()  # no review_paths, gate_verdicts, pr_refs
    spec = SC.project_work(saga)
    for row in spec.rows:
        if row.state == SC.CardState.NOT_REACHED:
            assert row.ref is None, (
                f"row {row.key!r} is NOT_REACHED but has ref {row.ref!r} — violates AE7/R13"
            )


def test_project_work_r12_ci_merge_carry_external_ref() -> None:
    """R12 external-read: determinable CI/Merge (HITL) cells carry a resolvable GitHub ref."""
    pr_ref = "https://github.com/infiquetra/infiquetra-claude-plugins/pull/303"
    saga = _mock_saga(pr_refs=[pr_ref], destination="pr")
    spec = SC.project_work(saga)

    ci_row = next(r for r in spec.rows if r.key == "ci")
    assert ci_row.state == SC.CardState.IN_PROGRESS
    assert ci_row.ref == pr_ref, f"CI ref should be external PR ref, got {ci_row.ref!r}"

    merge_row = next(r for r in spec.rows if r.key == "merge")
    assert merge_row.state == SC.CardState.BLOCKED
    assert merge_row.ref == pr_ref


# ── project_code_review tests ─────────────────────────────────────────────────────────────────────


def test_project_code_review_rows_complete() -> None:
    """project_code_review produces exactly 7 rows."""
    spec = SC.project_code_review(_CODE_REVIEW_CLEAN, ref="docs/reviews/clean.md")
    assert spec.archetype == "gate-sequence"
    assert len(spec.rows) == 7
    labels = [r.label for r in spec.rows]
    assert labels == [
        "Scope",
        "Intent",
        "Lenses",
        "Review fan-out",
        "Merge",
        "Validators",
        "Verdict",
    ]


def test_project_code_review_scope_clean() -> None:
    """'Scope Check: CLEAN' → Scope row is done."""
    spec = SC.project_code_review(_CODE_REVIEW_CLEAN, ref="r.md")
    scope_row = next(r for r in spec.rows if r.key == "scope")
    assert scope_row.state == SC.CardState.DONE
    assert scope_row.ref == "r.md"


def test_project_code_review_scope_drift() -> None:
    """'Scope Check: DRIFT DETECTED' → Scope row is blocked."""
    spec = SC.project_code_review(_CODE_REVIEW_BLOCKED, ref="r.md")
    scope_row = next(r for r in spec.rows if r.key == "scope")
    assert scope_row.state == SC.CardState.BLOCKED


def test_project_code_review_intent_all_done() -> None:
    """Intent row is done when all plan-completion audit tokens are DONE."""
    spec = SC.project_code_review(_CODE_REVIEW_CLEAN, ref="r.md")
    intent_row = next(r for r in spec.rows if r.key == "intent")
    assert intent_row.state == SC.CardState.DONE


def test_project_code_review_intent_not_done_blocked() -> None:
    """Intent row is blocked when any plan-completion audit token is NOT-DONE."""
    spec = SC.project_code_review(_CODE_REVIEW_BLOCKED, ref="r.md")
    intent_row = next(r for r in spec.rows if r.key == "intent")
    assert intent_row.state == SC.CardState.BLOCKED


def test_project_code_review_verdict_clean_is_done() -> None:
    """A 'CLEAN' verdict line → Verdict row is done."""
    spec = SC.project_code_review(_CODE_REVIEW_CLEAN, ref="r.md")
    verdict_row = next(r for r in spec.rows if r.key == "verdict")
    assert verdict_row.state == SC.CardState.DONE
    assert verdict_row.ref == "r.md"


def test_project_code_review_verdict_blocked_is_blocked() -> None:
    """A 'BLOCKED' verdict line → Verdict row is blocked."""
    spec = SC.project_code_review(_CODE_REVIEW_BLOCKED, ref="r.md")
    verdict_row = next(r for r in spec.rows if r.key == "verdict")
    assert verdict_row.state == SC.CardState.BLOCKED


def test_project_code_review_ae7_missing_scope_is_not_reached() -> None:
    """AE7: artifact text without 'Scope Check:' → Scope row is not-reached with no ref."""
    minimal = "# Review\n\n**Verdict:** CLEAN\n"
    spec = SC.project_code_review(minimal, ref="r.md")
    scope_row = next(r for r in spec.rows if r.key == "scope")
    assert scope_row.state == SC.CardState.NOT_REACHED
    assert scope_row.ref is None


# ── project_qa tests ──────────────────────────────────────────────────────────────────────────────


def test_project_qa_rows_complete() -> None:
    """project_qa produces exactly 5 rows."""
    spec = SC.project_qa(_QA_SHIP, ref="docs/qa/qa-278.md")
    assert spec.archetype == "gate-sequence"
    assert len(spec.rows) == 5
    labels = [r.label for r in spec.rows]
    assert labels == ["Risk class", "Checks", "Findings", "Health score", "Ship verdict"]


def test_project_qa_ship_verdict_done() -> None:
    """'verdict: ship-with-deferred' → Ship verdict row is done with ref."""
    spec = SC.project_qa(_QA_SHIP, ref="docs/qa/qa-278.md")
    ship_row = next(r for r in spec.rows if r.key == "ship")
    assert ship_row.state == SC.CardState.DONE
    assert ship_row.ref == "docs/qa/qa-278.md"


def test_project_qa_ae9_fail_verdict_is_failed_not_blocked() -> None:
    """AE9: 'verdict: fail' → Ship verdict row is FAILED (not blocked, not not-reached) with ref."""
    spec = SC.project_qa(_QA_FAIL, ref="docs/qa/qa-fail.md")
    ship_row = next(r for r in spec.rows if r.key == "ship")
    assert ship_row.state == SC.CardState.FAILED, (
        f"expected FAILED for 'verdict: fail', got {ship_row.state!r}"
    )
    assert ship_row.state != SC.CardState.BLOCKED
    assert ship_row.state != SC.CardState.NOT_REACHED
    assert ship_row.ref == "docs/qa/qa-fail.md", "AE9: failure ship verdict must carry ref"


def test_project_qa_risk_class_pass_is_done() -> None:
    """Risk class row is done when all table rows have 'pass' result."""
    spec = SC.project_qa(_QA_SHIP, ref="r.md")
    risk_row = next(r for r in spec.rows if r.key == "risk")
    assert risk_row.state == SC.CardState.DONE


def test_project_qa_risk_class_fail_is_failed() -> None:
    """Risk class row is failed when any table row has 'fail' result."""
    spec = SC.project_qa(_QA_FAIL, ref="r.md")
    risk_row = next(r for r in spec.rows if r.key == "risk")
    assert risk_row.state == SC.CardState.FAILED


def test_project_qa_health_score_from_frontmatter() -> None:
    """Health score row is done and ref encodes the score value."""
    spec = SC.project_qa(_QA_SHIP, ref="docs/qa/qa-278.md")
    health_row = next(r for r in spec.rows if r.key == "health")
    assert health_row.state == SC.CardState.DONE
    assert "95" in (health_row.ref or ""), f"expected score in ref, got {health_row.ref!r}"


def test_project_qa_ae7_missing_frontmatter_is_not_reached() -> None:
    """AE7: qa artifact with no frontmatter → health_score/ship rows are not-reached with no ref."""
    no_frontmatter = "# QA Report\n\n## Findings\n\nNo issues.\n"
    spec = SC.project_qa(no_frontmatter, ref="r.md")
    health_row = next(r for r in spec.rows if r.key == "health")
    ship_row = next(r for r in spec.rows if r.key == "ship")
    assert health_row.state == SC.CardState.NOT_REACHED
    assert health_row.ref is None
    assert ship_row.state == SC.CardState.NOT_REACHED
    assert ship_row.ref is None


# ── AE5: shared-concept label+glyph consistency across surfaces ───────────────────────────────────


# ── U4: project_outcome tests ─────────────────────────────────────────────────────────────────────


def _make_projection(
    *,
    done: int = 3,
    total: int = 10,
    percent: int = 30,
    complete: bool = False,
    frontier: list | None = None,
    blocked: list | None = None,
    attention_count: int = 0,
    state_counts: dict | None = None,
    outcome_id: str = "outcome-test-1",
) -> dict:
    """Build a minimal outcome projection dict mirroring outcome_projection.project() output."""
    return {
        "outcome_id": outcome_id,
        "progress": {"done": done, "total": total, "percent": percent},
        "complete": complete,
        "frontier": frontier if frontier is not None else ["node-A", "node-B"],
        "blocked": blocked if blocked is not None else [],
        "attention": {"count": attention_count, "top": None},
        "state_counts": state_counts if state_counts is not None else {"done": done, "ready": 2},
    }


def test_project_outcome_rows_complete() -> None:
    """project_outcome produces exactly 5 fixed rows in the correct order."""
    proj = _make_projection()
    spec = SC.project_outcome(proj)
    assert spec.archetype == "summary-projection"
    labels = [r.label for r in spec.rows]
    assert labels == [
        "Progress",
        "Ready frontier",
        "Blocked",
        "Attention",
        "Negative terminals",
    ], f"unexpected row labels: {labels}"


def test_project_outcome_ae3_values_equal_dict_exactly() -> None:
    """AE3: project_outcome card values equal the fixture projection dict EXACTLY — no recomputation."""
    proj = _make_projection(done=7, total=20, percent=35, frontier=["n1", "n2", "n3"])
    spec = SC.project_outcome(proj)

    # Progress ref encodes done/total/percent from the dict directly.
    progress_row = next(r for r in spec.rows if r.key == "progress")
    assert "7" in (progress_row.ref or ""), f"done count missing from ref: {progress_row.ref!r}"
    assert "20" in (progress_row.ref or ""), f"total count missing from ref: {progress_row.ref!r}"
    assert "35" in (progress_row.ref or ""), f"percent missing from ref: {progress_row.ref!r}"

    # Frontier ref encodes the frontier count from the dict directly.
    frontier_row = next(r for r in spec.rows if r.key == "frontier")
    assert "3" in (frontier_row.ref or ""), f"frontier count missing from ref: {frontier_row.ref!r}"


def test_project_outcome_ae3_3_and_30_node_same_card_height() -> None:
    """AE3: a 3-node and a 30-node projection dict render the SAME card height (constant-size)."""
    proj_3 = _make_projection(
        done=1, total=3, frontier=["n1"], state_counts={"done": 1, "ready": 1, "blocked": 1}
    )
    proj_30 = _make_projection(
        done=10,
        total=30,
        frontier=[f"n{i}" for i in range(10)],
        state_counts={"done": 10, "ready": 10, "blocked": 5, "dispatched": 5},
    )
    spec_3 = SC.project_outcome(proj_3)
    spec_30 = SC.project_outcome(proj_30)

    # Both produce exactly 5 fixed rows — constant-size regardless of node count.
    assert len(spec_3.rows) == 5
    assert len(spec_30.rows) == 5

    card_3 = SC.render(spec_3)
    card_30 = SC.render(spec_30)
    assert _body_line_count(card_3, SC._CARD_WIDTH) == _body_line_count(card_30, SC._CARD_WIDTH)


def test_project_outcome_complete_is_done() -> None:
    """complete=True in the projection → Progress row is DONE."""
    proj = _make_projection(done=10, total=10, percent=100, complete=True, frontier=[])
    spec = SC.project_outcome(proj)
    progress_row = next(r for r in spec.rows if r.key == "progress")
    assert progress_row.state == SC.CardState.DONE


def test_project_outcome_in_progress_when_not_complete() -> None:
    """complete=False → Progress row is IN_PROGRESS."""
    proj = _make_projection(done=5, total=10, percent=50, complete=False)
    spec = SC.project_outcome(proj)
    progress_row = next(r for r in spec.rows if r.key == "progress")
    assert progress_row.state == SC.CardState.IN_PROGRESS


def test_project_outcome_blocked_nodes_render_blocked() -> None:
    """Blocked list non-empty → Blocked row is BLOCKED."""
    proj = _make_projection(blocked=["node-B", "node-C"])
    spec = SC.project_outcome(proj)
    blocked_row = next(r for r in spec.rows if r.key == "blocked")
    assert blocked_row.state == SC.CardState.BLOCKED
    assert blocked_row.ref is not None


def test_project_outcome_ae9_failed_nodes_render_failed_not_blocked() -> None:
    """AE9: state_counts with failed nodes → Negative-terminals row is FAILED, NOT blocked/not-reached."""
    proj = _make_projection(
        state_counts={"done": 5, "failed": 2, "ready": 1},
    )
    spec = SC.project_outcome(proj)
    neg_row = next(r for r in spec.rows if r.key == "neg_terminals")
    assert neg_row.state == SC.CardState.FAILED, (
        f"expected FAILED for failed nodes, got {neg_row.state!r}"
    )
    assert neg_row.state != SC.CardState.BLOCKED
    assert neg_row.state != SC.CardState.NOT_REACHED
    assert neg_row.ref is not None, "AE9: FAILED neg-terminals row must carry ref"


def test_project_outcome_ae9_halted_nodes_render_halted() -> None:
    """AE9: state_counts with halted nodes (no failed) → Negative-terminals row is HALTED."""
    proj = _make_projection(
        state_counts={"done": 5, "halted": 1, "ready": 2},
    )
    spec = SC.project_outcome(proj)
    neg_row = next(r for r in spec.rows if r.key == "neg_terminals")
    assert neg_row.state == SC.CardState.HALTED, (
        f"expected HALTED for halted nodes, got {neg_row.state!r}"
    )
    assert neg_row.ref is not None, "AE9: HALTED neg-terminals row must carry ref"


def test_project_outcome_ae9_no_neg_terminals_is_done() -> None:
    """No failed/rejected/stalled/halted → Negative-terminals row is DONE."""
    proj = _make_projection(state_counts={"done": 5, "ready": 3})
    spec = SC.project_outcome(proj)
    neg_row = next(r for r in spec.rows if r.key == "neg_terminals")
    assert neg_row.state == SC.CardState.DONE


def test_project_outcome_consumes_dict_not_recomputes() -> None:
    """AE3: project_outcome does not recompute — it renders state_counts from the passed dict.

    A dict with a 'stalled' count in state_counts renders FAILED; if the function recomputed from
    a node list it would miss it.  Only the dict values are authoritative.
    """
    proj = _make_projection(
        state_counts={"done": 3, "stalled": 1},
        frontier=[],
    )
    spec = SC.project_outcome(proj)
    neg_row = next(r for r in spec.rows if r.key == "neg_terminals")
    assert neg_row.state == SC.CardState.FAILED, (
        "stalled in state_counts must yield FAILED — proves dict consumed, not recomputed"
    )


# ── U4: project_resume tests ──────────────────────────────────────────────────────────────────────


def _mock_resume_saga(
    saga_id: str = "saga-resume-1",
    phase_status: str = "in_progress",
    destination: str = "pr",
    blockers: str = "",
    open_questions: object = None,  # None → treated as ABSENT (not a list)
    gate_verdicts: object = None,  # None → treated as ABSENT (not a list)
    next_step: str = "",
) -> object:
    """Build a lightweight mock saga object for project_resume tests."""
    return types.SimpleNamespace(
        saga_id=saga_id,
        phase_status=phase_status,
        destination=destination,
        blockers=blockers,
        open_questions=open_questions,
        gate_verdicts=gate_verdicts,
        next_step=next_step,
    )


def test_project_resume_rows_complete() -> None:
    """project_resume produces exactly 5 fixed rows in the correct order."""
    saga = _mock_resume_saga()
    spec = SC.project_resume(saga)
    assert spec.archetype == "summary-projection"
    labels = [r.label for r in spec.rows]
    assert labels == [
        "Phase/destination",
        "Blockers",
        "Open questions",
        "Last gate verdicts",
        "Route (next-step)",
    ], f"unexpected row labels: {labels}"


def test_project_resume_all_5_rows_map_to_real_fields() -> None:
    """Every rendered row maps to a real saga Phase-3a field — no perpetually-unknown row."""
    saga = _mock_resume_saga(
        phase_status="in_progress",
        destination="pr",
        blockers="waiting on reviewer",
        open_questions=["Is the plan ready?"],
        gate_verdicts=["tests:done:saga-resume-1/gate_verdicts"],
        next_step="Open PR and request review",
    )
    spec = SC.project_resume(saga)

    # Each row key corresponds to a real saga field (no "frontier"/"open_leaves" — outcome-DAG only).
    row_keys = {r.key for r in spec.rows}
    outcome_dag_keys = {"frontier", "open_leaves"}
    assert not (row_keys & outcome_dag_keys), (
        f"project_resume must not contain outcome-DAG rows: found {row_keys & outcome_dag_keys}"
    )
    # All 5 expected keys present.
    expected_keys = {"phase", "blockers", "open_questions", "gate_verdicts", "route"}
    assert expected_keys == row_keys, f"unexpected row keys: {row_keys}"


def test_project_resume_blockers_open_is_blocked() -> None:
    """Non-empty blockers string → Blockers row is BLOCKED [open]."""
    saga = _mock_resume_saga(blockers="Waiting on external approval")
    spec = SC.project_resume(saga)
    blockers_row = next(r for r in spec.rows if r.key == "blockers")
    assert blockers_row.state == SC.CardState.BLOCKED
    assert blockers_row.ref is not None


def test_project_resume_blockers_empty_is_done() -> None:
    """Empty blockers string → Blockers row is DONE [cleared]."""
    saga = _mock_resume_saga(blockers="")
    spec = SC.project_resume(saga)
    blockers_row = next(r for r in spec.rows if r.key == "blockers")
    assert blockers_row.state == SC.CardState.DONE
    assert blockers_row.ref is not None


def test_project_resume_open_questions_present_is_in_progress() -> None:
    """Non-empty open_questions list → Open questions row is IN_PROGRESS."""
    saga = _mock_resume_saga(open_questions=["Q1: Is the API stable?", "Q2: Do we need migration?"])
    spec = SC.project_resume(saga)
    oq_row = next(r for r in spec.rows if r.key == "open_questions")
    assert oq_row.state == SC.CardState.IN_PROGRESS


def test_project_resume_open_questions_empty_is_done() -> None:
    """Empty open_questions list → Open questions row is DONE."""
    saga = _mock_resume_saga(open_questions=[])
    spec = SC.project_resume(saga)
    oq_row = next(r for r in spec.rows if r.key == "open_questions")
    assert oq_row.state == SC.CardState.DONE


def test_project_resume_gate_verdicts_failed_via_parse() -> None:
    """Last gate verdicts routes through parse_gate_verdict — a tests:failed entry → FAILED."""
    saga = _mock_resume_saga(gate_verdicts=["tests:failed:saga-resume-1/gate_verdicts"])
    spec = SC.project_resume(saga)
    gv_row = next(r for r in spec.rows if r.key == "gate_verdicts")
    assert gv_row.state == SC.CardState.FAILED, (
        f"tests:failed entry must yield FAILED gate_verdicts row, got {gv_row.state!r}"
    )
    assert gv_row.ref is not None


def test_project_resume_gate_verdicts_all_done() -> None:
    """All gate verdicts done → Last gate verdicts row is DONE."""
    saga = _mock_resume_saga(
        gate_verdicts=["tests:done:ref1", "ruff:done:ref2"],
    )
    spec = SC.project_resume(saga)
    gv_row = next(r for r in spec.rows if r.key == "gate_verdicts")
    assert gv_row.state == SC.CardState.DONE


def test_project_resume_gate_verdicts_none_is_not_reached() -> None:
    """No gate_verdicts → Last gate verdicts row is NOT_REACHED with no ref."""
    saga = _mock_resume_saga(gate_verdicts=None)
    spec = SC.project_resume(saga)
    gv_row = next(r for r in spec.rows if r.key == "gate_verdicts")
    assert gv_row.state == SC.CardState.NOT_REACHED
    assert gv_row.ref is None


def test_project_resume_route_present_is_done() -> None:
    """Non-empty next_step → Route row is DONE with next_step text as ref."""
    next_step_text = "Open PR and request review from the team"
    saga = _mock_resume_saga(next_step=next_step_text)
    spec = SC.project_resume(saga)
    route_row = next(r for r in spec.rows if r.key == "route")
    assert route_row.state == SC.CardState.DONE
    assert route_row.ref == next_step_text


def test_project_resume_route_absent_is_not_reached() -> None:
    """Empty next_step → Route row is NOT_REACHED with no ref."""
    saga = _mock_resume_saga(next_step="")
    spec = SC.project_resume(saga)
    route_row = next(r for r in spec.rows if r.key == "route")
    assert route_row.state == SC.CardState.NOT_REACHED
    assert route_row.ref is None


def test_project_resume_safe_degradation_all_absent() -> None:
    """Safe degradation: empty/absent blockers/open_questions/gate_verdicts/next_step → no crash.

    Verified states: cleared/done for blockers, done for empty oq, not-reached for gv/route.
    No guessed glyphs on any row.
    """
    saga = _mock_resume_saga(
        blockers="",
        open_questions=[],
        gate_verdicts=None,
        next_step="",
    )
    spec = SC.project_resume(saga)
    # Must not crash; verify each row is a legal CardState value.
    for row in spec.rows:
        assert isinstance(row.state, SC.CardState), (
            f"row {row.key!r} has illegal state {row.state!r}"
        )

    # Safe-degrade specific expectations.
    assert next(r for r in spec.rows if r.key == "blockers").state == SC.CardState.DONE
    assert next(r for r in spec.rows if r.key == "open_questions").state == SC.CardState.DONE
    assert next(r for r in spec.rows if r.key == "gate_verdicts").state == SC.CardState.NOT_REACHED
    assert next(r for r in spec.rows if r.key == "route").state == SC.CardState.NOT_REACHED


def test_project_resume_no_outcome_dag_rows() -> None:
    """project_resume must not contain 'Open leaves' / 'Ready frontier' outcome-DAG rows (P1 fix).

    These are outcome-DAG concepts with no producer in /resume's single-thread reconstruction.
    Including them would render perpetually NOT_REACHED, violating R12/R13.
    """
    saga = _mock_resume_saga()
    spec = SC.project_resume(saga)
    labels_lower = {r.label.lower() for r in spec.rows}
    dag_labels = {"open leaves", "ready frontier", "frontier"}
    assert not (labels_lower & dag_labels), (
        f"project_resume must not contain outcome-DAG rows: found {labels_lower & dag_labels}"
    )


# ── AE5: shared-concept label+glyph consistency across surfaces ───────────────────────────────────


def test_ae5_done_glyph_consistent_across_work_and_qa() -> None:
    """AE5: the DONE glyph from project_work Tests row matches the DONE glyph from project_qa rows.

    Shared concepts use the SAME glyph via the single GLYPH_MAP — this is guaranteed by construction
    (one render site, one map) but the test makes the invariant explicit and falsifiable.
    """
    # Render project_work with tests:done
    saga = _mock_saga(gate_verdicts=["tests:done:gate_verdicts"])
    work_spec = SC.project_work(saga)
    tests_row = next(r for r in work_spec.rows if r.key == "tests")
    work_tests_card = SC.render(
        SC.CardSpec(
            archetype="gate-sequence",
            header=SC.CardHeader(surface="/work", id="s"),
            rows=(tests_row,),
        )
    )

    # Render project_qa with passing verdict (checks row will be DONE)
    qa_spec = SC.project_qa(_QA_SHIP, ref="qa.md")
    checks_row = next(r for r in qa_spec.rows if r.key == "checks")
    qa_checks_card = SC.render(
        SC.CardSpec(
            archetype="gate-sequence",
            header=SC.CardHeader(surface="/qa", id="s"),
            rows=(checks_row,),
        )
    )

    done_glyph = SC.GLYPH_MAP["done"]
    assert done_glyph in work_tests_card, "DONE glyph missing from project_work Tests row"
    assert done_glyph in qa_checks_card, "DONE glyph missing from project_qa Checks row"
