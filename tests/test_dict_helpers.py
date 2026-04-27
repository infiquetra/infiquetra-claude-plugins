"""Unit tests for dict_helpers.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dict_helpers import get_nested


class TestGetNested:
    """Test get_nested function."""

    def test_get_nested_returns_value_for_dotted_path(self):
        """Test successful nested lookup."""
        data = {"a": {"b": 1}}
        result = get_nested(data, "a.b")
        assert result == 1

    def test_get_nested_returns_default_for_missing_key(self):
        """Test missing key returns default value."""
        data = {"a": {"b": 1}}
        result = get_nested(data, "a.c", default=-1)
        assert result == -1

    def test_get_nested_returns_default_when_stepping_into_non_dict(self):
        """Test stepping into a non-dict returns default."""
        data = {"a": 1}
        result = get_nested(data, "a.b")
        assert result is None

    def test_get_nested_empty_path_returns_entire_data(self):
        """Test empty path returns the entire data dict."""
        data = {}
        result = get_nested(data, "")
        assert result == {}
        assert result is data

    def test_get_nested_supports_three_or_more_levels(self):
        """Test deep nesting with 3+ levels."""
        data = {"a": {"b": {"c": {"d": 4}}}}
        result = get_nested(data, "a.b.c.d")
        assert result == 4
