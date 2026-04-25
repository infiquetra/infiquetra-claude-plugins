"""Helper functions for text operations."""

def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """
    Return the plural form of a word based on count.

    If count == 1, return word unchanged.
    Otherwise, return plural if provided, else word + "s".
    Handles empty string: returns empty string regardless of count.

    Args:
        word: The word to pluralize
        count: The quantity determining singular vs plural
        plural: Optional custom plural form (e.g., "children" for "child")

    Returns:
        The singular or plural form appropriate for the count
    """
    if word == "":
        return ""

    if count == 1:
        return word

    if plural is not None:
        return plural

    return f"{word}s"
