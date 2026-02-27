# Todoist Filter Query Syntax

Complete reference for Todoist's filter query language. Use with `tasks filter --query "<query>"`.

## Basic Filters

### Date Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `today` | Tasks due today | `today` |
| `tomorrow` | Tasks due tomorrow | `tomorrow` |
| `yesterday` | Tasks due yesterday | `yesterday` |
| `overdue` | All overdue tasks | `overdue` |
| `no date` | Tasks without due dates | `no date` |
| `no due date` | Tasks without due dates (alias) | `no due date` |

### Relative Date Ranges

| Filter | Description | Example |
|--------|-------------|---------|
| `7 days` | Tasks due in next 7 days | `7 days` |
| `next 7 days` | Tasks due in next 7 days (alias) | `next 7 days` |
| `30 days` | Tasks due in next 30 days | `30 days` |

### Specific Dates

| Filter | Description | Example |
|--------|-------------|---------|
| `Jan 1` | Tasks due on specific date | `Feb 24` |
| `Jan 1 - Jan 7` | Tasks due in date range | `Feb 24 - Mar 1` |

### Day of Week

| Filter | Description | Example |
|--------|-------------|---------|
| `Monday` | Tasks due on next Monday | `Friday` |
| `Mon` | Short form | `Fri` |

### Recurring Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `recurring` | All recurring tasks | `recurring` |
| `no recurring` | Non-recurring tasks only | `no recurring` |

## Priority Filters

| Filter | Description | Display Priority |
|--------|-------------|------------------|
| `p1` | Urgent priority | P1 (red flag) |
| `p2` | Higher priority | P2 (orange flag) |
| `p3` | High priority | P3 (yellow flag) |
| `p4` | Normal priority | P4 (white flag) |
| `no priority` | Tasks without explicit priority | None |

**Important:** Priority values are inverted in the API:
- API priority 4 = Display P1 (most urgent)
- API priority 3 = Display P2
- API priority 2 = Display P3
- API priority 1 = Display P4 (normal)

## Project Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `#ProjectName` | Tasks in specific project | `#Work` |
| `##ProjectName` | Tasks in project and subprojects | `##Personal` |
| `no project` | Inbox tasks | `no project` |

**Notes:**
- Project names are case-sensitive
- Use spaces as-is: `#Work Projects`
- For multiple words, no quotes needed

## Label Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `@LabelName` | Tasks with specific label | `@urgent` |
| `no labels` | Tasks without any labels | `no labels` |

**Notes:**
- Label names are case-sensitive
- Use spaces as-is: `@waiting for`

## Section Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `/SectionName` | Tasks in specific section | `/In Progress` |
| `no section` | Tasks not in any section | `no section` |

## Assignee Filters (Shared Projects)

| Filter | Description | Example |
|--------|-------------|---------|
| `assigned to: me` | Tasks assigned to you | `assigned to: me` |
| `assigned to: others` | Tasks assigned to others | `assigned to: others` |
| `assigned to: Name` | Tasks assigned to person | `assigned to: John` |
| `assigned by: me` | Tasks you assigned | `assigned by: me` |
| `assigned by: others` | Tasks others assigned | `assigned by: others` |
| `no assigned` | Unassigned tasks | `no assigned` |

**Note:** Personal accounts won't use assignee filters.

## Status Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `assigned` | Tasks with assignees | `assigned` |
| `unassigned` | Tasks without assignees | `unassigned` |
| `all` | All tasks (completed + incomplete) | `all` |

## Search Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `search: text` | Full-text search | `search: meeting notes` |

**Notes:**
- Searches task content and description
- Case-insensitive
- Use quotes for exact phrases: `search: "quarterly review"`

## Duration Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `duration < 30` | Tasks with duration less than 30 minutes | `duration < 30` |
| `duration > 60` | Tasks with duration more than 60 minutes | `duration > 60` |
| `duration = 30` | Tasks with exactly 30 minutes duration | `duration = 30` |
| `no duration` | Tasks without time estimates | `no duration` |

## Subtask Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `subtasks` | Only subtasks | `subtasks` |
| `no subtasks` | Only parent tasks | `no subtasks` |

## Combinators

### AND (`&`)
**All conditions must match**

```
today & p1
@urgent & #Work
overdue & #Personal & p1
```

### OR (`|`)
**Any condition can match**

```
today | overdue
p1 | p2
@urgent | @important
```

### NOT (`!`)
**Exclude matching items**

```
!#Work
!(p1 | p2)
today & !@routine
```

