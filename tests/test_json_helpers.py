"""Unit tests for json_helpers.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from json_helpers import safe_json_load


def test_safe_json_load_missing_file_returns_default(tmp_path):
    missing_path = tmp_path / "missing.json"

    assert safe_json_load(missing_path) is None
    assert safe_json_load(missing_path, default={}) == {}


def test_safe_json_load_empty_file_returns_default(tmp_path):
    empty_path = tmp_path / "empty.json"
    empty_path.write_text("", encoding="utf-8")

    assert safe_json_load(empty_path, default=[]) == []


def test_safe_json_load_malformed_json_returns_default(tmp_path):
    broken_path = tmp_path / "broken.json"
    broken_path.write_text("{", encoding="utf-8")

    assert safe_json_load(broken_path, default=[]) == []


def test_safe_json_load_valid_json_returns_parsed_result(tmp_path):
    valid_path = tmp_path / "valid.json"
    valid_path.write_text(
        '{"name": "infiquetra", "enabled": true}',
        encoding="utf-8",
    )

    result = safe_json_load(valid_path)
    assert result == {"name": "infiquetra", "enabled": True}


def test_safe_json_load_accepts_path_and_str_arguments(tmp_path):
    valid_path = tmp_path / "valid.json"
    valid_path.write_text(
        '{"name": "infiquetra", "enabled": true}',
        encoding="utf-8",
    )

    assert safe_json_load(valid_path) == {"name": "infiquetra", "enabled": True}
    assert safe_json_load(str(valid_path)) == {"name": "infiquetra", "enabled": True}
