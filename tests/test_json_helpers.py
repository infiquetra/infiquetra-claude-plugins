"""Tests for json_helpers.safe_json_load."""

import json
import sys
from pathlib import Path

# Add scripts directory to path for non-package imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from json_helpers import safe_json_load


def test_safe_json_load_missing_file_returns_none(tmp_path: Path) -> None:
    """Missing file returns None when default is omitted."""
    assert safe_json_load(tmp_path / "does_not_exist.json") is None


def test_safe_json_load_missing_file_returns_default(tmp_path: Path) -> None:
    """Missing file returns the provided default object."""
    assert safe_json_load(tmp_path / "does_not_exist.json", default={}) == {}


def test_safe_json_load_empty_file_returns_default(tmp_path: Path) -> None:
    """Empty file returns the provided default."""
    f = tmp_path / "empty.json"
    f.write_text("")
    assert safe_json_load(f, default=[]) == []


def test_safe_json_load_malformed_json_returns_default(tmp_path: Path) -> None:
    """Malformed JSON returns the provided default."""
    f = tmp_path / "broken.json"
    f.write_text("{invalid json")
    assert safe_json_load(f, default=[]) == []


def test_safe_json_load_valid_json_returns_parsed_object(tmp_path: Path) -> None:
    """Valid JSON returns the parsed Python object."""
    f = tmp_path / "good.json"
    f.write_text(json.dumps({"key": "value"}))
    assert safe_json_load(f) == {"key": "value"}


def test_safe_json_load_accepts_path_and_str(tmp_path: Path) -> None:
    """Both Path and str arguments work against the same file."""
    f = tmp_path / "good.json"
    f.write_text(json.dumps([1, 2, 3]))
    expected = [1, 2, 3]
    assert safe_json_load(f) == expected
    assert safe_json_load(str(f)) == expected
