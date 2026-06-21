"""Tests for U16: SHA-stamp stager + stale-main-after-squash guard (R18).

Two tools close the remaining this-repo-local release rituals:

1. ``tools/sha_stamp_stager.py`` — reads the real squash SHA from
   ``gh pr view --json mergeCommit``, finds placeholder lines in the journal,
   and **stages** the substitution.  Never blind-applies; operator reviews the
   staged diff before committing.

2. ``tools/stale_main_guard.py`` — detects when local ``main`` is behind
   ``origin/main`` (after a squash-merge) and emits a loud warning.
   Auto-fast-forwards when main is clean.  Non-blocking (exit 0 always).
   Must not false-fire when main is current, and must handle worktree sessions
   without auto-forwarding the wrong branch.

Both tools are THIS-REPO-LOCAL: they do not assume cross-repo idioms and must
never false-fire on a legitimately current main.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers: dynamic module import (tools/ is not a package)
# ---------------------------------------------------------------------------

_TOOLS_ROOT = Path(__file__).parent.parent / "tools"


def _load_module(name: str):  # type: ignore[return]
    """Load a module from tools/ by filename."""
    path = _TOOLS_ROOT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"Cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# SHA-stamp stager tests
# ---------------------------------------------------------------------------


class TestShaStampStager:
    """Tests for tools/sha_stamp_stager.py."""

    @pytest.fixture()
    def stager(self):
        return _load_module("sha_stamp_stager")

    # -- _find_placeholder_files ---------------------------------------------

    def test_find_placeholder_finds_marked_file(self, stager: Any, tmp_path: Path) -> None:
        """Files containing the placeholder are returned."""
        marked = tmp_path / "LEARNINGS.md"
        marked.write_text("## 2026-06-21\n\nPR squash: PENDING_SHA\n")
        unmarked = tmp_path / "DECISIONS.md"
        unmarked.write_text("## A decision\n\nNo placeholder here.\n")

        result = stager._find_placeholder_files(tmp_path, "PENDING_SHA")
        assert marked in result
        assert unmarked not in result

    def test_find_placeholder_returns_empty_when_none(self, stager: Any, tmp_path: Path) -> None:
        """An empty list is returned when no file contains the placeholder."""
        (tmp_path / "clean.md").write_text("No markers here.\n")
        result = stager._find_placeholder_files(tmp_path, "PENDING_SHA")
        assert result == []

    def test_find_placeholder_finds_multiple_files(self, stager: Any, tmp_path: Path) -> None:
        """All files containing the placeholder are returned."""
        for name in ("A.md", "B.md", "C.md"):
            (tmp_path / name).write_text(f"entry for {name}: PENDING_SHA\n")
        result = stager._find_placeholder_files(tmp_path, "PENDING_SHA")
        assert len(result) == 3

    def test_find_placeholder_skips_binary(self, stager: Any, tmp_path: Path) -> None:
        """Binary files are silently skipped even if they contain the byte sequence."""
        binary = tmp_path / "data.bin"
        binary.write_bytes(b"\x00\x01PENDING_SHA\x02\xff")
        result = stager._find_placeholder_files(tmp_path, "PENDING_SHA")
        # Must not raise; the binary file may or may not appear depending on
        # whether the byte sequence decodes — the important thing is no crash.
        assert isinstance(result, list)

    def test_find_placeholder_custom_placeholder(self, stager: Any, tmp_path: Path) -> None:
        """A non-default placeholder string is respected."""
        f = tmp_path / "notes.md"
        f.write_text("SHA: SHA-TODO\n")
        result = stager._find_placeholder_files(tmp_path, "SHA-TODO")
        assert f in result
        # Default placeholder should NOT match
        result_default = stager._find_placeholder_files(tmp_path, "PENDING_SHA")
        assert f not in result_default

    # -- _build_diff ---------------------------------------------------------

    def test_build_diff_contains_sha(self, stager: Any, tmp_path: Path) -> None:
        """The diff output contains the real SHA in the '+' lines."""
        f = tmp_path / "entry.md"
        f.write_text("squash: PENDING_SHA\n")
        diff = stager._build_diff(f, "PENDING_SHA", "abc1234def5678")
        assert "abc1234def5678" in diff
        assert "PENDING_SHA" in diff  # in the removed '-' lines

    def test_build_diff_shows_removal_and_addition(self, stager: Any, tmp_path: Path) -> None:
        """Unified diff has both '-' (removal) and '+' (addition) lines."""
        f = tmp_path / "entry.md"
        f.write_text("sha: PENDING_SHA\n")
        diff = stager._build_diff(f, "PENDING_SHA", "deadbeef")
        assert "-sha: PENDING_SHA" in diff
        assert "+sha: deadbeef" in diff

    def test_build_diff_no_change_when_placeholder_absent(
        self, stager: Any, tmp_path: Path
    ) -> None:
        """When the placeholder is absent, the diff is empty."""
        f = tmp_path / "clean.md"
        f.write_text("No placeholder.\n")
        diff = stager._build_diff(f, "PENDING_SHA", "abc1234")
        # No +/- lines → empty diff (unified_diff returns nothing for equal content)
        assert diff == ""

    # -- _apply_substitution -------------------------------------------------

    def test_apply_substitution_replaces_all_occurrences(self, stager: Any, tmp_path: Path) -> None:
        """Every occurrence of the placeholder is replaced."""
        f = tmp_path / "multi.md"
        f.write_text("sha1: PENDING_SHA\nsha2: PENDING_SHA\n")
        stager._apply_substitution(f, "PENDING_SHA", "cafebabe")
        result = f.read_text()
        assert "PENDING_SHA" not in result
        assert result.count("cafebabe") == 2

    def test_apply_substitution_preserves_surrounding_text(
        self, stager: Any, tmp_path: Path
    ) -> None:
        """Text around the placeholder is preserved exactly."""
        f = tmp_path / "entry.md"
        original = "PR #123 squash: PENDING_SHA — merged 2026-06-21\n"
        f.write_text(original)
        stager._apply_substitution(f, "PENDING_SHA", "aabbccdd")
        result = f.read_text()
        assert result == "PR #123 squash: aabbccdd — merged 2026-06-21\n"

    # -- _squash_sha_from_pr (mocked) ----------------------------------------

    def test_squash_sha_returns_oid_for_merged_pr(self, stager: Any) -> None:
        """_squash_sha_from_pr returns the mergeCommit.oid for a MERGED PR."""
        payload = json.dumps(
            {"state": "MERGED", "mergeCommit": {"oid": "abc123def456abc123def456abc123def456abc1"}}
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=payload, stderr="")
            sha = stager._squash_sha_from_pr(42)
        assert sha == "abc123def456abc123def456abc123def456abc1"

    def test_squash_sha_exits_on_open_pr(self, stager: Any) -> None:
        """_squash_sha_from_pr exits 1 if the PR is not yet merged."""
        payload = json.dumps({"state": "OPEN", "mergeCommit": None})
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=payload, stderr="")
            with pytest.raises(SystemExit) as exc_info:
                stager._squash_sha_from_pr(99)
        assert exc_info.value.code == 1

    def test_squash_sha_exits_on_gh_failure(self, stager: Any) -> None:
        """_squash_sha_from_pr exits 1 if gh returns non-zero."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
            with pytest.raises(SystemExit) as exc_info:
                stager._squash_sha_from_pr(1)
        assert exc_info.value.code == 1

    # -- main (dry-run) -------------------------------------------------------

    def test_main_dry_run_does_not_stage(self, stager: Any, tmp_path: Path) -> None:
        """--dry-run shows the diff but does not call git add."""
        # Set up a fake journal dir with a placeholder.
        journal_dir = tmp_path / "docs" / "engineering-journal"
        journal_dir.mkdir(parents=True)
        entry = journal_dir / "LEARNINGS.md"
        entry.write_text("squash SHA: PENDING_SHA\n")

        # Mock: gh returns a merged PR; git rev-parse returns tmp_path; git add
        # should NOT be called.
        def _fake_run(args, **kwargs):
            if "rev-parse" in args:
                return MagicMock(returncode=0, stdout=str(tmp_path), stderr="")
            if "gh" in args and "pr" in args:
                payload = json.dumps(
                    {
                        "state": "MERGED",
                        "mergeCommit": {"oid": "deadbeef12345678deadbeef12345678deadbeef"},
                    }
                )
                return MagicMock(returncode=0, stdout=payload, stderr="")
            if "git" in args and "add" in args:
                raise AssertionError("git add must NOT be called in --dry-run mode")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=_fake_run):
            rc = stager.main(
                ["--pr", "10", "--search-root", "docs/engineering-journal", "--dry-run"]
            )
        assert rc == 0

    def test_main_no_placeholder_exits_zero(self, stager: Any, tmp_path: Path) -> None:
        """main exits 0 with a 'nothing to stage' message when no placeholder found."""
        journal_dir = tmp_path / "docs" / "engineering-journal"
        journal_dir.mkdir(parents=True)
        (journal_dir / "clean.md").write_text("no placeholders here\n")

        def _fake_run(args, **kwargs):
            if "rev-parse" in args:
                return MagicMock(returncode=0, stdout=str(tmp_path), stderr="")
            if "gh" in args:
                payload = json.dumps(
                    {
                        "state": "MERGED",
                        "mergeCommit": {"oid": "cafe1234cafe1234cafe1234cafe1234cafe1234"},
                    }
                )
                return MagicMock(returncode=0, stdout=payload, stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=_fake_run):
            rc = stager.main(["--pr", "5", "--search-root", "docs/engineering-journal"])
        assert rc == 0


