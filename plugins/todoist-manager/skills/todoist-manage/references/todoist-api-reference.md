# Todoist API Reference

Complete reference for the todoist-api-python SDK v3.x methods wrapped by `todoist_client.py`.

## Client Initialization

```python
from todoist_api_python.api import TodoistAPI
api = TodoistAPI(token="your_token_here")
```

## Core Models

### Task
```python
class Task:
    id: str
    content: str
    description: str
    project_id: str
    section_id: Optional[str]
    parent_id: Optional[str]
    order: int
    priority: int  # 1=normal, 2=high, 3=higher, 4=urgent (inverted from display!)
    is_completed: bool
    labels: List[str]
    created_at: str
    creator_id: str
    url: str
    due: Optional[Due]
    duration: Optional[Duration]
```

### Project
```python
class Project:
    id: str
    name: str
    color: str
    parent_id: Optional[str]
    order: int
    comment_count: int
    is_shared: bool
    is_favorite: bool
    is_inbox_project: bool
    is_team_inbox: bool
    view_style: str  # "list" or "board"
    url: str
```

### Section
```python
class Section:
    id: str
    project_id: str
    order: int
    name: str
```

### Label
```python
class Label:
    id: str
    name: str
    color: str
    order: int
    is_favorite: bool
```

### Comment
```python
class Comment:
    id: str
    task_id: Optional[str]
    project_id: Optional[str]
    content: str
    posted_at: str
```

### Due
```python
class Due:
    date: str  # YYYY-MM-DD
    string: str  # Natural language like "tomorrow at 12pm"
    datetime: Optional[str]  # RFC3339 format
    timezone: Optional[str]
    is_recurring: bool
```

### Duration
```python
class Duration:
    amount: int
    unit: str  # "minute" or "day"
```

## Tasks

### get_tasks()
**List tasks with optional filters**

```python
api.get_tasks(
    project_id: Optional[str] = None,
    section_id: Optional[str] = None,
    label: Optional[str] = None,
    filter: Optional[str] = None,
    lang: Optional[str] = None,
    ids: Optional[List[str]] = None
) -> List[Task]
```

