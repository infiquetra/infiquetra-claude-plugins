"""Unit tests for dict_helpers.py."""

import sys
from pathlib import Path

# Add scripts directory to path so we can import dict_helpers
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dict_helpers import get_nested


def test_get_nested_happy_path():
    """Test happy path nested lookup."""
    data = {"a": {"b": 1}}
    result = get_nested(data, "a.b")
    assert result == 1


def test_get_nested_missing_key_returns_default():
    """Test missing key returns given default."""
    data = {"a": {"b": 1}}
    result = get_nested(data, "a.c", default=-1)
    assert result == -1


def test_get_nested_returns_default_when_stepping_into_non_dict():
    """Test stepping into a non-dict returns default."""
    data = {"a": 1}
    result = get_nested(data, "a.b")
    assert result is None


def test_get_nested_empty_path_returns_original_data():
    """Test empty path returns original dict."""
    data = {"x": "y"}
    result = get_nested(data, "")
    assert result == data


def test_get_nested_three_level_lookup():
    """Test nested lookup three levels deep."""
    data = {"a": {"b": {"c": {"d": "value"}}}}
    result = get_nested(data, "a.b.c")
    assert result == {"d": "value"}
