"""Dictionary helper functions for path-based lookups."""

from typing import Any


def get_nested(data: dict, path: str, default=None) -> Any:
    """
    Get a value from a nested dictionary using a dotted path.

    Args:
        data: The dictionary to search.
        path: A dotted path like "a.b.c".
        default: The value to return if the path is not found.

    Returns:
        The value at the path, or default if not found.
        Returns data unchanged if path is empty.

    Examples:
        >>> get_nested({"a": {"b": 1}}, "a.b")
        1
        >>> get_nested({"a": {"b": 1}}, "a.c", default=-1)
        -1
        >>> get_nested({"a": 1}, "a.b")
        None
        >>> get_nested({}, "")
        {}
    """
    if path == "":
        return data

    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]

    return current
