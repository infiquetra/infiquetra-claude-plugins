"""Text helper functions for Infiquetra Claude Plugins."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return the plural or singular form of a word based on its count.

    Args:
        word: The base word to pluralize
        count: The number of items (1 = singular, otherwise plural)
        plural: Optional custom plural form (e.g., "children" for "child")

    Returns:
        The singular form if count is 1, or the plural form if count != 1.
        Returns empty string if word is empty, regardless of count.

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
