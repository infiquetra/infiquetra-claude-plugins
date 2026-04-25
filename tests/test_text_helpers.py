"""Unit tests for text_helpers.py."""

import sys
from pathlib import Path

# Add scripts directory to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from text_helpers import pluralize


def test_pluralize_singular():
    """Test singular count returns word unchanged."""
    assert pluralize("cat", 1) == "cat"


def test_pluralize_regular_plural():
    """Test plural count returns word + 's'."""
    assert pluralize("cat", 2) == "cats"


def test_pluralize_custom_plural():
    """Test that custom plural overrides default."""
    assert pluralize("child", 2, plural="children") == "children"


def test_pluralize_zero_count():
    """Test zero count uses plural form."""
    assert pluralize("cat", 0) == "cats"


def test_pluralize_empty_string():
    """Test empty word returns empty string regardless of count."""
    assert pluralize("", 5) == ""
