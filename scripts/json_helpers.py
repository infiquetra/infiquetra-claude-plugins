"""Helper utilities for JSON file handling."""

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """Load JSON from a file, returning default on any failure.

    Args:
        path: Path to the JSON file (str or Path).
        default: Value to return if file doesn't exist, is empty,
                 or contains invalid JSON.

    Returns:
        Parsed JSON data if valid, otherwise the default value.
    """
    json_path = Path(path)

    if not json_path.exists():
        return default

    try:
        content = json_path.read_text(encoding="utf-8")
    except OSError:
        return default

    stripped = content.strip()
    if not stripped:
        return default

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return default
