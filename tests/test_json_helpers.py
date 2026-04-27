"""Unit tests for json_helpers.py."""

from pathlib import Path

import pytest

from scripts.json_helpers import safe_json_load


class TestSafeJsonLoad:
    """Test safe_json_load function."""

    def test_safe_json_load_missing_file_returns_default(self, tmp_path: Path) -> None:
        """Missing file returns default value (None or custom)."""
        missing_file = tmp_path / "missing.json"

        assert safe_json_load(missing_file) is None
        assert safe_json_load(missing_file, default={}) == {}

    def test_safe_json_load_empty_file_returns_default(self, tmp_path: Path) -> None:
        """Empty file returns default value."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")

        assert safe_json_load(empty_file, default=[]) == []

    def test_safe_json_load_malformed_json_returns_default(self, tmp_path: Path) -> None:
        """Malformed JSON returns default value."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json")

        assert safe_json_load(bad_file, default=[]) == []

    def test_safe_json_load_valid_json_returns_parsed_result(self, tmp_path: Path) -> None:
        """Valid JSON returns parsed object."""
        good_file = tmp_path / "good.json"
        good_file.write_text('{"name": "infiquetra", "enabled": true}')

        result = safe_json_load(good_file)
        assert result == {"name": "infiquetra", "enabled": True}

    def test_safe_json_load_accepts_str_and_path(self, tmp_path: Path) -> None:
        """Function accepts both str and Path for path argument."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')

        # Test with Path object
        result_path = safe_json_load(json_file)
        # Test with str
        result_str = safe_json_load(str(json_file))

        assert result_path == result_str == {"key": "value"}
