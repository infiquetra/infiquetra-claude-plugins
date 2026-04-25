"""Unit tests for scripts/dict_helpers.get_nested()."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dict_helpers import get_nested


class TestGetNested:
    """Test suite for dotted-path dictionary lookups."""

    def test_get_nested_happy_path(self):
        """Happy path: simple two-level lookup succeeds."""
        data = {"a": {"b": 1}}
        assert get_nested(data, "a.b") == 1

    def test_get_nested_missing_key_returns_default(self):
        """Missing key returns the provided default."""
        data = {"a": {"b": 1}}
        assert get_nested(data, "a.c", default=-1) == -1

    def test_get_nested_non_dict_mid_path_returns_default(self):
        """Stepping into a non-dict value returns None (the default)."""
        data = {"a": 1}
        assert get_nested(data, "a.b") is None

    def test_get_nested_empty_path_returns_original_data(self):
        """Empty path returns the entire input dict unchanged."""
        data = {}
        assert get_nested(data, "") == {}

    def test_get_nested_three_plus_levels(self):
        """Three-plus-level nested lookup succeeds."""
        data = {"a": {"b": {"c": {"d": 5}}}}
        assert get_nested(data, "a.b.c.d") == 5

    def test_get_nested_does_not_mutate_input(self):
        """Input data remains unchanged after function call."""
        original_data = {"a": {"b": {"c": 1}}, "x": 2}
        # Make a deep copy to compare against
        import copy
        data_copy = copy.deepcopy(original_data)

        # Call the function
        result = get_nested(original_data, "a.b.c", default=0)

        # Verify result is correct
        assert result == 1

        # Verify input data is unchanged
        assert original_data == data_copy
