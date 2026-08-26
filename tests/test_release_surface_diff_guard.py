"""Tests for tools/release_surface_diff_guard.py (#429, #842)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
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


def make_manifest_reader(manifests: dict[tuple[str, str], str | None]):
    def reader(ref: str, path: str) -> str | None:
        return manifests.get((ref, path))

    return reader


def test_skill_edit_without_bump_fails():
    violations = GUARD.find_violations(["plugins/foo/skills/x/SKILL.md"])

    assert len(violations) == 1
    assert "foo" in violations[0]
    assert (
        "non-doc files changed without a matching plugin.json + CHANGELOG.md bump" in violations[0]
    )


def test_skill_edit_with_bump_passes():
    reader = make_manifest_reader(
        {
            ("base", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.0.0"}
            ),
            ("HEAD", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.1.0"}
            ),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert violations == []


def test_version_equal_to_base_ref_fails():
    reader = make_manifest_reader(
        {
            ("base", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.0.0"}
            ),
            ("HEAD", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.0.0"}
            ),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "foo" in violations[0]
    assert "'1.0.0'" in violations[0]
    assert "equal to base-ref version '1.0.0'" in violations[0]


def test_version_lower_than_base_ref_fails():
    reader = make_manifest_reader(
        {
            ("base", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.1.0"}
            ),
            ("HEAD", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.0.0"}
            ),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "foo" in violations[0]
    assert "'1.0.0'" in violations[0]
    assert "'1.1.0'" in violations[0]
    assert "lower than base-ref version '1.1.0'" in violations[0]


def test_version_greater_than_base_ref_passes():
    reader = make_manifest_reader(
        {
            ("base", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "0.141.0"}
            ),
            ("HEAD", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "0.142.0"}
            ),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert violations == []


def test_missing_head_manifest_fails():
    reader = make_manifest_reader(
        {
            ("base", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.0.0"}
            ),
            ("HEAD", "plugins/foo/.claude-plugin/plugin.json"): None,
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "foo" in violations[0]
    assert "proposed manifest plugins/foo/.claude-plugin/plugin.json is missing" in violations[0]
    assert "'1.0.0'" in violations[0]


def test_invalid_json_head_manifest_fails():
    reader = make_manifest_reader(
        {
            ("base", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.0.0"}
            ),
            ("HEAD", "plugins/foo/.claude-plugin/plugin.json"): "{invalid-json",
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "foo" in violations[0]
    assert (
        "proposed manifest plugins/foo/.claude-plugin/plugin.json has invalid JSON" in violations[0]
    )
    assert "'1.0.0'" in violations[0]


def test_missing_version_key_head_manifest_fails():
    reader = make_manifest_reader(
        {
            ("base", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.0.0"}
            ),
            ("HEAD", "plugins/foo/.claude-plugin/plugin.json"): json.dumps({"name": "foo"}),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "foo" in violations[0]
    assert (
        "proposed manifest plugins/foo/.claude-plugin/plugin.json is missing 'version' key"
        in violations[0]
    )
    assert "'1.0.0'" in violations[0]


def test_non_string_version_head_manifest_fails():
    reader = make_manifest_reader(
        {
            ("base", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.0.0"}
            ),
            ("HEAD", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": None}
            ),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "foo" in violations[0]
    assert (
        "proposed manifest plugins/foo/.claude-plugin/plugin.json 'version' is not a string (None)"
        in violations[0]
    )
    assert "'1.0.0'" in violations[0]


def test_malformed_head_version_fails():
    reader = make_manifest_reader(
        {
            ("base", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.0.0"}
            ),
            ("HEAD", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "invalid-version"}
            ),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "foo" in violations[0]
    assert "'invalid-version'" in violations[0]
    assert "'1.0.0'" in violations[0]
    assert "malformed" in violations[0]


def test_invalid_json_base_manifest_fails():
    reader = make_manifest_reader(
        {
            ("base", "plugins/foo/.claude-plugin/plugin.json"): "not-json",
            ("HEAD", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.0.1"}
            ),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "foo" in violations[0]
    assert (
        "base-ref manifest plugins/foo/.claude-plugin/plugin.json has invalid JSON" in violations[0]
    )
    assert "'1.0.1'" in violations[0]


def test_missing_version_key_base_manifest_fails():
    reader = make_manifest_reader(
        {
            ("base", "plugins/foo/.claude-plugin/plugin.json"): json.dumps({"name": "foo"}),
            ("HEAD", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.0.1"}
            ),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "foo" in violations[0]
    assert (
        "base-ref manifest plugins/foo/.claude-plugin/plugin.json is missing 'version' key"
        in violations[0]
    )
    assert "'1.0.1'" in violations[0]


def test_non_string_version_base_manifest_fails():
    reader = make_manifest_reader(
        {
            ("base", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": 123}
            ),
            ("HEAD", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.0.1"}
            ),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "foo" in violations[0]
    assert (
        "base-ref manifest plugins/foo/.claude-plugin/plugin.json 'version' is not a string (123)"
        in violations[0]
    )
    assert "'1.0.1'" in violations[0]


def test_malformed_base_version_fails():
    reader = make_manifest_reader(
        {
            ("base", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "bad-base"}
            ),
            ("HEAD", "plugins/foo/.claude-plugin/plugin.json"): json.dumps(
                {"name": "foo", "version": "1.0.1"}
            ),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",
            "plugins/foo/.claude-plugin/plugin.json",
            "plugins/foo/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "foo" in violations[0]
    assert "'bad-base'" in violations[0]
    assert "'1.0.1'" in violations[0]
    assert (
        "base-ref manifest plugins/foo/.claude-plugin/plugin.json version 'bad-base' is malformed"
        in violations[0]
    )


def test_new_plugin_with_valid_version_passes():
    reader = make_manifest_reader(
        {
            ("base", "plugins/newplugin/.claude-plugin/plugin.json"): None,
            ("HEAD", "plugins/newplugin/.claude-plugin/plugin.json"): json.dumps(
                {"name": "newplugin", "version": "0.1.0"}
            ),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/newplugin/skills/x/SKILL.md",
            "plugins/newplugin/.claude-plugin/plugin.json",
            "plugins/newplugin/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert violations == []


def test_new_plugin_with_malformed_version_fails():
    reader = make_manifest_reader(
        {
            ("base", "plugins/newplugin/.claude-plugin/plugin.json"): None,
            ("HEAD", "plugins/newplugin/.claude-plugin/plugin.json"): json.dumps(
                {"name": "newplugin", "version": "not-semver"}
            ),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/newplugin/skills/x/SKILL.md",
            "plugins/newplugin/.claude-plugin/plugin.json",
            "plugins/newplugin/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "newplugin" in violations[0]
    assert "'not-semver'" in violations[0]
    assert "<absent>" in violations[0]
    assert "malformed" in violations[0]


def test_new_plugin_with_invalid_json_fails():
    reader = make_manifest_reader(
        {
            ("base", "plugins/newplugin/.claude-plugin/plugin.json"): None,
            ("HEAD", "plugins/newplugin/.claude-plugin/plugin.json"): "{bad-json",
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/newplugin/skills/x/SKILL.md",
            "plugins/newplugin/.claude-plugin/plugin.json",
            "plugins/newplugin/CHANGELOG.md",
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "newplugin" in violations[0]
    assert "invalid JSON" in violations[0]
    assert "<absent>" in violations[0]


@pytest.mark.parametrize(
    "path",
    [
        "plugins/foo/README.md",
        "plugins/foo/skills/x/README.md",
        "plugins/foo/docs/architecture.md",
        "plugins/foo/docs/guide/deep.md",
        "plugins/foo/tests/test_x.py",
        "plugins/foo/scripts/tests/test_y.py",
    ],
)
def test_doc_only_change_not_required_to_bump(path):
    violations = GUARD.find_violations([path])

    assert violations == []


def test_multi_plugin_diff_isolates_correctly():
    reader = make_manifest_reader(
        {
            ("base", "plugins/bar/.claude-plugin/plugin.json"): json.dumps(
                {"name": "bar", "version": "1.0.0"}
            ),
            ("HEAD", "plugins/bar/.claude-plugin/plugin.json"): json.dumps(
                {"name": "bar", "version": "1.0.1"}
            ),
        }
    )
    violations = GUARD.find_violations(
        [
            "plugins/foo/skills/x/SKILL.md",  # non-compliant: no bump
            "plugins/bar/skills/y/SKILL.md",
            "plugins/bar/.claude-plugin/plugin.json",
            "plugins/bar/CHANGELOG.md",  # compliant
        ],
        manifest_reader=reader,
    )

    assert len(violations) == 1
    assert "foo" in violations[0]
    assert "bar" not in violations[0]


@pytest.mark.parametrize(
    ("v1", "v2", "expected"),
    [
        ("1.0.0", "1.0.1", True),
        ("1.0.1", "1.0.0", False),
        ("1.0.0", "1.0.0", False),
        ("0.1.0", "0.2.0", True),
        ("1.9.9", "2.0.0", True),
        ("1.0.0-alpha", "1.0.0", True),
        ("1.0.0-alpha.1", "1.0.0-alpha.2", True),
        ("1.0.0-alpha.1", "1.0.0-alpha.beta", True),
        ("1.0.0-beta", "1.0.0-rc.1", True),
        ("1.0.0-rc.1", "1.0.0", True),
        ("1.0.0+build1", "1.0.0+build2", False),  # build metadata has equal precedence
    ],
)
def test_semver_precedence(v1: str, v2: str, expected: bool):
    s1 = GUARD.parse_semver(v1)
    s2 = GUARD.parse_semver(v2)
    assert s1 is not None
    assert s2 is not None
    assert (s1 < s2) == expected


@pytest.mark.parametrize(
    "invalid",
    [
        "1.0",
        "1.0.0.0",
        "v1.0.0",
        "01.0.0",
        "1.01.0",
        "1.0.01",
        "1.0.0-01",
        "latest",
        "",
        None,
    ],
)
def test_semver_invalid_parsing(invalid: str | None):
    assert GUARD.parse_semver(invalid) is None


def test_git_base_ref_tip_collision_fails(tmp_path: Path):
    """Reproduction of the #833/#834 collision:

    Branch B branched from main at 1.0.0 and bumps to 1.0.1.
    Meanwhile, Branch A merges into main bumping to 1.0.1.
    Branch B tested against the updated main tip must fail because 1.0.1 is not > main's 1.0.1.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    plugin_dir = repo / "plugins" / "sample"
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / "skills" / "sample-skill").mkdir(parents=True)

    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    manifest.write_text(json.dumps({"name": "sample", "version": "1.0.0"}))
    changelog = plugin_dir / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [1.0.0] - 2026-08-26\n- initial\n")
    skill = plugin_dir / "skills" / "sample-skill" / "SKILL.md"
    skill.write_text("# Skill\n")

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit (1.0.0)"], cwd=repo, check=True, capture_output=True
    )

    # Branch B branches from 1.0.0
    subprocess.run(["git", "checkout", "-b", "branch-b"], cwd=repo, check=True, capture_output=True)
    skill.write_text("# Skill modified by B\n")
    manifest.write_text(json.dumps({"name": "sample", "version": "1.0.1"}))
    changelog.write_text(
        "# Changelog\n\n## [1.0.1] - 2026-08-26\n- branch B\n## [1.0.0] - 2026-08-26\n- initial\n"
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "branch B bumps to 1.0.1"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Meanwhile on main (simulating Branch A merging): bump to 1.0.1
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)
    skill.write_text("# Skill modified by A\n")
    manifest.write_text(json.dumps({"name": "sample", "version": "1.0.1"}))
    changelog.write_text(
        "# Changelog\n\n## [1.0.1] - 2026-08-26\n- branch A\n## [1.0.0] - 2026-08-26\n- initial\n"
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "branch A merges to main with 1.0.1"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Switch back to branch-b and run guard against main
    subprocess.run(["git", "checkout", "branch-b"], cwd=repo, check=True, capture_output=True)

    def repo_runner(cmd, **kwargs):
        return subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False)

    paths = GUARD.changed_files("main", runner=repo_runner)
    violations = GUARD.find_violations(paths, base_ref="main", runner=repo_runner)

    # Branch B must FAIL against main tip because main already has 1.0.1
    assert len(violations) == 1
    assert "sample" in violations[0]
    assert "'1.0.1'" in violations[0]
    assert "equal to base-ref version '1.0.1'" in violations[0]


