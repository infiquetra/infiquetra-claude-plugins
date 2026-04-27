"""Tests for scripts.text_helpers module."""

import sys
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(
    0,
    str(Path(__file__).parent.parent / "scripts"),
)

from text_helpers import pluralize


def test_pluralize_returns_singular_when_count_is_one() -> None:
    """Asserts that pluralize returns word unchanged when count is exactly 1."""
    assert pluralize("cat", 1) == "cat"


def test_pluralize_adds_s_for_regular_plural() -> None:
    """Asserts that pluralize appends 's' when count is not 1 and no custom plural provided."""
    assert pluralize("cat", 2) == "cats"


def test_pluralize_uses_custom_plural_when_provided() -> None:
    """Asserts that pluralize uses custom plural when provided."""
    assert pluralize("child", 2, plural="children") == "children"


def test_pluralize_zero_count_uses_plural_form() -> None:
    """Asserts that pluralize returns plural form for zero count."""
    assert pluralize("cat", 0) == "cats"


def test_pluralize_empty_string_returns_empty_string() -> None:
    """Asserts that pluralize returns empty string regardless of count for empty input."""
    assert pluralize("", 5) == ""
