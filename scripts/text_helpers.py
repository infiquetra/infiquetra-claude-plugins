"""Small text formatting helpers used by scripts."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return the plural form of a word based on count.

    Args:
        word: The word to pluralize.
        count: The count determining singular/plural form.
        plural: Optional custom plural form.

    Returns:
        The word unchanged if count is 1, otherwise the plural form.

    Examples:
        >>> pluralize("cat", 1)
        'cat'
        >>> pluralize("cat", 2)
        'cats'
        >>> pluralize("child", 2, plural="children")
        'children'
        >>> pluralize("", 5)
        ''
    """
    if word == "":
        return ""
    if count == 1:
        return word
    return plural if plural is not None else f"{word}s"
