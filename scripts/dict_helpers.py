"""Dictionary helper utilities for dotted-path nested lookups."""

from typing import Any


def get_nested(data: dict[str, Any], path: str, default: Any = None) -> Any:
    """Walk a nested dict along a dotted path, returning the deepest match.

    Args:
        data: The dictionary to traverse.
        path: A dotted string like ``"a.b.c"``.
        default: Value returned when any step is missing or not a dict.

    Returns:
        The value at the end of the path, or *default* on failure.
        If *path* is empty, returns *data* unchanged.

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
    for segment in path.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            return default

    return current
