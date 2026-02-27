---
name: todoist-manage
description: Complete Todoist integration for natural-language task management, daily planning workflows, and productivity coaching through Claude Code conversations
when_to_use: |
  Use this skill when the user:
  - Mentions Todoist or their task list
  - Asks to see tasks, plan their day, or review progress
  - Requests task management operations (add, update, complete, delete)
  - Wants daily planning, morning review, evening review, or weekly review
  - Needs productivity coaching or help organizing work
  - Says "good morning", "plan my day", "what's on my plate", "show my tasks"
  - Mentions overdue tasks, upcoming deadlines, or project status
  - Asks to break down complex tasks or estimate time
  - Wants to organize projects, sections, or labels
  - Needs help with focus, prioritization, or time management

  Auto-triggers (use without explicit /todoist command):
  - "show me my tasks"
  - "what do I have today"
  - "plan my day"
  - "morning review"
  - "evening review"
  - "weekly review"
  - "what's overdue"
  - "add task"
  - "complete task"
  - "what should I work on"
  - "help me prioritize"
  - "focus list"
  - "time block my day"
---

# Todoist Management Skill

Complete personal productivity manager integrating Todoist with Claude Code for natural-language task management, strategic planning, and productivity coaching.

## Prerequisites

### 1. Check Environment Variable

```bash
echo $TODOIST_TOKEN
```

**If not set:**
```
❌ TODOIST_TOKEN not set. You need a Todoist API token to use this skill.

How to get your token:
1. Go to https://todoist.com/app/settings/integrations/developer
2. Scroll to "API token" section
3. Copy your token
4. Run: export TODOIST_TOKEN="your_token_here"
5. Add to your shell profile (~/.zshrc or ~/.bashrc) to persist
```

### 2. Check SDK Installation

```bash
python -c "import todoist_api_python; print('✓ SDK installed')"
```

**If not installed:**
```bash
pip install 'todoist-api-python>=3.1.0,<4.0.0'
# or
uv pip install 'todoist-api-python>=3.1.0,<4.0.0'
```

### 3. Verify Script Access

**Script location:** `plugins/todoist-manager/skills/todoist-manage/scripts/todoist_client.py`

**Test:**
```bash
python plugins/todoist-manager/skills/todoist-manage/scripts/todoist_client.py overview
```

**Expected:** JSON output with overview data

## Script Usage

All operations use the `todoist_client.py` script with JSON output.

### General Pattern

```bash
python <script_path> <resource> <action> [--options]
```

**Resources:** `tasks`, `projects`, `sections`, `labels`, `comments`, `overview`, `daily-summary`

**Output:** Always JSON with this structure:
```json
{
  "success": true,
  "data": { ... },
  "count": 5
}
```

Or for errors:
```json
{
  "error": true,
  "message": "Error description",
  "context": { ... }
}
```

## Section A: Task Management

### List All Tasks

```bash
python todoist_client.py tasks list
```

**Options:**
- `--project-id 12345` - Filter by project
- `--section-id 67890` - Filter by section
- `--label urgent` - Filter by label name
- `--ids 111 222 333` - Specific task IDs

### Filter Tasks with Queries

```bash
python todoist_client.py tasks filter --query "today & p1"
```

**Common queries:**
- `"today"` - Tasks due today
- `"overdue"` - All overdue tasks
- `"7 days"` - Tasks due in next 7 days
- `"today & p1"` - Urgent tasks due today
- `"#Work"` - Tasks in Work project
- `"@urgent"` - Tasks with urgent label
- `"today & !@routine"` - Today's tasks excluding routine
- `"(overdue | today) & (p1 | p2)"` - High-priority tasks needing attention

**See:** `references/filter-query-syntax.md` for complete query language

### Get Single Task

```bash
python todoist_client.py tasks get --task-id 12345
```

### Add Task

**Full form:**
```bash
python todoist_client.py tasks add \
  --content "Task title" \
  --description "Additional details" \
  --project-id 12345 \
  --section-id 67890 \
  --labels urgent important \
  --priority 4 \
  --due-string "tomorrow at 3pm" \
  --duration 30 \
  --duration-unit minute
```

