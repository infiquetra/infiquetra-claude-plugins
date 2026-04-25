"""Text helper utilities for Infiquetra scripts."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """
    Return a word in its plural form based on a count.

    If word is empty, returns empty string.
    If count is 1, returns word unchanged.
    Otherwise, returns plural if provided, else word + "s".
    """
    if not word:
        return ""

    if count == 1:
        return word

    if plural is not None:
        return plural

    return f"{word}s"
