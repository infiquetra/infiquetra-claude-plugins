"""Tests for dict_helpers.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dict_helpers import get_nested


def test_get_nested_happy_path():
    """Test basic dotted path lookup returns the nested value."""
    assert get_nested({"a": {"b": 1}}, "a.b") == 1


def test_get_nested_missing_key_returns_default():
    """Test missing key returns default value."""
    assert get_nested({"a": {"b": 1}}, "a.c", default=-1) == -1


def test_get_nested_non_dict_mid_path_returns_default():
    """Test stepping into a non-dict returns default."""
    assert get_nested({"a": 1}, "a.b") is None


def test_get_nested_empty_path_returns_entire_data():
    """Test empty path returns the entire data dict."""
    data = {}
    assert get_nested(data, "") == data


def test_get_nested_three_plus_levels():
    """Test lookup works with 3+ levels of nesting."""
    data = {"a": {"b": {"c": {"d": 2}}}}
    assert get_nested(data, "a.b.c.d") == 2