**Minimal:**
```bash
python todoist_client.py tasks add --content "Buy milk"
```

**Priority values:**
- `1` = Normal (P4 in UI)
- `2` = High (P3 in UI)
- `3` = Higher (P2 in UI)
- `4` = Urgent (P1 in UI)

**Due date options (use ONE):**
- `--due-string "tomorrow at 3pm"` - Natural language (recommended)
- `--due-date "2025-02-24"` - Date only (YYYY-MM-DD)
- `--due-datetime "2025-02-24T15:00:00Z"` - Full datetime (RFC3339)

**Duration for time-blocking:**
- `--duration 30 --duration-unit minute` - 30-minute task
- `--duration 2 --duration-unit day` - 2-day task

### Quick Add Task

```bash
python todoist_client.py tasks quick-add --text "Buy milk tomorrow @shopping p1"
```

**Quick-add syntax:**
- `tomorrow` - Due date
- `@shopping` - Label
- `p1` - Priority (urgent)
- `#Work` - Project
- `!3` - Priority (alternative syntax)
- `every monday` - Recurring
- `^today` - Due date with time
- `//Section Name` - Section

**Examples:**
- `"Call John tomorrow at 2pm @phone p2 #Work"`
- `"Team meeting every Friday at 10am #Work"`
- `"Review PR !1 ^today"`

### Update Task

```bash
python todoist_client.py tasks update \
  --task-id 12345 \
  --content "Updated title" \
  --priority 4 \
  --due-string "friday"
```

**Updatable fields:** content, description, labels, priority, due (date/string/datetime), duration

### Complete Task

```bash
python todoist_client.py tasks complete --task-id 12345
```

### Uncomplete Task (Reopen)

```bash
python todoist_client.py tasks uncomplete --task-id 12345
```

### Delete Task

```bash
python todoist_client.py tasks delete --task-id 12345
```

**⚠️ Confirm before deleting** unless clearly temporary or user explicitly requested deletion.

### Bulk Operations

For multiple tasks, use parallel bash calls or loop:

```bash
# Complete multiple tasks
for task_id in 111 222 333; do
  python todoist_client.py tasks complete --task-id $task_id
done
```

**Present summary:**
```
✅ Completed 3 tasks:
- Task A
- Task B
- Task C
```

## Section B: Project & Organization

### Projects

**List all:**
```bash
python todoist_client.py projects list
```

**Get one:**
```bash
python todoist_client.py projects get --project-id 12345
```

**Add project:**
```bash
python todoist_client.py projects add \
  --name "New Project" \
  --color "blue" \
  --is-favorite \
  --view-style "board"
```

**Colors:** berry_red, red, orange, yellow, olive_green, lime_green, green, mint_green, teal, sky_blue, light_blue, blue, grape, violet, lavender, magenta, salmon, charcoal, grey, taupe

**Update:**
```bash
python todoist_client.py projects update --project-id 12345 --name "Renamed Project"
```

**Delete:**
```bash
python todoist_client.py projects delete --project-id 12345
```

**⚠️ Confirm before deleting projects** - this deletes all contained tasks.

### Sections

**List (all or by project):**
```bash
python todoist_client.py sections list
python todoist_client.py sections list --project-id 12345
```

**Add section:**
```bash
python todoist_client.py sections add --name "In Progress" --project-id 12345 --order 1
```

**Update:**
```bash
python todoist_client.py sections update --section-id 67890 --name "Completed"
```

**Delete:**
```bash
python todoist_client.py sections delete --section-id 67890
```

### Labels

**List all:**
```bash
python todoist_client.py labels list
```

**Add label:**
```bash
python todoist_client.py labels add \
  --name "urgent" \
  --color "red" \
  --is-favorite
```

**Update:**
```bash
python todoist_client.py labels update --label-id 54321 --name "super-urgent" --color "berry_red"
```

**Delete:**
```bash
python todoist_client.py labels delete --label-id 54321
```

### Comments

**List (for task or project):**
```bash
python todoist_client.py comments list --task-id 12345
python todoist_client.py comments list --project-id 67890
```

