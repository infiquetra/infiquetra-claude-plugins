"""Tests for confirmed prepared issue creation and mutation planning."""

# ruff: noqa: E402,I001

import json
import sys
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sdlc_manager  # noqa: E402


OLYMPUS_BODY = """### Objective
Add a prepared issue workflow.

### Acceptance criteria
- [ ] Drafts are written before GitHub mutation

### Out-of-scope / non-goals
- Do not auto-move issues to Ready

### Files expected to change
plugins/mission-control/scripts/sdlc_manager.py

### Tests to add or update
plugins/mission-control/tests/test_issue_create_prepared.py

### Verification
```bash
uv run pytest plugins/mission-control/tests/test_issue_create_prepared.py
```
"""


def _ready_draft(tmp_path: Path) -> Path:
    return cast(
        Path,
        sdlc_manager.issue_prepare(
            repo="hermes-claude-code-router",
            issue_type="capability",
            team="olympus",
            project="mount-olympus",
            source=OLYMPUS_BODY,
            title="Prepared issue workflow",
            status=None,
            risk="medium",
            mode=None,
            draft_dir=tmp_path,
        ),
    )


def _blocked_draft(tmp_path: Path) -> Path:
    return cast(
        Path,
        sdlc_manager.issue_prepare(
            repo="hermes-claude-code-router",
            issue_type="capability",
            team="olympus",
            project="mount-olympus",
            source="Implement it.",
            title="Blocked issue workflow",
            status=None,
            risk="medium",
            mode=None,
            draft_dir=tmp_path,
        ),
    )


def _mapped_config() -> dict:
    return {
        "project_mappings": {
            "projects": {
                "mount-olympus": {
                    "number": 1,
                    "name": "Olympus",
                    "repositories": ["hermes-claude-code-router"],
                }
            }
        }
    }


def _unmapped_config() -> dict:
    return {
        "project_mappings": {
            "projects": {
                "mount-olympus": {
                    "number": 1,
                    "name": "Olympus",
                    "repositories": [],
                }
            }
        }
    }


def test_blocked_draft_refuses_to_mutate(tmp_path) -> None:
    draft = _blocked_draft(tmp_path)

    with (
        patch.object(sdlc_manager, "load_config") as mock_config,
        patch.object(sdlc_manager, "_create_github_issue") as mock_create,
        pytest.raises(RuntimeError, match="blocking readiness"),
    ):
        sdlc_manager.issue_create_prepared(draft, fmt="text", auto_confirm=True)

    mock_config.assert_not_called()
    mock_create.assert_not_called()


def test_declined_confirmation_applies_no_mutation(tmp_path) -> None:
    draft = _ready_draft(tmp_path)

    with (
        patch.object(sdlc_manager, "load_config", return_value=_mapped_config()),
        patch.object(sdlc_manager, "_repo_missing_labels", return_value=[]),
        patch.object(sdlc_manager, "_repo_missing_templates", return_value=[]),
        patch.object(sdlc_manager, "_safe_input", return_value="n"),
        patch.object(sdlc_manager, "_create_github_issue") as mock_create,
    ):
        result = sdlc_manager.issue_create_prepared(draft, fmt="text", auto_confirm=False)

    assert result == {"created": False, "reason": "declined"}
    mock_create.assert_not_called()


def test_create_prepared_creates_issue_and_marks_draft(tmp_path) -> None:
    draft = _ready_draft(tmp_path)

    with (
        patch.object(sdlc_manager, "load_config", return_value=_mapped_config()),
        patch.object(sdlc_manager, "_repo_missing_labels", return_value=[]),
        patch.object(sdlc_manager, "_repo_missing_templates", return_value=[]),
        patch.object(
            sdlc_manager,
            "_create_github_issue",
            return_value=("https://github.com/infiquetra/hermes-claude-code-router/issues/42", 42),
        ),
        patch.object(sdlc_manager, "board_add") as mock_board,
        patch.object(sdlc_manager, "flow_set_field") as mock_status,
    ):
        result = sdlc_manager.issue_create_prepared(draft, fmt="text", auto_confirm=True)

    assert result["created"] is True
    mock_board.assert_called_once_with(
        "hermes-claude-code-router",
        42,
        fmt="text",
        config=_mapped_config(),
        project_name="mount-olympus",
    )
    mock_status.assert_called_once_with(
        "mount-olympus",
        "hermes-claude-code-router",
        42,
        "Status",
        "Backlog",
        fmt="text",
    )

    sidecar = json.loads(draft.with_suffix(".json").read_text())
    assert sidecar["state"] == "created"
    assert sidecar["created_issue_number"] == 42
    assert "## Created Issue" in draft.read_text()


