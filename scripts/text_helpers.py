"""Small text helper utilities for scripts."""

def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """
    Pluralize a word based on a count.

    - If word is empty, returns empty string.
    - If count is 1, returns the singular word.
    - If count is not 1 and a custom plural is provided, returns custom plural.
    - Otherwise, returns the word with 's' appended.
    """
    if word == "":
        return ""
    if count == 1:
        return word
    if plural is not None:
        return plural
    return f"{word}s"