**Add comment:**
```bash
python todoist_client.py comments add --content "Progress update: 50% complete" --task-id 12345
```

**Update:**
```bash
python todoist_client.py comments update --comment-id 99999 --content "Updated progress: 75% complete"
```

**Delete:**
```bash
python todoist_client.py comments delete --comment-id 99999
```

**Use comments for:**
- Progress updates on long-running tasks
- Blockers or notes
- Reminders from user to themselves
- Context for future reference

## Section C: Daily Planning

### Morning Review Workflow

**Goal:** Start the day with clarity and focus.

**1. Fetch overview:**
```bash
python todoist_client.py overview
```

**Output structure:**
```json
{
  "success": true,
  "data": {
    "overdue": {
      "count": 3,
      "by_project": {
        "Work": [...],
        "Personal": [...]
      }
    },
    "today": {
      "count": 12,
      "by_project": {...}
    },
    "upcoming": {
      "count": 25,
      "by_project": {...}
    },
    "total_pending": 40
  }
}
```

**2. Present with priority grouping:**

```
📊 Good morning! Here's your overview:

🔴 Overdue (3)
  Work:
    □ [P1] Fix production bug (urgent!)
    □ [P2] Client proposal draft
  Personal:
    □ [P3] Schedule dentist appointment

📅 Today (12 tasks)
  Work (8):
    □ [P1] Team standup (9am)
    □ [P1] Deploy feature X
    □ [P2] Code review for PR #123
    □ [P2] Update documentation
    □ [P3] Clean up backlog
    ...
  Personal (4):
    □ [P2] Gym workout
    □ [P3] Meal prep
    ...

📆 Upcoming (25 tasks in next 7 days)
  Top priorities:
    - [P1] Quarterly planning (Friday)
    - [P1] Client demo (Thursday)
    - [P2] 1-on-1 with manager (Wednesday)
```

**3. Coach for focus selection:**

Ask user:
- "Which 3-5 tasks would make today a success?"
- "What's your energy level today? (High/Medium/Low)"
- "Any blockers or dependencies?"
- "Expected meetings or interruptions?"

**4. Generate time-blocked schedule:**

Based on user selections and task durations:

```
⏰ Your Focus Plan for Today

🌅 Morning (9am-12pm) - Deep Work
  □ 9:00-9:15   Team standup (15 min)
  □ 9:30-11:00  Deploy feature X (90 min) [P1] 🔴
  □ 11:00-12:00 Code review PR #123 (60 min) [P2]

☀️ Afternoon (1pm-5pm) - Collaboration
  □ 1:00-2:00   Update documentation (60 min) [P2]
  □ 2:00-3:00   Client proposal draft (60 min) [P2] ⚠️ overdue
  □ 3:00-4:00   Fix production bug (60 min) [P1] 🔴 ⚠️ overdue

🌙 Evening (5pm-6pm) - Personal
  □ 5:00-6:00   Gym workout (60 min) [P2]

⏱️  Total: 6.25 hours (buffer: 30 min) ✅

💡 Tips:
- You have 3 overdue tasks - prioritizing those first
- Schedule looks achievable with buffer
- Consider gym as optional if running behind
```

**5. Create focus filter:**

```bash
# Save user's focus selections as custom filter
python todoist_client.py tasks filter --query "(id:111 | id:222 | id:333 | id:444 | id:555)"
```

**Or create a label:**
```bash
python todoist_client.py labels add --name "today-focus"
# Then add label to selected tasks
python todoist_client.py tasks update --task-id 111 --labels today-focus work
```

**6. Proactive suggestions:**

- **Too many P1 tasks (>5)?** "You have 8 urgent tasks today. That's overwhelming. Can we reschedule some or renegotiate deadlines?"
- **Long tasks without subtasks?** "This 3-hour task looks big. Want to break it into smaller steps?"
- **Overdue tasks?** "You have 3 overdue tasks. Let's triage - which are still relevant?"
- **Over capacity?** "You have 8 hours of tasks scheduled with only 6 hours available. Let's defer some to later this week."

