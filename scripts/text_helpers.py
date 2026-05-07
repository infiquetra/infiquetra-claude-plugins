"""Text helper utilities for string formatting."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return the singular or plural form of a word based on count.

    Args:
        word: The singular form of the word.
        count: The quantity determining singular vs. plural.
        plural: Custom plural form. If omitted, appends "s" to word.

    Returns:
        The appropriate form of the word, or empty string if word is empty.
    """
    if word == "":
        return ""
    if count == 1:
        return word
    if plural is not None:
        return plural
    return f"{word}s"
