"""Unit tests for dict_helpers.py."""

import sys
from pathlib import Path

# Add scripts directory to path for non-package import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from dict_helpers import get_nested


class TestGetNested:
    """Tests for get_nested()."""

    def test_get_nested_happy_path(self) -> None:
        """Basic dotted lookup returns the nested value."""
        data = {"a": {"b": 1}}
        assert get_nested(data, "a.b") == 1

    def test_get_nested_missing_key_returns_default(self) -> None:
        """Missing key at any depth returns the supplied default."""
        data = {"a": {"b": 1}}
        assert get_nested(data, "a.c", default=-1) == -1

    def test_get_nested_non_dict_step_returns_default(self) -> None:
        """Stepping into a non-dict returns None (default)."""
        data = {"a": 1}
        assert get_nested(data, "a.b") is None

    def test_get_nested_empty_path_returns_data(self) -> None:
        """Empty path returns the entire dict without copying."""
        data = {"x": 1}
        result = get_nested(data, "")
        assert result is data

    def test_get_nested_three_plus_levels(self) -> None:
        """Traversal works for three or more levels of nesting."""
        data = {"a": {"b": {"c": {"d": "found"}}}}
        assert get_nested(data, "a.b.c.d") == "found"

        # Verify no mutation occurred during traversal
        assert data == {"a": {"b": {"c": {"d": "found"}}}}
