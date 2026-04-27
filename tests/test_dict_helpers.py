"""Tests for dict helper utilities."""

from scripts.dict_helpers import get_nested


def test_get_nested_happy_path():
    """Test that a dotted path returns the nested value."""
    assert get_nested({"a": {"b": 1}}, "a.b") == 1


def test_get_nested_missing_key_returns_default():
    """Test that a missing key returns the provided default."""
    assert get_nested({"a": {"b": 1}}, "a.c", default=-1) == -1


def test_get_nested_non_dict_step_returns_default():
    """Test that stepping into a non-dict returns the default."""
    assert get_nested({"a": 1}, "a.b") is None


def test_get_nested_empty_path_returns_data():
    """Test that an empty path returns the input dict without copying."""
    data = {}
    assert get_nested(data, "") is data


def test_get_nested_three_or_more_levels():
    """Test that deeply nested lookups work for 3+ levels."""
    assert get_nested({"a": {"b": {"c": {"d": 4}}}}, "a.b.c.d") == 4
