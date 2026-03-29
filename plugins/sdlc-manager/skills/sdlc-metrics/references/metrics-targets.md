# SDLC Flow Metrics Reference

Quick reference for Infiquetra Mount Olympus Kanban flow metrics: definitions, targets, and
interpretation guidance. Source of truth: `$INFIQUETRA_SDLC_PATH/docs/process/kanban-workflow.md`
and `$INFIQUETRA_SDLC_PATH/docs/process/issue-types.md`.

---

## Cycle Time

**Definition**: Time from first entry into "In Development" to when the item reaches "Deployed".

**Measurement**: P50 (median), P85 (target benchmark), P95 (worst-case tail), via GitHub
timeline events (`ProjectV2ItemFieldValueEvent` on status field).

**Note**: Cycle time measures In Development entry -> Deployed. It does not include time
sitting in Ready (that is lead time / wait time, tracked separately via WIP age).

### Targets by Issue Type

| Type | P85 Target | SLA (if applicable) |
|------|------------|---------------------|
| Capability | < 5 days | -- |
| Enhancement | < 2 days | -- |
| Defect (general) | < 1 day | -- |
| Defect (Critical) | -- | 4 hours |
| Defect (High) | -- | 1 day |
| Defect (Medium) | -- | 3 days |
| Defect (Low) | -- | When capacity |
| Exploration | < 3 days | -- |
| Context Update | < 1 day | -- |

### Typical Column Durations (reference, not targets)

| Column | Capability | Enhancement | Defect |
|--------|------------|-------------|--------|
| In Development | 3-12 days | 1-4 days | 2 hrs - 1 day |
| E2E Testing | 4-8 hours | 1-4 hours | 30 min - 2 hours |
| Deployment Ready | 0-2 days | 0-2 days | 0-2 days |

---

## Throughput

**Definition**: Number of work items moved to "Deployed" per week.

**Measurement**: Count of completed items, tracked by issue type, rolling 4-week average.

**Use**: Capacity planning, delivery forecasting, trend analysis.

### Targets by Issue Type (per week, team of 5)

| Type | Target | Direction |
|------|--------|-----------|
| Capabilities | 2-4 | Higher is better |
| Enhancements | 5-10 | Higher is better |
| Defects | < 2 | Lower is better (indicates quality) |
| Explorations | 1-2 | Varies |
| Context Updates | 3-5 | Varies |

---

## WIP Age

**Definition**: How long current in-progress items have been in their column.

**Measurement**: Days since item entered its current column, calculated for all items
not yet in Deployed. 85th percentile age by column.

**Use**: Identify stale work, trigger escalations, surface bottlenecks.

### Age Thresholds (flag as aging)

| Column | Threshold | Action When Exceeded |
|--------|-----------|----------------------|
| Ready | > 2 days | Review in standup — is it truly prioritized? |
| In Development | > 5 days | Check for blockers, consider swarming |
| E2E Testing | > 1 day | Check for test failures or environment issues |
| Deployment Ready | > 2 days | Check deployment window availability |

---

## Flow Efficiency

**Definition**: Active time divided by total cycle time, expressed as a percentage.

**Formula**: (time in In Development + time in E2E Testing) / total cycle time

**Target**: > 50%

**Active columns**: In Development, E2E Testing (team is doing work)
**Wait columns**: Ready, Deployment Ready (item is queued, not being actively worked)

**Example**:
```
Item total cycle time: 10 days
- In Development: 5 days (active)
- E2E Testing: 1 day (active)
- Deployment Ready: 4 days (wait)

Flow Efficiency = (5 + 1) / 10 = 60%  -- Above target
```

---

## How to Read Metrics

### When cycle time is over target

1. Run `metrics column-time` on slow items to find which column consumed the most time
2. Check E2E Testing aging — manual testing is often a bottleneck for teams new to this process
3. Check Deployment Ready aging — deployment window constraints inflate cycle time
   without reflecting development speed
4. Look for items with the `blocked` label — blocked time counts against cycle time
5. High WIP in In Development causes context switching, which slows all items down
6. Consider: is this a one-off or a trend? Use a longer `--days` window to distinguish noise
   from systemic issues

### When throughput is low

1. Check WIP limits — if In Development is at or over limit, team can't pull new work to complete
2. Look at In Development aging — items not finishing drive low throughput
3. Check if Ready is empty — if there's no prioritized work, throughput will drop
4. Look at defect rate — high defect volume can crowd out Capability and Enhancement delivery
5. Consider Capability size — very large capabilities reduce weekly throughput even if flow is healthy

### When WIP age is high

1. Identify the specific items and discuss in standup
2. Add `blocked` label immediately if blocked by external dependency
3. Consider swarming — pair or bring additional developers to clear the item
4. Escalate per policy:
   - Blocked > 4 hours -> tech lead
   - Blocked > 1 day -> engineering manager
5. If item is not blocked but slow, check In Development WIP limits

### When flow efficiency is low (< 50%)

1. High wait in Deployment Ready -> check deployment process and scheduling
2. High wait in Ready -> items are being created faster than the team is pulling them
3. Items bouncing between columns -> check why items are being moved backwards
4. Blocked time -> investigate root causes and track frequency

---

## Defect SLA Escalation Policies

| Condition | Action | Timeframe |
|-----------|--------|-----------|
| Critical defect created | Pull directly to In Development, skip Ready | Immediately |
| Critical defect not fixed | Escalate to EM and stakeholders | 2 hours |
| High defect aging > 1 day | Flag in standup, escalate to tech lead | 24 hours |
| Medium defect aging > 3 days | Review priority in standup | 72 hours |
| Any defect in E2E > 4 hours | Check for test environment issues | 4 hours |
| Any item blocked | Add `blocked` label, notify team in Discord | Immediately |
| Item blocked > 4 hours | Escalate to tech lead | 4 hours |
| Item blocked > 1 day | Escalate to engineering manager | 24 hours |

---

## Metrics Quick Reference

| Metric | Command | Key flag |
|--------|---------|----------|
| Cycle time all types | `metrics cycle-time --project mount-olympus` | `--days N` |
| Cycle time by type | `metrics cycle-time --project mount-olympus --type capability` | `--type` |
| Throughput | `metrics throughput --project mount-olympus` | `--weeks N` |
| WIP age | `metrics wip-age --project mount-olympus` | -- |
| Column breakdown | `metrics column-time --project mount-olympus --number 42` | `--number` |

Project: `mount-olympus`
