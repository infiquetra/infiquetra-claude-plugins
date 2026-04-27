"""Tests for json_helpers utility."""

from pathlib import Path

from scripts.json_helpers import safe_json_load


def test_safe_json_load_returns_default_for_missing_file(tmp_path: Path) -> None:
    """Missing file returns None by default, or the explicit default."""
    assert safe_json_load(tmp_path / "missing.json") is None
    assert safe_json_load(tmp_path / "missing.json", default={}) == {}


def test_safe_json_load_returns_default_for_empty_file(tmp_path: Path) -> None:
    """Empty file returns the specified default."""
    p = tmp_path / "empty.json"
    p.write_text("", encoding="utf-8")
    assert safe_json_load(p, default=[]) == []


def test_safe_json_load_returns_default_for_malformed_json(tmp_path: Path) -> None:
    """Malformed JSON returns the specified default."""
    p = tmp_path / "broken.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert safe_json_load(p, default=[]) == []


def test_safe_json_load_returns_parsed_valid_json(tmp_path: Path) -> None:
    """Valid JSON is parsed and returned."""
    p = tmp_path / "good.json"
    p.write_text('{"name": "infiquetra", "enabled": true}', encoding="utf-8")
    result = safe_json_load(p)
    assert result == {"name": "infiquetra", "enabled": True}


def test_safe_json_load_accepts_str_and_path_arguments(tmp_path: Path) -> None:
    """Both str and Path arguments produce the same result."""
    p = tmp_path / "data.json"
    p.write_text('{"key": "value"}', encoding="utf-8")
    assert safe_json_load(p) == {"key": "value"}
    assert safe_json_load(str(p)) == {"key": "value"}
