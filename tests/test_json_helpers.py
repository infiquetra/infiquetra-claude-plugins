from scripts.json_helpers import safe_json_load


def test_safe_json_load_returns_default_for_missing_file(tmp_path):
    missing_path = tmp_path / "missing.json"
    assert safe_json_load(missing_path) is None
    assert safe_json_load(missing_path, default={}) == {}


def test_safe_json_load_returns_default_for_empty_file(tmp_path):
    empty_path = tmp_path / "empty.json"
    empty_path.write_text("")
    assert safe_json_load(empty_path, default=[]) == []


def test_safe_json_load_returns_default_for_malformed_json(tmp_path):
    broken_path = tmp_path / "broken.json"
    broken_path.write_text("{not valid json")
    assert safe_json_load(broken_path, default=[]) == []


def test_safe_json_load_returns_parsed_valid_json(tmp_path):
    good_path = tmp_path / "good.json"
    data = {"name": "infiquetra", "count": 2}
    good_path.write_text('{"name": "infiquetra", "count": 2}')
    assert safe_json_load(good_path) == data


def test_safe_json_load_accepts_str_path(tmp_path):
    good_path = tmp_path / "good.json"
    data = {"name": "infiquetra", "count": 2}
    good_path.write_text('{"name": "infiquetra", "count": 2}')
    assert safe_json_load(str(good_path)) == data
