import pytest
from scripts.dict_helpers import get_nested

def test_get_nested_happy_path():
    data = {"a": {"b": 1}}
    assert get_nested(data, "a.b") == 1

def test_get_nested_missing_key_returns_default():
    data = {"a": {"b": 1}}
    assert get_nested(data, "a.c", default=-1) == -1
    assert get_nested(data, "a.c") is None

def test_get_nested_non_dict_intermediate_returns_default():
    data = {"a": 1}
    assert get_nested(data, "a.b") is None
    assert get_nested(data, "a.b", default="fallback") == "fallback"

def test_get_nested_empty_path_returns_original_data():
    data = {"a": 1}
    assert get_nested(data, "") == data
    
    empty_data = {}
    assert get_nested(empty_data, "") == empty_data

def test_get_nested_three_plus_levels():
    data = {"a": {"b": {"c": {"d": 4}}}}
    assert get_nested(data, "a.b.c.d") == 4
    assert get_nested(data, "a.b.c") == {"d": 4}
    assert get_nested(data, "a.b.z", default="missing") == "missing"
