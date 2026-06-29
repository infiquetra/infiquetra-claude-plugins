#!/usr/bin/env python3
"""Shared glyph-card renderer — single status emitter for all saga surfaces (U1, #278).

Derived-on-read from durable engine state: **no operator-writable status field**.
Constant-size, position-stable; every determinable cell traceable to its evidence via indexed
footer.

Two archetypes (KTD6):
  gate-sequence      — static superset of gates; every row rendered regardless of state, so a row
                       whose state is not-reached still occupies its line (R3 constant-size).
  summary-projection — fixed summary rows; height constant regardless of how many dynamic items the
                       caller summarised from a backing projection (R3).

House pattern mirrors ``outcome_projection.py``: pure functions over explicit values, no I/O at
import, stdlib only.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import StrEnum

# ── Wire-state enum (R1) ─────────────────────────────────────────────────────────────────────────
# Frozen wire contract.  These string values are carried in CardRow.state and in every downstream
# serialisation.  They MUST NOT change without a migration.  Renaming a displayed label or swapping
# a glyph is a display-map edit (R9), not a wire-value change.


class CardState(StrEnum):
    """Fixed wire-state vocabulary (R1).

    ``NOT_REACHED`` also covers "unknown" — any cell whose status cannot yet be determined renders
    as the same quiet placeholder glyph.
    """

    DONE = "done"
    IN_PROGRESS = "in-progress"
    BLOCKED = "blocked"
    FAILED = "failed"
    HALTED = "halted"
    NOT_REACHED = "not-reached"  # also used for "unknown" / unresolvable


# ── Display-label-map pattern (R9; mirrors saga.py:73-87) ────────────────────────────────────────
# GLYPH_MAP and OPERATOR_LABEL_MAP are additive dictionaries whose keys are the frozen wire-state
# values.  A key miss falls back to the raw wire string — never errors.  Renaming a label or
# swapping a glyph is an edit to these maps, NOT a stored-state change.
#
# Agent-facing wire markers (CardState enum values) stay distinct from operator-facing vocabulary
# (the values in OPERATOR_LABEL_MAP), satisfying R11.

GLYPH_MAP: dict[str, str] = {
    "done": "✓",
    "in-progress": "◐",
    "blocked": "⊘",
    "failed": "✗",
    "halted": "‖",
    "not-reached": "·",
}

OPERATOR_LABEL_MAP: dict[str, str] = {
    "done": "done",
    "in-progress": "in progress",
    "blocked": "blocked",
    "failed": "failed",
    "halted": "halted",
    "not-reached": "not reached",
}


def display_glyph(state: CardState) -> str:
    """Return the operator-facing glyph for *state*; fall back to the raw wire string on a miss."""
    return GLYPH_MAP.get(state.value, state.value)


def display_state_label(state: CardState) -> str:
    """Return the operator-facing label for *state*; fall back to the raw wire string on a miss."""
    return OPERATOR_LABEL_MAP.get(state.value, state.value)


def is_determinable(state: CardState) -> bool:
    """True iff this cell's status is determinable and should carry a drill-down ref (R12/R13).

    NOT_REACHED / unknown cells are exempt: they render a quiet placeholder and carry neither an
    index tag nor a footer reference.
    """
    return state != CardState.NOT_REACHED


# ── Card-spec data model (KTD6) ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CardRow:
    """One row in a glyph card.

    ``state`` drives the glyph through GLYPH_MAP — a pure function, so there is no field that sets
    the *displayed* status independently of the stored ``state`` (R2/AE2).  ``ref`` is the
    drill-down evidence reference for determinable cells; it is silently ignored for NOT_REACHED
    rows (R13).
    """

    key: str  # stable machine identifier (used for ordering/deduplication by callers)
    label: str  # operator-facing row label
    state: CardState  # wire state — drives glyph, index eligibility, and footer inclusion
    ref: str | None = None  # evidence reference; expected for determinable rows (R12)


@dataclass(frozen=True)
class CardHeader:
    """Surface-identity block rendered above the card body."""

    surface: str  # surface name, e.g. "/work" or "/code-review"
    id: str  # saga id, artifact path, or other stable identifier
    round: int | None = None  # optional iteration/round counter


@dataclass(frozen=True)
class CardSpec:
    """Complete, immutable specification for one glyph card.

    ``archetype`` selects rendering semantics:
      "gate-sequence"      — a static superset of gates; all rows rendered regardless of state.
      "summary-projection" — a fixed summary row set; rendered count is always len(rows).

    Constant height (R3) is a structural property of the spec: the renderer always emits one line
    per row, so the row count in the spec determines the card height — state changes only change
    glyphs, not line count.
    """

    archetype: str  # "gate-sequence" | "summary-projection"
    header: CardHeader
    rows: tuple[CardRow, ...]  # ordered; frozen to prevent accidental mutation after construction


# ── Renderer ─────────────────────────────────────────────────────────────────────────────────────

_CARD_WIDTH = 58  # inner character width (between border edges)


def _hr(char: str = "═") -> str:
    """Horizontal rule of exactly _CARD_WIDTH characters."""
    return char * _CARD_WIDTH


def render(spec: CardSpec) -> str:
    """Render *spec* to a fixed-width, position-stable glyph card string (R3/KTD3).

    Layout:
      ══════════ (top border)
       /surface · id
      ══════════ (header separator)
       G  Row label                              [n]
       ·  Not-reached row
      ══════════ (bottom border)
      [n] evidence reference
      [m] evidence reference

    Every determinable cell receives a short ``[n]`` index; its ``ref`` is listed in a footer block
    beneath the card.  NOT_REACHED cells occupy their row but carry no index tag and no footer entry
    (R13).

    The rendered string is a pure function of *spec* — identical input always produces byte-identical
    output (R2/AE2).  The card body width is constant regardless of which states are set (R3).
    """
    lines: list[str] = []

    # ── Header ──────────────────────────────────────────────────────────────────────────────────
    lines.append(_hr())
    hdr = spec.header
    round_suffix = f" · round {hdr.round}" if hdr.round is not None else ""
    header_text = f" {hdr.surface}{round_suffix} · {hdr.id}"
    # Truncate if the surface/id string is unusually long; never wrap (would break constant width).
    lines.append(header_text[:_CARD_WIDTH])
    lines.append(_hr())

    # ── Body ─────────────────────────────────────────────────────────────────────────────────────
    # Enumerate determinable cells to assign monotonically increasing [n] indices.
    footer_refs: list[tuple[int, str]] = []
    counter = 0

    for row in spec.rows:
        glyph = display_glyph(row.state)

        if is_determinable(row.state):
            counter += 1
            n = counter
            if row.ref:
                footer_refs.append((n, row.ref))
            index_tag = f"[{n}]"
        else:
            index_tag = ""

        # Fixed body layout: " G  {label:<label_width}{index_tag}"
        # Column breakdown: 1 leading space + 1 glyph + 2 spaces + label + index = _CARD_WIDTH
        label_width = _CARD_WIDTH - 4 - len(index_tag)
        if index_tag:
            lines.append(f" {glyph}  {row.label:<{label_width}}{index_tag}")
        else:
            lines.append(f" {glyph}  {row.label:<{label_width}}")

    lines.append(_hr())

    # ── Footer (indexed drill-down refs, KTD3) ───────────────────────────────────────────────────
    # Absent entirely when no determinable cell carries a ref — the card body is the sole output.
    if footer_refs:
        for n, ref in footer_refs:
            lines.append(f"[{n}] {ref}")
        lines.append("")  # trailing blank separates the footer visually from subsequent output

    return "\n".join(lines) + "\n"


# ── Self-test (CI-runnable; mirrors completeness_gate.py::self_test) ─────────────────────────────


def _make_gate_sequence_sample() -> CardSpec:
    """Sample gate-sequence card with five gates in mixed states (done/failed/halted/in-progress/not-reached)."""
    return CardSpec(
        archetype="gate-sequence",
        header=CardHeader(surface="/work", id="saga-demo-1234", round=2),
        rows=(
            CardRow("impl", "Implementation", CardState.DONE, ref="saga-demo-1234/tick-3.md"),
            CardRow("tests", "Tests", CardState.FAILED, ref="saga-demo-1234/gate_verdicts"),
            CardRow("review", "Reviewer panel", CardState.HALTED, ref="saga-demo-1234/review.md"),
            CardRow("ci", "CI", CardState.IN_PROGRESS, ref="github.com/org/repo/actions/1"),
            CardRow("merge", "Merge", CardState.NOT_REACHED, ref=None),
        ),
    )


def _make_summary_projection_sample() -> CardSpec:
    """Sample summary-projection card with four fixed rows."""
    return CardSpec(
        archetype="summary-projection",
        header=CardHeader(surface="/outcome", id="outcome-alpha"),
        rows=(
            CardRow("progress", "Progress", CardState.IN_PROGRESS, ref="outcome-alpha/spec.md"),
            CardRow("frontier", "Ready frontier", CardState.DONE, ref="outcome-alpha/store"),
            CardRow("blocked", "Blocked", CardState.BLOCKED, ref="outcome-alpha/store#blocked"),
            CardRow("attention", "Attention", CardState.NOT_REACHED, ref=None),
        ),
    )


def self_test() -> int:
    """Render sample cards for both archetypes and verify structural invariants (CI-runnable)."""
    gate_spec = _make_gate_sequence_sample()
    gate_card = render(gate_spec)

    summary_spec = _make_summary_projection_sample()
    summary_card = render(summary_spec)

    # 1. All expected glyphs are present in the gate-sequence card.
    for glyph, name in [
        ("✓", "done"),
        ("✗", "failed"),
        ("‖", "halted"),
        ("◐", "in-progress"),
        ("·", "not-reached"),
    ]:
        if glyph not in gate_card:
            print(
                f"UNCAUGHT: glyph '{glyph}' ({name}) missing from gate-sequence card",
                file=sys.stderr,
            )
            return 1
    print("glyphs-present: gate-sequence card contains all five glyphs")

    # 2. Footer indices present for the four determinable rows with refs.
    for n in (1, 2, 3, 4):
        if f"[{n}]" not in gate_card:
            print(f"UNCAUGHT: footer index [{n}] missing from gate-sequence card", file=sys.stderr)
            return 1
    print("footer-indexed: determinable rows carry [1]..[4] indices")

    # 3. NOT_REACHED row (Merge, index 5 would be) carries no footer index.
    if "[5]" in gate_card:
        print(
            "UNCAUGHT: NOT_REACHED 'Merge' row leaked a footer index into the card", file=sys.stderr
        )
        return 1
    print("not-reached-no-index: NOT_REACHED row carries no footer index")

    # 4. Determinism — same spec renders byte-identical output.
    if render(gate_spec) != render(gate_spec):
        print("UNCAUGHT: render is not deterministic", file=sys.stderr)
        return 1
    print("determinism: same spec renders byte-identical output")

    # 5. Constant body line count — body height unchanged between the two renders.
    def _body_line_count(card: str) -> int:
        """Count body rows between the 2nd border (header separator) and 3rd border (bottom)."""
        borders_seen = 0
        in_body = False
        count = 0
        for line in card.splitlines():
            if line.startswith("═"):
                borders_seen += 1
                if borders_seen == 2:
                    in_body = True  # body starts after the header separator
                elif borders_seen == 3:
                    break  # body ends at the bottom border
            elif in_body:
                count += 1
        return count

    gate_body = _body_line_count(gate_card)
    if gate_body != len(gate_spec.rows):
        print(
            f"UNCAUGHT: gate-sequence body has {gate_body} lines, expected {len(gate_spec.rows)}",
            file=sys.stderr,
        )
        return 1
    print(f"constant-size: gate-sequence body = {gate_body} lines (matches spec row count)")

    print("\ngate-sequence card:")
    print(gate_card)
    print("summary-projection card:")
    print(summary_card)
    print("self-test: all checks passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Shared glyph-card renderer — derived-on-read status for saga surfaces (#278)."
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Render sample cards and verify structural invariants (CI-runnable).",
    )
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
