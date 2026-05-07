"""Unit tests for text_helpers.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from text_helpers import pluralize  # noqa: E402


def test_pluralize_returns_word_for_singular_count():
    """Singular count returns the word unchanged."""
    assert pluralize("cat", 1) == "cat"


def test_pluralize_appends_s_for_regular_plural():
    """Plural count appends 's' when no custom plural provided."""
    assert pluralize("cat", 2) == "cats"


def test_pluralize_uses_custom_plural_when_provided():
    """Custom plural is used when provided for non-singular counts."""
    assert pluralize("child", 2, plural="children") == "children"


def test_pluralize_treats_zero_as_plural():
    """Zero count is treated as plural (appends 's')."""
    assert pluralize("cat", 0) == "cats"


def test_pluralize_returns_empty_string_regardless_of_count():
    """Empty string input returns empty string for any count."""
    assert pluralize("", 5) == ""
    assert pluralize("", 1, plural="ignored") == ""
