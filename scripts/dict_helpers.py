"""Dictionary helper functions for path-based lookups."""

from typing import Any


def get_nested(data: dict, path: str, default=None) -> Any:
    """
    Get a value from a nested dictionary using a dotted path.

    Args:
        data: The dictionary to traverse.
        path: A dotted string like "a.b.c" specifying the path.
        default: Value to return if path is not found. Defaults to None.

    Returns:
        The value at the path, default if not found, or the entire data
        if path is empty.
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
