"""Tests for json_helpers.py."""

import json
import sys
from pathlib import Path

# Add script directory to path
sys.path.insert(
    0, str(Path(__file__).parent.parent / "scripts")
)

from json_helpers import safe_json_load


def test_safe_json_load_returns_default_for_missing_file(tmp_path: Path) -> None:
    """Should return default when file does not exist."""
    missing_file = tmp_path / "does_not_exist.json"
    assert safe_json_load(missing_file) is None
    assert safe_json_load(missing_file, default={}) == {}
    assert safe_json_load(missing_file, default=[]) == []


def test_safe_json_load_returns_default_for_empty_file(tmp_path: Path) -> None:
    """Should return default when file is empty."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("")
    assert safe_json_load(empty_file) is None
    assert safe_json_load(empty_file, default={}) == {}


def test_safe_json_load_returns_default_for_whitespace_only_file(tmp_path: Path) -> None:
    """Should return default when file contains only whitespace."""
    ws_file = tmp_path / "whitespace.json"
    ws_file.write_text("   \n\t  \n")
    assert safe_json_load(ws_file) is None
    assert safe_json_load(ws_file, default="default") == "default"


def test_safe_json_load_returns_default_for_malformed_json(tmp_path: Path) -> None:
    """Should return default when file contains invalid JSON."""
    bad_file = tmp_path / "broken.json"
    bad_file.write_text('{"key": invalid json here}')
    assert safe_json_load(bad_file) is None
    assert safe_json_load(bad_file, default=[]) == []


def test_safe_json_load_returns_parsed_value_for_valid_json(tmp_path: Path) -> None:
    """Should return parsed data for valid JSON."""
    good_file = tmp_path / "good.json"
    data = {"name": "test", "value": 42, "nested": {"a": [1, 2, 3]}}
    good_file.write_text(json.dumps(data))
    assert safe_json_load(good_file) == data


def test_safe_json_load_accepts_str_and_path(tmp_path: Path) -> None:
    """Should accept both str and Path arguments for path."""
    good_file = tmp_path / "good.json"
    data = {"key": "value"}
    good_file.write_text(json.dumps(data))

    # Test with Path object
    assert safe_json_load(good_file) == data

    # Test with str
    assert safe_json_load(str(good_file)) == data