def test_committed_content_vs_working_tree_in_git_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    plugin_dir = repo / "plugins" / "sample"
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / "skills" / "sample-skill").mkdir(parents=True)

    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    manifest.write_text(json.dumps({"name": "sample", "version": "1.0.0"}))
    changelog = plugin_dir / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [1.0.0] - 2026-08-26\n- initial\n")
    skill = plugin_dir / "skills" / "sample-skill" / "SKILL.md"
    skill.write_text("# Skill\n")

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"], cwd=repo, check=True, capture_output=True
    )

    # Create feature branch
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, check=True, capture_output=True)

    # 1. Advance version in committed HEAD: 1.0.0 -> 1.0.1
    skill.write_text("# Skill modified\n")
    manifest.write_text(json.dumps({"name": "sample", "version": "1.0.1"}))
    changelog.write_text(
        "# Changelog\n\n## [1.0.1] - 2026-08-26\n- bumped\n## [1.0.0] - 2026-08-26\n- initial\n"
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "bump version"], cwd=repo, check=True, capture_output=True
    )

    # Dirty the working tree with an uncommitted downgrade (1.0.0)
    manifest.write_text(json.dumps({"name": "sample", "version": "1.0.0"}))

    def repo_runner(cmd, **kwargs):
        return subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False)

    # Guard must read committed HEAD (1.0.1) and pass, ignoring uncommitted working tree
    paths = GUARD.changed_files("main", runner=repo_runner)
    violations = GUARD.find_violations(paths, base_ref="main", runner=repo_runner)
    assert violations == []


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


