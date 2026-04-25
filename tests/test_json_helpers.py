import json

from scripts.json_helpers import safe_json_load


def test_safe_json_load_returns_default_for_missing_file(tmp_path):
    """AC 1.1: Missing file returns default value instead of raising."""
    missing_file = tmp_path / "does_not_exist.json"
    result = safe_json_load(missing_file, default={"status": "missing"})
    assert result == {"status": "missing"}


def test_safe_json_load_returns_default_for_empty_file(tmp_path):
    """AC 1.2: Empty file returns default value."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("")

    result = safe_json_load(empty_file, default=[])
    assert result == []


def test_safe_json_load_returns_default_for_malformed_json(tmp_path):
    """AC 1.3: Malformed JSON returns default value."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{'invalid': json}")

    result = safe_json_load(bad_file, default=None)
    assert result is None


def test_safe_json_load_returns_parsed_object_for_valid_json(tmp_path):
    """AC 1.4: Valid JSON returns the parsed object."""
    data = {"key": "value", "list": [1, 2, 3]}
    good_file = tmp_path / "good.json"
    good_file.write_text(json.dumps(data))

    result = safe_json_load(good_file)
    assert result == data


def test_safe_json_load_accepts_str_and_path_inputs(tmp_path):
    """AC 1.5: Accepts both str and Path types for the path argument."""
    data = {"data": 42}
    test_file = tmp_path / "test.json"
    test_file.write_text(json.dumps(data))

    # Test with string path
    assert safe_json_load(str(test_file)) == data

    # Test with Path object
    assert safe_json_load(test_file) == data
