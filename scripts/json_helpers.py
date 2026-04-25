"""JSON file loading helpers with safe fallback behavior."""

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """
    Safely load JSON from a file, returning default on any error.

    Args:
        path: Path to the JSON file (str or Path).
        default: Value to return if file doesn't exist, is empty, or contains invalid JSON.

    Returns:
        Parsed JSON object if successful, otherwise the default value.
    """
    path = Path(path)

    if not path.exists():
        return default

    content = path.read_text().strip()
    if not content:
        return default

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return default
