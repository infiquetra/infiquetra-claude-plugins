"""Tests for scripts.text_helpers."""

import sys
from pathlib import Path

# Add repo root to path so "scripts" is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.text_helpers import pluralize


class TestPluralize:
    def test_pluralize_singular(self) -> None:
        """count == 1 returns word unchanged."""
        result = pluralize("cat", 1)
        assert result == "cat"

    def test_pluralize_regular_plural(self) -> None:
        """count != 1 without custom plural appends 's'."""
        result = pluralize("cat", 2)
        assert result == "cats"

    def test_pluralize_custom_plural(self) -> None:
        """count != 1 with custom plural returns the custom form."""
        result = pluralize("child", 2, plural="children")
        assert result == "children"

    def test_pluralize_zero_count(self) -> None:
        """count == 0 returns plural form."""
        result = pluralize("cat", 0)
        assert result == "cats"

    def test_pluralize_empty_string(self) -> None:
        """Empty word returns empty string regardless of count."""
        result = pluralize("", 5)
        assert result == ""
