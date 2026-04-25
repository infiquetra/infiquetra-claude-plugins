#!/usr/bin/env python3
"""JSON helper functions for Infiquetra Claude Code plugins."""

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """
    Safely load JSON from a file, returning a default value on any error.

    Args:
        path: File path as string or Path object
        default: Value to return if file is missing, empty, or invalid JSON

    Returns:
        Parsed JSON object or default value
    """
    file_path = Path(path)

    # Return default if file doesn't exist
    if not file_path.exists():
        return default

    # Return default if file is empty
    if file_path.stat().st_size == 0:
        return default

    # Try to parse JSON, return default on any error
    try:
        return json.loads(file_path.read_text())
    except json.JSONDecodeError:
        return default
