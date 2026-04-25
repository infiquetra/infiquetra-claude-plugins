"""Tests for text helper functions."""

from scripts.text_helpers import pluralize


def test_pluralize_singular():
    """Test that singular count returns the word unchanged."""
    assert pluralize("cat", 1) == "cat"


def test_pluralize_regular_plural():
    """Test regular pluralization by adding 's'."""
    assert pluralize("cat", 2) == "cats"


def test_pluralize_custom_plural():
    """Test custom plural form is used when provided."""
    assert pluralize("child", 2, plural="children") == "children"


def test_pluralize_zero_count_uses_plural():
    """Test that zero count uses plural form."""
    assert pluralize("cat", 0) == "cats"


def test_pluralize_empty_string():
    """Test that empty string returns empty string regardless of count."""
    assert pluralize("", 5) == ""
