# Todoist Manager Plugin

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](./CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.12+-brightgreen.svg)](https://www.python.org)
[![SDK](https://img.shields.io/badge/todoist--api--python-3.1.0-orange.svg)](https://todoist-python.readthedocs.io)

Complete Todoist integration for Claude Code enabling natural-language task management, daily planning workflows, and productivity coaching through conversational AI.

## Overview

Transform your productivity with AI-powered task management. This plugin brings your Todoist workspace into Claude Code, enabling you to:

- 🗣️ **Natural language task management** - "Show me my tasks today" or "Add task: Buy milk tomorrow @shopping p1"
- 📅 **Intelligent daily planning** - Morning reviews, evening reflections, time-blocking with capacity analysis
- 📊 **Strategic weekly reviews** - Project health monitoring, completion metrics, pattern recognition
- 🧠 **AI productivity coaching** - Task breakdown, prioritization guidance, proactive suggestions
- 🔄 **Complete workflow automation** - From quick task adds to multi-day project planning

**No rigid commands. Just conversation.**

## Features

### 🎯 Core Task Management

- **CRUD Operations:** Create, read, update, delete tasks with full metadata support
- **Smart Filters:** Query tasks using Todoist's powerful filter language (`today & p1`, `@urgent`, `overdue`)
- **Quick Add:** Natural language task creation (`"Buy milk tomorrow @shopping p1"`)
- **Bulk Operations:** Complete, reschedule, or update multiple tasks efficiently
- **Comments:** Add progress updates, notes, and context to tasks
- **Subtasks:** Break down complex work into manageable steps

### 📋 Project & Organization

- **Project Management:** Create, update, and organize projects with sections
- **Label System:** Design and apply context labels (`@office`, `@phone`, `@focus`)
- **Sections:** Organize tasks within projects (e.g., "In Progress", "Blocked", "Done")
- **Hierarchy:** Support for parent/child projects and subtasks
- **Colors & Favorites:** Visual organization with colors and favorite markers

### 🌅 Daily Planning Workflows

**Morning Review:**
- Fetch overdue, today, and upcoming tasks
- Group by priority and project
- Generate time-blocked schedule with capacity analysis
- Create focus lists for the day
- Energy-matched scheduling (deep work vs. admin tasks)

**Evening Review:**
- Completion summary with celebration of wins
- Analyze incomplete tasks
- Reschedule or defer as needed
- Prep tomorrow's overview
- Pattern recognition (chronic deferrals, overload signals)

**Time-Blocking:**
- Calculate available time (meetings, breaks, buffer)
- Fit tasks based on priority and duration
- Flag over-capacity warnings
- Match tasks to energy levels (morning focus, afternoon collaboration, evening admin)

### 📊 Weekly Reviews

- **Completion Metrics:** Tasks completed by project, priority, and date
- **Project Health:** Status indicators (on track, at risk, stalled)
- **Pattern Detection:** Priority inflation, task deferrals, project stalling
- **Maintenance:** Archive completed work, clean up backlog, update labels

### 🧠 Productivity Coaching

- **Task Breakdown:** Decompose complex tasks into actionable subtasks with time estimates
- **Prioritization:** Identify critical vs. nice-to-have work
- **Capacity Planning:** Realistic scheduling based on available time
- **Pattern Recognition:** Detect productivity issues (overload, chronic deferrals, priority inflation)
- **Proactive Suggestions:** Context-aware recommendations for better task management
- **Habit Formation:** Recurring reviews, time-blocking, planning rituals

### 🤖 AI Agent for Complex Workflows

For extended multi-turn sessions, the **todoist-manager agent** provides:
- Multi-day/week planning with comprehensive time-blocking
- Complete task list and project reorganization
- Strategic productivity coaching with pattern analysis
- GTD (Getting Things Done) implementation
- Project planning with phases and milestones

## Installation

### 1. Install Plugin

From the `claude-plugins` repository root:

```bash
./install.sh todoist-manager
```

Or for development (symlink):

```bash
./install.sh --dev todoist-manager
```

### 2. Get Todoist API Token

1. Visit [Todoist Integrations Settings](https://todoist.com/app/settings/integrations/developer)
2. Scroll to "API token" section
3. Copy your token

### 3. Set Environment Variable

**Temporary (current session):**
```bash
export TODOIST_TOKEN="your_token_here"
```

**Persistent (add to shell profile):**
```bash
# For Zsh (macOS default)
echo 'export TODOIST_TOKEN="your_token_here"' >> ~/.zshrc
source ~/.zshrc

# For Bash
echo 'export TODOIST_TOKEN="your_token_here"' >> ~/.bashrc
source ~/.bashrc
```

### 4. Install Python SDK

```bash
pip install 'todoist-api-python>=3.1.0,<4.0.0'

# Or using uv (recommended for Infiquetra projects)
uv pip install 'todoist-api-python>=3.1.0,<4.0.0'
```

### 5. Verify Installation

```bash
python ~/.claude/plugins/todoist-manager/skills/todoist-manage/scripts/todoist_client.py overview
```

Expected: JSON output with your Todoist data

## Usage

### Quick Start

**Invoke the command:**
```bash
/todoist
```

**Or just talk naturally:**
```
"Show me my tasks today"
"Plan my day"
"Add task: Buy milk tomorrow @shopping p1"
"Let's do my morning review"
"What's overdue?"
"Help me prioritize"
```

**Auto-triggers** (no `/todoist` needed):
- "show me my tasks"
- "plan my day"
- "morning review"
- "evening review"
- "weekly review"
- "add task"
- "complete task"
- "what should I work on"
- "time block my day"

### Example Sessions

#### Morning Planning

```
You: Good morning, let's plan my day

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
...

Which 3-5 tasks would make today a success?

You: The three P1 tasks plus the code review

Claude: [Generates time-blocked schedule with capacity analysis]
```

#### Task Breakdown

```
You: I need to work on the quarterly report but don't know where to start

Claude: [Asks clarifying questions about scope, audience, deadline]

You: Executive summary for leadership, due Friday, probably 4-5 hours

Claude:
Here's a breakdown:

1. Research last quarter's data (30 min) @computer
2. Draft executive summary (45 min) @focus @computer
3. Create performance charts (30 min) @computer
4. Write detailed sections (90 min) @focus @computer
5. Review and edit (20 min) @computer
6. Get feedback from manager (async) @waiting
7. Incorporate feedback (30 min) @computer
8. Final proofread (15 min) @computer
9. Submit report (5 min) @computer

Total: ~4.5 hours + async feedback

Should I create these as subtasks in Todoist?
```

#### Evening Review

```
You: Let's review my day

Claude:
🎉 Solid day!

✅ Completed: 8/12 tasks (67%)

What you accomplished:
✓ Fix production bug (P1) - Big win! 🚀
✓ Deploy feature X (P1)
✓ Client call (P1)
✓ Code review (P2)
...

⏳ Remaining (4 tasks):
□ Backlog cleanup (P3) - Defer to weekend?
□ Learning time (P3) - Move to next week?
□ Meal prep (P3) - Tomorrow or Sunday?
□ Fix UI bug (P2) - What blocked this?

What would you like to do with these?
```

#### Complete Reorganization (Agent)

```
You: I have 200 tasks across 15 projects and I'm overwhelmed. Help me reorganize everything.

Claude: I'll use the todoist-manager agent to conduct a comprehensive reorganization session.

[Agent spawns and conducts multi-turn conversation]

Agent:
Let's start by understanding your current pain points...

[Analyzes projects, designs new structure, migrates tasks, validates results]
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TODOIST_TOKEN` | Yes | Personal API token from Todoist settings |

### Dependencies

- **Python:** 3.12+ (3.11 compatible)
- **SDK:** `todoist-api-python>=3.1.0,<4.0.0`

### File Locations

```
~/.claude/plugins/todoist-manager/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── todoist-manage/
│       ├── SKILL.md                          # Main skill instructions
│       ├── scripts/
│       │   └── todoist_client.py             # Python CLI
│       └── references/
│           ├── todoist-api-reference.md       # API method reference
│           ├── filter-query-syntax.md         # Query language guide
│           └── productivity-workflows.md      # Planning templates
├── agents/
│   └── todoist-manager.md                     # Agent for complex workflows
├── commands/
│   └── todoist.md                             # /todoist command docs
└── README.md
```

## Advanced Usage

### Filter Queries

Use Todoist's powerful filter language:

```bash
# Today's urgent tasks
today & p1

# Work tasks due this week
#Work & 7 days

# Waiting tasks that are overdue
@waiting & overdue

# High-priority tasks without due dates
(p1 | p2) & no date

# Complex boolean logic
(today | overdue) & (#Work | #Personal) & !@routine
```

**Date filters:** `today`, `tomorrow`, `overdue`, `7 days`, `next week`, `no date`
**Priority:** `p1` (urgent), `p2` (higher), `p3` (high), `p4` (normal)
**Projects:** `#ProjectName` or `##ProjectName` (include subprojects)
**Labels:** `@LabelName`
**Sections:** `/SectionName`
**Combinators:** `&` (AND), `|` (OR), `!` (NOT), `()` (grouping)

See `references/filter-query-syntax.md` for complete reference.

### Direct Script Usage

For automation or scripting:

```bash
SCRIPT="$HOME/.claude/plugins/todoist-manager/skills/todoist-manage/scripts/todoist_client.py"

# Overview dashboard
python $SCRIPT overview

# Today's tasks
python $SCRIPT tasks filter --query "today"

# Add task
python $SCRIPT tasks add --content "Task name" --due-string "tomorrow" --priority 4

# Complete task
python $SCRIPT tasks complete --task-id 12345

# List projects
python $SCRIPT projects list

# Weekly summary (approximate)
python $SCRIPT tasks filter --query "7 days"
```

All commands output JSON for programmatic parsing.

### Integration with Other Tools

**Git hooks:**
```bash
# .git/hooks/post-commit
python $SCRIPT tasks add --content "Review PR for $(git rev-parse --short HEAD)" --project-id $WORK_PROJECT_ID
```

**Cron jobs:**
```bash
# Daily morning reminder
0 8 * * * python $SCRIPT overview | mail -s "Today's Tasks" user@example.com
```

**Shell aliases:**
```bash
alias tasks="python $SCRIPT tasks filter --query"
alias tasks-today="tasks 'today'"
alias tasks-urgent="tasks 'p1 | p2'"
```

## Troubleshooting

### "TODOIST_TOKEN not set"

**Cause:** Environment variable not configured

**Fix:**
```bash
export TODOIST_TOKEN="your_token_here"
echo 'export TODOIST_TOKEN="your_token_here"' >> ~/.zshrc
source ~/.zshrc
```

### "todoist-api-python not installed"

**Cause:** SDK not installed

**Fix:**
```bash
pip install 'todoist-api-python>=3.1.0,<4.0.0'
```

### "Rate limit exceeded (429)"

**Cause:** Too many API requests in short time

**Fix:**
- Wait 60 seconds and retry
- Use filter queries instead of listing all tasks
- Batch operations when possible

**Rate limits:**
- Free: ~450 requests per 15 minutes
- Premium: Higher limits

### "Task not found (404)"

**Cause:** Task ID doesn't exist or was deleted

**Fix:**
- Verify task ID
- Search by content instead: `tasks filter --query "search: task name"`
- Check if task was recently deleted

### "Connection timeout"

**Cause:** Network issues or Todoist API down

**Fix:**
- Check internet connection
- Check Todoist status: https://status.todoist.com
- Retry after a delay

### Script errors

**Debug mode:**
```bash
python -u $SCRIPT overview 2>&1 | tee debug.log
```

**Verify token:**
```bash
echo $TODOIST_TOKEN | wc -c  # Should be ~40 characters
```

**Test SDK:**
```bash
python -c "from todoist_api_python.api import TodoistAPI; print('OK')"
```

## API Reference

### Resources

- `tasks` - Task CRUD operations
- `projects` - Project management
- `sections` - Section organization
- `labels` - Label management
- `comments` - Task/project comments
- `overview` - Dashboard summary
- `daily-summary` - Daily completion stats

### Common Operations

**List tasks:**
```bash
python $SCRIPT tasks list [--project-id ID] [--section-id ID] [--label NAME]
```

**Filter tasks:**
```bash
python $SCRIPT tasks filter --query "today & p1"
```

**Add task:**
```bash
python $SCRIPT tasks add \
  --content "Task title" \
  --due-string "tomorrow at 3pm" \
  --priority 4 \
  --labels urgent work \
  --project-id 12345
```

**Quick add:**
```bash
python $SCRIPT tasks quick-add --text "Buy milk tomorrow @shopping p1"
```

**Update task:**
```bash
python $SCRIPT tasks update \
  --task-id 12345 \
  --content "Updated title" \
  --due-string "friday"
```

**Complete task:**
```bash
python $SCRIPT tasks complete --task-id 12345
```

See `references/todoist-api-reference.md` for complete API documentation.

## Best Practices

### Daily Workflow

1. **Morning Review (5-10 min):**
   - Run `/todoist` and say "morning review"
   - Review overdue, today, upcoming
   - Select 3-5 focus tasks
   - Generate time-blocked schedule

2. **During the Day:**
   - Complete tasks as you finish them
   - Add new tasks as they come up
   - Update priorities as needed
   - Add comments for progress updates

3. **Evening Review (5 min):**
   - Say "evening review"
   - Celebrate completed work
   - Reschedule incomplete tasks
   - Prep tomorrow's plan

4. **Weekly Review (30 min):**
   - Sunday evening or Monday morning
   - Say "weekly review"
   - Analyze completion metrics
   - Review project health
   - Archive completed work
   - Plan upcoming week

### Organization Tips

**Projects:**
- Keep it simple: 5-10 active projects max
- Use hierarchy: Work > Client X > Feature Y
- Archive completed projects regularly

**Labels:**
- Context labels: `@office`, `@home`, `@computer`, `@phone`
- Energy labels: `@focus`, `@quick`, `@routine`
- Status labels: `@waiting`, `@blocked`, `@urgent`

**Sections:**
- Organize by status: "To Do", "In Progress", "Blocked", "Done"
- Or by phase: "Research", "Design", "Build", "Review", "Deploy"

**Priorities:**
- P1 (urgent): Must do today, blocking others
- P2 (higher): Should do soon, significant impact
- P3 (high): Nice to have, moderate impact
- P4 (normal): Eventually, low impact

**Due Dates:**
- Only set if truly deadline-driven
- Use recurring for habits/routines
- Leave "no date" for backlog items
- Use natural language: "tomorrow at 3pm", "every Monday"

### Productivity Patterns

**Time-Blocking:**
- Estimate task durations
- Use `--duration` and `--duration-unit` when adding tasks
- Match tasks to your energy levels
- Build in buffer time (10-20%)

**Task Breakdown:**
- Keep tasks under 60 minutes
- Break large tasks into subtasks
- Each subtask = one clear action
- Add context labels for easy filtering

**Focus Lists:**
- Create daily focus lists (3-5 tasks)
- Use labels to mark focus tasks
- Filter with `@focus & today`
- Review and adjust as day progresses

**Review Habits:**
- Morning review: Every day
- Evening review: Every day
- Weekly review: Once per week
- Monthly review: Once per month (with agent)

## Contributing

This plugin is part of the Infiquetra Claude Plugins collection. For bug reports, feature requests, or contributions:

1. **Issues:** Open in `claude-plugins` repository
2. **Pull Requests:** Follow Infiquetra contribution guidelines
3. **Discussions:**  Slack channel

## Resources

- **Todoist API:** https://developer.todoist.com
- **Python SDK:** https://todoist-python.readthedocs.io
- **Filter Syntax:** https://todoist.com/help/articles/205248842
- **Plugin Documentation:** See `commands/todoist.md`, `skills/todoist-manage/SKILL.md`
- **Agent Documentation:** See `agents/todoist-manager.md`

## License

Part of Infiquetra Claude Plugins - your organization Internal Tools

## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for version history and updates.

---

**Ready to supercharge your productivity?** Install the plugin and try: `/todoist` or just say "show me my tasks today"! 🚀
