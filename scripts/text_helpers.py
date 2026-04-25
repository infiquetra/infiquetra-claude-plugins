"""Text helper functions for Infiquetra Claude Plugins."""

def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """
    Pluralize a word based on count.

    Args:
        word: The singular form of the word
        count: The number of items
        plural: Optional custom plural form

    Returns:
        The appropriate form of the word based on count

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
