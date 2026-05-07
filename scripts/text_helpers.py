"""Text utility helpers for Infiquetra scripts."""


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return the singular or plural form of *word* based on *count*.

    - If *word* is empty, returns empty string regardless of other arguments.
    - If *count* is 1, returns *word* unchanged.
    - Otherwise, returns *plural* if provided, else *word* + "s".
    """
    if word == "":
        return ""
    if count == 1:
        return word
    if plural is not None:
        return plural
    return f"{word}s"
