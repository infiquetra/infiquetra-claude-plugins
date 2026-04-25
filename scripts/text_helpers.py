"""Text helper utilities for Infiquetra plugins."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return the singular or plural form of a word based on count.

    Args:
        word: The singular form of the word.
        count: The quantity determining which form to use.
        plural: Optional override for the plural form.

    Returns:
        The word unchanged if count is 1, otherwise the plural form.
        Returns empty string if word is empty.
    """
    if word == "":
        return ""
    if count == 1:
        return word
    return plural if plural is not None else word + "s"
