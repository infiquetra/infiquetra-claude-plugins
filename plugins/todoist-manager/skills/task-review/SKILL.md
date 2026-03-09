---
name: task-review
description: Review 1-3 Todoist tasks for clarity, actionability, and execution readiness using a structured scoring rubric
when_to_use: |
  Use this skill when the user:
  - Asks to "review" tasks before working on them
  - Wants to know if a task is ready to execute
  - Asks "is this task clear enough?"
  - Wants feedback on task quality or completeness
  - Is about to start a task and wants to double-check it
  - Says "prepare this task" or "make this task ready"
  - Wants to review 1-3 specific tasks for readiness

  Auto-triggers:
  - "review task [X]"
  - "is this task ready?"
  - "check my tasks"
  - "prepare task for execution"
  - "what's wrong with this task?"
  - "make this task actionable"
---

# Task Readiness Review Skill

Structured review of 1-3 Todoist tasks for clarity, actionability, and execution readiness. Scores each task across 5 dimensions and provides specific improvement recommendations.

## When to Use This Skill

Use for **focused reviews of 1-3 tasks** when the user wants:
- To understand if a task is ready to execute
- Specific feedback on task quality
- Recommendations to improve task clarity

**For batch reviews of many tasks**, use the **todoist-manager agent** instead.

## Prerequisites

- `TODOIST_TOKEN` set in environment
- `todoist-api-python` SDK installed (auto-installs if missing)
- Script: `plugins/todoist-manager/skills/todoist-manage/scripts/todoist_client.py`

## Review Process

### Step 1: Fetch Task Details

```bash
python3 <script_path> tasks get --task-id <ID>
```

If user provided task content instead of ID, search first:
```bash
python3 <script_path> tasks filter --query "search: <task content>"
```

### Step 2: Score the Task

Score each dimension using the **readiness rubric** (`references/readiness-rubric.md`):

| Dimension | Max Score | Key Question |
|-----------|-----------|--------------|
| Clarity | 2 | Is the task content unambiguous? |
| Actionability | 2 | Does it start with a clear action verb? |
| Scope | 2 | Can it be done in one session (<2 hours)? |
| Context | 2 | Does it have the right metadata? |
| Outcome | 2 | Is "done" clearly defined? |

**Total: 10 points**

### Step 3: Present Scorecard

Format:
```
📋 Task Review: "[Task Content]"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Clarity     ██████░░░░ 3/5  ⚠️
Actionability ██████████ 5/5 ✅
Scope       ████░░░░░░ 2/5  ❌
Context     ████████░░ 4/5  ✅
Outcome     ██████░░░░ 3/5  ⚠️

Overall: 17/25 — Needs Improvement

Issues Found:
❌ Scope too large — estimate suggests 3-4 hours
⚠️ Missing due date for time-sensitive work
⚠️ Outcome not clearly defined

Recommendations:
1. Break into 2-3 subtasks (30-60 min each)
2. Add due date: --due-string "friday"
3. Add success criterion to description

Want me to apply these improvements? [Y/N]
```

### Step 4: Apply Improvements (with confirmation)

Based on review, offer to:

**Update task content:**
```bash
python3 <script_path> tasks update \
  --task-id <ID> \
  --content "Verb + specific action + outcome" \
  --description "Done when: [criterion]" \
  --due-string "friday" \
  --labels focus computer
```

**Break into subtasks:**
```bash
# Create subtasks from parent
python3 <script_path> tasks add \
  --content "Step 1: Research X" \
  --parent-id <ID> \
  --duration 30 \
  --duration-unit minute
```

**Add context labels:**
```bash
python3 <script_path> tasks update \
  --task-id <ID> \
  --labels focus computer
```

## Scoring Reference

See `references/readiness-rubric.md` for the complete 5-dimension scoring rubric with detailed criteria.

See `references/task-templates.md` for 7 task type templates (research, writing, coding, meeting, admin, communication, planning).

## Review Output Formats

### Quick Review (single task)

```
✅ Task Ready: "Write unit tests for auth module"
Score: 22/25 — Ready to Execute

Minor suggestions:
- Consider adding @focus label for deep work
- Due date is 5 days out — still realistic?
```

### Detailed Review (task needing work)

```
📋 Task Review: "Work on the project"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ NOT READY — Score: 8/25

Critical Issues:
1. Clarity (1/5): "Work on the project" is too vague
   → Which project? What aspect? What outcome?

2. Actionability (1/5): No action verb
   → Start with: Research / Write / Review / Build / Fix / Test

3. Scope (2/5): "Project" implies undefined scope
   → What's the smallest meaningful next step?

4. Context (2/5): No project, labels, or due date
   → Add context to make it filterable

5. Outcome (2/5): No success criterion
   → When is this "done"?

Revised task suggestion:
"Draft project requirements document for Q2 feature"
+ Description: "Done when: 1-page requirements doc reviewed by stakeholder"
+ Due: next Tuesday
+ Labels: @focus @computer
+ Duration: 90 min

Apply this revision? [Y/N]
```

### Batch Review (2-3 tasks)

```
📋 Reviewing 3 Tasks for Readiness
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Task 1: "Write unit tests for auth module" — 22/25 Ready
⚠️  Task 2: "Update documentation" — 14/25 Needs Work
❌ Task 3: "Handle the client thing" — 6/25 Not Ready

Detailed reviews follow...
```

## Improvement Patterns

### Vague → Specific

| Before | After |
|--------|-------|
| "Work on project" | "Write API endpoint for user login" |
| "Do the report" | "Draft Q2 metrics report (2 pages)" |
| "Fix the bug" | "Fix null pointer in user.profile.get()" |
| "Call someone" | "Call Sarah re: contract renewal" |

### Missing Action Verb

Strong action verbs: Research, Write, Review, Build, Fix, Test, Deploy, Update, Draft, Design, Schedule, Send, Call, Analyze, Create, Document

### Scope Reduction

If task > 2 hours:
1. Identify the smallest meaningful next step
2. Make that the task
3. Add remaining steps as subtasks

### Context Labels

**Energy context:**
- `@focus` — requires deep concentration
- `@quick` — under 15 minutes
- `@routine` — habitual, low-energy

**Location context:**
- `@computer` — requires desktop/laptop
- `@phone` — can do from phone
- `@office` — requires physical presence
- `@home` — home environment needed

**Status context:**
- `@waiting` — blocked on someone else
- `@blocked` — has an explicit blocker

## Safety

- Always show proposed changes before applying
- Never delete task content without confirmation
- Preserve existing labels/metadata when adding new ones
- If breaking into subtasks, keep parent task as container
