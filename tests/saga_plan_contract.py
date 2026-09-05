"""Shared readers for Plan's documented save templates, not a shell interpreter.

Both the consumer-row and routing checks must see the same section, fences and
options. Templates contain angle-bracket placeholders and explanatory comments;
we read their declared flags without executing them or certifying shell control flow.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

PLAN_SKILL = Path(__file__).parent.parent / "plugins/saga/skills/plan/SKILL.md"
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\n]*)$")
_OPTION = re.compile(r"--([a-z][a-z0-9-]*)(?:=(.*))?", re.DOTALL)


def plan_phase_53(*, text: str | None = None) -> str:
    """Read exactly Phase 5.3, failing with the source and missing boundary."""
    if text is None:
        text = PLAN_SKILL.read_text(encoding="utf-8")
    boundaries = []
    for heading in ("5.3", "5.4"):
        matches = list(re.finditer(rf"^### {re.escape(heading)}(?:\s|$)", text, re.MULTILINE))
        assert len(matches) == 1, f"{PLAN_SKILL}: expected exactly one ### {heading} heading"
        boundaries.append(matches[0].start())
    start, end = boundaries
    assert start < end, f"{PLAN_SKILL}: ### 5.3 must precede ### 5.4"
    return text[start:end]


def save_blocks(section: str) -> list[str]:
    """Collect save templates in backtick or tilde fences, including titled ones.

    Only line-start fences open blocks; inline backticks cannot shift the pairing.
    Closing fences must use the opening character and at least its run length.
    """
    blocks = []
    opening = ""
    body: list[str] = []
    for line in section.splitlines():
        if not opening:
            match = _FENCE.fullmatch(line)
            if match and not (match[1][0] == "`" and "`" in match[2]):
                opening = match[1]
                body = []
        elif re.fullmatch(rf" {{0,3}}{re.escape(opening[0])}{{{len(opening)},}}\s*", line):
            block = "\n".join(body)
            if re.search(r"\bsaga\.py\s+save\b", block):
                blocks.append(block)
            opening = ""
        else:
            body.append(line)
    assert not opening, f"{PLAN_SKILL} Phase 5.3: unclosed {opening} fence"
    assert blocks, f"{PLAN_SKILL} Phase 5.3: no fenced saga.py save templates found"
    return blocks


def _without_comments(text: str) -> str:
    """Strip a hash only at an unquoted word boundary, as shell comments require.

    shlex's built-in comments mode also strips hashes inside ordinary words
    such as owner/repo#926, so quoting alone is insufficient here.
    """
    result = []
    quote = ""
    escaped = False
    comment = False
    word_start = True
    for char in text:
        if comment:
            if char != "\n":
                continue
            comment = False
        if escaped:
            escaped = False
            result.append(char)
            word_start = False
            continue
        elif char == "\\" and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = ""
        elif char in {"'", '"'}:
            quote = char
        elif char == "#" and word_start:
            comment = True
            continue
        result.append(char)
        word_start = char.isspace() and not quote and not escaped
    return "".join(result)


def save_options(block: str) -> dict[str, list[str]]:
    """Read value-taking long options from a save template, retaining repeats.

    POSIX quoting preserves hashes inside values and ignores shell comments at
    any indentation. Keep line boundaries when removing template continuations
    so a comment cannot consume the next documented line. Values are consumed
    with their option; a quoted value containing a flag is not another option.
    """
    try:
        tokens = shlex.split(_without_comments(block.replace("\\\n", "\n")), posix=True)
    except ValueError as exc:
        raise AssertionError(
            f"{PLAN_SKILL} Phase 5.3: invalid save-template quoting: {exc}"
        ) from exc
    options: dict[str, list[str]] = {}
    index = 0
    while index < len(tokens):
        match = _OPTION.fullmatch(tokens[index])
        index += 1
        if match is None:
            continue
        name, value = match.groups()
        if value is None:
            assert index < len(tokens), f"{PLAN_SKILL} Phase 5.3: --{name} needs a value"
            value = tokens[index]
            index += 1
        options.setdefault(name.replace("-", "_"), []).append(value)
    return options
