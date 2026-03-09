#!/usr/bin/env python3
"""
Todoist CLI - Command-line interface for Todoist API operations.

This script wraps the official todoist-api-python SDK and provides a unified
CLI for all Todoist operations. All output is JSON for Claude Code to parse.

Environment Variables:
    TODOIST_TOKEN: Personal API token from Todoist (required)

Usage:
    python3 todoist_client.py overview
    python3 todoist_client.py tasks list
    python3 todoist_client.py tasks filter --query "today & p1"
    python3 todoist_client.py tasks add --content "Task name" --project-id 12345
    python3 todoist_client.py projects list
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Iterator

# Try to import the SDK; auto-install if missing
try:
    from todoist_api_python.api import TodoistAPI
    from todoist_api_python.models import (
        Task,
        Project,
        Section,
        Label,
        Comment,
        Due,
        Duration,
    )
except ImportError:
    import subprocess
    print(json.dumps({"info": "Installing todoist-api-python SDK..."}), flush=True)
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "todoist-api-python>=3.1.0,<4.0.0"],
        stdout=subprocess.DEVNULL,
    )
    from todoist_api_python.api import TodoistAPI
    from todoist_api_python.models import (
        Task,
        Project,
        Section,
        Label,
        Comment,
        Due,
        Duration,
    )


class TodoistClient:
    """Wrapper for Todoist API operations with JSON output."""

    def __init__(self, token: Optional[str] = None):
        """Initialize the Todoist client.

        Args:
            token: Todoist API token (defaults to TODOIST_TOKEN env var)
        """
        self.token = token or os.getenv("TODOIST_TOKEN")
        if not self.token:
            self._error("TODOIST_TOKEN environment variable not set")
            sys.exit(1)

        try:
            self.api = TodoistAPI(self.token)
        except Exception as e:
            self._error(f"Failed to initialize Todoist API: {str(e)}")
            sys.exit(1)

    def _error(self, message: str, **kwargs) -> None:
        """Output error in JSON format."""
        error_data = {"error": True, "message": message}
        error_data.update(kwargs)
        print(json.dumps(error_data, indent=2))

    def _success(self, data: Any, **kwargs) -> None:
        """Output success data in JSON format."""
        output = {"success": True, "data": data}
        output.update(kwargs)
        print(json.dumps(output, indent=2, default=str))

    def _collect(self, iterator: Iterator) -> List[Any]:
        """Collect all pages from an iterator.

        The SDK returns Iterator[list[T]] for paginated results.
        We need to consume all pages and flatten into a single list.
        """
        results = []
        try:
            for page in iterator:
                if isinstance(page, list):
                    results.extend(page)
                else:
                    results.append(page)
        except Exception as e:
            self._error(f"Error collecting paginated results: {str(e)}")
            sys.exit(1)
        return results

    def _task_to_dict(self, task: Task) -> Dict[str, Any]:
        """Convert Task object to dict with nested object handling."""
        task_dict = {
            "id": task.id,
            "content": task.content,
            "description": task.description,
            "project_id": task.project_id,
            "section_id": task.section_id,
            "parent_id": task.parent_id,
            "order": task.order,
            "priority": task.priority,
            "is_completed": task.is_completed,
            "labels": task.labels,
            "created_at": task.created_at,
            "creator_id": task.creator_id,
            "url": task.url,
        }

        # Handle Due object
        if task.due:
            task_dict["due"] = {
                "date": task.due.date,
                "string": task.due.string,
                "datetime": getattr(task.due, "datetime", None),
                "timezone": getattr(task.due, "timezone", None),
                "is_recurring": task.due.is_recurring,
            }
        else:
            task_dict["due"] = None

        # Handle Duration object
        if hasattr(task, "duration") and task.duration:
            task_dict["duration"] = {
                "amount": task.duration.amount,
                "unit": task.duration.unit,
            }
        else:
            task_dict["duration"] = None

        return task_dict

    def _project_to_dict(self, project: Project) -> Dict[str, Any]:
        """Convert Project object to dict."""
        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "color": project.color,
            "parent_id": project.parent_id,
            "order": project.order,
            "is_shared": project.is_shared,
            "is_favorite": project.is_favorite,
            "is_inbox_project": project.is_inbox_project,
            "is_collapsed": project.is_collapsed,
            "is_archived": project.is_archived,
            "can_assign_tasks": project.can_assign_tasks,
            "view_style": project.view_style,
            "created_at": str(project.created_at),
            "updated_at": str(project.updated_at),
            "workspace_id": project.workspace_id,
            "folder_id": project.folder_id,
        }

    def _section_to_dict(self, section: Section) -> Dict[str, Any]:
        """Convert Section object to dict."""
        return {
            "id": section.id,
            "project_id": section.project_id,
            "order": section.order,
            "name": section.name,
        }

    def _label_to_dict(self, label: Label) -> Dict[str, Any]:
        """Convert Label object to dict."""
        return {
            "id": label.id,
            "name": label.name,
            "color": label.color,
            "order": label.order,
            "is_favorite": label.is_favorite,
        }

    def _comment_to_dict(self, comment: Comment) -> Dict[str, Any]:
        """Convert Comment object to dict."""
        return {
            "id": comment.id,
            "task_id": getattr(comment, "task_id", None),
            "project_id": getattr(comment, "project_id", None),
            "content": comment.content,
            "posted_at": comment.posted_at,
        }

    # ===========================
    # TASKS
    # ===========================

    def tasks_list(self, project_id: Optional[str] = None, section_id: Optional[str] = None,
                   label: Optional[str] = None, ids: Optional[List[str]] = None) -> None:
        """List tasks with optional filters."""
        try:
            kwargs = {}
            if project_id:
                kwargs["project_id"] = project_id
            if section_id:
                kwargs["section_id"] = section_id
            if label:
                kwargs["label"] = label
            if ids:
                kwargs["ids"] = ids

            tasks_paginator = self.api.get_tasks(**kwargs)
            tasks = self._collect(tasks_paginator)
            tasks_data = [self._task_to_dict(task) for task in tasks]
            self._success(tasks_data, count=len(tasks_data))
        except Exception as e:
            self._error(f"Failed to list tasks: {str(e)}")
            sys.exit(1)

    def tasks_filter(self, query: str) -> None:
        """Filter tasks using Todoist query syntax."""
        try:
            iterator = self.api.filter_tasks(query=query)
            tasks = self._collect(iterator)
            tasks_data = [self._task_to_dict(task) for task in tasks]
            self._success(tasks_data, count=len(tasks_data), query=query)
        except Exception as e:
            self._error(f"Failed to filter tasks: {str(e)}", query=query)
            sys.exit(1)

    def tasks_get(self, task_id: str) -> None:
        """Get a specific task by ID."""
        try:
            task = self.api.get_task(task_id=task_id)
            self._success(self._task_to_dict(task))
        except Exception as e:
            self._error(f"Failed to get task: {str(e)}", task_id=task_id)
            sys.exit(1)

    def tasks_add(self, content: str, description: Optional[str] = None,
                  project_id: Optional[str] = None, section_id: Optional[str] = None,
                  parent_id: Optional[str] = None, order: Optional[int] = None,
                  labels: Optional[List[str]] = None, priority: Optional[int] = None,
                  due_string: Optional[str] = None, due_date: Optional[str] = None,
                  due_datetime: Optional[str] = None, due_lang: Optional[str] = None,
                  assignee_id: Optional[str] = None, duration: Optional[int] = None,
                  duration_unit: Optional[str] = None) -> None:
        """Add a new task."""
        try:
            kwargs = {"content": content}
            if description:
                kwargs["description"] = description
            if project_id:
                kwargs["project_id"] = project_id
            if section_id:
                kwargs["section_id"] = section_id
            if parent_id:
                kwargs["parent_id"] = parent_id
            if order is not None:
                kwargs["order"] = order
            if labels:
                kwargs["labels"] = labels
            if priority is not None:
                kwargs["priority"] = priority
            if due_string:
                kwargs["due_string"] = due_string
            if due_date:
                kwargs["due_date"] = due_date
            if due_datetime:
                kwargs["due_datetime"] = due_datetime
            if due_lang:
                kwargs["due_lang"] = due_lang
            if assignee_id:
                kwargs["assignee_id"] = assignee_id
            if duration is not None and duration_unit:
                kwargs["duration"] = duration
                kwargs["duration_unit"] = duration_unit

            task = self.api.add_task(**kwargs)
            self._success(self._task_to_dict(task))
        except Exception as e:
            self._error(f"Failed to add task: {str(e)}")
            sys.exit(1)

    def tasks_quick_add(self, text: str) -> None:
        """Add a task using Todoist quick-add syntax."""
        try:
            task = self.api.add_task_quick(text=text)
            self._success(self._task_to_dict(task))
        except Exception as e:
            self._error(f"Failed to quick-add task: {str(e)}", text=text)
            sys.exit(1)

    def tasks_update(self, task_id: str, content: Optional[str] = None,
                     description: Optional[str] = None, labels: Optional[List[str]] = None,
                     priority: Optional[int] = None, due_string: Optional[str] = None,
                     due_date: Optional[str] = None, due_datetime: Optional[str] = None,
                     due_lang: Optional[str] = None, assignee_id: Optional[str] = None,
                     duration: Optional[int] = None, duration_unit: Optional[str] = None) -> None:
        """Update an existing task."""
        try:
            kwargs = {}
            if content:
                kwargs["content"] = content
            if description:
                kwargs["description"] = description
            if labels is not None:
                kwargs["labels"] = labels
            if priority is not None:
                kwargs["priority"] = priority
            if due_string:
                kwargs["due_string"] = due_string
            if due_date:
                kwargs["due_date"] = due_date
            if due_datetime:
                kwargs["due_datetime"] = due_datetime
            if due_lang:
                kwargs["due_lang"] = due_lang
            if assignee_id:
                kwargs["assignee_id"] = assignee_id
            if duration is not None and duration_unit:
                kwargs["duration"] = duration
                kwargs["duration_unit"] = duration_unit

            success = self.api.update_task(task_id=task_id, **kwargs)
            if success:
                # Fetch the updated task
                task = self.api.get_task(task_id=task_id)
                self._success(self._task_to_dict(task))
            else:
                self._error("Failed to update task", task_id=task_id)
                sys.exit(1)
        except Exception as e:
            self._error(f"Failed to update task: {str(e)}", task_id=task_id)
            sys.exit(1)

    def tasks_complete(self, task_id: str) -> None:
        """Mark a task as completed."""
        try:
            success = self.api.complete_task(task_id=task_id)
            if success:
                self._success({"task_id": task_id, "completed": True})
            else:
                self._error("Failed to complete task", task_id=task_id)
                sys.exit(1)
        except Exception as e:
            self._error(f"Failed to complete task: {str(e)}", task_id=task_id)
            sys.exit(1)

    def tasks_uncomplete(self, task_id: str) -> None:
        """Reopen a completed task."""
        try:
            success = self.api.uncomplete_task(task_id=task_id)
            if success:
                self._success({"task_id": task_id, "uncompleted": True})
            else:
                self._error("Failed to uncomplete task", task_id=task_id)
                sys.exit(1)
        except Exception as e:
            self._error(f"Failed to uncomplete task: {str(e)}", task_id=task_id)
            sys.exit(1)

    def tasks_delete(self, task_id: str) -> None:
        """Delete a task."""
        try:
            success = self.api.delete_task(task_id=task_id)
            if success:
                self._success({"task_id": task_id, "deleted": True})
            else:
                self._error("Failed to delete task", task_id=task_id)
                sys.exit(1)
        except Exception as e:
            self._error(f"Failed to delete task: {str(e)}", task_id=task_id)
            sys.exit(1)

    def tasks_subtasks(self, parent_id: str) -> None:
        """Fetch subtasks for a given parent task ID."""
        try:
            tasks_iterator = self.api.get_tasks(parent_id=parent_id)
            tasks = self._collect(tasks_iterator)
            self._success([self._task_to_dict(task) for task in tasks], count=len(tasks))
        except Exception as e:
            self._error(f"Failed to get subtasks: {str(e)}", parent_id=parent_id)
            sys.exit(1)

    # ===========================
    # PROJECTS
    # ===========================

    def projects_list(self) -> None:
        """List all projects."""
        try:
            projects_paginator = self.api.get_projects()
            projects = self._collect(projects_paginator)
            projects_data = [self._project_to_dict(project) for project in projects]
            self._success(projects_data, count=len(projects_data))
        except Exception as e:
            self._error(f"Failed to list projects: {str(e)}")
            sys.exit(1)

    def projects_get(self, project_id: str) -> None:
        """Get a specific project by ID."""
        try:
            project = self.api.get_project(project_id=project_id)
            self._success(self._project_to_dict(project))
        except Exception as e:
            self._error(f"Failed to get project: {str(e)}", project_id=project_id)
            sys.exit(1)

    def projects_add(self, name: str, parent_id: Optional[str] = None,
                     color: Optional[str] = None, is_favorite: Optional[bool] = None,
                     view_style: Optional[str] = None) -> None:
        """Add a new project."""
        try:
            kwargs = {"name": name}
            if parent_id:
                kwargs["parent_id"] = parent_id
            if color:
                kwargs["color"] = color
            if is_favorite is not None:
                kwargs["is_favorite"] = is_favorite
            if view_style:
                kwargs["view_style"] = view_style

            project = self.api.add_project(**kwargs)
            self._success(self._project_to_dict(project))
        except Exception as e:
            self._error(f"Failed to add project: {str(e)}")
            sys.exit(1)

    def projects_update(self, project_id: str, name: Optional[str] = None,
                        color: Optional[str] = None, is_favorite: Optional[bool] = None,
                        view_style: Optional[str] = None) -> None:
        """Update an existing project."""
        try:
            kwargs = {}
            if name:
                kwargs["name"] = name
            if color:
                kwargs["color"] = color
            if is_favorite is not None:
                kwargs["is_favorite"] = is_favorite
            if view_style:
                kwargs["view_style"] = view_style

            success = self.api.update_project(project_id=project_id, **kwargs)
            if success:
                project = self.api.get_project(project_id=project_id)
                self._success(self._project_to_dict(project))
            else:
                self._error("Failed to update project", project_id=project_id)
                sys.exit(1)
        except Exception as e:
            self._error(f"Failed to update project: {str(e)}", project_id=project_id)
            sys.exit(1)

    def projects_delete(self, project_id: str) -> None:
        """Delete a project."""
        try:
            success = self.api.delete_project(project_id=project_id)
            if success:
                self._success({"project_id": project_id, "deleted": True})
            else:
                self._error("Failed to delete project", project_id=project_id)
                sys.exit(1)
        except Exception as e:
            self._error(f"Failed to delete project: {str(e)}", project_id=project_id)
            sys.exit(1)

    # ===========================
    # SECTIONS
    # ===========================

    def sections_list(self, project_id: Optional[str] = None) -> None:
        """List sections, optionally filtered by project."""
        try:
            kwargs = {}
            if project_id:
                kwargs["project_id"] = project_id

            sections_paginator = self.api.get_sections(**kwargs)
            sections = self._collect(sections_paginator)
            sections_data = [self._section_to_dict(section) for section in sections]
            self._success(sections_data, count=len(sections_data))
        except Exception as e:
            self._error(f"Failed to list sections: {str(e)}")
            sys.exit(1)

    def sections_get(self, section_id: str) -> None:
        """Get a specific section by ID."""
        try:
            section = self.api.get_section(section_id=section_id)
            self._success(self._section_to_dict(section))
        except Exception as e:
            self._error(f"Failed to get section: {str(e)}", section_id=section_id)
            sys.exit(1)

    def sections_add(self, name: str, project_id: str, order: Optional[int] = None) -> None:
        """Add a new section to a project."""
        try:
            kwargs = {"name": name, "project_id": project_id}
            if order is not None:
                kwargs["order"] = order

            section = self.api.add_section(**kwargs)
            self._success(self._section_to_dict(section))
        except Exception as e:
            self._error(f"Failed to add section: {str(e)}")
            sys.exit(1)

    def sections_update(self, section_id: str, name: str) -> None:
        """Update a section's name."""
        try:
            success = self.api.update_section(section_id=section_id, name=name)
            if success:
                section = self.api.get_section(section_id=section_id)
                self._success(self._section_to_dict(section))
            else:
                self._error("Failed to update section", section_id=section_id)
                sys.exit(1)
        except Exception as e:
            self._error(f"Failed to update section: {str(e)}", section_id=section_id)
            sys.exit(1)

    def sections_delete(self, section_id: str) -> None:
        """Delete a section."""
        try:
            success = self.api.delete_section(section_id=section_id)
            if success:
                self._success({"section_id": section_id, "deleted": True})
            else:
                self._error("Failed to delete section", section_id=section_id)
                sys.exit(1)
        except Exception as e:
            self._error(f"Failed to delete section: {str(e)}", section_id=section_id)
            sys.exit(1)

    # ===========================
    # LABELS
    # ===========================

    def labels_list(self) -> None:
        """List all labels."""
        try:
            labels_paginator = self.api.get_labels()
            labels = self._collect(labels_paginator)
            labels_data = [self._label_to_dict(label) for label in labels]
            self._success(labels_data, count=len(labels_data))
        except Exception as e:
            self._error(f"Failed to list labels: {str(e)}")
            sys.exit(1)

    def labels_get(self, label_id: str) -> None:
        """Get a specific label by ID."""
        try:
            label = self.api.get_label(label_id=label_id)
            self._success(self._label_to_dict(label))
        except Exception as e:
            self._error(f"Failed to get label: {str(e)}", label_id=label_id)
            sys.exit(1)

    def labels_add(self, name: str, color: Optional[str] = None,
                   order: Optional[int] = None, is_favorite: Optional[bool] = None) -> None:
        """Add a new label."""
        try:
            kwargs = {"name": name}
            if color:
                kwargs["color"] = color
            if order is not None:
                kwargs["order"] = order
            if is_favorite is not None:
                kwargs["is_favorite"] = is_favorite

            label = self.api.add_label(**kwargs)
            self._success(self._label_to_dict(label))
        except Exception as e:
            self._error(f"Failed to add label: {str(e)}")
            sys.exit(1)

    def labels_update(self, label_id: str, name: Optional[str] = None,
                      color: Optional[str] = None, order: Optional[int] = None,
                      is_favorite: Optional[bool] = None) -> None:
        """Update an existing label."""
        try:
            kwargs = {}
            if name:
                kwargs["name"] = name
            if color:
                kwargs["color"] = color
            if order is not None:
                kwargs["order"] = order
            if is_favorite is not None:
                kwargs["is_favorite"] = is_favorite

            success = self.api.update_label(label_id=label_id, **kwargs)
            if success:
                label = self.api.get_label(label_id=label_id)
                self._success(self._label_to_dict(label))
            else:
                self._error("Failed to update label", label_id=label_id)
                sys.exit(1)
        except Exception as e:
            self._error(f"Failed to update label: {str(e)}", label_id=label_id)
            sys.exit(1)

    def labels_delete(self, label_id: str) -> None:
        """Delete a label."""
        try:
            success = self.api.delete_label(label_id=label_id)
            if success:
                self._success({"label_id": label_id, "deleted": True})
            else:
                self._error("Failed to delete label", label_id=label_id)
                sys.exit(1)
        except Exception as e:
            self._error(f"Failed to delete label: {str(e)}", label_id=label_id)
            sys.exit(1)

    # ===========================
    # COMMENTS
    # ===========================

    def comments_list(self, task_id: Optional[str] = None, project_id: Optional[str] = None) -> None:
        """List comments for a task or project."""
        try:
            kwargs = {}
            if task_id:
                kwargs["task_id"] = task_id
            if project_id:
                kwargs["project_id"] = project_id

            comments_paginator = self.api.get_comments(**kwargs)
            comments = self._collect(comments_paginator)
            comments_data = [self._comment_to_dict(comment) for comment in comments]
            self._success(comments_data, count=len(comments_data))
        except Exception as e:
            self._error(f"Failed to list comments: {str(e)}")
            sys.exit(1)

    def comments_get(self, comment_id: str) -> None:
        """Get a specific comment by ID."""
        try:
            comment = self.api.get_comment(comment_id=comment_id)
            self._success(self._comment_to_dict(comment))
        except Exception as e:
            self._error(f"Failed to get comment: {str(e)}", comment_id=comment_id)
            sys.exit(1)

    def comments_add(self, content: str, task_id: Optional[str] = None,
                     project_id: Optional[str] = None) -> None:
        """Add a comment to a task or project."""
        try:
            kwargs = {"content": content}
            if task_id:
                kwargs["task_id"] = task_id
            if project_id:
                kwargs["project_id"] = project_id

            comment = self.api.add_comment(**kwargs)
            self._success(self._comment_to_dict(comment))
        except Exception as e:
            self._error(f"Failed to add comment: {str(e)}")
            sys.exit(1)

    def comments_update(self, comment_id: str, content: str) -> None:
        """Update a comment's content."""
        try:
            success = self.api.update_comment(comment_id=comment_id, content=content)
            if success:
                comment = self.api.get_comment(comment_id=comment_id)
                self._success(self._comment_to_dict(comment))
            else:
                self._error("Failed to update comment", comment_id=comment_id)
                sys.exit(1)
        except Exception as e:
            self._error(f"Failed to update comment: {str(e)}", comment_id=comment_id)
            sys.exit(1)

    def comments_delete(self, comment_id: str) -> None:
        """Delete a comment."""
        try:
            success = self.api.delete_comment(comment_id=comment_id)
            if success:
                self._success({"comment_id": comment_id, "deleted": True})
            else:
                self._error("Failed to delete comment", comment_id=comment_id)
                sys.exit(1)
        except Exception as e:
            self._error(f"Failed to delete comment: {str(e)}", comment_id=comment_id)
            sys.exit(1)

    # ===========================
    # OVERVIEW & SUMMARIES
    # ===========================

    def overview(self) -> None:
        """Generate dashboard overview: overdue, today, upcoming grouped by project."""
        try:
            # Fetch all projects for names
            projects_paginator = self.api.get_projects()
            projects = self._collect(projects_paginator)
            project_map = {p.id: p.name for p in projects}

            # Fetch overdue tasks
            overdue_iterator = self.api.filter_tasks(query="overdue")
            overdue_tasks = self._collect(overdue_iterator)

            # Fetch today's tasks
            today_iterator = self.api.filter_tasks(query="today")
            today_tasks = self._collect(today_iterator)

            # Fetch upcoming tasks (next 7 days, excluding today)
            upcoming_iterator = self.api.filter_tasks(query="7 days")
            upcoming_tasks = self._collect(upcoming_iterator)
            # Filter out today's tasks from upcoming
            today_ids = {t.id for t in today_tasks}
            upcoming_tasks = [t for t in upcoming_tasks if t.id not in today_ids]

            def group_by_project(tasks):
                """Group tasks by project."""
                grouped = {}
                for task in tasks:
                    project_name = project_map.get(task.project_id, "Unknown Project")
                    if project_name not in grouped:
                        grouped[project_name] = []
                    grouped[project_name].append(self._task_to_dict(task))
                return grouped

            overview_data = {
                "overdue": {
                    "count": len(overdue_tasks),
                    "by_project": group_by_project(overdue_tasks),
                },
                "today": {
                    "count": len(today_tasks),
                    "by_project": group_by_project(today_tasks),
                },
                "upcoming": {
                    "count": len(upcoming_tasks),
                    "by_project": group_by_project(upcoming_tasks),
                },
                "total_pending": len(overdue_tasks) + len(today_tasks) + len(upcoming_tasks),
            }

            self._success(overview_data)
        except Exception as e:
            self._error(f"Failed to generate overview: {str(e)}")
            sys.exit(1)

    def daily_summary(self) -> None:
        """Generate daily summary: completed today + remaining today."""
        try:
            # Get today's date range
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)

            # Fetch completed tasks for today
            # Note: SDK method might differ; using filter if no direct method
            # Assuming we need to get recent completions and filter
            try:
                # Try to get completed tasks by completion date
                completed_iterator = self.api.get_completed_tasks_by_completion_date()
                completed_today = []
                for page in completed_iterator:
                    for task in page:
                        # Filter by completion date
                        if hasattr(task, 'completed_at'):
                            completed_at = datetime.fromisoformat(task.completed_at.replace('Z', '+00:00'))
                            if today_start <= completed_at < today_end:
                                completed_today.append(self._task_to_dict(task))
            except Exception:
                # Fallback if completed tasks endpoint unavailable
                completed_today = []

            # Fetch remaining tasks for today
            today_iterator = self.api.filter_tasks(query="today")
            remaining_today = self._collect(today_iterator)

            summary_data = {
                "completed_today": {
                    "count": len(completed_today),
                    "tasks": completed_today,
                },
                "remaining_today": {
                    "count": len(remaining_today),
                    "tasks": [self._task_to_dict(task) for task in remaining_today],
                },
                "completion_rate": (
                    f"{len(completed_today) / (len(completed_today) + len(remaining_today)) * 100:.1f}%"
                    if (len(completed_today) + len(remaining_today)) > 0
                    else "N/A"
                ),
            }

            self._success(summary_data)
        except Exception as e:
            self._error(f"Failed to generate daily summary: {str(e)}")
            sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Todoist CLI - Command-line interface for Todoist API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="resource", help="Resource to manage")

    # ===========================
    # TASKS
    # ===========================
    tasks_parser = subparsers.add_parser("tasks", help="Manage tasks")
    tasks_subparsers = tasks_parser.add_subparsers(dest="action", help="Task action")

    # tasks list
    tasks_list_parser = tasks_subparsers.add_parser("list", help="List tasks")
    tasks_list_parser.add_argument("--project-id", help="Filter by project ID")
    tasks_list_parser.add_argument("--section-id", help="Filter by section ID")
    tasks_list_parser.add_argument("--label", help="Filter by label name")
    tasks_list_parser.add_argument("--ids", nargs="+", help="Specific task IDs")

    # tasks filter
    tasks_filter_parser = tasks_subparsers.add_parser("filter", help="Filter tasks with query")
    tasks_filter_parser.add_argument("--query", required=True, help="Todoist filter query")

    # tasks get
    tasks_get_parser = tasks_subparsers.add_parser("get", help="Get a specific task")
    tasks_get_parser.add_argument("--task-id", required=True, help="Task ID")

    # tasks add
    tasks_add_parser = tasks_subparsers.add_parser("add", help="Add a new task")
    tasks_add_parser.add_argument("--content", required=True, help="Task content")
    tasks_add_parser.add_argument("--description", help="Task description")
    tasks_add_parser.add_argument("--project-id", help="Project ID")
    tasks_add_parser.add_argument("--section-id", help="Section ID")
    tasks_add_parser.add_argument("--parent-id", help="Parent task ID")
    tasks_add_parser.add_argument("--order", type=int, help="Task order")
    tasks_add_parser.add_argument("--labels", nargs="+", help="Label names")
    tasks_add_parser.add_argument("--priority", type=int, choices=[1, 2, 3, 4], help="Priority (1=normal, 4=urgent)")
    tasks_add_parser.add_argument("--due-string", help="Due date in natural language")
    tasks_add_parser.add_argument("--due-date", help="Due date (YYYY-MM-DD)")
    tasks_add_parser.add_argument("--due-datetime", help="Due datetime (RFC3339)")
    tasks_add_parser.add_argument("--due-lang", help="Language for due string")
    tasks_add_parser.add_argument("--assignee-id", help="Assignee ID")
    tasks_add_parser.add_argument("--duration", type=int, help="Duration amount")
    tasks_add_parser.add_argument("--duration-unit", choices=["minute", "day"], help="Duration unit")

    # tasks quick-add
    tasks_quick_add_parser = tasks_subparsers.add_parser("quick-add", help="Quick add task")
    tasks_quick_add_parser.add_argument("--text", required=True, help="Quick add text")

    # tasks update
    tasks_update_parser = tasks_subparsers.add_parser("update", help="Update a task")
    tasks_update_parser.add_argument("--task-id", required=True, help="Task ID")
    tasks_update_parser.add_argument("--content", help="New content")
    tasks_update_parser.add_argument("--description", help="New description")
    tasks_update_parser.add_argument("--labels", nargs="+", help="New label names")
    tasks_update_parser.add_argument("--priority", type=int, choices=[1, 2, 3, 4], help="Priority")
    tasks_update_parser.add_argument("--due-string", help="Due date in natural language")
    tasks_update_parser.add_argument("--due-date", help="Due date (YYYY-MM-DD)")
    tasks_update_parser.add_argument("--due-datetime", help="Due datetime (RFC3339)")
    tasks_update_parser.add_argument("--due-lang", help="Language for due string")
    tasks_update_parser.add_argument("--assignee-id", help="Assignee ID")
    tasks_update_parser.add_argument("--duration", type=int, help="Duration amount")
    tasks_update_parser.add_argument("--duration-unit", choices=["minute", "day"], help="Duration unit")

    # tasks complete
    tasks_complete_parser = tasks_subparsers.add_parser("complete", help="Complete a task")
    tasks_complete_parser.add_argument("--task-id", required=True, help="Task ID")

    # tasks uncomplete
    tasks_uncomplete_parser = tasks_subparsers.add_parser("uncomplete", help="Reopen a task")
    tasks_uncomplete_parser.add_argument("--task-id", required=True, help="Task ID")

    # tasks delete
    tasks_delete_parser = tasks_subparsers.add_parser("delete", help="Delete a task")
    tasks_delete_parser.add_argument("--task-id", required=True, help="Task ID")

    # tasks subtasks
    tasks_subtasks_parser = tasks_subparsers.add_parser("subtasks", help="Get subtasks for a parent task")
    tasks_subtasks_parser.add_argument("--parent-id", required=True, help="Parent task ID")

    # ===========================
    # PROJECTS
    # ===========================
    projects_parser = subparsers.add_parser("projects", help="Manage projects")
    projects_subparsers = projects_parser.add_subparsers(dest="action", help="Project action")

    # projects list
    projects_subparsers.add_parser("list", help="List projects")

    # projects get
    projects_get_parser = projects_subparsers.add_parser("get", help="Get a specific project")
    projects_get_parser.add_argument("--project-id", required=True, help="Project ID")

    # projects add
    projects_add_parser = projects_subparsers.add_parser("add", help="Add a new project")
    projects_add_parser.add_argument("--name", required=True, help="Project name")
    projects_add_parser.add_argument("--parent-id", help="Parent project ID")
    projects_add_parser.add_argument("--color", help="Project color")
    projects_add_parser.add_argument("--is-favorite", action="store_true", help="Mark as favorite")
    projects_add_parser.add_argument("--view-style", choices=["list", "board"], help="View style")

    # projects update
    projects_update_parser = projects_subparsers.add_parser("update", help="Update a project")
    projects_update_parser.add_argument("--project-id", required=True, help="Project ID")
    projects_update_parser.add_argument("--name", help="New name")
    projects_update_parser.add_argument("--color", help="New color")
    projects_update_parser.add_argument("--is-favorite", action="store_true", help="Mark as favorite")
    projects_update_parser.add_argument("--view-style", choices=["list", "board"], help="View style")

    # projects delete
    projects_delete_parser = projects_subparsers.add_parser("delete", help="Delete a project")
    projects_delete_parser.add_argument("--project-id", required=True, help="Project ID")

    # ===========================
    # SECTIONS
    # ===========================
    sections_parser = subparsers.add_parser("sections", help="Manage sections")
    sections_subparsers = sections_parser.add_subparsers(dest="action", help="Section action")

    # sections list
    sections_list_parser = sections_subparsers.add_parser("list", help="List sections")
    sections_list_parser.add_argument("--project-id", help="Filter by project ID")

    # sections get
    sections_get_parser = sections_subparsers.add_parser("get", help="Get a specific section")
    sections_get_parser.add_argument("--section-id", required=True, help="Section ID")

    # sections add
    sections_add_parser = sections_subparsers.add_parser("add", help="Add a new section")
    sections_add_parser.add_argument("--name", required=True, help="Section name")
    sections_add_parser.add_argument("--project-id", required=True, help="Project ID")
    sections_add_parser.add_argument("--order", type=int, help="Section order")

    # sections update
    sections_update_parser = sections_subparsers.add_parser("update", help="Update a section")
    sections_update_parser.add_argument("--section-id", required=True, help="Section ID")
    sections_update_parser.add_argument("--name", required=True, help="New name")

    # sections delete
    sections_delete_parser = sections_subparsers.add_parser("delete", help="Delete a section")
    sections_delete_parser.add_argument("--section-id", required=True, help="Section ID")

    # ===========================
    # LABELS
    # ===========================
    labels_parser = subparsers.add_parser("labels", help="Manage labels")
    labels_subparsers = labels_parser.add_subparsers(dest="action", help="Label action")

    # labels list
    labels_subparsers.add_parser("list", help="List labels")

    # labels get
    labels_get_parser = labels_subparsers.add_parser("get", help="Get a specific label")
    labels_get_parser.add_argument("--label-id", required=True, help="Label ID")

    # labels add
    labels_add_parser = labels_subparsers.add_parser("add", help="Add a new label")
    labels_add_parser.add_argument("--name", required=True, help="Label name")
    labels_add_parser.add_argument("--color", help="Label color")
    labels_add_parser.add_argument("--order", type=int, help="Label order")
    labels_add_parser.add_argument("--is-favorite", action="store_true", help="Mark as favorite")

    # labels update
    labels_update_parser = labels_subparsers.add_parser("update", help="Update a label")
    labels_update_parser.add_argument("--label-id", required=True, help="Label ID")
    labels_update_parser.add_argument("--name", help="New name")
    labels_update_parser.add_argument("--color", help="New color")
    labels_update_parser.add_argument("--order", type=int, help="New order")
    labels_update_parser.add_argument("--is-favorite", action="store_true", help="Mark as favorite")

    # labels delete
    labels_delete_parser = labels_subparsers.add_parser("delete", help="Delete a label")
    labels_delete_parser.add_argument("--label-id", required=True, help="Label ID")

    # ===========================
    # COMMENTS
    # ===========================
    comments_parser = subparsers.add_parser("comments", help="Manage comments")
    comments_subparsers = comments_parser.add_subparsers(dest="action", help="Comment action")

    # comments list
    comments_list_parser = comments_subparsers.add_parser("list", help="List comments")
    comments_list_parser.add_argument("--task-id", help="Filter by task ID")
    comments_list_parser.add_argument("--project-id", help="Filter by project ID")

    # comments get
    comments_get_parser = comments_subparsers.add_parser("get", help="Get a specific comment")
    comments_get_parser.add_argument("--comment-id", required=True, help="Comment ID")

    # comments add
    comments_add_parser = comments_subparsers.add_parser("add", help="Add a new comment")
    comments_add_parser.add_argument("--content", required=True, help="Comment content")
    comments_add_parser.add_argument("--task-id", help="Task ID")
    comments_add_parser.add_argument("--project-id", help="Project ID")

    # comments update
    comments_update_parser = comments_subparsers.add_parser("update", help="Update a comment")
    comments_update_parser.add_argument("--comment-id", required=True, help="Comment ID")
    comments_update_parser.add_argument("--content", required=True, help="New content")

    # comments delete
    comments_delete_parser = comments_subparsers.add_parser("delete", help="Delete a comment")
    comments_delete_parser.add_argument("--comment-id", required=True, help="Comment ID")

    # ===========================
    # OVERVIEW & SUMMARIES
    # ===========================
    subparsers.add_parser("overview", help="Generate dashboard overview")
    subparsers.add_parser("daily-summary", help="Generate daily summary")

    # Parse arguments
    args = parser.parse_args()

    if not args.resource:
        parser.print_help()
        sys.exit(1)

    # Initialize client
    client = TodoistClient()

    # Route to appropriate handler
    if args.resource == "tasks":
        if not args.action:
            tasks_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.tasks_list(
                project_id=args.project_id,
                section_id=args.section_id,
                label=args.label,
                ids=args.ids,
            )
        elif args.action == "filter":
            client.tasks_filter(query=args.query)
        elif args.action == "get":
            client.tasks_get(task_id=args.task_id)
        elif args.action == "add":
            client.tasks_add(
                content=args.content,
                description=args.description,
                project_id=args.project_id,
                section_id=args.section_id,
                parent_id=args.parent_id,
                order=args.order,
                labels=args.labels,
                priority=args.priority,
                due_string=args.due_string,
                due_date=args.due_date,
                due_datetime=args.due_datetime,
                due_lang=args.due_lang,
                assignee_id=args.assignee_id,
                duration=args.duration,
                duration_unit=args.duration_unit,
            )
        elif args.action == "quick-add":
            client.tasks_quick_add(text=args.text)
        elif args.action == "update":
            client.tasks_update(
                task_id=args.task_id,
                content=args.content,
                description=args.description,
                labels=args.labels,
                priority=args.priority,
                due_string=args.due_string,
                due_date=args.due_date,
                due_datetime=args.due_datetime,
                due_lang=args.due_lang,
                assignee_id=args.assignee_id,
                duration=args.duration,
                duration_unit=args.duration_unit,
            )
        elif args.action == "complete":
            client.tasks_complete(task_id=args.task_id)
        elif args.action == "uncomplete":
            client.tasks_uncomplete(task_id=args.task_id)
        elif args.action == "delete":
            client.tasks_delete(task_id=args.task_id)
        elif args.action == "subtasks":
            client.tasks_subtasks(parent_id=args.parent_id)

    elif args.resource == "projects":
        if not args.action:
            projects_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.projects_list()
        elif args.action == "get":
            client.projects_get(project_id=args.project_id)
        elif args.action == "add":
            client.projects_add(
                name=args.name,
                parent_id=args.parent_id,
                color=args.color,
                is_favorite=args.is_favorite,
                view_style=args.view_style,
            )
        elif args.action == "update":
            client.projects_update(
                project_id=args.project_id,
                name=args.name,
                color=args.color,
                is_favorite=args.is_favorite,
                view_style=args.view_style,
            )
        elif args.action == "delete":
            client.projects_delete(project_id=args.project_id)

    elif args.resource == "sections":
        if not args.action:
            sections_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.sections_list(project_id=args.project_id)
        elif args.action == "get":
            client.sections_get(section_id=args.section_id)
        elif args.action == "add":
            client.sections_add(
                name=args.name,
                project_id=args.project_id,
                order=args.order,
            )
        elif args.action == "update":
            client.sections_update(section_id=args.section_id, name=args.name)
        elif args.action == "delete":
            client.sections_delete(section_id=args.section_id)

    elif args.resource == "labels":
        if not args.action:
            labels_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.labels_list()
        elif args.action == "get":
            client.labels_get(label_id=args.label_id)
        elif args.action == "add":
            client.labels_add(
                name=args.name,
                color=args.color,
                order=args.order,
                is_favorite=args.is_favorite,
            )
        elif args.action == "update":
            client.labels_update(
                label_id=args.label_id,
                name=args.name,
                color=args.color,
                order=args.order,
                is_favorite=args.is_favorite,
            )
        elif args.action == "delete":
            client.labels_delete(label_id=args.label_id)

    elif args.resource == "comments":
        if not args.action:
            comments_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.comments_list(task_id=args.task_id, project_id=args.project_id)
        elif args.action == "get":
            client.comments_get(comment_id=args.comment_id)
        elif args.action == "add":
            client.comments_add(
                content=args.content,
                task_id=args.task_id,
                project_id=args.project_id,
            )
        elif args.action == "update":
            client.comments_update(comment_id=args.comment_id, content=args.content)
        elif args.action == "delete":
            client.comments_delete(comment_id=args.comment_id)

    elif args.resource == "overview":
        client.overview()

    elif args.resource == "daily-summary":
        client.daily_summary()


if __name__ == "__main__":
    main()
