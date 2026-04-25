"""Tests for json_helpers.py"""

import json
from pathlib import Path

from scripts.json_helpers import safe_json_load


def test_safe_json_load_missing_file_returns_none(tmp_path: Path):
    """Test that missing file returns None by default."""
    missing_file = tmp_path / "missing.json"
    assert safe_json_load(missing_file) is None


def test_safe_json_load_missing_file_returns_custom_default(tmp_path: Path):
    """Test that missing file returns custom default."""
    missing_file = tmp_path / "missing.json"
    custom_default = {"default": True}
    assert safe_json_load(missing_file, default=custom_default) == custom_default


def test_safe_json_load_empty_file_returns_default(tmp_path: Path):
    """Test that empty file returns default."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("")
    assert safe_json_load(empty_file, default="empty") == "empty"


def test_safe_json_load_malformed_json_returns_default(tmp_path: Path):
    """Test that malformed JSON returns default."""
    broken_file = tmp_path / "broken.json"
    broken_file.write_text("{ invalid json }")
    assert safe_json_load(broken_file, default="malformed") == "malformed"


def test_safe_json_load_valid_json_returns_parsed_object(tmp_path: Path):
    """Test that valid JSON returns parsed object."""
    valid_file = tmp_path / "valid.json"
    test_data = {"key": "value", "number": 42}
    valid_file.write_text(json.dumps(test_data))
    assert safe_json_load(valid_file) == test_data


def test_safe_json_load_accepts_path_and_str(tmp_path: Path):
    """Test that both Path and str arguments work."""
    valid_file = tmp_path / "valid.json"
    test_data = {"key": "value"}
    valid_file.write_text(json.dumps(test_data))

    # Test with Path object
    result_path = safe_json_load(valid_file)
    # Test with string path
    result_str = safe_json_load(str(valid_file))

    assert result_path == test_data
    assert result_str == test_data
    assert result_path == result_str
