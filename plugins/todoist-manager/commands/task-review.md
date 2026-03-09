# /task-review - Review Tasks for Readiness

Structured review of 1-3 Todoist tasks for clarity, actionability, and execution readiness. Scores each task on a 10-point rubric and provides specific improvement recommendations.

## Usage

```bash
/task-review
```

Then tell Claude which task(s) to review:
```
"Review task: Fix the login bug"
"Check task ID 12345678"
"Review my next 3 tasks"
```

## What It Does

Scores each task across 5 dimensions and provides actionable feedback:

| Dimension | Key Question |
|-----------|--------------|
| **Clarity** | Is the task content unambiguous? |
| **Actionability** | Does it start with a clear action verb? |
| **Scope** | Can it be done in one session (<2 hours)? |
| **Context** | Does it have the right metadata (labels, priority, due date)? |
| **Outcome** | Is "done" clearly defined? |

## Example Output

```
📋 Task Review: "Handle the client thing"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ NOT READY — Score: 4/10

Issues Found:
❌ Clarity (0/2): Too vague — which client? what thing?
❌ Actionability (0/2): "Handle" gives no clear first step
⚠️  Scope (2/2): Probably bounded but hard to tell
❌ Context (0/2): No project, labels, priority, or due date
❌ Outcome (0/2): "Done" is undefined

Revised task suggestion:
"Call Sarah re: Q2 contract renewal terms"
+ Description: "Done when: terms agreed, summary email sent"
+ Labels: @phone @client
+ Due: tomorrow at 2pm
+ Duration: 30 min

Apply this revision? [Y/N]
```

## When to Use

**Use `/task-review` when:**
- About to start a task and want to double-check it
- A task has been deferred multiple times (usually means it's unclear)
- Reviewing tasks before your morning planning session
- Adding new tasks and want to ensure quality

**Use the `todoist-manager` agent instead for:**
- Batch reviews of 10+ tasks
- Full productivity audits
- Complete task list reorganization

## Quick Actions After Review

Based on the review, Claude can:

- **Update task content** — make it more specific and action-oriented
- **Add missing metadata** — labels, priority, due date, duration
- **Add description** — include success criterion ("done when...")
- **Break into subtasks** — if scope is too large (use `/plan-task` instead)

## Auto-Trigger

These phrases activate the task review automatically (no `/task-review` needed):
- "review task [X]"
- "is this task ready?"
- "check my tasks"
- "what's wrong with this task?"
- "prepare task for execution"

## Related

- **`/plan-task`** — Break down a complex task into subtasks
- **`/todoist`** — Full Todoist task management
- **`todoist-manager` agent** — Strategic coaching, batch reviews

## Scoring Reference

Full rubric in `skills/task-review/references/readiness-rubric.md`

| Score | Meaning |
|-------|---------|
| 9-10  | ✅ Ready to Execute |
| 7-8   | ✅ Ready with minor polish |
| 5-6   | ⚠️ Needs Improvement |
| 3-4   | ❌ Not Ready |
| 0-2   | ❌ Placeholder — rewrite needed |
