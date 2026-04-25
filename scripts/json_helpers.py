"""JSON loading helpers with graceful fallback on missing or invalid files."""

import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """Load JSON from *path*, returning *default* on any failure.

    Returns *default* when the file is missing, empty, or contains
    malformed JSON. Returns the parsed object for valid JSON files.
    Accepts both ``str`` and ``Path`` arguments.
    """
    p = Path(path)
    if not p.exists():
        return default
    text = p.read_text()
    if not text.strip():
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default
