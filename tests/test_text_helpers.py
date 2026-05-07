"""Unit tests for text_helpers.pluralize."""

import sys
from pathlib import Path

# Add scripts directory to path so we can import text_helpers directly.
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from text_helpers import pluralize


def test_pluralize_returns_singular_when_count_is_one():
    assert pluralize("cat", 1) == "cat"


def test_pluralize_adds_s_for_regular_plural():
    assert pluralize("cat", 2) == "cats"


def test_pluralize_uses_custom_plural():
    assert pluralize("child", 2, plural="children") == "children"


def test_pluralize_zero_count_uses_plural_form():
    assert pluralize("cat", 0) == "cats"


def test_pluralize_empty_string_returns_empty_string():
    assert pluralize("", 5) == ""
    assert pluralize("", 1) == ""
    assert pluralize("", 2, plural="children") == ""
