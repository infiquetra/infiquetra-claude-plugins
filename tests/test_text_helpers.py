"""Tests for text_helpers.py."""


from scripts.text_helpers import pluralize


def test_pluralize_returns_singular_for_count_one():
    """Test that pluralize returns singular form when count is 1."""
    assert pluralize("cat", 1) == "cat"
    assert pluralize("dog", 1) == "dog"
    assert pluralize("", 1) == ""


def test_pluralize_appends_s_for_regular_plural():
    """Test that pluralize appends 's' for regular plural forms."""
    assert pluralize("cat", 2) == "cats"
    assert pluralize("dog", 5) == "dogs"
    assert pluralize("box", 0) == "boxs"


def test_pluralize_uses_custom_plural_when_provided():
    """Test that pluralize uses custom plural when provided."""
    assert pluralize("child", 2, plural="children") == "children"
    assert pluralize("person", 0, plural="people") == "people"
    assert pluralize("mouse", 1, plural="mice") == "mouse"  # count=1 takes precedence


def test_pluralize_zero_count_uses_plural_form():
    """Test that pluralize uses plural form for zero count."""
    assert pluralize("cat", 0) == "cats"
    assert pluralize("dog", 0) == "dogs"
    assert pluralize("", 0) == ""


def test_pluralize_empty_string_returns_empty_string():
    """Test that pluralize returns empty string for empty input."""
    assert pluralize("", 0) == ""
    assert pluralize("", 1) == ""
    assert pluralize("", 5) == ""
    assert pluralize("", 100, plural="something") == ""