"""Unit tests for sdlc_manager.py."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add plugin scripts directory to path
sys.path.insert(
    0,
    str(Path(__file__).parent.parent / "plugins" / "mission-control" / "scripts"),
)

import sdlc_manager

# ===========================
# Helpers
# ===========================


def make_subprocess_result(stdout="", stderr="", returncode=0):
    """Create a mock subprocess.CompletedProcess."""
    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


# ===========================
# _gh wrapper tests
# ===========================


class TestGhWrapper:
    """Tests for the _gh CLI wrapper."""

    def test_gh_success(self, monkeypatch):
        """gh returns stdout on success."""
        mock_run = MagicMock(return_value=make_subprocess_result(stdout="hello"))
        monkeypatch.setattr("subprocess.run", mock_run)

        result = sdlc_manager._gh(["api", "repos"])
        assert result == "hello"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["gh", "api", "repos"]

    def test_gh_no_ghe_host_in_env(self, monkeypatch):
        """gh calls must NOT inject GH_HOST (we target github.com)."""
        mock_run = MagicMock(return_value=make_subprocess_result(stdout="ok"))
        monkeypatch.setattr("subprocess.run", mock_run)

        sdlc_manager._gh(["api", "repos"])

        # The call should NOT pass an env with GH_HOST overridden
        call_kwargs = mock_run.call_args[1]
        # _gh() does not set env at all — it uses default
        assert "env" not in call_kwargs or call_kwargs.get("env") is None

    def test_gh_failure_raises(self, monkeypatch):
        """gh returns RuntimeError on non-zero exit."""
        mock_run = MagicMock(return_value=make_subprocess_result(stderr="not found", returncode=1))
        monkeypatch.setattr("subprocess.run", mock_run)

        with pytest.raises(RuntimeError, match="gh command failed"):
            sdlc_manager._gh(["api", "repos"])


# ===========================
# Metrics: cycle time percentile calculation
# ===========================


class TestMetricsCycleTime:
    """Tests for metrics_cycle_time percentile math."""

    @patch.object(sdlc_manager, "_get_issue_column_times")
    @patch.object(sdlc_manager, "get_project_items")
    @patch.object(sdlc_manager, "load_config")
    def test_percentiles_known_dataset(self, mock_config, mock_items, mock_times, capsys):
        """P50/P85/P95 are correct for a known 10-item dataset."""
        mock_config.return_value = {
            "project_mappings": {
                "projects": {"mount-olympus": {"number": 1, "name": "MO Ops", "id": "P1"}}
            }
        }

        # Build 10 deployed items with known cycle times
        cycle_days = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        items = []
        for i, _days in enumerate(cycle_days):
            items.append(
                {
                    "id": f"item-{i}",
                    "createdAt": "2026-01-01T00:00:00Z",
                    "updatedAt": "2026-01-15T00:00:00Z",
                    "content": {
                        "number": i + 1,
                        "title": f"Item {i + 1}",
                        "url": "",
                        "state": "CLOSED",
                        "labels": {"nodes": [{"name": "capability"}]},
                        "repository": {"name": "test-repo"},
                    },
                    "fieldValues": {
                        "nodes": [{"name": "Deployed", "field": {"name": "Status", "id": "F1"}}]
                    },
                }
            )

        mock_items.return_value = ("P1", items)

        # Return transitions that produce the exact cycle_days above
        def fake_times(org, repo, number):
            days = cycle_days[number - 1]
            return [
                {"at": "2026-01-01T00:00:00Z", "from": "", "to": "In Development"},
                {
                    "at": f"2026-01-{int(1 + days):02d}T00:00:00Z",
                    "from": "In Development",
                    "to": "Deployed",
                },
            ]

        mock_times.side_effect = fake_times

        sdlc_manager.metrics_cycle_time("mount-olympus", 30, None, "text")

        output = capsys.readouterr().out
        # With 10 items [1..10], index int(10*0.5)=5 -> value 6.0
        assert "P50: 6.0 days" in output
        assert "P85: 9.0 days" in output
        assert "P95: 10.0 days" in output

    @patch.object(sdlc_manager, "get_project_items")
    @patch.object(sdlc_manager, "load_config")
    def test_empty_dataset_no_crash(self, mock_config, mock_items, capsys):
        """No deployed items should print a message, not crash."""
        mock_config.return_value = {
            "project_mappings": {
                "projects": {"mount-olympus": {"number": 1, "name": "MO Ops", "id": "P1"}}
            }
        }
        mock_items.return_value = ("P1", [])

        sdlc_manager.metrics_cycle_time("mount-olympus", 30, None, "text")

        output = capsys.readouterr().out
        assert "No completed items" in output

    @patch.object(sdlc_manager, "_get_issue_column_times")
    @patch.object(sdlc_manager, "get_project_items")
    @patch.object(sdlc_manager, "load_config")
    def test_small_dataset_under_7_items(self, mock_config, mock_items, mock_times, capsys):
        """Percentile calculation handles fewer than 7 items without crashing."""
        mock_config.return_value = {
            "project_mappings": {
                "projects": {"mount-olympus": {"number": 1, "name": "MO Ops", "id": "P1"}}
            }
        }

        # Only 3 items
        items = []
        for i in range(3):
            items.append(
                {
                    "id": f"item-{i}",
                    "createdAt": "2026-01-01T00:00:00Z",
                    "updatedAt": "2026-01-15T00:00:00Z",
                    "content": {
                        "number": i + 1,
                        "title": f"Item {i + 1}",
                        "url": "",
                        "state": "CLOSED",
                        "labels": {"nodes": [{"name": "capability"}]},
                        "repository": {"name": "test-repo"},
                    },
                    "fieldValues": {
                        "nodes": [{"name": "Deployed", "field": {"name": "Status", "id": "F1"}}]
                    },
                }
            )

        mock_items.return_value = ("P1", items)

        def fake_times(org, repo, number):
            return [
                {"at": "2026-01-01T00:00:00Z", "from": "", "to": "In Development"},
                {
                    "at": f"2026-01-{number + 1:02d}T00:00:00Z",
                    "from": "In Development",
                    "to": "Deployed",
                },
            ]

        mock_times.side_effect = fake_times

        # Should not raise
        sdlc_manager.metrics_cycle_time("mount-olympus", 30, None, "text")

        output = capsys.readouterr().out
        assert "Sample size: 3" in output
        assert "P50" in output


# ===========================
# Board: archive dry-run
# ===========================


class TestBoardArchive:
    """Tests for board_archive dry-run behavior."""

    @patch.object(sdlc_manager, "_graphql")
    @patch.object(sdlc_manager, "get_project_items")
    @patch.object(sdlc_manager, "load_config")
    def test_dry_run_prevents_archiving(self, mock_config, mock_items, mock_graphql, capsys):
        """Dry-run lists items but does not call the archive mutation."""
        mock_config.return_value = {
            "project_mappings": {
                "projects": {"mount-olympus": {"number": 1, "name": "MO Ops", "id": "P1"}}
            }
        }

        items = [
            {
                "id": "item-1",
                "createdAt": "2026-01-01T00:00:00Z",
                "content": {
                    "number": 10,
                    "title": "Deploy auth service",
                    "repository": {"name": "athena-service"},
                },
                "fieldValues": {
                    "nodes": [{"name": "Deployed", "field": {"name": "Status", "id": "F1"}}]
                },
            },
            {
                "id": "item-2",
                "createdAt": "2026-01-02T00:00:00Z",
                "content": {
                    "number": 11,
                    "title": "In progress item",
                    "repository": {"name": "athena-service"},
                },
                "fieldValues": {
                    "nodes": [{"name": "In Development", "field": {"name": "Status", "id": "F1"}}]
                },
            },
        ]

        mock_items.return_value = ("P1", items)

        sdlc_manager.board_archive("mount-olympus", dry_run=True, fmt="text")

        output = capsys.readouterr().out
        assert "DRY RUN" in output
        assert "athena-service#10" in output
        # Only the deployed item should appear, not the in-progress one
        assert "athena-service#11" not in output
        # The archive mutation should never be called in dry-run
        mock_graphql.assert_not_called()

    @patch.object(sdlc_manager, "_graphql")
    @patch.object(sdlc_manager, "get_project_items")
    @patch.object(sdlc_manager, "load_config")
    def test_real_archive_calls_mutation(self, mock_config, mock_items, mock_graphql, capsys):
        """Non-dry-run actually calls the archive mutation."""
        mock_config.return_value = {
            "project_mappings": {
                "projects": {"mount-olympus": {"number": 1, "name": "MO Ops", "id": "P1"}}
            }
        }

        items = [
            {
                "id": "item-1",
                "createdAt": "2026-01-01T00:00:00Z",
                "content": {
                    "number": 10,
                    "title": "Deploy auth service",
                    "repository": {"name": "athena-service"},
                },
                "fieldValues": {
                    "nodes": [{"name": "Deployed", "field": {"name": "Status", "id": "F1"}}]
                },
            },
        ]

        mock_items.return_value = ("P1", items)
        mock_graphql.return_value = {"archiveProjectV2Item": {"item": {"id": "item-1"}}}

        sdlc_manager.board_archive("mount-olympus", dry_run=False, fmt="text")

        # The archive mutation should be called
        mock_graphql.assert_called_once()
        call_args = mock_graphql.call_args
        assert "archiveProjectV2Item" in call_args[0][0]


# NOTE: The Beads/Dolt subcommand group was removed in PR #114 (Phase C).
# Tests for beads_claim / beads_complete / beads_ready are deleted here;
# the underlying coordination layer was decommissioned 2026-04-26.


# ===========================
# WIP limits: configurable
# ===========================


class TestWipLimitsConfigurable:
    """Tests for configurable WIP limits from legacy_rollout_config.

    The config key was renamed from `beads_config` → `legacy_rollout_config`
    in PR #114 (Beads removal); the underlying file (beads-config.json)
    was already removed from infiquetra-sdlc on 2026-04-26 so the key
    degrades gracefully to {} in production. These tests mock the loader
    to inject overrides, exercising the override path."""

    @patch.object(sdlc_manager, "get_project_items")
    @patch.object(sdlc_manager, "load_config")
    def test_uses_config_wip_limits(self, mock_config, mock_items, capsys):
        """WIP limits from legacy_rollout_config override defaults."""
        mock_config.return_value = {
            "project_mappings": {
                "projects": {"mount-olympus": {"number": 1, "name": "MO Ops", "id": "P1"}}
            },
            "legacy_rollout_config": {
                "wip_limits": {
                    "ready": 5,
                    "in_development": 8,
                    "e2e_testing": 2,
                    "deployment_ready": 3,
                }
            },
        }
        mock_items.return_value = ("P1", [])

        sdlc_manager.board_wip("mount-olympus", "text")

        output = capsys.readouterr().out
        # Tighten the assertion to verify the OVERRIDDEN column (Ready)
        # specifically renders with the override limit (5), not just any
        # rendering that happens to contain "5".
        assert "Ready" in output
        # The rendered limit could be "0/5" or "0/ 5" depending on column
        # widths; either form indicates the override was applied (default
        # would be 10, not 5).
        assert " 0/ 5" in output or "0/5" in output

    @patch.object(sdlc_manager, "get_project_items")
    @patch.object(sdlc_manager, "load_config")
    def test_falls_back_to_defaults(self, mock_config, mock_items, capsys):
        """Missing wip_limits in legacy_rollout_config falls back to defaults."""
        mock_config.return_value = {
            "project_mappings": {
                "projects": {"mount-olympus": {"number": 1, "name": "MO Ops", "id": "P1"}}
            },
            "legacy_rollout_config": {},
        }
        mock_items.return_value = ("P1", [])

        sdlc_manager.board_wip("mount-olympus", "text")

        output = capsys.readouterr().out
        # Default In Development limit is 10
        assert "10" in output


# ===========================
# #279 no-live-gh guard self-test (Claude-owned; proves the autouse tripwire fires)
# ===========================


def test_no_live_gh_guard_blocks_unmocked_gh_calls():
    """The autouse `_no_live_gh` guard (conftest.py) must RAISE on an unmocked `gh` call.

    Deny-by-default: this module exercises GitHub-mutating verbs, so any subprocess `gh`
    invocation that a test forgot to mock must fail loudly rather than touch the live board.
    """
    import subprocess

    with pytest.raises(RuntimeError, match="no-live-gh guard"):
        subprocess.run(["gh", "issue", "view", "1"])


# ===========================
# #279 U3 issue-write verbs (close / reopen / comment / label add/remove) — agy appends BELOW
# ===========================


class TestIssueClose:
    """Tests for issue_close — idempotent PATCH state=closed."""

    def test_close_issues_correct_patch(self, monkeypatch):
        """issue_close sends PATCH to the issues endpoint with state=closed."""
        import json

        captured = {}

        def mock_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["input"] = kwargs.get("input", "")
            return make_subprocess_result(stdout=json.dumps({"number": 42, "state": "closed"}))

        monkeypatch.setattr("subprocess.run", mock_run)
        sdlc_manager.issue_close("infiquetra-claude-plugins", 42)

        cmd = captured["cmd"]
        assert "api" in cmd
        assert "--method" in cmd
        assert "PATCH" in cmd
        assert any("issues/42" in part for part in cmd)
        body = json.loads(captured["input"])
        assert body["state"] == "closed"

    def test_close_already_closed_is_success(self, monkeypatch):
        """Re-closing an already-closed issue succeeds (PATCH is naturally idempotent)."""
        import json

        captured = {}

        def mock_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["input"] = kwargs.get("input", "")
            # GitHub returns the issue in its current state regardless
            return make_subprocess_result(stdout=json.dumps({"number": 42, "state": "closed"}))

        monkeypatch.setattr("subprocess.run", mock_run)
        sdlc_manager.issue_close("infiquetra-claude-plugins", 42)  # must not raise

        # Idempotency is structural: the verb unconditionally PATCHes state=closed (no read-modify-write),
        # so a re-close is the same safe call. Assert that's what it actually issued.
        assert "PATCH" in captured["cmd"]
        assert json.loads(captured["input"])["state"] == "closed"


class TestIssueReopen:
    """Tests for issue_reopen — inverse of issue_close."""

    def test_reopen_sends_state_open(self, monkeypatch):
        """issue_reopen sends PATCH with state=open."""
        import json

        captured = {}

        def mock_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["input"] = kwargs.get("input", "")
            return make_subprocess_result(stdout=json.dumps({"number": 5, "state": "open"}))

        monkeypatch.setattr("subprocess.run", mock_run)
        sdlc_manager.issue_reopen("infiquetra-claude-plugins", 5)

        body = json.loads(captured["input"])
        assert body["state"] == "open"

    def test_close_then_reopen_round_trip(self, monkeypatch):
        """close -> reopen round-trip: each call uses the correct state value."""
        import json

        states_sent = []

        def mock_run(cmd, **kwargs):
            body = json.loads(kwargs.get("input", "{}"))
            if "state" in body:
                states_sent.append(body["state"])
            return make_subprocess_result(
                stdout=json.dumps({"number": 10, "state": body.get("state", "open")})
            )

        monkeypatch.setattr("subprocess.run", mock_run)
        sdlc_manager.issue_close("infiquetra-claude-plugins", 10)
        sdlc_manager.issue_reopen("infiquetra-claude-plugins", 10)

        assert states_sent == ["closed", "open"]


class TestIssueComment:
    """Tests for issue_comment — POST to the comments endpoint."""

    def test_comment_posts_to_comments_endpoint(self, monkeypatch):
        """issue_comment POSTs to /issues/{number}/comments with the body."""
        import json

        captured = {}

        def mock_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["input"] = kwargs.get("input", "")
            return make_subprocess_result(stdout=json.dumps({"id": 99, "body": "hello"}))

        monkeypatch.setattr("subprocess.run", mock_run)
        sdlc_manager.issue_comment("infiquetra-claude-plugins", 7, "hello")

        cmd = captured["cmd"]
        assert "POST" in cmd
        assert any("comments" in part for part in cmd)
        body = json.loads(captured["input"])
        assert body["body"] == "hello"


class TestIssueLabelAddRemove:
    """Tests for issue_label_add / issue_label_remove — round-trip and idempotency."""

    def test_label_add_posts_to_labels_endpoint(self, monkeypatch):
        """issue_label_add POSTs the label name to the labels endpoint."""
        import json

        captured = {}

        def mock_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["input"] = kwargs.get("input", "")
            return make_subprocess_result(stdout=json.dumps([{"name": "blocked"}]))

        monkeypatch.setattr("subprocess.run", mock_run)
        sdlc_manager.issue_label_add("infiquetra-claude-plugins", 3, "blocked")

        cmd = captured["cmd"]
        assert "POST" in cmd
        assert any("labels" in part for part in cmd)
        body = json.loads(captured["input"])
        assert "blocked" in body["labels"]

    def test_label_remove_sends_delete(self, monkeypatch):
        """issue_label_remove sends DELETE to the labels/{label} endpoint."""
        captured = {}

        def mock_run(cmd, **kwargs):
            captured["cmd"] = cmd
            # GitHub returns 204 with empty body for DELETE
            return make_subprocess_result(stdout="")

        monkeypatch.setattr("subprocess.run", mock_run)
        sdlc_manager.issue_label_remove("infiquetra-claude-plugins", 3, "blocked")

        cmd = captured["cmd"]
        assert "DELETE" in cmd
        assert any("blocked" in part for part in cmd)

    def test_label_add_then_remove_round_trip(self, monkeypatch):
        """Adding then removing a label calls the correct endpoints in order."""
        import json

        methods_called = []

        def mock_run(cmd, **kwargs):
            if "--method" in cmd:
                idx = cmd.index("--method")
                methods_called.append(cmd[idx + 1])
            # Return appropriate response per method
            if "DELETE" in cmd:
                return make_subprocess_result(stdout="")
            return make_subprocess_result(stdout=json.dumps([{"name": "blocked"}]))

        monkeypatch.setattr("subprocess.run", mock_run)
        sdlc_manager.issue_label_add("infiquetra-claude-plugins", 3, "blocked")
        sdlc_manager.issue_label_remove("infiquetra-claude-plugins", 3, "blocked")

        assert methods_called == ["POST", "DELETE"]

    def test_re_adding_existing_label_is_success(self, monkeypatch):
        """Re-adding an already-present label returns success (GitHub returns 200, no error)."""
        import json

        def mock_run(cmd, **kwargs):
            # GitHub returns 200 with the label list even if already present
            return make_subprocess_result(stdout=json.dumps([{"name": "blocked"}]))

        monkeypatch.setattr("subprocess.run", mock_run)
        # Should not raise
        sdlc_manager.issue_label_add("infiquetra-claude-plugins", 3, "blocked")

    def test_removing_absent_label_is_success(self, monkeypatch):
        """Removing an absent label (404) is treated as success — idempotent."""
        import json

        def mock_run(cmd, **kwargs):
            # Simulate GitHub returning 404 for DELETE of absent label
            return make_subprocess_result(
                stdout=json.dumps({"message": "Label does not exist"}),
                stderr="gh: Label does not exist (HTTP 404)",
                returncode=1,
            )

        monkeypatch.setattr("subprocess.run", mock_run)
        # Should not raise — ApiNotFoundError is swallowed
        sdlc_manager.issue_label_remove("infiquetra-claude-plugins", 3, "nonexistent")

    def test_transient_error_propagates(self, monkeypatch):
        """A non-404/non-422 gh error (e.g. network/500) surfaces as an exception."""

        def mock_run(cmd, **kwargs):
            return make_subprocess_result(
                stdout="",
                stderr="gh: internal server error (HTTP 500)",
                returncode=1,
            )

        monkeypatch.setattr("subprocess.run", mock_run)
        with pytest.raises((sdlc_manager.GhApiError, RuntimeError)):
            sdlc_manager.issue_label_remove("infiquetra-claude-plugins", 3, "blocked")
