"""Text helper functions for scripts."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return singular or plural form of a word based on count.

    Args:
        word: The singular form of the word.
        count: The number determining singular/plural form.
        plural: Optional custom plural form. If not provided, appends 's'.

    Returns:
        The appropriate form of the word for the given count.
        Returns empty string if word is empty, regardless of count.
    """
    if word == "":
        return ""
    if count == 1:
        return word
    return plural if plural is not None else word + "s"
