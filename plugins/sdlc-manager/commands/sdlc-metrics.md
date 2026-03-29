---
name: sdlc-metrics
description: Show flow metrics dashboard for Infiquetra project boards — cycle time, throughput, WIP age, and flow health
---

Display a comprehensive flow metrics dashboard for an Infiquetra project board, showing cycle times, throughput, WIP age, and comparisons against targets.

## Usage

```
/sdlc-metrics [project] [--type metric-type]
```

## Arguments

- `project` — Project name: `mount-olympus` (default) or `strategic`
- `--type` — Optional metric type: `cycle-time`, `throughput`, `wip-age`, or `all` (default)

## What This Does

1. Shows cycle time percentiles (P50/P85/P95) vs. targets
2. Shows throughput by issue type for last 4 weeks
3. Shows WIP age for all in-progress items
4. Flags metrics that are over target
5. Provides interpretation and recommendations

## Examples

```
/sdlc-metrics
/sdlc-metrics mount-olympus
/sdlc-metrics strategic --type cycle-time
/sdlc-metrics mount-olympus --type throughput
/sdlc-metrics mount-olympus --type wip-age
```

## Script Commands

```bash
SCRIPT=~/.claude/plugins/cache/infiquetra-plugins/sdlc-manager/1.0.0/scripts/sdlc_manager.py

# Cycle time (uses timeline events — may take a moment)
python3 $SCRIPT metrics cycle-time --project mount-olympus --days 30

# Throughput by week
python3 $SCRIPT metrics throughput --project mount-olympus --weeks 4

# WIP age (fast — no timeline events needed)
python3 $SCRIPT metrics wip-age --project mount-olympus
```

## Metric Targets

| Issue Type | Cycle Time P85 | SLA |
|------------|---------------|-----|
| Capability | < 5 days | -- |
| Enhancement | < 2 days | -- |
| Defect (Critical) | -- | 4 hours |
| Defect (High) | -- | 1 day |
| Defect (Medium) | -- | 3 days |

Throughput targets: 2-4 capabilities/week, 5-10 enhancements/week

## Instructions

When the user invokes `/sdlc-metrics [project] [--type metric-type]`:

1. Determine project (default: mount-olympus)
2. Determine which metrics to show (default: all)
3. Run appropriate commands:
   - Cycle time: Note this requires fetching timeline events and may take 30-60s
   - Throughput: Fast, just looks at deployed items
   - WIP age: Fast, just looks at current board state
4. Present results with:
   - Clear comparison vs. targets (pass/fail markers)
   - Interpretation of what's over/under target
   - Specific recommendations when metrics are over target
5. Offer follow-up: "Want me to investigate the aging items in E2E Testing?"

### Interpreting Metrics

**Cycle time over target**:
- Check WIP age for bottlenecks
- Look for items stuck in E2E Testing or Deployment Ready
- Consider if WIP limits are being respected

**Throughput too low**:
- Check if too many items are in In Development simultaneously
- Look for blocked items
- Check if WIP limits are being exceeded

**WIP age high**:
- Items stuck >3 days: blockers or WIP violations
- Recommend flagging in standup and considering swarming

Use the `sdlc-metrics` skill for detailed metric analysis or the `sdlc-operator` agent for comprehensive SDLC health reports.
