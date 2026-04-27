from typing import Any

def get_nested(data: dict, path: str, default: Any = None) -> Any:
    """
    Walks a dictionary using a dotted path string and returns the deepest match.
    Returns the default value if any step in the path is missing or not a dictionary.
    """
    if not path:
        return data
    
    current = data
    for key in path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
            
    return current
