"""Unit tests for text_helpers.py."""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from text_helpers import pluralize


def test_pluralize_returns_word_for_singular_count():
    """Test that singular count returns word unchanged."""
    assert pluralize("cat", 1) == "cat"
    assert pluralize("dog", 1) == "dog"
    assert pluralize("apple", 1) == "apple"


def test_pluralize_adds_s_for_regular_plural():
    """Test that non-singular count without custom plural adds 's'."""
    assert pluralize("cat", 2) == "cats"
    assert pluralize("dog", 0) == "dogs"
    assert pluralize("apple", 3) == "apples"


def test_pluralize_uses_custom_plural_for_non_singular_count():
    """Test that custom plural is used when provided and count != 1."""
    assert pluralize("child", 2, plural="children") == "children"
    assert pluralize("child", 0, plural="children") == "children"
    assert pluralize("child", 5, plural="children") == "children"


def test_pluralize_zero_count_uses_plural_form():
    """Test that zero count uses plural form (regular or custom)."""
    # Regular plural
    assert pluralize("cat", 0) == "cats"
    assert pluralize("dog", 0) == "dogs"
    # Custom plural
    assert pluralize("child", 0, plural="children") == "children"
    assert pluralize("ox", 0, plural="oxen") == "oxen"


def test_pluralize_empty_string_returns_empty_string():
    """Test that empty string returns empty regardless of count."""
    assert pluralize("", 5) == ""
    assert pluralize("", 1) == ""
    assert pluralize("", 0) == ""
    assert pluralize("", 2, plural="children") == ""
    assert pluralize("", 3, plural="oxen") == ""


def test_pluralize_singular_ignores_custom_plural():
    """Test that singular count ignores custom plural even when provided."""
    assert pluralize("child", 1, plural="children") == "child"
    assert pluralize("ox", 1, plural="oxen") == "ox"
