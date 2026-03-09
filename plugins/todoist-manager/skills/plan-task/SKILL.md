---
name: plan-task
description: Break down a complex task or project idea into well-structured, actionable Todoist subtasks with estimates and metadata
when_to_use: |
  Use this skill when the user:
  - Says "I don't know where to start" on a task
  - Has a task that's too big to execute directly
  - Wants to break down a project into steps
  - Asks "plan this out for me"
  - Has a task deferred 2+ times (likely too big or unclear)
  - Mentions a goal or outcome and wants it turned into tasks
  - Says "help me plan [project/initiative]"

  Auto-triggers:
  - "break this down"
  - "plan this task"
  - "I don't know where to start"
  - "create a plan for [X]"
  - "how do I approach [task]?"
  - "this task is too big"
  - "subtasks for [X]"
---

# Plan Task Skill

Converts a complex task or vague goal into a set of well-structured, actionable Todoist subtasks with realistic time estimates and appropriate metadata.

## When to Use This Skill

Use when:
- A task is too large to execute directly (>2 hours estimated)
- The task has been deferred 2+ times (usually means scope is unclear)
- The user has a goal but no clear steps
- The first action isn't obvious from the task content

## Prerequisites

- `TODOIST_TOKEN` set in environment
- `todoist-api-python` SDK installed (auto-installs if missing)
- Script: `plugins/todoist-manager/skills/todoist-manage/scripts/todoist_client.py`

## Planning Process

### Step 1: Understand the Goal

**Always clarify before planning.** Ask:

1. **Outcome:** "What does 'done' look like? What's the deliverable?"
2. **Audience:** "Who is this for? Who needs to review or approve it?"
3. **Deadline:** "When does this need to be complete?"
4. **Constraints:** "Any dependencies, blockers, or tools involved?"
5. **Estimate:** "How long do you think this will take total?"

Keep questions focused — ask 2-3 at most, not all 5.

### Step 2: Fetch Existing Task (if applicable)

If the user references an existing task:
```bash
python3 <script_path> tasks get --task-id <ID>
```

Or search by content:
```bash
python3 <script_path> tasks filter --query "search: <task content>"
```

### Step 3: Generate Subtask Plan

**Planning principles:**
- Each subtask starts with an action verb
- Each subtask is completable in 15-90 minutes
- Subtasks are sequenced logically (prerequisite before dependent)
- Include time estimates
- Add appropriate context labels

**Present plan for confirmation:**

```
📋 Plan for: "Write quarterly business review presentation"

Here's how I'd break this down:

1. Gather Q3 metrics data (30 min) @computer
   → Pull numbers from dashboard, spreadsheet, analytics

2. Draft slide outline (20 min) @computer @focus
   → 8-10 slides: Exec summary, KPIs, Wins, Challenges, Q4 goals

3. Write executive summary slide (30 min) @focus @computer
   → 3 bullet points max, key message clear

4. Create performance charts (45 min) @computer
   → Revenue trend, user growth, NPS score charts

5. Write KPI slides (45 min) @focus @computer
   → One slide per KPI with context and trend

6. Write Wins & Challenges slides (30 min) @computer

7. Draft Q4 goals slide (20 min) @computer @focus

8. Design cover and transitions (20 min) @computer

9. Self-review full deck (20 min) @computer
   → Read as audience, check flow and clarity

10. Send for stakeholder review (5 min) @quick
    → Email deck to Sarah and Marcus for feedback

11. Incorporate feedback (30 min) @computer

12. Final proofread and send (15 min) @quick

Total: ~5 hours across multiple sessions

Suggested split:
- Session 1 (2h): Steps 1-5
- Session 2 (2h): Steps 6-10
- Session 3 (1h): Steps 11-12

Create these as subtasks? [Y/N]
```

### Step 4: Create Parent Task (if needed)

If no parent task exists:
```bash
python3 <script_path> tasks add \
  --content "Write quarterly business review presentation" \
  --project-id <ID> \
  --priority 2 \
  --due-string "Friday" \
  --labels focus computer
```

### Step 5: Create Subtasks

```bash
# For each subtask in sequence:
python3 <script_path> tasks add \
  --content "Gather Q3 metrics data" \
  --parent-id <parent_task_id> \
  --duration 30 \
  --duration-unit minute \
  --labels computer \
  --priority 2

python3 <script_path> tasks add \
  --content "Draft slide outline" \
  --parent-id <parent_task_id> \
  --duration 20 \
  --duration-unit minute \
  --labels computer focus \
  --priority 2
# ... continue for all subtasks
```

### Step 6: Confirm and Summarize

After creating all subtasks:

```
✅ Created plan for "Write quarterly business review presentation"

12 subtasks created:
- Total estimated time: ~5 hours
- Suggested over 3 sessions
- First step: "Gather Q3 metrics data" (30 min)

Want to schedule Session 1 (Steps 1-5) for today?
```

## Task Planning Templates

See `../todoist-manage/references/productivity-workflows.md` for planning frameworks.
See `../task-review/references/task-templates.md` for 7 task type templates.

## Common Breakdowns

### Writing / Document Tasks

Structure:
1. Research / gather inputs
2. Outline structure
3. Write section by section
4. Self-review
5. External review
6. Incorporate feedback
7. Finalize and send/publish

### Coding / Engineering Tasks

Structure:
1. Understand requirements (read spec/ticket)
2. Explore existing code (find relevant files)
3. Plan approach (pseudo-code or doc)
4. Implement core logic
5. Add error handling
6. Write tests
7. Code review
8. Deploy / merge

### Research / Analysis Tasks

Structure:
1. Define key questions to answer
2. Identify sources
3. Gather data / read sources
4. Synthesize findings
5. Draft summary / recommendations
6. Review and finalize

### Meeting / Presentation Prep

Structure:
1. Define objectives and audience
2. Gather supporting data
3. Create outline / agenda
4. Build slides or talking points
5. Rehearse / review
6. Send pre-reads to attendees

### Project Planning Tasks

Structure:
1. Define success criteria
2. Identify stakeholders
3. List deliverables
4. Estimate effort per deliverable
5. Sequence and schedule
6. Identify risks
7. Document plan
8. Get approval

## Sizing Guidelines

| Complexity | Subtask Count | Session Count |
|------------|---------------|---------------|
| Simple     | 2-4 subtasks  | 1 session     |
| Medium     | 5-8 subtasks  | 1-2 sessions  |
| Complex    | 9-15 subtasks | 2-3 sessions  |
| Large      | 15+ subtasks  | Consider full project structure |

For Large tasks (15+ subtasks), recommend creating a **project** in Todoist with sections for phases, rather than a flat subtask list.

## Proactive Suggestions

After creating the plan, offer:

- **First subtask today?** "Want to add step 1 to today's focus list?"
- **Time-block?** "This is ~5 hours. Want to time-block sessions for this week?"
- **Dependencies?** "Steps 3-12 depend on step 1. Should we schedule step 1 first?"
- **Deadline check?** "With 5 hours of work and a Friday deadline, you'll need to start by Wednesday."

## Safety

- Always show the full plan before creating subtasks
- Confirm the parent task before creating children
- If parent task already has subtasks, show them and ask whether to add or replace
- Keep subtask count reasonable (<= 15 per parent)
