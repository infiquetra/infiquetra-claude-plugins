"""Tests for scripts/changelog_heading_lint.py (#429)."""

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "changelog_heading_lint",
    Path(__file__).parent.parent / "scripts" / "changelog_heading_lint.py",
)
assert _SPEC is not None and _SPEC.loader is not None
CHL = importlib.util.module_from_spec(_SPEC)
sys.modules["changelog_heading_lint"] = CHL
_SPEC.loader.exec_module(CHL)

REPO_ROOT = Path(__file__).parent.parent

CANONICAL = """# Changelog

## [Unreleased]

## [1.0.0] - 2026-07-01

### Added
- Initial release.
"""

UNBRACKETED_VERSION = """# Changelog

## 1.0.0 - 2026-07-01

### Added
- Initial release.
"""

PLUGIN_NAME_SUFFIXED_TITLE = """# Changelog - some-plugin

## [1.0.0] - 2026-07-01

### Added
- Initial release.
"""

EM_DASH_DATE_SEPARATOR = """# Changelog

## [1.0.0] — 2026-07-01

### Added
- Initial release.
"""


def test_accepts_canonical_heading(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CANONICAL)

    assert CHL.lint_changelog(changelog) == []


def test_rejects_noncanonical_heading(tmp_path):
    for name, content in (
        ("unbracketed", UNBRACKETED_VERSION),
        ("suffixed_title", PLUGIN_NAME_SUFFIXED_TITLE),
        ("em_dash", EM_DASH_DATE_SEPARATOR),
    ):
        changelog = tmp_path / f"{name}.md"
        changelog.write_text(content)

        failures = CHL.lint_changelog(changelog)

        assert failures, f"{name} should have failed the lint"


def test_fleet_baseline():
    """Live fleet baseline — written against U1-U3's combined output, not run standalone before U3."""
    results = CHL.lint_fleet(REPO_ROOT / "plugins")

    assert results == {}, f"non-conforming CHANGELOGs: {sorted(str(p) for p in results)}"
