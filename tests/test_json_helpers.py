"""Unit tests for json_helpers.py."""

import json
import sys
from pathlib import Path

# Add scripts directory to path for import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from json_helpers import safe_json_load


def test_missing_file_returns_none(tmp_path):
    """Test that missing file returns None."""
    missing_file = tmp_path / "missing.json"
    result = safe_json_load(missing_file)
    assert result is None


def test_missing_file_returns_default(tmp_path):
    """Test that missing file returns provided default."""
    missing_file = tmp_path / "missing.json"
    result = safe_json_load(missing_file, default={})
    assert result == {}


def test_empty_file_returns_default(tmp_path):
    """Test that empty file returns provided default."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("")
    result = safe_json_load(empty_file, default=[])
    assert result == []


def test_malformed_json_returns_default(tmp_path):
    """Test that malformed JSON returns provided default."""
    malformed_file = tmp_path / "malformed.json"
    malformed_file.write_text('{"invalid": json}')
    result = safe_json_load(malformed_file, default={"error": True})
    assert result == {"error": True}


def test_valid_json_returns_parsed(tmp_path):
    """Test that valid JSON returns parsed object."""
    valid_file = tmp_path / "valid.json"
    test_data = {"key": "value", "number": 42}
    valid_file.write_text(json.dumps(test_data))
    result = safe_json_load(valid_file)
    assert result == test_data


def test_path_and_str_inputs_work(tmp_path):
    """Test that both Path and str inputs work."""
    test_file = tmp_path / "test.json"
    test_data = {"test": "data"}
    test_file.write_text(json.dumps(test_data))
    
    # Test with str path
    result_str = safe_json_load(str(test_file))
    assert result_str == test_data
    
    # Test with Path object
    result_path = safe_json_load(test_file)
    assert result_path == test_data