def test_missing_mapping_opens_pr_and_stops_without_override(tmp_path) -> None:
    draft = _ready_draft(tmp_path)

    with (
        patch.object(sdlc_manager, "load_config", return_value=_unmapped_config()),
        patch.object(sdlc_manager, "_repo_missing_labels", return_value=[]),
        patch.object(sdlc_manager, "_repo_missing_templates", return_value=[]),
        patch.object(sdlc_manager, "_open_mapping_pr", return_value="https://github.com/pr/1"),
        patch.object(sdlc_manager, "_create_github_issue") as mock_create,
    ):
        result = sdlc_manager.issue_create_prepared(draft, fmt="text", auto_confirm=True)

    assert result == {"created": False, "mapping_pr_url": "https://github.com/pr/1"}
    mock_create.assert_not_called()
    sidecar = json.loads(draft.with_suffix(".json").read_text())
    assert sidecar["state"] == "mapping_pending"
    assert sidecar["pending_mapping"] == {
        "repo": "hermes-claude-code-router",
        "project": "mount-olympus",
    }


def test_override_mapping_creates_issue_and_records_pending_mapping(tmp_path) -> None:
    draft = _ready_draft(tmp_path)

    with (
        patch.object(sdlc_manager, "load_config", return_value=_unmapped_config()),
        patch.object(sdlc_manager, "_repo_missing_labels", return_value=[]),
        patch.object(sdlc_manager, "_repo_missing_templates", return_value=[]),
        patch.object(sdlc_manager, "_open_mapping_pr", return_value="https://github.com/pr/1"),
        patch.object(
            sdlc_manager,
            "_create_github_issue",
            return_value=("https://github.com/infiquetra/hermes-claude-code-router/issues/42", 42),
        ),
        patch.object(sdlc_manager, "board_add"),
        patch.object(sdlc_manager, "flow_set_field"),
    ):
        result = sdlc_manager.issue_create_prepared(
            draft,
            fmt="text",
            auto_confirm=True,
            override_mapping=True,
        )

    assert result["created"] is True
    assert result["mapping_pr_url"] == "https://github.com/pr/1"
    sidecar = json.loads(draft.with_suffix(".json").read_text())
    assert sidecar["state"] == "created"
    assert sidecar["pending_mapping"] is True


def test_missing_labels_and_templates_are_deployed_after_confirmation(tmp_path) -> None:
    draft = _ready_draft(tmp_path)

    with (
        patch.object(sdlc_manager, "load_config", return_value=_mapped_config()),
        patch.object(sdlc_manager, "_repo_missing_labels", return_value=["hermes-task"]),
        patch.object(sdlc_manager, "_repo_missing_templates", return_value=["capability.yml"]),
        patch.object(sdlc_manager, "labels_deploy") as mock_labels,
        patch.object(sdlc_manager, "rollout_deploy_templates") as mock_templates,
        patch.object(
            sdlc_manager,
            "_create_github_issue",
            return_value=("https://github.com/infiquetra/hermes-claude-code-router/issues/42", 42),
        ),
        patch.object(sdlc_manager, "board_add"),
        patch.object(sdlc_manager, "flow_set_field"),
    ):
        sdlc_manager.issue_create_prepared(draft, fmt="text", auto_confirm=True)

    mock_labels.assert_called_once_with("hermes-claude-code-router", fmt="text")
    mock_templates.assert_called_once_with("hermes-claude-code-router", fmt="text")


def test_mapping_pr_uses_temporary_worktree(tmp_path) -> None:
    worktree_root = tmp_path / "infiquetra-sdlc"
    mapping_path = worktree_root / "config" / "project-mappings.json"
    mapping_path.parent.mkdir(parents=True)
    mapping_path.write_text('{"projects": {"mount-olympus": {"repositories": []}}}\n')

    with (
        patch.object(
            sdlc_manager,
            "_mapping_update_target",
            return_value=(mapping_path, worktree_root, "infiquetra-sdlc", None),
        ),
        patch.object(sdlc_manager, "_run_git_command", return_value="ok") as mock_git,
        patch.object(sdlc_manager, "_write_mapping_update") as mock_write,
        patch.object(
            sdlc_manager, "_gh", return_value="https://github.com/infiquetra/infiquetra-sdlc/pull/1"
        ),
    ):
        url = sdlc_manager._open_mapping_pr("hermes-claude-code-router", "mount-olympus")

    assert url == "https://github.com/infiquetra/infiquetra-sdlc/pull/1"
    git_args = [call.args[0] for call in mock_git.call_args_list]
    assert any(args[:3] == ["git", "worktree", "add"] for args in git_args)
    assert any(args[:4] == ["git", "worktree", "remove", "--force"] for args in git_args)
    assert not any(args[:2] == ["git", "checkout"] for args in git_args)

    written_path = mock_write.call_args.args[0]
    assert written_path != mapping_path
    assert written_path.name == "project-mappings.json"
