"""Dictionary helper utilities for safe nested value lookup."""

from typing import Any


def get_nested(data: dict, path: str, default=None) -> Any:
    """
    Safely retrieve a nested value from a dictionary using a dotted path.

    Args:
        data: The dictionary to traverse
        path: A dotted string like "a.b.c" specifying the nested path
        default: Value to return if any key in the path is missing or
                 if we encounter a non-dict before the final segment

    Returns:
        The value at the nested path, or default if the path is invalid
    """
    # Handle empty path - return entire data
    if path == "":
        return data

    current: Any = data

    for segment in path.split("."):
        # Only continue if current is a dict and the key exists
        if not isinstance(current, dict) or segment not in current:
            return default
        current = current[segment]

    return current
