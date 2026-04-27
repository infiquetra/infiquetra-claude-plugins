"""Tests for dict_helpers."""

from scripts.dict_helpers import get_nested


def test_get_nested_happy_path_returns_value():
    assert get_nested({"a": {"b": 1}}, "a.b") == 1


def test_get_nested_missing_key_returns_default():
    assert get_nested({"a": {"b": 1}}, "a.c", default=-1) == -1


def test_get_nested_non_dict_step_returns_default():
    assert get_nested({"a": 1}, "a.b") is None


def test_get_nested_empty_path_returns_data():
    assert get_nested({}, "") == {}
    assert get_nested({"a": 1}, "") == {"a": 1}


def test_get_nested_three_plus_levels_and_does_not_mutate():
    data = {"a": {"b": {"c": "value"}}}
    expected = {"a": {"b": {"c": "value"}}}
    assert get_nested(data, "a.b.c") == "value"
    assert data == expected
