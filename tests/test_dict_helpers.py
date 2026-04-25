from scripts.dict_helpers import get_nested


def test_get_nested_happy_path():
    data = {"a": {"b": 1}}
    assert get_nested(data, "a.b") == 1

def test_get_nested_missing_key_returns_default():
    data = {"a": {"b": 1}}
    assert get_nested(data, "a.c", default=-1) == -1
    assert get_nested(data, "x") is None

def test_get_nested_non_dict_step_returns_none():
    data = {"a": 1}
    assert get_nested(data, "a.b") is None

def test_get_nested_empty_path_returns_original_data():
    data = {"a": 1}
    assert get_nested(data, "") == data
    assert get_nested({}, "") == {}

def test_get_nested_three_level_lookup():
    data = {"a": {"b": {"c": 42}}}
    assert get_nested(data, "a.b.c") == 42
    assert get_nested(data, "a.b.d", default="missing") == "missing"