**See:** `references/productivity-workflows.md` for complete morning review template

### Evening Review Workflow

**Goal:** Reflect on progress and prep for tomorrow.

**1. Fetch daily summary:**
```bash
python todoist_client.py daily-summary
```

**Output:**
```json
{
  "success": true,
  "data": {
    "completed_today": {
      "count": 8,
      "tasks": [...]
    },
    "remaining_today": {
      "count": 4,
      "tasks": [...]
    },
    "completion_rate": "66.7%"
  }
}
```

**2. Celebrate wins:**

```
🎉 Great work today!

✅ Completed: 8/12 tasks (67%)

What you accomplished:
  ✓ Deploy feature X (P1) - Nice work!
  ✓ Team standup
  ✓ Code review PR #123 (P2)
  ✓ Update documentation
  ✓ Gym workout
  ...

🌟 You cleared 2 overdue tasks and completed all P1s!
```

**3. Review incomplete tasks:**

```
⏳ Remaining tasks (4):

□ Client proposal draft (P2) - Due today
  → Reschedule to tomorrow?

□ Fix production bug (P1) - Due today
  → What blocked this?

□ Clean up backlog (P3)
  → Still relevant or defer?

□ Meal prep (P3)
  → Move to weekend?
```

**For each incomplete, ask:**
- "Still relevant?"
- "What blocked completion?"
- "New due date?"
- "Should we break this down?"

**Actions:**
- Reschedule: `python todoist_client.py tasks update --task-id 123 --due-string "tomorrow"`
- Defer: `--due-string "next week"` or remove due date
- Delete: `python todoist_client.py tasks delete --task-id 123`
- Break down: Create subtasks

**4. Prep for tomorrow:**

```bash
python todoist_client.py tasks filter --query "tomorrow"
```

Present tomorrow's overview:
```
📅 Tomorrow Preview (8 tasks)

Top priorities:
  □ [P1] Client proposal draft (rescheduled from today)
  □ [P1] Quarterly planning prep
  □ [P2] 1-on-1 with manager

Looks manageable! Get good rest. 😴
```

**5. Flag patterns:**

- **Task deferred 3+ times?** "I notice 'Client proposal' keeps getting rescheduled. Is this still a priority?"
- **Consistently incomplete days?** "You've had 4 days in a row under 50% completion. Feeling overwhelmed?"
- **Same tasks always late?** "Your gym workouts keep slipping. Want to move them to morning?"

**See:** `references/productivity-workflows.md` for complete evening review template

### Weekly Review Workflow

**Goal:** Big-picture perspective and course correction.

**1. Generate weekly metrics:**

```bash
# Approximate with filters
python todoist_client.py tasks filter --query "completed this week"
python todoist_client.py tasks filter --query "next 7 days"
python todoist_client.py tasks filter --query "overdue"
```

**2. Present weekly dashboard:**

```
📊 Week of Feb 17-23, 2025

Completed: 45 tasks ✅
Overdue: 3 tasks ⚠️
Completion rate: 82% 🎯

By Project:
  Work: 28 tasks (62%)
  Personal: 15 tasks (33%)
  Side Project: 2 tasks (5%)

By Priority:
  P1: 15 tasks (33%)
  P2: 20 tasks (44%)
  P3+: 10 tasks (22%)

Project Health:
  🟢 Work - On track (8 tasks/week, low overdue)
  🟡 Side Project - At risk (no activity in 5 days)
  🔴 Personal - Stalled (10 tasks overdue, no progress)
```

**3. Review project health:**

For each project:
- ✅ Completed tasks this week
- ⚠️ Overdue count
- 🕐 Days since last activity
- 📋 Tasks without due dates

**Status indicators:**
- 🟢 On track: Progress, low overdue
- 🟡 At risk: High overdue OR no activity 5-7 days
- 🔴 Stalled: No activity 7+ days

**4. Coaching questions:**

- "What went well this week?"
- "What blocked progress on [Stalled Project]?"
- "Side Project has had no activity - pause or delete?"
- "What's the top priority for next week?"
- "Do you need a lighter week or can you push harder?"

**5. Identify patterns:**

