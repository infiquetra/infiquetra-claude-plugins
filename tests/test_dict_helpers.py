"""Tests for scripts.dict_helpers."""

import sys
from pathlib import Path

# Add repo root to path so "scripts" is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.dict_helpers import get_nested


class TestGetNested:
    def test_get_nested_happy_path(self) -> None:
        data = {"a": {"b": 1}}
        result = get_nested(data, "a.b")
        assert result == 1

    def test_get_nested_missing_key_returns_default(self) -> None:
        data = {"a": {"b": 1}}
        result = get_nested(data, "a.c", default=-1)
        assert result == -1

    def test_get_nested_non_dict_step_returns_default(self) -> None:
        data = {"a": 1}
        result = get_nested(data, "a.b")
        assert result is None

    def test_get_nested_empty_path_returns_original_data(self) -> None:
        data = {}
        result = get_nested(data, "")
        assert result == {}

    def test_get_nested_three_level_lookup(self) -> None:
        data = {"a": {"b": {"c": "deep"}}}
        result = get_nested(data, "a.b.c")
        assert result == "deep"
        # Verify no mutation
        assert data == {"a": {"b": {"c": "deep"}}}
