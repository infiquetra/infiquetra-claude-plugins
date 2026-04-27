import pytest
from scripts.dict_helpers import get_nested

def test_get_nested_returns_value_for_existing_path():
    """Happy path: existing nested key should return the value."""
    assert get_nested({"a": {"b": 1}}, "a.b") == 1

def test_get_nested_returns_default_for_missing_key():
    """Missing key should return the provided default value."""
    assert get_nested({"a": {"b": 1}}, "a.c", default=-1) == -1

def test_get_nested_returns_default_when_step_is_not_dict():
    """Stepping into a non-dict value should return the default."""
    assert get_nested({"a": 1}, "a.b") is None

def test_get_nested_empty_path_returns_data():
    """Empty path should return the entire input dictionary."""
    data = {"a": 1}
    assert get_nested(data, "") == {"a": 1}
    # Also verify empty dict case from requirements
    assert get_nested({}, "") == {}

def test_get_nested_supports_three_or_more_levels():
    """Deeply nested lookups (3+ levels) should work correctly."""
    assert get_nested({"a": {"b": {"c": "value"}}}, "a.b.c") == "value"
