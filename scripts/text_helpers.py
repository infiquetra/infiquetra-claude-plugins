"""Text helper utilities."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return the plural form of a word.

    Args:
        word: The singular noun to pluralize.
        count: The quantity determining singular vs plural.
        plural: Optional custom plural form. If None, default is word + "s".

    Returns:
        The empty string if word is empty.
        The unchanged word if count == 1.
        The provided plural if count != 1 and plural is not None.
        Otherwise word + "s".
    """
    if word == "":
        return ""
    if count == 1:
        return word
    return plural if plural is not None else f"{word}s"
