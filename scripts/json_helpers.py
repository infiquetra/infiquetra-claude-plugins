"""JSON loading helpers with graceful fallback handling."""

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default=None) -> Any:
    """Load JSON from a path, returning default if file missing or invalid.

    Args:
        path: Path to the JSON file (str or Path).
        default: Value to return if file doesn't exist or is invalid JSON.

    Returns:
        Parsed JSON object or the default value.
    """
    json_path = Path(path)

    if not json_path.exists():
        return default

    try:
        return json.loads(json_path.read_text())
    except json.JSONDecodeError:
        return default
