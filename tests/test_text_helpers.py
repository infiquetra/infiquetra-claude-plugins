"""Tests for scripts.text_helpers.pluralize."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from text_helpers import pluralize  # noqa: E402


def test_pluralize_returns_singular_for_count_one():
    assert pluralize("cat", 1) == "cat"


def test_pluralize_adds_s_for_regular_plural():
    assert pluralize("cat", 2) == "cats"


def test_pluralize_uses_custom_plural():
    assert pluralize("child", 2, plural="children") == "children"


def test_pluralize_zero_count_uses_plural_form():
    assert pluralize("cat", 0) == "cats"


def test_pluralize_empty_string_returns_empty():
    assert pluralize("", 5) == ""
    assert pluralize("", 1) == ""
