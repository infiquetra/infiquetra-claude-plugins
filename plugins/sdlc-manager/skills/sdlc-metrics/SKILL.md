---
name: sdlc-metrics
description: |
  Flow metrics and analysis for the Infiquetra Mount Olympus Kanban board using timeline events.
  Provides cycle time percentiles, throughput trends, WIP age distribution, per-column
  time breakdowns, and flow efficiency — with targets by issue type and interpretation guidance.
when_to_use: |
  Use this skill when the user wants to:

  Cycle time analysis:
  - "how long are issues taking", "what's our cycle time", "how fast are we delivering"
  - "cycle time report", "are we hitting our cycle time targets", "cycle time breakdown"
  - "how long did this capability take", "how long has issue #42 been in progress"
  - "compare this month to last month", "are we getting faster"

  Throughput analysis:
  - "how many capabilities did we ship last week", "deployment velocity",
    "throughput this month", "throughput report", "how many items did we complete"
  - "are we on track for our throughput targets", "weekly delivery rate"

  WIP age and aging work:
  - "how old are our in-progress items", "what's been sitting in development too long"
  - "aging work items", "WIP age report", "what's stale", "aging in E2E"

  Flow health and efficiency:
  - "how's our flow", "are we meeting our targets", "flow efficiency",
    "are we healthy", "flow health check", "overall metrics summary"
  - "flow efficiency report", "what percentage of time is active vs. waiting"

  SLA and defect response:
  - "are any defects violating SLA", "critical defect response time",
    "defect SLA check", "are high priority defects on track"

  Per-column time breakdown:
  - "how long do items spend in E2E testing", "column time breakdown for issue #42"
  - "where's the bottleneck", "which column is slowest"
---

# SDLC Metrics

Flow metrics and analysis for the Infiquetra Mount Olympus Kanban board using GitHub timeline
events. Measures cycle time, throughput, WIP age, and flow efficiency — with targets by issue type.

## Script Location

```
$INFIQUETRA_SDLC_PATH/../infiquetra-claude-plugins/plugins/sdlc-manager/scripts/sdlc_manager.py
```

> If `$INFIQUETRA_SDLC_PATH` is unset, use `~/workspace/infiquetra/infiquetra-sdlc` as the default base path.

**IMPORTANT**: Always use `python3` (not `python`) to run the script.

## How Timeline Metrics Work

The script queries `timelineItems` on GitHub issues to find `ProjectV2ItemFieldValueEvent`
entries showing status column changes. From these events it calculates:

- **Time in each column**: Timestamp of entry into column -> timestamp of exit from column
- **Cycle time**: Time from first entry into "In Development" through "Deployed"
- **Percentiles**: P50 (median), P85 (target benchmark), P95 (worst-case tail)
- **WIP age**: For in-progress items, elapsed time since entering the current column

## Core Operations

### Cycle Time

```bash
# Cycle time for all issue types over last 30 days
python3 sdlc_manager.py metrics cycle-time --project mount-olympus

# Filter by days window
python3 sdlc_manager.py metrics cycle-time --project mount-olympus --days 14

# Filter to specific issue type
python3 sdlc_manager.py metrics cycle-time --project mount-olympus --type capability
python3 sdlc_manager.py metrics cycle-time --project mount-olympus --type enhancement
python3 sdlc_manager.py metrics cycle-time --project mount-olympus --type defect
```

#### Sample Output

```
Cycle Time Report — mount-olympus (last 30 days)

              P50      P85      P95    Target   Status
capability    3.2d     4.8d     7.1d   < 5d     ✓ On target
enhancement   1.1d     1.8d     3.2d   < 2d     ✓ On target
defect        0.4d     0.9d     1.5d   < 1d     ✓ On target
exploration   1.5d     2.6d     3.0d   < 3d     ✓ On target

Items measured: 18 (9 capability, 5 enhancement, 3 defect, 1 exploration)
Slowest item:  #38 capability "User onboarding service" — 7.1 days
               Bottleneck: E2E Testing (2.3 days)
```

### Throughput

```bash
# Throughput over last 4 weeks (default)
python3 sdlc_manager.py metrics throughput --project mount-olympus

# Specify weeks window
python3 sdlc_manager.py metrics throughput --project mount-olympus --weeks 8

# Filter by issue type
python3 sdlc_manager.py metrics throughput --project mount-olympus --type capability
```

### WIP Age

```bash
# Current WIP age distribution (all in-progress items)
python3 sdlc_manager.py metrics wip-age --project mount-olympus
```

Output shows each in-progress item, which column it is in, and how long it has been there.
Items exceeding age thresholds are flagged.

### Per-Column Time Breakdown

```bash
# How long a specific issue spent in each column
python3 sdlc_manager.py metrics column-time --project mount-olympus --number 42
```

Useful for diagnosing where an individual item got stuck.

## Targets by Issue Type

### Cycle Time Targets (P85)

