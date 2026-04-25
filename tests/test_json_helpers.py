"""Unit tests for safe_json_load function."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from json_helpers import safe_json_load


class TestSafeJsonLoad:
    """Test safe_json_load function."""

    def test_safe_json_load_returns_none_for_missing_file(self, tmp_path):
        """Test that missing file returns None when default is omitted."""
        missing_file = tmp_path / "does_not_exist.json"
        result = safe_json_load(missing_file)
        assert result is None

    def test_safe_json_load_returns_custom_default_for_missing_file(self, tmp_path):
        """Test that missing file returns the caller-provided default object."""
        missing_file = tmp_path / "does_not_exist.json"
        custom_default = {"fallback": "value"}
        result = safe_json_load(missing_file, default=custom_default)
        assert result == custom_default

    def test_safe_json_load_returns_default_for_empty_file(self, tmp_path):
        """Test that empty file returns the provided default."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")
        custom_default = []
        result = safe_json_load(empty_file, default=custom_default)
        assert result == custom_default

    def test_safe_json_load_returns_default_for_malformed_json(self, tmp_path):
        """Test that malformed JSON returns the provided default."""
        broken_file = tmp_path / "broken.json"
        broken_file.write_text("{ invalid json }")
        custom_default = []
        result = safe_json_load(broken_file, default=custom_default)
        assert result == custom_default

    def test_safe_json_load_returns_parsed_object_for_valid_json(self, tmp_path):
        """Test that valid JSON returns the parsed object."""
        valid_file = tmp_path / "valid.json"
        expected = {"name": "test", "count": 42}
        valid_file.write_text(json.dumps(expected))
        result = safe_json_load(valid_file)
        assert result == expected

    def test_safe_json_load_accepts_path_and_str_arguments(self, tmp_path):
        """Test that both str and Path arguments produce the same parsed result."""
        valid_file = tmp_path / "valid.json"
        expected = {"data": [1, 2, 3]}
        valid_file.write_text(json.dumps(expected))

        result_str = safe_json_load(str(valid_file))
        result_path = safe_json_load(valid_file)

        assert result_str == expected
        assert result_path == expected
        assert result_str == result_path
