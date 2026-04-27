from scripts.text_helpers import pluralize


def test_pluralize_returns_word_for_singular_count() -> None:
    assert pluralize("cat", 1) == "cat"


def test_pluralize_adds_s_for_regular_plural() -> None:
    assert pluralize("cat", 2) == "cats"


def test_pluralize_uses_custom_plural() -> None:
    assert pluralize("child", 2, plural="children") == "children"


def test_pluralize_zero_count_uses_plural_form() -> None:
    assert pluralize("cat", 0) == "cats"


def test_pluralize_empty_string_returns_empty_string() -> None:
    assert pluralize("", 5) == ""
