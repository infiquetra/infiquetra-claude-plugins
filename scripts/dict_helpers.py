"""Dictionary helper utilities."""

from typing import Any


def get_nested(data: dict, path: str, default: Any = None) -> Any:
    """Walk a dotted path through a nested dictionary.

    Args:
        data: The dictionary to traverse.
        path: Dotted string of keys, e.g. "a.b.c".
        default: Value to return when a key is missing or a step is not a dict.

    Returns:
        The value at the deepest key, or ``default`` when traversal fails.
        An empty ``path`` returns ``data`` itself without mutation or copying.
    """
    if path == "":
        return data

    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current
