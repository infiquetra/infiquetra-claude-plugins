"""Dict path lookup helpers."""

from typing import Any


def get_nested(data: dict, path: str, default: Any = None) -> Any:
    """Walk a dotted path into a nested dict, returning the deepest match.

    Args:
        data: The dict to traverse.
        path: Dot-separated key path, e.g. ``"a.b.c"``.
        default: Value returned when a key is missing or a step is not a dict.

    Returns:
        The value at the end of the path, or *default* if traversal fails.
    """
    if path == "":
        return data

    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current