### Grouping with Parentheses
**Control evaluation order**

```
(today | tomorrow) & p1
#Work & (p1 | p2) & !@routine
(overdue | today) & (#Work | #Personal)
```

## Operator Precedence

1. `!` (NOT) - highest
2. `&` (AND)
3. `|` (OR) - lowest

Use parentheses to override: `!(p1 | p2)` vs `!p1 | p2`

## Common Recipes

### Daily Planning

```bash
# Focus tasks: urgent + due today
today & p1

# All of today's work
today

# Overdue + today
overdue | today

# This week's work
7 days
```

### Priority Management

```bash
# High-priority work tasks
#Work & (p1 | p2)

# Urgent tasks across all projects
p1

# Everything except low priority
!(p3 | p4)

# Important but not urgent
p2 & !overdue
```

### Project Planning

```bash
# Work tasks due this week
#Work & 7 days

# Personal overdue tasks
#Personal & overdue

# All work tasks with labels
#Work & !no labels

# Active work (has due date)
#Work & !no date
```

### Label-Based Workflows

```bash
# Waiting on others
@waiting & (today | overdue)

# Quick wins
@quick & p1

# Focus time needed
@focus & 7 days

# Errands to run
@errands & (today | tomorrow)
```

### Maintenance & Cleanup

```bash
# Tasks without due dates
no date

# Tasks without projects (inbox)
no project

# Tasks without labels
no labels

# Recurring tasks review
recurring & 30 days

# Long tasks (>60 minutes)
duration > 60
```

### Context-Based Work

```bash
# Home tasks for weekend
#Home & (Saturday | Sunday)

# Office tasks for this week
#Office & 7 days & !no date

# Computer tasks
@computer & (today | tomorrow)

# Phone tasks
@phone & !no date
```

### Time Blocking

```bash
# Short tasks (<30 min)
duration < 30 & today

# Long tasks (>60 min)
duration > 60 & 7 days

# Tasks needing time estimates
no duration & (today | tomorrow)
```

### Advanced Workflows

```bash
# Weekly review prep
(overdue | 7 days) & #Work & p1

# Focus session (urgent work, need focus time)
p1 & @focus & #Work

# Morning routine
today & @morning & no subtasks

# Planning view (next week, no routine tasks)
7 days & !@routine & !p4

# Blocked tasks (waiting + important)
@waiting & (p1 | p2)
```

## Query Best Practices

1. **Start simple, add complexity** - Begin with `today`, then refine
2. **Use labels for context** - `@home`, `@office`, `@computer`, `@phone`
3. **Combine dates and priorities** - `today & p1` for daily focus
4. **Group similar conditions** - `(p1 | p2)` clearer than `p1 | p2 | p3`
5. **Use negation sparingly** - `!@routine` better than listing all other labels
6. **Test queries incrementally** - Add one filter at a time
7. **Save complex queries as filters** - Reuse in Todoist app

## Query Limits

- Maximum query length: ~500 characters
- Complex queries with many ORs may be slow
- Deeply nested parentheses can cause parsing issues
- Use saved filters in Todoist app for very complex queries

## Troubleshooting

### Query Returns Nothing

- Check project/label names for typos (case-sensitive)
- Verify date format: `Feb 24` not `2/24`
- Use `all` to see if tasks exist: `#Work & all`
- Remove filters one by one to isolate issue

### Query Returns Too Many Results

- Add date filter: `& today`
- Add priority filter: `& (p1 | p2)`
- Add project filter: `& #Work`
- Use NOT to exclude: `& !@routine`

### Syntax Errors

- Balance parentheses: `(today | tomorrow)`
- Don't mix quotes: Use `search: "text"` not `search: 'text'`
- Space after combinator: `today & p1` not `today&p1`
- Use `#` for projects, `@` for labels, `/` for sections

## Examples by Use Case

### Getting Things Done (GTD)

```bash
# Next actions
@next & no date
@next & (today | overdue)

# Waiting for
@waiting

# Someday/maybe
@someday

# Projects (tasks with subtasks)
no subtasks & #Projects
```

### Time Blocking

```bash
# Morning (short tasks)
today & duration < 30

# Afternoon (deep work)
today & duration > 60

# Evening (personal)
today & #Personal
```

### Pomodoro Technique

```bash
# 25-minute tasks
duration = 25

# Focus sessions
@focus & today
```

### Weekly Planning

```bash
# This week's priorities
7 days & (p1 | p2)

# Upcoming deadlines
next 7 days & !today

# Overdue review
overdue & !@routine
```
