"""Dict traversal helpers."""

from __future__ import annotations

from typing import Any


def get_nested(data: dict[str, Any], path: str, default: Any = None) -> Any:
    """Walk a dotted path through a dict and return the deepest match.

    Args:
        data: The dict to traverse.
        path: Dotted path segments, e.g. "a.b.c". Empty string returns data unchanged.
        default: Value to return when any step is not a dict or the key is missing.

    Returns:
        The value at the deepest matching key, or ``default`` on any failure.
    """
    if path == "":
        return data

    current: Any = data
    for segment in path.split("."):
        if not isinstance(current, dict):
            return default
        if segment not in current:
            return default
        current = current[segment]
    return current
