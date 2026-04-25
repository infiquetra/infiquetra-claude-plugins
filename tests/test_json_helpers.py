"""Unit tests for json_helpers.py."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import json_helpers


class TestSafeJsonLoad:
    """Tests for safe_json_load()."""

    def test_safe_json_load_missing_file_returns_none(self, tmp_path: Path) -> None:
        """Missing file returns None."""
        result = json_helpers.safe_json_load(tmp_path / "does_not_exist.json")
        assert result is None

    def test_safe_json_load_missing_file_returns_supplied_default(
        self, tmp_path: Path
    ) -> None:
        """Missing file returns the caller-supplied default."""
        result = json_helpers.safe_json_load(
            tmp_path / "does_not_exist.json", default={}
        )
        assert result == {}

    def test_safe_json_load_empty_file_returns_default(self, tmp_path: Path) -> None:
        """Empty file returns the supplied default."""
        file_path = tmp_path / "empty.json"
        file_path.touch()
        result = json_helpers.safe_json_load(file_path, default=[])
        assert result == []

    def test_safe_json_load_malformed_json_returns_default(
        self, tmp_path: Path
    ) -> None:
        """Malformed JSON returns the supplied default."""
        file_path = tmp_path / "broken.json"
        file_path.write_text("{ not valid json", encoding="utf-8")
        result = json_helpers.safe_json_load(file_path, default=[])
        assert result == []

    def test_safe_json_load_valid_json_accepts_path_and_str(
        self, tmp_path: Path
    ) -> None:
        """Valid JSON is parsed and returned for both Path and str arguments."""
        data = {"key": "value", "number": 42}
        file_path = tmp_path / "good.json"
        file_path.write_text(json.dumps(data), encoding="utf-8")

        result_str = json_helpers.safe_json_load(str(file_path))
        result_path = json_helpers.safe_json_load(file_path)

        assert result_str == data
        assert result_path == data
