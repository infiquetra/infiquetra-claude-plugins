"""Tests for text_helpers.py."""

import sys
from pathlib import Path

# Add scripts directory to sys.path to import text_helpers
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from text_helpers import pluralize


def test_pluralize_singular():
    """Test pluralize with count 1 returns singular word."""
    assert pluralize("cat", 1) == "cat"


def test_pluralize_regular_plural():
    """Test pluralize with count != 1 returns regular plural (word + 's')."""
    assert pluralize("cat", 2) == "cats"
    assert pluralize("dog", 0) == "dogs"
    assert pluralize("bird", -1) == "birds"


def test_pluralize_custom_plural():
    """Test pluralize with count != 1 returns custom plural if provided."""
    assert pluralize("child", 2, plural="children") == "children"
    assert pluralize("goose", 0, plural="geese") == "geese"


def test_pluralize_zero_count_uses_plural_form():
    """Test pluralize with count 0 uses plural form."""
    assert pluralize("cat", 0) == "cats"
    assert pluralize("child", 0, plural="children") == "children"


def test_pluralize_empty_string_returns_empty_string():
    """Test pluralize with empty string returns empty string regardless of count."""
    assert pluralize("", 1) == ""
    assert pluralize("", 2) == ""
    assert pluralize("", 0) == ""
