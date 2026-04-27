"""Tests for dict helper utilities."""

from scripts.dict_helpers import get_nested


def test_get_nested_returns_happy_path_value():
    """Test basic nested dict lookup returns correct value."""
    assert get_nested({"a": {"b": 1}}, "a.b") == 1


def test_get_nested_returns_default_for_missing_key():
    """Test missing key returns specified default."""
    assert get_nested({"a": {"b": 1}}, "a.c", default=-1) == -1


def test_get_nested_returns_default_when_step_is_not_dict():
    """Test that stepping into non-dict returns default."""
    assert get_nested({"a": 1}, "a.b") is None


def test_get_nested_empty_path_returns_entire_data():
    """Test that empty path returns the entire dict unchanged."""
    data = {"a": 1}
    assert get_nested(data, "") == {"a": 1}
    assert get_nested({}, "") == {}


def test_get_nested_supports_three_or_more_levels():
    """Test traversal through 3+ levels of nesting."""
    data = {"a": {"b": {"c": {"d": "value"}}}}
    assert get_nested(data, "a.b.c.d") == "value"
