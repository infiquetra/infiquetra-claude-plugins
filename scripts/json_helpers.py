"""JSON helper utilities for safe loading of JSON files."""

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default=None) -> Any:
    """
    Safely load JSON from a file path.

    Args:
        path: Path to the JSON file (str or Path object)
        default: Default value to return if file doesn't exist or is invalid

    Returns:
        Parsed JSON object if successful, otherwise default value
    """
    json_path = Path(path)

    # If file doesn't exist, return default
    if not json_path.exists():
        return default

    try:
        # Try to parse the JSON content
        return json.loads(json_path.read_text())
    except json.JSONDecodeError:
        # If JSON is invalid or empty, return default
        return default