| Issue Type | P85 Target | Notes |
|------------|------------|-------|
| Capability | < 5 days | End-to-end: In Development -> Deployed |
| Enhancement | < 2 days | Smaller scope |
| Defect (general) | < 1 day | Highest urgency |
| Exploration | < 3 days | Timeboxed research |
| Context Update | < 1 day | Documentation |

### Defect SLA Targets

| Priority | SLA | Description |
|----------|-----|-------------|
| Critical | 4 hours | System down, data loss, security breach |
| High | 1 day | Major functionality broken |
| Medium | 3 days | Minor functionality broken |
| Low | When capacity | Cosmetic or rare edge case |

### Throughput Targets (per week)

| Issue Type | Target | Direction |
|------------|--------|-----------|
| Capabilities | 2-4 | Higher is better |
| Enhancements | 5-10 | Higher is better |
| Defects | < 2 | Lower is better |

### WIP Age Thresholds (flag as aging)

| Column | Age Threshold |
|--------|---------------|
| Ready | > 2 days |
| In Development | > 5 days |
| E2E Testing | > 1 day |
| Deployment Ready | > 2 days |

### Flow Efficiency Target

**Target**: > 50%

**Formula**: (time in In Development + time in E2E Testing) / total cycle time

Active columns are In Development and E2E Testing. Waiting columns are Ready and
Deployment Ready. High wait time in Deployment Ready typically indicates deployment
window constraints.

## Natural Language Examples

**"What's our cycle time for capabilities this month?"**
-> `metrics cycle-time --project mount-olympus --type capability --days 30`

**"How many capabilities did we ship last week?"**
-> `metrics throughput --project mount-olympus --weeks 1 --type capability`

**"How old are our in-progress items?"**
-> `metrics wip-age --project mount-olympus`

**"How long has issue #42 been in development?"**
-> `metrics column-time --project mount-olympus --number 42`

**"Are we meeting our targets?"**
-> Run `metrics cycle-time` and `metrics throughput`, compare to targets above

**"Are any defects violating SLA?"**
-> `metrics wip-age --project mount-olympus` — look for defects flagged as aging

**"Compare this month to last month"**
-> `metrics cycle-time --project mount-olympus --days 30` vs. `--days 60` (compare first/second half)

## Interpreting Results

### When Cycle Time is Over Target

1. **Run column-time on slow items** to find where they got stuck
2. **Check E2E Testing aging** — manual testing is often the bottleneck
3. **Check Deployment Ready aging** — deployment window delays inflate cycle time
4. **Look for blocked items** — blocked label can stall flow for days
5. **Check WIP in In Development** — high WIP creates context switching, slows everything

### When Throughput is Low

1. **Check WIP in In Development** — if near or over limit, team may be stuck
2. **Check In Development aging** — items not completing drive low throughput
3. **Check Ready column** — if empty, team may lack prioritized work
4. **Look at Objective completion** — are all capabilities tied to a blocked Objective?

### When WIP Age is High

1. **Identify the specific items** and ask about blockers in standup
2. **Consider swarming** — additional developers on a stuck item can unblock it
3. **Check for external blockers** — dependencies on other teams or systems
4. **Escalate per policy**: blocked > 4 hours -> tech lead; blocked > 1 day -> EM

### When Flow Efficiency is Low (< 50%)

1. **High wait in Deployment Ready** -> deployment scheduling delays
2. **High wait in Ready** -> context switching or team not pulling promptly
3. **Multiple handoffs** -> check if items are bouncing between columns
4. **Blocked time** -> blocked items count as wait time, reducing efficiency

## Workflow Examples

### Weekly Metrics Review

```bash
# Run for mount-olympus board
python3 sdlc_manager.py metrics cycle-time --project mount-olympus --days 7
python3 sdlc_manager.py metrics throughput --project mount-olympus --weeks 4
python3 sdlc_manager.py metrics wip-age --project mount-olympus
```

Compare each metric to the targets table. Share summary in #mount-olympus Discord channel.

### SLA Check for Defects

```bash
# Get all in-progress items (includes defects with their age)
python3 sdlc_manager.py metrics wip-age --project mount-olympus

# For any defect flagged as aging, check full timeline
python3 sdlc_manager.py metrics column-time --project mount-olympus --number <N>
```

Cross-reference priority label (`critical`/`high-priority`/`medium-priority`) against SLA targets above.

### Diagnosing a Bottleneck

```bash
# 1. Check which column has the most aging items
python3 sdlc_manager.py metrics wip-age --project mount-olympus

# 2. Check cycle time breakdown to see which column adds the most time
python3 sdlc_manager.py metrics cycle-time --project mount-olympus --days 30

# 3. Drill into specific slow items
python3 sdlc_manager.py metrics column-time --project mount-olympus --number <N>
```

## Reference Documents

- `references/metrics-targets.md` — Complete targets, definitions, and interpretation guide
- `skills/sdlc-board/references/kanban-workflow.md` — Column definitions and WIP limits
