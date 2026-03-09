"""Unit tests for todoist_client.py."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent
        / "plugins"
        / "todoist-manager"
        / "skills"
        / "todoist-manage"
        / "scripts"
    ),
)

from todoist_client import TodoistClient


def _make_project(project_id: str, parent_id=None):
    """Create a mock project object."""
    project = MagicMock()
    project.id = project_id
    project.parent_id = parent_id
    return project


def _make_task(task_id: str, content: str = "Test task"):
    """Create a minimal mock task object."""
    task = MagicMock()
    task.id = task_id
    task.content = content
    task.description = ""
    task.project_id = "proj1"
    task.section_id = None
    task.parent_id = None
    task.order = 1
    task.labels = []
    task.priority = 1
    task.comment_count = 0
    task.is_completed = False
    task.created_at = "2025-01-01T00:00:00Z"
    task.creator_id = "user1"
    task.assignee_id = None
    task.assigner_id = None
    task.due = None
    task.deadline = None
    task.duration = None
    task.url = ""
    return task


@pytest.fixture
def client(monkeypatch):
    """Return a TodoistClient with a mocked API."""
    monkeypatch.setenv("TODOIST_TOKEN", "test-token")
    with patch("todoist_client.TodoistAPI"):
        c = TodoistClient()
    return c


class TestGetDescendantProjectIds:
    """Tests for _get_descendant_project_ids."""

    def test_no_children(self, client):
        """Returns empty list when parent has no children."""
        projects = [
            _make_project("parent"),
            _make_project("other", parent_id="unrelated"),
        ]
        client.api.get_projects.return_value = iter([projects])

        result = client._get_descendant_project_ids("parent")

        assert result == []

    def test_direct_children(self, client):
        """Returns direct children of the parent project."""
        projects = [
            _make_project("parent"),
            _make_project("child1", parent_id="parent"),
            _make_project("child2", parent_id="parent"),
            _make_project("other", parent_id="unrelated"),
        ]
        client.api.get_projects.return_value = iter([projects])

        result = client._get_descendant_project_ids("parent")

        assert set(result) == {"child1", "child2"}

    def test_nested_descendants(self, client):
        """Returns all levels of descendants via BFS."""
        projects = [
            _make_project("parent"),
            _make_project("child1", parent_id="parent"),
            _make_project("child2", parent_id="parent"),
            _make_project("grandchild1", parent_id="child1"),
            _make_project("grandchild2", parent_id="child2"),
        ]
        client.api.get_projects.return_value = iter([projects])

        result = client._get_descendant_project_ids("parent")

        assert set(result) == {"child1", "child2", "grandchild1", "grandchild2"}


class TestTasksList:
    """Tests for tasks_list."""

    def test_list_without_flag(self, client, capsys):
        """Without --include-child-projects, queries only the given project."""
        task = _make_task("t1")
        client.api.get_tasks.return_value = iter([[task]])

        client.tasks_list(project_id="proj1")

        client.api.get_tasks.assert_called_once_with(project_id="proj1")
        output = json.loads(capsys.readouterr().out)
        assert output["success"] is True
        assert output["count"] == 1

    def test_list_with_include_child_projects(self, client, capsys):
        """With --include-child-projects, queries parent and all descendants."""
        projects = [
            _make_project("parent"),
            _make_project("child1", parent_id="parent"),
            _make_project("child2", parent_id="parent"),
        ]
        client.api.get_projects.return_value = iter([projects])

        parent_task = _make_task("t1")
        child1_task = _make_task("t2")
        child2_task = _make_task("t3")

        # Return different tasks per project_id call
        def get_tasks_side_effect(project_id, **kwargs):
            mapping = {
                "parent": [parent_task],
                "child1": [child1_task],
                "child2": [child2_task],
            }
            return iter([mapping.get(project_id, [])])

        client.api.get_tasks.side_effect = get_tasks_side_effect

        client.tasks_list(project_id="parent", include_child_projects=True)

        assert client.api.get_tasks.call_count == 3
        output = json.loads(capsys.readouterr().out)
        assert output["success"] is True
        assert output["count"] == 3

    def test_include_child_projects_without_project_id_falls_back(self, client, capsys):
        """Without project_id, --include-child-projects is silently ignored."""
        task = _make_task("t1")
        client.api.get_tasks.return_value = iter([[task]])

        client.tasks_list(include_child_projects=True)

        # Falls back to normal list (no project_id set)
        client.api.get_tasks.assert_called_once_with()
        output = json.loads(capsys.readouterr().out)
        assert output["success"] is True
