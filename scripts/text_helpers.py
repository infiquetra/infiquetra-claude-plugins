"""Text formatting helpers for Infiquetra Claude plugins."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return the correct singular or plural form of a word based on count.

    Args:
        word: The singular form of the word.
        count: The number to determine singular/plural form.
        plural: Optional custom plural form. If not provided, appends "s".

    Returns:
        The word unchanged if count is 1, otherwise the plural form.
        Empty string input returns empty string regardless of count.
    """
    if word == "":
        return ""
    if count == 1:
        return word
    return plural if plural is not None else f"{word}s"
