"""Unit tests for scripts/text_helpers.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from text_helpers import pluralize


class TestPluralize:
    """Test pluralize() text helper."""

    def test_pluralize_singular(self):
        """Test singular count returns word unchanged."""
        assert pluralize("cat", 1) == "cat"

    def test_pluralize_regular_plural(self):
        """Test regular plural by appending 's'."""
        assert pluralize("cat", 2) == "cats"

    def test_pluralize_custom_plural(self):
        """Test custom plural form when provided."""
        assert pluralize("child", 2, plural="children") == "children"

    def test_pluralize_zero_count_uses_plural_form(self):
        """Test zero count uses plural form (not singular)."""
        assert pluralize("cat", 0) == "cats"

    def test_pluralize_empty_string_returns_empty(self):
        """Test empty string always returns empty regardless of count."""
        assert pluralize("", 5) == ""
