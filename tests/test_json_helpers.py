"""Tests for json_helpers."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from json_helpers import safe_json_load


def test_safe_json_load_missing_file_returns_default(tmp_path):
    missing = tmp_path / "missing.json"
    assert safe_json_load(missing) is None
    assert safe_json_load(missing, default={}) == {}


def test_safe_json_load_empty_file_returns_default(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text("", encoding="utf-8")
    assert safe_json_load(empty, default=[]) == []


def test_safe_json_load_malformed_json_returns_default(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{not valid json", encoding="utf-8")
    assert safe_json_load(broken, default=[]) == []


def test_safe_json_load_valid_json_returns_parsed_result(tmp_path):
    good = tmp_path / "good.json"
    good.write_text('{"name": "infiquetra", "count": 2}', encoding="utf-8")
    assert safe_json_load(good) == {"name": "infiquetra", "count": 2}


def test_safe_json_load_accepts_path_and_str_arguments(tmp_path):
    path_arg = tmp_path / "list.json"
    path_arg.write_text("[1, 2, 3]", encoding="utf-8")
    assert safe_json_load(path_arg) == [1, 2, 3]
    assert safe_json_load(str(path_arg)) == [1, 2, 3]
