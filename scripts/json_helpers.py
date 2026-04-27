from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """Load JSON from a file, returning default if the file doesn't exist or is invalid JSON."""
    json_path = Path(path)

    if not json_path.exists():
        return default

    try:
        with json_path.open(encoding="utf-8") as file_obj:
            return json.load(file_obj)
    except (OSError, json.JSONDecodeError):
        return default
