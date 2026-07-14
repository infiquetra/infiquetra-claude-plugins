"""Tests for the write-ownership lane lint (issue #431).

Covers the clean-pass case against the real saga / mission-control / deploy directories
(AC2 / AC5), the seeded cross-lane-violation gate (AC3, via a throwaway fixture — never a
live edit to plugins/deploy/), the reserved ``gh api projects/`` board-surface guard, loud
failure on a malformed/missing manifest, and a drift guard that the lint stays wired into
the marketplace CI job (AC4).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).parent
REPO_ROOT = TESTS_ROOT.parent
SCRIPTS_ROOT = REPO_ROOT / "scripts"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import check_ownership_lanes as col  # noqa: E402

REAL_MANIFEST = REPO_ROOT / "marketplace" / "ownership_lanes.json"
REAL_PLUGINS_ROOT = REPO_ROOT / "plugins"


def _write_plugin_script(root: Path, plugin: str, relpath: str, body: str) -> Path:
    path = root / plugin / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


@pytest.fixture
def manifest() -> dict[str, object]:
    return col.load_manifest(REAL_MANIFEST)


# --------------------------------------------------------------------------- AC1


def test_real_manifest_is_valid_json() -> None:
    """AC1: the shipped manifest parses and declares the three named lanes."""
    data = json.loads(REAL_MANIFEST.read_text())
    for plugin in ("saga", "mission-control", "deploy"):
        assert plugin in data["lanes"]
        assert isinstance(data["lanes"][plugin]["allowed_gh_subcommands"], list)


# ------------------------------------------------------------------ AC2 / AC5


def test_real_tree_is_clean(manifest: dict[str, object]) -> None:
    """AC2 / AC5: the real saga / mission-control / deploy scripts have zero violations."""
    violations = col.run_check(manifest, REAL_PLUGINS_ROOT)
    assert violations == [], "\n".join(v.render(REAL_PLUGINS_ROOT) for v in violations)


def test_main_exit_zero_on_real_tree() -> None:
    """AC2: the CLI entrypoint exits 0 against the real tree."""
    rc = col.main(["--manifest", str(REAL_MANIFEST), "--plugins-root", str(REAL_PLUGINS_ROOT)])
    assert rc == 0


# --------------------------------------------------------------------------- AC3


def test_seeded_violation_deploy_calls_gh_issue(
    tmp_path: Path, manifest: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    """AC3: a throwaway deploy-lane script calling `gh issue` trips the lint by name."""
    offender = _write_plugin_script(
        tmp_path,
        "deploy",
        "scripts/rogue_promote.py",
        "import subprocess\n"
        'subprocess.run(["gh", "issue", "create", "--title", "oops"], check=True)\n',
    )

    violations = col.run_check(manifest, tmp_path)
    assert len(violations) == 1
    v = violations[0]
    assert v.plugin == "deploy"
    assert v.call == "gh issue"
    assert v.file == offender
    assert "mission-control" in v.crossed_into

    rc = col.main(["--manifest", str(REAL_MANIFEST), "--plugins-root", str(tmp_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "rogue_promote.py" in err
    assert "gh issue" in err


def test_seeded_violation_reserved_api_path(tmp_path: Path, manifest: dict[str, object]) -> None:
    """A saga-lane script writing board fields via `gh api projects/` crosses into mc."""
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/rogue_board.py",
        "import subprocess\n"
        "pid = 42\n"
        'subprocess.run(["gh", "api", "--method", "PATCH", f"projects/{pid}/items"])\n',
    )
    violations = col.run_check(manifest, tmp_path)
    assert len(violations) == 1
    assert violations[0].crossed_into == "mission-control"
    assert "projects/" in violations[0].call


# --------------------------------------------------------------- detection unit


def test_find_gh_invocations_ignores_docstrings_and_messages() -> None:
    """Docstrings/comments/error strings that merely mention gh are not real calls."""
    source = (
        "def f():\n"
        '    """Reads `gh issue view` off the node."""\n'
        "    # gh pr merge is saga's job\n"
        '    msg = "gh pr view failed; degrading safe"\n'
        "    return msg\n"
    )
    assert col.find_gh_invocations(source) == []


def test_find_gh_invocations_skips_dynamic_command() -> None:
    """`["gh"] + args` has no literal subcommand and must be skipped (not flagged)."""
    invs = col.find_gh_invocations('cmd = ["gh"] + args\n')
    assert len(invs) == 1
    assert invs[0].subcommand is None


def test_find_gh_invocations_reads_list_subcommand() -> None:
    invs = col.find_gh_invocations('run(["gh", "pr", "create", "--fill"])\n')
    assert len(invs) == 1
    assert invs[0].subcommand == "pr"


def test_find_gh_invocations_reads_combined_token() -> None:
    invs = col.find_gh_invocations('run(["gh api", "user"])\n')
    assert len(invs) == 1
    assert invs[0].subcommand == "api"


def test_allowed_subcommand_not_flagged(tmp_path: Path, manifest: dict[str, object]) -> None:
    """saga using `gh pr` (its own lane) and read-only `gh api repos/` is clean."""
    _write_plugin_script(
        tmp_path,
        "saga",
        "scripts/ship.py",
        "import subprocess\n"
        'subprocess.run(["gh", "pr", "merge", "1", "--squash"])\n'
        'subprocess.run(["gh", "api", "repos/o/r/deployments"])\n',
    )
    assert col.run_check(manifest, tmp_path) == []


# --------------------------------------------------------------- manifest guard


def test_missing_manifest_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(col.ManifestError, match="not found"):
        col.load_manifest(tmp_path / "nope.json")


def test_malformed_manifest_fails_loud(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json")
    with pytest.raises(col.ManifestError, match="not valid JSON"):
        col.load_manifest(bad)


def test_manifest_missing_key_fails_loud(tmp_path: Path) -> None:
    bad = tmp_path / "partial.json"
    bad.write_text('{"sensitive_subcommands": [], "reserved_api_paths": {}}')
    with pytest.raises(col.ManifestError, match="lanes"):
        col.load_manifest(bad)


def test_main_returns_2_on_bad_manifest(tmp_path: Path) -> None:
    rc = col.main(["--manifest", str(tmp_path / "missing.json")])
    assert rc == 2


# --------------------------------------------------------------------------- AC4


def test_lint_wired_into_ci() -> None:
    """AC4: the marketplace validate job still invokes the lint (drift guard)."""
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "check_ownership_lanes.py" in ci