- **Priority inflation:** "75% of tasks are P1/P2 - that's not sustainable"
- **Project explosion:** "Work project has 50 tasks - needs organization"
- **Label neglect:** "Only 20% of tasks have context labels"
- **Duration missing:** "Most tasks have no time estimates - hard to plan"

**6. Weekly maintenance:**

- Archive completed projects
- Delete cancelled tasks
- Update stale due dates
- Review "no date" inbox
- Clean up unused labels
- Organize sections

**See:** `references/productivity-workflows.md` for complete weekly review template

## Section D: Productivity Coach

### Task Breakdown

**When to trigger:**
- Task duration >60 minutes
- User says "I don't know where to start"
- Task has been deferred 2+ times
- Vague task content ("Work on project X")

**Process:**

**1. Clarify outcome:**
- "What does 'done' look like?"
- "What's the deliverable?"
- "Who needs what from this?"

**2. Identify steps:**
- Each step starts with action verb
- Each step <30 minutes
- Each step is concrete and actionable

**3. Create subtasks:**

```bash
# Add parent task if needed
python todoist_client.py tasks add \
  --content "Write quarterly report" \
  --project-id 12345 \
  --due-string "Friday"

# Get task ID from response, then add subtasks
python todoist_client.py tasks add \
  --content "Research last quarter's data" \
  --parent-id [parent_task_id] \
  --duration 30 \
  --duration-unit minute \
  --labels computer \
  --priority 2

python todoist_client.py tasks add \
  --content "Draft executive summary" \
  --parent-id [parent_task_id] \
  --duration 45 \
  --duration-unit minute \
  --labels computer focus \
  --priority 2

# Continue for all subtasks
```

**4. Add context:**
- Duration estimates (`--duration`, `--duration-unit`)
- Labels for context (`@computer`, `@phone`, `@office`)
- Labels for energy (`@focus`, `@quick`, `@routine`)
- Due dates for sequencing

**Example breakdown:**

```
"Write quarterly report" →

1. Research last quarter's data (30 min) @computer
2. Draft executive summary (45 min) @focus @computer
3. Create performance charts (30 min) @computer
4. Write detailed sections (90 min) @focus @computer
5. Review and edit (20 min) @computer
6. Get feedback from manager (async) @waiting
7. Incorporate feedback (30 min) @computer
8. Final proofread (15 min) @computer
9. Submit report (5 min) @computer

Total: ~4.5 hours of work time + async feedback
```

**See:** `references/productivity-workflows.md` for complete breakdown framework

### Time-Boxing

**When to use:**
- User asks "will this fit today?"
- Daily plan exceeds available time
- User wants realistic schedule

**Process:**

**1. Calculate available time:**

Ask:
- "What time do you need to stop today?"
- "How many meetings do you have?"
- "Any committed blocks?"

Calculate:
```
Available = End - Start - Meetings - Breaks - Buffer (10%)

Example:
9am-6pm = 9 hours = 540 minutes
- Meetings: 2 hours = 120 minutes
- Lunch + breaks: 1 hour = 60 minutes
- Buffer (10%): 36 minutes
= Available: 324 minutes (5.4 hours)
```

**2. Fetch tasks with durations:**

```bash
python todoist_client.py tasks filter --query "today & !no duration"
```

**3. Prioritize and fit:**

Algorithm:
1. Sort by priority (P1 > P2 > P3 > P4)
2. Sum P1 task durations
3. If under capacity, add P2 tasks
4. Continue until 80-90% capacity

**4. Present schedule:**

```
📅 Today's Schedule (324 min available)

🔴 Must Do (180 min)
  □ 9:00-10:30  Deploy feature X (90 min)
  □ 11:00-12:00 Code review (60 min)
  □ 2:00-2:30   Client call (30 min)

🟡 Should Do (90 min)
  □ 2:30-3:30   Documentation (60 min)
  □ 3:30-4:00   Email responses (30 min)

Buffer: 54 minutes ✅

⚠️ Deferred to tomorrow:
  □ Backlog cleanup (60 min) - P3
  □ Learning time (45 min) - P3
```

