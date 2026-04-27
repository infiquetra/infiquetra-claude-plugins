"""Tests for text helper functions."""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from text_helpers import pluralize


def test_pluralize_returns_singular_for_count_one() -> None:
    """Test that count of 1 returns the word unchanged."""
    assert pluralize("cat", 1) == "cat"


def test_pluralize_adds_s_for_regular_plural() -> None:
    """Test that count != 1 adds 's' by default."""
    assert pluralize("cat", 2) == "cats"


def test_pluralize_uses_custom_plural() -> None:
    """Test that custom plural form is used when provided."""
    assert pluralize("child", 2, plural="children") == "children"


def test_pluralize_zero_uses_plural_form() -> None:
    """Test that zero count uses plural form."""
    assert pluralize("cat", 0) == "cats"


def test_pluralize_empty_string_returns_empty() -> None:
    """Test that empty string returns empty string regardless of count."""
    assert pluralize("", 5) == ""
    assert pluralize("", 1, plural="ignored") == ""
