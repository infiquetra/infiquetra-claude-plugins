"""JSON helper utilities for safe file loading."""

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """Load JSON from a file, returning a default value on any error.

    Args:
        path: Path to the JSON file (accepts str or Path).
        default: Value to return if file is missing, empty, or invalid (default: None).

    Returns:
        The parsed JSON object, or the default value if loading fails.
    """
    normalized_path = Path(path)

    if not normalized_path.exists():
        return default

    content = normalized_path.read_text()

    if not content.strip():
        return default

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return default
