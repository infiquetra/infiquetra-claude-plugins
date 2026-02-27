# Productivity Workflows & Coaching Templates

Strategic frameworks for daily planning, task management, and productivity coaching through Todoist.

## Morning Review Workflow

**Goal:** Start the day with clarity on what matters most.

### 1. Fetch Overview

```bash
python todoist_client.py overview
```

**What to present:**
- Overdue count (with urgency indicator if >5)
- Today's task count by project
- Upcoming tasks (next 7 days) summary

### 2. Present by Priority Tiers

**Format tasks in three tiers:**

**🔴 Urgent (P1)**
- Must be done today
- Blocking others
- Time-sensitive

**🟡 Important (P2)**
- Significant impact
- Should be completed
- Not time-critical today

**⚪ Other (P3-P4)**
- Nice to have
- Low impact
- Can be rescheduled

### 3. Coaching Questions

Ask the user to guide focus selection:

- "Which 3 tasks would make today a success?"
- "Are any tasks blockers for team members?"
- "What's your energy level? (Deep work vs. light tasks)"
- "Any tasks that could be delegated or deferred?"
- "Expected meetings/interruptions today?"

### 4. Generate Focus List

**Create a custom focus filter:**

```bash
# Based on user's selections
python todoist_client.py tasks filter --query "(p1 & today) | @focus"
```

**Present as time-blocked schedule:**
```
🌅 Morning (9am-12pm) - Deep Work
□ Task A (90 min) - High priority project
□ Task B (45 min) - Planning session

☀️ Afternoon (1pm-5pm) - Collaboration
□ Task C (30 min) - Team review
□ Task D (60 min) - Documentation

🌙 Evening (5pm-6pm) - Admin
□ Task E (20 min) - Email follow-ups
□ Task F (15 min) - Tomorrow prep
```

### 5. Offer Proactive Suggestions

Based on patterns:

- **Too many P1 tasks?** Suggest renegotiating deadlines or deferring
- **Long tasks without subtasks?** Suggest breaking down
- **Tasks without durations?** Suggest time estimates for better planning
- **Recurring overdue?** Flag as pattern and suggest rescheduling or canceling

## Evening Review Workflow

**Goal:** Close the day with a sense of accomplishment and prep for tomorrow.

### 1. Fetch Daily Summary

```bash
python todoist_client.py daily-summary
```

**Present:**
- ✅ Completed today (count + list)
- ⏳ Incomplete today (remaining)
- 📊 Completion rate (%)

### 2. Celebrate Wins

**Positive reinforcement:**
- "Great work! You completed 8/10 tasks today (80%)"
- "You crushed all your P1 tasks!"
- "You finished ahead of schedule on [Project Name]"

### 3. Review Incomplete Tasks

For each incomplete task:

**Ask:**
- "Still relevant? Or can we defer?"
- "What blocked completion?"
- "Should this be broken into smaller tasks?"
- "New due date?"

**Actions:**
- Reschedule: Update due date
- Defer: Move to specific future date or "no date"
- Break down: Create subtasks
- Delete: Remove if no longer needed

### 4. Prep for Tomorrow

**Generate tomorrow's overview:**

```bash
python todoist_client.py tasks filter --query "tomorrow"
```

**Questions:**
- "Anything to add for tomorrow?"
- "Any prep work needed tonight?"
- "Expected challenges or blockers?"

### 5. Pattern Recognition

Track and flag:
- **Chronic deferrals:** Task rescheduled 3+ times
- **Recurring overdue:** Same task always late
- **Project stalling:** No progress in 7 days
- **Overwhelm signals:** Consistently incomplete days

**Coaching:**
- "I notice [Task X] keeps getting rescheduled. Is this still a priority?"
- "You haven't made progress on [Project Y] this week. Want to discuss blockers?"

## Weekly Review Workflow

**Goal:** Big-picture perspective and course correction.

### 1. Fetch Weekly Data

**Completed this week:**
```bash
# Approximate with date range
python todoist_client.py tasks filter --query "completed this week"
```

