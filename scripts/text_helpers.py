"""Text helper utilities for scripts."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return pluralized form of word based on count.

    Args:
        word: The word to pluralize.
        count: The count determining pluralization.
        plural: Optional custom plural form. If not provided, appends 's'.

    Returns:
        The word unchanged if count is 1, otherwise the plural form.
    """
    if word == "":
        return ""
    if count == 1:
        return word
    return plural if plural is not None else f"{word}s"
