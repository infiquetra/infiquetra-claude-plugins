---
name: metrics
description: Show flow metrics for Infiquetra project boards
---

Display a flow metrics dashboard for an Infiquetra project board: cycle time,
throughput, WIP age, and bottleneck hints.

## Usage

```
/metrics [jeff-intent|asgard|mount-olympus] [--type metric-type]
```

## Arguments

- `project` - Project name: `mount-olympus` (default), `asgard`, or `jeff-intent`
- `--type` - Optional metric type: `cycle-time`, `throughput`, `wip-age`, or `all` (default)

## What This Does

1. Shows cycle time percentiles against targets.
2. Shows terminal-status throughput.
3. Shows WIP age for current active items.
4. Flags metrics that are over target.
5. Separates workflow Status from deployment environment state.

## Examples

```
/metrics
/metrics mount-olympus
/metrics asgard --type throughput
/metrics jeff-intent --type wip-age
```

## Script Commands

```bash
SCRIPT=~/.claude/plugins/cache/infiquetra-plugins/mission-control/1.6.0/scripts/sdlc_manager.py

python3 $SCRIPT metrics cycle-time --project mount-olympus --days 30
python3 $SCRIPT metrics throughput --project asgard --weeks 4
python3 $SCRIPT metrics wip-age --project jeff-intent
```

## Instructions

When the user invokes `/metrics [project] [--type metric-type]`:

1. Determine project, defaulting to `mount-olympus`.
2. Determine which metrics to show, defaulting to all.
3. Run the matching metric commands.
4. Summarize pass/fail signals, bottlenecks, and concrete next actions.

Use the `metrics` skill for detailed interpretation or the `sdlc-operator` agent for
multi-step SDLC health reports.
