"""Tests for scripts/changelog_heading_lint.py (#429)."""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    ("content", "exit_code", "diagnostic"),
    [
        (CANONICAL, 0, "all plugin CHANGELOGs match the canonical grammar"),
        (UNBRACKETED_VERSION, 1, "version heading must match"),
        (PLUGIN_NAME_SUFFIXED_TITLE, 1, "title must be exactly '# Changelog'"),
        (EM_DASH_DATE_SEPARATOR, 1, "version heading must match"),
    ],
)
def test_cli_exit_status_and_diagnostics(tmp_path, content, exit_code, diagnostic):
    """Exercise the executable boundary against an isolated fleet, including failures."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    script = scripts_dir / "changelog_heading_lint.py"
    shutil.copyfile(REPO_ROOT / "scripts" / script.name, script)
    changelog = tmp_path / "plugins" / "example" / "CHANGELOG.md"
    changelog.parent.mkdir(parents=True)
    changelog.write_text(content)

    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)

    assert result.returncode == exit_code
    if exit_code:
        assert result.stdout == ""
        assert str(changelog) in result.stderr
        assert diagnostic in result.stderr
    else:
        assert diagnostic in result.stdout
        assert result.stderr == ""
