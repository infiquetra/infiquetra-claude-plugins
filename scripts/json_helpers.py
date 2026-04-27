from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """
    Safely loads a JSON file. Returns default if the file does not exist,
    is empty, or contains invalid JSON.

    Args:
        path: Path to the JSON file (str or Path object).
        default: Value to return if loading fails. Defaults to None.

    Returns:
        The parsed JSON data or the default value.
    """
    json_path = Path(path)

    if not json_path.exists():
        return default

    try:
        content = json_path.read_text()
        if not content:
            return default
        return json.loads(content)
    except json.JSONDecodeError:
        return default
