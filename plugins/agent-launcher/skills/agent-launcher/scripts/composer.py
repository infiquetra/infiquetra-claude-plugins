"""Pure terminal-composer inspection for the agent-launcher reuse guard.

The launcher owns the Herdr read and the decision to prompt.  This module owns only the
presentation problem: find the input box in one ANSI viewport and classify its contents without
persisting those contents.  Keeping that parser separate prevents terminal heuristics from growing
inside the session lifecycle code.  The accepted ambiguity is recorded in
``docs/engineering-journal/DECISIONS.md#907-styled-composer-trade``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")

# This is a complete roster, not a fallback table.  A vendor whose input box has not been
# characterised is present with ``None`` and receives an explicit unsupported-vendor result.
# The launcher asserts these keys against its own vendor roster at import time.
COMPOSER_GLYPH_BY_VENDOR: dict[str, str | None] = {
    "claude": "❯",
    "codex": "›",
    "grok": "❯",
    "agy": ">",
    "qwen": ">",
    # No stable composer marker was present in the 2026-08-30 live captures.  Muse could not be
    # launched through the wrapper on that host, and OpenCode presented no composer marker.
    "muse": None,
    "opencode": None,
}

COMPOSER_MARKERS = frozenset(glyph for glyph in COMPOSER_GLYPH_BY_VENDOR.values() if glyph)

# A border may precede the prompt glyph.  These are structural terminal characters, not content.
_LEADING_BORDER_GLYPHS = frozenset("│┃┆┇┊┋╎╏▏▎▍▌▋▊▉█╭╰┌└")
_TRAILING_BORDER_GLYPHS = frozenset("│┃┆┇┊┋╎╏▏▎▍▌▋▊▉█╮╯┐┘")
_HORIZONTAL_RULE_GLYPHS = frozenset("─━═▄▀ ")


class ComposerState(StrEnum):
    """Mutually exclusive outcomes from a successful or unsupported composer parse."""

    EMPTY = "empty"
    STAGED = "staged"
    UNCLASSIFIABLE = "unclassifiable"
    NOT_FOUND = "not_found"
    UNSUPPORTED_VENDOR = "unsupported_vendor"
    READ_FAILED = "read_failed"
    READ_TIMEOUT = "read_timeout"


@dataclass(frozen=True)
class ComposerInspection:
    """A composer outcome and withheld text only when the outcome is staged."""

    state: ComposerState
    text: str | None = None


@dataclass
class _StyleState:
    """The Select Graphic Rendition attributes that make a run client-drawn."""

    intensity: bool = False
    italic: bool = False
    underline: bool = False
    blink: bool = False
    inverse: bool = False
    conceal: bool = False
    strike: bool = False
    foreground: bool = False
    background: bool = False

    @property
    def active(self) -> bool:
        return any(vars(self).values())

    def reset(self) -> None:
        for name in vars(self):
            setattr(self, name, False)

    def apply(self, params: str) -> None:
        codes = [int(code) for code in params.split(";") if code] if params else [0]
        index = 0
        while index < len(codes):
            code = codes[index]
            if code == 0:
                self.reset()
            elif code in (1, 2):
                self.intensity = True
            elif code == 3:
                self.italic = True
            elif code == 4:
                self.underline = True
            elif code in (5, 6):
                self.blink = True
            elif code == 7:
                self.inverse = True
            elif code == 8:
                self.conceal = True
            elif code == 9:
                self.strike = True
            elif code == 22:
                self.intensity = False
            elif code == 23:
                self.italic = False
            elif code == 24:
                self.underline = False
            elif code == 25:
                self.blink = False
            elif code == 27:
                self.inverse = False
            elif code == 28:
                self.conceal = False
            elif code == 29:
                self.strike = False
            elif code == 39:
                self.foreground = False
            elif code == 49:
                self.background = False
            elif 30 <= code <= 38 or 90 <= code <= 97:
                self.foreground = True
                if code == 38 and index + 1 < len(codes):
                    index += 4 if codes[index + 1] == 2 else 2
            elif 40 <= code <= 48 or 100 <= code <= 107:
                self.background = True
                if code == 48 and index + 1 < len(codes):
                    index += 4 if codes[index + 1] == 2 else 2
            index += 1


@dataclass
class _ComposerBlock:
    """One contiguous composer region beginning at a vendor marker."""

    lines: list[str]
    marker_column: int
    ambiguous_empty: bool = False
    adjacent_to_previous: bool = False


def strip_ansi(text: str) -> str:
    """Remove terminal control sequences without changing printable content."""
    return ANSI_RE.sub("", text)


def _without_border(text: str) -> tuple[str, int]:
    """Return row content without a paired box border and its original content column."""
    leading = len(text) - len(text.lstrip())
    candidate = text.lstrip()
    bordered = False
    while candidate and candidate[0] in _LEADING_BORDER_GLYPHS:
        bordered = True
        candidate = candidate[1:].lstrip()
    consumed = len(text) - len(candidate)
    if bordered:
        candidate = candidate.rstrip()
        while candidate and candidate[-1] in _TRAILING_BORDER_GLYPHS:
            candidate = candidate[:-1].rstrip()
    return candidate, max(leading, consumed)


def _has_leading_border(text: str) -> bool:
    candidate = text.lstrip()
    return bool(candidate and candidate[0] in _LEADING_BORDER_GLYPHS)


def _marker_column(line: str, glyph: str) -> int | None:
    candidate, column = _without_border(strip_ansi(line).replace("\xa0", " "))
    return column if candidate.startswith(glyph) else None


def _is_horizontal_rule(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and set(stripped) <= _HORIZONTAL_RULE_GLYPHS


def _is_continuation(line: str, *, marker_column: int) -> bool:
    """Whether terminal geometry proves this row belongs to the current composer box.

    Indentation alone is not proof: vendor status footers use the same indentation as wrapped
    input. Unbordered rows are therefore an ambiguity boundary. A bordered row can continue only
    inside the same box and beyond the marker column.
    """
    clean = strip_ansi(line).replace("\xa0", " ")
    if not clean.strip():
        return False
    candidate, column = _without_border(clean)
    if _is_horizontal_rule(candidate) or candidate[:1] in COMPOSER_MARKERS:
        return False
    return _has_leading_border(clean) and column > marker_column


def _composer_blocks(ansi_text: str, *, glyph: str) -> list[_ComposerBlock]:
    """Return structurally bounded marker blocks in pane order.

    A blank or merely indented row is not absorbed as input. When it follows an otherwise empty
    marker, the empty claim becomes ambiguous instead: that shape can be either viewport chrome
    or a multiline draft, and the viewport supplies no authorship signal that distinguishes them.
    """
    blocks: list[_ComposerBlock] = []
    current: _ComposerBlock | None = None
    separated = True
    for line in ansi_text.splitlines():
        column = _marker_column(line, glyph)
        if column is not None:
            current = _ComposerBlock(
                lines=[line],
                marker_column=column,
                adjacent_to_previous=bool(blocks and not separated),
            )
            blocks.append(current)
            separated = False
            continue
        if current is None:
            if strip_ansi(line).strip():
                separated = True
            continue
        if _is_continuation(line, marker_column=current.marker_column):
            current.lines.append(line)
            separated = False
            continue
        if not _visible_after_marker(current.lines, glyph):
            clean = strip_ansi(line).replace("\xa0", " ")
            if not clean.strip() or _without_border(clean)[1] > current.marker_column:
                current.ambiguous_empty = True
        clean = strip_ansi(line).replace("\xa0", " ")
        candidate, column = _without_border(clean)
        separated = bool(clean.strip()) and (
            _is_horizontal_rule(candidate) or column <= current.marker_column
        )
        current = None
    return blocks


def _visible_after_marker(lines: list[str], glyph: str) -> str:
    clean_lines = [_without_border(strip_ansi(line).replace("\xa0", " "))[0] for line in lines]
    first = clean_lines[0]
    if first.startswith(glyph):
        clean_lines[0] = first[len(glyph) :]
    # Terminal wraps do not add a character to the draft; joining with a newline over-counts it.
    return "".join(line.strip() for line in clean_lines).strip()


def _unstyled_text(lines: list[str], glyph: str) -> str:
    """Printable characters emitted while no Select Graphic Rendition attribute was active."""
    state = _StyleState()
    output: list[str] = []
    for line in lines:
        cursor = 0
        row: list[str] = []
        for sgr in SGR_RE.finditer(line):
            if not state.active:
                row.append(ANSI_RE.sub("", line[cursor : sgr.start()]))
            state.apply(sgr.group(1))
            cursor = sgr.end()
        if not state.active:
            row.append(ANSI_RE.sub("", line[cursor:]))
        candidate, _ = _without_border("".join(row).replace("\xa0", " "))
        if _has_leading_border(strip_ansi(line)) and candidate:
            candidate = candidate.rstrip()
            while candidate and candidate[-1] in _TRAILING_BORDER_GLYPHS:
                candidate = candidate[:-1].rstrip()
        output.append(candidate)
    if output and output[0].startswith(glyph):
        output[0] = output[0][len(glyph) :]
    return "".join(output).strip()


def _classify_block(block: _ComposerBlock, *, glyph: str) -> ComposerInspection:
    visible = _visible_after_marker(block.lines, glyph)
    if not visible:
        if block.ambiguous_empty or block.adjacent_to_previous:
            return ComposerInspection(ComposerState.UNCLASSIFIABLE)
        # An empty box is empty regardless of how the client coloured its marker or background.
        return ComposerInspection(ComposerState.EMPTY, "")
    staged = _unstyled_text(block.lines, glyph)
    if staged:
        # Once any unstyled character proves operator input, the whole visible block is the
        # withheld draft. Styled wrapped rows belong to that same contiguous composer and count.
        return ComposerInspection(ComposerState.STAGED, visible)
    # A fully client-styled non-empty row is byte-indistinguishable from a styled operator draft.
    return ComposerInspection(ComposerState.UNCLASSIFIABLE)


def inspect_composer(ansi_text: str, *, vendor: str) -> ComposerInspection:
    """Inspect the last composer block positionally and let that block decide the outcome.

    The last block is authoritative even when it cannot be classified.  An earlier scrollback echo
    must never stand in for a lower live box merely because the lower block is styled.
    """
    if vendor not in COMPOSER_GLYPH_BY_VENDOR:
        return ComposerInspection(ComposerState.UNSUPPORTED_VENDOR)
    glyph = COMPOSER_GLYPH_BY_VENDOR[vendor]
    if glyph is None:
        return ComposerInspection(ComposerState.UNSUPPORTED_VENDOR)
    blocks = _composer_blocks(ansi_text, glyph=glyph)
    if not blocks:
        return ComposerInspection(ComposerState.NOT_FOUND)
    return _classify_block(blocks[-1], glyph=glyph)


def composer_staged_text(ansi_text: str, *, vendor: str) -> str | None:
    """Compatibility view: staged text, empty string, or None for every other outcome."""
    result = inspect_composer(ansi_text, vendor=vendor)
    if result.state is ComposerState.STAGED:
        return result.text
    if result.state is ComposerState.EMPTY:
        return ""
    return None
