"""Helper functions for dictionary operations."""

from typing import Any


def get_nested(data: dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Get a nested value from a dictionary using a dotted path string.

    Args:
        data: The dictionary to traverse
        path: Dot-separated path string (e.g., "a.b.c")
        default: Default value to return if path not found

    Returns:
        The value at the nested path, or default if not found
    """
    # Handle empty path case
    if path == "":
        return data

    # Traverse the path
    current = data
    for segment in path.split("."):
        # Check if current is a dictionary
        if not isinstance(current, dict):
            return default

        # Check if segment exists in current dictionary
        if segment not in current:
            return default

        # Move to the next level
        current = current[segment]

    return current
