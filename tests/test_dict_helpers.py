"""Tests for scripts/dict_helpers.get_nested."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dict_helpers import get_nested


def test_get_nested_happy_path() -> None:
    assert get_nested({"a": {"b": 1}}, "a.b") == 1


def test_get_nested_missing_key_returns_default() -> None:
    assert get_nested({"a": {"b": 1}}, "a.c", default=-1) == -1


def test_get_nested_non_dict_step_returns_default() -> None:
    assert get_nested({"a": 1}, "a.b") is None


def test_get_nested_empty_path_returns_data() -> None:
    data: dict = {}
    assert get_nested(data, "") == {}
    assert get_nested(data, "") is data


def test_get_nested_three_plus_levels() -> None:
    assert get_nested({"a": {"b": {"c": {"d": "value"}}}}, "a.b.c.d") == "value"


def test_get_nested_does_not_mutate_data() -> None:
    data = {"a": {"b": 1}}
    get_nested(data, "a.b")
    assert data == {"a": {"b": 1}}
