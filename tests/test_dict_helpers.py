"""Unit tests for dict_helpers.py."""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dict_helpers import get_nested


def test_get_nested_returns_value_for_happy_path():
    """Test that get_nested returns the value for a valid path."""
    data = {"a": {"b": 1}}
    result = get_nested(data, "a.b")
    assert result == 1


def test_get_nested_returns_default_for_missing_key():
    """Test that get_nested returns default when key is missing."""
    data = {"a": {"b": 1}}
    result = get_nested(data, "a.c", default=-1)
    assert result == -1


def test_get_nested_returns_default_when_stepping_into_non_dict():
    """Test that get_nested returns default when traversing into a non-dict value."""
    data = {"a": 1}
    result = get_nested(data, "a.b")
    assert result is None


def test_get_nested_returns_data_for_empty_path():
    """Test that get_nested returns data unchanged for empty path."""
    data = {}
    result = get_nested(data, "")
    assert result == {}
    assert result is data


def test_get_nested_supports_three_or_more_levels():
    """Test that get_nested supports deeply nested paths (3+ levels)."""
    data = {"a": {"b": {"c": "value"}}}
    result = get_nested(data, "a.b.c")
    assert result == "value"
    # Verify no mutation occurred
    assert data == {"a": {"b": {"c": "value"}}}