**Upcoming next week:**
```bash
python todoist_client.py tasks filter --query "next 7 days"
```

### 2. Present Weekly Metrics

**Format:**
```
📊 Week of [Date Range]

Completed: 45 tasks
Overdue: 3 tasks
Rescheduled: 8 tasks
New tasks added: 12 tasks

By Project:
- Work: 28 tasks (62%)
- Personal: 15 tasks (33%)
- Side Project: 2 tasks (5%)

By Priority:
- P1: 15 tasks
- P2: 20 tasks
- P3+: 10 tasks
```

### 3. Review Project Health

For each active project:

**Check:**
- Tasks completed vs. added
- Overdue count
- Tasks without due dates
- Stalled tasks (no activity in 7+ days)

**Status:**
- 🟢 On track: Progressing, low overdue
- 🟡 At risk: High overdue, no recent activity
- 🔴 Stalled: No progress in 7+ days

### 4. Identify Bottlenecks

**Common patterns:**
- **Task explosion:** Project has >20 tasks without subtask organization
- **Priority inflation:** Everything is P1
- **Deadline creep:** Due dates constantly pushed
- **Label neglect:** Tasks without context labels

### 5. Planning Questions

**Strategic:**
- "What went well this week?"
- "What blocked progress?"
- "Any projects to pause or cancel?"
- "What's the top priority for next week?"
- "Energy level - need a lighter week?"

### 6. Weekly Actions

**Maintenance:**
- Archive completed projects
- Delete cancelled tasks
- Update project goals/descriptions
- Review and update labels
- Clean up "no date" inbox

## Task Breakdown Framework

**Goal:** Decompose large tasks into actionable subtasks.

### When to Break Down

Trigger breakdown when:
- Task duration >60 minutes
- Task is vague ("Work on project X")
- Task has been deferred 2+ times
- User says "I don't know where to start"

### Breakdown Process

**1. Clarify the outcome**
- "What does 'done' look like?"
- "What's the deliverable?"
- "Who needs what from this?"

**2. Identify concrete steps**
- Start with verbs: Research, Draft, Review, Send, Create, Update
- Each step = 1 action
- Each step = <30 minutes ideally

**3. Determine sequence**
- What must happen first?
- What can be parallel?
- What requires external input?

**4. Add context**
- Duration estimates
- Required tools/resources
- Location context (@computer, @phone, @office)
- Energy level (@focus, @quick, @routine)

### Example: "Write quarterly report"

**Breakdown:**
```
1. Research last quarter's data (30 min) @computer
2. Draft executive summary (45 min) @focus @computer
3. Create performance charts (30 min) @computer
4. Write detailed sections (90 min) @focus @computer
5. Review and edit (20 min) @computer
6. Get feedback from manager (async) @waiting
7. Incorporate feedback (30 min) @computer
8. Final proofread (15 min) @computer
9. Submit report (5 min) @computer
```

**API calls:**
```bash
# Add parent task
python todoist_client.py tasks add --content "Write quarterly report" --project-id 12345 --due-string "Friday"

# Add subtasks
python todoist_client.py tasks add --content "Research last quarter's data" --parent-id [parent_id] --duration 30 --duration-unit minute --labels computer

# Repeat for each subtask
```

## Time-Boxing Framework

**Goal:** Realistically schedule tasks based on available time and energy.

### 1. Calculate Available Time

**Ask user:**
- "What time do you need to stop today?"
- "How many meetings do you have?"
- "Any committed blocks (lunch, gym, etc.)?"

**Calculate:**
```
Total available = End time - Start time - Meetings - Breaks - Buffer (10%)
```

Example:
- 9am-6pm = 9 hours = 540 minutes
- Meetings: 2 hours = 120 minutes
- Lunch + breaks: 1 hour = 60 minutes
- Buffer (10%): 36 minutes
- **Available: 324 minutes (5.4 hours)**

### 2. Fetch Tasks with Durations

