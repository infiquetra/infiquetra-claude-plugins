from scripts.text_helpers import pluralize

def test_pluralize_singular_returns_word():
    assert pluralize("cat", 1) == "cat"

def test_pluralize_regular_plural_adds_s():
    assert pluralize("cat", 2) == "cats"

def test_pluralize_custom_plural_uses_override():
    assert pluralize("child", 2, plural="children") == "children"

def test_pluralize_zero_count_uses_plural_form():
    assert pluralize("cat", 0) == "cats"

def test_pluralize_empty_string_returns_empty_string():
    assert pluralize("", 5) == ""
