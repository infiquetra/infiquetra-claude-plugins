"""Unit tests for dict_helpers.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dict_helpers import get_nested


class TestGetNested:
    """Test get_nested function."""

    def test_get_nested_happy_path(self):
        """Test basic nested lookup returns the correct value."""
        data = {"a": {"b": 1}}
        result = get_nested(data, "a.b")
        assert result == 1

    def test_get_nested_missing_key_returns_default(self):
        """Test missing key returns the provided default value."""
        data = {"a": {"b": 1}}
        result = get_nested(data, "a.c", default=-1)
        assert result == -1

    def test_get_nested_non_dict_step_returns_default(self):
        """Test stepping into a non-dict returns default."""
        data = {"a": 1}
        result = get_nested(data, "a.b")
        assert result is None

    def test_get_nested_empty_path_returns_data(self):
        """Test empty path returns the entire data dict."""
        data = {}
        result = get_nested(data, "")
        assert result == {}

    def test_get_nested_three_level_lookup(self):
        """Test three-level nested lookup."""
        data = {"a": {"b": {"c": 2}}}
        result = get_nested(data, "a.b.c")
        assert result == 2
