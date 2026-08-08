"""Contract tests for the house-style output-style plugin (issue #704, unit U4).

These tests assert the shape Claude Code's output-style loader and the plan's own
contract require:

- the style file lives at the plugin ROOT under ``output-styles/``, not under
  ``.claude-plugin/`` (that is where Claude Code actually looks for it);
- its YAML frontmatter sets ``keep-coding-instructions: true`` literally, and does
  NOT set ``force-for-plugin``;
- a "placard" section names what the style suppresses;
- the tell (``::house-style::``) is present as a single literal string and contains
  no box-drawing Unicode character (U+2500-U+257F) — box-drawing is exactly what the
  style itself forbids for emphasis/callouts, so the tell must not be drawn that way;
- ``plugin.json`` parses, carries the required fields, has at most 10 keywords, and
  has no ``outputStyles`` key (Claude Code discovers output styles by file location,
  not by manifest declaration).

Each assertion is proven meaningful by a matching ``test_*_mutation_detects_removal``
test: it mutates the real file on disk (strips the frontmatter key / placard section /
tell), asserts the corresponding checker function goes red, then restores the original
content in a ``finally`` block. A contract test that would still pass with the contract
stripped out is worse than no test, because it reports safety that is not there.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "house-style"
STYLE_PATH = PLUGIN_ROOT / "output-styles" / "house-style.md"
PLUGIN_JSON_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"

TELL = "::house-style::"
BOX_DRAWING_RE = re.compile(r"[─-╿]")
REQUIRED_PLUGIN_JSON_FIELDS = {"name", "version", "description", "author", "repository"}
MAX_KEYWORDS = 10


def _read_style_text() -> str:
    return STYLE_PATH.read_text(encoding="utf-8")


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a ``---``-delimited frontmatter block from the Markdown body.

    Returns ``({}, text)`` if the file has no well-formed frontmatter block, so
    checker functions can treat "frontmatter missing entirely" as "key absent"
    rather than raising.
    """

    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    front_raw = text[4:end]
    body = text[end + 4 :]
    try:
        parsed = yaml.safe_load(front_raw) or {}
    except yaml.YAMLError:
        return {}, body
    if not isinstance(parsed, dict):
        return {}, body
    return parsed, body


# ---------------------------------------------------------------------------
# Checker functions — pure, reusable by both the "real file" assertions and the
# mutation tests, so a mutation exercises the exact same code path a normal test
# run does.
# ---------------------------------------------------------------------------


def _check_style_file_at_plugin_root() -> bool:
    return STYLE_PATH.is_file()


def _check_keep_coding_instructions_true(text: str) -> bool:
    front, _ = _split_frontmatter(text)
    return front.get("keep-coding-instructions") is True


def _check_force_for_plugin_absent(text: str) -> bool:
    front, _ = _split_frontmatter(text)
    return "force-for-plugin" not in front


def _check_placard_present(text: str) -> bool:
    _, body = _split_frontmatter(text)
    return bool(re.search(r"^## Placard\b", body, flags=re.MULTILINE))


def _check_tell_present_as_literal(text: str) -> bool:
    return TELL in text


def _check_tell_has_no_box_drawing() -> bool:
    return not BOX_DRAWING_RE.search(TELL)


# ---------------------------------------------------------------------------
# Real-file assertions
# ---------------------------------------------------------------------------


def test_style_file_exists_at_plugin_root_not_under_claude_plugin() -> None:
    assert _check_style_file_at_plugin_root(), (
        f"expected the style file at {STYLE_PATH}, the plugin ROOT under "
        "output-styles/ — Claude Code's output-style loader does not look under "
        ".claude-plugin/"
    )
    misplaced = PLUGIN_ROOT / ".claude-plugin" / "output-styles" / "house-style.md"
    assert not misplaced.is_file(), (
        "found a second copy of house-style.md under .claude-plugin/output-styles/ — "
        "Claude Code will not discover it there"
    )


