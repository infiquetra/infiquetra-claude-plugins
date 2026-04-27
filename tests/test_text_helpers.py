from scripts.text_helpers import pluralize


def test_pluralize_returns_singular_for_count_one():
    assert pluralize("cat", 1) == "cat"

def test_pluralize_adds_s_for_regular_plural():
    assert pluralize("cat", 2) == "cats"

def test_pluralize_uses_custom_plural_when_provided():
    assert pluralize("child", 2, plural="children") == "children"

def test_pluralize_zero_count_uses_plural_form():
    assert pluralize("cat", 0) == "cats"

def test_pluralize_empty_string_stays_empty():
    assert pluralize("", 5) == ""
