"""Unit tests for the shared glyph-card renderer (U1, #278).

Tests are falsifiable and state-driven — they exercise real behaviour rather than keyword
presence.  Conventions mirror tests/test_completeness_gate.py and tests/test_outcome_projection.py:
dynamic module load via importlib.util.spec_from_file_location, factory helpers for specs,
derived-state asserts.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

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


def _gate_spec(rows: list[object]) -> object:
    return SC.CardSpec(
        archetype="gate-sequence",
        header=_header(),
        rows=tuple(rows),
    )


def _summary_spec(rows: list[object]) -> object:
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