**Capacity warnings:**
- ⚠️ Over capacity: Total >100% available
- ⚠️ No buffer: Total = 95-100% available
- ✅ Good balance: Total = 80-90% available
- 😌 Light day: Total <70% available

**5. Match energy levels:**

**Morning (9am-12pm):** Deep work
- @focus tasks
- Long tasks (>60 min)
- Creative/strategic work

**Afternoon (1pm-5pm):** Collaboration
- @collaborate tasks
- Meetings
- Communication

**Evening (5pm-6pm):** Admin
- @quick tasks
- <30 minute tasks
- Email, planning

```bash
# Morning focus tasks
python todoist_client.py tasks filter --query "today & @focus & duration > 60"

# Evening quick tasks
python todoist_client.py tasks filter --query "today & @quick & duration < 30"
```

**See:** `references/productivity-workflows.md` for complete time-boxing framework

### Pattern Recognition

**Automatically detect and flag:**

**🟢 Green Flags (Healthy):**
- Completion rate >70%
- Balanced priorities
- Regular progress on all projects
- Minimal deferrals
- Consistent reviews

**🟡 Yellow Flags (Warning):**
- Completion rate 50-70%
- Priority inflation (too many P1s)
- Frequent rescheduling
- Growing "no date" backlog
- Inconsistent project activity

**🔴 Red Flags (Action Needed):**
- Completion rate <50%
- Chronic overdue (>10 tasks)
- Project stalled 7+ days
- Task deferred 5+ times
- Daily load >8 hours
- No reviews in 7+ days

**Coaching interventions:**

**For priority inflation:**
```
"I notice 15 tasks marked P1. That's overwhelming - not everything can be urgent.
Let's identify the true must-dos for today and downgrade or defer the rest."
```

**For chronic deferrals:**
```
"This task has been rescheduled 5 times. Let's figure out why:
- Still relevant? Or delete?
- Too big? Break it down?
- Blocked? Create unblocking task?
- Lost motivation? Defer indefinitely?"
```

**For overload:**
```
"You have 12 hours of tasks for 6 hours available time.
Let's prioritize the critical 3-4 tasks and defer the rest."
```

**See:** `references/productivity-workflows.md` for complete pattern recognition guide

### Proactive Suggestions

**Always offer when relevant:**

**After showing tasks:**
- "Want me to estimate durations for time-blocking?"
- "Should we add context labels (@office, @computer, @home)?"
- "Any tasks feel too big to tackle?"
- "Which is most critical for today?"

**During planning:**
- "This task has been on your list 3 weeks - still want it?"
- "You have 5 projects with P1 tasks - too many priorities?"
- "All tasks in one project - want to organize by area?"

**After completion:**
- "Nice work! 3/5 P1 tasks done."
- "Great momentum - overdue list is clear!"
- "What would you like to tackle next?"
- "You have 90 minutes left - perfect for [Task Y]."

**Encourage habits:**
- "Would daily reviews at 8am help?"
- "Want a recurring weekly review every Sunday?"
- "Should we create a morning routine checklist?"

## Error Handling

### Missing Token

```json
{
  "error": true,
  "message": "TODOIST_TOKEN environment variable not set"
}
```

**Response:**
```
❌ Todoist token not configured.

To fix:
1. Get your token: https://todoist.com/app/settings/integrations/developer
2. Set it: export TODOIST_TOKEN="your_token_here"
3. Persist: Add to ~/.zshrc or ~/.bashrc
4. Reload: source ~/.zshrc

Then try again!
```

### Rate Limiting

```json
{
  "error": true,
  "message": "Failed to list tasks: 429 Too Many Requests"
}
```

**Response:**
```
⚠️ Hit Todoist rate limit (too many requests).

The API has automatic retry, but you might need to wait a minute.
Try again in 60 seconds.

Tip: Use filter queries instead of listing all tasks to reduce API calls.
```

### Invalid Task ID

```json
{
  "error": true,
  "message": "Failed to get task: Task not found",
  "task_id": "12345"
}
```

