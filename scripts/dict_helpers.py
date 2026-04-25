"""Dictionary helper functions for Infiquetra Claude Plugins."""

from typing import Any


def get_nested(data: dict, path: str, default: Any = None) -> Any:
    """
    Retrieve a value from a nested dictionary using a dotted path.

    Args:
        data: The dictionary to navigate
        path: A dotted path like "a.b.c" specifying the nested key
        default: Value to return if path doesn't exist

    Returns:
        The value at the nested path, or default if not found.
        Returns the entire data dict if path is empty.

    Examples:
        >>> get_nested({"a": {"b": 1}}, "a.b")
        1
        >>> get_nested({"a": {"b": 1}}, "a.c", default=-1)
        -1
        >>> get_nested({"a": 1}, "a.b") is None
        True
        >>> get_nested({}, "") == {}
        True
    """
    if path == "":
        return data

    keys = path.split(".")
    current = data

    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]

    return current
