"""Tests for text_helpers module."""
# ruff: noqa: E402

import sys
from pathlib import Path

# Add the scripts directory to the path so we can import text_helpers
scripts_path = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_path))

from text_helpers import pluralize


def test_pluralize_singular():
    """Test that count of 1 returns the singular form."""
    result = pluralize("cat", 1)
    assert result == "cat"


def test_pluralize_regular_plural():
    """Test that count of 2 returns the regular plural form (word + s)."""
    result = pluralize("cat", 2)
    assert result == "cats"


def test_pluralize_custom_plural():
    """Test that custom plural form is used when provided."""
    result = pluralize("child", 2, plural="children")
    assert result == "children"


def test_pluralize_zero_count():
    """Test that count of 0 returns the plural form."""
    result = pluralize("cat", 0)
    assert result == "cats"


def test_pluralize_empty_string():
    """Test that empty string returns empty string regardless of count."""
    result = pluralize("", 5)
    assert result == ""
