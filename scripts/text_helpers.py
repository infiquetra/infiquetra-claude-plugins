"""Text helpers for Infiquetra Claude Code plugins."""

from __future__ import annotations


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return the singular or plural form of a word based on count.

    Args:
        word: The singular form of the word.
        count: The count to determine singular vs plural.
        plural: Optional custom plural form. If not provided, appends "s".

    Returns:
        The word unchanged if count is 1, otherwise the plural form.
        Returns empty string if word is empty, regardless of count.
    """
    if word == "":
        return ""
    if count == 1:
        return word
    return plural if plural is not None else word + "s"
