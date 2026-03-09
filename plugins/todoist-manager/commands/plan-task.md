# /plan-task - Break Down Complex Tasks

Converts a complex task or vague goal into well-structured, actionable Todoist subtasks with realistic time estimates and appropriate metadata.

## Usage

```bash
/plan-task
```

Then describe the task to plan:
```
"Plan this task: Write quarterly business review"
"Break down: Set up CI/CD pipeline for new service"
"I don't know where to start with the client proposal"
"Help me plan out the feature release checklist"
```

## What It Does

1. **Clarifies the goal** — asks 2-3 targeted questions about outcome, deadline, and scope
2. **Generates a step-by-step plan** — ordered subtasks with action verbs and time estimates
3. **Shows the plan** — lets you review and adjust before creating anything
4. **Creates subtasks in Todoist** — parent task + all subtasks with metadata

## Example Output

```
📋 Plan for: "Write quarterly business review presentation"

Breakdown (12 steps, ~5 hours):

Session 1 (~2h)
  1. Gather Q3 metrics data (30 min) @computer
  2. Draft slide outline (20 min) @focus @computer
  3. Write executive summary slide (30 min) @focus
  4. Create performance charts (45 min) @computer

Session 2 (~2h)
  5. Write KPI slides (45 min) @focus @computer
  6. Write Wins & Challenges slides (30 min) @computer
  7. Draft Q4 goals slide (20 min) @focus
  8. Design cover and transitions (20 min) @computer
  9. Self-review full deck (20 min)

Session 3 (~1h)
  10. Send for stakeholder review (5 min) @quick
  11. Incorporate feedback (30 min) @computer
  12. Final proofread and send (15 min) @quick

Create these subtasks? [Y/N]
```

## When to Use

**Use `/plan-task` when:**
- A task is too large to execute in one session (>2 hours)
- You don't know where to start
- A task has been deferred multiple times
- You have a goal but no clear steps
- You want a structured approach before diving in

**Use the `todoist-manager` agent instead for:**
- Multi-week project planning with milestones
- Planning entire sprints or quarters
- Strategic goal setting and roadmapping

## Common Task Types

| Task Type | Typical Steps |
|-----------|---------------|
| Writing / Documents | Outline → Write sections → Review → Revise → Send |
| Coding / Engineering | Understand → Explore → Plan → Implement → Test → Deploy |
| Research / Analysis | Define questions → Gather → Synthesize → Document → Present |
| Meeting Prep | Define objectives → Gather data → Build materials → Rehearse → Send pre-reads |
| Admin / Process | Gather info → Complete form/action → Confirm/submit → Follow up |

## After Planning

Once subtasks are created, Claude will:

- **Identify the first step** — "Ready to start with step 1?"
- **Suggest scheduling** — "Want to time-block sessions this week?"
- **Flag deadlines** — "With 5 hours of work, you'll need to start by Wednesday for a Friday deadline"
- **Offer a focus label** — Add `@today-focus` to the first step

## Auto-Trigger

These phrases activate plan-task automatically:
- "break this down"
- "plan this task"
- "I don't know where to start with [X]"
- "create a plan for [X]"
- "this task is too big"
- "subtasks for [X]"

## Related

- **`/task-review`** — Check if a task is ready to execute (before planning)
- **`/todoist`** — Full Todoist task management
- **`todoist-manager` agent** — Strategic multi-week planning

## Tips

**Be specific when describing the task:**
- ✅ "Plan: Write API documentation for the new auth endpoints (3 endpoints)"
- ❌ "Plan my work stuff"

**Share constraints upfront:**
- "Due Friday, probably 4-5 hours total"
- "Needs sign-off from Sarah before going live"
- "Starting from scratch — no existing draft"
