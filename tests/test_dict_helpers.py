"""Unit tests for dict_helpers.py."""

import pytest
import sys
from pathlib import Path
from typing import Any

# Add scripts directory to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dict_helpers import get_nested


class TestGetNested:
    """Test get_nested function."""

    def test_get_nested_happy_path(self):
        """Test happy path with valid nested dict and path."""
        data = {"a": {"b": {"c": 1}}}
        result = get_nested(data, "a.b.c")
        assert result == 1

    def test_get_nested_missing_key_returns_default(self):
        """Test that missing key returns default value."""
        data = {"a": {"b": 1}}
        result = get_nested(data, "a.c", default=-1)
        assert result == -1

    def test_get_nested_non_dict_step_returns_default(self):
        """Test that stepping into non-dict value returns default."""
        data = {"a": 1}
        result = get_nested(data, "a.b", default="default")
        assert result == "default"

    def test_get_nested_empty_path_returns_entire_data(self):
        """Test that empty path returns entire data."""
        data = {"a": {"b": 1}}
        result = get_nested(data, "")
        assert result == data

    def test_get_nested_three_level_lookup(self):
        """Test lookup with three levels of nesting."""
        data = {"level1": {"level2": {"level3": "deep_value"}}}
        result = get_nested(data, "level1.level2.level3")
        assert result == "deep_value"

    def test_get_nested_does_not_mutate_input(self):
        """Test that the original data structure is not mutated."""
        data = {"a": {"b": {"c": 1}}}
        original_data = data.copy()
        get_nested(data, "a.b.c")
        assert data == original_data
        
        # Also check nested mutation
        get_nested(data, "a.b")
        assert data == original_data