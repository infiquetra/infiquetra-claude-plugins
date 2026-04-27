"""Unit tests for text_helpers.py."""

import sys
from pathlib import Path

# Add repo root to path so `scripts` is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.text_helpers import pluralize


class TestPluralize:
    """Tests for pluralize()."""

    def test_returns_singular_when_count_is_one(self) -> None:
        """count == 1 returns the word unchanged."""
        assert pluralize("cat", 1) == "cat"

    def test_adds_s_for_regular_plural(self) -> None:
        """Default plural appends 's'."""
        assert pluralize("cat", 2) == "cats"

    def test_uses_custom_plural_when_provided(self) -> None:
        """Explicit plural override is returned for non-one counts."""
        assert pluralize("child", 2, plural="children") == "children"

    def test_treats_zero_as_plural(self) -> None:
        """Zero count produces the plural form."""
        assert pluralize("cat", 0) == "cats"

    def test_returns_empty_string_regardless_of_count(self) -> None:
        """Empty word returns empty string for any count or plural override."""
        assert pluralize("", 5) == ""
        assert pluralize("", 1) == ""
        assert pluralize("", 2, plural="children") == ""
