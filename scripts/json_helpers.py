"""JSON helper utilities."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default=None) -> Any:
    """Load and parse a JSON file, returning a default on failure.

    Args:
        path: Path to the JSON file. Accepts str or Path.
        default: Value to return if the file is missing, empty, or unparseable.

    Returns:
        The parsed JSON content, or ``default`` if the file is missing or invalid.
    """
    json_path = Path(path)
    if not json_path.exists():
        return default
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default
