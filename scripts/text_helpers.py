"""Text helper utilities for scripts."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return the pluralized form of a word based on count.

    Args:
        word: The singular form of the word.
        count: The count to evaluate.
        plural: Optional custom plural form. If provided, used when count != 1.

    Returns:
        Empty string if word is empty.
        word unchanged if count == 1.
        plural if provided and count != 1.
        word + "s" otherwise.
    """
    if word == "":
        return ""
    if count == 1:
        return word
    if plural is not None:
        return plural
    return word + "s"
