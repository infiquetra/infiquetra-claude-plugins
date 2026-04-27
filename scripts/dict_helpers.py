"""Dictionary helper utilities."""

from typing import Any


def get_nested(data: dict, path: str, default: Any = None) -> Any:
    """Traverse a dict using a dotted path and return the value.

    Args:
        data: The dictionary to traverse.
        path: A dotted string like "a.b.c" indicating nested keys.
        default: Value returned when a key is missing or traversal
                 reaches a non-dict before the path ends.

    Returns:
        The value at the end of the path, or *default* if the path
        cannot be fully followed.

    Examples:
        >>> get_nested({"a": {"b": 1}}, "a.b")
        1
        >>> get_nested({"a": {"b": 1}}, "a.c", default=-1)
        -1
        >>> get_nested({"a": 1}, "a.b") is None
        True
        >>> get_nested({}, "")
        {}
    """
    if path == "":
        return data

    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default

    return current
