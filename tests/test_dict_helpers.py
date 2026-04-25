"""Tests for dict_helpers.py."""

from scripts.dict_helpers import get_nested


def test_get_nested_happy_path():
    """Test that get_nested returns the correct value for a valid path."""
    data = {"a": {"b": 1}}
    assert get_nested(data, "a.b") == 1


def test_get_nested_missing_key_returns_default():
    """Test that get_nested returns default when a key is missing."""
    data = {"a": {"b": 1}}
    assert get_nested(data, "a.c", default=-1) == -1


def test_get_nested_non_dict_traversal_returns_default():
    """Test that get_nested returns default when stepping into a non-dict."""
    data = {"a": 1}
    assert get_nested(data, "a.b") is None


def test_get_nested_empty_path_returns_entire_dict():
    """Test that get_nested returns the entire dict for empty path."""
    data = {}
    assert get_nested(data, "") == data

    data2 = {"x": 1}
    assert get_nested(data2, "") == data2


def test_get_nested_deep_nesting():
    """Test that get_nested works with 3+ levels of nesting."""
    data = {"a": {"b": {"c": {"d": 2}}}}
    assert get_nested(data, "a.b.c.d") == 2


def test_get_nested_does_not_mutate_input():
    """Test that get_nested does not modify the source dict."""
    data = {"a": {"b": 1}}
    original_data = {"a": {"b": 1}}
    get_nested(data, "a.b")
    assert data == original_data
