import json
from pathlib import Path
from typing import Any


def safe_json_load(path: str | Path, default: Any = None) -> Any:
    """
    Safely load a JSON file.

    Returns default if the file does not exist, is empty, or contains invalid JSON.
    Accepts both string and Path objects as input.
    """
    path = Path(path)

    if not path.exists():
        return default

    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return default
        return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return default