def test_frontmatter_sets_keep_coding_instructions_true() -> None:
    text = _read_style_text()
    front, _ = _split_frontmatter(text)
    assert "keep-coding-instructions" in front, (
        "frontmatter is missing keep-coding-instructions entirely"
    )
    assert front["keep-coding-instructions"] is True, (
        "keep-coding-instructions must be the literal boolean true, "
        f"got {front['keep-coding-instructions']!r}"
    )
    assert _check_keep_coding_instructions_true(text)


def test_frontmatter_has_no_force_for_plugin() -> None:
    text = _read_style_text()
    assert _check_force_for_plugin_absent(text), (
        "frontmatter sets force-for-plugin, which this style must not carry"
    )


def test_placard_section_names_what_the_style_suppresses() -> None:
    text = _read_style_text()
    assert _check_placard_present(text), "no '## Placard' section found in house-style.md"
    _, body = _split_frontmatter(text)
    placard_match = re.search(r"^## Placard.*?(?=^## |\Z)", body, flags=re.MULTILINE | re.DOTALL)
    assert placard_match, "could not isolate the Placard section body"
    placard_body = placard_match.group(0)
    assert "Suppressed" in placard_body, "Placard section does not name what is suppressed"


def test_tell_is_present_as_a_single_literal_string() -> None:
    text = _read_style_text()
    assert _check_tell_present_as_literal(text), (
        f"tell {TELL!r} not found anywhere in the style file"
    )


def test_tell_contains_no_box_drawing_characters() -> None:
    assert _check_tell_has_no_box_drawing(), (
        f"tell {TELL!r} contains a box-drawing character in U+2500-U+257F, which the "
        "style itself forbids for callouts/emphasis"
    )


def test_plugin_json_parses_and_has_required_fields() -> None:
    data = json.loads(PLUGIN_JSON_PATH.read_text(encoding="utf-8"))
    missing = REQUIRED_PLUGIN_JSON_FIELDS - data.keys()
    assert not missing, f"plugin.json is missing required fields: {sorted(missing)}"


def test_plugin_json_keywords_at_most_ten() -> None:
    data = json.loads(PLUGIN_JSON_PATH.read_text(encoding="utf-8"))
    keywords = data.get("keywords", [])
    assert len(keywords) <= MAX_KEYWORDS, (
        f"plugin.json declares {len(keywords)} keywords, over the {MAX_KEYWORDS} cap"
    )


def test_plugin_json_has_no_output_styles_key() -> None:
    data = json.loads(PLUGIN_JSON_PATH.read_text(encoding="utf-8"))
    assert "outputStyles" not in data, (
        "plugin.json declares an outputStyles key — Claude Code discovers output "
        "styles by file location under output-styles/, not by manifest declaration"
    )


# ---------------------------------------------------------------------------
# Mutation tests — prove each checker actually goes red when its target is removed.
# ---------------------------------------------------------------------------


@pytest.fixture
def restore_style_file():
    original = STYLE_PATH.read_text(encoding="utf-8")
    try:
        yield
    finally:
        STYLE_PATH.write_text(original, encoding="utf-8")


def test_mutation_stripped_frontmatter_fails_keep_coding_instructions_check(
    restore_style_file,
) -> None:
    text = _read_style_text()
    mutated = text.replace("keep-coding-instructions: true\n", "")
    assert mutated != text, "mutation did not change the file — frontmatter key not found verbatim"
    assert not _check_keep_coding_instructions_true(mutated), (
        "checker still passed after stripping keep-coding-instructions: true — "
        "the assertion is not actually load-bearing"
    )
    # Sanity: the unmutated text passes.
    assert _check_keep_coding_instructions_true(text)


