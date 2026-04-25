"""Dictionary helper utilities for nested path lookups."""

from typing import Any


def get_nested(data: dict, path: str, default: Any = None) -> Any:
    """Retrieve a value from a nested dict using a dotted path string.

    Args:
        data: The dictionary to search.
        path: A dotted string path like "a.b.c" to traverse.
        default: The value to return if any step fails (default: None).

    Returns:
        The value at the path if found, otherwise the default.

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

    current_value: Any = data

    for segment in path.split("."):
        if not isinstance(current_value, dict):
            return default
        if segment not in current_value:
            return default
        current_value = current_value[segment]

    return current_value