def test_changed_files_runner_is_keyword_only():
    """runner must be keyword-only (house convention) — a positional call is a TypeError."""
    with pytest.raises(TypeError):
        GUARD.changed_files("origin/main", lambda cmd, **kwargs: None)


def test_changed_files_raises_on_nonzero_exit():
    def failing_runner(cmd, **kwargs):
        class Result:
            returncode = 1
            stdout = ""
            stderr = "unknown revision"

        return Result()

    with pytest.raises(GUARD.DiffGuardError):
        GUARD.changed_files("origin/main", runner=failing_runner)


def test_main_parses_base_ref_flag(monkeypatch):
    captured = {}

    def fake_changed_files(base_ref, **kwargs):
        captured["base_ref"] = base_ref
        return []

    monkeypatch.setattr(GUARD, "changed_files", fake_changed_files)

    rc = GUARD.main(["--base-ref", "abc1234"])

    assert rc == 0
    assert captured == {"base_ref": "abc1234"}


def test_main_defaults_base_ref_to_origin_main(monkeypatch):
    captured = {}

    def fake_changed_files(base_ref, **kwargs):
        captured["base_ref"] = base_ref
        return []

    monkeypatch.setattr(GUARD, "changed_files", fake_changed_files)

    GUARD.main([])

    assert captured == {"base_ref": GUARD.DEFAULT_BASE_REF}


def test_main_reports_violations_and_exits_1(monkeypatch, capsys):
    monkeypatch.setattr(
        GUARD, "changed_files", lambda base_ref, **kwargs: ["plugins/foo/skills/x/SKILL.md"]
    )
    monkeypatch.setattr(
        GUARD,
        "find_violations",
        lambda paths, base_ref=GUARD.DEFAULT_BASE_REF, **kwargs: [
            "foo: proposed manifest version '1.0.0' is equal to base-ref version '1.0.0' (must be strictly greater)"
        ],
    )

    rc = GUARD.main([])
    assert rc == 1
    captured = capsys.readouterr()
    assert "release_surface_diff_guard: violations found:" in captured.err
    assert (
        "foo: proposed manifest version '1.0.0' is equal to base-ref version '1.0.0'"
        in captured.err
    )


def test_main_handles_diff_guard_error(monkeypatch, capsys):
    def failing_changed_files(base_ref, **kwargs):
        raise GUARD.DiffGuardError("git diff failed")

    monkeypatch.setattr(GUARD, "changed_files", failing_changed_files)

    rc = GUARD.main([])
    assert rc == 1
    captured = capsys.readouterr()
    assert "release_surface_diff_guard: git diff failed" in captured.err
