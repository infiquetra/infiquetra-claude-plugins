# SDLC Flow Metrics Reference

Quick reference for Infiquetra board-flow metrics. Source of truth:
`$INFIQUETRA_SDLC_PATH/config/sdlc-schema.json`,
`$INFIQUETRA_SDLC_PATH/docs/process/metrics-guide.md`, and
`$INFIQUETRA_SDLC_PATH/docs/process/kanban-workflow.md`.

---

## Cycle Time

**Definition**: Time from first active ownership to terminal workflow status.

| Board | Start | Terminal |
|-------|-------|----------|
| Jeff Intent | Active | Done |
| Asgard | Active | Done |
| Olympus | Assigned | Done, Closed, Cancelled |

Olympus history may include `In Progress`, `In Development`, or `Deployed`; tooling may
include those for historical calculations but should not create new movement with those names.

**Measurement**: P50, P85, and P95 via GitHub timeline events
(`ProjectV2ItemFieldValueEvent` on the Status field).

### Targets by Issue Type

| Type | P85 Target | SLA if applicable |
|------|------------|-------------------|
| Capability | < 5 days | -- |
| Enhancement | < 2 days | -- |
| Defect | < 1 day | Critical: 4 hours; high: 1 day; medium: 3 days |
| Exploration | < 3 days | -- |
| Context Update | < 1 day | -- |

---

## Throughput

**Definition**: Number of work items moved to a terminal workflow status per week.

**Use**: Capacity planning, delivery forecasting, and trend analysis.

| Board | Counted terminal statuses |
|-------|---------------------------|
| Jeff Intent | Done |
| Asgard | Done |
| Olympus | Done, Closed, Cancelled |

---

## WIP Age

**Definition**: How long current active items have been in their current Status.

**Use**: Identify stale work, trigger escalation, and surface bottlenecks.

| Board | Status | Threshold |
|-------|--------|-----------|
| Jeff Intent | Active, Verify | > 3 days |
| Asgard | Active, Verify | > 3 days |
| Olympus | Ready | > 2 days |
| Olympus | Planning | > 2 days |
| Olympus | Assigned | > 5 days |
| Olympus | In Progress | > 5 days |
| Olympus | In Review | > 2 days |

---

## Flow Efficiency

**Definition**: Active work time divided by total cycle time.

For Olympus, active work is primarily `Assigned` plus `In Review`. For intent-flow boards,
active work is `Active` plus `Verify`. `Ready`, `Shaping`, and `Planning` are wait or
preparation states unless a card's evidence shows otherwise.

Target: greater than 50%.

---

## How to Read Metrics

### When Cycle Time Is Over Target

1. Run `metrics column-time` on slow items.
2. Check WIP age for active or review bottlenecks.
3. Look for `Blocked`, `Needs Question`, or missing Jeff decision signals.
4. Confirm deployment delay is not being misread as workflow delay.
5. Use a longer `--days` window to separate noise from a trend.

### When Throughput Is Low

1. Check WIP limits.
2. Look at active-status aging.
3. Check if `Ready` is empty or poorly shaped.
4. Look at defect rate and unplanned work.
5. Consider whether large capabilities should be split.

### When WIP Age Is High

1. Identify the specific cards and discuss them in board review.
2. Add or confirm `blocked` / `Needs Question` state where appropriate.
3. Swarm, split, or move the card back to shaping if the issue is not actually ready.

---

## Metrics Quick Reference

| Metric | Command | Key flag |
|--------|---------|----------|
| Cycle time all types | `metrics cycle-time --project mount-olympus` | `--days N` |
| Cycle time by type | `metrics cycle-time --project mount-olympus --type capability` | `--type` |
| Throughput | `metrics throughput --project asgard` | `--weeks N` |
| WIP age | `metrics wip-age --project jeff-intent` | -- |
| Status breakdown | `metrics column-time --project mount-olympus --number 42` | `--number` |
