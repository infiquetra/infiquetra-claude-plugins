"""Path-aware JSON loader helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """Load and parse a JSON file, returning a default on failure.

    Args:
        path: Path to the JSON file. Accepts str or Path.
        default: Value to return when the file is missing, empty,
            or contains invalid JSON. Defaults to None.

    Returns:
        The parsed JSON object on success, otherwise the default value.
    """
    file_path = Path(path)
    if not file_path.exists():
        return default
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError:
        return default
    if not content:
        return default
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return default