**Parameters:**
- `project_id`: Filter by project
- `section_id`: Filter by section
- `label`: Filter by label name
- `filter`: Todoist filter query (see filter-query-syntax.md)
- `lang`: Language for due date parsing (default: user's language)
- `ids`: List of specific task IDs

**Returns:** List of Task objects

### filter_tasks()
**Filter tasks using Todoist query syntax (paginated)**

```python
api.filter_tasks(
    filter: str,
    lang: Optional[str] = None
) -> Iterator[List[Task]]
```

**Parameters:**
- `filter`: Todoist filter query (e.g., "today & p1", "@urgent", "overdue")
- `lang`: Language for due date parsing

**Returns:** Iterator of task lists (requires collection with `_collect()`)

**Example:**
```python
iterator = api.filter_tasks(filter="today & p1")
tasks = []
for page in iterator:
    tasks.extend(page)
```

### get_task()
**Get a specific task by ID**

```python
api.get_task(task_id: str) -> Task
```

### add_task()
**Create a new task**

```python
api.add_task(
    content: str,
    description: Optional[str] = None,
    project_id: Optional[str] = None,
    section_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    order: Optional[int] = None,
    labels: Optional[List[str]] = None,
    priority: Optional[int] = None,  # 1-4
    due_string: Optional[str] = None,
    due_date: Optional[str] = None,  # YYYY-MM-DD
    due_datetime: Optional[str] = None,  # RFC3339
    due_lang: Optional[str] = None,
    assignee_id: Optional[str] = None,
    duration: Optional[int] = None,
    duration_unit: Optional[str] = None  # "minute" or "day"
) -> Task
```

**Due Date Options (use ONE):**
- `due_string`: Natural language ("tomorrow at 3pm", "every monday")
- `due_date`: Date only ("2025-02-24")
- `due_datetime`: Full datetime ("2025-02-24T15:00:00Z")

**Priority Values:**
- `1`: Normal (default)
- `2`: High
- `3`: Higher
- `4`: Urgent (displays as P1 in UI)

**Duration:**
- Used for time-blocking
- `duration_unit` must be "minute" or "day"
- Example: 30 minute task = `duration=30, duration_unit="minute"`

### quick_add_task()
**Add task using Todoist's quick-add syntax**

```python
api.quick_add_task(text: str) -> Task
```

**Example quick-add syntax:**
- `"Buy milk tomorrow @shopping p1"`
- `"Call John every Monday at 9am #Work"`
- `"Review PR !3"` (priority 3)

### update_task()
**Update an existing task**

```python
api.update_task(
    task_id: str,
    content: Optional[str] = None,
    description: Optional[str] = None,
    labels: Optional[List[str]] = None,
    priority: Optional[int] = None,
    due_string: Optional[str] = None,
    due_date: Optional[str] = None,
    due_datetime: Optional[str] = None,
    due_lang: Optional[str] = None,
    assignee_id: Optional[str] = None,
    duration: Optional[int] = None,
    duration_unit: Optional[str] = None
) -> bool
```

**Returns:** True on success, False on failure

### close_task()
**Mark task as completed**

```python
api.close_task(task_id: str) -> bool
```

### reopen_task()
**Reopen a completed task**

```python
api.reopen_task(task_id: str) -> bool
```

### delete_task()
**Permanently delete a task**

```python
api.delete_task(task_id: str) -> bool
```

## Projects

### get_projects()
```python
api.get_projects() -> List[Project]
```

### get_project()
```python
api.get_project(project_id: str) -> Project
```

### add_project()
```python
api.add_project(
    name: str,
    parent_id: Optional[str] = None,
    color: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    view_style: Optional[str] = None  # "list" or "board"
) -> Project
```

**Colors:** Use Todoist color names: "berry_red", "red", "orange", "yellow", "olive_green", "lime_green", "green", "mint_green", "teal", "sky_blue", "light_blue", "blue", "grape", "violet", "lavender", "magenta", "salmon", "charcoal", "grey", "taupe"

### update_project()
```python
api.update_project(
    project_id: str,
    name: Optional[str] = None,
    color: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    view_style: Optional[str] = None
) -> bool
```

### delete_project()
```python
api.delete_project(project_id: str) -> bool
```

## Sections

### get_sections()
```python
api.get_sections(project_id: Optional[str] = None) -> List[Section]
```

### get_section()
```python
api.get_section(section_id: str) -> Section
```

### add_section()
```python
api.add_section(
    name: str,
    project_id: str,
    order: Optional[int] = None
) -> Section
```

### update_section()
```python
api.update_section(section_id: str, name: str) -> bool
```

### delete_section()
```python
api.delete_section(section_id: str) -> bool
```

## Labels

### get_labels()
```python
api.get_labels() -> List[Label]
```

### get_label()
```python
api.get_label(label_id: str) -> Label
```

### add_label()
```python
api.add_label(
    name: str,
    color: Optional[str] = None,
    order: Optional[int] = None,
    is_favorite: Optional[bool] = None
) -> Label
```

### update_label()
```python
api.update_label(
    label_id: str,
    name: Optional[str] = None,
    color: Optional[str] = None,
    order: Optional[int] = None,
    is_favorite: Optional[bool] = None
) -> bool
```

### delete_label()
```python
api.delete_label(label_id: str) -> bool
```

## Comments

### get_comments()
```python
api.get_comments(
    task_id: Optional[str] = None,
    project_id: Optional[str] = None
) -> List[Comment]
```

**Note:** Provide either `task_id` OR `project_id`, not both.

### get_comment()
```python
api.get_comment(comment_id: str) -> Comment
```

### add_comment()
```python
api.add_comment(
    content: str,
    task_id: Optional[str] = None,
    project_id: Optional[str] = None
) -> Comment
```

### update_comment()
```python
api.update_comment(comment_id: str, content: str) -> bool
```

### delete_comment()
```python
api.delete_comment(comment_id: str) -> bool
```

## Completed Tasks (v3.x SDK)

### get_completed_tasks()
```python
api.get_completed_tasks() -> Iterator[List[Task]]
```

**Returns:** Iterator of completed task lists (requires collection)

**Note:** This returns recent completions. For date-based filtering, use in combination with datetime filtering in your code.

## Error Handling

### Common Exceptions

**401 Unauthorized:**
- Invalid or expired API token
- Check `TODOIST_TOKEN` environment variable

**403 Forbidden:**
- Insufficient permissions
- Trying to modify shared project you don't own

**404 Not Found:**
- Task/project/section/label/comment ID doesn't exist
- Resource was deleted

**429 Too Many Requests:**
- Rate limit exceeded
- Wait before retrying (SDK handles some rate limiting automatically)

**500 Internal Server Error:**
- Todoist server error
- Retry after a delay

### Rate Limits

- **Free tier**: ~450 requests per 15 minutes
- **Premium/Business**: Higher limits
- SDK includes automatic retry with exponential backoff
- Use bulk operations when possible

## Response Format

All script outputs are JSON:

```json
{
  "success": true,
  "data": { ... },
  "count": 5,
  "query": "today & p1"
}
```

Or for errors:

```json
{
  "error": true,
  "message": "Failed to get task: Task not found",
  "task_id": "12345"
}
```

## Pagination Pattern

For paginated endpoints (filter_tasks, get_completed_tasks):

```python
def _collect(iterator):
    results = []
    for page in iterator:
        if isinstance(page, list):
            results.extend(page)
        else:
            results.append(page)
    return results
```

## Best Practices

1. **Use filter queries instead of fetching all tasks** - More efficient
2. **Use quick_add_task() for natural language** - Faster for users
3. **Check is_completed before updating** - Avoid unnecessary API calls
4. **Cache project/label lists** - These rarely change
5. **Use bulk operations** - Group related changes
6. **Handle rate limits gracefully** - Implement retry logic
7. **Store IDs, not names** - Names can change, IDs are permanent
