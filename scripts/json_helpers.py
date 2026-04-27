"""Safe JSON loading utility."""

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """Load and parse a JSON file, returning a default on failure.

    Args:
        path: Path to the JSON file (str or Path).
        default: Value to return if the file is missing, empty, or invalid.

    Returns:
        The parsed JSON object, or *default* on failure.

    Examples:
        >>> safe_json_load("does_not_exist.json") is None
        True
        >>> safe_json_load("does_not_exist.json", default={})
        {}
        >>> safe_json_load(Path("broken.json"), default=[])
        []
        >>> safe_json_load("good.json")
        {'name': 'infiquetra', 'enabled': True}
    """
    json_path = Path(path)
    if not json_path.exists():
        return default
    try:
        text = json_path.read_text(encoding="utf-8")
        return json.loads(text)
    except json.JSONDecodeError:
        return default
