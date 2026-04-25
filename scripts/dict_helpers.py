"""Helper utilities for dictionary traversal."""

from typing import Any


def get_nested(data: dict, path: str, default: Any = None) -> Any:
    """Get a nested value from a dict using a dotted path.

    Args:
        data: The dict to traverse.
        path: Dotted string representing the key path (e.g., "a.b.c").
        default: Value to return if any step fails (missing key or non‑dict).

    Returns:
        The value at the deepest matching key if traversal succeeds;
        otherwise returns default.
    """
    if not path:
        return data

    current = data
    for segment in path.split("."):
        if not isinstance(current, dict):
            return default
        if segment not in current:
            return default
        current = current[segment]

    return current