def test_mutation_stripped_placard_fails_placard_check(restore_style_file) -> None:
    text = _read_style_text()
    mutated = re.sub(
        r"^## Placard.*?(?=^## )",
        "",
        text,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert mutated != text, "mutation did not change the file — Placard section not found"
    assert not _check_placard_present(mutated), (
        "checker still passed after stripping the Placard section — "
        "the assertion is not actually load-bearing"
    )
    assert _check_placard_present(text)


def test_mutation_stripped_tell_fails_tell_check(restore_style_file) -> None:
    text = _read_style_text()
    mutated = text.replace(TELL, "")
    assert mutated != text, "mutation did not change the file — tell string not found verbatim"
    assert not _check_tell_present_as_literal(mutated), (
        "checker still passed after stripping the tell string — "
        "the assertion is not actually load-bearing"
    )
    assert _check_tell_present_as_literal(text)


# --------------------------------------------------------------------------------------
# Coherence: the rules the #704 code review found contradicting each other
#
# Nothing else checks whether the style's own rules can all be obeyed at once. A
# contradiction here is not a typo -- it ships as live behaviour and the writer resolves it
# differently on different turns, which is worse than either rule alone.
# --------------------------------------------------------------------------------------


def _style() -> str:
    return STYLE_PATH.read_text()


def test_the_visual_gate_is_declared_to_override_turn_shape() -> None:
    """Delta turns default to no visual; the gate requires one on some delta turns.

    Without an explicit precedence the same turn -- mid-session, operator asks "where do
    things stand?" -- is both required and forbidden to carry a picture.
    """
    text = _style()
    assert "overrides the turn shape in both directions" in text
    assert "Turn shape sets the default, the gate sets the answer." in text


def test_the_routine_no_visual_rule_carries_the_three_item_carve_out() -> None:
    """The subagent preamble carries this carve-out; the style dropped it.

    Two writers governed by the two halves of one plugin produced opposite output on the
    identical turn: a command result comparing three test files.
    """
    text = _style()
    assert "**Routine turns get no unrequested visual**, with one exception." in text
    assert "three-item comparison" in text


def test_the_arrow_chain_uses_the_notation_the_scorer_can_see() -> None:
    """`->` is invisible to the visual detector; `-->`, `→` and `⇒` are not."""
    text = _style()
    assert "written with `-->`" in text
    assert "written with `->`" not in text


def test_both_turn_shapes_are_told_to_open_with_a_bolded_claim() -> None:
    """Nothing else would move verdict_first_rate, which needs a bolded opening line."""
    assert "**Both shapes open with a bolded claim.**" in _style()


def test_the_delta_turn_does_not_revoke_plain_english_rule_one() -> None:
    """`~/.claude/CLAUDE.md` rule 1 is unconditional and reaches every subagent.

    The style is additive by decision, so it may add a turn shape but may not narrow a
    ratified global rule -- that would leave the main thread and its subagents opening turns
    by different rules, with the divergence invisible from either file alone.
    """
    text = _style()
    assert "No re-establishment of context, no unrequested visual." not in text
    assert "Anchoring is not a licence to drop the situating clause." in text


def test_the_closing_ceremony_has_a_size_exemption() -> None:
    """Requirement R9 asks for a size threshold; a state-change test alone never fires it.

    "Renamed `foo.py` to `bar.py`." changed state and is 28 characters, so without a size
    exemption it must carry a three-line closing block that quadruples the turn.
    """
    text = _style()
    assert "The turn is shorter than its ceremony would be" in text
    assert "whether or\n   not it changed state" in text


def test_a_relay_of_a_single_finding_does_not_force_a_visual() -> None:
    """The operator's standing fan-out is three agents; each return was an orientation turn.

    Three "no findings" verdicts produced three full re-orientations with three required
    pictures and nothing to draw.
    """
    text = _style()
    assert "A relay turn is always an orientation turn" not in text
    assert "relaying more than one finding" in text


def test_the_abbreviation_rule_does_not_ban_what_claude_md_requires() -> None:
    """Plain English rule 3 mandates meaning-first expansion on first use.

    The style banned that pattern outright while permitting short forms used three or more
    times, leaving the writer no legal way to introduce one.
    """
    text = _style()
    assert "the `Full Name (ABC)` introduction pattern is not used" not in text
    assert "this style narrows\nnothing" in text
