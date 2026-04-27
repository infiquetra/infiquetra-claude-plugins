"""JSON loading helpers with safe fallback behavior."""

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """Load JSON from *path*, returning *default* for missing/empty/invalid files."""
    path_obj = Path(path)
    if not path_obj.exists():
        return default
    try:
        content = path_obj.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return default
