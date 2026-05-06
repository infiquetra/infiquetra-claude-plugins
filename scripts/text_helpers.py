"""Text helper utilities."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return the singular or plural form of ``word`` for ``count``."""
    if word == "":
        return ""
    if count == 1:
        return word
    return plural if plural is not None else f"{word}s"
