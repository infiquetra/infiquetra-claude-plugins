"""Dictionary traversal helper utilities."""

from typing import Any


def get_nested(data: dict, path: str, default: Any = None) -> Any:
    """
    Get a nested value from a dict using a dotted path string.

    Args:
        data: The dictionary to traverse
        path: A dotted path string like "a.b.c"
        default: Value to return if path is missing or non-dict encountered

    Returns:
        The value at the path, or default if path cannot be traversed

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
    # Empty path returns the entire data
    if path == "":
        return data

    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return default
        if part not in current:
            return default
        current = current[part]

    return current
