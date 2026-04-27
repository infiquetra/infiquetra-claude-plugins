"""Text formatting utilities for Infiquetra Claude plugins."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return the singular or plural form of *word* based on *count*.

    Args:
        word: The word to pluralize.
        count: Determines singular (1) vs plural (all other values).
        plural: Optional explicit plural override. When provided and
            *count* is not 1, this value is returned instead of
            *word* + "s".

    Returns:
        *word* unchanged when *count* == 1.
        *plural* when provided and *count* != 1.
        *word* + ``"s"`` otherwise.
        Empty string when *word* is empty, regardless of *count*.

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

    if plural is not None:
        return plural

    return word + "s"
