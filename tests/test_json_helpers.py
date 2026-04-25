"""Unit tests for json_helpers.py."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from json_helpers import safe_json_load


class TestSafeJsonLoad:
    """Test safe_json_load function."""

    def test_missing_file_returns_none_default(self, tmp_path: Path) -> None:
        """Test that missing file returns None when default is omitted."""
        result = safe_json_load(str(tmp_path / "nonexistent.json"))
        assert result is None

    def test_missing_file_returns_custom_default(self, tmp_path: Path) -> None:
        """Test that missing file returns custom default."""
        result = safe_json_load(str(tmp_path / "nonexistent.json"), default={})
        assert result == {}

    def test_empty_file_returns_default(self, tmp_path: Path) -> None:
        """Test that empty file returns the provided default."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")
        result = safe_json_load(str(empty_file), default=[])
        assert result == []

    def test_empty_file_with_whitespace_returns_default(self, tmp_path: Path) -> None:
        """Test that file with only whitespace returns default."""
        empty_file = tmp_path / "whitespace.json"
        empty_file.write_text("   \n  \t  ")
        result = safe_json_load(str(empty_file), default={})
        assert result == {}

    def test_malformed_json_returns_default(self, tmp_path: Path) -> None:
        """Test that malformed JSON returns the provided default."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json")
        result = safe_json_load(str(bad_file), default="fallback")
        assert result == "fallback"

    def test_valid_json_returns_parsed_object(self, tmp_path: Path) -> None:
        """Test that valid JSON returns the parsed object."""
        good_file = tmp_path / "good.json"
        test_obj = {"name": "test", "value": 42}
        good_file.write_text(json.dumps(test_obj))
        result = safe_json_load(str(good_file))
        assert result == test_obj

    def test_str_path_argument(self, tmp_path: Path) -> None:
        """Test that str path argument works correctly."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')
        result = safe_json_load(str(test_file))
        assert result == {"key": "value"}

    def test_path_argument(self, tmp_path: Path) -> None:
        """Test that Path argument works correctly."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')
        result = safe_json_load(test_file)
        assert result == {"key": "value"}

    def test_path_vs_str_same_result(self, tmp_path: Path) -> None:
        """Test that Path and str arguments produce the same result."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"x": 1}')
        result_str = safe_json_load(str(test_file))
        result_path = safe_json_load(test_file)
        assert result_str == result_path
