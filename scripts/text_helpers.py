def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """
    Pluralizes a word based on the count.

    If the word is empty, returns an empty string.
    If count is 1, returns the word unchanged.
    Otherwise, returns the custom plural if provided, or the word with 's' appended.
    """
    if word == "":
        return ""
    if count == 1:
        return word
    return plural if plural is not None else f"{word}s"