# ---------------------------------------------------------------------------
# Stale-main guard tests
# ---------------------------------------------------------------------------


class TestStaleMainGuard:
    """Tests for tools/stale_main_guard.py."""

    @pytest.fixture()
    def guard(self):
        return _load_module("stale_main_guard")

    # -- _commits_behind -----------------------------------------------------

    def test_commits_behind_returns_int(self, guard: Any) -> None:
        """_commits_behind parses the integer stdout from git rev-list."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="3", stderr="")
            count = guard._commits_behind()
        assert count == 3

    def test_commits_behind_returns_zero_when_current(self, guard: Any) -> None:
        """_commits_behind returns 0 when main is up to date."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="0", stderr="")
            count = guard._commits_behind()
        assert count == 0

    def test_commits_behind_returns_none_on_error(self, guard: Any) -> None:
        """_commits_behind returns None when the git command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=128, stdout="", stderr="fatal: unknown revision"
            )
            count = guard._commits_behind()
        assert count is None

    # -- _is_worktree --------------------------------------------------------

    def test_is_worktree_false_when_dirs_equal(self, guard: Any) -> None:
        """_is_worktree returns False when --git-dir == --git-common-dir."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="/repo/.git", stderr=""),
                MagicMock(returncode=0, stdout="/repo/.git", stderr=""),
            ]
            assert guard._is_worktree() is False

    def test_is_worktree_true_when_dirs_differ(self, guard: Any) -> None:
        """_is_worktree returns True when --git-dir and --git-common-dir differ."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="/repo/.git/worktrees/epic4", stderr=""),
                MagicMock(returncode=0, stdout="/repo/.git", stderr=""),
            ]
            assert guard._is_worktree() is True

    # -- run_guard (the main logic, _fetch=False for unit tests) -------------

    def test_guard_silent_when_current(self, guard: Any, capsys) -> None:
        """No output when main is up to date (count == 0).

        This is the most important false-fire guard: a legitimately current
        main must produce ZERO output.
        """
        with (
            patch.object(guard, "_commits_behind", return_value=0),
        ):
            rc = guard.run_guard(_fetch=False)
        assert rc == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out == ""

    def test_guard_silent_when_behind_returns_none(self, guard: Any, capsys) -> None:
        """No output when _commits_behind returns None (no remote branch, etc.)."""
        with patch.object(guard, "_commits_behind", return_value=None):
            rc = guard.run_guard(_fetch=False)
        assert rc == 0
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_guard_warns_in_worktree(self, guard: Any, capsys) -> None:
        """In a worktree session, emits a warning but does NOT auto-fast-forward."""
        with (
            patch.object(guard, "_commits_behind", return_value=2),
            patch.object(guard, "_is_worktree", return_value=True),
            patch.object(guard, "_current_branch", return_value="feat/some-branch"),
            patch.object(guard, "_fast_forward_main") as mock_ff,
        ):
            rc = guard.run_guard(_fetch=False)

        assert rc == 0
        mock_ff.assert_not_called()
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "worktree" in captured.err
        assert "2" in captured.err

    def test_guard_warns_when_not_on_main(self, guard: Any, capsys) -> None:
        """Not on main branch: warn but do not attempt fast-forward."""
        with (
            patch.object(guard, "_commits_behind", return_value=1),
            patch.object(guard, "_is_worktree", return_value=False),
            patch.object(guard, "_current_branch", return_value="feat/other"),
            patch.object(guard, "_fast_forward_main") as mock_ff,
        ):
            rc = guard.run_guard(_fetch=False)

        assert rc == 0
        mock_ff.assert_not_called()
        captured = capsys.readouterr()
        assert "WARNING" in captured.err

    def test_guard_auto_ff_when_on_main_and_clean(self, guard: Any, capsys) -> None:
        """On main with a clean tree: auto-fast-forward and confirm."""
        with (
            patch.object(guard, "_commits_behind", return_value=3),
            patch.object(guard, "_is_worktree", return_value=False),
            patch.object(guard, "_current_branch", return_value="main"),
            patch.object(guard, "_working_tree_is_clean", return_value=True),
            patch.object(guard, "_fast_forward_main", return_value=True),
        ):
            rc = guard.run_guard(_fetch=False)

        assert rc == 0
        captured = capsys.readouterr()
        # Should confirm the fast-forward, not just warn
        assert "Auto-fast-forwarded" in captured.err
        assert "3" in captured.err

    def test_guard_warns_when_on_main_but_dirty(self, guard: Any, capsys) -> None:
        """On main with uncommitted changes: warn but skip auto-fast-forward."""
        with (
            patch.object(guard, "_commits_behind", return_value=1),
            patch.object(guard, "_is_worktree", return_value=False),
            patch.object(guard, "_current_branch", return_value="main"),
            patch.object(guard, "_working_tree_is_clean", return_value=False),
            patch.object(guard, "_fast_forward_main") as mock_ff,
        ):
            rc = guard.run_guard(_fetch=False)

        assert rc == 0
        mock_ff.assert_not_called()
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "uncommitted" in captured.err

    def test_guard_warns_on_ff_failure(self, guard: Any, capsys) -> None:
        """When auto-fast-forward fails, still emits a warning (non-blocking)."""
        with (
            patch.object(guard, "_commits_behind", return_value=1),
            patch.object(guard, "_is_worktree", return_value=False),
            patch.object(guard, "_current_branch", return_value="main"),
            patch.object(guard, "_working_tree_is_clean", return_value=True),
            patch.object(guard, "_fast_forward_main", return_value=False),
        ):
            rc = guard.run_guard(_fetch=False)

        assert rc == 0
        captured = capsys.readouterr()
        assert "WARNING" in captured.err

    def test_guard_always_exits_zero(self, guard: Any) -> None:
        """run_guard returns 0 in all branches — it is strictly non-blocking."""
        scenarios = [
            # (behind, is_worktree, branch, clean, ff_result)
            (0, False, "main", True, True),
            (1, True, "feat/x", True, True),
            (2, False, "feat/y", True, True),
            (3, False, "main", True, True),
            (3, False, "main", False, False),
            (3, False, "main", True, False),
            (None, False, "main", True, True),
        ]
        for behind, in_wt, branch, clean, ff_ok in scenarios:
            with (
                patch.object(guard, "_commits_behind", return_value=behind),
                patch.object(guard, "_is_worktree", return_value=in_wt),
                patch.object(guard, "_current_branch", return_value=branch),
                patch.object(guard, "_working_tree_is_clean", return_value=clean),
                patch.object(guard, "_fast_forward_main", return_value=ff_ok),
            ):
                rc = guard.run_guard(_fetch=False)
            assert rc == 0, f"Expected 0 for scenario {(behind, in_wt, branch, clean, ff_ok)}"

    # -- False-fire guard (the spec's key correctness property) ---------------

    def test_no_false_fire_on_current_main(self, guard: Any, capsys) -> None:
        """The stale-main guard MUST NOT emit any output when main is current.

        This is the primary false-fire prevention test specified in U16.
        A guard that warns on a current main would train the operator to ignore
        it — defeating its purpose.
        """
        with patch.object(guard, "_commits_behind", return_value=0):
            guard.run_guard(_fetch=False)
        captured = capsys.readouterr()
        assert captured.out == "", "No stdout output on current main"
        assert captured.err == "", "No stderr output on current main"
