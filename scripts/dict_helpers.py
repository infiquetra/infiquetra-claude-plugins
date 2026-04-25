from typing import Any


def get_nested(data: dict, path: str, default: Any = None) -> Any:
    """
    Get a value from a nested dictionary using a dotted path.

    Args:
        data: The dictionary to search.
        path: A dotted string path like "a.b.c".
        default: The value to return if the path is not found or a step is not a dict.

    Returns:
        The value at the path or the default value.
    """
    if not path:
        return data

    current = data
    for segment in path.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            return default

    return current