**Response:**
```
❌ Task 12345 not found. It may have been deleted or the ID is incorrect.

Want to search for the task instead? I can filter by content.
```

### Network Errors

```json
{
  "error": true,
  "message": "Failed to list tasks: Connection timeout"
}
```

**Response:**
```
❌ Can't reach Todoist API. Check your internet connection.

If you're online, Todoist might be experiencing issues.
Status: https://status.todoist.com
```

## Output Formatting

### Task Lists

**Format based on context:**

**As checklist:**
```
□ Task A (P1) - Due today
□ Task B (P2) - Due tomorrow
□ Task C (P3) - No due date
```

**As table:**
```
| Task                | Priority | Due Date  | Project |
|---------------------|----------|-----------|---------|
| Deploy feature X    | P1 🔴    | Today     | Work    |
| Code review         | P2 🟡    | Tomorrow  | Work    |
| Gym workout         | P2 🟡    | Today     | Personal|
```

**Grouped by project:**
```
Work (8 tasks):
  🔴 P1: Deploy feature X (due today)
  🟡 P2: Code review (due tomorrow)
  ⚪ P3: Documentation update (no date)

Personal (4 tasks):
  🟡 P2: Gym workout (due today)
  ⚪ P3: Meal prep (due Sunday)
```

### Priority Indicators

- 🔴 P1 (Urgent) - priority = 4
- 🟡 P2 (Higher) - priority = 3
- 🟠 P3 (High) - priority = 2
- ⚪ P4 (Normal) - priority = 1

### Status Indicators

- ✅ Completed
- □ Incomplete
- ⚠️ Overdue
- ⏰ Due today
- 📅 Upcoming
- 🔄 Recurring
- ⏳ In progress (has comments/activity)

### Contextual Formatting

**For morning review:** Group by priority, highlight overdue
**For time-blocking:** Format as timeline with durations
**For weekly review:** Show metrics and trends
**For search results:** Show relevant fields (due date, project, priority)

**Always:**
- Use emojis for visual clarity
- Highlight urgent/overdue items
- Group logically (by project, by priority, by date)
- Show counts for awareness
- Provide actionable next steps

## Safety Guidelines

### Always Confirm

**Destructive actions:**
- Deleting tasks (unless temporary)
- Deleting projects
- Deleting labels
- Bulk deletions (>5 items)

**Prompt:** "This will delete [X]. This can't be undone. Confirm?"

### Usually Confirm

**Significant changes:**
- Moving tasks between projects
- Changing due dates by >7 days
- Completing tasks on behalf of user
- Bulk updates (>10 items)
- Archiving projects

**Prompt:** "This will [action] affecting [N] items. Proceed?"

### No Confirmation Needed

**Read operations:**
- Listing tasks
- Filtering
- Viewing overviews
- Searching

**Minor updates:**
- Adding tasks
- Updating content/description
- Adding labels
- Adjusting due date by 1-2 days
- Creating subtasks
- Adding comments

### Trust Your Judgment

When unclear, err on side of confirmation for user peace of mind.

**Exceptions:**
- User explicitly said "delete all overdue tasks" → Confirm even though explicit
- User is in flow state completing many tasks → Skip confirmations for completions
- Emergency situation ("delete everything!") → Still confirm once

## Reference Documents

- **`references/todoist-api-reference.md`** - Complete SDK method reference, parameters, return types
- **`references/filter-query-syntax.md`** - Full Todoist filter query language with examples
- **`references/productivity-workflows.md`** - Strategic planning templates, coaching frameworks

**When to consult:**
- Need to verify exact API parameter names → todoist-api-reference.md
- Building complex filter query → filter-query-syntax.md
- Planning daily/weekly reviews → productivity-workflows.md
- Coaching on productivity patterns → productivity-workflows.md

## Session Examples

### Example 1: Morning Planning

**User:** "Good morning, let's plan my day"

**Claude:**
1. Runs `python todoist_client.py overview`
2. Parses JSON output
3. Presents with priority grouping:
   ```
   📊 Good morning! Here's your overview:

   ⚠️ 3 overdue tasks (2 urgent)
   📅 12 tasks due today
   📆 25 upcoming in next 7 days

   Top priorities for today:
   🔴 [P1] Fix production bug (overdue)
   🔴 [P1] Deploy feature X
   🔴 [P1] Client call at 2pm

   This looks achievable. Which 3-5 tasks would make today a success?
   ```

