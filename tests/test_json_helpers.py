"""Unit tests for json_helpers.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from json_helpers import safe_json_load  # noqa: E402


def test_safe_json_load_missing_file_returns_default(tmp_path):
    """Missing file returns the default value."""
    missing_path = tmp_path / "missing.json"
    assert safe_json_load(missing_path) is None
    assert safe_json_load(missing_path, default={}) == {}


def test_safe_json_load_empty_file_returns_default(tmp_path):
    """Empty file returns the default value."""
    empty_path = tmp_path / "empty.json"
    empty_path.write_text("")
    assert safe_json_load(empty_path, default=[]) == []


def test_safe_json_load_malformed_json_returns_default(tmp_path):
    """Malformed JSON returns the default value."""
    broken_path = tmp_path / "broken.json"
    broken_path.write_text("{not-json")
    assert safe_json_load(broken_path, default=[]) == []


def test_safe_json_load_valid_json_returns_parsed_result(tmp_path):
    """Valid JSON returns the parsed object."""
    good_path = tmp_path / "good.json"
    good_path.write_text('{"name": "infiquetra", "enabled": true, "count": 2}')
    assert safe_json_load(good_path) == {"name": "infiquetra", "enabled": True, "count": 2}


def test_safe_json_load_accepts_path_and_str(tmp_path):
    """Both Path and str arguments work."""
    path_arg = tmp_path / "list.json"
    path_arg.write_text("[1, 2, 3]")
    assert safe_json_load(path_arg) == [1, 2, 3]
    assert safe_json_load(str(path_arg)) == [1, 2, 3]
