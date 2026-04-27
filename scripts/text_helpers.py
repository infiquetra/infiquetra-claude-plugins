"""Small text formatting helpers used by scripts."""

from __future__ import annotations


def pluralize(word: str, count: int, *, plural: str | None = None) -> str:
    """Return `word` pluralized by `count`.

    Rules:
    - Empty string input always returns empty string (regardless of count).
    - count == 1 returns word unchanged.
    - Otherwise returns `plural` if provided, else word + "s".
    """
    if word == "":
        return ""
    if count == 1:
        return word
    return plural if plural is not None else f"{word}s"
