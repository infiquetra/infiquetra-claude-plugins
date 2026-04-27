from __future__ import annotations

from pathlib import Path

from scripts.json_helpers import safe_json_load


def test_safe_json_load_returns_default_for_missing_file(tmp_path: Path) -> None:
    """Test that safe_json_load returns default when file doesn't exist."""
    missing_path = tmp_path / "missing.json"

    # Default is None
    assert safe_json_load(missing_path) is None

    # Custom default
    assert safe_json_load(missing_path, default={}) == {}


def test_safe_json_load_returns_default_for_empty_file(tmp_path: Path) -> None:
    """Test that safe_json_load returns default when file is empty."""
    empty_path = tmp_path / "empty.json"
    empty_path.write_text("")

    assert safe_json_load(empty_path, default=[]) == []


def test_safe_json_load_returns_default_for_malformed_json(tmp_path: Path) -> None:
    """Test that safe_json_load returns default when file contains invalid JSON."""
    broken_path = tmp_path / "broken.json"
    broken_path.write_text("{not-json")

    assert safe_json_load(broken_path, default=[]) == []


def test_safe_json_load_returns_parsed_result_for_valid_json(tmp_path: Path) -> None:
    """Test that safe_json_load correctly parses valid JSON."""
    good_path = tmp_path / "good.json"
    good_path.write_text('{"name": "infiquetra", "count": 2}')

    result = safe_json_load(good_path)
    assert result == {"name": "infiquetra", "count": 2}


def test_safe_json_load_accepts_str_path(tmp_path: Path) -> None:
    """Test that safe_json_load accepts string paths (not just Path objects)."""
    good_path = tmp_path / "string-path.json"
    good_path.write_text('["a", "b"]')

    result = safe_json_load(str(good_path))
    assert result == ["a", "b"]