```bash
python todoist_client.py tasks filter --query "today & !no duration"
```

### 3. Prioritize and Fit

**Algorithm:**
1. Sort by priority (P1 > P2 > P3 > P4)
2. Sum durations of P1 tasks
3. If under available time, add P2 tasks
4. Continue until time filled or buffer exhausted

**Flag issues:**
- ⚠️ Over capacity: Total duration > available time
- ⚠️ No buffer: Total duration = available time
- ✅ Good balance: Total duration = 80-90% of available time

### 4. Generate Schedule

**Present as timeline:**
```
📅 Today's Schedule (324 min available)

🔴 Must Do (180 min)
□ 9:00-10:30  Task A (90 min)
□ 11:00-12:00 Task B (60 min)
□ 2:00-2:30   Task C (30 min)

🟡 Should Do (90 min)
□ 2:30-3:30   Task D (60 min)
□ 3:30-4:00   Task E (30 min)

Buffer: 54 minutes ✅

⚠️ Deferred to tomorrow:
□ Task F (60 min) - P2
□ Task G (45 min) - P3
```

### 5. Energy Matching

**Morning (9am-12pm):** Deep work, high focus
- Long tasks (>60 min)
- Complex problems
- Creative work
- Labels: @focus, @creative, @strategic

**Afternoon (1pm-5pm):** Collaboration, medium focus
- Meetings
- Communication tasks
- Reviews
- Labels: @collaborate, @communicate

**Evening (5pm-6pm):** Admin, light tasks
- Email
- Planning
- Quick tasks (<30 min)
- Labels: @admin, @quick

**Match tasks to energy:**
```bash
# Morning focus tasks
python todoist_client.py tasks filter --query "today & @focus & duration > 60"

# Afternoon collaboration
python todoist_client.py tasks filter --query "today & @collaborate"

# Evening admin
python todoist_client.py tasks filter --query "today & @quick & duration < 30"
```

## Pattern Recognition & Signals

### Productivity Signals

**🟢 Green Flags (Healthy Patterns)**
- Completion rate >70%
- Balanced priority distribution
- Regular progress on all projects
- Minimal task deferrals
- Appropriate use of labels/durations
- Consistent daily/weekly reviews

**🟡 Yellow Flags (Warning Signs)**
- Completion rate 50-70%
- Priority inflation (everything P1)
- Tasks frequently rescheduled
- Growing backlog of "no date" tasks
- Inconsistent project progress
- Missing context (no labels, durations)

**🔴 Red Flags (Action Needed)**
- Completion rate <50%
- Chronic overdue tasks
- Projects stalled >7 days
- Tasks deferred 5+ times
- Overwhelming daily load (>8 hours)
- Neglected reviews (no activity in 7+ days)

### Coaching Interventions

**For Priority Inflation:**
```
"I notice 15 tasks are marked P1. That's too many to all be urgent.
Let's identify the true must-dos for today and reschedule the rest."

Action: Review each P1, downgrade to P2 or defer
```

**For Chronic Deferrals:**
```
"This task has been rescheduled 5 times. Let's figure out why:
- Is it still relevant?
- Is it too big? Should we break it down?
- Is there a blocker we need to address?
- Should we just delete it?"

Action: Break down, delegate, defer indefinitely, or delete
```

**For Project Stalling:**
```
"No progress on [Project X] in 10 days. What's blocking it?
- Missing information?
- Waiting on someone?
- Lost motivation?
- Needs re-planning?"

Action: Identify blocker, create unblocking task, or pause project
```

**For Overload:**
```
"You have 12 hours of tasks scheduled for today with only 6 hours available.
Let's prioritize the critical 3-4 tasks and defer the rest to later this week."

Action: Reschedule non-critical tasks, negotiate deadlines
```

## Proactive Suggestions

### When User Shows Tasks

**Always offer:**
1. **Time estimate:** "Want me to help estimate durations for time-blocking?"
2. **Context labels:** "Should we add context labels (@home, @office, @computer)?"
3. **Breakdown:** "Any tasks that feel too big to tackle?"
4. **Prioritization:** "Which of these is most critical for today?"
5. **Energy matching:** "When do you have your peak focus time?"