4. User selects focus tasks
5. Generates time-blocked schedule
6. Creates focus filter or label
7. Estimates total time vs available
8. Offers to defer if over capacity

### Example 2: Task Breakdown

**User:** "I need to work on the client proposal but don't know where to start"

**Claude:**
1. Asks clarifying questions:
   ```
   Let me help break this down.

   - What's the proposal for? (Service offering? Pricing? Pitch?)
   - Who's the audience? (Technical? Executive?)
   - What's the deadline?
   - How long do you think this will take total?
   ```

2. User answers
3. Suggests breakdown:
   ```
   Here's a breakdown:

   1. Research client's needs (30 min) @computer
   2. Draft outline (20 min) @computer
   3. Write executive summary (45 min) @focus @computer
   4. Detail service offering (60 min) @focus @computer
   5. Create pricing table (30 min) @computer
   6. Design cover page (20 min) @computer
   7. Review and polish (20 min) @computer
   8. Get internal feedback (async) @waiting
   9. Incorporate feedback (30 min) @computer
   10. Send to client (5 min) @computer

   Total: ~4 hours of work + async feedback

   Should I create these as subtasks in Todoist?
   ```

4. User confirms
5. Creates parent task + all subtasks with appropriate metadata
6. Suggests starting with research (first subtask)

### Example 3: Evening Review

**User:** "Let's review my day"

**Claude:**
1. Runs `python todoist_client.py daily-summary`
2. Parses output
3. Celebrates wins:
   ```
   🎉 Solid day!

   ✅ Completed: 8/12 tasks (67%)

   What you accomplished:
   ✓ Deploy feature X (P1) - Big win! 🚀
   ✓ Client call
   ✓ Code review
   ✓ Documentation update
   ✓ Gym workout
   ✓ Email responses
   ✓ Team standup
   ✓ Planning session

   You cleared all your P1 tasks and made progress on 2 projects!
   ```

4. Reviews incomplete tasks:
   ```
   ⏳ Remaining (4 tasks):

   □ Fix production bug (P1) - Due today
     What blocked this? Still urgent?

   □ Client proposal (P2) - Due today
     Want to reschedule to tomorrow?

   □ Backlog cleanup (P3)
     Defer to this weekend?

   □ Meal prep (P3)
     Move to tomorrow or Sunday?
   ```

5. For each, gets user input and takes action (reschedule, defer, delete)
6. Prepares tomorrow's overview
7. Flags any patterns (if applicable)

## Quick Reference Commands

**Essential operations:**

```bash
# Morning overview
python todoist_client.py overview

# Today's tasks
python todoist_client.py tasks filter --query "today"

# Add task
python todoist_client.py tasks add --content "Task name" --due-string "tomorrow"

# Quick add (natural language)
python todoist_client.py tasks quick-add --text "Buy milk tomorrow @shopping p1"

# Complete task
python todoist_client.py tasks complete --task-id 12345

# Filter (custom query)
python todoist_client.py tasks filter --query "today & p1"

# Daily summary
python todoist_client.py daily-summary

# List projects
python todoist_client.py projects list

# List labels
python todoist_client.py labels list
```

**Script path:** `plugins/todoist-manager/skills/todoist-manage/scripts/todoist_client.py`

## Integration with Agent

For complex multi-turn workflows (weekly planning, major reorganization, strategic coaching), spawn the **todoist-manager agent**:

```bash
# Example trigger
"I need help completely reorganizing my task list and projects"
```

The agent has full access to this skill and can conduct extended planning sessions with strategic thinking.

**When to use agent:**
- Multi-day/week planning sessions
- Complete task list reorganization
- Strategic project planning
- Extended productivity coaching
- Complex goal setting

**When to use skill directly:**
- Quick task operations
- Daily/evening reviews
- Single task breakdowns
- Viewing overviews
- Routine task management
