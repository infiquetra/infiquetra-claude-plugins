"""Dictionary helper utilities."""

from typing import Any


def get_nested(data: dict, path: str, default: Any = None) -> Any:
    """Get a value from a nested dict using a dotted path.

    Args:
        data: The dictionary to traverse.
        path: Dotted path string (e.g., "a.b.c").
        default: Value to return if path is not found or traversal fails.

    Returns:
        The value at the path, or ``default`` if the path is invalid.
    """
    if path == "":
        return data
    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict):
            return default
        if key not in current:
            return default
        current = current[key]
    return current
