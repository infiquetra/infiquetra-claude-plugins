"""Tests for tools/release_surface_diff_guard.py (#429)."""

import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "release_surface_diff_guard",
    Path(__file__).parent.parent / "tools" / "release_surface_diff_guard.py",
)
assert _SPEC is not None and _SPEC.loader is not None
GUARD = importlib.util.module_from_spec(_SPEC)
sys.modules["release_surface_diff_guard"] = GUARD
_SPEC.loader.exec_module(GUARD)


def test_skill_edit_without_bump_fails():
    violations = GUARD.find_violations(["plugins/foo/skills/x/SKILL.md"])

    assert violations == ["foo"]


def test_skill_edit_with_bump_passes():
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ]
    )

    assert violations == []


@pytest.mark.parametrize(
    "path",
    [
        "plugins/foo/README.md",
        "plugins/foo/tests/test_x.py",
        "plugins/foo/scripts/tests/test_y.py",
    ],
)
def test_doc_only_change_not_required_to_bump(path):
    violations = GUARD.find_violations([path])

    assert violations == []


def test_multi_plugin_diff_isolates_correctly():
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",  # non-compliant: no bump
            "plugins/bar/skills/y/SKILL.md",
            "plugins/bar/.claude-plugin/plugin.json",
            "plugins/bar/CHANGELOG.md",  # compliant
        ]
    )

    assert violations == ["foo"]


def test_changed_files_parses_runner_output():
    def fake_runner(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = "plugins/foo/skills/x/SKILL.md\nplugins/foo/.claude-plugin/plugin.json\n"
            stderr = ""

        return Result()

    paths = GUARD.changed_files("origin/main", runner=fake_runner)

    assert paths == [
        "plugins/foo/skills/x/SKILL.md",
        "plugins/foo/.claude-plugin/plugin.json",
    ]


def test_changed_files_raises_on_nonzero_exit():
    def failing_runner(cmd, **kwargs):
        class Result:
            returncode = 1
            stdout = ""
            stderr = "unknown revision"

        return Result()

    with pytest.raises(GUARD.DiffGuardError):
        GUARD.changed_files("origin/main", runner=failing_runner)
