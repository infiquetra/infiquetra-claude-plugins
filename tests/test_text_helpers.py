"""Tests for scripts.text_helpers."""

import sys
from pathlib import Path

# Add repo root to path so scripts module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.text_helpers import pluralize


def test_pluralize_returns_word_for_singular_count():
    assert pluralize("cat", 1) == "cat"


def test_pluralize_adds_s_for_regular_plural():
    assert pluralize("cat", 2) == "cats"


def test_pluralize_uses_custom_plural_when_provided():
    assert pluralize("child", 2, plural="children") == "children"


def test_pluralize_treats_zero_as_plural():
    assert pluralize("cat", 0) == "cats"


def test_pluralize_returns_empty_string_regardless_of_count():
    assert pluralize("", 5) == ""
    assert pluralize("", 1) == ""
