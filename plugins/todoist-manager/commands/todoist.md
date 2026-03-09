# /todoist - Personal Task Management & Productivity Coaching

Natural-language Todoist integration for task management, daily planning, and productivity coaching through Claude Code.

## Usage

```bash
/todoist
```

Activates the **todoist-manage** skill for comprehensive Todoist operations.

## What It Does

The `/todoist` command enables full Todoist integration:

- **Task Management:** View, add, update, complete, and organize tasks
- **Daily Planning:** Morning reviews, evening reviews, time-blocking
- **Weekly Reviews:** Progress tracking, project health, pattern recognition
- **Productivity Coaching:** Task breakdown, prioritization, strategic planning
- **Organization:** Manage projects, sections, labels, and comments
- **Complex Workflows:** Multi-day planning, complete reorganization (via agent)

## Quick Actions

**After invoking `/todoist`, you can naturally say:**

```bash
# Morning planning
"Show me my tasks for today"
"What's overdue?"
"Let's plan my day"
"Give me an overview"

# Task operations
"Add task: Buy milk tomorrow @shopping p1"
"Complete task: Deploy feature X"
"Reschedule client call to Friday"
"Break down the quarterly report task"

# Reviews
"Let's do my morning review"
"Evening review"
"Weekly review"
"How did I do today?"

# Organization
"Show all my projects"
"List my labels"
"What's in the Work project?"
"Show tasks with @urgent label"

# Planning
"Time-block my day"
"Which tasks should I focus on?"
"What's my priority for today?"
"Create a schedule that fits in 6 hours"

# Coaching
"I'm overwhelmed - help me prioritize"
"I keep rescheduling the same task - what's wrong?"
"Analyze my productivity patterns"
"Help me organize my projects better"
```

## Auto-Trigger (No /todoist needed)

These phrases automatically activate the skill:

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

## Prerequisites

### 1. Todoist API Token

Get your personal API token:

1. Visit https://todoist.com/app/settings/integrations/developer
2. Scroll to "API token" section
3. Copy your token
4. Set environment variable:

```bash
export TODOIST_TOKEN="your_token_here"
```

**Persist across sessions:**

```bash
# Add to ~/.zshrc or ~/.bashrc
echo 'export TODOIST_TOKEN="your_token_here"' >> ~/.zshrc
source ~/.zshrc
```

### 2. Python SDK

Install the official Todoist SDK:

```bash
pip install 'todoist-api-python>=3.1.0,<4.0.0'
# or
uv pip install 'todoist-api-python>=3.1.0,<4.0.0'
```

### 3. Verify Setup

Test the configuration:

```bash
python3 plugins/todoist-manager/skills/todoist-manage/scripts/todoist_client.py overview
```

Expected: JSON output with your Todoist data

## Example Session

### Morning Planning

```
You: /todoist

Claude: Todoist integration activated! How can I help with your tasks today?

You: Let's plan my day

Claude:
📊 Good morning! Here's your overview:

⚠️ 3 overdue tasks (2 urgent)
📅 12 tasks due today
📆 25 upcoming in next 7 days

Top priorities for today:
🔴 [P1] Fix production bug (overdue)
🔴 [P1] Deploy feature X
🔴 [P1] Client call at 2pm
🟡 [P2] Code review PR #123
🟡 [P2] Update documentation
🟡 [P2] Team standup
...

This looks achievable. Which 3-5 tasks would make today a success?

You: The three P1 tasks plus the code review

Claude:
⏰ Your Focus Plan for Today

🌅 Morning (9am-12pm) - Deep Work
  □ 9:00-10:30  Fix production bug (90 min) [P1] 🔴 ⚠️ overdue
  □ 11:00-12:00 Deploy feature X (60 min) [P1] 🔴

☀️ Afternoon (1pm-5pm)
  □ 1:00-2:00   Code review PR #123 (60 min) [P2]
  □ 2:00-2:30   Client call (30 min) [P1] 🔴

⏱️  Total: 4 hours (buffer: 2 hours) ✅

💡 Tips:
- Tackling overdue bug first - great prioritization
- Schedule has good buffer for unexpected issues
- Client call is time-blocked - set a reminder?

Ready to start? Let me know when you complete each task!
```

### Task Breakdown

```
You: I need to work on the quarterly report but don't know where to start

Claude:
Let me help break this down.

Quick questions:
- What's the report for? (Team update? Executive summary?)
- Who's the audience?
- What's the deadline?
- How long do you think this will take total?

You: Executive summary for leadership, due Friday, probably 4-5 hours

Claude:
Perfect! Here's a breakdown:

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

Total: ~4.5 hours of work + async feedback

This matches your 4-5 hour estimate. Should I create these as subtasks in Todoist?

You: Yes please

Claude:
✅ Created quarterly report with 9 subtasks!

I've organized them with:
- Durations for time-blocking
- Context labels (@computer, @focus, @waiting)
- Logical sequence

Suggest starting with step 1 (research) - it's a 30-minute task that will set up the rest. Ready to begin?
```

