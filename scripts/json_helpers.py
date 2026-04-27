"""JSON helper utilities for safe file loading."""

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """
    Safely load JSON from a file, returning a default on errors.

    If the file does not exist, is empty, or contains invalid JSON,
    returns `default` instead of raising. For valid JSON files,
    returns the parsed object.

    Args:
        path: File path as string or Path object.
        default: Value to return on missing/empty/invalid JSON.
                 Defaults to None.

    Returns:
        The parsed JSON object, or `default` on any load error.
    """
    json_path = Path(path)

    if not json_path.exists():
        return default

    try:
        return json.loads(json_path.read_text())
    except json.JSONDecodeError:
        return default
