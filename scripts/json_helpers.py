"""JSON helper utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """Load JSON from *path* and return the parsed object.

    If *path* does not exist, is empty, or contains invalid JSON,
    return *default* instead of raising.
    """
    json_path = Path(path)
    if not json_path.exists():
        return default

    try:
        content = json_path.read_text(encoding="utf-8")
        return json.loads(content)
    except json.JSONDecodeError:
        return default