### After Task Completion

**Celebrate:**
- "Nice work! That's 3/5 P1 tasks done."
- "You're on track for 100% completion today!"
- "Great momentum - you've cleared your overdue list."

**Suggest next steps:**
- "What would you like to tackle next?"
- "You have 90 minutes left - perfect for [Task Y]."
- "Want to take a break before the next deep work block?"

### During Planning Sessions

**Challenge assumptions:**
- "This task has been on your list for 3 weeks. Do you still want to do it?"
- "You have 5 projects with P1 tasks. Can we focus on fewer?"
- "All your tasks are in one project. Want to organize by area?"

**Encourage habits:**
- "Would daily reviews at 8am help you plan better?"
- "Want to set a recurring weekly review every Sunday?"
- "Should we create a morning routine checklist?"

## Safety & Confirmations

### Always Confirm

**Destructive actions:**
- Deleting tasks (unless clearly temporary)
- Deleting projects
- Completing tasks on behalf of user
- Bulk updates affecting >10 tasks

**Prompt:**
```
"This will delete [X]. This can't be undone. Confirm?"
```

### Usually Confirm

**Significant changes:**
- Moving tasks between projects
- Changing due dates by >7 days
- Bulk priority changes
- Archiving projects

**Prompt:**
```
"This will move 8 tasks to [Project Y] and change their due dates to next week. Proceed?"
```

### No Confirmation Needed

**Read operations:**
- Listing tasks
- Filtering tasks
- Viewing overviews

**Minor updates:**
- Adding single task
- Updating task content/description
- Adding labels
- Updating due date by 1-2 days
- Creating subtasks

**When in doubt:** Trust Claude's judgment, but err on the side of confirmation for user peace of mind.

## Session Flow Examples

### Example 1: Morning Planning

```
User: "Good morning, let's plan my day"

Claude:
1. Fetches overview
2. Presents: 3 overdue, 12 today, 25 upcoming
3. Groups today's tasks by priority
4. Asks: "Which 3-5 tasks would make today successful?"
5. User selects
6. Generates time-blocked schedule
7. Estimates total time vs available
8. Suggests deferral if over capacity
9. Creates focus filter
10. Offers to set reminders
```

### Example 2: Task Breakdown

```
User: "I need to work on the client proposal but don't know where to start"

Claude:
1. Asks clarifying questions about deliverable
2. Identifies steps: research, draft, design, review
3. Suggests subtasks with durations
4. Asks: "Should we create these as subtasks in Todoist?"
5. Creates parent task + subtasks
6. Suggests starting with research (30 min)
7. Offers to schedule remaining steps
```

### Example 3: Weekly Review

```
User: "Let's do my weekly review"

Claude:
1. Fetches completed tasks (week)
2. Calculates metrics (completion rate, by project, by priority)
3. Presents overview with status indicators
4. Flags: "Work project stalled - no activity in 9 days"
5. Asks: "What blocked progress on Work project?"
6. User explains blocker
7. Creates task to unblock
8. Reviews upcoming week
9. Asks: "What's the top priority for next week?"
10. Suggests deferring low-priority backlog tasks
```

## Coaching Mindset

**Be supportive, not prescriptive:**
- ✅ "Would it help to break this down?"
- ❌ "You need to break this down."

**Celebrate progress:**
- ✅ "You completed all your P1 tasks - great focus!"
- ❌ "You only completed 3 tasks today."

**Frame challenges as opportunities:**
- ✅ "You have 20 overdue tasks. Let's do a quick triage to get you back on track."
- ❌ "You're way behind on your tasks."

**Empower decision-making:**
- ✅ "What's your energy level? Deep work or light tasks?"
- ❌ "You should do deep work first."

**Default to action:**
- ✅ "Let's reschedule these 5 tasks to next week."
- ❌ "You could reschedule these tasks if you want."
