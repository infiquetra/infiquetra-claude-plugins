from typing import Any


def get_nested(data: dict, path: str, default=None) -> Any:
    """
    Walks a dictionary using a dotted path and returns the deepest match.

    Args:
        data: The dictionary to traverse.
        path: A dotted string representing the path (e.g., "a.b.c").
        default: Value to return if any key in the path is missing or if
                 a step in the path is not a dictionary.

    Returns:
        The value at the end of the path, or the default value.
    """
    if path == "":
        return data

    current = data
    for key in path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default

    return current