### Evening Review

```
You: Let's review my day

Claude:
🎉 Solid day!

✅ Completed: 8/12 tasks (67%)

What you accomplished:
✓ Fix production bug (P1) - Big win! 🚀
✓ Deploy feature X (P1)
✓ Client call (P1)
✓ Code review PR #123 (P2)
✓ Team standup
✓ Email responses
✓ Documentation update
✓ Planning session

You cleared all your P1 tasks and made progress on 2 projects!

⏳ Remaining (4 tasks):

□ Backlog cleanup (P3)
  → Defer to this weekend?

□ Learning time (P3)
  → Move to tomorrow or next week?

□ Meal prep (P3)
  → Tomorrow or Sunday?

□ Fix UI bug (P2)
  → What blocked this? Still a priority?

What would you like to do with these?
```

## Complex Workflows

For extended multi-turn sessions (weekly planning, complete reorganization, strategic coaching), the **todoist-manager agent** will be automatically spawned.

**Triggers for agent:**
- "I need to completely reorganize my Todoist"
- "Help me plan my entire month"
- "I've been struggling with productivity - can you analyze my patterns?"
- "Let's set up a GTD system"
- "Design a project plan for my new initiative"

The agent has full Todoist access and provides strategic thinking for complex workflows.

## Features

### Task Operations
- List, filter, search tasks
- Add tasks (full form or quick-add)
- Update content, due dates, priorities, labels
- Complete/uncomplete tasks
- Delete tasks
- Break down complex tasks into subtasks
- Add/view comments

### Daily Planning
- Morning review with priority grouping
- Evening review with completion analysis
- Time-blocking with capacity planning
- Focus list generation
- Energy-matched scheduling (deep work vs. admin)

### Weekly Reviews
- Completion metrics by project/priority
- Project health assessment
- Pattern recognition (overload, deferrals, stalling)
- Maintenance tasks (cleanup, archive)

### Productivity Coaching
- Task breakdown framework
- Prioritization guidance
- Time estimation and scheduling
- Proactive suggestions based on patterns
- Habit formation support

### Organization
- Project management (create, update, archive)
- Section organization within projects
- Label system design and application
- Comment threads on tasks/projects

### Advanced Filtering
- Natural language queries
- Date filters (today, overdue, 7 days, etc.)
- Priority filters (p1, p2, p3, p4)
- Project/label/section filters
- Complex boolean queries (AND, OR, NOT)

## Tips

**Make it natural:**
- Just talk - no need for rigid commands
- Ask questions like "what should I work on?"
- Request help when stuck: "I'm overwhelmed"

**Use context:**
- Morning: "plan my day" or "morning review"
- Evening: "how did I do?" or "evening review"
- Weekly: "weekly review" or "what went well this week?"

**Be specific when needed:**
- "Add task: Buy milk tomorrow @shopping p1"
- "Complete task: Deploy feature X"
- "Show tasks with @urgent label"

**Let Claude coach you:**
- "Help me prioritize"
- "This task is too big - break it down"
- "Why do I keep rescheduling this?"

**Trust the agent:**
- For complex workflows, Claude will automatically spawn the todoist-manager agent
- The agent provides strategic thinking for multi-turn planning sessions

## Troubleshooting

### "TODOIST_TOKEN not set"

```bash
# Get token from Todoist
open https://todoist.com/app/settings/integrations/developer

# Set token
export TODOIST_TOKEN="your_token_here"

# Persist
echo 'export TODOIST_TOKEN="your_token_here"' >> ~/.zshrc
source ~/.zshrc
```

### "SDK not installed"

```bash
pip install 'todoist-api-python>=3.1.0,<4.0.0'
# or
uv pip install 'todoist-api-python>=3.1.0,<4.0.0'
```

### "Rate limit exceeded"

Wait 60 seconds and try again. Use filter queries instead of listing all tasks to reduce API calls.

### "Task not found"

The task may have been deleted or the ID is incorrect. Try searching by content instead.

## Related

- **Skill:** `todoist-manage` (handles all operations)
- **Agent:** `todoist-manager` (for complex workflows)
- **Script:** `plugins/todoist-manager/skills/todoist-manage/scripts/todoist_client.py`

## Learn More

- Todoist API: https://developer.todoist.com
- SDK Docs: https://todoist-python.readthedocs.io
- Filter Syntax: https://todoist.com/help/articles/205248842

---

**Ready to supercharge your productivity?** Just type `/todoist` or naturally say "show me my tasks today"!
