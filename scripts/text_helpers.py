"""Text formatting helpers."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return the singular or plural form of a word for a count."""
    if word == "":
        return ""
    if count == 1:
        return word
    if plural is not None:
        return plural
    return f"{word}s"
