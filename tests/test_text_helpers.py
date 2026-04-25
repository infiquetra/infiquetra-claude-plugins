"""Tests for scripts/text_helpers.py."""

import sys
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from text_helpers import pluralize


def test_pluralize_singular() -> None:
    """Singular count returns word unchanged."""
    assert pluralize("cat", 1) == "cat"


def test_pluralize_regular_plural() -> None:
    """Count > 1 without custom plural appends 's'."""
    assert pluralize("cat", 2) == "cats"


def test_pluralize_custom_plural() -> None:
    """Custom plural form is used when count is not 1."""
    assert pluralize("child", 2, plural="children") == "children"


def test_pluralize_zero_count() -> None:
    """Zero count returns plural form."""
    assert pluralize("cat", 0) == "cats"


def test_pluralize_empty_string() -> None:
    """Empty string returns empty string regardless of count."""
    assert pluralize("", 5) == ""
