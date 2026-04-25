"""Text helper functions for Infiquetra Claude Plugins."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """
    Pluralize a word based on count.

    Args:
        word: The word to potentially pluralize
        count: The count to determine if pluralization is needed
        plural: Custom plural form, if None uses word + "s"

    Returns:
        The word, pluralized if count != 1, or empty string if word is empty
    """
    # Handle empty string case first
    if word == "":
        return ""

    # If count is 1, return word unchanged
    if count == 1:
        return word

    # If custom plural provided, return it
    if plural is not None:
        return plural

    # Default pluralization
    return word + "s"
